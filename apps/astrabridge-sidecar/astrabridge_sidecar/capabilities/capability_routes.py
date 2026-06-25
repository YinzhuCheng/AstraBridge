from __future__ import annotations

from typing import Any

from ..common import now_iso
from .capability_registry import CapabilityRegistry, default_capability_registry


CAPABILITY_ROUTE_MODE_AUTO = "auto"
CAPABILITY_ROUTE_MODE_PINNED = "pinned"
CAPABILITY_ROUTE_MODES = {CAPABILITY_ROUTE_MODE_AUTO, CAPABILITY_ROUTE_MODE_PINNED}


def normalize_capability_route_record(
    capability_id: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    record = dict(payload or {})
    mode = str(record.get("mode") or CAPABILITY_ROUTE_MODE_AUTO).strip().lower()
    if mode not in CAPABILITY_ROUTE_MODES:
        mode = CAPABILITY_ROUTE_MODE_AUTO
    provider_id = str(record.get("provider_id") or "").strip() or None
    model = str(record.get("model") or "").strip() or None
    if mode != CAPABILITY_ROUTE_MODE_PINNED:
        provider_id = None
        model = None
    elif provider_id is None and model is not None:
        mode = CAPABILITY_ROUTE_MODE_AUTO
        model = None
    return {
        "capability_id": str(capability_id or "").strip(),
        "mode": mode,
        "provider_id": provider_id,
        "model": model,
        "updated_at": str(record.get("updated_at") or now_iso()),
    }


def resolve_capability_route_entry(
    capability_id: str,
    configured_models: list[dict[str, Any]] | None = None,
    *,
    route_record: dict[str, Any] | None = None,
    registry: CapabilityRegistry | None = None,
    include_deprecated: bool = False,
) -> dict[str, Any]:
    capability_registry = registry or default_capability_registry()
    spec = capability_registry.capability_spec(capability_id)
    normalized_route = normalize_capability_route_record(spec.capability_id, route_record)
    candidates = capability_registry.resolve_candidates(
        spec.capability_id,
        configured_models,
        include_deprecated=include_deprecated,
    )
    resolved_candidate = _resolve_candidate(candidates, normalized_route)
    resolution_status = "ok" if resolved_candidate else "no_capability_candidate"
    if spec.lane_type == "web_standalone" and resolved_candidate:
        resolution_status = "standalone"
    error = None if resolved_candidate else _route_error(spec.capability_id, normalized_route)
    return {
        "capability_id": spec.capability_id,
        "display_name": spec.display_name,
        "lane_type": spec.lane_type,
        "transport_mode": spec.transport_mode,
        "route_mode": normalized_route["mode"],
        "route_record": normalized_route,
        "resolution_status": resolution_status,
        "resolved_candidate": resolved_candidate,
        "candidates": candidates,
        "error": error,
        "updated_at": normalized_route["updated_at"],
    }


def provider_capability_summary(
    provider_id: str,
    route_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    provider_key = str(provider_id or "").strip()
    if not provider_key:
        return summary
    for entry in route_entries:
        capability_id = str(entry.get("capability_id") or "").strip()
        candidates = [
            dict(candidate)
            for candidate in list(entry.get("candidates") or [])
            if str((candidate or {}).get("provider_id") or "").strip() == provider_key
        ]
        if not capability_id or not candidates:
            continue
        modalities: list[str] = []
        models: list[str] = []
        for candidate in candidates:
            model = str(candidate.get("model") or "").strip()
            if model and model not in models:
                models.append(model)
            for modality in list(candidate.get("input_modalities") or []):
                text = str(modality or "").strip()
                if text and text not in modalities:
                    modalities.append(text)
        summary[capability_id] = {
            "available": True,
            "candidate_models": models,
            "input_modalities": modalities,
        }
    return summary


def _resolve_candidate(candidates: list[dict[str, Any]], route_record: dict[str, Any]) -> dict[str, Any] | None:
    if not candidates:
        return None
    if route_record.get("mode") != CAPABILITY_ROUTE_MODE_PINNED:
        return dict(candidates[0])
    provider_id = str(route_record.get("provider_id") or "").strip()
    model = str(route_record.get("model") or "").strip()
    for candidate in candidates:
        if str(candidate.get("provider_id") or "").strip() != provider_id:
            continue
        if model and str(candidate.get("model") or "").strip() != model:
            continue
        return dict(candidate)
    return None


def _route_error(capability_id: str, route_record: dict[str, Any]) -> str:
    if route_record.get("mode") == CAPABILITY_ROUTE_MODE_PINNED:
        provider_id = str(route_record.get("provider_id") or "").strip()
        model = str(route_record.get("model") or "").strip()
        target = f"{provider_id}/{model}" if model else provider_id
        return (
            f"no_capability_candidate: capability `{capability_id}` route is pinned to `{target}`, "
            "but no eligible candidate is currently available."
        )
    return (
        f"no_capability_candidate: capability `{capability_id}` has no eligible candidate. "
        "Check capability routing, provider enablement, and effective model catalog entries."
    )
