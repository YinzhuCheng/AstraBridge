from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.automations import AutomationStore
from astrabridge_sidecar.project_service import ProjectService


class AutomationStoreTests(unittest.TestCase):
    def test_store_crud_persists_specs_runs_and_inbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")

            store = AutomationStore(projects)
            created = store.create_automation(
                {
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "name": "Nightly audit",
                    "kind": "standalone",
                    "prompt": "Review repository health.",
                    "schedule": {"mode": "interval", "interval_minutes": 30},
                    "runtime": {
                        "permission_mode": "workspace-write",
                        "plugin_skill_preset_ids": ["project-default", "nightly-audit"],
                        "prompt_snapshot": {"headers": {"Authorization": "Bearer super-secret"}},
                    },
                }
            )

            self.assertEqual(created["automation_id"], "auto-1")
            self.assertEqual(created["schedule"]["expression"], "every:30m")
            self.assertEqual(created["runtime"]["plugin_skill_preset_ids"], ["project-default", "nightly-audit"])
            self.assertEqual(created["runtime"]["prompt_snapshot"]["headers"]["Authorization"], "[REDACTED]")
            self.assertEqual(store.list_automations()[0]["automation_id"], "auto-1")

            updated = store.update_automation(
                "auto-1",
                {
                    "description": "Updated description",
                    "schedule": {"mode": "daily", "expression": "08:15", "timezone": "Asia/Shanghai"},
                },
            )
            self.assertEqual(updated["description"], "Updated description")
            self.assertEqual(updated["schedule"]["expression"], "08:15")

            paused = store.pause_automation("auto-1")
            self.assertFalse(paused["enabled"])
            resumed = store.resume_automation("auto-1")
            self.assertTrue(resumed["enabled"])

            run = store.record_run(
                {
                    "run_id": "run-1",
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "trigger": "manual",
                    "status": "completed",
                    "due_at": "2026-06-24T12:00:00Z",
                    "started_at": "2026-06-24T12:00:05Z",
                    "finished_at": "2026-06-24T12:01:00Z",
                    "signal": "no_signal",
                    "summary": "completed cleanly",
                    "redacted_error": "Bearer secret should not persist",
                }
            )
            self.assertEqual(run["run_id"], "run-1")

            item = store.upsert_inbox_item(
                {
                    "item_id": "item-1",
                    "run_id": "run-1",
                    "automation_id": "auto-1",
                    "project_id": "demo",
                    "state": "unread",
                    "disposition": "finding",
                    "severity": "warning",
                    "title": "Repository drift",
                    "summary": "api_key leaked in output",
                }
            )
            self.assertEqual(item["item_id"], "item-1")
            self.assertEqual(store.inbox_summary("auto-1")["unread"], 1)

            reopened_projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            reopened_store = AutomationStore(reopened_projects)
            reopened = reopened_store.get_automation("auto-1")
            self.assertIsNotNone(reopened)
            self.assertEqual(reopened["last_status"], "completed")
            self.assertEqual(reopened["last_run_at"], "2026-06-24T12:01:00Z")
            self.assertEqual(reopened["inbox_summary"]["unread"], 1)
            self.assertEqual(reopened["runtime"]["plugin_skill_preset_ids"], ["project-default", "nightly-audit"])
            self.assertEqual(reopened_store.list_runs("auto-1")[0]["run_id"], "run-1")
            self.assertEqual(reopened_store.list_inbox_items("auto-1")[0]["item_id"], "item-1")

    def test_delete_is_soft_and_store_redacts_secret_like_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")

            store = AutomationStore(projects)
            store.create_automation(
                {
                    "automation_id": "auto-2",
                    "project_id": "demo",
                    "name": "Sensitive audit",
                    "kind": "standalone",
                    "prompt": "Authorization: Bearer abc123456789",
                    "runtime": {
                        "prompt_snapshot": {
                            "headers": {"Authorization": "Bearer abc123456789"},
                            "env": {"API_KEY": "top-secret"},
                        }
                    },
                }
            )
            archived = store.delete_automation("auto-2")
            self.assertIsNotNone(archived["archived_at"])
            self.assertIsNone(store.get_automation("auto-2"))
            self.assertEqual(store.get_automation("auto-2", include_archived=True)["archived_reason"], "deleted")

            state_path = workspace / ".astrabridge" / "automations" / "automations.json"
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            serialized = json.dumps(saved, ensure_ascii=False)
            self.assertIn("[REDACTED]", serialized)
            self.assertNotIn("Bearer abc123456789", serialized)
            self.assertNotIn("top-secret", serialized)


if __name__ == "__main__":
    unittest.main()
