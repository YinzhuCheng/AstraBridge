from __future__ import annotations

import argparse
import json
import os
import re
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .asset_registry_service import AssetRegistryService
from .agentic_update_service import AgenticUpdateService
from .automations import AutomationService
from .browser_workbench_service import BrowserWorkbenchService
from .checkpoint_service import CheckpointService
from .common import DEFAULT_PORT, public_error
from .common import now_iso, read_json, write_json
from .capabilities import capability_artifact_snapshot, capability_smoke_snapshot
from .capabilities.runtime import CapabilityRuntime
from .codex_plugin_skill_project_presets import mutate_project_plugin_skill_presets
from .dogfood_run_service import DogfoodRunService
from .image_prompt_strategy import build_rewrite_instruction, prompt_guides_payload
from .isolation_audit_service import IsolationAuditService
from .modal_service import ModalService
from .metadata_service import MetadataService
from .mcp_config_service import McpConfigService
from .llm_api_manager_service import LlmApiManagerService
from .runtime_config_service import RuntimeConfigService
from .official_login_guard import disabled_status
from .official_codex_service import OfficialCodexService
from .profile_service import ProfileService
from .project_context_service import ProjectContextService
from .project_service import ProjectService
from .project_tools_service import ProjectToolsService
from .provider_compatibility_smoke import run_provider_compatibility_smoke
from .router_config_service import RouterConfigService
from .router_service import RouterService
from .runtime_supervisor_service import RuntimeSupervisorService
from .runtime_service import RuntimeService
from .secret_service import SecretService
from .sidecar_provenance import build_sidecar_provenance
from .task_conversation_service import TaskConversationService
from .task_service import TaskService, _display_task_title
from .title_suggestion_service import TitleSuggestionService
from .web_tool_service import AstraBridgeWebService
from .wsl_dependency_service import WslDependencyService
from .yunwu_image_service import YunwuImageService


ALLOWED_ORIGINS = {
    "http://127.0.0.1:4181",
    "http://localhost:4181",
    "http://tauri.localhost",
    "tauri://localhost",
}
SMOKE_TASK_PREFIX_PATTERN = re.compile(r"^Step\s+\d+\s+(?:source|target)\s+for\s+", re.IGNORECASE)


def configured_allowed_origins() -> set[str]:
    raw = os.environ.get("ASTRABRIDGE_ALLOWED_ORIGINS", "")
    configured = {
        item.strip().rstrip("/")
        for item in raw.replace(";", ",").split(",")
        if item.strip()
    }
    return {*ALLOWED_ORIGINS, *configured}


def allow_any_loopback_origin() -> bool:
    return os.environ.get("ASTRABRIDGE_ALLOW_ANY_LOOPBACK_ORIGIN") == "1"


def is_loopback_origin(origin: str | None) -> bool:
    if not origin:
        return False
    try:
        parsed = urllib.parse.urlparse(origin)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def is_allowed_origin(origin: str | None) -> bool:
    if not origin:
        return False
    normalized = origin.rstrip("/")
    if normalized in configured_allowed_origins():
        return True
    return allow_any_loopback_origin() and is_loopback_origin(normalized)


def turn_text_from_payload(payload: dict[str, Any]) -> str:
    """Accept historical turn input aliases used by scripts and UI versions."""
    raw = payload.get("text")
    if raw is None:
        raw = payload.get("prompt")
    if raw is None:
        raw = payload.get("message")
    return str(raw or "")


def sse_frame(*, event: str | None = None, data: Any | None = None, comment: str | None = None, retry: int | None = None) -> bytes:
    """Format a Server-Sent Events frame with JSON-safe multiline handling."""
    lines: list[str] = []
    if comment is not None:
        for line in str(comment).splitlines() or [""]:
            lines.append(f": {line}")
    if retry is not None:
        lines.append(f"retry: {int(retry)}")
    if event:
        lines.append(f"event: {event}")
    if data is not None:
        text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        for line in str(text).splitlines() or [""]:
            lines.append(f"data: {line}")
    lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def visible_task_title(value: Any) -> str:
    title = str(value or "").strip()
    if not title:
        return ""
    return SMOKE_TASK_PREFIX_PATTERN.sub("", title).strip()


def normalize_task_conversation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    thread = payload.get("thread")
    if not isinstance(thread, dict):
        return payload
    normalized = dict(payload)
    normalized_thread = dict(thread)
    normalized_title = visible_task_title(normalized_thread.get("displayName") or normalized_thread.get("name"))
    if normalized_title:
        normalized_thread["name"] = normalized_title
        normalized_thread["displayName"] = normalized_title
    normalized["thread"] = normalized_thread
    return normalized


class AppContext:
    def __init__(self, seed_root: Path) -> None:
        self.seed_root = seed_root.expanduser().resolve()
        self.projects = ProjectService()
        self.profiles = ProfileService()
        self.secrets = SecretService()
        self.router_config = RouterConfigService(self.profiles)
        self.official_codex = OfficialCodexService(self.profiles, self.router_config)
        self.audit = IsolationAuditService()
        self.mcp_config = McpConfigService()
        router_host = os.environ.get("ASTRABRIDGE_LISTEN_HOST") or "0.0.0.0"
        router_port = int(os.environ.get("ASTRABRIDGE_PORT") or 8787)
        self.router = RouterService(self.profiles, self.router_config, host=router_host, port=router_port)
        self.router.start()
        router_status = self.router.status()
        os.environ["ASTRABRIDGE_BASE_URL"] = str(router_status.get("base_url") or "")
        os.environ["ASTRABRIDGE_PORT"] = str(router_status.get("listen_port") or router_port)
        os.environ["ASTRABRIDGE_TOKEN_FINGERPRINT"] = str(router_status.get("token_fingerprint") or "")
        self.metadata = MetadataService(self.router_config, self.router)
        self.agentic_updates = AgenticUpdateService(
            workspace_root_resolver=self.projects.require_workspace_root,
            runtime_root_resolver=lambda: self.projects.current_runtime_roots()["project_runtime_root"],
            provider_smoke_runtime_resolver=lambda: CapabilityRuntime(
                router_config=self.router_config,
                key_injector=self.llm_manager.inject_profile_key,
            ),
            router_config=self.router_config,
        )
        self.llm_manager = LlmApiManagerService(self.router_config, self.router)
        self.modals = ModalService(self.projects.require_shell_state_root)
        self.tasks = TaskService(self.projects)
        self.title_suggestions = TitleSuggestionService(self.projects, self.tasks, self.router)
        self.assets = AssetRegistryService(self.projects, self.tasks)
        self.yunwu_image = YunwuImageService()
        self.web_tools = AstraBridgeWebService(self.projects)
        self.browser_workbench = BrowserWorkbenchService(self.projects)
        self.dogfood = DogfoodRunService(self.projects)
        self.checkpoints = CheckpointService(self.projects)
        self.task_conversation = TaskConversationService(self.projects, self.tasks)
        self.runtime_config = RuntimeConfigService(
            codex_home_resolver=self.projects.current_runtime_codex_home,
            configured_models_resolver=self.router_config.models,
            secret_service=self.secrets,
            mcp_config=self.mcp_config,
        )
        self.project_context = ProjectContextService(
            self.projects,
            self.dogfood,
            self.assets,
            self.tasks,
            self.task_conversation,
            router_config_service=self.router_config,
            profile_service=self.profiles,
        )
        self.runtime = RuntimeService(
            self.projects,
            self.modals,
            runtime_config=self.runtime_config,
            secret_service=self.secrets,
            mcp_config=self.mcp_config,
            asset_registry=self.assets,
            project_context=self.project_context,
            task_service=self.tasks,
            task_conversation=self.task_conversation,
            dogfood_run=self.dogfood,
            profile_service=self.profiles,
            router_service=self.router,
            router_config_service=self.router_config,
            key_injector=self.llm_manager.inject_profile_key,
        )
        self.project_tools = ProjectToolsService(
            self.projects,
            self.runtime,
            checkpoints=self.checkpoints,
            tasks=self.tasks,
            profiles=self.profiles,
            router_config=self.router_config,
            task_conversation=self.task_conversation,
        )
        self.runtime.attach_project_tools(self.project_tools)
        self.automations = AutomationService(
            self.projects,
            runtime_service=self.runtime,
            profile_service=self.profiles,
            runtime_config=self.runtime_config,
            agentic_update_service=self.agentic_updates,
            event_recorder=self._record_automation_event,
        )
        self.supervisor = RuntimeSupervisorService(self.projects, self.runtime, self.modals, self.dogfood, automation_service=self.automations)
        self.wsl_dependencies = WslDependencyService()
        self.admin_token = __import__("secrets").token_urlsafe(24)
        if self.projects.current_project:
            self.automations.start()
        self._restore_startup_state()

    def _record_automation_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if hasattr(self.runtime, "record_external_event"):
            self.runtime.record_external_event(event_type, payload)
            return
        self.runtime.record_supervisor_event({"event": event_type, **payload})

    def _restore_startup_state(self) -> None:
        project = self.projects.current_project or {}
        if not project:
            return
        logical_active_thread = self.tasks.active_provider_thread(include_missing_fallback=True) or {}
        thread_id = str(project.get("current_thread_id") or logical_active_thread.get("thread_id") or "").strip()
        try:
            self.tasks.ensure_default_task(
                thread_id=thread_id or None,
                title=str(project.get("name") or "") or None,
            )
        except Exception as exc:  # noqa: BLE001
            self.runtime.record_supervisor_event({"event": "startup_task_restore_failed", "error": str(exc)[:300]})
        profile_id = self._startup_profile_id()
        if not profile_id:
            return
        try:
            profile = self.resolve_runtime_profile(profile_id)
        except Exception as exc:  # noqa: BLE001
            self.runtime.record_supervisor_event(
                {
                    "event": "startup_profile_restore_failed",
                    "profile_id": profile_id,
                    "error": str(exc)[:300],
                }
            )
            return
        self.runtime.restore_startup_runtime(profile, thread_id=thread_id or None)

    def _startup_profile_id(self) -> str | None:
        active_provider_thread = self.tasks.active_provider_thread(include_missing_fallback=True) or {}
        profile_id = str(active_provider_thread.get("profile_id") or "").strip()
        if profile_id:
            return profile_id
        project = self.projects.current_project or {}
        default_profile = str(project.get("default_profile_id") or "").strip()
        return default_profile or None

    def resolve_runtime_profile(self, profile_id: Any) -> dict[str, Any]:
        current = self.projects.current_project or {}
        active_provider_thread = self.tasks.active_provider_thread() or {}
        active_profile_id = str(active_provider_thread.get("profile_id") or "").strip()
        chosen = str(profile_id or "").strip() or active_profile_id or str(current.get("default_profile_id") or "").strip()
        profile = self.profiles.resolve_runtime_profile(chosen or None)
        self.llm_manager.inject_profile_key(profile)
        return self.profile_with_model_capabilities(profile)

    def get_profile_with_capabilities(self, profile_id: Any) -> dict[str, Any]:
        profile = self.profiles.get_profile(str(profile_id or "") or None)
        self.llm_manager.inject_profile_key(profile)
        return self.profile_with_model_capabilities(profile)

    def profile_with_model_capabilities(self, profile: dict[str, Any]) -> dict[str, Any]:
        from .model_catalog import merge_profile_with_effective_model

        return merge_profile_with_effective_model(profile, self.router_config.models())


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    context: AppContext

    def _run_after_response(self, *, name: str, callback: Callable[[], None]) -> None:
        def runner() -> None:
            try:
                callback()
            except Exception as exc:  # noqa: BLE001
                try:
                    self.context.runtime.record_supervisor_event(
                        {
                            "event": "background_post_response_failed",
                            "name": name,
                            "error": str(exc)[:300],
                        }
                    )
                except Exception:
                    return

        worker = threading.Thread(
            target=runner,
            name=f"astrabridge-{name}",
            daemon=True,
        )
        worker.start()

    def _send_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if is_allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin, Access-Control-Request-Headers, Access-Control-Request-Method, Access-Control-Request-Private-Network")
        allowed_headers = ["Content-Type", "X-Admin-Token", "X-Admin-Session-Token"]
        requested_headers = [
            item.strip()
            for item in str(self.headers.get("Access-Control-Request-Headers") or "").split(",")
            if item.strip() and all(char.isalnum() or char in {"-", "_"} for char in item.strip())
        ]
        for header in requested_headers:
            if header.lower() not in {item.lower() for item in allowed_headers}:
                allowed_headers.append(header)
        self.send_header("Access-Control-Allow-Headers", ", ".join(allowed_headers))
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        if str(self.headers.get("Access-Control-Request-Private-Network") or "").strip().lower() == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self._send_cors_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            self.close_connection = True
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # A browser timeout can close the socket after work has completed.
            # Do not attempt a second error response on that same connection.
            return

    def send_json(self, payload: Any, status: int = 200) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))

    def _send_file(self, path: Path, *, content_type: str, filename: str) -> None:
        body = path.read_bytes()
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{urllib.parse.quote(filename)}")
            self.send_header("Connection", "close")
            self.send_header("X-Content-Type-Options", "nosniff")
            self._send_cors_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            self.close_connection = True
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _send_event_stream(self, *, after: int = 0, limit: int | None = None, seconds: float = 60.0) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self._send_cors_headers()
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        cursor = max(0, int(after))
        deadline = time.monotonic() + max(1.0, seconds)
        last_heartbeat = 0.0
        try:
            self.wfile.write(sse_frame(event="astrabridge.hello", data={"cursor": cursor}, retry=2000))
            self.wfile.flush()
            while time.monotonic() < deadline:
                payload = self.context.runtime.list_events(after=cursor, limit=limit)
                events = list(payload.get("events") or [])
                cursor = int(payload.get("cursor") or cursor)
                if events:
                    for event in events:
                        self.wfile.write(sse_frame(event="astrabridge.event", data={"cursor": cursor, "event": event}))
                    self.wfile.flush()
                    last_heartbeat = time.monotonic()
                elif time.monotonic() - last_heartbeat >= 15:
                    self.wfile.write(sse_frame(comment=f"heartbeat cursor={cursor}"))
                    self.wfile.flush()
                    last_heartbeat = time.monotonic()
                time.sleep(1.0)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _record_ui_state_event(self, event: str, payload: dict[str, Any] | None = None) -> None:
        try:
            self.context.runtime.record_supervisor_event(
                {
                    "event": event,
                    "source": "sidecar_api",
                    **(payload or {}),
                }
            )
        except Exception:
            return

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8-sig") or "{}")

    def _sidecar_provenance(self) -> dict[str, Any]:
        listen_host = "127.0.0.1"
        listen_port: int | None = None
        address = getattr(getattr(self, "server", None), "server_address", None)
        if isinstance(address, tuple) and len(address) >= 2:
            listen_host = str(address[0] or listen_host)
            try:
                listen_port = int(address[1])
            except (TypeError, ValueError):
                listen_port = None
        return build_sidecar_provenance(
            listen_host=listen_host,
            listen_port=listen_port,
            seed_root=getattr(self.context, "seed_root", None),
        )

    def _payload_thread_id(self, payload: dict[str, Any]) -> str:
        raw = payload.get("thread_id")
        thread_id = str(raw or "").strip()
        if thread_id:
            return thread_id
        project = self.context.projects.current_project or {}
        current_thread_id = str(project.get("current_thread_id") or "").strip()
        if current_thread_id:
            return current_thread_id
        try:
            tasks = getattr(self.context, "tasks", None)
            if tasks is not None:
                return str(tasks.visible_provider_thread_id(include_missing_fallback=True) or "").strip()
        except Exception:
            return ""
        return ""

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, b"")

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            if path in {"/health", "/api/health"}:
                self.send_json(
                    {
                        "ok": True,
                        "service": "astrabridge-sidecar",
                        "sidecar": self._sidecar_provenance(),
                        "runtime": self.context.runtime.health_environment(),
                        "router": self.context.router.health_status(),
                    }
                )
                return
            if path == "/api/admin/session":
                self.send_json({"admin_session_token": self.context.admin_token})
                return
            if path in {"/api/projects/current", "/api/project/current"}:
                if not self.context.projects.current_project:
                    self.send_json({"project": None})
                    return
                # Launcher bootstrap only needs the currently open project. Avoid
                # pulling task reconciliation into this path because task-graph
                # runs can leave large task state hot, and a slow current-task
                # sync here blocks the whole app from re-entering the workspace.
                self.send_json({"project": self.context.projects.refresh_current_project()})
                return
            if path == "/api/projects/recent":
                self.send_json(self.context.projects.list_recent())
                return
            if path == "/api/projects/sidebar":
                self.send_json(self.context.projects.sidebar_snapshot())
                return
            if path == "/api/project/saves":
                self.send_json(self.context.checkpoints.list_saves())
                return
            if path == "/api/project/review/status":
                self.send_json(self.context.project_tools.review_status())
                return
            if path == "/api/project/review/diff":
                self.send_json(self.context.project_tools.review_diff(self._optional_query_string(query, "path")))
                return
            if path == "/api/project/files/tree":
                limit_values = query.get("limit", [])
                limit = int(limit_values[0]) if limit_values and str(limit_values[0]).strip() else 500
                self.send_json(self.context.project_tools.files_tree(query=self._optional_query_string(query, "query"), limit=limit))
                return
            if path == "/api/project/files/read":
                self.send_json(self.context.project_tools.read_file(str(query.get("path", [""])[0])))
                return
            if path == "/api/project/files/media":
                media = self.context.project_tools.file_media(str(query.get("path", [""])[0]))
                self._send_file(media["path"], content_type=str(media["mime_type"]), filename=str(media["name"]))
                return
            if path == "/api/browser/workbench/sessions":
                self.send_json(self.context.browser_workbench.list_sessions())
                return
            if path == "/api/browser/workbench/frame":
                session_id = self._optional_query_string(query, "id")
                if not session_id:
                    raise ValueError("id is required.")
                frame = self.context.browser_workbench.frame_path(session_id)
                self._send_file(frame, content_type="image/png", filename=frame.name)
                return
            if path == "/api/project/terminal/history":
                limit_values = query.get("limit", [])
                limit = int(limit_values[0]) if limit_values and str(limit_values[0]).strip() else 30
                self.send_json(self.context.project_tools.terminal_history(limit=limit))
                return
            if path in {"/api/project/tasks", "/api/tasks"}:
                self.send_json(self.context.tasks.snapshot())
                return
            if path in {"/api/project/tasks/current", "/api/tasks/current"}:
                task = self.context.tasks.current_task()
                self.send_json(
                    {
                        "task": self._task_view(task),
                        "project": self.context.projects.reconcile_task_projection(task),
                    }
                )
                return
            if path == "/api/task-graphs/templates":
                self.send_json(
                    self.context.tasks.list_graph_templates(
                        configured_models=self.context.router_config.models()
                        if getattr(self.context, "router_config", None)
                        else None,
                    )
                )
                return
            if path in {"/api/task-graphs/graph", "/api/task-graphs/current"}:
                graph = self.context.tasks.graph_definition(self._optional_query_string(query, "graph_id"))
                task_view = self.context.tasks.task_view(
                    self.context.tasks.current_task(),
                    compact_graph_runs=True,
                    compact_graph_details=True,
                )
                self.send_json({"graph": graph, "task": task_view})
                return
            if path == "/api/profiles":
                self.send_json(self.context.profiles.list_profiles())
                return
            if path == "/api/router/config":
                self.send_json(self.context.router_config.snapshot())
                return
            if path == "/api/runtime/capability-routes":
                self.send_json(self.context.router_config.capability_route_snapshot())
                return
            if path == "/api/runtime/capability-management":
                self.send_json(
                    self.context.router_config.capability_management_snapshot(
                        mcp_config=self.context.mcp_config.snapshot(),
                    )
                )
                return
            if path == "/api/runtime/capability-artifacts":
                self.send_json(
                    capability_artifact_snapshot(
                        self.context.projects.require_workspace_root(),
                        limit=int(query.get("limit", ["20"])[0] or 20),
                    )
                )
                return
            if path == "/api/llm-manager/session":
                self.send_json(self.context.llm_manager.session())
                return
            if path == "/api/llm-manager/keys":
                self.send_json(self.context.llm_manager.list_keys())
                return
            if path == "/api/llm-manager/catalog/effective":
                self.send_json(self.context.llm_manager.effective_catalog())
                return
            if path == "/api/llm-manager/health/results":
                self.send_json(self.context.llm_manager.health_results())
                return
            if path == "/api/router/metadata/sources":
                self.send_json(self.context.metadata.sources())
                return
            if path == "/api/router/models/effective-catalog":
                self.send_json(self.context.metadata.effective_catalog(query.get("model_id", [None])[0]))
                return
            if path == "/api/router/metadata/report":
                self.send_json(self.context.metadata.metadata_report())
                return
            if path == "/api/router/metadata/refresh/status":
                self.send_json(self.context.metadata.refresh_status(self._optional_query_string(query, "job_id")))
                return
            if path == "/api/router/metadata/refresh/result":
                self.send_json(self.context.metadata.refresh_result(self._optional_query_string(query, "job_id")))
                return
            if path == "/api/agentic-updates/runs":
                limit_values = query.get("limit", [])
                limit = int(limit_values[0]) if limit_values and str(limit_values[0]).strip() else 50
                self.send_json(self.context.agentic_updates.list_runs(limit=limit))
                return
            if path == "/api/agentic-updates/status":
                self.send_json(
                    self.context.agentic_updates.status(
                        self._optional_query_string(query, "job_id") or self._optional_query_string(query, "run_id")
                    )
                )
                return
            if path == "/api/agentic-updates/result":
                self.send_json(
                    self.context.agentic_updates.result(
                        self._optional_query_string(query, "job_id") or self._optional_query_string(query, "run_id")
                    )
                )
                return
            if path.startswith("/api/agentic-updates/"):
                parts = [part for part in path.split("/") if part]
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "agentic-updates" and parts[3] == "status":
                    self.send_json(self.context.agentic_updates.status(parts[2]))
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "agentic-updates" and parts[3] == "result":
                    self.send_json(self.context.agentic_updates.result(parts[2]))
                    return
            if path == "/api/router/image/prompt-guides":
                self.send_json(prompt_guides_payload())
                return
            if path == "/api/router/image/yunwu/protocol":
                self.send_json(self.context.yunwu_image.protocol())
                return
            if path == "/api/router/mcp/config":
                self.send_json(self.context.mcp_config.snapshot())
                return
            if path == "/api/runtime/environment":
                runtime = self.context.runtime.environment()
                runtime["router"] = self.context.router.status()
                runtime["sidecar"] = self._sidecar_provenance()
                self.send_json(runtime)
                return
            if path == "/api/runtime/kernel-probe":
                profile = self._resolve_runtime_profile(query.get("profile_id", [None])[0])
                self.send_json(self.context.runtime.kernel_probe_snapshot(profile))
                return
            if path == "/api/runtime/plugin-skill-registry":
                profile = self._resolve_runtime_profile(query.get("profile_id", [None])[0])
                self.send_json(self.context.runtime.plugin_skill_registry_snapshot(profile))
                return
            if path == "/api/runtime/dependencies/wsl":
                self.send_json(self.context.wsl_dependencies.status(self._optional_query_string(query, "distro")))
                return
            if path == "/api/router/status":
                self.send_json(self.context.router.status())
                return
            if path == "/api/automations":
                self.send_json(self.context.automations.list_automations())
                return
            if path == "/api/automations/runs":
                self.send_json(self.context.automations.list_runs(self._optional_query_string(query, "automation_id")))
                return
            if path == "/api/automations/run":
                run_id = self._optional_query_string(query, "run_id")
                if not run_id:
                    raise ValueError("run_id is required.")
                self.send_json(self.context.automations.get_run(run_id))
                return
            if path == "/api/automations/inbox":
                include_archived = str(query.get("include_archived", ["true"])[0]).strip().lower() != "false"
                self.send_json(
                    self.context.automations.list_inbox_items(
                        self._optional_query_string(query, "automation_id"),
                        include_archived=include_archived,
                    )
                )
                return
            if path == "/api/automations/scheduler/status":
                self.send_json({"scheduler": self.context.automations.scheduler_status()})
                return
            if path == "/api/router/events":
                limit = int(query.get("limit", ["50"])[0])
                self.send_json(self.context.router.events(limit=limit))
                return
            if path == "/api/official-codex/status":
                self.send_json(disabled_status())
                return
            if path == "/api/audit/isolation":
                sidecar_provenance = self._sidecar_provenance()
                self.send_json(
                    self.context.audit.snapshot(
                        current_project=self.context.projects.current_project,
                        runtime_environment=self.context.runtime.environment(),
                        router_status=self.context.router.status(),
                        official_codex_status=disabled_status(),
                        sidecar_provenance=sidecar_provenance,
                        sidecar_port=int(self.server.server_address[1]) if isinstance(self.server.server_address, tuple) else None,
                    )
                )
                return
            if path == "/api/runtime/events":
                after = int(query.get("after", ["0"])[0])
                limit_values = query.get("limit", [])
                limit = int(limit_values[0]) if limit_values and str(limit_values[0]).strip() else None
                self.send_json(self.context.runtime.list_events(after=after, limit=limit))
                return
            if path == "/api/events/stream":
                after = int(query.get("after", ["0"])[0])
                limit_values = query.get("limit", [])
                limit = int(limit_values[0]) if limit_values and str(limit_values[0]).strip() else None
                seconds_values = query.get("seconds", [])
                seconds = float(seconds_values[0]) if seconds_values and str(seconds_values[0]).strip() else 60.0
                self._send_event_stream(after=after, limit=limit, seconds=min(max(seconds, 1.0), 300.0))
                return
            if path == "/api/runtime/modals":
                self.send_json(self.context.modals.list_pending())
                return
            if path == "/api/runtime/supervisor/status":
                thread_id = self._optional_query_string(query, "thread_id")
                profile = self._resolve_runtime_profile(query.get("profile_id", [None])[0])
                self.send_json(self.context.supervisor.status(thread_id=thread_id, profile=profile))
                return
            if path == "/api/runtime/models":
                profile = self._profile(query.get("profile_id", [None])[0])
                self.send_json(self.context.runtime.list_models(profile))
                return
            if path == "/api/runtime/threads":
                archived = str(query.get("archived", ["false"])[0]).lower() == "true"
                profile = self._resolve_runtime_profile(query.get("profile_id", [None])[0])
                self.send_json(self.context.runtime.list_threads(profile, archived=archived))
                return
            if path == "/api/runtime/thread":
                thread_id = str(query.get("thread_id", [""])[0])
                profile = self._resolve_runtime_profile(query.get("profile_id", [None])[0])
                self.send_json(self.context.runtime.read_thread(profile, thread_id))
                return
            if path == "/api/runtime/goal":
                thread_id = str(query.get("thread_id", [""])[0])
                profile = self._resolve_runtime_profile(query.get("profile_id", [None])[0])
                try:
                    self.send_json(self.context.runtime.get_goal(profile, thread_id))
                except Exception as exc:
                    if self.context.runtime._is_thread_not_found_error(exc):  # type: ignore[attr-defined]
                        self.context.runtime._mark_provider_thread_missing(thread_id, reason="goal_thread_missing")  # type: ignore[attr-defined]
                        self.send_json({"goal": None, "status": "thread_missing", "thread_id": thread_id})
                        return
                    raise
                return
            if path == "/api/runtime/mcp/status":
                profile = self._resolve_runtime_profile(query.get("profile_id", [None])[0])
                self.send_json(
                    self.context.runtime.list_mcp_status(
                        profile,
                        thread_id=self._optional_query_string(query, "thread_id"),
                        detail=self._optional_query_string(query, "detail") or "toolsAndAuthOnly",
                    )
                )
                return
            if path == "/api/dogfood/run":
                self.send_json(self.context.dogfood.snapshot())
                return
            if path == "/api/dogfood/assets":
                self.send_json(self.context.assets.snapshot())
                return
            if path == "/api/project/context":
                self.send_json(
                    self.context.project_context.snapshot(
                        thread_id=self._optional_query_string(query, "thread_id"),
                        profile_id=self._optional_query_string(query, "profile_id"),
                        provider_id=self._optional_query_string(query, "provider_id"),
                        model_id=self._optional_query_string(query, "model_id"),
                    )
                )
                return
            if path == "/api/project/task-conversation":
                self.send_json(
                    normalize_task_conversation_payload(
                        self.context.task_conversation.conversation(task_id=self._optional_query_string(query, "task_id"))
                    )
                )
                return
            self.send_json({"ok": False, "error": "Not found"}, status=404)
        except Exception as exc:  # noqa: BLE001
            self.send_json(public_error(exc), status=400)

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urllib.parse.urlparse(self.path).path
            payload = self.read_json_body()
            if path.startswith("/api/") and path not in {"/api/projects/current", "/api/projects/recent"}:
                if self.command == "POST":
                    self._require_admin_token()
            if path == "/api/projects/create":
                project = self.context.projects.create_project(
                    str(payload.get("name") or ""),
                    str(payload.get("project_file") or ""),
                    workspace_root=payload.get("workspace_root"),
                    entry_mode=str(payload.get("entry_mode") or "existing"),
                )
                self.context.tasks.ensure_default_task(title=project.get("name") or "New task")
                project = self.context.projects.current_project
                self.context.runtime.restart_in_background()
                self.context.automations.start()
                self.send_json({"project": project})
                return
            if path in {"/api/projects/open", "/api/project/open"}:
                project = self.context.projects.open_project(str(payload.get("project_file") or ""))
                task = self.context.tasks.reconcile_after_project_reload(
                    preferred_thread_id=str(project.get("current_thread_id") or ""),
                )
                if not task:
                    self.context.tasks.ensure_default_task(
                        thread_id=project.get("current_thread_id"),
                        title=project.get("name") or "Default task",
                    )
                project = self.context.projects.current_project
                self.send_json({"project": project})
                self._run_after_response(
                    name="project-open-post-start",
                    callback=lambda: (
                        self.context.runtime.restart_in_background(),
                        self.context.automations.start(),
                    ),
                )
                return
            if path == "/api/projects/close":
                self.context.automations.stop()
                closed = self.context.projects.close_project()
                self.context.runtime.restart_in_background()
                self.send_json(closed)
                return
            if path == "/api/project/title/suggest":
                self.send_json(self.context.title_suggestions.suggest_project_title(force=bool(payload.get("force"))))
                return
            if path == "/api/project/attachments/stage":
                self.send_json(self.context.runtime.stage_uploaded_attachments(payload))
                return
            if path == "/api/browser/workbench/create":
                self.send_json(self.context.browser_workbench.create_session(payload))
                return
            if path == "/api/browser/workbench/navigate":
                self.send_json(self.context.browser_workbench.navigate(payload))
                return
            if path == "/api/browser/workbench/action":
                self.send_json(self.context.browser_workbench.action(payload))
                return
            if path == "/api/browser/workbench/layout":
                self.send_json(self.context.browser_workbench.layout(payload))
                return
            if path == "/api/browser/workbench/focus":
                self.send_json(self.context.browser_workbench.focus(str(payload.get("id") or "")))
                return
            if path == "/api/browser/workbench/close":
                self.send_json(self.context.browser_workbench.close(str(payload.get("id") or "")))
                return
            if path == "/api/browser/workbench/tile-two-up":
                self.send_json(self.context.browser_workbench.tile_two_up(list(payload.get("ids") or [])))
                return
            if path == "/api/automations/create":
                self.send_json(self.context.automations.create_automation(payload))
                return
            if path == "/api/automations/update":
                automation_id = str(payload.get("automation_id") or "").strip()
                if not automation_id:
                    raise ValueError("automation_id is required.")
                patch = {key: value for key, value in payload.items() if key != "automation_id"}
                self.send_json(self.context.automations.update_automation(automation_id, patch))
                return
            if path == "/api/automations/delete":
                automation_id = str(payload.get("automation_id") or "").strip()
                if not automation_id:
                    raise ValueError("automation_id is required.")
                self.send_json(self.context.automations.delete_automation(automation_id, reason=str(payload.get("reason") or "deleted")))
                return
            if path == "/api/automations/pause":
                automation_id = str(payload.get("automation_id") or "").strip()
                if not automation_id:
                    raise ValueError("automation_id is required.")
                self.send_json(self.context.automations.pause_automation(automation_id))
                return
            if path == "/api/automations/resume":
                automation_id = str(payload.get("automation_id") or "").strip()
                if not automation_id:
                    raise ValueError("automation_id is required.")
                self.send_json(self.context.automations.resume_automation(automation_id))
                return
            if path == "/api/automations/run-now":
                automation_id = str(payload.get("automation_id") or "").strip()
                if not automation_id:
                    raise ValueError("automation_id is required.")
                self.send_json(self.context.automations.run_now(automation_id, background=True))
                return
            if path == "/api/automations/runs/cancel":
                run_id = str(payload.get("run_id") or "").strip()
                if not run_id:
                    raise ValueError("run_id is required.")
                self.send_json(self.context.automations.cancel_run(run_id))
                return
            if path == "/api/automations/inbox/update":
                item_id = str(payload.get("item_id") or "").strip()
                if not item_id:
                    raise ValueError("item_id is required.")
                patch = {key: value for key, value in payload.items() if key != "item_id"}
                self.send_json(self.context.automations.update_inbox_item(item_id, patch))
                return
            if path == "/api/automations/inbox/promote":
                item_id = str(payload.get("item_id") or "").strip()
                if not item_id:
                    raise ValueError("item_id is required.")
                promotion_ref = str(payload.get("promotion_ref") or "").strip()
                if not promotion_ref:
                    raise ValueError("promotion_ref is required.")
                self.send_json(self.context.automations.promote_inbox_item(item_id, promotion_ref))
                return
            if path == "/api/projects/preferences":
                current = self.context.projects.current_project or {}
                merged = {
                    **(current.get("ui_preferences") or {}),
                    **dict(payload.get("ui_preferences") or {}),
                }
                self.send_json({"project": self.context.projects.update_project({"ui_preferences": merged})})
                return
            if path == "/api/projects/plugin-skill-presets":
                current = self.context.projects.current_project or {}
                next_state = mutate_project_plugin_skill_presets(
                    current.get("plugin_skill_presets"),
                    operation=str(payload.get("operation") or "").strip(),
                    preset_id=self._optional_string(payload, "preset_id"),
                    plugin_ref=payload.get("plugin_ref") if isinstance(payload.get("plugin_ref"), dict) else None,
                    skill_ref=payload.get("skill_ref") if isinstance(payload.get("skill_ref"), dict) else None,
                )
                self.send_json({"project": self.context.projects.update_project({"plugin_skill_presets": next_state})})
                return
            if path == "/api/project/saves/create":
                response = self.context.checkpoints.create(payload)
                self.context.tasks.record_checkpoint(response.get("save") or response.get("manifest") or response)
                manifest = (response.get("save") or response.get("manifest") or {}) if isinstance(response, dict) else {}
                if not isinstance(manifest, dict):
                    manifest = {}
                self._record_ui_state_event(
                    "checkpoint_created",
                    {
                        "save_id": manifest.get("save_id"),
                    },
                )
                self.send_json(response)
                return
            if path == "/api/project/saves/load":
                response = self.context.checkpoints.load(payload)
                self.context.tasks.reconcile_after_project_reload(
                    preferred_thread_id=str((self.context.projects.current_project or {}).get("current_thread_id") or ""),
                )
                self._record_ui_state_event("checkpoint_loaded", {"save_id": str(payload.get("save_id") or "")})
                self.send_json(response)
                return
            if path == "/api/project/edit/preview":
                self.send_json(self.context.project_tools.edit_preview(payload))
                return
            if path == "/api/project/edit/apply":
                response = self.context.project_tools.edit_apply(payload)
                event_payload = (response.get("event") or {}).get("payload") or {}
                self._record_ui_state_event(
                    "edit_operation_applied",
                    {
                        "path": event_payload.get("path"),
                        "selected_operation": event_payload.get("selected_operation"),
                        "checkpoint_save_id": event_payload.get("checkpoint_save_id"),
                    },
                )
                self.send_json(response)
                return
            if path == "/api/project/tasks/create":
                task = self.context.tasks.create_task(str(payload.get("title") or "") or None)
                self.send_json({"task": task, "project": self.context.projects.current_project})
                return
            if path == "/api/project/tasks/switch":
                task = self.context.tasks.switch_task(str(payload.get("task_id") or ""))
                self.send_json({"task": task, "project": self.context.projects.current_project})
                return
            if path == "/api/project/tasks/title":
                task = self.context.tasks.update_current_task_title(str(payload.get("title") or ""))
                self.send_json({"task": task, "project": self.context.projects.current_project})
                return
            if path == "/api/project/tasks/title/suggest":
                self.send_json(self.context.title_suggestions.suggest_current_task_title(force=bool(payload.get("force"))))
                return
            if path == "/api/profiles":
                self.send_json({"profile": self.context.profiles.upsert_profile(payload)})
                return
            if path == "/api/profiles/delete":
                self.send_json(self.context.profiles.delete_profile(str(payload.get("profile_id") or "")))
                return
            if path == "/api/profiles/load-secret":
                profile = self._profile(payload.get("profile_id"))
                status = self.context.runtime.load_secret(
                    profile,
                    session_key=str(payload.get("session_key") or "") or None,
                    key_file_path=str(payload.get("key_file_path") or "") or None,
                    persist_to_keychain=bool(payload.get("persist_to_keychain")),
                )
                if bool(payload.get("persist_to_keychain")) and status.get("secret_ref"):
                    self.context.profiles.upsert_profile(
                        {
                            **profile,
                            "auth_mode": "os_keychain",
                            "secret_ref": status.get("secret_ref"),
                        }
                    )
                self.send_json({"runtime_config": status})
                return
            if path == "/api/router/providers/save":
                self.send_json({"provider": self.context.router_config.upsert_provider(payload)})
                return
            if path == "/api/llm-manager/login":
                self.send_json(self.context.llm_manager.login(payload))
                return
            if path == "/api/llm-manager/logout":
                self.send_json(self.context.llm_manager.logout())
                return
            if path == "/api/llm-manager/users/create":
                self.send_json(self.context.llm_manager.create_user(payload))
                return
            if path == "/api/llm-manager/users/switch":
                self.send_json(self.context.llm_manager.switch_user(payload))
                return
            if path == "/api/llm-manager/users/change-password":
                self.send_json(self.context.llm_manager.change_password(payload))
                return
            if path == "/api/llm-manager/users/profile":
                self.send_json(self.context.llm_manager.save_user_profile(payload))
                return
            if path == "/api/llm-manager/keys/save":
                self.send_json(self.context.llm_manager.save_key(payload))
                return
            if path == "/api/llm-manager/keys/delete":
                self.send_json(self.context.llm_manager.delete_key(payload))
                return
            if path == "/api/llm-manager/keys/test":
                self.send_json(self.context.llm_manager.test_key(payload))
                return
            if path == "/api/llm-manager/health/run":
                self.send_json(self.context.llm_manager.run_health(payload))
                return
            if path == "/api/llm-manager/mode/anonymous":
                self.send_json(self.context.llm_manager.login({"mode": "anonymous"}))
                return
            if path == "/api/router/providers/delete":
                self.send_json(self.context.router_config.delete_provider(str(payload.get("provider_id") or "")))
                return
            if path == "/api/router/models/save":
                self.send_json({"model": self.context.router_config.upsert_model(payload)})
                return
            if path == "/api/router/models/delete":
                self.send_json(self.context.router_config.delete_model(str(payload.get("model_id") or "")))
                return
            if path == "/api/router/reasoning/save":
                self.send_json({"reasoning": self.context.router_config.save_reasoning(payload)})
                return
            if path == "/api/router/metadata/sources/save":
                self.send_json(self.context.metadata.save_sources(payload))
                return
            if path == "/api/router/metadata/refresh":
                self.send_json(self.context.metadata.refresh(apply=bool(payload.get("apply"))))
                return
            if path == "/api/router/metadata/refresh/start":
                self.send_json(self.context.metadata.start_refresh(apply=bool(payload.get("apply"))))
                return
            if path == "/api/agentic-updates/start":
                self.send_json(self.context.agentic_updates.start(payload))
                return
            if path == "/api/agentic-updates/automation-template":
                self.send_json(self.context.automations.create_agentic_update_check_template(payload))
                return
            if path == "/api/agentic-updates/apply":
                self.send_json(self.context.agentic_updates.apply(payload))
                return
            if path == "/api/agentic-updates/rollback":
                self.send_json(self.context.agentic_updates.rollback(payload))
                return
            if path == "/api/agentic-updates/code-change-plan":
                self.send_json(self.context.agentic_updates.code_change_plan(payload))
                return
            if path == "/api/agentic-updates/validate":
                self.send_json(self.context.agentic_updates.validate(payload))
                return
            if path == "/api/agentic-updates/kernel-verify":
                self.send_json(self.context.agentic_updates.verify_kernel_candidate(payload))
                return
            if path == "/api/task-graphs/instantiate":
                self.send_json(
                    self.context.tasks.instantiate_graph_template(
                        str(payload.get("template_id") or ""),
                        title=str(payload.get("title") or "").strip() or None,
                        configured_models=self.context.router_config.models() if getattr(self.context, "router_config", None) else None,
                    )
                )
                return
            if path == "/api/task-graphs/import":
                self.send_json(
                    self.context.tasks.import_graph_from_orchestration_file(
                        payload,
                        profiles_snapshot=self.context.profiles.list_profiles() if getattr(self.context, "profiles", None) else None,
                        configured_models=self.context.router_config.models() if getattr(self.context, "router_config", None) else None,
                    )
                )
                return
            if path == "/api/task-graphs/export":
                self.send_json(self.context.tasks.export_graph_for_orchestration_file(payload))
                return
            if path == "/api/task-graphs/snapshot":
                self.send_json(self.context.tasks.create_graph_snapshot(payload))
                return
            if path == "/api/task-graphs/snapshot/diff":
                self.send_json(self.context.tasks.diff_graph_snapshot(payload))
                return
            if path == "/api/task-graphs/rollback":
                self.send_json(self.context.tasks.rollback_graph_to_snapshot(payload))
                return
            if path == "/api/task-graphs/save":
                self.send_json(self.context.tasks.save_graph_definition(payload))
                return
            if path == "/api/task-graphs/node/update":
                self.send_json(self.context.tasks.update_graph_node(payload))
                return
            if path == "/api/task-graphs/edge/update":
                self.send_json(self.context.tasks.update_graph_edge(payload))
                return
            if path == "/api/task-graphs/dry-run":
                self.send_json(
                    self.context.tasks.dry_run_graph(
                        payload,
                        profiles_snapshot=self.context.profiles.list_profiles() if getattr(self.context, "profiles", None) else None,
                        configured_models=self.context.router_config.models() if getattr(self.context, "router_config", None) else None,
                    )
                )
                return
            if path == "/api/task-graphs/run":
                try:
                    self.send_json(self.context.runtime.execute_task_graph_run(payload))
                except Exception as exc:  # noqa: BLE001
                    structured_error = public_error(exc)
                    graph_id = str(payload.get("graph_id") or "").strip()
                    if graph_id and not structured_error.get("graph"):
                        try:
                            graph_payload = self.context.tasks.graph_definition(graph_id)
                        except Exception:
                            graph_payload = None
                        if isinstance(graph_payload, dict) and graph_payload:
                            structured_error["graph"] = graph_payload
                    if not structured_error.get("task"):
                        try:
                            current_task = self.context.tasks.current_task()
                            structured_task = self.context.tasks.task_view(
                                current_task,
                                compact_graph_runs=True,
                            )
                        except Exception:
                            structured_task = None
                        if isinstance(structured_task, dict) and structured_task:
                            structured_error["task"] = structured_task
                    live_run = dict(structured_error.get("live_run") or {})
                    run_ref = dict(live_run.get("run_ref") or {})
                    terminal_status = str(
                        run_ref.get("status") or live_run.get("run_status") or ""
                    ).strip().lower()
                    if terminal_status in {"failed", "cancelled"} or graph_id:
                        structured_error["ok"] = False
                        self.send_json(structured_error, status=200)
                        return
                    raise
                return
            if path == "/api/task-graphs/worker/start":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(
                    self.context.runtime.start_graph_worker(
                        profile,
                        graph_id=str(payload.get("graph_id") or ""),
                        run_id=str(payload.get("run_id") or ""),
                        node_id=str(payload.get("node_id") or ""),
                        parent_thread_id=str(payload.get("parent_thread_id") or ""),
                        model=self._optional_string(payload, "model"),
                        effort=self._optional_string(payload, "effort"),
                        permission_mode=self._optional_string(payload, "permission_mode") or "auto",
                        artifact_refs=payload.get("artifact_refs") if isinstance(payload.get("artifact_refs"), list) else None,
                    )
                )
                return
            if path == "/api/task-graphs/worker/output":
                self.send_json(self.context.tasks.record_graph_worker_output(payload))
                return
            if path == "/api/task-graphs/fixture-run":
                self.send_json(self.context.tasks.execute_fixture_graph(payload))
                return
            if path == "/api/task-graphs/run/cancel":
                self.send_json(self.context.tasks.cancel_graph_run(payload))
                return
            if path == "/api/task-graphs/run/recover":
                self.send_json(self.context.tasks.recover_graph_run(payload))
                return
            if path == "/api/task-graphs/approval/resolve":
                self.send_json(self.context.tasks.resolve_graph_run_approval(payload))
                return
            if path == "/api/router/metadata/import-seed":
                self.send_json(self.context.metadata.import_seed(apply=bool(payload.get("apply", True))))
                return
            if path == "/api/router/models/test-matrix":
                self.send_json(self.context.metadata.test_matrix(payload))
                return
            if path == "/api/router/mcp/config/save":
                self.send_json({"server": self.context.mcp_config.upsert_server(payload), "config": self.context.mcp_config.snapshot()})
                return
            if path == "/api/router/mcp/config/delete":
                self.send_json(self.context.mcp_config.delete_server(str(payload.get("name") or "")))
                return
            if path == "/api/router/mcp/preset/context7":
                self.send_json(self.context.mcp_config.apply_context7_preset())
                return
            if path == "/api/router/mcp/preset/yunwu-image":
                self.send_json(self.context.mcp_config.apply_yunwu_image_preset())
                return
            if path == "/api/router/mcp/preset/astrabridge-web":
                self.send_json(self.context.mcp_config.apply_astrabridge_web_preset())
                return
            if path == "/api/router/mcp/preset/astrabridge-capabilities":
                self.send_json(self.context.mcp_config.apply_astrabridge_capabilities_preset())
                return
            if path == "/api/router/image/yunwu/test":
                self.send_json(self.context.yunwu_image.test_connectivity(api_key=self._ephemeral_key(payload)))
                return
            if path == "/api/router/image/yunwu/generate":
                self.send_json(
                    self.context.yunwu_image.generate(
                        prompt=str(payload.get("prompt") or ""),
                        model=str(payload.get("model") or "gpt-image-2"),
                        size=str(payload.get("size") or "1024x1024"),
                        n=int(payload.get("n") or 1),
                        image_urls=[str(item) for item in (payload.get("image_urls") or [])],
                        response_format=str(payload.get("response_format") or "url"),
                        quality=str(payload.get("quality") or "auto"),
                        image_format=str(payload.get("format") or payload.get("image_format") or "png"),
                        background=self._optional_string(payload, "background"),
                        prompt_category=str(payload.get("prompt_category") or ""),
                        api_key=self._ephemeral_key(payload),
                        timeout_sec=int(payload.get("timeout_sec") or 300),
                        workspace_root=self.context.projects.require_workspace_root(),
                        purpose=self._optional_string(payload, "purpose"),
                    )
                )
                return
            if path == "/api/router/image/yunwu/edit":
                self.send_json(
                    self.context.yunwu_image.edit(
                        prompt=str(payload.get("prompt") or ""),
                        image_paths=[str(item) for item in (payload.get("image_paths") or [])],
                        mask_path=self._optional_string(payload, "mask_path"),
                        model=str(payload.get("model") or "gpt-image-2"),
                        size=str(payload.get("size") or "1024x1024"),
                        n=int(payload.get("n") or 1),
                        quality=str(payload.get("quality") or "auto"),
                        background=str(payload.get("background") or "auto"),
                        moderation=str(payload.get("moderation") or "auto"),
                        prompt_category=str(payload.get("prompt_category") or ""),
                        api_key=self._ephemeral_key(payload),
                        timeout_sec=int(payload.get("timeout_sec") or 300),
                        workspace_root=self.context.projects.require_workspace_root(),
                        purpose=self._optional_string(payload, "purpose"),
                    )
                )
                return
            if path == "/api/router/image/yunwu/transparent-asset":
                self.send_json(
                    self.context.yunwu_image.transparent_asset(
                        prompt=str(payload.get("prompt") or ""),
                        model=str(payload.get("model") or "gpt-image-2"),
                        size=str(payload.get("size") or "1024x1024"),
                        n=int(payload.get("n") or 1),
                        quality=str(payload.get("quality") or "high"),
                        moderation=str(payload.get("moderation") or "auto"),
                        prompt_category=str(payload.get("prompt_category") or "game_asset_japanese_anime"),
                        api_key=self._ephemeral_key(payload),
                        timeout_sec=int(payload.get("timeout_sec") or 300),
                        workspace_root=self.context.projects.require_workspace_root(),
                        purpose=self._optional_string(payload, "purpose"),
                    )
                )
                return
            if path == "/api/router/image/prompt-rewrite/instruction":
                self.send_json(
                    build_rewrite_instruction(
                        category_id=str(payload.get("category_id") or "game_asset_japanese_anime"),
                        user_prompt=str(payload.get("prompt") or ""),
                        target_style=str(payload.get("target_style") or ""),
                        size=str(payload.get("size") or "2048x2048"),
                        quality=str(payload.get("quality") or "high"),
                        image_format=str(payload.get("format") or payload.get("image_format") or "png"),
                        transparent_background=bool(payload.get("transparent_background")),
                        reference_image_mode=bool(payload.get("reference_image_mode")),
                    )
                )
                return
            if path == "/api/dogfood/run/save":
                response = self.context.dogfood.save(payload)
                self._record_ui_state_event("dogfood_run_saved")
                self.send_json(response)
                return
            if path == "/api/dogfood/captures/add":
                response = self.context.dogfood.add_capture(payload)
                self._record_ui_state_event("dogfood_capture_added", {"label": str(payload.get("label") or "")[:120]})
                self.send_json(response)
                return
            if path == "/api/dogfood/browser-smoke":
                response = self.context.dogfood.browser_smoke(payload)
                smoke = dict(response.get("browser_smoke") or {}) if isinstance(response, dict) else {}
                self._record_ui_state_event(
                    "dogfood_browser_smoke",
                    {
                        "label": str(smoke.get("label") or payload.get("label") or "")[:120],
                        "status": str(smoke.get("status") or ""),
                    },
                )
                self.send_json(response)
                return
            if path == "/api/dogfood/milestone":
                result = self.context.dogfood.add_milestone(payload)
                milestone = dict(result.get("milestone") or {})
                run_path_raw = str(result.get("path") or "").strip()
                if run_path_raw and bool(payload.get("sync_run_summary")):
                    run_path = Path(run_path_raw)
                    run_payload = self.context.dogfood._normalize(read_json(run_path, {}))
                    self.context.dogfood._apply_milestone_summary(run_payload, milestone)
                    run_payload["updated_at"] = str(milestone.get("created_at") or now_iso())
                    write_json(run_path, run_payload)
                    result["run_summary"] = self.context.dogfood._run_summary(run_payload)
                    if bool(payload.get("include_run")):
                        result["run"] = run_payload
                result["route_summary_synced"] = bool(payload.get("sync_run_summary"))
                self._record_ui_state_event(
                    "dogfood_milestone_added",
                    {
                        "label": str(milestone.get("label") or payload.get("label") or "")[:120],
                        "status": str(milestone.get("status") or payload.get("status") or "")[:80],
                    },
                )
                self.send_json(result)
                return
            if path == "/api/dogfood/assets/rebuild":
                response = self.context.assets.rebuild()
                rebuilt_registry = dict(response.get("registry") or {}) if isinstance(response, dict) else {}
                self._record_ui_state_event("dogfood_assets_rebuilt", {"count": len(rebuilt_registry.get("assets") or [])})
                if bool(payload.get("include_registry")):
                    self.send_json(response)
                else:
                    self.send_json(self.context.assets.concise_response(response))
                return
            if path == "/api/dogfood/assets/mark":
                response = self.context.assets.mark(payload)
                self._record_ui_state_event("dogfood_asset_marked", {"asset_id": str(payload.get("asset_id") or "")[:120]})
                self.send_json(response)
                return
            if path == "/api/dogfood/assets/promote":
                response = self.context.assets.promote(payload)
                self._record_ui_state_event(
                    "dogfood_asset_promoted",
                    {
                        "asset_id": str(payload.get("asset_id") or "")[:120],
                        "game_ref": str(response.get("game_ref") or "")[:240] if isinstance(response, dict) else "",
                    },
                )
                self.send_json(response)
                return
            if path == "/api/project/context/rebuild":
                response = self.context.project_context.snapshot(
                    thread_id=self._optional_string(payload, "thread_id"),
                    profile_id=self._optional_string(payload, "profile_id"),
                    provider_id=self._optional_string(payload, "provider_id"),
                    model_id=self._optional_string(payload, "model_id"),
                )
                self._record_ui_state_event("project_context_rebuilt", {"thread_id": self._optional_string(payload, "thread_id")})
                self.send_json(response)
                return
            if path == "/api/project/demo/release-workflow/prepare":
                response = self.context.project_tools.prepare_release_workflow_demo(payload)
                self._record_ui_state_event(
                    "release_workflow_demo_prepared",
                    {
                        "task_id": str(((response or {}).get("task") or {}).get("task_id") or "")[:120],
                        "workspace_root": str((response or {}).get("workspace_root") or "")[:240],
                    },
                )
                self.send_json(response)
                return
            if path == "/api/project/demo/native-kernel/prepare":
                response = self.context.project_tools.prepare_native_kernel_workflow_demo(payload)
                self._record_ui_state_event(
                    "native_kernel_demo_prepared",
                    {
                        "task_id": str(((response or {}).get("task") or {}).get("task_id") or "")[:120],
                        "workspace_root": str((response or {}).get("workspace_root") or "")[:240],
                    },
                )
                self.send_json(response)
                return
            if path == "/api/router/payload-preview":
                self.send_json(self.context.router.preview_payload(payload))
                return
            if path == "/api/tools/web/search-batch":
                self.send_json(self.context.web_tools.search_batch(payload))
                return
            if path == "/api/tools/web/research-brief":
                self.send_json(self.context.web_tools.research_brief(payload))
                return
            if path == "/api/tools/web/fetch":
                self.send_json(self.context.web_tools.fetch(payload))
                return
            if path == "/api/router/test-provider":
                self.send_json(
                    self.context.router.test_provider(
                        str(payload.get("provider_id") or ""),
                        self._optional_string(payload, "model_id"),
                        stream=bool(payload.get("stream")),
                    )
                )
                return
            if path == "/api/router/test-provider-vision":
                self.send_json(
                    self.context.router.test_provider_vision(
                        str(payload.get("provider_id") or ""),
                        self._optional_string(payload, "model_id"),
                        stream=bool(payload.get("stream")),
                    )
                )
                return
            if path == "/api/runtime/verify-app-server-image-route":
                profile = self._resolve_runtime_profile_for_turn(
                    {
                        "profile_id": self._optional_string(payload, "profile_id"),
                        "model": self._optional_string(payload, "model_id"),
                    }
                )
                self.send_json(
                    self.context.runtime.verify_app_server_image_transport(
                        profile,
                        model=self._optional_string(payload, "model_id"),
                    )
                )
                return
            if path == "/api/router/export-config":
                self.send_json(self.context.router_config.export_sanitized())
                return
            if path == "/api/router/import-config":
                self.send_json(self.context.router_config.import_sanitized(payload))
                return
            if path == "/api/runtime/capability-routes/save":
                self.send_json({"route": self.context.router_config.save_capability_route(payload)})
                return
            if path == "/api/runtime/capability-invoke":
                capability_id = str(payload.get("capability_id") or "").strip()
                if not capability_id:
                    raise ValueError("capability_id is required.")
                capability_payload = payload.get("payload")
                if not isinstance(capability_payload, dict):
                    capability_payload = {}
                capability_payload = self._payload_with_default_workspace_root(capability_payload)
                self.send_json(
                    {
                        "result": CapabilityRuntime(
                            router_config=self.context.router_config,
                            key_injector=self.context.llm_manager.inject_profile_key,
                        ).invoke(capability_id, capability_payload)
                    }
                )
                return
            if path == "/api/runtime/capability-smoke":
                payload = self._payload_with_default_workspace_root(payload)
                route_record = self.context.router_config.capability_routes().get(str(payload.get("capability_id") or "").strip())
                self.send_json(
                    {
                        "smoke": capability_smoke_snapshot(
                            payload,
                            configured_models=self.context.router_config.models(),
                            route_record=route_record,
                            runtime=CapabilityRuntime(
                                router_config=self.context.router_config,
                                key_injector=self.context.llm_manager.inject_profile_key,
                            ),
                        )
                    }
                )
                return
            if path == "/api/runtime/provider-compatibility-smoke":
                self.send_json(
                    {
                        "smoke": run_provider_compatibility_smoke(
                            payload,
                            configured_models=self.context.router_config.models(),
                            capability_route_records=self.context.router_config.capability_routes(),
                            runtime=CapabilityRuntime(
                                router_config=self.context.router_config,
                                key_injector=self.context.llm_manager.inject_profile_key,
                            ),
                            workspace_root=self.context.projects.require_workspace_root(),
                        )
                    }
                )
                return
            if path == "/api/runtime/plugin-install-plan":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                plugin_id = str(payload.get("plugin_id") or "").strip()
                if not plugin_id:
                    raise ValueError("plugin_id is required.")
                self.send_json(
                    self.context.runtime.plugin_install_plan(
                        profile,
                        plugin_id=plugin_id,
                        source_catalog_id=self._optional_string(payload, "source_catalog_id"),
                    )
                )
                return
            if path == "/api/runtime/plugin-install-apply":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                plugin_id = str(payload.get("plugin_id") or "").strip()
                if not plugin_id:
                    raise ValueError("plugin_id is required.")
                self.send_json(
                    self.context.runtime.plugin_install_apply(
                        profile,
                        plugin_id=plugin_id,
                        source_catalog_id=self._optional_string(payload, "source_catalog_id"),
                    )
                )
                return
            if path == "/api/runtime/computer-use/browser-scenario":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                max_wait_sec = float(payload.get("max_wait_sec") or 8.0)
                max_wait_sec = max(0.0, min(max_wait_sec, 30.0))
                self.send_json(
                    self.context.runtime.computer_use_browser_scenario(
                        profile,
                        run_model=bool(payload.get("run_model", True)),
                        include_yunwu=bool(payload.get("include_yunwu", True)),
                        allow_fallback_sites=bool(payload.get("allow_fallback_sites", True)),
                        max_wait_sec=max_wait_sec,
                    )
                )
                return
            if path == "/api/runtime/skill-enablement":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                record_id = str(payload.get("record_id") or "").strip()
                if not record_id:
                    raise ValueError("record_id is required.")
                self.send_json(
                    self.context.runtime.skill_enablement_update(
                        profile,
                        record_id=record_id,
                        scope=str(payload.get("scope") or "").strip(),
                        enablement_status=str(payload.get("enablement_status") or "").strip(),
                    )
                )
                return
            if path == "/api/runtime/skill-scenario/plugin-creator-fixture":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(
                    self.context.runtime.skill_plugin_creator_fixture_scenario(
                        profile,
                        skill_name=str(payload.get("skill_name") or "plugin-creator").strip() or "plugin-creator",
                    )
                )
                return
            if path == "/api/router/token/rotate":
                self.send_json(self.context.router.rotate_token())
                return
            if path == "/api/router/keys/delete":
                provider = self.context.router_config.upsert_provider(
                    {
                        **self.context.router._provider_by_id(str(payload.get("provider_id") or "")),
                        "auth_key_ref": None,
                    }
                )
                deleted = self.context.secrets.delete(str(payload.get("secret_ref") or provider.get("auth_key_ref") or ""))
                self.send_json({"deleted": deleted, "provider": provider})
                return
            if path == "/api/runtime/restart":
                self.send_json({"runtime": self.context.runtime.restart()})
                return
            if path == "/api/runtime/mcp/reload":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(self.context.runtime.reload_mcp_servers(profile))
                return
            if path == "/api/runtime/mcp/tool-call":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(
                    self.context.runtime.call_mcp_tool(
                        profile,
                        thread_id=self._payload_thread_id(payload),
                        server=str(payload.get("server") or ""),
                        tool=str(payload.get("tool") or ""),
                        arguments=payload.get("arguments") or {},
                        preserve_active_thread=bool(payload.get("preserve_active_thread", True)),
                    )
                )
                return
            if path == "/api/official-codex/apply":
                self.send_json(disabled_status(), status=403)
                return
            if path == "/api/official-codex/restore":
                self.send_json(disabled_status(), status=403)
                return
            if path == "/api/runtime/modals/resolve":
                self.send_json({"modal": self.context.modals.resolve(str(payload.get("modal_id") or ""), payload)})
                return
            if path == "/api/runtime/modals/fake":
                self.send_json({"modal": self.context.modals.create_fake(str(payload.get("kind") or "user_input"), payload.get("params") or {})})
                return
            if path == "/api/runtime/supervisor/decision":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(self.context.supervisor.decision(payload, profile))
                return
            if path == "/api/runtime/threads/create":
                profile = self._profile(payload.get("profile_id"))
                response = self.context.runtime.create_thread(
                    profile,
                    model=self._optional_string(payload, "model"),
                    effort=self._optional_string(payload, "effort"),
                    permission_mode=str(payload.get("permission_mode") or "auto"),
                    task_id=self._optional_string(payload, "task_id"),
                    name=self._optional_string(payload, "name"),
                    operation_id=self._optional_string(payload, "operation_id"),
                )
                self.send_json({**response, "project": self.context.projects.current_project, "task": self._task_view(self.context.tasks.current_task())})
                return
            if path == "/api/runtime/threads/create/start":
                # The start endpoint must return an operation receipt promptly.
                # Key injection and catalog enrichment belong to the background
                # runtime preparation path, not this HTTP request.
                profile = self.context.profiles.get_profile(
                    str(payload.get("profile_id") or "") or None
                )
                response = self.context.runtime.begin_thread_create(
                    profile,
                    model=self._optional_string(payload, "model"),
                    effort=self._optional_string(payload, "effort"),
                    permission_mode=str(payload.get("permission_mode") or "auto"),
                    name=self._optional_string(payload, "name"),
                    operation_id=self._optional_string(payload, "operation_id"),
                )
                # This endpoint is deliberately an operation receipt. Reading the
                # active task here can contend with the worker that is creating
                # it, turning an asynchronous start back into a blocking HTTP
                # request. The client reconciles the completed operation and
                # refreshes project/task state through its existing queries.
                self.send_json(response)
                return
            if path == "/api/runtime/threads/create/recover":
                # Recovery is primarily an operation-state read. Keep its
                # request path free of Vault work so a caller can always learn
                # whether the background creation reached a terminal state.
                profile = self.context.profiles.get_profile(
                    str(payload.get("profile_id") or "") or None
                )
                response = self.context.runtime.recover_thread_create(
                    profile,
                    operation_id=str(payload.get("operation_id") or ""),
                )
                self.send_json(response)
                return
            if path == "/api/runtime/threads/fork":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                response = self.context.runtime.fork_thread(
                    profile,
                    thread_id=str(payload.get("thread_id") or ""),
                    model=self._optional_string(payload, "model"),
                    effort=self._optional_string(payload, "effort"),
                    permission_mode=str(payload.get("permission_mode") or "auto"),
                    name=self._optional_string(payload, "name"),
                )
                self.send_json({**response, "project": self.context.projects.current_project, "task": self._task_view(self.context.tasks.current_task())})
                return
            if path == "/api/runtime/threads/rename":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(
                    {
                        "thread": self.context.runtime.rename_thread(
                            profile,
                            str(payload.get("thread_id") or ""),
                            str(payload.get("name") or ""),
                        )
                    }
                )
                return
            if path == "/api/runtime/threads/archive":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(
                    self.context.runtime.archive_thread(
                        profile,
                        str(payload.get("thread_id") or ""),
                    )
                )
                return
            if path == "/api/runtime/threads/switch":
                thread_id = self._optional_string(payload, "thread_id")
                project = self.context.projects.switch_thread(thread_id)
                task = self.context.tasks.restore_active_provider_thread(thread_id) if thread_id else self.context.tasks.current_task()
                self.send_json({"project": self.context.projects.current_project or project, "task": self._task_view(task)})
                return
            if path == "/api/runtime/thread-settings":
                settings = self.context.runtime.update_thread_defaults(
                    thread_id=str(payload.get("thread_id") or ""),
                    profile_id=self._optional_string(payload, "profile_id"),
                    model=self._optional_string(payload, "model"),
                    effort=self._optional_string(payload, "effort"),
                    permission_mode=self._optional_string(payload, "permission_mode"),
                    collaboration_mode=self._optional_string(payload, "collaboration_mode"),
                )
                self.send_json({"settings": settings})
                return
            if path == "/api/runtime/goal/set":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                token_budget = payload.get("token_budget")
                self.send_json(
                    self.context.runtime.set_goal(
                        profile,
                        thread_id=self._payload_thread_id(payload),
                        objective=str(payload.get("objective") or ""),
                        token_budget=int(token_budget) if token_budget not in {None, ""} else None,
                        status=self._optional_string(payload, "status"),
                    )
                )
                return
            if path == "/api/runtime/goal/clear":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(self.context.runtime.clear_goal(profile, self._payload_thread_id(payload)))
                return
            if path == "/api/runtime/thread/compact":
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(self.context.runtime.compact_thread(profile, self._payload_thread_id(payload)))
                return
            if path in {"/api/runtime/turns/start", "/api/turn/start"}:
                profile = self._resolve_runtime_profile_for_turn(payload)
                attachments = payload.get("attachments")
                turn_text = turn_text_from_payload(payload)
                if not turn_text.strip() and not list(attachments or []):
                    raise ValueError("Turn text or attachments are required.")
                response = self.context.runtime.start_turn(
                    profile,
                    thread_id=self._payload_thread_id(payload),
                    text=turn_text,
                    attachments=list(attachments or []),
                    model=self._optional_string(payload, "model"),
                    effort=self._optional_string(payload, "effort"),
                    permission_mode=str(payload.get("permission_mode") or "auto"),
                    collaboration_mode=self._optional_string(payload, "collaboration_mode"),
                    context_mode=self._optional_string(payload, "context_mode"),
                    execution_policy=self._optional_string(payload, "execution_policy"),
                )
                if bool(payload.get("include_full_state")):
                    self.send_json({**response, "project": self.context.projects.current_project, "task": self._task_view(self.context.tasks.current_task())})
                else:
                    self.send_json(
                        {
                            **response,
                            "project": self._compact_project(self.context.projects.current_project),
                            "task": self._compact_task(self.context.tasks.current_task()),
                        }
                    )
                return
            if path in {"/api/runtime/turns/interrupt", "/api/turn/interrupt"}:
                profile = self._resolve_runtime_profile(payload.get("profile_id"))
                self.send_json(
                    self.context.runtime.interrupt_turn(
                        profile,
                        str(payload.get("thread_id") or ""),
                        str(payload.get("turn_id") or ""),
                    )
                )
                return
            if path == "/api/runtime/dependencies/wsl/scripts":
                self.send_json(self.context.wsl_dependencies.write_scripts(self._optional_string(payload, "distro")))
                return
            if path == "/api/runtime/dependencies/wsl/install":
                self.send_json(self.context.wsl_dependencies.launch_installer(self._optional_string(payload, "distro")))
                return
            self.send_json({"ok": False, "error": "Not found"}, status=404)
        except Exception as exc:  # noqa: BLE001
            self.send_json(public_error(exc), status=400)

    def do_DELETE(self) -> None:  # noqa: N802
        try:
            self._require_admin_token()
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            query = urllib.parse.parse_qs(parsed.query)
            if path == "/api/project/saves/delete":
                save_id = str(query.get("save_id", [""])[0])
                response = self.context.checkpoints.delete(save_id)
                self._record_ui_state_event("checkpoint_deleted", {"save_id": save_id})
                self.send_json(response)
                return
            self.send_json({"ok": False, "error": "Not found"}, status=404)
        except Exception as exc:  # noqa: BLE001
            self.send_json(public_error(exc), status=400)

    def _profile(self, profile_id: Any) -> dict[str, Any]:
        return self.context.get_profile_with_capabilities(profile_id)

    def _resolve_runtime_profile(self, profile_id: Any) -> dict[str, Any]:
        return self.context.resolve_runtime_profile(profile_id)

    def _resolve_runtime_profile_for_turn(self, payload: dict[str, Any]) -> dict[str, Any]:
        explicit_profile_id = self._optional_string(payload, "profile_id")
        if explicit_profile_id:
            return self._resolve_runtime_profile(explicit_profile_id)
        inferred_profile_id = self._infer_profile_id_for_model(
            model=self._optional_string(payload, "model"),
            effort=self._optional_string(payload, "effort"),
        )
        if inferred_profile_id:
            return self._resolve_runtime_profile(inferred_profile_id)
        return self._resolve_runtime_profile(None)

    def _infer_profile_id_for_model(self, model: str | None, effort: str | None) -> str | None:
        model_text = str(model or "").strip()
        if not model_text:
            return None
        provider_hint = ""
        native_model = model_text
        if "/" in model_text:
            provider_hint, native_model = [part.strip() for part in model_text.split("/", 1)]
        native_model = native_model.strip()
        if not native_model:
            return None
        profiles = [item for item in self.context.profiles.list_profiles().get("profiles") or [] if isinstance(item, dict)]
        active_provider = str((self.context.tasks.active_provider_thread() or {}).get("provider_id") or "").strip()
        candidates: list[dict[str, Any]] = []
        for item in profiles:
            provider_id = str(item.get("provider_id") or "").strip()
            profile_model = str(item.get("model") or "").strip()
            if provider_hint and provider_id != provider_hint:
                continue
            if profile_model != native_model and f"{provider_id}/{profile_model}" != model_text:
                continue
            candidates.append(item)
        if not candidates:
            return None
        effort_text = str(effort or "").strip()

        def score(item: dict[str, Any]) -> tuple[int, str]:
            provider_id = str(item.get("provider_id") or "").strip()
            profile_id = str(item.get("profile_id") or "").strip()
            item_effort = str(item.get("reasoning_effort") or "").strip()
            value = 0
            if provider_hint and provider_id == provider_hint:
                value += 100
            if active_provider and provider_id == active_provider:
                value += 20
            if effort_text and item_effort == effort_text:
                value += 10
            if effort_text and effort_text in profile_id:
                value += 3
            if profile_id.endswith("-default"):
                value += 1
            return (-value, profile_id)

        chosen = sorted(candidates, key=score)[0]
        return str(chosen.get("profile_id") or "").strip() or None

    def _profile_with_model_capabilities(self, profile: dict[str, Any]) -> dict[str, Any]:
        return self.context.profile_with_model_capabilities(profile)

    def _payload_with_default_workspace_root(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        if str(normalized.get("workspace_root") or "").strip():
            return normalized
        workspace_root = self._default_workspace_root()
        if workspace_root:
            normalized["workspace_root"] = workspace_root
        return normalized

    def _default_workspace_root(self) -> str:
        current_project_service = getattr(getattr(self, "context", None), "projects", None)
        project_payload = getattr(current_project_service, "current_project", None)
        if isinstance(project_payload, dict):
            project_root = str(project_payload.get("workspace_root") or "").strip()
            if project_root:
                return project_root
        seed_root = getattr(getattr(self, "context", None), "seed_root", None)
        if isinstance(seed_root, Path):
            return str(seed_root.resolve())
        if seed_root is not None:
            return str(seed_root).strip()
        return ""

    def _optional_string(self, payload: dict[str, Any], key: str) -> str | None:
        value = payload.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _optional_query_string(self, query: dict[str, list[str]], key: str) -> str | None:
        value = query.get(key, [None])[0]
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _ephemeral_key(self, payload: dict[str, Any]) -> str | None:
        session_key = str(payload.get("session_key") or "").strip()
        if session_key:
            return session_key
        api_key = str(payload.get("api_key") or "").strip()
        if api_key:
            return api_key
        key_file_path = str(payload.get("key_file_path") or "").strip()
        if not key_file_path:
            return None
        path = Path(key_file_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Key file does not exist: {path}")
        return path.read_text(encoding="utf-8").strip()

    def _compact_project(self, project: dict[str, Any] | None) -> dict[str, Any] | None:
        if not project:
            return None
        return {
            "schema_version": str(project.get("schema_version") or ""),
            "project_id": str(project.get("project_id") or ""),
            "name": str(project.get("name") or ""),
            "project_file": str(project.get("project_file") or ""),
            "workspace_root": str(project.get("workspace_root") or ""),
            "entry_mode": str(project.get("entry_mode") or ""),
            "default_profile_id": str(project.get("default_profile_id") or ""),
            "default_model": str(project.get("default_model") or ""),
            "default_effort": str(project.get("default_effort") or ""),
            "current_thread_id": str(project.get("current_thread_id") or ""),
            "current_task_id": str(project.get("current_task_id") or ""),
            "recent_threads": list(project.get("recent_threads") or [])[:8],
            "recent_tasks": list(project.get("recent_tasks") or [])[:8],
            "ui_preferences": dict(project.get("ui_preferences") or {}),
            "updated_at": str(project.get("updated_at") or ""),
        }

    def _compact_task(self, task: dict[str, Any] | None) -> dict[str, Any] | None:
        if not task:
            return None
        active_thread_id = str(task.get("active_provider_thread_id") or "")
        provider_threads = [dict(item) for item in list(task.get("provider_threads") or []) if isinstance(item, dict)]
        active = [item for item in provider_threads if str(item.get("thread_id") or "") == active_thread_id]
        recent = sorted(provider_threads, key=lambda item: str(item.get("updated_at") or ""), reverse=True)[:6]
        compact_threads: list[dict[str, Any]] = []
        for item in [*active, *recent]:
            thread_id = str(item.get("thread_id") or "")
            if not thread_id or any(existing.get("thread_id") == thread_id for existing in compact_threads):
                continue
            compact_threads.append(
                {
                    "thread_id": thread_id,
                    "role": str(item.get("role") or ""),
                    "profile_id": str(item.get("profile_id") or ""),
                    "provider_id": str(item.get("provider_id") or ""),
                    "model": str(item.get("model") or ""),
                    "reasoning_effort": str(item.get("reasoning_effort") or ""),
                    "permission_mode": str(item.get("permission_mode") or ""),
                    "collaboration_mode": item.get("collaboration_mode"),
                    "name": self._compact_text(item.get("name"), 180),
                    "updated_at": str(item.get("updated_at") or ""),
                    "missing_at": str(item.get("missing_at") or ""),
                    "missing_reason": str(item.get("missing_reason") or ""),
                }
            )
        return {
            "schema_version": str(task.get("schema_version") or ""),
            "task_id": str(task.get("task_id") or ""),
            "project_id": str(task.get("project_id") or ""),
            "title": _display_task_title(task.get("title")) or "New task",
            "status": str(task.get("status") or ""),
            "handoff_policy": str(task.get("handoff_policy") or ""),
            "active_provider_thread_id": active_thread_id,
            "lane_state": self._lane_state(task),
            "provider_threads": compact_threads,
            "fork_threads": list(task.get("fork_threads") or [])[:6],
            "handoff_events": self._compact_handoff_events(list(task.get("handoff_events") or [])[-6:]),
            "goal": task.get("goal"),
            "plan": task.get("plan"),
            "checkpoint_refs": list(task.get("checkpoint_refs") or [])[:10],
            "verification_refs": list(task.get("verification_refs") or [])[:10],
            "diagnostic_refs": list(task.get("diagnostic_refs") or [])[:10],
            "asset_context_refs": list(task.get("asset_context_refs") or [])[:6],
            "context_pack_refs": list(task.get("context_pack_refs") or [])[:6],
            "created_at": str(task.get("created_at") or ""),
            "updated_at": str(task.get("updated_at") or ""),
        }

    def _compact_handoff_events(self, events: list[Any]) -> list[dict[str, Any]]:
        compact: list[dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            compact.append(self._compact_handoff_event(event))
        return compact

    def _compact_handoff_event(self, event: dict[str, Any]) -> dict[str, Any]:
        context = getattr(self, "context", None)
        if getattr(context, "tasks", None) is not None:
            return context.tasks.compact_handoff_event(event)
        return {
            "event_id": str(event.get("event_id") or ""),
            "type": str(event.get("type") or ""),
            "handoff_policy": str(event.get("handoff_policy") or ""),
            "from_thread_id": str(event.get("from_thread_id") or ""),
            "to_thread_id": str(event.get("to_thread_id") or ""),
            "profile_id": str(event.get("profile_id") or ""),
            "provider_id": str(event.get("provider_id") or ""),
            "model": str(event.get("model") or ""),
            "reasoning_effort": str(event.get("reasoning_effort") or ""),
            "permission_mode": str(event.get("permission_mode") or ""),
            "reused_existing": bool(event.get("reused_existing")),
            "created_at": str(event.get("created_at") or ""),
        }

    def _lane_state(self, task: dict[str, Any] | None) -> dict[str, Any] | None:
        context = getattr(self, "context", None)
        if not task or getattr(context, "tasks", None) is None:
            return None
        return context.tasks.lane_state(task=task)

    def _task_view(self, task: dict[str, Any] | None) -> dict[str, Any] | None:
        context = getattr(self, "context", None)
        if not task or getattr(context, "tasks", None) is None:
            return task
        return context.tasks.task_view(task)

    def _compact_text(self, value: Any, limit: int = 180) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)].rstrip() + "…"

    def _require_admin_token(self) -> None:
        provided = str(self.headers.get("X-Admin-Token") or self.headers.get("X-Admin-Session-Token") or "").strip()
        if not provided:
            authorization = str(self.headers.get("Authorization") or "").strip()
            if authorization.lower().startswith("bearer "):
                provided = authorization[7:].strip()
        if provided != self.context.admin_token:
            raise PermissionError("Missing or invalid admin session token.")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        print("astrabridge-sidecar: " + (format % args))


def serve(port: int, seed_root: Path) -> None:
    if _port_in_use(port):
        raise RuntimeError(f"AstraBridge sidecar port is already in use: 127.0.0.1:{port}")
    Handler.context = AppContext(seed_root)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"AstraBridge sidecar listening at http://127.0.0.1:{port}")
    print(f"Seed root: {seed_root.resolve()}")
    server.serve_forever()


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--seed-root", default=str(Path.cwd()))
    args = parser.parse_args()
    if args.serve:
        serve(args.port, Path(args.seed_root))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


