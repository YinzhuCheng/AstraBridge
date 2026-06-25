from __future__ import annotations

from copy import deepcopy
from typing import Any

from .common import new_id, now_iso


PROJECT_PLUGIN_SKILL_PRESETS_SCHEMA_VERSION = "astrabridge-project-plugin-skill-presets-v1"
DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID = "project-default"
DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_LABEL = "Project default"
_SUPPORTED_OPERATIONS = {"add_plugin", "remove_plugin", "add_skill", "remove_skill", "reset"}


def normalize_project_plugin_skill_presets(payload: Any) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    presets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in list(source.get("presets") or []):
        if not isinstance(item, dict):
            continue
        preset_id = _clean_text(item.get("preset_id")) or DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID
        if preset_id in seen_ids:
            continue
        seen_ids.add(preset_id)
        display_name = _clean_text(item.get("display_name")) or _default_preset_label(preset_id)
        presets.append(
            {
                "preset_id": preset_id,
                "display_name": display_name,
                "plugin_refs": _normalize_plugin_refs(item.get("plugin_refs") or item.get("plugins")),
                "skill_refs": _normalize_skill_refs(item.get("skill_refs") or item.get("skills")),
                "created_at": _clean_text(item.get("created_at")) or "",
                "updated_at": _clean_text(item.get("updated_at")) or "",
                "notes": _clean_string_list(item.get("notes")),
            }
        )
    if DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID not in seen_ids:
        presets.insert(
            0,
            {
                "preset_id": DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID,
                "display_name": DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_LABEL,
                "plugin_refs": [],
                "skill_refs": [],
                "created_at": "",
                "updated_at": "",
                "notes": [],
            },
        )
    active_preset_id = _clean_text(source.get("active_preset_id")) or DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID
    if active_preset_id not in {item["preset_id"] for item in presets}:
        active_preset_id = DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID
    return {
        "schema_version": PROJECT_PLUGIN_SKILL_PRESETS_SCHEMA_VERSION,
        "active_preset_id": active_preset_id,
        "presets": presets,
        "updated_at": _clean_text(source.get("updated_at")) or "",
        "notes": _clean_string_list(source.get("notes")),
    }


def mutate_project_plugin_skill_presets(
    payload: Any,
    *,
    operation: str,
    preset_id: str | None = None,
    plugin_ref: dict[str, Any] | None = None,
    skill_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_operation = _clean_text(operation).lower()
    if clean_operation not in _SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported project plugin/skill preset operation: {operation}")
    state = normalize_project_plugin_skill_presets(payload)
    clean_preset_id = _clean_text(preset_id) or _clean_text(state.get("active_preset_id")) or DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID
    preset = _ensure_preset(state, clean_preset_id)
    state["active_preset_id"] = clean_preset_id
    timestamp = now_iso()

    if clean_operation == "add_plugin":
        normalized = _normalize_plugin_ref(plugin_ref or {})
        if normalized is None:
            raise ValueError("plugin_ref is required for add_plugin.")
        _upsert_plugin_ref(preset["plugin_refs"], normalized)
    elif clean_operation == "remove_plugin":
        normalized = _normalize_plugin_ref(plugin_ref or {})
        if normalized is None:
            raise ValueError("plugin_ref is required for remove_plugin.")
        preset["plugin_refs"] = [
            item
            for item in list(preset.get("plugin_refs") or [])
            if _plugin_ref_key(item) != _plugin_ref_key(normalized)
        ]
    elif clean_operation == "add_skill":
        normalized = _normalize_skill_ref(skill_ref or {})
        if normalized is None:
            raise ValueError("skill_ref is required for add_skill.")
        _upsert_skill_ref(preset["skill_refs"], normalized)
    elif clean_operation == "remove_skill":
        normalized = _normalize_skill_ref(skill_ref or {})
        if normalized is None:
            raise ValueError("skill_ref is required for remove_skill.")
        preset["skill_refs"] = [
            item
            for item in list(preset.get("skill_refs") or [])
            if _skill_ref_key(item) != _skill_ref_key(normalized)
        ]
    else:
        preset["plugin_refs"] = []
        preset["skill_refs"] = []
        preset["notes"] = _dedupe_strings([*list(preset.get("notes") or []), "reset_by_user"])

    if not _clean_text(preset.get("created_at")):
        preset["created_at"] = timestamp
    preset["updated_at"] = timestamp
    state["updated_at"] = timestamp
    return normalize_project_plugin_skill_presets(state)


def active_project_plugin_skill_preset(payload: Any) -> dict[str, Any]:
    state = normalize_project_plugin_skill_presets(payload)
    active_preset_id = _clean_text(state.get("active_preset_id")) or DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID
    return next(
        (deepcopy(item) for item in list(state.get("presets") or []) if _clean_text(item.get("preset_id")) == active_preset_id),
        {
            "preset_id": DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID,
            "display_name": DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_LABEL,
            "plugin_refs": [],
            "skill_refs": [],
            "created_at": "",
            "updated_at": "",
            "notes": [],
        },
    )


def _ensure_preset(state: dict[str, Any], preset_id: str) -> dict[str, Any]:
    for item in list(state.get("presets") or []):
        if _clean_text(item.get("preset_id")) == preset_id:
            return item
    preset = {
        "preset_id": preset_id,
        "display_name": _default_preset_label(preset_id),
        "plugin_refs": [],
        "skill_refs": [],
        "created_at": "",
        "updated_at": "",
        "notes": [],
    }
    state.setdefault("presets", []).append(preset)
    return preset


def _normalize_plugin_refs(values: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in list(values or []):
        normalized = _normalize_plugin_ref(item)
        if normalized is None:
            continue
        key = _plugin_ref_key(normalized)
        if key in seen:
            continue
        seen.add(key)
        refs.append(normalized)
    return refs


def _normalize_plugin_ref(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    plugin_id = _clean_text(value.get("plugin_id"))
    if not plugin_id:
        return None
    source_catalog_id = _clean_text(value.get("source_catalog_id")) or None
    return {
        "plugin_id": plugin_id,
        "source_catalog_id": source_catalog_id,
        "display_name": _clean_text(value.get("display_name")) or plugin_id,
    }


def _normalize_skill_refs(values: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in list(values or []):
        normalized = _normalize_skill_ref(item)
        if normalized is None:
            continue
        key = _skill_ref_key(normalized)
        if key in seen:
            continue
        seen.add(key)
        refs.append(normalized)
    return refs


def _normalize_skill_ref(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    record_id = _clean_text(value.get("record_id"))
    skill_name = _clean_text(value.get("skill_name"))
    if not record_id or not skill_name:
        return None
    return {
        "record_id": record_id,
        "skill_name": skill_name,
        "owner_plugin_id": _clean_text(value.get("owner_plugin_id")) or None,
        "source_catalog_id": _clean_text(value.get("source_catalog_id")) or None,
        "display_name": _clean_text(value.get("display_name")) or skill_name,
    }


def _upsert_plugin_ref(entries: list[dict[str, Any]], value: dict[str, Any]) -> None:
    key = _plugin_ref_key(value)
    for index, item in enumerate(list(entries)):
        if _plugin_ref_key(item) == key:
            entries[index] = value
            return
    entries.append(value)


def _upsert_skill_ref(entries: list[dict[str, Any]], value: dict[str, Any]) -> None:
    key = _skill_ref_key(value)
    for index, item in enumerate(list(entries)):
        if _skill_ref_key(item) == key:
            entries[index] = value
            return
    entries.append(value)


def _plugin_ref_key(value: dict[str, Any]) -> tuple[str, str]:
    return (_clean_text(value.get("plugin_id")), _clean_text(value.get("source_catalog_id")))


def _skill_ref_key(value: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _clean_text(value.get("record_id")),
        _clean_text(value.get("skill_name")),
        _clean_text(value.get("owner_plugin_id")),
        _clean_text(value.get("source_catalog_id")),
    )


def _default_preset_label(preset_id: str) -> str:
    return DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_LABEL if preset_id == DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID else preset_id


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_list(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    return _dedupe_strings([_clean_text(item) for item in items])


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
