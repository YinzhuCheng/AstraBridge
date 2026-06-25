from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.automations import AutomationStore, AutomationTriageService, AutomationWorkspaceManager
from astrabridge_sidecar.project_service import ProjectService


class AutomationTriageTests(unittest.TestCase):
    def test_finalize_run_archives_no_signal_and_persists_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects, store, triage = self._make_services(Path(temp))
            automation = store.create_automation(self._automation_payload("auto-1"))
            run = store.record_run(self._run_payload("auto-1", "run-1"))
            session = self._workspace_session(projects, "auto-1", "run-1")

            finalized = triage.finalize_run(
                automation,
                run,
                {
                    "run_id": "run-1",
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "trigger": "manual",
                    "status": "completed",
                    "due_at": run["due_at"],
                    "started_at": "2026-06-24T00:00:05+00:00",
                    "finished_at": "2026-06-24T00:00:10+00:00",
                    "summary": "Repository clean.",
                    "stdout_excerpt": "all good",
                },
                workspace_session=session,
                cleanup_result={"cleaned": False, "retained": True},
            )

            self.assertEqual(finalized["run"]["signal"], "no_signal")
            self.assertEqual(finalized["run"]["status"], "completed")
            self.assertEqual(finalized["inbox_item"]["state"], "archived")
            self.assertEqual(finalized["inbox_item"]["disposition"], "no_signal")
            manifest_path = Path(finalized["artifact_ref"])
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["signal"], "no_signal")
            self.assertEqual(manifest["workspace"]["mode"], "current_workspace")

    def test_finalize_run_detects_finding_and_redacts_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects, store, triage = self._make_services(Path(temp))
            automation = store.create_automation(self._automation_payload("auto-2"))
            run = store.record_run(self._run_payload("auto-2", "run-2"))
            session = self._workspace_session(projects, "auto-2", "run-2")

            finalized = triage.finalize_run(
                automation,
                run,
                {
                    "run_id": "run-2",
                    "automation_id": "auto-2",
                    "project_id": "demo",
                    "trigger": "manual",
                    "status": "completed",
                    "due_at": run["due_at"],
                    "started_at": "2026-06-24T00:01:00+00:00",
                    "finished_at": "2026-06-24T00:01:04+00:00",
                    "summary": "Found TODO in src. Authorization: Bearer abcdefghijklmnop",
                    "stdout_excerpt": "todo remains api_key=secret-value",
                },
                workspace_session=session,
            )

            self.assertEqual(finalized["run"]["signal"], "finding")
            self.assertEqual(finalized["inbox_item"]["state"], "unread")
            self.assertEqual(finalized["inbox_item"]["disposition"], "finding")
            manifest_text = Path(finalized["artifact_ref"]).read_text(encoding="utf-8")
            self.assertIn("[REDACTED]", manifest_text)
            self.assertNotIn("secret-value", manifest_text)
            self.assertNotIn("abcdefghijklmnop", manifest_text)

    def test_finalize_run_maps_approval_required_and_supports_promote(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            projects, store, triage = self._make_services(root)
            automation = store.create_automation(self._automation_payload("auto-3"))
            run = store.record_run(self._run_payload("auto-3", "run-3"))
            session = self._workspace_session(projects, "auto-3", "run-3")

            finalized = triage.finalize_run(
                automation,
                run,
                {
                    "run_id": "run-3",
                    "automation_id": "auto-3",
                    "project_id": "demo",
                    "trigger": "manual",
                    "status": "failed",
                    "due_at": run["due_at"],
                    "started_at": "2026-06-24T00:02:00+00:00",
                    "finished_at": "2026-06-24T00:02:02+00:00",
                    "summary": "Blocked on approval.",
                    "redacted_error": "approval_required: needs confirmation",
                },
                workspace_session=session,
            )

            self.assertEqual(finalized["run"]["status"], "needs_review")
            self.assertEqual(finalized["inbox_item"]["disposition"], "approval_required")
            reviewed = triage.update_inbox_item(finalized["inbox_item"]["item_id"], {"state": "reviewed"})
            self.assertEqual(reviewed["state"], "reviewed")
            promoted = triage.promote_inbox_item(finalized["inbox_item"]["item_id"], "task:task-123")
            self.assertEqual(promoted["state"], "promoted")
            self.assertEqual(promoted["promotion_ref"], "task:task-123")

            reopened_projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            reopened_store = AutomationStore(reopened_projects)
            persisted = reopened_store.get_inbox_item(finalized["inbox_item"]["item_id"])
            self.assertEqual(persisted["state"], "promoted")
            self.assertEqual(persisted["promotion_ref"], "task:task-123")

    def _make_services(self, root: Path) -> tuple[ProjectService, AutomationStore, AutomationTriageService]:
        workspace = root / "workspace"
        project_file = root / "demo.abproj"
        projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
        projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
        store = AutomationStore(projects)
        triage = AutomationTriageService(projects, store)
        return projects, store, triage

    def _workspace_session(self, projects: ProjectService, automation_id: str, run_id: str):
        manager = AutomationWorkspaceManager(projects)
        return manager.prepare_workspace(
            {
                "automation_id": automation_id,
                "runtime": {"permission_mode": "read-only"},
                "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
            },
            {"run_id": run_id},
        )

    def _automation_payload(self, automation_id: str) -> dict[str, object]:
        return {
            "automation_id": automation_id,
            "project_id": "demo",
            "name": f"Automation {automation_id}",
            "kind": "standalone",
            "prompt": "Audit repo",
            "runtime": {"permission_mode": "workspace-write"},
            "triage": {"archive_no_signal": True, "notify_on": "every_run", "finding_keywords": ["todo", "fixme"]},
        }

    def _run_payload(self, automation_id: str, run_id: str) -> dict[str, object]:
        return {
            "run_id": run_id,
            "automation_id": automation_id,
            "project_id": "demo",
            "trigger": "manual",
            "status": "queued",
            "due_at": "2026-06-24T00:00:00+00:00",
            "signal": "unknown",
            "summary": "",
        }


if __name__ == "__main__":
    unittest.main()
