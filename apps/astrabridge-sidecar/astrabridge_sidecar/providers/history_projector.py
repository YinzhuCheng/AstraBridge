from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from ..security import redact_sensitive
from .registry import get_provider_profile


NEUTRAL_TRANSCRIPT_SCHEMA_VERSION = "astrabridge-neutral-transcript-v1"
REASONING_ARTIFACT_PROVENANCE_SCHEMA_VERSION = "astrabridge-reasoning-artifact-provenance-v1"
REASONING_ARTIFACT_REPLAY_DESCRIPTOR_SCHEMA_VERSION = "astrabridge-reasoning-artifact-replay-descriptor-v1"
REASONING_ARTIFACT_DROP_RECORD_SCHEMA_VERSION = "astrabridge-reasoning-artifact-drop-v1"
REASONING_ARTIFACT_REPLAY_SCOPE = "same_issuer_endpoint_model"
REASONING_ARTIFACT_RETENTION = "ephemeral"

PRIVATE_PROVIDER_KEYS = {
    "encrypted_reasoning",
    "private_reasoning",
    "provider_response_id",
    "reasoning_blob",
    "reasoning_signature",
    "response_id",
    "signed_thinking",
    "thought_signature",
    "vendor_id",
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@:+-]{0,255}$")
_FINGERPRINT_RE = re.compile(r"^[a-f0-9]{64}$")
_DIRECT_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(?:sk|rk|pk)-[A-Za-z0-9_-]{8,}\b|\b(?:api|access|auth|secret)?[_-]?(?:key|token)_[A-Za-z0-9_-]{8,}\b"
)
_SAFE_ARTIFACT_PAYLOAD_FIELDS = ("summary", "visible_summary", "text")


def _redact_neutral_value(value: Any) -> Any:
    """Apply the product redactor plus a compact direct-token guard.

    Neutral handoff material is durable workspace state, so it must not rely on
    a provider using one of the known private-field names before a token is
    redacted.  This function intentionally preserves ordinary task text while
    replacing recognizable credential-shaped values.
    """

    redacted = redact_sensitive(value)
    if isinstance(redacted, dict):
        return {str(key): _redact_neutral_value(item) for key, item in redacted.items()}
    if isinstance(redacted, list):
        return [_redact_neutral_value(item) for item in redacted]
    if isinstance(redacted, str):
        return _DIRECT_SECRET_VALUE_RE.sub("[REDACTED]", redacted)
    return redacted


def _safe_text(value: Any, *, limit: int = 4000) -> str:
    text = str(_redact_neutral_value(value) or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _safe_identifier(value: Any) -> str | None:
    candidate = str(value or "").strip()
    if not candidate or not _IDENTIFIER_RE.fullmatch(candidate):
        return None
    return candidate


def _safe_fingerprint(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    return candidate if _FINGERPRINT_RE.fullmatch(candidate) else None


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _canonical_model_id(value: Any, *, provider_id: str | None = None) -> str:
    model = str(value or "").strip().lower()
    provider = str(provider_id or "").strip().lower()
    if provider and model.startswith(provider + "/"):
        return model.split("/", 1)[1]
    return model


def sanitize_provider_private_state(value: Any) -> tuple[Any, list[str]]:
    stripped: set[str] = set()

    def _sanitize(current: Any) -> Any:
        if isinstance(current, dict):
            sanitized: dict[str, Any] = {}
            for key, item in current.items():
                clean_key = str(key).strip()
                if clean_key.lower() in PRIVATE_PROVIDER_KEYS:
                    stripped.add(clean_key)
                    continue
                sanitized[key] = _sanitize(item)
            return sanitized
        if isinstance(current, list):
            return [_sanitize(item) for item in current]
        return current

    return _redact_neutral_value(_sanitize(value)), sorted(stripped)


def provider_private_warning(stripped_keys: list[str]) -> str | None:
    if not stripped_keys:
        return None
    return f"Stripped provider-private fields during history projection: {', '.join(sorted(set(stripped_keys)))}."


@dataclass
class ReasoningArtifact:
    provider_id: str
    model_id: str
    kind: str
    replayable: bool
    payload: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class NeutralMessage:
    role: Literal["user", "assistant", "tool", "system"]
    text: str
    tool_call_id: str | None = None
    tool_name: str | None = None
    provider_data: dict[str, Any] = field(default_factory=dict)
    content_parts: list[dict[str, Any]] = field(default_factory=list)
    lineage: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectionResult:
    messages: list[dict[str, Any]]
    dropped_artifacts: int
    repaired_tool_pairs: int
    warnings: list[str]
    replayable_artifacts: list[dict[str, Any]] = field(default_factory=list)
    replayable_artifact_count: int = 0
    projection_preview: str | None = None
    artifact_drop_records: list[dict[str, Any]] = field(default_factory=list)
    transcript_entries: list[dict[str, Any]] = field(default_factory=list)


def _safe_lineage(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    result: dict[str, Any] = {}
    for key in ("task_id", "thread_id", "source_thread_id", "target_thread_id", "turn_id", "item_id", "tool_call_id", "checkpoint_id"):
        identifier = _safe_identifier(raw.get(key))
        if identifier:
            result[key] = identifier
    checkpoint_ids = raw.get("checkpoint_ids")
    if isinstance(checkpoint_ids, list):
        safe_ids = [_safe_identifier(item) for item in checkpoint_ids]
        safe_ids = [item for item in safe_ids if item]
        if safe_ids:
            result["checkpoint_ids"] = safe_ids[:20]
    return result


def _safe_task_state(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    result: dict[str, Any] = {}
    for key in ("task_id", "active_provider_thread_id", "status", "plan_status"):
        item = _safe_text(raw.get(key), limit=256)
        if item:
            result[key] = item
    for key in ("title", "goal_summary"):
        item = _safe_text(raw.get(key), limit=1000)
        if item:
            result[key] = item
    return result


def _safe_checkpoint_refs(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in list(value or []):
        if not isinstance(raw, dict):
            continue
        save_id = _safe_identifier(raw.get("save_id") or raw.get("checkpoint_id"))
        if not save_id:
            continue
        record: dict[str, Any] = {"checkpoint_id": save_id}
        description = _safe_text(raw.get("description") or raw.get("summary"), limit=1000)
        created_at = _safe_text(raw.get("created_at"), limit=128)
        if description:
            record["description"] = description
        if created_at:
            record["created_at"] = created_at
        records.append(record)
    return records[:40]


def _safe_transcript_entry(message: NeutralMessage, *, sequence: int) -> dict[str, Any]:
    role = str(message.role or "assistant").strip().lower()
    entry: dict[str, Any] = {
        "entry_id": f"message:{sequence}",
        "role": role if role in {"user", "assistant", "tool", "system"} else "assistant",
        "content": _safe_text(message.text),
        "lineage": _safe_lineage(message.lineage),
    }
    if message.tool_call_id:
        tool_call_id = _safe_identifier(message.tool_call_id)
        if tool_call_id:
            entry["tool_call_id"] = tool_call_id
    if message.tool_name:
        tool_name = _safe_identifier(message.tool_name)
        if tool_name:
            entry["tool_name"] = tool_name
    if entry["role"] == "tool":
        entry["entry_kind"] = "tool_result_summary"
    elif entry.get("tool_name"):
        entry["entry_kind"] = "tool_call_summary"
    elif entry["role"] == "user":
        entry["entry_kind"] = "user_intent"
    else:
        entry["entry_kind"] = "visible_output"
    return entry


def _safe_transcript_entry_record(value: Any, *, sequence: int) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    role = str(raw.get("role") or "assistant").strip().lower()
    entry_kind = str(raw.get("entry_kind") or "visible_output").strip()
    if entry_kind not in {"user_intent", "visible_output", "tool_call_summary", "tool_result_summary"}:
        entry_kind = "visible_output"
    entry = {
        "entry_id": _safe_identifier(raw.get("entry_id")) or f"message:{sequence}",
        "role": role if role in {"user", "assistant", "tool", "system"} else "assistant",
        "entry_kind": entry_kind,
        "content": _safe_text(raw.get("content")),
        "lineage": _safe_lineage(raw.get("lineage")),
    }
    for key in ("tool_call_id", "tool_name"):
        value = _safe_identifier(raw.get(key))
        if value:
            entry[key] = value
    return entry


def build_neutral_transcript(
    *,
    transcript_entries: list[dict[str, Any]],
    projected_messages: list[dict[str, Any]],
    replayable_artifacts: list[dict[str, Any]],
    artifact_drop_records: list[dict[str, Any]],
    lineage: dict[str, Any],
    task_state: dict[str, Any] | None = None,
    checkpoint_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the durable, secret-free continuity payload for a handoff.

    The transcript intentionally contains only visible task continuity.  Native
    reasoning is represented by an issuer-bound descriptor or an explicit drop
    record, never by the provider's opaque state.
    """

    safe_entries = [
        _safe_transcript_entry_record(entry, sequence=index + 1)
        for index, entry in enumerate(transcript_entries)
        if isinstance(entry, dict)
    ]
    safe_replay = [
        _safe_artifact_descriptor(item)
        for item in replayable_artifacts
        if isinstance(item, dict)
    ]
    safe_drops = [
        _safe_artifact_drop_record(item)
        for item in artifact_drop_records
        if isinstance(item, dict)
    ]
    return {
        "schema_version": NEUTRAL_TRANSCRIPT_SCHEMA_VERSION,
        "lineage": _safe_lineage(lineage),
        "task_state": _safe_task_state(task_state),
        "checkpoints": _safe_checkpoint_refs(checkpoint_refs),
        "entries": safe_entries,
        "projection": {
            "projected_message_count": len([item for item in projected_messages if isinstance(item, dict)]),
            "safe_entry_count": len(safe_entries),
        },
        "reasoning_artifacts": {
            "replay_descriptors": safe_replay,
            "drop_records": safe_drops,
            "opaque_provider_state": "omitted",
            "cross_provider_native_replay": "forbidden",
        },
    }


def _safe_artifact_descriptor(value: dict[str, Any]) -> dict[str, Any]:
    record = {
        "schema_version": REASONING_ARTIFACT_REPLAY_DESCRIPTOR_SCHEMA_VERSION,
        "artifact_ref": _safe_identifier(value.get("artifact_ref")) or "artifact:unknown",
        "kind": _safe_identifier(value.get("kind")) or "reasoning_state",
        "issuer": _safe_issuer(value.get("issuer")),
        "lineage": _safe_lineage(value.get("lineage")),
        "replay": _safe_replay_policy(value.get("replay")),
    }
    summary = _safe_text(value.get("visible_summary"), limit=1000)
    if summary:
        record["visible_summary"] = summary
    return record


def _safe_artifact_drop_record(value: dict[str, Any]) -> dict[str, Any]:
    record = {
        "schema_version": REASONING_ARTIFACT_DROP_RECORD_SCHEMA_VERSION,
        "artifact_ref": _safe_identifier(value.get("artifact_ref")) or "artifact:unknown",
        "kind": _safe_identifier(value.get("kind")) or "reasoning_state",
        "issuer": _safe_issuer(value.get("issuer")),
        "lineage": _safe_lineage(value.get("lineage")),
        "drop_reason": _safe_identifier(value.get("drop_reason")) or "artifact_not_replayed",
        "replay_requested": bool(value.get("replay_requested")),
        "replay": _safe_replay_policy(value.get("replay")),
    }
    reasons = [
        _safe_identifier(item)
        for item in list(value.get("reasons") or [])
    ]
    reasons = [item for item in reasons if item]
    if reasons:
        record["reasons"] = reasons[:12]
    summary = _safe_text(value.get("visible_summary"), limit=1000)
    if summary:
        record["visible_summary"] = summary
    return record


def _safe_issuer(value: Any) -> dict[str, str | None]:
    raw = dict(value) if isinstance(value, dict) else {}
    return {
        "provider_id": _safe_identifier(raw.get("provider_id")),
        "model_id": _safe_identifier(raw.get("model_id")),
        "endpoint_fingerprint": _safe_fingerprint(raw.get("endpoint_fingerprint")),
        "adapter_signature": _safe_fingerprint(raw.get("adapter_signature")),
    }


def _safe_replay_policy(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    policy: dict[str, Any] = {
        "eligible": bool(raw.get("eligible")),
        "scope": _safe_identifier(raw.get("scope")),
        "retention": _safe_identifier(raw.get("retention")),
    }
    for key in ("issued_at", "expires_at"):
        parsed = _parse_timestamp(raw.get(key))
        policy[key] = parsed.isoformat() if parsed else None
    return policy


class HistoryProjector:
    def project(
        self,
        *,
        neutral_messages: list[NeutralMessage],
        artifacts: list[ReasoningArtifact],
        source_provider: str | None,
        target_provider: str,
        source_model_id: str | None = None,
        target_model_id: str | None = None,
        source_endpoint_fingerprint: str | None = None,
        target_endpoint_fingerprint: str | None = None,
        source_adapter_signature: str | None = None,
        target_adapter_signature: str | None = None,
        now: datetime | None = None,
    ) -> ProjectionResult:
        source = str(source_provider or "").strip().lower() or None
        target = str(target_provider or "").strip().lower()
        target_profile = self._target_profile(target)
        target_known = target_profile is not None
        text_only_mode = not target_known
        supports_tool_result_images = bool(target_profile and target_profile.capabilities.supports_tool_result_images)

        dropped = 0
        repaired_tool_pairs = 0
        warnings: list[str] = []
        replayable_artifacts: list[dict[str, Any]] = []
        artifact_drop_records: list[dict[str, Any]] = []
        projected: list[dict[str, Any]] = []
        transcript_entries = [_safe_transcript_entry(message, sequence=index + 1) for index, message in enumerate(neutral_messages)]
        expected_tool_ids: list[str] = []
        seen_tool_ids: set[str] = set()
        artifact_summaries: list[str] = []
        replay_context = {
            "source_provider": source,
            "source_model_id": source_model_id,
            "source_endpoint_fingerprint": source_endpoint_fingerprint,
            "source_adapter_signature": source_adapter_signature,
            "target_provider": target,
            "target_model_id": target_model_id,
            "target_endpoint_fingerprint": target_endpoint_fingerprint,
            "target_adapter_signature": target_adapter_signature,
            "now": now or datetime.now(timezone.utc),
        }

        if text_only_mode:
            warnings.append("Unknown target provider; projected text-only history summary and dropped provider-private replay state.")

        for message in neutral_messages:
            sanitized_provider_data, stripped_provider_keys = sanitize_provider_private_state(message.provider_data)
            safe_message_text = _safe_text(message.text)
            private_warning = provider_private_warning(stripped_provider_keys)
            if private_warning:
                warnings.append(private_warning)

            if message.role == "tool":
                safe_tool_call_id = _safe_text(message.tool_call_id, limit=256)
                tool_content, tool_warning = self._project_tool_result_content(
                    message,
                    supports_tool_result_images=supports_tool_result_images,
                    text_only_mode=text_only_mode,
                )
                if tool_warning:
                    warnings.append(tool_warning)
                if not message.tool_call_id:
                    repaired_tool_pairs += 1
                    warnings.append("Dropped orphan tool result without tool_call_id.")
                    continue
                seen_tool_ids.add(message.tool_call_id)
                projected.append(
                    {
                        "role": "tool",
                        "tool_call_id": safe_tool_call_id,
                        "content": tool_content,
                    }
                )
                continue

            if message.role == "assistant" and message.tool_call_id and message.tool_name:
                expected_tool_ids.append(message.tool_call_id)
                safe_tool_call_id = _safe_text(message.tool_call_id, limit=256)
                safe_tool_name = _safe_text(message.tool_name, limit=256)
                if text_only_mode:
                    projected.append(
                        {
                            "role": "assistant",
                            "content": self._text_only_tool_call_summary(message),
                        }
                    )
                    continue
                projected.append(
                    {
                        "role": "assistant",
                        "content": safe_message_text or None,
                        "tool_calls": [
                            {
                                "id": safe_tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": safe_tool_name,
                                    "arguments": self._safe_arguments_json(sanitized_provider_data.get("arguments_json")),
                                },
                            }
                        ],
                    }
                )
                continue

            content = safe_message_text
            if message.content_parts:
                content_parts_text, content_warning = self._parts_to_text_summary(
                    message.content_parts,
                    supports_images=supports_tool_result_images,
                    for_tool=False,
                )
                if content_warning:
                    warnings.append(content_warning)
                if content_parts_text:
                    content = "\n".join(part for part in [content, content_parts_text] if part).strip()
            projected.append({"role": message.role, "content": content})

        for index, artifact in enumerate(artifacts):
            sanitized_payload, stripped_provider_keys = sanitize_provider_private_state(dict(artifact.payload or {}))
            private_warning = provider_private_warning(stripped_provider_keys)
            if private_warning:
                warnings.append(private_warning)
            safe_payload = self._safe_artifact_payload(sanitized_payload)
            artifact_kind = _safe_identifier(artifact.kind) or "reasoning_state"
            summary = self._artifact_summary(artifact_kind, safe_payload)
            replay_allowed, provenance, reasons = self._artifact_replay_decision(
                artifact=artifact,
                replay_context=replay_context,
                target_profile=target_profile,
                text_only_mode=text_only_mode,
            )
            artifact_ref = f"artifact:{index + 1}"
            if replay_allowed:
                replayable_artifacts.append(
                    {
                        "schema_version": REASONING_ARTIFACT_REPLAY_DESCRIPTOR_SCHEMA_VERSION,
                        "artifact_ref": artifact_ref,
                        "kind": artifact_kind,
                        "issuer": provenance.get("issuer"),
                        "lineage": provenance.get("lineage"),
                        "replay": provenance.get("replay"),
                        "visible_summary": summary or None,
                    }
                )
                continue
            dropped += 1
            drop_reason = reasons[0] if reasons else "artifact_not_replayed"
            artifact_drop_records.append(
                {
                    "schema_version": REASONING_ARTIFACT_DROP_RECORD_SCHEMA_VERSION,
                    "artifact_ref": artifact_ref,
                    "kind": artifact_kind,
                    "issuer": provenance.get("issuer"),
                    "lineage": provenance.get("lineage"),
                    "drop_reason": drop_reason,
                    "reasons": reasons,
                    "replay_requested": bool(artifact.replayable),
                    "replay": provenance.get("replay"),
                    "visible_summary": summary or None,
                }
            )
            warning = self._replay_drop_warning(drop_reason)
            if warning:
                warnings.append(warning)
            if summary:
                artifact_summaries.append(summary)

        if dropped and source and source != target:
            warnings.append("Opaque provider reasoning artifacts were dropped during cross-provider projection.")
        elif dropped and text_only_mode:
            warnings.append("Provider reasoning artifacts were reduced to text-only summaries for an unknown target provider.")

        if artifact_summaries and dropped:
            projected.append(
                {
                    "role": "system",
                    "content": "Prior provider summary:\n" + "\n".join(f"- {item}" for item in artifact_summaries[:4]),
                }
            )

        for tool_id in expected_tool_ids:
            if tool_id and tool_id not in seen_tool_ids:
                repaired_tool_pairs += 1
                projected.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": "Tool result was unavailable in Codex history; continue from the available context.",
                    }
                )
                transcript_entries.append(
                    {
                        "entry_id": f"repair:{tool_id}",
                        "entry_kind": "tool_result_summary",
                        "role": "tool",
                        "tool_call_id": _safe_text(tool_id, limit=256),
                        "content": "Tool result was unavailable in Codex history; continue from the available context.",
                        "lineage": {"tool_call_id": _safe_text(tool_id, limit=256)},
                    }
                )

        deduped_warnings: list[str] = []
        for warning in warnings:
            clean = str(warning or "").strip()
            if clean and clean not in deduped_warnings:
                deduped_warnings.append(clean)

        return ProjectionResult(
            messages=projected,
            dropped_artifacts=dropped,
            repaired_tool_pairs=repaired_tool_pairs,
            warnings=deduped_warnings,
            replayable_artifacts=replayable_artifacts,
            replayable_artifact_count=len(replayable_artifacts),
            projection_preview=self._projection_preview(projected),
            artifact_drop_records=artifact_drop_records,
            transcript_entries=transcript_entries,
        )

    def _artifact_replay_decision(
        self,
        *,
        artifact: ReasoningArtifact,
        replay_context: dict[str, Any],
        target_profile: Any,
        text_only_mode: bool,
    ) -> tuple[bool, dict[str, Any], list[str]]:
        provenance, provenance_reasons = self._normalize_artifact_provenance(artifact.provenance)
        source = str(replay_context.get("source_provider") or "").strip().lower()
        target = str(replay_context.get("target_provider") or "").strip().lower()
        artifact_provider = str(artifact.provider_id or "").strip().lower()
        issuer = dict(provenance.get("issuer") or {})
        replay = dict(provenance.get("replay") or {})
        reasons: list[str] = []
        if text_only_mode:
            reasons.append("target_provider_unknown")
        if not artifact.replayable:
            reasons.append("artifact_not_marked_replayable")
        if not source or not target or not artifact_provider or source != artifact_provider or target != artifact_provider:
            reasons.append("cross_provider_replay_forbidden")
        if target_profile is None or not bool(target_profile.capabilities.supports_reasoning_replay):
            reasons.append("target_provider_replay_not_supported")
        if not _safe_identifier(replay_context.get("source_model_id")) or not _safe_identifier(replay_context.get("target_model_id")):
            reasons.append("route_model_identity_incomplete")
        if not _safe_fingerprint(replay_context.get("source_endpoint_fingerprint")) or not _safe_fingerprint(replay_context.get("target_endpoint_fingerprint")):
            reasons.append("route_endpoint_identity_incomplete")
        if not _safe_fingerprint(replay_context.get("source_adapter_signature")) or not _safe_fingerprint(replay_context.get("target_adapter_signature")):
            reasons.append("route_adapter_identity_incomplete")
        reasons.extend(provenance_reasons)
        if issuer.get("provider_id") != artifact_provider:
            reasons.append("issuer_provider_mismatch")
        if _canonical_model_id(issuer.get("model_id"), provider_id=artifact_provider) != _canonical_model_id(artifact.model_id, provider_id=artifact_provider):
            reasons.append("issuer_model_mismatch")
        if _canonical_model_id(issuer.get("model_id"), provider_id=artifact_provider) != _canonical_model_id(replay_context.get("source_model_id"), provider_id=artifact_provider):
            reasons.append("source_model_mismatch")
        if _canonical_model_id(issuer.get("model_id"), provider_id=artifact_provider) != _canonical_model_id(replay_context.get("target_model_id"), provider_id=artifact_provider):
            reasons.append("target_model_mismatch")
        if issuer.get("endpoint_fingerprint") != _safe_fingerprint(replay_context.get("source_endpoint_fingerprint")):
            reasons.append("source_endpoint_mismatch")
        if issuer.get("endpoint_fingerprint") != _safe_fingerprint(replay_context.get("target_endpoint_fingerprint")):
            reasons.append("target_endpoint_mismatch")
        if issuer.get("adapter_signature") != _safe_fingerprint(replay_context.get("source_adapter_signature")):
            reasons.append("source_adapter_mismatch")
        if issuer.get("adapter_signature") != _safe_fingerprint(replay_context.get("target_adapter_signature")):
            reasons.append("target_adapter_mismatch")
        now = replay_context.get("now")
        if not isinstance(now, datetime):
            now = datetime.now(timezone.utc)
        issued_at = _parse_timestamp(replay.get("issued_at"))
        expires_at = _parse_timestamp(replay.get("expires_at"))
        if issued_at and expires_at and expires_at <= issued_at:
            reasons.append("artifact_expiry_invalid")
        if expires_at and now.astimezone(timezone.utc) > expires_at:
            reasons.append("artifact_provenance_stale")
        deduped = list(dict.fromkeys(reason for reason in reasons if reason))
        return not deduped, provenance, deduped

    def _normalize_artifact_provenance(self, value: Any) -> tuple[dict[str, Any], list[str]]:
        raw = dict(value) if isinstance(value, dict) else {}
        issuer = _safe_issuer(raw.get("issuer"))
        lineage = _safe_lineage(raw.get("lineage"))
        replay = _safe_replay_policy(raw.get("replay"))
        reasons: list[str] = []
        if str(raw.get("schema_version") or "").strip() != REASONING_ARTIFACT_PROVENANCE_SCHEMA_VERSION:
            reasons.append("provenance_schema_invalid")
        if not all(issuer.get(key) for key in ("provider_id", "model_id", "endpoint_fingerprint", "adapter_signature")):
            reasons.append("provenance_issuer_incomplete")
        if not all(lineage.get(key) for key in ("thread_id", "turn_id", "item_id")):
            reasons.append("provenance_lineage_incomplete")
        if replay.get("scope") != REASONING_ARTIFACT_REPLAY_SCOPE:
            reasons.append("provenance_scope_invalid")
        if replay.get("retention") != REASONING_ARTIFACT_RETENTION:
            reasons.append("provenance_retention_invalid")
        if not replay.get("eligible"):
            reasons.append("provenance_replay_not_eligible")
        if not replay.get("issued_at") or not replay.get("expires_at"):
            reasons.append("provenance_time_window_incomplete")
        return {
            "schema_version": REASONING_ARTIFACT_PROVENANCE_SCHEMA_VERSION,
            "issuer": issuer,
            "lineage": lineage,
            "replay": replay,
        }, reasons

    @staticmethod
    def _safe_artifact_payload(value: Any) -> dict[str, Any]:
        raw = dict(value) if isinstance(value, dict) else {}
        return {
            key: _redact_neutral_value(raw.get(key))
            for key in _SAFE_ARTIFACT_PAYLOAD_FIELDS
            if raw.get(key) is not None
        }

    @staticmethod
    def _replay_drop_warning(reason: str) -> str | None:
        if reason == "cross_provider_replay_forbidden":
            return "Cross-provider reasoning replay is forbidden; preserved only visible summary."
        if reason == "target_provider_replay_not_supported":
            return "Target provider does not support reasoning replay; preserved only visible summary."
        if reason in {"provenance_schema_invalid", "provenance_issuer_incomplete", "provenance_lineage_incomplete", "provenance_time_window_incomplete"}:
            return "Reasoning artifact provenance is incomplete; preserved only visible summary."
        if reason == "artifact_provenance_stale":
            return "Reasoning artifact provenance is stale; preserved only visible summary."
        if reason in {"route_model_identity_incomplete", "route_endpoint_identity_incomplete", "route_adapter_identity_incomplete"}:
            return "Target route identity is incomplete; preserved only visible summary."
        return None

    def _target_profile(self, provider_id: str):
        try:
            return get_provider_profile(provider_id) if provider_id else None
        except ValueError:
            return None

    def _safe_arguments_json(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(_redact_neutral_value(value), ensure_ascii=False, separators=(",", ":"))
        text = _safe_text(value)
        if not text:
            return "{}"
        try:
            return json.dumps(_redact_neutral_value(json.loads(text)), ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return json.dumps({"raw": _safe_text(text)}, ensure_ascii=False, separators=(",", ":"))

    def _project_tool_result_content(
        self,
        message: NeutralMessage,
        *,
        supports_tool_result_images: bool,
        text_only_mode: bool,
    ) -> tuple[str, str | None]:
        parts = list(message.content_parts or list(message.provider_data.get("content_parts") or []))
        if not parts:
            return _safe_text(message.text), None
        text_summary, warning = self._parts_to_text_summary(parts, supports_images=supports_tool_result_images, for_tool=True)
        if text_only_mode:
            text_summary = "\n".join(part for part in [_safe_text(message.text), text_summary] if part).strip()
            return text_summary or _safe_text(message.text), warning
        return "\n".join(part for part in [_safe_text(message.text), text_summary] if part).strip() or _safe_text(message.text), warning

    def _parts_to_text_summary(
        self,
        parts: list[dict[str, Any]],
        *,
        supports_images: bool,
        for_tool: bool,
    ) -> tuple[str, str | None]:
        chunks: list[str] = []
        image_count = 0
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type") or "").strip().lower()
            if part_type in {"text", "output_text"} and str(part.get("text") or "").strip():
                chunks.append(_safe_text(part.get("text")))
                continue
            if part_type in {"image", "image_url", "input_image", "output_image"}:
                image_count += 1
                if supports_images:
                    chunks.append(f"[image result retained as metadata: {part_type}]")
                else:
                    detail = _safe_text(part.get("detail") or part.get("mime_type") or part.get("format"), limit=128)
                    suffix = f" ({detail})" if detail else ""
                    chunks.append(f"[image result omitted{suffix}]")
        warning = None
        if image_count and not supports_images:
            warning = (
                "Downgraded image tool result to text metadata because the target provider does not support tool-result images."
                if for_tool
                else "Downgraded image content part to text metadata for the target provider."
            )
        return "\n".join(chunk for chunk in chunks if chunk).strip(), warning

    def _text_only_tool_call_summary(self, message: NeutralMessage) -> str:
        base = _safe_text(message.text)
        tool = _safe_text(message.tool_name or "tool", limit=256)
        summary = f"Assistant requested tool call: {tool}."
        return "\n".join(part for part in [base, summary] if part).strip()

    def _artifact_summary(self, kind: str, payload: dict[str, Any]) -> str:
        summary = payload.get("summary")
        if isinstance(summary, list):
            text = " ".join(_safe_text(item, limit=320) for item in summary if _safe_text(item, limit=320))
            if text:
                return self._clip(f"{kind}: {text}", 320)
        if isinstance(summary, str) and summary.strip():
            return self._clip(f"{kind}: {_safe_text(summary, limit=320)}", 320)
        visible = payload.get("visible_summary") or payload.get("text")
        if isinstance(visible, str) and visible.strip():
            return self._clip(f"{kind}: {_safe_text(visible, limit=320)}", 320)
        return ""

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _projection_preview(self, messages: list[dict[str, Any]]) -> str | None:
        chunks: list[str] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "").strip().lower()
            content = self._message_preview_content(message)
            if not content:
                continue
            prefix = {
                "system": "System",
                "user": "User",
                "assistant": "Assistant",
                "tool": "Tool",
            }.get(role, "Message")
            chunks.append(f"{prefix}: {content}")
        if not chunks:
            return None
        return self._clip(" | ".join(chunks[-3:]), 480)

    def _message_preview_content(self, message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return " ".join(content.split())
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str) and item.strip():
                    parts.append(" ".join(item.split()))
                elif isinstance(item, dict):
                    text = str(item.get("text") or item.get("content") or "").strip()
                    if text:
                        parts.append(" ".join(text.split()))
            joined = " ".join(parts).strip()
            if joined:
                return joined
        tool_calls = list(message.get("tool_calls") or [])
        if tool_calls:
            names = [
                str((call.get("function") or {}).get("name") or call.get("name") or "").strip()
                for call in tool_calls
                if isinstance(call, dict)
            ]
            names = [name for name in names if name]
            if names:
                return f"requested tool call(s): {', '.join(names[:3])}"
        tool_call_id = str(message.get("tool_call_id") or "").strip()
        if tool_call_id:
            return f"tool result for {tool_call_id}"
        return ""
