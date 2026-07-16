from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from .profile import ProviderProfile
from .registry import get_provider_profile
from .runtime_transition import build_transition_plan


FailureCategory = Literal[
    "unknown",
    "provider_timeout",
    "rate_limit",
    "billing",
    "provider_5xx",
    "context_window_limit",
    "auth_failure",
    "unsupported_model",
    "unsupported_feature",
    "invalid_request_shape",
    "semantic_no_output",
    "artifact_issue",
    "provider_model_mismatch",
    "tool_mismatch",
    "permission_denied",
    "runtime_state_corruption",
    "provider_error",
    "transport_failure",
]


@dataclass(frozen=True)
class FailureRecommendation:
    action: str
    label: str
    reason: str
    target: str | None = None
    transition: dict[str, Any] | None = None


@dataclass(frozen=True)
class RuntimeFailureNotice:
    category: FailureCategory
    summary: str
    message: str
    actionable_hint: str
    provider: str = ""
    model: str = ""
    level: Literal["warning", "danger"] = "danger"
    retryable: bool = False
    compact_recommended: bool = False
    fork_recommended: bool = False
    recommended_actions: tuple[FailureRecommendation, ...] = ()
    fallback_models: tuple[str, ...] = ()
    reasoning_downgrade_levels: tuple[str, ...] = ()
    requires_key_check: bool = False
    provider_switch_recommended: bool = False
    recommended_action: str = "inspect_runtime_notice"
    recoverability: Literal["retryable", "recoverable", "requires_user_action", "fail_closed"] = "recoverable"

    def to_payload(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "category": self.category,
            "provider": self.provider,
            "model": self.model,
            "summary": self.summary[:240],
            "message": self.message[:500],
            "actionable_hint": self.actionable_hint[:240],
            "retryable": self.retryable,
            "compact_recommended": self.compact_recommended,
            "fork_recommended": self.fork_recommended,
            "fallback_models": list(self.fallback_models),
            "reasoning_downgrade_levels": list(self.reasoning_downgrade_levels),
            "requires_key_check": self.requires_key_check,
            "provider_switch_recommended": self.provider_switch_recommended,
            "recommended_action": self.recommended_action,
            "recoverability": self.recoverability,
            "recommended_actions": [
                {
                    "action": item.action,
                    "label": item.label,
                    "reason": item.reason,
                    "target": item.target,
                    "transition": item.transition,
                }
                for item in self.recommended_actions
            ],
        }


@dataclass(frozen=True)
class ParsedRuntimeError:
    message: str
    provider: str = ""
    model: str = ""
    parsed: dict[str, Any] = field(default_factory=dict)


def parse_runtime_error(raw_message: str, *, current_provider: str | None = None, current_model: str | None = None) -> ParsedRuntimeError:
    parsed: dict[str, Any] = {}
    message = str(raw_message or "")
    try:
        value = json.loads(message)
        if isinstance(value, dict):
            parsed = value.get("error") if isinstance(value.get("error"), dict) else value
            message = str(parsed.get("message") or message)
    except Exception:
        parsed = {}
    provider = str(parsed.get("provider") or current_provider or "").strip().lower()
    model = str(parsed.get("model") or current_model or "").strip()
    return ParsedRuntimeError(message=message, provider=provider, model=model, parsed=parsed)


def classify_runtime_failure(
    raw_message: str,
    *,
    current_provider: str | None = None,
    current_model: str | None = None,
) -> RuntimeFailureNotice:
    parsed = parse_runtime_error(raw_message, current_provider=current_provider, current_model=current_model)
    lowered = parsed.message.lower()
    profile = _provider_profile(parsed.provider)
    fallback_models = _fallback_models(parsed.provider, parsed.model)
    downgrade_levels = _downgrade_reasoning_levels(profile)

    if any(
        token in lowered
        for token in [
            "provider/model mismatch",
            "provider model mismatch",
            "resolved candidate mismatch",
            "provider-backed result came from",
            "executed against the wrong provider",
        ]
    ):
        return _notice(
            category="provider_model_mismatch",
            summary="The provider-backed result came from a different provider/model than the requested lane.",
            message=parsed.message,
            actionable_hint="Fail closed for this lane, mark the capability unverified, and inspect capability routing before retrying.",
            provider=parsed.provider,
            model=parsed.model,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="inspect_capability_route",
            recoverability="fail_closed",
            recommended_actions=_recommendations(
                _action("inspect_capability_route", "Inspect Route", "Review capability routing and adapter selection before retrying."),
                _action("mark_capability_unverified", "Mark Unverified", "Do not treat this capability lane as verified until the route mismatch is fixed."),
                _action("handoff_provider", "Switch Provider", "Use another verified provider lane while the routing mismatch remains unresolved."),
            ),
        )
    if any(
        token in lowered
        for token in [
            "image width and height greater than",
            "greater than 10px",
            "public https image urls or inline data:image payloads",
            "inline/base64 image inputs or local file paths",
            "audio-only message content",
            "audio parts only",
            "invalid request shape",
            "400 client error: bad request",
            "invalid request",
            "unprocessable entity",
            "invalid image",
            "invalid file format",
        ]
    ):
        return _notice(
            category="invalid_request_shape",
            summary="The request shape is incompatible with the selected provider/model lane.",
            message=parsed.message,
            actionable_hint="Treat this as a local validation or request-construction issue, adjust the payload shape, and retry with a safer request.",
            provider=parsed.provider,
            model=parsed.model,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="retry_safer_request_shape",
            recoverability="recoverable",
            recommended_actions=_recommendations(
                _action("inspect_request_shape", "Inspect Request", "Review request payload fields, modality parts, and provider-specific constraints."),
                _action("retry_safer_request_shape", "Retry Safer Request", "Retry with a smaller or provider-safe request shape."),
                _fallback_model_action(parsed.provider, fallback_models, "Switch to a fallback model only if the request shape is already valid for the target lane."),
            ),
        )
    if any(
        token in lowered
        for token in [
            "semantic output is empty",
            "returned no visible text",
            "returned no visible final answer",
            "returned no visible answer",
            "no usable visible answer",
        ]
    ):
        return _notice(
            category="semantic_no_output",
            summary="The provider route completed but did not produce a usable visible answer.",
            message=parsed.message,
            actionable_hint="Mark the capability unverified, retry with a simpler fixture or safer prompt shape, and fall back to another lane if semantics stay empty.",
            provider=parsed.provider,
            model=parsed.model,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            provider_switch_recommended=True,
            recommended_action="mark_capability_unverified",
            recoverability="recoverable",
            recommended_actions=_recommendations(
                _action("mark_capability_unverified", "Mark Unverified", "Keep the capability lane in a partial or unverified state until semantic output is reliable."),
                _action("retry_safer_request_shape", "Retry Simpler Fixture", "Retry with a simpler prompt or fixture to separate transport success from semantic success."),
                _fallback_model_action(parsed.provider, fallback_models, "Try another model in the same provider family if the semantic empty-output issue appears model-specific."),
            ),
        )
    if any(
        token in lowered
        for token in [
            "no persisted local image artifact",
            "returned no audio artifact",
            "artifact missing",
            "failed to persist",
            "artifact persistence",
        ]
    ):
        return _notice(
            category="artifact_issue",
            summary="The provider route completed but the required artifact was not persisted correctly.",
            message=parsed.message,
            actionable_hint="Treat the capability as unverified until artifact persistence is repaired and rerun.",
            provider=parsed.provider,
            model=parsed.model,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="inspect_artifact_persistence",
            recoverability="recoverable",
            recommended_actions=_recommendations(
                _action("inspect_artifact_persistence", "Inspect Artifacts", "Check artifact persisters, manifests, and output-path wiring."),
                _action("mark_capability_unverified", "Mark Unverified", "Do not promote the capability until output artifacts are durable and locally visible."),
                _retry_same_lane_action(parsed.provider, parsed.model),
            ),
        )
    if "winerror 10060" in lowered or "timed out" in lowered or "timeout" in lowered:
        return _notice(
            category="provider_timeout",
            summary="Provider network timeout. The upstream model endpoint did not respond before the socket timeout.",
            message=parsed.message,
            actionable_hint="Retry the turn, switch provider, or check network/provider status before continuing.",
            provider=parsed.provider,
            model=parsed.model,
            retryable=True,
            fork_recommended=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            provider_switch_recommended=True,
            recommended_action="retry_same_lane",
            recoverability="retryable",
            recommended_actions=_recommendations(
                _retry_same_lane_action(parsed.provider, parsed.model),
                _fallback_model_action(parsed.provider, fallback_models, "Try a fallback model in the same provider lane."),
                _action("handoff_provider", "Switch Provider", "Move the task to another provider lane if the timeout repeats."),
            ),
        )
    if any(token in lowered for token in ["429", "rate limit", "too many requests"]):
        return _notice(
            category="rate_limit",
            summary="Provider rate limit blocked the turn.",
            message=parsed.message,
            actionable_hint="Retry later, downgrade to a lighter model, or move the task to another provider lane.",
            provider=parsed.provider,
            model=parsed.model,
            retryable=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            provider_switch_recommended=True,
            recommended_action="switch_model",
            recoverability="retryable",
            recommended_actions=_recommendations(
                _fallback_model_action(parsed.provider, fallback_models, "Try a lighter fallback model to reduce rate pressure."),
                _action("retry_same_lane", "Retry Later", "Retry the lane after provider rate limits cool down."),
                _action("handoff_provider", "Switch Provider", "Move to another provider lane if rate pressure continues."),
            ),
        )
    if any(token in lowered for token in ["insufficient quota", "quota exceeded", "billing", "payment required"]):
        return _notice(
            category="billing",
            summary="Provider billing or quota blocked the turn.",
            message=parsed.message,
            actionable_hint="Restore provider quota, switch credentials, or continue on another provider lane.",
            provider=parsed.provider,
            model=parsed.model,
            requires_key_check=True,
            provider_switch_recommended=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="handoff_provider",
            recoverability="requires_user_action",
            recommended_actions=_recommendations(
                _action("verify_secret_mapping", "Check Billing Key", "Confirm the selected credential has quota and billing enabled."),
                _action("handoff_provider", "Switch Provider", "Continue the task on another provider lane."),
            ),
        )
    if any(token in lowered for token in ["500", "502", "503", "504", "service unavailable", "bad gateway", "gateway timeout"]):
        return _notice(
            category="provider_5xx",
            summary="Provider returned a transient server-side failure.",
            message=parsed.message,
            actionable_hint="Retry the turn, try a fallback model, or move the task to another provider lane if the provider stays unstable.",
            provider=parsed.provider,
            model=parsed.model,
            retryable=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            provider_switch_recommended=True,
            recommended_action="retry_same_lane",
            recoverability="retryable",
            recommended_actions=_recommendations(
                _retry_same_lane_action(parsed.provider, parsed.model),
                _fallback_model_action(parsed.provider, fallback_models, "Try a fallback model if the server issue appears model-specific."),
                _action("handoff_provider", "Switch Provider", "Move to another provider lane while the provider is degraded."),
            ),
        )
    if any(token in lowered for token in ["context length exceeded", "maximum context length", "context window", "too many tokens"]):
        return _notice(
            category="context_window_limit",
            summary="The request exceeded the model context window.",
            message=parsed.message,
            actionable_hint="Compact the thread, fork a narrower follow-up, or retry with a smaller request.",
            provider=parsed.provider,
            model=parsed.model,
            compact_recommended=True,
            fork_recommended=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="compact_thread",
            recoverability="recoverable",
            recommended_actions=_recommendations(
                _compact_then_retry_action(parsed.provider, parsed.model),
                _action("fork_followup", "Fork Narrower", "Continue in a smaller follow-up thread."),
                _reasoning_downgrade_action(parsed.provider, parsed.model, downgrade_levels),
                _fallback_model_action(parsed.provider, fallback_models, "Switch to a smaller fallback model if available."),
            ),
        )
    if any(
        token in lowered
        for token in [
            "401",
            "unauthorized",
            "invalid api key",
            "incorrect api key",
            "authentication",
            "auth failed",
            "secret is not loaded for env key",
            "no managed key or environment value",
        ]
    ):
        return _notice(
            category="auth_failure",
            summary="Provider authentication failed.",
            message=parsed.message,
            actionable_hint="Check the selected provider key, vault entry, or environment mapping before retrying.",
            provider=parsed.provider,
            model=parsed.model,
            requires_key_check=True,
            provider_switch_recommended=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="refresh_provider_key",
            recoverability="requires_user_action",
            recommended_actions=_recommendations(
                _action("refresh_provider_key", "Reload Key", "Reload the provider key from vault or environment."),
                _action("verify_secret_mapping", "Check Secret Mapping", "Confirm the selected profile points at the intended secret."),
                _action("handoff_provider", "Switch Provider", "Use another provider lane until the key issue is fixed."),
            ),
        )
    if any(
        token in lowered
        for token in [
            "no_capability_candidate",
            "does not support model",
            "unsupported model",
            "model not found",
            "unknown model",
        ]
    ):
        return _notice(
            category="unsupported_model",
            summary="The selected model does not expose an eligible capability route for this request.",
            message=parsed.message,
            actionable_hint="Switch to a supported model or disable the unsupported capability lane for this request.",
            provider=parsed.provider,
            model=parsed.model,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            provider_switch_recommended=True,
            recommended_action="switch_model" if fallback_models else "disable_feature",
            recoverability="recoverable",
            recommended_actions=_recommendations(
                _fallback_model_action(parsed.provider, fallback_models, "Switch to an eligible model for this capability lane."),
                _action("disable_feature", "Disable Feature", "Retry without the unsupported capability lane."),
                _action("handoff_provider", "Switch Provider", "Move to another provider lane with verified support."),
            ),
        )
    if any(token in lowered for token in ["unsupported", "not supported", "does not support"]):
        return _notice(
            category="unsupported_feature",
            summary="The selected provider or model does not support this feature.",
            message=parsed.message,
            actionable_hint="Switch to a supported model, disable the unsupported feature, or try another provider lane.",
            provider=parsed.provider,
            model=parsed.model,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            provider_switch_recommended=True,
            recommended_action="switch_model" if fallback_models else "handoff_provider",
            recoverability="recoverable",
            recommended_actions=_recommendations(
                _fallback_model_action(parsed.provider, fallback_models, "Switch to a model that advertises the required capability."),
                _action("disable_feature", "Disable Feature", "Retry without the unsupported tool, modality, or reasoning mode."),
                _action("handoff_provider", "Switch Provider", "Move the task to a provider lane that supports the feature."),
            ),
        )
    if any(token in lowered for token in ["tool call", "tool result", "mcp", "function call"]) and any(
        token in lowered for token in ["missing", "invalid", "mismatch", "schema"]
    ):
        return _notice(
            category="tool_mismatch",
            summary="Tool-call state did not line up with the provider response.",
            message=parsed.message,
            actionable_hint="Retry the turn, inspect MCP/tool wiring, or fork a fresh thread if the history is stale.",
            provider=parsed.provider,
            model=parsed.model,
            retryable=True,
            fork_recommended=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="retry_same_lane",
            recoverability="retryable",
            recommended_actions=_recommendations(
                _retry_same_lane_action(parsed.provider, parsed.model),
                _action("inspect_tool_contract", "Inspect Tools", "Review tool schema, MCP registration, and tool result wiring."),
                _action("fork_followup", "Fork Fresh Lane", "Create a fresh continuation if prior tool history is stale."),
            ),
        )
    if any(token in lowered for token in ["permission denied", "access denied", "operation not permitted"]):
        return _notice(
            category="permission_denied",
            summary="Runtime or provider permissions blocked the operation.",
            message=parsed.message,
            actionable_hint="Raise approval, relax the execution mode, or choose a provider lane with sufficient authority.",
            provider=parsed.provider,
            model=parsed.model,
            provider_switch_recommended=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="ask_user_approval",
            recoverability="requires_user_action",
            recommended_actions=_recommendations(
                _action("ask_user_approval", "Request Approval", "Ask for approval before retrying the blocked action."),
                _action("handoff_provider", "Switch Provider", "Move the task to a provider lane with the required authority."),
            ),
        )
    if any(token in lowered for token in ["thread not found", "provider thread missing", "systemerror", "state corruption", "stale state"]):
        return _notice(
            category="runtime_state_corruption",
            summary="Runtime state became inconsistent with the current thread or provider session.",
            message=parsed.message,
            actionable_hint="Retry with provider handoff, reopen the thread, or fork a fresh continuation from the latest saved state.",
            provider=parsed.provider,
            model=parsed.model,
            fork_recommended=True,
            provider_switch_recommended=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="restart_runtime_lane",
            recoverability="recoverable",
            recommended_actions=_recommendations(
                _restart_runtime_action(parsed.provider, parsed.model),
                _action("fork_followup", "Fork Fresh Lane", "Continue from the latest saved state in a new lane."),
                _action("handoff_provider", "Switch Provider", "Move to another provider lane if this runtime stays inconsistent."),
            ),
        )
    if "provider_error" in lowered or parsed.parsed.get("type") == "provider_error":
        return _notice(
            category="provider_error",
            summary="Provider returned an error during the turn.",
            message=parsed.message,
            actionable_hint="Check provider auth, request shape, router state, or upstream connectivity.",
            provider=parsed.provider,
            model=parsed.model,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            recommended_action="inspect_request_shape",
            recoverability="recoverable",
            recommended_actions=_recommendations(
                _action("inspect_request_shape", "Inspect Request", "Review the request body and provider metadata for incompatibilities."),
                _fallback_model_action(parsed.provider, fallback_models, "Try a fallback model if the issue appears model-specific."),
                _action("handoff_provider", "Switch Provider", "Move to another provider lane if the error persists."),
            ),
        )
    if any(token in lowered for token in ["connection reset", "connection aborted", "name resolution", "dns", "refused", "temporarily unavailable"]):
        return _notice(
            category="transport_failure",
            summary="Network transport failed before the provider returned a usable response.",
            message=parsed.message,
            actionable_hint="Retry the turn or check local network, DNS, proxy, and provider endpoint reachability.",
            provider=parsed.provider,
            model=parsed.model,
            retryable=True,
            fallback_models=fallback_models,
            reasoning_downgrade_levels=downgrade_levels,
            provider_switch_recommended=True,
            recommended_action="retry_same_lane",
            recoverability="retryable",
            recommended_actions=_recommendations(
                _retry_same_lane_action(parsed.provider, parsed.model),
                _action("inspect_network", "Check Network", "Check local DNS, proxy, firewall, and provider reachability."),
                _action("handoff_provider", "Switch Provider", "Use another provider lane while transport remains unstable."),
            ),
        )
    return _notice(
        category="unknown",
        summary="Runtime failure did not match a known classified lane.",
        message=parsed.message,
        actionable_hint=str(parsed.parsed.get("actionable_hint") or "Inspect the runtime notice and retry with a narrower next step."),
        provider=parsed.provider,
        model=parsed.model,
        fallback_models=fallback_models,
        reasoning_downgrade_levels=downgrade_levels,
        recommended_action="inspect_runtime_notice",
        recoverability="recoverable",
        recommended_actions=_recommendations(
            _action("inspect_runtime_notice", "Inspect Notice", "Review the runtime notice and thread diagnostics before retrying."),
        ),
    )


def _provider_profile(provider_id: str) -> ProviderProfile | None:
    try:
        return get_provider_profile(provider_id) if provider_id else None
    except ValueError:
        return None


def _fallback_models(provider_id: str, current_model: str) -> tuple[str, ...]:
    if not provider_id:
        return ()
    profile = _provider_profile(provider_id)
    current_native_model = current_model.split("/", 1)[1] if "/" in current_model else current_model
    preferred = (profile.fallback_policy.fallback_models or profile.fallback_models) if profile is not None else ()
    seen: set[str] = set()
    models: list[str] = []
    for model in preferred:
        normalized = str(model or "").strip()
        if not normalized or normalized in {current_model, current_native_model} or normalized in seen:
            continue
        seen.add(normalized)
        models.append(normalized)
    if models:
        return tuple(models)
    from ..model_catalog.catalog import fallback_model_ids

    catalog_models = fallback_model_ids(provider_id, current_model, include_deprecated=False)
    if catalog_models:
        return catalog_models
    return tuple(models)


def _downgrade_reasoning_levels(profile: ProviderProfile | None) -> tuple[str, ...]:
    if profile is None:
        return ()
    seen: set[str] = set()
    levels: list[str] = []
    for level in profile.fallback_policy.downgrade_reasoning_levels:
        normalized = str(level or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        levels.append(normalized)
    return tuple(levels)


def _action(
    action: str,
    label: str,
    reason: str,
    *,
    target: str | None = None,
    transition: dict[str, Any] | None = None,
) -> FailureRecommendation:
    return FailureRecommendation(action=action, label=label, reason=reason, target=target, transition=transition)


def _fallback_model_action(provider_id: str, fallback_models: tuple[str, ...], reason: str) -> FailureRecommendation | None:
    if not fallback_models:
        return None
    target = fallback_models[0]
    transition = _transition_dict(
        action="switch_model",
        reason=reason,
        provider_id=provider_id,
        model_id=target,
    )
    return _action("switch_model", "Try Fallback Model", reason, target=target, transition=transition)


def _reasoning_downgrade_action(provider_id: str, model_id: str, levels: tuple[str, ...]) -> FailureRecommendation | None:
    if not levels:
        return None
    target = levels[0]
    transition = _transition_dict(
        action="downgrade_reasoning",
        reason="Retry with a lower reasoning level to reduce context pressure.",
        provider_id=provider_id,
        model_id=model_id,
        reasoning_effort=target,
    )
    return _action("downgrade_reasoning", "Lower Reasoning", "Retry with a lower reasoning level to reduce context pressure.", target=target, transition=transition)


def _compact_then_retry_action(provider_id: str, model_id: str) -> FailureRecommendation:
    transition = _transition_dict(
        action="compact_then_retry",
        reason="Summarize the thread before retrying.",
        provider_id=provider_id,
        model_id=model_id,
        compact_before_send=True,
    )
    return _action("compact_thread", "Compact", "Summarize the thread before retrying.", transition=transition)


def _retry_same_lane_action(provider_id: str, model_id: str) -> FailureRecommendation:
    transition = _transition_dict(
        action="retry_same_lane",
        reason="Retry the current execution lane once.",
        provider_id=provider_id,
        model_id=model_id,
    )
    return _action("retry_same_lane", "Retry", "Retry the current execution lane once.", transition=transition)


def _restart_runtime_action(provider_id: str, model_id: str) -> FailureRecommendation:
    transition = _transition_dict(
        action="restart_runtime_lane",
        reason="Restart or reopen the current execution lane.",
        provider_id=provider_id,
        model_id=model_id,
        restart_runtime=True,
    )
    return _action("restart_runtime_lane", "Restart Runtime", "Restart or reopen the current execution lane.", transition=transition)


def _recommendations(*items: FailureRecommendation | None) -> tuple[FailureRecommendation, ...]:
    return tuple(item for item in items if item is not None)


def _transition_dict(
    *,
    action: str,
    reason: str,
    provider_id: str,
    model_id: str,
    reasoning_effort: str | None = None,
    restart_runtime: bool = False,
    compact_before_send: bool = False,
) -> dict[str, Any] | None:
    if not provider_id:
        return None
    return build_transition_plan(
        action=action,
        reason=reason,
        provider_id=provider_id,
        model_id=model_id or None,
        reasoning_effort=reasoning_effort,
        restart_runtime=restart_runtime,
        compact_before_send=compact_before_send,
    ).to_dict()


def _notice(
    *,
    category: FailureCategory,
    summary: str,
    message: str,
    actionable_hint: str,
    provider: str = "",
    model: str = "",
    retryable: bool = False,
    compact_recommended: bool = False,
    fork_recommended: bool = False,
    fallback_models: tuple[str, ...] = (),
    reasoning_downgrade_levels: tuple[str, ...] = (),
    requires_key_check: bool = False,
    provider_switch_recommended: bool = False,
    recommended_action: str = "inspect_runtime_notice",
    recoverability: Literal["retryable", "recoverable", "requires_user_action", "fail_closed"] = "recoverable",
    recommended_actions: tuple[FailureRecommendation, ...] = (),
) -> RuntimeFailureNotice:
    return RuntimeFailureNotice(
        category=category,
        summary=summary,
        message=message,
        actionable_hint=actionable_hint,
        provider=provider,
        model=model,
        retryable=retryable,
        compact_recommended=compact_recommended,
        fork_recommended=fork_recommended,
        fallback_models=fallback_models,
        reasoning_downgrade_levels=reasoning_downgrade_levels,
        requires_key_check=requires_key_check,
        provider_switch_recommended=provider_switch_recommended,
        recommended_action=recommended_action,
        recoverability=recoverability,
        recommended_actions=recommended_actions,
    )
