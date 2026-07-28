from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.modal_service import ModalService  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.providers.execution_route import (  # noqa: E402
    EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
    resolve_execution_route,
)
from astrabridge_sidecar.providers.runtime_admission import legacy_runtime_route_admission, resolve_runtime_route_admission  # noqa: E402
from astrabridge_sidecar.runtime_service import RuntimeRouteAdmissionError, RuntimeService  # noqa: E402


class _RouterConfigFixture:
    def __init__(self, models: list[dict[str, object]]) -> None:
        self._models = models

    def models(self) -> list[dict[str, object]]:
        return [dict(model) for model in self._models]


def _provider() -> dict[str, object]:
    return {
        "profile_id": "kimi-default",
        "provider_id": "kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "wire_api": "chat",
        "execution_backend": "app_server",
        "model": "kimi-k3",
        "reasoning_effort": "high",
    }


def _model() -> dict[str, object]:
    return {
        "id": "kimi/kimi-k3",
        "provider": "kimi",
        "native_model": "kimi-k3",
        "enabled": True,
        "codex_agent_enabled": True,
        "authority_tier": "A",
        "tool_mode": "guarded_actions",
        "input_modalities": ["text"],
        "supported_reasoning_levels": ["low", "high"],
        "default_reasoning_level": "high",
    }


def _coding_route_evidence(model: dict[str, object], provider: dict[str, object]) -> dict[str, object]:
    route = resolve_execution_route(model, provider=provider)
    subject = dict(route["subject"])
    endpoint = dict(route["endpoint"])
    adapter = dict(route["adapter"])
    return {
        "schema_version": EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
        "state": "coding_route_verified",
        "subject": {
            **subject,
            "endpoint_fingerprint": endpoint["fingerprint"],
            "adapter_signature": adapter["signature"],
        },
        "source_provenance": {
            "kind": "deterministic_runtime_admission_fixture",
            "issuer": "astrabridge-tests",
            "record_id": "runtime-route-admission",
        },
        "evidence_refs": ["tests/test_runtime_route_admission.py"],
        "validation_scope": ["coding_route", "tools", "recovery"],
        "verified_at": "2026-07-27T00:00:00+00:00",
        "expires_at": "2030-01-01T00:00:00+00:00",
    }


class RuntimeRouteAdmissionTests(unittest.TestCase):
    def test_legacy_compatibility_projection_retains_explicit_native_backend_without_claiming_proof(self) -> None:
        provider = _provider()
        provider["execution_backend"] = "native_kernel"

        admission = legacy_runtime_route_admission(provider, requested_model="kimi-k3")

        self.assertEqual(admission["status"], "admitted")
        self.assertEqual(admission["presentation_state"], "legacy_unqualified")
        self.assertEqual(admission["effective"]["execution_backend"], "native_kernel")
        self.assertFalse(admission["route"]["default_route_eligible"])

    def test_documented_route_requires_explicit_review_only_confirmation(self) -> None:
        admission = resolve_runtime_route_admission(
            _provider(),
            model=_model(),
            requested_model="kimi-k3",
            requested_effort="high",
            requested_permission_mode="auto",
            requested_execution_policy="standard",
        )

        self.assertEqual(admission["status"], "confirmation_required")
        self.assertEqual(admission["presentation_state"], "preview_review")
        self.assertEqual(admission["effective"]["execution_driver"], "preview_review")
        self.assertEqual(admission["effective"]["execution_backend"], "app_server")
        self.assertEqual(admission["effective"]["execution_policy"], "no_tools")
        self.assertEqual(admission["effective"]["permission_mode"], "ask")
        self.assertFalse(admission["route"]["default_route_eligible"])
        self.assertIn("tool_semantics_removed", [item["code"] for item in admission["degradation"]["reasons"]])

    def test_confirmed_review_route_stays_reduced_and_never_auto_falls_back(self) -> None:
        admission = resolve_runtime_route_admission(
            _provider(),
            model=_model(),
            requested_model="kimi-k3",
            requested_permission_mode="full",
            requested_execution_policy="standard",
            confirm_degradation=True,
        )

        self.assertEqual(admission["status"], "admitted")
        self.assertEqual(admission["presentation_state"], "preview_review")
        self.assertTrue(admission["degradation"]["confirmed"])
        self.assertEqual(admission["effective"]["execution_policy"], "no_tools")
        self.assertFalse(admission["fallback"]["automatic_fallback"])

    def test_verified_route_preserves_standard_agent_posture_but_is_not_default(self) -> None:
        provider = _provider()
        model = _model()
        model["execution_route_evidence"] = _coding_route_evidence(model, provider)
        admission = resolve_runtime_route_admission(
            provider,
            model=model,
            requested_model="kimi-k3",
            requested_effort="high",
            requested_permission_mode="auto",
            requested_execution_policy="standard",
        )

        self.assertEqual(admission["status"], "admitted")
        self.assertEqual(admission["presentation_state"], "provider_app_server")
        self.assertEqual(admission["route"]["admission"], "verified_non_default")
        self.assertEqual(admission["effective"]["execution_policy"], "standard")
        self.assertEqual(admission["effective"]["permission_mode"], "auto")
        self.assertFalse(admission["route"]["default_route_eligible"])

    def test_disabled_model_and_unsupported_modality_are_blocked(self) -> None:
        model = _model()
        model["enabled"] = False
        admission = resolve_runtime_route_admission(
            _provider(),
            model=model,
            requested_model="kimi-k3",
            attachments=[{"kind": "image", "path": "diagram.png"}],
        )

        self.assertEqual(admission["status"], "blocked")
        codes = [item["code"] for item in admission["degradation"]["reasons"]]
        self.assertIn("model_disabled", codes)
        self.assertIn("requested_modality_not_declared", codes)

    def test_cross_provider_context_and_reasoning_mapping_are_explicit(self) -> None:
        provider = _provider()
        model = _model()
        model["execution_route_evidence"] = _coding_route_evidence(model, provider)
        admission = resolve_runtime_route_admission(
            provider,
            model=model,
            requested_model="kimi-k3",
            requested_effort="max",
            requested_permission_mode="ask",
            requested_execution_policy="no_tools",
            source_provider_id="deepseek",
        )

        self.assertEqual(admission["status"], "confirmation_required")
        self.assertEqual(admission["effective"]["reasoning_effort"], "high")
        codes = [item["code"] for item in admission["degradation"]["reasons"]]
        self.assertIn("cross_provider_continuity_reduced", codes)
        self.assertIn("reasoning_effort_mapped", codes)

    def test_runtime_blocks_before_prepare_and_does_not_promote_review_route_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Admission", root / "admission.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                router_config_service=_RouterConfigFixture([_model()]),
            )
            runtime._prepare_runtime = lambda *_args, **_kwargs: self.fail("runtime preparation must not start before route confirmation")  # type: ignore[method-assign]

            with self.assertRaises(RuntimeRouteAdmissionError) as raised:
                runtime.start_turn(
                    _provider(),
                    thread_id="thread-kimi",
                    text="Inspect the workspace.",
                    attachments=[],
                    model="kimi-k3",
                    effort="high",
                    permission_mode="auto",
                )

            self.assertEqual(raised.exception.admission["status"], "confirmation_required")
            before = dict(projects.current_project or {})
            runtime._update_project_runtime_defaults(  # noqa: SLF001
                _provider(),
                "kimi-k3",
                "high",
                route_admission=raised.exception.admission,
            )
            after = dict(projects.current_project or {})
            self.assertEqual(after.get("default_model"), before.get("default_model"))

    def test_thread_create_and_fork_gate_before_provider_runtime_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Admission", root / "admission.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                router_config_service=_RouterConfigFixture([_model()]),
            )
            runtime._prepare_runtime = lambda *_args, **_kwargs: self.fail("provider runtime setup must not start before route confirmation")  # type: ignore[method-assign]

            with self.assertRaises(RuntimeRouteAdmissionError) as create_raised:
                runtime.create_thread(
                    _provider(),
                    model="kimi-k3",
                    effort="high",
                    permission_mode="auto",
                )
            self.assertEqual(create_raised.exception.admission["status"], "confirmation_required")

            with self.assertRaises(RuntimeRouteAdmissionError) as fork_raised:
                runtime.fork_thread(
                    _provider(),
                    thread_id="thread-kimi",
                    model="kimi-k3",
                    effort="high",
                    permission_mode="auto",
                )
            self.assertEqual(fork_raised.exception.admission["status"], "confirmation_required")

    def test_thread_setup_preflight_does_not_overclaim_a_native_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Admission", root / "admission.abproj", workspace_root=workspace, entry_mode="existing")
            provider = _provider()
            provider["execution_backend"] = "native_kernel"
            model = _model()
            model["execution_route_evidence"] = _coding_route_evidence(model, provider)
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                router_config_service=_RouterConfigFixture([model]),
            )
            runtime._native_kernel_enabled = lambda: True  # type: ignore[method-assign]

            admission = runtime.route_admission(
                provider,
                model="kimi-k3",
                effort="high",
                permission_mode="auto",
                execution_policy="standard",
                operation="thread_create",
            )

            self.assertEqual(admission["status"], "blocked")
            self.assertEqual(admission["presentation_state"], "blocked")
            self.assertIn("thread_setup_driver_not_supported", [item["code"] for item in admission["degradation"]["reasons"]])


if __name__ == "__main__":
    unittest.main()
