from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from astrabridge_sidecar.promotion_gate import run_promotion_gate  # noqa: E402
from scripts.run_local_gate import run_local_gate  # noqa: E402


class LocalGateSummaryTests(unittest.TestCase):
    def test_local_gate_writes_machine_readable_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_root = Path(temp_dir) / "local-gate"

            def fake_runner(command: list[str], cwd: Path, dry_run: bool) -> dict[str, object]:  # noqa: ARG001
                return {"exit_code": 0, "stdout": "ok\n", "stderr": "", "dry_run": dry_run}

            summary = run_local_gate(
                mode="quick",
                artifact_root=artifact_root,
                run_id="unit-local-gate",
                command_runner=fake_runner,
                emit_logs=False,
            )

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["mode"], "quick")
            self.assertEqual(summary["check_count"], 7)
            self.assertTrue(Path(summary["artifact_paths"]["summary_json"]).exists())
            self.assertTrue(Path(summary["artifact_paths"]["report_md"]).exists())
            self.assertTrue(all(check["status"] == "pass" for check in summary["checks"]))


class PromotionGateTests(unittest.TestCase):
    def test_promotion_gate_rejects_unknown_status_and_commit_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested_root = root / "nested" / "fake-check"
            run_id = "fake-check"
            summary_dir = nested_root / run_id / "reports"
            summary_dir.mkdir(parents=True, exist_ok=True)
            summary = {
                "schema_version": "fake-gate-v1",
                "run_id": run_id,
                "status": "pass",
                "checks": {"slo": "unknown"},
                "artifact_paths": {
                    "summary_json": str(summary_dir / "summary.json"),
                    "report_md": str(summary_dir / "report.md"),
                },
            }
            Path(summary["artifact_paths"]["summary_json"]).write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            Path(summary["artifact_paths"]["report_md"]).write_text("# fake\n", encoding="utf-8")

            def fake_runner(command: list[str], cwd: Path) -> dict[str, object]:  # noqa: ARG001
                return {"exit_code": 0, "stdout": json.dumps(summary, ensure_ascii=False), "stderr": ""}

            result = run_promotion_gate(
                mode="pr",
                workspace_root=root,
                artifact_root=root / "promotion",
                run_id="promotion-unit",
                expected_commit="expected-commit",
                command_runner=fake_runner,
                check_specs=[
                    {
                        "check_id": "fake-check",
                        "label": "Fake check",
                        "required": True,
                        "cwd": root,
                        "command": ["python", "fake.py", "--artifact-root", str(nested_root), "--run-id", run_id],
                        "required_status_paths": ("status", "checks.slo"),
                        "required_summary_fields": ("schema_version", "status", "checks", "artifact_paths"),
                        "required_artifact_keys": ("summary_json", "report_md"),
                        "expected_schema_version": "fake-gate-v1",
                    }
                ],
                git_context={
                    "repo_root": str(root),
                    "commit": "actual-commit",
                    "expected_commit": "expected-commit",
                    "branch": "main",
                    "detached_head": False,
                    "dirty": False,
                },
                toolchain_versions={"python": {"status": "pass", "version": "Python 3.12.0"}},
            )

            self.assertEqual(result["status"], "fail")
            self.assertTrue(any("required status path `checks.slo` is `unknown`" in item for item in result["promotion_errors"]))
            self.assertTrue(any("tested commit does not match" in item for item in result["promotion_errors"]))

    def test_promotion_gate_rejects_missing_or_forged_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested_root = root / "nested" / "fake-check"
            run_id = "fake-check"
            summary_dir = nested_root / run_id / "reports"
            summary_dir.mkdir(parents=True, exist_ok=True)
            forged_stdout = {
                "schema_version": "fake-gate-v1",
                "run_id": run_id,
                "status": "pass",
                "artifact_paths": {
                    "summary_json": str(summary_dir / "summary.json"),
                    "report_md": str(summary_dir / "report.md"),
                },
            }
            persisted_summary = {
                "schema_version": "fake-gate-v1",
                "run_id": run_id,
                "status": "fail",
                "artifact_paths": forged_stdout["artifact_paths"],
            }
            Path(forged_stdout["artifact_paths"]["summary_json"]).write_text(
                json.dumps(persisted_summary, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            def fake_runner(command: list[str], cwd: Path) -> dict[str, object]:  # noqa: ARG001
                return {"exit_code": 0, "stdout": json.dumps(forged_stdout, ensure_ascii=False), "stderr": ""}

            result = run_promotion_gate(
                mode="pr",
                workspace_root=root,
                artifact_root=root / "promotion",
                run_id="promotion-unit",
                command_runner=fake_runner,
                check_specs=[
                    {
                        "check_id": "fake-check",
                        "label": "Fake check",
                        "required": True,
                        "cwd": root,
                        "command": ["python", "fake.py", "--artifact-root", str(nested_root), "--run-id", run_id],
                        "required_status_paths": ("status",),
                        "required_summary_fields": ("schema_version", "status", "artifact_paths"),
                        "required_artifact_keys": ("summary_json", "report_md"),
                        "expected_schema_version": "fake-gate-v1",
                    }
                ],
                git_context={
                    "repo_root": str(root),
                    "commit": "actual-commit",
                    "expected_commit": "actual-commit",
                    "branch": "main",
                    "detached_head": False,
                    "dirty": False,
                },
                toolchain_versions={"python": {"status": "pass", "version": "Python 3.12.0"}},
            )

            self.assertEqual(result["status"], "fail")
            check = result["checks"][0]
            self.assertEqual(check["status"], "fail")
            self.assertTrue(any("required report_md artifact is missing" in item for item in check["failures"]))
            self.assertTrue(any("stdout summary does not match persisted summary.json" in item for item in check["failures"]))


if __name__ == "__main__":
    unittest.main()
