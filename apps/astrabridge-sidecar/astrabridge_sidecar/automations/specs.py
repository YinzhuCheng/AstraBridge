from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..common import now_iso


AUTOMATION_SPEC_SCHEMA_VERSION = "astrabridge-automation-spec-v1"
AUTOMATION_RUN_SCHEMA_VERSION = "astrabridge-automation-run-v1"
AUTOMATION_INBOX_ITEM_SCHEMA_VERSION = "astrabridge-automation-inbox-item-v1"

AUTOMATION_KINDS = {"standalone", "thread"}
AUTOMATION_SCHEDULE_MODES = {"manual", "interval", "daily"}
AUTOMATION_PERMISSION_MODES = {"read-only", "workspace-write", "full-access"}
AUTOMATION_RUN_STATUSES = {"queued", "running", "needs_review", "completed", "failed", "skipped", "cancelled"}
AUTOMATION_INBOX_STATES = {"unread", "reviewed", "archived", "promoted"}
AUTOMATION_INBOX_DISPOSITIONS = {"finding", "no_signal", "failure", "approval_required"}
AUTOMATION_INBOX_SEVERITIES = {"info", "warning", "error"}
AUTOMATION_EXECUTION_HOSTS = {"windows", "wsl", "auto"}
AUTOMATION_WORKSPACE_MODES = {"current_workspace", "dedicated_worktree"}
AUTOMATION_CLEANUP_POLICIES = {"keep_on_finding", "keep_on_failure", "delete_on_no_signal", "manual"}
AUTOMATION_CATCH_UP_POLICIES = {"skip_missed", "run_once"}

SECRET_FIELD_TOKENS = ("authorization", "cookie", "secret", "token", "api_key", "password", "bearer")

AUTOMATION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "skipped", "cancelled", "failed"},
    "running": {"completed", "failed", "needs_review", "cancelled"},
    "needs_review": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "skipped": set(),
    "cancelled": set(),
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_list(value: Any) -> list[str]:
    items = value if isinstance(value, list) else [value]
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return ordered


def _redact_secret_like(value: Any, *, key: str | None = None) -> Any:
    lowered_key = _clean_text(key).lower()
    if lowered_key and any(token in lowered_key for token in SECRET_FIELD_TOKENS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact_secret_like(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_secret_like(item) for item in value]
    text = _clean_text(value)
    if lowered_key and lowered_key.endswith("_env") and text:
        return "[REDACTED_ENV_VALUE]"
    return value


def _required_text(payload: dict[str, Any], field: str) -> str:
    text = _clean_text(payload.get(field))
    if not text:
        raise ValueError(f"{field} is required.")
    return text


def _positive_int(value: Any, *, field: str, default: int, minimum: int = 1) -> int:
    if value in {None, ""}:
        return default
    number = int(value)
    if number < minimum:
        raise ValueError(f"{field} must be >= {minimum}.")
    return number


def _normalize_schedule(payload: Any) -> dict[str, Any]:
    source = dict(payload or {})
    mode = _clean_text(source.get("mode") or "manual").lower()
    if mode not in AUTOMATION_SCHEDULE_MODES:
        raise ValueError(f"Unsupported automation schedule mode: {mode or '<missing>'}.")
    timezone = _clean_text(source.get("timezone") or "UTC") or "UTC"
    catch_up_policy = _clean_text(source.get("catch_up_policy") or "skip_missed").lower()
    if catch_up_policy not in AUTOMATION_CATCH_UP_POLICIES:
        raise ValueError(f"Unsupported catch_up_policy: {catch_up_policy or '<missing>'}.")
    expression = ""
    if mode == "manual":
        expression = "manual"
    elif mode == "interval":
        minutes = _positive_int(source.get("interval_minutes"), field="interval_minutes", default=0)
        expression = f"every:{minutes}m"
    elif mode == "daily":
        hour_text = _clean_text(source.get("hour"))
        minute_text = _clean_text(source.get("minute"))
        if hour_text and minute_text:
            expression = f"{int(hour_text):02d}:{int(minute_text):02d}"
        else:
            expression = _clean_text(source.get("expression"))
        if len(expression) != 5 or expression[2] != ":":
            raise ValueError("daily schedule expression must be HH:MM.")
        hour = int(expression[:2])
        minute = int(expression[3:])
        if hour not in range(24) or minute not in range(60):
            raise ValueError("daily schedule HH:MM is out of range.")
    return {
        "mode": mode,
        "expression": expression,
        "timezone": timezone,
        "next_run_at": _clean_text(source.get("next_run_at")),
        "catch_up_policy": catch_up_policy,
    }


def _normalize_runtime(payload: Any) -> dict[str, Any]:
    source = dict(payload or {})
    permission_mode = _clean_text(source.get("permission_mode") or "workspace-write").lower()
    if permission_mode not in AUTOMATION_PERMISSION_MODES:
        raise ValueError(f"Unsupported automation permission_mode: {permission_mode or '<missing>'}.")
    if permission_mode == "full-access" and source.get("dangerous_opt_in") is not True:
        raise ValueError("full-access automation runtime requires dangerous_opt_in=true.")
    execution_host = _clean_text(source.get("execution_host") or "auto").lower()
    if execution_host not in AUTOMATION_EXECUTION_HOSTS:
        raise ValueError(f"Unsupported execution_host: {execution_host or '<missing>'}.")
    return {
        "profile_id": _clean_text(source.get("profile_id")) or None,
        "model": _clean_text(source.get("model")) or None,
        "effort": _clean_text(source.get("effort")) or None,
        "permission_mode": permission_mode,
        "collaboration_mode": _clean_text(source.get("collaboration_mode")) or None,
        "execution_host": execution_host,
        "mcp_preset_ids": _clean_string_list(source.get("mcp_preset_ids") or []),
        "plugin_skill_preset_ids": _clean_string_list(source.get("plugin_skill_preset_ids") or []),
        "dangerous_opt_in": bool(source.get("dangerous_opt_in", False)),
        "prompt_snapshot": _redact_secret_like(source.get("prompt_snapshot") or {}),
    }


def _normalize_workspace(payload: Any) -> dict[str, Any]:
    source = dict(payload or {})
    mode = _clean_text(source.get("mode") or "dedicated_worktree").lower()
    if mode not in AUTOMATION_WORKSPACE_MODES:
        raise ValueError(f"Unsupported workspace mode: {mode or '<missing>'}.")
    cleanup_policy = _clean_text(source.get("cleanup_policy") or "keep_on_finding").lower()
    if cleanup_policy not in AUTOMATION_CLEANUP_POLICIES:
        raise ValueError(f"Unsupported cleanup_policy: {cleanup_policy or '<missing>'}.")
    return {
        "mode": mode,
        "base_branch": _clean_text(source.get("base_branch")) or None,
        "worktree_root": _clean_text(source.get("worktree_root")) or None,
        "cleanup_policy": cleanup_policy,
    }


def _normalize_triage(payload: Any) -> dict[str, Any]:
    source = dict(payload or {})
    notify_on = _clean_text(source.get("notify_on") or "finding").lower()
    if notify_on not in {"finding", "failure", "every_run"}:
        raise ValueError(f"Unsupported triage notify_on: {notify_on or '<missing>'}.")
    return {
        "archive_no_signal": bool(source.get("archive_no_signal", True)),
        "notify_on": notify_on,
        "finding_keywords": _clean_string_list(source.get("finding_keywords") or []),
    }


def _normalize_limits(payload: Any) -> dict[str, Any]:
    source = dict(payload or {})
    return {
        "timeout_sec": _positive_int(source.get("timeout_sec"), field="timeout_sec", default=1800),
        "max_retries": _positive_int(source.get("max_retries"), field="max_retries", default=0, minimum=0),
        "max_artifact_bytes": _positive_int(source.get("max_artifact_bytes"), field="max_artifact_bytes", default=2_000_000),
        "max_parallel_runs": _positive_int(source.get("max_parallel_runs"), field="max_parallel_runs", default=1),
        "daily_run_limit": _positive_int(source.get("daily_run_limit"), field="daily_run_limit", default=0, minimum=0),
        "retry_backoff_sec": _positive_int(source.get("retry_backoff_sec"), field="retry_backoff_sec", default=300),
        "retry_backoff_multiplier": _positive_int(source.get("retry_backoff_multiplier"), field="retry_backoff_multiplier", default=2),
        "retry_backoff_max_sec": _positive_int(source.get("retry_backoff_max_sec"), field="retry_backoff_max_sec", default=3600),
    }


@dataclass(frozen=True)
class AutomationSpec:
    schema_version: str
    automation_id: str
    project_id: str
    name: str
    description: str
    enabled: bool
    kind: str
    prompt: str
    schedule: dict[str, Any]
    runtime: dict[str, Any]
    workspace: dict[str, Any]
    triage: dict[str, Any]
    limits: dict[str, Any]
    created_at: str
    updated_at: str
    last_run_at: str | None
    last_status: str | None

    @classmethod
    def normalize(cls, payload: Any) -> "AutomationSpec":
        if not isinstance(payload, dict):
            raise ValueError("Automation spec payload must be an object.")
        kind = _clean_text(payload.get("kind") or "standalone").lower()
        if kind not in AUTOMATION_KINDS:
            raise ValueError(f"Unsupported automation kind: {kind or '<missing>'}.")
        return cls(
            schema_version=AUTOMATION_SPEC_SCHEMA_VERSION,
            automation_id=_required_text(payload, "automation_id"),
            project_id=_required_text(payload, "project_id"),
            name=_required_text(payload, "name"),
            description=_clean_text(payload.get("description")),
            enabled=bool(payload.get("enabled", True)),
            kind=kind,
            prompt=_required_text(payload, "prompt"),
            schedule=_normalize_schedule(payload.get("schedule")),
            runtime=_normalize_runtime(payload.get("runtime")),
            workspace=_normalize_workspace(payload.get("workspace")),
            triage=_normalize_triage(payload.get("triage")),
            limits=_normalize_limits(payload.get("limits")),
            created_at=_clean_text(payload.get("created_at")) or now_iso(),
            updated_at=_clean_text(payload.get("updated_at")) or now_iso(),
            last_run_at=_clean_text(payload.get("last_run_at")) or None,
            last_status=_clean_text(payload.get("last_status")) or None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AutomationRun:
    schema_version: str
    run_id: str
    automation_id: str
    project_id: str
    trigger: str
    status: str
    due_at: str
    started_at: str | None
    finished_at: str | None
    thread_id: str | None
    turn_id: str | None
    worktree_path: str | None
    runtime_profile_id: str | None
    exit_code: int | None
    signal: str
    summary: str
    artifact_refs: list[str]
    redacted_error: str | None
    next_retry_at: str | None
    retry_count: int

    @classmethod
    def normalize(cls, payload: Any) -> "AutomationRun":
        if not isinstance(payload, dict):
            raise ValueError("Automation run payload must be an object.")
        status = _required_text(payload, "status").lower()
        if status not in AUTOMATION_RUN_STATUSES:
            raise ValueError(f"Unsupported automation run status: {status}.")
        trigger = _required_text(payload, "trigger").lower()
        if trigger not in {"schedule", "manual", "retry"}:
            raise ValueError(f"Unsupported automation trigger: {trigger}.")
        signal = _clean_text(payload.get("signal") or "unknown").lower()
        if signal not in {"finding", "no_signal", "unknown"}:
            raise ValueError(f"Unsupported automation signal: {signal}.")
        return cls(
            schema_version=AUTOMATION_RUN_SCHEMA_VERSION,
            run_id=_required_text(payload, "run_id"),
            automation_id=_required_text(payload, "automation_id"),
            project_id=_required_text(payload, "project_id"),
            trigger=trigger,
            status=status,
            due_at=_required_text(payload, "due_at"),
            started_at=_clean_text(payload.get("started_at")) or None,
            finished_at=_clean_text(payload.get("finished_at")) or None,
            thread_id=_clean_text(payload.get("thread_id")) or None,
            turn_id=_clean_text(payload.get("turn_id")) or None,
            worktree_path=_clean_text(payload.get("worktree_path")) or None,
            runtime_profile_id=_clean_text(payload.get("runtime_profile_id")) or None,
            exit_code=int(payload["exit_code"]) if payload.get("exit_code") not in {None, ""} else None,
            signal=signal,
            summary=_clean_text(payload.get("summary")),
            artifact_refs=_clean_string_list(payload.get("artifact_refs") or []),
            redacted_error=_clean_text(payload.get("redacted_error")) or None,
            next_retry_at=_clean_text(payload.get("next_retry_at")) or None,
            retry_count=_positive_int(payload.get("retry_count"), field="retry_count", default=0, minimum=0),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AutomationInboxItem:
    schema_version: str
    item_id: str
    run_id: str
    automation_id: str
    project_id: str
    state: str
    disposition: str
    severity: str
    title: str
    summary: str
    created_at: str
    updated_at: str
    promotion_ref: str | None

    @classmethod
    def normalize(cls, payload: Any) -> "AutomationInboxItem":
        if not isinstance(payload, dict):
            raise ValueError("Automation inbox item payload must be an object.")
        state = _required_text(payload, "state").lower()
        disposition = _required_text(payload, "disposition").lower()
        severity = _required_text(payload, "severity").lower()
        if state not in AUTOMATION_INBOX_STATES:
            raise ValueError(f"Unsupported automation inbox state: {state}.")
        if disposition not in AUTOMATION_INBOX_DISPOSITIONS:
            raise ValueError(f"Unsupported automation inbox disposition: {disposition}.")
        if severity not in AUTOMATION_INBOX_SEVERITIES:
            raise ValueError(f"Unsupported automation inbox severity: {severity}.")
        return cls(
            schema_version=AUTOMATION_INBOX_ITEM_SCHEMA_VERSION,
            item_id=_required_text(payload, "item_id"),
            run_id=_required_text(payload, "run_id"),
            automation_id=_required_text(payload, "automation_id"),
            project_id=_required_text(payload, "project_id"),
            state=state,
            disposition=disposition,
            severity=severity,
            title=_required_text(payload, "title"),
            summary=_clean_text(payload.get("summary")),
            created_at=_clean_text(payload.get("created_at")) or now_iso(),
            updated_at=_clean_text(payload.get("updated_at")) or now_iso(),
            promotion_ref=_clean_text(payload.get("promotion_ref")) or None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def can_transition_run_status(from_status: str, to_status: str) -> bool:
    source = _clean_text(from_status).lower()
    target = _clean_text(to_status).lower()
    if source not in AUTOMATION_STATUS_TRANSITIONS:
        raise ValueError(f"Unknown automation run status: {from_status}")
    if target not in AUTOMATION_RUN_STATUSES:
        raise ValueError(f"Unknown automation run status: {to_status}")
    return target in AUTOMATION_STATUS_TRANSITIONS[source]


def assert_transition_run_status(from_status: str, to_status: str) -> None:
    if not can_transition_run_status(from_status, to_status):
        raise ValueError(f"Invalid automation run status transition: {from_status} -> {to_status}")
