from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.exhaustive_smoke_general_model import (
    build_command_execution_result,
    build_edit_apply_patch_result,
    build_text_health_result,
    session_function_calls,
    summarize_thread_execution,
)


class ExhaustiveSmokeGeneralModelTests(unittest.TestCase):
    def test_text_health_passes_only_on_exact_ok(self) -> None:
        case = _base_case("chat.text_health", scope_decision="run", execution_policy="run_live")

        exact = build_text_health_result(case, test_result={"ok": True, "provider": "deepseek", "model": "deepseek/deepseek-v4-pro", "response_excerpt": "ok", "usage_signal": {"status": "available"}})
        partial = build_text_health_result(case, test_result={"ok": True, "provider": "deepseek", "model": "deepseek/deepseek-v4-pro", "response_excerpt": "okay", "usage_signal": {"status": "available"}})

        self.assertEqual(exact["outcome"], "pass")
        self.assertEqual(partial["outcome"], "partial")
        self.assertIn("not exactly `ok`", partial["reasons"][0])

    def test_session_function_calls_pair_call_and_output(self) -> None:
        events = [
            {"type": "response_item", "payload": {"type": "function_call", "name": "shell_command", "arguments": "{\"command\":\"pwd\"}", "call_id": "c1"}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c1", "output": "Exit code: 0\nOutput:\nD:/AstraBridge\n"}},
        ]
        calls = session_function_calls(events)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "shell_command")
        self.assertEqual(calls[0]["exit_code"], 0)

    def test_command_execution_passes_when_shell_call_succeeds(self) -> None:
        case = _base_case("agent.command_execution", scope_decision="run", execution_policy="run_live")
        thread = {"id": "thread-1", "path": "D:/session.jsonl", "cwd": "D:/repo", "status": {"type": "idle"}, "turns": [{"status": "completed", "items": []}]}
        events = [
            {"type": "response_item", "payload": {"type": "function_call", "name": "shell_command", "arguments": "{\"command\":\"git rev-parse --show-toplevel\"}", "call_id": "c1"}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c1", "output": "Exit code: 0\nOutput:\nD:/AstraBridge\n"}},
        ]

        result = build_command_execution_result(case, thread=thread, session_events=events)

        self.assertEqual(result["outcome"], "pass")
        self.assertEqual(result["artifact_observations"][1]["status"], "pass")

    def test_reduced_authority_command_without_tool_stays_reduced_authority(self) -> None:
        case = _base_case("agent.command_execution", scope_decision="reduced-authority", execution_policy="confirm_reduced_authority")
        case["runner_hints"] = {"expected_authority_outcome": "reduced_authority_confirmation"}
        thread = {"id": "thread-1", "path": "D:/session.jsonl", "cwd": "D:/repo", "status": {"type": "idle"}, "turns": [{"status": "completed", "items": [{"type": "agentMessage", "text": "I cannot run shell commands here."}]}]}

        result = build_command_execution_result(case, thread=thread, session_events=[])

        self.assertEqual(result["outcome"], "reduced-authority")
        self.assertEqual(result["artifact_observations"][1]["status"], "missing")

    def test_edit_apply_patch_is_partial_when_only_shell_edits_file(self) -> None:
        case = _base_case("agent.edit_apply_patch", scope_decision="run", execution_policy="run_live")
        thread = {"id": "thread-1", "path": "D:/session.jsonl", "cwd": "D:/repo", "status": {"type": "idle"}, "turns": [{"status": "completed", "items": []}]}
        events = [
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "shell_command",
                    "arguments": "{\"command\":\"Set-Content D:/repo/scratch.txt STATE=ready\"}",
                    "call_id": "c1",
                },
            },
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c1", "output": "Exit code: 0\nOutput:\n"}},
        ]

        result = build_edit_apply_patch_result(
            case,
            thread=thread,
            session_events=events,
            scratch_path="D:/repo/scratch.txt",
            before_text="STATE=pending\n",
            after_text="STATE=ready\n",
        )

        self.assertEqual(result["outcome"], "partial")
        self.assertIn("shell commands", result["reasons"][0])

    def test_summarize_thread_execution_tracks_thread_items_and_session_calls(self) -> None:
        thread = {
            "id": "thread-1",
            "path": "D:/session.jsonl",
            "cwd": "D:/repo",
            "status": {"type": "idle"},
            "turns": [
                {
                    "status": "completed",
                    "items": [
                        {"type": "commandExecution", "command": "pwd", "status": "completed", "exitCode": 0, "aggregatedOutput": "D:/repo"},
                        {"type": "agentMessage", "text": "done"},
                    ],
                }
            ],
        }
        events = [
            {"type": "response_item", "payload": {"type": "function_call", "name": "shell_command", "arguments": "{\"command\":\"pwd\"}", "call_id": "c1"}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "c1", "output": "Exit code: 0\nOutput:\nD:/repo\n"}},
        ]

        summary = summarize_thread_execution(thread, events)

        self.assertEqual(summary["command_event_count"], 1)
        self.assertEqual(summary["shell_call_count"], 1)
        self.assertEqual(summary["assistant_text"], "done")


def _base_case(lane_kind: str, *, scope_decision: str, execution_policy: str) -> dict:
    return {
        "case_id": f"case-{lane_kind}",
        "lane_id": f"provider/model:{lane_kind}",
        "lane_group": "general_model",
        "lane_kind": lane_kind,
        "provider_id": "deepseek",
        "model_id": "deepseek/deepseek-v4-pro",
        "scope_decision": scope_decision,
        "execution_policy": execution_policy,
        "runner_kind": "task_runtime_validation",
        "runner_hints": {"expected_authority_outcome": "authority_probe"},
    }


if __name__ == "__main__":
    unittest.main()
