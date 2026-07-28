"""Secret-free transactional admission for retry, fallback, and handoff turns.

Provider failures are ambiguous with respect to tool side effects: a network
failure can happen after a provider has emitted a tool call, and a thread
handoff can otherwise make that call appear new to the target lane.  This
module makes the decision explicit before a fresh/reused lane is admitted.

The state machine deliberately does *not* execute a fallback.  It prepares a
durable, user-visible decision record which the runtime can attach to a
handoff event after the target lane is successfully created or selected.  It
also fails closed when a durable tool-action receipt cannot establish whether
an already-admitted side effect completed.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..common import now_iso
from ..security import redact_sensitive


TURN_TRANSITION_SCHEMA_VERSION = "astrabridge-turn-transition-v1"
TURN_TRANSITION_STAGES = (
    "snapshot",
    "receipt_check",
    "neutral_projection",
    "capability_downgrade",
    "target_route_admission",
    "lane_start",
    "completion",
)
UNRESOLVED_TOOL_ACTION_STATES = frozenset({"executing", "interrupted", "recovery_required"})


class TurnTransitionBlocked(RuntimeError):
    """A replacement turn would risk replaying an unresolved side effect."""

    def __init__(self, transition: dict[str, Any]) -> None:
        self.transition = deepcopy(transition)
        user_visible = dict(transition.get("user_visible") or {})
        super().__init__(
            str(
                user_visible.get("message")
                or "A previous side-effect action needs explicit recovery confirmation before this turn can continue."
            )
        )


def build_turn_transition(
    *,
    source: dict[str, Any] | None,
    target: dict[str, Any] | None,
    trigger: str = "turn_start",
    failure_notice: dict[str, Any] | None = None,
    receipt_references: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    target_route: dict[str, Any] | None = None,
    context_mode: str = "default",
    retry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a single transaction record before any target lane is started.

    ``receipt_references`` must be the narrow, safe projection from the local
    action ledger.  The record intentionally contains no prompt, raw provider
    error, tool arguments, provider-private transcript, or secret-bearing
    fields.  A target lane is ready only after unresolved receipts and an
    explicitly rejected route have both been ruled out.
    """

    source_lane = _safe_lane(source)
    target_lane = _safe_lane(target)
    failure = _safe_failure(failure_notice)
    receipts = [_safe_receipt_reference(item) for item in (receipt_references or []) if isinstance(item, dict)]
    unresolved = [item for item in receipts if item["state"] in UNRESOLVED_TOOL_ACTION_STATES or item["recovery_required"]]
    route = _safe_target_route(target_route, target_lane)
    retry_metadata = _safe_retry_metadata(retry)
    cross_provider = bool(source_lane["provider_id"] and source_lane["provider_id"] != target_lane["provider_id"])
    fresh_context = str(context_mode or "default").strip().lower() in {"minimal_text", "minimal_visual", "no_context"}
    failure_category = str(failure.get("category") or "")
    compact_before_send = bool(failure.get("compact_recommended"))
    downgrade_reasoning_to = str(failure.get("reasoning_downgrade_level") or "") or None
    unsupported_feature = failure_category in {"unsupported_feature", "tool_mismatch"}
    semantic_loss = _semantic_loss(
        cross_provider=cross_provider,
        fresh_context=fresh_context,
        compact_before_send=compact_before_send,
        unresolved_receipts=bool(unresolved),
        unsupported_feature=unsupported_feature,
    )
    route_rejected = not bool(route.get("accepted", True))
    blocked = bool(unresolved) or route_rejected
    projection_required = cross_provider or fresh_context or failure_category == "runtime_state_corruption"
    retry_eligible = bool(failure.get("retryable")) and not blocked
    fallback_suggested = bool(failure.get("fallback_models") or failure.get("provider_switch_recommended"))
    action = "block_for_action_recovery" if unresolved else ("block_target_route" if route_rejected else "admit_lane_start")
    user_message = (
        "A previously admitted side-effect action has an unresolved receipt. Confirm whether it applied before retrying or handing off; "
        "AstraBridge will not replay it automatically."
        if unresolved
        else (
            "The selected target route is explicitly unavailable for execution. Choose an admitted route before continuing."
            if route_rejected
            else "The target lane is admitted with side-effect replay disabled."
        )
    )
    stages = {
        "snapshot": {
            "status": "completed",
            "source": source_lane,
            "target": target_lane,
            "trigger": _safe_text(trigger, limit=80) or "turn_start",
        },
        "receipt_check": {
            "status": "blocked" if unresolved else "completed",
            "receipt_count": len(receipts),
            "unresolved_count": len(unresolved),
            "unresolved_receipts": unresolved,
            "replay_policy": "never_replay_side_effects_automatically",
        },
        "neutral_projection": {
            "status": "required" if projection_required else "not_required",
            "mode": "task_context_neutral_projection" if projection_required else "existing_lane_context",
            "provider_private_state_replay": "forbidden" if cross_provider else "not_requested",
        },
        "capability_downgrade": {
            "status": "advisory" if any((compact_before_send, downgrade_reasoning_to, unsupported_feature, retry_metadata)) else "not_required",
            "compact_before_send": compact_before_send,
            "reasoning_effort": downgrade_reasoning_to,
            "unsupported_tool_or_reasoning_replay": "disabled" if unsupported_feature else "not_requested",
            "fallback_models": list(failure.get("fallback_models") or []),
            "provider_switch_suggested": bool(failure.get("provider_switch_recommended")),
            "retry_eligible": retry_eligible,
            "fallback_suggested": fallback_suggested,
            "retry": retry_metadata,
        },
        "target_route_admission": {
            "status": "blocked" if route_rejected else "admitted",
            "route": route,
        },
        "lane_start": {
            "status": "blocked" if blocked else "ready",
            "target_thread_id": None,
            "reused_existing": None,
        },
        "completion": {
            "status": "blocked" if blocked else "pending",
            "target_thread_id": None,
            "recovery_evidence": _recovery_evidence(receipts, unresolved),
        },
    }
    return {
        "schema_version": TURN_TRANSITION_SCHEMA_VERSION,
        "transition_id": _transition_id(source_lane, target_lane, trigger, failure, receipts),
        "created_at": now_iso(),
        "decision": action,
        "status": "blocked" if blocked else "ready",
        "failure": failure or None,
        "retry": retry_metadata or None,
        "semantic_loss": semantic_loss,
        "recovery_evidence": _recovery_evidence(receipts, unresolved),
        "stages": stages,
        "user_visible": {
            "status": "blocked" if blocked else "ready",
            "message": user_message,
            "next_action": "resolve_tool_action_recovery" if unresolved else ("select_admitted_route" if route_rejected else "start_target_lane"),
        },
        "record_required": bool(failure or receipts or cross_provider or fresh_context or retry_metadata),
    }


def assert_turn_transition_admitted(transition: dict[str, Any]) -> None:
    """Fail closed before creating/forking/reusing a target lane."""

    if str(dict(transition or {}).get("status") or "") != "ready":
        raise TurnTransitionBlocked(dict(transition or {}))


def complete_turn_transition(
    transition: dict[str, Any],
    *,
    target_thread_id: str,
    reused_existing: bool,
    completion_status: str = "lane_started",
) -> dict[str, Any]:
    """Advance an admitted transaction only after target-lane admission succeeds."""

    assert_turn_transition_admitted(transition)
    completed = deepcopy(dict(transition or {}))
    stages = dict(completed.get("stages") or {})
    lane_start = dict(stages.get("lane_start") or {})
    completion = dict(stages.get("completion") or {})
    lane_start.update(
        {
            "status": "completed",
            "target_thread_id": _safe_identifier(target_thread_id),
            "reused_existing": bool(reused_existing),
        }
    )
    completion.update(
        {
            "status": "completed",
            "completion_status": _safe_text(completion_status, limit=80) or "lane_started",
            "target_thread_id": _safe_identifier(target_thread_id),
            "completed_at": now_iso(),
        }
    )
    stages["lane_start"] = lane_start
    stages["completion"] = completion
    completed["stages"] = stages
    completed["status"] = "completed"
    completed["decision"] = "lane_started"
    completed["completed_at"] = completion["completed_at"]
    completed["user_visible"] = {
        "status": "completed",
        "message": "The target lane started with provider-private state and unresolved side effects excluded from replay.",
        "next_action": "continue_turn",
    }
    return completed


def compact_turn_transition(transition: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the handoff-safe summary kept in task and UI state."""

    if not isinstance(transition, dict) or str(transition.get("schema_version") or "") != TURN_TRANSITION_SCHEMA_VERSION:
        return None
    stages = dict(transition.get("stages") or {})
    receipt_check = dict(stages.get("receipt_check") or {})
    route_admission = dict(stages.get("target_route_admission") or {})
    lane_start = dict(stages.get("lane_start") or {})
    completion = dict(stages.get("completion") or {})
    return {
        "schema_version": TURN_TRANSITION_SCHEMA_VERSION,
        "transition_id": _safe_identifier(transition.get("transition_id")),
        "status": _safe_text(transition.get("status"), limit=40),
        "decision": _safe_text(transition.get("decision"), limit=80),
        "failure_category": _safe_text(dict(transition.get("failure") or {}).get("category"), limit=80) or None,
        "retry": _safe_retry_metadata(transition.get("retry") if isinstance(transition.get("retry"), dict) else None) or None,
        "semantic_loss": [_safe_text(item, limit=240) for item in list(transition.get("semantic_loss") or []) if _safe_text(item, limit=240)],
        "receipt_check": {
            "status": _safe_text(receipt_check.get("status"), limit=40),
            "receipt_count": _safe_nonnegative_int(receipt_check.get("receipt_count")),
            "unresolved_count": _safe_nonnegative_int(receipt_check.get("unresolved_count")),
            "replay_policy": _safe_text(receipt_check.get("replay_policy"), limit=100),
        },
        "target_route": dict(route_admission.get("route") or {}),
        "target_route_status": _safe_text(route_admission.get("status"), limit=40),
        "target_thread_id": _safe_identifier(lane_start.get("target_thread_id") or completion.get("target_thread_id")),
        "reused_existing": bool(lane_start.get("reused_existing")),
        "completion_status": _safe_text(completion.get("completion_status"), limit=80) or None,
        "recovery_evidence": _safe_recovery_evidence(transition.get("recovery_evidence")),
        "created_at": _safe_text(transition.get("created_at"), limit=64) or None,
        "completed_at": _safe_text(transition.get("completed_at"), limit=64) or None,
    }


def _safe_lane(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    return {
        "thread_id": _safe_identifier(raw.get("thread_id")),
        "profile_id": _safe_identifier(raw.get("profile_id")),
        "provider_id": _safe_text(raw.get("provider_id"), limit=120).lower() or None,
        "model_id": _safe_text(raw.get("model_id") or raw.get("model"), limit=240) or None,
        "reasoning_effort": _safe_text(raw.get("reasoning_effort") or raw.get("effort"), limit=80) or None,
        "execution_backend": _safe_text(raw.get("execution_backend"), limit=80) or None,
    }


def _safe_failure(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        return {}
    raw = dict(value or {})
    fallback_models = [_safe_text(item, limit=240) for item in list(raw.get("fallback_models") or [])]
    levels = [_safe_text(item, limit=80) for item in list(raw.get("reasoning_downgrade_levels") or [])]
    return {
        "category": _safe_text(raw.get("category"), limit=80),
        "retryable": bool(raw.get("retryable")),
        "compact_recommended": bool(raw.get("compact_recommended")),
        "provider_switch_recommended": bool(raw.get("provider_switch_recommended")),
        "recommended_action": _safe_text(raw.get("recommended_action"), limit=100) or None,
        "fallback_models": [item for item in fallback_models if item][:8],
        "reasoning_downgrade_level": next((item for item in levels if item), None),
    }


def _safe_receipt_reference(value: dict[str, Any]) -> dict[str, Any]:
    lineage = dict(value.get("lineage") or {})
    return {
        "receipt_id": _safe_identifier(value.get("receipt_id")),
        "idempotency_key": _safe_identifier(value.get("idempotency_key")),
        "action_id": _safe_identifier(value.get("action_id")),
        "tool_name": _safe_text(value.get("tool_name"), limit=80) or None,
        "state": _safe_text(value.get("state"), limit=80) or "unknown",
        "recovery_required": bool(value.get("recovery_required")),
        "lineage": {
            "task_id": _safe_identifier(lineage.get("task_id")),
            "visible_thread_id": _safe_identifier(lineage.get("visible_thread_id")),
            "execution_thread_id": _safe_identifier(lineage.get("execution_thread_id")),
            "turn_id": _safe_identifier(lineage.get("turn_id")),
            "tool_call_id": _safe_identifier(lineage.get("tool_call_id")),
        },
    }


def _safe_target_route(value: dict[str, Any] | None, target: dict[str, Any]) -> dict[str, Any]:
    raw = dict(value or {})
    accepted = raw.get("accepted")
    return {
        "provider_id": _safe_text(raw.get("provider_id") or target.get("provider_id"), limit=120).lower() or None,
        "model_id": _safe_text(raw.get("model_id") or target.get("model_id"), limit=240) or None,
        "execution_backend": _safe_text(raw.get("execution_backend") or target.get("execution_backend"), limit=80) or None,
        "admission": _safe_text(raw.get("admission"), limit=80) or "not_recorded",
        "verification_status": _safe_text(raw.get("verification_status"), limit=80) or "not_recorded",
        "accepted": bool(accepted) if isinstance(accepted, bool) else True,
        "basis": _safe_text(raw.get("basis"), limit=160) or "runtime_configuration_observed",
    }


def _safe_retry_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {}) if isinstance(value, dict) else {}
    attempt = raw.get("attempt_count")
    delay = raw.get("delay_seconds")
    metadata = {
        "attempt_count": max(1, int(attempt)) if isinstance(attempt, int) and not isinstance(attempt, bool) and attempt > 0 else None,
        "delay_seconds": max(0.0, float(delay)) if isinstance(delay, (int, float)) and not isinstance(delay, bool) else None,
        "retry_policy": _safe_text(raw.get("retry_policy"), limit=120) or None,
    }
    return metadata if any(item is not None for item in metadata.values()) else {}


def _semantic_loss(
    *,
    cross_provider: bool,
    fresh_context: bool,
    compact_before_send: bool,
    unresolved_receipts: bool,
    unsupported_feature: bool,
) -> list[str]:
    items = ["Side-effect actions are never replayed automatically across retry, fallback, or handoff lanes."]
    if cross_provider:
        items.append("Provider-private conversation and reasoning state are excluded; only neutral task context may cross providers.")
    if fresh_context:
        items.append("The replacement lane uses a fresh or reduced context projection instead of hidden source-thread state.")
    if compact_before_send:
        items.append("Context compaction is recommended before the next send, so low-priority history may be omitted.")
    if unresolved_receipts:
        items.append("An unresolved side-effect receipt blocks replay until an explicit recovery decision is recorded.")
    if unsupported_feature:
        items.append("Unsupported tool or reasoning state is excluded from the replacement lane.")
    return items


def _recovery_evidence(receipts: list[dict[str, Any]], unresolved: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "receipt_count": len(receipts),
        "unresolved_receipt_count": len(unresolved),
        "unresolved_receipt_ids": [item.get("receipt_id") or item.get("idempotency_key") for item in unresolved][:24],
        "replay_policy": "never_replay_side_effects_automatically",
    }


def _safe_recovery_evidence(value: Any) -> dict[str, Any]:
    raw = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "receipt_count": _safe_nonnegative_int(raw.get("receipt_count")),
        "unresolved_receipt_count": _safe_nonnegative_int(raw.get("unresolved_receipt_count")),
        "unresolved_receipt_ids": [
            _safe_identifier(item)
            for item in list(raw.get("unresolved_receipt_ids") or [])
            if _safe_identifier(item)
        ][:24],
        "replay_policy": _safe_text(raw.get("replay_policy"), limit=100),
    }


def _transition_id(
    source: dict[str, Any],
    target: dict[str, Any],
    trigger: str,
    failure: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> str:
    # A stable, non-secret route/receipt identity is enough for logs.  Do not
    # use Python's hash() because it changes across process launches.
    import hashlib
    import json

    payload = {
        "source": source,
        "target": target,
        "trigger": _safe_text(trigger, limit=80),
        "failure": failure,
        "receipts": [
            {
                "receipt_id": item.get("receipt_id"),
                "idempotency_key": item.get("idempotency_key"),
                "state": item.get("state"),
            }
            for item in receipts
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"turn-transition-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:24]}"


def _safe_identifier(value: Any) -> str | None:
    import re

    candidate = str(value or "").strip()
    return candidate if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@/+\-]{0,255}", candidate) else None


def _safe_text(value: Any, *, limit: int) -> str:
    return str(redact_sensitive(value) or "").strip()[:limit]


def _safe_nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    return max(0, int(value)) if isinstance(value, int) else 0
