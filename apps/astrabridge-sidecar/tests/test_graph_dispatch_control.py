from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.graph_dispatch_control import GraphDispatchController, GraphDispatchRequest  # noqa: E402


class GraphDispatchControlTests(unittest.TestCase):
    def test_provider_and_model_concurrency_maps_are_enforced_per_route(self) -> None:
        controller = GraphDispatchController()
        limits = {
            "max_active_nodes": 4,
            "reserved_interactive_slots": 0,
            "max_provider_active_nodes": 4,
            "max_model_active_nodes": 4,
            "max_workspace_active_nodes": 4,
            "provider_concurrency": [
                {"provider_id": "qwen", "max_active_agents": 1},
                {"provider_id": "glm", "max_active_agents": 2},
            ],
            "model_concurrency": [
                {"provider_id": "qwen", "model_id": "qwen-a", "max_active_agents": 1},
                {"provider_id": "qwen", "model_id": "qwen-b", "max_active_agents": 1},
                {"provider_id": "glm", "model_id": "glm-a", "max_active_agents": 1},
            ],
        }
        qwen_a = GraphDispatchRequest("run-1", "node-a", "workspace", "qwen", "qwen-a")
        qwen_b = GraphDispatchRequest("run-1", "node-b", "workspace", "qwen", "qwen-b")
        glm_a = GraphDispatchRequest("run-1", "node-c", "workspace", "glm", "glm-a")

        qwen_token, qwen_admission = controller.try_acquire(qwen_a, limits=limits)
        self.assertEqual(qwen_admission["status"], "acquired")
        self.assertIsNotNone(qwen_token)

        _, qwen_denied = controller.try_acquire(qwen_b, limits=limits)
        self.assertEqual(qwen_denied["reason"], "provider_limit")

        glm_token, glm_admission = controller.try_acquire(glm_a, limits=limits)
        self.assertEqual(glm_admission["status"], "acquired")
        self.assertIsNotNone(glm_token)

        controller.release(qwen_token)
        qwen_b_token, qwen_b_admission = controller.try_acquire(qwen_b, limits=limits)
        self.assertEqual(qwen_b_admission["status"], "acquired")
        controller.release(qwen_b_token)
        controller.release(glm_token)

    def test_scalar_compatibility_limit_remains_fallback_for_unmapped_route(self) -> None:
        controller = GraphDispatchController()
        request = GraphDispatchRequest("run-2", "node-a", "workspace", "unknown", "model")
        token, result = controller.try_acquire(
            request,
            limits={
                "max_active_nodes": 2,
                "reserved_interactive_slots": 0,
                "max_provider_active_nodes": 1,
                "max_model_active_nodes": 1,
                "max_workspace_active_nodes": 2,
                "provider_concurrency": [{"provider_id": "qwen", "max_active_agents": 1}],
                "model_concurrency": [{"provider_id": "qwen", "model_id": "qwen-a", "max_active_agents": 1}],
            },
        )
        self.assertEqual(result["status"], "acquired")
        controller.release(token)

    def test_provider_call_budget_is_monotonic_across_retries(self) -> None:
        controller = GraphDispatchController()
        request = GraphDispatchRequest("run-budget", "node-a", "workspace", "qwen", "qwen-a")
        limits = {
            "max_active_nodes": 1,
            "reserved_interactive_slots": 0,
            "max_provider_active_nodes": 1,
            "max_model_active_nodes": 1,
            "max_workspace_active_nodes": 1,
            "max_provider_calls": 1,
        }
        token, first = controller.try_acquire(request, limits=limits)
        self.assertEqual(first["status"], "acquired")
        controller.release(token)
        _, second = controller.try_acquire(request, limits=limits)
        self.assertEqual(second["reason"], "provider_call_budget")
        self.assertEqual(controller.status()["run_provider_call_counts"]["run-budget"], 1)
        controller.clear_run("run-budget")


if __name__ == "__main__":
    unittest.main()
