from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import (
    CapabilitySpec,
    capability_spec_index,
    default_adapter_contracts,
    default_capability_specs,
    normalize_adapter_contract,
    normalize_capability_spec,
    normalize_schema,
)


class CapabilitySpecTests(unittest.TestCase):
    def test_normalize_schema_marks_required_fields_and_dedupes(self) -> None:
        schema = normalize_schema(
            {
                "fields": [
                    {"name": "prompt", "value_type": "string"},
                    {"name": "prompt", "value_type": "string", "required": True},
                    {"name": "image_inputs", "value_type": "array[image_part]"},
                ],
                "required_fields": ["image_inputs", "missing_field"],
            }
        )

        self.assertEqual([field.name for field in schema.fields], ["prompt", "image_inputs"])
        self.assertEqual(schema.required_fields, ("image_inputs",))
        self.assertFalse(schema.fields[0].required)
        self.assertTrue(schema.fields[1].required)

    def test_normalize_capability_spec_rejects_unknown_lane_type(self) -> None:
        with self.assertRaises(ValueError):
            normalize_capability_spec(
                {
                    "capability_id": "bad.capability",
                    "lane_type": "unsupported",
                    "transport_mode": "request_response",
                    "input_schema": {"fields": []},
                    "output_schema": {"fields": []},
                    "artifact_policy": "none",
                    "provider_eligibility_rule": "none",
                }
            )

    def test_default_capability_specs_cover_required_taxonomy(self) -> None:
        specs = capability_spec_index(default_capability_specs())

        self.assertEqual(
            set(specs),
            {"web.search", "image.generate", "vision.analyze", "speech.transcribe", "speech.synthesize"},
        )
        self.assertEqual(specs["web.search"].lane_type, "web_standalone")
        self.assertEqual(specs["image.generate"].lane_type, "model_backed")
        self.assertEqual(specs["speech.synthesize"].transport_mode, "stream_sse")
        self.assertIn("audio_inputs", specs["speech.transcribe"].input_schema.required_fields)
        self.assertIn("artifact_refs", specs["speech.synthesize"].output_schema.required_fields)

    def test_default_capability_specs_can_roundtrip(self) -> None:
        specs = [CapabilitySpec.from_any(spec.to_dict()) for spec in default_capability_specs()]
        self.assertEqual(len(specs), 5)
        self.assertEqual(specs[2].capability_id, "vision.analyze")


class AdapterContractTests(unittest.TestCase):
    def test_normalize_adapter_contract_dedupes_model_matches(self) -> None:
        contract = normalize_adapter_contract(
            {
                "adapter_id": "qwen.test",
                "capability_id": "vision.analyze",
                "provider_id": "qwen",
                "model_match": ["qwen3.7-plus", "qwen3.7-plus", "", "qwen3-vl-plus"],
                "normalization_rules": ["a", "a", "b"],
            }
        )

        self.assertEqual(contract.model_match, ("qwen3.7-plus", "qwen3-vl-plus"))
        self.assertEqual(contract.normalization_rules, ("a", "b"))

    def test_default_adapter_contracts_cover_smoked_paths(self) -> None:
        contracts = {contract.adapter_id: contract for contract in default_adapter_contracts()}

        self.assertIn("yunwu.image.generate.v1", contracts)
        self.assertIn("qwen.asr.chat.v1", contracts)
        self.assertIn("qwen.tts.omni.v1", contracts)
        self.assertIn("kimi.vision.chat.v1", contracts)
        self.assertTrue(contracts["qwen.tts.omni.v1"].supports_streaming)
        self.assertIn("audio_only_message_content", contracts["qwen.asr.chat.v1"].normalization_rules)


if __name__ == "__main__":
    unittest.main()
