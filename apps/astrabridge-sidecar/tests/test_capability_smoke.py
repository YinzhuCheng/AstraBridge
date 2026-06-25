from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities.smoke import capability_smoke_snapshot
from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.router_config_service import RouterConfigService


class FakeCapabilityRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def invoke(self, capability_id: str, payload: dict) -> dict:
        self.calls.append((capability_id, payload))
        return {
            "schema_version": "fake-provider-result-v1",
            "capability_id": capability_id,
            "provider_id": "qwen",
            "model": "qwen3-vl-plus",
            "text": "red square",
            "usage": {"total_tokens": 12},
            "artifact_refs": [{"artifact_type": "summary", "path": "D:/AstraBridge/.astrabridge/capabilities/fake/summary.json"}],
            "audio_bytes_base64": "must-not-leak",
            "route": {
                "capability_id": capability_id,
                "route_mode": "auto",
                "resolved_candidate": {"provider_id": "qwen", "model": "qwen3-vl-plus", "adapter_id": "qwen.vision"},
            },
        }


class FailingCapabilityRuntime:
    def invoke(self, capability_id: str, payload: dict) -> dict:
        raise RuntimeError("provider rejected Authorization: Bearer unitfake")


class CapabilitySmokeTests(unittest.TestCase):
    def test_dry_run_smoke_is_deterministic_for_model_backed_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(store_path=root / "profiles.json")
            router_config = RouterConfigService(profiles, store_path=root / "router_config.json")
            models = router_config.models()

            for capability_id in ["image.generate", "vision.analyze", "speech.transcribe", "speech.synthesize"]:
                smoke = capability_smoke_snapshot({"capability_id": capability_id}, configured_models=models)

                self.assertEqual(smoke["schema_version"], "astrabridge-capability-smoke-result-v1")
                self.assertEqual(smoke["capability_id"], capability_id)
                self.assertEqual(smoke["mode"], "dry_run")
                self.assertEqual(smoke["status"], "pass")
                self.assertFalse(smoke["provider_invoked"])
                self.assertIn("sample_input", smoke["sanitized_request"])
                self.assertIn("sample_output", smoke["sanitized_response"])
                self.assertEqual(smoke["artifact_refs"], [])

    def test_provider_backed_smoke_requires_explicit_authorization(self) -> None:
        with self.assertRaisesRegex(ValueError, "allow_provider=true"):
            capability_smoke_snapshot({"capability_id": "vision.analyze", "mode": "provider"})

    def test_provider_backed_smoke_invokes_runtime_and_sanitizes_result(self) -> None:
        runtime = FakeCapabilityRuntime()
        smoke = capability_smoke_snapshot(
            {"capability_id": "vision.analyze", "mode": "provider", "allow_provider": True},
            runtime=runtime,
        )

        self.assertEqual(smoke["status"], "pass")
        self.assertTrue(smoke["provider_invoked"])
        self.assertEqual(runtime.calls[0][0], "vision.analyze")
        self.assertIn("generated_red_square_png", str(smoke["sanitized_request"]))
        self.assertEqual(smoke["sanitized_response"]["provider_result"]["text_preview"], "red square")
        self.assertNotIn("must-not-leak", str(smoke["sanitized_response"]))
        self.assertNotIn("secret-token-value", str(smoke["sanitized_response"]))
        self.assertEqual(smoke["artifact_refs"][0]["artifact_type"], "summary")

    def test_provider_backed_smoke_sanitizes_provider_errors(self) -> None:
        smoke = capability_smoke_snapshot(
            {"capability_id": "vision.analyze", "mode": "provider", "allow_provider": True},
            runtime=FailingCapabilityRuntime(),
        )

        self.assertEqual(smoke["status"], "fail")
        self.assertIn("Bearer [redacted]", smoke["sanitized_response"]["provider_error"])
        self.assertNotIn("unitfake", smoke["sanitized_response"]["provider_error"])

    def test_web_standalone_capability_rejected_for_manual_provider_smoke(self) -> None:
        with self.assertRaisesRegex(ValueError, "not model-backed"):
            capability_smoke_snapshot({"capability_id": "web.search"})


if __name__ == "__main__":
    unittest.main()
