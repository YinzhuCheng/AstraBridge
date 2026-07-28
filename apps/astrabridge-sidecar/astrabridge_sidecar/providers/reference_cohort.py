"""Deterministic, route-level provider reference cohort evaluation.

This evaluator deliberately does not open provider connections or promote a
route.  It binds the existing four-provider semantic corpus to exact catalog
models, then records what the current route contract can and cannot claim.
The result is intended for a bounded evidence run: it distinguishes a passing
deterministic adapter/continuity/tool/context contract from provider-backed
execution authority.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..coding_kernel import ContextSection, build_context_budget
from ..tool_action_ledger import ToolActionReceiptLedger
from .execution_route import EXECUTION_ROUTE_PROMOTION_STATES, resolve_execution_route
from .history_projector import HistoryProjector, NeutralMessage, ReasoningArtifact
from .registry import get_provider_profile
from .runtime_admission import resolve_runtime_route_admission
from .transports import transport_class_for_profile


REFERENCE_COHORT_SCHEMA_VERSION = "astrabridge-four-provider-reference-cohort-v1"
REFERENCE_COHORT_SUBJECTS = (
    {"provider_id": "qwen", "model_id": "qwen/qwen3.7-plus", "native_model": "qwen3.7-plus"},
    {"provider_id": "deepseek", "model_id": "deepseek/deepseek-v4-pro", "native_model": "deepseek-v4-pro"},
    {"provider_id": "kimi", "model_id": "kimi/kimi-k3", "native_model": "kimi-k3"},
    {"provider_id": "glm", "model_id": "glm/glm-5.2", "native_model": "glm-5.2"},
)
CODEX_CONTROL_SUBJECT = {"provider_id": "openai", "model_id": "openai/gpt-5.5", "native_model": "gpt-5.5"}


class _DeterministicTransportRouter:
    """Minimal adapter dependency used only for request-shape evaluation."""

    @staticmethod
    def apply_temperature_config(_profile: dict[str, Any], _payload: dict[str, Any], _model: str | None) -> None:
        return None


def build_reference_cohort_report(
    *,
    catalog_models: list[dict[str, Any]],
    semantic_corpus: dict[str, Any],
    run_id: str,
    ledger_root: Path,
    parser_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate the fixed external cohort without a network or provider call.

    ``ledger_root`` is an artifact directory owned by the current run.  The
    per-route receipts it creates contain only redacted/digested local action
    metadata and prove the receipt machinery's deterministic contract.
    """

    models_by_id = {
        str(item.get("id") or "").strip(): dict(item)
        for item in list(catalog_models or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    cases_by_model = {
        str(item.get("model_id") or "").strip(): dict(item)
        for item in list(semantic_corpus.get("cases") or [])
        if isinstance(item, dict) and str(item.get("model_id") or "").strip()
    }
    selected = [dict(subject) for subject in REFERENCE_COHORT_SUBJECTS]
    results = [
        _evaluate_subject(
            subject=subject,
            model=models_by_id.get(subject["model_id"]),
            semantic_case=cases_by_model.get(subject["model_id"]),
            target_subject=selected[(index + 1) % len(selected)],
            ledger_root=ledger_root,
        )
        for index, subject in enumerate(selected)
    ]
    control = _codex_control(models_by_id.get(CODEX_CONTROL_SUBJECT["model_id"]))
    classifications = [str(item.get("classification") or "blocked") for item in results]
    checks_pass = all(str(item.get("deterministic_validation", {}).get("status") or "") == "pass" for item in results)
    parser_status = str((parser_coverage or {}).get("status") or "not_run")
    report_status = "pass" if checks_pass and parser_status in {"pass", "not_run"} else "blocked"
    common_path = list(EXECUTION_ROUTE_PROMOTION_STATES[1:])
    kimi = next(item for item in results if item["subject"]["provider_id"] == "kimi")
    generic_path = list(kimi.get("promotion_path") or []) == common_path and all(
        list(item.get("promotion_path") or []) == common_path for item in results
    )
    return {
        "schema_version": REFERENCE_COHORT_SCHEMA_VERSION,
        "run_id": str(run_id),
        "status": report_status,
        "mode": "deterministic_provider_free",
        "provider_calls_attempted": False,
        "network_calls_attempted": False,
        "metadata_apply_attempted": False,
        "route_promotion_attempted": False,
        "selected_subjects": selected,
        "parser_coverage": _compact_parser_coverage(parser_coverage),
        "routes": results,
        "codex_control": control,
        "kimi_k3_generic_promotion_path": {
            "status": "pass" if generic_path else "blocked",
            "model_id": "kimi/kimi-k3",
            "shared_required_evidence_states": common_path,
            "kimi_only_bypass": False,
            "message": (
                "Kimi K3 uses the same documented-to-coding-route lifecycle as every selected external route; "
                "fixture evidence does not promote any catalog route."
                if generic_path
                else "Kimi K3's lifecycle diverged from the common external-route promotion path."
            ),
        },
        "classification_summary": {
            "verified": classifications.count("verified"),
            "partial": classifications.count("partial"),
            "reduced_authority": classifications.count("reduced_authority"),
            "blocked": classifications.count("blocked"),
            "deferred": classifications.count("deferred"),
        },
        "live_smoke": {
            "status": "deferred",
            "reason": "explicit_provider_call_authorization_and_secret_owning_runner_required",
            "automatic_retry_or_fallback": False,
        },
    }


def _evaluate_subject(
    *,
    subject: dict[str, str],
    model: dict[str, Any] | None,
    semantic_case: dict[str, Any] | None,
    target_subject: dict[str, str],
    ledger_root: Path,
) -> dict[str, Any]:
    if not isinstance(model, dict):
        return _blocked_subject(subject, "catalog_exact_model_missing", "Restore or select the exact catalog model before cohort validation.")
    if not isinstance(semantic_case, dict):
        return _blocked_subject(subject, "semantic_fixture_missing", "Add one exact semantic conformance fixture for this route.")
    if str(semantic_case.get("native_model") or "") != subject["native_model"]:
        return _blocked_subject(subject, "semantic_fixture_subject_mismatch", "Repair the fixture to bind the exact selected native model.")

    profile = _profile_for_subject(subject)
    route = resolve_execution_route(model, provider=profile)
    admission = resolve_runtime_route_admission(
        profile,
        model=model,
        requested_model=subject["native_model"],
        requested_effort="high",
        requested_permission_mode="auto",
        requested_execution_policy="standard",
    )
    route_admission = str(dict(route.get("driver") or {}).get("admission") or "review_only")
    semantic = _evaluate_semantic_case(profile, semantic_case)
    context = _evaluate_context(subject, model, profile, route)
    handoff = _evaluate_neutral_handoff(subject, target_subject)
    receipt = _evaluate_tool_receipt(subject, ledger_root)
    fallback = _evaluate_fallback(route, admission)
    checks = {
        "semantic_conformance": semantic,
        "neutral_handoff": handoff,
        "tool_receipt": receipt,
        "fallback": fallback,
        "context": context,
    }
    deterministic_pass = all(str(dict(item).get("status") or "") == "pass" for item in checks.values())
    classification = _classification(route_admission=route_admission, deterministic_pass=deterministic_pass)
    return {
        "subject": dict(subject),
        "route": _compact_route(route),
        "runtime_admission": _compact_runtime_admission(admission),
        "deterministic_validation": {"status": "pass" if deterministic_pass else "blocked", "checks": checks},
        "classification": classification,
        "promotion_path": list(EXECUTION_ROUTE_PROMOTION_STATES[1:]),
        "next_fix": _next_fix(route_admission),
    }


def _profile_for_subject(subject: dict[str, str]) -> dict[str, Any]:
    profile = dict(get_provider_profile(subject["provider_id"]).to_default_profile())
    profile["model"] = subject["native_model"]
    profile["provider_family"] = subject["provider_id"]
    return profile


def _evaluate_semantic_case(profile: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    adapter_class = transport_class_for_profile(profile, provider_family=str(case["provider_id"]))
    adapter = adapter_class(_DeterministicTransportRouter(), profile)
    request = deepcopy(dict(case.get("request") or {}))
    upstream = adapter.build_request(request)
    normalized = adapter.normalize_response(deepcopy(case.get("upstream_response")), request)
    events = adapter.client_stream_events_from_upstream_json(deepcopy(case.get("upstream_response")), request)
    contract = adapter.semantic_conformance_contract()
    error = adapter.classify_error(str(case.get("error_message") or ""), model_id=str(case.get("model_id") or ""))
    tool_names = [str(item.name) for item in list(normalized.tool_calls or [])]
    checks = {
        "adapter_matches_fixture": adapter.describe() == str(case.get("adapter") or ""),
        "wire_api_matches_fixture": adapter.wire_api() == str(case.get("wire_api") or ""),
        "native_model_selected": str(upstream.get("model") or "") == str(case.get("native_model") or ""),
        "text_normalized": normalized.text == str(case.get("expected_text") or ""),
        "tool_normalized": tool_names == [str(case.get("expected_tool_name") or "")],
        "stream_completed": any(item.get("type") == "response.completed" for item in events if isinstance(item, dict)),
        "tool_definitions_still_evidence_gated": str(dict(contract.get("request") or {}).get("tool_definitions") or "") == "requires_execution_route_evidence",
        "error_taxonomy_matches": str(error.get("category") or "") == str(case.get("expected_error_category") or ""),
    }
    return {
        "status": "pass" if all(checks.values()) else "blocked",
        "adapter": adapter.describe(),
        "wire_api": adapter.wire_api(),
        "checks": checks,
    }


def _evaluate_context(
    subject: dict[str, str],
    model: dict[str, Any],
    profile: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, Any]:
    _selected, report = build_context_budget(
        sections=[ContextSection("cohort_prompt", "Reference Cohort Prompt", 0, "Validate this route without a provider call.", essential=True)],
        provider_id=subject["provider_id"],
        model_id=subject["native_model"],
        context_window=_positive_int(model.get("advertised_context_window")),
        effective_context_window_percent=int(profile.get("effective_context_window_percent") or 80),
        auto_compact_token_limit=_positive_int(profile.get("auto_compact_token_limit")),
        tool_schema_token_estimate=128,
        endpoint_protocol=str(profile.get("wire_api") or "") or None,
        endpoint_fingerprint=str(dict(route.get("endpoint") or {}).get("fingerprint") or "") or None,
        endpoint_overhead_status="conservative",
        advertised_context_window_status="documented",
        output_reserve_tokens=256,
    )
    payload = report.to_dict()
    admitted = str(payload.get("preflight_admission") or "").startswith("admitted")
    return {
        "status": "pass" if admitted else "blocked",
        "preflight_admission": payload.get("preflight_admission"),
        "usable_coding_context_status": payload.get("usable_coding_context_status"),
        "safe_context_budget_established": bool(payload.get("safe_context_budget_established")),
        "endpoint_overhead_status": payload.get("endpoint_overhead_status"),
    }


def _evaluate_neutral_handoff(subject: dict[str, str], target_subject: dict[str, str]) -> dict[str, Any]:
    projection = HistoryProjector().project(
        source_provider=subject["provider_id"],
        target_provider=target_subject["provider_id"],
        source_model_id=subject["native_model"],
        target_model_id=target_subject["native_model"],
        neutral_messages=[NeutralMessage(role="user", text="Continue from the visible task summary.")],
        artifacts=[
            ReasoningArtifact(
                provider_id=subject["provider_id"],
                model_id=subject["native_model"],
                kind="reasoning_state",
                replayable=True,
                payload={"visible_summary": "Provider-private reasoning is intentionally not replayed cross-provider."},
                provenance={},
            )
        ],
    )
    dropped = int(projection.dropped_artifacts or 0)
    replayed = int(projection.replayable_artifact_count or 0)
    return {
        "status": "pass" if dropped >= 1 and replayed == 0 else "blocked",
        "target_provider_id": target_subject["provider_id"],
        "dropped_provider_private_artifacts": dropped,
        "replayed_provider_private_artifacts": replayed,
        "policy": "neutral_summary_only",
    }


def _evaluate_tool_receipt(subject: dict[str, str], ledger_root: Path) -> dict[str, Any]:
    workspace_root = Path(ledger_root) / subject["provider_id"] / subject["native_model"]
    ledger = ToolActionReceiptLedger(workspace_root)
    digest = sha256(subject["model_id"].encode("utf-8")).hexdigest()
    envelope = ledger.build_envelope(
        tool_name="create_checkpoint",
        arguments={"description": "Reference cohort deterministic receipt."},
        lineage={
            "task_id": "reference-cohort",
            "thread_id": f"cohort-{subject['provider_id']}",
            "turn_id": "cohort-turn",
            "tool_call_id": f"cohort-{subject['provider_id']}-checkpoint",
        },
        authority={"tier": "C", "decision": "review_only", "permission_mode": "ask"},
        workspace={"workspace_version": digest, "checkpoint_version": "cohort-baseline"},
        idempotency_key=f"cohort-{subject['provider_id']}-{digest[:12]}",
        source="reference_cohort",
    )
    admitted = ledger.admit(envelope)
    decision = str(admitted.get("decision") or "")
    receipt = dict(admitted.get("receipt") or {})
    execution_started = False
    if decision == "execute":
        receipt = ledger.complete(envelope, result={"ok": True, "status": "completed"})
        execution_started = True
    return {
        "status": "pass" if decision == "execute" and receipt.get("state") == "completed" else "blocked",
        "decision": decision,
        "receipt_state": receipt.get("state"),
        "execution_started": execution_started,
        "ledger_path": str(ledger.path),
        "replay_policy": "never_replay_side_effects_automatically",
        "route_tool_exposure": "separate_runtime_admission_required",
    }


def _evaluate_fallback(route: dict[str, Any], admission: dict[str, Any]) -> dict[str, Any]:
    targets = [str(item) for item in list(dict(route.get("fallback") or {}).get("target_models") or []) if str(item).strip()]
    automatic = bool(dict(admission.get("fallback") or {}).get("automatic_fallback"))
    return {
        "status": "pass" if not automatic else "blocked",
        "target_models": targets,
        "selection_policy": "explicit_user_selection_required",
        "automatic_fallback": automatic,
    }


def _compact_route(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_id": route.get("route_id"),
        "subject": dict(route.get("subject") or {}),
        "configured_driver": dict(route.get("driver") or {}).get("configured_id"),
        "execution_driver": dict(route.get("driver") or {}).get("execution_id"),
        "admission": dict(route.get("driver") or {}).get("admission"),
        "evidence_state": dict(route.get("evidence") or {}).get("effective_state"),
        "verification_status": dict(route.get("evidence") or {}).get("verification_status"),
        "evidence_reasons": list(dict(route.get("evidence") or {}).get("reasons") or []),
        "default_route_eligible": bool(route.get("default_route_eligible")),
    }


def _compact_runtime_admission(admission: dict[str, Any]) -> dict[str, Any]:
    effective = dict(admission.get("effective") or {})
    return {
        "status": admission.get("status"),
        "presentation_state": admission.get("presentation_state"),
        "effective_execution_driver": effective.get("execution_driver"),
        "effective_execution_policy": effective.get("execution_policy"),
        "effective_permission_mode": effective.get("permission_mode"),
        "degradation_reasons": [str(item.get("code") or "") for item in list(dict(admission.get("degradation") or {}).get("reasons") or []) if isinstance(item, dict)],
    }


def _next_fix(route_admission: str) -> dict[str, Any]:
    if route_admission in {"default_eligible", "verified_non_default"}:
        return {"status": "none", "message": "Current route evidence is already coding-route qualified."}
    return {
        "status": "required",
        "next_gate": "execution_route_adapter_dry_run",
        "remaining_evidence_states": list(EXECUTION_ROUTE_PROMOTION_STATES[1:]),
        "provider_smoke_requires_explicit_user_gate_after_adapter_dry_run": True,
        "message": "Run the exact route's adapter dry-run, then an explicitly authorized provider smoke, tool contract, and coding-route verification; do not promote provider-wide evidence.",
    }


def _classification(*, route_admission: str, deterministic_pass: bool) -> str:
    if not deterministic_pass:
        return "blocked"
    if route_admission == "default_eligible":
        return "verified"
    if route_admission == "verified_non_default":
        return "partial"
    if route_admission in {"review_only", "tool_contract_only"}:
        return "reduced_authority"
    return "deferred"


def _codex_control(model: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(model, dict):
        return {
            "status": "deferred",
            "subject": dict(CODEX_CONTROL_SUBJECT),
            "reason": "catalog_exact_model_missing",
        }
    profile = _profile_for_subject(CODEX_CONTROL_SUBJECT)
    route = resolve_execution_route(model, provider=profile)
    return {
        "status": "recorded",
        "subject": dict(CODEX_CONTROL_SUBJECT),
        "configured_driver": dict(route.get("driver") or {}).get("configured_id"),
        "current_admission": dict(route.get("driver") or {}).get("admission"),
        "default_route_eligible": bool(route.get("default_route_eligible")),
        "message": "Control only: Codex/App Server is not granted an external provider-route promotion bypass.",
    }


def _blocked_subject(subject: dict[str, str], code: str, message: str) -> dict[str, Any]:
    return {
        "subject": dict(subject),
        "route": {},
        "runtime_admission": {"status": "blocked", "degradation_reasons": [code]},
        "deterministic_validation": {"status": "blocked", "checks": {}},
        "classification": "blocked",
        "promotion_path": list(EXECUTION_ROUTE_PROMOTION_STATES[1:]),
        "next_fix": {"status": "required", "next_gate": code, "message": message},
    }


def _compact_parser_coverage(value: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    return {
        "status": raw.get("status") or "not_run",
        "deterministic": raw.get("deterministic"),
        "provider_calls_attempted": bool(raw.get("provider_calls_attempted", False)),
        "network_calls_attempted": bool(raw.get("network_calls_attempted", False)),
        "providers": dict(raw.get("providers") or {}),
    }


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


__all__ = [
    "CODEX_CONTROL_SUBJECT",
    "REFERENCE_COHORT_SCHEMA_VERSION",
    "REFERENCE_COHORT_SUBJECTS",
    "build_reference_cohort_report",
]
