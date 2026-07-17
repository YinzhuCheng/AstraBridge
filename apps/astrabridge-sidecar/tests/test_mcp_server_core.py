from __future__ import annotations

import io
import json
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.mcp_server_core import (  # noqa: E402
    MCP_LATEST_PROTOCOL_VERSION,
    LoopbackMcpSession,
    McpServerCore,
    McpStdioFramingState,
    StreamableHttpMcpServer,
    read_stdio_message,
    run_stdio_mcp_server,
)


def _encode_raw_message(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def _encode_header_message(payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body


def _read_all_messages(buffer: bytes) -> list[dict[str, Any]]:
    state = McpStdioFramingState()
    stream = io.BytesIO(buffer)
    messages: list[dict[str, Any]] = []
    while True:
        message = read_stdio_message(stream, state=state)
        if message is None:
            break
        messages.append(message)
    return messages


def _echo_result(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"echo:{message}"}]}


def _echo_core(*, tool_call_timeout_sec: float | None = None, tool_handler=None) -> McpServerCore:
    def _tools() -> list[dict[str, Any]]:
        return [
            {
                "name": "echo_tool",
                "description": "Deterministic echo tool for MCP conformance tests.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                    "additionalProperties": False,
                },
            }
        ]

    def _handler(name: str, arguments: dict[str, Any], context) -> dict[str, Any]:
        if tool_handler is not None:
            return tool_handler(name, arguments, context)
        if name != "echo_tool":
            raise ValueError(f"Unknown tool: {name}")
        return _echo_result(str(arguments.get("message") or ""))

    return McpServerCore(
        server_name="test-mcp-core",
        server_version="0.1.0",
        instructions="Deterministic MCP core test fixture.",
        tools_provider=_tools,
        tool_handler=_handler,
        tool_call_timeout_sec=tool_call_timeout_sec,
    )


class McpServerCoreTests(unittest.TestCase):
    def test_initialize_negotiates_current_legacy_and_unsupported_versions(self) -> None:
        core = _echo_core()
        cases = [
            (MCP_LATEST_PROTOCOL_VERSION, MCP_LATEST_PROTOCOL_VERSION),
            ("2024-11-05", "2024-11-05"),
            ("2023-01-01", MCP_LATEST_PROTOCOL_VERSION),
        ]
        for requested, expected in cases:
            with self.subTest(requested=requested):
                response = core.handle_message(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": requested},
                    }
                )
                self.assertEqual(response["result"]["protocolVersion"], expected)

    def test_stdio_server_supports_multiple_raw_and_header_messages(self) -> None:
        core = _echo_core()
        call_message = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "echo_tool", "arguments": {"message": "hello"}},
        }
        initialize_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": MCP_LATEST_PROTOCOL_VERSION},
        }
        for framing_name, encoder in (("raw", _encode_raw_message), ("header", _encode_header_message)):
            with self.subTest(framing=framing_name):
                stdin = io.BytesIO(encoder(initialize_message) + encoder(call_message))
                stdout = io.BytesIO()
                run_stdio_mcp_server(core, stdin, stdout, state=McpStdioFramingState())
                messages = _read_all_messages(stdout.getvalue())
                self.assertEqual(len(messages), 2)
                self.assertEqual(messages[0]["result"]["protocolVersion"], MCP_LATEST_PROTOCOL_VERSION)
                self.assertEqual(messages[1]["result"], _echo_result("hello"))

    def test_stdio_server_returns_parse_error_for_invalid_json(self) -> None:
        core = _echo_core()
        stdin = io.BytesIO(b"{not-json}\n")
        stdout = io.BytesIO()
        run_stdio_mcp_server(core, stdin, stdout, state=McpStdioFramingState())
        messages = _read_all_messages(stdout.getvalue())
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["error"]["code"], -32700)

    def test_loopback_stdio_and_streamable_http_are_equivalent_for_deterministic_tool(self) -> None:
        core = _echo_core()
        initialize_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": MCP_LATEST_PROTOCOL_VERSION},
        }
        tool_call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "echo_tool", "arguments": {"message": "semantics"}},
        }

        loopback = LoopbackMcpSession(core)
        self.assertEqual(loopback.request(initialize_message)["result"]["protocolVersion"], MCP_LATEST_PROTOCOL_VERSION)
        loopback_result = loopback.request(tool_call)["result"]

        stdin = io.BytesIO(_encode_raw_message(initialize_message) + _encode_raw_message(tool_call))
        stdout = io.BytesIO()
        run_stdio_mcp_server(core, stdin, stdout, state=McpStdioFramingState())
        stdio_messages = _read_all_messages(stdout.getvalue())
        stdio_result = stdio_messages[-1]["result"]

        http_server = StreamableHttpMcpServer(core)
        initialize_response = http_server.handle_request("POST", body=initialize_message)
        session_id = initialize_response.headers["Mcp-Session-Id"]
        protocol_version = initialize_response.headers["MCP-Protocol-Version"]
        http_response = http_server.handle_request(
            "POST",
            headers={"Mcp-Session-Id": session_id, "MCP-Protocol-Version": protocol_version},
            body=tool_call,
        )
        http_result = http_response.json()["result"]

        self.assertEqual(loopback_result, _echo_result("semantics"))
        self.assertEqual(loopback_result, stdio_result)
        self.assertEqual(loopback_result, http_result)

    def test_notifications_and_invalid_requests_follow_jsonrpc_rules(self) -> None:
        core = _echo_core()
        self.assertIsNone(core.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        invalid = core.handle_message({"jsonrpc": "2.0", "id": 1, "params": {}})
        self.assertEqual(invalid["error"]["code"], -32600)
        missing = core.handle_message({"jsonrpc": "2.0", "id": 2, "method": "missing/method", "params": {}})
        self.assertEqual(missing["error"]["code"], -32601)

    def test_tool_call_timeout_returns_error(self) -> None:
        def _slow_handler(_name: str, _arguments: dict[str, Any], _context) -> dict[str, Any]:
            time.sleep(0.15)
            return _echo_result("late")

        core = _echo_core(tool_call_timeout_sec=0.05, tool_handler=_slow_handler)
        response = core.handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "echo_tool", "arguments": {"message": "late"}},
            }
        )
        self.assertEqual(response["error"]["code"], -32000)
        self.assertIn("timed out", response["error"]["message"])

    def test_cancel_notification_suppresses_in_flight_response(self) -> None:
        started = threading.Event()
        cancelled = threading.Event()

        def _cancellable_handler(_name: str, _arguments: dict[str, Any], context) -> dict[str, Any]:
            started.set()
            while not context.cancel_event.wait(0.01):
                pass
            cancelled.set()
            return _echo_result("cancelled")

        core = _echo_core(tool_handler=_cancellable_handler)
        response_box: dict[str, Any] = {}

        def _issue_request() -> None:
            response_box["response"] = core.handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": "call-1",
                    "method": "tools/call",
                    "params": {"name": "echo_tool", "arguments": {"message": "cancel"}},
                }
            )

        worker = threading.Thread(target=_issue_request, daemon=True)
        worker.start()
        self.assertTrue(started.wait(1))
        cancel_response = core.handle_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/cancelled",
                "params": {"requestId": "call-1", "reason": "user cancelled"},
            }
        )
        worker.join(1)
        self.assertIsNone(cancel_response)
        self.assertTrue(cancelled.is_set())
        self.assertIsNone(response_box.get("response"))

    def test_progress_notifications_and_streamable_http_session_lifecycle(self) -> None:
        def _progress_handler(_name: str, arguments: dict[str, Any], context) -> dict[str, Any]:
            context.emit_progress(1, total=2, message="started")
            return _echo_result(str(arguments.get("message") or ""))

        core = _echo_core(tool_handler=_progress_handler)
        loopback = LoopbackMcpSession(core)
        loopback.request(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "echo_tool",
                    "arguments": {"message": "progress"},
                    "_meta": {"progressToken": "progress-1"},
                },
            }
        )
        notifications = loopback.drain_notifications()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["method"], "notifications/progress")
        self.assertEqual(notifications[0]["params"]["progressToken"], "progress-1")

        http_server = StreamableHttpMcpServer(core)
        initialize_response = http_server.handle_request(
            "POST",
            body={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": MCP_LATEST_PROTOCOL_VERSION},
            },
        )
        session_id = initialize_response.headers["Mcp-Session-Id"]
        protocol_version = initialize_response.headers["MCP-Protocol-Version"]

        bad_headers = http_server.handle_request("POST", headers={"Mcp-Session-Id": session_id}, body={"jsonrpc": "2.0", "id": 2, "method": "ping"})
        self.assertEqual(bad_headers.status_code, 400)

        unknown_session = http_server.handle_request(
            "POST",
            headers={"Mcp-Session-Id": "missing", "MCP-Protocol-Version": protocol_version},
            body={"jsonrpc": "2.0", "id": 2, "method": "ping"},
        )
        self.assertEqual(unknown_session.status_code, 404)

        tool_response = http_server.handle_request(
            "POST",
            headers={"Mcp-Session-Id": session_id, "MCP-Protocol-Version": protocol_version},
            body={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "echo_tool",
                    "arguments": {"message": "http-progress"},
                    "_meta": {"progressToken": "progress-http"},
                },
            },
        )
        self.assertEqual(tool_response.status_code, 200)

        sse_response = http_server.handle_request(
            "GET",
            headers={"Mcp-Session-Id": session_id, "MCP-Protocol-Version": protocol_version},
        )
        self.assertEqual(sse_response.status_code, 200)
        self.assertIn("notifications/progress", sse_response.text())
        self.assertIn("progress-http", sse_response.text())

        delete_response = http_server.handle_request("DELETE", headers={"Mcp-Session-Id": session_id})
        self.assertEqual(delete_response.status_code, 204)
        after_delete = http_server.handle_request(
            "POST",
            headers={"Mcp-Session-Id": session_id, "MCP-Protocol-Version": protocol_version},
            body={"jsonrpc": "2.0", "id": 3, "method": "ping"},
        )
        self.assertEqual(after_delete.status_code, 404)


if __name__ == "__main__":
    unittest.main()
