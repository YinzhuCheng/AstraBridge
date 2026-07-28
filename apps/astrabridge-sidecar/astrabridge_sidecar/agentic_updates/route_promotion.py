"""Secret-free execution-route promotion records for supervised updates.

Documentation discovery is allowed to improve a model catalog.  It is not
allowed to turn that model into a coding-agent route.  This module keeps the
two lifecycles separate: catalog facts can be proposed independently, while a
route proof must be bound to one provider, model, endpoint fingerprint, and
adapter signature before it can advance one evidence stage at a time.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Callable

from ..common import now_iso
from ..providers.execution_route import (
    EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
    EXECUTION_ROUTE_PROMOTION_STATES,
    execution_route_evidence_for_storage,
    normalize_execution_route_evidence,
    resolve_execution_route,
)


AGENTIC_UPDATE_ROUTE_PROMOTION_SCHEMA_VERSION = "astrabridge-agentic-update-route-promotion-v1"
AGENTIC_UPDATE_ROUTE_PROMOTION_RECORD_SCHEMA_VERSION = "astrabridge-agentic-update-route-promotion-record-v1"
AGENTIC_UPDATE_ROUTE_PROMOTION_VALIDATION_SCHEMA_VERSION = "astrabridge-agentic-update-route-promotion-validation-v1"
AGENTIC_UPDATE_ROUTE_PROMOTION_APPLY_LEDGER_SCHEMA_VERSION = "astrabridge-agentic-update-route-promotion-apply-ledger-v1"
AGENTIC_UPDATE_ROUTE_PROMOTION_ROLLBACK_SCHEMA_VERSION = "astrabridge-agentic-update-route-promotion-rollback-v1"

ROUTE_PROMOTION_ACTIONS = ("document", "promote", "downgrade", "expire", "rollback")
ROUTE_PROMOTION_CHANGE_TYPES = {
    "route_promoted",
    "route_downgraded",
    "route_evidence_expired",
    "route_rollback_requested",
}
ROUTE_PROMOTION_REQUIRED_GATES: dict[str, list[str]] = {
    "adapter_dry_run_passed": ["execution_route_dry_run"],
    "provider_smoke_passed": ["execution_route_dry_run", "execution_route_provider_smoke"],
    "tool_contract_passed": [
        "execution_route_dry_run",
        "execution_route_provider_smoke",
        "execution_route_tool_contract",
    ],
    "coding_route_verified": [
        "execution_route_dry_run",
        "execution_route_provider_smoke",
        "execution_route_tool_contract",
        "execution_route_coding_smoke",
    ],
    "default_route_eligible": [
        "execution_route_dry_run",
        "execution_route_provider_smoke",
        "execution_route_tool_contract",
        "execution_route_coding_smoke",
        "execution_route_default_review",
    ],
}
ROUTE_PROMOTION_STATE_RANK = {state: index for index, state in enumerate(EXECUTION_ROUTE_PROMOTION_STATES)}
ROUTE_PROMOTION_PROVIDER_GATES = {
    "execution_route_provider_smoke",
    "execution_route_tool_contract",
    "execution_route_coding_smoke",
    "execution_route_default_review",
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:+-]{0,255}$")
_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_FINGERPRINT_RE = re.compile(r"^(?:sha256:)?[A-Fa-f0-9]{16,128}$")
_SECRET_REFERENCE_RE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|authorization|bearer|password|secret)\s*[=:]"
)
_PATH_SECRET_RE = re.compile(r"(?i)(?:^|[/=:])(?:sk|key|token)_[A-Za-z0-9_-]{8,}")
_TOKEN_VALUE_RE = re.compile(r"(?i)\b(?:sk|rk|pk)-[A-Za-z0-9_-]{12,}\b")

RouteSmokeRunner = Callable[[dict[str, Any]], dict[str, Any]]


def route_promotion_section_template(*, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_SCHEMA_VERSION,
        "generated_at": generated_at or now_iso(),
        "status": "not_requested",
        "records": [],
        "warnings": [],
    }


def normalize_route_promotion_section(
    value: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize a route lifecycle section without accepting provider secrets.

    A non-documentation promotion has to carry a complete, canonical route
    proof.  This routine validates the proof's internal binding; applying it
    later also binds it to the then-current router endpoint and adapter.
    """

    if value in (None, {}):
        return route_promotion_section_template()
    if not isinstance(value, dict):
        raise ValueError("route_promotion must be an object.")
    schema_version = str(value.get("schema_version") or AGENTIC_UPDATE_ROUTE_PROMOTION_SCHEMA_VERSION).strip()
    if schema_version != AGENTIC_UPDATE_ROUTE_PROMOTION_SCHEMA_VERSION:
        raise ValueError("Unexpected route_promotion schema version.")
    raw_records = value.get("records")
    if raw_records is None:
        raw_records = value.get("events") or []
    if not isinstance(raw_records, list):
        raise ValueError("route_promotion.records must be a list.")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_records:
        if not isinstance(raw, dict):
            raise ValueError("route_promotion.records entries must be objects.")
        record = normalize_route_promotion_record(raw, now=now)
        record_id = str(record["record_id"])
        if record_id in seen:
            raise ValueError(f"Duplicate route promotion record_id: {record_id}")
        seen.add(record_id)
        records.append(record)
    warnings = _safe_labels(value.get("warnings"), field="route_promotion.warnings")
    return {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_SCHEMA_VERSION,
        "generated_at": _safe_timestamp(value.get("generated_at")) or now_iso(),
        "status": _section_status(records),
        "records": records,
        "warnings": warnings,
    }


def normalize_route_promotion_record(raw: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("route promotion record must be an object.")
    schema_version = str(raw.get("schema_version") or AGENTIC_UPDATE_ROUTE_PROMOTION_RECORD_SCHEMA_VERSION).strip()
    if schema_version != AGENTIC_UPDATE_ROUTE_PROMOTION_RECORD_SCHEMA_VERSION:
        raise ValueError("Unexpected route promotion record schema version.")
    action = str(raw.get("action") or "").strip()
    target_state = str(raw.get("target_state") or raw.get("state") or "").strip()
    if not action:
        action = "promote" if target_state and target_state != "documented" else "document"
    if action not in ROUTE_PROMOTION_ACTIONS:
        raise ValueError("route promotion action is invalid.")
    if not target_state:
        target_state = "documented" if action != "promote" else "adapter_dry_run_passed"
    if target_state not in EXECUTION_ROUTE_PROMOTION_STATES:
        raise ValueError("route promotion target_state is invalid.")
    if action == "promote" and target_state == "documented":
        raise ValueError("route promotion cannot promote to documented.")
    if action != "promote" and target_state != "documented":
        raise ValueError("route downgrade, expiry, rollback, and documentation must target documented.")

    model_id = _safe_identifier(raw.get("model_id"), field="model_id")
    provider_id = _safe_identifier(raw.get("provider_id") or model_id.split("/", 1)[0], field="provider_id")
    native_model = _safe_identifier(
        raw.get("native_model") or (model_id.split("/", 1)[1] if "/" in model_id else model_id),
        field="native_model",
    )
    if "/" in model_id and model_id.split("/", 1)[0] != provider_id:
        raise ValueError("route promotion provider_id must match model_id.")

    raw_previous = raw.get("previous_evidence")
    previous_evidence = _storage_evidence(raw_previous, field="previous_evidence")
    raw_subject = raw.get("route_subject") or raw.get("subject")
    if raw_subject is None and previous_evidence:
        raw_subject = previous_evidence.get("subject")
    route_subject = _route_subject(
        raw_subject,
        provider_id=provider_id,
        model_id=model_id,
        native_model=native_model,
        full_required=action == "promote",
    )
    if previous_evidence:
        _assert_subject_identity(previous_evidence["subject"], route_subject, allow_partial_route_subject=True)
    previous_state = str(raw.get("previous_state") or (previous_evidence or {}).get("state") or "documented").strip()
    if previous_state not in EXECUTION_ROUTE_PROMOTION_STATES:
        raise ValueError("route promotion previous_state is invalid.")

    route_evidence: dict[str, Any] | None = None
    if action == "promote":
        if not _has_full_route_subject(route_subject):
            raise ValueError("route promotion requires an endpoint- and adapter-bound route_subject.")
        source_evidence = raw.get("route_evidence") or raw.get("evidence")
        if not isinstance(source_evidence, dict):
            raise ValueError("route promotion requires route_evidence.")
        normalized = normalize_execution_route_evidence(source_evidence, subject=route_subject, now=now)
        if normalized.get("effective_state") != target_state or normalized.get("reasons"):
            raise ValueError("route promotion evidence must be current and exactly bound to route_subject.")
        route_evidence = execution_route_evidence_for_storage(normalized)
        if route_evidence is None or str(route_evidence.get("state") or "") != target_state:
            raise ValueError("route promotion evidence is not safe for storage.")
        if ROUTE_PROMOTION_STATE_RANK[target_state] != ROUTE_PROMOTION_STATE_RANK[previous_state] + 1:
            raise ValueError("route promotion must advance exactly one lifecycle state at a time.")
    elif action == "expire":
        if not previous_evidence:
            raise ValueError("route evidence expiry requires previous_evidence.")
        expires_at = _parse_datetime(previous_evidence.get("expires_at"))
        effective_now = _normalized_now(now)
        if expires_at is None or expires_at > effective_now:
            raise ValueError("route evidence expiry requires an expired previous_evidence record.")

    source_provenance = _source_provenance(raw.get("source_provenance"), provider_id=provider_id, fallback_record_id=model_id)
    evidence_refs = _safe_refs(raw.get("evidence_refs"), field="evidence_refs")
    if not evidence_refs:
        evidence_refs = list(route_evidence.get("evidence_refs") or []) if route_evidence else []
    if action == "promote" and not evidence_refs:
        raise ValueError("route promotion requires secret-free evidence_refs.")
    reason = _safe_label(raw.get("reason") or _default_reason(action, target_state), field="reason")
    record_id = _safe_identifier(
        raw.get("record_id") or _record_id(action, model_id, target_state, reason, route_subject),
        field="record_id",
    )
    required_gates = route_promotion_required_gates(target_state, action=action)
    return {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_RECORD_SCHEMA_VERSION,
        "record_id": record_id,
        "action": action,
        "provider_id": provider_id,
        "model_id": model_id,
        "native_model": native_model,
        "previous_state": previous_state,
        "target_state": target_state,
        "route_subject": route_subject,
        "previous_evidence": previous_evidence,
        "route_evidence": route_evidence,
        "reason": reason,
        "source_provenance": source_provenance,
        "evidence_refs": evidence_refs,
        "required_gates": required_gates,
        "requires_provider_calls": bool(set(required_gates).intersection(ROUTE_PROMOTION_PROVIDER_GATES)),
        "created_at": _safe_timestamp(raw.get("created_at")) or now_iso(),
    }


def route_promotion_required_gates(target_state: str, *, action: str) -> list[str]:
    if action == "document":
        return []
    if action in {"downgrade", "expire", "rollback"}:
        return ["execution_route_dry_run"]
    return list(ROUTE_PROMOTION_REQUIRED_GATES.get(target_state) or [])


def documented_route_record_for_candidate(candidate: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Return a factual-record companion that deliberately carries no proof."""

    model_id = str(candidate.get("model_id") or "").strip()
    provider_id = str(candidate.get("provider_id") or (model_id.split("/", 1)[0] if "/" in model_id else "")).strip()
    native_model = str(candidate.get("native_model") or (model_id.split("/", 1)[1] if "/" in model_id else model_id)).strip()
    refs = [dict(item) for item in list(candidate.get("source_refs") or []) if isinstance(item, dict)]
    first = refs[0] if refs else {}
    source_id = str(first.get("source_id") or first.get("id") or f"documentation-{model_id}").strip()
    # The discovery result already owns the full source URL and hash. Keep the
    # lifecycle record reference-shaped so query strings or fragments cannot
    # accidentally become durable route evidence.
    source_ref = f"source:{source_id}" if source_id else ""
    return normalize_route_promotion_record(
        {
            "action": "document",
            "provider_id": provider_id,
            "model_id": model_id,
            "native_model": native_model,
            "previous_state": "documented",
            "target_state": "documented",
            "reason": "documentation_discovery_only",
            "source_provenance": {
                "kind": "official_docs" if refs else "discovery",
                "issuer": provider_id or "agentic_update",
                "record_id": source_id,
            },
            "evidence_refs": [source_ref] if source_ref else [],
        },
        now=now,
    )


def deprovision_route_record(
    current: dict[str, Any],
    *,
    action: str,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Create a restrictive event from a stored proof without deleting facts."""

    if action not in {"downgrade", "expire", "rollback"}:
        raise ValueError("deprovision route action is invalid.")
    previous = _storage_evidence(current.get("execution_route_evidence"), field="execution_route_evidence")
    if not previous:
        return None
    subject = dict(previous.get("subject") or {})
    model_id = str(current.get("model_id") or current.get("id") or subject.get("model_id") or "").strip()
    provider_id = str(current.get("provider_id") or current.get("provider") or subject.get("provider_id") or "").strip()
    native_model = str(current.get("native_model") or subject.get("native_model") or "").strip()
    if not model_id or not provider_id or not native_model:
        return None
    if action == "expire":
        expires_at = _parse_datetime(previous.get("expires_at"))
        if expires_at is None or expires_at > _normalized_now(now):
            return None
    return normalize_route_promotion_record(
        {
            "action": action,
            "provider_id": provider_id,
            "model_id": model_id,
            "native_model": native_model,
            "previous_state": previous.get("state"),
            "target_state": "documented",
            "route_subject": subject,
            "previous_evidence": previous,
            "reason": reason,
            "source_provenance": {
                "kind": "route_lifecycle_audit",
                "issuer": "astrabridge",
                "record_id": f"{action}-{model_id}",
            },
            "evidence_refs": list(previous.get("evidence_refs") or []),
        },
        now=now,
    )


def route_promotion_records_from_proposal(
    proposal: dict[str, Any],
    *,
    only_diff_changes: bool = False,
) -> list[dict[str, Any]]:
    section = normalize_route_promotion_section(dict(proposal.get("route_promotion") or {}))
    records = [dict(item) for item in section["records"]]
    if not only_diff_changes:
        return records
    ids = route_promotion_record_ids_from_diff(dict(proposal.get("diff") or {}))
    return [record for record in records if str(record.get("record_id") or "") in ids]


def route_promotion_record_ids_from_diff(diff: dict[str, Any]) -> set[str]:
    record_ids: set[str] = set()
    for change in list(dict(diff or {}).get("changes") or []):
        if not isinstance(change, dict) or str(change.get("change_type") or "") not in ROUTE_PROMOTION_CHANGE_TYPES:
            continue
        details = dict(change.get("details") or {})
        record_id = str(details.get("route_promotion_record_id") or "").strip()
        if record_id:
            record_ids.add(record_id)
    return record_ids


def route_promotion_dry_run(proposal: dict[str, Any]) -> dict[str, Any]:
    """Validate the exact route binding locally; it never opens a network connection."""

    records = route_promotion_records_from_proposal(proposal, only_diff_changes=True)
    record_results = []
    for record in records:
        action = str(record.get("action") or "")
        state = str(record.get("target_state") or "documented")
        subject = dict(record.get("route_subject") or {})
        result = {
            "record_id": record.get("record_id"),
            "model_id": record.get("model_id"),
            "action": action,
            "target_state": state,
            "route_subject": subject,
            "status": "pass",
            "reasons": [],
        }
        if action == "promote" and not _has_full_route_subject(subject):
            result.update({"status": "fail", "reasons": ["route_subject_incomplete"]})
        record_results.append(result)
    status = "pass" if all(item["status"] == "pass" for item in record_results) else "fail"
    return {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_VALIDATION_SCHEMA_VERSION,
        "kind": "dry_run",
        "status": status,
        "provider_calls_attempted": False,
        "record_results": record_results,
        "evidence_refs": [],
        "warnings": [],
    }


def run_route_promotion_provider_smoke(
    proposal: dict[str, Any],
    *,
    gate_id: str,
    allow_provider_calls: bool,
    route_smoke_runner: RouteSmokeRunner | None,
) -> dict[str, Any]:
    """Call a capability-specific runner only after explicit authorization.

    The runner receives only route identifiers and fingerprints.  It owns key
    retrieval and must return a compact, secret-free result that repeats the
    exact route subject for every passed record.
    """

    records = [
        record
        for record in route_promotion_records_from_proposal(proposal, only_diff_changes=True)
        if gate_id in set(record.get("required_gates") or [])
    ]
    if not allow_provider_calls:
        return _blocked_provider_smoke(records, gate_id=gate_id, reason="provider_calls_not_authorized")
    if route_smoke_runner is None:
        return _blocked_provider_smoke(records, gate_id=gate_id, reason="route_specific_provider_smoke_runner_unavailable")
    payload = {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_VALIDATION_SCHEMA_VERSION,
        "kind": "provider_smoke_request",
        "gate_id": gate_id,
        "records": [
            {
                "record_id": record["record_id"],
                "provider_id": record["provider_id"],
                "model_id": record["model_id"],
                "native_model": record["native_model"],
                "target_state": record["target_state"],
                "route_subject": dict(record["route_subject"]),
            }
            for record in records
        ],
    }
    response = route_smoke_runner(deepcopy(payload))
    return _normalize_provider_smoke_response(response, records=records, gate_id=gate_id)


def validate_route_promotion_apply(
    proposal: dict[str, Any],
    *,
    run_contract: dict[str, Any],
    validation_result: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return route records ready to apply or fail closed with an exact gate."""

    records = route_promotion_records_from_proposal(proposal, only_diff_changes=True)
    if not records:
        raise ValueError("No execution-route lifecycle changes are available for apply.")
    result = dict(validation_result or proposal.get("validation_result") or {})
    gates = {
        str(gate.get("gate_id") or ""): dict(gate)
        for gate in list(result.get("gates") or [])
        if isinstance(gate, dict) and str(gate.get("gate_id") or "").strip()
    }
    contract = dict(run_contract or {})
    for record in records:
        action = str(record.get("action") or "")
        target_state = str(record.get("target_state") or "documented")
        if action == "promote":
            if target_state == "adapter_dry_run_passed":
                if str(contract.get("apply_mode") or "") not in {"verify_candidate", "promote_after_smoke"}:
                    raise ValueError("Adapter dry-run promotion requires verify_candidate or promote_after_smoke apply mode.")
            else:
                if not bool(contract.get("allow_network")) or not bool(contract.get("allow_provider_calls")):
                    raise ValueError("Provider-backed route promotion requires explicit allow_provider_calls=true authorization.")
                if str(contract.get("apply_mode") or "") != "promote_after_smoke":
                    raise ValueError("Provider-backed route promotion requires promote_after_smoke apply mode.")
        for gate_id in list(record.get("required_gates") or []):
            gate = gates.get(gate_id)
            if not gate or str(gate.get("status") or "") != "pass" or bool(gate.get("blocks_promotion")):
                raise ValueError(f"Route promotion record {record.get('record_id')} is blocked by {gate_id}.")
            evidence_mode = str(gate.get("evidence_mode") or "").strip()
            if gate_id == "execution_route_dry_run" and evidence_mode not in {"internal", "route_dry_run"}:
                raise ValueError("Route promotion requires a real internal route dry-run record, not fixture evidence.")
            if gate_id in ROUTE_PROMOTION_PROVIDER_GATES and evidence_mode != "provider":
                raise ValueError("Tool/coding/default route promotion requires provider-backed route smoke evidence.")
    return records


def route_promotion_storage_for_model(
    record: dict[str, Any],
    *,
    model: dict[str, Any],
    provider: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Bind a ready record to the actual router state before persistence."""

    normalized = normalize_route_promotion_record(record, now=now)
    if normalized["target_state"] == "documented":
        return None
    proof = dict(normalized.get("route_evidence") or {})
    route = resolve_execution_route(model, provider=provider, evidence=proof, now=now)
    evidence = dict(route.get("evidence") or {})
    if evidence.get("effective_state") != normalized["target_state"] or evidence.get("reasons"):
        raise ValueError("Route promotion proof no longer matches the current provider/model/endpoint/adapter route.")
    stored = execution_route_evidence_for_storage(evidence)
    if stored is None:
        raise ValueError("Route promotion proof cannot be stored safely.")
    return stored


def route_promotion_apply_ledger(
    *,
    run_id: str,
    records: list[dict[str, Any]],
    applied_events: list[dict[str, Any]],
    status: str = "applied",
) -> dict[str, Any]:
    return {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_APPLY_LEDGER_SCHEMA_VERSION,
        "run_id": _safe_identifier(run_id, field="run_id"),
        "created_at": now_iso(),
        "status": _safe_label(status, field="status"),
        "metadata_preserved": True,
        "records": [
            {
                "record_id": record.get("record_id"),
                "action": record.get("action"),
                "model_id": record.get("model_id"),
                "target_state": record.get("target_state"),
                "route_subject": dict(record.get("route_subject") or {}),
            }
            for record in records
        ],
        "applied_events": [dict(event) for event in applied_events],
        "warnings": [],
    }


def route_promotion_rollback_record(
    *,
    run_id: str,
    apply_id: str | None,
    ledger: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_ROLLBACK_SCHEMA_VERSION,
        "run_id": _safe_identifier(run_id, field="run_id"),
        "apply_id": _safe_identifier(apply_id, field="apply_id", required=False) or None,
        "rolled_back_at": now_iso(),
        "action": "restore_prior_route_evidence_or_documented_state",
        "metadata_preserved": True,
        "record_ids": [
            str(item.get("record_id") or "")
            for item in list((ledger or {}).get("records") or [])
            if isinstance(item, dict) and str(item.get("record_id") or "").strip()
        ],
    }


def _blocked_provider_smoke(records: list[dict[str, Any]], *, gate_id: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_VALIDATION_SCHEMA_VERSION,
        "kind": "provider_smoke",
        "gate_id": gate_id,
        "status": "blocked",
        "provider_calls_attempted": False,
        "record_results": [
            {
                "record_id": record.get("record_id"),
                "route_subject": dict(record.get("route_subject") or {}),
                "status": "blocked",
                "reasons": [reason],
            }
            for record in records
        ],
        "evidence_refs": [],
        "warnings": [],
    }


def _normalize_provider_smoke_response(
    response: Any,
    *,
    records: list[dict[str, Any]],
    gate_id: str,
) -> dict[str, Any]:
    if not isinstance(response, dict):
        return _blocked_provider_smoke(records, gate_id=gate_id, reason="route_smoke_runner_returned_non_object")
    raw_results = response.get("record_results")
    if not isinstance(raw_results, list):
        return _blocked_provider_smoke(records, gate_id=gate_id, reason="route_smoke_runner_missing_record_results")
    by_id = {str(item.get("record_id") or ""): item for item in raw_results if isinstance(item, dict)}
    normalized_results = []
    failures = False
    for record in records:
        record_id = str(record.get("record_id") or "")
        raw = by_id.get(record_id)
        reasons: list[str] = []
        status = "pass"
        if not raw:
            status = "blocked"
            reasons.append("route_smoke_runner_missing_record_result")
        elif str(raw.get("status") or "") != "pass":
            status = "blocked"
            reasons.extend(_safe_labels(raw.get("reasons"), field="route_smoke_reasons")) or reasons.append("route_smoke_runner_did_not_pass")
        else:
            subject = _route_subject(
                raw.get("route_subject"),
                provider_id=str(record.get("provider_id") or ""),
                model_id=str(record.get("model_id") or ""),
                native_model=str(record.get("native_model") or ""),
                full_required=True,
            )
            if subject != dict(record.get("route_subject") or {}):
                status = "fail"
                reasons.append("route_smoke_subject_mismatch")
        if status != "pass":
            failures = True
        normalized_results.append(
            {
                "record_id": record_id,
                "route_subject": dict(record.get("route_subject") or {}),
                "status": status,
                "reasons": reasons,
                "evidence_refs": _safe_refs((raw or {}).get("evidence_refs"), field="route_smoke_evidence_refs"),
            }
        )
    refs = _safe_refs(response.get("evidence_refs"), field="route_smoke_evidence_refs")
    for result in normalized_results:
        refs.extend(item for item in result["evidence_refs"] if item not in refs)
    if not refs:
        failures = True
        for result in normalized_results:
            if result["status"] == "pass":
                result["status"] = "blocked"
                result["reasons"].append("route_smoke_evidence_refs_missing")
    return {
        "schema_version": AGENTIC_UPDATE_ROUTE_PROMOTION_VALIDATION_SCHEMA_VERSION,
        "kind": "provider_smoke",
        "gate_id": gate_id,
        "status": "pass" if not failures else "blocked",
        "provider_calls_attempted": True,
        "record_results": normalized_results,
        "evidence_refs": refs,
        "warnings": _safe_labels(response.get("warnings"), field="route_smoke_warnings"),
    }


def _storage_evidence(value: Any, *, field: str) -> dict[str, Any] | None:
    if value in (None, {}):
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")
    stored = execution_route_evidence_for_storage(value)
    if stored is None:
        raise ValueError(f"{field} must be a complete secret-free execution route proof.")
    _route_subject(
        stored.get("subject"),
        provider_id=str(dict(stored.get("subject") or {}).get("provider_id") or ""),
        model_id=str(dict(stored.get("subject") or {}).get("model_id") or ""),
        native_model=str(dict(stored.get("subject") or {}).get("native_model") or ""),
        full_required=True,
    )
    return stored


def _route_subject(
    value: Any,
    *,
    provider_id: str,
    model_id: str,
    native_model: str,
    full_required: bool,
) -> dict[str, str]:
    raw = dict(value) if isinstance(value, dict) else {}
    subject = {
        "provider_id": _safe_identifier(raw.get("provider_id") or provider_id, field="route_subject.provider_id"),
        "model_id": _safe_identifier(raw.get("model_id") or model_id, field="route_subject.model_id"),
        "native_model": _safe_identifier(raw.get("native_model") or native_model, field="route_subject.native_model"),
    }
    for key in ("endpoint_fingerprint", "adapter_signature"):
        raw_value = str(raw.get(key) or "").strip()
        if raw_value:
            if not _FINGERPRINT_RE.fullmatch(raw_value):
                raise ValueError(f"route_subject.{key} must be a SHA-256 fingerprint.")
            subject[key] = raw_value.lower()
    if full_required and not _has_full_route_subject(subject):
        raise ValueError("route_subject must include endpoint_fingerprint and adapter_signature.")
    return subject


def _has_full_route_subject(subject: dict[str, Any]) -> bool:
    return all(str(subject.get(key) or "").strip() for key in ("provider_id", "model_id", "native_model", "endpoint_fingerprint", "adapter_signature"))


def _assert_subject_identity(
    presented: dict[str, Any],
    expected: dict[str, Any],
    *,
    allow_partial_route_subject: bool,
) -> None:
    for key in ("provider_id", "model_id", "native_model"):
        if str(presented.get(key) or "") != str(expected.get(key) or ""):
            raise ValueError("route evidence subject does not match route promotion identity.")
    for key in ("endpoint_fingerprint", "adapter_signature"):
        presented_value = str(presented.get(key) or "")
        expected_value = str(expected.get(key) or "")
        if expected_value and presented_value != expected_value:
            raise ValueError("route evidence binding does not match route promotion subject.")
        if not allow_partial_route_subject and not expected_value:
            raise ValueError("route evidence binding is incomplete.")


def _source_provenance(value: Any, *, provider_id: str, fallback_record_id: str) -> dict[str, str]:
    raw = dict(value) if isinstance(value, dict) else {}
    return {
        "kind": _safe_label(raw.get("kind") or "agentic_update", field="source_provenance.kind"),
        "issuer": _safe_label(raw.get("issuer") or provider_id or "astrabridge", field="source_provenance.issuer"),
        "record_id": _safe_label(raw.get("record_id") or fallback_record_id, field="source_provenance.record_id"),
    }


def _safe_refs(value: Any, *, field: str) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else ([] if value in (None, "") else [value])
    refs: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if not text:
            continue
        if len(text) > 512 or "?" in text or "#" in text or _contains_secret_reference(text):
            raise ValueError(f"{field} contains an unsafe evidence reference.")
        if text not in refs:
            refs.append(text)
    return refs


def _safe_labels(value: Any, *, field: str) -> list[str]:
    values = value if isinstance(value, (list, tuple)) else ([] if value in (None, "") else [value])
    labels = []
    for item in values:
        label = _safe_label(item, field=field)
        if label not in labels:
            labels.append(label)
    return labels


def _safe_identifier(value: Any, *, field: str, required: bool = True) -> str:
    text = str(value or "").strip()
    if not text and not required:
        return ""
    if not text or not _IDENTIFIER_RE.fullmatch(text) or _contains_secret_reference(text):
        raise ValueError(f"{field} must be a non-secret identifier.")
    return text


def _safe_label(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text or not _LABEL_RE.fullmatch(text) or _contains_secret_reference(text):
        raise ValueError(f"{field} must be a non-secret label.")
    return text


def _safe_timestamp(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    return parsed.isoformat() if parsed else None


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalized_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _contains_secret_reference(value: str) -> bool:
    return bool(_SECRET_REFERENCE_RE.search(value) or _PATH_SECRET_RE.search(value) or _TOKEN_VALUE_RE.search(value))


def _default_reason(action: str, target_state: str) -> str:
    return {
        "document": "documentation_discovery_only",
        "promote": f"promotion_to_{target_state}",
        "downgrade": "route_downgrade_requested",
        "expire": "route_evidence_expired",
        "rollback": "route_rollback_requested",
    }[action]


def _record_id(action: str, model_id: str, target_state: str, reason: str, subject: dict[str, Any]) -> str:
    fingerprint = "|".join(
        [action, model_id, target_state, reason, str(subject.get("endpoint_fingerprint") or ""), str(subject.get("adapter_signature") or "")]
    )
    return f"route-{action}-{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:16]}"


def _section_status(records: list[dict[str, Any]]) -> str:
    if not records:
        return "not_requested"
    if any(str(record.get("action") or "") == "promote" for record in records):
        return "gated"
    if any(str(record.get("action") or "") != "document" for record in records):
        return "review_required"
    return "documented_only"


__all__ = [
    "AGENTIC_UPDATE_ROUTE_PROMOTION_APPLY_LEDGER_SCHEMA_VERSION",
    "AGENTIC_UPDATE_ROUTE_PROMOTION_RECORD_SCHEMA_VERSION",
    "AGENTIC_UPDATE_ROUTE_PROMOTION_ROLLBACK_SCHEMA_VERSION",
    "AGENTIC_UPDATE_ROUTE_PROMOTION_SCHEMA_VERSION",
    "AGENTIC_UPDATE_ROUTE_PROMOTION_VALIDATION_SCHEMA_VERSION",
    "ROUTE_PROMOTION_ACTIONS",
    "ROUTE_PROMOTION_CHANGE_TYPES",
    "ROUTE_PROMOTION_PROVIDER_GATES",
    "ROUTE_PROMOTION_REQUIRED_GATES",
    "RouteSmokeRunner",
    "deprovision_route_record",
    "documented_route_record_for_candidate",
    "normalize_route_promotion_record",
    "normalize_route_promotion_section",
    "route_promotion_apply_ledger",
    "route_promotion_dry_run",
    "route_promotion_record_ids_from_diff",
    "route_promotion_records_from_proposal",
    "route_promotion_required_gates",
    "route_promotion_rollback_record",
    "route_promotion_section_template",
    "route_promotion_storage_for_model",
    "run_route_promotion_provider_smoke",
    "validate_route_promotion_apply",
]
