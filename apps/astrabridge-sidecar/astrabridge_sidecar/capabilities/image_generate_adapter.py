from __future__ import annotations

from typing import Any

from ..yunwu_image_service import YunwuImageService


IMAGE_GENERATE_CAPABILITY_RESULT_SCHEMA = "astrabridge-image-generate-capability-result-v1"


class YunwuImageGenerateAdapter:
    def __init__(self, service: YunwuImageService | None = None) -> None:
        self._service = service or YunwuImageService()

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._service.generate(
            prompt=str(payload.get("prompt") or ""),
            model=str(payload.get("model") or "gpt-image-2"),
            size=str(payload.get("size") or "1024x1024"),
            n=int(payload.get("n") or 1),
            image_urls=[str(item) for item in (payload.get("image_urls") or [])],
            response_format=str(payload.get("response_format") or "url"),
            quality=str(payload.get("quality") or "auto"),
            image_format=str(payload.get("image_format") or payload.get("format") or payload.get("output_format") or "png"),
            background=str(payload.get("background") or "") or None,
            prompt_category=str(payload.get("prompt_category") or ""),
            api_key=str(payload.get("api_key") or "") or None,
            timeout_sec=int(payload.get("timeout_sec") or 300),
            workspace_root=payload.get("workspace_root"),
            purpose=str(payload.get("purpose") or "capability_image_generate"),
        )
        return self.normalize_result(result, operation="generate")

    def edit_as_generation(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._service.edit(
            prompt=str(payload.get("prompt") or ""),
            image_paths=[str(item) for item in (payload.get("image_paths") or [])],
            mask_path=str(payload.get("mask_path") or "") or None,
            model=str(payload.get("model") or "gpt-image-2"),
            size=str(payload.get("size") or "1024x1024"),
            n=int(payload.get("n") or 1),
            quality=str(payload.get("quality") or "auto"),
            background=str(payload.get("background") or "auto"),
            moderation=str(payload.get("moderation") or "auto"),
            prompt_category=str(payload.get("prompt_category") or ""),
            reference_image_mode=payload.get("reference_image_mode"),
            api_key=str(payload.get("api_key") or "") or None,
            timeout_sec=int(payload.get("timeout_sec") or 300),
            workspace_root=payload.get("workspace_root"),
            purpose=str(payload.get("purpose") or "capability_image_edit"),
        )
        return self.normalize_result(result, operation="edit")

    def transparent_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._service.transparent_asset(
            prompt=str(payload.get("prompt") or ""),
            model=str(payload.get("model") or "gpt-image-2"),
            size=str(payload.get("size") or "1024x1024"),
            n=int(payload.get("n") or 1),
            quality=str(payload.get("quality") or "high"),
            moderation=str(payload.get("moderation") or "auto"),
            prompt_category=str(payload.get("prompt_category") or "game_asset_japanese_anime"),
            reference_image_mode=bool(payload.get("reference_image_mode", False)),
            api_key=str(payload.get("api_key") or "") or None,
            timeout_sec=int(payload.get("timeout_sec") or 300),
            workspace_root=payload.get("workspace_root"),
            purpose=str(payload.get("purpose") or "capability_transparent_asset"),
        )
        return self.normalize_result(result, operation="transparent_asset")

    def normalize_result(self, result: dict[str, Any], *, operation: str) -> dict[str, Any]:
        persisted_assets = [dict(item) for item in (result.get("persisted_assets") or []) if isinstance(item, dict)]
        artifact_refs = persisted_assets or self._fallback_artifact_refs(result)
        revised_prompt = ""
        for item in result.get("data") or []:
            if isinstance(item, dict) and str(item.get("revised_prompt") or "").strip():
                revised_prompt = str(item.get("revised_prompt") or "").strip()
                break
        if not revised_prompt:
            for item in persisted_assets:
                if str(item.get("revised_prompt") or "").strip():
                    revised_prompt = str(item.get("revised_prompt") or "").strip()
                    break
        model = ""
        for item in persisted_assets:
            if str(item.get("model") or "").strip():
                model = str(item.get("model") or "").strip()
                break
        return {
            "schema_version": IMAGE_GENERATE_CAPABILITY_RESULT_SCHEMA,
            "capability_id": "image.generate",
            "provider_id": "yunwu",
            "model": model,
            "operation": operation,
            "artifact_refs": artifact_refs,
            "revised_prompt": revised_prompt,
            "requested_n": int(result.get("requested_n") or 0),
            "actual_n": int(result.get("actual_n") or len(artifact_refs)),
            "count_mismatch": bool(result.get("count_mismatch", False)),
            "asset_manifest_path": str(result.get("asset_manifest_path") or ""),
        }

    def _fallback_artifact_refs(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for index, item in enumerate(result.get("data") or []):
            if not isinstance(item, dict):
                continue
            refs.append(
                {
                    "asset_id": str(item.get("asset_id") or ""),
                    "local_path": str(item.get("local_path") or ""),
                    "source_url": str(item.get("url") or ""),
                    "result_index": index,
                    "has_alpha": bool(item.get("has_alpha", False)),
                    "transparency_status": str(item.get("transparency_status") or ""),
                    "actual_width": item.get("actual_width"),
                    "actual_height": item.get("actual_height"),
                    "actual_format": str(item.get("actual_format") or ""),
                    "validation_warnings": list(item.get("validation_warnings") or []),
                }
            )
        return refs
