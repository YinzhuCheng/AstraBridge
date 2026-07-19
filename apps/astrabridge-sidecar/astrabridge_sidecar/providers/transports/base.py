from __future__ import annotations

import base64
import hashlib
import inspect
import json
import mimetypes
import re
import time
import urllib.parse
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Any

from ...reasoning_policy import normalize_reasoning_effort
from ..failures import classify_runtime_failure
from ..ir import NormalizedResponse, ProviderWarning, RawProviderArtifactRef, ReasoningState, ToolCall, Usage
from ..tooling import (
    enforce_tool_message_sequence,
    normalize_tool_calls,
    sanitize_tool_definitions,
    summarize_tool_output,
    tool_output_char_limit,
)


LOCAL_IMAGE_MAX_BYTES = 100 * 1024 * 1024
EMBEDDED_INPUT_IMAGE_BLOCK_RE = re.compile(
    r'\{[^{}]*"type"\s*:\s*"input_image"[^{}]*"image_url"\s*:\s*"(data:image/[^"]+)"[^{}]*\}',
    re.DOTALL,
)
EMBEDDED_IMAGE_URL_RE = re.compile(r'"image_url"\s*:\s*"(data:image/[^"]+)"')


class ProviderTransport(ABC):
    def __init__(self, router: Any, profile: dict[str, Any]) -> None:
        self.router = router
        self.profile = profile

    @abstractmethod
    def convert_messages(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def convert_tools(self, tools: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def normalize_response(self, raw: Any, original_payload: dict[str, Any]) -> NormalizedResponse:
        raise NotImplementedError

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
            summarized_output, _warnings = summarize_tool_output(output, char_limit=self._tool_output_char_limit())
            parts.append(f"output:\n{summarized_output}")
        return "\n".join(parts) or "Command completed with no captured output."

    def _tool_output_char_limit(self) -> int:
        return tool_output_char_limit(self.profile.get("tool_output_token_limit"))

    def _transition_summary_message(self, item: dict[str, Any]) -> str:
        item_type = str(item.get("type") or "")
        if item_type == "contextCompaction":
            return "[context compaction]\nThread context was compacted before this turn. Continue from the surviving summary, tool results, and recent file state."
        if item_type == "enteredReviewMode":
            review = str(item.get("review") or "").strip()
            return f"[review mode entered]\n{review}".strip()
        if item_type == "exitedReviewMode":
            review = str(item.get("review") or "").strip()
            return f"[review mode exited]\n{review}".strip()
        if item_type != "collabAgentToolCall":
            return ""
        tool = str(item.get("tool") or "").strip()
        receivers = [str(value).strip() for value in list(item.get("receiverThreadIds") or []) if str(value).strip()]
        prompt = str(item.get("prompt") or "").strip()
        model = str(item.get("model") or "").strip()
        effort = str(item.get("reasoningEffort") or "").strip()
        states = item.get("agentsStates") or {}
        lines: list[str] = []
        if tool == "spawnAgent":
            lines.append("[forked collaborator thread]")
            if receivers:
                lines.append(f"Spawned collaborator thread(s): {', '.join(receivers)}")
            else:
                lines.append("Spawned a collaborator thread.")
        elif tool == "sendInput":
            lines.append("[collaborator follow-up]")
            if receivers:
                lines.append(f"Sent follow-up input to: {', '.join(receivers)}")
        elif tool == "resumeAgent":
            lines.append("[collaborator resumed]")
            if receivers:
                lines.append(f"Resumed collaborator thread(s): {', '.join(receivers)}")
        elif tool == "wait":
            lines.append("[collaborator wait]")
            lines.append("Waiting for collaborator progress.")
        elif tool == "closeAgent":
            lines.append("[collaborator closed]")
            if receivers:
                lines.append(f"Closed collaborator thread(s): {', '.join(receivers)}")
        else:
            lines.append("[collaborator transition]")
            lines.append(f"Recorded collaborator tool event: {tool or 'unknown'}")
        if model:
            lines.append(f"Model: {model}")
        if effort:
            lines.append(f"Reasoning effort: {effort}")
        if prompt:
            lines.append(f"Prompt summary: {prompt[:240]}")
        if isinstance(states, dict) and states:
            lines.append(f"Known collaborator states: {', '.join(sorted(states.keys()))}")
        return "\n".join(lines).strip()

    def endpoint_path(self) -> str:
        return "/responses"

    def wire_api(self) -> str:
        return str(self.profile.get("wire_api") or "responses")

    def describe(self) -> str:
        return "responses"

    def transport_signature(self) -> str:
        return transport_signature_for_class(type(self))

    def supports_passthrough_stream(self) -> bool:
        return True

    def supports_local_image_input(self) -> bool:
        return False

    def classify_error(self, raw_message: str, *, model_id: str | None = None) -> dict[str, Any]:
        return classify_runtime_failure(
            raw_message,
            current_provider=self._provider_id(),
            current_model=str(model_id or self.profile.get("model") or "").strip(),
        ).to_payload()

    def cancellation_contract(self) -> dict[str, Any]:
        return {
            "owner": "runtime_turn",
            "strategy": "interrupt_provider_thread",
            "supports_explicit_provider_abort": False,
            "transport_stateful_cancel": False,
        }

    def _local_image_data_url(self, raw_path: str) -> str:
        path = self._local_image_path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(f"image file not found: {raw_path}")
        size = path.stat().st_size
        if size > LOCAL_IMAGE_MAX_BYTES:
            raise ValueError(f"image file is too large for provider vision input: {size} bytes")
        mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
        if mime_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            raise ValueError(f"unsupported image format: {mime_type}")
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

    def _provider_id(self) -> str:
        return str(self.profile.get("provider_id") or self.profile.get("provider_family") or "").strip()

    def _model_id(self, original_payload: dict[str, Any]) -> str:
        return str(original_payload.get("model") or self.profile.get("model") or "").strip()

    def _reasoning_state(
        self,
        summary: str | None,
        *,
        model_id: str | None = None,
        replayable: bool = False,
        opaque_artifacts: list[dict[str, Any]] | None = None,
    ) -> ReasoningState | None:
        if not summary and not opaque_artifacts:
            return None
        return ReasoningState(
            provider_id=self._provider_id(),
            model_id=str(model_id or self.profile.get("model") or "").strip(),
            replayable=replayable,
            visible_summary=summary,
            opaque_artifacts=list(opaque_artifacts or []),
        )

    def _warning(self, code: str, message: str, severity: str = "warning") -> ProviderWarning:
        normalized_severity = severity if severity in {"info", "warning", "error"} else "warning"
        return ProviderWarning(code=code, message=message, severity=normalized_severity)

    def _raw_ref(self, *, kind: str, locator: Any, summary: str | None = None) -> RawProviderArtifactRef:
        return RawProviderArtifactRef(kind=kind, locator=str(locator or "unknown"), redaction_status="redacted", summary=summary)

    def _explicit_reasoning_effort(self, payload: dict[str, Any]) -> str | None:
        reasoning = payload.get("reasoning")
        if not isinstance(reasoning, dict):
            return None
        return normalize_reasoning_effort(reasoning.get("effort"))

    def _resolved_reasoning_effort(self, payload: dict[str, Any]) -> str | None:
        explicit = self._explicit_reasoning_effort(payload)
        if explicit is not None:
            return explicit
        return normalize_reasoning_effort(self.router.resolve_reasoning_effort(self.profile, payload.get("model")))

    def apply_reasoning_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = dict(payload)
        effort = self._resolved_reasoning_effort(payload)
        if effort:
            upstream_payload["reasoning"] = {"effort": effort}
        else:
            upstream_payload.pop("reasoning", None)
        return upstream_payload

    def upstream_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.build_request(payload)

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
            elif item.get("type") == "reasoning":
                events.append({"type": "response.output_item.added", "output_index": output_index, "item": item})
                events.append(
                    {
                        "type": "response.output_item.done",
                        "output_index": output_index,
                        "item": {**item, "status": "completed"},
                    }
                )
            elif item.get("type") == "function_call":
                events.append({"type": "response.output_item.added", "output_index": output_index, "item": item})
                events.append(
                    {
                        "type": "response.output_item.done",
                        "output_index": output_index,
                        "item": {**item, "status": "completed"},
                    }
                )
        events.append({"type": "response.completed", "response": response})
        return events


class ResponsesTransport(ProviderTransport):
    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = self.apply_reasoning_config(payload)
        upstream_payload["model"] = str(self.profile.get("model") or "")
        raw_input = payload.get("input")
        if isinstance(raw_input, list):
            upstream_payload["input"] = self.convert_messages(payload)
        elif isinstance(raw_input, dict):
            converted = self.convert_messages(payload)
            upstream_payload["input"] = converted[0] if len(converted) == 1 else converted
        self.router.apply_temperature_config(self.profile, upstream_payload, payload.get("model"))
        return upstream_payload

    def convert_messages(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw_input = payload.get("input")
        if isinstance(raw_input, list):
            converted: list[dict[str, Any]] = []
            for item in raw_input:
                converted.extend(self._convert_responses_input_item(item))
            return converted
        if isinstance(raw_input, dict):
            return self._convert_responses_input_item(raw_input)
        return list(raw_input or []) if isinstance(raw_input, list) else []

    def convert_tools(self, tools: Any) -> list[dict[str, Any]]:
        sanitized, _warnings = sanitize_tool_definitions(tools)
        return sanitized if isinstance(tools, list) else []

    def normalize_response(self, raw: Any, original_payload: dict[str, Any]) -> NormalizedResponse:
        output = list((raw or {}).get("output") or [])
        text_parts: list[str] = []
        reasoning_summary: str | None = None
        reasoning_items: list[dict[str, Any]] = []
        tool_calls: list[ToolCall] = []
        warnings: list[ProviderWarning] = []
        for item in output:
            item_type = str(item.get("type") or "")
            if item_type == "reasoning":
                reasoning_items.append(dict(item))
                summary = item.get("summary") or item.get("content") or []
                reasoning_summary = "\n".join(str(part) for part in summary if str(part).strip()) or reasoning_summary
            elif item_type == "message":
                for content in list(item.get("content") or []):
                    if str(content.get("type") or "") == "output_text":
                        text_parts.append(str(content.get("text") or ""))
            elif item_type == "function_call":
                repaired_calls, repair_warnings = normalize_tool_calls(
                    [
                        {
                            "id": item.get("call_id") or item.get("id"),
                            "name": item.get("name"),
                            "arguments": item.get("arguments"),
                        }
                    ],
                    allow_parallel=bool(self.profile.get("supports_parallel_tool_calls", False)),
                )
                warnings.extend(self._warning("tool_call_repair", warning, "warning") for warning in repair_warnings)
                for call in repaired_calls:
                    tool_calls.append(
                        ToolCall(
                            id=str(call.get("id") or "call_router"),
                            name=str((call.get("function") or {}).get("name") or "tool"),
                            arguments_json=str((call.get("function") or {}).get("arguments") or "{}"),
                            provider_data={"response_item_id": item.get("id")},
                        )
                    )
        usage = dict((raw or {}).get("usage") or {})
        normalized_usage = None
        if usage:
            token_details = dict(usage.get("output_tokens_details") or {})
            normalized_usage = Usage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                reasoning_tokens=token_details.get("reasoning_tokens"),
                total_tokens=usage.get("total_tokens"),
            )
        if reasoning_summary and not text_parts and not tool_calls:
            warnings.append(self._warning("reasoning_only_response", "Provider returned reasoning without visible assistant text.", "info"))
        reasoning_state = self._reasoning_state(
            reasoning_summary,
            model_id=self._model_id(original_payload),
            replayable=False,
            opaque_artifacts=[
                {
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "summary_count": len(list(item.get("summary") or [])),
                }
                for item in reasoning_items[:8]
            ],
        )
        return NormalizedResponse(
            text="".join(text_parts),
            reasoning_summary=reasoning_summary,
            reasoning_state=reasoning_state,
            tool_calls=tool_calls,
            usage=normalized_usage,
            finish_reason=str((raw or {}).get("status") or "completed"),
            provider_data={
                "model": self._model_id(original_payload),
                "response_id": (raw or {}).get("id"),
                "status": (raw or {}).get("status"),
                "output_types": [str(item.get("type") or "") for item in output],
                "tool_call_count": len(tool_calls),
            },
            warnings=warnings,
            raw_ref=self._raw_ref(kind="responses_output", locator=(raw or {}).get("id"), summary=f"{len(output)} output item(s)"),
        )

    def _convert_responses_input_item(self, item: Any) -> list[dict[str, Any]]:
        if not isinstance(item, dict):
            return [item] if isinstance(item, dict) else [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": str(item)}]}]
        item_type = str(item.get("type") or "")
        if item_type in {"contextCompaction", "enteredReviewMode", "exitedReviewMode", "collabAgentToolCall"}:
            summary = self._transition_summary_message(item)
            if not summary:
                return []
            return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": summary}]}]
        if item_type == "commandExecution":
            tool_id = str(item.get("id") or item.get("call_id") or "tool_call")
            return [{"type": "function_call_output", "call_id": tool_id, "output": self._command_execution_tool_result(item)}]
        return [item]


class ChatCompletionsTransport(ProviderTransport):
    def endpoint_path(self) -> str:
        return "/chat/completions"

    def wire_api(self) -> str:
        return "chat"

    def describe(self) -> str:
        return "chat_completions"

    def supports_passthrough_stream(self) -> bool:
        return False

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = self.apply_reasoning_config(payload)
        tools = self.convert_tools(payload.get("tools"))
        messages = self.convert_messages(payload)
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

    def normalize_response(self, raw: Any, original_payload: dict[str, Any]) -> NormalizedResponse:
        choice = ((raw.get("choices") or [{}])[0]) if isinstance(raw.get("choices"), list) else {}
        message = dict(choice.get("message") or {})
        reasoning_content = str(message.get("reasoning_content") or "")
        text = self._visible_text_or_reasoning_only_notice(str(message.get("content") or ""), reasoning_content, bool(message.get("tool_calls")))
        warnings: list[ProviderWarning] = []
        repaired_calls, repair_warnings = normalize_tool_calls(
            list(message.get("tool_calls") or []),
            allow_parallel=bool(self.profile.get("supports_parallel_tool_calls", False)),
        )
        warnings.extend(self._warning("tool_call_repair", warning, "warning") for warning in repair_warnings)
        tool_calls = [
            ToolCall(
                id=str(call.get("id") or "call_router"),
                name=str((call.get("function") or {}).get("name") or "tool"),
                arguments_json=str((call.get("function") or {}).get("arguments") or "{}"),
                provider_data={},
            )
            for call in repaired_calls
        ]
        usage = dict(raw.get("usage") or {})
        normalized_usage = None
        if usage:
            token_details = dict(usage.get("completion_tokens_details") or {})
            normalized_usage = Usage(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                reasoning_tokens=token_details.get("reasoning_tokens", usage.get("reasoning_tokens")),
                total_tokens=usage.get("total_tokens"),
            )
        if reasoning_content and not str(message.get("content") or "").strip() and not tool_calls:
            warnings.append(self._warning("reasoning_only_notice_emitted", "Visible text was synthesized because the provider returned reasoning without assistant text.", "info"))
        return NormalizedResponse(
            text=text,
            reasoning_summary=reasoning_content or None,
            reasoning_state=self._reasoning_state(
                reasoning_content or None,
                model_id=self._model_id(original_payload),
                replayable=False,
                opaque_artifacts=[{"field": "reasoning_content", "chars": len(reasoning_content)}] if reasoning_content else [],
            ),
            tool_calls=tool_calls,
            usage=normalized_usage,
            finish_reason=str(choice.get("finish_reason") or "stop"),
            provider_data={
                "model": self._model_id(original_payload),
                "response_id": raw.get("id"),
                "choice_count": len(list(raw.get("choices") or [])),
                "tool_call_count": len(tool_calls),
            },
            warnings=warnings,
            raw_ref=self._raw_ref(kind="chat_completion_choice", locator=raw.get("id"), summary="First choice normalized from chat completions."),
        )

    def convert_messages(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
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

    def convert_tools(self, tools: Any) -> list[dict[str, Any]]:
        converted, _warnings = sanitize_tool_definitions(tools)
        return converted

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

    def _visible_text_or_reasoning_only_notice(self, text: str, reasoning_content: str, has_tool_calls: bool) -> str:
        if text or not reasoning_content or has_tool_calls:
            return text
        return "(Provider returned reasoning content but no final assistant message. Open the reasoning preview or retry with an explicit final-answer instruction.)"

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
                return [{"role": "assistant", "content": f"{self._flatten_content(item.get('reasoning_content'))}\n{self._flatten_content(item.get('content'))}".strip()}]
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
                            "function": {"name": name, "arguments": self._safe_tool_arguments(item.get("arguments"))},
                        }
                    ],
                }
            ]
        if item_type == "message":
            role = self._map_role(str(item.get("role") or "user"))
            return [{"role": role, "content": self._chat_content(item.get("content"))}]
        if item_type in {"contextCompaction", "enteredReviewMode", "exitedReviewMode", "collabAgentToolCall"}:
            summary = self._transition_summary_message(item)
            return [{"role": "assistant", "content": summary}] if summary else []
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
                return [{"type": "text", "text": "[image attachment omitted: provider requires a base64 data URL]"}]
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
        except Exception as exc:  # noqa: BLE001
            return {"type": "text", "text": f"[image attachment unavailable: {str(exc)[:160]}]"}

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
            summarized_output, _warnings = summarize_tool_output(output, char_limit=self._tool_output_char_limit())
            parts.append(f"output:\n{summarized_output}")
        return "\n".join(parts) or "Command completed with no captured output."

    def _repair_tool_message_sequence(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        repaired, _warnings = enforce_tool_message_sequence(messages)
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

    def _sanitize_chat_tool_calls(self, value: Any) -> list[dict[str, Any]]:
        calls, _warnings = normalize_tool_calls(
            value,
            allow_parallel=bool(self.profile.get("supports_parallel_tool_calls", False)),
        )
        return calls

    def _safe_tool_arguments(self, value: Any) -> str:
        calls, _warnings = normalize_tool_calls(
            [{"name": "tool", "arguments": value}],
            allow_parallel=True,
        )
        if not calls:
            return "{}"
        return str((calls[0].get("function") or {}).get("arguments") or "{}")

    def _transition_summary_message(self, item: dict[str, Any]) -> str:
        item_type = str(item.get("type") or "")
        if item_type == "contextCompaction":
            return "[context compaction]\nThread context was compacted before this turn. Continue from the surviving summary, tool results, and recent file state."
        if item_type == "enteredReviewMode":
            review = str(item.get("review") or "").strip()
            return f"[review mode entered]\n{review}".strip()
        if item_type == "exitedReviewMode":
            review = str(item.get("review") or "").strip()
            return f"[review mode exited]\n{review}".strip()
        if item_type != "collabAgentToolCall":
            return ""
        tool = str(item.get("tool") or "").strip()
        receivers = [str(value).strip() for value in list(item.get("receiverThreadIds") or []) if str(value).strip()]
        prompt = str(item.get("prompt") or "").strip()
        model = str(item.get("model") or "").strip()
        effort = str(item.get("reasoningEffort") or "").strip()
        states = item.get("agentsStates") or {}
        lines: list[str] = []
        if tool == "spawnAgent":
            lines.append("[forked collaborator thread]")
            if receivers:
                lines.append(f"Spawned collaborator thread(s): {', '.join(receivers)}")
            else:
                lines.append("Spawned a collaborator thread.")
        elif tool == "sendInput":
            lines.append("[collaborator follow-up]")
            if receivers:
                lines.append(f"Sent follow-up input to: {', '.join(receivers)}")
        elif tool == "resumeAgent":
            lines.append("[collaborator resumed]")
            if receivers:
                lines.append(f"Resumed collaborator thread(s): {', '.join(receivers)}")
        elif tool == "wait":
            lines.append("[collaborator wait]")
            lines.append("Waiting for collaborator progress.")
        elif tool == "closeAgent":
            lines.append("[collaborator closed]")
            if receivers:
                lines.append(f"Closed collaborator thread(s): {', '.join(receivers)}")
        else:
            lines.append("[collaborator transition]")
            lines.append(f"Recorded collaborator tool event: {tool or 'unknown'}")
        if model:
            lines.append(f"Model: {model}")
        if effort:
            lines.append(f"Reasoning effort: {effort}")
        if prompt:
            lines.append(f"Prompt summary: {prompt[:240]}")
        if isinstance(states, dict) and states:
            lines.append(f"Known collaborator states: {', '.join(sorted(states.keys()))}")
        return "\n".join(lines).strip()

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


@lru_cache(maxsize=None)
def transport_signature_for_class(transport_class: type[ProviderTransport]) -> str:
    digest = hashlib.sha256()
    digest.update(str(transport_class.__module__).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(transport_class.__qualname__).encode("utf-8"))
    digest.update(b"\0")
    for source_file in _transport_source_files(transport_class):
        digest.update(source_file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


@lru_cache(maxsize=None)
def _transport_source_files(transport_class: type[ProviderTransport]) -> tuple[Path, ...]:
    files: list[Path] = []
    for candidate in (inspect.getsourcefile(transport_class), inspect.getsourcefile(ProviderTransport)):
        if not candidate:
            continue
        path = Path(candidate).resolve()
        if path not in files and path.is_file():
            files.append(path)
    return tuple(files)
