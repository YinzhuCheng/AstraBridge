from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.runtime_stability_gate import (  # noqa: E402
    capture_runtime_stability_fixture_evidence,
    run_runtime_stability_gate,
    scan_runtime_stability_artifacts,
)


class RuntimeStabilityGateTests(unittest.TestCase):
    def test_fast_mode_writes_summary_reports_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            calls: list[tuple[tuple[str, ...], str]] = []

            def fake_runner(command: list[str], cwd: Path) -> dict[str, object]:
                calls.append((tuple(command), str(cwd)))
                return {"exit_code": 0, "stdout": "ok\n", "stderr": ""}

            def fake_inventory(output_dir: Path) -> dict[str, object]:
                output_dir.mkdir(parents=True, exist_ok=True)
                marker = output_dir / "inventory.txt"
                marker.write_text("no astrabridge listeners observed\n", encoding="utf-8")
                return {
                    "schema_version": "runtime-stability-process-inventory-test-v1",
                    "captured_at": "2026-07-17T00:00:00+00:00",
                    "records": [{"label": "inventory", "stdout_path": str(marker)}],
                }

            summary = run_runtime_stability_gate(
                workspace_root=root,
                mode="fast",
                include_fixture_evidence=False,
                command_runner=fake_runner,
                process_inventory_provider=fake_inventory,
            )

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["mode"], "fast")
            self.assertEqual(summary["suite_count"], 11)
            self.assertEqual(len(calls), 11)
            self.assertTrue(Path(summary["artifact_paths"]["summary_json"]).exists())
            self.assertTrue(Path(summary["artifact_paths"]["report_md"]).exists())
            self.assertTrue(Path(summary["artifact_paths"]["fault_matrix_json"]).exists())
            self.assertTrue(Path(summary["artifact_paths"]["long_horizon_bundle_json"]).exists())
            self.assertTrue(Path(summary["artifact_paths"]["injected_chaos_drills_json"]).exists())
            self.assertTrue((root / "PRIVATE" / "runtime-stability").exists())
            for suite in summary["suites"]:
                self.assertEqual(suite["status"], "pass")
                self.assertEqual(suite["executed_iterations"], 1)
                for iteration in suite["iterations"]:
                    self.assertTrue(Path(iteration["stdout_path"]).exists())
                    self.assertTrue(Path(iteration["stderr_path"]).exists())
            self.assertTrue(Path(summary["process_inventories"]["before"]).exists())
            self.assertTrue(Path(summary["process_inventories"]["after"]).exists())
            self.assertEqual(summary["fault_matrix"]["schema_version"], "astrabridge-runtime-stability-fault-matrix-v1")
            self.assertEqual(summary["fault_matrix"]["case_count"], 9)
            self.assertEqual(summary["fault_matrix"]["status"], "partial")
            self.assertFalse(summary["fault_matrix"]["release_ready"])
            self.assertEqual(summary["long_horizon_bundle"]["status"], "partial")
            self.assertFalse(summary["long_horizon_bundle"]["release_qualified"])
            self.assertIn("supervised_update_policy_and_containment", summary["long_horizon_bundle"]["suite_labels"])
            self.assertEqual(summary["injected_chaos_drills"]["status"], "partial")
            self.assertFalse(summary["injected_chaos_drills"]["release_qualified"])
            self.assertIn("provider_retry_storm_and_circuit_breaker_chaos", summary["injected_chaos_drills"]["drill_labels"])
            process_kill = next(item for item in summary["fault_matrix"]["cases"] if item["fault_id"] == "process_level_kill")
            self.assertEqual(process_kill["status"], "partial")

    def test_release_mode_marks_gate_failed_when_one_critical_iteration_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            call_counts: dict[str, int] = {}

            def fake_runner(command: list[str], cwd: Path) -> dict[str, object]:  # noqa: ARG001
                label = "unknown"
                for part in command:
                    text = str(part)
                    if "test_graph_scheduler" in text:
                        label = "scheduler"
                        break
                call_counts[label] = call_counts.get(label, 0) + 1
                if label == "scheduler" and call_counts[label] == 2:
                    return {"exit_code": 1, "stdout": "", "stderr": "simulated deterministic failure"}
                return {"exit_code": 0, "stdout": "ok\n", "stderr": ""}

            summary = run_runtime_stability_gate(
                workspace_root=root,
                mode="release",
                include_fixture_evidence=False,
                include_process_inventory=False,
                command_runner=fake_runner,
            )

            self.assertEqual(summary["status"], "fail")
            scheduler_suite = next(
                item for item in summary["suites"] if item["label"] == "scheduler_recovery_and_idempotency"
            )
            self.assertEqual(scheduler_suite["status"], "fail")
            self.assertLess(scheduler_suite["max_consecutive_passes"], scheduler_suite["required_pass_count"])
            failed_logs = [
                Path(iteration["stderr_path"])
                for iteration in scheduler_suite["iterations"]
                if iteration["exit_code"] != 0
            ]
            self.assertTrue(failed_logs)
            self.assertIn("simulated deterministic failure", failed_logs[0].read_text(encoding="utf-8"))

    def test_secret_scan_flags_secret_like_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_path = root / "reports"
            report_path.mkdir()
            (report_path / "summary.log").write_text(
                "Authorization: Bearer abcdefghijklmnopqrstuv\n",
                encoding="utf-8",
            )

            report = scan_runtime_stability_artifacts(root)

            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["finding_count"], 1)
            self.assertEqual(report["findings"][0]["code"], "secret-like")
            self.assertIn("[redacted]", report["findings"][0]["excerpt"].lower())

    def test_fault_matrix_records_required_failure_classes_and_release_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def fake_runner(command: list[str], cwd: Path) -> dict[str, object]:  # noqa: ARG001
                return {"exit_code": 0, "stdout": "ok\n", "stderr": ""}

            summary = run_runtime_stability_gate(
                workspace_root=root,
                mode="release",
                include_fixture_evidence=False,
                include_process_inventory=False,
                command_runner=fake_runner,
            )

            self.assertEqual(summary["fault_matrix"]["status"], "pass")
            self.assertTrue(summary["fault_matrix"]["release_ready"])
            self.assertEqual(summary["long_horizon_bundle"]["status"], "pass")
            self.assertTrue(summary["long_horizon_bundle"]["release_qualified"])
            self.assertEqual(summary["injected_chaos_drills"]["status"], "pass")
            self.assertTrue(summary["injected_chaos_drills"]["release_qualified"])
            by_id = {item["fault_id"]: item for item in summary["fault_matrix"]["cases"]}
            self.assertEqual(
                sorted(by_id),
                sorted(
                    [
                        "process_level_kill",
                        "disk_full_or_read_only",
                        "sqlite_damage",
                        "clock_shift",
                        "network_partition",
                        "truncated_stream",
                        "update_interruption",
                        "multimodal_no_final_answer",
                        "cross_version",
                    ]
                ),
            )
            self.assertEqual(by_id["process_level_kill"]["stale_process_count"]["value"], 0)
            self.assertEqual(by_id["multimodal_no_final_answer"]["downgraded_authority_visibility"]["status"], "pass")
            for record in by_id.values():
                self.assertIn("final_state", record)
                self.assertIn("duplicate_effects", record)
                self.assertIn("recovery_time", record)
                self.assertIn("evidence_completeness", record)
                self.assertIn("stale_process_count", record)
                self.assertIn("downgraded_authority_visibility", record)

    def test_release_mode_long_horizon_bundle_requires_supervised_updater_containment_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def fake_runner(command: list[str], cwd: Path) -> dict[str, object]:  # noqa: ARG001
                return {"exit_code": 0, "stdout": "ok\n", "stderr": ""}

            summary = run_runtime_stability_gate(
                workspace_root=root,
                mode="release",
                include_fixture_evidence=False,
                include_process_inventory=False,
                command_runner=fake_runner,
            )

            bundle = dict(summary["long_horizon_bundle"])
            self.assertEqual(bundle["bundle_id"], "shipping_state_long_horizon_stability")
            self.assertEqual(bundle["status"], "pass")
            self.assertTrue(bundle["release_qualified"])
            self.assertIn("supervised_update_policy_and_containment", bundle["suite_labels"])
            supervised_suite = next(item for item in bundle["suites"] if item["label"] == "supervised_update_policy_and_containment")
            self.assertEqual(supervised_suite["executed_iterations"], 8)
            self.assertEqual(supervised_suite["required_pass_count"], 8)

    def test_release_mode_requires_provider_retry_storm_chaos_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def fake_runner(command: list[str], cwd: Path) -> dict[str, object]:  # noqa: ARG001
                return {"exit_code": 0, "stdout": "ok\n", "stderr": ""}

            summary = run_runtime_stability_gate(
                workspace_root=root,
                mode="release",
                include_fixture_evidence=False,
                include_process_inventory=False,
                command_runner=fake_runner,
            )

            drills = dict(summary["injected_chaos_drills"])
            self.assertEqual(drills["drill_pack_id"], "cross_lane_injected_chaos")
            self.assertEqual(drills["status"], "pass")
            self.assertTrue(drills["release_qualified"])
            self.assertIn("provider_retry_storm_and_circuit_breaker_chaos", drills["drill_labels"])
            provider_drill = next(item for item in drills["drills"] if item["label"] == "provider_retry_storm_and_circuit_breaker_chaos")
            self.assertEqual(provider_drill["executed_iterations"], 8)
            self.assertEqual(provider_drill["required_pass_count"], 8)
            self.assertTrue(provider_drill["thresholds"]["retry_budget_exhaustion_stops_after_single_retry"])

    def test_fixture_evidence_capture_writes_projection_and_store_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "fixture-evidence"
            runtime_root = Path(temp_dir) / "runtime-root"

            with patch.dict(os.environ, {"ASTRABRIDGE_RUNTIME_ROOT": str(runtime_root)}):
                evidence = capture_runtime_stability_fixture_evidence(output_dir=output_dir)

            self.assertEqual(evidence["status"], "pass")
            self.assertEqual(evidence["provider_gate"]["approved_status"], "completed")
            self.assertEqual(evidence["recovery"]["cancelled_status"], "cancelled")
            self.assertEqual(evidence["recovery"]["resumed_status"], "completed")
            self.assertEqual(evidence["recovery"]["recovery_strategy"], "resume_run")
            self.assertTrue(Path(evidence["artifact_paths"]["fixture_summary_json"]).exists())
            self.assertTrue(Path(evidence["artifact_paths"]["provider_pending_run_json"]).exists())
            self.assertTrue(Path(evidence["artifact_paths"]["provider_approved_run_json"]).exists())
            self.assertTrue(Path(evidence["artifact_paths"]["cancelled_run_json"]).exists())
            self.assertTrue(Path(evidence["artifact_paths"]["resumed_run_json"]).exists())
            self.assertTrue(Path(evidence["artifact_paths"]["task_view_json"]).exists())
            self.assertTrue(evidence["artifact_paths"]["copied_artifacts"])
            self.assertIsNotNone(evidence["artifact_paths"]["durable_store_snapshot"])
            self.assertTrue(Path(str(evidence["artifact_paths"]["durable_store_snapshot"])).exists())


if __name__ == "__main__":
    unittest.main()
