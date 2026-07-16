from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..common import slugify, write_json
from ..provider_compatibility_smoke import assert_secret_free_provider_compatibility_smoke_report, run_provider_compatibility_smoke
from .artifacts import ensure_agentic_update_run_layout, validate_agentic_update_artifact_path
from .contracts import assert_secret_free_agentic_update_payload, validate_update_proposal


AGENTIC_UPDATE_PROVIDER_SMOKE_CASES_SCHEMA_VERSION = "astrabridge-agentic-update-provider-smoke-cases-v1"
AGENTIC_UPDATE_PROVIDER_SMOKE_CASES_FILENAME = "validation/provider-smoke-cases.json"
SUPPORTED_PROVIDER_SMOKE_CAPABILITIES = ("image.generate", "vision.analyze", "speech.transcribe", "speech.synthesize")


def generate_provider_smoke_cases_from_proposal(
    proposal: dict[str, Any],
    *,
    mode: str = "dry_run",
    allow_provider_calls: bool = False,
    credential_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validated = validate_update_proposal(proposal)
    smoke_mode = "provider" if str(mode or "").strip() == "provider" else "dry_run"
    credential_index = _credential_index(credential_status)
    cases: list[dict[str, Any]] = []
    warnings: list[str] = []
    for change in list(dict(validated.get("diff") or {}).get("changes") or []):
        if not isinstance(change, dict) or not _change_requires_provider_smoke(change):
            continue
        provider_id = _provider_id(change)
        model = _native_model(str(change.get("model_id") or change.get("target") or ""))
        capabilities = _capabilities_for_change(change)
        if not capabilities:
            case_id = _case_id("manual", change, provider_id, model)
            cases.append(
                {
                    "case_id": case_id,
                    "provider_id": provider_id or None,
                    "model": model or None,
                    "mode": "dry_run",
                    "skip_reason": "no_automated_capability_smoke_fixture_for_change",
                    "agentic_update": _case_source(validated, change),
                }
            )
            warnings.append(f"no_automated_provider_smoke_fixture:{change.get('change_id')}")
            continue
        for capability_id in capabilities:
            provider_allowed = bool(allow_provider_calls and smoke_mode == "provider")
            skip_reason = ""
            if smoke_mode == "provider" and not provider_allowed:
                skip_reason = "provider_calls_not_authorized"
            elif smoke_mode == "provider" and not _credential_available(provider_id, credential_index):
                skip_reason = "provider_credential_status_unavailable"
            case = {
                "case_id": _case_id(capability_id, change, provider_id, model),
                "capability_id": capability_id,
                "provider_id": provider_id or None,
                "model": model or None,
                "mode": smoke_mode if not skip_reason else "dry_run",
                "allow_provider": provider_allowed and not skip_reason,
                "agentic_update": _case_source(validated, change),
            }
            if skip_reason:
                case["skip_reason"] = skip_reason
            cases.append(case)
    if not cases:
        cases.append(
            {
                "case_id": "no-provider-smoke-required",
                "mode": "dry_run",
                "skip_reason": "proposal_has_no_provider_smoke_changes",
                "agentic_update": {"run_id": validated.get("run_id")},
            }
        )
    payload = {
        "schema_version": AGENTIC_UPDATE_PROVIDER_SMOKE_CASES_SCHEMA_VERSION,
        "run_id": validated.get("run_id"),
        "mode": smoke_mode,
        "allow_provider_calls": bool(allow_provider_calls),
        "case_count": len(cases),
        "cases": cases,
        "credential_status": _redacted_credential_status(credential_index),
        "warnings": _dedupe(warnings),
    }
    assert_secret_free_agentic_update_payload(payload, label="agentic_update_provider_smoke_cases")
    return payload


def run_agentic_update_provider_smoke(
    *,
    workspace_root: str | Path,
    run_id: str,
    proposal: dict[str, Any],
    mode: str = "dry_run",
    allow_provider_calls: bool = False,
    credential_status: dict[str, Any] | None = None,
    configured_models: list[dict[str, Any]] | None = None,
    capability_route_records: dict[str, Any] | None = None,
    runtime: Any | None = None,
    gate_id: str = "provider_compatibility_smoke",
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    layout = ensure_agentic_update_run_layout(workspace, run_id)
    case_pack = generate_provider_smoke_cases_from_proposal(
        proposal,
        mode=mode,
        allow_provider_calls=allow_provider_calls,
        credential_status=credential_status,
    )
    cases_path = validate_agentic_update_artifact_path(workspace, run_id, AGENTIC_UPDATE_PROVIDER_SMOKE_CASES_FILENAME)
    write_json(cases_path, case_pack)
    smoke_run_id = _smoke_run_id(run_id, gate_id)
    artifact_root = validate_agentic_update_artifact_path(workspace, run_id, "validation/provider-smoke")
    report = run_provider_compatibility_smoke(
        {
            "run_id": smoke_run_id,
            "cases": case_pack["cases"],
        },
        configured_models=configured_models,
        capability_route_records=capability_route_records or {},
        runtime=runtime,
        workspace_root=workspace,
        artifact_root=artifact_root,
    )
    report["agentic_update"] = {
        "run_id": run_id,
        "proposal_run_id": case_pack.get("run_id"),
        "gate_id": gate_id,
        "case_pack_path": str(cases_path),
    }
    report["matrix_update_suggestions"] = _matrix_update_suggestions(report, run_id=run_id, smoke_run_id=smoke_run_id)
    report["artifact_paths"]["agentic_update_case_pack"] = str(cases_path)
    report["artifact_paths"]["agentic_update_validation_root"] = str(Path(layout["subdirectories"]["validation"]))
    assert_secret_free_provider_compatibility_smoke_report(report)
    write_json(Path(report["artifact_paths"]["summary_json"]), report)
    return report


def provider_smoke_report_blocks_promotion(report: dict[str, Any], *, provider_backed: bool) -> bool:
    if str(report.get("status") or "") in {"fail", "blocked", "partial"}:
        return True
    for case in list(report.get("cases") or []):
        if not isinstance(case, dict):
            continue
        reasons = {str(item) for item in list(case.get("reasons") or [])}
        if str(case.get("status")) == "skipped" and reasons.intersection({"provider_calls_not_authorized", "provider_credential_status_unavailable"}):
            return True
        if provider_backed and str(case.get("mode") or "") != "provider" and str(case.get("status") or "") != "pass":
            return True
    return False


def _change_requires_provider_smoke(change: dict[str, Any]) -> bool:
    if str(change.get("risk_class") or "") == "requires_provider_smoke":
        return True
    requirements = {str(item) for item in list(change.get("validation_requirements") or [])}
    if requirements.intersection({"provider_compatibility_smoke", "capability_smoke"}):
        return True
    reasons = " ".join(str(item) for item in list(change.get("reasons") or []))
    return any(marker in reasons for marker in ("modality_requires_provider_smoke", "unverified_", "long_context", "reasoning_modes"))


def _capabilities_for_change(change: dict[str, Any]) -> list[str]:
    details = dict(change.get("details") or {})
    capability = str(details.get("capability") or "").strip().lower()
    candidates: list[str] = []
    if capability in {"image.generate", "image_generation"}:
        candidates.append("image.generate")
    if capability in {"vision", "vision.analyze"}:
        candidates.append("vision.analyze")
    if capability in {"audio", "speech.transcribe"}:
        candidates.append("speech.transcribe")
    if capability in {"tts", "speech.synthesize"}:
        candidates.append("speech.synthesize")
    metadata = dict(details.get("candidate_metadata") or {})
    if not metadata and isinstance(details.get("candidate"), dict):
        metadata = dict(details.get("candidate") or {})
    modalities = _string_list(metadata.get("input_modalities") or details.get("candidate") or details.get("modalities"))
    if "image" in modalities:
        candidates.append("vision.analyze")
    if "audio" in modalities:
        candidates.extend(["speech.transcribe", "speech.synthesize"])
    for reason in list(change.get("reasons") or []):
        text = str(reason).lower()
        if "image_modality" in text or "vision" in text:
            candidates.append("vision.analyze")
        if "audio_modality" in text or "speech" in text:
            candidates.extend(["speech.transcribe", "speech.synthesize"])
    return [item for item in _dedupe(candidates) if item in SUPPORTED_PROVIDER_SMOKE_CAPABILITIES]


def _case_source(proposal: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": proposal.get("run_id"),
        "change_id": change.get("change_id"),
        "change_type": change.get("change_type"),
        "risk_class": change.get("risk_class"),
        "model_id": change.get("model_id"),
    }


def _case_id(capability_id: str, change: dict[str, Any], provider_id: str, model: str) -> str:
    return slugify(
        "-".join(
            part
            for part in [
                capability_id.replace(".", "-"),
                provider_id,
                model,
                str(change.get("change_id") or change.get("change_type") or "change"),
            ]
            if part
        ),
        default="provider-smoke-case",
    )


def _smoke_run_id(run_id: str, gate_id: str) -> str:
    prefix = {"provider_compatibility_smoke": "pcs", "capability_smoke": "cs"}.get(gate_id, "ps")
    digest = hashlib.sha256(f"{run_id}:{gate_id}".encode("utf-8")).hexdigest()[:10]
    return slugify(f"{prefix}-{digest}", default=f"{prefix}-smoke")


def _provider_id(change: dict[str, Any]) -> str:
    provider = str(change.get("provider_id") or "").strip()
    if provider:
        return provider
    model_id = str(change.get("model_id") or change.get("target") or "").strip()
    return model_id.split("/", 1)[0] if "/" in model_id else ""


def _native_model(model_id: str) -> str:
    text = str(model_id or "").strip()
    return text.split("/", 1)[1] if "/" in text else text


def _credential_index(value: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    data = value if isinstance(value, dict) else {}
    raw = data.get("providers") if isinstance(data.get("providers"), list) else data
    index: dict[str, dict[str, Any]] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                provider_id = str(item.get("provider_id") or item.get("id") or "").strip()
                if provider_id:
                    index[provider_id] = dict(item)
    elif isinstance(raw, dict):
        for provider_id, item in raw.items():
            if isinstance(item, dict):
                index[str(provider_id)] = dict(item)
            else:
                index[str(provider_id)] = {"available": bool(item)}
    return index


def _credential_available(provider_id: str, credential_index: dict[str, dict[str, Any]]) -> bool:
    if not provider_id:
        return False
    record = credential_index.get(provider_id) or {}
    return bool(record.get("available") or record.get("credential_available") or record.get("has_credential"))


def _redacted_credential_status(credential_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for provider_id, record in sorted(credential_index.items()):
        sources = [str(item) for item in list(record.get("sources") or []) if str(item).strip()]
        records.append({"provider_id": provider_id, "available": _credential_available(provider_id, credential_index), "sources": sources[:4]})
    return records


def _matrix_update_suggestions(report: dict[str, Any], *, run_id: str, smoke_run_id: str) -> list[dict[str, Any]]:
    suggestions = []
    for item in list(report.get("matrix_updates") or []):
        if not isinstance(item, dict):
            continue
        update = dict(item)
        update["agentic_update_run_id"] = run_id
        update["source_smoke_run_id"] = smoke_run_id
        update["evidence_paths"] = [
            f"PRIVATE/agentic-update-pipeline/runs/{run_id}/validation/provider-smoke/{smoke_run_id}/summary.json",
            f"PRIVATE/agentic-update-pipeline/runs/{run_id}/validation/provider-smoke/{smoke_run_id}/cases",
        ]
        suggestions.append(update)
    return suggestions


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, list) else [value]
    result = []
    for item in raw:
        text = str(item or "").strip().lower()
        if text:
            result.append(text)
    return _dedupe(result)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
