from __future__ import annotations

import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_compiler import compile_agent_orchestration_graph  # noqa: E402
from astrabridge_sidecar.agent_orchestration_file_format import load_agent_orchestration_example  # noqa: E402
from astrabridge_sidecar.runtime_guardrails import (  # noqa: E402
    RUNTIME_GUARDRAIL_HARD_LIMITS,
    RUNTIME_GUARDRAIL_SCHEMA_VERSION,
    evaluate_runtime_guardrails,
)
from astrabridge_sidecar.modal_service import ModalService  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.runtime_service import RuntimeService  # noqa: E402
from astrabridge_sidecar.task_service import TaskService  # noqa: E402


class RuntimeGuardrailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = load_agent_orchestration_example("fanout_research_synthesis")
        self.compiled = compile_agent_orchestration_graph(self.graph)
        self.budget = {"limits": {"total_tokens": 80_000}}

    def test_bounded_legacy_budget_is_normalized_and_passes(self) -> None:
        first = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=self.compiled,
            run_budget=self.budget,
            dispatch_limits={
                "max_active_nodes": 2,
                "reserved_interactive_slots": 1,
                "max_provider_active_nodes": 4,
                "max_model_active_nodes": 2,
                "retry_budget_max": 2,
            },
        )
        second = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=self.compiled,
            run_budget=self.budget,
            dispatch_limits={
                "max_active_nodes": 2,
                "reserved_interactive_slots": 1,
                "max_provider_active_nodes": 4,
                "max_model_active_nodes": 2,
                "retry_budget_max": 2,
            },
        )
        self.assertEqual(first["schema_version"], RUNTIME_GUARDRAIL_SCHEMA_VERSION)
        self.assertEqual(first["status"], "pass")
        self.assertEqual(first["decision_digest"], second["decision_digest"])
        self.assertEqual(first["provenance"]["provider_calls_started"], 0)
        self.assertEqual(first["provenance"]["mcp_calls_started"], 0)
        self.assertEqual(first["provenance"]["agents_started"], 0)
        self.assertEqual(first["normalized_budget"]["max_total_tokens"], 80_000)
        self.assertEqual(first["effective_dispatch_limits"]["reserved_interactive_slots"], 1)

    def test_budget_ceiling_and_observed_counts_fail_closed(self) -> None:
        too_many_agents = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=self.compiled,
            run_budget={"max_total_agents": 1, "max_total_tokens": 80_000},
        )
        self.assertTrue(any("agent count" in item for item in too_many_agents["blockers"]))

        too_many_tokens = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=self.compiled,
            run_budget={"max_total_tokens": RUNTIME_GUARDRAIL_HARD_LIMITS["max_total_tokens"] + 1},
        )
        self.assertTrue(any("max_total_tokens" in item for item in too_many_tokens["blockers"]))

        too_much_parallelism = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=self.compiled,
            run_budget={"max_parallel_agents": 1, "max_total_tokens": 80_000},
        )
        self.assertTrue(any("max_parallel_agents" in item for item in too_much_parallelism["blockers"]))

    def test_nested_subagents_direct_messages_and_private_memory_fail_closed(self) -> None:
        compiled = copy.deepcopy(self.compiled)
        compiled["nodes"][0]["execution"]["subagent_policy"]["allow_nested_subagents"] = True
        nested = evaluate_runtime_guardrails(graph=self.graph, compiled_plan=compiled, run_budget=self.budget)
        self.assertTrue(any("nested" in item for item in nested["blockers"]))

        direct_graph = copy.deepcopy(self.graph)
        direct_graph["edges"][0]["context_policy"]["allow_direct_teammate_messages"] = True
        direct = evaluate_runtime_guardrails(graph=direct_graph, compiled_plan=self.compiled, run_budget=self.budget)
        self.assertTrue(any("direct teammate" in item for item in direct["blockers"]))

        private_graph = copy.deepcopy(self.graph)
        private_graph["edges"][0]["context_policy"]["exclude_private_memory"] = False
        private = evaluate_runtime_guardrails(graph=private_graph, compiled_plan=self.compiled, run_budget=self.budget)
        self.assertTrue(any("private memory" in item for item in private["blockers"]))

    def test_retry_concurrency_and_depth_limits_are_enforced(self) -> None:
        compiled = copy.deepcopy(self.compiled)
        compiled["nodes"][0]["execution"]["retry_policy"]["max_attempts"] = 3
        retry = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=compiled,
            run_budget={"max_retries": 1, "max_total_tokens": 80_000},
        )
        self.assertTrue(any("retry events" in item for item in retry["blockers"]))

        missing_route = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=self.compiled,
            run_budget={
                "max_total_tokens": 80_000,
                "provider_concurrency": [],
                "model_concurrency": [],
            },
        )
        self.assertTrue(any("missing route" in item for item in missing_route["blockers"]))

        deep = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=self.compiled,
            run_budget=self.budget,
            parent_context={"ancestor_graph_ids": ["parent-a", "parent-b"]},
        )
        self.assertTrue(any("invocation depth" in item for item in deep["blockers"]))

    def test_strict_budget_mode_rejects_compatibility_derived_fields(self) -> None:
        strict = evaluate_runtime_guardrails(
            graph=self.graph,
            compiled_plan=self.compiled,
            run_budget=self.budget,
            require_complete_budget=True,
        )
        self.assertTrue(any("required for strict live admission" in item for item in strict["blockers"]))

    def test_runtime_service_queue_rejects_excess_agent_budget_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Runtime guardrail admission", root / "guardrail.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Runtime guardrail task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                node = dict(graph["nodes"][0])
                node.update(
                    {
                        "kind": "worker",
                        "provider_id": "qwen",
                        "model_id": "qwen3-coder-plus",
                        "execution_backend": "app_server",
                    }
                )
                graph["nodes"][0] = node
                graph = tasks.save_graph_definition({"graph": graph})["graph"]
                tasks.dry_run_graph = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
                    "dry_run": {"overall_status": "pass", "graph_result": {"reasons": []}}
                }
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    with self.assertRaisesRegex(ValueError, "Runtime guardrails blocked"):
                        runtime.queue_task_graph_run(
                            {
                                "graph_id": graph["graph_id"],
                                "budget": {"max_total_agents": 0, "max_total_tokens": 10},
                            }
                        )
                    self.assertEqual(runtime._graph_dispatch_control.status()["active_dispatch_count"], 0)
                finally:
                    runtime.shutdown()
            finally:
                if previous_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_root


if __name__ == "__main__":
    unittest.main()
