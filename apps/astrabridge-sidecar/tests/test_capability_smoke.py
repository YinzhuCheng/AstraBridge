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
        if capability_id == "image.generate":
            return {
                "schema_version": "fake-provider-result-v1",
                "capability_id": capability_id,
                "provider_id": "yunwu",
                "model": "gpt-image-2",
                "operation": payload.get("operation") or "generate",
                "requested_n": 1,
                "actual_n": 1,
                "artifact_refs": [
                    {
                        "asset_id": "yunwu-asset-1",
                        "local_path": "D:/workspace/.astrabridge/assets/generated/yunwu-asset-1.png",
                        "result_index": 0,
                        "actual_width": 1024,
                        "actual_height": 1024,
                        "actual_format": "png",
                    }
                ],
                "route": {
                    "capability_id": capability_id,
                    "route_mode": "auto",
                    "resolved_candidate": {"provider_id": "yunwu", "model": "gpt-image-2", "adapter_id": "yunwu.image.generate.v1"},
                },
            }
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


class EmptyImageArtifactRuntime:
    def invoke(self, capability_id: str, payload: dict) -> dict:
        return {
            "schema_version": "fake-provider-result-v1",
            "capability_id": capability_id,
            "provider_id": "yunwu",
            "model": "gpt-image-2",
            "operation": "generate",
            "requested_n": 1,
            "actual_n": 1,
            "artifact_refs": [{"asset_id": "", "local_path": "", "result_index": 0}],
        }


class RouteLessCapabilityRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def invoke(self, capability_id: str, payload: dict) -> dict:
        self.calls.append((capability_id, payload))
        if capability_id == "speech.synthesize":
            return {
                "schema_version": "fake-provider-result-v1",
                "capability_id": capability_id,
                "provider_id": payload.get("provider_id") or "qwen",
                "model": payload.get("model") or "qwen3-tts-instruct-flash",
                "mime_type": "audio/wav",
                "audio_format": "wav",
                "artifact_refs": [{"artifact_type": "audio", "path": "D:/AstraBridge/.astrabridge/capabilities/fake/output.wav"}],
            }
        return {
            "schema_version": "fake-provider-result-v1",
            "capability_id": capability_id,
            "provider_id": payload.get("provider_id") or "qwen",
            "model": payload.get("model") or "qwen3-vl-plus",
            "text": "red square",
            "usage": {"total_tokens": 12},
            "artifact_refs": [{"artifact_type": "summary", "path": "D:/AstraBridge/.astrabridge/capabilities/fake/summary.json"}],
        }


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
                self.assertEqual(smoke["usage_signal"]["status"], "not_available")
                self.assertEqual(smoke["usage_signal"]["reason"], "dry_run_no_provider_call")
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
        self.assertEqual(smoke["usage_signal"]["status"], "available")
        self.assertEqual(smoke["usage_signal"]["tokens"]["total_tokens"], 12)
        self.assertEqual(smoke["sanitized_response"]["provider_result"]["usage_signal"]["tokens"]["total_tokens"], 12)
        self.assertNotIn("must-not-leak", str(smoke["sanitized_response"]))
        self.assertNotIn("secret-token-value", str(smoke["sanitized_response"]))
        self.assertEqual(smoke["artifact_refs"][0]["artifact_type"], "summary")

    def test_provider_backed_image_generate_smoke_accepts_custom_asset_payload(self) -> None:
        runtime = FakeCapabilityRuntime()
        smoke = capability_smoke_snapshot(
            {
                "capability_id": "image.generate",
                "mode": "provider",
                "allow_provider": True,
                "prompt": "Generate a small benchmark badge.",
                "model": "gpt-image-2",
                "size": "1024x1024",
                "quality": "medium",
                "image_format": "png",
                "workspace_root": "D:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace",
                "purpose": "agent_bench_step14_asset_generation",
            },
            runtime=runtime,
        )

        self.assertEqual(smoke["status"], "pass")
        self.assertEqual(runtime.calls[0][0], "image.generate")
        payload = runtime.calls[0][1]
        self.assertEqual(payload["prompt"], "Generate a small benchmark badge.")
        self.assertEqual(payload["model"], "gpt-image-2")
        self.assertEqual(payload["quality"], "medium")
        self.assertEqual(payload["image_format"], "png")
        self.assertEqual(payload["operation"], "generate")
        self.assertEqual(payload["workspace_root"], "D:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace")
        self.assertEqual(smoke["sanitized_request"]["sample_input"]["workspace_root"], payload["workspace_root"])

    def test_provider_backed_speech_synthesize_smoke_uses_qwen_tts_defaults(self) -> None:
        runtime = FakeCapabilityRuntime()
        smoke = capability_smoke_snapshot(
            {
                "capability_id": "speech.synthesize",
                "mode": "provider",
                "allow_provider": True,
                "workspace_root": "D:/AstraBridge/PRIVATE/provider-compatibility/step7",
            },
            runtime=runtime,
        )

        self.assertEqual(smoke["status"], "pass")
        self.assertEqual(runtime.calls[0][0], "speech.synthesize")
        payload = runtime.calls[0][1]
        self.assertEqual(payload["voice"], "Cherry")
        self.assertEqual(payload["audio_format"], "wav")
        self.assertEqual(payload["workspace_root"], "D:/AstraBridge/PRIVATE/provider-compatibility/step7")

    def test_provider_backed_image_generate_smoke_fails_empty_artifact_refs(self) -> None:
        smoke = capability_smoke_snapshot(
            {"capability_id": "image.generate", "mode": "provider", "allow_provider": True},
            runtime=EmptyImageArtifactRuntime(),
        )

        self.assertEqual(smoke["status"], "fail")
        self.assertIn("no persisted local image artifact", " ".join(smoke["sanitized_response"]["notes"]))

    def test_provider_backed_vision_smoke_accepts_custom_image_paths(self) -> None:
        runtime = FakeCapabilityRuntime()
        smoke = capability_smoke_snapshot(
            {
                "capability_id": "vision.analyze",
                "mode": "provider",
                "allow_provider": True,
                "prompt": "Read the task card.",
                "image_paths": ["D:/AstraBridge/PRIVATE/agent-bench-dogfood/raw/step13-multimodal-input/visual-fixture.png"],
                "detail": "high",
                "max_output_tokens": 512,
            },
            runtime=runtime,
        )

        self.assertEqual(smoke["status"], "pass")
        self.assertEqual(runtime.calls[0][0], "vision.analyze")
        payload = runtime.calls[0][1]
        self.assertEqual(payload["prompt"], "Read the task card.")
        self.assertEqual(payload["detail"], "high")
        self.assertEqual(payload["max_output_tokens"], 512)
        self.assertEqual(payload["image_paths"], ["D:/AstraBridge/PRIVATE/agent-bench-dogfood/raw/step13-multimodal-input/visual-fixture.png"])
        self.assertEqual(smoke["sanitized_request"]["sample_input"]["image_paths"], payload["image_paths"])
        self.assertNotIn("data:image/", str(smoke["sanitized_request"]))

    def test_provider_backed_default_fixtures_preserve_explicit_provider_and_model(self) -> None:
        runtime = FakeCapabilityRuntime()

        capability_smoke_snapshot(
            {
                "capability_id": "vision.analyze",
                "mode": "provider",
                "allow_provider": True,
                "provider_id": "qwen",
                "model": "qwen3-vl-plus",
                "workspace_root": "D:/AstraBridge",
            },
            runtime=runtime,
        )
        capability_smoke_snapshot(
            {
                "capability_id": "speech.transcribe",
                "mode": "provider",
                "allow_provider": True,
                "provider_id": "qwen",
                "model": "qwen3-asr-flash",
                "workspace_root": "D:/AstraBridge",
            },
            runtime=runtime,
        )

        vision_payload = runtime.calls[0][1]
        asr_payload = runtime.calls[1][1]

        self.assertEqual(vision_payload["provider_id"], "qwen")
        self.assertEqual(vision_payload["model"], "qwen3-vl-plus")
        self.assertEqual(vision_payload["workspace_root"], "D:/AstraBridge")
        self.assertEqual(asr_payload["provider_id"], "qwen")
        self.assertEqual(asr_payload["model"], "qwen3-asr-flash")
        self.assertEqual(asr_payload["workspace_root"], "D:/AstraBridge")

    def test_provider_backed_vision_smoke_reports_explicit_route_even_when_default_auto_route_differs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(store_path=root / "profiles.json")
            router_config = RouterConfigService(profiles, store_path=root / "router_config.json")
            runtime = RouteLessCapabilityRuntime()

            smoke = capability_smoke_snapshot(
                {
                    "capability_id": "vision.analyze",
                    "mode": "provider",
                    "allow_provider": True,
                    "provider_id": "qwen",
                    "model": "qwen3-vl-plus",
                    "workspace_root": "D:/AstraBridge",
                },
                configured_models=router_config.models(),
                runtime=runtime,
            )

        self.assertEqual(runtime.calls[0][1]["provider_id"], "qwen")
        self.assertEqual(runtime.calls[0][1]["model"], "qwen3-vl-plus")
        self.assertEqual(smoke["route"]["route_mode"], "explicit")
        self.assertEqual(smoke["route"]["resolved_candidate"]["provider_id"], "qwen")
        self.assertEqual(smoke["route"]["resolved_candidate"]["model"], "qwen3-vl-plus")

    def test_provider_backed_tts_smoke_reports_explicit_instruct_model_even_without_runtime_route_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(store_path=root / "profiles.json")
            router_config = RouterConfigService(profiles, store_path=root / "router_config.json")
            runtime = RouteLessCapabilityRuntime()

            smoke = capability_smoke_snapshot(
                {
                    "capability_id": "speech.synthesize",
                    "mode": "provider",
                    "allow_provider": True,
                    "provider_id": "qwen",
                    "model": "qwen3-tts-instruct-flash",
                    "workspace_root": "D:/AstraBridge",
                    "instructions": "Speak calmly.",
                },
                configured_models=router_config.models(),
                runtime=runtime,
            )

        self.assertEqual(runtime.calls[0][1]["model"], "qwen3-tts-instruct-flash")
        self.assertEqual(smoke["route"]["route_mode"], "explicit")
        self.assertEqual(smoke["route"]["resolved_candidate"]["provider_id"], "qwen")
        self.assertEqual(smoke["route"]["resolved_candidate"]["model"], "qwen3-tts-instruct-flash")

    def test_provider_backed_speech_transcribe_smoke_accepts_custom_audio_inputs(self) -> None:
        runtime = FakeCapabilityRuntime()
        smoke = capability_smoke_snapshot(
            {
                "capability_id": "speech.transcribe",
                "mode": "provider",
                "allow_provider": True,
                "provider_id": "qwen",
                "model": "qwen3-asr-flash",
                "audio_inputs": [{"data_uri": "data:audio/wav;base64,UklGRg==", "mime_type": "audio/wav"}],
                "language_hint": "en",
                "workspace_root": "D:/AstraBridge",
            },
            runtime=runtime,
        )

        self.assertEqual(smoke["status"], "pass")
        self.assertEqual(runtime.calls[0][0], "speech.transcribe")
        payload = runtime.calls[0][1]
        self.assertEqual(payload["provider_id"], "qwen")
        self.assertEqual(payload["model"], "qwen3-asr-flash")
        self.assertEqual(payload["language_hint"], "en")
        self.assertEqual(payload["audio_inputs"][0]["mime_type"], "audio/wav")
        self.assertTrue(payload["audio_inputs"][0]["data_uri"].startswith("data:audio/wav;base64,"))
        self.assertEqual(smoke["sanitized_request"]["sample_input"]["audio_inputs"][0]["fixture"], "inline_audio_data")
        self.assertNotIn("data:audio/", str(smoke["sanitized_request"]))

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
