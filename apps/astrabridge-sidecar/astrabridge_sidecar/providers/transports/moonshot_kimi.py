from __future__ import annotations

from typing import Any

from .base import ChatCompletionsTransport


KIMI_KEEP_ALL_EFFORTS = {"xhigh", "max"}
KIMI_THINKING_OUTPUT_FLOOR = 32768
KIMI_K3_REASONING_EFFORT_MAP = {
    "minimal": "low",
    "low": "low",
    "medium": "high",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}


class KimiChatTransport(ChatCompletionsTransport):
    def describe(self) -> str:
        return "kimi_chat"

    def reasoning_control_semantics(self) -> str:
        return "kimi_k3_reasoning_effort_or_chat_thinking"

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
        if native_model == "kimi-k3":
            return self._build_k3_request(upstream_payload, effort)
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

    def _build_k3_request(self, upstream_payload: dict[str, Any], effort: str | None) -> dict[str, Any]:
        if effort == "off":
            raise ValueError("kimi-k3 is always-thinking and does not support reasoning effort 'off'; use low, high, or xhigh.")
        upstream_payload.pop("thinking", None)
        native_effort = KIMI_K3_REASONING_EFFORT_MAP.get(str(effort or "").strip().lower())
        if native_effort:
            upstream_payload["reasoning_effort"] = native_effort
        else:
            upstream_payload.pop("reasoning_effort", None)
        for fixed_parameter in ("temperature", "top_p", "n", "presence_penalty", "frequency_penalty"):
            upstream_payload.pop(fixed_parameter, None)
        if "max_tokens" in upstream_payload:
            upstream_payload["max_completion_tokens"] = upstream_payload.pop("max_tokens")
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
