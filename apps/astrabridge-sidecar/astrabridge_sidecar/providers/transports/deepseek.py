from __future__ import annotations

from .base import ChatCompletionsTransport


DEEPSEEK_MAX_EFFORTS = {"xhigh", "max"}


class DeepSeekChatTransport(ChatCompletionsTransport):
    def describe(self) -> str:
        return "deepseek_chat"

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().build_request(payload)
        merged_messages = self._merge_reasoning_content_into_assistant_messages(list(upstream_payload.get("messages") or []))
        upstream_payload["messages"] = self._repair_tool_message_sequence(merged_messages)
        effort = self._resolved_reasoning_effort(payload)
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
