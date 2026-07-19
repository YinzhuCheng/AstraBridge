from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO

if __package__ in {None, ""}:
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from astrabridge_sidecar.mcp_server_core import McpServerCore, McpStdioFramingState, read_stdio_message, run_stdio_mcp_server, write_stdio_message
    from astrabridge_sidecar.release_identity import release_product_version
else:
    from .mcp_server_core import McpServerCore, McpStdioFramingState, read_stdio_message, run_stdio_mcp_server, write_stdio_message
    from .release_identity import release_product_version


SERVER_NAME = "astrabridge-mcp-probe-fixture"
SERVER_VERSION = release_product_version()
_STREAM_STATE = McpStdioFramingState()


def main() -> None:
    run_stdio_mcp_server(_server_core(), sys.stdin.buffer, sys.stdout.buffer, state=_STREAM_STATE)


def _server_core() -> McpServerCore:
    return McpServerCore(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        instructions="AstraBridge MCP compatibility probe fixture. Use only for no-key visibility checks.",
        tools_provider=_tools,
        tool_handler=lambda name, arguments, _context: _dispatch_tool(name, arguments),
    )


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "astrabridge_probe_ping",
            "description": "No-key ping tool used by AstraBridge to verify Codex MCP visibility.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }
    ]


def _call_tool(params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name") or "")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}
    return _dispatch_tool(name, args)


def _dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name != "astrabridge_probe_ping":
        raise ValueError(f"Unknown probe fixture tool: {name}")
    message = str(args.get("message") or "pong")
    return {"content": [{"type": "text", "text": f"astrabridge_probe_ping:{message}"}]}

def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    return read_stdio_message(stream, state=_STREAM_STATE)


def _write_message(stream: BinaryIO, payload: dict[str, Any]) -> None:
    write_stdio_message(stream, payload, state=_STREAM_STATE)


if __name__ == "__main__":
    main()
