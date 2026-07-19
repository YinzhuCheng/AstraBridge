from __future__ import annotations

import hashlib
import hmac
import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.external_a2a_gateway import (  # noqa: E402
    EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION,
    EXTERNAL_A2A_CARD_REF_PREFIX,
    EXTERNAL_A2A_GATEWAY_SCHEMA_VERSION,
    ExternalA2AGatewayClient,
    ExternalA2AGatewayService,
    FakeExternalA2ATaskExecutor,
    RuntimeExternalA2ATaskExecutor,
    a2a_artifact_to_artifact_ref,
    a2a_message_to_agent_envelope,
    a2a_task_to_agent_task,
    agent_envelope_to_a2a_message,
    agent_task_to_a2a_task,
    artifact_ref_to_a2a_artifact,
    build_external_a2a_gateway_snapshot,
    validate_external_a2a_agent_card_registry,
    validate_external_a2a_task_transition,
)
from astrabridge_sidecar.external_a2a_conformance import build_external_a2a_conformance_kit  # noqa: E402
from astrabridge_sidecar.server import AstraBridgeSidecarHttpServer, Handler  # noqa: E402


def _stable_json_digest(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _sample_public_agent_card() -> dict[str, object]:
    return {
        "protocolVersion": "1.0",
        "name": "Geo Route Agent",
        "description": "Finds routes and returns structured travel plans.",
        "url": "https://geo.example.com/a2a",
        "version": "2026.07.17",
        "supportedInterfaces": [
            {
                "url": "https://geo.example.com/a2a",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "extendedAgentCard": True,
        },
        "securitySchemes": {
            "oidc": {
                "openIdConnectSecurityScheme": {
                    "openIdConnectUrl": "https://accounts.example.com/.well-known/openid-configuration"
                }
            }
        },
        "security": [{"oidc": ["openid", "profile"]}],
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": "route-plan",
                "name": "Route Planner",
                "description": "Plans structured travel routes between two points.",
                "tags": ["maps", "travel"],
                "examples": ["Find a route from Tokyo to Osaka."],
            }
        ],
    }


def _sample_registry() -> dict[str, object]:
    public_card = _sample_public_agent_card()
    extended_card = deepcopy(public_card)
    extended_card["description"] = "Extended route-planning card for authenticated clients."
    extended_card["skills"] = [
        *list(extended_card.get("skills") or []),
        {
            "id": "traffic-live",
            "name": "Live Traffic",
            "description": "Returns live traffic status for authenticated clients.",
        },
    ]
    return {
        "schema_version": EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION,
        "generated_at": "2026-07-17T10:00:00+09:00",
        "stale_after_seconds": 2592000,
        "supported_protocol_versions": ["1.0"],
        "cards": [
            {
                "card_ref": f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route",
                "trust_level": "pinned",
                "discovery": {
                    "mode": "well_known",
                    "url": "https://geo.example.com/.well-known/agent-card.json",
                },
                "public_agent_card": public_card,
                "public_agent_card_digest": _stable_json_digest(public_card),
                "authenticated_extended_agent_card": extended_card,
                "authenticated_extended_agent_card_digest": _stable_json_digest(extended_card),
            }
        ],
    }


class ExternalA2AGatewayTests(unittest.TestCase):
    def test_registry_validation_and_gateway_snapshot_resolve_referenced_cards(self) -> None:
        registry = validate_external_a2a_agent_card_registry(
            _sample_registry(),
            referenced_card_refs={f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"},
        )

        self.assertIsNotNone(registry)
        self.assertEqual(registry["schema_version"], EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION)
        snapshot = build_external_a2a_gateway_snapshot(
            registry=registry,
            referenced_card_refs={f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"},
        )
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["schema_version"], EXTERNAL_A2A_GATEWAY_SCHEMA_VERSION)
        self.assertEqual(snapshot["supported_protocol_versions"], ["1.0"])
        self.assertEqual(snapshot["referenced_card_refs"], [f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"])
        self.assertEqual(snapshot["registry_snapshot"][0]["trust_level"], "pinned")
        self.assertTrue(str(dict(snapshot.get("manifest") or {}).get("digest") or "").startswith("sha256:"))
        self.assertEqual(dict(snapshot.get("manifest") or {}).get("verification_state"), "verified")

    def test_registry_rejects_digest_binding_and_missing_ref_drift(self) -> None:
        broken_digest = _sample_registry()
        broken_digest["cards"][0]["public_agent_card_digest"] = "sha256:not-the-real-digest"
        with self.assertRaisesRegex(ValueError, "does not match the normalized Agent Card digest"):
            validate_external_a2a_agent_card_registry(broken_digest)

        broken_binding = _sample_registry()
        broken_binding["cards"][0]["public_agent_card"]["supportedInterfaces"][0]["protocolBinding"] = "GRPC"
        broken_binding["cards"][0]["public_agent_card_digest"] = _stable_json_digest(broken_binding["cards"][0]["public_agent_card"])
        broken_binding["cards"][0]["authenticated_extended_agent_card_digest"] = _stable_json_digest(
            broken_binding["cards"][0]["authenticated_extended_agent_card"]
        )
        with self.assertRaisesRegex(ValueError, "unsupported protocol binding"):
            validate_external_a2a_agent_card_registry(broken_binding)

        with self.assertRaisesRegex(ValueError, "unresolved external A2A card refs"):
            validate_external_a2a_agent_card_registry(
                _sample_registry(),
                referenced_card_refs={f"{EXTERNAL_A2A_CARD_REF_PREFIX}missing"},
            )

    def test_gateway_snapshot_fails_closed_for_expired_registry_manifest(self) -> None:
        registry = _sample_registry()
        registry["generated_at"] = "2025-01-01T00:00:00+00:00"
        registry["stale_after_seconds"] = 60
        validated = validate_external_a2a_agent_card_registry(
            registry,
            referenced_card_refs={f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"},
        )
        with self.assertRaisesRegex(ValueError, "registry manifest is expired"):
            build_external_a2a_gateway_snapshot(
                registry=validated,
                referenced_card_refs={f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"},
            )

    def test_adapter_rejects_unsafe_or_oversized_artifacts_and_ambiguous_task_transitions(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe URI scheme"):
            a2a_artifact_to_artifact_ref(
                {
                    "artifactId": "artifact-unsafe",
                    "mimeType": "application/pdf",
                    "uri": "file:///C:/secret.txt",
                },
                task_id="task-a2a",
                run_id="run-a2a",
                source_node_id="node-external",
            )

        with self.assertRaisesRegex(ValueError, "size limit"):
            a2a_artifact_to_artifact_ref(
                {
                    "artifactId": "artifact-big",
                    "mimeType": "application/pdf",
                    "uri": "https://geo.example.com/files/report.pdf",
                    "sizeBytes": 1024 * 1024 * 128,
                },
                task_id="task-a2a",
                run_id="run-a2a",
                source_node_id="node-external",
            )

        self.assertEqual(
            validate_external_a2a_task_transition("TASK_STATE_SUBMITTED", "TASK_STATE_WORKING"),
            "TASK_STATE_WORKING",
        )
        with self.assertRaisesRegex(ValueError, "Ambiguous external A2A task transition"):
            validate_external_a2a_task_transition("TASK_STATE_COMPLETED", "TASK_STATE_WORKING")

    def test_message_task_and_artifact_adapters_round_trip_through_internal_protocol_shapes(self) -> None:
        envelope = a2a_message_to_agent_envelope(
            {
                "messageId": "msg-123",
                "role": "agent",
                "parts": [
                    {
                        "partId": "part-text",
                        "kind": "text",
                        "mimeType": "text/plain",
                        "text": "Route planning is complete.",
                    },
                    {
                        "partId": "part-json",
                        "kind": "json",
                        "mimeType": "application/json",
                        "data": {"origin": "Tokyo", "destination": "Osaka"},
                    },
                    {
                        "partId": "part-artifact",
                        "kind": "document",
                        "mimeType": "application/pdf",
                        "artifact": {
                            "artifactId": "route-pdf",
                            "mimeType": "application/pdf",
                            "uri": "https://geo.example.com/files/route.pdf",
                            "sizeBytes": 4096,
                        },
                    },
                ],
            },
            task_id="task-a2a",
            run_id="run-a2a",
            sender={"agent_id": "remote-geo-agent", "provider_id": "external-a2a"},
            recipient={"agent_id": "astrabridge-gateway", "provider_id": "astrabridge"},
        )
        self.assertEqual(envelope["kind"], "handoff")
        round_trip_message = agent_envelope_to_a2a_message(envelope)
        self.assertEqual(round_trip_message["messageId"], "msg-123")
        self.assertEqual(len(round_trip_message["parts"]), 3)

        artifact_ref = dict(envelope["content"][2]["artifact"])
        external_artifact = artifact_ref_to_a2a_artifact(artifact_ref)
        self.assertEqual(external_artifact["artifactId"], "route-pdf")
        self.assertEqual(external_artifact["uri"], "https://geo.example.com/files/route.pdf")

        agent_task = a2a_task_to_agent_task(
            {
                "id": "task-remote-123",
                "state": "TASK_STATE_WORKING",
                "input": [
                    {
                        "partId": "task-input",
                        "kind": "text",
                        "mimeType": "text/plain",
                        "text": "Find the fastest route.",
                    }
                ],
            },
            graph_id="graph-a2a",
            node_id="node-a2a-gateway",
            run_id="run-a2a",
        )
        self.assertEqual(agent_task["kind"], "external_a2a_task")
        external_task = agent_task_to_a2a_task(agent_task, state="TASK_STATE_INPUT_REQUIRED")
        self.assertEqual(external_task["id"], "task-remote-123")
        self.assertEqual(external_task["state"], "TASK_STATE_INPUT_REQUIRED")

    def test_gateway_http_routes_support_discovery_duplicate_send_stream_reconnect_and_artifacts(self) -> None:
        service = ExternalA2AGatewayService(executor=FakeExternalA2ATaskExecutor(default_delay_sec=0.3))
        with _running_gateway_server(service) as base_url:
            client = ExternalA2AGatewayClient(base_url)
            card = client.fetch_agent_card()
            self.assertEqual(card["protocolVersion"], "1.0")
            self.assertEqual(card["supportedInterfaces"][0]["url"], f"{base_url}/a2a")

            task_payload = {
                "id": "task-http-1",
                "input": [
                    {
                        "partId": "prompt",
                        "kind": "text",
                        "mimeType": "text/plain",
                        "text": "Plan a route from Tokyo to Osaka.",
                    }
                ],
            }
            metadata = {
                "external_a2a": {
                    "test_behavior": {
                        "delay_sec": 0.3,
                        "response_text": "Route ready.",
                        "artifact_uri": "https://geo.example.com/files/route.pdf",
                        "artifact_mime_type": "application/pdf",
                    }
                }
            }
            first = client.send_task(task_payload, idempotency_key="idem-http-1", metadata=metadata)
            duplicate = client.send_task(task_payload, idempotency_key="idem-http-1", metadata=metadata)
            self.assertFalse(first["duplicate"])
            self.assertTrue(duplicate["duplicate"])
            self.assertEqual(first["task"]["id"], duplicate["task"]["id"])

            first_batch = client.stream_task_events("task-http-1", after=0, seconds=0.2)
            self.assertTrue(
                any(
                    event["type"] in {"task_submitted", "task_started", "task_execution_bound"}
                    for event in first_batch
                )
            )
            first_cursor = int(first_batch[0].get("cursor") or 0)
            second_batch = client.stream_task_events("task-http-1", after=first_cursor, seconds=1.0)
            self.assertTrue(any(event["type"] == "task_completed" for event in second_batch))

            terminal = _wait_for_task_state(client, "task-http-1", {"TASK_STATE_COMPLETED"})
            self.assertEqual(terminal["task"]["state"], "TASK_STATE_COMPLETED")
            self.assertEqual(terminal["task"]["artifacts"][0]["uri"], "https://geo.example.com/files/route.pdf")
            self.assertNotIn("file://", json.dumps(terminal, ensure_ascii=False))

            with self.assertRaises(urllib.error.HTTPError) as captured:
                client.send_task(
                    {
                        "id": "task-http-1",
                        "input": [
                            {
                                "partId": "prompt-changed",
                                "kind": "text",
                                "mimeType": "text/plain",
                                "text": "This payload is intentionally different.",
                            }
                        ],
                    },
                    idempotency_key="idem-http-1",
                    metadata=metadata,
                )
            self.assertEqual(captured.exception.code, 409)

    def test_gateway_http_route_preserves_remote_failure_without_secret_leakage(self) -> None:
        service = ExternalA2AGatewayService(executor=FakeExternalA2ATaskExecutor(default_delay_sec=0.05))
        with _running_gateway_server(service) as base_url:
            client = ExternalA2AGatewayClient(base_url)
            failed = client.send_task(
                {
                    "id": "task-http-fail",
                    "input": [
                        {
                            "partId": "prompt",
                            "kind": "text",
                            "mimeType": "text/plain",
                            "text": "Trigger a controlled remote failure.",
                        }
                    ],
                },
                idempotency_key="idem-http-fail",
                metadata={
                    "external_a2a": {
                        "test_behavior": {
                            "fail": True,
                            "error": "Remote failure simulated for July 17, 2026.",
                        },
                        "authorization": "Bearer unit_secret_should_not_survive",
                        "raw_reasoning": "private thoughts",
                    }
                },
            )
            self.assertEqual(failed["task"]["id"], "task-http-fail")
            terminal = _wait_for_task_state(client, "task-http-fail", {"TASK_STATE_FAILED"})
            encoded = json.dumps(terminal, ensure_ascii=False)
            self.assertIn("Remote failure simulated for July 17, 2026.", encoded)
            self.assertNotIn("unit_secret_should_not_survive", encoded)
            self.assertNotIn("private thoughts", encoded)

    def test_runtime_executor_cancellation_reaches_runtime_interrupt_lane_through_http_gateway(self) -> None:
        class FakeRuntime:
            def __init__(self) -> None:
                self.started: list[dict[str, object]] = []
                self.interrupted: list[tuple[str, str, str]] = []

            def start_turn(self, profile, **payload):  # noqa: ANN001
                self.started.append({"profile": deepcopy(profile), **deepcopy(payload)})
                return {
                    "thread": {"id": str(payload.get("thread_id") or "thread-runtime")},
                    "turn": {"id": "turn-runtime-1"},
                }

            def interrupt_turn(self, profile, thread_id, turn_id):  # noqa: ANN001
                self.interrupted.append((str(profile.get("profile_id") or ""), str(thread_id), str(turn_id)))
                return {"interrupt": {"ok": True, "thread_id": thread_id, "turn_id": turn_id}}

            def record_external_event(self, event_type, payload):  # noqa: ANN001
                return None

        fake_runtime = FakeRuntime()
        service = ExternalA2AGatewayService(
            executor=RuntimeExternalA2ATaskExecutor(
                runtime=fake_runtime,
                profile_resolver=lambda profile_id: {
                    "profile_id": str(profile_id or "deepseek-default"),
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                },
                thread_id_resolver=lambda _task_record: "thread-runtime-1",
            )
        )
        with _running_gateway_server(service) as base_url:
            client = ExternalA2AGatewayClient(base_url)
            client.send_task(
                {
                    "id": "task-runtime-cancel",
                    "input": [
                        {
                            "partId": "prompt",
                            "kind": "text",
                            "mimeType": "text/plain",
                            "text": "Start a runtime-backed external A2A turn.",
                        }
                    ],
                },
                idempotency_key="idem-runtime-cancel",
                metadata={
                    "external_a2a": {
                        "profile_id": "deepseek-default",
                        "thread_id": "thread-runtime-1",
                        "permission_mode": "auto",
                    }
                },
            )
            working = _wait_for_task_state(client, "task-runtime-cancel", {"TASK_STATE_WORKING"})
            self.assertEqual(working["task"]["execution"]["turn_id"], "turn-runtime-1")

            cancelled = client.cancel_task("task-runtime-cancel")
            self.assertEqual(cancelled["task"]["state"], "TASK_STATE_CANCELED")
            self.assertEqual(fake_runtime.started[0]["thread_id"], "thread-runtime-1")
            self.assertEqual(fake_runtime.interrupted[0], ("deepseek-default", "thread-runtime-1", "turn-runtime-1"))

    def test_strict_gateway_negotiates_supported_version_and_preserves_signed_trust_decision(self) -> None:
        now = datetime.now(timezone.utc)
        public_card = _sample_public_agent_card()
        card_digest = _stable_json_digest(public_card)
        signature = hmac.new(b"unit-signing-secret", card_digest.encode("utf-8"), hashlib.sha256).hexdigest()
        service = ExternalA2AGatewayService(
            executor=FakeExternalA2ATaskExecutor(default_delay_sec=0.05),
            trusted_peer_policies={
                "trusted-geo": {
                    "trust_level": "pinned",
                    "audiences": ["astrabridge-gateway"],
                    "workspace_ids": ["workspace-demo"],
                    "required_security_schemes": ["mutualTlsSecurityScheme"],
                    "require_signed_agent_card": True,
                    "signing_key_ids": ["peer-card-key-1"],
                    "pinned_agent_card_digest": card_digest,
                }
            },
            signature_keys={"peer-card-key-1": "unit-signing-secret"},
            require_trusted_peers=True,
            local_workspace_id="workspace-demo",
        )
        result = service.submit_task(
            {
                "task": {
                    "id": "task-negotiated",
                    "input": [
                        {
                            "partId": "prompt",
                            "kind": "text",
                            "mimeType": "text/plain",
                            "text": "Negotiate down to the supported A2A version.",
                        }
                    ],
                },
                "idempotencyKey": "idem-negotiated",
                "metadata": {
                    "external_a2a": {
                        "issuer": "trusted-geo",
                        "audience": "astrabridge-gateway",
                        "workspace_id": "workspace-demo",
                        "trust_level": "pinned",
                        "protocol_version": "9.0",
                        "supported_protocol_versions": ["9.0", "1.0"],
                        "allow_downgrade": True,
                        "protocol_binding": "WEBSOCKET",
                        "supported_protocol_bindings": ["WEBSOCKET", "JSONRPC"],
                        "required_extensions": ["task-send", "task-stream"],
                        "optional_extensions": ["artifact-transfer", "future-extension"],
                        "security_schemes": ["mutualTlsSecurityScheme"],
                        "request_id": "req-negotiated",
                        "sent_at": now.isoformat(),
                        "expires_at": (now + timedelta(minutes=5)).isoformat(),
                        "peer_agent_card": public_card,
                        "peer_agent_card_digest": card_digest,
                        "peer_agent_card_signature": {
                            "algorithm": "hmac-sha256",
                            "key_id": "peer-card-key-1",
                            "signature": signature,
                        },
                    }
                },
            }
        )
        external_meta = dict(dict(result["task"].get("metadata") or {}).get("external_a2a") or {})
        negotiation = dict(external_meta.get("negotiation") or {})
        trust_decision = dict(external_meta.get("trust_decision") or {})
        self.assertEqual(negotiation["selected_protocol_version"], "1.0")
        self.assertEqual(negotiation["downgraded_from_protocol_version"], "9.0")
        self.assertEqual(negotiation["selected_protocol_binding"], "JSONRPC")
        self.assertIn("future-extension", negotiation["rejected_optional_extensions"])
        self.assertTrue(trust_decision["signed_agent_card_verified"])
        self.assertEqual(trust_decision["issuer"], "trusted-geo")
        self.assertEqual(trust_decision["decision"], "trusted")
        self.assertEqual(trust_decision["peer_agent_card_digest"], card_digest)
        self.assertTrue(str(trust_decision["gateway_policy_digest"]).startswith("sha256:"))

    def test_conformance_kit_negative_security_cases_reject_with_expected_http_status_and_code(self) -> None:
        service = _strict_gateway_service()
        kit = build_external_a2a_conformance_kit()
        with _running_gateway_server(service) as base_url:
            client = ExternalA2AGatewayClient(base_url)
            for case in list(kit["negative_cases"]):
                with self.assertRaises(urllib.error.HTTPError) as captured:
                    client.send_task(
                        dict(case["task"]),
                        idempotency_key=f"idem-{case['case_id']}",
                        metadata=dict(case["metadata"]),
                    )
                self.assertEqual(captured.exception.code, int(case["expected_http_status"]))
                error_payload = json.loads(captured.exception.read().decode("utf-8"))
                self.assertEqual(error_payload["code"], case["expected_code"])

    def test_gateway_rejects_replayed_request_from_conformance_kit(self) -> None:
        service = _strict_gateway_service()
        kit = build_external_a2a_conformance_kit()
        with _running_gateway_server(service) as base_url:
            client = ExternalA2AGatewayClient(base_url)
            replay_case = dict(kit["replay_case"])
            initial = dict(replay_case["initial"])
            client.send_task(
                dict(initial["task"]),
                idempotency_key="idem-replay-initial",
                metadata=dict(initial["metadata"]),
            )
            replayed = dict(replay_case["replayed"])
            with self.assertRaises(urllib.error.HTTPError) as captured:
                client.send_task(
                    dict(replayed["task"]),
                    idempotency_key="idem-replay-second",
                    metadata=dict(replayed["metadata"]),
                )
            self.assertEqual(captured.exception.code, int(replayed["expected_http_status"]))
            error_payload = json.loads(captured.exception.read().decode("utf-8"))
            self.assertEqual(error_payload["code"], replayed["expected_code"])


class _GatewayServerContext:
    def __init__(self, service: ExternalA2AGatewayService) -> None:
        self.seed_root = Path(tempfile.gettempdir())
        self.external_a2a = service
        self.runtime = SimpleNamespace(
            list_events=lambda after=0, limit=None: {"cursor": after, "events": []},
            record_supervisor_event=lambda event: None,
            record_external_event=lambda event_type, payload: None,
            health_environment=lambda: {"running": False, "runtime_config": {}},
            environment=lambda: {"running": False, "runtime_config": {}},
        )
        self.router = SimpleNamespace(
            health_status=lambda: {"listen_port": 8787, "base_url": "http://127.0.0.1:8787/v1"},
            status=lambda: {"listen_port": 8787, "base_url": "http://127.0.0.1:8787/v1"},
        )


class _running_gateway_server:
    def __init__(self, service: ExternalA2AGatewayService) -> None:
        self._service = service
        self._server: AstraBridgeSidecarHttpServer | None = None
        self._thread: threading.Thread | None = None
        self._old_context = getattr(Handler, "context", None)

    def __enter__(self) -> str:
        self._server = AstraBridgeSidecarHttpServer(("127.0.0.1", 0), Handler)
        Handler.context = _GatewayServerContext(self._service)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self._old_context is None:
            try:
                delattr(Handler, "context")
            except AttributeError:
                pass
        else:
            Handler.context = self._old_context


def _strict_gateway_service() -> ExternalA2AGatewayService:
    return ExternalA2AGatewayService(
        executor=FakeExternalA2ATaskExecutor(default_delay_sec=0.05),
        trusted_peer_policies={
            "trusted-geo": {
                "trust_level": "pinned",
                "audiences": ["astrabridge-gateway"],
                "workspace_ids": ["workspace-demo"],
                "required_security_schemes": ["mutualTlsSecurityScheme"],
            }
        },
        require_trusted_peers=True,
        local_workspace_id="workspace-demo",
    )


def _wait_for_task_state(
    client: ExternalA2AGatewayClient,
    task_id: str,
    expected_states: set[str],
    *,
    timeout_sec: float = 5.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        payload = client.get_task(task_id)
        task = dict(payload.get("task") or {})
        if str(task.get("state") or "") in expected_states:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {task_id} to reach one of {sorted(expected_states)}.")


if __name__ == "__main__":
    unittest.main()
