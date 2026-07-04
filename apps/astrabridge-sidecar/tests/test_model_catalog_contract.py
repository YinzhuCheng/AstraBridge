from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.model_catalog import model_catalog_entry, resolved_runtime_provider_contract_fields


class ModelCatalogContractTests(unittest.TestCase):
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
        self.assertEqual(contract["capability_metadata"]["apply_patch_tool_type"]["provider_value"], "json")
        self.assertEqual(contract["capability_metadata"]["apply_patch_tool_type"]["codex_value"], "freeform")
        self.assertEqual(contract["capability_metadata"]["apply_patch_tool_type"]["mapping_status"], "json_to_codex_freeform")
        self.assertEqual(contract["capability_metadata"]["web_search"]["tool_type"], "text_and_image")
        self.assertTrue(contract["capability_metadata"]["vision"]["supports_image_inputs"])
        self.assertTrue(contract["capability_metadata"]["parallel_tools"]["supported"])
        self.assertEqual(contract["capability_metadata"]["mcp"]["tool_call_policy"], "verified")
        self.assertEqual(contract["capability_metadata"]["token_usage"]["usage_event"], "thread/tokenUsage/updated")
        self.assertEqual(contract["codex_runtime_metadata"]["tool_output_token_limit"], 32_000)

    def test_runtime_provider_contract_warns_for_incoherent_metadata(self) -> None:
        contract = resolved_runtime_provider_contract_fields(
            {
                "provider": "custom",
                "native_model": "custom-model",
                "input_modalities": ["text"],
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
        self.assertEqual(contract["capability_metadata"]["apply_patch_tool_type"]["mapping_status"], "unsupported")
        self.assertEqual(contract["codex_runtime_metadata"]["web_search_tool_type"], "text")


if __name__ == "__main__":
    unittest.main()
