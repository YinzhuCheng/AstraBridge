from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_install_smoke import run_plugin_install_smoke


class PluginInstallSmokeTests(unittest.TestCase):
    def test_run_plugin_install_smoke_writes_report_and_covers_required_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            artifact_root = repo_root / "PRIVATE" / "demo-runs" / "plugin-install-smoke-test"

            report = run_plugin_install_smoke(
                artifact_root=artifact_root,
                repo_root=repo_root,
            )

            self.assertEqual(report["summary"]["overall_status"], "pass")
            case_ids = [item["case_id"] for item in report["cases"]]
            self.assertEqual(
                case_ids,
                ["install", "update", "already_current", "malformed", "failed_apply_rollback", "secret_scan"],
            )
            self.assertTrue((artifact_root / "reports" / "smoke-report.json").exists())


if __name__ == "__main__":
    unittest.main()
