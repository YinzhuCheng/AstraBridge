from __future__ import annotations

from typing import Any

from .base import ChatCompletionsTransport


class GlmChatTransport(ChatCompletionsTransport):
    def describe(self) -> str:
        return "glm_chat"

    def reasoning_control_semantics(self) -> str:
        return "reasoning_effort"

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().build_request(payload)
        effort = self._resolved_reasoning_effort(payload)
        if effort == "off":
            upstream_payload["reasoning_effort"] = "none"
        elif effort in {"minimal", "low", "medium", "high"}:
            upstream_payload["reasoning_effort"] = "high"
        elif effort in {"xhigh", "auto"}:
            if effort == "xhigh":
                upstream_payload["reasoning_effort"] = "max"
            else:
                upstream_payload.pop("reasoning_effort", None)
        elif effort:
            upstream_payload["reasoning_effort"] = "max"
        return upstream_payload
