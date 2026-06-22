from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


CONTEXT_BUDGET_SCHEMA_VERSION = "astrabridge-context-budget-v1"


@dataclass(frozen=True)
class ContextSection:
    section_id: str
    label: str
    priority: int
    text: str
    essential: bool = False


@dataclass(frozen=True)
class ContextSectionEstimate:
    section_id: str
    label: str
    priority: int
    chars: int
    estimated_tokens: int
    essential: bool
    included: bool
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextBudgetReport:
    provider_id: str | None
    model_id: str | None
    context_window: int | None
    effective_context_window_percent: int
    effective_context_budget_tokens: int | None
    auto_compact_token_limit: int | None
    tool_schema_token_estimate: int
    usable_prompt_budget_tokens: int | None
    full_text_tokens: int
    selected_text_tokens: int
    selected_text_chars: int
    compact_recommended: bool
    dropped_section_ids: tuple[str, ...]
    section_estimates: tuple[ContextSectionEstimate, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = CONTEXT_BUDGET_SCHEMA_VERSION
        payload["section_estimates"] = [item.to_dict() for item in self.section_estimates]
        payload["dropped_section_ids"] = list(self.dropped_section_ids)
        return payload


def estimate_text_tokens(text: str) -> int:
    raw = str(text or "")
    if not raw:
        return 0
    return max(1, (len(raw) + 3) // 4)


def estimate_tool_schema_tokens(model: dict[str, Any]) -> int:
    estimate = 240
    if model.get("apply_patch_tool_type"):
        estimate += 550
    if model.get("supports_search_tool"):
        estimate += 320
    if model.get("supports_mcp_tools"):
        estimate += 1_100
    if model.get("supports_parallel_tool_calls"):
        estimate += 180
    if model.get("experimental_supported_tools"):
        estimate += min(600, 80 * len(list(model.get("experimental_supported_tools") or [])))
    return estimate


def build_context_budget(
    *,
    sections: list[ContextSection],
    provider_id: str | None,
    model_id: str | None,
    context_window: int | None,
    effective_context_window_percent: int = 80,
    auto_compact_token_limit: int | None = None,
    tool_schema_token_estimate: int = 0,
) -> tuple[str, ContextBudgetReport]:
    ordered = sorted(sections, key=lambda item: (item.priority, item.section_id))
    effective_budget = None
    if context_window:
        effective_budget = int(int(context_window) * (int(effective_context_window_percent or 80) / 100))
    usable_budget = effective_budget
    if auto_compact_token_limit:
        usable_budget = min(int(auto_compact_token_limit), usable_budget or int(auto_compact_token_limit))
    if usable_budget is not None:
        usable_budget = max(256, int(usable_budget) - int(tool_schema_token_estimate or 0))

    rendered_parts: list[str] = []
    selected_tokens = 0
    selected_chars = 0
    dropped: list[str] = []
    estimates: list[ContextSectionEstimate] = []

    for section in ordered:
        text = str(section.text or "").strip()
        chars = len(text)
        tokens = estimate_text_tokens(text)
        included = False
        truncated = False
        rendered = text
        remaining = None if usable_budget is None else max(0, usable_budget - selected_tokens)

        if not text:
            estimates.append(
                ContextSectionEstimate(
                    section_id=section.section_id,
                    label=section.label,
                    priority=section.priority,
                    chars=0,
                    estimated_tokens=0,
                    essential=section.essential,
                    included=False,
                    truncated=False,
                )
            )
            continue

        if remaining is None or tokens <= remaining:
            included = True
        elif section.essential and remaining and remaining >= 24:
            truncated = True
            rendered = clip_text_to_tokens(text, remaining)
            tokens = estimate_text_tokens(rendered)
            chars = len(rendered)
            included = True
        else:
            dropped.append(section.section_id)

        if included:
            rendered_parts.append(rendered)
            selected_tokens += tokens
            selected_chars += chars
        estimates.append(
            ContextSectionEstimate(
                section_id=section.section_id,
                label=section.label,
                priority=section.priority,
                chars=chars,
                estimated_tokens=tokens,
                essential=section.essential,
                included=included,
                truncated=truncated,
            )
        )

    full_text = "\n\n".join(str(section.text or "").strip() for section in ordered if str(section.text or "").strip())
    compact_recommended = bool(dropped)
    if usable_budget is not None and estimate_text_tokens(full_text) > usable_budget:
        compact_recommended = True
    report = ContextBudgetReport(
        provider_id=provider_id,
        model_id=model_id,
        context_window=context_window,
        effective_context_window_percent=int(effective_context_window_percent or 80),
        effective_context_budget_tokens=effective_budget,
        auto_compact_token_limit=auto_compact_token_limit,
        tool_schema_token_estimate=int(tool_schema_token_estimate or 0),
        usable_prompt_budget_tokens=usable_budget,
        full_text_tokens=estimate_text_tokens(full_text),
        selected_text_tokens=selected_tokens,
        selected_text_chars=selected_chars,
        compact_recommended=compact_recommended,
        dropped_section_ids=tuple(dropped),
        section_estimates=tuple(estimates),
    )
    return "\n\n".join(rendered_parts), report


def clip_text_to_tokens(text: str, token_limit: int) -> str:
    if token_limit <= 0:
        return ""
    approx_chars = max(32, int(token_limit) * 4)
    raw = str(text or "")
    if len(raw) <= approx_chars:
        return raw
    clipped = raw[: max(0, approx_chars - 14)].rstrip()
    return clipped + "\n[truncated]"
