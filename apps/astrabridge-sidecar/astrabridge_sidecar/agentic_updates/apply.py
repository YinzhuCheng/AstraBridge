from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
from typing import Any

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


AGENTIC_UPDATE_APPLY_MANIFEST_SCHEMA_VERSION = "astrabridge-agentic-update-apply-manifest-v1"
AGENTIC_UPDATE_ROLLBACK_RESULT_SCHEMA_VERSION = "astrabridge-agentic-update-rollback-result-v1"
SAFE_APPLY_RISK_CLASSES = {"docs_only", "metadata_only"}
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
    workspace = Path(workspace_root).resolve()
    layout = ensure_agentic_update_run_layout(workspace, run_id)
    validated_proposal = validate_update_proposal(proposal)
    _validate_manual_approval(approval)
    _validate_metadata_only_risk(validated_proposal)
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

    router_after = deepcopy(router_before)
    models_lock_after = deepcopy(models_lock_before)
    applied_changes = _apply_metadata_changes(router_after, models_lock_after, validated_proposal)
    write_json(router_path, router_after)
    write_json(models_lock_path, models_lock_after)
    write_json(sources_lock_path, sources_lock_before)

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
    )
    rollback_manifest_path = Path(layout["files"]["rollback_manifest"])
    write_json(rollback_manifest_path, rollback_manifest)

    manifest = {
        "schema_version": AGENTIC_UPDATE_APPLY_MANIFEST_SCHEMA_VERSION,
        "apply_id": apply_id,
        "run_id": run_id,
        "mode": "isolated_apply",
        "status": "applied_metadata_only",
        "applied_at": now_iso(),
        "approval": {
            "approved": True,
            "approved_by": str(approval.get("approved_by") or "manual_review").strip(),
            "approved_at": str(approval.get("approved_at") or now_iso()).strip(),
            "approval_note": str(approval.get("approval_note") or "").strip(),
        },
        "risk_class": validated_proposal["diff"].get("risk_class"),
        "isolated_state_root": str(state_root),
        "changed_paths": [
            _workspace_relative(workspace, router_path),
            _workspace_relative(workspace, models_lock_path),
            _workspace_relative(workspace, sources_lock_path),
        ],
        "touched": {
            "router_config": str(router_path),
            "generated_models_lock": str(models_lock_path),
            "generated_sources_lock": str(sources_lock_path),
        },
        "applied_changes": applied_changes,
        "before_summary": _state_summary(router_before, models_lock_before),
        "after_summary": _state_summary(router_after, models_lock_after),
        "rollback_manifest_path": str(rollback_manifest_path),
        "backup_paths": {
            "router_config": str(router_backup),
            "generated_models_lock": str(models_backup),
            "generated_sources_lock": str(sources_backup),
        },
        "warnings": [],
    }
    assert_secret_free_agentic_update_payload(manifest, label="agentic_update_apply_manifest")
    write_json(Path(layout["files"]["apply_manifest"]), manifest)
    return manifest


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
    assert_secret_free_agentic_update_payload(result, label="agentic_update_rollback_result")
    write_json(result_path, result)
    return result


def _validate_manual_approval(approval: dict[str, Any] | None) -> None:
    if not isinstance(approval, dict) or approval.get("approved") is not True:
        raise ValueError("Manual approval is required before applying an agentic update proposal.")
    if not str(approval.get("approved_by") or "").strip():
        raise ValueError("approval.approved_by is required.")


def _validate_metadata_only_risk(proposal: dict[str, Any]) -> None:
    diff = dict(proposal.get("diff") or {})
    risk = str(diff.get("risk_class") or "blocked_manual_review")
    if risk not in SAFE_APPLY_RISK_CLASSES:
        raise ValueError(f"Metadata-only apply refuses proposal risk_class={risk}.")
    for change in list(diff.get("changes") or []):
        if not isinstance(change, dict):
            raise ValueError("Proposal diff changes must be objects.")
        change_risk = str(change.get("risk_class") or risk)
        change_type = str(change.get("change_type") or "")
        if change_risk not in SAFE_APPLY_RISK_CLASSES:
            raise ValueError(f"Metadata-only apply refuses change risk_class={change_risk}.")
        if change_type not in SUPPORTED_METADATA_CHANGE_TYPES:
            raise ValueError(f"Metadata-only apply does not support change_type={change_type}.")


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
    manifest["evidence_paths"] = [
        "apply/apply-manifest.json",
        "rollback/rollback-manifest.json",
        _run_relative(workspace, run_id, router_backup),
        _run_relative(workspace, run_id, models_backup),
        _run_relative(workspace, run_id, sources_backup),
    ]
    return validate_rollback_manifest(manifest, workspace_root=workspace)


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
