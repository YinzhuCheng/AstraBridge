from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import default_capability_registry


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
        self.assertIn("image", qwen_models["qwen3.7-plus"]["input_modalities"])
        self.assertEqual(qwen_models["qwen3-vl-plus"]["source"], "adapter_override")
        self.assertTrue(any("expanded from catalog/profile defaults" in note for note in qwen_models["qwen3.7-plus"]["eligibility_notes"]))

    def test_yunwu_image_generation_keeps_adapter_override_models(self) -> None:
        registry = default_capability_registry()

        candidates = registry.resolve_candidates("image.generate")
        yunwu_models = {item["model"]: item for item in candidates if item["provider_id"] == "yunwu"}

        self.assertIn("gpt-image-2", yunwu_models)
        self.assertIn("flux-kontext-pro", yunwu_models)
        self.assertEqual(yunwu_models["gpt-image-2"]["source"], "adapter_override")
        self.assertFalse(yunwu_models["gpt-image-2"]["catalog_present"])

    def test_qwen_transcription_prefers_catalog_default_but_keeps_contract_model(self) -> None:
        registry = default_capability_registry()

        preferred = registry.preferred_candidate("speech.transcribe")
        candidates = registry.resolve_candidates("speech.transcribe")
        qwen_models = {item["model"]: item for item in candidates if item["provider_id"] == "qwen"}

        self.assertEqual(preferred["provider_id"], "qwen")
        self.assertIn("qwen3-asr-flash", qwen_models)
        self.assertEqual(qwen_models["qwen3-asr-flash"]["source"], "adapter_override")
        self.assertIn("audio", qwen_models["qwen3-asr-flash"]["input_modalities"])


if __name__ == "__main__":
    unittest.main()
