from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import re
import shlex
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from .app_server_client import AppServerClient, JsonRpcError
from .coding_kernel import project_turn_to_coding_events
from .common import WORKSPACE_STATE_DIRNAME, append_jsonl, new_id, now_iso, read_json, write_json
from .dogfood_run_service import MAX_BROWSER_SMOKE_ACTIONS
from .lcr_web_mcp_server import _tools as lcr_web_dynamic_tools
from .lcr_web_service import LcrWebService
from .mcp_config_service import McpConfigService
from .modal_service import ModalService
from .model_catalog import (
    ASTRABRIDGE_MODELS_CACHE_FILENAME,
    ASTRABRIDGE_MODEL_CATALOG_FILENAME,
    preferred_provider_model_record,
)
from .profile_service import ProfileService
from .providers import HistoryProjector, NeutralMessage, ReasoningArtifact, classify_runtime_failure
from .router_service import ROUTER_ENV_KEY, ROUTER_PORT
from .runtime_config_service import RuntimeConfigService, codex_model_id, codex_reasoning_effort
from .security import SecurityError, redact_sensitive, resolve_under, scan_text_for_secrets
from .secret_service import SecretService
from .task_service import _display_thread_name
from .tool_context_service import ToolContextService, sanitize_tool_context
from .wsl_dependency_service import ASTRABRIDGE_WSL_BIN, ASTRABRIDGE_WSL_CODEX_HOME, ASTRABRIDGE_WSL_ROOT
from .yunwu_image_mcp_server import _summarize_image_result as summarize_yunwu_image_result
from .yunwu_image_mcp_server import _tools as yunwu_image_dynamic_tools
from .yunwu_image_service import YunwuImageService


EVENT_RESPONSE_STRING_LIMIT = 4000
EVENT_RESPONSE_LIST_LIMIT = 40
EVENT_RESPONSE_DEPTH_LIMIT = 6
EVENT_HYDRATE_TAIL_LIMIT = 5000
EVENT_HYDRATE_MAX_BYTES = 4 * 1024 * 1024
APP_SERVER_INIT_TIMEOUT_SECONDS = 20.0
THREAD_START_TIMEOUT_SECONDS = 20.0
THREAD_FORK_TIMEOUT_SECONDS = 20.0
THREAD_READ_TIMEOUT_SECONDS = 20.0
THREAD_LIST_TIMEOUT_SECONDS = 20.0
TURN_START_TIMEOUT_SECONDS = 45.0
TURN_RUNTIME_PIN_SECONDS = 300.0
VALID_COLLABORATION_MODES = {"default", "plan"}
VALID_CONTEXT_MODES = {"default", "full", "minimal_text", "minimal_visual", "no_context"}
VALID_EXECUTION_BACKENDS = {"app_server", "native_kernel"}
BROWSER_SMOKE_TOOL_NAME = "astrabridge_browser_smoke"
LEGACY_BROWSER_SMOKE_TOOL_NAME = "lcr_browser_smoke"
BROWSER_SMOKE_TOOL_ALIASES = {BROWSER_SMOKE_TOOL_NAME, LEGACY_BROWSER_SMOKE_TOOL_NAME}
_OPENAI_DEFAULT_MODEL = str(
    (preferred_provider_model_record("openai", include_deprecated=False) or {}).get("native_model") or "gpt-5.5"
)


class RuntimeService:
    def __init__(
        self,
        project_service,
        modal_service: ModalService,
        runtime_config: RuntimeConfigService | None = None,
        secret_service: SecretService | None = None,
        mcp_config: McpConfigService | None = None,
        asset_registry: Any | None = None,
        project_context: Any | None = None,
        task_service: Any | None = None,
        task_conversation: Any | None = None,
        dogfood_run: Any | None = None,
        lcr_web_service: Any | None = None,
        profile_service: ProfileService | None = None,
        router_service: Any | None = None,
    ) -> None:
        self._projects = project_service
        self._modals = modal_service
        self._secrets = secret_service or SecretService()
        self._mcp_config = mcp_config or getattr(runtime_config, "_mcp_config", None) or McpConfigService()
        self._asset_registry = asset_registry
        self._project_context = project_context
        self._tasks = task_service
        self._task_conversation = task_conversation
        self._dogfood_run = dogfood_run
        self._lcr_web = lcr_web_service or LcrWebService(project_service)
        self._tool_context = ToolContextService(project_service, task_service)
        codex_home_resolver = getattr(self._projects, "current_runtime_codex_home", None)
        self._runtime_config = runtime_config or RuntimeConfigService(
            codex_home_resolver=codex_home_resolver if callable(codex_home_resolver) else None,
            secret_service=self._secrets,
            mcp_config=self._mcp_config,
        )
        self._profiles = profile_service or ProfileService()
        self._router = router_service
        self._project_tools = None
        self._native_turn_loop = None
        self._client: AppServerClient | None = None
        self._runtime_signature: tuple[Any, ...] | None = None
        self._events: list[dict[str, Any]] = []
        self._hydrated_event_log_path: Path | None = None
        self._context_guard_continue_once: set[str] = set()
        self._yunwu_image = YunwuImageService()
        self._lock = threading.RLock()
        self._thread_cache_lock = threading.RLock()
        self._runtime_operation_lock = threading.RLock()
        self._runtime_operation_local = threading.local()
        self._runtime_start_turn_in_progress = False
        self._runtime_thread_start_in_progress = False
        self._runtime_pin_signature: tuple[Any, ...] | None = None
        self._runtime_pin_until_monotonic = 0.0
        self._runtime_pin_thread_id: str | None = None
        self._runtime_pin_turn_id: str | None = None

    def attach_router(self, router_service: Any) -> None:
        self._router = router_service
        self._initialize_native_turn_loop()

    def attach_project_tools(self, project_tools: Any) -> None:
        self._project_tools = project_tools
        self._initialize_native_turn_loop()

    def _initialize_native_turn_loop(self) -> None:
        if self._router is None or self._project_tools is None:
            return
        if self._native_turn_loop is not None:
            return
        from .coding_kernel import NativeCodingTurnLoop

        self._native_turn_loop = NativeCodingTurnLoop(self, self._router, self._project_tools)

    def environment(self) -> dict[str, Any]:
        execution_host = self._execution_host()
        codex_executable = self._launch_descriptor()
        return {
            "codex_cli": codex_executable,
            "execution_host": execution_host,
            "wsl_distro": self._wsl_distro(),
            "running": self._client.is_running() if self._client else False,
            "runtime_config": {
                **self._runtime_config.status(),
                "execution_host": execution_host,
                "wsl_distro": self._wsl_distro(),
            },
        }

    def restart(self) -> dict[str, Any]:
        self._close_client("manual_restart")
        return self.environment()

    def restore_startup_runtime(self, profile: dict[str, Any] | None, *, thread_id: str | None = None) -> dict[str, Any]:
        if not profile:
            return {"restored": False, "reason": "no_profile"}
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        result: dict[str, Any] = {
            "restored": True,
            "runtime": runtime_status,
            "client_started": False,
            "thread_id": str(thread_id or "").strip() or None,
            "thread_exists": None,
            "reconciled_thread_id": None,
        }
        try:
            client = self._ensure_client(runtime_status)
            result["client_started"] = client.is_running()
        except Exception as exc:  # noqa: BLE001
            result["client_error"] = str(exc)[:300]
            self._record_event(
                {
                    "type": "startup_runtime_restored",
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "secret_loaded": runtime_status.get("secret_loaded"),
                    "client_started": False,
                    "thread_id": result.get("thread_id"),
                    "thread_exists": None,
                    "error": result["client_error"],
                }
            )
            return result
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id and self._tasks is not None:
            recovery_hint = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
            clean_thread_id = str(recovery_hint.get("thread_id") or "").strip()
            result["thread_id"] = clean_thread_id or None
        if clean_thread_id:
            exists = self._thread_exists(client, clean_thread_id)
            result["thread_exists"] = exists
            if not exists:
                self._mark_provider_thread_missing(clean_thread_id, reason="startup_thread_missing")
                current_project = self._projects.current_project or {}
                reconciled_thread_id = str(current_project.get("current_thread_id") or "").strip()
                if reconciled_thread_id and reconciled_thread_id != clean_thread_id:
                    result["reconciled_thread_id"] = reconciled_thread_id
                else:
                    result["reconciled_thread_id"] = None
                if not result["reconciled_thread_id"]:
                    try:
                        recovered_thread_id = self._recover_startup_provider_thread(
                            client,
                            missing_thread_id=clean_thread_id,
                            profile=profile,
                            runtime_status=runtime_status,
                        )
                    except Exception as exc:  # noqa: BLE001
                        result["recovery_error"] = str(exc)[:300]
                    else:
                        result["recovered_thread_id"] = recovered_thread_id
                        result["reconciled_thread_id"] = recovered_thread_id
        self._record_event(
            {
                "type": "startup_runtime_restored",
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "secret_loaded": runtime_status.get("secret_loaded"),
                "client_started": result.get("client_started"),
                "thread_id": result.get("thread_id"),
                "thread_exists": result.get("thread_exists"),
                "reconciled_thread_id": result.get("reconciled_thread_id"),
            }
        )
        return result

    def _recover_startup_provider_thread(
        self,
        client: AppServerClient,
        *,
        missing_thread_id: str,
        profile: dict[str, Any],
        runtime_status: dict[str, Any],
    ) -> str:
        if self._tasks is None:
            raise RuntimeError("Task continuity is unavailable.")
        if runtime_status.get("secret_loaded") is False:
            raise RuntimeError("Runtime secret is unavailable; startup cannot recover the missing provider thread yet.")
        recovery_hint = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
        permission_mode = str(recovery_hint.get("permission_mode") or "auto")
        collaboration_mode = recovery_hint.get("collaboration_mode")
        model = str(recovery_hint.get("model") or profile.get("model") or "").strip() or None
        effort = str(recovery_hint.get("reasoning_effort") or profile.get("reasoning_effort") or "").strip() or None
        replacement_thread_id, _handoff_event = self._recover_missing_provider_thread(
            client,
            missing_thread_id=missing_thread_id,
            profile=profile,
            model=model,
            effort=effort,
            permission_mode=permission_mode,
            collaboration_mode=collaboration_mode,
            reason="startup_thread_missing",
        )
        return replacement_thread_id

    def load_secret(
        self,
        profile: dict[str, Any],
        session_key: str | None = None,
        key_file_path: str | None = None,
        persist_to_keychain: bool = False,
    ) -> dict[str, Any]:
        profile = dict(profile)
        if persist_to_keychain and session_key and profile.get("provider_id"):
            profile["secret_ref"] = self._secrets.store(str(profile.get("provider_id")), session_key)
            profile["auth_mode"] = "os_keychain"
        runtime_status = self._runtime_config.load_secret(profile, session_key=session_key, key_file_path=key_file_path)
        runtime_status["execution_host"] = self._execution_host()
        runtime_status["wsl_distro"] = self._wsl_distro()
        if profile.get("secret_ref"):
            runtime_status = {**runtime_status, "auth_mode": profile.get("auth_mode"), "secret_ref": profile.get("secret_ref")}
        self._update_project_runtime_defaults(profile, None, None)
        self._refresh_client_if_runtime_changed(runtime_status)
        self._record_event({"type": "runtime_secret_loaded", "runtime": runtime_status})
        return runtime_status

    def list_models(self, profile: dict[str, Any]) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        try:
            client = self._runtime_request_client(runtime_status)
            result = client.request("model/list", {"includeHidden": False, "limit": 200}, timeout=THREAD_LIST_TIMEOUT_SECONDS)
        except RuntimeError as exc:
            if "runtime_switch_deferred_start_turn" not in str(exc):
                raise
            self._record_event(
                {
                    "type": "models_list_deferred_start_turn",
                    "profile_id": profile.get("profile_id"),
                    "runtime": runtime_status,
                }
            )
            return {"models": [], "next_cursor": None, "warning": "runtime_switch_deferred_start_turn"}
        payload = {"models": list(result.get("data") or []), "next_cursor": result.get("nextCursor")}
        self._record_event({"type": "models_listed", "runtime": runtime_status, "count": len(payload["models"])})
        return payload

    def list_threads(self, profile: dict[str, Any], *, archived: bool = False) -> dict[str, Any]:
        if archived:
            return {"threads": [], "next_cursor": None, "backwards_cursor": None}
        runtime_status = self._runtime_status_for_profile(profile, require_secret=False)
        if self._runtime_switch_is_pinned(runtime_status):
            cached = self._cached_threads_response(archived=archived, warning="runtime_switch_deferred_active_turn")
            self._record_event(
                {
                    "type": "threads_list_deferred_active_turn",
                    "profile_id": profile.get("profile_id"),
                    "archived": archived,
                    "count": len(cached.get("threads") or []),
                    "runtime": runtime_status,
                }
            )
            return cached
        self._refresh_client_if_runtime_changed(runtime_status)
        cwd = self._runtime_workspace_root()
        try:
            client = self._ensure_client(runtime_status)
            result = client.request("thread/list", {"cwd": cwd, "archived": archived, "limit": 200}, timeout=THREAD_LIST_TIMEOUT_SECONDS)
        except Exception as exc:
            cached = self._cached_threads_response(archived=archived, warning=str(exc))
            self._record_event(
                {
                    "type": "threads_list_fallback",
                    "profile_id": profile.get("profile_id"),
                    "archived": archived,
                    "count": len(cached.get("threads") or []),
                    "error": str(exc),
                }
            )
            return cached
        threads = [self._decorate_thread(thread) for thread in list(result.get("data") or [])]
        if not threads:
            cached = self._cached_threads_response(archived=archived)
            if cached.get("threads"):
                self._record_event(
                    {
                        "type": "threads_list_cache_overlay",
                        "profile_id": profile.get("profile_id"),
                        "archived": archived,
                        "count": len(cached.get("threads") or []),
                    }
                )
                return cached
        self._projects.cache_threads(threads)
        native_threads = self._native_cached_threads()
        seen_ids = {str(thread.get("id") or "") for thread in threads}
        for native_thread in native_threads:
            native_id = str(native_thread.get("id") or "")
            if native_id and native_id not in seen_ids:
                threads.append(native_thread)
        self._record_event({"type": "threads_listed", "count": len(threads), "archived": archived})
        return {
            "threads": threads,
            "next_cursor": result.get("nextCursor"),
            "backwards_cursor": result.get("backwardsCursor"),
        }

    def read_thread(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        native_thread = self._read_native_thread(thread_id)
        if native_thread is not None:
            decorated = self._decorate_thread(native_thread)
            decorated = self._decorate_dynamic_tool_evidence(decorated)
            decorated = self._decorate_turn_coding_events(decorated)
            decorated = self._decorate_turn_completion_quality(decorated)
            self._record_task_thread_snapshot(decorated)
            return {"thread": decorated}
        runtime_status = self._runtime_status_for_profile(profile, require_secret=False)
        if self._runtime_switch_is_pinned(runtime_status):
            cached = self._cached_thread(thread_id, warning="runtime_switch_deferred_active_turn")
            if cached:
                self._record_task_thread_snapshot(cached)
                self._record_event(
                    {
                        "type": "thread_read_deferred_active_turn",
                        "thread_id": thread_id,
                        "profile_id": profile.get("profile_id"),
                        "runtime": runtime_status,
                    }
                )
                return {"thread": cached}
        self._refresh_client_if_runtime_changed(runtime_status)
        try:
            client = self._ensure_client(runtime_status)
            result = client.request("thread/read", {"threadId": thread_id, "includeTurns": True}, timeout=THREAD_READ_TIMEOUT_SECONDS)
        except Exception as exc:
            cached = self._cached_thread(thread_id, warning=str(exc))
            if cached:
                self._record_task_thread_snapshot(cached)
                self._record_event(
                    {
                        "type": "thread_read_fallback",
                        "thread_id": thread_id,
                        "profile_id": profile.get("profile_id"),
                        "error": str(exc),
                    }
                )
                return {"thread": cached}
            raise
        thread = self._decorate_thread(dict(result.get("thread") or {}))
        thread = self._overlay_dynamic_tool_events(thread)
        thread = self._decorate_dynamic_tool_evidence(thread)
        thread = self._decorate_turn_coding_events(thread)
        thread = self._decorate_turn_completion_quality(thread)
        normalized_status = self._normalize_thread_status(thread)
        if isinstance(normalized_status, dict):
            if normalized_status != thread.get("status"):
                thread = {**thread, "status": normalized_status}
            normalized_status = self._overlay_cached_thread_status(thread["id"], normalized_status)
            if normalized_status != thread.get("status"):
                thread = {**thread, "status": normalized_status}
        cache_patch: dict[str, Any] = {"name": thread.get("name")}
        if isinstance(thread.get("status"), dict):
            cache_patch["status"] = thread.get("status")
        self._cache_thread_entry(thread["id"], cache_patch)
        self._record_task_thread_snapshot(thread)
        return {"thread": thread}

    def _record_task_thread_snapshot(self, thread: dict[str, Any]) -> None:
        if self._tasks is not None:
            try:
                coding_events: list[dict[str, Any]] = []
                for turn in list(thread.get("turns") or []):
                    if not isinstance(turn, dict):
                        continue
                    for event in list(turn.get("coding_events") or []):
                        if isinstance(event, dict):
                            coding_events.append(event)
                if coding_events:
                    self._tasks.record_coding_events(coding_events)
            except Exception as exc:  # noqa: BLE001
                self._record_event(
                    {
                        "type": "task_coding_event_projection_failed",
                        "thread_id": str(thread.get("id") or thread.get("thread_id") or ""),
                        "error": str(exc)[:300],
                    }
                )
        if self._task_conversation is None:
            return
        try:
            self._task_conversation.record_thread_snapshot(thread)
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                {
                    "type": "task_thread_snapshot_failed",
                    "thread_id": str(thread.get("id") or thread.get("thread_id") or ""),
                    "error": str(exc)[:300],
                }
            )

    def create_thread(
        self,
        profile: dict[str, Any],
        *,
        model: str | None,
        effort: str | None,
        permission_mode: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        if not getattr(self._runtime_operation_local, "in_thread_start", False):
            with self._runtime_operation_lock:
                self._runtime_thread_start_in_progress = True
                self._runtime_operation_local.in_thread_start = True
                try:
                    return self.create_thread(
                        profile,
                        model=model,
                        effort=effort,
                        permission_mode=permission_mode,
                        name=name,
                    )
                finally:
                    self._runtime_operation_local.in_thread_start = False
                    self._runtime_thread_start_in_progress = False
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        client = self._runtime_request_client(runtime_status)
        params = self._thread_start_params(profile=profile, model=model, permission_mode=permission_mode)
        try:
            result = client.request("thread/start", params, timeout=THREAD_START_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            self._record_event({"type": "thread_create_timeout", "profile_id": profile.get("profile_id"), "runtime": runtime_status})
            raise RuntimeError(
                "Send is blocked at thread setup: Codex app-server did not create a thread in time. "
                "Check Codex login/runtime health and the selected model/provider settings."
            ) from exc
        thread = dict(result.get("thread") or {})
        thread_id = str(thread.get("id") or "")
        if not thread_id:
            raise RuntimeError("thread/start did not return a thread id.")
        if name and name.strip():
            client.request("thread/name/set", {"threadId": thread_id, "name": name.strip()})
            thread["name"] = name.strip()
        self._projects.switch_thread(thread_id)
        self._cache_thread_entry(
            thread_id,
            {
                "name": thread.get("name"),
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": model or profile.get("model"),
                "reasoning_effort": effort or profile.get("reasoning_effort"),
                "permission_mode": permission_mode,
            },
        )
        if self._tasks is not None:
            self._tasks.create_task(
                name or thread.get("name") or "New task",
                thread_id=thread_id,
                settings=self._task_thread_settings(profile, model, effort, permission_mode, name=thread.get("name")),
            )
        self._update_project_runtime_defaults(profile, model, effort)
        self._record_event({"type": "thread_created", "thread_id": thread_id, "runtime": runtime_status})
        try:
            return self.read_thread(profile, thread_id)
        except Exception as exc:
            self._record_event({"type": "thread_read_after_create_fallback", "thread_id": thread_id, "error": str(exc)})
            return {"thread": self._decorate_thread({**thread, "id": thread_id, "turns": list(thread.get("turns") or [])})}

    def fork_thread(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        model: str | None,
        effort: str | None,
        permission_mode: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        if not getattr(self._runtime_operation_local, "in_thread_start", False):
            with self._runtime_operation_lock:
                self._runtime_thread_start_in_progress = True
                self._runtime_operation_local.in_thread_start = True
                try:
                    return self.fork_thread(
                        profile,
                        thread_id=thread_id,
                        model=model,
                        effort=effort,
                        permission_mode=permission_mode,
                        name=name,
                    )
                finally:
                    self._runtime_operation_local.in_thread_start = False
                    self._runtime_thread_start_in_progress = False
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        client = self._ensure_client(runtime_status)
        params = {
            "threadId": thread_id,
            **self._thread_start_params(profile=profile, model=model, permission_mode=permission_mode),
        }
        try:
            result = client.request("thread/fork", params, timeout=THREAD_FORK_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            self._record_event({"type": "thread_fork_timeout", "thread_id": thread_id, "profile_id": profile.get("profile_id")})
            raise RuntimeError(
                "Fork is blocked at thread setup: Codex app-server did not fork the thread in time. "
                "Check runtime health and the active provider/model settings."
            ) from exc
        thread = dict(result.get("thread") or {})
        fork_id = str(thread.get("id") or "")
        if not fork_id:
            raise RuntimeError("thread/fork did not return a thread id.")
        if name and name.strip():
            client.request("thread/name/set", {"threadId": fork_id, "name": name.strip()})
            thread["name"] = name.strip()
        self._projects.switch_thread(fork_id)
        self._cache_thread_entry(
            fork_id,
            {
                "name": thread.get("name"),
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": model or profile.get("model"),
                "reasoning_effort": effort or profile.get("reasoning_effort"),
                "permission_mode": permission_mode,
            },
        )
        if self._tasks is not None:
            self._tasks.bind_thread(
                thread_id=fork_id,
                settings=self._task_thread_settings(profile, model, effort, permission_mode, name=thread.get("name")),
                role="fork",
                make_active=True,
            )
        self._update_project_runtime_defaults(profile, model, effort)
        self._record_event({"type": "thread_forked", "thread_id": fork_id, "from_thread_id": thread_id})
        try:
            return self.read_thread(profile, fork_id)
        except Exception as exc:
            self._record_event({"type": "thread_read_after_fork_fallback", "thread_id": fork_id, "error": str(exc)})
            return {"thread": self._decorate_thread({**thread, "id": fork_id, "turns": list(thread.get("turns") or [])})}

    def rename_thread(self, profile: dict[str, Any], thread_id: str, name: str) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        if not name.strip():
            raise ValueError("name is required.")
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        client.request("thread/name/set", {"threadId": thread_id, "name": name.strip()})
        self._cache_thread_entry(thread_id, {"name": name.strip()})
        self._record_event({"type": "thread_renamed", "thread_id": thread_id, "name": name.strip()})
        return {"thread_id": thread_id, "name": name.strip()}

    def archive_thread(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        client.request("thread/archive", {"threadId": thread_id})
        if (self._projects.current_project or {}).get("current_thread_id") == thread_id:
            self._projects.switch_thread(None)
        self._mark_provider_thread_missing(thread_id, reason="thread_archived")
        self._record_event({"type": "thread_archived", "thread_id": thread_id, "runtime": runtime_status})
        return {"archived": thread_id}

    def update_thread_defaults(
        self,
        *,
        thread_id: str,
        profile_id: str | None,
        model: str | None,
        effort: str | None,
        permission_mode: str | None,
        collaboration_mode: str | None = None,
    ) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        normalized = self._normalize_shell_settings(
            {
                "profile_id": profile_id,
                "model": model,
                "reasoning_effort": effort,
                "permission_mode": permission_mode,
                "collaboration_mode": collaboration_mode,
            },
            current_project=self._projects.current_project or {},
            prefer_project_defaults=False,
        )
        self._cache_thread_entry(
            thread_id,
            {
                "profile_id": normalized.get("profile_id"),
                "model": normalized.get("model"),
                "reasoning_effort": normalized.get("reasoning_effort"),
                "permission_mode": normalized.get("permission_mode"),
                "collaboration_mode": normalized.get("collaboration_mode"),
            },
        )
        if normalized.get("profile_id") or normalized.get("model") or normalized.get("reasoning_effort"):
            self._projects.update_project(
                {
                    **({"default_profile_id": normalized.get("profile_id")} if normalized.get("profile_id") else {}),
                    **({"default_model": normalized.get("model")} if normalized.get("model") else {}),
                    **({"default_effort": normalized.get("reasoning_effort")} if normalized.get("reasoning_effort") else {}),
                }
            )
        return self._thread_settings_for(thread_id)

    def get_goal(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        try:
            result = client.request("thread/goal/get", {"threadId": thread_id})
        except Exception as exc:
            if self._is_thread_not_found_error(exc):
                self._mark_provider_thread_missing(thread_id, reason="goal_thread_missing")
                self._record_event(
                    {
                        "type": "goal_thread_missing",
                        "thread_id": thread_id,
                        "profile_id": profile.get("profile_id"),
                    }
                )
                fallback_goal = None
                if self._tasks is not None:
                    try:
                        fallback_goal = (self._tasks.current_task() or {}).get("goal")
                    except Exception:
                        fallback_goal = None
                return {"goal": fallback_goal, "status": "thread_missing", "thread_id": thread_id}
            raise
        return {"goal": result.get("goal")}

    def set_goal(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        objective: str,
        token_budget: int | None,
    ) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        client.request(
            "thread/goal/set",
            {"threadId": thread_id, "objective": objective, "tokenBudget": token_budget},
        )
        if self._tasks is not None:
            self._tasks.record_goal(thread_id, {"objective": objective, "tokenBudget": token_budget})
        self._record_event({"type": "goal_set", "thread_id": thread_id, "token_budget": token_budget})
        return self.get_goal(profile, thread_id)

    def clear_goal(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        client.request("thread/goal/clear", {"threadId": thread_id})
        if self._tasks is not None:
            self._tasks.record_goal(thread_id, None)
        self._record_event({"type": "goal_cleared", "thread_id": thread_id})
        return {"goal": None}

    def start_turn(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        text: str,
        attachments: list[dict[str, Any]] | None,
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None = None,
        context_mode: str | None = None,
    ) -> dict[str, Any]:
        if not getattr(self._runtime_operation_local, "in_start_turn", False):
            with self._runtime_operation_lock:
                self._runtime_start_turn_in_progress = True
                self._runtime_operation_local.in_start_turn = True
                try:
                    return self.start_turn(
                        profile,
                        thread_id=thread_id,
                        text=text,
                        attachments=attachments,
                        model=model,
                        effort=effort,
                        permission_mode=permission_mode,
                        collaboration_mode=collaboration_mode,
                        context_mode=context_mode,
                    )
                finally:
                    self._runtime_operation_local.in_start_turn = False
                    self._runtime_start_turn_in_progress = False
        requested_thread_id = self._resolve_requested_thread_id(thread_id.strip() or self._visible_task_thread_id_hint())
        if not requested_thread_id:
            raise ValueError("thread_id is required.")
        normalized_context_mode = self._normalize_context_mode(context_mode)
        execution_backend = self._thread_execution_backend(requested_thread_id, profile)
        if execution_backend == "native_kernel":
            return self._start_native_turn(
                profile,
                thread_id=requested_thread_id,
                text=text,
                attachments=attachments or [],
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                collaboration_mode=collaboration_mode,
                context_mode=normalized_context_mode,
            )
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        client = self._ensure_client(runtime_status)

        def prepare_effective_thread(active_client: AppServerClient) -> tuple[str, dict[str, Any] | None]:
            force_fresh_context_thread = normalized_context_mode in {"minimal_text", "minimal_visual", "no_context"} and self._tasks is not None
            if force_fresh_context_thread:
                desired = self._task_thread_settings(
                    profile,
                    model,
                    effort,
                    permission_mode,
                    collaboration_mode=collaboration_mode,
                )
                reason = f"{normalized_context_mode}_fresh_thread"
                prepared_thread_id, prepared_handoff = self._start_fresh_provider_thread_for_turn(
                    active_client,
                    source_thread_id=requested_thread_id,
                    profile=profile,
                    model=model,
                    effort=effort,
                    permission_mode=permission_mode,
                    desired=desired,
                    reason=reason,
                )
            else:
                prepared_thread_id, prepared_handoff = self._ensure_provider_thread_for_turn(
                    active_client,
                    source_thread_id=requested_thread_id,
                    profile=profile,
                    model=model,
                    effort=effort,
                    permission_mode=permission_mode,
                    collaboration_mode=collaboration_mode,
                    context_mode=normalized_context_mode,
                )
            if normalized_context_mode == "minimal_visual" and self._tasks is not None:
                guard_state = self._context_guard_state(prepared_thread_id)
                if str(guard_state.get("level") or "") == "pause":
                    desired = self._task_thread_settings(
                        profile,
                        model,
                        effort,
                        permission_mode,
                        collaboration_mode=collaboration_mode,
                    )
                    prepared_thread_id, prepared_handoff = self._start_fresh_provider_thread_for_turn(
                        active_client,
                        source_thread_id=prepared_thread_id,
                        profile=profile,
                        model=model,
                        effort=effort,
                        permission_mode=permission_mode,
                        desired=desired,
                        reason="minimal_visual_hot_thread",
                    )
            self._raise_if_context_guard_blocks_turn(active_client, prepared_thread_id)
            return prepared_thread_id, prepared_handoff

        try:
            effective_thread_id, handoff_event = prepare_effective_thread(client)
        except RuntimeError as exc:
            if not self._is_app_server_transport_error(exc):
                raise
            self._record_event(
                {
                    "type": "turn_start_provider_thread_transport_retry",
                    "thread_id": requested_thread_id,
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "error": str(exc),
                }
            )
            self._close_client("turn_start_provider_thread_transport_retry")
            runtime_status = self._prepare_runtime(profile, require_secret=True)
            client = self._ensure_client(runtime_status)
            effective_thread_id, handoff_event = prepare_effective_thread(client)
        inputs = self._build_user_inputs(
            text,
            attachments or [],
            thread_id=effective_thread_id,
            context_mode=normalized_context_mode,
            profile_id=str(profile.get("profile_id") or ""),
            provider_id=str(profile.get("provider_id") or ""),
            model_id=str(model or profile.get("model") or ""),
        )
        params = {
            "threadId": effective_thread_id,
            "input": inputs,
            "cwd": self._runtime_workspace_root(),
            "approvalsReviewer": "user",
            "model": codex_model_id(profile, model),
            "effort": codex_reasoning_effort(effort or profile.get("reasoning_effort")),
            **self._turn_permission_overrides(permission_mode),
        }
        mode_params = self._collaboration_mode_params(
            profile=profile,
            model=model,
            effort=effort,
            collaboration_mode=collaboration_mode,
        )
        if mode_params:
            params["collaborationMode"] = mode_params
        try:
            result = client.request("turn/start", params, timeout=TURN_START_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            return self._turn_start_background_pending_response(
                exc,
                effective_thread_id=effective_thread_id,
                handoff_event=handoff_event,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                collaboration_mode=collaboration_mode,
                context_mode=normalized_context_mode,
                runtime_status=runtime_status,
                attachments=attachments or [],
            )
        except JsonRpcError as exc:
            if not self._is_thread_not_found_error(exc):
                raise
            self._mark_provider_thread_missing(effective_thread_id, reason="turn_start_thread_missing")
            effective_thread_id, handoff_event = self._recover_missing_provider_thread(
                client,
                missing_thread_id=effective_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                collaboration_mode=collaboration_mode,
                reason="turn_start_thread_missing",
            )
            inputs = self._build_user_inputs(
                text,
                attachments or [],
                thread_id=effective_thread_id,
                context_mode=normalized_context_mode,
                profile_id=str(profile.get("profile_id") or ""),
                provider_id=str(profile.get("provider_id") or ""),
                model_id=str(model or profile.get("model") or ""),
            )
            params["threadId"] = effective_thread_id
            params["input"] = inputs
            try:
                result = client.request("turn/start", params, timeout=TURN_START_TIMEOUT_SECONDS)
            except TimeoutError as retry_exc:
                return self._turn_start_background_pending_response(
                    retry_exc,
                    effective_thread_id=effective_thread_id,
                    handoff_event=handoff_event,
                    profile=profile,
                    model=model,
                    effort=effort,
                    permission_mode=permission_mode,
                    collaboration_mode=collaboration_mode,
                    context_mode=normalized_context_mode,
                    runtime_status=runtime_status,
                    attachments=attachments or [],
                )
        except RuntimeError as exc:
            if not self._is_app_server_transport_error(exc):
                raise
            self._record_event(
                {
                    "type": "turn_start_transport_retry",
                    "thread_id": effective_thread_id,
                    "profile_id": profile.get("profile_id"),
                    "provider_id": profile.get("provider_id"),
                    "error": str(exc),
                }
            )
            self._close_client("turn_start_transport_retry")
            client = self._runtime_request_client(runtime_status)
            result = client.request("turn/start", params, timeout=TURN_START_TIMEOUT_SECONDS)
        turn = dict(result.get("turn") or {})
        self._pin_runtime_for_turn(runtime_status, effective_thread_id, str(turn.get("id") or ""))
        self._projects.switch_thread(effective_thread_id)
        if self._tasks is not None:
            self._tasks.force_visible_provider_thread(effective_thread_id)
        self._cache_thread_entry(
            effective_thread_id,
            {
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": model or profile.get("model"),
                "reasoning_effort": effort or profile.get("reasoning_effort"),
                "permission_mode": permission_mode,
                "collaboration_mode": collaboration_mode or "default",
            },
        )
        self._update_project_runtime_defaults(profile, model, effort)
        self._record_event(
            {
                "type": "turn_started_request",
                "thread_id": effective_thread_id,
                "turn_id": turn.get("id"),
                "runtime": runtime_status,
                "attachments": [{"name": item.get("name"), "kind": item.get("kind")} for item in attachments or []],
                "collaboration_mode": collaboration_mode or "default",
                "context_mode": normalized_context_mode,
            }
        )
        return {"turn": turn, "thread_id": effective_thread_id, "handoff": handoff_event}

    def _resolve_requested_thread_id(self, thread_id: str) -> str:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id.startswith("task:") or self._tasks is None:
            return clean_thread_id
        hint = self._tasks.visible_provider_thread_id(include_missing_fallback=True)
        return str(hint or clean_thread_id).strip()

    def _thread_execution_backend(self, thread_id: str, profile: dict[str, Any]) -> str:
        settings = self._thread_settings_for(thread_id) if thread_id else {}
        profile_backend = profile.get("execution_backend")
        return self._normalize_execution_backend(settings.get("execution_backend") or profile_backend)

    def _native_kernel_enabled(self) -> bool:
        raw = str(os.environ.get("ASTRABRIDGE_ENABLE_NATIVE_KERNEL") or "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _start_native_turn(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        text: str,
        attachments: list[dict[str, Any]],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        context_mode: str,
    ) -> dict[str, Any]:
        if not self._native_kernel_enabled():
            raise RuntimeError("Native kernel execution is disabled. Set ASTRABRIDGE_ENABLE_NATIVE_KERNEL=1 to enable it.")
        if self._native_turn_loop is None:
            raise RuntimeError("Native kernel dependencies are not attached.")
        result = self._native_turn_loop.run_turn(
            thread_id=thread_id,
            profile=profile,
            text=text,
            attachments=attachments,
            model=model,
            effort=effort,
            permission_mode=permission_mode,
            collaboration_mode=collaboration_mode,
            context_mode=context_mode,
        )
        self._cache_thread_entry(thread_id, result.thread_cache_patch)
        self._projects.switch_thread(thread_id)
        if self._tasks is not None:
            self._tasks.force_visible_provider_thread(thread_id)
        self._update_project_runtime_defaults(profile, model, effort)
        self._record_task_thread_snapshot(result.thread)
        self._record_event(
            {
                "type": "native_turn_completed",
                "thread_id": thread_id,
                "turn_id": result.turn.get("id"),
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": model or profile.get("model"),
                "context_mode": context_mode,
            }
        )
        return {"turn": result.turn, "thread_id": thread_id, "handoff": result.handoff}

    def _turn_start_background_pending_response(
        self,
        exc: TimeoutError,
        *,
        effective_thread_id: str,
        handoff_event: dict[str, Any] | None,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        context_mode: str,
        runtime_status: dict[str, Any],
        attachments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        synthetic_turn = {
            "id": new_id("pending-turn"),
            "status": "starting",
            "synthetic": True,
            "background_start": True,
        }
        self._projects.switch_thread(effective_thread_id)
        self._cache_thread_entry(
            effective_thread_id,
            {
                "profile_id": profile.get("profile_id"),
                "provider_id": profile.get("provider_id"),
                "model": model or profile.get("model"),
                "reasoning_effort": effort or profile.get("reasoning_effort"),
                "permission_mode": permission_mode,
                "collaboration_mode": collaboration_mode or "default",
            },
        )
        self._update_project_runtime_defaults(profile, model, effort)
        self._record_event(
            {
                "type": "turn_start_background_pending",
                "thread_id": effective_thread_id,
                "synthetic_turn_id": synthetic_turn["id"],
                "profile_id": profile.get("profile_id"),
                "model": model or profile.get("model"),
                "runtime": runtime_status,
                "attachments": [{"name": item.get("name"), "kind": item.get("kind")} for item in attachments],
                "collaboration_mode": collaboration_mode or "default",
                "context_mode": context_mode,
                "warning": (
                    "app-server did not answer turn/start before the sidecar timeout; "
                    "the turn may still be running and should be tracked through runtime events."
                ),
            }
        )
        return {
            "turn": synthetic_turn,
            "thread_id": effective_thread_id,
            "handoff": handoff_event,
            "background_start": True,
            "warning": str(exc),
        }

    def compact_thread(self, profile: dict[str, Any], thread_id: str) -> dict[str, Any]:
        if not thread_id.strip():
            raise ValueError("thread_id is required.")
        runtime_status = self._prepare_runtime(profile, require_secret=True)
        client = self._ensure_client(runtime_status)
        try:
            client.request("thread/compact/start", {"threadId": thread_id})
        except JsonRpcError as exc:
            message = str(exc)
            if self._is_thread_not_found_error(exc):
                failure = classify_runtime_failure(
                    '{"error":{"message":"provider thread missing","type":"runtime_error"}}',
                    current_provider=str(profile.get("provider_id") or ""),
                    current_model=str(profile.get("model") or ""),
                ).to_payload()
                self._mark_provider_thread_missing(thread_id, reason="compact_thread_not_found")
                self._record_event(
                    {
                        "type": "thread_compact_blocked",
                        "thread_id": thread_id,
                        "status": "thread_missing",
                        "reason": "thread_not_found",
                        "failure": failure,
                        "runtime": runtime_status,
                    }
                )
                return {
                    "started": False,
                    "thread_id": thread_id,
                    "status": "thread_missing",
                    "recoverable": True,
                    "recommended_action": failure.get("recommended_action") or "restart_runtime_lane",
                    "recommended_actions": list(failure.get("recommended_actions") or []),
                    "recoverability": failure.get("recoverability") or "recoverable",
                    "message": " ".join(
                        part
                        for part in [
                            str(failure.get("summary") or "").strip(),
                            str(failure.get("actionable_hint") or "").strip(),
                        ]
                        if part
                    ).strip(),
                }
            raise
        self._record_event({"type": "thread_compact_requested", "thread_id": thread_id, "runtime": runtime_status})
        return {"started": True, "thread_id": thread_id}

    def allow_context_guard_continue_once(self, thread_id: str) -> dict[str, Any]:
        clean_thread_id = thread_id.strip()
        if not clean_thread_id:
            raise ValueError("thread_id is required.")
        self._context_guard_continue_once.add(clean_thread_id)
        self._record_event({"type": "context_guard_continue_once_allowed", "thread_id": clean_thread_id})
        return {"allowed": True, "thread_id": clean_thread_id}

    def reload_mcp_servers(self, profile: dict[str, Any]) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        result = client.request("config/mcpServer/reload", None)
        self._record_event({"type": "mcp_reloaded", "runtime": runtime_status})
        return {"reloaded": True, "result": result}

    def list_mcp_status(self, profile: dict[str, Any], *, thread_id: str | None = None, detail: str = "toolsAndAuthOnly") -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        params = {"limit": 100, "detail": detail if detail in {"full", "toolsAndAuthOnly"} else "toolsAndAuthOnly"}
        if thread_id:
            params["threadId"] = thread_id
        result = client.request("mcpServerStatus/list", params)
        self._record_event({"type": "mcp_status_listed", "count": len(result.get("data") or []), "runtime": runtime_status})
        return {"servers": list(result.get("data") or []), "next_cursor": result.get("nextCursor")}

    def call_mcp_tool(
        self,
        profile: dict[str, Any],
        *,
        thread_id: str,
        server: str,
        tool: str,
        arguments: Any | None = None,
        preserve_active_thread: bool = True,
    ) -> dict[str, Any]:
        if not server.strip() or not tool.strip():
            raise ValueError("MCP server and tool are required.")
        tool_timeout = self._mcp_tool_timeout_seconds(server)
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        prior_project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "")
        prior_task_thread_id = ""
        prior_task_thread_settings: dict[str, Any] = {}
        restore_project_thread_id = prior_project_thread_id
        restore_task_thread_id = prior_task_thread_id
        if self._tasks is not None:
            prior_task = self._tasks.current_task() or {}
            prior_task_thread_id = str(prior_task.get("active_provider_thread_id") or "")
            restore_task_thread_id = prior_task_thread_id
            for item in list(prior_task.get("provider_threads") or []):
                if str(item.get("thread_id") or "") == prior_task_thread_id:
                    prior_task_thread_settings = dict(item)
                    break
        source_thread_id = (
            thread_id.strip()
            or str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
            or self._visible_task_thread_id_hint()
        )
        if source_thread_id and not restore_task_thread_id:
            restore_task_thread_id = source_thread_id
        if source_thread_id and not restore_project_thread_id:
            restore_project_thread_id = source_thread_id
        effective_thread_id = self._resolve_thread_for_direct_mcp_call(
            client,
            source_thread_id=source_thread_id,
            profile=profile,
        )
        if source_thread_id:
            if self._tasks is not None:
                projected_task = self._tasks.current_task() or {}
                projected_task_thread_id = str(projected_task.get("active_provider_thread_id") or "")
                projected_project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "")
                if projected_task_thread_id or projected_project_thread_id:
                    if projected_task_thread_id != source_thread_id or projected_project_thread_id != source_thread_id:
                        restore_task_thread_id = projected_task_thread_id or restore_task_thread_id
                        restore_project_thread_id = projected_project_thread_id or projected_task_thread_id or restore_project_thread_id
            else:
                projected_project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "")
                if projected_project_thread_id != source_thread_id:
                    restore_project_thread_id = projected_project_thread_id
        handoff_event: dict[str, Any] | None = None
        try:
            result = client.request(
                "mcpServer/tool/call",
                {"threadId": effective_thread_id, "server": server, "tool": tool, "arguments": arguments or {}},
                timeout=tool_timeout,
            )
        except JsonRpcError as exc:
            if not self._is_thread_not_found_error(exc):
                raise
            self._record_event(
                {
                    "type": "mcp_tool_thread_missing",
                    "thread_id": effective_thread_id,
                    "source_thread_id": source_thread_id,
                    "server": server,
                    "tool": tool,
                }
            )
            recovered_thread_id = self._resolve_thread_for_direct_mcp_call(
                client,
                source_thread_id=source_thread_id,
                profile=profile,
            )
            result = client.request(
                "mcpServer/tool/call",
                {"threadId": recovered_thread_id, "server": server, "tool": tool, "arguments": arguments or {}},
                timeout=tool_timeout,
            )
            effective_thread_id = recovered_thread_id
        usage_delta = self._record_yunwu_image_usage_from_tool_result(server=server, tool=tool, result=result)
        self._record_event(
            {
                "type": "mcp_tool_called",
                "server": server,
                "tool": tool,
                "thread_id": effective_thread_id,
                "source_thread_id": source_thread_id,
                "handoff_event": handoff_event,
                "usage_delta": usage_delta,
                "runtime": runtime_status,
            }
        )
        if preserve_active_thread:
            self._restore_active_thread_after_direct_mcp_tool_call(
                project_thread_id=restore_project_thread_id,
                task_thread_id=restore_task_thread_id,
                task_thread_settings=prior_task_thread_settings,
            )
        return {"result": result, "thread_id": effective_thread_id, "handoff_event": handoff_event, "usage_delta": usage_delta}

    def _restore_active_thread_after_direct_mcp_tool_call(
        self,
        *,
        project_thread_id: str,
        task_thread_id: str,
        task_thread_settings: dict[str, Any],
    ) -> None:
        """Direct tools may need an internal runtime thread, but must not steal UI focus."""
        restored: dict[str, str] = {}
        if project_thread_id:
            try:
                self._projects.switch_thread(project_thread_id)
                restored["project_thread_id"] = project_thread_id
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "mcp_tool_project_thread_restore_failed", "thread_id": project_thread_id, "error": str(exc)[:300]})
        if self._tasks is not None and task_thread_id:
            try:
                self._tasks.restore_active_provider_thread(task_thread_id)
                restored_task = self._tasks.current_task()
                if str((restored_task or {}).get("active_provider_thread_id") or "").strip() != task_thread_id:
                    self._tasks.force_visible_provider_thread(task_thread_id)
                    restored_task = self._tasks.current_task()
                restored["task_thread_id"] = task_thread_id
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "mcp_tool_task_thread_restore_failed", "thread_id": task_thread_id, "error": str(exc)[:300]})
        if task_thread_id and not str((self._projects.current_project or {}).get("current_thread_id") or "").strip():
            try:
                self._projects.switch_thread(task_thread_id)
                restored.setdefault("project_thread_id", task_thread_id)
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "mcp_tool_project_thread_fallback_restore_failed", "thread_id": task_thread_id, "error": str(exc)[:300]})
        if restored:
            self._record_event({"type": "mcp_tool_active_thread_restored", **restored})
        if self._tasks is not None:
            try:
                current_task = self._tasks.current_task() or {}
                if current_task:
                    self._projects.reconcile_task_projection(current_task)
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "mcp_tool_task_projection_reconcile_failed", "error": str(exc)[:300]})

    def _resolve_thread_for_direct_mcp_call(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
    ) -> str:
        """Find or create an internal app-server thread for direct tool calls.

        Direct MCP calls are UI/supervisor actions, not provider switches. They
        may need a thread id because the app-server API requires one, but that
        thread must not become part of the user-visible task/provider-thread
        graph. Otherwise image generation, web research, or browser smoke can
        make a task look like it switched models or lost its active thread.
        """
        clean_source = source_thread_id.strip()
        result = client.request(
            "thread/start",
            self._thread_start_params(profile=profile, model=None, permission_mode="auto"),
            timeout=THREAD_START_TIMEOUT_SECONDS,
        )
        thread = dict(result.get("thread") or {})
        target_thread_id = str(thread.get("id") or "")
        if not target_thread_id:
            raise RuntimeError("thread/start did not return a thread id for MCP tool call.")
        self._record_event(
            {
                "type": "mcp_tool_internal_thread_started",
                "thread_id": target_thread_id,
                "source_thread_id": clean_source,
                "reason": "direct_tool_context_isolated",
            }
        )
        return target_thread_id

    def _visible_task_thread_id_hint(self) -> str:
        if self._tasks is None:
            return ""
        try:
            return str(self._tasks.visible_provider_thread_id(include_missing_fallback=True) or "").strip()
        except Exception:
            return ""

    def _mcp_tool_timeout_seconds(self, server: str) -> float:
        try:
            for item in self._mcp_config.enabled_servers():
                if str(item.get("name") or "") != server:
                    continue
                return max(float(item.get("tool_timeout_sec") or 120.0), 1.0)
        except Exception:
            return 120.0
        return 120.0

    def _ensure_provider_thread_for_mcp_call(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
        force_fresh: bool = False,
    ) -> tuple[str, dict[str, Any] | None]:
        """Return an isolated internal thread for direct tool calls.

        Kept as a compatibility wrapper for older call sites. Direct MCP/tool
        calls must not become provider handoffs and must not mark the visible
        source thread missing when the tool runtime belongs to another provider.
        """
        del force_fresh
        return self._resolve_thread_for_direct_mcp_call(client, source_thread_id=source_thread_id, profile=profile), None

    def _record_yunwu_image_usage_from_tool_result(self, *, server: str, tool: str, result: Any) -> dict[str, int]:
        if server != "yunwu_image" and not tool.startswith("yunwu_image_"):
            return {}
        self._refresh_asset_registry_after_yunwu_tool(tool=tool)
        actual_n = self._extract_yunwu_actual_n(result)
        if actual_n <= 0:
            return {}
        delta = {"yunwu_images": actual_n}
        if self._dogfood_run is not None:
            try:
                self._dogfood_run.record_usage(delta)
            except Exception as exc:  # noqa: BLE001
                self._record_event({"type": "dogfood_usage_record_failed", "delta": delta, "error": str(exc)[:300]})
        return delta

    def _refresh_asset_registry_after_yunwu_tool(self, *, tool: str) -> None:
        if self._asset_registry is None:
            return
        try:
            response = self._asset_registry.rebuild()
            registry = dict(response.get("registry") or {})
            assets = list(registry.get("assets") or [])
            self._record_event(
                {
                    "type": "asset_registry_refreshed",
                    "source": "yunwu_image_tool",
                    "tool": tool,
                    "asset_count": len(assets),
                }
            )
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                {
                    "type": "asset_registry_refresh_failed",
                    "source": "yunwu_image_tool",
                    "tool": tool,
                    "error": str(exc)[:300],
                }
            )

    def _extract_yunwu_actual_n(self, result: Any) -> int:
        if isinstance(result, dict):
            direct = result.get("actual_n")
            if isinstance(direct, int):
                return max(0, direct)
            if isinstance(direct, str) and direct.isdigit():
                return int(direct)
            content = result.get("content")
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = str(item.get("text") or "")
                    actual_n = self._extract_actual_n_from_text(text)
                    if actual_n > 0:
                        return actual_n
        return 0

    @staticmethod
    def _extract_actual_n_from_text(text: str) -> int:
        if not text:
            return 0
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return 0
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return 0
        actual = payload.get("actual_n")
        if isinstance(actual, int):
            return max(0, actual)
        if isinstance(actual, str) and actual.isdigit():
            return int(actual)
        return 0

    def _update_project_runtime_defaults(self, profile: dict[str, Any], model: str | None, effort: str | None) -> None:
        self._projects.update_project(
            {
                "default_profile_id": profile.get("profile_id"),
                "default_model": model or profile.get("model"),
                "default_effort": effort or profile.get("reasoning_effort"),
            }
        )

    def _task_thread_settings(
        self,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        *,
        collaboration_mode: str | None = None,
        execution_backend: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        settings = {
            "name": name,
            "profile_id": profile.get("profile_id"),
            "provider_id": profile.get("provider_id"),
            "model": model or profile.get("model"),
            "reasoning_effort": effort or profile.get("reasoning_effort"),
            "permission_mode": permission_mode,
            "execution_backend": self._normalize_execution_backend(execution_backend or profile.get("execution_backend")),
        }
        if collaboration_mode is not None:
            settings["collaboration_mode"] = collaboration_mode or "default"
        return settings

    def _ensure_provider_thread_for_turn(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        context_mode: str = "default",
    ) -> tuple[str, dict[str, Any] | None]:
        if self._tasks is None:
            return source_thread_id, None
        desired = self._task_thread_settings(profile, model, effort, permission_mode, collaboration_mode=collaboration_mode)
        force_fresh_contextless_thread = context_mode == "no_context"
        self._tasks.ensure_default_task()
        source_thread_available = True
        handoff_needed = True
        if source_thread_id:
            self._tasks.ensure_default_task(thread_id=source_thread_id)
            handoff_needed = self._tasks.needs_provider_handoff(
                thread_id=source_thread_id,
                profile_id=str(desired.get("profile_id") or ""),
                model=str(desired.get("model") or ""),
                effort=str(desired.get("reasoning_effort") or ""),
            )
        if source_thread_id and not handoff_needed and not self._thread_exists(client, source_thread_id):
            source_thread_available = False
            self._mark_provider_thread_missing(source_thread_id, reason="provider_handoff_source_missing")
        if source_thread_available and source_thread_id and not handoff_needed:
            if not force_fresh_contextless_thread:
                self._tasks.bind_thread(thread_id=source_thread_id, settings=desired, role="provider", make_active=True)
                return source_thread_id, None

        if force_fresh_contextless_thread:
            return self._start_fresh_provider_thread_for_turn(
                client,
                source_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                desired=desired,
                reason="no_context_fresh_thread",
            )

        reusable = self._tasks.find_provider_thread(
            profile_id=str(desired.get("profile_id") or ""),
            provider_id=str(desired.get("provider_id") or ""),
            model=str(desired.get("model") or ""),
            effort=str(desired.get("reasoning_effort") or ""),
        )
        reusable_thread_id = str((reusable or {}).get("thread_id") or "")
        if reusable_thread_id and reusable_thread_id != source_thread_id:
            if self._thread_exists(client, reusable_thread_id):
                context_budget_report = self._project_context_budget_report(
                    thread_id=source_thread_id or reusable_thread_id,
                    profile_id=str(desired.get("profile_id") or ""),
                    provider_id=str(desired.get("provider_id") or ""),
                    model_id=str(desired.get("model") or ""),
                )
                handoff_event = self._tasks.record_provider_handoff(
                    from_thread_id=source_thread_id,
                    to_thread_id=reusable_thread_id,
                    settings={**desired, "name": reusable.get("name") or desired.get("name")},
                    reused_existing=True,
                    context_budget_report=context_budget_report,
                    **self._handoff_projection_kwargs(
                        source_thread_id=source_thread_id,
                        target_provider_id=str(desired.get("provider_id") or ""),
                    ),
                )
                self._projects.switch_thread(reusable_thread_id)
                self._record_event(
                    {
                        "type": "provider_handoff",
                        "from_thread_id": source_thread_id,
                        "to_thread_id": reusable_thread_id,
                        "profile_id": desired.get("profile_id"),
                        "provider_id": desired.get("provider_id"),
                        "model": desired.get("model"),
                        "reasoning_effort": desired.get("reasoning_effort"),
                        "reused_existing": True,
                    }
                )
                return reusable_thread_id, handoff_event
            self._mark_provider_thread_missing(reusable_thread_id, reason="provider_handoff_target_missing")

        if not source_thread_available:
            return self._recover_missing_provider_thread(
                client,
                missing_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                collaboration_mode=collaboration_mode,
                reason="provider_handoff_source_missing",
            )

        if not source_thread_id:
            return self._start_fresh_provider_thread_for_turn(
                client,
                source_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                desired=desired,
                reason="provider_handoff_no_source_thread",
            )

        if handoff_needed:
            # A provider switch is not the same as an official Codex fork in AstraBridge:
            # the target provider's app-server cannot reliably read or fork a
            # thread owned by the source provider runtime. Keep task continuity
            # through the AstraBridge task/project/asset context pack, and reserve
            # thread/fork for same-runtime forks.
            return self._start_fresh_provider_thread_for_turn(
                client,
                source_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                desired=desired,
                reason="provider_handoff_cross_provider_fresh_thread",
            )

        params = {
            "threadId": source_thread_id,
            **self._thread_start_params(profile=profile, model=model, permission_mode=permission_mode),
        }
        try:
            result = client.request("thread/fork", params, timeout=THREAD_FORK_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            self._record_event(
                {
                    "type": "provider_handoff_timeout",
                    "from_thread_id": source_thread_id,
                    "profile_id": desired.get("profile_id"),
                    "model": desired.get("model"),
                }
            )
            raise RuntimeError(
                "Provider switch is blocked: Codex app-server did not preserve the task context into the target provider thread in time."
            ) from exc
        except JsonRpcError as exc:
            if not self._is_thread_not_found_error(exc):
                raise
            self._mark_provider_thread_missing(source_thread_id, reason="provider_handoff_source_missing")
            return self._recover_missing_provider_thread(
                client,
                missing_thread_id=source_thread_id,
                profile=profile,
                model=model,
                effort=effort,
                permission_mode=permission_mode,
                collaboration_mode=collaboration_mode,
                reason="provider_handoff_source_missing",
            )
        thread = dict(result.get("thread") or {})
        target_thread_id = str(thread.get("id") or "")
        if not target_thread_id:
            raise RuntimeError("Provider handoff did not return a target thread id.")
        desired["name"] = thread.get("name") or desired.get("name")
        self._cache_thread_entry(target_thread_id, desired)
        context_budget_report = self._project_context_budget_report(
            thread_id=source_thread_id or target_thread_id,
            profile_id=str(desired.get("profile_id") or ""),
            provider_id=str(desired.get("provider_id") or ""),
            model_id=str(desired.get("model") or ""),
        )
        handoff_event = self._tasks.record_provider_handoff(
            from_thread_id=source_thread_id,
            to_thread_id=target_thread_id,
            settings=desired,
            reused_existing=False,
            context_budget_report=context_budget_report,
            **self._handoff_projection_kwargs(
                source_thread_id=source_thread_id,
                target_provider_id=str(desired.get("provider_id") or ""),
            ),
        )
        self._record_event(
            {
                "type": "provider_handoff",
                "from_thread_id": source_thread_id,
                "to_thread_id": target_thread_id,
                "profile_id": desired.get("profile_id"),
                "model": desired.get("model"),
                "reasoning_effort": desired.get("reasoning_effort"),
                "reused_existing": False,
            }
        )
        return target_thread_id, handoff_event

    def _start_fresh_provider_thread_for_turn(
        self,
        client: AppServerClient,
        *,
        source_thread_id: str,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        desired: dict[str, Any],
        reason: str,
    ) -> tuple[str, dict[str, Any] | None]:
        params = self._thread_start_params(profile=profile, model=model, permission_mode=permission_mode)
        result = client.request("thread/start", params, timeout=THREAD_START_TIMEOUT_SECONDS)
        thread = dict(result.get("thread") or {})
        target_thread_id = str(thread.get("id") or "")
        if not target_thread_id:
            raise RuntimeError("thread/start did not return a target thread id.")
        desired["name"] = thread.get("name") or desired.get("name")
        self._cache_thread_entry(target_thread_id, desired)
        context_budget_report = self._project_context_budget_report(
            thread_id=source_thread_id or target_thread_id,
            profile_id=str(desired.get("profile_id") or ""),
            provider_id=str(desired.get("provider_id") or ""),
            model_id=str(desired.get("model") or ""),
        )
        handoff_event = self._tasks.record_provider_handoff(
            from_thread_id=source_thread_id,
            to_thread_id=target_thread_id,
            settings=desired,
            reused_existing=False,
            context_budget_report=context_budget_report,
            **self._handoff_projection_kwargs(
                source_thread_id=source_thread_id,
                target_provider_id=str(desired.get("provider_id") or ""),
            ),
        )
        self._projects.switch_thread(target_thread_id)
        self._record_event(
            {
                "type": "provider_handoff",
                "from_thread_id": source_thread_id,
                "to_thread_id": target_thread_id,
                "profile_id": desired.get("profile_id"),
                "provider_id": desired.get("provider_id"),
                "model": desired.get("model"),
                "reasoning_effort": desired.get("reasoning_effort"),
                "reused_existing": False,
                "reason": reason,
            }
        )
        return target_thread_id, handoff_event

    def _recover_missing_provider_thread(
        self,
        client: AppServerClient,
        *,
        missing_thread_id: str,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        reason: str,
    ) -> tuple[str, dict[str, Any] | None]:
        desired = self._task_thread_settings(
            profile,
            model,
            effort,
            permission_mode,
            collaboration_mode=collaboration_mode,
            name="Recovered provider thread",
        )
        params = self._thread_start_params(profile=profile, model=model, permission_mode=permission_mode)
        result = client.request("thread/start", params, timeout=THREAD_START_TIMEOUT_SECONDS)
        thread = dict(result.get("thread") or {})
        target_thread_id = str(thread.get("id") or "")
        if not target_thread_id:
            raise RuntimeError("thread/start did not return a replacement thread id.")
        desired["name"] = thread.get("name") or desired.get("name")
        self._cache_thread_entry(target_thread_id, desired)
        handoff_event = None
        if self._tasks is not None:
            context_budget_report = self._project_context_budget_report(
                thread_id=missing_thread_id or target_thread_id,
                profile_id=str(desired.get("profile_id") or ""),
                provider_id=str(desired.get("provider_id") or ""),
                model_id=str(desired.get("model") or ""),
            )
            handoff_event = self._tasks.record_provider_handoff(
                from_thread_id=missing_thread_id,
                to_thread_id=target_thread_id,
                settings=desired,
                reused_existing=False,
                context_budget_report=context_budget_report,
                **self._handoff_projection_kwargs(
                    source_thread_id=missing_thread_id,
                    target_provider_id=str(desired.get("provider_id") or ""),
                ),
            )
        self._projects.switch_thread(target_thread_id)
        self._record_event(
            {
                "type": "provider_thread_recovered",
                "reason": reason,
                "missing_thread_id": missing_thread_id,
                "replacement_thread_id": target_thread_id,
                "profile_id": desired.get("profile_id"),
                "model": desired.get("model"),
                "reasoning_effort": desired.get("reasoning_effort"),
            }
        )
        return target_thread_id, handoff_event

    def interrupt_turn(self, profile: dict[str, Any], thread_id: str, turn_id: str) -> dict[str, Any]:
        runtime_status = self._prepare_runtime(profile, require_secret=False)
        client = self._ensure_client(runtime_status)
        resolved_turn_id = turn_id
        try:
            result = client.request("turn/interrupt", {"threadId": thread_id, "turnId": resolved_turn_id})
        except JsonRpcError as exc:
            if self._is_thread_not_found_error(exc):
                self._mark_provider_thread_missing(thread_id, reason="turn_interrupt_thread_missing")
                self._record_event(
                    {
                        "type": "provider_thread_missing",
                        "reason": "turn_interrupt_thread_missing",
                        "thread_id": thread_id,
                        "turn_id": resolved_turn_id,
                        "runtime": runtime_status,
                    }
                )
                return {
                    "interrupt": {
                        "ok": False,
                        "status": "thread_missing",
                        "thread_id": thread_id,
                        "turn_id": resolved_turn_id,
                    }
                }
            active_turn_id = self._active_turn_id_from_interrupt_error(str(exc))
            if not active_turn_id or active_turn_id == turn_id:
                raise
            self._record_event(
                {
                    "type": "turn_interrupt_retry",
                    "thread_id": thread_id,
                    "requested_turn_id": turn_id,
                    "active_turn_id": active_turn_id,
                    "runtime": runtime_status,
                }
            )
            resolved_turn_id = active_turn_id
            result = client.request("turn/interrupt", {"threadId": thread_id, "turnId": resolved_turn_id})
        self._record_event(
            {
                "type": "turn_interrupted",
                "thread_id": thread_id,
                "turn_id": resolved_turn_id,
                "requested_turn_id": turn_id,
                "runtime": runtime_status,
            }
        )
        cancelled_modals = self._modals.cancel_for_turn(
            thread_id,
            resolved_turn_id,
            reason="Turn was interrupted; pending approval is no longer actionable.",
        )
        return {"interrupt": result, "cancelled_modals": cancelled_modals}

    @staticmethod
    def _active_turn_id_from_interrupt_error(message: str) -> str | None:
        match = re.search(r"expected active turn id [0-9a-f-]+ but found ([0-9a-f-]+)", message, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def _is_thread_not_found_error(error: Exception) -> bool:
        message = str(error).lower()
        return (
            "thread not found" in message
            or "thread not loaded" in message
            or "invalid thread id" in message
        )

    def _thread_exists(self, client: AppServerClient, thread_id: str) -> bool:
        if not str(thread_id or "").strip():
            return False
        try:
            client.request("thread/read", {"threadId": thread_id, "includeTurns": False}, timeout=THREAD_READ_TIMEOUT_SECONDS)
            return True
        except JsonRpcError as exc:
            if self._is_thread_not_found_error(exc):
                return False
            raise

    def _mark_provider_thread_missing(self, thread_id: str, *, reason: str) -> None:
        if self._tasks is not None:
            try:
                self._tasks.mark_provider_thread_missing(thread_id, reason=reason)
            except Exception:
                pass
            try:
                self._tasks.current_task()
            except Exception:
                pass
        self._record_event(
            {
                "type": "provider_thread_missing",
                "reason": reason,
                "thread_id": thread_id,
            }
        )

    def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, Any]:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            if limit is not None and limit > 0 and after <= 0:
                start = max(0, len(self._events) - limit)
                events = self._events[start:]
            else:
                events = self._events[after:]
                if limit is not None and limit > 0:
                    events = events[:limit]
            cursor = len(self._events)
        return {"cursor": cursor, "events": [self._event_for_response(item) for item in events]}

    def _hydrate_events_from_disk_locked(self) -> None:
        try:
            shell_root = self._projects.require_shell_state_root()
        except Exception:
            return
        path = shell_root / "runtime_events.jsonl"
        if self._hydrated_event_log_path == path:
            return
        if not path.is_file():
            self._hydrated_event_log_path = path
            return
        loaded: deque[dict[str, Any]] = deque(maxlen=EVENT_HYDRATE_TAIL_LIMIT)
        try:
            size = path.stat().st_size
            with path.open("rb") as handle:
                if size > EVENT_HYDRATE_MAX_BYTES:
                    handle.seek(-EVENT_HYDRATE_MAX_BYTES, os.SEEK_END)
                payload = handle.read(EVENT_HYDRATE_MAX_BYTES + 1)
            lines = payload.decode("utf-8", errors="replace").splitlines()
            if size > EVENT_HYDRATE_MAX_BYTES and lines:
                lines = lines[1:]
            for line in lines[-EVENT_HYDRATE_TAIL_LIMIT:]:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    loaded.append(redact_sensitive(item))
        except Exception:
            return
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*list(loaded), *self._events]:
            fingerprint = json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            merged.append(item)
        self._events = merged
        for index, item in enumerate(self._events):
            item["index"] = index
        self._hydrated_event_log_path = path

    def record_supervisor_event(self, event: dict[str, Any]) -> None:
        self._record_event({"type": "runtime_supervisor", **event})

    def request_native_command_approval(
        self,
        *,
        thread_id: str,
        turn_id: str,
        command: str,
        cwd: str,
        reason: str,
    ) -> dict[str, Any]:
        return dict(
            self._modals.request(
                "item/commandExecution/requestApproval",
                {
                    "threadId": thread_id,
                    "turnId": turn_id,
                    "itemId": new_id("cmd"),
                    "command": command,
                    "cwd": cwd,
                    "reason": reason,
                },
            )
            or {}
        )

    def _raise_if_context_guard_blocks_turn(self, client: AppServerClient, thread_id: str) -> None:
        state = self._context_guard_state(thread_id)
        if state.get("level") == "compacting":
            self._record_event(
                {
                    "type": "context_guard_compaction_in_progress",
                    "thread_id": thread_id,
                    "turn_id": state.get("turn_id"),
                    "started_at": state.get("started_at"),
                }
            )
            raise RuntimeError("Context compaction is still running for this thread. Wait for compaction to finish before starting the next turn.")
        if state.get("level") != "pause":
            return
        if not self._thread_exists(client, thread_id):
            self._mark_provider_thread_missing(thread_id, reason="context_guard_thread_missing")
            return
        if thread_id in self._context_guard_continue_once:
            self._context_guard_continue_once.remove(thread_id)
            self._record_event(
                {
                    "type": "context_guard_continue_once_consumed",
                    "thread_id": thread_id,
                    "context_percent": state.get("context_percent"),
                    "turn_id": state.get("turn_id"),
                }
            )
            return
        self._record_event(
            {
                "type": "context_guard_turn_blocked",
                "thread_id": thread_id,
                "turn_id": state.get("turn_id"),
                "context_percent": state.get("context_percent"),
                "recommended_action": "compact",
            }
        )
        raise RuntimeError(
            "Context is above 90% for this thread. Compact context, fork/switch provider thread, "
            "or explicitly choose Continue once before starting another long turn."
        )

    def _context_guard_state(self, thread_id: str) -> dict[str, Any]:
        token = self._latest_context_token_usage(thread_id)
        if not token:
            return {"level": "ok", "context_percent": 0}
        token_at = token.get("last_updated_at")
        missing_at = self._latest_provider_thread_missing_timestamp(thread_id)
        if missing_at and (not token_at or self._timestamp_after(str(missing_at), str(token_at))):
            return {
                "level": "missing",
                "context_percent": token.get("context_percent"),
                "turn_id": token.get("turn_id"),
                "missing_at": missing_at,
            }
        compacted_at = self._latest_completed_compaction_timestamp(thread_id)
        if compacted_at and (not token_at or self._timestamp_after(str(compacted_at), str(token_at))):
            return {
                "level": "compacted",
                "context_percent": token.get("context_percent"),
                "turn_id": token.get("turn_id"),
            }
        running_compaction = self._latest_running_compaction(thread_id)
        if running_compaction:
            compaction_turn_id = str(running_compaction.get("turn_id") or "")
            if compaction_turn_id and compaction_turn_id == str(token.get("turn_id") or ""):
                return {
                    "level": "compacting",
                    "context_percent": token.get("context_percent"),
                    "turn_id": compaction_turn_id,
                    "started_at": running_compaction.get("started_at"),
                }
        percent = float(token.get("context_percent") or 0)
        return {
            "level": "pause" if percent >= 90 else "ok",
            "context_percent": percent,
            "turn_id": token.get("turn_id"),
            "last_updated_at": token_at,
        }

    def _latest_context_token_usage(self, thread_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        for event in reversed(events):
            if event.get("type") != "notification" or event.get("method") != "thread/tokenUsage/updated":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            usage = params.get("tokenUsage") or {}
            total = usage.get("total") or {}
            last = usage.get("last") or {}
            context_window = int(usage.get("modelContextWindow") or 0)
            cumulative_total_tokens = int(total.get("totalTokens") or 0)
            context_tokens = int(last.get("inputTokens") or last.get("totalTokens") or cumulative_total_tokens or 0)
            context_source = "last.inputTokens" if int(last.get("inputTokens") or 0) > 0 else (
                "last.totalTokens" if int(last.get("totalTokens") or 0) > 0 else "total.totalTokens"
            )
            percent = round((context_tokens / context_window) * 100, 1) if context_window > 0 else 0
            return {
                "total_tokens": context_tokens,
                "context_estimate_tokens": context_tokens,
                "context_estimate_source": context_source,
                "cumulative_total_tokens": cumulative_total_tokens,
                "context_window": context_window,
                "context_percent": percent,
                "turn_id": str(params.get("turnId") or ""),
                "last": last,
                "last_updated_at": event.get("timestamp"),
            }
        return None

    def _latest_completed_compaction_timestamp(self, thread_id: str) -> str | None:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        for event in reversed(events):
            if event.get("type") != "notification" or event.get("method") not in {"item/completed", "thread/compacted"}:
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            item = params.get("item") or {}
            if event.get("method") == "thread/compacted" or item.get("type") == "contextCompaction":
                return str(event.get("timestamp") or "")
        return None

    def _latest_running_compaction(self, thread_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        for event in reversed(events):
            if event.get("type") != "notification":
                continue
            params = event.get("params") or {}
            if thread_id and str(params.get("threadId") or "") != thread_id:
                continue
            method = str(event.get("method") or "")
            if method == "thread/compacted":
                return None
            item = params.get("item") or {}
            if item.get("type") != "contextCompaction":
                continue
            if method == "item/completed":
                return None
            if method == "item/started":
                return {
                    "turn_id": str(params.get("turnId") or ""),
                    "item_id": str(item.get("id") or ""),
                    "started_at": event.get("timestamp"),
                }
        return None

    def _latest_provider_thread_missing_timestamp(self, thread_id: str) -> str | None:
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        for event in reversed(events):
            if event.get("type") != "provider_thread_missing":
                continue
            if thread_id and str(event.get("thread_id") or "") != thread_id:
                continue
            return str(event.get("timestamp") or "")
        return None

    def _timestamp_after(self, left: str, right: str) -> bool:
        try:
            left_dt = datetime.fromisoformat(left.replace("Z", "+00:00"))
            right_dt = datetime.fromisoformat(right.replace("Z", "+00:00"))
            return left_dt > right_dt
        except Exception:
            return left > right

    def _prepare_runtime(self, profile: dict[str, Any], *, require_secret: bool) -> dict[str, Any]:
        with self._runtime_operation_lock:
            if self._should_defer_runtime_prepare(profile):
                self._record_event(
                    {
                        "type": "runtime_switch_deferred_start_turn",
                        "requested_runtime": self._runtime_defer_preview(profile),
                        "active_runtime_signature": list(self._runtime_signature or []),
                        "reason": "start_turn_in_progress_config_write_guard",
                    }
                )
                raise RuntimeError("runtime_switch_deferred_start_turn")
            runtime_status = self._runtime_status_for_profile(profile, require_secret=require_secret)
            self._refresh_client_if_runtime_changed(runtime_status)
            return runtime_status

    def _runtime_status_for_profile(self, profile: dict[str, Any], *, require_secret: bool) -> dict[str, Any]:
        deferred_runtime = self._deferred_active_runtime_status(profile)
        if deferred_runtime is not None:
            return deferred_runtime
        runtime_status = self._runtime_config.prepare_profile(profile, require_secret=require_secret)
        runtime_status["execution_host"] = self._execution_host()
        runtime_status["wsl_distro"] = self._wsl_distro()
        return runtime_status

    def _should_defer_runtime_prepare(self, profile: dict[str, Any]) -> bool:
        if not (self._runtime_start_turn_in_progress or self._runtime_thread_start_in_progress):
            return False
        if getattr(self._runtime_operation_local, "in_start_turn", False):
            return False
        if getattr(self._runtime_operation_local, "in_thread_start", False):
            return False
        active = self._runtime_config.status()
        if not active.get("configured"):
            return False
        return self._profile_targets_different_runtime(profile, active)

    def _deferred_active_runtime_status(self, profile: dict[str, Any]) -> dict[str, Any] | None:
        if getattr(self._runtime_operation_local, "in_start_turn", False):
            return None
        if getattr(self._runtime_operation_local, "in_thread_start", False):
            return None
        if not (self._runtime_start_turn_in_progress or self._runtime_thread_start_in_progress):
            return None
        active = self._runtime_config.status()
        if not active.get("configured"):
            return None
        if not self._profile_targets_different_runtime(profile, active):
            return None
        reason = "thread_start_in_progress_passive_status_guard" if self._runtime_thread_start_in_progress else "start_turn_in_progress_passive_status_guard"
        self._record_event(
            {
                "type": "runtime_switch_deferred_active_mutation",
                "requested_runtime": self._runtime_defer_preview(profile),
                "active_runtime_signature": list(self._runtime_signature or []),
                "reason": reason,
            }
        )
        return {
            **active,
            "execution_host": self._execution_host(),
            "wsl_distro": self._wsl_distro(),
        }

    def _profile_targets_different_runtime(self, profile: dict[str, Any], active: dict[str, Any]) -> bool:
        checks = (
            ("provider_id", "provider_id"),
            ("base_url", "base_url"),
            ("model", "model"),
            ("reasoning_effort", "reasoning_effort"),
            ("wire_api", "wire_api"),
        )
        for profile_key, active_key in checks:
            requested = str(profile.get(profile_key) or "").strip()
            current = str(active.get(active_key) or "").strip()
            if requested and current and requested != current:
                return True
        return False

    def _runtime_defer_preview(self, profile: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_id": profile.get("provider_id"),
            "model": profile.get("model"),
            "reasoning_effort": profile.get("reasoning_effort"),
            "wire_api": profile.get("wire_api"),
        }

    def _ensure_client(self, runtime_status: dict[str, Any]) -> AppServerClient:
        desired_signature = self._runtime_config.runtime_signature(runtime_status)
        with self._lock:
            if self._client is not None and self._client.is_running():
                if self._runtime_signature == desired_signature:
                    return self._client
                if (
                    (self._runtime_start_turn_in_progress and not getattr(self._runtime_operation_local, "in_start_turn", False))
                    or (self._runtime_thread_start_in_progress and not getattr(self._runtime_operation_local, "in_thread_start", False))
                ):
                    self._record_event(
                        {
                            "type": "runtime_switch_deferred_active_mutation",
                            "requested_runtime": runtime_status,
                            "active_runtime_signature": list(self._runtime_signature or []),
                            "reason": "runtime_request_during_active_mutation",
                        }
                    )
                    raise RuntimeError("runtime_switch_deferred_start_turn")
                if self._runtime_switch_is_pinned_signature(desired_signature):
                    raise RuntimeError("runtime_switch_deferred_active_turn")
                self._close_client("runtime_signature_mismatch")
            launch = self._resolve_launch_target(runtime_status)
            env = os.environ.copy()
            try:
                workspace_root = self._projects.require_workspace_root()
                env["ASTRABRIDGE_WORKSPACE_ROOT"] = str(workspace_root)
                env["ASTRABRIDGE_ASSET_ROOT"] = str(workspace_root / WORKSPACE_STATE_DIRNAME / "assets" / "generated")
            except Exception:
                pass
            client = AppServerClient(
                codex_executable=launch["codex_executable"],
                launch_command=launch["launch_command"],
                ws_url=launch.get("ws_url"),
                env={**env, **dict(launch.get("env_updates") or {})},
                cwd=launch["cwd"],
                on_notification=self._on_notification,
                on_server_request=self._on_server_request,
                on_stderr=self._on_stderr,
            )
            try:
                client.start()
            except TimeoutError as exc:
                try:
                    client.close()
                except Exception:
                    pass
                raise RuntimeError(
                    "Codex runtime initialization timed out. The desktop app-server did not become ready in time."
                ) from exc
            except Exception as exc:  # noqa: BLE001
                try:
                    client.close()
                except Exception:
                    pass
                raise RuntimeError(f"Codex runtime failed to start: {exc}") from exc
            self._client = client
            self._runtime_signature = desired_signature
            self._record_event({"type": "runtime_started", "runtime": runtime_status})
            return client

    def _runtime_request_client(self, runtime_status: dict[str, Any]) -> "_RuntimeRequestClient":
        return _RuntimeRequestClient(self, runtime_status)

    def _is_app_server_transport_error(self, exc: RuntimeError) -> bool:
        message = str(exc)
        return any(
            marker in message
            for marker in (
                "codex_app_server_not_running",
                "codex_app_server_closed",
                "codex_app_server_disconnected",
                "websocket URL is not configured",
            )
        )

    def _refresh_client_if_runtime_changed(self, runtime_status: dict[str, Any]) -> None:
        with self._lock:
            signature = self._runtime_config.runtime_signature(runtime_status)
            if self._client is not None and self._runtime_signature is not None and signature != self._runtime_signature:
                if (
                    (self._runtime_start_turn_in_progress and not getattr(self._runtime_operation_local, "in_start_turn", False))
                    or (self._runtime_thread_start_in_progress and not getattr(self._runtime_operation_local, "in_thread_start", False))
                ):
                    self._record_event(
                        {
                            "type": "runtime_switch_deferred_active_mutation",
                            "requested_runtime": runtime_status,
                            "active_runtime_signature": list(self._runtime_signature or []),
                            "reason": "runtime_refresh_during_active_mutation",
                        }
                    )
                    return
                if self._runtime_switch_is_pinned_signature(signature):
                    self._record_event(
                        {
                            "type": "runtime_switch_deferred_active_turn",
                            "requested_runtime": runtime_status,
                            "pinned_thread_id": self._runtime_pin_thread_id,
                            "pinned_turn_id": self._runtime_pin_turn_id,
                        }
                    )
                    return
                self._close_client("runtime_configuration_changed")
            self._runtime_signature = signature

    def _pin_runtime_for_turn(self, runtime_status: dict[str, Any], thread_id: str, turn_id: str) -> None:
        with self._lock:
            self._runtime_pin_signature = self._runtime_config.runtime_signature(runtime_status)
            self._runtime_pin_until_monotonic = time.monotonic() + TURN_RUNTIME_PIN_SECONDS
            self._runtime_pin_thread_id = thread_id
            self._runtime_pin_turn_id = turn_id or None

    def _runtime_switch_is_pinned(self, runtime_status: dict[str, Any]) -> bool:
        signature = self._runtime_config.runtime_signature(runtime_status)
        return self._runtime_switch_is_pinned_signature(signature)

    def _runtime_switch_is_pinned_signature(self, requested_signature: tuple[Any, ...]) -> bool:
        if getattr(self._runtime_operation_local, "in_start_turn", False):
            return False
        return (
            self._client is not None
            and self._client.is_running()
            and self._runtime_signature is not None
            and self._runtime_pin_signature is not None
            and self._runtime_signature == self._runtime_pin_signature
            and requested_signature != self._runtime_signature
            and time.monotonic() < self._runtime_pin_until_monotonic
        )

    def _close_client(self, reason: str) -> None:
        with self._lock:
            if self._client is None:
                return
            try:
                self._client.close()
            finally:
                self._client = None
            self._record_event({"type": "runtime_stopped", "reason": reason})

    def _on_notification(self, method: str, params: Any) -> None:
        payload = redact_sensitive(params)
        self._record_project_context_notification(method, payload)
        if method == "thread/name/updated" and isinstance(payload, dict):
            self._cache_thread_entry(str(payload.get("threadId") or ""), {"name": payload.get("threadName")})
        elif method == "thread/settings/updated" and isinstance(payload, dict):
            self._sync_thread_settings_from_notification(payload)
        elif method == "thread/started" and isinstance(payload, dict):
            thread = dict(payload.get("thread") or {})
            thread_id = str(thread.get("id") or "")
            if thread_id:
                self._cache_thread_entry(thread_id, {"name": thread.get("name")})
        self._record_event({"type": "notification", "method": method, "params": payload})

    def _on_server_request(self, method: str, params: Any) -> Any:
        if method == "item/tool/call":
            return self._handle_dynamic_tool_call(params)
        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/tool/requestUserInput",
            "mcpServer/elicitation/request",
            "item/permissions/requestApproval",
            "applyPatchApproval",
            "execCommandApproval",
        }:
            return self._modals.request(method, params)
        raise RuntimeError(f"Unsupported server request: {method}")

    def _handle_dynamic_tool_call(self, params: Any) -> dict[str, Any]:
        payload = dict(params or {}) if isinstance(params, dict) else {}
        tool = str(payload.get("tool") or payload.get("name") or "").strip()
        arguments = payload.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}
        try:
            if tool not in self._lcr_dynamic_tool_names():
                raise ValueError(f"Unsupported AstraBridge dynamic tool: {tool}")
            arguments = self._arguments_with_tool_context(tool, arguments)
            result = self._call_lcr_dynamic_tool(tool, arguments)
            summary = self._summarize_lcr_dynamic_tool_result(tool, result)
            context = sanitize_tool_context(arguments.get("tool_context"))
            if context:
                summary["tool_context"] = context
            tool_server = self._dynamic_tool_server(tool)
            usage_delta = self._record_yunwu_image_usage_from_tool_result(server=tool_server, tool=tool, result=summary)
            content_text = self._dynamic_tool_text_result(tool, summary)
            self._record_event(
                {
                    "type": "dynamic_tool_called",
                    "server": tool_server,
                    "tool": tool,
                    "thread_id": payload.get("threadId"),
                    "turn_id": payload.get("turnId"),
                    "success": True,
                    "usage_delta": usage_delta,
                    "result": summary,
                }
            )
            return {"success": True, "contentItems": [{"type": "inputText", "text": content_text}]}
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self._record_event(
                {
                    "type": "dynamic_tool_failed",
                    "server": self._dynamic_tool_server(tool),
                    "tool": tool,
                    "thread_id": payload.get("threadId"),
                    "turn_id": payload.get("turnId"),
                    "success": False,
                    "error": message,
                }
            )
            return {"success": False, "contentItems": [{"type": "inputText", "text": f"AstraBridge dynamic tool failed: {message}"}]}

    def _call_lcr_dynamic_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool in BROWSER_SMOKE_TOOL_ALIASES:
            return self._call_lcr_browser_smoke_dynamic_tool(arguments)
        if tool.startswith("lcr_web_"):
            return self._call_lcr_web_dynamic_tool(tool, arguments)
        return self._call_yunwu_dynamic_tool(tool, arguments)

    def _arguments_with_tool_context(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        merged = dict(arguments or {})
        merged["tool_context"] = self._tool_context.build(
            tool_name=tool,
            provided=merged.get("tool_context"),
        )
        return merged

    def _summarize_lcr_dynamic_tool_result(self, tool: str, result: dict[str, Any]) -> dict[str, Any]:
        if tool.startswith("yunwu_image_"):
            return summarize_yunwu_image_result(result)
        if tool in BROWSER_SMOKE_TOOL_ALIASES:
            record = dict(result.get("browser_smoke") or {})
            return {
                "tool": BROWSER_SMOKE_TOOL_NAME,
                "path": result.get("path"),
                "status": record.get("status"),
                "http_status": record.get("http_status"),
                "url": record.get("url"),
                "label": record.get("label"),
                "screenshot_path": record.get("screenshot_path"),
                "screenshot_status": record.get("screenshot_status"),
                "console_errors": list(record.get("console_errors") or [])[:10],
                "request_failures": list(record.get("request_failures") or [])[:10],
                "error": record.get("error"),
                "tool_event_verified": True,
            }
        return result

    def _dynamic_tool_server(self, tool: str) -> str:
        if tool in BROWSER_SMOKE_TOOL_ALIASES:
            return "astrabridge_browser"
        if tool.startswith("lcr_web_"):
            return "lcr_web"
        if tool.startswith("yunwu_image_"):
            return "yunwu_image"
        return "lcr"

    def _call_lcr_browser_smoke_dynamic_tool(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._dogfood_run is None:
            raise ValueError("Dogfood browser smoke service is not available.")
        payload = {
            "url": str(arguments.get("url") or "").strip(),
            "label": str(arguments.get("label") or "agent browser smoke").strip(),
            "actions": list(arguments.get("actions") or []),
            "auto_milestone": bool(arguments.get("auto_milestone", True)),
        }
        return self._dogfood_run.browser_smoke(payload)

    def _call_lcr_web_dynamic_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool == "lcr_web_search_batch":
            return self._lcr_web.search_batch(arguments)
        if tool == "lcr_web_research_brief":
            return self._lcr_web.research_brief(arguments)
        if tool == "lcr_web_search":
            return self._lcr_web.search_batch(
                {
                    "queries": [{"query": str(arguments.get("query") or ""), "max_results": int(arguments.get("max_results") or 5)}],
                    "dedupe": True,
                    "timeout_sec": int(arguments.get("timeout_sec") or 20),
                    "tool_context": arguments.get("tool_context"),
                }
            )
        if tool == "lcr_web_fetch":
            return self._lcr_web.fetch(arguments)
        raise ValueError(f"Unsupported AstraBridge web dynamic tool: {tool}")

    def _call_yunwu_dynamic_tool(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        workspace_root = self._projects.require_workspace_root()
        if tool == "yunwu_image_generate":
            return self._yunwu_image.generate(
                prompt=str(arguments.get("prompt") or ""),
                model=str(arguments.get("model") or "gpt-image-2"),
                size=str(arguments.get("size") or "1024x1024"),
                n=int(arguments.get("n") or 1),
                image_urls=[str(item) for item in (arguments.get("image_urls") or [])],
                response_format=str(arguments.get("response_format") or "url"),
                quality=str(arguments.get("quality") or "high"),
                image_format=str(arguments.get("format") or arguments.get("output_format") or "png"),
                background=str(arguments.get("background") or "auto") or None,
                prompt_category=str(arguments.get("prompt_category") or ""),
                workspace_root=workspace_root,
                purpose=str(arguments.get("purpose") or "agent_generated_asset"),
            )
        if tool == "yunwu_image_transparent_asset":
            return self._yunwu_image.transparent_asset(
                prompt=str(arguments.get("prompt") or ""),
                model=str(arguments.get("model") or "gpt-image-2"),
                size=str(arguments.get("size") or "1024x1024"),
                n=int(arguments.get("n") or 1),
                quality=str(arguments.get("quality") or "high"),
                moderation=str(arguments.get("moderation") or "auto"),
                prompt_category=str(arguments.get("prompt_category") or "game_asset_japanese_anime"),
                workspace_root=workspace_root,
                purpose=str(arguments.get("purpose") or "agent_transparent_asset"),
            )
        if tool == "yunwu_image_edit":
            return self._yunwu_image.edit(
                prompt=str(arguments.get("prompt") or ""),
                image_paths=[str(item) for item in (arguments.get("image_paths") or [])],
                mask_path=str(arguments.get("mask_path") or "") or None,
                model=str(arguments.get("model") or "gpt-image-2"),
                size=str(arguments.get("size") or "1024x1024"),
                n=int(arguments.get("n") or 1),
                quality=str(arguments.get("quality") or "high"),
                background=str(arguments.get("background") or "transparent"),
                moderation=str(arguments.get("moderation") or "auto"),
                prompt_category=str(arguments.get("prompt_category") or ""),
                workspace_root=workspace_root,
                purpose=str(arguments.get("purpose") or "agent_edited_asset"),
            )
        raise ValueError(f"Unsupported Yunwu dynamic tool: {tool}")

    def _dynamic_tool_text_result(self, tool: str, summary: dict[str, Any]) -> str:
        return "AstraBridge dynamic tool result for " + tool + ":\n" + json.dumps(summary, ensure_ascii=False, indent=2)

    def _on_stderr(self, line: str) -> None:
        self._record_event({"type": "stderr", "line": line})

    def _build_user_inputs(
        self,
        text: str,
        attachments: list[dict[str, Any]],
        thread_id: str | None = None,
        context_mode: str | None = None,
        profile_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        clean_text = text.strip()
        normalized_context_mode = self._normalize_context_mode(context_mode)
        include_context = normalized_context_mode in {"default", "full"}
        if normalized_context_mode == "minimal_visual":
            mode_note = (
                "AstraBridge minimal visual mode: answer from the attached image(s) and the user's prompt only. "
                "Do not inspect repository files, run commands, or use tools unless the user explicitly asks for that in this turn."
            )
            clean_text = f"{mode_note}\n\n{clean_text}" if clean_text else mode_note
        project_context_items = (
            self._project_context_inputs(
                thread_id=thread_id,
                profile_id=profile_id,
                provider_id=provider_id,
                model_id=model_id,
            )
            if include_context
            else []
        )
        project_context_text = "\n\n".join(str(item.get("text") or "") for item in project_context_items if item.get("type") == "text").strip()
        project_mentions = [item for item in project_context_items if item.get("type") == "mention"]
        asset_context_items = self._asset_context_inputs() if include_context else []
        asset_context_text = "\n\n".join(str(item.get("text") or "") for item in asset_context_items if item.get("type") == "text").strip()
        asset_mentions = [item for item in asset_context_items if item.get("type") == "mention"]
        if project_context_text:
            clean_text = (
                f"{clean_text}\n\n---\n{project_context_text}"
                if clean_text
                else project_context_text
            )
        if asset_context_text:
            clean_text = (
                f"{clean_text}\n\n---\n{asset_context_text}"
                if clean_text
                else asset_context_text
            )
        if clean_text or not attachments:
            items.append({"type": "text", "text": clean_text or "Please inspect the attached files.", "text_elements": []})
        for attachment in attachments:
            staged = self._stage_attachment(str(attachment.get("path") or ""), str(attachment.get("name") or "attachment"))
            runtime_path = self._path_for_runtime(staged)
            mime_type = str(attachment.get("mime_type") or mimetypes.guess_type(staged.name)[0] or "")
            if mime_type.startswith("image/"):
                items.append({"type": "localImage", "path": runtime_path, "detail": "high"})
            else:
                items.append({"type": "mention", "name": staged.name, "path": runtime_path})
        for mention in project_mentions:
            raw_path = str(mention.get("path") or "")
            if not raw_path:
                continue
            items.append(
                {
                    "type": "mention",
                    "name": str(mention.get("name") or Path(raw_path).name),
                    "path": self._path_for_runtime(Path(raw_path)),
                }
            )
        for mention in asset_mentions:
            raw_path = str(mention.get("path") or "")
            if not raw_path:
                continue
            items.append(
                {
                    "type": "mention",
                    "name": str(mention.get("name") or Path(raw_path).name),
                    "path": self._path_for_runtime(Path(raw_path)),
                }
            )
        return items

    def _normalize_context_mode(self, context_mode: str | None) -> str:
        mode = str(context_mode or "default").strip().lower()
        aliases = {
            "": "default",
            "auto": "default",
            "project": "default",
            "project_context": "default",
            "with_context": "default",
            "health": "minimal_text",
            "health_check": "minimal_text",
            "light": "minimal_text",
            "lightweight": "minimal_text",
            "minimal_text": "minimal_text",
            "handoff": "default",
            "multi_provider": "default",
            "multi_provider_handoff": "default",
            "minimal": "minimal_visual",
            "visual": "minimal_visual",
            "visual_only": "minimal_visual",
            "none": "no_context",
            "off": "no_context",
        }
        mode = aliases.get(mode, mode)
        if mode not in VALID_CONTEXT_MODES:
            valid = ", ".join(sorted(VALID_CONTEXT_MODES | set(aliases)))
            raise ValueError(f"Unsupported context mode: {context_mode}. Supported context modes: {valid}")
        return "default" if mode == "full" else mode

    def _project_context_inputs(
        self,
        *,
        thread_id: str | None = None,
        profile_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._project_context is None:
            return []
        try:
            return list(
                self._project_context.context_inputs(
                    thread_id=thread_id,
                    profile_id=profile_id,
                    provider_id=provider_id,
                    model_id=model_id,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "project_context_pack_failed", "error": str(exc)[:300]})
            return []

    def _project_context_budget_report(
        self,
        *,
        thread_id: str | None = None,
        profile_id: str | None = None,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> dict[str, Any] | None:
        if self._project_context is None:
            return None
        try:
            snapshot = self._project_context.snapshot(
                thread_id=thread_id,
                profile_id=profile_id,
                provider_id=provider_id,
                model_id=model_id,
            )
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "project_context_budget_failed", "error": str(exc)[:300]})
            return None
        pack = dict(snapshot.get("context_pack") or {})
        report = dict(pack.get("budget_report") or {})
        return report or None

    def _handoff_projection_kwargs(self, *, source_thread_id: str | None, target_provider_id: str) -> dict[str, Any]:
        summary = self._handoff_projection_summary(source_thread_id=source_thread_id, target_provider_id=target_provider_id)
        if not summary:
            return {}
        return {
            "dropped_artifacts": int(summary.get("dropped_artifacts") or 0),
            "repaired_tool_pairs": int(summary.get("repaired_tool_pairs") or 0),
            "replayable_artifact_count": int(summary.get("replayable_artifact_count") or 0),
            "projection_preview": str(summary.get("projection_preview") or "").strip() or None,
            "warnings": list(summary.get("warnings") or []),
        }

    def _handoff_projection_summary(self, *, source_thread_id: str | None, target_provider_id: str) -> dict[str, Any] | None:
        source_thread = self._thread_for_handoff_projection(source_thread_id)
        target_provider = str(target_provider_id or "").strip().lower()
        if not source_thread or not target_provider:
            return None
        source_provider = self._thread_provider_id_for_projection(source_thread)
        neutral_messages, artifacts = self._thread_projection_inputs(source_thread)
        if not neutral_messages and not artifacts:
            return None
        projected = HistoryProjector().project(
            neutral_messages=neutral_messages,
            artifacts=artifacts,
            source_provider=source_provider,
            target_provider=target_provider,
        )
        return {
            "source_provider": source_provider,
            "target_provider": target_provider,
            "dropped_artifacts": projected.dropped_artifacts,
            "repaired_tool_pairs": projected.repaired_tool_pairs,
            "warnings": projected.warnings,
            "projected_message_count": len(projected.messages),
            "replayable_artifact_count": projected.replayable_artifact_count,
            "projection_preview": projected.projection_preview,
        }

    def _thread_for_handoff_projection(self, source_thread_id: str | None) -> dict[str, Any] | None:
        clean_thread_id = str(source_thread_id or "").strip()
        if not clean_thread_id:
            return None
        native = self._read_native_thread(clean_thread_id)
        if isinstance(native, dict) and native:
            return native
        cached = self._cached_thread(clean_thread_id)
        if isinstance(cached, dict) and cached:
            return cached
        return None

    def _thread_provider_id_for_projection(self, thread: dict[str, Any]) -> str | None:
        settings = dict(thread.get("shellSettings") or {})
        provider = str(settings.get("provider_id") or "").strip().lower()
        if provider:
            return provider
        for turn in list(thread.get("turns") or []):
            if not isinstance(turn, dict):
                continue
            provider = str(turn.get("provider_id") or turn.get("providerId") or "").strip().lower()
            if provider:
                return provider
            for item in list(turn.get("items") or []):
                if not isinstance(item, dict):
                    continue
                provider_data = dict(item.get("providerData") or item.get("provider_data") or {})
                normalized = dict(provider_data.get("normalized") or {})
                reasoning_state = dict(normalized.get("reasoning_state") or {})
                provider = str(reasoning_state.get("provider_id") or normalized.get("provider_id") or "").strip().lower()
                if provider:
                    return provider
        return None

    def _thread_projection_inputs(self, thread: dict[str, Any]) -> tuple[list[NeutralMessage], list[ReasoningArtifact]]:
        neutral_messages: list[NeutralMessage] = []
        artifacts: list[ReasoningArtifact] = []
        for turn in list(thread.get("turns") or []):
            if not isinstance(turn, dict):
                continue
            for item in list(turn.get("items") or []):
                if not isinstance(item, dict):
                    continue
                neutral_messages.extend(self._projection_messages_from_item(item))
                artifacts.extend(self._projection_artifacts_from_item(item))
        return neutral_messages, artifacts

    def _projection_messages_from_item(self, item: dict[str, Any]) -> list[NeutralMessage]:
        item_type = str(item.get("type") or "").strip()
        provider_data = dict(item.get("providerData") or item.get("provider_data") or {})
        normalized = dict(provider_data.get("normalized") or {})
        text = self._projection_item_text(item, normalized)
        messages: list[NeutralMessage] = []
        if item_type in {"userMessage", "inputMessage", "user_message"} and text:
            messages.append(NeutralMessage(role="user", text=text))
            return messages
        if item_type in {"agentMessage", "assistantMessage", "agent_message", "assistant_message"}:
            if text:
                messages.append(NeutralMessage(role="assistant", text=text))
            for call in list(normalized.get("tool_calls") or []):
                if not isinstance(call, dict):
                    continue
                tool_id = str(call.get("id") or "").strip()
                tool_name = str(call.get("name") or "").strip()
                arguments_json = str(call.get("arguments_json") or "").strip() or "{}"
                if tool_id and tool_name:
                    messages.append(
                        NeutralMessage(
                            role="assistant",
                            text="",
                            tool_call_id=tool_id,
                            tool_name=tool_name,
                            provider_data={"arguments_json": arguments_json},
                        )
                    )
        return messages

    def _projection_artifacts_from_item(self, item: dict[str, Any]) -> list[ReasoningArtifact]:
        provider_data = dict(item.get("providerData") or item.get("provider_data") or {})
        normalized = dict(provider_data.get("normalized") or {})
        reasoning_state = dict(normalized.get("reasoning_state") or {})
        if not reasoning_state:
            return []
        provider_id = str(reasoning_state.get("provider_id") or "").strip()
        model_id = str(reasoning_state.get("model_id") or "").strip()
        if not provider_id or not model_id:
            return []
        return [
            ReasoningArtifact(
                provider_id=provider_id,
                model_id=model_id,
                kind="reasoning_state",
                replayable=bool(reasoning_state.get("replayable")),
                payload=reasoning_state,
            )
        ]

    def _projection_item_text(self, item: dict[str, Any], normalized: dict[str, Any]) -> str:
        text = str(normalized.get("text") or "").strip()
        if text:
            return text
        direct = item.get("text") or item.get("message") or item.get("content")
        if isinstance(direct, str):
            return direct.strip()
        return ""

    def _asset_context_inputs(self) -> list[dict[str, Any]]:
        if self._asset_registry is None:
            return []
        try:
            return list(self._asset_registry.context_inputs())
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "asset_context_pack_failed", "error": str(exc)[:300]})
            return []

    def _stage_attachment(self, raw_path: str, preferred_name: str) -> Path:
        if not raw_path.strip():
            raise ValueError("Attachment path is required.")
        source = Path(raw_path).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Attachment does not exist: {source}")
        try:
            workspace_root = self._projects.require_workspace_root().resolve()
            if source == workspace_root or workspace_root in source.parents:
                if source.parts.count(WORKSPACE_STATE_DIRNAME):
                    return source
                return resolve_under(workspace_root, source)
        except Exception:
            pass
        try:
            scan_text_for_secrets(source)
        except SecurityError:
            raise
        attachments_root = self._projects.require_shell_state_root() / "attachments"
        attachments_root.mkdir(parents=True, exist_ok=True)
        extension = source.suffix or Path(preferred_name).suffix
        stem = Path(preferred_name).stem or source.stem or "attachment"
        target = attachments_root / f"{stem}-{new_id('ATT')}{extension}"
        shutil.copy2(source, target)
        return target

    def _execution_host(self) -> str:
        project = self._projects.current_project or {}
        prefs = dict(project.get("ui_preferences") or {})
        host = str(prefs.get("execution_host") or "windows").strip().lower()
        return "wsl" if host == "wsl" else "windows"

    def _wsl_distro(self) -> str | None:
        project = self._projects.current_project or {}
        prefs = dict(project.get("ui_preferences") or {})
        value = str(prefs.get("wsl_distro") or "").strip()
        return value or None

    def _runtime_workspace_root(self) -> str:
        return self._path_for_runtime(self._projects.require_workspace_root())

    def _path_for_runtime(self, path: Path) -> str:
        resolved = path.expanduser().resolve()
        if self._execution_host() == "wsl":
            return self._windows_path_to_wsl(resolved)
        return str(resolved)

    def _windows_path_to_wsl(self, path: Path) -> str:
        resolved = path.expanduser().resolve()
        drive = resolved.drive.rstrip(":").lower()
        if not drive:
            raise RuntimeError(f"WSL execution requires a drive-backed Windows path. Unsupported path: {resolved}")
        tail = resolved.as_posix()[2:]
        return f"/mnt/{drive}{tail}"

    def _launch_descriptor(self) -> str | None:
        if self._execution_host() == "wsl":
            distro = self._wsl_distro() or "default"
            codex_binary = os.environ.get("ASTRABRIDGE_WSL_CODEX_BIN") or ASTRABRIDGE_WSL_BIN
            return f"wsl::{distro}::{codex_binary}"
        return os.environ.get("ASTRABRIDGE_CODEX_BIN") or shutil.which("codex")

    def _resolve_launch_target(self, runtime_status: dict[str, Any]) -> dict[str, Any]:
        if self._execution_host() != "wsl":
            codex_executable = os.environ.get("ASTRABRIDGE_CODEX_BIN") or shutil.which("codex")
            if not codex_executable:
                raise RuntimeError("Codex CLI/runtime was not detected. Install Codex or set ASTRABRIDGE_CODEX_BIN before sending.")
            return {
                "codex_executable": codex_executable,
                "launch_command": None,
                "ws_url": None,
                "env_updates": {},
                "cwd": self._app_server_launch_cwd(),
            }

        wsl_executable = shutil.which("wsl.exe") or shutil.which("wsl")
        if not wsl_executable:
            raise RuntimeError("WSL execution host is selected, but wsl.exe was not detected on Windows.")
        workspace_root = self._projects.require_workspace_root()
        launcher_cwd_wsl = self._windows_path_to_wsl(self._app_server_launch_cwd())
        codex_home_wsl = os.environ.get("ASTRABRIDGE_WSL_CODEX_HOME") or ASTRABRIDGE_WSL_CODEX_HOME
        codex_binary = os.environ.get("ASTRABRIDGE_WSL_CODEX_BIN") or ASTRABRIDGE_WSL_BIN
        requested_distro = self._wsl_distro()
        installed_distros = self._list_wsl_distros(wsl_executable)
        if requested_distro and requested_distro not in installed_distros:
            raise RuntimeError(
                f"WSL execution host is selected, but the configured distro was not found: {requested_distro}. "
                f"Available distros: {', '.join(installed_distros) if installed_distros else 'none'}."
            )
        if not requested_distro and not installed_distros:
            raise RuntimeError(
                "WSL execution host is selected, but no WSL distro is installed on this machine yet. "
                "Install one first with `wsl.exe --install <Distro>`."
            )
        distro = requested_distro or (installed_distros[0] if installed_distros else None)
        distro_args = ["-d", distro] if distro else []
        self._terminate_stale_astrabridge_wsl_app_servers(wsl_executable, distro_args)
        probe = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", self._wsl_codex_probe_command(codex_binary)])
        if int(probe["returncode"]) != 0:
            detail = str(probe["stderr"] or probe["stdout"]).strip()
            suffix = f" ({detail})" if detail else ""
            raise RuntimeError(
                "WSL execution host is selected, but a Linux-native Codex CLI is not ready inside WSL. "
                "Install the AstraBridge-managed WSL runtime or set ASTRABRIDGE_WSL_CODEX_BIN." + suffix
            )
        codex_home_wsl_abs = self._wsl_expand_home(wsl_executable, distro_args, codex_home_wsl)
        home_wsl_abs = self._wsl_expand_home(wsl_executable, distro_args, "$HOME")
        codex_binary_abs = self._wsl_expand_home(wsl_executable, distro_args, codex_binary)
        self._sync_wsl_codex_home(runtime_status, wsl_executable, distro_args, codex_home_wsl_abs, home_wsl_abs)
        env_updates = self._wsl_runtime_env(runtime_status, codex_home_wsl_abs)
        env_passthrough = self._wsl_env_passthrough_args(env_updates)
        codex_command = self._wsl_codex_command(codex_binary_abs)
        clean_path = f"{home_wsl_abs.rstrip('/')}/.local/share/astrabridge/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        ws_port = self._reserve_loopback_port()
        ws_url = f"ws://127.0.0.1:{ws_port}"
        command = (
            f"cd {shlex.quote(launcher_cwd_wsl)} && "
            f"exec env -i HOME={shlex.quote(home_wsl_abs)} USER=\"${{USER:-}}\" LOGNAME=\"${{LOGNAME:-}}\" "
            f"SHELL=/bin/bash PATH={shlex.quote(clean_path)} {env_passthrough}{codex_command} "
            f"app-server --listen {shlex.quote(ws_url)} --disable plugins --disable plugin_sharing --disable remote_plugin"
        )
        return {
            "codex_executable": wsl_executable,
            "launch_command": [wsl_executable, *distro_args, "--exec", "/bin/bash", "-lc", command],
            "ws_url": ws_url,
            "env_updates": env_updates,
            "cwd": None,
        }

    def _app_server_launch_cwd(self) -> Path:
        """Keep Codex app-server process-local files out of the workspace root."""
        path = self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME / "runtime-cwd"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _terminate_stale_astrabridge_wsl_app_servers(self, wsl_executable: str, distro_args: list[str]) -> None:
        script = r'''
import os
import signal
import time

needle = "/.local/share/astrabridge/bin/codex app-server"
current = os.getpid()

def matching_pids():
    matches = []
    for raw_pid in os.listdir("/proc"):
        if not raw_pid.isdigit():
            continue
        pid = int(raw_pid)
        if pid == current:
            continue
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "ignore")
        except Exception:
            continue
        if needle in cmd:
            matches.append(pid)
    return matches

terminated = []
for pid in matching_pids():
    try:
        os.kill(pid, signal.SIGTERM)
        terminated.append(pid)
    except ProcessLookupError:
        pass
    except PermissionError:
        pass

if terminated:
    time.sleep(0.3)
    for pid in matching_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
print(",".join(str(pid) for pid in terminated))
'''
        command = "python3 - <<'PY'\n" + script.strip() + "\nPY"
        result = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", command])
        text = str(result.get("stdout") or "").strip()
        if text:
            self._record_event({"type": "wsl_app_server_cleanup", "terminated_pids": text.split(",")})

    def _wsl_expand_home(self, wsl_executable: str, distro_args: list[str], path: str) -> str:
        if not path.startswith("$HOME"):
            return path
        home = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", 'printf "%s" "$HOME"'])
        if int(home["returncode"]) != 0 or not str(home["stdout"]).strip():
            raise RuntimeError("WSL execution host is selected, but the Linux home directory could not be resolved.")
        return path.replace("$HOME", str(home["stdout"]).strip(), 1)

    def _sync_wsl_codex_home(
        self,
        runtime_status: dict[str, Any],
        wsl_executable: str,
        distro_args: list[str],
        codex_home_wsl_abs: str,
        home_wsl_abs: str,
    ) -> None:
        windows_codex_home = Path(str(runtime_status.get("codex_home") or "")).expanduser()
        config_path = windows_codex_home / "config.toml"
        models_dir = windows_codex_home / "models"
        models_cache = windows_codex_home / ASTRABRIDGE_MODELS_CACHE_FILENAME
        if not config_path.is_file() or not models_dir.is_dir():
            raise RuntimeError("AstraBridge runtime config was not rendered before WSL launch.")
        wsl_config_path = windows_codex_home / "config.wsl.toml"
        wsl_catalog_path = f"{codex_home_wsl_abs.rstrip('/')}/models/{ASTRABRIDGE_MODEL_CATALOG_FILENAME}"
        wsl_router_base_url = self._wsl_router_base_url(wsl_executable, distro_args)
        sidecar_source_wsl = self._windows_path_to_wsl(Path(__file__).resolve().parents[1])
        sidecar_link_wsl = f"{home_wsl_abs.rstrip('/')}/.local/share/astrabridge/sidecar-src"
        config_text = self._rewrite_wsl_config_text(
            config_path.read_text(encoding="utf-8"),
            codex_home_wsl_abs=codex_home_wsl_abs,
            router_base_url=wsl_router_base_url,
            sidecar_source_wsl=sidecar_source_wsl,
            sidecar_link_wsl=sidecar_link_wsl,
        )
        wsl_config_path.write_text(config_text, encoding="utf-8", newline="\n")
        source_home_wsl = self._windows_path_to_wsl(windows_codex_home)
        command = (
            f"mkdir -p {shlex.quote(codex_home_wsl_abs)} {shlex.quote(codex_home_wsl_abs + '/models')} {shlex.quote(posixpath.dirname(sidecar_link_wsl))} && "
            f"ln -sfn {shlex.quote(sidecar_source_wsl)} {shlex.quote(sidecar_link_wsl)} && "
            f"cp {shlex.quote(source_home_wsl + '/config.wsl.toml')} {shlex.quote(codex_home_wsl_abs + '/config.toml')} && "
            f"cp -R {shlex.quote(source_home_wsl + '/models/.')} {shlex.quote(codex_home_wsl_abs + '/models/')}"
        )
        if models_cache.is_file():
            command += f" && cp {shlex.quote(source_home_wsl + '/' + ASTRABRIDGE_MODELS_CACHE_FILENAME)} {shlex.quote(codex_home_wsl_abs + '/' + ASTRABRIDGE_MODELS_CACHE_FILENAME)}"
        result = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", command])
        if int(result["returncode"]) != 0:
            detail = str(result["stderr"] or result["stdout"]).strip()
            raise RuntimeError(f"Failed to sync AstraBridge Codex config into WSL CODEX_HOME: {detail}")

    def _rewrite_wsl_config_text(
        self,
        config_text: str,
        *,
        codex_home_wsl_abs: str,
        router_base_url: str | None = None,
        sidecar_source_wsl: str | None = None,
        sidecar_link_wsl: str | None = None,
    ) -> str:
        wsl_catalog_path = f"{codex_home_wsl_abs.rstrip('/')}/models/{ASTRABRIDGE_MODEL_CATALOG_FILENAME}"
        config_text = re.sub(
            r'^model_catalog_json = ".*"$',
            f'model_catalog_json = "{wsl_catalog_path.replace(chr(34), chr(92) + chr(34))}"',
            config_text,
            flags=re.MULTILINE,
        )
        if router_base_url:
            config_text = re.sub(
                r'^(base_url = ")http://(?:127\.0\.0\.1|localhost|0\.0\.0\.0):([0-9]+)/v1(")$',
                lambda match: f'{match.group(1)}{router_base_url.rsplit(":", 1)[0]}:{match.group(2)}/v1{match.group(3)}',
                config_text,
                flags=re.MULTILINE,
            )
        # MCP presets are rendered by the Windows sidecar. When app-server runs
        # inside WSL, Windows executables and paths in stdio MCP blocks must be
        # translated before Codex tries to launch them.
        config_text = re.sub(
            r'^(command = )"[A-Za-z]:\\\\[^"]*python(?:\.exe)?"$',
            r'\1"python3"',
            config_text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        config_text = re.sub(r'"[A-Za-z]:\\\\[^"]*"', self._replace_toml_windows_path_for_wsl, config_text)
        if sidecar_source_wsl and sidecar_link_wsl:
            config_text = config_text.replace(sidecar_source_wsl.rstrip("/"), sidecar_link_wsl.rstrip("/"))
        return config_text

    def _replace_toml_windows_path_for_wsl(self, match: re.Match[str]) -> str:
        escaped = match.group(0)[1:-1]
        windows_text = escaped.replace("\\\\", "\\")
        try:
            wsl_path = self._windows_path_to_wsl(Path(windows_text))
        except Exception:
            return match.group(0)
        return f'"{wsl_path.replace(chr(34), chr(92) + chr(34))}"'

    def _wsl_router_base_url(self, wsl_executable: str, distro_args: list[str]) -> str | None:
        candidates: list[str] = []

        def add_candidate(value: str | None) -> None:
            host = str(value or "").strip()
            if host and host not in candidates:
                candidates.append(host)

        add_candidate(os.environ.get("ASTRABRIDGE_WSL_HOST"))
        result = self._run_capture([wsl_executable, *distro_args, "ip", "route", "show", "default"])
        text = str(result.get("stdout") or "").strip()
        match = re.search(r"\bdefault\s+via\s+([0-9a-fA-F:.]+)\b", text)
        add_candidate(match.group(1) if match else "")
        fallback = self._run_capture([wsl_executable, *distro_args, "cat", "/etc/resolv.conf"])
        fallback_text = str(fallback.get("stdout") or "")
        for nameserver in re.findall(r"^nameserver\s+([0-9a-fA-F:.]+)\s*$", fallback_text, re.MULTILINE):
            add_candidate(nameserver)
        add_candidate("host.docker.internal")
        add_candidate("localhost")
        add_candidate("127.0.0.1")
        if not candidates:
            return None
        router_port = int(os.environ.get("ASTRABRIDGE_PORT") or ROUTER_PORT)
        expected_fingerprint = str(os.environ.get("ASTRABRIDGE_TOKEN_FINGERPRINT") or "").strip()
        attempts = self._probe_wsl_router_candidates(wsl_executable, distro_args, candidates, router_port)
        for attempt in attempts:
            if attempt.get("service") != "astrabridge":
                continue
            if expected_fingerprint and attempt.get("token_fingerprint") != expected_fingerprint:
                continue
            base_url = str(attempt.get("base_url") or "").strip()
            if base_url:
                self._record_event(
                    {
                        "type": "wsl_router_probe_selected",
                        "host": attempt.get("host"),
                        "token_fingerprint": attempt.get("token_fingerprint"),
                    }
                )
                return base_url
        self._record_event(
            {
                "type": "wsl_router_probe_failed",
                "expected_fingerprint": expected_fingerprint or None,
                "attempts": attempts[:8],
            }
        )
        reason = "no reachable AstraBridge router"
        if expected_fingerprint:
            reason = f"no reachable AstraBridge router with fingerprint {expected_fingerprint}"
        raise RuntimeError(
            f"WSL execution host is selected, but WSL could not reach the current AstraBridge ({reason}). "
            "Stop stale sidecars, check Windows firewall/port forwarding, or set ASTRABRIDGE_WSL_HOST."
        )

    def _probe_wsl_router_candidates(
        self,
        wsl_executable: str,
        distro_args: list[str],
        candidates: list[str],
        router_port: int,
    ) -> list[dict[str, Any]]:
        candidate_json = json.dumps(candidates, ensure_ascii=False)
        script = f"""
import json
import urllib.request

candidates = {candidate_json}
port = {int(router_port)}

def format_host(host):
    if ":" in host and not host.startswith("["):
        return "[" + host + "]"
    return host

for host in candidates:
    formatted = format_host(host)
    record = {{"host": host, "base_url": f"http://{{formatted}}:{{port}}"}}
    try:
        url = f"http://{{formatted}}:{{port}}/readyz"
        request = urllib.request.Request(url, headers={{"Accept": "application/json"}})
        with urllib.request.urlopen(request, timeout=1.5) as response:
            body = response.read(65536).decode("utf-8", "replace")
            payload = json.loads(body or "{{}}")
            record.update({{
                "status": getattr(response, "status", None),
                "ok": payload.get("ok"),
                "service": payload.get("service"),
                "token_fingerprint": payload.get("token_fingerprint"),
            }})
    except Exception as exc:
        record["error"] = str(exc)[:200]
    print(json.dumps(record, ensure_ascii=False))
"""
        command = "python3 - <<'PY'\n" + script.strip() + "\nPY"
        result = self._run_capture([wsl_executable, *distro_args, "bash", "-lc", command])
        attempts: list[dict[str, Any]] = []
        if int(result.get("returncode") or 0) != 0:
            return [
                {
                    "error": str(result.get("stderr") or result.get("stdout") or "WSL router probe failed")[:300],
                    "returncode": result.get("returncode"),
                }
            ]
        for line in str(result.get("stdout") or "").splitlines():
            try:
                parsed = json.loads(line)
            except Exception:
                continue
            if isinstance(parsed, dict):
                attempts.append(parsed)
        return attempts

    def _reserve_loopback_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _list_wsl_distros(self, wsl_executable: str) -> list[str]:
        result = self._run_capture([wsl_executable, "-l", "-q"])
        if int(result["returncode"]) != 0:
            return []
        return [line.strip() for line in str(result["stdout"] or "").splitlines() if line.strip()]

    def _run_capture(self, command: list[str]) -> dict[str, Any]:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return {
            "returncode": completed.returncode,
            "stdout": self._decode_output(completed.stdout),
            "stderr": self._decode_output(completed.stderr),
        }

    def _decode_output(self, payload: bytes) -> str:
        if not payload:
            return ""
        for encoding in ("utf-8", "utf-16-le", "gbk", "cp936"):
            try:
                return payload.decode(encoding).replace("\x00", "").strip()
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="replace").replace("\x00", "").strip()

    def _wsl_codex_path_export(self) -> str:
        return f'export PATH="{ASTRABRIDGE_WSL_ROOT}/bin:$PATH"; '

    def _wsl_codex_command(self, codex_binary: str) -> str:
        if codex_binary in {"codex", ASTRABRIDGE_WSL_BIN}:
            return "codex"
        return self._quote_wsl_value(codex_binary)

    def _wsl_codex_probe_command(self, codex_binary: str) -> str:
        codex_command = self._wsl_codex_command(codex_binary)
        return (
            f"export CODEX_HOME={self._quote_wsl_value(os.environ.get('ASTRABRIDGE_WSL_CODEX_HOME') or ASTRABRIDGE_WSL_CODEX_HOME)}; "
            f"{self._wsl_codex_path_export()}"
            f'if ! command -v {codex_command} > /tmp/lcr_codex_probe_path 2>/dev/null; then echo "codex executable not found: {codex_command}" >&2; exit 127; fi; '
            'if grep -q "WindowsApps" /tmp/lcr_codex_probe_path; then printf "codex resolves to WindowsApps inside WSL: " >&2; cat /tmp/lcr_codex_probe_path >&2; exit 126; fi; '
            f"{codex_command} --version >/dev/null 2>&1"
        )

    def _quote_wsl_value(self, value: str) -> str:
        if value.startswith("$HOME/"):
            return f'"{value}"'
        return shlex.quote(value)

    def _wsl_runtime_env(self, runtime_status: dict[str, Any], codex_home_wsl: str) -> dict[str, str]:
        values = {
            "CODEX_HOME": codex_home_wsl,
            ROUTER_ENV_KEY: os.environ.get(ROUTER_ENV_KEY, ""),
            "NO_PROXY": os.environ.get("NO_PROXY", ""),
            "no_proxy": os.environ.get("no_proxy", ""),
        }
        try:
            workspace_root = self._projects.require_workspace_root()
            asset_root = workspace_root / WORKSPACE_STATE_DIRNAME / "assets" / "generated"
            # MCP servers may be launched as either WSL-native commands or Windows
            # executables from a WSL app-server. Keep the canonical variables in
            # host paths for Windows Python MCP servers and expose WSL variants for
            # native Linux tools.
            values["ASTRABRIDGE_WORKSPACE_ROOT"] = str(workspace_root)
            values["ASTRABRIDGE_ASSET_ROOT"] = str(asset_root)
            values["ASTRABRIDGE_WORKSPACE_ROOT_WSL"] = self._windows_path_to_wsl(workspace_root)
            values["ASTRABRIDGE_ASSET_ROOT_WSL"] = self._windows_path_to_wsl(asset_root)
        except Exception:
            pass
        env_key = str(runtime_status.get("env_key") or "")
        if env_key:
            values[env_key] = os.environ.get(env_key, "")
        for mcp_env_key in self._mcp_passthrough_env_keys():
            if mcp_env_key not in values:
                values[mcp_env_key] = os.environ.get(mcp_env_key, "")
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            value = os.environ.get(key)
            if value:
                values[key] = value
        sanitized = {name: str(value) for name, value in values.items() if value is not None}
        passthrough_names = [name for name in sanitized if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name)]
        existing_wslenv = str(os.environ.get("WSLENV") or "").strip()
        wslenv_parts = [part for part in existing_wslenv.split(":") if part]
        existing_names = {part.split("/", 1)[0] for part in wslenv_parts}
        wslenv_parts.extend(name for name in passthrough_names if name not in existing_names)
        if wslenv_parts:
            sanitized["WSLENV"] = ":".join(wslenv_parts)
        return sanitized

    def _mcp_passthrough_env_keys(self) -> list[str]:
        names: set[str] = set()
        try:
            servers = self._mcp_config.enabled_servers()
        except Exception:
            servers = []
        for server in servers:
            for name in list(server.get("env_vars") or []):
                text = str(name or "").strip()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", text):
                    names.add(text)
            bearer = str(server.get("bearer_token_env_var") or "").strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", bearer):
                names.add(bearer)
            for value in dict(server.get("env_http_headers") or {}).values():
                text = str(value or "").strip()
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", text):
                    names.add(text)
        return sorted(names)

    def _wsl_env_passthrough_args(self, env_values: dict[str, str]) -> str:
        assignments: list[str] = []
        for name in env_values:
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                continue
            assignments.append(f'{name}="${{{name}:-}}"')
        return (" ".join(assignments) + " ") if assignments else ""

    def _thread_start_params(self, *, profile: dict[str, Any], model: str | None, permission_mode: str) -> dict[str, Any]:
        params = {
            "cwd": self._runtime_workspace_root(),
            "approvalsReviewer": "user",
            "modelProvider": profile.get("provider_id"),
            "model": codex_model_id(profile, model),
            "serviceName": "local_codex_router_desktop",
        }
        dynamic_tools = self._lcr_dynamic_tools()
        if dynamic_tools:
            params["dynamicTools"] = dynamic_tools
        params.update(self._thread_permission_overrides(permission_mode))
        return params

    def _lcr_dynamic_tools(self) -> list[dict[str, Any]]:
        dynamic_tools: list[dict[str, Any]] = []
        if self._dogfood_run is not None:
            dynamic_tools.append(
                {
                    "name": BROWSER_SMOKE_TOOL_NAME,
                    "description": (
                        "Run a local browser smoke test for a localhost, 127.0.0.1, or file:// URL, optionally "
                        "performing simple UI actions, then record console errors and a screenshot in the AstraBridge "
                        "dogfood ledger. WSL-style file URLs such as file:///mnt/d/... are supported and normalized "
                        "for the host browser; do not start an ad-hoc HTTP server just to capture a screenshot. "
                        "For story/tutorial screens, prefer click_text_until_absent over guessing a fixed number of clicks. "
                        "Use expect_text/forbidden_text for the intended final state; without assertions the result is only "
                        "a screenshot/console smoke, not verified gameplay evidence. "
                        "Use this after UI/game changes instead of only claiming visual validation."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Local URL to smoke test. Must start with http://127.0.0.1:, http://localhost:, or file://.",
                            },
                            "label": {"type": "string", "description": "Short evidence label."},
                            "actions": {
                                "type": "array",
                                "maxItems": MAX_BROWSER_SMOKE_ACTIONS,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": [
                                                "click_text",
                                                "click_text_until_absent",
                                                "click_selector",
                                                "expect_selector",
                                                "expect_selector_count_at_least",
                                                "expect_text",
                                                "wait_for_text_absent",
                                                "press",
                                                "wait_ms",
                                                "wait",
                                                "pause",
                                            ],
                                        },
                                        "text": {"type": "string"},
                                        "selector": {"type": "string"},
                                        "count": {"type": "integer", "minimum": 1, "maximum": 50},
                                        "key": {"type": "string"},
                                        "ms": {"type": "integer", "minimum": 0, "maximum": 5000},
                                        "max_clicks": {"type": "integer", "minimum": 1, "maximum": 50},
                                        "settle_ms": {"type": "integer", "minimum": 0, "maximum": 2000},
                                        "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                                    },
                                    "required": ["type"],
                                    "additionalProperties": False,
                                },
                            },
                            "expect_text": {
                                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 20}],
                                "description": "Final-state text that must be visible before the screenshot counts as verified.",
                            },
                            "expect_selector": {
                                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 20}],
                                "description": "Final-state CSS selector that must be visible before the screenshot counts as verified.",
                            },
                            "expect_selector_count_at_least": {
                                "oneOf": [
                                    {
                                        "type": "object",
                                        "properties": {
                                            "selector": {"type": "string"},
                                            "count": {"type": "integer", "minimum": 1, "maximum": 50},
                                            "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                                        },
                                        "required": ["selector", "count"],
                                        "additionalProperties": False,
                                    },
                                    {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "selector": {"type": "string"},
                                                "count": {"type": "integer", "minimum": 1, "maximum": 50},
                                                "timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                                            },
                                            "required": ["selector", "count"],
                                            "additionalProperties": False,
                                        },
                                        "maxItems": 20,
                                    },
                                ],
                                "description": "Final-state CSS selector that must resolve to at least count visible nodes before the screenshot counts as verified.",
                            },
                            "forbidden_text": {
                                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 20}],
                                "description": "Text that must be absent before the screenshot counts as verified; use this to ensure tutorial/dialog text such as Next is gone.",
                            },
                            "fail_if_text_visible": {
                                "oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}, "maxItems": 20}],
                                "description": "Alias for forbidden_text.",
                            },
                            "assert_timeout_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
                            "auto_milestone": {"type": "boolean", "default": True},
                        },
                        "required": ["url"],
                        "additionalProperties": False,
                    },
                }
            )
        if self._mcp_server_enabled("lcr_web"):
            dynamic_tools.extend(
                {
                    "name": str(tool.get("name") or ""),
                    "description": str(tool.get("description") or ""),
                    "inputSchema": dict(tool.get("inputSchema") or {}),
                }
                for tool in lcr_web_dynamic_tools()
                if tool.get("name")
            )
        if self._mcp_server_enabled("yunwu_image"):
            dynamic_tools.extend(
                {
                    "name": str(tool.get("name") or ""),
                    "description": str(tool.get("description") or ""),
                    "inputSchema": dict(tool.get("inputSchema") or {}),
                }
                for tool in yunwu_image_dynamic_tools()
                if tool.get("name")
            )
        return dynamic_tools

    def _lcr_dynamic_tool_names(self) -> set[str]:
        return {str(tool.get("name") or "") for tool in self._lcr_dynamic_tools()}

    def _mcp_server_enabled(self, name: str) -> bool:
        try:
            servers = self._mcp_config.enabled_servers()
        except Exception:
            return False
        return any(str(server.get("name") or "") == name for server in servers)

    def _thread_permission_overrides(self, permission_mode: str) -> dict[str, Any]:
        mode = (permission_mode or "auto").strip().lower()
        if mode == "ask":
            return {"approvalPolicy": "untrusted", "sandbox": "read-only"}
        if mode == "full":
            return {"approvalPolicy": "never", "sandbox": "danger-full-access"}
        return {"approvalPolicy": "on-request", "sandbox": "workspace-write"}

    def _turn_permission_overrides(self, permission_mode: str) -> dict[str, Any]:
        mode = (permission_mode or "auto").strip().lower()
        if mode == "ask":
            return {
                "approvalPolicy": "untrusted",
                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            }
        if mode == "full":
            return {
                "approvalPolicy": "never",
                "sandboxPolicy": {"type": "dangerFullAccess"},
            }
        return {
            "approvalPolicy": "on-request",
            "sandboxPolicy": {
                "type": "workspaceWrite",
                "writableRoots": [self._runtime_workspace_root()],
                "networkAccess": False,
                "excludeTmpdirEnvVar": False,
                "excludeSlashTmp": False,
            },
        }

    def _collaboration_mode_params(
        self,
        *,
        profile: dict[str, Any],
        model: str | None,
        effort: str | None,
        collaboration_mode: str | None,
    ) -> dict[str, Any] | None:
        if collaboration_mode is None:
            return None
        mode = collaboration_mode.strip().lower()
        if mode not in VALID_COLLABORATION_MODES:
            raise ValueError(f"Unsupported collaboration mode: {collaboration_mode}")
        return {
            "mode": mode,
            "settings": {
                "model": codex_model_id(profile, model),
                "reasoning_effort": codex_reasoning_effort(effort or profile.get("reasoning_effort")),
                "developer_instructions": None,
            },
        }

    def _read_thread_cache(self) -> dict[str, Any]:
        path = self._projects.require_shell_state_root() / "thread_cache.json"
        with self._thread_cache_lock:
            try:
                cache = read_json(path, {"by_id": {}, "updated_at": None})
            except Exception as exc:  # noqa: BLE001
                self._record_event(
                    {
                        "type": "thread_cache_read_failed",
                        "path": str(path),
                        "error": str(exc)[:300],
                    }
                )
                return {"by_id": {}, "updated_at": None}
        if not isinstance(cache, dict):
            return {"by_id": {}, "updated_at": None}
        return cache

    def _cached_threads_response(self, *, archived: bool = False, warning: str | None = None) -> dict[str, Any]:
        if archived:
            return {"threads": [], "next_cursor": None, "backwards_cursor": None, "warning": warning}
        cache = self._read_thread_cache()
        by_id = dict(cache.get("by_id") or {})
        current = self._projects.current_project or {}
        ordered_ids: list[str] = []
        for thread_id in current.get("recent_threads") or []:
            if isinstance(thread_id, str) and thread_id and thread_id not in ordered_ids:
                ordered_ids.append(thread_id)
        for thread_id in by_id.keys():
            if thread_id not in ordered_ids:
                ordered_ids.append(thread_id)
        threads = [thread for thread_id in ordered_ids if (thread := self._cached_thread(thread_id))]
        return {"threads": threads, "next_cursor": None, "backwards_cursor": None, "warning": warning}

    def _cached_thread(self, thread_id: str, warning: str | None = None) -> dict[str, Any] | None:
        if not thread_id:
            return None
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        native_thread = entry.get("thread")
        if isinstance(native_thread, dict):
            thread = dict(native_thread)
            if warning:
                thread["shellWarning"] = warning
            return self._decorate_thread(thread)
        if not entry and thread_id not in (self._projects.current_project or {}).get("recent_threads", []):
            return None
        name = entry.get("name") or thread_id
        thread = {
            "id": thread_id,
            "sessionId": thread_id,
            "name": name,
            "preview": "",
            "status": self._thread_cache_status(thread_id) or {"type": "idle"},
            "cwd": self._runtime_workspace_root(),
            "turns": [],
            "shellWarning": warning,
        }
        return self._decorate_thread(thread)

    def _native_cached_threads(self) -> list[dict[str, Any]]:
        cache = self._read_thread_cache()
        threads: list[dict[str, Any]] = []
        for entry in list((cache.get("by_id") or {}).values()):
            if not isinstance(entry, dict):
                continue
            native_thread = entry.get("thread")
            if not isinstance(native_thread, dict):
                continue
            threads.append(self._decorate_thread(dict(native_thread)))
        threads.sort(key=lambda item: str(item.get("status", {}).get("updated_at") or ""), reverse=True)
        return threads

    def _read_native_thread(self, thread_id: str) -> dict[str, Any] | None:
        if not thread_id:
            return None
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        native_thread = entry.get("thread")
        if not isinstance(native_thread, dict):
            return None
        return dict(native_thread)

    def _cache_thread_entry(self, thread_id: str, patch: dict[str, Any]) -> None:
        if not thread_id:
            return
        with self._thread_cache_lock:
            cache = self._read_thread_cache()
            by_id = dict(cache.get("by_id") or {})
            current = dict(by_id.get(thread_id) or {})
            sanitized_patch = dict(patch)
            if "name" in sanitized_patch:
                sanitized_patch["name"] = _display_thread_name(
                    sanitized_patch.get("name"),
                    sanitized_patch.get("provider_id") or current.get("provider_id"),
                )
            merged = {
                **current,
                **{key: value for key, value in sanitized_patch.items() if value is not None},
                "thread_id": thread_id,
                "updated_at": now_iso(),
            }
            by_id[thread_id] = merged
            cache["by_id"] = by_id
            cache["updated_at"] = now_iso()
            path = self._projects.require_shell_state_root() / "thread_cache.json"
            try:
                write_json(path, cache)
            except Exception as exc:  # noqa: BLE001
                self._record_event(
                    {
                        "type": "thread_cache_write_failed",
                        "thread_id": thread_id,
                        "path": str(path),
                        "error": str(exc)[:300],
                    }
                )
                return
        hint_patch = {key: value for key, value in merged.items() if key != "thread"}
        self._record_project_context_hint(thread_id, hint_patch)

    def _record_project_context_hint(self, thread_id: str, patch: dict[str, Any]) -> None:
        if self._project_context is None:
            return
        try:
            self._project_context.record_thread_hint(thread_id, patch)
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "project_context_hint_failed", "thread_id": thread_id, "error": str(exc)[:300]})

    def _record_project_context_notification(self, method: str, payload: Any) -> None:
        if self._project_context is None:
            return
        try:
            self._project_context.record_runtime_notification(method, payload)
            if self._tasks is not None and isinstance(payload, dict):
                thread_id = str(payload.get("threadId") or payload.get("thread_id") or "")
                if not thread_id and isinstance(payload.get("thread"), dict):
                    thread_id = str(payload.get("thread", {}).get("id") or "")
                if method == "turn/plan/updated" and thread_id:
                    self._tasks.record_plan(
                        thread_id,
                        {
                            "turn_id": str(payload.get("turnId") or ""),
                            "explanation": payload.get("explanation"),
                            "steps": list(payload.get("plan") or []),
                            "updated_at": now_iso(),
                        },
                    )
                elif method == "thread/goal/updated" and thread_id:
                    self._tasks.record_goal(thread_id, payload.get("goal") or {})
                elif method == "thread/goal/cleared" and thread_id:
                    self._tasks.record_goal(thread_id, None)
        except Exception as exc:  # noqa: BLE001
            self._record_event({"type": "project_context_notification_failed", "method": method, "error": str(exc)[:300]})

    def _thread_settings_for(self, thread_id: str) -> dict[str, Any]:
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        task_entry = self._task_thread_entry(thread_id)
        if task_entry:
            entry = {**task_entry, **entry}
        current = self._projects.current_project or {}
        normalized = self._normalize_shell_settings(entry, current_project=current, prefer_project_defaults=True)
        cache_patch = {
            "profile_id": normalized.get("profile_id"),
            "model": normalized.get("model"),
            "reasoning_effort": normalized.get("reasoning_effort"),
            "permission_mode": normalized.get("permission_mode"),
            "collaboration_mode": normalized.get("collaboration_mode"),
            "execution_backend": normalized.get("execution_backend"),
        }
        if any(entry.get(key) != value for key, value in cache_patch.items() if value is not None):
            self._cache_thread_entry(thread_id, cache_patch)
        return normalized

    def _task_thread_entry(self, thread_id: str) -> dict[str, Any]:
        if self._tasks is None:
            return {}
        try:
            task = self._tasks.current_task() or {}
        except Exception:
            return {}
        for collection_key in ("provider_threads", "fork_threads"):
            for item in list(task.get(collection_key) or []):
                if str((item or {}).get("thread_id") or "") == thread_id:
                    return dict(item)
        return {}

    def _normalize_shell_settings(
        self,
        settings: dict[str, Any],
        *,
        current_project: dict[str, Any],
        prefer_project_defaults: bool,
    ) -> dict[str, Any]:
        project_profile_id = str(current_project.get("default_profile_id") or "").strip()
        chosen_profile_id = str(settings.get("profile_id") or "").strip()
        target_profile = self._resolve_shell_profile(chosen_profile_id or project_profile_id)
        provider_id = str(target_profile.get("provider_id") or "openai").strip() or "openai"
        profile_id = str(target_profile.get("profile_id") or project_profile_id or "openai-compatible").strip()
        project_model = self._normalize_shell_model(current_project.get("default_model"), provider_id)
        chosen_model = self._normalize_shell_model(settings.get("model"), provider_id)
        if prefer_project_defaults and not chosen_model:
            chosen_model = project_model
        if not chosen_model or self._shell_model_provider_mismatch(chosen_model, provider_id):
            chosen_model = self._normalize_shell_model(target_profile.get("model"), provider_id) or project_model
        project_effort = codex_reasoning_effort(current_project.get("default_effort"))
        chosen_effort = codex_reasoning_effort(settings.get("reasoning_effort"))
        if prefer_project_defaults and not str(settings.get("reasoning_effort") or "").strip():
            chosen_effort = project_effort
        permission_mode = str(settings.get("permission_mode") or "").strip().lower() or "auto"
        if permission_mode not in {"ask", "auto", "full"}:
            permission_mode = "auto"
        collaboration_mode = str(settings.get("collaboration_mode") or "").strip().lower() or "default"
        if collaboration_mode not in VALID_COLLABORATION_MODES:
            collaboration_mode = "default"
        execution_backend = self._normalize_execution_backend(settings.get("execution_backend"))
        return {
            "profile_id": profile_id,
            "model": (
                chosen_model
                or self._normalize_shell_model(target_profile.get("model"), provider_id)
                or self._default_model_for_provider(provider_id)
            ),
            "reasoning_effort": chosen_effort or codex_reasoning_effort(target_profile.get("reasoning_effort")),
            "permission_mode": permission_mode,
            "collaboration_mode": collaboration_mode,
            "execution_backend": execution_backend,
        }

    def _normalize_execution_backend(self, value: Any) -> str:
        backend = str(value or "").strip().lower() or "app_server"
        if backend not in VALID_EXECUTION_BACKENDS:
            return "app_server"
        return backend

    def _resolve_shell_profile(self, profile_id: str) -> dict[str, Any]:
        fallback = "openai-compatible"
        try:
            return self._profiles.resolve_runtime_profile(profile_id or fallback)
        except Exception:
            try:
                return self._profiles.resolve_runtime_profile(fallback)
            except Exception:
                return {
                    "profile_id": fallback,
                    "provider_id": "openai",
                    "model": _OPENAI_DEFAULT_MODEL,
                    "reasoning_effort": "high",
                }

    @staticmethod
    def _default_model_for_provider(provider_id: str) -> str:
        provider = str(provider_id or "openai").strip() or "openai"
        preferred_model = (preferred_provider_model_record(provider, include_deprecated=False) or {}).get("native_model")
        return str(preferred_model or _OPENAI_DEFAULT_MODEL).strip() or _OPENAI_DEFAULT_MODEL

    def _normalize_shell_model(self, value: Any, provider_id: str) -> str:
        model = str(value or "").strip()
        if not model:
            return ""
        if "/" not in model:
            return model
        model_provider, native_model = model.split("/", 1)
        if model_provider.strip().lower() == provider_id.strip().lower():
            return native_model.strip()
        return model

    def _shell_model_provider_mismatch(self, model: str, provider_id: str) -> bool:
        if "/" not in model:
            return False
        model_provider, _native_model = model.split("/", 1)
        return model_provider.strip().lower() != provider_id.strip().lower()

    def _decorate_thread(self, thread: dict[str, Any]) -> dict[str, Any]:
        thread_id = str(thread.get("id") or "")
        settings = self._thread_settings_for(thread_id) if thread_id else {}
        display_name = (
            _display_thread_name(thread.get("name"), settings.get("provider_id") or settings.get("profile_id"))
            or self._thread_cache_name(thread_id)
            or str(thread.get("preview") or thread_id)
        )
        normalized_status = self._normalize_thread_status(thread)
        if thread_id:
            normalized_status = self._overlay_cached_thread_status(thread_id, normalized_status)
        return {**thread, "status": normalized_status, "shellSettings": settings, "displayName": display_name}

    def _decorate_turn_coding_events(self, thread: dict[str, Any]) -> dict[str, Any]:
        turns = list(thread.get("turns") or [])
        if not turns:
            return thread
        thread_id = str(thread.get("id") or "")
        task_id = self._task_id_for_thread(thread_id)
        execution_backend = str((thread.get("shellSettings") or {}).get("execution_backend") or "").strip()
        source = "native_kernel" if execution_backend == "native_kernel" else "codex_app_server"
        decorated_turns: list[dict[str, Any]] = []
        changed = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            enriched = dict(turn)
            if thread_id and not enriched.get("source_thread_id") and not enriched.get("sourceThreadId"):
                enriched["source_thread_id"] = thread_id
            if not enriched.get("provider_id") and not enriched.get("providerId"):
                provider_id = str((thread.get("shellSettings") or {}).get("provider_id") or "").strip()
                if provider_id:
                    enriched["provider_id"] = provider_id
            if not enriched.get("model"):
                model = str((thread.get("shellSettings") or {}).get("model") or "").strip()
                if model:
                    enriched["model"] = model
            coding_events = project_turn_to_coding_events(
                task_id=task_id,
                visible_thread_id=thread_id or "thread:unknown",
                turn=enriched,
                source=source,
            )
            if enriched.get("coding_events") != coding_events:
                enriched["coding_events"] = coding_events
                changed = True
            decorated_turns.append(enriched)
        return {**thread, "turns": decorated_turns} if changed else thread

    def _task_id_for_thread(self, thread_id: str) -> str:
        if not thread_id or self._tasks is None:
            return ""
        snapshot = self._tasks.snapshot() or {}
        for task in list(snapshot.get("tasks") or []):
            if not isinstance(task, dict):
                continue
            if any(str(item.get("thread_id") or "") == thread_id for item in list(task.get("provider_threads") or []) if isinstance(item, dict)):
                return str(task.get("task_id") or "")
        return ""

    def _normalize_thread_status(self, thread: dict[str, Any]) -> dict[str, Any] | Any:
        status = thread.get("status")
        if not isinstance(status, dict):
            return status
        status_type = str(status.get("type") or "")
        if status_type not in {"systemError", "notLoaded"}:
            return status
        turns = [item for item in list(thread.get("turns") or []) if isinstance(item, dict)]
        if not turns:
            return status
        latest_turn = turns[-1]
        latest_error = latest_turn.get("error")
        if str(latest_turn.get("status") or "") == "completed" and (
            latest_error is None or latest_error == "" or latest_error == {}
        ):
            normalized = dict(status)
            normalized["type"] = "idle"
            normalized["stale_error_type"] = status_type
            normalized["stale_error_normalized"] = True
            return normalized
        return status

    def _thread_cache_status(self, thread_id: str) -> dict[str, Any] | None:
        if not thread_id:
            return None
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        status = entry.get("status")
        return dict(status) if isinstance(status, dict) else None

    def _overlay_cached_thread_status(self, thread_id: str, status: dict[str, Any] | Any) -> dict[str, Any] | Any:
        if not isinstance(status, dict):
            return status
        cached_status = self._thread_cache_status(thread_id)
        if not isinstance(cached_status, dict):
            return status
        if str(status.get("type") or "") not in {"systemError", "notLoaded"}:
            return status
        if str(cached_status.get("type") or "") == "idle" and cached_status.get("stale_error_normalized"):
            return cached_status
        return status

    def _overlay_dynamic_tool_events(self, thread: dict[str, Any]) -> dict[str, Any]:
        """Make app-server dynamic tool events visible when thread/read omits them."""
        thread_id = str(thread.get("id") or "")
        turns = list(thread.get("turns") or [])
        if not thread_id or not turns:
            return thread
        turn_ids = {str(turn.get("id") or "") for turn in turns if isinstance(turn, dict)}
        if not turn_ids:
            return thread
        with self._lock:
            self._hydrate_events_from_disk_locked()
            events = list(self._events)
        tool_items: dict[str, list[tuple[int, dict[str, Any]]]] = {turn_id: [] for turn_id in turn_ids}
        latest_by_item: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
        for event in events:
            if event.get("type") != "notification" or event.get("method") not in {"item/started", "item/completed"}:
                continue
            params = dict(event.get("params") or {})
            if str(params.get("threadId") or "") != thread_id:
                continue
            turn_id = str(params.get("turnId") or "")
            if turn_id not in turn_ids:
                continue
            item = dict(params.get("item") or {})
            if item.get("type") != "dynamicToolCall":
                continue
            item_id = str(item.get("id") or "")
            if not item_id:
                continue
            latest_by_item[(turn_id, item_id)] = (int(event.get("index") or 0), item)
        for (turn_id, _item_id), entry in latest_by_item.items():
            tool_items.setdefault(turn_id, []).append(entry)
        decorated_turns: list[dict[str, Any]] = []
        changed_thread = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            turn_id = str(turn.get("id") or "")
            extras = [item for _index, item in sorted(tool_items.get(turn_id, []), key=lambda pair: pair[0])]
            if not extras:
                decorated_turns.append(turn)
                continue
            items = [dict(item) if isinstance(item, dict) else item for item in list(turn.get("items") or [])]
            latest_by_id = {
                str(item.get("id") or ""): item
                for item in extras
                if isinstance(item, dict) and str(item.get("id") or "")
            }
            merged_items: list[Any] = []
            turn_changed = False
            existing_ids: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    merged_items.append(item)
                    continue
                item_id = str(item.get("id") or "")
                if item_id:
                    existing_ids.add(item_id)
                latest_item = latest_by_id.get(item_id)
                if latest_item:
                    merged_item = {**item, **latest_item}
                    if merged_item != item:
                        turn_changed = True
                    merged_items.append(merged_item)
                else:
                    merged_items.append(item)
            missing = [item for item in extras if str(item.get("id") or "") not in existing_ids]
            if not missing:
                if turn_changed:
                    decorated_turns.append({**turn, "items": merged_items})
                    changed_thread = True
                else:
                    decorated_turns.append(turn)
                continue
            insert_at = next(
                (idx for idx, item in enumerate(merged_items) if isinstance(item, dict) and item.get("type") == "agentMessage"),
                len(merged_items),
            )
            merged_items[insert_at:insert_at] = missing
            decorated_turns.append({**turn, "items": merged_items})
            changed_thread = True
        return {**thread, "turns": decorated_turns} if changed_thread else thread

    def _decorate_dynamic_tool_evidence(self, thread: dict[str, Any]) -> dict[str, Any]:
        """Attach compact, UI-ready verification metadata to dynamic tool items."""
        turns = list(thread.get("turns") or [])
        if not turns:
            return thread
        decorated_turns: list[dict[str, Any]] = []
        changed = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            items = list(turn.get("items") or [])
            decorated_items: list[Any] = []
            for item in items:
                if not isinstance(item, dict):
                    decorated_items.append(item)
                    continue
                evidence = self._item_verified_evidence(item)
                if evidence:
                    item = {**item, "lcrVerifiedEvidence": evidence}
                    changed = True
                decorated_items.append(item)
            decorated_turns.append({**turn, "items": decorated_items} if changed else turn)
        return {**thread, "turns": decorated_turns} if changed else thread

    def _item_verified_evidence(self, item: dict[str, Any]) -> dict[str, Any] | None:
        item_type = str(item.get("type") or "")
        if item_type == "dynamicToolCall":
            return self._dynamic_tool_verified_evidence(item)
        if item_type == "commandExecution":
            return self._command_execution_verified_evidence(item)
        return None

    def _dynamic_tool_verified_evidence(self, item: dict[str, Any]) -> dict[str, Any] | None:
        tool = str(item.get("tool") or item.get("name") or "").strip()
        if not tool:
            return None
        summary = self._dynamic_tool_summary_from_item(item)
        verified = bool(summary.get("tool_event_verified")) if summary else False
        content_text = self._dynamic_tool_content_text(item)
        if not verified and "tool_event_verified" in content_text:
            verified = True
        if not verified and str(item.get("status") or "").lower() == "completed" and summary:
            if self._dynamic_tool_evidence_values(summary, ("local_path", "asset_id", "record_id", "url", "path", "screenshot_path")):
                verified = True
        evidence: dict[str, Any] = {
            "tool": tool,
            "server": self._dynamic_tool_server(tool),
            "status": item.get("status") or ("completed" if verified else "unknown"),
            "verified": verified,
            "label": "tool-event verified" if verified else "tool-event unverified",
            "summary": self._dynamic_tool_evidence_lines(tool, summary, content_text),
        }
        paths = self._dynamic_tool_evidence_values(summary, ("path", "screenshot_path", "manifest_path", "local_path"))
        urls = self._dynamic_tool_evidence_values(summary, ("url", "navigation_url"))
        if paths:
            evidence["paths"] = paths[:6]
        if urls:
            evidence["urls"] = urls[:6]
        return evidence

    def _command_execution_verified_evidence(self, item: dict[str, Any]) -> dict[str, Any] | None:
        command = str(item.get("command") or "").strip()
        if not command:
            return None
        status = str(item.get("status") or "unknown")
        exit_code = item.get("exitCode")
        completed = status in {"completed", "failed", "cancelled"} or exit_code is not None
        summary = [f"command: {command[:220]}"]
        if exit_code is not None:
            summary.append(f"exit code: {exit_code}")
        output = str(item.get("aggregatedOutput") or item.get("output") or "").strip()
        if output:
            summary.append("output: " + " ".join(output.split())[:220])
        return {
            "tool": "shell_command",
            "server": "codex_builtin",
            "status": status,
            "verified": completed,
            "label": "command-event verified" if completed else "command-event pending",
            "summary": summary[:6],
        }

    def _dynamic_tool_content_text(self, item: dict[str, Any]) -> str:
        texts: list[str] = []
        for content in item.get("contentItems") or []:
            if isinstance(content, dict) and content.get("type") in {"inputText", "text"}:
                texts.append(str(content.get("text") or ""))
        return "\n".join(texts).strip()

    def _dynamic_tool_summary_from_item(self, item: dict[str, Any]) -> dict[str, Any]:
        content_text = self._dynamic_tool_content_text(item)
        if not content_text:
            return {}
        match = re.search(r"\{.*\}\s*$", content_text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except Exception:  # noqa: BLE001
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _dynamic_tool_evidence_lines(self, tool: str, summary: dict[str, Any], fallback_text: str) -> list[str]:
        lines: list[str] = []
        if tool in BROWSER_SMOKE_TOOL_ALIASES:
            status = summary.get("status")
            label = summary.get("label")
            if status or label:
                lines.append(f"browser smoke {label or ''} {status or ''}".strip())
            if summary.get("screenshot_path"):
                lines.append(f"screenshot: {summary.get('screenshot_path')}")
            errors = summary.get("console_errors")
            if isinstance(errors, list):
                lines.append(f"console errors: {len(errors)}")
            request_failures = summary.get("request_failures")
            if isinstance(request_failures, list):
                lines.append(f"request failures: {len(request_failures)}")
        elif tool.startswith("lcr_web_"):
            if summary.get("record_id"):
                lines.append(f"research record: {summary.get('record_id')}")
            result = summary.get("result")
            sources = result.get("sources") if isinstance(result, dict) else summary.get("sources")
            if isinstance(sources, list):
                lines.append(f"sources: {len(sources)}")
                for source in sources[:2]:
                    if isinstance(source, dict) and source.get("url"):
                        lines.append(str(source.get("url")))
        elif tool.startswith("yunwu_image_"):
            if summary.get("actual_n") is not None or summary.get("requested_n") is not None:
                lines.append(f"images: {summary.get('actual_n', '?')}/{summary.get('requested_n', '?')}")
            for asset_id in self._dynamic_tool_evidence_values(summary, ("asset_id",)):
                lines.append(f"asset: {asset_id}")
            if summary.get("has_alpha") is not None:
                lines.append(f"alpha: {summary.get('has_alpha')}")
        if not lines and fallback_text:
            compact = " ".join(fallback_text.split())
            lines.append(compact[:240])
        return lines[:6]

    def _dynamic_tool_evidence_values(self, value: Any, keys: tuple[str, ...]) -> list[str]:
        found: list[str] = []
        if isinstance(value, dict):
            for key in keys:
                current = value.get(key)
                if isinstance(current, str) and current:
                    found.append(current)
            for current in value.values():
                found.extend(self._dynamic_tool_evidence_values(current, keys))
        elif isinstance(value, list):
            for item in value:
                found.extend(self._dynamic_tool_evidence_values(item, keys))
        deduped: list[str] = []
        for item in found:
            if item not in deduped:
                deduped.append(item)
        return deduped

    def _decorate_turn_completion_quality(self, thread: dict[str, Any]) -> dict[str, Any]:
        turns = list(thread.get("turns") or [])
        if not turns:
            return thread
        decorated_turns: list[dict[str, Any]] = []
        changed = False
        for turn in turns:
            if not isinstance(turn, dict):
                decorated_turns.append(turn)
                continue
            quality = self._turn_completion_quality(turn)
            if quality:
                decorated_turns.append({**turn, "lcrCompletionQuality": quality})
                changed = True
            else:
                decorated_turns.append(turn)
        return {**thread, "turns": decorated_turns} if changed else thread

    def _turn_completion_quality(self, turn: dict[str, Any]) -> dict[str, Any] | None:
        if str(turn.get("status") or "") != "completed":
            return None
        items = [item for item in list(turn.get("items") or []) if isinstance(item, dict)]
        tool_count = sum(1 for item in items if item.get("type") in {"dynamicToolCall", "commandExecution"})
        if tool_count == 0:
            return None
        agent_texts = [str(item.get("text") or "").strip() for item in items if item.get("type") == "agentMessage"]
        nonempty = [text for text in agent_texts if text]
        max_chars = max((len(text) for text in nonempty), default=0)
        final_text = nonempty[-1] if nonempty else ""
        if max_chars >= 240:
            return None
        weak_markers = (
            "let me",
            "now i",
            "now let",
            "i will",
            "i'll",
            "produce the",
            "start by",
        )
        looks_like_progress_note = any(marker in final_text.lower() for marker in weak_markers)
        if not looks_like_progress_note and max_chars >= 120:
            return None
        return {
            "status": "suspect",
            "reason": "completed_with_short_or_progress_only_final_after_verified_activity",
            "tool_item_count": tool_count,
            "agent_message_count": len(nonempty),
            "max_agent_chars": max_chars,
            "final_preview": final_text[:240],
            "recommended_action": "continue_or_retry_final_answer",
        }

    def _thread_cache_name(self, thread_id: str) -> str | None:
        if not thread_id:
            return None
        cache = self._read_thread_cache()
        entry = dict((cache.get("by_id") or {}).get(thread_id) or {})
        name = entry.get("name")
        return _display_thread_name(name, entry.get("provider_id")) if name else None

    def _sync_thread_settings_from_notification(self, payload: dict[str, Any]) -> None:
        thread_id = str(payload.get("threadId") or "")
        thread_settings = dict(payload.get("threadSettings") or {})
        if not thread_id:
            return
        self._cache_thread_entry(
            thread_id,
            {
                "model": thread_settings.get("model"),
                "reasoning_effort": thread_settings.get("effort"),
                "collaboration_mode": (thread_settings.get("collaborationMode") or {}).get("mode")
                if isinstance(thread_settings.get("collaborationMode"), dict)
                else None,
            },
        )

    def _record_event(self, event: dict[str, Any]) -> None:
        record = redact_sensitive({"index": None, "timestamp": now_iso(), **event})
        with self._lock:
            record["index"] = len(self._events)
            self._events.append(record)
        try:
            shell_root = self._projects.require_shell_state_root()
            append_jsonl(shell_root / "runtime_events.jsonl", record)
        except Exception:
            pass

    def _event_for_response(self, event: dict[str, Any]) -> dict[str, Any]:
        return self._summarize_value(event, 0)

    def _summarize_value(self, value: Any, depth: int) -> Any:
        if depth > EVENT_RESPONSE_DEPTH_LIMIT:
            return {"summary": "Nested event details truncated for UI response."}
        if isinstance(value, str):
            if len(value) <= EVENT_RESPONSE_STRING_LIMIT:
                return value
            omitted = len(value) - EVENT_RESPONSE_STRING_LIMIT
            return value[:EVENT_RESPONSE_STRING_LIMIT] + f"\n...[truncated {omitted} chars]"
        if isinstance(value, list):
            items = [self._summarize_value(item, depth + 1) for item in value[:EVENT_RESPONSE_LIST_LIMIT]]
            if len(value) > EVENT_RESPONSE_LIST_LIMIT:
                items.append({"summary": f"{len(value) - EVENT_RESPONSE_LIST_LIMIT} additional items truncated."})
            return items
        if isinstance(value, dict):
            return {key: self._summarize_value(item, depth + 1) for key, item in value.items()}
        return value


class _RuntimeRequestClient:
    """Stable request facade for one prepared runtime.

    `start_turn` can perform several app-server calls before the actual
    `turn/start`: read source thread, fork/start a provider thread, then start
    the turn. UI polling may concurrently request another provider profile. This
    facade keeps the whole handoff on the intended runtime and retries one
    transport-level app-server disconnect without recording large request
    payloads or secrets.
    """

    def __init__(self, runtime: RuntimeService, runtime_status: dict[str, Any]) -> None:
        self._runtime = runtime
        self._runtime_status = runtime_status
        self._client = runtime._ensure_client(runtime_status)

    def is_running(self) -> bool:
        return self._client.is_running()

    def request(self, method: str, params: Any | None = None, timeout: float = 120.0) -> Any:
        try:
            return self._client.request(method, params, timeout=timeout)
        except RuntimeError as exc:
            if not self._runtime._is_app_server_transport_error(exc):
                raise
            self._runtime._record_event(
                {
                    "type": "runtime_request_transport_retry",
                    "method": method,
                    "thread_id": str(params.get("threadId") or "") if isinstance(params, dict) else None,
                    "error": str(exc),
                    "runtime": self._runtime_status,
                }
            )
            self._runtime._close_client(f"{method}_transport_retry")
            self._client = self._runtime._ensure_client(self._runtime_status)
            return self._client.request(method, params, timeout=timeout)

