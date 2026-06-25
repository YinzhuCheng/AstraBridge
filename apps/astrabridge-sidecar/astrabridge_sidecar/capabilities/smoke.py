from __future__ import annotations

from typing import Any

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
    status = "pass" if mode == "dry_run" else "provider_not_run"
    return {
        "schema_version": CAPABILITY_SMOKE_SCHEMA_VERSION,
        "capability_id": capability_id,
        "mode": mode,
        "status": status,
        "provider_invoked": False,
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
            "sample_input": fixture["sample_input"],
        },
        "sanitized_response": {
            "sample_output": fixture["sample_output"],
            "notes": [
                "Dry-run smoke validates the capability contract, routing state, and UI wiring without invoking a provider.",
            ],
        },
        "artifact_refs": [],
        "evidence_refs": [],
        "created_at": now_iso(),
    }
