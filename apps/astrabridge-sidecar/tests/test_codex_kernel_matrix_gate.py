from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_kernel_matrix_gate import validate_compatibility_matrix


class CodexKernelMatrixGateTests(unittest.TestCase):
    def test_validator_allows_verified_entry_with_existing_probe_and_smoke_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._touch(repo_root / "PRIVATE/demo-runs/codex-kernel-smoke-1/reports/smoke-report.json")
            self._touch(repo_root / "PRIVATE/demo-runs/codex-kernel-smoke-1/reports/kernel-probe-snapshot.json")
            self._touch(repo_root / "PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md")
            matrix_path = repo_root / "PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md"
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix_path.write_text(
                self._entry_text(
                    matrix_id="AB-CODEX-TEST-VERIFIED",
                    codex_version="0.137.0",
                    overall_status="verified",
                    smoke_result="passed",
                    binary_locator=r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                    evidence_paths=[
                        "PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md",
                        "PRIVATE/demo-runs/codex-kernel-smoke-1/reports/smoke-report.json",
                        "PRIVATE/demo-runs/codex-kernel-smoke-1/reports/kernel-probe-snapshot.json",
                    ],
                ),
                encoding="utf-8",
            )

            report = validate_compatibility_matrix(
                matrix_path=matrix_path,
                repo_root=repo_root,
            )

            self.assertTrue(report["ok"])
            self.assertEqual(report["error_count"], 0)
            self.assertEqual(report["entries"][0]["verified_gate"], "passed")

    def test_validator_rejects_verified_entry_without_smoke_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._touch(repo_root / "PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md")
            self._touch(repo_root / "PRIVATE/demo-runs/codex-kernel-smoke-1/reports/kernel-probe-snapshot.json")
            matrix_path = repo_root / "PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md"
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix_path.write_text(
                self._entry_text(
                    matrix_id="AB-CODEX-TEST-NO-SMOKE",
                    codex_version="0.137.0",
                    overall_status="verified",
                    smoke_result="passed",
                    binary_locator=r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                    evidence_paths=[
                        "PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md",
                        "PRIVATE/demo-runs/codex-kernel-smoke-1/reports/kernel-probe-snapshot.json",
                    ],
                ),
                encoding="utf-8",
            )

            report = validate_compatibility_matrix(
                matrix_path=matrix_path,
                repo_root=repo_root,
            )

            self.assertFalse(report["ok"])
            self.assertTrue(
                any(
                    issue["field"] == "evidence_paths" and "smoke report" in issue["message"]
                    for issue in report["issues"]
                )
            )

    def test_validator_rejects_missing_evidence_reference_for_nonverified_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            matrix_path = repo_root / "PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md"
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix_path.write_text(
                self._entry_text(
                    matrix_id="AB-CODEX-TEST-PROBED",
                    codex_version="0.137.0 target line",
                    overall_status="probed",
                    smoke_result="not_run",
                    binary_locator="ASTRABRIDGE_WSL_CODEX_BIN",
                    evidence_paths=["PRIVATE/demo-runs/missing/smoke-report.json"],
                ),
                encoding="utf-8",
            )

            report = validate_compatibility_matrix(
                matrix_path=matrix_path,
                repo_root=repo_root,
            )

            self.assertFalse(report["ok"])
            self.assertTrue(
                any(
                    issue["field"] == "evidence_paths" and "does not exist" in issue["message"]
                    for issue in report["issues"]
                )
            )

    def test_validator_allows_probed_entry_without_smoke_when_other_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            self._touch(repo_root / "PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md")
            matrix_path = repo_root / "PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md"
            matrix_path.parent.mkdir(parents=True, exist_ok=True)
            matrix_path.write_text(
                self._entry_text(
                    matrix_id="AB-CODEX-TEST-PROBED-OK",
                    codex_version="0.137.0 target line",
                    overall_status="probed",
                    smoke_result="not_run",
                    binary_locator="ASTRABRIDGE_WSL_CODEX_BIN",
                    evidence_paths=["PLAN/CODEX_KERNEL_PLUGIN_SKILL_INTEGRATION_PLAN.md"],
                ),
                encoding="utf-8",
            )

            report = validate_compatibility_matrix(
                matrix_path=matrix_path,
                repo_root=repo_root,
            )

            self.assertTrue(report["ok"])
            self.assertEqual(report["entries"][0]["verified_gate"], "not_applicable")

    def _touch(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    def _entry_text(
        self,
        *,
        matrix_id: str,
        codex_version: str,
        overall_status: str,
        smoke_result: str,
        binary_locator: str,
        evidence_paths: list[str],
    ) -> str:
        evidence_block = "\n".join(f"  - `{item}`" for item in evidence_paths)
        return f"""# Codex Kernel Compatibility Matrix

### `{matrix_id}`

- `matrix_id`: `{matrix_id}`
- `codex_version`: `{codex_version}`
- `release_anchor`: `codex-cli 0.137.0`
- `platform`: `windows`
- `execution_lane`: `Test lane`
- `binary_locator`: `{binary_locator}`
- `overall_status`: `{overall_status}`
- `probe_result`: `Probe summary`
- `smoke_result`: `{smoke_result}`
- `known_breakages`:
  - `none recorded`
- `required_mitigations`:
  - `none`
- `evidence_paths`:
{evidence_block}
- `last_reviewed_at`: `2026-06-25`
"""


if __name__ == "__main__":
    unittest.main()
