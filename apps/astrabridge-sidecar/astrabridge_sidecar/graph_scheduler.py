from __future__ import annotations

from collections import deque
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from .common import new_id, now_iso
from .security import redact_sensitive


GraphExecutionCallback = Callable[[str, dict[str, Any]], Any]


@dataclass
class _SchedulerJob:
    run_id: str
    status: str
    created_at: str
    updated_at: str
    requested_parallelism: int = 1
    owner_id: str = ""
    cancel_reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    result_status: str | None = None
    done: threading.Event = field(default_factory=threading.Event, repr=False)

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "requested_parallelism": self.requested_parallelism,
            "owner_id": self.owner_id,
            "cancel_reason": self.cancel_reason,
            "error": self.error,
            "result_status": self.result_status,
        }


class DurableGraphScheduler:
    """Small process-local dispatch loop for durable graph run receipts.

    The scheduler intentionally keeps only redacted job metadata in memory.
    The graph payload is handed to the callback and is never returned from a
    status endpoint.  The callback is the sole live-run advancement path; the
    durable run store remains the authoritative state source.
    """

    def __init__(
        self,
        callback: GraphExecutionCallback,
        *,
        max_workers: int = 4,
        max_queue_size: int = 128,
        owner_id: str | None = None,
    ) -> None:
        if not callable(callback):
            raise TypeError("A graph execution callback is required.")
        self._callback = callback
        self._max_workers = max(1, int(max_workers))
        self._max_queue_size = max(1, int(max_queue_size))
        self._owner_id = str(owner_id or new_id("graph-scheduler")).strip()
        self._queue: deque[tuple[str, dict[str, Any]] | None] = deque()
        self._queue_condition = threading.Condition()
        self._jobs: dict[str, _SchedulerJob] = {}
        self._lock = threading.RLock()
        self._accepting = True
        self._started_at = now_iso()
        self._workers: list[threading.Thread] = []

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def submit(
        self,
        run_id: str,
        payload: dict[str, Any],
        *,
        max_parallelism: int = 1,
    ) -> dict[str, Any]:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            raise ValueError("run_id is required for scheduler submission.")
        if not isinstance(payload, dict):
            raise TypeError("Scheduler payload must be a dict.")
        with self._lock:
            existing = self._jobs.get(clean_run_id)
            if existing is not None:
                return existing.snapshot()
            if not self._accepting:
                raise RuntimeError("Graph scheduler is shutting down.")
            queued_jobs = sum(1 for item in self._jobs.values() if item.status == "queued")
            if queued_jobs >= self._max_queue_size:
                raise RuntimeError("graph_scheduler_queue_full")
            created_at = now_iso()
            job = _SchedulerJob(
                run_id=clean_run_id,
                status="queued",
                created_at=created_at,
                updated_at=created_at,
                requested_parallelism=max(1, int(max_parallelism or 1)),
                owner_id=self._owner_id,
            )
            self._ensure_workers_locked()
            self._jobs[clean_run_id] = job
            with self._queue_condition:
                # Queue entries contain the in-memory callback payload only.  It is
                # never copied into job metadata or returned by status().
                self._queue.append((clean_run_id, dict(payload)))
                self._queue_condition.notify()
            return job.snapshot()

    def get(self, run_id: str) -> dict[str, Any] | None:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            return None
        with self._lock:
            job = self._jobs.get(clean_run_id)
            return job.snapshot() if job is not None else None

    def wait(self, run_id: str, *, timeout: float | None = None) -> dict[str, Any] | None:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            return None
        with self._lock:
            job = self._jobs.get(clean_run_id)
        if job is None:
            return None
        job.done.wait(timeout=timeout)
        return self.get(clean_run_id)

    def status(self) -> dict[str, Any]:
        with self._lock:
            jobs = [job.snapshot() for job in self._jobs.values()]
            jobs.sort(key=lambda item: (str(item.get("updated_at") or ""), str(item.get("run_id") or "")), reverse=True)
            active = [item for item in jobs if item.get("status") in {"queued", "running"}]
            return {
                "schema_version": "astrabridge-graph-scheduler-v1",
                "running": bool(self._accepting),
                "owner_id": self._owner_id,
                "started_at": self._started_at,
                "max_workers": self._max_workers,
                "max_queue_size": self._max_queue_size,
                "active_job_count": len(active),
                "queued_job_ids": [str(item["run_id"]) for item in active if item.get("status") == "queued"],
                "running_job_ids": [str(item["run_id"]) for item in active if item.get("status") == "running"],
                "jobs": jobs[:100],
            }

    def cancel(self, run_id: str, *, reason: str = "cancelled") -> dict[str, Any] | None:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            return None
        with self._lock:
            job = self._jobs.get(clean_run_id)
            if job is None:
                return None
            if job.status != "queued":
                return job.snapshot()
            finished_at = now_iso()
            job.status = "cancelled"
            job.result_status = "cancelled"
            job.cancel_reason = str(reason or "cancelled")[:120]
            job.finished_at = finished_at
            job.updated_at = finished_at
            job.done.set()
            return job.snapshot()

    def shutdown(self, *, wait: bool = False) -> None:
        with self._lock:
            if not self._accepting:
                return
            self._accepting = False
        with self._queue_condition:
            for _ in self._workers:
                self._queue.append(None)
            self._queue_condition.notify_all()
        if wait:
            for worker in self._workers:
                worker.join(timeout=5.0)

    def _ensure_workers_locked(self) -> None:
        if self._workers:
            return
        for index in range(self._max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"astrabridge-graph-scheduler-{index + 1}",
                daemon=True,
            )
            self._workers.append(worker)
            worker.start()

    def _worker_loop(self) -> None:
        while True:
            with self._queue_condition:
                while not self._queue:
                    self._queue_condition.wait()
                item = self._queue.popleft()
            if item is None:
                return
            run_id, payload = item
            with self._lock:
                job = self._jobs.get(run_id)
                if job is None:
                    continue
                if job.status == "cancelled":
                    continue
                started_at = now_iso()
                job.status = "running"
                job.started_at = started_at
                job.updated_at = started_at
            try:
                result = self._callback(run_id, payload)
            except Exception as exc:  # noqa: BLE001
                finished_at = now_iso()
                with self._lock:
                    job = self._jobs.get(run_id)
                    if job is not None:
                        job.status = "failed"
                        job.finished_at = finished_at
                        job.updated_at = finished_at
                        job.error = str(redact_sensitive(str(exc) or type(exc).__name__))[:500]
                        job.done.set()
            else:
                finished_at = now_iso()
                result_status = None
                if isinstance(result, dict):
                    live_run = result.get("live_run")
                    if isinstance(live_run, dict):
                        result_status = str(live_run.get("run_status") or "").strip() or None
                with self._lock:
                    job = self._jobs.get(run_id)
                    if job is not None:
                        job.status = "completed"
                        job.finished_at = finished_at
                        job.updated_at = finished_at
                        job.result_status = result_status
                        job.done.set()
