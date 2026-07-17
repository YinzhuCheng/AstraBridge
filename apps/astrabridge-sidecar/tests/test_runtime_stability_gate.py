from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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
            self.assertEqual(summary["suite_count"], 5)
            self.assertEqual(len(calls), 5)
            self.assertTrue(Path(summary["artifact_paths"]["summary_json"]).exists())
            self.assertTrue(Path(summary["artifact_paths"]["report_md"]).exists())
            self.assertTrue((root / "PRIVATE" / "runtime-stability").exists())
            for suite in summary["suites"]:
                self.assertEqual(suite["status"], "pass")
                self.assertEqual(suite["executed_iterations"], 1)
                for iteration in suite["iterations"]:
                    self.assertTrue(Path(iteration["stdout_path"]).exists())
                    self.assertTrue(Path(iteration["stderr_path"]).exists())
            self.assertTrue(Path(summary["process_inventories"]["before"]).exists())
            self.assertTrue(Path(summary["process_inventories"]["after"]).exists())

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

    def test_fixture_evidence_capture_writes_projection_and_store_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "fixture-evidence"

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
