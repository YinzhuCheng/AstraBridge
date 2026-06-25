from __future__ import annotations

import datetime as dt
import shutil
import tomllib
from pathlib import Path
from typing import Any

from .app_server_client import JsonRpcError
from .codex_app_server_probe import ProbeClientFactory
from .common import app_runtime_dir, new_id, now_iso, write_json
from .security import redact_sensitive


def probe_mcp_compatibility(
    *,
    codex_home: Path,
    mcp_config: dict[str, Any] | None = None,
    client_factory: ProbeClientFactory | None = None,
    artifact_root: Path | None = None,
    request_timeout: float = 20.0,
) -> dict[str, Any]:
    probe_id = new_id("codex-mcp-probe")
    generated_at = now_iso()
    artifact_dir = (artifact_root or app_runtime_dir("kernel-probes")).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / f"{probe_id}.json"
    config_path = Path(codex_home).resolve() / "config.toml"
    warnings: list[str] = []

    status = {
        "config_file_status": "missing",
        "config_render_status": "error",
        "config_schema_status": "not_checked",
        "server_command_probe_status": "not_checked",
        "reload_status": "not_checked",
        "server_status_list_status": "not_checked",
        "config_visibility_status": "not_checked",
    }

    parsed_config: dict[str, Any] = {}
    if config_path.exists():
        try:
            parsed_config = tomllib.loads(config_path.read_text(encoding="utf-8"))
            status["config_file_status"] = "present"
            status["config_render_status"] = "supported"
        except tomllib.TOMLDecodeError as exc:
            status["config_file_status"] = "malformed"
            warnings.append(f"Rendered CODEX_HOME config.toml is malformed: {str(exc)[:200]}")
    else:
        warnings.append("Rendered CODEX_HOME config.toml is missing.")

    rendered_specs = _rendered_server_specs(parsed_config)
    configured_specs = _configured_server_specs(mcp_config, rendered_specs)
    schema_diagnostics = _config_schema_diagnostics(parsed_config, configured_specs)
    status["config_schema_status"] = schema_diagnostics["status"]
    warnings.extend(schema_diagnostics["warnings"])
    launch_diagnostics = _server_launch_diagnostics(configured_specs)
    status["server_command_probe_status"] = _server_command_probe_status(launch_diagnostics)
    rendered_server_names = sorted(rendered_specs)
    expected_server_names = sorted(configured_specs)
    if expected_server_names and status["config_file_status"] == "present":
        missing_sections = sorted(set(expected_server_names) - set(rendered_server_names))
        if missing_sections:
            warnings.append(f"Rendered config.toml is missing expected MCP server sections: {', '.join(missing_sections)}")

    visible_records: list[dict[str, Any]] = []
    visible_server_names: list[str] = []
    visible_tools: list[str] = []
    request_sequence: list[str] = []
    startup_notifications: list[dict[str, Any]] = []
    status_thread_id: str | None = None
    if status["config_file_status"] == "present" and client_factory is not None:
        client = client_factory(
            lambda method, params: _record_mcp_notification(startup_notifications, method, params),
            lambda method, params: {},
        )
        try:
            client.start()
            try:
                request_sequence.append("config/mcpServer/reload")
                client.request("config/mcpServer/reload", None, timeout=request_timeout)
                status["reload_status"] = "supported"
            except TimeoutError:
                status["reload_status"] = "timeout"
                warnings.append("config/mcpServer/reload timed out.")
            except JsonRpcError as exc:
                status["reload_status"] = _jsonrpc_probe_status(exc)
                warnings.append(f"config/mcpServer/reload returned JSON-RPC error code {exc.code}.")
            except Exception as exc:  # noqa: BLE001
                status["reload_status"] = "error"
                warnings.append(f"config/mcpServer/reload failed: {str(exc)[:200]}")

            try:
                request_sequence.append("thread/start")
                thread_start = client.request("thread/start", _status_thread_start_params(), timeout=request_timeout)
                status_thread_id = _thread_id_from_response(thread_start)
                if not status_thread_id:
                    warnings.append("thread/start for MCP status returned no thread id; mcpServerStatus/list will be queried without threadId.")
            except TimeoutError:
                warnings.append("thread/start for MCP status timed out; mcpServerStatus/list will be queried without threadId.")
            except JsonRpcError as exc:
                warnings.append(f"thread/start for MCP status returned JSON-RPC error code {exc.code}; mcpServerStatus/list will be queried without threadId.")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"thread/start for MCP status failed: {str(exc)[:200]}")

            try:
                request_sequence.append("mcpServerStatus/list")
                status_params: dict[str, Any] = {"detail": "toolsAndAuthOnly"}
                if status_thread_id:
                    status_params["threadId"] = status_thread_id
                result = client.request(
                    "mcpServerStatus/list",
                    status_params,
                    timeout=request_timeout,
                )
                parsed_visible_records = _visible_records_from_status_result(result)
                if parsed_visible_records is not None:
                    status["server_status_list_status"] = "supported"
                    visible_records = parsed_visible_records
                    visible_server_names = sorted(record["name"] for record in visible_records if record["name"])
                    visible_tools = sorted({tool for record in visible_records for tool in record["visible_tool_names"]})
                else:
                    status["server_status_list_status"] = "incompatible_response"
                    warnings.append("mcpServerStatus/list returned an incompatible response shape.")
            except TimeoutError:
                status["server_status_list_status"] = "timeout"
                warnings.append("mcpServerStatus/list timed out.")
            except JsonRpcError as exc:
                status["server_status_list_status"] = _jsonrpc_probe_status(exc)
                warnings.append(f"mcpServerStatus/list returned JSON-RPC error code {exc.code}.")
            except Exception as exc:  # noqa: BLE001
                status["server_status_list_status"] = "error"
                warnings.append(f"mcpServerStatus/list failed: {str(exc)[:200]}")
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
    elif status["config_file_status"] == "present":
        status["reload_status"] = "skipped"
        status["server_status_list_status"] = "skipped"

    comparison = _compare_visibility(
        configured_specs=configured_specs,
        visible_records=visible_records,
        config_file_status=status["config_file_status"],
    )
    status["config_visibility_status"] = comparison["config_visibility_status"]
    warnings.extend(comparison["warnings"])

    report = {
        "schema_version": "codex-mcp-probe-v1",
        "generated_at": generated_at,
        "probe_id": probe_id,
        "report_path": str(report_path),
        "mcp": {
            **status,
            "codex_home": str(Path(codex_home).resolve()),
            "config_path": str(config_path),
            "config_updated_at": _config_updated_at(mcp_config, config_path),
            "rendered_servers": rendered_server_names,
            "expected_servers": expected_server_names,
            "visible_servers": visible_server_names,
            "expected_tools": sorted({tool for spec in configured_specs.values() for tool in spec["expected_tool_names"]}),
            "visible_tools": visible_tools,
            "request_sequence": request_sequence,
            "status_thread_id_observed": status_thread_id,
            "startup_notifications": startup_notifications,
            "config_schema_diagnostics": schema_diagnostics["diagnostics"],
            "server_launch_diagnostics": launch_diagnostics,
            "missing_servers": comparison["missing_servers"],
            "missing_tools": comparison["missing_tools"],
            "unexpected_servers": comparison["unexpected_servers"],
            "server_records": comparison["server_records"],
        },
        "known_warnings": _dedupe_preserve_order(warnings),
    }
    sanitized = redact_sensitive(report)
    write_json(report_path, sanitized)
    return sanitized


def _configured_server_specs(
    mcp_config: dict[str, Any] | None,
    rendered_specs: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    if isinstance(mcp_config, dict):
        for server in list(mcp_config.get("servers") or []):
            if not isinstance(server, dict):
                continue
            name = str(server.get("name") or "").strip()
            if not name or not bool(server.get("enabled", True)):
                continue
            specs[name] = {
                "name": name,
                "transport": str(server.get("transport") or "stdio"),
                "command": str(server.get("command") or ""),
                "args": [str(item) for item in list(server.get("args") or [])],
                "cwd": str(server.get("cwd") or ""),
                "env_vars": [str(item) for item in list(server.get("env_vars") or [])],
                "expected_tool_names": _spec_tool_names(server),
                "min_tool_count": _minimum_expected_tool_count(name, _spec_tool_names(server)),
            }
    if specs:
        return specs
    return {name: dict(spec) for name, spec in rendered_specs.items()}


def _rendered_server_specs(parsed_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    servers = parsed_config.get("mcp_servers")
    if not isinstance(servers, dict):
        return {}
    specs: dict[str, dict[str, Any]] = {}
    for name, raw in servers.items():
        if not isinstance(raw, dict):
            continue
        server_name = str(name or "").strip()
        if not server_name or not bool(raw.get("enabled", True)):
            continue
        expected_tool_names = _rendered_tool_names(raw)
        specs[server_name] = {
            "name": server_name,
            "transport": "streamable_http" if raw.get("url") else "stdio",
            "command": str(raw.get("command") or ""),
            "args": [str(item) for item in list(raw.get("args") or [])],
            "cwd": str(raw.get("cwd") or ""),
            "env_vars": [str(item) for item in list(raw.get("env_vars") or [])],
            "expected_tool_names": expected_tool_names,
            "min_tool_count": _minimum_expected_tool_count(server_name, expected_tool_names),
        }
    return specs


def _status_thread_start_params() -> dict[str, Any]:
    return {
        "ephemeral": True,
        "threadSource": "user",
        "sessionStartSource": "startup",
    }


def _thread_id_from_response(response: Any) -> str | None:
    if not isinstance(response, dict):
        return None
    for key in ("threadId", "thread_id", "id"):
        value = response.get(key)
        if value:
            return str(value)
    thread = response.get("thread")
    if isinstance(thread, dict):
        for key in ("id", "threadId", "thread_id"):
            value = thread.get(key)
            if value:
                return str(value)
    return None


def _config_schema_diagnostics(
    parsed_config: dict[str, Any],
    configured_specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    warnings: list[str] = []
    servers = parsed_config.get("mcp_servers")
    if not isinstance(servers, dict):
        return {
            "status": "missing",
            "diagnostics": [],
            "warnings": ["Rendered config.toml does not contain an [mcp_servers] table."],
        }
    for name, spec in sorted(configured_specs.items()):
        raw = servers.get(name)
        record = {
            "name": name,
            "section_present": isinstance(raw, dict),
            "transport": spec.get("transport") or "stdio",
            "has_stdio_command": bool(spec.get("command")),
            "tool_count": len(list(spec.get("expected_tool_names") or [])),
        }
        if not isinstance(raw, dict):
            record["status"] = "missing_section"
            warnings.append(f"Rendered config.toml is missing [mcp_servers.{name}].")
        elif record["transport"] == "stdio" and not record["has_stdio_command"]:
            record["status"] = "missing_command"
            warnings.append(f"Rendered config.toml MCP server {name} is stdio but has no command.")
        else:
            record["status"] = "ok"
        diagnostics.append(record)
    if not diagnostics:
        return {"status": "empty", "diagnostics": diagnostics, "warnings": warnings}
    if any(item["status"] != "ok" for item in diagnostics):
        return {"status": "partial", "diagnostics": diagnostics, "warnings": warnings}
    return {"status": "supported", "diagnostics": diagnostics, "warnings": warnings}


def _server_launch_diagnostics(configured_specs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for name, spec in sorted(configured_specs.items()):
        transport = str(spec.get("transport") or "stdio")
        command = str(spec.get("command") or "").strip()
        cwd = str(spec.get("cwd") or "").strip()
        command_resolved = ""
        command_status = "not_required"
        if transport == "stdio":
            if not command:
                command_status = "missing"
            else:
                command_path = Path(command)
                if command_path.is_absolute() or command_path.parent != Path("."):
                    command_status = "present" if command_path.exists() else "missing"
                    command_resolved = str(command_path)
                else:
                    resolved = shutil.which(command)
                    command_status = "present" if resolved else "missing"
                    command_resolved = resolved or ""
        cwd_status = "not_configured"
        if cwd:
            cwd_status = "present" if Path(cwd).exists() else "missing"
        missing_env_vars = [name for name in list(spec.get("env_vars") or []) if not str(name or "").strip()]
        diagnostics.append(
            {
                "name": name,
                "transport": transport,
                "command": command,
                "command_status": command_status,
                "command_resolved": command_resolved,
                "args_count": len(list(spec.get("args") or [])),
                "cwd": cwd,
                "cwd_status": cwd_status,
                "declared_env_vars": [str(item) for item in list(spec.get("env_vars") or [])],
                "missing_env_var_names": missing_env_vars,
            }
        )
    return diagnostics


def _server_command_probe_status(diagnostics: list[dict[str, Any]]) -> str:
    if not diagnostics:
        return "empty"
    blocking = [item for item in diagnostics if item.get("command_status") == "missing" or item.get("cwd_status") == "missing"]
    if not blocking:
        return "supported"
    if len(blocking) == len(diagnostics):
        return "missing"
    return "partial"


def _spec_tool_names(server: dict[str, Any]) -> list[str]:
    tool_names = sorted(str(name).strip() for name in dict(server.get("tools") or {}).keys() if str(name).strip())
    if tool_names:
        return tool_names
    enabled_tools = [str(name).strip() for name in list(server.get("enabled_tools") or []) if str(name).strip()]
    return sorted(set(enabled_tools))


def _rendered_tool_names(server: dict[str, Any]) -> list[str]:
    tools = server.get("tools")
    if not isinstance(tools, dict):
        enabled_tools = server.get("enabled_tools")
        if isinstance(enabled_tools, list):
            return sorted(str(name).strip() for name in enabled_tools if str(name).strip())
        return []
    return sorted(str(name).strip() for name in tools.keys() if str(name).strip())


def _minimum_expected_tool_count(server_name: str, expected_tool_names: list[str]) -> int:
    if expected_tool_names:
        return len(expected_tool_names)
    if server_name == "context7":
        return 1
    return 0


def _visible_server_record(item: dict[str, Any]) -> dict[str, Any]:
    name = str(item.get("name") or item.get("serverName") or item.get("server") or "").strip()
    tools = item.get("tools")
    tool_names: list[str]
    if isinstance(tools, dict):
        tool_names = sorted(str(key).strip() for key in tools.keys() if str(key).strip())
    elif isinstance(tools, list):
        tool_names = sorted(_visible_tool_name(value) for value in tools if _visible_tool_name(value))
    else:
        tool_names = []
    auth_state = _auth_state(item.get("authStatus"))
    return {
        "name": name,
        "visible_tool_names": tool_names,
        "auth_state": auth_state,
    }


def _visible_records_from_status_result(result: Any) -> list[dict[str, Any]] | None:
    raw_items: Any
    if isinstance(result, list):
        raw_items = result
    elif isinstance(result, dict):
        if isinstance(result.get("data"), list):
            raw_items = result.get("data")
        elif isinstance(result.get("servers"), list):
            raw_items = result.get("servers")
        elif isinstance(result.get("items"), list):
            raw_items = result.get("items")
        else:
            return None
    else:
        return None
    return [_visible_server_record(item) for item in list(raw_items or []) if isinstance(item, dict)]


def _record_mcp_notification(records: list[dict[str, Any]], method: str, params: Any) -> None:
    name = str(method or "").strip()
    if not name.startswith("mcpServer/"):
        return
    record: dict[str, Any] = {"method": name}
    if isinstance(params, dict):
        server = str(params.get("serverName") or params.get("server") or params.get("name") or "").strip()
        status = str(params.get("status") or params.get("state") or params.get("startupStatus") or "").strip()
        message = str(params.get("message") or params.get("error") or "").strip()
        if server:
            record["server"] = server
        if status:
            record["status"] = status[:120]
        if message:
            record["message"] = message[:300]
        if not server and not status and not message:
            record["keys"] = sorted(str(key) for key in params.keys())[:20]
    records.append(redact_sensitive(record))


def _visible_tool_name(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return ""


def _auth_state(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()[:80] or "unknown"
    if isinstance(value, dict):
        for key in ("status", "state", "type", "kind"):
            text = str(value.get(key) or "").strip()
            if text:
                return text[:80]
        if value.get("authenticated") is True:
            return "authenticated"
        if value.get("authenticated") is False:
            return "unauthenticated"
    return "unknown"


def _compare_visibility(
    *,
    configured_specs: dict[str, dict[str, Any]],
    visible_records: list[dict[str, Any]],
    config_file_status: str,
) -> dict[str, Any]:
    visible_by_name = {record["name"]: record for record in visible_records if str(record.get("name") or "").strip()}
    missing_servers: list[str] = []
    missing_tools: list[str] = []
    warnings: list[str] = []
    server_records: list[dict[str, Any]] = []

    for name, spec in sorted(configured_specs.items()):
        visible = visible_by_name.get(name)
        expected_tool_names = list(spec["expected_tool_names"])
        expected_tools = set(expected_tool_names)
        min_tool_count = int(spec.get("min_tool_count") or 0)
        if visible is None:
            missing_servers.append(name)
            server_records.append(
                {
                    "name": name,
                    "configured": True,
                    "visible": False,
                    "visibility_status": "missing",
                    "expected_tool_names": expected_tool_names,
                    "visible_tool_names": [],
                    "missing_tool_names": expected_tool_names,
                    "auth_state": "unknown",
                }
            )
            continue
        visible_tool_names = list(visible["visible_tool_names"])
        visible_tools = set(visible_tool_names)
        record_missing_tools = sorted(expected_tools - visible_tools)
        if record_missing_tools:
            missing_tools.extend(record_missing_tools)
        if expected_tools:
            visibility_status = "visible" if not record_missing_tools else "partial"
        elif min_tool_count > 0:
            visibility_status = "visible" if len(visible_tool_names) >= min_tool_count else "partial"
            if visibility_status != "visible":
                warnings.append(f"MCP server {name} is visible but reported fewer tools than expected.")
        else:
            visibility_status = "visible"
        server_records.append(
            {
                "name": name,
                "configured": True,
                "visible": True,
                "visibility_status": visibility_status,
                "expected_tool_names": expected_tool_names,
                "visible_tool_names": visible_tool_names,
                "missing_tool_names": record_missing_tools,
                "auth_state": visible["auth_state"],
            }
        )

    unexpected_servers = sorted(name for name in visible_by_name if name not in configured_specs)
    for name in unexpected_servers:
        visible = visible_by_name[name]
        server_records.append(
            {
                "name": name,
                "configured": False,
                "visible": True,
                "visibility_status": "unexpected",
                "expected_tool_names": [],
                "visible_tool_names": list(visible["visible_tool_names"]),
                "missing_tool_names": [],
                "auth_state": visible["auth_state"],
            }
        )

    if config_file_status == "malformed":
        config_visibility_status = "malformed"
    elif not configured_specs:
        config_visibility_status = "empty"
    elif not visible_by_name:
        config_visibility_status = "missing"
    else:
        partial_records = [record for record in server_records if record["configured"] and record["visibility_status"] != "visible"]
        config_visibility_status = "visible" if not partial_records and not missing_servers else "partial"

    if missing_servers:
        warnings.append(f"Expected MCP servers were not visible to Codex: {', '.join(missing_servers)}")
    if missing_tools:
        warnings.append(f"Expected MCP tools were not visible to Codex: {', '.join(sorted(set(missing_tools)))}")

    return {
        "config_visibility_status": config_visibility_status,
        "missing_servers": sorted(set(missing_servers)),
        "missing_tools": sorted(set(missing_tools)),
        "unexpected_servers": unexpected_servers,
        "server_records": sorted(server_records, key=lambda item: (not bool(item.get("configured")), str(item.get("name") or ""))),
        "warnings": warnings,
    }


def _config_updated_at(mcp_config: dict[str, Any] | None, config_path: Path) -> str | None:
    if isinstance(mcp_config, dict):
        updated_at = str(mcp_config.get("updated_at") or "").strip()
        if updated_at:
            return updated_at
    if not config_path.exists():
        return None
    try:
        modified = dt.datetime.fromtimestamp(config_path.stat().st_mtime, tz=dt.timezone.utc).astimezone()
        return modified.isoformat()
    except OSError:
        return None


def _jsonrpc_probe_status(exc: JsonRpcError) -> str:
    if int(exc.code or 0) == -32601:
        return "incompatible_response"
    return "error_response"


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
