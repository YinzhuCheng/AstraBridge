from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import (
    AGENTIC_UPDATE_KERNEL_CANDIDATE_SCHEMA_VERSION,
    CODEX_KERNEL_RELEASE_SOURCE_SCHEMA_VERSION,
    KERNEL_CANDIDATE_RELATIVE_PATH,
    codex_kernel_release_sources,
    discover_codex_kernel_candidates,
    kernel_candidates_to_update_proposal,
    validate_update_proposal,
)


class AgenticUpdateKernelCandidateTests(unittest.TestCase):
    def test_fixture_kernel_candidate_discovery_writes_candidates_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            result = discover_codex_kernel_candidates(
                workspace_root=workspace,
                run_id="kernel-fixture",
                run_contract={
                    "scope": "codex_kernel",
                    "version_policy": "pinned",
                    "target_version": "0.138.0",
                    "allow_network": False,
                    "apply_mode": "proposal_only",
                },
                source_records=[
                    _source(
                        "fixture-release",
                        "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
                        parser_strategy="github_releases",
                    )
                ],
                fixture_sources={
                    "fixture-release": {
                        "content_type": "application/json",
                        "body": json.dumps(
                            {
                                "candidates": [
                                    {
                                        "version": "rust-v0.138.0",
                                        "release_date": "2026-07-01",
                                        "platforms": ["windows-x64", "linux-x64"],
                                        "download_url": "https://github.com/openai/codex/releases/download/rust-v0.138.0/codex.zip",
                                        "install_hint": "npm install -g @openai/codex@0.138.0",
                                        "changelog_url": "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
                                        "release_notes": "Fixture release notes for offline candidate discovery.",
                                    }
                                ]
                            }
                        ),
                    }
                },
            )

            candidate = result["candidates"][0]
            self.assertEqual(result["schema_version"], AGENTIC_UPDATE_KERNEL_CANDIDATE_SCHEMA_VERSION)
            self.assertEqual(result["summary"]["status"], "discovered")
            self.assertEqual(candidate["version"], "0.138.0")
            self.assertEqual(candidate["release_date"], "2026-07-01")
            self.assertEqual(candidate["platforms"], ["windows-x64", "linux-x64"])
            self.assertFalse(candidate["permission_policy"]["install_allowed"])
            self.assertFalse(candidate["permission_policy"]["switch_allowed"])
            self.assertEqual(
                candidate["side_effect_policy"],
                {
                    "writes_official_codex_config": False,
                    "writes_project_codex_files": False,
                    "writes_astrabridge_runtime_config": False,
                    "installs_binary": False,
                    "switches_binary": False,
                },
            )
            self.assertTrue((workspace / "PRIVATE" / "agentic-update-pipeline" / "runs" / "kernel-fixture" / KERNEL_CANDIDATE_RELATIVE_PATH).exists())
            self.assertTrue(Path(result["artifact_paths"]["proposal"]).exists())
            self.assertFalse((workspace / ".codex").exists())
            self.assertFalse((workspace / ".astrabridge").exists())
            self.assertFalse((workspace / "runtime-config.json").exists())

    def test_candidate_can_be_represented_in_update_proposal_schema(self) -> None:
        candidate = _candidate("0.138.0")
        proposal = kernel_candidates_to_update_proposal(
            run_contract={
                "scope": "codex_kernel",
                "version_policy": "pinned",
                "target_version": "0.138.0",
                "allow_network": False,
                "apply_mode": "proposal_only",
            },
            run_id="kernel-proposal",
            candidates=[candidate],
            sources=[_source_summary("fixture-release")],
            mode="fixture",
            warnings=[],
        )

        validated = validate_update_proposal(proposal)

        self.assertEqual(validated["discovery_result"]["findings"][0]["kind"], "codex_kernel_candidate")
        self.assertEqual(validated["discovery_result"]["findings"][0]["version"], "0.138.0")
        self.assertEqual(validated["diff"]["status"], "not_generated")
        self.assertEqual(validated["validation_result"]["status"], "not_run")
        self.assertEqual(validated["apply_manifest"]["changed_paths"], [])
        self.assertTrue(validated["rollback_manifest"]["reversible"])

    def test_install_authorization_only_changes_permission_flag_not_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            result = discover_codex_kernel_candidates(
                workspace_root=workspace,
                run_id="install-authorized",
                run_contract={
                    "scope": "codex_kernel",
                    "version_policy": "pinned",
                    "target_version": "0.138.0",
                    "apply_mode": "verify_candidate",
                    "allow_install": True,
                },
                source_records=[_source("fixture-release", "https://github.com/openai/codex/releases/tag/rust-v0.138.0")],
                fixture_sources={
                    "fixture-release": {
                        "candidates": [
                            {
                                "version": "0.138.0",
                                "platforms": "windows-x64, linux-x64",
                                "install_hint": "npm install -g @openai/codex@0.138.0",
                            }
                        ]
                    }
                },
            )

            candidate = result["candidates"][0]
            self.assertTrue(candidate["permission_policy"]["install_allowed"])
            self.assertFalse(candidate["permission_policy"]["switch_allowed"])
            self.assertFalse(candidate["side_effect_policy"]["installs_binary"])
            self.assertFalse(candidate["side_effect_policy"]["switches_binary"])
            self.assertFalse(candidate["side_effect_policy"]["writes_official_codex_config"])
            self.assertFalse((workspace / ".codex").exists())
            self.assertFalse((workspace / ".astrabridge").exists())

    def test_fixture_parser_defaults_and_warnings_for_partial_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = discover_codex_kernel_candidates(
                workspace_root=Path(temp_dir),
                run_id="partial-candidate",
                run_contract={
                    "scope": "codex_kernel",
                    "version_policy": "pinned",
                    "target_version": "0.139.0",
                    "allow_network": False,
                },
                source_records=[_source("line-release", "https://github.com/openai/codex/releases/tag/rust-v0.139.0")],
                fixture_sources={
                    "line-release": "version: rust-v0.139.0 | notes: partial fixture candidate",
                },
            )

            candidate = result["candidates"][0]
            self.assertEqual(candidate["version"], "0.139.0")
            self.assertEqual(candidate["platforms"], [])
            self.assertIsNone(candidate["release_date"])
            self.assertIn("missing_release_date", candidate["warnings"])
            self.assertIn("missing_platforms", candidate["warnings"])
            self.assertFalse(candidate["validation_state"]["verified"])
            self.assertEqual(candidate["promotion_state"]["status"], "blocked_until_validation")

    def test_official_release_sources_are_declared(self) -> None:
        sources = codex_kernel_release_sources()
        urls = {source["url"] for source in sources}

        self.assertIn("https://github.com/openai/codex/releases", urls)
        self.assertIn("https://github.com/openai/codex", urls)
        self.assertIn("https://www.npmjs.com/package/@openai/codex", urls)
        self.assertIn("https://chatgpt.com/codex/install.sh", urls)
        for source in sources:
            self.assertEqual(source["schema_version"], CODEX_KERNEL_RELEASE_SOURCE_SCHEMA_VERSION)
            self.assertEqual(source["trust_level"], "official")
            self.assertIn("parser_strategy", source)


def _source(source_id: str, url: str, *, parser_strategy: str = "manual_review") -> dict[str, object]:
    return {
        "source_id": source_id,
        "url": url,
        "source_type": "release_notes",
        "trust_level": "official",
        "channel": "release_notes",
        "parser_strategy": parser_strategy,
        "stale_after_days": 7,
        "promotable": True,
    }


def _source_summary(source_id: str) -> dict[str, object]:
    return {
        "source_id": source_id,
        "url": "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
        "trust_level": "official",
        "channel": "release_notes",
        "parser_strategy": "github_releases",
        "content_hash": "sha256:fixture",
        "status_label": "ok",
        "excerpt": "Fixture release metadata.",
    }


def _candidate(version: str) -> dict[str, object]:
    return {
        "candidate_id": "codex-kernel-fixture-0",
        "version": version,
        "release_date": "2026-07-01",
        "platforms": ["windows-x64"],
        "distribution": {
            "download_url": "https://github.com/openai/codex/releases/download/rust-v0.138.0/codex.zip",
            "install_hint": "npm install -g @openai/codex@0.138.0",
            "changelog_url": "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
        },
        "source_refs": [
            {
                "source_id": "fixture-release",
                "source_url": "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
                "content_hash": "sha256:fixture",
                "parser_strategy": "github_releases",
            }
        ],
        "permission_policy": {
            "install_allowed": False,
            "switch_allowed": False,
            "apply_mode": "proposal_only",
        },
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
        "promotion_state": {
            "status": "blocked_until_validation",
            "recommended": False,
            "requires_manual_review": True,
        },
        "warnings": [],
    }


if __name__ == "__main__":
    unittest.main()
