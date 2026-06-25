from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.app_server_client import JsonRpcError
from astrabridge_sidecar.codex_app_server_probe import probe_app_server_protocol


class _FakeProbeClient:
    def __init__(self, on_notification, on_server_request, scenario: str) -> None:
        self._on_notification = on_notification
        self._on_server_request = on_server_request
        self._scenario = scenario
        self.closed = False

    def start(self) -> None:
        if self._scenario == "start-timeout":
            raise TimeoutError("Timed out waiting for app-server response: initialize")
        self._on_notification("thread/status/changed", {"status": "ready"})

    def close(self) -> None:
        self.closed = True

    def request(self, method: str, params=None, timeout: float = 120.0):  # noqa: ARG002
        if self._scenario == "thread-timeout" and method == "thread/start":
            raise TimeoutError("Timed out waiting for app-server response: thread/start")
        if self._scenario == "resume-error" and method == "thread/resume":
            raise JsonRpcError("no rollout found for thread id thread-1", code=-32600, data=None)
        if self._scenario == "turn-incompatible" and method == "turn/start":
            raise JsonRpcError("Method not found", code=-32601, data={"token": "fixture-token-value"})
        if method == "thread/start":
            self._on_notification("thread/started", {"thread": {"id": "thread-1"}})
            return {"thread": {"id": "thread-1"}}
        if method == "thread/resume":
            return {"thread": {"id": "thread-1"}}
        if method == "turn/start":
            self._on_notification("runtime/server_request", {"method": "commandExecution/requestApproval", "id": 1})
            self._on_notification("item/mcpToolCall/progress", {"server": "context7"})
            self._on_server_request("commandExecution/requestApproval", {"approvalId": "APR-1"})
            return {"turn": {"id": "turn-1"}}
        raise AssertionError(f"Unexpected method: {method}")


class AppServerProtocolProbeTests(unittest.TestCase):
    def test_probe_success_writes_redacted_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = probe_app_server_protocol(
                client_factory=lambda on_notification, on_server_request: _FakeProbeClient(on_notification, on_server_request, "success"),
                artifact_root=Path(temp),
                cwd="D:/AstraBridge/.astrabridge/runtime-cwd",
                request_timeout=1.0,
            )

            self.assertEqual(report["app_server"]["start_status"], "supported")
            self.assertEqual(report["app_server"]["initialize_status"], "supported")
            self.assertEqual(report["app_server"]["thread_start_status"], "supported")
            self.assertEqual(report["app_server"]["thread_resume_status"], "supported")
            self.assertEqual(report["app_server"]["turn_start_status"], "supported")
            self.assertEqual(report["app_server"]["approval_events_status"], "observed")
            self.assertEqual(report["app_server"]["mcp_elicitation_status"], "observed")
            self.assertEqual(report["app_server"]["turn_error_shape_status"], "not_observed")
            report_file = Path(report["report_path"])
            self.assertTrue(report_file.is_file())
            saved = json.loads(report_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["app_server"]["thread_id_observed"], "thread-1")
            self.assertEqual(saved["app_server"]["request_sequence"], ["thread/start", "turn/start", "thread/resume"])

    def test_probe_timeout_marks_thread_start_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = probe_app_server_protocol(
                client_factory=lambda on_notification, on_server_request: _FakeProbeClient(on_notification, on_server_request, "thread-timeout"),
                artifact_root=Path(temp),
                request_timeout=1.0,
            )

            self.assertEqual(report["app_server"]["start_status"], "supported")
            self.assertEqual(report["app_server"]["initialize_status"], "supported")
            self.assertEqual(report["app_server"]["thread_start_status"], "timeout")
            self.assertEqual(report["app_server"]["thread_resume_status"], "skipped")
            self.assertEqual(report["app_server"]["turn_start_status"], "skipped")
            self.assertIn("thread/start", " ".join(report["known_warnings"]))

    def test_probe_incompatible_turn_error_is_classified_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = probe_app_server_protocol(
                client_factory=lambda on_notification, on_server_request: _FakeProbeClient(on_notification, on_server_request, "turn-incompatible"),
                artifact_root=Path(temp),
                request_timeout=1.0,
            )

            self.assertEqual(report["app_server"]["thread_start_status"], "supported")
            self.assertEqual(report["app_server"]["thread_resume_status"], "supported")
            self.assertEqual(report["app_server"]["turn_start_status"], "incompatible_response")
            self.assertEqual(report["app_server"]["turn_error_shape_status"], "jsonrpc_error")
            self.assertIn("[REDACTED]", json.dumps(report["app_server"]["turn_error"]))
            saved = Path(report["report_path"]).read_text(encoding="utf-8")
            self.assertNotIn("fixture-token-value", saved)

    def test_probe_thread_resume_error_is_classified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = probe_app_server_protocol(
                client_factory=lambda on_notification, on_server_request: _FakeProbeClient(on_notification, on_server_request, "resume-error"),
                artifact_root=Path(temp),
                request_timeout=1.0,
            )

            self.assertEqual(report["app_server"]["thread_start_status"], "supported")
            self.assertEqual(report["app_server"]["thread_resume_status"], "error_response")
            self.assertEqual(report["app_server"]["turn_start_status"], "supported")
            self.assertEqual(report["app_server"]["thread_resume_error_shape_status"], "jsonrpc_error")
            self.assertEqual(report["app_server"]["turn_error_shape_status"], "not_observed")
            self.assertEqual(report["app_server"]["request_sequence"], ["thread/start", "turn/start", "thread/resume"])


if __name__ == "__main__":
    unittest.main()
