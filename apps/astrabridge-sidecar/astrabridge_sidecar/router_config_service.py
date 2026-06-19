from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import app_data_dir, now_iso, read_json, write_json


KNOWN_MODEL_CATALOG: dict[str, list[dict[str, Any]]] = {
    "openai": [
        {"native_model": "gpt-5.5", "display_name": "GPT-5.5", "advertised_context_window": 1000000, "supported_reasoning_levels": ["none", "low", "medium", "high", "xhigh"]},
        {"native_model": "gpt-5.4", "display_name": "GPT-5.4", "advertised_context_window": 1000000, "supported_reasoning_levels": ["none", "low", "medium", "high", "xhigh"]},
        {"native_model": "gpt-5.4-mini", "display_name": "GPT-5.4 mini", "advertised_context_window": 1000000, "supported_reasoning_levels": ["none", "low", "medium", "high"]},
        {"native_model": "gpt-5.4-nano", "display_name": "GPT-5.4 nano", "advertised_context_window": 1000000, "supported_reasoning_levels": ["none", "low", "medium"]},
        {"native_model": "gpt-5", "display_name": "GPT-5", "advertised_context_window": 400000, "supported_reasoning_levels": ["minimal", "low", "medium", "high"]},
    ],
    "yunwu": [
        {"native_model": "gpt-5.5", "display_name": "GPT-5.5", "advertised_context_window": 1000000},
        {"native_model": "gpt-5.4", "display_name": "GPT-5.4", "advertised_context_window": 1000000},
        {"native_model": "gpt-5.4-mini", "display_name": "GPT-5.4 mini", "advertised_context_window": 1000000},
        {"native_model": "gpt-5.3-codex", "display_name": "GPT-5.3 Codex", "advertised_context_window": 1000000},
    ],
    "deepseek": [
        {"native_model": "deepseek-v4-pro", "display_name": "DeepSeek V4 Pro", "advertised_context_window": 1000000},
        {"native_model": "deepseek-v4-flash", "display_name": "DeepSeek V4 Flash", "advertised_context_window": 1000000},
    ],
    "kimi": [
        {
            "native_model": "kimi-k2.6",
            "display_name": "Kimi K2.6",
            "advertised_context_window": 256000,
            "input_modalities": ["text", "image", "video"],
            "modality_limits": {
                "image_transport": "chat_completions_base64_image_url",
                "remote_image_url_supported": False,
                "supported_image_formats": ["png", "jpeg", "webp", "gif"],
                "request_body_limit_mb": 100,
                "video_input": "provider_supported_unverified_in_lcr",
            },
            "source_urls": [
                "https://platform.kimi.com/docs/overview",
                "https://platform.kimi.com/docs/models",
                "https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart",
            ],
        },
        {
            "native_model": "kimi-k2.5",
            "display_name": "Kimi K2.5",
            "advertised_context_window": 256000,
            "input_modalities": ["text", "image", "video"],
            "modality_limits": {
                "image_transport": "chat_completions_base64_image_url",
                "remote_image_url_supported": False,
                "supported_image_formats": ["png", "jpeg", "webp", "gif"],
                "request_body_limit_mb": 100,
                "video_input": "provider_supported_unverified_in_lcr",
            },
            "source_urls": [
                "https://platform.kimi.com/docs/overview",
                "https://platform.kimi.com/docs/models",
                "https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart",
            ],
        },
    ],
    "qwen": [
        {"native_model": "qwen3-max", "display_name": "Qwen3 Max", "advertised_context_window": 262144},
        {"native_model": "qwen3-coder-plus", "display_name": "Qwen3 Coder Plus", "advertised_context_window": 1000000},
        {"native_model": "qwen3.5-plus", "display_name": "Qwen3.5 Plus", "advertised_context_window": 1000000},
        {"native_model": "qwen-long-latest", "display_name": "Qwen Long Latest", "advertised_context_window": 1000000},
    ],
    "dashscope": [
        {"native_model": "qwen3-max", "display_name": "Qwen3 Max", "advertised_context_window": 262144},
        {"native_model": "qwen3-coder-plus", "display_name": "Qwen3 Coder Plus", "advertised_context_window": 1000000},
        {"native_model": "qwen3.5-plus", "display_name": "Qwen3.5 Plus", "advertised_context_window": 1000000},
        {"native_model": "qwen-long-latest", "display_name": "Qwen Long Latest", "advertised_context_window": 1000000},
    ],
}


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
        display_name = str(provider.get("display_name") or provider.get("label") or provider_id).strip()
        base_url = str(provider.get("base_url") or "").strip()
        env_key = str(provider.get("env_key") or "OPENAI_API_KEY").strip()
        auth_mode = str(provider.get("auth_mode") or "os_keychain").strip()
        merged = {
            "id": provider_id,
            "provider_id": provider_id,
            "display_name": display_name,
            "enabled": bool(provider.get("enabled", True)),
            "adapter_type": str(provider.get("adapter_type") or provider.get("wire_api") or "responses"),
            "base_url": base_url,
            "auth_key_ref": provider.get("auth_key_ref"),
            "default_model": str(provider.get("default_model") or provider.get("model") or "").strip(),
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
        merged = {
            "id": model_id,
            "provider": provider,
            "native_model": native_model,
            "display_name": str(model.get("display_name") or native_model),
            "enabled": bool(model.get("enabled", True)),
            "advertised_context_window": int(model.get("advertised_context_window") or 1000000),
            "ui_context_hint_only": bool(model.get("ui_context_hint_only", True)),
            "adapter_profile": str(model.get("adapter_profile") or "default"),
            **_model_capability_fields(model),
            "created_at": model.get("created_at") or now_iso(),
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
        if not providers:
            providers = [self._provider_from_profile(profile) for profile in profiles if profile.get("base_url")]
        if not models:
            models = []
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
        provider_id = str(profile.get("provider_id") or "")
        return {
            "id": provider_id,
            "provider_id": provider_id,
            "display_name": str(profile.get("label") or provider_id),
            "enabled": True,
            "adapter_type": str(profile.get("wire_api") or "responses"),
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
        }

    def _sync_provider_profile(self, provider: dict[str, Any]) -> None:
        default_model = str(provider.get("default_model") or "").strip()
        if not default_model:
            return
        self._profiles.upsert_profile(
            {
                "profile_id": f"{provider['id']}-default",
                "label": str(provider.get("display_name") or provider["id"]),
                "type": "custom_provider",
                "provider_id": provider["id"],
                "base_url": provider.get("base_url"),
                "model": default_model,
                "reasoning_effort": self.reasoning().get("global_effort") or "high",
                "wire_api": provider.get("adapter_type") or "responses",
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
        return {
            "id": f"{provider['id']}/{native_model}",
            "provider": provider["id"],
            "native_model": native_model,
            "display_name": native_model,
            "enabled": True,
            "advertised_context_window": 1000000,
            "ui_context_hint_only": True,
            "adapter_profile": "default",
            **_model_capability_fields({}),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

    def _merge_known_models(self, providers: list[dict[str, Any]], models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged = {str(item.get("id")): dict(item) for item in models if isinstance(item, dict)}
        for provider in providers:
            provider_id = str(provider.get("id") or "")
            normalized = provider_id.lower()
            known_entries = KNOWN_MODEL_CATALOG.get(normalized)
            if not known_entries:
                known_entries = next((entries for key, entries in KNOWN_MODEL_CATALOG.items() if key in normalized), None)
            if not known_entries:
                continue
            for entry in known_entries:
                native_model = str(entry["native_model"])
                model_id = f"{provider_id}/{native_model}"
                if model_id in merged:
                    continue
                merged[model_id] = {
                    "id": model_id,
                    "provider": provider_id,
                    "native_model": native_model,
                    "display_name": str(entry.get("display_name") or native_model),
                    "enabled": True,
                    "advertised_context_window": int(entry.get("advertised_context_window") or 1000000),
                    "ui_context_hint_only": True,
                    "adapter_profile": "default",
                    **_model_capability_fields(entry),
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                }
        return sorted(merged.values(), key=lambda item: str(item.get("id")))


def _model_capability_fields(model: dict[str, Any]) -> dict[str, Any]:
    modalities = model.get("input_modalities")
    if not isinstance(modalities, list):
        modalities = ["text"]
    temperature_default = _optional_float(model.get("temperature_default"), 0.0)
    temperature_ui_min = _optional_float(model.get("temperature_ui_min"), 0.0)
    temperature_ui_max = _optional_float(model.get("temperature_ui_max"), 2.0)
    provider_temperature_min = _optional_float(model.get("provider_temperature_min"), 0.0)
    provider_temperature_max = _optional_float(model.get("provider_temperature_max"), 2.0)
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
        "native_web_search_support": str(model.get("native_web_search_support") or "unverified"),
        "tool_web_search_support": str(model.get("tool_web_search_support") or "unverified"),
        "mcp_web_support": str(model.get("mcp_web_support") or "unverified"),
        "web_smoke_status": str(model.get("web_smoke_status") or "untested"),
        "citation_quality": str(model.get("citation_quality") or "untested"),
        "last_web_verified_at": model.get("last_web_verified_at"),
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
        "ui_warnings": list(model.get("ui_warnings") or _default_ui_warnings(model, modalities)),
        "source_urls": list(model.get("source_urls") or []),
        "source_status": str(model.get("source_status") or "seeded"),
        "last_verified_at": model.get("last_verified_at"),
        "verification_notes": str(model.get("verification_notes") or ""),
    }


def _optional_float(value: Any, fallback: float) -> float:
    if value in {None, ""}:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


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

