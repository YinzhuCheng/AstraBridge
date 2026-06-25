from __future__ import annotations

from typing import Any, Callable

from ..common import now_iso
from .runner import AutomationRunner
from .scheduler import AutomationScheduler
from .store import AutomationStore
from .triage import AutomationTriageService
from .workspace import AutomationWorkspaceManager


class AutomationService:
    def __init__(
        self,
        project_service,
        *,
        runtime_service: Any | None = None,
        profile_service: Any | None = None,
        runtime_config: Any | None = None,
        event_recorder: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._projects = project_service
        self._runtime = runtime_service
        self._profiles = profile_service
        self._runtime_config = runtime_config
        self._event_recorder = event_recorder
        self._store = AutomationStore(project_service)
        self._scheduler = AutomationScheduler(self._store)
        self._workspace = AutomationWorkspaceManager(project_service)
        self._runner = AutomationRunner(
            project_service,
            runtime_service=runtime_service,
            profile_service=profile_service,
            runtime_config=runtime_config,
        )
        self._triage = AutomationTriageService(project_service, self._store)

    def start(self) -> dict[str, Any]:
        if not self._has_open_project():
            return self._neutral_scheduler_status(running=False)
        status = self._scheduler.start()
        self._record_event("automation_scheduler_started", {"scheduler": status})
        return status

    def stop(self) -> dict[str, Any]:
        status = self._scheduler.stop()
        self._record_event("automation_scheduler_stopped", {"scheduler": status})
        return status

    def list_automations(self) -> dict[str, Any]:
        self._require_project()
        items = self._store.list_automations()
        return {"automations": items, "count": len(items)}

    def create_automation(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_project()
        created = self._store.create_automation(payload)
        self._record_event("automation_created", {"automation_id": created.get("automation_id")})
        return {"automation": created}

    def update_automation(self, automation_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        self._require_project()
        updated = self._store.update_automation(automation_id, patch)
        self._record_event("automation_updated", {"automation_id": automation_id})
        return {"automation": updated}

    def delete_automation(self, automation_id: str, *, reason: str = "deleted") -> dict[str, Any]:
        self._require_project()
        deleted = self._store.delete_automation(automation_id, reason=reason)
        self._record_event("automation_updated", {"automation_id": automation_id, "archived": True})
        return {"automation": deleted}

    def pause_automation(self, automation_id: str) -> dict[str, Any]:
        self._require_project()
        paused = self._store.pause_automation(automation_id)
        self._record_event("automation_updated", {"automation_id": automation_id, "enabled": False})
        return {"automation": paused}

    def resume_automation(self, automation_id: str) -> dict[str, Any]:
        self._require_project()
        resumed = self._store.resume_automation(automation_id)
        self._record_event("automation_updated", {"automation_id": automation_id, "enabled": True})
        return {"automation": resumed}

    def run_now(self, automation_id: str) -> dict[str, Any]:
        self._require_project()
        self._ensure_scheduler_started()
        queued = self._scheduler.trigger_now(automation_id)
        if not queued:
            raise ValueError("Automation could not be queued.")
        self._record_event(
            "automation_run_queued",
            {
                "automation_id": queued.get("automation_id"),
                "run_id": queued.get("run_id"),
                "trigger": queued.get("trigger"),
            },
        )
        return self.execute_run(str(queued.get("run_id") or ""))

    def execute_run(self, run_id: str) -> dict[str, Any]:
        self._require_project()
        run = self._store.get_run(run_id)
        if not run:
            raise ValueError("Automation run not found.")
        automation = self._store.get_automation(str(run.get("automation_id") or ""))
        if not automation:
            raise ValueError("Automation not found.")
        running_run = self._store.record_run(
            {
                **run,
                "status": "running",
                "started_at": now_iso(),
                "summary": "automation run started",
            }
        )
        self._record_event(
            "automation_run_started",
            {"automation_id": running_run.get("automation_id"), "run_id": running_run.get("run_id")},
        )
        session = None
        try:
            session = self._workspace.prepare_workspace(automation, running_run)
            if session.worktree_path:
                running_run = self._store.record_run({**running_run, "worktree_path": session.worktree_path})
            runner_result = self._runner.execute(automation, running_run, session)
        except Exception as exc:  # noqa: BLE001
            runner_result = {
                **running_run,
                "status": "failed",
                "finished_at": now_iso(),
                "summary": "Automation run failed before execution completed.",
                "redacted_error": str(exc)[:300] or "automation_execute_failed",
                "signal": "unknown",
            }
        cleanup_result = None
        if session is not None and str(runner_result.get("status") or "").lower() != "running":
            classification = self._triage.classify_result(automation, running_run, runner_result)
            cleanup_result = self._workspace.finalize_workspace(
                session,
                signal=classification.get("signal"),
                status=classification.get("status"),
            )
        finalized = self._triage.finalize_run(
            automation,
            running_run,
            runner_result,
            workspace_session=session,
            cleanup_result=cleanup_result,
        )
        final_run = finalized["run"]
        final_status = str(final_run.get("status") or "").lower()
        if final_status == "failed":
            event_type = "automation_run_failed"
        elif final_status == "running":
            event_type = "automation_run_progress"
        else:
            event_type = "automation_run_completed"
        self._record_event(
            event_type,
            {
                "automation_id": final_run.get("automation_id"),
                "run_id": final_run.get("run_id"),
                "status": final_run.get("status"),
                "signal": final_run.get("signal"),
            },
        )
        inbox_item = finalized.get("inbox_item")
        if inbox_item:
            inbox_event = "automation_inbox_item_archived" if str(inbox_item.get("state") or "") == "archived" else "automation_inbox_item_created"
            self._record_event(
                inbox_event,
                {
                    "automation_id": inbox_item.get("automation_id"),
                    "run_id": inbox_item.get("run_id"),
                    "item_id": inbox_item.get("item_id"),
                    "state": inbox_item.get("state"),
                    "disposition": inbox_item.get("disposition"),
                },
            )
        return {
            "run": final_run,
            "inbox_item": inbox_item,
            "artifact_ref": finalized.get("artifact_ref"),
            "scheduler": self.scheduler_status(),
        }

    def list_runs(self, automation_id: str | None = None) -> dict[str, Any]:
        self._require_project()
        runs = self._store.list_runs(automation_id)
        return {"runs": runs, "count": len(runs)}

    def get_run(self, run_id: str) -> dict[str, Any]:
        self._require_project()
        run = self._store.get_run(run_id)
        if not run:
            raise ValueError("Automation run not found.")
        return {"run": run}

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        self._require_project()
        run = self._store.get_run(run_id)
        if not run:
            raise ValueError("Automation run not found.")
        current = str(run.get("status") or "").lower()
        if current not in {"queued", "running", "needs_review"}:
            return {"run": run}
        updated = self._store.record_run(
            {
                **run,
                "status": "cancelled",
                "finished_at": now_iso(),
                "summary": str(run.get("summary") or "automation run cancelled"),
                "redacted_error": str(run.get("redacted_error") or "cancelled_by_user"),
            }
        )
        self._record_event("automation_run_failed", {"automation_id": updated.get("automation_id"), "run_id": updated.get("run_id"), "status": "cancelled"})
        return {"run": updated}

    def list_inbox_items(self, automation_id: str | None = None, *, include_archived: bool = True) -> dict[str, Any]:
        self._require_project()
        items = self._store.list_inbox_items(automation_id, include_archived=include_archived)
        return {"items": items, "count": len(items)}

    def update_inbox_item(self, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        self._require_project()
        item = self._triage.update_inbox_item(item_id, patch)
        self._record_event(
            "automation_updated",
            {"item_id": item.get("item_id"), "inbox_state": item.get("state"), "automation_id": item.get("automation_id")},
        )
        return {"item": item}

    def promote_inbox_item(self, item_id: str, promotion_ref: str) -> dict[str, Any]:
        self._require_project()
        item = self._triage.promote_inbox_item(item_id, promotion_ref)
        self._record_event(
            "automation_promoted_to_task",
            {
                "automation_id": item.get("automation_id"),
                "run_id": item.get("run_id"),
                "item_id": item.get("item_id"),
                "promotion_ref": item.get("promotion_ref"),
            },
        )
        return {"item": item}

    def scheduler_status(self) -> dict[str, Any]:
        if not self._has_open_project():
            return self._neutral_scheduler_status(running=False)
        status = dict(self._scheduler.status())
        runs = self._store.list_runs()
        active_runs = [
            {
                "run_id": run.get("run_id"),
                "automation_id": run.get("automation_id"),
                "status": run.get("status"),
                "due_at": run.get("due_at"),
            }
            for run in runs
            if str(run.get("status") or "").lower() in {"queued", "running", "needs_review"}
        ][:10]
        last_failure = next((run for run in runs if str(run.get("status") or "").lower() == "failed"), None)
        next_due = self._next_due_summary()
        return {
            **status,
            "active_runs": active_runs,
            "last_failure": last_failure,
            "next_due": next_due,
            "inbox_summary": self._store.inbox_summary(),
        }

    def status_summary(self) -> dict[str, Any]:
        scheduler = self.scheduler_status()
        return {
            "scheduler": scheduler,
            "active_runs": scheduler.get("active_runs") or [],
            "last_failure": scheduler.get("last_failure"),
            "next_due": scheduler.get("next_due"),
            "inbox_summary": scheduler.get("inbox_summary") or {},
        }

    def _next_due_summary(self) -> dict[str, Any] | None:
        candidate = None
        for automation in self._store.list_automations():
            schedule = dict(automation.get("schedule") or {})
            next_run_at = str(schedule.get("next_run_at") or "").strip()
            if not next_run_at:
                continue
            summary = {
                "automation_id": automation.get("automation_id"),
                "name": automation.get("name"),
                "next_run_at": next_run_at,
            }
            if candidate is None or next_run_at < str(candidate.get("next_run_at") or ""):
                candidate = summary
        return candidate

    def _ensure_scheduler_started(self) -> None:
        if self._scheduler.status().get("running"):
            return
        self._scheduler.start()

    def _require_project(self) -> None:
        if not self._has_open_project():
            raise ValueError("No project is open.")

    def _has_open_project(self) -> bool:
        return bool(getattr(self._projects, "current_project", None))

    def _neutral_scheduler_status(self, *, running: bool) -> dict[str, Any]:
        return {
            "running": running,
            "active_run_count": 0,
            "next_wake_up_at": None,
            "active_runs": [],
            "last_failure": None,
            "next_due": None,
            "inbox_summary": {"unread": 0, "reviewed": 0, "archived": 0, "promoted": 0},
        }

    def _record_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_recorder is None:
            return
        self._event_recorder(event_type, dict(payload))
