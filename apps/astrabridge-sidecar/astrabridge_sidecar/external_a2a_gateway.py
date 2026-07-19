from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol
from urllib.parse import urlparse
from uuid import uuid4

from .common import now_iso
from .protocol import SCHEMA_VERSION, validate_protocol_payload


EXTERNAL_A2A_GATEWAY_SCHEMA_VERSION = "astrabridge-external-a2a-gateway-v1"
EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION = "astrabridge-external-agent-card-registry-v1"
EXTERNAL_A2A_MANIFEST_SCHEMA_VERSION = "astrabridge-external-a2a-manifest-v1"
EXTERNAL_A2A_CARD_REF_PREFIX = "a2a_card:"
SUPPORTED_A2A_PROTOCOL_VERSIONS = ("1.0",)
SUPPORTED_A2A_PROTOCOL_BINDINGS = ("JSONRPC",)
SUPPORTED_A2A_TASK_STATES = (
    "TASK_STATE_SUBMITTED",
    "TASK_STATE_WORKING",
    "TASK_STATE_INPUT_REQUIRED",
    "TASK_STATE_AUTH_REQUIRED",
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_REJECTED",
)
TERMINAL_A2A_TASK_STATES = {
    "TASK_STATE_COMPLETED",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
    "TASK_STATE_REJECTED",
}
INTERRUPTED_A2A_TASK_STATES = {
    "TASK_STATE_INPUT_REQUIRED",
    "TASK_STATE_AUTH_REQUIRED",
}
SUPPORTED_A2A_TRUST_LEVELS = ("untrusted", "workspace_trusted", "pinned")
SUPPORTED_A2A_SECURITY_SCHEME_KEYS = {
    "noAuthSecurityScheme",
    "httpBearerSecurityScheme",
    "apiKeySecurityScheme",
    "oauth2ClientCredentialsSecurityScheme",
    "openIdConnectSecurityScheme",
    "mutualTlsSecurityScheme",
}
SUPPORTED_A2A_CONTENT_KINDS = {
    "text",
    "json",
    "artifact",
    "image",
    "audio",
    "video",
    "document",
    "code",
    "tool_result",
}
SUPPORTED_A2A_EXTENSIONS = (
    "task-send",
    "task-stream",
    "task-cancel",
    "artifact-transfer",
)
SUPPORTED_A2A_ARTIFACT_URI_SCHEMES = {"https", "http", "workspace", "ab-artifact"}
UNSAFE_A2A_ARTIFACT_URI_SCHEMES = {"file", "javascript", "data"}
MAX_A2A_ARTIFACT_URI_LENGTH = 2048
MAX_A2A_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_A2A_REQUEST_BYTES = 256 * 1024
DEFAULT_A2A_REPLAY_WINDOW_SECONDS = 300
DEFAULT_A2A_CLOCK_SKEW_SECONDS = 30
EXTERNAL_A2A_NEGOTIATION_SCHEMA_VERSION = "astrabridge-external-a2a-negotiation-v1"
EXTERNAL_A2A_TRUST_DECISION_SCHEMA_VERSION = "astrabridge-external-a2a-trust-decision-v1"
DEFAULT_EXTERNAL_A2A_REGISTRY_STALE_AFTER_SECONDS = 7 * 24 * 60 * 60
DEFAULT_EXTERNAL_A2A_GATEWAY_STALE_AFTER_SECONDS = 24 * 60 * 60
_CARD_REF_RE = re.compile(rf"^{re.escape(EXTERNAL_A2A_CARD_REF_PREFIX)}[A-Za-z0-9][A-Za-z0-9._:-]*$")

_ALLOWED_A2A_STATE_TRANSITIONS: dict[str, set[str]] = {
    "TASK_STATE_SUBMITTED": {"TASK_STATE_WORKING", "TASK_STATE_INPUT_REQUIRED", "TASK_STATE_AUTH_REQUIRED", *TERMINAL_A2A_TASK_STATES},
    "TASK_STATE_WORKING": {"TASK_STATE_WORKING", "TASK_STATE_INPUT_REQUIRED", "TASK_STATE_AUTH_REQUIRED", *TERMINAL_A2A_TASK_STATES},
    "TASK_STATE_INPUT_REQUIRED": {"TASK_STATE_WORKING", "TASK_STATE_AUTH_REQUIRED", *TERMINAL_A2A_TASK_STATES},
    "TASK_STATE_AUTH_REQUIRED": {"TASK_STATE_WORKING", "TASK_STATE_INPUT_REQUIRED", *TERMINAL_A2A_TASK_STATES},
    "TASK_STATE_COMPLETED": set(),
    "TASK_STATE_FAILED": set(),
    "TASK_STATE_CANCELED": set(),
    "TASK_STATE_REJECTED": set(),
}


def validate_external_a2a_agent_card_registry(
    value: Any,
    *,
    referenced_card_refs: set[str] | None = None,
) -> dict[str, Any] | None:
    if value is None:
        refs = {str(item).strip() for item in set(referenced_card_refs or set()) if str(item).strip()}
        if refs:
            raise ValueError("graph references external A2A card refs but external_agent_card_registry is missing.")
        return None
    registry = _ensure_dict(value, "external_agent_card_registry")
    _require_fields(
        registry,
        "external_agent_card_registry",
        ("schema_version", "supported_protocol_versions", "cards"),
    )
    if str(registry.get("schema_version") or "").strip() != EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION:
        raise ValueError("Unexpected external A2A agent-card registry schema version.")
    supported_versions = _normalize_version_list(
        registry.get("supported_protocol_versions"),
        field="external_agent_card_registry.supported_protocol_versions",
    )
    cards = registry.get("cards")
    if not isinstance(cards, list):
        raise ValueError("external_agent_card_registry.cards must be a list.")
    normalized_cards: list[dict[str, Any]] = []
    by_ref: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(cards):
        normalized = _normalize_registry_entry(
            entry,
            index=index,
            supported_protocol_versions=supported_versions,
        )
        card_ref = str(normalized.get("card_ref") or "")
        if card_ref in by_ref:
            raise ValueError(f"external_agent_card_registry has duplicate card_ref: {card_ref}")
        by_ref[card_ref] = normalized
        normalized_cards.append(normalized)
    refs = {str(item).strip() for item in set(referenced_card_refs or set()) if str(item).strip()}
    missing = sorted(ref for ref in refs if ref.startswith(EXTERNAL_A2A_CARD_REF_PREFIX) and ref not in by_ref)
    if missing:
        raise ValueError(f"graph references unresolved external A2A card refs: {', '.join(missing)}")
    normalized_registry = {
        "schema_version": EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION,
        "supported_protocol_versions": supported_versions,
        "cards": normalized_cards,
    }
    generated_at = str(registry.get("generated_at") or registry.get("refreshed_at") or "").strip() or None
    stale_after_seconds = _optional_positive_int(registry.get("stale_after_seconds")) or DEFAULT_EXTERNAL_A2A_REGISTRY_STALE_AFTER_SECONDS
    freshness = _manifest_freshness(
        observed_at=generated_at,
        stale_after_seconds=stale_after_seconds,
        expires_at=registry.get("expires_at"),
    )
    normalized_registry["manifest"] = {
        "schema_version": EXTERNAL_A2A_MANIFEST_SCHEMA_VERSION,
        "digest": _stable_json_digest(normalized_registry),
        "freshness_status": freshness["freshness_status"],
        "observed_at": freshness["observed_at"],
        "stale_after_seconds": freshness["stale_after_seconds"],
        "expires_at": freshness["expires_at"],
        "verification_state": "verified" if freshness["freshness_status"] == "current" else "downgraded",
    }
    if generated_at:
        normalized_registry["generated_at"] = generated_at
    normalized_registry["stale_after_seconds"] = stale_after_seconds
    if freshness["expires_at"]:
        normalized_registry["expires_at"] = freshness["expires_at"]
    return normalized_registry


def build_external_a2a_gateway_snapshot(
    *,
    registry: dict[str, Any] | None,
    referenced_card_refs: set[str] | None = None,
) -> dict[str, Any] | None:
    refs = sorted(
        ref for ref in {str(item).strip() for item in set(referenced_card_refs or set()) if str(item).strip()}
        if ref.startswith(EXTERNAL_A2A_CARD_REF_PREFIX)
    )
    if not refs:
        return None
    normalized_registry = validate_external_a2a_agent_card_registry(registry, referenced_card_refs=set(refs))
    if not normalized_registry:
        raise ValueError("external A2A card refs require a validated registry snapshot.")
    registry_manifest = dict(normalized_registry.get("manifest") or {})
    registry_verification_state = str(registry_manifest.get("verification_state") or "downgraded").strip().lower()
    registry_freshness_status = str(registry_manifest.get("freshness_status") or "unknown").strip().lower()
    if registry_freshness_status == "expired":
        raise ValueError("external A2A registry manifest is expired; refresh the referenced Agent Card registry before compiling a live route.")
    by_ref = {
        str(item.get("card_ref") or "").strip(): dict(item)
        for item in list(normalized_registry.get("cards") or [])
        if isinstance(item, dict)
    }
    resolved_cards = [deepcopy(by_ref[ref]) for ref in refs]
    snapshot = {
        "schema_version": EXTERNAL_A2A_GATEWAY_SCHEMA_VERSION,
        "supported_protocol_versions": list(normalized_registry.get("supported_protocol_versions") or []),
        "supported_protocol_bindings": list(SUPPORTED_A2A_PROTOCOL_BINDINGS),
        "resolved_at": now_iso(),
        "referenced_card_refs": refs,
        "registry_snapshot": resolved_cards,
        "mapping_contract": {
            "message_adapter": "a2a_message<->AgentEnvelope",
            "task_adapter": "a2a_task<->AgentTask",
            "part_adapter": "a2a_part<->ContentPart",
            "artifact_adapter": "a2a_artifact<->ArtifactRef",
            "lifecycle_owner": "external_a2a_gateway.validate_external_a2a_task_transition",
            "durable_store_owner": "astrabridge_sidecar.protocol + durable_run_store",
        },
    }
    freshness = _manifest_freshness(
        observed_at=str(snapshot.get("resolved_at") or "").strip() or None,
        stale_after_seconds=DEFAULT_EXTERNAL_A2A_GATEWAY_STALE_AFTER_SECONDS,
        expires_at=None,
    )
    snapshot["manifest"] = {
        "schema_version": EXTERNAL_A2A_MANIFEST_SCHEMA_VERSION,
        "digest": _stable_json_digest(snapshot),
        "registry_digest": str(registry_manifest.get("digest") or "").strip() or None,
        "freshness_status": freshness["freshness_status"],
        "observed_at": freshness["observed_at"],
        "stale_after_seconds": freshness["stale_after_seconds"],
        "expires_at": freshness["expires_at"],
        "verification_state": "verified" if registry_verification_state == "verified" else "downgraded",
        "routable_card_refs": list(refs) if registry_verification_state == "verified" else [],
        "downgraded_card_refs": [] if registry_verification_state == "verified" else list(refs),
    }
    return snapshot


def validate_external_a2a_task_transition(previous_state: str | None, next_state: str) -> str:
    normalized_next = _normalize_task_state(next_state, field="external_a2a_task.next_state")
    normalized_previous = _normalize_task_state(previous_state, field="external_a2a_task.previous_state") if previous_state else None
    if normalized_previous is None:
        return normalized_next
    if normalized_previous == normalized_next and normalized_next in TERMINAL_A2A_TASK_STATES:
        raise ValueError(f"Ambiguous external A2A task transition: terminal state {normalized_next} cannot repeat.")
    if normalized_next not in _ALLOWED_A2A_STATE_TRANSITIONS.get(normalized_previous, set()):
        raise ValueError(f"Ambiguous external A2A task transition: {normalized_previous} -> {normalized_next} is not allowed.")
    return normalized_next


def a2a_artifact_to_artifact_ref(
    artifact: dict[str, Any],
    *,
    task_id: str,
    run_id: str,
    source_node_id: str,
) -> dict[str, Any]:
    data = _ensure_dict(artifact, "a2a_artifact")
    artifact_id = _require_non_empty_string(
        data.get("artifactId") or data.get("artifact_id"),
        field="a2a_artifact.artifactId",
    )
    media_type = _require_non_empty_string(
        data.get("mimeType") or data.get("mime_type"),
        field="a2a_artifact.mimeType",
    )
    uri = _normalize_external_artifact_uri(
        data.get("uri") or data.get("artifactUri") or data.get("artifact_uri"),
        field="a2a_artifact.uri",
    )
    size_bytes = int(data.get("sizeBytes") or data.get("size_bytes") or 0)
    if size_bytes < 0:
        raise ValueError("a2a_artifact.sizeBytes must be non-negative.")
    if size_bytes > MAX_A2A_ARTIFACT_BYTES:
        raise ValueError("a2a_artifact exceeds the AstraBridge external A2A artifact size limit.")
    internal_uri = f"ab-artifact://external-a2a/{artifact_id}"
    return validate_protocol_payload(
        "ArtifactRef",
        {
            "artifact_id": artifact_id,
            "artifact_uri": internal_uri,
            "media_type": media_type,
            "status": "ready",
            "lineage": {
                "task_id": task_id,
                "run_id": run_id,
                "source_node_id": source_node_id,
                "parent_artifact_ids": [],
            },
            "metadata": {
                "external_a2a": {
                    "source_uri": uri,
                    "size_bytes": size_bytes or None,
                    "sha256": str(data.get("sha256") or "").strip() or None,
                }
            },
        },
    )


def artifact_ref_to_a2a_artifact(artifact_ref: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_protocol_payload("ArtifactRef", artifact_ref)
    metadata = dict(normalized.get("metadata") or {})
    external = dict(metadata.get("external_a2a") or {})
    uri = str(external.get("source_uri") or normalized.get("artifact_uri") or "").strip()
    _normalize_external_artifact_uri(uri, field="artifact_ref.external_a2a.source_uri")
    return {
        "artifactId": str(normalized.get("artifact_id") or ""),
        "mimeType": str(normalized.get("media_type") or ""),
        "uri": uri,
        "sizeBytes": int(external.get("size_bytes") or 0) or None,
        "sha256": str(external.get("sha256") or "").strip() or None,
    }


def a2a_part_to_content_part(
    part: dict[str, Any],
    *,
    task_id: str,
    run_id: str,
    source_node_id: str,
) -> dict[str, Any]:
    data = _ensure_dict(part, "a2a_part")
    part_id = _require_non_empty_string(data.get("partId") or data.get("part_id"), field="a2a_part.partId")
    kind = _normalize_part_kind(data.get("kind"), field=f"a2a_part[{part_id}].kind")
    mime_type = _require_non_empty_string(data.get("mimeType") or data.get("mime_type"), field=f"a2a_part[{part_id}].mimeType")
    candidate: dict[str, Any] = {
        "part_id": part_id,
        "kind": kind,
        "mime_type": mime_type,
        "metadata": {"external_a2a": {"source_kind": kind}},
    }
    if kind == "text":
        candidate["text"] = _require_non_empty_string(data.get("text"), field=f"a2a_part[{part_id}].text")
    elif kind == "json":
        if "data" not in data:
            raise ValueError(f"a2a_part[{part_id}] json parts must include data.")
        candidate["data"] = deepcopy(data.get("data"))
    else:
        artifact = data.get("artifact")
        if not isinstance(artifact, dict):
            artifact = {
                "artifactId": data.get("artifactId") or data.get("artifact_id") or part_id,
                "mimeType": mime_type,
                "uri": data.get("uri") or data.get("artifactUri") or data.get("artifact_uri"),
                "sizeBytes": data.get("sizeBytes") or data.get("size_bytes"),
                "sha256": data.get("sha256"),
            }
        candidate["artifact"] = a2a_artifact_to_artifact_ref(
            artifact,
            task_id=task_id,
            run_id=run_id,
            source_node_id=source_node_id,
        )
    return validate_protocol_payload("ContentPart", candidate)


def content_part_to_a2a_part(content_part: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_protocol_payload("ContentPart", content_part)
    base = {
        "partId": str(normalized.get("part_id") or ""),
        "kind": str(normalized.get("kind") or ""),
        "mimeType": str(normalized.get("mime_type") or ""),
    }
    if isinstance(normalized.get("artifact"), dict):
        base["artifact"] = artifact_ref_to_a2a_artifact(dict(normalized.get("artifact") or {}))
        return base
    if "data" in normalized:
        base["data"] = deepcopy(normalized.get("data"))
        return base
    base["text"] = str(normalized.get("text") or "")
    return base


def a2a_message_to_agent_envelope(
    message: dict[str, Any],
    *,
    task_id: str,
    run_id: str,
    sender: dict[str, Any],
    recipient: dict[str, Any],
    envelope_kind: str = "handoff",
) -> dict[str, Any]:
    data = _ensure_dict(message, "a2a_message")
    message_id = _require_non_empty_string(data.get("messageId") or data.get("message_id"), field="a2a_message.messageId")
    parts = data.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("a2a_message.parts must be a non-empty list.")
    content = [
        a2a_part_to_content_part(
            dict(item),
            task_id=task_id,
            run_id=run_id,
            source_node_id=str(dict(sender).get("agent_id") or "external-a2a"),
        )
        for item in parts
        if isinstance(item, dict)
    ]
    if not content:
        raise ValueError("a2a_message.parts must contain at least one object part.")
    return validate_protocol_payload(
        "AgentEnvelope",
        {
            "envelope_id": f"a2a-envelope:{message_id}",
            "schema_version": SCHEMA_VERSION,
            "message_id": message_id,
            "task_id": task_id,
            "run_id": run_id,
            "sender": _normalize_peer_ref(sender, field="a2a_message.sender"),
            "recipient": _normalize_peer_ref(recipient, field="a2a_message.recipient"),
            "kind": envelope_kind,
            "content": content,
            "created_at": _require_non_empty_string(data.get("createdAt") or data.get("created_at") or now_iso(), field="a2a_message.createdAt"),
            "delivery": {
                "attempt": max(1, int(data.get("attempt") or 1)),
                "idempotency_key": str(data.get("idempotencyKey") or data.get("idempotency_key") or f"a2a-delivery:{message_id}"),
                "trace_id": str(data.get("traceId") or data.get("trace_id") or f"a2a-trace:{message_id}"),
                "sequence": max(0, int(data.get("sequence") or 0)),
            },
            "metadata": {
                "external_a2a": {
                    "role": str(data.get("role") or "").strip() or None,
                }
            },
            "security_policy": {},
        },
    )


def agent_envelope_to_a2a_message(envelope: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_protocol_payload("AgentEnvelope", envelope)
    return {
        "messageId": str(normalized.get("message_id") or ""),
        "role": str(dict(normalized.get("metadata") or {}).get("external_a2a", {}).get("role") or "agent"),
        "parts": [content_part_to_a2a_part(dict(item)) for item in list(normalized.get("content") or []) if isinstance(item, dict)],
        "createdAt": str(normalized.get("created_at") or ""),
        "sequence": int(dict(normalized.get("delivery") or {}).get("sequence") or 0),
    }


def a2a_task_to_agent_task(
    task: dict[str, Any],
    *,
    graph_id: str,
    node_id: str,
    run_id: str,
) -> dict[str, Any]:
    data = _ensure_dict(task, "a2a_task")
    task_id = _require_non_empty_string(data.get("id") or data.get("taskId") or data.get("task_id"), field="a2a_task.id")
    state = _normalize_task_state(data.get("state"), field="a2a_task.state")
    parts = list(data.get("input") or [])
    if not parts and isinstance(data.get("message"), dict):
        parts = list(dict(data.get("message") or {}).get("parts") or [])
    content = [
        a2a_part_to_content_part(
            dict(item),
            task_id=task_id,
            run_id=run_id,
            source_node_id=node_id,
        )
        for item in parts
        if isinstance(item, dict)
    ]
    return validate_protocol_payload(
        "AgentTask",
        {
            "task_id": task_id,
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "graph_id": graph_id,
            "node_id": node_id,
            "kind": "external_a2a_task",
            "input": content,
            "output_policy": {
                "external_a2a_state": state,
            },
            "security_policy": {},
            "created_at": _require_non_empty_string(data.get("createdAt") or data.get("created_at") or now_iso(), field="a2a_task.createdAt"),
            "metadata": {
                "external_a2a": {
                    "state": state,
                    "context_id": str(data.get("contextId") or data.get("context_id") or "").strip() or None,
                }
            },
        },
    )


def agent_task_to_a2a_task(agent_task: dict[str, Any], *, state: str) -> dict[str, Any]:
    normalized = validate_protocol_payload("AgentTask", agent_task)
    normalized_state = _normalize_task_state(state, field="agent_task.external_state")
    return {
        "id": str(normalized.get("task_id") or ""),
        "state": normalized_state,
        "input": [content_part_to_a2a_part(dict(item)) for item in list(normalized.get("input") or []) if isinstance(item, dict)],
        "createdAt": str(normalized.get("created_at") or ""),
    }


def _normalize_registry_entry(
    value: Any,
    *,
    index: int,
    supported_protocol_versions: list[str],
) -> dict[str, Any]:
    label = f"external_agent_card_registry.cards[{index}]"
    data = _ensure_dict(value, label)
    _require_fields(
        data,
        label,
        ("card_ref", "trust_level", "discovery", "public_agent_card", "public_agent_card_digest"),
    )
    card_ref = _require_non_empty_string(data.get("card_ref"), field=f"{label}.card_ref")
    if not _CARD_REF_RE.match(card_ref):
        raise ValueError(f"{label}.card_ref must start with {EXTERNAL_A2A_CARD_REF_PREFIX}")
    trust_level = _require_enum(data.get("trust_level"), field=f"{label}.trust_level", allowed=SUPPORTED_A2A_TRUST_LEVELS)
    discovery = _normalize_discovery(data.get("discovery"), field=f"{label}.discovery")
    public_card = _normalize_agent_card(
        data.get("public_agent_card"),
        field=f"{label}.public_agent_card",
        supported_protocol_versions=supported_protocol_versions,
    )
    public_digest = _require_non_empty_string(data.get("public_agent_card_digest"), field=f"{label}.public_agent_card_digest")
    computed_public_digest = _stable_json_digest(public_card)
    if public_digest != computed_public_digest:
        raise ValueError(f"{label}.public_agent_card_digest does not match the normalized Agent Card digest.")
    extended_card = None
    extended_digest = None
    if data.get("authenticated_extended_agent_card") is not None:
        if not bool(dict(public_card.get("capabilities") or {}).get("extendedAgentCard")):
            raise ValueError(f"{label} includes an authenticated_extended_agent_card but the public card does not declare capabilities.extendedAgentCard=true.")
        extended_card = _normalize_agent_card(
            data.get("authenticated_extended_agent_card"),
            field=f"{label}.authenticated_extended_agent_card",
            supported_protocol_versions=supported_protocol_versions,
        )
        extended_digest = _require_non_empty_string(
            data.get("authenticated_extended_agent_card_digest"),
            field=f"{label}.authenticated_extended_agent_card_digest",
        )
        computed_extended_digest = _stable_json_digest(extended_card)
        if extended_digest != computed_extended_digest:
            raise ValueError(f"{label}.authenticated_extended_agent_card_digest does not match the normalized extended Agent Card digest.")
    return {
        "card_ref": card_ref,
        "trust_level": trust_level,
        "discovery": discovery,
        "public_agent_card": public_card,
        "public_agent_card_digest": computed_public_digest,
        "authenticated_extended_agent_card": extended_card,
        "authenticated_extended_agent_card_digest": extended_digest,
    }


def _normalize_discovery(value: Any, *, field: str) -> dict[str, Any]:
    data = _ensure_dict(value, field)
    _require_fields(data, field, ("mode", "url"))
    mode = _require_enum(data.get("mode"), field=f"{field}.mode", allowed=("well_known", "direct"))
    url = _require_https_url(data.get("url"), field=f"{field}.url")
    if mode == "well_known" and not url.endswith("/.well-known/agent-card.json"):
        raise ValueError(f"{field}.url must point to /.well-known/agent-card.json for well_known discovery.")
    return {
        "mode": mode,
        "url": url,
    }


def _normalize_agent_card(value: Any, *, field: str, supported_protocol_versions: list[str]) -> dict[str, Any]:
    data = _ensure_dict(value, field)
    _require_fields(
        data,
        field,
        ("protocolVersion", "name", "description", "url", "version", "capabilities", "defaultInputModes", "defaultOutputModes", "skills"),
    )
    protocol_version = _normalize_protocol_version(data.get("protocolVersion"), field=f"{field}.protocolVersion")
    if protocol_version not in supported_protocol_versions:
        raise ValueError(f"{field}.protocolVersion {protocol_version} is outside the registry's supported A2A version window.")
    name = _require_non_empty_string(data.get("name"), field=f"{field}.name")
    description = _require_non_empty_string(data.get("description"), field=f"{field}.description")
    url = _require_https_url(data.get("url"), field=f"{field}.url")
    version = _require_non_empty_string(data.get("version"), field=f"{field}.version")
    capabilities = _normalize_capabilities(data.get("capabilities"), field=f"{field}.capabilities")
    supported_interfaces = _normalize_supported_interfaces(data, field=field, default_protocol_version=protocol_version)
    security_schemes = _normalize_security_schemes(data.get("securitySchemes"), field=f"{field}.securitySchemes")
    security = _normalize_security_requirements(
        data.get("security"),
        field=f"{field}.security",
        security_schemes=security_schemes,
    )
    default_input_modes = _normalize_string_list(
        data.get("defaultInputModes"),
        field=f"{field}.defaultInputModes",
        required=True,
    )
    default_output_modes = _normalize_string_list(
        data.get("defaultOutputModes"),
        field=f"{field}.defaultOutputModes",
        required=True,
    )
    skills = data.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError(f"{field}.skills must be a non-empty list.")
    normalized_skills = [_normalize_skill(item, field=f"{field}.skills[{index}]") for index, item in enumerate(skills)]
    normalized = {
        "protocolVersion": protocol_version,
        "name": name,
        "description": description,
        "url": url,
        "version": version,
        "supportedInterfaces": supported_interfaces,
        "capabilities": capabilities,
        "defaultInputModes": default_input_modes,
        "defaultOutputModes": default_output_modes,
        "skills": normalized_skills,
    }
    if security_schemes:
        normalized["securitySchemes"] = security_schemes
    if security:
        normalized["security"] = security
    return normalized


def _normalize_supported_interfaces(value: dict[str, Any], *, field: str, default_protocol_version: str) -> list[dict[str, Any]]:
    raw = value.get("supportedInterfaces")
    if raw is None:
        raw = []
        preferred_transport = str(value.get("preferredTransport") or "").strip()
        if preferred_transport:
            raw.append(
                {
                    "url": value.get("url"),
                    "transport": preferred_transport,
                    "protocolVersion": default_protocol_version,
                }
            )
        for item in list(value.get("additionalInterfaces") or []):
            raw.append(item)
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{field}.supportedInterfaces must be a non-empty list.")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        entry = _ensure_dict(item, f"{field}.supportedInterfaces[{index}]")
        url = _require_https_url(entry.get("url"), field=f"{field}.supportedInterfaces[{index}].url")
        binding = _require_non_empty_string(
            entry.get("protocolBinding") or entry.get("protocol_binding") or entry.get("transport"),
            field=f"{field}.supportedInterfaces[{index}].protocolBinding",
        ).upper()
        if binding not in SUPPORTED_A2A_PROTOCOL_BINDINGS:
            raise ValueError(f"{field}.supportedInterfaces[{index}] declares unsupported protocol binding {binding}.")
        protocol_version = _normalize_protocol_version(
            entry.get("protocolVersion") or entry.get("protocol_version") or default_protocol_version,
            field=f"{field}.supportedInterfaces[{index}].protocolVersion",
        )
        tenant = str(entry.get("tenant") or "").strip() or None
        normalized_entry = {
            "url": url,
            "protocolBinding": binding,
            "protocolVersion": protocol_version,
        }
        if tenant:
            normalized_entry["tenant"] = tenant
        normalized.append(normalized_entry)
    return normalized


def _normalize_capabilities(value: Any, *, field: str) -> dict[str, Any]:
    data = _ensure_dict(value, field)
    return {
        "streaming": bool(data.get("streaming")),
        "pushNotifications": bool(data.get("pushNotifications")),
        "extendedAgentCard": bool(data.get("extendedAgentCard")),
    }


def _normalize_security_schemes(value: Any, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    data = _ensure_dict(value, field)
    normalized: dict[str, Any] = {}
    for scheme_name, scheme_payload in data.items():
        clean_name = _require_non_empty_string(scheme_name, field=f"{field}.key")
        payload = _ensure_dict(scheme_payload, f"{field}[{clean_name}]")
        keys = [str(item).strip() for item in payload.keys() if str(item).strip()]
        if len(keys) != 1:
            raise ValueError(f"{field}[{clean_name}] must declare exactly one security scheme variant.")
        variant = keys[0]
        if variant not in SUPPORTED_A2A_SECURITY_SCHEME_KEYS:
            raise ValueError(f"{field}[{clean_name}] declares unsupported security scheme {variant}.")
        details = _ensure_dict(payload.get(variant), f"{field}[{clean_name}].{variant}")
        if variant == "apiKeySecurityScheme":
            _require_fields(details, f"{field}[{clean_name}].{variant}", ("name", "in"))
            _require_non_empty_string(details.get("name"), field=f"{field}[{clean_name}].{variant}.name")
            _require_enum(details.get("in"), field=f"{field}[{clean_name}].{variant}.in", allowed=("header", "query"))
        elif variant == "oauth2ClientCredentialsSecurityScheme":
            _require_fields(details, f"{field}[{clean_name}].{variant}", ("tokenUrl",))
            _require_https_url(details.get("tokenUrl"), field=f"{field}[{clean_name}].{variant}.tokenUrl")
        elif variant == "openIdConnectSecurityScheme":
            _require_fields(details, f"{field}[{clean_name}].{variant}", ("openIdConnectUrl",))
            _require_https_url(details.get("openIdConnectUrl"), field=f"{field}[{clean_name}].{variant}.openIdConnectUrl")
        normalized[clean_name] = {variant: deepcopy(details)}
    return normalized


def _normalize_security_requirements(value: Any, *, field: str, security_schemes: dict[str, Any]) -> list[dict[str, list[str]]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list when present.")
    normalized: list[dict[str, list[str]]] = []
    for index, item in enumerate(value):
        requirement = _ensure_dict(item, f"{field}[{index}]")
        if not requirement:
            raise ValueError(f"{field}[{index}] must not be empty.")
        normalized_requirement: dict[str, list[str]] = {}
        for scheme_name, scopes in requirement.items():
            clean_name = _require_non_empty_string(scheme_name, field=f"{field}[{index}].scheme")
            if clean_name not in security_schemes:
                raise ValueError(f"{field}[{index}] references unknown security scheme {clean_name}.")
            scope_list = _normalize_string_list(scopes, field=f"{field}[{index}][{clean_name}]", required=False)
            normalized_requirement[clean_name] = scope_list
        normalized.append(normalized_requirement)
    return normalized


def _normalize_skill(value: Any, *, field: str) -> dict[str, Any]:
    data = _ensure_dict(value, field)
    _require_fields(data, field, ("id", "name", "description"))
    skill_id = _require_non_empty_string(data.get("id"), field=f"{field}.id")
    name = _require_non_empty_string(data.get("name"), field=f"{field}.name")
    description = _require_non_empty_string(data.get("description"), field=f"{field}.description")
    tags = _normalize_string_list(data.get("tags"), field=f"{field}.tags", required=False)
    examples = _normalize_string_list(data.get("examples"), field=f"{field}.examples", required=False)
    normalized = {
        "id": skill_id,
        "name": name,
        "description": description,
    }
    if tags:
        normalized["tags"] = tags
    if examples:
        normalized["examples"] = examples
    return normalized


def _normalize_peer_ref(value: Any, *, field: str) -> dict[str, Any]:
    data = _ensure_dict(value, field)
    normalized = {
        "agent_id": _require_non_empty_string(data.get("agent_id") or data.get("agentId"), field=f"{field}.agent_id"),
        "provider_id": _require_non_empty_string(data.get("provider_id") or data.get("providerId"), field=f"{field}.provider_id"),
    }
    model_id = str(data.get("model_id") or data.get("modelId") or "").strip()
    lane_id = str(data.get("lane_id") or data.get("laneId") or "").strip()
    if model_id:
        normalized["model_id"] = model_id
    if lane_id:
        normalized["lane_id"] = lane_id
    return normalized


def _normalize_part_kind(value: Any, *, field: str) -> str:
    clean = _require_non_empty_string(value, field=field)
    if clean not in SUPPORTED_A2A_CONTENT_KINDS:
        raise ValueError(f"{field} must be one of {', '.join(sorted(SUPPORTED_A2A_CONTENT_KINDS))}.")
    return clean


def _normalize_protocol_version(value: Any, *, field: str) -> str:
    clean = _normalize_protocol_version_text(value, field=field)
    if clean not in SUPPORTED_A2A_PROTOCOL_VERSIONS:
        raise ValueError(
            f"{field} declares unsupported A2A protocol version {clean}; AstraBridge currently supports {', '.join(SUPPORTED_A2A_PROTOCOL_VERSIONS)}."
        )
    return clean


def _normalize_version_list(value: Any, *, field: str) -> list[str]:
    versions = _normalize_string_list(value, field=field, required=True)
    normalized = [_normalize_protocol_version(item, field=field) for item in versions]
    deduped: list[str] = []
    for item in normalized:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _normalize_task_state(value: Any, *, field: str) -> str:
    clean = _require_non_empty_string(value, field=field).upper()
    if clean not in SUPPORTED_A2A_TASK_STATES:
        raise ValueError(
            f"{field} must be one of {', '.join(SUPPORTED_A2A_TASK_STATES)}."
        )
    return clean


def _normalize_protocol_version_text(value: Any, *, field: str) -> str:
    clean = _require_non_empty_string(value, field=field)
    if not re.fullmatch(r"\d+\.\d+", clean):
        raise ValueError(f"{field} must be a major.minor A2A protocol version.")
    return clean


def _normalize_protocol_binding_text(value: Any, *, field: str) -> str:
    return _require_non_empty_string(value, field=field).upper()


def _normalize_external_artifact_uri(value: Any, *, field: str) -> str:
    uri = _require_non_empty_string(value, field=field)
    if len(uri) > MAX_A2A_ARTIFACT_URI_LENGTH:
        raise ValueError(f"{field} exceeds the AstraBridge external A2A URI length limit.")
    parsed = urlparse(uri)
    scheme = str(parsed.scheme or "").strip().lower()
    if scheme in UNSAFE_A2A_ARTIFACT_URI_SCHEMES:
        raise ValueError(f"{field} uses an unsafe URI scheme: {scheme}.")
    if scheme not in SUPPORTED_A2A_ARTIFACT_URI_SCHEMES:
        raise ValueError(f"{field} uses unsupported URI scheme {scheme}.")
    if scheme in {"workspace", "ab-artifact"}:
        raw_path = parsed.netloc + parsed.path
        normalized_path = str(PurePosixPath(raw_path))
        if normalized_path.startswith("..") or "/../" in normalized_path:
            raise ValueError(f"{field} contains path traversal.")
    return uri


def _require_https_url(value: Any, *, field: str) -> str:
    clean = _require_non_empty_string(value, field=field)
    parsed = urlparse(clean)
    if str(parsed.scheme or "").strip().lower() != "https":
        raise ValueError(f"{field} must be an https URL.")
    if not str(parsed.netloc or "").strip():
        raise ValueError(f"{field} must be an absolute URL.")
    return clean


def _stable_json_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _ensure_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a dict.")
    return dict(value)


def _require_fields(data: dict[str, Any], label: str, fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if field not in data]
    if missing:
        raise ValueError(f"{label} is missing required field(s): {', '.join(missing)}")


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _require_enum(value: Any, *, field: str, allowed: tuple[str, ...] | set[str]) -> str:
    clean = _require_non_empty_string(value, field=field)
    allowed_values = tuple(sorted(str(item) for item in allowed))
    if clean not in allowed_values:
        raise ValueError(f"{field} must be one of {', '.join(allowed_values)}.")
    return clean


def _normalize_string_list(value: Any, *, field: str, required: bool) -> list[str]:
    if value is None:
        if required:
            raise ValueError(f"{field} must be a non-empty list of strings.")
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of strings.")
    cleaned = [_require_non_empty_string(item, field=field) for item in value]
    if required and not cleaned:
        raise ValueError(f"{field} must be a non-empty list of strings.")
    return cleaned


class ExternalA2AConflictError(RuntimeError):
    """Raised when an A2A idempotency key is reused with a different payload."""


class ExternalA2ANotFoundError(RuntimeError):
    """Raised when a requested A2A task journal record does not exist."""


class ExternalA2ARequestRejectedError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code or "external_a2a_request_rejected")
        self.status_code = int(status_code)
        self.detail = deepcopy(detail or {})

    def response_payload(self) -> dict[str, Any]:
        payload = {
            "ok": False,
            "error": str(self),
            "code": self.code,
        }
        if self.detail:
            payload["detail"] = deepcopy(self.detail)
        return payload


class ExternalA2ATaskExecutor(Protocol):
    def start(
        self,
        task_record: dict[str, Any],
        emit: Callable[..., dict[str, Any]],
    ) -> dict[str, Any] | None: ...

    def cancel(
        self,
        task_record: dict[str, Any],
        emit: Callable[..., dict[str, Any]],
    ) -> dict[str, Any] | None: ...


def build_local_external_a2a_agent_card(
    *,
    base_url: str,
    version: str = "2026.07.17",
    name: str = "AstraBridge External A2A Gateway",
) -> dict[str, Any]:
    clean_base_url = str(base_url or "").strip().rstrip("/")
    if not clean_base_url:
        raise ValueError("base_url is required.")
    parsed = urlparse(clean_base_url)
    if str(parsed.scheme or "").strip().lower() not in {"http", "https"}:
        raise ValueError("base_url must use http or https.")
    if not str(parsed.netloc or "").strip():
        raise ValueError("base_url must be absolute.")
    card = {
        "protocolVersion": "1.0",
        "name": name,
        "description": "Accepts external A2A tasks, streams task updates, and bridges supported work into AstraBridge runtime lanes.",
        "url": f"{clean_base_url}/a2a",
        "version": version,
        "supportedInterfaces": [
            {
                "url": f"{clean_base_url}/a2a",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json", "application/pdf"],
        "skills": [
            {
                "id": "astrabridge-task-bridge",
                "name": "AstraBridge Task Bridge",
                "description": "Bridges external A2A tasks into AstraBridge execution lanes and returns streamed task updates plus typed artifacts.",
                "tags": ["a2a", "agent", "workflow", "gateway"],
                "examples": [
                    "Send a task, stream progress, cancel it, and retrieve artifacts through the AstraBridge A2A gateway."
                ],
            }
        ],
        "x-astrabridge": {
            "supportedProtocolVersions": list(SUPPORTED_A2A_PROTOCOL_VERSIONS),
            "supportedProtocolBindings": list(SUPPORTED_A2A_PROTOCOL_BINDINGS),
            "supportedExtensions": list(SUPPORTED_A2A_EXTENSIONS),
        },
    }
    return card


class FakeExternalA2ATaskExecutor:
    def __init__(self, *, default_delay_sec: float = 0.05) -> None:
        self._default_delay_sec = max(0.0, float(default_delay_sec))
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    def start(
        self,
        task_record: dict[str, Any],
        emit: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        task_id = str(task_record.get("task_id") or "")
        behavior = dict(dict(task_record.get("metadata") or {}).get("external_a2a", {}).get("test_behavior") or {})
        delay_sec = max(0.0, float(behavior.get("delay_sec") or self._default_delay_sec))
        response_text = str(behavior.get("response_text") or "AstraBridge external A2A task completed.").strip()
        artifact_uri = str(behavior.get("artifact_uri") or "https://astrabridge.example.invalid/artifacts/result.txt").strip()
        artifact_mime_type = str(behavior.get("artifact_mime_type") or "text/plain").strip() or "text/plain"
        artifact_kind = str(behavior.get("artifact_kind") or "document").strip() or "document"
        include_artifact = bool(behavior.get("include_artifact", True))
        should_fail = bool(behavior.get("fail"))
        emit(
            next_state="TASK_STATE_WORKING",
            event_type="task_started",
            execution={"executor": "fake", "scheduled_at": now_iso()},
        )

        def _complete() -> None:
            time.sleep(delay_sec)
            with self._lock:
                if task_id in self._cancelled:
                    return
            if should_fail:
                emit(
                    next_state="TASK_STATE_FAILED",
                    event_type="task_failed",
                    error=str(behavior.get("error") or "Remote executor reported a controlled failure."),
                    execution={"executor": "fake", "completed_at": now_iso(), "result": "failed"},
                )
                return
            message_parts: list[dict[str, Any]] = [
                {
                    "partId": f"{task_id}-text",
                    "kind": "text",
                    "mimeType": "text/plain",
                    "text": response_text,
                }
            ]
            artifacts: list[dict[str, Any]] = []
            if include_artifact:
                artifact = {
                    "artifactId": f"{task_id}-artifact",
                    "mimeType": artifact_mime_type,
                    "uri": artifact_uri,
                    "sizeBytes": int(behavior.get("artifact_size_bytes") or 128),
                }
                artifacts.append(artifact)
                message_parts.append(
                    {
                        "partId": f"{task_id}-artifact-part",
                        "kind": artifact_kind,
                        "mimeType": artifact_mime_type,
                        "artifact": artifact,
                    }
                )
            emit(
                next_state="TASK_STATE_COMPLETED",
                event_type="task_completed",
                message={
                    "messageId": f"{task_id}-message",
                    "role": "agent",
                    "createdAt": now_iso(),
                    "parts": message_parts,
                },
                artifacts=artifacts,
                execution={"executor": "fake", "completed_at": now_iso(), "result": "completed"},
            )

        threading.Thread(target=_complete, name=f"a2a-fake-{task_id}", daemon=True).start()
        return {"executor": "fake", "accepted": True, "task_id": task_id}

    def cancel(
        self,
        task_record: dict[str, Any],
        emit: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        task_id = str(task_record.get("task_id") or "")
        with self._lock:
            self._cancelled.add(task_id)
        emit(
            next_state="TASK_STATE_CANCELED",
            event_type="task_cancelled",
            execution={"executor": "fake", "cancelled_at": now_iso()},
        )
        return {"executor": "fake", "accepted": True, "task_id": task_id}


class RuntimeExternalA2ATaskExecutor:
    def __init__(
        self,
        *,
        runtime: Any,
        profile_resolver: Callable[[str | None], dict[str, Any]],
        thread_id_resolver: Callable[[dict[str, Any]], str | None],
    ) -> None:
        self._runtime = runtime
        self._profile_resolver = profile_resolver
        self._thread_id_resolver = thread_id_resolver

    def start(
        self,
        task_record: dict[str, Any],
        emit: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        external_meta = dict(dict(task_record.get("metadata") or {}).get("external_a2a") or {})
        profile = self._profile_resolver(str(external_meta.get("profile_id") or "").strip() or None)
        thread_id = str(external_meta.get("thread_id") or self._thread_id_resolver(task_record) or "").strip()
        if not thread_id:
            raise ValueError("external_a2a runtime bridge requires a target thread_id.")
        text = _text_from_a2a_parts(list(task_record.get("input_parts") or []))
        if not text:
            raise ValueError("external_a2a runtime bridge requires at least one text or json input part.")
        response = self._runtime.start_turn(
            profile,
            thread_id=thread_id,
            text=text,
            attachments=[],
            model=str(external_meta.get("model") or "").strip() or None,
            effort=str(external_meta.get("effort") or "").strip() or None,
            permission_mode=str(external_meta.get("permission_mode") or "auto"),
            collaboration_mode=str(external_meta.get("collaboration_mode") or "").strip() or None,
            context_mode=str(external_meta.get("context_mode") or "").strip() or None,
            execution_policy=str(external_meta.get("execution_policy") or "").strip() or None,
        )
        thread_payload = dict(response.get("thread") or {})
        turn_payload = dict(response.get("turn") or {})
        execution = {
            "executor": "runtime",
            "thread_id": str(thread_payload.get("id") or thread_id),
            "turn_id": str(turn_payload.get("id") or ""),
            "profile_id": str(profile.get("profile_id") or ""),
            "provider_id": str(profile.get("provider_id") or ""),
            "model": str(external_meta.get("model") or profile.get("model") or ""),
            "permission_mode": str(external_meta.get("permission_mode") or "auto"),
            "started_at": now_iso(),
        }
        emit(
            next_state="TASK_STATE_WORKING",
            event_type="task_started",
            execution=execution,
        )
        return execution

    def cancel(
        self,
        task_record: dict[str, Any],
        emit: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        execution = dict(task_record.get("execution") or {})
        external_meta = dict(dict(task_record.get("metadata") or {}).get("external_a2a") or {})
        profile = self._profile_resolver(str(external_meta.get("profile_id") or "").strip() or None)
        thread_id = str(execution.get("thread_id") or external_meta.get("thread_id") or self._thread_id_resolver(task_record) or "").strip()
        turn_id = str(execution.get("turn_id") or "").strip()
        if not thread_id or not turn_id:
            raise ValueError("external_a2a runtime cancellation requires a started thread_id and turn_id.")
        interrupt = self._runtime.interrupt_turn(profile, thread_id, turn_id)
        emit(
            next_state="TASK_STATE_CANCELED",
            event_type="task_cancelled",
            execution={**execution, "interrupt": deepcopy(interrupt), "cancelled_at": now_iso()},
        )
        return {"interrupt": interrupt, "thread_id": thread_id, "turn_id": turn_id}


class ExternalA2AGatewayService:
    def __init__(
        self,
        *,
        executor: ExternalA2ATaskExecutor,
        event_recorder: Callable[[str, dict[str, Any]], None] | None = None,
        product_version: str = "2026.07.17",
        gateway_name: str = "AstraBridge External A2A Gateway",
        trusted_peer_policies: dict[str, dict[str, Any]] | None = None,
        signature_keys: dict[str, str] | None = None,
        require_trusted_peers: bool = False,
        default_audience: str = "astrabridge-gateway",
        local_workspace_id: str | None = None,
        max_request_bytes: int = MAX_A2A_REQUEST_BYTES,
        replay_window_seconds: int = DEFAULT_A2A_REPLAY_WINDOW_SECONDS,
        clock_skew_seconds: int = DEFAULT_A2A_CLOCK_SKEW_SECONDS,
        supported_extensions: tuple[str, ...] = SUPPORTED_A2A_EXTENSIONS,
    ) -> None:
        self._executor = executor
        self._event_recorder = event_recorder
        self._product_version = str(product_version or "2026.07.17")
        self._gateway_name = str(gateway_name or "AstraBridge External A2A Gateway")
        self._trusted_peer_policies = {
            str(issuer).strip(): deepcopy(dict(policy))
            for issuer, policy in dict(trusted_peer_policies or {}).items()
            if str(issuer or "").strip() and isinstance(policy, dict)
        }
        self._signature_keys = {
            str(key_id).strip(): str(secret)
            for key_id, secret in dict(signature_keys or {}).items()
            if str(key_id or "").strip() and str(secret or "")
        }
        self._require_trusted_peers = bool(require_trusted_peers)
        self._default_audience = str(default_audience or "astrabridge-gateway").strip() or "astrabridge-gateway"
        self._local_workspace_id = str(local_workspace_id or "").strip() or None
        self._max_request_bytes = max(1024, int(max_request_bytes or MAX_A2A_REQUEST_BYTES))
        self._replay_window_seconds = max(1, int(replay_window_seconds or DEFAULT_A2A_REPLAY_WINDOW_SECONDS))
        self._clock_skew_seconds = max(0, int(clock_skew_seconds or DEFAULT_A2A_CLOCK_SKEW_SECONDS))
        self._supported_extensions = tuple(
            ext for ext in (_require_non_empty_string(item, field="external_a2a_gateway.supported_extensions") for item in supported_extensions)
            if ext
        ) or SUPPORTED_A2A_EXTENSIONS
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}
        self._idempotency: dict[str, dict[str, str]] = {}
        self._seen_request_ids: dict[tuple[str, str], dict[str, Any]] = {}

    def local_agent_card(self, *, base_url: str) -> dict[str, Any]:
        return build_local_external_a2a_agent_card(
            base_url=base_url,
            version=self._product_version,
            name=self._gateway_name,
        )

    def submit_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = _ensure_dict(payload, "external_a2a_gateway.submit_task")
        request_size_bytes = _json_size_bytes(data)
        if request_size_bytes > self._max_request_bytes:
            raise ExternalA2ARequestRejectedError(
                "external A2A request exceeds the AstraBridge gateway request size limit.",
                code="request_too_large",
                status_code=413,
                detail={
                    "request_size_bytes": request_size_bytes,
                    "max_request_bytes": self._max_request_bytes,
                },
            )
        task_payload = data.get("task")
        if not isinstance(task_payload, dict):
            task_payload = data
        normalized_task_payload = self._normalize_submission_task(task_payload)
        task_id = str(normalized_task_payload.get("id") or "")
        idempotency_key = _require_non_empty_string(
            data.get("idempotencyKey") or data.get("idempotency_key") or f"a2a-idempotency:{task_id}",
            field="external_a2a_gateway.submit_task.idempotencyKey",
        )
        request_digest = _stable_json_digest(
            {
                key: deepcopy(value)
                for key, value in normalized_task_payload.items()
                if key not in {"createdAt", "created_at"}
            }
        )
        input_parts = [deepcopy(item) for item in list(normalized_task_payload.get("input") or []) if isinstance(item, dict)]
        metadata = self._normalize_gateway_metadata(data.get("metadata"))
        external_meta = dict(metadata.get("external_a2a") or {})
        negotiation = self._negotiate_request(external_meta)
        trust_decision = self._evaluate_peer_policy(external_meta)
        replay_record = self._validate_replay_window(external_meta, request_digest=request_digest)
        metadata = self._augment_gateway_metadata(
            metadata,
            negotiation=negotiation,
            trust_decision=trust_decision,
            request_size_bytes=request_size_bytes,
            replay_record=replay_record,
        )
        task_record = {
            "task_id": task_id,
            "context_id": str(normalized_task_payload.get("contextId") or normalized_task_payload.get("context_id") or f"context-{task_id}"),
            "state": "TASK_STATE_SUBMITTED",
            "created_at": str(normalized_task_payload.get("createdAt") or now_iso()),
            "updated_at": now_iso(),
            "request_digest": request_digest,
            "idempotency_key": idempotency_key,
            "input_parts": input_parts,
            "messages": [],
            "artifacts": [],
            "events": [],
            "cursor": 0,
            "execution": {},
            "metadata": metadata,
            "agent_task": a2a_task_to_agent_task(
                normalized_task_payload,
                graph_id="external-a2a-gateway",
                node_id="external-a2a-bridge",
                run_id=f"external-a2a-run:{task_id}",
            ),
            "error": None,
        }
        with self._lock:
            existing = self._idempotency.get(idempotency_key)
            if existing is not None:
                existing_task = self._tasks.get(existing.get("task_id") or "")
                if existing_task is None:
                    raise ExternalA2ANotFoundError("external A2A idempotency journal is inconsistent.")
                if str(existing.get("request_digest") or "") != request_digest:
                    raise ExternalA2AConflictError("external A2A idempotency key was reused with a different payload.")
                return {"task": self._task_view_locked(existing_task), "duplicate": True}
            if task_id in self._tasks and str(self._tasks[task_id].get("request_digest") or "") != request_digest:
                raise ExternalA2AConflictError(f"external A2A task id {task_id} already exists with a different payload.")
            self._append_event_locked(
                task_record,
                event_type="task_submitted",
                state="TASK_STATE_SUBMITTED",
            )
            self._tasks[task_id] = task_record
            self._idempotency[idempotency_key] = {"task_id": task_id, "request_digest": request_digest}
            request_id = str(dict(dict(metadata.get("external_a2a") or {}).get("replay") or {}).get("request_id") or "").strip()
            issuer = str(dict(dict(metadata.get("external_a2a") or {}).get("trust_decision") or {}).get("issuer") or "").strip() or "anonymous"
            if request_id:
                self._seen_request_ids[(issuer, request_id)] = {
                    "request_digest": request_digest,
                    "accepted_at": now_iso(),
                }
            task_view = self._task_view_locked(task_record)
        self._record_gateway_event("external_a2a_task_submitted", {"task_id": task_id, "state": "TASK_STATE_SUBMITTED"})
        self._run_executor_start(task_id)
        return {"task": task_view, "duplicate": False}

    def get_task(self, task_id: str) -> dict[str, Any]:
        clean_task_id = _require_non_empty_string(task_id, field="external_a2a_gateway.get_task.task_id")
        with self._lock:
            record = self._tasks.get(clean_task_id)
            if record is None:
                raise ExternalA2ANotFoundError(f"external A2A task {clean_task_id} was not found.")
            return {"task": self._task_view_locked(record)}

    def cancel_task(self, task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_task_id = _require_non_empty_string(task_id, field="external_a2a_gateway.cancel_task.task_id")
        with self._lock:
            record = self._tasks.get(clean_task_id)
            if record is None:
                raise ExternalA2ANotFoundError(f"external A2A task {clean_task_id} was not found.")
            current_state = str(record.get("state") or "")
            if current_state in TERMINAL_A2A_TASK_STATES:
                return {"task": self._task_view_locked(record), "already_terminal": True}
        result = self._executor.cancel(
            self._task_snapshot(clean_task_id),
            lambda **kwargs: self._apply_task_update(clean_task_id, **kwargs),
        )
        self._record_gateway_event(
            "external_a2a_task_cancel_requested",
            {"task_id": clean_task_id, "payload": self._normalize_gateway_metadata(payload or {}), "result": deepcopy(result or {})},
        )
        return {"task": self.get_task(clean_task_id)["task"], "cancel": deepcopy(result or {})}

    def task_events(self, task_id: str, *, after: int = 0, limit: int | None = None) -> dict[str, Any]:
        clean_task_id = _require_non_empty_string(task_id, field="external_a2a_gateway.task_events.task_id")
        with self._lock:
            record = self._tasks.get(clean_task_id)
            if record is None:
                raise ExternalA2ANotFoundError(f"external A2A task {clean_task_id} was not found.")
            events = [deepcopy(item) for item in list(record.get("events") or []) if int(item.get("cursor") or 0) > max(0, int(after))]
            if limit is not None:
                events = events[: max(0, int(limit))]
            return {
                "task_id": clean_task_id,
                "cursor": int(record.get("cursor") or 0),
                "events": events,
                "terminal": str(record.get("state") or "") in TERMINAL_A2A_TASK_STATES,
            }

    def is_terminal(self, task_id: str) -> bool:
        with self._lock:
            record = self._tasks.get(str(task_id or "").strip())
            return bool(record and str(record.get("state") or "") in TERMINAL_A2A_TASK_STATES)

    def _run_executor_start(self, task_id: str) -> None:
        def _runner() -> None:
            snapshot = self._task_snapshot(task_id)
            try:
                execution = self._executor.start(
                    snapshot,
                    lambda **kwargs: self._apply_task_update(task_id, **kwargs),
                )
                if execution:
                    self._apply_task_update(
                        task_id,
                        event_type="task_execution_bound",
                        execution=deepcopy(execution),
                    )
            except Exception as exc:  # noqa: BLE001
                self._apply_task_update(
                    task_id,
                    next_state="TASK_STATE_FAILED",
                    event_type="task_failed",
                    error=str(exc)[:500],
                    execution={"executor_error": type(exc).__name__},
                )

        threading.Thread(target=_runner, name=f"a2a-start-{task_id}", daemon=True).start()

    def _task_snapshot(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise ExternalA2ANotFoundError(f"external A2A task {task_id} was not found.")
            return deepcopy(record)

    def _apply_task_update(
        self,
        task_id: str,
        *,
        next_state: str | None = None,
        event_type: str = "task_updated",
        message: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        error: str | None = None,
        execution: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            record = self._tasks.get(task_id)
            if record is None:
                raise ExternalA2ANotFoundError(f"external A2A task {task_id} was not found.")
            previous_state = str(record.get("state") or "")
            resolved_state = previous_state
            if next_state is not None:
                resolved_state = validate_external_a2a_task_transition(previous_state, next_state)
                record["state"] = resolved_state
            if message is not None:
                sanitized_message = self._sanitize_message(record, message)
                record.setdefault("messages", []).append(sanitized_message)
            sanitized_artifacts = self._sanitize_artifacts(record, artifacts or [])
            if sanitized_artifacts:
                existing_artifact_ids = {str(item.get("artifactId") or "") for item in list(record.get("artifacts") or []) if isinstance(item, dict)}
                for artifact in sanitized_artifacts:
                    artifact_id = str(artifact.get("artifactId") or "")
                    if artifact_id not in existing_artifact_ids:
                        record.setdefault("artifacts", []).append(artifact)
                        existing_artifact_ids.add(artifact_id)
            if error is not None:
                record["error"] = str(error).strip() or None
            if execution:
                record["execution"] = {**dict(record.get("execution") or {}), **deepcopy(execution)}
            if metadata:
                normalized_metadata = self._normalize_gateway_metadata(metadata)
                record["metadata"] = {
                    **dict(record.get("metadata") or {}),
                    **normalized_metadata,
                }
            record["updated_at"] = now_iso()
            event = self._append_event_locked(
                record,
                event_type=event_type,
                state=resolved_state,
                message=record.get("messages", [])[-1] if message is not None and list(record.get("messages") or []) else None,
                artifacts=sanitized_artifacts,
                error=record.get("error"),
                execution=record.get("execution"),
            )
            task_view = self._task_view_locked(record)
        self._record_gateway_event(
            f"external_a2a_{event_type}",
            {
                "task_id": task_id,
                "state": resolved_state,
                "cursor": int(event.get("cursor") or 0),
            },
        )
        return task_view

    def _append_event_locked(
        self,
        record: dict[str, Any],
        *,
        event_type: str,
        state: str,
        message: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        error: str | None = None,
        execution: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record["cursor"] = int(record.get("cursor") or 0) + 1
        event = {
            "cursor": int(record["cursor"]),
            "taskId": str(record.get("task_id") or ""),
            "type": str(event_type or "task_updated"),
            "state": str(state or record.get("state") or ""),
            "timestamp": now_iso(),
        }
        if message is not None:
            event["message"] = deepcopy(message)
        if artifacts:
            event["artifacts"] = deepcopy(artifacts)
        if error:
            event["error"] = str(error)
        if execution:
            event["execution"] = deepcopy(execution)
        record.setdefault("events", []).append(event)
        return event

    def _sanitize_message(self, record: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
        envelope = a2a_message_to_agent_envelope(
            message,
            task_id=str(record.get("task_id") or ""),
            run_id=str(dict(record.get("agent_task") or {}).get("run_id") or ""),
            sender={"agent_id": "external-a2a-peer", "provider_id": "external-a2a"},
            recipient={"agent_id": "astrabridge-gateway", "provider_id": "astrabridge"},
        )
        sanitized = agent_envelope_to_a2a_message(envelope)
        for part in list(sanitized.get("parts") or []):
            artifact = dict(part.get("artifact") or {})
            if artifact:
                self._sanitize_artifacts(record, [artifact])
        return sanitized

    def _sanitize_artifacts(self, record: dict[str, Any], artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sanitized: list[dict[str, Any]] = []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            internal = a2a_artifact_to_artifact_ref(
                artifact,
                task_id=str(record.get("task_id") or ""),
                run_id=str(dict(record.get("agent_task") or {}).get("run_id") or ""),
                source_node_id="external-a2a-bridge",
            )
            sanitized.append(artifact_ref_to_a2a_artifact(internal))
        return sanitized

    def _normalize_submission_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        clean = _ensure_dict(payload, "external_a2a_gateway.task")
        task_id = str(clean.get("id") or clean.get("taskId") or clean.get("task_id") or f"task-{uuid4().hex[:16]}").strip()
        state = _normalize_task_state(clean.get("state") or "TASK_STATE_SUBMITTED", field="external_a2a_gateway.task.state")
        input_parts = list(clean.get("input") or [])
        if not input_parts and isinstance(clean.get("message"), dict):
            input_parts = list(dict(clean.get("message") or {}).get("parts") or [])
        if not input_parts:
            raise ValueError("external_a2a_gateway.task.input must include at least one part.")
        normalized_parts = [
            content_part_to_a2a_part(
                a2a_part_to_content_part(
                    dict(item),
                    task_id=task_id,
                    run_id=f"external-a2a-run:{task_id}",
                    source_node_id="external-a2a-bridge",
                )
            )
            for item in input_parts
            if isinstance(item, dict)
        ]
        if not normalized_parts:
            raise ValueError("external_a2a_gateway.task.input must include at least one object part.")
        return {
            "id": task_id,
            "state": state,
            "contextId": str(clean.get("contextId") or clean.get("context_id") or f"context-{task_id}"),
            "input": normalized_parts,
            "createdAt": str(clean.get("createdAt") or clean.get("created_at") or now_iso()),
        }

    def _task_view_locked(self, record: dict[str, Any]) -> dict[str, Any]:
        payload = agent_task_to_a2a_task(dict(record.get("agent_task") or {}), state=str(record.get("state") or "TASK_STATE_SUBMITTED"))
        payload["contextId"] = str(record.get("context_id") or "")
        payload["updatedAt"] = str(record.get("updated_at") or "")
        payload["messages"] = [deepcopy(item) for item in list(record.get("messages") or []) if isinstance(item, dict)]
        payload["artifacts"] = [deepcopy(item) for item in list(record.get("artifacts") or []) if isinstance(item, dict)]
        if payload["messages"]:
            payload["message"] = deepcopy(payload["messages"][-1])
        if dict(record.get("execution") or {}):
            payload["execution"] = deepcopy(dict(record.get("execution") or {}))
        metadata = self._normalize_gateway_metadata(record.get("metadata"))
        if metadata:
            payload["metadata"] = metadata
        if str(record.get("error") or "").strip():
            payload["error"] = str(record.get("error") or "").strip()
        return payload

    def _augment_gateway_metadata(
        self,
        metadata: dict[str, Any],
        *,
        negotiation: dict[str, Any],
        trust_decision: dict[str, Any],
        request_size_bytes: int,
        replay_record: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = deepcopy(metadata)
        external = dict(normalized.get("external_a2a") or {})
        external["negotiation"] = negotiation
        external["trust_decision"] = trust_decision
        external["request_size_bytes"] = int(request_size_bytes)
        external["replay"] = replay_record
        normalized["external_a2a"] = external
        return normalized

    def _negotiate_request(self, external_meta: dict[str, Any]) -> dict[str, Any]:
        peer_versions = _normalize_string_list(
            external_meta.get("supported_protocol_versions") or [external_meta.get("protocol_version") or external_meta.get("protocolVersion") or SUPPORTED_A2A_PROTOCOL_VERSIONS[0]],
            field="external_a2a.supported_protocol_versions",
            required=True,
        )
        peer_versions = [_normalize_protocol_version_text(item, field="external_a2a.supported_protocol_versions") for item in peer_versions]
        requested_version = _normalize_protocol_version_text(
            external_meta.get("protocol_version") or external_meta.get("protocolVersion") or peer_versions[0],
            field="external_a2a.protocol_version",
        )
        selected_version = requested_version if requested_version in SUPPORTED_A2A_PROTOCOL_VERSIONS else ""
        if not selected_version:
            for version in SUPPORTED_A2A_PROTOCOL_VERSIONS:
                if version in peer_versions:
                    selected_version = version
                    break
        if not selected_version:
            raise ExternalA2ARequestRejectedError(
                "external A2A request is incompatible with AstraBridge's supported protocol versions.",
                code="incompatible_protocol_version",
                status_code=422,
                detail={
                    "requested_protocol_version": requested_version,
                    "peer_supported_protocol_versions": peer_versions,
                    "gateway_supported_protocol_versions": list(SUPPORTED_A2A_PROTOCOL_VERSIONS),
                },
            )
        if requested_version != selected_version and not bool(external_meta.get("allow_downgrade", True)):
            raise ExternalA2ARequestRejectedError(
                "external A2A request does not allow protocol downgrade.",
                code="protocol_downgrade_rejected",
                status_code=422,
                detail={
                    "requested_protocol_version": requested_version,
                    "selected_protocol_version": selected_version,
                },
            )

        peer_bindings = [
            _normalize_protocol_binding_text(item, field="external_a2a.supported_protocol_bindings")
            for item in _normalize_string_list(
                external_meta.get("supported_protocol_bindings") or [external_meta.get("protocol_binding") or external_meta.get("protocolBinding") or SUPPORTED_A2A_PROTOCOL_BINDINGS[0]],
                field="external_a2a.supported_protocol_bindings",
                required=True,
            )
        ]
        requested_binding = _normalize_protocol_binding_text(
            external_meta.get("protocol_binding") or external_meta.get("protocolBinding") or peer_bindings[0],
            field="external_a2a.protocol_binding",
        )
        selected_binding = requested_binding if requested_binding in SUPPORTED_A2A_PROTOCOL_BINDINGS else ""
        if not selected_binding:
            for binding in SUPPORTED_A2A_PROTOCOL_BINDINGS:
                if binding in peer_bindings:
                    selected_binding = binding
                    break
        if not selected_binding:
            raise ExternalA2ARequestRejectedError(
                "external A2A request is incompatible with AstraBridge's supported protocol bindings.",
                code="incompatible_protocol_binding",
                status_code=422,
                detail={
                    "requested_protocol_binding": requested_binding,
                    "peer_supported_protocol_bindings": peer_bindings,
                    "gateway_supported_protocol_bindings": list(SUPPORTED_A2A_PROTOCOL_BINDINGS),
                },
            )
        required_extensions = _normalize_string_list(external_meta.get("required_extensions"), field="external_a2a.required_extensions", required=False)
        optional_extensions = _normalize_string_list(external_meta.get("optional_extensions"), field="external_a2a.optional_extensions", required=False)
        unsupported_required = [item for item in required_extensions if item not in self._supported_extensions]
        if unsupported_required:
            raise ExternalA2ARequestRejectedError(
                "external A2A request requires unsupported extensions.",
                code="unsupported_required_extensions",
                status_code=422,
                detail={
                    "required_extensions": required_extensions,
                    "unsupported_required_extensions": unsupported_required,
                    "gateway_supported_extensions": list(self._supported_extensions),
                },
            )
        accepted_optional = [item for item in optional_extensions if item in self._supported_extensions]
        rejected_optional = [item for item in optional_extensions if item not in self._supported_extensions]
        return {
            "schema_version": EXTERNAL_A2A_NEGOTIATION_SCHEMA_VERSION,
            "requested_protocol_version": requested_version,
            "peer_supported_protocol_versions": peer_versions,
            "selected_protocol_version": selected_version,
            "requested_protocol_binding": requested_binding,
            "peer_supported_protocol_bindings": peer_bindings,
            "selected_protocol_binding": selected_binding,
            "required_extensions": required_extensions,
            "optional_extensions": optional_extensions,
            "accepted_extensions": [*required_extensions, *accepted_optional],
            "rejected_optional_extensions": rejected_optional,
            "downgraded_from_protocol_version": requested_version if requested_version != selected_version else None,
            "downgraded_from_protocol_binding": requested_binding if requested_binding != selected_binding else None,
        }

    def _evaluate_peer_policy(self, external_meta: dict[str, Any]) -> dict[str, Any]:
        issuer = str(external_meta.get("issuer") or "").strip()
        audience = str(external_meta.get("audience") or "").strip()
        workspace_id = str(external_meta.get("workspace_id") or external_meta.get("workspaceId") or external_meta.get("tenant") or "").strip()
        trust_level = str(external_meta.get("trust_level") or external_meta.get("trustLevel") or "workspace_trusted").strip()
        if trust_level not in SUPPORTED_A2A_TRUST_LEVELS:
            raise ExternalA2ARequestRejectedError(
                "external A2A request declares an unsupported peer trust level.",
                code="unsupported_trust_level",
                status_code=403,
                detail={"trust_level": trust_level},
            )
        if trust_level == "untrusted":
            raise ExternalA2ARequestRejectedError(
                "external A2A request is untrusted under the configured gateway policy.",
                code="untrusted_peer",
                status_code=403,
                detail={"issuer": issuer or None, "trust_level": trust_level},
            )
        policy = deepcopy(self._trusted_peer_policies.get(issuer) or {})
        if self._require_trusted_peers and not policy:
            raise ExternalA2ARequestRejectedError(
                "external A2A request issuer is not trusted by this gateway.",
                code="untrusted_peer",
                status_code=403,
                detail={"issuer": issuer or None},
            )
        expected_audiences = _normalize_string_list(policy.get("audiences") or [self._default_audience], field="external_a2a.policy.audiences", required=True)
        if not audience and not policy and not self._require_trusted_peers:
            audience = self._default_audience
        if audience and audience not in expected_audiences:
            raise ExternalA2ARequestRejectedError(
                "external A2A request audience does not match the gateway audience binding.",
                code="wrong_audience",
                status_code=403,
                detail={
                    "issuer": issuer or None,
                    "audience": audience or None,
                    "expected_audiences": expected_audiences,
                },
            )
        if not audience:
            raise ExternalA2ARequestRejectedError(
                "external A2A request audience does not match the gateway audience binding.",
                code="wrong_audience",
                status_code=403,
                detail={
                    "issuer": issuer or None,
                    "audience": None,
                    "expected_audiences": expected_audiences,
                },
            )
        allowed_workspace_ids = _normalize_string_list(policy.get("workspace_ids"), field="external_a2a.policy.workspace_ids", required=False)
        if self._local_workspace_id and not workspace_id:
            workspace_id = self._local_workspace_id
        if allowed_workspace_ids and workspace_id not in allowed_workspace_ids:
            raise ExternalA2ARequestRejectedError(
                "external A2A request workspace binding is not trusted for this gateway.",
                code="workspace_binding_rejected",
                status_code=403,
                detail={
                    "issuer": issuer or None,
                    "workspace_id": workspace_id or None,
                    "allowed_workspace_ids": allowed_workspace_ids,
                },
            )
        required_security_schemes = _normalize_string_list(policy.get("required_security_schemes"), field="external_a2a.policy.required_security_schemes", required=False)
        presented_security_schemes = _normalize_string_list(
            external_meta.get("security_schemes") or external_meta.get("securitySchemes"),
            field="external_a2a.security_schemes",
            required=False,
        )
        missing_schemes = [item for item in required_security_schemes if item not in presented_security_schemes]
        if missing_schemes:
            raise ExternalA2ARequestRejectedError(
                "external A2A request does not satisfy the gateway security scheme policy.",
                code="missing_security_scheme",
                status_code=403,
                detail={
                    "issuer": issuer or None,
                    "required_security_schemes": required_security_schemes,
                    "presented_security_schemes": presented_security_schemes,
                    "missing_security_schemes": missing_schemes,
                },
            )
        allowed_key_ids = _normalize_string_list(policy.get("signing_key_ids"), field="external_a2a.policy.signing_key_ids", required=False)
        signed_agent_card_verified = False
        signed_card_digest = None
        if bool(policy.get("require_signed_agent_card")):
            signed_agent_card_verified, signed_card_digest = self._verify_signed_agent_card(external_meta, policy)
        minimum_trust = str(policy.get("trust_level") or "workspace_trusted").strip() or "workspace_trusted"
        if _trust_level_rank(trust_level) < _trust_level_rank(minimum_trust):
            raise ExternalA2ARequestRejectedError(
                "external A2A request trust level is below the gateway minimum.",
                code="untrusted_peer",
                status_code=403,
                detail={
                    "issuer": issuer or None,
                    "trust_level": trust_level,
                    "minimum_trust_level": minimum_trust,
                },
            )
        return {
            "schema_version": EXTERNAL_A2A_TRUST_DECISION_SCHEMA_VERSION,
            "issuer": issuer or None,
            "audience": audience,
            "workspace_id": workspace_id or None,
            "trust_level": trust_level,
            "minimum_trust_level": minimum_trust,
            "required_security_schemes": required_security_schemes,
            "presented_security_schemes": presented_security_schemes,
            "signed_agent_card_required": bool(policy.get("require_signed_agent_card")),
            "signed_agent_card_verified": signed_agent_card_verified,
            "signed_agent_card_digest": signed_card_digest,
            "peer_agent_card_digest": str(external_meta.get("peer_agent_card_digest") or "").strip() or None,
            "gateway_policy_digest": _stable_json_digest(
                {
                    "issuer": issuer or None,
                    "policy": {
                        "trust_level": minimum_trust,
                        "audiences": expected_audiences,
                        "workspace_ids": allowed_workspace_ids,
                        "required_security_schemes": required_security_schemes,
                        "require_signed_agent_card": bool(policy.get("require_signed_agent_card")),
                        "signing_key_ids": allowed_key_ids,
                        "pinned_agent_card_digest": str(policy.get("pinned_agent_card_digest") or "").strip() or None,
                    },
                }
            ),
            "decision": "trusted",
        }

    def _verify_signed_agent_card(self, external_meta: dict[str, Any], policy: dict[str, Any]) -> tuple[bool, str]:
        presented_card = external_meta.get("peer_agent_card")
        if not isinstance(presented_card, dict):
            raise ExternalA2ARequestRejectedError(
                "external A2A gateway requires a signed peer Agent Card but none was presented.",
                code="missing_signed_agent_card",
                status_code=403,
                detail={},
            )
        normalized_card = _normalize_agent_card(
            presented_card,
            field="external_a2a.peer_agent_card",
            supported_protocol_versions=list(SUPPORTED_A2A_PROTOCOL_VERSIONS),
        )
        presented_digest = _require_non_empty_string(
            external_meta.get("peer_agent_card_digest"),
            field="external_a2a.peer_agent_card_digest",
        )
        computed_digest = _stable_json_digest(normalized_card)
        if presented_digest != computed_digest:
            raise ExternalA2ARequestRejectedError(
                "external A2A peer Agent Card digest does not match the normalized card content.",
                code="peer_agent_card_digest_mismatch",
                status_code=403,
                detail={"presented_digest": presented_digest, "computed_digest": computed_digest},
            )
        pinned_digest = str(policy.get("pinned_agent_card_digest") or "").strip()
        if pinned_digest and pinned_digest != computed_digest:
            raise ExternalA2ARequestRejectedError(
                "external A2A peer Agent Card digest is not trusted by the gateway pinset.",
                code="peer_agent_card_untrusted",
                status_code=403,
                detail={"presented_digest": computed_digest, "pinned_digest": pinned_digest},
            )
        signature = _ensure_dict(external_meta.get("peer_agent_card_signature"), "external_a2a.peer_agent_card_signature")
        algorithm = _require_non_empty_string(signature.get("algorithm"), field="external_a2a.peer_agent_card_signature.algorithm").lower()
        if algorithm != "hmac-sha256":
            raise ExternalA2ARequestRejectedError(
                "external A2A peer Agent Card signature algorithm is unsupported.",
                code="unsupported_agent_card_signature_algorithm",
                status_code=403,
                detail={"algorithm": algorithm},
            )
        key_id = _require_non_empty_string(signature.get("key_id") or signature.get("keyId"), field="external_a2a.peer_agent_card_signature.key_id")
        allowed_key_ids = _normalize_string_list(policy.get("signing_key_ids"), field="external_a2a.policy.signing_key_ids", required=False)
        if allowed_key_ids and key_id not in allowed_key_ids:
            raise ExternalA2ARequestRejectedError(
                "external A2A peer Agent Card signature key is not trusted by the gateway policy.",
                code="untrusted_agent_card_signing_key",
                status_code=403,
                detail={"key_id": key_id, "allowed_key_ids": allowed_key_ids},
            )
        secret = self._signature_keys.get(key_id)
        if not secret:
            raise ExternalA2ARequestRejectedError(
                "external A2A gateway does not have the configured signing key required to verify the peer Agent Card.",
                code="missing_agent_card_signing_key",
                status_code=403,
                detail={"key_id": key_id},
            )
        expected_signature = hmac.new(secret.encode("utf-8"), computed_digest.encode("utf-8"), hashlib.sha256).hexdigest()
        presented_signature = _require_non_empty_string(signature.get("signature"), field="external_a2a.peer_agent_card_signature.signature")
        if not hmac.compare_digest(presented_signature, expected_signature):
            raise ExternalA2ARequestRejectedError(
                "external A2A peer Agent Card signature verification failed.",
                code="agent_card_signature_invalid",
                status_code=403,
                detail={"key_id": key_id},
            )
        return True, computed_digest

    def _validate_replay_window(self, external_meta: dict[str, Any], *, request_digest: str) -> dict[str, Any]:
        self._prune_seen_request_ids()
        now = datetime.now(timezone.utc)
        request_id = str(external_meta.get("request_id") or external_meta.get("requestId") or "").strip()
        issuer = str(external_meta.get("issuer") or "").strip() or "anonymous"
        sent_at = _optional_datetime(
            external_meta.get("sent_at") or external_meta.get("sentAt") or external_meta.get("request_at") or external_meta.get("requestAt"),
            field="external_a2a.sent_at",
        )
        not_before = _optional_datetime(
            external_meta.get("not_before") or external_meta.get("notBefore"),
            field="external_a2a.not_before",
        )
        expires_at = _optional_datetime(
            external_meta.get("expires_at") or external_meta.get("expiresAt"),
            field="external_a2a.expires_at",
        )
        if sent_at is not None:
            if sent_at < now - timedelta(seconds=self._replay_window_seconds + self._clock_skew_seconds):
                raise ExternalA2ARequestRejectedError(
                    "external A2A request is outside the allowed replay window.",
                    code="expired_request",
                    status_code=409,
                    detail={
                        "sent_at": sent_at.isoformat(),
                        "replay_window_seconds": self._replay_window_seconds,
                    },
                )
            if sent_at > now + timedelta(seconds=self._clock_skew_seconds):
                raise ExternalA2ARequestRejectedError(
                    "external A2A request timestamp is too far in the future for the configured gateway clock-skew tolerance.",
                    code="request_not_yet_valid",
                    status_code=409,
                    detail={"sent_at": sent_at.isoformat(), "clock_skew_seconds": self._clock_skew_seconds},
                )
        if not_before is not None and not_before > now + timedelta(seconds=self._clock_skew_seconds):
            raise ExternalA2ARequestRejectedError(
                "external A2A request is not yet valid under the declared not-before policy.",
                code="request_not_yet_valid",
                status_code=409,
                detail={"not_before": not_before.isoformat()},
            )
        if expires_at is not None and expires_at < now - timedelta(seconds=self._clock_skew_seconds):
            raise ExternalA2ARequestRejectedError(
                "external A2A request has expired under the declared expiry policy.",
                code="expired_request",
                status_code=409,
                detail={"expires_at": expires_at.isoformat()},
            )
        if request_id:
            key = (issuer, request_id)
            if key in self._seen_request_ids:
                raise ExternalA2ARequestRejectedError(
                    "external A2A request replay was detected by the gateway replay journal.",
                    code="replayed_request",
                    status_code=409,
                    detail={"issuer": issuer, "request_id": request_id},
                )
        return {
            "issuer": issuer if issuer != "anonymous" else None,
            "request_id": request_id or None,
            "sent_at": sent_at.isoformat() if sent_at else None,
            "not_before": not_before.isoformat() if not_before else None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "replay_window_seconds": self._replay_window_seconds,
        }

    def _prune_seen_request_ids(self) -> None:
        if not self._seen_request_ids:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._replay_window_seconds + self._clock_skew_seconds)
        stale_keys: list[tuple[str, str]] = []
        for key, payload in list(self._seen_request_ids.items()):
            accepted_at = _optional_datetime(payload.get("accepted_at"), field="external_a2a.replay.accepted_at")
            if accepted_at is not None and accepted_at < cutoff:
                stale_keys.append(key)
        for key in stale_keys:
            self._seen_request_ids.pop(key, None)

    def _normalize_gateway_metadata(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        data = _ensure_dict(value, "external_a2a_gateway.metadata")
        normalized = deepcopy(data)
        external = dict(normalized.get("external_a2a") or {})
        if external:
            for secret_key in ("api_key", "authorization", "cookie", "bearer_token", "raw_reasoning"):
                external.pop(secret_key, None)
            normalized["external_a2a"] = external
        return normalized

    def _record_gateway_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_recorder is None:
            return
        try:
            self._event_recorder(event_type, deepcopy(payload))
        except Exception:
            return


class ExternalA2AGatewayClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = str(base_url or "").strip().rstrip("/")
        if not self._base_url:
            raise ValueError("base_url is required.")
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch_agent_card(self, *, timeout_sec: float = 5.0) -> dict[str, Any]:
        with self._opener.open(f"{self._base_url}/.well-known/agent-card.json", timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))

    def send_task(
        self,
        task: dict[str, Any],
        *,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
        timeout_sec: float = 5.0,
    ) -> dict[str, Any]:
        return self._post_json(
            "/a2a/tasks/send",
            {"task": deepcopy(task), "idempotencyKey": idempotency_key, "metadata": deepcopy(metadata or {})},
            timeout_sec=timeout_sec,
        )

    def get_task(self, task_id: str, *, timeout_sec: float = 5.0) -> dict[str, Any]:
        with self._opener.open(f"{self._base_url}/a2a/tasks/{urllib.parse.quote(task_id)}", timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))

    def cancel_task(self, task_id: str, *, timeout_sec: float = 5.0) -> dict[str, Any]:
        return self._post_json(f"/a2a/tasks/{urllib.parse.quote(task_id)}/cancel", {}, timeout_sec=timeout_sec)

    def stream_task_events(
        self,
        task_id: str,
        *,
        after: int = 0,
        seconds: float = 5.0,
        timeout_sec: float = 10.0,
    ) -> list[dict[str, Any]]:
        url = f"{self._base_url}/a2a/tasks/{urllib.parse.quote(task_id)}/events/stream?after={max(0, int(after))}&seconds={max(1.0, float(seconds))}"
        request = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
        events: list[dict[str, Any]] = []
        with self._opener.open(request, timeout=timeout_sec) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                if isinstance(payload, dict) and isinstance(payload.get("event"), dict):
                    events.append(payload["event"])
        return events

    def _post_json(self, path: str, payload: dict[str, Any], *, timeout_sec: float) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with self._opener.open(request, timeout=timeout_sec) as response:
            return json.loads(response.read().decode("utf-8"))


def _text_from_a2a_parts(parts: list[dict[str, Any]]) -> str:
    fragments: list[str] = []
    for item in parts:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        if kind == "text":
            text = str(item.get("text") or "").strip()
            if text:
                fragments.append(text)
            continue
        if kind == "json" and "data" in item:
            fragments.append(json.dumps(item.get("data"), ensure_ascii=False, sort_keys=True))
    return "\n\n".join(fragment for fragment in fragments if fragment).strip()


def _json_size_bytes(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _manifest_freshness(
    *,
    observed_at: str | None,
    stale_after_seconds: int | None,
    expires_at: Any,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    observed_dt = _optional_datetime(observed_at, field="external_a2a.manifest.observed_at")
    expiry_dt = _optional_datetime(expires_at, field="external_a2a.manifest.expires_at")
    stale_after = int(stale_after_seconds or 0)
    if expiry_dt is None and observed_dt is not None and stale_after > 0:
        expiry_dt = observed_dt + timedelta(seconds=stale_after)
    freshness_status = "current" if observed_dt is not None else "not_configured"
    if expiry_dt is not None and now > expiry_dt:
        freshness_status = "expired"
    return {
        "observed_at": observed_dt.isoformat() if observed_dt else None,
        "stale_after_seconds": stale_after or None,
        "expires_at": expiry_dt.isoformat() if expiry_dt else None,
        "freshness_status": freshness_status,
    }


def _optional_positive_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _optional_datetime(value: Any, *, field: str) -> datetime | None:
    if value in {None, ""}:
        return None
    text = _require_non_empty_string(value, field=field)
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _trust_level_rank(value: str) -> int:
    ranks = {
        "untrusted": 0,
        "workspace_trusted": 1,
        "pinned": 2,
    }
    return int(ranks.get(str(value or "").strip(), -1))


__all__ = [
    "EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION",
    "EXTERNAL_A2A_CARD_REF_PREFIX",
    "EXTERNAL_A2A_GATEWAY_SCHEMA_VERSION",
    "ExternalA2AConflictError",
    "ExternalA2AGatewayClient",
    "ExternalA2AGatewayService",
    "ExternalA2ANotFoundError",
    "ExternalA2ARequestRejectedError",
    "FakeExternalA2ATaskExecutor",
    "RuntimeExternalA2ATaskExecutor",
    "SUPPORTED_A2A_EXTENSIONS",
    "SUPPORTED_A2A_PROTOCOL_BINDINGS",
    "SUPPORTED_A2A_PROTOCOL_VERSIONS",
    "SUPPORTED_A2A_TASK_STATES",
    "TERMINAL_A2A_TASK_STATES",
    "INTERRUPTED_A2A_TASK_STATES",
    "validate_external_a2a_agent_card_registry",
    "build_external_a2a_gateway_snapshot",
    "validate_external_a2a_task_transition",
    "a2a_artifact_to_artifact_ref",
    "artifact_ref_to_a2a_artifact",
    "a2a_part_to_content_part",
    "content_part_to_a2a_part",
    "a2a_message_to_agent_envelope",
    "agent_envelope_to_a2a_message",
    "a2a_task_to_agent_task",
    "agent_task_to_a2a_task",
    "build_local_external_a2a_agent_card",
]
