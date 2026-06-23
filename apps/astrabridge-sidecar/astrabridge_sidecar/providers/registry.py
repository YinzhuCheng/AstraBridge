from __future__ import annotations

from .profile import (
    AuthSpec,
    ContextPolicy,
    EditPolicy,
    FallbackPolicy,
    ProviderCapabilities,
    ProviderProfile,
    ProviderSafetyPolicy,
    ReasoningPolicy,
    ToolPolicy,
)


PATCH_FRIENDLY_EDIT_POLICY = EditPolicy(small="patch", medium="patch", large="replace")
STRUCTURED_EDIT_POLICY = EditPolicy(small="patch", medium="structured_edit", large="replace")
DEFAULT_TOOL_POLICY = ToolPolicy()
DEEPSEEK_TOOL_POLICY = ToolPolicy(
    supports_mcp_tools=True,
    mcp_tool_call_policy="conservative",
    mcp_verified_servers=("astrabridge_web",),
    mcp_smoke_status="pass_direct_tool_call",
    mcp_tool_argument_validation="router_repair",
    tool_web_search_support="verified",
    mcp_web_support="verified_astrabridge_web",
    web_smoke_status="pass_direct_tool_call",
    citation_quality="requires_explicit_url_instruction",
)


_PROFILES: tuple[ProviderProfile, ...] = (
    ProviderProfile(
        id="openai",
        display_name="OpenAI",
        aliases=("openai_api_key",),
        auth=AuthSpec(type="api_key", env_vars=("OPENAI_API_KEY",), secret_name="openai"),
        base_url="https://api.openai.com/v1",
        protocol="responses",
        models_url="https://api.openai.com/v1/models",
        default_model="gpt-5.5",
        fallback_models=("gpt-5.5",),
        capabilities=ProviderCapabilities(True, True, False, False, False, True, False, False, 1_000_000, 128_000),
        reasoning_policy=ReasoningPolicy(
            mode="openai_responses",
            allow_cross_provider_replay=False,
            supported_levels=("none", "low", "medium", "high", "xhigh"),
            default_level="high",
        ),
        tool_policy=DEFAULT_TOOL_POLICY,
        edit_policy=PATCH_FRIENDLY_EDIT_POLICY,
        context_policy=ContextPolicy(advertised_context_window=1_000_000),
        fallback_policy=FallbackPolicy(fallback_models=("gpt-5.5",)),
        safety_policy=ProviderSafetyPolicy(),
    ),
    ProviderProfile(
        id="yunwu",
        display_name="Yunwu",
        aliases=(),
        auth=AuthSpec(type="api_key", env_vars=("YUNWU_API_KEY",), secret_name="yunwu"),
        base_url="https://yunwu.ai/v1",
        protocol="responses",
        models_url=None,
        default_model="gpt-5.5",
        fallback_models=("gpt-5.5",),
        capabilities=ProviderCapabilities(True, True, False, False, False, True, False, False, 1_000_000, 128_000),
        reasoning_policy=ReasoningPolicy(
            mode="openai_responses",
            allow_cross_provider_replay=False,
            supported_levels=("none", "low", "medium", "high", "xhigh"),
            default_level="high",
        ),
        tool_policy=DEFAULT_TOOL_POLICY,
        edit_policy=PATCH_FRIENDLY_EDIT_POLICY,
        context_policy=ContextPolicy(advertised_context_window=1_000_000),
        fallback_policy=FallbackPolicy(fallback_models=("gpt-5.5",)),
        safety_policy=ProviderSafetyPolicy(),
    ),
    ProviderProfile(
        id="deepseek",
        display_name="DeepSeek",
        aliases=(),
        auth=AuthSpec(type="api_key", env_vars=("DEEPSEEK_API_KEY",), secret_name="deepseek"),
        base_url="https://api.deepseek.com",
        protocol="chat",
        models_url="https://api.deepseek.com/models",
        default_model="deepseek-v4-pro",
        fallback_models=("deepseek-v4-pro", "deepseek-v4-flash"),
        capabilities=ProviderCapabilities(True, True, False, False, False, True, False, False, 1_000_000, 64_000),
        reasoning_policy=ReasoningPolicy(
            mode="reasoning_content",
            allow_cross_provider_replay=False,
            preserve_for_tool_turns=True,
            supported_levels=("high", "xhigh", "max"),
            default_level="xhigh",
        ),
        tool_policy=DEEPSEEK_TOOL_POLICY,
        edit_policy=PATCH_FRIENDLY_EDIT_POLICY,
        context_policy=ContextPolicy(advertised_context_window=1_000_000),
        fallback_policy=FallbackPolicy(fallback_models=("deepseek-v4-pro", "deepseek-v4-flash"), downgrade_reasoning_levels=("xhigh", "high")),
        safety_policy=ProviderSafetyPolicy(),
    ),
    ProviderProfile(
        id="qwen",
        display_name="Qwen / DashScope",
        aliases=("dashscope",),
        auth=AuthSpec(type="api_key", env_vars=("DASHSCOPE_API_KEY",), secret_name="qwen"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        protocol="qwen_responses",
        models_url="https://dashscope.aliyuncs.com/compatible-mode/v1/models",
        default_model="qwen3.7-plus",
        fallback_models=("qwen3.7-plus", "qwen3.7-max-2026-06-08", "qwen3.6-flash"),
        capabilities=ProviderCapabilities(True, True, False, False, False, True, False, False, 1_000_000, 64_000),
        reasoning_policy=ReasoningPolicy(
            mode="enable_thinking",
            allow_cross_provider_replay=False,
            supported_levels=("low", "medium", "high", "xhigh"),
            default_level="high",
        ),
        tool_policy=DEFAULT_TOOL_POLICY,
        edit_policy=STRUCTURED_EDIT_POLICY,
        context_policy=ContextPolicy(advertised_context_window=1_000_000),
        fallback_policy=FallbackPolicy(fallback_models=("qwen3.7-plus", "qwen3.7-max-2026-06-08", "qwen3.6-flash")),
        safety_policy=ProviderSafetyPolicy(
            provider_temperature_min=0.00001,
            provider_temperature_max=1.0,
            temperature_adapter_policy="qwen_omit_zero_clamp_1",
        ),
    ),
    ProviderProfile(
        id="kimi",
        display_name="Kimi",
        aliases=("moonshot",),
        auth=AuthSpec(type="api_key", env_vars=("KIMI_API_KEY",), secret_name="kimi"),
        base_url="https://api.moonshot.cn/v1",
        protocol="chat",
        models_url="https://api.moonshot.cn/v1/models",
        default_model="kimi-k2.7-code",
        fallback_models=("kimi-k2.7-code", "kimi-k2.6"),
        capabilities=ProviderCapabilities(True, True, False, True, False, True, False, False, 256_000, 32_768),
        reasoning_policy=ReasoningPolicy(
            mode="reasoning_content",
            allow_cross_provider_replay=False,
            preserve_for_tool_turns=True,
            supported_levels=("low", "medium", "high", "xhigh"),
            default_level="high",
        ),
        tool_policy=DEFAULT_TOOL_POLICY,
        edit_policy=STRUCTURED_EDIT_POLICY,
        context_policy=ContextPolicy(default_input_modalities=("text", "image"), advertised_context_window=256_000),
        fallback_policy=FallbackPolicy(fallback_models=("kimi-k2.7-code", "kimi-k2.6")),
        safety_policy=ProviderSafetyPolicy(
            temperature_default=1.0,
            temperature_ui_min=1.0,
            temperature_ui_max=1.0,
            provider_temperature_min=1.0,
            provider_temperature_max=1.0,
            temperature_adapter_policy="kimi_only_temperature_1",
        ),
    ),
    ProviderProfile(
        id="glm",
        display_name="GLM / Z.AI",
        aliases=("zai", "z-ai", "zhipu", "bigmodel"),
        auth=AuthSpec(type="api_key", env_vars=("GLM_API_KEY", "ZAI_API_KEY", "ZHIPU_API_KEY"), secret_name="glm"),
        base_url="https://open.bigmodel.cn/api/paas/v4",
        protocol="chat",
        models_url="https://open.bigmodel.cn/api/paas/v4/models",
        default_model="glm-5.2",
        fallback_models=("glm-5.2",),
        capabilities=ProviderCapabilities(True, True, False, True, False, True, False, False, 1_000_000, 32_768),
        reasoning_policy=ReasoningPolicy(
            mode="reasoning_effort",
            allow_cross_provider_replay=False,
            supported_levels=("low", "medium", "high", "xhigh"),
            default_level="high",
        ),
        tool_policy=DEFAULT_TOOL_POLICY,
        edit_policy=STRUCTURED_EDIT_POLICY,
        context_policy=ContextPolicy(default_input_modalities=("text", "image"), advertised_context_window=1_000_000),
        fallback_policy=FallbackPolicy(fallback_models=("glm-5.2",)),
        safety_policy=ProviderSafetyPolicy(),
    ),
)


_BY_ID = {profile.id: profile for profile in _PROFILES}
_ALIASES = {alias: profile.id for profile in _PROFILES for alias in profile.aliases}


def resolve_provider_id(provider_id: str | None) -> str:
    candidate = str(provider_id or "").strip().lower()
    if not candidate:
        raise ValueError("provider_id is required.")
    if candidate in _BY_ID:
        return candidate
    if candidate in _ALIASES:
        return _ALIASES[candidate]
    raise ValueError(f"Unknown provider id: {provider_id}")


def get_provider_profile(provider_id: str | None) -> ProviderProfile:
    return _BY_ID[resolve_provider_id(provider_id)]


def all_provider_profiles() -> list[ProviderProfile]:
    return list(_PROFILES)


def default_profiles() -> list[dict[str, object]]:
    return [profile.to_default_profile() for profile in _PROFILES]
