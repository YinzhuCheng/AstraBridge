from __future__ import annotations

import io
import json
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
from astrabridge_sidecar.mcp_node_policy import McpToolPolicyDenied, resolve_node_mcp_tool_policy  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.server import Handler  # noqa: E402
from astrabridge_sidecar.web_tool_service import AstraBridgeWebService  # noqa: E402


class McpBrokerServiceTests(unittest.TestCase):
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
