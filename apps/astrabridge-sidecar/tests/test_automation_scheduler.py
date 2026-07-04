from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.automations import AutomationScheduler, AutomationStore
from astrabridge_sidecar.project_service import ProjectService


UTC = dt.timezone.utc


class _FakeClock:
    def __init__(self, value: dt.datetime) -> None:
        self.value = value

    def now(self) -> dt.datetime:
        return self.value

    def set(self, value: dt.datetime) -> None:
        self.value = value


class AutomationSchedulerTests(unittest.TestCase):
    def test_interval_scheduler_claims_once_and_respects_global_concurrency(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self._make_store(Path(temp))
            clock = _FakeClock(dt.datetime(2026, 6, 24, 0, 0, tzinfo=UTC))
            scheduler = AutomationScheduler(store, now_fn=clock.now, max_active_runs=1)
            store.create_automation(
                {
                    "automation_id": "auto-a",
                    "project_id": "demo",
                    "name": "A",
                    "kind": "standalone",
                    "prompt": "run a",
                    "schedule": {"mode": "interval", "interval_minutes": 15},
                }
            )
            store.create_automation(
                {
                    "automation_id": "auto-b",
                    "project_id": "demo",
                    "name": "B",
                    "kind": "standalone",
                    "prompt": "run b",
                    "schedule": {"mode": "interval", "interval_minutes": 15},
                }
            )

            scheduler.start()
            first = scheduler.tick()
            self.assertEqual(len(first["queued_run_ids"]), 1)
            self.assertEqual(store.list_runs("auto-a")[0]["status"], "queued")

            second = scheduler.tick()
            self.assertEqual(second["queued_run_ids"], [])
            self.assertEqual(len(store.list_runs()), 1)

    def test_daily_schedule_and_next_wake_up_use_timezone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self._make_store(Path(temp))
            clock = _FakeClock(dt.datetime(2026, 6, 24, 0, 10, tzinfo=UTC))
            scheduler = AutomationScheduler(store, now_fn=clock.now, max_active_runs=2)
            store.create_automation(
                {
                    "automation_id": "auto-daily",
                    "project_id": "demo",
                    "name": "Daily",
                    "kind": "standalone",
                    "prompt": "run daily",
                    "schedule": {"mode": "daily", "expression": "09:30", "timezone": "Asia/Shanghai"},
                }
            )

            next_wake = scheduler.next_wake_up_at()
            self.assertEqual(next_wake, "2026-06-24T01:30:00+00:00")
            clock.set(dt.datetime(2026, 6, 24, 1, 30, tzinfo=UTC))
            scheduler.start()
            result = scheduler.tick()
            self.assertEqual(len(result["queued_run_ids"]), 1)
            self.assertEqual(store.list_runs("auto-daily")[0]["due_at"], "2026-06-24T01:30:00+00:00")

    def test_missed_run_policies_skip_or_queue_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self._make_store(Path(temp))
            clock = _FakeClock(dt.datetime(2026, 6, 24, 3, 0, tzinfo=UTC))
            scheduler = AutomationScheduler(store, now_fn=clock.now, max_active_runs=3)
            store.create_automation(
                {
                    "automation_id": "skip-auto",
                    "project_id": "demo",
                    "name": "Skip",
                    "kind": "standalone",
                    "prompt": "skip",
                    "schedule": {
                        "mode": "interval",
                        "interval_minutes": 30,
                        "next_run_at": "2026-06-24T00:00:00+00:00",
                        "catch_up_policy": "skip_missed",
                    },
                }
            )
            store.create_automation(
                {
                    "automation_id": "once-auto",
                    "project_id": "demo",
                    "name": "Once",
                    "kind": "standalone",
                    "prompt": "once",
                    "schedule": {
                        "mode": "interval",
                        "interval_minutes": 30,
                        "next_run_at": "2026-06-24T00:00:00+00:00",
                        "catch_up_policy": "run_once",
                    },
                }
            )

            scheduler.start()
            result = scheduler.tick()
            self.assertEqual(result["skipped_automation_ids"], ["skip-auto"])
            self.assertEqual(len(result["queued_run_ids"]), 1)
            self.assertEqual(store.list_runs("skip-auto"), [])
            self.assertEqual(len(store.list_runs("once-auto")), 1)
            self.assertGreater(
                store.get_automation("skip-auto")["schedule"]["next_run_at"],
                "2026-06-24T03:00:00+00:00",
            )

    def test_stale_running_run_is_recovered_and_not_reclaimed_until_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self._make_store(Path(temp))
            clock = _FakeClock(dt.datetime(2026, 6, 24, 5, 0, tzinfo=UTC))
            scheduler = AutomationScheduler(
                store,
                now_fn=clock.now,
                stale_after=dt.timedelta(minutes=30),
                max_active_runs=2,
            )
            store.create_automation(
                {
                    "automation_id": "auto-stale",
                    "project_id": "demo",
                    "name": "Stale",
                    "kind": "standalone",
                    "prompt": "stale",
                    "schedule": {
                        "mode": "interval",
                        "interval_minutes": 10,
                        "next_run_at": "2026-06-24T04:45:00+00:00",
                        "catch_up_policy": "run_once",
                    },
                }
            )
            store.record_run(
                {
                    "run_id": "run-stale",
                    "automation_id": "auto-stale",
                    "project_id": "demo",
                    "trigger": "schedule",
                    "status": "running",
                    "due_at": "2026-06-24T04:00:00+00:00",
                    "started_at": "2026-06-24T04:00:00+00:00",
                    "signal": "unknown",
                    "summary": "still running",
                }
            )

            scheduler.start()
            result = scheduler.tick()
            self.assertEqual(result["recovered_run_ids"], ["run-stale"])
            recovered = store.get_run("run-stale")
            self.assertEqual(recovered["status"], "failed")
            self.assertEqual(recovered["redacted_error"], "automation_watchdog_stale_running_timeout")
            self.assertEqual(recovered["watchdog_reason"], "stale_running_timeout")
            self.assertEqual(recovered["recovered_by"], "scheduler_watchdog")
            self.assertEqual(len(result["queued_run_ids"]), 1)

    def test_failed_run_schedules_retry_with_backoff_and_honors_daily_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = self._make_store(Path(temp))
            clock = _FakeClock(dt.datetime(2026, 6, 24, 6, 0, tzinfo=UTC))
            scheduler = AutomationScheduler(store, now_fn=clock.now, max_active_runs=3)
            store.create_automation(
                {
                    "automation_id": "auto-retry",
                    "project_id": "demo",
                    "name": "Retry",
                    "kind": "standalone",
                    "prompt": "retry",
                    "schedule": {"mode": "interval", "interval_minutes": 10, "next_run_at": "2026-06-24T07:00:00+00:00"},
                    "limits": {"max_retries": 2, "daily_run_limit": 2},
                }
            )
            store.record_run(
                {
                    "run_id": "run-failed",
                    "automation_id": "auto-retry",
                    "project_id": "demo",
                    "trigger": "manual",
                    "status": "failed",
                    "due_at": "2026-06-24T05:50:00+00:00",
                    "started_at": "2026-06-24T05:50:00+00:00",
                    "finished_at": "2026-06-24T05:55:00+00:00",
                    "signal": "unknown",
                    "summary": "failed",
                    "next_retry_at": "2026-06-24T05:59:00+00:00",
                    "retry_count": 0,
                }
            )

            scheduler.start()
            result = scheduler.tick()
            self.assertEqual(len(result["queued_run_ids"]), 1)
            retry_runs = [run for run in store.list_runs("auto-retry") if run["trigger"] == "retry"]
            self.assertEqual(len(retry_runs), 1)
            self.assertEqual(retry_runs[0]["retry_count"], 1)
            self.assertIsNone(store.get_run("run-failed")["next_retry_at"])

            clock.set(dt.datetime(2026, 6, 24, 8, 0, tzinfo=UTC))
            result = scheduler.tick()
            self.assertEqual(result["queued_run_ids"], [])

    def _make_store(self, root: Path) -> AutomationStore:
        workspace = root / "workspace"
        project_file = root / "demo.abproj"
        projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
        projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
        return AutomationStore(projects)


if __name__ == "__main__":
    unittest.main()
