from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
import datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.common import now_iso
from astrabridge_sidecar.agent_orchestration_file_format import load_agent_orchestration_example
from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.task_service import TaskService


class TaskGraphWorkerRuntimeTests(unittest.TestCase):
    def test_no_tools_graph_policy_omits_dynamic_tools_and_auto_declines_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("No tools policy", root / "no-tools.abproj", workspace_root=workspace)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._dynamic_tools = lambda: [{"name": "unsafe_dynamic_tool"}]  # type: ignore[method-assign]
            runtime.interrupt_turn = lambda profile, thread_id, turn_id: {  # type: ignore[method-assign]  # noqa: ARG005
                "interrupt": {"ok": True, "turnId": turn_id}
            }

            self.assertEqual(
                runtime._graph_worker_turn_execution_policy(  # type: ignore[attr-defined]
                    {"allowed_tool_classes": [], "supports_mcp": False}
                ),
                "no_tools",
            )
            self.assertEqual(
                runtime._graph_worker_turn_execution_policy(  # type: ignore[attr-defined]
                    {"allowed_tool_classes": ["read_file"], "supports_mcp": False}
                ),
                "standard",
            )
            thread_params = runtime._thread_start_params(  # type: ignore[attr-defined]
                profile={"provider_id": "qwen", "model": "qwen3-coder-plus"},
                model="qwen3-coder-plus",
                permission_mode="ask",
                include_dynamic_tools=False,
            )
            self.assertNotIn("dynamicTools", thread_params)

            runtime._register_active_turn_execution_policy("thread-worker", "no_tools")  # type: ignore[attr-defined]
            runtime._record_execution_policy_started(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
                policy="no_tools",
            )
            approval = runtime._on_server_request(  # type: ignore[attr-defined]
                "item/commandExecution/requestApproval",
                {"threadId": "thread-worker", "turnId": "nested-runtime-turn"},
            )
            dynamic = runtime._on_server_request(  # type: ignore[attr-defined]
                "item/tool/call",
                {"threadId": "thread-worker", "turnId": "nested-runtime-turn", "tool": "unsafe_dynamic_tool"},
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "item/started",
                {
                    "threadId": "thread-worker",
                    "turnId": "nested-runtime-turn",
                    "item": {"id": "command-1", "type": "commandExecution"},
                },
            )

            self.assertEqual(approval, {"decision": "decline"})
            self.assertFalse(dynamic["success"])
            violation = runtime._turn_execution_policy_violation(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
            )
            self.assertIsNotNone(violation)
            self.assertEqual(violation["status"], "violated")
            self.assertEqual(violation["blocked_tool_call_count"], 3)
            self.assertFalse(violation["compliant_success"])

    def test_no_tools_observed_turn_alias_accepts_usage_and_fail_closed_interrupts_started_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("No tools observed turn", root / "no-tools-observed-turn.abproj", workspace_root=workspace)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            interrupted: list[tuple[str, str]] = []
            runtime.interrupt_turn = lambda profile, thread_id, turn_id: interrupted.append((thread_id, turn_id)) or {  # type: ignore[method-assign]  # noqa: ARG005
                "interrupt": {"ok": True, "turnId": turn_id}
            }
            runtime._cache_thread_entry(  # type: ignore[attr-defined]
                "thread-worker",
                {
                    "profile_id": "qwen",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                },
            )

            runtime._register_active_turn_execution_policy("thread-worker", "no_tools")  # type: ignore[attr-defined]
            runtime._record_execution_policy_started(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
                policy="no_tools",
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "turn/started",
                {
                    "threadId": "thread-worker",
                    "turn": {"id": "observed-turn", "status": "inProgress"},
                },
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "thread/tokenUsage/updated",
                {
                    "threadId": "thread-worker",
                    "turnId": "observed-turn",
                    "tokenUsage": {
                        "total": {
                            "inputTokens": 40,
                            "outputTokens": 10,
                            "totalTokens": 50,
                        },
                        "last": {"inputTokens": 40, "outputTokens": 10, "totalTokens": 50},
                        "modelContextWindow": 128000,
                    },
                },
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "item/started",
                {
                    "threadId": "thread-worker",
                    "turnId": "observed-turn",
                    "item": {"id": "command-1", "type": "commandExecution"},
                },
            )

            signal = runtime._graph_live_turn_usage_signal(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
                provider_id="qwen",
                model="qwen3-coder-plus",
            )
            violation = runtime._turn_execution_policy_violation(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
            )

            self.assertEqual(signal["status"], "available")
            self.assertEqual(signal["tokens"]["total_tokens"], 50)
            self.assertEqual(interrupted, [("thread-worker", "observed-turn")])
            self.assertIsNotNone(violation)
            self.assertEqual(violation["blocked_tool_call_count"], 1)
            self.assertFalse(violation["compliant_success"])

    def test_no_tools_policy_survives_terminal_notification_until_follow_on_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("No tools follow-on cleanup", root / "no-tools-follow-on.abproj", workspace_root=workspace)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._schedule_terminal_thread_snapshot = lambda **_payload: None  # type: ignore[method-assign]
            interrupted: list[str] = []
            runtime.interrupt_turn = lambda profile, thread_id, turn_id: interrupted.append(f"{thread_id}:{turn_id}")  # type: ignore[method-assign]  # noqa: ARG005
            runtime._clear_bounded_turn_goal = lambda client, **kwargs: True  # type: ignore[method-assign]  # noqa: ARG005

            runtime._register_active_turn_execution_policy("thread-worker", "no_tools")  # type: ignore[attr-defined]
            runtime._record_execution_policy_started(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
                policy="no_tools",
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "turn/completed",
                {
                    "threadId": "thread-worker",
                    "turn": {"id": "turn-worker", "status": "completed", "items": []},
                },
            )

            approval_before_cleanup = runtime._on_server_request(  # type: ignore[attr-defined]
                "item/commandExecution/requestApproval",
                {"threadId": "thread-worker", "turnId": "follow-on-turn"},
            )
            active_before_cleanup = runtime._active_turn_execution_policy_for(  # type: ignore[attr-defined]
                {"threadId": "thread-worker", "turnId": "follow-on-turn"}
            )

            class FakeClient:
                @staticmethod
                def request(method: str, params: dict[str, object], timeout: float) -> dict[str, object]:  # noqa: ARG004
                    return {
                        "thread": {
                            "id": "thread-worker",
                            "turns": [
                                {"id": "turn-worker", "status": "completed", "items": []},
                                {"id": "follow-on-turn", "status": "inProgress", "items": []},
                            ],
                        }
                    }

            cleanup = runtime._stop_bounded_turn_follow_on_execution(  # type: ignore[attr-defined]
                {"provider_id": "qwen", "model": "qwen3-coder-plus"},
                FakeClient(),
                thread_id="thread-worker",
                completed_turn_id="turn-worker",
            )
            active_after_cleanup = runtime._active_turn_execution_policy_for(  # type: ignore[attr-defined]
                {"threadId": "thread-worker", "turnId": "follow-on-turn"}
            )

            self.assertEqual(approval_before_cleanup, {"decision": "decline"})
            self.assertIsNotNone(active_before_cleanup)
            self.assertTrue(cleanup["goal_cleared"])
            self.assertEqual(cleanup["follow_on_turn_id"], "follow-on-turn")
            self.assertTrue(cleanup["follow_on_turn_interrupted"])
            self.assertEqual(interrupted, ["thread-worker:follow-on-turn"])
            self.assertIsNone(active_after_cleanup)

    def test_turn_aborted_notification_reconciles_as_cancelled_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Aborted turn", root / "aborted-turn.abproj", workspace_root=workspace)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._schedule_terminal_thread_snapshot = lambda **_payload: None  # type: ignore[method-assign]
            runtime._register_active_turn_execution_policy("thread-worker", "no_tools")  # type: ignore[attr-defined]
            runtime._record_execution_policy_started(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
                policy="no_tools",
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "turn/aborted",
                {
                    "threadId": "thread-worker",
                    "turn": {"id": "nested-runtime-turn", "status": "inProgress"},
                },
            )

            class FakeClient:
                @staticmethod
                def request(method: str, params: dict[str, object], timeout: float) -> dict[str, object]:  # noqa: ARG004
                    return {
                        "thread": {
                            "id": "thread-worker",
                            "turns": [{"id": "turn-worker", "status": "inProgress", "items": []}],
                        }
                    }

            terminal = runtime._wait_for_probe_turn_terminal(  # type: ignore[attr-defined]
                FakeClient(),
                thread_id="thread-worker",
                turn_id="turn-worker",
                timeout_seconds=5.0,
                operation_label="task graph node Planner",
            )
            status, _final_text, _reasoning = runtime._probe_turn_result(  # type: ignore[attr-defined]
                terminal,
                turn_id="turn-worker",
            )
            notification = runtime._terminal_turn_notification(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
            )

            self.assertEqual(status, "cancelled")
            self.assertIsNotNone(notification)
            self.assertEqual(notification["status"], "cancelled")
            self.assertEqual(notification["turn_id"], "turn-worker")
            self.assertIsNone(  # type: ignore[attr-defined]
                runtime._active_turn_execution_policy_for(
                    {"threadId": "thread-worker", "turnId": "nested-runtime-turn"}
                )
            )

    def test_instantiate_graph_template_defaults_graph_nodes_to_default_collaboration_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph defaults", root / "graph-defaults.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph defaults task")

            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            modes = {
                str(node.get("node_id") or ""): str(node.get("collaboration_mode") or "")
                for node in list(graph.get("nodes") or [])
                if isinstance(node, dict)
            }

            self.assertTrue(modes)
            self.assertTrue(all(mode == "default" for mode in modes.values()))

    def test_graph_worker_collaboration_mode_normalizes_plan_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph worker mode", root / "graph-worker-mode.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph worker mode task", thread_id="thread-parent")
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            for node in graph["nodes"]:
                if str(node.get("node_id") or "").strip() == "node_supervisor":
                    node["collaboration_mode"] = "plan"

            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            supervisor = next(node for node in graph["nodes"] if str(node.get("node_id") or "").strip() == "node_supervisor")

            self.assertEqual(runtime._normalize_graph_worker_collaboration_mode(supervisor), "default")  # type: ignore[attr-defined]
            self.assertEqual(runtime._normalize_graph_worker_collaboration_mode({"collaboration_mode": "default"}), "default")  # type: ignore[attr-defined]
            self.assertIsNone(runtime._normalize_graph_worker_collaboration_mode({}))  # type: ignore[attr-defined]

    def test_live_graph_preflight_blocks_all_dispatch_when_any_node_route_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph preflight", root / "graph-preflight.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph preflight task", thread_id="thread-parent")
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            for node in graph["nodes"]:
                node["human_summary_template"] = f"Return a bounded result for {node['label']}."
            graph["nodes"][-1]["provider_id"] = None
            tasks.save_graph_definition({"graph": graph})
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            tasks.dry_run_graph = lambda payload, profiles_snapshot=None, configured_models=None: {  # type: ignore[method-assign]  # noqa: ARG005
                "dry_run": {"overall_status": "pass", "graph_result": {"reasons": []}}
            }
            runtime._profiles.resolve_runtime_profile = lambda provider_id: {"provider_id": provider_id}  # type: ignore[method-assign]
            calls = {"worker": 0, "turn": 0}
            runtime.start_graph_worker = lambda profile, **payload: calls.__setitem__("worker", calls["worker"] + 1)  # type: ignore[method-assign]  # noqa: ARG005
            runtime.start_turn = lambda profile, **payload: calls.__setitem__("turn", calls["turn"] + 1)  # type: ignore[method-assign]  # noqa: ARG005

            with self.assertRaisesRegex(ValueError, "missing an explicit provider"):
                runtime.execute_task_graph_run(
                    {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 80000}}}
                )

            self.assertEqual(calls, {"worker": 0, "turn": 0})

    def test_live_graph_marks_completed_turn_failed_when_no_tools_policy_is_violated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph policy", root / "graph-policy.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph policy task", thread_id="thread-parent")
            graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
            for graph_node in graph["nodes"]:
                graph_node["human_summary_template"] = f"Return a bounded result for {graph_node['label']} without tools."
                graph_node["tools"] = {"approval_mode": "ask", "allowed_tool_classes": [], "supports_mcp": False}
            node = graph["nodes"][0]
            tasks.save_graph_definition({"graph": graph})
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            tasks.dry_run_graph = lambda payload, profiles_snapshot=None, configured_models=None: {  # type: ignore[method-assign]  # noqa: ARG005
                "dry_run": {"overall_status": "pass", "graph_result": {"reasons": []}}
            }
            runtime._profiles.resolve_runtime_profile = lambda provider_id: {  # type: ignore[method-assign]
                "profile_id": f"{provider_id}-default",
                "provider_id": provider_id,
                "model": "qwen3-coder-plus",
                "reasoning_effort": "medium",
            }

            def fake_start_worker(profile: dict[str, str], **payload: object) -> dict[str, object]:
                node_id = str(payload["node_id"])
                tasks.record_graph_worker(
                    {
                        "graph_id": str(payload["graph_id"]),
                        "run_id": str(payload["run_id"]),
                        "node_id": node_id,
                        "worker_thread_id": f"worker-{node_id}",
                        "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                        "spawn_mode": "isolated_lane",
                        "worker_origin": "provider_lane",
                        "agent_role": "artifact_source",
                        "agent_nickname": "Start Here",
                        "status": "ready",
                        "runtime_contract": {
                            "provider_id": profile["provider_id"],
                            "model": "qwen3-coder-plus",
                            "tool_policy": node["tools"],
                            "turn_execution_policy": "no_tools",
                        },
                    },
                    graph_definition=graph,
                )
                return {
                    "worker": {
                        "thread_id": f"worker-{node_id}",
                        "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                        "worker_origin": "provider_lane",
                        "spawn_mode": "isolated_lane",
                        "settings": {"execution_backend": "app_server"},
                    }
                }

            def fake_start_turn(profile: dict[str, str], **payload: object) -> dict[str, object]:  # noqa: ARG001
                self.assertEqual(payload.get("execution_policy"), "no_tools")
                node_id = str(payload.get("thread_id") or "").removeprefix("worker-")
                provider_thread_id = f"provider-{node_id}"
                turn_id = f"turn-{node_id}"
                runtime._record_event(  # type: ignore[attr-defined]
                    {
                        "type": "turn_execution_policy_tool_blocked",
                        "thread_id": provider_thread_id,
                        "turn_id": turn_id,
                        "policy": "no_tools",
                        "request_method": "item/commandExecution/requestApproval",
                        "tool_name": "shell_command",
                        "reason": "tool_not_declared_by_task_graph_node",
                        "compliant_success": False,
                    }
                )
                return {
                    "thread_id": provider_thread_id,
                    "turn": {"id": turn_id},
                }

            runtime.start_graph_worker = fake_start_worker  # type: ignore[method-assign]
            runtime.start_turn = fake_start_turn  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda profile, require_secret=False: {}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: object()  # type: ignore[method-assign]  # noqa: ARG005
            runtime._turn_execution_policy_violation = lambda **payload: {  # type: ignore[method-assign]  # noqa: ARG005
                "status": "violated",
                "policy": "no_tools",
                "blocked_tool_call_count": 1,
                "request_methods": ["item/commandExecution/requestApproval"],
                "tool_names": ["shell_command"],
                "item_types": [],
                "reason": "model_requested_tools_outside_task_graph_contract",
                "compliant_success": False,
            }
            runtime._wait_for_probe_turn_terminal = lambda client, **payload: {  # type: ignore[method-assign]  # noqa: ARG005
                "id": payload["thread_id"],
                "turns": [
                    {
                        "id": payload["turn_id"],
                        "status": "completed",
                        "items": [
                            {
                                "type": "agentMessage",
                                "text": "I want to inspect the workspace first.",
                            }
                        ],
                    }
                ],
            }

            result = runtime.execute_task_graph_run(
                {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 80000}}}
            )

            run_ref = result["live_run"]["run_ref"]
            self.assertEqual(result["live_run"]["run_status"], "failed")
            self.assertEqual(run_ref["node_status_counts"]["failed"], 1)
            binding = run_ref["worker_bindings"][0]
            self.assertEqual(binding["status"], "failed")
            self.assertIn("policy_violated", str(binding["output_summary"]["machine_result_preview"]))
            self.assertEqual(run_ref["metrics"]["tool_call_count"], 1)

    def test_live_graph_salvages_structured_response_after_no_tools_policy_violation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph policy salvage", root / "graph-policy-salvage.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph policy salvage task", thread_id="thread-parent")
            graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
            for graph_node in graph["nodes"]:
                graph_node["human_summary_template"] = f"Return a bounded result for {graph_node['label']} without tools."
                graph_node["tools"] = {"approval_mode": "ask", "allowed_tool_classes": [], "supports_mcp": False}
            node = graph["nodes"][0]
            tasks.save_graph_definition({"graph": graph})
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            tasks.dry_run_graph = lambda payload, profiles_snapshot=None, configured_models=None: {  # type: ignore[method-assign]  # noqa: ARG005
                "dry_run": {"overall_status": "pass", "graph_result": {"reasons": []}}
            }
            runtime._profiles.resolve_runtime_profile = lambda provider_id: {  # type: ignore[method-assign]
                "profile_id": f"{provider_id}-default",
                "provider_id": provider_id,
                "model": "qwen3-coder-plus",
                "reasoning_effort": "medium",
            }

            def fake_start_worker(profile: dict[str, str], **payload: object) -> dict[str, object]:
                node_id = str(payload["node_id"])
                tasks.record_graph_worker(
                    {
                        "graph_id": str(payload["graph_id"]),
                        "run_id": str(payload["run_id"]),
                        "node_id": node_id,
                        "worker_thread_id": f"worker-{node_id}",
                        "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                        "spawn_mode": "isolated_lane",
                        "worker_origin": "provider_lane",
                        "agent_role": "artifact_source",
                        "agent_nickname": "Start Here",
                        "status": "ready",
                        "runtime_contract": {
                            "provider_id": profile["provider_id"],
                            "model": "qwen3-coder-plus",
                            "tool_policy": node["tools"],
                            "turn_execution_policy": "no_tools",
                        },
                    },
                    graph_definition=graph,
                )
                return {
                    "worker": {
                        "thread_id": f"worker-{node_id}",
                        "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                        "worker_origin": "provider_lane",
                        "spawn_mode": "isolated_lane",
                        "settings": {"execution_backend": "app_server"},
                    }
                }

            def fake_start_turn(profile: dict[str, str], **payload: object) -> dict[str, object]:  # noqa: ARG001
                self.assertEqual(payload.get("execution_policy"), "no_tools")
                node_id = str(payload.get("thread_id") or "").removeprefix("worker-")
                provider_thread_id = f"provider-{node_id}"
                turn_id = f"turn-{node_id}"
                runtime._record_event(  # type: ignore[attr-defined]
                    {
                        "type": "turn_execution_policy_tool_blocked",
                        "thread_id": provider_thread_id,
                        "turn_id": turn_id,
                        "policy": "no_tools",
                        "request_method": "item/commandExecution/requestApproval",
                        "tool_name": "shell_command",
                        "reason": "tool_not_declared_by_task_graph_node",
                        "compliant_success": False,
                    }
                )
                return {
                    "thread_id": provider_thread_id,
                    "turn": {"id": turn_id},
                }

            runtime.start_graph_worker = fake_start_worker  # type: ignore[method-assign]
            runtime.start_turn = fake_start_turn  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda profile, require_secret=False: {}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: object()  # type: ignore[method-assign]  # noqa: ARG005
            runtime._turn_execution_policy_violation = lambda **payload: {  # type: ignore[method-assign]  # noqa: ARG005
                "status": "violated",
                "policy": "no_tools",
                "blocked_tool_call_count": 1,
                "request_methods": ["item/commandExecution/requestApproval"],
                "tool_names": ["shell_command"],
                "item_types": [],
                "reason": "model_requested_tools_outside_task_graph_contract",
                "compliant_success": False,
            }
            runtime._wait_for_probe_turn_terminal = lambda client, **payload: {  # type: ignore[method-assign]  # noqa: ARG005
                "id": payload["thread_id"],
                "turns": [
                    {
                        "id": payload["turn_id"],
                        "status": "completed",
                        "items": [
                            {
                                "type": "agentMessage",
                                "text": json.dumps(
                                    {
                                        "human_summary": "Recovered structured response.",
                                        "machine_result": {"status": "ok", "result": "bounded"},
                                    }
                                ),
                            }
                        ],
                    }
                ],
            }

            result = runtime.execute_task_graph_run(
                {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 80000}}}
            )

            run_ref = result["live_run"]["run_ref"]
            self.assertEqual(result["live_run"]["run_status"], "partial")
            self.assertEqual(run_ref["node_status_counts"]["completed"], 3)
            self.assertEqual(run_ref["node_outcome_counts"]["partial"], 3)
            binding = run_ref["worker_bindings"][0]
            self.assertEqual(binding["status"], "completed")
            self.assertIn("Recovered structured response.", str(binding["output_summary"]["human_summary"]))
            self.assertIn("structured-response fallback", " ".join(binding["output_summary"]["next_action_hints"]))
            self.assertEqual(run_ref["metrics"]["tool_call_count"], 1)

    def test_live_graph_usage_signal_uses_matching_turn_total(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph usage", root / "graph-usage.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph usage task")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._on_notification(  # type: ignore[attr-defined]
                "thread/tokenUsage/updated",
                {
                    "threadId": "thread-worker",
                    "turnId": "turn-worker",
                    "tokenUsage": {
                        "total": {
                            "inputTokens": 110,
                            "cachedInputTokens": 10,
                            "outputTokens": 30,
                            "reasoningOutputTokens": 5,
                            "totalTokens": 140,
                        },
                        "last": {"inputTokens": 110, "outputTokens": 30, "totalTokens": 140},
                        "modelContextWindow": 128000,
                    },
                },
            )

            signal = runtime._graph_live_turn_usage_signal(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-worker",
                provider_id="qwen",
                model="qwen3-coder-plus",
            )

            self.assertEqual(signal["status"], "available")
            self.assertEqual(signal["tokens"]["total_tokens"], 140)
            self.assertEqual(signal["tokens"]["reasoning_tokens"], 5)

    def test_live_graph_failure_reconciles_started_sibling_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph reconcile", root / "graph-reconcile.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph reconcile task")
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            dry_run = tasks.dry_run_graph({"graph_id": graph["graph_id"]})["dry_run"]
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            interrupted: list[tuple[str, str]] = []
            runtime._terminal_turn_notification = lambda **payload: {"status": "completed"}  # type: ignore[method-assign]
            runtime.interrupt_turn = lambda profile, thread_id, turn_id: interrupted.append((thread_id, turn_id)) or {"interrupt": {"ok": True}}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._prepare_runtime = lambda profile, require_secret=False: {}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: object()  # type: ignore[method-assign]  # noqa: ARG005
            runtime._wait_for_probe_turn_terminal = lambda client, **payload: {  # type: ignore[method-assign]  # noqa: ARG005
                "turns": [
                    {
                        "id": payload["turn_id"],
                        "status": "completed",
                        "items": [
                            {
                                "type": "agentMessage",
                                "text": json.dumps(
                                    {
                                        "human_summary": "Research Branch A recovered its bounded output.",
                                        "machine_result": {"branch": "A", "status": "completed"},
                                    }
                                ),
                            }
                        ],
                    }
                ]
            }
            runtime._graph_live_turn_usage_signal = lambda **payload: {"status": "not_available", "tokens": {}}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._turn_execution_policy_violation = lambda **payload: None  # type: ignore[method-assign]  # noqa: ARG005

            tasks.record_graph_worker(
                {
                    "graph_id": graph["graph_id"],
                    "run_id": dry_run["run_id"],
                    "node_id": "node_research_a",
                    "worker_thread_id": "thread-a",
                    "parent_thread_id": "thread-parent",
                    "spawn_mode": "isolated_lane",
                    "worker_origin": "provider_lane",
                    "agent_role": "worker",
                    "agent_nickname": "Research Branch A",
                    "status": "running",
                    "runtime_contract": {
                        "provider_id": "qwen",
                        "model": "qwen3-coder-plus",
                        "reasoning_effort": "medium",
                        "permission_mode": "auto",
                        "collaboration_mode": "default",
                        "execution_backend": "app_server",
                    },
                },
                graph_definition=graph,
            )

            node_states = {"node_research_a": {"status": "running", "outcome": "pending"}}
            event_refs: list[dict[str, object]] = []
            artifact_refs: list[dict[str, object]] = []

            records = runtime._reconcile_graph_live_started_turns(  # type: ignore[attr-defined]
                graph=graph,
                run_id=dry_run["run_id"],
                started_executions=[
                    {
                        "node_id": "node_research_a",
                        "graph_node": next(item for item in graph["nodes"] if item["node_id"] == "node_research_a"),
                        "execution_thread_id": "thread-a",
                        "turn_id": "turn-a",
                        "profile": {"provider_id": "qwen"},
                        "worker": {
                            "thread_id": "thread-a",
                            "parent_thread_id": "thread-parent",
                            "worker_origin": "provider_lane",
                            "spawn_mode": "isolated_lane",
                            "agent_role": "worker",
                            "agent_nickname": "Research Branch A",
                        },
                        "started_monotonic": time.monotonic() - 1.0,
                    }
                ],
                settled_execution_keys=set(),
                node_states=node_states,
                event_refs=event_refs,
                artifact_refs=artifact_refs,
            )

            self.assertEqual(interrupted, [])
            self.assertEqual(records[0]["status"], "terminal_result_committed")
            self.assertEqual(records[0]["terminal_status"], "completed")
            self.assertEqual(node_states["node_research_a"]["status"], "completed")
            event_types = [str(item.get("event_type") or "") for item in event_refs]
            self.assertIn("turn_reconciled", event_types)
            self.assertIn("node_completed", event_types)
            run_ref = tasks.graph_run_ref(dry_run["run_id"])
            self.assertIsNotNone(run_ref)
            binding = next(
                item
                for item in list((run_ref or {}).get("worker_bindings") or [])
                if str(item.get("node_id") or "") == "node_research_a"
            )
            self.assertEqual(str(binding.get("status") or ""), "completed")
            output_summary = dict(binding.get("output_summary") or {})
            output_bundle_path = workspace / str(output_summary.get("artifact_bundle_path") or "")
            self.assertTrue(output_bundle_path.exists())
            output_payload = json.loads(output_bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(output_payload["human_summary"], "Research Branch A recovered its bounded output.")
            self.assertTrue(any(str(item.get("path") or "").endswith("/output.json") for item in artifact_refs))

    def test_reconcile_graph_live_started_turns_commits_terminal_output_after_interrupt_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph reconcile recovery", root / "graph-reconcile-recovery.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph reconcile recovery task")
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            dry_run = tasks.dry_run_graph({"graph_id": graph["graph_id"]})["dry_run"]
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            wait_calls: list[str] = []

            def fail_interrupt(profile: dict[str, object], thread_id: str, turn_id: str) -> dict[str, object]:  # noqa: ARG001
                raise TimeoutError("Timed out waiting for app-server response: turn/interrupt")

            def recover_terminal_thread(client: object, **payload: object) -> dict[str, object]:  # noqa: ARG001
                wait_calls.append(str(payload["operation_label"]))
                return {
                    "turns": [
                        {
                            "id": payload["turn_id"],
                            "status": "completed",
                            "items": [
                                {
                                    "type": "agentMessage",
                                    "text": json.dumps(
                                        {
                                            "human_summary": "Research Branch A completed before cancellation could be confirmed.",
                                            "machine_result": {"branch": "A", "status": "completed"},
                                        }
                                    ),
                                }
                            ],
                        }
                    ]
                }

            runtime.interrupt_turn = fail_interrupt  # type: ignore[method-assign]
            runtime._terminal_turn_notification = lambda **payload: None  # type: ignore[method-assign]  # noqa: ARG005
            runtime._prepare_runtime = lambda profile, require_secret=False: {}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: object()  # type: ignore[method-assign]  # noqa: ARG005
            runtime._wait_for_probe_turn_terminal = recover_terminal_thread  # type: ignore[method-assign]
            runtime._graph_live_turn_usage_signal = lambda **payload: {"status": "not_available", "tokens": {}}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._turn_execution_policy_violation = lambda **payload: None  # type: ignore[method-assign]  # noqa: ARG005

            tasks.record_graph_worker(
                {
                    "graph_id": graph["graph_id"],
                    "run_id": dry_run["run_id"],
                    "node_id": "node_research_a",
                    "worker_thread_id": "thread-a",
                    "parent_thread_id": "thread-parent",
                    "spawn_mode": "isolated_lane",
                    "worker_origin": "provider_lane",
                    "agent_role": "worker",
                    "agent_nickname": "Research Branch A",
                    "status": "running",
                    "runtime_contract": {
                        "provider_id": "qwen",
                        "model": "qwen3-coder-plus",
                        "reasoning_effort": "medium",
                        "permission_mode": "auto",
                        "collaboration_mode": "default",
                        "execution_backend": "app_server",
                    },
                },
                graph_definition=graph,
            )

            node_states = {"node_research_a": {"status": "running", "outcome": "pending"}}
            event_refs: list[dict[str, object]] = []
            artifact_refs: list[dict[str, object]] = []

            records = runtime._reconcile_graph_live_started_turns(  # type: ignore[attr-defined]
                graph=graph,
                run_id=dry_run["run_id"],
                started_executions=[
                    {
                        "node_id": "node_research_a",
                        "graph_node": next(item for item in graph["nodes"] if item["node_id"] == "node_research_a"),
                        "execution_thread_id": "thread-a",
                        "turn_id": "turn-a",
                        "profile": {"provider_id": "qwen"},
                        "worker": {
                            "thread_id": "thread-a",
                            "parent_thread_id": "thread-parent",
                            "worker_origin": "provider_lane",
                            "spawn_mode": "isolated_lane",
                            "agent_role": "worker",
                            "agent_nickname": "Research Branch A",
                        },
                        "started_monotonic": time.monotonic() - 1.0,
                    }
                ],
                settled_execution_keys=set(),
                node_states=node_states,
                event_refs=event_refs,
                artifact_refs=artifact_refs,
            )

            self.assertEqual(records[0]["status"], "terminal_result_committed_after_reconcile_error")
            self.assertEqual(records[0]["terminal_status"], "completed")
            self.assertEqual(records[0]["recovery_error_type"], "TimeoutError")
            self.assertEqual(node_states["node_research_a"]["status"], "completed")
            self.assertTrue(any("task graph recovery" in label for label in wait_calls))
            run_ref = tasks.graph_run_ref(dry_run["run_id"])
            self.assertIsNotNone(run_ref)
            binding = next(
                item
                for item in list((run_ref or {}).get("worker_bindings") or [])
                if str(item.get("node_id") or "") == "node_research_a"
            )
            self.assertEqual(str(binding.get("status") or ""), "completed")

    def test_terminal_notification_reconciles_nested_turn_id_with_stale_thread_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Terminal notification", root / "terminal-notification.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Terminal notification task", thread_id="thread-parent")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._schedule_terminal_thread_snapshot = lambda **_payload: None  # type: ignore[method-assign]

            class FakeClient:
                def request(self, method: str, params: dict[str, object], timeout: float) -> dict[str, object]:  # noqa: ARG002
                    self.assert_request(method, params)
                    return {
                        "thread": {
                            "id": "thread-worker",
                            "turns": [
                                {
                                    "id": "turn-worker",
                                    "status": "inProgress",
                                    "items": [
                                        {
                                            "type": "agentMessage",
                                            "text": json.dumps(
                                                {
                                                    "human_summary": "Planner completed.",
                                                    "machine_result": {"next_workers": ["docs", "api", "ui"]},
                                                }
                                            ),
                                        }
                                    ],
                                }
                            ],
                        }
                    }

                @staticmethod
                def assert_request(method: str, params: dict[str, object]) -> None:
                    if method != "thread/read" or params.get("threadId") != "thread-worker":
                        raise AssertionError(f"unexpected request: {method} {params}")

            runtime._on_notification(  # type: ignore[attr-defined]
                "turn/completed",
                {
                    "threadId": "thread-worker",
                    "turn": {
                        "id": "turn-worker",
                        "status": "completed",
                        "items": [],
                        "itemsView": "notLoaded",
                        "completedAt": 123,
                    },
                },
            )

            terminal = runtime._wait_for_probe_turn_terminal(  # type: ignore[attr-defined]
                FakeClient(),
                thread_id="thread-worker",
                turn_id="turn-worker",
                timeout_seconds=5.0,
                operation_label="task graph node Planner",
            )
            status, final_text, _reasoning = runtime._probe_turn_result(terminal, turn_id="turn-worker")  # type: ignore[attr-defined]

            self.assertEqual(status, "completed")
            self.assertIn("Planner completed", final_text)
            notification = runtime._terminal_turn_notification(thread_id="thread-worker", turn_id="turn-worker")  # type: ignore[attr-defined]
            self.assertIsNotNone(notification)
            self.assertEqual(notification["turn_id"], "turn-worker")
            self.assertTrue(
                any(
                    item.get("type") == "runtime_turn_terminal_notification_reconciled"
                    for item in runtime.list_events()["events"]
                )
            )

    def test_wait_for_probe_turn_terminal_recovers_after_thread_read_timeout_when_terminal_notification_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project(
                "Graph notification recovery",
                root / "graph-notification-recovery.abproj",
                workspace_root=workspace,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))

            class FakeClient:
                def request(self, method: str, params: dict[str, object], timeout: float) -> dict[str, object]:  # noqa: ARG002
                    if method != "thread/read" or params.get("threadId") != "thread-worker":
                        raise AssertionError(f"unexpected request: {method} {params}")
                    raise TimeoutError("Timed out waiting for app-server response: thread/read")

            runtime._cache_thread_entry(  # type: ignore[attr-defined]
                "thread-worker",
                {
                    "thread": {
                        "id": "thread-worker",
                        "turns": [
                            {
                                "id": "turn-worker",
                                "status": "inProgress",
                                "items": [
                                    {
                                        "type": "agentMessage",
                                        "text": json.dumps(
                                            {
                                                "human_summary": "Recovered after read timeout.",
                                                "machine_result": {"status": "ok"},
                                            }
                                        ),
                                    }
                                ],
                            }
                        ],
                    }
                },
            )

            runtime._on_notification(  # type: ignore[attr-defined]
                "turn/completed",
                {
                    "threadId": "thread-worker",
                    "turn": {
                        "id": "turn-worker",
                        "status": "completed",
                        "items": [],
                        "itemsView": "notLoaded",
                        "completedAt": 456,
                    },
                },
            )

            terminal = runtime._wait_for_probe_turn_terminal(  # type: ignore[attr-defined]
                FakeClient(),
                thread_id="thread-worker",
                turn_id="turn-worker",
                timeout_seconds=5.0,
                operation_label="task graph node Planner",
            )
            status, final_text, _reasoning = runtime._probe_turn_result(terminal, turn_id="turn-worker")  # type: ignore[attr-defined]

            self.assertEqual(status, "completed")
            self.assertIn("Recovered after read timeout", final_text)
            reconciled_events = [
                item
                for item in runtime.list_events()["events"]
                if item.get("type") == "runtime_turn_terminal_notification_reconciled"
            ]
            self.assertTrue(reconciled_events)
            self.assertEqual(
                str(reconciled_events[-1].get("thread_read_error_type") or ""),
                "TimeoutError",
            )

    def test_wait_for_probe_turn_terminal_prefers_richer_cached_snapshot_over_empty_terminal_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project(
                "Graph richer terminal snapshot",
                root / "graph-richer-terminal.abproj",
                workspace_root=workspace,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))

            class FakeClient:
                def request(self, method: str, params: dict[str, object], timeout: float) -> dict[str, object]:  # noqa: ARG002
                    if method != "thread/read" or params.get("threadId") != "thread-worker":
                        raise AssertionError(f"unexpected request: {method} {params}")
                    return {
                        "thread": {
                            "id": "thread-worker",
                            "turns": [
                                {
                                    "id": "turn-worker",
                                    "status": "completed",
                                    "items": [],
                                    "itemsView": "notLoaded",
                                }
                            ],
                        }
                    }

            runtime._read_native_thread = lambda thread_id: {  # type: ignore[method-assign]
                "id": thread_id,
                "turns": [
                    {
                        "id": "turn-worker",
                        "status": "completed",
                        "items": [
                            {
                                "type": "agentMessage",
                                "text": json.dumps(
                                    {
                                        "human_summary": "Recovered from the richer cached snapshot.",
                                        "machine_result": {"status": "ok"},
                                    }
                                ),
                            }
                        ],
                    }
                ],
            }

            terminal = runtime._wait_for_probe_turn_terminal(  # type: ignore[attr-defined]
                FakeClient(),
                thread_id="thread-worker",
                turn_id="turn-worker",
                timeout_seconds=5.0,
                operation_label="task graph node Planner",
            )
            status, final_text, _reasoning = runtime._probe_turn_result(terminal, turn_id="turn-worker")  # type: ignore[attr-defined]

            self.assertEqual(status, "completed")
            self.assertIn("Recovered from the richer cached snapshot", final_text)

    def test_wait_for_probe_turn_terminal_recovers_when_follow_on_turn_hides_target_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project(
                "Graph follow-on recovery",
                root / "graph-follow-on-recovery.abproj",
                workspace_root=workspace,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))

            class FakeClient:
                def request(self, method: str, params: dict[str, object], timeout: float) -> dict[str, object]:  # noqa: ARG002
                    if method != "thread/read" or params.get("threadId") != "thread-worker":
                        raise AssertionError(f"unexpected request: {method} {params}")
                    return {
                        "thread": {
                            "id": "thread-worker",
                            "turns": [
                                {
                                    "id": "turn-follow-on",
                                    "status": "inProgress",
                                    "items": [],
                                }
                            ],
                        }
                    }

            runtime._cache_thread_entry(  # type: ignore[attr-defined]
                "thread-worker",
                {
                    "thread": {
                        "id": "thread-worker",
                        "turns": [
                            {
                                "id": "turn-worker",
                                "status": "completed",
                                "items": [
                                    {
                                        "type": "agentMessage",
                                        "text": json.dumps(
                                            {
                                                "human_summary": "Planner completed before the follow-on turn started.",
                                                "machine_result": {"status": "ok", "next": ["worker-a", "worker-b"]},
                                            }
                                        ),
                                    }
                                ],
                            }
                        ],
                    }
                },
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "turn/completed",
                {
                    "threadId": "thread-worker",
                    "turn": {
                        "id": "turn-worker",
                        "status": "completed",
                        "items": [],
                        "itemsView": "notLoaded",
                        "completedAt": 789,
                    },
                },
            )

            terminal = runtime._wait_for_probe_turn_terminal(  # type: ignore[attr-defined]
                FakeClient(),
                thread_id="thread-worker",
                turn_id="turn-worker",
                timeout_seconds=5.0,
                operation_label="task graph node Planner",
            )
            status, final_text, _reasoning = runtime._probe_turn_result(terminal, turn_id="turn-worker")  # type: ignore[attr-defined]

            self.assertEqual(status, "completed")
            self.assertIn("Planner completed before the follow-on turn started", final_text)
            reconciled_events = [
                item
                for item in runtime.list_events()["events"]
                if item.get("type") == "runtime_turn_terminal_notification_reconciled"
            ]
            self.assertTrue(reconciled_events)

    def test_wait_for_probe_turn_terminal_maps_observed_completed_turn_onto_target_turn_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project(
                "Graph observed turn recovery",
                root / "graph-observed-turn-recovery.abproj",
                workspace_root=workspace,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))

            class FakeClient:
                def request(self, method: str, params: dict[str, object], timeout: float) -> dict[str, object]:  # noqa: ARG002
                    if method != "thread/read" or params.get("threadId") != "thread-worker":
                        raise AssertionError(f"unexpected request: {method} {params}")
                    return {
                        "thread": {
                            "id": "thread-worker",
                            "turns": [
                                {
                                    "id": "turn-follow-on",
                                    "status": "inProgress",
                                    "items": [],
                                }
                            ],
                        }
                    }

            runtime._cache_thread_entry(  # type: ignore[attr-defined]
                "thread-worker",
                {
                    "thread": {
                        "id": "thread-worker",
                        "turns": [
                            {
                                "id": "turn-observed",
                                "status": "completed",
                                "items": [
                                    {
                                        "type": "agentMessage",
                                        "text": json.dumps(
                                            {
                                                "human_summary": "Planner returned a bounded JSON result.",
                                                "machine_result": {"status": "ok", "next_workers": ["worker-a"]},
                                            }
                                        ),
                                    }
                                ],
                            }
                        ],
                    }
                },
            )
            runtime._register_active_turn_execution_policy("thread-worker", "no_tools")  # type: ignore[attr-defined]
            runtime._record_execution_policy_started(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-target",
                policy="no_tools",
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "turn/completed",
                {
                    "threadId": "thread-worker",
                    "turn": {
                        "id": "turn-observed",
                        "status": "completed",
                        "items": [],
                        "itemsView": "notLoaded",
                        "completedAt": 789,
                    },
                },
            )

            terminal = runtime._wait_for_probe_turn_terminal(  # type: ignore[attr-defined]
                FakeClient(),
                thread_id="thread-worker",
                turn_id="turn-target",
                timeout_seconds=5.0,
                operation_label="task graph node Planner",
            )
            status, final_text, _reasoning = runtime._probe_turn_result(terminal, turn_id="turn-target")  # type: ignore[attr-defined]

            self.assertEqual(status, "completed")
            self.assertIn("Planner returned a bounded JSON result", final_text)
            mapped_turn = next(
                item
                for item in list(terminal.get("turns") or [])
                if isinstance(item, dict) and str(item.get("id") or "") == "turn-target"
            )
            self.assertEqual(str(mapped_turn.get("observedTurnId") or ""), "turn-observed")

    def test_wait_for_probe_turn_terminal_prefers_prior_completed_turn_over_follow_on_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project(
                "Graph prior completed turn recovery",
                root / "graph-prior-completed-turn-recovery.abproj",
                workspace_root=workspace,
            )

            transcript_thread = {
                "id": "thread-worker",
                "turns": [
                    {
                        "id": "turn-planner-json",
                        "status": "completed",
                        "startedAt": 100,
                        "completedAt": 150,
                        "items": [
                            {
                                "type": "agentMessage",
                                "text": json.dumps(
                                    {
                                        "human_summary": "Planner emitted the bounded JSON handoff.",
                                        "machine_result": {"status": "ok", "next_workers": ["worker-a"]},
                                    }
                                ),
                            }
                        ],
                    },
                    {
                        "id": "turn-follow-on",
                        "status": "completed",
                        "startedAt": 150,
                        "completedAt": 220,
                        "items": [
                            {
                                "type": "agentMessage",
                                "text": "The planner already completed its bounded task. Waiting for worker outputs.",
                            }
                        ],
                    },
                ],
            }
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                task_conversation=type(
                    "TranscriptStub",
                    (),
                    {"thread_snapshot": staticmethod(lambda thread_id: transcript_thread if thread_id == "thread-worker" else None)},
                )(),
            )

            class FakeClient:
                def request(self, method: str, params: dict[str, object], timeout: float) -> dict[str, object]:  # noqa: ARG002
                    if method != "thread/read" or params.get("threadId") != "thread-worker":
                        raise AssertionError(f"unexpected request: {method} {params}")
                    return {
                        "thread": {
                            "id": "thread-worker",
                            "turns": [
                                {
                                    "id": "turn-follow-on",
                                    "status": "completed",
                                    "items": [],
                                    "itemsView": "notLoaded",
                                    "startedAt": 150,
                                    "completedAt": 220,
                                }
                            ],
                        }
                    }

            runtime._register_active_turn_execution_policy("thread-worker", "no_tools")  # type: ignore[attr-defined]
            runtime._record_execution_policy_started(  # type: ignore[attr-defined]
                thread_id="thread-worker",
                turn_id="turn-target",
                policy="no_tools",
            )
            runtime._on_notification(  # type: ignore[attr-defined]
                "turn/completed",
                {
                    "threadId": "thread-worker",
                    "turn": {
                        "id": "turn-follow-on",
                        "status": "completed",
                        "items": [],
                        "itemsView": "notLoaded",
                        "startedAt": 150,
                        "completedAt": 220,
                    },
                },
            )

            terminal = runtime._wait_for_probe_turn_terminal(  # type: ignore[attr-defined]
                FakeClient(),
                thread_id="thread-worker",
                turn_id="turn-target",
                timeout_seconds=5.0,
                operation_label="task graph node Planner",
            )
            status, final_text, _reasoning = runtime._probe_turn_result(terminal, turn_id="turn-target")  # type: ignore[attr-defined]

            self.assertEqual(status, "completed")
            self.assertIn("Planner emitted the bounded JSON handoff", final_text)
            mapped_turn = next(
                item
                for item in list(terminal.get("turns") or [])
                if isinstance(item, dict) and str(item.get("id") or "") == "turn-target"
            )
            self.assertEqual(str(mapped_turn.get("observedTurnId") or ""), "turn-follow-on")
            self.assertEqual(str(mapped_turn.get("recoveredFromTurnId") or ""), "turn-planner-json")

    def test_read_native_thread_falls_back_to_task_transcript_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Thread snapshot fallback", root / "thread-snapshot-fallback.abproj", workspace_root=workspace)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._task_conversation = type(  # type: ignore[attr-defined]
                "TranscriptStub",
                (),
                {
                    "thread_snapshot": staticmethod(
                        lambda thread_id: {
                            "id": thread_id,
                            "name": "Worker Thread",
                            "status": {"type": "idle"},
                            "turns": [
                                {
                                    "id": "turn-worker",
                                    "status": "completed",
                                    "items": [
                                        {
                                            "type": "agentMessage",
                                            "text": '{"human_summary":"From transcript","machine_result":{"status":"ok"}}',
                                        }
                                    ],
                                }
                            ],
                        }
                    )
                },
            )()

            native = runtime._read_native_thread("thread-worker")  # type: ignore[attr-defined]

            self.assertIsNotNone(native)
            self.assertEqual(str(native.get("id") or ""), "thread-worker")
            turns = [item for item in list(native.get("turns") or []) if isinstance(item, dict)]
            self.assertEqual(len(turns), 1)
            self.assertEqual(str(turns[0].get("id") or ""), "turn-worker")

    def test_live_graph_clears_bounded_goal_and_interrupts_follow_on_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph follow-on cleanup", root / "graph-follow-on-cleanup.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph follow-on cleanup task", thread_id="thread-parent")
            graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
            graph["nodes"][0]["label"] = "Planner"
            graph["nodes"][0]["human_summary_template"] = "Return a bounded planner result."
            graph["nodes"][0]["provider_id"] = "qwen"
            graph["nodes"][0]["model_id"] = "qwen3-coder-plus"
            graph["nodes"][0]["reasoning_effort"] = "medium"
            graph["nodes"][0]["tools"] = {"approval_mode": "ask", "allowed_tool_classes": [], "supports_mcp": False}
            tasks.save_graph_definition({"graph": graph})
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            tasks.dry_run_graph = lambda payload, profiles_snapshot=None, configured_models=None: {  # type: ignore[method-assign]  # noqa: ARG005
                "dry_run": {"overall_status": "pass", "graph_result": {"reasons": []}}
            }
            runtime._profiles.resolve_runtime_profile = lambda provider_id: {  # type: ignore[method-assign]
                "profile_id": f"{provider_id}-default",
                "provider_id": provider_id,
                "model": "qwen3-coder-plus",
                "reasoning_effort": "medium",
            }

            def fake_start_worker(profile: dict[str, str], **payload: object) -> dict[str, object]:
                node_id = str(payload["node_id"])
                tasks.record_graph_worker(
                    {
                        "graph_id": str(payload["graph_id"]),
                        "run_id": str(payload["run_id"]),
                        "node_id": node_id,
                        "worker_thread_id": f"worker-{node_id}",
                        "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                        "spawn_mode": "isolated_lane",
                        "worker_origin": "provider_lane",
                        "agent_role": "planner",
                        "agent_nickname": "Planner",
                        "status": "ready",
                        "runtime_contract": {
                            "provider_id": profile["provider_id"],
                            "model": "qwen3-coder-plus",
                            "tool_policy": graph["nodes"][0]["tools"],
                            "turn_execution_policy": "no_tools",
                        },
                    },
                    graph_definition=graph,
                )
                return {
                    "worker": {
                        "thread_id": f"worker-{node_id}",
                        "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                        "worker_origin": "provider_lane",
                        "spawn_mode": "isolated_lane",
                        "settings": {"execution_backend": "app_server"},
                    }
                }

            runtime.start_graph_worker = fake_start_worker  # type: ignore[method-assign]
            runtime.start_turn = lambda profile, **payload: {  # type: ignore[method-assign]  # noqa: ARG005
                "thread_id": "provider-node_start_here",
                "turn": {"id": "turn-node-start-here"},
            }
            runtime._prepare_runtime = lambda profile, require_secret=False: {}  # type: ignore[method-assign]  # noqa: ARG005

            cleared_threads: list[str] = []

            class FakeClient:
                def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:  # noqa: ARG002
                    if method == "thread/goal/clear":
                        cleared_threads.append(str(params.get("threadId") or ""))
                        return {"ok": True}
                    if method == "thread/read":
                        return {
                            "thread": {
                                "id": "provider-node_start_here",
                                "turns": [
                                    {
                                        "id": "turn-follow-on",
                                        "status": "inProgress",
                                        "items": [],
                                    }
                                ],
                            }
                        }
                    raise AssertionError(f"unexpected request: {method} {params}")

            fake_client = FakeClient()
            runtime._ensure_client = lambda runtime_status: fake_client  # type: ignore[method-assign]  # noqa: ARG005
            runtime._wait_for_probe_turn_terminal = lambda client, **payload: {  # type: ignore[method-assign]  # noqa: ARG005
                "id": payload["thread_id"],
                "turns": [
                    {
                        "id": payload["turn_id"],
                        "status": "completed",
                        "items": [
                            {
                                "type": "agentMessage",
                                "text": json.dumps(
                                    {
                                        "human_summary": "Planner completed.",
                                        "machine_result": {"status": "ok"},
                                    }
                                ),
                            }
                        ],
                    }
                ],
            }
            runtime._graph_live_turn_usage_signal = lambda **payload: {"status": "not_available", "tokens": {}}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._turn_execution_policy_violation = lambda **payload: None  # type: ignore[method-assign]  # noqa: ARG005
            interrupted: list[tuple[str, str]] = []
            runtime.interrupt_turn = lambda profile, thread_id, turn_id: interrupted.append((thread_id, turn_id)) or {"interrupt": {"ok": True}}  # type: ignore[method-assign]  # noqa: ARG005

            result = runtime.execute_task_graph_run(
                {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 80000}}}
            )

            self.assertEqual(result["live_run"]["run_status"], "completed")
            self.assertEqual(cleared_threads, ["provider-node_start_here"])
            self.assertEqual(interrupted, [("provider-node_start_here", "turn-follow-on")])

    def test_live_graph_timeout_persists_failed_terminal_state_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph timeout", root / "graph-timeout.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Graph timeout task",
                thread_id="thread-parent",
                settings={"profile_id": "qwen-default", "provider_id": "qwen", "model": "qwen3-coder-plus"},
            )
            graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
            graph["nodes"][0]["human_summary_template"] = "Return a bounded timeout-test result."
            tasks.save_graph_definition({"graph": graph})
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            tasks.dry_run_graph = lambda payload, profiles_snapshot=None, configured_models=None: {  # type: ignore[method-assign]  # noqa: ARG005
                "dry_run": {"overall_status": "pass", "graph_result": {"reasons": []}}
            }
            runtime._profiles.resolve_runtime_profile = lambda provider_id: {  # type: ignore[method-assign]
                "profile_id": f"{provider_id}-default",
                "provider_id": provider_id,
                "model": "qwen3-coder-plus",
                "reasoning_effort": "medium",
            }
            runtime.start_graph_worker = lambda profile, **payload: {  # type: ignore[method-assign]  # noqa: ARG005
                "worker": {
                    "thread_id": f"thread-{payload['node_id']}",
                    "parent_thread_id": payload.get("parent_thread_id"),
                    "graph_id": payload["graph_id"],
                    "run_id": payload["run_id"],
                    "node_id": payload["node_id"],
                    "spawn_mode": "inline_lane",
                    "worker_origin": "provider_lane",
                    "settings": {"execution_backend": "app_server"},
                }
            }
            runtime.start_turn = lambda profile, **payload: {"turn": {"id": "turn-timeout"}}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: object()  # type: ignore[method-assign]  # noqa: ARG005

            def fail_wait(
                client: object,
                *,
                thread_id: str,
                turn_id: str,
                timeout_seconds: float,
                operation_label: str,
            ) -> dict[str, object]:  # noqa: ARG001
                raise TimeoutError(f"Timed out waiting for {operation_label} to reach a terminal state.")

            runtime._wait_for_probe_turn_terminal = fail_wait  # type: ignore[method-assign]

            with self.assertRaisesRegex(TimeoutError, "task graph node Start Here") as exc_info:
                runtime.execute_task_graph_run(
                    {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 80000}}}
                )

            public_payload = getattr(exc_info.exception, "public_payload", None)
            self.assertIsInstance(public_payload, dict)
            self.assertEqual(
                str(((public_payload or {}).get("live_run") or {}).get("run_status") or ""),
                "failed",
            )
            self.assertEqual(
                str(
                    ((((public_payload or {}).get("live_run") or {}).get("run_ref") or {}).get("status"))
                    or ""
                ),
                "failed",
            )
            self.assertEqual(
                str((((public_payload or {}).get("task") or {}).get("graph_activity_summary") or {}).get("latest_run_status") or ""),
                "failed",
            )

            live_refs = [
                item
                for item in list(tasks.current_task().get("graph_run_refs") or [])
                if str(item.get("run_id") or "").startswith("graph-run-live-")
            ]
            self.assertEqual(len(live_refs), 1)
            failed_ref = live_refs[0]
            self.assertEqual(failed_ref["status"], "failed")
            self.assertEqual(failed_ref["latest_event_type"], "run_failed")
            self.assertEqual(failed_ref["node_status_counts"]["failed"], 1)
            self.assertTrue(any(item["event_type"] == "node_failed" for item in failed_ref["timeline_events"]))
            failure_ref = next(
                item for item in failed_ref["artifact_refs"] if str(item.get("path") or "").endswith("/failure.json")
            )
            failure_payload = json.loads((workspace / failure_ref["path"]).read_text(encoding="utf-8"))
            self.assertEqual(failure_payload["failure_kind"], "terminal_collection_timeout")
            self.assertEqual(failure_payload["active_node_id"], "node_start_here")
            self.assertTrue((workspace / str(failure_ref["path"])).exists())
            self.assertTrue(
                any(str(item.get("path") or "").endswith("/report.md") for item in failed_ref["artifact_refs"])
            )

    def test_execute_task_graph_run_dispatches_parallel_fanout_and_persists_live_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph live runtime", root / "graph-live-runtime.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Graph live runtime task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "medium",
                },
            )
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            for node in graph["nodes"]:
                node["human_summary_template"] = f"Return the bounded result for {node['label']}."
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)

            dry_run_ref = tasks.dry_run_graph({"graph_id": graph["graph_id"]})["dry_run"]["run_ref"]
            tasks.current_task()["graph_run_refs"] = [dry_run_ref]

            dispatch_order: list[str] = []
            wait_order: list[str] = []
            wait_thread_ids: dict[str, str] = {}
            collaboration_modes: dict[str, str | None] = {}
            execution_policies: dict[str, str | None] = {}
            live_run_manifest_path: Path | None = None
            manifest_seen_after_supervisor = False

            for node in graph["nodes"]:
                if str(node.get("node_id") or "").strip() in {"node_supervisor", "node_merge"}:
                    node["collaboration_mode"] = "plan"
            tasks.save_graph_definition({"graph": graph})

            runtime._profiles.resolve_runtime_profile = lambda provider_id: {  # type: ignore[method-assign]
                "profile_id": f"{provider_id}-default",
                "provider_id": provider_id,
                "model": "qwen3-coder-plus" if provider_id == "qwen" else "kimi-k2.6",
                "reasoning_effort": "medium",
            }
            tasks.dry_run_graph = lambda payload, profiles_snapshot=None, configured_models=None: {  # type: ignore[method-assign]  # noqa: ARG005
                "dry_run": {
                    "overall_status": "pass",
                    "graph_result": {"reasons": []},
                }
            }

            def fake_start_graph_worker(profile: dict[str, str], **payload: object) -> dict[str, object]:
                node_id = str(payload.get("node_id") or "")
                nonlocal live_run_manifest_path
                dispatch_order.append(f"worker:{node_id}")
                spawn_mode = str(dict(next(item for item in graph["nodes"] if item["node_id"] == node_id).get("execution_policy") or {}).get("spawn_mode") or "isolated_lane")
                worker_origin = "codex_subagent" if spawn_mode == "subagent_worker" else "provider_lane"
                if live_run_manifest_path is None:
                    live_run_manifest_path = (
                        workspace
                        / "PRIVATE"
                        / "task-graph"
                        / "live-run"
                        / str(payload.get("run_id") or "")
                        / "run-manifest.json"
                    )
                tasks.record_graph_worker(
                    {
                        "graph_id": str(payload.get("graph_id") or ""),
                        "run_id": str(payload.get("run_id") or ""),
                        "node_id": node_id,
                        "worker_thread_id": f"thread-{node_id}",
                        "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                        "spawn_mode": spawn_mode,
                        "worker_origin": worker_origin,
                        "agent_role": str(next(item for item in graph["nodes"] if item["node_id"] == node_id).get("kind") or "worker"),
                        "agent_nickname": str(next(item for item in graph["nodes"] if item["node_id"] == node_id).get("label") or node_id),
                        "status": "ready",
                        "runtime_contract": {
                            "profile_id": str(profile.get("profile_id") or ""),
                            "provider_id": str(profile.get("provider_id") or ""),
                            "model": str(payload.get("model") or profile.get("model") or ""),
                            "reasoning_effort": str(payload.get("effort") or profile.get("reasoning_effort") or ""),
                            "permission_mode": str(payload.get("permission_mode") or "auto"),
                            "collaboration_mode": "default",
                            "execution_backend": "app_server",
                            "spawn_mode": spawn_mode,
                            "timeout_ms": 180000,
                            "tool_policy": {"approval_mode": "ask", "allowed_tool_classes": ["read_file", "web"], "supports_mcp": False},
                        },
                    },
                    graph_definition=graph,
                )
                return {
                    "worker": {
                        "thread_id": f"thread-{node_id}",
                        "parent_thread_id": str(payload.get("parent_thread_id") or ""),
                        "graph_id": str(payload.get("graph_id") or ""),
                        "run_id": str(payload.get("run_id") or ""),
                        "node_id": node_id,
                        "spawn_mode": spawn_mode,
                        "worker_origin": worker_origin,
                        "agent_role": str(next(item for item in graph["nodes"] if item["node_id"] == node_id).get("kind") or "worker"),
                        "agent_nickname": str(next(item for item in graph["nodes"] if item["node_id"] == node_id).get("label") or node_id),
                        "settings": {"execution_backend": "app_server"},
                    }
                }

            def fake_start_turn(profile: dict[str, str], **payload: object) -> dict[str, object]:  # noqa: ARG001
                thread_id = str(payload.get("thread_id") or "")
                node_id = thread_id.replace("thread-", "")
                nonlocal manifest_seen_after_supervisor
                dispatch_order.append(f"turn:{node_id}")
                collaboration_modes[node_id] = str(payload.get("collaboration_mode") or "") or None
                execution_policies[node_id] = str(payload.get("execution_policy") or "") or None
                if node_id == "node_research_a" and live_run_manifest_path is not None:
                    manifest = json.loads(live_run_manifest_path.read_text(encoding="utf-8"))
                    supervisor_state = next(
                        item for item in list(manifest.get("node_run_states") or []) if item.get("node_id") == "node_supervisor"
                    )
                    self.assertEqual(supervisor_state["status"], "completed")
                    self.assertTrue(
                        any(item["event_type"] == "node_completed" and item.get("node_id") == "node_supervisor" for item in manifest["event_refs"])
                    )
                    manifest_seen_after_supervisor = True
                return {
                    "turn": {"id": f"turn-{node_id}"},
                    "thread_id": f"provider-{node_id}",
                    "handoff": {
                        "from_thread_id": thread_id,
                        "to_thread_id": f"provider-{node_id}",
                    },
                }

            def fake_wait_for_terminal(
                client: object,
                *,
                thread_id: str,
                turn_id: str,
                timeout_seconds: float,
                operation_label: str,
            ) -> dict[str, object]:  # noqa: ARG001
                node_id = turn_id.replace("turn-", "")
                wait_order.append(node_id)
                wait_thread_ids[node_id] = thread_id
                return {"thread_id": thread_id, "turn_id": turn_id}

            def fake_probe_result(thread: dict[str, object], *, turn_id: str) -> tuple[str, str, str]:  # noqa: ARG001
                node_id = turn_id.replace("turn-", "")
                return (
                    "completed",
                    json.dumps(
                        {
                            "human_summary": f"{node_id} summary",
                            "machine_result": {"node_id": node_id, "status": "ok"},
                        }
                    ),
                    "",
                )

            runtime.start_graph_worker = fake_start_graph_worker  # type: ignore[method-assign]
            runtime.start_turn = fake_start_turn  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: object()  # type: ignore[method-assign]  # noqa: ARG005
            runtime._wait_for_probe_turn_terminal = fake_wait_for_terminal  # type: ignore[method-assign]
            runtime._probe_turn_result = fake_probe_result  # type: ignore[method-assign]

            result = runtime.execute_task_graph_run(
                {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 80000}}}
            )

            self.assertEqual(result["live_run"]["run_status"], "completed")
            self.assertEqual(result["live_run"]["run_ref"]["status"], "completed")
            self.assertTrue(manifest_seen_after_supervisor)
            self.assertEqual(tasks.current_task()["active_provider_thread_id"], "thread-parent")
            branch_dispatch = [item for item in dispatch_order if item in {"turn:node_research_a", "turn:node_research_b"}]
            self.assertEqual(branch_dispatch, ["turn:node_research_a", "turn:node_research_b"])
            self.assertIn("node_research_a", wait_order)
            self.assertIn("node_research_b", wait_order)
            self.assertTrue(wait_thread_ids)
            self.assertTrue(
                all(thread_id == f"provider-{node_id}" for node_id, thread_id in wait_thread_ids.items())
            )
            self.assertEqual(collaboration_modes.get("node_supervisor"), "default")
            self.assertEqual(collaboration_modes.get("node_merge"), "default")
            self.assertTrue(execution_policies)
            self.assertTrue(all(policy == "no_tools" for policy in execution_policies.values()))
            self.assertTrue((workspace / result["live_run"]["artifact_paths"]["summary_json"]).exists())
            self.assertTrue((workspace / result["live_run"]["artifact_paths"]["report_md"]).exists())
            latest_ref = tasks.graph_run_ref(result["live_run"]["run_id"])
            self.assertIsNotNone(latest_ref)
            self.assertEqual(latest_ref["worker_count"], 4)
            resolved_events = [
                item
                for item in runtime.list_events()["events"]
                if item.get("type") == "graph_worker_turn_thread_resolved"
            ]
            self.assertEqual(len(resolved_events), 4)
            self.assertTrue(all(bool(item.get("provider_handoff")) for item in resolved_events))
            self.assertTrue(
                all(str(item.get("execution_thread_id") or "").startswith("provider-") for item in resolved_events)
            )

    def test_execute_cancellable_fixture_backfills_missing_subagent_policy_from_legacy_orchestration_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph recovery compat", root / "graph-recovery-compat.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph recovery compat task")

            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            orchestration_graph = json.loads(json.dumps(graph["orchestration_graph"]))
            for node in orchestration_graph["nodes"]:
                execution = dict(node.get("execution") or {})
                if str(execution.get("spawn_mode") or "").strip() == "subagent_worker":
                    execution.pop("subagent_policy", None)
                    node["execution"] = execution
            graph["orchestration_graph"] = orchestration_graph
            tasks.upsert_graph_definition(graph)

            synced = tasks._orchestration_graph_for_task_graph(graph)
            result = tasks.execute_fixture_graph({"graph_id": graph["graph_id"], "execution_mode": "cancellable"})

            run_ref = result["fixture_run"]["run_ref"]
            self.assertEqual(run_ref["status"], "running")
            worker_nodes = [
                node
                for node in list(synced.get("nodes") or [])
                if str(dict(node.get("execution") or {}).get("spawn_mode") or "").strip() == "subagent_worker"
            ]
            self.assertTrue(worker_nodes)
            for node in worker_nodes:
                policy = dict(dict(node.get("execution") or {}).get("subagent_policy") or {})
                self.assertEqual(policy.get("isolation_mode"), "lane")
                self.assertEqual(policy.get("max_turns"), 8)
                self.assertFalse(bool(policy.get("allow_direct_teammate_messages")))
                self.assertFalse(bool(policy.get("share_worktree")))
                self.assertFalse(bool(policy.get("allow_nested_subagents")))

    def test_dry_run_graph_validates_multimodal_typed_ports_against_configured_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph multimodal dry-run", root / "graph-multimodal.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph multimodal task")

            imported = tasks.import_graph_from_orchestration_file(
                {
                    "graph_text": json.dumps(load_agent_orchestration_example("multimodal_capability_adapter"), ensure_ascii=False, indent=2) + "\n",
                },
                profiles_snapshot={
                    "profiles": [
                        {
                            "profile_id": "qwen-default",
                            "provider_id": "qwen",
                            "model": "qwen3-coder-plus",
                            "input_modalities": ["text", "image"],
                            "capabilities": {"supports_vision": True, "supports_tool_result_images": True},
                        }
                    ]
                },
                configured_models=[
                    {
                        "id": "qwen/qwen3-coder-plus",
                        "provider": "qwen",
                        "native_model": "qwen3-coder-plus",
                        "input_modalities": ["text", "image"],
                    }
                ],
            )

            dry_run = tasks.dry_run_graph(
                {"graph_id": imported["graph"]["graph_id"]},
                profiles_snapshot={
                    "profiles": [
                        {
                            "profile_id": "qwen-default",
                            "provider_id": "qwen",
                            "model": "qwen3-coder-plus",
                            "input_modalities": ["text", "image"],
                            "capabilities": {"supports_vision": True, "supports_tool_result_images": True},
                        }
                    ]
                },
                configured_models=[
                    {
                        "id": "qwen/qwen3-coder-plus",
                        "provider": "qwen",
                        "native_model": "qwen3-coder-plus",
                        "input_modalities": ["text", "image"],
                    }
                ],
            )["dry_run"]

            self.assertEqual(dry_run["overall_status"], "pass")
            self.assertEqual(dry_run["status_counts"]["blocked"], 0)
            self.assertTrue((workspace / dry_run["artifact_paths"]["compiled_plan_json"]).exists())

    def test_dry_run_graph_blocks_invalid_multimodal_route_for_text_only_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph multimodal block", root / "graph-multimodal-block.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph multimodal blocked task")

            imported = tasks.import_graph_from_orchestration_file(
                {
                    "graph_text": json.dumps(load_agent_orchestration_example("multimodal_capability_adapter"), ensure_ascii=False, indent=2) + "\n",
                }
            )

            with self.assertRaisesRegex(ValueError, "invalid provider/model modality claims"):
                tasks.dry_run_graph(
                    {"graph_id": imported["graph"]["graph_id"]},
                    profiles_snapshot={
                        "profiles": [
                            {
                                "profile_id": "qwen-default",
                                "provider_id": "qwen",
                                "model": "qwen3-coder-plus",
                                "input_modalities": ["text"],
                                "capabilities": {"supports_vision": False, "supports_tool_result_images": False},
                            }
                        ]
                    },
                    configured_models=[
                        {
                            "id": "qwen/qwen3-coder-plus",
                            "provider": "qwen",
                            "native_model": "qwen3-coder-plus",
                            "input_modalities": ["text"],
                        }
                    ],
                )

    def test_dry_run_graph_persists_compiled_plan_without_recovery_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph dry-run fixture", root / "graph-dry-run-fixture.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph dry-run fixture task")
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]

            dry_run = tasks.dry_run_graph({"graph_id": graph["graph_id"]})["dry_run"]

            self.assertIn("compiled_plan", dry_run)
            self.assertEqual(dry_run["run_status"], "dry_run_passed")
            self.assertTrue((workspace / dry_run["artifact_paths"]["summary_json"]).exists())
            self.assertTrue((workspace / dry_run["artifact_paths"]["report_md"]).exists())
            self.assertTrue((workspace / dry_run["artifact_paths"]["compiled_plan_json"]).exists())
            artifact_paths = {str(item["path"]) for item in dry_run["artifact_refs"]}
            self.assertEqual(artifact_paths, set(dry_run["artifact_paths"].values()))

    def test_dry_run_graph_blocks_static_budget_overrun_and_exports_budget_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph budget block", root / "graph-budget-block.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task("Graph budget block task")
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            graph_policy = dict(graph.get("graph_policy") or {})
            graph_policy["budget"] = {"limits": {"provider_call_count": 1}}
            graph["graph_policy"] = graph_policy
            tasks.upsert_graph_definition(graph)

            dry_run = tasks.dry_run_graph({"graph_id": graph["graph_id"]})["dry_run"]

            self.assertEqual(dry_run["overall_status"], "blocked")
            self.assertEqual(dry_run["budget"]["status"], "exceeded")
            self.assertEqual(dry_run["budget"]["graph"]["observed"]["provider_call_count"], 4)
            self.assertEqual(dry_run["run_ref"]["budget"]["status"], "exceeded")
            self.assertEqual(dry_run["run_ref"]["budget"]["graph"]["exceeded_fields"], ["provider_call_count"])
            export_artifact = next(
                item
                for item in dry_run["run_ref"]["artifact_refs"]
                if str(item.get("path") or "").endswith("run-export.json")
            )
            export_payload = json.loads((workspace / export_artifact["path"]).read_text(encoding="utf-8"))
            self.assertEqual(export_payload["budget"]["status"], "exceeded")
            self.assertEqual(export_payload["budget"]["graph"]["observed"]["provider_call_count"], 4)

    def test_start_graph_worker_creates_isolated_lane_and_persists_sanitized_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph worker runtime", root / "graph-worker.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Graph worker task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
            node_worker = next(item for item in graph["nodes"] if item["node_id"] == "node_worker")
            node_worker["tools"] = {
                "approval_mode": "ask",
                "allowed_tool_classes": ["read_file", "shell"],
                "supports_mcp": True,
            }
            node_worker["mcp_preset_ids"] = ["astrabridge_web", "astrabridge_capabilities"]
            node_worker["skill_ids"] = ["agent-orchestration-operator"]
            node_worker["execution_policy"]["subagent_policy"] = {
                "isolation_mode": "lane",
                "max_turns": 6,
                "allow_direct_teammate_messages": False,
                "share_worktree": False,
                "allow_nested_subagents": False,
            }
            tasks.upsert_graph_definition(graph)
            dry_run = tasks.dry_run_graph(
                {"graph_id": graph["graph_id"]},
                profiles_snapshot={
                    "profiles": [
                        {
                            "profile_id": "qwen-default",
                            "provider_id": "qwen",
                            "model": "qwen3-coder-plus",
                            "reasoning_effort": "high",
                        }
                    ]
                },
            )["dry_run"]

            class FakeClient:
                def __init__(self) -> None:
                    self.requests: list[tuple[str, dict[str, object]]] = []

                def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                    payload = dict(params or {})
                    self.requests.append((method, payload))
                    if method == "thread/start":
                        return {"thread": {"id": "thread-worker-1", "name": "worker"}}
                    if method == "thread/name/set":
                        return {"ok": True}
                    raise AssertionError(f"Unexpected method {method}")

            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            client = FakeClient()
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: client  # type: ignore[method-assign]  # noqa: ARG005

            result = runtime.start_graph_worker(
                {
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                },
                graph_id=graph["graph_id"],
                run_id=dry_run["run_id"],
                node_id="node_worker",
                parent_thread_id="thread-parent",
                artifact_refs=[
                    {
                        "artifact_id": "artifact-worker-report",
                        "artifact_kind": "validation_report",
                        "path": "PRIVATE/task-graph/workers/report.md",
                        "status": "ready",
                        "reasoning_content": "private reasoning",
                        "authorization": "Bearer secret",
                    }
                ],
            )

            self.assertEqual(result["worker"]["thread_id"], "thread-worker-1")
            self.assertEqual(result["worker"]["parent_thread_id"], "thread-parent")
            self.assertEqual(result["worker"]["worker_origin"], "codex_subagent")
            self.assertEqual(tasks.current_task()["active_provider_thread_id"], "thread-parent")
            self.assertEqual(str((projects.current_project or {}).get("current_thread_id") or ""), "thread-parent")

            start_method, start_params = client.requests[0]
            self.assertEqual(start_method, "thread/start")
            self.assertEqual(
                start_params["source"],
                {
                    "subagent": {
                        "thread_spawn": {
                            "parent_thread_id": "thread-parent",
                        "depth": 1,
                        "agent_path": None,
                        "agent_nickname": "Worker",
                        "agent_role": "worker",
                        "max_turns": 6,
                        "isolation_mode": "lane",
                        "allow_direct_teammate_messages": False,
                        "share_worktree": False,
                        "allow_nested_subagents": False,
                    }
                }
            },
        )

            run_ref = tasks.graph_run_ref(dry_run["run_id"])
            self.assertIsNotNone(run_ref)
            self.assertEqual(run_ref["worker_count"], 1)
            binding = run_ref["worker_bindings"][0]
            self.assertEqual(binding["worker_thread_id"], "thread-worker-1")
            self.assertEqual(binding["parent_thread_id"], "thread-parent")
            self.assertEqual(binding["worker_origin"], "codex_subagent")
            self.assertEqual(binding["agent_nickname"], "Worker")
            self.assertEqual(binding["runtime_contract"]["model"], "qwen3-coder-plus")
            self.assertEqual(binding["runtime_contract"]["reasoning_effort"], "high")
            self.assertEqual(binding["runtime_contract"]["permission_mode"], "auto")
            self.assertEqual(binding["runtime_contract"]["collaboration_mode"], "default")
            self.assertEqual(binding["runtime_contract"]["execution_backend"], "app_server")
            self.assertEqual(binding["runtime_contract"]["spawn_mode"], "subagent_worker")
            self.assertEqual(binding["runtime_contract"]["timeout_ms"], 120000)
            self.assertEqual(binding["runtime_contract"]["tool_policy"]["approval_mode"], "ask")
            self.assertEqual(binding["runtime_contract"]["tool_policy"]["allowed_tool_classes"], ["read_file", "shell"])
            self.assertTrue(binding["runtime_contract"]["tool_policy"]["supports_mcp"])
            self.assertEqual(binding["runtime_contract"]["mcp_preset_ids"], ["astrabridge_web", "astrabridge_capabilities"])
            self.assertEqual(binding["runtime_contract"]["skill_ids"], ["agent-orchestration-operator"])
            self.assertEqual(binding["runtime_contract"]["subagent_policy"]["isolation_mode"], "lane")
            self.assertEqual(binding["runtime_contract"]["subagent_policy"]["max_turns"], 6)
            self.assertNotIn("reasoning_content", binding["artifact_refs"][0])
            self.assertNotIn("authorization", binding["artifact_refs"][0])
            self.assertEqual(binding["artifact_refs"][0]["path"], "PRIVATE/task-graph/workers/report.md")
            self.assertEqual(task["task_id"], run_ref["task_id"])

            output = tasks.record_graph_worker_output(
                {
                    "graph_id": graph["graph_id"],
                    "run_id": dry_run["run_id"],
                    "node_id": "node_worker",
                    "worker_thread_id": "thread-worker-1",
                    "human_summary": "Worker produced a bounded result for the synthesizer.",
                    "machine_result": {
                        "summary": "bounded result",
                        "artifact_refs": ["PRIVATE/task-graph/workers/report.md"],
                        "raw_history": "must not become downstream context",
                    },
                    "confidence": "high",
                    "next_action_hints": ["Pass only the artifact bundle to the synthesizer."],
                    "usage_signal": {
                        "input_tokens": 1200,
                        "output_tokens": 300,
                        "total_tokens": 1500,
                    },
                    "provider_call_count": 1,
                    "tool_call_count": 2,
                    "elapsed_ms": 4200,
                    "attempt_count": 2,
                }
            )
            self.assertEqual(output["worker_binding"]["status"], "completed")
            self.assertTrue((workspace / "PRIVATE" / "task-graph" / "workers" / dry_run["run_id"] / "node_worker" / "output.json").exists())
            self.assertTrue((workspace / "PRIVATE" / "task-graph" / "workers" / dry_run["run_id"] / "node_worker" / "summary.md").exists())
            self.assertTrue((workspace / "PRIVATE" / "task-graph" / "workers" / dry_run["run_id"] / "node_worker" / "handoff.json").exists())
            self.assertTrue((workspace / "PRIVATE" / "task-graph" / "workers" / dry_run["run_id"] / "node_worker" / "output-envelope.json").exists())
            self.assertTrue((workspace / dry_run["artifact_paths"]["compiled_plan_json"]).exists())
            self.assertEqual(output["worker_binding"]["output_summary"]["artifact_bundle_path"], f"PRIVATE/task-graph/workers/{dry_run['run_id']}/node_worker/output.json")
            self.assertEqual(output["worker_binding"]["output_summary"]["output_envelope_path"], f"PRIVATE/task-graph/workers/{dry_run['run_id']}/node_worker/output-envelope.json")
            self.assertEqual(output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["source"], "artifact_refs_and_context_policy")
            self.assertIn("machine_result", output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["message_part_types"])
            self.assertIn("artifact_ref", output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["message_part_types"])
            self.assertTrue(output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["exclude_private_memory"])
            self.assertNotIn("raw_history", str(output["worker_binding"]["downstream_handoffs"]))
            input_envelope_path = workspace / output["worker_binding"]["downstream_handoffs"][0]["downstream_input"]["input_envelope_path"]
            input_envelope = json.loads(input_envelope_path.read_text(encoding="utf-8"))
            self.assertTrue(input_envelope["exclude_private_memory"])
            self.assertIn("machine_result", input_envelope["message_part_types"])
            self.assertIn("artifact_ref", input_envelope["message_part_types"])
            self.assertEqual(len(input_envelope["artifact_refs"]), 2)
            self.assertNotIn("raw_history", json.dumps(input_envelope, ensure_ascii=False))
            output_envelope_path = workspace / output["worker_binding"]["output_summary"]["output_envelope_path"]
            output_envelope = json.loads(output_envelope_path.read_text(encoding="utf-8"))
            self.assertIn("machine_result", output_envelope["message_part_types"])
            self.assertIn("human_summary", output_envelope["message_part_types"])
            self.assertNotIn("authorization", json.dumps(output_envelope, ensure_ascii=False))

            reloaded_tasks = TaskService(projects)
            restored_run_ref = reloaded_tasks.graph_run_ref(dry_run["run_id"])
            self.assertIsNotNone(restored_run_ref)
            self.assertEqual(restored_run_ref["worker_count"], 1)
            self.assertEqual(restored_run_ref["worker_bindings"][0]["worker_thread_id"], "thread-worker-1")
            self.assertEqual(restored_run_ref["worker_bindings"][0]["output_summary"]["human_summary"], "Worker produced a bounded result for the synthesizer.")
            self.assertEqual(restored_run_ref["worker_bindings"][0]["runtime_contract"]["subagent_policy"]["max_turns"], 6)
            self.assertTrue(restored_run_ref["worker_bindings"][0]["downstream_handoffs"][0]["downstream_input"]["exclude_private_memory"])
            self.assertTrue(any(str(item["path"]).endswith("/compiled-plan.json") for item in restored_run_ref["artifact_refs"]))
            self.assertEqual(restored_run_ref["metrics"]["token_usage"]["total_tokens"], 1500)
            self.assertEqual(restored_run_ref["metrics"]["provider_call_count"], 1)
            self.assertEqual(restored_run_ref["metrics"]["tool_call_count"], 2)
            self.assertEqual(restored_run_ref["metrics"]["retry_count"], 1)
            export_artifact = next(
                item
                for item in restored_run_ref["artifact_refs"]
                if str(item.get("path") or "").endswith("run-export.json")
            )
            export_payload = json.loads((workspace / export_artifact["path"]).read_text(encoding="utf-8"))
            self.assertEqual(export_payload["metrics"]["token_usage"]["total_tokens"], 1500)
            self.assertNotIn("authorization", json.dumps(export_payload, ensure_ascii=False))
            self.assertNotIn("raw_history", json.dumps(export_payload, ensure_ascii=False))

    def test_start_graph_worker_blocks_unsupported_nested_or_worktree_subagents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph worker runtime", root / "graph-worker.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Graph worker task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
            node_worker = next(item for item in graph["nodes"] if item["node_id"] == "node_worker")
            node_worker["execution_policy"]["subagent_policy"] = {
                "isolation_mode": "lane",
                "max_turns": 4,
                "allow_direct_teammate_messages": False,
                "share_worktree": False,
                "allow_nested_subagents": True,
            }
            tasks.upsert_graph_definition(graph)
            dry_run = tasks.dry_run_graph(
                {"graph_id": graph["graph_id"]},
                profiles_snapshot={
                    "profiles": [
                        {
                            "profile_id": "qwen-default",
                            "provider_id": "qwen",
                            "model": "qwen3-coder-plus",
                            "reasoning_effort": "high",
                        }
                    ]
                },
            )["dry_run"]

            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: None  # type: ignore[method-assign]  # noqa: ARG005

            with self.assertRaisesRegex(ValueError, "nested subagents"):
                runtime.start_graph_worker(
                    {
                        "profile_id": "qwen-default",
                        "provider_id": "qwen",
                        "model": "qwen3-coder-plus",
                        "reasoning_effort": "high",
                    },
                    graph_id=graph["graph_id"],
                    run_id=dry_run["run_id"],
                    node_id="node_worker",
                    parent_thread_id="thread-parent",
                )

    def test_fixture_fanout_run_persists_partial_merge_and_attributable_branch_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Fanout fixture runtime", root / "fanout-fixture.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Fanout fixture task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]

            result = tasks.execute_fixture_graph(
                {
                    "graph_id": graph["graph_id"],
                    "branch_behaviors": {
                        "node_research_a": "completed",
                        "node_research_b": "blocked",
                    },
                }
            )

            fixture_run = result["fixture_run"]
            self.assertEqual(fixture_run["run_status"], "partial")
            run_ref = fixture_run["run_ref"]
            self.assertEqual(run_ref["status"], "partial")
            self.assertEqual(run_ref["node_outcome_counts"]["passed"], 2)
            self.assertEqual(run_ref["node_outcome_counts"]["blocked"], 1)
            self.assertEqual(run_ref["node_outcome_counts"]["partial"], 1)
            self.assertEqual(run_ref["worker_count"], 3)
            self.assertTrue((workspace / fixture_run["artifact_paths"]["summary_json"]).exists())
            self.assertTrue((workspace / fixture_run["artifact_paths"]["report_md"]).exists())

            bindings = {item["node_id"]: item for item in run_ref["worker_bindings"]}
            self.assertIn("node_research_a", bindings)
            self.assertIn("node_research_b", bindings)
            self.assertIn("node_merge", bindings)
            self.assertEqual(bindings["node_research_a"]["status"], "completed")
            self.assertEqual(bindings["node_research_b"]["status"], "blocked")
            self.assertEqual(bindings["node_merge"]["status"], "partial")
            self.assertTrue(any(str(item["path"]).endswith("/summary.md") for item in bindings["node_research_a"]["artifact_refs"]))
            self.assertTrue(any(str(item["path"]).endswith("/summary.md") for item in bindings["node_research_b"]["artifact_refs"]))
            self.assertIn("consumed_worker_artifacts", str(bindings["node_merge"]["output_summary"]["machine_result_preview"]))
            self.assertEqual(bindings["node_research_a"]["downstream_handoffs"][0]["downstream_input"]["source"], "artifact_refs_and_context_policy")
            self.assertEqual(bindings["node_research_b"]["downstream_handoffs"][0]["downstream_input"]["source"], "artifact_refs_and_context_policy")

            reloaded_tasks = TaskService(projects)
            restored_run_ref = reloaded_tasks.graph_run_ref(fixture_run["run_id"])
            self.assertEqual(restored_run_ref["status"], "partial")
            self.assertEqual(restored_run_ref["worker_count"], 3)
            self.assertEqual(restored_run_ref["node_outcome_counts"]["partial"], 1)

    def test_provider_gate_fixture_requires_approval_and_persists_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Provider gate fixture", root / "provider-gate.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Provider gate task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("provider_update_smoke_gate")["graph"]

            pending = tasks.execute_fixture_graph({"graph_id": graph["graph_id"]})["fixture_run"]
            pending_run = pending["run_ref"]
            self.assertEqual(pending["run_status"], "paused_for_review")
            self.assertEqual(pending_run["status"], "paused_for_review")
            self.assertEqual(pending_run["approval_state"], "pending")
            self.assertEqual(pending_run["approval_details"]["review_kind"], "provider_call_gate")
            self.assertEqual(pending_run["node_status_counts"]["waiting_on_approval"], 1)
            self.assertEqual(pending_run["worker_count"], 3)

            rejected = tasks.resolve_graph_run_approval(
                {"run_id": pending["run_id"], "decision": "reject", "notes": "Need a narrower provider scope."}
            )
            rejected_run = rejected["run_ref"]
            self.assertEqual(rejected_run["status"], "failed")
            self.assertEqual(rejected_run["approval_state"], "rejected")
            self.assertEqual(rejected_run["approval_details"]["decision"], "reject")
            self.assertEqual(rejected_run["node_status_counts"]["blocked"], 1)
            self.assertEqual(rejected_run["node_outcome_counts"]["blocked"], 1)
            gate_binding = next(item for item in rejected_run["worker_bindings"] if item["node_id"] == "node_gate")
            self.assertEqual(gate_binding["status"], "blocked")
            self.assertTrue(any(str(item["path"]).endswith("/summary.md") for item in gate_binding["artifact_refs"]))

            approved_pending = tasks.execute_fixture_graph({"graph_id": graph["graph_id"]})["fixture_run"]
            approved = tasks.resolve_graph_run_approval(
                {"run_id": approved_pending["run_id"], "decision": "approve", "notes": "Promotion approved for this fixture run."}
            )
            approved_run = approved["run_ref"]
            self.assertEqual(approved_run["status"], "completed")
            self.assertEqual(approved_run["approval_state"], "approved")
            self.assertEqual(approved_run["approval_details"]["decision"], "approve")
            self.assertEqual(approved_run["node_status_counts"]["completed"], 3)
            self.assertEqual(approved_run["node_outcome_counts"]["passed"], 3)

            reloaded_tasks = TaskService(projects)
            restored_run_ref = reloaded_tasks.graph_run_ref(approved_pending["run_id"])
            self.assertEqual(restored_run_ref["status"], "completed")
            self.assertEqual(restored_run_ref["approval_details"]["status"], "approved")

    def test_template_specific_fixture_runs_complete_for_linear_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Linear template fixtures", root / "linear-fixtures.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Linear template fixture task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )

            for template_id, expected_workers in (
                ("supervisor_worker_synthesizer", 3),
                ("code_fix_test_review", 4),
                ("document_extract_analyze_report", 3),
            ):
                with self.subTest(template_id=template_id):
                    graph = tasks.instantiate_graph_template(template_id)["graph"]
                    result = tasks.execute_fixture_graph({"graph_id": graph["graph_id"]})["fixture_run"]
                    run_ref = result["run_ref"]
                    self.assertEqual(result["run_status"], "completed")
                    self.assertEqual(run_ref["status"], "completed")
                    self.assertEqual(run_ref["worker_count"], expected_workers)
                    self.assertEqual(run_ref["node_outcome_counts"]["passed"], expected_workers)
                    self.assertTrue((workspace / result["artifact_paths"]["summary_json"]).exists())
                    self.assertTrue((workspace / result["artifact_paths"]["report_md"]).exists())
                    self.assertTrue(any(item["event_type"] == "run_completed" for item in run_ref["timeline_events"]))
                    self.assertEqual(len(run_ref["worker_bindings"]), expected_workers)
                    self.assertIn("compiled_plan_json", result["artifact_paths"])
                    self.assertIn("run_manifest_json", result["artifact_paths"])
                    self.assertTrue((workspace / result["artifact_paths"]["compiled_plan_json"]).exists())
                    self.assertTrue((workspace / result["artifact_paths"]["run_manifest_json"]).exists())

    def test_generic_fixture_scheduler_runs_custom_blank_graph_and_persists_policy_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Custom blank fixture", root / "custom-blank.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Custom blank fixture task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]

            result = tasks.execute_fixture_graph({"graph_id": graph["graph_id"]})["fixture_run"]
            run_ref = result["run_ref"]
            self.assertEqual(result["run_status"], "completed")
            self.assertEqual(run_ref["status"], "completed")
            self.assertEqual(run_ref["worker_count"], 1)
            self.assertEqual(run_ref["policy_snapshot"]["scheduler"], "compiled_graph_mvp")
            self.assertFalse(run_ref["policy_snapshot"]["compatibility_shim"])
            self.assertTrue((workspace / result["artifact_paths"]["compiled_plan_json"]).exists())
            self.assertTrue((workspace / result["artifact_paths"]["run_manifest_json"]).exists())

    def test_generic_fixture_scheduler_marks_blocked_downstream_and_reports_parallelism(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Compiled scheduler failure cases", root / "compiled-failure.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Compiled scheduler failure task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )

            fanout_graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            fanout_result = tasks.execute_fixture_graph(
                {
                    "graph_id": fanout_graph["graph_id"],
                    "branch_behaviors": {
                        "node_research_a": "completed",
                        "node_research_b": "blocked",
                    },
                }
            )["fixture_run"]
            fanout_run = fanout_result["run_ref"]
            self.assertEqual(fanout_run["policy_snapshot"]["max_parallelism"], 2)
            self.assertEqual(fanout_run["policy_snapshot"]["parallel_group_ids"], ["group_0", "group_1", "group_2"])
            fanout_bindings = {item["node_id"]: item for item in fanout_run["worker_bindings"]}
            self.assertEqual(fanout_bindings["node_research_a"]["status"], "completed")
            self.assertEqual(fanout_bindings["node_research_b"]["status"], "blocked")
            self.assertEqual(fanout_bindings["node_merge"]["status"], "partial")
            run_manifest = json.loads((workspace / fanout_result["artifact_paths"]["run_manifest_json"]).read_text(encoding="utf-8"))
            node_states = {item["node_id"]: item for item in run_manifest["node_run_states"]}
            self.assertEqual(node_states["node_research_a"]["parallel_group_id"], "group_1")
            self.assertEqual(node_states["node_research_b"]["parallel_group_id"], "group_1")
            self.assertEqual(node_states["node_merge"]["parallel_group_id"], "group_2")
            self.assertEqual(node_states["node_research_a"]["started_at"], node_states["node_research_b"]["started_at"])
            self.assertLess(
                dt.datetime.fromisoformat(node_states["node_research_a"]["updated_at"]),
                dt.datetime.fromisoformat(node_states["node_merge"]["started_at"]),
            )
            self.assertGreater(node_states["node_research_a"]["elapsed_ms"], 0)
            self.assertGreater(node_states["node_research_b"]["elapsed_ms"], 0)
            join_events = [
                item
                for item in list(fanout_run["timeline_events"] or [])
                if item["event_type"] == "node_progress" and item.get("node_id") == "node_merge"
            ]
            self.assertTrue(join_events)
            self.assertEqual(join_events[0]["parallel_group_id"], "group_2")
            self.assertIn("satisfied join `all_required`", str(join_events[0]["summary"]))

            code_fix_graph = tasks.instantiate_graph_template("code_fix_test_review")["graph"]
            failed = tasks.execute_fixture_graph(
                {
                    "graph_id": code_fix_graph["graph_id"],
                    "node_behaviors": {
                        "node_plan_fix": "failed",
                    },
                }
            )["fixture_run"]
            failed_run = failed["run_ref"]
            self.assertEqual(failed["run_status"], "failed")
            self.assertEqual(failed_run["status"], "failed")
            bindings = {item["node_id"]: item for item in failed_run["worker_bindings"]}
            self.assertEqual(bindings["node_plan_fix"]["status"], "failed")
            self.assertEqual(bindings["node_code_fix"]["status"], "blocked")
            self.assertEqual(bindings["node_test"]["status"], "blocked")
            self.assertEqual(bindings["node_review"]["status"], "blocked")
            self.assertEqual(failed_run["node_outcome_counts"]["failed"], 1)
            self.assertEqual(failed_run["node_outcome_counts"]["blocked"], 3)
            self.assertTrue(any(item["event_type"] == "node_failed" for item in failed_run["timeline_events"]))

    def test_cancellable_fixture_run_can_be_cancelled_and_restored_with_timeline_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Cancellable fixture runtime", root / "cancellable-fixture.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Cancellable fixture task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]

            running = tasks.execute_fixture_graph({"graph_id": graph["graph_id"], "execution_mode": "cancellable"})["fixture_run"]
            running_ref = running["run_ref"]
            self.assertEqual(running["run_status"], "running")
            self.assertEqual(running_ref["status"], "running")
            self.assertEqual(running_ref["node_status_counts"]["running"], 1)
            self.assertTrue(running_ref["timeline_events"])

            cancelled = tasks.cancel_graph_run({"run_id": running["run_id"], "notes": "Cancelled during validation."})
            cancelled_ref = cancelled["run_ref"]
            self.assertEqual(cancelled_ref["status"], "cancelled")
            self.assertEqual(cancelled_ref["latest_event_type"], "run_cancelled")
            self.assertTrue(any(item["event_type"] == "run_cancelled" for item in cancelled_ref["timeline_events"]))
            self.assertTrue(any(str(item["path"]).endswith("/report.md") for item in cancelled_ref["diagnostic_refs"]))
            self.assertTrue((workspace / cancelled["cancellation"]["artifact_paths"]["report_md"]).exists())
            self.assertTrue((workspace / cancelled["cancellation"]["artifact_paths"]["summary_json"]).exists())

            reloaded_tasks = TaskService(projects)
            restored_run_ref = reloaded_tasks.graph_run_ref(running["run_id"])
            self.assertEqual(restored_run_ref["status"], "cancelled")
            self.assertTrue(any(item["event_type"] == "run_cancelled" for item in restored_run_ref["timeline_events"]))
            self.assertTrue(any(str(item["path"]).endswith("/report.md") for item in restored_run_ref["diagnostic_refs"]))

    def test_stale_task_save_does_not_overwrite_newer_cancelled_graph_run_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Graph run merge runtime", root / "graph-run-merge.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Graph run merge task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]

            running = tasks.execute_fixture_graph({"graph_id": graph["graph_id"], "execution_mode": "cancellable"})["fixture_run"]
            stale_task = tasks.current_task()
            self.assertIsNotNone(stale_task)
            cancelled = tasks.cancel_graph_run({"run_id": running["run_id"], "notes": "Cancelled before stale save."})
            self.assertEqual(cancelled["run_ref"]["status"], "cancelled")

            stale_task = dict(stale_task or {})
            stale_task["updated_at"] = now_iso()
            tasks._save_task(stale_task)

            restored_run_ref = tasks.graph_run_ref(running["run_id"])
            self.assertEqual(restored_run_ref["status"], "cancelled")
            self.assertEqual(restored_run_ref["latest_event_type"], "run_cancelled")
            self.assertTrue(any(item["event_type"] == "run_cancelled" for item in restored_run_ref["timeline_events"]))

    def test_retry_failed_nodes_recovery_creates_new_completed_run_and_preserves_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Retry recovery runtime", root / "retry-recovery.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Retry recovery task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("code_fix_test_review")["graph"]
            failed = tasks.execute_fixture_graph(
                {"graph_id": graph["graph_id"], "node_behaviors": {"node_plan_fix": "failed"}}
            )["fixture_run"]
            self.assertEqual(failed["run_ref"]["status"], "failed")

            recovered = tasks.recover_graph_run(
                {
                    "run_id": failed["run_id"],
                    "strategy": "retry_failed_nodes",
                    "node_behaviors": {"node_plan_fix": "completed"},
                }
            )
            recovered_run = recovered["fixture_run"]["run_ref"]
            self.assertEqual(recovered_run["status"], "completed")
            self.assertNotEqual(recovered_run["run_id"], failed["run_id"])
            self.assertEqual(recovered_run["policy_snapshot"]["recovery"]["strategy"], "retry_failed_nodes")
            self.assertIn("node_plan_fix", recovered["recovery"]["rerun_node_ids"])
            self.assertTrue((workspace / recovered["recovery"]["artifact_paths"]["manifest_json"]).exists())
            self.assertTrue((workspace / recovered["recovery"]["artifact_paths"]["report_md"]).exists())

    def test_rerun_selected_nodes_reuses_upstream_completed_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Selected rerun runtime", root / "selected-rerun.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Selected rerun task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
            completed = tasks.execute_fixture_graph({"graph_id": graph["graph_id"]})["fixture_run"]
            rerun = tasks.recover_graph_run(
                {
                    "run_id": completed["run_id"],
                    "strategy": "rerun_selected_nodes",
                    "selected_node_ids": ["node_worker"],
                }
            )
            rerun_run = rerun["fixture_run"]["run_ref"]
            self.assertEqual(rerun_run["status"], "completed")
            self.assertIn("node_supervisor", rerun["recovery"]["reused_node_ids"])
            self.assertIn("node_worker", rerun["recovery"]["rerun_node_ids"])
            rerun_manifest = json.loads((workspace / rerun["fixture_run"]["artifact_paths"]["run_manifest_json"]).read_text(encoding="utf-8"))
            reused_state = next(item for item in rerun_manifest["node_run_states"] if item["node_id"] == "node_supervisor")
            self.assertEqual(reused_state["reused_from_run_id"], completed["run_id"])

    def test_resume_cancelled_run_and_partial_execution_preserve_new_run_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Resume and partial runtime", root / "resume-partial.abproj", workspace_root=workspace)
            tasks = TaskService(projects)
            tasks.create_task(
                "Resume and partial task",
                thread_id="thread-parent",
                settings={
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
            running = tasks.execute_fixture_graph({"graph_id": graph["graph_id"], "execution_mode": "cancellable"})["fixture_run"]
            cancelled = tasks.cancel_graph_run({"run_id": running["run_id"], "notes": "Cancelled for resume validation."})
            resumed = tasks.recover_graph_run({"run_id": running["run_id"], "strategy": "resume_run"})
            resumed_run = resumed["fixture_run"]["run_ref"]
            self.assertEqual(cancelled["run_ref"]["status"], "cancelled")
            self.assertEqual(resumed_run["status"], "completed")
            self.assertNotEqual(resumed_run["run_id"], running["run_id"])
            self.assertEqual(resumed_run["policy_snapshot"]["recovery"]["strategy"], "resume_run")

            baseline = tasks.execute_fixture_graph({"graph_id": graph["graph_id"]})["fixture_run"]
            partial = tasks.recover_graph_run(
                {
                    "run_id": baseline["run_id"],
                    "strategy": "partial_execution",
                    "selected_node_ids": ["node_research_b"],
                }
            )
            partial_run = partial["fixture_run"]["run_ref"]
            self.assertEqual(partial_run["status"], "completed")
            self.assertIn("node_research_a", partial["recovery"]["reused_node_ids"])
            self.assertIn("node_merge", partial["recovery"]["rerun_node_ids"])


if __name__ == "__main__":
    unittest.main()
