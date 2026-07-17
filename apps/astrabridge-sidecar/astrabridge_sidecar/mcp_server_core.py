from __future__ import annotations

import json
import re
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Callable, Mapping


MCP_LATEST_PROTOCOL_VERSION = "2025-11-25"
MCP_SUPPORTED_PROTOCOL_VERSIONS = (MCP_LATEST_PROTOCOL_VERSION, "2024-11-05")
JSONRPC_VERSION = "2.0"

_STDIO_HEADER_FRAMING = "header"
_STDIO_RAW_FRAMING = "raw"
_MAX_LOG_FIELD_CHARS = 500

_REDACTION_PATTERNS = (
    (re.compile(r"(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]+"), "Authorization: [REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key|token|secret|cookie)\s*[:=]\s*[A-Za-z0-9._~+/=-]{8,}"), r"\1=[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "sk-[REDACTED]"),
)

McpToolHandler = Callable[[str, dict[str, Any], "McpToolCallContext"], dict[str, Any]]
McpListProvider = Callable[[], list[dict[str, Any]]]
McpLogHook = Callable[..., None]


def _empty_items() -> list[dict[str, Any]]:
    return []


def _redact_log_text(text: str) -> str:
    redacted = str(text or "")
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    redacted = re.sub(r"\s+", " ", redacted).strip()
    return redacted[:_MAX_LOG_FIELD_CHARS]


def _sanitize_log_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        return _redact_log_text(value.decode("utf-8", errors="replace"))
    if isinstance(value, str):
        return _redact_log_text(value)
    try:
        return _redact_log_text(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError):
        return _redact_log_text(repr(value))


def emit_mcp_log(log_hook: McpLogHook | None, event: str, **fields: Any) -> None:
    if log_hook is None:
        return
    sanitized = {key: _sanitize_log_value(value) for key, value in fields.items()}
    try:
        log_hook(event, **sanitized)
    except Exception:
        pass


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": {"code": code, "message": message}}


def _read_first_nonempty_byte(stream: BinaryIO) -> bytes:
    while True:
        chunk = stream.read(1)
        if not chunk:
            return b""
        if chunk in b" \t\r\n":
            continue
        return chunk


def _read_json_object(stream: BinaryIO, first: bytes) -> bytes:
    buffer = bytearray(first)
    depth = 1
    in_string = False
    escaped = False
    while depth > 0:
        chunk = stream.read(1)
        if not chunk:
            break
        char = chunk[0]
        buffer.extend(chunk)
        if in_string:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                in_string = False
            continue
        if char == 34:
            in_string = True
        elif char == 123:
            depth += 1
        elif char == 125:
            depth -= 1
    return bytes(buffer)


@dataclass
class McpStdioFramingState:
    output_framing: str = _STDIO_HEADER_FRAMING


def read_stdio_message(
    stream: BinaryIO,
    *,
    state: McpStdioFramingState,
    log_hook: McpLogHook | None = None,
) -> dict[str, Any] | None:
    first = _read_first_nonempty_byte(stream)
    if not first:
        return None
    if first == b"{":
        state.output_framing = _STDIO_RAW_FRAMING
        payload_text = _read_json_object(stream, first).decode("utf-8")
    else:
        state.output_framing = _STDIO_HEADER_FRAMING
        headers: dict[str, str] = {}
        line = first + stream.readline()
        while line and line.strip():
            decoded = line.decode("ascii", errors="replace")
            key, _sep, value = decoded.partition(":")
            if key:
                headers[key.lower()] = value.strip()
            line = stream.readline()
        length = int(headers.get("content-length") or 0)
        if length <= 0:
            return None
        payload_text = stream.read(length).decode("utf-8")
    message = json.loads(payload_text)
    if not isinstance(message, dict):
        raise ValueError("MCP message must be a JSON object.")
    if not message.get("method"):
        emit_mcp_log(log_hook, "methodless_message", keys=sorted(message.keys()), raw=payload_text)
    return message


def write_stdio_message(stream: BinaryIO, payload: dict[str, Any], *, state: McpStdioFramingState) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if state.output_framing == _STDIO_RAW_FRAMING:
        stream.write(encoded + b"\n")
        stream.flush()
        return
    header = f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii")
    stream.write(header)
    stream.write(encoded)
    stream.flush()


@dataclass
class McpToolCallContext:
    request_id: Any
    session_id: str | None = None
    progress_token: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    notification_sink: Callable[[dict[str, Any]], None] | None = None

    def emit_notification(self, method: str, params: Mapping[str, Any] | None = None) -> bool:
        if self.notification_sink is None:
            return False
        message: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": str(method or "")}
        if params is not None:
            message["params"] = dict(params)
        self.notification_sink(message)
        return True

    def emit_progress(self, progress: int | float, *, total: int | float | None = None, message: str | None = None) -> bool:
        if self.progress_token in {None, ""}:
            return False
        params: dict[str, Any] = {"progressToken": self.progress_token, "progress": progress}
        if total is not None:
            params["total"] = total
        if message:
            params["message"] = str(message)
        return self.emit_notification("notifications/progress", params)


@dataclass
class McpServerCore:
    server_name: str
    server_version: str
    instructions: str
    tools_provider: McpListProvider
    tool_handler: McpToolHandler
    capabilities: dict[str, Any] = field(default_factory=lambda: {"tools": {}})
    resources_provider: McpListProvider = _empty_items
    resource_templates_provider: McpListProvider = _empty_items
    supported_protocol_versions: tuple[str, ...] = MCP_SUPPORTED_PROTOCOL_VERSIONS
    tool_call_timeout_sec: float | None = None
    log_hook: McpLogHook | None = None
    _cancel_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _cancel_events: dict[str, threading.Event] = field(default_factory=dict, init=False, repr=False)

    def negotiate_protocol_version(self, requested_version: str | None) -> str:
        candidate = str(requested_version or "").strip()
        if candidate and candidate in self.supported_protocol_versions:
            return candidate
        return self.supported_protocol_versions[0]

    def handle_message(
        self,
        message: dict[str, Any] | Any,
        *,
        notification_sink: Callable[[dict[str, Any]], None] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return _jsonrpc_error(None, -32600, "Invalid Request")
        request_id = message.get("id")
        has_id = "id" in message
        method = message.get("method")
        if not isinstance(method, str) or not method.strip():
            return None if not has_id else _jsonrpc_error(request_id, -32600, "Invalid Request")
        params = message.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return None if not has_id else _jsonrpc_error(request_id, -32602, "Params must be an object.")
        if message.get("jsonrpc") not in {None, JSONRPC_VERSION}:
            return None if not has_id else _jsonrpc_error(request_id, -32600, "Unsupported JSON-RPC version.")
        try:
            if method == "initialize":
                negotiated = self.negotiate_protocol_version(str(params.get("protocolVersion") or ""))
                return _jsonrpc_result(
                    request_id,
                    {
                        "protocolVersion": negotiated,
                        "capabilities": dict(self.capabilities),
                        "serverInfo": {"name": self.server_name, "version": self.server_version},
                        "instructions": self.instructions,
                    },
                )
            if method in {"notifications/initialized", "initialized"}:
                return None
            if method == "notifications/cancelled":
                self._cancel_request(params.get("requestId"))
                emit_mcp_log(self.log_hook, "cancelled", request_id=params.get("requestId"), session_id=session_id, reason=params.get("reason"))
                return None
            if method == "ping":
                return None if not has_id else _jsonrpc_result(request_id, {})
            if method == "tools/list":
                return None if not has_id else _jsonrpc_result(request_id, {"tools": [dict(item) for item in self.tools_provider()]})
            if method == "resources/list":
                return None if not has_id else _jsonrpc_result(request_id, {"resources": [dict(item) for item in self.resources_provider()]})
            if method == "resources/templates/list":
                templates = [dict(item) for item in self.resource_templates_provider()]
                return None if not has_id else _jsonrpc_result(request_id, {"resourceTemplates": templates})
            if method == "tools/call":
                if not has_id:
                    return None
                result = self._handle_tool_call(
                    request_id,
                    params,
                    notification_sink=notification_sink,
                    session_id=session_id,
                )
                return None if result is None else _jsonrpc_result(request_id, result)
            if not has_id:
                return None
            return _jsonrpc_error(request_id, -32601, f"Unsupported method: {method}")
        except Exception as exc:  # noqa: BLE001
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            emit_mcp_log(self.log_hook, "handler_error", method=method, error=detail)
            return _jsonrpc_error(request_id, -32000, detail)

    def _handle_tool_call(
        self,
        request_id: Any,
        params: dict[str, Any],
        *,
        notification_sink: Callable[[dict[str, Any]], None] | None,
        session_id: str | None,
    ) -> dict[str, Any] | None:
        name = str(params.get("name") or "").strip()
        if not name:
            raise ValueError("Tool name is required.")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object.")
        meta = params.get("_meta") or {}
        if not isinstance(meta, dict):
            meta = {}
        cancel_event = threading.Event()
        context = McpToolCallContext(
            request_id=request_id,
            session_id=session_id,
            progress_token=meta.get("progressToken"),
            meta=dict(meta),
            cancel_event=cancel_event,
            notification_sink=notification_sink,
        )
        cancel_key = self._request_key(request_id)
        with self._cancel_lock:
            self._cancel_events[cancel_key] = cancel_event
        try:
            result = self._invoke_tool_handler(name, arguments, context)
            if cancel_event.is_set():
                emit_mcp_log(self.log_hook, "tool_call_cancelled", request_id=request_id, tool=name, session_id=session_id)
                return None
            if not isinstance(result, dict):
                raise TypeError("Tool result must be an object.")
            return result
        finally:
            with self._cancel_lock:
                self._cancel_events.pop(cancel_key, None)

    def _invoke_tool_handler(self, name: str, arguments: dict[str, Any], context: McpToolCallContext) -> dict[str, Any]:
        timeout_sec = self.tool_call_timeout_sec
        if timeout_sec is None or timeout_sec <= 0:
            return self.tool_handler(name, arguments, context)
        result_holder: dict[str, Any] = {}
        error_holder: dict[str, Exception] = {}
        done = threading.Event()

        def _worker() -> None:
            try:
                result_holder["result"] = self.tool_handler(name, arguments, context)
            except Exception as exc:  # noqa: BLE001
                error_holder["error"] = exc
            finally:
                done.set()

        thread = threading.Thread(target=_worker, name=f"mcp-tool-{name}", daemon=True)
        thread.start()
        if not done.wait(timeout_sec):
            context.cancel_event.set()
            raise TimeoutError(f"Tool call timed out after {timeout_sec:g} seconds.")
        if "error" in error_holder:
            raise error_holder["error"]
        return result_holder.get("result") or {}

    def _cancel_request(self, request_id: Any) -> None:
        cancel_key = self._request_key(request_id)
        with self._cancel_lock:
            cancel_event = self._cancel_events.get(cancel_key)
        if cancel_event is not None:
            cancel_event.set()

    @staticmethod
    def _request_key(request_id: Any) -> str:
        try:
            return json.dumps(request_id, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            return repr(request_id)


def run_stdio_mcp_server(
    core: McpServerCore,
    stdin: BinaryIO,
    stdout: BinaryIO,
    *,
    state: McpStdioFramingState | None = None,
    log_hook: McpLogHook | None = None,
) -> None:
    framing = state or McpStdioFramingState()
    write_lock = threading.Lock()

    def _notification_sink(message: dict[str, Any]) -> None:
        with write_lock:
            write_stdio_message(stdout, message, state=framing)

    while True:
        try:
            message = read_stdio_message(stdin, state=framing, log_hook=log_hook)
        except json.JSONDecodeError as exc:
            emit_mcp_log(log_hook, "parse_error", error=str(exc))
            with write_lock:
                write_stdio_message(stdout, _jsonrpc_error(None, -32700, "Parse error"), state=framing)
            continue
        if message is None:
            emit_mcp_log(log_hook, "eof")
            break
        emit_mcp_log(log_hook, "received", method=message.get("method"), has_id="id" in message)
        response = core.handle_message(message, notification_sink=_notification_sink)
        if response is not None:
            emit_mcp_log(log_hook, "responding", has_error="error" in response)
            with write_lock:
                write_stdio_message(stdout, response, state=framing)


@dataclass
class LoopbackMcpSession:
    core: McpServerCore
    session_id: str | None = None
    notifications: list[dict[str, Any]] = field(default_factory=list)

    def request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        return self.core.handle_message(message, notification_sink=self.notifications.append, session_id=self.session_id)

    def drain_notifications(self) -> list[dict[str, Any]]:
        items = list(self.notifications)
        self.notifications.clear()
        return items


@dataclass
class McpHttpResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def json(self) -> dict[str, Any] | None:
        if not self.body:
            return None
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@dataclass
class _StreamableHttpSession:
    session_id: str
    protocol_version: str
    notifications: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StreamableHttpMcpServer:
    core: McpServerCore
    _sessions: dict[str, _StreamableHttpSession] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def handle_request(
        self,
        method: str,
        *,
        headers: Mapping[str, str] | None = None,
        body: bytes | str | dict[str, Any] | None = None,
    ) -> McpHttpResponse:
        normalized_headers = {str(key).lower(): str(value).strip() for key, value in dict(headers or {}).items()}
        method_name = str(method or "").upper()
        if method_name == "POST":
            return self._handle_post(normalized_headers, body)
        if method_name == "GET":
            return self._handle_get(normalized_headers)
        if method_name == "DELETE":
            return self._handle_delete(normalized_headers)
        return self._json_response(405, {"error": {"code": -32601, "message": f"Unsupported HTTP method: {method_name}"}})

    def _handle_post(self, headers: dict[str, str], body: bytes | str | dict[str, Any] | None) -> McpHttpResponse:
        try:
            message = self._decode_body(body)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return self._json_response(400, _jsonrpc_error(None, -32700, f"Parse error: {exc}"))
        method = str(message.get("method") or "")
        if method == "initialize":
            response = self.core.handle_message(message)
            if response is None:
                return McpHttpResponse(status_code=202, headers={"Cache-Control": "no-store"})
            negotiated = str(dict(response.get("result") or {}).get("protocolVersion") or MCP_LATEST_PROTOCOL_VERSION)
            session_id = uuid.uuid4().hex
            with self._lock:
                self._sessions[session_id] = _StreamableHttpSession(session_id=session_id, protocol_version=negotiated)
            return self._json_response(
                200,
                response,
                extra_headers={
                    "Cache-Control": "no-store",
                    "Mcp-Session-Id": session_id,
                    "MCP-Protocol-Version": negotiated,
                },
            )
        session = self._require_session(headers)
        if isinstance(session, McpHttpResponse):
            return session

        def _queue_notification(notification: dict[str, Any]) -> None:
            with self._lock:
                live_session = self._sessions.get(session.session_id)
                if live_session is not None:
                    live_session.notifications.append(dict(notification))

        response = self.core.handle_message(message, notification_sink=_queue_notification, session_id=session.session_id)
        base_headers = {
            "Cache-Control": "no-store",
            "Mcp-Session-Id": session.session_id,
            "MCP-Protocol-Version": session.protocol_version,
        }
        if response is None:
            return McpHttpResponse(status_code=202, headers=base_headers)
        return self._json_response(200, response, extra_headers=base_headers)

    def _handle_get(self, headers: dict[str, str]) -> McpHttpResponse:
        session = self._require_session(headers)
        if isinstance(session, McpHttpResponse):
            return session
        with self._lock:
            notifications = list(session.notifications)
            session.notifications.clear()
        payload = self._encode_sse_messages(notifications)
        return McpHttpResponse(
            status_code=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-store",
                "Mcp-Session-Id": session.session_id,
                "MCP-Protocol-Version": session.protocol_version,
            },
            body=payload,
        )

    def _handle_delete(self, headers: dict[str, str]) -> McpHttpResponse:
        session_id = str(headers.get("mcp-session-id") or "").strip()
        if not session_id:
            return self._json_response(400, {"error": {"message": "Missing Mcp-Session-Id header."}})
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return self._json_response(404, {"error": {"message": "Unknown MCP session."}})
        return McpHttpResponse(
            status_code=204,
            headers={
                "Cache-Control": "no-store",
                "Mcp-Session-Id": session.session_id,
                "MCP-Protocol-Version": session.protocol_version,
            },
        )

    def _require_session(self, headers: dict[str, str]) -> _StreamableHttpSession | McpHttpResponse:
        session_id = str(headers.get("mcp-session-id") or "").strip()
        if not session_id:
            return self._json_response(400, {"error": {"message": "Missing Mcp-Session-Id header."}})
        protocol_version = str(headers.get("mcp-protocol-version") or "").strip()
        if not protocol_version:
            return self._json_response(400, {"error": {"message": "Missing MCP-Protocol-Version header."}})
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            return self._json_response(404, {"error": {"message": "Unknown MCP session."}})
        if protocol_version != session.protocol_version:
            return self._json_response(400, {"error": {"message": "MCP-Protocol-Version does not match the negotiated session version."}})
        return session

    @staticmethod
    def _decode_body(body: bytes | str | dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(body, dict):
            return dict(body)
        if isinstance(body, bytes):
            return json.loads(body.decode("utf-8"))
        if isinstance(body, str):
            return json.loads(body)
        raise TypeError("HTTP POST body is required.")

    @staticmethod
    def _encode_sse_messages(messages: list[dict[str, Any]]) -> bytes:
        parts: list[str] = []
        for message in messages:
            payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            parts.append(f"event: message\ndata: {payload}\n\n")
        return "".join(parts).encode("utf-8")

    @staticmethod
    def _json_response(status_code: int, payload: dict[str, Any], *, extra_headers: Mapping[str, str] | None = None) -> McpHttpResponse:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update({str(key): str(value) for key, value in extra_headers.items()})
        return McpHttpResponse(status_code=status_code, headers=headers, body=body)
