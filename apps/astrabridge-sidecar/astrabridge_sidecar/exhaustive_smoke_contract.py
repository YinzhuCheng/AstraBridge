from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal


EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION = "astrabridge-exhaustive-smoke-case-v1"
EXHAUSTIVE_SMOKE_RESULT_SCHEMA_VERSION = "astrabridge-exhaustive-smoke-result-v1"
EXHAUSTIVE_SCOPE_DECISIONS = ("run", "skip", "unsupported", "reduced-authority")
EXHAUSTIVE_EXECUTION_POLICIES = ("run_live", "skip_case", "record_unsupported", "confirm_reduced_authority")
EXHAUSTIVE_RESULT_OUTCOMES = ("pass", "partial", "fail", "unsupported", "reduced-authority", "skipped")
EXHAUSTIVE_LANE_GROUPS = ("general_model", "capability", "compact_handoff")
EXHAUSTIVE_RUNNER_KINDS = ("provider_compatibility_smoke", "task_runtime_validation", "compact_validation")
EXHAUSTIVE_FIXTURE_KINDS = (
    "text_health",
    "command_execution",
    "edit_apply_patch",
    "vision_fixture",
    "audio_fixture",
    "tts_text",
    "image_prompt",
    "long_context_compact",
    "health_check",
    "handoff_probe",
)
ARTIFACT_OBSERVATION_STATUSES = ("pass", "missing", "invalid", "not_applicable")
LOWER_LEVEL_STATUS_TO_OUTCOME = {
    "pass": "pass",
    "partial": "partial",
    "fail": "fail",
    "skipped": "skipped",
    "blocked": "fail",
    "provider_not_run": "fail",
}
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
_DESKTOP_KEY_PATH_RE = re.compile(r"(?i)(^|[\\/])key\.txt$")


LaneGroup = Literal["general_model", "capability", "compact_handoff"]
ScopeDecision = Literal["run", "skip", "unsupported", "reduced-authority"]
ExecutionPolicy = Literal["run_live", "skip_case", "record_unsupported", "confirm_reduced_authority"]
ResultOutcome = Literal["pass", "partial", "fail", "unsupported", "reduced-authority", "skipped"]
RunnerKind = Literal["provider_compatibility_smoke", "task_runtime_validation", "compact_validation"]
FixtureKind = Literal[
    "text_health",
    "command_execution",
    "edit_apply_patch",
    "vision_fixture",
    "audio_fixture",
    "tts_text",
    "image_prompt",
    "long_context_compact",
    "health_check",
    "handoff_probe",
]
ArtifactObservationStatus = Literal["pass", "missing", "invalid", "not_applicable"]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_list(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def default_execution_policy(scope_decision: ScopeDecision | str) -> str:
    text = _clean_text(scope_decision).lower()
    if text == "skip":
        return "skip_case"
    if text == "unsupported":
        return "record_unsupported"
    if text == "reduced-authority":
        return "confirm_reduced_authority"
    return "run_live"


def default_runner_kind(lane_group: LaneGroup | str, lane_kind: str) -> str:
    group = _clean_text(lane_group).lower()
    kind = _clean_text(lane_kind).lower()
    if group == "capability":
        return "provider_compatibility_smoke"
    if kind in {"thread.compact", "thread.health_check"}:
        return "compact_validation"
    return "task_runtime_validation"


def default_fixture_kind(lane_group: LaneGroup | str, lane_kind: str) -> str:
    group = _clean_text(lane_group).lower()
    kind = _clean_text(lane_kind).lower()
    if group == "capability":
        if kind == "vision.analyze":
            return "vision_fixture"
        if kind == "speech.transcribe":
            return "audio_fixture"
        if kind == "speech.synthesize":
            return "tts_text"
        return "image_prompt"
    if kind == "agent.command_execution":
        return "command_execution"
    if kind == "agent.edit_apply_patch":
        return "edit_apply_patch"
    if kind == "thread.compact":
        return "long_context_compact"
    if kind == "thread.health_check":
        return "health_check"
    if kind == "same_task.handoff_target":
        return "handoff_probe"
    return "text_health"


@dataclass(frozen=True)
class ExhaustiveSmokeArtifactExpectation:
    artifact_key: str
    artifact_type: str
    required: bool = True
    evidence_origin: str = ""
    validation_rule: str = ""
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "ExhaustiveSmokeArtifactExpectation":
        if isinstance(payload, ExhaustiveSmokeArtifactExpectation):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Artifact expectation payload must be a dict.")
        artifact_key = _clean_text(payload.get("artifact_key"))
        artifact_type = _clean_text(payload.get("artifact_type"))
        if not artifact_key or not artifact_type:
            raise ValueError("Artifact expectation requires artifact_key and artifact_type.")
        item = cls(
            artifact_key=artifact_key,
            artifact_type=artifact_type,
            required=bool(payload.get("required", True)),
            evidence_origin=_clean_text(payload.get("evidence_origin")),
            validation_rule=_clean_text(payload.get("validation_rule")),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )
        assert_secret_free_exhaustive_smoke_payload(item.to_dict(), path=f"artifact_expectation:{artifact_key}")
        return item

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "artifact_key": self.artifact_key,
            "artifact_type": self.artifact_type,
            "required": self.required,
            "evidence_origin": self.evidence_origin,
            "validation_rule": self.validation_rule,
        }
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class ExhaustiveSmokeArtifactObservation:
    artifact_key: str
    status: ArtifactObservationStatus
    observed: bool
    artifact_type: str = ""
    path: str = ""
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "ExhaustiveSmokeArtifactObservation":
        if isinstance(payload, ExhaustiveSmokeArtifactObservation):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Artifact observation payload must be a dict.")
        artifact_key = _clean_text(payload.get("artifact_key"))
        status = _clean_text(payload.get("status")).lower()
        if not artifact_key or status not in ARTIFACT_OBSERVATION_STATUSES:
            raise ValueError("Artifact observation requires a valid artifact_key and status.")
        item = cls(
            artifact_key=artifact_key,
            status=status,  # type: ignore[arg-type]
            observed=bool(payload.get("observed", status == "pass")),
            artifact_type=_clean_text(payload.get("artifact_type")),
            path=_clean_text(payload.get("path")),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )
        assert_secret_free_exhaustive_smoke_payload(item.to_dict(), path=f"artifact_observation:{artifact_key}")
        return item

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "artifact_key": self.artifact_key,
            "status": self.status,
            "observed": self.observed,
            "artifact_type": self.artifact_type,
            "path": self.path,
        }
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class ExhaustiveSmokeCase:
    case_id: str
    lane_id: str
    lane_group: LaneGroup
    lane_kind: str
    provider_id: str
    model_id: str
    native_model: str = ""
    capability_id: str = ""
    scope_decision: ScopeDecision = "run"
    execution_policy: ExecutionPolicy = "run_live"
    runner_kind: RunnerKind = "task_runtime_validation"
    fixture_kind: FixtureKind = "text_health"
    fixture_id: str = "default"
    request_profile: str = "default"
    request_overrides: dict[str, Any] = field(default_factory=dict)
    route_expectation: dict[str, Any] = field(default_factory=dict)
    runner_hints: dict[str, Any] = field(default_factory=dict)
    artifact_expectations: tuple[ExhaustiveSmokeArtifactExpectation, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    schema_version: str = EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION

    @classmethod
    def from_any(cls, payload: Any) -> "ExhaustiveSmokeCase":
        if isinstance(payload, ExhaustiveSmokeCase):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Exhaustive smoke case payload must be a dict.")
        case_id = _clean_text(payload.get("case_id"))
        lane_id = _clean_text(payload.get("lane_id"))
        lane_group = _clean_text(payload.get("lane_group")).lower()
        lane_kind = _clean_text(payload.get("lane_kind"))
        provider_id = _clean_text(payload.get("provider_id"))
        model_id = _clean_text(payload.get("model_id"))
        if not case_id or not lane_id or lane_group not in EXHAUSTIVE_LANE_GROUPS or not lane_kind or not provider_id or not model_id:
            raise ValueError("Exhaustive smoke case requires case_id, lane_id, lane_group, lane_kind, provider_id, and model_id.")
        scope_decision = _clean_text(payload.get("scope_decision") or "run").lower()
        if scope_decision not in EXHAUSTIVE_SCOPE_DECISIONS:
            raise ValueError(f"Unsupported scope_decision: {scope_decision or '<missing>'}")
        execution_policy = _clean_text(payload.get("execution_policy") or default_execution_policy(scope_decision)).lower()
        if execution_policy not in EXHAUSTIVE_EXECUTION_POLICIES:
            raise ValueError(f"Unsupported execution_policy: {execution_policy or '<missing>'}")
        runner_kind = _clean_text(payload.get("runner_kind") or default_runner_kind(lane_group, lane_kind)).lower()
        if runner_kind not in EXHAUSTIVE_RUNNER_KINDS:
            raise ValueError(f"Unsupported runner_kind: {runner_kind or '<missing>'}")
        fixture_kind = _clean_text(payload.get("fixture_kind") or default_fixture_kind(lane_group, lane_kind)).lower()
        if fixture_kind not in EXHAUSTIVE_FIXTURE_KINDS:
            raise ValueError(f"Unsupported fixture_kind: {fixture_kind or '<missing>'}")
        capability_id = _clean_text(payload.get("capability_id"))
        if lane_group == "capability" and not capability_id:
            raise ValueError("Capability cases require capability_id.")
        route_expectation = dict(payload.get("route_expectation") or {})
        runner_hints = dict(payload.get("runner_hints") or default_runner_hints(lane_group, lane_kind, execution_policy))
        request_overrides = dict(payload.get("request_overrides") or {})
        artifact_expectations = tuple(
            ExhaustiveSmokeArtifactExpectation.from_any(item)
            for item in list(payload.get("artifact_expectations") or default_artifact_expectations(lane_group, lane_kind))
        )
        item = cls(
            case_id=case_id,
            lane_id=lane_id,
            lane_group=lane_group,  # type: ignore[arg-type]
            lane_kind=lane_kind,
            provider_id=provider_id,
            model_id=model_id,
            native_model=_clean_text(payload.get("native_model")),
            capability_id=capability_id,
            scope_decision=scope_decision,  # type: ignore[arg-type]
            execution_policy=execution_policy,  # type: ignore[arg-type]
            runner_kind=runner_kind,  # type: ignore[arg-type]
            fixture_kind=fixture_kind,  # type: ignore[arg-type]
            fixture_id=_clean_text(payload.get("fixture_id") or "default"),
            request_profile=_clean_text(payload.get("request_profile") or "default"),
            request_overrides=request_overrides,
            route_expectation=route_expectation,
            runner_hints=runner_hints,
            artifact_expectations=artifact_expectations,
            evidence_refs=tuple(_clean_string_list(payload.get("evidence_refs"))),
            notes=tuple(_clean_string_list(payload.get("notes"))),
            schema_version=_clean_text(payload.get("schema_version") or EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION),
        )
        _validate_case_coherence(item)
        assert_secret_free_exhaustive_smoke_case(item)
        return item

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "lane_id": self.lane_id,
            "lane_group": self.lane_group,
            "lane_kind": self.lane_kind,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "native_model": self.native_model,
            "capability_id": self.capability_id,
            "scope_decision": self.scope_decision,
            "execution_policy": self.execution_policy,
            "runner_kind": self.runner_kind,
            "fixture_kind": self.fixture_kind,
            "fixture_id": self.fixture_id,
            "request_profile": self.request_profile,
            "request_overrides": dict(self.request_overrides),
            "route_expectation": dict(self.route_expectation),
            "runner_hints": dict(self.runner_hints),
            "artifact_expectations": [item.to_dict() for item in self.artifact_expectations],
            "evidence_refs": list(self.evidence_refs),
            "notes": list(self.notes),
        }
        return payload


@dataclass(frozen=True)
class ExhaustiveSmokeResult:
    case_id: str
    lane_id: str
    lane_group: LaneGroup
    lane_kind: str
    provider_id: str
    model_id: str
    capability_id: str = ""
    scope_decision: ScopeDecision = "run"
    execution_policy: ExecutionPolicy = "run_live"
    runner_kind: RunnerKind = "task_runtime_validation"
    outcome: ResultOutcome = "fail"
    lower_level_status: str = ""
    route_observed: dict[str, Any] = field(default_factory=dict)
    usage_signal: dict[str, Any] = field(default_factory=dict)
    artifact_observations: tuple[ExhaustiveSmokeArtifactObservation, ...] = ()
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    failure_notice: dict[str, Any] = field(default_factory=dict)
    evidence_paths: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    case_schema_version: str = EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION
    schema_version: str = EXHAUSTIVE_SMOKE_RESULT_SCHEMA_VERSION

    @classmethod
    def from_any(cls, payload: Any) -> "ExhaustiveSmokeResult":
        if isinstance(payload, ExhaustiveSmokeResult):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Exhaustive smoke result payload must be a dict.")
        case_id = _clean_text(payload.get("case_id"))
        lane_id = _clean_text(payload.get("lane_id"))
        lane_group = _clean_text(payload.get("lane_group")).lower()
        lane_kind = _clean_text(payload.get("lane_kind"))
        provider_id = _clean_text(payload.get("provider_id"))
        model_id = _clean_text(payload.get("model_id"))
        if not case_id or not lane_id or lane_group not in EXHAUSTIVE_LANE_GROUPS or not lane_kind or not provider_id or not model_id:
            raise ValueError("Exhaustive smoke result requires case_id, lane_id, lane_group, lane_kind, provider_id, and model_id.")
        scope_decision = _clean_text(payload.get("scope_decision") or "run").lower()
        execution_policy = _clean_text(payload.get("execution_policy") or default_execution_policy(scope_decision)).lower()
        runner_kind = _clean_text(payload.get("runner_kind") or default_runner_kind(lane_group, lane_kind)).lower()
        lower_level_status = _clean_text(payload.get("lower_level_status")).lower()
        outcome = _clean_text(
            payload.get("outcome")
            or outcome_from_lower_level_status(
                lower_level_status,
                scope_decision=scope_decision,
                execution_policy=execution_policy,
            )
        ).lower()
        if scope_decision not in EXHAUSTIVE_SCOPE_DECISIONS:
            raise ValueError(f"Unsupported scope_decision: {scope_decision or '<missing>'}")
        if execution_policy not in EXHAUSTIVE_EXECUTION_POLICIES:
            raise ValueError(f"Unsupported execution_policy: {execution_policy or '<missing>'}")
        if runner_kind not in EXHAUSTIVE_RUNNER_KINDS:
            raise ValueError(f"Unsupported runner_kind: {runner_kind or '<missing>'}")
        if outcome not in EXHAUSTIVE_RESULT_OUTCOMES:
            raise ValueError(f"Unsupported outcome: {outcome or '<missing>'}")
        item = cls(
            case_id=case_id,
            lane_id=lane_id,
            lane_group=lane_group,  # type: ignore[arg-type]
            lane_kind=lane_kind,
            provider_id=provider_id,
            model_id=model_id,
            capability_id=_clean_text(payload.get("capability_id")),
            scope_decision=scope_decision,  # type: ignore[arg-type]
            execution_policy=execution_policy,  # type: ignore[arg-type]
            runner_kind=runner_kind,  # type: ignore[arg-type]
            outcome=outcome,  # type: ignore[arg-type]
            lower_level_status=lower_level_status,
            route_observed=dict(payload.get("route_observed") or {}),
            usage_signal=dict(payload.get("usage_signal") or {}),
            artifact_observations=tuple(
                ExhaustiveSmokeArtifactObservation.from_any(item)
                for item in list(payload.get("artifact_observations") or [])
            ),
            reasons=tuple(_clean_string_list(payload.get("reasons"))),
            warnings=tuple(_clean_string_list(payload.get("warnings"))),
            failure_notice=dict(payload.get("failure_notice") or {}),
            evidence_paths=tuple(_clean_string_list(payload.get("evidence_paths"))),
            notes=tuple(_clean_string_list(payload.get("notes"))),
            case_schema_version=_clean_text(payload.get("case_schema_version") or EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION),
            schema_version=_clean_text(payload.get("schema_version") or EXHAUSTIVE_SMOKE_RESULT_SCHEMA_VERSION),
        )
        _validate_result_coherence(item)
        assert_secret_free_exhaustive_smoke_result(item)
        return item

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "case_schema_version": self.case_schema_version,
            "case_id": self.case_id,
            "lane_id": self.lane_id,
            "lane_group": self.lane_group,
            "lane_kind": self.lane_kind,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "capability_id": self.capability_id,
            "scope_decision": self.scope_decision,
            "execution_policy": self.execution_policy,
            "runner_kind": self.runner_kind,
            "outcome": self.outcome,
            "lower_level_status": self.lower_level_status,
            "route_observed": dict(self.route_observed),
            "usage_signal": dict(self.usage_signal),
            "artifact_observations": [item.to_dict() for item in self.artifact_observations],
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "failure_notice": dict(self.failure_notice),
            "evidence_paths": list(self.evidence_paths),
            "notes": list(self.notes),
        }
        return payload


def default_runner_hints(lane_group: LaneGroup | str, lane_kind: str, execution_policy: ExecutionPolicy | str) -> dict[str, Any]:
    group = _clean_text(lane_group).lower()
    kind = _clean_text(lane_kind).lower()
    policy = _clean_text(execution_policy).lower()
    if policy == "skip_case":
        return {"allow_provider": False, "mode": "skip"}
    if policy == "record_unsupported":
        return {"allow_provider": False, "mode": "record"}
    if group == "capability":
        return {"allow_provider": True, "mode": "provider"}
    if kind in {"thread.compact", "thread.health_check"}:
        return {"allow_provider": True, "mode": "provider", "same_task": True}
    return {"allow_provider": True, "mode": "provider"}


def default_artifact_expectations(lane_group: LaneGroup | str, lane_kind: str) -> list[dict[str, Any]]:
    kind = _clean_text(lane_kind).lower()
    base = [
        {
            "artifact_key": "case_summary",
            "artifact_type": "result_record",
            "required": True,
            "evidence_origin": "case_result",
            "validation_rule": "summary_present",
        }
    ]
    if kind == "chat.text_health":
        base.append(
            {
                "artifact_key": "visible_text_signal",
                "artifact_type": "semantic_signal",
                "required": True,
                "evidence_origin": "sanitized_response",
                "validation_rule": "non_empty_visible_text",
            }
        )
        return base
    if kind == "agent.command_execution":
        base.append(
            {
                "artifact_key": "command_execution_signal",
                "artifact_type": "runtime_signal",
                "required": True,
                "evidence_origin": "runtime_trace",
                "validation_rule": "command_execution_or_explicit_downgrade",
            }
        )
        return base
    if kind == "agent.edit_apply_patch":
        base.append(
            {
                "artifact_key": "edit_strategy_signal",
                "artifact_type": "runtime_signal",
                "required": True,
                "evidence_origin": "runtime_trace",
                "validation_rule": "apply_patch_or_propose_only_downgrade",
            }
        )
        return base
    if kind == "vision.analyze":
        base.append(
            {
                "artifact_key": "visible_text_signal",
                "artifact_type": "semantic_signal",
                "required": True,
                "evidence_origin": "sanitized_response",
                "validation_rule": "non_empty_visible_text",
            }
        )
        return base
    if kind == "speech.transcribe":
        base.append(
            {
                "artifact_key": "transcript_signal",
                "artifact_type": "semantic_signal",
                "required": True,
                "evidence_origin": "sanitized_response",
                "validation_rule": "non_empty_transcript",
            }
        )
        return base
    if kind == "speech.synthesize":
        base.extend(
            [
                {
                    "artifact_key": "audio_artifact",
                    "artifact_type": "audio_file",
                    "required": True,
                    "evidence_origin": "artifact_refs",
                    "validation_rule": "persisted_audio_artifact",
                },
                {
                    "artifact_key": "transcript_sidecar",
                    "artifact_type": "text_file",
                    "required": False,
                    "evidence_origin": "artifact_refs",
                    "validation_rule": "transcript_sidecar_when_available",
                },
            ]
        )
        return base
    if kind == "image.generate":
        base.extend(
            [
                {
                    "artifact_key": "image_artifact",
                    "artifact_type": "image_file",
                    "required": True,
                    "evidence_origin": "artifact_refs",
                    "validation_rule": "persisted_local_image_artifact",
                },
                {
                    "artifact_key": "asset_manifest",
                    "artifact_type": "manifest",
                    "required": True,
                    "evidence_origin": "artifact_refs",
                    "validation_rule": "asset_manifest_present",
                },
            ]
        )
        return base
    if kind == "thread.compact":
        base.append(
            {
                "artifact_key": "compact_summary_signal",
                "artifact_type": "runtime_signal",
                "required": True,
                "evidence_origin": "runtime_trace",
                "validation_rule": "compact_summary_or_failure_notice",
            }
        )
        return base
    if kind == "thread.health_check":
        base.append(
            {
                "artifact_key": "health_check_signal",
                "artifact_type": "runtime_signal",
                "required": True,
                "evidence_origin": "runtime_trace",
                "validation_rule": "health_check_result_present",
            }
        )
        return base
    if kind == "same_task.handoff_target":
        base.append(
            {
                "artifact_key": "handoff_signal",
                "artifact_type": "runtime_signal",
                "required": True,
                "evidence_origin": "runtime_trace",
                "validation_rule": "handoff_completion_or_explicit_downgrade",
            }
        )
        return base
    return base


def outcome_from_lower_level_status(
    lower_level_status: str | None,
    *,
    scope_decision: ScopeDecision | str = "run",
    execution_policy: ExecutionPolicy | str | None = None,
) -> str:
    scope = _clean_text(scope_decision).lower() or "run"
    policy = _clean_text(execution_policy or default_execution_policy(scope)).lower()
    if policy == "skip_case":
        return "skipped"
    if policy == "record_unsupported":
        return "unsupported"
    if policy == "confirm_reduced_authority":
        normalized = LOWER_LEVEL_STATUS_TO_OUTCOME.get(_clean_text(lower_level_status).lower(), "fail")
        return "pass" if normalized == "pass" else "reduced-authority"
    return LOWER_LEVEL_STATUS_TO_OUTCOME.get(_clean_text(lower_level_status).lower(), "fail")


def normalize_exhaustive_smoke_case(payload: Any) -> dict[str, Any]:
    return ExhaustiveSmokeCase.from_any(payload).to_dict()


def normalize_exhaustive_smoke_result(payload: Any) -> dict[str, Any]:
    return ExhaustiveSmokeResult.from_any(payload).to_dict()


def assert_secret_free_exhaustive_smoke_case(case: ExhaustiveSmokeCase | dict[str, Any]) -> None:
    payload = case.to_dict() if isinstance(case, ExhaustiveSmokeCase) else dict(case)
    if _clean_text(payload.get("schema_version")) != EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION:
        raise ValueError("Unexpected exhaustive smoke case schema version.")
    assert_secret_free_exhaustive_smoke_payload(payload, path="exhaustive_smoke_case")


def assert_secret_free_exhaustive_smoke_result(result: ExhaustiveSmokeResult | dict[str, Any]) -> None:
    payload = result.to_dict() if isinstance(result, ExhaustiveSmokeResult) else dict(result)
    if _clean_text(payload.get("schema_version")) != EXHAUSTIVE_SMOKE_RESULT_SCHEMA_VERSION:
        raise ValueError("Unexpected exhaustive smoke result schema version.")
    assert_secret_free_exhaustive_smoke_payload(payload, path="exhaustive_smoke_result")


def assert_secret_free_exhaustive_smoke_payload(payload: Any, *, path: str) -> None:
    _reject_secret_like(payload, path=path)


def _validate_case_coherence(case: ExhaustiveSmokeCase) -> None:
    expected_policy = default_execution_policy(case.scope_decision)
    if case.scope_decision in {"skip", "unsupported"} and case.execution_policy != expected_policy:
        raise ValueError(f"scope_decision {case.scope_decision} must use execution_policy {expected_policy}.")
    if case.scope_decision == "reduced-authority" and case.execution_policy not in {"confirm_reduced_authority", "skip_case"}:
        raise ValueError("reduced-authority cases must confirm the downgrade or skip explicitly.")
    if case.lane_group == "capability" and not case.capability_id:
        raise ValueError("Capability cases must include capability_id.")


def _validate_result_coherence(result: ExhaustiveSmokeResult) -> None:
    if result.scope_decision == "skip" and result.outcome != "skipped":
        raise ValueError("Skipped scope_decision results must end in skipped outcome.")
    if result.scope_decision == "unsupported" and result.outcome != "unsupported":
        raise ValueError("Unsupported scope_decision results must end in unsupported outcome.")
    if result.scope_decision == "reduced-authority" and result.execution_policy == "confirm_reduced_authority":
        if result.outcome not in {"reduced-authority", "pass"}:
            raise ValueError("Reduced-authority confirmation results must end in reduced-authority or pass outcome.")


def _reject_secret_like(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = _clean_text(key).lower()
            if key_text in _SECRET_FIELD_MARKERS:
                raise ValueError(f"Secret-like field name detected at {path}.{key}.")
            _reject_secret_like(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_secret_like(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        if _SECRET_VALUE_RE.search(value):
            raise ValueError(f"Secret-like value detected at {path}.")
        if _DESKTOP_KEY_PATH_RE.search(value):
            raise ValueError(f"Desktop key path detected at {path}.")
        return
