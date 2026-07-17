from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Callable

import requests

from ..common import new_id, now_iso, path_for_host, write_json
from ..multimodal_result_envelope import enrich_capability_result


SPEECH_TRANSCRIBE_CAPABILITY_RESULT_SCHEMA = "astrabridge-speech-transcribe-capability-result-v1"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _ensure_data_uri(value: str, mime_type: str) -> str:
    text = _clean_text(value)
    if text.startswith("data:"):
        return text
    return f"data:{mime_type};base64,{text}"


def _mime_type_for_path(path: Path, explicit_mime_type: str) -> str:
    if explicit_mime_type:
        return explicit_mime_type
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def _normalize_transcript_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            for key in ("text", "content"):
                text = _clean_text(item.get(key))
                if text:
                    parts.append(text)
                    break
        return "\n".join(parts).strip()
    return ""


class QwenSpeechTranscribeAdapter:
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

    def transcribe(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = _clean_text(payload.get("api_key")) or self._api_key or _clean_text(os.environ.get("DASHSCOPE_API_KEY"))
        if not api_key:
            raise ValueError("Qwen ASR requires an api_key or DASHSCOPE_API_KEY.")
        request_body = self.build_request(payload)
        response = self._post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=int(payload.get("timeout_sec") or 180),
        )
        response.raise_for_status()
        response_body = response.json()
        result = self.normalize_result(payload, request_body, response_body)
        persisted = self.persist_artifacts(payload, request_body, response_body, result)
        if persisted:
            result.update(persisted)
        return enrich_capability_result("speech.transcribe", result, workspace_root=payload.get("workspace_root"))

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        audio_parts = self._normalize_audio_parts(payload.get("audio_inputs") or [])
        if not audio_parts:
            raise ValueError("speech.transcribe requires at least one audio input.")
        content = [{"type": "input_audio", "input_audio": {"data": item["data"]}} for item in audio_parts]
        request_body: dict[str, Any] = {
            "model": _clean_text(payload.get("model") or "qwen3-asr-flash"),
            "messages": [{"role": "user", "content": content}],
            "asr_options": {
                "language": _clean_text(payload.get("language_hint")),
                "enable_itn": bool(payload.get("enable_itn", False)),
            },
        }
        if not request_body["asr_options"]["language"]:
            request_body["asr_options"].pop("language", None)
        return request_body

    def normalize_result(
        self,
        payload: dict[str, Any],
        request_body: dict[str, Any],
        response_body: dict[str, Any],
    ) -> dict[str, Any]:
        choices = response_body.get("choices") or []
        first_choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = first_choice.get("message") if isinstance(first_choice.get("message"), dict) else {}
        annotations = [dict(item) for item in (message.get("annotations") or []) if isinstance(item, dict)]
        language = ""
        for item in annotations:
            if _clean_text(item.get("language")):
                language = _clean_text(item.get("language"))
                break
        transcript = _normalize_transcript_text(message.get("content"))
        ignored_prompt = _clean_text(payload.get("prompt"))
        return {
            "schema_version": SPEECH_TRANSCRIBE_CAPABILITY_RESULT_SCHEMA,
            "capability_id": "speech.transcribe",
            "provider_id": "qwen",
            "model": _clean_text(response_body.get("model") or request_body.get("model")),
            "text": transcript,
            "language": language or _clean_text(payload.get("language_hint")),
            "segments": [],
            "annotations": annotations,
            "usage": dict(response_body.get("usage") or {}),
            "finish_reason": _clean_text(first_choice.get("finish_reason")),
            "audio_input_count": len((request_body.get("messages") or [{}])[0].get("content") or []),
            "audio_only_content": True,
            "prompt_ignored": bool(ignored_prompt),
            "normalization_notes": [
                "Qwen ASR request content contains audio parts only.",
                "Any caller prompt is intentionally not forwarded as a text content part.",
            ],
        }

    def persist_artifacts(
        self,
        payload: dict[str, Any],
        request_body: dict[str, Any],
        response_body: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        workspace_root = payload.get("workspace_root")
        if not workspace_root:
            return {}
        root = path_for_host(workspace_root).resolve() / ".astrabridge" / "capabilities" / "speech_transcribe"
        run_id = new_id("qwen-asr")
        run_dir = root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        request_path = run_dir / "request.json"
        response_path = run_dir / "response.json"
        transcript_path = run_dir / "transcript.txt"
        summary_path = run_dir / "summary.json"
        write_json(
            request_path,
            {
                "saved_at": now_iso(),
                "method": "POST",
                "url": f"{self._base_url}/chat/completions",
                "json": request_body,
            },
        )
        write_json(
            response_path,
            {
                "saved_at": now_iso(),
                "body": response_body,
            },
        )
        transcript_path.write_text(str(result.get("text") or ""), encoding="utf-8")
        write_json(
            summary_path,
            {
                "saved_at": now_iso(),
                "capability_id": "speech.transcribe",
                "provider_id": "qwen",
                "model": result.get("model"),
                "language": result.get("language"),
                "audio_input_count": result.get("audio_input_count"),
                "prompt_ignored": result.get("prompt_ignored"),
                "request_path": str(request_path),
                "response_path": str(response_path),
                "transcript_path": str(transcript_path),
            },
        )
        return {
            "artifact_refs": [
                {"artifact_type": "request", "path": str(request_path)},
                {"artifact_type": "response", "path": str(response_path)},
                {"artifact_type": "transcript", "path": str(transcript_path)},
                {"artifact_type": "summary", "path": str(summary_path)},
            ],
            "artifact_dir": str(run_dir),
        }

    def _normalize_audio_parts(self, audio_inputs: Any) -> list[dict[str, str]]:
        items = audio_inputs if isinstance(audio_inputs, list) else [audio_inputs]
        normalized: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            mime_type = _clean_text(item.get("mime_type")) or "audio/wav"
            data_uri = _clean_text(item.get("data_uri"))
            if data_uri:
                normalized.append({"data": _ensure_data_uri(data_uri, mime_type), "mime_type": mime_type})
                continue
            data = _clean_text(item.get("data"))
            if data:
                normalized.append({"data": _ensure_data_uri(data, mime_type), "mime_type": mime_type})
                continue
            path_value = _clean_text(item.get("path"))
            if not path_value:
                continue
            path = path_for_host(path_value)
            file_mime = _mime_type_for_path(path, mime_type)
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            normalized.append({"data": f"data:{file_mime};base64,{encoded}", "mime_type": file_mime})
        return normalized
