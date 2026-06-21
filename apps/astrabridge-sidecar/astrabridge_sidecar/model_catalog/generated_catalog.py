from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..common import app_data_dir, now_iso, read_json, write_json


GENERATED_CATALOG_SCHEMA = "astrabridge-generated-catalog-v1"
GENERATED_MODELS_LOCK_FILENAME = "models.lock.json"
GENERATED_SOURCES_LOCK_FILENAME = "sources.lock.json"
GENERATED_REVIEW_FILENAME = "review.md"


def catalog_generated_dir(root: Path | None = None) -> Path:
    return (root or (app_data_dir() / "model_catalog")) / "generated"


@dataclass
class GeneratedCatalog:
    providers: list[dict[str, Any]]
    models: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    generated_at: str
    catalog_version: str
    review_path: str
    models_lock_path: str
    sources_lock_path: str


def default_catalog_sources() -> list[dict[str, Any]]:
    return [
        {
            "provider_id": "yunwu",
            "display_name": "Yunwu",
            "urls": [
                "https://yunwu.apifox.cn/api-232421952",
                "https://yunwu.apifox.cn/api-425475208",
                "https://yunwu.apifox.cn/api-425481728",
                "https://yunwu.ai/pricing?group=Codex%E4%B8%93%E5%B1%9E",
            ],
            "source_status": "screenshot_seed",
            "notes": "Apifox pages were not readable through the current fetcher; keep screenshot seed and manual verification notes.",
        },
        {
            "provider_id": "openai",
            "display_name": "OpenAI",
            "urls": [
                "https://developers.openai.com/api/docs/models",
                "https://platform.openai.com/docs/guides/reasoning",
            ],
            "source_status": "official_docs",
            "notes": "OpenAI stays as a normal API-key provider only. No official account login path.",
        },
        {
            "provider_id": "deepseek",
            "display_name": "DeepSeek",
            "urls": [
                "https://api-docs.deepseek.com/quick_start/pricing",
                "https://api-docs.deepseek.com/api/list-models",
            ],
            "source_status": "official_docs",
            "notes": "V4 line is the active AstraBridge coding baseline as of 2026-06-21.",
        },
        {
            "provider_id": "kimi",
            "display_name": "Kimi",
            "urls": [
                "https://platform.moonshot.ai/docs/overview",
                "https://platform.moonshot.ai/docs/guide/start-using-kimi-api",
                "https://platform.kimi.com/docs/api/overview",
                "https://platform.kimi.com/docs/pricing/chat",
            ],
            "source_status": "official_docs",
            "notes": "K2.7 Code is the preferred coding lane; K2.6 remains available.",
        },
        {
            "provider_id": "qwen",
            "display_name": "Qwen / DashScope",
            "urls": [
                "https://help.aliyun.com/zh/model-studio/models",
                "https://help.aliyun.com/zh/model-studio/newly-released-models",
                "https://help.aliyun.com/zh/model-studio/text-generation-model/",
                "https://help.aliyun.com/zh/model-studio/vision",
            ],
            "source_status": "official_docs",
            "notes": "Qwen3.7 Plus is the balanced default; Qwen3.7 Max remains the strongest reasoning tier.",
        },
        {
            "provider_id": "glm",
            "display_name": "GLM / Z.AI",
            "urls": [
                "https://open.bigmodel.cn/dev/api",
                "https://open.bigmodel.cn/pricing",
            ],
            "source_status": "official_docs",
            "notes": "Official pricing/docs surface GLM-5.2 as the flagship 1M-context model.",
        },
    ]


def default_seed_providers() -> list[dict[str, Any]]:
    return [
        {
            "id": "yunwu",
            "display_name": "Yunwu",
            "enabled": True,
            "adapter_type": "responses",
            "base_url": "https://yunwu.ai/v1",
            "default_model": "gpt-5.5",
            "env_key": "YUNWU_API_KEY",
            "auth_mode": "env_ref",
            "proxy_mode": "direct",
            "proxy_url": "",
        },
        {
            "id": "openai",
            "display_name": "OpenAI",
            "enabled": True,
            "adapter_type": "responses",
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-5.5",
            "env_key": "OPENAI_API_KEY",
            "auth_mode": "env_ref",
            "proxy_mode": "direct",
            "proxy_url": "",
        },
        {
            "id": "deepseek",
            "display_name": "DeepSeek",
            "enabled": True,
            "adapter_type": "chat",
            "base_url": "https://api.deepseek.com",
            "default_model": "deepseek-v4-pro",
            "env_key": "DEEPSEEK_API_KEY",
            "auth_mode": "env_ref",
            "proxy_mode": "direct",
            "proxy_url": "",
        },
        {
            "id": "kimi",
            "display_name": "Kimi",
            "enabled": True,
            "adapter_type": "chat",
            "base_url": "https://api.moonshot.cn/v1",
            "default_model": "kimi-k2.6",
            "env_key": "KIMI_API_KEY",
            "auth_mode": "env_ref",
            "proxy_mode": "direct",
            "proxy_url": "",
        },
        {
            "id": "qwen",
            "display_name": "Qwen / DashScope",
            "enabled": True,
            "adapter_type": "responses",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen3.7-plus",
            "env_key": "DASHSCOPE_API_KEY",
            "auth_mode": "env_ref",
            "proxy_mode": "direct",
            "proxy_url": "",
        },
        {
            "id": "glm",
            "display_name": "GLM / Z.AI",
            "enabled": True,
            "adapter_type": "chat",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "default_model": "glm-5.2",
            "env_key": "GLM_API_KEY",
            "auth_mode": "env_ref",
            "proxy_mode": "direct",
            "proxy_url": "",
        },
    ]


def default_seed_models() -> list[dict[str, Any]]:
    return [
        {
            "id": "yunwu/gpt-5.5",
            "provider": "yunwu",
            "native_model": "gpt-5.5",
            "display_name": "GPT-5.5",
            "enabled": True,
            "recommended": True,
            "default_for_provider": True,
            "advertised_context_window": 1_000_000,
            "supported_reasoning_levels": ["none", "low", "medium", "high", "xhigh"],
            "default_reasoning_level": "high",
            "source_status": "screenshot_seed",
            "confidence": "medium",
            "verification_notes": "Seeded from Yunwu screenshot and aligned conservatively with OpenAI same-name docs.",
        },
        {
            "id": "openai/gpt-5.5",
            "provider": "openai",
            "native_model": "gpt-5.5",
            "display_name": "GPT-5.5",
            "enabled": True,
            "recommended": True,
            "default_for_provider": True,
            "advertised_context_window": 1_000_000,
            "supported_reasoning_levels": ["none", "low", "medium", "high", "xhigh"],
            "default_reasoning_level": "high",
            "source_status": "official_docs",
            "confidence": "high",
        },
        {
            "id": "deepseek/deepseek-v4-pro",
            "provider": "deepseek",
            "native_model": "deepseek-v4-pro",
            "display_name": "DeepSeek V4 Pro",
            "enabled": True,
            "recommended": True,
            "default_for_provider": True,
            "advertised_context_window": 1_000_000,
            "supported_reasoning_levels": ["high", "xhigh", "max"],
            "default_reasoning_level": "xhigh",
            "supports_mcp_tools": True,
            "mcp_tool_call_policy": "conservative",
            "mcp_verified_servers": ["lcr_web"],
            "mcp_smoke_status": "pass_direct_tool_call",
            "mcp_tool_argument_validation": "router_repair",
            "tool_web_search_support": "verified",
            "mcp_web_support": "verified_lcr_web",
            "web_smoke_status": "pass_direct_tool_call",
            "citation_quality": "requires_explicit_url_instruction",
            "source_status": "official_docs",
            "confidence": "high",
            "verification_notes": "AstraBridge direct MCP smoke passed for lcr_web on 2026-06-15; keep arbitrary external MCP tools conservative until model-initiated smoke passes.",
        },
        {
            "id": "deepseek/deepseek-v4-flash",
            "provider": "deepseek",
            "native_model": "deepseek-v4-flash",
            "display_name": "DeepSeek V4 Flash",
            "enabled": True,
            "advertised_context_window": 1_000_000,
            "supported_reasoning_levels": ["off", "high"],
            "default_reasoning_level": "high",
            "source_status": "official_docs",
            "confidence": "high",
        },
        {
            "id": "deepseek/deepseek-chat",
            "provider": "deepseek",
            "native_model": "deepseek-chat",
            "display_name": "DeepSeek Chat",
            "enabled": True,
            "deprecated": True,
            "deprecated_after": "2026-07-24T15:59:00+00:00",
            "advertised_context_window": 128_000,
            "supported_reasoning_levels": ["off"],
            "default_reasoning_level": "off",
            "source_status": "official_docs",
            "confidence": "high",
            "verification_notes": "Deprecated in official docs in favor of DeepSeek-V4-Flash non-thinking mode.",
        },
        {
            "id": "deepseek/deepseek-reasoner",
            "provider": "deepseek",
            "native_model": "deepseek-reasoner",
            "display_name": "DeepSeek Reasoner",
            "enabled": True,
            "deprecated": True,
            "deprecated_after": "2026-07-24T15:59:00+00:00",
            "advertised_context_window": 128_000,
            "supported_reasoning_levels": ["high"],
            "default_reasoning_level": "high",
            "source_status": "official_docs",
            "confidence": "high",
            "verification_notes": "Deprecated in official docs in favor of DeepSeek-V4-Flash thinking mode.",
        },
        {
            "id": "kimi/kimi-k2.7-code",
            "provider": "kimi",
            "native_model": "kimi-k2.7-code",
            "display_name": "Kimi K2.7 Code",
            "enabled": True,
            "recommended": True,
            "default_for_provider": False,
            "advertised_context_window": 256_000,
            "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
            "default_reasoning_level": "high",
            "provider_temperature_min": 1.0,
            "provider_temperature_max": 1.0,
            "temperature_adapter_policy": "kimi_only_temperature_1",
            "modality_limits": {
                "image_transport": "chat_completions_base64_image_url",
                "remote_image_url_supported": False,
                "supported_image_formats": ["png", "jpeg", "webp", "gif"],
                "request_body_limit_mb": 100,
                "video_input": "provider_supported_unverified_in_astrabridge",
            },
            "source_status": "official_docs",
            "confidence": "high",
        },
        {
            "id": "kimi/kimi-k2.6",
            "provider": "kimi",
            "native_model": "kimi-k2.6",
            "display_name": "Kimi K2.6",
            "enabled": True,
            "default_for_provider": True,
            "advertised_context_window": 256_000,
            "input_modalities": ["text", "image", "video"],
            "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
            "default_reasoning_level": "high",
            "provider_temperature_min": 1.0,
            "provider_temperature_max": 1.0,
            "temperature_adapter_policy": "kimi_only_temperature_1",
            "modality_limits": {
                "image_transport": "chat_completions_base64_image_url",
                "remote_image_url_supported": False,
                "supported_image_formats": ["png", "jpeg", "webp", "gif"],
                "request_body_limit_mb": 100,
                "video_input": "provider_supported_unverified_in_astrabridge",
            },
            "source_status": "official_docs",
            "confidence": "high",
        },
        {
            "id": "qwen/qwen3.7-plus",
            "provider": "qwen",
            "native_model": "qwen3.7-plus",
            "display_name": "Qwen3.7 Plus",
            "enabled": True,
            "recommended": True,
            "default_for_provider": True,
            "advertised_context_window": 1_000_000,
            "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
            "default_reasoning_level": "high",
            "provider_temperature_min": 0.00001,
            "provider_temperature_max": 1.0,
            "temperature_adapter_policy": "qwen_omit_zero_clamp_1",
            "source_status": "official_docs",
            "confidence": "high",
        },
        {
            "id": "qwen/qwen3.7-max-2026-06-08",
            "provider": "qwen",
            "native_model": "qwen3.7-max-2026-06-08",
            "display_name": "Qwen3.7 Max 2026-06-08",
            "enabled": True,
            "advertised_context_window": 1_000_000,
            "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
            "default_reasoning_level": "high",
            "provider_temperature_min": 0.00001,
            "provider_temperature_max": 1.0,
            "temperature_adapter_policy": "qwen_omit_zero_clamp_1",
            "source_status": "official_docs",
            "confidence": "high",
        },
        {
            "id": "qwen/qwen3.6-flash",
            "provider": "qwen",
            "native_model": "qwen3.6-flash",
            "display_name": "Qwen3.6 Flash",
            "enabled": True,
            "advertised_context_window": 1_000_000,
            "supported_reasoning_levels": ["low", "medium", "high"],
            "default_reasoning_level": "medium",
            "provider_temperature_min": 0.00001,
            "provider_temperature_max": 1.0,
            "temperature_adapter_policy": "qwen_omit_zero_clamp_1",
            "source_status": "official_docs",
            "confidence": "high",
        },
        {
            "id": "glm/glm-5.2",
            "provider": "glm",
            "native_model": "glm-5.2",
            "display_name": "GLM 5.2",
            "enabled": True,
            "recommended": True,
            "default_for_provider": True,
            "advertised_context_window": 1_000_000,
            "input_modalities": ["text", "image"],
            "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
            "default_reasoning_level": "high",
            "source_status": "official_docs",
            "confidence": "medium",
            "verification_notes": "Official Z.AI pricing/docs surface GLM-5.2 as the flagship 1M-context model as of 2026-06-21.",
        },
    ]


def build_generated_catalog(
    *,
    sources: list[dict[str, Any]] | None = None,
    providers: list[dict[str, Any]] | None = None,
    models: list[dict[str, Any]] | None = None,
    output_root: Path | None = None,
    fetched: list[dict[str, Any]] | None = None,
) -> GeneratedCatalog:
    generated_at = now_iso()
    source_records = [dict(item) for item in (sources or default_catalog_sources())]
    provider_records = [dict(item) for item in (providers or default_seed_providers())]
    model_records = []
    source_map = {str(item.get("provider_id") or ""): dict(item) for item in source_records}
    for item in (models or default_seed_models()):
        model = dict(item)
        provider_id = str(model.get("provider") or "")
        source = source_map.get(provider_id, {})
        model.setdefault("source_urls", list(source.get("urls") or []))
        model.setdefault("source_status", source.get("source_status") or "seeded")
        model.setdefault("source_provenance", {"provider_id": provider_id, "source_status": model.get("source_status")})
        model.setdefault("catalog_version", GENERATED_CATALOG_SCHEMA)
        model_records.append(model)
    out_dir = catalog_generated_dir(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    models_lock_path = out_dir / GENERATED_MODELS_LOCK_FILENAME
    sources_lock_path = out_dir / GENERATED_SOURCES_LOCK_FILENAME
    review_path = out_dir / GENERATED_REVIEW_FILENAME
    models_lock = {
        "schema_version": GENERATED_CATALOG_SCHEMA,
        "generated_at": generated_at,
        "models": model_records,
    }
    sources_lock = {
        "schema_version": GENERATED_CATALOG_SCHEMA,
        "generated_at": generated_at,
        "sources": source_records,
        "fetch_status": list(fetched or []),
    }
    review_lines = [
        "# AstraBridge Catalog Review",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Providers: `{len(provider_records)}`",
        f"- Models: `{len(model_records)}`",
        "",
        "## Notes",
        "",
    ]
    for source in source_records:
        review_lines.append(
            f"- `{source.get('provider_id')}`: `{source.get('source_status')}` - {str(source.get('notes') or '').strip()}"
        )
    write_json(models_lock_path, models_lock)
    write_json(sources_lock_path, sources_lock)
    review_path.write_text("\n".join(review_lines).strip() + "\n", encoding="utf-8", newline="\n")
    return GeneratedCatalog(
        providers=provider_records,
        models=model_records,
        sources=source_records,
        generated_at=generated_at,
        catalog_version=GENERATED_CATALOG_SCHEMA,
        review_path=str(review_path),
        models_lock_path=str(models_lock_path),
        sources_lock_path=str(sources_lock_path),
    )


def current_generated_catalog(output_root: Path | None = None) -> GeneratedCatalog:
    out_dir = catalog_generated_dir(output_root)
    models_payload = read_json(out_dir / GENERATED_MODELS_LOCK_FILENAME, {})
    sources_payload = read_json(out_dir / GENERATED_SOURCES_LOCK_FILENAME, {})
    models = [dict(item) for item in list(models_payload.get("models") or []) if isinstance(item, dict)]
    sources = [dict(item) for item in list(sources_payload.get("sources") or []) if isinstance(item, dict)]
    generated_at = str(models_payload.get("generated_at") or sources_payload.get("generated_at") or "")
    if not models or not sources:
        return build_generated_catalog(output_root=output_root)
    return GeneratedCatalog(
        providers=default_seed_providers(),
        models=models,
        sources=sources,
        generated_at=generated_at or now_iso(),
        catalog_version=str(models_payload.get("schema_version") or GENERATED_CATALOG_SCHEMA),
        review_path=str(out_dir / GENERATED_REVIEW_FILENAME),
        models_lock_path=str(out_dir / GENERATED_MODELS_LOCK_FILENAME),
        sources_lock_path=str(out_dir / GENERATED_SOURCES_LOCK_FILENAME),
    )
