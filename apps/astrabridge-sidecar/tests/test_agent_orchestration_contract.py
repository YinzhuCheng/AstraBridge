from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_contract import (  # noqa: E402
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    lift_task_graph_to_agent_orchestration_graph,
    lower_agent_orchestration_graph_to_task_graph,
    validate_agent_orchestration_graph,
)
from astrabridge_sidecar.task_graph_contract import (  # noqa: E402
    GRAPH_TEMPLATE_IDS,
    load_task_graph_fixture,
)


def _valid_graph() -> dict:
    return {
        "schema_version": AGENT_ORCHESTRATION_SCHEMA_VERSION,
        "graph_id": "graph_code_fix_review_v1",
        "task_id": "task_example",
        "title": "Code Fix / Test / Review",
        "template_id": "code_fix_test_review",
        "status": "ready",
        "metadata": {
            "description": "Bounded code change with validation and review.",
            "tags": ["coding", "review"],
            "owners": [],
            "created_at": "2026-07-07T00:00:00+09:00",
            "updated_at": "2026-07-07T00:05:00+09:00",
        },
        "graph_policy": {
            "entry_node_ids": ["node_plan_fix"],
            "max_depth": 2,
            "default_permission_mode": "ask",
            "default_collaboration_mode": "default",
            "default_execution_backend": "app_server",
            "requires_dry_run_before_live": True,
        },
        "schema_registry": {
            "schema.plan_fix_result": {"type": "object", "required": ["plan"]},
            "schema.code_fix_result": {"type": "object", "required": ["changed_files"]},
            "schema.test_result": {"type": "object", "required": ["status"]},
        },
        "nodes": [
            {
                "node_id": "node_plan_fix",
                "kind": "supervisor",
                "label": "Plan Fix",
                "role": "planner",
                "card_ref": "agent_card_code_supervisor",
                "routing": {"selection_mode": "explicit", "provider_id": "qwen", "model_id": "qwen3-coder-plus"},
                "prompt": {"template_mode": "inline", "template": "Bound the fix and define expected evidence."},
                "tools": {"approval_mode": "ask", "allowed_tool_classes": ["web", "read_file"]},
                "ports": {
                    "inputs": [{"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True}],
                    "outputs": [
                        {"port_id": "machine_result", "label": "Machine Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.plan_fix_result"},
                        {"port_id": "plan_manifest", "label": "Plan Manifest", "port_type": "structured_json", "shape": "single", "required": False, "artifact_kind": "structured_json"},
                    ],
                },
                "input_contract": {"mode": "task_context_and_typed_ports", "port_ids": ["task_context"]},
                "output_contract": {
                    "mode": "structured_and_artifacts",
                    "machine_result_schema_ref": "schema.plan_fix_result",
                    "artifact_specs": [{"kind": "structured_json", "id": "plan_manifest"}],
                    "human_summary_required": True,
                },
                "execution": {"spawn_mode": "inline_lane", "timeout_ms": 120000, "retry_policy": {"max_attempts": 1}, "execution_backend": "app_server"},
                "safety": {
                    "risk_class": "moderate",
                    "allow_provider_calls": True,
                    "allow_code_changes": False,
                    "allow_install": False,
                    "requires_human_approval": False,
                },
                "ui": {"position": {"x": 60, "y": 160}},
                "status": "ready",
            },
            {
                "node_id": "node_code_fix",
                "kind": "worker",
                "label": "Apply Code Fix",
                "role": "coder",
                "card_ref": "agent_card_code_worker",
                "routing": {"selection_mode": "explicit", "provider_id": "qwen", "model_id": "qwen3-coder-plus"},
                "prompt": {"template_mode": "inline", "template": "Apply the bounded fix only within the approved file set."},
                "tools": {"approval_mode": "ask", "allowed_tool_classes": ["read_file", "edit_file", "shell"]},
                "ports": {
                    "inputs": [
                        {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                        {"port_id": "plan_input", "label": "Plan Input", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.plan_fix_result"},
                    ],
                    "outputs": [
                        {"port_id": "machine_result", "label": "Machine Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.code_fix_result"},
                        {"port_id": "bounded_patch", "label": "Bounded Patch", "port_type": "code_diff", "shape": "single", "required": False, "artifact_kind": "code_diff"},
                    ],
                },
                "input_contract": {"mode": "typed_ports", "port_ids": ["plan_input"]},
                "output_contract": {
                    "mode": "structured_and_artifacts",
                    "machine_result_schema_ref": "schema.code_fix_result",
                    "artifact_specs": [{"kind": "code_diff", "id": "bounded_patch"}],
                    "human_summary_required": True,
                },
                "execution": {
                    "spawn_mode": "subagent_worker",
                    "timeout_ms": 180000,
                    "retry_policy": {"max_attempts": 1},
                    "execution_backend": "app_server",
                    "subagent_policy": {
                        "isolation_mode": "lane",
                        "max_turns": 8,
                        "allow_direct_teammate_messages": False,
                        "share_worktree": False,
                        "allow_nested_subagents": False,
                    },
                },
                "safety": {
                    "risk_class": "high",
                    "allow_provider_calls": True,
                    "allow_code_changes": True,
                    "allow_install": False,
                    "requires_human_approval": True,
                    "approval_kind": "filesystem_write_gate",
                },
                "ui": {"position": {"x": 300, "y": 160}},
                "status": "ready",
            },
            {
                "node_id": "node_test",
                "kind": "validator",
                "label": "Run Tests",
                "role": "validator",
                "card_ref": "agent_card_test_validator",
                "routing": {"selection_mode": "profile", "profile_id": "profile-qwen-validator"},
                "prompt": {"template_mode": "inline", "template": "Run the scoped validation and report failures precisely."},
                "tools": {"approval_mode": "ask", "allowed_tool_classes": ["shell", "read_file"]},
                "ports": {
                    "inputs": [
                        {"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True},
                        {"port_id": "fix_result", "label": "Fix Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.code_fix_result"},
                        {"port_id": "patch_input", "label": "Patch Input", "port_type": "code_diff", "shape": "single", "required": False, "artifact_kind": "code_diff"},
                    ],
                    "outputs": [
                        {"port_id": "machine_result", "label": "Machine Result", "port_type": "structured_json", "shape": "single", "required": True, "schema_ref": "schema.test_result"},
                        {"port_id": "test_report", "label": "Test Report", "port_type": "agent_report", "shape": "single", "required": False, "artifact_kind": "test_report"},
                    ],
                },
                "input_contract": {"mode": "typed_ports", "port_ids": ["fix_result", "patch_input"]},
                "output_contract": {
                    "mode": "structured_and_artifacts",
                    "machine_result_schema_ref": "schema.test_result",
                    "artifact_specs": [{"kind": "test_report", "id": "test_report"}],
                    "human_summary_required": True,
                },
                "execution": {"spawn_mode": "isolated_lane", "timeout_ms": 120000, "retry_policy": {"max_attempts": 1}, "execution_backend": "app_server"},
                "safety": {
                    "risk_class": "moderate",
                    "allow_provider_calls": False,
                    "allow_code_changes": False,
                    "allow_install": False,
                    "requires_human_approval": False,
                },
                "ui": {"position": {"x": 540, "y": 160}},
                "status": "ready",
            },
        ],
        "edges": [
            {
                "edge_id": "edge_plan_fix",
                "from_node_id": "node_plan_fix",
                "to_node_id": "node_code_fix",
                "edge_type": "context_handoff",
                "handoff_contract": {
                    "message_template": "Use the approved file set and implementation plan.",
                    "message_part_modes": ["machine_result", "human_summary"],
                    "required_output_schema_refs": ["schema.plan_fix_result"],
                    "port_bindings": [{"from_port_id": "machine_result", "to_port_id": "plan_input"}],
                },
                "context_policy": {
                    "policy_id": "policy_plan_fix",
                    "history_mode": "latest_summary_only",
                    "artifact_mode": "required_output_only",
                    "exclude_private_memory": True,
                    "include_machine_results": True,
                    "include_human_summaries": True,
                    "summary_strategy": "human_and_machine",
                },
                "ui": {"position": {"x": 180, "y": 160}},
                "status": "ready",
            },
            {
                "edge_id": "edge_fix_test",
                "from_node_id": "node_code_fix",
                "to_node_id": "node_test",
                "edge_type": "artifact_handoff",
                "handoff_contract": {
                    "message_template": "Validate the bounded patch and return a failure-focused report.",
                    "message_part_modes": ["machine_result", "artifact_ref", "human_summary"],
                    "required_output_schema_refs": ["schema.code_fix_result"],
                    "port_bindings": [
                        {"from_port_id": "machine_result", "to_port_id": "fix_result"},
                        {"from_port_id": "bounded_patch", "to_port_id": "patch_input"},
                    ],
                },
                "context_policy": {
                    "policy_id": "policy_fix_test",
                    "history_mode": "explicit_refs_only",
                    "artifact_mode": "required_output_only",
                    "exclude_private_memory": True,
                    "include_machine_results": True,
                    "include_human_summaries": True,
                    "summary_strategy": "human_and_machine",
                },
                "ui": {"position": {"x": 420, "y": 160}},
                "status": "ready",
            },
        ],
        "migration": {
            "source_kind": "native_authoring",
            "compiled_task_graph_version": "astrabridge-task-graph-v1",
        },
        "state_version": 1,
    }


class AgentOrchestrationContractTests(unittest.TestCase):
    def test_valid_graph_accepts_known_profile_provider_and_model_refs(self) -> None:
        graph = _valid_graph()

        validated = validate_agent_orchestration_graph(
            graph,
            known_profile_ids={"profile-qwen-validator"},
            known_provider_ids={"qwen"},
            known_model_ids={"qwen3-coder-plus"},
            known_model_capabilities={
                "qwen3-coder-plus": {
                    "input_port_types": ["text", "structured_json", "code_diff"],
                    "output_port_types": ["structured_json", "code_diff", "agent_report"],
                }
            },
        )

        self.assertEqual(validated["schema_version"], AGENT_ORCHESTRATION_SCHEMA_VERSION)
        self.assertEqual(validated["graph_policy"]["entry_node_ids"], ["node_plan_fix"])

    def test_invalid_graph_cases_fail_with_actionable_messages(self) -> None:
        cases: list[tuple[str, str, callable]] = []

        def missing_prompt() -> dict:
            graph = _valid_graph()
            graph["nodes"][0]["prompt"] = {"template_mode": "inline"}
            return graph

        def same_node_edge() -> dict:
            graph = _valid_graph()
            graph["edges"][0]["to_node_id"] = graph["edges"][0]["from_node_id"]
            return graph

        def cycle_graph() -> dict:
            graph = _valid_graph()
            graph["edges"].append(
                {
                    "edge_id": "edge_test_plan",
                    "from_node_id": "node_test",
                    "to_node_id": "node_plan_fix",
                    "edge_type": "control_dependency",
                    "handoff_contract": {
                        "message_template": "Loop back",
                        "message_part_modes": ["machine_result"],
                        "required_output_schema_refs": ["schema.test_result"],
                        "port_bindings": [{"from_port_id": "machine_result", "to_port_id": "task_context"}],
                    },
                    "context_policy": {
                        "policy_id": "policy_test_plan",
                        "history_mode": "latest_summary_only",
                        "artifact_mode": "required_output_only",
                        "exclude_private_memory": True,
                        "include_machine_results": True,
                        "include_human_summaries": True,
                        "summary_strategy": "human_and_machine",
                    },
                    "ui": {"position": {"x": 300, "y": 60}},
                    "status": "ready",
                }
            )
            return graph

        def missing_output_schema_ref() -> dict:
            graph = _valid_graph()
            graph["nodes"][1]["output_contract"]["machine_result_schema_ref"] = ""
            return graph

        def unsafe_permissions() -> dict:
            graph = _valid_graph()
            graph["nodes"][1]["safety"]["requires_human_approval"] = False
            return graph

        def unsafe_private_memory() -> dict:
            graph = _valid_graph()
            graph["edges"][0]["context_policy"]["exclude_private_memory"] = False
            return graph

        def unknown_port_type() -> dict:
            graph = _valid_graph()
            graph["nodes"][1]["ports"]["outputs"][1]["port_type"] = "unknown_modality"
            return graph

        def invalid_model_modality_claim() -> dict:
            graph = _valid_graph()
            graph["nodes"][1]["routing"]["capability_claims"] = {
                "input_port_types": ["text", "structured_json", "image"],
                "output_port_types": ["structured_json", "code_diff"],
            }
            graph["nodes"][1]["ports"]["inputs"].append(
                {"port_id": "image_input", "label": "Image Input", "port_type": "image", "shape": "single", "required": False}
            )
            graph["nodes"][1]["input_contract"]["port_ids"] = ["plan_input", "image_input"]
            return graph

        def excessive_depth() -> dict:
            graph = _valid_graph()
            graph["graph_policy"]["max_depth"] = 1
            return graph

        cases.extend(
            [
                ("missing_prompt", "prompt[node_plan_fix].template", missing_prompt),
                ("same_node_edge", "must not connect a node to itself", same_node_edge),
                ("cycle_graph", "disallowed cycle", cycle_graph),
                ("missing_output_schema_ref", "machine_result_schema_ref", missing_output_schema_ref),
                ("unsafe_permissions", "must require human approval", unsafe_permissions),
                ("unsafe_private_memory", "exclude_private_memory=true", unsafe_private_memory),
                ("unknown_port_type", "must be one of", unknown_port_type),
                ("excessive_depth", "exceeds max_depth", excessive_depth),
            ]
        )

        for case_id, expected_error, builder in cases:
            with self.subTest(case_id=case_id):
                with self.assertRaises((ValueError, TypeError)) as exc:
                    validate_agent_orchestration_graph(
                        builder(),
                        known_model_capabilities={
                            "qwen3-coder-plus": {
                                "input_port_types": ["text", "structured_json", "code_diff"],
                                "output_port_types": ["structured_json", "code_diff", "agent_report"],
                            }
                        },
                    )
                self.assertIn(expected_error, str(exc.exception))

        with self.assertRaises((ValueError, TypeError)) as exc:
            validate_agent_orchestration_graph(
                invalid_model_modality_claim(),
                known_model_capabilities={
                    "qwen3-coder-plus": {
                        "input_port_types": ["text", "structured_json", "code_diff"],
                        "output_port_types": ["structured_json", "code_diff", "agent_report"],
                    }
                },
            )
        self.assertIn("invalid provider/model modality claims", str(exc.exception))

    def test_duplicate_node_ids_are_rejected(self) -> None:
        graph = _valid_graph()
        graph["nodes"].append(deepcopy(graph["nodes"][0]))

        with self.assertRaises(ValueError) as exc:
            validate_agent_orchestration_graph(graph)
        self.assertIn("duplicate node_id", str(exc.exception))

    def test_missing_schema_registry_ref_is_rejected(self) -> None:
        graph = _valid_graph()
        graph["edges"][0]["handoff_contract"]["required_output_schema_refs"] = ["schema.unknown"]

        with self.assertRaises(ValueError) as exc:
            validate_agent_orchestration_graph(graph)
        self.assertIn("unknown schema", str(exc.exception))

    def test_legacy_task_graph_fixtures_lift_with_warnings_and_lower_back(self) -> None:
        for template_id in GRAPH_TEMPLATE_IDS:
            with self.subTest(template_id=template_id):
                legacy = load_task_graph_fixture(template_id)
                lifted = lift_task_graph_to_agent_orchestration_graph(legacy)
                warnings = list(lifted["migration"]["warnings"])
                self.assertTrue(warnings)
                self.assertEqual(lifted["migration"]["source_kind"], "legacy_task_graph")
                lowered = lower_agent_orchestration_graph_to_task_graph(lifted)
                self.assertEqual(lowered["graph_id"], legacy["graph_id"])
                self.assertEqual(lowered["template_id"], legacy["template_id"])


if __name__ == "__main__":
    unittest.main()
