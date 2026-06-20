from __future__ import annotations

import json
import re
from typing import Any

from .security import redact_sensitive


TOOL_CONTEXT_SCHEMA_VERSION = "lcr-tool-context-envelope-v1"

_TEXT_LIMITS = {
    "schema_version": 80,
    "tool_name": 120,
    "project_id": 160,
    "task_id": 160,
    "task_title": 220,
    "task_goal": 800,
    "current_plan_step": 800,
    "workspace_root": 420,
    "selected_provider": 120,
    "selected_model": 160,
    "selected_effort": 80,
    "permission_mode": 80,
    "project_context_ref": 420,
    "asset_context_ref": 420,
    "output_contract": 900,
}

_LIST_LIMITS = {
    "evidence_requirements": (8, 260),
    "forbidden_inputs": (12, 260),
    "context_refs": (8, 420),
    "asset_context_refs": (6, 420),
    "checkpoint_refs": (6, 260),
}

_SECRET_TERMS_RE = re.compile(
    r"(?i)(authorization|bearer\s+|api[_-]?key|secret|cookie|token|password|raw[_-]?messages|base64|data:image)"
)

DEFAULT_FORBIDDEN_INPUTS = [
    "Do not include raw .astrabridge/runtime_events.jsonl.",
    "Do not include raw .astrabridge/approvals.jsonl.",
    "Do not include API keys, Authorization headers, bearer tokens, cookies, or passwords.",
    "Do not include image base64 or large raw provider responses.",
]

DEFAULT_EVIDENCE_REQUIREMENTS = [
    "Return tool-event verified evidence paths or URLs when available.",
    "Clearly separate verified observations from model-claimed actions.",
]


class ToolContextService:
    """Builds the small context envelope passed to AstraBridge built-in tools.

    This is intentionally not a transcript copier. It gives tools enough task,
    plan, workspace, and context-pack references to be useful while avoiding raw
    runtime logs, approvals, credentials, or huge binary payloads.
    """

    def __init__(self, project_service, task_service=None) -> None:
        self._projects = project_service
        self._tasks = task_service

    def build(
        self,
        *,
        tool_name: str,
        provided: Any | None = None,
        output_contract: str | None = None,
        evidence_requirements: list[str] | None = None,
        forbidden_inputs: list[str] | None = None,
    ) -> dict[str, Any]:
        base = self._default_envelope(
            tool_name=tool_name,
            output_contract=output_contract,
            evidence_requirements=evidence_requirements,
            forbidden_inputs=forbidden_inputs,
        )
        explicit = sanitize_tool_context(provided)
        merged = {**base, **explicit}
        for key in ("evidence_requirements", "forbidden_inputs", "context_refs", "asset_context_refs", "checkpoint_refs"):
            merged[key] = _merge_lists(base.get(key), explicit.get(key), key)
        return sanitize_tool_context(merged)

    def _default_envelope(
        self,
        *,
        tool_name: str,
        output_contract: str | None,
        evidence_requirements: list[str] | None,
        forbidden_inputs: list[str] | None,
    ) -> dict[str, Any]:
        project = dict(self._projects.current_project or {})
        task = self._current_task()
        active_thread = self._active_provider_thread()
        plan_step = _current_plan_step(task.get("plan"))
        context_refs = [str(item.get("path") or "") for item in list(task.get("context_pack_refs") or [])]
        asset_refs = [str(item.get("path") or "") for item in list(task.get("asset_context_refs") or [])]
        checkpoints = [
            str(item.get("description") or item.get("save_id") or "")
            for item in list(task.get("checkpoint_refs") or [])[:6]
        ]
        return {
            "schema_version": TOOL_CONTEXT_SCHEMA_VERSION,
            "tool_name": tool_name,
            "project_id": str(project.get("project_id") or ""),
            "task_id": str(task.get("task_id") or project.get("current_task_id") or ""),
            "task_title": str(task.get("title") or project.get("name") or ""),
            "task_goal": _goal_text(task.get("goal")),
            "current_plan_step": plan_step,
            "workspace_root": str(project.get("workspace_root") or ""),
            "selected_provider": str(active_thread.get("provider_id") or project.get("default_profile_id") or ""),
            "selected_model": str(active_thread.get("model") or project.get("default_model") or ""),
            "selected_effort": str(active_thread.get("reasoning_effort") or project.get("default_effort") or ""),
            "permission_mode": str(active_thread.get("permission_mode") or ""),
            "project_context_ref": context_refs[0] if context_refs else "",
            "asset_context_ref": asset_refs[0] if asset_refs else "",
            "context_refs": context_refs,
            "asset_context_refs": asset_refs,
            "checkpoint_refs": checkpoints,
            "evidence_requirements": list(evidence_requirements or DEFAULT_EVIDENCE_REQUIREMENTS),
            "forbidden_inputs": list(forbidden_inputs or DEFAULT_FORBIDDEN_INPUTS),
            "output_contract": output_contract or _default_output_contract(tool_name),
        }

    def _current_task(self) -> dict[str, Any]:
        if self._tasks is None:
            return {}
        try:
            return dict(self._tasks.current_task() or {})
        except Exception:
            return {}

    def _active_provider_thread(self) -> dict[str, Any]:
        if self._tasks is None:
            return {}
        try:
            return dict(self._tasks.active_provider_thread(include_missing_fallback=True) or {})
        except Exception:
            return {}


def sanitize_tool_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    sanitized: dict[str, Any] = {}
    for key, limit in _TEXT_LIMITS.items():
        text = _safe_text(value.get(key), limit)
        if text:
            sanitized[key] = text
    for key, (max_items, limit) in _LIST_LIMITS.items():
        items = _safe_list(value.get(key), max_items=max_items, limit=limit)
        if items:
            sanitized[key] = items
    return sanitized


def _safe_list(value: Any, *, max_items: int, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:max_items]:
        text = _safe_text(item, limit)
        if text:
            result.append(text)
    return result


def _safe_text(value: Any, limit: int) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    text = str(redact_sensitive(value))
    text = _SECRET_TERMS_RE.sub("[REDACTED]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    return text[:limit]


def _merge_lists(base: Any, explicit: Any, key: str) -> list[str]:
    max_items, limit = _LIST_LIMITS.get(key, (8, 260))
    seen: set[str] = set()
    merged = []
    for source in (base, explicit):
        for item in _safe_list(source, max_items=max_items, limit=limit):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
            if len(merged) >= max_items:
                return merged
    return merged


def _goal_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("objective", "goal", "text", "description"):
            text = _safe_text(value.get(key), 800)
            if text:
                return text
        return _safe_text(json.dumps(value, ensure_ascii=False, sort_keys=True), 800)
    return _safe_text(value, 800)


def _current_plan_step(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    steps = value.get("steps") or value.get("plan") or []
    if not isinstance(steps, list):
        return ""
    preferred = None
    fallback = None
    for item in steps:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").lower()
        step = _safe_text(item.get("step") or item.get("text") or item.get("title"), 760)
        if not step:
            continue
        fallback = fallback or step
        if status in {"in_progress", "active", "running"}:
            preferred = step
            break
    return preferred or fallback or ""


def _default_output_contract(tool_name: str) -> str:
    if tool_name.startswith("lcr_web_"):
        return "Return source URLs, concise summaries, confidence/freshness notes, and unresolved questions. Do not claim facts without a source URL."
    if tool_name.startswith("yunwu_image_"):
        return "Return requested_n, actual_n, local paths, dimensions, format, alpha status, validation warnings, and intended game usage."
    if tool_name == "lcr_browser_smoke":
        return "Return screenshot path, URL, pass/fail status, console error count, and any blocking failure reason."
    if tool_name.startswith("asset_"):
        return "Return asset_id, manifest key, promoted path, validation status, and screenshot evidence when available."
    return "Return compact verified evidence and next-action guidance."

