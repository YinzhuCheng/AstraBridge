from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.provider_capability_dry_run_matrix import run_provider_capability_dry_run_matrix
from astrabridge_sidecar.provider_capability_verification_gate import evaluate_dry_run_summary, load_verification_baseline


class ProviderCapabilityVerificationGateTests(unittest.TestCase):
    def test_evaluation_flags_unexpected_preview_and_capability_regressions(self) -> None:
        baseline = {
            "schema_version": "astrabridge-provider-capability-verification-gate-v1",
            "allowed_nonpass_preview_cases": [
                {"case_id": "preview-known", "allowed_statuses": ["blocked"]},
            ],
            "allowed_problem_capability_cases": [
                {"case_id": "capability-known", "allowed_capability_statuses": ["conflicting"]},
            ],
        }
        summary = {
            "preview_cases": [
                {"case_id": "preview-known", "status": "blocked"},
                {"case_id": "preview-new", "status": "blocked", "model": "kimi/example", "preview_variant": "off_probe", "reasons": ["new blocker"]},
            ],
            "capability_cases": [
                {"case_id": "capability-known", "capability_status": "conflicting"},
                {
                    "case_id": "capability-new",
                    "capability_status": "conflicting",
                    "status": "blocked",
                    "model": "qwen/example",
                    "capability_id": "vision.analyze",
                    "reasons": ["new conflict"],
                },
            ],
        }

        result = evaluate_dry_run_summary(summary, baseline)

        self.assertEqual(result["status"], "fail")
        self.assertEqual([case["case_id"] for case in result["unexpected_preview_cases"]], ["preview-new"])
        self.assertEqual([case["case_id"] for case in result["unexpected_capability_cases"]], ["capability-new"])

    def test_current_baseline_accepts_current_dry_run_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = run_provider_capability_dry_run_matrix(
                workspace_root=Path(temp_dir),
                run_id="unit-provider-capability-gate-baseline",
            )

            result = evaluate_dry_run_summary(summary, load_verification_baseline())

            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["unexpected_preview_cases"], [])
            self.assertEqual(result["unexpected_capability_cases"], [])


if __name__ == "__main__":
    unittest.main()
