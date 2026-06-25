from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.automations import (
    AUTOMATION_SPEC_SCHEMA_VERSION,
    AutomationInboxItem,
    AutomationRun,
    AutomationSpec,
    assert_transition_run_status,
    can_transition_run_status,
)


class AutomationSpecTests(unittest.TestCase):
    def test_automation_spec_normalizes_schedule_runtime_and_redacts_prompt_snapshot(self) -> None:
        spec = AutomationSpec.normalize(
            {
                "automation_id": "auto-1",
                "project_id": "proj-1",
                "name": "Daily review",
                "description": "Check repo health",
                "enabled": True,
                "kind": "standalone",
                "prompt": "Summarize findings.",
                "schedule": {
                    "mode": "daily",
                    "expression": "09:30",
                    "timezone": "Asia/Shanghai",
                    "catch_up_policy": "run_once",
                },
                "runtime": {
                    "profile_id": "deepseek-default",
                    "model": "deepseek-v4-pro",
                    "permission_mode": "workspace-write",
                    "execution_host": "wsl",
                    "mcp_preset_ids": ["context7", "context7", "astrabridge_web"],
                    "plugin_skill_preset_ids": ["project-default", "project-default", "plugin-audit"],
                    "prompt_snapshot": {
                        "headers": {"Authorization": "Bearer abc"},
                        "env": {"API_KEY": "secret-value"},
                    },
                },
                "workspace": {"mode": "dedicated_worktree", "cleanup_policy": "keep_on_failure"},
                "triage": {"archive_no_signal": True, "notify_on": "finding", "finding_keywords": ["todo", "fixme", "todo"]},
                "limits": {"timeout_sec": 900, "max_retries": 2, "max_artifact_bytes": 4096, "max_parallel_runs": 1},
            }
        )

        self.assertEqual(spec.schema_version, AUTOMATION_SPEC_SCHEMA_VERSION)
        self.assertEqual(spec.schedule["expression"], "09:30")
        self.assertEqual(spec.schedule["catch_up_policy"], "run_once")
        self.assertEqual(spec.runtime["mcp_preset_ids"], ["context7", "astrabridge_web"])
        self.assertEqual(spec.runtime["plugin_skill_preset_ids"], ["project-default", "plugin-audit"])
        self.assertEqual(spec.runtime["prompt_snapshot"]["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(spec.runtime["prompt_snapshot"]["env"]["API_KEY"], "[REDACTED]")
        self.assertEqual(spec.workspace["mode"], "dedicated_worktree")
        self.assertEqual(spec.triage["finding_keywords"], ["todo", "fixme"])

    def test_automation_spec_rejects_invalid_schedule_and_full_access_without_opt_in(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported automation schedule mode"):
            AutomationSpec.normalize(
                {
                    "automation_id": "auto-1",
                    "project_id": "proj-1",
                    "name": "Broken",
                    "kind": "standalone",
                    "prompt": "x",
                    "schedule": {"mode": "cron"},
                }
            )

        with self.assertRaisesRegex(ValueError, "full-access automation runtime requires dangerous_opt_in=true"):
            AutomationSpec.normalize(
                {
                    "automation_id": "auto-2",
                    "project_id": "proj-1",
                    "name": "Danger",
                    "kind": "standalone",
                    "prompt": "x",
                    "runtime": {"permission_mode": "full-access"},
                }
            )

    def test_automation_spec_rejects_invalid_daily_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "daily schedule HH:MM is out of range"):
            AutomationSpec.normalize(
                {
                    "automation_id": "auto-3",
                    "project_id": "proj-1",
                    "name": "Bad time",
                    "kind": "standalone",
                    "prompt": "x",
                    "schedule": {"mode": "daily", "expression": "25:00"},
                }
            )


class AutomationRunTests(unittest.TestCase):
    def test_automation_run_normalizes_fields(self) -> None:
        run = AutomationRun.normalize(
            {
                "run_id": "run-1",
                "automation_id": "auto-1",
                "project_id": "proj-1",
                "trigger": "manual",
                "status": "running",
                "due_at": "2026-06-24T12:00:00Z",
                "signal": "unknown",
                "summary": "started",
                "artifact_refs": ["a", "a", "b"],
                "exit_code": "",
            }
        )

        self.assertEqual(run.trigger, "manual")
        self.assertEqual(run.status, "running")
        self.assertEqual(run.artifact_refs, ["a", "b"])
        self.assertIsNone(run.exit_code)

    def test_run_status_transition_matrix(self) -> None:
        self.assertTrue(can_transition_run_status("queued", "running"))
        self.assertTrue(can_transition_run_status("running", "needs_review"))
        self.assertFalse(can_transition_run_status("completed", "running"))
        with self.assertRaisesRegex(ValueError, "Invalid automation run status transition"):
            assert_transition_run_status("completed", "failed")


class AutomationInboxTests(unittest.TestCase):
    def test_automation_inbox_item_normalizes_and_validates(self) -> None:
        item = AutomationInboxItem.normalize(
            {
                "item_id": "item-1",
                "run_id": "run-1",
                "automation_id": "auto-1",
                "project_id": "proj-1",
                "state": "unread",
                "disposition": "finding",
                "severity": "warning",
                "title": "New finding",
                "summary": "repo drift",
            }
        )

        self.assertEqual(item.state, "unread")
        self.assertEqual(item.disposition, "finding")
        self.assertEqual(item.severity, "warning")

        with self.assertRaisesRegex(ValueError, "Unsupported automation inbox disposition"):
            AutomationInboxItem.normalize(
                {
                    "item_id": "item-2",
                    "run_id": "run-1",
                    "automation_id": "auto-1",
                    "project_id": "proj-1",
                    "state": "unread",
                    "disposition": "mystery",
                    "severity": "warning",
                    "title": "bad",
                }
            )


if __name__ == "__main__":
    unittest.main()
