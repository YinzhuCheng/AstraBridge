from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.runtime_rollout_gate import (  # noqa: E402
    capture_runtime_rollout_migration_evidence,
    capture_runtime_rollout_rollback_readback,
    capture_runtime_rollout_shadow_comparison,
    run_runtime_rollout_gate,
    runtime_rollout_feature_flags,
)


class RuntimeRolloutGateTests(unittest.TestCase):
    def test_feature_flag_manifest_declares_final_rollout_window(self) -> None:
        manifest = runtime_rollout_feature_flags()
        flag_ids = [item["flag_id"] for item in manifest["flags"]]

        self.assertEqual(manifest["schema_version"], "astrabridge-runtime-rollout-feature-flags-v1")
        self.assertEqual(manifest["status"], "enabled")
        self.assertIn("runtime_client_pool_lane_isolation", flag_ids)
        self.assertIn("protocol_v1_canonical_codegen", flag_ids)
        self.assertIn("durable_scheduler_and_reconciliation", flag_ids)
        self.assertIn("agent_envelope_delivery_ledger", flag_ids)
        self.assertIn("mcp_server_core_and_broker_boundary", flag_ids)
        self.assertIn(".astrabridge/tasks.json", manifest["compatibility_window"]["legacy_read_paths"])

    def test_shadow_migration_and_rollback_evidence_are_self_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime_root = root / "runtime-root"
            with patch.dict(os.environ, {"ASTRABRIDGE_RUNTIME_ROOT": str(runtime_root)}):
                shadow = capture_runtime_rollout_shadow_comparison(output_dir=root / "shadow")
                migration = capture_runtime_rollout_migration_evidence(
                    repo_workspace_root=REPO_ROOT,
                    output_dir=root / "migration",
                    dogfood_source_workspace=REPO_ROOT,
                )
                rollback = capture_runtime_rollout_rollback_readback(output_dir=root / "rollback")

            self.assertEqual(shadow["status"], "pass")
            self.assertEqual(shadow["case_count"], 5)
            self.assertEqual(migration["status"], "pass")
            self.assertIn("recoverable", migration["fixture_workspace"]["classification_summary"]["counts"])
            self.assertEqual(rollback["status"], "pass")
            self.assertEqual(rollback["db_hash_before"], rollback["db_hash_after"])
            self.assertTrue(str(rollback["artifact_paths"]["snapshot_workspace_root"]).endswith("\\r\\w"))

    def test_rollout_gate_writes_summary_with_stubbed_release_gate_and_visual_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_desktop_root = root / "fake-desktop"
            fake_dist = fake_desktop_root / "dist"
            fake_dist.mkdir(parents=True, exist_ok=True)
            (fake_dist / "index.html").write_text("<html><body><h1>AstraBridge</h1></body></html>", encoding="utf-8")

            def fake_command_runner(command: list[str], cwd: Path) -> dict[str, object]:
                if command[:4] == ["cmd", "/c", "npm", "run"]:
                    return {"command": command, "cwd": str(cwd), "returncode": 0, "stdout": "build ok", "stderr": ""}
                if any("capture_astrabridge_page.mjs" in str(item) for item in command):
                    out_path = Path(command[command.index("--out") + 1])
                    report_path = Path(command[command.index("--report") + 1])
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(b"png")
                    report_path.write_text(
                        json.dumps({"ok": True, "screenshot_path": str(out_path), "console_issues": [], "request_failures": []}, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    return {"command": command, "cwd": str(cwd), "returncode": 0, "stdout": "capture ok", "stderr": ""}
                raise AssertionError(f"Unexpected command: {command}")

            def fake_release_gate_runner(**_kwargs: object) -> dict[str, object]:
                return {
                    "schema_version": "astrabridge-runtime-stability-gate-v1",
                    "status": "pass",
                    "artifact_paths": {
                        "run_dir": str(root / "release-gate"),
                        "fault_matrix_json": str(root / "release-gate" / "fault-matrix.json"),
                        "long_horizon_bundle_json": str(root / "release-gate" / "long-horizon-bundle.json"),
                        "injected_chaos_drills_json": str(root / "release-gate" / "injected-chaos-drills.json"),
                    },
                    "fault_matrix": {
                        "schema_version": "astrabridge-runtime-stability-fault-matrix-v1",
                        "status": "pass",
                        "release_ready": True,
                        "case_count": 9,
                        "cases": [{"fault_id": "process_level_kill", "status": "pass"}],
                    },
                    "long_horizon_bundle": {
                        "schema_version": "astrabridge-runtime-stability-long-horizon-bundle-v1",
                        "status": "pass",
                        "release_qualified": True,
                        "bundle_id": "shipping_state_long_horizon_stability",
                        "suite_count": 5,
                        "suite_labels": [
                            "scheduler_recovery_and_idempotency",
                            "terminal_projection_and_stream_recovery",
                            "mcp_timeout_cancel_and_policy_fail_closed",
                            "windows_update_interruption_rehearsal",
                            "supervised_update_policy_and_containment",
                        ],
                    },
                    "injected_chaos_drills": {
                        "schema_version": "astrabridge-runtime-stability-injected-chaos-drills-v1",
                        "status": "pass",
                        "release_qualified": True,
                        "drill_pack_id": "cross_lane_injected_chaos",
                        "drill_count": 1,
                        "drill_labels": [
                            "provider_retry_storm_and_circuit_breaker_chaos",
                        ],
                    },
                }

            with patch.dict(os.environ, {"ASTRABRIDGE_RUNTIME_ROOT": str(root / "runtime-root")}):
                with patch("astrabridge_sidecar.runtime_rollout_gate._DESKTOP_ROOT", fake_desktop_root):
                    summary = run_runtime_rollout_gate(
                        workspace_root=REPO_ROOT,
                        artifact_root=root / "rollout",
                        run_id="unit-rollout",
                        command_runner=fake_command_runner,
                        release_gate_runner=fake_release_gate_runner,
                    )

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["checks"]["release_gate"], "pass")
            self.assertEqual(summary["checks"]["desktop_build"], "pass")
            self.assertEqual(summary["checks"]["desktop_visual_qa"], "pass")
            self.assertEqual(summary["release_fault_matrix"]["status"], "pass")
            self.assertTrue(summary["release_fault_matrix"]["release_ready"])
            self.assertEqual(summary["release_fault_matrix"]["case_count"], 9)
            self.assertEqual(summary["release_long_horizon_bundle"]["status"], "pass")
            self.assertTrue(summary["release_long_horizon_bundle"]["release_qualified"])
            self.assertEqual(summary["release_long_horizon_bundle"]["bundle_id"], "shipping_state_long_horizon_stability")
            self.assertEqual(summary["release_injected_chaos_drills"]["status"], "pass")
            self.assertTrue(summary["release_injected_chaos_drills"]["release_qualified"])
            self.assertEqual(summary["release_injected_chaos_drills"]["drill_pack_id"], "cross_lane_injected_chaos")
            self.assertTrue(Path(summary["artifact_paths"]["summary_json"]).exists())
            self.assertTrue(Path(summary["artifact_paths"]["report_md"]).exists())


if __name__ == "__main__":
    unittest.main()
