from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.llm_api_manager_service import LlmApiManagerService
from astrabridge_sidecar.metadata_service import MetadataService
from astrabridge_sidecar.model_catalog.generated_catalog import default_seed_models
from astrabridge_sidecar.model_catalog import preferred_provider_model_record, resolved_provider_source_of_truth_fields
from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.router_config_service import RouterConfigService


class DummyRouter:
    pass


class ProviderCatalogContractTests(unittest.TestCase):
    def test_seed_catalog_includes_qwen_and_kimi_capability_models(self) -> None:
        seeded = {str(item["id"]): item for item in default_seed_models()}

        self.assertIn("qwen/qwen3-vl-plus", seeded)
        self.assertIn("qwen/qwen3-vl-flash", seeded)
        self.assertIn("qwen/qwen3-asr-flash", seeded)
        self.assertIn("qwen/qwen3-tts-flash", seeded)
        self.assertIn("qwen/qwen3-tts-instruct-flash", seeded)
        self.assertIn("qwen/cosyvoice-v3-plus", seeded)
        self.assertIn("qwen/cosyvoice-v3.5-plus", seeded)
        self.assertIn("kimi/kimi-k2.7-code-highspeed", seeded)
        self.assertEqual(seeded["qwen/qwen3-vl-plus"]["input_modalities"], ["text", "image"])
        self.assertEqual(seeded["qwen/qwen3-vl-plus"]["modality_limits"]["remote_image_url_supported"], True)
        self.assertEqual(seeded["qwen/qwen3-asr-flash"]["input_modalities"], ["text", "audio"])
        self.assertEqual(seeded["qwen/qwen3-asr-flash"]["modality_limits"]["audio_transport"], "chat_completions_input_audio_data_uri")
        self.assertEqual(seeded["qwen/qwen3-tts-flash"]["default_reasoning_level"], "off")
        self.assertEqual(seeded["qwen/cosyvoice-v3-plus"]["modality_limits"]["tts_instruction_field"], "instruction")
        self.assertEqual(seeded["qwen/cosyvoice-v3.5-plus"]["modality_limits"]["tts_system_voice_support"], "unsupported")
        self.assertEqual(seeded["kimi/kimi-k2.7-code-highspeed"]["input_modalities"], ["text", "image"])

    def test_provider_source_of_truth_prefers_generated_default_model_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profiles = ProfileService(root / "profiles.json")
            config = RouterConfigService(profiles, root / "router.json")
            metadata = MetadataService(config, DummyRouter(), root / "sources.json", root / "report")
            metadata.import_seed(apply=True)

            kimi_provider = next(item for item in config.providers() if item["id"] == "kimi")
            config.upsert_provider({**kimi_provider, "default_model": "kimi-k2.6"})
            kimi_k26 = next(item for item in config.models() if item["id"] == "kimi/kimi-k2.6")
            kimi_k27 = next(item for item in config.models() if item["id"] == "kimi/kimi-k2.7-code")
            config.upsert_model({**kimi_k26, "default_for_provider": True, "recommended": False})
            config.upsert_model(
                {
                    **kimi_k27,
                    "default_for_provider": False,
                    "recommended": True,
                    "tool_web_search_support": "verified",
                    "web_smoke_status": "pass",
                    "citation_quality": "source_url_verified",
                }
            )

            preferred = preferred_provider_model_record("kimi", config.models(), include_deprecated=False)
            self.assertIsNotNone(preferred)
            self.assertEqual(preferred["id"], "kimi/kimi-k2.7-code")

            kimi_contract = resolved_provider_source_of_truth_fields(
                next(item for item in config.providers() if item["id"] == "kimi"),
                config.models(),
            )
            self.assertEqual(kimi_contract["configured_default_model"], "kimi-k2.6")
            self.assertEqual(kimi_contract["effective_default_model"], "kimi-k2.7-code")
            self.assertEqual(kimi_contract["effective_default_model_id"], "kimi/kimi-k2.7-code")
            self.assertEqual(kimi_contract["default_model_alignment"], "stale_config")
            self.assertIn("configured_default_model_differs_from_catalog_preferred_model", kimi_contract["warnings"])
            self.assertEqual(kimi_contract["reasoning_policy_mode"], "reasoning_content")
            self.assertEqual(kimi_contract["reasoning_state"]["visibility"], "visible_summary_only")
            self.assertFalse(kimi_contract["reasoning_state"]["replayable"])
            self.assertEqual(kimi_contract["context_window"], 256000)
            self.assertEqual(kimi_contract["context_gate"]["auto_compact_status"], "configured_unverified")
            self.assertEqual(kimi_contract["context_gate"]["compact_summary_quality_status"], "untested")
            self.assertEqual(kimi_contract["workflow_contract"]["auto_compact"], "configured_unverified")
            self.assertEqual(kimi_contract["apply_patch_tool_type"], None)
            self.assertEqual(kimi_contract["web_capability"]["tool_web_search_support"], "verified")
            self.assertEqual(kimi_contract["web_capability"]["web_smoke_status"], "pass")
            self.assertIn("auto_compact_validation_unverified", kimi_contract["warnings"])
            self.assertIn("compact_summary_quality_unverified", kimi_contract["warnings"])

            deepseek_contract = resolved_provider_source_of_truth_fields(
                next(item for item in config.providers() if item["id"] == "deepseek"),
                config.models(),
            )
            self.assertEqual(deepseek_contract["reasoning_policy_mode"], "reasoning_content")
            self.assertEqual(deepseek_contract["reasoning_state"]["visibility"], "visible_summary_only")
            self.assertEqual(deepseek_contract["context_window"], 1000000)
            self.assertEqual(deepseek_contract["context_gate"]["auto_compact_status"], "configured_unverified")
            self.assertEqual(deepseek_contract["context_gate"]["provider_rejection_category"], "context_window_limit")
            self.assertEqual(deepseek_contract["workflow_contract"]["auto_compact"], "configured_unverified")
            self.assertTrue(deepseek_contract["tool_policy"]["supports_mcp_tools"])
            self.assertEqual(deepseek_contract["tool_policy"]["mcp_tool_call_policy"], "conservative")
            self.assertEqual(deepseek_contract["apply_patch_tool_type"], None)
            self.assertEqual(deepseek_contract["web_capability"]["tool_web_search_support"], "verified")
            self.assertIn("auto_compact_validation_unverified", deepseek_contract["warnings"])

    def test_effective_catalog_provider_redaction_keeps_alignment_and_key_availability_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profiles = ProfileService(root / "profiles.json")
            config = RouterConfigService(profiles, root / "router.json")
            metadata = MetadataService(config, DummyRouter(), root / "sources.json", root / "report")
            metadata.import_seed(apply=True)

            kimi_provider = next(item for item in config.providers() if item["id"] == "kimi")
            config.upsert_provider({**kimi_provider, "default_model": "kimi-k2.6", "auth_key_ref": "vault:kimi"})
            kimi_k26 = next(item for item in config.models() if item["id"] == "kimi/kimi-k2.6")
            kimi_k27 = next(item for item in config.models() if item["id"] == "kimi/kimi-k2.7-code")
            config.upsert_model({**kimi_k26, "default_for_provider": True, "recommended": False})
            config.upsert_model({**kimi_k27, "default_for_provider": False, "recommended": True})

            manager = LlmApiManagerService(config, DummyRouter(), root / "manager")
            catalog = manager.effective_catalog()
            provider = next(item for item in catalog["providers"] if item["id"] == "kimi")

            self.assertEqual(provider["default_model"], "kimi-k2.6")
            self.assertEqual(provider["effective_default_model"], "kimi-k2.7-code")
            self.assertEqual(provider["effective_default_model_id"], "kimi/kimi-k2.7-code")
            self.assertEqual(provider["default_model_alignment"], "stale_config")
            self.assertIn("configured_default_model_differs_from_catalog_preferred_model", provider["provider_contract_warnings"])
            self.assertEqual(provider["auth_key_ref"], None)
            self.assertEqual(provider["managed_key_available"], False)
            self.assertNotIn("vault:kimi", json.dumps(provider))

    def test_effective_catalog_refreshes_stale_glm_command_execution_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profiles = ProfileService(root / "profiles.json")
            config = RouterConfigService(profiles, root / "router.json")
            metadata = MetadataService(config, DummyRouter(), root / "sources.json", root / "report")
            metadata.import_seed(apply=True)

            stale_glm = next(item for item in config.models() if item["id"] == "glm/glm-5.2")
            config.import_sanitized(
                {
                    "providers": config.providers(),
                    "models": [
                        {
                            key: value
                            for key, value in stale_glm.items()
                            if key not in {"command_execution_status", "command_execution_note", "ui_warnings"}
                        }
                    ],
                    "reasoning": config.reasoning(),
                }
            )

            catalog = metadata.effective_catalog("glm/glm-5.2")
            self.assertEqual(catalog["model_count"], 1)
            model = catalog["models"][0]
            self.assertEqual(model["id"], "glm/glm-5.2")
            self.assertEqual(model["command_execution_status"], "partial_no_command_execution")
            self.assertIn("no commandExecution event", str(model["command_execution_note"]))
            self.assertTrue(
                any("partial" in warning.lower() and "command execution" in warning.lower() for warning in list(model.get("ui_warnings") or []))
            )

    def test_effective_catalog_suppresses_unsafe_default_route_advertising(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profiles = ProfileService(root / "profiles.json")
            config = RouterConfigService(profiles, root / "router.json")
            metadata = MetadataService(config, DummyRouter(), root / "sources.json", root / "report")
            metadata.import_seed(apply=True)

            catalog = metadata.effective_catalog("qwen/qwen3.7-plus")
            self.assertEqual(catalog["model_count"], 1)
            model = catalog["models"][0]
            self.assertEqual(model["id"], "qwen/qwen3.7-plus")
            self.assertFalse(model["recommended"])
            self.assertFalse(model["default_for_provider"])
            self.assertFalse(model["default_route_verified"])
            self.assertIn("authority_tier_C", list(model.get("default_route_blockers") or []))


if __name__ == "__main__":
    unittest.main()
