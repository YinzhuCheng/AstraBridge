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
from astrabridge_sidecar.capabilities.vision_analyze_adapter import QWEN_VISION_MODELS


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
        self.assertIn("provider_id", specs["speech.transcribe"].output_schema.required_fields)
        self.assertIn("provider_id", specs["speech.synthesize"].output_schema.required_fields)
        self.assertIn("model", specs["speech.synthesize"].output_schema.required_fields)
        self.assertIn("operation", {field.name for field in specs["image.generate"].input_schema.fields})
        self.assertIn("operation", specs["image.generate"].output_schema.required_fields)

    def test_multimodal_contracts_expose_stable_abstract_fields_and_avoid_provider_specific_notes(self) -> None:
        specs = capability_spec_index(default_capability_specs())

        image_generate = specs["image.generate"]
        speech_transcribe = specs["speech.transcribe"]
        speech_synthesize = specs["speech.synthesize"]

        image_input_fields = {field.name: field for field in image_generate.input_schema.fields}
        image_output_fields = {field.name: field for field in image_generate.output_schema.fields}
        synth_output_fields = {field.name: field for field in speech_synthesize.output_schema.fields}

        self.assertEqual(image_input_fields["operation"].value_type, "string")
        self.assertIn("generate, edit, or transparent_asset", image_input_fields["operation"].description)
        self.assertEqual(image_output_fields["count_mismatch"].value_type, "boolean")
        self.assertEqual(synth_output_fields["audio_format"].value_type, "string")
        self.assertEqual(synth_output_fields["finish_reason"].value_type, "string")
        self.assertFalse(any("qwen" in note.lower() for note in speech_transcribe.notes))

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
        self.assertIn("qwen.image.dashscope.v1", contracts)
        self.assertIn("qwen.asr.chat.v1", contracts)
        self.assertIn("qwen.tts.api.v1", contracts)
        self.assertIn("kimi.vision.chat.v1", contracts)
        self.assertTrue(contracts["qwen.tts.api.v1"].supports_streaming)
        self.assertIn("audio_only_message_content", contracts["qwen.asr.chat.v1"].normalization_rules)
        self.assertIn("cosyvoice-v3-plus", contracts["qwen.tts.api.v1"].model_match)
        self.assertIn("final_audio_url_preferred_for_non_pcm_artifacts", contracts["qwen.tts.api.v1"].normalization_rules)

    def test_qwen_vision_adapter_contract_matches_runtime_gate(self) -> None:
        contracts = {contract.adapter_id: contract for contract in default_adapter_contracts()}

        self.assertEqual(set(contracts["qwen.vision.chat.v1"].model_match), set(QWEN_VISION_MODELS))


if __name__ == "__main__":
    unittest.main()
