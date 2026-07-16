from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.automations import AutomationRunner, AutomationWorkspaceManager
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.security import redact_sensitive


class _FakeProfileService:
    def resolve_runtime_profile(self, profile_id: str) -> dict[str, object]:
        return {
            "profile_id": profile_id,
            "provider_id": "qwen",
            "model": "qwen3.7-plus",
            "reasoning_effort": "high",
            "env_key": "DASHSCOPE_API_KEY",
            "authority_tier": "A",
            "authority_reason": "Test profile has guarded tool execution authority.",
            "command_execution_status": "verified",
            "command_execution_note": "Test fixture declares command execution verification.",
        }


class AutomationSecurityTests(unittest.TestCase):
    def test_redact_sensitive_covers_query_tokens_and_env_like_dicts(self) -> None:
        payload = {
            "api_key": "secret-value",
            "Authorization": "Bearer secret-token-value",
            "url": "https://example.test/path?token=abc123&mode=demo",
            "nested": {"DASHSCOPE_API_KEY": "dash-secret"},
        }
        redacted = redact_sensitive(payload)
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["Authorization"], "[REDACTED]")
        self.assertIn("token=[REDACTED]", redacted["url"])
        self.assertEqual(redacted["nested"]["DASHSCOPE_API_KEY"], "[REDACTED]")

    def test_redact_sensitive_covers_desktop_key_path_strings(self) -> None:
        payload = {
            "note": r"C:\Users\cyz19\Desktop\key.txt should never be persisted",
        }

        redacted = redact_sensitive(payload)

        self.assertEqual(redacted["note"], "[REDACTED_DESKTOP_SECRET_PATH] should never be persisted")

    def test_runner_filters_env_and_requires_explicit_full_access_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects = self._make_project(Path(temp))
            manager = AutomationWorkspaceManager(projects)
            session = manager.prepare_workspace(
                {
                    "automation_id": "auto-1",
                    "runtime": {"permission_mode": "workspace-write"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                },
                {"run_id": "run-1"},
            )

            captured: dict[str, object] = {}

            def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                captured["command"] = command
                captured["env"] = kwargs["env"]
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            original_dashscope = os.environ.get("DASHSCOPE_API_KEY")
            original_other = os.environ.get("OTHER_PROVIDER_API_KEY")
            try:
                os.environ["DASHSCOPE_API_KEY"] = "dashscope-secret"
                os.environ["OTHER_PROVIDER_API_KEY"] = "other-secret"
                runner = AutomationRunner(projects, profile_service=_FakeProfileService(), subprocess_run=fake_run)
                result = runner.execute(
                    {
                        "automation_id": "auto-1",
                        "project_id": "demo",
                        "kind": "standalone",
                        "prompt": "audit repo",
                        "runtime": {"profile_id": "qwen-default", "permission_mode": "workspace-write", "model": "qwen3.7-plus"},
                        "limits": {"timeout_sec": 30},
                    },
                    self._run_payload("run-1"),
                    session,
                )
                self.assertEqual(result["status"], "completed")
                env = captured["env"]
                self.assertIn("DASHSCOPE_API_KEY", env)
                self.assertNotIn("OTHER_PROVIDER_API_KEY", env)

                with self.assertRaisesRegex(ValueError, "dangerous_opt_in=true"):
                    runner.execute(
                        {
                            "automation_id": "auto-2",
                            "project_id": "demo",
                            "kind": "standalone",
                            "prompt": "audit repo",
                            "runtime": {"profile_id": "qwen-default", "permission_mode": "full-access", "model": "qwen3.7-plus"},
                            "limits": {"timeout_sec": 30},
                        },
                        self._run_payload("run-2"),
                        session,
                    )
            finally:
                if original_dashscope is None:
                    os.environ.pop("DASHSCOPE_API_KEY", None)
                else:
                    os.environ["DASHSCOPE_API_KEY"] = original_dashscope
                if original_other is None:
                    os.environ.pop("OTHER_PROVIDER_API_KEY", None)
                else:
                    os.environ["OTHER_PROVIDER_API_KEY"] = original_other

    def _make_project(self, root: Path) -> ProjectService:
        workspace = root / "workspace"
        project_file = root / "demo.abproj"
        projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
        projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
        return projects

    def _run_payload(self, run_id: str) -> dict[str, object]:
        return {
            "run_id": run_id,
            "automation_id": "auto-1",
            "project_id": "demo",
            "trigger": "manual",
            "status": "queued",
            "due_at": dt.datetime(2026, 6, 24, 0, 0, tzinfo=dt.timezone.utc).isoformat(),
            "retry_count": 0,
        }


if __name__ == "__main__":
    unittest.main()
