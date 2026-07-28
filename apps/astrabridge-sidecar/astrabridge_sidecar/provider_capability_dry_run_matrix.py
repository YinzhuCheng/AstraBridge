from __future__ import annotations

import json
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .common import now_iso, slugify, write_json
from .capabilities.capability_registry import default_capability_registry
from .profile_service import ProfileService
from .provider_compatibility_smoke import run_provider_compatibility_smoke
from .provider_model_compatibility_matrix import (
    assert_secret_free_provider_model_compatibility_matrix,
    compatibility_matrix_entry_template,
    empty_provider_model_compatibility_matrix,
)
from .router_config_service import RouterConfigService
from .router_service import RouterService


PROVIDER_CAPABILITY_DRY_RUN_MATRIX_SCHEMA_VERSION = "astrabridge-provider-capability-dry-run-matrix-v1"
DEFAULT_PRIORITY_PROVIDER_IDS = ("yunwu", "openai", "qwen", "deepseek", "kimi", "glm")
_REQUIRED_MODALITIES = {
    "vision.analyze": ("image",),
    "speech.transcribe": ("audio",),
}
_MODELED_MULTIMODAL_CAPABILITIES = (
    "image.generate",
    "vision.analyze",
    "speech.transcribe",
    "speech.synthesize",
)
_PREVIEW_REASONING_LABELS = ("default", "off_probe", "high", "xhigh")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+[a-z0-9._~+/=-]{12,}|cookie\s*:|ssh-rsa|BEGIN\s+(RSA|OPENSSH|EC|DSA)\s+PRIVATE\s+KEY)"
)


def run_provider_capability_dry_run_matrix(
    *,
    workspace_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
    priority_provider_ids: list[str] | tuple[str, ...] | None = None,
    router: RouterService | None = None,
    router_config: RouterConfigService | None = None,
    configured_models: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(workspace_root).expanduser().resolve() if workspace_root else Path.cwd().resolve()
    priority_ids = tuple(str(item).strip() for item in (priority_provider_ids or DEFAULT_PRIORITY_PROVIDER_IDS) if str(item).strip())
    created_at = now_iso()
    resolved_run_id = slugify(run_id or f"provider-capability-dry-run-matrix-{created_at}", default="provider-capability-dry-run-matrix")
    run_dir = _resolve_run_dir(root=root, artifact_root=artifact_root, run_id=resolved_run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if router is None or router_config is None or configured_models is None:
        temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(temp_dir.name)
        profiles = ProfileService(temp_root / "profiles.json")
        router_config = RouterConfigService(profiles, temp_root / "router.json")
        router = RouterService(profiles, router_config, port=0)
        configured_models = router_config.models()

    assert router is not None
    assert router_config is not None
    assert configured_models is not None

    providers = [
        dict(item)
        for item in list(router_config.providers() or [])
        if isinstance(item, dict) and str(item.get("id") or item.get("provider_id") or "").strip() in priority_ids
    ]
    models = _selected_models(configured_models, priority_provider_ids=priority_ids)
    preview_cases = _build_preview_cases(router, models=models, run_dir=run_dir)

    smoke_run_id = f"{resolved_run_id}-capability-smoke"
    smoke_cases = _capability_smoke_cases(models)
    smoke_report = run_provider_compatibility_smoke(
        {"run_id": smoke_run_id, "cases": smoke_cases},
        configured_models=configured_models,
        runtime=None,
        workspace_root=root,
    )
    normalized_smoke_cases = _normalize_smoke_cases(smoke_report, model_index={str(item.get("id")): item for item in models})
    matrix = _build_matrix(
        providers=providers,
        models=models,
        preview_cases=preview_cases,
        smoke_cases=normalized_smoke_cases,
        run_id=resolved_run_id,
        created_at=created_at,
        smoke_report=smoke_report,
    )
    assert_secret_free_provider_model_compatibility_matrix(matrix)

    preview_dir = run_dir / "preview-cases"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_case_paths: list[str] = []
    for case in preview_cases:
        target = preview_dir / f"{slugify(str(case.get('case_id') or 'preview'), default='preview')}.json"
        write_json(target, case)
        preview_case_paths.append(str(target))

    matrix_path = run_dir / "matrix.json"
    summary_path = run_dir / "summary.json"
    report_path = run_dir / "report.md"
    write_json(matrix_path, matrix)

    summary = {
        "schema_version": PROVIDER_CAPABILITY_DRY_RUN_MATRIX_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": created_at,
        "priority_provider_ids": list(priority_ids),
        "provider_ids_covered": sorted({str(item.get("id") or item.get("provider_id") or "") for item in providers if str(item.get("id") or item.get("provider_id") or "").strip()}),
        "model_ids_covered": [str(item.get("id") or "") for item in models],
        "web_lane_policy": "standalone",
        "preview_case_count": len(preview_cases),
        "capability_smoke_case_count": len(normalized_smoke_cases),
        "matrix_entry_count": len(list(matrix.get("entries") or [])),
        "preview_status_counts": dict(Counter(str(case.get("status") or "blocked") for case in preview_cases)),
        "capability_status_counts": dict(Counter(str(case.get("capability_status") or "unknown") for case in normalized_smoke_cases)),
        "matrix_overall_status_counts": dict(Counter(str(entry.get("overall_status") or "unknown") for entry in list(matrix.get("entries") or []))),
        "matrix_exposure_state_counts": dict(
            Counter(
                str(dict(entry.get("runtime_normalized_contract") or {}).get("multimodal_lane", {}).get("exposure_state") or "unknown")
                for entry in list(matrix.get("entries") or [])
            )
        ),
        "matrix_route_eligibility_counts": {
            "eligible": sum(
                1
                for entry in list(matrix.get("entries") or [])
                if bool(dict(entry.get("runtime_normalized_contract") or {}).get("multimodal_lane", {}).get("eligible_for_auto_route"))
            ),
            "blocked_or_downgraded": sum(
                1
                for entry in list(matrix.get("entries") or [])
                if not bool(dict(entry.get("runtime_normalized_contract") or {}).get("multimodal_lane", {}).get("eligible_for_auto_route"))
            ),
        },
        "preview_cases": preview_cases,
        "capability_cases": normalized_smoke_cases,
        "matrix_path": str(matrix_path),
        "artifact_paths": {
            "run_dir": str(run_dir),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
            "matrix_json": str(matrix_path),
            "preview_case_dir": str(preview_dir),
            "capability_smoke_summary_json": str(smoke_report.get("artifact_paths", {}).get("summary_json") or ""),
            "capability_smoke_report_md": str(smoke_report.get("artifact_paths", {}).get("report_md") or ""),
            "capability_smoke_case_dir": str(smoke_report.get("artifact_paths", {}).get("case_dir") or ""),
        },
        "redaction": {
            "secret_free": True,
            "live_provider_calls": False,
            "preview_request_redaction": "router_preview_payload",
            "capability_smoke_mode": "dry_run_only",
        },
    }
    _assert_secret_free_summary(summary)
    write_json(summary_path, summary)
    report_path.write_text(_render_report_md(summary, matrix=matrix, smoke_report=smoke_report, preview_case_paths=preview_case_paths), encoding="utf-8", newline="\n")
    if temp_dir is not None:
        temp_dir.cleanup()
    return summary


def _resolve_run_dir(*, root: Path, artifact_root: str | Path | None, run_id: str) -> Path:
    if artifact_root:
        return Path(artifact_root).expanduser().resolve() / run_id
    return root / "PRIVATE" / "agentic-update-pipeline" / "runs" / run_id


def _selected_models(
    configured_models: list[dict[str, Any]],
    *,
    priority_provider_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for item in configured_models:
        if not isinstance(item, dict):
            continue
        if not item.get("enabled", True):
            continue
        provider_id = str(item.get("provider") or "").strip()
        if provider_id not in priority_provider_ids:
            continue
        models.append(dict(item))
    return sorted(models, key=lambda item: (str(item.get("provider") or ""), str(item.get("native_model") or item.get("id") or "")))


def _build_preview_cases(router: RouterService, *, models: list[dict[str, Any]], run_dir: Path) -> list[dict[str, Any]]:
    preview_cases: list[dict[str, Any]] = []
    for model in models:
        model_id = str(model.get("id") or "")
        provider_id = str(model.get("provider") or "")
        for label, effort in _preview_variants(model):
            payload: dict[str, Any] = {"model": model_id, "input": "Reply with exactly: ok", "stream": False}
            if effort is not None:
                payload["reasoning"] = {"effort": effort}
            case_id = slugify(f"preview-{provider_id}-{model.get('native_model') or model_id}-{label}", default="preview-case")
            try:
                preview = router.preview_payload(payload)
                request_shape = dict(preview.get("upstream_payload") or {})
                adapter = str(preview.get("adapter") or "")
                warnings = [str(item) for item in list(preview.get("warnings") or []) if str(item or "").strip()]
                case = {
                    "case_id": case_id,
                    "case_type": "router_preview",
                    "provider_id": provider_id,
                    "model": model_id,
                    "capability_id": "chat.text",
                    "preview_variant": label,
                    "status": "pass",
                    "reasons": [],
                    "warnings": warnings,
                    "route": {
                        "route_mode": "pinned_model_preview",
                        "resolution_status": "ok",
                        "resolved_candidate": {
                            "provider_id": provider_id,
                            "model": str(model.get("native_model") or model_id),
                            "adapter_id": adapter,
                        },
                    },
                    "adapter": adapter,
                    "request_shape": request_shape,
                    "reasoning_mapping": _extract_reasoning_mapping(request_shape, requested_effort=effort, warnings=warnings),
                    "capability_status": "supported",
                    "evidence_path": str(run_dir / "preview-cases" / f"{case_id}.json"),
                }
            except Exception as exc:  # noqa: BLE001
                reasons = [_safe_text(str(exc) or exc.__class__.__name__)]
                case = {
                    "case_id": case_id,
                    "case_type": "router_preview",
                    "provider_id": provider_id,
                    "model": model_id,
                    "capability_id": "chat.text",
                    "preview_variant": label,
                    "status": "blocked",
                    "reasons": reasons,
                    "warnings": [],
                    "route": {
                        "route_mode": "pinned_model_preview",
                        "resolution_status": "blocked",
                        "resolved_candidate": {
                            "provider_id": provider_id,
                            "model": str(model.get("native_model") or model_id),
                            "adapter_id": None,
                        },
                    },
                    "adapter": None,
                    "request_shape": {},
                    "reasoning_mapping": {"requested_effort": effort, "mapping_notes": reasons},
                    "capability_status": "blocked",
                    "evidence_path": str(run_dir / "preview-cases" / f"{case_id}.json"),
                }
            preview_cases.append(case)
    return preview_cases


def _preview_variants(model: dict[str, Any]) -> list[tuple[str, str | None]]:
    supported = {str(item).strip() for item in list(model.get("supported_reasoning_levels") or []) if str(item).strip()}
    default_effort = str(model.get("default_reasoning_level") or "").strip()
    variants: list[tuple[str, str | None]] = [("default", None)]
    if supported and (supported != {"off"} or default_effort not in {"", "off"}):
        variants.append(("off_probe", "off"))
    for label in ("high", "xhigh"):
        if label in supported:
            variants.append((label, label))
    deduped: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for item in variants:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return [item for item in deduped if item[0] in _PREVIEW_REASONING_LABELS]


def _extract_reasoning_mapping(
    request_shape: dict[str, Any],
    *,
    requested_effort: str | None,
    warnings: list[str],
) -> dict[str, Any]:
    mapping: dict[str, Any] = {
        "requested_effort": requested_effort or "default",
        "mapping_notes": warnings[:6],
    }
    for key in ("reasoning", "enable_thinking", "thinking", "reasoning_effort", "max_tokens"):
        if key in request_shape:
            mapping[key] = request_shape.get(key)
    if isinstance(request_shape.get("reasoning"), dict):
        mapping["normalized_effort"] = dict(request_shape.get("reasoning") or {}).get("effort")
    elif "reasoning_effort" in request_shape:
        mapping["normalized_effort"] = request_shape.get("reasoning_effort")
    elif request_shape.get("enable_thinking") is False:
        mapping["normalized_effort"] = "off"
    return mapping


def _capability_smoke_cases(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    registry = default_capability_registry()
    capability_ids = [
        spec.capability_id
        for spec in [registry.capability_spec(capability_id) for capability_id in registry.capability_ids()]
        if spec.lane_type == "model_backed" and spec.capability_id in _MODELED_MULTIMODAL_CAPABILITIES
    ]
    cases: list[dict[str, Any]] = []
    for model in models:
        provider_id = str(model.get("provider") or "")
        native_model = str(model.get("native_model") or "")
        for capability_id in capability_ids:
            cases.append(
                {
                    "case_id": f"{provider_id}-{native_model}-{capability_id}-dry-run",
                    "capability_id": capability_id,
                    "provider_id": provider_id,
                    "model": native_model,
                    "mode": "dry_run",
                }
            )
    return cases


def _normalize_smoke_cases(report: dict[str, Any], *, model_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for case in list(report.get("cases") or []):
        if not isinstance(case, dict):
            continue
        provider_id = str(case.get("provider_id") or "")
        model = str(case.get("model") or "")
        full_model_id = f"{provider_id}/{model}" if provider_id and model and "/" not in model else model
        model_record = model_index.get(full_model_id) or {}
        route = dict(case.get("route") or {})
        candidate = dict(route.get("resolved_candidate") or {})
        normalized.append(
            {
                "case_id": str(case.get("case_id") or ""),
                "case_type": "capability_smoke",
                "provider_id": provider_id,
                "model": full_model_id,
                "capability_id": str(case.get("capability_id") or ""),
                "preview_variant": "capability_dry_run",
                "status": str(case.get("status") or "blocked"),
                "reasons": [str(item) for item in list(case.get("reasons") or []) if str(item or "").strip()],
                "warnings": [str(item) for item in list(case.get("warnings") or []) if str(item or "").strip()],
                "route": route,
                "adapter": candidate.get("adapter_id"),
                "request_shape": dict((case.get("sanitized_request") or {}).get("sample_input") or {}),
                "reasoning_mapping": {},
                "capability_status": _classify_capability_status(case, model_record=model_record),
                "evidence_path": f"PRIVATE/provider-compatibility/runs/{report.get('run_id')}/cases/{case.get('case_id')}.json",
            }
        )
    return normalized


def _classify_capability_status(case: dict[str, Any], *, model_record: dict[str, Any]) -> str:
    status = str(case.get("status") or "blocked")
    if status in {"pass", "partial"}:
        return "supported"
    if status == "skipped":
        return "skipped"
    capability_id = str(case.get("capability_id") or "")
    route = dict(case.get("route") or {})
    if str(route.get("resolution_status") or "") == "no_capability_candidate":
        required = set(_REQUIRED_MODALITIES.get(capability_id, ()))
        modalities = {str(item).lower() for item in list(model_record.get("input_modalities") or [])}
        if required and required.issubset(modalities):
            return "conflicting"
        return "unsupported"
    if status in {"fail", "blocked"}:
        return "conflicting"
    return "unknown"


def _build_matrix(
    *,
    providers: list[dict[str, Any]],
    models: list[dict[str, Any]],
    preview_cases: list[dict[str, Any]],
    smoke_cases: list[dict[str, Any]],
    run_id: str,
    created_at: str,
    smoke_report: dict[str, Any],
) -> dict[str, Any]:
    matrix = empty_provider_model_compatibility_matrix()
    matrix["generated_at"] = created_at
    matrix["matrix_id"] = run_id
    matrix["matrix_scope"] = {
        "source_kind": "dry_run_preview_and_capability_smoke",
        "managed_session_mode": "not_required",
        "managed_username": None,
        "registry_provider_ids": sorted({str(item.get("id") or item.get("provider_id") or "") for item in providers if str(item.get("id") or item.get("provider_id") or "").strip()}),
        "effective_provider_ids": sorted({str(item.get("provider") or "") for item in models if str(item.get("provider") or "").strip()}),
        "web_lane_policy": "standalone",
    }
    matrix["evidence_index"] = {
        "source_files": [
            "apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/provider_compatibility_smoke.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py",
        ],
        "runtime_sources": ["router.preview_payload", "run_provider_compatibility_smoke"],
        "artifact_paths": [
            f"PRIVATE/agentic-update-pipeline/runs/{run_id}/summary.json",
            f"PRIVATE/agentic-update-pipeline/runs/{run_id}/matrix.json",
            str(smoke_report.get("artifact_paths", {}).get("summary_json") or ""),
        ],
    }
    preview_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    smoke_by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in preview_cases:
        preview_by_model[str(case.get("model") or "")].append(case)
    for case in smoke_cases:
        smoke_by_model[str(case.get("model") or "")].append(case)
    for model in models:
        model_id = str(model.get("id") or "")
        model_preview_cases = preview_by_model.get(model_id, [])
        model_smoke_cases = smoke_by_model.get(model_id, [])
        smoke_by_capability = {str(case.get("capability_id") or ""): case for case in model_smoke_cases}
        for capability_id in _MODELED_MULTIMODAL_CAPABILITIES:
            case = smoke_by_capability.get(capability_id)
            if case is None:
                continue
            entry = compatibility_matrix_entry_template()
            entry["entry_id"] = f"{model_id}:{capability_id}"
            entry["provider_id"] = str(model.get("provider") or "")
            entry["model_id"] = model_id
            entry["display_name"] = f"{str(model.get('display_name') or model.get('native_model') or model_id)} {capability_id}"
            runtime_contract = dict(model.get("runtime_provider_contract") or {})
            capability_metadata = dict(runtime_contract.get("capability_metadata") or {})
            lane_projection = _lane_projection(
                model=model,
                capability_id=capability_id,
                smoke_case=case,
            )
            entry["declared_capability"] = {
                "source_of_truth": ["router_config.models", "capability_registry", "capability_smoke.dry_run"],
                "protocol": str(model.get("adapter_type") or model.get("protocol") or model.get("reasoning_policy_mode") or ""),
                "reasoning_mode": str(model.get("reasoning_policy_mode") or ""),
                "default_model": str(model.get("native_model") or model_id),
                "input_modalities": list(model.get("input_modalities") or []),
                "edit_policy": {"apply_patch_tool_type": model.get("apply_patch_tool_type")},
                "tool_policy": {
                    "supports_parallel_tool_calls": bool(model.get("supports_parallel_tool_calls", False)),
                    "supports_mcp_tools": bool(model.get("supports_mcp_tools", False)),
                    "supports_search_tool": bool(model.get("supports_search_tool", False)),
                },
                "context_policy": {
                    "advertised_context_window": model.get("advertised_context_window"),
                    "temperature_adapter_policy": model.get("temperature_adapter_policy"),
                    "source_status": model.get("source_status"),
                },
                "fallback_policy": {
                    "recommended": bool(model.get("recommended", False)),
                    "default_for_provider": bool(model.get("default_for_provider", False)),
                    "deprecated": bool(model.get("deprecated", False)),
                },
                "route_eligibility": {
                    "documented_state": lane_projection["documented_state"],
                    "wired_state": lane_projection["wired_state"],
                    "verified_state": lane_projection["verified_state"],
                    "exposure_state": lane_projection["exposure_state"],
                    "required_modalities": list(_REQUIRED_MODALITIES.get(capability_id, ())),
                    "declared_modalities": list(model.get("input_modalities") or []),
                    "downgrade_reasons": list(lane_projection["downgrade_reasons"]),
                },
            }
            entry["runtime_normalized_contract"] = {
                "source_of_truth": ["model_catalog.catalog", "capability_registry", "capability_smoke.dry_run"],
                "managed_key_available": None,
                "effective_default_model": str(model.get("native_model") or model_id),
                "codex_runtime_metadata": dict(runtime_contract.get("codex_runtime_metadata") or {}),
                "capability_metadata": capability_metadata,
                "reasoning_state": dict(capability_metadata.get("reasoning_state") or {}),
                "context_window": dict(capability_metadata.get("context_window") or {}),
                "authority": {
                    "authority_tier": model.get("authority_tier"),
                    "authority_reason": model.get("authority_reason"),
                    "command_execution_status": model.get("command_execution_status"),
                },
                "contract_warnings": list(runtime_contract.get("warnings") or []),
                "multimodal_lane": lane_projection,
            }
            entry["validated_evidence"] = {
                "validation_status": _aggregate_lane_validation_status(case),
                "health_status": _aggregate_health_status(model_preview_cases),
                "validation_scope": sorted(
                    {
                        *[f"preview:{preview.get('preview_variant')}" for preview in model_preview_cases],
                        f"capability:{capability_id}",
                        f"route:{lane_projection['route_resolution_status']}",
                        f"exposure:{lane_projection['exposure_state']}",
                        f"request_shape:{lane_projection['request_shape_validation_status']}",
                    }
                ),
                "evidence_paths": [
                    str(case.get("evidence_path") or ""),
                    *[str(preview.get("evidence_path") or "") for preview in model_preview_cases if str(preview.get("evidence_path") or "").strip()],
                ],
                "last_verified_at": created_at,
                "usage_signals": {
                    "preview_variants": [str(preview.get("preview_variant") or "") for preview in model_preview_cases],
                    "capability_status": case.get("capability_status"),
                    "route_resolution_status": lane_projection["route_resolution_status"],
                },
                "known_failures": [*list(case.get("reasons") or [])][:16],
                "known_pitfalls": [*list(case.get("warnings") or [])][:16],
                "notes": [
                    "dry_run_only",
                    "not_provider_backed",
                    f"adapter_family:{lane_projection['adapter_family']}",
                ],
            }
            entry["overall_status"] = _aggregate_lane_overall_status(lane_projection)
            entry["warnings"] = list(
                {
                    *[str(item) for item in list(model.get("ui_warnings") or []) if str(item or "").strip()],
                    *[str(item) for item in entry["validated_evidence"]["known_pitfalls"] if str(item or "").strip()],
                    *[str(item) for item in lane_projection["downgrade_reasons"] if str(item or "").strip()],
                }
            )
            matrix["entries"].append(entry)
    return matrix


def _aggregate_lane_validation_status(case: dict[str, Any]) -> str:
    capability_status = str(case.get("capability_status") or "unknown")
    status = str(case.get("status") or "blocked")
    if capability_status == "supported" and status == "pass":
        return "partial"
    if capability_status == "unsupported":
        return "blocked"
    if capability_status == "conflicting":
        return "fail"
    if status == "skipped":
        return "skipped"
    if status == "blocked":
        return "blocked"
    return "unknown"


def _aggregate_health_status(preview_cases: list[dict[str, Any]]) -> str:
    statuses = {str(case.get("status") or "blocked") for case in preview_cases}
    if "pass" in statuses:
        return "pass"
    if "blocked" in statuses:
        return "blocked"
    return "unknown"


def _aggregate_lane_overall_status(lane_projection: dict[str, Any]) -> str:
    exposure_state = str(lane_projection.get("exposure_state") or "unknown")
    if exposure_state == "verified_runnable":
        return "verified"
    if exposure_state in {"wired_unverified", "documented_unwired"}:
        return "partial"
    if exposure_state in {"blocked", "hidden"}:
        return "blocked"
    return "unknown"


def _render_report_md(
    summary: dict[str, Any],
    *,
    matrix: dict[str, Any],
    smoke_report: dict[str, Any],
    preview_case_paths: list[str],
) -> str:
    lines = [
        "# Provider Capability Dry-Run Matrix",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Created: `{summary.get('created_at')}`",
        f"- Priority providers: `{', '.join(list(summary.get('priority_provider_ids') or []))}`",
        f"- Covered providers: `{', '.join(list(summary.get('provider_ids_covered') or []))}`",
        f"- Covered models: `{len(list(summary.get('model_ids_covered') or []))}`",
        f"- Preview cases: `{summary.get('preview_case_count')}`",
        f"- Capability dry-run cases: `{summary.get('capability_smoke_case_count')}`",
        f"- Matrix entries: `{summary.get('matrix_entry_count')}`",
        f"- Preview status counts: `{json.dumps(summary.get('preview_status_counts') or {}, ensure_ascii=False)}`",
        f"- Capability status counts: `{json.dumps(summary.get('capability_status_counts') or {}, ensure_ascii=False)}`",
        f"- Matrix overall counts: `{json.dumps(summary.get('matrix_overall_status_counts') or {}, ensure_ascii=False)}`",
        f"- Matrix exposure counts: `{json.dumps(summary.get('matrix_exposure_state_counts') or {}, ensure_ascii=False)}`",
        f"- Matrix route eligibility counts: `{json.dumps(summary.get('matrix_route_eligibility_counts') or {}, ensure_ascii=False)}`",
        "",
        "## Artifact Paths",
        "",
        f"- Summary JSON: `{summary.get('artifact_paths', {}).get('summary_json')}`",
        f"- Matrix JSON: `{summary.get('artifact_paths', {}).get('matrix_json')}`",
        f"- Preview case dir: `{summary.get('artifact_paths', {}).get('preview_case_dir')}`",
        f"- Capability smoke summary: `{summary.get('artifact_paths', {}).get('capability_smoke_summary_json')}`",
        f"- Capability smoke report: `{summary.get('artifact_paths', {}).get('capability_smoke_report_md')}`",
        "",
        "## Dry-Run Findings",
        "",
    ]
    blocked_preview = [case for case in list(summary.get("preview_cases") or []) if str(case.get("status") or "") != "pass"]
    if blocked_preview:
        lines.append("### Preview Blockers")
        lines.append("")
        for case in blocked_preview[:12]:
            lines.append(
                f"- `{case.get('case_id')}` `{case.get('model')}` `{case.get('preview_variant')}` -> `{case.get('status')}` `{json.dumps(case.get('reasons') or [], ensure_ascii=False)}`"
            )
        lines.append("")
    conflicting_capability_cases = [
        case for case in list(summary.get("capability_cases") or []) if str(case.get("capability_status") or "") in {"conflicting", "unknown"}
    ]
    if conflicting_capability_cases:
        lines.append("### Conflicting Or Unknown Capability Cases")
        lines.append("")
        for case in conflicting_capability_cases[:20]:
            lines.append(
                f"- `{case.get('capability_id')}` `{case.get('model')}` -> status=`{case.get('status')}` capability_status=`{case.get('capability_status')}` reasons=`{json.dumps(case.get('reasons') or [], ensure_ascii=False)}`"
            )
        lines.append("")
    unsupported_cases = [case for case in list(summary.get("capability_cases") or []) if str(case.get("capability_status") or "") == "unsupported"]
    if unsupported_cases:
        lines.append("### Unsupported Capability Cases")
        lines.append("")
        for case in unsupported_cases[:20]:
            lines.append(
                f"- `{case.get('capability_id')}` `{case.get('model')}` -> route=`{dict(case.get('route') or {}).get('resolution_status')}`"
            )
        lines.append("")
    lines.extend(["### Lane Exposure Projection", ""])
    # The matrix is deliberately bounded by the selected catalog, so omitting
    # a tail slice from the operator report can hide a real model/capability
    # lane even though it exists in the machine-readable artifact. Keep the
    # Markdown projection complete as well as the JSON matrix.
    for entry in list(matrix.get("entries") or []):
        lane = dict(dict(entry.get("runtime_normalized_contract") or {}).get("multimodal_lane") or {})
        lines.append(
            f"- `{entry.get('entry_id')}` capability=`{lane.get('capability_id')}` exposure=`{lane.get('exposure_state')}` "
            f"route=`{lane.get('route_resolution_status')}` auto=`{lane.get('eligible_for_auto_route')}` "
            f"adapter=`{lane.get('adapter_id')}` family=`{lane.get('adapter_family')}` "
            f"request_shape=`{lane.get('request_shape_validation_status')}` reasons=`{json.dumps(lane.get('downgrade_reasons') or [], ensure_ascii=False)}`"
        )
    lines.append("")
    lines.extend(
        [
            "## Matrix Summary",
            "",
            f"- Matrix entries: `{len(list(matrix.get('entries') or []))}`",
            f"- Smoke report status: `{smoke_report.get('status')}`",
            f"- Preview case files written: `{len(preview_case_paths)}`",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _safe_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?i)(api[_-]?key|authorization|token|cookie)(['\":= ]+)([A-Za-z0-9._~+/=-]{8,})", r"\1\2[redacted]", text)
    text = re.sub(r"data:image/[^'\"\s,]+,?[A-Za-z0-9+/=._:-]*", "data:image/[redacted]", text)
    return text[:1200]


def _assert_secret_free_summary(summary: dict[str, Any]) -> None:
    _reject_secret_like(summary, path="provider_capability_dry_run_matrix")


def _lane_projection(
    *,
    model: dict[str, Any],
    capability_id: str,
    smoke_case: dict[str, Any],
) -> dict[str, Any]:
    route = dict(smoke_case.get("route") or {})
    candidate = dict(route.get("resolved_candidate") or {})
    model_id = str(model.get("id") or "")
    native_model = str(model.get("native_model") or "")
    declared_modalities = [str(item).strip().lower() for item in list(model.get("input_modalities") or []) if str(item).strip()]
    required_modalities = list(_REQUIRED_MODALITIES.get(capability_id, ()))
    has_required_modalities = all(modality in set(declared_modalities) for modality in required_modalities)
    adapter_id = str(candidate.get("adapter_id") or "")
    adapter_family = _adapter_family_for(adapter_id)
    route_resolution_status = str(route.get("resolution_status") or "unknown")
    capability_status = str(smoke_case.get("capability_status") or "unknown")
    model_source_status = str(model.get("source_status") or "unknown")

    if required_modalities and not has_required_modalities:
        documented_state = "unsupported"
    elif model_source_status in {"official_docs", "screenshot_seed", "first_party_unverified"}:
        documented_state = "documented"
    else:
        documented_state = "unknown"

    resolved_model = str(candidate.get("model") or "")
    resolved_provider = str(candidate.get("provider_id") or "")
    if route_resolution_status == "ok" and resolved_provider == str(model.get("provider") or "") and resolved_model == native_model:
        wired_state = "wired"
    elif route_resolution_status == "no_capability_candidate":
        wired_state = "unwired"
    else:
        wired_state = "unknown"

    if capability_status == "supported":
        verified_state = "partial"
    elif capability_status in {"conflicting", "unsupported"}:
        verified_state = "blocked"
    else:
        verified_state = "unknown"

    downgrade_reasons: list[str] = []
    if documented_state == "unsupported":
        downgrade_reasons.append("model_missing_required_input_modality")
    if route_resolution_status == "no_capability_candidate":
        downgrade_reasons.append("no_capability_candidate")
    downgrade_reasons.extend([str(item) for item in list(smoke_case.get("reasons") or []) if str(item or "").strip()])

    if verified_state == "blocked":
        exposure_state = "blocked" if documented_state != "unsupported" else "hidden"
    elif documented_state == "documented" and wired_state == "wired":
        exposure_state = "wired_unverified"
    elif documented_state == "documented" and wired_state == "unwired":
        exposure_state = "documented_unwired"
    elif documented_state == "unsupported":
        exposure_state = "hidden"
    else:
        exposure_state = "unknown"

    request_shape_validation_status = (
        "pass"
        if route_resolution_status == "ok" and capability_status == "supported"
        else "blocked"
        if capability_status in {"unsupported", "conflicting"} or route_resolution_status == "no_capability_candidate"
        else "unknown"
    )
    request_shape_validation_reasons = list(dict(smoke_case.get("sanitized_response") or {}).get("notes") or [])[:8]
    modality_limits = dict(model.get("modality_limits") or {})

    return {
        "capability_id": capability_id,
        "model_id": model_id,
        "route_resolution_status": route_resolution_status,
        "eligible_for_auto_route": exposure_state == "verified_runnable",
        "eligible_for_pinned_route": exposure_state == "verified_runnable",
        "adapter_id": adapter_id or None,
        "adapter_family": adapter_family,
        "documented_state": documented_state,
        "wired_state": wired_state,
        "verified_state": verified_state,
        "exposure_state": exposure_state,
        "capability_status": capability_status,
        "required_modalities": required_modalities,
        "declared_modalities": declared_modalities,
        "request_shape_validation_status": request_shape_validation_status,
        "request_shape_validation_reasons": request_shape_validation_reasons,
        "modality_limits": modality_limits,
        "expected_artifact_path": str(smoke_case.get("evidence_path") or ""),
        "downgrade_reasons": downgrade_reasons[:12],
    }


def _adapter_family_for(adapter_id: str) -> str:
    text = str(adapter_id or "").strip()
    if not text:
        return "none"
    if text.startswith("qwen.image.dashscope"):
        return "dashscope_image"
    if text.startswith("yunwu.image."):
        return "openai_compatible_image"
    if text.startswith("qwen.asr."):
        return "dashscope_asr"
    if text.startswith("qwen.tts."):
        return "dashscope_tts"
    if text.endswith(".vision.chat.v1"):
        return "chat_multimodal_vision"
    return "unknown"


def _reject_secret_like(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_secret_like(item, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secret_like(item, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if value.startswith("data:image/"):
        raise ValueError(f"Inline image data leaked into dry-run matrix payload at {path}")
    if _SECRET_VALUE_RE.search(value):
        raise ValueError(f"Secret-like value leaked into dry-run matrix payload at {path}")
