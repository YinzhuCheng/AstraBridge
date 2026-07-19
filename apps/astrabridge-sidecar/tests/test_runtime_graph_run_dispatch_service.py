from __future__ import annotations

import sys
import unittest
from pathlib import Path


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.runtime_graph_run_dispatch_service import (  # noqa: E402
    RuntimeGraphRunDispatchService,
)


class _StubRuntime:
    def __init__(self, *, current_project: dict[str, object] | None = None) -> None:
        self._projects = type("Projects", (), {"current_project": current_project})()
        self._tasks = None


class RuntimeGraphRunDispatchServiceTests(unittest.TestCase):
    def test_resolve_dispatch_limits_honors_topology_and_override_flooring(self) -> None:
        service = RuntimeGraphRunDispatchService(_StubRuntime(current_project={"project_id": "proj-1"}))

        limits = service.resolve_dispatch_limits(
            payload={
                "_dispatch_limits": {
                    "reserved_interactive_slots": 0,
                    "breaker_failure_threshold": 0,
                    "breaker_cooldown_seconds": 0,
                }
            },
            compiled_plan={"topology": {"max_parallelism": 3}},
        )

        self.assertEqual(limits["max_active_nodes"], 3)
        self.assertEqual(limits["reserved_interactive_slots"], 0)
        self.assertEqual(limits["max_provider_active_nodes"], 4)
        self.assertEqual(limits["max_model_active_nodes"], 2)
        self.assertEqual(limits["max_workspace_active_nodes"], 8)
        self.assertEqual(limits["breaker_failure_threshold"], 1)
        self.assertEqual(limits["breaker_cooldown_seconds"], 1.0)
        self.assertEqual(limits["retry_budget_max"], 3)

    def test_normalize_parallel_groups_batches_large_groups_by_dispatch_limits(self) -> None:
        normalized, max_parallelism = RuntimeGraphRunDispatchService.normalize_parallel_groups(
            {
                "parallel_groups": [
                    {"group_id": "fanout", "node_ids": ["a", "b", "c", "d", "e"]},
                ],
                "topology": {"max_parallelism": 5},
            },
            dispatch_limits={
                "max_active_nodes": 3,
                "reserved_interactive_slots": 1,
                "max_provider_active_nodes": 2,
                "max_model_active_nodes": 4,
                "max_workspace_active_nodes": 8,
            },
        )

        self.assertEqual(max_parallelism, 2)
        self.assertEqual(
            [item["group_id"] for item in normalized],
            ["fanout__batch_1", "fanout__batch_2", "fanout__batch_3"],
        )
        self.assertEqual(
            [item["node_ids"] for item in normalized],
            [["a", "b"], ["c", "d"], ["e"]],
        )

    def test_build_dispatch_request_uses_project_id_or_workspace_default(self) -> None:
        with_project = RuntimeGraphRunDispatchService(_StubRuntime(current_project={"project_id": "proj-42"}))
        request = with_project.build_dispatch_request(
            run_id="run-1",
            node_id="node-1",
            provider_id="qwen",
            model_id="qwen3.7-plus",
        )
        self.assertEqual(request.workspace_id, "proj-42")
        self.assertEqual(request.provider_id, "qwen")
        self.assertEqual(request.model_id, "qwen3.7-plus")

        fallback = RuntimeGraphRunDispatchService(_StubRuntime(current_project=None))
        fallback_request = fallback.build_dispatch_request(
            run_id="run-2",
            node_id="node-2",
            provider_id="",
            model_id="",
        )
        self.assertEqual(fallback_request.workspace_id, "workspace-default")
        self.assertEqual(fallback_request.provider_id, "unknown-provider")
        self.assertEqual(fallback_request.model_id, "unknown-model")


if __name__ == "__main__":
    unittest.main()
