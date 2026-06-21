from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from ..model_catalog import known_context_window
from .registry import get_provider_profile


@dataclass
class TransitionSummary:
    from_provider: str | None
    to_provider: str
    projection_mode: str
    dropped_artifacts: int
    repaired_tool_pairs: int
    kept_summary: bool
    warnings: list[str]
    context_budget: int | None
    selected_edit_policy: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize_transition(
    *,
    from_provider: str | None,
    to_provider: str,
    to_model: str | None,
    dropped_artifacts: int = 0,
    repaired_tool_pairs: int = 0,
    warnings: list[str] | None = None,
    projection_mode: str = "task_context_fresh_thread",
) -> TransitionSummary:
    profile = get_provider_profile(to_provider)
    target_model = str(to_model or profile.default_model or "").strip()
    context_budget = known_context_window(profile.id, target_model)
    extra_warnings = list(warnings or [])
    if from_provider and from_provider != to_provider:
        extra_warnings.append("Cross-provider handoff uses AstraBridge task context instead of raw provider-state replay.")
    return TransitionSummary(
        from_provider=from_provider,
        to_provider=profile.id,
        projection_mode=projection_mode,
        dropped_artifacts=dropped_artifacts,
        repaired_tool_pairs=repaired_tool_pairs,
        kept_summary=True,
        warnings=list(dict.fromkeys(extra_warnings)),
        context_budget=context_budget,
        selected_edit_policy={
            "small": profile.edit_policy.small,
            "medium": profile.edit_policy.medium,
            "large": profile.edit_policy.large,
        },
    )
