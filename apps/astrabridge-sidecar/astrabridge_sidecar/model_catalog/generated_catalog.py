from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..common import app_data_dir, now_iso, read_json, write_json
from ..providers import all_provider_profiles, get_provider_profile


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
    return [dict(profile.to_catalog_provider()) for profile in all_provider_profiles()]


def _seed_model_from_profile(
    provider_id: str,
    native_model: str,
    display_name: str,
    **overrides: Any,
) -> dict[str, Any]:
    profile_defaults = dict(get_provider_profile(provider_id).to_model_defaults())
    return {
        "id": f"{provider_id}/{native_model}",
        "provider": provider_id,
        "native_model": native_model,
        "display_name": display_name,
        "enabled": True,
        **profile_defaults,
        **overrides,
    }


def default_seed_models() -> list[dict[str, Any]]:
    return [
        _seed_model_from_profile(
            "yunwu",
            "gpt-5.5",
            "GPT-5.5",
            recommended=True,
            default_for_provider=True,
            source_status="screenshot_seed",
            confidence="medium",
            verification_notes="Seeded from Yunwu screenshot and aligned conservatively with OpenAI same-name docs.",
        ),
        _seed_model_from_profile(
            "openai",
            "gpt-5.5",
            "GPT-5.5",
            recommended=True,
            default_for_provider=True,
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "deepseek",
            "deepseek-v4-pro",
            "DeepSeek V4 Pro",
            recommended=True,
            default_for_provider=True,
            source_status="official_docs",
            confidence="high",
            verification_notes="AstraBridge direct MCP smoke passed for lcr_web on 2026-06-15; keep arbitrary external MCP tools conservative until model-initiated smoke passes.",
        ),
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
        _seed_model_from_profile(
            "kimi",
            "kimi-k2.7-code",
            "Kimi K2.7 Code",
            recommended=True,
            default_for_provider=False,
            modality_limits={
                "image_transport": "chat_completions_base64_image_url",
                "remote_image_url_supported": False,
                "supported_image_formats": ["png", "jpeg", "webp", "gif"],
                "request_body_limit_mb": 100,
                "video_input": "provider_supported_unverified_in_astrabridge",
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "kimi",
            "kimi-k2.6",
            "Kimi K2.6",
            default_for_provider=True,
            input_modalities=["text", "image", "video"],
            modality_limits={
                "image_transport": "chat_completions_base64_image_url",
                "remote_image_url_supported": False,
                "supported_image_formats": ["png", "jpeg", "webp", "gif"],
                "request_body_limit_mb": 100,
                "video_input": "provider_supported_unverified_in_astrabridge",
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen3.7-plus",
            "Qwen3.7 Plus",
            recommended=True,
            default_for_provider=True,
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen3.7-max-2026-06-08",
            "Qwen3.7 Max 2026-06-08",
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen3.6-flash",
            "Qwen3.6 Flash",
            supported_reasoning_levels=["low", "medium", "high"],
            default_reasoning_level="medium",
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "glm",
            "glm-5.2",
            "GLM 5.2",
            recommended=True,
            default_for_provider=True,
            source_status="official_docs",
            confidence="medium",
            verification_notes="Official Z.AI pricing/docs surface GLM-5.2 as the flagship 1M-context model as of 2026-06-21.",
        ),
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
