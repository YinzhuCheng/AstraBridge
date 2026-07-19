from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from .common import new_id, now_iso


_BREAKER_FAILURE_CATEGORIES = {
    "provider_timeout",
    "rate_limit",
    "provider_5xx",
    "transport_failure",
}


@dataclass(frozen=True)
class GraphDispatchRequest:
    run_id: str
    node_id: str
    workspace_id: str
    provider_id: str
    model_id: str


class GraphDispatchController:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_tokens: dict[str, dict[str, Any]] = {}
        self._retry_usage: dict[tuple[str, str, str], int] = {}
        self._breakers: dict[tuple[str, str], dict[str, Any]] = {}

    def try_acquire(self, request: GraphDispatchRequest, *, limits: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        with self._lock:
            breaker = self._breaker_gate_locked(request=request, limits=limits)
            if breaker is not None:
                return None, breaker

            active = list(self._active_tokens.values())
            global_limit = max(0, int(limits.get("max_active_nodes") or 0))
            reserved_interactive = max(0, int(limits.get("reserved_interactive_slots") or 0))
            graph_global_limit = max(0, global_limit - reserved_interactive)
            provider_limit = max(0, int(limits.get("max_provider_active_nodes") or 0))
            model_limit = max(0, int(limits.get("max_model_active_nodes") or 0))
            workspace_limit = max(0, int(limits.get("max_workspace_active_nodes") or 0))

            global_in_use = len(active)
            provider_in_use = sum(1 for item in active if str(item.get("provider_id") or "") == request.provider_id)
            model_in_use = sum(
                1
                for item in active
                if str(item.get("provider_id") or "") == request.provider_id and str(item.get("model_id") or "") == request.model_id
            )
            workspace_in_use = sum(1 for item in active if str(item.get("workspace_id") or "") == request.workspace_id)

            if graph_global_limit <= 0:
                return None, {"status": "denied", "reason": "global_limit", "limit": graph_global_limit}
            if global_in_use >= graph_global_limit:
                return None, {"status": "denied", "reason": "global_limit", "limit": graph_global_limit}
            if provider_limit > 0 and provider_in_use >= provider_limit:
                return None, {"status": "denied", "reason": "provider_limit", "limit": provider_limit}
            if model_limit > 0 and model_in_use >= model_limit:
                return None, {"status": "denied", "reason": "model_limit", "limit": model_limit}
            if workspace_limit > 0 and workspace_in_use >= workspace_limit:
                return None, {"status": "denied", "reason": "workspace_limit", "limit": workspace_limit}

            token = new_id("graph-dispatch-slot")
            self._active_tokens[token] = {
                "token": token,
                "run_id": request.run_id,
                "node_id": request.node_id,
                "workspace_id": request.workspace_id,
                "provider_id": request.provider_id,
                "model_id": request.model_id,
                "acquired_at": now_iso(),
            }
            return token, {
                "status": "acquired",
                "token": token,
                "global_in_use": global_in_use + 1,
                "graph_global_limit": graph_global_limit,
            }

    def release(self, token: str | None) -> None:
        clean_token = str(token or "").strip()
        if not clean_token:
            return
        with self._lock:
            self._active_tokens.pop(clean_token, None)

    def record_success(self, request: GraphDispatchRequest) -> None:
        scope = (request.provider_id, request.model_id)
        with self._lock:
            breaker = self._breakers.get(scope)
            if breaker is None:
                return
            breaker.update(
                {
                    "state": "closed",
                    "opened_at": None,
                    "reopen_at": None,
                    "last_success_at": now_iso(),
                    "consecutive_failures": 0,
                    "last_failure_category": None,
                    "last_failure_message": None,
                }
            )

    def record_failure(
        self,
        request: GraphDispatchRequest,
        *,
        category: str,
        message: str | None,
        limits: dict[str, Any],
    ) -> dict[str, Any]:
        scope = (request.provider_id, request.model_id)
        threshold = max(1, int(limits.get("breaker_failure_threshold") or 1))
        cooldown_seconds = max(1.0, float(limits.get("breaker_cooldown_seconds") or 1.0))
        with self._lock:
            breaker = self._breakers.setdefault(
                scope,
                {
                    "provider_id": request.provider_id,
                    "model_id": request.model_id,
                    "state": "closed",
                    "consecutive_failures": 0,
                    "opened_at": None,
                    "reopen_at": None,
                    "last_failure_category": None,
                    "last_failure_message": None,
                    "last_success_at": None,
                },
            )
            if category not in _BREAKER_FAILURE_CATEGORIES:
                return dict(breaker)
            breaker["consecutive_failures"] = int(breaker.get("consecutive_failures") or 0) + 1
            breaker["last_failure_category"] = category
            breaker["last_failure_message"] = str(message or "")[:240] or None
            if int(breaker["consecutive_failures"]) >= threshold:
                breaker["state"] = "open"
                breaker["opened_at"] = now_iso()
                breaker["reopen_at"] = time.monotonic() + cooldown_seconds
            return dict(breaker)

    def consume_retry_budget(self, request: GraphDispatchRequest, *, limits: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        max_retry_events = max(0, int(limits.get("retry_budget_max") or 0))
        scope = (request.run_id, request.provider_id, request.model_id)
        with self._lock:
            used = int(self._retry_usage.get(scope) or 0)
            if used >= max_retry_events:
                return False, {"allowed": False, "used": used, "limit": max_retry_events}
            self._retry_usage[scope] = used + 1
            return True, {"allowed": True, "used": used + 1, "limit": max_retry_events}

    def clear_run(self, run_id: str) -> None:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            return
        with self._lock:
            self._active_tokens = {
                token: value
                for token, value in self._active_tokens.items()
                if str(value.get("run_id") or "") != clean_run_id
            }
            self._retry_usage = {
                key: value
                for key, value in self._retry_usage.items()
                if str(key[0] or "") != clean_run_id
            }

    def status(self) -> dict[str, Any]:
        with self._lock:
            active = [dict(item) for item in self._active_tokens.values()]
            breakers = [
                {
                    "provider_id": str(item.get("provider_id") or ""),
                    "model_id": str(item.get("model_id") or ""),
                    "state": str(item.get("state") or "closed"),
                    "consecutive_failures": int(item.get("consecutive_failures") or 0),
                    "opened_at": item.get("opened_at"),
                    "last_success_at": item.get("last_success_at"),
                    "last_failure_category": item.get("last_failure_category"),
                    "cooldown_active": bool(
                        str(item.get("state") or "") == "open"
                        and isinstance(item.get("reopen_at"), (int, float))
                        and float(item.get("reopen_at") or 0.0) > time.monotonic()
                    ),
                }
                for item in self._breakers.values()
            ]
            breakers.sort(key=lambda item: (item["provider_id"], item["model_id"]))
            return {
                "active_dispatch_count": len(active),
                "active_dispatches": [
                    {
                        "run_id": str(item.get("run_id") or ""),
                        "node_id": str(item.get("node_id") or ""),
                        "workspace_id": str(item.get("workspace_id") or ""),
                        "provider_id": str(item.get("provider_id") or ""),
                        "model_id": str(item.get("model_id") or ""),
                        "acquired_at": item.get("acquired_at"),
                    }
                    for item in active
                ],
                "circuit_breakers": breakers,
            }

    def _breaker_gate_locked(self, *, request: GraphDispatchRequest, limits: dict[str, Any]) -> dict[str, Any] | None:
        scope = (request.provider_id, request.model_id)
        breaker = self._breakers.get(scope)
        if breaker is None:
            return None
        if str(breaker.get("state") or "") != "open":
            return None
        reopen_at = breaker.get("reopen_at")
        if not isinstance(reopen_at, (int, float)):
            return None
        if float(reopen_at) <= time.monotonic():
            breaker["state"] = "closed"
            breaker["consecutive_failures"] = 0
            breaker["opened_at"] = None
            breaker["reopen_at"] = None
            return None
        return {
            "status": "denied",
            "reason": "circuit_open",
            "provider_id": request.provider_id,
            "model_id": request.model_id,
            "last_failure_category": breaker.get("last_failure_category"),
        }


__all__ = ["GraphDispatchController", "GraphDispatchRequest"]
