from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.mcp_broker_service import McpBrokerService  # noqa: E402
from astrabridge_sidecar.mcp_config_service import McpConfigService  # noqa: E402
from astrabridge_sidecar.mcp_node_policy import McpToolPolicyDenied, resolve_node_mcp_tool_policy  # noqa: E402
from astrabridge_sidecar.mcp_server_core import McpHttpResponse, McpServerCore, StreamableHttpMcpServer  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.server import Handler  # noqa: E402
from astrabridge_sidecar.web_tool_service import AstraBridgeWebService  # noqa: E402
from astrabridge_sidecar.durable_run_store import DurableRunEventStore  # noqa: E402


def _jwt_token(*, aud: str, scope: str) -> str:
    def _segment(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        encoded = __import__("base64").urlsafe_b64encode(raw).decode("ascii")
        return encoded.rstrip("=")

    return ".".join(
        (
            _segment({"alg": "none", "typ": "JWT"}),
            _segment({"aud": aud, "scope": scope}),
            "sig",
        )
    )


class _RemoteMcpTransportFixture:
    def __init__(
        self,
        *,
        token: str,
        required_scope: str = "mcp:basic",
        scopes_supported: list[str] | None = None,
        long_running: bool = False,
        leaking_artifact: bool = False,
    ) -> None:
        self.token = token
        self.required_scope = required_scope
        self.scopes_supported = list(scopes_supported or [required_scope])
        self.long_running = long_running
        self.leaking_artifact = leaking_artifact
        self.mcp_url = "https://remote.example/mcp"
        self.metadata_url = "https://remote.example/.well-known/oauth-protected-resource/mcp"
        self.auth_metadata_url = "https://auth.example.com/.well-known/oauth-authorization-server"
        self.tool_call_count = 0
        self.authorized_request_count = 0
        self.unauthorized_request_count = 0
        self._http_server = StreamableHttpMcpServer(self._core())

    def _core(self) -> McpServerCore:
        def _tools() -> list[dict[str, Any]]:
            return [
                {
                    "name": "remote_echo",
                    "description": "Remote MCP broker fixture.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                        "additionalProperties": False,
                    },
                }
            ]

        def _handler(name: str, arguments: dict[str, Any], context) -> dict[str, Any]:
            self.tool_call_count += 1
            if name != "remote_echo":
                raise ValueError(name)
            context.emit_progress(1, total=1, message="remote-progress")
            if self.long_running:
                context.emit_notification("notifications/progress", {"progressToken": "durable", "progress": 1, "message": "accepted"})
                return {}
            artifact_uri = "workspace://.astrabridge/assets/generated/remote.png"
            if self.leaking_artifact:
                artifact_uri = "C:\\sensitive\\remote.png"
            structured = {
                "typed_result": {
                    "schema_version": "astrabridge-mcp-tool-result-v1",
                    "request_id": "remote-request-1",
                    "tool": "remote_echo",
                    "result_kind": "capability",
                    "status": "ok",
                    "artifact_refs": [
                        {
                            "artifact_id": "artifact-1",
                            "artifact_uri": artifact_uri,
                            "media_type": "image/png",
                            "status": "ready",
                            "size_bytes": 12,
                            "digest_sha256": "a" * 64,
                            "lineage": {"task_id": "task.remote", "run_id": "run.remote", "source_node_id": "tool.remote_echo"},
                            "metadata": {"relative_path": ".astrabridge/assets/generated/remote.png", "artifact_kind": "image"},
                        }
                    ],
                    "diagnostic_refs": [],
                    "content_parts": [
                        {
                            "part_id": "remote_echo.artifact.1",
                            "kind": "image",
                            "mime_type": "image/png",
                            "artifact": {
                                "artifact_id": "artifact-1",
                                "artifact_uri": artifact_uri,
                                "media_type": "image/png",
                                "status": "ready",
                                "size_bytes": 12,
                                "digest_sha256": "a" * 64,
                                "lineage": {"task_id": "task.remote", "run_id": "run.remote", "source_node_id": "tool.remote_echo"},
                                "metadata": {"relative_path": ".astrabridge/assets/generated/remote.png", "artifact_kind": "image"},
                            },
                            "metadata": {"artifact_uri": artifact_uri},
                        }
                    ],
                    "summary": {"message": str(arguments.get("message") or "")},
                },
                "content_parts": [
                    {
                        "part_id": "remote_echo.text",
                        "kind": "text",
                        "mime_type": "text/plain",
                        "text": str(arguments.get("message") or ""),
                    }
                ],
                "protocol_artifact_refs": [
                    {
                        "artifact_id": "artifact-1",
                        "artifact_uri": artifact_uri,
                        "media_type": "image/png",
                        "status": "ready",
                        "size_bytes": 12,
                        "digest_sha256": "a" * 64,
                        "lineage": {"task_id": "task.remote", "run_id": "run.remote", "source_node_id": "tool.remote_echo"},
                        "metadata": {"relative_path": ".astrabridge/assets/generated/remote.png", "artifact_kind": "image"},
                    }
                ],
                "diagnostic_refs": [],
            }
            return {
                "content": [{"type": "text", "text": f"remote:{arguments.get('message') or ''}"}],
                "structuredContent": structured,
            }

        return McpServerCore(
            server_name="remote-fixture",
            server_version="0.1.0",
            instructions="Remote streamable HTTP fixture.",
            tools_provider=_tools,
            tool_handler=_handler,
        )

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None,
        body: bytes | str | dict[str, Any] | None,
    ) -> McpHttpResponse:
        normalized_headers = {str(key).lower(): str(value) for key, value in dict(headers or {}).items()}
        if url == self.metadata_url and method == "GET":
            return McpHttpResponse(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "resource": self.mcp_url,
                        "authorization_servers": ["https://auth.example.com"],
                        "scopes_supported": list(self.scopes_supported),
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
            )
        if url == self.auth_metadata_url and method == "GET":
            return McpHttpResponse(
                status_code=200,
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "issuer": "https://auth.example.com",
                        "token_endpoint": "https://auth.example.com/token",
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
            )
        if url == self.mcp_url and normalized_headers.get("authorization") != f"Bearer {self.token}":
            self.unauthorized_request_count += 1
            return McpHttpResponse(
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{self.metadata_url}", scope="{self.required_scope}"'},
            )
        if url == self.mcp_url:
            self.authorized_request_count += 1
            if isinstance(body, dict):
                payload = dict(body)
            elif isinstance(body, bytes):
                payload = json.loads(body.decode("utf-8"))
            elif isinstance(body, str):
                payload = json.loads(body)
            else:
                payload = {}
            if self.long_running and method == "POST" and str(payload.get("method") or "") == "tools/call":
                self.tool_call_count += 1
                return McpHttpResponse(
                    status_code=202,
                    headers={
                        "Cache-Control": "no-store",
                        "Mcp-Session-Id": str(normalized_headers.get("mcp-session-id") or "remote-session"),
                        "MCP-Protocol-Version": str(normalized_headers.get("mcp-protocol-version") or "2025-11-25"),
                        "X-AstraBridge-Task-Handle": "remote-handle-1",
                    },
                )
            return self._http_server.handle_request(method, headers=headers, body=body)
        return McpHttpResponse(status_code=404)


class McpBrokerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._runtime_root_tempdir = tempfile.TemporaryDirectory()
        previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
        os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = self._runtime_root_tempdir.name

        def _restore_runtime_root() -> None:
            if previous_runtime_root is None:
                os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
            else:
                os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root
            self._runtime_root_tempdir.cleanup()

        self.addCleanup(_restore_runtime_root)

    def test_capability_broker_includes_mcp_metadata_and_workspace_root(self) -> None:
        class FakeCapabilityRuntime:
            def route_snapshot(self, capability_id: str | None = None) -> dict[str, Any]:
                return {"requested_capability_id": capability_id, "routes": [{"capability_id": "vision.analyze"}]}

            def invoke(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
                return {
                    "capability_id": capability_id,
                    "tool_event_verified": True,
                    "echo": dict(payload),
                }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            broker = McpBrokerService(project_service=projects, capability_runtime=FakeCapabilityRuntime())

            response = broker.invoke_capability(
                "vision.analyze",
                {"prompt": "describe the image"},
                caller="unit_test",
                operation_id="mcp-op-unit-capability",
            )

        result = dict(response["result"])
        mcp = dict(response["mcp"])
        self.assertEqual(result["capability_id"], "vision.analyze")
        self.assertEqual(result["echo"]["workspace_root"], str(workspace))
        self.assertTrue(result["tool_event_verified"])
        self.assertEqual(mcp["server"], "astrabridge_capabilities")
        self.assertEqual(mcp["tool"], "astrabridge_capability_vision_analyze")
        self.assertEqual(mcp["operation_id"], "mcp-op-unit-capability")
        self.assertEqual(mcp["policy_decision"]["decision"], "allow")
        self.assertEqual(mcp["audit_event"]["type"], "mcp_broker_tool_call")
        self.assertTrue(str(mcp["request_id"]).startswith("mcp-request-"))
        self.assertEqual(mcp["protocol_version"], "2025-11-25")

    def test_yunwu_broker_uses_internal_meta_without_leaking_secret(self) -> None:
        captured_calls: list[dict[str, Any]] = []

        class FakeYunwuImageService:
            def generate(self, **kwargs: Any) -> dict[str, Any]:
                captured_calls.append(dict(kwargs))
                workspace_root = Path(str(kwargs["workspace_root"]))
                return {
                    "created": 123,
                    "requested_n": kwargs.get("n"),
                    "actual_n": 1,
                    "count_mismatch": False,
                    "asset_manifest_path": str(workspace_root / ".astrabridge" / "assets" / "generated" / "asset_manifest.json"),
                    "data": [
                        {
                            "asset_id": "yunwu-test",
                            "local_path": str(workspace_root / ".astrabridge" / "assets" / "generated" / "yunwu-test.png"),
                            "b64_json_present": True,
                            "has_alpha": True,
                            "transparent_pixel_ratio": 0.5,
                            "transparency_status": "passed",
                        }
                    ],
                }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            broker = McpBrokerService(project_service=projects, yunwu_image_service=FakeYunwuImageService())

            response = broker.invoke_tool(
                "yunwu_image",
                "yunwu_image_generate",
                {"prompt": "single transparent key", "n": 1, "timeout_sec": 222},
                caller="unit_test",
                internal_meta={"internal_api_key": "secret-token-value"},
            )

        self.assertEqual(len(captured_calls), 1)
        call = captured_calls[0]
        self.assertEqual(call["api_key"], "secret-token-value")
        self.assertEqual(call["workspace_root"], str(workspace))
        self.assertEqual(call["timeout_sec"], 222)
        self.assertEqual(response["result"]["data"][0]["b64_json_present"], True)
        rendered = json.dumps(response, ensure_ascii=False)
        self.assertNotIn("secret-token-value", rendered)
        self.assertIn("b64_json_present", rendered)

    def test_web_lane_service_remains_standalone_while_persisting_mcp_metadata(self) -> None:
        class FakeBroker:
            def invoke_tool(self, server: str, tool: str, arguments: dict[str, Any], **_: Any) -> dict[str, Any]:
                return {
                    "result": {
                        "tool": tool,
                        "merged_results": [{"url": "https://example.com/spec", "title": "Spec"}],
                        "tool_event_verified": True,
                    },
                    "mcp": {
                        "server": server,
                        "tool": tool,
                        "request_id": "mcp-request-web-lane-1",
                        "operation_id": "mcp-op-web-lane-1",
                    },
                }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            service = AstraBridgeWebService(projects)
            service.set_mcp_broker(FakeBroker())

            response = service.search_batch({"queries": [{"query": "AstraBridge MCP broker", "max_results": 3}]})
            self.assertTrue(Path(str(response["path"])).exists())

        self.assertEqual(response["result"]["tool"], "astrabridge_web_search_batch")
        self.assertEqual(response["mcp"]["request_id"], "mcp-request-web-lane-1")
        self.assertEqual(response["usage_signal"]["source"], "web_lane")

    def test_handler_yunwu_generate_route_uses_broker_and_internal_meta(self) -> None:
        calls: list[dict[str, Any]] = []

        class FakeBroker:
            def invoke_tool(self, server: str, tool: str, arguments: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
                calls.append(
                    {
                        "server": server,
                        "tool": tool,
                        "arguments": dict(arguments),
                        "internal_meta": dict(kwargs.get("internal_meta") or {}),
                    }
                )
                return {
                    "result": {"created": 123, "tool_event_verified": True},
                    "mcp": {"request_id": "mcp-request-http-yunwu-1"},
                }

        handler, captured = self._build_post_handler(
            "/api/router/image/yunwu/generate",
            {
                "prompt": "single transparent key",
                "n": 1,
                "session_key": "temporary-secret",
            },
            SimpleNamespace(
                mcp_broker=FakeBroker(),
                projects=SimpleNamespace(require_workspace_root=lambda: "D:/Workspace/demo"),
            ),
        )

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 200)
        self.assertEqual(calls[0]["server"], "yunwu_image")
        self.assertEqual(calls[0]["tool"], "yunwu_image_generate")
        self.assertEqual(calls[0]["arguments"]["workspace_root"], "D:/Workspace/demo")
        self.assertEqual(calls[0]["internal_meta"], {"internal_api_key": "temporary-secret"})
        self.assertNotIn("session_key", calls[0]["arguments"])
        self.assertNotIn("api_key", calls[0]["arguments"])
        self.assertEqual(captured["payload"]["mcp"]["request_id"], "mcp-request-http-yunwu-1")

    def test_handler_capability_invoke_route_uses_broker(self) -> None:
        calls: list[dict[str, Any]] = []

        class FakeBroker:
            def invoke_capability(self, capability_id: str, payload: dict[str, Any], **_: Any) -> dict[str, Any]:
                calls.append({"capability_id": capability_id, "payload": dict(payload)})
                return {
                    "result": {"capability_id": capability_id, "tool_event_verified": True, "workspace_root": payload.get("workspace_root")},
                    "mcp": {"request_id": "mcp-request-http-capability-1"},
                }

        handler, captured = self._build_post_handler(
            "/api/runtime/capability-invoke",
            {
                "capability_id": "image.generate",
                "payload": {"prompt": "render a prop"},
            },
            SimpleNamespace(
                mcp_broker=FakeBroker(),
                projects=SimpleNamespace(current_project={"workspace_root": "D:/Workspace/demo"}),
                seed_root=Path("D:/AstraBridge"),
            ),
        )

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 200)
        self.assertEqual(calls[0]["capability_id"], "image.generate")
        self.assertEqual(calls[0]["payload"]["workspace_root"], "D:/Workspace/demo")
        self.assertEqual(captured["payload"]["mcp"]["request_id"], "mcp-request-http-capability-1")

    def test_broker_denies_node_policy_before_capability_side_effect(self) -> None:
        calls: list[dict[str, Any]] = []

        class FakeCapabilityRuntime:
            def route_snapshot(self, capability_id: str | None = None) -> dict[str, Any]:
                return {"requested_capability_id": capability_id, "routes": [{"capability_id": "image.generate"}]}

            def invoke(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
                calls.append({"capability_id": capability_id, "payload": dict(payload)})
                return {"capability_id": capability_id, "payload": dict(payload)}

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            broker = McpBrokerService(project_service=projects, capability_runtime=FakeCapabilityRuntime())
            policy = resolve_node_mcp_tool_policy(
                tools={
                    "approval_mode": "allow",
                    "allowed_tool_classes": [],
                    "supports_mcp": False,
                    "mcp_policy": {
                        "tool_rules": [
                            {
                                "server": "astrabridge_capabilities",
                                "tools": ["astrabridge_capability_image_generate"],
                                "approval_mode": "deny",
                            }
                        ]
                    },
                },
                node_id="node_policy_test",
            )

            with self.assertRaises(McpToolPolicyDenied):
                broker.invoke_capability(
                    "image.generate",
                    {"prompt": "render a prop"},
                    caller="unit_test",
                    internal_meta={
                        "astrabridge_mcp_tool_policy": policy,
                        "astrabridge_mcp_policy_state": {},
                        "astrabridge_mcp_policy_context": {"run_id": "run-1", "node_id": "node-a", "attempt_count": 1},
                    },
                )

        self.assertEqual(calls, [])

    def test_remote_streamable_http_broker_discovers_protected_resource_metadata_and_preserves_typed_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            config = McpConfigService(root / "mcp_servers.json")
            config.upsert_server(
                {
                    "name": "remote_fixture",
                    "transport": "streamable_http",
                    "url": "https://remote.example/mcp",
                    "bearer_token_env_var": "ASTRABRIDGE_TEST_REMOTE_TOKEN",
                    "enabled": True,
                }
            )
            token = _jwt_token(aud="https://remote.example/mcp", scope="mcp:basic")
            fixture = _RemoteMcpTransportFixture(token=token)
            original = os.environ.get("ASTRABRIDGE_TEST_REMOTE_TOKEN")
            os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = token
            try:
                broker = McpBrokerService(project_service=projects, mcp_config=config, http_transport=fixture)
                response = broker.invoke_tool(
                    "remote_fixture",
                    "remote_echo",
                    {"message": "hello-remote"},
                    caller="unit_test",
                    operation_id="remote-op-typed-1",
                )
            finally:
                if original is None:
                    os.environ.pop("ASTRABRIDGE_TEST_REMOTE_TOKEN", None)
                else:
                    os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = original

        result = dict(response["result"])
        typed = dict(result["typed_result"])
        mcp = dict(response["mcp"])
        authorization = dict(mcp["authorization"])
        self.assertEqual(mcp["transport"], "streamable_http")
        self.assertEqual(authorization["resource_metadata_url"], fixture.metadata_url)
        self.assertEqual(authorization["resource"], "https://remote.example/mcp")
        self.assertEqual(authorization["required_scopes"], ["mcp:basic"])
        self.assertEqual(authorization["authorization_server_metadata_url"], fixture.auth_metadata_url)
        self.assertEqual(typed["summary"]["message"], "hello-remote")
        self.assertEqual(typed["artifact_refs"][0]["artifact_uri"], "workspace://.astrabridge/assets/generated/remote.png")
        self.assertTrue(any(str(item.get("method") or "") == "notifications/progress" for item in list(mcp["notifications"] or [])))
        self.assertEqual(fixture.tool_call_count, 1)

    def test_remote_streamable_http_broker_rejects_wrong_resource_and_overbroad_tokens(self) -> None:
        cases = [
            ("wrong_resource", _jwt_token(aud="https://different.example/mcp", scope="mcp:basic"), "audience"),
            ("overbroad_scope", _jwt_token(aud="https://remote.example/mcp", scope="mcp:basic mcp:write"), "broader"),
        ]
        for label, token, expected_text in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    workspace = root / "workspace"
                    workspace.mkdir()
                    projects = ProjectService(root / "recent.json")
                    projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
                    config = McpConfigService(root / "mcp_servers.json")
                    config.upsert_server(
                        {
                            "name": "remote_fixture",
                            "transport": "streamable_http",
                            "url": "https://remote.example/mcp",
                            "bearer_token_env_var": "ASTRABRIDGE_TEST_REMOTE_TOKEN",
                            "enabled": True,
                        }
                    )
                    fixture = _RemoteMcpTransportFixture(token=token)
                    original = os.environ.get("ASTRABRIDGE_TEST_REMOTE_TOKEN")
                    os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = token
                    try:
                        broker = McpBrokerService(project_service=projects, mcp_config=config, http_transport=fixture)
                        with self.assertRaises(PermissionError) as cm:
                            broker.invoke_tool(
                                "remote_fixture",
                                "remote_echo",
                                {"message": "hello-remote"},
                                caller="unit_test",
                                operation_id=f"remote-op-auth-{label}",
                            )
                    finally:
                        if original is None:
                            os.environ.pop("ASTRABRIDGE_TEST_REMOTE_TOKEN", None)
                        else:
                            os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = original
                self.assertIn(expected_text, str(cm.exception).lower())
                self.assertEqual(fixture.tool_call_count, 0)

    def test_remote_streamable_http_broker_rejects_local_artifact_path_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            config = McpConfigService(root / "mcp_servers.json")
            config.upsert_server(
                {
                    "name": "remote_fixture",
                    "transport": "streamable_http",
                    "url": "https://remote.example/mcp",
                    "bearer_token_env_var": "ASTRABRIDGE_TEST_REMOTE_TOKEN",
                    "enabled": True,
                }
            )
            token = _jwt_token(aud="https://remote.example/mcp", scope="mcp:basic")
            fixture = _RemoteMcpTransportFixture(token=token, leaking_artifact=True)
            original = os.environ.get("ASTRABRIDGE_TEST_REMOTE_TOKEN")
            os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = token
            try:
                broker = McpBrokerService(project_service=projects, mcp_config=config, http_transport=fixture)
                with self.assertRaises(ValueError) as cm:
                    broker.invoke_tool(
                        "remote_fixture",
                        "remote_echo",
                        {"message": "hello-remote"},
                        caller="unit_test",
                        operation_id="remote-op-leak-1",
                    )
            finally:
                if original is None:
                    os.environ.pop("ASTRABRIDGE_TEST_REMOTE_TOKEN", None)
                else:
                    os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = original
        self.assertIn("machine-local path", str(cm.exception))

    def test_remote_durable_task_bridge_survives_restart_without_duplicate_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            config = McpConfigService(root / "mcp_servers.json")
            config.upsert_server(
                {
                    "name": "remote_fixture",
                    "transport": "streamable_http",
                    "url": "https://remote.example/mcp",
                    "bearer_token_env_var": "ASTRABRIDGE_TEST_REMOTE_TOKEN",
                    "enabled": True,
                }
            )
            token = _jwt_token(aud="https://remote.example/mcp", scope="mcp:basic")
            fixture = _RemoteMcpTransportFixture(token=token, long_running=True)
            original = os.environ.get("ASTRABRIDGE_TEST_REMOTE_TOKEN")
            os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = token
            try:
                broker = McpBrokerService(project_service=projects, mcp_config=config, http_transport=fixture)
                first = broker.invoke_tool(
                    "remote_fixture",
                    "remote_echo",
                    {"message": "hello-remote"},
                    caller="unit_test",
                    operation_id="remote-op-durable-1",
                )
                restarted = McpBrokerService(project_service=projects, mcp_config=config, http_transport=fixture)
                second = restarted.invoke_tool(
                    "remote_fixture",
                    "remote_echo",
                    {"message": "hello-remote"},
                    caller="unit_test",
                    operation_id="remote-op-durable-1",
                )
                store = DurableRunEventStore(workspace)
                store.initialize()
                durable = store.get_external_operation("remote-op-durable-1")
                store.close()
            finally:
                if original is None:
                    os.environ.pop("ASTRABRIDGE_TEST_REMOTE_TOKEN", None)
                else:
                    os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = original

        self.assertEqual(first["result"]["status"], "pending")
        self.assertFalse(first["result"]["recovered"])
        self.assertEqual(second["result"]["status"], "pending")
        self.assertTrue(second["result"]["recovered"])
        self.assertEqual(fixture.tool_call_count, 1)
        self.assertEqual(durable["status"], "accepted")
        self.assertEqual(dict(durable["payload"] or {}).get("remote_handle"), "remote-handle-1")

    def test_remote_broker_denies_policy_before_http_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            config = McpConfigService(root / "mcp_servers.json")
            config.upsert_server(
                {
                    "name": "remote_fixture",
                    "transport": "streamable_http",
                    "url": "https://remote.example/mcp",
                    "bearer_token_env_var": "ASTRABRIDGE_TEST_REMOTE_TOKEN",
                    "enabled": True,
                }
            )
            token = _jwt_token(aud="https://remote.example/mcp", scope="mcp:basic")
            fixture = _RemoteMcpTransportFixture(token=token)
            original = os.environ.get("ASTRABRIDGE_TEST_REMOTE_TOKEN")
            os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = token
            try:
                broker = McpBrokerService(project_service=projects, mcp_config=config, http_transport=fixture)
                policy = resolve_node_mcp_tool_policy(
                    tools={
                        "approval_mode": "allow",
                        "allowed_tool_classes": [],
                        "supports_mcp": True,
                        "mcp_policy": {
                            "tool_rules": [
                                {
                                    "server": "remote_fixture",
                                    "tools": ["remote_echo"],
                                    "approval_mode": "deny",
                                }
                            ]
                        },
                    },
                    node_id="node_policy_test",
                )
                with self.assertRaises(McpToolPolicyDenied):
                    broker.invoke_tool(
                        "remote_fixture",
                        "remote_echo",
                        {"message": "blocked"},
                        caller="unit_test",
                        operation_id="remote-op-policy-1",
                        internal_meta={
                            "astrabridge_mcp_tool_policy": policy,
                            "astrabridge_mcp_policy_state": {},
                            "astrabridge_mcp_policy_context": {"run_id": "run-1", "node_id": "node-a", "attempt_count": 1},
                        },
                    )
            finally:
                if original is None:
                    os.environ.pop("ASTRABRIDGE_TEST_REMOTE_TOKEN", None)
                else:
                    os.environ["ASTRABRIDGE_TEST_REMOTE_TOKEN"] = original
        self.assertEqual(fixture.authorized_request_count, 0)
        self.assertEqual(fixture.tool_call_count, 0)

    def test_step_12_boundary_sources_reject_direct_bypass_patterns(self) -> None:
        runtime_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_service.py").read_text(encoding="utf-8")
        for pattern in (
            "self._web_tools.search_batch(",
            "self._web_tools.research_brief(",
            "self._web_tools.fetch(",
            "self._capability_runtime.invoke(",
            "self._yunwu_image.generate(",
            "self._yunwu_image.edit(",
            "self._yunwu_image.transparent_asset(",
        ):
            self.assertNotIn(pattern, runtime_source)

        server_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "server.py").read_text(encoding="utf-8")
        server_route_block = server_source[
            server_source.index('if path == "/api/router/image/yunwu/test":') : server_source.index('if path == "/api/runtime/capability-smoke":')
        ]
        self.assertIn("self.context.mcp_broker.invoke_tool(", server_route_block)
        self.assertIn("self.context.mcp_broker.invoke_capability(", server_route_block)
        self.assertNotIn("self.context.yunwu_image.generate(", server_route_block)
        self.assertNotIn("self.context.yunwu_image.edit(", server_route_block)
        self.assertNotIn("self.context.yunwu_image.transparent_asset(", server_route_block)
        self.assertNotIn("CapabilityRuntime(", server_route_block)

        web_source = (SIDECAR_ROOT / "astrabridge_sidecar" / "web_tool_service.py").read_text(encoding="utf-8")
        public_web_block = web_source[web_source.index("def search_batch(") : web_source.index("def _invoke_via_broker(")]
        self.assertIn("_invoke_via_broker(", public_web_block)
        self.assertNotIn("_search_batch(", public_web_block)
        self.assertNotIn("_research_brief(", public_web_block)
        self.assertNotIn("_fetch(", public_web_block)

    def _build_post_handler(self, path: str, payload: dict[str, Any], context: Any) -> tuple[Handler, dict[str, Any]]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        handler = object.__new__(Handler)
        handler.command = "POST"
        handler.path = path
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler.context = context
        handler._require_admin_token = lambda: None  # type: ignore[method-assign]
        captured: dict[str, Any] = {}
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[method-assign]
        return handler, captured


if __name__ == "__main__":
    unittest.main()
