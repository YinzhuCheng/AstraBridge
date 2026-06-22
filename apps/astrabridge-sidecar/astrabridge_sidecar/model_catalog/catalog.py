from __future__ import annotations

from typing import Any

from ..providers import get_provider_profile, resolve_provider_id
from ..providers.tooling import assess_model_authority


CODEX_CLI_BASELINE = "0.137.0"
DEFAULT_EFFECTIVE_CONTEXT_WINDOW_PERCENT = 80
ASTRABRIDGE_MODEL_CATALOG_FILENAME = "astrabridge-models.json"
ASTRABRIDGE_MODELS_CACHE_FILENAME = "astrabridge-models-cache.json"


def known_context_window(provider_id: str, model: str) -> int | None:
    profile = _profile_for(provider_id, model)
    if profile and profile.context_window():
        return int(profile.context_window() or 0) or None
    provider = provider_id.lower()
    native_model = model.lower()
    if "deepseek" in provider or "deepseek" in native_model:
        return 1_000_000 if "v4" in native_model else 128_000
    if "kimi" in provider or "kimi" in native_model or "moonshot" in provider:
        return 256_000
    if "glm" in provider or "zai" in provider or "zhipu" in provider or "glm" in native_model:
        return 1_000_000 if "5.2" in native_model else 128_000
    if "qwen" in provider or "dashscope" in provider or "qwen" in native_model:
        return 1_000_000 if any(token in native_model for token in ("3.7", "coder", "long", "plus", "flash")) else 262_144
    if "gpt-5.5" in native_model or "gpt-5.4" in native_model:
        return 1_000_000
    if "gpt-5" in native_model:
        return 400_000
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
    signals = f"{provider_id} {model}".lower()
    if ("kimi" in signals or "moonshot" in signals) and any(
        token in signals for token in ("kimi-k2.7", "kimi-k2.6", "k2.6", "kimi-k2.5", "k2.5", "vision", "visual")
    ):
        return ["text", "image"]
    if "glm" in signals or "zai" in signals or "zhipu" in signals:
        if any(token in signals for token in ("5.2", "4.1v", "4.5", "vision", "visual")):
            return ["text", "image"]
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
    efforts = configured_efforts or known_reasoning_efforts(provider_id, native_model)
    default_effort = (
        _codex_reasoning_effort(reasoning_effort)
        if reasoning_effort
        else str(configured_model.get("default_reasoning_level") or "").strip()
        or (profile.default_reasoning_level() if profile else "")
        or (efforts[-1] if efforts else None)
    )
    resolved_compact_limit = compact_limit(context_window, auto_compact_token_limit)
    truncation_limit = int(configured_model.get("tool_output_token_limit") or tool_output_truncation_limit(context_window))
    input_modalities = normalize_input_modalities(configured_model.get("input_modalities"), provider_id, native_model)
    apply_patch_tool_type = configured_model.get("apply_patch_tool_type")
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
        "apply_patch_tool_type": apply_patch_tool_type if apply_patch_tool_type in {"freeform", "json"} else None,
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
        "native_web_search_support": configured_model.get("native_web_search_support") or "unverified",
        "tool_web_search_support": configured_model.get("tool_web_search_support") or "unverified",
        "mcp_web_support": configured_model.get("mcp_web_support") or "unverified",
        "web_smoke_status": configured_model.get("web_smoke_status") or "untested",
        "citation_quality": configured_model.get("citation_quality") or "untested",
        "last_web_verified_at": configured_model.get("last_web_verified_at"),
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
    }


def _codex_reasoning_effort(effort: Any) -> str:
    normalized = str(effort or "high").strip().lower()
    if normalized == "max":
        return "xhigh"
    if normalized in {"off", "auto", "minimal", "low", "medium", "high", "xhigh", "none"}:
        return normalized
    return "high"


def _optional_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed


def _profile_for(provider_id: str, model: str) -> Any | None:
    for candidate in (provider_id, model, f"{provider_id} {model}"):
        text = str(candidate or "").strip()
        if not text:
            continue
        try:
            return get_provider_profile(resolve_provider_id(text))
        except ValueError:
            lowered = text.lower()
            if "deepseek" in lowered:
                return get_provider_profile("deepseek")
            if "kimi" in lowered or "moonshot" in lowered:
                return get_provider_profile("kimi")
            if "qwen" in lowered or "dashscope" in lowered:
                return get_provider_profile("qwen")
            if any(token in lowered for token in ("glm", "zai", "zhipu", "bigmodel")):
                return get_provider_profile("glm")
            if "yunwu" in lowered:
                return get_provider_profile("yunwu")
            if "openai" in lowered or "gpt-" in lowered:
                return get_provider_profile("openai")
    return None
