from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import (
    AGENTIC_UPDATE_PARSER_OUTPUT_SCHEMA_VERSION,
    DEEPSEEK_OFFICIAL_DOCS_PARSER_ID,
    GLM_OFFICIAL_DOCS_PARSER_ID,
    KIMI_OFFICIAL_DOCS_PARSER_ID,
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
            if provider_id in {"qwen", "deepseek", "kimi", "glm"}:
                expected = {
                    "qwen": QWEN_OFFICIAL_DOCS_PARSER_ID,
                    "deepseek": DEEPSEEK_OFFICIAL_DOCS_PARSER_ID,
                    "kimi": KIMI_OFFICIAL_DOCS_PARSER_ID,
                    "glm": GLM_OFFICIAL_DOCS_PARSER_ID,
                }[provider_id]
                self.assertEqual(stub["implementation"], expected)
                self.assertEqual(stub["status"], "provider_specific_parser")
            else:
                self.assertEqual(stub["implementation"], "generic_conservative_v1")
                self.assertEqual(stub["status"], "stub_uses_generic_parser")

    def test_kimi_official_markdown_sources_merge_model_metadata_and_adapter_mapping(self) -> None:
        source_records = [
            {
                "ok": True,
                "provider_id": "kimi",
                "platform_id": "platform.kimi.ai",
                "source_id": "kimi-models-markdown",
                "url": "https://platform.kimi.ai/docs/models.md",
                "content_hash": "sha256:kimi-models",
                "excerpt_chars": 600,
                "parser_strategy": "markdown_table",
                "source_type": "models_catalog",
                "trust_level": "official",
                "parser_excerpt": """
                    # Model List
                    | Model Name | Description |
                    | --- | --- |
                    | `kimi-k3` | Kimi's flagship model with native visual understanding and a 1M-token context window. |
                """,
            },
            {
                "ok": True,
                "provider_id": "kimi",
                "platform_id": "platform.kimi.ai",
                "source_id": "kimi-k3-guide",
                "url": "https://platform.kimi.ai/docs/guide/kimi-k3-quickstart.md",
                "content_hash": "sha256:kimi-k3-guide",
                "excerpt_chars": 700,
                "parser_strategy": "markdown_document",
                "source_type": "guide",
                "trust_level": "official",
                "discovered_from_source_id": "kimi-llms-index",
                "parser_excerpt": """
                    # Kimi K3
                    Kimi K3 supports text, image, and video input plus ToolCalls for agent workflows.
                    completion = client.chat.completions.create(model="kimi-k3", messages=[])
                """,
            },
            {
                "ok": True,
                "provider_id": "kimi",
                "platform_id": "platform.kimi.ai",
                "source_id": "kimi-reasoning-effort",
                "url": "https://platform.kimi.ai/docs/guide/use-reasoning-effort.md",
                "content_hash": "sha256:kimi-reasoning",
                "excerpt_chars": 700,
                "parser_strategy": "markdown_document",
                "source_type": "guide",
                "trust_level": "official",
                "discovered_from_source_id": "kimi-llms-index",
                "parser_excerpt": """
                    # Reasoning Effort
                    Kimi K3 configures reasoning with the top-level `reasoning_effort` field.
                    The model `kimi-k3` supports "low", "high", and "max", with "max" as the default.
                """,
            },
            {
                "ok": True,
                "provider_id": "kimi",
                "platform_id": "platform.kimi.ai",
                "source_id": "kimi-k3-pricing",
                "url": "https://platform.kimi.ai/docs/pricing/chat-k3.md",
                "content_hash": "sha256:kimi-k3-pricing",
                "excerpt_chars": 700,
                "parser_strategy": "markdown_table",
                "source_type": "pricing",
                "trust_level": "official",
                "discovered_from_source_id": "kimi-llms-index",
                "parser_excerpt": """
                    | Model | Unit | Cache Hit | Cache Miss | Output | Context Window |
                    | --- | --- | --- | --- | --- | --- |
                    | `kimi-k3` | 1M tokens | $0.30 | $3.00 | $15.00 | 1,048,576 tokens |
                    Kimi K3 supports internet search, but every capability claim still requires validation.
                """,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_agentic_update_source_pack(
                workspace_root=Path(temp_dir),
                run_id="kimi-official-markdown",
                source_records=source_records,
            )

        self.assertEqual(parsed["summary"]["parsed_model_count"], 1)
        proposal = parsed["proposals"][0]
        metadata = proposal["candidate_metadata"]
        self.assertEqual(proposal["model_id"], "kimi/kimi-k3")
        self.assertEqual(metadata["advertised_context_window"], 1_048_576)
        self.assertEqual(metadata["input_modalities"], ["text", "image", "video"])
        self.assertEqual(metadata["native_supported_reasoning_levels"], ["low", "high", "max"])
        self.assertEqual(metadata["native_default_reasoning_level"], "max")
        self.assertEqual(metadata["supported_reasoning_levels"], ["low", "high", "xhigh"])
        self.assertEqual(metadata["default_reasoning_level"], "xhigh")
        self.assertEqual(metadata["reasoning_effort_mapping"], {"low": "low", "high": "high", "xhigh": "max"})
        self.assertEqual(metadata["pricing"]["cached_input_per_mtok"], 0.3)
        self.assertEqual(metadata["pricing"]["input_per_mtok"], 3.0)
        self.assertEqual(metadata["pricing"]["output_per_mtok"], 15.0)
        self.assertFalse(metadata["deprecated"])
        self.assertEqual(len(proposal["source_refs"]), 4)
        self.assertEqual({item["platform_id"] for item in proposal["source_refs"]}, {"platform.kimi.ai"})
        self.assertTrue(proposal["capability_claims"]["tool_calls"]["declared"])
        self.assertTrue(proposal["capability_claims"]["web_search"]["declared"])
        self.assertFalse(proposal["capability_claims"]["tool_calls"]["verified"])
        self.assertEqual(proposal["adapter_requirements"]["reasoning_parameter"], "reasoning_effort")
        self.assertEqual(proposal["adapter_requirements"]["review_status"], "requires_adapter_review")
        self.assertIn("provider_reasoning_transport_mapping_requires_adapter_review", proposal["warnings"])
        self.assertNotIn("missing_context_window_defaulted_unknown", proposal["warnings"])
        self.assertNotIn("missing_reasoning_modes_defaulted_empty", proposal["warnings"])
        self.assertNotIn("missing_modalities_defaulted_text_only", proposal["warnings"])
        self.assertEqual(provider_parser_stubs()["kimi"]["implementation"], KIMI_OFFICIAL_DOCS_PARSER_ID)

    def test_deepseek_official_html_sources_merge_current_model_contract(self) -> None:
        source_records = [
            {
                "ok": True,
                "provider_id": "deepseek",
                "source_id": "deepseek-pricing",
                "url": "https://api-docs.deepseek.com/quick_start/pricing/",
                "content_hash": "sha256:deepseek-pricing",
                "parser_strategy": "html_table",
                "source_type": "pricing",
                "trust_level": "official",
                "parser_excerpt": """
                    <table>
                    <tr><td>MODEL</td><td>deepseek-v4-flash</td><td>deepseek-v4-pro</td></tr>
                    <tr><td>CONTEXT LENGTH</td><td colspan="2">1M tokens</td></tr>
                    <tr><td>1M INPUT TOKENS (CACHE HIT)</td><td>$0.0028</td><td>$0.003625</td></tr>
                    <tr><td>1M INPUT TOKENS (CACHE MISS)</td><td>$0.14</td><td>$0.435</td></tr>
                    <tr><td>1M OUTPUT TOKENS</td><td>$0.28</td><td>$0.87</td></tr>
                    </table>
                    <p>Both models support tool calls.</p>
                """,
            },
            {
                "ok": True,
                "provider_id": "deepseek",
                "source_id": "deepseek-thinking",
                "url": "https://api-docs.deepseek.com/guides/thinking_mode/",
                "content_hash": "sha256:deepseek-thinking",
                "parser_strategy": "html_document",
                "source_type": "guide",
                "trust_level": "official",
                "parser_excerpt": """
                    <h1>Thinking mode</h1><p>deepseek-v4-pro enables thinking by default.</p>
                    <p>Set <code>reasoning_effort</code> to "high" or "max". Low and medium compatibility levels map to high.</p>
                """,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_agentic_update_source_pack(
                workspace_root=Path(temp_dir),
                run_id="deepseek-official-html",
                source_records=source_records,
            )

        self.assertEqual(parsed["summary"]["parsed_model_count"], 2)
        proposal = next(item for item in parsed["proposals"] if item["model_id"] == "deepseek/deepseek-v4-pro")
        metadata = proposal["candidate_metadata"]
        self.assertEqual(proposal["model_id"], "deepseek/deepseek-v4-pro")
        self.assertEqual(metadata["advertised_context_window"], 1_000_000)
        self.assertEqual(metadata["native_supported_reasoning_levels"], ["high", "max"])
        self.assertEqual(metadata["reasoning_effort_mapping"], {"low": "high", "medium": "high", "high": "high", "xhigh": "max"})
        self.assertEqual(metadata["pricing"]["cached_input_per_mtok"], 0.003625)
        self.assertEqual(metadata["pricing"]["input_per_mtok"], 0.435)
        self.assertEqual(metadata["pricing"]["output_per_mtok"], 0.87)
        self.assertTrue(proposal["capability_claims"]["tool_calls"]["declared"])
        self.assertEqual(proposal["adapter_requirements"]["reasoning_parameter"], "reasoning_effort")

    def test_glm_official_markdown_sources_merge_reasoning_mapping(self) -> None:
        source_records = [
            {
                "ok": True,
                "provider_id": "glm",
                "source_id": "glm-5-2",
                "url": "https://docs.z.ai/guides/llm/glm-5.2.md",
                "content_hash": "sha256:glm-model",
                "parser_strategy": "markdown_document",
                "source_type": "models_catalog",
                "trust_level": "official",
                "parser_excerpt": """
                    # GLM-5.2
                    `glm-5.2` is the flagship 1,000,000-token text model and supports function calling.
                    See /openclaw#switching-to-glm-5-turbo-model for integration notes.
                    The unrelated encoder architecture is GLM-0.5B.
                """,
            },
            {
                "ok": True,
                "provider_id": "glm",
                "source_id": "glm-reasoning",
                "url": "https://docs.z.ai/api-reference/llm/chat-completion.md",
                "content_hash": "sha256:glm-reasoning",
                "parser_strategy": "markdown_document",
                "source_type": "api_reference",
                "trust_level": "official",
                "parser_excerpt": """
                    For `glm-5.2`, `reasoning_effort` accepts `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`.
                    `low` and `medium` map to `high`; `xhigh` maps to `max`; the default is `max`.
                """,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_agentic_update_source_pack(
                workspace_root=Path(temp_dir),
                run_id="glm-official-markdown",
                source_records=source_records,
            )

        self.assertEqual(parsed["summary"]["parsed_model_count"], 1)
        proposal = parsed["proposals"][0]
        metadata = proposal["candidate_metadata"]
        self.assertEqual(proposal["model_id"], "glm/glm-5.2")
        self.assertEqual(metadata["advertised_context_window"], 1_000_000)
        self.assertEqual(metadata["native_default_reasoning_level"], "max")
        self.assertEqual(metadata["default_reasoning_level"], "xhigh")
        self.assertEqual(
            metadata["reasoning_effort_mapping"],
            {"off": "none", "minimal": "minimal", "low": "high", "medium": "high", "high": "high", "xhigh": "max"},
        )
        self.assertTrue(proposal["capability_claims"]["tool_calls"]["declared"])
        self.assertEqual(provider_parser_stubs()["glm"]["implementation"], GLM_OFFICIAL_DOCS_PARSER_ID)

    def test_kimi_tool_message_json_is_not_promoted_as_unknown_model(self) -> None:
        source_records = [
            {
                "ok": True,
                "provider_id": "kimi",
                "source_id": "kimi-tool-guide",
                "url": "https://platform.kimi.ai/docs/guide/kimi-k3-tool-calling.md",
                "content_hash": "sha256:kimi-tool-guide",
                "excerpt_chars": 500,
                "parser_strategy": "markdown_document",
                "source_type": "guide",
                "trust_level": "official",
                "parser_excerpt": """
                    ```json
                    [{"role": "assistant", "content": "", "tool_calls": [{"type": "function"}]}]
                    ```
                    completion = client.chat.completions.create(model="kimi-k3", messages=[])
                """,
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            parsed = parse_agentic_update_source_pack(
                workspace_root=Path(temp_dir),
                run_id="kimi-tool-json",
                source_records=source_records,
            )

        self.assertEqual(parsed["proposals"], [])
        self.assertNotIn("kimi/unknown-model", [item["model_id"] for item in parsed["proposals"]])
        self.assertIn("weak_model_candidate_dropped:kimi:kimi-k3", parsed["warnings"])

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
        self.assertIn("no_models_parsed:deepseek:deepseek-html-head", parsed["warnings"])

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
