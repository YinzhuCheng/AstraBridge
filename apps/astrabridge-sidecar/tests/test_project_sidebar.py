from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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
            self.assertEqual(first_node["tasks"][0]["lane_count"], 1)
            self.assertEqual(first_node["tasks"][0]["active_lane_label"], "qwen / qwen3.7-plus")

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
