from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .astrabridge_capabilities_mcp_server import _server_core as capability_server_core
from .astrabridge_web_mcp_server import _server_core as web_server_core
from .common import new_id, now_iso
from .durable_run_store import DurableRunEventStore
from .mcp_node_policy import McpToolPolicyDenied, authorize_mcp_tool_call
from .mcp_server_core import (
    JSONRPC_VERSION,
    LoopbackMcpSession,
    MCP_LATEST_PROTOCOL_VERSION,
    McpHttpResponse,
    McpServerCore,
)
from .release_identity import release_product_version
from .yunwu_image_mcp_server import _server_core as yunwu_server_core


RemoteHttpTransport = Callable[[str, str, Mapping[str, str] | None, bytes | str | dict[str, Any] | None], McpHttpResponse]

_REMOTE_OPERATION_KIND = "mcp_remote_tool_call"
_REMOTE_OPERATION_CLASSIFICATION = "broker_dispatch"
_REMOTE_PENDING_RESULT_SCHEMA_VERSION = "astrabridge-mcp-durable-task-bridge-v1"


@dataclass(slots=True)
class _RemoteSessionState:
    server: str
    url: str
    session_id: str
    protocol_version: str
    authorization: dict[str, Any] = field(default_factory=dict)
    allowed_tools: set[str] = field(default_factory=set)


@dataclass(slots=True)
class McpBrokerService:
    project_service: Any
    capability_runtime: Any | None = None
    yunwu_image_service: Any | None = None
    mcp_config: Any | None = None
    http_transport: RemoteHttpTransport | None = None
    _web_core: McpServerCore = field(init=False, repr=False)
    _capability_core: McpServerCore | None = field(init=False, repr=False)
    _yunwu_core: McpServerCore | None = field(init=False, repr=False)
    _remote_sessions: dict[str, _RemoteSessionState] = field(default_factory=dict, init=False, repr=False)
    _remote_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _durable_store: DurableRunEventStore | None = field(default=None, init=False, repr=False)
    _durable_store_workspace: str | None = field(default=None, init=False, repr=False)

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
        clean_server = str(server or "").strip()
        clean_tool = str(tool or "").strip()
        if not clean_tool:
            raise ValueError("tool is required.")
        payload = self._arguments_with_workspace_root(clean_server, clean_tool, arguments or {})
        policy_decision = self._authorize_tool(
            clean_server,
            clean_tool,
            payload,
            caller=caller,
            internal_meta=internal_meta,
        )
        clean_operation_id = str(operation_id or "").strip() or new_id("mcp-op")
        core = self._resolve_internal_core(clean_server)
        if core is not None:
            return self._invoke_loopback_tool(
                clean_server,
                clean_tool,
                payload,
                core=core,
                caller=caller,
                operation_id=clean_operation_id,
                internal_meta=internal_meta,
                policy_decision=policy_decision,
            )
        server_config = self._resolve_remote_server_config(clean_server)
        if str(server_config.get("transport") or "").strip() != "streamable_http":
            raise ValueError(f"Unsupported MCP broker transport for server `{clean_server}`.")
        return self._invoke_streamable_http_tool(
            clean_server,
            clean_tool,
            payload,
            server_config=server_config,
            caller=caller,
            operation_id=clean_operation_id,
            internal_meta=internal_meta,
            policy_decision=policy_decision,
        )

    def read_resource(
        self,
        server: str,
        resource: str,
        *,
        caller: str,
        operation_id: str | None = None,
        internal_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_server = str(server or "").strip()
        clean_resource = str(resource or "").strip()
        if not clean_resource:
            raise ValueError("resource is required.")
        clean_operation_id = str(operation_id or "").strip() or new_id("mcp-resource")
        policy_decision = self._authorize_resource_read(
            clean_server,
            clean_resource,
            caller=caller,
            internal_meta=internal_meta,
        )
        core = self._resolve_internal_core(clean_server)
        if core is not None:
            return self._read_loopback_resource(
                clean_server,
                clean_resource,
                core=core,
                caller=caller,
                operation_id=clean_operation_id,
                internal_meta=internal_meta,
                policy_decision=policy_decision,
            )
        server_config = self._resolve_remote_server_config(clean_server)
        if str(server_config.get("transport") or "").strip() != "streamable_http":
            raise ValueError(f"Unsupported MCP broker transport for server `{clean_server}`.")
        return self._read_streamable_http_resource(
            clean_server,
            clean_resource,
            server_config=server_config,
            caller=caller,
            operation_id=clean_operation_id,
            internal_meta=internal_meta,
            policy_decision=policy_decision,
        )

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

    def _authorize_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any],
        *,
        caller: str,
        internal_meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        policy_snapshot = dict(dict(internal_meta or {}).get("astrabridge_mcp_tool_policy") or {})
        if policy_snapshot:
            policy_decision = authorize_mcp_tool_call(
                policy_snapshot,
                server=server,
                tool=tool,
                arguments=arguments,
                caller=str(caller or "").strip() or "internal",
                state=dict(dict(internal_meta or {}).get("astrabridge_mcp_policy_state") or {}),
                context=dict(dict(internal_meta or {}).get("astrabridge_mcp_policy_context") or {}),
            )
        else:
            policy_decision = {"decision": "allow", "reason": "registered_server_tool"}
        policy_decision["server_enabled"] = self._server_enabled(server)
        policy_decision["caller"] = str(caller or "").strip() or "internal"
        return policy_decision

    def _authorize_resource_read(
        self,
        server: str,
        resource_uri: str,
        *,
        caller: str,
        internal_meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        policy_snapshot = dict(dict(internal_meta or {}).get("astrabridge_mcp_tool_policy") or {})
        if not policy_snapshot:
            return {
                "decision": "allow",
                "reason": "registered_server_resource",
                "server_enabled": self._server_enabled(server),
                "caller": str(caller or "").strip() or "internal",
            }
        representative_rule = next(
            (
                dict(item)
                for item in list(policy_snapshot.get("tool_rules") or [])
                if isinstance(item, dict)
                and str(item.get("server") or "").strip() == server
                and bool(item.get("available"))
            ),
            None,
        )
        if representative_rule is None:
            raise McpToolPolicyDenied(
                f"AstraBridge MCP node policy denied undeclared resource read on `{server}`.",
                decision={
                    "decision": "deny",
                    "reason": "undeclared_resource_server",
                    "server": server,
                    "tool": None,
                    "resource_uri": resource_uri,
                },
            )
        policy_decision = authorize_mcp_tool_call(
            policy_snapshot,
            server=server,
            tool=str(representative_rule.get("tool") or "").strip(),
            arguments={"resource_uri": resource_uri},
            caller=str(caller or "").strip() or "internal",
            state=dict(dict(internal_meta or {}).get("astrabridge_mcp_policy_state") or {}),
            context=dict(dict(internal_meta or {}).get("astrabridge_mcp_policy_context") or {}),
        )
        policy_decision["resource_uri"] = resource_uri
        policy_decision["server_enabled"] = self._server_enabled(server)
        policy_decision["caller"] = str(caller or "").strip() or "internal"
        return policy_decision

    def _invoke_loopback_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any],
        *,
        core: McpServerCore,
        caller: str,
        operation_id: str,
        internal_meta: dict[str, Any] | None,
        policy_decision: dict[str, Any],
    ) -> dict[str, Any]:
        allowed_tools = {str(item.get("name") or "").strip() for item in core.tools_provider()}
        if tool not in allowed_tools:
            raise ValueError(f"Unsupported MCP broker tool `{tool}` for server `{server}`.")
        session = LoopbackMcpSession(core, session_id=new_id("mcp-session"))
        init_response = session.request(
            {
                "jsonrpc": JSONRPC_VERSION,
                "id": new_id("mcp-init"),
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_LATEST_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "astrabridge-sidecar-broker", "version": release_product_version()},
                },
            }
        )
        if not isinstance(init_response, dict) or "error" in init_response:
            raise RuntimeError(f"MCP broker initialize failed for server `{server}`.")
        session.request({"jsonrpc": JSONRPC_VERSION, "method": "notifications/initialized"})
        request_id = new_id("mcp-request")
        response = session.request(
            {
                "jsonrpc": JSONRPC_VERSION,
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool,
                    "arguments": arguments,
                    "_meta": {
                        "progressToken": str(dict(internal_meta or {}).get("progressToken") or operation_id),
                        "operationId": operation_id,
                        **dict(internal_meta or {}),
                    },
                },
            }
        )
        notifications = session.drain_notifications()
        if not isinstance(response, dict):
            raise RuntimeError(f"MCP broker did not receive a response for `{tool}`.")
        if "error" in response:
            message = str(dict(response.get("error") or {}).get("message") or f"tool call failed: {tool}")
            raise RuntimeError(message)
        result = dict(response.get("result") or {})
        structured = result.get("structuredContent")
        trace_context = self._trace_context(internal_meta)
        audit_event = {
            "type": "mcp_broker_tool_call",
            "server": server,
            "tool": tool,
            "transport": "loopback",
            "session_id": session.session_id,
            "request_id": request_id,
            "operation_id": operation_id,
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
                "tool": tool,
                "transport": "loopback",
                "session_id": session.session_id,
                "request_id": request_id,
                "operation_id": operation_id,
                "protocol_version": str(dict(init_response.get("result") or {}).get("protocolVersion") or MCP_LATEST_PROTOCOL_VERSION),
                "policy_decision": dict(policy_decision),
                "notifications": notifications,
                "audit_event": audit_event,
            },
        }

    def _read_loopback_resource(
        self,
        server: str,
        resource: str,
        *,
        core: McpServerCore,
        caller: str,
        operation_id: str,
        internal_meta: dict[str, Any] | None,
        policy_decision: dict[str, Any],
    ) -> dict[str, Any]:
        resources = [dict(item) for item in core.resources_provider()]
        descriptor = next(
            (
                item
                for item in resources
                if str(item.get("uri") or "").strip() == resource
            ),
            None,
        )
        if descriptor is None:
            raise ValueError(f"Unsupported MCP broker resource `{resource}` for server `{server}`.")
        reader = getattr(core, "resource_reader", None)
        if callable(reader):
            result = dict(reader(resource) or {})
        else:
            mime_type = str(descriptor.get("mimeType") or descriptor.get("mime_type") or "application/json").strip() or "application/json"
            text_value = descriptor.get("text")
            blob_value = descriptor.get("blob")
            if text_value is None and blob_value is None:
                text_value = json.dumps(descriptor, ensure_ascii=False)
            content_item = {
                "uri": resource,
                "mimeType": mime_type,
            }
            if blob_value is not None:
                content_item["blob"] = str(blob_value)
            else:
                content_item["text"] = str(text_value or "")
            result = {"resource": descriptor, "contents": [content_item]}
        structured = result.get("structuredContent")
        trace_context = self._trace_context(internal_meta)
        audit_event = {
            "type": "mcp_broker_resource_read",
            "server": server,
            "resource": resource,
            "transport": "loopback",
            "operation_id": operation_id,
            "policy_decision": dict(policy_decision),
            "caller": str(caller or "").strip() or "internal",
            "success": True,
            "trace_context": trace_context,
        }
        return {
            "result": structured if structured is not None else result,
            "mcp_result": result,
            "mcp": {
                "server": server,
                "resource": resource,
                "transport": "loopback",
                "operation_id": operation_id,
                "policy_decision": dict(policy_decision),
                "audit_event": audit_event,
            },
        }

    def _invoke_streamable_http_tool(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any],
        *,
        server_config: dict[str, Any],
        caller: str,
        operation_id: str,
        internal_meta: dict[str, Any] | None,
        policy_decision: dict[str, Any],
    ) -> dict[str, Any]:
        request_fingerprint = _request_fingerprint(server, tool, arguments, caller=caller)
        durable_existing = self._load_remote_durable_operation(operation_id)
        if durable_existing is not None:
            existing_payload = dict(durable_existing.get("payload") or {})
            existing_fingerprint = str(existing_payload.get("request_fingerprint") or "").strip()
            if existing_fingerprint and existing_fingerprint != request_fingerprint:
                raise ValueError(f"Remote MCP durable operation `{operation_id}` is already bound to a different request payload.")
            existing_status = str(durable_existing.get("status") or "").strip().lower()
            if existing_status == "completed":
                replay_response = dict(existing_payload.get("broker_response") or {})
                if replay_response:
                    replay_response.setdefault("mcp", {})
                    replay_response["mcp"] = {
                        **dict(replay_response.get("mcp") or {}),
                        "durable_task": {
                            "schema_version": _REMOTE_PENDING_RESULT_SCHEMA_VERSION,
                            "operation_id": operation_id,
                            "status": "completed",
                            "recovered": True,
                        },
                    }
                    return replay_response
            if existing_status in {"pending", "accepted", "running"}:
                return self._pending_remote_broker_response(
                    server,
                    tool,
                    operation_id=operation_id,
                    policy_decision=policy_decision,
                    durable_payload=existing_payload,
                    recovered=True,
                )
        session = self._ensure_remote_session(server, server_config)
        if not session.allowed_tools:
            session.allowed_tools = self._list_remote_tools(session)
        if tool not in session.allowed_tools:
            raise ValueError(f"Unsupported MCP broker tool `{tool}` for server `{server}`.")
        request_id = new_id("mcp-request")
        payload = {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": arguments,
                "_meta": {
                    "progressToken": str(dict(internal_meta or {}).get("progressToken") or operation_id),
                    "operationId": operation_id,
                    **dict(internal_meta or {}),
                },
            },
        }
        self._record_remote_operation(
            operation_id,
            server=server,
            tool=tool,
            status="pending",
            payload={
                "transport": "streamable_http",
                "request_fingerprint": request_fingerprint,
                "authorization": self._durable_authorization_snapshot(session.authorization),
                "request_arguments": arguments,
            },
        )
        response = self._remote_jsonrpc_request(session, payload, allow_reinitialize=True)
        notifications = self._remote_notifications(session)
        if response.status_code == 202:
            remote_handle = str(response.headers.get("X-AstraBridge-Task-Handle") or "").strip() or None
            durable_payload = {
                "transport": "streamable_http",
                "request_fingerprint": request_fingerprint,
                "authorization": self._durable_authorization_snapshot(session.authorization),
                "remote_handle": remote_handle,
                "notifications": notifications,
            }
            self._record_remote_operation(
                operation_id,
                server=server,
                tool=tool,
                status="accepted",
                payload=durable_payload,
                external_handle=remote_handle,
            )
            return self._pending_remote_broker_response(
                server,
                tool,
                operation_id=operation_id,
                policy_decision=policy_decision,
                durable_payload=durable_payload,
                recovered=False,
            )
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError(f"Remote MCP broker returned a non-JSON response for `{tool}`.")
        if "error" in body:
            message = str(dict(body.get("error") or {}).get("message") or f"tool call failed: {tool}")
            self._record_remote_operation(
                operation_id,
                server=server,
                tool=tool,
                status="failed",
                payload={
                    "transport": "streamable_http",
                    "request_fingerprint": request_fingerprint,
                    "authorization": self._durable_authorization_snapshot(session.authorization),
                    "error": message,
                },
            )
            raise RuntimeError(message)
        result = dict(body.get("result") or {})
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            self._validate_remote_typed_result(structured)
        trace_context = self._trace_context(internal_meta)
        audit_event = {
            "type": "mcp_broker_tool_call",
            "server": server,
            "tool": tool,
            "transport": "streamable_http",
            "session_id": session.session_id,
            "request_id": request_id,
            "operation_id": operation_id,
            "protocol_version": session.protocol_version,
            "policy_decision": dict(policy_decision),
            "caller": str(caller or "").strip() or "internal",
            "notification_count": len(notifications),
            "success": True,
            "trace_context": trace_context,
            "resource_metadata": self._durable_authorization_snapshot(session.authorization),
        }
        broker_response = {
            "result": structured if structured is not None else result,
            "mcp_result": result,
            "mcp": {
                "server": server,
                "tool": tool,
                "transport": "streamable_http",
                "session_id": session.session_id,
                "request_id": request_id,
                "operation_id": operation_id,
                "protocol_version": session.protocol_version,
                "policy_decision": dict(policy_decision),
                "notifications": notifications,
                "authorization": self._durable_authorization_snapshot(session.authorization),
                "audit_event": audit_event,
                "durable_task": {
                    "schema_version": _REMOTE_PENDING_RESULT_SCHEMA_VERSION,
                    "operation_id": operation_id,
                    "status": "completed",
                    "recovered": False,
                },
            },
        }
        self._record_remote_operation(
            operation_id,
            server=server,
            tool=tool,
            status="completed",
            payload={
                "transport": "streamable_http",
                "request_fingerprint": request_fingerprint,
                "authorization": self._durable_authorization_snapshot(session.authorization),
                "broker_response": broker_response,
            },
        )
        return broker_response

    def _pending_remote_broker_response(
        self,
        server: str,
        tool: str,
        *,
        operation_id: str,
        policy_decision: dict[str, Any],
        durable_payload: dict[str, Any],
        recovered: bool,
    ) -> dict[str, Any]:
        pending_result = {
            "schema_version": _REMOTE_PENDING_RESULT_SCHEMA_VERSION,
            "status": "pending",
            "operation_id": operation_id,
            "remote_handle": durable_payload.get("remote_handle"),
            "recovered": recovered,
            "notifications": list(durable_payload.get("notifications") or []),
        }
        return {
            "result": pending_result,
            "mcp_result": {"structuredContent": pending_result},
            "mcp": {
                "server": server,
                "tool": tool,
                "transport": "streamable_http",
                "operation_id": operation_id,
                "policy_decision": dict(policy_decision),
                "authorization": _coerce_mapping(durable_payload.get("authorization")),
                "durable_task": {
                    "schema_version": _REMOTE_PENDING_RESULT_SCHEMA_VERSION,
                    "operation_id": operation_id,
                    "status": "pending",
                    "recovered": recovered,
                    "remote_handle": durable_payload.get("remote_handle"),
                },
                "notifications": list(durable_payload.get("notifications") or []),
                "audit_event": {
                    "type": "mcp_broker_tool_call",
                    "server": server,
                    "tool": tool,
                    "transport": "streamable_http",
                    "operation_id": operation_id,
                    "policy_decision": dict(policy_decision),
                    "success": True,
                    "durable_pending": True,
                    "recovered": recovered,
                },
            },
        }

    def _read_streamable_http_resource(
        self,
        server: str,
        resource: str,
        *,
        server_config: dict[str, Any],
        caller: str,
        operation_id: str,
        internal_meta: dict[str, Any] | None,
        policy_decision: dict[str, Any],
    ) -> dict[str, Any]:
        request_fingerprint = _request_fingerprint(server, "resources/read", {"resource_uri": resource}, caller=caller)
        durable_existing = self._load_remote_durable_operation(operation_id)
        if durable_existing is not None:
            existing_payload = dict(durable_existing.get("payload") or {})
            existing_fingerprint = str(existing_payload.get("request_fingerprint") or "").strip()
            if existing_fingerprint and existing_fingerprint != request_fingerprint:
                raise ValueError(f"Remote MCP durable operation `{operation_id}` is already bound to a different request payload.")
            existing_status = str(durable_existing.get("status") or "").strip().lower()
            if existing_status == "completed":
                replay_response = dict(existing_payload.get("broker_response") or {})
                if replay_response:
                    replay_response.setdefault("mcp", {})
                    replay_response["mcp"] = {
                        **dict(replay_response.get("mcp") or {}),
                        "durable_task": {
                            "schema_version": _REMOTE_PENDING_RESULT_SCHEMA_VERSION,
                            "operation_id": operation_id,
                            "status": "completed",
                            "recovered": True,
                        },
                    }
                    return replay_response
            if existing_status in {"pending", "accepted", "running"}:
                return self._pending_remote_broker_response(
                    server,
                    f"resources/read:{resource}",
                    operation_id=operation_id,
                    policy_decision=policy_decision,
                    durable_payload=existing_payload,
                    recovered=True,
                )
        session = self._ensure_remote_session(server, server_config)
        request_id = new_id("mcp-request")
        payload = {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "method": "resources/read",
            "params": {
                "uri": resource,
                "_meta": {
                    "progressToken": str(dict(internal_meta or {}).get("progressToken") or operation_id),
                    "operationId": operation_id,
                    **dict(internal_meta or {}),
                },
            },
        }
        self._record_remote_operation(
            operation_id,
            server=server,
            tool="resources/read",
            status="pending",
            payload={
                "transport": "streamable_http",
                "request_fingerprint": request_fingerprint,
                "authorization": self._durable_authorization_snapshot(session.authorization),
                "resource_uri": resource,
            },
        )
        response = self._remote_jsonrpc_request(session, payload, allow_reinitialize=True)
        notifications = self._remote_notifications(session)
        if response.status_code == 202:
            remote_handle = str(response.headers.get("X-AstraBridge-Task-Handle") or "").strip() or None
            durable_payload = {
                "transport": "streamable_http",
                "request_fingerprint": request_fingerprint,
                "authorization": self._durable_authorization_snapshot(session.authorization),
                "remote_handle": remote_handle,
                "notifications": notifications,
            }
            self._record_remote_operation(
                operation_id,
                server=server,
                tool="resources/read",
                status="accepted",
                payload=durable_payload,
                external_handle=remote_handle,
            )
            return self._pending_remote_broker_response(
                server,
                f"resources/read:{resource}",
                operation_id=operation_id,
                policy_decision=policy_decision,
                durable_payload=durable_payload,
                recovered=False,
            )
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError(f"Remote MCP broker returned a non-JSON response for resource `{resource}`.")
        if "error" in body:
            message = str(dict(body.get("error") or {}).get("message") or f"resource read failed: {resource}")
            self._record_remote_operation(
                operation_id,
                server=server,
                tool="resources/read",
                status="failed",
                payload={
                    "transport": "streamable_http",
                    "request_fingerprint": request_fingerprint,
                    "authorization": self._durable_authorization_snapshot(session.authorization),
                    "error": message,
                },
            )
            raise RuntimeError(message)
        result = dict(body.get("result") or {})
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            self._validate_remote_typed_result(structured)
        trace_context = self._trace_context(internal_meta)
        audit_event = {
            "type": "mcp_broker_resource_read",
            "server": server,
            "resource": resource,
            "transport": "streamable_http",
            "session_id": session.session_id,
            "request_id": request_id,
            "operation_id": operation_id,
            "protocol_version": session.protocol_version,
            "policy_decision": dict(policy_decision),
            "caller": str(caller or "").strip() or "internal",
            "notification_count": len(notifications),
            "success": True,
            "trace_context": trace_context,
            "resource_metadata": self._durable_authorization_snapshot(session.authorization),
        }
        broker_response = {
            "result": structured if structured is not None else result,
            "mcp_result": result,
            "mcp": {
                "server": server,
                "resource": resource,
                "transport": "streamable_http",
                "session_id": session.session_id,
                "request_id": request_id,
                "operation_id": operation_id,
                "protocol_version": session.protocol_version,
                "policy_decision": dict(policy_decision),
                "notifications": notifications,
                "authorization": self._durable_authorization_snapshot(session.authorization),
                "audit_event": audit_event,
                "durable_task": {
                    "schema_version": _REMOTE_PENDING_RESULT_SCHEMA_VERSION,
                    "operation_id": operation_id,
                    "status": "completed",
                    "recovered": False,
                },
            },
        }
        self._record_remote_operation(
            operation_id,
            server=server,
            tool="resources/read",
            status="completed",
            payload={
                "transport": "streamable_http",
                "request_fingerprint": request_fingerprint,
                "authorization": self._durable_authorization_snapshot(session.authorization),
                "broker_response": broker_response,
            },
        )
        return broker_response

    def _resolve_internal_core(self, server: str) -> McpServerCore | None:
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
        return None

    def _resolve_remote_server_config(self, server: str) -> dict[str, Any]:
        if self.mcp_config is None:
            raise ValueError(f"Unsupported MCP broker server: {server}")
        snapshot = dict(self.mcp_config.snapshot() or {})
        for item in list(snapshot.get("servers") or []):
            if isinstance(item, dict) and str(item.get("name") or "").strip() == server:
                return dict(item)
        raise ValueError(f"Unsupported MCP broker server: {server}")

    def _ensure_remote_session(self, server: str, server_config: dict[str, Any]) -> _RemoteSessionState:
        url = str(server_config.get("url") or "").strip()
        if not url:
            raise ValueError(f"Remote MCP server `{server}` is missing a URL.")
        with self._remote_lock:
            existing = self._remote_sessions.get(server)
            if existing is not None and existing.url == url:
                return existing
        initialized = self._initialize_remote_session(server, server_config)
        with self._remote_lock:
            self._remote_sessions[server] = initialized
        return initialized

    def _initialize_remote_session(self, server: str, server_config: dict[str, Any]) -> _RemoteSessionState:
        url = str(server_config.get("url") or "").strip()
        initialize_message = {
            "jsonrpc": JSONRPC_VERSION,
            "id": new_id("mcp-init"),
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "astrabridge-sidecar-broker", "version": release_product_version()},
            },
        }
        first = self._http_request("POST", url, headers=self._json_headers(), body=initialize_message)
        authorization = {}
        if first.status_code == 401:
            authorization = self._discover_remote_authorization(server_config, challenge_response=first)
            first = self._http_request(
                "POST",
                url,
                headers={**self._json_headers(), **self._authorization_headers(server_config, authorization)},
                body=initialize_message,
            )
        if first.status_code != 200:
            raise RuntimeError(f"MCP broker initialize failed for remote server `{server}` with HTTP {first.status_code}.")
        response = first.json()
        if not isinstance(response, dict) or "error" in response:
            raise RuntimeError(f"MCP broker initialize failed for remote server `{server}`.")
        session_id = str(first.headers.get("Mcp-Session-Id") or first.headers.get("mcp-session-id") or "").strip()
        protocol_version = str(first.headers.get("MCP-Protocol-Version") or first.headers.get("mcp-protocol-version") or "").strip()
        if not session_id or not protocol_version:
            raise RuntimeError(f"Remote MCP server `{server}` did not return negotiated session headers.")
        session = _RemoteSessionState(
            server=server,
            url=url,
            session_id=session_id,
            protocol_version=protocol_version,
            authorization=authorization,
        )
        self._http_request(
            "POST",
            session.url,
            headers={**self._session_headers(session), **self._authorization_headers(server_config, session.authorization)},
            body={"jsonrpc": JSONRPC_VERSION, "method": "notifications/initialized"},
        )
        return session

    def _list_remote_tools(self, session: _RemoteSessionState) -> set[str]:
        server_config = self._resolve_remote_server_config(session.server)
        response = self._remote_jsonrpc_request(
            session,
            {"jsonrpc": JSONRPC_VERSION, "id": new_id("mcp-tools-list"), "method": "tools/list", "params": {}},
            allow_reinitialize=True,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Remote MCP tools/list failed for server `{session.server}` with HTTP {response.status_code}.")
        body = response.json()
        result = dict(dict(body or {}).get("result") or {})
        return {
            str(item.get("name") or "").strip()
            for item in list(result.get("tools") or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }

    def _remote_jsonrpc_request(
        self,
        session: _RemoteSessionState,
        message: dict[str, Any],
        *,
        allow_reinitialize: bool,
    ) -> McpHttpResponse:
        server_config = self._resolve_remote_server_config(session.server)
        response = self._http_request(
            "POST",
            session.url,
            headers={**self._session_headers(session), **self._authorization_headers(server_config, session.authorization)},
            body=message,
        )
        if response.status_code in {400, 404} and allow_reinitialize:
            with self._remote_lock:
                self._remote_sessions.pop(session.server, None)
            refreshed = self._initialize_remote_session(session.server, server_config)
            refreshed.allowed_tools = set(session.allowed_tools)
            with self._remote_lock:
                self._remote_sessions[session.server] = refreshed
            session.session_id = refreshed.session_id
            session.protocol_version = refreshed.protocol_version
            session.authorization = dict(refreshed.authorization)
            response = self._http_request(
                "POST",
                session.url,
                headers={**self._session_headers(session), **self._authorization_headers(server_config, session.authorization)},
                body=message,
            )
        if response.status_code in {401, 403}:
            challenge = self._parse_www_authenticate(response.headers.get("WWW-Authenticate") or response.headers.get("www-authenticate") or "")
            if challenge:
                session.authorization = self._discover_remote_authorization(server_config, challenge_response=response)
                response = self._http_request(
                    "POST",
                    session.url,
                    headers={**self._session_headers(session), **self._authorization_headers(server_config, session.authorization)},
                    body=message,
                )
        return response

    def _discover_remote_authorization(
        self,
        server_config: dict[str, Any],
        *,
        challenge_response: McpHttpResponse,
    ) -> dict[str, Any]:
        url = str(server_config.get("url") or "").strip()
        challenge = self._parse_www_authenticate(challenge_response.headers.get("WWW-Authenticate") or challenge_response.headers.get("www-authenticate") or "")
        metadata = self._discover_protected_resource_metadata(url, challenge=challenge)
        metadata_url = str(metadata.get("metadata_url") or "").strip()
        authorization_servers = [str(item).strip() for item in list(metadata.get("authorization_servers") or []) if str(item).strip()]
        authorization_server_metadata = self._discover_authorization_server_metadata(authorization_servers[0]) if authorization_servers else {}
        required_scopes = _split_scopes(challenge.get("scope")) or _split_scopes(metadata.get("scopes_supported"))
        canonical_resource = _canonical_resource_uri(str(metadata.get("resource") or url))
        token = self._configured_bearer_token(server_config)
        token_claims = _decode_jwt_claims(token)
        validation = {
            "canonical_resource": canonical_resource,
            "required_scopes": required_scopes,
            "scopes_supported": _split_scopes(metadata.get("scopes_supported")),
            "token_jwt_claims_available": bool(token_claims),
        }
        if token_claims:
            token_audiences = {_canonical_resource_uri(item) for item in _claims_audiences(token_claims)}
            if canonical_resource and canonical_resource not in token_audiences:
                raise PermissionError(f"Remote MCP bearer token audience does not match resource `{canonical_resource}`.")
            token_scopes = set(_split_scopes(token_claims.get("scope")))
            required_scope_set = set(required_scopes)
            supported_scope_set = set(_split_scopes(metadata.get("scopes_supported")))
            if required_scope_set and not required_scope_set.issubset(token_scopes):
                raise PermissionError("Remote MCP bearer token is missing one or more required scopes.")
            if supported_scope_set and token_scopes and not token_scopes.issubset(supported_scope_set):
                raise PermissionError("Remote MCP bearer token carries scopes broader than the protected resource metadata allows.")
            validation["token_scopes"] = sorted(token_scopes)
        return {
            "resource_metadata_url": metadata_url,
            "resource": canonical_resource,
            "scopes_supported": _split_scopes(metadata.get("scopes_supported")),
            "required_scopes": required_scopes,
            "authorization_servers": authorization_servers,
            "authorization_server_metadata": authorization_server_metadata,
            "validation": validation,
        }

    def _discover_protected_resource_metadata(self, server_url: str, *, challenge: dict[str, str]) -> dict[str, Any]:
        candidates: list[str] = []
        challenge_metadata = str(challenge.get("resource_metadata") or "").strip()
        if challenge_metadata:
            candidates.append(challenge_metadata)
        candidates.extend(_protected_resource_metadata_candidates(server_url))
        seen: set[str] = set()
        for candidate in candidates:
            clean = str(candidate or "").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            response = self._http_request("GET", clean, headers={}, body=None)
            if response.status_code != 200:
                continue
            payload = response.json()
            if isinstance(payload, dict):
                return {
                    **payload,
                    "metadata_url": clean,
                }
        raise RuntimeError("Remote MCP authorization challenge did not expose a valid protected resource metadata document.")

    def _discover_authorization_server_metadata(self, issuer: str) -> dict[str, Any]:
        for candidate in _authorization_server_metadata_candidates(issuer):
            response = self._http_request("GET", candidate, headers={}, body=None)
            if response.status_code != 200:
                continue
            payload = response.json()
            if isinstance(payload, dict):
                return {"metadata_url": candidate, **payload}
        return {}

    def _remote_notifications(self, session: _RemoteSessionState) -> list[dict[str, Any]]:
        server_config = self._resolve_remote_server_config(session.server)
        response = self._http_request(
            "GET",
            session.url,
            headers={**self._session_headers(session), **self._authorization_headers(server_config, session.authorization)},
            body=None,
        )
        if response.status_code != 200:
            return []
        return _decode_sse_messages(response.body)

    def _configured_bearer_token(self, server_config: dict[str, Any]) -> str:
        env_name = str(server_config.get("bearer_token_env_var") or "").strip()
        if not env_name:
            raise PermissionError("Remote MCP authorization requires bearer_token_env_var in the server config.")
        token = str(os.environ.get(env_name) or "").strip()
        if not token:
            raise PermissionError(f"Remote MCP bearer token environment variable `{env_name}` is not set.")
        return token

    def _authorization_headers(self, server_config: dict[str, Any], authorization: dict[str, Any]) -> dict[str, str]:
        headers = {
            str(key): str(value)
            for key, value in dict(server_config.get("http_headers") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        for key, env_name in dict(server_config.get("env_http_headers") or {}).items():
            clean_name = str(env_name or "").strip()
            clean_value = str(os.environ.get(clean_name) or "").strip()
            if clean_name and clean_value:
                headers[str(key)] = clean_value
        if authorization:
            headers["Authorization"] = f"Bearer {self._configured_bearer_token(server_config)}"
        return headers

    @staticmethod
    def _json_headers() -> dict[str, str]:
        return {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    @staticmethod
    def _session_headers(session: _RemoteSessionState) -> dict[str, str]:
        return {
            **McpBrokerService._json_headers(),
            "Mcp-Session-Id": session.session_id,
            "MCP-Protocol-Version": session.protocol_version,
        }

    def _http_request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        body: bytes | str | dict[str, Any] | None,
    ) -> McpHttpResponse:
        transport = self.http_transport or self._default_http_transport
        return transport(str(method or "").upper(), url, headers, body)

    @staticmethod
    def _default_http_transport(
        method: str,
        url: str,
        headers: Mapping[str, str] | None,
        body: bytes | str | dict[str, Any] | None,
    ) -> McpHttpResponse:
        data: bytes | None = None
        if isinstance(body, bytes):
            data = body
        elif isinstance(body, str):
            data = body.encode("utf-8")
        elif isinstance(body, dict):
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method.upper())
        for key, value in dict(headers or {}).items():
            request.add_header(str(key), str(value))
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return McpHttpResponse(
                    status_code=int(response.status),
                    headers={str(key): str(value) for key, value in response.headers.items()},
                    body=response.read(),
                )
        except urllib.error.HTTPError as exc:
            return McpHttpResponse(
                status_code=int(exc.code),
                headers={str(key): str(value) for key, value in exc.headers.items()},
                body=exc.read(),
            )

    @staticmethod
    def _parse_www_authenticate(header_value: str) -> dict[str, str]:
        text = str(header_value or "").strip()
        if not text.lower().startswith("bearer"):
            return {}
        fields: dict[str, str] = {}
        for part in text[len("Bearer") :].split(","):
            key, _sep, value = str(part).strip().partition("=")
            clean_key = str(key or "").strip()
            clean_value = str(value or "").strip().strip('"')
            if clean_key:
                fields[clean_key] = clean_value
        return fields

    def _validate_remote_typed_result(self, payload: dict[str, Any]) -> None:
        typed_result = dict(payload.get("typed_result") or {})
        if typed_result:
            self._validate_remote_artifact_refs(list(typed_result.get("artifact_refs") or []), field_name="typed_result.artifact_refs")
            self._validate_remote_artifact_refs(list(typed_result.get("diagnostic_refs") or []), field_name="typed_result.diagnostic_refs")
        self._validate_remote_artifact_refs(list(payload.get("protocol_artifact_refs") or []), field_name="protocol_artifact_refs")
        self._validate_remote_artifact_refs(list(payload.get("diagnostic_refs") or []), field_name="diagnostic_refs")
        content_parts = list(payload.get("content_parts") or typed_result.get("content_parts") or [])
        for index, item in enumerate(content_parts, start=1):
            if not isinstance(item, dict):
                continue
            artifact = item.get("artifact")
            if isinstance(artifact, dict):
                self._validate_remote_artifact_ref(artifact, field_name=f"content_parts[{index}].artifact")

    def _validate_remote_artifact_refs(self, values: list[Any], *, field_name: str) -> None:
        for index, item in enumerate(values, start=1):
            if isinstance(item, dict):
                self._validate_remote_artifact_ref(item, field_name=f"{field_name}[{index}]")

    def _validate_remote_artifact_ref(self, payload: dict[str, Any], *, field_name: str) -> None:
        artifact_uri = str(payload.get("artifact_uri") or "").strip()
        if artifact_uri:
            parsed = urllib.parse.urlparse(artifact_uri)
        if not parsed.scheme or parsed.scheme.lower() == "file" or _looks_like_absolute_path(artifact_uri):
            raise ValueError(f"Remote MCP artifact reference `{field_name}` leaks a machine-local path.")
        metadata = dict(payload.get("metadata") or {})
        relative_path = str(metadata.get("relative_path") or "").strip()
        if relative_path and (_looks_like_absolute_path(relative_path) or ".." in relative_path.replace("\\", "/").split("/")):
            raise ValueError(f"Remote MCP artifact reference `{field_name}` carries an unsafe relative_path.")

    def _record_remote_operation(
        self,
        operation_id: str,
        *,
        server: str,
        tool: str,
        status: str,
        payload: dict[str, Any],
        external_handle: str | None = None,
    ) -> None:
        store = self._durable_store_for_workspace()
        if store is None:
            return
        run_id = self._ensure_remote_operation_run(store, server=server, tool=tool)
        store.record_external_operation(
            operation_id,
            run_id,
            kind=_REMOTE_OPERATION_KIND,
            classification=_REMOTE_OPERATION_CLASSIFICATION,
            status=status,
            external_handle=external_handle,
            payload=payload,
        )

    def _load_remote_durable_operation(self, operation_id: str) -> dict[str, Any] | None:
        store = self._durable_store_for_workspace()
        if store is None:
            return None
        operation = store.get_external_operation(operation_id)
        if operation is None:
            return None
        if str(operation.get("kind") or "").strip() != _REMOTE_OPERATION_KIND:
            return None
        return operation

    def _durable_store_for_workspace(self) -> DurableRunEventStore | None:
        workspace_root = self._workspace_root()
        if not workspace_root:
            return None
        if self._durable_store is not None and self._durable_store_workspace == workspace_root:
            return self._durable_store
        if self._durable_store is not None:
            self._durable_store.close()
        store = DurableRunEventStore(workspace_root)
        store.initialize()
        self._durable_store = store
        self._durable_store_workspace = workspace_root
        return store

    def _ensure_remote_operation_run(self, store: DurableRunEventStore, *, server: str, tool: str) -> str:
        run_id = f"mcp-remote:{server}:{tool}"
        existing = store.load_run(run_id, include_events=False)
        if existing is not None:
            return run_id
        timestamp = now_iso()
        store.create_run(
            {
                "schema_version": "astrabridge-task-graph-run-v1",
                "run_id": run_id,
                "graph_id": f"mcp.remote.{server}",
                "task_id": f"mcp.remote.{server}",
                "trace_id": f"trace-{run_id}",
                "status": "queued",
                "state_version": 0,
                "created_at": timestamp,
                "updated_at": timestamp,
                "artifact_refs": [],
                "event_refs": [],
                "node_run_states": [],
                "agent_envelopes": [],
                "run_policy_snapshot": {
                    "owner": "astrabridge_sidecar.mcp_broker_service",
                    "transport": "streamable_http",
                    "server": server,
                    "tool": tool,
                },
            },
            source="scheduler",
        )
        return run_id

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

    @staticmethod
    def _trace_context(internal_meta: dict[str, Any] | None) -> dict[str, Any]:
        trace_context = dict(dict(internal_meta or {}).get("astrabridge_trace") or {})
        if not trace_context:
            trace_context = dict(dict(internal_meta or {}).get("astrabridge_mcp_policy_context") or {})
        return trace_context

    @staticmethod
    def _durable_authorization_snapshot(authorization: dict[str, Any]) -> dict[str, Any]:
        if not authorization:
            return {}
        return {
            "resource_metadata_url": str(authorization.get("resource_metadata_url") or "").strip() or None,
            "resource": str(authorization.get("resource") or "").strip() or None,
            "required_scopes": list(authorization.get("required_scopes") or []),
            "scopes_supported": list(authorization.get("scopes_supported") or []),
            "authorization_servers": list(authorization.get("authorization_servers") or []),
            "authorization_server_metadata_url": str(dict(authorization.get("authorization_server_metadata") or {}).get("metadata_url") or "").strip() or None,
            "validation": dict(authorization.get("validation") or {}),
        }


def _request_fingerprint(server: str, tool: str, arguments: dict[str, Any], *, caller: str) -> str:
    payload = {
        "server": str(server or "").strip(),
        "tool": str(tool or "").strip(),
        "caller": str(caller or "").strip() or "internal",
        "arguments": dict(arguments or {}),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _protected_resource_metadata_candidates(server_url: str) -> list[str]:
    parsed = urllib.parse.urlparse(server_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    endpoint_path = parsed.path.strip("/")
    candidates: list[str] = []
    if endpoint_path:
        candidates.append(f"{base}/.well-known/oauth-protected-resource/{endpoint_path}")
    candidates.append(f"{base}/.well-known/oauth-protected-resource")
    return candidates


def _authorization_server_metadata_candidates(issuer: str) -> list[str]:
    parsed = urllib.parse.urlparse(str(issuer or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return []
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.strip("/")
    if path:
        return [
            f"{base}/.well-known/oauth-authorization-server/{path}",
            f"{base}/.well-known/openid-configuration/{path}",
            f"{base}/{path}/.well-known/openid-configuration",
        ]
    return [
        f"{base}/.well-known/oauth-authorization-server",
        f"{base}/.well-known/openid-configuration",
    ]


def _canonical_resource_uri(value: str) -> str:
    parsed = urllib.parse.urlparse(str(value or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    if not host:
        return ""
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or ""
    if path == "/":
        path = ""
    return urllib.parse.urlunparse((scheme, f"{host}{port}", path, "", "", ""))


def _claims_audiences(claims: dict[str, Any]) -> list[str]:
    aud = claims.get("aud")
    if isinstance(aud, list):
        return [str(item).strip() for item in aud if str(item).strip()]
    clean = str(aud or claims.get("resource") or "").strip()
    return [clean] if clean else []


def _split_scopes(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [item for item in text.replace(",", " ").split() if item]


def _decode_jwt_claims(token: str) -> dict[str, Any]:
    parts = str(token or "").split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
        value = json.loads(decoded.decode("utf-8"))
    except Exception:
        return {}
    return dict(value) if isinstance(value, dict) else {}


def _decode_sse_messages(body: bytes) -> list[dict[str, Any]]:
    text = body.decode("utf-8", errors="replace")
    messages: list[dict[str, Any]] = []
    for block in text.split("\n\n"):
        data_lines = [line[5:].lstrip() for line in block.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        payload_text = "\n".join(data_lines).strip()
        if not payload_text:
            continue
        try:
            payload = json.loads(payload_text)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            messages.append(payload)
    return messages


def _looks_like_absolute_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if text.startswith(("/", "\\")):
        return True
    return len(text) > 2 and text[1] == ":" and text[0].isalpha()


def _coerce_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
