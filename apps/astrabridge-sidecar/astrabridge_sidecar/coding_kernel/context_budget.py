from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


CONTEXT_BUDGET_SCHEMA_VERSION = "astrabridge-context-budget-v2"
CONTEXT_BUDGET_POLICY_SCHEMA_VERSION = "astrabridge-context-budget-policy-v1"
MINIMUM_SAFE_PROMPT_TOKENS = 256

# These are deliberately conservative protocol envelopes, not a claim that a
# provider has verified a particular endpoint's exact tokenizer behavior. A
# route can replace one with endpoint-bound evidence through
# ``context_budget_policy``.
DEFAULT_PROTOCOL_OVERHEAD_TOKENS = {
    "chat": 128,
    "responses": 160,
    "native_kernel": 96,
}

SAFE_REASONING_ARTIFACT_POLICIES = {
    "drop_opaque_reasoning_artifacts",
    "neutral_summary_only",
    "same_route_native_replay_only",
}


@dataclass(frozen=True)
class ContextSection:
    section_id: str
    label: str
    priority: int
    text: str
    essential: bool = False


@dataclass(frozen=True)
class ContextSectionEstimate:
    section_id: str
    label: str
    priority: int
    chars: int
    estimated_tokens: int
    selected_chars: int
    selected_estimated_tokens: int
    essential: bool
    included: bool
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttachmentModalityEstimate:
    modality: str
    count: int
    total_bytes: int
    estimated_tokens: int
    estimate_basis: str
    support_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextBudgetReport:
    provider_id: str | None
    model_id: str | None
    context_window: int | None
    advertised_context_window_tokens: int | None
    advertised_context_window_status: str
    effective_context_window_percent: int
    effective_context_budget_tokens: int | None
    auto_compact_token_limit: int | None
    tool_output_token_limit: int | None
    manual_compact_status: str
    auto_compact_status: str
    compact_summary_quality_status: str
    endpoint_protocol: str | None
    endpoint_fingerprint: str | None
    endpoint_protocol_overhead_tokens: int | None
    endpoint_overhead_status: str
    tool_schema_token_estimate: int
    attachment_modality_token_estimate: int
    existing_thread_context_tokens: int
    output_reserve_tokens: int
    output_reserve_status: str
    reasoning_artifact_policy: str
    reasoning_artifact_reserve_tokens: int
    usable_prompt_budget_tokens: int | None
    calculated_usable_coding_context_tokens: int | None
    verified_usable_coding_context_tokens: int | None
    usable_coding_context_status: str
    minimum_safe_prompt_tokens: int
    safe_context_budget_established: bool
    preflight_admission: str
    recommended_action: str
    preflight_reasons: tuple[str, ...]
    full_text_tokens: int
    selected_text_tokens: int
    selected_text_chars: int
    compact_recommended: bool
    preflight_budgeting_status: str
    automatic_request_truncation: bool
    provider_rejection_category: str
    dropped_section_ids: tuple[str, ...]
    truncated_section_ids: tuple[str, ...]
    unsupported_attachment_modalities: tuple[str, ...]
    attachment_estimates: tuple[AttachmentModalityEstimate, ...]
    section_estimates: tuple[ContextSectionEstimate, ...]
    calculation_basis: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = CONTEXT_BUDGET_SCHEMA_VERSION
        payload["section_estimates"] = [item.to_dict() for item in self.section_estimates]
        payload["attachment_estimates"] = [item.to_dict() for item in self.attachment_estimates]
        payload["dropped_section_ids"] = list(self.dropped_section_ids)
        payload["truncated_section_ids"] = list(self.truncated_section_ids)
        payload["unsupported_attachment_modalities"] = list(self.unsupported_attachment_modalities)
        payload["preflight_reasons"] = list(self.preflight_reasons)
        return payload


def estimate_text_tokens(text: str) -> int:
    raw = str(text or "")
    if not raw:
        return 0
    return max(1, (len(raw) + 3) // 4)


def estimate_tool_schema_tokens(model: dict[str, Any]) -> int:
    estimate = 240
    if model.get("apply_patch_tool_type"):
        estimate += 550
    if model.get("supports_search_tool"):
        estimate += 320
    if model.get("supports_mcp_tools"):
        estimate += 1_100
    if model.get("supports_parallel_tool_calls"):
        estimate += 180
    if model.get("experimental_supported_tools"):
        estimate += min(600, 80 * len(list(model.get("experimental_supported_tools") or [])))
    return estimate


def normalize_context_budget_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    """Return a bounded, secret-free route-budget policy.

    The policy is intentionally metadata-only. It can express endpoint-bound
    evidence and reserves, but never includes URLs, headers, credentials, or
    opaque provider reasoning.
    """

    raw = dict(policy or {})
    endpoint_overhead = _optional_nonnegative_int(raw.get("endpoint_protocol_overhead_tokens"))
    output_reserve = _optional_nonnegative_int(raw.get("output_reserve_tokens"))
    reasoning_reserve = _optional_nonnegative_int(raw.get("reasoning_artifact_reserve_tokens"))
    reasoning_policy = str(raw.get("reasoning_artifact_policy") or "neutral_summary_only").strip().lower()
    if reasoning_policy not in SAFE_REASONING_ARTIFACT_POLICIES:
        reasoning_policy = "drop_opaque_reasoning_artifacts"
    context_window_status = str(raw.get("advertised_context_window_status") or "advertised").strip().lower()
    if context_window_status not in {"advertised", "verified", "unknown"}:
        context_window_status = "advertised"
    endpoint_overhead_status = str(raw.get("endpoint_overhead_status") or "").strip().lower()
    if endpoint_overhead_status not in {"verified", "conservative", "unknown"}:
        endpoint_overhead_status = "verified" if endpoint_overhead is not None and bool(raw.get("endpoint_verified")) else "conservative"
    return {
        "schema_version": CONTEXT_BUDGET_POLICY_SCHEMA_VERSION,
        "advertised_context_window_status": context_window_status,
        "endpoint_protocol_overhead_tokens": endpoint_overhead,
        "endpoint_overhead_status": endpoint_overhead_status,
        "output_reserve_tokens": output_reserve,
        "output_reserve_status": "configured" if output_reserve is not None else "derived_conservative",
        "reasoning_artifact_policy": reasoning_policy,
        "reasoning_artifact_reserve_tokens": reasoning_reserve,
    }


def estimate_attachment_modality_tokens(
    attachments: list[dict[str, Any]] | None,
    *,
    supported_modalities: list[str] | tuple[str, ...] | set[str] | None = None,
) -> tuple[int, tuple[AttachmentModalityEstimate, ...], tuple[str, ...]]:
    """Estimate attachment cost without retaining names, paths, or contents."""

    grouped: dict[str, dict[str, int]] = {}
    known_modalities = {str(item).strip().lower() for item in (supported_modalities or []) if str(item).strip()}
    for raw in list(attachments or []):
        if not isinstance(raw, dict):
            continue
        modality = _attachment_modality(raw)
        size = _optional_nonnegative_int(raw.get("size")) or 0
        bucket = grouped.setdefault(modality, {"count": 0, "total_bytes": 0})
        bucket["count"] += 1
        bucket["total_bytes"] += size

    estimates: list[AttachmentModalityEstimate] = []
    unsupported: list[str] = []
    for modality in sorted(grouped):
        bucket = grouped[modality]
        count = bucket["count"]
        total_bytes = bucket["total_bytes"]
        tokens, basis = _attachment_tokens_for(modality, count=count, total_bytes=total_bytes)
        if modality in {"file", "referenced_file"}:
            support_status = "referenced_not_inlined"
        elif not known_modalities:
            support_status = "unknown"
        elif modality in known_modalities:
            support_status = "declared"
        else:
            support_status = "unsupported"
            unsupported.append(modality)
        estimates.append(
            AttachmentModalityEstimate(
                modality=modality,
                count=count,
                total_bytes=total_bytes,
                estimated_tokens=tokens,
                estimate_basis=basis,
                support_status=support_status,
            )
        )
    return sum(item.estimated_tokens for item in estimates), tuple(estimates), tuple(unsupported)


def build_context_budget(
    *,
    sections: list[ContextSection],
    provider_id: str | None,
    model_id: str | None,
    context_window: int | None,
    effective_context_window_percent: int = 80,
    auto_compact_token_limit: int | None = None,
    tool_output_token_limit: int | None = None,
    manual_compact_status: str = "app_server_native",
    auto_compact_status: str = "configured_unverified",
    compact_summary_quality_status: str = "untested",
    tool_schema_token_estimate: int = 0,
    preflight_budgeting_status: str = "budgeted_before_send",
    automatic_request_truncation: bool = False,
    provider_rejection_category: str = "context_window_limit",
    endpoint_protocol: str | None = None,
    endpoint_fingerprint: str | None = None,
    endpoint_protocol_overhead_tokens: int | None = None,
    endpoint_overhead_status: str | None = None,
    advertised_context_window_status: str = "advertised",
    attachments: list[dict[str, Any]] | None = None,
    attachment_modality_token_estimate: int | None = None,
    supported_modalities: list[str] | tuple[str, ...] | set[str] | None = None,
    output_reserve_tokens: int | None = None,
    output_reserve_status: str | None = None,
    reasoning_artifact_policy: str = "neutral_summary_only",
    reasoning_artifact_reserve_tokens: int | None = None,
    existing_thread_context_tokens: int | None = 0,
    minimum_safe_prompt_tokens: int = MINIMUM_SAFE_PROMPT_TOKENS,
) -> tuple[str, ContextBudgetReport]:
    """Build a deterministic, endpoint-aware context budget report.

    The returned text is a deliberate context-pack selection. Callers that
    send a user-authored prompt must never silently substitute a truncated
    essential section: inspect ``truncated_section_ids`` and
    ``preflight_admission`` first.
    """

    ordered = sorted(sections, key=lambda item: (item.priority, item.section_id))
    normalized_protocol = str(endpoint_protocol or "").strip().lower() or None
    normalized_context_status = _context_window_status(advertised_context_window_status)
    policy = normalize_context_budget_policy(
        {
            "advertised_context_window_status": normalized_context_status,
            "endpoint_protocol_overhead_tokens": endpoint_protocol_overhead_tokens,
            "endpoint_overhead_status": endpoint_overhead_status,
            "output_reserve_tokens": output_reserve_tokens,
            "reasoning_artifact_policy": reasoning_artifact_policy,
            "reasoning_artifact_reserve_tokens": reasoning_artifact_reserve_tokens,
        }
    )

    context_value = _optional_positive_int(context_window)
    effective_percent = _bounded_percent(effective_context_window_percent)
    effective_budget = int(context_value * (effective_percent / 100)) if context_value is not None else None
    compact_cap = _optional_positive_int(auto_compact_token_limit)
    input_capacity = effective_budget
    if compact_cap is not None:
        input_capacity = min(compact_cap, input_capacity or compact_cap)

    derived_endpoint_overhead = DEFAULT_PROTOCOL_OVERHEAD_TOKENS.get(normalized_protocol or "")
    endpoint_overhead = policy["endpoint_protocol_overhead_tokens"]
    endpoint_status = str(policy["endpoint_overhead_status"])
    if endpoint_overhead is None and derived_endpoint_overhead is not None:
        endpoint_overhead = derived_endpoint_overhead
        if endpoint_status == "unknown":
            endpoint_status = "conservative"
    elif endpoint_overhead is None:
        endpoint_status = "unknown"

    estimated_attachment_tokens, attachment_estimates, unsupported_modalities = estimate_attachment_modality_tokens(
        attachments,
        supported_modalities=supported_modalities,
    )
    attachment_tokens = (
        _optional_nonnegative_int(attachment_modality_token_estimate)
        if attachment_modality_token_estimate is not None
        else estimated_attachment_tokens
    )
    attachment_tokens = int(attachment_tokens or 0)
    existing_context_tokens = int(_optional_nonnegative_int(existing_thread_context_tokens) or 0)
    output_reserve = policy["output_reserve_tokens"]
    if output_reserve is None:
        output_reserve = _derived_output_reserve(input_capacity)
    reasoning_policy = str(policy["reasoning_artifact_policy"])
    reasoning_reserve = policy["reasoning_artifact_reserve_tokens"]
    if reasoning_reserve is None:
        reasoning_reserve = _derived_reasoning_reserve(reasoning_policy, input_capacity)

    tool_schema_tokens = int(_optional_nonnegative_int(tool_schema_token_estimate) or 0)
    reserve_total = (
        int(endpoint_overhead or 0)
        + tool_schema_tokens
        + attachment_tokens
        + existing_context_tokens
        + int(output_reserve or 0)
        + int(reasoning_reserve or 0)
    )
    calculated_usable = int(input_capacity - reserve_total) if input_capacity is not None else None
    minimum_safe = max(1, int(minimum_safe_prompt_tokens or MINIMUM_SAFE_PROMPT_TOKENS))

    preflight_reasons: list[str] = []
    if context_value is None:
        preflight_reasons.append("advertised_context_window_unknown")
    if normalized_protocol is None:
        preflight_reasons.append("endpoint_protocol_unknown")
    if endpoint_overhead is None:
        preflight_reasons.append("endpoint_protocol_overhead_unknown")
    if unsupported_modalities:
        preflight_reasons.append("attachment_modality_not_supported")
    if calculated_usable is not None and calculated_usable < minimum_safe:
        preflight_reasons.append("usable_prompt_budget_below_safe_minimum")

    safe_budget = not preflight_reasons
    if safe_budget:
        usable_budget = calculated_usable
    else:
        # Fail closed for an unknown or unsafe route: no automatically injected
        # project context is selected merely because a provider advertises a
        # large window.
        usable_budget = 0

    rendered_parts: list[str] = []
    selected_tokens = 0
    selected_chars = 0
    dropped: list[str] = []
    truncated: list[str] = []
    estimates: list[ContextSectionEstimate] = []

    for section in ordered:
        source_text = str(section.text or "").strip()
        source_chars = len(source_text)
        source_tokens = estimate_text_tokens(source_text)
        included = False
        is_truncated = False
        rendered = source_text
        selected_section_tokens = source_tokens
        selected_section_chars = source_chars
        remaining = max(0, int(usable_budget or 0) - selected_tokens)

        if not source_text:
            estimates.append(
                ContextSectionEstimate(
                    section_id=section.section_id,
                    label=section.label,
                    priority=section.priority,
                    chars=0,
                    estimated_tokens=0,
                    selected_chars=0,
                    selected_estimated_tokens=0,
                    essential=section.essential,
                    included=False,
                    truncated=False,
                )
            )
            continue

        if safe_budget and source_tokens <= remaining:
            included = True
        elif safe_budget and section.essential and remaining >= 24:
            is_truncated = True
            rendered = clip_text_to_tokens(source_text, remaining)
            selected_section_tokens = estimate_text_tokens(rendered)
            selected_section_chars = len(rendered)
            included = True
            truncated.append(section.section_id)
        else:
            dropped.append(section.section_id)

        if included:
            rendered_parts.append(rendered)
            selected_tokens += selected_section_tokens
            selected_chars += selected_section_chars
        estimates.append(
            ContextSectionEstimate(
                section_id=section.section_id,
                label=section.label,
                priority=section.priority,
                chars=source_chars,
                estimated_tokens=source_tokens,
                selected_chars=selected_section_chars if included else 0,
                selected_estimated_tokens=selected_section_tokens if included else 0,
                essential=section.essential,
                included=included,
                truncated=is_truncated,
            )
        )

    full_text = "\n\n".join(str(section.text or "").strip() for section in ordered if str(section.text or "").strip())
    compact_recommended = bool(dropped or truncated)
    if calculated_usable is not None and estimate_text_tokens(full_text) > max(0, calculated_usable):
        compact_recommended = True
    essential_overflow = any(
        estimate.essential and (not estimate.included or estimate.truncated)
        for estimate in estimates
    )
    if essential_overflow:
        preflight_reasons.append("essential_context_section_exceeds_safe_budget")

    if not safe_budget:
        preflight_admission = "blocked" if calculated_usable is not None and calculated_usable < minimum_safe else "downgrade_required"
        recommended_action = "choose_verified_context_route" if context_value is None or normalized_protocol is None else "reduce_context_or_compact"
    elif essential_overflow:
        preflight_admission = "blocked"
        recommended_action = "reduce_essential_turn_input"
    elif compact_recommended:
        preflight_admission = "admitted_after_compaction"
        recommended_action = "compact_before_send"
    elif normalized_context_status == "verified" and endpoint_status == "verified":
        preflight_admission = "admitted"
        recommended_action = "continue"
    else:
        preflight_admission = "admitted_with_conservative_budget"
        recommended_action = "continue_with_context_budget_notice"

    if normalized_context_status == "verified" and endpoint_status == "verified" and safe_budget:
        usable_context_status = "verified"
        verified_usable = calculated_usable
    elif context_value is None or normalized_protocol is None or endpoint_overhead is None:
        usable_context_status = "unknown"
        verified_usable = None
    else:
        usable_context_status = "conservative_estimate"
        verified_usable = None

    final_preflight_status = str(preflight_budgeting_status or "budgeted_before_send")
    if preflight_admission in {"blocked", "downgrade_required"}:
        final_preflight_status = "safe_budget_not_established"
    elif preflight_admission == "admitted_after_compaction":
        final_preflight_status = "budgeted_with_deterministic_compaction"

    calculation_basis = {
        "policy_schema_version": CONTEXT_BUDGET_POLICY_SCHEMA_VERSION,
        "selection_policy": "priority_then_section_id",
        "advertised_capacity": {
            "tokens": context_value,
            "status": normalized_context_status,
            "effective_percent": effective_percent,
            "effective_tokens": effective_budget,
            "auto_compact_token_limit": compact_cap,
        },
        "endpoint": {
            "protocol": normalized_protocol,
            "fingerprint": _safe_fingerprint(endpoint_fingerprint),
            "protocol_overhead_tokens": endpoint_overhead,
            "overhead_status": endpoint_status,
        },
        "reserves": {
            "tool_schema_tokens": tool_schema_tokens,
            "attachment_modality_tokens": attachment_tokens,
            "existing_thread_context_tokens": existing_context_tokens,
            "output_reserve_tokens": int(output_reserve or 0),
            "output_reserve_status": str(policy["output_reserve_status"]),
            "reasoning_artifact_policy": reasoning_policy,
            "reasoning_artifact_reserve_tokens": int(reasoning_reserve or 0),
        },
        "minimum_safe_prompt_tokens": minimum_safe,
        "reserve_total_tokens": reserve_total,
        "calculated_usable_coding_context_tokens": calculated_usable,
    }
    report = ContextBudgetReport(
        provider_id=provider_id,
        model_id=model_id,
        context_window=context_value,
        advertised_context_window_tokens=context_value,
        advertised_context_window_status=normalized_context_status,
        effective_context_window_percent=effective_percent,
        effective_context_budget_tokens=effective_budget,
        auto_compact_token_limit=compact_cap,
        tool_output_token_limit=_optional_positive_int(tool_output_token_limit),
        manual_compact_status=str(manual_compact_status or "app_server_native"),
        auto_compact_status=str(auto_compact_status or "configured_unverified"),
        compact_summary_quality_status=str(compact_summary_quality_status or "untested"),
        endpoint_protocol=normalized_protocol,
        endpoint_fingerprint=_safe_fingerprint(endpoint_fingerprint),
        endpoint_protocol_overhead_tokens=endpoint_overhead,
        endpoint_overhead_status=endpoint_status,
        tool_schema_token_estimate=tool_schema_tokens,
        attachment_modality_token_estimate=attachment_tokens,
        existing_thread_context_tokens=existing_context_tokens,
        output_reserve_tokens=int(output_reserve or 0),
        output_reserve_status=str(policy["output_reserve_status"]),
        reasoning_artifact_policy=reasoning_policy,
        reasoning_artifact_reserve_tokens=int(reasoning_reserve or 0),
        usable_prompt_budget_tokens=usable_budget if safe_budget else None,
        calculated_usable_coding_context_tokens=calculated_usable,
        verified_usable_coding_context_tokens=verified_usable,
        usable_coding_context_status=usable_context_status,
        minimum_safe_prompt_tokens=minimum_safe,
        safe_context_budget_established=safe_budget,
        preflight_admission=preflight_admission,
        recommended_action=recommended_action,
        preflight_reasons=tuple(preflight_reasons),
        full_text_tokens=estimate_text_tokens(full_text),
        selected_text_tokens=selected_tokens,
        selected_text_chars=selected_chars,
        compact_recommended=compact_recommended,
        preflight_budgeting_status=final_preflight_status,
        automatic_request_truncation=bool(automatic_request_truncation),
        provider_rejection_category=str(provider_rejection_category or "context_window_limit"),
        dropped_section_ids=tuple(dropped),
        truncated_section_ids=tuple(truncated),
        unsupported_attachment_modalities=unsupported_modalities,
        attachment_estimates=attachment_estimates,
        section_estimates=tuple(estimates),
        calculation_basis=calculation_basis,
    )
    return "\n\n".join(rendered_parts), report


def selected_text_by_section(
    sections: list[ContextSection],
    report: ContextBudgetReport | dict[str, Any],
) -> dict[str, str]:
    """Materialize the already-reported deterministic selection in memory.

    This helper is intentionally not represented in ``ContextBudgetReport`` so
    durable reports stay secret-free and do not duplicate prompt text.
    """

    payload = report.to_dict() if isinstance(report, ContextBudgetReport) else dict(report or {})
    estimates = {
        str(item.get("section_id") or ""): dict(item)
        for item in list(payload.get("section_estimates") or [])
        if isinstance(item, dict)
    }
    selected: dict[str, str] = {}
    for section in sections:
        estimate = estimates.get(section.section_id)
        if not estimate or not bool(estimate.get("included")):
            continue
        text = str(section.text or "").strip()
        if bool(estimate.get("truncated")):
            text = clip_text_to_tokens(text, int(estimate.get("selected_estimated_tokens") or 0))
        selected[section.section_id] = text
    return selected


def clip_text_to_tokens(text: str, token_limit: int) -> str:
    if token_limit <= 0:
        return ""
    approx_chars = max(32, int(token_limit) * 4)
    raw = str(text or "")
    if len(raw) <= approx_chars:
        return raw
    clipped = raw[: max(0, approx_chars - 14)].rstrip()
    return clipped + "\n[truncated]"


def _attachment_modality(raw: dict[str, Any]) -> str:
    kind = str(raw.get("kind") or "").strip().lower()
    mime_type = str(raw.get("mime_type") or raw.get("mimeType") or "").strip().lower()
    if kind in {"image", "audio", "video"}:
        return kind
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("video/"):
        return "video"
    if kind in {"mention", "referenced_file", "reference"}:
        return "referenced_file"
    return "file"


def _attachment_tokens_for(modality: str, *, count: int, total_bytes: int) -> tuple[int, str]:
    if modality == "image":
        return max(256 * count, min(8_192 * count, 512 * count + (total_bytes + 16_383) // 16_384)), "conservative_image_envelope"
    if modality == "audio":
        return max(768 * count, min(12_288 * count, 1_024 * count + (total_bytes + 8_191) // 8_192)), "conservative_audio_envelope"
    if modality == "video":
        return max(1_536 * count, min(24_576 * count, 2_048 * count + (total_bytes + 16_383) // 16_384)), "conservative_video_envelope"
    if modality == "referenced_file":
        return 96 * count, "reference_metadata_envelope"
    return max(192 * count, min(4_096 * count, 256 * count + (total_bytes + 4_095) // 4_096)), "conservative_file_envelope"


def _derived_output_reserve(input_capacity: int | None) -> int:
    if input_capacity is None:
        return 0
    return max(128, min(4_096, max(1, int(input_capacity) // 8)))


def _derived_reasoning_reserve(policy: str, input_capacity: int | None) -> int:
    if policy != "same_route_native_replay_only" or input_capacity is None:
        return 0
    return max(128, min(1_024, max(1, int(input_capacity) // 16)))


def _bounded_percent(value: int | str | None) -> int:
    try:
        return min(100, max(1, int(value or 80)))
    except (TypeError, ValueError):
        return 80


def _context_window_status(value: str | None) -> str:
    normalized = str(value or "advertised").strip().lower()
    return normalized if normalized in {"advertised", "verified", "unknown"} else "advertised"


def _optional_positive_int(value: Any) -> int | None:
    result = _optional_nonnegative_int(value)
    return result if result and result > 0 else None


def _optional_nonnegative_int(value: Any) -> int | None:
    try:
        if value in {None, ""}:
            return None
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _safe_fingerprint(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    # Endpoint identity is expected to be a digest. Do not turn a raw URL into
    # a durable report field when a caller accidentally supplies one.
    if "://" in text or "/" in text or "=" in text:
        return None
    return text[:128]
