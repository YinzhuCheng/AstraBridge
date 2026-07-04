from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ..common import now_iso
from .store import AutomationStore


UTC = dt.timezone.utc


def _parse_iso(value: str | None) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _future_daily_occurrence(*, now_utc: dt.datetime, expression: str, timezone_name: str) -> dt.datetime:
    timezone = ZoneInfo(timezone_name)
    local_now = now_utc.astimezone(timezone)
    hour = int(expression[:2])
    minute = int(expression[3:])
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate < local_now:
        candidate = candidate + dt.timedelta(days=1)
    return candidate.astimezone(UTC)


@dataclass(frozen=True)
class SchedulerTickResult:
    queued_run_ids: list[str]
    skipped_automation_ids: list[str]
    recovered_run_ids: list[str]
    next_wake_up_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "queued_run_ids": list(self.queued_run_ids),
            "skipped_automation_ids": list(self.skipped_automation_ids),
            "recovered_run_ids": list(self.recovered_run_ids),
            "next_wake_up_at": self.next_wake_up_at,
        }


class AutomationScheduler:
    def __init__(
        self,
        store: AutomationStore,
        *,
        now_fn: Callable[[], dt.datetime] | None = None,
        stale_after: dt.timedelta | None = None,
        max_active_runs: int = 1,
    ) -> None:
        self._store = store
        self._now_fn = now_fn or (lambda: dt.datetime.now(UTC))
        self._stale_after = stale_after or dt.timedelta(hours=2)
        self._max_active_runs = max(1, int(max_active_runs))
        self._running = False

    def start(self) -> dict[str, Any]:
        self._running = True
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._running = False
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "active_run_count": self._active_run_count(),
            "next_wake_up_at": self.next_wake_up_at(),
        }

    def next_wake_up_at(self) -> str | None:
        next_times: list[dt.datetime] = []
        now = self._now()
        for automation in self._store.list_automations():
            if not automation.get("enabled"):
                continue
            schedule = dict(automation.get("schedule") or {})
            if str(schedule.get("mode") or "").lower() == "manual":
                continue
            next_run = self._ensure_next_run_at(automation, now=now)
            if next_run is not None:
                next_times.append(next_run)
        for run in self._store.list_runs():
            if str(run.get("status") or "").lower() != "failed":
                continue
            next_retry_at = _parse_iso(str(run.get("next_retry_at") or ""))
            if next_retry_at is not None:
                next_times.append(next_retry_at)
        if not next_times:
            return None
        return _to_iso(min(next_times))

    def trigger_now(self, automation_id: str) -> dict[str, Any] | None:
        automation = self._store.get_automation(automation_id)
        if not automation:
            raise ValueError("Automation not found.")
        if not automation.get("enabled"):
            raise ValueError("Paused automations cannot be triggered.")
        if self._has_active_run(str(automation.get("automation_id") or "")):
            return None
        if self._active_run_count() >= self._max_active_runs:
            return None
        return self._queue_run(automation, due_at=self._now(), trigger="manual")

    def tick(self) -> dict[str, Any]:
        if not self._running:
            return SchedulerTickResult([], [], [], self.next_wake_up_at()).to_dict()
        now = self._now()
        recovered_run_ids = self._recover_stale_runs(now=now)
        queued_run_ids: list[str] = []
        skipped_automation_ids: list[str] = []

        retry_queued = self._queue_due_retries(now=now)
        queued_run_ids.extend(retry_queued)

        for automation in self._store.list_automations():
            if self._active_run_count() >= self._max_active_runs:
                break
            if not automation.get("enabled"):
                continue
            schedule = dict(automation.get("schedule") or {})
            mode = str(schedule.get("mode") or "").lower()
            if mode == "manual":
                continue
            automation_id = str(automation.get("automation_id") or "")
            due_at = self._ensure_next_run_at(automation, now=now)
            if due_at is None or due_at > now:
                continue
            if self._has_active_run(automation_id):
                continue
            if not self._under_daily_run_limit(automation, now=now):
                skipped_automation_ids.append(automation_id)
                self._advance_schedule(automation, anchor=now)
                continue
            catch_up_policy = str(schedule.get("catch_up_policy") or "skip_missed").lower()
            if due_at < now and catch_up_policy == "skip_missed":
                skipped_automation_ids.append(automation_id)
                self._advance_schedule(automation, anchor=now)
                continue
            queued = self._queue_run(automation, due_at=due_at, trigger="schedule")
            if queued:
                queued_run_ids.append(str(queued.get("run_id") or ""))
                self._advance_schedule(automation, anchor=now)
        return SchedulerTickResult(
            queued_run_ids=queued_run_ids,
            skipped_automation_ids=skipped_automation_ids,
            recovered_run_ids=recovered_run_ids,
            next_wake_up_at=self.next_wake_up_at(),
        ).to_dict()

    def _queue_run(self, automation: dict[str, Any], *, due_at: dt.datetime, trigger: str) -> dict[str, Any]:
        automation_id = str(automation.get("automation_id") or "")
        project_id = str(automation.get("project_id") or "")
        run_id = f"{automation_id}-run-{due_at.strftime('%Y%m%dT%H%M%S%f')}"
        payload = {
            "run_id": run_id,
            "automation_id": automation_id,
            "project_id": project_id,
            "trigger": trigger,
            "status": "queued",
            "due_at": _to_iso(due_at),
            "signal": "unknown",
            "summary": "queued by scheduler",
            "runtime_profile_id": (automation.get("runtime") or {}).get("profile_id"),
            "retry_count": int(automation.get("retry_count") or 0),
        }
        return self._store.record_run(payload)

    def _queue_due_retries(self, *, now: dt.datetime) -> list[str]:
        queued_run_ids: list[str] = []
        for run in self._store.list_runs():
            if self._active_run_count() >= self._max_active_runs:
                break
            if str(run.get("status") or "").lower() != "failed":
                continue
            next_retry_at = _parse_iso(str(run.get("next_retry_at") or ""))
            if next_retry_at is None or next_retry_at > now:
                continue
            automation = self._store.get_automation(str(run.get("automation_id") or ""))
            if not automation or not automation.get("enabled"):
                continue
            automation_id = str(automation.get("automation_id") or "")
            if self._has_active_run(automation_id):
                continue
            if not self._under_daily_run_limit(automation, now=now):
                continue
            retry_count = int(run.get("retry_count") or 0) + 1
            queued = self._store.record_run(
                {
                    "run_id": f"{automation_id}-retry-{now.strftime('%Y%m%dT%H%M%S%f')}",
                    "automation_id": automation_id,
                    "project_id": str(automation.get("project_id") or ""),
                    "trigger": "retry",
                    "status": "queued",
                    "due_at": _to_iso(now),
                    "signal": "unknown",
                    "summary": "queued retry by scheduler",
                    "runtime_profile_id": (automation.get("runtime") or {}).get("profile_id"),
                    "retry_count": retry_count,
                }
            )
            self._store.record_run({**run, "next_retry_at": None})
            queued_run_ids.append(str(queued.get("run_id") or ""))
        return queued_run_ids

    def _recover_stale_runs(self, *, now: dt.datetime) -> list[str]:
        recovered: list[str] = []
        for run in self._store.list_runs():
            if str(run.get("status") or "").lower() != "running":
                continue
            started_at = _parse_iso(str(run.get("started_at") or "")) or _parse_iso(str(run.get("due_at") or ""))
            if started_at is None or (now - started_at) < self._stale_after:
                continue
            updated = dict(run)
            updated["status"] = "failed"
            updated["finished_at"] = _to_iso(now)
            updated["redacted_error"] = "automation_watchdog_stale_running_timeout"
            updated["summary"] = "Automation watchdog recovered a stale running run after the timeout window."
            updated["watchdog_reason"] = "stale_running_timeout"
            updated["watchdog_summary"] = (
                f"No final result was recorded within {int(self._stale_after.total_seconds())} seconds, "
                "so the scheduler recovered the run for review."
            )
            updated["recovered_by"] = "scheduler_watchdog"
            updated["recovered_at"] = _to_iso(now)
            self._store.record_run(updated)
            recovered.append(str(updated.get("run_id") or ""))
        return recovered

    def _under_daily_run_limit(self, automation: dict[str, Any], *, now: dt.datetime) -> bool:
        limit = int(((automation.get("limits") or {}).get("daily_run_limit")) or 0)
        if limit <= 0:
            return True
        automation_id = str(automation.get("automation_id") or "")
        today_start = now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        count = 0
        for run in self._store.list_runs(automation_id):
            due_at = _parse_iso(str(run.get("due_at") or ""))
            if due_at is None or due_at < today_start:
                continue
            if str(run.get("status") or "").lower() in {"queued", "running", "needs_review", "completed", "failed", "cancelled", "skipped"}:
                count += 1
        return count < limit

    def _ensure_next_run_at(self, automation: dict[str, Any], *, now: dt.datetime) -> dt.datetime | None:
        schedule = dict(automation.get("schedule") or {})
        mode = str(schedule.get("mode") or "").lower()
        if mode == "manual":
            return None
        existing = _parse_iso(str(schedule.get("next_run_at") or ""))
        if existing is not None:
            return existing
        computed = self._compute_next_run(automation, anchor=now, prefer_immediate_interval=True)
        self._store.update_automation(
            str(automation.get("automation_id") or ""),
            {"schedule": {"next_run_at": _to_iso(computed) if computed else None}},
        )
        return computed

    def _advance_schedule(self, automation: dict[str, Any], *, anchor: dt.datetime) -> None:
        next_run = self._compute_next_run(automation, anchor=anchor, prefer_immediate_interval=False)
        self._store.update_automation(
            str(automation.get("automation_id") or ""),
            {"schedule": {"next_run_at": _to_iso(next_run) if next_run else None}},
        )

    def _compute_next_run(
        self,
        automation: dict[str, Any],
        *,
        anchor: dt.datetime,
        prefer_immediate_interval: bool,
    ) -> dt.datetime | None:
        schedule = dict(automation.get("schedule") or {})
        mode = str(schedule.get("mode") or "").lower()
        if mode == "manual":
            return None
        if mode == "interval":
            expression = str(schedule.get("expression") or "").strip()
            minutes_text = expression.removeprefix("every:").removesuffix("m")
            minutes = max(1, int(minutes_text or "1"))
            if prefer_immediate_interval:
                return anchor
            return anchor + dt.timedelta(minutes=minutes)
        if mode == "daily":
            return _future_daily_occurrence(
                now_utc=anchor,
                expression=str(schedule.get("expression") or "00:00"),
                timezone_name=str(schedule.get("timezone") or "UTC") or "UTC",
            )
        raise ValueError(f"Unsupported scheduler mode: {mode or '<missing>'}.")

    def _has_active_run(self, automation_id: str) -> bool:
        clean_id = str(automation_id or "").strip()
        for run in self._store.list_runs(clean_id):
            if str(run.get("status") or "").lower() in {"queued", "running", "needs_review"}:
                return True
        return False

    def _active_run_count(self) -> int:
        count = 0
        for run in self._store.list_runs():
            if str(run.get("status") or "").lower() in {"queued", "running", "needs_review"}:
                count += 1
        return count

    def _now(self) -> dt.datetime:
        value = self._now_fn()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
