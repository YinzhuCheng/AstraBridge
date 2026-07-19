from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.project_service import ProjectService


class ProjectRuntimeActivationTests(unittest.TestCase):
    def test_create_project_writes_committed_runtime_activation_journal(self) -> None:
        original_appdata = os.environ.get("ASTRABRIDGE_APPDATA")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                os.environ["ASTRABRIDGE_APPDATA"] = str(root / "AppData")
                workspace = root / "workspace"
                workspace.mkdir()
                service = ProjectService(root / "recent.json")

                service.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")

                journal_path = workspace / ".astrabridge" / "runtime-activation-journal.json"
                rollback_path = workspace / ".astrabridge" / "runtime-activation-rollback.json"
                self.assertTrue(journal_path.is_file())
                self.assertTrue(rollback_path.is_file())

                journal = json.loads(journal_path.read_text(encoding="utf-8"))
                track = journal["tracks"][0]
                self.assertEqual(journal["schema_version"], "astrabridge-agentic-update-apply-journal-v1")
                self.assertEqual(journal["status"], "committed")
                self.assertEqual(track["track_id"], "runtime_directory_activation")
                self.assertEqual(track["health_verdict"], "pass")
                self.assertEqual(track["rollback_target"]["restore_status"], "available_for_manual_restore")

                rollback = json.loads(rollback_path.read_text(encoding="utf-8"))
                self.assertEqual(rollback["schema_version"], "astrabridge-runtime-directory-activation-rollback-v1")
                self.assertEqual(rollback["restore_status"], "available_for_manual_restore")
                self.assertTrue(rollback["state_after"]["project_runtime_root"]["exists"])
        finally:
            if original_appdata is None:
                os.environ.pop("ASTRABRIDGE_APPDATA", None)
            else:
                os.environ["ASTRABRIDGE_APPDATA"] = original_appdata

    def test_failed_storage_policy_write_rolls_back_runtime_activation_state(self) -> None:
        class FailingProjectService(ProjectService):
            def _write_storage_policy(self, workspace_root: Path, *, project_path: Path | None = None, entry_mode: str | None = None) -> None:
                raise RuntimeError("forced storage policy failure")

        original_appdata = os.environ.get("ASTRABRIDGE_APPDATA")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                os.environ["ASTRABRIDGE_APPDATA"] = str(root / "AppData")
                workspace = root / "workspace"
                workspace.mkdir()
                service = FailingProjectService(root / "recent.json")
                project_path = root / "demo.abproj"

                with self.assertRaises(RuntimeError):
                    service.create_project("Demo", project_path, workspace_root=workspace, entry_mode="existing")

                runtime_roots = service._runtime_roots_for_project(project_path.resolve(), workspace.resolve())
                journal_path = workspace / ".astrabridge" / "runtime-activation-journal.json"
                rollback_path = workspace / ".astrabridge" / "runtime-activation-rollback.json"
                policy_path = workspace / ".astrabridge" / "storage_policy.json"

                self.assertTrue(journal_path.is_file())
                self.assertTrue(rollback_path.is_file())
                self.assertFalse(policy_path.exists())
                self.assertTrue(runtime_roots["project_runtime_root"].exists())
                self.assertFalse(runtime_roots["codex_home_root"].exists())
                self.assertFalse(runtime_roots["downloads_root"].exists())
                self.assertFalse(runtime_roots["caches_root"].exists())
                self.assertFalse(runtime_roots["tmp_root"].exists())

                journal = json.loads(journal_path.read_text(encoding="utf-8"))
                track = journal["tracks"][0]
                self.assertEqual(journal["status"], "rolled_back")
                self.assertEqual(track["track_id"], "runtime_directory_activation")
                self.assertEqual(track["health_verdict"], "fail")
                self.assertEqual(track["rollback_target"]["restore_status"], "restored_after_failure")

                rollback = json.loads(rollback_path.read_text(encoding="utf-8"))
                self.assertEqual(rollback["restore_status"], "restored_after_failure")
                self.assertTrue(rollback["restored_state"]["project_runtime_root"]["exists"])
                self.assertFalse(rollback["restored_state"]["codex_home_root"]["exists"])
        finally:
            if original_appdata is None:
                os.environ.pop("ASTRABRIDGE_APPDATA", None)
            else:
                os.environ["ASTRABRIDGE_APPDATA"] = original_appdata


if __name__ == "__main__":
    unittest.main()
