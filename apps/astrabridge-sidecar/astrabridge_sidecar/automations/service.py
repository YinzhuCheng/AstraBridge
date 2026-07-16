from __future__ import annotations

import threading
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
        agentic_update_service: Any | None = None,
        event_recorder: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._projects = project_service
        self._runtime = runtime_service
        self._profiles = profile_service
        self._runtime_config = runtime_config
        self._agentic_updates = agentic_update_service
        self._event_recorder = event_recorder
        self._store = AutomationStore(project_service)
        self._scheduler = AutomationScheduler(self._store)
        self._workspace = AutomationWorkspaceManager(project_service)
        self._runner = AutomationRunner(
            project_service,
            runtime_service=runtime_service,
            profile_service=profile_service,
            runtime_config=runtime_config,
            agentic_update_service=agentic_update_service,
        )
        self._triage = AutomationTriageService(project_service, self._store)
        self._executing_run_ids: set[str] = set()
        self._background_run_threads: dict[str, threading.Thread] = {}
        self._background_run_threads_lock = threading.RLock()

    def start(self) -> dict[str, Any]:
        if not self._has_open_project():
            return self._neutral_scheduler_status(running=False)
        self._reconcile_watchdog_runs()
        status = self._scheduler.start()
        self._record_event("automation_scheduler_started", {"scheduler": status})
        return status

    def stop(self) -> dict[str, Any]:
        status = self._scheduler.stop()
        self._record_event("automation_scheduler_stopped", {"scheduler": status})
        return status

    def list_automations(self) -> dict[str, Any]:
        self._require_project()
        self._reconcile_watchdog_runs()
        items = self._store.list_automations()
        return {"automations": items, "count": len(items)}

    def create_automation(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_project()
        created = self._store.create_automation(payload)
        self._record_event("automation_created", {"automation_id": created.get("automation_id")})
        return {"automation": created}

    def create_agentic_update_check_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_project()
        if self._agentic_updates is None:
            raise ValueError("Agentic update service is not configured.")
        project = dict(getattr(self._projects, "current_project", None) or {})
        run_contract = self._agentic_update_run_contract_from_payload(payload)
        automation_id = str(payload.get("automation_id") or "").strip() or self._default_agentic_update_automation_id(run_contract)
        schedule = dict(payload.get("schedule") or {"mode": "daily", "expression": "03:00", "timezone": "UTC"})
        limits = {
            "timeout_sec": 1800,
            "max_retries": 0,
            "max_artifact_bytes": 2_000_000,
            "max_parallel_runs": 1,
            "daily_run_limit": 1,
            **dict(payload.get("limits") or {}),
        }
        agentic_update = {
            "template_version": "agentic-update-check-template-v1",
            "run_contract": run_contract,
            "network_policy": str(payload.get("network_policy") or ("official_docs_only" if run_contract.get("allow_network") else "fixture_only")),
            "max_source_records": int(payload.get("max_source_records") or 10),
        }
        for key in (
            "provider_sources",
            "fixture_sources",
            "provider_fixture_sources",
            "current_models",
            "complete_provider_snapshot",
            "kernel_source_records",
            "kernel_fixture_sources",
        ):
            if key in payload:
                agentic_update[key] = payload.get(key)
        spec = {
            "automation_id": automation_id,
            "project_id": str(payload.get("project_id") or project.get("project_id") or "project").strip(),
            "name": str(payload.get("name") or "Agentic update check").strip(),
            "description": str(
                payload.get("description")
                or "User-scoped recurring agentic update discovery/proposal check. It never applies changes, installs binaries, or calls providers."
            ).strip(),
            "enabled": bool(payload.get("enabled", False)),
            "kind": "agentic_update_check",
            "prompt": str(payload.get("prompt") or "Run AstraBridge agentic update proposal check.").strip(),
            "schedule": schedule,
            "runtime": {"permission_mode": "read-only", **dict(payload.get("runtime") or {})},
            "workspace": {
                "mode": "current_workspace",
                "cleanup_policy": "manual",
                **dict(payload.get("workspace") or {}),
            },
            "triage": {
                "archive_no_signal": True,
                "notify_on": "finding",
                "finding_keywords": ["changes_detected", "proposal_only_complete"],
                **dict(payload.get("triage") or {}),
            },
            "limits": limits,
            "agentic_update": agentic_update,
        }
        created = self.create_automation(spec)
        self._record_event("agentic_update_check_template_created", {"automation_id": automation_id})
        return created

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

    def run_now(self, automation_id: str, *, background: bool = False) -> dict[str, Any]:
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
        if background:
            queued_run_id = str(queued.get("run_id") or "").strip()
            if not queued_run_id:
                raise ValueError("Queued automation run is missing a run_id.")
            self._launch_background_run(queued_run_id)
            return {
                "run": self._store.get_run(queued_run_id) or queued,
                "inbox_item": None,
                "artifact_ref": None,
                "scheduler": self.scheduler_status(),
            }
        return self.execute_run(str(queued.get("run_id") or ""))

    def _launch_background_run(self, run_id: str) -> None:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            raise ValueError("run_id is required.")
        thread = threading.Thread(
            target=self._execute_run_background,
            args=(clean_run_id,),
            name=f"astrabridge-automation-{clean_run_id}",
            daemon=True,
        )
        with self._background_run_threads_lock:
            self._background_run_threads[clean_run_id] = thread
        thread.start()

    def _execute_run_background(self, run_id: str) -> None:
        try:
            self.execute_run(run_id)
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                "automation_run_background_dispatch_failed",
                {
                    "run_id": run_id,
                    "error": str(exc)[:300] or "automation_background_dispatch_failed",
                },
            )
        finally:
            with self._background_run_threads_lock:
                self._background_run_threads.pop(str(run_id or "").strip(), None)

    def wait_for_background_run(self, run_id: str, *, timeout_sec: float | None = None) -> bool:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            return True
        with self._background_run_threads_lock:
            thread = self._background_run_threads.get(clean_run_id)
        if thread is None:
            return True
        thread.join(timeout=timeout_sec)
        return not thread.is_alive()

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
        self._executing_run_ids.add(str(running_run.get("run_id") or ""))
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
        try:
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
        finally:
            self._executing_run_ids.discard(str(running_run.get("run_id") or ""))

    def list_runs(self, automation_id: str | None = None) -> dict[str, Any]:
        self._require_project()
        self._reconcile_watchdog_runs()
        runs = self._store.list_runs(automation_id)
        return {"runs": runs, "count": len(runs)}

    def get_run(self, run_id: str) -> dict[str, Any]:
        self._require_project()
        self._reconcile_watchdog_runs()
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
        automation = self._store.get_automation(str(run.get("automation_id") or ""))
        if not automation:
            raise ValueError("Automation not found.")
        finalized = self._triage.finalize_run(
            automation,
            run,
            {
                **run,
                "status": "cancelled",
                "finished_at": now_iso(),
                "summary": str(run.get("summary") or "automation run cancelled"),
                "redacted_error": str(run.get("redacted_error") or "cancelled_by_user"),
                "signal": "unknown",
            },
        )
        updated = finalized["run"]
        self._record_event("automation_run_failed", {"automation_id": updated.get("automation_id"), "run_id": updated.get("run_id"), "status": "cancelled"})
        inbox_item = finalized.get("inbox_item")
        if inbox_item:
            self._record_event(
                "automation_inbox_item_created",
                {
                    "automation_id": inbox_item.get("automation_id"),
                    "run_id": inbox_item.get("run_id"),
                    "item_id": inbox_item.get("item_id"),
                    "state": inbox_item.get("state"),
                    "disposition": inbox_item.get("disposition"),
                },
            )
        return {"run": updated, "inbox_item": inbox_item, "artifact_ref": finalized.get("artifact_ref")}

    def list_inbox_items(self, automation_id: str | None = None, *, include_archived: bool = True) -> dict[str, Any]:
        self._require_project()
        self._reconcile_watchdog_runs()
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
        self._reconcile_watchdog_runs()
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

    def _reconcile_watchdog_runs(self) -> list[dict[str, Any]]:
        recovered = self._recover_interrupted_runs()
        finalized = self._finalize_watchdog_failures()
        return [*recovered, *finalized]

    def _recover_interrupted_runs(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        for run in self._store.list_runs():
            run_id = str(run.get("run_id") or "")
            if run_id in self._executing_run_ids:
                continue
            if str(run.get("status") or "").lower() != "running":
                continue
            automation = self._store.get_automation(str(run.get("automation_id") or ""))
            if not automation:
                continue
            if str(automation.get("kind") or "").lower() != "standalone":
                continue
            summary = "Automation run was interrupted before it wrote a final result."
            finalized = self._triage.finalize_run(
                automation,
                run,
                {
                    **run,
                    "status": "failed",
                    "finished_at": now_iso(),
                    "summary": summary,
                    "redacted_error": "automation_runner_interrupted_after_service_restart",
                    "signal": "unknown",
                    "watchdog_reason": "service_restart_interrupted",
                    "watchdog_summary": (
                        "AstraBridge found this run still marked active after the automation worker stopped, "
                        "so it recovered the run into a reviewable failure."
                    ),
                    "recovered_by": "service_restart",
                    "recovered_at": now_iso(),
                },
                cleanup_result={"status": "unknown", "reason": "service_restart_or_runner_exit_before_final_state"},
            )
            final_run = finalized["run"]
            recovered.append(final_run)
            self._record_event(
                "automation_run_failed",
                {
                    "automation_id": final_run.get("automation_id"),
                    "run_id": final_run.get("run_id"),
                    "status": final_run.get("status"),
                    "signal": final_run.get("signal"),
                    "recovered": True,
                    "watchdog_reason": final_run.get("watchdog_reason"),
                    "recovered_by": final_run.get("recovered_by"),
                },
            )
            inbox_item = finalized.get("inbox_item")
            if inbox_item:
                self._record_event(
                    "automation_inbox_item_created",
                    {
                        "automation_id": inbox_item.get("automation_id"),
                        "run_id": inbox_item.get("run_id"),
                        "item_id": inbox_item.get("item_id"),
                        "state": inbox_item.get("state"),
                        "disposition": inbox_item.get("disposition"),
                    },
                )
        return recovered

    def _finalize_watchdog_failures(self) -> list[dict[str, Any]]:
        finalized_runs: list[dict[str, Any]] = []
        for run in self._store.list_runs():
            status = str(run.get("status") or "").lower()
            if status != "failed":
                continue
            if list(run.get("artifact_refs") or []):
                continue
            watchdog_reason = str(run.get("watchdog_reason") or "").strip().lower()
            redacted_error = str(run.get("redacted_error") or "").strip()
            if watchdog_reason != "stale_running_timeout" and redacted_error not in {
                "automation_watchdog_stale_running_timeout",
                "stale_run_recovered",
            }:
                continue
            automation = self._store.get_automation(str(run.get("automation_id") or ""))
            if not automation:
                continue
            finalized = self._triage.finalize_run(
                automation,
                run,
                {
                    **run,
                    "status": "failed",
                    "finished_at": run.get("finished_at") or now_iso(),
                    "summary": str(run.get("summary") or "Automation watchdog recovered a stale running run after the timeout window."),
                    "redacted_error": "automation_watchdog_stale_running_timeout",
                    "signal": str(run.get("signal") or "unknown") or "unknown",
                    "watchdog_reason": "stale_running_timeout",
                    "watchdog_summary": str(run.get("watchdog_summary") or "").strip()
                    or "The scheduler did not observe a final result before the stale timeout, so AstraBridge recovered this run for review.",
                    "recovered_by": str(run.get("recovered_by") or "scheduler_watchdog").strip() or "scheduler_watchdog",
                    "recovered_at": run.get("recovered_at") or run.get("finished_at") or now_iso(),
                },
                cleanup_result={"status": "unknown", "reason": "scheduler_watchdog_recovered_stale_running_run"},
            )
            final_run = finalized["run"]
            finalized_runs.append(final_run)
            self._record_event(
                "automation_run_failed",
                {
                    "automation_id": final_run.get("automation_id"),
                    "run_id": final_run.get("run_id"),
                    "status": final_run.get("status"),
                    "signal": final_run.get("signal"),
                    "recovered": True,
                    "watchdog_reason": final_run.get("watchdog_reason"),
                    "recovered_by": final_run.get("recovered_by"),
                },
            )
            inbox_item = finalized.get("inbox_item")
            if inbox_item:
                inbox_event = (
                    "automation_inbox_item_archived"
                    if str(inbox_item.get("state") or "") == "archived"
                    else "automation_inbox_item_created"
                )
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
        return finalized_runs

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

    def _agentic_update_run_contract_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload.get("run_contract"), dict):
            contract = dict(payload["run_contract"])
            contract.setdefault("apply_mode", "proposal_only")
            contract.setdefault("allow_network", False)
            contract.setdefault("allow_provider_calls", False)
            contract.setdefault("allow_install", False)
            contract.setdefault("allow_code_changes", False)
            contract.setdefault("approval_policy", "manual_review_required")
            return contract
        return {
            "scope": payload.get("scope") or "provider_metadata",
            "providers": payload.get("providers") or [],
            "models": payload.get("models") or [],
            "version_policy": payload.get("version_policy") or "stable",
            "target_version": payload.get("target_version") or None,
            "apply_mode": payload.get("apply_mode") or "proposal_only",
            "allow_network": payload.get("allow_network") if isinstance(payload.get("allow_network"), bool) else False,
            "allow_provider_calls": payload.get("allow_provider_calls") if isinstance(payload.get("allow_provider_calls"), bool) else False,
            "allow_install": payload.get("allow_install") if isinstance(payload.get("allow_install"), bool) else False,
            "allow_code_changes": payload.get("allow_code_changes") if isinstance(payload.get("allow_code_changes"), bool) else False,
            "approval_policy": payload.get("approval_policy") or "manual_review_required",
        }

    def _default_agentic_update_automation_id(self, run_contract: dict[str, Any]) -> str:
        providers = [str(item).strip() for item in list(run_contract.get("providers") or []) if str(item).strip()]
        suffix = "-".join(providers[:2]) if providers else "all"
        return f"agentic-update-check-{suffix}"
