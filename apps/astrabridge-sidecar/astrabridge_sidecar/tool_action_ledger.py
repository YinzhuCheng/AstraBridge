"""Validated side-effect action envelopes and durable receipt ledger.

Provider adapters may repair a tool-call wire shape, but a repaired call is not
authorization to change the workspace.  This module is the narrow local
boundary between validated tool arguments and an actual side effect.  It keeps
only redacted/digested argument views on disk so a handoff or retry can answer
whether an action already happened without retaining command text, edit
contents, credentials, or provider-private state.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, now_iso, read_json, write_json
from .security import redact_sensitive


TOOL_ACTION_ENVELOPE_SCHEMA_VERSION = "astrabridge-tool-action-envelope-v1"
TOOL_ACTION_RECEIPT_SCHEMA_VERSION = "astrabridge-tool-action-receipt-v1"
TOOL_ACTION_LEDGER_SCHEMA_VERSION = "astrabridge-tool-action-ledger-v1"
SIDE_EFFECTING_TOOL_NAMES = frozenset({"create_checkpoint", "edit_apply", "run_command", "run_tests"})
EDIT_ACTION_OPERATIONS = frozenset({"apply_patch", "replace_file", "write_file", "structured_edit", "propose_only"})
TOOL_ACTION_STATES = frozenset(
    {
        "approval_required",
        "completed",
        "executing",
        "interrupted",
        "recovery_required",
        "repairable",
        "retryable",
        "terminal",
    }
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+\-]{0,255}$")
_DIRECT_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(?:sk|rk|pk)-[A-Za-z0-9_-]{8,}\b|\b(?:api|access|auth|secret)?[_-]?(?:key|token)_[A-Za-z0-9_-]{8,}\b"
)
_LEDGER_LOCK = threading.RLock()


class ToolActionValidationError(ValueError):
    """A repairable request error that must be returned to the tool caller."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.state = "repairable"


class ToolActionImmutableConflict(ValueError):
    """An idempotency key was reused for a different action identity."""


def is_side_effecting_tool(tool_name: Any) -> bool:
    return str(tool_name or "").strip() in SIDE_EFFECTING_TOOL_NAMES


def validate_side_effect_arguments(tool_name: str, value: Any) -> dict[str, Any]:
    """Return a schema-valid normalized action argument object.

    In particular, the transport repair wrapper ``{"raw": ...}`` is never an
    executable argument object, even if another field in that object happens to
    look valid.  A caller must repair it into the declared tool schema first.
    """

    name = str(tool_name or "").strip()
    if name not in SIDE_EFFECTING_TOOL_NAMES:
        raise ToolActionValidationError("unsupported_side_effect_tool", f"Unsupported side-effect tool: {name or 'unknown'}.")
    if not isinstance(value, dict):
        raise ToolActionValidationError("arguments_not_object", f"{name} arguments must be a JSON object.")
    reject_unvalidated_raw_wrapper(value, tool_name=name)
    arguments = deepcopy(value)
    if name in {"run_command", "run_tests"}:
        _reject_unknown(arguments, {"command", "cwd", "timeout_seconds"}, name)
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ToolActionValidationError("command_required", f"{name} requires a non-empty command string.")
        if "cwd" in arguments and arguments["cwd"] is not None and not isinstance(arguments["cwd"], str):
            raise ToolActionValidationError("cwd_invalid", f"{name}.cwd must be a string when provided.")
        if "timeout_seconds" in arguments and arguments["timeout_seconds"] is not None:
            timeout = arguments["timeout_seconds"]
            if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
                raise ToolActionValidationError("timeout_invalid", f"{name}.timeout_seconds must be a positive integer when provided.")
        return arguments
    if name == "create_checkpoint":
        _reject_unknown(arguments, {"description"}, name)
        if "description" in arguments and arguments["description"] is not None and not isinstance(arguments["description"], str):
            raise ToolActionValidationError("description_invalid", "create_checkpoint.description must be a string when provided.")
        return arguments

    _reject_unknown(arguments, {"path", "content", "search", "replace", "count", "edits", "operation"}, name)
    path = arguments.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ToolActionValidationError("path_required", "edit_apply requires a non-empty workspace-relative path.")
    has_content = isinstance(arguments.get("content"), str)
    has_single_edit = isinstance(arguments.get("search"), str) and bool(arguments.get("search")) and isinstance(arguments.get("replace"), str)
    has_edits = isinstance(arguments.get("edits"), list) and bool(arguments.get("edits"))
    if not (has_content or has_single_edit or has_edits):
        raise ToolActionValidationError("edit_instruction_required", "edit_apply requires content, a search/replace pair, or a non-empty edits list.")
    if "content" in arguments and arguments["content"] is not None and not isinstance(arguments["content"], str):
        raise ToolActionValidationError("content_invalid", "edit_apply.content must be a string when provided.")
    if "search" in arguments and arguments["search"] is not None and not isinstance(arguments["search"], str):
        raise ToolActionValidationError("search_invalid", "edit_apply.search must be a string when provided.")
    if "replace" in arguments and arguments["replace"] is not None and not isinstance(arguments["replace"], str):
        raise ToolActionValidationError("replace_invalid", "edit_apply.replace must be a string when provided.")
    if "count" in arguments and arguments["count"] is not None:
        count = arguments["count"]
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ToolActionValidationError("count_invalid", "edit_apply.count must be a positive integer when provided.")
    if "edits" in arguments and arguments["edits"] is not None:
        _validate_edit_list(arguments["edits"])
    if "operation" in arguments and arguments["operation"] is not None:
        operation = arguments["operation"]
        if not isinstance(operation, str) or operation.strip().lower() not in EDIT_ACTION_OPERATIONS:
            raise ToolActionValidationError(
                "operation_invalid",
                "edit_apply.operation must be one of apply_patch, replace_file, write_file, structured_edit, or propose_only.",
            )
    return arguments


def reject_unvalidated_raw_wrapper(value: Any, *, tool_name: str | None = None) -> None:
    """Reject a transport-repair ``raw`` wrapper before an action is admitted.

    Service payloads carry trusted routing context alongside tool arguments, so
    they cannot always be passed wholesale to the strict per-tool schema.  The
    service must nevertheless reject a raw wrapper anywhere in the incoming
    side-effect request before selecting the executable fields.
    """

    if _contains_raw_wrapper(value):
        label = str(tool_name or "side-effect tool").strip() or "side-effect tool"
        raise ToolActionValidationError(
            "unvalidated_raw_wrapper",
            f"{label} cannot execute from an unvalidated raw argument wrapper; repair it to the declared schema first.",
        )


class ToolActionReceiptLedger:
    """Workspace-local append-safe receipt state for side-effect tools.

    The native tool loop is serial, and this ledger protects repeated calls in
    that process with a lock plus atomic state replacement.  A lingering
    ``executing`` receipt fails closed as ``recovery_required`` rather than
    launching a potentially duplicated command or edit.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._path = self._workspace_root / WORKSPACE_STATE_DIRNAME / "tool_action_receipts.json"

    @property
    def path(self) -> Path:
        return self._path

    def build_envelope(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        lineage: dict[str, Any] | None,
        authority: dict[str, Any] | None,
        workspace: dict[str, Any] | None,
        idempotency_key: str | None = None,
        source: str = "sidecar",
    ) -> dict[str, Any]:
        name = str(tool_name or "").strip()
        normalized = validate_side_effect_arguments(name, arguments)
        safe_arguments = _safe_argument_view(name, normalized)
        normalized_lineage = _safe_lineage(lineage, seed=_stable_digest({"tool": name, "arguments": safe_arguments}))
        normalized_authority = _safe_authority(authority)
        normalized_workspace = _safe_workspace(workspace)
        identity = {
            "schema_version": TOOL_ACTION_ENVELOPE_SCHEMA_VERSION,
            "tool_name": name,
            "arguments": safe_arguments,
            "lineage": normalized_lineage,
        }
        identity_digest = _stable_digest(identity)
        requested_key = _safe_identifier(idempotency_key)
        if idempotency_key and not requested_key:
            raise ToolActionValidationError("idempotency_key_invalid", "idempotency_key must be a bounded identifier when provided.")
        key = requested_key or f"tool-{identity_digest[:40]}"
        return {
            "schema_version": TOOL_ACTION_ENVELOPE_SCHEMA_VERSION,
            "action_id": f"action-{identity_digest[:24]}",
            "idempotency_key": key,
            "identity_digest": identity_digest,
            "tool_name": name,
            "arguments": safe_arguments,
            "lineage": normalized_lineage,
            "authority": normalized_authority,
            "workspace": normalized_workspace,
            "source": _safe_identifier(source) or "sidecar",
            "created_at": now_iso(),
        }

    def admit(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Reserve an action exactly once or return its existing receipt."""

        normalized = self._normalize_envelope(envelope)
        with _LEDGER_LOCK:
            state = self._state()
            receipts = dict(state.get("receipts") or {})
            key = normalized["idempotency_key"]
            existing = dict(receipts.get(key) or {})
            if existing:
                if str(existing.get("identity_digest") or "") != normalized["identity_digest"]:
                    raise ToolActionImmutableConflict("idempotency_key is already bound to a different tool action.")
                current_state = str(existing.get("state") or "")
                if current_state in {"completed", "terminal"}:
                    return {"decision": "duplicate", "receipt": deepcopy(existing)}
                if current_state in {"executing", "interrupted", "recovery_required"}:
                    updated = {
                        **existing,
                        "state": "recovery_required",
                        "outcome": "recovery_required",
                        "recovery_required": True,
                        "updated_at": now_iso(),
                    }
                    receipts[key] = updated
                    state["receipts"] = receipts
                    self._write_state(state)
                    return {"decision": "recovery_required", "receipt": deepcopy(updated)}
                if current_state in {"approval_required", "retryable"}:
                    updated = {
                        **existing,
                        "authority": deepcopy(normalized["authority"]),
                        "workspace": deepcopy(normalized["workspace"]),
                        "source": normalized["source"],
                        "state": "executing",
                        "outcome": "pending",
                        "recovery_required": False,
                        "attempt_count": max(1, int(existing.get("attempt_count") or 0) + 1),
                        "updated_at": now_iso(),
                        "started_at": now_iso(),
                    }
                    receipts[key] = updated
                    state["receipts"] = receipts
                    self._write_state(state)
                    return {"decision": "execute", "receipt": deepcopy(updated)}
                raise ToolActionImmutableConflict(f"Unknown durable tool-action state: {current_state or 'missing'}.")
            receipt = self._new_receipt(normalized, state="executing", outcome="pending", attempt_count=1)
            receipts[key] = receipt
            state["receipts"] = receipts
            self._write_state(state)
            return {"decision": "execute", "receipt": deepcopy(receipt)}

    def record_approval_required(self, envelope: dict[str, Any], *, reason: str) -> dict[str, Any]:
        normalized = self._normalize_envelope(envelope)
        with _LEDGER_LOCK:
            state = self._state()
            receipts = dict(state.get("receipts") or {})
            key = normalized["idempotency_key"]
            existing = dict(receipts.get(key) or {})
            if existing and str(existing.get("identity_digest") or "") != normalized["identity_digest"]:
                raise ToolActionImmutableConflict("idempotency_key is already bound to a different tool action.")
            if existing and str(existing.get("state") or "") in {"completed", "terminal", "executing", "interrupted", "recovery_required"}:
                return deepcopy(existing)
            receipt = existing or self._new_receipt(normalized, state="approval_required", outcome="user_approval_required", attempt_count=0)
            receipt.update(
                {
                    "authority": deepcopy(normalized["authority"]),
                    "workspace": deepcopy(normalized["workspace"]),
                    "source": normalized["source"],
                    "state": "approval_required",
                    "outcome": "user_approval_required",
                    "approval_reason": _safe_text(reason, limit=600),
                    "recovery_required": False,
                    "updated_at": now_iso(),
                }
            )
            receipts[key] = receipt
            state["receipts"] = receipts
            self._write_state(state)
            return deepcopy(receipt)

    def record_retryable(self, envelope: dict[str, Any], *, reason: str) -> dict[str, Any]:
        """Record a pre-execution failure that may be safely attempted again.

        This state is for failures such as an unavailable approval bridge: no
        tool process or edit was started, so recovery confirmation is not
        needed before retrying the same idempotency key.
        """

        normalized = self._normalize_envelope(envelope)
        with _LEDGER_LOCK:
            state = self._state()
            receipts = dict(state.get("receipts") or {})
            key = normalized["idempotency_key"]
            existing = dict(receipts.get(key) or {})
            if existing and str(existing.get("identity_digest") or "") != normalized["identity_digest"]:
                raise ToolActionImmutableConflict("idempotency_key is already bound to a different tool action.")
            if existing and str(existing.get("state") or "") in {"completed", "terminal", "executing", "interrupted", "recovery_required"}:
                return deepcopy(existing)
            receipt = existing or self._new_receipt(normalized, state="retryable", outcome="retryable_pre_execution_failure", attempt_count=0)
            receipt.update(
                {
                    "authority": deepcopy(normalized["authority"]),
                    "workspace": deepcopy(normalized["workspace"]),
                    "source": normalized["source"],
                    "state": "retryable",
                    "outcome": "retryable_pre_execution_failure",
                    "retry_reason": _safe_text(reason, limit=600),
                    "recovery_required": False,
                    "updated_at": now_iso(),
                }
            )
            receipts[key] = receipt
            state["receipts"] = receipts
            self._write_state(state)
            return deepcopy(receipt)

    def complete(self, envelope: dict[str, Any], *, result: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_envelope(envelope)
        result_summary = _safe_result_summary(result)
        timed_out = bool(result_summary.get("timed_out"))
        successful = bool(result_summary.get("ok"))
        state_name = "interrupted" if timed_out else ("completed" if successful else "terminal")
        outcome = "timeout_unknown_effect" if timed_out else ("applied" if successful else "terminal_failure")
        return self._update_completion(
            normalized,
            state_name=state_name,
            outcome=outcome,
            result=result_summary,
            recovery_required=timed_out,
        )

    def interrupt(self, envelope: dict[str, Any], *, reason: str) -> dict[str, Any]:
        normalized = self._normalize_envelope(envelope)
        return self._update_completion(
            normalized,
            state_name="interrupted",
            outcome="interrupted_unknown_effect",
            result={"error": _safe_text(reason, limit=600)},
            recovery_required=True,
        )

    def record_terminal(self, envelope: dict[str, Any], *, reason: str) -> dict[str, Any]:
        normalized = self._normalize_envelope(envelope)
        return self._update_completion(
            normalized,
            state_name="terminal",
            outcome="authorization_or_contract_denied",
            result={"error": _safe_text(reason, limit=600)},
            recovery_required=False,
        )

    def resolve_recovery(self, idempotency_key: str, *, resolution: str) -> dict[str, Any]:
        key = _safe_identifier(idempotency_key)
        if not key:
            raise ToolActionValidationError("idempotency_key_invalid", "idempotency_key must be a bounded identifier.")
        decision = str(resolution or "").strip().lower()
        if decision not in {"confirmed_applied", "confirmed_not_applied"}:
            raise ToolActionValidationError(
                "recovery_resolution_invalid",
                "Recovery resolution must be confirmed_applied or confirmed_not_applied.",
            )
        with _LEDGER_LOCK:
            state = self._state()
            receipts = dict(state.get("receipts") or {})
            receipt = dict(receipts.get(key) or {})
            if not receipt:
                raise KeyError(f"Unknown tool action receipt: {key}")
            if str(receipt.get("state") or "") not in {"interrupted", "recovery_required"}:
                raise ToolActionImmutableConflict("Only interrupted tool actions may be recovered.")
            receipt.update(
                {
                    "state": "completed" if decision == "confirmed_applied" else "retryable",
                    "outcome": decision,
                    "recovery_required": False,
                    "recovered_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            receipts[key] = receipt
            state["receipts"] = receipts
            self._write_state(state)
            return deepcopy(receipt)

    def receipt(self, idempotency_key: str) -> dict[str, Any] | None:
        key = _safe_identifier(idempotency_key)
        if not key:
            return None
        with _LEDGER_LOCK:
            return deepcopy(dict(self._state().get("receipts") or {}).get(key) or None)

    def receipt_references_for_lineage(
        self,
        *,
        task_id: str | None = None,
        visible_thread_id: str | None = None,
        execution_thread_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return only secret-free action references for a source turn/lane.

        A handoff/retry only needs enough evidence to decide whether a prior
        side effect might have run.  Returning argument digests or raw receipt
        contents here would invite them into task handoff and runtime event
        records, so this intentionally exposes IDs, state, and lineage only.
        """

        requested_task_id = _safe_identifier(task_id)
        requested_thread_ids = {
            value
            for value in (
                _safe_identifier(visible_thread_id),
                _safe_identifier(execution_thread_id),
            )
            if value
        }
        requested_turn_id = _safe_identifier(turn_id)
        if not (requested_task_id or requested_thread_ids or requested_turn_id):
            return []
        with _LEDGER_LOCK:
            references: list[dict[str, Any]] = []
            for receipt in dict(self._state().get("receipts") or {}).values():
                if not isinstance(receipt, dict):
                    continue
                lineage = dict(receipt.get("lineage") or {})
                if requested_task_id and str(lineage.get("task_id") or "") != requested_task_id:
                    continue
                lineage_thread_ids = {
                    str(lineage.get("visible_thread_id") or ""),
                    str(lineage.get("execution_thread_id") or ""),
                }
                if requested_thread_ids and not (requested_thread_ids & lineage_thread_ids):
                    continue
                if requested_turn_id and str(lineage.get("turn_id") or "") != requested_turn_id:
                    continue
                references.append(_safe_receipt_reference(receipt))
            return sorted(
                references,
                key=lambda item: (
                    str(item.get("updated_at") or ""),
                    str(item.get("receipt_id") or item.get("idempotency_key") or ""),
                ),
            )

    def _update_completion(
        self,
        envelope: dict[str, Any],
        *,
        state_name: str,
        outcome: str,
        result: dict[str, Any],
        recovery_required: bool,
    ) -> dict[str, Any]:
        with _LEDGER_LOCK:
            state = self._state()
            receipts = dict(state.get("receipts") or {})
            key = envelope["idempotency_key"]
            receipt = dict(receipts.get(key) or self._new_receipt(envelope, state="executing", outcome="pending", attempt_count=1))
            if str(receipt.get("identity_digest") or "") != envelope["identity_digest"]:
                raise ToolActionImmutableConflict("idempotency_key is already bound to a different tool action.")
            receipt.update(
                {
                    "state": state_name,
                    "outcome": outcome,
                    "result": _safe_result_summary(result),
                    "recovery_required": bool(recovery_required),
                    "completed_at": now_iso(),
                    "updated_at": now_iso(),
                }
            )
            receipts[key] = receipt
            state["receipts"] = receipts
            self._write_state(state)
            return deepcopy(receipt)

    def _new_receipt(self, envelope: dict[str, Any], *, state: str, outcome: str, attempt_count: int) -> dict[str, Any]:
        timestamp = now_iso()
        return {
            "schema_version": TOOL_ACTION_RECEIPT_SCHEMA_VERSION,
            "receipt_id": f"receipt-{str(envelope.get('identity_digest') or '')[:24]}",
            "idempotency_key": envelope["idempotency_key"],
            "action_id": envelope["action_id"],
            "identity_digest": envelope["identity_digest"],
            "tool_name": envelope["tool_name"],
            "state": state,
            "outcome": outcome,
            "attempt_count": max(0, int(attempt_count)),
            "recovery_required": False,
            "arguments": deepcopy(envelope["arguments"]),
            "lineage": deepcopy(envelope["lineage"]),
            "authority": deepcopy(envelope["authority"]),
            "workspace": deepcopy(envelope["workspace"]),
            "source": envelope["source"],
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    def _normalize_envelope(self, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ToolActionValidationError("envelope_invalid", "Tool action envelope must be an object.")
        if str(value.get("schema_version") or "") != TOOL_ACTION_ENVELOPE_SCHEMA_VERSION:
            raise ToolActionValidationError("envelope_schema_invalid", "Tool action envelope schema is invalid.")
        key = _safe_identifier(value.get("idempotency_key"))
        identity = str(value.get("identity_digest") or "").strip().lower()
        tool_name = str(value.get("tool_name") or "").strip()
        if not key or not re.fullmatch(r"[a-f0-9]{64}", identity) or tool_name not in SIDE_EFFECTING_TOOL_NAMES:
            raise ToolActionValidationError("envelope_identity_invalid", "Tool action envelope identity is invalid.")
        safe_arguments = _safe_argument_view(tool_name, dict(value.get("arguments") or {}), already_safe=True)
        lineage = _safe_lineage(value.get("lineage"), seed=identity)
        expected_identity = _stable_digest(
            {
                "schema_version": TOOL_ACTION_ENVELOPE_SCHEMA_VERSION,
                "tool_name": tool_name,
                "arguments": safe_arguments,
                "lineage": lineage,
            }
        )
        if expected_identity != identity:
            raise ToolActionValidationError("envelope_identity_invalid", "Tool action envelope identity does not match its safe action fields.")
        return {
            "schema_version": TOOL_ACTION_ENVELOPE_SCHEMA_VERSION,
            "action_id": _safe_identifier(value.get("action_id")) or f"action-{identity[:24]}",
            "idempotency_key": key,
            "identity_digest": identity,
            "tool_name": tool_name,
            "arguments": safe_arguments,
            "lineage": lineage,
            "authority": _safe_authority(value.get("authority")),
            "workspace": _safe_workspace(value.get("workspace")),
            "source": _safe_identifier(value.get("source")) or "sidecar",
        }

    def _state(self) -> dict[str, Any]:
        payload = read_json(self._path, {})
        if not isinstance(payload, dict):
            payload = {}
        receipts = payload.get("receipts")
        return {
            "schema_version": TOOL_ACTION_LEDGER_SCHEMA_VERSION,
            "receipts": dict(receipts) if isinstance(receipts, dict) else {},
            "updated_at": str(payload.get("updated_at") or "") or None,
        }

    def _write_state(self, state: dict[str, Any]) -> None:
        write_json(
            self._path,
            {
                "schema_version": TOOL_ACTION_LEDGER_SCHEMA_VERSION,
                "updated_at": now_iso(),
                "receipts": dict(state.get("receipts") or {}),
            },
        )


def _safe_receipt_reference(value: dict[str, Any]) -> dict[str, Any]:
    """Compact a receipt for retry/handoff admission without action details."""

    raw = dict(value or {})
    lineage = dict(raw.get("lineage") or {})
    tool_name = str(raw.get("tool_name") or "").strip()
    return {
        "receipt_id": _safe_identifier(raw.get("receipt_id")),
        "idempotency_key": _safe_identifier(raw.get("idempotency_key")),
        "action_id": _safe_identifier(raw.get("action_id")),
        "tool_name": tool_name if tool_name in SIDE_EFFECTING_TOOL_NAMES else "unknown",
        "state": str(raw.get("state") or "unknown").strip()[:80] or "unknown",
        "recovery_required": bool(raw.get("recovery_required")),
        "lineage": {
            "task_id": _safe_identifier(lineage.get("task_id")),
            "visible_thread_id": _safe_identifier(lineage.get("visible_thread_id")),
            "execution_thread_id": _safe_identifier(lineage.get("execution_thread_id")),
            "turn_id": _safe_identifier(lineage.get("turn_id")),
            "tool_call_id": _safe_identifier(lineage.get("tool_call_id")),
        },
        "updated_at": _safe_text(raw.get("updated_at"), limit=64) or None,
    }


def _contains_raw_wrapper(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).strip().lower() == "raw":
                return True
            if _contains_raw_wrapper(item):
                return True
    if isinstance(value, list):
        return any(_contains_raw_wrapper(item) for item in value)
    return False


def _reject_unknown(value: dict[str, Any], allowed: set[str], tool_name: str) -> None:
    unexpected = sorted(str(key) for key in value if str(key) not in allowed)
    if unexpected:
        raise ToolActionValidationError(
            "arguments_schema_invalid",
            f"{tool_name} arguments contain unsupported fields: {', '.join(unexpected[:6])}.",
        )


def _validate_edit_list(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ToolActionValidationError("edits_invalid", "edit_apply.edits must be a non-empty list when provided.")
    for index, item in enumerate(value):
        if not isinstance(item, dict) or _contains_raw_wrapper(item):
            raise ToolActionValidationError("edits_invalid", f"edit_apply.edits[{index}] must be a normalized object.")
        _reject_unknown(item, {"search", "replace", "count"}, "edit_apply.edits")
        if not isinstance(item.get("search"), str) or not str(item.get("search") or ""):
            raise ToolActionValidationError("edits_invalid", f"edit_apply.edits[{index}].search must be a non-empty string.")
        if not isinstance(item.get("replace"), str):
            raise ToolActionValidationError("edits_invalid", f"edit_apply.edits[{index}].replace must be a string.")
        if "count" in item and item["count"] is not None:
            count = item["count"]
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise ToolActionValidationError("edits_invalid", f"edit_apply.edits[{index}].count must be a positive integer.")


def _safe_argument_view(tool_name: str, value: dict[str, Any], *, already_safe: bool = False) -> dict[str, Any]:
    arguments = dict(value or {})
    if tool_name in {"run_command", "run_tests"}:
        if already_safe:
            return {
                "command_digest": _safe_digest_value(arguments.get("command_digest")),
                "cwd": _safe_text(arguments.get("cwd"), limit=512) or None,
                "timeout_seconds": _positive_int(arguments.get("timeout_seconds")),
            }
        return {
            "command_digest": _stable_digest(_redact_value(arguments.get("command"))),
            "cwd": _safe_text(arguments.get("cwd"), limit=512) or None,
            "timeout_seconds": _positive_int(arguments.get("timeout_seconds")),
        }
    if tool_name == "create_checkpoint":
        if already_safe:
            return {"description_digest": _safe_digest_value(arguments.get("description_digest"))}
        return {"description_digest": _stable_digest(_redact_value(arguments.get("description") or ""))}
    if already_safe:
        return {
            "path": _safe_text(arguments.get("path"), limit=512) or None,
            "content_digest": _safe_digest_value(arguments.get("content_digest")),
            "search_digest": _safe_digest_value(arguments.get("search_digest")),
            "replace_digest": _safe_digest_value(arguments.get("replace_digest")),
            "edits_digest": _safe_digest_value(arguments.get("edits_digest")),
            "count": _positive_int(arguments.get("count")),
            "operation": _safe_identifier(arguments.get("operation")),
        }
    return {
        "path": _safe_text(arguments.get("path"), limit=512) or None,
        "content_digest": _stable_digest(_redact_value(arguments.get("content"))) if "content" in arguments else None,
        "search_digest": _stable_digest(_redact_value(arguments.get("search"))) if "search" in arguments else None,
        "replace_digest": _stable_digest(_redact_value(arguments.get("replace"))) if "replace" in arguments else None,
        "edits_digest": _stable_digest(_redact_value(arguments.get("edits"))) if "edits" in arguments else None,
        "count": _positive_int(arguments.get("count")),
        "operation": _safe_identifier(arguments.get("operation")),
    }


def _safe_lineage(value: Any, *, seed: str) -> dict[str, str]:
    raw = dict(value) if isinstance(value, dict) else {}
    task_id = _safe_identifier(raw.get("task_id")) or f"workspace-{seed[:16]}"
    visible_thread_id = _safe_identifier(raw.get("visible_thread_id") or raw.get("thread_id")) or f"thread-{seed[:16]}"
    execution_thread_id = _safe_identifier(raw.get("execution_thread_id")) or visible_thread_id
    turn_id = _safe_identifier(raw.get("turn_id")) or f"turn-{seed[:16]}"
    tool_call_id = _safe_identifier(raw.get("tool_call_id") or raw.get("call_id")) or f"call-{seed[:16]}"
    return {
        "task_id": task_id,
        "visible_thread_id": visible_thread_id,
        "execution_thread_id": execution_thread_id,
        "turn_id": turn_id,
        "tool_call_id": tool_call_id,
    }


def _safe_authority(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    tier = str(raw.get("tier") or raw.get("authority_tier") or "").strip().upper()
    return {
        "tier": tier if tier in {"A", "B", "C", "D"} else "unknown",
        "decision": _safe_identifier(raw.get("decision")) or "unknown",
        "permission_mode": _safe_identifier(raw.get("permission_mode")) or "unknown",
        "reason": _safe_text(raw.get("reason"), limit=600) or None,
    }


def _safe_workspace(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    return {
        "workspace_version": _safe_digest_value(raw.get("workspace_version")) or "unknown",
        "checkpoint_version": _safe_identifier(raw.get("checkpoint_version")) or "none",
    }


def _safe_result_summary(value: Any) -> dict[str, Any]:
    raw = dict(value) if isinstance(value, dict) else {}
    result: dict[str, Any] = {
        "ok": bool(raw.get("ok")),
        "status": _safe_identifier(raw.get("status")) or None,
        "applied": bool(raw.get("applied")),
        "timed_out": bool(raw.get("timed_out")),
        "exit_code": raw.get("exit_code") if isinstance(raw.get("exit_code"), int) else None,
        "path": _safe_text(raw.get("path"), limit=512) or None,
        "checkpoint_save_id": _safe_identifier(raw.get("checkpoint_save_id")) or None,
        "error": _safe_text(raw.get("error"), limit=600) or None,
    }
    return result


def _redact_value(value: Any) -> Any:
    redacted = redact_sensitive(value)
    if isinstance(redacted, dict):
        return {str(key): _redact_value(item) for key, item in redacted.items()}
    if isinstance(redacted, list):
        return [_redact_value(item) for item in redacted]
    if isinstance(redacted, str):
        return _DIRECT_SECRET_VALUE_RE.sub("[REDACTED]", redacted)
    return redacted


def _safe_text(value: Any, *, limit: int) -> str:
    text = str(_redact_value(value) or "").strip()
    return text[:limit]


def _safe_identifier(value: Any) -> str | None:
    candidate = str(value or "").strip()
    return candidate if _IDENTIFIER_RE.fullmatch(candidate) else None


def _safe_digest_value(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    return candidate if re.fullmatch(r"[a-f0-9]{64}", candidate) else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) and value > 0 else None


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
