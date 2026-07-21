"""Deterministic evaluation and promotion gate for skill-backed orchestration.

The gate evaluates the finite built-in skill set through the same resolver,
compiler, MCP loopback, fixture runtime, provider/A2A binding, communication
isolation, and runtime-guardrail owners used by the product path.  It never
dispatches a real provider call or discovers an external peer.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from .agent_orchestration_compiler import compile_agent_orchestration_graph
from .communication_isolation import validate_typed_communication_isolation
from .common import now_iso, slugify, write_json
from .mcp_broker_service import McpBrokerService
from .project_service import ProjectService
from .runtime_guardrails import evaluate_runtime_guardrails
from .security import SECRET_RE, redact_sensitive
from .skill_orchestration_validation import load_skill_orchestration_manifest, resolve_skill_to_graph
from .task_service import TaskService


SKILL_ORCHESTRATION_EVALUATION_SCHEMA_VERSION = "astrabridge-skill-orchestration-evaluation-gate-v1"
SKILL_ORCHESTRATION_EVALUATION_MANIFEST_SCHEMA_VERSION = "astrabridge-skill-orchestration-evaluation-manifest-v1"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRODUCTIZED_STATUSES = frozenset({"productized", "provider-qualified", "external-a2a-qualified"})
_EVALUATION_MODES = frozenset({"evaluate", "promotion"})

# Keep this list finite and explicit.  New patterns must be added with a
# parameter fixture and a corresponding evaluation report rather than being
# silently discovered by a broad filesystem scan.
BUILTIN_SKILL_CASES: tuple[dict[str, Any], ...] = (
    {
        "skill_id": "astrabridge.supervisor-worker-synthesizer",
        "parameters": {"task_goal": "Evaluate a bounded supervisor worker synthesis run."},
    },
    {
        "skill_id": "astrabridge.review-fix-verify",
        "parameters": {
            "task_goal": "Evaluate a bounded review and verification run.",
            "target_files": ["README.md"],
            "test_command": "python -m unittest",
        },
    },
    {
        "skill_id": "astrabridge.fanout-research-synthesis",
        "parameters": {
            "research_goal": "Evaluate bounded fanout research synthesis.",
            "branch_scopes": ["official documentation", "compatibility evidence"],
        },
    },
    {
        "skill_id": "astrabridge.provider-update-smoke",
        "parameters": {
            "update_goal": "Evaluate a provider metadata smoke gate.",
            "provider_ids": ["qwen"],
            "smoke_cases": ["catalog"],
            "promotion_owner": "evaluation-owner",
        },
    },
    {
        "skill_id": "astrabridge.multimodal-capability-adapter",
        "parameters": {
            "task_goal": "Evaluate one bounded multimodal capability adaptation.",
            "capability_id": "vision.analyze",
            "input_artifacts": [{"kind": "image", "ref": "artifact.image"}],
            "desired_output": "structured result",
        },
    },
)


def run_skill_orchestration_evaluation_gate(
    *,
    mode: str = "evaluate",
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
    skill_ids: Iterable[str] | None = None,
    fixture_runs: bool = True,
) -> dict[str, Any]:
    """Evaluate the built-in skill set and persist a redacted gate bundle.

    ``mode=evaluate`` reports whether the candidate set is structurally safe to
    test.  ``mode=promotion`` additionally requires a productized lifecycle
    status and completed fixture evidence for every selected pattern.  Both
    modes use the same safety checks; promotion mode only tightens admission.
    """

    resolved_mode = str(mode or "evaluate").strip().lower() or "evaluate"
    if resolved_mode not in _EVALUATION_MODES:
        raise ValueError("mode must be evaluate or promotion.")
    selected_ids = [str(item).strip() for item in list(skill_ids or []) if str(item or "").strip()]
    cases = [deepcopy(case) for case in BUILTIN_SKILL_CASES if not selected_ids or str(case["skill_id"]) in selected_ids]
    missing_ids = sorted(set(selected_ids).difference(str(case["skill_id"]) for case in BUILTIN_SKILL_CASES))
    if not cases:
        raise ValueError("At least one known skill pattern must be selected.")

    root = Path(artifact_root).expanduser().resolve() if artifact_root else _REPO_ROOT / "PRIVATE" / "skill-first-orchestration" / "evaluation"
    resolved_run_id = slugify(run_id or f"skill-evaluation-{resolved_mode}-{now_iso()}", default="skill-evaluation")
    run_dir = root / resolved_run_id
    patterns_dir = run_dir / "patterns"
    validation_dir = run_dir / "validations"
    workspace_dir = run_dir / "workspace"
    for path in (run_dir, patterns_dir, validation_dir, workspace_dir):
        path.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": SKILL_ORCHESTRATION_EVALUATION_MANIFEST_SCHEMA_VERSION,
        "mode": resolved_mode,
        "run_id": resolved_run_id,
        "skill_ids": [str(case["skill_id"]) for case in cases],
        "fixture_runs": bool(fixture_runs),
        "missing_requested_skill_ids": missing_ids,
        "created_at": now_iso(),
    }
    manifest_path = validation_dir / "manifest.json"
    write_json(manifest_path, manifest)

    projects = ProjectService(
        store_path=workspace_dir / "projects.json",
        session_path=workspace_dir / "current_project.json",
    )
    projects.create_project(
        "Skill orchestration evaluation",
        workspace_dir / "skill-evaluation.abproj",
        workspace_root=workspace_dir,
        entry_mode="new",
    )
    tasks = TaskService(projects)
    tasks.create_task("Skill orchestration evaluation task")
    service = _build_mcp_service(projects=projects, tasks=tasks)
    broker = McpBrokerService(project_service=projects, orchestration_service=service)

    pattern_results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        result = _evaluate_case(
            case=case,
            index=index,
            mode=resolved_mode,
            fixture_runs=fixture_runs,
            broker=broker,
            pattern_dir=patterns_dir,
        )
        pattern_results.append(result)

    promotion_blockers: list[str] = []
    if missing_ids:
        promotion_blockers.extend(f"requested_skill_not_in_builtin_set:{item}" for item in missing_ids)
    for result in pattern_results:
        if not bool(result.get("promotion_eligible")):
            for blocker in list(result.get("promotion_blockers") or []):
                promotion_blockers.append(f"{result.get('skill_id')}:{blocker}")
    promotion_blockers = _unique(promotion_blockers)
    safety_failures = [
        f"{result.get('skill_id')}:{blocker}"
        for result in pattern_results
        if str(result.get("status") or "") != "pass"
        for blocker in list(result.get("blockers") or [])
    ]
    status = "pass" if not safety_failures else "fail"
    if resolved_mode == "promotion" and promotion_blockers:
        status = "fail"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "report.md"
    summary = {
        "schema_version": SKILL_ORCHESTRATION_EVALUATION_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": manifest["created_at"],
        "mode": resolved_mode,
        "status": status,
        "promotion_ready": not promotion_blockers,
        "promotion_blockers": promotion_blockers,
        "safety_failures": safety_failures,
        "pattern_count": len(pattern_results),
        "patterns": pattern_results,
        "evaluation_policy": {
            "provider_calls": 0,
            "network_discovery_calls": 0,
            "mcp_transport": "loopback",
            "fixture_runs": bool(fixture_runs),
            "candidate_status_is_not_productization": True,
            "fail_closed_on": [
                "manifest_or_graph_blocker",
                "communication_isolation_blocker",
                "runtime_guardrail_blocker",
                "mcp_loopback_policy_missing",
                "provider_a2a_truthfulness_blocker",
                "fixture_execution_failure",
                "promotion_mode_non_productized_skill",
            ],
        },
        "artifact_paths": {
            "run_dir": str(run_dir),
            "workspace_dir": str(workspace_dir),
            "manifest_json": str(manifest_path),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
            "patterns_dir": str(patterns_dir),
        },
    }
    write_json(summary_path, redact_sensitive(summary))
    report_path.write_text(render_skill_orchestration_evaluation_report(summary), encoding="utf-8", newline="\n")
    return redact_sensitive(summary)


def render_skill_orchestration_evaluation_report(summary: dict[str, Any]) -> str:
    lines = [
        "# AstraBridge Skill Orchestration Evaluation Gate",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Mode: `{summary.get('mode')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Promotion ready: `{summary.get('promotion_ready')}`",
        f"- Pattern count: `{summary.get('pattern_count')}`",
        "",
        "## Pattern Results",
        "",
    ]
    for pattern in list(summary.get("patterns") or []):
        lines.append(
            f"- `{pattern.get('skill_id')}` status=`{pattern.get('status')}` "
            f"promotion_eligible=`{pattern.get('promotion_eligible')}` "
            f"fixture=`{dict(pattern.get('fixture') or {}).get('status')}`"
        )
        for blocker in list(pattern.get("blockers") or [])[:12]:
            lines.append(f"  - blocker: `{blocker}`")
        for blocker in list(pattern.get("promotion_blockers") or [])[:12]:
            lines.append(f"  - promotion blocker: `{blocker}`")
    if summary.get("promotion_blockers"):
        lines.extend(["", "## Promotion Blockers", ""])
        lines.extend(f"- `{item}`" for item in list(summary.get("promotion_blockers") or [])[:64])
    return "\n".join(lines).rstrip() + "\n"


def _build_mcp_service(*, projects: ProjectService, tasks: TaskService) -> Any:
    # Import locally to keep this module's pure resolution imports cheap for
    # callers that only need the manifest/evaluation helpers.
    from .skill_orchestration_mcp_service import SkillOrchestrationMcpService

    return SkillOrchestrationMcpService(project_service=projects, task_service=tasks)


def _evaluate_case(
    *,
    case: dict[str, Any],
    index: int,
    mode: str,
    fixture_runs: bool,
    broker: McpBrokerService,
    pattern_dir: Path,
) -> dict[str, Any]:
    skill_id = str(case.get("skill_id") or "").strip()
    parameters = deepcopy(dict(case.get("parameters") or {}))
    result: dict[str, Any] = {
        "skill_id": skill_id,
        "status": "fail",
        "promotion_eligible": False,
        "promotion_blockers": [],
        "warnings": [],
        "blockers": [],
        "checks": {},
        "fixture": {"status": "skipped", "outcome": "not_started"},
    }
    try:
        manifest = load_skill_orchestration_manifest(skill_id)
        result["skill_status"] = str(manifest.get("status") or "candidate")
        result["template_id"] = str(dict(manifest.get("extensions") or {}).get("template_id") or "")
        result["manifest_digest"] = _digest_ref(manifest)
        result["checks"]["manifest"] = _check("pass", "manifest loaded and hashed")
        if SECRET_RE.search(json.dumps(manifest, ensure_ascii=False)):
            result["checks"]["manifest_content_scan"] = _check("fail", "manifest contains secret-like content")
            result["blockers"].append("manifest_secret_like_content")
        else:
            result["checks"]["manifest_content_scan"] = _check("pass", "manifest has no secret-like values")

        resolution = resolve_skill_to_graph(skill_id, parameters)
        result["graph_digest"] = str(resolution.get("graph_digest") or "")
        result["warnings"].extend(str(item) for item in list(resolution.get("warnings") or []) if str(item or "").strip())
        result["blockers"].extend(str(item) for item in list(resolution.get("blockers") or []) if str(item or "").strip())
        if result["blockers"]:
            result["checks"]["resolution"] = _check("fail", "skill resolution has blockers")
            return _finalize_case(result=result, mode=mode, pattern_dir=pattern_dir, index=index)
        result["checks"]["resolution"] = _check("pass", "skill resolves to a canonical graph")
        graph = dict(resolution.get("canonical_graph") or {})
        compiled = compile_agent_orchestration_graph(graph)
        result["checks"]["compile"] = _check("pass", "canonical graph compiles")
        isolation = validate_typed_communication_isolation(graph, compiled)
        result["checks"]["communication_isolation"] = _decision_check(isolation, "typed communication isolation")
        if str(isolation.get("status") or "") != "pass":
            result["blockers"].extend(str(item) for item in list(isolation.get("blockers") or []))

        budget = _evaluation_budget(manifest, graph)
        guardrails = evaluate_runtime_guardrails(
            graph=graph,
            compiled_plan=compiled,
            run_budget=budget,
            dispatch_limits=None,
            parent_context={},
            mode="fixture_run",
            require_complete_budget=True,
        )
        result["checks"]["runtime_guardrails"] = _decision_check(guardrails, "runtime guardrails")
        if str(guardrails.get("status") or "") != "pass":
            result["blockers"].extend(str(item) for item in list(guardrails.get("blockers") or []))

        policies = dict(manifest.get("policies") or {})
        mcp_policy = dict(policies.get("mcp") or {})
        if mcp_policy.get("loopback_allowed") is True:
            result["checks"]["mcp"] = _check("pass", "MCP loopback is declared")
        else:
            result["checks"]["mcp"] = _check("fail", "MCP loopback is not declared")
            result["blockers"].append("mcp_loopback_policy_missing")

        binding = deepcopy(dict(resolution.get("provider_a2a_binding") or {}))
        binding_status = str(binding.get("status") or "").strip()
        binding_provenance = dict(binding.get("provenance") or {})
        binding_ok = binding_status in {"qualified", "downgraded", "deferred"} and all(
            int(binding_provenance.get(field) or 0) == 0
            for field in ("provider_calls", "mcp_calls", "agent_invocations", "network_discovery_calls")
        )
        if str(result.get("skill_status") or "candidate") in {"provider-qualified", "external-a2a-qualified"}:
            binding_ok = binding_ok and binding_status == "qualified"
        result["checks"]["provider_a2a"] = _check(
            "pass" if binding_ok else "fail",
            f"provider/A2A binding status={binding_status or 'missing'}",
            details={"status": binding_status, "binding_digest": binding.get("binding_digest")},
        )
        if not binding_ok:
            result["blockers"].append("provider_a2a_truthfulness_or_discovery_violation")
        result["provider_a2a_status"] = binding_status

        if fixture_runs and not result["blockers"]:
            result["fixture"] = _run_fixture_case(
                broker=broker,
                skill_id=skill_id,
                parameters=parameters,
                budget=budget,
                operation_prefix=f"skill-eval-{index}",
            )
            if str(result["fixture"].get("status") or "") != "pass":
                result["blockers"].append(str(result["fixture"].get("message") or "fixture_execution_failed"))
        elif not fixture_runs:
            result["fixture"] = {"status": "skipped", "outcome": "disabled_for_test"}
        result["status"] = "pass" if not result["blockers"] else "fail"
        result["promotion_blockers"].extend(_promotion_blockers(result))
        result["promotion_eligible"] = not result["promotion_blockers"] and result["status"] == "pass"
        return _finalize_case(result=result, mode=mode, pattern_dir=pattern_dir, index=index)
    except Exception as exc:  # noqa: BLE001
        result["blockers"].append(f"evaluation_exception:{type(exc).__name__}")
        result["warnings"].append(str(redact_sensitive(str(exc)))[:400])
        result["status"] = "fail"
        result["promotion_blockers"].extend(_promotion_blockers(result))
        return _finalize_case(result=result, mode=mode, pattern_dir=pattern_dir, index=index)


def _run_fixture_case(
    *,
    broker: McpBrokerService,
    skill_id: str,
    parameters: dict[str, Any],
    budget: dict[str, Any],
    operation_prefix: str,
) -> dict[str, Any]:
    base = {
        "direction": "request",
        "schema_version": "astrabridge-skill-backed-orchestration-mcp-v1",
        "skill_ref": {"skill_id": skill_id, "version": "1.0.0"},
        "parameters": parameters,
    }

    def call(tool: str, request: dict[str, Any], operation_id: str) -> dict[str, Any]:
        payload = broker.invoke_tool(
            "astrabridge-orchestration",
            tool,
            request,
            caller="skill-evaluation-gate",
            operation_id=operation_id,
        )
        return dict(payload.get("result") or {})

    proposed = call(
        "astrabridge_orchestration_propose",
        {**base, "operation": "propose", "request_id": f"{operation_prefix}-propose"},
        f"{operation_prefix}-propose",
    )
    if str(proposed.get("status") or "") != "completed":
        return _fixture_blocked_result(proposed, outcome="propose_blocked", fallback="mcp_propose_blocked")
    resolution_ref = dict(dict(proposed.get("result") or {}).get("resolution_ref") or {})
    dry_run = call(
        "astrabridge_orchestration_dry_run",
        {
            "direction": "request",
            "schema_version": "astrabridge-skill-backed-orchestration-mcp-v1",
            "operation": "dry_run",
            "request_id": f"{operation_prefix}-dry-run",
            "resolution_ref": resolution_ref,
            "budget": budget,
            "include_compiled_plan": False,
        },
        f"{operation_prefix}-dry-run",
    )
    if str(dry_run.get("status") or "") != "completed":
        return _fixture_blocked_result(dry_run, outcome="dry_run_blocked", fallback="mcp_dry_run_blocked")
    receipt = dict(dict(dry_run.get("result") or {}).get("dry_run_receipt") or {})
    launch = call(
        "astrabridge_orchestration_launch",
        {
            "direction": "request",
            "schema_version": "astrabridge-skill-backed-orchestration-mcp-v1",
            "operation": "launch",
            "request_id": f"{operation_prefix}-launch",
            "resolution_ref": resolution_ref,
            "budget": budget,
            "approval": {
                "mode": "manual",
                "approval_ref": f"{operation_prefix}-approval",
                "risky_effects_require_approval": ["provider_call", "file_write"],
            },
            "idempotency_key": f"{operation_prefix}-idempotency",
            "dry_run_receipt": receipt,
            "mode": "fixture",
            "input": {},
        },
        f"{operation_prefix}-launch",
    )
    if str(launch.get("status") or "") != "accepted":
        return _fixture_blocked_result(launch, outcome="launch_blocked", fallback="mcp_fixture_launch_blocked")
    run_id = str(dict(launch.get("result") or {}).get("run_id") or "").strip()
    if not run_id:
        return {"status": "fail", "outcome": "run_id_missing", "message": "mcp_fixture_run_id_missing"}
    inspected = call(
        "astrabridge_orchestration_inspect",
        {
            "direction": "request",
            "schema_version": "astrabridge-skill-backed-orchestration-mcp-v1",
            "operation": "inspect",
            "request_id": f"{operation_prefix}-inspect",
            "run_id": run_id,
            "projection": "summary",
        },
        f"{operation_prefix}-inspect",
    )
    inspected_run = dict(dict(inspected.get("result") or {}).get("run") or {})
    run_status = str(inspected_run.get("status") or "").strip()
    if run_status == "completed":
        return {"status": "pass", "outcome": "completed", "run_id": run_id, "message": "fixture completed"}
    if run_status == "paused_for_review":
        # Provider update smoke intentionally ends at its explicit manual gate;
        # the pending approval is evidence, not an implicit success.
        return {"status": "pass", "outcome": "pending_review", "run_id": run_id, "message": "fixture reached explicit review gate"}
    return {"status": "fail", "outcome": run_status or "unknown", "run_id": run_id, "message": f"fixture_run_status:{run_status or 'unknown'}"}


def _fixture_blocked_result(payload: dict[str, Any], *, outcome: str, fallback: str) -> dict[str, Any]:
    """Keep bounded MCP error evidence in the fixture report without secrets."""

    error = dict(payload.get("error") or {})
    code = str(error.get("code") or payload.get("code") or "").strip()
    detail = str(error.get("message") or error.get("detail") or payload.get("message") or "").strip()
    message = code or fallback
    result: dict[str, Any] = {"status": "fail", "outcome": outcome, "message": message}
    if detail:
        result["detail"] = str(redact_sensitive(detail))[:400]
    return result


def _evaluation_budget(manifest: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    policies = dict(manifest.get("policies") or {})
    declared = dict(policies.get("budget") or {})
    graph_policy = dict(graph.get("graph_policy") or {})
    routes = _graph_routes(graph)
    provider_limits = [dict(item) for item in list(declared.get("provider_concurrency") or []) if isinstance(item, dict)]
    provider_keys = {str(item.get("provider_id") or "").strip() for item in provider_limits}
    for provider_id, _ in routes:
        if provider_id and provider_id not in provider_keys:
            provider_limits.append({"provider_id": provider_id, "max_active_agents": 1})
            provider_keys.add(provider_id)
    model_limits = [dict(item) for item in list(declared.get("model_concurrency") or []) if isinstance(item, dict)]
    model_keys = {f"{str(item.get('provider_id') or '').strip()}/{str(item.get('model_id') or '').strip()}" for item in model_limits}
    for provider_id, model_id in routes:
        key = f"{provider_id}/{model_id}"
        if provider_id and model_id and key not in model_keys:
            model_limits.append({"provider_id": provider_id, "model_id": model_id, "max_active_agents": 1})
            model_keys.add(key)
    return {
        "max_depth": 2 if int(graph_policy.get("max_depth") or 2) <= 2 else int(graph_policy.get("max_depth") or 2),
        "max_total_agents": max(1, int(declared.get("max_total_agents") or len(routes) or 1)),
        "max_parallel_agents": max(1, int(declared.get("max_parallel_agents") or 1)),
        "max_total_tokens": max(1, int(declared.get("max_total_tokens") or 1)),
        "max_provider_calls": max(1, int(declared.get("max_provider_calls") or max(1, len(routes)))),
        "max_retries": max(0, int(declared.get("max_retries") or 0)),
        "provider_concurrency": provider_limits,
        "model_concurrency": model_limits,
        "allow_nested_subagents": False,
        "allow_direct_teammate_messages": False,
    }


def _graph_routes(graph: dict[str, Any]) -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for node in list(graph.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        routing = dict(node.get("routing") or {})
        provider_id = str(node.get("provider_id") or routing.get("provider_id") or "").strip()
        model_id = str(node.get("model_id") or routing.get("model_id") or "").strip()
        if provider_id or model_id:
            routes.append((provider_id, model_id))
    return sorted(set(routes))


def _promotion_blockers(result: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if str(result.get("skill_status") or "candidate") not in _PRODUCTIZED_STATUSES:
        blockers.append(f"skill_status_not_productized:{result.get('skill_status') or 'unknown'}")
    fixture = dict(result.get("fixture") or {})
    if str(fixture.get("outcome") or "") != "completed":
        blockers.append(f"fixture_not_completed:{fixture.get('outcome') or 'unknown'}")
    if str(result.get("skill_status") or "") in {"provider-qualified", "external-a2a-qualified"} and str(result.get("provider_a2a_status") or "") != "qualified":
        blockers.append("provider_a2a_not_qualified")
    if list(result.get("blockers") or []):
        blockers.append("safety_checks_have_blockers")
    return _unique(blockers)


def _finalize_case(*, result: dict[str, Any], mode: str, pattern_dir: Path, index: int) -> dict[str, Any]:
    result["promotion_blockers"] = _unique(
        [*list(result.get("promotion_blockers") or []), *_promotion_blockers(result)]
    )
    result["promotion_eligible"] = not result["promotion_blockers"] and str(result.get("status") or "") == "pass"
    if mode == "promotion":
        result["status"] = "pass" if result.get("status") == "pass" and result.get("promotion_eligible") else "fail"
    result["warnings"] = _unique(str(item) for item in list(result.get("warnings") or []) if str(item or "").strip())
    result["blockers"] = _unique(str(item) for item in list(result.get("blockers") or []) if str(item or "").strip())
    result["promotion_blockers"] = _unique(str(item) for item in list(result.get("promotion_blockers") or []) if str(item or "").strip())
    result["checks"] = redact_sensitive(result.get("checks") or {})
    result["fixture"] = redact_sensitive(result.get("fixture") or {})
    path = pattern_dir / f"{index:02d}-{slugify(str(result.get('skill_id') or 'skill'), default='skill')}.json"
    write_json(path, redact_sensitive(result))
    result["artifact_path"] = str(path)
    return redact_sensitive(result)


def _check(status: str, message: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": str(status), "message": str(redact_sensitive(message))[:400]}
    if details:
        payload["details"] = redact_sensitive(details)
    return payload


def _decision_check(value: dict[str, Any], label: str) -> dict[str, Any]:
    status = "pass" if str(value.get("status") or "") == "pass" else "fail"
    return _check(
        status,
        f"{label}: {status}",
        details={
            "decision_digest": value.get("decision_digest"),
            "blocker_count": len(list(value.get("blockers") or [])),
            "warning_count": len(list(value.get("warnings") or [])),
        },
    )


def _digest_ref(value: Any) -> str:
    import hashlib

    payload = json.dumps(redact_sensitive(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            result.append(clean)
            seen.add(clean)
    return result


__all__ = [
    "BUILTIN_SKILL_CASES",
    "SKILL_ORCHESTRATION_EVALUATION_MANIFEST_SCHEMA_VERSION",
    "SKILL_ORCHESTRATION_EVALUATION_SCHEMA_VERSION",
    "render_skill_orchestration_evaluation_report",
    "run_skill_orchestration_evaluation_gate",
]
