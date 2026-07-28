from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from ..capabilities.capability_routes import normalize_capability_route_record
from ..common import new_id, now_iso, read_json, write_json
from ..model_catalog import GENERATED_CATALOG_SCHEMA, current_generated_catalog
from ..security import SecurityError, resolve_under
from .artifacts import (
    ensure_agentic_update_run_layout,
    rollback_manifest_template,
    validate_agentic_update_artifact_path,
    validate_rollback_manifest,
)
from .contracts import assert_secret_free_agentic_update_payload, validate_update_proposal
from .route_promotion import (
    ROUTE_PROMOTION_CHANGE_TYPES,
    route_promotion_apply_ledger,
    route_promotion_records_from_proposal,
    route_promotion_rollback_record,
    route_promotion_storage_for_model,
    validate_route_promotion_apply,
)


AGENTIC_UPDATE_APPLY_MANIFEST_SCHEMA_VERSION = "astrabridge-agentic-update-apply-manifest-v1"
AGENTIC_UPDATE_APPLY_JOURNAL_SCHEMA_VERSION = "astrabridge-agentic-update-apply-journal-v1"
AGENTIC_UPDATE_ROLLBACK_RESULT_SCHEMA_VERSION = "astrabridge-agentic-update-rollback-result-v1"
SAFE_APPLY_RISK_CLASSES = {"docs_only", "metadata_only"}
APPLY_TRACK_PROVIDER_METADATA = "provider_metadata"
APPLY_TRACK_CAPABILITY_ROUTES = "capability_routes"
APPLY_TRACK_EXECUTION_ROUTES = "execution_routes"
SUPPORTED_METADATA_CHANGE_TYPES = {
    "added_model",
    "changed_context_window",
    "changed_pricing",
    "changed_default_model",
    "changed_recommended_hint",
    "changed_default_reasoning",
    "deprecated_model",
    "undeprecated_model",
}
SUPPORTED_CAPABILITY_ROUTE_CHANGE_TYPES = {
    "set_capability_route",
    "remove_capability_route",
}
SUPPORTED_EXECUTION_ROUTE_CHANGE_TYPES = set(ROUTE_PROMOTION_CHANGE_TYPES)


def apply_journaled_proposal(
    *,
    workspace_root: str | Path,
    run_id: str,
    proposal: dict[str, Any],
    approval: dict[str, Any],
    router_config_snapshot: dict[str, Any] | None = None,
    generated_catalog_snapshot: dict[str, Any] | None = None,
    isolated_state_root: str | Path | None = None,
    allow_execution_route_changes: bool = False,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    layout = ensure_agentic_update_run_layout(workspace, run_id)
    validated_proposal = validate_update_proposal(proposal)
    _validate_manual_approval(approval)
    track_plan = _plan_supported_apply_tracks(validated_proposal, allow_execution_route_changes=allow_execution_route_changes)
    _validate_track_scoped_risk(
        validated_proposal,
        track_plan,
        allow_execution_route_changes=allow_execution_route_changes,
    )
    _validate_proposal_rollback_contract(validated_proposal)

    state_root = _resolve_isolated_state_root(workspace, run_id, isolated_state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    apply_id = new_id("metadata-apply")
    backup_root = validate_agentic_update_artifact_path(workspace, run_id, Path("rollback") / "backups" / apply_id)
    backup_root.mkdir(parents=True, exist_ok=True)

    router_path = state_root / "router_config.json"
    models_lock_path = state_root / "model_catalog" / "generated" / "models.lock.json"
    sources_lock_path = state_root / "model_catalog" / "generated" / "sources.lock.json"

    router_before = _read_or_seed_router_config(router_path, router_config_snapshot)
    models_lock_before, sources_lock_before = _read_or_seed_catalog_locks(models_lock_path, sources_lock_path, generated_catalog_snapshot)

    router_backup = backup_root / "router_config.before.json"
    models_backup = backup_root / "models.lock.before.json"
    sources_backup = backup_root / "sources.lock.before.json"
    write_json(router_backup, router_before)
    write_json(models_backup, models_lock_before)
    write_json(sources_backup, sources_lock_before)

    journal_path = Path(layout["files"]["apply_journal"])
    track_states_before = _track_state_snapshots(router_before, models_lock_before, sources_lock_before)
    journal = _initialize_apply_journal(
        run_id=run_id,
        apply_id=apply_id,
        proposal=validated_proposal,
        approval=approval,
        track_plan=track_plan,
        track_states_before=track_states_before,
    )
    _write_apply_journal(journal_path, journal)
    _advance_apply_journal(journal, journal_path, stage="backups_written")

    router_after = deepcopy(router_before)
    models_lock_after = deepcopy(models_lock_before)
    applied_changes: list[dict[str, Any]] = []
    route_applied_events: list[dict[str, Any]] = []
    try:
        if track_plan[APPLY_TRACK_PROVIDER_METADATA]:
            metadata_changes = _apply_metadata_changes(router_after, models_lock_after, validated_proposal)
            for change in metadata_changes:
                change["track_id"] = APPLY_TRACK_PROVIDER_METADATA
            applied_changes.extend(metadata_changes)
            _advance_apply_track(
                journal,
                journal_path,
                track_id=APPLY_TRACK_PROVIDER_METADATA,
                stage="applied",
            )
        if track_plan[APPLY_TRACK_CAPABILITY_ROUTES]:
            route_changes = _apply_capability_route_changes(router_after, validated_proposal)
            for change in route_changes:
                change["track_id"] = APPLY_TRACK_CAPABILITY_ROUTES
            applied_changes.extend(route_changes)
            _advance_apply_track(
                journal,
                journal_path,
                track_id=APPLY_TRACK_CAPABILITY_ROUTES,
                stage="applied",
            )
        if track_plan[APPLY_TRACK_EXECUTION_ROUTES]:
            route_changes, route_applied_events = _apply_execution_route_changes(router_after, validated_proposal)
            for change in route_changes:
                change["track_id"] = APPLY_TRACK_EXECUTION_ROUTES
            applied_changes.extend(route_changes)
            _advance_apply_track(
                journal,
                journal_path,
                track_id=APPLY_TRACK_EXECUTION_ROUTES,
                stage="applied",
            )
        write_json(router_path, router_after)
        write_json(models_lock_path, models_lock_after)
        write_json(sources_lock_path, sources_lock_before)

        track_states_after = _track_state_snapshots(router_after, models_lock_after, sources_lock_before)
        health_verdicts = _evaluate_track_health(
            proposal=validated_proposal,
            track_plan=track_plan,
            router_after=router_after,
            models_lock_after=models_lock_after,
        )
        for track_id, verdict in health_verdicts.items():
            _finalize_apply_track(
                journal,
                journal_path,
                track_id=track_id,
                staged_digest=_json_sha256(track_states_after[track_id]),
                health_verdict=verdict,
                changed_paths=_track_changed_paths(
                    track_id,
                    router_path=router_path,
                    models_lock_path=models_lock_path,
                    sources_lock_path=sources_lock_path,
                    workspace=workspace,
                ),
            )
        failing_tracks = [track_id for track_id, verdict in health_verdicts.items() if verdict != "pass"]
        if failing_tracks:
            raise ValueError(
                "Apply health verification failed for tracks: " + ", ".join(sorted(failing_tracks))
            )
    except Exception:
        _restore_state_from_backups(
            router_path=router_path,
            models_lock_path=models_lock_path,
            sources_lock_path=sources_lock_path,
            router_backup=router_backup,
            models_backup=models_backup,
            sources_backup=sources_backup,
        )
        _rollback_apply_journal(journal, journal_path)
        raise

    rollback_manifest = _build_apply_rollback_manifest(
        workspace=workspace,
        run_id=run_id,
        run_contract=validated_proposal["run_contract"],
        apply_id=apply_id,
        router_path=router_path,
        models_lock_path=models_lock_path,
        sources_lock_path=sources_lock_path,
        router_backup=router_backup,
        models_backup=models_backup,
        sources_backup=sources_backup,
        has_execution_route_changes=bool(track_plan[APPLY_TRACK_EXECUTION_ROUTES]),
    )
    rollback_manifest_path = Path(layout["files"]["rollback_manifest"])
    write_json(rollback_manifest_path, rollback_manifest)

    route_apply_ledger_path: Path | None = None
    if track_plan[APPLY_TRACK_EXECUTION_ROUTES]:
        route_apply_ledger_path = Path(layout["files"]["route_promotion_apply_ledger"])
        route_ledger = route_promotion_apply_ledger(
            run_id=run_id,
            records=route_promotion_records_from_proposal(validated_proposal, only_diff_changes=True),
            applied_events=route_applied_events,
        )
        assert_secret_free_agentic_update_payload(route_ledger, label="agentic_update_route_promotion_apply_ledger")
        write_json(route_apply_ledger_path, route_ledger)

    for track_id in track_plan:
        if not track_plan[track_id]:
            continue
        _commit_apply_track(
            journal,
            journal_path,
            track_id=track_id,
            rollback_target=_track_rollback_target(
                track_id,
                rollback_manifest_path=rollback_manifest_path,
                workspace=workspace,
                run_id=run_id,
                router_backup=router_backup,
                models_backup=models_backup,
                sources_backup=sources_backup,
            ),
        )
    journal["status"] = "committed"
    journal["completed_at"] = now_iso()
    _write_apply_journal(journal_path, journal)

    manifest_status = (
        "applied_metadata_only"
        if track_plan[APPLY_TRACK_PROVIDER_METADATA]
        and not track_plan[APPLY_TRACK_CAPABILITY_ROUTES]
        and not track_plan[APPLY_TRACK_EXECUTION_ROUTES]
        else "applied_route_promotion"
        if track_plan[APPLY_TRACK_EXECUTION_ROUTES]
        and not track_plan[APPLY_TRACK_PROVIDER_METADATA]
        and not track_plan[APPLY_TRACK_CAPABILITY_ROUTES]
        else "applied_track_updates"
    )
    documented_metadata_staged = any(
        _documented_metadata_change_is_safe(validated_proposal, change)
        for change in list(dict(validated_proposal.get("diff") or {}).get("changes") or [])
        if isinstance(change, dict)
    )
    documented_record_count = len(
        [
            record
            for record in route_promotion_records_from_proposal(validated_proposal)
            if str(record.get("action") or "") == "document"
        ]
    )
    manifest = {
        "schema_version": AGENTIC_UPDATE_APPLY_MANIFEST_SCHEMA_VERSION,
        "apply_id": apply_id,
        "run_id": run_id,
        "mode": "isolated_apply",
        "status": manifest_status,
        "applied_at": now_iso(),
        "approval": {
            "approved": True,
            "approved_by": str(approval.get("approved_by") or "manual_review").strip(),
            "approved_at": str(approval.get("approved_at") or now_iso()).strip(),
            "approval_note": str(approval.get("approval_note") or "").strip(),
        },
        "risk_class": validated_proposal["diff"].get("risk_class"),
        "isolated_state_root": str(state_root),
        "changed_paths": sorted(
            {
                *(
                    _track_changed_paths(
                        APPLY_TRACK_PROVIDER_METADATA,
                        router_path=router_path,
                        models_lock_path=models_lock_path,
                        sources_lock_path=sources_lock_path,
                        workspace=workspace,
                    )
                    if track_plan[APPLY_TRACK_PROVIDER_METADATA]
                    else []
                ),
                *(
                    _track_changed_paths(
                        APPLY_TRACK_CAPABILITY_ROUTES,
                        router_path=router_path,
                        models_lock_path=models_lock_path,
                        sources_lock_path=sources_lock_path,
                        workspace=workspace,
                    )
                    if track_plan[APPLY_TRACK_CAPABILITY_ROUTES]
                    else []
                ),
                *(
                    _track_changed_paths(
                        APPLY_TRACK_EXECUTION_ROUTES,
                        router_path=router_path,
                        models_lock_path=models_lock_path,
                        sources_lock_path=sources_lock_path,
                        workspace=workspace,
                    )
                    if track_plan[APPLY_TRACK_EXECUTION_ROUTES]
                    else []
                ),
            }
        ),
        "track_ids": [track_id for track_id, changes in track_plan.items() if changes],
        "journal_path": str(journal_path),
        "touched": {
            "router_config": str(router_path),
            "generated_models_lock": str(models_lock_path),
            "generated_sources_lock": str(sources_lock_path),
        },
        "applied_changes": applied_changes,
        "before_summary": _state_summary(router_before, models_lock_before),
        "after_summary": _state_summary(router_after, models_lock_after),
        "tracks": [
            _journal_track_summary(track)
            for track in list(journal.get("tracks") or [])
            if str(track.get("track_id") or "").strip()
        ],
        "rollback_manifest_path": str(rollback_manifest_path),
        "route_promotion": {
            "apply_ledger_path": str(route_apply_ledger_path) if route_apply_ledger_path else None,
            "metadata_preserved": True,
            "record_count": len(route_applied_events),
            "documented_record_count": documented_record_count,
            "authority_changed": bool(route_applied_events),
        },
        "backup_paths": {
            "router_config": str(router_backup),
            "generated_models_lock": str(models_backup),
            "generated_sources_lock": str(sources_backup),
        },
        "warnings": ["documented_metadata_staged_without_execution_route_authority"] if documented_metadata_staged else [],
    }
    assert_secret_free_agentic_update_payload(manifest, label="agentic_update_apply_manifest")
    write_json(Path(layout["files"]["apply_manifest"]), manifest)
    return manifest


def apply_metadata_only_proposal(
    *,
    workspace_root: str | Path,
    run_id: str,
    proposal: dict[str, Any],
    approval: dict[str, Any],
    router_config_snapshot: dict[str, Any] | None = None,
    generated_catalog_snapshot: dict[str, Any] | None = None,
    isolated_state_root: str | Path | None = None,
) -> dict[str, Any]:
    return apply_journaled_proposal(
        workspace_root=workspace_root,
        run_id=run_id,
        proposal=proposal,
        approval=approval,
        router_config_snapshot=router_config_snapshot,
        generated_catalog_snapshot=generated_catalog_snapshot,
        isolated_state_root=isolated_state_root,
    )


def apply_execution_route_promotion_proposal(
    *,
    workspace_root: str | Path,
    run_id: str,
    proposal: dict[str, Any],
    approval: dict[str, Any],
    router_config_snapshot: dict[str, Any] | None = None,
    generated_catalog_snapshot: dict[str, Any] | None = None,
    isolated_state_root: str | Path | None = None,
) -> dict[str, Any]:
    """Apply an explicitly gated route lifecycle proposal in isolated state.

    Unlike metadata-only apply, this path verifies the route-promotion gates
    and then re-binds the proof to the current endpoint and adapter before any
    evidence is persisted.  It never treats documentation as authority.
    """

    return apply_journaled_proposal(
        workspace_root=workspace_root,
        run_id=run_id,
        proposal=proposal,
        approval=approval,
        router_config_snapshot=router_config_snapshot,
        generated_catalog_snapshot=generated_catalog_snapshot,
        isolated_state_root=isolated_state_root,
        allow_execution_route_changes=True,
    )


def rollback_metadata_apply(
    *,
    workspace_root: str | Path,
    run_id: str,
    apply_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    layout = ensure_agentic_update_run_layout(workspace, run_id)
    manifest_path = _resolve_apply_manifest_path(workspace, run_id, apply_manifest_path or layout["file_relative_paths"]["apply_manifest"])
    manifest = read_json(manifest_path, {})
    if not isinstance(manifest, dict) or manifest.get("schema_version") != AGENTIC_UPDATE_APPLY_MANIFEST_SCHEMA_VERSION:
        raise ValueError("A valid agentic update apply manifest is required for rollback.")
    rollback_manifest_path = Path(str(manifest.get("rollback_manifest_path") or layout["files"]["rollback_manifest"]))
    rollback_manifest = validate_rollback_manifest(read_json(rollback_manifest_path, {}), workspace_root=workspace)
    restored_paths: list[str] = []
    updated_steps: list[dict[str, Any]] = []
    for step in rollback_manifest["steps"]:
        updated = dict(step)
        backup_path = validate_agentic_update_artifact_path(workspace, run_id, step.get("backup_path"))
        restore_path = resolve_under(workspace, str(step.get("workspace_path") or ""))
        if not backup_path.exists():
            updated["status"] = "failed"
            updated["error"] = f"Missing backup: {step.get('backup_path')}"
            updated_steps.append(updated)
            raise FileNotFoundError(str(backup_path))
        restore_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(backup_path, restore_path)
        updated["status"] = "applied"
        updated["restored_at"] = now_iso()
        restored_paths.append(_workspace_relative(workspace, restore_path))
        updated_steps.append(updated)
    rollback_manifest["steps"] = updated_steps
    write_json(rollback_manifest_path, rollback_manifest)
    result_path = validate_agentic_update_artifact_path(workspace, run_id, "rollback/rollback-result.json")
    result = {
        "schema_version": AGENTIC_UPDATE_ROLLBACK_RESULT_SCHEMA_VERSION,
        "run_id": run_id,
        "apply_id": manifest.get("apply_id"),
        "status": "rolled_back",
        "rolled_back_at": now_iso(),
        "restored_paths": restored_paths,
        "rollback_manifest_path": str(rollback_manifest_path),
        "apply_manifest_path": str(manifest_path),
        "evidence_paths": [
            "apply/apply-manifest.json",
            "rollback/rollback-manifest.json",
            "rollback/rollback-result.json",
        ],
    }
    if APPLY_TRACK_EXECUTION_ROUTES in set(manifest.get("track_ids") or []):
        ledger_path = Path(layout["files"]["route_promotion_apply_ledger"])
        ledger = read_json(ledger_path, {}) if ledger_path.exists() else {}
        route_rollback = route_promotion_rollback_record(
            run_id=run_id,
            apply_id=str(manifest.get("apply_id") or "") or None,
            ledger=ledger if isinstance(ledger, dict) else None,
        )
        rollback_record_path = Path(layout["files"]["route_promotion_rollback"])
        assert_secret_free_agentic_update_payload(route_rollback, label="agentic_update_route_promotion_rollback")
        write_json(rollback_record_path, route_rollback)
        result["route_promotion"] = {
            "rollback_record_path": str(rollback_record_path),
            "metadata_preserved": True,
            "record_ids": list(route_rollback.get("record_ids") or []),
        }
    assert_secret_free_agentic_update_payload(result, label="agentic_update_rollback_result")
    write_json(result_path, result)
    return result


def _validate_manual_approval(approval: dict[str, Any] | None) -> None:
    if not isinstance(approval, dict) or approval.get("approved") is not True:
        raise ValueError("Manual approval is required before applying an agentic update proposal.")
    if not str(approval.get("approved_by") or "").strip():
        raise ValueError("approval.approved_by is required.")


def _validate_track_scoped_risk(
    proposal: dict[str, Any],
    track_plan: dict[str, list[dict[str, Any]]],
    *,
    allow_execution_route_changes: bool,
) -> None:
    diff = dict(proposal.get("diff") or {})
    risk = str(diff.get("risk_class") or "blocked_manual_review")
    non_route_tracks = any(
        track_plan[track_id]
        for track_id in (APPLY_TRACK_PROVIDER_METADATA, APPLY_TRACK_CAPABILITY_ROUTES)
    )
    non_route_changes = [
        dict(change)
        for change in list(diff.get("changes") or [])
        if isinstance(change, dict) and str(change.get("change_type") or "") not in SUPPORTED_EXECUTION_ROUTE_CHANGE_TYPES
    ]
    documented_metadata_only = bool(non_route_changes) and all(
        _documented_metadata_change_is_safe(proposal, change) for change in non_route_changes
    )
    if (
        non_route_tracks
        and risk not in SAFE_APPLY_RISK_CLASSES
        and not track_plan[APPLY_TRACK_EXECUTION_ROUTES]
        and not documented_metadata_only
    ):
        raise ValueError(f"Metadata-only apply refuses proposal risk_class={risk}.")
    for change in list(diff.get("changes") or []):
        if not isinstance(change, dict):
            raise ValueError("Proposal diff changes must be objects.")
        change_risk = str(change.get("risk_class") or risk)
        change_type = str(change.get("change_type") or "")
        if change_type in SUPPORTED_EXECUTION_ROUTE_CHANGE_TYPES:
            if not allow_execution_route_changes:
                raise ValueError("Metadata-only apply does not support execution-route lifecycle changes.")
            continue
        if change_risk not in SAFE_APPLY_RISK_CLASSES and not _documented_metadata_change_is_safe(proposal, change):
            raise ValueError(f"Metadata-only apply refuses change risk_class={change_risk}.")
        if change_type not in SUPPORTED_METADATA_CHANGE_TYPES and change_type not in SUPPORTED_CAPABILITY_ROUTE_CHANGE_TYPES:
            raise ValueError(f"Metadata-only apply does not support change_type={change_type}.")
    if track_plan[APPLY_TRACK_EXECUTION_ROUTES]:
        validate_route_promotion_apply(
            proposal,
            run_contract=dict(proposal.get("run_contract") or {}),
        )
    if not any(track_plan.values()):
        raise ValueError("No supported provider metadata, capability-route, or execution-route changes are available for apply.")


def _documented_metadata_change_is_safe(proposal: dict[str, Any], change: dict[str, Any]) -> bool:
    """Permit factual catalog intake without treating it as route authority.

    New documented models may carry long-context, modality, or reasoning facts
    that still need provider smoke before use.  The catalog record is safe to
    stage because the metadata writer never stores route evidence and marks
    context as a UI hint.  Existing-model behavior remains conservative.
    """

    if str(change.get("change_type") or "") != "added_model":
        return False
    details = dict(change.get("details") or {})
    if details.get("documented_metadata_apply_eligible") is not True:
        return False
    if str(details.get("documented_metadata_apply_risk") or "") != str(change.get("risk_class") or ""):
        return False
    model_id = str(change.get("model_id") or change.get("target") or "").strip()
    if not model_id:
        return False
    try:
        records = route_promotion_records_from_proposal(proposal)
    except (TypeError, ValueError):
        return False
    return any(
        str(record.get("model_id") or "") == model_id
        and str(record.get("action") or "") == "document"
        and str(record.get("target_state") or "") == "documented"
        and not record.get("route_evidence")
        for record in records
    )


def _validate_proposal_rollback_contract(proposal: dict[str, Any]) -> None:
    rollback_manifest = proposal.get("rollback_manifest")
    if not isinstance(rollback_manifest, dict):
        raise ValueError("Proposal rollback_manifest is required before apply.")
    if rollback_manifest.get("reversible") is not True:
        raise ValueError("Proposal rollback_manifest must be reversible before apply.")


def _resolve_isolated_state_root(workspace: Path, run_id: str, value: str | Path | None) -> Path:
    if value in (None, ""):
        return validate_agentic_update_artifact_path(workspace, run_id, "tmp/isolated-apply-state")
    candidate = Path(value)
    if candidate.is_absolute():
        raise SecurityError("isolated_state_root must be workspace-relative.")
    if not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise SecurityError(f"Invalid isolated_state_root: {value}")
    return resolve_under(workspace, candidate)


def _resolve_apply_manifest_path(workspace: Path, run_id: str, value: str | Path) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return resolve_under(workspace, candidate.relative_to(workspace))
    return validate_agentic_update_artifact_path(workspace, run_id, candidate)


def _read_or_seed_router_config(path: Path, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if path.exists():
        return _sanitize_router_config_snapshot(read_json(path, {}))
    payload = _sanitize_router_config_snapshot(snapshot or {})
    write_json(path, payload)
    return payload


def _read_or_seed_catalog_locks(
    models_lock_path: Path,
    sources_lock_path: Path,
    snapshot: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if models_lock_path.exists() and sources_lock_path.exists():
        return read_json(models_lock_path, {}), read_json(sources_lock_path, {})
    locks = _generated_catalog_locks(snapshot)
    write_json(models_lock_path, locks["models_lock"])
    write_json(sources_lock_path, locks["sources_lock"])
    return locks["models_lock"], locks["sources_lock"]


def _sanitize_router_config_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    providers = []
    for provider in list((snapshot or {}).get("providers") or []):
        if not isinstance(provider, dict):
            continue
        item = dict(provider)
        item["auth_key_ref"] = None
        providers.append(item)
    return {
        "providers": providers,
        "models": [dict(item) for item in list((snapshot or {}).get("models") or []) if isinstance(item, dict)],
        "reasoning": dict((snapshot or {}).get("reasoning") or {"global_effort": "high", "provider_overrides": {}, "model_overrides": {}, "native_parameter_overrides": {}}),
        "capability_routes": dict((snapshot or {}).get("capability_routes") or {}),
    }


def _generated_catalog_locks(snapshot: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if isinstance(snapshot, dict) and "models_lock" in snapshot and "sources_lock" in snapshot:
        return {
            "models_lock": deepcopy(snapshot["models_lock"]),
            "sources_lock": deepcopy(snapshot["sources_lock"]),
        }
    generated = current_generated_catalog()
    return {
        "models_lock": {
            "schema_version": generated.catalog_version or GENERATED_CATALOG_SCHEMA,
            "generated_at": generated.generated_at or now_iso(),
            "models": [dict(item) for item in generated.models],
        },
        "sources_lock": {
            "schema_version": GENERATED_CATALOG_SCHEMA,
            "generated_at": generated.generated_at or now_iso(),
            "sources": [dict(item) for item in generated.sources],
            "fetch_status": [],
        },
    }


def _apply_metadata_changes(
    router_payload: dict[str, Any],
    models_lock: dict[str, Any],
    proposal: dict[str, Any],
) -> list[dict[str, Any]]:
    router_models = {str(item.get("id") or ""): dict(item) for item in router_payload.get("models") or [] if isinstance(item, dict)}
    catalog_models = {str(item.get("id") or ""): dict(item) for item in models_lock.get("models") or [] if isinstance(item, dict)}
    candidate_index = _candidate_index(proposal)
    applied: list[dict[str, Any]] = []
    for change in list(proposal["diff"].get("changes") or []):
        change_type = str(change.get("change_type") or "")
        if change_type not in SUPPORTED_METADATA_CHANGE_TYPES:
            continue
        model_id = str(change.get("model_id") or change.get("target") or "").strip()
        if not model_id:
            raise ValueError("Metadata apply changes require model_id or target.")
        if change_type == "added_model":
            candidate = candidate_index.get(model_id)
            model = _model_record_from_candidate(change, candidate)
            router_models[model_id] = {**router_models.get(model_id, {}), **model}
            catalog_models[model_id] = {**catalog_models.get(model_id, {}), **model}
        else:
            if model_id not in router_models and model_id not in catalog_models:
                raise ValueError(f"Cannot apply {change_type} for missing model: {model_id}")
            current = {**catalog_models.get(model_id, {}), **router_models.get(model_id, {})}
            updated = _apply_single_model_change(current, change)
            router_models[model_id] = updated
            catalog_models[model_id] = updated
        applied.append(
            {
                "change_id": change.get("change_id"),
                "change_type": change_type,
                "model_id": model_id,
                "risk_class": change.get("risk_class"),
            }
        )
    router_payload["models"] = sorted(router_models.values(), key=lambda item: str(item.get("id")))
    models_lock["models"] = sorted(catalog_models.values(), key=lambda item: str(item.get("id")))
    models_lock.setdefault("schema_version", GENERATED_CATALOG_SCHEMA)
    models_lock["generated_at"] = now_iso()
    return applied


def _apply_capability_route_changes(
    router_payload: dict[str, Any],
    proposal: dict[str, Any],
) -> list[dict[str, Any]]:
    routes = {
        str(capability_id): dict(record)
        for capability_id, record in dict(router_payload.get("capability_routes") or {}).items()
        if isinstance(record, dict)
    }
    applied: list[dict[str, Any]] = []
    for change in list(proposal["diff"].get("changes") or []):
        change_type = str(change.get("change_type") or "")
        if change_type not in SUPPORTED_CAPABILITY_ROUTE_CHANGE_TYPES:
            continue
        capability_id = str(change.get("capability_id") or change.get("target") or "").strip()
        if not capability_id:
            raise ValueError("Capability-route apply changes require capability_id or target.")
        if change_type == "set_capability_route":
            route_record = dict(change.get("details") or {}).get("route_record")
            if not isinstance(route_record, dict):
                raise ValueError(f"Capability-route apply requires details.route_record for {capability_id}.")
            routes[capability_id] = normalize_capability_route_record(capability_id, route_record)
        elif change_type == "remove_capability_route":
            routes.pop(capability_id, None)
        applied.append(
            {
                "change_id": change.get("change_id"),
                "change_type": change_type,
                "capability_id": capability_id,
                "risk_class": change.get("risk_class"),
            }
        )
    router_payload["capability_routes"] = {
        capability_id: routes[capability_id]
        for capability_id in sorted(routes)
    }
    return applied


def _apply_execution_route_changes(
    router_payload: dict[str, Any],
    proposal: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = route_promotion_records_from_proposal(proposal, only_diff_changes=True)
    models = {
        str(item.get("id") or ""): dict(item)
        for item in list(router_payload.get("models") or [])
        if isinstance(item, dict)
    }
    providers = {
        str(item.get("id") or item.get("provider_id") or ""): dict(item)
        for item in list(router_payload.get("providers") or [])
        if isinstance(item, dict)
    }
    change_by_record_id = {
        str(dict(change.get("details") or {}).get("route_promotion_record_id") or ""): dict(change)
        for change in list(dict(proposal.get("diff") or {}).get("changes") or [])
        if isinstance(change, dict) and str(change.get("change_type") or "") in SUPPORTED_EXECUTION_ROUTE_CHANGE_TYPES
    }
    applied_changes: list[dict[str, Any]] = []
    applied_events: list[dict[str, Any]] = []
    for record in records:
        model_id = str(record.get("model_id") or "").strip()
        model = dict(models.get(model_id) or {})
        if not model:
            raise ValueError(f"Execution-route apply requires an existing model: {model_id}")
        provider_id = str(record.get("provider_id") or model.get("provider") or "").strip()
        provider = dict(providers.get(provider_id) or {})
        if not provider:
            raise ValueError(f"Execution-route apply requires configured provider: {provider_id}")
        previous_evidence = deepcopy(model.get("execution_route_evidence")) if isinstance(model.get("execution_route_evidence"), dict) else None
        stored_evidence = route_promotion_storage_for_model(record, model=model, provider=provider)
        if stored_evidence is None:
            model.pop("execution_route_evidence", None)
        else:
            model["execution_route_evidence"] = stored_evidence
        model["updated_at"] = now_iso()
        models[model_id] = model
        change = change_by_record_id.get(str(record.get("record_id") or ""), {})
        applied_changes.append(
            {
                "change_id": change.get("change_id"),
                "change_type": change.get("change_type"),
                "model_id": model_id,
                "risk_class": change.get("risk_class"),
                "route_promotion_record_id": record.get("record_id"),
            }
        )
        applied_events.append(
            {
                "record_id": record.get("record_id"),
                "action": record.get("action"),
                "model_id": model_id,
                "previous_state": record.get("previous_state"),
                "target_state": record.get("target_state"),
                "route_subject": deepcopy(record.get("route_subject") or {}),
                "previous_evidence": previous_evidence,
                "applied_evidence": stored_evidence,
            }
        )
    router_payload["models"] = sorted(models.values(), key=lambda item: str(item.get("id") or ""))
    return applied_changes, applied_events


def _candidate_index(proposal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in list((proposal.get("discovery_result") or {}).get("findings") or []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or "").strip()
        if model_id:
            index[model_id] = dict(item)
    return index


def _model_record_from_candidate(change: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any]:
    model_id = str(change.get("model_id") or change.get("target") or "").strip()
    provider_id = str(change.get("provider_id") or (candidate or {}).get("provider_id") or model_id.split("/", 1)[0]).strip()
    native_model = str((candidate or {}).get("native_model") or (model_id.split("/", 1)[1] if "/" in model_id else model_id)).strip()
    metadata = dict((candidate or {}).get("candidate_metadata") or dict((change.get("details") or {}).get("candidate_metadata") or {}))
    pricing = dict(metadata.get("pricing") or {})
    source_refs = [dict(item) for item in list((candidate or {}).get("source_refs") or change.get("source_refs") or []) if isinstance(item, dict)]
    return {
        "id": model_id,
        "provider": provider_id,
        "native_model": native_model,
        "display_name": str((candidate or {}).get("display_name") or native_model),
        "enabled": True,
        "advertised_context_window": int(metadata.get("advertised_context_window") or 128000),
        "ui_context_hint_only": True,
        "adapter_profile": "default",
        "input_modalities": [str(item) for item in list(metadata.get("input_modalities") or ["text"])],
        "supported_reasoning_levels": [str(item) for item in list(metadata.get("supported_reasoning_levels") or [])],
        "default_reasoning_level": metadata.get("default_reasoning_level"),
        "pricing_currency": str(pricing.get("currency") or ""),
        "pricing_input_per_mtok": pricing.get("input_per_mtok"),
        "pricing_output_per_mtok": pricing.get("output_per_mtok"),
        "pricing_cached_input_per_mtok": pricing.get("cached_input_per_mtok"),
        "pricing_status": "official_docs" if source_refs else "unknown",
        "deprecated": bool(metadata.get("deprecated", False)),
        "deprecated_after": metadata.get("deprecated_after"),
        "default_for_provider": bool(metadata.get("default_for_provider", False)),
        "recommended": bool(metadata.get("recommended", False)),
        "confidence": metadata.get("confidence") or "low",
        "source_urls": [str(item.get("source_url") or item.get("url") or "") for item in source_refs if str(item.get("source_url") or item.get("url") or "").strip()],
        "source_status": "official_docs" if source_refs else "proposed",
        "source_provenance": _source_provenance(source_refs, provider_id),
        "catalog_version": GENERATED_CATALOG_SCHEMA,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _apply_single_model_change(model: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    updated = dict(model)
    details = dict(change.get("details") or {})
    change_type = str(change.get("change_type") or "")
    candidate_value = details.get("candidate")
    if change_type == "changed_context_window":
        updated["advertised_context_window"] = int(candidate_value)
    elif change_type == "changed_pricing":
        pricing = dict(candidate_value or {})
        updated["pricing_input_per_mtok"] = pricing.get("input_per_mtok")
        updated["pricing_output_per_mtok"] = pricing.get("output_per_mtok")
        updated["pricing_cached_input_per_mtok"] = pricing.get("cached_input_per_mtok")
        updated["pricing_currency"] = str(pricing.get("currency") or updated.get("pricing_currency") or "")
        updated["pricing_status"] = "official_docs"
    elif change_type == "changed_default_model":
        updated["default_for_provider"] = bool(candidate_value)
    elif change_type == "changed_recommended_hint":
        updated["recommended"] = bool(candidate_value)
    elif change_type == "changed_default_reasoning":
        updated["default_reasoning_level"] = candidate_value
    elif change_type == "deprecated_model":
        updated["deprecated"] = True
        candidate = dict(candidate_value or {}) if isinstance(candidate_value, dict) else {}
        updated["deprecated_after"] = candidate.get("deprecated_after") or details.get("deprecated_after") or updated.get("deprecated_after")
    elif change_type == "undeprecated_model":
        updated["deprecated"] = False
        updated["deprecated_after"] = None
    else:
        raise ValueError(f"Unsupported metadata change type: {change_type}")
    updated["updated_at"] = now_iso()
    return updated


def _source_provenance(source_refs: list[dict[str, Any]], provider_id: str) -> dict[str, Any]:
    first = source_refs[0] if source_refs else {}
    return {
        "provider_id": provider_id,
        "source_url": first.get("source_url") or first.get("url"),
        "source_id": first.get("source_id"),
        "content_hash": first.get("content_hash"),
        "source_status": "official_docs" if source_refs else "proposed",
        "trust_level": first.get("trust_level") or "official" if source_refs else "manual_review",
    }


def _build_apply_rollback_manifest(
    *,
    workspace: Path,
    run_id: str,
    run_contract: dict[str, Any],
    apply_id: str,
    router_path: Path,
    models_lock_path: Path,
    sources_lock_path: Path,
    router_backup: Path,
    models_backup: Path,
    sources_backup: Path,
    has_execution_route_changes: bool,
) -> dict[str, Any]:
    manifest = rollback_manifest_template(run_id, run_contract)
    records = [
        ("router_config", "restore-router-config", router_path, router_backup),
        ("generated_catalog_locks", "restore-models-lock", models_lock_path, models_backup),
        ("generated_catalog_locks", "restore-sources-lock", sources_lock_path, sources_backup),
    ]
    for kind, step_id, restore_path, backup_path in records:
        record = {
            "target_id": step_id,
            "workspace_path": _workspace_relative(workspace, restore_path),
            "backup_path": _run_relative(workspace, run_id, backup_path),
            "apply_id": apply_id,
        }
        manifest["rollback_targets"][kind].append(record)
        manifest["steps"].append(
            {
                "step_id": step_id,
                "target_kind": kind,
                "action": "restore_file_from_backup",
                "status": "ready",
                "workspace_path": record["workspace_path"],
                "backup_path": record["backup_path"],
            }
        )
    if has_execution_route_changes:
        manifest["rollback_targets"]["execution_routes"].append(
            {
                "target_id": "restore-execution-route-evidence",
                "workspace_path": _workspace_relative(workspace, router_path),
                "backup_path": _run_relative(workspace, run_id, router_backup),
                "apply_id": apply_id,
                "rollback_step_id": "restore-router-config",
            }
        )
    manifest["evidence_paths"] = [
        "apply/apply-manifest.json",
        "rollback/rollback-manifest.json",
        _run_relative(workspace, run_id, router_backup),
        _run_relative(workspace, run_id, models_backup),
        _run_relative(workspace, run_id, sources_backup),
    ]
    if has_execution_route_changes:
        manifest["evidence_paths"].append("route-promotion/route-promotion-apply-ledger.json")
    return validate_rollback_manifest(manifest, workspace_root=workspace)


def _plan_supported_apply_tracks(
    proposal: dict[str, Any],
    *,
    allow_execution_route_changes: bool,
) -> dict[str, list[dict[str, Any]]]:
    tracks = {
        APPLY_TRACK_PROVIDER_METADATA: [],
        APPLY_TRACK_CAPABILITY_ROUTES: [],
        APPLY_TRACK_EXECUTION_ROUTES: [],
    }
    for change in list(dict(proposal.get("diff") or {}).get("changes") or []):
        if not isinstance(change, dict):
            raise ValueError("Proposal diff changes must be objects.")
        change_type = str(change.get("change_type") or "")
        if change_type in SUPPORTED_METADATA_CHANGE_TYPES:
            tracks[APPLY_TRACK_PROVIDER_METADATA].append(dict(change))
            continue
        if change_type in SUPPORTED_CAPABILITY_ROUTE_CHANGE_TYPES:
            tracks[APPLY_TRACK_CAPABILITY_ROUTES].append(dict(change))
            continue
        if change_type in SUPPORTED_EXECUTION_ROUTE_CHANGE_TYPES:
            if not allow_execution_route_changes:
                raise ValueError("Apply only supports execution-route changes through apply_execution_route_promotion_proposal.")
            tracks[APPLY_TRACK_EXECUTION_ROUTES].append(dict(change))
            continue
        raise ValueError(
            "Apply only supports provider metadata, capability-route, and explicit execution-route changes; "
            f"unsupported change_type={change_type or '<missing>'}."
        )
    return tracks


def _track_state_snapshots(
    router_payload: dict[str, Any],
    models_lock: dict[str, Any],
    sources_lock: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        APPLY_TRACK_PROVIDER_METADATA: {
            "router_models": [dict(item) for item in list(router_payload.get("models") or []) if isinstance(item, dict)],
            "catalog_models": [dict(item) for item in list(models_lock.get("models") or []) if isinstance(item, dict)],
            "sources_lock": dict(sources_lock or {}),
        },
        APPLY_TRACK_CAPABILITY_ROUTES: {
            "capability_routes": dict(router_payload.get("capability_routes") or {}),
        },
        APPLY_TRACK_EXECUTION_ROUTES: {
            "route_evidence": [
                {
                    "model_id": item.get("id"),
                    "execution_route_evidence": deepcopy(item.get("execution_route_evidence"))
                    if isinstance(item.get("execution_route_evidence"), dict)
                    else None,
                }
                for item in list(router_payload.get("models") or [])
                if isinstance(item, dict)
            ],
        },
    }


def _initialize_apply_journal(
    *,
    run_id: str,
    apply_id: str,
    proposal: dict[str, Any],
    approval: dict[str, Any],
    track_plan: dict[str, list[dict[str, Any]]],
    track_states_before: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    trust_decision = _approval_trust_decision(approval)
    tracks: list[dict[str, Any]] = []
    for track_id, changes in track_plan.items():
        if not changes:
            continue
        tracks.append(
            {
                "track_id": track_id,
                "status": "running",
                "source_digest": _json_sha256(track_states_before[track_id]),
                "staged_digest": None,
                "trust_decision": trust_decision,
                "health_verdict": "not_run",
                "changed_paths": [],
                "change_ids": [str(change.get("change_id") or "") for change in changes if str(change.get("change_id") or "").strip()],
                "rollback_target": {},
                "history": [
                    {
                        "stage": "initialized",
                        "at": now_iso(),
                    }
                ],
            }
        )
    return {
        "schema_version": AGENTIC_UPDATE_APPLY_JOURNAL_SCHEMA_VERSION,
        "apply_id": apply_id,
        "run_id": run_id,
        "status": "running",
        "started_at": now_iso(),
        "completed_at": None,
        "risk_class": str(dict(proposal.get("diff") or {}).get("risk_class") or ""),
        "tracks": tracks,
        "warnings": [],
    }


def _write_apply_journal(path: Path, journal: dict[str, Any]) -> None:
    write_json(path, journal)


def _advance_apply_journal(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    stage: str,
) -> None:
    for track in list(journal.get("tracks") or []):
        history = list(track.get("history") or [])
        history.append({"stage": stage, "at": now_iso()})
        track["history"] = history
    _write_apply_journal(journal_path, journal)


def _advance_apply_track(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    track_id: str,
    stage: str,
) -> None:
    track = _journal_track(journal, track_id)
    history = list(track.get("history") or [])
    history.append({"stage": stage, "at": now_iso()})
    track["history"] = history
    _write_apply_journal(journal_path, journal)


def _finalize_apply_track(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    track_id: str,
    staged_digest: str,
    health_verdict: str,
    changed_paths: list[str],
) -> None:
    track = _journal_track(journal, track_id)
    track["staged_digest"] = staged_digest
    track["health_verdict"] = health_verdict
    track["changed_paths"] = list(changed_paths)
    history = list(track.get("history") or [])
    history.append({"stage": "healthcheck_completed", "at": now_iso(), "verdict": health_verdict})
    track["history"] = history
    _write_apply_journal(journal_path, journal)


def _commit_apply_track(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    track_id: str,
    rollback_target: dict[str, Any],
) -> None:
    track = _journal_track(journal, track_id)
    track["status"] = "committed"
    track["rollback_target"] = dict(rollback_target)
    history = list(track.get("history") or [])
    history.append({"stage": "committed", "at": now_iso()})
    track["history"] = history
    _write_apply_journal(journal_path, journal)


def _rollback_apply_journal(journal: dict[str, Any], journal_path: Path) -> None:
    journal["status"] = "rolled_back"
    journal["completed_at"] = now_iso()
    for track in list(journal.get("tracks") or []):
        if str(track.get("status") or "") == "committed":
            continue
        track["status"] = "rolled_back"
        history = list(track.get("history") or [])
        history.append({"stage": "rolled_back", "at": now_iso()})
        track["history"] = history
    _write_apply_journal(journal_path, journal)


def _journal_track(journal: dict[str, Any], track_id: str) -> dict[str, Any]:
    for track in list(journal.get("tracks") or []):
        if str(track.get("track_id") or "") == track_id:
            return track
    raise ValueError(f"Missing apply journal track: {track_id}")


def _evaluate_track_health(
    *,
    proposal: dict[str, Any],
    track_plan: dict[str, list[dict[str, Any]]],
    router_after: dict[str, Any],
    models_lock_after: dict[str, Any],
) -> dict[str, str]:
    verdicts: dict[str, str] = {}
    if track_plan[APPLY_TRACK_PROVIDER_METADATA]:
        verdicts[APPLY_TRACK_PROVIDER_METADATA] = (
            "pass" if _metadata_changes_match_expected(router_after, models_lock_after, proposal) else "fail"
        )
    if track_plan[APPLY_TRACK_CAPABILITY_ROUTES]:
        verdicts[APPLY_TRACK_CAPABILITY_ROUTES] = (
            "pass" if _capability_route_changes_match_expected(router_after, proposal) else "fail"
        )
    if track_plan[APPLY_TRACK_EXECUTION_ROUTES]:
        verdicts[APPLY_TRACK_EXECUTION_ROUTES] = (
            "pass" if _execution_route_changes_match_expected(router_after, proposal) else "fail"
        )
    return verdicts


def _metadata_changes_match_expected(
    router_payload: dict[str, Any],
    models_lock: dict[str, Any],
    proposal: dict[str, Any],
) -> bool:
    router_models = {str(item.get("id") or ""): dict(item) for item in list(router_payload.get("models") or []) if isinstance(item, dict)}
    catalog_models = {str(item.get("id") or ""): dict(item) for item in list(models_lock.get("models") or []) if isinstance(item, dict)}
    for change in list(dict(proposal.get("diff") or {}).get("changes") or []):
        change_type = str(change.get("change_type") or "")
        if change_type not in SUPPORTED_METADATA_CHANGE_TYPES:
            continue
        model_id = str(change.get("model_id") or change.get("target") or "").strip()
        if not model_id:
            return False
        router_model = router_models.get(model_id)
        catalog_model = catalog_models.get(model_id)
        if router_model is None or catalog_model is None:
            return False
        if change_type == "added_model":
            continue
        if change_type == "changed_context_window":
            expected = int(dict(change.get("details") or {}).get("candidate"))
            if int(router_model.get("advertised_context_window") or 0) != expected:
                return False
            if int(catalog_model.get("advertised_context_window") or 0) != expected:
                return False
        elif change_type == "changed_pricing":
            pricing = dict(dict(change.get("details") or {}).get("candidate") or {})
            if router_model.get("pricing_input_per_mtok") != pricing.get("input_per_mtok"):
                return False
            if catalog_model.get("pricing_output_per_mtok") != pricing.get("output_per_mtok"):
                return False
        elif change_type == "changed_default_model":
            expected = bool(dict(change.get("details") or {}).get("candidate"))
            if bool(router_model.get("default_for_provider")) != expected:
                return False
            if bool(catalog_model.get("default_for_provider")) != expected:
                return False
        elif change_type == "changed_recommended_hint":
            expected = bool(dict(change.get("details") or {}).get("candidate"))
            if bool(router_model.get("recommended")) != expected:
                return False
            if bool(catalog_model.get("recommended")) != expected:
                return False
        elif change_type == "changed_default_reasoning":
            expected = dict(change.get("details") or {}).get("candidate")
            if router_model.get("default_reasoning_level") != expected:
                return False
            if catalog_model.get("default_reasoning_level") != expected:
                return False
        elif change_type == "deprecated_model":
            if not bool(router_model.get("deprecated")) or not bool(catalog_model.get("deprecated")):
                return False
        elif change_type == "undeprecated_model":
            if bool(router_model.get("deprecated")) or bool(catalog_model.get("deprecated")):
                return False
    return True


def _capability_route_changes_match_expected(
    router_payload: dict[str, Any],
    proposal: dict[str, Any],
) -> bool:
    routes = {
        str(capability_id): dict(record)
        for capability_id, record in dict(router_payload.get("capability_routes") or {}).items()
        if isinstance(record, dict)
    }
    for change in list(dict(proposal.get("diff") or {}).get("changes") or []):
        change_type = str(change.get("change_type") or "")
        if change_type not in SUPPORTED_CAPABILITY_ROUTE_CHANGE_TYPES:
            continue
        capability_id = str(change.get("capability_id") or change.get("target") or "").strip()
        if not capability_id:
            return False
        if change_type == "remove_capability_route":
            if capability_id in routes:
                return False
            continue
        route_record = dict(change.get("details") or {}).get("route_record")
        if not isinstance(route_record, dict):
            return False
        expected = normalize_capability_route_record(capability_id, route_record)
        actual = dict(routes.get(capability_id) or {})
        if not actual:
            return False
        for field in ("capability_id", "mode", "provider_id", "model"):
            if actual.get(field) != expected.get(field):
                return False
        if not str(actual.get("updated_at") or "").strip():
            return False
    return True


def _execution_route_changes_match_expected(
    router_payload: dict[str, Any],
    proposal: dict[str, Any],
) -> bool:
    models = {
        str(item.get("id") or ""): dict(item)
        for item in list(router_payload.get("models") or [])
        if isinstance(item, dict)
    }
    try:
        records = route_promotion_records_from_proposal(proposal, only_diff_changes=True)
    except (TypeError, ValueError):
        return False
    for record in records:
        model = models.get(str(record.get("model_id") or ""))
        if not model:
            return False
        target_state = str(record.get("target_state") or "documented")
        actual = model.get("execution_route_evidence")
        if target_state == "documented":
            if isinstance(actual, dict):
                return False
            continue
        expected = dict(record.get("route_evidence") or {})
        if not isinstance(actual, dict) or not expected:
            return False
        for field in (
            "schema_version",
            "state",
            "subject",
            "source_provenance",
            "evidence_refs",
            "validation_scope",
            "verified_at",
            "expires_at",
        ):
            if actual.get(field) != expected.get(field):
                return False
    return True


def _track_changed_paths(
    track_id: str,
    *,
    router_path: Path,
    models_lock_path: Path,
    sources_lock_path: Path,
    workspace: Path,
) -> list[str]:
    if track_id == APPLY_TRACK_PROVIDER_METADATA:
        return [
            _workspace_relative(workspace, router_path),
            _workspace_relative(workspace, models_lock_path),
            _workspace_relative(workspace, sources_lock_path),
        ]
    if track_id == APPLY_TRACK_CAPABILITY_ROUTES:
        return [_workspace_relative(workspace, router_path)]
    if track_id == APPLY_TRACK_EXECUTION_ROUTES:
        return [_workspace_relative(workspace, router_path)]
    raise ValueError(f"Unsupported apply track: {track_id}")


def _track_rollback_target(
    track_id: str,
    *,
    rollback_manifest_path: Path,
    workspace: Path,
    run_id: str,
    router_backup: Path,
    models_backup: Path,
    sources_backup: Path,
) -> dict[str, Any]:
    if track_id == APPLY_TRACK_PROVIDER_METADATA:
        backup_paths = {
            "router_config": _run_relative(workspace, run_id, router_backup),
            "generated_models_lock": _run_relative(workspace, run_id, models_backup),
            "generated_sources_lock": _run_relative(workspace, run_id, sources_backup),
        }
    elif track_id == APPLY_TRACK_CAPABILITY_ROUTES:
        backup_paths = {
            "router_config": _run_relative(workspace, run_id, router_backup),
        }
    elif track_id == APPLY_TRACK_EXECUTION_ROUTES:
        backup_paths = {
            "router_config": _run_relative(workspace, run_id, router_backup),
            "route_promotion_ledger": "route-promotion/route-promotion-apply-ledger.json",
        }
    else:
        raise ValueError(f"Unsupported apply track: {track_id}")
    return {
        "rollback_manifest_path": str(rollback_manifest_path),
        "backup_paths": backup_paths,
    }


def _approval_trust_decision(approval: dict[str, Any]) -> str:
    approved_by = str(approval.get("approved_by") or "").strip()
    return f"manual_review_approved:{approved_by or 'unknown'}"


def _restore_state_from_backups(
    *,
    router_path: Path,
    models_lock_path: Path,
    sources_lock_path: Path,
    router_backup: Path,
    models_backup: Path,
    sources_backup: Path,
) -> None:
    for backup_path, restore_path in (
        (router_backup, router_path),
        (models_backup, models_lock_path),
        (sources_backup, sources_lock_path),
    ):
        restore_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(backup_path, restore_path)


def _journal_track_summary(track: dict[str, Any]) -> dict[str, Any]:
    return {
        "track_id": track.get("track_id"),
        "status": track.get("status"),
        "source_digest": track.get("source_digest"),
        "staged_digest": track.get("staged_digest"),
        "trust_decision": track.get("trust_decision"),
        "health_verdict": track.get("health_verdict"),
        "changed_paths": list(track.get("changed_paths") or []),
        "change_ids": list(track.get("change_ids") or []),
        "rollback_target": dict(track.get("rollback_target") or {}),
    }


def _json_sha256(payload: Any) -> str:
    canonical = deepcopy(payload)
    json_bytes = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(json_bytes).hexdigest()


def _state_summary(router_payload: dict[str, Any], models_lock: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_count": len(list(router_payload.get("providers") or [])),
        "router_model_count": len(list(router_payload.get("models") or [])),
        "catalog_model_count": len(list(models_lock.get("models") or [])),
    }


def _workspace_relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace).as_posix()


def _run_relative(workspace: Path, run_id: str, path: Path) -> str:
    run_root = Path(ensure_agentic_update_run_layout(workspace, run_id)["run_root"])
    return path.resolve().relative_to(run_root).as_posix()
