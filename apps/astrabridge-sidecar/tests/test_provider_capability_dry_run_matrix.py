from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.provider_capability_dry_run_matrix import run_provider_capability_dry_run_matrix
from astrabridge_sidecar.provider_model_compatibility_matrix import assert_secret_free_provider_model_compatibility_matrix


class ProviderCapabilityDryRunMatrixTests(unittest.TestCase):
    def test_runner_writes_secret_free_preview_smoke_and_matrix_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = run_provider_capability_dry_run_matrix(
                workspace_root=root,
                run_id="unit-dry-run-matrix",
            )

            self.assertEqual(summary["schema_version"], "astrabridge-provider-capability-dry-run-matrix-v1")
            self.assertIn("qwen", summary["provider_ids_covered"])
            self.assertIn("kimi", summary["provider_ids_covered"])
            self.assertGreater(summary["preview_case_count"], 0)
            self.assertGreater(summary["capability_smoke_case_count"], 0)
            self.assertGreater(summary["matrix_entry_count"], 0)
            self.assertIn("matrix_exposure_state_counts", summary)
            self.assertIn("matrix_route_eligibility_counts", summary)

            run_dir = root / "PRIVATE" / "agentic-update-pipeline" / "runs" / "unit-dry-run-matrix"
            matrix_path = run_dir / "matrix.json"
            summary_path = run_dir / "summary.json"
            report_path = run_dir / "report.md"
            self.assertTrue(matrix_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue((run_dir / "preview-cases").exists())

            matrix = __import__("json").loads(matrix_path.read_text(encoding="utf-8"))
            assert_secret_free_provider_model_compatibility_matrix(matrix)
            self.assertTrue(all(":" in str(entry.get("entry_id") or "") for entry in list(matrix.get("entries") or [])))
            qwen_vision = next(
                entry for entry in list(matrix.get("entries") or []) if str(entry.get("entry_id") or "") == "qwen/qwen3-vl-plus:vision.analyze"
            )
            lane = dict(qwen_vision.get("runtime_normalized_contract") or {}).get("multimodal_lane") or {}
            self.assertEqual(lane["adapter_family"], "chat_multimodal_vision")
            self.assertEqual(lane["request_shape_validation_status"], "pass")
            self.assertEqual(lane["exposure_state"], "wired_unverified")
            self.assertIn("capability:vision.analyze", list(dict(qwen_vision.get("validated_evidence") or {}).get("validation_scope") or []))
            summary_text = summary_path.read_text(encoding="utf-8")
            self.assertNotIn("data:image/", summary_text)
            self.assertNotIn("Bearer ", summary_text)
            self.assertIn("capability_smoke_summary_json", summary_text)
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("Lane Exposure Projection", report_text)
            self.assertIn("qwen/qwen3-vl-plus:vision.analyze", report_text)

    def test_runner_records_kimi_off_probe_as_local_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            summary = run_provider_capability_dry_run_matrix(
                workspace_root=Path(temp_dir),
                run_id="unit-kimi-off-probe",
            )

            kimi_cases = [
                case
                for case in list(summary.get("preview_cases") or [])
                if case.get("model") == "kimi/kimi-k2.7-code" and case.get("preview_variant") == "off_probe"
            ]
            self.assertEqual(len(kimi_cases), 1)
            self.assertEqual(kimi_cases[0]["status"], "blocked")
            self.assertIn("does not support reasoning effort 'off'", " ".join(kimi_cases[0]["reasons"]))

    def test_runner_marks_unsupported_lane_with_exposure_reasoning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = run_provider_capability_dry_run_matrix(
                workspace_root=root,
                run_id="unit-lane-exposure",
            )

            matrix_path = root / "PRIVATE" / "agentic-update-pipeline" / "runs" / "unit-lane-exposure" / "matrix.json"
            matrix = __import__("json").loads(matrix_path.read_text(encoding="utf-8"))
            unsupported_entry = next(
                entry
                for entry in list(matrix.get("entries") or [])
                if str(entry.get("entry_id") or "") == "deepseek/deepseek-v4-pro:vision.analyze"
            )
            lane = dict(unsupported_entry.get("runtime_normalized_contract") or {}).get("multimodal_lane") or {}
            self.assertEqual(lane["route_resolution_status"], "no_capability_candidate")
            self.assertIn(lane["exposure_state"], {"blocked", "hidden"})
            self.assertIn("no_capability_candidate", list(lane.get("downgrade_reasons") or []))


if __name__ == "__main__":
    unittest.main()
