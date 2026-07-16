from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.task_graph_contract import load_task_graph_fixture, load_task_graph_run_fixture
from astrabridge_sidecar.task_service import TaskService


class TaskGraphTaskPersistenceTests(unittest.TestCase):
    def test_graph_definition_and_run_ref_persist_under_task_state_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph persistence", root / "graph.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            task = tasks.create_task("Graph task")

            graph = _graph_for_task("provider_update_smoke_gate", task_id=task["task_id"])
            run = _run_for_task("provider_update_smoke_gate", task_id=task["task_id"], graph_id=graph["graph_id"])

            saved_graph = tasks.upsert_graph_definition(graph)
            saved_run = tasks.record_graph_run(run, graph_definition=saved_graph)

            reloaded = TaskService(projects).current_task()

            self.assertIsNotNone(reloaded)
            self.assertEqual(reloaded["graph_definitions"][0]["graph_id"], saved_graph["graph_id"])
            self.assertEqual(reloaded["graph_run_refs"][0]["run_id"], saved_run["run_id"])
            self.assertEqual(reloaded["graph_activity_summary"]["graph_count"], 1)
            self.assertEqual(reloaded["graph_activity_summary"]["run_count"], 1)
            self.assertEqual(reloaded["graph_activity_summary"]["latest_run_status"], "ready_for_dry_run")
            self.assertNotIn("thread_id", reloaded["graph_activity_summary"])

    def test_current_task_normalizes_duplicate_graph_definitions_and_full_run_objects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph normalize", root / "normalize.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            created = tasks.create_task("Normalize task")

            graph = _graph_for_task("document_extract_analyze_report", task_id=created["task_id"])
            run = _run_for_task("document_extract_analyze_report", task_id=created["task_id"], graph_id=graph["graph_id"])
            state = tasks._state()  # noqa: SLF001
            state["tasks"][0]["graph_definitions"] = [graph, graph]
            state["tasks"][0]["graph_run_refs"] = [run, run]
            tasks._write_state(state)  # noqa: SLF001

            normalized = TaskService(projects).current_task()

            self.assertIsNotNone(normalized)
            self.assertEqual(normalized["task_id"], created["task_id"])
            self.assertEqual(len(normalized["graph_definitions"]), 1)
            self.assertEqual(len(normalized["graph_run_refs"]), 1)
            self.assertEqual(normalized["graph_run_refs"][0]["artifact_count"], 0)
            self.assertEqual(normalized["graph_activity_summary"]["latest_graph_id"], graph["graph_id"])

    def test_record_graph_run_uses_current_task_graph_definition_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph lookup", root / "lookup.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            task = tasks.create_task("Lookup task")

            graph = tasks.upsert_graph_definition(_graph_for_task("supervisor_worker_synthesizer", task_id=task["task_id"]))
            run = _run_for_task("supervisor_worker_synthesizer", task_id=task["task_id"], graph_id=graph["graph_id"])

            saved_run = tasks.record_graph_run(run)
            latest_graph = tasks.graph_definition()
            latest_run = tasks.graph_run_ref()

            self.assertEqual(graph["graph_id"], latest_graph["graph_id"])
            self.assertEqual(saved_run["run_id"], latest_run["run_id"])
            self.assertEqual(latest_run["graph_id"], graph["graph_id"])

    def test_stale_equal_timestamp_graph_run_save_preserves_richer_snapshot_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph merge richness", root / "graph-merge.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            task = tasks.create_task("Graph merge task")

            graph = tasks.upsert_graph_definition(_graph_for_task("fanout_fanin_research", task_id=task["task_id"]))
            run = _run_for_task("fanout_fanin_research", task_id=task["task_id"], graph_id=graph["graph_id"])
            saved_run = tasks.record_graph_run(run)
            stale_task = copy.deepcopy(tasks.current_task())
            self.assertIsNotNone(stale_task)

            run_id = saved_run["run_id"]
            richer_ref = copy.deepcopy(tasks.graph_run_ref(run_id))
            self.assertIsNotNone(richer_ref)
            same_timestamp = "2026-07-14T02:34:34.246024+09:00"
            richer_ref["status"] = "running"
            richer_ref["updated_at"] = same_timestamp
            richer_ref["latest_event_at"] = same_timestamp
            richer_ref["latest_event_type"] = "node_completed"
            richer_ref["node_status_counts"] = {"completed": 1, "waiting_on_dependencies": 2}
            richer_ref["node_outcome_counts"] = {"passed": 1, "pending": 2}
            richer_ref["timeline_events"] = [
                {"event_id": f"{run_id}-created", "event_type": "run_created", "created_at": "2026-07-14T02:33:00+09:00"},
                {"event_id": f"{run_id}-node_supervisor-started", "event_type": "node_started", "node_id": "node_supervisor", "created_at": "2026-07-14T02:33:09+09:00"},
                {"event_id": f"{run_id}-node_supervisor-completed", "event_type": "node_completed", "node_id": "node_supervisor", "created_at": same_timestamp},
            ]
            richer_ref["event_count"] = 3
            richer_ref["worker_count"] = 1
            richer_ref["artifact_refs"] = [
                {"artifact_id": "compiled-plan", "artifact_kind": "graph_definition", "path": "PRIVATE/task-graph/live-run/run/compiled-plan.json", "status": "ready"},
                {"artifact_id": "handoff-json", "artifact_kind": "structured_json", "path": "PRIVATE/task-graph/live-run/run/node_supervisor/handoff.json", "status": "ready"},
            ]
            richer_ref["artifact_count"] = 2
            tasks.persist_graph_run_ref(richer_ref)

            stale_run_ref = next(item for item in stale_task["graph_run_refs"] if item["run_id"] == run_id)
            stale_run_ref["status"] = "running"
            stale_run_ref["updated_at"] = same_timestamp
            stale_run_ref["latest_event_at"] = same_timestamp
            stale_run_ref["latest_event_type"] = "node_completed"
            stale_run_ref["node_status_counts"] = {"running": 1, "waiting_on_dependencies": 4}
            stale_run_ref["node_outcome_counts"] = {"pending": 5}
            stale_run_ref["timeline_events"] = [
                {"event_id": f"{run_id}-created", "event_type": "run_created", "created_at": "2026-07-14T02:33:00+09:00"},
                {"event_id": f"{run_id}-node_supervisor-started", "event_type": "node_started", "node_id": "node_supervisor", "created_at": "2026-07-14T02:33:09+09:00"},
            ]
            stale_run_ref["event_count"] = 2
            stale_run_ref["worker_count"] = 0
            stale_run_ref["artifact_refs"] = [
                {"artifact_id": "compiled-plan", "artifact_kind": "graph_definition", "path": "PRIVATE/task-graph/live-run/run/compiled-plan.json", "status": "ready"},
            ]
            stale_run_ref["artifact_count"] = 1
            stale_task["updated_at"] = same_timestamp
            tasks._save_task(stale_task)  # noqa: SLF001

            restored = tasks.graph_run_ref(run_id)
            self.assertEqual(restored["status"], "running")
            self.assertEqual(restored["latest_event_type"], "node_completed")
            self.assertEqual(restored["node_status_counts"]["completed"], 1)
            self.assertEqual(restored["node_status_counts"]["waiting_on_dependencies"], 4)
            self.assertEqual(restored["event_count"], 3)
            self.assertEqual(len(restored["timeline_events"]), 3)
            self.assertTrue(any(item["event_type"] == "node_completed" for item in restored["timeline_events"]))
            self.assertEqual(restored["artifact_count"], 3)
            self.assertTrue(any(item["artifact_id"] == "handoff-json" for item in restored["artifact_refs"]))
            self.assertEqual(restored["worker_count"], 1)

    def test_instantiate_graph_template_rebinds_stale_default_models_to_available_catalog_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph defaults", root / "defaults.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Defaults task")

            configured_models = [
                {
                    "id": "qwen/qwen3.7-plus",
                    "provider": "qwen",
                    "native_model": "qwen3.7-plus",
                    "enabled": True,
                    "deprecated": False,
                }
            ]

            graph = tasks.instantiate_graph_template(
                "supervisor_worker_synthesizer",
                configured_models=configured_models,
            )["graph"]

            node_models = {
                node["node_id"]: node.get("model_id")
                for node in graph["nodes"]
            }
            self.assertEqual(node_models["node_supervisor"], "qwen3.7-plus")
            self.assertEqual(node_models["node_worker"], "qwen3.7-plus")
            self.assertEqual(node_models["node_synth"], "kimi-k2.6")

def _graph_for_task(template_id: str, *, task_id: str) -> dict:
    graph = load_task_graph_fixture(template_id)
    graph["task_id"] = task_id
    return graph


def _run_for_task(template_id: str, *, task_id: str, graph_id: str) -> dict:
    run = load_task_graph_run_fixture(template_id)
    run["task_id"] = task_id
    run["graph_id"] = graph_id
    for event in list(run.get("event_refs") or []):
        if isinstance(event, dict):
            event["task_id"] = task_id
            event["run_id"] = run["run_id"]
    for artifact in list(run.get("artifact_refs") or []):
        if isinstance(artifact, dict):
            artifact["task_id"] = task_id
            artifact["run_id"] = run["run_id"]
    return run


if __name__ == "__main__":
    unittest.main()
