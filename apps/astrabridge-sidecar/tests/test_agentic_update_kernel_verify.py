from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import agentic_update_proposal_template
from astrabridge_sidecar.agentic_updates.kernel_verify import run_agentic_update_kernel_candidate_verification
from astrabridge_sidecar.common import write_json


class AgenticUpdateKernelVerifyTests(unittest.TestCase):
    def test_existing_binary_mode_uses_isolated_artifact_root_and_matrix_suggestion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            calls: list[dict[str, Any]] = []

            def fake_smoke_runner(**kwargs: Any) -> dict[str, Any]:
                artifact_root = Path(kwargs["artifact_root"])
                binary = {
                    "execution_host": "windows",
                    "wsl_distro": None,
                    "path": os.environ.get("ASTRABRIDGE_CODEX_BIN"),
                    "path_source": "env_override",
                    "launch_descriptor": os.environ.get("ASTRABRIDGE_CODEX_BIN"),
                    "version_text": "codex-cli 0.138.0",
                    "version_semver": "0.138.0",
                    "version_parse_status": "ok",
                    "version_error": None,
                }
                calls.append({"artifact_root": str(artifact_root), "binary": binary})
                reports_dir = artifact_root / "reports"
                smoke_path = reports_dir / "smoke-report.json"
                probe_path = reports_dir / "kernel-probe-snapshot.json"
                report = {
                    "schema_version": "codex-kernel-smoke-v1",
                    "artifact_root": str(artifact_root),
                    "workspace_root": str(artifact_root / "workspace"),
                    "project_file": str(artifact_root / "project" / "kernel.abproj"),
                    "report_path": str(smoke_path),
                    "kernel_probe_snapshot_path": str(probe_path),
                    "summary": {"overall_status": "pass", "critical_failures": []},
                    "checks": [
                        {
                            "check_id": "binary_discovery",
                            "status": "pass",
                            "critical": True,
                            "details": {
                                **binary,
                                "version_text": "codex-cli 0.138.0",
                                "version_semver": "0.138.0",
                                "version_parse_status": "ok",
                            },
                        }
                    ],
                }
                write_json(probe_path, {"observed": {"binary": report["checks"][0]["details"]}})
                write_json(smoke_path, report)
                return report

            report = run_agentic_update_kernel_candidate_verification(
                workspace_root=workspace,
                run_id="kernel-existing",
                proposal=_kernel_candidate_proposal(run_id="kernel-existing", version="0.138.0"),
                mode="existing_binary",
                binary_locator=r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                kernel_smoke_runner=fake_smoke_runner,
            )

            self.assertEqual(report["status"], "verified")
            self.assertTrue(report["verified"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["binary"]["path"], r"D:\Tools\OpenAI\Codex\bin\codex.exe")
            self.assertTrue(Path(report["artifact_paths"]["smoke_report"]).exists())
            self.assertTrue(Path(report["artifact_paths"]["kernel_probe_snapshot"]).exists())
            self.assertTrue(Path(report["artifact_paths"]["apply_journal"]).exists())
            journal = Path(report["artifact_paths"]["apply_journal"]).read_text(encoding="utf-8")
            self.assertIn('"track_id": "codex_kernel_candidate"', journal)
            self.assertIn('"status": "committed"', journal)
            self.assertTrue(report["activation"]["restored_runtime_state"])
            self.assertIn("PRIVATE/agentic-update-pipeline/runs/kernel-existing", report["matrix_update_suggestion"]["evidence_paths"][0])
            self.assertFalse((workspace / ".codex").exists())
            self.assertFalse((workspace / ".astrabridge").exists())


def _kernel_candidate_proposal(*, run_id: str, version: str) -> dict[str, Any]:
    contract = {
        "scope": "codex_kernel",
        "version_policy": "pinned",
        "target_version": version,
        "allow_network": False,
        "apply_mode": "verify_candidate",
    }
    proposal = agentic_update_proposal_template(contract, run_id=run_id)
    candidate = {
        "candidate_id": f"codex-kernel-{version}",
        "kind": "codex_kernel_candidate",
        "version": version,
        "release_date": "2026-07-01",
        "platforms": ["windows-x64"],
        "distribution": {
            "download_url": "https://github.com/openai/codex/releases/download/rust-v0.138.0/codex.zip",
            "install_hint": "npm install -g @openai/codex@0.138.0",
            "changelog_url": "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
        },
        "source_refs": [],
        "permission_policy": {"install_allowed": False, "switch_allowed": False, "apply_mode": "verify_candidate"},
        "side_effect_policy": {
            "writes_official_codex_config": False,
            "writes_project_codex_files": False,
            "writes_astrabridge_runtime_config": False,
            "installs_binary": False,
            "switches_binary": False,
        },
        "validation_state": {
            "status": "requires_kernel_probe_and_smoke",
            "verified": False,
            "probe_evidence_paths": [],
            "smoke_evidence_paths": [],
        },
        "promotion_state": {"status": "blocked_until_validation", "recommended": False, "requires_manual_review": True},
        "warnings": [],
    }
    proposal["discovery_result"]["findings"] = [candidate]
    proposal["diff"] = {
        "schema_version": "astrabridge-agentic-update-diff-v1",
        "status": "changes_detected",
        "risk_class": "requires_kernel_smoke",
        "summary": {"change_count": 1, "risk_counts": {"requires_kernel_smoke": 1}, "kernel_candidate_count": 1},
        "changes": [
            {
                "change_id": f"codex-kernel-candidate-{version}",
                "change_type": "codex_kernel_candidate",
                "risk_class": "requires_kernel_smoke",
                "target": version,
                "reasons": ["codex_kernel_candidates_require_probe_and_smoke"],
                "details": {"candidate": candidate},
                "source_refs": [],
                "current_state_refs": [],
                "validation_requirements": ["codex_kernel_probe", "codex_kernel_smoke"],
            }
        ],
        "warnings": [],
        "artifact_paths": {},
    }
    return proposal


if __name__ == "__main__":
    unittest.main()
