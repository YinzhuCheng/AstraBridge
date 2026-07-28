from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
SIDECAR_ROOT = Path(__file__).resolve().parents[1]
COHORT_MANIFEST_PATH = REPOSITORY_ROOT / "examples" / "contributor-feedback-cohort" / "cohort-manifest.json"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload  # noqa: E402
from run_contributor_feedback_cohort_rehearsal import run_contributor_feedback_cohort_rehearsal  # noqa: E402


class ContributorFeedbackCohortRehearsalTests(unittest.TestCase):
    def test_cohort_validates_templates_and_rehearses_two_independent_candidate_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = run_contributor_feedback_cohort_rehearsal(Path(temp_dir) / "cohort")

        self.assertEqual(evidence["mode"], "deterministic_provider_free")
        self.assertEqual(evidence["provider_calls"], [])
        self.assertFalse(evidence["network_calls_attempted"])
        self.assertEqual(evidence["template_validation"]["status"], "pass")
        self.assertFalse(evidence["template_validation"]["blank_issues_enabled"])
        self.assertEqual(evidence["template_validation"]["template_count"], 5)
        self.assertEqual(evidence["cohort"]["status"], "rehearsed_pre_preview")
        self.assertEqual(evidence["cohort"]["candidate_count"], 3)
        self.assertEqual(evidence["cohort"]["independent_rehearsal_count"], 2)
        self.assertEqual({item["rehearsal_id"] for item in evidence["cohort"]["rehearsals"]}, {"candidate-skill-a", "candidate-skill-b"})
        self.assertTrue(all(item["validation"] == "pass" for item in evidence["cohort"]["rehearsals"]))
        self.assertTrue(all(item["authority_widening_boundary"] == "blocked" for item in evidence["cohort"]["rehearsals"]))
        self.assertEqual(evidence["review_expectation"]["current_status"], "pending_public_intake")
        self.assertIn("7 calendar days", evidence["review_expectation"]["activation_disposition_target"])
        assert_secret_free_agentic_update_payload(evidence, label="contributor_feedback_cohort")

    def test_cohort_rejects_a_manifest_that_claims_active_public_intake(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = json.loads(COHORT_MANIFEST_PATH.read_text(encoding="utf-8"))
            manifest["response_contract"]["current_intake_status"] = "open"
            manifest_path = root / "cohort-manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "must not claim active public intake"):
                run_contributor_feedback_cohort_rehearsal(root / "cohort", cohort_manifest_path=manifest_path)


if __name__ == "__main__":
    unittest.main()
