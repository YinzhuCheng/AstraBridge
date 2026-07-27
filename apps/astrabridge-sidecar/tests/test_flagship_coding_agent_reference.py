from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = REPO_ROOT / "scripts" / "run_flagship_coding_agent_reference.py"


class FlagshipCodingAgentReferenceTests(unittest.TestCase):
    def test_runner_builds_no_key_evidence_with_failure_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "flagship-reference"
            completed = subprocess.run(
                [sys.executable, str(RUNNER), "--output-root", str(output_root)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(completed.stdout)

            self.assertEqual(evidence["reference"]["template_id"], "code_fix_test_review")
            self.assertEqual(evidence["graph"]["node_count"], 4)
            self.assertEqual(evidence["graph"]["edge_count"], 3)
            self.assertEqual(evidence["provider_calls"], [])
            self.assertEqual(evidence["project"]["workspace_root"], "w")
            self.assertTrue(evidence["permission_boundary"]["requires_human_approval"])
            self.assertEqual(evidence["permission_boundary"]["approval_kind"], "filesystem_write_gate")

            seed_project = evidence["seed_project"]
            self.assertNotEqual(seed_project["before_check"]["exit_code"], 0)
            self.assertEqual(seed_project["recovered_check"]["exit_code"], 0)
            self.assertTrue((output_root / seed_project["expected_patch"]).exists())

            self.assertEqual(evidence["dry_run"]["status"], "pass")
            self.assertEqual(evidence["failure_exercise"]["status"], "failed")
            self.assertEqual(
                set(evidence["failure_exercise"]["blocked_node_ids"]),
                {"node_code_fix", "node_test", "node_review"},
            )
            self.assertEqual(evidence["recovery_exercise"]["status"], "completed")
            self.assertEqual(evidence["recovery_exercise"]["strategy"], "retry_failed_nodes")
            self.assertEqual(
                set(evidence["recovery_exercise"]["rerun_node_ids"]),
                {"node_plan_fix", "node_code_fix", "node_test", "node_review"},
            )

            packet = evidence["artifact_packet"]
            self.assertTrue((output_root / packet["evidence_json"]).exists())
            self.assertTrue((output_root / packet["evidence_markdown"]).exists())
            self.assertTrue((output_root / "w" / packet["exported_orchestration_graph"]).exists())
            self.assertTrue((output_root / "w" / packet["failed_run_manifest"]).exists())
            self.assertTrue((output_root / "w" / packet["recovery_manifest"]).exists())


if __name__ == "__main__":
    unittest.main()
