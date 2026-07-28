from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
from typing import Any, Callable

from ..common import now_iso, read_json, write_json
from ..security import redact_sensitive
from .artifacts import ensure_agentic_update_run_layout
from .contracts import assert_secret_free_agentic_update_payload, validate_update_proposal
from .provider_smoke import provider_smoke_report_blocks_promotion, run_agentic_update_provider_smoke
from .route_promotion import RouteSmokeRunner, route_promotion_dry_run, run_route_promotion_provider_smoke


AGENTIC_UPDATE_VALIDATION_REPORT_SCHEMA_VERSION = "astrabridge-agentic-update-validation-report-v1"
VALIDATION_MODES = {"dry_run", "fixture_only", "provider_backed"}

GATE_COMMANDS: dict[str, dict[str, Any]] = {
    "schema_validation": {
        "kind": "internal",
        "command": [".\\.venv\\Scripts\\python.exe", "-m", "unittest", "tests.test_agentic_update_contract"],
        "cwd": "apps/astrabridge-sidecar",
    },
    "metadata_tests": {
        "kind": "command",
        "command": [
            ".\\.venv\\Scripts\\python.exe",
            "-m",
            "unittest",
            "tests.test_provider_source_registry",
            "tests.test_agentic_update_parsers",
            "tests.test_agentic_update_diffing",
        ],
        "cwd": "apps/astrabridge-sidecar",
    },
    "model_catalog_tests": {
        "kind": "command",
        "command": [".\\.venv\\Scripts\\python.exe", "-m", "unittest", "tests.test_model_catalog_contract", "tests.test_provider_source_registry"],
        "cwd": "apps/astrabridge-sidecar",
    },
    "transport_tests": {
        "kind": "command",
        "command": [".\\.venv\\Scripts\\python.exe", "-m", "unittest", "tests.test_router_transport_registry", "tests.test_tool_call_compatibility"],
        "cwd": "apps/astrabridge-sidecar",
    },
    "provider_compatibility_smoke": {
        "kind": "provider_smoke",
        "command": ["POST", "/api/runtime/provider-compatibility-smoke"],
        "cwd": ".",
    },
    "capability_smoke": {
        "kind": "provider_smoke",
        "command": ["POST", "/api/runtime/capability-smoke"],
        "cwd": ".",
    },
    "execution_route_dry_run": {
        "kind": "route_dry_run",
        "command": ["internal", "execution-route-dry-run"],
        "cwd": ".",
    },
    "execution_route_provider_smoke": {
        "kind": "route_provider_smoke",
        "command": ["POST", "/api/runtime/execution-route-smoke"],
        "cwd": ".",
    },
    "execution_route_tool_contract": {
        "kind": "route_provider_smoke",
        "command": ["POST", "/api/runtime/execution-route-tool-contract-smoke"],
        "cwd": ".",
    },
    "execution_route_coding_smoke": {
        "kind": "route_provider_smoke",
        "command": ["POST", "/api/runtime/execution-route-coding-smoke"],
        "cwd": ".",
    },
    "execution_route_default_review": {
        "kind": "route_provider_smoke",
        "command": ["POST", "/api/runtime/execution-route-default-review"],
        "cwd": ".",
    },
    "codex_kernel_probe": {
        "kind": "command",
        "command": [".\\.venv\\Scripts\\python.exe", "-m", "unittest", "tests.test_codex_kernel_probe_snapshot"],
        "cwd": "apps/astrabridge-sidecar",
    },
    "codex_kernel_smoke": {
        "kind": "command",
        "command": [".\\.venv\\Scripts\\python.exe", "-m", "unittest", "tests.test_codex_kernel_smoke"],
        "cwd": "apps/astrabridge-sidecar",
    },
    "desktop_tests": {
        "kind": "command",
        "command": ["npm.cmd", "run", "test", "--", "AgenticUpdateReviewPanel.test.tsx"],
        "cwd": "apps/astrabridge-desktop",
    },
    "desktop_build": {
        "kind": "command",
        "command": ["npm.cmd", "run", "build"],
        "cwd": "apps/astrabridge-desktop",
    },
    "diff_check": {
        "kind": "command",
        "command": ["git", "diff", "--check"],
        "cwd": ".",
    },
    "secret_scan": {
        "kind": "internal",
        "command": ["rg", "-n", "-i", "api[_-]?key|authorization|bearer|secret|token|password|cookie"],
        "cwd": ".",
    },
    "rollback_plan_review": {
        "kind": "internal",
        "command": [],
        "cwd": ".",
    },
    "manual_review": {
        "kind": "manual",
        "command": [],
        "cwd": ".",
    },
}

RISK_CLASS_GATES: dict[str, list[str]] = {
    "docs_only": ["schema_validation", "diff_check", "secret_scan"],
    "metadata_only": ["schema_validation", "metadata_tests", "model_catalog_tests", "diff_check", "secret_scan"],
    "requires_provider_smoke": [
        "schema_validation",
        "metadata_tests",
        "model_catalog_tests",
        "provider_compatibility_smoke",
        "capability_smoke",
        "diff_check",
        "secret_scan",
    ],
    "requires_adapter_review": [
        "schema_validation",
        "transport_tests",
        "provider_compatibility_smoke",
        "capability_smoke",
        "desktop_tests",
        "desktop_build",
        "diff_check",
        "secret_scan",
    ],
    "requires_kernel_smoke": ["schema_validation", "codex_kernel_probe", "codex_kernel_smoke", "diff_check", "secret_scan"],
    "blocked_manual_review": ["schema_validation", "manual_review", "rollback_plan_review", "secret_scan"],
}

VALIDATION_REQUIREMENT_GATES = {
    "schema_validation": "schema_validation",
    "proposal_review": "schema_validation",
    "metadata_tests": "metadata_tests",
    "model_catalog_tests": "model_catalog_tests",
    "provider_compatibility_smoke": "provider_compatibility_smoke",
    "adapter_review": "transport_tests",
    "transport_tests": "transport_tests",
    "codex_kernel_probe": "codex_kernel_probe",
    "codex_kernel_smoke": "codex_kernel_smoke",
    "manual_review": "manual_review",
    "rollback_plan_review": "rollback_plan_review",
    "execution_route_dry_run": "execution_route_dry_run",
    "execution_route_provider_smoke": "execution_route_provider_smoke",
    "execution_route_tool_contract": "execution_route_tool_contract",
    "execution_route_coding_smoke": "execution_route_coding_smoke",
    "execution_route_default_review": "execution_route_default_review",
}

CommandRunner = Callable[[list[str], Path], dict[str, Any]]


def run_agentic_update_validation_gates(
    *,
    workspace_root: str | Path,
    run_id: str,
    proposal: dict[str, Any],
    mode: str = "fixture_only",
    allow_provider_calls: bool | None = None,
    execute_commands: bool | None = None,
    fixture_command_results: dict[str, Any] | None = None,
    command_runner: CommandRunner | None = None,
    configured_models: list[dict[str, Any]] | None = None,
    capability_route_records: dict[str, Any] | None = None,
    provider_runtime: Any | None = None,
    credential_status: dict[str, Any] | None = None,
    route_smoke_runner: RouteSmokeRunner | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    layout = ensure_agentic_update_run_layout(workspace, run_id)
    validation_mode = str(mode or "fixture_only").strip()
    if validation_mode not in VALIDATION_MODES:
        raise ValueError(f"Unsupported agentic update validation mode: {validation_mode}")
    validated_proposal = validate_update_proposal(proposal)
    contract = dict(validated_proposal.get("run_contract") or {})
    provider_authorized = bool(contract.get("allow_provider_calls")) if allow_provider_calls is None else bool(allow_provider_calls)
    should_execute_commands = validation_mode == "fixture_only" if execute_commands is None else bool(execute_commands)
    fixture_results = dict(fixture_command_results or {})
    gate_ids = _validation_gate_ids(validated_proposal)
    gates: list[dict[str, Any]] = []
    for gate_id in gate_ids:
        gates.append(
            _run_gate(
                workspace=workspace,
                proposal=validated_proposal,
                gate_id=gate_id,
                mode=validation_mode,
                provider_authorized=provider_authorized,
                execute_commands=should_execute_commands,
                fixture_results=fixture_results,
                command_runner=command_runner,
                run_id=run_id,
                configured_models=configured_models,
                capability_route_records=capability_route_records,
                provider_runtime=provider_runtime,
                credential_status=credential_status,
                route_smoke_runner=route_smoke_runner,
            )
        )
    next_fix_targets = _next_fix_targets(gates)
    status = _aggregate_status(gates, mode=validation_mode)
    report = {
        "schema_version": AGENTIC_UPDATE_VALIDATION_REPORT_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "run_id": run_id,
        "mode": validation_mode,
        "status": status,
        "promotion_blocked": bool(next_fix_targets) or status in {"fail", "blocked", "partial"},
        "risk_class": str(dict(validated_proposal.get("diff") or {}).get("risk_class") or "blocked_manual_review"),
        "allow_provider_calls": provider_authorized,
        "execute_commands": should_execute_commands,
        "gate_count": len(gates),
        "gates": gates,
        "next_fix_targets": next_fix_targets,
        "artifact_paths": {
            "validation_report": layout["files"]["validation_report"],
            "validation_markdown": layout["files"]["validation_markdown"],
        },
        "warnings": _report_warnings(gates, mode=validation_mode),
    }
    assert_secret_free_agentic_update_payload(report, label="agentic_update_validation_report")
    write_json(Path(layout["files"]["validation_report"]), report)
    Path(layout["files"]["validation_markdown"]).write_text(_render_validation_markdown(report), encoding="utf-8")
    _update_proposal_validation(Path(layout["files"]["proposal"]), report)
    return report


def _validation_gate_ids(proposal: dict[str, Any]) -> list[str]:
    diff = dict(proposal.get("diff") or {})
    risk_class = str(diff.get("risk_class") or "blocked_manual_review")
    gate_ids = list(RISK_CLASS_GATES.get(risk_class, RISK_CLASS_GATES["blocked_manual_review"]))
    for change in list(diff.get("changes") or []):
        if not isinstance(change, dict):
            continue
        change_risk = str(change.get("risk_class") or "")
        gate_ids.extend(RISK_CLASS_GATES.get(change_risk, []))
        for requirement in list(change.get("validation_requirements") or []):
            gate = VALIDATION_REQUIREMENT_GATES.get(str(requirement))
            if gate:
                gate_ids.append(gate)
    scopes = set(dict(proposal.get("run_contract") or {}).get("scope") or [])
    if scopes.intersection({"capability_routes", "plugin_skill_surface"}):
        gate_ids.extend(["desktop_tests", "desktop_build"])
    return _dedupe([gate_id for gate_id in gate_ids if gate_id in GATE_COMMANDS])


def _run_gate(
    *,
    workspace: Path,
    proposal: dict[str, Any],
    gate_id: str,
    mode: str,
    provider_authorized: bool,
    execute_commands: bool,
    fixture_results: dict[str, Any],
    command_runner: CommandRunner | None,
    run_id: str,
    configured_models: list[dict[str, Any]] | None,
    capability_route_records: dict[str, Any] | None,
    provider_runtime: Any | None,
    credential_status: dict[str, Any] | None,
    route_smoke_runner: RouteSmokeRunner | None,
) -> dict[str, Any]:
    definition = dict(GATE_COMMANDS[gate_id])
    gate = {
        "gate_id": gate_id,
        "kind": definition["kind"],
        "required": True,
        "status": "blocked",
        "command": list(definition.get("command") or []),
        "cwd": str(definition.get("cwd") or "."),
        "exit_code": None,
        "stdout_excerpt": "",
        "stderr_excerpt": "",
        "reasons": [],
        "warnings": [],
        "blocks_promotion": True,
        "evidence_mode": "not_run",
    }
    if gate_id in fixture_results:
        return _gate_from_fixture_result(gate, fixture_results[gate_id])
    if mode == "dry_run":
        gate.update({"status": "skipped", "reasons": ["dry_run_validation_does_not_execute_gates"], "blocks_promotion": True, "evidence_mode": "dry_run"})
        return gate
    if definition["kind"] == "route_dry_run":
        return _run_route_dry_run_gate(workspace=workspace, run_id=run_id, proposal=proposal, gate=gate)
    if definition["kind"] == "route_provider_smoke":
        return _run_route_provider_smoke_gate(
            workspace=workspace,
            run_id=run_id,
            proposal=proposal,
            gate=gate,
            mode=mode,
            provider_authorized=provider_authorized,
            route_smoke_runner=route_smoke_runner,
        )
    if definition["kind"] == "internal":
        return _run_internal_gate(gate, proposal)
    if definition["kind"] == "manual":
        gate.update({"status": "blocked", "reasons": ["manual_review_required_before_promotion"], "blocks_promotion": True})
        return gate
    if definition["kind"] == "provider_smoke":
        if mode == "dry_run":
            gate.update({"status": "skipped", "reasons": ["dry_run_validation_does_not_execute_gates"], "blocks_promotion": True})
            return gate
        if mode == "provider_backed" and not provider_authorized:
            gate.update({"status": "skipped", "reasons": ["provider_calls_not_authorized"], "blocks_promotion": True, "evidence_mode": "dry_run"})
            return gate
        smoke_mode = "provider" if mode == "provider_backed" else "dry_run"
        return _run_provider_smoke_gate(
            workspace=workspace,
            run_id=run_id,
            proposal=proposal,
            gate=gate,
            smoke_mode=smoke_mode,
            allow_provider_calls=provider_authorized,
            configured_models=configured_models,
            capability_route_records=capability_route_records,
            provider_runtime=provider_runtime,
            credential_status=credential_status,
        )
    if not execute_commands:
        gate.update({"status": "skipped", "reasons": ["command_execution_disabled"], "blocks_promotion": True, "evidence_mode": "not_run"})
        return gate
    return _run_command_gate(workspace, gate, command_runner=command_runner)


def _run_provider_smoke_gate(
    *,
    workspace: Path,
    run_id: str,
    proposal: dict[str, Any],
    gate: dict[str, Any],
    smoke_mode: str,
    allow_provider_calls: bool,
    configured_models: list[dict[str, Any]] | None,
    capability_route_records: dict[str, Any] | None,
    provider_runtime: Any | None,
    credential_status: dict[str, Any] | None,
) -> dict[str, Any]:
    try:
        report = run_agentic_update_provider_smoke(
            workspace_root=workspace,
            run_id=run_id,
            proposal=proposal,
            mode=smoke_mode,
            allow_provider_calls=allow_provider_calls,
            credential_status=credential_status,
            configured_models=configured_models,
            capability_route_records=capability_route_records,
            runtime=provider_runtime,
            gate_id=str(gate.get("gate_id") or "provider_compatibility_smoke"),
        )
    except Exception as exc:  # noqa: BLE001 - validation records provider-smoke setup failures as evidence.
        gate.update({"status": "fail", "reasons": [_safe_text(str(exc) or exc.__class__.__name__)], "blocks_promotion": True})
        return gate
    blocks = provider_smoke_report_blocks_promotion(report, provider_backed=smoke_mode == "provider")
    gate.update(
        {
            "status": _smoke_gate_status(report, blocks=blocks),
            "reasons": _smoke_gate_reasons(report, blocks=blocks),
            "warnings": list(report.get("warnings") or []),
            "blocks_promotion": blocks,
            "evidence_mode": "provider" if smoke_mode == "provider" else "dry_run",
            "provider_smoke_report": {
                "schema_version": report.get("schema_version"),
                "run_id": report.get("run_id"),
                "status": report.get("status"),
                "case_count": dict(report.get("summary") or {}).get("case_count"),
                "artifact_paths": dict(report.get("artifact_paths") or {}),
                "matrix_update_suggestions": list(report.get("matrix_update_suggestions") or []),
            },
        }
    )
    return gate


def _run_route_dry_run_gate(
    *,
    workspace: Path,
    run_id: str,
    proposal: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any]:
    try:
        report = route_promotion_dry_run(proposal)
    except Exception as exc:  # noqa: BLE001 - malformed route records are validation evidence.
        gate.update(
            {
                "status": "fail",
                "reasons": [_safe_text(str(exc) or exc.__class__.__name__)],
                "blocks_promotion": True,
                "evidence_mode": "internal",
            }
        )
        return gate
    artifact_path = _write_route_promotion_gate_artifact(workspace, run_id, str(gate.get("gate_id") or "execution_route_dry_run"), report)
    blocks = str(report.get("status") or "") != "pass"
    gate.update(
        {
            "status": "pass" if not blocks else "fail",
            "reasons": _route_promotion_gate_reasons(report),
            "blocks_promotion": blocks,
            "evidence_mode": "internal",
            "route_promotion_report": {
                "schema_version": report.get("schema_version"),
                "kind": report.get("kind"),
                "status": report.get("status"),
                "record_count": len(list(report.get("record_results") or [])),
                "artifact_path": str(artifact_path),
            },
        }
    )
    return gate


def _run_route_provider_smoke_gate(
    *,
    workspace: Path,
    run_id: str,
    proposal: dict[str, Any],
    gate: dict[str, Any],
    mode: str,
    provider_authorized: bool,
    route_smoke_runner: RouteSmokeRunner | None,
) -> dict[str, Any]:
    gate_id = str(gate.get("gate_id") or "execution_route_provider_smoke")
    if mode != "provider_backed":
        gate.update(
            {
                "status": "skipped",
                "reasons": ["route_provider_smoke_requires_provider_backed_validation"],
                "blocks_promotion": True,
                "evidence_mode": "dry_run",
            }
        )
        return gate
    report = run_route_promotion_provider_smoke(
        proposal,
        gate_id=gate_id,
        allow_provider_calls=provider_authorized,
        route_smoke_runner=route_smoke_runner,
    )
    artifact_path = _write_route_promotion_gate_artifact(workspace, run_id, gate_id, report)
    blocks = str(report.get("status") or "") != "pass"
    gate.update(
        {
            "status": "pass" if not blocks else ("skipped" if not provider_authorized else "blocked"),
            "reasons": _route_promotion_gate_reasons(report),
            "warnings": list(report.get("warnings") or []),
            "blocks_promotion": blocks,
            "evidence_mode": "provider" if bool(report.get("provider_calls_attempted")) else "dry_run",
            "route_promotion_report": {
                "schema_version": report.get("schema_version"),
                "kind": report.get("kind"),
                "status": report.get("status"),
                "record_count": len(list(report.get("record_results") or [])),
                "artifact_path": str(artifact_path),
            },
        }
    )
    return gate


def _write_route_promotion_gate_artifact(workspace: Path, run_id: str, gate_id: str, report: dict[str, Any]) -> Path:
    safe_gate_id = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in gate_id)
    artifact_path = ensure_agentic_update_run_layout(workspace, run_id)["subdirectories"]["route-promotion"]
    path = Path(artifact_path) / "validation" / f"{safe_gate_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_secret_free_agentic_update_payload(report, label="agentic_update_route_promotion_validation")
    write_json(path, report)
    return path


def _route_promotion_gate_reasons(report: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for result in list(report.get("record_results") or []):
        if not isinstance(result, dict):
            continue
        if str(result.get("status") or "") == "pass":
            continue
        reasons.extend(_safe_text(str(item)) for item in list(result.get("reasons") or []) if str(item).strip())
    return _dedupe(reasons)


def _smoke_gate_status(report: dict[str, Any], *, blocks: bool) -> str:
    status = str(report.get("status") or "blocked")
    if blocks and status == "pass":
        return "blocked"
    if status in {"pass", "fail", "partial", "skipped", "blocked"}:
        return status
    return "blocked"


def _smoke_gate_reasons(report: dict[str, Any], *, blocks: bool) -> list[str]:
    reasons: list[str] = []
    for case in list(report.get("cases") or []):
        if not isinstance(case, dict):
            continue
        if str(case.get("status") or "") == "pass" and not blocks:
            continue
        reasons.extend(str(item) for item in list(case.get("reasons") or []) if str(item).strip())
    if blocks and not reasons:
        reasons.append("provider_smoke_blocks_promotion")
    return _dedupe(reasons)


def _run_internal_gate(gate: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    gate_id = str(gate.get("gate_id") or "")
    try:
        if gate_id == "schema_validation":
            validate_update_proposal(proposal)
        elif gate_id == "diff_check":
            _validate_diff_section(proposal)
        elif gate_id == "secret_scan":
            assert_secret_free_agentic_update_payload(proposal, label="agentic_update_validation_secret_scan")
        elif gate_id == "rollback_plan_review":
            _validate_rollback_section(proposal)
        else:
            raise ValueError(f"Unsupported internal validation gate: {gate_id}")
    except Exception as exc:  # noqa: BLE001 - validation reports failures as data.
        gate.update({"status": "fail", "reasons": [_safe_text(str(exc) or exc.__class__.__name__)], "blocks_promotion": True})
        return gate
    gate.update({"status": "pass", "blocks_promotion": False, "evidence_mode": "internal"})
    return gate


def _run_command_gate(workspace: Path, gate: dict[str, Any], *, command_runner: CommandRunner | None) -> dict[str, Any]:
    command = [str(item) for item in list(gate.get("command") or [])]
    cwd = _gate_cwd(workspace, str(gate.get("cwd") or "."))
    try:
        result = command_runner(command, cwd) if command_runner is not None else _default_command_runner(command, cwd)
    except Exception as exc:  # noqa: BLE001 - command failures are validation evidence.
        gate.update({"status": "fail", "reasons": [_safe_text(str(exc) or exc.__class__.__name__)], "blocks_promotion": True})
        return gate
    exit_code = int(result.get("exit_code") if result.get("exit_code") is not None else result.get("returncode") or 0)
    gate.update(
        {
            "exit_code": exit_code,
            "stdout_excerpt": _safe_text(str(result.get("stdout") or "")),
            "stderr_excerpt": _safe_text(str(result.get("stderr") or "")),
            "status": "pass" if exit_code == 0 else "fail",
            "blocks_promotion": exit_code != 0,
            "evidence_mode": "command",
        }
    )
    if exit_code != 0:
        gate["reasons"] = [f"command_exit_code_{exit_code}"]
    return gate


def _gate_from_fixture_result(gate: dict[str, Any], value: Any) -> dict[str, Any]:
    payload = dict(value) if isinstance(value, dict) else {"status": str(value)}
    status = str(payload.get("status") or "pass")
    if status not in {"pass", "warn", "fail", "partial", "skipped", "blocked"}:
        status = "blocked"
    gate.update(
        {
            "status": status,
            "exit_code": payload.get("exit_code"),
            "stdout_excerpt": _safe_text(str(payload.get("stdout") or "")),
            "stderr_excerpt": _safe_text(str(payload.get("stderr") or "")),
            "reasons": [_safe_text(str(item)) for item in list(payload.get("reasons") or [])],
            "warnings": [_safe_text(str(item)) for item in list(payload.get("warnings") or [])],
            "blocks_promotion": bool(payload.get("blocks_promotion", status in {"fail", "blocked", "partial"})),
            "evidence_mode": "fixture",
        }
    )
    return gate


def _default_command_runner(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
    )
    return {"exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def _validate_diff_section(proposal: dict[str, Any]) -> None:
    diff = dict(proposal.get("diff") or {})
    if str(diff.get("schema_version") or "") != "astrabridge-agentic-update-diff-v1":
        raise ValueError("proposal.diff has an unexpected schema version.")
    if str(diff.get("status") or "") == "not_generated":
        raise ValueError("proposal.diff has not been generated.")
    if "risk_class" not in diff:
        raise ValueError("proposal.diff.risk_class is required.")
    if not isinstance(diff.get("changes"), list):
        raise ValueError("proposal.diff.changes must be a list.")


def _validate_rollback_section(proposal: dict[str, Any]) -> None:
    rollback = dict(proposal.get("rollback_manifest") or {})
    if rollback.get("reversible") is not True:
        raise ValueError("proposal.rollback_manifest must be reversible.")
    if not isinstance(rollback.get("steps"), list):
        raise ValueError("proposal.rollback_manifest.steps must be a list.")


def _aggregate_status(gates: list[dict[str, Any]], *, mode: str) -> str:
    statuses = {str(gate.get("status") or "blocked") for gate in gates}
    blocking_skips = any(bool(gate.get("blocks_promotion")) and str(gate.get("status")) == "skipped" for gate in gates)
    if "fail" in statuses:
        return "fail"
    if "blocked" in statuses or blocking_skips:
        return "blocked"
    if "partial" in statuses or "warn" in statuses:
        return "partial"
    if statuses <= {"skipped"}:
        return "skipped"
    if mode == "dry_run":
        return "skipped"
    return "pass"


def _next_fix_targets(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for gate in gates:
        status = str(gate.get("status") or "")
        if status not in {"fail", "blocked", "partial", "skipped"}:
            continue
        if not bool(gate.get("blocks_promotion")):
            continue
        reasons = [str(item) for item in list(gate.get("reasons") or []) if str(item).strip()]
        targets.append(
            {
                "gate_id": gate.get("gate_id"),
                "status": status,
                "reason": reasons[0] if reasons else "validation_gate_blocks_promotion",
                "action": _next_action_for_gate(str(gate.get("gate_id") or ""), reasons),
            }
        )
    return targets


def _next_action_for_gate(gate_id: str, reasons: list[str]) -> str:
    if "provider_calls_not_authorized" in reasons:
        return "Request explicit allow_provider_calls=true authorization or run fixture-only validation without promotion."
    if gate_id in {"metadata_tests", "model_catalog_tests", "transport_tests", "desktop_tests", "desktop_build", "codex_kernel_smoke"}:
        return "Inspect stdout/stderr excerpts, fix the failing code path, and rerun the validation gate."
    if gate_id == "provider_compatibility_smoke":
        return "Run provider compatibility smoke after explicit provider-call authorization."
    if gate_id == "capability_smoke":
        return "Run capability smoke after explicit provider-call authorization."
    if gate_id == "execution_route_dry_run":
        return "Fix the route subject or evidence binding, then rerun the secret-free route dry-run."
    if gate_id in {"execution_route_provider_smoke", "execution_route_tool_contract", "execution_route_coding_smoke", "execution_route_default_review"}:
        return "Run the exact route-bound provider smoke after explicit authorization and attach the returned evidence references."
    if gate_id == "manual_review":
        return "Complete manual review and attach approval evidence before promotion."
    return "Inspect the validation report and rerun after resolving the recorded reason."


def _report_warnings(gates: list[dict[str, Any]], *, mode: str) -> list[str]:
    warnings: list[str] = []
    if mode == "dry_run":
        warnings.append("dry_run_validation_did_not_execute_gates")
    if any(str(gate.get("status")) == "skipped" and "provider_calls_not_authorized" in gate.get("reasons", []) for gate in gates):
        warnings.append("provider_backed_validation_skipped_without_authorization")
    return warnings


def _render_validation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agentic Update Validation Report",
        "",
        f"- Run id: `{report.get('run_id')}`",
        f"- Status: `{report.get('status')}`",
        f"- Mode: `{report.get('mode')}`",
        f"- Risk class: `{report.get('risk_class')}`",
        f"- Promotion blocked: `{report.get('promotion_blocked')}`",
        "",
        "## Gates",
        "",
        "| Gate | Status | Reason | Command |",
        "| --- | --- | --- | --- |",
    ]
    for gate in list(report.get("gates") or []):
        reason = "; ".join(str(item) for item in list(gate.get("reasons") or []))
        command = " ".join(str(item) for item in list(gate.get("command") or []))
        lines.append(f"| {_md(str(gate.get('gate_id') or ''))} | {_md(str(gate.get('status') or ''))} | {_md(reason)} | {_md(command)} |")
    if report.get("next_fix_targets"):
        lines.extend(["", "## Next Fix Targets", ""])
        for target in list(report.get("next_fix_targets") or []):
            lines.append(f"- `{target.get('gate_id')}`: {target.get('action')}")
    return "\n".join(lines).rstrip() + "\n"


def _update_proposal_validation(proposal_path: Path, report: dict[str, Any]) -> None:
    if not proposal_path.exists():
        return
    proposal = read_json(proposal_path, {})
    if not isinstance(proposal, dict):
        return
    proposal["validation_result"] = {
        "schema_version": "astrabridge-agentic-update-validation-result-v1",
        "status": report["status"],
        "mode": report.get("mode"),
        "gates": [
            {
                "gate_id": gate.get("gate_id"),
                "status": gate.get("status"),
                "blocks_promotion": gate.get("blocks_promotion"),
                "evidence_mode": gate.get("evidence_mode"),
                "reasons": list(gate.get("reasons") or []),
                "route_promotion_report": dict(gate.get("route_promotion_report") or {}),
            }
            for gate in list(report.get("gates") or [])
        ],
        "evidence_paths": ["validation/validation-report.json", "validation/validation-report.md"],
        "warnings": list(report.get("warnings") or []),
    }
    write_json(proposal_path, validate_update_proposal(proposal))


def _gate_cwd(workspace: Path, cwd: str) -> Path:
    if cwd in {"", "."}:
        return workspace
    candidate = workspace / cwd
    return candidate.resolve()


def _safe_text(value: str) -> str:
    sanitized = redact_sensitive(value)
    text = str(sanitized or "")
    return text[:4000]


def _md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
