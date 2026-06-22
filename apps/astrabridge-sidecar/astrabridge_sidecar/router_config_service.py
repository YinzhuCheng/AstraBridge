from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import app_data_dir, now_iso, read_json, write_json
from .model_catalog import current_generated_catalog, resolved_web_capability_fields
from .providers import get_provider_profile, resolve_provider_id
from .providers.tooling import assess_model_authority


PROFILE_MODEL_SEED_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "kimi": {
        "kimi-k2.7-code": {
            "display_name": "Kimi K2.7 Code",
            "input_modalities": ["text", "image"],
            "modality_limits": {
                "image_transport": "chat_completions_base64_image_url",
                "remote_image_url_supported": False,
                "supported_image_formats": ["png", "jpeg", "webp", "gif"],
                "request_body_limit_mb": 100,
                "video_input": "provider_supported_unverified_in_astrabridge",
            },
            "source_urls": [
                "https://platform.moonshot.ai/docs/overview",
                "https://platform.kimi.com/docs/api/overview",
                "https://platform.kimi.com/docs/guide/start-using-kimi-api",
            ],
        },
        "kimi-k2.6": {
            "display_name": "Kimi K2.6",
            "input_modalities": ["text", "image", "video"],
            "modality_limits": {
                "image_transport": "chat_completions_base64_image_url",
                "remote_image_url_supported": False,
                "supported_image_formats": ["png", "jpeg", "webp", "gif"],
                "request_body_limit_mb": 100,
                "video_input": "provider_supported_unverified_in_astrabridge",
            },
            "source_urls": [
                "https://platform.moonshot.ai/docs/overview",
                "https://platform.kimi.com/docs/api/overview",
                "https://platform.kimi.com/docs/guide/start-using-kimi-api",
            ],
        },
    },
}

PROVIDER_METADATA_FIELDS = (
    "runtime_backend",
    "supported_reasoning_levels",
    "default_reasoning_level",
    "reasoning_policy_mode",
    "input_modalities",
    "edit_policy",
    "capabilities",
    "apply_patch_tool_type",
    "web_search_tool_type",
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
    "temperature_default",
    "temperature_ui_min",
    "temperature_ui_max",
    "provider_temperature_min",
    "provider_temperature_max",
    "temperature_adapter_policy",
    "effective_context_window_percent",
    "auto_compact_token_limit",
    "tool_output_token_limit",
    "supports_image_detail_original",
    "fallback_models",
    "downgrade_reasoning_levels",
    "drop_unsupported_modalities",
)


class RouterConfigService:
    def __init__(self, profile_service, store_path: Path | None = None) -> None:
        self._profiles = profile_service
        self.store_path = store_path or (app_data_dir() / "router_config.json")

    def snapshot(self) -> dict[str, Any]:
        payload = self._load()
        providers = payload["providers"]
        models = payload["models"]
        latest_test = payload.get("latest_test")
        enabled_provider_ids = {str(item.get("id")) for item in providers if item.get("enabled", True)}
        return {
            "providers": providers,
            "models": models,
            "reasoning": payload["reasoning"],
            "latest_test": latest_test,
            "enabled_model_count": len([item for item in models if item.get("enabled", True) and item.get("provider") in enabled_provider_ids]),
        }

    def providers(self) -> list[dict[str, Any]]:
        return list(self._load()["providers"])

    def models(self) -> list[dict[str, Any]]:
        return list(self._load()["models"])

    def reasoning(self) -> dict[str, Any]:
        return dict(self._load()["reasoning"])

    def upsert_provider(self, provider: dict[str, Any]) -> dict[str, Any]:
        payload = self._load()
        provider_id = str(provider.get("id") or provider.get("provider_id") or "").strip()
        if not provider_id:
            raise ValueError("Provider id is required.")
        provider_family = _provider_family(
            provider_id,
            adapter_profile=provider.get("adapter_profile"),
            wire_api=provider.get("adapter_type") or provider.get("wire_api"),
            base_url=provider.get("base_url"),
            model=provider.get("default_model") or provider.get("model"),
        )
        registry_profile = get_provider_profile(provider_family) if provider_family else None
        registry_defaults = registry_profile.to_router_provider() if registry_profile else {}
        display_name = str(provider.get("display_name") or provider.get("label") or (registry_profile.display_name if registry_profile else provider_id)).strip()
        base_url = str(provider.get("base_url") or (registry_profile.base_url if registry_profile else "")).strip()
        env_key = str(provider.get("env_key") or ((registry_profile.auth.env_vars[0]) if registry_profile and registry_profile.auth.env_vars else "OPENAI_API_KEY")).strip()
        auth_mode = str(provider.get("auth_mode") or "os_keychain").strip()
        merged = {
            **registry_defaults,
            "id": provider_id,
            "provider_id": provider_id,
            "provider_family": provider_family,
            "display_name": display_name,
            "enabled": bool(provider.get("enabled", True)),
            "adapter_type": str(provider.get("adapter_type") or provider.get("wire_api") or ("responses" if registry_profile and registry_profile.protocol in {"responses", "qwen_responses"} else "responses")),
            "runtime_backend": str(provider.get("runtime_backend") or provider.get("execution_backend") or (registry_profile.runtime_backend if registry_profile else "app_server")),
            "base_url": base_url,
            "auth_key_ref": provider.get("auth_key_ref"),
            "default_model": str(provider.get("default_model") or provider.get("model") or (registry_profile.default_model if registry_profile else "")).strip(),
            "request_timeout_ms": int(provider.get("request_timeout_ms") or 300000),
            "stream_idle_timeout_ms": int(provider.get("stream_idle_timeout_ms") or 300000),
            "env_key": env_key,
            "auth_mode": auth_mode,
            "proxy_mode": str(provider.get("proxy_mode") or "direct"),
            "proxy_url": str(provider.get("proxy_url") or ""),
            "logo_source_url": str(provider.get("logo_source_url") or ""),
            "logo_asset_path": str(provider.get("logo_asset_path") or ""),
            "logo_license_note": str(provider.get("logo_license_note") or ""),
            "accent_color": str(provider.get("accent_color") or ""),
            "created_at": provider.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        existing = {str(item.get("id")): item for item in payload["providers"]}
        if provider_id in existing:
            merged["created_at"] = existing[provider_id].get("created_at") or merged["created_at"]
        existing[provider_id] = merged
        payload["providers"] = sorted(existing.values(), key=lambda item: str(item.get("id")))
        write_json(self.store_path, payload)
        self._sync_provider_profile(merged)
        self._ensure_default_model_entry(merged)
        return merged

    def delete_provider(self, provider_id: str) -> dict[str, Any]:
        payload = self._load()
        payload["providers"] = [item for item in payload["providers"] if str(item.get("id")) != provider_id]
        payload["models"] = [item for item in payload["models"] if str(item.get("provider")) != provider_id]
        write_json(self.store_path, payload)
        return {"deleted": provider_id}

    def upsert_model(self, model: dict[str, Any]) -> dict[str, Any]:
        payload = self._load()
        model_id = str(model.get("id") or "").strip()
        provider = str(model.get("provider") or "").strip()
        native_model = str(model.get("native_model") or "").strip()
        if not model_id or not provider or not native_model:
            raise ValueError("Model id, provider, and native_model are required.")
        if "/" not in model_id:
            model_id = f"{provider}/{native_model}"
        provider_family = _provider_family(provider, model=native_model)
        base_defaults = _profile_model_defaults(provider_family)
        merged_model = {**base_defaults, **model}
        merged = {
            "id": model_id,
            "provider": provider,
            "native_model": native_model,
            "display_name": str(merged_model.get("display_name") or native_model),
            "enabled": bool(merged_model.get("enabled", True)),
            "advertised_context_window": int(merged_model.get("advertised_context_window") or 1000000),
            "ui_context_hint_only": bool(merged_model.get("ui_context_hint_only", True)),
            "adapter_profile": str(merged_model.get("adapter_profile") or "default"),
            **_model_capability_fields(merged_model),
            "created_at": merged_model.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        existing = {str(item.get("id")): item for item in payload["models"]}
        if model_id in existing:
            merged["created_at"] = existing[model_id].get("created_at") or merged["created_at"]
        existing[model_id] = merged
        payload["models"] = sorted(existing.values(), key=lambda item: str(item.get("id")))
        write_json(self.store_path, payload)
        return merged

    def delete_model(self, model_id: str) -> dict[str, Any]:
        payload = self._load()
        payload["models"] = [item for item in payload["models"] if str(item.get("id")) != model_id]
        write_json(self.store_path, payload)
        return {"deleted": model_id}

    def save_reasoning(self, reasoning: dict[str, Any]) -> dict[str, Any]:
        payload = self._load()
        payload["reasoning"] = {
            "global_effort": str(reasoning.get("global_effort") or "high"),
            "provider_overrides": dict(reasoning.get("provider_overrides") or {}),
            "model_overrides": dict(reasoning.get("model_overrides") or {}),
            "native_parameter_overrides": dict(reasoning.get("native_parameter_overrides") or {}),
            "updated_at": now_iso(),
        }
        write_json(self.store_path, payload)
        return payload["reasoning"]

    def record_test_result(self, result: dict[str, Any]) -> None:
        payload = self._load()
        payload["latest_test"] = {"timestamp": now_iso(), **result}
        write_json(self.store_path, payload)

    def export_sanitized(self) -> dict[str, Any]:
        payload = self._load()
        exported = {
            "providers": [],
            "models": payload["models"],
            "reasoning": payload["reasoning"],
        }
        for provider in payload["providers"]:
            item = dict(provider)
            item["auth_key_ref"] = None
            exported["providers"].append(item)
        return exported

    def import_sanitized(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self._load()
        current["providers"] = [dict(item) for item in list(payload.get("providers") or [])]
        current["models"] = [dict(item) for item in list(payload.get("models") or [])]
        current["reasoning"] = dict(payload.get("reasoning") or current["reasoning"])
        for provider in current["providers"]:
            provider["auth_key_ref"] = None
            self._sync_provider_profile(provider)
        write_json(self.store_path, current)
        return self.snapshot()

    def _load(self) -> dict[str, Any]:
        payload = read_json(self.store_path, {})
        if not isinstance(payload, dict):
            payload = {}
        profiles = list((self._profiles.list_profiles().get("profiles") or []))
        providers = [item for item in payload.get("providers") or [] if isinstance(item, dict)]
        models = [item for item in payload.get("models") or [] if isinstance(item, dict)]
        generated = current_generated_catalog()
        if not providers:
            providers = [self._provider_from_profile(profile) for profile in profiles if profile.get("base_url")]
        if not providers:
            providers = [dict(item) for item in generated.providers]
        if not models:
            generated_models = [dict(item) for item in generated.models if isinstance(item, dict)]
            models = generated_models or []
            if not models:
                for provider in providers:
                    default_model = str(provider.get("default_model") or "").strip()
                    if default_model:
                        models.append(self._default_model(provider, default_model))
        models = self._merge_known_models(providers, models)
        reasoning = payload.get("reasoning")
        if not isinstance(reasoning, dict):
            reasoning = {
                "global_effort": "high",
                "provider_overrides": {},
                "model_overrides": {},
                "native_parameter_overrides": {},
                "updated_at": now_iso(),
            }
        loaded = {
            "providers": sorted(providers, key=lambda item: str(item.get("id"))),
            "models": sorted(models, key=lambda item: str(item.get("id"))),
            "reasoning": reasoning,
            "latest_test": payload.get("latest_test"),
        }
        write_json(self.store_path, loaded)
        return loaded

    def _provider_from_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(profile.get("provider_id") or "openai")
        extras = {key: profile.get(key) for key in PROVIDER_METADATA_FIELDS if key in profile}
        return {
            "id": provider_id,
            "provider_id": provider_id,
            "provider_family": _provider_family(
                provider_id,
                wire_api=profile.get("wire_api"),
                base_url=profile.get("base_url"),
                model=profile.get("model"),
            ),
            "display_name": str(profile.get("label") or provider_id),
            "enabled": True,
            "adapter_type": str(profile.get("wire_api") or "responses"),
            "runtime_backend": str(profile.get("execution_backend") or profile.get("runtime_backend") or "app_server"),
            "base_url": str(profile.get("base_url") or ""),
            "auth_key_ref": profile.get("secret_ref"),
            "default_model": str(profile.get("model") or ""),
            "request_timeout_ms": 300000,
            "stream_idle_timeout_ms": 300000,
            "env_key": str(profile.get("env_key") or "OPENAI_API_KEY"),
            "auth_mode": str(profile.get("auth_mode") or "env_ref"),
            "proxy_mode": str(profile.get("proxy_mode") or "direct"),
            "proxy_url": str(profile.get("proxy_url") or ""),
            "created_at": profile.get("created_at") or now_iso(),
            "updated_at": profile.get("updated_at") or now_iso(),
            **extras,
        }

    def _sync_provider_profile(self, provider: dict[str, Any]) -> None:
        default_model = str(provider.get("default_model") or "").strip()
        if not default_model:
            return
        profile_id = "openai-compatible" if provider["id"] == "openai" else f"{provider['id']}-default"
        provider_family = _provider_family(
            provider.get("provider_family") or provider.get("adapter_profile") or provider.get("provider_id") or provider.get("id"),
            wire_api=provider.get("adapter_type"),
            base_url=provider.get("base_url"),
            model=default_model,
        )
        registry_profile = get_provider_profile(provider_family) if provider_family else None
        registry_defaults = registry_profile.to_default_profile() if registry_profile else {}
        self._profiles.upsert_profile(
            {
                **registry_defaults,
                "profile_id": profile_id,
                "label": str(provider.get("display_name") or provider["id"]),
                "type": "custom_provider",
                "provider_id": provider["id"],
                "base_url": provider.get("base_url"),
                "model": default_model,
                "reasoning_effort": (
                    str(provider.get("default_reasoning_level") or "").strip()
                    or str(registry_defaults.get("reasoning_effort") or "").strip()
                    or str(self.reasoning().get("global_effort") or "high")
                ),
                "wire_api": provider.get("adapter_type") or "responses",
                "execution_backend": provider.get("runtime_backend") or provider.get("execution_backend") or registry_defaults.get("execution_backend") or "app_server",
                "env_key": provider.get("env_key") or "OPENAI_API_KEY",
                "auth_mode": provider.get("auth_mode") or "env_ref",
                "secret_ref": provider.get("auth_key_ref"),
                "proxy_mode": provider.get("proxy_mode") or "direct",
                "proxy_url": provider.get("proxy_url") or "",
            }
        )

    def _ensure_default_model_entry(self, provider: dict[str, Any]) -> None:
        default_model = str(provider.get("default_model") or "").strip()
        if not default_model:
            return
        model_id = f"{provider['id']}/{default_model}"
        payload = self._load()
        if any(str(item.get("id")) == model_id for item in payload["models"]):
            return
        payload["models"].append(self._default_model(provider, default_model))
        payload["models"] = sorted(payload["models"], key=lambda item: str(item.get("id")))
        write_json(self.store_path, payload)

    def _default_model(self, provider: dict[str, Any], native_model: str) -> dict[str, Any]:
        provider_family = _provider_family(
            provider.get("provider_family") or provider.get("adapter_profile") or provider.get("id") or provider.get("provider_id"),
            wire_api=provider.get("adapter_type"),
            base_url=provider.get("base_url"),
            model=native_model,
        )
        defaults = _profile_model_defaults(provider_family)
        return {
            "id": f"{provider['id']}/{native_model}",
            "provider": provider["id"],
            "native_model": native_model,
            "display_name": native_model,
            "enabled": True,
            "advertised_context_window": int(defaults.get("advertised_context_window") or 1000000),
            "ui_context_hint_only": True,
            "adapter_profile": "default",
            **_model_capability_fields(defaults),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

    def _merge_known_models(self, providers: list[dict[str, Any]], models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged = {str(item.get("id")): dict(item) for item in models if isinstance(item, dict)}
        provider_model_counts: dict[str, int] = {}
        for item in models:
            if not isinstance(item, dict):
                continue
            provider_key = str(item.get("provider") or "")
            if provider_key:
                provider_model_counts[provider_key] = provider_model_counts.get(provider_key, 0) + 1
        for provider in providers:
            provider_id = str(provider.get("id") or provider.get("provider_id") or "openai")
            if provider_model_counts.get(provider_id, 0) > 0:
                continue
            provider_family = _provider_family(
                provider.get("provider_family") or provider_id,
                adapter_profile=provider.get("adapter_profile"),
                wire_api=provider.get("adapter_type"),
                base_url=provider.get("base_url"),
                model=provider.get("default_model"),
            )
            known_entries = _profile_seed_entries(provider_family)
            if not known_entries:
                continue
            base_defaults = _profile_model_defaults(provider_family)
            for entry in known_entries:
                native_model = str(entry["native_model"])
                model_id = f"{provider_id}/{native_model}"
                if model_id in merged:
                    continue
                seeded = {**base_defaults, **entry}
                merged[model_id] = {
                    "id": model_id,
                    "provider": provider_id,
                    "provider_family": provider_family,
                    "native_model": native_model,
                    "display_name": str(seeded.get("display_name") or native_model),
                    "enabled": True,
                    "advertised_context_window": int(seeded.get("advertised_context_window") or 1000000),
                    "ui_context_hint_only": True,
                    "adapter_profile": "default",
                    **_model_capability_fields(seeded),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
        return sorted(merged.values(), key=lambda item: str(item.get("id")))


def _profile_seed_entries(provider_family: str | None) -> list[dict[str, Any]]:
    if not provider_family:
        return []
    try:
        profile = get_provider_profile(provider_family)
    except ValueError:
        return []
    advertised_context_window = profile.context_window() or 1_000_000
    preferred_models = profile.fallback_policy.fallback_models or profile.fallback_models or (profile.default_model,)
    seed_entries: list[dict[str, Any]] = []
    for native_model in preferred_models:
        clean_model = str(native_model or "").strip()
        if not clean_model:
            continue
        overrides = PROFILE_MODEL_SEED_OVERRIDES.get(profile.id, {}).get(clean_model, {})
        seed_entries.append(
            {
                "native_model": clean_model,
                "display_name": str(overrides.get("display_name") or clean_model),
                "advertised_context_window": int(overrides.get("advertised_context_window") or advertised_context_window),
                **overrides,
            }
        )
    return seed_entries


def _model_capability_fields(model: dict[str, Any]) -> dict[str, Any]:
    modalities = model.get("input_modalities")
    if not isinstance(modalities, list):
        modalities = ["text"]
    temperature_default = _optional_float(model.get("temperature_default"), 0.0)
    temperature_ui_min = _optional_float(model.get("temperature_ui_min"), 0.0)
    temperature_ui_max = _optional_float(model.get("temperature_ui_max"), 2.0)
    provider_temperature_min = _optional_float(model.get("provider_temperature_min"), 0.0)
    provider_temperature_max = _optional_float(model.get("provider_temperature_max"), 2.0)
    authority = assess_model_authority(
        {
            **model,
            "supports_tool_calls": bool(model.get("supports_mcp_tools", False) or model.get("apply_patch_tool_type")),
        }
    )
    ui_warnings = list(model.get("ui_warnings") or _default_ui_warnings(model, modalities))
    for warning in authority.ui_warnings:
        if warning not in ui_warnings:
            ui_warnings.append(warning)
    return {
        "input_modalities": [str(item) for item in modalities if str(item).strip()] or ["text"],
        "model_kind": str(model.get("model_kind") or "chat"),
        "codex_agent_enabled": bool(model.get("codex_agent_enabled", True)),
        "apply_patch_tool_type": model.get("apply_patch_tool_type"),
        "web_search_tool_type": model.get("web_search_tool_type") or "text",
        "supports_parallel_tool_calls": bool(model.get("supports_parallel_tool_calls", False)),
        "supports_reasoning_summaries": bool(model.get("supports_reasoning_summaries", False)),
        "reasoning_display_policy": str(model.get("reasoning_display_policy") or "collapsed_3_lines"),
        "supported_reasoning_levels": list(model.get("supported_reasoning_levels") or []),
        "default_reasoning_level": model.get("default_reasoning_level"),
        "supports_search_tool": bool(model.get("supports_search_tool", False)),
        **resolved_web_capability_fields(model),
        "supports_image_detail_original": bool(model.get("supports_image_detail_original", False)),
        "effective_context_window_percent": int(model.get("effective_context_window_percent") or 80),
        "auto_compact_token_limit": model.get("auto_compact_token_limit"),
        "tool_output_token_limit": model.get("tool_output_token_limit"),
        "temperature_default": temperature_default,
        "temperature_ui_min": temperature_ui_min,
        "temperature_ui_max": temperature_ui_max,
        "provider_temperature_min": provider_temperature_min,
        "provider_temperature_max": provider_temperature_max,
        "temperature_adapter_policy": str(model.get("temperature_adapter_policy") or "pass_through_0_2"),
        "pricing_currency": str(model.get("pricing_currency") or ""),
        "pricing_input_per_mtok": model.get("pricing_input_per_mtok"),
        "pricing_output_per_mtok": model.get("pricing_output_per_mtok"),
        "pricing_cached_input_per_mtok": model.get("pricing_cached_input_per_mtok"),
        "pricing_source_url": str(model.get("pricing_source_url") or ""),
        "pricing_status": str(model.get("pricing_status") or "unknown"),
        "use_responses_lite": bool(model.get("use_responses_lite", False)),
        "tool_mode": model.get("tool_mode"),
        "multi_agent_version": model.get("multi_agent_version"),
        "experimental_supported_tools": list(model.get("experimental_supported_tools") or []),
        "supports_mcp_tools": bool(model.get("supports_mcp_tools", False)),
        "mcp_tool_call_policy": str(model.get("mcp_tool_call_policy") or "unsupported"),
        "mcp_verified_servers": list(model.get("mcp_verified_servers") or []),
        "mcp_smoke_status": str(model.get("mcp_smoke_status") or "untested"),
        "mcp_tool_argument_validation": str(model.get("mcp_tool_argument_validation") or "unsupported"),
        "codex_builtin_tools": dict(model.get("codex_builtin_tools") or _default_builtin_tool_support()),
        "planner_support": dict(model.get("planner_support") or _default_planner_support()),
        "goal_support": dict(model.get("goal_support") or {"thread_goal": "app_server_native"}),
        "context_compaction_support": dict(model.get("context_compaction_support") or _default_context_compaction_support()),
        "modality_limits": dict(model.get("modality_limits") or _default_modality_limits(modalities)),
        "ui_warnings": ui_warnings,
        "authority_tier": authority.tier,
        "authority_reason": authority.reason,
        "parallel_tool_call_status": authority.parallel_tool_call_status,
        "source_urls": list(model.get("source_urls") or []),
        "source_status": str(model.get("source_status") or "seeded"),
        "recommended": bool(model.get("recommended", False)),
        "default_for_provider": bool(model.get("default_for_provider", False)),
        "deprecated": bool(model.get("deprecated", False)),
        "deprecated_after": model.get("deprecated_after"),
        "confidence": model.get("confidence"),
        "catalog_version": model.get("catalog_version"),
        "source_provenance": dict(model.get("source_provenance") or {}),
        "last_verified_at": model.get("last_verified_at"),
        "verification_notes": str(model.get("verification_notes") or ""),
    }


def _profile_model_defaults(provider_family: str | None) -> dict[str, Any]:
    if not provider_family:
        return {}
    try:
        return dict(get_provider_profile(provider_family).to_model_defaults())
    except ValueError:
        return {}


def _optional_float(value: Any, fallback: float) -> float:
    if value in {None, ""}:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _provider_family(
    provider_id: Any,
    *,
    adapter_profile: Any = None,
    wire_api: Any = None,
    base_url: Any = None,
    model: Any = None,
) -> str | None:
    for candidate in (adapter_profile, provider_id):
        try:
            return resolve_provider_id(str(candidate or "").strip())
        except ValueError:
            continue
    signals = " ".join(
        str(value or "").strip().lower()
        for value in (provider_id, wire_api, base_url, model)
        if str(value or "").strip()
    )
    if any(token in signals for token in ("deepseek",)):
        return "deepseek"
    if any(token in signals for token in ("moonshot", "kimi")):
        return "kimi"
    if any(token in signals for token in ("dashscope", "qwen")):
        return "qwen"
    if any(token in signals for token in ("bigmodel", "glm", "zai", "zhipu")):
        return "glm"
    if "yunwu" in signals:
        return "yunwu"
    if "openai" in signals:
        return "openai"
    return None


def _default_builtin_tool_support() -> dict[str, dict[str, str]]:
    return {
        "shell_command": {"support": "verified", "notes": "Codex app-server native tool; still permission-gated by sandbox mode."},
        "apply_patch": {"support": "conservative", "notes": "Expose only through Codex native patch flow unless model smoke verifies structured patch calls."},
        "view_image": {"support": "conservative", "notes": "Requires image input modality verification."},
        "update_plan": {"support": "conservative", "notes": "Provider must emit exact tool calls; verify with plan smoke."},
        "request_user_input": {"support": "conservative", "notes": "Provider must emit exact structured tool calls; verify with modal smoke."},
        "thread_goal": {"support": "verified", "notes": "Goal is app-server state, not model-native behavior."},
        "thread_compact": {"support": "conservative", "notes": "Manual compact is app-server native; summary quality must be smoke-tested per model."},
    }


def _default_planner_support() -> dict[str, str]:
    return {
        "update_plan": "conservative",
        "plan_mode": "conservative",
        "request_user_input": "conservative",
    }


def _default_context_compaction_support() -> dict[str, str]:
    return {
        "manual_compact": "app_server_native",
        "auto_compact": "configured_unverified",
        "structured_summary_quality": "untested",
    }


def _default_modality_limits(modalities: Any) -> dict[str, Any]:
    values = [str(item).lower() for item in list(modalities or [])]
    return {
        "text": True,
        "image_input": "image" in values,
        "file_mentions": True,
        "image_generation": False,
    }


def _default_ui_warnings(model: dict[str, Any], modalities: Any) -> list[str]:
    warnings = []
    values = [str(item).lower() for item in list(modalities or [])]
    if "image" not in values and str(model.get("model_kind") or "chat") == "chat":
        warnings.append("Image attachments are not verified for this model; send them as file context only or choose an image-capable model.")
    if not bool(model.get("supports_mcp_tools", False)):
        warnings.append("MCP tool use is unverified for this model. Keep MCP tools approval-gated until a smoke test passes.")
    return warnings

