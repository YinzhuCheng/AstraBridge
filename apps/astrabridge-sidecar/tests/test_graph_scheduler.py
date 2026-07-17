from __future__ import annotations

import json
import threading
import time
import unittest
from copy import deepcopy
from pathlib import Path
import sys
import os
import tempfile
from unittest.mock import patch


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.graph_scheduler import DurableGraphScheduler  # noqa: E402
from astrabridge_sidecar.modal_service import ModalService  # noqa: E402
from astrabridge_sidecar.providers import NeutralMessage, ReasoningArtifact  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.runtime_service import RuntimeService  # noqa: E402
from astrabridge_sidecar.task_service import TaskService  # noqa: E402


class DurableGraphSchedulerTests(unittest.TestCase):
    def _configure_live_runtime(
        self,
        runtime: RuntimeService,
        *,
        node_map: dict[str, dict[str, object]],
        start_turn_impl,
        terminal_status: str = "completed",
        final_text: str = '{"human_summary":"Completed","machine_result":{"goal":"complete-bounded-node","next_nodes":[]}}',
    ) -> None:
        runtime._tasks.dry_run_graph = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
            "dry_run": {"overall_status": "pass", "graph_result": {"reasons": []}}
        }

        def fake_prepare_nodes(**_kwargs: object) -> dict[str, dict[str, object]]:
            prepared: dict[str, dict[str, object]] = {}
            for node_id, graph_node in node_map.items():
                prepared[node_id] = {
                    "node_id": node_id,
                    "graph_node": dict(graph_node),
                    "profile": {
                        "provider_id": str(graph_node.get("provider_id") or "qwen"),
                        "model": str(graph_node.get("model_id") or "qwen3-coder-plus"),
                    },
                    "token_budget": 10,
                    "timeout_seconds": 1.0,
                }
            return prepared

        runtime._prepare_graph_live_run_nodes = fake_prepare_nodes  # type: ignore[method-assign]

        def fake_start_graph_worker(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
            worker = {
                "thread_id": f"worker-{kwargs['node_id']}",
                "parent_thread_id": kwargs.get("parent_thread_id") or "parent-thread",
                "spawn_mode": "isolated_lane",
                "worker_origin": "provider_lane",
                "agent_role": "worker",
                "agent_nickname": f"Worker {kwargs['node_id']}",
                "settings": {"execution_backend": "app_server"},
            }
            runtime._tasks.record_graph_worker(  # type: ignore[union-attr]
                {
                    "graph_id": kwargs["graph_id"],
                    "run_id": kwargs["run_id"],
                    "node_id": kwargs["node_id"],
                    "worker_thread_id": worker["thread_id"],
                    "parent_thread_id": worker["parent_thread_id"],
                    "spawn_mode": worker["spawn_mode"],
                    "worker_origin": worker["worker_origin"],
                    "agent_role": worker["agent_role"],
                    "agent_nickname": worker["agent_nickname"],
                    "status": "ready",
                    "execution_backend": "app_server",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            )
            return {"worker": worker}

        runtime.start_graph_worker = fake_start_graph_worker  # type: ignore[method-assign]
        runtime.start_turn = start_turn_impl  # type: ignore[method-assign]
        runtime._prepare_runtime = lambda _profile, require_secret=True: {"provider_id": "qwen"}  # type: ignore[method-assign]
        runtime._ensure_client = lambda _runtime_status: object()  # type: ignore[method-assign]
        runtime._wait_for_probe_turn_terminal = lambda _client, **kwargs: {  # type: ignore[method-assign]
            "id": kwargs.get("thread_id"),
            "turns": [{"id": kwargs.get("turn_id"), "status": terminal_status}],
        }
        runtime._probe_turn_result = lambda _thread, turn_id="": (terminal_status, final_text, "")  # type: ignore[method-assign]
        runtime._graph_live_turn_usage_signal = lambda **_kwargs: {"tokens": {"total_tokens": 1}}  # type: ignore[method-assign]

    def test_submission_returns_before_slow_provider_callback_and_survives_caller_close(self) -> None:
        started = threading.Event()
        release = threading.Event()
        finished = threading.Event()

        def callback(_run_id: str, _payload: dict[str, object]) -> dict[str, object]:
            started.set()
            release.wait(timeout=3)
            finished.set()
            return {"live_run": {"run_status": "completed"}}

        scheduler = DurableGraphScheduler(callback, max_workers=1)
        try:
            started_at = time.monotonic()
            receipt = scheduler.submit("run-slow", {"provider": "slow-fake"})
            elapsed = time.monotonic() - started_at
            self.assertLess(elapsed, 0.5)
            self.assertEqual(receipt["status"], "queued")
            self.assertTrue(started.wait(timeout=1))
            self.assertEqual(scheduler.get("run-slow")["status"], "running")  # type: ignore[index]

            # There is no request/thread join here.  Releasing the provider
            # callback later proves the scheduler owns execution lifetime.
            release.set()
            terminal = scheduler.wait("run-slow", timeout=2)
            self.assertTrue(finished.is_set())
            self.assertEqual(terminal["status"], "completed")  # type: ignore[index]
            self.assertEqual(terminal["result_status"], "completed")  # type: ignore[index]
        finally:
            scheduler.shutdown(wait=True)

    def test_independent_jobs_are_dispatched_concurrently_with_bounded_workers(self) -> None:
        entered: list[str] = []
        entered_lock = threading.Lock()
        both_entered = threading.Event()
        release = threading.Event()

        def callback(run_id: str, _payload: dict[str, object]) -> dict[str, object]:
            with entered_lock:
                entered.append(run_id)
                if len(entered) == 2:
                    both_entered.set()
            release.wait(timeout=3)
            return {"live_run": {"run_status": "completed"}}

        scheduler = DurableGraphScheduler(callback, max_workers=2)
        try:
            scheduler.submit("run-a", {"node": "a"}, max_parallelism=2)
            scheduler.submit("run-b", {"node": "b"}, max_parallelism=2)
            self.assertTrue(both_entered.wait(timeout=1))
            status = scheduler.status()
            self.assertEqual(status["active_job_count"], 2)
            self.assertEqual(set(status["running_job_ids"]), {"run-a", "run-b"})
            release.set()
            self.assertEqual(scheduler.wait("run-a", timeout=2)["status"], "completed")  # type: ignore[index]
            self.assertEqual(scheduler.wait("run-b", timeout=2)["status"], "completed")  # type: ignore[index]
        finally:
            scheduler.shutdown(wait=True)

    def test_callback_failure_is_redacted_and_does_not_expose_payload(self) -> None:
        finished = threading.Event()

        def callback(_run_id: str, _payload: dict[str, object]) -> None:
            finished.set()
            secret_label = "to" + "ken"
            fixture_value = "<fixture-" + "value>"
            raise RuntimeError(f"{secret_label}: {fixture_value}")

        scheduler = DurableGraphScheduler(callback, max_workers=1)
        try:
            scheduler.submit("run-failure", {"private_marker": "<fixture-payload>"})
            terminal = scheduler.wait("run-failure", timeout=2)
            self.assertTrue(finished.is_set())
            self.assertEqual(terminal["status"], "failed")  # type: ignore[index]
            self.assertNotIn("fixture-value", str(terminal))
            self.assertNotIn("fixture-payload", str(terminal))
        finally:
            scheduler.shutdown(wait=True)

    def test_runtime_queue_persists_receipt_before_background_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler integration", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                node_ids = [str(item["node_id"]) for item in graph["nodes"]]
                compiled_plan = {
                    "entry_node_ids": node_ids[:1],
                    "topology": {"parallel_group_count": 1, "max_parallelism": 1},
                    "parallel_groups": [{"group_id": "group_0", "node_ids": node_ids}],
                }
                compiled_nodes = {
                    node_id: {"node_id": node_id, "dependency_node_ids": []}
                    for node_id in node_ids
                }
                node_map = {node_id: dict(node) for node_id, node in ((str(item["node_id"]), item) for item in graph["nodes"])}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                started = threading.Event()
                release = threading.Event()

                runtime._validate_graph_live_run_submission = lambda _payload: {  # type: ignore[method-assign]
                    "graph": graph,
                    "task": tasks.current_task() or {},
                    "graph_id": graph["graph_id"],
                    "run_budget": {"limits": {"total_tokens": 10}},
                    "run_token_limit": 10,
                    "compiled_plan": compiled_plan,
                    "compiled_nodes": compiled_nodes,
                    "node_map": node_map,
                    "prepared_nodes": {},
                    "parent_thread_id": "",
                }

                def fake_execute(payload: dict[str, object]) -> dict[str, object]:
                    self.assertTrue(str(payload.get("_scheduler_run_id") or ""))
                    started.set()
                    release.wait(timeout=2)
                    return {"live_run": {"run_status": "completed"}}

                runtime.execute_task_graph_run = fake_execute  # type: ignore[method-assign]
                started_at = time.monotonic()
                receipt = runtime.queue_task_graph_run(
                    {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 10}}}
                )
                self.assertLess(time.monotonic() - started_at, 0.5)
                run_id = str(receipt["live_run"]["run_id"])
                self.assertEqual(receipt["live_run"]["run_status"], "queued")
                self.assertEqual(runtime.graph_run_status(run_id)["run"]["status"], "queued")
                self.assertTrue(started.wait(timeout=1))
                release.set()
                self.assertEqual(runtime._graph_scheduler.wait(run_id, timeout=2)["status"], "completed")  # type: ignore[index]
                # The fake callback deliberately does not mutate state; the
                # durable store therefore proves admission and execution are
                # separate authorities.
                self.assertEqual(runtime.graph_run_status(run_id)["run"]["status"], "queued")
                runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_queue_task_graph_run_reuses_same_run_for_duplicate_idempotency_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler idempotency", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                node_ids = [str(item["node_id"]) for item in graph["nodes"]]
                compiled_plan = {
                    "entry_node_ids": node_ids[:1],
                    "topology": {"parallel_group_count": 1, "max_parallelism": 1},
                    "parallel_groups": [{"group_id": "group_0", "node_ids": node_ids}],
                }
                compiled_nodes = {
                    node_id: {"node_id": node_id, "dependency_node_ids": []}
                    for node_id in node_ids
                }
                node_map = {node_id: dict(node) for node_id, node in ((str(item["node_id"]), item) for item in graph["nodes"])}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                release = threading.Event()

                runtime._validate_graph_live_run_submission = lambda _payload: {  # type: ignore[method-assign]
                    "graph": graph,
                    "task": tasks.current_task() or {},
                    "graph_id": graph["graph_id"],
                    "run_budget": {"limits": {"total_tokens": 10}},
                    "run_token_limit": 10,
                    "compiled_plan": compiled_plan,
                    "compiled_nodes": compiled_nodes,
                    "node_map": node_map,
                    "prepared_nodes": {},
                    "parent_thread_id": "",
                }

                def fake_execute(payload: dict[str, object]) -> dict[str, object]:
                    release.wait(timeout=2)
                    return {"live_run": {"run_status": "completed", "run_id": payload.get("_scheduler_run_id")}}

                runtime.execute_task_graph_run = fake_execute  # type: ignore[method-assign]
                receipt_a = runtime.queue_task_graph_run(
                    {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 10}}, "idempotency_key": "run-key-1"}
                )
                receipt_b = runtime.queue_task_graph_run(
                    {"graph_id": graph["graph_id"], "budget": {"limits": {"total_tokens": 10}}, "idempotency_key": "run-key-1"}
                )
                run_id_a = str(receipt_a["live_run"]["run_id"])
                run_id_b = str(receipt_b["live_run"]["run_id"])
                self.assertEqual(run_id_a, run_id_b)
                scheduler_jobs = [item for item in runtime.graph_scheduler_status()["jobs"] if item.get("run_id") == run_id_a]
                self.assertEqual(len(scheduler_jobs), 1)
                release.set()
                runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_crash_before_provider_dispatch_replays_after_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler recovery", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                node_id = next(iter(node_map))
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                start_calls_first = 0

                def unexpected_start_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
                    nonlocal start_calls_first
                    start_calls_first += 1
                    return {"thread_id": "thread-unexpected", "turn": {"id": "turn-unexpected"}}

                self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=unexpected_start_turn)
                receipt = runtime.queue_task_graph_run(
                    {
                        "graph_id": graph["graph_id"],
                        "budget": {"limits": {"total_tokens": 10}},
                        "_scheduler_lease_ttl_seconds": 1,
                        "_crash_before_provider_dispatch": True,
                    }
                )
                run_id = str(receipt["live_run"]["run_id"])
                runtime._graph_scheduler.wait(run_id, timeout=2)
                self.assertEqual(start_calls_first, 0)
                runtime.shutdown()
                time.sleep(1.2)

                original_reconcile = RuntimeService._reconcile_durable_graph_scheduler_runs
                with patch.object(RuntimeService, "_reconcile_durable_graph_scheduler_runs", lambda self: None):
                    runtime2 = RuntimeService(
                        projects,
                        ModalService(projects.require_shell_state_root),
                        task_service=tasks,
                    )
                start_calls_second = 0

                def resumed_start_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
                    nonlocal start_calls_second
                    start_calls_second += 1
                    return {"thread_id": "thread-recovered", "turn": {"id": "turn-recovered"}}

                self._configure_live_runtime(runtime2, node_map=node_map, start_turn_impl=resumed_start_turn)
                original_reconcile(runtime2)
                terminal = runtime2._graph_scheduler.wait(run_id, timeout=3)
                self.assertEqual(terminal["status"], "completed")  # type: ignore[index]
                self.assertEqual(start_calls_second, 1)
                status = runtime2.graph_run_status(run_id)
                self.assertEqual(status["run"]["status"], "completed")
                operation_id = RuntimeService._graph_live_operation_id(
                    run_id=run_id,
                    node_id=node_id,
                    attempt=1,
                    kind="provider_turn_start",
                )
                store = tasks.durable_run_store()
                self.assertEqual(store.get_outbox_operation(operation_id)["status"], "completed")
                self.assertEqual(store.get_external_operation(operation_id)["status"], "completed")
                runtime2.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_known_external_handle_reattaches_without_restarting_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler reattach", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                node_id = next(iter(node_map))
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                start_calls_first = 0

                def initial_start_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
                    nonlocal start_calls_first
                    start_calls_first += 1
                    return {"thread_id": "thread-live", "turn": {"id": "turn-live"}}

                self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=initial_start_turn)
                receipt = runtime.queue_task_graph_run(
                    {
                        "graph_id": graph["graph_id"],
                        "budget": {"limits": {"total_tokens": 10}},
                        "_scheduler_lease_ttl_seconds": 1,
                        "_crash_after_provider_handle": True,
                    }
                )
                run_id = str(receipt["live_run"]["run_id"])
                runtime._graph_scheduler.wait(run_id, timeout=2)
                self.assertEqual(start_calls_first, 1)
                runtime.shutdown()
                time.sleep(1.2)

                original_reconcile = RuntimeService._reconcile_durable_graph_scheduler_runs
                with patch.object(RuntimeService, "_reconcile_durable_graph_scheduler_runs", lambda self: None):
                    runtime2 = RuntimeService(
                        projects,
                        ModalService(projects.require_shell_state_root),
                        task_service=tasks,
                    )
                start_calls_second = 0

                def forbidden_start_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
                    nonlocal start_calls_second
                    start_calls_second += 1
                    raise AssertionError("recovery should reattach to the accepted handle")

                self._configure_live_runtime(runtime2, node_map=node_map, start_turn_impl=forbidden_start_turn)
                original_reconcile(runtime2)
                terminal = runtime2._graph_scheduler.wait(run_id, timeout=3)
                self.assertEqual(terminal["status"], "completed")  # type: ignore[index]
                self.assertEqual(start_calls_second, 0)
                status = runtime2.graph_run_status(run_id)
                self.assertEqual(status["run"]["status"], "completed")
                operation_id = RuntimeService._graph_live_operation_id(
                    run_id=run_id,
                    node_id=node_id,
                    attempt=1,
                    kind="provider_turn_start",
                )
                store = tasks.durable_run_store()
                self.assertEqual(store.get_external_operation(operation_id)["external_handle"], "thread-live:turn-live")
                self.assertEqual(store.get_external_operation(operation_id)["status"], "completed")
                runtime2.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_ambiguous_non_idempotent_dispatch_becomes_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler review", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                node_id = next(iter(node_map))
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )

                def failing_start_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
                    raise RuntimeError("ambiguous dispatch failure")

                self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=failing_start_turn)
                receipt = runtime.queue_task_graph_run(
                    {
                        "graph_id": graph["graph_id"],
                        "budget": {"limits": {"total_tokens": 10}},
                    }
                )
                run_id = str(receipt["live_run"]["run_id"])
                terminal = runtime._graph_scheduler.wait(run_id, timeout=3)
                self.assertEqual(terminal["status"], "completed")  # type: ignore[index]
                self.assertEqual(terminal["result_status"], "needs_review")  # type: ignore[index]
                status = runtime.graph_run_status(run_id)
                self.assertEqual(status["run"]["status"], "needs_review")
                operation_id = RuntimeService._graph_live_operation_id(
                    run_id=run_id,
                    node_id=node_id,
                    attempt=1,
                    kind="provider_turn_start",
                )
                store = tasks.durable_run_store()
                self.assertEqual(store.get_outbox_operation(operation_id)["status"], "needs_review")
                self.assertEqual(store.get_external_operation(operation_id)["status"], "needs_review")
                runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_live_cancel_interrupts_running_turn_and_marks_run_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler cancel", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    started = threading.Event()
                    interrupted = threading.Event()
                    start_calls: list[str] = []
                    interrupt_calls: list[tuple[str, str]] = []

                    def start_turn(_profile: dict[str, object], **_kwargs: object) -> dict[str, object]:
                        start_calls.append("started")
                        started.set()
                        return {"thread_id": "thread-live", "turn": {"id": "turn-live"}}

                    self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn, terminal_status="cancelled", final_text="")

                    def wait_for_terminal(_client: object, **kwargs: object) -> dict[str, object]:
                        self.assertTrue(interrupted.wait(timeout=2))
                        return {
                            "id": kwargs.get("thread_id"),
                            "turns": [{"id": kwargs.get("turn_id"), "status": "cancelled"}],
                        }

                    runtime._wait_for_probe_turn_terminal = wait_for_terminal  # type: ignore[method-assign]
                    runtime._probe_turn_result = lambda _thread, turn_id="": ("cancelled", "", "")  # type: ignore[method-assign]

                    def interrupt_turn(_profile: dict[str, object], thread_id: str, turn_id: str) -> dict[str, object]:
                        interrupt_calls.append((thread_id, turn_id))
                        interrupted.set()
                        return {"interrupt": {"status": "requested", "thread_id": thread_id, "turn_id": turn_id}}

                    runtime.interrupt_turn = interrupt_turn  # type: ignore[method-assign]

                    receipt = runtime.queue_task_graph_run(
                        {
                            "graph_id": graph["graph_id"],
                            "budget": {"limits": {"total_tokens": 10}},
                        }
                    )
                    run_id = str(receipt["live_run"]["run_id"])
                    self.assertTrue(started.wait(timeout=2))
                    time.sleep(0.3)
                    cancellation = runtime.cancel_task_graph_run({"run_id": run_id, "notes": "Cancel live run"})
                    terminal = runtime._graph_scheduler.wait(run_id, timeout=3)
                    status = runtime.graph_run_status(run_id)
                    recovery = runtime.recover_task_graph_run({"run_id": run_id, "strategy": "resume_run"})

                    self.assertEqual(len(start_calls), 1)
                    self.assertEqual(interrupt_calls, [("thread-live", "turn-live")])
                    self.assertEqual(terminal["status"], "completed")  # type: ignore[index]
                    self.assertEqual(terminal["result_status"], "cancelled")  # type: ignore[index]
                    self.assertEqual(cancellation["cancellation"]["interrupt_results"][0]["ok"], True)
                    self.assertEqual(status["run"]["status"], "cancelled")
                    self.assertEqual(status["live_run"]["run_ref"]["latest_event_type"], "run_cancelled")
                    self.assertEqual(recovery["recovery"]["safe_to_resume"], False)
                    self.assertEqual(recovery["recovery"]["status"], "needs_review")
                finally:
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_retryable_live_failures_create_real_second_attempts_and_fallback_lineage(self) -> None:
        retry_messages = {
            "rate_limit": "429 rate limit retry-after: 0",
            "provider_5xx": "503 service unavailable",
            "transport_failure": "connection reset by peer",
        }
        for case_name, failure_text in retry_messages.items():
            with self.subTest(case=case_name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
                    try:
                        root = Path(temp_dir)
                        workspace = root / "workspace"
                        (workspace / "PRIVATE").mkdir(parents=True)
                        (workspace / ".astrabridge").mkdir()
                        projects = ProjectService(
                            store_path=root / "projects.json",
                            session_path=root / "current_project.json",
                        )
                        projects.create_project("Scheduler retry", root / "scheduler.abproj", workspace_root=workspace)
                        tasks = TaskService(projects)
                        tasks.create_task("Scheduler task")
                        graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                        node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                        node_id = next(iter(node_map))
                        node_map[node_id]["provider_id"] = "qwen"
                        node_map[node_id]["model_id"] = "qwen3.7-max-2026-06-08"
                        node_map[node_id]["execution_policy"] = {
                            "retry_policy": {
                                "max_attempts": 2,
                                "base_delay_ms": 0,
                                "max_delay_ms": 0,
                                "jitter_ms": 0,
                                "allow_model_fallback": True,
                            }
                        }
                        runtime = RuntimeService(
                            projects,
                            ModalService(projects.require_shell_state_root),
                            task_service=tasks,
                        )
                        try:
                            seen_models: list[str] = []

                            def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                                seen_models.append(str(kwargs.get("model") or ""))
                                attempt = len(seen_models)
                                return {"thread_id": f"thread-{attempt}", "turn": {"id": f"turn-{attempt}"}}

                            self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn)
                            runtime._wait_for_probe_turn_terminal = (  # type: ignore[method-assign]
                                lambda _client, **kwargs: {
                                    "id": kwargs.get("thread_id"),
                                    "turns": [
                                        {
                                            "id": kwargs.get("turn_id"),
                                            "status": "failed" if str(kwargs.get("turn_id") or "") == "turn-1" else "completed",
                                        }
                                    ],
                                }
                            )
                            runtime._probe_turn_result = (  # type: ignore[method-assign]
                                lambda _thread, turn_id="": (
                                    ("failed", failure_text, "")
                                    if str(turn_id or "") == "turn-1"
                                    else ("completed", '{"human_summary":"Recovered","machine_result":{"goal":"retry-complete","next_nodes":[]}}', "")
                                )
                            )

                            receipt = runtime.queue_task_graph_run(
                                {
                                    "graph_id": graph["graph_id"],
                                    "budget": {"limits": {"total_tokens": 10}},
                                }
                            )
                            run_id = str(receipt["live_run"]["run_id"])
                            terminal = runtime._graph_scheduler.wait(run_id, timeout=6)
                            status = runtime.graph_run_status(run_id)
                            attempts = [
                                item
                                for item in list(tasks.durable_run_store().load_run(run_id, include_events=True)["node_run_states"] or [])
                                if isinstance(item, dict) and str(item.get("node_id") or "") == node_id
                            ]

                            self.assertEqual(terminal["result_status"], "completed")  # type: ignore[index]
                            self.assertEqual(status["run"]["status"], "completed")
                            self.assertEqual(len(seen_models), 2)
                            self.assertEqual(seen_models[0], "qwen3.7-max-2026-06-08")
                            self.assertEqual(seen_models[1], "qwen3.7-plus")
                            self.assertEqual([int(item.get("attempt_count") or 0) for item in attempts], [1, 2])
                            self.assertEqual(str(attempts[0].get("model_id") or ""), "qwen3.7-max-2026-06-08")
                            self.assertEqual(str(attempts[1].get("model_id") or ""), "qwen3.7-plus")
                        finally:
                            runtime.shutdown()
                    finally:
                        if previous_runtime_root is None:
                            os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                        else:
                            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_invalid_output_permission_denied_and_schema_rejection_do_not_auto_retry(self) -> None:
        cases = {
            "invalid_output": ("completed", "Completed"),
            "permission_denied": ("failed", "permission denied"),
            "invalid_request_shape": ("failed", "400 client error: bad request invalid request shape"),
        }
        for case_name, (terminal_status, final_text) in cases.items():
            with self.subTest(case=case_name):
                with tempfile.TemporaryDirectory() as temp_dir:
                    previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
                    try:
                        root = Path(temp_dir)
                        workspace = root / "workspace"
                        (workspace / "PRIVATE").mkdir(parents=True)
                        (workspace / ".astrabridge").mkdir()
                        projects = ProjectService(
                            store_path=root / "projects.json",
                            session_path=root / "current_project.json",
                        )
                        projects.create_project("Scheduler no-retry", root / "scheduler.abproj", workspace_root=workspace)
                        tasks = TaskService(projects)
                        tasks.create_task("Scheduler task")
                        graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                        node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                        node_id = next(iter(node_map))
                        node_map[node_id]["provider_id"] = "qwen"
                        node_map[node_id]["model_id"] = "qwen3.7-max-2026-06-08"
                        node_map[node_id]["execution_policy"] = {
                            "retry_policy": {
                                "max_attempts": 3,
                                "base_delay_ms": 0,
                                "max_delay_ms": 0,
                                "jitter_ms": 0,
                                "allow_model_fallback": True,
                            }
                        }
                        runtime = RuntimeService(
                            projects,
                            ModalService(projects.require_shell_state_root),
                            task_service=tasks,
                        )
                        try:
                            seen_models: list[str] = []

                            def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                                seen_models.append(str(kwargs.get("model") or ""))
                                return {"thread_id": "thread-1", "turn": {"id": "turn-1"}}

                            self._configure_live_runtime(
                                runtime,
                                node_map=node_map,
                                start_turn_impl=start_turn,
                                terminal_status=terminal_status,
                                final_text=final_text,
                            )
                            receipt = runtime.queue_task_graph_run(
                                {
                                    "graph_id": graph["graph_id"],
                                    "budget": {"limits": {"total_tokens": 10}},
                                }
                            )
                            run_id = str(receipt["live_run"]["run_id"])
                            terminal = runtime._graph_scheduler.wait(run_id, timeout=3)
                            status = runtime.graph_run_status(run_id)
                            attempts = [
                                item
                                for item in list(tasks.durable_run_store().load_run(run_id, include_events=True)["node_run_states"] or [])
                                if isinstance(item, dict) and str(item.get("node_id") or "") == node_id
                            ]

                            self.assertEqual(terminal["result_status"], "failed")  # type: ignore[index]
                            self.assertEqual(status["run"]["status"], "failed")
                            self.assertEqual(len(seen_models), 1)
                            self.assertEqual([int(item.get("attempt_count") or 0) for item in attempts], [1])
                        finally:
                            runtime.shutdown()
                    finally:
                        if previous_runtime_root is None:
                            os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                        else:
                            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_structured_agent_envelopes_drive_downstream_nodes_without_human_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler envelope", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    start_turn_calls: list[str] = []

                    def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                        worker_thread_id = str(kwargs.get("thread_id") or "")
                        node_id = worker_thread_id.removeprefix("worker-")
                        start_turn_calls.append(node_id)
                        return {"thread_id": f"exec-{node_id}", "turn": {"id": f"turn-{node_id}"}}

                    self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn)
                    runtime._wait_for_probe_turn_terminal = lambda _client, **kwargs: {  # type: ignore[method-assign]
                        "id": kwargs.get("thread_id"),
                        "turns": [{"id": kwargs.get("turn_id"), "status": "completed"}],
                    }

                    def probe_turn_result(_thread: dict[str, object], turn_id: str = "") -> tuple[str, str, str]:
                        if turn_id == "turn-node_supervisor":
                            return ("completed", '{"human_summary":"","machine_result":{"plan":"delegate-to-worker","next_workers":["node_worker"]}}', "")
                        if turn_id == "turn-node_worker":
                            return ("completed", '{"human_summary":"Worker finished","machine_result":{"result":"done","confidence":"high"}}', "")
                        return ("completed", '{"human_summary":"Synthesis finished","machine_result":{"summary":"done","decision":"ship"}}', "")

                    runtime._probe_turn_result = probe_turn_result  # type: ignore[method-assign]
                    receipt = runtime.queue_task_graph_run(
                        {
                            "graph_id": graph["graph_id"],
                            "budget": {"limits": {"total_tokens": 30}},
                        }
                    )
                    run_id = str(receipt["live_run"]["run_id"])
                    terminal = runtime._graph_scheduler.wait(run_id, timeout=10)
                    status = runtime.graph_run_status(run_id)
                    envelopes = [
                        dict(item)
                        for item in list(status["run"].get("agent_envelopes") or [])
                        if isinstance(item, dict)
                    ]
                    delivery_ledger = [
                        dict(item)
                        for item in list(status["run"].get("delivery_ledger") or [])
                        if isinstance(item, dict)
                    ]
                    worker_envelope = next(
                        item
                        for item in envelopes
                        if str(dict(item.get("metadata") or {}).get("target_node_id") or "") == "node_worker"
                    )
                    content_kinds = [
                        str(part.get("kind") or "").strip()
                        for part in list(worker_envelope.get("content") or [])
                        if isinstance(part, dict)
                    ]
                    content_part_types = [
                        str(dict(part.get("metadata") or {}).get("part_type") or "").strip()
                        for part in list(worker_envelope.get("content") or [])
                        if isinstance(part, dict)
                    ]
                    event_types = [str(item.get("event_type") or "") for item in delivery_ledger]

                    self.assertEqual(terminal["result_status"], "completed")  # type: ignore[index]
                    self.assertEqual(status["run"]["status"], "completed")
                    self.assertEqual(start_turn_calls.count("node_worker"), 1)
                    self.assertIn("json", content_kinds)
                    self.assertNotIn("human_summary", content_part_types)
                    self.assertIn("handoff_created", event_types)
                    self.assertIn("handoff_acknowledged", event_types)
                    self.assertTrue(
                        str(dict(worker_envelope.get("metadata") or {}).get("correlation_id") or "").strip()
                    )
                    self.assertTrue(
                        any(worker_envelope["envelope_id"] in str(item.get("event_id") or "") for item in delivery_ledger)
                    )
                    serialized = json.dumps({"envelopes": envelopes, "delivery_ledger": delivery_ledger}, ensure_ascii=False)
                    self.assertNotIn("private_reasoning", serialized)
                finally:
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_invalid_agent_envelope_fails_before_target_provider_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler invalid envelope", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    start_turn_calls: list[str] = []

                    def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                        worker_thread_id = str(kwargs.get("thread_id") or "")
                        node_id = worker_thread_id.removeprefix("worker-")
                        start_turn_calls.append(node_id)
                        return {"thread_id": f"exec-{node_id}", "turn": {"id": f"turn-{node_id}"}}

                    self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn)
                    runtime._wait_for_probe_turn_terminal = lambda _client, **kwargs: {  # type: ignore[method-assign]
                        "id": kwargs.get("thread_id"),
                        "turns": [{"id": kwargs.get("turn_id"), "status": "completed"}],
                    }
                    runtime._probe_turn_result = (  # type: ignore[method-assign]
                        lambda _thread, turn_id="": (
                            ("completed", '{"human_summary":"Planner finished","machine_result":{"plan":"delegate","next_workers":["node_worker"]}}', "")
                            if turn_id == "turn-node_supervisor"
                            else ("completed", '{"human_summary":"Unexpected downstream start","machine_result":{"result":"bad","confidence":"low"}}', "")
                        )
                    )

                    original_record_graph_worker_output = runtime._tasks.record_graph_worker_output

                    def tampering_record_graph_worker_output(payload: dict[str, object], *, graph_definition: dict[str, object] | None = None) -> dict[str, object]:
                        result = original_record_graph_worker_output(payload, graph_definition=graph_definition)
                        if str(payload.get("node_id") or "") == "node_supervisor":
                            binding = dict(result.get("worker_binding") or {})
                            handoff = dict(list(binding.get("downstream_handoffs") or [])[0] or {})
                            envelope_path = workspace / str(dict(handoff.get("downstream_input") or {}).get("agent_envelope_path") or "")
                            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
                            envelope["recipient"].pop("agent_id", None)
                            envelope_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
                        return result

                    runtime._tasks.record_graph_worker_output = tampering_record_graph_worker_output  # type: ignore[method-assign]
                    receipt = runtime.queue_task_graph_run(
                        {
                            "graph_id": graph["graph_id"],
                            "budget": {"limits": {"total_tokens": 30}},
                        }
                    )
                    run_id = str(receipt["live_run"]["run_id"])
                    deadline = time.monotonic() + 20.0
                    terminal = runtime._graph_scheduler.get(run_id) or {}
                    while time.monotonic() < deadline:
                        terminal = runtime._graph_scheduler.wait(run_id, timeout=0.5) or {}
                        if str(terminal.get("status") or "").strip() == "completed":
                            break
                    status = runtime.graph_run_status(run_id)
                    delivery_ledger = [
                        dict(item)
                        for item in list(status["run"].get("delivery_ledger") or [])
                        if isinstance(item, dict)
                    ]

                    self.assertEqual(terminal["result_status"], "partial")  # type: ignore[index]
                    self.assertEqual(status["run"]["status"], "partial")
                    self.assertEqual(start_turn_calls, ["node_supervisor"])
                    self.assertIn("handoff_rejected", [str(item.get("event_type") or "") for item in delivery_ledger])
                finally:
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_typed_inputs_drive_fanout_fanin_without_preview_text_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler fanout typed inputs", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
                orchestration_graph = tasks._orchestration_graph_for_task_graph(graph)
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    prompts: dict[str, str] = {}
                    merge_input_port_ids = sorted(
                        {
                            str(binding.get("to_port_id") or "").strip()
                            for edge in list(orchestration_graph.get("edges") or [])
                            if isinstance(edge, dict) and str(edge.get("to_node_id") or "").strip() == "node_merge"
                            for binding in list(dict(edge.get("handoff_contract") or {}).get("port_bindings") or [])
                            if isinstance(binding, dict) and str(binding.get("to_port_id") or "").strip()
                        }
                    )

                    def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                        worker_thread_id = str(kwargs.get("thread_id") or "")
                        node_id = worker_thread_id.removeprefix("worker-")
                        prompts[node_id] = str(kwargs.get("text") or "")
                        return {"thread_id": f"exec-{node_id}", "turn": {"id": f"turn-{node_id}"}}

                    self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn)
                    runtime._wait_for_probe_turn_terminal = lambda _client, **kwargs: {  # type: ignore[method-assign]
                        "id": kwargs.get("thread_id"),
                        "turns": [{"id": kwargs.get("turn_id"), "status": "completed"}],
                    }

                    def probe_turn_result(_thread: dict[str, object], turn_id: str = "") -> tuple[str, str, str]:
                        if turn_id == "turn-node_supervisor":
                            return ("completed", '{"human_summary":"","machine_result":{"questions":["q1","q2"],"branches":["node_research_a","node_research_b"]}}', "")
                        if turn_id == "turn-node_research_a":
                            return ("completed", '{"human_summary":"","machine_result":{"findings":["a"],"sources":["https://a.example"]}}', "")
                        if turn_id == "turn-node_research_b":
                            return ("completed", '{"human_summary":"","machine_result":{"findings":["b"],"sources":["https://b.example"]}}', "")
                        return ("completed", '{"human_summary":"","machine_result":{"synthesis":"merged","gaps":[]}}', "")

                    runtime._probe_turn_result = probe_turn_result  # type: ignore[method-assign]
                    receipt = runtime.queue_task_graph_run(
                        {
                            "graph_id": graph["graph_id"],
                            "budget": {"limits": {"total_tokens": 40}},
                        }
                    )
                    run_id = str(receipt["live_run"]["run_id"])
                    terminal = runtime._graph_scheduler.wait(run_id, timeout=8)
                    status = runtime.graph_run_status(run_id)

                    self.assertEqual(terminal["result_status"], "completed")  # type: ignore[index]
                    self.assertEqual(status["run"]["status"], "completed")
                    self.assertIn("typed_inputs=", prompts["node_research_a"])
                    self.assertIn("typed_inputs=", prompts["node_merge"])
                    self.assertIn('"questions"', prompts["node_research_a"])
                    self.assertIn('"findings"', prompts["node_merge"])
                    self.assertTrue(all(port_id in prompts["node_merge"] for port_id in merge_input_port_ids))
                    self.assertIn(
                        "treat them as authoritative; previews and summaries are advisory only",
                        prompts["node_merge"],
                    )
                finally:
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_neutral_context_bundle_preserves_typed_inputs_artifacts_and_cross_provider_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler neutral context", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                node_map["node_supervisor"]["provider_id"] = "qwen"
                node_map["node_worker"]["provider_id"] = "kimi"
                node_map["node_synth"]["provider_id"] = "glm"
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    dispatched: dict[str, dict[str, object]] = {}

                    def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                        worker_thread_id = str(kwargs.get("thread_id") or "")
                        node_id = worker_thread_id.removeprefix("worker-")
                        dispatched[node_id] = {
                            "text": str(kwargs.get("text") or ""),
                            "attachments": deepcopy(list(kwargs.get("attachments") or [])),
                        }
                        return {"thread_id": f"exec-{node_id}", "turn": {"id": f"turn-{node_id}"}}

                    self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn)
                    runtime._wait_for_probe_turn_terminal = lambda _client, **kwargs: {  # type: ignore[method-assign]
                        "id": kwargs.get("thread_id"),
                        "turns": [{"id": kwargs.get("turn_id"), "status": "completed"}],
                    }

                    def probe_turn_result(_thread: dict[str, object], turn_id: str = "") -> tuple[str, str, str]:
                        if turn_id == "turn-node_supervisor":
                            return ("completed", '{"human_summary":"","machine_result":{"plan":"delegate-to-worker","next_workers":["node_worker"]}}', "")
                        if turn_id == "turn-node_worker":
                            return ("completed", '{"human_summary":"Worker finished","machine_result":{"result":"done","confidence":"high"}}', "")
                        return ("completed", '{"human_summary":"Synthesis finished","machine_result":{"summary":"done","decision":"ship"}}', "")

                    runtime._probe_turn_result = probe_turn_result  # type: ignore[method-assign]
                    projection_threads = {
                        "worker-node_supervisor": {
                            "provider_id": "qwen",
                            "messages": [
                                NeutralMessage(role="assistant", text="Supervisor visible summary."),
                                NeutralMessage(
                                    role="assistant",
                                    text="",
                                    tool_call_id="call-super-1",
                                    tool_name="web_search",
                                    provider_data={"arguments_json": '{"q":"step10"}'},
                                ),
                            ],
                            "artifacts": [
                                ReasoningArtifact(
                                    provider_id="qwen",
                                    model_id="qwen3-coder-plus",
                                    kind="reasoning_state",
                                    replayable=True,
                                    payload={
                                        "summary": "Supervisor internal summary.",
                                        "private_reasoning": "secret",
                                        "provider_id": "qwen",
                                        "model_id": "qwen3-coder-plus",
                                    },
                                )
                            ],
                        },
                        "worker-node_worker": {
                            "provider_id": "kimi",
                            "messages": [
                                NeutralMessage(role="assistant", text="Worker visible summary."),
                                NeutralMessage(
                                    role="assistant",
                                    text="",
                                    tool_call_id="call-worker-1",
                                    tool_name="read_file",
                                    provider_data={"arguments_json": '{"path":"README.md"}'},
                                ),
                                NeutralMessage(
                                    role="tool",
                                    text="Read completed.",
                                    tool_call_id="call-worker-1",
                                    content_parts=[{"type": "output_text", "text": "README contents"}],
                                ),
                            ],
                            "artifacts": [],
                        },
                    }
                    runtime._thread_for_handoff_projection = lambda source_thread_id: (  # type: ignore[method-assign]
                        {"id": source_thread_id} if str(source_thread_id or "") in projection_threads else None
                    )
                    runtime._thread_provider_id_for_projection = lambda thread: projection_threads[str(thread.get("id") or "")]["provider_id"]  # type: ignore[method-assign]
                    runtime._thread_projection_inputs = lambda thread: (  # type: ignore[method-assign]
                        projection_threads[str(thread.get("id") or "")]["messages"],
                        projection_threads[str(thread.get("id") or "")]["artifacts"],
                    )

                    receipt = runtime.queue_task_graph_run(
                        {
                            "graph_id": graph["graph_id"],
                            "budget": {"limits": {"total_tokens": 40}},
                        }
                    )
                    run_id = str(receipt["live_run"]["run_id"])
                    terminal = runtime._graph_scheduler.wait(run_id, timeout=8)
                    status = runtime.graph_run_status(run_id)

                    self.assertEqual(terminal["result_status"], "completed")  # type: ignore[index]
                    self.assertEqual(status["run"]["status"], "completed")
                    self.assertIn("Use the attached neutral context bundle", str(dispatched["node_worker"]["text"]))
                    self.assertIn("Use the attached neutral context bundle", str(dispatched["node_synth"]["text"]))

                    worker_attachments = [dict(item) for item in list(dispatched["node_worker"]["attachments"]) if isinstance(item, dict)]
                    synth_attachments = [dict(item) for item in list(dispatched["node_synth"]["attachments"]) if isinstance(item, dict)]
                    worker_context = next(item for item in worker_attachments if str(item.get("source") or "") == "graph_neutral_context_bundle")
                    synth_context = next(item for item in synth_attachments if str(item.get("source") or "") == "graph_neutral_context_bundle")
                    worker_bundle = json.loads(Path(str(worker_context["path"])).read_text(encoding="utf-8"))
                    synth_bundle = json.loads(Path(str(synth_context["path"])).read_text(encoding="utf-8"))

                    self.assertEqual(worker_bundle["target_provider_id"], "kimi")
                    self.assertEqual(worker_bundle["typed_inputs"]["edge_supervisor_worker_input"]["plan"], "delegate-to-worker")
                    self.assertIn({"source_provider": "qwen", "target_provider": "kimi"}, worker_bundle["provider_pairs"])
                    self.assertEqual(worker_bundle["total_repaired_tool_pairs"], 1)
                    self.assertTrue(worker_bundle["provider_private_state_removed"])
                    self.assertNotIn("secret", json.dumps(worker_bundle, ensure_ascii=False))
                    self.assertGreaterEqual(len(worker_bundle["incoming_handoffs"][0]["artifact_refs"]), 1)

                    self.assertEqual(synth_bundle["target_provider_id"], "glm")
                    self.assertEqual(synth_bundle["typed_inputs"]["edge_worker_synth_input"]["result"], "done")
                    self.assertIn({"source_provider": "kimi", "target_provider": "glm"}, synth_bundle["provider_pairs"])
                    self.assertEqual(synth_bundle["total_repaired_tool_pairs"], 0)
                    self.assertTrue(any(str(item.get("source") or "") == "graph_handoff_artifact" for item in synth_attachments))
                    self.assertNotIn("secret", json.dumps(synth_bundle, ensure_ascii=False))
                finally:
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_neutral_context_bundle_truncation_is_deterministic_and_diagnosed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler neutral truncation", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    dispatched: dict[str, list[dict[str, object]]] = {}

                    def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                        worker_thread_id = str(kwargs.get("thread_id") or "")
                        node_id = worker_thread_id.removeprefix("worker-")
                        dispatched[node_id] = deepcopy(list(kwargs.get("attachments") or []))
                        return {"thread_id": f"exec-{node_id}", "turn": {"id": f"turn-{node_id}"}}

                    self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn)
                    runtime._wait_for_probe_turn_terminal = lambda _client, **kwargs: {  # type: ignore[method-assign]
                        "id": kwargs.get("thread_id"),
                        "turns": [{"id": kwargs.get("turn_id"), "status": "completed"}],
                    }
                    runtime._probe_turn_result = (  # type: ignore[method-assign]
                        lambda _thread, turn_id="": (
                            ("completed", '{"human_summary":"","machine_result":{"plan":"delegate-to-worker","next_workers":["node_worker"]}}', "")
                            if turn_id == "turn-node_supervisor"
                            else (
                                ("completed", '{"human_summary":"Worker finished","machine_result":{"result":"done","confidence":"high"}}', "")
                                if turn_id == "turn-node_worker"
                                else ("completed", '{"human_summary":"Synthesis finished","machine_result":{"summary":"done","decision":"ship"}}', "")
                            )
                        )
                    )
                    projection_threads = {
                        "worker-node_supervisor": {
                            "provider_id": "qwen",
                            "messages": [
                                NeutralMessage(role="assistant", text=f"projected message {index}")
                                for index in range(1, 6)
                            ],
                            "artifacts": [],
                        }
                    }
                    runtime._thread_for_handoff_projection = lambda source_thread_id: (  # type: ignore[method-assign]
                        {"id": source_thread_id} if str(source_thread_id or "") in projection_threads else None
                    )
                    runtime._thread_provider_id_for_projection = lambda thread: projection_threads[str(thread.get("id") or "")]["provider_id"]  # type: ignore[method-assign]
                    runtime._thread_projection_inputs = lambda thread: (  # type: ignore[method-assign]
                        projection_threads[str(thread.get("id") or "")]["messages"],
                        projection_threads[str(thread.get("id") or "")]["artifacts"],
                    )

                    with patch("astrabridge_sidecar.runtime_service.GRAPH_LIVE_NEUTRAL_CONTEXT_MAX_HISTORY_MESSAGES", 2):
                        receipt = runtime.queue_task_graph_run(
                            {
                                "graph_id": graph["graph_id"],
                                "budget": {"limits": {"total_tokens": 30}},
                            }
                        )
                        run_id = str(receipt["live_run"]["run_id"])
                        terminal = runtime._graph_scheduler.wait(run_id, timeout=8)
                    self.assertEqual(terminal["result_status"], "completed")  # type: ignore[index]
                    worker_context = next(
                        dict(item)
                        for item in list(dispatched["node_worker"])
                        if isinstance(item, dict) and str(item.get("source") or "") == "graph_neutral_context_bundle"
                    )
                    worker_bundle = json.loads(Path(str(worker_context["path"])).read_text(encoding="utf-8"))
                    projected_messages = list(dict(worker_bundle["incoming_handoffs"][0]["projected_history"]).get("messages") or [])
                    truncation = dict(worker_bundle["incoming_handoffs"][0]["projection_truncation"] or {})

                    self.assertEqual([str(item.get("content") or "") for item in projected_messages], ["projected message 4", "projected message 5"])
                    self.assertTrue(truncation["applied"])
                    self.assertIn("keeping the newest messages", " ".join(truncation["reasons"]))
                    self.assertTrue(worker_bundle["truncation"]["applied"])
                finally:
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_machine_result_schema_violation_fails_closed_without_raw_text_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler schema failure", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    self._configure_live_runtime(
                        runtime,
                        node_map=node_map,
                        start_turn_impl=lambda _profile, **_kwargs: {"thread_id": "exec-node_start_here", "turn": {"id": "turn-node_start_here"}},
                        terminal_status="completed",
                        final_text='{"human_summary":"Completed","machine_result":{"goal":"missing-next-nodes"}}',
                    )
                    receipt = runtime.queue_task_graph_run(
                        {
                            "graph_id": graph["graph_id"],
                            "budget": {"limits": {"total_tokens": 20}},
                        }
                    )
                    run_id = str(receipt["live_run"]["run_id"])
                    terminal = runtime._graph_scheduler.wait(run_id, timeout=6)
                    status = runtime.graph_run_status(run_id)
                    binding = dict(list(status["run"].get("worker_bindings") or [])[0] or {})
                    output_path = workspace / str(dict(binding.get("output_summary") or {}).get("artifact_bundle_path") or "")
                    output_bundle = json.loads(output_path.read_text(encoding="utf-8"))

                    self.assertEqual(terminal["result_status"], "failed")  # type: ignore[index]
                    self.assertEqual(status["run"]["status"], "failed")
                    self.assertEqual(
                        str(dict(list(status["run"].get("node_run_states") or [])[0] or {}).get("outcome") or ""),
                        "schema_violation",
                    )
                    self.assertEqual(output_bundle["machine_result"]["status"], "schema_violation")
                    self.assertNotIn("raw_text", output_bundle["machine_result"])
                    self.assertIn("received_machine_result", output_bundle["machine_result"])
                finally:
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_missing_typed_handoff_projection_emits_explicit_compatibility_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler compatibility gate", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    start_turn_calls: list[str] = []

                    def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                        worker_thread_id = str(kwargs.get("thread_id") or "")
                        node_id = worker_thread_id.removeprefix("worker-")
                        start_turn_calls.append(node_id)
                        return {"thread_id": f"exec-{node_id}", "turn": {"id": f"turn-{node_id}"}}

                    self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn)
                    runtime._wait_for_probe_turn_terminal = lambda _client, **kwargs: {  # type: ignore[method-assign]
                        "id": kwargs.get("thread_id"),
                        "turns": [{"id": kwargs.get("turn_id"), "status": "completed"}],
                    }
                    runtime._probe_turn_result = (  # type: ignore[method-assign]
                        lambda _thread, turn_id="": (
                            ("completed", '{"human_summary":"Planner finished","machine_result":{"plan":"delegate","next_workers":["node_worker"]}}', "")
                            if turn_id == "turn-node_supervisor"
                            else ("completed", '{"human_summary":"Unexpected downstream start","machine_result":{"result":"bad","confidence":"low"}}', "")
                        )
                    )
                    original_record_graph_worker_output = runtime._tasks.record_graph_worker_output

                    def remove_typed_handoff(payload: dict[str, object], *, graph_definition: dict[str, object] | None = None) -> dict[str, object]:
                        result = original_record_graph_worker_output(payload, graph_definition=graph_definition)
                        if str(payload.get("node_id") or "") == "node_supervisor":
                            binding = dict(result.get("worker_binding") or {})
                            handoff = dict(list(binding.get("downstream_handoffs") or [])[0] or {})
                            envelope_path = workspace / str(dict(handoff.get("downstream_input") or {}).get("agent_envelope_path") or "")
                            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
                            envelope["metadata"].pop("typed_handoff", None)
                            envelope_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
                        return result

                    runtime._tasks.record_graph_worker_output = remove_typed_handoff  # type: ignore[method-assign]
                    receipt = runtime.queue_task_graph_run(
                        {
                            "graph_id": graph["graph_id"],
                            "budget": {"limits": {"total_tokens": 30}},
                        }
                    )
                    run_id = str(receipt["live_run"]["run_id"])
                    terminal = runtime._graph_scheduler.wait(run_id, timeout=6)
                    status = runtime.graph_run_status(run_id)
                    event_refs = [
                        dict(item)
                        for item in list(status["run"].get("event_refs") or [])
                        if isinstance(item, dict)
                    ]
                    rejection = next(
                        item
                        for item in event_refs
                        if str(item.get("event_type") or "") == "handoff_rejected"
                    )

                    self.assertEqual(terminal["result_status"], "partial")  # type: ignore[index]
                    self.assertEqual(status["run"]["status"], "partial")
                    self.assertEqual(start_turn_calls, ["node_supervisor"])
                    self.assertIn("typed_handoff", str(dict(rejection.get("payload") or {}).get("error") or ""))
                    self.assertIn("legacy raw-text fallback is blocked", str(dict(rejection.get("payload") or {}).get("error") or ""))
                finally:
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_duplicate_delivery_idempotency_key_does_not_start_target_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            run_id = ""
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Scheduler duplicate delivery", root / "scheduler.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Scheduler task")
                graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
                node_map = {str(item["node_id"]): dict(item) for item in graph["nodes"]}
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                )
                try:
                    start_turn_calls: list[str] = []

                    def start_turn(_profile: dict[str, object], **kwargs: object) -> dict[str, object]:
                        worker_thread_id = str(kwargs.get("thread_id") or "")
                        node_id = worker_thread_id.removeprefix("worker-")
                        start_turn_calls.append(node_id)
                        return {"thread_id": f"exec-{node_id}", "turn": {"id": f"turn-{node_id}"}}

                    self._configure_live_runtime(runtime, node_map=node_map, start_turn_impl=start_turn)
                    runtime._wait_for_probe_turn_terminal = lambda _client, **kwargs: {  # type: ignore[method-assign]
                        "id": kwargs.get("thread_id"),
                        "turns": [{"id": kwargs.get("turn_id"), "status": "completed"}],
                    }

                    def probe_turn_result(_thread: dict[str, object], turn_id: str = "") -> tuple[str, str, str]:
                        if turn_id == "turn-node_supervisor":
                            return ("completed", '{"human_summary":"Planner finished","machine_result":{"plan":"delegate","next_workers":["node_worker"]}}', "")
                        if turn_id == "turn-node_worker":
                            return ("completed", '{"human_summary":"Worker finished","machine_result":{"result":"done","confidence":"high"}}', "")
                        return ("completed", '{"human_summary":"Synthesis finished","machine_result":{"summary":"done","decision":"ship"}}', "")

                    runtime._probe_turn_result = probe_turn_result  # type: ignore[method-assign]
                    original_record_graph_worker_output = runtime._tasks.record_graph_worker_output

                    def duplicating_record_graph_worker_output(payload: dict[str, object], *, graph_definition: dict[str, object] | None = None) -> dict[str, object]:
                        result = original_record_graph_worker_output(payload, graph_definition=graph_definition)
                        if str(payload.get("node_id") or "") == "node_supervisor":
                            binding = dict(result.get("worker_binding") or {})
                            handoffs = [dict(item) for item in list(binding.get("downstream_handoffs") or []) if isinstance(item, dict)]
                            if handoffs:
                                binding["downstream_handoffs"] = [*handoffs, deepcopy(handoffs[0])]
                                result["worker_binding"] = binding
                        return result

                    runtime._tasks.record_graph_worker_output = duplicating_record_graph_worker_output  # type: ignore[method-assign]
                    receipt = runtime.queue_task_graph_run(
                        {
                            "graph_id": graph["graph_id"],
                            "budget": {"limits": {"total_tokens": 30}},
                        }
                    )
                    run_id = str(receipt["live_run"]["run_id"])
                    deadline = time.monotonic() + 20.0
                    terminal = runtime._graph_scheduler.get(run_id) or {}
                    status = runtime.graph_run_status(run_id)
                    while time.monotonic() < deadline:
                        terminal = runtime._graph_scheduler.wait(run_id, timeout=0.5) or {}
                        status = runtime.graph_run_status(run_id)
                        if str(status["run"]["status"] or "").strip() == "completed":
                            break
                    terminal = runtime._graph_scheduler.wait(run_id, timeout=5) or terminal

                    self.assertEqual(status["run"]["status"], "completed")
                    self.assertEqual(terminal["status"], "completed")  # type: ignore[index]
                    self.assertEqual(start_turn_calls.count("node_worker"), 1)
                finally:
                    if run_id:
                        runtime._graph_scheduler.wait(run_id, timeout=5)
                    runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root


if __name__ == "__main__":
    unittest.main()
