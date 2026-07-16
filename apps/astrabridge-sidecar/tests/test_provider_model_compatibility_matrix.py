from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.provider_model_compatibility_matrix import (
    ENTRY_SECTION_NAMES,
    PROVIDER_MODEL_COMPATIBILITY_MATRIX_SCHEMA_VERSION,
    assert_secret_free_provider_model_compatibility_matrix,
    compatibility_matrix_entry_template,
    empty_provider_model_compatibility_matrix,
)
from astrabridge_sidecar.security import SecurityError


class ProviderModelCompatibilityMatrixTests(unittest.TestCase):
    def test_empty_matrix_has_required_sections(self) -> None:
        matrix = empty_provider_model_compatibility_matrix()
        entry = compatibility_matrix_entry_template()

        self.assertEqual(matrix["schema_version"], PROVIDER_MODEL_COMPATIBILITY_MATRIX_SCHEMA_VERSION)
        self.assertEqual(matrix["entry_section_names"], list(ENTRY_SECTION_NAMES))
        self.assertEqual(matrix["matrix_scope"]["web_lane_policy"], "standalone")
        self.assertEqual(entry["entry_kind"], "model")
        for section in ENTRY_SECTION_NAMES:
            self.assertIn(section, entry)

    def test_secret_free_assertion_accepts_usage_tokens_and_evidence_paths(self) -> None:
        matrix = empty_provider_model_compatibility_matrix()
        matrix["generated_at"] = "2026-07-04T20:00:00+09:00"
        matrix["matrix_id"] = "provider-compatibility-baseline"
        matrix["matrix_scope"]["source_kind"] = "registry_runtime_and_evidence"
        matrix["matrix_scope"]["managed_session_mode"] = "managed_user"
        matrix["matrix_scope"]["managed_username"] = "astra"
        matrix["matrix_scope"]["registry_provider_ids"] = ["qwen"]
        matrix["matrix_scope"]["effective_provider_ids"] = ["qwen"]

        entry = compatibility_matrix_entry_template()
        entry["entry_id"] = "qwen/qwen3.7-plus"
        entry["provider_id"] = "qwen"
        entry["model_id"] = "qwen/qwen3.7-plus"
        entry["display_name"] = "Qwen 3.7 Plus"
        entry["declared_capability"]["source_of_truth"] = ["providers/registry.py"]
        entry["declared_capability"]["protocol"] = "qwen_responses"
        entry["runtime_normalized_contract"]["source_of_truth"] = ["model_catalog/catalog.py"]
        entry["runtime_normalized_contract"]["managed_key_available"] = True
        entry["runtime_normalized_contract"]["reasoning_state"] = {"visibility": "visible_summary_only", "replayable": False}
        entry["runtime_normalized_contract"]["context_window"] = {"declared_context_window": 262144, "auto_compact_status": "configured_unverified"}
        entry["validated_evidence"]["validation_status"] = "pass"
        entry["validated_evidence"]["health_status"] = "pass"
        entry["validated_evidence"]["evidence_paths"] = ["PRIVATE/agent-bench-dogfood/reports/step19-cross-provider-routing-record.json"]
        entry["validated_evidence"]["usage_signals"] = {
            "input_tokens": 51,
            "output_tokens": 183,
            "reasoning_tokens": 178,
            "total_tokens": 234,
        }
        entry["overall_status"] = "partial"
        matrix["entries"].append(entry)

        assert_secret_free_provider_model_compatibility_matrix(matrix)

    def test_secret_free_assertion_rejects_secret_like_fields(self) -> None:
        matrix = empty_provider_model_compatibility_matrix()
        entry = compatibility_matrix_entry_template()
        entry["entry_id"] = "bad-entry"
        entry["provider_id"] = "qwen"
        entry["model_id"] = "qwen/qwen3.7-plus"
        entry["overall_status"] = "unknown"
        entry["validated_evidence"]["validation_status"] = "unknown"
        entry["validated_evidence"]["api_key"] = "live-secret-value"
        matrix["entries"].append(entry)

        with self.assertRaises(SecurityError):
            assert_secret_free_provider_model_compatibility_matrix(matrix)

    def test_secret_free_assertion_rejects_desktop_key_path(self) -> None:
        matrix = empty_provider_model_compatibility_matrix()
        entry = compatibility_matrix_entry_template()
        entry["entry_id"] = "desktop-key-path"
        entry["provider_id"] = "qwen"
        entry["model_id"] = "qwen/qwen3.7-plus"
        entry["overall_status"] = "unknown"
        entry["validated_evidence"]["validation_status"] = "unknown"
        entry["validated_evidence"]["notes"] = [r"C:\Users\cyz19\Desktop\key.txt should never appear here"]
        matrix["entries"].append(entry)

        with self.assertRaises(SecurityError):
            assert_secret_free_provider_model_compatibility_matrix(matrix)


if __name__ == "__main__":
    unittest.main()
