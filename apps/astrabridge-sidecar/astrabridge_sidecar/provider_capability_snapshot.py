from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from .providers import resolve_provider_id
from .providers.transports import transport_class_for_profile
from .providers.transports.base import transport_signature_for_class


PROVIDER_CAPABILITY_SNAPSHOT_SCHEMA_VERSION = "astrabridge-provider-capability-snapshot-v1"
PROVIDER_CAPABILITY_MANIFEST_SCHEMA_VERSION = "astrabridge-provider-capability-manifest-v1"
DEFAULT_PROVIDER_CAPABILITY_STALE_AFTER_SECONDS = 7 * 24 * 60 * 60
_GRAPH_CAPABILITY_TO_PORTS = {
    "vision.analyze": {"input": {"image"}, "output": {"image"}},
    "speech.transcribe": {"input": {"audio"}, "output": set()},
    "speech.synthesize": {"input": set(), "output": {"audio"}},
    "image.generate": {"input": set(), "output": {"image"}},
}


def current_model_provider_contract(model: dict[str, Any], *, provider: dict[str, Any]) -> dict[str, str]:
    provider_id = str(model.get("provider") or provider.get("id") or provider.get("provider_id") or "").strip()
    native_model = str(model.get("native_model") or "").strip()
    model_id = str(model.get("id") or (f"{provider_id}/{native_model}" if provider_id and native_model else "")).strip()
    provider_family = _provider_family(
        provider.get("provider_family") or model.get("provider_family") or provider_id,
        provider_family=provider.get("provider_family") or model.get("provider_family"),
        adapter_profile=model.get("adapter_profile") or provider.get("adapter_profile"),
        wire_api=provider.get("adapter_type") or provider.get("wire_api"),
        base_url=provider.get("base_url"),
        model=native_model or provider.get("default_model"),
    )
    profile = {
        "provider_id": provider_id,
        "provider_family": provider_family,
        "adapter_profile": model.get("adapter_profile") or provider.get("adapter_profile") or "default",
        "wire_api": provider.get("adapter_type") or provider.get("wire_api") or "responses",
        "base_url": provider.get("base_url"),
        "model": native_model,
    }
    transport_class = transport_class_for_profile(profile, provider_family=provider_family)
    transport = transport_class(None, profile)
    return {
        "provider_id": provider_id,
        "model_id": model_id,
        "native_model": native_model,
        "runtime_backend": str(provider.get("runtime_backend") or provider.get("execution_backend") or "app_server"),
        "transport_adapter": transport.describe(),
        "transport_signature": transport_signature_for_class(transport_class),
    }


def capability_snapshot_matches_current_contract(snapshot: dict[str, Any], current_contract: dict[str, Any]) -> bool:
    state = describe_capability_snapshot_manifest(
        snapshot,
        current_contract=current_contract,
    )
    return str(state.get("verification_state") or "") in {"verified", "partial", "blocked", "unknown"}


def build_verified_capability_snapshot(
    *,
    model: dict[str, Any],
    provider: dict[str, Any],
    matrix_entries: list[dict[str, Any]],
    created_at: str | None = None,
) -> dict[str, Any]:
    current_contract = current_model_provider_contract(model, provider=provider)
    capability_records: dict[str, dict[str, Any]] = {}
    graph_input_ports: set[str] = set()
    graph_output_ports: set[str] = set()
    evidence_paths: set[str] = set()
    validation_scope: set[str] = set()
    known_failures: list[str] = []
    known_pitfalls: list[str] = []
    overall_status = "unknown"
    status_rank = {"unknown": 0, "blocked": 1, "partial": 2, "verified": 3}

    for entry in matrix_entries:
        if not isinstance(entry, dict):
            continue
        lane = dict(dict(entry.get("runtime_normalized_contract") or {}).get("multimodal_lane") or {})
        validated = dict(entry.get("validated_evidence") or {})
        capability_id = str(lane.get("capability_id") or "").strip()
        if not capability_id:
            continue
        validation_status = str(validated.get("validation_status") or "unknown").strip()
        exposure_state = str(lane.get("exposure_state") or "unknown").strip()
        eligible_for_pinned_route = bool(lane.get("eligible_for_pinned_route"))
        capability_records[capability_id] = {
            "capability_id": capability_id,
            "overall_status": str(entry.get("overall_status") or "unknown").strip() or "unknown",
            "validation_status": validation_status,
            "exposure_state": exposure_state,
            "eligible_for_auto_route": bool(lane.get("eligible_for_auto_route")),
            "eligible_for_pinned_route": eligible_for_pinned_route,
            "adapter_family": str(lane.get("adapter_family") or "").strip() or None,
            "adapter_id": str(lane.get("adapter_id") or "").strip() or None,
            "route_resolution_status": str(lane.get("route_resolution_status") or "").strip() or None,
            "request_shape_validation_status": str(lane.get("request_shape_validation_status") or "").strip() or None,
            "required_modalities": [str(item).strip() for item in list(lane.get("required_modalities") or []) if str(item or "").strip()],
            "declared_modalities": [str(item).strip() for item in list(lane.get("declared_modalities") or []) if str(item or "").strip()],
            "known_failures": [str(item).strip() for item in list(validated.get("known_failures") or []) if str(item or "").strip()][:16],
            "known_pitfalls": [str(item).strip() for item in list(validated.get("known_pitfalls") or []) if str(item or "").strip()][:16],
            "evidence_paths": [str(item).strip() for item in list(validated.get("evidence_paths") or []) if str(item or "").strip()],
            "last_verified_at": validated.get("last_verified_at"),
        }
        for path in capability_records[capability_id]["evidence_paths"]:
            evidence_paths.add(path)
        for scope in list(validated.get("validation_scope") or []):
            clean_scope = str(scope or "").strip()
            if clean_scope:
                validation_scope.add(clean_scope)
        for item in capability_records[capability_id]["known_failures"]:
            if item not in known_failures:
                known_failures.append(item)
        for item in capability_records[capability_id]["known_pitfalls"]:
            if item not in known_pitfalls:
                known_pitfalls.append(item)
        current_status = capability_records[capability_id]["overall_status"]
        if status_rank.get(str(current_status), 0) > status_rank.get(overall_status, 0):
            overall_status = str(current_status)
        if eligible_for_pinned_route:
            ports = _GRAPH_CAPABILITY_TO_PORTS.get(capability_id, {})
            graph_input_ports.update(set(ports.get("input") or set()))
            graph_output_ports.update(set(ports.get("output") or set()))

    if not capability_records:
        overall_status = "unknown"
    snapshot = {
        "schema_version": PROVIDER_CAPABILITY_SNAPSHOT_SCHEMA_VERSION,
        "status": overall_status,
        "created_at": created_at,
        "verified_at": created_at,
        **current_contract,
        "capabilities": capability_records,
        "graph_capabilities": {
            "input_port_types": sorted(graph_input_ports),
            "output_port_types": sorted(graph_output_ports),
            "validation_scope": sorted(validation_scope),
            "evidence_paths": sorted(evidence_paths),
        },
        "known_failures": known_failures[:24],
        "known_pitfalls": known_pitfalls[:24],
    }
    snapshot["manifest"] = _build_snapshot_manifest(snapshot)
    return snapshot


def describe_capability_snapshot_manifest(
    snapshot: dict[str, Any],
    *,
    current_contract: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    if str(snapshot.get("schema_version") or "").strip() != PROVIDER_CAPABILITY_SNAPSHOT_SCHEMA_VERSION:
        return {
            "schema_version": PROVIDER_CAPABILITY_MANIFEST_SCHEMA_VERSION,
            "verification_state": "invalid",
            "freshness_status": "invalid",
            "digest_status": "invalid",
            "reason": "unexpected_schema_version",
        }
    status = str(snapshot.get("status") or "").strip().lower()
    if status not in {"verified", "partial", "blocked", "unknown"}:
        return {
            "schema_version": PROVIDER_CAPABILITY_MANIFEST_SCHEMA_VERSION,
            "verification_state": "invalid",
            "freshness_status": "invalid",
            "digest_status": "invalid",
            "reason": "unexpected_snapshot_status",
        }
    embedded_manifest = dict(snapshot.get("manifest") or {})
    computed_digest = _stable_json_digest(_manifest_payload_without_manifest(snapshot))
    presented_digest = str(embedded_manifest.get("digest") or "").strip()
    digest_status = "valid" if presented_digest and presented_digest == computed_digest else ("missing" if not presented_digest else "mismatch")
    freshness = _freshness_window(
        observed_at=str(snapshot.get("verified_at") or snapshot.get("created_at") or "").strip() or None,
        stale_after_seconds=embedded_manifest.get("stale_after_seconds"),
        expires_at=embedded_manifest.get("expires_at"),
        now=now,
    )
    contract_current = _snapshot_contract_matches_current_contract(snapshot, current_contract)
    if not contract_current:
        verification_state = "drifted"
    elif digest_status == "mismatch":
        verification_state = "tampered"
    elif freshness["freshness_status"] == "expired":
        verification_state = "expired"
    elif freshness["freshness_status"] == "stale":
        verification_state = "stale"
    else:
        verification_state = status
    return {
        "schema_version": PROVIDER_CAPABILITY_MANIFEST_SCHEMA_VERSION,
        "digest": presented_digest or computed_digest,
        "computed_digest": computed_digest,
        "digest_status": digest_status,
        "contract_digest": _stable_json_digest(dict(current_contract or {})),
        "source_digest": str(embedded_manifest.get("source_digest") or "").strip() or None,
        "freshness_status": freshness["freshness_status"],
        "observed_at": freshness["observed_at"],
        "stale_after_seconds": freshness["stale_after_seconds"],
        "expires_at": freshness["expires_at"],
        "verification_state": verification_state,
        "snapshot_status": status,
        "contract_current": contract_current,
    }


def graph_port_capabilities_from_snapshot(snapshot: dict[str, Any]) -> dict[str, list[str]]:
    graph_capabilities = dict(snapshot.get("graph_capabilities") or {})
    return {
        "input_port_types": [
            str(item).strip()
            for item in list(graph_capabilities.get("input_port_types") or [])
            if str(item or "").strip()
        ],
        "output_port_types": [
            str(item).strip()
            for item in list(graph_capabilities.get("output_port_types") or [])
            if str(item or "").strip()
        ],
    }


def aggregate_matrix_entries_by_model(matrix: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in list(matrix.get("entries") or []):
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("model_id") or "").strip()
        if model_id:
            grouped[model_id].append(dict(entry))
    return dict(grouped)


def _provider_family(
    seed: Any,
    *,
    provider_family: Any = None,
    adapter_profile: Any = None,
    wire_api: Any = None,
    base_url: Any = None,
    model: Any = None,
) -> str | None:
    candidates = (seed, provider_family, adapter_profile, wire_api, base_url, model)
    for candidate in candidates:
        try:
            return resolve_provider_id(str(candidate or "").strip())
        except ValueError:
            continue
    return None


def _build_snapshot_manifest(snapshot: dict[str, Any]) -> dict[str, Any]:
    freshness = _freshness_window(
        observed_at=str(snapshot.get("verified_at") or snapshot.get("created_at") or "").strip() or None,
        stale_after_seconds=DEFAULT_PROVIDER_CAPABILITY_STALE_AFTER_SECONDS,
        expires_at=None,
    )
    payload = _manifest_payload_without_manifest(snapshot)
    return {
        "schema_version": PROVIDER_CAPABILITY_MANIFEST_SCHEMA_VERSION,
        "digest": _stable_json_digest(payload),
        "source_digest": _stable_json_digest(
            {
                "capabilities": dict(snapshot.get("capabilities") or {}),
                "graph_capabilities": dict(snapshot.get("graph_capabilities") or {}),
            }
        ),
        "contract_digest": _stable_json_digest(
            {
                key: snapshot.get(key)
                for key in (
                    "provider_id",
                    "model_id",
                    "native_model",
                    "runtime_backend",
                    "transport_adapter",
                    "transport_signature",
                )
            }
        ),
        "freshness_status": freshness["freshness_status"],
        "observed_at": freshness["observed_at"],
        "stale_after_seconds": freshness["stale_after_seconds"],
        "expires_at": freshness["expires_at"],
        "verification_state": str(snapshot.get("status") or "unknown").strip().lower() or "unknown",
    }


def _manifest_payload_without_manifest(snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = dict(snapshot)
    payload.pop("manifest", None)
    return payload


def _snapshot_contract_matches_current_contract(snapshot: dict[str, Any], current_contract: dict[str, Any]) -> bool:
    required_pairs = {
        "provider_id": str(current_contract.get("provider_id") or ""),
        "model_id": str(current_contract.get("model_id") or ""),
        "native_model": str(current_contract.get("native_model") or ""),
        "runtime_backend": str(current_contract.get("runtime_backend") or ""),
        "transport_adapter": str(current_contract.get("transport_adapter") or ""),
        "transport_signature": str(current_contract.get("transport_signature") or ""),
    }
    for key, expected in required_pairs.items():
        if expected and str(snapshot.get(key) or "") != expected:
            return False
    return True


def _freshness_window(
    *,
    observed_at: str | None,
    stale_after_seconds: Any,
    expires_at: Any,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized_now = now or datetime.now(timezone.utc)
    observed_dt = _optional_datetime(observed_at)
    stale_after = int(stale_after_seconds or DEFAULT_PROVIDER_CAPABILITY_STALE_AFTER_SECONDS)
    expiry_dt = _optional_datetime(expires_at)
    if expiry_dt is None and observed_dt is not None and stale_after > 0:
        expiry_dt = observed_dt + timedelta(seconds=stale_after)
    freshness_status = "current"
    if expiry_dt is not None and normalized_now > expiry_dt:
        freshness_status = "expired"
    elif observed_dt is None:
        freshness_status = "unknown"
    return {
        "observed_at": observed_dt.isoformat() if observed_dt else None,
        "stale_after_seconds": stale_after,
        "expires_at": expiry_dt.isoformat() if expiry_dt else None,
        "freshness_status": freshness_status,
    }


def _optional_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    normalized = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stable_json_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


__all__ = [
    "PROVIDER_CAPABILITY_SNAPSHOT_SCHEMA_VERSION",
    "PROVIDER_CAPABILITY_MANIFEST_SCHEMA_VERSION",
    "aggregate_matrix_entries_by_model",
    "build_verified_capability_snapshot",
    "capability_snapshot_matches_current_contract",
    "current_model_provider_contract",
    "describe_capability_snapshot_manifest",
    "graph_port_capabilities_from_snapshot",
]
