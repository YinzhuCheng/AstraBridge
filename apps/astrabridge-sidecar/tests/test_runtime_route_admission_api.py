from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.server import Handler  # noqa: E402
from astrabridge_sidecar.runtime_service import RuntimeRouteAdmissionError  # noqa: E402


class RuntimeRouteAdmissionApiTests(unittest.TestCase):
    def test_handler_preflight_uses_metadata_profile_and_never_starts_runtime(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}

        class Runtime:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def route_admission(self, profile: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
                self.calls.append({"profile": profile, **kwargs})
                return {
                    "schema_version": "astrabridge-runtime-route-admission-v1",
                    "status": "confirmation_required",
                    "presentation_state": "preview_review",
                    "route": {"admission": "review_only", "default_route_eligible": False},
                    "effective": {"execution_policy": "no_tools", "permission_mode": "ask"},
                    "degradation": {"requires_confirmation": True, "reasons": []},
                    "fallback": {"automatic_fallback": False, "target_models": []},
                }

        class Context:
            runtime = Runtime()

            @staticmethod
            def resolve_runtime_profile_metadata(profile_id: str | None) -> dict[str, Any]:
                return {"profile_id": profile_id or "project-default", "provider_id": "kimi", "model": "kimi-k3"}

            def resolve_runtime_profile(self, _profile_id: str | None) -> dict[str, Any]:
                raise AssertionError("Route admission must not resolve a secret-owning runtime profile.")

        handler.context = Context()  # type: ignore[assignment]
        handler.path = "/api/runtime/route-admission"  # type: ignore[assignment]
        handler.command = "POST"  # type: ignore[assignment]
        handler._require_admin_token = lambda: None  # type: ignore[assignment]
        handler.read_json_body = lambda: {  # type: ignore[assignment]
            "profile_id": "kimi-default",
            "model": "kimi-k3",
            "effort": "high",
            "permission_mode": "auto",
            "execution_policy": "standard",
            "context_mode": "full",
            "attachments": [{"kind": "image", "path": "diagram.png"}],
            "operation": "thread_create",
        }
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 200, captured)
        self.assertEqual(captured["payload"]["status"], "confirmation_required")
        self.assertEqual(len(handler.context.runtime.calls), 1)  # type: ignore[attr-defined]
        call = handler.context.runtime.calls[0]  # type: ignore[attr-defined]
        self.assertEqual(call["profile"]["profile_id"], "kimi-default")
        self.assertEqual(call["model"], "kimi-k3")
        self.assertEqual(call["attachments"], [{"kind": "image", "path": "diagram.png"}])
        self.assertFalse(call["confirm_degradation"])
        self.assertEqual(call["operation"], "thread_create")

    def test_handler_returns_confirmation_payload_when_thread_start_is_not_admitted(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}
        admission = {
            "schema_version": "astrabridge-runtime-route-admission-v1",
            "status": "confirmation_required",
            "presentation_state": "preview_review",
            "route": {"admission": "review_only", "default_route_eligible": False},
            "effective": {"execution_policy": "no_tools", "permission_mode": "ask"},
            "degradation": {"requires_confirmation": True, "reasons": []},
            "fallback": {"automatic_fallback": False, "target_models": []},
        }

        class Runtime:
            def create_thread(self, _profile: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
                raise RuntimeRouteAdmissionError(admission, operation="thread_create")

        class Context:
            runtime = Runtime()

        handler.context = Context()  # type: ignore[assignment]
        handler.path = "/api/runtime/threads/create"  # type: ignore[assignment]
        handler.command = "POST"  # type: ignore[assignment]
        handler._require_admin_token = lambda: None  # type: ignore[assignment]
        handler._profile = lambda _profile_id: {"profile_id": "kimi-default"}  # type: ignore[assignment]
        handler.read_json_body = lambda: {  # type: ignore[assignment]
            "profile_id": "kimi-default",
            "model": "kimi-k3",
            "permission_mode": "auto",
        }
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 409)
        self.assertEqual(captured["payload"]["route_admission"]["status"], "confirmation_required")
        self.assertIn("confirmation is required", captured["payload"]["error"])


if __name__ == "__main__":
    unittest.main()
