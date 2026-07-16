from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

from .common import now_iso, read_json, slugify, write_json
from .exhaustive_smoke_contract import (
    default_execution_policy,
    normalize_exhaustive_smoke_case,
    normalize_exhaustive_smoke_result,
    outcome_from_lower_level_status,
    assert_secret_free_exhaustive_smoke_payload,
)


EXHAUSTIVE_SMOKE_BATCH_PLAN_SCHEMA_VERSION = "astrabridge-exhaustive-smoke-batch-plan-v1"
EXHAUSTIVE_SMOKE_BATCH_MANIFEST_SCHEMA_VERSION = "astrabridge-exhaustive-smoke-batch-manifest-v1"
EXHAUSTIVE_SMOKE_RUN_STATE_SCHEMA_VERSION = "astrabridge-exhaustive-smoke-run-state-v1"
EXHAUSTIVE_SMOKE_RUN_SUMMARY_SCHEMA_VERSION = "astrabridge-exhaustive-smoke-run-summary-v1"
EXHAUSTIVE_SMOKE_PREFLIGHT_SCHEMA_VERSION = "astrabridge-exhaustive-smoke-preflight-v1"

NONLIVE_EXECUTION_POLICIES = {"skip_case", "record_unsupported"}
RUN_STATE_PENDING = "pending"
RUN_STATE_COMPLETED = "completed"

_BATCH_FAMILIES = (
    {
        "family_id": "batch-a-general-model",
        "family_label": "Batch A: General Text, Tool, And Code-Agent Lanes",
        "step_id": "6",
        "matches": lambda case: str(case.get("lane_group") or "") == "general_model",
        "selection_metadata": {"lane_group": "general_model"},
    },
    {
        "family_id": "batch-b-vision-analyze",
        "family_label": "Batch B: Vision Analyze Lanes",
        "step_id": "7",
        "matches": lambda case: str(case.get("lane_kind") or "") == "vision.analyze",
        "selection_metadata": {"lane_kind": "vision.analyze"},
    },
    {
        "family_id": "batch-c-speech-transcribe",
        "family_label": "Batch C: Speech Transcribe Lanes",
        "step_id": "8",
        "matches": lambda case: str(case.get("lane_kind") or "") == "speech.transcribe",
        "selection_metadata": {"lane_kind": "speech.transcribe"},
    },
    {
        "family_id": "batch-d-speech-synthesize",
        "family_label": "Batch D: Speech Synthesize Lanes",
        "step_id": "9",
        "matches": lambda case: str(case.get("lane_kind") or "") == "speech.synthesize",
        "selection_metadata": {"lane_kind": "speech.synthesize"},
    },
    {
        "family_id": "batch-e-image-generate",
        "family_label": "Batch E: Image Generate Lanes",
        "step_id": "10",
        "matches": lambda case: str(case.get("lane_kind") or "") == "image.generate",
        "selection_metadata": {"lane_kind": "image.generate"},
    },
    {
        "family_id": "batch-f-continuation",
        "family_label": "Batch F: Compact, Health-Check, And Same-Task Continuation Lanes",
        "step_id": "11",
        "matches": lambda case: str(case.get("lane_group") or "") == "compact_handoff",
        "selection_metadata": {"lane_group": "compact_handoff"},
    },
)


ExhaustiveSmokeExecutor = Callable[[dict[str, Any]], dict[str, Any]]
HttpGetJson = Callable[[str], dict[str, Any]]


def build_exhaustive_smoke_batch_plan(
    case_manifest: dict[str, Any],
    *,
    run_id: str | None = None,
    generated_at: str | None = None,
    batch_size: int = 12,
) -> dict[str, Any]:
    if not isinstance(case_manifest, dict):
        raise TypeError("Exhaustive smoke case manifest must be a dict.")
    cases = [normalize_exhaustive_smoke_case(item) for item in list(case_manifest.get("cases") or [])]
    if not cases:
        raise ValueError("Exhaustive smoke batch plan requires at least one synthesized case.")
    resolved_batch_size = max(1, int(batch_size or 1))
    created_at = generated_at or now_iso()
    resolved_run_id = slugify(run_id or str(case_manifest.get("run_id") or "exhaustive-smoke-run"), default="exhaustive-smoke-run")
    batches: list[dict[str, Any]] = []
    family_summaries: list[dict[str, Any]] = []
    for family in _BATCH_FAMILIES:
        family_cases = [case for case in cases if family["matches"](case)]
        if not family_cases:
            continue
        chunk_count = (len(family_cases) + resolved_batch_size - 1) // resolved_batch_size
        family_summaries.append(
            {
                "family_id": family["family_id"],
                "family_label": family["family_label"],
                "step_id": family["step_id"],
                "case_count": len(family_cases),
                "chunk_count": chunk_count,
                "scope_decision_counts": _count_by_key(family_cases, "scope_decision"),
            }
        )
        for chunk_index in range(chunk_count):
            start = chunk_index * resolved_batch_size
            chunk_cases = family_cases[start : start + resolved_batch_size]
            batch_id = f"{family['family_id']}-{chunk_index + 1:02d}"
            batches.append(
                build_exhaustive_smoke_batch_manifest(
                    chunk_cases,
                    run_id=resolved_run_id,
                    generated_at=created_at,
                    batch_id=batch_id,
                    family_id=str(family["family_id"]),
                    family_label=str(family["family_label"]),
                    step_id=str(family["step_id"]),
                    source_case_manifest=dict(case_manifest.get("source_manifest") or {}),
                    selection_policy={
                        **dict(family.get("selection_metadata") or {}),
                        "batch_size": resolved_batch_size,
                        "chunk_index": chunk_index + 1,
                        "chunk_count": chunk_count,
                    },
                )
            )
    plan = {
        "schema_version": EXHAUSTIVE_SMOKE_BATCH_PLAN_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "generated_at": created_at,
        "batch_size": resolved_batch_size,
        "source_case_manifest": {
            "schema_version": str(case_manifest.get("schema_version") or "").strip() or None,
            "case_schema_version": str(case_manifest.get("case_schema_version") or "").strip() or None,
            "run_id": str(case_manifest.get("run_id") or "").strip() or None,
            "source_manifest": dict(case_manifest.get("source_manifest") or {}),
        },
        "scope_policy": dict(case_manifest.get("scope_policy") or {}),
        "family_summaries": family_summaries,
        "batches": batches,
        "summary": {
            "case_count": len(cases),
            "batch_count": len(batches),
            "family_count": len(family_summaries),
            "scope_decision_counts": _count_by_key(cases, "scope_decision"),
            "provider_ids": sorted({str(case.get("provider_id") or "") for case in cases if str(case.get("provider_id") or "").strip()}),
        },
    }
    assert_secret_free_exhaustive_smoke_payload(plan, path="exhaustive_smoke_batch_plan")
    return plan


def build_exhaustive_smoke_batch_manifest(
    cases: list[dict[str, Any]],
    *,
    run_id: str,
    generated_at: str,
    batch_id: str,
    family_id: str,
    family_label: str,
    step_id: str,
    source_case_manifest: dict[str, Any],
    selection_policy: dict[str, Any],
) -> dict[str, Any]:
    normalized_cases = [normalize_exhaustive_smoke_case(item) for item in cases]
    if not normalized_cases:
        raise ValueError("Batch manifest requires at least one case.")
    manifest = {
        "schema_version": EXHAUSTIVE_SMOKE_BATCH_MANIFEST_SCHEMA_VERSION,
        "run_id": str(run_id),
        "generated_at": str(generated_at),
        "batch_id": str(batch_id),
        "family_id": str(family_id),
        "family_label": str(family_label),
        "step_id": str(step_id),
        "source_case_manifest": dict(source_case_manifest or {}),
        "selection_policy": dict(selection_policy or {}),
        "summary": {
            "case_count": len(normalized_cases),
            "scope_decision_counts": _count_by_key(normalized_cases, "scope_decision"),
            "execution_policy_counts": _count_by_key(normalized_cases, "execution_policy"),
            "lane_group_counts": _count_by_key(normalized_cases, "lane_group"),
            "provider_ids": sorted({str(case.get("provider_id") or "") for case in normalized_cases if str(case.get("provider_id") or "").strip()}),
        },
        "cases": normalized_cases,
    }
    assert_secret_free_exhaustive_smoke_payload(manifest, path=f"exhaustive_smoke_batch_manifest:{batch_id}")
    return manifest


def materialize_exhaustive_smoke_run(
    case_manifest: dict[str, Any],
    *,
    run_dir: str | Path,
    run_id: str | None = None,
    generated_at: str | None = None,
    batch_size: int = 12,
) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    plan = build_exhaustive_smoke_batch_plan(
        case_manifest,
        run_id=run_id,
        generated_at=generated_at,
        batch_size=batch_size,
    )
    batch_plan_path = root / "batch-plan.json"
    write_json(batch_plan_path, plan)
    for batch in list(plan.get("batches") or []):
        batch_dir = root / "batches" / str(batch.get("batch_id") or "batch")
        write_json(batch_dir / "manifest.json", batch)
    state = initialize_exhaustive_smoke_run_state(
        plan,
        batch_plan_path=batch_plan_path,
        run_dir=root,
    )
    state_path = root / "run-state.json"
    write_json(state_path, state)
    summary = summarize_exhaustive_smoke_run_state(state)
    write_json(root / "summary.json", summary)
    return {
        "batch_plan": plan,
        "run_state": state,
        "summary": summary,
        "artifact_paths": {
            "run_dir": str(root),
            "batch_plan_json": str(batch_plan_path),
            "run_state_json": str(state_path),
            "summary_json": str(root / "summary.json"),
        },
    }


def initialize_exhaustive_smoke_run_state(
    batch_plan: dict[str, Any],
    *,
    batch_plan_path: str | Path | None = None,
    run_dir: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(batch_plan, dict):
        raise TypeError("Batch plan must be a dict.")
    batches = list(batch_plan.get("batches") or [])
    created = created_at or now_iso()
    case_statuses: dict[str, dict[str, Any]] = {}
    batch_statuses: dict[str, dict[str, Any]] = {}
    for batch in batches:
        batch_id = str(batch.get("batch_id") or "").strip()
        if not batch_id:
            continue
        cases = [normalize_exhaustive_smoke_case(item) for item in list(batch.get("cases") or [])]
        batch_statuses[batch_id] = {
            "family_id": str(batch.get("family_id") or ""),
            "step_id": str(batch.get("step_id") or ""),
            "total_cases": len(cases),
            "completed_cases": 0,
            "pending_cases": len(cases),
            "status": "pending",
            "last_invoked_at": None,
            "last_completed_at": None,
            "outcome_counts": {},
        }
        for case in cases:
            case_id = str(case.get("case_id") or "").strip()
            case_statuses[case_id] = {
                "batch_id": batch_id,
                "family_id": str(batch.get("family_id") or ""),
                "scope_decision": str(case.get("scope_decision") or ""),
                "execution_policy": str(case.get("execution_policy") or default_execution_policy(str(case.get("scope_decision") or ""))),
                "status": RUN_STATE_PENDING,
                "outcome": None,
                "result_path": None,
                "completed_at": None,
                "attempt_count": 0,
            }
    state = {
        "schema_version": EXHAUSTIVE_SMOKE_RUN_STATE_SCHEMA_VERSION,
        "run_id": str(batch_plan.get("run_id") or ""),
        "created_at": created,
        "updated_at": created,
        "run_dir": str(Path(run_dir).resolve()) if run_dir is not None else None,
        "batch_plan_path": str(Path(batch_plan_path).resolve()) if batch_plan_path is not None else None,
        "source_case_manifest": dict(batch_plan.get("source_case_manifest") or {}),
        "case_count": len(case_statuses),
        "completed_case_count": 0,
        "pending_case_count": len(case_statuses),
        "batch_statuses": batch_statuses,
        "case_statuses": case_statuses,
        "resume_markers": _resume_markers_from_state(batch_plan, case_statuses=case_statuses),
    }
    assert_secret_free_exhaustive_smoke_payload(state, path="exhaustive_smoke_run_state")
    return state


def run_exhaustive_smoke_preflight(
    case_manifest: dict[str, Any],
    *,
    run_dir: str | Path,
    sidecar_base_url: str | None,
    http_get_json: HttpGetJson | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    getter = http_get_json or _http_get_json
    expected_provider_ids = _expected_provider_ids(case_manifest)
    checks = [
        _artifact_root_check(root),
    ]
    health_payload: dict[str, Any] = {}
    session_payload: dict[str, Any] = {}
    profiles_payload: dict[str, Any] = {}
    base_url = str(sidecar_base_url or "").strip()
    if base_url:
        try:
            health_payload = getter(base_url.rstrip("/") + "/api/health")
            checks.append(
                {
                    "check_id": "sidecar_reachability",
                    "status": "pass",
                    "details": {
                        "base_url": base_url,
                        "service": health_payload.get("service"),
                        "listen_port": ((health_payload.get("sidecar") or {}).get("listen_port")),
                        "runtime_running": ((health_payload.get("runtime") or {}).get("running")),
                        "router_running": ((health_payload.get("router") or {}).get("running")),
                        "provider_count": ((health_payload.get("router") or {}).get("provider_count")),
                        "model_count": ((health_payload.get("router") or {}).get("model_count")),
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                {
                    "check_id": "sidecar_reachability",
                    "status": "fail",
                    "details": {
                        "base_url": base_url,
                        "error": str(exc),
                        "error_type": exc.__class__.__name__,
                    },
                }
            )
            preflight = _build_preflight_payload(
                run_dir=root,
                sidecar_base_url=base_url,
                expected_provider_ids=expected_provider_ids,
                checks=checks,
            )
            assert_secret_free_exhaustive_smoke_payload(preflight, path="exhaustive_smoke_preflight")
            return preflight
        try:
            session_payload = getter(base_url.rstrip("/") + "/api/llm-manager/session")
        except Exception as exc:  # noqa: BLE001
            session_payload = {"error": str(exc), "error_type": exc.__class__.__name__}
        try:
            profiles_payload = getter(base_url.rstrip("/") + "/api/profiles")
        except Exception as exc:  # noqa: BLE001
            profiles_payload = {"error": str(exc), "error_type": exc.__class__.__name__}
        checks.append(_managed_vault_check(session_payload))
        checks.append(_provider_availability_check(expected_provider_ids, session_payload=session_payload, profiles_payload=profiles_payload))
    else:
        checks.append(
            {
                "check_id": "sidecar_reachability",
                "status": "fail",
                "details": {"error": "sidecar_base_url is required for provider-backed preflight."},
            }
        )
    preflight = _build_preflight_payload(
        run_dir=root,
        sidecar_base_url=base_url or None,
        expected_provider_ids=expected_provider_ids,
        checks=checks,
    )
    preflight["observed"] = {
        "health": {
            "service": health_payload.get("service"),
            "listen_port": ((health_payload.get("sidecar") or {}).get("listen_port")),
            "runtime_running": ((health_payload.get("runtime") or {}).get("running")),
            "router_running": ((health_payload.get("router") or {}).get("running")),
            "provider_count": ((health_payload.get("router") or {}).get("provider_count")),
            "model_count": ((health_payload.get("router") or {}).get("model_count")),
        }
        if health_payload
        else {},
        "session": {
            "mode": session_payload.get("mode"),
            "username": session_payload.get("username"),
            "unlocked": session_payload.get("unlocked"),
            "key_count": session_payload.get("key_count"),
            "active_provider_ids": sorted({str(key) for key in dict(session_payload.get("active_key_ids") or {}).keys() if str(key).strip()}),
        }
        if session_payload and "error" not in session_payload
        else {},
        "profiles": {
            "provider_ids": sorted(
                {
                    str(item.get("provider_id") or "")
                    for item in list(profiles_payload.get("profiles") or [])
                    if isinstance(item, dict) and str(item.get("provider_id") or "").strip()
                }
            ),
            "profile_count": len(list(profiles_payload.get("profiles") or [])) if isinstance(profiles_payload, dict) else 0,
        }
        if profiles_payload and "error" not in profiles_payload
        else {},
    }
    assert_secret_free_exhaustive_smoke_payload(preflight, path="exhaustive_smoke_preflight")
    return preflight


def execute_exhaustive_smoke_batch(
    batch_manifest: dict[str, Any],
    *,
    run_dir: str | Path,
    executor: ExhaustiveSmokeExecutor | None = None,
    max_cases: int | None = None,
) -> dict[str, Any]:
    batch = dict(batch_manifest or {})
    if str(batch.get("schema_version") or "") != EXHAUSTIVE_SMOKE_BATCH_MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unexpected exhaustive smoke batch manifest schema version.")
    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "run-state.json"
    batch_plan_path = root / "batch-plan.json"
    batch_plan = read_json(batch_plan_path, {})
    if state_path.exists():
        state = dict(read_json(state_path, {}))
    else:
        state = initialize_exhaustive_smoke_run_state(
            {"run_id": batch.get("run_id"), "source_case_manifest": dict(batch.get("source_case_manifest") or {}), "batches": [batch]},
            batch_plan_path=batch_plan_path if batch_plan_path.exists() else None,
            run_dir=root,
        )
    batch_id = str(batch.get("batch_id") or "").strip()
    batch_dir = root / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    write_json(batch_dir / "manifest.json", batch)
    case_dir = batch_dir / "cases"
    case_dir.mkdir(parents=True, exist_ok=True)

    normalized_cases = [normalize_exhaustive_smoke_case(item) for item in list(batch.get("cases") or [])]
    allowed = max_cases if max_cases is None else max(0, int(max_cases))
    executed_case_ids: list[str] = []
    resumed_case_ids: list[str] = []
    deferred_case_ids: list[str] = []
    for case in normalized_cases:
        case_id = str(case.get("case_id") or "").strip()
        case_status = dict((state.get("case_statuses") or {}).get(case_id) or {})
        if str(case_status.get("status") or "") == RUN_STATE_COMPLETED:
            resumed_case_ids.append(case_id)
            continue
        if allowed is not None and len(executed_case_ids) >= allowed:
            deferred_case_ids.append(case_id)
            continue
        result = _execute_case(case, executor=executor)
        if result is None:
            deferred_case_ids.append(case_id)
            continue
        result_path = case_dir / f"{slugify(case_id, default='case')}.json"
        write_json(result_path, result)
        executed_case_ids.append(case_id)
        case_statuses = dict(state.get("case_statuses") or {})
        prior_entry = dict(case_statuses.get(case_id) or {})
        case_statuses[case_id] = {
            **prior_entry,
            "batch_id": batch_id,
            "family_id": str(batch.get("family_id") or ""),
            "scope_decision": str(case.get("scope_decision") or ""),
            "execution_policy": str(case.get("execution_policy") or ""),
            "status": RUN_STATE_COMPLETED,
            "outcome": result.get("outcome"),
            "result_path": str(result_path),
            "completed_at": now_iso(),
            "attempt_count": int(prior_entry.get("attempt_count") or 0) + 1,
        }
        state["case_statuses"] = case_statuses
    _refresh_state_counts(state, batch_plan=batch_plan if isinstance(batch_plan, dict) else {"batches": [batch]})
    _update_batch_status(state, batch_manifest=batch, batch_dir=batch_dir)
    state["updated_at"] = now_iso()
    state["resume_markers"] = _resume_markers_from_state(batch_plan if isinstance(batch_plan, dict) and batch_plan else {"batches": [batch]}, case_statuses=dict(state.get("case_statuses") or {}))
    write_json(state_path, state)
    summary = summarize_exhaustive_smoke_run_state(state)
    write_json(root / "summary.json", summary)
    batch_summary = _batch_summary_from_state(state, batch_manifest=batch, batch_dir=batch_dir, executed_case_ids=executed_case_ids, resumed_case_ids=resumed_case_ids, deferred_case_ids=deferred_case_ids)
    write_json(batch_dir / "summary.json", batch_summary)
    return {
        "state": state,
        "summary": summary,
        "batch_summary": batch_summary,
        "executed_case_ids": executed_case_ids,
        "resumed_case_ids": resumed_case_ids,
        "deferred_case_ids": deferred_case_ids,
        "artifact_paths": {
            "run_state_json": str(state_path),
            "summary_json": str(root / "summary.json"),
            "batch_summary_json": str(batch_dir / "summary.json"),
            "batch_case_dir": str(case_dir),
        },
    }


def summarize_exhaustive_smoke_run_state(state: dict[str, Any]) -> dict[str, Any]:
    case_statuses = dict(state.get("case_statuses") or {})
    completed = [dict(item) for item in case_statuses.values() if str(item.get("status") or "") == RUN_STATE_COMPLETED]
    outcome_counts = _count_dict_values(completed, "outcome")
    batch_statuses = dict(state.get("batch_statuses") or {})
    status_counts = _count_dict_values(list(batch_statuses.values()), "status")
    summary = {
        "schema_version": EXHAUSTIVE_SMOKE_RUN_SUMMARY_SCHEMA_VERSION,
        "run_id": str(state.get("run_id") or ""),
        "created_at": str(state.get("created_at") or ""),
        "updated_at": str(state.get("updated_at") or ""),
        "case_count": int(state.get("case_count") or 0),
        "completed_case_count": int(state.get("completed_case_count") or 0),
        "pending_case_count": int(state.get("pending_case_count") or 0),
        "completed_outcome_counts": outcome_counts,
        "batch_status_counts": status_counts,
        "resume_markers": dict(state.get("resume_markers") or {}),
    }
    assert_secret_free_exhaustive_smoke_payload(summary, path="exhaustive_smoke_run_summary")
    return summary


def _execute_case(case: dict[str, Any], *, executor: ExhaustiveSmokeExecutor | None) -> dict[str, Any] | None:
    scope_decision = str(case.get("scope_decision") or "run").strip().lower() or "run"
    execution_policy = str(case.get("execution_policy") or default_execution_policy(scope_decision)).strip().lower()
    if execution_policy == "skip_case":
        return _nonlive_result(
            case,
            lower_level_status="skipped",
            reasons=[_scope_reason_for_case(case) or "Case skipped by scope decision."],
        )
    if execution_policy == "record_unsupported":
        return _nonlive_result(
            case,
            lower_level_status="skipped",
            reasons=[_scope_reason_for_case(case) or "Capability is unsupported for this lane."],
        )
    if executor is None:
        return None
    try:
        payload = dict(executor(case) or {})
    except Exception as exc:  # noqa: BLE001 - durable batch runner records local execution failures.
        payload = {
            "lower_level_status": "fail",
            "reasons": [str(exc) or exc.__class__.__name__],
            "failure_notice": {"summary": str(exc) or exc.__class__.__name__},
            "notes": ["executor_exception"],
        }
    result_payload = {
        "case_id": str(case.get("case_id") or ""),
        "lane_id": str(case.get("lane_id") or ""),
        "lane_group": str(case.get("lane_group") or ""),
        "lane_kind": str(case.get("lane_kind") or ""),
        "provider_id": str(case.get("provider_id") or ""),
        "model_id": str(case.get("model_id") or ""),
        "capability_id": str(case.get("capability_id") or ""),
        "scope_decision": scope_decision,
        "execution_policy": execution_policy,
        "runner_kind": str(case.get("runner_kind") or ""),
        **payload,
    }
    if not str(result_payload.get("outcome") or "").strip():
        result_payload["outcome"] = outcome_from_lower_level_status(
            str(result_payload.get("lower_level_status") or ""),
            scope_decision=scope_decision,
            execution_policy=execution_policy,
        )
    return normalize_exhaustive_smoke_result(result_payload)


def _nonlive_result(case: dict[str, Any], *, lower_level_status: str, reasons: list[str]) -> dict[str, Any]:
    scope_decision = str(case.get("scope_decision") or "run").strip().lower() or "run"
    execution_policy = str(case.get("execution_policy") or default_execution_policy(scope_decision)).strip().lower()
    payload = {
        "case_id": str(case.get("case_id") or ""),
        "lane_id": str(case.get("lane_id") or ""),
        "lane_group": str(case.get("lane_group") or ""),
        "lane_kind": str(case.get("lane_kind") or ""),
        "provider_id": str(case.get("provider_id") or ""),
        "model_id": str(case.get("model_id") or ""),
        "capability_id": str(case.get("capability_id") or ""),
        "scope_decision": scope_decision,
        "execution_policy": execution_policy,
        "runner_kind": str(case.get("runner_kind") or ""),
        "lower_level_status": lower_level_status,
        "outcome": outcome_from_lower_level_status(lower_level_status, scope_decision=scope_decision, execution_policy=execution_policy),
        "reasons": [str(item) for item in reasons if str(item).strip()],
        "notes": ["nonlive_scope_resolution"],
    }
    return normalize_exhaustive_smoke_result(payload)


def _artifact_root_check(root: Path) -> dict[str, Any]:
    (root / "batches").mkdir(parents=True, exist_ok=True)
    status = "pass" if root.exists() and (root / "batches").exists() else "fail"
    return {
        "check_id": "artifact_root_setup",
        "status": status,
        "details": {
            "run_dir": str(root),
            "batches_dir": str(root / "batches"),
            "exists": root.exists(),
        },
    }


def _managed_vault_check(session_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(session_payload, dict) or session_payload.get("error"):
        return {
            "check_id": "managed_vault_session",
            "status": "fail",
            "details": {
                "error": str(session_payload.get("error") or "session unavailable"),
                "error_type": session_payload.get("error_type"),
            },
        }
    mode = str(session_payload.get("mode") or "")
    unlocked = bool(session_payload.get("unlocked"))
    status = "pass" if mode == "managed_user" and unlocked else "warn"
    return {
        "check_id": "managed_vault_session",
        "status": status,
        "details": {
            "mode": mode,
            "username": session_payload.get("username"),
            "unlocked": unlocked,
            "key_count": session_payload.get("key_count"),
            "active_provider_ids": sorted({str(key) for key in dict(session_payload.get("active_key_ids") or {}).keys() if str(key).strip()}),
        },
    }


def _provider_availability_check(
    expected_provider_ids: list[str],
    *,
    session_payload: dict[str, Any],
    profiles_payload: dict[str, Any],
) -> dict[str, Any]:
    active_provider_ids = sorted({str(key) for key in dict(session_payload.get("active_key_ids") or {}).keys() if str(key).strip()})
    profile_provider_ids = sorted(
        {
            str(item.get("provider_id") or "")
            for item in list(profiles_payload.get("profiles") or [])
            if isinstance(item, dict) and str(item.get("provider_id") or "").strip()
        }
    )
    missing_active = sorted(set(expected_provider_ids) - set(active_provider_ids))
    missing_profiles = sorted(set(expected_provider_ids) - set(profile_provider_ids))
    status = "pass" if not missing_active and not missing_profiles else "warn"
    return {
        "check_id": "provider_availability",
        "status": status,
        "details": {
            "expected_provider_ids": expected_provider_ids,
            "active_key_provider_ids": active_provider_ids,
            "profile_provider_ids": profile_provider_ids,
            "missing_active_key_provider_ids": missing_active,
            "missing_profile_provider_ids": missing_profiles,
        },
    }


def _build_preflight_payload(
    *,
    run_dir: Path,
    sidecar_base_url: str | None,
    expected_provider_ids: list[str],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = _count_dict_values(checks, "status")
    return {
        "schema_version": EXHAUSTIVE_SMOKE_PREFLIGHT_SCHEMA_VERSION,
        "created_at": now_iso(),
        "run_dir": str(run_dir),
        "sidecar_base_url": sidecar_base_url,
        "expected_provider_ids": expected_provider_ids,
        "ok": summary.get("fail", 0) == 0,
        "summary": {
            "pass": summary.get("pass", 0),
            "warn": summary.get("warn", 0),
            "fail": summary.get("fail", 0),
        },
        "checks": checks,
    }


def _refresh_state_counts(state: dict[str, Any], *, batch_plan: dict[str, Any]) -> None:
    case_statuses = dict(state.get("case_statuses") or {})
    completed_case_count = sum(1 for item in case_statuses.values() if str((item or {}).get("status") or "") == RUN_STATE_COMPLETED)
    state["completed_case_count"] = completed_case_count
    state["pending_case_count"] = max(0, int(state.get("case_count") or len(case_statuses)) - completed_case_count)
    for batch in list(batch_plan.get("batches") or []):
        batch_id = str(batch.get("batch_id") or "").strip()
        if not batch_id:
            continue
        cases = [normalize_exhaustive_smoke_case(item) for item in list(batch.get("cases") or [])]
        completed = 0
        outcome_counts: dict[str, int] = {}
        for case in cases:
            case_status = dict(case_statuses.get(str(case.get("case_id") or "")) or {})
            if str(case_status.get("status") or "") == RUN_STATE_COMPLETED:
                completed += 1
                outcome = str(case_status.get("outcome") or "")
                if outcome:
                    outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        pending = len(cases) - completed
        batch_statuses = dict(state.get("batch_statuses") or {})
        prior = dict(batch_statuses.get(batch_id) or {})
        status = "completed" if pending == 0 else ("partial" if completed > 0 else "pending")
        batch_statuses[batch_id] = {
            **prior,
            "family_id": str(batch.get("family_id") or ""),
            "step_id": str(batch.get("step_id") or ""),
            "total_cases": len(cases),
            "completed_cases": completed,
            "pending_cases": pending,
            "status": status,
            "outcome_counts": outcome_counts,
        }
        state["batch_statuses"] = batch_statuses


def _update_batch_status(state: dict[str, Any], *, batch_manifest: dict[str, Any], batch_dir: Path) -> None:
    batch_id = str(batch_manifest.get("batch_id") or "").strip()
    batch_statuses = dict(state.get("batch_statuses") or {})
    prior = dict(batch_statuses.get(batch_id) or {})
    prior["last_invoked_at"] = now_iso()
    if str(prior.get("status") or "") == "completed":
        prior["last_completed_at"] = now_iso()
    batch_statuses[batch_id] = prior
    state["batch_statuses"] = batch_statuses
    write_json(batch_dir / "status.json", prior)


def _batch_summary_from_state(
    state: dict[str, Any],
    *,
    batch_manifest: dict[str, Any],
    batch_dir: Path,
    executed_case_ids: list[str],
    resumed_case_ids: list[str],
    deferred_case_ids: list[str],
) -> dict[str, Any]:
    batch_id = str(batch_manifest.get("batch_id") or "")
    batch_status = dict((state.get("batch_statuses") or {}).get(batch_id) or {})
    summary = {
        "schema_version": EXHAUSTIVE_SMOKE_RUN_SUMMARY_SCHEMA_VERSION,
        "run_id": str(state.get("run_id") or ""),
        "batch_id": batch_id,
        "family_id": str(batch_manifest.get("family_id") or ""),
        "family_label": str(batch_manifest.get("family_label") or ""),
        "step_id": str(batch_manifest.get("step_id") or ""),
        "updated_at": str(state.get("updated_at") or now_iso()),
        "batch_status": batch_status,
        "executed_case_ids": list(executed_case_ids),
        "resumed_case_ids": list(resumed_case_ids),
        "deferred_case_ids": list(deferred_case_ids),
        "artifact_paths": {
            "batch_dir": str(batch_dir),
            "manifest_json": str(batch_dir / "manifest.json"),
            "status_json": str(batch_dir / "status.json"),
            "summary_json": str(batch_dir / "summary.json"),
            "case_dir": str(batch_dir / "cases"),
        },
    }
    assert_secret_free_exhaustive_smoke_payload(summary, path=f"exhaustive_smoke_batch_summary:{batch_id}")
    return summary


def _resume_markers_from_state(batch_plan: dict[str, Any], *, case_statuses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for batch in list(batch_plan.get("batches") or []):
        for case in list(batch.get("cases") or []):
            case_id = str(case.get("case_id") or "").strip()
            if str((case_statuses.get(case_id) or {}).get("status") or "") != RUN_STATE_COMPLETED:
                return {
                    "next_batch_id": str(batch.get("batch_id") or ""),
                    "next_case_id": case_id,
                }
    return {"next_batch_id": None, "next_case_id": None}


def _scope_reason_for_case(case: dict[str, Any]) -> str:
    runner_hints = dict(case.get("runner_hints") or {})
    scope_reason = str(runner_hints.get("scope_reason") or "").strip()
    if scope_reason:
        return scope_reason
    for note in list(case.get("notes") or []):
        text = str(note or "").strip()
        if text.startswith("scope_reason:"):
            return text.split(":", 1)[1].strip()
    return ""


def _expected_provider_ids(case_manifest: dict[str, Any]) -> list[str]:
    provider_ids = set()
    for case in list(case_manifest.get("cases") or []):
        if not isinstance(case, dict):
            continue
        execution_policy = str(case.get("execution_policy") or default_execution_policy(str(case.get("scope_decision") or ""))).strip().lower()
        provider_id = str(case.get("provider_id") or "").strip()
        if execution_policy in NONLIVE_EXECUTION_POLICIES or not provider_id:
            continue
        provider_ids.add(provider_id)
    return sorted(provider_ids)


def _count_by_key(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        text = str(item.get(key) or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return counts


def _count_dict_values(items: list[dict[str, Any]] | dict[str, dict[str, Any]], key: str) -> dict[str, int]:
    values = items.values() if isinstance(items, dict) else items
    counts: dict[str, int] = {}
    for item in values:
        text = str((item or {}).get(key) or "").strip()
        if not text:
            continue
        counts[text] = counts.get(text, 0) + 1
    return counts


def _http_get_json(url: str) -> dict[str, Any]:
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(text)
        except Exception:
            body = {"error": text[:1000]}
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
