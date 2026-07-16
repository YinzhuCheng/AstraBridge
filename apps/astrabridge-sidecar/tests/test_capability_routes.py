from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.router_config_service import RouterConfigService
from astrabridge_sidecar.runtime_service import RuntimeService


class CapabilityRouteTests(unittest.TestCase):
    def test_router_config_persists_pinned_capability_route_and_resolves_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(store_path=root / "profiles.json")
            router_config = RouterConfigService(profiles, store_path=root / "router_config.json")

            route = router_config.save_capability_route(
                {
                    "capability_id": "vision.analyze",
                    "mode": "pinned",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                }
            )
            snapshot = router_config.snapshot()

            self.assertEqual(route["resolved_candidate"]["provider_id"], "kimi")
            self.assertEqual(route["resolved_candidate"]["model"], "kimi-k2.6")
            resolved = {item["capability_id"]: item for item in snapshot["capability_routes"]}
            self.assertEqual(resolved["vision.analyze"]["route_mode"], "pinned")
            self.assertEqual(resolved["vision.analyze"]["route_record"]["provider_id"], "kimi")
            kimi_provider = next(item for item in snapshot["providers"] if item["id"] == "kimi")
            self.assertIn("vision.analyze", dict(kimi_provider.get("capability_summary") or {}))
            self.assertTrue(
                isinstance(
                    route["resolved_candidate"]["runtime_provider_contract"]["capability_metadata"]["vision"]["modality_limits"],
                    dict,
                )
            )

    def test_runtime_service_raises_clear_error_for_missing_pinned_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(store_path=root / "profiles.json")
            router_config = RouterConfigService(profiles, store_path=root / "router_config.json")
            runtime = RuntimeService(Mock(), Mock(), profile_service=profiles, router_config_service=router_config)

            router_config.save_capability_route(
                {
                    "capability_id": "speech.transcribe",
                    "mode": "pinned",
                    "provider_id": "qwen",
                    "model": "nonexistent-asr-model",
                }
            )

            with self.assertRaisesRegex(RuntimeError, "no_capability_candidate"):
                runtime.resolve_capability_route("speech.transcribe")

    def test_capability_management_snapshot_exposes_ui_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(store_path=root / "profiles.json")
            router_config = RouterConfigService(profiles, store_path=root / "router_config.json")

            snapshot = router_config.capability_management_snapshot(
                mcp_config={
                    "servers": [
                        {
                            "name": "astrabridge_capabilities",
                            "enabled": True,
                            "tools": {
                                "astrabridge_capability_routes": {"approval_mode": "auto"},
                                "astrabridge_capability_vision_analyze": {"approval_mode": "prompt"},
                            },
                        }
                    ]
                }
            )
            capabilities = {item["capability_id"]: item for item in snapshot["capabilities"]}

            self.assertEqual(snapshot["schema_version"], "astrabridge-capability-management-v1")
            self.assertIn("vision.analyze", capabilities)
            self.assertIn("speech.synthesize", capabilities)
            self.assertEqual(capabilities["vision.analyze"]["contract"]["artifact_policy"], "persist_optional_visual_artifacts")
            self.assertIn("qwen_vision_smoke", capabilities["vision.analyze"]["smoke"]["case_ids"])
            self.assertEqual(capabilities["speech.synthesize"]["artifacts"]["recent_refs"], [])
            self.assertTrue(snapshot["mcp_preset"]["configured"])
            self.assertTrue(snapshot["mcp_preset"]["enabled"])
            self.assertEqual(snapshot["mcp_preset"]["configured_tool_count"], 2)
            self.assertEqual(snapshot["mcp_preset"]["health_status"], "partial")
            self.assertIn("astrabridge_capability_image_generate", snapshot["mcp_preset"]["missing_tool_names"])
            self.assertEqual(snapshot["mcp_preset"]["approval_modes"]["astrabridge_capability_routes"], "auto")


if __name__ == "__main__":
    unittest.main()
