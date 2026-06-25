from __future__ import annotations

import json
import sys
import traceback
from typing import Any, BinaryIO


SERVER_NAME = "astrabridge-mcp-probe-fixture"
SERVER_VERSION = "0.1.0"
_OUTPUT_FRAMING = "header"


def main() -> None:
    while True:
        message = _read_message(sys.stdin.buffer)
        if message is None:
            break
        response = _handle_message(message)
        if response is not None:
            _write_message(sys.stdout.buffer, response)


def _handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = str(message.get("method") or "")
    params = message.get("params") or {}
    try:
        if method == "initialize":
            return _result(
                request_id,
                {
                    "protocolVersion": str(params.get("protocolVersion") or "2024-11-05"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": "AstraBridge MCP compatibility probe fixture. Use only for no-key visibility checks.",
                },
            )
        if method in {"notifications/initialized", "initialized"}:
            return None
        if method == "tools/list":
            return _result(request_id, {"tools": _tools()})
        if method == "resources/list":
            return _result(request_id, {"resources": []})
        if method == "resources/templates/list":
            return _result(request_id, {"resourceTemplates": []})
        if method == "tools/call":
            return _result(request_id, _call_tool(params))
        if request_id is None:
            return None
        return _error(request_id, -32601, f"Unsupported method: {method}")
    except Exception as exc:  # noqa: BLE001
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        return _error(request_id, -32000, detail)


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
    if name != "astrabridge_probe_ping":
        raise ValueError(f"Unknown probe fixture tool: {name}")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}
    message = str(args.get("message") or "pong")
    return {"content": [{"type": "text", "text": f"astrabridge_probe_ping:{message}"}]}


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    global _OUTPUT_FRAMING
    first = _read_first_nonempty_byte(stream)
    if not first:
        return None
    if first == b"{":
        _OUTPUT_FRAMING = "raw"
        return json.loads(_read_json_object(stream, first).decode("utf-8"))
    _OUTPUT_FRAMING = "header"
    headers: dict[str, str] = {}
    line = first + stream.readline()
    while line and line.strip():
        decoded = line.decode("utf-8", errors="replace").strip()
        key, _sep, value = decoded.partition(":")
        if key:
            headers[key.lower()] = value.strip()
        line = stream.readline()
    length = int(headers.get("content-length") or 0)
    if length <= 0:
        return None
    body = stream.read(length)
    return json.loads(body.decode("utf-8"))


def _read_first_nonempty_byte(stream: BinaryIO) -> bytes:
    while True:
        chunk = stream.read(1)
        if not chunk:
            return b""
        if chunk in b" \t\r\n":
            continue
        return chunk


def _read_json_object(stream: BinaryIO, first: bytes) -> bytes:
    buffer = bytearray(first)
    depth = 1
    in_string = False
    escaped = False
    while depth > 0:
        chunk = stream.read(1)
        if not chunk:
            break
        char = chunk[0]
        buffer.extend(chunk)
        if in_string:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                in_string = False
            continue
        if char == 34:
            in_string = True
        elif char == 123:
            depth += 1
        elif char == 125:
            depth -= 1
    return bytes(buffer)


def _write_message(stream: BinaryIO, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if _OUTPUT_FRAMING == "raw":
        stream.write(encoded + b"\n")
        stream.flush()
        return
    header = f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii")
    stream.write(header)
    stream.write(encoded)
    stream.flush()


if __name__ == "__main__":
    main()
