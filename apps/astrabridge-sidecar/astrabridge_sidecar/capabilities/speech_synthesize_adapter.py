from __future__ import annotations

import base64
import io
import json
import os
import wave
from pathlib import Path
from typing import Any, Callable, Iterable

import requests

from ..common import new_id, now_iso, path_for_host, write_json


SPEECH_SYNTHESIZE_CAPABILITY_RESULT_SCHEMA = "astrabridge-speech-synthesize-capability-result-v1"


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
    return f"audio/{normalized}" if normalized else "application/octet-stream"


def _safe_json_loads(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class QwenSpeechSynthesizeAdapter:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        post_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._base_url = _clean_text(base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        self._api_key = _clean_text(api_key)
        self._post = post_fn or requests.post

    def synthesize(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = _clean_text(payload.get("api_key")) or self._api_key or _clean_text(os.environ.get("DASHSCOPE_API_KEY"))
        if not api_key:
            raise ValueError("Qwen Omni TTS requires an api_key or DASHSCOPE_API_KEY.")
        request_body = self.build_request(payload)
        response = self._post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json=request_body,
            timeout=int(payload.get("timeout_sec") or 240),
            stream=True,
        )
        response.raise_for_status()
        sse_lines = self._read_sse_lines(response)
        result = self.normalize_result(payload, request_body, sse_lines)
        persisted = self.persist_artifacts(payload, request_body, sse_lines, result)
        if persisted:
            result.update(persisted)
        return result

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = _clean_text(payload.get("text"))
        if not text:
            raise ValueError("speech.synthesize requires non-empty text.")
        messages: list[dict[str, Any]] = []
        instructions = _clean_text(payload.get("instructions"))
        if instructions:
            messages.append({"role": "system", "content": instructions})
        messages.append({"role": "user", "content": text})
        audio_format = _clean_text(payload.get("audio_format") or "wav").lower() or "wav"
        request_body: dict[str, Any] = {
            "model": _clean_text(payload.get("model") or "qwen3.5-omni-plus"),
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "modalities": ["text", "audio"],
            "audio": {
                "voice": _clean_text(payload.get("voice") or "Tina"),
                "format": audio_format,
            },
        }
        return request_body

    def normalize_result(
        self,
        payload: dict[str, Any],
        request_body: dict[str, Any],
        sse_lines: list[str],
    ) -> dict[str, Any]:
        text_parts: list[str] = []
        audio_chunks: list[bytes] = []
        usage: dict[str, Any] = {}
        finish_reason = ""
        response_id = ""
        model = _clean_text(request_body.get("model"))
        for line in sse_lines:
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if not body or body == "[DONE]":
                continue
            event = _safe_json_loads(body)
            if not event:
                continue
            response_id = response_id or _clean_text(event.get("id"))
            model = _clean_text(event.get("model") or model)
            if isinstance(event.get("usage"), dict):
                usage = dict(event.get("usage") or {})
            choices = event.get("choices") or []
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                finish_reason = _clean_text(choice.get("finish_reason") or finish_reason)
                delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                content = delta.get("content")
                if isinstance(content, str) and content:
                    text_parts.append(content)
                audio = delta.get("audio") if isinstance(delta.get("audio"), dict) else {}
                audio_data = _clean_text(audio.get("data"))
                if audio_data:
                    audio_chunks.append(base64.b64decode(audio_data))
        audio_bytes = b"".join(audio_chunks)
        audio_format = _clean_text((request_body.get("audio") or {}).get("format") or payload.get("audio_format") or "wav").lower()
        mime_type = _default_audio_mime_type(audio_format)
        duration_sec = self._duration_from_audio_bytes(audio_bytes, audio_format)
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
            "audio_format": audio_format,
            "audio_bytes_base64": base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else "",
            "stream_event_count": len(sse_lines),
            "normalization_notes": [
                "Qwen Omni TTS request uses streaming chat completions with text and audio modalities.",
                "Audio bytes are assembled from SSE delta.audio.data chunks.",
            ],
        }

    def persist_artifacts(
        self,
        payload: dict[str, Any],
        request_body: dict[str, Any],
        sse_lines: list[str],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        workspace_root = payload.get("workspace_root")
        if not workspace_root:
            return {}
        root = path_for_host(workspace_root).resolve() / ".astrabridge" / "capabilities" / "speech_synthesize"
        run_id = new_id("qwen-tts")
        run_dir = root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        request_path = run_dir / "request.json"
        sse_path = run_dir / "response.sse.txt"
        transcript_path = run_dir / "transcript.txt"
        audio_extension = _clean_text(result.get("audio_format") or "wav").lower() or "wav"
        audio_path = run_dir / f"output.{audio_extension}"
        summary_path = run_dir / "summary.json"
        audio_bytes = base64.b64decode(str(result.get("audio_bytes_base64") or ""))
        write_json(
            request_path,
            {
                "saved_at": now_iso(),
                "method": "POST",
                "url": f"{self._base_url}/chat/completions",
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
