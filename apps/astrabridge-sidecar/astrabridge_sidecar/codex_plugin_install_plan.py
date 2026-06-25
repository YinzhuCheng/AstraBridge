from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .common import now_iso
from .codex_plugin_skill_registry_contract import (
    PluginRegistryRecord,
    PluginSkillRegistrySnapshot,
    RegistrySourceCatalog,
)
from .security import redact_sensitive


PLUGIN_INSTALL_PLAN_SCHEMA_VERSION = "astrabridge-plugin-install-plan-v1"
_FILE_LIST_LIMIT = 24


def build_plugin_install_plan(
    *,
    registry_snapshot: dict[str, Any] | PluginSkillRegistrySnapshot,
    plugin_id: str,
    source_catalog_id: str | None,
    codex_home: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    snapshot = PluginSkillRegistrySnapshot.from_any(registry_snapshot)
    plugin = _select_plugin(snapshot, plugin_id=plugin_id, source_catalog_id=source_catalog_id)
    catalog = next((item for item in snapshot.source_catalogs if item.source_catalog_id == plugin.source_catalog_id), None)
    if catalog is None:
        raise ValueError(f"Plugin {plugin.plugin_id} references missing source_catalog_id {plugin.source_catalog_id}.")

    action, status, reason = _plan_action(plugin)
    source_root = _existing_dir(_candidate_roots(plugin, catalog))
    target_root = _target_root(plugin, codex_home)

    source_files, source_file_count = _list_files(source_root)
    existing_target_files, existing_target_file_count = _list_files(target_root)
    planned_write_files = _planned_write_files(source_files, target_root)

    warnings = [warning.to_dict() for warning in plugin.compatibility_warnings]
    errors: list[dict[str, Any]] = []
    notes = ["planning_only", "apply_step_not_executed"]

    if action in {"install", "update"}:
        support_error = _unsupported_source_error(plugin, catalog, source_root=source_root, target_root=target_root)
        if support_error is not None:
            action = "unsupported"
            status = "unsupported"
            reason = str(support_error.get("code") or "plugin_source_unsupported")
            errors.append(support_error)
        elif source_file_count == 0:
            action = "unsupported"
            status = "unsupported"
            reason = "plugin_source_empty"
            errors.append(
                {
                    "schema_version": "astrabridge-plugin-skill-warning-v1",
                    "code": "plugin-source-empty",
                    "severity": "error",
                    "message": "Plugin source root is empty. Rebuild or repoint the local plugin source before applying changes.",
                    "field": "source_path",
                }
            )
    elif action == "unsupported":
        errors.append(
            {
                "schema_version": "astrabridge-plugin-skill-warning-v1",
                "code": "plugin-install-status-unsupported",
                "severity": "error",
                "message": f"Plugin install status `{plugin.install_status}` cannot be planned for mutation yet.",
                "field": "install_status",
            }
        )

    declared_skill_names = sorted(
        {
            *plugin.keywords,
            *(skill.skill_name for skill in snapshot.skills if skill.owner_plugin_id == plugin.plugin_id),
        }
    )
    detected_skill_names = sorted(skill.skill_name for skill in snapshot.skills if skill.owner_plugin_id == plugin.plugin_id)

    rollback_snapshot = _rollback_snapshot_plan(
        plugin=plugin,
        codex_home=codex_home,
        target_root=target_root,
        existing_target_files=existing_target_files,
        existing_target_file_count=existing_target_file_count,
    )

    payload = {
        "schema_version": PLUGIN_INSTALL_PLAN_SCHEMA_VERSION,
        "generated_at": generated_at or now_iso(),
        "action": action,
        "status": status,
        "reason": reason,
        "plugin": {
            "record_id": plugin.record_id,
            "plugin_id": plugin.plugin_id,
            "display_name": plugin.display_name,
            "source_catalog_id": plugin.source_catalog_id,
            "install_status": plugin.install_status,
            "enablement_status": plugin.enablement_status,
            "compatibility_status": plugin.compatibility_status,
        },
        "source": {
            "source_catalog_id": catalog.source_catalog_id,
            "kind": catalog.kind,
            "display_name": catalog.display_name,
            "source_path": str(source_root) if source_root is not None else catalog.source_path,
            "source_url": catalog.source_url or plugin.provenance.source_url,
            "catalog_path": catalog.catalog_path,
            "writable": catalog.writable,
        },
        "versions": {
            "current_version": plugin.installed_version or plugin.version,
            "target_version": plugin.available_version or plugin.version,
            "installed_version": plugin.installed_version,
            "available_version": plugin.available_version,
        },
        "permission_hints": list(plugin.permission_hints),
        "declared_app_ids": list(plugin.declared_app_ids),
        "mcp_changes": {
            "declared_servers": list(plugin.declared_mcp_servers),
        },
        "skill_changes": {
            "declared_skills": declared_skill_names,
            "detected_installed_skills": detected_skill_names,
        },
        "files": {
            "source_root": str(source_root) if source_root is not None else None,
            "target_root": str(target_root),
            "source_file_count": source_file_count,
            "existing_target_file_count": existing_target_file_count,
            "planned_write_count": len(planned_write_files) if action in {"install", "update"} else 0,
            "source_files": source_files,
            "existing_target_files": existing_target_files,
            "planned_write_files": planned_write_files if action in {"install", "update"} else [],
        },
        "rollback_snapshot": rollback_snapshot,
        "warnings": warnings,
        "errors": errors,
        "notes": notes,
    }
    return redact_sensitive(payload)


def _select_plugin(
    snapshot: PluginSkillRegistrySnapshot,
    *,
    plugin_id: str,
    source_catalog_id: str | None,
) -> PluginRegistryRecord:
    candidates = [record for record in snapshot.plugins if record.plugin_id == str(plugin_id or "").strip()]
    if source_catalog_id:
        candidates = [record for record in candidates if record.source_catalog_id == source_catalog_id]
    if not candidates:
        raise ValueError(f"Plugin `{plugin_id}` was not found in the current registry snapshot.")
    candidates.sort(
        key=lambda record: (
            record.install_status != "installed",
            record.install_status != "update_available",
            record.display_name.lower(),
        )
    )
    return candidates[0]


def _plan_action(plugin: PluginRegistryRecord) -> tuple[str, str, str]:
    if plugin.install_status == "available":
        return "install", "ready", "install_available_plugin"
    if plugin.install_status == "update_available":
        return "update", "ready", "update_available_plugin"
    if plugin.install_status == "installed":
        return "noop", "ready", "already_current"
    return "unsupported", "unsupported", f"install_status_{plugin.install_status}"


def _candidate_roots(plugin: PluginRegistryRecord, catalog: RegistrySourceCatalog) -> list[Path]:
    candidates: list[Path] = []
    for value in (
        catalog.source_path,
        plugin.provenance.source_path,
        plugin.install_root,
        plugin.provenance.manifest_path,
    ):
        normalized = _normalize_plugin_root(value)
        if normalized is not None and normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _normalize_plugin_root(value: str | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        candidate = Path(text).expanduser().resolve()
    except Exception:
        return None
    if candidate.is_file():
        if candidate.name == "plugin.json" and candidate.parent.name == ".codex-plugin":
            return candidate.parent.parent
        return candidate.parent
    return candidate


def _existing_dir(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _target_root(plugin: PluginRegistryRecord, codex_home: Path) -> Path:
    install_root = _normalize_plugin_root(plugin.install_root)
    if install_root is not None:
        return install_root
    return (codex_home / "plugins" / plugin.plugin_id).resolve()


def _unsupported_source_error(
    plugin: PluginRegistryRecord,
    catalog: RegistrySourceCatalog,
    *,
    source_root: Path | None,
    target_root: Path,
) -> dict[str, Any] | None:
    if catalog.kind in {"official", "curated"}:
        return {
            "schema_version": "astrabridge-plugin-skill-warning-v1",
            "code": "plugin-source-unsupported",
            "severity": "error",
            "message": "Remote or curated plugin sources are not plannable yet. Mirror the plugin into an AstraBridge-managed local source before applying changes.",
            "field": "source_catalog_id",
        }
    if source_root is None:
        return {
            "schema_version": "astrabridge-plugin-skill-warning-v1",
            "code": "plugin-source-missing",
            "severity": "error",
            "message": "No readable local plugin source root was found. Repoint the plugin to a local source before applying changes.",
            "field": "source_path",
        }
    if source_root == target_root and plugin.install_status == "update_available":
        return {
            "schema_version": "astrabridge-plugin-skill-warning-v1",
            "code": "plugin-update-source-missing",
            "severity": "error",
            "message": "Update planning needs a local source root separate from the installed plugin root so changed files can be reviewed before apply.",
            "field": "source_path",
        }
    return None


def _list_files(root: Path | None) -> tuple[list[dict[str, Any]], int]:
    if root is None or not root.exists() or not root.is_dir():
        return [], 0
    files = sorted(path for path in root.rglob("*") if path.is_file())
    entries: list[dict[str, Any]] = []
    for path in files[:_FILE_LIST_LIMIT]:
        try:
            relative = path.relative_to(root).as_posix()
            size = path.stat().st_size
        except Exception:
            continue
        entries.append(
            {
                "relative_path": relative,
                "path": str(path),
                "bytes": size,
            }
        )
    return entries, len(files)


def _planned_write_files(source_files: list[dict[str, Any]], target_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in source_files:
        relative_path = str(item.get("relative_path") or "").strip()
        if not relative_path:
            continue
        entries.append(
            {
                "relative_path": relative_path,
                "path": str((target_root / relative_path).resolve()),
                "bytes": item.get("bytes"),
            }
        )
    return entries


def _rollback_snapshot_plan(
    *,
    plugin: PluginRegistryRecord,
    codex_home: Path,
    target_root: Path,
    existing_target_files: list[dict[str, Any]],
    existing_target_file_count: int,
) -> dict[str, Any]:
    snapshot_id = _snapshot_id(plugin.plugin_id, target_root)
    snapshot_root = (codex_home / "plugin-rollbacks" / snapshot_id).resolve()
    return {
        "status": "planned",
        "snapshot_id": snapshot_id,
        "snapshot_root": str(snapshot_root),
        "captured_file_count": existing_target_file_count,
        "captured_files": existing_target_files,
        "notes": ["created_on_apply_only", "captures_existing_target_before_mutation"],
    }


def _snapshot_id(plugin_id: str, target_root: Path) -> str:
    digest = hashlib.sha256(f"{plugin_id}:{target_root}".encode("utf-8")).hexdigest()[:12]
    return f"plugin-{plugin_id}-{digest}"
