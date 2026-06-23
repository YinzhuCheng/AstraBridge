from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import Any

from .common import app_data_dir, now_iso, read_json, write_json
from .security import SECRET_RE, SecurityError, redact_sensitive


SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
ALLOWED_TRANSPORTS = {"stdio", "streamable_http"}
ALLOWED_APPROVAL_MODES = {"auto", "prompt", "approve"}

CONTEXT7_PRESET: dict[str, Any] = {
    "name": "context7",
    "display_name": "Context7",
    "enabled": True,
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@upstash/context7-mcp"],
    "cwd": None,
    "env": {},
    "env_vars": [],
    "url": "",
    "bearer_token_env_var": None,
    "http_headers": {},
    "env_http_headers": {},
    "startup_timeout_sec": 20,
    "tool_timeout_sec": 60,
    "required": False,
    "default_tools_approval_mode": "prompt",
    "enabled_tools": [],
    "disabled_tools": [],
    "tools": {},
    "trust_note": "Free documentation lookup MCP server. Keep approval prompts enabled until a model/server pair has passed smoke tests.",
    "source_url": "https://github.com/upstash/context7",
}


def yunwu_image_preset() -> dict[str, Any]:
    sidecar_root = str(Path(__file__).resolve().parents[1])
    server_script = str(Path(__file__).resolve().with_name("yunwu_image_mcp_server.py"))
    return {
        "name": "yunwu_image",
        "display_name": "Yunwu Image Tool",
        "enabled": True,
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-u", server_script],
        "cwd": sidecar_root,
        "env": {"PYTHONPATH": sidecar_root},
        "env_vars": [
            "YUNWU_API_KEY",
            "ASTRABRIDGE_WORKSPACE_ROOT",
            "ASTRABRIDGE_ASSET_ROOT",
            "ASTRABRIDGE_WORKSPACE_ROOT_WSL",
            "ASTRABRIDGE_ASSET_ROOT_WSL",
        ],
        "url": "",
        "bearer_token_env_var": None,
        "http_headers": {},
        "env_http_headers": {},
        "startup_timeout_sec": 20,
        "tool_timeout_sec": 300,
        "required": False,
        "default_tools_approval_mode": "prompt",
        "enabled_tools": [],
        "disabled_tools": [],
        "tools": {
            "yunwu_image_generate": {"approval_mode": "prompt"},
            "yunwu_image_transparent_asset": {"approval_mode": "prompt"},
            "yunwu_image_edit": {"approval_mode": "prompt"},
        },
        "trust_note": "Image generation/editing tool for Yunwu OpenAI-compatible Images endpoint. The tool reads only the configured runtime environment variable and never accepts credentials as tool arguments.",
        "source_url": "https://platform.openai.com/docs/api-reference/images/create",
    }


def astrabridge_web_preset() -> dict[str, Any]:
    sidecar_root = str(Path(__file__).resolve().parents[1])
    server_script = str(Path(__file__).resolve().with_name("astrabridge_web_mcp_server.py"))
    return {
        "name": "astrabridge_web",
        "display_name": "AstraBridge Built-in Web Tools",
        "enabled": True,
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-u", server_script],
        "cwd": sidecar_root,
        "env": {"PYTHONPATH": sidecar_root},
        "env_vars": [],
        "url": "",
        "bearer_token_env_var": None,
        "http_headers": {},
        "env_http_headers": {},
        "startup_timeout_sec": 20,
        "tool_timeout_sec": 60,
        "required": False,
        "default_tools_approval_mode": "auto",
        "enabled_tools": [],
        "disabled_tools": [],
        "tools": {
            "astrabridge_web_search_batch": {"approval_mode": "auto"},
            "astrabridge_web_research_brief": {"approval_mode": "auto"},
            "astrabridge_web_search": {"approval_mode": "auto"},
            "astrabridge_web_fetch": {"approval_mode": "auto"},
        },
        "trust_note": "App-owned web research tools for public HTTP(S) batch search and lightweight research briefs. Basic search is represented as batch size 1. These tools are auto-approved because they reject local/private URLs, reject secret-like arguments, do not accept credentials, and return truncated sanitized text.",
        "source_url": "https://duckduckgo.com/",
    }

class McpConfigService:
    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = store_path or (app_data_dir() / "mcp_servers.json")

    def snapshot(self) -> dict[str, Any]:
        payload = self._load()
        return {
            **payload,
            "environment": {
                "node": bool(shutil.which("node")),
                "npx": bool(shutil.which("npx")),
                "python": bool(sys.executable),
            },
        }

    def apply_context7_preset(self) -> dict[str, Any]:
        server = self.upsert_server(CONTEXT7_PRESET)
        return {"server": server, "config": self.snapshot()}

    def apply_yunwu_image_preset(self) -> dict[str, Any]:
        server = self.upsert_server(yunwu_image_preset())
        return {"server": server, "config": self.snapshot()}

    def apply_astrabridge_web_preset(self) -> dict[str, Any]:
        server = self.upsert_server(astrabridge_web_preset())
        return {"server": server, "config": self.snapshot()}

    def upsert_server(self, server: dict[str, Any]) -> dict[str, Any]:
        payload = self._load()
        normalized = self._normalize_server(server)
        normalized["updated_at"] = now_iso()
        existing = {str(item.get("name")): item for item in payload["servers"]}
        if normalized["name"] in existing:
            normalized["created_at"] = existing[normalized["name"]].get("created_at") or normalized["created_at"]
        existing[normalized["name"]] = normalized
        payload["servers"] = sorted(existing.values(), key=lambda item: str(item.get("name")))
        payload["updated_at"] = now_iso()
        write_json(self.store_path, payload)
        return normalized

    def delete_server(self, name: str) -> dict[str, Any]:
        payload = self._load()
        payload["servers"] = [item for item in payload["servers"] if str(item.get("name")) != name]
        payload["updated_at"] = now_iso()
        write_json(self.store_path, payload)
        return {"deleted": name, "config": self.snapshot()}

    def enabled_servers(self) -> list[dict[str, Any]]:
        return [server for server in self._load()["servers"] if server.get("enabled", True)]

    def render_toml(self) -> str:
        blocks: list[str] = []
        for server in self.enabled_servers():
            blocks.extend(self._render_server_toml(server))
        return "\n".join(blocks).strip()

    def _load(self) -> dict[str, Any]:
        payload = read_json(self.store_path, {})
        if not isinstance(payload, dict):
            payload = {}
        servers = [self._normalize_server(item) for item in list(payload.get("servers") or []) if isinstance(item, dict)]
        loaded = {"servers": servers, "updated_at": payload.get("updated_at") or now_iso()}
        write_json(self.store_path, loaded)
        return loaded

    def _normalize_server(self, server: dict[str, Any]) -> dict[str, Any]:
        name = str(server.get("name") or "").strip()
        if not name or not SERVER_NAME_RE.match(name):
            raise SecurityError("MCP server name must contain only letters, numbers, dot, dash, or underscore.")
        transport = str(server.get("transport") or "stdio").strip()
        if transport not in ALLOWED_TRANSPORTS:
            raise SecurityError(f"Unsupported MCP transport: {transport}")
        default_approval = str(server.get("default_tools_approval_mode") or "prompt").strip()
        if default_approval not in ALLOWED_APPROVAL_MODES:
            raise SecurityError("MCP approval mode must be auto, prompt, or approve.")
        normalized = {
            "name": name,
            "display_name": str(server.get("display_name") or name).strip() or name,
            "enabled": bool(server.get("enabled", True)),
            "transport": transport,
            "command": str(server.get("command") or "").strip(),
            "args": self._string_list(server.get("args")),
            "cwd": self._optional_string(server.get("cwd")),
            "env": self._env_map(server.get("env")),
            "env_vars": self._env_list(server.get("env_vars")),
            "url": self._optional_string(server.get("url")) or "",
            "bearer_token_env_var": self._optional_env(server.get("bearer_token_env_var")),
            "http_headers": self._safe_map(server.get("http_headers")),
            "env_http_headers": self._env_header_map(server.get("env_http_headers")),
            "startup_timeout_sec": self._positive_int(server.get("startup_timeout_sec"), 20),
            "tool_timeout_sec": self._positive_int(server.get("tool_timeout_sec"), 60),
            "required": bool(server.get("required", False)),
            "default_tools_approval_mode": default_approval,
            "enabled_tools": self._string_list(server.get("enabled_tools")),
            "disabled_tools": self._string_list(server.get("disabled_tools")),
            "tools": self._tool_map(server.get("tools")),
            "trust_note": str(server.get("trust_note") or "").strip(),
            "source_url": str(server.get("source_url") or "").strip(),
            "created_at": server.get("created_at") or now_iso(),
            "updated_at": server.get("updated_at") or now_iso(),
        }
        if transport == "stdio" and not normalized["command"]:
            raise SecurityError("STDIO MCP servers require a command.")
        if transport == "streamable_http" and not normalized["url"].startswith(("http://", "https://")):
            raise SecurityError("Streamable HTTP MCP servers require an HTTP(S) URL.")
        self._reject_secret_like(normalized)
        return normalized

    def _render_server_toml(self, server: dict[str, Any]) -> list[str]:
        key = _toml_key(str(server["name"]))
        lines = [f"[mcp_servers.{key}]", f"enabled = {_toml_bool(server.get('enabled', True))}", f"required = {_toml_bool(server.get('required', False))}"]
        if server["transport"] == "stdio":
            lines.append(f'command = "{_toml_escape(server["command"])}"')
            if server.get("args"):
                lines.append(f"args = {_toml_array(server['args'])}")
            if server.get("cwd"):
                lines.append(f'cwd = "{_toml_escape(str(server["cwd"]))}"')
        else:
            lines.append(f'url = "{_toml_escape(str(server["url"]))}"')
            if server.get("bearer_token_env_var"):
                lines.append(f'bearer_token_env_var = "{_toml_escape(str(server["bearer_token_env_var"]))}"')
        lines.append(f"startup_timeout_sec = {int(server.get('startup_timeout_sec') or 20)}")
        lines.append(f"tool_timeout_sec = {int(server.get('tool_timeout_sec') or 60)}")
        default_approval = _toml_escape(str(server.get("default_tools_approval_mode") or "prompt"))
        lines.append(f'default_tools_approval_mode = "{default_approval}"')
        if server.get("enabled_tools"):
            lines.append(f"enabled_tools = {_toml_array(server['enabled_tools'])}")
        if server.get("disabled_tools"):
            lines.append(f"disabled_tools = {_toml_array(server['disabled_tools'])}")
        if server.get("env_vars"):
            lines.append(f"env_vars = {_toml_array(server['env_vars'])}")
        for section_name, values in (("env", server.get("env") or {}), ("http_headers", server.get("http_headers") or {}), ("env_http_headers", server.get("env_http_headers") or {})):
            if values:
                lines.append("")
                lines.append(f"[mcp_servers.{key}.{section_name}]")
                for map_key, value in sorted(dict(values).items()):
                    lines.append(f'{_toml_key(str(map_key))} = "{_toml_escape(str(value))}"')
        for tool_name, tool_config in sorted(dict(server.get("tools") or {}).items()):
            approval_mode = str((tool_config or {}).get("approval_mode") or "").strip()
            if not approval_mode:
                continue
            lines.append("")
            lines.append(f"[mcp_servers.{key}.tools.{_toml_key(str(tool_name))}]")
            lines.append(f'approval_mode = "{_toml_escape(approval_mode)}"')
        lines.append("")
        return lines

    def _reject_secret_like(self, server: dict[str, Any]) -> None:
        scrubbed = {
            key: value
            for key, value in server.items()
            if key not in {"bearer_token_env_var", "env_vars", "env_http_headers", "created_at", "updated_at"}
        }
        serialized = str(redact_sensitive(scrubbed))
        if "[REDACTED]" in serialized or SECRET_RE.search(serialized):
            raise SecurityError("MCP config contains secret-like literal content. Store only environment variable names.")

    def _string_list(self, value: Any) -> list[str]:
        if isinstance(value, str):
            raw = value.replace("\n", ",").split(",")
        elif isinstance(value, list):
            raw = value
        else:
            raw = []
        return [str(item).strip() for item in raw if str(item).strip()]

    def _env_list(self, value: Any) -> list[str]:
        envs = self._string_list(value)
        for env_name in envs:
            if not ENV_NAME_RE.match(env_name):
                raise SecurityError(f"Invalid MCP environment variable name: {env_name}")
        return envs

    def _env_map(self, value: Any) -> dict[str, str]:
        values = self._safe_map(value)
        for key in values:
            if not ENV_NAME_RE.match(str(key)):
                raise SecurityError(f"Invalid MCP env key: {key}")
        return values

    def _safe_map(self, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        result = {str(key).strip(): str(item).strip() for key, item in value.items() if str(key).strip() and str(item).strip()}
        for key, item in result.items():
            if SECRET_RE.search(key) or SECRET_RE.search(item):
                raise SecurityError("MCP map fields cannot contain secret-like values.")
        return result

    def _env_header_map(self, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        result = {str(key).strip(): str(item).strip() for key, item in value.items() if str(key).strip() and str(item).strip()}
        for env_name in result.values():
            if not ENV_NAME_RE.match(env_name):
                raise SecurityError(f"Invalid MCP header environment variable name: {env_name}")
        return result

    def _tool_map(self, value: Any) -> dict[str, dict[str, str]]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, dict[str, str]] = {}
        for tool_name, config in value.items():
            name = str(tool_name).strip()
            if not name:
                continue
            approval_mode = str((config or {}).get("approval_mode") or "").strip()
            if approval_mode and approval_mode not in ALLOWED_APPROVAL_MODES:
                raise SecurityError("MCP per-tool approval mode must be auto, prompt, or approve.")
            result[name] = {"approval_mode": approval_mode}
        return result

    def _optional_string(self, value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    def _optional_env(self, value: Any) -> str | None:
        text = self._optional_string(value)
        if not text:
            return None
        if not ENV_NAME_RE.match(text):
            raise SecurityError(f"Invalid MCP bearer token env var: {text}")
        return text

    def _positive_int(self, value: Any, fallback: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed > 0 else fallback


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _toml_key(value: str) -> str:
    return value if re.match(r"^[A-Za-z0-9_-]+$", value) else f'"{_toml_escape(value)}"'


def _toml_array(values: list[Any]) -> str:
    return "[" + ", ".join(f'"{_toml_escape(str(value))}"' for value in values) + "]"


def _toml_bool(value: Any) -> str:
    return "true" if bool(value) else "false"

