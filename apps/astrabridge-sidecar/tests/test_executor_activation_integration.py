from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.task_service import TaskService


class ExecutorActivationIntegrationTests(unittest.TestCase):
    def test_task_service_dry_run_writes_committed_executor_activation_artifacts(self) -> None:
        original_appdata = os.environ.get("ASTRABRIDGE_APPDATA")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                os.environ["ASTRABRIDGE_APPDATA"] = str(root / "AppData")
                workspace = root / "workspace"
                workspace.mkdir()
                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Executor activation", root / "executor-activation.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Executor activation task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]

                dry_run = tasks.dry_run_graph({"graph_id": graph["graph_id"]})["dry_run"]

                self.assertEqual(dry_run["run_status"], "dry_run_passed")
                current_path = workspace / ".astrabridge" / "executor-activation" / "current.json"
                self.assertTrue(current_path.is_file())
                current = json.loads(current_path.read_text(encoding="utf-8"))
                self.assertIn("task_graph_dry_run", str(current.get("activation_scope") or ""))
                self.assertTrue(Path(str(current.get("report_path") or "")).is_file())
                self.assertTrue(Path(str(current.get("journal_path") or "")).is_file())

                journal = json.loads(Path(str(current["journal_path"])).read_text(encoding="utf-8"))
                self.assertEqual(journal["status"], "committed")
                self.assertEqual(journal["tracks"][0]["track_id"], "node_executor_activation")
        finally:
            if original_appdata is None:
                os.environ.pop("ASTRABRIDGE_APPDATA", None)
            else:
                os.environ["ASTRABRIDGE_APPDATA"] = original_appdata

    def test_task_service_live_validation_stale_registry_preserves_previous_executor_pointer(self) -> None:
        original_appdata = os.environ.get("ASTRABRIDGE_APPDATA")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                os.environ["ASTRABRIDGE_APPDATA"] = str(root / "AppData")
                workspace = root / "workspace"
                workspace.mkdir()
                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Executor activation stale", root / "executor-activation-stale.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Executor activation stale task")
                graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]

                tasks.dry_run_graph({"graph_id": graph["graph_id"]})
                current_path = workspace / ".astrabridge" / "executor-activation" / "current.json"
                baseline_current = json.loads(current_path.read_text(encoding="utf-8"))

                for node in graph["nodes"]:
                    ui_hints = dict(node.get("ui_hints") or {})
                    ui_hints["node_type_registry_fingerprint"] = "stale-registry"
                    node["ui_hints"] = ui_hints
                tasks.save_graph_definition({"graph": graph})

                dry_run = tasks.dry_run_graph({"graph_id": graph["graph_id"], "validation_mode": "live"})["dry_run"]

                self.assertEqual(dry_run["overall_status"], "blocked")
                self.assertIn("stale registry fingerprint", " ".join(dry_run["graph_result"]["reasons"]).lower())
                current_after = json.loads(current_path.read_text(encoding="utf-8"))
                self.assertEqual(current_after["activation_id"], baseline_current["activation_id"])
                self.assertEqual(current_after["report_path"], baseline_current["report_path"])

                activation_root = workspace / ".astrabridge" / "executor-activation"
                rolled_back_journals = []
                for journal_path in activation_root.glob("*/apply-journal.json"):
                    payload = json.loads(journal_path.read_text(encoding="utf-8"))
                    if str(payload.get("status") or "") == "rolled_back":
                        rolled_back_journals.append(payload)
                self.assertTrue(rolled_back_journals)
                self.assertTrue(any(track["track_id"] == "node_executor_activation" for payload in rolled_back_journals for track in payload["tracks"]))
        finally:
            if original_appdata is None:
                os.environ.pop("ASTRABRIDGE_APPDATA", None)
            else:
                os.environ["ASTRABRIDGE_APPDATA"] = original_appdata


if __name__ == "__main__":
    unittest.main()
