from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Callable

import requests

from ..common import new_id, now_iso, path_for_host, write_json
from ..multimodal_result_envelope import enrich_capability_result


DASHSCOPE_IMAGE_GENERATE_CAPABILITY_RESULT_SCHEMA = "astrabridge-image-generate-capability-result-v1"
_DEFAULT_DASHSCOPE_IMAGE_BASE_URL = "https://dashscope.aliyuncs.com/api/v1"
_DASHSCOPE_IMAGE_TASKS_PATH = "/services/aigc/text2image/image-synthesis"
_DASHSCOPE_IMAGE_SUPPORTED_MODELS = frozenset({"qwen-image-plus"})
_DASHSCOPE_IMAGE_SIZES = frozenset(
    {
        "auto",
        "1024x1024",
        "1280x720",
        "720x1280",
        "1440x1440",
        "750x1328",
        "1328x750",
    }
)
_DASHSCOPE_IMAGE_MAX_N = 4


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_dashscope_image_base_url(base_url: str | None) -> str:
    normalized = _clean_text(base_url or _DEFAULT_DASHSCOPE_IMAGE_BASE_URL).rstrip("/")
    legacy_suffix = "/compatible-mode/v1"
    if normalized.endswith(legacy_suffix):
        normalized = normalized[: -len(legacy_suffix)] + "/api/v1"
    elif not normalized.endswith("/api/v1"):
        normalized = normalized + "/api/v1"
    return normalized or _DEFAULT_DASHSCOPE_IMAGE_BASE_URL


class DashScopeImageGenerateAdapter:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        post_fn: Callable[..., Any] | None = None,
        get_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._base_url = _normalize_dashscope_image_base_url(base_url)
        self._api_key = _clean_text(api_key)
        self._post = post_fn or requests.post
        self._get = get_fn or requests.get

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = _clean_text(payload.get("api_key")) or self._api_key or _clean_text(os.environ.get("DASHSCOPE_API_KEY"))
        if not api_key:
            raise ValueError("DashScope image generation requires an api_key or DASHSCOPE_API_KEY.")
        request_body = self.build_request(payload)
        response = self._post(
            f"{self._base_url}{_DASHSCOPE_IMAGE_TASKS_PATH}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
            },
            json=request_body,
            timeout=int(payload.get("timeout_sec") or 300),
        )
        response.raise_for_status()
        create_body = response.json()
        task_id = self._extract_task_id(create_body)
        if not task_id:
            raise RuntimeError("DashScope image generation did not return a task_id.")
        poll_body = self.poll_task(task_id, api_key=api_key, timeout_sec=int(payload.get("timeout_sec") or 300))
        result = self.normalize_result(payload, request_body, create_body, poll_body)
        persisted = self.persist_artifacts(payload, request_body, create_body, poll_body, result)
        if persisted:
            result.update(persisted)
        return enrich_capability_result("image.generate", result, workspace_root=payload.get("workspace_root"))

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        operation = _clean_text(payload.get("operation") or "generate").lower() or "generate"
        if operation != "generate":
            raise ValueError("DashScope image adapter currently supports only operation `generate`.")
        prompt = _clean_text(payload.get("prompt"))
        if not prompt:
            raise ValueError("image.generate requires non-empty prompt.")
        model = _clean_text(payload.get("model") or "qwen-image-plus")
        if model not in _DASHSCOPE_IMAGE_SUPPORTED_MODELS:
            supported = ", ".join(sorted(_DASHSCOPE_IMAGE_SUPPORTED_MODELS))
            raise ValueError(f"DashScope image adapter does not support model `{model}`. Supported image models: {supported}.")
        size = _clean_text(payload.get("size") or "1024x1024").lower() or "1024x1024"
        if size not in _DASHSCOPE_IMAGE_SIZES:
            allowed = ", ".join(sorted(_DASHSCOPE_IMAGE_SIZES))
            raise ValueError(f"DashScope image size `{size}` is unsupported. Allowed values: {allowed}.")
        n = self._bounded_n(payload.get("n"))
        image_inputs = self._normalize_reference_images(payload.get("image_inputs") or [])
        request_body: dict[str, Any] = {
            "model": model,
            "input": {
                "prompt": prompt,
            },
            "parameters": {
                "size": size.replace("x", "*"),
                "n": n,
            },
        }
        if image_inputs:
            request_body["input"]["ref_image"] = image_inputs[0]
        watermark = payload.get("watermark")
        if watermark is not None:
            request_body["parameters"]["watermark"] = bool(watermark)
        prompt_extend = payload.get("prompt_extend")
        if prompt_extend is not None:
            request_body["parameters"]["prompt_extend"] = bool(prompt_extend)
        return request_body

    def poll_task(self, task_id: str, *, api_key: str, timeout_sec: int) -> dict[str, Any]:
        response = self._get(
            f"{self._base_url}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_sec,
        )
        response.raise_for_status()
        body = response.json()
        task_status = _clean_text((body.get("output") or {}).get("task_status"))
        if task_status and task_status not in {"SUCCEEDED", "SUCCESS"}:
            raise RuntimeError(f"DashScope image task `{task_id}` did not succeed: {task_status}.")
        return body

    def normalize_result(
        self,
        payload: dict[str, Any],
        request_body: dict[str, Any],
        create_body: dict[str, Any],
        poll_body: dict[str, Any],
    ) -> dict[str, Any]:
        output = poll_body.get("output") if isinstance(poll_body.get("output"), dict) else {}
        results = [dict(item) for item in list(output.get("results") or []) if isinstance(item, dict)]
        artifact_refs = self._normalize_artifact_refs(results)
        requested_n = int((request_body.get("parameters") or {}).get("n") or 0)
        actual_n = len(artifact_refs)
        return {
            "schema_version": DASHSCOPE_IMAGE_GENERATE_CAPABILITY_RESULT_SCHEMA,
            "capability_id": "image.generate",
            "provider_id": "qwen",
            "model": _clean_text(create_body.get("model") or request_body.get("model")),
            "operation": "generate",
            "artifact_refs": artifact_refs,
            "revised_prompt": _clean_text((output.get("input") or {}).get("prompt") or (request_body.get("input") or {}).get("prompt")),
            "requested_n": requested_n,
            "actual_n": actual_n,
            "count_mismatch": actual_n != requested_n,
            "asset_manifest_path": "",
            "task_id": _clean_text(output.get("task_id") or self._extract_task_id(create_body)),
            "task_status": _clean_text(output.get("task_status")),
            "usage": dict(poll_body.get("usage") or {}),
            "finish_reason": _clean_text(output.get("task_status")),
            "normalization_notes": [
                "DashScope image generation is executed as an async image-synthesis task and then normalized into AstraBridge image artifacts.",
                "Only the generate operation is currently supported for the DashScope image family.",
            ],
        }

    def persist_artifacts(
        self,
        payload: dict[str, Any],
        request_body: dict[str, Any],
        create_body: dict[str, Any],
        poll_body: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        workspace_root = payload.get("workspace_root")
        if not workspace_root:
            return {}
        root = path_for_host(workspace_root).resolve() / ".astrabridge" / "capabilities" / "image_generate"
        run_id = new_id("dashscope-image")
        run_dir = root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        request_path = run_dir / "request.json"
        create_response_path = run_dir / "create_response.json"
        poll_response_path = run_dir / "poll_response.json"
        summary_path = run_dir / "summary.json"
        assets_dir = run_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        persisted_assets = self._download_assets(assets_dir, list(result.get("artifact_refs") or []), timeout=int(payload.get("timeout_sec") or 300))
        write_json(
            request_path,
            {
                "saved_at": now_iso(),
                "method": "POST",
                "url": f"{self._base_url}{_DASHSCOPE_IMAGE_TASKS_PATH}",
                "json": request_body,
            },
        )
        write_json(create_response_path, {"saved_at": now_iso(), "body": create_body})
        write_json(poll_response_path, {"saved_at": now_iso(), "body": poll_body})
        asset_manifest_path = run_dir / "asset_manifest.json"
        write_json(asset_manifest_path, {"saved_at": now_iso(), "artifacts": persisted_assets})
        write_json(
            summary_path,
            {
                "saved_at": now_iso(),
                "capability_id": "image.generate",
                "provider_id": "qwen",
                "model": result.get("model"),
                "operation": result.get("operation"),
                "requested_n": result.get("requested_n"),
                "actual_n": result.get("actual_n"),
                "count_mismatch": result.get("count_mismatch"),
                "task_id": result.get("task_id"),
                "task_status": result.get("task_status"),
                "request_path": str(request_path),
                "create_response_path": str(create_response_path),
                "poll_response_path": str(poll_response_path),
                "asset_manifest_path": str(asset_manifest_path),
            },
        )
        return {
            "artifact_refs": persisted_assets,
            "artifact_dir": str(run_dir),
            "asset_manifest_path": str(asset_manifest_path),
        }

    def _normalize_reference_images(self, image_inputs: Any) -> list[str]:
        items = image_inputs if isinstance(image_inputs, list) else [image_inputs]
        normalized: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            url = _clean_text(item.get("url"))
            if url.startswith("https://"):
                normalized.append(url)
                continue
            data_uri = _clean_text(item.get("data_uri"))
            if data_uri.startswith("data:image/"):
                normalized.append(data_uri)
                continue
            data = _clean_text(item.get("data"))
            mime_type = _clean_text(item.get("mime_type")) or "image/png"
            if data:
                normalized.append(data if data.startswith("data:image/") else f"data:{mime_type};base64,{data}")
                continue
            path_value = _clean_text(item.get("path"))
            if path_value:
                path = path_for_host(path_value)
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                normalized.append(f"data:{mime_type};base64,{encoded}")
        return normalized[:1]

    def _normalize_artifact_refs(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for index, item in enumerate(results):
            url = _clean_text(item.get("url"))
            if not url:
                continue
            refs.append(
                {
                    "asset_id": _clean_text(item.get("orig_prompt") or f"dashscope-image-{index}") or f"dashscope-image-{index}",
                    "source_url": url,
                    "result_index": index,
                    "validation_warnings": [],
                }
            )
        return refs

    def _download_assets(self, assets_dir: Path, artifact_refs: list[dict[str, Any]], *, timeout: int) -> list[dict[str, Any]]:
        persisted: list[dict[str, Any]] = []
        for index, item in enumerate(artifact_refs):
            ref = dict(item)
            url = _clean_text(ref.get("source_url"))
            local_path = ""
            if url:
                response = self._get(url, timeout=timeout)
                raise_for_status = getattr(response, "raise_for_status", None)
                if callable(raise_for_status):
                    raise_for_status()
                content = getattr(response, "content", b"")
                body = content if isinstance(content, bytes) else bytes(content or b"")
                local = assets_dir / f"result-{index}.png"
                local.write_bytes(body)
                local_path = str(local)
            ref["local_path"] = local_path
            ref["asset_id"] = f"dashscope-image-{index}"
            persisted.append(ref)
        return persisted

    def _extract_task_id(self, body: dict[str, Any]) -> str:
        output = body.get("output") if isinstance(body.get("output"), dict) else {}
        return _clean_text(output.get("task_id"))

    def _bounded_n(self, value: Any) -> int:
        try:
            parsed = int(value or 1)
        except (TypeError, ValueError):
            parsed = 1
        return min(max(parsed, 1), _DASHSCOPE_IMAGE_MAX_N)
