from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


CODING_EVENT_SCHEMA_VERSION = "astrabridge-coding-event-v1"


@dataclass
class CodingEvent:
    event_id: str
    task_id: str
    visible_thread_id: str
    execution_thread_id: str | None
    provider_id: str | None
    model_id: str | None
    event_type: str
    timestamp: str | None
    payload: dict[str, Any]
    redaction_status: Literal["redacted", "secret_free", "blocked"]
    source: Literal["codex_app_server", "native_kernel", "transport", "ui", "sidecar"]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def project_turn_to_coding_events(
    *,
    task_id: str,
    visible_thread_id: str,
    turn: dict[str, Any],
    source: Literal["codex_app_server", "native_kernel", "transport", "ui", "sidecar"] = "codex_app_server",
) -> list[dict[str, Any]]:
    execution_thread_id = str(turn.get("source_thread_id") or turn.get("sourceThreadId") or "") or None
    provider_id = str(turn.get("provider_id") or turn.get("providerId") or "") or None
    model_id = str(turn.get("model") or "") or None
    timestamp = _string_or_none(turn.get("completedAt") or turn.get("startedAt") or turn.get("updatedAt") or turn.get("createdAt"))
    turn_id = str(turn.get("id") or "")

    events: list[dict[str, Any]] = []
    for index, item in enumerate(list(turn.get("items") or [])):
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "")
        event_type, payload = _event_payload(item_type, item)
        if not event_type:
            continue
        event = CodingEvent(
            event_id=f"{turn_id or 'turn'}:{str(item.get('id') or index)}",
            task_id=task_id,
            visible_thread_id=visible_thread_id,
            execution_thread_id=execution_thread_id,
            provider_id=provider_id,
            model_id=model_id,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
            redaction_status="secret_free",
            source=source,
        )
        events.append(event.to_dict())
    return events


def project_handoff_event_to_coding_events(
    *,
    task_id: str,
    visible_thread_id: str,
    handoff_event: dict[str, Any],
    source: Literal["codex_app_server", "native_kernel", "transport", "ui", "sidecar"] = "sidecar",
) -> list[dict[str, Any]]:
    if not isinstance(handoff_event, dict):
        return []
    event_id = str(handoff_event.get("event_id") or "").strip() or "handoff"
    provider_id = _string_or_none(handoff_event.get("provider_id"))
    model_id = _string_or_none(handoff_event.get("model"))
    timestamp = _string_or_none(handoff_event.get("created_at") or handoff_event.get("updated_at"))
    payload = {
        "from_thread_id": _string_or_none(handoff_event.get("from_thread_id")),
        "to_thread_id": _string_or_none(handoff_event.get("to_thread_id")),
        "profile_id": _string_or_none(handoff_event.get("profile_id")),
        "provider_id": provider_id,
        "model": model_id,
        "reasoning_effort": _string_or_none(handoff_event.get("reasoning_effort")),
        "reused_existing": bool(handoff_event.get("reused_existing")),
        "transition_summary": dict(handoff_event.get("transition_summary") or {}),
    }
    event = CodingEvent(
        event_id=event_id,
        task_id=task_id,
        visible_thread_id=visible_thread_id,
        execution_thread_id=_string_or_none(handoff_event.get("to_thread_id")),
        provider_id=provider_id,
        model_id=model_id,
        event_type="provider_handoff",
        timestamp=timestamp,
        payload=payload,
        redaction_status="secret_free",
        source=source,
    )
    return [event.to_dict()]


def _event_payload(item_type: str, item: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    if item_type in {"userMessage", "agentMessage", "assistantMessage"}:
        return (
            "agent_message",
            {
                "role": "user" if item_type == "userMessage" else "assistant",
                "text": _text_preview(item),
            },
        )
    if item_type == "plan":
        return ("plan_update", {"text": _text_preview(item)})
    if item_type == "reasoning":
        return ("reasoning_summary", {"text": _text_preview(item)})
    if item_type == "commandExecution":
        return (
            "command_execution",
            {
                "command": str(item.get("command") or ""),
                "status": str(item.get("status") or ""),
                "exit_code": item.get("exitCode"),
                "output_excerpt": _clip(str(item.get("aggregatedOutput") or ""), 400),
            },
        )
    if item_type == "fileChange":
        changes = [entry for entry in list(item.get("changes") or []) if isinstance(entry, dict)]
        paths = [str(entry.get("path") or entry.get("newPath") or entry.get("file") or "").strip() for entry in changes]
        return (
            "file_change",
            {
                "paths": [path for path in paths if path],
                "count": len(changes),
            },
        )
    if item_type in {"enteredReviewMode", "exitedReviewMode"}:
        return (
            "runtime_transition",
            {
                "transition": "review_entered" if item_type == "enteredReviewMode" else "review_exited",
                "review": _clip(str(item.get("review") or ""), 400),
            },
        )
    if item_type == "contextCompaction":
        return ("runtime_transition", {"transition": "context_compaction"})
    if item_type == "collabAgentToolCall":
        return (
            "runtime_transition",
            {
                "transition": "collab_agent_tool",
                "tool": str(item.get("tool") or ""),
                "receiver_thread_ids": [str(value) for value in list(item.get("receiverThreadIds") or []) if str(value).strip()],
                "prompt": _clip(str(item.get("prompt") or ""), 400),
            },
        )
    return None, {}


def _text_preview(item: dict[str, Any]) -> str:
    direct = item.get("text") or item.get("message") or item.get("content")
    if isinstance(direct, str):
        return _clip(direct.strip(), 1200)
    if isinstance(direct, list):
        chunks = []
        for entry in direct:
            if isinstance(entry, dict) and isinstance(entry.get("text"), str):
                chunks.append(entry["text"])
            elif isinstance(entry, str):
                chunks.append(entry)
        return _clip("\n".join(chunks).strip(), 1200)
    if item.get("summary"):
        summary = item.get("summary")
        if isinstance(summary, list):
            return _clip("\n".join(str(entry) for entry in summary if str(entry).strip()), 1200)
    return ""


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[truncated]"


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
