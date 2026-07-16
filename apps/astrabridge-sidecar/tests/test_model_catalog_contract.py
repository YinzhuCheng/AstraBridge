from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.model_catalog import model_catalog_entry, resolved_runtime_provider_contract_fields


class ModelCatalogContractTests(unittest.TestCase):
    def test_catalog_entry_exports_app_server_reasoning_labels(self) -> None:
        entry = model_catalog_entry(
            model_id="openai/gpt-5.5",
            provider_id="openai",
            native_model="gpt-5.5",
            display_name="OpenAI Compatible gpt-5.5",
            context_window=1_000_000,
            configured_model={
                "supported_reasoning_levels": ["off", "high", "xhigh"],
                "default_reasoning_level": "off",
                "native_supported_reasoning_levels": ["off", "high", "max"],
                "native_default_reasoning_level": "off",
            },
        )

        self.assertEqual(entry["default_reasoning_level"], "none")
        self.assertEqual(entry["native_supported_reasoning_levels"], ["none", "high", "xhigh"])
        self.assertEqual(entry["native_default_reasoning_level"], "none")
        self.assertEqual([item["effort"] for item in entry["supported_reasoning_levels"]], ["none", "high", "xhigh"])
        self.assertEqual([item["reasoningEffort"] for item in entry["supportedReasoningEfforts"]], ["none", "high", "xhigh"])
        self.assertEqual(entry["runtime_provider_contract"]["provider_metadata"]["supported_reasoning_levels"], ["none", "high", "xhigh"])
        self.assertEqual(entry["runtime_provider_contract"]["provider_metadata"]["native_supported_reasoning_levels"], ["none", "high", "xhigh"])
        self.assertEqual(entry["runtime_provider_contract"]["codex_runtime_metadata"]["default_reasoning_level"], "none")
        self.assertEqual(entry["runtime_provider_contract"]["capability_metadata"]["reasoning_effort"]["provider_default"], "none")
        self.assertEqual(entry["runtime_provider_contract"]["capability_metadata"]["reasoning_effort"]["codex_values"], ["none", "high", "xhigh"])
        self.assertEqual(entry["runtime_provider_contract"]["capability_metadata"]["reasoning_effort"]["native_provider_default"], "none")

    def test_catalog_entry_exposes_runtime_provider_contract_mapping(self) -> None:
        entry = model_catalog_entry(
            model_id="deepseek/deepseek-v4-pro",
            provider_id="deepseek",
            native_model="deepseek-v4-pro",
            display_name="DeepSeek V4 Pro",
            context_window=1_000_000,
            configured_model={
                "supported_reasoning_levels": ["high", "max"],
                "default_reasoning_level": "max",
                "native_supported_reasoning_levels": ["high", "max"],
                "native_default_reasoning_level": "max",
                "input_modalities": ["text", "image"],
                "apply_patch_tool_type": "json",
                "web_search_tool_type": "text_and_image",
                "supports_search_tool": True,
                "supports_parallel_tool_calls": True,
                "supports_mcp_tools": True,
                "mcp_tool_call_policy": "verified",
                "mcp_verified_servers": ["astrabridge_web"],
                "mcp_smoke_status": "pass_direct_tool_call",
                "mcp_tool_argument_validation": "schema_checked",
                "supports_image_detail_original": True,
                "pricing_currency": "USD",
                "pricing_input_per_mtok": 1.0,
                "pricing_output_per_mtok": 3.0,
            },
        )

        contract = entry["runtime_provider_contract"]

        self.assertEqual(contract["schema_version"], "astrabridge-runtime-provider-contract-v1")
        self.assertEqual(contract["validation"]["status"], "pass")
        self.assertEqual(contract["capability_metadata"]["reasoning_effort"]["provider_values"], ["high", "xhigh"])
        self.assertEqual(contract["capability_metadata"]["reasoning_effort"]["codex_default"], "xhigh")
        self.assertEqual(contract["capability_metadata"]["reasoning_effort"]["native_provider_values"], ["high", "xhigh"])
        self.assertEqual(contract["capability_metadata"]["reasoning_effort"]["native_provider_default"], "xhigh")
        self.assertEqual(contract["capability_metadata"]["reasoning_state"]["visibility"], "provider_private")
        self.assertFalse(contract["capability_metadata"]["reasoning_state"]["replayable"])
        self.assertEqual(contract["capability_metadata"]["apply_patch_tool_type"]["provider_value"], "json")
        self.assertEqual(contract["capability_metadata"]["apply_patch_tool_type"]["codex_value"], "freeform")
        self.assertEqual(contract["capability_metadata"]["apply_patch_tool_type"]["mapping_status"], "json_to_codex_freeform")
        self.assertEqual(contract["capability_metadata"]["web_search"]["tool_type"], "text_and_image")
        self.assertEqual(contract["capability_metadata"]["context_window"]["declared_context_window"], 1_000_000)
        self.assertEqual(contract["capability_metadata"]["context_window"]["effective_context_window_percent"], 80)
        self.assertEqual(contract["capability_metadata"]["context_window"]["effective_context_budget_tokens"], 800_000)
        self.assertEqual(contract["capability_metadata"]["context_window"]["auto_compact_status"], "configured_unverified")
        self.assertEqual(contract["capability_metadata"]["context_window"]["compact_summary_quality_status"], "untested")
        self.assertEqual(contract["capability_metadata"]["context_window"]["tool_output_token_limit"], 32_000)
        self.assertEqual(contract["capability_metadata"]["context_window"]["preflight_budgeting_status"], "budgeted_before_send")
        self.assertFalse(contract["capability_metadata"]["context_window"]["automatic_request_truncation"])
        self.assertEqual(contract["capability_metadata"]["context_window"]["provider_rejection_category"], "context_window_limit")
        self.assertTrue(contract["capability_metadata"]["vision"]["supports_image_inputs"])
        self.assertTrue(contract["capability_metadata"]["parallel_tools"]["supported"])
        self.assertEqual(contract["capability_metadata"]["mcp"]["tool_call_policy"], "verified")
        self.assertEqual(contract["capability_metadata"]["token_usage"]["usage_event"], "thread/tokenUsage/updated")
        self.assertEqual(contract["codex_runtime_metadata"]["effective_context_budget_tokens"], 800_000)
        self.assertEqual(contract["codex_runtime_metadata"]["tool_output_token_limit"], 32_000)
        self.assertEqual(contract["provider_metadata"]["native_supported_reasoning_levels"], ["high", "xhigh"])
        self.assertEqual(contract["provider_metadata"]["native_default_reasoning_level"], "xhigh")

    def test_runtime_provider_contract_warns_for_incoherent_metadata(self) -> None:
        contract = resolved_runtime_provider_contract_fields(
            {
                "provider": "custom",
                "native_model": "custom-model",
                "input_modalities": ["text"],
                "supported_reasoning_levels": ["none", "max"],
                "default_reasoning_level": "none",
                "reasoning_policy_mode": "reasoning_content",
                "apply_patch_tool_type": "yaml",
                "web_search_tool_type": "binary",
                "supports_mcp_tools": True,
                "mcp_tool_call_policy": "unsupported",
                "supports_parallel_tool_calls": True,
                "supports_image_detail_original": True,
            }
        )

        warnings = set(contract["validation"]["warnings"])

        self.assertEqual(contract["validation"]["status"], "warn")
        self.assertIn("unsupported_apply_patch_tool_type", warnings)
        self.assertIn("unsupported_web_search_tool_type_defaulted_to_text", warnings)
        self.assertIn("mcp_tools_enabled_with_unsupported_policy", warnings)
        self.assertIn("image_detail_original_enabled_without_image_modality", warnings)
        self.assertEqual(contract["capability_metadata"]["reasoning_effort"]["provider_values"], ["off", "xhigh"])
        self.assertEqual(contract["capability_metadata"]["reasoning_effort"]["codex_default"], "off")
        self.assertEqual(contract["capability_metadata"]["reasoning_effort"]["native_provider_values"], ["none", "max"])
        self.assertEqual(contract["capability_metadata"]["reasoning_effort"]["native_provider_default"], "none")
        self.assertEqual(contract["capability_metadata"]["reasoning_state"]["visibility"], "visible_summary_only")
        self.assertEqual(contract["capability_metadata"]["context_window"]["provider_rejection_category"], "context_window_limit")
        self.assertFalse(contract["capability_metadata"]["context_window"]["automatic_request_truncation"])
        self.assertEqual(contract["capability_metadata"]["apply_patch_tool_type"]["mapping_status"], "unsupported")
        self.assertEqual(contract["codex_runtime_metadata"]["web_search_tool_type"], "text")

    def test_explicit_modalities_override_provider_defaults_without_readding_image(self) -> None:
        contract = resolved_runtime_provider_contract_fields(
            {
                "provider": "qwen",
                "native_model": "qwen3.7-plus",
                "input_modalities": ["text"],
            }
        )

        self.assertEqual(contract["provider_metadata"]["input_modalities"], ["text"])
        self.assertFalse(contract["capability_metadata"]["vision"]["supports_image_inputs"])


if __name__ == "__main__":
    unittest.main()
