from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.automations import AutomationWorkspaceManager
from astrabridge_sidecar.project_service import ProjectService


@unittest.skipIf(shutil.which("git") is None, "git is required for automation workspace tests")
class AutomationWorkspaceTests(unittest.TestCase):
    def test_dedicated_worktree_uses_app_owned_runtime_root_and_cleanup_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            projects = self._make_git_project(root)
            manager = AutomationWorkspaceManager(projects)
            automation = {
                "automation_id": "auto-1",
                "runtime": {"permission_mode": "workspace-write"},
                "workspace": {"mode": "dedicated_worktree", "cleanup_policy": "delete_on_no_signal"},
            }
            run = {"run_id": "run-1"}

            session = manager.prepare_workspace(automation, run)
            self.assertEqual(session.mode, "dedicated_worktree")
            self.assertIsNotNone(session.worktree_path)
            worktree_path = Path(session.worktree_path or "").resolve()
            runtime_root = projects.current_runtime_roots()["project_runtime_root"].resolve()
            self.assertTrue(worktree_path.exists())
            self.assertTrue(runtime_root == worktree_path or runtime_root in worktree_path.parents)
            self.assertNotIn(projects.require_workspace_root().resolve(), worktree_path.parents)

            retained = manager.finalize_workspace(session, signal="finding", status="completed")
            self.assertFalse(retained["cleaned"])
            self.assertTrue(Path(session.worktree_path or "").exists())

            manual_delete = manager.finalize_workspace(
                AutomationWorkspaceManager(projects).prepare_workspace(
                    {
                        "automation_id": "auto-1b",
                        "runtime": {"permission_mode": "workspace-write"},
                        "workspace": {"mode": "dedicated_worktree", "cleanup_policy": "delete_on_no_signal"},
                    },
                    {"run_id": "run-1b"},
                ),
                signal="no_signal",
                status="completed",
            )
            self.assertTrue(manual_delete["cleaned"])
            self.assertFalse(Path(manual_delete["worktree_path"]).exists())

    def test_dirty_workspace_blocks_current_workspace_destructive_run_but_not_dedicated_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            projects = self._make_git_project(root)
            workspace = projects.require_workspace_root()
            (workspace / "dirty.txt").write_text("local drift\n", encoding="utf-8")
            manager = AutomationWorkspaceManager(projects)

            with self.assertRaisesRegex(ValueError, "dirty_workspace_blocks_current_workspace_run"):
                manager.prepare_workspace(
                    {
                        "automation_id": "auto-dirty",
                        "runtime": {"permission_mode": "workspace-write"},
                        "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                    },
                    {"run_id": "run-dirty"},
                )

            session = manager.prepare_workspace(
                {
                    "automation_id": "auto-safe",
                    "runtime": {"permission_mode": "workspace-write"},
                    "workspace": {"mode": "dedicated_worktree", "cleanup_policy": "manual"},
                },
                {"run_id": "run-safe"},
            )
            self.assertEqual(session.mode, "dedicated_worktree")
            self.assertTrue(Path(session.worktree_path or "").exists())

    def test_non_git_workspace_falls_back_or_errors_for_dedicated_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
            manager = AutomationWorkspaceManager(projects)

            current = manager.prepare_workspace(
                {
                    "automation_id": "auto-local",
                    "runtime": {"permission_mode": "workspace-write"},
                    "workspace": {"mode": "current_workspace", "cleanup_policy": "manual"},
                },
                {"run_id": "run-local"},
            )
            self.assertEqual(current.execution_root, str(workspace.resolve()))

            with self.assertRaisesRegex(ValueError, "git_required_for_worktree"):
                manager.prepare_workspace(
                    {
                        "automation_id": "auto-worktree",
                        "runtime": {"permission_mode": "workspace-write"},
                        "workspace": {"mode": "dedicated_worktree", "cleanup_policy": "manual"},
                    },
                    {"run_id": "run-worktree"},
                )

    def _make_git_project(self, root: Path) -> ProjectService:
        workspace = root / "workspace"
        project_file = root / "demo.abproj"
        projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
        projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
        self._git(workspace, ["init"])
        self._git(workspace, ["config", "user.email", "test@example.com"])
        self._git(workspace, ["config", "user.name", "AstraBridge Tests"])
        (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
        self._git(workspace, ["add", "README.md"])
        self._git(workspace, ["commit", "-m", "init"])
        return projects

    def _git(self, cwd: Path, args: list[str]) -> None:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
        if completed.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {completed.stderr or completed.stdout}")


if __name__ == "__main__":
    unittest.main()
