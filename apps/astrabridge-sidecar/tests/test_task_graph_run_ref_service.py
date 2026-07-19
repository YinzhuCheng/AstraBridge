from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.task_graph_run_ref_service import TaskGraphRunRefService
from astrabridge_sidecar.task_service import TaskService


class TaskGraphRunRefServiceTests(unittest.TestCase):
    def _build_tasks(self) -> tuple[TaskService, TaskGraphRunRefService]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
        os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = str(root / "runtime-root")
        self.addCleanup(
            lambda: (
                os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                if previous_runtime_root is None
                else os.environ.__setitem__("ASTRABRIDGE_RUNTIME_ROOT", previous_runtime_root)
            )
        )
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "PRIVATE").mkdir()
        (workspace / ".astrabridge").mkdir()
        projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
        projects.create_project("Run ref owner", root / "run-ref.abproj", workspace_root=workspace)
        tasks = TaskService(projects)
        tasks.create_task("Run ref task")
        return tasks, TaskGraphRunRefService(tasks)

    def test_task_response_graph_run_refs_compacts_shell_polling_payloads(self) -> None:
        _tasks, owner = self._build_tasks()
        compacted = owner.task_response_graph_run_refs(
            [
                {
                    "run_id": "run-1",
                    "graph_id": "graph-1",
                    "task_id": "task-1",
                    "status": "completed",
                    "artifact_count": 1,
                    "event_count": 2,
                    "worker_count": 1,
                    "metrics": {"duration_ms": 12},
                    "budget": {"total_tokens": 10},
                    "artifacts": [{"path": "PRIVATE/large-output.json", "content": "not for task list"}],
                    "events": [{"summary": "not for task list"}],
                    "worker_bindings": [{"node_id": "node-1", "status": "completed"}],
                }
            ]
        )

        visible = compacted[0]
        self.assertEqual(visible["run_id"], "run-1")
        self.assertEqual(visible["artifact_count"], 1)
        self.assertIn("worker_bindings", visible)
        self.assertNotIn("artifacts", visible)
        self.assertNotIn("events", visible)

    def test_graph_activity_summary_reports_latest_run_and_counts(self) -> None:
        _tasks, owner = self._build_tasks()
        summary = owner.graph_activity_summary(
            {
                "graph_definitions": [
                    {"graph_id": "graph-new", "status": "ready", "updated_at": "2026-07-19T16:10:00+09:00"},
                    {"graph_id": "graph-old", "status": "archived", "updated_at": "2026-07-18T16:10:00+09:00"},
                ],
                "graph_run_refs": [
                    {"run_id": "run-new", "status": "running", "updated_at": "2026-07-19T16:11:00+09:00"},
                    {"run_id": "run-old", "status": "completed", "updated_at": "2026-07-18T16:11:00+09:00"},
                ],
            }
        )

        self.assertEqual(summary["graph_count"], 2)
        self.assertEqual(summary["run_count"], 2)
        self.assertEqual(summary["latest_graph_id"], "graph-new")
        self.assertEqual(summary["latest_run_id"], "run-new")
        self.assertEqual(summary["latest_run_status"], "running")
        self.assertEqual(summary["graph_status_counts"]["ready"], 1)
        self.assertEqual(summary["run_status_counts"]["completed"], 1)

    def test_merge_task_graph_run_ref_preserves_richer_equal_timestamp_snapshot(self) -> None:
        _tasks, owner = self._build_tasks()
        same_timestamp = "2026-07-19T16:12:00+09:00"
        richer_existing = {
            "run_id": "run-1",
            "status": "running",
            "updated_at": same_timestamp,
            "latest_event_at": same_timestamp,
            "latest_event_type": "node_completed",
            "node_status_counts": {"completed": 1, "waiting_on_dependencies": 2},
            "node_outcome_counts": {"passed": 1, "pending": 2},
            "timeline_events": [
                {"event_id": "run-1-created", "event_type": "run_created", "created_at": "2026-07-19T16:11:00+09:00"},
                {"event_id": "run-1-node-started", "event_type": "node_started", "node_id": "node-1", "created_at": "2026-07-19T16:11:30+09:00"},
                {"event_id": "run-1-node-completed", "event_type": "node_completed", "node_id": "node-1", "created_at": same_timestamp},
            ],
            "event_count": 3,
            "worker_count": 1,
            "artifact_refs": [
                {"artifact_id": "compiled-plan", "artifact_kind": "graph_definition", "path": "PRIVATE/task-graph/live-run/run/compiled-plan.json", "status": "ready"},
                {"artifact_id": "handoff-json", "artifact_kind": "structured_json", "path": "PRIVATE/task-graph/live-run/run/node-1/handoff.json", "status": "ready"},
            ],
            "artifact_count": 2,
        }
        stale_candidate = {
            "run_id": "run-1",
            "status": "running",
            "updated_at": same_timestamp,
            "latest_event_at": same_timestamp,
            "latest_event_type": "node_started",
            "node_status_counts": {"running": 1, "waiting_on_dependencies": 4},
            "node_outcome_counts": {"pending": 5},
            "timeline_events": [
                {"event_id": "run-1-created", "event_type": "run_created", "created_at": "2026-07-19T16:11:00+09:00"},
                {"event_id": "run-1-node-started", "event_type": "node_started", "node_id": "node-1", "created_at": "2026-07-19T16:11:30+09:00"},
            ],
            "event_count": 2,
            "worker_count": 0,
            "artifact_refs": [
                {"artifact_id": "compiled-plan", "artifact_kind": "graph_definition", "path": "PRIVATE/task-graph/live-run/run/compiled-plan.json", "status": "ready"},
            ],
            "artifact_count": 1,
        }

        merged = owner.merge_task_graph_run_ref(richer_existing, stale_candidate)

        self.assertEqual(merged["status"], "running")
        self.assertEqual(merged["latest_event_type"], "node_completed")
        self.assertEqual(merged["node_status_counts"]["completed"], 1)
        self.assertEqual(merged["node_status_counts"]["waiting_on_dependencies"], 4)
        self.assertEqual(merged["event_count"], 3)
        self.assertEqual(len(merged["timeline_events"]), 3)
        self.assertTrue(any(item["event_type"] == "node_completed" for item in merged["timeline_events"]))
        self.assertEqual(merged["artifact_count"], 2)
        self.assertTrue(any(item["artifact_id"] == "handoff-json" for item in merged["artifact_refs"]))


if __name__ == "__main__":
    unittest.main()
