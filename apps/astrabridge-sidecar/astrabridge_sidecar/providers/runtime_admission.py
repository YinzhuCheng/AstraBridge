"""Secret-free runtime admission for one selected model route.

``ExecutionRoute`` describes the strongest route that the catalog evidence can
support.  This module turns that static fact into a task-start decision without
opening a provider connection, reading a credential, or mutating project
state.  In particular, a review-only route is allowed to remain a review-only
conversation only after the caller explicitly accepts the loss of agent/tool
semantics; it is never silently treated as an App Server coding lane merely
because App Server is the transport host.
"""

from __future__ import annotations

from typing import Any

from .execution_route import resolve_execution_route


RUNTIME_ROUTE_ADMISSION_SCHEMA_VERSION = "astrabridge-runtime-route-admission-v1"
RUNTIME_ROUTE_ADMISSION_STATUSES = ("admitted", "confirmation_required", "blocked")
RUNTIME_ROUTE_PRESENTATION_STATES = (
    "codex_native",
    "provider_native",
    "provider_app_server",
    "preview_review",
    "reduced_authority",
    "blocked",
    "fallback_available",
    "legacy_unqualified",
)

_TOOL_POLICIES = {"standard", "patch_only", "no_tools"}
_PERMISSION_MODES = {"ask", "auto", "full"}
_CONTEXT_MODES = {"default", "full", "minimal_text", "minimal_visual", "no_context"}
_RICH_MODALITIES = {"image", "audio", "video"}


def resolve_runtime_route_admission(
    profile: dict[str, Any],
    *,
    model: dict[str, Any] | None = None,
    requested_model: str | None = None,
    requested_effort: str | None = None,
    requested_permission_mode: str | None = None,
    requested_execution_policy: str | None = None,
    requested_context_mode: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    source_provider_id: str | None = None,
    native_kernel_enabled: bool = False,
    confirm_degradation: bool = False,
    model_contract_present: bool = True,
) -> dict[str, Any]:
    """Resolve an executable runtime posture for the selected route.

    The result is deliberately compact and credential-free so the same object
    can be returned by the preflight API, attached to a turn-start response,
    rendered by the desktop, and recorded in an event.  It does *not* select a
    fallback model or change the caller's model request.
    """

    provider = dict(profile or {})
    selected_model = _selected_model_contract(
        provider,
        model=model,
        requested_model=requested_model,
    )
    provider_id = _text(selected_model.get("provider") or selected_model.get("provider_id") or provider.get("provider_id")).lower()
    native_model = _native_model(selected_model, fallback=_text(requested_model) or _text(provider.get("model")))
    requested_policy = _choice(requested_execution_policy, _TOOL_POLICIES, "standard")
    requested_permission = _choice(requested_permission_mode, _PERMISSION_MODES, "auto")
    requested_context = _choice(requested_context_mode, _CONTEXT_MODES, "default")
    requested_modalities = _requested_modalities(attachments)
    supported_modalities = _modalities(selected_model)
    configured_evidence = selected_model.get("execution_route_evidence")
    if not isinstance(configured_evidence, dict):
        configured_evidence = provider.get("execution_route_evidence")
    route = resolve_execution_route(
        selected_model,
        provider=provider,
        evidence=dict(configured_evidence) if isinstance(configured_evidence, dict) else None,
    )
    driver = dict(route.get("driver") or {})
    authority = dict(route.get("authority") or {})
    evidence = dict(route.get("evidence") or {})
    route_admission = _text(driver.get("admission")) or "review_only"
    route_driver = _text(driver.get("execution_id")) or "preview_review"
    configured_driver = _text(driver.get("configured_id")) or "app_server"
    effective_authority = _text(authority.get("effective_tier")).upper() or "C"
    declared_authority = _text(authority.get("declared_tier")).upper() or effective_authority
    evidence_state = _text(evidence.get("effective_state")) or "documented"
    verification_status = _text(evidence.get("verification_status")) or "missing"
    model_enabled = bool(selected_model.get("enabled", True))
    agent_enabled = bool(selected_model.get("codex_agent_enabled", True))
    effective_effort, effort_degraded = _effective_reasoning_effort(selected_model, requested_effort)

    blockers: list[str] = []
    degradation_reasons: list[dict[str, str]] = []
    unsupported_modalities = sorted(requested_modalities - supported_modalities)
    if unsupported_modalities:
        blockers.append("requested_modality_not_declared")
        degradation_reasons.append(
            {
                "code": "requested_modality_not_declared",
                "message": f"The selected model does not declare support for: {', '.join(unsupported_modalities)}.",
            }
        )
    if not model_enabled:
        blockers.append("model_disabled")
        degradation_reasons.append(
            {"code": "model_disabled", "message": "This model is disabled in the configured catalog."}
        )
    if not agent_enabled or effective_authority == "D":
        blockers.append("model_not_agent_enabled")
        degradation_reasons.append(
            {
                "code": "model_not_agent_enabled",
                "message": "This model is not eligible for AstraBridge agent execution.",
            }
        )
    if route_driver == "native_kernel" and not native_kernel_enabled:
        blockers.append("native_kernel_disabled")
        degradation_reasons.append(
            {
                "code": "native_kernel_disabled",
                "message": "This route requires the AstraBridge native-provider driver, which is not enabled.",
            }
        )
    if route_driver == "native_kernel" and route_admission not in {"default_eligible", "verified_non_default"}:
        blockers.append("native_driver_not_route_verified")
        degradation_reasons.append(
            {
                "code": "native_driver_not_route_verified",
                "message": "The native-provider driver is unavailable until this exact route is coding-route verified.",
            }
        )
    if not model_contract_present:
        degradation_reasons.append(
            {
                "code": "model_contract_not_configured",
                "message": "This model has no exact configured model contract; it remains review-only until it is recorded and verified.",
            }
        )

    is_reduced_route = route_admission in {"review_only", "tool_contract_only"} or route_driver == "preview_review"
    effective_policy = requested_policy
    effective_permission = requested_permission
    execution_backend = route_driver
    requires_confirmation = False
    if is_reduced_route:
        execution_backend = "app_server"
        effective_policy = "no_tools"
        effective_permission = "ask"
        if requested_policy != "no_tools":
            requires_confirmation = True
            degradation_reasons.append(
                {
                    "code": "tool_semantics_removed",
                    "message": "The selected route is limited to review/proposal output; tool, edit, command, and MCP execution are disabled.",
                }
            )
        if requested_permission != "ask":
            requires_confirmation = True
            degradation_reasons.append(
                {
                    "code": "permission_reduced_to_read_only",
                    "message": "The route is forced to read-only approval mode while its coding authority is unverified.",
                }
            )
        if requested_modalities & _RICH_MODALITIES:
            requires_confirmation = True
            degradation_reasons.append(
                {
                    "code": "multimodal_route_unverified_for_agent_execution",
                    "message": "Rich-input handling may be available only as a review route and is not being presented as verified agent execution.",
                }
            )

    source_provider = _text(source_provider_id).lower()
    if source_provider and provider_id and source_provider != provider_id and requested_context != "no_context":
        requires_confirmation = True
        degradation_reasons.append(
            {
                "code": "cross_provider_continuity_reduced",
                "message": "A cross-provider handoff keeps only neutral task context; provider-private history and reasoning are not replayed.",
            }
        )
    if effort_degraded:
        requires_confirmation = True
        degradation_reasons.append(
            {
                "code": "reasoning_effort_mapped",
                "message": f"Requested reasoning effort is mapped to {effective_effort} for this model route.",
            }
        )

    fallback_targets = [
        _text(value)
        for value in list(dict(route.get("fallback") or {}).get("target_models") or [])
        if _text(value)
    ]
    fallback_status = "available" if fallback_targets else "none"
    if blockers:
        status = "blocked"
        presentation_state = "blocked"
    elif requires_confirmation and not confirm_degradation:
        status = "confirmation_required"
        presentation_state = _presentation_state(
            provider_id=provider_id,
            route_driver=route_driver,
            route_admission=route_admission,
            reduced=is_reduced_route,
            fallback_available=bool(fallback_targets),
        )
    else:
        status = "admitted"
        presentation_state = _presentation_state(
            provider_id=provider_id,
            route_driver=route_driver,
            route_admission=route_admission,
            reduced=is_reduced_route,
            fallback_available=bool(fallback_targets),
        )

    route_blockers = _unique_strings(
        [
            *[str(item).strip() for item in list(evidence.get("reasons") or []) if str(item or "").strip()],
            *blockers,
        ]
    )
    return {
        "schema_version": RUNTIME_ROUTE_ADMISSION_SCHEMA_VERSION,
        "status": status,
        "presentation_state": presentation_state,
        "requested": {
            "provider_id": provider_id or None,
            "model_id": f"{provider_id}/{native_model}" if provider_id and native_model else native_model or None,
            "execution_policy": requested_policy,
            "permission_mode": requested_permission,
            "context_mode": requested_context,
            "reasoning_effort": _text(requested_effort) or None,
            "input_modalities": sorted(requested_modalities),
        },
        "effective": {
            "execution_driver": route_driver,
            "execution_backend": execution_backend,
            "authority_tier": effective_authority,
            "declared_authority_tier": declared_authority,
            "tool_mode": _text(dict(route.get("tool_mode") or {}).get("effective")) or "review_only",
            "execution_policy": effective_policy,
            "permission_mode": effective_permission,
            "context_mode": requested_context,
            "reasoning_effort": effective_effort or None,
            "input_modalities": sorted(supported_modalities),
        },
        "route": {
            "route_id": _text(route.get("route_id")) or None,
            "admission": route_admission,
            "configured_driver": configured_driver,
            "execution_driver": route_driver,
            "evidence_state": evidence_state,
            "verification_status": verification_status,
            "default_route_eligible": bool(route.get("default_route_eligible")),
            "blockers": route_blockers,
        },
        "degradation": {
            "active": bool(degradation_reasons),
            "requires_confirmation": requires_confirmation,
            "confirmed": bool(confirm_degradation and requires_confirmation and not blockers),
            "reasons": _dedupe_reason_records(degradation_reasons),
        },
        "fallback": {
            "status": fallback_status,
            "target_models": fallback_targets,
            "automatic_fallback": False,
            "message": (
                "Fallback targets are available for explicit user selection; AstraBridge did not change the requested model."
                if fallback_targets
                else "No configured route-specific fallback target is available."
            ),
        },
    }


def legacy_runtime_route_admission(
    profile: dict[str, Any],
    *,
    requested_model: str | None = None,
    requested_effort: str | None = None,
    requested_permission_mode: str | None = None,
    requested_execution_policy: str | None = None,
    requested_context_mode: str | None = None,
) -> dict[str, Any]:
    """Project a non-promoting compatibility state for embedded legacy callers.

    Production ``AppContext`` always attaches ``RouterConfigService``.  This
    compatibility projection keeps isolated unit/embedding callers functional
    without claiming route verification or default eligibility.
    """

    provider_id = _text(profile.get("provider_id")).lower()
    native_model = _native_model(profile, fallback=_text(requested_model) or _text(profile.get("model")))
    execution_backend = _legacy_execution_backend(profile)
    requested_policy = _choice(requested_execution_policy, _TOOL_POLICIES, "standard")
    requested_permission = _choice(requested_permission_mode, _PERMISSION_MODES, "auto")
    requested_context = _choice(requested_context_mode, _CONTEXT_MODES, "default")
    return {
        "schema_version": RUNTIME_ROUTE_ADMISSION_SCHEMA_VERSION,
        "status": "admitted",
        "presentation_state": "legacy_unqualified",
        "requested": {
            "provider_id": provider_id or None,
            "model_id": f"{provider_id}/{native_model}" if provider_id and native_model else native_model or None,
            "execution_policy": requested_policy,
            "permission_mode": requested_permission,
            "context_mode": requested_context,
            "reasoning_effort": _text(requested_effort) or None,
            "input_modalities": [],
        },
        "effective": {
            "execution_driver": execution_backend,
            "execution_backend": execution_backend,
            "authority_tier": "unknown",
            "declared_authority_tier": "unknown",
            "tool_mode": "legacy_unqualified",
            "execution_policy": requested_policy,
            "permission_mode": requested_permission,
            "context_mode": requested_context,
            "reasoning_effort": _text(requested_effort) or None,
            "input_modalities": [],
        },
        "route": {
            "route_id": None,
            "admission": "legacy_unqualified",
            "configured_driver": execution_backend,
            "execution_driver": execution_backend,
            "evidence_state": "not_available",
            "verification_status": "not_available",
            "default_route_eligible": False,
            "blockers": ["router_config_service_unavailable"],
        },
        "degradation": {
            "active": True,
            "requires_confirmation": False,
            "confirmed": False,
            "reasons": [
                {
                    "code": "router_config_service_unavailable",
                    "message": "Route evidence is not available in this embedded compatibility runtime; no verification claim is made.",
                }
            ],
        },
        "fallback": {
            "status": "none",
            "target_models": [],
            "automatic_fallback": False,
            "message": "No route-specific fallback was evaluated.",
        },
    }


def _selected_model_contract(
    profile: dict[str, Any],
    *,
    model: dict[str, Any] | None,
    requested_model: str | None,
) -> dict[str, Any]:
    selected = dict(profile)
    if isinstance(model, dict):
        selected.update(model)
    requested = _text(requested_model)
    if requested:
        provider_id, native_model = _split_model_id(requested, default_provider=_text(selected.get("provider_id") or selected.get("provider")))
        if provider_id:
            selected["provider_id"] = provider_id
            selected["provider"] = provider_id
        if native_model:
            selected["model"] = native_model
            selected["native_model"] = native_model
    return selected


def _native_model(model: dict[str, Any], *, fallback: str) -> str:
    candidate = _text(model.get("native_model") or model.get("model") or fallback)
    _provider, native = _split_model_id(candidate, default_provider=_text(model.get("provider_id") or model.get("provider")))
    return native


def _split_model_id(value: str, *, default_provider: str) -> tuple[str, str]:
    clean = _text(value)
    if "/" not in clean:
        return _text(default_provider).lower(), clean
    provider_id, native_model = [part.strip() for part in clean.split("/", 1)]
    return provider_id.lower(), native_model


def _choice(value: Any, allowed: set[str], default: str) -> str:
    candidate = _text(value).lower().replace("-", "_")
    return candidate if candidate in allowed else default


def _legacy_execution_backend(profile: dict[str, Any]) -> str:
    """Retain an embedded caller's explicit local execution host.

    The compatibility projection does not claim route evidence, but it must
    not rewrite an isolated native-kernel test/runtime into an App Server
    request merely because no RouterConfigService was attached.
    """

    candidate = _text(profile.get("execution_backend")).lower().replace("-", "_")
    return candidate if candidate in {"app_server", "native_kernel"} else "app_server"


def _modalities(model: dict[str, Any]) -> set[str]:
    values = model.get("input_modalities")
    if not isinstance(values, (list, tuple, set)):
        return {"text"}
    normalized = {_text(item).lower() for item in values if _text(item)}
    return normalized or {"text"}


def _requested_modalities(attachments: list[dict[str, Any]] | None) -> set[str]:
    requested = {"text"}
    for attachment in list(attachments or []):
        if not isinstance(attachment, dict):
            continue
        kind = _text(attachment.get("kind") or attachment.get("modality") or attachment.get("type")).lower()
        if kind in _RICH_MODALITIES:
            requested.add(kind)
    return requested


def _effective_reasoning_effort(model: dict[str, Any], requested_effort: str | None) -> tuple[str, bool]:
    requested = _text(requested_effort).lower()
    supported_raw = model.get("supported_reasoning_levels") or model.get("native_supported_reasoning_levels") or []
    supported = [_text(value).lower() for value in list(supported_raw) if _text(value)]
    if not supported:
        return requested, False
    if requested and requested in supported:
        return requested, False
    preferred = _text(model.get("default_reasoning_level") or model.get("native_default_reasoning_level")).lower()
    effective = preferred if preferred in supported else supported[0]
    return effective, bool(requested and effective != requested)


def _presentation_state(
    *,
    provider_id: str,
    route_driver: str,
    route_admission: str,
    reduced: bool,
    fallback_available: bool,
) -> str:
    if reduced:
        return "reduced_authority" if route_admission == "tool_contract_only" else "preview_review"
    if route_driver == "native_kernel":
        return "provider_native"
    if provider_id in {"openai", "codex"} and route_driver == "app_server":
        return "codex_native"
    if fallback_available and route_admission not in {"default_eligible", "verified_non_default"}:
        return "fallback_available"
    return "provider_app_server"


def _dedupe_reason_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        code = _text(record.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        unique.append({"code": code, "message": _text(record.get("message"))})
    return unique


def _unique_strings(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def _text(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "RUNTIME_ROUTE_ADMISSION_SCHEMA_VERSION",
    "RUNTIME_ROUTE_ADMISSION_STATUSES",
    "RUNTIME_ROUTE_PRESENTATION_STATES",
    "legacy_runtime_route_admission",
    "resolve_runtime_route_admission",
]
