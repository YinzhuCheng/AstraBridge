import tempfile
import unittest
from pathlib import Path

from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.task_service import TaskService


class TaskServiceRestoreActiveProviderThreadTests(unittest.TestCase):
    def test_current_task_prefers_task_state_over_stale_project_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            project_file = root / "projection.abproj"
            projects.create_project("Projection repair", project_file, workspace_root=workspace)
            tasks = TaskService(projects)

            stale = tasks.create_task(
                "Stale projected task",
                thread_id="thread-qwen",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3.7-plus",
                    "reasoning_effort": "high",
                },
            )
            target = tasks.create_task("Lane-less DG task")
            tasks.switch_task(str(stale["task_id"]))
            tasks.switch_task(str(target["task_id"]))

            projects.update_project({"current_task_id": stale["task_id"], "current_thread_id": "thread-qwen"})

            current = tasks.current_task()

            self.assertIsNotNone(current)
            self.assertEqual(current["task_id"], target["task_id"])
            self.assertEqual(projects.current_project["current_task_id"], target["task_id"])
            self.assertIsNone(projects.current_project["current_thread_id"])

            persisted = project_file.read_text(encoding="utf-8")
            self.assertIn(f'"current_task_id": "{target["task_id"]}"', persisted)
            self.assertIn('"current_thread_id": null', persisted)

    def test_switch_task_returns_full_current_task_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Switch task shape", root / "switch-shape.abproj", workspace_root=workspace)
            tasks = TaskService(projects)

            created = tasks.create_task(
                "Switch target",
                thread_id="thread-qwen",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3.7-plus",
                    "reasoning_effort": "high",
                },
            )
            tasks.create_task("Other task")

            switched = tasks.switch_task(str(created["task_id"]))

            self.assertEqual(switched["task_id"], created["task_id"])
            self.assertEqual(switched["active_provider_thread_id"], "thread-qwen")
            self.assertIn("provider_threads", switched)
            self.assertEqual(switched["provider_threads"][0]["thread_id"], "thread-qwen")

    def test_snapshot_and_switch_task_use_persisted_current_task_projection_without_normalizing_current_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Fast task projection", root / "fast-projection.abproj", workspace_root=workspace)
            tasks = TaskService(projects)

            target = tasks.create_task(
                "Target task",
                thread_id="thread-qwen",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3.7-plus",
                    "reasoning_effort": "high",
                },
            )
            current = tasks.create_task("Other task")

            def _fail_current_task() -> dict[str, object] | None:
                raise AssertionError("current_task normalization should not run for snapshot/switch fast path")

            tasks.current_task = _fail_current_task  # type: ignore[method-assign]

            snapshot = tasks.snapshot()
            switched = tasks.switch_task(str(target["task_id"]))

            self.assertEqual(snapshot["current_task"]["task_id"], current["task_id"])
            self.assertEqual(switched["task_id"], target["task_id"])
            self.assertIn("provider_threads", switched)
            self.assertEqual(switched["provider_threads"][0]["thread_id"], "thread-qwen")

    def test_bind_thread_to_explicit_lane_less_task_preserves_task_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Task binding", root / "task-binding.abproj", workspace_root=workspace)
            tasks = TaskService(projects)

            selected = tasks.create_task("DG Multimodal UI")
            bound = tasks.bind_thread_to_task_id(
                task_id=str(selected["task_id"]),
                thread_id="thread-qwen-vision",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-vl-plus",
                    "reasoning_effort": "medium",
                },
            )

            self.assertEqual(bound["task_id"], selected["task_id"])
            self.assertEqual(bound["title"], "DG Multimodal UI")
            self.assertEqual(bound["active_provider_thread_id"], "thread-qwen-vision")
            self.assertEqual(projects.current_project["current_task_id"], selected["task_id"])
            self.assertEqual(projects.current_project["current_thread_id"], "thread-qwen-vision")
            self.assertEqual(len(tasks.snapshot()["tasks"]), 1)

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
            old_snapshot = next(item for item in tasks._state()["tasks"] if item["task_id"] == old_task["task_id"])
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
