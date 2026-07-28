"""Versioned, secret-free execution-route admission contracts.

Provider profiles describe long-lived provider defaults.  They are not proof
that every model at every endpoint may execute as a coding agent.  This module
is the deliberately narrow boundary between those defaults and an admitted
runtime route.  It is intentionally side-effect free: later runtime ownership
work may consume its result, but constructing a route never opens a network
connection or changes a user configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .registry import resolve_provider_id
from .tooling.model_authority import assess_model_authority
from .transports import transport_class_for_profile
from .transports.base import transport_signature_for_class


EXECUTION_ROUTE_SCHEMA_VERSION = "astrabridge-execution-route-v1"
EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION = "astrabridge-execution-route-evidence-v1"
EXECUTION_ROUTE_PROMOTION_STATES = (
    "documented",
    "adapter_dry_run_passed",
    "provider_smoke_passed",
    "tool_contract_passed",
    "coding_route_verified",
    "default_route_eligible",
)
EXECUTION_ROUTE_DRIVERS = ("app_server", "native_kernel", "preview_review")

_AUTHORITY_RANK = {"D": 0, "C": 1, "B": 2, "A": 3}
_PROMOTION_AUTHORITY_CEILING = {
    "documented": "C",
    "adapter_dry_run_passed": "C",
    "provider_smoke_passed": "C",
    "tool_contract_passed": "B",
    "coding_route_verified": "A",
    "default_route_eligible": "A",
}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:+-]{0,255}$")
_SECRET_REFERENCE_RE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|authorization|bearer|password|secret)\s*[=:]"
)
_PATH_SECRET_RE = re.compile(r"(?i)(?:^|[/=:])(?:sk|key|token)_[A-Za-z0-9_-]{8,}")
_TOKEN_VALUE_RE = re.compile(r"(?i)\b(?:sk|rk|pk)-[A-Za-z0-9_-]{12,}\b")


def resolve_execution_route(
    model: dict[str, Any],
    *,
    provider: dict[str, Any],
    evidence: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve a model-specific route without trusting provider-wide claims.

    Evidence is accepted only when it explicitly binds this exact provider,
    model, endpoint fingerprint, and adapter signature.  Missing, stale, or
    malformed evidence de-promotes the route to a review-only route instead of
    failing open to the provider profile's execution backend.
    """

    subject = _build_subject(model, provider=provider)
    endpoint, endpoint_reason = _route_endpoint(provider, provider_id=subject["provider_id"])
    adapter = _build_adapter(model, provider=provider, subject=subject)
    configured_driver, driver_source = _configured_driver(model, provider=provider)
    declared_authority = _declared_authority(model)
    normalized_evidence = normalize_execution_route_evidence(
        evidence,
        subject={
            **subject,
            "endpoint_fingerprint": endpoint.get("fingerprint"),
            "adapter_signature": adapter["signature"],
        },
        now=now,
    )
    if endpoint_reason:
        normalized_evidence = {
            **normalized_evidence,
            "effective_state": "documented",
            "verification_status": "invalid",
            "reasons": _unique([*list(normalized_evidence.get("reasons") or []), endpoint_reason]),
        }

    evidence_state = str(normalized_evidence["effective_state"])
    evidence_ceiling = _PROMOTION_AUTHORITY_CEILING[evidence_state]
    effective_authority = _lower_authority(declared_authority, evidence_ceiling)
    admission, execution_driver = _admission_for(
        evidence_state=evidence_state,
        effective_authority=effective_authority,
        configured_driver=configured_driver,
    )
    route_id_seed = "|".join(
        (
            subject["provider_id"],
            subject["model_id"],
            str(endpoint.get("fingerprint") or "unresolved"),
            adapter["signature"],
        )
    )

    return {
        "schema_version": EXECUTION_ROUTE_SCHEMA_VERSION,
        "route_id": f"route:{hashlib.sha256(route_id_seed.encode('utf-8')).hexdigest()[:20]}",
        "subject": subject,
        "endpoint": endpoint,
        "adapter": adapter,
        "driver": {
            "configured_id": configured_driver,
            "configured_source": driver_source,
            "execution_id": execution_driver,
            "admission": admission,
            "requires_evidence_state": "coding_route_verified",
        },
        "authority": {
            "declared_tier": declared_authority,
            "evidence_ceiling": evidence_ceiling,
            "effective_tier": effective_authority,
        },
        "tool_mode": {
            "declared": _declared_tool_mode(model, declared_authority=declared_authority),
            "effective": _tool_mode_for_authority(effective_authority),
        },
        "context_policy": {
            "projection": "neutral_summary_only",
            "advertised_context_window": _positive_int(
                model.get("advertised_context_window")
                or model.get("context_window")
                or provider.get("advertised_context_window")
                or provider.get("max_context_tokens")
            ),
            "cross_provider_private_state_replay": "forbidden",
        },
        "reasoning_policy": {
            "mode": _safe_label(model.get("reasoning_policy_mode") or provider.get("reasoning_policy_mode") or "none"),
            "cross_provider_replay": "forbidden",
            "same_route_replay": "requires_current_evidence",
        },
        "fallback": {
            "target_models": _fallback_models(model, provider=provider, current_model=subject["model_id"]),
            "admission": "each_target_requires_its_own_execution_route",
        },
        "evidence": normalized_evidence,
        "default_route_eligible": admission == "default_eligible",
    }


def normalize_endpoint_identity(value: Any, *, provider_id: str) -> dict[str, str]:
    """Return a credential-free endpoint identity or reject unsafe input.

    Query strings, fragments, user-info, and obvious secret-bearing paths are
    deliberately excluded.  Callers must never persist a rejected raw value.
    """

    raw = str(value or "").strip()
    if not raw:
        raise ValueError("endpoint base URL is required")
    if _contains_secret_reference(raw):
        raise ValueError("endpoint base URL must not contain secret material")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("endpoint base URL must use http(s) with a hostname")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("endpoint base URL must not contain user-info, query, or fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("endpoint base URL has an invalid port") from exc
    host = parsed.hostname.lower()
    if port and not ((parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80)):
        host = f"{host}:{port}"
    path = parsed.path.rstrip("/")
    canonical = urlunsplit((parsed.scheme.lower(), host, path, "", ""))
    fingerprint = _sha256(canonical)
    return {
        "provider_id": _safe_identifier(provider_id, field="provider_id"),
        "base_url": canonical,
        "fingerprint": fingerprint,
        "identity_status": "resolved",
    }


def normalize_execution_route_evidence(
    evidence: dict[str, Any] | None,
    *,
    subject: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate and reduce evidence to a safe, model-bound lifecycle record."""

    expected = {
        "provider_id": _safe_identifier(subject.get("provider_id"), field="provider_id"),
        "model_id": _safe_identifier(subject.get("model_id"), field="model_id"),
        "native_model": _safe_identifier(subject.get("native_model"), field="native_model"),
        "endpoint_fingerprint": _safe_fingerprint(subject.get("endpoint_fingerprint")),
        "adapter_signature": _safe_fingerprint(subject.get("adapter_signature")),
    }
    if not evidence:
        return _documented_evidence(reason="evidence_missing")
    if not isinstance(evidence, dict):
        return _documented_evidence(reason="evidence_not_an_object")

    presented_state = str(evidence.get("state") or evidence.get("promotion_state") or "").strip()
    if presented_state not in EXECUTION_ROUTE_PROMOTION_STATES:
        return _documented_evidence(reason="unknown_promotion_state")
    if presented_state == "documented":
        return {
            **_documented_evidence(reason="documentation_only"),
            "presented_state": "documented",
        }
    if str(evidence.get("schema_version") or "").strip() != EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION:
        return _documented_evidence(reason="unexpected_evidence_schema", presented_state=presented_state)

    reasons: list[str] = []
    raw_subject = evidence.get("subject")
    evidence_subject = dict(raw_subject) if isinstance(raw_subject, dict) else {}
    presented_subject: dict[str, str] = {}
    for key, expected_value in expected.items():
        try:
            presented_value = (
                _safe_fingerprint(evidence_subject.get(key))
                if key.endswith("fingerprint") or key == "adapter_signature"
                else _safe_identifier(evidence_subject.get(key), field=key, required=False)
            )
        except ValueError:
            presented_value = ""
        if presented_value:
            presented_subject[key] = presented_value
        if not expected_value or presented_value != expected_value:
            reasons.append(f"subject_{key}_mismatch")

    provenance = _normalize_provenance(evidence.get("source_provenance"))
    if provenance is None:
        reasons.append("source_provenance_missing_or_unsafe")
    evidence_refs, refs_valid = _normalize_evidence_refs(evidence.get("evidence_refs"))
    if not refs_valid:
        reasons.append("evidence_references_missing_or_unsafe")
    validation_scope = _normalize_validation_scope(evidence.get("validation_scope"))
    if not validation_scope:
        reasons.append("validation_scope_missing")

    verified_at = _parse_datetime(evidence.get("verified_at"))
    expires_at = _parse_datetime(evidence.get("expires_at"))
    if verified_at is None:
        reasons.append("verified_at_missing_or_invalid")
    if expires_at is None:
        reasons.append("expires_at_missing_or_invalid")
    if verified_at and expires_at and expires_at <= verified_at:
        reasons.append("expiry_not_after_verification")
    normalized_now = _parse_datetime(now) if now is not None else datetime.now(timezone.utc)
    normalized_now = normalized_now or datetime.now(timezone.utc)
    if expires_at and normalized_now > expires_at:
        reasons.append("evidence_expired")

    safe_record = {
        "schema_version": EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
        "state": presented_state,
        "presented_state": presented_state,
        "effective_state": presented_state if not reasons else "documented",
        "verification_status": "current" if not reasons else ("expired" if "evidence_expired" in reasons else "invalid"),
        # Keep the proof's original binding separate from the current route's
        # expected binding. Replacing a stale proof subject with `expected`
        # would let endpoint or adapter drift silently self-heal on reload.
        "subject": presented_subject,
        "expected_subject": expected,
        "source_provenance": provenance,
        "evidence_refs": evidence_refs,
        "validation_scope": validation_scope,
        "verified_at": verified_at.isoformat() if verified_at else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "reasons": _unique(reasons),
    }
    return safe_record


def execution_route_evidence_for_storage(evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a re-usable, secret-free proof payload or ``None``.

    The resolver's observation fields (effective state, current expected
    subject, and reasons) are intentionally not persisted. The original,
    safely normalized evidence subject is retained so future endpoint/adapter
    drift remains observable instead of becoming a new proof by accident.
    """

    if not isinstance(evidence, dict):
        return None
    state = str(evidence.get("state") or evidence.get("presented_state") or "").strip()
    if state not in EXECUTION_ROUTE_PROMOTION_STATES or state == "documented":
        return None
    subject = evidence.get("subject")
    provenance = evidence.get("source_provenance")
    refs = evidence.get("evidence_refs")
    scope = evidence.get("validation_scope")
    verified_at = evidence.get("verified_at")
    expires_at = evidence.get("expires_at")
    if (
        not isinstance(subject, dict)
        or not isinstance(provenance, dict)
        or not isinstance(refs, list)
        or not isinstance(scope, list)
        or not all(str(subject.get(key) or "").strip() for key in ("provider_id", "model_id", "native_model", "endpoint_fingerprint", "adapter_signature"))
        or not all(str(provenance.get(key) or "").strip() for key in ("kind", "issuer", "record_id"))
        or not refs
        or not scope
        or not _parse_datetime(verified_at)
        or not _parse_datetime(expires_at)
    ):
        return None
    return {
        "schema_version": EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
        "state": state,
        "subject": {key: str(subject.get(key) or "") for key in ("provider_id", "model_id", "native_model", "endpoint_fingerprint", "adapter_signature")},
        "source_provenance": {key: str(provenance.get(key) or "") for key in ("kind", "issuer", "record_id")},
        "evidence_refs": [str(item) for item in refs],
        "validation_scope": [str(item) for item in scope],
        "verified_at": _parse_datetime(verified_at).isoformat(),
        "expires_at": _parse_datetime(expires_at).isoformat(),
    }


def _build_subject(model: dict[str, Any], *, provider: dict[str, Any]) -> dict[str, str]:
    provider_id = _provider_id(model, provider=provider)
    native_model = str(model.get("native_model") or model.get("model") or "").strip()
    model_id = str(model.get("id") or "").strip()
    if not native_model and "/" in model_id:
        native_model = model_id.split("/", 1)[1]
    if not native_model:
        native_model = str(provider.get("default_model") or "").strip()
    if not model_id:
        model_id = f"{provider_id}/{native_model}" if native_model else provider_id
    return {
        "provider_id": _safe_identifier(provider_id, field="provider_id"),
        "model_id": _safe_identifier(model_id, field="model_id"),
        "native_model": _safe_identifier(native_model, field="native_model"),
    }


def _route_endpoint(provider: dict[str, Any], *, provider_id: str) -> tuple[dict[str, str | None], str | None]:
    try:
        return normalize_endpoint_identity(provider.get("base_url"), provider_id=provider_id), None
    except ValueError:
        return {
            "provider_id": provider_id,
            "base_url": None,
            "fingerprint": None,
            "identity_status": "unresolved",
        }, "endpoint_identity_unresolved"


def _build_adapter(model: dict[str, Any], *, provider: dict[str, Any], subject: dict[str, str]) -> dict[str, str]:
    provider_family = _provider_family(model, provider=provider, provider_id=subject["provider_id"])
    profile = {
        "provider_id": subject["provider_id"],
        "provider_family": provider_family,
        "adapter_profile": model.get("adapter_profile") or provider.get("adapter_profile") or "default",
        "wire_api": provider.get("adapter_type") or provider.get("wire_api") or "responses",
        "base_url": provider.get("base_url"),
        "model": subject["native_model"],
    }
    transport_class = transport_class_for_profile(profile, provider_family=provider_family)
    transport = transport_class(None, profile)
    return {
        "id": _safe_label(transport.describe()),
        "signature": _safe_fingerprint(transport_signature_for_class(transport_class)),
        "wire_api": _safe_label(profile["wire_api"]),
    }


def _provider_id(model: dict[str, Any], *, provider: dict[str, Any]) -> str:
    raw = str(model.get("provider") or provider.get("id") or provider.get("provider_id") or "").strip()
    try:
        return resolve_provider_id(raw)
    except ValueError:
        return raw


def _provider_family(model: dict[str, Any], *, provider: dict[str, Any], provider_id: str) -> str:
    for candidate in (
        provider.get("provider_family"),
        model.get("provider_family"),
        model.get("adapter_profile"),
        provider.get("adapter_profile"),
        provider_id,
    ):
        try:
            return resolve_provider_id(str(candidate or "").strip())
        except ValueError:
            continue
    return provider_id


def _configured_driver(model: dict[str, Any], *, provider: dict[str, Any]) -> tuple[str, str]:
    for field, source in (
        ("execution_driver", "model"),
        ("runtime_backend", "model"),
        ("execution_backend", "model"),
    ):
        candidate = str(model.get(field) or "").strip()
        if candidate in EXECUTION_ROUTE_DRIVERS and candidate != "preview_review":
            return candidate, source
    for field in ("runtime_backend", "execution_backend"):
        candidate = str(provider.get(field) or "").strip()
        if candidate in EXECUTION_ROUTE_DRIVERS and candidate != "preview_review":
            return candidate, "provider_default"
    return "app_server", "safe_default"


def _declared_authority(model: dict[str, Any]) -> str:
    explicit = str(model.get("authority_tier") or "").strip().upper()
    if explicit in _AUTHORITY_RANK:
        return explicit
    return assess_model_authority(model).tier


def _declared_tool_mode(model: dict[str, Any], *, declared_authority: str) -> str:
    explicit = _safe_label(model.get("tool_mode"))
    if explicit:
        return explicit
    if declared_authority == "A":
        return "guarded_actions"
    if declared_authority == "B":
        return "propose_only"
    return "review_only"


def _admission_for(*, evidence_state: str, effective_authority: str, configured_driver: str) -> tuple[str, str]:
    if evidence_state == "default_route_eligible" and effective_authority == "A":
        return "default_eligible", configured_driver
    if evidence_state == "coding_route_verified" and effective_authority == "A":
        return "verified_non_default", configured_driver
    if evidence_state == "tool_contract_passed" and effective_authority in {"A", "B"}:
        return "tool_contract_only", "preview_review"
    return "review_only", "preview_review"


def _tool_mode_for_authority(authority: str) -> str:
    if authority == "A":
        return "guarded_actions"
    if authority == "B":
        return "propose_only"
    return "review_only"


def _fallback_models(model: dict[str, Any], *, provider: dict[str, Any], current_model: str) -> list[str]:
    raw = model.get("fallback_models") or provider.get("fallback_models") or []
    values = raw if isinstance(raw, (list, tuple)) else [raw]
    targets: list[str] = []
    for value in values:
        candidate = str(value or "").strip()
        if not candidate:
            continue
        if "/" not in candidate:
            provider_id = str(current_model).split("/", 1)[0]
            candidate = f"{provider_id}/{candidate}"
        try:
            normalized = _safe_identifier(candidate, field="fallback_model")
        except ValueError:
            continue
        if normalized != current_model and normalized not in targets:
            targets.append(normalized)
    return targets


def _normalize_provenance(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    kind = _safe_label(value.get("kind") or value.get("source_kind"))
    issuer = _safe_label(value.get("issuer") or value.get("recorded_by"))
    record_id = _safe_label(value.get("record_id") or value.get("run_id") or value.get("id"))
    if not kind or not issuer or not record_id:
        return None
    return {"kind": kind, "issuer": issuer, "record_id": record_id}


def _normalize_evidence_refs(value: Any) -> tuple[list[str], bool]:
    values = value if isinstance(value, (list, tuple)) else []
    refs: list[str] = []
    valid = True
    for item in values:
        if not isinstance(item, str):
            valid = False
            continue
        candidate = item.strip()
        if (
            not candidate
            or len(candidate) > 512
            or "?" in candidate
            or "#" in candidate
            or _contains_secret_reference(candidate)
        ):
            valid = False
            continue
        if candidate not in refs:
            refs.append(candidate)
    return refs, bool(refs) and valid


def _normalize_validation_scope(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else []
    scopes: list[str] = []
    for item in values:
        label = _safe_label(item)
        if label and label not in scopes:
            scopes.append(label)
    return scopes


def _documented_evidence(*, reason: str, presented_state: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
        "state": "documented",
        "presented_state": presented_state or "documented",
        "effective_state": "documented",
        "verification_status": "missing" if reason == "evidence_missing" else "invalid",
        "subject": {},
        "expected_subject": {},
        "source_provenance": None,
        "evidence_refs": [],
        "validation_scope": [],
        "verified_at": None,
        "expires_at": None,
        "reasons": [reason],
    }


def _lower_authority(left: str, right: str) -> str:
    return left if _AUTHORITY_RANK[left] <= _AUTHORITY_RANK[right] else right


def _safe_identifier(value: Any, *, field: str, required: bool = True) -> str:
    normalized = str(value or "").strip()
    if not normalized and not required:
        return ""
    if not normalized or not _IDENTIFIER_RE.fullmatch(normalized) or _contains_secret_reference(normalized):
        raise ValueError(f"{field} must be a non-secret identifier")
    return normalized


def _safe_fingerprint(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized or not re.fullmatch(r"(?:sha256:)?[A-Fa-f0-9]{16,128}", normalized):
        return ""
    return normalized.lower()


def _safe_label(value: Any) -> str:
    normalized = str(value or "").strip()
    if (
        not normalized
        or len(normalized) > 128
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@/-]*", normalized)
        or _contains_secret_reference(normalized)
    ):
        return ""
    return normalized


def _positive_int(value: Any) -> int | None:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _parse_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _contains_secret_reference(value: str) -> bool:
    return bool(_SECRET_REFERENCE_RE.search(value) or _PATH_SECRET_RE.search(value) or _TOKEN_VALUE_RE.search(value))


def _sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


__all__ = [
    "EXECUTION_ROUTE_DRIVERS",
    "EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION",
    "EXECUTION_ROUTE_PROMOTION_STATES",
    "EXECUTION_ROUTE_SCHEMA_VERSION",
    "execution_route_evidence_for_storage",
    "normalize_endpoint_identity",
    "normalize_execution_route_evidence",
    "resolve_execution_route",
]
