from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .capabilities.capability_routes import normalize_capability_route_record
from .capabilities.smoke import capability_smoke_snapshot
from .common import now_iso, slugify, write_json
from .provider_model_compatibility_matrix import VALIDATION_STATUSES
from .providers import classify_runtime_failure
from .security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, SecurityError


PROVIDER_COMPATIBILITY_SMOKE_REPORT_SCHEMA_VERSION = "astrabridge-provider-compatibility-smoke-report-v1"
PROVIDER_COMPATIBILITY_SMOKE_CASE_SCHEMA_VERSION = "astrabridge-provider-compatibility-smoke-case-v1"
PROVIDER_COMPATIBILITY_SMOKE_STATUSES = ("pass", "fail", "partial", "skipped", "blocked")
PROVIDER_COMPATIBILITY_SMOKE_MODES = ("dry_run", "provider")

_SECRET_FIELD_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "access_token",
    "refresh_token",
    "session_token",
    "bearer_token",
    "vault_password",
    "admin_session_token",
    "provider_secret",
    "raw_secret",
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+[a-z0-9._~+/=-]{12,}|cookie\s*:|ssh-rsa|BEGIN\s+(RSA|OPENSSH|EC|DSA)\s+PRIVATE\s+KEY)"
)
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", flags=re.IGNORECASE)
_KEY_VALUE_RE = re.compile(r"(?i)(api[_-]?key|authorization|token|cookie)(['\":= ]+)([A-Za-z0-9._~+/=-]{8,})")


def run_provider_compatibility_smoke(
    payload: dict[str, Any],
    *,
    configured_models: list[dict[str, Any]] | None = None,
    capability_route_records: dict[str, Any] | None = None,
    runtime: Any | None = None,
    workspace_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Run a secret-free provider/model compatibility smoke batch."""

    if not isinstance(payload, dict):
        raise TypeError("Provider compatibility smoke payload must be a dict.")
    created_at = now_iso()
    run_id = slugify(str(payload.get("run_id") or f"provider-compatibility-smoke-{created_at}"), default="provider-compatibility-smoke")
    cases_payload = payload.get("cases")
    if not isinstance(cases_payload, list) or not cases_payload:
        raise ValueError("Provider compatibility smoke requires a non-empty cases list.")
    run_dir = _resolve_run_dir(run_id, workspace_root=workspace_root, artifact_root=artifact_root)
    cases: list[dict[str, Any]] = []
    for index, raw_case in enumerate(cases_payload):
        if not isinstance(raw_case, dict):
            raw_case = {"case_id": f"case-{index + 1}", "skip_reason": "case payload was not an object"}
        case = _run_case(
            raw_case,
            index=index,
            configured_models=configured_models,
            capability_route_records=capability_route_records or {},
            runtime=runtime,
        )
        cases.append(case)

    counts = {status: 0 for status in PROVIDER_COMPATIBILITY_SMOKE_STATUSES}
    for case in cases:
        counts[str(case.get("status") or "blocked")] += 1
    report = {
        "schema_version": PROVIDER_COMPATIBILITY_SMOKE_REPORT_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": created_at,
        "status": _aggregate_status(cases),
        "counts": counts,
        "summary": {
            "case_count": len(cases),
            "provider_case_count": sum(1 for case in cases if str(case.get("mode") or "") == "provider"),
            "dry_run_case_count": sum(1 for case in cases if str(case.get("mode") or "") == "dry_run"),
        },
        "cases": cases,
        "matrix_updates": [],
        "artifact_paths": {},
        "redaction": {
            "secret_free": True,
            "raw_provider_requests_persisted": False,
            "raw_provider_responses_persisted": False,
        },
    }
    report["matrix_updates"] = compatibility_matrix_updates_from_smoke_report(report)
    assert_secret_free_provider_compatibility_smoke_report(report)
    _write_evidence(run_dir, report)
    report["artifact_paths"] = {
        "run_dir": str(run_dir),
        "summary_json": str(run_dir / "summary.json"),
        "report_md": str(run_dir / "report.md"),
        "case_dir": str(run_dir / "cases"),
    }
    assert_secret_free_provider_compatibility_smoke_report(report)
    write_json(run_dir / "summary.json", report)
    return report


def compatibility_matrix_updates_from_smoke_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    updates: list[dict[str, Any]] = []
    if not isinstance(report, dict):
        return updates
    run_id = str(report.get("run_id") or "").strip()
    for case in list(report.get("cases") or []):
        if not isinstance(case, dict):
            continue
        provider_id = str(case.get("provider_id") or "").strip()
        model = str(case.get("model") or "").strip()
        capability_id = str(case.get("capability_id") or "").strip()
        if not provider_id and isinstance(case.get("route"), dict):
            candidate = dict((case.get("route") or {}).get("resolved_candidate") or {})
            provider_id = str(candidate.get("provider_id") or "").strip()
            model = str(candidate.get("model") or model).strip()
        status = _matrix_status(str(case.get("status") or "blocked"))
        if status not in VALIDATION_STATUSES:
            status = "unknown"
        updates.append(
            {
                "entry_id": f"{provider_id}/{model}" if provider_id and model else provider_id or model or capability_id,
                "provider_id": provider_id or None,
                "model_id": model or None,
                "capability_id": capability_id or None,
                "validation_status": status,
                "validation_scope": [capability_id] if capability_id else [],
                "evidence_paths": _case_evidence_paths(case, run_id=run_id),
                "usage_signal": case.get("usage_signal"),
                "known_failures": list(case.get("reasons") or []) if status in {"fail", "blocked"} else [],
                "known_pitfalls": list(case.get("warnings") or []),
                "last_verified_at": report.get("created_at"),
            }
        )
    return updates


def assert_secret_free_provider_compatibility_smoke_report(report: dict[str, Any]) -> None:
    if not isinstance(report, dict):
        raise TypeError("Provider compatibility smoke report must be a dict.")
    if str(report.get("schema_version") or "") != PROVIDER_COMPATIBILITY_SMOKE_REPORT_SCHEMA_VERSION:
        raise ValueError("Unexpected provider compatibility smoke schema version.")
    _reject_secret_like(report, path="provider_compatibility_smoke")


def _run_case(
    raw_case: dict[str, Any],
    *,
    index: int,
    configured_models: list[dict[str, Any]] | None,
    capability_route_records: dict[str, Any],
    runtime: Any | None,
) -> dict[str, Any]:
    case_id = slugify(str(raw_case.get("case_id") or f"case-{index + 1}"), default=f"case-{index + 1}")
    capability_id = str(raw_case.get("capability_id") or "").strip()
    provider_id = str(raw_case.get("provider_id") or "").strip()
    model = str(raw_case.get("model") or "").strip()
    mode = str(raw_case.get("mode") or "dry_run").strip().lower() or "dry_run"
    if mode not in PROVIDER_COMPATIBILITY_SMOKE_MODES:
        mode = "dry_run"
    base = {
        "schema_version": PROVIDER_COMPATIBILITY_SMOKE_CASE_SCHEMA_VERSION,
        "case_id": case_id,
        "capability_id": capability_id or None,
        "provider_id": provider_id or None,
        "model": model or None,
        "mode": mode,
        "status": "blocked",
        "reasons": [],
        "warnings": [],
        "route": None,
        "sanitized_request": {},
        "sanitized_response": {},
        "usage_signal": None,
        "artifact_refs": [],
        "evidence_refs": [],
        "failure_notice": None,
    }
    skip_reason = str(raw_case.get("skip_reason") or "").strip()
    if skip_reason:
        base.update({"status": "skipped", "reasons": [_safe_text(skip_reason)]})
        return base
    if not capability_id:
        base["reasons"] = ["capability_id is required."]
        return base
    allow_provider = bool(raw_case.get("allow_provider", False))
    if mode == "provider" and not allow_provider:
        base["reasons"] = ["Provider-backed smoke requires allow_provider=true."]
        return base
    case_payload = _case_payload(raw_case, capability_id=capability_id, mode=mode, provider_id=provider_id, model=model)
    route_record = _case_route_record(raw_case, capability_id=capability_id, capability_route_records=capability_route_records)
    try:
        smoke = capability_smoke_snapshot(
            case_payload,
            configured_models=configured_models,
            route_record=route_record,
            runtime=runtime,
        )
    except Exception as exc:  # noqa: BLE001 - compatibility runner records blockers as evidence.
        base["reasons"] = [_safe_text(str(exc) or exc.__class__.__name__)]
        return base
    status, reasons, warnings = _map_case_status(
        smoke,
        requested_provider=provider_id,
        requested_model=model,
    )
    route = dict(smoke.get("route") or {})
    candidate = dict(route.get("resolved_candidate") or {})
    failure_notice = _failure_notice_for_case(
        smoke,
        status=status,
        reasons=reasons,
        warnings=warnings,
        requested_provider=provider_id,
        requested_model=model,
        resolved_provider=str(candidate.get("provider_id") or "").strip(),
        resolved_model=str(candidate.get("model") or "").strip(),
    )
    base.update(
        {
            "status": status,
            "reasons": reasons,
            "warnings": warnings,
            "route": {
                "route_mode": route.get("route_mode"),
                "resolution_status": route.get("resolution_status"),
                "resolved_candidate": {
                    "provider_id": candidate.get("provider_id"),
                    "model": candidate.get("model"),
                    "adapter_id": candidate.get("adapter_id"),
                }
                if candidate
                else None,
                "error": route.get("error"),
            },
            "sanitized_request": _safe_value(smoke.get("sanitized_request") or {}),
            "sanitized_response": _safe_value(smoke.get("sanitized_response") or {}),
            "usage_signal": smoke.get("usage_signal"),
            "artifact_refs": _safe_value(smoke.get("artifact_refs") or []),
            "evidence_refs": _safe_value(smoke.get("evidence_refs") or []),
            "failure_notice": failure_notice,
        }
    )
    if not provider_id and candidate.get("provider_id"):
        base["provider_id"] = candidate.get("provider_id")
    if not model and candidate.get("model"):
        base["model"] = candidate.get("model")
    return base


def _case_payload(raw_case: dict[str, Any], *, capability_id: str, mode: str, provider_id: str, model: str) -> dict[str, Any]:
    blocked_keys = {"case_id", "skip_reason"}
    payload = {key: value for key, value in raw_case.items() if key not in blocked_keys}
    payload["capability_id"] = capability_id
    payload["mode"] = mode
    if provider_id:
        payload["provider_id"] = provider_id
    if model:
        payload["model"] = model
    return payload


def _case_route_record(
    raw_case: dict[str, Any],
    *,
    capability_id: str,
    capability_route_records: dict[str, Any],
) -> dict[str, Any] | None:
    provider_id = str(raw_case.get("provider_id") or "").strip()
    model = str(raw_case.get("model") or "").strip()
    if provider_id:
        return normalize_capability_route_record(
            capability_id,
            {
                "mode": "pinned",
                "provider_id": provider_id,
                "model": model,
            },
        )
    route_record = capability_route_records.get(capability_id)
    return dict(route_record) if isinstance(route_record, dict) else None


def _map_case_status(
    smoke: dict[str, Any],
    *,
    requested_provider: str = "",
    requested_model: str = "",
) -> tuple[str, list[str], list[str]]:
    smoke_status = str(smoke.get("status") or "").strip()
    route = dict(smoke.get("route") or {})
    notes = [str(item) for item in list((smoke.get("sanitized_response") or {}).get("notes") or []) if str(item or "").strip()]
    error = str(route.get("error") or "").strip()
    provider_error = str((smoke.get("sanitized_response") or {}).get("provider_error") or "").strip()
    actual_provider, actual_model = _actual_provider_result_target(smoke)
    reasons: list[str] = []
    warnings: list[str] = []
    requested_target = "/".join(item for item in [requested_provider, requested_model] if item)
    actual_target = "/".join(item for item in [actual_provider, actual_model] if item)
    if requested_target and actual_target and requested_target != actual_target:
        reasons.append(
            _safe_text(
                f"provider/model mismatch: requested `{requested_target}` but provider-backed result came from `{actual_target}`."
            )
        )
        warnings.extend(_safe_text(item) for item in notes)
        return "fail", reasons, warnings
    if route.get("resolution_status") == "no_capability_candidate":
        reasons.append(_safe_text(error or "No eligible capability candidate was available."))
        return "blocked", reasons, warnings
    if smoke_status == "pass":
        return "pass", reasons, [_safe_text(item) for item in notes[1:]]
    if smoke_status == "warn":
        return "partial", reasons, [_safe_text(item) for item in notes]
    if smoke_status == "provider_not_run":
        reasons.append("Provider-backed smoke did not invoke a provider runtime.")
        return "blocked", reasons, warnings
    if smoke_status == "fail":
        if "no_capability_candidate" in provider_error or "requires an api" in provider_error.lower():
            reasons.append(_safe_text(provider_error))
            return "blocked", reasons, warnings
        reasons.append(_safe_text(provider_error or "Provider smoke failed."))
        warnings.extend(_safe_text(item) for item in notes)
        return "fail", reasons, warnings
    reasons.append(_safe_text(f"Unsupported capability smoke status: {smoke_status or 'unknown'}"))
    return "blocked", reasons, warnings


def _actual_provider_result_target(smoke: dict[str, Any]) -> tuple[str, str]:
    provider_result = dict(((smoke.get("sanitized_response") or {}).get("provider_result") or {}))
    route = dict(provider_result.get("route") or {})
    candidate = dict(route.get("resolved_candidate") or {})
    provider_id = str(provider_result.get("provider_id") or candidate.get("provider_id") or "").strip()
    model = str(provider_result.get("model") or candidate.get("model") or "").strip()
    return provider_id, model


def _failure_notice_for_case(
    smoke: dict[str, Any],
    *,
    status: str,
    reasons: list[str],
    warnings: list[str],
    requested_provider: str,
    requested_model: str,
    resolved_provider: str,
    resolved_model: str,
) -> dict[str, Any] | None:
    if status in {"pass", "skipped"}:
        return None
    actual_provider, actual_model = _actual_provider_result_target(smoke)
    message_parts = [item for item in [*reasons, *warnings] if str(item or "").strip()]
    if not message_parts:
        route = dict(smoke.get("route") or {})
        error = str(route.get("error") or "").strip()
        if error:
            message_parts.append(error)
    if not message_parts:
        return None
    provider_context = actual_provider or requested_provider or resolved_provider
    model_context = actual_model or requested_model or resolved_model
    notice = classify_runtime_failure(
        " ".join(message_parts),
        current_provider=provider_context or None,
        current_model=model_context or None,
    ).to_payload()
    if requested_provider or requested_model:
        notice["requested_provider"] = requested_provider or None
        notice["requested_model"] = requested_model or None
    if resolved_provider or resolved_model:
        notice["resolved_provider"] = resolved_provider or None
        notice["resolved_model"] = resolved_model or None
    if actual_provider or actual_model:
        notice["observed_provider"] = actual_provider or None
        notice["observed_model"] = actual_model or None
    return _safe_value(notice)


def _matrix_status(status: str) -> str:
    return {
        "pass": "pass",
        "partial": "partial",
        "fail": "fail",
        "skipped": "skipped",
        "blocked": "blocked",
    }.get(status, "unknown")


def _aggregate_status(cases: list[dict[str, Any]]) -> str:
    statuses = {str(case.get("status") or "blocked") for case in cases}
    if statuses <= {"pass", "skipped"} and "pass" in statuses:
        return "pass"
    if "fail" in statuses:
        return "fail"
    if "blocked" in statuses:
        return "blocked"
    if "partial" in statuses:
        return "partial"
    return "skipped"


def _case_evidence_paths(case: dict[str, Any], *, run_id: str) -> list[str]:
    paths = [f"PRIVATE/provider-compatibility/runs/{run_id}/cases/{case.get('case_id')}.json"]
    for ref in list(case.get("evidence_refs") or []):
        if isinstance(ref, dict) and ref.get("path"):
            paths.append(str(ref.get("path")))
    return paths


def _resolve_run_dir(
    run_id: str,
    *,
    workspace_root: str | Path | None,
    artifact_root: str | Path | None,
) -> Path:
    if artifact_root:
        return Path(artifact_root).expanduser().resolve() / run_id
    root = Path(workspace_root).expanduser().resolve() if workspace_root else Path.cwd().resolve()
    return root / "PRIVATE" / "provider-compatibility" / "runs" / run_id


def _write_evidence(run_dir: Path, report: dict[str, Any]) -> None:
    cases_dir = run_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    for case in list(report.get("cases") or []):
        if not isinstance(case, dict):
            continue
        write_json(cases_dir / f"{slugify(str(case.get('case_id') or 'case'), default='case')}.json", case)
    (run_dir / "report.md").write_text(_render_report_md(report), encoding="utf-8")


def _render_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# Provider Compatibility Smoke Report",
        "",
        f"- Run ID: `{report.get('run_id')}`",
        f"- Status: `{report.get('status')}`",
        f"- Created: `{report.get('created_at')}`",
        f"- Counts: `{json.dumps(report.get('counts') or {}, ensure_ascii=False)}`",
        "",
        "## Cases",
        "",
    ]
    for case in list(report.get("cases") or []):
        if not isinstance(case, dict):
            continue
        target = "/".join(item for item in [str(case.get("provider_id") or ""), str(case.get("model") or "")] if item)
        lines.extend(
            [
                f"### {case.get('case_id')}",
                "",
                f"- Capability: `{case.get('capability_id')}`",
                f"- Target: `{target or 'auto'}`",
                f"- Mode: `{case.get('mode')}`",
                f"- Status: `{case.get('status')}`",
                f"- Reasons: `{json.dumps(case.get('reasons') or [], ensure_ascii=False)}`",
                f"- Warnings: `{json.dumps(case.get('warnings') or [], ensure_ascii=False)}`",
                (
                    f"- Failure notice: `category={(case.get('failure_notice') or {}).get('category')}` "
                    f"`action={(case.get('failure_notice') or {}).get('recommended_action')}`"
                    if isinstance(case.get("failure_notice"), dict) and case.get("failure_notice")
                    else ""
                ),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _safe_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in _SECRET_FIELD_MARKERS):
                sanitized[key] = "[redacted]"
            else:
                sanitized[key] = _safe_value(item)
        return sanitized
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, str):
        return _safe_text(value)
    return value


def _safe_text(value: str) -> str:
    text = str(value or "")
    text = _BEARER_RE.sub("Bearer [redacted]", text)
    text = re.sub(r"(?i)authorization\s*:\s*Bearer \[redacted\]", "auth_header=Bearer [redacted]", text)
    text = _KEY_VALUE_RE.sub(r"\1\2[redacted]", text)
    text = re.sub(r"data:image/[^'\"\s,]+,?[A-Za-z0-9+/=._:-]*", "data:image/[redacted]", text)
    text = re.sub(r"data:audio/[^'\"\s,]+,?[A-Za-z0-9+/=._:-]*", "data:audio/[redacted]", text)
    return text[:1200]


def _reject_secret_like(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in _SECRET_FIELD_MARKERS):
                if item not in (None, "", "[redacted]"):
                    raise SecurityError(f"Forbidden secret-bearing field in provider compatibility smoke report: {path}.{key}")
            _reject_secret_like(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_like(item, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if value.startswith("data:image/") or value.startswith("data:audio/"):
        raise SecurityError(f"Inline media data is not allowed in provider compatibility smoke reports: {path}")
    if DESKTOP_KEY_PATH_RE.search(value):
        raise SecurityError(f"Desktop key path is not allowed in provider compatibility smoke reports: {path}")
    if SECRET_QUERY_RE.search(value) or _SECRET_VALUE_RE.search(value):
        raise SecurityError(f"Secret-like value is not allowed in provider compatibility smoke reports: {path}")
