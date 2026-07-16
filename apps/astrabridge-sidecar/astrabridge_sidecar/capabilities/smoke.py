from __future__ import annotations

import base64
import io
import math
import re
import struct
import time
from typing import Any
import wave
import zlib

from ..common import now_iso
from ..usage_signal import normalize_usage_signal
from .capability_routes import resolve_capability_route_entry
from .capability_registry import default_capability_registry


CAPABILITY_SMOKE_SCHEMA_VERSION = "astrabridge-capability-smoke-result-v1"

_DRY_RUN_FIXTURES: dict[str, dict[str, Any]] = {
    "image.generate": {
        "case_id": "dry_run_image_generate",
        "sample_input": {"prompt": "AstraBridge capability smoke test image prompt.", "n": 1, "size": "1024x1024"},
        "sample_output": {"artifact_refs": [{"artifact_type": "image", "status": "fixture_only"}], "revised_prompt": None},
    },
    "vision.analyze": {
        "case_id": "dry_run_vision_analyze",
        "sample_input": {"prompt": "Read the title in the fixture image.", "image_inputs": [{"fixture": "astrabridge-title-card"}]},
        "sample_output": {"text": "AstraBridge vision smoke fixture recognized.", "annotations": []},
    },
    "speech.transcribe": {
        "case_id": "dry_run_speech_transcribe",
        "sample_input": {"audio_inputs": [{"fixture": "astrabridge-speech-smoke.wav"}], "language_hint": "en"},
        "sample_output": {"text": "This is an AstraBridge speech recognition smoke test.", "segments": []},
    },
    "speech.synthesize": {
        "case_id": "dry_run_speech_synthesize",
        "sample_input": {"text": "AstraBridge speech synthesis smoke test.", "voice": "fixture"},
        "sample_output": {"artifact_refs": [{"artifact_type": "audio", "status": "fixture_only"}], "mime_type": "audio/wav"},
    },
}


def capability_smoke_snapshot(
    payload: dict[str, Any],
    *,
    configured_models: list[dict[str, Any]] | None = None,
    route_record: dict[str, Any] | None = None,
    runtime: Any | None = None,
) -> dict[str, Any]:
    capability_id = str(payload.get("capability_id") or "").strip()
    mode = str(payload.get("mode") or "dry_run").strip().lower() or "dry_run"
    allow_provider = bool(payload.get("allow_provider", False))
    registry = default_capability_registry()
    if not capability_id:
        raise ValueError("capability_id is required.")
    spec = registry.capability_spec(capability_id)
    if spec.lane_type != "model_backed":
        raise ValueError(f"Capability {capability_id} is not model-backed and does not support manual provider smoke.")
    if capability_id not in _DRY_RUN_FIXTURES:
        raise ValueError(f"Capability {capability_id} does not have a dry-run smoke fixture.")
    if mode != "dry_run" and not allow_provider:
        raise ValueError("Provider-backed smoke requires allow_provider=true.")

    fixture = dict(_DRY_RUN_FIXTURES[capability_id])
    route = _resolve_smoke_route(
        capability_id,
        payload,
        configured_models=configured_models,
        route_record=route_record,
        registry=registry,
    )
    candidate = dict(route.get("resolved_candidate") or {})
    provider_requested = mode != "dry_run"
    provider_result: dict[str, Any] | None = None
    provider_error = ""
    provider_invoked = False
    elapsed_ms: int | None = None
    status = "pass" if mode == "dry_run" else "provider_not_run"
    provider_sample_input = fixture["sample_input"]
    provider_notes = [
        "Dry-run smoke validates the capability contract, routing state, and UI wiring without invoking a provider.",
    ]
    artifact_refs: list[dict[str, Any]] = []
    evidence_refs: list[dict[str, Any]] = []
    if provider_requested and runtime is not None:
        actual_payload, provider_sample_input = _provider_smoke_payload(capability_id, payload)
        started = time.perf_counter()
        try:
            provider_result = runtime.invoke(capability_id, actual_payload)
            provider_invoked = True
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            route = _route_from_provider_result(provider_result, fallback_route=route)
            candidate = dict(route.get("resolved_candidate") or {})
            status, provider_notes = _provider_status_notes(capability_id, provider_result)
            artifact_refs = _sanitize_artifact_refs(provider_result.get("artifact_refs") or [])
            evidence_refs = _evidence_refs_from_artifacts(artifact_refs)
        except Exception as exc:  # noqa: BLE001 - smoke should preserve failure as data for the UI.
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            provider_error = _safe_error_message(exc)
            provider_invoked = not _looks_like_local_provider_blocker(provider_error)
            status = "fail"
            provider_notes = ["Provider smoke was requested and failed; inspect the sanitized error before retrying."]
    usage_reason = None
    if not provider_requested:
        usage_reason = "dry_run_no_provider_call"
    elif provider_result is None:
        usage_reason = "provider_smoke_failed"
    elif not isinstance(provider_result.get("usage"), dict):
        usage_reason = "provider_result_usage_not_reported"
    return {
        "schema_version": CAPABILITY_SMOKE_SCHEMA_VERSION,
        "capability_id": capability_id,
        "mode": mode,
        "status": status,
        "provider_invoked": provider_invoked,
        "provider_requested": provider_requested,
        "case_id": fixture["case_id"],
        "route": {
            "route_mode": route.get("route_mode"),
            "resolution_status": route.get("resolution_status"),
            "resolved_candidate": candidate or None,
            "error": route.get("error"),
        },
        "sanitized_request": {
            "capability_id": capability_id,
            "mode": mode,
            "allow_provider": allow_provider,
            "sample_input": provider_sample_input,
        },
        "sanitized_response": {
            "sample_output": fixture["sample_output"] if not provider_result else None,
            "provider_result": _sanitize_provider_result(provider_result) if provider_result else None,
            "provider_error": provider_error or None,
            "elapsed_ms": elapsed_ms,
            "notes": provider_notes,
        },
        "artifact_refs": artifact_refs,
        "evidence_refs": evidence_refs,
        "usage_signal": normalize_usage_signal(
            source="capability_smoke",
            provider_id=candidate.get("provider_id"),
            model=candidate.get("model"),
            usage=(provider_result or {}).get("usage") if isinstance(provider_result, dict) else None,
            reason=usage_reason,
            request_kind=capability_id,
        ),
        "created_at": now_iso(),
    }


def _resolve_smoke_route(
    capability_id: str,
    payload: dict[str, Any],
    *,
    configured_models: list[dict[str, Any]] | None,
    route_record: dict[str, Any] | None,
    registry: Any,
) -> dict[str, Any]:
    provider_override = _clean_route_text(payload.get("provider_id"))
    model_override = _clean_route_text(payload.get("model"))
    if provider_override or model_override:
        candidates = registry.resolve_candidates(capability_id, configured_models)
        for candidate in candidates:
            if provider_override and _clean_route_text(candidate.get("provider_id")) != provider_override:
                continue
            if model_override and _clean_route_text(candidate.get("model")) != model_override:
                continue
            return {
                "capability_id": capability_id,
                "route_mode": "explicit",
                "resolution_status": "ok",
                "resolved_candidate": dict(candidate),
                "candidates": candidates,
                "error": None,
            }
        return {
            "capability_id": capability_id,
            "route_mode": "explicit",
            "resolution_status": "no_capability_candidate",
            "resolved_candidate": None,
            "candidates": candidates,
            "error": _explicit_route_error(capability_id, provider_override=provider_override, model_override=model_override),
        }
    return resolve_capability_route_entry(
        capability_id,
        configured_models,
        route_record=route_record,
        registry=registry,
    )


def _route_from_provider_result(
    provider_result: dict[str, Any] | None,
    *,
    fallback_route: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(provider_result, dict):
        return fallback_route
    fallback_candidate = dict(fallback_route.get("resolved_candidate") or {})
    runtime_route = dict(provider_result.get("route") or {})
    runtime_candidate = dict(runtime_route.get("resolved_candidate") or {})
    provider_id = _clean_route_text(provider_result.get("provider_id"))
    model = _clean_route_text(provider_result.get("model"))
    if not runtime_candidate and (provider_id or model):
        runtime_candidate = {
            "provider_id": provider_id or None,
            "model": model or None,
        }
    for key in ("provider_id", "model", "adapter_id"):
        if not runtime_candidate.get(key) and fallback_candidate.get(key):
            runtime_candidate[key] = fallback_candidate[key]
    if not runtime_candidate:
        return fallback_route
    return {
        "capability_id": _clean_route_text(runtime_route.get("capability_id")) or _clean_route_text(provider_result.get("capability_id")) or fallback_route.get("capability_id"),
        "route_mode": _clean_route_text(runtime_route.get("route_mode")) or _clean_route_text(fallback_route.get("route_mode")) or "explicit",
        "resolution_status": _clean_route_text(runtime_route.get("resolution_status")) or "ok",
        "resolved_candidate": runtime_candidate,
        "error": _clean_route_text(runtime_route.get("error")) or _clean_route_text(fallback_route.get("error")) or None,
    }


def _explicit_route_error(capability_id: str, *, provider_override: str, model_override: str) -> str:
    if provider_override and model_override:
        target = f"{provider_override}/{model_override}"
    else:
        target = provider_override or model_override or "<empty>"
    return f"no_capability_candidate: capability `{capability_id}` explicit route `{target}` has no eligible candidate."


def _clean_route_text(value: Any) -> str:
    return str(value or "").strip()


def _provider_smoke_payload(capability_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    timeout_sec = int(payload.get("timeout_sec") or 180)
    if capability_id == "image.generate":
        actual = {
            "prompt": str(payload.get("prompt") or "AstraBridge provider smoke: a minimal blue square app icon on a white background.").strip(),
            "n": int(payload.get("n") or 1),
            "size": str(payload.get("size") or "1024x1024"),
            "response_format": str(payload.get("response_format") or "url"),
            "quality": str(payload.get("quality") or "auto"),
            "image_format": str(payload.get("image_format") or payload.get("format") or payload.get("output_format") or "png"),
            "operation": str(payload.get("operation") or "generate").strip(),
            "timeout_sec": timeout_sec,
            "purpose": str(payload.get("purpose") or "capability_provider_smoke_image_generate").strip(),
        }
        for key in ("provider_id", "model", "workspace_root", "background", "prompt_category", "moderation"):
            if payload.get(key):
                actual[key] = payload[key]
        sample_keys = ("prompt", "n", "size", "response_format", "quality", "image_format", "operation", "purpose")
        sample = {key: actual[key] for key in sample_keys}
        for key in ("provider_id", "model", "workspace_root", "background", "prompt_category", "moderation"):
            if actual.get(key):
                sample[key] = actual[key]
        return actual, sample
    if capability_id == "vision.analyze":
        custom_image_paths = _clean_string_list(payload.get("image_paths"))
        custom_image_urls = _clean_string_list(payload.get("image_urls"))
        custom_image_inputs = [item for item in list(payload.get("image_inputs") or []) if isinstance(item, dict)]
        if custom_image_paths or custom_image_urls or custom_image_inputs:
            actual = {
                "prompt": str(payload.get("prompt") or "Inspect the attached image and summarize the visible facts.").strip(),
                "image_paths": custom_image_paths,
                "image_urls": custom_image_urls,
                "image_inputs": custom_image_inputs,
                "detail": str(payload.get("detail") or "low").strip(),
                "max_output_tokens": int(payload.get("max_output_tokens") or 256),
                "timeout_sec": timeout_sec,
            }
            for key in ("provider_id", "model", "workspace_root"):
                if payload.get(key):
                    actual[key] = payload[key]
            sample = {
                "prompt": actual["prompt"],
                "image_paths": custom_image_paths,
                "image_urls": custom_image_urls,
                "image_inputs": _sanitize_image_input_samples(custom_image_inputs),
                "detail": actual["detail"],
                "max_output_tokens": actual["max_output_tokens"],
            }
            if actual.get("provider_id"):
                sample["provider_id"] = actual["provider_id"]
            if actual.get("model"):
                sample["model"] = actual["model"]
            return actual, sample
        actual = {
            "prompt": "This is a provider smoke test. Briefly describe the image color.",
            "image_inputs": [{"data_uri": _red_square_png_data_uri(), "mime_type": "image/png"}],
            "detail": "low",
            "max_output_tokens": 48,
            "timeout_sec": timeout_sec,
        }
        for key in ("provider_id", "model", "workspace_root"):
            if payload.get(key):
                actual[key] = payload[key]
        sample = {
            "prompt": actual["prompt"],
            "image_inputs": [{"fixture": "generated_red_square_png", "mime_type": "image/png"}],
            "detail": actual["detail"],
            "max_output_tokens": actual["max_output_tokens"],
        }
        for key in ("provider_id", "model", "workspace_root"):
            if actual.get(key):
                sample[key] = actual[key]
        return actual, sample
    if capability_id == "speech.transcribe":
        custom_audio_inputs = [item for item in list(payload.get("audio_inputs") or []) if isinstance(item, dict)]
        custom_audio_paths = _clean_string_list(payload.get("audio_paths"))
        if custom_audio_inputs or custom_audio_paths:
            actual = {
                "audio_inputs": custom_audio_inputs or [{"path": path} for path in custom_audio_paths],
                "language_hint": str(payload.get("language_hint") or "en").strip(),
                "timeout_sec": timeout_sec,
            }
            for key in ("provider_id", "model", "workspace_root"):
                if payload.get(key):
                    actual[key] = payload[key]
            sample = {
                "audio_inputs": _sanitize_audio_input_samples(actual["audio_inputs"]),
                "language_hint": actual["language_hint"],
            }
            if actual.get("provider_id"):
                sample["provider_id"] = actual["provider_id"]
            if actual.get("model"):
                sample["model"] = actual["model"]
            if actual.get("workspace_root"):
                sample["workspace_root"] = actual["workspace_root"]
            return actual, sample
        actual = {
            "audio_inputs": [{"data_uri": _tone_wav_data_uri(), "mime_type": "audio/wav"}],
            "language_hint": "en",
            "timeout_sec": timeout_sec,
        }
        for key in ("provider_id", "model", "workspace_root"):
            if payload.get(key):
                actual[key] = payload[key]
        sample = {
            "audio_inputs": [{"fixture": "generated_tone_wav", "mime_type": "audio/wav", "duration_sec": 0.8}],
            "language_hint": actual["language_hint"],
        }
        for key in ("provider_id", "model", "workspace_root"):
            if actual.get(key):
                sample[key] = actual[key]
        return actual, sample
    if capability_id == "speech.synthesize":
        actual = {
            "text": "AstraBridge provider smoke test.",
            "voice": str(payload.get("voice") or "Cherry"),
            "audio_format": "wav",
            "timeout_sec": int(payload.get("timeout_sec") or 240),
        }
        for key in ("provider_id", "model", "workspace_root", "language_type", "instructions"):
            if payload.get(key):
                actual[key] = payload[key]
        sample = {key: actual[key] for key in ("text", "voice", "audio_format")}
        for key in ("provider_id", "model", "workspace_root", "language_type", "instructions"):
            if actual.get(key):
                sample[key] = actual[key]
        return actual, sample
    raise ValueError(f"Unsupported provider smoke capability: {capability_id}")


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _sanitize_image_input_samples(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in items:
        sample = {key: item.get(key) for key in ("path", "url", "mime_type") if item.get(key)}
        if item.get("data_uri") or item.get("data"):
            sample["fixture"] = "inline_image_data"
            if item.get("mime_type"):
                sample["mime_type"] = item.get("mime_type")
        if sample:
            sanitized.append(sample)
    return sanitized


def _sanitize_audio_input_samples(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in items:
        sample = {key: item.get(key) for key in ("path", "mime_type", "duration_sec") if item.get(key)}
        if item.get("data_uri") or item.get("data"):
            sample["fixture"] = "inline_audio_data"
            if item.get("mime_type"):
                sample["mime_type"] = item.get("mime_type")
        if sample:
            sanitized.append(sample)
    return sanitized


def _provider_status_notes(capability_id: str, result: dict[str, Any]) -> tuple[str, list[str]]:
    notes = ["Provider smoke invoked the configured capability route and returned a normalized response."]
    if capability_id in {"vision.analyze", "speech.transcribe"} and not str(result.get("text") or "").strip():
        notes.append("Provider returned no visible text for the fixture; transport passed but semantic output is empty.")
        return "warn", notes
    if capability_id == "speech.synthesize" and not result.get("audio_bytes_base64") and not result.get("artifact_refs"):
        notes.append("Provider returned no audio artifact for the fixture.")
        return "warn", notes
    if capability_id == "image.generate" and not _has_persisted_image_artifact(result.get("artifact_refs") or []):
        notes.append("Provider returned no persisted local image artifact for the fixture.")
        return "fail", notes
    return "pass", notes


def _has_persisted_image_artifact(refs: Any) -> bool:
    if not isinstance(refs, list):
        return False
    for item in refs:
        if not isinstance(item, dict):
            continue
        path = str(item.get("local_path") or item.get("path") or "").strip()
        if path:
            return True
    return False


def _sanitize_provider_result(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    allowed_keys = [
        "schema_version",
        "capability_id",
        "provider_id",
        "model",
        "operation",
        "finish_reason",
        "usage",
        "language",
        "mime_type",
        "duration_sec",
        "audio_format",
        "stream_event_count",
        "audio_input_count",
        "audio_only_content",
        "image_input_count",
        "requested_n",
        "actual_n",
        "count_mismatch",
        "normalization_notes",
    ]
    sanitized = {key: result.get(key) for key in allowed_keys if key in result}
    sanitized["usage_signal"] = normalize_usage_signal(
        source="capability_provider_result",
        provider_id=result.get("provider_id"),
        model=result.get("model"),
        usage=result.get("usage"),
        reason=None if isinstance(result.get("usage"), dict) else "provider_result_usage_not_reported",
        request_kind=result.get("capability_id"),
    )
    text = str(result.get("text") or "").strip()
    if text:
        sanitized["text_preview"] = text[:240]
        sanitized["text_length"] = len(text)
    revised_prompt = str(result.get("revised_prompt") or "").strip()
    if revised_prompt:
        sanitized["revised_prompt_preview"] = revised_prompt[:240]
    refs = _sanitize_artifact_refs(result.get("artifact_refs") or [])
    sanitized["artifact_count"] = len(refs)
    sanitized["artifact_refs"] = refs[:8]
    if isinstance(result.get("route"), dict):
        route = dict(result.get("route") or {})
        candidate = dict(route.get("resolved_candidate") or {})
        sanitized["route"] = {
            "capability_id": route.get("capability_id"),
            "route_mode": route.get("route_mode"),
            "resolved_candidate": {
                "provider_id": candidate.get("provider_id"),
                "model": candidate.get("model"),
                "adapter_id": candidate.get("adapter_id"),
            } if candidate else None,
        }
    return sanitized


def _sanitize_artifact_refs(refs: Any) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    if not isinstance(refs, list):
        return sanitized
    allowed = {
        "artifact_type",
        "path",
        "relative_path",
        "local_path",
        "mime_type",
        "asset_id",
        "result_index",
        "actual_width",
        "actual_height",
        "actual_format",
        "exists",
        "has_alpha",
        "transparency_status",
    }
    for item in refs:
        if not isinstance(item, dict):
            continue
        sanitized.append({key: value for key, value in item.items() if key in allowed})
    return sanitized


def _evidence_refs_from_artifacts(artifact_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in artifact_refs:
        artifact_type = str(item.get("artifact_type") or "").strip()
        path = str(item.get("path") or item.get("local_path") or "").strip()
        if artifact_type in {"summary", "transcript", "text", "audio"} and path:
            evidence.append({"kind": f"capability_{artifact_type}", "path": path})
    return evidence


def _safe_error_message(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(api[_-]?key|authorization|token)(['\":= ]+)([A-Za-z0-9._~+/=-]{8,})", r"\1\2[redacted]", text)
    return text[:1200]


def _looks_like_local_provider_blocker(error: str) -> bool:
    lowered = error.lower()
    return "requires an api_key" in lowered or "requires an api key" in lowered or "no_capability_candidate" in lowered


def _red_square_png_data_uri() -> str:
    width = 64
    height = 64
    raw = b"".join(b"\x00" + (b"\xf0\x3a\x2f" * width) for _ in range(height))
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(raw))
    png += _png_chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _tone_wav_data_uri() -> str:
    sample_rate = 16_000
    duration_sec = 0.8
    frame_count = int(sample_rate * duration_sec)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            amplitude = int(0.2 * 32767 * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames.extend(struct.pack("<h", amplitude))
        wav_file.writeframes(bytes(frames))
    return "data:audio/wav;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
