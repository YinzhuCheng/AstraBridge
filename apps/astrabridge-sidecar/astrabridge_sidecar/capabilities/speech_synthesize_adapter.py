from __future__ import annotations

import base64
import io
import json
import os
import wave
from pathlib import Path
from typing import Any, Callable

import requests

from ..common import new_id, now_iso, path_for_host, write_json


SPEECH_SYNTHESIZE_CAPABILITY_RESULT_SCHEMA = "astrabridge-speech-synthesize-capability-result-v1"

QWEN_TTS_MODELS = ("qwen3-tts-flash", "qwen3-tts-instruct-flash")
COSYVOICE_TTS_MODELS = (
    "cosyvoice-v2",
    "cosyvoice-v3-flash",
    "cosyvoice-v3-plus",
    "cosyvoice-v3.5-flash",
    "cosyvoice-v3.5-plus",
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _default_audio_mime_type(audio_format: str) -> str:
    normalized = _clean_text(audio_format).lower()
    if normalized == "wav":
        return "audio/wav"
    if normalized == "mp3":
        return "audio/mpeg"
    if normalized == "pcm":
        return "audio/L16"
    if normalized == "opus":
        return "audio/opus"
    return f"audio/{normalized}" if normalized else "application/octet-stream"


def _normalize_dashscope_tts_base_url(base_url: str | None) -> str:
    normalized = _clean_text(base_url or "https://dashscope.aliyuncs.com/api/v1").rstrip("/")
    legacy_suffix = "/compatible-mode/v1"
    if normalized.endswith(legacy_suffix):
        normalized = normalized[: -len(legacy_suffix)] + "/api/v1"
    elif not normalized.endswith("/api/v1"):
        normalized = normalized + "/api/v1"
    return normalized or "https://dashscope.aliyuncs.com/api/v1"


def _safe_json_loads(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clean_string_list(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


class AlibabaSpeechSynthesizeAdapter:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        post_fn: Callable[..., Any] | None = None,
        get_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._base_url = _normalize_dashscope_tts_base_url(base_url)
        self._api_key = _clean_text(api_key)
        self._post = post_fn or requests.post
        self._get = get_fn or requests.get

    def synthesize(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = _clean_text(payload.get("api_key")) or self._api_key or _clean_text(os.environ.get("DASHSCOPE_API_KEY"))
        if not api_key:
            raise ValueError("Alibaba TTS requires an api_key or DASHSCOPE_API_KEY.")
        request_body, profile = self.build_request(payload)
        response = self._post(
            f"{self._base_url}{profile['endpoint_path']}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "X-DashScope-SSE": "enable",
            },
            json=request_body,
            timeout=int(payload.get("timeout_sec") or 240),
            stream=True,
        )
        response.raise_for_status()
        sse_lines = self._read_sse_lines(response)
        result = self.normalize_result(payload, request_body, sse_lines, profile=profile)
        persisted = self.persist_artifacts(payload, request_body, sse_lines, result, profile=profile)
        if persisted:
            result.update(persisted)
        return result

    def build_request(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        text = _clean_text(payload.get("text"))
        if not text:
            raise ValueError("speech.synthesize requires non-empty text.")
        instructions = _clean_text(payload.get("instructions"))
        requested_model = _clean_text(payload.get("model"))
        profile = self._profile_for_model(requested_model, instructions=instructions)
        audio_format = _clean_text(payload.get("audio_format") or profile["default_audio_format"]).lower() or profile["default_audio_format"]
        voice = _clean_text(payload.get("voice") or profile.get("default_voice"))
        if profile["voice_required"] and not voice:
            raise ValueError(f"speech.synthesize model `{profile['model']}` requires an explicit voice.")
        request_body = profile["build_request"](
            text=text,
            instructions=instructions,
            voice=voice,
            audio_format=audio_format,
            payload=payload,
        )
        return request_body, profile

    def normalize_result(
        self,
        payload: dict[str, Any],
        request_body: dict[str, Any],
        sse_lines: list[str],
        *,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        text_parts: list[str] = []
        output_audio_bytes = b""
        delta_audio_chunks: list[bytes] = []
        usage: dict[str, Any] = {}
        finish_reason = ""
        response_id = ""
        audio_url = ""
        model = _clean_text(request_body.get("model") or profile["model"])
        event_types: list[str] = []
        output_audio_encoding = ""
        for line in sse_lines:
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if not body or body == "[DONE]":
                continue
            event = _safe_json_loads(body)
            if not event:
                continue
            response_id = response_id or _clean_text(event.get("request_id") or event.get("id"))
            model = _clean_text(event.get("model") or model)
            event_type = _clean_text(event.get("type"))
            if event_type:
                event_types.append(event_type)
            if isinstance(event.get("usage"), dict):
                usage = dict(event.get("usage") or {})
            finish_reason = _clean_text(event.get("finish_reason") or finish_reason)
            output = event.get("output") if isinstance(event.get("output"), dict) else {}
            finish_reason = _clean_text(output.get("finish_reason") or finish_reason)
            for key in ("text", "transcript", "original_text"):
                value = output.get(key)
                if isinstance(value, str) and _clean_text(value):
                    text_parts.append(str(value))
            audio = output.get("audio") if isinstance(output.get("audio"), dict) else {}
            audio_data = _clean_text(audio.get("data"))
            if audio_data:
                output_audio_bytes = base64.b64decode(audio_data)
            output_audio_encoding = _clean_text(audio.get("format") or audio.get("encoding") or output_audio_encoding)
            audio_url = audio_url or _clean_text(audio.get("url"))
            choices = event.get("choices") or []
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                finish_reason = _clean_text(choice.get("finish_reason") or finish_reason)
                delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    text_parts.append(content)
                delta_audio = delta.get("audio") if isinstance(delta.get("audio"), dict) else {}
                delta_audio_data = _clean_text(delta_audio.get("data"))
                if delta_audio_data:
                    delta_audio_chunks.append(base64.b64decode(delta_audio_data))
                output_audio_encoding = _clean_text(delta_audio.get("format") or delta_audio.get("encoding") or output_audio_encoding)
                audio_url = audio_url or _clean_text(delta_audio.get("url"))
        audio_bytes = output_audio_bytes or b"".join(delta_audio_chunks)
        requested_audio_format = profile["extract_requested_audio_format"](request_body, payload)
        mime_type = _default_audio_mime_type(requested_audio_format)
        duration_sec = self._duration_from_audio_bytes(audio_bytes, requested_audio_format)
        text_value = "".join(text_parts).strip()
        return {
            "schema_version": SPEECH_SYNTHESIZE_CAPABILITY_RESULT_SCHEMA,
            "capability_id": "speech.synthesize",
            "provider_id": "qwen",
            "model": model,
            "text": text_value,
            "mime_type": mime_type,
            "duration_sec": duration_sec,
            "usage": usage,
            "finish_reason": finish_reason,
            "response_id": response_id,
            "audio_format": requested_audio_format,
            "audio_url": audio_url,
            "audio_bytes_base64": base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else "",
            "stream_event_count": len(sse_lines),
            "stream_event_types": event_types,
            "tts_family": profile["family_id"],
            "tts_protocol_profile": profile["protocol_profile"],
            "stream_audio_encoding": output_audio_encoding or None,
            "normalization_notes": list(profile["normalization_notes"]),
        }

    def persist_artifacts(
        self,
        payload: dict[str, Any],
        request_body: dict[str, Any],
        sse_lines: list[str],
        result: dict[str, Any],
        *,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        workspace_root = payload.get("workspace_root")
        if not workspace_root:
            return {}
        root = path_for_host(workspace_root).resolve() / ".astrabridge" / "capabilities" / "speech_synthesize"
        run_id = new_id(profile["artifact_prefix"])
        run_dir = root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        request_path = run_dir / "request.json"
        sse_path = run_dir / "response.sse.txt"
        transcript_path = run_dir / "transcript.txt"
        audio_extension = _clean_text(result.get("audio_format") or profile["default_audio_format"]).lower() or profile["default_audio_format"]
        audio_path = run_dir / f"output.{audio_extension}"
        summary_path = run_dir / "summary.json"
        audio_bytes = base64.b64decode(str(result.get("audio_bytes_base64") or ""))
        audio_url = _clean_text(result.get("audio_url"))
        if self._should_download_final_audio(result, profile=profile):
            audio_bytes = self._download_audio_bytes(audio_url, timeout=int(payload.get("timeout_sec") or 240))
        elif not audio_bytes and audio_url:
            audio_bytes = self._download_audio_bytes(audio_url, timeout=int(payload.get("timeout_sec") or 240))
        write_json(
            request_path,
            {
                "saved_at": now_iso(),
                "method": "POST",
                "url": f"{self._base_url}{profile['endpoint_path']}",
                "json": request_body,
            },
        )
        sse_path.write_text("\n".join(sse_lines) + ("\n" if sse_lines else ""), encoding="utf-8")
        transcript_path.write_text(str(result.get("text") or ""), encoding="utf-8")
        audio_path.write_bytes(audio_bytes)
        write_json(
            summary_path,
            {
                "saved_at": now_iso(),
                "capability_id": "speech.synthesize",
                "provider_id": "qwen",
                "model": result.get("model"),
                "mime_type": result.get("mime_type"),
                "duration_sec": result.get("duration_sec"),
                "stream_event_count": result.get("stream_event_count"),
                "stream_event_types": list(result.get("stream_event_types") or []),
                "tts_family": result.get("tts_family"),
                "tts_protocol_profile": result.get("tts_protocol_profile"),
                "request_path": str(request_path),
                "sse_path": str(sse_path),
                "transcript_path": str(transcript_path),
                "audio_path": str(audio_path),
            },
        )
        return {
            "artifact_refs": [
                {"artifact_type": "request", "path": str(request_path)},
                {"artifact_type": "sse", "path": str(sse_path)},
                {"artifact_type": "transcript", "path": str(transcript_path)},
                {"artifact_type": "audio", "path": str(audio_path), "mime_type": result.get("mime_type")},
                {"artifact_type": "summary", "path": str(summary_path)},
            ],
            "artifact_dir": str(run_dir),
        }

    def _should_download_final_audio(self, result: dict[str, Any], *, profile: dict[str, Any]) -> bool:
        audio_url = _clean_text(result.get("audio_url"))
        if not audio_url:
            return False
        requested_audio_format = _clean_text(result.get("audio_format")).lower()
        if requested_audio_format == "pcm":
            return False
        stream_audio_encoding = _clean_text(result.get("stream_audio_encoding")).lower()
        if profile["family_id"] == "cosyvoice" and not _clean_text(result.get("audio_bytes_base64")) == "":
            return True
        return bool(stream_audio_encoding == "pcm" and _clean_text(result.get("audio_bytes_base64")))

    def _download_audio_bytes(self, audio_url: str, *, timeout: int) -> bytes:
        response = self._get(audio_url, timeout=timeout)
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        content = getattr(response, "content", b"")
        if isinstance(content, bytes):
            return content
        return bytes(content or b"")

    def _read_sse_lines(self, response: Any) -> list[str]:
        lines: list[str] = []
        for raw_line in response.iter_lines():
            if raw_line is None:
                continue
            if isinstance(raw_line, bytes):
                text = raw_line.decode("utf-8", errors="replace")
            else:
                text = str(raw_line)
            text = text.rstrip("\r")
            if text:
                lines.append(text)
        return lines

    def _duration_from_audio_bytes(self, audio_bytes: bytes, audio_format: str) -> float | None:
        if not audio_bytes or _clean_text(audio_format).lower() != "wav":
            return None
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
                if frame_rate <= 0:
                    return None
                return round(frame_count / frame_rate, 6)
        except wave.Error:
            return None

    def _profile_for_model(self, model: str, *, instructions: str) -> dict[str, Any]:
        normalized_model = _clean_text(model)
        if normalized_model in COSYVOICE_TTS_MODELS:
            return self._cosyvoice_profile(normalized_model)
        resolved_model = normalized_model or ("qwen3-tts-instruct-flash" if instructions else "qwen3-tts-flash")
        return self._qwen_profile(resolved_model)

    def _qwen_profile(self, model: str) -> dict[str, Any]:
        def build_request(*, text: str, instructions: str, voice: str, audio_format: str, payload: dict[str, Any]) -> dict[str, Any]:
            input_payload: dict[str, Any] = {
                "text": text,
                "voice": voice,
                "format": audio_format,
            }
            language_hint = _clean_text(payload.get("language_type") or payload.get("language_hint"))
            if language_hint:
                input_payload["language_type"] = language_hint
            if instructions:
                input_payload["instructions"] = instructions
            return {
                "model": model,
                "input": input_payload,
                "stream": True,
            }

        return {
            "family_id": "qwen_tts",
            "protocol_profile": "dashscope_multimodal_generation_sse",
            "model": model,
            "endpoint_path": "/services/aigc/multimodal-generation/generation",
            "default_audio_format": "wav",
            "default_voice": "Tina",
            "voice_required": False,
            "artifact_prefix": "qwen-tts",
            "build_request": build_request,
            "extract_requested_audio_format": lambda request_body, payload: _clean_text(
                ((request_body.get("input") or {}).get("format")) or payload.get("audio_format") or "wav"
            ).lower()
            or "wav",
            "normalization_notes": (
                "Qwen TTS uses the DashScope multimodal-generation SSE endpoint.",
                "Streaming events may contain output text, transcript text, audio snapshots, or audio delta chunks.",
                "When stream chunks do not match the requested container format, the final audio URL is preferred for artifact persistence.",
            ),
        }

    def _cosyvoice_profile(self, model: str) -> dict[str, Any]:
        def build_request(*, text: str, instructions: str, voice: str, audio_format: str, payload: dict[str, Any]) -> dict[str, Any]:
            input_payload: dict[str, Any] = {
                "text": text,
                "voice": voice,
                "format": audio_format,
            }
            sample_rate = payload.get("sample_rate")
            if sample_rate not in (None, ""):
                input_payload["sample_rate"] = int(sample_rate)
            for source_key, target_key in (
                ("volume", "volume"),
                ("rate", "rate"),
                ("pitch", "pitch"),
                ("bit_rate", "bit_rate"),
                ("seed", "seed"),
            ):
                value = payload.get(source_key)
                if value not in (None, ""):
                    input_payload[target_key] = value
            for source_key, target_key in (
                ("enable_ssml", "enable_ssml"),
                ("word_timestamp_enabled", "word_timestamp_enabled"),
            ):
                value = payload.get(source_key)
                if value is not None:
                    input_payload[target_key] = bool(value)
            language_hints = _clean_string_list(payload.get("language_hints") or payload.get("language_hint"))
            if language_hints:
                input_payload["language_hints"] = language_hints
            if instructions:
                input_payload["instruction"] = instructions
            return {
                "model": model,
                "input": input_payload,
                "parameters": {"streaming": True},
            }

        return {
            "family_id": "cosyvoice",
            "protocol_profile": "dashscope_speech_synthesizer_sse",
            "model": model,
            "endpoint_path": "/services/audio/tts/SpeechSynthesizer",
            "default_audio_format": "mp3",
            "default_voice": "",
            "voice_required": True,
            "artifact_prefix": "cosyvoice-tts",
            "build_request": build_request,
            "extract_requested_audio_format": lambda request_body, payload: _clean_text(
                ((request_body.get("input") or {}).get("format")) or payload.get("audio_format") or "mp3"
            ).lower()
            or "mp3",
            "normalization_notes": (
                "CosyVoice HTTP TTS uses the DashScope SpeechSynthesizer SSE endpoint.",
                "CosyVoice streams sentence-level events and may provide stream chunks before the final downloadable audio asset.",
                "The adapter prefers the final audio URL for non-PCM artifact persistence when stream chunks are container-agnostic.",
            ),
        }


QwenSpeechSynthesizeAdapter = AlibabaSpeechSynthesizeAdapter
