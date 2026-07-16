from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import (
    AGENTIC_UPDATE_DIFF_SCHEMA_VERSION,
    build_agentic_update_diff,
)


class AgenticUpdateDiffingTests(unittest.TestCase):
    def test_diff_covers_add_change_remove_and_deprecate_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diff = build_agentic_update_diff(
                workspace_root=Path(temp_dir),
                run_id="diff-cases",
                run_contract={
                    "scope": "provider_metadata",
                    "providers": ["qwen"],
                    "allow_network": False,
                },
                parser_output={
                    "proposals": [
                        _proposal("qwen/new-text-model", context=128000),
                        _proposal("qwen/context-change", context=1000000),
                        _proposal("qwen/pricing-change", pricing_input=0.2, pricing_output=0.8),
                        _proposal("qwen/deprecate-me", deprecated=True, deprecated_after="2026-08-01T00:00:00+00:00"),
                    ]
                },
                current_models=[
                    _current("qwen/context-change", context=128000),
                    _current("qwen/pricing-change", pricing_input=0.1, pricing_output=0.4),
                    _current("qwen/deprecate-me", deprecated=False),
                    _current("qwen/remove-me"),
                ],
                complete_provider_snapshot=True,
                update_proposal=False,
            )

        changes = {change["change_type"]: change for change in diff["changes"]}

        self.assertEqual(diff["schema_version"], AGENTIC_UPDATE_DIFF_SCHEMA_VERSION)
        self.assertEqual(diff["risk_class"], "blocked_manual_review")
        self.assertEqual(changes["added_model"]["risk_class"], "metadata_only")
        self.assertEqual(changes["changed_context_window"]["risk_class"], "requires_provider_smoke")
        self.assertEqual(changes["changed_pricing"]["risk_class"], "docs_only")
        self.assertEqual(changes["deprecated_model"]["risk_class"], "metadata_only")
        self.assertEqual(changes["removed_model"]["risk_class"], "blocked_manual_review")
        self.assertIn("provider_compatibility_smoke", changes["changed_context_window"]["validation_requirements"])

    def test_risk_classification_is_conservative_for_capabilities_and_long_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diff = build_agentic_update_diff(
                workspace_root=Path(temp_dir),
                run_id="risky-claims",
                run_contract={
                    "scope": "provider_metadata",
                    "providers": ["qwen"],
                    "allow_network": False,
                },
                parser_output={
                    "proposals": [
                        _proposal(
                            "qwen/risky",
                            context=1000000,
                            modalities=["text", "image", "audio"],
                            claims={
                                "tool_calls": True,
                                "web_search": True,
                                "vision": True,
                                "audio": True,
                                "apply_patch": True,
                            },
                        )
                    ]
                },
                current_models=[],
                update_proposal=False,
            )

        change = diff["changes"][0]
        reasons = set(change["reasons"])

        self.assertEqual(change["risk_class"], "requires_provider_smoke")
        self.assertIn("long_context_claim_requires_provider_smoke", reasons)
        self.assertIn("image_modality_requires_provider_smoke", reasons)
        self.assertIn("audio_modality_requires_provider_smoke", reasons)
        self.assertIn("unverified_tool_calls_claim", reasons)
        self.assertIn("unverified_web_search_claim", reasons)
        self.assertIn("unverified_apply_patch_claim", reasons)
        self.assertIn("provider_compatibility_smoke", change["validation_requirements"])

    def test_generated_markdown_points_to_source_evidence_and_current_state_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            diff = build_agentic_update_diff(
                workspace_root=workspace,
                run_id="markdown-evidence",
                run_contract={
                    "scope": "provider_metadata",
                    "providers": ["qwen"],
                    "allow_network": False,
                },
                parser_output={"proposals": [_proposal("qwen/existing", context=1000000, source_id="official-qwen", content_hash="sha256:evidence")]},
                current_models=[_current("qwen/existing", context=128000, source_url="https://help.aliyun.com/zh/model-studio/models")],
                update_proposal=False,
            )

            markdown_path = Path(diff["artifact_paths"]["proposal_markdown"])
            markdown = markdown_path.read_text(encoding="utf-8")
            markdown_exists = markdown_path.exists()
            diff_exists = Path(diff["artifact_paths"]["proposal_diff"]).exists()

        self.assertTrue(diff_exists)
        self.assertTrue(markdown_exists)
        self.assertIn("official-qwen sha256:evidence", markdown)
        self.assertIn("effective_model_record:qwen/existing", markdown)
        self.assertIn("current_source_url:https://help.aliyun.com/zh/model-studio/models", markdown)

    def test_codex_kernel_candidates_require_kernel_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            diff = build_agentic_update_diff(
                workspace_root=Path(temp_dir),
                run_id="kernel-diff",
                run_contract={
                    "scope": "codex_kernel",
                    "version_policy": "pinned",
                    "target_version": "0.138.0",
                    "allow_network": False,
                },
                kernel_candidate_output={
                    "candidates": [
                        {
                            "candidate_id": "codex-kernel-0.138.0-0",
                            "version": "0.138.0",
                            "release_date": "2026-07-01",
                            "platforms": ["windows-x64"],
                            "distribution": {"install_hint": "npm install -g @openai/codex@0.138.0"},
                            "source_refs": [
                                {
                                    "source_id": "openai-codex-github-releases",
                                    "source_url": "https://github.com/openai/codex/releases",
                                    "content_hash": "sha256:kernel",
                                }
                            ],
                        }
                    ]
                },
                current_models=[],
                update_proposal=False,
            )

        self.assertEqual(diff["risk_class"], "requires_kernel_smoke")
        self.assertEqual(diff["changes"][0]["change_type"], "codex_kernel_candidate")
        self.assertIn("codex_kernel_probe", diff["changes"][0]["validation_requirements"])
        self.assertIn("codex_kernel_smoke", diff["changes"][0]["validation_requirements"])

    def test_missing_candidate_metadata_does_not_clear_existing_model_fields(self) -> None:
        candidate = _proposal("qwen/qwen3.7-plus", context=None, pricing_input=None, pricing_output=None)
        candidate["candidate_metadata"]["supported_reasoning_levels"] = []
        candidate["candidate_metadata"]["default_reasoning_level"] = None
        candidate["candidate_metadata"]["pricing"] = {
            "input_per_mtok": None,
            "output_per_mtok": None,
            "currency": None,
            "status": "parsed_unvalidated",
        }
        candidate["warnings"] = [
            "missing_context_window_defaulted_unknown",
            "missing_reasoning_modes_defaulted_empty",
            "requires_validation_before_promotion",
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            diff = build_agentic_update_diff(
                workspace_root=Path(temp_dir),
                run_id="missing-fields",
                run_contract={
                    "scope": "provider_metadata",
                    "providers": ["qwen"],
                    "allow_network": False,
                },
                parser_output={"proposals": [candidate]},
                current_models=[_current("qwen/qwen3.7-plus", context=1000000, pricing_input=0.2, pricing_output=0.8)],
                update_proposal=False,
            )

        self.assertEqual(diff["summary"]["provider_model_candidate_count"], 1)
        self.assertEqual(diff["changes"], [])
        self.assertEqual(diff["status"], "empty")


def _proposal(
    model_id: str,
    *,
    context: int | None = 128000,
    modalities: list[str] | None = None,
    reasoning: list[str] | None = None,
    default_reasoning: str = "low",
    pricing_input: float | None = 0.1,
    pricing_output: float | None = 0.4,
    deprecated: bool = False,
    deprecated_after: str | None = None,
    claims: dict[str, bool] | None = None,
    source_id: str = "fixture-source",
    content_hash: str = "sha256:fixture",
) -> dict[str, object]:
    provider, native = model_id.split("/", 1)
    declared_claims = claims or {}
    return {
        "proposal_id": f"{provider}-{native}",
        "provider_id": provider,
        "model_id": model_id,
        "native_model": native,
        "display_name": native,
        "candidate_metadata": {
            "advertised_context_window": context,
            "input_modalities": modalities or ["text"],
            "supported_reasoning_levels": reasoning or ["low"],
            "default_reasoning_level": default_reasoning,
            "pricing": {"input_per_mtok": pricing_input, "output_per_mtok": pricing_output, "currency": "USD"},
            "deprecated": deprecated,
            "deprecated_after": deprecated_after,
            "default_for_provider": False,
            "recommended": False,
            "confidence": "high",
        },
        "capability_claims": {
            name: {
                "declared": bool(declared_claims.get(name, False)),
                "claim_status": "unverified_claim" if declared_claims.get(name, False) else "not_declared",
                "validation_status": "requires_validation" if declared_claims.get(name, False) else "not_validated",
                "verified": False,
            }
            for name in ("tool_calls", "web_search", "vision", "audio", "apply_patch")
        },
        "source_refs": [
            {
                "source_id": source_id,
                "source_url": "https://example.test/source",
                "content_hash": content_hash,
                "parser_strategy": "json_api",
            }
        ],
        "warnings": [],
    }


def _current(
    model_id: str,
    *,
    context: int = 128000,
    pricing_input: float = 0.1,
    pricing_output: float = 0.4,
    deprecated: bool = False,
    source_url: str = "https://example.test/current",
) -> dict[str, object]:
    provider, native = model_id.split("/", 1)
    return {
        "id": model_id,
        "provider": provider,
        "native_model": native,
        "display_name": native,
        "advertised_context_window": context,
        "input_modalities": ["text"],
        "supported_reasoning_levels": ["low"],
        "default_reasoning_level": "low",
        "pricing_input_per_mtok": pricing_input,
        "pricing_output_per_mtok": pricing_output,
        "pricing_currency": "USD",
        "deprecated": deprecated,
        "default_for_provider": False,
        "recommended": False,
        "source_urls": [source_url],
        "source_provenance": {
            "provider_id": provider,
            "source_url": source_url,
            "source_status": "official_docs",
            "trust_level": "official",
        },
    }


if __name__ == "__main__":
    unittest.main()
