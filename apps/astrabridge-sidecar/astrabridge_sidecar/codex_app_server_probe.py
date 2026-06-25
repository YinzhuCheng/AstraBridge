from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from .app_server_client import JsonRpcError
from .common import app_runtime_dir, new_id, now_iso, write_json
from .security import redact_sensitive


NotificationHandler = Callable[[str, Any], None]
ServerRequestHandler = Callable[[str, Any], Any]


class ProbeClient(Protocol):
    def start(self) -> None: ...
    def close(self) -> None: ...
    def request(self, method: str, params: Any | None = None, timeout: float = 120.0) -> Any: ...


ProbeClientFactory = Callable[[NotificationHandler, ServerRequestHandler], ProbeClient]


def probe_app_server_protocol(
    *,
    client_factory: ProbeClientFactory,
    artifact_root: Path | None = None,
    cwd: str | None = None,
    request_timeout: float = 20.0,
) -> dict[str, Any]:
    probe_id = new_id("codex-app-server-probe")
    generated_at = now_iso()
    artifact_dir = (artifact_root or app_runtime_dir("kernel-probes")).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / f"{probe_id}.json"
    notifications_seen: list[str] = []
    server_requests_seen: list[str] = []
    warnings: list[str] = []
    request_sequence: list[str] = []
    turn_error: dict[str, Any] | None = None
    thread_resume_error: dict[str, Any] | None = None
    thread_id: str | None = None

    status = {
        "start_status": "not_checked",
        "initialize_status": "not_checked",
        "thread_start_status": "not_checked",
        "thread_resume_status": "not_checked",
        "turn_start_status": "not_checked",
        "approval_events_status": "not_observed",
        "mcp_elicitation_status": "not_observed",
        "thread_resume_error_shape_status": "not_observed",
        "turn_error_shape_status": "not_observed",
    }

    def on_notification(method: str, params: Any) -> None:
        name = str(method or "").strip()
        if not name:
            return
        notifications_seen.append(name)
        if name == "runtime/server_request":
            request_method = ""
            if isinstance(params, dict):
                request_method = str(params.get("method") or "").strip()
            if request_method:
                server_requests_seen.append(request_method)
                lowered = request_method.lower()
                if "approval" in lowered or "permission" in lowered:
                    status["approval_events_status"] = "observed"
                if lowered.startswith("mcpserver/") or "mcp" in lowered:
                    status["mcp_elicitation_status"] = "observed"
        elif "approval" in name.lower() or "guardian" in name.lower():
            status["approval_events_status"] = "observed"
        elif name.startswith("mcpServer/") or "mcpToolCall" in name:
            status["mcp_elicitation_status"] = "observed"

    def on_server_request(method: str, params: Any) -> Any:
        del params
        lowered = str(method or "").strip().lower()
        if "approval" in lowered or "permission" in lowered:
            return {"decision": "decline", "reason": "AstraBridge protocol probe does not auto-approve actions."}
        return {}

    client = client_factory(on_notification, on_server_request)
    try:
        client.start()
        status["start_status"] = "supported"
        status["initialize_status"] = "supported"

        request_sequence.append("thread/start")
        thread_start = client.request("thread/start", _thread_start_params(cwd), timeout=request_timeout)
        thread_id = _thread_id_from_response(thread_start)
        if not thread_id:
            status["thread_start_status"] = "incompatible_response"
            warnings.append("thread/start returned a response without thread id.")
        else:
            status["thread_start_status"] = "supported"

        if thread_id:
            request_sequence.append("turn/start")
            try:
                client.request("turn/start", _turn_start_params(thread_id), timeout=request_timeout)
                status["turn_start_status"] = "supported"
            except TimeoutError:
                status["turn_start_status"] = "timeout"
                warnings.append("turn/start timed out before a response was observed.")
            except JsonRpcError as exc:
                status["turn_start_status"] = _jsonrpc_probe_status(exc)
                status["turn_error_shape_status"] = "jsonrpc_error"
                turn_error = _jsonrpc_error_payload(exc)
            except Exception as exc:  # noqa: BLE001
                status["turn_start_status"] = "error"
                status["turn_error_shape_status"] = "runtime_error"
                turn_error = {"message": str(exc)[:300]}

            request_sequence.append("thread/resume")
            try:
                thread_resume = client.request("thread/resume", {"threadId": thread_id}, timeout=request_timeout)
                if _thread_id_from_response(thread_resume):
                    status["thread_resume_status"] = "supported"
                else:
                    status["thread_resume_status"] = "incompatible_response"
                    warnings.append("thread/resume returned a response without thread id.")
            except TimeoutError:
                status["thread_resume_status"] = "timeout"
                warnings.append("thread/resume timed out during independent resume diagnostics.")
            except JsonRpcError as exc:
                status["thread_resume_status"] = _jsonrpc_probe_status(exc)
                status["thread_resume_error_shape_status"] = "jsonrpc_error"
                thread_resume_error = _jsonrpc_error_payload(exc)
                warnings.append("thread/resume failed during independent resume diagnostics; fresh turn probe was still exercised.")
            except Exception as exc:  # noqa: BLE001
                status["thread_resume_status"] = "error"
                status["thread_resume_error_shape_status"] = "runtime_error"
                thread_resume_error = {"message": str(exc)[:300]}
                warnings.append("thread/resume raised during independent resume diagnostics; fresh turn probe was still exercised.")
        else:
            status["thread_resume_status"] = "skipped"
            status["turn_start_status"] = "skipped"
    except TimeoutError as exc:
        message = str(exc)
        if status["start_status"] == "not_checked":
            status["start_status"] = "timeout"
            status["initialize_status"] = "timeout"
        elif request_sequence and request_sequence[-1] == "thread/start":
            status["thread_start_status"] = "timeout"
            status["thread_resume_status"] = "skipped"
            status["turn_start_status"] = "skipped"
        elif request_sequence and request_sequence[-1] == "turn/start":
            status["turn_start_status"] = "timeout"
        elif request_sequence and request_sequence[-1] == "thread/resume":
            status["thread_resume_status"] = "timeout"
        warnings.append(message[:300])
    except JsonRpcError as exc:
        probe_status = _jsonrpc_probe_status(exc)
        if status["start_status"] == "not_checked":
            status["start_status"] = probe_status
            status["initialize_status"] = probe_status
        elif request_sequence and request_sequence[-1] == "thread/start":
            status["thread_start_status"] = probe_status
            status["thread_resume_status"] = "skipped"
            status["turn_start_status"] = "skipped"
        elif request_sequence and request_sequence[-1] == "turn/start":
            status["turn_start_status"] = probe_status
            turn_error = _jsonrpc_error_payload(exc)
            status["turn_error_shape_status"] = "jsonrpc_error"
        elif request_sequence and request_sequence[-1] == "thread/resume":
            status["thread_resume_status"] = probe_status
            thread_resume_error = _jsonrpc_error_payload(exc)
            status["thread_resume_error_shape_status"] = "jsonrpc_error"
        else:
            turn_error = _jsonrpc_error_payload(exc)
            status["turn_error_shape_status"] = "jsonrpc_error"
    except Exception as exc:  # noqa: BLE001
        if status["start_status"] == "not_checked":
            status["start_status"] = "error"
            status["initialize_status"] = "error"
        elif request_sequence and request_sequence[-1] == "thread/start":
            status["thread_start_status"] = "error"
            status["thread_resume_status"] = "skipped"
            status["turn_start_status"] = "skipped"
        elif request_sequence and request_sequence[-1] == "turn/start":
            status["turn_start_status"] = "error"
        elif request_sequence and request_sequence[-1] == "thread/resume":
            status["thread_resume_status"] = "error"
        warnings.append(str(exc)[:300])
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass

    report = {
        "schema_version": "codex-app-server-probe-v1",
        "generated_at": generated_at,
        "probe_id": probe_id,
        "report_path": str(report_path),
        "app_server": {
            **status,
            "thread_id_observed": thread_id,
            "notifications_seen": sorted(set(notifications_seen)),
            "server_requests_seen": sorted(set(server_requests_seen)),
            "request_sequence": request_sequence,
            "thread_resume_error": thread_resume_error,
            "turn_error": turn_error,
        },
        "known_warnings": warnings,
    }
    sanitized = redact_sensitive(report)
    write_json(report_path, sanitized)
    return sanitized


def _thread_start_params(cwd: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ephemeral": True,
        "threadSource": "user",
        "sessionStartSource": "startup",
    }
    if cwd:
        payload["cwd"] = cwd
    return payload


def _turn_start_params(thread_id: str) -> dict[str, Any]:
    return {
        "threadId": thread_id,
        "approvalPolicy": "never",
        "input": [
            {
                "type": "text",
                "text": "AstraBridge app-server protocol probe. Reply with OK.",
                "text_elements": [],
            }
        ],
    }


def _thread_id_from_response(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    thread = payload.get("thread")
    if isinstance(thread, dict):
        thread_id = str(thread.get("id") or "").strip()
        if thread_id:
            return thread_id
    thread_id = str(payload.get("threadId") or payload.get("thread_id") or "").strip()
    return thread_id or None


def _jsonrpc_probe_status(exc: JsonRpcError) -> str:
    if int(exc.code or 0) == -32601:
        return "incompatible_response"
    return "error_response"


def _jsonrpc_error_payload(exc: JsonRpcError) -> dict[str, Any]:
    return {
        "code": exc.code,
        "message": str(exc)[:300],
        "data": redact_sensitive(exc.data),
    }
