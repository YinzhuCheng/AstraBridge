from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import CapabilityRegistry, default_capability_registry, normalize_adapter_contract


class CapabilityRegistryTests(unittest.TestCase):
    def test_web_search_resolves_to_standalone_lane(self) -> None:
        registry = default_capability_registry()

        candidates = registry.resolve_candidates("web.search")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["lane_type"], "web_standalone")
        self.assertIsNone(candidates[0]["provider_id"])
        self.assertEqual(candidates[0]["source"], "standalone_lane")

    def test_qwen_and_kimi_vision_candidates_are_capability_aware(self) -> None:
        registry = default_capability_registry()

        candidates = registry.resolve_candidates("vision.analyze")
        qwen_models = {item["model"]: item for item in candidates if item["provider_id"] == "qwen"}
        kimi_models = {item["model"]: item for item in candidates if item["provider_id"] == "kimi"}

        self.assertIn("qwen3.7-plus", qwen_models)
        self.assertIn("qwen3-vl-plus", qwen_models)
        self.assertIn("kimi-k2.6", kimi_models)
        self.assertIn("kimi-k2.7-code", kimi_models)
        self.assertIn("kimi-k3", kimi_models)
        self.assertIn("image", qwen_models["qwen3.7-plus"]["input_modalities"])
        self.assertEqual(qwen_models["qwen3.7-plus"]["source"], "catalog_default_model")
        self.assertEqual(qwen_models["qwen3-vl-plus"]["source"], "catalog_model")
        self.assertEqual(qwen_models["qwen3.7-plus"]["capability_contract"]["capability_id"], "vision.analyze")
        self.assertEqual(qwen_models["qwen3.7-plus"]["capability_contract"]["adapter"]["adapter_id"], "qwen.vision.chat.v1")
        self.assertEqual(qwen_models["qwen3.7-plus"]["runtime_provider_contract"]["schema_version"], "astrabridge-runtime-provider-contract-v1")
        self.assertTrue(qwen_models["qwen3.7-plus"]["runtime_provider_contract"]["capability_metadata"]["vision"]["supports_image_inputs"])
        self.assertEqual(
            qwen_models["qwen3.7-plus"]["runtime_provider_contract"]["capability_metadata"]["vision"]["modality_limits"]["min_image_side_px"],
            11,
        )
        self.assertFalse(
            kimi_models["kimi-k2.6"]["runtime_provider_contract"]["capability_metadata"]["vision"]["modality_limits"]["remote_image_url_supported"]
        )

    def test_image_generation_candidates_include_wired_yunwu_and_qwen_models(self) -> None:
        registry = default_capability_registry()

        candidates = registry.resolve_candidates("image.generate")
        yunwu_models = {item["model"]: item for item in candidates if item["provider_id"] == "yunwu"}
        qwen_models = {item["model"]: item for item in candidates if item["provider_id"] == "qwen"}

        self.assertEqual(candidates[0]["model"], "gpt-image-2")
        self.assertIn("gpt-image-2", yunwu_models)
        self.assertIn("gpt-image-2-all", yunwu_models)
        self.assertNotIn("gpt-image-1", yunwu_models)
        self.assertEqual(set(yunwu_models), {"gpt-image-2", "gpt-image-2-all"})
        self.assertEqual(yunwu_models["gpt-image-2"]["source"], "adapter_override")
        self.assertFalse(yunwu_models["gpt-image-2"]["catalog_present"])
        self.assertEqual(yunwu_models["gpt-image-2"]["capability_contract"]["required_input_fields"], ["prompt"])
        self.assertEqual(yunwu_models["gpt-image-2"]["runtime_provider_contract"]["provider_metadata"]["provider_id"], "yunwu")
        self.assertIn("qwen-image-plus", qwen_models)
        self.assertEqual(qwen_models["qwen-image-plus"]["source"], "catalog_model")
        self.assertTrue(qwen_models["qwen-image-plus"]["catalog_present"])
        self.assertEqual(qwen_models["qwen-image-plus"]["capability_contract"]["adapter"]["adapter_id"], "qwen.image.dashscope.v1")

    def test_qwen_transcription_prefers_catalog_default_but_keeps_contract_model(self) -> None:
        registry = default_capability_registry()

        preferred = registry.preferred_candidate("speech.transcribe")
        candidates = registry.resolve_candidates("speech.transcribe")
        qwen_models = {item["model"]: item for item in candidates if item["provider_id"] == "qwen"}

        self.assertEqual(preferred["provider_id"], "qwen")
        self.assertIn("qwen3-asr-flash", qwen_models)
        self.assertEqual(qwen_models["qwen3-asr-flash"]["source"], "catalog_model")
        self.assertIn("audio", qwen_models["qwen3-asr-flash"]["input_modalities"])
        self.assertEqual(
            qwen_models["qwen3-asr-flash"]["runtime_provider_contract"]["capability_metadata"]["vision"]["modality_limits"]["audio_transport"],
            "chat_completions_input_audio_data_uri",
        )

    def test_speech_synthesize_keeps_qwen_default_and_exposes_cosyvoice_variants(self) -> None:
        registry = default_capability_registry()

        preferred = registry.preferred_candidate("speech.synthesize")
        candidates = registry.resolve_candidates("speech.synthesize")
        qwen_models = {item["model"]: item for item in candidates if item["provider_id"] == "qwen"}

        self.assertIsNotNone(preferred)
        self.assertEqual(preferred["model"], "qwen3-tts-flash")
        self.assertIn("qwen3-tts-instruct-flash", qwen_models)
        self.assertIn("cosyvoice-v3-plus", qwen_models)
        self.assertIn("cosyvoice-v3.5-plus", qwen_models)
        self.assertEqual(qwen_models["cosyvoice-v3-plus"]["capability_contract"]["adapter"]["adapter_id"], "qwen.tts.api.v1")
        self.assertIn("audio", qwen_models["cosyvoice-v3-plus"]["input_modalities"])

    def test_explicit_text_only_model_is_blocked_from_vision_candidates(self) -> None:
        registry = default_capability_registry()

        candidates = registry.resolve_candidates(
            "vision.analyze",
            configured_models=[
                {
                    "id": "qwen/qwen3.7-plus",
                    "provider": "qwen",
                    "native_model": "qwen3.7-plus",
                    "display_name": "Qwen3.7 Plus",
                    "enabled": True,
                    "input_modalities": ["text"],
                }
            ],
        )
        qwen_models = {item["model"]: item for item in candidates if item["provider_id"] == "qwen"}

        self.assertNotIn("qwen3.7-plus", qwen_models)
        self.assertIn("qwen3-vl-plus", qwen_models)

    def test_explicit_text_only_model_is_blocked_from_transcription_candidates(self) -> None:
        registry = default_capability_registry()

        candidates = registry.resolve_candidates(
            "speech.transcribe",
            configured_models=[
                {
                    "id": "qwen/qwen3-asr-flash",
                    "provider": "qwen",
                    "native_model": "qwen3-asr-flash",
                    "display_name": "Qwen3 ASR Flash",
                    "enabled": True,
                    "input_modalities": ["text"],
                }
            ],
        )
        qwen_models = {item["model"]: item for item in candidates if item["provider_id"] == "qwen"}

        self.assertNotIn("qwen3-asr-flash", qwen_models)

    def test_explicit_text_only_kimi_model_is_blocked_from_vision_candidates(self) -> None:
        registry = default_capability_registry()

        candidates = registry.resolve_candidates(
            "vision.analyze",
            configured_models=[
                {
                    "id": "kimi/kimi-k2.7-code",
                    "provider": "kimi",
                    "native_model": "kimi-k2.7-code",
                    "display_name": "Kimi K2.7 Code",
                    "enabled": True,
                    "input_modalities": ["text"],
                }
            ],
        )
        kimi_models = {item["model"]: item for item in candidates if item["provider_id"] == "kimi"}

        self.assertNotIn("kimi-k2.7-code", kimi_models)

    def test_unknown_vision_model_without_declared_modalities_is_not_exposed_even_if_adapter_matches(self) -> None:
        registry = CapabilityRegistry(
            adapter_contracts=[
                normalize_adapter_contract(
                    {
                        "adapter_id": "qwen.vision.test.v1",
                        "capability_id": "vision.analyze",
                        "provider_id": "qwen",
                        "model_match": ["qwen-vision-unknown"],
                    }
                )
            ]
        )

        candidates = registry.resolve_candidates("vision.analyze")

        self.assertEqual(candidates, [])

    def test_unknown_asr_model_without_declared_modalities_is_not_exposed_even_if_adapter_matches(self) -> None:
        registry = CapabilityRegistry(
            adapter_contracts=[
                normalize_adapter_contract(
                    {
                        "adapter_id": "qwen.asr.test.v1",
                        "capability_id": "speech.transcribe",
                        "provider_id": "qwen",
                        "model_match": ["qwen-asr-unknown"],
                    }
                )
            ]
        )

        candidates = registry.resolve_candidates("speech.transcribe")

        self.assertEqual(candidates, [])

    def test_glm_family_is_not_exposed_as_vision_candidate_by_default(self) -> None:
        registry = default_capability_registry()

        candidates = registry.resolve_candidates("vision.analyze")

        self.assertNotIn("glm", {item["provider_id"] for item in candidates})


if __name__ == "__main__":
    unittest.main()
