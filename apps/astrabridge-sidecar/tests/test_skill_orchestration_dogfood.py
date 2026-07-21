from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.skill_orchestration_dogfood import (  # noqa: E402
    DOGFOOD_CASES,
    run_skill_orchestration_dogfood,
)


class SkillOrchestrationDogfoodTests(unittest.TestCase):
    def test_initial_case_catalog_is_finite_and_points_at_current_repo_surfaces(self) -> None:
        case_ids = [str(item["case_id"]) for item in DOGFOOD_CASES]
        self.assertEqual(len(case_ids), 5)
        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertTrue(all(list(item.get("observed_paths") or []) for item in DOGFOOD_CASES))
        serialized = json.dumps(DOGFOOD_CASES, ensure_ascii=False)
        self.assertNotIn("Bearer ", serialized)
        self.assertNotIn("BEGIN PRIVATE KEY", serialized)

    def test_selected_case_runs_the_canonical_mcp_dogfood_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="astrabridge-dogfood-") as temp_dir:
            summary = run_skill_orchestration_dogfood(
                artifact_root=Path(temp_dir),
                run_id="unit-supervisor",
                case_ids=["skill-boundary-synthesis"],
                repo_root=Path(__file__).resolve().parents[3],
            )
            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["case_count"], 1)
            case = summary["cases"][0]
            self.assertEqual(case["operational_status"], "pass")
            self.assertEqual(case["fixture_outcome"], "completed")
            self.assertEqual([item["status"] for item in case["mcp_operations"]], ["completed", "completed", "completed", "accepted", "completed"])
            self.assertEqual(summary["execution_policy"]["provider_calls"], 0)
            self.assertEqual(summary["execution_policy"]["network_discovery_calls"], 0)
            self.assertTrue(Path(summary["artifact_paths"]["summary_json"]).exists())
            self.assertTrue(Path(summary["artifact_paths"]["report_md"]).exists())


if __name__ == "__main__":
    unittest.main()
