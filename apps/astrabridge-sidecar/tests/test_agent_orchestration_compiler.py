from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_compiler import (  # noqa: E402
    AGENT_ORCHESTRATION_COMPILED_PLAN_VERSION,
    compile_agent_orchestration_graph,
)
from astrabridge_sidecar.agent_orchestration_file_format import load_agent_orchestration_example  # noqa: E402


class AgentOrchestrationCompilerTests(unittest.TestCase):
    def test_linear_graph_compiles_to_one_node_per_group_in_dependency_order(self) -> None:
        graph = load_agent_orchestration_example("supervisor_worker_synthesizer")

        compiled = compile_agent_orchestration_graph(graph)

        self.assertEqual(compiled["schema_version"], AGENT_ORCHESTRATION_COMPILED_PLAN_VERSION)
        self.assertEqual(compiled["topology"]["parallel_group_count"], 3)
        self.assertEqual([item["node_ids"] for item in compiled["parallel_groups"]], [["node_supervisor"], ["node_worker"], ["node_synth"]])

    def test_fanout_fanin_graph_compiles_parallel_branch_group_and_all_required_join(self) -> None:
        graph = load_agent_orchestration_example("fanout_research_synthesis")

        compiled = compile_agent_orchestration_graph(graph)

        self.assertEqual(compiled["topology"]["parallel_group_count"], 3)
        self.assertEqual(compiled["parallel_groups"][1]["node_ids"], ["node_branch_a", "node_branch_b"])
        synth = next(item for item in compiled["nodes"] if item["node_id"] == "node_synth")
        self.assertEqual(synth["join_mode"], "all_required")
        self.assertEqual(sorted(synth["dependency_node_ids"]), ["node_branch_a", "node_branch_b"])

    def test_approval_gated_graph_compiles_manual_gate_as_approval_required(self) -> None:
        graph = load_agent_orchestration_example("provider_update_smoke")

        compiled = compile_agent_orchestration_graph(graph)

        gate = next(item for item in compiled["nodes"] if item["node_id"] == "node_gate")
        self.assertTrue(gate["approval_required"])
        self.assertEqual(gate["join_mode"], "approval_gate_required")
        self.assertIn("node_gate", compiled["approval_nodes"])

    def test_invalid_cycle_bubbles_up_from_contract_validation(self) -> None:
        graph = load_agent_orchestration_example("code_fix_review")
        graph["edges"].append(
            {
                "edge_id": "edge_review_plan",
                "from_node_id": "node_review",
                "to_node_id": "node_plan_fix",
                "edge_type": "control_dependency",
                "handoff_contract": {
                    "message_template": "Loop back",
                    "message_part_modes": ["machine_result"],
                    "required_output_schema_refs": ["schema.review_result"],
                    "port_bindings": [{"from_port_id": "machine_result", "to_port_id": "task_context"}],
                },
                "context_policy": {
                    "policy_id": "policy_review_plan",
                    "history_mode": "latest_summary_only",
                    "artifact_mode": "required_output_only",
                    "exclude_private_memory": True,
                    "include_machine_results": True,
                    "include_human_summaries": True,
                    "summary_strategy": "human_and_machine",
                },
                "ui": {"position": {"x": 300, "y": 60}, "layout_mode": "canvas"},
                "status": "ready",
            }
        )

        with self.assertRaises(ValueError) as exc:
            compile_agent_orchestration_graph(graph)
        self.assertIn("disallowed cycle", str(exc.exception))

    def test_missing_dependency_for_required_input_port_is_rejected(self) -> None:
        graph = load_agent_orchestration_example("fanout_research_synthesis")
        graph["edges"] = [edge for edge in graph["edges"] if edge["edge_id"] != "edge_b_synth"]

        with self.assertRaises(ValueError) as exc:
            compile_agent_orchestration_graph(graph)
        self.assertIn("missing dependency", str(exc.exception))

    def test_unsupported_port_binding_type_is_rejected(self) -> None:
        graph = load_agent_orchestration_example("multimodal_capability_adapter")
        graph["edges"][0]["handoff_contract"]["port_bindings"][1]["to_port_id"] = "probe_result"

        with self.assertRaises(ValueError) as exc:
            compile_agent_orchestration_graph(graph)
        self.assertIn("unsupported port binding", str(exc.exception))

    def test_unsafe_implicit_full_history_sharing_is_rejected(self) -> None:
        graph = load_agent_orchestration_example("code_fix_review")
        graph["edges"][0]["context_policy"]["history_mode"] = "last_n_messages"
        graph["edges"][0]["context_policy"]["history_length"] = 0

        with self.assertRaises(ValueError) as exc:
            compile_agent_orchestration_graph(graph)
        self.assertIn("unsafe implicit full-history sharing", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
