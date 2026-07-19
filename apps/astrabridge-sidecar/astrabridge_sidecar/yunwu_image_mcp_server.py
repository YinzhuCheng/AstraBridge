from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from astrabridge_sidecar.common import normalize_path_for_host
    from astrabridge_sidecar.mcp_server_core import (
        McpToolCallContext,
        McpServerCore,
        McpStdioFramingState,
        read_stdio_message,
        run_stdio_mcp_server,
        write_stdio_message,
    )
    from astrabridge_sidecar.multimodal_result_envelope import enrich_yunwu_image_result, typed_result_text_summary
    from astrabridge_sidecar.release_identity import release_product_version
    from astrabridge_sidecar.yunwu_image_service import MAX_YUNWU_IMAGE_CONCURRENCY, YunwuImageService
else:
    from .common import normalize_path_for_host
    from .mcp_server_core import (
        McpToolCallContext,
        McpServerCore,
        McpStdioFramingState,
        read_stdio_message,
        run_stdio_mcp_server,
        write_stdio_message,
    )
    from .multimodal_result_envelope import enrich_yunwu_image_result, typed_result_text_summary
    from .release_identity import release_product_version
    from .yunwu_image_service import MAX_YUNWU_IMAGE_CONCURRENCY, YunwuImageService


SERVER_NAME = "astrabridge-yunwu-image"
SERVER_VERSION = release_product_version()
_STREAM_STATE = McpStdioFramingState()
def main() -> None:
    _debug("started", argv=sys.argv[:3])
    service = YunwuImageService()
    run_stdio_mcp_server(_server_core(service), sys.stdin.buffer, sys.stdout.buffer, state=_STREAM_STATE, log_hook=_debug)


def _server_core(service: YunwuImageService) -> McpServerCore:
    return McpServerCore(
        server_name=SERVER_NAME,
        server_version=SERVER_VERSION,
        instructions=(
            "Use Yunwu image tools only when the user explicitly asks to generate or edit images. "
            "Never request or pass API keys as tool arguments; the server reads YUNWU_API_KEY from its environment."
        ),
        tools_provider=_tools,
        tool_handler=lambda name, arguments, context: _dispatch_tool(service, name, arguments, context),
        log_hook=_debug,
    )


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "yunwu_image_generate",
            "description": "Generate images through Yunwu's OpenAI-compatible Images API. Rewrite prompts with the AstraBridge image prompt guides before calling this tool. For transparent props or sprites, explicitly pass background=transparent. For background plates or scene backdrops, keep background=auto or opaque. Prefer format=png, quality=high, and n=1 with up to 5 concurrent calls instead of relying on unstable n>1 batches. A single image call can take 45-90 seconds; report each completed asset id/path/alpha check as it returns instead of claiming the whole batch is finished. API keys are read from YUNWU_API_KEY in the MCP server environment.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Text prompt for the image."},
                    "model": {"type": "string", "enum": ["gpt-image-2", "gpt-image-2-all"], "default": "gpt-image-2"},
                    "size": {
                        "type": "string",
                        "enum": ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x2048", "2048x1152", "3840x2160", "2160x3840"],
                        "default": "1024x1024",
                    },
                    "n": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 1,
                        "description": "Yunwu may return fewer images than requested. AstraBridge records requested_n/actual_n/count_mismatch; production batches should usually use concurrent n=1.",
                    },
                    "quality": {"type": "string", "enum": ["low", "medium", "high", "auto"], "default": "high"},
                    "format": {"type": "string", "enum": ["png", "jpeg", "webp"], "default": "png"},
                    "output_format": {
                        "type": "string",
                        "enum": ["png", "jpeg", "webp"],
                        "description": "Alias for format. The Yunwu request payload still uses the field name format.",
                    },
                    "background": {
                        "type": "string",
                        "enum": ["opaque", "transparent", "auto"],
                        "default": "auto",
                        "description": "Structured background request. Use transparent only for cutout assets; use auto or opaque for background plates and scene backdrops.",
                    },
                    "prompt_category": {
                        "type": "string",
                        "description": "Prompt guide category, for example game_asset_japanese_anime, japanese_anime_style, people_avatar, landscape_scene, image_edit_recreation.",
                    },
                    "image_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 5,
                        "description": "Optional HTTP(S) image URLs for gpt-image-2-all composition/edit-like generation.",
                    },
                    "response_format": {"type": "string", "enum": ["url", "b64_json"], "default": "url"},
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 900, "default": 300},
                    "purpose": {"type": "string", "description": "Short asset purpose, such as hero_sprite or monster_icon."},
                    "interface_note": {
                        "type": "string",
                        "description": f"Yunwu image API max concurrency is {MAX_YUNWU_IMAGE_CONCURRENCY}. Use single transparent assets for characters/props; use same-category sheets only for tiles/icons with large gutters. AstraBridge records alpha, size, format, requested_n, actual_n, and count_mismatch.",
                    },
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
        },
        {
            "name": "yunwu_image_transparent_asset",
            "description": "Create a transparent Japanese-anime game asset through Yunwu's /images/edits route. AstraBridge automatically supplies a blank transparent seed PNG, repeats the alpha=0 transparency definition in the prompt, and validates alpha/size/format after saving. Use this before plain generation for sprites, props, doors, stairs, keys, gems, monsters, and HUD icons. A single transparent-asset call often takes 45-90 seconds; treat every tool result as per-asset progress and report actual_n, local_path, has_alpha, and transparency_status before starting the next visual decision.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Production prompt for a single transparent game asset or same-category asset sheet."},
                    "model": {"type": "string", "enum": ["gpt-image-2", "gpt-image-2-all"], "default": "gpt-image-2"},
                    "size": {
                        "type": "string",
                        "enum": ["1024x1024", "1536x1024", "1024x1536", "2048x2048", "2048x1152", "3840x2160", "2160x3840"],
                        "default": "1024x1024",
                    },
                    "n": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 1,
                        "description": "Prefer repeated n=1 calls; n>1 can be unstable and will be recorded as requested_n/actual_n. If several assets are needed, issue separate n=1 calls and summarize each result as it completes.",
                    },
                    "quality": {"type": "string", "enum": ["low", "medium", "high", "auto"], "default": "high"},
                    "moderation": {"type": "string", "enum": ["low", "auto"], "default": "auto"},
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 900, "default": 300},
                    "prompt_category": {"type": "string", "default": "game_asset_japanese_anime"},
                    "purpose": {"type": "string", "description": "Short asset purpose, such as heroine_walk_down_frame or yellow_door_sprite."},
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
        },
        {
            "name": "yunwu_image_edit",
            "description": "Edit local image files through Yunwu's OpenAI-compatible Images edits API. Use this for reference-image consistency, heroine walk frames, style transfer, transparent cutouts, and redraws. Pass local image paths; API keys are read from YUNWU_API_KEY.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Edit instruction."},
                    "image_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 15,
                        "description": "Local image paths to edit.",
                    },
                    "mask_path": {"type": "string", "description": "Optional local PNG mask path."},
                    "model": {
                        "type": "string",
                        "enum": ["gpt-image-1", "gpt-image-2", "gpt-image-2-all"],
                        "default": "gpt-image-2",
                    },
                    "size": {
                        "type": "string",
                        "enum": ["auto", "1024x1024", "1536x1024", "1024x1536", "2048x2048", "2048x1152", "3840x2160", "2160x3840"],
                        "default": "1024x1024",
                    },
                    "n": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 1,
                        "description": "Yunwu may return fewer images than requested; prefer repeated n=1 calls for production asset draws.",
                    },
                    "quality": {"type": "string", "enum": ["low", "medium", "high", "auto"], "default": "high"},
                    "background": {"type": "string", "enum": ["opaque", "transparent", "auto"], "default": "transparent"},
                    "moderation": {"type": "string", "enum": ["low", "auto"], "default": "auto"},
                    "timeout_sec": {"type": "integer", "minimum": 1, "maximum": 900, "default": 300},
                    "prompt_category": {
                        "type": "string",
                        "description": "Prompt guide category. Use game_asset_japanese_anime or image_edit_recreation for most game asset edits.",
                    },
                    "purpose": {"type": "string", "description": "Short asset purpose, such as revised_hero_sprite."},
                },
                "required": ["prompt", "image_paths"],
                "additionalProperties": False,
            },
        },
    ]


def _call_tool(service: YunwuImageService, params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name") or "")
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object.")
    return _dispatch_tool(service, name, args, None)


def _dispatch_tool(
    service: YunwuImageService,
    name: str,
    args: dict[str, Any],
    context: McpToolCallContext | None,
) -> dict[str, Any]:
    workspace_root = _workspace_root_argument(args) or _workspace_root()
    api_key = _context_api_key(context)
    timeout_sec = int(args.get("timeout_sec") or 300)
    if name == "yunwu_image_generate":
        result = service.generate(
            prompt=str(args.get("prompt") or ""),
            model=str(args.get("model") or "gpt-image-2"),
            size=str(args.get("size") or "1024x1024"),
            n=int(args.get("n") or 1),
            image_urls=[str(item) for item in (args.get("image_urls") or [])],
            response_format=str(args.get("response_format") or "url"),
            quality=str(args.get("quality") or "high"),
            image_format=str(args.get("format") or args.get("output_format") or "png"),
            background=str(args.get("background") or "auto") or None,
            prompt_category=str(args.get("prompt_category") or ""),
            api_key=api_key,
            timeout_sec=timeout_sec,
            workspace_root=workspace_root,
            purpose=str(args.get("purpose") or "agent_generated_asset"),
        )
        result = enrich_yunwu_image_result(name, result, workspace_root=workspace_root, request_id=str(context.request_id) if context else None)
        summary = _summarize_image_result(result)
        return _tool_text(summary, structured_payload=result)
    if name == "yunwu_image_transparent_asset":
        result = service.transparent_asset(
            prompt=str(args.get("prompt") or ""),
            model=str(args.get("model") or "gpt-image-2"),
            size=str(args.get("size") or "1024x1024"),
            n=int(args.get("n") or 1),
            quality=str(args.get("quality") or "high"),
            moderation=str(args.get("moderation") or "auto"),
            prompt_category=str(args.get("prompt_category") or "game_asset_japanese_anime"),
            api_key=api_key,
            timeout_sec=timeout_sec,
            workspace_root=workspace_root,
            purpose=str(args.get("purpose") or "agent_transparent_asset"),
        )
        result = enrich_yunwu_image_result(name, result, workspace_root=workspace_root, request_id=str(context.request_id) if context else None)
        summary = _summarize_image_result(result)
        return _tool_text(summary, structured_payload=result)
    if name == "yunwu_image_edit":
        result = service.edit(
            prompt=str(args.get("prompt") or ""),
            image_paths=[_normalize_host_path(str(item)) for item in (args.get("image_paths") or [])],
            mask_path=_normalize_host_path(str(args.get("mask_path") or "")) or None,
            model=str(args.get("model") or "gpt-image-2"),
            size=str(args.get("size") or "1024x1024"),
            n=int(args.get("n") or 1),
            quality=str(args.get("quality") or "high"),
            background=str(args.get("background") or "transparent"),
            moderation=str(args.get("moderation") or "auto"),
            prompt_category=str(args.get("prompt_category") or ""),
            api_key=api_key,
            timeout_sec=timeout_sec,
            workspace_root=workspace_root,
            purpose=str(args.get("purpose") or "agent_edited_asset"),
        )
        result = enrich_yunwu_image_result(name, result, workspace_root=workspace_root, request_id=str(context.request_id) if context else None)
        summary = _summarize_image_result(result)
        return _tool_text(summary, structured_payload=result)
    raise ValueError(f"Unknown Yunwu image tool: {name}")


def _workspace_root() -> str | None:
    if os.name == "nt":
        return _first_host_path_env("ASTRABRIDGE_WORKSPACE_ROOT", "ASTRABRIDGE_WORKSPACE_ROOT_WSL")
    return _first_host_path_env("ASTRABRIDGE_WORKSPACE_ROOT_WSL", "ASTRABRIDGE_WORKSPACE_ROOT")


def _first_host_path_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return _normalize_host_path(value)
    return None


def _normalize_host_path(path: str) -> str:
    return _normalize_path_for_os(path, os.name)


def _workspace_root_argument(args: dict[str, Any]) -> str | None:
    workspace_root = _normalize_host_path(str(args.get("workspace_root") or ""))
    return workspace_root or None


def _context_api_key(context: McpToolCallContext | None) -> str | None:
    if context is None:
        return None
    meta = dict(context.meta or {})
    for key in ("internal_api_key", "internalApiKey"):
        value = str(meta.get(key) or "").strip()
        if value:
            return value
    return None


def _normalize_path_for_os(path: str, host_os_name: str) -> str:
    return normalize_path_for_host(path, host_os_name=host_os_name)


def _summarize_image_result(result: dict[str, Any]) -> dict[str, Any]:
    data = []
    for item in result.get("data") or []:
        if not isinstance(item, dict):
            continue
        entry: dict[str, Any] = {}
        if item.get("url"):
            entry["url"] = item["url"]
        if item.get("local_path"):
            entry["local_path"] = item["local_path"]
        if item.get("asset_id"):
            entry["asset_id"] = item["asset_id"]
        if item.get("save_error"):
            entry["save_error"] = item["save_error"]
        if item.get("revised_prompt") is not None:
            entry["revised_prompt"] = item.get("revised_prompt")
        if item.get("b64_json") or item.get("b64_json_present"):
            entry["b64_json_present"] = True
        for key in (
            "actual_width",
            "actual_height",
            "actual_format",
            "actual_mode",
            "has_alpha",
            "transparent_pixel_ratio",
            "semi_transparent_pixel_ratio",
            "transparency_status",
            "validation_warnings",
        ):
            if key in item:
                entry[key] = item.get(key)
        data.append(entry)
    return {
        "created": result.get("created"),
        "asset_manifest_path": result.get("asset_manifest_path"),
        "requested_n": result.get("requested_n"),
        "actual_n": result.get("actual_n"),
        "count_mismatch": result.get("count_mismatch"),
        "max_concurrency": result.get("max_concurrency"),
        "tool_event_verified": True,
        "data": data,
    }


def _tool_text(payload: dict[str, Any], structured_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    structured = structured_payload if structured_payload is not None else payload
    return {
        "structuredContent": structured,
        "content": [{"type": "text", "text": typed_result_text_summary(structured, title="Yunwu image tool result:")}],
    }


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    return read_stdio_message(stream, state=_STREAM_STATE, log_hook=_debug)


def _debug(event: str, **fields: Any) -> None:
    try:
        raw_path = os.environ.get("ASTRABRIDGE_MCP_DEBUG_LOG")
        if not raw_path:
            local_app_data = os.environ.get("LOCALAPPDATA")
            if not local_app_data:
                return
            raw_path = str(Path(local_app_data) / "AstraBridge" / "mcp" / "astrabridge_yunwu_image_debug.jsonl")
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    write_stdio_message(stream, message, state=_STREAM_STATE)


if __name__ == "__main__":
    main()

