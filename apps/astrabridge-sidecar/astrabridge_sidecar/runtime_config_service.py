from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .common import default_codex_home, now_iso, write_json
from .mcp_config_service import McpConfigService
from .model_catalog import (
    ASTRABRIDGE_MODEL_CATALOG_FILENAME,
    ASTRABRIDGE_MODELS_CACHE_FILENAME,
    compact_limit,
    known_context_window,
    model_catalog_entry,
    normalize_input_modalities,
    tool_output_truncation_limit,
)
from .security import SECRET_RE, SecurityError
from .secret_service import SecretService


ROUTER_ENV_KEY = "CODEX_ROUTER_API_KEY"
DEFAULT_ROUTER_BASE_URL = "http://127.0.0.1:8787/v1"
ALLOWED_WIRE_APIS = {"responses", "chat"}
ALLOWED_REASONING_EFFORTS = {"off", "auto", "minimal", "low", "medium", "high", "xhigh", "max"}
CODEX_REASONING_EFFORTS = {"off", "auto", "minimal", "low", "medium", "high", "xhigh"}
ALLOWED_PROXY_MODES = {"direct", "system", "custom"}
ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
PROVIDER_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
RESERVED_CODEX_PROVIDER_IDS = {"openai"}
PROXY_URL_RE = re.compile(r"^(https?|socks5)://(127\.0\.0\.1|localhost):([1-9][0-9]{0,4})$")
PROXY_ENV_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
LOCAL_NO_PROXY = "127.0.0.1,localhost,::1"


class RuntimeConfigService:
    def __init__(self, codex_home: Path | None = None, secret_service: SecretService | None = None, mcp_config: McpConfigService | None = None) -> None:
        self.codex_home = (codex_home or default_codex_home()).resolve()
        self._active_runtime: dict[str, Any] | None = None
        self._secrets = secret_service or SecretService()
        self._mcp_config = mcp_config or McpConfigService()

    def prepare_profile(
        self,
        profile: dict[str, Any],
        *,
        require_secret: bool,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._normalize_profile(profile)
        if session_key is not None and session_key.strip():
            os.environ[runtime["env_key"]] = session_key.strip()
        elif runtime["auth_mode"] == "os_keychain" and runtime.get("secret_ref"):
            loaded = self._secrets.load(str(runtime.get("secret_ref")))
            if loaded:
                os.environ[runtime["env_key"]] = loaded
        self.codex_home.mkdir(parents=True, exist_ok=True)
        self._write_config(runtime)
        self._apply_proxy_environment(runtime)
        os.environ["CODEX_HOME"] = str(self.codex_home)
        secret_loaded = bool(os.environ.get(runtime["env_key"]))
        if require_secret and not secret_loaded:
            raise RuntimeError(
                f"runtime_secret_missing: set {runtime['env_key']} in the environment, paste a session key, or load a local key file."
            )
        runtime = {**runtime, "codex_home": str(self.codex_home), "configured": True, "secret_loaded": secret_loaded}
        self._active_runtime = runtime
        return self.redacted(runtime)

    def load_secret(
        self,
        profile: dict[str, Any],
        *,
        session_key: str | None = None,
        key_file_path: str | None = None,
    ) -> dict[str, Any]:
        runtime = self._normalize_profile(profile)
        if session_key and session_key.strip():
            os.environ[runtime["env_key"]] = session_key.strip()
        elif key_file_path:
            value = Path(key_file_path).expanduser().read_text(encoding="utf-8-sig").strip()
            if "\n" in value or "\r" in value:
                value = value.splitlines()[0].strip()
            if len(value) < 8:
                raise SecurityError("Key file does not contain a plausible API key.")
            os.environ[runtime["env_key"]] = value
        elif runtime["auth_mode"] == "os_keychain" and runtime.get("secret_ref"):
            value = self._secrets.load(str(runtime.get("secret_ref")))
            if not value:
                raise ValueError("No keychain secret is stored for this provider.")
            os.environ[runtime["env_key"]] = value
        else:
            raise ValueError("Either session_key or key_file_path is required.")
        return self.prepare_profile(profile, require_secret=True)

    def status(self) -> dict[str, Any]:
        if self._active_runtime is not None:
            runtime = {
                **self._active_runtime,
                "secret_loaded": bool(os.environ.get(str(self._active_runtime["env_key"]))),
            }
            return self.redacted(runtime)
        return {
            "configured": False,
            "codex_home": str(self.codex_home),
            "provider_id": None,
            "provider_name": None,
            "base_url": None,
            "model": None,
            "reasoning_effort": None,
            "wire_api": None,
            "env_key": None,
            "secret_loaded": False,
            "proxy_mode": "direct",
            "proxy_url": "",
            "secret_source": None,
            "secret_fingerprint": None,
        }

    def redacted(self, runtime: dict[str, Any]) -> dict[str, Any]:
        return {
            "configured": bool(runtime.get("configured", True)),
            "codex_home": str(runtime.get("codex_home") or self.codex_home),
            "provider_id": runtime.get("provider_id"),
            "provider_name": runtime.get("provider_name"),
            "base_url": runtime.get("base_url"),
            "model": runtime.get("model"),
            "reasoning_effort": runtime.get("reasoning_effort"),
            "wire_api": runtime.get("wire_api"),
            "env_key": runtime.get("env_key"),
            "secret_loaded": bool(runtime.get("secret_loaded")),
            "proxy_mode": runtime.get("proxy_mode") or "direct",
            "proxy_url": runtime.get("proxy_url") or "",
            "execution_host": runtime.get("execution_host") or "windows",
            "wsl_distro": runtime.get("wsl_distro"),
            "input_modalities": runtime.get("input_modalities"),
            "apply_patch_tool_type": runtime.get("apply_patch_tool_type"),
            "web_search_tool_type": runtime.get("web_search_tool_type"),
            "supports_parallel_tool_calls": runtime.get("supports_parallel_tool_calls"),
            "supports_reasoning_summaries": runtime.get("supports_reasoning_summaries"),
            "supports_search_tool": runtime.get("supports_search_tool"),
            "native_web_search_support": runtime.get("native_web_search_support"),
            "tool_web_search_support": runtime.get("tool_web_search_support"),
            "mcp_web_support": runtime.get("mcp_web_support"),
            "web_smoke_status": runtime.get("web_smoke_status"),
            "citation_quality": runtime.get("citation_quality"),
            "last_web_verified_at": runtime.get("last_web_verified_at"),
            "tool_mode": runtime.get("tool_mode"),
            "multi_agent_version": runtime.get("multi_agent_version"),
            "use_responses_lite": runtime.get("use_responses_lite"),
            "supports_mcp_tools": runtime.get("supports_mcp_tools"),
            "mcp_tool_call_policy": runtime.get("mcp_tool_call_policy"),
            "mcp_verified_servers": runtime.get("mcp_verified_servers"),
            "mcp_smoke_status": runtime.get("mcp_smoke_status"),
            "mcp_tool_argument_validation": runtime.get("mcp_tool_argument_validation"),
            "secret_source": runtime.get("secret_source"),
            "secret_fingerprint": runtime.get("secret_fingerprint"),
            "mcp_config_updated_at": self._mcp_config.snapshot().get("updated_at"),
        }

    def runtime_signature(self, runtime_status: dict[str, Any]) -> tuple[Any, ...]:
        return (
            runtime_status.get("codex_home"),
            runtime_status.get("provider_id"),
            runtime_status.get("base_url"),
            runtime_status.get("model"),
            runtime_status.get("reasoning_effort"),
            runtime_status.get("wire_api"),
            runtime_status.get("env_key"),
            runtime_status.get("secret_fingerprint"),
            runtime_status.get("proxy_mode"),
            runtime_status.get("proxy_url"),
            runtime_status.get("execution_host"),
            runtime_status.get("wsl_distro"),
            runtime_status.get("mcp_config_updated_at"),
            tuple(runtime_status.get("input_modalities") or []),
            runtime_status.get("apply_patch_tool_type"),
            runtime_status.get("web_search_tool_type"),
            runtime_status.get("supports_parallel_tool_calls"),
            runtime_status.get("supports_reasoning_summaries"),
            runtime_status.get("supports_search_tool"),
            runtime_status.get("native_web_search_support"),
            runtime_status.get("tool_web_search_support"),
            runtime_status.get("mcp_web_support"),
            runtime_status.get("web_smoke_status"),
            runtime_status.get("citation_quality"),
            runtime_status.get("last_web_verified_at"),
            runtime_status.get("tool_mode"),
            runtime_status.get("multi_agent_version"),
            runtime_status.get("use_responses_lite"),
            runtime_status.get("supports_mcp_tools"),
            runtime_status.get("mcp_tool_call_policy"),
            tuple(runtime_status.get("mcp_verified_servers") or []),
            runtime_status.get("mcp_smoke_status"),
            runtime_status.get("mcp_tool_argument_validation"),
        )

    def _normalize_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(profile.get("provider_id") or "openai").strip()
        if not PROVIDER_ID_RE.match(provider_id):
            raise SecurityError(f"Invalid provider_id: {provider_id}")
        base_url = str(profile.get("base_url") or "https://api.openai.com/v1").strip().rstrip("/")
        if not base_url.startswith(("https://", "http://")):
            raise SecurityError("Provider base_url must be an HTTP(S) URL.")
        if SECRET_RE.search(base_url):
            raise SecurityError("Provider base_url contains secret-like content.")
        wire_api = str(profile.get("wire_api") or "responses").strip().lower()
        if wire_api not in ALLOWED_WIRE_APIS:
            raise SecurityError(f"Unsupported provider wire_api: {wire_api}")
        reasoning_effort = str(profile.get("reasoning_effort") or "high").strip().lower()
        if reasoning_effort not in ALLOWED_REASONING_EFFORTS:
            raise SecurityError(f"Unsupported reasoning effort: {reasoning_effort}")
        env_key = str(profile.get("env_key") or "OPENAI_API_KEY").strip()
        if not ENV_KEY_RE.match(env_key):
            raise SecurityError("env_key must be a valid environment variable name.")
        proxy_mode, proxy_url = self._normalize_proxy(profile)
        model = str(profile.get("model") or "gpt-5").strip()
        if not model:
            raise SecurityError("model is required.")
        metadata = self._secrets.metadata(
            env_key=env_key,
            auth_mode=str(profile.get("auth_mode") or "env_ref"),
            secret_ref=str(profile.get("secret_ref") or "") or None,
        )
        return {
            "profile_id": str(profile.get("profile_id") or provider_id),
            "provider_id": provider_id,
            "provider_name": str(profile.get("label") or provider_id),
            "base_url": base_url,
            "model": model,
            "context_window": _optional_positive_int(profile.get("context_window")) or known_context_window(provider_id, model),
            "auto_compact_token_limit": _optional_positive_int(profile.get("auto_compact_token_limit")),
            "input_modalities": normalize_input_modalities(profile.get("input_modalities"), provider_id, model),
            "apply_patch_tool_type": profile.get("apply_patch_tool_type"),
            "web_search_tool_type": profile.get("web_search_tool_type"),
            "supports_parallel_tool_calls": profile.get("supports_parallel_tool_calls"),
            "supports_reasoning_summaries": profile.get("supports_reasoning_summaries"),
            "supports_search_tool": profile.get("supports_search_tool"),
            "native_web_search_support": profile.get("native_web_search_support"),
            "tool_web_search_support": profile.get("tool_web_search_support"),
            "mcp_web_support": profile.get("mcp_web_support"),
            "web_smoke_status": profile.get("web_smoke_status"),
            "citation_quality": profile.get("citation_quality"),
            "last_web_verified_at": profile.get("last_web_verified_at"),
            "tool_mode": profile.get("tool_mode"),
            "multi_agent_version": profile.get("multi_agent_version"),
            "use_responses_lite": profile.get("use_responses_lite"),
            "supports_mcp_tools": profile.get("supports_mcp_tools"),
            "mcp_tool_call_policy": profile.get("mcp_tool_call_policy"),
            "mcp_verified_servers": profile.get("mcp_verified_servers"),
            "mcp_smoke_status": profile.get("mcp_smoke_status"),
            "mcp_tool_argument_validation": profile.get("mcp_tool_argument_validation"),
            "codex_builtin_tools": profile.get("codex_builtin_tools"),
            "planner_support": profile.get("planner_support"),
            "goal_support": profile.get("goal_support"),
            "context_compaction_support": profile.get("context_compaction_support"),
            "modality_limits": profile.get("modality_limits"),
            "ui_warnings": profile.get("ui_warnings"),
            "reasoning_effort": reasoning_effort,
            "wire_api": wire_api,
            "env_key": env_key,
            "proxy_mode": proxy_mode,
            "proxy_url": proxy_url,
            "auth_mode": str(profile.get("auth_mode") or "env_ref"),
            "secret_ref": str(profile.get("secret_ref") or "") or None,
            "secret_source": metadata.source,
            "secret_fingerprint": metadata.fingerprint,
        }

    def _normalize_proxy(self, profile: dict[str, Any]) -> tuple[str, str]:
        mode = str(profile.get("proxy_mode") or "direct").strip().lower()
        if mode not in ALLOWED_PROXY_MODES:
            raise SecurityError(f"Unsupported proxy mode: {mode}")
        proxy_url = str(profile.get("proxy_url") or "").strip()
        if not proxy_url:
            return mode, ""
        if "@" in proxy_url or SECRET_RE.search(proxy_url) or not PROXY_URL_RE.match(proxy_url):
            raise SecurityError("proxy_url must be a credential-free local HTTP(S) or SOCKS5 URL.")
        return mode, proxy_url if mode == "custom" else ""

    def _apply_proxy_environment(self, runtime: dict[str, Any]) -> None:
        mode = str(runtime.get("proxy_mode") or "direct")
        if mode == "system":
            return
        if mode == "direct":
            for key in PROXY_ENV_KEYS:
                os.environ.pop(key, None)
            os.environ["NO_PROXY"] = LOCAL_NO_PROXY
            os.environ["no_proxy"] = LOCAL_NO_PROXY
            return
        proxy_url = str(runtime.get("proxy_url") or "").strip()
        if not proxy_url:
            raise SecurityError("Custom proxy mode requires proxy_url.")
        for key in PROXY_ENV_KEYS:
            os.environ[key] = proxy_url
        os.environ["NO_PROXY"] = LOCAL_NO_PROXY
        os.environ["no_proxy"] = LOCAL_NO_PROXY

    def _write_config(self, runtime: dict[str, Any]) -> None:
        codex_model = codex_model_id(runtime, runtime["model"])
        codex_base_url = os.environ.get("ASTRABRIDGE_BASE_URL", DEFAULT_ROUTER_BASE_URL).rstrip("/")
        context_window = (
            _optional_positive_int(os.environ.get("ASTRABRIDGE_MODEL_CONTEXT_WINDOW"))
            or _optional_positive_int(runtime.get("context_window"))
            or 128_000
        )
        auto_compact_limit = (
            _optional_positive_int(os.environ.get("ASTRABRIDGE_AUTO_COMPACT_TOKEN_LIMIT"))
            or _optional_positive_int(runtime.get("auto_compact_token_limit"))
            or None
        )
        auto_compact_limit = compact_limit(context_window, auto_compact_limit)
        tool_output_limit = tool_output_truncation_limit(context_window)
        catalog_path = self._write_model_catalog(runtime, codex_model, context_window, auto_compact_limit)
        metadata_lines = []
        metadata_lines.append(f'model_catalog_json = "{_toml_escape(str(catalog_path))}"')
        metadata_lines.append(f"model_context_window = {context_window}")
        metadata_lines.append(f"model_auto_compact_token_limit = {auto_compact_limit}")
        metadata_lines.append(f"tool_output_token_limit = {tool_output_limit}")
        mcp_toml = self._mcp_config.render_toml()
        content = "\n".join(
            [
                f'model = "{_toml_escape(codex_model)}"',
                f'model_provider = "{_toml_escape(runtime["provider_id"])}"',
                f'model_reasoning_effort = "{_toml_escape(codex_reasoning_effort(runtime["reasoning_effort"]))}"',
                "hide_agent_reasoning = true",
                'cli_auth_credentials_store = "ephemeral"',
                'mcp_oauth_credentials_store = "keyring"',
                *metadata_lines,
                "",
                *self._model_provider_section_lines(runtime, codex_base_url),
                "",
                "[features]",
                "plugins = false",
                "plugin_sharing = false",
                "remote_plugin = false",
                "",
                mcp_toml,
                "",
            ]
        )
        (self.codex_home / "config.toml").write_text(content, encoding="utf-8", newline="\n")

    def _model_provider_section_lines(self, runtime: dict[str, Any], codex_base_url: str) -> list[str]:
        providers: dict[str, str] = {}

        def add(provider_id: Any, label: Any) -> None:
            provider = str(provider_id or "").strip()
            if not provider or not PROVIDER_ID_RE.match(provider):
                return
            if provider.lower() in RESERVED_CODEX_PROVIDER_IDS:
                return
            providers.setdefault(provider, str(label or provider).strip() or provider)

        add(runtime.get("provider_id"), runtime.get("provider_name"))
        try:
            from .profile_service import ProfileService

            for profile in ProfileService().list_profiles().get("profiles") or []:
                if not isinstance(profile, dict):
                    continue
                add(profile.get("provider_id"), profile.get("label"))
        except Exception:
            # Current runtime provider is enough to launch; full provider list is
            # a robustness layer for multi-provider handoff and UI polling races.
            pass

        lines: list[str] = []
        for provider, label in providers.items():
            lines.extend(
                [
                    f'[model_providers.{_toml_key(provider)}]',
                    f'name = "{_toml_escape(label)} via AstraBridge"',
                    f'base_url = "{_toml_escape(codex_base_url)}"',
                    f'env_key = "{ROUTER_ENV_KEY}"',
                    'wire_api = "responses"',
                    "requires_openai_auth = false",
                    "supports_websockets = false",
                    "",
                ]
            )
        return lines

    def _write_model_catalog(self, runtime: dict[str, Any], codex_model: str, context_window: int, auto_compact_limit: int) -> Path:
        configured_model = {
            "input_modalities": runtime.get("input_modalities"),
            "apply_patch_tool_type": runtime.get("apply_patch_tool_type"),
            "web_search_tool_type": runtime.get("web_search_tool_type"),
            "supports_parallel_tool_calls": runtime.get("supports_parallel_tool_calls"),
            "supports_reasoning_summaries": runtime.get("supports_reasoning_summaries"),
            "supports_search_tool": runtime.get("supports_search_tool"),
            "native_web_search_support": runtime.get("native_web_search_support"),
            "tool_web_search_support": runtime.get("tool_web_search_support"),
            "mcp_web_support": runtime.get("mcp_web_support"),
            "web_smoke_status": runtime.get("web_smoke_status"),
            "citation_quality": runtime.get("citation_quality"),
            "last_web_verified_at": runtime.get("last_web_verified_at"),
            "tool_mode": runtime.get("tool_mode"),
            "multi_agent_version": runtime.get("multi_agent_version"),
            "use_responses_lite": runtime.get("use_responses_lite"),
            "tool_output_token_limit": tool_output_truncation_limit(context_window),
            "supports_mcp_tools": runtime.get("supports_mcp_tools"),
            "mcp_tool_call_policy": runtime.get("mcp_tool_call_policy"),
            "mcp_verified_servers": runtime.get("mcp_verified_servers"),
            "mcp_smoke_status": runtime.get("mcp_smoke_status"),
            "mcp_tool_argument_validation": runtime.get("mcp_tool_argument_validation"),
            "codex_builtin_tools": runtime.get("codex_builtin_tools"),
            "planner_support": runtime.get("planner_support"),
            "goal_support": runtime.get("goal_support"),
            "context_compaction_support": runtime.get("context_compaction_support"),
            "modality_limits": runtime.get("modality_limits"),
            "ui_warnings": runtime.get("ui_warnings"),
        }
        model = model_catalog_entry(
            model_id=codex_model,
            provider_id=str(runtime.get("provider_id") or ""),
            native_model=str(runtime.get("model") or ""),
            display_name=f"{runtime['provider_name']} {runtime['model']}",
            context_window=context_window,
            reasoning_effort=runtime.get("reasoning_effort"),
            configured_model=configured_model,
            auto_compact_token_limit=auto_compact_limit,
        )
        catalog_path = self.codex_home / "models" / ASTRABRIDGE_MODEL_CATALOG_FILENAME
        catalog_payload = {"models": [model]}
        write_json(catalog_path, catalog_payload)
        write_json(
            self.codex_home / ASTRABRIDGE_MODELS_CACHE_FILENAME,
            {
                "fetched_at": now_iso(),
                "etag": "astrabridge",
                "client_version": "0.137.0",
                "models": [model],
            },
        )
        return catalog_path


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _toml_key(value: str) -> str:
    return value if re.match(r"^[A-Za-z0-9_-]+$", value) else f'"{_toml_escape(value)}"'


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def codex_reasoning_effort(effort: Any) -> str:
    normalized = str(effort or "high").strip().lower()
    if normalized == "max":
        return "xhigh"
    if normalized in CODEX_REASONING_EFFORTS:
        return normalized
    return "high"


def codex_model_id(profile_or_runtime: dict[str, Any], model: Any | None = None) -> str:
    provider_id = str(profile_or_runtime.get("provider_id") or "").strip()
    native_model = str(model or profile_or_runtime.get("model") or "").strip()
    if not native_model:
        return native_model
    if "/" in native_model:
        return native_model
    return f"{provider_id}/{native_model}" if provider_id else native_model

