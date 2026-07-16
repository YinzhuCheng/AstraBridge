from __future__ import annotations

from typing import Any

from .common import now_iso, slugify
from .exhaustive_smoke_contract import (
    EXHAUSTIVE_LANE_GROUPS,
    EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION,
    ExhaustiveSmokeCase,
    assert_secret_free_exhaustive_smoke_payload,
    default_execution_policy,
    default_runner_hints,
)


EXHAUSTIVE_SMOKE_CASE_MANIFEST_SCHEMA_VERSION = "astrabridge-exhaustive-smoke-case-manifest-v1"
_GROUP_TO_MANIFEST_KEY = {
    "general_model": "general_model_lanes",
    "capability": "capability_lanes",
    "compact_handoff": "compact_handoff_lanes",
}
_LANE_GROUP_ORDER = {name: index for index, name in enumerate(EXHAUSTIVE_LANE_GROUPS)}
_REQUEST_PROFILE_BY_LANE_KIND = {
    "image.generate": "capability_image_generate_default",
    "vision.analyze": "capability_vision_analyze_default",
    "speech.transcribe": "capability_speech_transcribe_default",
    "speech.synthesize": "capability_speech_synthesize_default",
    "thread.compact": "compact_thread_default",
    "thread.health_check": "compact_health_check_default",
    "same_task.handoff_target": "same_task_handoff_default",
}


def synthesize_exhaustive_smoke_cases(
    scope_manifest: dict[str, Any],
    *,
    include_lane_groups: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(scope_manifest, dict):
        raise TypeError("Scope manifest must be a dict.")
    requested_groups = [
        str(item).strip()
        for item in (include_lane_groups or EXHAUSTIVE_LANE_GROUPS)
        if str(item).strip()
    ]
    invalid = [item for item in requested_groups if item not in EXHAUSTIVE_LANE_GROUPS]
    if invalid:
        raise ValueError(f"Unsupported lane groups for exhaustive synthesis: {', '.join(invalid)}")

    cases: list[dict[str, Any]] = []
    for lane_group in requested_groups:
        manifest_key = _GROUP_TO_MANIFEST_KEY[lane_group]
        for lane in list(scope_manifest.get(manifest_key) or []):
            if not isinstance(lane, dict):
                continue
            cases.append(_synthesize_case(lane_group, lane))
    return sorted(cases, key=_case_sort_key)


def build_exhaustive_smoke_case_manifest(
    scope_manifest: dict[str, Any],
    *,
    source_manifest_path: str | None = None,
    run_id: str | None = None,
    generated_at: str | None = None,
    include_lane_groups: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    created_at = generated_at or now_iso()
    resolved_run_id = slugify(
        run_id or f"exhaustive-smoke-case-manifest-{created_at}",
        default="exhaustive-smoke-case-manifest",
    )
    cases = synthesize_exhaustive_smoke_cases(
        scope_manifest,
        include_lane_groups=include_lane_groups,
    )
    manifest = {
        "schema_version": EXHAUSTIVE_SMOKE_CASE_MANIFEST_SCHEMA_VERSION,
        "case_schema_version": EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "generated_at": created_at,
        "source_manifest": {
            "schema_version": str(scope_manifest.get("schema_version") or "").strip() or None,
            "run_id": str(scope_manifest.get("run_id") or "").strip() or None,
            "path": str(source_manifest_path or "").strip() or None,
        },
        "scope_policy": dict(scope_manifest.get("scope_policy") or {}),
        "cases": cases,
        "summary": _summary_payload(cases),
    }
    assert_secret_free_exhaustive_smoke_payload(manifest, path="exhaustive_smoke_case_manifest")
    return manifest


def _synthesize_case(lane_group: str, lane: dict[str, Any]) -> dict[str, Any]:
    lane_kind = str(lane.get("lane_kind") or "").strip()
    provider_id = str(lane.get("provider_id") or "").strip()
    model_id = str(lane.get("model_id") or "").strip()
    if not lane_kind or not provider_id or not model_id:
        raise ValueError("Lane payload must include lane_kind, provider_id, and model_id.")
    native_model = str(lane.get("native_model") or "").strip() or _native_model_from_model_id(model_id)
    scope_decision = str(lane.get("classification") or "run").strip().lower() or "run"
    capability_id = lane_kind if lane_group == "capability" else ""
    candidate = dict(lane.get("candidate_snapshot") or {})
    metadata_snapshot = dict(lane.get("metadata_snapshot") or {})
    adapter_id = str(lane.get("adapter_id") or candidate.get("adapter_id") or "").strip()
    execution_policy = default_execution_policy(scope_decision)
    route_expectation = {
        "provider_id": provider_id,
        "model": native_model,
    }
    if adapter_id:
        route_expectation["adapter_id"] = adapter_id
    request_overrides = _request_overrides_for_lane(
        lane_group=lane_group,
        lane_kind=lane_kind,
        provider_id=provider_id,
        native_model=native_model,
        capability_id=capability_id,
    )
    runner_hints = _runner_hints_for_lane(
        lane_group=lane_group,
        lane_kind=lane_kind,
        scope_decision=scope_decision,
        execution_policy=execution_policy,
        lane=lane,
        metadata_snapshot=metadata_snapshot,
    )
    notes = _notes_for_lane(lane=lane, metadata_snapshot=metadata_snapshot)
    item = ExhaustiveSmokeCase.from_any(
        {
            "case_id": _case_id_for_lane(lane_group, lane),
            "lane_id": str(lane.get("lane_id") or "").strip(),
            "lane_group": lane_group,
            "lane_kind": lane_kind,
            "provider_id": provider_id,
            "model_id": model_id,
            "native_model": native_model,
            "capability_id": capability_id,
            "scope_decision": scope_decision,
            "execution_policy": execution_policy,
            "fixture_id": _fixture_id_for_lane(
                lane_group=lane_group,
                lane_kind=lane_kind,
                scope_decision=scope_decision,
                metadata_snapshot=metadata_snapshot,
            ),
            "request_profile": _request_profile_for_lane(
                lane_group=lane_group,
                lane_kind=lane_kind,
                scope_decision=scope_decision,
                metadata_snapshot=metadata_snapshot,
            ),
            "request_overrides": request_overrides,
            "route_expectation": route_expectation,
            "runner_hints": runner_hints,
            "evidence_refs": list(lane.get("evidence_refs") or []),
            "notes": notes,
        }
    )
    return item.to_dict()


def _case_id_for_lane(lane_group: str, lane: dict[str, Any]) -> str:
    lane_id = str(lane.get("lane_id") or "").strip()
    classification = str(lane.get("classification") or "run").strip().lower() or "run"
    raw = f"{lane_group}-{lane_id}-{classification}"
    return slugify(raw, default="exhaustive-case")


def _request_profile_for_lane(
    *,
    lane_group: str,
    lane_kind: str,
    scope_decision: str,
    metadata_snapshot: dict[str, Any],
) -> str:
    if lane_group != "general_model":
        return _REQUEST_PROFILE_BY_LANE_KIND.get(lane_kind, "default")
    structured_tool_surface = _has_structured_tool_surface(metadata_snapshot)
    if lane_kind == "chat.text_health":
        return "general_text_health_exact_short_answer"
    if lane_kind == "agent.command_execution":
        if scope_decision == "reduced-authority":
            return "general_command_execution_reduced_authority_probe"
        if structured_tool_surface:
            return "general_command_execution_read_only_shell_once"
        return "general_command_execution_authority_probe"
    if lane_kind == "agent.edit_apply_patch":
        if scope_decision == "reduced-authority":
            return "general_edit_apply_patch_reduced_authority_probe"
        if structured_tool_surface:
            return "general_edit_apply_patch_scratch_patch_probe"
        return "general_edit_apply_patch_authority_probe"
    return "default"


def _fixture_id_for_lane(
    *,
    lane_group: str,
    lane_kind: str,
    scope_decision: str,
    metadata_snapshot: dict[str, Any],
) -> str:
    if lane_group != "general_model":
        return "default"
    structured_tool_surface = _has_structured_tool_surface(metadata_snapshot)
    if lane_kind == "chat.text_health":
        return "exact_short_text"
    if lane_kind == "agent.command_execution":
        if scope_decision == "reduced-authority":
            return "read_only_shell_reduced_authority_probe"
        if structured_tool_surface:
            return "read_only_shell_once"
        return "read_only_shell_authority_probe"
    if lane_kind == "agent.edit_apply_patch":
        if scope_decision == "reduced-authority":
            return "scratch_patch_reduced_authority_probe"
        if structured_tool_surface:
            return "scratch_patch_apply_probe"
        return "scratch_patch_authority_probe"
    return "default"


def _request_overrides_for_lane(
    *,
    lane_group: str,
    lane_kind: str,
    provider_id: str,
    native_model: str,
    capability_id: str,
) -> dict[str, Any]:
    request_overrides = {
        "provider_id": provider_id,
        "model": native_model,
    }
    if capability_id:
        request_overrides["capability_id"] = capability_id
    if lane_group != "general_model":
        return request_overrides
    if lane_kind == "chat.text_health":
        request_overrides["stream"] = False
        return request_overrides
    if lane_kind in {"agent.command_execution", "agent.edit_apply_patch"}:
        request_overrides.update(
            {
                "effort": "low",
                "permission_mode": "full",
                "context_mode": "no_context",
                "include_full_state": True,
            }
        )
    return request_overrides


def _runner_hints_for_lane(
    *,
    lane_group: str,
    lane_kind: str,
    scope_decision: str,
    execution_policy: str,
    lane: dict[str, Any],
    metadata_snapshot: dict[str, Any],
) -> dict[str, Any]:
    runner_hints = default_runner_hints(lane_group, lane_kind, execution_policy)
    runner_hints.update(
        {
            "explicit_provider_model": True,
            "scope_reason": str(lane.get("reason") or "").strip(),
            "lane_origin": str(lane.get("lane_origin") or "catalog_lane").strip(),
        }
    )
    if lane_group != "general_model":
        return runner_hints
    authority_tier = str(metadata_snapshot.get("authority_tier") or "").strip()
    structured_tool_surface = _has_structured_tool_surface(metadata_snapshot)
    runner_hints.update(
        {
            "authority_tier": authority_tier or None,
            "authority_reason": str(metadata_snapshot.get("authority_reason") or "").strip() or None,
            "command_execution_status": str(metadata_snapshot.get("command_execution_status") or "").strip() or None,
            "parallel_tool_call_status": str(metadata_snapshot.get("parallel_tool_call_status") or "").strip() or None,
            "supports_tool_calls": bool(metadata_snapshot.get("tool_support", False)),
            "supports_mcp_tools": bool(metadata_snapshot.get("mcp_support", False)),
            "structured_tool_surface": structured_tool_surface,
        }
    )
    if lane_kind == "chat.text_health":
        runner_hints.update(
            {
                "validation_surface": "provider_key_test",
                "response_contract": "single_short_text_answer",
                "expected_signal": "visible_text",
            }
        )
        return runner_hints
    if lane_kind == "agent.command_execution":
        runner_hints.update(
            {
                "validation_surface": "runtime_turn",
                "permission_mode": "full",
                "context_mode": "no_context",
                "include_full_state": True,
                "prompt_contract": "run_one_read_only_shell_then_return_json",
                "shell_command": "git rev-parse --show-toplevel",
                "final_response_format": "json_only",
                "mutation_scope": "read_only",
            }
        )
        runner_hints.update(_authority_expectation_hints(lane_kind=lane_kind, scope_decision=scope_decision, authority_tier=authority_tier, structured_tool_surface=structured_tool_surface))
        return runner_hints
    if lane_kind == "agent.edit_apply_patch":
        runner_hints.update(
            {
                "validation_surface": "runtime_turn",
                "permission_mode": "full",
                "context_mode": "no_context",
                "include_full_state": True,
                "prompt_contract": "apply_patch_to_scratch_file_then_return_json",
                "final_response_format": "json_only",
                "mutation_scope": "scratch_only",
                "target_file_kind": "scratch_file",
                "preferred_edit_operation": "apply_patch" if structured_tool_surface else "propose_only_or_runtime_bridge",
            }
        )
        runner_hints.update(_authority_expectation_hints(lane_kind=lane_kind, scope_decision=scope_decision, authority_tier=authority_tier, structured_tool_surface=structured_tool_surface))
    return runner_hints


def _authority_expectation_hints(
    *,
    lane_kind: str,
    scope_decision: str,
    authority_tier: str,
    structured_tool_surface: bool,
) -> dict[str, Any]:
    if lane_kind == "agent.command_execution":
        if scope_decision == "reduced-authority":
            return {
                "expected_authority_outcome": "reduced_authority_confirmation",
                "success_signal": "command_execution_or_explicit_downgrade",
            }
        if structured_tool_surface or authority_tier in {"A", "B"}:
            return {
                "expected_authority_outcome": "command_execution_required",
                "success_signal": "command_execution_required",
            }
        return {
            "expected_authority_outcome": "authority_probe",
            "success_signal": "command_execution_or_explicit_downgrade",
            "reclassification_allowed": True,
        }
    if lane_kind == "agent.edit_apply_patch":
        if scope_decision == "reduced-authority":
            return {
                "expected_authority_outcome": "reduced_authority_confirmation",
                "success_signal": "apply_patch_or_propose_only_downgrade",
            }
        if structured_tool_surface or authority_tier in {"A", "B"}:
            return {
                "expected_authority_outcome": "apply_patch_required",
                "success_signal": "apply_patch_required",
            }
        return {
            "expected_authority_outcome": "authority_probe",
            "success_signal": "apply_patch_or_propose_only_downgrade",
            "reclassification_allowed": True,
        }
    return {}


def _notes_for_lane(*, lane: dict[str, Any], metadata_snapshot: dict[str, Any]) -> list[str]:
    notes = []
    reason = str(lane.get("reason") or "").strip()
    if reason:
        notes.append(f"scope_reason: {reason}")
    lane_origin = str(lane.get("lane_origin") or "").strip()
    if lane_origin:
        notes.append(f"lane_origin: {lane_origin}")
    if metadata_snapshot:
        _append_metadata_note(notes, "authority_tier", metadata_snapshot.get("authority_tier"))
        _append_metadata_note(notes, "command_execution_status", metadata_snapshot.get("command_execution_status"))
        _append_metadata_note(notes, "parallel_tool_call_status", metadata_snapshot.get("parallel_tool_call_status"))
        _append_metadata_note(notes, "tool_support", _bool_text(metadata_snapshot.get("tool_support")))
        _append_metadata_note(notes, "mcp_support", _bool_text(metadata_snapshot.get("mcp_support")))
    return notes


def _append_metadata_note(notes: list[str], key: str, value: Any) -> None:
    text = str(value or "").strip()
    if text:
        notes.append(f"{key}: {text}")


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def _has_structured_tool_surface(metadata_snapshot: dict[str, Any]) -> bool:
    return bool(metadata_snapshot.get("tool_support", False) or metadata_snapshot.get("mcp_support", False))


def _native_model_from_model_id(model_id: str) -> str:
    text = str(model_id or "").strip()
    if "/" in text:
        return text.split("/", 1)[1]
    return text


def _case_sort_key(case: dict[str, Any]) -> tuple[int, str, str, str, str]:
    lane_group = str(case.get("lane_group") or "")
    return (
        _LANE_GROUP_ORDER.get(lane_group, 99),
        str(case.get("provider_id") or ""),
        str(case.get("model_id") or ""),
        str(case.get("lane_kind") or ""),
        str(case.get("case_id") or ""),
    )


def _summary_payload(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_scope_decision: dict[str, int] = {}
    by_lane_group: dict[str, dict[str, int]] = {}
    by_provider: dict[str, dict[str, int]] = {}
    for case in cases:
        scope_decision = str(case.get("scope_decision") or "run")
        lane_group = str(case.get("lane_group") or "")
        provider_id = str(case.get("provider_id") or "")
        by_scope_decision[scope_decision] = by_scope_decision.get(scope_decision, 0) + 1
        by_lane_group.setdefault(lane_group, {})
        by_lane_group[lane_group][scope_decision] = by_lane_group[lane_group].get(scope_decision, 0) + 1
        by_provider.setdefault(provider_id, {})
        by_provider[provider_id][scope_decision] = by_provider[provider_id].get(scope_decision, 0) + 1
    return {
        "case_count": len(cases),
        "scope_decision_counts": by_scope_decision,
        "lane_group_scope_counts": by_lane_group,
        "provider_scope_counts": by_provider,
        "provider_ids": sorted({str(case.get("provider_id") or "") for case in cases if str(case.get("provider_id") or "").strip()}),
    }
