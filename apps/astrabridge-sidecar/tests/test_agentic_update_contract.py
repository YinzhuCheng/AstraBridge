from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import (
    AGENTIC_UPDATE_CONTRACT_SCHEMA_VERSION,
    AGENTIC_UPDATE_PROPOSAL_SCHEMA_VERSION,
    agentic_update_proposal_template,
    agentic_update_schema_definitions,
    normalize_update_scope_contract,
    validate_update_proposal,
)
from astrabridge_sidecar.security import SecurityError


class AgenticUpdateContractTests(unittest.TestCase):
    def test_valid_scope_contract_defaults_to_proposal_only(self) -> None:
        contract = normalize_update_scope_contract(
            {
                "scope": "provider_metadata",
                "providers": ["qwen", "qwen"],
                "version_policy": "stable",
            }
        )

        self.assertEqual(contract["schema_version"], AGENTIC_UPDATE_CONTRACT_SCHEMA_VERSION)
        self.assertEqual(contract["scope"], ["provider_metadata"])
        self.assertEqual(contract["providers"], ["qwen"])
        self.assertEqual(contract["version_policy"], "stable")
        self.assertEqual(contract["apply_mode"], "proposal_only")
        self.assertTrue(contract["allow_network"])
        self.assertFalse(contract["allow_provider_calls"])
        self.assertFalse(contract["allow_install"])
        self.assertFalse(contract["allow_code_changes"])
        self.assertEqual(contract["approval_policy"], "manual_review_required")

    def test_invalid_scope_contracts_are_rejected(self) -> None:
        cases = [
            {"scope": "unsupported_scope"},
            {"scope": "provider_metadata", "version_policy": "nightly"},
            {"scope": "provider_metadata", "apply_mode": "auto_apply"},
            {"scope": []},
        ]

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises((TypeError, ValueError)):
                    normalize_update_scope_contract(payload)

    def test_pinned_policy_requires_target_version(self) -> None:
        with self.assertRaises(ValueError):
            normalize_update_scope_contract({"scope": "codex_kernel", "version_policy": "pinned"})

        contract = normalize_update_scope_contract(
            {"scope": "codex_kernel", "version_policy": "pinned", "target_version": "codex-v1.2.3"}
        )
        self.assertEqual(contract["target_version"], "codex-v1.2.3")

    def test_unsafe_authorization_combinations_are_rejected(self) -> None:
        cases = [
            {
                "scope": "provider_metadata",
                "allow_provider_calls": True,
                "apply_mode": "proposal_only",
            },
            {
                "scope": "provider_metadata",
                "allow_provider_calls": True,
                "allow_network": False,
                "apply_mode": "verify_candidate",
            },
            {
                "scope": "provider_metadata",
                "allow_install": True,
                "apply_mode": "verify_candidate",
            },
            {
                "scope": "provider_adapter",
                "allow_code_changes": True,
                "apply_mode": "proposal_only",
            },
            {
                "scope": "provider_adapter",
                "allow_code_changes": True,
                "apply_mode": "isolated_apply",
                "approval_policy": "preapproved_discovery_only",
            },
        ]

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    normalize_update_scope_contract(payload)

    def test_secret_like_fields_and_raw_payloads_are_rejected(self) -> None:
        cases = [
            {"scope": "provider_metadata", "api_key": "sk-" + ("a" * 24)},
            {"scope": "provider_metadata", "notes": ["Authorization: Bearer abcdefghijklmnopqrstuvwxyz"]},
            {"scope": "provider_metadata", "raw_response": {"body": "large upstream response"}},
            {"scope": "provider_metadata", "notes": [r"C:\Users\cyz19\Desktop\key.txt"]},
            {"scope": "provider_metadata", "notes": ["data:image/png;base64,abcdef"]},
        ]

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(SecurityError):
                    normalize_update_scope_contract(payload)

    def test_schema_definitions_cover_required_artifacts(self) -> None:
        definitions = agentic_update_schema_definitions()["definitions"]

        for name in (
            "update_request",
            "normalized_scope_contract",
            "discovery_result",
            "proposal",
            "diff",
            "validation_result",
            "approval_state",
            "apply_manifest",
            "rollback_manifest",
        ):
            self.assertIn(name, definitions)

    def test_fixture_proposal_validates_without_network_or_provider_keys(self) -> None:
        proposal = agentic_update_proposal_template(
            {
                "scope": ["provider_metadata", "docs_only"],
                "providers": ["qwen"],
                "models": ["qwen3-vl-plus"],
                "version_policy": "stable",
                "allow_network": False,
                "apply_mode": "proposal_only",
            },
            run_id="fixture-agentic-update",
            created_at="2026-07-05T00:00:00+00:00",
        )
        proposal["discovery_result"]["sources"].append(
            {
                "source_id": "fixture-qwen-doc",
                "source_url": "fixtures/provider-docs/qwen-models.html",
                "trust": "fixture",
                "content_hash": "sha256:fixture",
                "short_excerpt": "Qwen fixture model metadata for offline validation.",
            }
        )
        proposal["discovery_result"]["findings"].append(
            {
                "provider_id": "qwen",
                "model_id": "qwen3-vl-plus",
                "classification": "unchanged",
            }
        )
        proposal["diff"]["status"] = "empty"
        proposal["validation_result"]["status"] = "skipped"
        proposal["validation_result"]["gates"].append(
            {
                "gate_id": "fixture-only",
                "status": "skipped",
                "reason": "No network or provider keys required.",
            }
        )

        validated = validate_update_proposal(proposal)

        self.assertEqual(validated["schema_version"], AGENTIC_UPDATE_PROPOSAL_SCHEMA_VERSION)
        self.assertEqual(validated["run_id"], "fixture-agentic-update")
        self.assertFalse(validated["run_contract"]["allow_network"])
        self.assertFalse(validated["run_contract"]["allow_provider_calls"])
        self.assertEqual(validated["validation_result"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
