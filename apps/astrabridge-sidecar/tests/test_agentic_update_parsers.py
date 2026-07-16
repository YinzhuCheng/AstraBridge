from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import (
    AGENTIC_UPDATE_PARSER_OUTPUT_SCHEMA_VERSION,
    QWEN_OFFICIAL_DOCS_PARSER_ID,
    SUPPORTED_PROVIDER_PARSER_IDS,
    parse_agentic_update_source_pack,
    provider_parser_stubs,
    run_agentic_update_discovery,
)


class AgenticUpdateParserTests(unittest.TestCase):
    def test_parser_fixtures_produce_deterministic_provider_proposals_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            discovery = run_agentic_update_discovery(
                workspace_root=workspace,
                run_id="parser-fixtures",
                run_contract={
                    "scope": "provider_metadata",
                    "providers": ["qwen", "deepseek"],
                    "allow_network": False,
                },
                provider_sources=[
                    _provider_source(
                        "qwen",
                        [
                            {
                                "source_id": "qwen-fixture",
                                "url": "https://example.test/qwen",
                            }
                        ],
                    ),
                    _provider_source(
                        "deepseek",
                        [
                            {
                                "source_id": "deepseek-fixture",
                                "url": "https://example.test/deepseek",
                            }
                        ],
                    ),
                ],
                fixture_sources={
                    "qwen-fixture": {
                        "content_type": "application/json",
                        "body": json.dumps(
                            {
                                "models": [
                                    {
                                        "model_id": "qwen/qwen3.8-plus",
                                        "display_name": "Qwen3.8 Plus",
                                        "context_window": 1000000,
                                        "input_modalities": ["text", "image"],
                                        "supported_reasoning_levels": ["low", "medium", "high"],
                                        "default_reasoning_level": "high",
                                        "pricing": {"input_per_mtok": 0.2, "output_per_mtok": 0.8, "currency": "USD"},
                                        "recommended": True,
                                        "default_for_provider": True,
                                        "vision": True,
                                        "tool_support": True,
                                        "apply_patch": True,
                                        "confidence": "high",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        ),
                    },
                    "deepseek-fixture": {
                        "content_type": "application/json",
                        "body": json.dumps(
                            {
                                "models": [
                                    {
                                        "model_id": "deepseek/deepseek-v5-pro",
                                        "display_name": "DeepSeek V5 Pro",
                                        "context_window": 1000000,
                                        "input_modalities": ["text"],
                                        "supported_reasoning_levels": ["high", "xhigh"],
                                        "default_reasoning_level": "xhigh",
                                        "pricing_input_per_mtok": 0.14,
                                        "pricing_output_per_mtok": 0.28,
                                        "web_search": True,
                                        "deprecated": False,
                                        "confidence": "medium",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        ),
                    },
                },
            )

            parsed = parse_agentic_update_source_pack(
                workspace_root=workspace,
                run_id="parser-fixtures",
                source_pack_path=discovery["artifact_paths"]["source_pack"],
            )

            self.assertEqual(parsed["schema_version"], AGENTIC_UPDATE_PARSER_OUTPUT_SCHEMA_VERSION)
            self.assertEqual(parsed["summary"]["parsed_model_count"], 2)
            self.assertTrue(Path(parsed["artifact_paths"]["parser_output"]).exists())
            self.assertEqual([item["model_id"] for item in parsed["proposals"]], ["qwen/qwen3.8-plus", "deepseek/deepseek-v5-pro"])
            qwen = parsed["proposals"][0]
            deepseek = parsed["proposals"][1]
            self.assertEqual(qwen["candidate_metadata"]["input_modalities"], ["text", "image"])
            self.assertEqual(qwen["candidate_metadata"]["advertised_context_window"], 1000000)
            self.assertEqual(qwen["candidate_metadata"]["pricing"]["input_per_mtok"], 0.2)
            self.assertTrue(qwen["capability_claims"]["tool_calls"]["declared"])
            self.assertTrue(qwen["capability_claims"]["vision"]["declared"])
            self.assertTrue(qwen["capability_claims"]["apply_patch"]["declared"])
            self.assertEqual(deepseek["candidate_metadata"]["supported_reasoning_levels"], ["high", "xhigh"])
            self.assertTrue(deepseek["capability_claims"]["web_search"]["declared"])

    def test_unknown_fields_default_conservative_and_emit_warnings(self) -> None:
        source_records = [
            {
                "ok": True,
                "provider_id": "qwen",
                "source_id": "line-fixture",
                "url": "https://example.test/qwen-line",
                "content_hash": "sha256:line",
                "excerpt_chars": 120,
                "parser_strategy": "html_document",
                "excerpt": "model: qwen/qwen-line | display_name: Qwen Line | mystery_field: unsupported | vision: true",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_agentic_update_source_pack(
                workspace_root=Path(temp_dir),
                run_id="unknown-fields",
                source_records=source_records,
            )

            proposal = parsed["proposals"][0]
            self.assertEqual(proposal["candidate_metadata"]["advertised_context_window"], None)
            self.assertEqual(proposal["candidate_metadata"]["input_modalities"], ["text"])
            self.assertEqual(proposal["candidate_metadata"]["supported_reasoning_levels"], [])
            self.assertIn("missing_context_window_defaulted_unknown", proposal["warnings"])
            self.assertIn("missing_reasoning_modes_defaulted_empty", proposal["warnings"])
            self.assertIn("missing_modalities_defaulted_text_only", proposal["warnings"])
            self.assertIn("unknown_field:mystery_field", proposal["warnings"])
            self.assertTrue(proposal["capability_claims"]["vision"]["declared"])
            self.assertFalse(proposal["capability_claims"]["vision"]["verified"])

    def test_provider_specific_parser_stubs_are_registered_for_managed_providers(self) -> None:
        stubs = provider_parser_stubs()

        self.assertEqual(set(stubs), set(SUPPORTED_PROVIDER_PARSER_IDS))
        for provider_id, stub in stubs.items():
            self.assertEqual(stub["provider_id"], provider_id)
            if provider_id == "qwen":
                self.assertEqual(stub["implementation"], QWEN_OFFICIAL_DOCS_PARSER_ID)
                self.assertEqual(stub["status"], "provider_specific_parser")
            else:
                self.assertEqual(stub["implementation"], "generic_conservative_v1")
                self.assertEqual(stub["status"], "stub_uses_generic_parser")

    def test_no_parsed_capability_is_marked_verified_without_validation_evidence(self) -> None:
        source_records = [
            {
                "ok": True,
                "provider_id": "qwen",
                "source_id": "claims",
                "url": "https://example.test/qwen-claims",
                "content_hash": "sha256:claims",
                "excerpt_chars": 100,
                "parser_strategy": "html_document",
                "excerpt": json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "qwen/qwen-claims",
                                "context_window": 1000000,
                                "input_modalities": ["text", "image", "audio"],
                                "supported_reasoning_levels": ["high"],
                                "tool_support": True,
                                "web_search": True,
                                "vision": True,
                                "audio": True,
                                "apply_patch": True,
                            }
                        ]
                    }
                ),
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_agentic_update_source_pack(
                workspace_root=Path(temp_dir),
                run_id="claims-run",
                source_records=source_records,
            )

        proposal = parsed["proposals"][0]
        self.assertEqual(proposal["validation_state"]["status"], "requires_validation")
        self.assertFalse(proposal["validation_state"]["verified"])
        for capability in ("tool_calls", "web_search", "vision", "audio", "apply_patch"):
            claim = proposal["capability_claims"][capability]
            self.assertTrue(claim["declared"])
            self.assertFalse(claim["verified"])
            self.assertNotEqual(claim["validation_status"], "verified")
            self.assertNotEqual(claim["claim_status"], "verified")

    def test_qwen_official_html_parser_extracts_model_ids_without_unknown_model_noise(self) -> None:
        source_records = [
            {
                "ok": True,
                "provider_id": "qwen",
                "source_id": "qwen-official-html",
                "url": "https://help.aliyun.com/zh/model-studio/text-generation-model/",
                "content_hash": "sha256:qwen-html",
                "excerpt_chars": 1200,
                "parser_excerpt_chars": 800,
                "parser_strategy": "html_table",
                "excerpt": "<!DOCTYPE html><html><head><meta name=\"nav-config\" content=\"footer=default\"></head></html>",
                "parser_excerpt": """
                    <meta name="nav-config" content="footer=default">
                    <td>qwen3.7-plus</td>
                    <td>qwen3-coder-plus</td>
                    <td>qwen3-vl-plus</td>
                    <a href="/zh/model-studio/qwen-api-reference">qwen-api-reference</a>
                    <img src="qwen-color.svg">
                """,
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_agentic_update_source_pack(
                workspace_root=Path(temp_dir),
                run_id="qwen-html",
                source_records=source_records,
            )

        model_ids = [item["model_id"] for item in parsed["proposals"]]
        by_model = {item["model_id"]: item for item in parsed["proposals"]}

        self.assertEqual(parsed["summary"]["parsed_model_count"], 3)
        self.assertIn("qwen/qwen3.7-plus", model_ids)
        self.assertIn("qwen/qwen3-coder-plus", model_ids)
        self.assertIn("qwen/qwen3-vl-plus", model_ids)
        self.assertNotIn("qwen/unknown-model", model_ids)
        self.assertNotIn("qwen/qwen-api-reference", model_ids)
        self.assertNotIn("qwen/qwen-color.svg", model_ids)
        self.assertEqual(by_model["qwen/qwen3-vl-plus"]["candidate_metadata"]["input_modalities"], ["text", "image"])
        self.assertFalse(by_model["qwen/qwen3-vl-plus"]["validation_state"]["verified"])
        self.assertEqual(provider_parser_stubs()["qwen"]["implementation"], QWEN_OFFICIAL_DOCS_PARSER_ID)

    def test_html_without_provider_parser_does_not_emit_meta_tag_candidates(self) -> None:
        source_records = [
            {
                "ok": True,
                "provider_id": "deepseek",
                "source_id": "deepseek-html-head",
                "url": "https://api-docs.deepseek.com/api/list-models",
                "content_hash": "sha256:html-head",
                "excerpt_chars": 400,
                "parser_strategy": "html_document",
                "excerpt": "<!DOCTYPE html><html><head><meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\"></head></html>",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_agentic_update_source_pack(
                workspace_root=Path(temp_dir),
                run_id="html-head",
                source_records=source_records,
            )

        self.assertEqual(parsed["summary"]["parsed_model_count"], 0)
        self.assertIn("html_source_requires_provider_parser:deepseek:deepseek-html-head", parsed["warnings"])

    def test_discovery_parser_excerpt_allows_qwen_models_beyond_short_excerpt(self) -> None:
        long_head = "<!DOCTYPE html><html><head>" + ("<meta name=\"nav-config\" content=\"footer=default\">" * 80) + "</head><body>"
        body = long_head + "<table><tr><td>qwen3.7-plus</td><td>qwen3-vl-plus</td></tr></table></body></html>"
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            discovery = run_agentic_update_discovery(
                workspace_root=workspace,
                run_id="qwen-parser-excerpt",
                run_contract={
                    "scope": "provider_metadata",
                    "providers": ["qwen"],
                    "allow_network": False,
                },
                provider_sources=[
                    _provider_source(
                        "qwen",
                        [
                            {
                                "source_id": "qwen-long-html",
                                "url": "https://help.aliyun.com/zh/model-studio/models",
                            }
                        ],
                    )
                ],
                fixture_sources={
                    "qwen-long-html": {
                        "content_type": "text/html; charset=utf-8",
                        "body": body,
                    }
                },
                max_excerpt_chars=1200,
            )
            parsed = parse_agentic_update_source_pack(
                workspace_root=workspace,
                run_id="qwen-parser-excerpt",
                source_pack_path=discovery["artifact_paths"]["source_pack"],
            )

        model_ids = [item["model_id"] for item in parsed["proposals"]]

        self.assertIn("qwen/qwen3.7-plus", model_ids)
        self.assertIn("qwen/qwen3-vl-plus", model_ids)
        self.assertNotIn("qwen/unknown-model", model_ids)


def _provider_source(provider_id: str, source_records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "provider_id": provider_id,
        "display_name": provider_id.title(),
        "source_status": "official_docs",
        "source_type": "models_catalog",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": "html_document",
        "stale_after_days": 7,
        "source_records": [
            {
                "source_id": record.get("source_id") or f"{provider_id}-source",
                "url": record["url"],
                "source_type": record.get("source_type") or "models_catalog",
                "trust_level": record.get("trust_level") or "official",
                "channel": record.get("channel") or "stable_docs",
                "parser_strategy": record.get("parser_strategy") or "html_document",
                "stale_after_days": record.get("stale_after_days") or 7,
            }
            for record in source_records
        ],
    }


if __name__ == "__main__":
    unittest.main()
