from __future__ import annotations

from pathlib import Path
from typing import Any

from .capabilities.capability_registry import default_capability_registry
from .capabilities.capability_routes import (
    provider_capability_summary,
    resolve_capability_route_entry,
    normalize_capability_route_record,
)
from .common import app_data_dir, now_iso, read_json, write_json
from .model_catalog import current_generated_catalog, resolved_web_capability_fields
from .provider_capability_snapshot import (
    build_verified_capability_snapshot,
    capability_snapshot_matches_current_contract,
    current_model_provider_contract,
    describe_capability_snapshot_manifest,
    aggregate_matrix_entries_by_model,
)
from .providers import (
    default_builtin_tool_support,
    default_context_compaction_support,
    default_goal_support,
    default_planner_support,
    get_provider_profile,
    resolve_provider_id,
)
from .providers.transports import transport_class_for_profile
from .providers.transports.base import transport_signature_for_class
from .providers.tooling import assess_default_route_verification, assess_model_authority, has_structured_tool_surface


PROFILE_MODEL_SEED_OVERRIDES: dict[str, dict[str, dict[str, Any]]] = {
    "qwen": {
        "qwen3-vl-plus": {
            "display_name": "Qwen3 VL Plus",
            "input_modalities": ["text", "image"],
            "source_urls": [
                "https://help.aliyun.com/zh/model-studio/models",
                "https://help.aliyun.com/zh/model-studio/vision",
            ],
        },
        "qwen3-vl-flash": {
            "display_name": "Qwen3 VL Flash",
            "input_modalities": ["text", "image"],
            "source_urls": [
                "https://help.aliyun.com/zh/model-studio/models",
                "https://help.aliyun.com/zh/model-studio/vision",
            ],
        },
        "qwen3-asr-flash": {
            "display_name": "Qwen3 ASR Flash",
            "input_modalities": ["text", "audio"],
            "source_urls": [
                "https://help.aliyun.com/zh/model-studio/models",
                "https://help.aliyun.com/zh/model-studio/asr-model/",
            ],
        },
        "qwen3-tts-flash": {
            "display_name": "Qwen3 TTS Flash",
            "input_modalities": ["text", "audio"],
            "source_urls": [
                "https://help.aliyun.com/zh/model-studio/models",
                "https://help.aliyun.com/zh/model-studio/qwen-tts-api",
            ],
        },
        "qwen3-tts-instruct-flash": {
            "display_name": "Qwen3 TTS Instruct Flash",
            "input_modalities": ["text", "audio"],
            "source_urls": [
                "https://help.aliyun.com/zh/model-studio/models",
                "https://help.aliyun.com/zh/model-studio/qwen-tts-api",
            ],
        },
    },
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
        "kimi-k2.7-code-highspeed": {
            "display_name": "Kimi K2.7 Code Highspeed",
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
    "model_defaults",
    "runtime_backend",
    "supported_reasoning_levels",
    "default_reasoning_level",
    "native_supported_reasoning_levels",
    "native_default_reasoning_level",
    "reasoning_policy_mode",
    "supports_reasoning_replay",
    "preserve_reasoning_for_tool_turns",
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
    "codex_builtin_tools",
    "planner_support",
    "goal_support",
    "context_compaction_support",
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

CATALOG_MANAGED_MODEL_SOURCE_STATUSES = {"official_docs", "screenshot_seed", "seeded"}
CATALOG_MANAGED_MODALITY_SYNC_FIELDS = (
    "input_modalities",
    "supports_image_detail_original",
    "modality_limits",
    "ui_warnings",
)


class RouterConfigService:
    def __init__(self, profile_service, store_path: Path | None = None) -> None:
        self._profiles = profile_service
        self.store_path = store_path or (app_data_dir() / "router_config.json")

    def health_snapshot(self) -> dict[str, Any]:
        payload = read_json(self.store_path, {})
        if not isinstance(payload, dict):
            payload = {}
        providers = [item for item in payload.get("providers") or [] if isinstance(item, dict)]
        models = [item for item in payload.get("models") or [] if isinstance(item, dict)]
        if not providers:
            profiles = list((self._profiles.list_profiles().get("profiles") or []))
            providers = [self._provider_from_profile(profile) for profile in profiles if isinstance(profile, dict) and profile.get("base_url")]
        if not providers:
            providers = [dict(item) for item in current_generated_catalog().providers]
        if not models:
            models = [dict(item) for item in current_generated_catalog().models if isinstance(item, dict)]
        enabled_provider_ids = {str(item.get("id") or item.get("provider_id") or "") for item in providers if item.get("enabled", True)}
        enabled_model_count = len(
            [
                item
                for item in models
                if item.get("enabled", True) and str(item.get("provider") or item.get("provider_id") or "") in enabled_provider_ids
            ]
        )
        return {
            "providers": providers,
            "provider_count": len([item for item in providers if item.get("enabled", True)]),
            "model_count": enabled_model_count,
            "latest_test": payload.get("latest_test"),
        }

    def snapshot(self) -> dict[str, Any]:
        payload = self._load()
        providers = payload["providers"]
        models = self._refresh_models(providers, payload["models"])
        latest_test = payload.get("latest_test")
        capability_routes = self.capability_route_snapshot(models)
        providers_with_capabilities = [
            {
                **provider,
                "capability_summary": provider_capability_summary(
                    str(provider.get("id") or provider.get("provider_id") or ""),
                    capability_routes["routes"],
                ),
            }
            for provider in providers
        ]
        enabled_provider_ids = {str(item.get("id")) for item in providers if item.get("enabled", True)}
        return {
            "providers": providers_with_capabilities,
            "models": models,
            "reasoning": payload["reasoning"],
            "capability_routes": capability_routes["routes"],
            "latest_test": latest_test,
            "enabled_model_count": len([item for item in models if item.get("enabled", True) and item.get("provider") in enabled_provider_ids]),
        }

    def providers(self) -> list[dict[str, Any]]:
        return list(self._load()["providers"])

    def models(self) -> list[dict[str, Any]]:
        payload = self._load()
        return self._refresh_models(payload["providers"], payload["models"])

    def reasoning(self) -> dict[str, Any]:
        return dict(self._load()["reasoning"])

    def capability_routes(self) -> dict[str, dict[str, Any]]:
        raw = self._load().get("capability_routes") or {}
        if not isinstance(raw, dict):
            return {}
        normalized: dict[str, dict[str, Any]] = {}
        for capability_id, record in raw.items():
            normalized[str(capability_id)] = normalize_capability_route_record(str(capability_id), record if isinstance(record, dict) else {})
        return normalized

    def capability_route_snapshot(self, configured_models: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        models = configured_models if configured_models is not None else self.models()
        route_records = self.capability_routes()
        registry = default_capability_registry()
        route_entries = [
            resolve_capability_route_entry(capability_id, models, route_record=route_records.get(capability_id), registry=registry)
            for capability_id in sorted({*route_records.keys(), *registry.capability_ids()})
        ]
        updated_at = max((str(item.get("updated_at") or "") for item in route_entries), default=now_iso()) or now_iso()
        return {"routes": route_entries, "updated_at": updated_at}

    def capability_management_snapshot(
        self,
        *,
        mcp_config: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        routes = self.capability_route_snapshot(configured_models)
        registry = default_capability_registry()
        adapter_contracts = registry.adapter_contracts()
        entries: list[dict[str, Any]] = []
        for route in routes["routes"]:
            capability_id = str(route.get("capability_id") or "").strip()
            spec = registry.capability_spec(capability_id)
            adapters = [item.to_dict() for item in adapter_contracts if item.capability_id == capability_id]
            smoke_case_ids = [
                str(item.get("smoke_case_id") or "").strip()
                for item in adapters
                if str(item.get("smoke_case_id") or "").strip()
            ]
            entries.append(
                {
                    "capability_id": capability_id,
                    "display_name": spec.display_name,
                    "lane_type": spec.lane_type,
                    "transport_mode": spec.transport_mode,
                    "route": route,
                    "availability": {
                        "available": route.get("resolved_candidate") is not None,
                        "candidate_count": len(list(route.get("candidates") or [])),
                        "resolution_status": route.get("resolution_status"),
                        "error": route.get("error"),
                    },
                    "contract": spec.to_dict(),
                    "adapters": adapters,
                    "smoke": {
                        "status": spec.smoke_status,
                        "case_ids": smoke_case_ids,
                        "last_result": None,
                        "evidence_refs": [],
                    },
                    "artifacts": {
                        "policy": spec.artifact_policy,
                        "recent_refs": [],
                    },
                }
            )
        return {
            "schema_version": "astrabridge-capability-management-v1",
            "capabilities": entries,
            "routes": routes["routes"],
            "mcp_preset": _capability_mcp_preset_status(mcp_config),
            "updated_at": routes["updated_at"],
        }

    def save_capability_route(self, route: dict[str, Any]) -> dict[str, Any]:
        capability_id = str(route.get("capability_id") or "").strip()
        if not capability_id:
            raise ValueError("capability_id is required.")
        payload = self._load()
        capability_routes = dict(payload.get("capability_routes") or {})
        normalized = normalize_capability_route_record(capability_id, {**route, "updated_at": now_iso()})
        capability_routes[capability_id] = normalized
        payload["capability_routes"] = capability_routes
        write_json(self.store_path, payload)
        return resolve_capability_route_entry(capability_id, payload["models"], route_record=normalized)

    def upsert_provider(self, provider: dict[str, Any]) -> dict[str, Any]:
        payload = self._load()
        provider_id = str(provider.get("id") or provider.get("provider_id") or "").strip()
        if not provider_id:
            raise ValueError("Provider id is required.")
        provider_family = _provider_family(
            provider_id,
            provider_family=provider.get("provider_family"),
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

    def apply_catalog_seed(
        self,
        providers: list[dict[str, Any]],
        models: list[dict[str, Any]],
        *,
        managed_provider_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """Apply a generated catalog with one router-config write.

        Metadata refresh used to call the single-record upsert methods for
        every provider and model. Each call reloaded and atomically rewrote
        the same JSON file, which made the asynchronous job appear stuck on
        Windows and increased the chance of watcher/reader contention. Keep
        the single-record methods for interactive edits, but use one in-memory
        merge for catalog refreshes.
        """
        payload = self._load()
        provider_map = {
            str(item.get("id") or item.get("provider_id") or ""): dict(item)
            for item in list(payload.get("providers") or [])
            if isinstance(item, dict) and str(item.get("id") or item.get("provider_id") or "").strip()
        }
        model_map = {
            str(item.get("id") or ""): dict(item)
            for item in list(payload.get("models") or [])
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        incoming_provider_ids: set[str] = set()
        applied_providers: list[dict[str, Any]] = []

        for provider in list(providers or []):
            if not isinstance(provider, dict):
                continue
            provider_id = str(provider.get("id") or provider.get("provider_id") or "").strip()
            if not provider_id:
                continue
            existing = provider_map.get(provider_id) or {}
            provider_family = _provider_family(
                provider_id,
                provider_family=provider.get("provider_family"),
                adapter_profile=provider.get("adapter_profile"),
                wire_api=provider.get("adapter_type") or provider.get("wire_api"),
                base_url=provider.get("base_url"),
                model=provider.get("default_model") or provider.get("model"),
            )
            registry_profile = get_provider_profile(provider_family) if provider_family else None
            registry_defaults = registry_profile.to_router_provider() if registry_profile else {}
            display_name = str(
                provider.get("display_name")
                or provider.get("label")
                or (registry_profile.display_name if registry_profile else provider_id)
            ).strip()
            default_model = str(
                provider.get("default_model")
                or provider.get("model")
                or (registry_profile.default_model if registry_profile else "")
            ).strip()
            merged_provider = {
                **registry_defaults,
                "id": provider_id,
                "provider_id": provider_id,
                "provider_family": provider_family,
                "display_name": display_name,
                "enabled": bool(provider.get("enabled", True)),
                "adapter_type": str(
                    provider.get("adapter_type")
                    or provider.get("wire_api")
                    or ("responses" if registry_profile and registry_profile.protocol in {"responses", "qwen_responses"} else "responses")
                ),
                "runtime_backend": str(
                    provider.get("runtime_backend")
                    or provider.get("execution_backend")
                    or (registry_profile.runtime_backend if registry_profile else "app_server")
                ),
                "base_url": str(provider.get("base_url") or (registry_profile.base_url if registry_profile else "")).strip(),
                # Catalog seeds are sanitized and omit credentials. Preserve a
                # configured reference instead of accidentally disconnecting a
                # provider during a metadata refresh.
                "auth_key_ref": provider.get("auth_key_ref")
                if provider.get("auth_key_ref") is not None
                else existing.get("auth_key_ref"),
                "default_model": default_model,
                "request_timeout_ms": int(provider.get("request_timeout_ms") or 300000),
                "stream_idle_timeout_ms": int(provider.get("stream_idle_timeout_ms") or 300000),
                "env_key": str(
                    provider.get("env_key")
                    or ((registry_profile.auth.env_vars[0]) if registry_profile and registry_profile.auth.env_vars else "OPENAI_API_KEY")
                ).strip(),
                "auth_mode": str(provider.get("auth_mode") or "os_keychain").strip(),
                "proxy_mode": str(provider.get("proxy_mode") or "direct"),
                "proxy_url": str(provider.get("proxy_url") or ""),
                "logo_source_url": str(provider.get("logo_source_url") or ""),
                "logo_asset_path": str(provider.get("logo_asset_path") or ""),
                "logo_license_note": str(provider.get("logo_license_note") or ""),
                "accent_color": str(provider.get("accent_color") or ""),
                "created_at": existing.get("created_at") or provider.get("created_at") or now_iso(),
                "updated_at": now_iso(),
            }
            provider_map[provider_id] = merged_provider
            incoming_provider_ids.add(provider_id)
            applied_providers.append(merged_provider)

        managed_ids = {str(item).strip() for item in (managed_provider_ids or incoming_provider_ids) if str(item).strip()}
        incoming_model_ids: set[str] = set()
        for model in list(models or []):
            if not isinstance(model, dict):
                continue
            provider_id = str(model.get("provider") or model.get("provider_id") or "").strip()
            native_model = str(model.get("native_model") or "").strip()
            model_id = str(model.get("id") or "").strip()
            if not provider_id and "/" in model_id:
                provider_id, native_model = model_id.split("/", 1)
            if not native_model and "/" in model_id:
                native_model = model_id.split("/", 1)[1]
            if not provider_id or not native_model:
                continue
            model_id = model_id if "/" in model_id else f"{provider_id}/{native_model}"
            provider_family = _provider_family(provider_id, model=native_model)
            base_defaults = _profile_model_defaults(provider_family)
            merged_model = {**base_defaults, **model}
            existing = model_map.get(model_id) or {}
            model_map[model_id] = {
                "id": model_id,
                "provider": provider_id,
                "native_model": native_model,
                "display_name": str(merged_model.get("display_name") or native_model),
                "enabled": bool(merged_model.get("enabled", True)),
                "advertised_context_window": int(merged_model.get("advertised_context_window") or 1000000),
                "ui_context_hint_only": bool(merged_model.get("ui_context_hint_only", True)),
                "adapter_profile": str(merged_model.get("adapter_profile") or "default"),
                **_model_capability_fields(merged_model),
                "created_at": existing.get("created_at") or merged_model.get("created_at") or now_iso(),
                "updated_at": now_iso(),
            }
            incoming_model_ids.add(model_id)

        # Keep user/custom models, but remove stale entries owned by the
        # generated providers exactly as the old per-record path did.
        model_map = {
            model_id: item
            for model_id, item in model_map.items()
            if str(item.get("provider") or "") not in managed_ids or model_id in incoming_model_ids
        }
        for provider_id in incoming_provider_ids:
            provider = provider_map[provider_id]
            default_model = str(provider.get("default_model") or "").strip()
            default_id = f"{provider_id}/{default_model}" if default_model else ""
            if default_id and default_id not in model_map:
                model_map[default_id] = self._default_model(provider, default_model)

        payload["providers"] = sorted(provider_map.values(), key=lambda item: str(item.get("id")))
        payload["models"] = sorted(model_map.values(), key=lambda item: str(item.get("id")))
        write_json(self.store_path, payload)
        for provider in applied_providers:
            self._sync_provider_profile(provider)
        return self.snapshot()

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

    def record_app_server_image_transport_verification(self, model_id: str, verification: dict[str, Any] | None) -> dict[str, Any]:
        payload = self._load()
        models = []
        updated_model: dict[str, Any] | None = None
        for item in payload["models"]:
            if not isinstance(item, dict):
                models.append(item)
                continue
            if str(item.get("id") or "") != str(model_id or "").strip():
                models.append(item)
                continue
            updated = dict(item)
            if verification:
                updated["app_server_image_transport_verification"] = dict(verification)
            else:
                updated.pop("app_server_image_transport_verification", None)
            updated["updated_at"] = now_iso()
            updated_model = updated
            models.append(updated)
        if updated_model is None:
            raise ValueError(f"Unknown model id: {model_id}")
        payload["models"] = models
        write_json(self.store_path, payload)
        providers = payload["providers"]
        return self._refresh_model(
            {
                str(item.get("id") or item.get("provider_id") or ""): dict(item)
                for item in providers
                if isinstance(item, dict)
            },
            updated_model,
        )

    def record_verified_capability_snapshot(self, model_id: str, snapshot: dict[str, Any] | None) -> dict[str, Any]:
        payload = self._load()
        models = []
        updated_model: dict[str, Any] | None = None
        for item in payload["models"]:
            if not isinstance(item, dict):
                models.append(item)
                continue
            if str(item.get("id") or "") != str(model_id or "").strip():
                models.append(item)
                continue
            updated = dict(item)
            if snapshot:
                updated["verified_capability_snapshot"] = dict(snapshot)
            else:
                updated.pop("verified_capability_snapshot", None)
            updated["updated_at"] = now_iso()
            updated_model = updated
            models.append(updated)
        if updated_model is None:
            raise ValueError(f"Unknown model id: {model_id}")
        payload["models"] = models
        write_json(self.store_path, payload)
        providers = payload["providers"]
        return self._refresh_model(
            {
                str(item.get("id") or item.get("provider_id") or ""): dict(item)
                for item in providers
                if isinstance(item, dict)
            },
            updated_model,
        )

    def record_provider_compatibility_matrix(self, matrix: dict[str, Any]) -> dict[str, Any]:
        payload = self._load()
        provider_map = {
            str(item.get("id") or item.get("provider_id") or ""): dict(item)
            for item in list(payload.get("providers") or [])
            if isinstance(item, dict)
        }
        entries_by_model = aggregate_matrix_entries_by_model(matrix)
        models: list[dict[str, Any]] = []
        for item in list(payload.get("models") or []):
            if not isinstance(item, dict):
                continue
            updated = dict(item)
            model_id = str(updated.get("id") or "").strip()
            provider_id = str(updated.get("provider") or "").strip()
            matrix_entries = list(entries_by_model.get(model_id) or [])
            if matrix_entries:
                updated["verified_capability_snapshot"] = build_verified_capability_snapshot(
                    model=updated,
                    provider=dict(provider_map.get(provider_id) or {}),
                    matrix_entries=matrix_entries,
                    created_at=str(matrix.get("generated_at") or matrix.get("created_at") or now_iso()),
                )
                updated["updated_at"] = now_iso()
            models.append(updated)
        payload["models"] = models
        write_json(self.store_path, payload)
        return self.snapshot()

    def export_sanitized(self) -> dict[str, Any]:
        payload = self._load()
        exported = {
            "providers": [],
            "models": self._refresh_models(payload["providers"], payload["models"]),
            "reasoning": payload["reasoning"],
            "capability_routes": payload.get("capability_routes") or {},
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
        current["capability_routes"] = dict(payload.get("capability_routes") or current.get("capability_routes") or {})
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
            "capability_routes": dict(payload.get("capability_routes") or {}),
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
                provider_family=provider_id,
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
            provider_family=provider.get("provider_family"),
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
            provider_family=provider.get("provider_family"),
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
        generated = current_generated_catalog()
        generated_by_id = {
            str(item.get("id") or ""): dict(item)
            for item in generated.models
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        for model_id, existing in list(merged.items()):
            generated_model = generated_by_id.get(model_id)
            if not generated_model or not _should_sync_catalog_managed_modalities(existing, generated.catalog_version):
                continue
            synced = dict(existing)
            for field in CATALOG_MANAGED_MODALITY_SYNC_FIELDS:
                if field in generated_model:
                    synced[field] = generated_model[field]
            # Keep static transport limits from the generated catalog. Only the
            # app-server verification fields are recalculated below; dropping
            # the whole map loses provider-specific image/audio constraints.
            modality_limits = dict(generated_model.get("modality_limits") or {})
            for field in (
                "app_server_image_input_status",
                "app_server_image_transport_signature",
                "app_server_image_last_verified_at",
            ):
                modality_limits.pop(field, None)
            if modality_limits:
                synced["modality_limits"] = modality_limits
            else:
                synced.pop("modality_limits", None)
            synced.pop("ui_warnings", None)
            computed_fields = _model_capability_fields(synced)
            for field in CATALOG_MANAGED_MODALITY_SYNC_FIELDS:
                if field in computed_fields:
                    synced[field] = computed_fields[field]
            merged[model_id] = synced
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
                provider_family=provider.get("provider_family"),
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

    def _refresh_models(self, providers: list[dict[str, Any]], models: list[dict[str, Any]]) -> list[dict[str, Any]]:
        provider_map = {
            str(item.get("id") or item.get("provider_id") or ""): dict(item)
            for item in providers
            if isinstance(item, dict)
        }
        refreshed: list[dict[str, Any]] = []
        for item in models:
            if not isinstance(item, dict):
                continue
            refreshed.append(self._refresh_model(provider_map, dict(item)))
        return refreshed

    def _refresh_model(self, provider_map: dict[str, dict[str, Any]], model: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(model.get("provider") or "")
        provider = dict(provider_map.get(provider_id) or {})
        native_model = str(model.get("native_model") or "")
        provider_family = _provider_family(
            provider.get("provider_family") or model.get("provider_family") or provider_id,
            provider_family=provider.get("provider_family") or model.get("provider_family"),
            adapter_profile=model.get("adapter_profile") or provider.get("adapter_profile"),
            wire_api=provider.get("adapter_type") or provider.get("wire_api"),
            base_url=provider.get("base_url"),
            model=native_model or provider.get("default_model"),
        )
        merged = {**_profile_model_defaults(provider_family), **model}
        refreshed = {
            **model,
            "provider_family": provider_family or model.get("provider_family"),
            **_model_capability_fields(merged),
        }
        refreshed = _apply_app_server_image_transport_status(refreshed, provider=provider)
        return _apply_verified_capability_snapshot_status(refreshed, provider=provider)


def _profile_seed_entries(provider_family: str | None) -> list[dict[str, Any]]:
    if not provider_family:
        return []
    try:
        profile = get_provider_profile(provider_family)
    except ValueError:
        return []
    advertised_context_window = profile.context_window() or 1_000_000
    preferred_models = profile.fallback_policy.fallback_models or profile.fallback_models or (profile.default_model,)
    override_models = tuple(PROFILE_MODEL_SEED_OVERRIDES.get(profile.id, {}).keys())
    seed_entries: list[dict[str, Any]] = []
    seen_models: set[str] = set()
    for native_model in (*preferred_models, *override_models):
        clean_model = str(native_model or "").strip()
        if not clean_model or clean_model in seen_models:
            continue
        seen_models.add(clean_model)
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
            "supports_tool_calls": has_structured_tool_surface(model),
        }
    )
    ui_warnings = list(model.get("ui_warnings") or _default_ui_warnings(model, modalities))
    for warning in authority.ui_warnings:
        if warning not in ui_warnings:
            ui_warnings.append(warning)
    default_route = assess_default_route_verification(model)
    default_multimodal_route = assess_default_route_verification(
        model,
        require_image_input_verified=True,
    )
    # Keep the compact boolean capability fields for older UI/runtime
    # consumers, while allowing a provider-specific transport contract to
    # add richer limits on top.
    modality_limits = {
        **_default_modality_limits(modalities),
        **dict(model.get("modality_limits") or {}),
    }
    if "image" in modalities:
        modality_limits.setdefault("app_server_image_input_status", "unverified")
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
        "native_supported_reasoning_levels": list(model.get("native_supported_reasoning_levels") or model.get("supported_reasoning_levels") or []),
        "native_default_reasoning_level": model.get("native_default_reasoning_level") or model.get("default_reasoning_level"),
        "reasoning_policy_mode": str(model.get("reasoning_policy_mode") or "none"),
        "supports_reasoning_replay": bool(model.get("supports_reasoning_replay", False)),
        "preserve_reasoning_for_tool_turns": bool(model.get("preserve_reasoning_for_tool_turns", False)),
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
        "codex_builtin_tools": dict(model.get("codex_builtin_tools") or default_builtin_tool_support()),
        "planner_support": dict(model.get("planner_support") or default_planner_support()),
        "goal_support": dict(model.get("goal_support") or default_goal_support()),
        "context_compaction_support": dict(model.get("context_compaction_support") or default_context_compaction_support()),
        "modality_limits": modality_limits,
        "ui_warnings": ui_warnings,
        "authority_tier": authority.tier,
        "authority_reason": authority.reason,
        "parallel_tool_call_status": authority.parallel_tool_call_status,
        "command_execution_status": authority.command_execution_status,
        "command_execution_note": authority.command_execution_note,
        "source_urls": list(model.get("source_urls") or []),
        "source_status": str(model.get("source_status") or "seeded"),
        "default_route_verified": bool(default_route.get("verified", False)),
        "default_route_status": str(default_route.get("status") or "warning_gated"),
        "default_route_blockers": list(default_route.get("reasons") or []),
        "default_multimodal_route_verified": bool(default_multimodal_route.get("verified", False)),
        "default_multimodal_route_status": str(default_multimodal_route.get("status") or "warning_gated"),
        "default_multimodal_route_blockers": list(default_multimodal_route.get("reasons") or []),
        "recommended": bool(model.get("recommended", False)) and bool(default_route.get("verified", False)),
        "default_for_provider": bool(model.get("default_for_provider", False)) and bool(default_route.get("verified", False)),
        "deprecated": bool(model.get("deprecated", False)),
        "deprecated_after": model.get("deprecated_after"),
        "confidence": model.get("confidence"),
        "catalog_version": model.get("catalog_version"),
        "source_provenance": dict(model.get("source_provenance") or {}),
        "last_verified_at": model.get("last_verified_at"),
        "verification_notes": str(model.get("verification_notes") or ""),
        "app_server_image_transport_verification": dict(model.get("app_server_image_transport_verification") or {}),
        "verified_capability_snapshot": dict(model.get("verified_capability_snapshot") or {}),
    }


def _apply_app_server_image_transport_status(model: dict[str, Any], *, provider: dict[str, Any]) -> dict[str, Any]:
    refreshed = dict(model)
    modalities = [str(item).strip().lower() for item in list(refreshed.get("input_modalities") or [])]
    if "image" not in modalities:
        return refreshed
    verification = dict(refreshed.get("app_server_image_transport_verification") or {})
    modality_limits = dict(refreshed.get("modality_limits") or {})
    current_contract = _current_app_server_image_transport_contract(refreshed, provider=provider)
    verified = _verification_matches_current_contract(verification, current_contract)
    modality_limits["app_server_image_input_status"] = "verified" if verified else "unverified"
    modality_limits["app_server_image_transport_signature"] = current_contract["transport_signature"]
    if verified:
        modality_limits["app_server_image_last_verified_at"] = verification.get("verified_at")
    else:
        modality_limits.pop("app_server_image_last_verified_at", None)
    refreshed["modality_limits"] = modality_limits
    return refreshed


def _apply_verified_capability_snapshot_status(model: dict[str, Any], *, provider: dict[str, Any]) -> dict[str, Any]:
    refreshed = dict(model)
    snapshot = dict(refreshed.get("verified_capability_snapshot") or {})
    current_contract = current_model_provider_contract(refreshed, provider=provider)
    if snapshot:
        manifest_state = describe_capability_snapshot_manifest(snapshot, current_contract=current_contract)
        verification_state = str(manifest_state.get("verification_state") or "unknown").strip().lower() or "unknown"
        if verification_state in {"verified", "partial", "blocked", "unknown"}:
            refreshed["verified_capability_snapshot_status"] = str(snapshot.get("status") or "unknown").strip().lower() or "unknown"
        else:
            refreshed["verified_capability_snapshot_status"] = "stale"
        refreshed["verified_capability_snapshot_last_verified_at"] = snapshot.get("verified_at")
        refreshed["verified_capability_snapshot_manifest_digest"] = manifest_state.get("digest")
        refreshed["verified_capability_snapshot_freshness_status"] = manifest_state.get("freshness_status")
        refreshed["verified_capability_snapshot_verification_state"] = verification_state
        refreshed["verified_capability_snapshot_expires_at"] = manifest_state.get("expires_at")
    else:
        refreshed["verified_capability_snapshot_status"] = "unverified"
        refreshed["verified_capability_snapshot_last_verified_at"] = None
        refreshed["verified_capability_snapshot_manifest_digest"] = None
        refreshed["verified_capability_snapshot_freshness_status"] = None
        refreshed["verified_capability_snapshot_verification_state"] = "unverified"
        refreshed["verified_capability_snapshot_expires_at"] = None
    refreshed["verified_capability_snapshot_contract"] = current_contract
    return refreshed


def _verification_matches_current_contract(verification: dict[str, Any], current_contract: dict[str, Any]) -> bool:
    if str(verification.get("status") or "").strip().lower() != "verified":
        return False
    required_pairs = {
        "provider_id": str(current_contract.get("provider_id") or ""),
        "model_id": str(current_contract.get("model_id") or ""),
        "native_model": str(current_contract.get("native_model") or ""),
        "runtime_backend": str(current_contract.get("runtime_backend") or ""),
        "transport_adapter": str(current_contract.get("transport_adapter") or ""),
        "transport_signature": str(current_contract.get("transport_signature") or ""),
    }
    for key, expected in required_pairs.items():
        if expected and str(verification.get(key) or "") != expected:
            return False
    return True


def _current_app_server_image_transport_contract(model: dict[str, Any], *, provider: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(model.get("provider") or provider.get("id") or provider.get("provider_id") or "").strip()
    native_model = str(model.get("native_model") or "").strip()
    model_id = str(model.get("id") or (f"{provider_id}/{native_model}" if provider_id and native_model else "")).strip()
    provider_family = _provider_family(
        provider.get("provider_family") or model.get("provider_family") or provider_id,
        provider_family=provider.get("provider_family") or model.get("provider_family"),
        adapter_profile=model.get("adapter_profile") or provider.get("adapter_profile"),
        wire_api=provider.get("adapter_type") or provider.get("wire_api"),
        base_url=provider.get("base_url"),
        model=native_model or provider.get("default_model"),
    )
    profile = {
        "provider_id": provider_id,
        "provider_family": provider_family,
        "adapter_profile": model.get("adapter_profile") or provider.get("adapter_profile") or "default",
        "wire_api": provider.get("adapter_type") or provider.get("wire_api") or "responses",
        "base_url": provider.get("base_url"),
        "model": native_model,
    }
    transport_class = transport_class_for_profile(profile, provider_family=provider_family)
    transport = transport_class(None, profile)
    return {
        "provider_id": provider_id,
        "model_id": model_id,
        "native_model": native_model,
        "runtime_backend": str(provider.get("runtime_backend") or provider.get("execution_backend") or "app_server"),
        "transport_adapter": transport.describe(),
        "transport_signature": transport_signature_for_class(transport_class),
    }


_CAPABILITY_MCP_EXPECTED_TOOLS = (
    "astrabridge_capability_routes",
    "astrabridge_capability_image_generate",
    "astrabridge_capability_vision_analyze",
    "astrabridge_capability_speech_transcribe",
    "astrabridge_capability_speech_synthesize",
)


def _capability_mcp_preset_status(mcp_config: dict[str, Any] | None) -> dict[str, Any]:
    servers = list((mcp_config or {}).get("servers") or [])
    server = next((item for item in servers if str((item or {}).get("name") or "") == "astrabridge_capabilities"), None)
    tools = dict((server or {}).get("tools") or {}) if isinstance(server, dict) else {}
    tool_names = sorted(tools.keys())
    missing_tool_names = [name for name in _CAPABILITY_MCP_EXPECTED_TOOLS if name not in tools]
    configured = server is not None
    enabled = bool((server or {}).get("enabled")) if isinstance(server, dict) else False
    health_status = "missing"
    if configured and not enabled:
        health_status = "disabled"
    elif configured and missing_tool_names:
        health_status = "partial"
    elif configured:
        health_status = "configured"
    return {
        "server_name": "astrabridge_capabilities",
        "configured": configured,
        "enabled": enabled,
        "runtime_visible": None,
        "tool_names": tool_names,
        "expected_tool_names": list(_CAPABILITY_MCP_EXPECTED_TOOLS),
        "missing_tool_names": missing_tool_names,
        "configured_tool_count": len(tool_names),
        "health_status": health_status,
        "approval_modes": {name: dict(config or {}).get("approval_mode") for name, config in tools.items()},
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
    provider_family: Any = None,
    adapter_profile: Any = None,
    wire_api: Any = None,
    base_url: Any = None,
    model: Any = None,
) -> str | None:
    for candidate in (provider_family, adapter_profile, provider_id, wire_api, base_url, model):
        try:
            return resolve_provider_id(str(candidate or "").strip())
        except ValueError:
            continue
    return None


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


def _should_sync_catalog_managed_modalities(model: dict[str, Any], generated_catalog_version: str) -> bool:
    catalog_version = str(model.get("catalog_version") or "").strip()
    if catalog_version and catalog_version == str(generated_catalog_version or "").strip():
        return True
    source_status = str(model.get("source_status") or "").strip().lower()
    return source_status in CATALOG_MANAGED_MODEL_SOURCE_STATUSES

