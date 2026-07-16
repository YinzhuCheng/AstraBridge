from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import run_agentic_update_fixture_dogfood


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000100"
    "e221bc330000000049454e44ae426082"
)


class AgenticUpdateFixtureDogfoodTests(unittest.TestCase):
    def test_fixture_dogfood_produces_evidence_and_blocks_unsafe_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)

            def fake_screenshot_runner(html_path: Path, screenshot_path: Path) -> dict[str, Any]:
                self.assertTrue(html_path.exists())
                screenshot_path.write_bytes(PNG_1X1)
                return {"exit_code": 0, "stdout_excerpt": "fake screenshot", "stderr_excerpt": ""}

            report = run_agentic_update_fixture_dogfood(
                workspace_root=workspace,
                run_id="step18-unit-dogfood",
                screenshot_runner=fake_screenshot_runner,
            )

            artifacts = dict(report["artifact_paths"])
            summary = dict(report["summary"])
            dogfood = dict(report["dogfood"])
            proposal = json.loads(Path(artifacts["proposal"]).read_text(encoding="utf-8"))
            diff = json.loads(Path(artifacts["proposal_diff"]).read_text(encoding="utf-8"))
            validation = json.loads(Path(artifacts["validation_report"]).read_text(encoding="utf-8"))
            rollback = json.loads(Path(artifacts["rollback_manifest"]).read_text(encoding="utf-8"))
            screenshot_index = json.loads(Path(artifacts["screenshot_index"]).read_text(encoding="utf-8"))
            sensitive_scan = json.loads(Path(artifacts["secret_scan"]).read_text(encoding="utf-8"))

            self.assertEqual(report["status"], "pass")
            self.assertEqual(summary["validation_status"], "pass")
            self.assertEqual(proposal["run_id"], "step18-unit-dogfood")
            self.assertEqual(diff["risk_class"], "requires_kernel_smoke")
            self.assertGreaterEqual(diff["summary"]["change_count"], 2)
            self.assertEqual(validation["status"], "pass")
            self.assertTrue(rollback["reversible"])
            self.assertTrue(Path(artifacts["proposal_review_screenshot"]).exists())
            self.assertTrue(screenshot_index["screenshots"][0]["captured"])
            self.assertTrue(all(screenshot_index["screenshots"][0]["unsafe_actions_disabled"].values()))
            self.assertEqual(sensitive_scan["status"], "pass")
            self.assertEqual(sensitive_scan["matches"], [])
            self.assertTrue(summary["unsafe_api_blocked"])
            self.assertFalse(dogfood["safety"]["provider_calls_attempted"])
            self.assertFalse(dogfood["safety"]["install_attempted"])
            self.assertFalse(dogfood["safety"]["source_code_changed"])
            self.assertFalse((workspace / ".astrabridge").exists())
            self.assertFalse((workspace / ".codex").exists())
            self.assertFalse((workspace / "codex-locator.json").exists())


if __name__ == "__main__":
    unittest.main()
