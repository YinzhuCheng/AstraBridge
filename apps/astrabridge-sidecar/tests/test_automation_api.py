from __future__ import annotations

import json
import sys
import tempfile
import threading
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


class AutomationApiTests(unittest.TestCase):
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

            def run_now(self, automation_id: str) -> dict[str, Any]:
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
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/automations", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["count"], 1)

            create_request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/automations/create",
                data=json.dumps({"automation_id": "auto-2", "project_id": "demo", "name": "Demo"}).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Admin-Token": "unit-admin"},
                method="POST",
            )
            with urllib.request.urlopen(create_request, timeout=5) as response:
                created = json.loads(response.read().decode("utf-8"))
            self.assertEqual(created["automation"]["automation_id"], "auto-2")

            scheduler_request = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/automations/scheduler/status", timeout=5)
            scheduler_payload = json.loads(scheduler_request.read().decode("utf-8"))
            self.assertTrue(scheduler_payload["scheduler"]["running"])

            promote_request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/automations/inbox/promote",
                data=json.dumps({"item_id": "item-1", "promotion_ref": "task:123"}).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Admin-Token": "unit-admin"},
                method="POST",
            )
            with urllib.request.urlopen(promote_request, timeout=5) as response:
                promoted = json.loads(response.read().decode("utf-8"))
            self.assertEqual(promoted["item"]["promotion_ref"], "task:123")

            update_request = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/automations/update",
                data=json.dumps({"automation_id": "auto-1", "enabled": False}).encode("utf-8"),
                headers={"Content-Type": "application/json", "X-Admin-Token": "unit-admin"},
                method="POST",
            )
            with urllib.request.urlopen(update_request, timeout=5) as response:
                updated = json.loads(response.read().decode("utf-8"))
            self.assertFalse(updated["automation"]["enabled"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
