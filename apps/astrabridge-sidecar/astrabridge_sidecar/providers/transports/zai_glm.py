from __future__ import annotations

from typing import Any

from .base import ChatCompletionsTransport


class GlmChatTransport(ChatCompletionsTransport):
    def describe(self) -> str:
        return "glm_chat"

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().build_request(payload)
        effort = self._requested_effort(payload)
        if effort and effort not in {"auto", "off"}:
            upstream_payload["reasoning_effort"] = effort
        elif effort == "off":
            upstream_payload["reasoning_effort"] = "none"
        return upstream_payload

    def _requested_effort(self, payload: dict[str, Any]) -> str | None:
        reasoning = payload.get("reasoning")
        if isinstance(reasoning, dict):
            effort = str(reasoning.get("effort") or "").strip().lower()
            if effort:
                return effort
        effort = str(self.profile.get("reasoning_effort") or "").strip().lower()
        return effort or None
