"""Isolated, lifecycle-aware client lanes for provider runtimes.

The app-server client is stateful: its process, environment, request ids, and
notification callbacks belong to one provider/model runtime.  A single global
client therefore cannot safely serve a provider handoff while another turn is
still running.  This module owns the small amount of concurrency machinery
needed to keep those lifetimes independent.

Only a one-way digest of a runtime signature is retained by the pool.  The
signature may contain a secret fingerprint or other sensitive configuration,
but lane keys and snapshots never expose those values.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Hashable


ClientFactory = Callable[[], Any]


def _canonicalize(value: Any) -> Any:
    """Return a deterministic, JSON-safe value for hashing only.

    Raw values are never stored in a ``RuntimeLaneKey``.  The recursive
    conversion keeps tuple/list and mapping order semantics stable while
    avoiding ``repr`` output, which could accidentally include credentials.
    """

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=lambda item: str(item))}
    return {"type": type(value).__name__}


@dataclass(frozen=True)
class RuntimeLaneKey:
    """Opaque immutable identity for one runtime lane."""

    digest: str

    @classmethod
    def from_signature(cls, signature: Any) -> "RuntimeLaneKey":
        canonical = json.dumps(_canonicalize(signature), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return cls(hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32])

    @property
    def lane_id(self) -> str:
        return f"lane-{self.digest[:16]}"


@dataclass(frozen=True)
class RuntimeLaneSnapshot:
    lane_id: str
    active_leases: int
    request_slots_in_use: int
    created_at: float
    last_used_at: float
    running: bool
    retiring: bool
    restart_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "active_leases": self.active_leases,
            "request_slots_in_use": self.request_slots_in_use,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "running": self.running,
            "retiring": self.retiring,
            "restart_count": self.restart_count,
        }


class _RuntimeLane:
    def __init__(self, key: RuntimeLaneKey, *, concurrency_limit: int) -> None:
        self.key = key
        self.client: Any | None = None
        self.lock = threading.RLock()
        self.slot_condition = threading.Condition(self.lock)
        self.concurrency_limit = max(1, int(concurrency_limit))
        self.active_leases = 0
        self.request_slots_in_use = 0
        self.created_at = time.monotonic()
        self.last_used_at = self.created_at
        self.retiring = False
        self.restart_count = 0
        self.created_once = False
        self.close_when_idle = False

    def ensure_client(self, factory: ClientFactory, *, max_restarts: int) -> Any:
        with self.lock:
            if self.client is not None and self._is_running(self.client) and not self.retiring:
                self.last_used_at = time.monotonic()
                return self.client
            if self.client is not None:
                self._close_now_locked()
            if self.created_once and self.restart_count >= max(0, int(max_restarts)):
                raise RuntimeError("runtime_client_lane_restart_limit_exceeded")
            client = factory()
            self.client = client
            if self.created_once:
                self.restart_count += 1
            else:
                self.created_once = True
            self.last_used_at = time.monotonic()
            return client

    def acquire(self, factory: ClientFactory, *, timeout: float | None, max_restarts: int) -> "RuntimeClientLease":
        deadline = None if timeout is None else time.monotonic() + max(0.0, float(timeout))
        with self.slot_condition:
            while self.request_slots_in_use >= self.concurrency_limit:
                if deadline is None:
                    self.slot_condition.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("runtime_client_lane_concurrency_limit")
                self.slot_condition.wait(remaining)
            client = self.ensure_client(factory, max_restarts=max_restarts)
            self.request_slots_in_use += 1
            self.active_leases += 1
            self.last_used_at = time.monotonic()
            return RuntimeClientLease(self, client)

    def release(self) -> None:
        with self.slot_condition:
            if self.active_leases > 0:
                self.active_leases -= 1
            if self.request_slots_in_use > 0:
                self.request_slots_in_use -= 1
            self.last_used_at = time.monotonic()
            if self.active_leases == 0 and self.close_when_idle:
                self._close_now_locked()
            self.slot_condition.notify_all()

    def close(self, *, force: bool) -> Any | None:
        with self.slot_condition:
            self.retiring = True
            if self.active_leases and not force:
                self.close_when_idle = True
                return None
            return self._close_now_locked()

    def snapshot(self) -> RuntimeLaneSnapshot:
        with self.lock:
            client = self.client
            running = bool(client is not None and self._is_running(client))
            return RuntimeLaneSnapshot(
                lane_id=self.key.lane_id,
                active_leases=self.active_leases,
                request_slots_in_use=self.request_slots_in_use,
                created_at=self.created_at,
                last_used_at=self.last_used_at,
                running=running,
                retiring=self.retiring,
                restart_count=self.restart_count,
            )

    def _close_now_locked(self) -> Any | None:
        client = self.client
        self.client = None
        self.close_when_idle = False
        if client is not None:
            try:
                client.close()
            except Exception:
                # Shutdown/reaping must not strand the pool lock because a
                # third-party client may already have lost its subprocess.
                pass
        return client

    @staticmethod
    def _is_running(client: Any) -> bool:
        probe = getattr(client, "is_running", None)
        if not callable(probe):
            return True
        try:
            return bool(probe())
        except Exception:
            return False


class RuntimeClientLease:
    """A bounded active-turn lease for one lane client."""

    def __init__(self, lane: _RuntimeLane, client: Any) -> None:
        self._lane = lane
        self.client = client
        self._released = False

    @property
    def lane_id(self) -> str:
        return self._lane.key.lane_id

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._lane.release()

    def __enter__(self) -> "RuntimeClientLease":
        return self

    def __exit__(self, _exc_type: Any, _exc_value: Any, _traceback: Any) -> None:
        self.release()


class RuntimeClientPool:
    """Thread-safe registry of independently managed runtime client lanes."""

    def __init__(
        self,
        *,
        max_lanes: int = 8,
        idle_ttl_seconds: float = 300.0,
        concurrency_limit: int = 8,
        max_restarts: int = 3,
    ) -> None:
        self.max_lanes = max(1, int(max_lanes))
        self.idle_ttl_seconds = max(0.0, float(idle_ttl_seconds))
        self.concurrency_limit = max(1, int(concurrency_limit))
        self.max_restarts = max(0, int(max_restarts))
        self._lock = threading.RLock()
        self._lanes: dict[RuntimeLaneKey, _RuntimeLane] = {}

    @staticmethod
    def key_for(signature: Any) -> RuntimeLaneKey:
        return RuntimeLaneKey.from_signature(signature)

    @staticmethod
    def lane_id_for(signature: Any) -> str:
        return RuntimeLaneKey.from_signature(signature).lane_id

    def get_or_create(self, signature: Any, factory: ClientFactory) -> Any:
        key = self.key_for(signature)
        with self._lock:
            self._reap_idle_locked()
            lane = self._lanes.get(key)
            if lane is None:
                self._evict_for_capacity_locked()
                lane = _RuntimeLane(key, concurrency_limit=self.concurrency_limit)
                self._lanes[key] = lane
            try:
                return lane.ensure_client(factory, max_restarts=self.max_restarts)
            except Exception:
                if self._lanes.get(key) is lane and lane.active_leases == 0:
                    self._lanes.pop(key, None)
                raise

    def acquire(self, signature: Any, factory: ClientFactory, *, timeout: float | None = None) -> RuntimeClientLease:
        key = self.key_for(signature)
        with self._lock:
            self._reap_idle_locked()
            lane = self._lanes.get(key)
            if lane is None:
                self._evict_for_capacity_locked()
                lane = _RuntimeLane(key, concurrency_limit=self.concurrency_limit)
                self._lanes[key] = lane
            try:
                return lane.acquire(factory, timeout=timeout, max_restarts=self.max_restarts)
            except Exception:
                if self._lanes.get(key) is lane and lane.active_leases == 0 and lane.client is None:
                    self._lanes.pop(key, None)
                raise

    def has_lane(self, signature: Any) -> bool:
        key = self.key_for(signature)
        with self._lock:
            return key in self._lanes

    def close_lane(self, signature: Any, *, force: bool = False) -> Any | None:
        key = self.key_for(signature)
        with self._lock:
            lane = self._lanes.pop(key, None)
        if lane is None:
            return None
        return lane.close(force=force)

    def reap_idle(self, *, now: float | None = None) -> list[str]:
        with self._lock:
            return self._reap_idle_locked(now=now)

    def shutdown(self) -> list[str]:
        with self._lock:
            lanes = list(self._lanes.values())
            self._lanes.clear()
        closed: list[str] = []
        for lane in lanes:
            lane.close(force=True)
            closed.append(lane.key.lane_id)
        return closed

    def snapshots(self) -> list[dict[str, Any]]:
        with self._lock:
            lanes = list(self._lanes.values())
        return [lane.snapshot().as_dict() for lane in sorted(lanes, key=lambda item: item.key.lane_id)]

    def _reap_idle_locked(self, *, now: float | None = None) -> list[str]:
        current = time.monotonic() if now is None else float(now)
        candidates: list[tuple[RuntimeLaneKey, _RuntimeLane]] = []
        for key, lane in self._lanes.items():
            snapshot = lane.snapshot()
            if snapshot.active_leases == 0 and current - snapshot.last_used_at >= self.idle_ttl_seconds:
                candidates.append((key, lane))
        for key, lane in candidates:
            self._lanes.pop(key, None)
            lane.close(force=False)
        return [key.lane_id for key, _lane in candidates]

    def _evict_for_capacity_locked(self) -> None:
        if len(self._lanes) < self.max_lanes:
            return
        idle = sorted(
            (
                lane.snapshot().last_used_at,
                key,
                lane,
            )
            for key, lane in self._lanes.items()
            if lane.snapshot().active_leases == 0
        )
        if not idle:
            raise RuntimeError("runtime_client_lane_capacity_exhausted")
        _last_used, key, lane = idle[0]
        self._lanes.pop(key, None)
        lane.close(force=False)


__all__ = [
    "RuntimeClientLease",
    "RuntimeClientPool",
    "RuntimeLaneKey",
    "RuntimeLaneSnapshot",
]
