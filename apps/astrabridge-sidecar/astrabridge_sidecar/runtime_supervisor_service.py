from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import now_iso
from .providers import classify_runtime_failure
from .runtime_observability import (
    build_runtime_observability_summary,
    build_runtime_support_bundle,
    load_external_operations_for_observability,
    persist_runtime_observability_summary,
    persist_runtime_support_bundle,
)
from .security import redact_sensitive


class RuntimeSupervisorService:
    """Compact, sanitized runtime state for the desktop inspector and guards."""

    def __init__(self, project_service, runtime_service, modal_service, dogfood_service, automation_service: Any | None = None) -> None:
        self._projects = project_service
        self._runtime = runtime_service
        self._modals = modal_service
        self._dogfood = dogfood_service
        self._automations = automation_service
        self._auto_paused_turns: set[str] = set()
        self._guard_events_seen: set[str] = set()

    def status(self, thread_id: str | None = None, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        refresh_current_project = getattr(self._projects, "refresh_current_project", None)
        if callable(refresh_current_project):
            current_project = refresh_current_project() or self._projects.current_project or {}
        else:
            current_project = self._projects.current_project or {}
        requested_thread_id = str(thread_id or self._active_task_thread_id() or current_project.get("current_thread_id") or "")
        selected_thread_id = self._effective_thread_id_for_status(requested_thread_id, profile)
        events = self._runtime.list_events(after=0).get("events", [])
        plan = self._latest_plan(events, selected_thread_id)
        token = self._latest_token_usage(events, selected_thread_id)
        thread_status = self._latest_thread_status(events, selected_thread_id)
        thread_snapshot = self._thread_snapshot(selected_thread_id, profile)
        thread_status = self._normalize_thread_status_from_snapshot(thread_status, thread_snapshot)
        current_task = self._current_task()
        runtime_error = self._latest_runtime_error(
            events,
            selected_thread_id,
            thread_status,
            thread_snapshot=thread_snapshot,
            profile=profile,
        )
        compaction = self._latest_compaction(events, selected_thread_id)
        pending_modals = [
            item
            for item in self._modals.list_pending().get("modals", [])
            if not selected_thread_id or item.get("thread_id") == selected_thread_id
        ]
        waiting_on_approval = self._thread_waiting_on_approval(thread_status) or bool(pending_modals)
        watchdog = self._turn_watchdog(events, selected_thread_id, thread_status, waiting_on_approval=waiting_on_approval)
        guard = self._guard(token, thread_status, compaction, waiting_on_approval=waiting_on_approval)
        if guard.get("should_pause") and selected_thread_id and profile:
            guard = {
                **guard,
                "auto_pause": self._auto_pause_guard(profile, selected_thread_id, token),
            }
        self._record_guard_event(selected_thread_id, token, guard)
        dogfood = self._dogfood.snapshot().get("run", {})
        browser = self._latest_browser_smoke(dogfood)
        workspace_root = self._workspace_root()
        environment = {
            "project_name": current_project.get("name") or "",
            "cwd": str(workspace_root) if workspace_root else "",
            "git": self._git_summary(workspace_root),
            "provider": (profile or {}).get("provider_id") or current_project.get("default_profile_id") or "",
            "model": (profile or {}).get("model") or current_project.get("default_model") or "",
            "effort": (profile or {}).get("reasoning_effort") or current_project.get("default_effort") or "",
            "permission": current_project.get("ui_preferences", {}).get("permission_mode") or "",
            "mcp": self._mcp_summary(events),
        }
        observability = build_runtime_observability_summary(
            events,
            workspace_root=workspace_root,
            current_task=current_task,
            thread_id=selected_thread_id,
            external_operations=self._external_operations(),
            configured_models=self._configured_models_for_observability(),
            selected_profile=profile or {},
        )
        persist_runtime_observability_summary(observability, workspace_root=workspace_root)
        support_bundle = build_runtime_support_bundle(
            observability_summary=observability,
            runtime_events=events,
            workspace_root=workspace_root,
            environment=environment,
            thread_status=thread_status,
            runtime_error=runtime_error,
            guard=guard,
            watchdog=watchdog,
        )
        support_bundle_paths = persist_runtime_support_bundle(support_bundle, workspace_root=workspace_root)
        return redact_sensitive(
            {
                "thread_id": selected_thread_id,
                "requested_thread_id": requested_thread_id,
                "effective_thread_id": selected_thread_id,
                "updated_at": now_iso(),
                "plan": plan,
                "token": token,
                "guard": guard,
                "watchdog": watchdog,
                "thread_status": thread_status,
                "runtime_error": runtime_error,
                "compaction": compaction,
                "observability": observability,
                "support_bundle": {
                    **support_bundle,
                    "artifact_paths": support_bundle_paths or {},
                },
                "environment": environment,
                "browser": browser,
                "dogfood": {
                    "enabled": bool(dogfood.get("enabled")),
                    "phase": dogfood.get("phase") or "",
                    "status": dogfood.get("status") or "",
                    "current_provider": dogfood.get("current_provider") or "",
                    "next_step": dogfood.get("next_step") or "",
                    "usage": dogfood.get("usage") or {},
                    "budgets": dogfood.get("budgets") or {},
                    "latest_milestone": self._latest(dogfood.get("milestones") or []),
                },
                "modal": {
                    "pending_count": len(pending_modals),
                    "current": pending_modals[0] if pending_modals else None,
                },
                "automations": self._automation_summary(),
            }
        )

    def _automation_summary(self) -> dict[str, Any]:
        if self._automations is None:
            return {
                "scheduler": {"running": False, "active_run_count": 0, "next_wake_up_at": None},
                "active_runs": [],
                "last_failure": None,
                "next_due": None,
                "inbox_summary": {"unread": 0, "reviewed": 0, "archived": 0, "promoted": 0},
            }
        try:
            return dict(self._automations.status_summary())
        except Exception as exc:  # noqa: BLE001
            return {
                "scheduler": {"running": False, "active_run_count": 0, "next_wake_up_at": None},
                "active_runs": [],
                "last_failure": {"summary": "automation_status_unavailable", "redacted_error": str(exc)[:240]},
                "next_due": None,
                "inbox_summary": {"unread": 0, "reviewed": 0, "archived": 0, "promoted": 0},
            }

    def _active_task_thread_id(self) -> str:
        tasks = getattr(self._runtime, "_tasks", None)
        if tasks is None:
            return ""
        try:
            active_thread = tasks.active_provider_thread(include_missing_fallback=False)
            if active_thread:
                return str(active_thread.get("thread_id") or "").strip()
            # current_task() may normalize stale task state as a side effect, but
            # do not trust the raw active_provider_thread_id after
            # active_provider_thread() has rejected it as missing or implausible.
            tasks.current_task()
        except Exception:
            return ""
        return ""

    def _current_task(self) -> dict[str, Any] | None:
        tasks = getattr(self._runtime, "_tasks", None)
        if tasks is None:
            return None
        try:
            task = tasks.current_task() or {}
        except Exception:
            return None
        return dict(task) if isinstance(task, dict) else None

    def _external_operations(self) -> list[dict[str, Any]]:
        tasks = getattr(self._runtime, "_tasks", None)
        if tasks is None:
            return []
        try:
            store = tasks.durable_run_store()
        except Exception:
            return []
        return load_external_operations_for_observability(getattr(store, "db_path", None))

    def _configured_models_for_observability(self) -> list[dict[str, Any]]:
        router_config = getattr(self._runtime, "_router_config", None)
        if router_config is None:
            return []
        models = getattr(router_config, "models", None)
        if not callable(models):
            return []
        try:
            return [dict(item) for item in list(models() or []) if isinstance(item, dict)]
        except Exception:
            return []

    def _effective_thread_id_for_status(self, requested_thread_id: str, profile: dict[str, Any] | None) -> str:
        clean_requested = str(requested_thread_id or "")
        tasks = getattr(self._runtime, "_tasks", None)
        if tasks is None or not profile:
            return clean_requested
        current = None
        try:
            current_task = tasks.current_task() or {}
            for item in list(current_task.get("provider_threads") or []):
                if str(item.get("thread_id") or "") == clean_requested:
                    current = dict(item)
                    break
        except Exception:
            current = None
        desired_profile = str((profile or {}).get("profile_id") or "")
        desired_provider = str((profile or {}).get("provider_id") or "")
        desired_model = str((profile or {}).get("model") or "")
        desired_effort = str((profile or {}).get("reasoning_effort") or "")
        try:
            if clean_requested and current and not current.get("missing_at") and not tasks.needs_provider_handoff(
                thread_id=clean_requested,
                profile_id=desired_profile,
                model=desired_model,
                effort=desired_effort,
            ):
                return clean_requested
            reusable = tasks.find_provider_thread(
                profile_id=desired_profile,
                provider_id=desired_provider,
                model=desired_model,
                effort=desired_effort,
            )
            reusable_thread_id = str((reusable or {}).get("thread_id") or "")
            if reusable_thread_id:
                return reusable_thread_id
        except Exception:
            return clean_requested
        return clean_requested

    def decision(self, payload: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action") or "").strip().lower()
        thread_id = str(payload.get("thread_id") or "").strip()
        turn_id = str(payload.get("turn_id") or "").strip()
        if action not in {"continue", "compact", "fork", "interrupt"}:
            raise ValueError("Supervisor decision must be continue, compact, fork, or interrupt.")
        result: dict[str, Any] = {"action": action, "thread_id": thread_id, "updated_at": now_iso()}
        if action == "compact":
            result["result"] = self._runtime.compact_thread(profile, thread_id)
            result["health_check"] = {
                "recommended": True,
                "prompt": "After compaction, send a short health check turn before continuing a long task.",
            }
        elif action == "fork":
            result["result"] = self._runtime.fork_thread(
                profile,
                thread_id=thread_id,
                model=payload.get("model"),
                effort=payload.get("effort"),
                permission_mode=str(payload.get("permission_mode") or "auto"),
                name=str(payload.get("name") or "Context guard fork"),
            )
        elif action == "interrupt":
            result["result"] = self._runtime.interrupt_turn(profile, thread_id, turn_id)
        else:
            allow_continue = getattr(self._runtime, "allow_context_guard_continue_once", None)
            if callable(allow_continue):
                result["result"] = allow_continue(thread_id)
            else:
                result["result"] = {"continued": True}
        self._dogfood.add_note(
            f"Runtime supervisor decision: {action} for thread {thread_id or 'unknown'}."
        )
        return redact_sensitive(result)

    def _workspace_root(self) -> Path | None:
        try:
            return self._projects.require_workspace_root()
        except Exception:
            return None

    def _latest_plan(self, events: list[dict[str, Any]], thread_id: str) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.get("type") != "notification" or event.get("method") != "turn/plan/updated":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            return {
                "thread_id": str(params.get("threadId") or ""),
                "turn_id": str(params.get("turnId") or ""),
                "explanation": params.get("explanation"),
                "steps": list(params.get("plan") or []),
                "last_updated_at": event.get("timestamp"),
                "source": "turn/plan/updated",
            }
        deltas: list[str] = []
        latest_turn_id = ""
        latest_timestamp = None
        for event in events:
            if event.get("type") != "notification" or event.get("method") != "item/plan/delta":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            latest_turn_id = str(params.get("turnId") or latest_turn_id)
            latest_timestamp = event.get("timestamp") or latest_timestamp
            deltas.append(str(params.get("delta") or ""))
        live_plan = "".join(deltas).strip()
        if live_plan:
            return {
                "thread_id": thread_id,
                "turn_id": latest_turn_id,
                "explanation": live_plan,
                "steps": self._steps_from_live_plan(live_plan),
                "last_updated_at": latest_timestamp,
                "source": "item/plan/delta",
            }
        return self._task_plan_fallback(thread_id)

    def _task_plan_fallback(self, thread_id: str) -> dict[str, Any] | None:
        tasks = getattr(self._runtime, "_tasks", None)
        if tasks is None:
            return None
        try:
            task = tasks.current_task() or {}
        except Exception:
            return None
        plan = task.get("plan")
        if not isinstance(plan, dict):
            return None
        steps = plan.get("steps")
        if isinstance(steps, str):
            steps = self._steps_from_live_plan(steps)
        elif not isinstance(steps, list):
            steps = []
        if not steps and not str(plan.get("explanation") or "").strip():
            return None
        return {
            "thread_id": thread_id or str(task.get("active_provider_thread_id") or ""),
            "turn_id": str(plan.get("turn_id") or ""),
            "explanation": plan.get("explanation"),
            "steps": list(steps),
            "last_updated_at": plan.get("updated_at") or task.get("updated_at"),
            "source": "task/plan",
        }

    def _latest_token_usage(self, events: list[dict[str, Any]], thread_id: str) -> dict[str, Any]:
        for event in reversed(events):
            if event.get("type") != "notification" or event.get("method") != "thread/tokenUsage/updated":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            usage = params.get("tokenUsage") or {}
            total = usage.get("total") or {}
            last = usage.get("last") or {}
            context_window = int(usage.get("modelContextWindow") or 0)
            cumulative_total_tokens = int(total.get("totalTokens") or 0)
            context_tokens = int(last.get("inputTokens") or last.get("totalTokens") or cumulative_total_tokens or 0)
            context_source = "last.inputTokens" if int(last.get("inputTokens") or 0) > 0 else (
                "last.totalTokens" if int(last.get("totalTokens") or 0) > 0 else "total.totalTokens"
            )
            percent = round((context_tokens / context_window) * 100, 1) if context_window > 0 else 0
            return {
                "total_tokens": context_tokens,
                "context_estimate_tokens": context_tokens,
                "context_estimate_source": context_source,
                "cumulative_total_tokens": cumulative_total_tokens,
                "context_window": context_window,
                "context_percent": percent,
                "turn_id": str(params.get("turnId") or ""),
                "last": last,
                "last_updated_at": event.get("timestamp"),
            }
        return {
            "total_tokens": 0,
            "context_estimate_tokens": 0,
            "context_estimate_source": "",
            "cumulative_total_tokens": 0,
            "context_window": 0,
            "context_percent": 0,
            "turn_id": "",
            "last": {},
            "last_updated_at": None,
        }

    def _latest_thread_status(self, events: list[dict[str, Any]], thread_id: str) -> dict[str, Any]:
        for event in reversed(events):
            if event.get("type") == "provider_thread_missing":
                if thread_id and str(event.get("thread_id") or "") != thread_id:
                    continue
                return {
                    "type": "missing",
                    "thread_id": thread_id,
                    "reason": event.get("reason") or "app_server_thread_not_found",
                    "last_updated_at": event.get("timestamp"),
                }
            if event.get("type") != "notification" or event.get("method") != "thread/status/changed":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            status = dict(params.get("status") or {"type": "unknown"})
            status.setdefault("thread_id", thread_id or str(params.get("threadId") or ""))
            return status
        return {"type": "unknown", "thread_id": thread_id}

    def _latest_runtime_error(
        self,
        events: list[dict[str, Any]],
        thread_id: str,
        thread_status: dict[str, Any],
        *,
        thread_snapshot: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Return the latest sanitized turn/runtime error for inspector notices.

        The app-server reports provider/network failures as ordinary error
        notifications plus a failed turn. Without surfacing this here, the UI
        can look merely idle after a provider timeout.
        """
        status_type = str((thread_status or {}).get("type") or "").lower()
        if self._thread_snapshot_has_stale_completed_failure(thread_snapshot):
            return None
        for event in reversed(events):
            if event.get("type") != "notification":
                continue
            method = str(event.get("method") or "")
            if method not in {"error", "turn/completed", "thread/status/changed"}:
                continue
            params = event.get("params") or {}
            event_thread_id = str(params.get("threadId") or "")
            if thread_id and event_thread_id and event_thread_id != thread_id:
                continue
            raw_message = ""
            turn_id = str(params.get("turnId") or "")
            if method == "error":
                error = params.get("error") or {}
                raw_message = str(error.get("message") or error)
            elif method == "turn/completed":
                turn = params.get("turn") or {}
                completed_status = str(turn.get("status") or "").lower()
                completed_error = turn.get("error")
                # Events are scanned newest first. A successful terminal turn
                # supersedes older error notifications for the same provider lane.
                if completed_status == "completed" and (completed_error is None or completed_error == "" or completed_error == {}):
                    return None
                if completed_status != "failed" and status_type != "systemerror":
                    continue
                turn_id = str(turn.get("id") or turn_id)
                error = completed_error or {}
                raw_message = str(error.get("message") or error)
            elif method == "thread/status/changed":
                status = params.get("status") or {}
                if str(status.get("type") or "").lower() != "systemerror":
                    continue
                raw_message = "Thread entered systemError."
            if not raw_message:
                continue
            normalized = self._normalize_runtime_error(raw_message, profile=profile)
            return {
                **normalized,
                "thread_id": thread_id or event_thread_id,
                "turn_id": turn_id,
                "method": method,
                "last_updated_at": event.get("timestamp"),
            }
        return None

    def _thread_snapshot(self, thread_id: str, profile: dict[str, Any] | None) -> dict[str, Any] | None:
        if not thread_id or not profile:
            return None
        try:
            result = self._runtime.read_thread(profile, thread_id)
        except Exception:
            return None
        thread = result.get("thread") if isinstance(result, dict) else None
        return dict(thread) if isinstance(thread, dict) else None

    def _normalize_thread_status_from_snapshot(
        self,
        thread_status: dict[str, Any],
        thread_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(thread_status, dict):
            return thread_status
        snapshot_status = (thread_snapshot or {}).get("status")
        if isinstance(snapshot_status, dict) and snapshot_status.get("stale_error_normalized"):
            return dict(snapshot_status)
        if not self._thread_snapshot_has_stale_completed_failure(thread_snapshot):
            return thread_status
        normalized = dict(thread_status)
        normalized["type"] = "idle"
        normalized["stale_error_type"] = str(
            ((thread_snapshot or {}).get("status") or {}).get("type") or thread_status.get("type") or "systemError"
        )
        normalized["stale_error_normalized"] = True
        return normalized

    def _thread_snapshot_has_stale_completed_failure(self, thread_snapshot: dict[str, Any] | None) -> bool:
        if not isinstance(thread_snapshot, dict):
            return False
        status = thread_snapshot.get("status")
        if not isinstance(status, dict):
            return False
        if status.get("stale_error_normalized"):
            return True
        if str(status.get("type") or "").lower() not in {"systemerror", "notloaded"}:
            return False
        turns = [item for item in list(thread_snapshot.get("turns") or []) if isinstance(item, dict)]
        if not turns:
            return False
        latest_turn = turns[-1]
        latest_error = latest_turn.get("error")
        return str(latest_turn.get("status") or "").lower() == "completed" and (
            latest_error is None or latest_error == "" or latest_error == {}
        )

    def _normalize_runtime_error(self, raw_message: str, *, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        notice = classify_runtime_failure(
            raw_message,
            current_provider=(profile or {}).get("provider_id"),
            current_model=(profile or {}).get("model"),
        )
        return notice.to_payload()

    def _guard(
        self,
        token: dict[str, Any],
        thread_status: dict[str, Any],
        compaction: dict[str, Any] | None = None,
        *,
        waiting_on_approval: bool = False,
    ) -> dict[str, Any]:
        percent = float(token.get("context_percent") or 0)
        active = str(thread_status.get("type") or "").lower() == "active"
        if self._compaction_is_newer_than_token(compaction, token):
            return {
                "level": "compacted",
                "recommended_action": "health_check",
                "should_pause": False,
                "message": "Context was compacted after the latest token usage update. Send a short health check before continuing a long task.",
                "stale_context_estimate": True,
            }
        if percent >= 90:
            if active and waiting_on_approval:
                return {
                    "level": "approval_wait",
                    "recommended_action": "resolve_approval",
                    "should_pause": False,
                    "message": "Context is above 90%, but the turn is waiting on an approval. Resolve the approval before compacting, forking, or interrupting.",
                }
            if active:
                return {
                    "level": "pause",
                    "recommended_action": "compact",
                    "should_pause": False,
                    "requires_decision": True,
                    "deferred_until_turn_boundary": True,
                    "message": "Context is above 90%. Let the active tool/command finish, then compact, fork, continue once, or interrupt before starting another long turn.",
                }
            return {
                "level": "pause",
                "recommended_action": "compact",
                "should_pause": False,
                "requires_decision": False,
                "message": "Context is above 90%. Choose compact, fork, continue once, or interrupt before the next long action.",
            }
        if percent >= 80:
            return {
                "level": "danger",
                "recommended_action": "compact",
                "should_pause": False,
                "message": "Context is above 80%. Compact or fork before the next long action.",
            }
        if percent >= 70:
            return {
                "level": "warning",
                "recommended_action": "watch",
                "should_pause": False,
                "message": "Context is above 70%. Keep the next turn narrow.",
            }
        return {"level": "ok", "recommended_action": "none", "should_pause": False, "message": ""}

    def _latest_compaction(self, events: list[dict[str, Any]], thread_id: str) -> dict[str, Any] | None:
        latest_started: dict[str, Any] | None = None
        latest_completed: dict[str, Any] | None = None
        latest_non_compaction_timestamp: str | None = None
        for event in events:
            if event.get("type") != "notification":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            item = params.get("item") or {}
            if item.get("type") != "contextCompaction":
                latest_non_compaction_timestamp = str(event.get("timestamp") or latest_non_compaction_timestamp or "")
                continue
            method = str(event.get("method") or "")
            item_id = str(item.get("id") or "")
            if method == "item/started":
                latest_started = {
                    "status": "running",
                    "item_id": item_id,
                    "turn_id": str(params.get("turnId") or ""),
                    "started_at": event.get("timestamp"),
                }
            elif method == "item/completed":
                latest_completed = {
                    "status": "completed",
                    "item_id": item_id,
                    "turn_id": str(params.get("turnId") or ""),
                    "completed_at": event.get("timestamp"),
                }
        if latest_completed and not latest_started:
            return latest_completed
        if latest_completed and latest_started:
            completed_at = self._parse_timestamp(str(latest_completed.get("completed_at") or ""))
            started_at = self._parse_timestamp(str(latest_started.get("started_at") or ""))
            if completed_at is not None and (started_at is None or completed_at >= started_at):
                return latest_completed
        if latest_started and latest_non_compaction_timestamp:
            started_at = self._parse_timestamp(str(latest_started.get("started_at") or ""))
            later_at = self._parse_timestamp(str(latest_non_compaction_timestamp or ""))
            if started_at is not None and later_at is not None and later_at > started_at:
                return {
                    **latest_started,
                    "status": "stale_running",
                    "stale_after": latest_non_compaction_timestamp,
                    "message": "Compaction start was followed by later runtime activity but no completion event; treating it as stale instead of blocking the UI.",
                }
        return latest_started

    def _compaction_is_newer_than_token(self, compaction: dict[str, Any] | None, token: dict[str, Any]) -> bool:
        if not compaction or compaction.get("status") != "completed":
            return False
        compacted_at = self._parse_timestamp(str(compaction.get("completed_at") or ""))
        token_at = self._parse_timestamp(str(token.get("last_updated_at") or ""))
        if compacted_at is None:
            return False
        if token_at is None:
            return True
        return compacted_at > token_at

    def _parse_timestamp(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _turn_watchdog(
        self,
        events: list[dict[str, Any]],
        thread_id: str,
        thread_status: dict[str, Any],
        *,
        waiting_on_approval: bool = False,
    ) -> dict[str, Any]:
        active = str(thread_status.get("type") or "").lower() == "active"
        latest_event = None
        latest_turn_id = ""
        for event in reversed(events):
            if event.get("type") != "notification":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            latest_event = event
            latest_turn_id = str(params.get("turnId") or latest_turn_id)
            break
        if not active or not latest_event:
            return {"level": "ok", "idle_seconds": 0, "recommended_action": "none", "message": "", "turn_id": latest_turn_id}
        idle_seconds = self._seconds_since(str(latest_event.get("timestamp") or ""))
        if waiting_on_approval:
            return {
                "level": "waiting",
                "idle_seconds": idle_seconds,
                "recommended_action": "resolve_approval",
                "message": "Turn is waiting on an approval, not stalled.",
                "turn_id": latest_turn_id,
            }
        if idle_seconds >= 240:
            return {
                "level": "pause",
                "idle_seconds": idle_seconds,
                "recommended_action": "interrupt_or_fork",
                "message": "No runtime delta for 240s. Consider interrupting this turn or forking a smaller follow-up.",
                "turn_id": latest_turn_id,
            }
        if idle_seconds >= 180:
            return {
                "level": "danger",
                "idle_seconds": idle_seconds,
                "recommended_action": "watch_or_interrupt",
                "message": "No runtime delta for 180s. The model may be stalled; prepare to interrupt or fork.",
                "turn_id": latest_turn_id,
            }
        if idle_seconds >= 90:
            return {
                "level": "warning",
                "idle_seconds": idle_seconds,
                "recommended_action": "watch",
                "message": "No runtime delta for 90s. Keep an eye on this long turn.",
                "turn_id": latest_turn_id,
            }
        return {"level": "ok", "idle_seconds": idle_seconds, "recommended_action": "none", "message": "", "turn_id": latest_turn_id}

    def _thread_waiting_on_approval(self, thread_status: dict[str, Any]) -> bool:
        flags = thread_status.get("activeFlags") or thread_status.get("active_flags") or []
        if isinstance(flags, str):
            flags = [flags]
        return any(str(flag).lower() == "waitingonapproval" for flag in flags)

    def _seconds_since(self, iso_timestamp: str) -> int:
        if not iso_timestamp:
            return 0
        try:
            parsed = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
            now = datetime.now(parsed.tzinfo)
            return max(0, int((now - parsed).total_seconds()))
        except Exception:
            return 0

    def _auto_pause_guard(self, profile: dict[str, Any], thread_id: str, token: dict[str, Any]) -> dict[str, Any]:
        turn_id = str(token.get("turn_id") or "").strip()
        key = f"{thread_id}:{turn_id or 'unknown'}"
        if not thread_id or not turn_id:
            return {"attempted": False, "status": "blocked_missing_turn_id"}
        if key in self._auto_paused_turns:
            return {"attempted": True, "status": "already_paused"}
        self._auto_paused_turns.add(key)
        try:
            result = self._runtime.interrupt_turn(profile, thread_id, turn_id)
            self._dogfood.add_note(
                f"Runtime supervisor auto-paused turn {turn_id} at {token.get('context_percent')}% context."
            )
            return {"attempted": True, "status": "interrupted", "result": result}
        except Exception as exc:  # noqa: BLE001
            self._dogfood.add_note(
                f"Runtime supervisor tried to auto-pause turn {turn_id} but failed: {str(exc)[:180]}."
            )
            return {"attempted": True, "status": "failed", "error": str(exc)[:300]}

    def _record_guard_event(self, thread_id: str, token: dict[str, Any], guard: dict[str, Any]) -> None:
        level = str(guard.get("level") or "ok")
        if level == "ok":
            return
        percent = float(token.get("context_percent") or 0)
        bucket = int(percent // 5) * 5
        turn_id = str(token.get("turn_id") or "")
        key = f"{thread_id}:{turn_id}:{level}:{bucket}"
        if key in self._guard_events_seen:
            return
        self._guard_events_seen.add(key)
        try:
            self._runtime.record_supervisor_event(
                {
                    "event": "context_guard",
                    "thread_id": thread_id,
                    "turn_id": turn_id,
                    "level": level,
                    "context_percent": percent,
                    "recommended_action": guard.get("recommended_action"),
                    "should_pause": bool(guard.get("should_pause")),
                }
            )
        except Exception:
            pass

    def _steps_from_live_plan(self, text: str) -> list[dict[str, str]]:
        steps: list[dict[str, str]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(("-", "*")):
                steps.append({"step": line.lstrip("-* ").strip(), "status": "pending"})
            elif len(steps) < 1:
                steps.append({"step": line[:160], "status": "in_progress"})
            if len(steps) >= 8:
                break
        return steps

    def _latest_browser_smoke(self, dogfood: dict[str, Any]) -> dict[str, Any]:
        return self._latest(dogfood.get("browser_smokes") or []) or {
            "status": "not_run",
            "url": "",
            "label": "",
            "console_errors": [],
            "screenshot_path": "",
        }

    def _mcp_summary(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        for event in reversed(events):
            if event.get("type") == "mcp_status_listed":
                return {"status": "listed", "count": event.get("count", 0), "last_updated_at": event.get("timestamp")}
            if event.get("type") == "mcp_reloaded":
                return {"status": "reloaded", "count": None, "last_updated_at": event.get("timestamp")}
        return {"status": "unknown", "count": None, "last_updated_at": None}

    def _git_summary(self, workspace_root: Path | None) -> dict[str, Any]:
        if not workspace_root:
            return {"is_repo": False, "branch": "", "changed_files": 0, "added": 0, "deleted": 0}
        try:
            branch = self._git(workspace_root, ["branch", "--show-current"]).strip()
            status = self._git(workspace_root, ["status", "--short"]).splitlines()
            numstat = self._git(workspace_root, ["diff", "--numstat"]).splitlines()
            added = 0
            deleted = 0
            for line in numstat:
                parts = line.split("\t")
                if len(parts) >= 2:
                    added += int(parts[0]) if parts[0].isdigit() else 0
                    deleted += int(parts[1]) if parts[1].isdigit() else 0
            return {
                "is_repo": True,
                "branch": branch or "detached",
                "changed_files": len(status),
                "added": added,
                "deleted": deleted,
            }
        except Exception:
            return {"is_repo": False, "branch": "", "changed_files": 0, "added": 0, "deleted": 0}

    def _git(self, cwd: Path, args: list[str]) -> str:
        return subprocess.check_output(
            ["git", *args],
            cwd=str(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.DEVNULL,
            timeout=3,
        )

    def _latest(self, values: list[Any]) -> Any | None:
        if not values:
            return None
        return values[-1]

