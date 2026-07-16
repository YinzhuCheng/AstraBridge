from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..common import normalize_path_for_host
from ..profile_service import ProfileService
from .capability_routes import resolve_capability_route_entry
from .capability_registry import default_capability_registry
from .dashscope_image_generate_adapter import DashScopeImageGenerateAdapter
from .image_generate_adapter import YunwuImageGenerateAdapter
from .speech_synthesize_adapter import QwenSpeechSynthesizeAdapter
from .speech_transcribe_adapter import QwenSpeechTranscribeAdapter
from .vision_analyze_adapter import KimiVisionAnalyzeAdapter, QwenVisionAnalyzeAdapter

if TYPE_CHECKING:
    from ..router_config_service import RouterConfigService


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


class CapabilityRuntime:
    def __init__(
        self,
        *,
        router_config: "RouterConfigService" | None = None,
        key_injector: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        if router_config is None:
            from ..router_config_service import RouterConfigService

            router_config = RouterConfigService(ProfileService())
        self._router_config = router_config
        self._key_injector = key_injector
        self._registry = default_capability_registry()
        self._image_yunwu = YunwuImageGenerateAdapter()
        self._image_qwen = DashScopeImageGenerateAdapter()
        self._speech_transcribe = QwenSpeechTranscribeAdapter()
        self._speech_synthesize = QwenSpeechSynthesizeAdapter()
        self._vision_qwen = QwenVisionAnalyzeAdapter()
        self._vision_kimi = KimiVisionAnalyzeAdapter()

    def route_snapshot(self, capability_id: str | None = None) -> dict[str, Any]:
        snapshot = self._router_config.capability_route_snapshot()
        if capability_id:
            wanted = _clean_text(capability_id)
            snapshot["routes"] = [item for item in list(snapshot.get("routes") or []) if str(item.get("capability_id") or "") == wanted]
        return snapshot

    def invoke(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        route = self._resolve_route(capability_id, payload)
        candidate = dict(route.get("resolved_candidate") or {})
        normalized = dict(payload)
        normalized.setdefault("workspace_root", _workspace_root())
        if candidate.get("provider_id") and not normalized.get("provider_id"):
            normalized["provider_id"] = candidate["provider_id"]
        if candidate.get("model") and not normalized.get("model"):
            normalized["model"] = candidate["model"]
        if self._key_injector and candidate.get("provider_id"):
            self._key_injector(candidate)
        result = self._dispatch(capability_id, normalized, candidate)
        if isinstance(result, dict):
            result["route"] = {
                "capability_id": capability_id,
                "route_mode": route.get("route_mode"),
                "resolved_candidate": candidate,
            }
        return result

    def _resolve_route(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        capability = _clean_text(capability_id)
        models = self._router_config.models()
        provider_override = _clean_text(payload.get("provider_id"))
        model_override = _clean_text(payload.get("model"))
        if provider_override:
            candidates = self._registry.resolve_candidates(capability, models)
            for candidate in candidates:
                if _clean_text(candidate.get("provider_id")) != provider_override:
                    continue
                if model_override and _clean_text(candidate.get("model")) != model_override:
                    continue
                return {
                    "capability_id": capability,
                    "route_mode": "explicit",
                    "resolved_candidate": candidate,
                    "candidates": candidates,
                }
            target = f"{provider_override}/{model_override}" if model_override else provider_override
            raise RuntimeError(
                f"no_capability_candidate: capability `{capability}` explicit route `{target}` has no eligible candidate."
            )
        route_record = self._router_config.capability_routes().get(capability)
        route = resolve_capability_route_entry(capability, models, route_record=route_record, registry=self._registry)
        if route.get("resolved_candidate") is None:
            raise RuntimeError(str(route.get("error") or f"no_capability_candidate: capability `{capability}` has no eligible candidate."))
        return route

    def _dispatch(self, capability_id: str, payload: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        capability = _clean_text(capability_id)
        if capability == "image.generate":
            operation = _clean_text(payload.get("operation") or "generate").lower() or "generate"
            provider_id = _clean_text(candidate.get("provider_id") or payload.get("provider_id"))
            if provider_id == "qwen":
                return self._image_qwen.generate(payload)
            if operation == "edit":
                return self._image_yunwu.edit_as_generation(payload)
            if operation == "transparent_asset":
                return self._image_yunwu.transparent_asset(payload)
            return self._image_yunwu.generate(payload)
        if capability == "speech.transcribe":
            return self._speech_transcribe.transcribe(_payload_with_audio_inputs(payload))
        if capability == "speech.synthesize":
            return self._speech_synthesize.synthesize(payload)
        if capability == "vision.analyze":
            provider_id = _clean_text(candidate.get("provider_id") or payload.get("provider_id"))
            adapter = self._vision_kimi if provider_id == "kimi" else self._vision_qwen
            return adapter.analyze(_payload_with_image_inputs(payload))
        raise ValueError(f"Unsupported capability runtime invocation: {capability}")


def _workspace_root() -> str | None:
    if os.name == "nt":
        workspace_root = _first_host_path_env("ASTRABRIDGE_WORKSPACE_ROOT", "ASTRABRIDGE_WORKSPACE_ROOT_WSL")
    else:
        workspace_root = _first_host_path_env("ASTRABRIDGE_WORKSPACE_ROOT_WSL", "ASTRABRIDGE_WORKSPACE_ROOT")
    if workspace_root:
        return workspace_root
    return normalize_path_for_host(os.getcwd(), host_os_name=os.name)


def _first_host_path_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return normalize_path_for_host(value, host_os_name=os.name)
    return None


def _payload_with_audio_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("audio_inputs"):
        return normalized
    audio_paths = [str(item) for item in (normalized.get("audio_paths") or []) if str(item or "").strip()]
    if audio_paths:
        normalized["audio_inputs"] = [{"path": normalize_path_for_host(item, host_os_name=os.name)} for item in audio_paths]
    return normalized


def _payload_with_image_inputs(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("image_inputs"):
        return normalized
    image_inputs: list[dict[str, Any]] = []
    for item in normalized.get("image_paths") or []:
        text = str(item or "").strip()
        if text:
            image_inputs.append({"path": normalize_path_for_host(text, host_os_name=os.name)})
    for item in normalized.get("image_urls") or []:
        text = str(item or "").strip()
        if text:
            image_inputs.append({"url": text})
    normalized["image_inputs"] = image_inputs
    return normalized
