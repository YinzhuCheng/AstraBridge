from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.profile_service import ProfileService  # noqa: E402
from astrabridge_sidecar.providers.execution_route import (  # noqa: E402
    EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
    resolve_execution_route,
)
from astrabridge_sidecar.router_config_service import RouterConfigService  # noqa: E402
from astrabridge_sidecar.router_service import RouterService  # noqa: E402


class ExecutionRouteOwnershipTests(unittest.TestCase):
    def _services(self, root: Path) -> tuple[ProfileService, RouterConfigService, RouterService]:
        profiles = ProfileService(root / "profiles.json")
        config = RouterConfigService(profiles, root / "router.json")
        return profiles, config, RouterService(profiles, config, port=0)

    def _tool_ready_model(self) -> dict[str, object]:
        return {
            "id": "deepseek/route-contract-probe",
            "provider": "deepseek",
            "native_model": "route-contract-probe",
            "display_name": "Route contract probe",
            "tool_mode": "native",
            "apply_patch_tool_type": "json",
            "supports_mcp_tools": True,
            "mcp_tool_call_policy": "verified",
            "mcp_smoke_status": "verified",
            "command_execution_status": "verified",
            "advertised_context_window": 1_000,
        }

    def _evidence_for(self, model: dict[str, object], *, state: str) -> dict[str, object]:
        route = dict(model["execution_route"])
        subject = dict(route["subject"])
        endpoint = dict(route["endpoint"])
        adapter = dict(route["adapter"])
        return {
            "schema_version": EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
            "state": state,
            "subject": {
                **subject,
                "endpoint_fingerprint": endpoint["fingerprint"],
                "adapter_signature": adapter["signature"],
            },
            "source_provenance": {
                "kind": "controlled_smoke",
                "issuer": "astrabridge",
                "record_id": "step-4-route-ownership",
            },
            "evidence_refs": ["PRIVATE/provider-compatibility/runs/step4/route-contract-probe.json"],
            "validation_scope": ["coding_route", "tools"],
            "verified_at": "2026-07-27T00:00:00+00:00",
            "expires_at": "2026-08-01T00:00:00+00:00",
        }

    @staticmethod
    def _model(config: RouterConfigService, model_id: str) -> dict[str, object]:
        return next(item for item in config.models() if str(item.get("id") or "") == model_id)

    def test_provider_backend_remains_a_candidate_but_router_resolves_review_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles, config, router = self._services(root)
            provider = next(item for item in config.providers() if item["id"] == "deepseek")
            config.upsert_provider({**provider, "runtime_backend": "native_kernel"})

            saved_profile = next(
                item
                for item in profiles.list_profiles()["profiles"]
                if str(item.get("profile_id") or "") == "deepseek-default"
            )
            route_profile = router._resolve_profile({"model": "deepseek/deepseek-v4-pro"})  # noqa: SLF001
            catalog_entry = next(item for item in router.list_models() if item["id"] == "deepseek/deepseek-v4-pro")

            self.assertEqual(saved_profile["execution_backend"], "native_kernel")
            self.assertEqual(route_profile["configured_execution_backend"], "native_kernel")
            self.assertEqual(route_profile["execution_backend"], "preview_review")
            self.assertEqual(route_profile["authority_tier"], "C")
            self.assertEqual(route_profile["execution_route_status"], "review_only")
            self.assertEqual(catalog_entry["execution_route_driver"], "preview_review")
            self.assertFalse(catalog_entry["default_route_verified"])

    def test_model_bound_evidence_persists_without_self_healing_endpoint_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _profiles, config, router = self._services(root)
            model_id = str(self._tool_ready_model()["id"])
            config.upsert_model(self._tool_ready_model())
            baseline = self._model(config, model_id)
            initial_endpoint = dict(dict(baseline["execution_route"])["endpoint"])

            admitted = config.record_execution_route_evidence(
                model_id,
                self._evidence_for(baseline, state="coding_route_verified"),
            )
            route_profile = router._resolve_profile({"model": model_id})  # noqa: SLF001
            persisted = json.loads((root / "router.json").read_text(encoding="utf-8"))
            stored_model = next(item for item in persisted["models"] if item["id"] == model_id)

            self.assertEqual(admitted["execution_route_status"], "verified_non_default")
            self.assertEqual(admitted["execution_route_driver"], "app_server")
            self.assertEqual(admitted["execution_route_authority_tier"], "A")
            self.assertEqual(route_profile["execution_backend"], "app_server")
            self.assertEqual(set(stored_model["execution_route_evidence"]), {
                "schema_version",
                "state",
                "subject",
                "source_provenance",
                "evidence_refs",
                "validation_scope",
                "verified_at",
                "expires_at",
            })
            self.assertNotIn("expected_subject", json.dumps(stored_model))

            provider = next(item for item in config.providers() if item["id"] == "deepseek")
            config.upsert_provider({**provider, "base_url": "https://example.test/v1"})
            drifted = self._model(config, model_id)
            drifted_route = dict(drifted["execution_route"])
            stored_after_drift = json.loads((root / "router.json").read_text(encoding="utf-8"))
            stored_proof = next(item for item in stored_after_drift["models"] if item["id"] == model_id)["execution_route_evidence"]

            self.assertEqual(drifted["execution_route_status"], "review_only")
            self.assertEqual(drifted["execution_route_driver"], "preview_review")
            self.assertEqual(drifted["execution_route_evidence_state"], "documented")
            self.assertIn("subject_endpoint_fingerprint_mismatch", drifted_route["evidence"]["reasons"])
            self.assertEqual(stored_proof["subject"]["endpoint_fingerprint"], initial_endpoint["fingerprint"])
            self.assertNotEqual(stored_proof["subject"]["endpoint_fingerprint"], drifted_route["endpoint"]["fingerprint"])

    def test_default_route_admission_requires_explicit_route_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _profiles, config, router = self._services(root)
            model_id = str(self._tool_ready_model()["id"])
            config.upsert_model(
                {
                    **self._tool_ready_model(),
                    "last_verified_at": "2026-07-27T00:00:00+00:00",
                    "verified_capability_snapshot": {"status": "verified"},
                    "default_for_provider": True,
                }
            )
            documented = self._model(config, model_id)

            admitted = config.record_execution_route_evidence(
                model_id,
                self._evidence_for(documented, state="default_route_eligible"),
            )
            route_profile = router._resolve_profile({"model": model_id})  # noqa: SLF001
            catalog_entry = next(item for item in router.list_models() if item["id"] == model_id)

            self.assertEqual(documented["execution_route_evidence_state"], "documented")
            self.assertFalse(documented["default_route_verified"])
            self.assertEqual(admitted["execution_route_status"], "default_eligible")
            self.assertTrue(admitted["default_route_verified"])
            self.assertEqual(route_profile["execution_backend"], "app_server")
            self.assertEqual(route_profile["authority_tier"], "A")
            self.assertTrue(catalog_entry["default_route_verified"])
            self.assertTrue(catalog_entry["execution_route_default_eligible"])

    def test_model_upsert_drops_unsafe_route_evidence_before_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _profiles, config, _router = self._services(root)
            model_id = str(self._tool_ready_model()["id"])
            config.upsert_model(
                {
                    **self._tool_ready_model(),
                    "execution_route_evidence": {
                        "schema_version": EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
                        "state": "coding_route_verified",
                        "evidence_refs": ["PRIVATE/provider-compatibility/run.json?api_key=redacted"],
                    },
                }
            )

            persisted = json.loads((root / "router.json").read_text(encoding="utf-8"))
            stored_model = next(item for item in persisted["models"] if item["id"] == model_id)
            refreshed = self._model(config, model_id)

            self.assertNotIn("execution_route_evidence", stored_model)
            self.assertNotIn("api_key", json.dumps(stored_model))
            self.assertEqual(refreshed["execution_route_status"], "review_only")
            self.assertEqual(refreshed["execution_route_evidence_state"], "documented")

    def test_router_blocks_tool_definitions_until_the_route_is_coding_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _profiles, config, router = self._services(root)
            tool = {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read one file.",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            }

            with self.assertRaisesRegex(ValueError, "model-and-endpoint route evidence"):
                router.preview_payload(
                    {
                        "model": "deepseek/deepseek-v4-pro",
                        "input": "Inspect the workspace.",
                        "tools": [tool],
                    }
                )

            model_id = str(self._tool_ready_model()["id"])
            config.upsert_model(self._tool_ready_model())
            documented = self._model(config, model_id)
            config.record_execution_route_evidence(
                model_id,
                self._evidence_for(documented, state="coding_route_verified"),
            )
            preview = router.preview_payload(
                {
                    "model": model_id,
                    "input": "Inspect the workspace.",
                    "tools": [tool],
                }
            )

            self.assertEqual(preview["execution_route_status"], "verified_non_default")
            self.assertIn("tools", preview["upstream_payload"])

    def test_profile_scoped_evidence_is_canonical_and_cannot_promote_another_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(root / "profiles.json")
            profile = profiles.upsert_profile(
                {
                    "profile_id": "fixture-deepseek",
                    "label": "Fixture DeepSeek",
                    "type": "custom_provider",
                    "provider_id": "fixture-deepseek",
                    "base_url": "https://example.test/v1",
                    "model": "fixture-model",
                    "wire_api": "chat",
                    "env_key": "FIXTURE_DEEPSEEK_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                    "authority_tier": "A",
                    "tool_mode": "native",
                    "apply_patch_tool_type": "json",
                    "supports_mcp_tools": True,
                    "mcp_tool_call_policy": "verified",
                    "mcp_smoke_status": "verified",
                    "command_execution_status": "verified",
                }
            )
            model = {
                "id": "fixture-deepseek/fixture-model",
                "provider": "fixture-deepseek",
                "native_model": "fixture-model",
                "authority_tier": "A",
                "tool_mode": "native",
                "apply_patch_tool_type": "json",
                "supports_mcp_tools": True,
                "mcp_tool_call_policy": "verified",
                "mcp_smoke_status": "verified",
                "command_execution_status": "verified",
            }
            baseline = resolve_execution_route(model, provider=profile)
            evidence = {
                "schema_version": EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
                "state": "coding_route_verified",
                "subject": {
                    **dict(baseline["subject"]),
                    "endpoint_fingerprint": dict(baseline["endpoint"])["fingerprint"],
                    "adapter_signature": dict(baseline["adapter"])["signature"],
                },
                "source_provenance": {
                    "kind": "deterministic_fixture",
                    "issuer": "astrabridge-tests",
                    "record_id": "profile-scoped-route-evidence",
                },
                "evidence_refs": ["tests/fixtures/provider_semantic_conformance_v1.json"],
                "validation_scope": ["coding_route", "tools"],
                "verified_at": "2026-07-27T00:00:00+00:00",
                "expires_at": "2030-01-01T00:00:00+00:00",
            }
            persisted = profiles.upsert_profile({**profile, "execution_route_evidence": evidence})
            router = RouterService(profiles, port=0)
            admitted = router._route_bound_profile(persisted, model={}, native_model="fixture-model")  # noqa: SLF001
            mismatch = router._route_bound_profile(persisted, model={}, native_model="different-model")  # noqa: SLF001

            stored_evidence = dict(persisted["execution_route_evidence"])
            self.assertEqual(admitted["execution_route_status"], "verified_non_default")
            self.assertEqual(admitted["execution_backend"], "app_server")
            self.assertEqual(mismatch["execution_route_status"], "review_only")
            self.assertNotIn("expected_subject", stored_evidence)
            self.assertEqual(stored_evidence["subject"]["model_id"], "fixture-deepseek/fixture-model")

            unsafe = profiles.upsert_profile(
                {
                    **persisted,
                    "execution_route_evidence": {
                        **evidence,
                        "evidence_refs": ["tests/fixtures/provider_semantic_conformance_v1.json?api_key=redacted"],
                    },
                }
            )
            self.assertNotIn("execution_route_evidence", unsafe)


if __name__ == "__main__":
    unittest.main()
