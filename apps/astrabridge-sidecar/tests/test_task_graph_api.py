from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from copy import deepcopy
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_checks import diff_agent_orchestration_graphs
from astrabridge_sidecar.agent_orchestration_file_format import load_agent_orchestration_example
from astrabridge_sidecar.langgraph_stategraph_adapter import LangGraphStateGraphLossError
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.server import Handler
from astrabridge_sidecar.task_service import GRAPH_DEFINITION_LIMIT, GraphRevisionConflictError, GraphSourceOwnershipError, TaskService


REPO_ROOT = Path(__file__).resolve().parents[3]
COMFYUI_EXAMPLE_ROOT = Path(__file__).resolve().parents[3] / "examples" / "comfyui-workflow"
LANGGRAPH_EXAMPLE_ROOT = Path(__file__).resolve().parents[3] / "examples" / "langgraph-stategraph"
TYPESCRIPT_CUSTOM_BLANK_FIXTURE_PATH = (
    REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "features" / "runtime" / "fixtures" / "customBlankGraph.fromTs.json"
)


def _load_comfyui_example_text(name: str) -> str:
    return (COMFYUI_EXAMPLE_ROOT / name).read_text(encoding="utf-8")


def _load_langgraph_example_text(name: str) -> str:
    return (LANGGRAPH_EXAMPLE_ROOT / name).read_text(encoding="utf-8")


def _expected_revision_payload(graph: dict[str, Any]) -> dict[str, Any]:
    revision = dict(graph.get("graph_revision") or {})
    return {"expected_revision": str(revision.get("revision_id") or "").strip()}


class TaskGraphApiTests(unittest.TestCase):
    def test_task_service_routes_graph_mutation_entrypoints_through_shared_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            with patch.dict(os.environ, {"ASTRABRIDGE_RUNTIME_ROOT": str(root / "runtime-root")}):
                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Delegation", root / "delegation.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Delegation task")

                with patch.object(tasks._graph_mutation, "export_graph_for_orchestration_file", return_value={"kind": "export"}) as export_mock, \
                    patch.object(tasks._graph_mutation, "save_graph_definition", return_value={"kind": "save"}) as save_mock, \
                    patch.object(tasks._graph_mutation, "import_graph_from_orchestration_file", return_value={"kind": "import"}) as import_mock, \
                    patch.object(tasks._graph_mutation, "update_graph_node", return_value={"kind": "node"}) as node_mock, \
                    patch.object(tasks._graph_mutation, "update_graph_edge", return_value={"kind": "edge"}) as edge_mock:
                    self.assertEqual(tasks.export_graph_for_orchestration_file({"graph_id": "graph-1"})["kind"], "export")
                    self.assertEqual(tasks.save_graph_definition({"graph": {"graph_id": "graph-1"}})["kind"], "save")
                    self.assertEqual(tasks.import_graph_from_orchestration_file({"graph_text": "{}"})["kind"], "import")
                    self.assertEqual(tasks.update_graph_node({"graph_id": "graph-1", "node_id": "node-1"})["kind"], "node")
                    self.assertEqual(tasks.update_graph_edge({"graph_id": "graph-1", "edge_id": "edge-1"})["kind"], "edge")

                export_mock.assert_called_once()
                save_mock.assert_called_once()
                import_mock.assert_called_once()
                node_mock.assert_called_once()
                edge_mock.assert_called_once()

    def test_orchestration_sync_promotes_reachable_drafts_and_prunes_disconnected_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Reachable Sync", root / "reachable-sync.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Reachable sync task")
            instantiated = tasks.instantiate_graph_template("supervisor_worker_synthesizer")
            graph_id = instantiated["graph"]["graph_id"]

            node_update = tasks.update_graph_node(
                {
                    "graph_id": graph_id,
                    "node_id": "node_auditor",
                    **_expected_revision_payload(instantiated["graph"]),
                    "create": {
                        "kind": "artifact_source",
                        "label": "API Auditor",
                        "position": {"x": 420, "y": 260},
                    },
                }
            )
            self.assertNotIn(
                "node_auditor",
                [item["node_id"] for item in node_update["graph"]["orchestration_graph"]["nodes"]],
            )

            context_policy = dict(node_update["graph"]["edges"][0]["context_policy"])
            edge_update = tasks.update_graph_edge(
                {
                    "graph_id": graph_id,
                    "edge_id": "edge_supervisor_auditor",
                    **_expected_revision_payload(node_update["graph"]),
                    "from_node_id": "node_supervisor",
                    "to_node_id": "node_auditor",
                    "edge_type": "control_dependency",
                    "context_policy": context_policy,
                    "status": "ready",
                }
            )
            connected_graph = edge_update["graph"]
            self.assertEqual(
                {item["node_id"] for item in connected_graph["orchestration_graph"]["nodes"]},
                {"node_supervisor", "node_worker", "node_synth", "node_auditor"},
            )
            self.assertIn(
                "edge_supervisor_auditor",
                [item["edge_id"] for item in connected_graph["orchestration_graph"]["edges"]],
            )

            without_edge = deepcopy(connected_graph)
            without_edge["edges"] = [
                item for item in without_edge["edges"] if item["edge_id"] != "edge_supervisor_auditor"
            ]
            saved = tasks.save_graph_definition({"graph": without_edge})["graph"]
            self.assertNotIn(
                "edge_supervisor_auditor",
                [item["edge_id"] for item in saved["orchestration_graph"]["edges"]],
            )
            self.assertNotIn(
                "node_auditor",
                [item["node_id"] for item in saved["orchestration_graph"]["nodes"]],
            )

    def test_export_import_reexport_round_trip_preserves_canonical_orchestration_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Canonical Round Trip", root / "canonical-roundtrip.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Canonical round-trip task")
            instantiated = tasks.instantiate_graph_template("custom_blank_graph", title="Round-trip import target")
            graph_id = instantiated["graph"]["graph_id"]

            source_graph = load_agent_orchestration_example("multimodal_capability_adapter")
            source_text = json.dumps(source_graph, ensure_ascii=False, indent=2) + "\n"
            imported = tasks.import_graph_from_orchestration_file(
                {"graph_text": source_text, **_expected_revision_payload(instantiated["graph"])}
            )
            imported_graph = imported["graph"]
            imported_graph_id = imported_graph["graph_id"]
            imported_orchestration = dict(imported["orchestration_graph"] or {})

            exported = tasks.export_graph_for_orchestration_file(
                {
                    "graph_id": imported_graph_id,
                    "export_path": "PRIVATE/agent-graph-dynamic-workflow/step3-roundtrip/exported-multimodal.json",
                }
            )
            reimported = tasks.import_graph_from_orchestration_file(
                {"graph_text": exported["serialized_text"], **_expected_revision_payload(imported_graph)}
            )
            reexported = tasks.export_graph_for_orchestration_file({"graph_id": reimported["graph"]["graph_id"]})
            diff_report = diff_agent_orchestration_graphs(imported_orchestration, reexported["orchestration_graph"])

            self.assertEqual(imported_graph["template_id"], "multimodal_capability_adapter")
            self.assertNotEqual(graph_id, imported_graph_id)
            self.assertEqual(exported["orchestration_graph"]["graph_id"], imported_orchestration["graph_id"])
            self.assertTrue((workspace / exported["export_path"]).exists())
            self.assertEqual(diff_report["status"], "no_change")
            self.assertEqual(diff_report["summary"]["change_count"], 0)
            self.assertEqual(reexported["orchestration_graph"]["nodes"][0]["ports"]["inputs"][1]["port_type"], "image")
            self.assertEqual(reexported["orchestration_graph"]["edges"][0]["handoff_contract"]["port_bindings"][1]["to_port_id"], "probe_image")

    def test_comfyui_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_comfyui_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("ComfyUI Round Trip", root / "comfyui-roundtrip.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("ComfyUI round-trip task")

            imported = tasks.import_graph_from_orchestration_file(
                {"graph_text": _load_comfyui_example_text("branched_multimodal_supported.json")}
            )
            exported = tasks.export_graph_for_orchestration_file(
                {"graph_id": imported["graph"]["graph_id"], "emit_generated_python": False}
            )
            reimported = tasks.import_graph_from_orchestration_file(
                {"graph_text": exported["serialized_text"], **_expected_revision_payload(imported["graph"])}
            )
            diff_report = diff_agent_orchestration_graphs(imported["orchestration_graph"], reimported["orchestration_graph"])

            first_node = imported["graph"]["nodes"][0]
            self.assertEqual(imported["source_format"], "comfyui_workflow")
            self.assertEqual(imported["loss_report"]["status"], "pass")
            self.assertEqual(first_node["ui_hints"]["node_type_config"]["artifact_uri"], "workspace://PRIVATE/comfyui/inputs/request.md")
            self.assertEqual(exported["source_format"], "comfyui_workflow")
            self.assertEqual(exported["export_format"], "comfyui_workflow")
            self.assertEqual(diff_report["status"], "no_change")
            self.assertEqual(diff_report["summary"]["change_count"], 0)

    def test_comfyui_import_reexports_updated_node_type_config_from_task_graph_ui_hints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("ComfyUI UI Edit", root / "comfyui-ui-edit.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("ComfyUI UI edit task")

            imported = tasks.import_graph_from_orchestration_file(
                {"graph_text": _load_comfyui_example_text("linear_supported.json")}
            )
            edited_graph = deepcopy(imported["graph"])
            tool_node = next(item for item in edited_graph["nodes"] if item["kind"] == "mcp_tool")
            tool_node.setdefault("ui_hints", {}).setdefault("node_type_config", {})["server"] = "workspace"
            tool_node["ui_hints"]["node_type_config"]["tool"] = "list_directory"

            saved = tasks.save_graph_definition({"graph": edited_graph})
            exported = tasks.export_graph_for_orchestration_file({"graph_id": saved["graph"]["graph_id"]})
            workflow = json.loads(exported["serialized_text"])
            exported_tool = next(item for item in workflow["nodes"] if item["type"] == "astrabridge/mcp_tool")

            self.assertEqual(exported["export_format"], "comfyui_workflow")
            self.assertEqual(exported_tool["properties"]["astrabridge"]["node_type_config"]["server"], "workspace")
            self.assertEqual(exported_tool["properties"]["astrabridge"]["node_type_config"]["tool"], "list_directory")
            self.assertEqual(exported_tool["widgets_values"][:2], ["workspace", "list_directory"])

    def test_langgraph_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_langgraph_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("LangGraph Round Trip", root / "langgraph-roundtrip.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("LangGraph round-trip task")

            imported = tasks.import_graph_from_orchestration_file(
                {"graph_text": _load_langgraph_example_text("conditional_subgraph_interrupt_supported.json")}
            )
            exported = tasks.export_graph_for_orchestration_file(
                {"graph_id": imported["graph"]["graph_id"], "emit_generated_python": False}
            )
            reimported = tasks.import_graph_from_orchestration_file(
                {"graph_text": exported["serialized_text"], **_expected_revision_payload(imported["graph"])}
            )
            diff_report = diff_agent_orchestration_graphs(imported["orchestration_graph"], reimported["orchestration_graph"])

            route_node = next(item for item in imported["graph"]["nodes"] if item["kind"] == "router_condition")
            self.assertEqual(imported["source_format"], "langgraph_stategraph_manifest")
            self.assertEqual(imported["loss_report"]["status"], "pass")
            self.assertEqual(route_node["ui_hints"]["node_type_config"]["condition"]["field"], "route")
            self.assertEqual(exported["source_format"], "langgraph_stategraph_manifest")
            self.assertEqual(exported["export_format"], "langgraph_stategraph_manifest")
            self.assertIsNone(exported["generated_python"])
            self.assertEqual(diff_report["status"], "no_change")
            self.assertEqual(diff_report["summary"]["change_count"], 0)

    def test_langgraph_import_reexports_updated_node_type_config_from_task_graph_ui_hints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("LangGraph UI Edit", root / "langgraph-ui-edit.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("LangGraph UI edit task")

            imported = tasks.import_graph_from_orchestration_file(
                {"graph_text": _load_langgraph_example_text("conditional_subgraph_interrupt_supported.json")}
            )
            edited_graph = deepcopy(imported["graph"])
            subgraph_node = next(item for item in edited_graph["nodes"] if item["kind"] == "subgraph")
            subgraph_node.setdefault("ui_hints", {}).setdefault("node_type_config", {})["graph_ref"] = "graph_review_subflow_v2"

            saved = tasks.save_graph_definition({"graph": edited_graph})
            exported = tasks.export_graph_for_orchestration_file(
                {"graph_id": saved["graph"]["graph_id"], "emit_generated_python": False}
            )
            manifest = json.loads(exported["serialized_text"])
            exported_subgraph = next(item for item in manifest["graph"]["nodes"] if item["type"] == "astrabridge/subgraph")

            self.assertEqual(exported["export_format"], "langgraph_stategraph_manifest")
            self.assertEqual(exported_subgraph["node_type_config"]["graph_ref"], "graph_review_subflow_v2")

    def test_langgraph_export_blocks_generated_python_for_runtime_bound_nodes_with_structured_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("LangGraph Blocked Export", root / "langgraph-blocked.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("LangGraph blocked export task")

            imported = tasks.import_graph_from_orchestration_file(
                {"graph_text": _load_langgraph_example_text("conditional_subgraph_interrupt_supported.json")}
            )

            with self.assertRaises(LangGraphStateGraphLossError) as ctx:
                tasks.export_graph_for_orchestration_file({"graph_id": imported["graph"]["graph_id"]})

            payload = dict(ctx.exception.public_payload)
            self.assertEqual(payload["source_format"], "langgraph_stategraph_manifest")
            self.assertEqual(payload["loss_report"]["status"], "blocked")
            issue_codes = {item["code"] for item in list(payload["loss_report"]["issues"] or [])}
            self.assertIn("generated_python_unsupported_node_type", issue_codes)
            self.assertIn("generated_python_unsupported_conditional_source", issue_codes)

    def test_langgraph_export_emits_executable_generated_python_for_supported_router_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("LangGraph Executable Export", root / "langgraph-executable.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("LangGraph executable export task")

            imported = tasks.import_graph_from_orchestration_file(
                {"graph_text": _load_langgraph_example_text("conditional_router_executable_supported.json")}
            )
            exported = tasks.export_graph_for_orchestration_file({"graph_id": imported["graph"]["graph_id"]})

            generated_python = str(exported["generated_python"] or "")
            self.assertEqual(exported["export_format"], "langgraph_stategraph_manifest")
            self.assertTrue(generated_python)
            self.assertIn("builder.add_conditional_edges", generated_python)
            self.assertNotIn("NotImplementedError", generated_python)
            compile(generated_python, "generated_langgraph.py", "exec")

    def test_http_task_graph_import_export_supports_langgraph_manifest_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("HTTP LangGraph", root / "http-langgraph.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("HTTP LangGraph task")

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks

            class TaskGraphHandler(Handler):
                pass

            TaskGraphHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), TaskGraphHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                imported = _post_json(
                    base_url + "/api/task-graphs/import",
                    {"graph_text": _load_langgraph_example_text("conditional_subgraph_interrupt_supported.json")},
                )
                exported = _post_json(
                    base_url + "/api/task-graphs/export",
                    {"graph_id": imported["graph"]["graph_id"], "emit_generated_python": False},
                )

                self.assertEqual(imported["source_format"], "langgraph_stategraph_manifest")
                self.assertEqual(exported["source_format"], "langgraph_stategraph_manifest")
                self.assertEqual(exported["export_format"], "langgraph_stategraph_manifest")
                self.assertIsNone(exported["generated_python"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_instantiating_a_new_graph_keeps_it_within_the_graph_definition_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph Limit", root / "graph-limit.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph limit task")

            created_graph_ids: list[str] = []
            for index in range(GRAPH_DEFINITION_LIMIT):
                instantiated = tasks.instantiate_graph_template("fanout_fanin_research", title=f"Fixture graph {index + 1}")
                created_graph_ids.append(instantiated["graph"]["graph_id"])

            newest = tasks.instantiate_graph_template("code_fix_test_review", title="Newest graph")
            newest_graph_id = newest["graph"]["graph_id"]
            current_task = tasks.current_task()

            self.assertIsNotNone(current_task)
            assert current_task is not None
            graph_definitions = list(current_task.get("graph_definitions") or [])
            self.assertEqual(len(graph_definitions), GRAPH_DEFINITION_LIMIT)
            self.assertEqual(graph_definitions[0]["graph_id"], newest_graph_id)
            self.assertIsNotNone(tasks.graph_definition(newest_graph_id))
            self.assertNotIn(created_graph_ids[0], [item["graph_id"] for item in graph_definitions])

    def test_graph_template_recommendations_follow_the_effective_model_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Template Catalog", root / "template-catalog.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Template catalog task")

            templates = tasks.list_graph_templates(
                configured_models=[
                    {
                        "id": "qwen/qwen3.7-plus",
                        "provider": "qwen",
                        "native_model": "qwen3.7-plus",
                        "apply_patch_tool_type": "freeform",
                        "tool_mode": "native",
                        "supports_mcp_tools": True,
                        "mcp_tool_call_policy": "verified",
                        "mcp_smoke_status": "pass_direct_tool_call",
                    },
                    {"id": "glm/glm-5.2", "provider": "glm", "native_model": "glm-5.2"},
                    {
                        "id": "deepseek/deepseek-v4-pro",
                        "provider": "deepseek",
                        "native_model": "deepseek-v4-pro",
                        "apply_patch_tool_type": "freeform",
                        "tool_mode": "native",
                        "supports_mcp_tools": True,
                        "mcp_tool_call_policy": "verified",
                        "mcp_smoke_status": "pass_direct_tool_call",
                    },
                ]
            )
            by_id = {item["template_id"]: item for item in templates["templates"]}

            self.assertEqual(
                by_id["provider_update_smoke_gate"]["recommended_model_ids"],
                ["qwen3.7-plus"],
            )
            self.assertEqual(
                by_id["code_fix_test_review"]["recommended_model_ids"][:2],
                ["qwen3.7-plus", "deepseek-v4-pro"],
            )

    def test_graph_template_recommendations_use_current_safe_defaults_without_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Template Safe Defaults", root / "template-safe-defaults.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Template safe defaults task")

            templates = tasks.list_graph_templates()
            by_id = {item["template_id"]: item for item in templates["templates"]}

            self.assertEqual(
                by_id["supervisor_worker_synthesizer"]["recommended_model_ids"],
                [],
            )
            self.assertEqual(
                by_id["provider_update_smoke_gate"]["recommended_model_ids"],
                [],
            )

    def test_dry_run_repairs_stale_template_defaults_against_current_configured_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph Repair", root / "graph-repair.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph repair task")

            instantiated = tasks.instantiate_graph_template("supervisor_worker_synthesizer")
            graph_id = instantiated["graph"]["graph_id"]
            stale_graph = tasks.graph_definition(graph_id)
            self.assertIsNotNone(stale_graph)
            assert stale_graph is not None
            stale_supervisor = next(item for item in stale_graph["nodes"] if item["node_id"] == "node_supervisor")
            self.assertEqual(stale_supervisor["model_id"], "qwen3-coder-plus")

            dry_run = tasks.dry_run_graph(
                {"graph_id": graph_id},
                profiles_snapshot={
                    "profiles": [
                        {"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3.7-plus"},
                        {"profile_id": "kimi-default", "provider_id": "kimi", "model": "kimi-k2.6"},
                    ]
                },
                configured_models=[
                    {
                        "id": "qwen/qwen3.7-plus",
                        "provider": "qwen",
                        "native_model": "qwen3.7-plus",
                        "apply_patch_tool_type": "freeform",
                        "tool_mode": "native",
                        "supports_mcp_tools": True,
                        "mcp_tool_call_policy": "verified",
                        "mcp_smoke_status": "pass_direct_tool_call",
                    }
                ],
            )

            refreshed_graph = tasks.graph_definition(graph_id)
            self.assertIsNotNone(refreshed_graph)
            assert refreshed_graph is not None
            repaired_supervisor = next(item for item in refreshed_graph["nodes"] if item["node_id"] == "node_supervisor")
            repaired_worker = next(item for item in refreshed_graph["nodes"] if item["node_id"] == "node_worker")
            self.assertEqual(repaired_supervisor["model_id"], "qwen3.7-plus")
            self.assertEqual(repaired_worker["model_id"], "qwen3.7-plus")
            self.assertEqual(dry_run["dry_run"]["overall_status"], "pass")
            self.assertEqual(dry_run["dry_run"]["run_status"], "dry_run_passed")
            self.assertFalse(dry_run["dry_run"]["graph_result"]["reasons"])

    def test_snapshot_diff_and_rollback_resolve_snapshot_artifacts_from_task_project_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace_a = root / "workspace-a"
            workspace_b = root / "workspace-b"
            workspace_a.mkdir()
            workspace_b.mkdir()
            (workspace_a / "PRIVATE").mkdir()
            (workspace_b / "PRIVATE").mkdir()
            (workspace_a / ".astrabridge").mkdir()
            (workspace_b / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            project_a = projects.create_project("Projection Target", root / "project-a.abproj", workspace_root=workspace_a)
            tasks = TaskService(projects)
            task = tasks.create_task("Projected graph task")
            instantiated = tasks.instantiate_graph_template("fanout_fanin_research", title="Fanout snapshot fixture")
            graph = instantiated["graph"]
            graph_id = graph["graph_id"]

            project_b = projects.create_project("Snapshot Source", root / "project-b.abproj", workspace_root=workspace_b)
            projects.open_project(project_a["project_file"])
            tasks = TaskService(projects)
            task = tasks.current_task()
            self.assertIsNotNone(task)
            assert task is not None

            old_graph = json.loads(json.dumps(graph))
            new_graph = json.loads(json.dumps(graph))
            new_graph["state_version"] = int(old_graph["state_version"]) + 1
            new_graph["updated_at"] = old_graph["updated_at"]
            target_node = next(item for item in new_graph["nodes"] if item["node_id"] == "node_research_b")
            target_node["provider_id"] = "qwen"
            target_node["model_id"] = "qwen3-coder-plus"

            old_orchestration = tasks._orchestration_graph_for_task_graph(old_graph)
            new_orchestration = tasks._orchestration_graph_for_task_graph(new_graph)
            snapshot_root = (
                workspace_b
                / ".astrabridge"
                / "task-graph"
                / "snapshots"
                / task["task_id"]
                / graph_id
            )
            old_snapshot_id = "snapshot-old"
            new_snapshot_id = "snapshot-new"
            old_snapshot_dir = snapshot_root / old_snapshot_id
            new_snapshot_dir = snapshot_root / new_snapshot_id
            old_snapshot_dir.mkdir(parents=True)
            new_snapshot_dir.mkdir(parents=True)
            (old_snapshot_dir / "task-graph.json").write_text(json.dumps(old_graph, ensure_ascii=False, indent=2), encoding="utf-8")
            (old_snapshot_dir / "orchestration-graph.json").write_text(json.dumps(old_orchestration, ensure_ascii=False, indent=2), encoding="utf-8")
            (new_snapshot_dir / "task-graph.json").write_text(json.dumps(new_graph, ensure_ascii=False, indent=2), encoding="utf-8")
            (new_snapshot_dir / "orchestration-graph.json").write_text(json.dumps(new_orchestration, ensure_ascii=False, indent=2), encoding="utf-8")

            task["project_id"] = project_b["project_id"]
            task["graph_snapshot_refs"] = [
                {
                    "snapshot_id": old_snapshot_id,
                    "task_id": task["task_id"],
                    "graph_id": graph_id,
                    "project_id": project_b["project_id"],
                    "label": "old snapshot",
                    "reason": "manual_snapshot",
                    "source_action": "unit_test",
                    "state_version": old_graph["state_version"],
                    "created_at": old_graph["created_at"],
                    "updated_at": old_graph["updated_at"],
                    "artifact_paths": {
                        "snapshot_dir": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{old_snapshot_id}",
                        "task_graph_json": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{old_snapshot_id}/task-graph.json",
                        "orchestration_graph_json": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{old_snapshot_id}/orchestration-graph.json",
                    },
                    "summary": {"node_count": 4, "edge_count": 4, "change_count": 0, "change_types": []},
                },
                {
                    "snapshot_id": new_snapshot_id,
                    "task_id": task["task_id"],
                    "graph_id": graph_id,
                    "project_id": project_b["project_id"],
                    "label": "new snapshot",
                    "reason": "manual_snapshot",
                    "source_action": "unit_test",
                    "state_version": new_graph["state_version"],
                    "created_at": new_graph["created_at"],
                    "updated_at": new_graph["updated_at"],
                    "artifact_paths": {
                        "snapshot_dir": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{new_snapshot_id}",
                        "task_graph_json": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{new_snapshot_id}/task-graph.json",
                        "orchestration_graph_json": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{new_snapshot_id}/orchestration-graph.json",
                    },
                    "summary": {"node_count": 4, "edge_count": 4, "change_count": 1, "change_types": ["node_routing_changed"]},
                },
            ]
            current_graph = json.loads(json.dumps(new_graph))
            tasks.upsert_graph_definition(current_graph)
            tasks._save_task(task)

            diff = tasks.diff_graph_snapshot(
                {
                    "snapshot_id": old_snapshot_id,
                    "compare_to_snapshot_id": new_snapshot_id,
                }
            )
            self.assertEqual(diff["diff_report"]["status"], "changed")
            self.assertIn("node_routing_changed", diff["diff_report"]["summary"]["change_types"])

            current_graph = tasks.graph_definition(graph_id)
            assert current_graph is not None
            rolled_back = tasks.rollback_graph_to_snapshot(
                {"snapshot_id": old_snapshot_id, **_expected_revision_payload(current_graph)}
            )
            rolled_back_node = next(item for item in rolled_back["graph"]["nodes"] if item["node_id"] == "node_research_b")
            self.assertEqual(rolled_back_node["provider_id"], "kimi")
            self.assertEqual(rolled_back_node["model_id"], "kimi-k2.6")

    def test_graph_save_promotes_canonical_graph_document_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Canonical Graph Document", root / "canonical-graph-document.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Canonical graph document task")

                instantiated = tasks.instantiate_graph_template("custom_blank_graph", title="Canonical doc target")
                graph = deepcopy(instantiated["graph"])
                graph["title"] = "Canonical doc target v2"

                saved = tasks.save_graph_definition({"graph": graph})["graph"]
                graph_document = dict(saved.get("graph_document") or {})
                graph_revision = dict(saved.get("graph_revision") or {})

                self.assertEqual(graph_document["schema_version"], "astrabridge-graph-document-v3")
                self.assertEqual(graph_document["compatibility_projection"]["writable_source"], "canonical_orchestration_graph")
                self.assertEqual(graph_revision["revision_index"], saved["state_version"])
                self.assertEqual(graph_revision["revision_id"], graph_document["current_revision"]["revision_id"])
                self.assertEqual(saved["orchestration_graph"]["title"], "Canonical doc target v2")
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_graph_document_compatibility_ranges_stay_stable_across_noop_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Compatibility Range Stability", root / "compatibility-range-stability.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Compatibility range stability task")

                instantiated = tasks.instantiate_graph_template("custom_blank_graph", title="Stable compatibility target")
                first_saved = tasks.save_graph_definition({"graph": deepcopy(instantiated["graph"])})["graph"]
                second_saved = tasks.save_graph_definition({"graph": deepcopy(first_saved)})["graph"]

                self.assertEqual(
                    second_saved["graph_document"]["migration"],
                    first_saved["graph_document"]["migration"],
                )
                self.assertEqual(
                    second_saved["graph_document"]["compatibility_projection"]["generated_at"],
                    first_saved["graph_document"]["compatibility_projection"]["generated_at"],
                )
                compatibility_ranges = dict(second_saved["graph_document"]["migration"]["compatibility_ranges"] or {})
                self.assertEqual(
                    compatibility_ranges["document_schema_versions"]["write"],
                    "astrabridge-graph-document-v3",
                )
                self.assertEqual(
                    compatibility_ranges["task_graph_consumers"]["write"],
                    "astrabridge-task-graph-v1",
                )
                self.assertEqual(
                    compatibility_ranges["orchestration_consumers"]["write"],
                    "astrabridge-agent-orchestration-graph-v1",
                )
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_imported_source_owned_graph_blocks_gui_mutations_until_detached(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Source-owned graph", root / "source-owned-graph.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Source-owned graph task")

                graph_path = workspace / ".astrabridge" / "sdk" / "custom_blank_graph.json"
                graph_path.parent.mkdir(parents=True, exist_ok=True)
                graph_path.write_text(
                    json.dumps(load_agent_orchestration_example("custom_blank_graph"), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

                imported = tasks.import_graph_from_orchestration_file(
                    {"graph_path": graph_path.relative_to(workspace).as_posix()}
                )["graph"]
                graph_id = imported["graph_id"]

                self.assertEqual(
                    imported["graph_document"]["compatibility_projection"]["writable_source"],
                    "source_owned_canonical_file",
                )
                self.assertEqual(
                    imported["graph_document"]["source_ownership"]["ownership_mode"],
                    "source_owned",
                )
                self.assertEqual(
                    imported["graph_document"]["source_ownership"]["source_file"]["path"],
                    ".astrabridge/sdk/custom_blank_graph.json",
                )

                with self.assertRaises(GraphSourceOwnershipError) as blocked:
                    tasks.update_graph_node(
                        {
                            "graph_id": graph_id,
                            "node_id": "node_start_here",
                            **_expected_revision_payload(imported),
                            "configuration": {"label": "Blocked GUI Edit"},
                        }
                    )
                self.assertEqual(blocked.exception.payload["error"], "graph_source_owned")
                self.assertEqual(blocked.exception.payload["action"], "update_graph_node")

                detached = tasks.save_graph_definition(
                    {"graph": deepcopy(imported), "source_owner_action": "detach"}
                )["graph"]
                self.assertEqual(
                    detached["graph_document"]["source_ownership"]["ownership_mode"],
                    "detached_gui_edit",
                )
                self.assertEqual(
                    detached["graph_document"]["compatibility_projection"]["writable_source"],
                    "detached_gui_graph",
                )

                updated = tasks.update_graph_node(
                    {
                        "graph_id": graph_id,
                        "node_id": "node_start_here",
                        **_expected_revision_payload(detached),
                        "configuration": {"label": "Detached GUI Edit"},
                    }
                )["graph"]
                self.assertEqual(
                    next(item for item in updated["nodes"] if item["node_id"] == "node_start_here")["label"],
                    "Detached GUI Edit",
                )
                self.assertEqual(
                    updated["graph_document"]["source_ownership"]["ownership_mode"],
                    "detached_gui_edit",
                )
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_typescript_sdk_fixture_survives_import_dry_run_fixture_run_export_reload_and_reimport(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("TS SDK round trip", root / "ts-sdk-roundtrip.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("TS SDK round-trip task")

                graph_path = workspace / ".astrabridge" / "sdk" / "custom_blank_graph.fromTs.json"
                graph_path.parent.mkdir(parents=True, exist_ok=True)
                graph_path.write_text(TYPESCRIPT_CUSTOM_BLANK_FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

                imported = tasks.import_graph_from_orchestration_file(
                    {"graph_path": graph_path.relative_to(workspace).as_posix()}
                )["graph"]
                graph_id = imported["graph_id"]
                opened = tasks.graph_definition(graph_id)

                self.assertIsNotNone(opened)
                self.assertEqual(imported["template_id"], "custom_blank_graph")
                self.assertEqual(imported["graph_document"]["compatibility_projection"]["writable_source"], "source_owned_canonical_file")
                self.assertEqual(
                    imported["graph_document"]["source_ownership"]["source_file"]["path"],
                    ".astrabridge/sdk/custom_blank_graph.fromTs.json",
                )
                self.assertEqual(
                    next(item for item in imported["nodes"] if item["node_id"] == "node_start_here")["label"],
                    "Start Here",
                )

                dry_run = tasks.dry_run_graph({"graph_id": graph_id})
                self.assertEqual(dry_run["dry_run"]["overall_status"], "pass")
                self.assertEqual(dry_run["dry_run"]["run_status"], "dry_run_passed")

                fixture_run = tasks.execute_fixture_graph({"graph_id": graph_id})["fixture_run"]
                self.assertEqual(fixture_run["run_status"], "completed")
                self.assertEqual(fixture_run["run_ref"]["status"], "completed")

                exported = tasks.export_graph_for_orchestration_file(
                    {
                        "graph_id": graph_id,
                        "export_path": "PRIVATE/sdk-roundtrip/exported-custom-blank.fromTs.json",
                    }
                )
                self.assertTrue((workspace / exported["export_path"]).exists())

                reloaded_tasks = TaskService(projects)
                reloaded_graph = reloaded_tasks.graph_definition(graph_id)
                self.assertIsNotNone(reloaded_graph)

                reexported = reloaded_tasks.export_graph_for_orchestration_file({"graph_id": graph_id})
                persisted_diff = diff_agent_orchestration_graphs(
                    exported["orchestration_graph"],
                    reexported["orchestration_graph"],
                )
                self.assertEqual(persisted_diff["status"], "no_change")

                reimported = reloaded_tasks.import_graph_from_orchestration_file(
                    {
                        "graph_text": reexported["serialized_text"],
                        **_expected_revision_payload(reloaded_graph),
                    }
                )
                final_export = reloaded_tasks.export_graph_for_orchestration_file(
                    {"graph_id": reimported["graph"]["graph_id"]}
                )
                round_trip_diff = diff_agent_orchestration_graphs(
                    reexported["orchestration_graph"],
                    final_export["orchestration_graph"],
                )

                self.assertEqual(round_trip_diff["status"], "no_change")
                self.assertEqual(round_trip_diff["summary"]["change_count"], 0)
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_update_graph_node_rejects_stale_expected_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Graph Revision Conflict", root / "graph-revision-conflict.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Graph revision conflict task")

                instantiated = tasks.instantiate_graph_template("supervisor_worker_synthesizer")
                graph = instantiated["graph"]
                graph_id = graph["graph_id"]
                stale_revision = _expected_revision_payload(graph)

                updated = tasks.update_graph_node(
                    {
                        "graph_id": graph_id,
                        "node_id": "node_worker",
                        **stale_revision,
                        "configuration": {"label": "Current worker label"},
                    }
                )["graph"]
                self.assertNotEqual(
                    updated["graph_revision"]["revision_id"],
                    stale_revision["expected_revision"],
                )

                with self.assertRaises(GraphRevisionConflictError) as exc:
                    tasks.update_graph_node(
                        {
                            "graph_id": graph_id,
                            "node_id": "node_worker",
                            **stale_revision,
                            "configuration": {"label": "Stale write should fail"},
                        }
                    )
                self.assertEqual(exc.exception.payload["error"], "graph_revision_conflict")
                self.assertEqual(exc.exception.payload["action"], "update_graph_node")
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_update_graph_node_preserves_non_conflicting_stale_layout_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Node merge preservation", root / "node-merge-preservation.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Node merge preservation task")

                instantiated = tasks.instantiate_graph_template("supervisor_worker_synthesizer")
                graph = instantiated["graph"]
                graph_id = graph["graph_id"]
                stale_revision = _expected_revision_payload(graph)

                current = tasks.update_graph_node(
                    {
                        "graph_id": graph_id,
                        "node_id": "node_worker",
                        **stale_revision,
                        "configuration": {"label": "Worker Current Label"},
                    }
                )["graph"]
                merged = tasks.update_graph_node(
                    {
                        "graph_id": graph_id,
                        "node_id": "node_worker",
                        **stale_revision,
                        "position": {"x": 777, "y": 222},
                    }
                )["graph"]
                merged_node = next(item for item in merged["nodes"] if item["node_id"] == "node_worker")

                self.assertEqual(current["graph_revision"]["revision_index"], 2)
                self.assertEqual(merged_node["label"], "Worker Current Label")
                self.assertEqual(merged_node["position"], {"x": 777, "y": 222})
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_save_graph_definition_preserves_non_conflicting_policy_and_edge_edits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Save merge preservation", root / "save-merge-preservation.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Save merge preservation task")

                instantiated = tasks.instantiate_graph_template("fanout_fanin_research")
                graph = instantiated["graph"]
                graph_id = graph["graph_id"]
                stale_revision = _expected_revision_payload(graph)

                edge_payload = {
                    "graph_id": graph_id,
                    "edge_id": "edge_plan_a",
                    **stale_revision,
                    "context_policy": {
                        **dict(next(item for item in graph["edges"] if item["edge_id"] == "edge_plan_a")["context_policy"]),
                        "history_mode": "last_n_messages",
                        "history_length": 3,
                    },
                }
                current = tasks.update_graph_edge(edge_payload)["graph"]

                stale_graph = deepcopy(graph)
                stale_graph["graph_policy"] = {
                    **dict(stale_graph.get("graph_policy") or {}),
                    "max_parallelism_hint": 2,
                }
                stale_target_node = next(item for item in stale_graph["nodes"] if item["node_id"] == "node_research_b")
                stale_target_node["position"] = {"x": 920, "y": 420}
                merged = tasks.save_graph_definition({"graph": stale_graph})["graph"]

                merged_edge = next(item for item in merged["edges"] if item["edge_id"] == "edge_plan_a")
                merged_node = next(item for item in merged["nodes"] if item["node_id"] == "node_research_b")

                self.assertEqual(current["graph_revision"]["revision_index"], 2)
                self.assertEqual(merged["graph_policy"]["max_parallelism_hint"], 2)
                self.assertEqual(merged_node["position"], {"x": 920, "y": 420})
                self.assertEqual(merged_edge["context_policy"]["history_mode"], "last_n_messages")
                self.assertEqual(merged_edge["context_policy"]["history_length"], 3)
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_overlapping_stale_node_edit_fails_with_base_current_incoming_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Conflict payload detail", root / "conflict-payload-detail.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Conflict payload detail task")

                instantiated = tasks.instantiate_graph_template("supervisor_worker_synthesizer")
                graph = instantiated["graph"]
                graph_id = graph["graph_id"]
                stale_revision = _expected_revision_payload(graph)

                tasks.update_graph_node(
                    {
                        "graph_id": graph_id,
                        "node_id": "node_worker",
                        **stale_revision,
                        "configuration": {"label": "Worker Current Label"},
                    }
                )
                with self.assertRaises(GraphRevisionConflictError) as exc:
                    tasks.update_graph_node(
                        {
                            "graph_id": graph_id,
                            "node_id": "node_worker",
                            **stale_revision,
                            "configuration": {"label": "Worker Incoming Label"},
                        }
                    )
                payload = exc.exception.payload
                self.assertEqual(payload["merge_status"], "overlap_rejected")
                self.assertEqual(payload["edits"]["base"]["revision"]["revision_id"], stale_revision["expected_revision"])
                self.assertIn("nodes.node_worker.label", payload["edits"]["current"]["changed_paths"])
                self.assertIn("nodes.node_worker.label", payload["edits"]["incoming"]["changed_paths"])
                self.assertEqual(payload["overlapping_edits"][0]["path"], "nodes.node_worker.label")
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_import_graph_from_orchestration_file_preserves_non_conflicting_stale_import_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Import merge preservation", root / "import-merge-preservation.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Import merge preservation task")

                instantiated = tasks.instantiate_graph_template("fanout_fanin_research")
                graph = instantiated["graph"]
                graph_id = graph["graph_id"]
                stale_revision = _expected_revision_payload(graph)

                exported = tasks.export_graph_for_orchestration_file({"graph_id": graph_id})
                orchestration = json.loads(exported["serialized_text"])
                imported_target = next(item for item in orchestration["nodes"] if item["node_id"] == "node_research_b")
                imported_target["routing"] = {
                    **dict(imported_target.get("routing") or {}),
                    "provider_id": "qwen",
                    "model_id": "qwen3-coder-plus",
                }

                current = tasks.update_graph_node(
                    {
                        "graph_id": graph_id,
                        "node_id": "node_supervisor",
                        **stale_revision,
                        "position": {"x": 999, "y": 111},
                    }
                )["graph"]
                merged = tasks.import_graph_from_orchestration_file(
                    {
                        "graph_text": json.dumps(orchestration, ensure_ascii=False, indent=2) + "\n",
                        **stale_revision,
                    }
                )["graph"]

                merged_supervisor = next(item for item in merged["nodes"] if item["node_id"] == "node_supervisor")
                merged_target = next(item for item in merged["orchestration_graph"]["nodes"] if item["node_id"] == "node_research_b")

                self.assertEqual(current["graph_revision"]["revision_index"], 2)
                self.assertEqual(merged_supervisor["position"], {"x": 999, "y": 111})
                self.assertEqual(merged_target["routing"]["provider_id"], "qwen")
                self.assertEqual(merged_target["routing"]["model_id"], "qwen3-coder-plus")
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_imported_file_live_dry_run_is_quarantined_until_reviewed_for_live_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Imported compatibility quarantine", root / "imported-compatibility.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Imported compatibility quarantine task")

                graph = load_agent_orchestration_example("custom_blank_graph")
                graph["migration"]["source_kind"] = "imported_file"
                node = graph["nodes"][0]
                node["routing"] = {
                    "selection_mode": "explicit",
                    "provider_id": "qwen",
                    "model_id": "qwen3-coder-plus",
                }
                node["safety"]["allow_provider_calls"] = True

                imported = tasks.import_graph_from_orchestration_file(
                    {"graph_text": json.dumps(graph, ensure_ascii=False, indent=2) + "\n"}
                )
                dry_run = tasks.dry_run_graph(
                    {"graph_id": imported["graph"]["graph_id"], "validation_mode": "live"},
                    profiles_snapshot={
                        "profiles": [
                            {"profile_id": "profile-qwen", "provider_id": "qwen", "model": "qwen3-coder-plus"}
                        ]
                    },
                    configured_models=[
                        {"id": "qwen/qwen3-coder-plus", "provider": "qwen", "native_model": "qwen3-coder-plus"}
                    ],
                )

                self.assertEqual(dry_run["dry_run"]["overall_status"], "blocked")
                self.assertEqual(dry_run["dry_run"]["compatibility_gate"]["source_kind"], "imported_file")
                self.assertFalse(dry_run["dry_run"]["compatibility_gate"]["reviewed_for_live_execution"])
                self.assertTrue(
                    any(
                        "reviewed_for_live_execution" in reason
                        for reason in list(dry_run["dry_run"]["graph_result"]["reasons"] or [])
                    )
                )
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_imported_file_review_override_does_not_bypass_disabled_unknown_node_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Imported unknown node blocker", root / "imported-unknown.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Imported unknown node blocker task")

                graph = load_agent_orchestration_example("custom_blank_graph")
                graph["migration"]["source_kind"] = "imported_file"
                graph["migration"]["compatibility"]["reviewed_for_live_execution"] = True
                graph["nodes"][0]["kind"] = "vendor_unknown/custom_tool"
                graph["nodes"][0]["routing"] = {
                    "selection_mode": "explicit",
                    "provider_id": "qwen",
                    "model_id": "qwen3-coder-plus",
                }
                graph["nodes"][0]["safety"]["allow_provider_calls"] = True

                imported = tasks.import_graph_from_orchestration_file(
                    {"graph_text": json.dumps(graph, ensure_ascii=False, indent=2) + "\n"}
                )
                dry_run = tasks.dry_run_graph(
                    {"graph_id": imported["graph"]["graph_id"], "validation_mode": "live"},
                    profiles_snapshot={
                        "profiles": [
                            {"profile_id": "profile-qwen", "provider_id": "qwen", "model": "qwen3-coder-plus"}
                        ]
                    },
                    configured_models=[
                        {"id": "qwen/qwen3-coder-plus", "provider": "qwen", "native_model": "qwen3-coder-plus"}
                    ],
                )

                self.assertEqual(dry_run["dry_run"]["overall_status"], "blocked")
                self.assertTrue(dry_run["dry_run"]["compatibility_gate"]["reviewed_for_live_execution"])
                blocked_node = next(
                    item for item in dry_run["dry_run"]["node_results"] if item["node_id"] == "node_start_here"
                )
                self.assertEqual(blocked_node["status"], "blocked")
                self.assertTrue(
                    any(
                        "disabled until its type mapping is reviewed" in reason
                        for reason in list(blocked_node["reasons"] or [])
                    )
                )
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_rollback_graph_to_snapshot_preserves_non_conflicting_stale_current_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                project = projects.create_project("Rollback merge preservation", root / "rollback-merge-preservation.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                task = tasks.create_task("Rollback merge preservation task")

                instantiated = tasks.instantiate_graph_template("fanout_fanin_research")
                graph = instantiated["graph"]
                graph_id = graph["graph_id"]
                stale_revision = _expected_revision_payload(graph)
                base_snapshot = tasks.create_graph_snapshot(
                    {"graph_id": graph_id, "label": "Base snapshot", "reason": "manual_snapshot"}
                )["snapshot"]

                snapshot_graph = deepcopy(graph)
                snapshot_node = next(item for item in snapshot_graph["nodes"] if item["node_id"] == "node_research_b")
                snapshot_node["provider_id"] = "qwen"
                snapshot_node["model_id"] = "qwen3-coder-plus"
                snapshot_graph["orchestration_graph"] = tasks._orchestration_graph_for_task_graph(snapshot_graph)
                snapshot_orchestration = dict(snapshot_graph["orchestration_graph"] or {})

                snapshot_id = "snapshot-routing-merge"
                snapshot_dir = (
                    workspace
                    / ".astrabridge"
                    / "task-graph"
                    / "snapshots"
                    / task["task_id"]
                    / graph_id
                    / snapshot_id
                )
                snapshot_dir.mkdir(parents=True)
                (snapshot_dir / "task-graph.json").write_text(json.dumps(snapshot_graph, ensure_ascii=False, indent=2), encoding="utf-8")
                (snapshot_dir / "orchestration-graph.json").write_text(json.dumps(snapshot_orchestration, ensure_ascii=False, indent=2), encoding="utf-8")

                task = tasks.current_task()
                assert task is not None
                task["graph_snapshot_refs"] = [
                    *list(task.get("graph_snapshot_refs") or []),
                    {
                        "snapshot_id": snapshot_id,
                        "task_id": task["task_id"],
                        "graph_id": graph_id,
                        "project_id": project["project_id"],
                        "label": "Routing snapshot",
                        "reason": "manual_snapshot",
                        "source_action": "unit_test",
                        "state_version": snapshot_graph["state_version"],
                        "created_at": snapshot_graph["created_at"],
                        "updated_at": snapshot_graph["updated_at"],
                        "based_on_snapshot_id": base_snapshot["snapshot_id"],
                        "artifact_paths": {
                            "snapshot_dir": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{snapshot_id}",
                            "task_graph_json": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{snapshot_id}/task-graph.json",
                            "orchestration_graph_json": f".astrabridge/task-graph/snapshots/{task['task_id']}/{graph_id}/{snapshot_id}/orchestration-graph.json",
                        },
                        "summary": {"node_count": 4, "edge_count": 4, "change_count": 1, "change_types": ["node_routing_changed"]},
                    },
                ]
                tasks._save_task(task)

                current = tasks.update_graph_node(
                    {
                        "graph_id": graph_id,
                        "node_id": "node_supervisor",
                        **stale_revision,
                        "position": {"x": 901, "y": 177},
                    }
                )["graph"]
                rolled_back = tasks.rollback_graph_to_snapshot(
                    {"snapshot_id": snapshot_id, **stale_revision}
                )["graph"]

                supervisor = next(item for item in rolled_back["nodes"] if item["node_id"] == "node_supervisor")
                target = next(item for item in rolled_back["nodes"] if item["node_id"] == "node_research_b")

                self.assertEqual(current["graph_revision"]["revision_index"], 2)
                self.assertEqual(supervisor["position"], {"x": 901, "y": 177})
                self.assertEqual(target["provider_id"], "qwen")
                self.assertEqual(target["model_id"], "qwen3-coder-plus")
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_legacy_graph_definition_is_migrated_to_graph_document_on_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Legacy Graph Migration", root / "legacy-graph-migration.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                task = tasks.create_task("Legacy graph migration task")
                graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
                legacy_graph = deepcopy(graph)
                legacy_graph.pop("graph_document", None)
                legacy_graph.pop("graph_revision", None)
                task = tasks.current_task() or task
                task["graph_definitions"] = [legacy_graph]
                tasks._save_task(task)

                reloaded = TaskService(projects)
                migrated = reloaded.graph_definition(graph["graph_id"])
                self.assertIsNotNone(migrated)
                assert migrated is not None
                self.assertEqual(migrated["graph_document"]["schema_version"], "astrabridge-graph-document-v3")
                self.assertEqual(migrated["graph_document"]["migration"]["upgraded_from"], "legacy_task_graph_definition")
                self.assertEqual(
                    migrated["graph_document"]["migration"]["compatibility_ranges"]["task_graph_consumers"]["write"],
                    "astrabridge-task-graph-v1",
                )
                self.assertEqual(
                    migrated["graph_document"]["migration"]["compatibility_ranges"]["orchestration_consumers"]["write"],
                    "astrabridge-agent-orchestration-graph-v1",
                )
                second_read = reloaded.graph_definition(graph["graph_id"])
                self.assertEqual(
                    second_read["graph_revision"]["revision_id"],
                    migrated["graph_revision"]["revision_id"],
                )
                self.assertEqual(
                    second_read["graph_document"]["migration"],
                    migrated["graph_document"]["migration"],
                )
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_snapshot_and_rollback_preview_surface_graph_document_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()

                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Snapshot document evidence", root / "snapshot-document-evidence.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Snapshot document evidence task")

                instantiated = tasks.instantiate_graph_template("fanout_fanin_research", title="Snapshot document evidence graph")
                graph = instantiated["graph"]
                graph_id = graph["graph_id"]

                first_snapshot = tasks.create_graph_snapshot(
                    {
                        "graph_id": graph_id,
                        "label": "Before provider route change",
                        "reason": "manual_snapshot",
                        "source_action": "unit_test",
                    }
                )["snapshot"]
                self.assertEqual(
                    first_snapshot["graph_document_evidence"]["document_schema_version"],
                    "astrabridge-graph-document-v3",
                )
                self.assertEqual(
                    first_snapshot["graph_document_evidence"]["compatibility_mode"],
                    "generated_compatibility_projection",
                )
                self.assertTrue(
                    (workspace / first_snapshot["artifact_paths"]["graph_document_json"]).exists()
                )

                modified_graph = deepcopy(graph)
                target_node = next(item for item in modified_graph["nodes"] if item["node_id"] == "node_research_b")
                target_node["provider_id"] = "qwen"
                target_node["model_id"] = "qwen3-coder-plus"
                saved = tasks.save_graph_definition({"graph": modified_graph})["graph"]

                diff = tasks.diff_graph_snapshot({"snapshot_id": first_snapshot["snapshot_id"]})
                self.assertEqual(diff["rollback_preview"]["comparison_mode"], "snapshot_to_current")
                self.assertEqual(
                    diff["rollback_preview"]["restored_document"]["migration_origin"],
                    first_snapshot["graph_document_evidence"]["migration_origin"],
                )
                self.assertEqual(
                    diff["rollback_preview"]["current_document"]["compatibility_mode"],
                    "generated_compatibility_projection",
                )

                rolled_back = tasks.rollback_graph_to_snapshot(
                    {
                        "snapshot_id": first_snapshot["snapshot_id"],
                        **_expected_revision_payload(saved),
                    }
                )
                rolled_back_node = next(item for item in rolled_back["graph"]["nodes"] if item["node_id"] == "node_research_b")
                self.assertEqual(rolled_back_node["provider_id"], "kimi")
                self.assertEqual(rolled_back_node["model_id"], "kimi-k2.6")
                self.assertEqual(
                    rolled_back["rollback_preview"]["restored_document"]["document_schema_version"],
                    "astrabridge-graph-document-v3",
                )
                self.assertEqual(
                    rolled_back["rollback_preview"]["restored_document"]["migration_origin"],
                    first_snapshot["graph_document_evidence"]["migration_origin"],
                )
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_http_api_lists_templates_instantiates_graph_and_updates_node_and_edge(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            example_graph_text = (
                Path(__file__).resolve().parents[3] / "examples" / "agent-orchestration" / "code_fix_review.json"
            ).read_text(encoding="utf-8")
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph API", root / "graph-api.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            base_task = tasks.create_task("Graph API task")

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks
            Context.resolve_runtime_profile = staticmethod(
                lambda profile_id: {
                    "profile_id": str(profile_id or "qwen-default"),
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                }
            )
            Context.get_profile_with_capabilities = Context.resolve_runtime_profile

            class FakeRuntime:
                def start_graph_worker(self, profile: dict, **payload: object) -> dict:
                    self.last_profile = dict(profile)
                    self.last_payload = dict(payload)
                    return tasks.record_graph_worker(
                        {
                            "graph_id": str(payload.get("graph_id") or ""),
                            "run_id": str(payload.get("run_id") or ""),
                            "node_id": str(payload.get("node_id") or ""),
                            "worker_thread_id": "thread-worker-http",
                            "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                            "spawn_mode": "subagent_worker",
                            "worker_origin": "codex_subagent",
                            "agent_role": "worker",
                            "agent_nickname": "Smoke worker",
                            "status": "ready",
                            "artifact_refs": list(payload.get("artifact_refs") or []),
                            "runtime_contract": {
                                "profile_id": str(profile.get("profile_id") or ""),
                                "provider_id": str(profile.get("provider_id") or ""),
                                "model": str(profile.get("model") or ""),
                                "reasoning_effort": str(profile.get("reasoning_effort") or ""),
                                "permission_mode": "auto",
                                "collaboration_mode": "default",
                                "execution_backend": "app_server",
                                "spawn_mode": "subagent_worker",
                                "timeout_ms": 180000,
                                "tool_policy": {
                                    "approval_mode": "ask",
                                    "allowed_tool_classes": ["read_file", "web"],
                                    "supports_mcp": False,
                                },
                                "subagent_policy": {
                                    "isolation_mode": "lane",
                                    "max_turns": 8,
                                    "allow_direct_teammate_messages": False,
                                    "share_worktree": False,
                                    "allow_nested_subagents": False,
                                },
                            },
                        }
                    )

                def execute_task_graph_run(self, payload: dict[str, object]) -> dict[str, object]:
                    graph_id = str(payload.get("graph_id") or "")
                    graph = tasks.graph_definition(graph_id)
                    assert graph is not None
                    dry_run = tasks.dry_run_graph({"graph_id": graph_id})["dry_run"]
                    live_ref = dict(dry_run.get("run_ref") or {})
                    live_ref["status"] = "completed"
                    live_ref["latest_event_type"] = "run_completed"
                    live_ref["node_status_counts"] = {"completed": max(1, len(list(graph.get("nodes") or [])))}
                    live_ref["node_outcome_counts"] = {"passed": max(1, len(list(graph.get("nodes") or [])))}
                    persisted = tasks.persist_graph_run_ref(live_ref)
                    return {
                        "schema_version": "astrabridge-task-graph-live-run-v1",
                        "live_run": {
                            "run_id": str(live_ref.get("run_id") or ""),
                            "run_status": "completed",
                            "run_ref": persisted["run_ref"],
                            "artifact_paths": {
                                "summary_json": "PRIVATE/task-graph/live-run/summary.json",
                                "report_md": "PRIVATE/task-graph/live-run/report.md",
                            },
                        },
                        "graph": graph,
                        "task": tasks.task_view(tasks.current_task(), compact_graph_runs=True),
                    }

            Context.runtime = FakeRuntime()

            class TaskGraphHandler(Handler):
                pass

            TaskGraphHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), TaskGraphHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                templates = _get_json(base_url + "/api/task-graphs/templates")
                instantiated = _post_json(
                    base_url + "/api/task-graphs/instantiate",
                    {"template_id": "provider_update_smoke_gate", "title": "Provider update graph"},
                )
                graph_id = instantiated["graph"]["graph_id"]
                fetched = _get_json(base_url + f"/api/task-graphs/graph?graph_id={graph_id}")
                updated = _post_json(
                    base_url + "/api/task-graphs/node/update",
                    {
                        "graph_id": graph_id,
                        "node_id": "node_smoke",
                        **_expected_revision_payload(fetched["graph"]),
                        "position": {"x": 444, "y": 222},
                        "configuration": {
                            "human_summary_template": "Summarize {{node_label}} for {{provider_id}} / {{model_id}}.",
                            "provider_id": "qwen",
                            "model_id": "qwen3-coder-plus",
                            "reasoning_effort": "high",
                            "ui_hints": {
                                "context_policy_preset": "artifact_first",
                                "memory_policy_preset": "ephemeral",
                            },
                            "approval_gate": {
                                "review_kind": "filesystem_write_gate",
                            },
                            "execution_policy": {
                                "spawn_mode": "isolated_lane",
                                "retry_policy": {"max_attempts": 2},
                                "timeout_ms": 180000,
                                "allow_provider_calls": True,
                                "allow_code_changes": True,
                                "allow_install": False,
                                "requires_human_approval": True,
                            },
                            "output_contract": {
                                "machine_result_schema": {"type": "object", "required": ["matrix", "blocked_cases"]},
                                "human_summary_required": True,
                                "artifact_outputs": ["validation_report", "smoke_matrix"],
                                "artifact_only": False,
                            },
                        },
                    },
                )
                dry_run = _post_json(
                    base_url + "/api/task-graphs/dry-run",
                    {
                        "graph_id": graph_id,
                    },
                )
                created_node = _post_json(
                    base_url + "/api/task-graphs/node/update",
                    {
                        "graph_id": graph_id,
                        "node_id": "node_custom",
                        **_expected_revision_payload(updated["graph"]),
                        "create": {
                            "kind": "artifact_source",
                            "label": "Custom Agent",
                            "position": {"x": 120, "y": 360},
                        },
                        "configuration": {
                            "ui_hints": {
                                "context_policy_preset": "task_digest",
                                "palette_role": "custom",
                            },
                        },
                    },
                )
                created_edge = _post_json(
                    base_url + "/api/task-graphs/edge/update",
                    {
                        "graph_id": graph_id,
                        **_expected_revision_payload(created_node["graph"]),
                        "from_node_id": "node_discover",
                        "to_node_id": "node_gate",
                        "edge_type": "control_dependency",
                        "handoff_contract": {
                            "message_template": "Review the smoke bundle before promotion.",
                            "message_part_modes": ["machine_result", "artifact_ref"],
                            "required_output_schema_refs": ["schema.node_discover.machine_result"],
                        },
                        "context_policy": {
                            "policy_id": "policy_smoke_gate",
                            "history_mode": "explicit_refs_only",
                            "artifact_mode": "explicit_artifacts",
                            "exclude_private_memory": True,
                            "include_machine_results": True,
                            "include_human_summaries": False,
                            "summary_strategy": "machine_result_only",
                            "history_length": 0,
                            "included_artifacts": ["smoke_matrix", "blocked_cases"],
                            "resource_refs": ["PRIVATE/provider-smoke/summary.json"],
                        },
                    },
                )
                updated_edge = _post_json(
                    base_url + "/api/task-graphs/edge/update",
                    {
                        "graph_id": graph_id,
                        "edge_id": "edge_smoke_gate",
                        **_expected_revision_payload(created_edge["graph"]),
                        "from_node_id": "node_smoke",
                        "to_node_id": "node_gate",
                        "edge_type": "approval_dependency",
                        "handoff_contract": {
                            "message_template": "Review the smoke matrix and blocked cases before promotion.",
                            "message_part_modes": ["machine_result", "human_summary", "artifact_ref"],
                            "required_output_schema_refs": ["schema.node_smoke.machine_result"],
                        },
                        "context_policy": {
                            "policy_id": "policy_edge_smoke_gate",
                            "history_mode": "latest_machine_result_only",
                            "artifact_mode": "explicit_artifacts",
                            "exclude_private_memory": True,
                            "include_machine_results": True,
                            "include_human_summaries": True,
                            "summary_strategy": "human_and_machine",
                            "history_length": 2,
                            "included_artifacts": ["smoke_matrix"],
                            "resource_refs": ["PRIVATE/provider-smoke/summary.json", "PRIVATE/provider-smoke/report.md"],
                        },
                    },
                )
                manual_snapshot = _post_json(
                    base_url + "/api/task-graphs/snapshot",
                    {
                        "graph_id": graph_id,
                        "label": "Manual API snapshot",
                        "reason": "manual_snapshot",
                        "source_action": "api_test",
                    },
                )
                saved_graph = json.loads(json.dumps(updated_edge["graph"]))
                saved_graph_edge = next(item for item in saved_graph["edges"] if item["edge_id"] == "edge_discover_smoke")
                saved_graph_edge["handoff_contract"] = dict(saved_graph_edge.get("handoff_contract") or {})
                saved_graph_edge["handoff_contract"]["message_template"] = "Deliver the required output from node_discover to node_smoke. {{source_node_label}}"
                saved_graph_result = _post_json(
                    base_url + "/api/task-graphs/save",
                    {
                        "graph": saved_graph,
                    },
                )
                snapshot_diff = _post_json(
                    base_url + "/api/task-graphs/snapshot/diff",
                    {
                        "snapshot_id": manual_snapshot["snapshot"]["snapshot_id"],
                    },
                )
                rolled_back = _post_json(
                    base_url + "/api/task-graphs/rollback",
                    {
                        "snapshot_id": manual_snapshot["snapshot"]["snapshot_id"],
                        **_expected_revision_payload(saved_graph_result["graph"]),
                    },
                )
                exported = _post_json(
                    base_url + "/api/task-graphs/export",
                    {
                        "graph_id": graph_id,
                        "export_path": "PRIVATE/agent-orchestration/productization/step7-test/exported-provider-update.json",
                    },
                )
                imported = _post_json(
                    base_url + "/api/task-graphs/import",
                    {
                        "graph_text": example_graph_text,
                        **_expected_revision_payload(rolled_back["graph"]),
                    },
                )
                imported_exported = _post_json(
                    base_url + "/api/task-graphs/export",
                    {
                        "graph_id": imported["graph"]["graph_id"],
                        "export_path": "PRIVATE/agent-orchestration/productization/step7-test/exported-code-fix-review.json",
                    },
                )
                started_worker = _post_json(
                    base_url + "/api/task-graphs/worker/start",
                    {
                        "profile_id": "qwen-default",
                        "graph_id": graph_id,
                        "run_id": dry_run["dry_run"]["run_id"],
                        "node_id": "node_smoke",
                        "parent_thread_id": "thread-parent-http",
                        "artifact_refs": [
                            {
                                "artifact_id": "artifact-smoke-summary",
                                "artifact_kind": "validation_report",
                                "path": "PRIVATE/task-graph/dry-run/example/report.md",
                                "status": "ready",
                                "reasoning_content": "must not persist",
                            }
                        ],
                    },
                )
                worker_output = _post_json(
                    base_url + "/api/task-graphs/worker/output",
                    {
                        "graph_id": graph_id,
                        "run_id": dry_run["dry_run"]["run_id"],
                        "node_id": "node_smoke",
                        "worker_thread_id": "thread-worker-http",
                        "human_summary": "Smoke worker produced a gate-ready summary.",
                        "machine_result": {
                            "matrix": ["qwen", "kimi"],
                            "blocked_cases": [],
                            "history_transcript": "should not become downstream history",
                        },
                        "next_action_hints": ["Review the output bundle before the gate node."],
                    },
                )
                current = _get_json(base_url + f"/api/task-graphs/current?graph_id={graph_id}")
                fanout_graph = _post_json(
                    base_url + "/api/task-graphs/instantiate",
                    {"template_id": "fanout_fanin_research", "title": "Fanout fixture graph"},
                )
                fixture_run = _post_json(
                    base_url + "/api/task-graphs/fixture-run",
                    {
                        "graph_id": fanout_graph["graph"]["graph_id"],
                        "branch_behaviors": {
                            "node_research_a": "completed",
                            "node_research_b": "blocked",
                        },
                    },
                )
                gate_graph = _post_json(
                    base_url + "/api/task-graphs/instantiate",
                    {"template_id": "provider_update_smoke_gate", "title": "Provider gate fixture graph"},
                )
                gate_pending = _post_json(
                    base_url + "/api/task-graphs/fixture-run",
                    {
                        "graph_id": gate_graph["graph"]["graph_id"],
                    },
                )
                gate_rejected = _post_json(
                    base_url + "/api/task-graphs/approval/resolve",
                    {
                        "run_id": gate_pending["fixture_run"]["run_id"],
                        "decision": "reject",
                        "notes": "Need a narrower provider scope.",
                    },
                )
                gate_second_pending = _post_json(
                    base_url + "/api/task-graphs/fixture-run",
                    {
                        "graph_id": gate_graph["graph"]["graph_id"],
                    },
                )
                gate_approved = _post_json(
                    base_url + "/api/task-graphs/approval/resolve",
                    {
                        "run_id": gate_second_pending["fixture_run"]["run_id"],
                        "decision": "approve",
                        "notes": "Promotion approved for the fixture.",
                    },
                )
                cancellable_running = _post_json(
                    base_url + "/api/task-graphs/fixture-run",
                    {
                        "graph_id": fanout_graph["graph"]["graph_id"],
                        "execution_mode": "cancellable",
                    },
                )
                cancellable_cancelled = _post_json(
                    base_url + "/api/task-graphs/run/cancel",
                    {
                        "run_id": cancellable_running["fixture_run"]["run_id"],
                        "notes": "Cancelled from the API test.",
                    },
                )
                resumed_run = _post_json(
                    base_url + "/api/task-graphs/run/recover",
                    {
                        "run_id": cancellable_running["fixture_run"]["run_id"],
                        "strategy": "resume_run",
                    },
                )
                failed_code_fix_graph = _post_json(
                    base_url + "/api/task-graphs/instantiate",
                    {"template_id": "code_fix_test_review", "title": "Failed code fix graph"},
                )
                failed_code_fix_run = _post_json(
                    base_url + "/api/task-graphs/fixture-run",
                    {
                        "graph_id": failed_code_fix_graph["graph"]["graph_id"],
                        "node_behaviors": {"node_plan_fix": "failed"},
                    },
                )
                retried_failed_run = _post_json(
                    base_url + "/api/task-graphs/run/recover",
                    {
                        "run_id": failed_code_fix_run["fixture_run"]["run_id"],
                        "strategy": "retry_failed_nodes",
                        "node_behaviors": {"node_plan_fix": "completed"},
                    },
                )
                linear_template_runs = []
                for template_id, title in (
                    ("supervisor_worker_synthesizer", "Supervisor fixture graph"),
                    ("code_fix_test_review", "Code fix fixture graph"),
                    ("document_extract_analyze_report", "Document fixture graph"),
                ):
                    linear_graph = _post_json(
                        base_url + "/api/task-graphs/instantiate",
                        {"template_id": template_id, "title": title},
                    )
                    linear_template_runs.append(
                        _post_json(
                            base_url + "/api/task-graphs/fixture-run",
                            {"graph_id": linear_graph["graph"]["graph_id"]},
                        )
                    )
                fanout_current = _get_json(
                    base_url + f"/api/task-graphs/current?graph_id={fanout_graph['graph']['graph_id']}"
                )
                gate_current = _get_json(
                    base_url + f"/api/task-graphs/current?graph_id={gate_graph['graph']['graph_id']}"
                )

                self.assertTrue(templates["templates"])
                template_ids = {item["template_id"] for item in templates["templates"]}
                self.assertIn("multimodal_capability_adapter", template_ids)
                self.assertIn("custom_blank_graph", template_ids)
                first = templates["templates"][0]
                self.assertIn("template_id", first)
                self.assertIn("preview_graph", first)
                self.assertIn("artifact_expectations", first)
                self.assertIn("validation_hints", first)
                self.assertIn("constraints", first)
                self.assertEqual(instantiated["graph"]["title"], "Provider update graph")
                self.assertEqual(instantiated["task"]["task_id"], base_task["task_id"])
                self.assertFalse(list((instantiated["task"] or {}).get("graph_run_refs") or []))
                self.assertEqual(fetched["graph"]["graph_id"], graph_id)
                self.assertEqual(updated["node"]["position"]["x"], 444)
                self.assertEqual(updated["node"]["position"]["y"], 222)
                self.assertEqual(updated["node"]["provider_id"], "qwen")
                self.assertEqual(updated["node"]["model_id"], "qwen3-coder-plus")
                self.assertEqual(
                    updated["node"]["human_summary_template"],
                    "Summarize {{node_label}} for {{provider_id}} / {{model_id}}.",
                )
                self.assertEqual(updated["node"]["ui_hints"]["memory_policy_preset"], "ephemeral")
                self.assertTrue(updated["node"]["execution_policy"]["allow_code_changes"])
                self.assertTrue(updated["node"]["execution_policy"]["requires_human_approval"])
                self.assertEqual(updated["node"]["approval_gate"]["review_kind"], "filesystem_write_gate")
                self.assertEqual(updated["node"]["output_contract"]["artifact_outputs"], ["validation_report", "smoke_matrix"])
                self.assertEqual(created_node["node"]["node_id"], "node_custom")
                self.assertEqual(created_node["node"]["kind"], "artifact_source")
                self.assertEqual(created_node["node"]["ui_hints"]["palette_role"], "custom")
                self.assertEqual(created_node["node"]["position"]["y"], 360)
                self.assertEqual(dry_run["dry_run"]["overall_status"], "warning")
                self.assertTrue((workspace / dry_run["dry_run"]["artifact_paths"]["summary_json"]).exists())
                self.assertTrue((workspace / dry_run["dry_run"]["artifact_paths"]["report_md"]).exists())
                self.assertEqual(dry_run["dry_run"]["run_status"], "dry_run_passed")
                self.assertGreaterEqual(dry_run["dry_run"]["status_counts"]["warning"], 1)
                self.assertIn("run_ref", dry_run["dry_run"])
                self.assertEqual(created_edge["edge"]["edge_type"], "control_dependency")
                self.assertEqual(created_edge["edge"]["handoff_contract"]["message_part_modes"], ["machine_result", "artifact_ref"])
                self.assertEqual(updated_edge["edge"]["context_policy"]["history_mode"], "latest_machine_result_only")
                self.assertEqual(updated_edge["edge"]["context_policy"]["history_length"], 2)
                self.assertEqual(updated_edge["edge"]["context_policy"]["included_artifacts"], ["smoke_matrix"])
                self.assertEqual(
                    updated_edge["edge"]["handoff_contract"]["message_template"],
                    "Review the smoke matrix and blocked cases before promotion.",
                )
                self.assertEqual(manual_snapshot["snapshot"]["label"], "Manual API snapshot")
                self.assertTrue(
                    (workspace / manual_snapshot["snapshot"]["artifact_paths"]["task_graph_json"]).exists()
                )
                self.assertTrue(
                    (workspace / manual_snapshot["snapshot"]["artifact_paths"]["orchestration_graph_json"]).exists()
                )
                self.assertEqual(snapshot_diff["snapshot"]["snapshot_id"], manual_snapshot["snapshot"]["snapshot_id"])
                self.assertEqual(snapshot_diff["diff_report"]["status"], "changed")
                self.assertIn("edge_handoff_changed", snapshot_diff["diff_report"]["summary"]["change_types"])
                self.assertIn("Rollback to", rolled_back["snapshot"]["label"])
                rolled_back_edge = next(item for item in rolled_back["graph"]["edges"] if item["edge_id"] == "edge_discover_smoke")
                self.assertNotEqual(
                    dict(rolled_back_edge.get("handoff_contract") or {}).get("message_template"),
                    "Deliver the required output from node_discover to node_smoke. {{source_node_label}}",
                )
                self.assertGreaterEqual(len(rolled_back["task"]["graph_snapshot_refs"]), 1)
                self.assertIn(
                    "Deliver the required output from node_discover to node_smoke.",
                    next(item for item in saved_graph_result["graph"]["edges"] if item["edge_id"] == "edge_discover_smoke")["handoff_contract"]["message_template"],
                )
                exported_path = workspace / exported["export_path"]
                self.assertTrue(exported_path.exists())
                exported_payload = json.loads(exported_path.read_text(encoding="utf-8"))
                self.assertEqual(exported["orchestration_graph"]["graph_id"], graph_id)
                self.assertEqual(exported_payload["graph_id"], graph_id)
                self.assertEqual(exported_payload["title"], "Provider update graph")
                self.assertEqual(exported_payload["nodes"][1]["label"], "Generate Smoke Matrix")
                self.assertEqual(
                    exported_payload["nodes"][1]["prompt"]["template"],
                    "Summarize {{node_label}} for {{provider_id}} / {{model_id}}.",
                )
                self.assertTrue(exported_payload["nodes"][1]["safety"]["allow_code_changes"])
                self.assertEqual(exported_payload["nodes"][1]["safety"]["approval_kind"], "filesystem_write_gate")
                exported_created_edge = next(item for item in exported_payload["edges"] if item["edge_id"] == created_edge["edge"]["edge_id"])
                self.assertEqual(exported_created_edge["edge_type"], "control_dependency")
                self.assertEqual(
                    exported_created_edge["handoff_contract"]["message_template"],
                    "Review the smoke bundle before promotion.",
                )
                self.assertEqual(
                    exported_created_edge["handoff_contract"]["message_part_modes"],
                    ["machine_result", "artifact_ref"],
                )
                exported_updated_edge = next(item for item in exported_payload["edges"] if item["edge_id"] == "edge_smoke_gate")
                self.assertEqual(
                    exported_updated_edge["handoff_contract"]["message_template"],
                    "Review the smoke matrix and blocked cases before promotion.",
                )
                self.assertEqual(
                    exported_updated_edge["handoff_contract"]["message_part_modes"],
                    ["machine_result", "human_summary", "artifact_ref"],
                )
                exported_saved_edge = next(item for item in exported_payload["edges"] if item["edge_id"] == "edge_discover_smoke")
                self.assertIn(
                    "Deliver the required output from node_discover to node_smoke.",
                    exported_saved_edge["handoff_contract"]["message_template"],
                )
                self.assertEqual(imported["graph"]["template_id"], "code_fix_test_review")
                self.assertIsNone(imported["import_path"])
                self.assertEqual(imported["orchestration_graph"]["title"], "Code Fix / Test / Review")
                imported_exported_path = workspace / imported_exported["export_path"]
                self.assertTrue(imported_exported_path.exists())
                imported_exported_payload = json.loads(imported_exported_path.read_text(encoding="utf-8"))
                self.assertEqual(imported_exported_payload["template_id"], "code_fix_test_review")
                self.assertEqual(len(imported_exported_payload["nodes"]), 4)
                self.assertEqual(len(imported_exported_payload["edges"]), 3)
                self.assertEqual(started_worker["worker_binding"]["worker_thread_id"], "thread-worker-http")
                self.assertEqual(started_worker["worker_binding"]["parent_thread_id"], "thread-parent-http")
                self.assertEqual(started_worker["worker_binding"]["runtime_contract"]["spawn_mode"], "subagent_worker")
                self.assertEqual(started_worker["worker_binding"]["runtime_contract"]["subagent_policy"]["isolation_mode"], "lane")
                self.assertEqual(started_worker["worker_binding"]["runtime_contract"]["tool_policy"]["approval_mode"], "ask")
                self.assertEqual(started_worker["run_ref"]["worker_count"], 1)
                self.assertNotIn("reasoning_content", started_worker["worker_binding"]["artifact_refs"][0])
                self.assertEqual(worker_output["worker_binding"]["status"], "completed")
                self.assertEqual(worker_output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["source"], "artifact_refs_and_context_policy")
                self.assertIn("machine_result", worker_output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["message_part_types"])
                self.assertTrue(
                    any(
                        item in worker_output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["message_part_types"]
                        for item in ["artifact_ref", "resource_ref", "human_summary"]
                    )
                )
                self.assertTrue(worker_output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["exclude_private_memory"])
                self.assertTrue(worker_output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["resource_refs"])
                self.assertTrue((workspace / worker_output["worker_binding"]["output_summary"]["output_envelope_path"]).exists())
                self.assertTrue((workspace / worker_output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["input_envelope_path"]).exists())
                self.assertNotIn("history_transcript", str(worker_output["worker_binding"]["downstream_handoffs"]))
                self.assertEqual(current["graph"]["graph_id"], graph_id)
                self.assertEqual(len(current["graph"]["edges"]), 3)
                self.assertGreaterEqual(current["task"]["graph_activity_summary"]["graph_count"], 2)
                self.assertEqual(current["task"]["graph_activity_summary"]["run_count"], 1)
                self.assertEqual(current["task"]["graph_run_refs"][0]["worker_count"], 1)
                self.assertEqual(current["task"]["graph_run_refs"][0]["worker_bindings"][0]["status"], "completed")
                self.assertEqual(fixture_run["fixture_run"]["run_status"], "partial")
                self.assertEqual(fixture_run["fixture_run"]["run_ref"]["status"], "partial")
                self.assertEqual(fixture_run["fixture_run"]["run_ref"]["worker_count"], 3)
                self.assertEqual(fixture_run["fixture_run"]["run_ref"]["node_outcome_counts"]["passed"], 2)
                self.assertEqual(fixture_run["fixture_run"]["run_ref"]["node_outcome_counts"]["blocked"], 1)
                self.assertEqual(fixture_run["fixture_run"]["run_ref"]["node_outcome_counts"]["partial"], 1)
                self.assertEqual(
                    fixture_run["fixture_run"]["run_ref"]["policy_snapshot"]["parallel_group_ids"],
                    ["group_0", "group_1", "group_2"],
                )
                self.assertTrue((workspace / fixture_run["fixture_run"]["artifact_paths"]["summary_json"]).exists())
                self.assertTrue((workspace / fixture_run["fixture_run"]["artifact_paths"]["report_md"]).exists())
                fanout_bindings = {
                    item["node_id"]: item for item in fixture_run["fixture_run"]["run_ref"]["worker_bindings"]
                }
                self.assertEqual(fanout_bindings["node_research_a"]["status"], "completed")
                self.assertEqual(fanout_bindings["node_research_b"]["status"], "blocked")
                self.assertEqual(fanout_bindings["node_merge"]["status"], "partial")
                merge_join_events = [
                    item
                    for item in list(fixture_run["fixture_run"]["run_ref"]["timeline_events"] or [])
                    if item["event_type"] == "node_progress" and item.get("node_id") == "node_merge"
                ]
                self.assertTrue(merge_join_events)
                self.assertEqual(merge_join_events[0]["parallel_group_id"], "group_2")
                self.assertEqual(
                    fanout_bindings["node_research_a"]["downstream_handoffs"][0]["downstream_input"]["source"],
                    "artifact_refs_and_context_policy",
                )
                self.assertEqual(fanout_bindings["node_research_b"]["downstream_handoffs"], [])
                self.assertGreaterEqual(fanout_current["task"]["graph_activity_summary"]["graph_count"], 3)
                self.assertGreaterEqual(fanout_current["task"]["graph_activity_summary"]["run_count"], 5)
                self.assertIn(
                    "partial",
                    [str(item.get("status") or "") for item in list(fanout_current["task"]["graph_run_refs"] or []) if isinstance(item, dict)],
                )
                self.assertEqual(gate_pending["fixture_run"]["run_status"], "paused_for_review")
                self.assertEqual(gate_pending["fixture_run"]["run_ref"]["approval_state"], "pending")
                self.assertEqual(gate_pending["fixture_run"]["run_ref"]["approval_details"]["review_kind"], "provider_call_gate")
                gate_pending_event = next(
                    item
                    for item in gate_pending["fixture_run"]["run_ref"]["timeline_events"]
                    if item["event_type"] == "approval_requested"
                )
                self.assertEqual(gate_pending_event["node_id"], "node_gate")
                self.assertEqual(gate_rejected["run_ref"]["status"], "failed")
                self.assertEqual(gate_rejected["run_ref"]["approval_state"], "rejected")
                self.assertEqual(gate_rejected["run_ref"]["approval_details"]["decision"], "reject")
                self.assertEqual(gate_approved["run_ref"]["status"], "completed")
                self.assertEqual(gate_approved["run_ref"]["approval_state"], "approved")
                self.assertEqual(gate_approved["run_ref"]["approval_details"]["decision"], "approve")
                self.assertEqual(cancellable_running["fixture_run"]["run_status"], "running")
                self.assertTrue(list(cancellable_running["task"]["graph_run_refs"] or []))
                self.assertNotIn("worker_bindings", cancellable_running["task"]["graph_run_refs"][0])
                self.assertNotIn("timeline_events", cancellable_running["task"]["graph_run_refs"][0])
                self.assertEqual(cancellable_cancelled["run_ref"]["status"], "cancelled")
                self.assertTrue(any(item["event_type"] == "run_cancelled" for item in cancellable_cancelled["run_ref"]["timeline_events"]))
                self.assertTrue(any(str(item["path"]).endswith("/report.md") for item in cancellable_cancelled["run_ref"]["diagnostic_refs"]))
                self.assertEqual(resumed_run["fixture_run"]["run_ref"]["status"], "completed")
                self.assertEqual(resumed_run["recovery"]["strategy"], "resume_run")
                self.assertTrue((workspace / resumed_run["recovery"]["artifact_paths"]["manifest_json"]).exists())
                self.assertEqual(failed_code_fix_run["fixture_run"]["run_ref"]["status"], "failed")
                self.assertEqual(retried_failed_run["fixture_run"]["run_ref"]["status"], "completed")
                self.assertEqual(retried_failed_run["recovery"]["strategy"], "retry_failed_nodes")
                self.assertEqual(
                    [item["fixture_run"]["run_status"] for item in linear_template_runs],
                    ["completed", "completed", "completed"],
                )
                self.assertEqual(
                    [item["fixture_run"]["run_ref"]["status"] for item in linear_template_runs],
                    ["completed", "completed", "completed"],
                )
                self.assertGreaterEqual(gate_current["task"]["graph_activity_summary"]["graph_count"], 3)
                self.assertGreaterEqual(gate_current["task"]["graph_activity_summary"]["run_count"], 5)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_http_task_graph_import_export_supports_comfyui_workflow_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("HTTP ComfyUI", root / "http-comfyui.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("HTTP ComfyUI task")

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks

            class TaskGraphHandler(Handler):
                pass

            TaskGraphHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), TaskGraphHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                imported = _post_json(
                    base_url + "/api/task-graphs/import",
                    {"graph_text": _load_comfyui_example_text("linear_supported.json")},
                )
                exported = _post_json(
                    base_url + "/api/task-graphs/export",
                    {"graph_id": imported["graph"]["graph_id"]},
                )

                self.assertEqual(imported["source_format"], "comfyui_workflow")
                self.assertEqual(exported["source_format"], "comfyui_workflow")
                self.assertEqual(exported["export_format"], "comfyui_workflow")
                self.assertIn('"type": "astrabridge/mcp_tool"', exported["serialized_text"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_http_api_exposes_live_task_graph_run_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph Live API", root / "graph-live-api.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph live API task")

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks
            Context.resolve_runtime_profile = staticmethod(lambda profile_id: {"profile_id": str(profile_id or "qwen-default"), "provider_id": "qwen", "model": "qwen3-coder-plus"})
            Context.get_profile_with_capabilities = Context.resolve_runtime_profile

            class FakeRuntime:
                def execute_task_graph_run(self, payload: dict[str, object]) -> dict[str, object]:
                    graph_id = str(payload.get("graph_id") or "")
                    graph = tasks.graph_definition(graph_id)
                    assert graph is not None
                    instantiated_ref = tasks.dry_run_graph({"graph_id": graph_id})["dry_run"]["run_ref"]
                    live_ref = dict(instantiated_ref or {})
                    live_ref["status"] = "completed"
                    live_ref["latest_event_type"] = "run_completed"
                    persisted = tasks.persist_graph_run_ref(live_ref)
                    return {
                        "schema_version": "astrabridge-task-graph-live-run-v1",
                        "live_run": {
                            "run_id": str(live_ref.get("run_id") or ""),
                            "run_status": "completed",
                            "run_ref": persisted["run_ref"],
                            "artifact_paths": {"summary_json": "PRIVATE/task-graph/live-run/summary.json"},
                        },
                        "graph": graph,
                        "task": tasks.task_view(tasks.current_task(), compact_graph_runs=True),
                    }

            Context.runtime = FakeRuntime()

            class TaskGraphHandler(Handler):
                pass

            TaskGraphHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), TaskGraphHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                graph = _post_json(
                    f"http://127.0.0.1:{server.server_address[1]}/api/task-graphs/instantiate",
                    {"template_id": "provider_update_smoke_gate", "title": "Live route graph"},
                )
                live_run = _post_json(
                    f"http://127.0.0.1:{server.server_address[1]}/api/task-graphs/run",
                    {"graph_id": graph["graph"]["graph_id"]},
                )
                self.assertEqual(live_run["live_run"]["run_status"], "completed")
                self.assertEqual(live_run["live_run"]["run_ref"]["status"], "completed")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_live_task_graph_run_endpoint_returns_structured_terminal_failure_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph http", root / "graph-http.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Graph http task",
                thread_id="thread-http",
                settings={"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3-coder-plus"},
            )

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks
            Context.resolve_runtime_profile = staticmethod(lambda profile_id: {"profile_id": str(profile_id or "qwen-default"), "provider_id": "qwen", "model": "qwen3-coder-plus"})
            Context.get_profile_with_capabilities = Context.resolve_runtime_profile

            class FakeRuntime:
                def execute_task_graph_run(self, payload: dict[str, object]) -> dict[str, object]:
                    exc = TimeoutError("Model runtime ended with an error.")
                    exc.public_payload = {  # type: ignore[attr-defined]
                        "live_run": {
                            "run_id": "graph-run-live-http-failed",
                            "run_status": "failed",
                            "run_ref": {
                                "run_id": "graph-run-live-http-failed",
                                "graph_id": str(payload.get("graph_id") or "graph-http"),
                                "task_id": str(task.get("task_id") or ""),
                                "status": "failed",
                                "created_at": "2026-07-15T06:26:21+09:00",
                                "updated_at": "2026-07-15T06:44:01+09:00",
                            },
                            "artifact_paths": {
                                "summary_json": "PRIVATE/task-graph/live-run/graph-run-live-http-failed/summary.json",
                            },
                        },
                        "graph": {"graph_id": str(payload.get("graph_id") or "graph-http")},
                        "task": tasks.task_view(tasks.current_task(), compact_graph_runs=True),
                    }
                    raise exc

            Context.runtime = FakeRuntime()

            class TaskGraphHandler(Handler):
                pass

            TaskGraphHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), TaskGraphHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                graph = _post_json(
                    f"http://127.0.0.1:{server.server_address[1]}/api/task-graphs/instantiate",
                    {"template_id": "provider_update_smoke_gate", "title": "Live route graph"},
                )
                live_run = _post_json(
                    f"http://127.0.0.1:{server.server_address[1]}/api/task-graphs/run",
                    {"graph_id": graph["graph"]["graph_id"]},
                )
                self.assertFalse(live_run["ok"])
                self.assertEqual(live_run["error"], "Model runtime ended with an error.")
                self.assertEqual(live_run["live_run"]["run_status"], "failed")
                self.assertEqual(live_run["live_run"]["run_ref"]["status"], "failed")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_live_task_graph_run_endpoint_fail_closes_pre_persistence_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph http", root / "graph-http.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Graph http task",
                thread_id="thread-http",
                settings={"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3-coder-plus"},
            )

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks
            Context.resolve_runtime_profile = staticmethod(lambda profile_id: {"profile_id": str(profile_id or "qwen-default"), "provider_id": "qwen", "model": "qwen3-coder-plus"})
            Context.get_profile_with_capabilities = Context.resolve_runtime_profile

            class FakeRuntime:
                def execute_task_graph_run(self, payload: dict[str, object]) -> dict[str, object]:
                    raise ValueError("pre-persistence task-graph failure")

            Context.runtime = FakeRuntime()

            class TaskGraphHandler(Handler):
                pass

            TaskGraphHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), TaskGraphHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                graph = _post_json(
                    f"http://127.0.0.1:{server.server_address[1]}/api/task-graphs/instantiate",
                    {"template_id": "provider_update_smoke_gate", "title": "Live route graph"},
                )
                live_run = _post_json(
                    f"http://127.0.0.1:{server.server_address[1]}/api/task-graphs/run",
                    {"graph_id": graph["graph"]["graph_id"]},
                )
                self.assertFalse(live_run["ok"])
                self.assertEqual(live_run["error"], "pre-persistence task-graph failure")
                self.assertEqual(live_run["graph"]["graph_id"], graph["graph"]["graph_id"])
                self.assertEqual(live_run["task"]["task_id"], task["task_id"])
                self.assertNotIn("live_run", live_run)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_live_cancel_and_recover_routes_prefer_runtime_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph http", root / "graph-http.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph http task")

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks

            class FakeRuntime:
                def __init__(self) -> None:
                    self.cancel_payload: dict[str, object] | None = None
                    self.recover_payload: dict[str, object] | None = None

                def cancel_task_graph_run(self, payload: dict[str, object]) -> dict[str, object]:
                    self.cancel_payload = dict(payload)
                    return {
                        "cancellation": {
                            "run_id": str(payload.get("run_id") or ""),
                            "status": "cancelled",
                            "requested_at": "2026-07-16T10:00:00+09:00",
                            "interrupt_results": [],
                        },
                        "route": "runtime-cancel",
                    }

                def recover_task_graph_run(self, payload: dict[str, object]) -> dict[str, object]:
                    self.recover_payload = dict(payload)
                    return {
                        "recovery": {
                            "run_id": str(payload.get("run_id") or ""),
                            "strategy": str(payload.get("strategy") or ""),
                            "status": "needs_review",
                            "safe_to_resume": False,
                        },
                        "route": "runtime-recover",
                    }

            runtime = FakeRuntime()
            Context.runtime = runtime

            class TaskGraphHandler(Handler):
                pass

            TaskGraphHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), TaskGraphHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                cancelled = _post_json(
                    base_url + "/api/task-graphs/run/cancel",
                    {"run_id": "graph-run-live-http", "notes": "Cancel from HTTP test"},
                )
                recovered = _post_json(
                    base_url + "/api/task-graphs/run/recover",
                    {"run_id": "graph-run-live-http", "strategy": "resume_run"},
                )
                self.assertEqual(cancelled["route"], "runtime-cancel")
                self.assertEqual(recovered["route"], "runtime-recover")
                self.assertEqual(runtime.cancel_payload, {"run_id": "graph-run-live-http", "notes": "Cancel from HTTP test"})
                self.assertEqual(runtime.recover_payload, {"run_id": "graph-run-live-http", "strategy": "resume_run"})
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_task_graph_get_route_returns_compact_task_graph_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph compact", root / "graph-compact.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph compact task")
            instantiated = tasks.instantiate_graph_template("provider_update_smoke_gate", title="Compact route graph")
            graph_id = instantiated["graph"]["graph_id"]
            dry_run = tasks.dry_run_graph({"graph_id": graph_id})

            class Context:
                admin_token = "unit-admin-token"

            Context.projects = projects
            Context.tasks = tasks

            class TaskGraphHandler(Handler):
                pass

            TaskGraphHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), TaskGraphHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                payload = _get_json(
                    f"http://127.0.0.1:{server.server_address[1]}/api/task-graphs/graph?graph_id={graph_id}"
                )
                task_payload = payload["task"]
                self.assertTrue(task_payload["graph_run_refs"])
                first_run = task_payload["graph_run_refs"][0]
                self.assertEqual(first_run["run_id"], dry_run["dry_run"]["run_ref"]["run_id"])
                self.assertNotIn("timeline_events", first_run)
                self.assertNotIn("worker_bindings", first_run)
                first_graph_ref = next(
                    item for item in task_payload["graph_definitions"] if item["graph_id"] == graph_id
                )
                self.assertNotIn("nodes", first_graph_ref)
                self.assertNotIn("edges", first_graph_ref)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


def _post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Admin-Token": "unit-admin-token",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
