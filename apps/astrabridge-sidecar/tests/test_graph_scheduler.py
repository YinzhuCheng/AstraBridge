from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
import sys
import os
import tempfile


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.graph_scheduler import DurableGraphScheduler  # noqa: E402
from astrabridge_sidecar.modal_service import ModalService  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.runtime_service import RuntimeService  # noqa: E402
from astrabridge_sidecar.task_service import TaskService  # noqa: E402


class DurableGraphSchedulerTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
