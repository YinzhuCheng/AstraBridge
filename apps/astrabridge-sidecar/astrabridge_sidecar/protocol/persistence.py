"""Innermost durable-write normalization for protocol-owned runtime records.

This module keeps the schema-derived protocol vocabularies and the durable
SQLite write boundary in one place. Current run projections remain
`astrabridge-task-graph-run-v1` compatibility shapes, but any persisted
envelopes, events, content parts, and artifact references are normalized to the
canonical protocol contract before they reach the store.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from .compatibility import adapt_legacy_artifact_path, migrate_compiled_plan, migrate_graph_definition
from .generated.v1 import (
    ARTIFACT_STATUSES,
    CAPABILITY_OUTPUT_STATUSES,
    CONTENT_PART_KINDS,
    PORT_SHAPES,
    PORT_TYPES,
    PROTOCOL_VOCABULARIES,
    RUN_EVENT_TYPES,
    SCHEMA_VERSION,
    validate_protocol_payload,
)


PROTOCOL_PERSISTENCE_SCHEMA_VERSION = "astrabridge-protocol-persistence-v1"
LEGACY_RUN_PROJECTION_SCHEMA_VERSIONS = frozenset({"astrabridge-task-graph-run-v1"})
DEFAULT_SOURCE_NODE_ID = "graph-runtime"
DEFAULT_DELIVERY_REPLAY_WINDOW_SECONDS = 0

CANONICAL_PROTOCOL_VOCABULARIES = {
    "run_event_types": tuple(RUN_EVENT_TYPES),
    "artifact_statuses": tuple(ARTIFACT_STATUSES),
    "content_part_kinds": tuple(CONTENT_PART_KINDS),
    "port_types": tuple(PORT_TYPES),
    "port_shapes": tuple(PORT_SHAPES),
    "capability_output_statuses": tuple(CAPABILITY_OUTPUT_STATUSES),
}


class ProtocolPersistenceError(ValueError):
    """The payload is outside the supported durable-write protocol contract."""


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _parse_timestamp(value: Any, *, field: str) -> datetime | None:
    text = _string_or_none(value)
    if text is None:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ProtocolPersistenceError(f"{field} must be an ISO-8601 timestamp when provided.") from exc


def _int_or_default(value: Any, *, field: str, default: int = 0, minimum: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ProtocolPersistenceError(f"{field} must be an integer.") from exc
    if parsed < minimum:
        raise ProtocolPersistenceError(f"{field} must be >= {minimum}.")
    return parsed


def canonicalize_protocol_delivery_contract(envelope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise TypeError("agent envelope must be an object.")
    candidate = deepcopy(envelope)
    delivery = dict(candidate.get("delivery") or {})
    metadata = dict(candidate.get("metadata") or {})
    recipient = dict(candidate.get("recipient") or {})
    raw_extension = dict(metadata.get("astrabridge_delivery") or {})
    created_at = _string_or_none(candidate.get("created_at"))
    created_dt = _parse_timestamp(created_at, field="created_at") if created_at else None
    not_before_at = _string_or_none(raw_extension.get("not_before_at") or metadata.get("not_before_at"))
    deadline_at = _string_or_none(raw_extension.get("deadline_at") or metadata.get("deadline_at"))
    ttl_seconds = _int_or_default(
        raw_extension.get("ttl_seconds") if raw_extension.get("ttl_seconds") is not None else metadata.get("ttl_seconds"),
        field="metadata.astrabridge_delivery.ttl_seconds",
        default=0,
        minimum=0,
    )
    replay_window_seconds = _int_or_default(
        raw_extension.get("replay_window_seconds")
        if raw_extension.get("replay_window_seconds") is not None
        else metadata.get("replay_window_seconds"),
        field="metadata.astrabridge_delivery.replay_window_seconds",
        default=DEFAULT_DELIVERY_REPLAY_WINDOW_SECONDS,
        minimum=0,
    )
    sequence = _int_or_default(delivery.get("sequence"), field="delivery.sequence", default=0, minimum=0)
    attempt = _int_or_default(delivery.get("attempt"), field="delivery.attempt", default=1, minimum=1)
    not_before_dt = _parse_timestamp(not_before_at, field="metadata.astrabridge_delivery.not_before_at") if not_before_at else None
    deadline_dt = _parse_timestamp(deadline_at, field="metadata.astrabridge_delivery.deadline_at") if deadline_at else None
    expires_dt = created_dt + timedelta(seconds=ttl_seconds) if created_dt is not None and ttl_seconds > 0 else None
    if not_before_dt is not None and deadline_dt is not None and not_before_dt > deadline_dt:
        raise ProtocolPersistenceError("Delivery not_before_at must be <= deadline_at.")
    if expires_dt is not None and deadline_dt is not None and deadline_dt > expires_dt:
        expires_dt = deadline_dt
    replay_deadline_dt = (
        created_dt + timedelta(seconds=replay_window_seconds)
        if created_dt is not None and replay_window_seconds > 0
        else expires_dt
    )
    contract = {
        "message_id": _string_or_none(candidate.get("message_id")),
        "delivery_idempotency_key": _string_or_none(delivery.get("idempotency_key")),
        "attempt": attempt,
        "sequence": sequence,
        "edge_id": _string_or_none(metadata.get("edge_id")),
        "graph_id": _string_or_none(metadata.get("graph_id")),
        "source_node_id": _string_or_none(metadata.get("source_node_id")),
        "target_node_id": _string_or_none(metadata.get("target_node_id")),
        "audience_agent_id": _string_or_none(recipient.get("agent_id")),
        "audience_provider_id": _string_or_none(recipient.get("provider_id")),
        "audience_lane_id": _string_or_none(recipient.get("lane_id")),
        "not_before_at": not_before_at,
        "deadline_at": deadline_at,
        "ttl_seconds": ttl_seconds,
        "expires_at": expires_dt.isoformat() if expires_dt is not None else None,
        "replay_window_seconds": replay_window_seconds,
        "replay_deadline_at": replay_deadline_dt.isoformat() if replay_deadline_dt is not None else None,
    }
    metadata["astrabridge_delivery"] = contract
    candidate["metadata"] = metadata
    return contract


def canonicalize_protocol_artifact_ref(
    artifact: dict[str, Any],
    *,
    task_id: str | None = None,
    run_id: str | None = None,
    source_node_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(artifact, dict):
        raise TypeError("artifact must be an object.")
    candidate = deepcopy(artifact)
    lineage = dict(candidate.get("lineage") or {})
    lineage_task_id = _string_or_none(lineage.get("task_id")) or _string_or_none(task_id) or _string_or_none(candidate.get("task_id"))
    lineage_run_id = _string_or_none(lineage.get("run_id")) or _string_or_none(run_id) or _string_or_none(candidate.get("run_id"))
    lineage_source_node_id = (
        _string_or_none(lineage.get("source_node_id"))
        or _string_or_none(source_node_id)
        or _string_or_none(candidate.get("source_node_id"))
        or _string_or_none(dict(candidate.get("metadata") or {}).get("source_node_id"))
        or DEFAULT_SOURCE_NODE_ID
    )
    raw_path = str(candidate.get("path") or candidate.get("relative_path") or "").replace("\\", "/").strip()
    if not _string_or_none(candidate.get("artifact_uri")) and raw_path.startswith("UNSAFE_EXTERNAL_PATH/"):
        candidate["artifact_uri"] = f"ab-artifact://{raw_path.lower()}"
    elif not _string_or_none(candidate.get("artifact_uri")):
        canonical = adapt_legacy_artifact_path(
            candidate,
            task_id=lineage_task_id,
            run_id=lineage_run_id,
            source_node_id=lineage_source_node_id,
        )
        candidate = {**candidate, **canonical}
    candidate.setdefault("media_type", _string_or_none(candidate.get("mime_type")) or "application/octet-stream")
    candidate.setdefault("status", _string_or_none(candidate.get("status")) or "ready")
    candidate["lineage"] = {
        **lineage,
        "task_id": lineage_task_id,
        "run_id": lineage_run_id,
        "source_node_id": lineage_source_node_id,
    }
    return deepcopy(validate_protocol_payload("ArtifactRef", candidate))


def canonicalize_protocol_content_part(
    part: dict[str, Any],
    *,
    task_id: str | None = None,
    run_id: str | None = None,
    source_node_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(part, dict):
        raise TypeError("content part must be an object.")
    candidate = deepcopy(part)
    if isinstance(candidate.get("artifact"), dict):
        candidate["artifact"] = canonicalize_protocol_artifact_ref(
            dict(candidate["artifact"]),
            task_id=task_id,
            run_id=run_id,
            source_node_id=source_node_id,
        )
    return deepcopy(validate_protocol_payload("ContentPart", candidate))


def canonicalize_protocol_agent_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise TypeError("agent envelope must be an object.")
    candidate = deepcopy(envelope)
    candidate.setdefault("schema_version", SCHEMA_VERSION)
    task_id = _string_or_none(candidate.get("task_id"))
    run_id = _string_or_none(candidate.get("run_id"))
    metadata = dict(candidate.get("metadata") or {})
    source_node_id = _string_or_none(metadata.get("source_node_id"))
    candidate["content"] = [
        canonicalize_protocol_content_part(
            dict(item),
            task_id=task_id,
            run_id=run_id,
            source_node_id=source_node_id,
        )
        for item in list(candidate.get("content") or [])
        if isinstance(item, dict)
    ]
    canonicalize_protocol_delivery_contract(candidate)
    return deepcopy(validate_protocol_payload("AgentEnvelope", candidate))


def canonicalize_protocol_run_event(
    event: dict[str, Any],
    *,
    run_id: str | None = None,
    task_id: str | None = None,
    trace_id: str | None = None,
    created_at: str | None = None,
    source_node_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise TypeError("run event must be an object.")
    candidate = deepcopy(event)
    candidate.setdefault("schema_version", SCHEMA_VERSION)
    if run_id is not None:
        candidate.setdefault("run_id", run_id)
    if task_id is not None:
        candidate.setdefault("task_id", task_id)
    if trace_id is not None:
        candidate.setdefault("trace_id", trace_id)
    if created_at is not None:
        candidate.setdefault("created_at", created_at)
    candidate.setdefault("payload", {})
    if not isinstance(candidate.get("payload"), dict):
        raise ProtocolPersistenceError("RunEvent.payload must remain an object at the durable write boundary.")
    if candidate.get("artifact_refs") is not None:
        candidate["artifact_refs"] = [
            canonicalize_protocol_artifact_ref(
                dict(item),
                task_id=_string_or_none(candidate.get("task_id")),
                run_id=_string_or_none(candidate.get("run_id")),
                source_node_id=source_node_id,
            )
            for item in list(candidate.get("artifact_refs") or [])
            if isinstance(item, dict)
        ]
    return deepcopy(validate_protocol_payload("RunEvent", candidate))


def canonicalize_run_projection_payload(run: dict[str, Any], *, source: str = "scheduler") -> dict[str, Any]:
    if not isinstance(run, dict):
        raise TypeError("run must be an object.")
    candidate = deepcopy(run)
    schema_version = _string_or_none(candidate.get("schema_version")) or "astrabridge-task-graph-run-v1"
    if schema_version not in LEGACY_RUN_PROJECTION_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(LEGACY_RUN_PROJECTION_SCHEMA_VERSIONS))
        raise ProtocolPersistenceError(
            f"Unsupported durable run projection schema_version {schema_version!r}. "
            f"Supported read-compatible versions: {supported}."
        )
    candidate["schema_version"] = schema_version
    candidate["protocol_schema_version"] = SCHEMA_VERSION
    task_id = _string_or_none(candidate.get("task_id"))
    run_id = _string_or_none(candidate.get("run_id"))
    trace_id = _string_or_none(candidate.get("trace_id")) or (f"trace-{run_id}" if run_id else None)
    created_at = _string_or_none(candidate.get("created_at"))
    artifact_refs = [
        canonicalize_protocol_artifact_ref(
            dict(item),
            task_id=task_id,
            run_id=run_id,
            source_node_id=_string_or_none(dict(item).get("source_node_id")),
        )
        for item in list(candidate.get("artifact_refs") or [])
        if isinstance(item, dict)
    ]
    candidate["artifact_refs"] = artifact_refs
    if candidate.get("diagnostic_refs") is not None:
        candidate["diagnostic_refs"] = [
            canonicalize_protocol_artifact_ref(
                dict(item),
                task_id=task_id,
                run_id=run_id,
                source_node_id=_string_or_none(dict(item).get("source_node_id")),
            )
            for item in list(candidate.get("diagnostic_refs") or [])
            if isinstance(item, dict)
        ]
    if candidate.get("agent_envelopes") is not None:
        candidate["agent_envelopes"] = [
            canonicalize_protocol_agent_envelope(dict(item))
            for item in list(candidate.get("agent_envelopes") or [])
            if isinstance(item, dict)
        ]
    if candidate.get("event_refs") is not None or candidate.get("timeline_events") is not None:
        events = list(candidate.get("event_refs") or candidate.get("timeline_events") or [])
        canonical_events = [
            canonicalize_protocol_run_event(
                {
                    **dict(item),
                    "sequence": int(dict(item).get("sequence") or index),
                },
                run_id=run_id,
                task_id=task_id,
                trace_id=trace_id,
                created_at=created_at,
                source_node_id=_string_or_none(dict(item).get("node_id")),
            )
            for index, item in enumerate(events)
            if isinstance(item, dict)
        ]
        candidate["event_refs"] = canonical_events
        if candidate.get("timeline_events") is not None:
            candidate["timeline_events"] = deepcopy(canonical_events)
    if candidate.get("graph_definition") is not None:
        candidate["graph_definition"] = migrate_graph_definition(dict(candidate["graph_definition"]))
    if candidate.get("compiled_plan") is not None:
        candidate["compiled_plan"] = migrate_compiled_plan(dict(candidate["compiled_plan"]))
    candidate.setdefault("persistence_source", _string_or_none(source) or "scheduler")
    return candidate


__all__ = [
    "CANONICAL_PROTOCOL_VOCABULARIES",
    "DEFAULT_DELIVERY_REPLAY_WINDOW_SECONDS",
    "DEFAULT_SOURCE_NODE_ID",
    "LEGACY_RUN_PROJECTION_SCHEMA_VERSIONS",
    "PROTOCOL_PERSISTENCE_SCHEMA_VERSION",
    "ProtocolPersistenceError",
    "canonicalize_protocol_agent_envelope",
    "canonicalize_protocol_artifact_ref",
    "canonicalize_protocol_content_part",
    "canonicalize_protocol_delivery_contract",
    "canonicalize_protocol_run_event",
    "canonicalize_run_projection_payload",
]
