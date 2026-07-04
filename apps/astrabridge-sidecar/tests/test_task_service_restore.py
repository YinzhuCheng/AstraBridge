import tempfile
import unittest
from pathlib import Path

from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.task_service import TaskService


class TaskServiceRestoreActiveProviderThreadTests(unittest.TestCase):
    def test_restore_active_provider_thread_switches_to_thread_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Restore owner", root / "restore-owner.abproj", workspace_root=workspace)
            tasks = TaskService(projects)

            old_task = tasks.create_task(
                "Old Kimi task",
                thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2",
                    "reasoning_effort": "high",
                },
            )
            owner_task = tasks.create_task(
                "Shell file task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                },
            )
            tasks.switch_task(str(old_task["task_id"]))

            restored = tasks.restore_active_provider_thread("thread-deepseek")

            self.assertIsNotNone(restored)
            self.assertEqual(restored["task_id"], owner_task["task_id"])
            self.assertEqual(restored["active_provider_thread_id"], "thread-deepseek")
            self.assertEqual(projects.current_project["current_task_id"], owner_task["task_id"])
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek")

            snapshot = tasks.snapshot()
            self.assertEqual(snapshot["current_task"]["task_id"], owner_task["task_id"])
            old_snapshot = next(item for item in snapshot["tasks"] if item["task_id"] == old_task["task_id"])
            old_thread_ids = {item["thread_id"] for item in old_snapshot["provider_threads"]}
            self.assertNotIn("thread-deepseek", old_thread_ids)

    def test_provider_handoff_makes_target_thread_active_and_preserves_source_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Handoff task", root / "handoff.abproj", workspace_root=workspace)
            tasks = TaskService(projects)

            task = tasks.create_task(
                "Provider handoff",
                thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2",
                    "reasoning_effort": "high",
                },
            )

            event = tasks.record_provider_handoff(
                from_thread_id="thread-kimi",
                to_thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                reused_existing=False,
            )

            current = tasks.current_task()
            self.assertIsNotNone(current)
            self.assertEqual(current["task_id"], task["task_id"])
            self.assertEqual(current["active_provider_thread_id"], "thread-deepseek")
            self.assertEqual(projects.current_project["current_task_id"], task["task_id"])
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek")

            provider_threads = {item["thread_id"]: item for item in current["provider_threads"]}
            self.assertEqual(provider_threads["thread-kimi"]["provider_id"], "kimi")
            self.assertEqual(provider_threads["thread-kimi"]["model"], "kimi-k2")
            self.assertEqual(provider_threads["thread-deepseek"]["provider_id"], "deepseek")
            self.assertEqual(provider_threads["thread-deepseek"]["model"], "deepseek-v4-pro")
            self.assertEqual(event["from_thread_id"], "thread-kimi")
            self.assertEqual(event["to_thread_id"], "thread-deepseek")
            self.assertEqual(current["handoff_events"][-1]["event_id"], event["event_id"])

    def test_missing_active_provider_thread_marks_diagnostic_and_falls_back_to_live_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Missing thread fallback", root / "missing.abproj", workspace_root=workspace)
            tasks = TaskService(projects)

            tasks.create_task(
                "Missing fallback",
                thread_id="thread-old",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2",
                    "reasoning_effort": "high",
                },
            )
            tasks.bind_thread(
                thread_id="thread-live",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                },
                role="provider",
                make_active=True,
            )

            self.assertEqual(tasks.visible_provider_thread_id(include_missing_fallback=True), "thread-live")
            tasks.mark_provider_thread_missing("thread-live", reason="runtime_thread_not_found")

            current = tasks.current_task()
            self.assertIsNotNone(current)
            self.assertEqual(current["active_provider_thread_id"], "thread-old")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-old")
            self.assertEqual(tasks.visible_provider_thread_id(include_missing_fallback=True), "thread-old")

            provider_threads = {item["thread_id"]: item for item in current["provider_threads"]}
            self.assertEqual(provider_threads["thread-live"]["missing_reason"], "runtime_thread_not_found")
            self.assertIn("missing_at", provider_threads["thread-live"])
            self.assertNotIn("missing_at", provider_threads["thread-old"])


if __name__ == "__main__":
    unittest.main()
