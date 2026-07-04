from __future__ import annotations

from typing import Any

from ..providers import get_provider_profile, resolve_provider_id
from ..providers.tooling import assess_model_authority


CODEX_CLI_BASELINE = "0.137.0"
DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT = 80
ASTRABRIDGE_MODEL_CATALOG_FILENAME = "astrabridge-models.json"
ASTRABRIDGE_MODELS_CACHE_FILENAME = "astrabridge-models-cache.json"
PROFILE_MODEL_RESERVED_FIELDS = {"id", "provider", "native_model", "display_name", "displayName"}
RUNTIME_PROVIDER_CONTRACT_SCHEMA_VERSION = "astrabridge-runtime-provider-contract-v1"
RUNTIME_PROVIDER_CONTRACT_AUDIT_FIELDS = (
    "reasoning_effort",
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
    if isinstance(value, list):
        normalized = [str(item).strip().lower() for item in value if str(item).strip()]
        allowed = [item for item in normalized if item in {"text", "image"}]
        if allowed:
            if known:
                allowed = [*allowed, *[item for item in known if item not in allowed]]
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
        effective = {**item, **configured_by_key.get(model_key, {}), **configured_by_id.get(model_id, {})}
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


def resolved_runtime_provider_contract_fields(model: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(model.get("provider") or model.get("provider_id") or "").strip()
    native_model = str(model.get("native_model") or model.get("model") or "").strip()
    model_id = str(model.get("id") or "").strip() or (f"{provider_id}/{native_model}" if provider_id and native_model else native_model)
    provider_efforts = _clean_string_list(model.get("supported_reasoning_levels"))
    if not provider_efforts:
        provider_efforts = known_reasoning_efforts(provider_id, native_model)
    codex_efforts = _codex_reasoning_efforts(provider_efforts)
    provider_default_effort = str(model.get("default_reasoning_level") or model.get("reasoning_effort") or "").strip()
    codex_default_effort = _codex_reasoning_effort(provider_default_effort or (codex_efforts[-1] if codex_efforts else "high"))
    if codex_default_effort not in codex_efforts:
        codex_efforts = [*codex_efforts, codex_default_effort]

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
    auto_compact_token_limit = _optional_positive_int(model.get("auto_compact_token_limit"))
    tool_output_token_limit = _optional_positive_int(model.get("tool_output_token_limit"))
    if context_window and not auto_compact_token_limit:
        auto_compact_token_limit = compact_limit(context_window)
    if context_window and not tool_output_token_limit:
        tool_output_token_limit = tool_output_truncation_limit(context_window)
    supports_mcp_tools = bool(model.get("supports_mcp_tools", False))
    mcp_tool_call_policy = str(model.get("mcp_tool_call_policy") or "unsupported")
    supports_parallel = bool(model.get("supports_parallel_tool_calls", False))
    supports_image_detail_original = bool("image" in input_modalities and model.get("supports_image_detail_original", False))
    authority = assess_model_authority(
        {
            **model,
            "supports_tool_calls": bool(supports_mcp_tools or apply_patch_tool_type),
            "supports_parallel_tool_calls": supports_parallel,
            "apply_patch_tool_type": apply_patch_tool_type,
        }
    )
    web_capabilities = resolved_web_capability_fields(model, mcp_fallback_to_smoke=True)
    workflow_contract = resolved_workflow_contract_fields(model, modalities_default=",".join(input_modalities))

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
            "auto_compact_token_limit": auto_compact_token_limit,
            "tool_output_token_limit": tool_output_token_limit,
        },
        "capability_metadata": {
            "reasoning_effort": {
                "provider_values": provider_efforts,
                "codex_values": codex_efforts,
                "provider_default": provider_default_effort or None,
                "codex_default": codex_default_effort,
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
    default_effort_raw = (
        _codex_reasoning_effort(reasoning_effort)
        if reasoning_effort
        else str(configured_model.get("default_reasoning_level") or "").strip()
        or (profile.default_reasoning_level() if profile else "")
        or (efforts[-1] if efforts else None)
    )
    default_effort = _codex_reasoning_effort(default_effort_raw)
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
            "supports_tool_calls": bool(configured_model.get("supports_mcp_tools", False) or apply_patch_tool_type),
            "apply_patch_tool_type": apply_patch_tool_type,
        }
    )
    ui_warnings = list(configured_model.get("ui_warnings") or [])
    for warning in authority.ui_warnings:
        if warning not in ui_warnings:
            ui_warnings.append(warning)
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
    return {
        "slug": model_id,
        "id": model_id,
        "display_name": display_name,
        "displayName": display_name,
        "description": "Third-party coding model routed through AstraBridge with conservative capabilities.",
        "default_reasoning_level": default_effort,
        "supported_reasoning_levels": [{"effort": effort, "description": effort} for effort in efforts],
        "supportedReasoningEfforts": [{"reasoningEffort": effort, "description": effort} for effort in efforts],
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
        "parallel_tool_call_status": authority.parallel_tool_call_status,
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
        "recommended": bool(configured_model.get("recommended", False)),
        "default_for_provider": bool(configured_model.get("default_for_provider", False)),
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
    normalized = str(value or "").strip().lower()
    if normalized in {"freeform", "json"}:
        return "freeform"
    return None


def _codex_reasoning_effort(effort: Any) -> str:
    normalized = str(effort or "high").strip().lower()
    if normalized == "max":
        return "xhigh"
    if normalized in {"off", "auto", "minimal", "low", "medium", "high", "xhigh", "none"}:
        return normalized
    return "high"


def _codex_reasoning_efforts(efforts: list[str]) -> list[str]:
    normalized: list[str] = []
    for effort in efforts:
        codex_effort = _codex_reasoning_effort(effort)
        if codex_effort not in normalized:
            normalized.append(codex_effort)
    return normalized or ["high"]


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


def _provider_model_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    return (
        0 if bool(item.get("default_for_provider", False)) else 1,
        0 if bool(item.get("recommended", False)) else 1,
        1 if bool(item.get("deprecated", False)) else 0,
    )


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
