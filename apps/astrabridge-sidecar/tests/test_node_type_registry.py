from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from copy import deepcopy
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agent_orchestration_compiler import compile_agent_orchestration_graph  # noqa: E402
from astrabridge_sidecar.agent_orchestration_contract import (  # noqa: E402
    lower_agent_orchestration_graph_to_task_graph,
    validate_agent_orchestration_graph,
)
from astrabridge_sidecar.agent_orchestration_file_format import load_agent_orchestration_example  # noqa: E402
from astrabridge_sidecar.node_type_registry import (  # noqa: E402
    OPAQUE_DISABLED_NODE_TYPE_ID,
    build_node_type_registry,
    compiled_plan_executor_capability_report,
    journaled_compiled_plan_executor_capability_report,
    node_type_registry_snapshot,
)
from astrabridge_sidecar import node_type_registry as node_type_registry_module  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.server import Handler  # noqa: E402
from astrabridge_sidecar.task_service import TaskService  # noqa: E402


class NodeTypeRegistryTests(unittest.TestCase):
    def test_registry_snapshot_contains_initial_public_types_and_aliases(self) -> None:
        snapshot = node_type_registry_snapshot()
        type_ids = [item["type_id"] for item in snapshot["node_types"]]

        self.assertEqual(snapshot["schema_version"], "astrabridge-node-type-registry-v1")
        self.assertIn("agent_model", type_ids)
        self.assertIn("mcp_tool", type_ids)
        self.assertIn("mcp_resource", type_ids)
        self.assertIn("transform", type_ids)
        self.assertIn("router_condition", type_ids)
        self.assertIn("loop", type_ids)
        self.assertIn("subgraph", type_ids)
        self.assertIn("human_approval", type_ids)
        self.assertIn("artifact_source", type_ids)
        self.assertIn("artifact_sink", type_ids)
        self.assertTrue(str(snapshot.get("executor_registry_fingerprint") or "").strip())
        self.assertEqual(
            str(dict(snapshot.get("executor_matrix") or {}).get("schema_version") or ""),
            "astrabridge-executor-registry-v1",
        )
        self.assertEqual(snapshot["kind_aliases"]["planner"], "agent_model")
        self.assertEqual(snapshot["kind_aliases"]["gate"], "human_approval")
        agent_model = next(item for item in snapshot["node_types"] if item["type_id"] == "agent_model")
        self.assertEqual(
            dict(agent_model.get("executor_capability") or {}).get("availability_summary"),
            "live_and_fixture",
        )
        variants = list(dict(agent_model.get("ui_hints") or {}).get("palette_variants") or [])
        self.assertIn("supervisor", [str(dict(item).get("kind") or "") for item in variants if isinstance(item, dict)])
        self.assertIn("custom", [str(dict(item).get("kind") or "") for item in variants if isinstance(item, dict)])
        mcp_tool = next(item for item in snapshot["node_types"] if item["type_id"] == "mcp_tool")
        self.assertEqual(
            dict(mcp_tool.get("executor_capability") or {}).get("availability_summary"),
            "live_and_fixture",
        )
        human_approval = next(item for item in snapshot["node_types"] if item["type_id"] == "human_approval")
        self.assertEqual(
            dict(human_approval.get("executor_capability") or {}).get("availability_summary"),
            "live_and_fixture",
        )
        loop = next(item for item in snapshot["node_types"] if item["type_id"] == "loop")
        self.assertEqual(
            dict(loop.get("executor_capability") or {}).get("availability_summary"),
            "live_and_fixture",
        )
        subgraph = next(item for item in snapshot["node_types"] if item["type_id"] == "subgraph")
        self.assertEqual(
            dict(subgraph.get("executor_capability") or {}).get("availability_summary"),
            "live_and_fixture",
        )

    def test_duplicate_or_conflicting_registration_fails(self) -> None:
        duplicate = deepcopy(node_type_registry_snapshot()["node_types"][0])

        with self.assertRaises(ValueError) as exc:
            build_node_type_registry(extra_specs=[duplicate])

        self.assertIn("Duplicate or conflicting node type registration", str(exc.exception))

    def test_registry_fingerprint_ignores_ui_hints(self) -> None:
        original = build_node_type_registry()
        base_specs = list(node_type_registry_module._base_node_type_specs())  # noqa: SLF001
        mutated_specs = deepcopy(base_specs)
        mutated_specs[0]["ui_hints"]["icon"] = "rocket"
        mutated_specs[0]["ui_hints"]["tone"] = "planner"

        with patch.object(node_type_registry_module, "_base_node_type_specs", return_value=tuple(mutated_specs)):
            mutated = build_node_type_registry()

        self.assertEqual(original["registry_fingerprint"], mutated["registry_fingerprint"])
        original_agent = next(item for item in original["node_types"] if item["type_id"] == "agent_model")
        mutated_agent = next(item for item in mutated["node_types"] if item["type_id"] == "agent_model")
        self.assertEqual(original_agent["registry_fingerprint"], mutated_agent["registry_fingerprint"])

    def test_fixture_node_type_added_to_registry_appears_in_snapshot_and_compiles(self) -> None:
        fixture_spec = {
            "type_id": "quality_gate",
            "version": 1,
            "category": "approval",
            "title": "Quality Gate",
            "description": "Fixture node type for Step 18 registry coverage.",
            "config_schema": {"type": "object", "properties": {"review_kind": {"type": "string"}}},
            "typed_ports": {
                "inputs": [{"port_id": "approval_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "approval_record", "port_type": "approval_record", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "quality_gate",
            "default_policy": {"execution_backend": "human_review", "spawn_mode": "manual_only", "approval_mode": "manual"},
            "ui_hints": {"palette_role": "gate", "palette_sections": ["control"], "icon": "lock", "tone": "gate"},
            "migration": {
                "legacy_kind_aliases": [],
                "compatible_roles": ["custom"],
                "default_role": "custom",
                "task_graph_projection_kind": "quality_gate",
            },
        }
        example = load_agent_orchestration_example("custom_blank_graph")
        example["nodes"][0]["kind"] = "quality_gate"
        example["nodes"][0]["role"] = "custom"

        base_specs = list(node_type_registry_module._base_node_type_specs())  # noqa: SLF001
        patched_specs = tuple([*deepcopy(base_specs), fixture_spec])
        with patch.object(node_type_registry_module, "_base_node_type_specs", return_value=patched_specs):
            snapshot = node_type_registry_snapshot()
            compiled = compile_agent_orchestration_graph(example)

        self.assertIn("quality_gate", [item["type_id"] for item in snapshot["node_types"]])
        compiled_node = compiled["nodes"][0]
        self.assertEqual(compiled_node["resolved_node_type_id"], "quality_gate")
        self.assertEqual(compiled_node["compiler_executor_id"], "quality_gate")
        self.assertTrue(compiled["node_type_registry_fingerprint"])

    def test_executor_capability_report_accepts_live_and_fixture_executor_after_step_13(self) -> None:
        graph = load_agent_orchestration_example("custom_blank_graph")
        graph["nodes"][0]["kind"] = "mcp_tool"
        graph["nodes"][0]["role"] = "custom"

        compiled = compile_agent_orchestration_graph(graph)
        live_report = compiled_plan_executor_capability_report(compiled, execution_mode="live_run")
        fixture_report = compiled_plan_executor_capability_report(compiled, execution_mode="fixture_run")

        self.assertTrue(live_report["ok"])
        self.assertTrue(fixture_report["ok"])

    def test_executor_capability_report_detects_registry_fingerprint_drift(self) -> None:
        graph = load_agent_orchestration_example("custom_blank_graph")
        compiled = compile_agent_orchestration_graph(graph)
        compiled["node_type_registry_fingerprint"] = "stale-registry"
        compiled["nodes"][0]["node_type_registry_fingerprint"] = "stale-registry"

        report = compiled_plan_executor_capability_report(compiled, execution_mode="fixture_run")

        self.assertFalse(report["ok"])
        self.assertIn("Registry fingerprint drift detected", " ".join(str(item) for item in report["blockers"]))

    def test_journaled_executor_activation_commits_and_updates_current_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / ".astrabridge").mkdir()
            graph = load_agent_orchestration_example("custom_blank_graph")
            compiled = compile_agent_orchestration_graph(graph)

            report = journaled_compiled_plan_executor_capability_report(
                compiled,
                execution_mode="fixture_run",
                workspace_root=workspace,
                activation_scope="unit-fixture-run",
            )

            journal_path = Path(report["activation"]["journal_path"])
            rollback_path = Path(report["activation"]["rollback_manifest_path"])
            current_path = Path(report["activation"]["current_pointer_path"])
            self.assertTrue(journal_path.is_file())
            self.assertTrue(rollback_path.is_file())
            self.assertTrue(current_path.is_file())

            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            self.assertEqual(journal["status"], "committed")
            self.assertEqual(journal["tracks"][0]["track_id"], "node_executor_activation")
            self.assertEqual(journal["tracks"][0]["health_verdict"], "pass")

            current = json.loads(current_path.read_text(encoding="utf-8"))
            self.assertEqual(current["activation_id"], report["activation"]["activation_id"])
            self.assertEqual(current["report_path"], report["activation"]["report_path"])

    def test_journaled_executor_activation_failure_preserves_previous_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / ".astrabridge").mkdir()
            graph = load_agent_orchestration_example("custom_blank_graph")
            success_compiled = compile_agent_orchestration_graph(graph)
            success_report = journaled_compiled_plan_executor_capability_report(
                success_compiled,
                execution_mode="fixture_run",
                workspace_root=workspace,
                activation_scope="baseline-fixture-run",
            )
            current_path = Path(success_report["activation"]["current_pointer_path"])
            baseline_current = json.loads(current_path.read_text(encoding="utf-8"))

            failed_compiled = compile_agent_orchestration_graph(graph)
            failed_compiled["node_type_registry_fingerprint"] = "stale-registry"
            failed_compiled["nodes"][0]["node_type_registry_fingerprint"] = "stale-registry"
            failed_report = journaled_compiled_plan_executor_capability_report(
                failed_compiled,
                execution_mode="fixture_run",
                workspace_root=workspace,
                activation_scope="blocked-fixture-run",
            )

            failed_journal = json.loads(Path(failed_report["activation"]["journal_path"]).read_text(encoding="utf-8"))
            failed_rollback = json.loads(Path(failed_report["activation"]["rollback_manifest_path"]).read_text(encoding="utf-8"))
            current_after = json.loads(current_path.read_text(encoding="utf-8"))

            self.assertFalse(failed_report["ok"])
            self.assertEqual(failed_journal["status"], "rolled_back")
            self.assertEqual(failed_journal["tracks"][0]["health_verdict"], "fail")
            self.assertEqual(failed_rollback["restore_status"], "restored_after_failure")
            self.assertEqual(current_after["activation_id"], baseline_current["activation_id"])
            self.assertEqual(current_after["report_path"], baseline_current["report_path"])

    def test_journaled_executor_activation_shortens_artifact_id_for_long_scope_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "nested-runtime-rollout" / "rollback-fixture-workspace" / "workspace"
            workspace.mkdir(parents=True)
            (workspace / ".astrabridge").mkdir()
            graph = load_agent_orchestration_example("custom_blank_graph")
            compiled = compile_agent_orchestration_graph(graph)

            report = journaled_compiled_plan_executor_capability_report(
                compiled,
                execution_mode="fixture_run",
                workspace_root=workspace,
                activation_scope="task_graph_fixture_run:graph-20260718T151136191070-d49a5c:rollback-readback-shadow-comparison",
            )

            activation = dict(report.get("activation") or {})
            activation_id = str(activation.get("activation_id") or "")
            rollback_path = Path(str(activation.get("rollback_manifest_path") or ""))

            self.assertTrue(activation_id)
            self.assertLessEqual(len(activation_id), 48)
            self.assertTrue(rollback_path.is_file())
            self.assertIn(".astrabridge\\executor-activation", str(rollback_path))

    def test_imported_unknown_node_type_becomes_opaque_disabled_with_diagnostics(self) -> None:
        graph = load_agent_orchestration_example("custom_blank_graph")
        graph["migration"]["source_kind"] = "imported_file"
        graph["nodes"][0]["kind"] = "vendor_magic"
        graph["nodes"][0]["role"] = "custom"

        validated = validate_agent_orchestration_graph(graph)
        lowered = lower_agent_orchestration_graph_to_task_graph(validated)

        node = validated["nodes"][0]
        lowered_node = lowered["nodes"][0]
        self.assertEqual(node["status"], "disabled")
        self.assertEqual(node["resolved_node_type_id"], OPAQUE_DISABLED_NODE_TYPE_ID)
        self.assertEqual(node["node_type_diagnostics"][0]["code"], "unknown_node_type")
        self.assertEqual(lowered_node["kind"], OPAQUE_DISABLED_NODE_TYPE_ID)
        self.assertEqual(lowered_node["status"], "disabled")
        self.assertEqual(lowered_node["ui_hints"]["original_node_type_kind"], "vendor_magic")

    def test_task_service_import_preserves_unknown_imported_node_kind_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Node type import", root / "node-type-import.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Node type import task")

            graph = load_agent_orchestration_example("custom_blank_graph")
            graph["migration"]["source_kind"] = "imported_file"
            graph["nodes"][0]["kind"] = "vendor_magic"
            graph["nodes"][0]["role"] = "custom"

            response = tasks.import_graph_from_orchestration_file({"graph_text": json.dumps(graph)})
            orchestration_graph = response["orchestration_graph"]
            lowered_graph = response["graph"]

            imported_node = orchestration_graph["nodes"][0]
            lowered_node = lowered_graph["nodes"][0]
            self.assertEqual(imported_node["kind"], "vendor_magic")
            self.assertEqual(imported_node["status"], "disabled")
            self.assertEqual(imported_node["node_type_diagnostics"][0]["code"], "unknown_node_type")
            self.assertEqual(lowered_node["kind"], OPAQUE_DISABLED_NODE_TYPE_ID)
            self.assertEqual(lowered_node["ui_hints"]["original_node_type_kind"], "vendor_magic")

    def test_node_type_registry_http_route_returns_public_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Node type route", root / "node-type-route.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Node type route task")

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks

            class RegistryHandler(Handler):
                pass

            RegistryHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), RegistryHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_address[1]}/api/task-graphs/node-types",
                    timeout=15,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["schema_version"], "astrabridge-node-type-registry-v1")
                self.assertIn("agent_model", [item["type_id"] for item in payload["node_types"]])
                self.assertNotIn(OPAQUE_DISABLED_NODE_TYPE_ID, [item["type_id"] for item in payload["node_types"]])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
