from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.automations import AutomationService
from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.runtime_supervisor_service import RuntimeSupervisorService
from astrabridge_sidecar.server import Handler


class _FakeRuntime:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record_external_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append({"type": event_type, **dict(payload or {})})

    def record_supervisor_event(self, event: dict[str, Any]) -> None:
        self.events.append({"type": "runtime_supervisor", **dict(event or {})})

    def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, Any]:
        events = self.events[after:]
        if limit is not None:
            events = events[:limit]
        return {"cursor": len(self.events), "events": events}


class _FakeDogfood:
    @staticmethod
    def snapshot() -> dict[str, Any]:
        return {"run": {}}


class _FakeProfiles:
    @staticmethod
    def resolve_runtime_profile(profile_id: str | None) -> dict[str, Any]:
        return {"profile_id": profile_id or "openai-compatible", "provider_id": "openai", "model": "gpt-5.5"}


class _AuthorityTierProfiles:
    @staticmethod
    def resolve_runtime_profile(profile_id: str | None) -> dict[str, Any]:
        return {"profile_id": profile_id or "qwen-default", "provider_id": "qwen", "model": "qwen3.7-plus"}


class _DeepSeekProfiles:
    @staticmethod
    def resolve_runtime_profile(profile_id: str | None) -> dict[str, Any]:
        return {"profile_id": profile_id or "deepseek-default", "provider_id": "deepseek", "model": "deepseek-v4-pro"}


class _GateRuntimeConfig:
    def __init__(self, codex_home: Path, *, authority_tier: str, authority_reason: str) -> None:
        self._codex_home = codex_home
        self._authority_tier = authority_tier
        self._authority_reason = authority_reason

    def prepare_profile(self, profile: dict[str, Any], require_secret: bool = False) -> dict[str, Any]:
        models_dir = self._codex_home / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "models": [
                {
                    "id": f"{profile['provider_id']}/{profile['model']}",
                    "provider": profile["provider_id"],
                    "native_model": profile["model"],
                    "authority_tier": self._authority_tier,
                    "authority_reason": self._authority_reason,
                    "command_execution_status": "verified",
                    "command_execution_note": "",
                }
            ]
        }
        (models_dir / "astrabridge-models.json").write_text(json.dumps(payload), encoding="utf-8")
        return {"codex_home": str(self._codex_home)}


class _MissingSecretRuntimeConfig(_GateRuntimeConfig):
    def prepare_profile(self, profile: dict[str, Any], require_secret: bool = False) -> dict[str, Any]:
        if require_secret:
            raise RuntimeError("runtime_secret_missing: set DEEPSEEK_API_KEY in the environment, paste a session key, or load a local key file.")
        return super().prepare_profile(profile, require_secret=require_secret)


class _FakeRunner:
    def execute(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        return {
            "run_id": run["run_id"],
            "automation_id": run["automation_id"],
            "project_id": run["project_id"],
            "trigger": run["trigger"],
            "status": "completed",
            "due_at": run["due_at"],
            "started_at": "2026-06-24T01:00:00+00:00",
            "finished_at": "2026-06-24T01:00:02+00:00",
            "thread_id": run.get("thread_id"),
            "turn_id": None,
            "worktree_path": None,
            "runtime_profile_id": "openai-compatible",
            "exit_code": 0,
            "signal": "finding",
            "summary": "Found TODO in workspace.",
            "artifact_refs": [],
            "redacted_error": None,
            "next_retry_at": None,
            "stdout_excerpt": "todo remains",
            "stderr_excerpt": None,
        }


class _NoSignalRunner:
    def execute(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        return {
            "run_id": run["run_id"],
            "automation_id": run["automation_id"],
            "project_id": run["project_id"],
            "trigger": run["trigger"],
            "status": "completed",
            "due_at": run["due_at"],
            "started_at": "2026-06-24T01:10:00+00:00",
            "finished_at": "2026-06-24T01:10:02+00:00",
            "thread_id": run.get("thread_id"),
            "turn_id": None,
            "worktree_path": None,
            "runtime_profile_id": "openai-compatible",
            "exit_code": 0,
            "signal": "unknown",
            "summary": "Repository clean.",
            "artifact_refs": [],
            "redacted_error": None,
            "next_retry_at": None,
            "stdout_excerpt": "all good",
            "stderr_excerpt": None,
        }


class _FailingRunner:
    def execute(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        raise RuntimeError("dirty workspace blocks execution")


class AutomationApiTests(unittest.TestCase):
    def _wait_for_run_status(
        self,
        service: AutomationService,
        run_id: str,
        *,
        terminal_statuses: set[str],
        timeout_sec: float = 2.0,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        latest: dict[str, Any] | None = None
        while time.time() < deadline:
            latest = service.get_run(run_id)
            status = str((latest or {}).get("run", {}).get("status") or "").lower()
            if status in terminal_statuses:
                return latest["run"]
            time.sleep(0.01)
        self.fail(f"Timed out waiting for automation run {run_id} to reach one of {sorted(terminal_statuses)}; latest={latest!r}")

    def test_automation_service_run_now_emits_events_and_supervisor_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfiles(),
                runtime_config=None,
                event_recorder=runtime.record_external_event,
            )
            service._runner = _FakeRunner()  # noqa: SLF001
            service.start()
            created = service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": True, "notify_on": "every_run", "finding_keywords": ["todo"]},
                }
            )

            self.assertEqual(created["automation"]["automation_id"], "auto-1")
            run_result = service.run_now("auto-1")
            self.assertEqual(run_result["run"]["status"], "completed")
            self.assertEqual(run_result["run"]["signal"], "finding")
            self.assertEqual(run_result["inbox_item"]["state"], "unread")
            self.assertTrue(any(event["type"] == "automation_run_queued" for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_run_started" for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_run_completed" for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_inbox_item_created" for event in runtime.events))

            modals = ModalService(projects.require_shell_state_root)
            supervisor = RuntimeSupervisorService(projects, runtime, modals, _FakeDogfood(), automation_service=service)
            status = supervisor.status(thread_id=None, profile=None)
            self.assertTrue(status["automations"]["scheduler"]["running"])
            self.assertEqual(status["automations"]["active_runs"], [])
            self.assertEqual(status["automations"]["inbox_summary"]["unread"], 1)
            self.assertEqual(status["automations"]["next_due"], None)
            self.assertTrue(Path(run_result["artifact_ref"]).exists())

    def test_automation_service_background_run_now_returns_queued_run_and_finishes_asynchronously(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfiles(),
                runtime_config=None,
                event_recorder=runtime.record_external_event,
            )
            service._runner = _FakeRunner()  # noqa: SLF001
            service.start()
            service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": True, "notify_on": "every_run", "finding_keywords": ["todo"]},
                }
            )

            run_result = service.run_now("auto-1", background=True)
            self.assertIn(str(run_result["run"]["status"]).lower(), {"queued", "running"})
            self.assertIsNone(run_result["inbox_item"])
            self.assertIsNone(run_result["artifact_ref"])

            self.assertTrue(service.wait_for_background_run(str(run_result["run"]["run_id"]), timeout_sec=5.0))
            finalized_run = service.get_run(str(run_result["run"]["run_id"]))["run"]
            self.assertEqual(finalized_run["status"], "completed")
            self.assertEqual(finalized_run["signal"], "finding")
            self.assertTrue(any(event["type"] == "automation_run_queued" for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_run_started" for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_run_completed" for event in runtime.events))

    def test_automation_service_completed_no_signal_archives_inbox_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfiles(),
                runtime_config=None,
                event_recorder=runtime.record_external_event,
            )
            service._runner = _NoSignalRunner()  # noqa: SLF001
            service.start()
            service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": True, "notify_on": "finding", "finding_keywords": ["todo"]},
                }
            )

            run_result = service.run_now("auto-1")
            self.assertEqual(run_result["run"]["status"], "completed")
            self.assertEqual(run_result["run"]["signal"], "no_signal")
            self.assertEqual(run_result["inbox_item"]["state"], "archived")
            self.assertEqual(run_result["inbox_item"]["disposition"], "no_signal")
            self.assertTrue(Path(run_result["artifact_ref"]).exists())
            self.assertTrue(any(event["type"] == "automation_run_completed" for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_inbox_item_archived" for event in runtime.events))

    def test_automation_service_completed_no_signal_can_finalize_without_inbox_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfiles(),
                runtime_config=None,
                event_recorder=runtime.record_external_event,
            )
            service._runner = _NoSignalRunner()  # noqa: SLF001
            service.start()
            service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": False, "notify_on": "finding", "finding_keywords": ["todo"]},
                }
            )

            run_result = service.run_now("auto-1")
            self.assertEqual(run_result["run"]["status"], "completed")
            self.assertEqual(run_result["run"]["signal"], "no_signal")
            self.assertIsNone(run_result["inbox_item"])
            self.assertTrue(Path(run_result["artifact_ref"]).exists())
            self.assertTrue(any(event["type"] == "automation_run_completed" for event in runtime.events))
            self.assertFalse(any(event["type"] in {"automation_inbox_item_created", "automation_inbox_item_archived"} for event in runtime.events))

    def test_automation_service_failure_run_surfaces_reviewable_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfiles(),
                runtime_config=None,
                event_recorder=runtime.record_external_event,
            )
            service._runner = _FailingRunner()  # noqa: SLF001
            service.start()
            service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": False, "notify_on": "every_run", "finding_keywords": ["todo"]},
                }
            )

            run_result = service.run_now("auto-1")
            self.assertEqual(run_result["run"]["status"], "failed")
            self.assertEqual(run_result["run"]["signal"], "unknown")
            self.assertIn("dirty workspace blocks execution", str(run_result["run"]["redacted_error"]))
            self.assertEqual(run_result["inbox_item"]["state"], "unread")
            self.assertEqual(run_result["inbox_item"]["disposition"], "failure")
            self.assertTrue(Path(run_result["artifact_ref"]).exists())
            self.assertTrue(any(event["type"] == "automation_run_failed" for event in runtime.events))

    def test_automation_service_blocks_unverified_standalone_profile_before_provider_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            codex_home = root / "codex-home"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_AuthorityTierProfiles(),
                runtime_config=_GateRuntimeConfig(
                    codex_home,
                    authority_tier="C",
                    authority_reason="Model has no verified structured tool-calling surface.",
                ),
                event_recorder=runtime.record_external_event,
            )
            service.start()
            service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"profile_id": "qwen-default", "permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": False, "notify_on": "every_run", "finding_keywords": ["todo"]},
                }
            )

            run_result = service.run_now("auto-1")
            self.assertEqual(run_result["run"]["status"], "failed")
            self.assertEqual(run_result["run"]["summary"], "Standalone automation was blocked before provider dispatch.")
            self.assertEqual(run_result["run"]["redacted_error"], "Model has no verified structured tool-calling surface.")
            self.assertEqual(run_result["inbox_item"]["disposition"], "failure")
            self.assertTrue(Path(run_result["artifact_ref"]).exists())
            self.assertTrue(any(event["type"] == "automation_run_failed" for event in runtime.events))

    def test_automation_service_blocks_missing_runtime_secret_before_provider_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            codex_home = root / "codex-home"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_DeepSeekProfiles(),
                runtime_config=_MissingSecretRuntimeConfig(
                    codex_home,
                    authority_tier="B",
                    authority_reason="Read-only review mode is acceptable after a real provider key is loaded.",
                ),
                event_recorder=runtime.record_external_event,
            )
            service.start()
            service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"profile_id": "deepseek-default", "permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": False, "notify_on": "every_run", "finding_keywords": ["todo"]},
                }
            )

            run_result = service.run_now("auto-1")
            self.assertEqual(run_result["run"]["status"], "failed")
            self.assertEqual(run_result["run"]["summary"], "Standalone automation was blocked before provider dispatch.")
            self.assertEqual(run_result["run"]["redacted_error"], "standalone_runtime_key_missing")
            self.assertEqual(run_result["inbox_item"]["disposition"], "failure")
            self.assertTrue(Path(run_result["artifact_ref"]).exists())
            self.assertTrue(any(event["type"] == "automation_run_failed" for event in runtime.events))

    def test_automation_service_cancel_run_marks_active_run_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfiles(),
                runtime_config=None,
                event_recorder=runtime.record_external_event,
            )
            service.start()
            service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": False, "notify_on": "every_run", "finding_keywords": ["todo"]},
                }
            )

            queued = service._scheduler.trigger_now("auto-1")  # noqa: SLF001
            self.assertIsNotNone(queued)
            cancel_result = service.cancel_run(str(queued["run_id"]))
            self.assertEqual(cancel_result["run"]["status"], "cancelled")
            self.assertEqual(cancel_result["run"]["summary"], "queued by scheduler")
            self.assertEqual(cancel_result["run"]["redacted_error"], "cancelled_by_user")
            self.assertTrue(Path(cancel_result["artifact_ref"]).exists())
            cancel_manifest = json.loads(Path(cancel_result["artifact_ref"]).read_text(encoding="utf-8"))
            self.assertEqual(cancel_manifest["usage_signal"]["status"], "not_available")
            self.assertEqual(cancel_manifest["usage_signal"]["reason"], "automation_result_usage_not_reported")
            self.assertEqual(cancel_result["run"]["artifact_refs"], [cancel_result["artifact_ref"]])
            self.assertEqual(cancel_result["inbox_item"]["disposition"], "failure")
            self.assertEqual(cancel_result["inbox_item"]["state"], "unread")
            self.assertTrue(any(event["type"] == "automation_run_failed" and event.get("status") == "cancelled" for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_inbox_item_created" for event in runtime.events))

    def test_automation_service_recovers_interrupted_standalone_run_with_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfiles(),
                runtime_config=None,
                event_recorder=runtime.record_external_event,
            )
            service.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": False, "notify_on": "every_run", "finding_keywords": ["todo"]},
                }
            )
            service._store.record_run(  # noqa: SLF001
                {
                    "run_id": "run-interrupted",
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "trigger": "manual",
                    "status": "running",
                    "due_at": "2026-06-24T01:00:00+00:00",
                    "started_at": "2026-06-24T01:00:01+00:00",
                    "signal": "unknown",
                    "summary": "automation run started",
                }
            )

            runs = service.list_runs("auto-1")["runs"]
            recovered = runs[0]
            self.assertEqual(recovered["run_id"], "run-interrupted")
            self.assertEqual(recovered["status"], "failed")
            self.assertEqual(recovered["summary"], "Automation run was interrupted before it wrote a final result.")
            self.assertEqual(recovered["redacted_error"], "automation_runner_interrupted_after_service_restart")
            self.assertEqual(recovered["watchdog_reason"], "service_restart_interrupted")
            self.assertEqual(recovered["recovered_by"], "service_restart")
            self.assertTrue(Path(recovered["artifact_refs"][0]).exists())
            manifest = json.loads(Path(recovered["artifact_refs"][0]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["watchdog"]["reason"], "service_restart_interrupted")
            self.assertEqual(manifest["watchdog"]["recovered_by"], "service_restart")
            inbox = service.list_inbox_items("auto-1")["items"]
            self.assertEqual(inbox[0]["run_id"], "run-interrupted")
            self.assertEqual(inbox[0]["state"], "unread")
            self.assertEqual(inbox[0]["disposition"], "failure")
            self.assertEqual(service.scheduler_status()["active_runs"], [])
            self.assertTrue(any(event["type"] == "automation_run_failed" and event.get("recovered") is True for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_inbox_item_created" for event in runtime.events))

    def test_automation_service_finalizes_watchdog_recovered_stale_run_with_artifact_and_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            runtime = _FakeRuntime()
            service = AutomationService(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfiles(),
                runtime_config=None,
                event_recorder=runtime.record_external_event,
            )
            service.create_automation(
                {
                    "automation_id": "auto-stale",
                    "project_id": "demo",
                    "name": "Watchdog audit",
                    "kind": "standalone",
                    "prompt": "Audit repo",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    "triage": {"archive_no_signal": False, "notify_on": "every_run", "finding_keywords": ["todo"]},
                }
            )
            service._store.record_run(  # noqa: SLF001
                {
                    "run_id": "run-stale",
                    "automation_id": "auto-stale",
                    "project_id": "demo",
                    "trigger": "schedule",
                    "status": "failed",
                    "due_at": "2026-06-24T01:00:00+00:00",
                    "started_at": "2026-06-24T01:00:01+00:00",
                    "finished_at": "2026-06-24T01:40:00+00:00",
                    "signal": "unknown",
                    "summary": "Automation watchdog recovered a stale running run after the timeout window.",
                    "redacted_error": "automation_watchdog_stale_running_timeout",
                    "artifact_refs": [],
                    "watchdog_reason": "stale_running_timeout",
                    "watchdog_summary": "No final result was recorded within 1800 seconds, so the scheduler recovered the run for review.",
                    "recovered_by": "scheduler_watchdog",
                    "recovered_at": "2026-06-24T01:40:00+00:00",
                }
            )

            runs = service.list_runs("auto-stale")["runs"]
            recovered = runs[0]
            self.assertEqual(recovered["run_id"], "run-stale")
            self.assertEqual(recovered["status"], "failed")
            self.assertEqual(recovered["watchdog_reason"], "stale_running_timeout")
            self.assertEqual(recovered["recovered_by"], "scheduler_watchdog")
            self.assertTrue(Path(recovered["artifact_refs"][0]).exists())
            manifest = json.loads(Path(recovered["artifact_refs"][0]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["watchdog"]["reason"], "stale_running_timeout")
            self.assertEqual(manifest["watchdog"]["recovered_by"], "scheduler_watchdog")
            inbox = service.list_inbox_items("auto-stale")["items"]
            self.assertEqual(inbox[0]["run_id"], "run-stale")
            self.assertEqual(inbox[0]["state"], "unread")
            self.assertEqual(inbox[0]["disposition"], "failure")
            self.assertTrue(any(event["type"] == "automation_run_failed" and event.get("watchdog_reason") == "stale_running_timeout" for event in runtime.events))
            self.assertTrue(any(event["type"] == "automation_inbox_item_created" for event in runtime.events))

    def test_automation_service_does_not_recover_intentional_thread_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            service = AutomationService(projects, profile_service=_FakeProfiles())
            service.create_automation(
                {
                    "automation_id": "auto-thread",
                    "project_id": "demo",
                    "name": "Thread audit",
                    "kind": "thread",
                    "prompt": "Audit thread",
                    "runtime": {"permission_mode": "read-only"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                }
            )
            service._store.record_run(  # noqa: SLF001
                {
                    "run_id": "run-thread",
                    "automation_id": "auto-thread",
                    "project_id": "demo",
                    "trigger": "manual",
                    "status": "running",
                    "due_at": "2026-06-24T01:00:00+00:00",
                    "started_at": "2026-06-24T01:00:01+00:00",
                    "thread_id": "thread-1",
                    "turn_id": "turn-1",
                    "signal": "unknown",
                    "summary": "Thread automation turn started.",
                }
            )

            runs = service.list_runs("auto-thread")["runs"]
            self.assertEqual(runs[0]["status"], "running")
            self.assertEqual(runs[0]["turn_id"], "turn-1")
            self.assertEqual(service.list_inbox_items("auto-thread")["items"], [])

    def test_handler_automation_routes(self) -> None:
        class FakeAutomations:
            def __init__(self) -> None:
                self.updated: list[tuple[str, dict[str, Any]]] = []

            def list_automations(self) -> dict[str, Any]:
                return {"automations": [{"automation_id": "auto-1"}], "count": 1}

            def create_automation(self, payload: dict[str, Any]) -> dict[str, Any]:
                return {"automation": payload}

            def update_automation(self, automation_id: str, patch: dict[str, Any]) -> dict[str, Any]:
                self.updated.append((automation_id, patch))
                return {"automation": {"automation_id": automation_id, **patch}}

            def delete_automation(self, automation_id: str, *, reason: str = "deleted") -> dict[str, Any]:
                return {"automation": {"automation_id": automation_id, "archived_reason": reason}}

            def pause_automation(self, automation_id: str) -> dict[str, Any]:
                return {"automation": {"automation_id": automation_id, "enabled": False}}

            def resume_automation(self, automation_id: str) -> dict[str, Any]:
                return {"automation": {"automation_id": automation_id, "enabled": True}}

            def run_now(self, automation_id: str, *, background: bool = False) -> dict[str, Any]:
                return {"run": {"automation_id": automation_id, "run_id": "run-1", "status": "completed"}}

            def cancel_run(self, run_id: str) -> dict[str, Any]:
                return {"run": {"run_id": run_id, "status": "cancelled"}}

            def list_runs(self, automation_id: str | None = None) -> dict[str, Any]:
                return {"runs": [{"run_id": "run-1", "automation_id": automation_id or "auto-1"}], "count": 1}

            def get_run(self, run_id: str) -> dict[str, Any]:
                return {"run": {"run_id": run_id, "status": "completed"}}

            def list_inbox_items(self, automation_id: str | None = None, *, include_archived: bool = True) -> dict[str, Any]:
                return {"items": [{"item_id": "item-1", "automation_id": automation_id or "auto-1", "state": "unread", "include_archived": include_archived}], "count": 1}

            def update_inbox_item(self, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
                return {"item": {"item_id": item_id, **patch}}

            def promote_inbox_item(self, item_id: str, promotion_ref: str) -> dict[str, Any]:
                return {"item": {"item_id": item_id, "state": "promoted", "promotion_ref": promotion_ref}}

            def scheduler_status(self) -> dict[str, Any]:
                return {"running": True, "active_run_count": 0, "next_wake_up_at": None}

        class FakeContext:
            def __init__(self) -> None:
                self.admin_token = "unit-admin"
                self.automations = FakeAutomations()

        class AutomationHandler(Handler):
            pass

        AutomationHandler.context = FakeContext()  # type: ignore[assignment]
        server = ThreadingHTTPServer(("127.0.0.1", 0), AutomationHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(f"http://127.0.0.1:{port}/api/automations", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["count"], 1)

            create_request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/automations/create",
                data=json.dumps({"automation_id": "auto-2", "project_id": "demo", "name": "Demo"}).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Admin-Token": "unit-admin"},
                method="POST",
            )
            with opener.open(create_request, timeout=5) as response:
                created = json.loads(response.read().decode("utf-8"))
            self.assertEqual(created["automation"]["automation_id"], "auto-2")

            scheduler_request = opener.open(f"http://127.0.0.1:{port}/api/automations/scheduler/status", timeout=5)
            scheduler_payload = json.loads(scheduler_request.read().decode("utf-8"))
            self.assertTrue(scheduler_payload["scheduler"]["running"])

            promote_request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/automations/inbox/promote",
                data=json.dumps({"item_id": "item-1", "promotion_ref": "task:123"}).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Admin-Token": "unit-admin"},
                method="POST",
            )
            with opener.open(promote_request, timeout=5) as response:
                promoted = json.loads(response.read().decode("utf-8"))
            self.assertEqual(promoted["item"]["promotion_ref"], "task:123")

            update_request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/automations/update",
                data=json.dumps({"automation_id": "auto-1", "enabled": False}).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Admin-Token": "unit-admin"},
                method="POST",
            )
            with opener.open(update_request, timeout=5) as response:
                updated = json.loads(response.read().decode("utf-8"))
            self.assertFalse(updated["automation"]["enabled"])
        finally:
            server.shutdown()
            server.server_close()

    def test_handler_options_supports_private_network_preflight(self) -> None:
        class FakeContext:
            def __init__(self) -> None:
                self.admin_token = "unit-admin"

        class OptionsHandler(Handler):
            pass

        OptionsHandler.context = FakeContext()  # type: ignore[assignment]
        server = ThreadingHTTPServer(("127.0.0.1", 0), OptionsHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/task-graphs/fixture-run",
                method="OPTIONS",
                headers={
                    "Origin": "http://127.0.0.1:4181",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type,x-admin-token",
                    "Access-Control-Request-Private-Network": "true",
                },
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=5) as response:
                self.assertEqual(response.status, 204)
                self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://127.0.0.1:4181")
                self.assertEqual(response.headers.get("Access-Control-Allow-Private-Network"), "true")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
