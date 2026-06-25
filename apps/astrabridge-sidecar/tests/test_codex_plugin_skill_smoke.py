from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_skill_smoke import run_plugin_skill_smoke


class PluginSkillSmokeTests(unittest.TestCase):
    def test_run_plugin_skill_smoke_writes_report_and_required_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            artifact_root = repo_root / "PRIVATE" / "demo-runs" / "plugin-skill-smoke-test"

            def fake_ui_smoke_runner(*, repo_root: Path, snapshot_path: Path, artifact_root: Path, fixture: dict[str, str], subprocess_run=None) -> dict[str, object]:  # noqa: ARG001
                artifact_root.mkdir(parents=True, exist_ok=True)
                assertions_path = artifact_root / "ui-assertions.json"
                vitest_report_path = artifact_root / "vitest-report.json"
                assertions_path.write_text(
                    json.dumps(
                        {
                            "schema_version": "astrabridge-plugin-skill-ui-assertions-v1",
                            "assertions": [
                                {"id": "title", "ok": True, "expected": "Extensions"},
                                {"id": "plugin_count", "ok": True, "expected": "Plugins: 1"},
                                {"id": "skill_count", "ok": True, "expected": "Skills: 1"},
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                vitest_report_path.write_text(json.dumps({"numTotalTests": 1, "numPassedTests": 1}), encoding="utf-8")
                return {
                    "status": "pass",
                    "snapshot_path": str(snapshot_path),
                    "assertions_path": str(assertions_path),
                    "vitest_report_path": str(vitest_report_path),
                    "assertions": [
                        {"id": "title", "ok": True, "expected": "Extensions"},
                        {"id": "plugin_count", "ok": True, "expected": "Plugins: 1"},
                        {"id": "skill_count", "ok": True, "expected": "Skills: 1"},
                    ],
                    "failed_assertions": [],
                    "warnings": [],
                }

            report = run_plugin_skill_smoke(
                artifact_root=artifact_root,
                repo_root=repo_root,
                ui_smoke_runner=fake_ui_smoke_runner,
            )

            self.assertEqual(report["summary"]["overall_status"], "pass")
            check_ids = [item["check_id"] for item in report["checks"]]
            self.assertEqual(
                check_ids,
                [
                    "plugin_discovery",
                    "skill_discovery",
                    "fixture_skill_availability",
                    "mcp_side_effects",
                    "ui_inventory_rendering",
                ],
            )
            self.assertTrue((artifact_root / "reports" / "smoke-report.json").exists())
            self.assertTrue((artifact_root / "reports" / "plugin-skill-registry-snapshot.json").exists())


if __name__ == "__main__":
    unittest.main()
