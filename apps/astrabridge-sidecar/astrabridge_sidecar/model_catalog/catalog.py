from __future__ import annotations

from typing import Any

from ..providers import get_provider_profile, resolve_provider_id
from ..providers.tooling import (
    assess_default_route_verification,
    assess_model_authority,
    has_structured_tool_surface,
    normalize_apply_patch_tool_type,
)
from ..reasoning_policy import normalize_reasoning_effort, normalize_reasoning_efforts, resolve_reasoning_state_visibility


CODEX_CLI_BASELINE = "0.137.0"
DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT = 80
ASTRABRIDGE_MODEL_CATALOG_FILENAME = "astrabridge-models.json"
ASTRABRIDGE_MODELS_CACHE_FILENAME = "astrabridge-models-cache.json"
PROFILE_MODEL_RESERVED_FIELDS = {"id", "provider", "native_model", "display_name", "displayName"}
RUNTIME_PROVIDER_CONTRACT_SCHEMA_VERSION = "astrabridge-runtime-provider-contract-v1"
APP_SERVER_REASONING_EFFORT_ALIASES = {
    "off": "none",
}
RUNTIME_PROVIDER_CONTRACT_AUDIT_FIELDS = (
    "reasoning_effort",
    "reasoning_state",
    "context_window",
    "tool_schema",
    "apply_patch_tool_type",
    "web_search",
    "vision",
    "parallel_tools",
    "mcp",
    "token_usage",
)
WEB_CAPABILITY_DEFAULTS = {
    "native_web_search_support": "unverified",
    "tool_web_search_support": "unverified",
    "mcp_web_support": "unverified",
    "web_smoke_status": "untested",
    "citation_quality": "untested",
}
ALLOWED_INPUT_MODALITIES = {"text", "image", "audio", "video", "file"}
WORKFLOW_CONTRACT_DEFAULTS = {
    "mcp_tools": "untested",
    "codex_builtin_tools": "metadata_only",
    "plan": "conservative",
    "request_user_input": "conservative",
    "goal": "app_server_native",
    "manual_compact": "app_server_native",
    "auto_compact": "configured_unverified",
    "compact_summary_quality": "untested",
}
CONFIGURED_MODEL_RUNTIME_OVERRIDE_FIELDS = {
    "enabled",
    "display_name",
    "displayName",
    "ui_context_hint_only",
    "adapter_profile",
    "codex_agent_enabled",
    "advertised_context_window",
    "input_modalities",
    "supported_reasoning_levels",
    "default_reasoning_level",
    "native_supported_reasoning_levels",
    "native_default_reasoning_level",
    "reasoning_policy_mode",
    "supports_reasoning_replay",
    "preserve_reasoning_for_tool_turns",
    "apply_patch_tool_type",
    "web_search_tool_type",
    "supports_parallel_tool_calls",
    "supports_search_tool",
    "supports_mcp_tools",
    "mcp_tool_call_policy",
    "mcp_verified_servers",
    "mcp_smoke_status",
    "mcp_tool_argument_validation",
    "native_web_search_support",
    "tool_web_search_support",
    "mcp_web_support",
    "web_smoke_status",
    "citation_quality",
    "supports_image_detail_original",
    "effective_context_window_percent",
    "auto_compact_token_limit",
    "tool_output_token_limit",
    "context_budget_policy",
    "temperature_default",
    "temperature_ui_min",
    "temperature_ui_max",
    "provider_temperature_min",
    "provider_temperature_max",
    "temperature_adapter_policy",
    "modality_limits",
    "ui_warnings",
    "command_execution_status",
    "command_execution_note",
    "pricing_currency",
    "pricing_input_per_mtok",
    "pricing_output_per_mtok",
    "pricing_cached_input_per_mtok",
    "pricing_source_url",
    "pricing_status",
    "last_web_verified_at",
    "source_urls",
    "created_at",
    "updated_at",
    "last_verified_at",
    "verification_notes",
    "recommended",
    "default_for_provider",
    "deprecated",
    "deprecated_after",
    "confidence",
    "catalog_version",
    "source_provenance",
}


def known_context_window(provider_id: str, model: str) -> int | None:
    profile = _profile_for(provider_id, model)
    if profile and profile.context_window():
        return int(profile.context_window() or 0) or None
    return None


def known_reasoning_efforts(provider_id: str, model: str) -> list[str]:
    profile = _profile_for(provider_id, model)
    if profile:
        return list(profile.reasoning_levels())
    return ["low", "medium", "high", "xhigh"]


def known_input_modalities(provider_id: str, model: str) -> list[str] | None:
    profile = _profile_for(provider_id, model)
    if profile:
        return list(profile.context_policy.default_input_modalities)
    return None


def compact_limit(context_window: int, configured_limit: int | None = None) -> int:
    upper_bound = int(context_window * 0.9)
    if configured_limit:
        return min(configured_limit, upper_bound)
    return int(context_window * (DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT / 100))


def tool_output_truncation_limit(context_window: int) -> int:
    if context_window <= 32_768:
        return 8_000
    if context_window <= 65_536:
        return 16_000
    return 32_000


def normalize_input_modalities(value: Any, provider_id: str = "", native_model: str = "") -> list[str]:
    known = known_input_modalities(provider_id, native_model)
    if isinstance(value, (list, tuple)):
        normalized = [str(item).strip().lower() for item in value if str(item).strip()]
        allowed = [item for item in normalized if item in ALLOWED_INPUT_MODALITIES]
        if allowed:
            return sorted(set(allowed), key=allowed.index)
    return known or ["text"]


def effective_model_records(
    configured_models: list[dict[str, Any]] | None = None,
    *,
    include_disabled: bool = True,
) -> list[dict[str, Any]]:
    from .generated_catalog import current_generated_catalog

    configured_list = [dict(item) for item in list(configured_models or []) if isinstance(item, dict)]
    generated = current_generated_catalog()
    configured_by_id = {
        str(item.get("id") or ""): dict(item)
        for item in configured_list
        if str(item.get("id") or "").strip()
    }
    configured_by_key = {
        (
            str(item.get("provider") or "").strip(),
            str(item.get("native_model") or "").strip(),
        ): dict(item)
        for item in configured_list
        if str(item.get("provider") or "").strip() and str(item.get("native_model") or "").strip()
    }
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str]] = set()
    for item in generated.models:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        model_key = (str(item.get("provider") or "").strip(), str(item.get("native_model") or "").strip())
        effective = _merge_generated_and_configured_model(
            item,
            configured_by_key.get(model_key, {}),
            configured_by_id.get(model_id, {}),
        )
        if not include_disabled and not bool(effective.get("enabled", True)):
            continue
        merged.append(effective)
        seen_ids.add(model_id)
        seen_keys.add(model_key)
    for model_id, item in configured_by_id.items():
        item_key = (str(item.get("provider") or "").strip(), str(item.get("native_model") or "").strip())
        if model_id in seen_ids or item_key in seen_keys:
            continue
        if not include_disabled and not bool(item.get("enabled", True)):
            continue
        merged.append(dict(item))
    return merged


def effective_model_record(
    provider_id: str,
    native_model: str,
    configured_models: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    provider_text = str(provider_id or "").strip()
    native_text = str(native_model or "").strip()
    full_model_id = f"{provider_text}/{native_text}" if provider_text and native_text else ""
    for item in effective_model_records(configured_models, include_disabled=True):
        item_id = str(item.get("id") or "").strip()
        if full_model_id and item_id == full_model_id:
            return item
        if (
            str(item.get("provider") or "").strip() == provider_text
            and str(item.get("native_model") or "").strip() == native_text
        ):
            return item
    return None


def merge_profile_with_effective_model(
    profile: dict[str, Any],
    configured_models: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    merged = dict(profile)
    provider_id = str(merged.get("provider_id") or "").strip()
    native_model = str(merged.get("model") or merged.get("native_model") or "").strip()
    if not provider_id or not native_model:
        return merged
    model = effective_model_record(provider_id, native_model, configured_models)
    if not model:
        return merged
    for key, value in model.items():
        if key in PROFILE_MODEL_RESERVED_FIELDS:
            continue
        existing = merged.get(key)
        is_empty = existing is None or existing == "" or existing == () or (isinstance(existing, list) and not existing)
        if is_empty:
            merged[key] = value
    return merged


def resolved_web_capability_fields(
    model: dict[str, Any],
    *,
    tool_default: str | None = None,
    smoke_default: str | None = None,
    citation_default: str | None = None,
    mcp_fallback_to_smoke: bool = False,
) -> dict[str, Any]:
    native_default = WEB_CAPABILITY_DEFAULTS["native_web_search_support"]
    tool_default_value = tool_default or WEB_CAPABILITY_DEFAULTS["tool_web_search_support"]
    smoke_default_value = smoke_default or WEB_CAPABILITY_DEFAULTS["web_smoke_status"]
    citation_default_value = citation_default or WEB_CAPABILITY_DEFAULTS["citation_quality"]
    mcp_default = WEB_CAPABILITY_DEFAULTS["mcp_web_support"]
    mcp_value = model.get("mcp_web_support")
    if not mcp_value and mcp_fallback_to_smoke:
        mcp_value = model.get("mcp_smoke_status")
    return {
        "native_web_search_support": str(model.get("native_web_search_support") or native_default),
        "tool_web_search_support": str(model.get("tool_web_search_support") or tool_default_value),
        "mcp_web_support": str(mcp_value or mcp_default),
        "web_smoke_status": str(model.get("web_smoke_status") or smoke_default_value),
        "citation_quality": str(model.get("citation_quality") or citation_default_value),
        "last_web_verified_at": model.get("last_web_verified_at"),
    }


def resolved_workflow_contract_fields(
    model: dict[str, Any],
    *,
    modalities_default: str | None = None,
) -> dict[str, Any]:
    planner_support = dict(model.get("planner_support") or {})
    goal_support = dict(model.get("goal_support") or {})
    context_compaction_support = dict(model.get("context_compaction_support") or {})
    return {
        "modalities": modalities_default or "metadata_only",
        "mcp_tools": str(model.get("mcp_smoke_status") or WORKFLOW_CONTRACT_DEFAULTS["mcp_tools"]),
        "codex_builtin_tools": WORKFLOW_CONTRACT_DEFAULTS["codex_builtin_tools"],
        "plan": str(planner_support.get("plan_mode") or WORKFLOW_CONTRACT_DEFAULTS["plan"]),
        "request_user_input": str(planner_support.get("request_user_input") or WORKFLOW_CONTRACT_DEFAULTS["request_user_input"]),
        "goal": str(goal_support.get("thread_goal") or WORKFLOW_CONTRACT_DEFAULTS["goal"]),
        "manual_compact": str(context_compaction_support.get("manual_compact") or WORKFLOW_CONTRACT_DEFAULTS["manual_compact"]),
        "auto_compact": str(context_compaction_support.get("auto_compact") or WORKFLOW_CONTRACT_DEFAULTS["auto_compact"]),
        "compact_summary_quality": str(
            context_compaction_support.get("structured_summary_quality") or WORKFLOW_CONTRACT_DEFAULTS["compact_summary_quality"]
        ),
    }


def resolved_provider_source_of_truth_fields(
    provider: dict[str, Any],
    configured_models: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    provider_id = str(provider.get("id") or provider.get("provider_id") or "").strip()
    configured_default_model = str(provider.get("default_model") or provider.get("model") or "").strip() or None
    preferred_model = preferred_provider_model_record(provider_id, configured_models, include_deprecated=False)
    if preferred_model is None and configured_default_model:
        preferred_model = effective_model_record(provider_id, configured_default_model, configured_models)
    source_model = dict(preferred_model or _provider_default_model_record(provider, configured_default_model))
    runtime_contract = resolved_runtime_provider_contract_fields(source_model) if source_model else {}
    codex_runtime = dict(runtime_contract.get("codex_runtime_metadata") or {})
    capability_metadata = dict(runtime_contract.get("capability_metadata") or {})
    reasoning_policy = dict(capability_metadata.get("reasoning_effort") or {})
    reasoning_state = dict(capability_metadata.get("reasoning_state") or {})
    context_gate = dict(capability_metadata.get("context_window") or {})
    tool_schema = dict(capability_metadata.get("tool_schema") or {})
    apply_patch = dict(capability_metadata.get("apply_patch_tool_type") or {})
    web_capability = dict(capability_metadata.get("web_search") or {})
    parallel_tools = dict(capability_metadata.get("parallel_tools") or {})
    mcp = dict(capability_metadata.get("mcp") or {})
    token_usage = dict(capability_metadata.get("token_usage") or {})
    workflow_contract = dict(token_usage.get("workflow_contract") or resolved_workflow_contract_fields(source_model))
    effective_default_model = str(source_model.get("native_model") or configured_default_model or "").strip() or None
    effective_default_model_id = str(source_model.get("id") or "").strip() or (
        f"{provider_id}/{effective_default_model}" if provider_id and effective_default_model else None
    )
    if configured_default_model and effective_default_model:
        default_model_alignment = "aligned" if configured_default_model == effective_default_model else "stale_config"
    elif effective_default_model:
        default_model_alignment = "catalog_only"
    else:
        default_model_alignment = "unknown"
    warnings: list[str] = []
    if configured_default_model and effective_default_model and configured_default_model != effective_default_model:
        warnings.append("configured_default_model_differs_from_catalog_preferred_model")
    if provider_id and not preferred_model:
        warnings.append("provider_preferred_model_missing")
    auto_compact_status = str(context_gate.get("auto_compact_status") or "")
    compact_summary_quality_status = str(context_gate.get("compact_summary_quality_status") or "")
    if auto_compact_status in {"configured_unverified", "untested"}:
        warnings.append("auto_compact_validation_unverified")
    if compact_summary_quality_status in {"configured_unverified", "untested"}:
        warnings.append("compact_summary_quality_unverified")
    return {
        "provider_id": provider_id or None,
        "protocol": str(provider.get("protocol") or provider.get("adapter_type") or "").strip() or None,
        "configured_default_model": configured_default_model,
        "effective_default_model": effective_default_model,
        "effective_default_model_id": effective_default_model_id,
        "default_model_alignment": default_model_alignment,
        "reasoning_policy_mode": str(provider.get("reasoning_policy_mode") or "").strip() or None,
        "context_window": codex_runtime.get("context_window"),
        "context_gate": context_gate,
        "auto_compact_token_limit": codex_runtime.get("auto_compact_token_limit"),
        "tool_output_token_limit": codex_runtime.get("tool_output_token_limit"),
        "workflow_contract": workflow_contract,
        "reasoning_policy": reasoning_policy,
        "reasoning_state": reasoning_state,
        "tool_policy": {
            "supports_tool_calls": bool(tool_schema.get("supports_tool_calls", False)),
            "supports_mcp_tools": bool(mcp.get("supports_mcp_tools", False)),
            "mcp_tool_call_policy": str(mcp.get("tool_call_policy") or "unsupported"),
            "supports_parallel_tool_calls": bool(parallel_tools.get("supported", False)),
            "parallel_tool_call_status": str(parallel_tools.get("status") or "disabled"),
        },
        "apply_patch_tool_type": apply_patch.get("codex_value"),
        "web_search_tool_type": web_capability.get("tool_type"),
        "web_capability": web_capability,
        "warnings": warnings,
    }


def resolved_runtime_provider_contract_fields(model: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(model.get("provider") or model.get("provider_id") or "").strip()
    native_model = str(model.get("native_model") or model.get("model") or "").strip()
    model_id = str(model.get("id") or "").strip() or (f"{provider_id}/{native_model}" if provider_id and native_model else native_model)
    raw_provider_efforts = _clean_string_list(model.get("supported_reasoning_levels"))
    if not raw_provider_efforts:
        raw_provider_efforts = known_reasoning_efforts(provider_id, native_model)
    native_provider_efforts = _clean_string_list(model.get("native_supported_reasoning_levels")) or list(raw_provider_efforts)
    provider_efforts = _codex_reasoning_efforts(raw_provider_efforts)
    codex_efforts = list(provider_efforts)
    native_provider_default_effort = _native_reasoning_effort(
        model.get("native_default_reasoning_level") or model.get("default_reasoning_level") or model.get("reasoning_effort") or ""
    )
    provider_default_effort = _codex_reasoning_effort(model.get("default_reasoning_level") or model.get("reasoning_effort") or native_provider_default_effort or "")
    codex_default_effort = _codex_reasoning_effort(provider_default_effort or (codex_efforts[-1] if codex_efforts else "high"))
    if codex_default_effort not in codex_efforts:
        codex_efforts = [*codex_efforts, codex_default_effort]
    reasoning_policy_mode = str(model.get("reasoning_policy_mode") or "").strip().lower() or None
    supports_reasoning_replay = bool(model.get("supports_reasoning_replay", False))
    preserve_reasoning_for_tool_turns = bool(model.get("preserve_reasoning_for_tool_turns", False))
    reasoning_state_visibility = resolve_reasoning_state_visibility(
        reasoning_policy_mode,
        supports_reasoning_replay=supports_reasoning_replay,
    )

    input_modalities = normalize_input_modalities(model.get("input_modalities"), provider_id, native_model)
    apply_patch_tool_type = model.get("apply_patch_tool_type")
    codex_apply_patch_tool_type = _codex_apply_patch_tool_type(apply_patch_tool_type)
    web_search_tool_type = str(model.get("web_search_tool_type") or "text").strip()
    codex_web_search_tool_type = web_search_tool_type if web_search_tool_type in {"text", "text_and_image"} else "text"
    context_window = (
        _optional_positive_int(model.get("context_window"))
        or _optional_positive_int(model.get("max_context_window"))
        or _optional_positive_int(model.get("advertised_context_window"))
        or known_context_window(provider_id, native_model)
    )
    effective_context_window_percent = int(model.get("effective_context_window_percent") or DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT)
    auto_compact_token_limit = _optional_positive_int(model.get("auto_compact_token_limit"))
    tool_output_token_limit = _optional_positive_int(model.get("tool_output_token_limit"))
    explicit_auto_compact_limit = auto_compact_token_limit
    explicit_tool_output_limit = tool_output_token_limit
    if context_window and not auto_compact_token_limit:
        auto_compact_token_limit = compact_limit(context_window)
    if context_window and not tool_output_token_limit:
        tool_output_token_limit = tool_output_truncation_limit(context_window)
    effective_context_budget_tokens = (
        int(int(context_window) * (effective_context_window_percent / 100))
        if context_window
        else None
    )
    supports_mcp_tools = bool(model.get("supports_mcp_tools", False))
    mcp_tool_call_policy = str(model.get("mcp_tool_call_policy") or "unsupported")
    supports_parallel = bool(model.get("supports_parallel_tool_calls", False))
    supports_image_detail_original = bool("image" in input_modalities and model.get("supports_image_detail_original", False))
    authority = assess_model_authority(
        {
            **model,
            "supports_tool_calls": has_structured_tool_surface(model),
            "supports_parallel_tool_calls": supports_parallel,
            "apply_patch_tool_type": apply_patch_tool_type,
        }
    )
    web_capabilities = resolved_web_capability_fields(model, mcp_fallback_to_smoke=True)
    workflow_contract = resolved_workflow_contract_fields(model, modalities_default=",".join(input_modalities))
    context_compaction_support = dict(model.get("context_compaction_support") or {})
    context_budget_policy = dict(model.get("context_budget_policy") or {})
    advertised_context_window_status = str(context_budget_policy.get("advertised_context_window_status") or "advertised").strip().lower()
    if advertised_context_window_status not in {"advertised", "verified", "unknown"}:
        advertised_context_window_status = "advertised"
    endpoint_budget_status = str(context_budget_policy.get("endpoint_overhead_status") or "conservative").strip().lower()
    if endpoint_budget_status not in {"verified", "conservative", "unknown"}:
        endpoint_budget_status = "conservative"
    manual_compact_status = str(context_compaction_support.get("manual_compact") or WORKFLOW_CONTRACT_DEFAULTS["manual_compact"])
    auto_compact_status = str(context_compaction_support.get("auto_compact") or WORKFLOW_CONTRACT_DEFAULTS["auto_compact"])
    compact_summary_quality_status = str(
        context_compaction_support.get("structured_summary_quality") or WORKFLOW_CONTRACT_DEFAULTS["compact_summary_quality"]
    )

    errors: list[str] = []
    warnings: list[str] = []
    if not provider_id:
        errors.append("provider_id_missing")
    if not native_model:
        errors.append("native_model_missing")
    if context_window is None:
        warnings.append("context_window_unverified")
    if provider_default_effort and codex_default_effort not in codex_efforts:
        warnings.append("default_reasoning_effort_not_in_supported_set")
    if apply_patch_tool_type and codex_apply_patch_tool_type is None:
        warnings.append("unsupported_apply_patch_tool_type")
    if web_search_tool_type not in {"text", "text_and_image"}:
        warnings.append("unsupported_web_search_tool_type_defaulted_to_text")
    if supports_mcp_tools and mcp_tool_call_policy == "unsupported":
        warnings.append("mcp_tools_enabled_with_unsupported_policy")
    if supports_parallel and not (supports_mcp_tools or codex_apply_patch_tool_type):
        warnings.append("parallel_tools_enabled_without_structured_tool_surface")
    if model.get("supports_image_detail_original") and "image" not in input_modalities:
        warnings.append("image_detail_original_enabled_without_image_modality")
    if not tool_output_token_limit:
        warnings.append("tool_output_token_limit_unverified")

    validation_status = "fail" if errors else "warn" if warnings else "pass"
    pricing_fields = {
        "currency": str(model.get("pricing_currency") or ""),
        "input_per_mtok": model.get("pricing_input_per_mtok"),
        "output_per_mtok": model.get("pricing_output_per_mtok"),
        "cached_input_per_mtok": model.get("pricing_cached_input_per_mtok"),
        "status": str(model.get("pricing_status") or "unknown"),
        "source_url_present": bool(str(model.get("pricing_source_url") or "").strip()),
    }
    usage_available = context_window is not None or tool_output_token_limit is not None
    return {
        "schema_version": RUNTIME_PROVIDER_CONTRACT_SCHEMA_VERSION,
        "audited_fields": list(RUNTIME_PROVIDER_CONTRACT_AUDIT_FIELDS),
        "model_id": model_id,
        "provider_metadata": {
            "provider_id": provider_id or None,
            "native_model": native_model or None,
            "supported_reasoning_levels": provider_efforts,
            "default_reasoning_level": provider_default_effort or None,
            "native_supported_reasoning_levels": native_provider_efforts,
            "native_default_reasoning_level": native_provider_default_effort or None,
            "reasoning_policy_mode": reasoning_policy_mode,
            "input_modalities": input_modalities,
            "tool_mode": model.get("tool_mode"),
            "model_kind": model.get("model_kind"),
        },
        "codex_runtime_metadata": {
            "model_id": model_id,
            "supported_reasoning_levels": codex_efforts,
            "default_reasoning_level": codex_default_effort,
            "apply_patch_tool_type": codex_apply_patch_tool_type,
            "web_search_tool_type": codex_web_search_tool_type,
            "supports_parallel_tool_calls": supports_parallel,
            "supports_mcp_tools": supports_mcp_tools,
            "mcp_tool_call_policy": mcp_tool_call_policy,
            "input_modalities": input_modalities,
            "supports_image_detail_original": supports_image_detail_original,
            "context_window": context_window,
            "effective_context_window_percent": effective_context_window_percent,
            "effective_context_budget_tokens": effective_context_budget_tokens,
            "auto_compact_token_limit": auto_compact_token_limit,
            "tool_output_token_limit": tool_output_token_limit,
            "advertised_context_window_status": advertised_context_window_status,
            "verified_usable_coding_context_tokens": None,
            "usable_coding_context_status": "requires_endpoint_preflight",
        },
        "capability_metadata": {
            "reasoning_effort": {
                "provider_values": provider_efforts,
                "codex_values": codex_efforts,
                "provider_default": provider_default_effort or None,
                "codex_default": codex_default_effort,
                "native_provider_values": native_provider_efforts,
                "native_provider_default": native_provider_default_effort or None,
            },
            "reasoning_state": {
                "visibility": reasoning_state_visibility,
                "replayable": supports_reasoning_replay,
                "reasoning_policy_mode": reasoning_policy_mode,
                "preserve_for_tool_turns": preserve_reasoning_for_tool_turns,
            },
            "tool_schema": {
                "supports_tool_calls": bool(supports_mcp_tools or codex_apply_patch_tool_type),
                "tool_mode": model.get("tool_mode"),
                "experimental_supported_tools": list(model.get("experimental_supported_tools") or []),
                "codex_builtin_tools": dict(model.get("codex_builtin_tools") or {}),
                "argument_validation": str(model.get("mcp_tool_argument_validation") or "unsupported"),
            },
            "apply_patch_tool_type": {
                "provider_value": apply_patch_tool_type,
                "codex_value": codex_apply_patch_tool_type,
                "mapping_status": _apply_patch_mapping_status(apply_patch_tool_type, codex_apply_patch_tool_type),
            },
            "web_search": {
                "tool_type": codex_web_search_tool_type,
                "supports_search_tool": bool(model.get("supports_search_tool", False)),
                **web_capabilities,
            },
            "context_window": {
                "declared_context_window": context_window,
                "advertised_context_window_tokens": context_window,
                "advertised_context_window_status": advertised_context_window_status,
                "effective_context_window_percent": effective_context_window_percent,
                "effective_context_budget_tokens": effective_context_budget_tokens,
                "auto_compact_token_limit": auto_compact_token_limit,
                "auto_compact_limit_source": (
                    "configured" if explicit_auto_compact_limit else "derived_from_context_window" if context_window else "unknown"
                ),
                "manual_compact_status": manual_compact_status,
                "auto_compact_status": auto_compact_status,
                "compact_summary_quality_status": compact_summary_quality_status,
                "tool_output_token_limit": tool_output_token_limit,
                "tool_output_limit_source": (
                    "configured" if explicit_tool_output_limit else "derived_from_context_window" if context_window else "unknown"
                ),
                "preflight_budgeting_status": "budgeted_before_send",
                "automatic_request_truncation": False,
                "provider_rejection_category": "context_window_limit",
                "endpoint_budget_status": endpoint_budget_status,
                "verified_usable_coding_context_tokens": None,
                "usable_coding_context_status": "requires_endpoint_preflight",
                "context_budget_policy": {
                    "schema_version": str(context_budget_policy.get("schema_version") or "astrabridge-context-budget-policy-v1"),
                    "endpoint_protocol_overhead_tokens": _optional_positive_int(
                        context_budget_policy.get("endpoint_protocol_overhead_tokens")
                    ),
                    "output_reserve_tokens": _optional_positive_int(context_budget_policy.get("output_reserve_tokens")),
                    "reasoning_artifact_policy": str(
                        context_budget_policy.get("reasoning_artifact_policy") or "neutral_summary_only"
                    ),
                },
            },
            "vision": {
                "input_modalities": input_modalities,
                "supports_image_inputs": "image" in input_modalities,
                "supports_image_detail_original": supports_image_detail_original,
                "modality_limits": dict(model.get("modality_limits") or {}),
            },
            "parallel_tools": {
                "supported": supports_parallel,
                "status": authority.parallel_tool_call_status,
            },
            "mcp": {
                "supports_mcp_tools": supports_mcp_tools,
                "tool_call_policy": mcp_tool_call_policy,
                "verified_servers": list(model.get("mcp_verified_servers") or []),
                "smoke_status": str(model.get("mcp_smoke_status") or "untested"),
                "argument_validation": str(model.get("mcp_tool_argument_validation") or "unsupported"),
            },
            "token_usage": {
                "usage_event": "thread/tokenUsage/updated",
                "usage_available": usage_available,
                "context_window": context_window,
                "auto_compact_token_limit": auto_compact_token_limit,
                "tool_output_token_limit": tool_output_token_limit,
                "pricing": pricing_fields,
                "workflow_contract": workflow_contract,
            },
        },
        "validation": {
            "status": validation_status,
            "errors": errors,
            "warnings": warnings,
        },
    }


def provider_model_records(
    provider_id: str,
    configured_models: list[dict[str, Any]] | None = None,
    *,
    include_disabled: bool = False,
    include_deprecated: bool = True,
) -> list[dict[str, Any]]:
    provider_text = str(provider_id or "").strip()
    if not provider_text:
        return []
    records: list[dict[str, Any]] = []
    for item in effective_model_records(configured_models, include_disabled=True):
        if str(item.get("provider") or "").strip() != provider_text:
            continue
        if not include_disabled and not bool(item.get("enabled", True)):
            continue
        if not include_deprecated and bool(item.get("deprecated", False)):
            continue
        records.append(item)
    return sorted(records, key=_provider_model_sort_key)


def preferred_provider_model_record(
    provider_id: str,
    configured_models: list[dict[str, Any]] | None = None,
    *,
    include_deprecated: bool = False,
) -> dict[str, Any] | None:
    records = provider_model_records(
        provider_id,
        configured_models,
        include_disabled=False,
        include_deprecated=include_deprecated,
    )
    return records[0] if records else None


def fallback_model_ids(
    provider_id: str,
    current_model: str,
    configured_models: list[dict[str, Any]] | None = None,
    *,
    include_deprecated: bool = False,
) -> tuple[str, ...]:
    current_native_model = str(current_model or "").split("/", 1)[1] if "/" in str(current_model or "") else str(current_model or "")
    seen: set[str] = set()
    models: list[str] = []
    for item in provider_model_records(
        provider_id,
        configured_models,
        include_disabled=False,
        include_deprecated=include_deprecated,
    ):
        native_model = str(item.get("native_model") or "").strip()
        if not native_model or native_model in {str(current_model or "").strip(), current_native_model} or native_model in seen:
            continue
        seen.add(native_model)
        models.append(native_model)
    return tuple(models)


def model_catalog_entry(
    *,
    model_id: str,
    provider_id: str,
    native_model: str,
    display_name: str,
    context_window: int,
    reasoning_effort: Any = None,
    configured_model: dict[str, Any] | None = None,
    auto_compact_token_limit: int | None = None,
) -> dict[str, Any]:
    configured_model = configured_model or {}
    configured_efforts = [str(item) for item in list(configured_model.get("supported_reasoning_levels") or []) if str(item).strip()]
    profile = _profile_for(provider_id, native_model)
    efforts = _codex_reasoning_efforts(configured_efforts or known_reasoning_efforts(provider_id, native_model))
    native_efforts = _clean_string_list(configured_model.get("native_supported_reasoning_levels")) or (
        list(profile.native_reasoning_levels()) if profile else list(configured_efforts or known_reasoning_efforts(provider_id, native_model))
    )
    default_effort_raw = (
        _codex_reasoning_effort(reasoning_effort)
        if reasoning_effort
        else str(configured_model.get("default_reasoning_level") or "").strip()
        or (profile.default_reasoning_level() if profile else "")
        or (efforts[-1] if efforts else None)
    )
    default_effort = _codex_reasoning_effort(default_effort_raw)
    native_default_effort = _native_reasoning_effort(
        configured_model.get("native_default_reasoning_level")
        or configured_model.get("default_reasoning_level")
        or (profile.native_default_reasoning_level() if profile else "")
        or default_effort_raw
    )
    if default_effort and default_effort not in efforts:
        efforts.append(default_effort)
    resolved_compact_limit = compact_limit(context_window, auto_compact_token_limit)
    truncation_limit = int(configured_model.get("tool_output_token_limit") or tool_output_truncation_limit(context_window))
    input_modalities = normalize_input_modalities(configured_model.get("input_modalities"), provider_id, native_model)
    apply_patch_tool_type = configured_model.get("apply_patch_tool_type")
    codex_apply_patch_tool_type = _codex_apply_patch_tool_type(apply_patch_tool_type)
    web_search_tool_type = configured_model.get("web_search_tool_type")
    temperature_default = _optional_float(configured_model.get("temperature_default"), 0.0)
    temperature_ui_min = _optional_float(configured_model.get("temperature_ui_min"), 0.0)
    temperature_ui_max = _optional_float(configured_model.get("temperature_ui_max"), 2.0)
    provider_temperature_min = _optional_float(configured_model.get("provider_temperature_min"), temperature_ui_min)
    provider_temperature_max = _optional_float(configured_model.get("provider_temperature_max"), temperature_ui_max)
    authority = assess_model_authority(
        {
            **configured_model,
            "supports_tool_calls": has_structured_tool_surface(configured_model),
            "apply_patch_tool_type": apply_patch_tool_type,
        }
    )
    ui_warnings = list(configured_model.get("ui_warnings") or [])
    for warning in authority.ui_warnings:
        if warning not in ui_warnings:
            ui_warnings.append(warning)
    default_route = assess_default_route_verification(configured_model)
    default_multimodal_route = assess_default_route_verification(
        configured_model,
        require_image_input_verified=True,
    )
    execution_route = dict(configured_model.get("execution_route") or {})
    execution_driver = dict(execution_route.get("driver") or {})
    execution_authority = dict(execution_route.get("authority") or {})
    execution_evidence = dict(execution_route.get("evidence") or {})
    execution_route_default_eligible = bool(execution_route.get("default_route_eligible"))
    execution_route_blockers = _unique_strings(
        [
            *[str(item).strip() for item in list(execution_evidence.get("reasons") or []) if str(item or "").strip()],
            *([] if execution_route_default_eligible else ["execution_route_not_default_eligible"]),
        ]
    )
    execution_warning = str(configured_model.get("execution_route_warning") or "").strip()
    if execution_warning and execution_warning not in ui_warnings:
        ui_warnings.append(execution_warning)
    effective_default_route_verified = bool(default_route.get("verified", False)) and execution_route_default_eligible
    effective_default_multimodal_route_verified = (
        bool(default_multimodal_route.get("verified", False)) and execution_route_default_eligible
    )
    effective_default_route_blockers = _unique_strings(
        [
            *[str(item).strip() for item in list(default_route.get("reasons") or []) if str(item or "").strip()],
            *execution_route_blockers,
        ]
    )
    effective_default_multimodal_route_blockers = _unique_strings(
        [
            *[str(item).strip() for item in list(default_multimodal_route.get("reasons") or []) if str(item or "").strip()],
            *execution_route_blockers,
        ]
    )
    web_capabilities = resolved_web_capability_fields(configured_model)
    runtime_provider_contract = resolved_runtime_provider_contract_fields(
        {
            **configured_model,
            "id": model_id,
            "provider": provider_id,
            "native_model": native_model,
            "context_window": context_window,
            "auto_compact_token_limit": resolved_compact_limit,
            "tool_output_token_limit": truncation_limit,
            "input_modalities": input_modalities,
            "supported_reasoning_levels": efforts,
            "default_reasoning_level": default_effort,
            "native_supported_reasoning_levels": native_efforts,
            "native_default_reasoning_level": native_default_effort,
            "apply_patch_tool_type": apply_patch_tool_type,
            "web_search_tool_type": web_search_tool_type,
            "supports_parallel_tool_calls": bool(configured_model.get("supports_parallel_tool_calls", False)),
            "supports_mcp_tools": bool(configured_model.get("supports_mcp_tools", False)),
            "mcp_tool_call_policy": configured_model.get("mcp_tool_call_policy") or "unsupported",
            "mcp_smoke_status": configured_model.get("mcp_smoke_status") or "untested",
            "mcp_tool_argument_validation": configured_model.get("mcp_tool_argument_validation") or "unsupported",
            "codex_builtin_tools": dict(configured_model.get("codex_builtin_tools") or {}),
            "modality_limits": dict(configured_model.get("modality_limits") or {}),
        }
    )
    exported_default_effort = _catalog_export_reasoning_effort(default_effort) or default_effort
    exported_efforts = _catalog_export_reasoning_efforts(efforts)
    exported_native_efforts = _catalog_export_reasoning_efforts(native_efforts)
    exported_native_default_effort = _catalog_export_reasoning_effort(native_default_effort) or native_default_effort
    runtime_provider_contract = _catalog_export_runtime_provider_contract(runtime_provider_contract)
    return {
        "slug": model_id,
        "id": model_id,
        "display_name": display_name,
        "displayName": display_name,
        "description": "Third-party coding model routed through AstraBridge with conservative capabilities.",
        "default_reasoning_level": exported_default_effort,
        "native_supported_reasoning_levels": exported_native_efforts,
        "native_default_reasoning_level": exported_native_default_effort,
        "supported_reasoning_levels": [{"effort": effort, "description": effort} for effort in exported_efforts],
        "supportedReasoningEfforts": [{"reasoningEffort": effort, "description": effort} for effort in exported_efforts],
        "shell_type": "shell_command",
        "visibility": "list",
        "supported_in_api": True,
        "priority": 50,
        "additional_speed_tiers": [],
        "service_tiers": [],
        "default_service_tier": None,
        "availability_nux": None,
        "upgrade": None,
        "base_instructions": (
            "You are Codex running through AstraBridge. Follow the app-server developer instructions exactly. "
            "When tools are provided, use exact structured tool calls with valid JSON arguments instead of describing the tool call in prose. "
            "Use request_user_input for blocking user choices and update_plan for visible planning when those tools are available."
        ),
        "base_instructions_overrides": {},
        "model_messages": None,
        "supports_reasoning_summaries": bool(configured_model.get("supports_reasoning_summaries", False)),
        "default_reasoning_summary": configured_model.get("default_reasoning_summary") or "auto",
        "support_verbosity": bool(configured_model.get("support_verbosity", False)),
        "default_verbosity": configured_model.get("default_verbosity"),
        "apply_patch_tool_type": codex_apply_patch_tool_type,
        "web_search_tool_type": web_search_tool_type if web_search_tool_type in {"text", "text_and_image"} else "text",
        "truncation_policy": {"type": "tokens", "mode": "tokens", "limit": truncation_limit},
        "supports_parallel_tool_calls": bool(configured_model.get("supports_parallel_tool_calls", False)),
        "supports_image_detail_original": bool("image" in input_modalities and configured_model.get("supports_image_detail_original", False)),
        "context_window": context_window,
        "max_context_window": context_window,
        "auto_compact_token_limit": resolved_compact_limit,
        "effective_context_window_percent": int(configured_model.get("effective_context_window_percent") or DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT),
        "experimental_supported_tools": list(configured_model.get("experimental_supported_tools") or []),
        "supports_mcp_tools": bool(configured_model.get("supports_mcp_tools", False)),
        "mcp_tool_call_policy": configured_model.get("mcp_tool_call_policy") or "unsupported",
        "mcp_verified_servers": list(configured_model.get("mcp_verified_servers") or []),
        "mcp_smoke_status": configured_model.get("mcp_smoke_status") or "untested",
        "mcp_tool_argument_validation": configured_model.get("mcp_tool_argument_validation") or "unsupported",
        "codex_builtin_tools": dict(configured_model.get("codex_builtin_tools") or {}),
        "planner_support": dict(configured_model.get("planner_support") or {}),
        "goal_support": dict(configured_model.get("goal_support") or {}),
        "context_compaction_support": dict(configured_model.get("context_compaction_support") or {}),
        "modality_limits": dict(configured_model.get("modality_limits") or {}),
        "ui_warnings": ui_warnings,
        "authority_tier": authority.tier,
        "authority_reason": authority.reason,
        "execution_route": execution_route,
        "execution_route_status": str(execution_driver.get("admission") or "review_only"),
        "execution_route_driver": str(execution_driver.get("execution_id") or "preview_review"),
        "execution_route_configured_driver": str(execution_driver.get("configured_id") or "app_server"),
        "execution_route_authority_tier": str(execution_authority.get("effective_tier") or "C"),
        "execution_route_declared_authority_tier": str(execution_authority.get("declared_tier") or authority.tier),
        "execution_route_evidence_state": str(execution_evidence.get("effective_state") or "documented"),
        "execution_route_verification_status": str(execution_evidence.get("verification_status") or "missing"),
        "execution_route_blockers": execution_route_blockers,
        "execution_route_default_eligible": execution_route_default_eligible,
        "parallel_tool_call_status": authority.parallel_tool_call_status,
        "command_execution_status": authority.command_execution_status,
        "command_execution_note": authority.command_execution_note,
        "input_modalities": input_modalities,
        "inputModalities": input_modalities,
        "supports_search_tool": bool(configured_model.get("supports_search_tool", False)),
        **web_capabilities,
        "use_responses_lite": bool(configured_model.get("use_responses_lite", False)),
        "auto_review_model_override": configured_model.get("auto_review_model_override"),
        "tool_mode": configured_model.get("tool_mode"),
        "multi_agent_version": configured_model.get("multi_agent_version"),
        "temperature_default": temperature_default,
        "temperature_ui_min": temperature_ui_min,
        "temperature_ui_max": temperature_ui_max,
        "provider_temperature_min": provider_temperature_min,
        "provider_temperature_max": provider_temperature_max,
        "temperature_adapter_policy": configured_model.get("temperature_adapter_policy") or "pass_through_0_2",
        "source_urls": list(configured_model.get("source_urls") or []),
        "source_status": configured_model.get("source_status") or "seeded",
        "last_verified_at": configured_model.get("last_verified_at"),
        "verification_notes": configured_model.get("verification_notes") or "",
        "catalog_version": configured_model.get("catalog_version"),
        "default_route_verified": effective_default_route_verified,
        "default_route_status": "verified" if effective_default_route_verified else "warning_gated",
        "default_route_blockers": effective_default_route_blockers,
        "default_multimodal_route_verified": effective_default_multimodal_route_verified,
        "default_multimodal_route_status": "verified" if effective_default_multimodal_route_verified else "warning_gated",
        "default_multimodal_route_blockers": effective_default_multimodal_route_blockers,
        "recommended": bool(configured_model.get("recommended", False)) and effective_default_route_verified,
        "default_for_provider": bool(configured_model.get("default_for_provider", False)) and effective_default_route_verified,
        "deprecated": bool(configured_model.get("deprecated", False)),
        "deprecated_after": configured_model.get("deprecated_after"),
        "confidence": configured_model.get("confidence"),
        "source_provenance": dict(configured_model.get("source_provenance") or {}),
        "runtime_provider_contract": runtime_provider_contract,
    }


def catalog_entry_from_record(
    record: dict[str, Any],
    *,
    reasoning_effort: Any = None,
) -> dict[str, Any]:
    provider_id = str(record.get("provider") or "")
    native_model = str(record.get("native_model") or "")
    display_name = str(record.get("display_name") or native_model or record.get("id") or "")
    context_window = int(record.get("advertised_context_window") or known_context_window(provider_id, native_model) or 128_000)
    return model_catalog_entry(
        model_id=str(record.get("id") or f"{provider_id}/{native_model}"),
        provider_id=provider_id,
        native_model=native_model,
        display_name=display_name,
        context_window=context_window,
        reasoning_effort=reasoning_effort,
        configured_model=record,
        auto_compact_token_limit=_optional_positive_int(record.get("auto_compact_token_limit")),
    )


def _clean_string_list(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            text = str(item.get("effort") or item.get("reasoningEffort") or item.get("id") or "").strip()
        else:
            text = str(item or "").strip()
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _apply_patch_mapping_status(provider_value: Any, codex_value: str | None) -> str:
    normalized = str(provider_value or "").strip().lower()
    if not normalized and codex_value is None:
        return "disabled"
    if normalized == "freeform" and codex_value == "freeform":
        return "native_freeform"
    if normalized == "json" and codex_value == "freeform":
        return "json_to_codex_freeform"
    return "unsupported"


def _codex_apply_patch_tool_type(value: Any) -> str | None:
    normalized = normalize_apply_patch_tool_type(value)
    if normalized is not None:
        return "freeform"
    return None


def _codex_reasoning_effort(effort: Any) -> str:
    return normalize_reasoning_effort(effort, default="high") or "high"


def _codex_reasoning_efforts(efforts: list[str]) -> list[str]:
    return normalize_reasoning_efforts(efforts, default="high")


def _catalog_export_reasoning_effort(effort: Any) -> str | None:
    normalized = normalize_reasoning_effort(effort)
    if not normalized:
        normalized = str(effort or "").strip().lower()
    if not normalized:
        return None
    return APP_SERVER_REASONING_EFFORT_ALIASES.get(normalized, normalized)


def _catalog_export_reasoning_efforts(efforts: list[str]) -> list[str]:
    exported: list[str] = []
    seen: set[str] = set()
    for effort in efforts:
        normalized = _catalog_export_reasoning_effort(effort)
        if not normalized or normalized in seen:
            continue
        exported.append(normalized)
        seen.add(normalized)
    return exported


def _catalog_export_runtime_provider_contract(contract: dict[str, Any]) -> dict[str, Any]:
    exported = dict(contract)
    provider_metadata = dict(exported.get("provider_metadata") or {})
    if provider_metadata:
        provider_metadata["supported_reasoning_levels"] = _catalog_export_reasoning_efforts(
            list(provider_metadata.get("supported_reasoning_levels") or [])
        )
        provider_default = _catalog_export_reasoning_effort(provider_metadata.get("default_reasoning_level"))
        if provider_default:
            provider_metadata["default_reasoning_level"] = provider_default
        provider_metadata["native_supported_reasoning_levels"] = _catalog_export_reasoning_efforts(
            list(provider_metadata.get("native_supported_reasoning_levels") or [])
        )
        native_provider_default = _catalog_export_reasoning_effort(provider_metadata.get("native_default_reasoning_level"))
        if native_provider_default:
            provider_metadata["native_default_reasoning_level"] = native_provider_default
        exported["provider_metadata"] = provider_metadata
    codex_runtime_metadata = dict(exported.get("codex_runtime_metadata") or {})
    if codex_runtime_metadata:
        codex_runtime_metadata["supported_reasoning_levels"] = _catalog_export_reasoning_efforts(
            list(codex_runtime_metadata.get("supported_reasoning_levels") or [])
        )
        codex_default = _catalog_export_reasoning_effort(codex_runtime_metadata.get("default_reasoning_level"))
        if codex_default:
            codex_runtime_metadata["default_reasoning_level"] = codex_default
        exported["codex_runtime_metadata"] = codex_runtime_metadata
    capability_metadata = dict(exported.get("capability_metadata") or {})
    reasoning_effort = dict(capability_metadata.get("reasoning_effort") or {})
    if reasoning_effort:
        reasoning_effort["provider_values"] = _catalog_export_reasoning_efforts(list(reasoning_effort.get("provider_values") or []))
        reasoning_effort["codex_values"] = _catalog_export_reasoning_efforts(list(reasoning_effort.get("codex_values") or []))
        provider_default = _catalog_export_reasoning_effort(reasoning_effort.get("provider_default"))
        if provider_default:
            reasoning_effort["provider_default"] = provider_default
        codex_default = _catalog_export_reasoning_effort(reasoning_effort.get("codex_default"))
        if codex_default:
            reasoning_effort["codex_default"] = codex_default
        reasoning_effort["native_provider_values"] = _catalog_export_reasoning_efforts(
            list(reasoning_effort.get("native_provider_values") or [])
        )
        native_provider_default = _catalog_export_reasoning_effort(reasoning_effort.get("native_provider_default"))
        if native_provider_default:
            reasoning_effort["native_provider_default"] = native_provider_default
        capability_metadata["reasoning_effort"] = reasoning_effort
        exported["capability_metadata"] = capability_metadata
    return exported


def _native_reasoning_effort(effort: Any) -> str | None:
    text = str(effort or "").strip().lower()
    return text or None


def _optional_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _provider_model_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        0 if bool(item.get("recommended", False)) else 1,
        0 if bool(item.get("default_for_provider", False)) else 1,
        1 if bool(item.get("deprecated", False)) else 0,
    )


def _merge_generated_and_configured_model(
    generated_model: dict[str, Any],
    *configured_models: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(generated_model)
    for configured in configured_models:
        if not configured:
            continue
        for key in CONFIGURED_MODEL_RUNTIME_OVERRIDE_FIELDS:
            if key in configured:
                merged[key] = configured[key]
        for key, value in configured.items():
            if key not in merged:
                merged[key] = value
    return merged


def _provider_default_model_record(provider: dict[str, Any], configured_default_model: str | None) -> dict[str, Any]:
    provider_id = str(provider.get("id") or provider.get("provider_id") or "").strip()
    native_model = str(configured_default_model or "").strip()
    if not provider_id or not native_model:
        return {}
    capabilities = dict(provider.get("capabilities") or {})
    return {
        "id": f"{provider_id}/{native_model}",
        "provider": provider_id,
        "native_model": native_model,
        "supported_reasoning_levels": list(provider.get("supported_reasoning_levels") or []),
        "default_reasoning_level": provider.get("default_reasoning_level"),
        "native_supported_reasoning_levels": list(provider.get("native_supported_reasoning_levels") or []),
        "native_default_reasoning_level": provider.get("native_default_reasoning_level"),
        "input_modalities": list(provider.get("input_modalities") or []),
        "tool_mode": provider.get("tool_mode"),
        "model_kind": provider.get("model_kind") or "chat",
        "apply_patch_tool_type": provider.get("apply_patch_tool_type"),
        "web_search_tool_type": provider.get("web_search_tool_type"),
        "supports_parallel_tool_calls": capabilities.get("supports_parallel_tool_calls", False),
        "supports_search_tool": provider.get("supports_search_tool", False),
        "supports_mcp_tools": provider.get("supports_mcp_tools", False),
        "mcp_tool_call_policy": provider.get("mcp_tool_call_policy"),
        "mcp_verified_servers": list(provider.get("mcp_verified_servers") or []),
        "mcp_smoke_status": provider.get("mcp_smoke_status"),
        "mcp_tool_argument_validation": provider.get("mcp_tool_argument_validation"),
        "native_web_search_support": provider.get("native_web_search_support"),
        "tool_web_search_support": provider.get("tool_web_search_support"),
        "mcp_web_support": provider.get("mcp_web_support"),
        "web_smoke_status": provider.get("web_smoke_status"),
        "citation_quality": provider.get("citation_quality"),
        "advertised_context_window": provider.get("advertised_context_window") or provider.get("max_context_tokens") or capabilities.get("max_context_tokens"),
        "effective_context_window_percent": provider.get("effective_context_window_percent"),
        "auto_compact_token_limit": provider.get("auto_compact_token_limit"),
        "tool_output_token_limit": provider.get("tool_output_token_limit"),
        "supports_image_detail_original": provider.get("supports_image_detail_original", False),
        "context_compaction_support": dict(provider.get("context_compaction_support") or {}),
        "planner_support": dict(provider.get("planner_support") or {}),
        "goal_support": dict(provider.get("goal_support") or {}),
        "codex_builtin_tools": dict(provider.get("codex_builtin_tools") or {}),
        "experimental_supported_tools": list(provider.get("experimental_supported_tools") or []),
    }


def _profile_for(provider_id: str, model: str) -> Any | None:
    for candidate in (provider_id, model, f"{provider_id} {model}"):
        text = str(candidate or "").strip()
        if not text:
            continue
        try:
            return get_provider_profile(resolve_provider_id(text))
        except ValueError:
            continue
    return None
