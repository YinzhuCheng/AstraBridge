from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from .common import append_jsonl, now_iso
from .security import classify_command


class ApprovalService:
    def __init__(self, timeout_seconds: float = 600.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._pending: dict[str, dict[str, Any]] = {}
        self._decisions: dict[str, dict[str, Any]] = {}
        self._waiters: dict[str, "queue.Queue[dict[str, Any]]"] = {}
        self._events: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._lock = threading.Lock()

    def request_approval(self, project_root: Path | None, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        params = params or {}
        approval_id = str(params.get("approvalId") or params.get("itemId") or f"APR-{len(self._pending) + 1:04d}")
        command = params.get("command")
        risk = classify_command(command, params.get("cwd")) if isinstance(command, str) else {
            "risk": "medium",
            "decision": "requires_confirmation",
            "reason": "File, permission, or tool approval requires user confirmation.",
        }
        record = {
            "approval_id": approval_id,
            "method": method,
            "params": params,
            "risk": risk,
            "project_root": str(project_root) if project_root else None,
            "created_at": now_iso(),
            "status": "pending",
        }
        waiter: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize=1)
        with self._lock:
            self._pending[approval_id] = record
            self._waiters[approval_id] = waiter
        self._events.put({"type": "approval_requested", "approval": self._sanitize(record)})
        if project_root:
            append_jsonl(project_root / ".research-os" / "approvals.jsonl", self._sanitize(record))
        try:
            decision = waiter.get(timeout=self.timeout_seconds)
            if decision["decision"] == "accept":
                return {"decision": "accept"}
            return {"decision": decision["decision"]}
        except queue.Empty:
            self.decide(approval_id, "decline", "Timed out waiting for Research OS UI approval.")
            return {"decision": "decline", "reason": "Timed out waiting for Research OS UI approval."}

    def list_pending(self) -> dict[str, Any]:
        return {"approvals": [self._sanitize(item) for item in self._pending.values()]}

    def decide(self, approval_id: str, decision: str, notes: str = "") -> dict[str, Any]:
        with self._lock:
            if approval_id not in self._pending:
                raise ValueError(f"Unknown approval_id: {approval_id}")
            record = self._pending.pop(approval_id)
            waiter = self._waiters.pop(approval_id, None)
        if decision not in {"accept", "decline", "cancel"}:
            raise ValueError("decision must be accept, decline, or cancel.")
        resolved = {
            **record,
            "status": "resolved",
            "decision": decision,
            "notes": notes,
            "resolved_at": now_iso(),
        }
        self._decisions[approval_id] = resolved
        self._events.put({"type": "approval_resolved", "approval": self._sanitize(resolved)})
        if waiter:
            waiter.put({"decision": decision, "notes": notes})
        return self._sanitize(resolved)

    def drain_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def _sanitize(self, record: dict[str, Any]) -> dict[str, Any]:
        clean = dict(record)
        params = dict(clean.get("params") or {})
        for key in list(params):
            if any(secret in key.lower() for secret in ["token", "secret", "api_key", "authorization", "cookie"]):
                params[key] = "[redacted]"
        clean["params"] = params
        return clean

