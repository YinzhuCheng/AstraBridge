from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .coding_kernel import ContextSection, build_context_budget, estimate_tool_schema_tokens, normalize_context_budget_policy
from .providers import classify_runtime_failure
from .provider_compatibility_smoke import compatibility_matrix_updates_from_smoke_report


COMPACT_VALIDATION_HARNESS_SCHEMA_VERSION = "astrabridge-compact-validation-harness-v1"


def synthetic_long_context_sections(*, provider_id: str, model_id: str, repeat_blocks: int = 180) -> list[ContextSection]:
    intro = (
        f"Synthetic long-context harness for {provider_id}/{model_id}. "
        "This case is secret-free and intentionally oversized so AstraBridge can exercise budget reporting, "
        "compact recommendation, and fallback guidance without persisting raw provider prompts."
    )
    project_summary = (
        "Workspace summary. Active repo contains multi-provider routing, capability adapters, runtime handoff state, "
        "tool execution metadata, and context compaction policy surfaces that must remain coherent after long-turn pressure."
    )
    oversized_map = "\n".join(
        f"src/module_{index:03d}.py :: exported behaviors, compact-relevant callsites, task state links, and runtime notes"
        for index in range(repeat_blocks)
    )
    history_digest = "\n".join(
        f"turn_{index:03d}: prior assistant reasoning summary, tool observations, and follow-up constraints"
        for index in range(repeat_blocks // 2)
    )
    rules = (
        "Do not persist raw secret-bearing prompts. Preserve only counts, dropped section ids, validation scope, "
        "fallback guidance, and post-compact continuation signals."
    )
    return [
        ContextSection("intro", "Intro", 0, intro, essential=True),
        ContextSection("project", "Project", 1, project_summary, essential=True),
        ContextSection("file_map", "Project File Map", 2, oversized_map, essential=False),
        ContextSection("history", "Task History", 3, history_digest, essential=False),
        ContextSection("rules", "Rules", 4, rules, essential=True),
    ]


def post_compact_continuation_state(*, token_last_updated_at: str, compacted_at: str) -> dict[str, Any]:
    compacted = _parse_timestamp(compacted_at)
    token_at = _parse_timestamp(token_last_updated_at)
    newer = compacted is not None and (token_at is None or compacted > token_at)
    if newer:
        return {
            "level": "compacted",
            "recommended_action": "health_check",
            "should_pause": False,
            "stale_context_estimate": True,
            "message": "Context was compacted after the latest token usage update. Send a short health check before continuing a long task.",
        }
    return {
        "level": "ok",
        "recommended_action": "continue",
        "should_pause": False,
        "stale_context_estimate": False,
        "message": "",
    }


def build_compact_validation_case(model: dict[str, Any], *, repeat_blocks: int | None = None) -> dict[str, Any]:
    provider_id = str(model.get("provider") or model.get("provider_id") or "")
    model_id = str(model.get("id") or model.get("model_id") or "")
    native_model = str(model.get("native_model") or model.get("model") or model_id)
    context_window = int(model.get("advertised_context_window") or model.get("context_window") or 0) or None
    effective_percent = int(model.get("effective_context_window_percent") or 80)
    auto_compact_token_limit = _optional_int(model.get("auto_compact_token_limit"))
    tool_output_token_limit = _optional_int(model.get("tool_output_token_limit"))
    context_support = dict(model.get("context_compaction_support") or {})
    context_policy = normalize_context_budget_policy(dict(model.get("context_budget_policy") or {}))
    tool_schema_token_estimate = estimate_tool_schema_tokens(model)
    sections = synthetic_long_context_sections(
        provider_id=provider_id,
        model_id=model_id,
        repeat_blocks=repeat_blocks if repeat_blocks is not None else _recommended_repeat_blocks(
            context_window=context_window,
            effective_context_window_percent=effective_percent,
            auto_compact_token_limit=auto_compact_token_limit,
            tool_schema_token_estimate=tool_schema_token_estimate,
        ),
    )
    _selected_text, budget = build_context_budget(
        sections=sections,
        provider_id=provider_id,
        model_id=native_model,
        context_window=context_window,
        effective_context_window_percent=effective_percent,
        auto_compact_token_limit=auto_compact_token_limit,
        tool_output_token_limit=tool_output_token_limit,
        manual_compact_status=str(context_support.get("manual_compact") or "app_server_native"),
        auto_compact_status=str(context_support.get("auto_compact") or "configured_unverified"),
        compact_summary_quality_status=str(context_support.get("structured_summary_quality") or "untested"),
        tool_schema_token_estimate=tool_schema_token_estimate,
        endpoint_protocol=str(model.get("wire_api") or "chat").strip().lower() or "chat",
        endpoint_fingerprint=f"dryrun-{provider_id or 'provider'}-{native_model or 'model'}".replace("/", "-"),
        endpoint_protocol_overhead_tokens=context_policy.get("endpoint_protocol_overhead_tokens"),
        endpoint_overhead_status=str(context_policy.get("endpoint_overhead_status") or "conservative"),
        advertised_context_window_status=str(context_policy.get("advertised_context_window_status") or "advertised"),
        supported_modalities=list(model.get("input_modalities") or ["text"]),
        output_reserve_tokens=context_policy.get("output_reserve_tokens"),
        output_reserve_status=str(context_policy.get("output_reserve_status") or "derived_conservative"),
        reasoning_artifact_policy=str(context_policy.get("reasoning_artifact_policy") or "neutral_summary_only"),
        reasoning_artifact_reserve_tokens=context_policy.get("reasoning_artifact_reserve_tokens"),
    )
    failure = classify_runtime_failure(
        json.dumps({"error": {"message": "context length exceeded", "provider": provider_id, "model": native_model}})
    ).to_payload()
    continuation = post_compact_continuation_state(
        token_last_updated_at="2026-07-05T12:00:00+09:00",
        compacted_at="2026-07-05T12:03:00+09:00",
    )
    budget_payload = budget.to_dict()
    usage_signal = {
        "declared_context_window": context_window,
        "advertised_context_window_tokens": budget_payload.get("advertised_context_window_tokens"),
        "verified_usable_coding_context_tokens": budget_payload.get("verified_usable_coding_context_tokens"),
        "usable_coding_context_status": budget_payload.get("usable_coding_context_status"),
        "effective_context_budget_tokens": budget_payload.get("effective_context_budget_tokens"),
        "compact_threshold_tokens": budget_payload.get("usable_prompt_budget_tokens"),
        "full_text_tokens": budget_payload.get("full_text_tokens"),
        "selected_text_tokens": budget_payload.get("selected_text_tokens"),
            "tool_schema_token_estimate": budget_payload.get("tool_schema_token_estimate"),
            "synthetic_repeat_blocks": repeat_blocks if repeat_blocks is not None else _recommended_repeat_blocks(
                context_window=context_window,
                effective_context_window_percent=effective_percent,
                auto_compact_token_limit=auto_compact_token_limit,
                tool_schema_token_estimate=tool_schema_token_estimate,
            ),
        }
    warnings: list[str] = []
    if budget_payload.get("auto_compact_status") != "verified":
        warnings.append(
            f"auto_compact_status={budget_payload.get('auto_compact_status')} remains metadata-only until provider-backed validation runs."
        )
    if budget_payload.get("compact_summary_quality_status") != "verified":
        warnings.append(
            f"compact_summary_quality_status={budget_payload.get('compact_summary_quality_status')} remains unverified until provider-backed validation runs."
        )
    case = {
        "case_id": f"{provider_id}-{native_model}-compact-harness".replace("/", "-"),
        "case_type": "dry_run_compact_validation",
        "capability_id": "thread.compact",
        "provider_id": provider_id,
        "model": native_model,
        "status": "pass",
        "context_window_summary": {
            "declared_context_window": context_window,
            "advertised_context_window_tokens": budget_payload.get("advertised_context_window_tokens"),
            "verified_usable_coding_context_tokens": budget_payload.get("verified_usable_coding_context_tokens"),
            "usable_coding_context_status": budget_payload.get("usable_coding_context_status"),
            "preflight_admission": budget_payload.get("preflight_admission"),
            "recommended_action": budget_payload.get("recommended_action"),
            "effective_context_budget_tokens": budget_payload.get("effective_context_budget_tokens"),
            "compact_threshold_tokens": budget_payload.get("usable_prompt_budget_tokens"),
            "full_text_tokens": budget_payload.get("full_text_tokens"),
            "selected_text_tokens": budget_payload.get("selected_text_tokens"),
            "selected_text_chars": budget_payload.get("selected_text_chars"),
            "dropped_section_ids": list(budget_payload.get("dropped_section_ids") or []),
            "truncated_section_ids": list(budget_payload.get("truncated_section_ids") or []),
            "compact_recommended": bool(budget_payload.get("compact_recommended")),
        },
        "budget_report": budget_payload,
        "context_limit_classification": {
            "category": failure.get("category"),
            "recommended_action": failure.get("recommended_action"),
            "compact_recommended": failure.get("compact_recommended"),
            "fork_recommended": failure.get("fork_recommended"),
        },
        "post_compact_continuation": continuation,
        "usage_signal": usage_signal,
        "reasons": [
            f"budget report built for declared context window {context_window}",
            f"context-limit classification recommends {failure.get('recommended_action')}",
            f"post-compact continuation recommends {continuation.get('recommended_action')}",
        ],
        "warnings": warnings,
        "validated_evidence_preview": {
            "validation_status": "pass",
            "validation_scope": [
                "dry_run_context_budget_report",
                "dry_run_context_limit_classification",
                "dry_run_post_compact_continuation",
            ],
            "usage_signals": usage_signal,
            "known_pitfalls": warnings,
            "notes": [
                "Dry-run harness only; provider-backed compact quality is deferred to the next step.",
                "Section texts are synthetic and are not persisted in the durable artifact output.",
            ],
        },
    }
    return case


def build_compact_validation_report(*, run_id: str, models: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    cases = [build_compact_validation_case(model) for model in models]
    counts = {status: sum(1 for case in cases if case.get("status") == status) for status in ["pass", "partial", "fail", "skipped", "blocked"]}
    report = {
        "schema_version": COMPACT_VALIDATION_HARNESS_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": created_at,
        "status": "fail" if counts["fail"] else "partial" if counts["partial"] else "pass",
        "counts": counts,
        "cases": cases,
        "acceptance": {
            "dry_run_tests_expected": True,
            "matrix_ready_output": True,
            "secret_free_artifacts_only": True,
        },
        "notes": [
            "This harness is intentionally dry-run only. It prepares compact/long-context evidence before provider-backed validation.",
            "Durable artifacts preserve counts, dropped section ids, recommendations, and continuation state without storing oversized raw prompts.",
        ],
    }
    report["matrix_updates"] = compatibility_matrix_updates_from_smoke_report(report)
    return report


def _optional_int(value: Any) -> int | None:
    try:
        if value in {None, ""}:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _recommended_repeat_blocks(
    *,
    context_window: int | None,
    effective_context_window_percent: int,
    auto_compact_token_limit: int | None,
    tool_schema_token_estimate: int,
) -> int:
    usable_budget = None
    if context_window:
        usable_budget = int(int(context_window) * (int(effective_context_window_percent or 80) / 100))
    if auto_compact_token_limit:
        usable_budget = min(int(auto_compact_token_limit), usable_budget or int(auto_compact_token_limit))
    if usable_budget is not None:
        usable_budget = max(256, usable_budget - int(tool_schema_token_estimate or 0))
    target_tokens = max(8_192, int(usable_budget or 8_192) + 4_096)
    return max(180, min(25_000, target_tokens // 38))


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
