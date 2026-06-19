from __future__ import annotations

import threading
from typing import Any, Callable

from .common import append_jsonl, new_id, now_iso
from .security import redact_sensitive


class ModalService:
    def __init__(self, shell_state_root_provider: Callable[[], Any], timeout_seconds: float = 3600.0) -> None:
        self._shell_state_root_provider = shell_state_root_provider
        self._timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}

    def list_pending(self) -> dict[str, Any]:
        with self._lock:
            modals = [self._public_modal(item) for item in self._pending.values()]
        modals.sort(key=lambda item: item["created_at"])
        return {"modals": modals}

    def cancel_for_turn(self, thread_id: str, turn_id: str | None = None, reason: str = "Turn was interrupted.") -> list[dict[str, Any]]:
        """Resolve pending modals for an interrupted turn so the UI does not show stale approvals."""
        resolved: list[dict[str, Any]] = []
        thread_id = str(thread_id or "").strip()
        turn_id = str(turn_id or "").strip()
        with self._lock:
            for modal_id, modal in list(self._pending.items()):
                if thread_id and str(modal.get("thread_id") or "") != thread_id:
                    continue
                if turn_id and str(modal.get("turn_id") or "") != turn_id:
                    continue
                resolution = self._cancel_resolution(str(modal.get("method") or ""), reason)
                modal["resolution"] = resolution
                modal["resolved_at"] = now_iso()
                modal["status"] = "resolved"
                modal["event"].set()
                public = self._public_modal(modal)
                resolved.append(public)
                self._pending.pop(modal_id, None)
        for public in resolved:
            self._record({"type": "modal_auto_cancelled", "modal": public})
        return resolved

    def resolve(self, modal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            modal = self._pending.get(modal_id)
            if modal is None:
                raise ValueError(f"Unknown modal: {modal_id}")
            modal["resolution"] = payload
            modal["resolved_at"] = now_iso()
            modal["status"] = "resolved"
            modal["event"].set()
            public = self._public_modal(modal)
            if modal.get("synthetic"):
                self._pending.pop(modal_id, None)
        self._record({"type": "modal_resolved", "modal": public})
        return public

    def create_fake(self, kind: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        method, defaults = self._fake_modal_template(kind)
        merged = {**defaults, **dict(params or {})}
        modal_id = new_id("MODAL")
        modal = {
            "modal_id": modal_id,
            "kind": self._modal_kind(method),
            "method": method,
            "params": redact_sensitive(merged),
            "thread_id": self._extract(merged, "threadId"),
            "turn_id": self._extract(merged, "turnId"),
            "item_id": self._extract(merged, "itemId"),
            "status": "pending",
            "created_at": now_iso(),
            "event": threading.Event(),
            "resolution": None,
            "synthetic": True,
        }
        with self._lock:
            self._pending[modal_id] = modal
        public = self._public_modal(modal)
        self._record({"type": "modal_requested", "modal": public, "synthetic": True})
        return public

    def request(self, method: str, params: Any) -> Any:
        modal_id = new_id("MODAL")
        event = threading.Event()
        modal = {
            "modal_id": modal_id,
            "kind": self._modal_kind(method),
            "method": method,
            "params": redact_sensitive(params),
            "thread_id": self._extract(params, "threadId"),
            "turn_id": self._extract(params, "turnId"),
            "item_id": self._extract(params, "itemId"),
            "status": "pending",
            "created_at": now_iso(),
            "event": event,
            "resolution": None,
        }
        with self._lock:
            self._pending[modal_id] = modal
        self._record({"type": "modal_requested", "modal": self._public_modal(modal)})
        event.wait(self._timeout_seconds)
        with self._lock:
            current = self._pending.pop(modal_id, modal)
        resolution = current.get("resolution") or self._default_resolution(method, params)
        public = self._public_modal({**current, "status": "resolved", "resolved_at": now_iso(), "resolution": resolution})
        self._record({"type": "modal_completed", "modal": public})
        return self._translate_resolution(method, params, resolution)

    def _public_modal(self, modal: dict[str, Any]) -> dict[str, Any]:
        return {
            "modal_id": modal["modal_id"],
            "kind": modal["kind"],
            "method": modal["method"],
            "thread_id": modal.get("thread_id"),
            "turn_id": modal.get("turn_id"),
            "item_id": modal.get("item_id"),
            "status": modal.get("status"),
            "created_at": modal.get("created_at"),
            "resolved_at": modal.get("resolved_at"),
            "params": modal.get("params"),
            "resolution": redact_sensitive(modal.get("resolution")),
        }

    def _default_resolution(self, method: str, params: Any) -> dict[str, Any]:
        if method == "item/tool/requestUserInput":
            questions = list((params or {}).get("questions") or [])
            return {
                "answers": {
                    str(question.get("id")): {"answers": []}
                    for question in questions
                    if str(question.get("id") or "").strip()
                }
            }
        if method == "item/permissions/requestApproval":
            return {"decision": "decline", "scope": "turn"}
        if method == "mcpServer/elicitation/request":
            return {"action": "decline", "content": None, "_meta": None}
        return {"decision": "decline"}

    def _cancel_resolution(self, method: str, reason: str) -> dict[str, Any]:
        if method == "item/tool/requestUserInput":
            return {"answers": {}, "reason": reason}
        if method == "item/permissions/requestApproval":
            return {"decision": "decline", "scope": "turn", "reason": reason}
        if method == "mcpServer/elicitation/request":
            return {"action": "cancel", "content": None, "_meta": {"reason": reason}}
        return {"decision": "cancel", "reason": reason}

    def _translate_resolution(self, method: str, params: Any, resolution: dict[str, Any]) -> Any:
        if method == "item/tool/requestUserInput":
            answers = resolution.get("answers") or {}
            return {"answers": answers}
        if method == "item/permissions/requestApproval":
            decision = str(resolution.get("decision") or "decline")
            if decision != "approve":
                return {"permissions": {}, "scope": str(resolution.get("scope") or "turn")}
            return {
                "permissions": resolution.get("permissions") or (params or {}).get("permissions") or {},
                "scope": str(resolution.get("scope") or "turn"),
                "strictAutoReview": bool(resolution.get("strict_auto_review", False)),
            }
        if method in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
            decision = str(resolution.get("decision") or "decline")
            if decision in {
                "accept_with_execpolicy_amendment",
                "acceptWithExecpolicyAmendment",
                "approve_execpolicy_amendment",
            }:
                amendment = (
                    resolution.get("execpolicy_amendment")
                    or resolution.get("proposedExecpolicyAmendment")
                    or self._extract_execpolicy_amendment(params)
                )
                if amendment:
                    return {"decision": {"acceptWithExecpolicyAmendment": {"execpolicy_amendment": amendment}}}
                return {"decision": "accept"}
            translated = {
                "accept": "accept",
                "approve": "accept",
                "accept_for_session": "acceptForSession",
                "approve_session": "acceptForSession",
                "decline": "decline",
                "cancel": "cancel",
            }.get(decision, "decline")
            return {"decision": translated}
        if method in {"applyPatchApproval", "execCommandApproval"}:
            decision = str(resolution.get("decision") or "decline")
            translated = {
                "approve": "approved",
                "approve_session": "approved_for_session",
                "decline": "denied",
                "cancel": "abort",
            }.get(decision, "denied")
            return {"decision": translated}
        if method == "mcpServer/elicitation/request":
            action = str(resolution.get("action") or resolution.get("decision") or "decline")
            if action not in {"accept", "decline", "cancel"}:
                action = "decline"
            return {
                "action": action,
                "content": resolution.get("content") if action == "accept" else None,
                "_meta": resolution.get("_meta"),
            }
        raise ValueError(f"Unsupported modal method: {method}")

    def _record(self, payload: dict[str, Any]) -> None:
        try:
            append_jsonl(self._shell_state_root_provider() / "approvals.jsonl", payload)
        except Exception:
            pass

    def _modal_kind(self, method: str) -> str:
        if method == "item/tool/requestUserInput":
            return "user_input"
        if method == "mcpServer/elicitation/request":
            return "mcp_elicitation"
        return "approval"

    def _extract(self, params: Any, key: str) -> str | None:
        if isinstance(params, dict):
            value = params.get(key)
            return str(value) if value is not None else None
        return None

    def _extract_execpolicy_amendment(self, params: Any) -> Any:
        if not isinstance(params, dict):
            return None
        direct = params.get("proposedExecpolicyAmendment")
        if direct:
            return direct
        for decision in params.get("availableDecisions") or []:
            if not isinstance(decision, dict):
                continue
            amendment = decision.get("acceptWithExecpolicyAmendment")
            if isinstance(amendment, dict) and amendment.get("execpolicy_amendment"):
                return amendment.get("execpolicy_amendment")
        return None

    def _fake_modal_template(self, kind: str) -> tuple[str, dict[str, Any]]:
        normalized = str(kind or "").strip().lower().replace("-", "_")
        common = {"threadId": "fake-thread", "turnId": "fake-turn", "itemId": new_id("ITEM")}
        if normalized in {"user_input", "request_user_input", "input"}:
            return (
                "item/tool/requestUserInput",
                {
                    **common,
                    "questions": [
                        {
                            "id": "path",
                            "header": "Next step",
                            "question": "Which safe validation path should AstraBridge take next?",
                            "options": [
                                {"label": "Run smoke test", "description": "Recommended: verify the current UI path with no provider spend."},
                                {"label": "Inspect logs", "description": "Read summarized runtime state before continuing."},
                            ],
                        }
                    ],
                },
            )
        if normalized in {"approval_readonly", "readonly", "read"}:
            return (
                "item/commandExecution/requestApproval",
                {
                    **common,
                    "cwd": "D:\\workflow",
                    "command": "Get-ChildItem -LiteralPath D:\\workflow -Force | Select-Object -First 20",
                    "reason": "Smoke check for a read-only approval modal.",
                },
            )
        if normalized in {"approval_write", "write", "encoding"}:
            return (
                "item/commandExecution/requestApproval",
                {
                    **common,
                    "cwd": "D:\\workflow",
                    "command": "Set-Content -Path D:\\workflow\\lcr-approval-smoke.txt -Value 'hello'",
                    "reason": "Smoke check for a Windows write command that should warn about explicit UTF-8 encoding.",
                },
            )
        if normalized in {"lcr_log_read", "runtime_log", "approvals_log"}:
            return (
                "item/commandExecution/requestApproval",
                {
                    **common,
                    "cwd": "D:\\workflow",
                    "command": "Get-Content -Path .lcr\\runtime_events.jsonl -Tail 200; Get-Content -Path .lcr\\approvals.jsonl -Tail 200",
                    "reason": "Smoke check for raw .lcr log reads; the UI should recommend summaries instead of raw logs.",
                },
            )
        if normalized in {"permission", "permissions"}:
            return (
                "item/permissions/requestApproval",
                {
                    **common,
                    "permissions": {"sandbox": "workspace-write", "network": False},
                    "reason": "Smoke check for runtime permission approval.",
                },
            )
        raise ValueError(f"Unsupported fake modal kind: {kind}")

