from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.providers import classify_runtime_failure


class RuntimeFailureTaxonomyTests(unittest.TestCase):
    def test_classifier_maps_qwen_tiny_image_to_invalid_request_shape(self) -> None:
        notice = classify_runtime_failure(
            "qwen vision adapter requires image width and height greater than 10px; inline image is 1x1px.",
            current_provider="qwen",
            current_model="qwen3-vl-plus",
        ).to_payload()

        self.assertEqual(notice["category"], "invalid_request_shape")
        self.assertEqual(notice["recommended_action"], "retry_safer_request_shape")
        self.assertEqual(notice["provider"], "qwen")
        self.assertEqual(notice["model"], "qwen3-vl-plus")

    def test_classifier_maps_missing_artifact_to_artifact_issue(self) -> None:
        notice = classify_runtime_failure(
            "Provider returned no persisted local image artifact for the fixture.",
            current_provider="yunwu",
            current_model="gpt-image-2",
        ).to_payload()

        self.assertEqual(notice["category"], "artifact_issue")
        self.assertEqual(notice["recommended_action"], "inspect_artifact_persistence")

    def test_classifier_maps_provider_model_mismatch_to_fail_closed_route_inspection(self) -> None:
        notice = classify_runtime_failure(
            "provider/model mismatch: requested `qwen/qwen3.7-plus` but provider-backed result came from `kimi/kimi-k2.7-code`.",
            current_provider="qwen",
            current_model="qwen3.7-plus",
        ).to_payload()

        self.assertEqual(notice["category"], "provider_model_mismatch")
        self.assertEqual(notice["recommended_action"], "inspect_capability_route")
        self.assertEqual(notice["recoverability"], "fail_closed")


if __name__ == "__main__":
    unittest.main()
