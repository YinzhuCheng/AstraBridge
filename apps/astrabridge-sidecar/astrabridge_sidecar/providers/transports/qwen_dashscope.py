from __future__ import annotations

from typing import Any

from .base import ResponsesTransport


QWEN_THINKING_ENABLED_EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max"}


class QwenResponsesTransport(ResponsesTransport):
    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().build_request(payload)
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
