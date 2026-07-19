from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_checks import diff_agent_orchestration_graphs  # noqa: E402
from astrabridge_sidecar.agent_orchestration_file_format import load_agent_orchestration_example  # noqa: E402
from astrabridge_sidecar.agent_orchestration_sdk import (  # noqa: E402
    AgentOrchestrationGraphBuilder,
    ArtifactSpec,
    CapabilityClaimsSpec,
    ContextPolicySpec,
    EdgeSpec,
    ExecutionSpec,
    GraphMetadataSpec,
    GraphPolicySpec,
    HandoffContractSpec,
    InputContractSpec,
    NodeSpec,
    OutputContractSpec,
    PortBindingSpec,
    PortSpec,
    PositionSpec,
    PromptSpec,
    RoutingSpec,
    SafetySpec,
    SubagentPolicySpec,
    ToolsSpec,
    UiSpec,
)
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.task_service import TaskService  # noqa: E402


def _custom_blank_graph_builder(*, task_id: str = "task_example") -> AgentOrchestrationGraphBuilder:
    builder = AgentOrchestrationGraphBuilder(
        graph_id="graph_custom_blank_graph_v1",
        task_id=task_id,
        title="Custom Blank Graph",
        template_id="custom_blank_graph",
        metadata=GraphMetadataSpec(
            description="Custom Blank Graph",
            tags=["custom", "blank", "starter"],
        ),
        graph_policy=GraphPolicySpec(entry_node_ids=["node_start_here"]),
    )
    builder.register_schema(
        "schema.blank_entry",
        {
            "type": "object",
            "required": ["goal", "next_nodes"],
        },
    )
    builder.add_node(
        NodeSpec(
            node_id="node_start_here",
            kind="artifact_source",
            label="Start Here",
            role="custom",
            card_ref="agent_card_blank_entry",
            routing=RoutingSpec(selection_mode="none"),
            prompt=PromptSpec(template="Use this starter node as the seed for a custom graph."),
            tools=ToolsSpec(approval_mode="ask", allowed_tool_classes=[]),
            inputs=[
                PortSpec(
                    port_id="task_context",
                    label="Task Context",
                    port_type="text",
                    shape="single",
                    required=True,
                )
            ],
            outputs=[
                PortSpec(
                    port_id="machine_result",
                    label="Machine Result",
                    port_type="structured_json",
                    shape="single",
                    required=True,
                    schema_ref="schema.blank_entry",
                )
            ],
            input_contract=InputContractSpec(
                mode="task_context_and_typed_ports",
                port_ids=["task_context"],
            ),
            output_contract=OutputContractSpec(
                mode="structured_only",
                machine_result_schema_ref="schema.blank_entry",
                artifact_specs=[],
                human_summary_required=True,
            ),
            execution=ExecutionSpec(
                spawn_mode="inline_lane",
                timeout_ms=60000,
                execution_backend="app_server",
            ),
            safety=SafetySpec(
                risk_class="low",
                allow_provider_calls=False,
                allow_code_changes=False,
                allow_install=False,
                requires_human_approval=False,
            ),
            ui=UiSpec(position=PositionSpec(x=140, y=200), layout_mode="canvas"),
        )
    )
    return builder


def _two_node_compile_graph_builder(*, task_id: str = "task_example") -> AgentOrchestrationGraphBuilder:
    builder = AgentOrchestrationGraphBuilder(
        graph_id="graph_sdk_compile_v1",
        task_id=task_id,
        title="SDK Compile Graph",
        template_id="supervisor_worker_synthesizer",
        metadata=GraphMetadataSpec(
            description="SDK Compile Graph",
            tags=["sdk", "compile"],
        ),
        graph_policy=GraphPolicySpec(entry_node_ids=["node_plan"]),
    )
    builder.register_schema("schema.sdk_plan", {"type": "object", "required": ["goal", "steps"]})
    builder.register_schema("schema.sdk_result", {"type": "object", "required": ["status", "summary"]})
    builder.add_node(
        NodeSpec(
            node_id="node_plan",
            kind="supervisor",
            label="SDK Planner",
            role="planner",
            card_ref="agent_card_sdk_planner",
            routing=RoutingSpec(
                selection_mode="explicit",
                provider_id="qwen",
                model_id="qwen3-coder-plus",
                capability_claims=CapabilityClaimsSpec(
                    input_port_types=["text"],
                    output_port_types=["structured_json"],
                ),
            ),
            prompt=PromptSpec(template="Plan the bounded workflow before execution."),
            tools=ToolsSpec(approval_mode="ask", allowed_tool_classes=["read_file"]),
            inputs=[
                PortSpec("task_context", "Task Context", "text"),
            ],
            outputs=[
                PortSpec("machine_result", "Machine Result", "structured_json", schema_ref="schema.sdk_plan"),
            ],
            input_contract=InputContractSpec(
                mode="task_context_and_typed_ports",
                port_ids=["task_context"],
            ),
            output_contract=OutputContractSpec(
                mode="structured_only",
                machine_result_schema_ref="schema.sdk_plan",
            ),
            execution=ExecutionSpec(
                spawn_mode="inline_lane",
                timeout_ms=120000,
                execution_backend="app_server",
            ),
            safety=SafetySpec(
                risk_class="moderate",
                allow_provider_calls=True,
                allow_code_changes=False,
                allow_install=False,
                requires_human_approval=False,
            ),
            ui=UiSpec(position=PositionSpec(x=80, y=180)),
        )
    )
    builder.add_node(
        NodeSpec(
            node_id="node_finalize",
            kind="synthesizer",
            label="SDK Finalize",
            role="synthesizer",
            card_ref="agent_card_sdk_synth",
            routing=RoutingSpec(
                selection_mode="explicit",
                provider_id="qwen",
                model_id="qwen3-coder-plus",
                capability_claims=CapabilityClaimsSpec(
                    input_port_types=["text", "structured_json"],
                    output_port_types=["structured_json", "agent_report"],
                ),
            ),
            prompt=PromptSpec(template="Summarize the planned result into one final output."),
            tools=ToolsSpec(approval_mode="ask", allowed_tool_classes=["read_file"]),
            inputs=[
                PortSpec("task_context", "Task Context", "text"),
                PortSpec("plan_input", "Plan Input", "structured_json", schema_ref="schema.sdk_plan"),
            ],
            outputs=[
                PortSpec("machine_result", "Machine Result", "structured_json", schema_ref="schema.sdk_result"),
                PortSpec("final_report", "Final Report", "agent_report", required=False, artifact_kind="run_summary"),
            ],
            input_contract=InputContractSpec(
                mode="task_context_and_typed_ports",
                port_ids=["task_context", "plan_input"],
            ),
            output_contract=OutputContractSpec(
                mode="structured_and_artifacts",
                machine_result_schema_ref="schema.sdk_result",
                artifact_specs=[ArtifactSpec(kind="run_summary", id="final_report")],
            ),
            execution=ExecutionSpec(
                spawn_mode="isolated_lane",
                timeout_ms=120000,
                execution_backend="app_server",
            ),
            safety=SafetySpec(
                risk_class="moderate",
                allow_provider_calls=False,
                allow_code_changes=False,
                allow_install=False,
                requires_human_approval=False,
            ),
            ui=UiSpec(position=PositionSpec(x=360, y=180)),
        )
    )
    builder.add_edge(
        EdgeSpec(
            edge_id="edge_plan_finalize",
            from_node_id="node_plan",
            to_node_id="node_finalize",
            edge_type="context_handoff",
            handoff_contract=HandoffContractSpec(
                message_template="Use the bounded SDK plan to produce the final result.",
                required_output_schema_refs=["schema.sdk_plan"],
                port_bindings=[PortBindingSpec(from_port_id="machine_result", to_port_id="plan_input")],
            ),
            context_policy=ContextPolicySpec(policy_id="policy_edge_plan_finalize"),
            ui=UiSpec(position=PositionSpec(x=220, y=180)),
        )
    )
    return builder


class AgentOrchestrationSdkTests(unittest.TestCase):
    def test_python_sdk_builder_emits_same_custom_blank_graph_as_example_catalog(self) -> None:
        graph = _custom_blank_graph_builder().build()

        self.assertEqual(graph, load_agent_orchestration_example("custom_blank_graph"))
        self.assertEqual(_custom_blank_graph_builder().to_json(), _custom_blank_graph_builder().to_json())

    def test_python_sdk_builder_emits_same_canonical_graph_as_typescript_fixture(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        ts_fixture_path = repo_root / "apps" / "astrabridge-desktop" / "src" / "features" / "runtime" / "fixtures" / "customBlankGraph.fromTs.json"

        graph = _custom_blank_graph_builder().build()
        ts_fixture = json.loads(ts_fixture_path.read_text(encoding="utf-8"))

        self.assertEqual(graph, ts_fixture)

    def test_python_sdk_builder_can_compile_and_lower_code_authored_graph(self) -> None:
        builder = _two_node_compile_graph_builder()

        compiled = builder.compile()
        lowered = builder.lower_to_task_graph()

        self.assertEqual(compiled["graph_id"], "graph_sdk_compile_v1")
        self.assertEqual(compiled["topology"]["parallel_group_count"], 2)
        self.assertEqual([item["node_ids"] for item in compiled["parallel_groups"]], [["node_plan"], ["node_finalize"]])
        self.assertEqual(lowered["graph_id"], "graph_sdk_compile_v1")
        self.assertEqual(lowered["template_id"], "supervisor_worker_synthesizer")
        self.assertEqual([item["node_id"] for item in lowered["nodes"]], ["node_plan", "node_finalize"])

    def test_task_service_import_accepts_python_sdk_emitted_graph_file_with_current_compatibility_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("SDK Import", root / "sdk-import.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            task = tasks.create_task("SDK import task")

            path = workspace / ".astrabridge" / "sdk" / "custom_blank_graph.json"
            builder = _custom_blank_graph_builder()
            builder.write_json(path)

            imported = tasks.import_graph_from_orchestration_file(
                {"graph_path": path.relative_to(workspace).as_posix()}
            )
            imported_graph = imported["orchestration_graph"]
            expected = builder.build()
            expected["task_id"] = str(task["task_id"])
            expected["metadata"]["updated_at"] = imported_graph["metadata"]["updated_at"]

            diff_report = diff_agent_orchestration_graphs(expected, imported_graph)

            self.assertEqual(imported["graph"]["template_id"], "custom_blank_graph")
            self.assertEqual(imported_graph["graph_id"], "graph_custom_blank_graph_v1")
            self.assertEqual(diff_report["status"], "changed")
            self.assertEqual(diff_report["summary"]["change_types"], ["node_output_changed"])
            self.assertEqual(
                imported["graph"]["graph_document"]["compatibility_projection"]["writable_source"],
                "source_owned_canonical_file",
            )
            self.assertEqual(
                imported["graph"]["graph_document"]["source_ownership"]["ownership_mode"],
                "source_owned",
            )


if __name__ == "__main__":
    unittest.main()
