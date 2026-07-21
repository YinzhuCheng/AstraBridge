from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_compiler import compile_agent_orchestration_graph  # noqa: E402
from astrabridge_sidecar.agent_orchestration_file_format import agent_orchestration_example_catalog  # noqa: E402
from astrabridge_sidecar.communication_isolation import (  # noqa: E402
    COMMUNICATION_ISOLATION_SCHEMA_VERSION,
    validate_typed_communication_isolation,
)
from astrabridge_sidecar.skill_orchestration_validation import (  # noqa: E402
    load_skill_orchestration_manifest,
    resolve_skill_to_graph,
)


class CommunicationIsolationTests(unittest.TestCase):
    def test_builtin_graphs_pass_one_typed_isolation_decision_and_compiled_projection(self) -> None:
        for graph_id, graph in agent_orchestration_example_catalog().items():
            with self.subTest(graph_id=graph_id):
                compiled = compile_agent_orchestration_graph(graph)
                first = validate_typed_communication_isolation(graph, compiled)
                second = validate_typed_communication_isolation(graph, compiled)
                self.assertEqual(first["schema_version"], COMMUNICATION_ISOLATION_SCHEMA_VERSION)
                self.assertEqual(first["status"], "pass")
                self.assertEqual(first["decision_digest"], second["decision_digest"])
                self.assertEqual(first["provenance"]["provider_calls"], 0)
                self.assertEqual(first["provenance"]["mcp_calls"], 0)
                self.assertEqual(first["provenance"]["agent_invocations"], 0)
                self.assertEqual(first["provenance"]["protocol_owner"], "astrabridge_sidecar.protocol")

    def test_unsafe_history_private_memory_direct_messages_and_artifact_leakage_fail_closed(self) -> None:
        graph = copy.deepcopy(agent_orchestration_example_catalog()["code_fix_review"])
        edge = graph["edges"][0]
        edge["context_policy"]["history_mode"] = "full_history"
        edge["context_policy"]["exclude_private_memory"] = False
        edge["context_policy"]["allow_direct_teammate_messages"] = True
        edge["context_policy"]["included_artifacts"] = ["artifact.not_declared"]
        decision = validate_typed_communication_isolation(graph)
        self.assertEqual(decision["status"], "blocked")
        blockers = "\n".join(decision["blockers"])
        self.assertIn("unsafe_history_mode", blockers)
        self.assertIn("exclude_private_memory_must_be_true", blockers)
        self.assertIn("direct_teammate_messages_must_be_disabled", blockers)
        self.assertIn("undeclared_artifacts", blockers)

    def test_undeclared_message_parts_and_typed_port_mismatch_are_rejected(self) -> None:
        graph = copy.deepcopy(agent_orchestration_example_catalog()["supervisor_worker_synthesizer"])
        edge = graph["edges"][0]
        edge["handoff_contract"]["message_part_modes"] = ["machine_result", "provider_private_reasoning"]
        edge["handoff_contract"]["port_bindings"][0]["to_port_id"] = "not_a_declared_input"
        decision = validate_typed_communication_isolation(graph)
        self.assertEqual(decision["status"], "blocked")
        blockers = "\n".join(decision["blockers"])
        self.assertIn("undeclared_message_part_modes", blockers)
        self.assertIn("unknown_target_input_port", blockers)

    def test_secret_like_handoff_is_blocked_without_echoing_payload(self) -> None:
        graph = copy.deepcopy(agent_orchestration_example_catalog()["supervisor_worker_synthesizer"])
        secret = "Authorization: " + "Bearer " + ("a" * 16)
        graph["edges"][0]["handoff_contract"]["message_template"] = secret
        decision = validate_typed_communication_isolation(graph)
        encoded = json.dumps(decision, ensure_ascii=False)
        self.assertEqual(decision["status"], "blocked")
        self.assertNotIn(secret, encoded)
        self.assertTrue(any("secret_like" in item or "provider_private" in item for item in decision["blockers"]))

    def test_skill_resolution_exposes_same_isolation_decision_and_blocks_unsafe_inline_graph(self) -> None:
        manifest = load_skill_orchestration_manifest("astrabridge-supervisor-worker-synthesizer")
        graph = copy.deepcopy(agent_orchestration_example_catalog()["supervisor_worker_synthesizer"])
        graph["edges"][0]["context_policy"]["history_mode"] = "full_history"
        manifest["resolution"] = {
            "mode": "inline_graph",
            "graph_schema_version": graph["schema_version"],
            "inline_graph": graph,
            "parameter_schema": manifest["resolution"]["parameter_schema"],
            "bindings": manifest["resolution"]["bindings"],
        }
        resolution = resolve_skill_to_graph(
            manifest,
            {"task_goal": "Keep this bounded."},
        )
        self.assertIsInstance(resolution.get("communication_isolation"), dict)
        self.assertEqual(resolution["communication_isolation"]["status"], "blocked")
        self.assertTrue(any("communication_isolation:" in item for item in resolution["blockers"]))


if __name__ == "__main__":
    unittest.main()
