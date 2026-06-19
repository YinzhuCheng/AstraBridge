from __future__ import annotations

import base64
import hashlib
import http.client
import json
import mimetypes
import os
import re
import secrets
import socket
import ssl
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any

from .model_catalog import known_context_window, model_catalog_entry
from .security import redact_sensitive


ROUTER_PORT = 8787
ROUTER_ENV_KEY = "CODEX_ROUTER_API_KEY"
QWEN_THINKING_ENABLED_EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max"}
DEEPSEEK_MAX_EFFORTS = {"xhigh", "max"}
KIMI_KEEP_ALL_EFFORTS = {"xhigh", "max"}
KIMI_THINKING_OUTPUT_FLOOR = 32768
LOCAL_IMAGE_MAX_BYTES = 100 * 1024 * 1024
EMBEDDED_INPUT_IMAGE_BLOCK_RE = re.compile(
    r'\{[^{}]*"type"\s*:\s*"input_image"[^{}]*"image_url"\s*:\s*"(data:image/[^"]+)"[^{}]*\}',
    re.DOTALL,
)
EMBEDDED_IMAGE_URL_RE = re.compile(r'"image_url"\s*:\s*"(data:image/[^"]+)"')


class ProviderAdapter:
    def __init__(self, router: "RouterService", profile: dict[str, Any]) -> None:
        self.router = router
        self.profile = profile

    def upstream_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = dict(payload)
        upstream_payload["model"] = str(self.profile.get("model") or "")
        self.router.apply_temperature_config(self.profile, upstream_payload, payload.get("model"))
        return upstream_payload

    def endpoint_path(self) -> str:
        return "/responses"

    def wire_api(self) -> str:
        return str(self.profile.get("wire_api") or "responses")

    def describe(self) -> str:
        return "responses"

    def supports_passthrough_stream(self) -> bool:
        return True

    def apply_reasoning_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = dict(payload)
        reasoning = payload.get("reasoning")
        if isinstance(reasoning, dict):
            return upstream_payload
        effort = self.router.resolve_reasoning_effort(self.profile, payload.get("model"))
        if effort:
            upstream_payload["reasoning"] = {"effort": effort}
        return upstream_payload

    def client_response_from_upstream_json(self, upstream: dict[str, Any], original_payload: dict[str, Any]) -> dict[str, Any]:
        return upstream

    def client_stream_events_from_upstream_json(self, upstream: dict[str, Any], original_payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = self.client_response_from_upstream_json(upstream, original_payload)
        response_id = str(response.get("id") or "response_router")
        events = [{"type": "response.created", "response": {"id": response_id, "object": "response", "status": "in_progress"}}]
        for output_index, item in enumerate(list(response.get("output") or [])):
            if item.get("type") == "message":
                item_id = item.get("id") or f"msg_{output_index}"
                events.append(
                    {
                        "type": "response.output_item.added",
                        "output_index": output_index,
                        "item": {"id": item_id, "type": "message", "role": "assistant", "status": "in_progress", "content": []},
                    }
                )
                for content_index, content in enumerate(list(item.get("content") or [])):
                    if content.get("type") == "output_text":
                        text = str(content.get("text") or "")
                        part = {"type": "output_text", "text": ""}
                        events.append(
                            {
                                "type": "response.content_part.added",
                                "item_id": item_id,
                                "output_index": output_index,
                                "content_index": content_index,
                                "part": part,
                            }
                        )
                        if text:
                            events.append(
                                {
                                    "type": "response.output_text.delta",
                                    "item_id": item_id,
                                    "output_index": output_index,
                                    "content_index": content_index,
                                    "delta": text,
                                }
                            )
                        events.append(
                            {
                                "type": "response.output_text.done",
                                "item_id": item_id,
                                "output_index": output_index,
                                "content_index": content_index,
                                "text": text,
                            }
                        )
                        events.append(
                            {
                                "type": "response.content_part.done",
                                "item_id": item_id,
                                "output_index": output_index,
                                "content_index": content_index,
                                "part": {"type": "output_text", "text": text},
                            }
                        )
                events.append(
                    {
                        "type": "response.output_item.done",
                        "output_index": output_index,
                        "item": {**item, "id": item_id, "status": "completed"},
                    }
                )
            elif item.get("type") == "function_call":
                events.append(
                    {
                        "type": "response.output_item.added",
                        "output_index": output_index,
                        "item": item,
                    }
                )
        events.append({"type": "response.completed", "response": response})
        return events


class QwenResponsesAdapter(ProviderAdapter):
    def upstream_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().apply_reasoning_config(super().upstream_payload(payload))
        reasoning = upstream_payload.get("reasoning")
        effort = None
        if isinstance(reasoning, dict):
            effort = str(reasoning.get("effort") or "").strip().lower() or None
        if effort is None:
            effort = str(self.profile.get("reasoning_effort") or "").strip().lower() or None
        if effort == "off":
            upstream_payload["enable_thinking"] = False
        elif effort == "auto":
            upstream_payload.pop("enable_thinking", None)
        elif effort in QWEN_THINKING_ENABLED_EFFORTS:
            upstream_payload["enable_thinking"] = True
        upstream_payload.pop("reasoning", None)
        for key in ("top_p", "service_tier"):
            upstream_payload.pop(key, None)
        extra_defaults = self.profile.get("extra_body_defaults")
        if isinstance(extra_defaults, dict):
            for key, value in extra_defaults.items():
                upstream_payload.setdefault(str(key), value)
        return upstream_payload

    def describe(self) -> str:
        return "qwen_responses"


class ChatCompletionsAdapter(ProviderAdapter):
    def endpoint_path(self) -> str:
        return "/chat/completions"

    def wire_api(self) -> str:
        return "chat"

    def describe(self) -> str:
        return "chat_completions"

    def supports_passthrough_stream(self) -> bool:
        return False

    def supports_local_image_input(self) -> bool:
        return False

    def upstream_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = self.apply_reasoning_config(payload)
        tools = self._convert_tools(payload.get("tools"))
        messages = self._convert_messages(payload)
        guidance = self._tool_guidance(tools)
        if guidance:
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = f"{messages[0].get('content')}\n\n{guidance}".strip()
            else:
                messages.insert(0, {"role": "system", "content": guidance})
        messages = self._repair_tool_message_sequence(messages)
        upstream_payload: dict[str, Any] = {
            "model": str(self.profile.get("model") or ""),
            "messages": messages,
            "stream": bool(payload.get("stream")),
        }
        if "temperature" in payload:
            upstream_payload["temperature"] = payload.get("temperature")
            self.router.apply_temperature_config(self.profile, upstream_payload, payload.get("model"))
        if upstream_payload["stream"]:
            upstream_payload["stream_options"] = {"include_usage": True}
        if tools:
            upstream_payload["tools"] = tools
        tool_choice = payload.get("tool_choice")
        if tool_choice is not None:
            upstream_payload["tool_choice"] = tool_choice
        max_output_tokens = payload.get("max_output_tokens")
        if max_output_tokens not in {None, ""}:
            upstream_payload["max_tokens"] = max_output_tokens
        return upstream_payload

    def _tool_guidance(self, tools: list[dict[str, Any]]) -> str:
        names = {
            str((tool.get("function") or {}).get("name") or "")
            for tool in tools
            if isinstance(tool, dict)
        }
        names.discard("")
        if not names:
            return ""
        lines = [
            "Codex app-server tool bridge: when a listed tool is appropriate, call it as a structured tool call with valid JSON arguments; do not describe the call in prose.",
        ]
        if "request_user_input" in names:
            lines.append("Use request_user_input for missing user choices; include 1-3 questions, a recommended option, and concise option descriptions.")
        if "update_plan" in names:
            lines.append("Use update_plan to publish or update the visible checklist when the mode allows it.")
        return "\n".join(lines)

    def client_response_from_upstream_json(self, upstream: dict[str, Any], original_payload: dict[str, Any]) -> dict[str, Any]:
        choice = ((upstream.get("choices") or [{}])[0]) if isinstance(upstream.get("choices"), list) else {}
        message = dict(choice.get("message") or {})
        output: list[dict[str, Any]] = []
        text = str(message.get("content") or "")
        reasoning_content = str(message.get("reasoning_content") or "")
        tool_calls = list(message.get("tool_calls") or [])
        text = self._visible_text_or_reasoning_only_notice(text, reasoning_content, bool(tool_calls))
        message_item_id = f"msg_{upstream.get('id') or int(time.time())}"
        if reasoning_content:
            output.append(
                {
                    "id": f"reasoning_{upstream.get('id') or int(time.time())}",
                    "type": "reasoning",
                    "summary": [reasoning_content],
                    "content": [reasoning_content],
                }
            )
        if text:
            output.append(
                {
                    "id": message_item_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                }
            )
        for call in tool_calls:
            function = dict(call.get("function") or {})
            call_id = str(call.get("id") or "call_router")
            output.append(
                {
                    "id": f"fc_{call_id}",
                    "type": "function_call",
                    "call_id": call_id,
                    "name": function.get("name") or "tool",
                    "arguments": self._safe_tool_arguments(function.get("arguments")),
                }
            )
        usage = dict(upstream.get("usage") or {})
        response = {
            "id": upstream.get("id") or f"resp_router_{int(time.time())}",
            "object": "response",
            "created_at": upstream.get("created") or int(time.time()),
            "model": original_payload.get("model") or f"{self.profile.get('provider_id')}/{self.profile.get('model')}",
            "status": "completed",
            "output": output,
            "output_text": text,
        }
        if usage:
            response["usage"] = self._response_usage_from_chat_usage(usage)
        return response

    def _visible_text_or_reasoning_only_notice(self, text: str, reasoning_content: str, has_tool_calls: bool) -> str:
        if text or not reasoning_content or has_tool_calls:
            return text
        return "(Provider returned reasoning content but no final assistant message. Open the reasoning preview or retry with an explicit final-answer instruction.)"

    def _convert_messages(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        instructions = payload.get("instructions")
        if isinstance(instructions, str) and instructions.strip():
            messages.append({"role": "system", "content": instructions.strip()})
        raw_input = payload.get("input")
        if isinstance(raw_input, str):
            messages.append({"role": "user", "content": raw_input})
            return messages
        if isinstance(raw_input, list):
            for item in raw_input:
                converted = self._convert_input_item(item)
                if converted:
                    messages.extend(converted)
            return messages
        if isinstance(raw_input, dict):
            converted = self._convert_input_item(raw_input)
            if converted:
                messages.extend(converted)
        return messages or [{"role": "user", "content": ""}]

    def _convert_input_item(self, item: Any) -> list[dict[str, Any]]:
        if not isinstance(item, dict):
            return [{"role": "user", "content": str(item)}]
        if "role" in item:
            role = self._map_role(str(item.get("role") or "user"))
            if role == "tool":
                tool_id = str(item.get("tool_call_id") or item.get("call_id") or "tool_call")
                return [{"role": "tool", "tool_call_id": tool_id, "content": self._flatten_content(item.get("content"))}]
            if role == "assistant" and item.get("tool_calls"):
                return [
                    {
                        "role": "assistant",
                        "content": self._chat_content(item.get("content")) or None,
                        "tool_calls": self._sanitize_chat_tool_calls(item.get("tool_calls")),
                    }
                ]
            if role == "assistant" and item.get("reasoning_content"):
                return [
                    {
                        "role": "assistant",
                        "content": f"{self._flatten_content(item.get('reasoning_content'))}\n{self._flatten_content(item.get('content'))}".strip(),
                    }
                ]
            return [{"role": role, "content": self._chat_content(item.get("content"))}]
        item_type = str(item.get("type") or "")
        if item_type == "localImage":
            return [{"role": "user", "content": self._chat_content(item)}]
        if item_type == "function_call_output":
            tool_id = str(item.get("call_id") or item.get("tool_call_id") or "tool_call")
            return [{"role": "tool", "tool_call_id": tool_id, "content": self._flatten_content(item.get("output"))}]
        if item_type == "commandExecution":
            tool_id = str(item.get("id") or item.get("call_id") or "tool_call")
            return [{"role": "tool", "tool_call_id": tool_id, "content": self._command_execution_tool_result(item)}]
        if item_type == "reasoning":
            summary = self._flatten_content(item.get("summary") or item.get("content") or item)
            if summary:
                return [{"role": "assistant", "content": f"[reasoning summary]\n{summary}"}]
            return []
        if item_type == "function_call":
            call_id = str(item.get("call_id") or item.get("id") or "tool_call")
            name = str(item.get("name") or "tool")
            return [
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": self._safe_tool_arguments(item.get("arguments")),
                            },
                        }
                    ],
                }
            ]
        if item_type == "message":
            role = self._map_role(str(item.get("role") or "user"))
            return [{"role": role, "content": self._chat_content(item.get("content"))}]
        if item_type in {"contextCompaction", "enteredReviewMode", "exitedReviewMode"}:
            return []
        return [{"role": "user", "content": self._flatten_content(item)}]

    def _chat_content(self, content: Any) -> Any:
        if not self.supports_local_image_input():
            return self._flatten_content(content)
        parts = self._chat_content_parts(content)
        if any(part.get("type") == "image_url" for part in parts):
            return parts
        return "\n".join(str(part.get("text") or "") for part in parts if part.get("type") == "text")

    def _chat_content_parts(self, content: Any) -> list[dict[str, Any]]:
        if content is None:
            return []
        if isinstance(content, str):
            embedded = self._embedded_input_image_parts(content)
            if embedded:
                return embedded
            return [{"type": "text", "text": content}]
        if isinstance(content, list):
            parts: list[dict[str, Any]] = []
            for item in content:
                parts.extend(self._chat_content_parts(item))
            return parts
        if isinstance(content, dict):
            item_type = str(content.get("type") or "")
            if item_type in {"input_text", "output_text", "text"}:
                text = str(content.get("text") or "")
                embedded = self._embedded_input_image_parts(text)
                if embedded:
                    return embedded
                return [{"type": "text", "text": text}] if text else []
            if item_type == "localImage":
                return [self._local_image_chat_part(content)]
            if item_type == "input_image":
                image_url = str(content.get("image_url") or content.get("url") or "")
                if image_url.startswith("data:image/"):
                    return [{"type": "image_url", "image_url": {"url": image_url}}]
                return [{"type": "text", "text": "[image attachment omitted: Kimi requires a base64 data URL]"}]
            if item_type == "image_url":
                image_url = dict(content.get("image_url") or {})
                url = str(image_url.get("url") or content.get("url") or "")
                if url.startswith("data:image/"):
                    return [{"type": "image_url", "image_url": {"url": url}}]
                return [{"type": "text", "text": "[image attachment omitted: provider requires base64 data URL, not remote/local URL]"}]
            if "content" in content:
                return self._chat_content_parts(content.get("content"))
            flattened = self._flatten_content(content)
            return [{"type": "text", "text": flattened}] if flattened else []
        return [{"type": "text", "text": str(content)}]

    def _embedded_input_image_parts(self, text: str) -> list[dict[str, Any]]:
        matches = list(EMBEDDED_INPUT_IMAGE_BLOCK_RE.finditer(text))
        if not matches:
            url_matches = list(EMBEDDED_IMAGE_URL_RE.finditer(text))
            if not url_matches:
                return []
            scrubbed = EMBEDDED_IMAGE_URL_RE.sub('"image_url":"[image attachment]"', text)
            parts: list[dict[str, Any]] = []
            if scrubbed.strip():
                parts.append({"type": "text", "text": scrubbed.strip()})
            parts.extend({"type": "image_url", "image_url": {"url": match.group(1)}} for match in url_matches)
            return parts
        parts: list[dict[str, Any]] = []
        cursor = 0
        for match in matches:
            before = text[cursor : match.start()]
            if before:
                parts.append({"type": "text", "text": before.rstrip() + "\n[image attachment]"})
            parts.append({"type": "image_url", "image_url": {"url": match.group(1)}})
            cursor = match.end()
        after = text[cursor:]
        if after.strip():
            parts.append({"type": "text", "text": after.lstrip()})
        return parts

    def _local_image_chat_part(self, content: dict[str, Any]) -> dict[str, Any]:
        path = str(content.get("path") or "")
        try:
            data_url = self._local_image_data_url(path)
            return {"type": "image_url", "image_url": {"url": data_url}}
        except Exception as exc:  # noqa: BLE001 - convert attachment failures into model-visible context.
            return {"type": "text", "text": f"[image attachment unavailable: {str(exc)[:160]}]"}

    def _local_image_data_url(self, raw_path: str) -> str:
        path = self._local_image_path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"image file not found: {raw_path}")
        size = path.stat().st_size
        if size > LOCAL_IMAGE_MAX_BYTES:
            raise ValueError(f"image file is too large for Kimi vision input: {size} bytes")
        mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
        if mime_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            raise ValueError(f"unsupported Kimi image format: {mime_type}")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _local_image_path(self, raw_path: str) -> Path:
        if not raw_path:
            raise ValueError("missing local image path")
        parsed = urllib.parse.urlparse(raw_path)
        if parsed.scheme == "file":
            value = urllib.parse.unquote(parsed.path)
            if value.startswith("/") and len(value) > 3 and value[2] == ":":
                value = value[1:]
            return Path(value)
        if raw_path.startswith("/mnt/") and len(raw_path) > 6 and raw_path[6] == "/":
            drive = raw_path[5].upper()
            rest = raw_path[7:].replace("/", "\\")
            return Path(f"{drive}:\\{rest}")
        return Path(raw_path)

    def _command_execution_tool_result(self, item: dict[str, Any]) -> str:
        command = str(item.get("command") or "").strip()
        status = str(item.get("status") or "").strip()
        output = str(item.get("aggregatedOutput") or "").strip()
        exit_code = item.get("exitCode")
        parts = []
        if command:
            parts.append(f"command: {command}")
        if status:
            parts.append(f"status: {status}")
        if exit_code is not None:
            parts.append(f"exit_code: {exit_code}")
        if output:
            parts.append(f"output:\n{output}")
        return "\n".join(parts) or "Command completed with no captured output."

    def _repair_tool_message_sequence(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        repaired: list[dict[str, Any]] = []
        index = 0
        while index < len(messages):
            message = messages[index]
            if message.get("role") != "assistant" or not message.get("tool_calls"):
                if message.get("role") == "tool":
                    repaired.append(
                        {
                            "role": "user",
                            "content": f"[orphan tool output for {message.get('tool_call_id') or 'unknown'}]\n{message.get('content') or ''}".strip(),
                        }
                    )
                else:
                    repaired.append(message)
                index += 1
                continue

            merged_assistant = dict(message)
            merged_calls = [dict(call) for call in list(message.get("tool_calls") or []) if isinstance(call, dict)]
            merged_content = self._flatten_content(merged_assistant.get("content"))
            index += 1
            while index < len(messages) and messages[index].get("role") == "assistant" and messages[index].get("tool_calls"):
                next_assistant = dict(messages[index])
                next_content = self._flatten_content(next_assistant.get("content"))
                if next_content and next_content not in merged_content:
                    merged_content = f"{merged_content}\n{next_content}".strip()
                if next_assistant.get("reasoning_content") and not merged_assistant.get("reasoning_content"):
                    merged_assistant["reasoning_content"] = next_assistant.get("reasoning_content")
                merged_calls.extend(dict(call) for call in list(next_assistant.get("tool_calls") or []) if isinstance(call, dict))
                index += 1
            merged_assistant["tool_calls"] = merged_calls
            merged_assistant["content"] = merged_content or None
            repaired.append(merged_assistant)
            expected = [str(call.get("id") or "") for call in merged_calls if isinstance(call, dict)]
            seen: set[str] = set()
            while index < len(messages) and messages[index].get("role") == "tool":
                tool_message = dict(messages[index])
                tool_id = str(tool_message.get("tool_call_id") or "")
                if tool_id:
                    seen.add(tool_id)
                repaired.append(tool_message)
                index += 1
            for tool_id in expected:
                if tool_id and tool_id not in seen:
                    repaired.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": "Tool result was unavailable in Codex history; continue from the available context.",
                        }
                    )
        return repaired

    def _flatten_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [self._flatten_content(item) for item in content]
            return "\n".join(part for part in parts if part)
        if isinstance(content, dict):
            item_type = str(content.get("type") or "")
            if item_type in {"input_text", "output_text", "text"}:
                return str(content.get("text") or "")
            if item_type == "localImage":
                return f"[local_image:{content.get('path')}]"
            if item_type == "mention":
                return f"[file:{content.get('path') or content.get('name')}]"
            if item_type == "function_call":
                return str(content.get("arguments") or "")
            if "text" in content:
                return str(content.get("text") or "")
            if "content" in content:
                return self._flatten_content(content.get("content"))
        return json.dumps(content, ensure_ascii=False) if content is not None else ""

    def _convert_tools(self, tools: Any) -> list[dict[str, Any]]:
        if not isinstance(tools, list):
            return []
        converted = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            if str(tool.get("type") or "") != "function":
                continue
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name") or "tool",
                        "description": tool.get("description") or "",
                        "parameters": tool.get("parameters") or {},
                    },
                }
            )
        return converted

    def _sanitize_chat_tool_calls(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        calls = []
        for index, call in enumerate(value):
            if not isinstance(call, dict):
                continue
            function = dict(call.get("function") or {})
            call_id = str(call.get("id") or call.get("call_id") or f"call_{index}")
            calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": str(function.get("name") or call.get("name") or "tool"),
                        "arguments": self._safe_tool_arguments(function.get("arguments") or call.get("arguments")),
                    },
                }
            )
        return calls

    def _safe_tool_arguments(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        text = str(value or "").strip()
        if not text:
            return "{}"
        if text.startswith("```"):
            text = text.strip("`").strip()
            if "\n" in text:
                text = text.split("\n", 1)[1].strip()
        try:
            json.loads(text)
            return text
        except Exception:
            return json.dumps({"raw": text}, ensure_ascii=False, separators=(",", ":"))

    def _response_usage_from_chat_usage(self, usage: dict[str, Any]) -> dict[str, Any]:
        token_details = dict(usage.get("completion_tokens_details") or {})
        return {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "output_tokens_details": {
                "reasoning_tokens": token_details.get("reasoning_tokens", usage.get("reasoning_tokens", 0)),
            },
        }

    def _map_role(self, role: str) -> str:
        lowered = role.lower()
        if lowered in {"assistant", "system", "tool", "user"}:
            return lowered
        if lowered == "developer":
            return "system"
        return "user"

    def _merge_reasoning_content_into_assistant_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        pending_reasoning: str | None = None
        for message in messages:
            role = str(message.get("role") or "")
            content = message.get("content")
            if role == "assistant" and isinstance(content, str) and content.startswith("[reasoning summary]\n"):
                pending_reasoning = content.split("\n", 1)[1].strip()
                continue
            if pending_reasoning and role == "assistant":
                message = dict(message)
                message["reasoning_content"] = pending_reasoning
                pending_reasoning = None
            if role == "assistant" and message.get("tool_calls") and merged and merged[-1].get("role") == "assistant" and not merged[-1].get("tool_calls"):
                previous = dict(merged.pop())
                message = dict(message)
                if previous.get("content") and not message.get("content"):
                    message["content"] = previous.get("content")
                if previous.get("reasoning_content") and not message.get("reasoning_content"):
                    message["reasoning_content"] = previous.get("reasoning_content")
            merged.append(message)
        if pending_reasoning:
            merged.append({"role": "assistant", "content": "", "reasoning_content": pending_reasoning})
        return merged


class DeepSeekChatAdapter(ChatCompletionsAdapter):
    def describe(self) -> str:
        return "deepseek_chat"

    def upstream_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().upstream_payload(payload)
        merged_messages = self._merge_reasoning_content_into_assistant_messages(list(upstream_payload.get("messages") or []))
        upstream_payload["messages"] = self._repair_tool_message_sequence(merged_messages)
        effort = self._requested_effort(payload)
        if effort == "off":
            upstream_payload["thinking"] = {"type": "disabled"}
            upstream_payload.pop("reasoning_effort", None)
        elif effort in DEEPSEEK_MAX_EFFORTS:
            upstream_payload["thinking"] = {"type": "enabled"}
            upstream_payload["reasoning_effort"] = "max"
        elif effort and effort != "auto":
            upstream_payload["thinking"] = {"type": "enabled"}
            upstream_payload["reasoning_effort"] = "high"
        if upstream_payload.get("thinking", {}).get("type") == "enabled":
            upstream_payload.pop("temperature", None)
            upstream_payload.pop("top_p", None)
        return upstream_payload

    def _requested_effort(self, payload: dict[str, Any]) -> str | None:
        reasoning = payload.get("reasoning")
        if isinstance(reasoning, dict):
            effort = str(reasoning.get("effort") or "").strip().lower()
            if effort:
                return effort
        effort = str(self.profile.get("reasoning_effort") or "").strip().lower()
        return effort or None


class KimiChatAdapter(ChatCompletionsAdapter):
    def describe(self) -> str:
        return "kimi_chat"

    def supports_local_image_input(self) -> bool:
        return True

    def upstream_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().upstream_payload(payload)
        merged_messages = self._merge_reasoning_content_into_assistant_messages(list(upstream_payload.get("messages") or []))
        upstream_payload["messages"] = self._repair_tool_message_sequence(merged_messages)
        effort = self._requested_effort(payload)
        explicit_effort = self._explicit_requested_effort(payload)
        has_local_image = self._has_local_image_input(payload)
        if effort == "off":
            upstream_payload["thinking"] = {"type": "disabled"}
        elif has_local_image and explicit_effort not in KIMI_KEEP_ALL_EFFORTS:
            # Kimi K2.6 shares max_tokens between reasoning_content and visible content.
            # Keep thinking enabled for vision turns, but reserve enough output window
            # so reasoning does not starve the final visible answer.
            upstream_payload["thinking"] = {"type": "enabled"}
            max_tokens = int(upstream_payload.get("max_tokens") or 0)
            if max_tokens < KIMI_THINKING_OUTPUT_FLOOR:
                upstream_payload["max_tokens"] = KIMI_THINKING_OUTPUT_FLOOR
        elif effort == "auto" or not effort:
            upstream_payload.pop("thinking", None)
        else:
            thinking: dict[str, Any] = {"type": "enabled"}
            if effort in KIMI_KEEP_ALL_EFFORTS:
                thinking["keep"] = "all"
            upstream_payload["thinking"] = thinking
            tool_choice = upstream_payload.get("tool_choice")
            if tool_choice not in {None, "auto", "none"}:
                upstream_payload["tool_choice"] = "auto"
            max_tokens = int(upstream_payload.get("max_tokens") or 0)
            floor = KIMI_THINKING_OUTPUT_FLOOR if effort in KIMI_KEEP_ALL_EFFORTS else 16000
            if max_tokens < floor:
                upstream_payload["max_tokens"] = floor
        return upstream_payload

    def _requested_effort(self, payload: dict[str, Any]) -> str | None:
        reasoning = payload.get("reasoning")
        if isinstance(reasoning, dict):
            effort = str(reasoning.get("effort") or "").strip().lower()
            if effort:
                return effort
        effort = str(self.profile.get("reasoning_effort") or "").strip().lower()
        return effort or None

    def _explicit_requested_effort(self, payload: dict[str, Any]) -> str | None:
        reasoning = payload.get("reasoning")
        if isinstance(reasoning, dict):
            effort = str(reasoning.get("effort") or "").strip().lower()
            return effort or None
        return None

    def _has_local_image_input(self, payload: dict[str, Any]) -> bool:
        raw_input = payload.get("input")

        def walk(value: Any) -> bool:
            if isinstance(value, dict):
                item_type = str(value.get("type") or "")
                if item_type in {"localImage", "input_image", "image_url"}:
                    return True
                return any(walk(child) for child in value.values())
            if isinstance(value, list):
                return any(walk(item) for item in value)
            if isinstance(value, str):
                return '"input_image"' in value and "data:image/" in value
            return False

        return walk(raw_input)


class RouterService:
    def __init__(self, profiles_service, router_config_service=None, *, host: str = "127.0.0.1", port: int = ROUTER_PORT) -> None:
        self._profiles = profiles_service
        self._router_config = router_config_service
        self._host = host
        self._requested_port = port
        self._port = port
        self._port_auto_selected = False
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._events: list[dict[str, Any]] = []
        self._token = secrets.token_urlsafe(24)
        self._ensure_token()

    def start(self) -> None:
        with self._lock:
            if self._server is not None:
                return
            bind_port = self._port
            self._port_auto_selected = False
            if bind_port and self._port_in_use(bind_port):
                bind_port = 0
                self._port_auto_selected = True
                self._record(
                    "router_port_auto_selected",
                    {
                        "host": self._host,
                        "requested_port": self._requested_port,
                        "selected_port": "auto",
                    },
                )
            service = self

            class Handler(BaseHTTPRequestHandler):
                def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(body)

                def do_GET(self) -> None:  # noqa: N802
                    parsed = urllib.parse.urlparse(self.path)
                    if parsed.path == "/healthz":
                        self._send_json(200, {"ok": True, "service": "astrabridge", "ready": True})
                        return
                    if parsed.path == "/readyz":
                        self._send_json(200, service.status())
                        return
                    if parsed.path == "/v1/models":
                        authorization = self.headers.get("Authorization")
                        if not service._authorized(authorization):
                            service._record_auth_failure(parsed.path, authorization)
                            self._send_json(401, {"error": {"type": "auth_error", "message": "Missing or invalid router token."}})
                            return
                        self._send_json(200, {"object": "list", "data": service.list_models()})
                        return
                    self._send_json(404, {"error": {"type": "not_found", "message": "Not found."}})

                def do_POST(self) -> None:  # noqa: N802
                    parsed = urllib.parse.urlparse(self.path)
                    if parsed.path != "/v1/responses":
                        self._send_json(404, {"error": {"type": "not_found", "message": "Not found."}})
                        return
                    authorization = self.headers.get("Authorization")
                    if not service._authorized(authorization):
                        service._record_auth_failure(parsed.path, authorization)
                        self._send_json(401, {"error": {"type": "auth_error", "message": "Missing or invalid router token."}})
                        return
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                        service.forward_response(payload, self)
                    except Exception as exc:  # noqa: BLE001
                        context = service._error_context_for_payload(locals().get("payload") if isinstance(locals().get("payload"), dict) else {})
                        envelope = {
                            "error": {
                                "type": "provider_error",
                                **context,
                                "message": str(exc),
                                "actionable_hint": service._provider_error_hint(str(exc), fallback="Check provider auth, request shape, router state, or upstream connectivity."),
                            }
                        }
                        service._record("router_error", {"error": envelope["error"]})
                        self._send_json(400, envelope)

                def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                    service._record("router_http", {"message": format % args})

            try:
                self._server = ThreadingHTTPServer((self._host, bind_port), Handler)
            except OSError as exc:
                if not self._port_auto_selected and bind_port:
                    fallback_port = 0
                    if fallback_port != bind_port:
                        self._record(
                            "router_port_auto_selected_after_bind_failure",
                            {
                                "host": self._host,
                                "requested_port": self._requested_port,
                                "selected_port": "auto",
                                "error": str(exc),
                            },
                        )
                        self._server = ThreadingHTTPServer((self._host, fallback_port), Handler)
                        self._port_auto_selected = True
                    else:
                        self._record("router_bind_failed", {"host": self._host, "port": bind_port, "error": str(exc)})
                        raise RuntimeError(
                            f"Local router port is already in use or cannot be bound: {self._host}:{bind_port}. "
                            "Stop the stale AstraBridge sidecar or choose a different ASTRABRIDGE_PORT."
                        ) from exc
                else:
                    self._record("router_bind_failed", {"host": self._host, "port": bind_port, "error": str(exc)})
                    raise RuntimeError(
                        f"Local router port is already in use or cannot be bound: {self._host}:{bind_port}. "
                        "Stop the stale AstraBridge sidecar or choose a different ASTRABRIDGE_PORT."
                    ) from exc
            self._port = int(self._server.server_address[1])
            self._thread = threading.Thread(target=self._server.serve_forever, name="astrabridge", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            server = self._server
            self._server = None
            self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()

    def status(self) -> dict[str, Any]:
        profiles = self._router_profiles()
        enabled = [profile for profile in profiles if profile.get("enabled", True)]
        available_models = self.list_models()
        latest_test = self._router_config.snapshot().get("latest_test") if self._router_config is not None else None
        advertised_host = "127.0.0.1" if self._host in {"", "0.0.0.0"} else self._host
        return {
            "ok": True,
            "service": "astrabridge",
            "running": self._server is not None,
            "listen_host": self._host,
            "requested_port": self._requested_port,
            "listen_port": self._port,
            "port_auto_selected": self._port_auto_selected,
            "base_url": f"http://{advertised_host}:{self._port}/v1",
            "router_env_key": ROUTER_ENV_KEY,
            "token_loaded": bool(self._token),
            "token_fingerprint": hashlib.sha256(self._token.encode("utf-8")).hexdigest()[:12] if self._token else None,
            "provider_count": len(enabled),
            "model_count": len(available_models),
            "latest_test": latest_test,
            "providers": [
                {
                    "provider_id": profile.get("provider_id"),
                    "label": profile.get("label"),
                    "base_url": profile.get("base_url"),
                    "model": profile.get("model"),
                    "wire_api": profile.get("wire_api"),
                    "secret_loaded": bool(os.environ.get(str(profile.get("env_key") or ""))),
                }
                for profile in enabled
            ],
        }

    def events(self, *, limit: int = 50) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit or 50), 200))
        with self._lock:
            events = list(self._events[-safe_limit:])
        return {"events": events, "count": len(events)}

    def list_models(self) -> list[dict[str, Any]]:
        models: list[dict[str, Any]] = []
        configured = self._router_config.models() if self._router_config is not None else []
        if configured:
            for model in configured:
                if not model.get("enabled", True):
                    continue
                provider = self._provider_by_id(str(model.get("provider") or ""))
                profile = {**provider, "model": model.get("native_model"), "adapter_profile": model.get("adapter_profile")}
                models.append(self._model_metadata(str(model.get("id") or ""), profile, model))
            return models
        for profile in self._router_profiles():
            if not profile.get("enabled", True):
                continue
            provider = str(profile.get("provider_id") or "").strip()
            model = str(profile.get("model") or "").strip()
            if not provider or not model:
                continue
            models.append(self._model_metadata(f"{provider}/{model}", profile, {}))
        return models

    def forward_response(self, payload: dict[str, Any], handler: BaseHTTPRequestHandler) -> None:
        chosen = self._resolve_profile(payload)
        secret = os.environ.get(str(chosen.get("env_key") or ""))
        if not secret:
            raise RuntimeError(f"Provider secret is not loaded for env key {chosen.get('env_key')}.")
        adapter = self._adapter_for(chosen)
        base_url = str(chosen.get("base_url") or "").rstrip("/")
        wire_api = adapter.wire_api()
        upstream_payload = adapter.upstream_payload(payload)
        parsed = urllib.parse.urlparse(f"{base_url}{adapter.endpoint_path()}")
        stream = bool(payload.get("stream"))
        upstream_stream = stream and (adapter.supports_passthrough_stream() or wire_api == "chat")
        response = self._request_upstream(
            parsed=parsed,
            payload=upstream_payload,
            bearer=secret,
            stream=upstream_stream,
        )
        retry_attempt = 0
        error_text = ""
        while response.status >= 400:
            error_text = response.read().decode("utf-8", errors="replace")
            if not self._should_retry_provider_error(chosen, response.status, error_text, retry_attempt):
                break
            retry_attempt += 1
            self._record(
                "provider_retry",
                {
                    "provider": chosen.get("provider_id"),
                    "status": response.status,
                    "attempt": retry_attempt,
                    "reason": self._provider_error_code(error_text) or "transient_provider_error",
                },
            )
            response.close()
            time.sleep(min(1.5 * retry_attempt, 4.0))
            response = self._request_upstream(
                parsed=parsed,
                payload=upstream_payload,
                bearer=secret,
                stream=upstream_stream,
            )
        if response.status >= 400:
            normalized = self._normalize_provider_error(chosen, response.status, error_text)
            encoded = json.dumps(normalized, ensure_ascii=False).encode("utf-8")
            handler.send_response(response.status)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.send_header("Content-Length", str(len(encoded)))
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            handler.wfile.write(encoded)
            self._record("provider_error", {"provider": chosen.get("provider_id"), "status": response.status, "error": normalized})
            response.close()
            return
        if wire_api == "responses":
            handler.send_response(response.status)
            handler.send_header("Content-Type", response.getheader("Content-Type", "application/json; charset=utf-8"))
            handler.send_header("Cache-Control", "no-store")
            handler.end_headers()
            if stream:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    handler.wfile.write(chunk)
                    handler.wfile.flush()
            else:
                body = response.read()
                handler.wfile.write(body)
        else:
            if stream:
                self._stream_chat_completion(adapter, response, payload, handler)
            else:
                body = response.read()
                upstream_json = json.loads(body.decode("utf-8") or "{}")
                client_response = adapter.client_response_from_upstream_json(upstream_json, payload)
                encoded = json.dumps(client_response, ensure_ascii=False).encode("utf-8")
                handler.send_response(response.status)
                handler.send_header("Content-Type", "application/json; charset=utf-8")
                handler.send_header("Content-Length", str(len(encoded)))
                handler.send_header("Cache-Control", "no-store")
                handler.end_headers()
                handler.wfile.write(encoded)
        self._record(
            "responses_forwarded",
            {
                "provider": chosen.get("provider_id"),
                "model": upstream_payload.get("model"),
                "stream": stream,
                "wire_api": wire_api,
                "adapter": adapter.describe(),
                "request": redact_sensitive(payload),
                "upstream_request": redact_sensitive(upstream_payload),
                "status": response.status,
            },
        )
        response.close()

    def _resolve_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_model = str(payload.get("model") or "").strip()
        if "/" not in raw_model:
            raise RuntimeError("Router models must be prefixed as provider/model.")
        provider_id, native_model = raw_model.split("/", 1)
        configured_models = self._router_config.models() if self._router_config is not None else []
        if configured_models:
            for item in configured_models:
                if not item.get("enabled", True):
                    continue
                if str(item.get("id") or "") == raw_model:
                    provider = self._provider_by_id(provider_id)
                    return {**provider, "model": native_model, "adapter_profile": item.get("adapter_profile")}
        for profile in self._router_profiles():
            if not profile.get("enabled", True):
                continue
            if str(profile.get("provider_id") or "").strip() == provider_id and str(profile.get("model") or "").strip() == native_model:
                return profile
        raise RuntimeError(f"No router profile matches model {raw_model}.")

    def _router_profiles(self) -> list[dict[str, Any]]:
        if self._router_config is not None:
            providers = self._router_config.providers()
            if providers:
                return [
                    {
                        "enabled": item.get("enabled", True),
                        "provider_id": item.get("id"),
                        "label": item.get("display_name"),
                        "base_url": item.get("base_url"),
                        "model": item.get("default_model"),
                        "wire_api": item.get("adapter_type"),
                        "adapter_profile": item.get("adapter_profile"),
                        "env_key": item.get("env_key"),
                        "auth_mode": item.get("auth_mode"),
                        "secret_ref": item.get("auth_key_ref"),
                        "proxy_mode": item.get("proxy_mode"),
                        "proxy_url": item.get("proxy_url"),
                    }
                    for item in providers
                ]
        profiles = self._profiles.list_profiles().get("profiles") or []
        router_profiles = []
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            if not profile.get("base_url"):
                continue
            router_profiles.append({"enabled": True, **profile})
        return router_profiles

    def _adapter_for(self, profile: dict[str, Any]) -> ProviderAdapter:
        signals = " ".join(
            str(profile.get(key) or "")
            for key in ("provider_id", "adapter_profile", "wire_api", "base_url", "model")
        ).strip().lower()
        wire_api = str(profile.get("wire_api") or "").strip().lower()
        if "qwen" in signals or "dashscope" in signals:
            return QwenResponsesAdapter(self, profile)
        if "deepseek" in signals:
            return DeepSeekChatAdapter(self, profile)
        if "kimi" in signals or "moonshot" in signals:
            return KimiChatAdapter(self, profile)
        if wire_api == "chat":
            return ChatCompletionsAdapter(self, profile)
        return ProviderAdapter(self, profile)

    def _adapter_for_provider(self, provider_id: str) -> ProviderAdapter:
        return self._adapter_for({"provider_id": provider_id})

    def _provider_by_id(self, provider_id: str) -> dict[str, Any]:
        for profile in self._router_profiles():
            if str(profile.get("provider_id") or "") == provider_id:
                return profile
        raise RuntimeError(f"Unknown provider {provider_id}.")

    def _model_metadata(self, model_id: str, profile: dict[str, Any], configured_model: dict[str, Any]) -> dict[str, Any]:
        context_window = int(configured_model.get("advertised_context_window") or _fallback_context_window(profile) or 128000)
        native_model = str(profile.get("model") or model_id.split("/", 1)[-1])
        display_name = str(configured_model.get("display_name") or model_id)
        entry = model_catalog_entry(
            model_id=model_id,
            provider_id=str(profile.get("provider_id") or ""),
            native_model=native_model,
            display_name=display_name,
            context_window=context_window,
            reasoning_effort=profile.get("reasoning_effort"),
            configured_model=configured_model,
            auto_compact_token_limit=_optional_positive_int(configured_model.get("auto_compact_token_limit")),
        )
        return {
            **entry,
            "id": model_id,
            "object": "model",
            "created": 0,
            "owned_by": profile.get("provider_id"),
            "adapter": self._adapter_for(profile).describe(),
        }

    def _authorized(self, authorization: str | None) -> bool:
        token = self._token
        if not token:
            return False
        prefix = "Bearer "
        return bool(authorization and authorization.startswith(prefix) and secrets.compare_digest(authorization[len(prefix):], token))

    def _record_auth_failure(self, path: str, authorization: str | None) -> None:
        prefix = "Bearer "
        provided = authorization[len(prefix):] if authorization and authorization.startswith(prefix) else ""
        self._record(
            "router_auth_failed",
            {
                "path": path,
                "authorization_present": bool(authorization),
                "provided_fingerprint": hashlib.sha256(provided.encode("utf-8")).hexdigest()[:12] if provided else None,
                "expected_fingerprint": hashlib.sha256(self._token.encode("utf-8")).hexdigest()[:12] if self._token else None,
            },
        )

    def _ensure_token(self) -> None:
        os.environ[ROUTER_ENV_KEY] = self._token

    def rotate_token(self) -> dict[str, Any]:
        self._token = secrets.token_urlsafe(24)
        os.environ[ROUTER_ENV_KEY] = self._token
        return self.status()

    def resolve_reasoning_effort(self, profile: dict[str, Any], model_id: Any) -> str | None:
        if self._router_config is None:
            return str(profile.get("reasoning_effort") or "").strip().lower() or None
        reasoning = self._router_config.reasoning()
        model_overrides = dict(reasoning.get("model_overrides") or {})
        provider_overrides = dict(reasoning.get("provider_overrides") or {})
        model_key = str(model_id or "")
        provider_key = str(profile.get("provider_id") or "")
        return (
            str(model_overrides.get(model_key) or "").strip().lower()
            or str(provider_overrides.get(provider_key) or "").strip().lower()
            or str(reasoning.get("global_effort") or profile.get("reasoning_effort") or "").strip().lower()
            or None
        )

    def preview_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile = self._resolve_profile(payload)
        adapter = self._adapter_for(profile)
        warnings = self.temperature_warnings(profile, payload.get("model"), payload.get("temperature"))
        return {
            "provider": profile.get("provider_id"),
            "model": payload.get("model"),
            "adapter": adapter.describe(),
            "warnings": warnings,
            "upstream_payload": redact_sensitive(adapter.upstream_payload(payload)),
        }

    def test_provider(self, provider_id: str, model_id: str | None = None, *, stream: bool = False) -> dict[str, Any]:
        provider = self._provider_by_id(provider_id)
        model = self._normalize_model_id(provider_id, model_id or provider.get("default_model") or provider.get("model"))
        payload = {"model": model, "input": "Reply with exactly: ok", "stream": stream}
        parsed_preview = self.preview_payload(payload)
        buffer = _BufferHandler()
        self.forward_response(payload, buffer)
        result = {
            "ok": buffer.status_code == 200,
            "provider": provider_id,
            "model": model,
            "stream": stream,
            "status": buffer.status_code,
            "content_type": buffer.headers.get("Content-Type"),
            "preview": parsed_preview["upstream_payload"],
            "response_excerpt": buffer.wfile.getvalue().decode("utf-8", errors="replace")[:1200],
        }
        if self._router_config is not None:
            self._router_config.record_test_result(result)
        return result

    def test_model_case(self, *, provider_id: str, model_id: str, effort: str | None = None, temperature: float | None = None, stream: bool = False) -> dict[str, Any]:
        provider = self._provider_by_id(provider_id)
        model_id = self._normalize_model_id(provider_id, model_id)
        payload: dict[str, Any] = {"model": model_id, "input": "Reply with exactly: ok", "stream": stream}
        if effort:
            payload["reasoning"] = {"effort": effort}
        if temperature is not None:
            payload["temperature"] = temperature
        parsed_preview = self.preview_payload(payload)
        buffer = _BufferHandler()
        self.forward_response(payload, buffer)
        result = {
            "ok": buffer.status_code == 200,
            "provider": provider_id,
            "model": model_id,
            "native_model": provider.get("model"),
            "effort": effort,
            "temperature": temperature,
            "stream": stream,
            "status": buffer.status_code,
            "content_type": buffer.headers.get("Content-Type"),
            "warnings": parsed_preview.get("warnings") or [],
            "preview": parsed_preview["upstream_payload"],
            "response_excerpt": buffer.wfile.getvalue().decode("utf-8", errors="replace")[:1200],
        }
        if self._router_config is not None:
            self._router_config.record_test_result(result)
        return result

    def _normalize_model_id(self, provider_id: str, model_id: Any) -> str:
        raw = str(model_id or "").strip()
        if not raw:
            raise RuntimeError(f"No model configured for provider {provider_id}.")
        if "/" in raw:
            return raw
        return f"{provider_id}/{raw}"

    def apply_temperature_config(self, profile: dict[str, Any], upstream_payload: dict[str, Any], model_id: Any) -> None:
        if "temperature" not in upstream_payload:
            return
        value = _optional_float(upstream_payload.get("temperature"))
        if value is None:
            upstream_payload.pop("temperature", None)
            return
        policy = self._temperature_policy(profile, model_id)
        if policy == "qwen_omit_zero_clamp_1":
            if value <= 0:
                upstream_payload.pop("temperature", None)
                return
            upstream_payload["temperature"] = min(max(value, 0.00001), 1.0)
            return
        if policy == "kimi_only_temperature_1":
            if abs(value - 1.0) > 0.000001:
                upstream_payload.pop("temperature", None)
                return
            upstream_payload["temperature"] = 1.0
            return
        upstream_payload["temperature"] = min(max(value, 0.0), 2.0)

    def temperature_warnings(self, profile: dict[str, Any], model_id: Any, temperature: Any) -> list[str]:
        value = _optional_float(temperature)
        if value is None:
            return []
        policy = self._temperature_policy(profile, model_id)
        if policy == "qwen_omit_zero_clamp_1":
            if value <= 0:
                return ["Qwen/DashScope compatible mode uses (0, 1.0] for temperature; 0 is omitted from upstream payload."]
            if value > 1:
                return ["Qwen/DashScope compatible mode caps temperature at 1.0; UI value was clamped for upstream."]
        if policy == "kimi_only_temperature_1":
            if abs(value - 1.0) > 0.000001:
                return ["Kimi K2 models only accept temperature=1; this UI value is omitted from the upstream payload."]
        if value < 0 or value > 2:
            return ["Temperature was clamped to the OpenAI-compatible 0-2 range."]
        return []

    def _temperature_policy(self, profile: dict[str, Any], model_id: Any) -> str:
        configured_models = self._router_config.models() if self._router_config is not None else []
        for item in configured_models:
            if str(item.get("id") or "") == str(model_id or ""):
                policy = str(item.get("temperature_adapter_policy") or "").strip()
                if policy:
                    return policy
        signals = " ".join(str(profile.get(key) or "") for key in ("provider_id", "base_url", "model", "adapter_profile")).lower()
        if "qwen" in signals or "dashscope" in signals:
            return "qwen_omit_zero_clamp_1"
        if "kimi" in signals or "moonshot" in signals:
            return "kimi_only_temperature_1"
        return "pass_through_0_2"

    def _request_upstream(self, *, parsed: urllib.parse.ParseResult, payload: dict[str, Any], bearer: str, stream: bool) -> http.client.HTTPResponse:
        if parsed.scheme not in {"http", "https"}:
            raise RuntimeError(f"Unsupported upstream scheme: {parsed.scheme}")
        headers = {
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = http.client.HTTPSConnection(parsed.hostname, port, timeout=300, context=ssl.create_default_context())
        else:
            connection = http.client.HTTPConnection(parsed.hostname, port, timeout=300)
        target = parsed.path or "/responses"
        if parsed.query:
            target += f"?{parsed.query}"
        connection.request("POST", target, body=body, headers=headers)
        return connection.getresponse()

    def _should_retry_provider_error(self, profile: dict[str, Any], status: int, text: str, attempt: int) -> bool:
        if attempt >= 2:
            return False
        provider = str(profile.get("provider_id") or "").lower()
        code = (self._provider_error_code(text) or "").lower()
        message = text.lower()
        if status in {502, 503, 504}:
            return True
        if status == 429 and ("overloaded" in message or code in {"engine_overloaded_error", "rate_limit_error"}):
            return True
        return "kimi" in provider and status == 429 and "engine_overloaded" in message

    def _provider_error_code(self, text: str) -> str | None:
        try:
            payload = json.loads(text)
            error = dict(payload.get("error") or payload)
            code = error.get("code") or error.get("type")
            return str(code) if code else None
        except Exception:
            return None

    def _port_in_use(self, port: int | None = None) -> bool:
        probe_port = int(port or self._port or 0)
        if probe_port <= 0:
            return False
        host = "127.0.0.1" if self._host in {"", "0.0.0.0"} else self._host
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex((host, probe_port)) == 0

    def _record(self, kind: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self._events.append({"kind": kind, **payload})

    def _normalize_provider_error(self, profile: dict[str, Any], status: int, text: str) -> dict[str, Any]:
        native_code = None
        message = text.strip() or "Provider rejected request."
        try:
            payload = json.loads(text)
            error = dict(payload.get("error") or payload)
            native_code = error.get("code") or error.get("type")
            message = str(error.get("message") or message)
        except Exception:
            pass
        hint = self._provider_error_hint(message, fallback="Check provider auth, request shape, or reasoning/tool compatibility.")
        return {
            "error": {
                "type": "provider_error",
                "provider": profile.get("provider_id"),
                "native_status": status,
                "native_code": native_code,
                "message": message,
                "actionable_hint": hint,
            }
        }

    @staticmethod
    def _provider_error_hint(message: str, *, fallback: str) -> str:
        lowered = str(message or "").lower()
        context_markers = (
            "context",
            "maximum context",
            "context length",
            "context window",
            "tokens exceeded",
            "too many tokens",
            "maximum tokens",
            "input too long",
        )
        if any(marker in lowered for marker in context_markers):
            return "The provider hit a context limit. Reduce history or attachments; the router does not truncate automatically."
        return fallback

    def _error_context_for_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_text = str(payload.get("model") or "")
        provider = ""
        model = model_text
        if "/" in model_text:
            provider, model = model_text.split("/", 1)
        if not provider:
            try:
                profile = self._resolve_profile(payload)
                provider = str(profile.get("provider_id") or "")
                model = str(profile.get("model") or model)
            except Exception:
                pass
        return redact_sensitive({"provider": provider or None, "model": model or None})

    def _stream_chat_completion(self, adapter: ProviderAdapter, response: http.client.HTTPResponse, original_payload: dict[str, Any], handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(response.status)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        response_id = f"resp_router_{int(time.time())}"
        message_item = {"id": "msg_stream", "type": "message", "role": "assistant", "status": "in_progress", "content": []}
        self._write_sse(handler, {"type": "response.created", "response": {"id": response_id, "object": "response", "status": "in_progress"}})
        self._write_sse(handler, {"type": "response.output_item.added", "output_index": 0, "item": message_item})
        self._write_sse(
            handler,
            {
                "type": "response.content_part.added",
                "item_id": "msg_stream",
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": ""},
            },
        )
        partial_text = []
        partial_reasoning = []
        reasoning_stream_started = False
        partial_tool_calls: dict[int, dict[str, Any]] = {}
        stream_usage: dict[str, Any] = {}
        pending_lines = ""
        for chunk in iter(lambda: response.read(4096), b""):
            pending_lines += chunk.decode("utf-8", errors="replace")
            while "\n" in pending_lines:
                line, pending_lines = pending_lines.split("\n", 1)
                stripped = line.strip()
                if not stripped.startswith("data:"):
                    continue
                data = stripped[5:].strip()
                if data == "[DONE]":
                    continue
                try:
                    event = json.loads(data)
                except Exception:
                    continue
                if isinstance(event.get("usage"), dict):
                    stream_usage = dict(event.get("usage") or {})
                choices = list(event.get("choices") or [])
                if not choices:
                    continue
                delta = dict(choices[0].get("delta") or {})
                content = delta.get("content")
                reasoning_content = delta.get("reasoning_content")
                for call_delta in list(delta.get("tool_calls") or []):
                    if not isinstance(call_delta, dict):
                        continue
                    index = int(call_delta.get("index") if call_delta.get("index") is not None else len(partial_tool_calls))
                    call = partial_tool_calls.setdefault(index, {"id": f"call_stream_{index}", "type": "function", "function": {"name": "", "arguments": ""}})
                    if call_delta.get("id"):
                        call["id"] = str(call_delta.get("id"))
                    function_delta = dict(call_delta.get("function") or {})
                    function = dict(call.get("function") or {})
                    if function_delta.get("name"):
                        function["name"] = str(function_delta.get("name"))
                    if function_delta.get("arguments"):
                        function["arguments"] = str(function.get("arguments") or "") + str(function_delta.get("arguments"))
                    call["function"] = function
                if reasoning_content:
                    if not reasoning_stream_started:
                        reasoning_stream_started = True
                        self._write_sse(
                            handler,
                            {
                                "type": "response.output_item.added",
                                "output_index": 1,
                                "item": {
                                    "id": "reasoning_stream",
                                    "type": "reasoning",
                                    "summary": [],
                                    "content": [],
                                    "status": "in_progress",
                                },
                            },
                        )
                    self._write_sse(
                        handler,
                        {
                            "type": "response.reasoning_text.delta",
                            "item_id": "reasoning_stream",
                            "output_index": 1,
                            "delta": str(reasoning_content),
                        },
                    )
                    partial_reasoning.append(str(reasoning_content))
                if content:
                    partial_text.append(str(content))
                    self._write_sse(handler, {"type": "response.output_text.delta", "item_id": "msg_stream", "output_index": 0, "content_index": 0, "delta": str(content)})
        text = "".join(partial_text)
        if isinstance(adapter, ChatCompletionsAdapter):
            text = adapter._visible_text_or_reasoning_only_notice(text, "".join(partial_reasoning), bool(partial_tool_calls))
            if text and not partial_text and partial_reasoning and not partial_tool_calls:
                self._write_sse(handler, {"type": "response.output_text.delta", "item_id": "msg_stream", "output_index": 0, "content_index": 0, "delta": text})
        self._write_sse(handler, {"type": "response.output_text.done", "item_id": "msg_stream", "output_index": 0, "content_index": 0, "text": text})
        self._write_sse(
            handler,
            {
                "type": "response.content_part.done",
                "item_id": "msg_stream",
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": text},
            },
        )
        output = []
        message_done_item = {"id": "msg_stream", "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}], "status": "completed"}
        output.append(message_done_item)
        self._write_sse(handler, {"type": "response.output_item.done", "output_index": 0, "item": message_done_item})
        if partial_reasoning:
            reasoning_item = {"id": "reasoning_stream", "type": "reasoning", "summary": ["".join(partial_reasoning)], "content": ["".join(partial_reasoning)]}
            reasoning_index = len(output)
            output.append(reasoning_item)
            if not reasoning_stream_started:
                self._write_sse(handler, {"type": "response.output_item.added", "output_index": reasoning_index, "item": reasoning_item})
            self._write_sse(handler, {"type": "response.output_item.done", "output_index": reasoning_index, "item": reasoning_item})
        for index, call in sorted(partial_tool_calls.items()):
            function = dict(call.get("function") or {})
            call_id = str(call.get("id") or f"call_stream_{index}")
            tool_item = {
                "id": f"fc_{call_id}",
                "type": "function_call",
                "call_id": call_id,
                "name": function.get("name") or "tool",
                "arguments": adapter._safe_tool_arguments(function.get("arguments")) if isinstance(adapter, ChatCompletionsAdapter) else str(function.get("arguments") or "{}"),
                "status": "completed",
            }
            output_index = len(output)
            output.append(tool_item)
            self._write_sse(handler, {"type": "response.output_item.added", "output_index": output_index, "item": tool_item})
            self._write_sse(handler, {"type": "response.output_item.done", "output_index": output_index, "item": tool_item})
        final_response = {
            "id": response_id,
            "object": "response",
            "status": "completed",
            "model": original_payload.get("model"),
            "output": output,
            "output_text": text,
        }
        if stream_usage and isinstance(adapter, ChatCompletionsAdapter):
            final_response["usage"] = adapter._response_usage_from_chat_usage(stream_usage)
        self._write_sse(handler, {"type": "response.completed", "response": final_response})
        handler.wfile.write(b"data: [DONE]\n\n")
        handler.wfile.flush()

    def _write_sse(self, handler: BaseHTTPRequestHandler, event: dict[str, Any]) -> None:
        handler.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
        handler.wfile.flush()


def _fallback_context_window(profile: dict[str, Any]) -> int | None:
    signals = " ".join(str(profile.get(key) or "") for key in ("provider_id", "base_url", "model")).lower()
    provider = str(profile.get("provider_id") or "")
    model = str(profile.get("model") or "")
    return known_context_window(provider, model) or known_context_window(signals, signals)


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


class _BufferHandler:
    def __init__(self) -> None:
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.body = b""
        self.wfile = BytesIO()

    def send_response(self, status_code: int) -> None:
        self.status_code = status_code

    def send_header(self, key: str, value: str) -> None:
        self.headers[key] = value

    def end_headers(self) -> None:
        return

