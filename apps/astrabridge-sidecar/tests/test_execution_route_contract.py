from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.providers.execution_route import (  # noqa: E402
    EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
    normalize_endpoint_identity,
    resolve_execution_route,
)
from astrabridge_sidecar.providers.registry import get_provider_profile  # noqa: E402


NOW = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)


class ExecutionRouteContractTests(unittest.TestCase):
    def _provider(self, **overrides: object) -> dict[str, object]:
        return {
            "id": "kimi",
            "provider_id": "kimi",
            "base_url": "https://api.moonshot.cn/v1",
            "adapter_type": "chat",
            "runtime_backend": "native_kernel",
            "fallback_models": ["kimi-k2.7-code"],
            **overrides,
        }

    def _model(self, *, model_id: str = "kimi/kimi-k3", **overrides: object) -> dict[str, object]:
        native_model = model_id.split("/", 1)[-1]
        return {
            "id": model_id,
            "provider": "kimi",
            "native_model": native_model,
            "authority_tier": "A",
            "tool_mode": "full",
            "apply_patch_tool_type": "json",
            "supports_mcp_tools": True,
            "mcp_tool_call_policy": "verified",
            "reasoning_policy_mode": "reasoning_content",
            "advertised_context_window": 1_048_576,
            **overrides,
        }

    def _evidence_for(
        self,
        route: dict[str, object],
        *,
        state: str,
        expires_at: str = "2026-08-01T00:00:00+00:00",
        overrides: dict[str, object] | None = None,
    ) -> dict[str, object]:
        subject = dict(route["subject"])
        endpoint = dict(route["endpoint"])
        adapter = dict(route["adapter"])
        payload: dict[str, object] = {
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
                "record_id": "step-3-kimi-k3",
            },
            "evidence_refs": ["PRIVATE/provider-compatibility/runs/kimi-k3/validation.json"],
            "validation_scope": ["coding_route", "tools"],
            "verified_at": "2026-07-26T00:00:00+00:00",
            "expires_at": expires_at,
        }
        payload.update(overrides or {})
        return payload

    def test_documented_route_is_review_only_even_when_model_declares_authority_a(self) -> None:
        route = resolve_execution_route(self._model(), provider=self._provider(), now=NOW)

        self.assertEqual(route["evidence"]["effective_state"], "documented")
        self.assertEqual(route["authority"]["declared_tier"], "A")
        self.assertEqual(route["authority"]["effective_tier"], "C")
        self.assertEqual(route["driver"]["configured_id"], "native_kernel")
        self.assertEqual(route["driver"]["execution_id"], "preview_review")
        self.assertEqual(route["driver"]["admission"], "review_only")
        self.assertFalse(route["default_route_eligible"])

    def test_provider_wide_backend_or_promotion_claim_cannot_promote_every_model(self) -> None:
        provider = self._provider(
            runtime_backend="native_kernel",
            route_promotion_state="default_route_eligible",
            verified_capability_snapshot={"status": "verified"},
        )
        first = resolve_execution_route(
            self._model(model_id="kimi/kimi-k3", last_verified_at="2026-07-26T00:00:00+00:00"),
            provider=provider,
            now=NOW,
        )
        second = resolve_execution_route(
            self._model(model_id="kimi/kimi-k2.7-code", last_verified_at="2026-07-26T00:00:00+00:00"),
            provider=provider,
            now=NOW,
        )

        self.assertNotEqual(first["route_id"], second["route_id"])
        for route in (first, second):
            self.assertEqual(route["evidence"]["effective_state"], "documented")
            self.assertEqual(route["authority"]["effective_tier"], "C")
            self.assertEqual(route["driver"]["execution_id"], "preview_review")
            self.assertFalse(route["default_route_eligible"])

    def test_current_model_bound_coding_evidence_admits_non_default_driver(self) -> None:
        model = self._model()
        provider = self._provider()
        baseline = resolve_execution_route(model, provider=provider, now=NOW)
        evidence = self._evidence_for(baseline, state="coding_route_verified")

        route = resolve_execution_route(model, provider=provider, evidence=evidence, now=NOW)

        self.assertEqual(route["evidence"]["effective_state"], "coding_route_verified")
        self.assertEqual(route["authority"]["effective_tier"], "A")
        self.assertEqual(route["driver"]["execution_id"], "native_kernel")
        self.assertEqual(route["driver"]["admission"], "verified_non_default")
        self.assertFalse(route["default_route_eligible"])

    def test_default_route_needs_model_bound_provenance_references_and_dates(self) -> None:
        model = self._model()
        provider = self._provider()
        baseline = resolve_execution_route(model, provider=provider, now=NOW)
        incomplete = self._evidence_for(
            baseline,
            state="default_route_eligible",
            overrides={
                "source_provenance": {},
                "evidence_refs": [],
                "verified_at": None,
                "expires_at": None,
            },
        )

        blocked = resolve_execution_route(model, provider=provider, evidence=incomplete, now=NOW)
        eligible = resolve_execution_route(
            model,
            provider=provider,
            evidence=self._evidence_for(baseline, state="default_route_eligible"),
            now=NOW,
        )

        self.assertEqual(blocked["evidence"]["effective_state"], "documented")
        self.assertEqual(blocked["driver"]["admission"], "review_only")
        self.assertTrue(blocked["evidence"]["reasons"])
        self.assertTrue(eligible["default_route_eligible"])
        self.assertEqual(eligible["driver"]["admission"], "default_eligible")

    def test_expired_or_endpoint_drifted_evidence_depromotes_route(self) -> None:
        model = self._model()
        provider = self._provider()
        baseline = resolve_execution_route(model, provider=provider, now=NOW)
        expired = resolve_execution_route(
            model,
            provider=provider,
            evidence=self._evidence_for(baseline, state="coding_route_verified", expires_at="2026-07-01T00:00:00+00:00"),
            now=NOW,
        )
        drifted_payload = self._evidence_for(baseline, state="coding_route_verified")
        drifted_subject = dict(drifted_payload["subject"])
        drifted_subject["endpoint_fingerprint"] = "sha256:" + "0" * 64
        drifted_payload["subject"] = drifted_subject
        drifted = resolve_execution_route(model, provider=provider, evidence=drifted_payload, now=NOW)

        self.assertEqual(expired["evidence"]["effective_state"], "documented")
        self.assertEqual(expired["evidence"]["verification_status"], "expired")
        self.assertIn("evidence_expired", expired["evidence"]["reasons"])
        self.assertEqual(drifted["evidence"]["effective_state"], "documented")
        self.assertIn("subject_endpoint_fingerprint_mismatch", drifted["evidence"]["reasons"])

    def test_endpoint_and_evidence_references_cannot_carry_secret_material(self) -> None:
        with self.assertRaises(ValueError):
            normalize_endpoint_identity("https://user:secret@api.moonshot.cn/v1", provider_id="kimi")

        model = self._model()
        provider = self._provider()
        baseline = resolve_execution_route(model, provider=provider, now=NOW)
        unsafe_evidence = self._evidence_for(
            baseline,
            state="coding_route_verified",
            overrides={"evidence_refs": ["PRIVATE/run/validation.json?api_key=redacted"]},
        )
        route = resolve_execution_route(model, provider=provider, evidence=unsafe_evidence, now=NOW)

        self.assertEqual(route["evidence"]["effective_state"], "documented")
        self.assertIn("evidence_references_missing_or_unsafe", route["evidence"]["reasons"])
        self.assertNotIn("api_key", json.dumps(route))

    def test_existing_provider_profiles_resolve_conservatively_without_route_evidence(self) -> None:
        for provider_id in ("qwen", "deepseek", "kimi", "glm"):
            profile = get_provider_profile(provider_id)
            provider = profile.to_router_provider()
            model = {
                "id": f"{provider_id}/{profile.default_model}",
                "provider": provider_id,
                "native_model": profile.default_model,
                **profile.to_model_defaults(),
            }

            route = resolve_execution_route(model, provider=provider, now=NOW)

            self.assertEqual(route["subject"]["provider_id"], provider_id)
            self.assertEqual(route["evidence"]["effective_state"], "documented")
            self.assertEqual(route["driver"]["execution_id"], "preview_review")
            self.assertFalse(route["default_route_eligible"])


if __name__ == "__main__":
    unittest.main()
