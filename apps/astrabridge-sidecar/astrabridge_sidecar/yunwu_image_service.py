from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import re
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, app_runtime_dir, now_iso, path_for_host, read_json, write_json
from .image_prompt_strategy import apply_prompt_guide, prompt_guides_payload


GENERATION_SIZES = {
    "auto",
    "1024x1024",
    "1536x1024",
    "1024x1536",
    "2048x2048",
    "2048x1152",
    "3840x2160",
    "2160x3840",
}
EDIT_SIZES = {
    "auto",
    "1024x1024",
    "1536x1024",
    "1024x1536",
    "2048x2048",
    "2048x1152",
    "3840x2160",
    "2160x3840",
}
GENERATION_IMAGE_MODELS = {"gpt-image-2", "gpt-image-2-all"}
EDIT_IMAGE_MODELS = {
    "gpt-image-1",
    "gpt-image-2",
    "gpt-image-2-all",
}
QUALITY_VALUES = {"low", "medium", "high", "auto"}
IMAGE_FORMAT_VALUES = {"png", "jpeg", "webp"}
RESPONSE_FORMAT_VALUES = {"url", "b64_json"}
BACKGROUND_VALUES = {"opaque", "auto", "transparent"}
MODERATION_VALUES = {"low", "auto"}
MAX_GENERATION_N = 10
MAX_YUNWU_IMAGE_CONCURRENCY = 5
MAX_GENERATION_REFERENCE_URLS = 5
MAX_EDIT_IMAGES = 15
TRANSPARENT_ALPHA_MIN_RATIO = 0.01
YUNWU_IMAGE_RETRY_ATTEMPTS = 3
YUNWU_IMAGE_RETRY_BASE_DELAY_SEC = 1.0
_IMAGE_URL_PATTERN = re.compile(r"https?://[^\s)\"']+\.(?:png|jpe?g|webp)(?:\?[^\s)\"']*)?", re.IGNORECASE)


class YunwuImageService:
    def __init__(self, base_url: str = "https://yunwu.ai/v1") -> None:
        self.base_url = base_url.rstrip("/")

    def capability_generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .capabilities.image_generate_adapter import YunwuImageGenerateAdapter

        return YunwuImageGenerateAdapter(self).generate(payload)

    def capability_edit(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .capabilities.image_generate_adapter import YunwuImageGenerateAdapter

        return YunwuImageGenerateAdapter(self).edit_as_generation(payload)

    def capability_transparent_asset(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .capabilities.image_generate_adapter import YunwuImageGenerateAdapter

        return YunwuImageGenerateAdapter(self).transparent_asset(payload)

    def transparent_asset(
        self,
        *,
        prompt: str,
        model: str = "gpt-image-2",
        size: str = "1024x1024",
        n: int = 1,
        quality: str = "high",
        moderation: str = "auto",
        prompt_category: str = "game_asset_japanese_anime",
        reference_image_mode: bool = False,
        api_key: str | None = None,
        timeout_sec: int = 300,
        workspace_root: str | Path | None = None,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        """Generate a transparent game asset through the edits route.

        Yunwu generation can return RGB images even when the prompt asks for
        transparency. For cutout sprites, this route creates a blank transparent
        seed image and calls /images/edits with background=transparent so the
        request is both semantically and structurally transparent.
        """
        seed_path = self._ensure_transparent_seed(workspace_root=workspace_root, size=size)
        return self.edit(
            prompt=prompt,
            image_paths=[str(seed_path)],
            model=model,
            size=size,
            n=n,
            quality=quality,
            background="transparent",
            moderation=moderation,
            prompt_category=prompt_category,
            reference_image_mode=reference_image_mode,
            api_key=api_key,
            timeout_sec=timeout_sec,
            workspace_root=workspace_root,
            purpose=purpose or "transparent_asset_edit_route",
        )

    def generate(
        self,
        *,
        prompt: str,
        model: str = "gpt-image-2",
        size: str = "1024x1024",
        n: int = 1,
        image_urls: list[str] | None = None,
        response_format: str = "url",
        quality: str = "auto",
        image_format: str = "png",
        background: str | None = None,
        prompt_category: str = "",
        api_key: str | None = None,
        timeout_sec: int = 300,
        workspace_root: str | Path | None = None,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        key = self._resolve_api_key(api_key)
        payload = self.generation_payload(
            prompt=prompt,
            model=model,
            size=size,
            n=n,
            image_urls=image_urls,
            response_format=response_format,
            quality=quality,
            image_format=image_format,
            background=background,
            prompt_category=prompt_category,
            purpose=purpose or "generation",
        )
        requested_n = self._bounded_n(n)
        result = self._normalize_generation_result(self._json_post("/images/generations", payload, key, timeout_sec=timeout_sec))
        return self._persist_assets(
            result,
            workspace_root=workspace_root,
            prompt=str(payload.get("prompt") or prompt),
            model=model,
            size=size,
            quality=quality,
            image_format=image_format,
            requested_background=background or "",
            requested_n=requested_n,
            purpose=purpose or "generation",
            source="yunwu_images_generations",
            prompt_category=str(payload.get("prompt_category") or prompt_category or ""),
            prompt_strategy_metadata={
                "prompt_guide_display_name": payload.get("prompt_guide_display_name"),
                "asset_mode": payload.get("asset_mode"),
                "prompt_enhancement_applied": bool(payload.get("prompt_enhancement_applied")),
            },
        )

    def edit(
        self,
        *,
        prompt: str,
        image_paths: list[str],
        model: str = "gpt-image-2",
        size: str = "1024x1024",
        n: int = 1,
        quality: str = "auto",
        background: str = "auto",
        moderation: str = "auto",
        mask_path: str | None = None,
        prompt_category: str = "",
        reference_image_mode: bool | None = None,
        api_key: str | None = None,
        timeout_sec: int = 300,
        workspace_root: str | Path | None = None,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        key = self._resolve_api_key(api_key)
        fields, files = self.edit_payload(
            prompt=prompt,
            image_paths=image_paths,
            model=model,
            size=size,
            n=n,
            quality=quality,
            background=background,
            moderation=moderation,
            mask_path=mask_path,
            prompt_category=prompt_category,
            reference_image_mode=reference_image_mode,
            purpose=purpose or "edit",
        )
        result = self._multipart_post("/images/edits", fields, files, key, timeout_sec=timeout_sec)
        result = self._normalize_generation_result(result)
        requested_n = self._bounded_n(n)
        return self._persist_assets(
            result,
            workspace_root=workspace_root,
            prompt=str(fields.get("prompt") or prompt),
            model=model,
            size=size,
            quality=quality,
            image_format="",
            requested_background=background,
            requested_n=requested_n,
            purpose=purpose or "edit",
            source="yunwu_images_edits",
            prompt_category=str(fields.get("prompt_category") or prompt_category or ""),
            prompt_strategy_metadata={
                "prompt_guide_display_name": fields.get("prompt_guide_display_name"),
                "asset_mode": fields.get("asset_mode"),
                "prompt_enhancement_applied": str(fields.get("prompt_enhancement_applied") or "").lower() == "true",
            },
        )

    def protocol(self) -> dict[str, Any]:
        return {
            "schema_version": 4,
            "provider": "yunwu",
            "base_url": self.base_url,
            "max_concurrency": MAX_YUNWU_IMAGE_CONCURRENCY,
            "prompt_guides": prompt_guides_payload(),
            "generation": {
                "endpoint": "/images/generations",
                "method": "POST",
                "content_type": "application/json",
                "models": sorted(GENERATION_IMAGE_MODELS),
                "parameters": {
                    "model": {"required": True, "type": "string"},
                    "prompt": {"required": True, "type": "string", "max_length": 1000},
                    "size": {"required": False, "type": "string", "values": sorted(GENERATION_SIZES), "custom_rule": "WIDTHxHEIGHT, both dimensions multiple of 16, max edge <= 3840, aspect <= 3:1, pixels 655360..8294400"},
                    "format": {
                        "required": False,
                        "type": "string",
                        "values": sorted(IMAGE_FORMAT_VALUES),
                        "aliases": ["image_format", "output_format"],
                        "note": "Yunwu request field is format; OpenAI-compatible callers may call the same concept output_format.",
                    },
                    "quality": {"required": False, "type": "string", "values": sorted(QUALITY_VALUES)},
                    "n": {"required": True, "type": "integer", "minimum": 1, "maximum": MAX_GENERATION_N},
                    "response_format": {"required": False, "type": "string", "values": sorted(RESPONSE_FORMAT_VALUES)},
                    "image": {"required": False, "type": "array[url]", "maximum": MAX_GENERATION_REFERENCE_URLS, "note": "Supported by some Yunwu composition routes such as gpt-image-2-all."},
                    "background": {
                        "required": False,
                        "type": "string",
                        "values": sorted(BACKGROUND_VALUES),
                        "note": "Use background=transparent as a structured request parameter for transparent game assets; do not rely on prompt wording alone.",
                    },
                    "prompt_category": {
                        "required": False,
                        "type": "string",
                        "default": "japanese_anime_style",
                        "note": "AstraBridge applies a local prompt-guide enhancement before the request and records the category in the asset manifest.",
                    },
                },
            },
            "edit": {
                "endpoint": "/images/edits",
                "method": "POST",
                "content_type": "multipart/form-data",
                "models": sorted(EDIT_IMAGE_MODELS),
                "parameters": {
                    "image": {"required": True, "type": "file[]", "maximum": MAX_EDIT_IMAGES, "max_total_hint": "each file <= 50MB"},
                    "prompt": {"required": True, "type": "string"},
                    "mask": {"required": False, "type": "png file", "maximum_size": "4MB", "note": "Applies to the first image when multiple inputs are provided."},
                    "model": {"required": False, "type": "string", "values": sorted(EDIT_IMAGE_MODELS)},
                    "n": {"required": False, "type": "integer", "minimum": 1, "maximum": MAX_GENERATION_N},
                    "quality": {"required": False, "type": "string", "values": sorted(QUALITY_VALUES)},
                    "size": {"required": False, "type": "string", "values": sorted(EDIT_SIZES), "custom_rule": "WIDTHxHEIGHT, both dimensions multiple of 16, max edge <= 3840, aspect <= 3:1, pixels 655360..8294400"},
                    "background": {"required": False, "type": "string", "values": sorted(BACKGROUND_VALUES), "recommended_for_transparency": "transparent"},
                    "moderation": {"required": False, "type": "string", "values": sorted(MODERATION_VALUES)},
                    "prompt_category": {
                        "required": False,
                        "type": "string",
                        "default": "image_edit_recreation",
                        "note": "AstraBridge applies a local prompt-guide enhancement before the request and records the category in the asset manifest.",
                    },
                },
            },
            "transparent_asset_edit_route": {
                "endpoint": "/images/edits",
                "method": "POST",
                "content_type": "multipart/form-data",
                "default_model": "gpt-image-2",
                "default_params": {"size": "1024x1024", "n": 1, "quality": "high", "background": "transparent", "moderation": "auto"},
                "seed_image": "AstraBridge creates a blank transparent seed PNG and sends it as the edit image when no reference image is available.",
                "prompt_suffix": "Prompt is automatically reinforced with an alpha definition: outside-object pixels must be alpha=0, not white, black, or checkerboard.",
                "use_for": [
                    "single character sprites",
                    "monster sprites",
                    "doors",
                    "stairs",
                    "keys",
                    "gems",
                    "HUD icons",
                    "transparent cutout redraws",
                ],
                "avoid_for": ["large painted scenes", "non-cutout backgrounds", "complex multi-category collages"],
            },
            "transparent_asset_contract": {
                "default_params": {"format": "png", "quality": "high", "background": "transparent"},
                "required_validation": [
                    "actual_width",
                    "actual_height",
                    "actual_format",
                    "actual_mode",
                    "has_alpha",
                    "transparent_pixel_ratio",
                    "semi_transparent_pixel_ratio",
                    "size_matches_request",
                    "format_matches_request",
                    "transparency_status",
                    "validation_warnings",
                ],
                "failure_taxonomy": [
                    "transparent_contract_failed",
                    "alpha_channel_missing",
                    "alpha_ratio_too_low",
                    "size_mismatch",
                    "format_mismatch",
                    "style_inconsistent",
                    "character_inconsistent",
                    "not_tileable",
                    "multi_asset_sheet_hard_to_slice",
                ],
            },
            "game_asset_policy": {
                "heroine_consistency": "Choose one approved heroine reference, then use edit/reference routes for idle and walk_down/up/left/right frames.",
                "single_asset_first": "Use one transparent image per door, stair, key, monster, gem, HUD icon, and battle portrait.",
                "sheet_only_for_same_category": "Use multi-asset sheets only for terrain tilesets, HUD icons, or same-style decorations with large gutters and regular layout.",
                "redraw_over_bad_slicing": "If alpha, size, semantic class, slice score, or visual review fails, redraw as a single transparent asset or a more regular sheet.",
            },
            "count_contract": {
                "requested_n": "AstraBridge records requested_n, actual_n, and count_mismatch because Yunwu may return a different number of assets.",
                "n_greater_than_1": "Treat n>1 as an unstable batch mode until a health check proves it stable for the selected model/route.",
                "default_batching": f"For production asset draws, prefer concurrent n=1 requests with max concurrency {MAX_YUNWU_IMAGE_CONCURRENCY}.",
                "retry_policy": "If actual_n is smaller than requested_n, callers may retry the missing count with at most 5 concurrent requests.",
            },
        }

    def test_connectivity(self, *, api_key: str | None = None, timeout_sec: int = 300) -> dict[str, Any]:
        started = time.time()
        result = self.generate(
            prompt="A tiny clean blue dot icon centered on a white background.",
            model="gpt-image-2",
            size="1024x1024",
            n=1,
            response_format="url",
            api_key=api_key,
            timeout_sec=timeout_sec,
        )
        return {
            "ok": True,
            "provider": "yunwu",
            "tool": "yunwu_image_generate",
            "model": "gpt-image-2",
            "elapsed_ms": int((time.time() - started) * 1000),
            "created": result.get("created"),
            "data": self._sanitize_data(result.get("data")),
            "timestamp": now_iso(),
        }

    def generation_payload(
        self,
        *,
        prompt: str,
        model: str = "gpt-image-2",
        size: str = "1024x1024",
        n: int = 1,
        image_urls: list[str] | None = None,
        response_format: str = "url",
        quality: str = "auto",
        image_format: str = "png",
        background: str | None = None,
        prompt_category: str = "",
        purpose: str = "",
    ) -> dict[str, Any]:
        prompt = str(prompt or "").strip()
        if not prompt:
            raise ValueError("Image prompt is required.")
        if model not in GENERATION_IMAGE_MODELS:
            raise ValueError(f"Unsupported Yunwu image model: {model}")
        self._validate_image_size(size, allowed_named=GENERATION_SIZES)
        count = self._bounded_n(n)
        if response_format not in RESPONSE_FORMAT_VALUES:
            raise ValueError("response_format must be url or b64_json.")
        if quality not in QUALITY_VALUES:
            raise ValueError("quality must be low, medium, high, or auto.")
        if image_format not in IMAGE_FORMAT_VALUES:
            raise ValueError("format must be png, jpeg, or webp.")
        normalized_background = str(background or "").strip()
        if normalized_background:
            if normalized_background not in BACKGROUND_VALUES:
                raise ValueError("background must be opaque, transparent, or auto.")
            if normalized_background == "transparent" and image_format == "jpeg":
                raise ValueError("transparent background requires png or webp format.")
        prompt_strategy = apply_prompt_guide(
            category_id=prompt_category or "japanese_anime_style",
            user_prompt=prompt,
            purpose=purpose,
            transparent_background=normalized_background == "transparent",
            reference_image_mode=bool(image_urls),
        )
        prompt = str(prompt_strategy["prompt"] or "")
        prompt = self._apply_transparent_prompt_contract(prompt, background=normalized_background)
        if len(prompt) > 1000:
            raise ValueError("Yunwu gpt-image-2 prompt must be 1000 characters or fewer.")
        payload: dict[str, Any] = {
            "model": model,
            "size": size,
            "n": count,
            "prompt": prompt,
            "response_format": response_format,
            "quality": quality,
            "format": image_format,
            "prompt_category": str(prompt_strategy["category_id"] or ""),
            "prompt_guide_display_name": str(prompt_strategy["guide_display_name"] or ""),
            "asset_mode": str(prompt_strategy["asset_mode"] or ""),
            "prompt_enhancement_applied": bool(prompt_strategy["enhancement_applied"]),
        }
        if normalized_background:
            payload["background"] = normalized_background
        urls = [str(item).strip() for item in (image_urls or []) if str(item).strip()]
        if urls:
            if len(urls) > MAX_GENERATION_REFERENCE_URLS:
                raise ValueError(f"Generation image URL input supports at most {MAX_GENERATION_REFERENCE_URLS} images.")
            if not all(url.startswith(("http://", "https://")) for url in urls):
                raise ValueError("Generation image inputs must be HTTP(S) URLs.")
            payload["image"] = urls
        return payload

    def edit_payload(
        self,
        *,
        prompt: str,
        image_paths: list[str],
        model: str = "gpt-image-2",
        size: str = "1024x1024",
        n: int = 1,
        quality: str = "auto",
        background: str = "auto",
        moderation: str = "auto",
        mask_path: str | None = None,
        prompt_category: str = "",
        reference_image_mode: bool | None = None,
        purpose: str = "",
    ) -> tuple[dict[str, str], list[tuple[str, Path]]]:
        prompt = str(prompt or "").strip()
        if not prompt:
            raise ValueError("Image edit prompt is required.")
        if model not in EDIT_IMAGE_MODELS:
            raise ValueError(f"Unsupported Yunwu image model: {model}")
        self._validate_image_size(size, allowed_named=EDIT_SIZES)
        if quality not in QUALITY_VALUES:
            raise ValueError("quality must be low, medium, high, or auto.")
        if background not in BACKGROUND_VALUES:
            raise ValueError("background must be opaque, transparent, or auto.")
        if background == "transparent" and size == "auto":
            # Keep this allowed because Yunwu accepts auto, but surface a consistent
            # field set to downstream validators by preserving background metadata.
            pass
        if moderation not in MODERATION_VALUES:
            raise ValueError("moderation must be low or auto.")
        prompt_strategy = apply_prompt_guide(
            category_id=prompt_category or "image_edit_recreation",
            user_prompt=prompt,
            purpose=purpose,
            transparent_background=background == "transparent",
            reference_image_mode=bool(image_paths) if reference_image_mode is None else bool(reference_image_mode),
        )
        prompt = str(prompt_strategy["prompt"] or "")
        prompt = self._apply_transparent_prompt_contract(prompt, background=background)
        if len(prompt) > 1000:
            raise ValueError("Yunwu gpt-image-2 edit prompt must be 1000 characters or fewer.")
        paths = [Path(item).expanduser().resolve() for item in image_paths if str(item).strip()]
        if not paths:
            raise ValueError("At least one image path is required for image edits.")
        if len(paths) > MAX_EDIT_IMAGES:
            raise ValueError("Yunwu image edits support fewer than 16 images.")
        for path in paths:
            if not path.is_file():
                raise ValueError(f"Image file does not exist: {path}")
            if path.stat().st_size > 50 * 1024 * 1024:
                raise ValueError(f"Image file exceeds 50MB: {path.name}")
        files = [("image", path) for path in paths]
        if mask_path:
            mask = Path(mask_path).expanduser().resolve()
            if not mask.is_file():
                raise ValueError(f"Mask file does not exist: {mask}")
            if mask.stat().st_size > 4 * 1024 * 1024:
                raise ValueError("Mask file exceeds 4MB.")
            files.append(("mask", mask))
        fields = {
            "prompt": prompt,
            "model": model,
            "n": str(self._bounded_n(n)),
            "quality": quality,
            "size": size,
            "background": background,
            "moderation": moderation,
            "prompt_category": str(prompt_strategy["category_id"] or ""),
            "prompt_guide_display_name": str(prompt_strategy["guide_display_name"] or ""),
            "asset_mode": str(prompt_strategy["asset_mode"] or ""),
            "prompt_enhancement_applied": "true" if prompt_strategy["enhancement_applied"] else "false",
        }
        return fields, files

    def _json_post(self, path: str, payload: dict[str, Any], api_key: str, *, timeout_sec: int) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        return self._open_json(request, timeout_sec)

    def _multipart_post(
        self,
        path: str,
        fields: dict[str, str],
        files: list[tuple[str, Path]],
        api_key: str,
        *,
        timeout_sec: int,
    ) -> dict[str, Any]:
        boundary = f"----astrabridge-yunwu-{uuid.uuid4().hex}"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            chunks.append(str(value).encode("utf-8"))
            chunks.append(b"\r\n")
        for name, path_value in files:
            mime = mimetypes.guess_type(path_value.name)[0] or "application/octet-stream"
            chunks.append(f"--{boundary}\r\n".encode("utf-8"))
            chunks.append(
                f'Content-Disposition: form-data; name="{name}"; filename="{path_value.name}"\r\n'
                f"Content-Type: {mime}\r\n\r\n".encode("utf-8")
            )
            chunks.append(path_value.read_bytes())
            chunks.append(b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(chunks)
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        return self._open_json(request, timeout_sec)

    def _open_json(self, request: urllib.request.Request, timeout_sec: int) -> dict[str, Any]:
        attempt = 0
        while True:
            attempt += 1
            try:
                with urllib.request.urlopen(request, timeout=timeout_sec) as response:
                    raw = response.read()
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                if attempt < YUNWU_IMAGE_RETRY_ATTEMPTS and self._retryable_http_status(exc.code):
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise RuntimeError(f"Yunwu image API returned HTTP {exc.code}: {self._safe_excerpt(raw)}") from exc
            except urllib.error.URLError as exc:
                if attempt < YUNWU_IMAGE_RETRY_ATTEMPTS and self._retryable_url_error(exc):
                    time.sleep(self._retry_delay(attempt))
                    continue
                raise RuntimeError(f"Yunwu image API connection failed: {exc.reason}") from exc

    def _retryable_http_status(self, status_code: int) -> bool:
        return int(status_code) in {408, 429, 500, 502, 503, 504}

    def _retryable_url_error(self, exc: urllib.error.URLError) -> bool:
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            return True
        text = str(reason or "").lower()
        return any(
            token in text
            for token in (
                "unexpected eof",
                "eof occurred in violation of protocol",
                "connection reset",
                "timed out",
                "timeout",
                "temporary failure",
                "tls",
                "ssl",
            )
        )

    def _retry_delay(self, attempt: int) -> float:
        return YUNWU_IMAGE_RETRY_BASE_DELAY_SEC * (2 ** max(attempt - 1, 0))

    def _resolve_api_key(self, api_key: str | None) -> str:
        key = str(api_key or os.environ.get("YUNWU_API_KEY") or os.environ.get("YUNWU_IMAGE_API_KEY") or "").strip()
        if not key:
            raise PermissionError("YUNWU_API_KEY is missing. Load it from LLM API Manager, paste a session key, or set the environment variable before using the image tool.")
        return key

    def _validate_image_size(self, size: str, *, allowed_named: set[str]) -> None:
        value = str(size or "").strip().lower()
        if value in allowed_named:
            return
        match = re.fullmatch(r"(\d+)x(\d+)", value)
        if not match:
            raise ValueError("Image size must be auto or WIDTHxHEIGHT.")
        width = int(match.group(1))
        height = int(match.group(2))
        long_edge = max(width, height)
        short_edge = min(width, height)
        pixels = width * height
        if long_edge > 3840:
            raise ValueError("Image size max edge must be <= 3840px.")
        if width % 16 != 0 or height % 16 != 0:
            raise ValueError("Image width and height must both be multiples of 16.")
        if short_edge <= 0 or long_edge / short_edge > 3:
            raise ValueError("Image aspect ratio must be <= 3:1.")
        if pixels < 655_360 or pixels > 8_294_400:
            raise ValueError("Image total pixels must be between 655360 and 8294400.")

    def _bounded_n(self, value: int | str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 1
        return min(max(parsed, 1), MAX_GENERATION_N)

    def _normalize_generation_result(self, result: dict[str, Any]) -> dict[str, Any]:
        data = result.get("data")
        if isinstance(data, list):
            return result
        extracted: list[dict[str, Any]] = []
        choices = result.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message")
                content = message.get("content") if isinstance(message, dict) else choice.get("text")
                extracted.extend(self._extract_items_from_content(content))
        if extracted:
            normalized = dict(result)
            normalized["data"] = extracted
            normalized.setdefault("created", int(time.time()))
            return normalized
        return {**result, "data": []}

    def _extract_items_from_content(self, content: Any) -> list[dict[str, Any]]:
        if isinstance(content, list):
            items: list[dict[str, Any]] = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("url"):
                        items.append({"url": str(part.get("url") or ""), "revised_prompt": part.get("revised_prompt") or ""})
                    elif part.get("b64_json"):
                        items.append({"b64_json": str(part.get("b64_json") or ""), "revised_prompt": part.get("revised_prompt") or ""})
                    elif part.get("text"):
                        items.extend(self._extract_items_from_content(part.get("text")))
            return items
        text = str(content or "").strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            if isinstance(parsed.get("data"), list):
                return [item for item in parsed["data"] if isinstance(item, dict)]
            if parsed.get("url") or parsed.get("b64_json"):
                return [parsed]
        return [{"url": match.group(0), "revised_prompt": ""} for match in _IMAGE_URL_PATTERN.finditer(text)]

    def _safe_excerpt(self, text: str) -> str:
        return text.replace("Bearer ", "Bearer [REDACTED]")[:1200]

    def _sanitize_data(self, data: Any) -> list[dict[str, Any]]:
        if not isinstance(data, list):
            return []
        sanitized: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            entry: dict[str, Any] = {}
            if item.get("url"):
                entry["url"] = self._sanitize_source_url(str(item.get("url") or ""))
            if item.get("revised_prompt") is not None:
                entry["revised_prompt"] = item.get("revised_prompt")
            if item.get("b64_json"):
                decoded = base64.b64decode(str(item["b64_json"]), validate=False)
                entry["b64_json_bytes"] = len(decoded)
            sanitized.append(entry)
        return sanitized

    def _apply_transparent_prompt_contract(self, prompt: str, *, background: str) -> str:
        if background != "transparent":
            return prompt
        lowered = prompt.lower()
        if "alpha=0" in lowered or "transparent background means" in lowered:
            return prompt[:1000]
        suffix = (
            " Transparent background means every pixel outside the asset silhouette must be alpha=0; "
            "do not paint white, black, grey, checkerboard, paper, canvas, scenery, floor, frame, or shadow behind it. "
            "Output a clean cutout PNG with transparent background. Transparent background, alpha=0 outside the object."
        )
        limit = 1000 - len(suffix)
        if limit <= 0:
            return suffix[:1000]
        base = prompt[:limit].rstrip()
        return f"{base}{suffix}"

    def _ensure_transparent_seed(self, *, workspace_root: str | Path | None, size: str) -> Path:
        parsed_size = self._parse_exact_size(size) or (1024, 1024)
        if workspace_root:
            root = path_for_host(workspace_root).resolve()
            seed_root = root / WORKSPACE_STATE_DIRNAME / "assets" / "generated" / "_seeds"
            seed_root.mkdir(parents=True, exist_ok=True)
            path = seed_root / f"transparent_seed_{parsed_size[0]}x{parsed_size[1]}.png"
            if not path.exists():
                path.write_bytes(self._blank_transparent_png_bytes(*parsed_size))
            return path
        seed_root = app_runtime_dir("yunwu", "seeds")
        path = seed_root / f"transparent_seed_{parsed_size[0]}x{parsed_size[1]}.png"
        if not path.exists():
            path.write_bytes(self._blank_transparent_png_bytes(*parsed_size))
        return path

    def _blank_transparent_png_bytes(self, width: int, height: int) -> bytes:
        def chunk(kind: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)

        row = bytes([0]) + bytes([0, 0, 0, 0]) * width
        raw = row * height
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )

    def _persist_assets(
        self,
        result: dict[str, Any],
        *,
        workspace_root: str | Path | None,
        prompt: str,
        model: str,
        size: str,
        quality: str,
        image_format: str,
        requested_background: str,
        requested_n: int,
        purpose: str,
        source: str,
        prompt_category: str,
        prompt_strategy_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data_for_count = result.get("data") if isinstance(result.get("data"), list) else []
        count_metadata = {
            "requested_n": requested_n,
            "actual_n": len(data_for_count),
            "count_mismatch": len(data_for_count) != requested_n,
            "max_concurrency": MAX_YUNWU_IMAGE_CONCURRENCY,
        }
        if not workspace_root:
            return {**result, **count_metadata}
        root = path_for_host(workspace_root).resolve()
        asset_root = root / WORKSPACE_STATE_DIRNAME / "assets" / "generated"
        asset_root.mkdir(parents=True, exist_ok=True)
        manifest_path = asset_root / "asset_manifest.json"
        manifest = read_json(manifest_path, {"assets": []})
        if not isinstance(manifest, dict):
            manifest = {"assets": []}
        assets = list(manifest.get("assets") or [])
        created = result.get("created")
        data = result.get("data") if isinstance(result.get("data"), list) else []
        persisted: list[dict[str, Any]] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            asset_id = f"yunwu-{created or int(time.time())}-{uuid.uuid4().hex[:8]}"
            local_path = ""
            save_error = ""
            if item.get("b64_json"):
                local_path, save_error = self._save_b64(asset_root, asset_id, str(item.get("b64_json") or ""))
            elif item.get("url"):
                local_path, save_error = self._download_url(asset_root, asset_id, str(item.get("url") or ""))
                item["url"] = self._sanitize_source_url(str(item.get("url") or ""))
            record = {
                "asset_id": asset_id,
                "provider": "yunwu",
                "tool": "yunwu_image_generate" if source.endswith("generations") else "yunwu_image_edit",
                "source": source,
                "model": model,
                "size": size,
                "requested_size": size,
                "quality": quality,
                "format": image_format,
                "requested_format": image_format,
                "requested_background": requested_background,
                "requested_n": requested_n,
                "actual_n": len(data_for_count),
                "count_mismatch": len(data_for_count) != requested_n,
                "result_index": index,
                "prompt": prompt,
                "prompt_category": prompt_category,
                "prompt_strategy_metadata": dict(prompt_strategy_metadata or {}),
                "purpose": purpose,
                "source_url": self._sanitize_source_url(str(item.get("url") or "")),
                "local_path": local_path,
                "revised_prompt": item.get("revised_prompt") or "",
                "created": created,
                "generated_at": now_iso(),
                **({"save_error": save_error} if save_error else {}),
            }
            record.update(
                self._inspect_saved_image(
                    local_path,
                    requested_size=size,
                    requested_format=image_format,
                    requested_background=requested_background,
                )
            )
            assets.append(record)
            persisted.append(record)
            item["b64_json_present"] = bool(item.get("b64_json"))
            item.pop("b64_json", None)
            item["local_path"] = local_path
            item["asset_id"] = asset_id
            for key in (
                "actual_width",
                "actual_height",
                "actual_format",
                "actual_mode",
                "has_alpha",
                "transparent_pixel_ratio",
                "semi_transparent_pixel_ratio",
                "transparency_status",
                "validation_warnings",
            ):
                if key in record:
                    item[key] = record[key]
            if save_error:
                item["save_error"] = save_error
        manifest["assets"] = assets[-500:]
        manifest["updated_at"] = now_iso()
        write_json(manifest_path, manifest)
        return {**result, **count_metadata, "asset_manifest_path": str(manifest_path), "persisted_assets": persisted}

    def _save_b64(self, asset_root: Path, asset_id: str, payload: str) -> tuple[str, str]:
        try:
            path = asset_root / f"{asset_id}.png"
            path.write_bytes(base64.b64decode(payload, validate=False))
            return str(path), ""
        except Exception as exc:  # noqa: BLE001
            return "", f"failed to save b64 image: {exc}"

    def _download_url(self, asset_root: Path, asset_id: str, url: str) -> tuple[str, str]:
        try:
            parsed = urllib.parse.urlparse(url)
            ext = Path(parsed.path).suffix.lower()
            if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
                ext = ".png"
            request = urllib.request.Request(url, headers={"User-Agent": "AstraBridge/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                content_type = str(response.headers.get("Content-Type") or "")
                if "webp" in content_type:
                    ext = ".webp"
                elif "jpeg" in content_type or "jpg" in content_type:
                    ext = ".jpg"
                elif "png" in content_type:
                    ext = ".png"
                body = response.read()
            path = asset_root / f"{asset_id}{ext}"
            path.write_bytes(body)
            return str(path), ""
        except Exception as exc:  # noqa: BLE001
            return "", f"failed to download generated image: {exc}"

    def _inspect_saved_image(
        self,
        local_path: str,
        *,
        requested_size: str,
        requested_format: str,
        requested_background: str,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        info: dict[str, Any] = {
            "actual_width": None,
            "actual_height": None,
            "actual_format": "",
            "actual_mode": "",
            "has_alpha": False,
            "transparent_pixel_ratio": None,
            "semi_transparent_pixel_ratio": None,
            "size_matches_request": None,
            "format_matches_request": None,
            "transparency_status": "not_requested",
            "validation_warnings": warnings,
        }
        if not local_path:
            warnings.append("local_path_missing")
            return info
        path = Path(local_path)
        if not path.is_file():
            warnings.append("local_file_missing")
            return info
        image_info = self._probe_image_file(path)
        info.update(image_info)
        expected_size = self._parse_exact_size(requested_size)
        if expected_size and info.get("actual_width") and info.get("actual_height"):
            info["size_matches_request"] = (info["actual_width"], info["actual_height"]) == expected_size
            if not info["size_matches_request"]:
                warnings.append("size_mismatch")
        normalized_requested_format = self._normalize_format(requested_format)
        actual_format = self._normalize_format(str(info.get("actual_format") or path.suffix.lstrip(".")))
        if normalized_requested_format:
            info["format_matches_request"] = actual_format == normalized_requested_format
            if not info["format_matches_request"]:
                warnings.append("format_mismatch")
        if requested_background == "transparent":
            if not info.get("has_alpha"):
                info["transparency_status"] = "failed_no_alpha"
                warnings.append("transparent_contract_failed")
                warnings.append("alpha_channel_missing")
            elif info.get("transparent_pixel_ratio") is not None and float(info.get("transparent_pixel_ratio") or 0) < TRANSPARENT_ALPHA_MIN_RATIO:
                info["transparency_status"] = "failed_low_alpha"
                warnings.append("transparent_contract_failed")
                warnings.append("alpha_ratio_too_low")
            else:
                info["transparency_status"] = "passed"
        return info

    def _probe_image_file(self, path: Path) -> dict[str, Any]:
        try:
            from PIL import Image  # type: ignore

            with Image.open(path) as image:
                width, height = image.size
                actual_format = str(image.format or path.suffix.lstrip(".")).lower()
                mode = image.mode
                has_alpha = "A" in image.getbands() or "transparency" in image.info
                transparent_ratio: float | None = None
                semi_transparent_ratio: float | None = None
                if has_alpha:
                    alpha = image.getchannel("A") if "A" in image.getbands() else image.convert("RGBA").getchannel("A")
                    histogram = alpha.histogram()
                    total = max(width * height, 1)
                    transparent_ratio = histogram[0] / total
                    semi_transparent_ratio = sum(histogram[1:255]) / total
                return {
                    "actual_width": width,
                    "actual_height": height,
                    "actual_format": self._normalize_format(actual_format),
                    "actual_mode": mode,
                    "has_alpha": has_alpha,
                    "transparent_pixel_ratio": transparent_ratio,
                    "semi_transparent_pixel_ratio": semi_transparent_ratio,
                }
        except Exception:
            return self._probe_png_header(path)

    def _probe_png_header(self, path: Path) -> dict[str, Any]:
        try:
            data = path.read_bytes()[:33]
            if not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
                return {"actual_format": self._normalize_format(path.suffix.lstrip("."))}
            width = int.from_bytes(data[16:20], "big")
            height = int.from_bytes(data[20:24], "big")
            color_type = data[25]
            has_alpha = color_type in {4, 6}
            return {
                "actual_width": width,
                "actual_height": height,
                "actual_format": "png",
                "actual_mode": f"png_color_type_{color_type}",
                "has_alpha": has_alpha,
            }
        except Exception:
            return {"actual_format": self._normalize_format(path.suffix.lstrip("."))}

    def _parse_exact_size(self, size: str) -> tuple[int, int] | None:
        match = re.fullmatch(r"(\d+)x(\d+)", str(size or "").strip().lower())
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    def _normalize_format(self, value: str) -> str:
        normalized = str(value or "").strip().lower().lstrip(".")
        if normalized == "jpg":
            return "jpeg"
        return normalized

    def _sanitize_source_url(self, url: str) -> str:
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url[:240]
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

