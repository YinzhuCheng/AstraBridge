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
    route = resolve_capability_route_entry(
        capability_id,
        configured_models,
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
            status, provider_notes = _provider_status_notes(capability_id, provider_result)
            artifact_refs = _sanitize_artifact_refs(provider_result.get("artifact_refs") or [])
            evidence_refs = _evidence_refs_from_artifacts(artifact_refs)
        except Exception as exc:  # noqa: BLE001 - smoke should preserve failure as data for the UI.
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            provider_error = _safe_error_message(exc)
            provider_invoked = not _looks_like_local_provider_blocker(provider_error)
            status = "fail"
            provider_notes = ["Provider smoke was requested and failed; inspect the sanitized error before retrying."]
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
        "created_at": now_iso(),
    }


def _provider_smoke_payload(capability_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    timeout_sec = int(payload.get("timeout_sec") or 180)
    if capability_id == "image.generate":
        actual = {
            "prompt": "AstraBridge provider smoke: a minimal blue square app icon on a white background.",
            "n": 1,
            "size": str(payload.get("size") or "1024x1024"),
            "response_format": "url",
            "timeout_sec": timeout_sec,
            "purpose": "capability_provider_smoke_image_generate",
        }
        return actual, {key: actual[key] for key in ("prompt", "n", "size", "response_format", "purpose")}
    if capability_id == "vision.analyze":
        actual = {
            "prompt": "This is a provider smoke test. Briefly describe the image color.",
            "image_inputs": [{"data_uri": _red_square_png_data_uri(), "mime_type": "image/png"}],
            "detail": "low",
            "max_output_tokens": 48,
            "timeout_sec": timeout_sec,
        }
        sample = {
            "prompt": actual["prompt"],
            "image_inputs": [{"fixture": "generated_red_square_png", "mime_type": "image/png"}],
            "detail": actual["detail"],
            "max_output_tokens": actual["max_output_tokens"],
        }
        return actual, sample
    if capability_id == "speech.transcribe":
        actual = {
            "audio_inputs": [{"data_uri": _tone_wav_data_uri(), "mime_type": "audio/wav"}],
            "language_hint": "en",
            "timeout_sec": timeout_sec,
        }
        sample = {
            "audio_inputs": [{"fixture": "generated_tone_wav", "mime_type": "audio/wav", "duration_sec": 0.8}],
            "language_hint": actual["language_hint"],
        }
        return actual, sample
    if capability_id == "speech.synthesize":
        actual = {
            "text": "AstraBridge provider smoke test.",
            "voice": str(payload.get("voice") or "Tina"),
            "audio_format": "wav",
            "timeout_sec": int(payload.get("timeout_sec") or 240),
        }
        return actual, {key: actual[key] for key in ("text", "voice", "audio_format")}
    raise ValueError(f"Unsupported provider smoke capability: {capability_id}")


def _provider_status_notes(capability_id: str, result: dict[str, Any]) -> tuple[str, list[str]]:
    notes = ["Provider smoke invoked the configured capability route and returned a normalized response."]
    if capability_id in {"vision.analyze", "speech.transcribe"} and not str(result.get("text") or "").strip():
        notes.append("Provider returned no visible text for the fixture; transport passed but semantic output is empty.")
        return "warn", notes
    if capability_id == "speech.synthesize" and not result.get("audio_bytes_base64") and not result.get("artifact_refs"):
        notes.append("Provider returned no audio artifact for the fixture.")
        return "warn", notes
    if capability_id == "image.generate" and not result.get("artifact_refs"):
        notes.append("Provider returned no image artifact reference for the fixture.")
        return "warn", notes
    return "pass", notes


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
