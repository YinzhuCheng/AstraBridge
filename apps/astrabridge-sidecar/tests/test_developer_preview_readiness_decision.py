from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
SIDECAR_ROOT = Path(__file__).resolve().parents[1]
READINESS_DOCUMENT = REPOSITORY_ROOT / "docs" / "DEVELOPER_PREVIEW_READINESS_DECISION.md"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload  # noqa: E402
from run_developer_preview_readiness_decision import run_developer_preview_readiness_decision  # noqa: E402


class DeveloperPreviewReadinessDecisionTests(unittest.TestCase):
    def test_public_decision_document_preserves_the_pause_boundary_and_owner_gate(self) -> None:
        text = READINESS_DOCUMENT.read_text(encoding="utf-8")

        self.assertIn("Status: `pause`", text)
        self.assertIn("**Branch C — pause.**", text)
        self.assertIn("`license_and_contribution_terms`", text)
        self.assertIn("`private_vulnerability_reporting`", text)
        self.assertIn("`private_conduct_reporting`", text)
        self.assertIn("`OSS-FOUNDATION-CLEARANCE-01`", text)
        self.assertIn("owner_gated", text)

    def test_current_evidence_requires_the_dg_oss_04_pause_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _write_inputs(root)
            evidence = run_developer_preview_readiness_decision(root / "readiness", **paths)

        decision = evidence["decision"]
        self.assertEqual(evidence["mode"], "deterministic_provider_free")
        self.assertEqual(evidence["provider_calls"], [])
        self.assertFalse(evidence["network_calls_attempted"])
        self.assertEqual(decision["gate_id"], "DG-OSS-04")
        self.assertEqual(decision["verdict"], "pause")
        self.assertEqual(decision["branch"], "C")
        self.assertEqual(
            set(decision["hard_pause_gate_ids"]),
            {
                "license_and_contribution_terms",
                "private_vulnerability_reporting",
                "private_conduct_reporting",
            },
        )
        scorecard = evidence["readiness_scorecard"]
        self.assertEqual(scorecard["quality_card_count"], 7)
        self.assertEqual(scorecard["quality_positive_card_count"], 3)
        self.assertEqual(scorecard["quality_non_pass_card_count"], 4)
        self.assertEqual(
            {item["id"] for item in scorecard["foundation_gates"]},
            {
                "license_and_contribution_terms",
                "private_vulnerability_reporting",
                "private_conduct_reporting",
                "public_support_and_issue_triage",
                "authorized_distribution_release",
            },
        )
        self.assertEqual(evidence["next_execution_unit"]["id"], "OSS-FOUNDATION-CLEARANCE-01")
        self.assertEqual(evidence["next_execution_unit"]["status"], "owner_gated")
        assert_secret_free_agentic_update_payload(evidence, label="developer_preview_readiness_decision")

    def test_rejects_an_attempt_to_hide_a_release_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _write_inputs(root)
            preview = json.loads(paths["preview_baseline_evidence"].read_text(encoding="utf-8"))
            preview["public_release"]["blockers"] = preview["public_release"]["blockers"][:-1]
            paths["preview_baseline_evidence"].write_text(json.dumps(preview), encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "all five canonical release blockers"):
                run_developer_preview_readiness_decision(root / "readiness", **paths)

    def test_rejects_an_attempt_to_activate_public_intake_in_cohort_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _write_inputs(root)
            cohort = json.loads(paths["contributor_cohort_evidence"].read_text(encoding="utf-8"))
            cohort["review_expectation"]["current_status"] = "open"
            paths["contributor_cohort_evidence"].write_text(json.dumps(cohort), encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "intake must remain pending"):
                run_developer_preview_readiness_decision(root / "readiness", **paths)


def _write_inputs(root: Path) -> dict[str, Path]:
    preview = {
        "schema_version": "astrabridge-developer-preview-baseline-evidence-v1",
        "mode": "deterministic_provider_free",
        "provider_calls": [],
        "network_calls_attempted": False,
        "package_contract": {"status": "pass"},
        "update_rehearsal": {"status": "pass"},
        "public_release": {
            "status": "blocked",
            "release_version": "0.1.0",
            "blockers": [
                {
                    "id": "license_and_contribution_terms",
                    "owner": "project and legal foundation owner",
                    "required_action": "Record license and contribution terms.",
                },
                {
                    "id": "private_vulnerability_reporting",
                    "owner": "security maintainer",
                    "required_action": "Configure private vulnerability reporting.",
                },
                {
                    "id": "private_conduct_reporting",
                    "owner": "conduct enforcement owner",
                    "required_action": "Configure private conduct reporting.",
                },
                {
                    "id": "public_support_and_issue_triage",
                    "owner": "community and maintainer-triage owner",
                    "required_action": "Keep public intake disabled until every prerequisite is verified.",
                },
                {
                    "id": "authorized_distribution_release",
                    "owner": "release owner",
                    "required_action": "Authorize distribution evidence.",
                },
            ],
        },
    }
    cohort = {
        "schema_version": "astrabridge-contributor-feedback-cohort-evidence-v1",
        "mode": "deterministic_provider_free",
        "provider_calls": [],
        "network_calls_attempted": False,
        "cohort": {
            "status": "rehearsed_pre_preview",
            "candidate_count": 3,
            "independent_rehearsal_count": 2,
        },
        "review_expectation": {"current_status": "pending_public_intake"},
    }
    preview_path = root / "preview-baseline.json"
    cohort_path = root / "contributor-cohort.json"
    preview_path.write_text(json.dumps(preview), encoding="utf-8")
    cohort_path.write_text(json.dumps(cohort), encoding="utf-8")
    return {
        "preview_baseline_evidence": preview_path,
        "contributor_cohort_evidence": cohort_path,
    }


if __name__ == "__main__":
    unittest.main()
