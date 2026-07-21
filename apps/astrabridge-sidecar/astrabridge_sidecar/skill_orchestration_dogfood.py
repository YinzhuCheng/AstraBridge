"""Provider-free dogfood runner for the initial skill-backed pattern set.

Dogfood is intentionally narrower than promotion: it uses realistic AstraBridge
work goals and repository references, but executes through the canonical MCP
loopback fixture owner so it never spends provider credits or performs external
network discovery.  Every request/response, resolution, run inspection, and
finding is persisted as redacted evidence.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .common import now_iso, slugify, write_json
from .mcp_broker_service import McpBrokerService
from .project_service import ProjectService
from .security import redact_sensitive
from .skill_orchestration_evaluation_gate import _evaluation_budget
from .skill_orchestration_mcp_service import (
    SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
    SkillOrchestrationMcpService,
)
from .skill_orchestration_validation import load_skill_orchestration_manifest, resolve_skill_to_graph
from .task_service import TaskService


SKILL_ORCHESTRATION_DOGFOOD_SCHEMA_VERSION = "astrabridge-skill-orchestration-dogfood-v1"

# These are bounded internal workflows, not generic synthetic prompts.  They
# point at current AstraBridge contracts, tests, and artifact paths while
# remaining provider-free when executed with mode=fixture.
DOGFOOD_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "skill-boundary-synthesis",
        "skill_id": "astrabridge.supervisor-worker-synthesizer",
        "workflow_family": "supervisor_worker_synthesizer",
        "goal": "Synthesize the current skill-first product boundary and the next operator action for AstraBridge.",
        "parameters": {
            "task_goal": "Review the current skill-first multi-provider orchestration boundary and produce one bounded operator summary for the next implementation round.",
            "constraints": [
                "Read-only planning evidence; do not call providers or mutate external systems.",
                "Keep graph depth at the shallow default and preserve MCP/A2A ownership boundaries.",
            ],
            "worker_scope": "Inspect the active skill-first plan, Step 12 evaluation evidence, and canonical MCP contract references.",
        },
        "observed_paths": [
            "PLAN/ASTRABRIDGE_SKILL_FIRST_MULTI_PROVIDER_AGENT_ORCHESTRATION_EXECUTION_PLAN.md",
            "PRIVATE/skill-first-orchestration/step12-evaluation/20260721/evaluation-gate-report.md",
        ],
        "follow_up_refs": [
            "PLAN/ASTRABRIDGE_SKILL_FIRST_ORCHESTRATION_BOUNDARY_CONTRACT.md",
            "apps/astrabridge-sidecar/astrabridge_sidecar/skill_orchestration_mcp_service.py",
        ],
    },
    {
        "case_id": "mcp-contract-review-fix",
        "skill_id": "astrabridge.review-fix-verify",
        "workflow_family": "code_fix_test_review",
        "goal": "Review the Step 12 MCP evaluation path and identify a bounded contract or test fix without widening runtime scope.",
        "parameters": {
            "task_goal": "Review the Step 12 skill orchestration evaluation path for one bounded contract improvement, then verify the relevant regression tests.",
            "target_files": [
                "apps/astrabridge-sidecar/astrabridge_sidecar/skill_orchestration_evaluation_gate.py",
                "apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py",
            ],
            "test_command": "python -m unittest apps/astrabridge-sidecar/tests/test_skill_orchestration_evaluation_gate.py",
            "review_criteria": [
                "No direct provider or network path is introduced.",
                "Typed artifact handoffs remain protocol-valid and redacted.",
                "Any follow-up remains bounded to the canonical owner.",
            ],
        },
        "observed_paths": [
            "apps/astrabridge-sidecar/astrabridge_sidecar/skill_orchestration_evaluation_gate.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py",
            "apps/astrabridge-sidecar/tests/test_skill_orchestration_evaluation_gate.py",
        ],
        "follow_up_refs": [
            "apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py::_fixture_typed_output_values",
            "apps/astrabridge-sidecar/tests/test_skill_orchestration_evaluation_gate.py",
        ],
    },
    {
        "case_id": "contract-source-fanout",
        "skill_id": "astrabridge.fanout-research-synthesis",
        "workflow_family": "fanout_fanin_research",
        "goal": "Compare authoritative MCP/A2A contract evidence and synthesize a bounded compatibility note.",
        "parameters": {
            "research_goal": "Compare AstraBridge's canonical MCP surface and external A2A boundary against authoritative protocol references, then synthesize only actionable compatibility findings.",
            "branch_scopes": [
                "MCP tool/resource envelope and loopback policy",
                "A2A peer card, trust, and cross-provider handoff boundary",
            ],
            "source_domains": ["modelcontextprotocol.io", "a2a-protocol.org"],
            "query_budget": 4,
        },
        "observed_paths": [
            "PLAN/ASTRABRIDGE_SKILL_BACKED_ORCHESTRATION_MCP_SURFACE_CONTRACT.md",
            "PLAN/ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md",
            "apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py",
        ],
        "follow_up_refs": [
            "apps/astrabridge-sidecar/astrabridge_sidecar/communication_isolation.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_conformance.py",
        ],
    },
    {
        "case_id": "provider-route-qualification",
        "skill_id": "astrabridge.provider-update-smoke",
        "workflow_family": "provider_update_smoke_gate",
        "goal": "Qualify current provider/model route metadata and preserve a manual promotion decision.",
        "parameters": {
            "update_goal": "Review current qwen and glm route metadata used by skill-backed orchestration, verify conservative capability claims, and prepare a promotion decision without external writeback.",
            "provider_ids": ["qwen", "glm"],
            "model_ids": ["qwen3-coder-plus", "glm-5.2"],
            "smoke_cases": [
                "catalog_consistency",
                "route_downgrade_truthfulness",
                "mcp_tool_policy",
            ],
            "promotion_owner": "astrabridge-dogfood-owner",
        },
        "observed_paths": [
            "apps/astrabridge-sidecar/astrabridge_sidecar/skill_provider_a2a_binding.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/promotion_gate.py",
        ],
        "follow_up_refs": [
            "apps/astrabridge-sidecar/astrabridge_sidecar/skill_provider_a2a_binding.py",
            "PRIVATE/skill-first-orchestration/step12-evaluation/20260721/promotion-evaluation-r1/summary.json",
        ],
    },
    {
        "case_id": "mcp-vision-fallback-contract",
        "skill_id": "astrabridge.multimodal-capability-adapter",
        "workflow_family": "multimodal_capability_adapter",
        "goal": "Validate the MCP-only vision capability adapter and its explicit fallback artifact contract.",
        "parameters": {
            "task_goal": "Validate one image-analysis request through the MCP-only capability adapter, preserving the selected route, adapted contract, and fallback evidence.",
            "capability_id": "vision.analyze",
            "input_artifacts": [{"kind": "image", "ref": "workspace://PRIVATE/skill-first-orchestration/step13-dogfood/20260721/inputs/vision-fixture.json"}],
            "desired_output": "structured result with explicit fallback status",
            "allowed_fallbacks": ["text-only-analysis", "manual-review"],
        },
        "observed_paths": [
            "apps/astrabridge-sidecar/astrabridge_sidecar/multimodal_result_envelope.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/mcp_node_policy.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/skill_orchestration_mcp_service.py",
        ],
        "follow_up_refs": [
            "apps/astrabridge-sidecar/astrabridge_sidecar/multimodal_result_envelope.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/skill_provider_a2a_binding.py",
        ],
    },
)


def run_skill_orchestration_dogfood(
    *,
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
    case_ids: Iterable[str] | None = None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run bounded realistic workflows through the canonical MCP fixture path."""

    root = Path(artifact_root).expanduser().resolve() if artifact_root else Path(__file__).resolve().parents[3] / "PRIVATE" / "skill-first-orchestration" / "step13-dogfood"
    resolved_run_id = slugify(run_id or f"dogfood-{now_iso()}", default="dogfood")
    run_dir = root / resolved_run_id
    cases_dir = run_dir / "cases"
    workspace_dir = run_dir / "workspace"
    inputs_dir = workspace_dir / "PRIVATE" / "skill-first-orchestration" / "step13-dogfood" / "20260721" / "inputs"
    for path in (run_dir, cases_dir, workspace_dir, inputs_dir):
        path.mkdir(parents=True, exist_ok=True)

    selected = {str(item).strip() for item in list(case_ids or []) if str(item or "").strip()}
    cases = [deepcopy(case) for case in DOGFOOD_CASES if not selected or str(case["case_id"]) in selected]
    missing = sorted(selected.difference(str(case["case_id"]) for case in DOGFOOD_CASES))
    if not cases:
        raise ValueError("At least one known dogfood case must be selected.")

    repo = Path(repo_root).expanduser().resolve() if repo_root else Path(__file__).resolve().parents[3]
    input_fixture = inputs_dir / "vision-fixture.json"
    write_json(
        input_fixture,
        {
            "schema_version": "astrabridge-dogfood-input-fixture-v1",
            "kind": "image",
            "description": "Redacted provider-free image placeholder used only to exercise the multimodal artifact contract.",
            "source": "dogfood",
            "created_at": now_iso(),
        },
    )

    projects = ProjectService(
        store_path=workspace_dir / "projects.json",
        session_path=workspace_dir / "current_project.json",
    )
    projects.create_project(
        "Skill orchestration dogfood",
        workspace_dir / "skill-dogfood.abproj",
        workspace_root=workspace_dir,
        entry_mode="new",
    )
    tasks = TaskService(projects)
    tasks.create_task("Skill orchestration dogfood task")
    service = SkillOrchestrationMcpService(project_service=projects, task_service=tasks)
    broker = McpBrokerService(project_service=projects, orchestration_service=service)

    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        case_dir = cases_dir / f"{index:02d}-{slugify(str(case['case_id']), default='case')}"
        case_dir.mkdir(parents=True, exist_ok=True)
        result = _run_case(
            case=case,
            case_dir=case_dir,
            broker=broker,
            repo_root=repo,
            workspace_root=workspace_dir,
            index=index,
        )
        write_json(case_dir / "case-summary.json", result)
        case_results.append(result)

    failures = [
        f"{item.get('case_id')}:{blocker}"
        for item in case_results
        if str(item.get("operational_status") or "") == "fail"
        for blocker in list(item.get("product_blockers") or [])
    ]
    policy_gates = [
        f"{item.get('case_id')}:{gate}"
        for item in case_results
        for gate in list(item.get("policy_gates") or [])
    ]
    polish_debt = [
        f"{item.get('case_id')}:{finding}"
        for item in case_results
        for finding in list(item.get("polish_debt") or [])
    ]
    summary = {
        "schema_version": SKILL_ORCHESTRATION_DOGFOOD_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": now_iso(),
        "status": "pass" if not failures else "fail",
        "promotion_ready": False,
        "case_count": len(case_results),
        "cases": case_results,
        "product_blockers": _unique(failures),
        "policy_gates": _unique(policy_gates),
        "polish_debt": _unique(polish_debt),
        "execution_policy": {
            "transport": "loopback",
            "mode": "fixture",
            "provider_calls": 0,
            "network_discovery_calls": 0,
            "external_writeback": False,
            "nested_subagents": False,
            "direct_teammate_messages": False,
            "realistic_repo_references_checked": True,
        },
        "artifact_paths": {
            "run_dir": str(run_dir),
            "cases_dir": str(cases_dir),
            "workspace_dir": str(workspace_dir),
            "summary_json": str(run_dir / "summary.json"),
            "report_md": str(run_dir / "report.md"),
            "input_fixture": str(input_fixture),
        },
        "missing_requested_case_ids": missing,
    }
    write_json(run_dir / "summary.json", redact_sensitive(summary))
    (run_dir / "report.md").write_text(render_skill_orchestration_dogfood_report(summary), encoding="utf-8", newline="\n")
    return redact_sensitive(summary)


def _run_case(
    *,
    case: dict[str, Any],
    case_dir: Path,
    broker: McpBrokerService,
    repo_root: Path,
    workspace_root: Path,
    index: int,
) -> dict[str, Any]:
    skill_id = str(case.get("skill_id") or "").strip()
    case_id = str(case.get("case_id") or "").strip()
    parameters = deepcopy(dict(case.get("parameters") or {}))
    result: dict[str, Any] = {
        "case_id": case_id,
        "skill_id": skill_id,
        "workflow_family": str(case.get("workflow_family") or "").strip(),
        "operational_status": "fail",
        "fixture_outcome": "not_started",
        "product_blockers": [],
        "policy_gates": [],
        "polish_debt": [],
        "follow_up_refs": [str(item) for item in list(case.get("follow_up_refs") or []) if str(item or "").strip()],
        "observed_inputs": [],
        "mcp_operations": [],
        "warnings": [],
    }
    for relative in list(case.get("observed_paths") or []):
        clean = str(relative or "").strip()
        if not clean:
            continue
        path = repo_root / clean
        observed: dict[str, Any] = {"path": clean, "exists": path.exists(), "kind": "repo_reference"}
        if path.is_file():
            raw = path.read_bytes()
            observed["size_bytes"] = len(raw)
            observed["sha256"] = hashlib.sha256(raw).hexdigest()
            if path.suffix.lower() in {".md", ".py", ".json", ".yaml", ".yml", ".toml"}:
                observed["line_count"] = raw.count(b"\n") + (1 if raw and not raw.endswith(b"\n") else 0)
        result["observed_inputs"].append(observed)
        if not path.exists():
            result["product_blockers"].append(f"observed_repo_path_missing:{clean}")

    try:
        manifest = load_skill_orchestration_manifest(skill_id)
        result["skill_status"] = str(manifest.get("status") or "candidate")
        if result["skill_status"] not in {"productized", "provider-qualified", "external-a2a-qualified"}:
            result["policy_gates"].append(f"skill_lifecycle_candidate:{result['skill_status']}")
        resolution = resolve_skill_to_graph(skill_id, parameters)
        result["resolution_digest"] = str(resolution.get("graph_digest") or "")
        result["warnings"].extend(_diagnostic_messages(resolution.get("warnings")))
        result["product_blockers"].extend(str(item) for item in list(resolution.get("blockers") or []) if str(item or "").strip())
        if result["product_blockers"]:
            result["fixture_outcome"] = "resolution_blocked"
            return _finalize_case(result, case_dir)

        budget = _evaluation_budget(manifest, dict(resolution.get("canonical_graph") or {}))
        base = {
            "direction": "request",
            "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
            "skill_ref": {"skill_id": skill_id, "version": "1.0.0"},
            "parameters": parameters,
        }

        def call(tool: str, operation: str, request: dict[str, Any]) -> dict[str, Any]:
            operation_id = f"dogfood-{index}-{case_id}-{operation}"
            payload = broker.invoke_tool(
                "astrabridge-orchestration",
                tool,
                request,
                caller="skill-orchestration-dogfood",
                operation_id=operation_id,
            )
            response = dict(payload.get("result") or {})
            write_json(
                case_dir / "mcp" / f"{operation}.json",
                redact_sensitive({"mcp": payload.get("mcp"), "result": response}),
            )
            result["mcp_operations"].append({"operation": operation, "status": response.get("status"), "artifact": str(case_dir / "mcp" / f"{operation}.json")})
            result["warnings"].extend(_diagnostic_messages(response.get("warnings")))
            return response

        proposed = call(
            "astrabridge_orchestration_propose",
            "propose",
            {**base, "operation": "propose", "request_id": f"{case_id}-propose"},
        )
        if str(proposed.get("status") or "") != "completed":
            result["product_blockers"].append(f"mcp_propose_status:{proposed.get('status') or 'unknown'}")
            return _finalize_case(result, case_dir)
        resolution_ref = dict(dict(proposed.get("result") or {}).get("resolution_ref") or {})
        result["resolution_ref"] = resolution_ref

        validated = call(
            "astrabridge_orchestration_validate",
            "validate",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "validate",
                "request_id": f"{case_id}-validate",
                "subject": {"resolution_ref": resolution_ref},
            },
        )
        if str(validated.get("status") or "") != "completed":
            result["product_blockers"].append(f"mcp_validate_status:{validated.get('status') or 'unknown'}")
            return _finalize_case(result, case_dir)

        dry_run = call(
            "astrabridge_orchestration_dry_run",
            "dry-run",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "dry_run",
                "request_id": f"{case_id}-dry-run",
                "resolution_ref": resolution_ref,
                "budget": budget,
                "include_compiled_plan": False,
            },
        )
        if str(dry_run.get("status") or "") != "completed":
            result["product_blockers"].append(f"mcp_dry_run_status:{dry_run.get('status') or 'unknown'}")
            return _finalize_case(result, case_dir)
        receipt = dict(dict(dry_run.get("result") or {}).get("dry_run_receipt") or {})

        launch = call(
            "astrabridge_orchestration_launch",
            "launch",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "launch",
                "request_id": f"{case_id}-launch",
                "resolution_ref": resolution_ref,
                "budget": budget,
                "approval": {
                    "mode": "manual",
                    "approval_ref": f"{case_id}-approval",
                    "risky_effects_require_approval": ["provider_call", "file_write", "external_write"],
                },
                "idempotency_key": f"{case_id}-idempotency",
                "dry_run_receipt": receipt,
                "mode": "fixture",
                "input": {},
            },
        )
        if str(launch.get("status") or "") != "accepted":
            result["product_blockers"].append(f"mcp_launch_status:{launch.get('status') or 'unknown'}")
            result["fixture_outcome"] = "launch_blocked"
            return _finalize_case(result, case_dir)
        run_id = str(dict(launch.get("result") or {}).get("run_id") or "").strip()
        if not run_id:
            result["product_blockers"].append("mcp_launch_run_id_missing")
            result["fixture_outcome"] = "run_id_missing"
            return _finalize_case(result, case_dir)
        result["run_id"] = run_id

        inspected = call(
            "astrabridge_orchestration_inspect",
            "inspect",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "inspect",
                "request_id": f"{case_id}-inspect",
                "run_id": run_id,
                "projection": "summary",
            },
        )
        inspected_run = dict(dict(inspected.get("result") or {}).get("run") or {})
        run_status = str(inspected_run.get("status") or "").strip()
        if run_status == "completed":
            result["operational_status"] = "pass"
            result["fixture_outcome"] = "completed"
        elif run_status == "paused_for_review":
            result["operational_status"] = "pass"
            result["fixture_outcome"] = "pending_review"
            result["policy_gates"].append("manual_review_required:provider_update_gate")
        else:
            result["fixture_outcome"] = run_status or "unknown"
            result["product_blockers"].append(f"fixture_run_status:{run_status or 'unknown'}")

        if any("mcp_preset_not_available_yet" in item or "mcp_server_not_available_yet" in item for item in result["warnings"]):
            result["polish_debt"].append("declared_mcp_preset_availability_is_not_yet_productized")
        if any("model_not_in_catalog_snapshot" in item for item in result["warnings"]):
            result["polish_debt"].append("provider_model_catalog_snapshot_needs_refresh_before_qualification")
        result["polish_debt"].append("fixture_outputs_are_provider_free_placeholders_by_design")
        return _finalize_case(result, case_dir)
    except Exception as exc:  # noqa: BLE001
        result["product_blockers"].append(f"dogfood_exception:{type(exc).__name__}")
        result["diagnostic"] = str(redact_sensitive(str(exc)))[:400]
        return _finalize_case(result, case_dir)


def _finalize_case(result: dict[str, Any], case_dir: Path) -> dict[str, Any]:
    result["product_blockers"] = _unique(result.get("product_blockers") or [])
    result["policy_gates"] = _unique(result.get("policy_gates") or [])
    result["polish_debt"] = _unique(result.get("polish_debt") or [])
    result["warnings"] = _unique(result.get("warnings") or [])
    result["artifact_root"] = str(case_dir)
    return redact_sensitive(result)


def render_skill_orchestration_dogfood_report(summary: dict[str, Any]) -> str:
    lines = [
        "# AstraBridge Skill Orchestration Dogfood",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Cases: `{summary.get('case_count')}`",
        f"- Promotion ready: `{summary.get('promotion_ready')}`",
        "",
        "## Case Findings",
        "",
    ]
    for case in list(summary.get("cases") or []):
        lines.append(
            f"- `{case.get('case_id')}` family=`{case.get('workflow_family')}` "
            f"operational=`{case.get('operational_status')}` fixture=`{case.get('fixture_outcome')}`"
        )
        for item in list(case.get("product_blockers") or []):
            lines.append(f"  - product blocker: `{item}`")
        for item in list(case.get("policy_gates") or []):
            lines.append(f"  - policy gate: `{item}`")
        for item in list(case.get("polish_debt") or []):
            lines.append(f"  - polish/evidence debt: `{item}`")
        for item in list(case.get("follow_up_refs") or []):
            lines.append(f"  - follow-up owner: `{item}`")
    if summary.get("product_blockers"):
        lines.extend(["", "## Product Blockers", ""])
        lines.extend(f"- `{item}`" for item in list(summary.get("product_blockers") or []))
    if summary.get("policy_gates"):
        lines.extend(["", "## Policy Gates", ""])
        lines.extend(f"- `{item}`" for item in list(summary.get("policy_gates") or []))
    if summary.get("polish_debt"):
        lines.extend(["", "## Polish And Evidence Debt", ""])
        lines.extend(f"- `{item}`" for item in list(summary.get("polish_debt") or []))
    return "\n".join(lines).rstrip() + "\n"


def _diagnostic_messages(value: Any) -> list[str]:
    messages: list[str] = []
    for item in list(value or []):
        if isinstance(item, dict):
            code = str(item.get("code") or "").strip()
            message = str(item.get("message") or "").strip()
            text = f"{code}:{message}" if code and message else code or message
        else:
            text = str(item or "").strip()
        if text:
            messages.append(str(redact_sensitive(text))[:400])
    return messages


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
    "DOGFOOD_CASES",
    "SKILL_ORCHESTRATION_DOGFOOD_SCHEMA_VERSION",
    "render_skill_orchestration_dogfood_report",
    "run_skill_orchestration_dogfood",
]
