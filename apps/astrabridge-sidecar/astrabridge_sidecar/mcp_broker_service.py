from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .astrabridge_capabilities_mcp_server import _server_core as capability_server_core
from .astrabridge_web_mcp_server import _server_core as web_server_core
from .common import new_id
from .mcp_node_policy import McpToolPolicyDenied, authorize_mcp_tool_call
from .mcp_server_core import JSONRPC_VERSION, LoopbackMcpSession, MCP_LATEST_PROTOCOL_VERSION, McpServerCore
from .yunwu_image_mcp_server import _server_core as yunwu_server_core


@dataclass(slots=True)
class McpBrokerService:
    project_service: Any
    capability_runtime: Any | None = None
    yunwu_image_service: Any | None = None
    mcp_config: Any | None = None
    _web_core: McpServerCore = field(init=False, repr=False)
    _capability_core: McpServerCore | None = field(init=False, repr=False)
    _yunwu_core: McpServerCore | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._web_core = web_server_core()
        self._capability_core = capability_server_core(self.capability_runtime) if self.capability_runtime is not None else None
        self._yunwu_core = yunwu_server_core(self.yunwu_image_service) if self.yunwu_image_service is not None else None

    def invoke_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        caller: str,
        operation_id: str | None = None,
        internal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        core = self._resolve_core(server)
        clean_tool = str(tool or "").strip()
        if not clean_tool:
            raise ValueError("tool is required.")
        allowed_tools = {str(item.get("name") or "").strip() for item in core.tools_provider()}
        if clean_tool not in allowed_tools:
            raise ValueError(f"Unsupported MCP broker tool `{clean_tool}` for server `{server}`.")
        payload = self._arguments_with_workspace_root(server, clean_tool, arguments or {})
        policy_snapshot = dict(dict(internal_meta or {}).get("astrabridge_mcp_tool_policy") or {})
        if policy_snapshot:
            policy_decision = authorize_mcp_tool_call(
                policy_snapshot,
                server=server,
                tool=clean_tool,
                arguments=payload,
                caller=str(caller or "").strip() or "internal",
                state=dict(dict(internal_meta or {}).get("astrabridge_mcp_policy_state") or {}),
                context=dict(dict(internal_meta or {}).get("astrabridge_mcp_policy_context") or {}),
            )
        else:
            policy_decision = {
                "decision": "allow",
                "reason": "registered_server_tool",
            }
        policy_decision["server_enabled"] = self._server_enabled(server)
        policy_decision["caller"] = str(caller or "").strip() or "internal"
        session = LoopbackMcpSession(core, session_id=new_id("mcp-session"))
        init_response = session.request(
            {
                "jsonrpc": JSONRPC_VERSION,
                "id": new_id("mcp-init"),
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_LATEST_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "astrabridge-sidecar-broker", "version": "0.1.0"},
                },
            }
        )
        if not isinstance(init_response, dict) or "error" in init_response:
            raise RuntimeError(f"MCP broker initialize failed for server `{server}`.")
        session.request({"jsonrpc": JSONRPC_VERSION, "method": "notifications/initialized"})
        request_id = new_id("mcp-request")
        clean_operation_id = str(operation_id or "").strip() or new_id("mcp-op")
        response = session.request(
            {
                "jsonrpc": JSONRPC_VERSION,
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": clean_tool,
                    "arguments": payload,
                    "_meta": {
                        "operationId": clean_operation_id,
                        **dict(internal_meta or {}),
                    },
                },
            }
        )
        notifications = session.drain_notifications()
        if not isinstance(response, dict):
            raise RuntimeError(f"MCP broker did not receive a response for `{clean_tool}`.")
        if "error" in response:
            message = str(dict(response.get("error") or {}).get("message") or f"tool call failed: {clean_tool}")
            raise RuntimeError(message)
        result = dict(response.get("result") or {})
        structured = result.get("structuredContent")
        trace_context = dict(dict(internal_meta or {}).get("astrabridge_trace") or {})
        if not trace_context:
            trace_context = dict(dict(internal_meta or {}).get("astrabridge_mcp_policy_context") or {})
        audit_event = {
            "type": "mcp_broker_tool_call",
            "server": server,
            "tool": clean_tool,
            "transport": "loopback",
            "session_id": session.session_id,
            "request_id": request_id,
            "operation_id": clean_operation_id,
            "protocol_version": str(dict(init_response.get("result") or {}).get("protocolVersion") or MCP_LATEST_PROTOCOL_VERSION),
            "policy_decision": dict(policy_decision),
            "caller": str(caller or "").strip() or "internal",
            "notification_count": len(notifications),
            "success": True,
            "trace_context": trace_context,
        }
        return {
            "result": structured if structured is not None else result,
            "mcp_result": result,
            "mcp": {
                "server": server,
                "tool": clean_tool,
                "transport": "loopback",
                "session_id": session.session_id,
                "request_id": request_id,
                "operation_id": clean_operation_id,
                "protocol_version": str(dict(init_response.get("result") or {}).get("protocolVersion") or MCP_LATEST_PROTOCOL_VERSION),
                "policy_decision": dict(policy_decision),
                "notifications": notifications,
                "audit_event": audit_event,
            },
        }

    def invoke_capability(
        self,
        capability_id: str,
        payload: dict[str, Any] | None = None,
        *,
        caller: str,
        operation_id: str | None = None,
        internal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        capability = str(capability_id or "").strip()
        if capability == "routes":
            return self.invoke_tool(
                "astrabridge_capabilities",
                "astrabridge_capability_routes",
                payload or {},
                caller=caller,
                operation_id=operation_id,
                internal_meta=internal_meta,
            )
        tool_map = {
            "image.generate": "astrabridge_capability_image_generate",
            "vision.analyze": "astrabridge_capability_vision_analyze",
            "speech.transcribe": "astrabridge_capability_speech_transcribe",
            "speech.synthesize": "astrabridge_capability_speech_synthesize",
        }
        tool = tool_map.get(capability)
        if not tool:
            raise ValueError(f"Unsupported capability for MCP broker: {capability}")
        return self.invoke_tool(
            "astrabridge_capabilities",
            tool,
            payload or {},
            caller=caller,
            operation_id=operation_id,
            internal_meta=internal_meta,
        )

    def _resolve_core(self, server: str) -> McpServerCore:
        clean_server = str(server or "").strip()
        if clean_server == "astrabridge_web":
            return self._web_core
        if clean_server == "astrabridge_capabilities":
            if self._capability_core is None:
                raise RuntimeError("Capability runtime is not available for the MCP broker.")
            return self._capability_core
        if clean_server == "yunwu_image":
            if self._yunwu_core is None:
                raise RuntimeError("Yunwu image service is not available for the MCP broker.")
            return self._yunwu_core
        raise ValueError(f"Unsupported internal MCP broker server: {clean_server}")

    def _arguments_with_workspace_root(self, server: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = dict(arguments or {})
        workspace_root = self._workspace_root()
        if workspace_root and server in {"astrabridge_capabilities", "yunwu_image"} and not str(payload.get("workspace_root") or "").strip():
            payload["workspace_root"] = workspace_root
        if workspace_root and tool == "astrabridge_capability_routes":
            payload.setdefault("workspace_root", workspace_root)
        return payload

    def _workspace_root(self) -> str:
        try:
            return str(self.project_service.require_workspace_root())
        except Exception:
            return ""

    def _server_enabled(self, server: str) -> bool:
        if self.mcp_config is None:
            return False
        try:
            return any(str(item.get("name") or "") == server for item in self.mcp_config.enabled_servers())
        except Exception:
            return False
