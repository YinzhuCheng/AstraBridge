from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, BinaryIO

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from astrabridge_sidecar.capabilities.runtime import CapabilityRuntime
else:
    from .capabilities.runtime import CapabilityRuntime


SERVER_NAME = "astrabridge-capabilities"
SERVER_VERSION = "0.1.0"
_OUTPUT_FRAMING = "header"


def main() -> None:
    runtime = CapabilityRuntime()
    while True:
        message = _read_message(sys.stdin.buffer)
        if message is None:
            break
        response = _handle_message(runtime, message)
        if response is not None:
            _write_message(sys.stdout.buffer, response)


def _handle_message(runtime: CapabilityRuntime, message: dict[str, Any]) -> dict[str, Any] | None:
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
                    "instructions": "Use AstraBridge capability tools when the user needs image generation, image understanding, speech recognition, or speech synthesis through the capability runtime. Route selection honors configured capability defaults unless the caller explicitly pins provider/model arguments. Never pass API keys as tool arguments; the server reads provider env vars from its environment.",
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
            return _result(request_id, _call_tool(runtime, params))
        if request_id is None:
            return None
        return _error(request_id, -32601, f"Unsupported method: {method}")
    except Exception as exc:  # noqa: BLE001
        details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        return _error(request_id, -32000, details)


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "astrabridge_capability_routes",
            "description": "List current capability routes and candidates from AstraBridge's capability runtime, including auto/pinned routing state and resolved provider/model candidates.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "capability_id": {"type": "string", "description": "Optional single capability id filter, such as vision.analyze."},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "astrabridge_capability_image_generate",
            "description": "Invoke AstraBridge image.generate capability through the configured capability runtime route. Use operation=edit or transparent_asset when needed; otherwise operation=generate.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "operation": {"type": "string", "enum": ["generate", "edit", "transparent_asset"], "default": "generate"},
                    "provider_id": {"type": "string"},
                    "model": {"type": "string"},
                    "size": {"type": "string"},
                    "n": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1},
                    "quality": {"type": "string"},
                    "format": {"type": "string"},
                    "output_format": {"type": "string"},
                    "image_format": {"type": "string"},
                    "background": {"type": "string"},
                    "moderation": {"type": "string"},
                    "prompt_category": {"type": "string"},
                    "purpose": {"type": "string"},
                    "image_urls": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                    "image_paths": {"type": "array", "items": {"type": "string"}, "maxItems": 15},
                    "mask_path": {"type": "string"},
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 900},
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
        },
        {
            "name": "astrabridge_capability_vision_analyze",
            "description": "Invoke AstraBridge vision.analyze capability through the configured capability runtime route or an explicit provider/model override.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "provider_id": {"type": "string"},
                    "model": {"type": "string"},
                    "detail": {"type": "string", "enum": ["low", "high", "auto", "original"]},
                    "image_paths": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
                    "image_urls": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
                    "max_output_tokens": {"type": "integer", "minimum": 1, "maximum": 32768},
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 600},
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
        },
        {
            "name": "astrabridge_capability_speech_transcribe",
            "description": "Invoke AstraBridge speech.transcribe capability. Audio is loaded from local file paths and sent through the capability adapter selected by the current route or an explicit override.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "provider_id": {"type": "string"},
                    "model": {"type": "string"},
                    "audio_paths": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
                    "language_hint": {"type": "string"},
                    "enable_itn": {"type": "boolean", "default": False},
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 600},
                },
                "required": ["audio_paths"],
                "additionalProperties": False,
            },
        },
        {
            "name": "astrabridge_capability_speech_synthesize",
            "description": "Invoke AstraBridge speech.synthesize capability. The result includes transcript text plus audio artifact references when workspace persistence is available.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "provider_id": {"type": "string"},
                    "model": {"type": "string"},
                    "instructions": {"type": "string"},
                    "voice": {"type": "string"},
                    "audio_format": {"type": "string", "enum": ["wav", "mp3", "pcm"], "default": "wav"},
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 600},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
    ]


def _call_tool(runtime: CapabilityRuntime, params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name") or "")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object.")
    if name == "astrabridge_capability_routes":
        capability_id = str(args.get("capability_id") or "").strip() or None
        return _tool_text(runtime.route_snapshot(capability_id))
    tool_map = {
        "astrabridge_capability_image_generate": "image.generate",
        "astrabridge_capability_vision_analyze": "vision.analyze",
        "astrabridge_capability_speech_transcribe": "speech.transcribe",
        "astrabridge_capability_speech_synthesize": "speech.synthesize",
    }
    capability_id = tool_map.get(name)
    if not capability_id:
        raise ValueError(f"Unknown AstraBridge capability tool: {name}")
    return _tool_text(runtime.invoke(capability_id, args))


def _tool_text(payload: dict[str, Any]) -> dict[str, Any]:
    lines = ["AstraBridge capability tool result:", json.dumps(payload, ensure_ascii=False, indent=2)]
    artifact_refs = [item for item in list(payload.get("artifact_refs") or []) if isinstance(item, dict)]
    if artifact_refs:
        lines.append("")
        lines.append("Artifacts:")
        for item in artifact_refs:
            path = str(item.get("path") or item.get("local_path") or "").strip()
            artifact_type = str(item.get("artifact_type") or "artifact").strip()
            if path:
                lines.append(f"- {artifact_type}: {path}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


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
