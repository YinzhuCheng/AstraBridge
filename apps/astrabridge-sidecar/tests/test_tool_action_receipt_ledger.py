from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.coding_kernel.turn_loop import RuntimeToolFacade
from astrabridge_sidecar.project_tools_service import ProjectToolsService
from astrabridge_sidecar.providers.ir import ToolCall
from astrabridge_sidecar.tool_action_ledger import (
    ToolActionImmutableConflict,
    ToolActionReceiptLedger,
    ToolActionValidationError,
)


class _ProjectsStub:
    def __init__(self, root: Path) -> None:
        self._root = root
        self.current_project: dict[str, object] = {}

    def require_workspace_root(self) -> Path:
        return self._root


class _RuntimeStub:
    def __init__(self) -> None:
        self.supervisor_events: list[dict[str, object]] = []

    def record_supervisor_event(self, payload: dict[str, object]) -> None:
        self.supervisor_events.append(dict(payload))


class _CheckpointsStub:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    def create(self, payload: dict[str, object], *, system: bool = False) -> dict[str, object]:
        entry = {
            "save_id": f"save-{len(self.created) + 1}",
            "description": str(payload.get("description") or ""),
            "system": bool(system),
        }
        self.created.append(entry)
        return {"save": entry}

    def list_saves(self) -> dict[str, object]:
        return {"saves": list(reversed(self.created))}


class ToolActionReceiptLedgerTests(unittest.TestCase):
    def _tools(self, root: Path) -> tuple[ProjectToolsService, _RuntimeStub, _CheckpointsStub]:
        runtime = _RuntimeStub()
        checkpoints = _CheckpointsStub()
        return ProjectToolsService(_ProjectsStub(root), runtime, checkpoints=checkpoints), runtime, checkpoints

    def test_raw_wrapper_cannot_reach_native_command_dispatch(self) -> None:
        invoked: list[dict[str, object]] = []
        facade = RuntimeToolFacade(
            SimpleNamespace(run_command=lambda payload: invoked.append(payload) or {"ok": True}),
            profile_id="provider-default",
            provider_id="provider",
            model_id="model-a",
            authority=SimpleNamespace(tier="A"),
            permission_mode="auto",
            thread_id="thread-a",
            turn_id="turn-a",
        )

        arguments, result, extra_items, tool_item = facade.execute(
            ToolCall(
                id="call-raw-command",
                name="run_command",
                arguments_json='{"raw":"{bad json}","command":"echo should-not-run"}',
            )
        )

        self.assertEqual(arguments, {})
        self.assertEqual(result["status"], "repairable")
        self.assertTrue(result["repairable"])
        self.assertEqual(tool_item["status"], "repairable")
        self.assertEqual(extra_items, [])
        self.assertEqual(invoked, [])

    def test_receipt_key_is_immutable_and_persists_only_safe_argument_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = ToolActionReceiptLedger(root)
            envelope = ledger.build_envelope(
                tool_name="run_command",
                arguments={"command": "echo command-text-must-not-be-persisted", "cwd": "src", "timeout_seconds": 30},
                lineage={"task_id": "task-a", "thread_id": "thread-a", "turn_id": "turn-a", "tool_call_id": "call-a"},
                authority={"tier": "A", "decision": "authorized", "permission_mode": "auto"},
                workspace={"workspace_version": "a" * 64, "checkpoint_version": "save-0"},
                idempotency_key="receipt-command-a",
            )
            self.assertEqual(ledger.admit(envelope)["decision"], "execute")
            receipt = ledger.complete(
                envelope,
                result={"ok": True, "status": "completed", "output": "output-text-must-not-be-persisted"},
            )
            persisted = ledger.path.read_text(encoding="utf-8")

            self.assertEqual(receipt["state"], "completed")
            self.assertIn("command_digest", persisted)
            self.assertNotIn("command-text-must-not-be-persisted", persisted)
            self.assertNotIn("output-text-must-not-be-persisted", persisted)

            conflicting = ledger.build_envelope(
                tool_name="run_command",
                arguments={"command": "echo a-different-command", "cwd": "src", "timeout_seconds": 30},
                lineage={"task_id": "task-a", "thread_id": "thread-a", "turn_id": "turn-a", "tool_call_id": "call-a"},
                authority={"tier": "A", "decision": "authorized", "permission_mode": "auto"},
                workspace={"workspace_version": "b" * 64, "checkpoint_version": "save-0"},
                idempotency_key="receipt-command-a",
            )
            with self.assertRaises(ToolActionImmutableConflict):
                ledger.admit(conflicting)

    def test_interrupted_receipt_cannot_be_downgraded_to_retryable_or_approval_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ledger = ToolActionReceiptLedger(Path(temp))
            envelope = ledger.build_envelope(
                tool_name="run_command",
                arguments={"command": "echo bounded", "timeout_seconds": 10},
                lineage={"task_id": "task-a", "thread_id": "thread-a", "turn_id": "turn-a", "tool_call_id": "call-a"},
                authority={"tier": "A", "decision": "approved", "permission_mode": "auto"},
                workspace={"workspace_version": "a" * 64, "checkpoint_version": "none"},
                idempotency_key="interrupted-state-protected",
            )
            ledger.admit(envelope)
            interrupted = ledger.interrupt(envelope, reason="interrupted after admission")
            retryable = ledger.record_retryable(envelope, reason="approval bridge unavailable")
            approval = ledger.record_approval_required(envelope, reason="approval requested")

            self.assertEqual(interrupted["state"], "interrupted")
            self.assertEqual(retryable["state"], "interrupted")
            self.assertEqual(approval["state"], "interrupted")

    def test_edit_apply_duplicate_reuses_receipt_without_second_checkpoint_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools, _runtime, checkpoints = self._tools(root)
            payload = {
                "path": "notes.txt",
                "content": "first write\n",
                "tool_call_id": "call-edit-once",
                "idempotency_key": "edit-once",
            }

            first = tools.edit_apply(payload)
            second = tools.edit_apply(payload)

            self.assertTrue(first["applied"])
            self.assertEqual(first["action_receipt"]["state"], "completed")
            self.assertEqual(second["status"], "duplicate")
            self.assertTrue(second["already_executed"])
            self.assertEqual(len(checkpoints.created), 1)
            self.assertEqual((root / "notes.txt").read_text(encoding="utf-8"), "first write\n")

    def test_checkpoint_duplicate_reuses_the_original_save_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tools, _runtime, checkpoints = self._tools(Path(temp))
            payload = {
                "description": "before a bounded tool action",
                "tool_call_id": "call-checkpoint-once",
                "idempotency_key": "checkpoint-once",
            }

            first = tools.create_checkpoint(payload)
            second = tools.create_checkpoint(payload)

            self.assertEqual(first["action_receipt"]["state"], "completed")
            self.assertEqual(second["status"], "duplicate")
            self.assertEqual(second["save"]["save_id"], first["save"]["save_id"])
            self.assertEqual(len(checkpoints.created), 1)

    def test_command_timeout_requires_recovery_before_same_action_can_run_again(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools, _runtime, _checkpoints = self._tools(root)
            calls: list[str] = []

            def fake_run(command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, object]:
                calls.append(command)
                if len(calls) == 1:
                    return {"returncode": None, "stdout": "partial", "stderr": "", "timed_out": True}
                return {"returncode": 0, "stdout": "done", "stderr": "", "timed_out": False}

            tools._run_shell_command = fake_run  # type: ignore[method-assign]
            payload = {
                "command": "python -m unittest -q",
                "tool_call_id": "call-timeout-once",
                "idempotency_key": "command-timeout-once",
            }

            timed_out = tools.run_tests(payload)
            blocked_retry = tools.run_tests(payload)
            self.assertTrue(timed_out["timed_out"])
            self.assertEqual(timed_out["action_receipt"]["state"], "interrupted")
            self.assertEqual(blocked_retry["status"], "recovery_required")
            self.assertEqual(len(calls), 1)
            recovered = tools.resolve_tool_action_recovery(
                "command-timeout-once",
                resolution="confirmed_not_applied",
            )
            rerun = tools.run_tests(payload)

            self.assertEqual(recovered["state"], "retryable")
            self.assertTrue(rerun["ok"])
            self.assertEqual(rerun["action_receipt"]["state"], "completed")
            self.assertEqual(len(calls), 2)

    def test_completed_command_duplicate_does_not_start_a_second_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tools, _runtime, _checkpoints = self._tools(Path(temp))
            calls: list[str] = []

            def completed_run(command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, object]:
                calls.append(command)
                return {"returncode": 0, "stdout": "done", "stderr": "", "timed_out": False}

            tools._run_shell_command = completed_run  # type: ignore[method-assign]
            payload = {
                "command": "python -m unittest -q",
                "tool_call_id": "call-command-once",
                "idempotency_key": "command-once",
            }

            first = tools.run_tests(payload)
            duplicate = tools.run_tests(payload)

            self.assertTrue(first["ok"])
            receipt = first["action_receipt"]
            self.assertEqual(receipt["lineage"]["tool_call_id"], "call-command-once")
            self.assertEqual(receipt["authority"]["decision"], "command_approval_accepted")
            self.assertEqual(len(receipt["workspace"]["workspace_version"]), 64)
            self.assertIn("checkpoint_version", receipt["workspace"])
            self.assertEqual(duplicate["status"], "duplicate")
            self.assertTrue(duplicate["already_executed"])
            self.assertEqual(len(calls), 1)

    def test_command_exception_is_interrupted_and_can_be_confirmed_applied_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools, _runtime, _checkpoints = self._tools(root)
            calls: list[str] = []

            def interrupted_run(command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, object]:
                calls.append(command)
                raise RuntimeError("simulated transport interruption")

            tools._run_shell_command = interrupted_run  # type: ignore[method-assign]
            payload = {
                "command": "python -m unittest -q",
                "tool_call_id": "call-interrupted-once",
                "idempotency_key": "command-interrupted-once",
            }

            with self.assertRaisesRegex(RuntimeError, "simulated transport interruption"):
                tools.run_tests(payload)
            receipt = tools.tool_action_receipt("command-interrupted-once")
            recovered = tools.resolve_tool_action_recovery(
                "command-interrupted-once",
                resolution="confirmed_applied",
            )
            duplicate = tools.run_tests(payload)

            self.assertEqual(receipt["state"], "interrupted")
            self.assertEqual(recovered["state"], "completed")
            self.assertEqual(duplicate["status"], "duplicate")
            self.assertEqual(len(calls), 1)

    def test_direct_service_raw_wrapper_is_repairable_before_runner_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tools, _runtime, _checkpoints = self._tools(Path(temp))
            invoked: list[str] = []
            tools._run_shell_command = lambda command, **_kwargs: invoked.append(command) or {  # type: ignore[method-assign]
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            }

            with self.assertRaises(ToolActionValidationError) as raised:
                tools.run_tests({"command": "python -m unittest -q", "raw": "unrepaired"})

            self.assertEqual(raised.exception.code, "unvalidated_raw_wrapper")
            self.assertEqual(invoked, [])

    def test_service_rechecks_native_model_authority_before_command_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tools, _runtime, _checkpoints = self._tools(Path(temp))
            invoked: list[str] = []
            tools._run_shell_command = lambda command, **_kwargs: invoked.append(command) or {  # type: ignore[method-assign]
                "returncode": 0,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
            }

            blocked = tools.run_tests(
                {
                    "command": "python -m unittest -q",
                    "action_source": "native_model_tool",
                    "tool_call_id": "call-tier-b",
                    "idempotency_key": "native-tier-b-command",
                }
            )

            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(blocked["action_receipt"]["state"], "terminal")
            self.assertEqual(invoked, [])


if __name__ == "__main__":
    unittest.main()
