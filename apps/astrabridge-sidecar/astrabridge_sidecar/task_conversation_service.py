from __future__ import annotations

from typing import Any

from .common import now_iso, read_json, write_json
from .coding_kernel import project_turn_to_coding_events
from .security import redact_sensitive


TASK_TRANSCRIPT_SCHEMA_VERSION = "astrabridge-task-transcripts-v1"
TASK_CONVERSATION_DIGEST_SCHEMA_VERSION = "astrabridge-task-conversation-digest-v1"
MAX_SNAPSHOT_TURNS = 60
MAX_DIGEST_ITEMS = 12
MAX_TEXT_CHARS = 1200
MAX_STORED_STRING_CHARS = 12000


class TaskConversationService:
    """Secret-free task-level transcript projection across provider lanes."""

    def __init__(self, project_service, task_service) -> None:
        self._projects = project_service
        self._tasks = task_service

    def record_thread_snapshot(self, thread: dict[str, Any]) -> None:
        thread_id = str(thread.get("id") or thread.get("thread_id") or "").strip()
        if not thread_id:
            return
        task = self._task_for_thread(thread_id)
        if not task:
            return
        route = self._route_for_thread(task, thread_id)
        snapshot = self._snapshot_thread(thread, task=task, route=route)
        state = self._state()
        threads = dict(state.get("threads") or {})
        threads[thread_id] = snapshot
        state["threads"] = threads
        state["schema_version"] = TASK_TRANSCRIPT_SCHEMA_VERSION
        state["updated_at"] = now_iso()
        write_json(self._path(), state)

    def conversation(self, *, task_id: str | None = None) -> dict[str, Any]:
        task = self._task_by_id(task_id) if task_id else self._current_task()
        if not task:
            raise ValueError("No current task is available.")
        state = self._state()
        snapshots = dict(state.get("threads") or {})
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        turns: list[dict[str, Any]] = []
        provider_threads = [dict(item) for item in list(task.get("provider_threads") or []) if isinstance(item, dict)]
        for route in reversed(provider_threads):
            thread_id = str(route.get("thread_id") or "").strip()
            snapshot = dict(snapshots.get(thread_id) or {})
            if not snapshot:
                continue
            for turn in list(snapshot.get("turns") or []):
                if not isinstance(turn, dict):
                    continue
                turns.append(self._annotate_turn(dict(turn), snapshot=snapshot, route=route))
        turns.sort(key=self._turn_sort_key)
        active_snapshot = dict(snapshots.get(active_thread_id) or {})
        active_route = self._route_for_thread(task, active_thread_id)
        return {
            "thread": {
                "id": f"task:{task.get('task_id')}",
                "sessionId": f"task:{task.get('task_id')}",
                "name": task.get("title") or "Task conversation",
                "displayName": task.get("title") or "Task conversation",
                "status": active_snapshot.get("status") or {"type": "idle"},
                "shellSettings": self._shell_settings(active_route),
                "turns": turns,
                "isCompositeTaskThread": True,
                "task_id": task.get("task_id"),
                "active_provider_thread_id": active_thread_id or None,
                "provider_threads": provider_threads,
            },
            "task": task,
            "transcript_path": str(self._path()),
            "updated_at": state.get("updated_at"),
        }

    def digest(self, *, task_id: str | None = None) -> dict[str, Any]:
        try:
            conversation = self.conversation(task_id=task_id)
        except Exception:
            return {
                "schema_version": TASK_CONVERSATION_DIGEST_SCHEMA_VERSION,
                "status": "unavailable",
                "items": [],
            }
        thread = dict(conversation.get("thread") or {})
        digest_items: list[dict[str, Any]] = []
        for turn in list(thread.get("turns") or [])[-MAX_DIGEST_ITEMS:]:
            if not isinstance(turn, dict):
                continue
            item = self._digest_turn(turn)
            if item:
                digest_items.append(item)
        return redact_sensitive(
            {
                "schema_version": TASK_CONVERSATION_DIGEST_SCHEMA_VERSION,
                "status": "ok",
                "task_id": (conversation.get("task") or {}).get("task_id"),
                "thread_count": len(list(thread.get("provider_threads") or [])),
                "turn_count": len(list(thread.get("turns") or [])),
                "items": digest_items[-MAX_DIGEST_ITEMS:],
                "updated_at": conversation.get("updated_at") or now_iso(),
            }
        )

    def _snapshot_thread(self, thread: dict[str, Any], *, task: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._truncate_large_strings(redact_sensitive(thread))
        turns = [dict(item) for item in list(sanitized.get("turns") or []) if isinstance(item, dict)]
        snapshot = {
            "thread_id": str(sanitized.get("id") or sanitized.get("thread_id") or ""),
            "task_id": task.get("task_id"),
            "name": sanitized.get("name") or sanitized.get("displayName") or route.get("name") or "",
            "displayName": sanitized.get("displayName") or sanitized.get("name") or route.get("name") or "",
            "status": sanitized.get("status") if isinstance(sanitized.get("status"), dict) else {"type": str(sanitized.get("status") or "idle")},
            "shellSettings": self._shell_settings({**route, **dict(sanitized.get("shellSettings") or {})}),
            "profile_id": route.get("profile_id") or dict(sanitized.get("shellSettings") or {}).get("profile_id"),
            "provider_id": route.get("provider_id") or dict(sanitized.get("shellSettings") or {}).get("provider_id"),
            "model": route.get("model") or dict(sanitized.get("shellSettings") or {}).get("model"),
            "reasoning_effort": route.get("reasoning_effort") or dict(sanitized.get("shellSettings") or {}).get("reasoning_effort"),
            "permission_mode": route.get("permission_mode") or dict(sanitized.get("shellSettings") or {}).get("permission_mode"),
            "turns": turns[-MAX_SNAPSHOT_TURNS:],
            "updated_at": now_iso(),
        }
        return redact_sensitive(snapshot)

    def _annotate_turn(self, turn: dict[str, Any], *, snapshot: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
        thread_id = str(snapshot.get("thread_id") or route.get("thread_id") or "")
        meta = {
            "task_id": snapshot.get("task_id"),
            "source_thread_id": thread_id,
            "profile_id": snapshot.get("profile_id") or route.get("profile_id"),
            "provider_id": snapshot.get("provider_id") or route.get("provider_id"),
            "model": snapshot.get("model") or route.get("model"),
            "reasoning_effort": snapshot.get("reasoning_effort") or route.get("reasoning_effort"),
        }
        annotated = {**turn, **{key: value for key, value in meta.items() if value not in {None, ""}}}
        items: list[Any] = []
        for item in list(annotated.get("items") or []):
            if isinstance(item, dict):
                items.append({**item, **{key: value for key, value in meta.items() if value not in {None, ""}}})
            else:
                items.append(item)
        annotated["items"] = items
        return annotated

    def _digest_turn(self, turn: dict[str, Any]) -> dict[str, Any] | None:
        chunks: list[str] = []
        file_changes: list[str] = []
        commands: list[str] = []
        for item in list(turn.get("items") or []):
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "")
            text = self._item_text(item)
            if text and item_type in {"userMessage", "user_message", "inputMessage", "agentMessage", "assistantMessage", "plan"}:
                chunks.append(text)
            if item_type == "fileChange":
                for change in list(item.get("changes") or []):
                    if isinstance(change, dict):
                        path = str(change.get("path") or change.get("newPath") or change.get("file") or "").strip()
                        if path:
                            file_changes.append(path)
            if item_type == "commandExecution" and item.get("command"):
                commands.append(str(item.get("command"))[:MAX_TEXT_CHARS])
        preview = self._clip("\n".join(chunks).strip(), MAX_TEXT_CHARS)
        events = project_turn_to_coding_events(
            task_id=str(turn.get("task_id") or ""),
            visible_thread_id=f"task:{str(turn.get('task_id') or '')}" if turn.get("task_id") else "task:unknown",
            turn=turn,
        )
        if not preview and not file_changes and not commands:
            return None
        return {
            "turn_id": turn.get("id"),
            "source_thread_id": turn.get("source_thread_id"),
            "provider_id": turn.get("provider_id"),
            "model": turn.get("model"),
            "started_at": turn.get("startedAt"),
            "completed_at": turn.get("completedAt"),
            "summary": preview,
            "files": file_changes[:10],
            "commands": commands[:5],
            "event_types": [str(item.get("event_type") or "") for item in events[:8] if str(item.get("event_type") or "").strip()],
        }

    def _item_text(self, item: dict[str, Any]) -> str:
        direct = item.get("text") or item.get("message") or item.get("content")
        if isinstance(direct, str):
            return self._clip(direct.strip(), MAX_TEXT_CHARS)
        if isinstance(direct, list):
            chunks = []
            for entry in direct:
                if isinstance(entry, dict) and isinstance(entry.get("text"), str):
                    chunks.append(entry["text"])
                elif isinstance(entry, str):
                    chunks.append(entry)
            return self._clip("\n".join(chunks).strip(), MAX_TEXT_CHARS)
        return ""

    def _turn_sort_key(self, turn: dict[str, Any]) -> tuple[int, str, str]:
        for key in ("startedAt", "completedAt", "updatedAt", "createdAt"):
            value = turn.get(key)
            if isinstance(value, (int, float)):
                return (int(value), str(turn.get("source_thread_id") or ""), str(turn.get("id") or ""))
            if isinstance(value, str) and value.isdigit():
                return (int(value), str(turn.get("source_thread_id") or ""), str(turn.get("id") or ""))
        return (0, str(turn.get("source_thread_id") or ""), str(turn.get("id") or ""))

    def _route_for_thread(self, task: dict[str, Any], thread_id: str) -> dict[str, Any]:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return {}
        for item in list(task.get("provider_threads") or []):
            if isinstance(item, dict) and str(item.get("thread_id") or "") == clean_thread_id:
                return dict(item)
        return {}

    def _shell_settings(self, route: dict[str, Any]) -> dict[str, Any]:
        return {
            key: route.get(key)
            for key in ("profile_id", "model", "reasoning_effort", "permission_mode", "collaboration_mode")
            if route.get(key) is not None
        }

    def _task_for_thread(self, thread_id: str) -> dict[str, Any] | None:
        for task in list((self._tasks.snapshot() or {}).get("tasks") or []):
            if not isinstance(task, dict):
                continue
            if any(str(item.get("thread_id") or "") == thread_id for item in list(task.get("provider_threads") or []) if isinstance(item, dict)):
                return task
        return None

    def _task_by_id(self, task_id: str | None) -> dict[str, Any] | None:
        clean_task_id = str(task_id or "").strip()
        if not clean_task_id:
            return None
        for task in list((self._tasks.snapshot() or {}).get("tasks") or []):
            if isinstance(task, dict) and str(task.get("task_id") or "") == clean_task_id:
                return task
        return None

    def _current_task(self) -> dict[str, Any] | None:
        task = self._tasks.current_task()
        return dict(task) if isinstance(task, dict) else None

    def _state(self) -> dict[str, Any]:
        payload = read_json(self._path(), {"schema_version": TASK_TRANSCRIPT_SCHEMA_VERSION, "threads": {}})
        if not isinstance(payload, dict):
            return {"schema_version": TASK_TRANSCRIPT_SCHEMA_VERSION, "threads": {}}
        payload.setdefault("schema_version", TASK_TRANSCRIPT_SCHEMA_VERSION)
        payload.setdefault("threads", {})
        return payload

    def _path(self):
        return self._projects.require_shell_state_root() / "task_transcripts.json"

    def _truncate_large_strings(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._truncate_large_strings(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._truncate_large_strings(item) for item in value]
        if isinstance(value, str):
            return self._clip(value, MAX_STORED_STRING_CHARS)
        return value

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "\n[truncated]"
