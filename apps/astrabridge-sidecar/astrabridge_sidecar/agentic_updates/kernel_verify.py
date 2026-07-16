from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
from typing import Any, Callable, Iterator

from ..codex_kernel_probe import discover_codex_binary_and_version
from ..common import now_iso, slugify, write_json
from .artifacts import (
    ensure_agentic_update_run_layout,
    rollback_manifest_template,
    validate_agentic_update_artifact_path,
    validate_rollback_manifest,
)
from .contracts import assert_secret_free_agentic_update_payload, validate_update_proposal


AGENTIC_UPDATE_KERNEL_VERIFY_SCHEMA_VERSION = "astrabridge-agentic-update-codex-kernel-verify-v1"
AGENTIC_UPDATE_KERNEL_VERIFY_FILENAME = "validation/codex-kernel-verify-report.json"
KERNEL_VERIFY_STATUSES = ("verified", "partial", "blocked")

KernelSmokeRunner = Callable[..., dict[str, Any]]


def _default_kernel_smoke_runner(*args: Any, **kwargs: Any) -> dict[str, Any]:
    # Import lazily because automations.specs imports agentic_updates while the
    # smoke module imports the automations package.
    from ..codex_kernel_smoke import run_codex_kernel_smoke

    return run_codex_kernel_smoke(*args, **kwargs)


def run_agentic_update_kernel_candidate_verification(
    *,
    workspace_root: str | Path,
    run_id: str,
    proposal: dict[str, Any],
    candidate_id: str | None = None,
    candidate: dict[str, Any] | None = None,
    binary_locator: str | None = None,
    version_locator: str | None = None,
    mode: str = "fixture",
    execution_host: str = "windows",
    wsl_distro: str | None = None,
    baseline: dict[str, Any] | None = None,
    fixture_smoke_report: dict[str, Any] | None = None,
    kernel_smoke_runner: KernelSmokeRunner | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    layout = ensure_agentic_update_run_layout(workspace, run_id)
    validated_proposal = validate_update_proposal(proposal)
    selected = _select_candidate(validated_proposal, candidate_id=candidate_id, candidate=candidate, version_locator=version_locator)
    contract = dict(validated_proposal.get("run_contract") or {})
    _validate_kernel_contract(contract, selected)
    normalized_mode = _normalize_mode(mode)
    verify_run_id = _verification_run_id(run_id, selected)
    artifact_root = validate_agentic_update_artifact_path(workspace, run_id, f"validation/codex-kernel-verify/{verify_run_id}")
    artifact_root.mkdir(parents=True, exist_ok=True)

    locator = str(binary_locator or selected.get("binary_locator") or "").strip()
    smoke_report = _run_or_write_smoke_report(
        workspace=workspace,
        artifact_root=artifact_root,
        mode=normalized_mode,
        execution_host=execution_host,
        wsl_distro=wsl_distro,
        binary_locator=locator,
        fixture_smoke_report=fixture_smoke_report,
        kernel_smoke_runner=kernel_smoke_runner,
    )
    report_path = validate_agentic_update_artifact_path(workspace, run_id, AGENTIC_UPDATE_KERNEL_VERIFY_FILENAME)
    facts = _candidate_facts(smoke_report=smoke_report, selected=selected, binary_locator=locator)
    evidence = _evidence_summary(workspace, smoke_report)
    status, reasons, warnings = _verification_status(
        selected=selected,
        facts=facts,
        smoke_report=smoke_report,
        evidence=evidence,
    )
    matrix_update = _matrix_update_suggestion(
        selected=selected,
        facts=facts,
        status=status,
        reasons=reasons,
        warnings=warnings,
        evidence=evidence,
        execution_host=execution_host,
        wsl_distro=wsl_distro,
    )
    rollback_required, rollback_reason = _rollback_required(status=status, baseline=baseline)
    rollback_manifest_path = None
    if rollback_required:
        rollback_manifest_path = _write_kernel_rollback_manifest(
            workspace=workspace,
            run_id=run_id,
            contract=contract,
            selected=selected,
            facts=facts,
            status=status,
            reason=rollback_reason,
            evidence=evidence,
            baseline=baseline,
        )

    candidate_after = deepcopy(selected)
    candidate_after["validation_state"] = {
        "status": status,
        "verified": status == "verified",
        "probe_evidence_paths": evidence["probe_evidence_paths"],
        "smoke_evidence_paths": evidence["smoke_evidence_paths"],
        "verified_gate": {
            "probe_evidence_present": evidence["probe_evidence_present"],
            "smoke_evidence_present": evidence["smoke_evidence_present"],
            "smoke_result": matrix_update["smoke_result"],
        },
    }
    candidate_after["promotion_state"] = {
        "status": status,
        "recommended": status == "verified",
        "requires_manual_review": status != "verified",
        "matrix_update_suggestion_id": matrix_update["matrix_id"],
    }
    report = {
        "schema_version": AGENTIC_UPDATE_KERNEL_VERIFY_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "run_id": run_id,
        "verification_run_id": verify_run_id,
        "mode": normalized_mode,
        "status": status,
        "verified": status == "verified",
        "candidate": candidate_after,
        "candidate_facts": facts,
        "baseline": dict(baseline or {}),
        "rollback": {
            "required": rollback_required,
            "reason": rollback_reason,
            "manifest_path": rollback_manifest_path,
        },
        "matrix_update_suggestion": matrix_update,
        "side_effect_policy": {
            "writes_official_codex_config": False,
            "writes_project_codex_files": False,
            "writes_astrabridge_runtime_config": False,
            "installs_binary": False,
            "switches_binary": False,
            "uses_temporary_binary_env_override": bool(locator),
        },
        "isolated_runtime_roots": {
            "artifact_root": str(artifact_root),
            "workspace_root": smoke_report.get("workspace_root"),
            "project_file": smoke_report.get("project_file"),
        },
        "artifact_paths": {
            "verification_report": str(report_path),
            "verification_root": str(artifact_root),
            "smoke_report": evidence["smoke_report_path"],
            "kernel_probe_snapshot": evidence["kernel_probe_snapshot_path"],
            "rollback_manifest": rollback_manifest_path,
        },
        "reasons": reasons,
        "warnings": warnings,
    }
    assert_secret_free_agentic_update_payload(report, label="agentic_update_kernel_verify")
    write_json(report_path, report)
    return report


def kernel_verify_blocks_promotion(report: dict[str, Any]) -> bool:
    return str(report.get("status") or "") != "verified" or not bool(report.get("verified"))


def _run_or_write_smoke_report(
    *,
    workspace: Path,
    artifact_root: Path,
    mode: str,
    execution_host: str,
    wsl_distro: str | None,
    binary_locator: str,
    fixture_smoke_report: dict[str, Any] | None,
    kernel_smoke_runner: KernelSmokeRunner | None,
) -> dict[str, Any]:
    if mode == "fixture":
        if fixture_smoke_report is None:
            raise ValueError("fixture kernel verification requires fixture_smoke_report.")
        return _write_fixture_smoke_report(artifact_root, fixture_smoke_report)
    runner = kernel_smoke_runner or _default_kernel_smoke_runner
    env_key = "ASTRABRIDGE_WSL_CODEX_BIN" if execution_host == "wsl" else "ASTRABRIDGE_CODEX_BIN"
    updates = {env_key: binary_locator} if binary_locator else {}
    with _temporary_env(updates):
        return runner(
            artifact_root=artifact_root,
            repo_root=workspace,
            execution_host=execution_host,
            wsl_distro=wsl_distro,
            binary_discovery_fn=_binary_discovery_fn(execution_host=execution_host, wsl_distro=wsl_distro, binary_locator=binary_locator),
        )


def _write_fixture_smoke_report(artifact_root: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    report = deepcopy(fixture)
    reports_dir = artifact_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    smoke_path = reports_dir / "smoke-report.json"
    probe_path = reports_dir / "kernel-probe-snapshot.json"
    binary_details = _binary_details_from_smoke(report)
    if binary_details:
        probe_payload = {
            "schema_version": "codex-kernel-probe-snapshot-v1",
            "generated_at": now_iso(),
            "observed": {"binary": binary_details},
            "inferred": {
                "compatibility_status": "compatible" if binary_details.get("version_parse_status") == "ok" else "blocked",
            },
        }
        write_json(probe_path, probe_payload)
        report["kernel_probe_snapshot_path"] = str(probe_path)
    report.setdefault("schema_version", "codex-kernel-smoke-v1")
    report.setdefault("artifact_root", str(artifact_root))
    report.setdefault("checks", [])
    report.setdefault("summary", {"overall_status": "fail", "critical_failures": ["fixture_missing_summary"]})
    report["report_path"] = str(smoke_path)
    artifacts = [str(smoke_path)]
    if report.get("kernel_probe_snapshot_path"):
        artifacts.append(str(probe_path))
    report["artifacts"] = _dedupe([str(item) for item in list(report.get("artifacts") or []) + artifacts])
    write_json(smoke_path, report)
    return report


def _binary_discovery_fn(*, execution_host: str, wsl_distro: str | None, binary_locator: str) -> Callable[..., dict[str, Any]]:
    def run(**_kwargs: Any) -> dict[str, Any]:
        env = dict(os.environ)
        if binary_locator:
            key = "ASTRABRIDGE_WSL_CODEX_BIN" if execution_host == "wsl" else "ASTRABRIDGE_CODEX_BIN"
            env[key] = binary_locator
        return discover_codex_binary_and_version(execution_host=execution_host, wsl_distro=wsl_distro, environ=env)

    return run


def _select_candidate(
    proposal: dict[str, Any],
    *,
    candidate_id: str | None,
    candidate: dict[str, Any] | None,
    version_locator: str | None,
) -> dict[str, Any]:
    if isinstance(candidate, dict):
        return deepcopy(candidate)
    target_id = str(candidate_id or "").strip()
    target_version = str(version_locator or dict(proposal.get("run_contract") or {}).get("target_version") or "").strip()
    for item in list(dict(proposal.get("discovery_result") or {}).get("findings") or []):
        if not isinstance(item, dict) or str(item.get("kind") or "") != "codex_kernel_candidate":
            continue
        if target_id and str(item.get("candidate_id") or "") != target_id:
            continue
        if target_version and str(item.get("version") or "") != target_version:
            continue
        return deepcopy(item)
    raise ValueError("No matching Codex kernel candidate was found in the proposal.")


def _validate_kernel_contract(contract: dict[str, Any], candidate: dict[str, Any]) -> None:
    if "codex_kernel" not in set(contract.get("scope") or []):
        raise ValueError("Codex kernel verification requires codex_kernel scope.")
    if str(contract.get("apply_mode") or "") not in {"verify_candidate", "promote_after_smoke"}:
        raise ValueError("Codex kernel verification requires apply_mode=verify_candidate or promote_after_smoke.")
    target_version = str(contract.get("target_version") or "").strip()
    candidate_version = str(candidate.get("version") or "").strip()
    if not target_version:
        raise ValueError("Codex kernel verification requires a pinned target_version.")
    if candidate_version and candidate_version != target_version:
        raise ValueError("Codex kernel candidate version must match run_contract.target_version.")


def _verification_status(
    *,
    selected: dict[str, Any],
    facts: dict[str, Any],
    smoke_report: dict[str, Any],
    evidence: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []
    expected = str(selected.get("version") or "").strip()
    observed = str(facts.get("observed_version") or "").strip()
    if not evidence["probe_evidence_present"]:
        reasons.append("kernel_probe_evidence_missing")
    if not evidence["smoke_evidence_present"]:
        reasons.append("kernel_smoke_evidence_missing")
    if str(facts.get("version_parse_status") or "") != "ok":
        reasons.append("kernel_version_parse_not_ok")
    if expected and observed and expected != observed:
        reasons.append("candidate_version_mismatch")
    elif expected and not observed:
        reasons.append("candidate_version_not_observed")

    summary = dict(smoke_report.get("summary") or {})
    smoke_status = str(summary.get("overall_status") or "fail")
    critical_failures = [str(item) for item in list(summary.get("critical_failures") or []) if str(item).strip()]
    if critical_failures:
        reasons.append("kernel_smoke_critical_failures")
    if smoke_status == "warn":
        warnings.append("kernel_smoke_completed_with_warnings")
    elif smoke_status != "pass":
        reasons.append(f"kernel_smoke_status_{smoke_status or 'unknown'}")

    if reasons:
        return "blocked", _dedupe(reasons), _dedupe(warnings)
    if warnings:
        return "partial", [], _dedupe(warnings)
    return "verified", [], []


def _candidate_facts(*, smoke_report: dict[str, Any], selected: dict[str, Any], binary_locator: str) -> dict[str, Any]:
    binary = _binary_details_from_smoke(smoke_report)
    locator = binary_locator or str(binary.get("path") or binary.get("launch_descriptor") or "").strip()
    return {
        "candidate_id": selected.get("candidate_id"),
        "expected_version": selected.get("version"),
        "observed_version": binary.get("version_semver"),
        "version_text": binary.get("version_text"),
        "version_parse_status": binary.get("version_parse_status"),
        "binary_locator": locator,
        "binary_path": binary.get("path"),
        "path_source": binary.get("path_source"),
        "launch_descriptor": binary.get("launch_descriptor"),
    }


def _binary_details_from_smoke(smoke_report: dict[str, Any]) -> dict[str, Any]:
    for check in list(smoke_report.get("checks") or []):
        if isinstance(check, dict) and str(check.get("check_id") or "") == "binary_discovery":
            return dict(check.get("details") or {})
    binary = smoke_report.get("binary")
    return dict(binary) if isinstance(binary, dict) else {}


def _evidence_summary(workspace: Path, smoke_report: dict[str, Any]) -> dict[str, Any]:
    smoke_path = _path_or_none(smoke_report.get("report_path"))
    probe_path = _path_or_none(smoke_report.get("kernel_probe_snapshot_path"))
    smoke_exists = smoke_path is not None and smoke_path.exists()
    probe_exists = probe_path is not None and probe_path.exists()
    return {
        "smoke_report_path": str(smoke_path) if smoke_path else None,
        "kernel_probe_snapshot_path": str(probe_path) if probe_path else None,
        "smoke_evidence_present": smoke_exists,
        "probe_evidence_present": probe_exists,
        "smoke_evidence_paths": [_workspace_relative(workspace, smoke_path)] if smoke_exists and smoke_path else [],
        "probe_evidence_paths": [_workspace_relative(workspace, probe_path)] if probe_exists and probe_path else [],
        "evidence_paths": _dedupe(
            [_workspace_relative(workspace, path) for path in [smoke_path, probe_path] if path is not None and path.exists()]
        ),
    }


def _matrix_update_suggestion(
    *,
    selected: dict[str, Any],
    facts: dict[str, Any],
    status: str,
    reasons: list[str],
    warnings: list[str],
    evidence: dict[str, Any],
    execution_host: str,
    wsl_distro: str | None,
) -> dict[str, Any]:
    version = str(facts.get("observed_version") or selected.get("version") or "unknown").strip()
    platform = "wsl" if execution_host == "wsl" else "windows"
    matrix_id = slugify(f"AB-CODEX-{version}-{platform}", default="AB-CODEX-candidate").upper()
    smoke_result = "passed" if status == "verified" else ("failed" if status == "blocked" else "not_run")
    return {
        "matrix_id": matrix_id,
        "codex_version": version,
        "release_anchor": f"codex-cli {selected.get('version')}",
        "platform": platform,
        "execution_lane": f"AstraBridge agentic update {platform}{':' + wsl_distro if wsl_distro else ''}",
        "binary_locator": facts.get("binary_locator"),
        "overall_status": status,
        "probe_result": facts.get("version_parse_status"),
        "smoke_result": smoke_result,
        "known_breakages": list(reasons) or ["none recorded"],
        "required_mitigations": _mitigations_for_status(status, reasons),
        "evidence_paths": evidence["evidence_paths"],
        "last_reviewed_at": now_iso().split("T", 1)[0],
        "warnings": list(warnings),
    }


def _mitigations_for_status(status: str, reasons: list[str]) -> list[str]:
    if status == "verified":
        return ["none"]
    if "candidate_version_mismatch" in reasons:
        return ["Verify the exact pinned candidate binary locator before promotion."]
    if "kernel_probe_evidence_missing" in reasons or "kernel_smoke_evidence_missing" in reasons:
        return ["Rerun candidate verification and preserve both probe and smoke evidence."]
    return ["Keep the current baseline locator until the candidate passes kernel probe and smoke."]


def _rollback_required(*, status: str, baseline: dict[str, Any] | None) -> tuple[bool, str | None]:
    if status == "blocked":
        return True, "candidate_blocked"
    if not baseline:
        return False, None
    baseline_status = str(baseline.get("overall_status") or baseline.get("status") or "unknown")
    if _status_rank(status) < _status_rank(baseline_status):
        return True, "candidate_worse_than_baseline"
    return False, None


def _write_kernel_rollback_manifest(
    *,
    workspace: Path,
    run_id: str,
    contract: dict[str, Any],
    selected: dict[str, Any],
    facts: dict[str, Any],
    status: str,
    reason: str | None,
    evidence: dict[str, Any],
    baseline: dict[str, Any] | None,
) -> str:
    manifest = rollback_manifest_template(run_id, contract)
    manifest["rollback_targets"]["codex_binary_locator_state"].append(
        {
            "target_id": "codex-kernel-candidate-locator",
            "candidate_id": selected.get("candidate_id"),
            "candidate_version": selected.get("version"),
            "candidate_locator": facts.get("binary_locator"),
            "baseline_locator": dict(baseline or {}).get("binary_locator"),
            "status": status,
            "reason": reason,
        }
    )
    manifest["steps"].append(
        {
            "step_id": "restore-baseline-codex-binary-locator",
            "target_kind": "codex_binary_locator_state",
            "action": "restore_previous_locator_or_clear_temporary_candidate_override",
            "status": "planned",
            "requires_user_approval": False,
            "destructive_without_approval": False,
        }
    )
    manifest_evidence = [
        _run_relative(workspace, run_id, path)
        for path in [
            _path_or_none(evidence.get("smoke_report_path")),
            _path_or_none(evidence.get("kernel_probe_snapshot_path")),
        ]
        if path is not None and path.exists()
    ]
    manifest["evidence_paths"] = _dedupe(list(manifest.get("evidence_paths") or []) + manifest_evidence)
    manifest["warnings"] = _dedupe(list(manifest.get("warnings") or []) + [str(reason or "candidate_requires_rollback_evidence")])
    validated = validate_rollback_manifest(manifest, workspace_root=workspace)
    layout = ensure_agentic_update_run_layout(workspace, run_id)
    rollback_path = Path(layout["files"]["rollback_manifest"])
    write_json(rollback_path, validated)
    return str(rollback_path)


def _normalize_mode(mode: str) -> str:
    text = str(mode or "fixture").strip()
    if text not in {"fixture", "existing_binary"}:
        raise ValueError(f"Unsupported Codex kernel verification mode: {text}")
    return text


def _verification_run_id(run_id: str, candidate: dict[str, Any]) -> str:
    return slugify(f"{run_id}-{candidate.get('candidate_id') or candidate.get('version') or 'candidate'}", default="codex-kernel-verify")


def _status_rank(status: str) -> int:
    return {"verified": 4, "probed": 3, "partial": 2, "blocked": 1, "unknown": 0}.get(str(status or "unknown"), 0)


def _path_or_none(value: Any) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def _workspace_relative(workspace: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return str(path)


def _run_relative(workspace: Path, run_id: str, path: Path) -> str:
    run_root = workspace / "PRIVATE" / "agentic-update-pipeline" / "runs" / run_id
    try:
        return path.resolve().relative_to(run_root.resolve()).as_posix()
    except ValueError:
        return _workspace_relative(workspace, path)


@contextmanager
def _temporary_env(updates: dict[str, str]) -> Iterator[None]:
    original = {key: os.environ.get(key) for key in updates}
    for key, value in updates.items():
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result
