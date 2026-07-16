from __future__ import annotations

from typing import Any


CODEX_REASONING_EFFORTS = ("off", "auto", "minimal", "low", "medium", "high", "xhigh")
_CODEX_REASONING_EFFORT_SET = set(CODEX_REASONING_EFFORTS)
REASONING_EFFORT_ALIASES = {
    "none": "off",
    "max": "xhigh",
}
VISIBLE_SUMMARY_REASONING_MODES = {
    "reasoning_effort",
    "enable_thinking",
    "reasoning_content",
    "openai_responses",
}


def normalize_reasoning_effort(value: Any, *, default: str | None = None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    normalized = REASONING_EFFORT_ALIASES.get(normalized, normalized)
    if normalized in _CODEX_REASONING_EFFORT_SET:
        return normalized
    return default


def normalize_reasoning_efforts(values: Any, *, default: str = "high") -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    normalized: list[str] = []
    for item in items:
        effort = normalize_reasoning_effort(item)
        if effort and effort not in normalized:
            normalized.append(effort)
    return normalized or [default]


def resolve_reasoning_state_visibility(
    reasoning_policy_mode: Any,
    *,
    supports_reasoning_replay: Any = False,
) -> str:
    if bool(supports_reasoning_replay):
        return "replayable"
    mode = str(reasoning_policy_mode or "").strip().lower()
    if mode in VISIBLE_SUMMARY_REASONING_MODES:
        return "visible_summary_only"
    return "provider_private"
