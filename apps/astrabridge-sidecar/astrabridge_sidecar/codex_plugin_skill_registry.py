from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .common import now_iso
from .codex_plugin_skill_icon_pipeline import resolve_plugin_icon_metadata, resolve_skill_icon_metadata
from .codex_plugin_skill_registry_contract import normalize_plugin_skill_registry_snapshot


def build_plugin_skill_registry_snapshot(
    *,
    plugin_report: dict[str, Any] | None,
    skill_report: dict[str, Any] | None,
    runtime_roots: dict[str, Any] | None,
    search_roots: list[Path] | None,
    generated_at: str | None = None,
    extra_notes: list[str] | None = None,
) -> dict[str, Any]:
    plugin_payload = (plugin_report or {}).get("plugin") if isinstance(plugin_report, dict) else {}
    plugin_payload = plugin_payload if isinstance(plugin_payload, dict) else {}
    skill_payload = (skill_report or {}).get("skill") if isinstance(skill_report, dict) else {}
    skill_payload = skill_payload if isinstance(skill_payload, dict) else {}

    runtime_root_paths = _runtime_root_paths(runtime_roots)
    search_root_paths = _unique_paths(search_roots or [])
    source_catalogs: dict[str, dict[str, Any]] = {}
    notes: list[str] = []
    notes.extend(_status_notes("plugin", plugin_payload, ("list_status", "installed_status", "read_status", "marketplace_status", "manifest_fallback_status")))
    notes.extend(_status_notes("skill", skill_payload, ("list_status", "extra_roots_status", "config_write_status", "change_notification_status")))
    notes.extend(f"plugin_note:{text}" for text in _clean_string_list(plugin_payload.get("notes")))
    notes.extend(f"skill_note:{text}" for text in _clean_string_list(skill_payload.get("notes")))
    notes.extend(f"plugin_warning:{text}" for text in _clean_string_list((plugin_report or {}).get("known_warnings")))
    notes.extend(f"skill_warning:{text}" for text in _clean_string_list((skill_report or {}).get("known_warnings")))
    notes.extend(_clean_string_list(extra_notes))

    duplicate_plugin_ids: list[str] = []
    plugin_records: list[dict[str, Any]] = []
    plugin_catalog_by_id: dict[str, str] = {}
    for plugin in _dedupe_plugins(list(plugin_payload.get("discovered_plugins") or []), duplicate_plugin_ids):
        if not isinstance(plugin, dict):
            continue
        source_catalog_id = _ensure_plugin_source_catalog(
            source_catalogs=source_catalogs,
            plugin=plugin,
            runtime_root_paths=runtime_root_paths,
            search_root_paths=search_root_paths,
        )
        record = _plugin_registry_record(plugin, source_catalog_id=source_catalog_id)
        source_catalog = source_catalogs.get(source_catalog_id)
        icon, icon_warnings, icon_notes = resolve_plugin_icon_metadata(
            plugin=plugin,
            source_catalog=source_catalog,
            runtime_roots=runtime_roots,
            search_roots=search_root_paths,
        )
        if icon is not None:
            record["icon"] = icon
        if icon_warnings:
            record["compatibility_warnings"] = [*(record.get("compatibility_warnings") or []), *icon_warnings]
        if icon_notes:
            record["notes"] = [*(record.get("notes") or []), *icon_notes]
        plugin_records.append(record)
        plugin_catalog_by_id[str(record.get("plugin_id") or "")] = source_catalog_id
    if duplicate_plugin_ids:
        notes.append(f"plugin_duplicate_ids:{', '.join(sorted(set(duplicate_plugin_ids)))}")

    duplicate_skill_names = _clean_string_list(skill_payload.get("duplicate_skill_names"))
    malformed_skill_paths = {_clean_text(item) for item in list(skill_payload.get("malformed_skill_paths") or []) if _clean_text(item)}
    missing_description_paths = {_clean_text(item) for item in list(skill_payload.get("missing_description_paths") or []) if _clean_text(item)}
    if duplicate_skill_names:
        notes.append(f"skill_duplicate_names:{', '.join(duplicate_skill_names)}")
    if malformed_skill_paths:
        notes.append(f"skill_malformed_paths:{len(malformed_skill_paths)}")
    if missing_description_paths:
        notes.append(f"skill_missing_descriptions:{len(missing_description_paths)}")

    skill_records: list[dict[str, Any]] = []
    seen_skill_record_ids: set[str] = set()
    for skill in list(skill_payload.get("discovered_skills") or []):
        if not isinstance(skill, dict):
            continue
        source_catalog_id = _resolve_skill_source_catalog(
            source_catalogs=source_catalogs,
            skill=skill,
            plugin_catalog_by_id=plugin_catalog_by_id,
            runtime_root_paths=runtime_root_paths,
            search_root_paths=search_root_paths,
        )
        record = _skill_registry_record(
            skill,
            source_catalog_id=source_catalog_id,
            duplicate_skill_names=set(duplicate_skill_names),
            malformed_skill_paths=malformed_skill_paths,
            missing_description_paths=missing_description_paths,
        )
        source_catalog = source_catalogs.get(source_catalog_id)
        icon, icon_warnings, icon_notes = resolve_skill_icon_metadata(
            skill=skill,
            source_catalog=source_catalog,
            runtime_roots=runtime_roots,
            search_roots=search_root_paths,
        )
        if icon is not None:
            record["icon"] = icon
        if icon_warnings:
            record["compatibility_warnings"] = [*(record.get("compatibility_warnings") or []), *icon_warnings]
        if icon_notes:
            record["notes"] = [*(record.get("notes") or []), *icon_notes]
        record_id = str(record.get("record_id") or "").strip()
        if not record_id or record_id in seen_skill_record_ids:
            continue
        seen_skill_record_ids.add(record_id)
        skill_records.append(record)

    snapshot = normalize_plugin_skill_registry_snapshot(
        {
            "schema_version": "astrabridge-plugin-skill-registry-v1",
            "generated_at": generated_at or now_iso(),
            "source_catalogs": list(source_catalogs.values()),
            "plugins": plugin_records,
            "skills": skill_records,
            "notes": _dedupe_preserve_order(notes),
        }
    )
    return snapshot.to_dict()


def _status_notes(prefix: str, payload: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    notes: list[str] = []
    for field in fields:
        value = _clean_text(payload.get(field) or "unknown")
        notes.append(f"{prefix}_{field}:{value}")
    return notes


def _dedupe_plugins(raw_plugins: list[Any], duplicate_plugin_ids: list[str]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in raw_plugins:
        if not isinstance(item, dict):
            continue
        plugin_id = _clean_text(item.get("plugin_id") or item.get("plugin_name") or item.get("name"))
        if not plugin_id:
            continue
        existing = by_id.get(plugin_id)
        if existing is None:
            by_id[plugin_id] = item
            continue
        duplicate_plugin_ids.append(plugin_id)
        if _plugin_score(item) > _plugin_score(existing):
            by_id[plugin_id] = item
    return sorted(by_id.values(), key=lambda item: str(item.get("plugin_id") or ""))


def _plugin_score(payload: dict[str, Any]) -> int:
    availability = _clean_text(payload.get("availability") or payload.get("install_status"))
    manifest_status = _clean_text(payload.get("manifest_status"))
    score = 0
    if availability == "installed":
        score += 8
    elif availability == "available":
        score += 5
    if manifest_status == "ok":
        score += 3
    elif manifest_status == "malformed":
        score -= 2
    if _clean_text(payload.get("description")):
        score += 2
    if bool(payload.get("enabled")):
        score += 1
    if _clean_text(payload.get("version")):
        score += 1
    return score


def _ensure_plugin_source_catalog(
    *,
    source_catalogs: dict[str, dict[str, Any]],
    plugin: dict[str, Any],
    runtime_root_paths: dict[str, Path],
    search_root_paths: list[Path],
) -> str:
    source_kind = _clean_text(plugin.get("source_kind") or "unknown")
    marketplace_name = _clean_text(plugin.get("marketplace_name"))
    marketplace_path = _clean_text(plugin.get("marketplace_path"))
    manifest_path = _clean_text(plugin.get("manifest_path"))
    root_path = _plugin_root_path(manifest_path)

    if source_kind == "remote_marketplace":
        kind = "official" if _looks_official_text(marketplace_name) else "curated"
        identity = marketplace_path or marketplace_name or _clean_text(plugin.get("plugin_id"))
        catalog_id = f"{kind}::marketplace::{_stable_id_fragment(identity)}"
        display_name = marketplace_name or ("Official marketplace" if kind == "official" else "Curated marketplace")
        source_catalogs.setdefault(
            catalog_id,
            {
                "source_catalog_id": catalog_id,
                "kind": kind,
                "display_name": display_name,
                "catalog_path": marketplace_path or None,
                "source_path": marketplace_path or None,
                "writable": False,
            },
        )
        return catalog_id

    if source_kind == "shared_remote":
        catalog_id = f"manual::shared-remote::{_stable_id_fragment(_clean_text(plugin.get('plugin_id')) or marketplace_name or 'shared-remote')}"
        source_catalogs.setdefault(
            catalog_id,
            {
                "source_catalog_id": catalog_id,
                "kind": "manual",
                "display_name": marketplace_name or "Manual shared plugin",
                "catalog_path": marketplace_path or None,
                "source_path": marketplace_path or root_path or None,
                "writable": True,
            },
        )
        return catalog_id

    resolved_kind = _path_kind(root_path or marketplace_path, runtime_root_paths=runtime_root_paths, search_root_paths=search_root_paths)
    identity = marketplace_path or root_path or _clean_text(plugin.get("plugin_id")) or "local"
    label = marketplace_name or Path(root_path or marketplace_path or identity).name or "Local plugin root"
    catalog_id = f"{resolved_kind}::plugin-root::{_stable_id_fragment(identity)}"
    source_catalogs.setdefault(
        catalog_id,
        {
            "source_catalog_id": catalog_id,
            "kind": resolved_kind,
            "display_name": label,
            "catalog_path": marketplace_path or None,
            "source_path": root_path or marketplace_path or None,
            "writable": resolved_kind in {"local", "project_local", "manual"},
        },
    )
    return catalog_id


def _resolve_skill_source_catalog(
    *,
    source_catalogs: dict[str, dict[str, Any]],
    skill: dict[str, Any],
    plugin_catalog_by_id: dict[str, str],
    runtime_root_paths: dict[str, Path],
    search_root_paths: list[Path],
) -> str:
    owner_plugin_id = _clean_text(skill.get("owner_plugin_id"))
    if owner_plugin_id and owner_plugin_id in plugin_catalog_by_id:
        return plugin_catalog_by_id[owner_plugin_id]
    source_kind = _clean_text(skill.get("source_kind"))
    path = _clean_text(skill.get("path"))
    if source_kind == "remote_catalog":
        catalog_id = "official::remote-skill-catalog"
        source_catalogs.setdefault(
            catalog_id,
            {
                "source_catalog_id": catalog_id,
                "kind": "official",
                "display_name": "Remote skill catalog",
                "writable": False,
            },
        )
        return catalog_id
    resolved_kind = "project_local" if source_kind == "project_root" else _path_kind(path, runtime_root_paths=runtime_root_paths, search_root_paths=search_root_paths)
    identity = path or owner_plugin_id or _clean_text(skill.get("skill_name")) or "skill-root"
    catalog_id = f"{resolved_kind}::skill-root::{_stable_id_fragment(identity)}"
    source_catalogs.setdefault(
        catalog_id,
        {
            "source_catalog_id": catalog_id,
            "kind": resolved_kind,
            "display_name": Path(path).parent.name if path else ("Project skill root" if resolved_kind == "project_local" else "Local skill root"),
            "source_path": path or None,
            "writable": resolved_kind in {"local", "project_local", "manual"},
        },
    )
    return catalog_id


def _plugin_registry_record(plugin: dict[str, Any], *, source_catalog_id: str) -> dict[str, Any]:
    manifest_status = _clean_text(plugin.get("manifest_status"))
    availability = _clean_text(plugin.get("availability"))
    source_kind = _clean_text(plugin.get("source_kind"))
    install_status = _plugin_install_status(availability=availability, manifest_status=manifest_status, plugin=plugin)
    warnings: list[dict[str, Any]] = []
    if manifest_status == "malformed":
        warnings.append(
            {
                "code": "plugin-manifest-malformed",
                "severity": "error",
                "message": "Plugin manifest could not be parsed.",
                "field": "manifest_path",
            }
        )
    elif manifest_status == "missing":
        warnings.append(
            {
                "code": "plugin-manifest-missing",
                "severity": "warning",
                "message": "Plugin marketplace entry points to a missing manifest.",
                "field": "manifest_path",
            }
        )
    compatibility_status = "compatible"
    if install_status == "incompatible":
        compatibility_status = "incompatible"
    elif install_status in {"malformed", "unavailable"} or warnings:
        compatibility_status = "warning"
    record = {
        "record_id": f"plugin::{_clean_text(plugin.get('plugin_id'))}::{_stable_id_fragment(source_catalog_id)}",
        "plugin_id": _clean_text(plugin.get("plugin_id")),
        "source_catalog_id": source_catalog_id,
        "display_name": _clean_text(plugin.get("display_name") or plugin.get("plugin_name") or plugin.get("plugin_id")),
        "install_status": install_status,
        "enablement_status": _plugin_enablement_status(plugin),
        "compatibility_status": compatibility_status,
        "version": _optional_text(plugin.get("version")),
        "installed_version": _optional_text(plugin.get("version")) if install_status == "installed" else None,
        "available_version": _optional_text(plugin.get("available_version") or plugin.get("version")) if install_status in {"available", "update_available"} else None,
        "description": _optional_text(plugin.get("description") or plugin.get("short_description")),
        "install_root": _plugin_root_path(_clean_text(plugin.get("manifest_path"))) if source_kind == "installed_root" else None,
        "keywords": _clean_string_list(plugin.get("skills_declared")),
        "declared_app_ids": _clean_string_list(plugin.get("apps") or plugin.get("apps_declared")),
        "declared_hook_keys": _clean_string_list(plugin.get("hooks")),
        "declared_mcp_servers": _clean_string_list(plugin.get("mcp_servers") or plugin.get("mcp_servers_declared")),
        "permission_hints": _plugin_permission_hints(plugin),
        "provenance": {
            "source_path": _plugin_root_path(_clean_text(plugin.get("manifest_path"))) or _optional_text(plugin.get("marketplace_path")),
            "manifest_path": _optional_text(plugin.get("manifest_path")),
            "checksum_algorithm": "sha256" if _optional_text(plugin.get("content_sha256")) else None,
            "checksum_value": _optional_text(plugin.get("content_sha256")),
        },
        "compatibility_warnings": warnings,
        "notes": _clean_string_list(
            [
                f"source_kind:{_clean_text(plugin.get('source_kind') or 'unknown')}",
                f"availability:{availability or 'unknown'}",
                f"manifest_status:{manifest_status or 'not_checked'}",
            ]
        ),
    }
    return {key: value for key, value in record.items() if not _is_empty_value(value)}


def _skill_registry_record(
    skill: dict[str, Any],
    *,
    source_catalog_id: str,
    duplicate_skill_names: set[str],
    malformed_skill_paths: set[str],
    missing_description_paths: set[str],
) -> dict[str, Any]:
    path = _clean_text(skill.get("path"))
    manifest_status = _clean_text(skill.get("manifest_status"))
    description_status = _clean_text(skill.get("description_status"))
    install_status = "malformed" if manifest_status == "malformed" or path in malformed_skill_paths else "installed"
    warnings: list[dict[str, Any]] = []
    if install_status == "malformed":
        warnings.append(
            {
                "code": "skill-manifest-malformed",
                "severity": "error",
                "message": "Skill manifest could not be parsed.",
                "field": "path",
            }
        )
    if path in missing_description_paths or description_status == "missing":
        warnings.append(
            {
                "code": "skill-description-missing",
                "severity": "warning",
                "message": "Skill manifest is missing a description.",
                "field": "description",
            }
        )
    skill_name = _clean_text(skill.get("skill_name"))
    if skill_name in duplicate_skill_names:
        warnings.append(
            {
                "code": "skill-duplicate-name",
                "severity": "warning",
                "message": "Duplicate skill name detected across discovered skill roots.",
                "field": "skill_name",
            }
        )
    compatibility_status = "warning" if warnings else "compatible"
    if install_status == "malformed":
        compatibility_status = "warning"
    record = {
        "record_id": f"skill::{skill_name}::{_stable_id_fragment(path or _clean_text(skill.get('owner_plugin_id')) or source_catalog_id)}",
        "skill_name": skill_name,
        "source_catalog_id": source_catalog_id,
        "display_name": _clean_text(skill.get("display_name") or skill_name),
        "install_status": install_status,
        "enablement_status": _skill_enablement_status(skill),
        "compatibility_status": compatibility_status,
        "owner_plugin_id": _optional_text(skill.get("owner_plugin_id")),
        "description": _optional_text(skill.get("description")),
        "owning_plugin_version": _optional_text(skill.get("version_hint")),
        "trigger_hints": _clean_string_list(skill.get("trigger_hints")),
        "permission_hints": _clean_string_list(skill.get("dependency_tools")),
        "provenance": {
            "source_path": path or None,
            "manifest_path": path or None,
            "checksum_algorithm": "sha256" if _optional_text(skill.get("content_sha256")) else None,
            "checksum_value": _optional_text(skill.get("content_sha256")),
        },
        "compatibility_warnings": warnings,
        "notes": _clean_string_list(
            [
                f"source_kind:{_clean_text(skill.get('source_kind') or 'unknown')}",
                f"manifest_status:{manifest_status or 'unknown'}",
                f"description_status:{description_status or 'unknown'}",
            ]
        ),
    }
    return {key: value for key, value in record.items() if not _is_empty_value(value)}


def _plugin_install_status(*, availability: str, manifest_status: str, plugin: dict[str, Any]) -> str:
    explicit = _clean_text(plugin.get("install_status"))
    if explicit in {"installed", "available", "update_available", "incompatible", "malformed", "unavailable", "unknown"}:
        return explicit
    if manifest_status == "malformed":
        return "malformed"
    if availability in {"installed", "available", "unavailable"}:
        return "unavailable" if availability == "unavailable" else availability
    if _optional_text(plugin.get("available_version")) and _optional_text(plugin.get("version")):
        return "update_available"
    return "unknown"


def _plugin_enablement_status(plugin: dict[str, Any]) -> str:
    explicit = _clean_text(plugin.get("enablement") or plugin.get("enablement_status"))
    if explicit in {"enabled", "disabled", "inherited", "blocked", "unknown"}:
        return explicit
    if "enabled" in plugin:
        return "enabled" if bool(plugin.get("enabled")) else "disabled"
    return "unknown"


def _skill_enablement_status(skill: dict[str, Any]) -> str:
    explicit = _clean_text(skill.get("enablement") or skill.get("enablement_status"))
    if explicit in {"enabled", "disabled", "inherited", "blocked", "unknown"}:
        return explicit
    if "enabled" in skill:
        return "enabled" if bool(skill.get("enabled")) else "disabled"
    return "unknown"


def _plugin_permission_hints(plugin: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    if _clean_string_list(plugin.get("mcp_servers") or plugin.get("mcp_servers_declared")):
        hints.append("declares_mcp_servers")
    if _clean_string_list(plugin.get("apps") or plugin.get("apps_declared")):
        hints.append("declares_apps")
    if _clean_string_list(plugin.get("skills") or plugin.get("skills_declared")):
        hints.append("declares_skills")
    return hints


def _runtime_root_paths(runtime_roots: dict[str, Any] | None) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for key, value in dict(runtime_roots or {}).items():
        text = _clean_text(value)
        if not text:
            continue
        try:
            roots[key] = Path(text).resolve()
        except Exception:
            continue
    return roots


def _path_kind(path_value: str | None, *, runtime_root_paths: dict[str, Path], search_root_paths: list[Path]) -> str:
    text = _clean_text(path_value)
    if not text:
        return "manual"
    try:
        candidate = Path(text).resolve()
    except Exception:
        return "manual"
    project_roots = [runtime_root_paths.get("project_runtime_root"), runtime_root_paths.get("workspace_runtime_cwd")]
    local_roots = [runtime_root_paths.get("codex_home_root"), *search_root_paths]
    for root in project_roots:
        if root and _is_relative_to(candidate, root):
            return "project_local"
    for root in local_roots:
        if root and _is_relative_to(candidate, root):
            return "local"
    return "manual"


def _plugin_root_path(manifest_path: str | None) -> str | None:
    text = _clean_text(manifest_path)
    if not text:
        return None
    try:
        return str(Path(text).resolve().parent.parent)
    except Exception:
        return None


def _looks_official_text(value: str | None) -> bool:
    text = _clean_text(value).lower()
    return any(token in text for token in ("official", "openai", "bundled", "codex"))


def _stable_id_fragment(value: str) -> str:
    return hashlib.sha256(_clean_text(value).encode("utf-8")).hexdigest()[:12]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except Exception:
        return False


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _clean_string_list(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _unique_paths(values: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for item in values:
        try:
            resolved = item.resolve()
        except Exception:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        out.append(resolved)
    return out


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False
