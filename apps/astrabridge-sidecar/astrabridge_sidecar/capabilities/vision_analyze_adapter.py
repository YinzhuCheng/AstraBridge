from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, Callable

import requests

from ..common import new_id, now_iso, path_for_host, write_json


VISION_ANALYZE_CAPABILITY_RESULT_SCHEMA = "astrabridge-vision-analyze-capability-result-v1"


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _ensure_data_uri(value: str, mime_type: str) -> str:
    text = _clean_text(value)
    if text.startswith("data:image/"):
        return text
    return f"data:{mime_type};base64,{text}"


def _mime_type_for_path(path: Path, explicit_mime_type: str) -> str:
    if explicit_mime_type:
        return explicit_mime_type
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "image/png"


def _normalize_visible_text(content: Any) -> str:
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


class ChatVisionAnalyzeAdapter:
    def __init__(
        self,
        *,
        provider_id: str,
        base_url: str,
        default_model: str,
        api_key: str | None = None,
        env_key: str | None = None,
        env_key_aliases: tuple[str, ...] = (),
        post_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._base_url = _clean_text(base_url).rstrip("/")
        self._default_model = default_model
        self._api_key = _clean_text(api_key)
        self._env_key = env_key or ""
        self._env_keys = tuple(key for key in (self._env_key, *env_key_aliases) if key)
        self._post = post_fn or requests.post

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = _clean_text(payload.get("api_key")) or self._api_key
        if not api_key:
            for env_key in self._env_keys:
                api_key = _clean_text(os.environ.get(env_key))
                if api_key:
                    break
        if not api_key:
            env_hint = " or ".join(self._env_keys) if self._env_keys else "a configured environment variable"
            raise ValueError(f"{self._provider_id} vision adapter requires an api_key or {env_hint}.")
        request_body = self.build_request(payload)
        response = self._post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=int(payload.get("timeout_sec") or 120),
        )
        response.raise_for_status()
        response_body = response.json()
        result = self.normalize_result(payload, request_body, response_body)
        persisted = self.persist_artifacts(payload, request_body, response_body, result)
        if persisted:
            result.update(persisted)
        return result

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = _clean_text(payload.get("prompt"))
        if not prompt:
            raise ValueError("vision.analyze requires non-empty prompt.")
        image_parts = self._normalize_image_inputs(payload.get("image_inputs") or [])
        if not image_parts:
            raise ValueError("vision.analyze requires at least one image input.")
        detail = _clean_text(payload.get("detail"))
        content: list[dict[str, Any]] = []
        for item in image_parts:
            part: dict[str, Any] = {"type": "image_url", "image_url": {"url": item["url"]}}
            if detail:
                part["image_url"]["detail"] = detail
            content.append(part)
        content.append({"type": "text", "text": prompt})
        request_body: dict[str, Any] = {
            "model": _clean_text(payload.get("model") or self._default_model),
            "messages": [{"role": "user", "content": content}],
        }
        max_output_tokens = payload.get("max_output_tokens")
        if max_output_tokens:
            request_body["max_tokens"] = int(max_output_tokens)
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
        text = _normalize_visible_text(message.get("content"))
        reasoning = _clean_text(message.get("reasoning_content"))
        annotations: list[dict[str, Any]] = []
        if reasoning:
            annotations.append({"type": "reasoning_content", "text": reasoning})
        return {
            "schema_version": VISION_ANALYZE_CAPABILITY_RESULT_SCHEMA,
            "capability_id": "vision.analyze",
            "provider_id": self._provider_id,
            "model": _clean_text(response_body.get("model") or request_body.get("model")),
            "text": text,
            "annotations": annotations,
            "usage": dict(response_body.get("usage") or {}),
            "finish_reason": _clean_text(first_choice.get("finish_reason")),
            "image_input_count": len((request_body.get("messages") or [{}])[0].get("content") or []) - 1,
            "detail": _clean_text(payload.get("detail")),
            "normalization_notes": [
                "Vision request uses chat-completions content with image_url parts plus a trailing text prompt.",
                "Visible answer text is extracted from message.content and provider reasoning is preserved as optional annotations when present.",
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
        root = path_for_host(workspace_root).resolve() / ".astrabridge" / "capabilities" / "vision_analyze"
        run_id = new_id(f"{self._provider_id}-vision")
        run_dir = root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        request_path = run_dir / "request.json"
        response_path = run_dir / "response.json"
        text_path = run_dir / "text.txt"
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
        text_path.write_text(str(result.get("text") or ""), encoding="utf-8")
        write_json(
            summary_path,
            {
                "saved_at": now_iso(),
                "capability_id": "vision.analyze",
                "provider_id": self._provider_id,
                "model": result.get("model"),
                "image_input_count": result.get("image_input_count"),
                "detail": result.get("detail"),
                "request_path": str(request_path),
                "response_path": str(response_path),
                "text_path": str(text_path),
            },
        )
        return {
            "artifact_refs": [
                {"artifact_type": "request", "path": str(request_path)},
                {"artifact_type": "response", "path": str(response_path)},
                {"artifact_type": "text", "path": str(text_path)},
                {"artifact_type": "summary", "path": str(summary_path)},
            ],
            "artifact_dir": str(run_dir),
        }

    def _normalize_image_inputs(self, image_inputs: Any) -> list[dict[str, str]]:
        items = image_inputs if isinstance(image_inputs, list) else [image_inputs]
        normalized: list[dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            mime_type = _clean_text(item.get("mime_type")) or "image/png"
            data_uri = _clean_text(item.get("data_uri"))
            if data_uri:
                normalized.append({"url": _ensure_data_uri(data_uri, mime_type)})
                continue
            data = _clean_text(item.get("data"))
            if data:
                normalized.append({"url": _ensure_data_uri(data, mime_type)})
                continue
            path_value = _clean_text(item.get("path"))
            if path_value:
                path = path_for_host(path_value)
                file_mime = _mime_type_for_path(path, mime_type)
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                normalized.append({"url": f"data:{file_mime};base64,{encoded}"})
                continue
            url = _clean_text(item.get("url"))
            if url.startswith("data:image/"):
                normalized.append({"url": url})
        return normalized


class QwenVisionAnalyzeAdapter(ChatVisionAnalyzeAdapter):
    def __init__(self, *, api_key: str | None = None, post_fn: Callable[..., Any] | None = None) -> None:
        super().__init__(
            provider_id="qwen",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_model="qwen3.7-plus",
            api_key=api_key,
            env_key="DASHSCOPE_API_KEY",
            post_fn=post_fn,
        )


class KimiVisionAnalyzeAdapter(ChatVisionAnalyzeAdapter):
    def __init__(self, *, api_key: str | None = None, post_fn: Callable[..., Any] | None = None) -> None:
        super().__init__(
            provider_id="kimi",
            base_url="https://api.moonshot.cn/v1",
            default_model="kimi-k2.6",
            api_key=api_key,
            env_key="KIMI_API_KEY",
            env_key_aliases=("MOONSHOT_API_KEY",),
            post_fn=post_fn,
        )
