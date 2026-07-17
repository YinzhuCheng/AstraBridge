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
        self.assertEqual(snapshot["kind_aliases"]["planner"], "agent_model")
        self.assertEqual(snapshot["kind_aliases"]["gate"], "human_approval")
        agent_model = next(item for item in snapshot["node_types"] if item["type_id"] == "agent_model")
        variants = list(dict(agent_model.get("ui_hints") or {}).get("palette_variants") or [])
        self.assertIn("supervisor", [str(dict(item).get("kind") or "") for item in variants if isinstance(item, dict)])
        self.assertIn("custom", [str(dict(item).get("kind") or "") for item in variants if isinstance(item, dict)])

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
