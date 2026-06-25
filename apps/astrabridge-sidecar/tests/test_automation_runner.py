from __future__ import annotations

import datetime as dt
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.automations import (
    AutomationRunner,
    AutomationWorkspaceManager,
)
from astrabridge_sidecar.project_service import ProjectService


class _FakeProfileService:
    def resolve_runtime_profile(self, profile_id: str) -> dict[str, object]:
        return {
            "profile_id": profile_id,
            "provider_id": "deepseek",
            "model": "deepseek-v4-pro",
            "reasoning_effort": "high",
        }


class _FakeRuntimeConfig:
    def prepare_profile(self, profile: dict[str, object], *, require_secret: bool) -> dict[str, object]:  # noqa: ARG002
        return {"codex_home": "D:/fake-codex-home"}


class _FakeRuntimeService:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[dict[str, object]] = []

    def start_turn(
        self,
        profile: dict[str, object],
        *,
        thread_id: str,
        text: str,
        attachments: list[dict[str, object]],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None = None,
        context_mode: str | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "profile": profile,
                "thread_id": thread_id,
                "text": text,
                "attachments": attachments,
                "model": model,
                "effort": effort,
                "permission_mode": permission_mode,
                "collaboration_mode": collaboration_mode,
                "context_mode": context_mode,
            }
        )
        if self.should_fail:
            raise RuntimeError("provider thread not found")
        return {"thread_id": thread_id, "turn": {"id": "turn-123"}}


class AutomationRunnerTests(unittest.TestCase):
    def test_standalone_runner_reports_completed_and_redacts_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects = self._make_project(Path(temp))
            session = self._workspace_session(projects, automation_id="auto-1", run_id="run-1")
            captured: dict[str, object] = {}

            def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                captured["command"] = command
                captured["kwargs"] = kwargs
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="done Authorization: Bearer secret-token-value",
                    stderr="",
                )

            runner = AutomationRunner(
                projects,
                profile_service=_FakeProfileService(),
                runtime_config=_FakeRuntimeConfig(),
                subprocess_run=fake_run,
            )
            result = runner.execute(
                self._standalone_automation(),
                self._run_payload(run_id="run-1", trigger="schedule"),
                session,
            )

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["exit_code"], 0)
            self.assertIn("[REDACTED]", result["summary"])
            self.assertEqual(captured["command"], ["codex", "exec", "Audit repo", "--sandbox", "workspace-write", "--model", "deepseek-v4-pro"])
            self.assertEqual(captured["kwargs"]["cwd"], session.execution_root)
            self.assertEqual(captured["kwargs"]["env"]["CODEX_HOME"], "D:/fake-codex-home")

    def test_standalone_runner_handles_failure_and_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects = self._make_project(Path(temp))
            session = self._workspace_session(projects, automation_id="auto-2", run_id="run-2")

            def fake_fail(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:  # noqa: ARG001
                return subprocess.CompletedProcess(command, 2, stdout="", stderr="fatal api_key=secret")

            runner = AutomationRunner(
                projects,
                profile_service=_FakeProfileService(),
                runtime_config=_FakeRuntimeConfig(),
                subprocess_run=fake_fail,
            )
            failed = runner.execute(self._standalone_automation(), self._run_payload(run_id="run-2"), session)
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["exit_code"], 2)
            self.assertIn("[REDACTED]", failed["redacted_error"])

            def fake_timeout(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:  # noqa: ARG001
                raise subprocess.TimeoutExpired(command, timeout=30)

            timeout_runner = AutomationRunner(
                projects,
                profile_service=_FakeProfileService(),
                runtime_config=_FakeRuntimeConfig(),
                subprocess_run=fake_timeout,
            )
            timed_out = timeout_runner.execute(self._standalone_automation(), self._run_payload(run_id="run-3"), session)
            self.assertEqual(timed_out["status"], "failed")
            self.assertIn("timed out", timed_out["summary"].lower())

    def test_thread_runner_handles_success_and_missing_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects = self._make_project(Path(temp))
            session = self._workspace_session(projects, automation_id="auto-3", run_id="run-4")
            runtime = _FakeRuntimeService()
            runner = AutomationRunner(
                projects,
                runtime_service=runtime,
                profile_service=_FakeProfileService(),
            )
            thread_automation = {
                **self._standalone_automation(),
                "kind": "thread",
                "runtime": {
                    "profile_id": "deepseek-default",
                    "model": "deepseek-v4-pro",
                    "effort": "high",
                    "permission_mode": "workspace-write",
                    "collaboration_mode": "plan",
                },
            }
            started = runner.execute(
                thread_automation,
                self._run_payload(run_id="run-4", thread_id="thread-42"),
                session,
            )
            self.assertEqual(started["status"], "running")
            self.assertEqual(started["turn_id"], "turn-123")
            self.assertEqual(runtime.calls[0]["permission_mode"], "auto")
            self.assertEqual(runtime.calls[0]["collaboration_mode"], "plan")

            failing_runtime = _FakeRuntimeService(should_fail=True)
            failing_runner = AutomationRunner(
                projects,
                runtime_service=failing_runtime,
                profile_service=_FakeProfileService(),
            )
            missing = failing_runner.execute(
                thread_automation,
                self._run_payload(run_id="run-5", thread_id="thread-missing"),
                session,
            )
            self.assertEqual(missing["status"], "failed")
            self.assertEqual(missing["redacted_error"], "thread_not_found")

    def _make_project(self, root: Path) -> ProjectService:
        workspace = root / "workspace"
        project_file = root / "demo.abproj"
        projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
        projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
        return projects

    def _workspace_session(self, projects: ProjectService, *, automation_id: str, run_id: str):
        manager = AutomationWorkspaceManager(projects)
        return manager.prepare_workspace(
            {
                "automation_id": automation_id,
                "runtime": {"permission_mode": "workspace-write"},
                "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
            },
            {"run_id": run_id},
        )

    def _standalone_automation(self) -> dict[str, object]:
        return {
            "automation_id": "auto-1",
            "project_id": "demo",
            "kind": "standalone",
            "prompt": "Audit repo",
            "runtime": {
                "profile_id": "deepseek-default",
                "model": "deepseek-v4-pro",
                "effort": "high",
                "permission_mode": "workspace-write",
            },
            "limits": {"timeout_sec": 30},
        }

    def _run_payload(self, *, run_id: str, trigger: str = "manual", thread_id: str | None = None) -> dict[str, object]:
        return {
            "run_id": run_id,
            "automation_id": "auto-1",
            "project_id": "demo",
            "trigger": trigger,
            "status": "queued",
            "due_at": dt.datetime(2026, 6, 24, 0, 0, tzinfo=dt.timezone.utc).isoformat(),
            "thread_id": thread_id,
        }


if __name__ == "__main__":
    unittest.main()
