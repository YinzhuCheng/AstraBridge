from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
from typing import Any, Callable, Iterator

from ..codex_kernel_probe import discover_codex_binary_and_version
from ..common import new_id, now_iso, slugify, write_json
from .apply import AGENTIC_UPDATE_APPLY_JOURNAL_SCHEMA_VERSION
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
APPLY_TRACK_CODEX_KERNEL_CANDIDATE = "codex_kernel_candidate"

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
    journal_path = Path(layout["files"]["apply_journal"])
    activation_id = new_id("kernel-verify")
    runtime_state_before = _kernel_runtime_state_before(
        execution_host=execution_host,
        wsl_distro=wsl_distro,
        baseline=baseline,
        binary_locator=locator,
        candidate=selected,
    )
    activation_journal = _initialize_kernel_activation_journal(
        run_id=run_id,
        activation_id=activation_id,
        proposal=validated_proposal,
        candidate=selected,
        execution_host=execution_host,
        wsl_distro=wsl_distro,
        runtime_state_before=runtime_state_before,
    )
    _write_kernel_activation_journal(journal_path, activation_journal)
    _append_kernel_activation_stage(activation_journal, journal_path, stage="baseline_captured")
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
    track_changed_paths = _kernel_track_changed_paths(workspace=workspace, run_id=run_id, evidence=evidence, report_path=report_path)
    staged_state = _kernel_activation_staged_state(
        candidate=selected,
        facts=facts,
        evidence=evidence,
        status=status,
        verified=status == "verified",
        matrix_update=matrix_update,
        rollback_required=rollback_required,
        rollback_reason=rollback_reason,
    )
    _append_kernel_activation_stage(activation_journal, journal_path, stage="candidate_checked")
    _finalize_kernel_activation_track(
        activation_journal,
        journal_path,
        staged_state=staged_state,
        health_verdict="pass" if status == "verified" else "fail",
        changed_paths=track_changed_paths,
    )
    rollback_manifest_path = _write_kernel_rollback_manifest(
        workspace=workspace,
        run_id=run_id,
        contract=contract,
        selected=selected,
        facts=facts,
        status=status,
        reason=rollback_reason or ("verification_gate_passed" if status == "verified" else "candidate_requires_rollback_evidence"),
        evidence=evidence,
        baseline=baseline,
        runtime_state_before=runtime_state_before,
    )
    runtime_state_after = _kernel_runtime_state_after(
        execution_host=execution_host,
        wsl_distro=wsl_distro,
        baseline=baseline,
        binary_locator=locator,
        candidate=selected,
    )
    restored_runtime_state = runtime_state_after["active_env_locator"] == runtime_state_before["active_env_locator"]
    _close_kernel_activation_track(
        activation_journal,
        journal_path,
        rollback_target=_kernel_activation_rollback_target(
            workspace=workspace,
            run_id=run_id,
            rollback_manifest_path=Path(rollback_manifest_path),
            runtime_state_before=runtime_state_before,
            runtime_state_after=runtime_state_after,
            restored_runtime_state=restored_runtime_state,
            status=status,
        ),
        restored_runtime_state=restored_runtime_state,
        committed=status == "verified",
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
        "activation": {
            "activation_id": activation_id,
            "journal_status": activation_journal.get("status"),
            "track_id": APPLY_TRACK_CODEX_KERNEL_CANDIDATE,
            "restored_runtime_state": restored_runtime_state,
            "runtime_state_before": runtime_state_before,
            "runtime_state_after": runtime_state_after,
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
            "apply_journal": str(journal_path),
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
    runtime_state_before: dict[str, Any],
) -> str:
    manifest = rollback_manifest_template(run_id, contract)
    manifest["rollback_targets"]["codex_binary_locator_state"].append(
        {
            "target_id": "codex-kernel-candidate-locator",
            "candidate_id": selected.get("candidate_id"),
            "candidate_version": selected.get("version"),
            "candidate_locator": facts.get("binary_locator"),
            "baseline_locator": dict(baseline or {}).get("binary_locator"),
            "env_key": runtime_state_before.get("env_key"),
            "baseline_env_locator": runtime_state_before.get("active_env_locator"),
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


def _kernel_runtime_state_before(
    *,
    execution_host: str,
    wsl_distro: str | None,
    baseline: dict[str, Any] | None,
    binary_locator: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    env_key = _kernel_locator_env_key(execution_host)
    return {
        "execution_host": execution_host,
        "wsl_distro": wsl_distro,
        "env_key": env_key,
        "active_env_locator": str(os.environ.get(env_key) or ""),
        "baseline_locator": str(dict(baseline or {}).get("binary_locator") or ""),
        "candidate_locator": str(binary_locator or candidate.get("binary_locator") or ""),
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "candidate_version": str(candidate.get("version") or ""),
    }


def _kernel_runtime_state_after(
    *,
    execution_host: str,
    wsl_distro: str | None,
    baseline: dict[str, Any] | None,
    binary_locator: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    state = _kernel_runtime_state_before(
        execution_host=execution_host,
        wsl_distro=wsl_distro,
        baseline=baseline,
        binary_locator=binary_locator,
        candidate=candidate,
    )
    state["restored_at"] = now_iso()
    return state


def _kernel_locator_env_key(execution_host: str) -> str:
    return "ASTRABRIDGE_WSL_CODEX_BIN" if execution_host == "wsl" else "ASTRABRIDGE_CODEX_BIN"


def _initialize_kernel_activation_journal(
    *,
    run_id: str,
    activation_id: str,
    proposal: dict[str, Any],
    candidate: dict[str, Any],
    execution_host: str,
    wsl_distro: str | None,
    runtime_state_before: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": AGENTIC_UPDATE_APPLY_JOURNAL_SCHEMA_VERSION,
        "apply_id": activation_id,
        "run_id": run_id,
        "status": "running",
        "mode": "kernel_candidate_verify",
        "started_at": now_iso(),
        "completed_at": None,
        "risk_class": str(dict(proposal.get("diff") or {}).get("risk_class") or ""),
        "approval": {
            "approved": True,
            "approved_by": "kernel_verification_gate",
            "approved_at": now_iso(),
            "approval_note": "verification_only_no_runtime_promotion",
        },
        "tracks": [
            {
                "track_id": APPLY_TRACK_CODEX_KERNEL_CANDIDATE,
                "status": "running",
                "source_digest": _json_sha256(runtime_state_before),
                "staged_digest": None,
                "trust_decision": _kernel_trust_decision(candidate=candidate, execution_host=execution_host, wsl_distro=wsl_distro),
                "health_verdict": "not_run",
                "changed_paths": [],
                "change_ids": [str(candidate.get("candidate_id") or str(candidate.get("version") or "codex-kernel-candidate"))],
                "rollback_target": {},
                "history": [
                    {
                        "stage": "initialized",
                        "at": now_iso(),
                        "candidate_id": str(candidate.get("candidate_id") or ""),
                        "candidate_version": str(candidate.get("version") or ""),
                    }
                ],
            }
        ],
    }


def _kernel_trust_decision(*, candidate: dict[str, Any], execution_host: str, wsl_distro: str | None) -> str:
    apply_mode = str(dict(candidate.get("permission_policy") or {}).get("apply_mode") or "verify_candidate").strip()
    if execution_host == "wsl" and wsl_distro:
        return f"kernel_candidate_{apply_mode}:{execution_host}:{wsl_distro}"
    return f"kernel_candidate_{apply_mode}:{execution_host}"


def _write_kernel_activation_journal(path: Path, journal: dict[str, Any]) -> None:
    assert_secret_free_agentic_update_payload(journal, label="kernel_activation_journal")
    write_json(path, journal)


def _append_kernel_activation_stage(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    stage: str,
    **details: Any,
) -> None:
    track = _kernel_activation_track(journal)
    history = list(track.get("history") or [])
    entry = {"stage": stage, "at": now_iso()}
    for key, value in details.items():
        if value is not None:
            entry[key] = value
    history.append(entry)
    track["history"] = history
    _write_kernel_activation_journal(journal_path, journal)


def _finalize_kernel_activation_track(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    staged_state: dict[str, Any],
    health_verdict: str,
    changed_paths: list[str],
) -> None:
    track = _kernel_activation_track(journal)
    track["staged_digest"] = _json_sha256(staged_state)
    track["health_verdict"] = health_verdict
    track["changed_paths"] = list(changed_paths)
    _append_kernel_activation_stage(
        journal,
        journal_path,
        stage="healthcheck_completed",
        verdict=health_verdict,
    )


def _close_kernel_activation_track(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    rollback_target: dict[str, Any],
    restored_runtime_state: bool,
    committed: bool,
) -> None:
    terminal_status = "committed" if committed else "rolled_back"
    journal["status"] = terminal_status
    journal["completed_at"] = now_iso()
    track = _kernel_activation_track(journal)
    track["status"] = terminal_status
    track["rollback_target"] = dict(rollback_target)
    history = list(track.get("history") or [])
    history.append(
        {
            "stage": terminal_status,
            "at": now_iso(),
            "restored_runtime_state": restored_runtime_state,
        }
    )
    track["history"] = history
    _write_kernel_activation_journal(journal_path, journal)


def _kernel_activation_track(journal: dict[str, Any]) -> dict[str, Any]:
    for track in list(journal.get("tracks") or []):
        if str(track.get("track_id") or "") == APPLY_TRACK_CODEX_KERNEL_CANDIDATE:
            return track
    raise ValueError("Missing kernel activation journal track.")


def _kernel_activation_staged_state(
    *,
    candidate: dict[str, Any],
    facts: dict[str, Any],
    evidence: dict[str, Any],
    status: str,
    verified: bool,
    matrix_update: dict[str, Any],
    rollback_required: bool,
    rollback_reason: str | None,
) -> dict[str, Any]:
    return {
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "candidate_version": str(candidate.get("version") or ""),
        "status": status,
        "verified": verified,
        "binary_locator": facts.get("binary_locator"),
        "probe_evidence_paths": list(evidence.get("probe_evidence_paths") or []),
        "smoke_evidence_paths": list(evidence.get("smoke_evidence_paths") or []),
        "matrix_id": matrix_update.get("matrix_id"),
        "smoke_result": matrix_update.get("smoke_result"),
        "rollback_required": rollback_required,
        "rollback_reason": rollback_reason,
    }


def _kernel_track_changed_paths(
    *,
    workspace: Path,
    run_id: str,
    evidence: dict[str, Any],
    report_path: Path,
) -> list[str]:
    paths: list[str] = []
    for value in (
        evidence.get("smoke_report_path"),
        evidence.get("kernel_probe_snapshot_path"),
        str(report_path),
    ):
        text = str(value or "").strip()
        if not text:
            continue
        paths.append(_run_relative(workspace, run_id, Path(text)))
    return _dedupe(paths)


def _kernel_activation_rollback_target(
    *,
    workspace: Path,
    run_id: str,
    rollback_manifest_path: Path,
    runtime_state_before: dict[str, Any],
    runtime_state_after: dict[str, Any],
    restored_runtime_state: bool,
    status: str,
) -> dict[str, Any]:
    return {
        "rollback_manifest_path": _run_relative(workspace, run_id, rollback_manifest_path),
        "runtime_state_before": deepcopy(runtime_state_before),
        "runtime_state_after": deepcopy(runtime_state_after),
        "restored_runtime_state": restored_runtime_state,
        "status": status,
    }


def _json_sha256(payload: Any) -> str:
    import hashlib
    import json

    canonical = deepcopy(payload)
    json_bytes = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(json_bytes).hexdigest()


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
