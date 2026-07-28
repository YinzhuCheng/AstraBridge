from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..common import now_iso, read_json, write_json
from ..model_catalog import effective_model_records
from .artifacts import ensure_agentic_update_run_layout, validate_agentic_update_artifact_path
from .contracts import assert_secret_free_agentic_update_payload, normalize_update_scope_contract, validate_update_proposal
from .route_promotion import (
    deprovision_route_record,
    documented_route_record_for_candidate,
    normalize_route_promotion_section,
)


AGENTIC_UPDATE_DIFF_SCHEMA_VERSION = "astrabridge-agentic-update-diff-v1"
AGENTIC_UPDATE_PROPOSAL_MARKDOWN_FILENAME = "diffs/proposal.md"
RISK_CLASSES = (
    "docs_only",
    "metadata_only",
    "requires_provider_smoke",
    "requires_kernel_smoke",
    "requires_adapter_review",
    "blocked_manual_review",
)
LONG_CONTEXT_THRESHOLD = 200_000
_RISK_RANK = {risk: index for index, risk in enumerate(RISK_CLASSES)}


def build_agentic_update_diff(
    *,
    workspace_root: str | Path,
    run_id: str,
    run_contract: dict[str, Any],
    parser_output: dict[str, Any] | None = None,
    kernel_candidate_output: dict[str, Any] | None = None,
    current_models: list[dict[str, Any]] | None = None,
    complete_provider_snapshot: bool = False,
    route_promotion_events: list[dict[str, Any]] | None = None,
    update_proposal: bool = True,
) -> dict[str, Any]:
    contract = normalize_update_scope_contract(run_contract)
    layout = ensure_agentic_update_run_layout(workspace_root, run_id)
    provider_candidates = _provider_model_candidates(parser_output)
    kernel_candidates = _kernel_candidates(kernel_candidate_output)
    current = _current_model_index(current_models)
    changes: list[dict[str, Any]] = []
    warnings: list[str] = []

    for candidate in provider_candidates:
        changes.extend(_diff_provider_candidate(candidate, current.get(candidate["model_id"])))

    if complete_provider_snapshot:
        candidate_model_ids = {candidate["model_id"] for candidate in provider_candidates}
        scoped_providers = set(contract.get("providers") or [])
        for model_id, model in sorted(current.items()):
            provider_id = str(model.get("provider_id") or "").strip()
            if scoped_providers and provider_id not in scoped_providers:
                continue
            if model_id not in candidate_model_ids:
                changes.append(_removed_model_change(model))
    else:
        warnings.append("removed_model_detection_skipped_without_complete_provider_snapshot")

    for candidate in kernel_candidates:
        changes.append(_kernel_candidate_change(candidate))

    route_promotion = _build_route_promotion_section(
        provider_candidates=provider_candidates,
        current=current,
        explicit_events=route_promotion_events,
    )
    for record in list(route_promotion.get("records") or []):
        if str(record.get("action") or "") != "document":
            changes.append(_route_lifecycle_change(record, current.get(str(record.get("model_id") or ""))))

    merged_changes = _merge_change_sources(changes)
    risk_class = _highest_risk([change["risk_class"] for change in merged_changes]) or "docs_only"
    generated_at = now_iso()
    diff_path = Path(layout["files"]["proposal_diff"])
    markdown_path = validate_agentic_update_artifact_path(workspace_root, run_id, AGENTIC_UPDATE_PROPOSAL_MARKDOWN_FILENAME)
    route_promotion_path = Path(layout["files"]["route_promotion_proposal"])
    diff = {
        "schema_version": AGENTIC_UPDATE_DIFF_SCHEMA_VERSION,
        "generated_at": generated_at,
        "run_id": run_id,
        "run_contract": contract,
        "status": "changes_detected" if merged_changes else "empty",
        "risk_class": risk_class,
        "summary": {
            "change_count": len(merged_changes),
            "risk_counts": _risk_counts(merged_changes),
            "provider_model_candidate_count": len(provider_candidates),
            "kernel_candidate_count": len(kernel_candidates),
            "route_promotion_record_count": len(list(route_promotion.get("records") or [])),
            "complete_provider_snapshot": bool(complete_provider_snapshot),
        },
        "changes": merged_changes,
        "artifact_paths": {
            "proposal_diff": str(diff_path),
            "proposal_markdown": str(markdown_path),
            "route_promotion_proposal": str(route_promotion_path),
        },
        "route_promotion": route_promotion,
        "warnings": warnings,
    }
    markdown = render_agentic_update_proposal_markdown(diff)
    assert_secret_free_agentic_update_payload(diff, label="agentic_update_diff")
    assert_secret_free_agentic_update_payload(markdown, label="agentic_update_diff_markdown")
    write_json(diff_path, diff)
    write_json(route_promotion_path, route_promotion)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")
    if update_proposal:
        _update_existing_proposal(layout["files"]["proposal"], diff)
    return diff


def render_agentic_update_proposal_markdown(diff: dict[str, Any]) -> str:
    lines = [
        "# Agentic Update Proposal",
        "",
        f"- Run id: `{diff.get('run_id')}`",
        f"- Status: `{diff.get('status')}`",
        f"- Overall risk: `{diff.get('risk_class')}`",
        f"- Change count: `{dict(diff.get('summary') or {}).get('change_count', 0)}`",
        "",
        "## Changes",
        "",
        "| Change | Risk | Target | Evidence | Current State |",
        "| --- | --- | --- | --- | --- |",
    ]
    for change in diff.get("changes") or []:
        evidence = ", ".join(_source_ref_label(item) for item in change.get("source_refs") or []) or "none"
        current_refs = ", ".join(_current_ref_label(item) for item in change.get("current_state_refs") or []) or "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(str(change.get("change_type") or "")),
                    _md_cell(str(change.get("risk_class") or "")),
                    _md_cell(str(change.get("target") or change.get("model_id") or change.get("candidate_id") or "")),
                    _md_cell(evidence),
                    _md_cell(current_refs),
                ]
            )
            + " |"
        )
    route_promotion = dict(diff.get("route_promotion") or {})
    route_records = [item for item in list(route_promotion.get("records") or []) if isinstance(item, dict)]
    if route_records:
        lines.extend(
            [
                "",
                "## Execution-Route Lifecycle",
                "",
                "| Action | Model | From | To | Required gates |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for record in route_records:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(str(record.get("action") or "")),
                        _md_cell(str(record.get("model_id") or "")),
                        _md_cell(str(record.get("previous_state") or "documented")),
                        _md_cell(str(record.get("target_state") or "documented")),
                        _md_cell(", ".join(str(item) for item in list(record.get("required_gates") or [])) or "none"),
                    ]
                )
                + " |"
            )
    if diff.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        for warning in diff["warnings"]:
            lines.append(f"- `{warning}`")
    return "\n".join(lines).rstrip() + "\n"


def _provider_model_candidates(parser_output: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not parser_output:
        return []
    raw = parser_output.get("proposals") if isinstance(parser_output, dict) else None
    if not isinstance(raw, list):
        return []
    return [_normalize_provider_candidate(item) for item in raw if isinstance(item, dict)]


def _kernel_candidates(kernel_candidate_output: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not kernel_candidate_output:
        return []
    raw = kernel_candidate_output.get("candidates") if isinstance(kernel_candidate_output, dict) else None
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _current_model_index(current_models: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    records = current_models if current_models is not None else effective_model_records()
    indexed: dict[str, dict[str, Any]] = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_current_model(item)
        model_id = normalized.get("model_id")
        if model_id:
            indexed[str(model_id)] = normalized
    return indexed


def _normalize_provider_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(candidate.get("provider_id") or "").strip()
    model_id = str(candidate.get("model_id") or "").strip()
    native_model = str(candidate.get("native_model") or "").strip()
    if not model_id and provider_id and native_model:
        model_id = f"{provider_id}/{native_model}"
    metadata = dict(candidate.get("candidate_metadata") or {})
    return {
        "proposal_id": str(candidate.get("proposal_id") or model_id).strip(),
        "provider_id": provider_id or (model_id.split("/", 1)[0] if "/" in model_id else ""),
        "model_id": model_id,
        "native_model": native_model or (model_id.split("/", 1)[1] if "/" in model_id else model_id),
        "display_name": str(candidate.get("display_name") or native_model or model_id).strip(),
        "metadata": {
            "advertised_context_window": _int_or_none(metadata.get("advertised_context_window")),
            "input_modalities": _string_list(metadata.get("input_modalities")) or ["text"],
            "supported_reasoning_levels": _string_list(metadata.get("supported_reasoning_levels")),
            "default_reasoning_level": _optional_string(metadata.get("default_reasoning_level")),
            "native_supported_reasoning_levels": _string_list(metadata.get("native_supported_reasoning_levels")),
            "native_default_reasoning_level": _optional_string(metadata.get("native_default_reasoning_level")),
            "reasoning_effort_mapping": dict(metadata.get("reasoning_effort_mapping") or {}),
            "pricing": _normalize_pricing(metadata.get("pricing")),
            "deprecated": bool(metadata.get("deprecated", False)),
            "deprecated_after": _optional_string(metadata.get("deprecated_after")),
            "default_for_provider": bool(metadata.get("default_for_provider", False)),
            "recommended": bool(metadata.get("recommended", False)),
            "confidence": _optional_string(metadata.get("confidence")) or "low",
        },
        "adapter_requirements": dict(candidate.get("adapter_requirements") or {}),
        "capability_claims": dict(candidate.get("capability_claims") or {}),
        "source_refs": list(candidate.get("source_refs") or []),
        "warnings": list(candidate.get("warnings") or []),
    }


def _normalize_current_model(model: dict[str, Any]) -> dict[str, Any]:
    provider_id = str(model.get("provider") or model.get("provider_id") or "").strip()
    native_model = str(model.get("native_model") or model.get("model") or "").strip()
    model_id = str(model.get("id") or model.get("model_id") or "").strip()
    if not model_id and provider_id and native_model:
        model_id = f"{provider_id}/{native_model}"
    return {
        "model_id": model_id,
        "provider_id": provider_id or (model_id.split("/", 1)[0] if "/" in model_id else ""),
        "native_model": native_model or (model_id.split("/", 1)[1] if "/" in model_id else model_id),
        "display_name": str(model.get("display_name") or model.get("displayName") or native_model or model_id).strip(),
        "metadata": {
            "advertised_context_window": _int_or_none(model.get("advertised_context_window") or model.get("context_window")),
            "input_modalities": _string_list(model.get("input_modalities") or model.get("modalities")) or ["text"],
            "supported_reasoning_levels": _string_list(model.get("supported_reasoning_levels") or model.get("reasoning_modes")),
            "default_reasoning_level": _optional_string(model.get("default_reasoning_level")),
            "native_supported_reasoning_levels": _string_list(model.get("native_supported_reasoning_levels")),
            "native_default_reasoning_level": _optional_string(model.get("native_default_reasoning_level")),
            "reasoning_effort_mapping": dict(model.get("reasoning_effort_mapping") or {}),
            "pricing": _normalize_pricing(model),
            "deprecated": bool(model.get("deprecated", False)),
            "deprecated_after": _optional_string(model.get("deprecated_after")),
            "default_for_provider": bool(model.get("default_for_provider", False)),
            "recommended": bool(model.get("recommended", False)),
        },
        "adapter_requirements": {
            "reasoning_parameter": _optional_string(model.get("reasoning_parameter")),
            "codex_to_provider_reasoning_effort": dict(model.get("reasoning_effort_mapping") or {}),
        },
        "execution_route_evidence": deepcopy(model.get("execution_route_evidence") or {}),
        "execution_route": deepcopy(model.get("execution_route") or {}),
        "capability_claims": _current_capability_claims(model),
        "current_state_refs": _current_state_refs(model, model_id),
    }


def _diff_provider_candidate(candidate: dict[str, Any], current: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not candidate["model_id"]:
        return [
            _change(
                "blocked_manual_review",
                "invalid_model_candidate",
                "unknown",
                candidate,
                current,
                reasons=["missing_model_id"],
                details={"candidate": deepcopy(candidate)},
            )
        ]
    if current is None:
        reasons = _new_model_risk_reasons(candidate)
        documented_metadata_risk = _risk_for_reasons(reasons, base="metadata_only")
        return [
            _change(
                documented_metadata_risk,
                "added_model",
                candidate["model_id"],
                candidate,
                current,
                reasons=reasons,
                details={
                    "candidate_metadata": deepcopy(candidate["metadata"]),
                    "adapter_requirements": deepcopy(candidate.get("adapter_requirements") or {}),
                    "documented_metadata_apply_eligible": True,
                    "documented_metadata_apply_risk": documented_metadata_risk,
                },
            )
        ]

    changes: list[dict[str, Any]] = []
    current_metadata = current["metadata"]
    candidate_metadata = candidate["metadata"]
    field_pairs = (
        ("advertised_context_window", "changed_context_window"),
        ("input_modalities", "changed_modalities"),
        ("supported_reasoning_levels", "changed_reasoning"),
        ("default_reasoning_level", "changed_default_reasoning"),
        ("pricing", "changed_pricing"),
        ("default_for_provider", "changed_default_model"),
        ("recommended", "changed_recommended_hint"),
    )
    candidate_warnings = set(str(item) for item in candidate.get("warnings") or [])
    for field, change_type in field_pairs:
        before = current_metadata.get(field)
        after = candidate_metadata.get(field)
        if _candidate_field_is_unknown(field, after, candidate_warnings):
            continue
        if _same_value(before, after):
            continue
        reasons = _field_risk_reasons(field, before, after)
        changes.append(
            _change(
                _risk_for_reasons(reasons, base=_base_risk_for_field(field)),
                change_type,
                candidate["model_id"],
                candidate,
                current,
                reasons=reasons,
                details={"field": field, "current": before, "candidate": after},
            )
        )

    if bool(current_metadata.get("deprecated")) != bool(candidate_metadata.get("deprecated")) or (
        candidate_metadata.get("deprecated_after") and candidate_metadata.get("deprecated_after") != current_metadata.get("deprecated_after")
    ):
        change_type = "deprecated_model" if candidate_metadata.get("deprecated") else "undeprecated_model"
        risk = "metadata_only" if candidate_metadata.get("deprecated") else "requires_adapter_review"
        changes.append(
            _change(
                risk,
                change_type,
                candidate["model_id"],
                candidate,
                current,
                reasons=["deprecation_state_changed"],
                details={
                    "current": {
                        "deprecated": current_metadata.get("deprecated"),
                        "deprecated_after": current_metadata.get("deprecated_after"),
                    },
                    "candidate": {
                        "deprecated": candidate_metadata.get("deprecated"),
                        "deprecated_after": candidate_metadata.get("deprecated_after"),
                    },
                },
            )
        )

    for capability, claim in sorted(candidate["capability_claims"].items()):
        declared = bool(dict(claim or {}).get("declared", False))
        current_declared = bool(dict(current["capability_claims"].get(capability) or {}).get("declared", False))
        if declared and not current_declared:
            changes.append(
                _change(
                    "requires_provider_smoke",
                    "changed_capability_claim",
                    candidate["model_id"],
                    candidate,
                    current,
                    reasons=[f"unverified_{capability}_claim"],
                    details={"capability": capability, "candidate_declared": True, "verified": False},
                )
            )

    adapter_reasons = _adapter_review_reasons(candidate, current)
    if adapter_reasons:
        changes.append(
            _change(
                "requires_adapter_review",
                "transport_schema_review_required",
                candidate["model_id"],
                candidate,
                current,
                reasons=adapter_reasons,
                details={"warnings": list(candidate.get("warnings") or [])},
            )
        )
    return changes


def _build_route_promotion_section(
    *,
    provider_candidates: list[dict[str, Any]],
    current: dict[str, dict[str, Any]],
    explicit_events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    raw_records = [dict(item) for item in list(explicit_events or []) if isinstance(item, dict)]
    explicit_section = normalize_route_promotion_section({"records": raw_records})
    records = [dict(item) for item in list(explicit_section.get("records") or [])]
    explicit_models = {str(item.get("model_id") or "") for item in records}

    for candidate in provider_candidates:
        model_id = str(candidate.get("model_id") or "")
        model = current.get(model_id)
        if model is None and model_id not in explicit_models:
            records.append(documented_route_record_for_candidate(candidate))
            continue
        if model is None or model_id in explicit_models:
            continue
        if _adapter_review_reasons(candidate, model):
            record = deprovision_route_record(
                model,
                action="downgrade",
                reason="adapter_contract_changed_requires_route_depromotion",
            )
            if record:
                records.append(record)

    for model_id, model in current.items():
        if model_id in explicit_models:
            continue
        evidence = dict(model.get("execution_route_evidence") or {})
        if not evidence:
            continue
        expired = deprovision_route_record(model, action="expire", reason="route_evidence_expired")
        if expired:
            records.append(expired)
            continue
        route = dict(model.get("execution_route") or {})
        previous_subject = dict(evidence.get("subject") or {})
        endpoint_fingerprint = str(dict(route.get("endpoint") or {}).get("fingerprint") or "")
        adapter_signature = str(dict(route.get("adapter") or {}).get("signature") or "")
        if endpoint_fingerprint and endpoint_fingerprint != str(previous_subject.get("endpoint_fingerprint") or ""):
            record = deprovision_route_record(
                model,
                action="downgrade",
                reason="endpoint_fingerprint_changed_requires_route_depromotion",
            )
        elif adapter_signature and adapter_signature != str(previous_subject.get("adapter_signature") or ""):
            record = deprovision_route_record(
                model,
                action="downgrade",
                reason="adapter_signature_changed_requires_route_depromotion",
            )
        else:
            record = None
        if record:
            records.append(record)

    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique[str(record.get("record_id") or "")] = record
    return normalize_route_promotion_section({"records": list(unique.values())})


def _route_lifecycle_change(record: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    action = str(record.get("action") or "")
    target_state = str(record.get("target_state") or "documented")
    if action == "promote":
        change_type = "route_promoted"
        risk = "requires_adapter_review" if target_state in {"tool_contract_passed", "coding_route_verified", "default_route_eligible"} else (
            "requires_provider_smoke" if target_state == "provider_smoke_passed" else "metadata_only"
        )
    elif action == "expire":
        change_type = "route_evidence_expired"
        risk = "metadata_only"
    elif action == "rollback":
        change_type = "route_rollback_requested"
        risk = "metadata_only"
    else:
        change_type = "route_downgraded"
        risk = "metadata_only"
    provenance = dict(record.get("source_provenance") or {})
    source_refs = [
        {
            "source_id": provenance.get("record_id"),
            "source_url": ref,
        }
        for ref in list(record.get("evidence_refs") or [])
    ]
    return {
        "change_id": f"{change_type}-{_slug(str(record.get('record_id') or record.get('model_id') or 'route'))}",
        "change_type": change_type,
        "risk_class": risk,
        "target": record.get("model_id"),
        "model_id": record.get("model_id"),
        "provider_id": record.get("provider_id"),
        "reasons": [record.get("reason")],
        "details": {
            "route_promotion_record_id": record.get("record_id"),
            "action": action,
            "previous_state": record.get("previous_state"),
            "target_state": target_state,
            "route_subject": deepcopy(record.get("route_subject") or {}),
        },
        "source_refs": source_refs,
        "current_state_refs": deepcopy((current or {}).get("current_state_refs") or []),
        "validation_requirements": _dedupe(
            [*_validation_requirements(risk), *list(record.get("required_gates") or [])]
        ),
    }


def _removed_model_change(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "change_id": f"removed-model-{_slug(model['model_id'])}",
        "change_type": "removed_model",
        "risk_class": "blocked_manual_review",
        "target": model["model_id"],
        "model_id": model["model_id"],
        "provider_id": model["provider_id"],
        "reasons": ["model_missing_from_complete_provider_snapshot"],
        "details": {
            "current_metadata": deepcopy(model["metadata"]),
            "candidate": None,
        },
        "source_refs": [],
        "current_state_refs": deepcopy(model["current_state_refs"]),
        "validation_requirements": _validation_requirements("blocked_manual_review"),
    }


def _kernel_candidate_change(candidate: dict[str, Any]) -> dict[str, Any]:
    version = str(candidate.get("version") or "unknown").strip()
    candidate_id = str(candidate.get("candidate_id") or f"codex-kernel-{version}").strip()
    return {
        "change_id": f"codex-kernel-candidate-{_slug(candidate_id)}",
        "change_type": "codex_kernel_candidate",
        "risk_class": "requires_kernel_smoke",
        "target": version,
        "candidate_id": candidate_id,
        "reasons": ["codex_kernel_candidate_requires_probe_and_smoke"],
        "details": {
            "version": version,
            "release_date": candidate.get("release_date"),
            "platforms": list(candidate.get("platforms") or []),
            "distribution": deepcopy(candidate.get("distribution") or {}),
        },
        "source_refs": deepcopy(candidate.get("source_refs") or []),
        "current_state_refs": [{"kind": "codex_kernel_matrix", "reference": "PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md"}],
        "validation_requirements": _validation_requirements("requires_kernel_smoke"),
    }


def _change(
    risk_class: str,
    change_type: str,
    target: str,
    candidate: dict[str, Any],
    current: dict[str, Any] | None,
    *,
    reasons: list[str],
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "change_id": f"{change_type}-{_slug(target)}",
        "change_type": change_type,
        "risk_class": risk_class,
        "target": target,
        "model_id": candidate.get("model_id"),
        "provider_id": candidate.get("provider_id"),
        "reasons": reasons,
        "details": details,
        "source_refs": deepcopy(candidate.get("source_refs") or []),
        "current_state_refs": deepcopy((current or {}).get("current_state_refs") or []),
        "validation_requirements": _validation_requirements(risk_class),
    }


def _merge_change_sources(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for change in changes:
        key = str(change.get("change_id") or "")
        if not key or key not in merged:
            merged[key] = change
            continue
        existing = merged[key]
        existing["risk_class"] = _highest_risk([existing["risk_class"], change["risk_class"]]) or existing["risk_class"]
        existing["reasons"] = _dedupe([*existing.get("reasons", []), *change.get("reasons", [])])
    return list(merged.values())


def _new_model_risk_reasons(candidate: dict[str, Any]) -> list[str]:
    reasons = ["new_model_requires_catalog_review"]
    context = candidate["metadata"].get("advertised_context_window")
    if context and int(context) >= LONG_CONTEXT_THRESHOLD:
        reasons.append("long_context_claim_requires_provider_smoke")
    for modality in candidate["metadata"].get("input_modalities") or []:
        if modality in {"image", "audio", "video"}:
            reasons.append(f"{modality}_modality_requires_provider_smoke")
    for capability, claim in sorted(candidate.get("capability_claims", {}).items()):
        if bool(dict(claim or {}).get("declared", False)):
            reasons.append(f"unverified_{capability}_claim")
    reasons.extend(_adapter_review_reasons(candidate, None))
    return _dedupe(reasons)


def _field_risk_reasons(field: str, before: Any, after: Any) -> list[str]:
    if field == "advertised_context_window":
        before_int = _int_or_none(before)
        after_int = _int_or_none(after)
        if after_int and after_int >= LONG_CONTEXT_THRESHOLD and (before_int is None or after_int > before_int):
            return ["long_context_claim_requires_provider_smoke"]
        return ["context_window_changed"]
    if field == "input_modalities":
        added = sorted(set(_string_list(after)).difference(_string_list(before)))
        risky = [item for item in added if item in {"image", "audio", "video"}]
        return [f"{item}_modality_requires_provider_smoke" for item in risky] or ["modalities_changed"]
    if field == "supported_reasoning_levels":
        return ["reasoning_modes_changed_requires_provider_smoke"]
    if field == "pricing":
        return ["pricing_changed"]
    if field in {"default_for_provider", "recommended", "default_reasoning_level"}:
        return [f"{field}_changed"]
    return [f"{field}_changed"]


def _base_risk_for_field(field: str) -> str:
    if field == "pricing":
        return "docs_only"
    if field in {"default_for_provider", "recommended", "default_reasoning_level", "advertised_context_window"}:
        return "metadata_only"
    if field in {"input_modalities", "supported_reasoning_levels"}:
        return "requires_provider_smoke"
    return "metadata_only"


def _candidate_field_is_unknown(field: str, value: Any, warnings: set[str]) -> bool:
    if field == "advertised_context_window":
        return value is None and "missing_context_window_defaulted_unknown" in warnings
    if field == "supported_reasoning_levels":
        return not _string_list(value) and "missing_reasoning_modes_defaulted_empty" in warnings
    if field == "input_modalities":
        return _string_list(value) == ["text"] and "missing_modalities_defaulted_text_only" in warnings
    if field == "default_reasoning_level":
        return value is None
    if field == "pricing":
        pricing = _normalize_pricing(value)
        return (
            pricing.get("input_per_mtok") is None
            and pricing.get("output_per_mtok") is None
            and pricing.get("currency") is None
        )
    return False


def _risk_for_reasons(reasons: list[str], *, base: str) -> str:
    risk = base
    if any(reason.startswith("unknown_field:") or reason == "missing_provider_id" for reason in reasons):
        risk = _highest_risk([risk, "requires_adapter_review"]) or risk
    if any("transport_mapping" in reason or "transport_review" in reason for reason in reasons):
        risk = _highest_risk([risk, "requires_adapter_review"]) or risk
    if any("modality_requires_provider_smoke" in reason or "claim" in reason or "long_context" in reason or "reasoning_modes" in reason for reason in reasons):
        risk = _highest_risk([risk, "requires_provider_smoke"]) or risk
    return risk


def _adapter_review_reasons(candidate: dict[str, Any], current: dict[str, Any] | None) -> list[str]:
    warnings = [str(item) for item in candidate.get("warnings") or []]
    reasons = [item for item in warnings if item.startswith("unknown_field:")]
    if candidate.get("provider_id") in {"", "unknown"}:
        reasons.append("missing_provider_id")
    requested_adapter = dict(candidate.get("adapter_requirements") or {})
    current_adapter = dict((current or {}).get("adapter_requirements") or {})
    reasoning_parameter = _optional_string(requested_adapter.get("reasoning_parameter"))
    current_reasoning_parameter = _optional_string(current_adapter.get("reasoning_parameter"))
    if reasoning_parameter and reasoning_parameter != current_reasoning_parameter:
        reasons.append("provider_reasoning_parameter_requires_transport_mapping")
    requested_mapping = dict(requested_adapter.get("codex_to_provider_reasoning_effort") or {})
    current_mapping = dict(current_adapter.get("codex_to_provider_reasoning_effort") or {})
    if requested_mapping and requested_mapping != current_mapping:
        reasons.append("codex_to_provider_reasoning_effort_mapping_requires_transport_review")
    return _dedupe(reasons)


def _validation_requirements(risk_class: str) -> list[str]:
    if risk_class == "docs_only":
        return ["schema_validation", "proposal_review"]
    if risk_class == "metadata_only":
        return ["schema_validation", "metadata_tests", "model_catalog_tests"]
    if risk_class == "requires_provider_smoke":
        return ["schema_validation", "metadata_tests", "provider_compatibility_smoke"]
    if risk_class == "requires_kernel_smoke":
        return ["codex_kernel_probe", "codex_kernel_smoke"]
    if risk_class == "requires_adapter_review":
        return ["adapter_review", "transport_tests", "provider_compatibility_smoke"]
    return ["manual_review", "rollback_plan_review"]


def _current_capability_claims(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    modalities = set(_string_list(model.get("input_modalities") or model.get("modalities")))
    return {
        "tool_calls": {"declared": bool(model.get("supports_tool_calls") or model.get("supports_parallel_tool_calls"))},
        "web_search": {"declared": bool(model.get("supports_search_tool") or model.get("native_web_search_support") == "verified")},
        "vision": {"declared": bool("image" in modalities)},
        "audio": {"declared": bool("audio" in modalities)},
        "apply_patch": {"declared": bool(model.get("apply_patch_tool_type"))},
    }


def _current_state_refs(model: dict[str, Any], model_id: str) -> list[dict[str, Any]]:
    refs = [{"kind": "effective_model_record", "reference": model_id}]
    provenance = model.get("source_provenance") if isinstance(model.get("source_provenance"), dict) else {}
    if provenance:
        refs.append(
            {
                "kind": "source_provenance",
                "reference": str(provenance.get("source_url") or provenance.get("provider_id") or model_id),
                "source_status": provenance.get("source_status"),
                "trust_level": provenance.get("trust_level"),
            }
        )
    for url in list(model.get("source_urls") or [])[:3]:
        refs.append({"kind": "current_source_url", "reference": str(url)})
    return refs


def _update_existing_proposal(proposal_path: str, diff: dict[str, Any]) -> None:
    path = Path(proposal_path)
    if not path.exists():
        return
    proposal = read_json(path, {})
    if not isinstance(proposal, dict):
        return
    proposal["diff"] = {
        "schema_version": AGENTIC_UPDATE_DIFF_SCHEMA_VERSION,
        "status": diff["status"],
        "risk_class": diff["risk_class"],
        "summary": deepcopy(diff["summary"]),
        "changes": deepcopy(diff["changes"]),
        "warnings": deepcopy(diff["warnings"]),
        "artifact_paths": deepcopy(diff["artifact_paths"]),
        "route_promotion": deepcopy(diff.get("route_promotion") or {}),
    }
    proposal["route_promotion"] = deepcopy(diff.get("route_promotion") or {})
    proposal["validation_result"]["status"] = "not_run"
    proposal["validation_result"]["warnings"] = _dedupe(
        list(proposal["validation_result"].get("warnings") or []) + ["validation_required_after_diff"]
    )
    validated = validate_update_proposal(proposal)
    write_json(path, validated)


def _risk_counts(changes: list[dict[str, Any]]) -> dict[str, int]:
    counts = {risk: 0 for risk in RISK_CLASSES}
    for change in changes:
        risk = str(change.get("risk_class") or "blocked_manual_review")
        counts[risk] = counts.get(risk, 0) + 1
    return counts


def _highest_risk(risks: list[str]) -> str | None:
    valid = [risk for risk in risks if risk in _RISK_RANK]
    if not valid:
        return None
    return max(valid, key=lambda risk: _RISK_RANK[risk])


def _normalize_pricing(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        raw = value
    else:
        raw = {}
    return {
        "input_per_mtok": _float_or_none(raw.get("input_per_mtok") if raw.get("input_per_mtok") is not None else raw.get("pricing_input_per_mtok")),
        "output_per_mtok": _float_or_none(
            raw.get("output_per_mtok") if raw.get("output_per_mtok") is not None else raw.get("pricing_output_per_mtok")
        ),
        "cached_input_per_mtok": _float_or_none(
            raw.get("cached_input_per_mtok")
            if raw.get("cached_input_per_mtok") is not None
            else raw.get("pricing_cached_input_per_mtok")
        ),
        "currency": _optional_string(raw.get("currency") or raw.get("pricing_currency")),
    }


def _same_value(before: Any, after: Any) -> bool:
    if isinstance(before, list) or isinstance(after, list):
        return _string_list(before) == _string_list(after)
    if isinstance(before, dict) or isinstance(after, dict):
        return jsonish(before) == jsonish(after)
    return before == after


def jsonish(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): jsonish(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [jsonish(item) for item in value]
    return value


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).strip().replace(",", "").replace("_", "")))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip().replace(",", "").replace("_", ""))
    except (TypeError, ValueError):
        return None


def _optional_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = [part.strip() for part in str(value).replace("/", ",").split(",")]
    return _dedupe([str(item).strip().lower() for item in raw if str(item).strip()])


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _slug(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(value or "").strip())
    return text.strip("-._")[:96] or "target"


def _source_ref_label(ref: dict[str, Any]) -> str:
    source_id = str(ref.get("source_id") or "source").strip()
    content_hash = str(ref.get("content_hash") or "").strip()
    return f"{source_id} {content_hash}".strip()


def _current_ref_label(ref: dict[str, Any]) -> str:
    return f"{ref.get('kind')}:{ref.get('reference')}"


def _md_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()
