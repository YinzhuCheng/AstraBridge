from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, BinaryIO

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from astrabridge_sidecar.capabilities.runtime import CapabilityRuntime
    from astrabridge_sidecar.mcp_server_core import (
        McpServerCore,
        McpStdioFramingState,
        read_stdio_message,
        run_stdio_mcp_server,
        write_stdio_message,
    )
    from astrabridge_sidecar.multimodal_result_envelope import typed_result_text_summary
    from astrabridge_sidecar.release_identity import release_product_version
else:
    from .capabilities.runtime import CapabilityRuntime
    from .mcp_server_core import McpServerCore, McpStdioFramingState, read_stdio_message, run_stdio_mcp_server, write_stdio_message
    from .multimodal_result_envelope import typed_result_text_summary
    from .release_identity import release_product_version


SERVER_NAME = "astrabridge-capabilities"
SERVER_VERSION = release_product_version()
_STREAM_STATE = McpStdioFramingState()


def main() -> None:
    runtime = CapabilityRuntime()
    run_stdio_mcp_server(_server_core(runtime), sys.stdin.buffer, sys.stdout.buffer, state=_STREAM_STATE)

def _server_core(runtime: CapabilityRuntime) -> McpServerCore:
    return McpServerCore(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        instructions=(
            "Use AstraBridge capability tools when the user needs image generation, image understanding, speech recognition, "
            "or speech synthesis through the capability runtime. Route selection honors configured capability defaults unless "
            "the caller explicitly pins provider/model arguments. Never pass API keys as tool arguments; the server reads "
            "provider env vars from its environment."
        ),
        tools_provider=_tools,
        tool_handler=lambda name, arguments, _context: _dispatch_tool(runtime, name, arguments),
    )


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
    return _dispatch_tool(runtime, name, args)


def _dispatch_tool(runtime: CapabilityRuntime, name: str, args: dict[str, Any]) -> dict[str, Any]:
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
    return {
        "structuredContent": payload,
        "content": [{"type": "text", "text": typed_result_text_summary(payload, title="AstraBridge capability tool result:")}],
    }


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    return read_stdio_message(stream, state=_STREAM_STATE)


def _write_message(stream: BinaryIO, payload: dict[str, Any]) -> None:
    write_stdio_message(stream, payload, state=_STREAM_STATE)


if __name__ == "__main__":
    main()
