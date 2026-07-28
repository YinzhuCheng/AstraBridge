"""Secret-free compaction and cross-route continuity contracts.

This module does not summarize provider output. It defines the evidence that a
caller must preserve when it *does* create a neutral compact summary, and keeps
that summary separate from opaque provider reasoning or raw private state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


CONTEXT_COMPACTION_HANDOFF_SCHEMA_VERSION = "astrabridge-context-compaction-handoff-v1"
NEUTRAL_COMPACTION_SUMMARY_SCHEMA_VERSION = "astrabridge-neutral-compaction-summary-v1"


def build_context_compaction_handoff_contract(
    *,
    source_route: dict[str, Any] | None,
    target_route: dict[str, Any] | None,
    source_budget_report: dict[str, Any] | None,
    target_budget_report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Describe whether a neutral compact handoff fits the target route.

    Only route identity digests and aggregate report information cross this
    boundary. The contract must never contain raw prompts, tool payloads,
    provider response IDs, opaque chain-of-thought, or credentials.
    """

    source = _safe_route(source_route)
    target = _safe_route(target_route)
    source_budget = _compact_budget_report(source_budget_report)
    target_budget = _compact_budget_report(target_budget_report)
    source_digest = _stable_digest(source_budget)
    target_digest = _stable_digest(target_budget)
    target_admission = str(target_budget.get("preflight_admission") or "downgrade_required")
    target_usable = _nonnegative_int(target_budget.get("calculated_usable_coding_context_tokens"))
    if target_usable is None:
        target_usable = _nonnegative_int(target_budget.get("usable_prompt_budget_tokens"))
    summary_budget = min(2_048, max(0, (target_usable or 0) // 4))

    reasons: list[str] = []
    if not source_budget:
        reasons.append("source_context_budget_unavailable")
    if not target_budget:
        reasons.append("target_context_budget_unavailable")
    if target_admission in {"blocked", "downgrade_required"}:
        reasons.append("target_context_budget_not_admitted")
    if summary_budget < 128:
        reasons.append("target_context_summary_budget_too_small")
    if not target.get("provider_id") or not target.get("model_id"):
        reasons.append("target_route_identity_incomplete")

    if reasons:
        status = "blocked"
        compatible = False
    elif target_admission == "admitted_with_conservative_budget":
        status = "ready_with_conservative_target_budget"
        compatible = True
    elif str(source_budget.get("preflight_admission") or "") == "admitted_after_compaction":
        status = "ready_after_source_compaction"
        compatible = True
    else:
        status = "ready"
        compatible = True

    summary_provenance = {
        "schema_version": NEUTRAL_COMPACTION_SUMMARY_SCHEMA_VERSION,
        "source_route": source,
        "target_route": target,
        "source_budget_report_digest": source_digest,
        "target_budget_report_digest": target_digest,
        "allowed_content": [
            "visible_user_intent",
            "neutral_task_state",
            "safe_tool_result_summaries",
            "checkpoint_references",
            "dropped_and_truncated_section_ids",
        ],
        "forbidden_content": [
            "opaque_provider_reasoning",
            "signed_thinking_artifacts",
            "provider_response_identifiers",
            "raw_tool_payloads",
            "credentials_or_authorization",
        ],
        "cross_route_reasoning_replay": "forbidden",
        "target_summary_token_budget": summary_budget,
    }
    return {
        "schema_version": CONTEXT_COMPACTION_HANDOFF_SCHEMA_VERSION,
        "status": status,
        "target_compatible": compatible,
        "reasons": reasons,
        "source_route": source,
        "target_route": target,
        "source_context_budget": source_budget,
        "target_context_budget": target_budget,
        "summary_provenance": summary_provenance,
        "summary_provenance_digest": _stable_digest(summary_provenance),
    }


def compact_context_compaction_handoff_contract(contract: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(contract, dict):
        return None
    summary = dict(contract.get("summary_provenance") or {})
    if not summary:
        # Runtime handoff references already carry the compact projection; keep
        # normalizing them rather than expecting callers to retain the full
        # durable bundle in task state.
        return {
            "schema_version": str(contract.get("schema_version") or ""),
            "status": str(contract.get("status") or ""),
            "target_compatible": bool(contract.get("target_compatible")),
            "reasons": [str(item).strip() for item in list(contract.get("reasons") or []) if str(item).strip()],
            "source_budget_report_digest": str(contract.get("source_budget_report_digest") or ""),
            "target_budget_report_digest": str(contract.get("target_budget_report_digest") or ""),
            "target_summary_token_budget": _nonnegative_int(contract.get("target_summary_token_budget")) or 0,
            "cross_route_reasoning_replay": str(contract.get("cross_route_reasoning_replay") or "forbidden"),
            "summary_provenance_digest": str(contract.get("summary_provenance_digest") or ""),
        }
    return {
        "schema_version": str(contract.get("schema_version") or ""),
        "status": str(contract.get("status") or ""),
        "target_compatible": bool(contract.get("target_compatible")),
        "reasons": [str(item).strip() for item in list(contract.get("reasons") or []) if str(item).strip()],
        "source_budget_report_digest": str(summary.get("source_budget_report_digest") or ""),
        "target_budget_report_digest": str(summary.get("target_budget_report_digest") or ""),
        "target_summary_token_budget": _nonnegative_int(summary.get("target_summary_token_budget")) or 0,
        "cross_route_reasoning_replay": str(summary.get("cross_route_reasoning_replay") or "forbidden"),
        "summary_provenance_digest": str(contract.get("summary_provenance_digest") or ""),
    }


def _compact_budget_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    return {
        "schema_version": str(report.get("schema_version") or ""),
        "provider_id": _safe_identifier(report.get("provider_id")),
        "model_id": _safe_identifier(report.get("model_id")),
        "advertised_context_window_tokens": _nonnegative_int(
            report.get("advertised_context_window_tokens") or report.get("context_window")
        ),
        "calculated_usable_coding_context_tokens": _nonnegative_int(report.get("calculated_usable_coding_context_tokens")),
        "verified_usable_coding_context_tokens": _nonnegative_int(report.get("verified_usable_coding_context_tokens")),
        "usable_coding_context_status": str(report.get("usable_coding_context_status") or "unknown"),
        "safe_context_budget_established": bool(report.get("safe_context_budget_established")),
        "preflight_admission": str(report.get("preflight_admission") or ""),
        "recommended_action": str(report.get("recommended_action") or ""),
        "dropped_section_ids": _safe_identifiers(report.get("dropped_section_ids")),
        "truncated_section_ids": _safe_identifiers(report.get("truncated_section_ids")),
        "reasoning_artifact_policy": str(report.get("reasoning_artifact_policy") or "neutral_summary_only"),
    }


def _safe_route(route: dict[str, Any] | None) -> dict[str, str | None]:
    raw = dict(route or {})
    return {
        "provider_id": _safe_identifier(raw.get("provider_id")),
        "model_id": _safe_identifier(raw.get("model_id")),
        "endpoint_fingerprint": _safe_fingerprint(raw.get("endpoint_fingerprint")),
        "adapter_signature": _safe_fingerprint(raw.get("adapter_signature")),
    }


def _safe_identifier(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or len(text) > 256:
        return None
    if any(marker in text.lower() for marker in ("authorization", "bearer", "api_key", "token=")):
        return None
    return text


def _safe_identifiers(value: Any) -> list[str]:
    return [item for item in (_safe_identifier(raw) for raw in list(value or [])) if item]


def _safe_fingerprint(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text or len(text) > 128 or "://" in text or "/" in text or "=" in text:
        return None
    return text


def _nonnegative_int(value: Any) -> int | None:
    try:
        if value in {None, ""}:
            return None
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _stable_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
