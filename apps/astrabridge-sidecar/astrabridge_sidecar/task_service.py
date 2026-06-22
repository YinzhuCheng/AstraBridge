from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, new_id, now_iso, read_json, write_json
from .providers.runtime_transition import summarize_transition
from .security import SECRET_RE, SecurityError, redact_sensitive


TASK_STATE_SCHEMA_VERSION = "astrabridge-task-state-v1"
DEFAULT_HANDOFF_POLICY = "multi_provider_handoff"
AUTO_INJECTED_CONTEXT_NAME_MARKERS = (
    "--- astrabridge project context pack",
    "astrabridge project context pack",
    "--- astrabridge asset context pack",
    "astrabridge asset context pack",
    "freshness rule:",
)


class TaskService:
    """User-facing task state over internal provider-specific Codex threads.

    A task is what the user perceives as one conversation or objective. Each
    task may use multiple internal Codex threads, one per provider/model route.
    Provider switching should therefore preserve the task and only change the
    active provider thread.
    """

    def __init__(self, project_service) -> None:
        self._projects = project_service

    def snapshot(self) -> dict[str, Any]:
        state = self._state()
        current = self.current_task()
        return {
            "schema_version": TASK_STATE_SCHEMA_VERSION,
            "current_task": current,
            "tasks": list(state.get("tasks") or []),
            "updated_at": state.get("updated_at"),
        }

    def ensure_default_task(self, *, thread_id: str | None = None, title: str | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        project = self._project()
        state = self._state()
        tasks = list(state.get("tasks") or [])
        current_task_id = str(project.get("current_task_id") or state.get("current_task_id") or "")
        task = self._find_task(tasks, current_task_id)
        if not task:
            task = self._new_task(title or project.get("name") or "New task")
            tasks.insert(0, task)
            current_task_id = str(task["task_id"])
        if thread_id:
            task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role="provider", make_active=True)
        state["tasks"] = self._replace_task(tasks, task)
        state["current_task_id"] = current_task_id
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def create_task(self, title: str | None = None, *, thread_id: str | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self._new_task(title or "New task")
        if thread_id:
            task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role="provider", make_active=True)
        state = self._state()
        tasks = [item for item in list(state.get("tasks") or []) if item.get("task_id") != task.get("task_id")]
        tasks.insert(0, task)
        state["tasks"] = tasks[:100]
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def switch_task(self, task_id: str) -> dict[str, Any]:
        state = self._state()
        tasks = list(state.get("tasks") or [])
        task = self._find_task(tasks, task_id)
        if not task:
            raise ValueError("Task not found.")
        task["updated_at"] = now_iso()
        state["tasks"] = self._replace_task(tasks, task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def update_current_task_title(self, title: str) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        clean_title = str(title or "").strip()
        if not clean_title:
            raise ValueError("Task title cannot be empty.")
        redacted_title = str(redact_sensitive(clean_title)).strip()
        if SECRET_RE.search(redacted_title):
            raise SecurityError("Secret-like content is not allowed in task titles.")
        task["title"] = redacted_title[:160]
        task["updated_at"] = now_iso()
        self._save_task(task)
        return task

    def current_task(self) -> dict[str, Any] | None:
        project = self._project()
        state = self._state()
        task_id = str(project.get("current_task_id") or state.get("current_task_id") or "")
        task = self._find_task(list(state.get("tasks") or []), task_id)
        if task:
            normalized_task, changed = self._normalize_task(task)
            if changed:
                state["tasks"] = self._replace_task(list(state.get("tasks") or []), normalized_task)
                state["current_task_id"] = normalized_task["task_id"]
                state["updated_at"] = now_iso()
                self._write_state(state)
                self._sync_project_current_task(normalized_task)
            elif self._project_sync_needed(normalized_task):
                self._sync_project_current_task(normalized_task)
            return normalized_task
        return None

    def reconcile_after_project_reload(self, *, preferred_thread_id: str | None = None) -> dict[str, Any] | None:
        """Re-anchor task pointers after project reopen or checkpoint restore."""
        state = self._state()
        tasks = [dict(item) for item in list(state.get("tasks") or []) if isinstance(item, dict)]
        if not tasks:
            return None
        normalized_tasks: list[dict[str, Any]] = []
        changed = False
        for item in tasks:
            normalized, item_changed = self._normalize_task(item)
            normalized_tasks.append(normalized)
            changed = changed or item_changed or normalized != item
        project = self._project()
        selected = self._select_reloaded_task(
            normalized_tasks,
            current_task_id=str(project.get("current_task_id") or state.get("current_task_id") or ""),
            preferred_thread_id=str(preferred_thread_id or project.get("current_thread_id") or "").strip(),
        )
        if not selected:
            return None
        selected_id = str(selected.get("task_id") or "").strip()
        if str(state.get("current_task_id") or "") != selected_id:
            state["current_task_id"] = selected_id
            changed = True
        if normalized_tasks != list(state.get("tasks") or []):
            state["tasks"] = normalized_tasks
            changed = True
        if changed:
            state["updated_at"] = now_iso()
            self._write_state(state)
        if self._project_sync_needed(selected):
            self._sync_project_current_task(selected)
        return selected

    def bind_thread(
        self,
        *,
        thread_id: str,
        settings: dict[str, Any] | None = None,
        role: str = "provider",
        title: str | None = None,
        make_active: bool = True,
    ) -> dict[str, Any]:
        task = self.ensure_default_task(title=title, settings=settings)
        task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role=role, make_active=make_active)
        state = self._state()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def find_provider_thread(
        self,
        *,
        profile_id: str | None,
        provider_id: str | None = None,
        model: str | None,
        effort: str | None,
    ) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        desired_profile = str(profile_id or "")
        desired_provider = str(provider_id or "").strip().lower()
        desired_model = _canonical_model_key(model)
        desired_effort = _canonical_effort_key(effort)
        matches: list[dict[str, Any]] = []
        for item in list(task.get("provider_threads") or []):
            if item.get("missing_at"):
                continue
            if not _provider_thread_entry_is_plausible(item):
                continue
            item_profile = str(item.get("profile_id") or "")
            item_provider = str(item.get("provider_id") or "").strip().lower()
            if desired_profile and item_profile != desired_profile:
                if not desired_provider or item_provider != desired_provider:
                    continue
            elif not desired_profile and desired_provider and item_provider != desired_provider:
                continue
            if desired_model and _canonical_model_key(item.get("model")) != desired_model:
                continue
            if desired_effort and _canonical_effort_key(item.get("reasoning_effort")) != desired_effort:
                continue
            matches.append(dict(item))
        if not matches:
            return None
        matches.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return matches[0]

    def active_provider_thread(self, *, include_missing_fallback: bool = False) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        active_thread_id = str(task.get("active_provider_thread_id") or "")
        provider_threads = [dict(item) for item in list(task.get("provider_threads") or [])]
        for item in provider_threads:
            if (
                str(item.get("thread_id") or "") == active_thread_id
                and not item.get("missing_at")
                and _provider_thread_entry_is_plausible(item)
            ):
                return dict(item)
        if not include_missing_fallback:
            return None
        project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
        if project_thread_id:
            for item in provider_threads:
                if str(item.get("thread_id") or "") == project_thread_id:
                    return dict(item)
        live_threads = [
            item for item in provider_threads if not item.get("missing_at") and _provider_thread_entry_is_plausible(item)
        ]
        if live_threads:
            live_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return dict(live_threads[0])
        if provider_threads:
            provider_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return dict(provider_threads[0])
        return None

    def visible_provider_thread_id(self, *, include_missing_fallback: bool = False) -> str:
        """Return the best secret-free visible provider thread hint for the current task."""
        task = self.current_task()
        if not task:
            return ""
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        if active_thread_id:
            return active_thread_id
        fallback = self.active_provider_thread(include_missing_fallback=include_missing_fallback)
        return str((fallback or {}).get("thread_id") or "").strip()

    def restore_active_provider_thread(self, thread_id: str) -> dict[str, Any] | None:
        """Restore UI focus without mutating thread metadata or missing diagnostics."""
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return self.current_task()
        task = self.current_task()
        if not task:
            return None
        task["active_provider_thread_id"] = clean_thread_id
        task["updated_at"] = now_iso()
        state = self._state()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def force_visible_provider_thread(self, thread_id: str) -> dict[str, Any] | None:
        """Force the visible task/project pointers onto a known provider thread.

        This is intentionally stronger than restore_active_provider_thread() and is
        only meant for supervisor-style actions such as direct MCP tool calls,
        where we want to preserve the user's visible task continuity even if the
        source provider thread has been marked missing in the runtime.
        """
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return self.current_task()
        project = self._project()
        state = self._state()
        task_id = str(project.get("current_task_id") or state.get("current_task_id") or "")
        task = self._find_task(list(state.get("tasks") or []), task_id)
        if not task:
            return None
        task["active_provider_thread_id"] = clean_thread_id
        task["updated_at"] = now_iso()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def needs_provider_handoff(self, *, thread_id: str | None, profile_id: str | None, model: str | None, effort: str | None) -> bool:
        if not thread_id:
            return False
        task = self.ensure_default_task(thread_id=thread_id)
        current = None
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == str(thread_id):
                current = item
                break
        if not current:
            return False
        if not current.get("profile_id") and not current.get("model") and not current.get("reasoning_effort"):
            return False
        if profile_id and str(current.get("profile_id") or "") != str(profile_id):
            return True
        if model and _canonical_model_key(current.get("model")) != _canonical_model_key(model):
            return True
        if effort and _canonical_effort_key(current.get("reasoning_effort")) != _canonical_effort_key(effort):
            return True
        return False

    def record_provider_handoff(
        self,
        *,
        from_thread_id: str | None,
        to_thread_id: str,
        settings: dict[str, Any],
        reused_existing: bool,
        context_budget_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.bind_thread(thread_id=to_thread_id, settings=settings, role="provider", make_active=True)
        source_settings = self._provider_thread_settings(task, from_thread_id)
        transition = summarize_transition(
            from_provider=str((source_settings or {}).get("provider_id") or "") or None,
            to_provider=str(settings.get("provider_id") or "openai"),
            to_model=str(settings.get("model") or "") or None,
            projection_mode="reused_provider_thread" if reused_existing else "task_context_fresh_thread",
            reasoning_effort=str(settings.get("reasoning_effort") or "") or None,
            context_budget_report=context_budget_report,
        )
        event = {
            "event_id": new_id("handoff"),
            "type": "provider_handoff",
            "handoff_policy": DEFAULT_HANDOFF_POLICY,
            "from_thread_id": from_thread_id,
            "to_thread_id": to_thread_id,
            "profile_id": settings.get("profile_id"),
            "provider_id": settings.get("provider_id"),
            "model": settings.get("model"),
            "reasoning_effort": settings.get("reasoning_effort"),
            "permission_mode": settings.get("permission_mode"),
            "reused_existing": reused_existing,
            "transition_summary": transition.to_dict(),
            "created_at": now_iso(),
        }
        handoff_events = list(task.get("handoff_events") or [])
        handoff_events.append(event)
        task["handoff_events"] = handoff_events[-80:]
        task["updated_at"] = now_iso()
        state = self._state()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return event

    def _provider_thread_settings(self, task: dict[str, Any] | None, thread_id: str | None) -> dict[str, Any] | None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id or not isinstance(task, dict):
            return None
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                return dict(item)
        return None

    def mark_provider_thread_missing(self, thread_id: str, *, reason: str | None = None) -> None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return
        task = self.current_task()
        if not task:
            return
        updated = False
        provider_threads: list[dict[str, Any]] = []
        for item in list(task.get("provider_threads") or []):
            entry = dict(item)
            if str(entry.get("thread_id") or "") == clean_thread_id:
                entry["missing_at"] = now_iso()
                entry["missing_reason"] = str(reason or "app_server_thread_not_found")
                updated = True
            provider_threads.append(entry)
        if not updated:
            return
        task["provider_threads"] = self._prune_provider_threads(provider_threads)
        if str(task.get("active_provider_thread_id") or "") == clean_thread_id:
            task["active_provider_thread_id"] = None
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_goal(self, thread_id: str, goal: Any) -> None:
        task = self.ensure_default_task(thread_id=thread_id)
        task["goal"] = redact_sensitive(goal)
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_plan(self, thread_id: str, plan: dict[str, Any]) -> None:
        task = self.ensure_default_task(thread_id=thread_id)
        task["plan"] = redact_sensitive(plan)
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        task = self.current_task()
        if not task:
            return
        refs = list(task.get("checkpoint_refs") or [])
        refs.insert(
            0,
            {
                "save_id": checkpoint.get("save_id"),
                "description": checkpoint.get("description") or checkpoint.get("default_description"),
                "created_at": checkpoint.get("created_at") or now_iso(),
            },
        )
        task["checkpoint_refs"] = refs[:40]
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_context_ref(self, *, pack_type: str, path: str, generated_at: str, summary: dict[str, Any] | None = None) -> None:
        task = self.current_task()
        if not task:
            return
        ref = {
            "pack_type": str(pack_type or "").strip() or "context",
            "path": str(path or "").strip(),
            "generated_at": str(generated_at or "").strip() or now_iso(),
            "summary": dict(summary or {}),
        }
        refs = [item for item in list(task.get("context_pack_refs") or []) if not self._same_context_ref(item, ref)]
        refs.insert(0, ref)
        task["context_pack_refs"] = refs[:20]
        if ref["pack_type"] == "asset":
            asset_refs = [item for item in list(task.get("asset_context_refs") or []) if not self._same_context_ref(item, ref)]
            asset_refs.insert(0, ref)
            task["asset_context_refs"] = asset_refs[:10]
        task["updated_at"] = now_iso()
        self._save_task(task)

    def _new_task(self, title: str) -> dict[str, Any]:
        project = self._project()
        task_id = new_id("task")
        now = now_iso()
        return {
            "schema_version": TASK_STATE_SCHEMA_VERSION,
            "task_id": task_id,
            "project_id": project.get("project_id"),
            "title": str(title or "New task").strip() or "New task",
            "status": "active",
            "handoff_policy": DEFAULT_HANDOFF_POLICY,
            "active_provider_thread_id": None,
            "provider_threads": [],
            "fork_threads": [],
            "handoff_events": [],
            "goal": None,
            "plan": None,
            "checkpoint_refs": [],
            "asset_context_refs": [],
            "context_pack_refs": [],
            "created_at": now,
            "updated_at": now,
        }

    def _bind_thread_to_task(
        self,
        task: dict[str, Any],
        *,
        thread_id: str,
        settings: dict[str, Any],
        role: str,
        make_active: bool,
    ) -> dict[str, Any]:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return task
        now = now_iso()
        hint = self._thread_context_hint(clean_thread_id)
        prior_entry: dict[str, Any] = {}
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                prior_entry = dict(item)
                break
        explicit_settings = {key: value for key, value in dict(settings or {}).items() if value is not None}
        merged_settings = {
            **{key: value for key, value in prior_entry.items() if value is not None},
            **{key: value for key, value in hint.items() if value is not None},
            **explicit_settings,
        }
        # Cache hints can be stale after provider handoffs or minimal visual turns.
        # Preserve an existing thread route unless this bind call explicitly
        # changes it; otherwise Kimi/DeepSeek metadata can bleed across providers.
        for route_key in (
            "profile_id",
            "provider_id",
            "model",
            "reasoning_effort",
            "permission_mode",
            "collaboration_mode",
            "execution_backend",
            "name",
        ):
            if route_key not in explicit_settings and prior_entry.get(route_key) is not None:
                merged_settings[route_key] = prior_entry.get(route_key)
        provider_id = merged_settings.get("provider_id")
        thread_entry = {
            "thread_id": clean_thread_id,
            "role": role or "provider",
            "profile_id": merged_settings.get("profile_id"),
            "provider_id": provider_id,
            "model": _display_model_id(merged_settings.get("model")),
            "reasoning_effort": _display_effort(merged_settings.get("reasoning_effort"), provider_id),
            "permission_mode": merged_settings.get("permission_mode"),
            "collaboration_mode": merged_settings.get("collaboration_mode"),
            "execution_backend": merged_settings.get("execution_backend"),
            "name": _display_thread_name(merged_settings.get("name"), provider_id),
            "updated_at": now,
        }
        existing = []
        created_at = now
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                created_at = str(item.get("created_at") or now)
                continue
            existing.append(item)
        thread_entry["created_at"] = created_at
        existing.insert(0, thread_entry)
        task["provider_threads"] = self._prune_provider_threads(existing)
        if role == "fork":
            fork_threads = [item for item in list(task.get("fork_threads") or []) if str(item.get("thread_id") or "") != clean_thread_id]
            fork_threads.insert(0, thread_entry)
            task["fork_threads"] = fork_threads[:40]
        if make_active:
            task["active_provider_thread_id"] = clean_thread_id
        if task.get("goal") is None and hint.get("goal") is not None:
            task["goal"] = redact_sensitive(hint.get("goal"))
        if task.get("plan") is None and hint.get("latest_plan") is not None:
            task["plan"] = redact_sensitive(hint.get("latest_plan"))
        task["updated_at"] = now
        return task

    def _prune_provider_threads(self, provider_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep task continuity records compact by route, not by raw thread count.

        The user-visible task should feel like one continuous chat even if app-server
        restarts or provider handoffs produce replacement internal threads. Keep the
        newest live thread per route and at most one recent missing diagnostic per
        route so context packs do not accumulate dozens of effectively equivalent
        provider-thread records.
        """
        seen_live_routes: set[tuple[str, str, str, str, str, str, str]] = set()
        seen_missing_routes: set[tuple[str, str, str, str, str, str, str]] = set()
        pruned: list[dict[str, Any]] = []
        for item in provider_threads:
            entry = dict(item)
            display_model = _display_model_id(entry.get("model"))
            if display_model is not None:
                entry["model"] = display_model
            display_effort = _display_effort(entry.get("reasoning_effort"), entry.get("provider_id"))
            if display_effort is not None:
                entry["reasoning_effort"] = display_effort
            display_name = _display_thread_name(entry.get("name"), entry.get("provider_id"))
            if display_name is not None or entry.get("name"):
                entry["name"] = display_name
            if not entry.get("missing_at") and not _provider_thread_entry_is_plausible(entry):
                entry["missing_at"] = now_iso()
                entry["missing_reason"] = "provider_model_mismatch"
            route_key = _provider_thread_route_key(entry)
            if entry.get("missing_at"):
                if route_key in seen_missing_routes:
                    continue
                seen_missing_routes.add(route_key)
            else:
                if route_key in seen_live_routes:
                    continue
                seen_live_routes.add(route_key)
                entry.pop("missing_at", None)
                entry.pop("missing_reason", None)
            pruned.append(entry)
        return pruned[:40]

    def _normalize_task(self, task: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        normalized = dict(task)
        changed = False
        original_threads = list(normalized.get("provider_threads") or [])
        pruned_threads = self._prune_provider_threads(original_threads)
        if pruned_threads != original_threads:
            normalized["provider_threads"] = pruned_threads
            changed = True
        original_forks = list(normalized.get("fork_threads") or [])
        pruned_forks = self._prune_fork_threads(original_forks)
        if pruned_forks != original_forks:
            normalized["fork_threads"] = pruned_forks
            changed = True
        original_checkpoints = list(normalized.get("checkpoint_refs") or [])
        pruned_checkpoints = self._dedupe_records(original_checkpoints, key_fields=("save_id",))
        if pruned_checkpoints != original_checkpoints:
            normalized["checkpoint_refs"] = pruned_checkpoints
            changed = True
        original_asset_refs = list(normalized.get("asset_context_refs") or [])
        pruned_asset_refs = self._dedupe_records(original_asset_refs, key_fields=("pack_type", "path"))
        if pruned_asset_refs != original_asset_refs:
            normalized["asset_context_refs"] = pruned_asset_refs
            changed = True
        original_context_refs = list(normalized.get("context_pack_refs") or [])
        pruned_context_refs = self._dedupe_records(original_context_refs, key_fields=("pack_type", "path"))
        if pruned_context_refs != original_context_refs:
            normalized["context_pack_refs"] = pruned_context_refs
            changed = True
        preferred_active_thread_id = self._preferred_active_thread_id(normalized, pruned_threads)
        if str(normalized.get("active_provider_thread_id") or "") != preferred_active_thread_id:
            normalized["active_provider_thread_id"] = preferred_active_thread_id or None
            changed = True
        return normalized, changed

    def _prune_fork_threads(self, fork_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_ids: set[str] = set()
        pruned: list[dict[str, Any]] = []
        for item in fork_threads:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            thread_id = str(entry.get("thread_id") or "").strip()
            if not thread_id or thread_id in seen_ids:
                continue
            seen_ids.add(thread_id)
            pruned.append(entry)
        return pruned[:40]

    def _dedupe_records(self, records: list[Any], *, key_fields: tuple[str, ...], limit: int = 40) -> list[dict[str, Any]]:
        seen: set[tuple[str, ...]] = set()
        deduped: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            key = tuple(str(item.get(field) or "").strip() for field in key_fields)
            if not any(key):
                continue
            if key in seen:
                continue
            seen.add(key)
            deduped.append(dict(item))
        return deduped[:limit]

    def _select_reloaded_task(
        self,
        tasks: list[dict[str, Any]],
        *,
        current_task_id: str,
        preferred_thread_id: str,
    ) -> dict[str, Any] | None:
        existing = self._find_task(tasks, current_task_id)
        if existing:
            return existing
        if preferred_thread_id:
            for task in tasks:
                for item in list(task.get("provider_threads") or []):
                    if str((item or {}).get("thread_id") or "").strip() == preferred_thread_id:
                        return dict(task)
        if tasks:
            tasks = [dict(item) for item in tasks]
            tasks.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return tasks[0]
        return None

    def _preferred_active_thread_id(self, task: dict[str, Any], provider_threads: list[dict[str, Any]]) -> str:
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        live_threads = [
            dict(item)
            for item in provider_threads
            if not item.get("missing_at") and _provider_thread_entry_is_plausible(item)
        ]
        live_ids = {str(item.get("thread_id") or "").strip() for item in live_threads}
        known_ids = {str(item.get("thread_id") or "").strip() for item in provider_threads}
        project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
        current_task_id = str((self._projects.current_project or {}).get("current_task_id") or "").strip()
        task_id = str(task.get("task_id") or "").strip()
        if active_thread_id and active_thread_id in live_ids:
            return active_thread_id
        if task_id and current_task_id == task_id and project_thread_id and project_thread_id in live_ids:
            return project_thread_id
        if project_thread_id and project_thread_id in live_ids:
            return project_thread_id
        if live_threads:
            live_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return str(live_threads[0].get("thread_id") or "").strip()
        if active_thread_id and active_thread_id in known_ids:
            return active_thread_id
        if project_thread_id and project_thread_id in known_ids:
            return project_thread_id
        if provider_threads:
            provider_threads = [dict(item) for item in provider_threads]
            provider_threads.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return str(provider_threads[0].get("thread_id") or "").strip()
        return ""

    def _thread_context_hint(self, thread_id: str) -> dict[str, Any]:
        """Return secret-free task continuity hints for a known Codex thread."""
        if not thread_id:
            return {}
        shell_root = self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME
        merged: dict[str, Any] = {}
        context_state = read_json(shell_root / "project_context_state.json", {})
        context_threads = context_state.get("threads") if isinstance(context_state, dict) else None
        if isinstance(context_threads, dict):
            context_entry = context_threads.get(thread_id)
            if isinstance(context_entry, dict):
                merged.update(context_entry)
        thread_cache = read_json(shell_root / "thread_cache.json", {})
        cache_entry = (thread_cache.get("by_id") or {}).get(thread_id) if isinstance(thread_cache, dict) else None
        if isinstance(cache_entry, dict):
            merged.update({key: value for key, value in cache_entry.items() if value is not None})
        provider_id = merged.get("provider_id")
        if not provider_id:
            model_text = str(merged.get("model") or "")
            if "/" in model_text:
                provider_id = model_text.split("/", 1)[0]
        return redact_sensitive(
            {
                "profile_id": merged.get("profile_id"),
                "provider_id": provider_id,
                "model": merged.get("model"),
                "reasoning_effort": merged.get("reasoning_effort"),
                "permission_mode": merged.get("permission_mode"),
                "collaboration_mode": merged.get("collaboration_mode"),
                "name": merged.get("name"),
                "goal": merged.get("goal"),
                "latest_plan": merged.get("latest_plan"),
            }
        )

    def _save_task(self, task: dict[str, Any]) -> None:
        state = self._state()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)

    def _sync_project_current_task(self, task: dict[str, Any]) -> None:
        self._projects.reconcile_task_projection(task)

    def _project_sync_needed(self, task: dict[str, Any]) -> bool:
        project = self._project()
        task_id = str(task.get("task_id") or "")
        active_thread = str(task.get("active_provider_thread_id") or "")
        return (
            str(project.get("current_task_id") or "") != task_id
            or str(project.get("current_thread_id") or "") != active_thread
        )

    def _replace_task(self, tasks: list[dict[str, Any]], task: dict[str, Any]) -> list[dict[str, Any]]:
        return [task, *[item for item in tasks if item.get("task_id") != task.get("task_id")]][:100]

    def _same_context_ref(self, left: Any, right: Any) -> bool:
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        return (
            str(left.get("pack_type") or "") == str(right.get("pack_type") or "")
            and str(left.get("path") or "") == str(right.get("path") or "")
        )

    def _find_task(self, tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
        if not task_id:
            return None
        for task in tasks:
            if str(task.get("task_id") or "") == task_id:
                return dict(task)
        return None

    def _state(self) -> dict[str, Any]:
        state = dict(read_json(self._path(), {"schema_version": TASK_STATE_SCHEMA_VERSION, "current_task_id": None, "tasks": []}))
        state.setdefault("schema_version", TASK_STATE_SCHEMA_VERSION)
        state.setdefault("tasks", [])
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        self._reject_secret_like(state)
        write_json(self._path(), state)

    def _path(self) -> Path:
        return self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME / "tasks.json"

    def _project(self) -> dict[str, Any]:
        project = self._projects.current_project
        if not project:
            raise ValueError("No project is open.")
        return dict(project)

    def _reject_secret_like(self, payload: dict[str, Any]) -> None:
        serialized = str(redact_sensitive(payload))
        if SECRET_RE.search(serialized):
            raise SecurityError("Secret-like content is not allowed in task records.")


def _canonical_model_key(model: Any) -> str:
    """Normalize display/provider-prefixed model ids for provider-thread reuse only."""
    text = str(model or "").strip().lower()
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _display_model_id(model: Any) -> str | None:
    text = str(model or "").strip()
    if not text:
        return None
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _canonical_effort_key(effort: Any) -> str:
    text = str(effort or "").strip().lower()
    if text == "max":
        return "xhigh"
    return text


def _display_effort(effort: Any, provider_id: Any = None) -> str | None:
    text = str(effort or "").strip()
    if not text:
        return None
    provider = str(provider_id or "").strip().lower()
    if provider.startswith("deepseek") and text.lower() in {"xhigh", "x-high"}:
        return "max"
    return text


def _display_thread_name(name: Any, provider_id: Any = None) -> str | None:
    text = str(name or "").strip()
    if not text:
        return None
    flattened = text.replace("\r", "\n")
    candidate_lines = [line.strip() for line in flattened.splitlines() if line.strip()]
    first_line = candidate_lines[0] if candidate_lines else ""
    lowered_first_line = first_line.lower()
    for marker in AUTO_INJECTED_CONTEXT_NAME_MARKERS:
        if marker in lowered_first_line:
            prefix = first_line[:lowered_first_line.index(marker)].strip(" -:\t")
            first_line = prefix or ""
            break
    if not first_line:
        provider = str(provider_id or "").strip()
        return f"{provider.title() or 'Provider'} thread"
    if first_line.lower().startswith(("astrabridge minimal visual mode:", "lcr minimal visual mode:")):
        provider = str(provider_id or "").strip()
        return f"{provider.title() or 'Provider'} visual review"
    if len(first_line) > 96:
        return f"{first_line[:93].rstrip()}..."
    return first_line


def _provider_thread_entry_is_plausible(item: dict[str, Any]) -> bool:
    """Reject obvious provider/model mismatches left by older handoff bugs.

    Keep this intentionally conservative. OpenAI-compatible providers such as
    Yunwu legitimately expose OpenAI-named models, while a Kimi thread with a
    DeepSeek model cannot be replayed or reused safely.
    """
    provider = str(item.get("provider_id") or "").strip().lower()
    profile = str(item.get("profile_id") or "").strip().lower()
    raw_model = str(item.get("model") or "").strip().lower()
    model = _canonical_model_key(raw_model)
    if not model or (not provider and not profile):
        return True
    if provider.startswith("deepseek"):
        return model.startswith("deepseek")
    if provider in {"kimi", "moonshot"} or profile.startswith(("kimi", "moonshot")):
        return model.startswith(("kimi", "moonshot"))
    if provider in {"qwen", "dashscope"} or profile.startswith(("qwen", "dashscope")):
        return model.startswith("qwen")
    return True


def _provider_thread_route_key(item: dict[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    provider = str(item.get("provider_id") or "").strip().lower()
    model = _canonical_model_key(item.get("model"))
    if not provider and "/" in model:
        provider = model.split("/", 1)[0]
    permission_mode = str(item.get("permission_mode") or "").strip().lower()
    collaboration_mode = str(item.get("collaboration_mode") or "").strip().lower()
    execution_backend = str(item.get("execution_backend") or "").strip().lower() or "app_server"
    role = str(item.get("role") or "provider").strip().lower()
    return (
        provider,
        model,
        _canonical_effort_key(item.get("reasoning_effort")),
        permission_mode,
        collaboration_mode,
        execution_backend,
        role,
    )

