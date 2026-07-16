from __future__ import annotations

from typing import Any

from .base import ChatCompletionsTransport


KIMI_KEEP_ALL_EFFORTS = {"xhigh", "max"}
KIMI_THINKING_OUTPUT_FLOOR = 32768


class KimiChatTransport(ChatCompletionsTransport):
    def describe(self) -> str:
        return "kimi_chat"

    def supports_local_image_input(self) -> bool:
        return True

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().build_request(payload)
        merged_messages = self._merge_reasoning_content_into_assistant_messages(list(upstream_payload.get("messages") or []))
        upstream_payload["messages"] = self._repair_tool_message_sequence(merged_messages)
        effort = self._resolved_reasoning_effort(payload)
        explicit_effort = self._explicit_reasoning_effort(payload)
        model_id = str(payload.get("model") or self.profile.get("model") or "").strip()
        native_model = model_id.split("/", 1)[1] if "/" in model_id else model_id
        has_local_image = self._has_local_image_input(payload)
        if effort == "off" and native_model in {"kimi-k2.7-code", "kimi-k2.7-code-highspeed"}:
            raise ValueError(f"{native_model} does not support reasoning effort 'off'; use low, medium, high, or xhigh.")
        if effort == "off":
            upstream_payload["thinking"] = {"type": "disabled"}
        elif has_local_image and explicit_effort not in KIMI_KEEP_ALL_EFFORTS:
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
