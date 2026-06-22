from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AuthSpec:
    type: Literal["api_key", "none"]
    env_vars: tuple[str, ...]
    secret_name: str | None = None


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_streaming: bool
    supports_tool_calls: bool
    supports_parallel_tool_calls: bool
    supports_vision: bool
    supports_tool_result_images: bool
    supports_reasoning: bool
    supports_reasoning_replay: bool
    supports_prompt_cache: bool
    max_context_tokens: int | None = None
    max_output_tokens: int | None = None


@dataclass(frozen=True)
class ReasoningPolicy:
    mode: Literal[
        "none",
        "reasoning_effort",
        "enable_thinking",
        "reasoning_content",
        "openai_responses",
    ]
    allow_cross_provider_replay: bool
    preserve_for_tool_turns: bool = False
    supported_levels: tuple[str, ...] = ("low", "medium", "high", "xhigh")
    default_level: str = "high"


@dataclass(frozen=True)
class EditPolicy:
    small: Literal["patch", "replace", "structured_edit", "propose_only"]
    medium: Literal["patch", "replace", "structured_edit", "propose_only"]
    large: Literal["patch", "replace", "structured_edit", "propose_only"]


@dataclass(frozen=True)
class ToolPolicy:
    apply_patch_tool_type: Literal["freeform", "json"] | None = None
    web_search_tool_type: Literal["text", "text_and_image"] = "text"
    supports_search_tool: bool = False
    supports_mcp_tools: bool = False
    mcp_tool_call_policy: str = "unsupported"
    mcp_verified_servers: tuple[str, ...] = ()
    mcp_smoke_status: str = "untested"
    mcp_tool_argument_validation: str = "unsupported"
    native_web_search_support: str = "unverified"
    tool_web_search_support: str = "unverified"
    mcp_web_support: str = "unverified"
    web_smoke_status: str = "untested"
    citation_quality: str = "untested"


@dataclass(frozen=True)
class ContextPolicy:
    default_input_modalities: tuple[str, ...] = ("text",)
    advertised_context_window: int | None = None
    effective_context_window_percent: int = 80
    auto_compact_token_limit: int | None = None
    tool_output_token_limit: int | None = None
    supports_image_detail_original: bool = False


@dataclass(frozen=True)
class FallbackPolicy:
    fallback_models: tuple[str, ...] = ()
    downgrade_reasoning_levels: tuple[str, ...] = ()
    drop_unsupported_modalities: bool = True


@dataclass(frozen=True)
class ProviderSafetyPolicy:
    temperature_default: float = 0.0
    temperature_ui_min: float = 0.0
    temperature_ui_max: float = 2.0
    provider_temperature_min: float = 0.0
    provider_temperature_max: float = 2.0
    temperature_adapter_policy: str = "pass_through_0_2"
    secret_scope: Literal["provider_only", "shared_runtime"] = "provider_only"


@dataclass(frozen=True)
class ProviderProfile:
    id: str
    display_name: str
    aliases: tuple[str, ...]
    auth: AuthSpec
    base_url: str
    protocol: str
    models_url: str | None
    default_model: str
    fallback_models: tuple[str, ...]
    capabilities: ProviderCapabilities
    reasoning_policy: ReasoningPolicy
    tool_policy: ToolPolicy
    edit_policy: EditPolicy
    context_policy: ContextPolicy
    fallback_policy: FallbackPolicy
    safety_policy: ProviderSafetyPolicy

    def adapter_type(self) -> str:
        return "responses" if self.protocol in {"responses", "qwen_responses"} else "chat"

    def primary_env_key(self) -> str:
        return self.auth.env_vars[0] if self.auth.env_vars else "OPENAI_API_KEY"

    def to_catalog_provider(self) -> dict[str, object]:
        return {
            "id": self.id,
            "provider_id": self.id,
            "display_name": self.display_name,
            "enabled": True,
            "adapter_type": self.adapter_type(),
            "base_url": self.base_url,
            "default_model": self.default_model,
            "env_key": self.primary_env_key(),
            "auth_mode": "env_ref",
            "proxy_mode": "direct",
            "proxy_url": "",
            "models_url": self.models_url,
            "protocol": self.protocol,
            "fallback_models": list(self.fallback_models),
            **self.provider_metadata_payload(),
        }

    def to_router_provider(self) -> dict[str, object]:
        return dict(self.to_catalog_provider())

    def to_default_profile(self) -> dict[str, object]:
        env_key = self.primary_env_key()
        profile_id = "openai-compatible" if self.id == "openai" else f"{self.id}-default"
        label = "OpenAI" if self.id == "openai" else self.display_name
        return {
            "profile_id": profile_id,
            "label": label,
            "type": "custom_provider",
            "provider_id": self.id,
            "base_url": self.base_url,
            "model": self.default_model,
            "reasoning_effort": self.default_profile_reasoning_effort(),
            "wire_api": self.adapter_type(),
            "env_key": env_key,
            "auth_mode": "env_ref",
            "secret_ref": f"env:{env_key}",
            "proxy_mode": "direct",
            "proxy_url": "",
            **self.profile_metadata_payload(),
        }

    def capability_payload(self) -> dict[str, object]:
        return {
            "supports_streaming": self.capabilities.supports_streaming,
            "supports_tool_calls": self.capabilities.supports_tool_calls,
            "supports_parallel_tool_calls": self.capabilities.supports_parallel_tool_calls,
            "supports_vision": self.capabilities.supports_vision,
            "supports_tool_result_images": self.capabilities.supports_tool_result_images,
            "supports_reasoning": self.capabilities.supports_reasoning,
            "supports_reasoning_replay": self.capabilities.supports_reasoning_replay,
            "supports_prompt_cache": self.capabilities.supports_prompt_cache,
            "max_context_tokens": self.capabilities.max_context_tokens,
            "max_output_tokens": self.capabilities.max_output_tokens,
            "input_modalities": list(self.context_policy.default_input_modalities),
        }

    def provider_metadata_payload(self) -> dict[str, object]:
        return {
            "supported_reasoning_levels": list(self.reasoning_levels()),
            "default_reasoning_level": self.default_reasoning_level(),
            "reasoning_policy_mode": self.reasoning_policy.mode,
            "edit_policy": self.edit_policy_payload(),
            "capabilities": self.capability_payload(),
            "fallback_models": list(self.fallback_policy.fallback_models or self.fallback_models),
            "temperature_default": self.safety_policy.temperature_default,
            "temperature_ui_min": self.safety_policy.temperature_ui_min,
            "temperature_ui_max": self.safety_policy.temperature_ui_max,
            "provider_temperature_min": self.safety_policy.provider_temperature_min,
            "provider_temperature_max": self.safety_policy.provider_temperature_max,
            "temperature_adapter_policy": self.safety_policy.temperature_adapter_policy,
            "effective_context_window_percent": self.context_policy.effective_context_window_percent,
            "auto_compact_token_limit": self.context_policy.auto_compact_token_limit,
            "tool_output_token_limit": self.context_policy.tool_output_token_limit,
            "supports_image_detail_original": self.context_policy.supports_image_detail_original,
            "downgrade_reasoning_levels": list(self.fallback_policy.downgrade_reasoning_levels),
            "drop_unsupported_modalities": self.fallback_policy.drop_unsupported_modalities,
        }

    def edit_policy_payload(self) -> dict[str, str]:
        return {
            "small": self.edit_policy.small,
            "medium": self.edit_policy.medium,
            "large": self.edit_policy.large,
        }

    def reasoning_levels(self) -> tuple[str, ...]:
        levels = tuple(str(item).strip().lower() for item in self.reasoning_policy.supported_levels if str(item).strip())
        return levels or ("high",)

    def default_reasoning_level(self) -> str:
        preferred = str(self.reasoning_policy.default_level or "").strip().lower()
        if preferred:
            return preferred
        return self.reasoning_levels()[-1]

    def default_profile_reasoning_effort(self) -> str:
        preferred = self.default_reasoning_level()
        return preferred if preferred not in {"none"} else "high"

    def context_window(self) -> int | None:
        return self.context_policy.advertised_context_window or self.capabilities.max_context_tokens

    def to_model_defaults(self) -> dict[str, object]:
        return {
            "advertised_context_window": self.context_window(),
            "input_modalities": list(self.context_policy.default_input_modalities),
            "supported_reasoning_levels": list(self.reasoning_levels()),
            "default_reasoning_level": self.default_reasoning_level(),
            "supports_parallel_tool_calls": self.capabilities.supports_parallel_tool_calls,
            "supports_search_tool": self.tool_policy.supports_search_tool,
            "native_web_search_support": self.tool_policy.native_web_search_support,
            "tool_web_search_support": self.tool_policy.tool_web_search_support,
            "mcp_web_support": self.tool_policy.mcp_web_support,
            "web_smoke_status": self.tool_policy.web_smoke_status,
            "citation_quality": self.tool_policy.citation_quality,
            "apply_patch_tool_type": self.tool_policy.apply_patch_tool_type,
            "web_search_tool_type": self.tool_policy.web_search_tool_type,
            "supports_mcp_tools": self.tool_policy.supports_mcp_tools,
            "mcp_tool_call_policy": self.tool_policy.mcp_tool_call_policy,
            "mcp_verified_servers": list(self.tool_policy.mcp_verified_servers),
            "mcp_smoke_status": self.tool_policy.mcp_smoke_status,
            "mcp_tool_argument_validation": self.tool_policy.mcp_tool_argument_validation,
            "supports_image_detail_original": self.context_policy.supports_image_detail_original,
            "effective_context_window_percent": self.context_policy.effective_context_window_percent,
            "auto_compact_token_limit": self.context_policy.auto_compact_token_limit,
            "tool_output_token_limit": self.context_policy.tool_output_token_limit,
            "temperature_default": self.safety_policy.temperature_default,
            "temperature_ui_min": self.safety_policy.temperature_ui_min,
            "temperature_ui_max": self.safety_policy.temperature_ui_max,
            "provider_temperature_min": self.safety_policy.provider_temperature_min,
            "provider_temperature_max": self.safety_policy.provider_temperature_max,
            "temperature_adapter_policy": self.safety_policy.temperature_adapter_policy,
            "source_status": "provider_profile",
            "provider_profile_id": self.id,
        }

    def default_model_config(self) -> dict[str, object]:
        return self.to_model_defaults()

    def profile_metadata_payload(self) -> dict[str, object]:
        blocked = {"auto_compact_token_limit", "tool_output_token_limit"}
        return {
            **self.provider_metadata_payload(),
            **{key: value for key, value in self.to_model_defaults().items() if key not in blocked},
        }
