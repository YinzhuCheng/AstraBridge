from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .registry import get_provider_profile


DEFAULT_PROVIDER_REQUEST_TIMEOUT_SECONDS = 45.0


@dataclass(frozen=True)
class RuntimeTransitionTarget:
    provider_id: str
    model_id: str
    protocol: str
    runtime_backend: str
    base_url: str
    env_key: str
    context_budget: int | None
    request_timeout_seconds: float
    reasoning_policy_mode: str
    default_reasoning_level: str
    supported_reasoning_levels: tuple[str, ...]
    temperature_adapter_policy: str
    fallback_models: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["supported_reasoning_levels"] = list(self.supported_reasoning_levels)
        payload["fallback_models"] = list(self.fallback_models)
        return payload


@dataclass(frozen=True)
class RuntimeTransitionPlan:
    action: str
    reason: str
    target: RuntimeTransitionTarget | None = None
    reasoning_effort: str | None = None
    context_strategy: str = "default"
    restart_runtime: bool = False
    compact_before_send: bool = False
    drop_reasoning_replay: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "target": self.target.to_dict() if self.target else None,
            "reasoning_effort": self.reasoning_effort,
            "context_strategy": self.context_strategy,
            "restart_runtime": self.restart_runtime,
            "compact_before_send": self.compact_before_send,
            "drop_reasoning_replay": self.drop_reasoning_replay,
            "notes": list(self.notes),
        }


@dataclass
class TransitionSummary:
    from_provider: str | None
    to_provider: str
    to_model: str
    projection_mode: str
    dropped_artifacts: int
    repaired_tool_pairs: int
    replayable_artifact_count: int
    projection_preview: str | None
    kept_summary: bool
    warnings: list[str]
    context_budget: int | None
    context_budget_report: dict[str, Any] | None
    selected_edit_policy: dict[str, str]
    target_runtime: dict[str, Any]
    transition_plan: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_transition_target(
    *,
    provider_id: str,
    model_id: str | None = None,
    request_timeout_seconds: float = DEFAULT_PROVIDER_REQUEST_TIMEOUT_SECONDS,
) -> RuntimeTransitionTarget:
    from ..model_catalog.catalog import fallback_model_ids, preferred_provider_model_record

    profile = get_provider_profile(provider_id)
    preferred_model = preferred_provider_model_record(profile.id, include_deprecated=False)
    target_model = str(
        model_id
        or (preferred_model or {}).get("native_model")
        or profile.default_model
        or ""
    ).strip()
    protocol = "responses" if profile.protocol in {"responses", "qwen_responses"} else "chat"
    env_key = profile.auth.env_vars[0] if profile.auth.env_vars else "OPENAI_API_KEY"
    context_budget = int((preferred_model or {}).get("advertised_context_window") or profile.context_window() or 0) or None
    fallback_models = fallback_model_ids(profile.id, target_model, include_deprecated=False)
    supported_reasoning_levels = tuple(
        str(item).strip().lower()
        for item in list((preferred_model or {}).get("supported_reasoning_levels") or profile.reasoning_levels())
        if str(item).strip()
    ) or profile.reasoning_levels()
    default_reasoning_level = str((preferred_model or {}).get("default_reasoning_level") or profile.default_reasoning_level()).strip().lower()
    return RuntimeTransitionTarget(
        provider_id=profile.id,
        model_id=target_model,
        protocol=protocol,
        runtime_backend=profile.runtime_backend,
        base_url=profile.base_url,
        env_key=env_key,
        context_budget=context_budget,
        request_timeout_seconds=request_timeout_seconds,
        reasoning_policy_mode=profile.reasoning_policy.mode,
        default_reasoning_level=default_reasoning_level,
        supported_reasoning_levels=supported_reasoning_levels,
        temperature_adapter_policy=profile.safety_policy.temperature_adapter_policy,
        fallback_models=fallback_models,
    )


def build_transition_plan(
    *,
    action: str,
    reason: str,
    provider_id: str | None = None,
    model_id: str | None = None,
    reasoning_effort: str | None = None,
    request_timeout_seconds: float = DEFAULT_PROVIDER_REQUEST_TIMEOUT_SECONDS,
    context_strategy: str = "default",
    restart_runtime: bool = False,
    compact_before_send: bool = False,
    drop_reasoning_replay: bool = False,
    notes: list[str] | tuple[str, ...] | None = None,
) -> RuntimeTransitionPlan:
    target = None
    if provider_id:
        target = build_transition_target(
            provider_id=provider_id,
            model_id=model_id,
            request_timeout_seconds=request_timeout_seconds,
        )
    return RuntimeTransitionPlan(
        action=action,
        reason=reason,
        target=target,
        reasoning_effort=str(reasoning_effort or "").strip() or None,
        context_strategy=context_strategy,
        restart_runtime=restart_runtime,
        compact_before_send=compact_before_send,
        drop_reasoning_replay=drop_reasoning_replay,
        notes=tuple(str(item).strip() for item in (notes or ()) if str(item).strip()),
    )


def summarize_transition(
    *,
    from_provider: str | None,
    to_provider: str,
    to_model: str | None,
    dropped_artifacts: int = 0,
    repaired_tool_pairs: int = 0,
    replayable_artifact_count: int = 0,
    projection_preview: str | None = None,
    warnings: list[str] | None = None,
    projection_mode: str = "task_context_fresh_thread",
    reasoning_effort: str | None = None,
    request_timeout_seconds: float = DEFAULT_PROVIDER_REQUEST_TIMEOUT_SECONDS,
    context_budget_report: dict[str, Any] | None = None,
) -> TransitionSummary:
    profile = get_provider_profile(to_provider)
    target_model = str(to_model or profile.default_model or "").strip()
    target_runtime = build_transition_target(
        provider_id=profile.id,
        model_id=target_model,
        request_timeout_seconds=request_timeout_seconds,
    )
    extra_warnings = list(warnings or [])
    cross_provider = bool(from_provider and from_provider != to_provider)
    if cross_provider:
        extra_warnings.append("Cross-provider handoff uses AstraBridge task context instead of raw provider-state replay.")
    compact_before_send = bool((context_budget_report or {}).get("compact_recommended"))
    if compact_before_send:
        extra_warnings.append("Target model context budget is tight; compacted project context should be preferred before the next long turn.")
    preflight_admission = str((context_budget_report or {}).get("preflight_admission") or "")
    usable_context_status = str((context_budget_report or {}).get("usable_coding_context_status") or "")
    if preflight_admission in {"blocked", "downgrade_required"}:
        extra_warnings.append(
            "Target route has no safe endpoint-aware context budget yet; AstraBridge must reduce context or choose another route before a long turn."
        )
    elif usable_context_status == "conservative_estimate":
        extra_warnings.append(
            "Target context capacity is an advertised/conservative estimate, not verified usable coding context."
        )
    transition_plan = build_transition_plan(
        action="provider_handoff",
        reason="Continue the same visible task on a provider-isolated execution lane.",
        provider_id=profile.id,
        model_id=target_model,
        reasoning_effort=reasoning_effort or profile.default_reasoning_level(),
        request_timeout_seconds=request_timeout_seconds,
        context_strategy=projection_mode,
        compact_before_send=compact_before_send,
        drop_reasoning_replay=cross_provider,
        notes=extra_warnings,
    )
    return TransitionSummary(
        from_provider=from_provider,
        to_provider=profile.id,
        to_model=target_model,
        projection_mode=projection_mode,
        dropped_artifacts=dropped_artifacts,
        repaired_tool_pairs=repaired_tool_pairs,
        replayable_artifact_count=replayable_artifact_count,
        projection_preview=str(projection_preview or "").strip() or None,
        kept_summary=True,
        warnings=list(dict.fromkeys(extra_warnings)),
        context_budget=target_runtime.context_budget,
        context_budget_report=dict(context_budget_report or {}) or None,
        selected_edit_policy={
            "small": profile.edit_policy.small,
            "medium": profile.edit_policy.medium,
            "large": profile.edit_policy.large,
        },
        target_runtime=target_runtime.to_dict(),
        transition_plan=transition_plan.to_dict(),
    )
