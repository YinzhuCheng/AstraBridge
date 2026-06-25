from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, new_id, now_iso, read_json, write_json


GLOBAL_SKILL_ENABLEMENT_SCHEMA_VERSION = "astrabridge-skill-enablement-global-v1"
PROJECT_SKILL_ENABLEMENT_SCHEMA_VERSION = "astrabridge-skill-enablement-project-v1"
_GLOBAL_STATUSES = {"enabled", "disabled"}
_PROJECT_STATUSES = {"enabled", "disabled", "inherited"}
_RUNTIME_ENABLEMENT_STATUSES = {"enabled", "disabled", "blocked", "inherited", "unknown"}


def apply_skill_enablement_snapshot(
    *,
    registry_snapshot: dict[str, Any],
    codex_home: Path,
    workspace_root: Path | None,
) -> dict[str, Any]:
    snapshot = deepcopy(registry_snapshot if isinstance(registry_snapshot, dict) else {})
    codex_home = codex_home.expanduser().resolve()
    workspace_root = workspace_root.expanduser().resolve() if workspace_root else None
    global_path = global_skill_enablement_state_path(codex_home)
    project_path = project_skill_enablement_state_path(workspace_root) if workspace_root else None
    global_state = _load_global_state(global_path)
    project_state = _load_project_state(project_path) if project_path else _empty_project_state()
    plugins_by_id = _plugin_index(snapshot)

    for skill in list(snapshot.get("skills") or []):
        if not isinstance(skill, dict):
            continue
        observed_status = _runtime_status(skill.get("observed_enablement_status") or skill.get("enablement_status"))
        global_rule = _match_global_rule(skill, global_state["rules"])
        project_override = _match_project_override(skill, project_state["overrides"])
        global_status = str(global_rule.get("status") or "").strip() if global_rule else ""
        if global_status not in _GLOBAL_STATUSES:
            global_status = observed_status if observed_status in _GLOBAL_STATUSES else "unknown"
        project_status = str(project_override.get("status") or "").strip() if project_override else ("inherited" if project_path else "unknown")
        if project_status not in _PROJECT_STATUSES and project_status != "unknown":
            project_status = "unknown"
        effective_status = _effective_enablement_status(
            observed_status=observed_status,
            global_status=global_status,
            project_status=project_status,
        )
        enablement_source = _enablement_source(global_rule=global_rule, project_override=project_override, effective_status=effective_status)
        blocked_warning = _owner_plugin_warning(skill, plugins_by_id)
        if blocked_warning is not None:
            effective_status = "blocked"
            enablement_source = "blocked"
            skill["compatibility_warnings"] = _dedupe_warnings(
                [*list(skill.get("compatibility_warnings") or []), blocked_warning]
            )
            skill["enablement_block_reason"] = str(blocked_warning.get("code") or "owner_plugin_unavailable")

        skill["observed_enablement_status"] = observed_status
        skill["global_enablement_status"] = global_status
        skill["project_enablement_status"] = project_status
        skill["effective_enablement_status"] = effective_status
        skill["enablement_status"] = effective_status
        skill["enablement_source"] = enablement_source
        skill["project_override_supported"] = project_path is not None
        skill["global_state_path"] = str(global_path)
        skill["project_state_path"] = str(project_path) if project_path else None
        skill["notes"] = _dedupe_strings(
            [
                *list(skill.get("notes") or []),
                f"enablement_source:{enablement_source}",
                *(["enablement_pending_user_approval"] if str((global_rule or {}).get("reason") or "") == "plugin_install_pending_approval" else []),
            ]
        )
    return snapshot


def update_skill_enablement_snapshot(
    *,
    registry_snapshot: dict[str, Any],
    codex_home: Path,
    workspace_root: Path | None,
    record_id: str,
    scope: str,
    enablement_status: str,
) -> dict[str, Any]:
    clean_record_id = str(record_id or "").strip()
    clean_scope = str(scope or "").strip().lower()
    clean_status = str(enablement_status or "").strip().lower()
    if not clean_record_id:
        raise ValueError("record_id is required.")
    if clean_scope not in {"global", "project"}:
        raise ValueError("scope must be global or project.")
    if clean_scope == "global" and clean_status not in _GLOBAL_STATUSES:
        raise ValueError("Global skill enablement must be enabled or disabled.")
    if clean_scope == "project" and clean_status not in _PROJECT_STATUSES:
        raise ValueError("Project skill enablement must be enabled, disabled, or inherited.")

    codex_home = codex_home.expanduser().resolve()
    workspace_root = workspace_root.expanduser().resolve() if workspace_root else None
    global_path = global_skill_enablement_state_path(codex_home)
    project_path = project_skill_enablement_state_path(workspace_root) if workspace_root else None

    current_snapshot = apply_skill_enablement_snapshot(
        registry_snapshot=registry_snapshot,
        codex_home=codex_home,
        workspace_root=workspace_root,
    )
    skill = _find_skill_record(current_snapshot, clean_record_id)
    if skill is None:
        raise ValueError(f"Unknown skill record_id: {clean_record_id}")
    if clean_status == "enabled":
        _validate_skill_can_enable(skill, current_snapshot)

    if clean_scope == "global":
        state = _load_global_state(global_path)
        _upsert_global_rule(
            state["rules"],
            skill=skill,
            status=clean_status,
            reason="user",
        )
        state["updated_at"] = now_iso()
        write_json(global_path, state)
    else:
        if project_path is None:
            raise ValueError("Project overrides require an open AstraBridge workspace.")
        state = _load_project_state(project_path)
        if clean_status == "inherited":
            state["overrides"] = [
                item for item in list(state.get("overrides") or []) if str(item.get("record_id") or "").strip() != clean_record_id
            ]
        else:
            _upsert_project_override(state["overrides"], skill=skill, status=clean_status)
        state["updated_at"] = now_iso()
        write_json(project_path, state)

    return apply_skill_enablement_snapshot(
        registry_snapshot=registry_snapshot,
        codex_home=codex_home,
        workspace_root=workspace_root,
    )


def register_pending_skill_approval_rules(
    *,
    codex_home: Path,
    plugin_id: str,
    source_catalog_id: str | None,
    skill_names: list[str] | tuple[str, ...],
) -> None:
    clean_plugin_id = str(plugin_id or "").strip()
    names = _dedupe_strings(list(skill_names or []))
    if not clean_plugin_id or not names:
        return
    global_path = global_skill_enablement_state_path(codex_home.expanduser().resolve())
    state = _load_global_state(global_path)
    changed = False
    timestamp = now_iso()
    for skill_name in names:
        if _match_selector_rule(
            {
                "skill_name": skill_name,
                "owner_plugin_id": clean_plugin_id,
                "source_catalog_id": str(source_catalog_id or "").strip() or None,
            },
            list(state.get("rules") or []),
        ):
            continue
        state["rules"].append(
            {
                "rule_id": new_id("skill-enablement"),
                "record_id": None,
                "skill_name": skill_name,
                "owner_plugin_id": clean_plugin_id,
                "source_catalog_id": str(source_catalog_id or "").strip() or None,
                "status": "disabled",
                "reason": "plugin_install_pending_approval",
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        changed = True
    if changed:
        state["updated_at"] = timestamp
        write_json(global_path, state)


def global_skill_enablement_state_path(codex_home: Path) -> Path:
    return codex_home.expanduser().resolve() / "astrabridge-managed" / "skill-enablement.global.json"


def project_skill_enablement_state_path(workspace_root: Path) -> Path:
    return workspace_root.expanduser().resolve() / WORKSPACE_STATE_DIRNAME / "extensions" / "skill-enablement.json"


def _effective_enablement_status(*, observed_status: str, global_status: str, project_status: str) -> str:
    if project_status in _GLOBAL_STATUSES:
        return project_status
    if global_status in _GLOBAL_STATUSES:
        return global_status
    if observed_status in _GLOBAL_STATUSES:
        return observed_status
    return "unknown"


def _enablement_source(
    *,
    global_rule: dict[str, Any] | None,
    project_override: dict[str, Any] | None,
    effective_status: str,
) -> str:
    if effective_status == "blocked":
        return "blocked"
    if project_override is not None and str(project_override.get("status") or "").strip() in _GLOBAL_STATUSES:
        return "project_override"
    if global_rule is not None and str(global_rule.get("status") or "").strip() in _GLOBAL_STATUSES:
        return str(global_rule.get("reason") or "global_rule").strip() or "global_rule"
    return "runtime_observed"


def _plugin_index(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    plugins_by_id: dict[str, dict[str, Any]] = {}
    for plugin in list(snapshot.get("plugins") or []):
        if not isinstance(plugin, dict):
            continue
        plugin_id = str(plugin.get("plugin_id") or "").strip()
        if plugin_id and plugin_id not in plugins_by_id:
            plugins_by_id[plugin_id] = plugin
    return plugins_by_id


def _owner_plugin_warning(skill: dict[str, Any], plugins_by_id: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    owner_plugin_id = str(skill.get("owner_plugin_id") or "").strip()
    if not owner_plugin_id:
        return None
    plugin = plugins_by_id.get(owner_plugin_id)
    if plugin is None:
        return _warning(
            "skill-owning-plugin-missing",
            f"Owning plugin {owner_plugin_id} is not available in the current registry snapshot.",
            field="owner_plugin_id",
        )
    install_status = str(plugin.get("install_status") or "").strip()
    if install_status != "installed":
        return _warning(
            "skill-owning-plugin-unavailable",
            f"Owning plugin {owner_plugin_id} is not installed in the current runtime lane.",
            field="owner_plugin_id",
        )
    plugin_enablement = str(plugin.get("enablement_status") or "").strip()
    if plugin_enablement in {"disabled", "blocked"}:
        return _warning(
            "skill-owning-plugin-disabled",
            f"Owning plugin {owner_plugin_id} is not enabled for the current runtime lane.",
            field="owner_plugin_id",
        )
    return None


def _validate_skill_can_enable(skill: dict[str, Any], snapshot: dict[str, Any]) -> None:
    blocked_warning = _owner_plugin_warning(skill, _plugin_index(snapshot))
    if blocked_warning is not None:
        raise ValueError(str(blocked_warning.get("message") or "Owning plugin is unavailable."))
    install_status = str(skill.get("install_status") or "").strip()
    if install_status != "installed":
        raise ValueError(f"Skill {skill.get('skill_name') or skill.get('display_name') or ''} is not installed.")


def _find_skill_record(snapshot: dict[str, Any], record_id: str) -> dict[str, Any] | None:
    for skill in list(snapshot.get("skills") or []):
        if not isinstance(skill, dict):
            continue
        if str(skill.get("record_id") or "").strip() == record_id:
            return skill
    return None


def _match_global_rule(skill: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    record_id = str(skill.get("record_id") or "").strip()
    exact = next(
        (
            item
            for item in rules
            if str(item.get("record_id") or "").strip() == record_id
            and str(item.get("status") or "").strip() in _GLOBAL_STATUSES
        ),
        None,
    )
    if exact is not None:
        return exact
    return _match_selector_rule(skill, rules)


def _match_selector_rule(skill: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    clean_skill_name = str(skill.get("skill_name") or "").strip()
    clean_owner = str(skill.get("owner_plugin_id") or "").strip()
    clean_source_catalog = str(skill.get("source_catalog_id") or "").strip()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for item in rules:
        status = str(item.get("status") or "").strip()
        if status not in _GLOBAL_STATUSES:
            continue
        item_skill_name = str(item.get("skill_name") or "").strip()
        item_owner = str(item.get("owner_plugin_id") or "").strip()
        item_source_catalog = str(item.get("source_catalog_id") or "").strip()
        if item_skill_name != clean_skill_name:
            continue
        score = 0
        if item_owner and item_owner == clean_owner:
            score += 2
        elif item_owner:
            continue
        if item_source_catalog and item_source_catalog == clean_source_catalog:
            score += 1
        elif item_source_catalog:
            continue
        candidates.append((score, item))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _match_project_override(skill: dict[str, Any], overrides: list[dict[str, Any]]) -> dict[str, Any] | None:
    record_id = str(skill.get("record_id") or "").strip()
    return next(
        (
            item
            for item in overrides
            if str(item.get("record_id") or "").strip() == record_id
            and str(item.get("status") or "").strip() in _PROJECT_STATUSES
        ),
        None,
    )


def _upsert_global_rule(
    rules: list[dict[str, Any]],
    *,
    skill: dict[str, Any],
    status: str,
    reason: str,
) -> None:
    record_id = str(skill.get("record_id") or "").strip()
    timestamp = now_iso()
    for item in rules:
        if str(item.get("record_id") or "").strip() == record_id:
            item.update(
                {
                    "record_id": record_id,
                    "skill_name": str(skill.get("skill_name") or "").strip(),
                    "owner_plugin_id": str(skill.get("owner_plugin_id") or "").strip() or None,
                    "source_catalog_id": str(skill.get("source_catalog_id") or "").strip() or None,
                    "status": status,
                    "reason": reason,
                    "updated_at": timestamp,
                }
            )
            return
    rules.append(
        {
            "rule_id": new_id("skill-enablement"),
            "record_id": record_id,
            "skill_name": str(skill.get("skill_name") or "").strip(),
            "owner_plugin_id": str(skill.get("owner_plugin_id") or "").strip() or None,
            "source_catalog_id": str(skill.get("source_catalog_id") or "").strip() or None,
            "status": status,
            "reason": reason,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )


def _upsert_project_override(overrides: list[dict[str, Any]], *, skill: dict[str, Any], status: str) -> None:
    record_id = str(skill.get("record_id") or "").strip()
    timestamp = now_iso()
    for item in overrides:
        if str(item.get("record_id") or "").strip() == record_id:
            item.update({"status": status, "updated_at": timestamp})
            return
    overrides.append(
        {
            "override_id": new_id("skill-project-override"),
            "record_id": record_id,
            "skill_name": str(skill.get("skill_name") or "").strip(),
            "status": status,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )


def _load_global_state(path: Path) -> dict[str, Any]:
    payload = read_json(path, _empty_global_state())
    rules: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for item in list(payload.get("rules") or []):
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").strip()
            if status not in _GLOBAL_STATUSES:
                continue
            rules.append(
                {
                    "rule_id": str(item.get("rule_id") or "").strip() or new_id("skill-enablement"),
                    "record_id": str(item.get("record_id") or "").strip() or None,
                    "skill_name": str(item.get("skill_name") or "").strip(),
                    "owner_plugin_id": str(item.get("owner_plugin_id") or "").strip() or None,
                    "source_catalog_id": str(item.get("source_catalog_id") or "").strip() or None,
                    "status": status,
                    "reason": str(item.get("reason") or "").strip() or "user",
                    "created_at": str(item.get("created_at") or "").strip() or None,
                    "updated_at": str(item.get("updated_at") or "").strip() or None,
                }
            )
    return {
        "schema_version": GLOBAL_SKILL_ENABLEMENT_SCHEMA_VERSION,
        "updated_at": str((payload or {}).get("updated_at") or "").strip() if isinstance(payload, dict) else "",
        "rules": rules,
    }


def _load_project_state(path: Path) -> dict[str, Any]:
    payload = read_json(path, _empty_project_state())
    overrides: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for item in list(payload.get("overrides") or []):
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").strip()
            if status not in _PROJECT_STATUSES:
                continue
            overrides.append(
                {
                    "override_id": str(item.get("override_id") or "").strip() or new_id("skill-project-override"),
                    "record_id": str(item.get("record_id") or "").strip(),
                    "skill_name": str(item.get("skill_name") or "").strip(),
                    "status": status,
                    "created_at": str(item.get("created_at") or "").strip() or None,
                    "updated_at": str(item.get("updated_at") or "").strip() or None,
                }
            )
    return {
        "schema_version": PROJECT_SKILL_ENABLEMENT_SCHEMA_VERSION,
        "updated_at": str((payload or {}).get("updated_at") or "").strip() if isinstance(payload, dict) else "",
        "overrides": overrides,
    }


def _empty_global_state() -> dict[str, Any]:
    return {
        "schema_version": GLOBAL_SKILL_ENABLEMENT_SCHEMA_VERSION,
        "updated_at": "",
        "rules": [],
    }


def _empty_project_state() -> dict[str, Any]:
    return {
        "schema_version": PROJECT_SKILL_ENABLEMENT_SCHEMA_VERSION,
        "updated_at": "",
        "overrides": [],
    }


def _runtime_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in _RUNTIME_ENABLEMENT_STATUSES:
        return text
    return "unknown"


def _warning(code: str, message: str, *, field: str | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": "astrabridge-plugin-skill-warning-v1",
        "code": code,
        "severity": "warning",
        "message": message,
    }
    if field:
        payload["field"] = field
    return payload


def _dedupe_warnings(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("code") or "").strip(), str(item.get("field") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
