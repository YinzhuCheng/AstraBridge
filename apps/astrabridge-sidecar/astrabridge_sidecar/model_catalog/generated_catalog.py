from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..common import app_data_dir, now_iso, read_json, write_json
from ..providers import all_provider_profiles, get_provider_profile
from .source_registry import (
    SOURCE_REGISTRY_SCHEMA_VERSION,
    default_provider_source_registry,
    normalize_provider_source_record,
    source_provenance_for_provider_source,
)


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
    return default_provider_source_registry()


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
            verification_notes="AstraBridge direct MCP smoke passed for astrabridge_web on 2026-06-15; keep external MCP tools conservative until model-initiated smoke passes.",
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
            "kimi-k3",
            "Kimi K3",
            recommended=True,
            default_for_provider=True,
            advertised_context_window=1_048_576,
            supported_reasoning_levels=["low", "high", "xhigh"],
            default_reasoning_level="xhigh",
            native_supported_reasoning_levels=["low", "high", "max"],
            native_default_reasoning_level="max",
            reasoning_effort_mapping={"low": "low", "high": "high", "xhigh": "max"},
            input_modalities=["text", "image", "video"],
            modality_limits={
                "image_transport": "chat_completions_base64_image_url_or_ms_uri",
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
            "kimi-k2.7-code",
            "Kimi K2.7 Code",
            recommended=False,
            default_for_provider=False,
            advertised_context_window=256_000,
            supported_reasoning_levels=["low", "medium", "high", "xhigh"],
            default_reasoning_level="high",
            native_supported_reasoning_levels=["low", "medium", "high", "xhigh"],
            native_default_reasoning_level="high",
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
            default_for_provider=False,
            advertised_context_window=256_000,
            supported_reasoning_levels=["off", "low", "medium", "high", "xhigh"],
            default_reasoning_level="high",
            native_supported_reasoning_levels=["off", "low", "medium", "high", "xhigh"],
            native_default_reasoning_level="high",
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
            "kimi",
            "kimi-k2.7-code-highspeed",
            "Kimi K2.7 Code Highspeed",
            default_for_provider=False,
            advertised_context_window=256_000,
            supported_reasoning_levels=["low", "medium", "high", "xhigh"],
            default_reasoning_level="high",
            native_supported_reasoning_levels=["low", "medium", "high", "xhigh"],
            native_default_reasoning_level="high",
            input_modalities=["text", "image"],
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
            input_modalities=["text", "image"],
            modality_limits={
                "image_transport": "chat_completions_image_url_or_data_uri",
                "remote_image_url_supported": True,
                "min_image_side_px": 11,
            },
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
            input_modalities=["text", "image"],
            modality_limits={
                "image_transport": "chat_completions_image_url_or_data_uri",
                "remote_image_url_supported": True,
                "min_image_side_px": 11,
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen3-vl-plus",
            "Qwen3 VL Plus",
            default_for_provider=False,
            input_modalities=["text", "image"],
            modality_limits={
                "image_transport": "chat_completions_image_url_or_data_uri",
                "remote_image_url_supported": True,
                "min_image_side_px": 11,
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen3-vl-flash",
            "Qwen3 VL Flash",
            default_for_provider=False,
            input_modalities=["text", "image"],
            modality_limits={
                "image_transport": "chat_completions_image_url_or_data_uri",
                "remote_image_url_supported": True,
                "min_image_side_px": 11,
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen-image-plus",
            "Qwen Image Plus",
            default_for_provider=False,
            input_modalities=["text"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            source_status="official_docs",
            confidence="high",
            verification_notes="Official DashScope image-generation docs-backed model intended for the dashscope_image family.",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen3-asr-flash",
            "Qwen3 ASR Flash",
            default_for_provider=False,
            input_modalities=["text", "audio"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            modality_limits={
                "audio_transport": "chat_completions_input_audio_data_uri",
                "mixed_text_prompt_forwarding": False,
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen3-tts-flash",
            "Qwen3 TTS Flash",
            default_for_provider=False,
            input_modalities=["text"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            modality_limits={
                "tts_family": "dashscope_http_sse",
                "tts_protocol_profile": "qwen_multimodal_generation",
                "tts_instruction_field": "instructions",
                "tts_voice_mode": "system_voice_or_named_voice",
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "qwen3-tts-instruct-flash",
            "Qwen3 TTS Instruct Flash",
            default_for_provider=False,
            input_modalities=["text"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            modality_limits={
                "tts_family": "dashscope_http_sse",
                "tts_protocol_profile": "qwen_multimodal_generation",
                "tts_instruction_field": "instructions",
                "tts_voice_mode": "system_voice_or_named_voice",
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "cosyvoice-v2",
            "CosyVoice V2",
            default_for_provider=False,
            input_modalities=["text"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            modality_limits={
                "tts_family": "dashscope_http_sse",
                "tts_protocol_profile": "cosyvoice_speech_synthesizer",
                "tts_voice_requirement": "explicit_voice_required",
                "tts_instruction_field": "instruction",
                "tts_system_voice_support": "supported",
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "cosyvoice-v3-flash",
            "CosyVoice V3 Flash",
            default_for_provider=False,
            input_modalities=["text"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            modality_limits={
                "tts_family": "dashscope_http_sse",
                "tts_protocol_profile": "cosyvoice_speech_synthesizer",
                "tts_voice_requirement": "explicit_voice_required",
                "tts_instruction_field": "instruction",
                "tts_system_voice_support": "supported",
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "cosyvoice-v3-plus",
            "CosyVoice V3 Plus",
            default_for_provider=False,
            input_modalities=["text"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            modality_limits={
                "tts_family": "dashscope_http_sse",
                "tts_protocol_profile": "cosyvoice_speech_synthesizer",
                "tts_voice_requirement": "explicit_voice_required",
                "tts_instruction_field": "instruction",
                "tts_system_voice_support": "supported",
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "cosyvoice-v3.5-flash",
            "CosyVoice V3.5 Flash",
            default_for_provider=False,
            input_modalities=["text"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            modality_limits={
                "tts_family": "dashscope_http_sse",
                "tts_protocol_profile": "cosyvoice_speech_synthesizer",
                "tts_voice_requirement": "explicit_voice_required",
                "tts_instruction_field": "instruction",
                "tts_system_voice_support": "unsupported",
            },
            source_status="official_docs",
            confidence="high",
        ),
        _seed_model_from_profile(
            "qwen",
            "cosyvoice-v3.5-plus",
            "CosyVoice V3.5 Plus",
            default_for_provider=False,
            input_modalities=["text"],
            supported_reasoning_levels=["off"],
            default_reasoning_level="off",
            modality_limits={
                "tts_family": "dashscope_http_sse",
                "tts_protocol_profile": "cosyvoice_speech_synthesizer",
                "tts_voice_requirement": "explicit_voice_required",
                "tts_instruction_field": "instruction",
                "tts_system_voice_support": "unsupported",
            },
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
    source_records = [normalize_provider_source_record(dict(item)) for item in (sources or default_catalog_sources())]
    provider_records = [dict(item) for item in (providers or default_seed_providers())]
    model_records = []
    source_map = {str(item.get("provider_id") or ""): dict(item) for item in source_records}
    for item in (models or default_seed_models()):
        model = dict(item)
        provider_id = str(model.get("provider") or "")
        source = source_map.get(provider_id, {})
        model.setdefault("source_urls", list(source.get("urls") or []))
        model.setdefault("source_status", source.get("source_status") or "seeded")
        model.setdefault("source_provenance", source_provenance_for_provider_source(source) if source else {"provider_id": provider_id, "source_status": model.get("source_status")})
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
        "source_registry_schema": SOURCE_REGISTRY_SCHEMA_VERSION,
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
    sources = [normalize_provider_source_record(dict(item)) for item in list(sources_payload.get("sources") or []) if isinstance(item, dict)]
    generated_at = str(models_payload.get("generated_at") or sources_payload.get("generated_at") or "")
    seed_records = [item for item in default_seed_models() if str(item.get("id") or "").strip()]
    default_seed_ids = {str(item.get("id") or "").strip() for item in seed_records}
    seed_by_id = {str(item.get("id") or "").strip(): dict(item) for item in seed_records}
    stored_model_ids = {str(item.get("id") or "").strip() for item in models if str(item.get("id") or "").strip()}
    stored_by_id = {str(item.get("id") or "").strip(): dict(item) for item in models if str(item.get("id") or "").strip()}
    if (
        not models
        or not sources
        or not default_seed_ids.issubset(stored_model_ids)
        or not _stored_models_match_seed_defaults(stored_by_id, seed_by_id)
    ):
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


def _stored_models_match_seed_defaults(
    stored_by_id: dict[str, dict[str, Any]],
    seed_by_id: dict[str, dict[str, Any]],
) -> bool:
    for model_id, seed in seed_by_id.items():
        stored = stored_by_id.get(model_id)
        if not stored:
            return False
        for field in (
            "advertised_context_window",
            "input_modalities",
            "supported_reasoning_levels",
            "default_reasoning_level",
            "native_supported_reasoning_levels",
            "native_default_reasoning_level",
            "reasoning_effort_mapping",
            "recommended",
            "default_for_provider",
            "deprecated",
            "deprecated_after",
            "modality_limits",
        ):
            if stored.get(field) != seed.get(field):
                return False
    return True
