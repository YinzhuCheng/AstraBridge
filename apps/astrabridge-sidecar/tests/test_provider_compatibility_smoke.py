from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.provider_compatibility_smoke import (
    assert_secret_free_provider_compatibility_smoke_report,
    run_provider_compatibility_smoke,
)
from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.router_config_service import RouterConfigService


class FakeCapabilityRuntime:
    def __init__(self, *, empty_text: bool = False) -> None:
        self.empty_text = empty_text
        self.calls: list[tuple[str, dict]] = []

    def invoke(self, capability_id: str, payload: dict) -> dict:
        self.calls.append((capability_id, payload))
        return {
            "schema_version": "fake-provider-result-v1",
            "capability_id": capability_id,
            "provider_id": payload.get("provider_id") or "qwen",
            "model": payload.get("model") or "qwen3-vl-plus",
            "text": "" if self.empty_text else "red square",
            "usage": {"input_tokens": 7, "output_tokens": 5, "total_tokens": 12},
            "artifact_refs": [{"artifact_type": "summary", "path": "D:/AstraBridge/PRIVATE/provider-compatibility/fake-summary.json"}],
            "audio_bytes_base64": "must-not-leak",
            "route": {
                "capability_id": capability_id,
                "route_mode": "explicit",
                "resolved_candidate": {
                    "provider_id": payload.get("provider_id") or "qwen",
                    "model": payload.get("model") or "qwen3-vl-plus",
                    "adapter_id": "qwen.vision",
                },
            },
        }


class FailingCapabilityRuntime:
    def invoke(self, capability_id: str, payload: dict) -> dict:
        raise RuntimeError("provider rejected Authorization: Bearer unitfake")


class MismatchedCapabilityRuntime:
    def invoke(self, capability_id: str, payload: dict) -> dict:
        return {
            "schema_version": "fake-provider-result-v1",
            "capability_id": capability_id,
            "provider_id": "kimi",
            "model": "kimi-k2.7-code",
            "text": "The image is",
            "usage": {"input_tokens": 12, "output_tokens": 9, "total_tokens": 21},
            "artifact_refs": [{"artifact_type": "summary", "path": "D:/AstraBridge/PRIVATE/provider-compatibility/fake-summary.json"}],
            "route": {
                "capability_id": capability_id,
                "route_mode": "auto",
                "resolved_candidate": {
                    "provider_id": "kimi",
                    "model": "kimi-k2.7-code",
                    "adapter_id": "kimi.vision",
                },
            },
        }


class RouteLessCapabilityRuntime:
    def invoke(self, capability_id: str, payload: dict) -> dict:
        return {
            "schema_version": "fake-provider-result-v1",
            "capability_id": capability_id,
            "provider_id": payload.get("provider_id") or "qwen",
            "model": payload.get("model") or "qwen3-vl-plus",
            "text": "red square",
            "usage": {"input_tokens": 7, "output_tokens": 5, "total_tokens": 12},
            "artifact_refs": [{"artifact_type": "summary", "path": "D:/AstraBridge/PRIVATE/provider-compatibility/fake-summary.json"}],
        }


class ProviderCompatibilitySmokeTests(unittest.TestCase):
    def test_runner_writes_secret_free_report_and_matrix_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            models = _configured_models(root)
            runtime = FakeCapabilityRuntime()
            report = run_provider_compatibility_smoke(
                {
                    "run_id": "unit-smoke",
                    "cases": [
                        {"case_id": "dry-vision", "capability_id": "vision.analyze"},
                        {
                            "case_id": "provider-vision",
                            "capability_id": "vision.analyze",
                            "mode": "provider",
                            "allow_provider": True,
                            "provider_id": "qwen",
                            "model": "qwen3-vl-plus",
                        },
                    ],
                },
                configured_models=models,
                runtime=runtime,
                workspace_root=root,
            )

            self.assertEqual(report["schema_version"], "astrabridge-provider-compatibility-smoke-report-v1")
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["counts"]["pass"], 2)
            self.assertEqual(len(report["matrix_updates"]), 2)
            assert_secret_free_provider_compatibility_smoke_report(report)
            run_dir = root / "PRIVATE" / "provider-compatibility" / "runs" / "unit-smoke"
            self.assertTrue((run_dir / "summary.json").exists())
            self.assertTrue((run_dir / "report.md").exists())
            self.assertTrue((run_dir / "cases" / "provider-vision.json").exists())
            text = (run_dir / "summary.json").read_text(encoding="utf-8")
            self.assertNotIn("must-not-leak", text)
            self.assertNotIn("data:image/", text)
            self.assertNotIn("unitfake", text)
            self.assertEqual(runtime.calls[0][1]["provider_id"], "qwen")
            self.assertEqual(runtime.calls[0][1]["model"], "qwen3-vl-plus")

    def test_runner_maps_provider_warnings_to_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = run_provider_compatibility_smoke(
                {
                    "run_id": "unit-partial",
                    "cases": [
                        {
                            "case_id": "empty-vision",
                            "capability_id": "vision.analyze",
                            "mode": "provider",
                            "allow_provider": True,
                            "provider_id": "qwen",
                            "model": "qwen3-vl-plus",
                        }
                    ],
                },
                configured_models=_configured_models(root),
                runtime=FakeCapabilityRuntime(empty_text=True),
                workspace_root=root,
            )

            self.assertEqual(report["status"], "partial")
            self.assertEqual(report["cases"][0]["status"], "partial")
            self.assertEqual(report["matrix_updates"][0]["validation_status"], "partial")
            self.assertIn("semantic output is empty", " ".join(report["cases"][0]["warnings"]))
            self.assertEqual(report["cases"][0]["failure_notice"]["category"], "semantic_no_output")
            self.assertEqual(report["cases"][0]["failure_notice"]["recommended_action"], "mark_capability_unverified")

    def test_runner_records_failed_provider_errors_without_raw_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = run_provider_compatibility_smoke(
                {
                    "run_id": "unit-fail",
                    "cases": [
                        {
                            "case_id": "provider-failure",
                            "capability_id": "vision.analyze",
                            "mode": "provider",
                            "allow_provider": True,
                            "provider_id": "qwen",
                            "model": "qwen3-vl-plus",
                        }
                    ],
                },
                configured_models=_configured_models(root),
                runtime=FailingCapabilityRuntime(),
                workspace_root=root,
            )

            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["cases"][0]["status"], "fail")
            self.assertIn("Bearer [redacted]", " ".join(report["cases"][0]["reasons"]))
            self.assertNotIn("unitfake", str(report))
            self.assertEqual(report["cases"][0]["failure_notice"]["category"], "unknown")
            assert_secret_free_provider_compatibility_smoke_report(report)

    def test_runner_fails_closed_on_provider_model_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = run_provider_compatibility_smoke(
                {
                    "run_id": "unit-mismatch",
                    "cases": [
                        {
                            "case_id": "provider-vision-mismatch",
                            "capability_id": "vision.analyze",
                            "mode": "provider",
                            "allow_provider": True,
                            "provider_id": "qwen",
                            "model": "qwen3-vl-plus",
                        }
                    ],
                },
                configured_models=_configured_models(root),
                runtime=MismatchedCapabilityRuntime(),
                workspace_root=root,
            )

            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["cases"][0]["status"], "fail")
            self.assertEqual(report["cases"][0]["failure_notice"]["category"], "provider_model_mismatch")
            self.assertEqual(report["cases"][0]["failure_notice"]["recommended_action"], "inspect_capability_route")
            self.assertEqual(report["cases"][0]["failure_notice"]["requested_provider"], "qwen")
            self.assertEqual(report["cases"][0]["failure_notice"]["observed_provider"], "kimi")

    def test_runner_preserves_explicit_route_snapshot_even_when_default_auto_route_differs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = run_provider_compatibility_smoke(
                {
                    "run_id": "unit-explicit-route",
                    "cases": [
                        {
                            "case_id": "provider-vision-explicit",
                            "capability_id": "vision.analyze",
                            "mode": "provider",
                            "allow_provider": True,
                            "provider_id": "qwen",
                            "model": "qwen3-vl-plus",
                        }
                    ],
                },
                configured_models=_configured_models(root),
                runtime=RouteLessCapabilityRuntime(),
                workspace_root=root,
            )

            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["cases"][0]["status"], "pass")
            self.assertEqual(report["cases"][0]["route"]["route_mode"], "explicit")
            self.assertEqual(report["cases"][0]["route"]["resolved_candidate"]["provider_id"], "qwen")
            self.assertEqual(report["cases"][0]["route"]["resolved_candidate"]["model"], "qwen3-vl-plus")

    def test_runner_records_skipped_and_blocked_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report = run_provider_compatibility_smoke(
                {
                    "run_id": "unit-blocked",
                    "cases": [
                        {"case_id": "manual-skip", "capability_id": "vision.analyze", "skip_reason": "provider maintenance window"},
                        {
                            "case_id": "missing-auth",
                            "capability_id": "vision.analyze",
                            "mode": "provider",
                            "provider_id": "qwen",
                            "model": "qwen3-vl-plus",
                        },
                        {
                            "case_id": "no-route",
                            "capability_id": "vision.analyze",
                            "provider_id": "missing-provider",
                            "model": "missing-model",
                        },
                    ],
                },
                configured_models=_configured_models(root),
                runtime=FakeCapabilityRuntime(),
                workspace_root=root,
            )

            statuses = {case["case_id"]: case["status"] for case in report["cases"]}
            self.assertEqual(statuses["manual-skip"], "skipped")
            self.assertEqual(statuses["missing-auth"], "blocked")
            self.assertEqual(statuses["no-route"], "blocked")
            self.assertIn("no_capability_candidate", " ".join(report["cases"][2]["reasons"]))
            self.assertEqual(report["matrix_updates"][0]["validation_status"], "skipped")
            self.assertEqual(report["matrix_updates"][1]["validation_status"], "blocked")
            self.assertEqual(report["cases"][2]["failure_notice"]["category"], "unsupported_model")


def _configured_models(root: Path) -> list[dict]:
    profiles = ProfileService(store_path=root / "profiles.json")
    router_config = RouterConfigService(profiles, store_path=root / "router_config.json")
    return router_config.models()


if __name__ == "__main__":
    unittest.main()
