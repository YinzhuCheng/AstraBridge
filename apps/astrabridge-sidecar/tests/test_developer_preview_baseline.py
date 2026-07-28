from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
SIDECAR_ROOT = Path(__file__).resolve().parents[1]

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload  # noqa: E402
from run_developer_preview_baseline_check import run_developer_preview_baseline_check  # noqa: E402


class DeveloperPreviewBaselineTests(unittest.TestCase):
    def test_baseline_summarizes_passing_pre_release_evidence_without_release_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            release_path = root / "release-summary.json"
            update_path = root / "update-summary.json"
            release_path.write_text(json.dumps(_release_summary()), encoding="utf-8")
            update_path.write_text(json.dumps(_update_summary()), encoding="utf-8")

            evidence = run_developer_preview_baseline_check(
                root / "baseline",
                release_readiness_summary=release_path,
                windows_update_summary=update_path,
            )

        self.assertEqual(evidence["mode"], "deterministic_provider_free")
        self.assertEqual(evidence["provider_calls"], [])
        self.assertFalse(evidence["network_calls_attempted"])
        self.assertEqual(evidence["source_evaluation"]["status"], "demonstrated")
        self.assertEqual(evidence["package_contract"]["status"], "pass")
        self.assertEqual(evidence["package_contract"]["staged_file_count_per_run"], 4)
        self.assertEqual(evidence["update_rehearsal"]["status"], "pass")
        self.assertEqual(evidence["update_rehearsal"]["recovery_scenario_count"], 2)
        self.assertEqual(evidence["public_release"]["status"], "blocked")
        self.assertEqual(
            {item["id"] for item in evidence["public_release"]["blockers"]},
            {
                "license_and_contribution_terms",
                "private_vulnerability_reporting",
                "private_conduct_reporting",
                "public_support_and_issue_triage",
                "authorized_distribution_release",
            },
        )
        support_blocker = next(
            item for item in evidence["public_release"]["blockers"] if item["id"] == "public_support_and_issue_triage"
        )
        self.assertEqual(support_blocker["owner"], "community and maintainer-triage owner")
        self.assertIn("prepared safe templates", support_blocker["required_action"])
        self.assertNotIn("Add safe issue templates", support_blocker["required_action"])
        self.assertEqual(evidence["package_contract"]["summary_reference"], "external-input-redacted")
        assert_secret_free_agentic_update_payload(evidence, label="developer_preview_baseline")

    def test_baseline_rejects_failed_or_incomplete_release_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            release = _release_summary()
            release["checks"]["stage_b"] = "fail"
            release_path = root / "release-summary.json"
            update_path = root / "update-summary.json"
            release_path.write_text(json.dumps(release), encoding="utf-8")
            update_path.write_text(json.dumps(_update_summary()), encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "stage_b"):
                run_developer_preview_baseline_check(
                    root / "baseline",
                    release_readiness_summary=release_path,
                    windows_update_summary=update_path,
                )


def _release_summary() -> dict[str, object]:
    return {
        "schema_version": "astrabridge-release-readiness-v1",
        "status": "pass",
        "release_version": "0.1.0",
        "checks": {
            "binding_evaluation": "pass",
            "updater_contract": "pass",
            "stage_a": "pass",
            "stage_b": "pass",
            "deterministic_comparison": "pass",
            "staged_binding_evaluation": "pass",
        },
        "staging_runs": {
            "stage_a": {"status": "pass", "file_count": 4},
            "stage_b": {"status": "pass", "file_count": 4},
        },
    }


def _update_summary() -> dict[str, object]:
    return {
        "schema_version": "astrabridge-windows-update-rehearsal-v1",
        "status": "pass",
        "release_version": "0.1.0",
        "selected_channel": "canary",
        "updater_contract_status": "pass",
        "clean_install_check": {"status": "pass"},
        "update_check": {"status": "pass", "transaction_status": "committed"},
        "rollback_check": {"status": "pass"},
        "recovery_matrix": {
            "status": "pass",
            "scenarios": [{"status": "pass"}, {"status": "pass"}],
        },
    }


if __name__ == "__main__":
    unittest.main()
