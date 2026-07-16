from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.task_service import TaskService
from astrabridge_sidecar.title_suggestion_service import TitleSuggestionService


class FakeTitleRouter:
    def __init__(self, text: str = "Generated Title", *, fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def complete_response(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(dict(payload))
        if self.fail:
            raise RuntimeError("provider unavailable")
        return {"normalized": SimpleNamespace(text=self.text)}


class ProjectSidebarSnapshotTests(unittest.TestCase):
    def test_sidebar_snapshot_reads_recent_project_tasks_without_switching_current_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_workspace = root / "first-workspace"
            second_workspace = root / "second-workspace"
            first_workspace.mkdir()
            second_workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("First Project", root / "first.abproj", workspace_root=first_workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Inspect pricing API",
                thread_id="thread-first",
                settings={"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3.7-plus", "reasoning_effort": "high"},
            )
            tasks.bind_thread(
                thread_id="thread-openai",
                settings={"profile_id": "openai-default", "provider_id": "openai", "model": "gpt-5.5", "reasoning_effort": "high"},
                make_active=False,
            )
            tasks.record_provider_handoff(
                from_thread_id="thread-openai",
                to_thread_id="thread-first",
                settings={"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3.7-plus", "reasoning_effort": "high"},
                reused_existing=True,
            )
            projects.create_project("Second Project", root / "second.abproj", workspace_root=second_workspace)
            current_before = str(projects.current_project["project_file"])

            snapshot = projects.sidebar_snapshot()

            self.assertEqual(str(projects.current_project["project_file"]), current_before)
            self.assertEqual(snapshot["schema_version"], "astrabridge-sidebar-v1")
            self.assertEqual([item["name"] for item in snapshot["projects"][:2]], ["Second Project", "First Project"])
            first_node = next(item for item in snapshot["projects"] if item["name"] == "First Project")
            self.assertFalse(first_node["is_current"])
            self.assertEqual(first_node["tasks"][0]["title"], "Inspect pricing API")
            self.assertEqual(first_node["tasks"][0]["threads"][0]["thread_id"], "thread-first")
            self.assertEqual(first_node["tasks"][0]["lane_count"], 2)
            self.assertEqual(first_node["tasks"][0]["active_lane_label"], "qwen / qwen3.7-plus")
            self.assertEqual(first_node["tasks"][0]["previous_lane_label"], "openai / gpt-5.5")

    def test_sidebar_snapshot_reads_task_state_through_cross_host_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "cross-host-workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            project_path = root / "cross-host.abproj"
            projects.create_project("Cross Host", project_path, workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Keep task navigation visible", thread_id="thread-cross-host")

            windows_project_path = r"D:\workspace\cross-host.abproj"
            windows_workspace_root = r"D:\workspace"
            project_payload = json.loads(project_path.read_text(encoding="utf-8"))
            project_payload["project_file"] = windows_project_path
            project_payload["workspace_root"] = windows_workspace_root
            project_path.write_text(json.dumps(project_payload), encoding="utf-8")

            recent_payload = json.loads((root / "projects.json").read_text(encoding="utf-8"))
            recent_payload["projects"][0]["project_file"] = windows_project_path
            recent_payload["projects"][0]["workspace_root"] = windows_workspace_root
            (root / "projects.json").write_text(json.dumps(recent_payload), encoding="utf-8")
            projects.close_project()

            aliases = {
                windows_project_path: project_path,
                windows_workspace_root: workspace,
            }
            with patch("astrabridge_sidecar.project_service.path_for_host", side_effect=lambda value: aliases.get(str(value), Path(str(value)))):
                snapshot = projects.sidebar_snapshot()

            self.assertEqual(len(snapshot["projects"]), 1)
            self.assertEqual(snapshot["projects"][0]["project_file"], windows_project_path)
            self.assertEqual([task["title"] for task in snapshot["projects"][0]["tasks"]], ["Keep task navigation visible"])

    def test_sidebar_snapshot_contains_warning_for_corrupt_task_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Corrupt Task State", root / "corrupt.abproj", workspace_root=workspace)
            task_state = workspace / ".astrabridge" / "tasks.json"
            task_state.parent.mkdir(parents=True, exist_ok=True)
            task_state.write_text("{not-json", encoding="utf-8")

            snapshot = projects.sidebar_snapshot()

            self.assertEqual(snapshot["projects"][0]["tasks"], [])
            self.assertTrue(any("task_state_read_failed" in warning for warning in snapshot["projects"][0]["warnings"]))

    def test_sidebar_snapshot_prefers_task_state_current_task_over_stale_project_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            project_file = root / "stale-sidebar.abproj"
            projects.create_project("Sidebar Repair", project_file, workspace_root=workspace)
            tasks = TaskService(projects)

            stale = tasks.create_task(
                "Stale Task",
                thread_id="thread-qwen",
                settings={"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3.7-plus", "reasoning_effort": "high"},
            )
            target = tasks.create_task("Current DG Task")
            tasks.switch_task(str(target["task_id"]))

            projects.update_project({"current_task_id": stale["task_id"], "current_thread_id": "thread-qwen"})

            snapshot = projects.sidebar_snapshot()

            node = snapshot["projects"][0]
            stale_item = next(item for item in node["tasks"] if item["task_id"] == stale["task_id"])
            target_item = next(item for item in node["tasks"] if item["task_id"] == target["task_id"])
            self.assertFalse(stale_item["is_current"])
            self.assertTrue(target_item["is_current"])

    def test_sidebar_snapshot_strips_smoke_prefix_from_lane_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Lane Labels", root / "lane-labels.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Step 11 source for compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run",
                thread_id="thread-step11",
                settings={"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3.7-plus", "reasoning_effort": "high"},
            )
            tasks.bind_thread(
                thread_id="thread-step11",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3.7-plus",
                    "reasoning_effort": "high",
                    "name": "Step 11 source for compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run",
                },
                make_active=True,
            )

            snapshot = projects.sidebar_snapshot()

            task = snapshot["projects"][0]["tasks"][0]
            self.assertEqual(task["title"], "compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run")
            self.assertEqual(task["active_lane_label"], "compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run")


class TitleSuggestionServiceTests(unittest.TestCase):
    def test_project_title_suggestion_uses_llm_for_generic_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("New project", root / "title.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "New task",
                thread_id="thread-title",
                settings={"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3.7-plus", "reasoning_effort": "high"},
            )
            router = FakeTitleRouter("调研 API 成本")
            service = TitleSuggestionService(projects, tasks, router)

            result = service.suggest_project_title()

            self.assertEqual(result["source"], "llm")
            self.assertTrue(result["changed"])
            self.assertEqual(projects.current_project["name"], "调研 API 成本")
            self.assertEqual(len(router.calls), 1)

    def test_title_suggestion_does_not_override_manual_task_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Manual Project", root / "manual.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Human named task")
            router = FakeTitleRouter("Should Not Apply")
            service = TitleSuggestionService(projects, tasks, router)

            result = service.suggest_current_task_title()

            self.assertEqual(result["source"], "unchanged")
            self.assertFalse(result["changed"])
            self.assertEqual(router.calls, [])
            self.assertEqual(tasks.current_task()["title"], "Human named task")

    def test_task_title_suggestion_falls_back_when_provider_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Fallback Project", root / "fallback.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Fallback Project",
                thread_id="thread-deepseek",
                settings={"profile_id": "deepseek-default", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "high"},
            )
            service = TitleSuggestionService(projects, tasks, FakeTitleRouter(fail=True))

            result = service.suggest_current_task_title()

            self.assertEqual(result["source"], "heuristic")
            self.assertTrue(result["changed"])
            self.assertEqual(tasks.current_task()["title"], "deepseek deepseek-v4-pro")


if __name__ == "__main__":
    unittest.main()
