from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.providers import (
    TurnTransitionBlocked,
    assert_turn_transition_admitted,
    build_turn_transition,
    classify_runtime_failure,
    complete_turn_transition,
)
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.task_service import TaskService
from astrabridge_sidecar.tool_action_ledger import ToolActionReceiptLedger


class _NoCallClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object]]] = []

    def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
        self.requests.append((method, dict(params)))
        raise AssertionError(f"The blocked transition must not call {method}.")


class _InterruptedReceiptTools:
    def tool_action_receipts_for_lineage(self, **_kwargs: object) -> list[dict[str, object]]:
        return [
            {
                "receipt_id": "receipt-interrupted",
                "idempotency_key": "command-interrupted",
                "action_id": "action-interrupted",
                "tool_name": "run_command",
                "state": "interrupted",
                "recovery_required": True,
                "lineage": {
                    "task_id": "task-a",
                    "visible_thread_id": "thread-source",
                    "execution_thread_id": "thread-source",
                    "turn_id": "turn-source",
                    "tool_call_id": "call-source",
                },
            }
        ]


class TransactionalTurnStateMachineTests(unittest.TestCase):
    def _transition(self, notice: dict[str, object] | None = None) -> dict[str, object]:
        return build_turn_transition(
            source={
                "thread_id": "thread-source",
                "profile_id": "openai-default",
                "provider_id": "openai",
                "model_id": "gpt-5.5",
                "reasoning_effort": "high",
                "execution_backend": "app_server",
            },
            target={
                "profile_id": "kimi-default",
                "provider_id": "kimi",
                "model_id": "kimi-k2.7-code",
                "reasoning_effort": "high",
                "execution_backend": "app_server",
            },
            trigger="graph_retry",
            failure_notice=notice,
            receipt_references=[],
            target_route={
                "provider_id": "kimi",
                "model_id": "kimi-k2.7-code",
                "execution_backend": "app_server",
                "admission": "verified_non_default",
                "verification_status": "verified",
                "accepted": True,
            },
            context_mode="no_context",
        )

    def test_fault_taxonomy_builds_safe_retry_and_handoff_admission(self) -> None:
        fault_cases = [
            ("provider timed out", "provider_timeout"),
            ("429 too many requests", "rate_limit"),
            ("maximum context length exceeded", "context_window_limit"),
            ("provider thread not found", "runtime_state_corruption"),
            ("connection aborted while stream was active", "transport_failure"),
            ("tool call schema mismatch", "tool_mismatch"),
            ("unsupported reasoning effort for this model", "unsupported_feature"),
        ]
        for raw, category in fault_cases:
            with self.subTest(category=category):
                notice = classify_runtime_failure(
                    raw,
                    current_provider="kimi",
                    current_model="kimi-k2.7-code",
                ).to_payload()
                transition = self._transition(notice)

                self.assertEqual(transition["status"], "ready")
                self.assertEqual(transition["failure"]["category"], category)
                self.assertEqual(transition["stages"]["receipt_check"]["replay_policy"], "never_replay_side_effects_automatically")
                self.assertIn("Provider-private conversation", " ".join(transition["semantic_loss"]))
                self.assertNotIn(raw, json.dumps(transition, ensure_ascii=False))
                if category == "context_window_limit":
                    self.assertTrue(transition["stages"]["capability_downgrade"]["compact_before_send"])
                if category in {"tool_mismatch", "unsupported_feature"}:
                    self.assertEqual(
                        transition["stages"]["capability_downgrade"]["unsupported_tool_or_reasoning_replay"],
                        "disabled",
                    )

    def test_unresolved_receipt_blocks_target_lane_and_never_replays_action(self) -> None:
        transition = build_turn_transition(
            source={"thread_id": "thread-source", "provider_id": "openai", "model_id": "gpt-5.5"},
            target={"provider_id": "kimi", "model_id": "kimi-k2.7-code"},
            receipt_references=[
                {
                    "receipt_id": "receipt-interrupted",
                    "idempotency_key": "command-interrupted",
                    "action_id": "action-interrupted",
                    "tool_name": "run_command",
                    "state": "interrupted",
                    "recovery_required": True,
                    "lineage": {"visible_thread_id": "thread-source", "execution_thread_id": "thread-source"},
                }
            ],
        )

        self.assertEqual(transition["status"], "blocked")
        self.assertEqual(transition["stages"]["lane_start"]["status"], "blocked")
        self.assertEqual(transition["recovery_evidence"]["unresolved_receipt_count"], 1)
        with self.assertRaises(TurnTransitionBlocked):
            assert_turn_transition_admitted(transition)
        with self.assertRaises(TurnTransitionBlocked):
            complete_turn_transition(transition, target_thread_id="thread-target", reused_existing=False)

    def test_retry_backoff_and_reasoning_downgrade_are_explicit_advisories(self) -> None:
        notice = classify_runtime_failure(
            "maximum context length exceeded",
            current_provider="kimi",
            current_model="kimi-k2.7-code",
        ).to_payload()
        transition = build_turn_transition(
            source={"thread_id": "thread-source", "provider_id": "kimi", "model_id": "kimi-k2.7-code"},
            target={"provider_id": "kimi", "model_id": "kimi-k2.7-code"},
            trigger="graph_retry",
            failure_notice=notice,
            retry={"attempt_count": 2, "delay_seconds": 1.5, "retry_policy": "graph_live_retry"},
        )

        self.assertEqual(transition["retry"]["attempt_count"], 2)
        self.assertEqual(transition["retry"]["delay_seconds"], 1.5)
        self.assertTrue(transition["stages"]["capability_downgrade"]["compact_before_send"])
        self.assertEqual(transition["stages"]["capability_downgrade"]["retry"]["retry_policy"], "graph_live_retry")

    def test_ordinary_same_lane_turn_has_a_receipt_check_without_spurious_retry_record(self) -> None:
        transition = build_turn_transition(
            source={"thread_id": "thread-source", "provider_id": "kimi", "model_id": "kimi-k2.7-code"},
            target={"thread_id": "thread-source", "provider_id": "kimi", "model_id": "kimi-k2.7-code"},
            retry={"attempt_count": None, "delay_seconds": None, "retry_policy": None},
        )

        self.assertEqual(transition["status"], "ready")
        self.assertFalse(transition["record_required"])
        self.assertIsNone(transition["retry"])
        self.assertEqual(transition["stages"]["receipt_check"]["status"], "completed")

    def test_ledger_lineage_lookup_exposes_no_command_or_argument_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            ledger = ToolActionReceiptLedger(Path(temp))
            envelope = ledger.build_envelope(
                tool_name="run_command",
                arguments={"command": "echo do-not-put-command-in-handoff", "timeout_seconds": 10},
                lineage={
                    "task_id": "task-a",
                    "visible_thread_id": "thread-source",
                    "execution_thread_id": "thread-worker",
                    "turn_id": "turn-source",
                    "tool_call_id": "call-source",
                },
                authority={"tier": "A", "decision": "approved", "permission_mode": "auto"},
                workspace={"workspace_version": "a" * 64, "checkpoint_version": "none"},
                idempotency_key="command-interrupted",
            )
            ledger.admit(envelope)
            ledger.interrupt(envelope, reason="stream interrupted")

            references = ledger.receipt_references_for_lineage(
                task_id="task-a",
                visible_thread_id="thread-source",
            )
            rendered = json.dumps(references, ensure_ascii=False)
            self.assertEqual(len(references), 1)
            self.assertEqual(references[0]["state"], "interrupted")
            self.assertNotIn("echo do-not-put-command-in-handoff", rendered)
            self.assertNotIn("command_digest", rendered)

    def test_runtime_blocks_before_thread_start_when_source_receipt_is_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-source",
                settings={
                    "profile_id": "openai-default",
                    "provider_id": "openai",
                    "model": "gpt-5.5",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime.attach_project_tools(_InterruptedReceiptTools())
            client = _NoCallClient()

            with self.assertRaises(TurnTransitionBlocked):
                runtime._ensure_provider_thread_for_turn(  # noqa: SLF001
                    client,
                    source_thread_id="thread-source",
                    profile={
                        "profile_id": "kimi-default",
                        "provider_id": "kimi",
                        "model": "kimi-k2.7-code",
                        "reasoning_effort": "high",
                    },
                    model="kimi-k2.7-code",
                    effort="high",
                    permission_mode="auto",
                    collaboration_mode=None,
                )
            self.assertEqual(client.requests, [])

    def test_ordinary_turn_blocks_before_runtime_prepare_when_source_receipt_is_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-source",
                settings={
                    "profile_id": "openai-default",
                    "provider_id": "openai",
                    "model": "gpt-5.5",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime.attach_project_tools(_InterruptedReceiptTools())

            def unexpected_prepare(*_args: object, **_kwargs: object) -> object:
                raise AssertionError("provider runtime must not start")

            runtime._prepare_runtime = unexpected_prepare  # type: ignore[method-assign]

            with self.assertRaises(TurnTransitionBlocked):
                runtime.start_turn(
                    {
                        "profile_id": "kimi-default",
                        "provider_id": "kimi",
                        "model": "kimi-k2.7-code",
                        "reasoning_effort": "high",
                    },
                    thread_id="thread-source",
                    text="continue safely",
                    attachments=[],
                    model="kimi-k2.7-code",
                    effort="high",
                    permission_mode="auto",
                )

    def test_completed_handoff_retains_semantic_loss_target_route_and_recovery_evidence(self) -> None:
        completed = complete_turn_transition(
            self._transition(),
            target_thread_id="thread-kimi",
            reused_existing=False,
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-openai",
                settings={"profile_id": "openai-default", "provider_id": "openai", "model": "gpt-5.5", "reasoning_effort": "high"},
            )
            event = tasks.record_provider_handoff(
                from_thread_id="thread-openai",
                to_thread_id="thread-kimi",
                settings={"profile_id": "kimi-default", "provider_id": "kimi", "model": "kimi-k2.7-code", "reasoning_effort": "high"},
                reused_existing=False,
                turn_transition=completed,
            )
            transition = dict(event.get("turn_transition") or {})
            self.assertEqual(transition["status"], "completed")
            self.assertTrue(transition["semantic_loss"])
            self.assertEqual(transition["target_route"]["provider_id"], "kimi")
            self.assertEqual(transition["recovery_evidence"]["replay_policy"], "never_replay_side_effects_automatically")


if __name__ == "__main__":
    unittest.main()
