from __future__ import annotations

import base64
import binascii
import inspect
import io
import json
import hashlib
import os
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import zipfile
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar import common as common_module
from astrabridge_sidecar import project_service as project_service_module
from astrabridge_sidecar import runtime_service as runtime_service_module
from astrabridge_sidecar import lcr_web_service as lcr_web_service_module
from astrabridge_sidecar import lcr_web_mcp_server
from astrabridge_sidecar.app_server_client import AppServerClient, JsonRpcError
from astrabridge_sidecar.asset_registry_service import AssetRegistryService
from astrabridge_sidecar.coding_kernel import project_handoff_event_to_coding_events, project_turn_to_coding_events
from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.checkpoint_service import CheckpointService
from astrabridge_sidecar.dogfood_run_service import DogfoodRunService
from astrabridge_sidecar.image_prompt_strategy import apply_prompt_guide, build_rewrite_instruction, prompt_guides_payload
from astrabridge_sidecar.isolation_audit_service import IsolationAuditService
from astrabridge_sidecar.llm_api_manager_service import LlmApiManagerService
from astrabridge_sidecar.lcr_web_service import LcrWebService
from astrabridge_sidecar.lcr_web_mcp_server import _tools as lcr_web_mcp_tools
from astrabridge_sidecar.metadata_service import MetadataService
from astrabridge_sidecar.mcp_config_service import McpConfigService
from astrabridge_sidecar.model_catalog import known_context_window, known_input_modalities, known_reasoning_efforts
from astrabridge_sidecar.official_login_guard import OFFICIAL_CODEX_DISABLED_ERROR, disabled_status
from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.providers import classify_runtime_failure, get_provider_profile
from astrabridge_sidecar.providers.history_projector import HistoryProjector, NeutralMessage, ReasoningArtifact
from astrabridge_sidecar.project_context_service import ProjectContextService
from astrabridge_sidecar.project_service import DEFAULT_RUNTIME_HOST_ENV, DEFAULT_RUNTIME_WSL_DISTRO_ENV, ProjectService
from astrabridge_sidecar.project_tools_service import ProjectToolsService
from astrabridge_sidecar.router_config_service import RouterConfigService
from astrabridge_sidecar.router_service import ROUTER_ENV_KEY, RouterService
from astrabridge_sidecar.runtime_config_service import RuntimeConfigService
from astrabridge_sidecar.runtime_supervisor_service import RuntimeSupervisorService
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.server import AppContext, Handler, sse_frame, turn_text_from_payload
from astrabridge_sidecar.task_conversation_service import TaskConversationService
from astrabridge_sidecar.task_service import TaskService
from astrabridge_sidecar.wsl_dependency_service import WslDependencyService
from astrabridge_sidecar.yunwu_image_mcp_server import _normalize_path_for_os as yunwu_image_normalize_path_for_os
from astrabridge_sidecar.yunwu_image_mcp_server import _tools as yunwu_image_mcp_tools
from astrabridge_sidecar.yunwu_image_service import YunwuImageService


def _png_rgba(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)

    row = bytes([0]) + bytes(rgba) * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _png_rgba_rect(width: int, height: int, rect: tuple[int, int, int, int], rgba: tuple[int, int, int, int]) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)

    left, top, right, bottom = rect
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend(rgba if left <= x < right and top <= y < bottom else (0, 0, 0, 0))
        rows.append(bytes(row))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


class DummyRouter:
    def __init__(self) -> None:
        self.provider_tests: list[dict[str, object]] = []
        self.model_tests: list[dict[str, object]] = []

    def test_provider(self, provider_id: str, model_id: str | None = None, *, stream: bool = False) -> dict[str, object]:
        self.provider_tests.append({"provider_id": provider_id, "model_id": model_id, "stream": stream})
        return {
            "ok": True,
            "provider": provider_id,
            "model": model_id or f"{provider_id}/model",
            "stream": stream,
            "status": 200,
            "preview": {"model": model_id},
            "response_excerpt": "ok",
        }

    def test_model_case(self, *, provider_id: str, model_id: str, effort: str | None = None, temperature: float | None = None, stream: bool = False) -> dict[str, object]:
        self.model_tests.append({"provider_id": provider_id, "model_id": model_id, "effort": effort, "temperature": temperature, "stream": stream})
        return {
            "ok": True,
            "provider": provider_id,
            "model": model_id,
            "effort": effort,
            "temperature": temperature,
            "stream": stream,
            "status": 200,
            "warnings": [],
            "preview": {"model": model_id},
            "response_excerpt": "ok",
        }


class _LiveProcessStub:
    def poll(self) -> None:
        return None


class _RuntimeEventsStub:
    def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
        return {
            "cursor": 2,
            "events": [
                {"timestamp": "2026-06-17T00:00:00+08:00", "method": "item/updated", "params": {"item": {"command": "node --check js/main.js", "status": "completed"}}},
                {"timestamp": "2026-06-17T00:01:00+08:00", "type": "runtime_supervisor", "command": "pwd", "status": "completed"},
            ],
        }


class AstraBridgeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._test_env_root = tempfile.TemporaryDirectory()
        self._env_keys = [
            "APPDATA",
            "LOCALAPPDATA",
            "CODEX_HOME",
            "ASTRABRIDGE_APPDATA",
            "ASTRABRIDGE_CODEX_HOME",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "NO_PROXY",
            "no_proxy",
        ]
        self._env_backup = {key: os.environ.get(key) for key in self._env_keys}
        env_root = Path(self._test_env_root.name)
        os.environ["APPDATA"] = str(env_root / "Roaming")
        os.environ["LOCALAPPDATA"] = str(env_root / "Local")
        os.environ["ASTRABRIDGE_APPDATA"] = str(env_root / "AstraBridgeAppData")
        os.environ["ASTRABRIDGE_CODEX_HOME"] = str(env_root / "AstraBridgeCodexHome")
        self._default_runtime_host = os.environ.get(DEFAULT_RUNTIME_HOST_ENV)
        self._default_runtime_distro = os.environ.get(DEFAULT_RUNTIME_WSL_DISTRO_ENV)
        os.environ[DEFAULT_RUNTIME_HOST_ENV] = "windows"
        os.environ.pop(DEFAULT_RUNTIME_WSL_DISTRO_ENV, None)
        project_service_module._DEFAULT_RUNTIME_PREFS_CACHE = None

    def tearDown(self) -> None:
        if self._default_runtime_host is None:
            os.environ.pop(DEFAULT_RUNTIME_HOST_ENV, None)
        else:
            os.environ[DEFAULT_RUNTIME_HOST_ENV] = self._default_runtime_host
        if self._default_runtime_distro is None:
            os.environ.pop(DEFAULT_RUNTIME_WSL_DISTRO_ENV, None)
        else:
            os.environ[DEFAULT_RUNTIME_WSL_DISTRO_ENV] = self._default_runtime_distro
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        project_service_module._DEFAULT_RUNTIME_PREFS_CACHE = None
        for attempt in range(6):
            try:
                self._test_env_root.cleanup()
                break
            except PermissionError:
                if attempt == 5:
                    self._test_env_root._ignore_cleanup_errors = True  # type: ignore[attr-defined]  # noqa: SLF001
                    self._test_env_root.cleanup()
                    break
                time.sleep(0.1 * (attempt + 1))

    def test_write_json_retries_transient_replace_permission_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "project_context_state.json"
            original_replace = common_module.os.replace
            calls = {"count": 0}

            def flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
                calls["count"] += 1
                if calls["count"] == 1:
                    raise PermissionError("simulated transient Windows file lock")
                original_replace(src, dst)

            common_module.os.replace = flaky_replace  # type: ignore[assignment]
            try:
                common_module.write_json(target, {"ok": True})
            finally:
                common_module.os.replace = original_replace  # type: ignore[assignment]

            self.assertEqual(calls["count"], 2)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"ok": True})
            self.assertEqual(list(Path(temp).glob(".project_context_state.json.*.tmp")), [])

    def test_write_json_skips_replace_when_content_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "router_config.json"
            target.write_text('{\n  "ok": true\n}\n', encoding="utf-8")
            original_replace = common_module.os.replace
            calls = {"count": 0}

            def counting_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
                calls["count"] += 1
                original_replace(src, dst)

            common_module.os.replace = counting_replace  # type: ignore[assignment]
            try:
                common_module.write_json(target, {"ok": True})
            finally:
                common_module.os.replace = original_replace  # type: ignore[assignment]

            self.assertEqual(calls["count"], 0)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"ok": True})

    def test_project_tools_file_preview_rejects_escape_and_secret_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
            (workspace / ".env").write_text("API_KEY=not-real\n", encoding="utf-8")
            state = workspace / ".astrabridge"
            state.mkdir()
            (state / "runtime_events.jsonl").write_text("{}\n", encoding="utf-8")
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="existing")
            tools = ProjectToolsService(projects, _RuntimeEventsStub())

            tree = tools.files_tree()
            paths = {item["path"] for item in tree["items"]}
            self.assertIn("README.md", paths)
            self.assertNotIn(".env", paths)
            self.assertNotIn(".astrabridge/runtime_events.jsonl", paths)
            self.assertEqual(tools.read_file("README.md")["content"], "# Demo\n")
            with self.assertRaises(ValueError):
                tools.read_file("../outside.txt")
            with self.assertRaises(ValueError):
                tools.read_file(".env")
            with self.assertRaises(ValueError):
                tools.read_file(".astrabridge/runtime_events.jsonl")

    def test_project_tools_terminal_history_is_summarized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="existing")
            tools = ProjectToolsService(projects, _RuntimeEventsStub())

            history = tools.terminal_history()
            commands = history["commands"]
            self.assertEqual(len(commands), 2)
            self.assertIn("node --check", commands[0]["command"])
            self.assertEqual(history["workspace_root"], str(workspace.resolve()))

    def test_project_tools_review_scopes_parent_git_repo_to_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            init = subprocess.run(["git", "init"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            if init.returncode != 0:
                self.skipTest("git is not available")
            subprocess.run(
                ["git", "-c", "user.email=demo@example.invalid", "-c", "user.name=AstraBridge Test", "commit", "--allow-empty", "-m", "init"],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            workspace = root / "PRIVATE" / "demo" / "workspace"
            workspace.mkdir(parents=True)
            (root / "repo_change.txt").write_text("outside workspace\n", encoding="utf-8")
            (workspace / "scorecard.py").write_text("print('ok')\n", encoding="utf-8")
            project_file = root / "demo.abproj"
            projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="existing")
            tools = ProjectToolsService(projects, _RuntimeEventsStub())

            status = tools.review_status()
            paths = {item["path"] for item in status["files"]}
            self.assertIn("scorecard.py", paths)
            self.assertNotIn("repo_change.txt", paths)
            self.assertEqual(status["git"]["changed_files"], 1)

            diff = tools.review_diff("scorecard.py")
            self.assertTrue(diff["ok"])
            self.assertTrue(diff.get("synthetic"))
            self.assertIn("diff --astrabridge", diff["diff"])
            self.assertIn("+print('ok')", diff["diff"])

    def test_app_data_dir_does_not_migrate_legacy_local_store(self) -> None:
        original_appdata = os.environ.get("APPDATA")
        original_localappdata = os.environ.get("LOCALAPPDATA")
        original_override = os.environ.get("ASTRABRIDGE_APPDATA")
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                roaming = root / "Roaming"
                local = root / "Local"
                roaming.mkdir()
                local.mkdir()
                old_store = local / "LCR"
                old_store.mkdir()
                (old_store / "projects.json").write_text('{"projects":[{"project_file":"D:/demo/demo.abproj"}]}\n', encoding="utf-8")
                (old_store / "current_project.json").write_text('{"project_file":"D:/demo/demo.abproj"}\n', encoding="utf-8")
                os.environ["APPDATA"] = str(roaming)
                os.environ["LOCALAPPDATA"] = str(local)
                os.environ.pop("ASTRABRIDGE_APPDATA", None)

                target = common_module.app_data_dir()

                self.assertEqual(target, (roaming / "AstraBridge").resolve())
                self.assertFalse((target / "projects.json").exists())
                self.assertFalse((target / "current_project.json").exists())
        finally:
            if original_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original_appdata
            if original_localappdata is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = original_localappdata
            if original_override is None:
                os.environ.pop("ASTRABRIDGE_APPDATA", None)
            else:
                os.environ["ASTRABRIDGE_APPDATA"] = original_override

    def test_project_create_and_duplicate_workspace_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = root / "recent.json"
            workspace = root / "workspace"
            workspace.mkdir()
            service = ProjectService(store)

            project = service.create_project(
                "Demo",
                root / "demo.abproj",
                workspace_root=workspace,
                entry_mode="existing",
            )

            self.assertEqual(project["schema_version"], "astrabridge-project-v1")
            self.assertIsNone(project["current_task_id"])
            self.assertEqual(project["recent_tasks"], [])
            self.assertTrue((workspace / ".astrabridge" / "attachments").exists())
            self.assertTrue((workspace / ".astrabridge" / "runtime_events.jsonl").exists())

            with self.assertRaises(ValueError):
                service.create_project(
                    "Other",
                    root / "other.abproj",
                    workspace_root=workspace,
                    entry_mode="existing",
                )

    def test_app_server_client_is_not_running_after_reader_disconnect(self) -> None:
        client = AppServerClient(codex_executable="codex")
        client._process = _LiveProcessStub()  # type: ignore[assignment]

        self.assertTrue(client.is_running())

        client._disconnected.set()

        self.assertFalse(client.is_running())

    def test_app_server_client_notification_callback_error_does_not_disconnect_reader(self) -> None:
        client = AppServerClient(codex_executable="codex", on_notification=lambda _method, _params: (_ for _ in ()).throw(PermissionError("cache locked")))

        client._emit_notification("thread/started", {"thread": {"id": "thread-a"}})  # noqa: SLF001

        self.assertFalse(client._disconnected.is_set())  # noqa: SLF001

    def test_handler_accepts_utf8_bom_json_body(self) -> None:
        handler = object.__new__(Handler)
        body = "\ufeff{\"project_file\":\"demo.abproj\"}".encode("utf-8")
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)

        self.assertEqual(handler.read_json_body()["project_file"], "demo.abproj")

    def test_project_defaults_to_wsl_when_runtime_default_is_wsl(self) -> None:
        previous_host = os.environ.get(DEFAULT_RUNTIME_HOST_ENV)
        previous_distro = os.environ.get(DEFAULT_RUNTIME_WSL_DISTRO_ENV)
        os.environ[DEFAULT_RUNTIME_HOST_ENV] = "wsl"
        os.environ[DEFAULT_RUNTIME_WSL_DISTRO_ENV] = "Ubuntu-24.04"
        project_service_module._DEFAULT_RUNTIME_PREFS_CACHE = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = root / "workspace"
                workspace.mkdir()
                service = ProjectService(root / "recent.json")

                project = service.create_project(
                    "Demo",
                    root / "demo.abproj",
                    workspace_root=workspace,
                    entry_mode="existing",
                )

                self.assertEqual(project["ui_preferences"]["execution_host"], "wsl")
                self.assertEqual(project["ui_preferences"]["wsl_distro"], "Ubuntu-24.04")

        finally:
            if previous_host is None:
                os.environ.pop(DEFAULT_RUNTIME_HOST_ENV, None)
            else:
                os.environ[DEFAULT_RUNTIME_HOST_ENV] = previous_host
            if previous_distro is None:
                os.environ.pop(DEFAULT_RUNTIME_WSL_DISTRO_ENV, None)
            else:
                os.environ[DEFAULT_RUNTIME_WSL_DISTRO_ENV] = previous_distro
            project_service_module._DEFAULT_RUNTIME_PREFS_CACHE = None

    def test_project_service_refresh_current_project_reloads_disk_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            project = projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            path = Path(str(project["project_file"]))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["current_thread_id"] = "thread-refreshed"
            path.write_text(json.dumps(payload), encoding="utf-8")

            refreshed = projects.refresh_current_project()

            self.assertEqual(refreshed["current_thread_id"], "thread-refreshed")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-refreshed")

    def test_project_service_refresh_current_project_repairs_and_persists_runtime_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            project = projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            path = Path(str(project["project_file"]))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["default_profile_id"] = "yunwu-gpt-55-xhigh"
            payload["default_model"] = "glm/glm-5.2"
            payload["default_effort"] = "max"
            path.write_text(json.dumps(payload), encoding="utf-8")

            refreshed = projects.refresh_current_project()
            persisted = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(refreshed["default_profile_id"], "openai-compatible")
            self.assertEqual(refreshed["default_model"], "gpt-5.5")
            self.assertEqual(refreshed["default_effort"], "xhigh")
            self.assertEqual(persisted["default_profile_id"], "openai-compatible")
            self.assertEqual(persisted["default_model"], "gpt-5.5")
            self.assertEqual(persisted["default_effort"], "xhigh")

    def test_project_service_reconcile_task_projection_repairs_project_thread_focus(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            project = projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            path = Path(str(project["project_file"]))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["current_task_id"] = "task-a"
            payload["current_thread_id"] = None
            path.write_text(json.dumps(payload), encoding="utf-8")
            projects.current_project["current_task_id"] = "task-a"
            projects.current_project["current_thread_id"] = None

            reconciled = projects.reconcile_task_projection(
                {
                    "task_id": "task-a",
                    "active_provider_thread_id": "thread-live",
                }
            )

            disk_payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(reconciled["current_thread_id"], "thread-live")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-live")
            self.assertEqual(disk_payload["current_thread_id"], "thread-live")
            self.assertEqual(disk_payload["recent_threads"][0], "thread-live")

    def test_task_service_tracks_provider_handoff_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)

            task = tasks.create_task(
                "Build game",
                thread_id="thread-openai",
                settings={
                    "profile_id": "openai-default",
                    "provider_id": "openai",
                    "model": "gpt-5.5",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            self.assertEqual(projects.current_project["current_task_id"], task["task_id"])
            self.assertEqual(projects.current_project["current_thread_id"], "thread-openai")

            event = tasks.record_provider_handoff(
                from_thread_id="thread-openai",
                to_thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
                reused_existing=False,
            )

            snapshot = tasks.snapshot()
            current = snapshot["current_task"]
            self.assertEqual(snapshot["schema_version"], "astrabridge-task-state-v1")
            self.assertEqual(event["to_thread_id"], "thread-deepseek")
            self.assertEqual(current["active_provider_thread_id"], "thread-deepseek")
            self.assertEqual(len(current["provider_threads"]), 2)
            self.assertEqual(event["transition_summary"]["to_provider"], "deepseek")
            self.assertEqual(event["transition_summary"]["to_model"], "deepseek-v4-pro")
            self.assertEqual(event["transition_summary"]["projection_mode"], "task_context_fresh_thread")
            self.assertGreaterEqual(int(event["transition_summary"]["context_budget"]), 1000000)
            self.assertEqual(event["transition_summary"]["target_runtime"]["protocol"], "chat")
            self.assertEqual(event["transition_summary"]["target_runtime"]["env_key"], "DEEPSEEK_API_KEY")
            self.assertEqual(event["transition_summary"]["transition_plan"]["action"], "provider_handoff")
            self.assertEqual(event["transition_summary"]["transition_plan"]["target"]["base_url"], "https://api.deepseek.com")
            self.assertEqual(event["transition_summary"]["transition_plan"]["reasoning_effort"], "max")
            state_text = (workspace / ".astrabridge" / "tasks.json").read_text(encoding="utf-8")
            self.assertIn("multi_provider_handoff", state_text)
            self.assertNotIn("Authorization", state_text)

    def test_task_conversation_merges_provider_threads_and_redacts_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Scorecard task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
            )
            tasks.record_provider_handoff(
                from_thread_id="thread-deepseek",
                to_thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.7-code",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
                reused_existing=False,
            )
            conversation = TaskConversationService(projects, tasks)
            conversation.record_thread_snapshot(
                {
                    "id": "thread-deepseek",
                    "name": "DeepSeek lane",
                    "status": {"type": "idle"},
                    "shellSettings": {"profile_id": "deepseek-default", "model": "deepseek-v4-pro"},
                    "turns": [
                        {
                            "id": "turn-1",
                            "startedAt": 1,
                            "items": [
                                {"type": "userMessage", "id": "user-1", "text": "Build a release readiness scorecard."},
                                {"type": "agentMessage", "id": "agent-1", "text": "Created scorecard.py"},
                            ],
                        }
                    ],
                }
            )
            conversation.record_thread_snapshot(
                {
                    "id": "thread-kimi",
                    "name": "Kimi lane",
                    "status": {"type": "idle"},
                    "shellSettings": {"profile_id": "kimi-default", "model": "kimi-k2.7-code"},
                    "turns": [
                        {
                            "id": "turn-2",
                            "startedAt": 2,
                            "items": [
                                {
                                    "type": "agentMessage",
                                    "id": "agent-2",
                                    "text": "Reviewed scorecard.py and added a boundary test. Authorization: Bearer should-not-persist",
                                }
                            ],
                        }
                    ],
                }
            )

            result = conversation.conversation(task_id=task["task_id"])
            thread = result["thread"]

            self.assertEqual(thread["id"], f"task:{task['task_id']}")
            self.assertTrue(thread["isCompositeTaskThread"])
            self.assertEqual(thread["active_provider_thread_id"], "thread-kimi")
            self.assertEqual([turn["id"] for turn in thread["turns"]], ["turn-1", "turn-2"])
            self.assertEqual(thread["turns"][0]["provider_id"], "deepseek")
            self.assertEqual(thread["turns"][1]["provider_id"], "kimi")
            self.assertEqual(thread["turns"][1]["items"][0]["provider_id"], "kimi")
            transcript_text = (workspace / ".astrabridge" / "task_transcripts.json").read_text(encoding="utf-8")
            self.assertIn("task_transcripts", str(result["transcript_path"]))
            self.assertNotIn("should-not-persist", transcript_text)
            self.assertNotIn("Authorization", transcript_text)

    def test_project_context_pack_includes_task_conversation_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Scorecard task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
            )
            conversation = TaskConversationService(projects, tasks)
            conversation.record_thread_snapshot(
                {
                    "id": "thread-deepseek",
                    "turns": [
                        {
                            "id": "turn-1",
                            "startedAt": 1,
                            "items": [
                                {"type": "userMessage", "id": "user-1", "text": "Build a release readiness scorecard."},
                                {"type": "fileChange", "id": "file-1", "changes": [{"path": "scorecard.py"}]},
                            ],
                        }
                    ],
                }
            )
            tasks.record_provider_handoff(
                from_thread_id="thread-deepseek",
                to_thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                reused_existing=False,
            )
            context = ProjectContextService(projects, task_service=tasks, task_conversation_service=conversation)

            pack = context.snapshot(thread_id="thread-deepseek")["context_pack"]

            self.assertEqual(pack["task_conversation_digest"]["status"], "ok")
            self.assertEqual(pack["task_conversation_digest"]["task_id"], task["task_id"])
            self.assertIn("Task conversation digest", pack["text"])
            self.assertIn("Build a release readiness scorecard", pack["text"])
            self.assertIn("scorecard.py", pack["text"])
            self.assertEqual(pack["task_conversation_digest"]["items"][0]["event_types"], ["agent_message", "file_change"])
            self.assertEqual(pack["task_conversation_digest"]["items"][1]["event_types"], ["provider_handoff"])
            self.assertIn("Provider handoff", pack["task_conversation_digest"]["items"][1]["summary"])

    def test_coding_event_projection_maps_core_coding_turn_items(self) -> None:
        events = project_turn_to_coding_events(
            task_id="task-1",
            visible_thread_id="task:task-1",
            turn={
                "id": "turn-1",
                "source_thread_id": "thread-deepseek",
                "provider_id": "deepseek",
                "model": "deepseek-v4-pro",
                "startedAt": 1,
                "items": [
                    {"type": "userMessage", "id": "user-1", "text": "Inspect the failing test."},
                    {"type": "reasoning", "id": "reasoning-1", "summary": ["Need to inspect the diff first."]},
                    {"type": "commandExecution", "id": "cmd-1", "command": "pytest -q", "status": "completed", "exitCode": 1, "aggregatedOutput": "1 failed"},
                    {"type": "fileChange", "id": "file-1", "changes": [{"path": "scorecard.py"}, {"path": "README.md"}]},
                    {"type": "contextCompaction", "id": "compact-1"},
                ],
            },
        )

        self.assertEqual([item["event_type"] for item in events], ["agent_message", "reasoning_summary", "command_execution", "file_change", "runtime_transition"])
        self.assertEqual(events[2]["payload"]["command"], "pytest -q")
        self.assertEqual(events[3]["payload"]["paths"], ["scorecard.py", "README.md"])
        self.assertEqual(events[4]["payload"]["transition"], "context_compaction")

    def test_coding_event_projection_maps_provider_handoff_event(self) -> None:
        events = project_handoff_event_to_coding_events(
            task_id="task-1",
            visible_thread_id="task:task-1",
            handoff_event={
                "event_id": "handoff-1",
                "from_thread_id": "thread-openai",
                "to_thread_id": "thread-kimi",
                "provider_id": "kimi",
                "model": "kimi-k2.6",
                "reasoning_effort": "high",
                "created_at": "2026-06-22T00:00:00+00:00",
                "transition_summary": {"projection_mode": "task_context_fresh_thread"},
            },
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "provider_handoff")
        self.assertEqual(events[0]["execution_thread_id"], "thread-kimi")
        self.assertEqual(events[0]["payload"]["transition_summary"]["projection_mode"], "task_context_fresh_thread")

    def test_default_task_inherits_thread_context_goal_and_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            shell_root = workspace / ".astrabridge"
            thread_id = "thread-deepseek"
            (shell_root / "thread_cache.json").write_text(
                json.dumps(
                    {
                        "by_id": {
                            thread_id: {
                                "name": "DS continuity thread",
                                "profile_id": "deepseek-v4-pro-max",
                                "model": "deepseek/deepseek-v4-pro",
                                "reasoning_effort": "xhigh",
                                "permission_mode": "auto",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (shell_root / "project_context_state.json").write_text(
                json.dumps(
                    {
                        "threads": {
                            thread_id: {
                                "goal": {"objective": "Continue the same game task"},
                                "latest_plan": {
                                    "steps": [
                                        {"step": "Keep task context", "status": "inProgress"},
                                    ],
                                },
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            task = TaskService(projects).ensure_default_task(thread_id=thread_id, title="Game task")

            provider_thread = task["provider_threads"][0]
            self.assertEqual(provider_thread["profile_id"], "deepseek-v4-pro-max")
            self.assertEqual(provider_thread["provider_id"], "deepseek")
            self.assertEqual(provider_thread["model"], "deepseek-v4-pro")
            self.assertEqual(provider_thread["reasoning_effort"], "max")
            self.assertEqual(task["goal"]["objective"], "Continue the same game task")
            self.assertEqual(task["plan"]["steps"][0]["step"], "Keep task context")

    def test_rebinding_existing_provider_thread_preserves_route_over_stale_cache_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Build game",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-v4-pro-max",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                    "name": "DeepSeek implementation",
                },
            )
            shell_root = workspace / ".astrabridge"
            (shell_root / "thread_cache.json").write_text(
                json.dumps(
                    {
                        "by_id": {
                            "thread-deepseek": {
                                "name": "AstraBridge minimal visual mode: this prompt is intentionally far too long",
                                "profile_id": "kimi-k2-6",
                                "provider_id": "kimi",
                                "model": "kimi/kimi-k2.6",
                                "reasoning_effort": "xhigh",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            rebound = tasks.ensure_default_task(thread_id="thread-deepseek")
            provider_thread = rebound["provider_threads"][0]

            self.assertEqual(provider_thread["profile_id"], "deepseek-v4-pro-max")
            self.assertEqual(provider_thread["provider_id"], "deepseek")
            self.assertEqual(provider_thread["model"], "deepseek-v4-pro")
            self.assertEqual(provider_thread["reasoning_effort"], "max")
            self.assertEqual(provider_thread["name"], "DeepSeek implementation")

    def test_minimal_visual_thread_name_is_compacted_for_new_provider_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            shell_root = workspace / ".astrabridge"
            (shell_root / "thread_cache.json").write_text(
                json.dumps(
                    {
                        "by_id": {
                            "thread-kimi-visual": {
                                "name": "AstraBridge minimal visual mode: Look only at these attached images and answer pass retry redraw",
                                "profile_id": "kimi-k2-6",
                                "provider_id": "kimi",
                                "model": "kimi/kimi-k2.6",
                                "reasoning_effort": "xhigh",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            task = TaskService(projects).ensure_default_task(thread_id="thread-kimi-visual")
            provider_thread = task["provider_threads"][0]

            self.assertEqual(provider_thread["model"], "kimi-k2.6")
            self.assertEqual(provider_thread["name"], "Kimi visual review")

    def test_auto_injected_context_suffix_is_trimmed_from_visible_thread_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            shell_root = workspace / ".astrabridge"
            (shell_root / "thread_cache.json").write_text(
                json.dumps(
                    {
                        "by_id": {
                            "thread-yunwu": {
                                "name": "Please audit the current workspace --- AstraBridge Project Context Pack (auto-injected, secret-free)",
                                "profile_id": "yunwu-default",
                                "provider_id": "yunwu",
                                "model": "gpt-5.5",
                                "reasoning_effort": "high",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            task = TaskService(projects).ensure_default_task(thread_id="thread-yunwu")
            provider_thread = task["provider_threads"][0]

            self.assertEqual(provider_thread["name"], "Please audit the current workspace")

    def test_provider_thread_matching_normalizes_model_and_effort_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Build game",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-v4-pro-max",
                    "provider_id": "deepseek",
                    "model": "deepseek/deepseek-v4-pro",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
            )

            match = tasks.find_provider_thread(
                profile_id="deepseek-v4-pro-max",
                model="deepseek-v4-pro",
                effort="max",
            )

            self.assertIsNotNone(match)
            self.assertEqual(match["thread_id"], "thread-deepseek")
            self.assertFalse(
                tasks.needs_provider_handoff(
                    thread_id="thread-deepseek",
                    profile_id="deepseek-v4-pro-max",
                    model="deepseek-v4-pro",
                    effort="max",
                )
            )

    def test_provider_thread_matching_can_fall_back_to_provider_id_and_skips_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Build game",
                thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-old-profile",
                    "provider_id": "kimi",
                    "model": "moonshot/kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
            )

            match = tasks.find_provider_thread(
                profile_id="kimi-new-profile",
                provider_id="kimi",
                model="kimi-k2.6",
                effort="xhigh",
            )

            self.assertIsNotNone(match)
            self.assertEqual(match["thread_id"], "thread-kimi")
            tasks.mark_provider_thread_missing("thread-kimi", reason="test_missing")
            self.assertIsNone(
                tasks.find_provider_thread(
                    profile_id="kimi-new-profile",
                    provider_id="kimi",
                    model="kimi-k2.6",
                    effort="xhigh",
                )
            )

    def test_runtime_reuses_existing_provider_thread_for_same_task_handoff(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    return {"thread": {"id": params.get("threadId")}}
                if method == "thread/fork":
                    raise AssertionError("Provider handoff should reuse existing thread instead of forking.")
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-openai",
                settings={
                    "profile_id": "openai-default",
                    "provider_id": "openai",
                    "model": "gpt-5.5",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-deepseek-existing",
                settings={
                    "profile_id": "deepseek-profile-old",
                    "provider_id": "deepseek",
                    "model": "deepseek/deepseek-v4-pro",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            client = FakeClient()

            thread_id, handoff = runtime._ensure_provider_thread_for_turn(  # noqa: SLF001
                client,
                source_thread_id="thread-openai",
                profile={"profile_id": "deepseek-profile-new", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
                collaboration_mode=None,
            )

            self.assertEqual(thread_id, "thread-deepseek-existing")
            self.assertTrue(handoff["reused_existing"])
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek-existing")
            self.assertEqual([method for method, _params in client.requests], ["thread/read"])

    def test_runtime_marks_missing_reusable_provider_thread_and_forks_once(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    if params.get("threadId") == "thread-openai":
                        return {"thread": {"id": "thread-openai"}}
                    raise JsonRpcError("thread not found")
                if method == "thread/start":
                    return {"thread": {"id": "thread-deepseek-fresh", "name": "Fresh DS"}}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-openai",
                settings={"profile_id": "openai", "provider_id": "openai", "model": "gpt-5.5", "reasoning_effort": "high"},
            )
            tasks.bind_thread(
                thread_id="thread-deepseek-missing",
                settings={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                make_active=False,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)

            thread_id, handoff = runtime._ensure_provider_thread_for_turn(  # noqa: SLF001
                FakeClient(),
                source_thread_id="thread-openai",
                profile={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
                collaboration_mode=None,
            )

            self.assertEqual(thread_id, "thread-deepseek-fresh")
            self.assertFalse(handoff["reused_existing"])
            task = tasks.current_task()
            missing = [item for item in task["provider_threads"] if item["thread_id"] == "thread-deepseek-missing"][0]
            self.assertEqual(missing["missing_reason"], "provider_handoff_target_missing")

    def test_runtime_archive_thread_reprojects_visible_task_thread(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.method = method
                self.params = params
                if method == "thread/archive":
                    return {"ok": True}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-active",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-fallback",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id", "deepseek")}  # type: ignore[method-assign]
            runtime._ensure_client = lambda runtime_status: FakeClient()  # type: ignore[method-assign]

            result = runtime.archive_thread({"provider_id": "deepseek"}, "thread-active")

            self.assertEqual(result["archived"], "thread-active")
            current = tasks.current_task()
            self.assertEqual(current["active_provider_thread_id"], "thread-fallback")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-fallback")
            archived = [item for item in current["provider_threads"] if item["thread_id"] == "thread-active"][0]
            self.assertEqual(archived["missing_reason"], "thread_archived")
            self.assertTrue(any(event.get("type") == "thread_archived" for event in runtime._events))

    def test_runtime_recovers_when_source_provider_thread_is_missing(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    raise JsonRpcError("thread not found")
                if method == "thread/start":
                    return {"thread": {"id": "thread-recovered", "name": "Recovered DS"}}
                if method == "thread/fork":
                    raise AssertionError("Missing source thread should recover with thread/start, not fork.")
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-stale",
                settings={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)

            thread_id, handoff = runtime._ensure_provider_thread_for_turn(  # noqa: SLF001
                FakeClient(),
                source_thread_id="thread-stale",
                profile={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
                collaboration_mode=None,
            )

            self.assertEqual(thread_id, "thread-recovered")
            self.assertFalse(handoff["reused_existing"])
            task = tasks.current_task()
            missing = [item for item in task["provider_threads"] if item["thread_id"] == "thread-stale"][0]
            self.assertEqual(missing["missing_reason"], "provider_handoff_source_missing")

    def test_task_title_update_and_missing_provider_thread_pruning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Old smoke title",
                thread_id="thread-openai",
                settings={"profile_id": "openai", "provider_id": "openai", "model": "gpt-5.5", "reasoning_effort": "high"},
            )

            renamed = tasks.update_current_task_title("Magic tower visual renderer dogfood")
            self.assertEqual(renamed["title"], "Magic tower visual renderer dogfood")

            for index in range(5):
                thread_id = f"thread-deepseek-missing-{index}"
                tasks.bind_thread(
                    thread_id=thread_id,
                    settings={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                    make_active=False,
                )
                tasks.mark_provider_thread_missing(thread_id, reason="test_missing")

            task = tasks.current_task()
            missing = [
                item
                for item in task["provider_threads"]
                if item.get("missing_at") and item.get("provider_id") == "deepseek" and item.get("model") == "deepseek-v4-pro"
            ]
            self.assertLessEqual(len(missing), 1)
            self.assertIn("Magic tower visual renderer dogfood", (workspace / ".astrabridge" / "tasks.json").read_text(encoding="utf-8"))

    def test_current_task_prunes_duplicate_live_provider_threads_by_canonical_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-deepseek-new",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-deepseek-old",
                settings={
                    "profile_id": "deepseek-legacy-profile",
                    "provider_id": "deepseek",
                    "model": "deepseek/deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            tasks.bind_thread(
                thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
                make_active=False,
            )

            current = tasks.current_task()

            deepseek_live = [
                item
                for item in current["provider_threads"]
                if not item.get("missing_at") and item.get("provider_id") == "deepseek"
            ]
            self.assertEqual([item["thread_id"] for item in deepseek_live], ["thread-deepseek-old"])
            self.assertEqual(len(current["provider_threads"]), 2)
            state_text = (workspace / ".astrabridge" / "tasks.json").read_text(encoding="utf-8")
            self.assertNotIn("thread-deepseek-new", state_text)

    def test_current_task_restores_active_provider_thread_from_latest_live_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-older-live",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-newer-live",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            state_path = workspace / ".astrabridge" / "tasks.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["tasks"][0]["active_provider_thread_id"] = None
            state_path.write_text(json.dumps(state), encoding="utf-8")
            projects.update_project({"current_thread_id": None})

            current = tasks.current_task()

            self.assertEqual(current["active_provider_thread_id"], "thread-newer-live")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-newer-live")

    def test_current_task_prefers_project_current_thread_when_it_is_live(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            state_path = workspace / ".astrabridge" / "tasks.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["tasks"][0]["active_provider_thread_id"] = "thread-missing"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            projects.update_project({"current_thread_id": "thread-kimi"})

            current = tasks.current_task()

            self.assertEqual(current["active_provider_thread_id"], "thread-kimi")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-kimi")

    def test_current_task_prefers_project_current_thread_even_when_old_active_thread_is_still_live(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Same task",
                thread_id="thread-deepseek-old",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-deepseek-visible",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            state_path = workspace / ".astrabridge" / "tasks.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["tasks"][0]["active_provider_thread_id"] = "thread-deepseek-old"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            projects.update_project({"current_task_id": task["task_id"], "current_thread_id": "thread-deepseek-visible"})

            current = tasks.current_task()

            self.assertEqual(current["active_provider_thread_id"], "thread-deepseek-visible")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek-visible")

    def test_active_provider_thread_can_fallback_to_latest_missing_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-deepseek-stale",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.mark_provider_thread_missing("thread-deepseek-stale", reason="startup_thread_missing")

            current = tasks.current_task()
            self.assertEqual(current["active_provider_thread_id"], "thread-deepseek-stale")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek-stale")
            fallback = tasks.active_provider_thread(include_missing_fallback=True)

            self.assertEqual(fallback["thread_id"], "thread-deepseek-stale")
            self.assertEqual(fallback["profile_id"], "deepseek-default")
            self.assertEqual(fallback["missing_reason"], "startup_thread_missing")

    def test_current_task_restores_latest_missing_provider_thread_when_no_live_threads_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-deepseek-older",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.mark_provider_thread_missing("thread-deepseek-older", reason="startup_thread_missing")
            tasks.bind_thread(
                thread_id="thread-kimi-newer",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            tasks.mark_provider_thread_missing("thread-kimi-newer", reason="startup_thread_missing")
            state_path = workspace / ".astrabridge" / "tasks.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["tasks"][0]["active_provider_thread_id"] = None
            state_path.write_text(json.dumps(state), encoding="utf-8")
            projects.update_project({"current_thread_id": None})

            current = tasks.current_task()

            self.assertEqual(current["active_provider_thread_id"], "thread-kimi-newer")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-kimi-newer")

    def test_current_task_resyncs_project_current_thread_even_when_task_state_is_already_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            projects.update_project({"current_thread_id": None})

            current = tasks.current_task()

            self.assertEqual(current["active_provider_thread_id"], "thread-deepseek")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek")

    def test_task_service_reconcile_after_project_reload_restores_current_task_from_visible_thread(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            first = tasks.create_task(
                "DeepSeek task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            second = tasks.create_task(
                "Kimi task",
                thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
            )
            state_path = workspace / ".astrabridge" / "tasks.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["current_task_id"] = None
            state_path.write_text(json.dumps(state), encoding="utf-8")
            projects.update_project({"current_task_id": None, "current_thread_id": "thread-deepseek"})

            reconciled = tasks.reconcile_after_project_reload(preferred_thread_id="thread-deepseek")

            self.assertEqual(reconciled["task_id"], first["task_id"])
            self.assertEqual(projects.current_project["current_task_id"], first["task_id"])
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek")
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["current_task_id"], first["task_id"])
            self.assertNotEqual(second["task_id"], first["task_id"])

    def test_task_service_reconcile_after_project_reload_dedupes_checkpoint_and_context_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            task = tasks.create_task(
                "DeepSeek task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            state_path = workspace / ".astrabridge" / "tasks.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["tasks"][0]["checkpoint_refs"] = [
                {"save_id": "save-1", "description": "A"},
                {"save_id": "save-1", "description": "A duplicate"},
                {"save_id": "save-2", "description": "B"},
            ]
            state["tasks"][0]["context_pack_refs"] = [
                {"pack_type": "project", "path": "a.json", "generated_at": "1"},
                {"pack_type": "project", "path": "a.json", "generated_at": "2"},
            ]
            state["tasks"][0]["asset_context_refs"] = [
                {"pack_type": "asset", "path": "asset.json", "generated_at": "1"},
                {"pack_type": "asset", "path": "asset.json", "generated_at": "2"},
            ]
            state["tasks"][0]["fork_threads"] = [
                {"thread_id": "fork-1"},
                {"thread_id": "fork-1"},
                {"thread_id": "fork-2"},
            ]
            state_path.write_text(json.dumps(state), encoding="utf-8")
            projects.update_project({"current_task_id": task["task_id"], "current_thread_id": "thread-deepseek"})

            reconciled = tasks.reconcile_after_project_reload(preferred_thread_id="thread-deepseek")

            self.assertEqual([item["save_id"] for item in reconciled["checkpoint_refs"]], ["save-1", "save-2"])
            self.assertEqual(len(reconciled["context_pack_refs"]), 1)
            self.assertEqual(len(reconciled["asset_context_refs"]), 1)
            self.assertEqual([item["thread_id"] for item in reconciled["fork_threads"]], ["fork-1", "fork-2"])

    def test_runtime_ensure_client_restarts_running_client_when_signature_changes(self) -> None:
        class FakeRuntimeConfig:
            def prepare_profile(self, profile: dict[str, object], *, require_secret: bool) -> dict[str, object]:  # noqa: ARG002
                return {"profile_id": profile.get("profile_id"), "provider_id": profile.get("provider_id")}

            def runtime_signature(self, status: dict[str, object]) -> tuple[object, ...]:
                return (status.get("provider_id"),)

        class ExistingClient:
            def __init__(self) -> None:
                self.closed = False

            def is_running(self) -> bool:
                return not self.closed

            def close(self) -> None:
                self.closed = True

        class FakeAppServerClient:
            instances: list["FakeAppServerClient"] = []

            def __init__(self, **_kwargs: object) -> None:
                self.started = False
                self.closed = False
                FakeAppServerClient.instances.append(self)

            def start(self) -> None:
                self.started = True

            def is_running(self) -> bool:
                return self.started and not self.closed

            def close(self) -> None:
                self.closed = True

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                runtime_config=FakeRuntimeConfig(),  # type: ignore[arg-type]
            )
            existing = ExistingClient()
            runtime._client = existing  # type: ignore[assignment]
            runtime._runtime_signature = ("deepseek",)
            runtime._resolve_launch_target = lambda _status: {  # type: ignore[method-assign]
                "codex_executable": "codex",
                "launch_command": ["codex"],
                "cwd": workspace,
                "env_updates": {},
            }

            with patch.object(runtime_service_module, "AppServerClient", FakeAppServerClient):
                client = runtime._ensure_client({"provider_id": "kimi"})

            self.assertTrue(existing.closed)
            self.assertIs(client, FakeAppServerClient.instances[-1])
            self.assertEqual(runtime._runtime_signature, ("kimi",))
            self.assertTrue(
                any(
                    event.get("type") == "runtime_stopped" and event.get("reason") == "runtime_signature_mismatch"
                    for event in runtime.list_events()["events"]
                )
            )

    def test_runtime_thread_list_defers_provider_switch_while_turn_runtime_is_pinned(self) -> None:
        class FakeRuntimeConfig:
            def prepare_profile(self, profile: dict[str, object], *, require_secret: bool) -> dict[str, object]:  # noqa: ARG002
                return {"profile_id": profile.get("profile_id"), "provider_id": profile.get("provider_id")}

            def runtime_signature(self, status: dict[str, object]) -> tuple[object, ...]:
                return (status.get("provider_id"),)

        class ExistingClient:
            def __init__(self) -> None:
                self.closed = False

            def is_running(self) -> bool:
                return not self.closed

            def close(self) -> None:
                self.closed = True

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            projects.cache_threads([{"id": "thread-kimi", "name": "Kimi visual turn", "turns": []}])
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                runtime_config=FakeRuntimeConfig(),  # type: ignore[arg-type]
            )
            existing = ExistingClient()
            runtime._client = existing  # type: ignore[assignment]
            runtime._runtime_signature = ("kimi",)
            runtime._runtime_pin_signature = ("kimi",)
            runtime._runtime_pin_until_monotonic = time.monotonic() + 60
            runtime._runtime_pin_thread_id = "thread-kimi"
            runtime._runtime_pin_turn_id = "turn-kimi"

            result = runtime.list_threads({"profile_id": "deepseek", "provider_id": "deepseek"})

            self.assertFalse(existing.closed)
            self.assertEqual(result["threads"][0]["id"], "thread-kimi")
            self.assertTrue(
                any(event.get("type") == "threads_list_deferred_active_turn" for event in runtime.list_events()["events"])
            )

    def test_runtime_thread_list_uses_active_runtime_during_thread_create_mutation(self) -> None:
        class FakeRuntimeConfig:
            def __init__(self) -> None:
                self.prepare_calls = 0

            def prepare_profile(self, profile: dict[str, object], *, require_secret: bool) -> dict[str, object]:  # noqa: ARG002
                self.prepare_calls += 1
                return {"profile_id": profile.get("profile_id"), "provider_id": profile.get("provider_id")}

            def runtime_signature(self, status: dict[str, object]) -> tuple[object, ...]:
                return (status.get("provider_id"),)

            def status(self) -> dict[str, object]:
                return {
                    "configured": True,
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "provider_name": "Qwen / DashScope",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen3.7-plus",
                    "reasoning_effort": "high",
                    "wire_api": "responses",
                    "env_key": "DASHSCOPE_API_KEY",
                    "secret_loaded": True,
                    "proxy_mode": "direct",
                    "proxy_url": "",
                    "secret_source": "environment",
                    "secret_fingerprint": "fingerprint",
                }

        class ExistingClient:
            def __init__(self) -> None:
                self.closed = False
                self.requests: list[tuple[str, dict[str, object]]] = []

            def is_running(self) -> bool:
                return not self.closed

            def close(self) -> None:
                self.closed = True

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:  # noqa: ARG002
                self.requests.append((method, params))
                if method == "thread/list":
                    return {"data": [{"id": "thread-qwen", "name": "Qwen active thread", "updatedAt": "2026-06-21T20:00:00+08:00"}]}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime_config = FakeRuntimeConfig()
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                runtime_config=runtime_config,  # type: ignore[arg-type]
            )
            existing = ExistingClient()
            runtime._client = existing  # type: ignore[assignment]
            runtime._runtime_signature = ("qwen",)
            runtime._runtime_thread_start_in_progress = True

            result = runtime.list_threads({"profile_id": "openai-compatible", "provider_id": "openai"})

            self.assertFalse(existing.closed)
            self.assertEqual(runtime_config.prepare_calls, 0)
            self.assertEqual(result["threads"][0]["id"], "thread-qwen")
            self.assertEqual(existing.requests[0][0], "thread/list")
            self.assertTrue(
                any(event.get("type") == "runtime_switch_deferred_active_mutation" for event in runtime.list_events()["events"])
            )

    def test_runtime_request_client_retries_one_transport_disconnect(self) -> None:
        class FakeClient:
            def __init__(self, generation: int) -> None:
                self.generation = generation
                self.requests: list[tuple[str, dict[str, object], float | None]] = []

            def is_running(self) -> bool:
                return True

            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, dict(params or {}), timeout))
                if self.generation == 1:
                    raise RuntimeError("codex_app_server_not_running")
                return {"ok": True, "generation": self.generation}

        class FakeRuntime:
            def __init__(self) -> None:
                self.ensure_count = 0
                self.closed_reasons: list[str] = []
                self.events: list[dict[str, object]] = []

            def _ensure_client(self, _runtime_status: dict[str, object]) -> FakeClient:
                self.ensure_count += 1
                return FakeClient(self.ensure_count)

            def _is_app_server_transport_error(self, exc: RuntimeError) -> bool:
                return "codex_app_server_not_running" in str(exc)

            def _record_event(self, event: dict[str, object]) -> None:
                self.events.append(event)

            def _close_client(self, reason: str) -> None:
                self.closed_reasons.append(reason)

        runtime = FakeRuntime()
        client = runtime_service_module._RuntimeRequestClient(runtime, {"provider_id": "kimi"})  # type: ignore[arg-type]

        result = client.request("thread/read", {"threadId": "thread-kimi"}, timeout=3)

        self.assertEqual(result, {"ok": True, "generation": 2})
        self.assertEqual(runtime.ensure_count, 2)
        self.assertEqual(runtime.closed_reasons, ["thread/read_transport_retry"])
        self.assertEqual(runtime.events[0]["type"], "runtime_request_transport_retry")
        self.assertEqual(runtime.events[0]["thread_id"], "thread-kimi")

    def test_start_turn_timeout_returns_background_pending_response(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    return {"thread": {"id": params.get("threadId")}}
                if method == "turn/start":
                    raise TimeoutError("slow provider")
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            projects.switch_thread("thread-deepseek")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
            )
            client = FakeClient()
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: client  # type: ignore[method-assign]  # noqa: ARG005

            result = runtime.start_turn(
                {"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                thread_id="thread-deepseek",
                text="Continue.",
                attachments=[],
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
            )

            self.assertTrue(result["background_start"])
            self.assertEqual(result["thread_id"], "thread-deepseek")
            self.assertTrue(result["turn"]["synthetic"])
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek")
            self.assertIn("turn/start", [method for method, _params in client.requests])
            self.assertEqual(runtime.list_events()["events"][-1]["type"], "turn_start_background_pending")

    def test_start_turn_can_recover_visible_task_thread_when_project_pointer_is_empty(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    return {"thread": {"id": params.get("threadId")}}
                if method == "turn/start":
                    return {"turn": {"id": "turn-ok"}}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
            )
            projects.update_project({"current_thread_id": None})
            client = FakeClient()
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: client  # type: ignore[method-assign]  # noqa: ARG005

            result = runtime.start_turn(
                {"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                thread_id="",
                text="Continue.",
                attachments=[],
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
            )

            self.assertEqual(result["thread_id"], "thread-deepseek")
            self.assertEqual(result["turn"]["id"], "turn-ok")
            self.assertTrue(any(method == "thread/read" and params.get("threadId") == "thread-deepseek" for method, params in client.requests))
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek")

    def test_start_turn_health_check_uses_fresh_minimal_thread(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/start":
                    return {"thread": {"id": "thread-health", "name": "Health Check"}}
                if method == "turn/start":
                    return {"turn": {"id": "turn-health"}}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            projects.switch_thread("thread-hot")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-hot",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            client = FakeClient()
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: client  # type: ignore[method-assign]  # noqa: ARG005
            runtime._events = [
                {
                    "type": "notification",
                    "method": "thread/tokenUsage/updated",
                    "timestamp": "2026-06-16T00:00:01+00:00",
                    "params": {
                        "threadId": "thread-hot",
                        "turnId": "turn-hot",
                        "tokenUsage": {"total": {"totalTokens": 95}, "modelContextWindow": 100},
                    },
                }
            ]

            result = runtime.start_turn(
                {"profile_id": "deepseek-default", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "high"},
                thread_id="thread-hot",
                text="Reply exactly: ok",
                attachments=[],
                model="deepseek-v4-pro",
                effort="high",
                permission_mode="auto",
                context_mode="health_check",
            )

            self.assertEqual(result["thread_id"], "thread-health")
            self.assertEqual(result["turn"]["id"], "turn-health")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-health")
            self.assertEqual([method for method, _params in client.requests], ["thread/start", "turn/start"])
            self.assertTrue(
                any(
                    event.get("type") == "provider_handoff"
                    and event.get("reason") == "minimal_text_fresh_thread"
                    for event in runtime.list_events()["events"]
                )
            )

    def test_start_turn_minimal_visual_uses_fresh_thread_when_reviewer_thread_is_hot(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    return {"thread": {"id": params.get("threadId")}}
                if method == "thread/start":
                    return {"thread": {"id": "thread-kimi-fresh", "name": "Fresh visual reviewer"}}
                if method == "turn/start":
                    return {"turn": {"id": "turn-kimi-visual"}}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            fake_image = workspace / "fake.png"
            fake_image.write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sWmB1EAAAAASUVORK5CYII="
                )
            )
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            projects.switch_thread("thread-kimi-hot")
            tasks = TaskService(projects)
            tasks.create_task(
                "Visual review task",
                thread_id="thread-kimi-hot",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
            )
            client = FakeClient()
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: client  # type: ignore[method-assign]  # noqa: ARG005
            runtime._events = [
                {
                    "type": "notification",
                    "method": "thread/tokenUsage/updated",
                    "timestamp": "2026-06-16T00:00:01+00:00",
                    "params": {
                        "threadId": "thread-kimi-hot",
                        "turnId": "turn-hot",
                        "tokenUsage": {"total": {"totalTokens": 95}, "modelContextWindow": 100},
                    },
                }
            ]

            result = runtime.start_turn(
                {"profile_id": "kimi-default", "provider_id": "kimi", "model": "kimi-k2.6", "reasoning_effort": "xhigh"},
                thread_id="thread-kimi-hot",
                text="Review this screenshot only.",
                attachments=[{"path": str(fake_image), "name": "fake.png", "mime_type": "image/png"}],
                model="kimi-k2.6",
                effort="xhigh",
                permission_mode="auto",
                context_mode="minimal_visual",
            )

            self.assertEqual(result["thread_id"], "thread-kimi-fresh")
            self.assertEqual(result["turn"]["id"], "turn-kimi-visual")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-kimi-fresh")
            self.assertEqual([method for method, _params in client.requests].count("thread/start"), 1)
            self.assertTrue(
                any(
                    event.get("type") == "provider_handoff"
                    and event.get("reason") in {"minimal_visual_hot_thread", "minimal_visual_fresh_thread"}
                    for event in runtime.list_events()["events"]
                )
            )

    def test_start_turn_missing_thread_recovery_timeout_returns_background_pending_response(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    raise JsonRpcError("thread not found")
                if method == "thread/start":
                    return {"thread": {"id": "thread-recovered", "name": "Recovered DS"}}
                if method == "turn/start":
                    raise TimeoutError("slow recovered provider")
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            projects.switch_thread("thread-stale")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-stale",
                settings={
                    "profile_id": "deepseek",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
            )
            client = FakeClient()
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: client  # type: ignore[method-assign]  # noqa: ARG005

            result = runtime.start_turn(
                {"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                thread_id="thread-stale",
                text="Continue.",
                attachments=[],
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
            )

            self.assertTrue(result["background_start"])
            self.assertEqual(result["thread_id"], "thread-recovered")
            self.assertTrue(result["turn"]["synthetic"])
            self.assertIn("thread/start", [method for method, _params in client.requests])
            self.assertEqual(runtime.list_events()["events"][-1]["type"], "turn_start_background_pending")

    def test_load_secret_updates_project_runtime_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            key_file = root / "dashscope.txt"
            key_file.write_text("sk-test-dashscope-demo-key", encoding="utf-8")
            projects = ProjectService(root / "recent.json")
            project = projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))

            status = runtime.load_secret(
                {
                    "profile_id": "qwen-default",
                    "label": "Qwen / DashScope",
                    "provider_id": "qwen",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen3.7-plus",
                    "reasoning_effort": "high",
                    "wire_api": "responses",
                    "env_key": "DASHSCOPE_API_KEY",
                    "auth_mode": "env_ref",
                },
                key_file_path=str(key_file),
            )

            self.assertTrue(status["secret_loaded"])
            updated = projects.current_project or {}
            self.assertEqual(updated.get("default_profile_id"), "qwen-default")
            self.assertEqual(updated.get("default_model"), "qwen3.7-plus")
            self.assertEqual(updated.get("default_effort"), "high")

    def test_start_turn_recovers_when_app_server_reports_thread_not_loaded(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    return {"thread": {"id": params.get("threadId")}}
                if method == "thread/start":
                    return {"thread": {"id": "thread-recovered", "name": "Recovered DS"}}
                if method == "turn/start":
                    if params.get("threadId") == "thread-stale":
                        raise JsonRpcError("thread not loaded: thread-stale")
                    return {"turn": {"id": "turn-recovered"}}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            projects.switch_thread("thread-stale")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-stale",
                settings={
                    "profile_id": "deepseek",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
            )
            client = FakeClient()
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"provider_id": profile.get("provider_id")}  # type: ignore[method-assign]  # noqa: ARG005
            runtime._ensure_client = lambda runtime_status: client  # type: ignore[method-assign]  # noqa: ARG005

            result = runtime.start_turn(
                {"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                thread_id="thread-stale",
                text="Continue.",
                attachments=[],
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
            )

            self.assertEqual(result["thread_id"], "thread-recovered")
            self.assertEqual(result["turn"]["id"], "turn-recovered")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-recovered")
            self.assertEqual([method for method, _params in client.requests].count("turn/start"), 2)
            self.assertTrue(any(event.get("type") == "provider_thread_recovered" for event in runtime.list_events()["events"]))

    def test_runtime_thread_cache_write_failure_is_non_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            original_write_json = runtime_service_module.write_json
            runtime_service_module.write_json = lambda _path, _payload: (_ for _ in ()).throw(PermissionError("cache locked"))  # type: ignore[assignment]
            try:
                runtime._cache_thread_entry("thread-a", {"name": "Thread A"})  # noqa: SLF001
            finally:
                runtime_service_module.write_json = original_write_json  # type: ignore[assignment]

            self.assertEqual(runtime.list_events()["events"][-1]["type"], "thread_cache_write_failed")

    def test_turn_text_from_payload_accepts_prompt_alias(self) -> None:
        self.assertEqual(turn_text_from_payload({"text": "Use text", "prompt": "Ignore prompt"}), "Use text")
        self.assertEqual(turn_text_from_payload({"prompt": "Use prompt"}), "Use prompt")
        self.assertEqual(turn_text_from_payload({"message": "Use message"}), "Use message")
        self.assertEqual(turn_text_from_payload({"text": "", "prompt": "Ignored because text is explicit"}), "")
        self.assertEqual(turn_text_from_payload({}), "")

    def test_sse_frame_formats_event_data_and_comment(self) -> None:
        event_frame = sse_frame(event="lcr.event", data={"cursor": 3, "message": "状态更新"}, retry=2000).decode("utf-8")
        self.assertIn("retry: 2000\n", event_frame)
        self.assertIn("event: lcr.event\n", event_frame)
        self.assertIn('data: {"cursor": 3, "message": "状态更新"}\n', event_frame)
        self.assertTrue(event_frame.endswith("\n\n"))

        heartbeat = sse_frame(comment="heartbeat cursor=3").decode("utf-8")
        self.assertEqual(heartbeat, ": heartbeat cursor=3\n\n")

    def test_runtime_thread_start_registers_yunwu_dynamic_tools_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._mcp_config.enabled_servers = lambda: [{"name": "yunwu_image", "enabled": True}]  # type: ignore[method-assign]

            params = runtime._thread_start_params(  # noqa: SLF001
                profile={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro"},
                model="deepseek-v4-pro",
                permission_mode="auto",
            )

            names = {tool["name"] for tool in params["dynamicTools"]}
            self.assertIn("yunwu_image_generate", names)
            self.assertIn("yunwu_image_transparent_asset", names)
            self.assertIn("yunwu_image_edit", names)

    def test_runtime_thread_start_registers_lcr_web_dynamic_tools_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._mcp_config.enabled_servers = lambda: [{"name": "lcr_web", "enabled": True}]  # type: ignore[method-assign]

            params = runtime._thread_start_params(  # noqa: SLF001
                profile={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro"},
                model="deepseek-v4-pro",
                permission_mode="auto",
            )

            names = {tool["name"] for tool in params["dynamicTools"]}
            self.assertIn("lcr_web_search_batch", names)
            self.assertIn("lcr_web_research_brief", names)
            self.assertIn("lcr_web_search", names)
            self.assertIn("lcr_web_fetch", names)
            self.assertNotIn("yunwu_image_generate", names)

    def test_runtime_thread_start_registers_browser_smoke_dynamic_tool_for_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                dogfood_run=DogfoodRunService(projects),
            )

            params = runtime._thread_start_params(  # noqa: SLF001
                profile={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro"},
                model="deepseek-v4-pro",
                permission_mode="auto",
            )

            names = {tool["name"] for tool in params["dynamicTools"]}
            self.assertIn("lcr_browser_smoke", names)
            smoke_tool = [tool for tool in params["dynamicTools"] if tool["name"] == "lcr_browser_smoke"][0]
            self.assertEqual(smoke_tool["inputSchema"]["properties"]["actions"]["maxItems"], 80)
            self.assertIn("file:///mnt/d", smoke_tool["description"])
            self.assertIn("do not start an ad-hoc HTTP server", smoke_tool["description"])
            action_types = smoke_tool["inputSchema"]["properties"]["actions"]["items"]["properties"]["type"]["enum"]
            self.assertIn("click_text_until_absent", action_types)
            self.assertIn("wait_for_text_absent", action_types)
            self.assertIn("max_clicks", smoke_tool["inputSchema"]["properties"]["actions"]["items"]["properties"])

    def test_runtime_thread_start_registers_browser_smoke_even_before_project_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            projects = ProjectService(root / "recent.json")
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                dogfood_run=DogfoodRunService(projects),
            )

            tools = runtime._lcr_dynamic_tools()  # noqa: SLF001

            names = {tool["name"] for tool in tools}
            self.assertIn("lcr_browser_smoke", names)

    def test_runtime_dynamic_yunwu_tool_call_returns_app_server_content_items(self) -> None:
        class FakeYunwuImage:
            def transparent_asset(self, **kwargs: object) -> dict[str, object]:
                return {
                    "created": 123,
                    "requested_n": kwargs.get("n"),
                    "actual_n": 1,
                    "count_mismatch": False,
                    "asset_manifest_path": str(Path(str(kwargs["workspace_root"])) / ".astrabridge" / "assets" / "generated" / "asset_manifest.json"),
                    "data": [
                        {
                            "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",
                            "asset_id": "yunwu-test",
                            "local_path": str(Path(str(kwargs["workspace_root"])) / ".astrabridge" / "assets" / "generated" / "yunwu-test.png"),
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
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._mcp_config.enabled_servers = lambda: [{"name": "yunwu_image", "enabled": True}]  # type: ignore[method-assign]
            runtime._yunwu_image = FakeYunwuImage()  # type: ignore[assignment]

            result = runtime._on_server_request(  # noqa: SLF001
                "item/tool/call",
                {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "tool": "yunwu_image_transparent_asset",
                    "arguments": {"prompt": "single transparent key", "n": 1},
                },
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["contentItems"][0]["type"], "inputText")
            self.assertIn("yunwu-test", result["contentItems"][0]["text"])
            self.assertIn("b64_json_present", result["contentItems"][0]["text"])
            self.assertIn("tool_context", result["contentItems"][0]["text"])
            self.assertIn("yunwu_image_transparent_asset", result["contentItems"][0]["text"])
            self.assertNotIn("iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB", result["contentItems"][0]["text"])
            self.assertEqual(runtime.list_events()["events"][-1]["type"], "dynamic_tool_called")
            event_payload = json.dumps(runtime.list_events()["events"][-1], ensure_ascii=False)
            self.assertIn('"server": "yunwu_image"', event_payload)
            self.assertIn("b64_json_present", event_payload)
            self.assertIn("tool_context", event_payload)
            self.assertNotIn("iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB", event_payload)

    def test_runtime_dynamic_lcr_web_tool_call_returns_research_brief_content(self) -> None:
        captured_arguments: dict[str, object] = {}

        class FakeLcrWeb:
            def research_brief(self, arguments: dict[str, object]) -> dict[str, object]:
                captured_arguments.update(arguments)
                return {
                    "ok": True,
                    "record_id": "research-1",
                    "tool_event_verified": True,
                    "path": "D:/workspace/.astrabridge/research/research-1.json",
                    "result": {
                        "tool": "lcr_web_research_brief",
                        "research_goal": arguments.get("research_goal"),
                        "sources": [{"url": "https://example.com/autotile", "title": "Autotile"}],
                        "citation_rule": "Use only URLs in sources.",
                    },
                }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(
                thread_id="thread-1",
                title="Magic Tower",
                settings={
                    "profile_id": "deepseek-v4",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
            )
            tasks.record_goal("thread-1", {"objective": "Build a three-floor magical tower game"})
            tasks.record_plan(
                "thread-1",
                {
                    "steps": [
                        {"step": "Research top-down JRPG map rendering", "status": "completed"},
                        {"step": "Implement free meadow background plus collision overlays", "status": "in_progress"},
                    ]
                },
            )
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                task_service=tasks,
                lcr_web_service=FakeLcrWeb(),
            )
            runtime._mcp_config.enabled_servers = lambda: [{"name": "lcr_web", "enabled": True}]  # type: ignore[method-assign]

            result = runtime._on_server_request(  # noqa: SLF001
                "item/tool/call",
                {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "tool": "lcr_web_research_brief",
                    "arguments": {"research_goal": "RPG autotile map visual design"},
                },
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["contentItems"][0]["type"], "inputText")
            text = result["contentItems"][0]["text"]
            self.assertIn("lcr_web_research_brief", text)
            self.assertIn("https://example.com/autotile", text)
            self.assertIn("tool_event_verified", text)
            event_payload = json.dumps(runtime.list_events()["events"][-1], ensure_ascii=False)
            self.assertIn("dynamic_tool_called", event_payload)
            self.assertIn('"server": "lcr_web"', event_payload)
            self.assertIn("https://example.com/autotile", event_payload)
            context = dict(captured_arguments.get("tool_context") or {})
            self.assertEqual(context["tool_name"], "lcr_web_research_brief")
            self.assertEqual(context["task_goal"], "Build a three-floor magical tower game")
            self.assertEqual(context["current_plan_step"], "Implement free meadow background plus collision overlays")
            self.assertEqual(context["selected_provider"], "deepseek")
            self.assertEqual(context["selected_model"], "deepseek-v4-pro")
            self.assertIn("Do not include raw .astrabridge/runtime_events.jsonl.", context["forbidden_inputs"])
            self.assertIn("tool_context", event_payload)

    def test_runtime_dynamic_lcr_web_search_alias_preserves_default_tool_context(self) -> None:
        captured_arguments: dict[str, object] = {}

        class FakeLcrWeb:
            def search_batch(self, arguments: dict[str, object]) -> dict[str, object]:
                captured_arguments.update(arguments)
                return {
                    "ok": True,
                    "record_id": "search-1",
                    "tool_event_verified": True,
                    "path": "D:/workspace/.astrabridge/research/search-1.json",
                    "result": {
                        "tool": "lcr_web_search_batch",
                        "merged_results": [{"url": "https://example.com/tilemap", "title": "Tilemap"}],
                    },
                }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(thread_id="thread-1", title="Magic Tower", settings={"provider_id": "deepseek", "model": "deepseek-v4-pro"})
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                task_service=tasks,
                lcr_web_service=FakeLcrWeb(),
            )
            runtime._mcp_config.enabled_servers = lambda: [{"name": "lcr_web", "enabled": True}]  # type: ignore[method-assign]

            result = runtime._on_server_request(  # noqa: SLF001
                "item/tool/call",
                {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "tool": "lcr_web_search",
                    "arguments": {"query": "JRPG meadow map overlay collision"},
                },
            )

            self.assertTrue(result["success"])
            context = dict(captured_arguments.get("tool_context") or {})
            self.assertEqual(context["tool_name"], "lcr_web_search")
            self.assertEqual(context["workspace_root"], str(workspace))
            self.assertEqual(context["selected_provider"], "deepseek")
            self.assertEqual(captured_arguments["queries"], [{"query": "JRPG meadow map overlay collision", "max_results": 5}])
            self.assertIn("tool_context", result["contentItems"][0]["text"])

    def test_runtime_dynamic_browser_smoke_tool_call_returns_evidence(self) -> None:
        class FakeDogfood:
            def browser_smoke(self, payload: dict[str, object]) -> dict[str, object]:
                return {
                    "path": "D:/workspace/.astrabridge/dogfood_run.json",
                    "browser_smoke": {
                        "label": payload.get("label"),
                        "url": payload.get("url"),
                        "status": "pass",
                        "http_status": 200,
                        "screenshot_path": "D:/workspace/.astrabridge/captures/smoke.png",
                        "screenshot_status": "captured",
                        "console_errors": [],
                    },
                }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                dogfood_run=FakeDogfood(),
            )

            result = runtime._on_server_request(  # noqa: SLF001
                "item/tool/call",
                {
                    "threadId": "thread-1",
                    "turnId": "turn-1",
                    "tool": "lcr_browser_smoke",
                    "arguments": {"url": "http://127.0.0.1:8123/", "label": "map smoke"},
                },
            )

            self.assertTrue(result["success"])
            text = result["contentItems"][0]["text"]
            self.assertIn("lcr_browser_smoke", text)
            self.assertIn("D:/workspace/.astrabridge/captures/smoke.png", text)
            self.assertIn("tool_context", text)
            event_payload = json.dumps(runtime.list_events()["events"][-1], ensure_ascii=False)
            self.assertIn('"server": "lcr_browser"', event_payload)
            self.assertIn("tool_event_verified", event_payload)
            self.assertIn("lcr_browser_smoke", event_payload)
            self.assertIn("tool_context", event_payload)

    def test_runtime_read_thread_overlays_dynamic_tool_items_from_events(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {"type": "agentMessage", "id": "agent-1", "text": "done"},
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]
            runtime._record_event(
                {
                    "type": "notification",
                    "method": "item/started",
                    "params": {
                        "threadId": "thread-1",
                        "turnId": "turn-1",
                        "item": {
                            "type": "dynamicToolCall",
                            "id": "tool-1",
                            "tool": "lcr_web_search_batch",
                            "arguments": {"queries": [{"query": "autotile"}]},
                            "status": "inProgress",
                        },
                    },
                }
            )
            runtime._record_event(
                {
                    "type": "notification",
                    "method": "item/completed",
                    "params": {
                        "threadId": "thread-1",
                        "turnId": "turn-1",
                        "item": {
                            "type": "dynamicToolCall",
                            "id": "tool-1",
                            "tool": "lcr_web_search_batch",
                            "arguments": {"queries": [{"query": "autotile"}]},
                            "status": "completed",
                            "contentItems": [{"type": "inputText", "text": "tool_event_verified=true"}],
                            "success": True,
                        },
                    },
                }
            )

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            items = result["thread"]["turns"][0]["items"]
            self.assertEqual([item["type"] for item in items], ["userMessage", "dynamicToolCall", "agentMessage"])
            self.assertEqual(items[1]["tool"], "lcr_web_search_batch")
            self.assertEqual(items[1]["status"], "completed")
            self.assertIn("tool_event_verified", items[1]["contentItems"][0]["text"])
            self.assertTrue(items[1]["lcrVerifiedEvidence"]["verified"])
            self.assertEqual(items[1]["lcrVerifiedEvidence"]["server"], "lcr_web")
            self.assertIn("tool-event verified", items[1]["lcrVerifiedEvidence"]["label"])

    def test_runtime_read_thread_records_task_conversation_snapshot(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-deepseek",
                            "name": "DeepSeek lane",
                            "status": {"type": "idle"},
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "startedAt": 1,
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "text": "Keep the same visible chat."},
                                        {"type": "agentMessage", "id": "agent-1", "text": "Done."},
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Visible task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
            )
            conversation = TaskConversationService(projects, tasks)
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                task_service=tasks,
                task_conversation=conversation,
            )
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "deepseek"}  # type: ignore[method-assign]

            runtime.read_thread({"profile_id": "deepseek-default", "provider_id": "deepseek"}, "thread-deepseek")
            composite = conversation.conversation(task_id=task["task_id"])["thread"]

            self.assertEqual(composite["id"], f"task:{task['task_id']}")
            self.assertEqual(composite["turns"][0]["provider_id"], "deepseek")
            self.assertEqual(composite["turns"][0]["items"][0]["provider_id"], "deepseek")

    def test_runtime_read_thread_decorates_existing_dynamic_tool_evidence(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {
                                            "type": "dynamicToolCall",
                                            "id": "tool-1",
                                            "tool": "lcr_browser_smoke",
                                            "status": "completed",
                                            "contentItems": [
                                                {
                                                    "type": "inputText",
                                                    "text": "AstraBridge dynamic tool result for lcr_browser_smoke:\n"
                                                    + json.dumps(
                                                        {
                                                            "tool": "lcr_browser_smoke",
                                                            "label": "map smoke",
                                                            "status": "pass",
                                                            "screenshot_path": "D:/workspace/.astrabridge/captures/map.png",
                                                            "console_errors": [],
                                                            "tool_event_verified": True,
                                                        }
                                                    ),
                                                }
                                            ],
                                        },
                                        {"type": "agentMessage", "id": "agent-1", "text": "done"},
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            item = result["thread"]["turns"][0]["items"][1]
            evidence = item["lcrVerifiedEvidence"]
            self.assertTrue(evidence["verified"])
            self.assertEqual(evidence["tool"], "lcr_browser_smoke")
            self.assertEqual(evidence["server"], "lcr_browser")
            self.assertIn("D:/workspace/.astrabridge/captures/map.png", evidence["paths"])
            self.assertTrue(any("browser smoke map smoke pass" in line for line in evidence["summary"]))

    def test_runtime_read_thread_normalizes_stale_system_error_after_completed_turn(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "status": {"type": "systemError"},
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "status": "completed",
                                    "error": None,
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {"type": "agentMessage", "id": "assistant-1", "text": "done"},
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            self.assertEqual(result["thread"]["status"]["type"], "idle")
            self.assertTrue(result["thread"]["status"]["stale_error_normalized"])
            self.assertEqual(result["thread"]["status"]["stale_error_type"], "systemError")

            cache = json.loads((projects.require_shell_state_root() / "thread_cache.json").read_text(encoding="utf-8"))
            self.assertEqual(cache["by_id"]["thread-1"]["status"]["type"], "idle")
            self.assertTrue(cache["by_id"]["thread-1"]["status"]["stale_error_normalized"])
            self.assertEqual(cache["by_id"]["thread-1"]["status"]["stale_error_type"], "systemError")

    def test_runtime_read_thread_normalizes_stale_not_loaded_after_completed_turn(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "status": {"type": "notLoaded"},
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "status": "completed",
                                    "error": None,
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {"type": "agentMessage", "id": "assistant-1", "text": "done"},
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            self.assertEqual(result["thread"]["status"]["type"], "idle")
            self.assertTrue(result["thread"]["status"]["stale_error_normalized"])
            self.assertEqual(result["thread"]["status"]["stale_error_type"], "notLoaded")

    def test_runtime_list_threads_overlays_cached_normalized_status_for_stale_system_error(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/list":
                    return {
                        "data": [
                            {
                                "id": "thread-1",
                                "name": "Demo thread",
                                "status": {"type": "systemError"},
                                "turns": [],
                            }
                        ]
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._runtime_status_for_profile = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]
            runtime._refresh_client_if_runtime_changed = lambda _status: None  # type: ignore[method-assign]
            runtime._cache_thread_entry(
                "thread-1",
                {
                    "name": "Demo thread",
                    "status": {
                        "type": "idle",
                        "stale_error_type": "systemError",
                        "stale_error_normalized": True,
                    },
                },
            )

            result = runtime.list_threads({"profile_id": "p"})

            self.assertEqual(result["threads"][0]["status"]["type"], "idle")
            self.assertTrue(result["threads"][0]["status"]["stale_error_normalized"])

    def test_runtime_list_threads_persists_normalized_status_for_cached_fallbacks(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/list":
                    return {
                        "data": [
                            {
                                "id": "thread-1",
                                "name": "Demo thread",
                                "status": {
                                    "type": "idle",
                                    "stale_error_type": "systemError",
                                    "stale_error_normalized": True,
                                },
                                "turns": [],
                            }
                        ]
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._runtime_status_for_profile = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]
            runtime._refresh_client_if_runtime_changed = lambda _status: None  # type: ignore[method-assign]

            result = runtime.list_threads({"profile_id": "p"})

            self.assertEqual(result["threads"][0]["status"]["type"], "idle")
            cache = json.loads((projects.require_shell_state_root() / "thread_cache.json").read_text(encoding="utf-8"))
            self.assertEqual(cache["by_id"]["thread-1"]["status"]["type"], "idle")
            self.assertTrue(cache["by_id"]["thread-1"]["status"]["stale_error_normalized"])

            fallback = runtime._cached_thread("thread-1", warning="boom")  # type: ignore[attr-defined]

            assert fallback is not None
            self.assertEqual(fallback["status"]["type"], "idle")
            self.assertTrue(fallback["status"]["stale_error_normalized"])

    def test_runtime_read_thread_marks_completed_yunwu_image_item_verified_from_paths(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {
                                            "type": "dynamicToolCall",
                                            "id": "tool-1",
                                            "tool": "yunwu_image_transparent_asset",
                                            "status": "completed",
                                            "contentItems": [
                                                {
                                                    "type": "inputText",
                                                    "text": "AstraBridge dynamic tool result for yunwu_image_transparent_asset:\n"
                                                    + json.dumps(
                                                        {
                                                            "requested_n": 1,
                                                            "actual_n": 1,
                                                            "data": [
                                                                {
                                                                    "asset_id": "yunwu-asset-1",
                                                                    "local_path": "D:/workspace/.astrabridge/assets/generated/yunwu-asset-1.png",
                                                                    "actual_format": "png",
                                                                    "actual_mode": "RGBA",
                                                                    "has_alpha": True,
                                                                    "transparency_status": "passed",
                                                                }
                                                            ],
                                                        }
                                                    ),
                                                }
                                            ],
                                        },
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            evidence = result["thread"]["turns"][0]["items"][1]["lcrVerifiedEvidence"]
            self.assertTrue(evidence["verified"])
            self.assertEqual(evidence["tool"], "yunwu_image_transparent_asset")
            self.assertEqual(evidence["server"], "yunwu_image")
            self.assertIn("D:/workspace/.astrabridge/assets/generated/yunwu-asset-1.png", evidence["paths"])
            self.assertIn("tool-event verified", evidence["label"])

    def test_runtime_read_thread_overlays_completed_dynamic_tool_event_over_stale_thread_item(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "status": "completed",
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {
                                            "type": "dynamicToolCall",
                                            "id": "tool-1",
                                            "tool": "yunwu_image_transparent_asset",
                                            "status": "inProgress",
                                            "contentItems": "",
                                            "success": None,
                                        },
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]
            runtime._record_event(
                {
                    "type": "notification",
                    "method": "item/completed",
                    "index": 10,
                    "params": {
                        "threadId": "thread-1",
                        "turnId": "turn-1",
                        "item": {
                            "type": "dynamicToolCall",
                            "id": "tool-1",
                            "tool": "yunwu_image_transparent_asset",
                            "status": "completed",
                            "contentItems": [
                                {
                                    "type": "inputText",
                                    "text": "AstraBridge dynamic tool result for yunwu_image_transparent_asset:\n"
                                    + json.dumps(
                                        {
                                            "requested_n": 1,
                                            "actual_n": 1,
                                            "data": [
                                                {
                                                    "asset_id": "yunwu-asset-1",
                                                    "local_path": "D:/workspace/.astrabridge/assets/generated/yunwu-asset-1.png",
                                                    "actual_format": "png",
                                                    "actual_mode": "RGBA",
                                                    "has_alpha": True,
                                                    "transparency_status": "passed",
                                                }
                                            ],
                                        }
                                    ),
                                }
                            ],
                            "success": True,
                            "durationMs": 1234,
                        },
                    },
                }
            )

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            item = result["thread"]["turns"][0]["items"][1]
            evidence = item["lcrVerifiedEvidence"]
            self.assertEqual(item["status"], "completed")
            self.assertTrue(item["success"])
            self.assertTrue(evidence["verified"])
            self.assertIn("D:/workspace/.astrabridge/assets/generated/yunwu-asset-1.png", evidence["paths"])

    def test_runtime_read_thread_decorates_command_execution_evidence(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {
                                            "type": "commandExecution",
                                            "id": "cmd-1",
                                            "command": "node --check js/main.js",
                                            "status": "completed",
                                            "exitCode": 0,
                                            "aggregatedOutput": "ok",
                                        },
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            evidence = result["thread"]["turns"][0]["items"][1]["lcrVerifiedEvidence"]
            self.assertTrue(evidence["verified"])
            self.assertEqual(evidence["tool"], "shell_command")
            self.assertEqual(evidence["server"], "codex_builtin")
            self.assertIn("command-event verified", evidence["label"])
            self.assertIn("exit code: 0", evidence["summary"])

    def test_runtime_read_thread_flags_completed_tool_turn_with_progress_only_final(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "status": "completed",
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {
                                            "type": "dynamicToolCall",
                                            "id": "tool-1",
                                            "tool": "lcr_web_research_brief",
                                            "status": "completed",
                                            "contentItems": [{"type": "inputText", "text": '{"tool_event_verified": true}'}],
                                        },
                                        {"type": "agentMessage", "id": "agent-1", "text": "Now let me produce the complete decision-complete plan."},
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            quality = result["thread"]["turns"][0]["lcrCompletionQuality"]
            self.assertEqual(quality["status"], "suspect")
            self.assertEqual(quality["recommended_action"], "continue_or_retry_final_answer")
            self.assertEqual(quality["tool_item_count"], 1)

    def test_runtime_read_thread_does_not_flag_completed_tool_turn_with_substantive_final(self) -> None:
        substantive = "Decision plan: " + ("use background art plus invisible collision grid. " * 8)

        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/read":
                    return {
                        "thread": {
                            "id": "thread-1",
                            "turns": [
                                {
                                    "id": "turn-1",
                                    "status": "completed",
                                    "items": [
                                        {"type": "userMessage", "id": "user-1", "content": []},
                                        {
                                            "type": "dynamicToolCall",
                                            "id": "tool-1",
                                            "tool": "lcr_web_research_brief",
                                            "status": "completed",
                                            "contentItems": [{"type": "inputText", "text": '{"tool_event_verified": true}'}],
                                        },
                                        {"type": "agentMessage", "id": "agent-1", "text": substantive},
                                    ],
                                }
                            ],
                        }
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._ensure_client = lambda _status: FakeClient()  # type: ignore[method-assign]
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True}  # type: ignore[method-assign]

            result = runtime.read_thread({"profile_id": "p"}, "thread-1")

            self.assertNotIn("lcrCompletionQuality", result["thread"]["turns"][0])

    def test_runtime_yunwu_tool_usage_refreshes_asset_registry(self) -> None:
        class FakeAssetRegistry:
            def __init__(self) -> None:
                self.rebuild_count = 0

            def rebuild(self) -> dict[str, object]:
                self.rebuild_count += 1
                return {"registry": {"assets": [{"asset_id": "asset-1"}]}}

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            assets = FakeAssetRegistry()
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), asset_registry=assets)

            delta = runtime._record_yunwu_image_usage_from_tool_result(  # noqa: SLF001
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                result={"actual_n": 1, "data": [{"asset_id": "asset-1"}]},
            )

            self.assertEqual(delta, {"yunwu_images": 1})
            self.assertEqual(assets.rebuild_count, 1)
            self.assertTrue(any(event.get("type") == "asset_registry_refreshed" for event in runtime.list_events()["events"]))

    def test_runtime_yunwu_tool_usage_does_not_overwrite_dogfood_current_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = DogfoodRunService(projects)
            dogfood.save({"enabled": True, "goal": "Build tower game", "current_provider": "deepseek"})
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), dogfood_run=dogfood)

            delta = runtime._record_yunwu_image_usage_from_tool_result(  # noqa: SLF001
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                result={"actual_n": 1, "data": [{"asset_id": "asset-1"}]},
            )

            self.assertEqual(delta, {"yunwu_images": 1})
            self.assertEqual(dogfood.snapshot()["run"]["usage"]["yunwu_images"], 1)
            self.assertEqual(dogfood.snapshot()["run"]["current_provider"], "deepseek")

    def test_runtime_direct_mcp_tool_call_recovers_matching_provider_thread_and_usage(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []
                self.tool_thread_id: str | None = None

            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                payload = dict(params or {})
                self.calls.append((method, payload))
                if method == "thread/read":
                    thread_id = str(payload.get("threadId") or "")
                    if thread_id == "thread-deepseek":
                        raise JsonRpcError("thread not found: thread-deepseek")
                    return {"thread": {"id": thread_id}}
                if method == "thread/start":
                    return {"thread": {"id": "thread-yunwu", "name": "Yunwu tool thread"}}
                if method == "mcpServer/tool/call":
                    self.tool_thread_id = str(payload.get("threadId") or "")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": 'Yunwu image tool result:\n{"actual_n": 1, "data": [{"asset_id": "asset-1"}]}',
                            }
                        ]
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-v4-pro-max",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
                title="Tool task",
            )
            dogfood = DogfoodRunService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks, dogfood_run=dogfood)
            fake_client = FakeClient()
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "yunwu"}  # type: ignore[method-assign]
            runtime._ensure_client = lambda _runtime_status: fake_client  # type: ignore[method-assign]

            response = runtime.call_mcp_tool(
                {
                    "profile_id": "yunwu-gpt-54",
                    "provider_id": "yunwu",
                    "model": "gpt-5.4",
                    "reasoning_effort": "high",
                },
                thread_id="thread-deepseek",
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                arguments={"prompt": "transparent grass"},
            )

            self.assertEqual(response["thread_id"], "thread-yunwu")
            self.assertIsNone(response["handoff_event"])
            self.assertEqual(response["usage_delta"], {"yunwu_images": 1})
            current = tasks.current_task()
            self.assertEqual(current["active_provider_thread_id"], "thread-deepseek")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek")
            self.assertFalse([item for item in current["provider_threads"] if item["thread_id"] == "thread-yunwu"])
            deepseek_thread = [item for item in current["provider_threads"] if item["thread_id"] == "thread-deepseek"][0]
            self.assertNotIn("missing_reason", deepseek_thread)
            self.assertFalse(current["handoff_events"])
            self.assertEqual(dogfood.snapshot()["run"]["usage"]["yunwu_images"], 1)
            self.assertEqual(fake_client.tool_thread_id, "thread-yunwu")
            self.assertFalse(any(call[0] == "thread/read" for call in fake_client.calls))
            self.assertTrue(any(call[0] == "mcpServer/tool/call" and call[1]["threadId"] == "thread-yunwu" for call in fake_client.calls))

    def test_runtime_direct_mcp_tool_call_uses_configured_tool_timeout(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.tool_call_timeout: float | None = None

            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                if method == "thread/start":
                    return {"thread": {"id": "thread-yunwu-tool", "name": "Yunwu tool thread"}}
                if method == "mcpServer/tool/call":
                    self.tool_call_timeout = timeout
                    return {"content": [{"type": "text", "text": "ok"}]}
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._mcp_config.enabled_servers = lambda: [{"name": "yunwu_image", "enabled": True, "tool_timeout_sec": 333}]  # type: ignore[method-assign]
            fake_client = FakeClient()
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "yunwu"}  # type: ignore[method-assign]
            runtime._ensure_client = lambda _runtime_status: fake_client  # type: ignore[method-assign]

            runtime.call_mcp_tool(
                {"profile_id": "yunwu-gpt-54", "provider_id": "yunwu", "model": "gpt-5.4", "reasoning_effort": "high"},
                thread_id="thread-yunwu",
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                arguments={"prompt": "transparent door"},
            )

            self.assertEqual(fake_client.tool_call_timeout, 333.0)

    def test_runtime_direct_mcp_tool_call_retries_when_tool_call_thread_missing(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []
                self.tool_thread_ids: list[str] = []
                self.started = 0

            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                payload = dict(params or {})
                self.calls.append((method, payload))
                if method == "thread/start":
                    self.started += 1
                    thread_id = "thread-yunwu-stale" if self.started == 1 else "thread-yunwu-recovered"
                    return {"thread": {"id": thread_id, "name": "Yunwu tool thread"}}
                if method == "mcpServer/tool/call":
                    thread_id = str(payload.get("threadId") or "")
                    self.tool_thread_ids.append(thread_id)
                    if thread_id != "thread-yunwu-recovered":
                        raise JsonRpcError(f"thread not found: {thread_id}")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": 'Yunwu image tool result:\n{"actual_n": 2, "data": [{"asset_id": "a"}, {"asset_id": "b"}]}',
                            }
                        ]
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(thread_id="thread-stale", title="Tool task")
            dogfood = DogfoodRunService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks, dogfood_run=dogfood)
            fake_client = FakeClient()
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "yunwu"}  # type: ignore[method-assign]
            runtime._ensure_client = lambda _runtime_status: fake_client  # type: ignore[method-assign]

            response = runtime.call_mcp_tool(
                {
                    "profile_id": "yunwu-gpt-54",
                    "provider_id": "yunwu",
                    "model": "gpt-5.4",
                    "reasoning_effort": "high",
                },
                thread_id="thread-stale",
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                arguments={"prompt": "transparent grass"},
            )

            self.assertEqual(fake_client.tool_thread_ids, ["thread-yunwu-stale", "thread-yunwu-recovered"])
            self.assertEqual(response["thread_id"], "thread-yunwu-recovered")
            self.assertIsNone(response["handoff_event"])
            self.assertEqual(response["usage_delta"], {"yunwu_images": 2})
            current = tasks.current_task()
            self.assertEqual(len(current["provider_threads"]), 1)
            stale = [item for item in current["provider_threads"] if item["thread_id"] == "thread-stale"][0]
            self.assertNotIn("missing_reason", stale)
            self.assertEqual(current["active_provider_thread_id"], "thread-stale")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-stale")
            self.assertFalse(current["handoff_events"])
            self.assertEqual(dogfood.snapshot()["run"]["usage"]["yunwu_images"], 2)

    def test_runtime_direct_mcp_tool_call_preserves_visible_task_with_live_fallback(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []
                self.tool_thread_ids: list[str] = []
                self.started = 0

            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                payload = dict(params or {})
                self.calls.append((method, payload))
                if method == "thread/start":
                    self.started += 1
                    thread_id = "thread-yunwu-stale" if self.started == 1 else "thread-yunwu-recovered"
                    return {"thread": {"id": thread_id, "name": "Yunwu tool thread"}}
                if method == "mcpServer/tool/call":
                    thread_id = str(payload.get("threadId") or "")
                    self.tool_thread_ids.append(thread_id)
                    if thread_id != "thread-yunwu-recovered":
                        raise JsonRpcError(f"thread not found: {thread_id}")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": 'Yunwu image tool result:\n{"actual_n": 1, "data": [{"asset_id": "fallback"}]}',
                            }
                        ]
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(
                thread_id="thread-stale",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                title="Tool task",
            )
            tasks.bind_thread(
                thread_id="thread-live-fallback",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            fake_client = FakeClient()
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "yunwu"}  # type: ignore[method-assign]
            runtime._ensure_client = lambda _runtime_status: fake_client  # type: ignore[method-assign]

            response = runtime.call_mcp_tool(
                {
                    "profile_id": "yunwu-gpt-54",
                    "provider_id": "yunwu",
                    "model": "gpt-5.4",
                    "reasoning_effort": "high",
                },
                thread_id="thread-stale",
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                arguments={"prompt": "transparent door"},
            )

            self.assertEqual(fake_client.tool_thread_ids, ["thread-yunwu-stale", "thread-yunwu-recovered"])
            self.assertEqual(response["thread_id"], "thread-yunwu-recovered")
            current = tasks.current_task()
            self.assertEqual(current["active_provider_thread_id"], "thread-stale")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-stale")
            stale = [item for item in current["provider_threads"] if item["thread_id"] == "thread-stale"][0]
            self.assertNotIn("missing_reason", stale)

    def test_runtime_direct_mcp_tool_call_uses_visible_task_thread_hint_when_project_pointer_is_empty(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.tool_thread_id: str | None = None
                self.calls: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                payload = dict(params or {})
                self.calls.append((method, payload))
                if method == "thread/start":
                    return {"thread": {"id": "thread-yunwu-tool", "name": "Yunwu tool thread"}}
                if method == "mcpServer/tool/call":
                    self.tool_thread_id = str(payload.get("threadId") or "")
                    return {"content": [{"type": "text", "text": 'Yunwu image tool result:\n{"actual_n": 1, "data": [{"asset_id": "asset-1"}]}'}]}
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-v4-pro-max",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
                title="Tool task",
            )
            projects.update_project({"current_thread_id": None})
            dogfood = DogfoodRunService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks, dogfood_run=dogfood)
            fake_client = FakeClient()
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "yunwu"}  # type: ignore[method-assign]
            runtime._ensure_client = lambda _runtime_status: fake_client  # type: ignore[method-assign]

            response = runtime.call_mcp_tool(
                {
                    "profile_id": "yunwu-gpt-54",
                    "provider_id": "yunwu",
                    "model": "gpt-5.4",
                    "reasoning_effort": "high",
                },
                thread_id="",
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                arguments={"prompt": "transparent grass"},
            )

            self.assertEqual(response["thread_id"], "thread-yunwu-tool")
            self.assertEqual(fake_client.tool_thread_id, "thread-yunwu-tool")
            self.assertFalse(any(method == "thread/read" for method, _params in fake_client.calls))
            self.assertEqual(tasks.current_task()["active_provider_thread_id"], "thread-deepseek")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-deepseek")

    def test_restore_startup_runtime_reprojects_visible_thread_when_stale_thread_is_missing(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                payload = dict(params or {})
                if method == "thread/read":
                    thread_id = str(payload.get("threadId") or "")
                    if thread_id == "thread-stale":
                        raise JsonRpcError(f"thread not found: {thread_id}")
                    return {"thread": {"id": thread_id}}
                raise AssertionError(f"unexpected request: {method}")

            def is_running(self) -> bool:
                return True

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(
                thread_id="thread-stale",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                title="Recovered task",
            )
            tasks.bind_thread(
                thread_id="thread-live-fallback",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "deepseek"}  # type: ignore[method-assign]
            runtime._ensure_client = lambda _runtime_status: FakeClient()  # type: ignore[method-assign]

            result = runtime.restore_startup_runtime(
                {
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                },
                thread_id="thread-stale",
            )

            current = tasks.current_task()
            self.assertFalse(result["thread_exists"])
            self.assertEqual(result["reconciled_thread_id"], "thread-live-fallback")
            self.assertEqual(current["active_provider_thread_id"], "thread-live-fallback")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-live-fallback")

    def test_restore_startup_runtime_recovers_replacement_thread_when_all_provider_threads_are_missing(self) -> None:
        class FakeClient:
            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                payload = dict(params or {})
                if method == "thread/read":
                    thread_id = str(payload.get("threadId") or "")
                    if thread_id == "thread-stale":
                        raise JsonRpcError(f"thread not found: {thread_id}")
                    return {"thread": {"id": thread_id}}
                if method == "thread/start":
                    return {"thread": {"id": "thread-recovered", "name": "Recovered provider thread"}}
                raise AssertionError(f"unexpected request: {method}")

            def is_running(self) -> bool:
                return True

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(
                thread_id="thread-stale",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                    "collaboration_mode": "plan",
                },
                title="Recovered task",
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda _profile, require_secret=False: {  # type: ignore[method-assign]
                "configured": True,
                "provider_id": "kimi",
                "secret_loaded": True,
            }
            runtime._ensure_client = lambda _runtime_status: FakeClient()  # type: ignore[method-assign]

            result = runtime.restore_startup_runtime(
                {
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                },
                thread_id="thread-stale",
            )

            current = tasks.current_task()
            self.assertFalse(result["thread_exists"])
            self.assertEqual(result["recovered_thread_id"], "thread-recovered")
            self.assertEqual(result["reconciled_thread_id"], "thread-recovered")
            self.assertEqual(current["active_provider_thread_id"], "thread-recovered")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-recovered")
            recovered = [item for item in current["provider_threads"] if item["thread_id"] == "thread-recovered"][0]
            self.assertEqual(recovered["profile_id"], "kimi-default")
            self.assertEqual(recovered["model"], "kimi-k2.6")

    def test_runtime_service_ensure_client_is_serialized_for_concurrent_callers(self) -> None:
        class FakeClient:
            start_count = 0
            init_count = 0

            def __init__(self, **kwargs) -> None:
                type(self).init_count += 1
                self._running = False

            def start(self) -> None:
                type(self).start_count += 1
                threading.Event().wait(0.05)
                self._running = True

            def close(self) -> None:
                self._running = False

            def is_running(self) -> bool:
                return self._running

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            runtime._resolve_launch_target = lambda _runtime_status: {  # type: ignore[method-assign]
                "codex_executable": "codex",
                "launch_command": ["codex", "app-server"],
                "cwd": workspace,
                "env_updates": {},
            }
            original_client = runtime_service_module.AppServerClient
            runtime_service_module.AppServerClient = FakeClient  # type: ignore[assignment]
            clients: list[object] = []
            errors: list[Exception] = []

            def worker() -> None:
                try:
                    clients.append(runtime._ensure_client({"configured": True, "provider_id": "deepseek"}))  # noqa: SLF001
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            try:
                threads = [threading.Thread(target=worker) for _ in range(4)]
                for item in threads:
                    item.start()
                for item in threads:
                    item.join()
            finally:
                runtime_service_module.AppServerClient = original_client  # type: ignore[assignment]

            self.assertFalse(errors)
            self.assertEqual(FakeClient.init_count, 1)
            self.assertEqual(FakeClient.start_count, 1)
            self.assertEqual(len({id(item) for item in clients}), 1)

    def test_runtime_direct_mcp_tool_call_without_task_service_uses_internal_thread(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []
                self.tool_thread_id: str | None = None

            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                payload = dict(params or {})
                self.calls.append((method, payload))
                if method == "thread/start":
                    return {"thread": {"id": "thread-yunwu-fresh", "name": "Fresh Yunwu tool thread"}}
                if method == "mcpServer/tool/call":
                    self.tool_thread_id = str(payload.get("threadId") or "")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": 'Yunwu image tool result:\n{"actual_n": 1, "data": [{"asset_id": "fresh"}]}',
                            }
                        ]
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = DogfoodRunService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), dogfood_run=dogfood)
            fake_client = FakeClient()
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "yunwu"}  # type: ignore[method-assign]
            runtime._ensure_client = lambda _runtime_status: fake_client  # type: ignore[method-assign]

            response = runtime.call_mcp_tool(
                {
                    "profile_id": "yunwu-gpt-54",
                    "provider_id": "yunwu",
                    "model": "gpt-5.4",
                    "reasoning_effort": "high",
                },
                thread_id="thread-from-other-runtime",
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                arguments={"prompt": "transparent grass"},
            )

            self.assertEqual(response["thread_id"], "thread-yunwu-fresh")
            self.assertEqual(fake_client.tool_thread_id, "thread-yunwu-fresh")
            self.assertEqual(response["usage_delta"], {"yunwu_images": 1})
            self.assertEqual(dogfood.snapshot()["run"]["usage"]["yunwu_images"], 1)
            self.assertFalse(any(method == "thread/read" for method, _params in fake_client.calls))

    def test_runtime_direct_mcp_tool_call_does_not_mark_source_missing_when_tool_runtime_differs(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []
                self.tool_thread_id: str | None = None

            def request(self, method: str, params: dict[str, object] | None = None, timeout: float | None = None) -> dict[str, object]:
                payload = dict(params or {})
                self.calls.append((method, payload))
                if method == "thread/start":
                    return {"thread": {"id": "thread-yunwu-fresh", "name": "Fresh Yunwu tool thread"}}
                if method == "mcpServer/tool/call":
                    self.tool_thread_id = str(payload.get("threadId") or "")
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": 'Yunwu image tool result:\n{"actual_n": 1, "data": [{"asset_id": "fresh"}]}',
                            }
                        ]
                    }
                raise AssertionError(f"unexpected request: {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(
                thread_id="thread-stale",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                title="Tool task",
            )
            tasks.bind_thread(
                thread_id="thread-live-fallback",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            fake_client = FakeClient()
            runtime._prepare_runtime = lambda _profile, require_secret=False: {"configured": True, "provider_id": "yunwu"}  # type: ignore[method-assign]
            runtime._ensure_client = lambda _runtime_status: fake_client  # type: ignore[method-assign]

            response = runtime.call_mcp_tool(
                {
                    "profile_id": "yunwu-gpt-54",
                    "provider_id": "yunwu",
                    "model": "gpt-5.4",
                    "reasoning_effort": "high",
                },
                thread_id="thread-stale",
                server="yunwu_image",
                tool="yunwu_image_transparent_asset",
                arguments={"prompt": "transparent key"},
            )

            self.assertEqual(response["thread_id"], "thread-yunwu-fresh")
            self.assertEqual(fake_client.tool_thread_id, "thread-yunwu-fresh")
            current = tasks.current_task()
            self.assertEqual(current["active_provider_thread_id"], "thread-stale")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-stale")
            stale = [item for item in current["provider_threads"] if item["thread_id"] == "thread-stale"][0]
            self.assertNotIn("missing_reason", stale)
            self.assertFalse(any(method == "thread/read" for method, _params in fake_client.calls))

    def test_handler_payload_thread_id_defaults_to_current_project_thread(self) -> None:
        handler = Handler.__new__(Handler)

        class Context:
            projects = type("Projects", (), {"current_project": {"current_thread_id": "thread-current"}})()

        handler.context = Context()  # type: ignore[assignment]
        self.assertEqual(handler._payload_thread_id({"thread_id": "thread-explicit"}), "thread-explicit")  # noqa: SLF001
        self.assertEqual(handler._payload_thread_id({}), "thread-current")  # noqa: SLF001

    def test_handler_payload_thread_id_falls_back_to_visible_task_thread(self) -> None:
        handler = Handler.__new__(Handler)

        class Tasks:
            @staticmethod
            def visible_provider_thread_id(*, include_missing_fallback: bool = False) -> str:
                return "thread-task-fallback" if include_missing_fallback else ""

        class Context:
            projects = type("Projects", (), {"current_project": {"current_thread_id": None}})()
            tasks = Tasks()

        handler.context = Context()  # type: ignore[assignment]
        self.assertEqual(handler._payload_thread_id({}), "thread-task-fallback")  # noqa: SLF001

    def test_handler_resolve_runtime_profile_prefers_active_provider_thread_profile(self) -> None:
        handler = Handler.__new__(Handler)

        class Profiles:
            def __init__(self) -> None:
                self.requested: list[str | None] = []

            def resolve_runtime_profile(self, profile_id: str | None) -> dict[str, Any]:
                self.requested.append(profile_id)
                return {"profile_id": profile_id, "provider_id": "deepseek", "model": "deepseek-v4-pro"}

        class Tasks:
            @staticmethod
            def active_provider_thread() -> dict[str, Any]:
                return {"profile_id": "deepseek-v4-pro-max"}

        class LlmManager:
            @staticmethod
            def inject_profile_key(profile: dict[str, Any]) -> None:
                return None

        class RouterConfig:
            @staticmethod
            def models() -> list[dict[str, Any]]:
                return []

        class Context:
            projects = type("Projects", (), {"current_project": {"default_profile_id": "project-default"}})()
            profiles = Profiles()
            tasks = Tasks()
            llm_manager = LlmManager()
            router_config = RouterConfig()

            def profile_with_model_capabilities(self, profile: dict[str, Any]) -> dict[str, Any]:
                return profile

            def resolve_runtime_profile(self, profile_id: Any) -> dict[str, Any]:
                current = self.projects.current_project or {}
                active_provider_thread = self.tasks.active_provider_thread() if getattr(self, "tasks", None) else {}
                active_profile_id = str((active_provider_thread or {}).get("profile_id") or "").strip()
                chosen = str(profile_id or "").strip() or active_profile_id or str(current.get("default_profile_id") or "")
                profile = self.profiles.resolve_runtime_profile(chosen or None)
                self.llm_manager.inject_profile_key(profile)
                return self.profile_with_model_capabilities(profile)

        handler.context = Context()  # type: ignore[assignment]
        resolved = handler._resolve_runtime_profile(None)  # noqa: SLF001
        self.assertEqual(resolved["profile_id"], "deepseek-v4-pro-max")
        self.assertEqual(handler.context.profiles.requested, ["deepseek-v4-pro-max"])  # type: ignore[attr-defined]

    def test_handler_require_admin_token_accepts_authorization_bearer(self) -> None:
        handler = Handler.__new__(Handler)

        class Context:
            admin_token = "unit-admin-token"

        handler.context = Context()  # type: ignore[assignment]
        handler.headers = {"Authorization": "Bearer unit-admin-token"}  # type: ignore[assignment]

        handler._require_admin_token()  # noqa: SLF001

    def test_handler_require_admin_token_accepts_admin_session_header_alias(self) -> None:
        handler = Handler.__new__(Handler)

        class Context:
            admin_token = "unit-admin-token"

        handler.context = Context()  # type: ignore[assignment]
        handler.headers = {"X-Admin-Session-Token": "unit-admin-token"}  # type: ignore[assignment]

        handler._require_admin_token()  # noqa: SLF001

    def test_handler_ephemeral_key_accepts_api_key_alias(self) -> None:
        handler = Handler.__new__(Handler)

        self.assertEqual(handler._ephemeral_key({"api_key": "unit-yunwu-key"}) , "unit-yunwu-key")  # noqa: SLF001
        self.assertEqual(handler._ephemeral_key({"session_key": "preferred", "api_key": "fallback"}), "preferred")  # noqa: SLF001

    def test_app_context_restore_startup_state_uses_model_capability_enriched_profile(self) -> None:
        context = AppContext.__new__(AppContext)
        captured: dict[str, Any] = {}

        class Projects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-current",
                "default_profile_id": "deepseek-v4-pro-max",
            }

        class Tasks:
            @staticmethod
            def ensure_default_task(thread_id: str | None = None, title: str | None = None) -> None:
                return None

            @staticmethod
            def active_provider_thread(include_missing_fallback: bool = False) -> dict[str, Any]:
                return {"profile_id": "deepseek-v4-pro-max"}

        class Profiles:
            def __init__(self) -> None:
                self.requested: list[str | None] = []

            def resolve_runtime_profile(self, profile_id: str | None) -> dict[str, Any]:
                self.requested.append(profile_id)
                return {"profile_id": profile_id, "provider_id": "deepseek", "model": "deepseek-v4-pro"}

        class LlmManager:
            @staticmethod
            def inject_profile_key(profile: dict[str, Any]) -> None:
                profile["key_injected"] = True

        class RouterConfig:
            @staticmethod
            def models() -> list[dict[str, Any]]:
                return [
                    {
                        "id": "deepseek-v4-pro",
                        "provider": "deepseek",
                        "native_model": "deepseek-v4-pro",
                        "tool_mode": "native",
                        "context_window": 262144,
                    }
                ]

        class Runtime:
            @staticmethod
            def record_supervisor_event(payload: dict[str, Any]) -> None:
                raise AssertionError(f"unexpected restore failure: {payload}")

            @staticmethod
            def restore_startup_runtime(profile: dict[str, Any], *, thread_id: str | None = None) -> None:
                captured["profile"] = dict(profile)
                captured["thread_id"] = thread_id

        context.projects = Projects()  # type: ignore[assignment]
        context.tasks = Tasks()  # type: ignore[assignment]
        context.profiles = Profiles()  # type: ignore[assignment]
        context.llm_manager = LlmManager()  # type: ignore[assignment]
        context.router_config = RouterConfig()  # type: ignore[assignment]
        context.runtime = Runtime()  # type: ignore[assignment]

        context._restore_startup_state()  # noqa: SLF001

        self.assertEqual(context.profiles.requested, ["deepseek-v4-pro-max"])  # type: ignore[attr-defined]
        self.assertEqual(captured["thread_id"], "thread-current")
        self.assertEqual(captured["profile"]["profile_id"], "deepseek-v4-pro-max")
        self.assertTrue(captured["profile"]["key_injected"])
        self.assertEqual(captured["profile"]["tool_mode"], "native")
        self.assertEqual(captured["profile"]["context_window"], 262144)

    def test_app_context_restore_startup_state_prefers_missing_task_route_profile_and_thread(self) -> None:
        context = AppContext.__new__(AppContext)
        captured: dict[str, Any] = {}

        class Projects:
            current_project = {
                "name": "Demo",
                "current_thread_id": None,
                "default_profile_id": "deepseek-v4-pro-max",
            }

        class Tasks:
            @staticmethod
            def ensure_default_task(thread_id: str | None = None, title: str | None = None) -> None:
                captured["ensure_thread_id"] = thread_id
                return None

            @staticmethod
            def active_provider_thread(include_missing_fallback: bool = False) -> dict[str, Any]:
                captured.setdefault("include_missing_fallback_calls", []).append(include_missing_fallback)
                return {
                    "thread_id": "thread-kimi-missing",
                    "profile_id": "kimi-k26",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "missing_reason": "startup_thread_missing",
                }

        class Profiles:
            def __init__(self) -> None:
                self.requested: list[str | None] = []

            def resolve_runtime_profile(self, profile_id: str | None) -> dict[str, Any]:
                self.requested.append(profile_id)
                return {"profile_id": profile_id, "provider_id": "kimi", "model": "kimi-k2.6"}

        class LlmManager:
            @staticmethod
            def inject_profile_key(profile: dict[str, Any]) -> None:
                profile["key_injected"] = True

        class RouterConfig:
            @staticmethod
            def models() -> list[dict[str, Any]]:
                return []

        class Runtime:
            @staticmethod
            def record_supervisor_event(payload: dict[str, Any]) -> None:
                raise AssertionError(f"unexpected restore failure: {payload}")

            @staticmethod
            def restore_startup_runtime(profile: dict[str, Any], *, thread_id: str | None = None) -> None:
                captured["profile"] = dict(profile)
                captured["thread_id"] = thread_id

        context.projects = Projects()  # type: ignore[assignment]
        context.tasks = Tasks()  # type: ignore[assignment]
        context.profiles = Profiles()  # type: ignore[assignment]
        context.llm_manager = LlmManager()  # type: ignore[assignment]
        context.router_config = RouterConfig()  # type: ignore[assignment]
        context.runtime = Runtime()  # type: ignore[assignment]

        context._restore_startup_state()  # noqa: SLF001

        self.assertIn(True, captured["include_missing_fallback_calls"])
        self.assertEqual(captured["ensure_thread_id"], "thread-kimi-missing")
        self.assertEqual(context.profiles.requested, ["kimi-k26"])  # type: ignore[attr-defined]
        self.assertEqual(captured["thread_id"], "thread-kimi-missing")
        self.assertEqual(captured["profile"]["profile_id"], "kimi-k26")

    def test_lcr_web_service_persists_verified_research_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            service = LcrWebService(projects)
            original_research_brief = lcr_web_service_module._research_brief
            lcr_web_service_module._research_brief = lambda **_kwargs: {  # type: ignore[assignment]
                "tool": "lcr_web_research_brief",
                "sources": [{"url": "https://example.com/", "title": "Example"}],
            }

            try:
                result = service.research_brief(
                    {
                        "research_goal": "unit test known source",
                        "queries": [],
                        "source_urls": ["https://example.com/"],
                        "fetch_top_n": 1,
                        "max_chars_per_source": 500,
                        "timeout_sec": 10,
                        "tool_context": {
                            "task_goal": "Build the magical tower game",
                            "current_plan_step": "Research autotile and free meadow maps",
                            "workspace_root": str(workspace),
                            "project_context_ref": ".astrabridge/project_context.json",
                            "asset_context_ref": ".astrabridge/assets/asset_registry.json",
                            "evidence_requirements": ["Return URLs", "Mark unfetched claims"],
                            "forbidden_inputs": [".astrabridge/runtime_events.jsonl", ".astrabridge/approvals.jsonl"],
                            "conversation": "raw hidden transcript should be ignored",
                            "authorization": "Bearer unit-secret",
                            "output_contract": "Do not include base64 data:image payloads.",
                        },
                    }
                )
            finally:
                lcr_web_service_module._research_brief = original_research_brief  # type: ignore[assignment]

            self.assertTrue(result["ok"])
            self.assertTrue(result["tool_event_verified"])
            path = Path(result["path"])
            self.assertTrue(path.is_file())
            self.assertIn(str(workspace / ".astrabridge" / "research"), str(path))
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(record["tool_event_verified"])
            self.assertEqual(record["tool_context"]["task_goal"], "Build the magical tower game")
            self.assertEqual(record["tool_context"]["asset_context_ref"], ".astrabridge/assets/asset_registry.json")
            record_text = json.dumps(record)
            self.assertNotIn("unit-secret", record_text)
            self.assertNotIn("raw hidden transcript", record_text)
            self.assertNotIn("data:image", record_text)

    def test_open_project_fills_missing_runtime_preferences_from_default(self) -> None:
        previous_host = os.environ.get(DEFAULT_RUNTIME_HOST_ENV)
        previous_distro = os.environ.get(DEFAULT_RUNTIME_WSL_DISTRO_ENV)
        os.environ[DEFAULT_RUNTIME_HOST_ENV] = "wsl"
        os.environ[DEFAULT_RUNTIME_WSL_DISTRO_ENV] = "Ubuntu-24.04"
        project_service_module._DEFAULT_RUNTIME_PREFS_CACHE = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = root / "workspace"
                workspace.mkdir()
                project_file = root / "demo.abproj"
                project_file.write_text(
                    json.dumps(
                        {
                            "schema_version": "astrabridge-project-v1",
                            "project_id": "demo",
                            "name": "Demo",
                            "project_file": str(project_file),
                            "workspace_root": str(workspace),
                            "entry_mode": "existing",
                            "default_profile_id": "openai-compatible",
                            "default_model": "gpt-5",
                            "default_effort": "high",
                            "current_thread_id": None,
                            "recent_threads": [],
                            "ui_preferences": {},
                            "created_at": "2026-01-01T00:00:00+00:00",
                            "updated_at": "2026-01-01T00:00:00+00:00",
                        }
                    ),
                    encoding="utf-8",
                )

                project = ProjectService(root / "recent.json").open_project(project_file)

                self.assertEqual(project["ui_preferences"]["execution_host"], "wsl")
                self.assertEqual(project["ui_preferences"]["wsl_distro"], "Ubuntu-24.04")
        finally:
            if previous_host is None:
                os.environ.pop(DEFAULT_RUNTIME_HOST_ENV, None)
            else:
                os.environ[DEFAULT_RUNTIME_HOST_ENV] = previous_host
            if previous_distro is None:
                os.environ.pop(DEFAULT_RUNTIME_WSL_DISTRO_ENV, None)
            else:
                os.environ[DEFAULT_RUNTIME_WSL_DISTRO_ENV] = previous_distro
            project_service_module._DEFAULT_RUNTIME_PREFS_CACHE = None

    def test_open_project_repairs_legacy_runtime_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project_file = root / "demo.abproj"
            project_file.write_text(
                json.dumps(
                    {
                        "schema_version": "astrabridge-project-v1",
                        "project_id": "demo",
                        "name": "Demo",
                        "project_file": str(project_file),
                        "workspace_root": str(workspace),
                        "entry_mode": "existing",
                        "default_profile_id": "yunwu-gpt-55-xhigh",
                        "default_model": "deepseek/deepseek-v4-pro",
                        "default_effort": "max",
                        "current_thread_id": None,
                        "recent_threads": [],
                        "ui_preferences": {},
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )

            project = ProjectService(root / "recent.json").open_project(project_file)

            self.assertEqual(project["default_profile_id"], "openai-compatible")
            self.assertEqual(project["default_model"], "gpt-5.5")
            self.assertEqual(project["default_effort"], "xhigh")
            saved = json.loads(project_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["default_profile_id"], "openai-compatible")
            self.assertEqual(saved["default_model"], "gpt-5.5")
            self.assertEqual(saved["default_effort"], "xhigh")

    def test_open_old_project_formats_are_rejected_without_migration(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            old_state = workspace / ".codex-shell"
            (old_state / "attachments").mkdir(parents=True)
            (old_state / "runtime_events.jsonl").write_text("", encoding="utf-8")
            old_project = root / "old.codexproj"
            old_project.write_text(
                json.dumps(
                    {
                        "schema_version": "codex-shell-project-v1",
                        "project_id": "old",
                        "name": "Old",
                        "project_file": str(old_project),
                        "workspace_root": str(workspace),
                        "entry_mode": "existing",
                        "default_profile_id": "openai-compatible",
                        "default_model": "gpt-5.3-codex",
                        "default_effort": "high",
                        "current_thread_id": None,
                        "recent_threads": [],
                        "ui_preferences": {"locale": "en"},
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )

            service = ProjectService(root / "recent.json")
            with self.assertRaisesRegex(ValueError, r"\.abproj"):
                service.open_project(old_project)
            self.assertFalse((root / "old.abproj").exists())
            self.assertFalse((workspace / ".astrabridge").exists())

            old_lcr_project = root / "old.lcrproj"
            old_lcr_project.write_text(json.dumps({"schema_version": "local-codex-router-project-v1"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"\.abproj"):
                service.open_project(old_lcr_project)
            self.assertFalse((root / "old.abproj").exists())

    def test_project_service_restores_current_project_from_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project_file = root / "demo.abproj"

            first = ProjectService(root / "projects.json")
            created = first.create_project("Demo", project_file, workspace_root=workspace, entry_mode="existing")
            self.assertEqual(first.current_project["project_file"], str(project_file))

            restored = ProjectService(root / "projects.json")
            self.assertIsNotNone(restored.current_project)
            self.assertEqual(restored.current_project["project_file"], created["project_file"])

            restored.close_project()
            cleared = ProjectService(root / "projects.json")
            self.assertIsNone(cleared.current_project)

    def test_project_service_restores_most_recent_project_when_session_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project_file = root / "demo.abproj"

            first = ProjectService(root / "projects.json")
            created = first.create_project("Demo", project_file, workspace_root=workspace, entry_mode="existing")
            session_path = root / "current_project.json"
            if session_path.exists():
                session_path.unlink()

            restored = ProjectService(root / "projects.json")
            self.assertIsNotNone(restored.current_project)
            self.assertEqual(restored.current_project["project_file"], created["project_file"])

    def test_project_service_restores_most_recent_project_when_session_file_is_blank(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project_file = root / "demo.abproj"

            first = ProjectService(root / "projects.json")
            created = first.create_project("Demo", project_file, workspace_root=workspace, entry_mode="existing")
            session_path = root / "current_project.json"
            session_path.write_text('{"project_file":"","updated_at":"2026-06-17T00:00:00+08:00"}\n', encoding="utf-8")

            restored = ProjectService(root / "projects.json")
            self.assertIsNotNone(restored.current_project)
            self.assertEqual(restored.current_project["project_file"], created["project_file"])

    def test_project_service_does_not_clear_session_file_on_transient_restore_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project_file = root / "demo.abproj"

            first = ProjectService(root / "projects.json")
            created = first.create_project("Demo", project_file, workspace_root=workspace, entry_mode="existing")
            project_file.unlink()
            project_file.write_text("{not valid json", encoding="utf-8")

            restored = ProjectService(root / "projects.json")

            self.assertIsNone(restored.current_project)
            session_payload = json.loads((root / "current_project.json").read_text(encoding="utf-8"))
            self.assertEqual(session_payload["project_file"], created["project_file"])

    def test_runtime_config_writes_profile_without_persisting_secret(self) -> None:
        original = os.environ.pop("TEST_PROVIDER_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                service = RuntimeConfigService(root / "embedded_codex_home")
                status = service.load_secret(
                    {
                        "profile_id": "provider-test",
                        "label": "Provider Test",
                        "provider_id": "openai",
                        "base_url": "https://example.com/v1",
                        "model": "test-model",
                        "reasoning_effort": "max",
                        "wire_api": "responses",
                        "env_key": "TEST_PROVIDER_KEY",
                        "auth_mode": "session_paste",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    },
                    session_key="unit_secret_test_value_123456",
                )

                config_text = (root / "embedded_codex_home" / "config.toml").read_text(encoding="utf-8")
                self.assertTrue(status["secret_loaded"])
                self.assertEqual(status["reasoning_effort"], "max")
                self.assertNotIn("unit_secret_test_value_123456", config_text)
                self.assertIn('model = "openai/test-model"', config_text)
                self.assertIn('base_url = "http://127.0.0.1:8787/v1"', config_text)
                self.assertIn('env_key = "CODEX_ROUTER_API_KEY"', config_text)
                self.assertIn('wire_api = "responses"', config_text)
                self.assertIn('model_reasoning_effort = "xhigh"', config_text)
                self.assertEqual(os.environ["TEST_PROVIDER_KEY"], "unit_secret_test_value_123456")
        finally:
            if original is None:
                os.environ.pop("TEST_PROVIDER_KEY", None)
            else:
                os.environ["TEST_PROVIDER_KEY"] = original

    def test_runtime_config_keeps_verified_kimi_image_modality_for_catalog(self) -> None:
        original = os.environ.pop("TEST_KIMI_PROVIDER_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                service = RuntimeConfigService(root / "embedded_codex_home")
                service.load_secret(
                    {
                        "profile_id": "kimi-router",
                        "label": "Kimi Router",
                        "provider_id": "kimi",
                        "base_url": "https://api.moonshot.cn/v1",
                        "model": "kimi-k2.6",
                        "reasoning_effort": "xhigh",
                        "wire_api": "chat",
                        "env_key": "TEST_KIMI_PROVIDER_KEY",
                        "auth_mode": "session_paste",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                        # Older saved profiles/catalog rows may have text-only modalities.
                        "input_modalities": ["text"],
                    },
                    session_key="unit_secret_kimi_test_value_123456",
                )

                catalog = json.loads((root / "embedded_codex_home" / "models" / "astrabridge-models.json").read_text(encoding="utf-8"))
                model_info = catalog["models"][0]
                self.assertEqual(model_info["slug"], "kimi/kimi-k2.6")
                self.assertEqual(model_info["input_modalities"], ["text", "image"])
                self.assertEqual(service.status()["input_modalities"], ["text", "image"])
        finally:
            if original is None:
                os.environ.pop("TEST_KIMI_PROVIDER_KEY", None)
            else:
                os.environ["TEST_KIMI_PROVIDER_KEY"] = original

    def test_modal_service_translates_approvals_and_user_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shell_root = root / ".astrabridge"
            shell_root.mkdir()
            service = ModalService(lambda: shell_root, timeout_seconds=2.0)

            approval_result: dict[str, object] = {}

            def approval_worker() -> None:
                nonlocal approval_result
                approval_result = service.request(
                    "item/commandExecution/requestApproval",
                    {"threadId": "thread_1", "turnId": "turn_1", "itemId": "item_1", "command": "git status"},
                )

            thread = threading.Thread(target=approval_worker)
            thread.start()
            pending = service.list_pending()["modals"][0]
            service.resolve(pending["modal_id"], {"decision": "approve_session"})
            thread.join(timeout=2)
            self.assertEqual(approval_result["decision"], "acceptForSession")

            execpolicy_result: dict[str, object] = {}
            amendment = ["powershell.exe", "-Command", "Get-ChildItem"]

            def execpolicy_worker() -> None:
                nonlocal execpolicy_result
                execpolicy_result = service.request(
                    "item/commandExecution/requestApproval",
                    {
                        "threadId": "thread_1",
                        "turnId": "turn_1b",
                        "itemId": "item_1b",
                        "command": "Get-ChildItem",
                        "availableDecisions": [
                            "accept",
                            {"acceptWithExecpolicyAmendment": {"execpolicy_amendment": amendment}},
                            "cancel",
                        ],
                    },
                )

            thread = threading.Thread(target=execpolicy_worker)
            thread.start()
            pending = service.list_pending()["modals"][0]
            service.resolve(pending["modal_id"], {"decision": "accept_with_execpolicy_amendment"})
            thread.join(timeout=2)
            self.assertEqual(
                execpolicy_result,
                {"decision": {"acceptWithExecpolicyAmendment": {"execpolicy_amendment": amendment}}},
            )

            input_result: dict[str, object] = {}

            def input_worker() -> None:
                nonlocal input_result
                input_result = service.request(
                    "item/tool/requestUserInput",
                    {
                        "threadId": "thread_1",
                        "turnId": "turn_2",
                        "itemId": "item_2",
                        "questions": [
                            {
                                "id": "provider",
                                "header": "Provider",
                                "question": "Which provider should be used?",
                                "options": [{"label": "Yunwu", "description": "Low-cost smoke test"}],
                            }
                        ],
                    },
                )

            thread = threading.Thread(target=input_worker)
            thread.start()
            pending = service.list_pending()["modals"][0]
            service.resolve(
                pending["modal_id"],
                {"answers": {"provider": {"answers": ["Yunwu", "Use the low-cost route first."]}}},
            )
            thread.join(timeout=2)
            self.assertEqual(
                input_result,
                {"answers": {"provider": {"answers": ["Yunwu", "Use the low-cost route first."]}}},
            )

            mcp_result: dict[str, object] = {}

            def mcp_worker() -> None:
                nonlocal mcp_result
                mcp_result = service.request(
                    "mcpServer/elicitation/request",
                    {
                        "threadId": "thread_1",
                        "turnId": "turn_3",
                        "serverName": "context7",
                        "mode": "form",
                        "message": "Choose a library.",
                        "requestedSchema": {"type": "object", "properties": {"library": {"type": "string"}}},
                    },
                )

            thread = threading.Thread(target=mcp_worker)
            thread.start()
            pending = service.list_pending()["modals"][0]
            self.assertEqual(pending["kind"], "mcp_elicitation")
            service.resolve(pending["modal_id"], {"action": "accept", "content": {"library": "react"}, "_meta": None})
            thread.join(timeout=2)
            self.assertEqual(mcp_result, {"action": "accept", "content": {"library": "react"}, "_meta": None})

            cancelled_result: dict[str, object] = {}

            def cancelled_worker() -> None:
                nonlocal cancelled_result
                cancelled_result = service.request(
                    "item/commandExecution/requestApproval",
                    {
                        "threadId": "thread_1",
                        "turnId": "turn_cancel",
                        "itemId": "item_cancel",
                        "command": "curl https://example.com",
                    },
                )

            thread = threading.Thread(target=cancelled_worker)
            thread.start()
            self.assertEqual(len(service.list_pending()["modals"]), 1)
            cancelled = service.cancel_for_turn("thread_1", "turn_cancel", reason="interrupted")
            thread.join(timeout=2)
            self.assertEqual(len(cancelled), 1)
            self.assertEqual(cancelled_result["decision"], "cancel")
            self.assertEqual(service.list_pending()["modals"], [])

            fake_input = service.create_fake("request_user_input")
            self.assertEqual(fake_input["kind"], "user_input")
            self.assertEqual(fake_input["method"], "item/tool/requestUserInput")
            self.assertEqual(service.list_pending()["modals"][0]["modal_id"], fake_input["modal_id"])
            service.resolve(fake_input["modal_id"], {"answers": {"path": {"answers": ["Run smoke test"]}}})
            self.assertEqual(service.list_pending()["modals"], [])

            fake_write = service.create_fake("approval_write")
            self.assertEqual(fake_write["kind"], "approval")
            self.assertEqual(fake_write["method"], "item/commandExecution/requestApproval")
            self.assertIn("Set-Content", str(fake_write["params"].get("command")))
            service.resolve(fake_write["modal_id"], {"decision": "decline"})
            self.assertEqual(service.list_pending()["modals"], [])

            fake_log = service.create_fake("lcr_log_read")
            self.assertIn(".astrabridge", str(fake_log["params"].get("command")))
            service.resolve(fake_log["modal_id"], {"decision": "decline"})
            self.assertEqual(service.list_pending()["modals"], [])

    def test_mcp_config_context7_toml_and_secret_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = McpConfigService(Path(temp) / "mcp_servers.json")
            applied = service.apply_context7_preset()
            self.assertEqual(applied["server"]["name"], "context7")
            toml = service.render_toml()
            self.assertIn("[mcp_servers.context7]", toml)
            self.assertIn('command = "npx"', toml)
            self.assertIn('args = ["-y", "@upstash/context7-mcp"]', toml)
            self.assertIn('default_tools_approval_mode = "prompt"', toml)

            with self.assertRaises(ValueError):
                service.upsert_server(
                    {
                        "name": "bad",
                        "transport": "streamable_http",
                        "url": "https://example.com",
                        "http_headers": {"Authorization": "Bearer unit"},
                    }
                )

    def test_mcp_config_yunwu_image_preset_toml(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = McpConfigService(Path(temp) / "mcp_servers.json")
            applied = service.apply_yunwu_image_preset()
            self.assertEqual(applied["server"]["name"], "yunwu_image")
            self.assertIn("YUNWU_API_KEY", applied["server"]["env_vars"])
            self.assertIn("ASTRABRIDGE_WORKSPACE_ROOT", applied["server"]["env_vars"])
            self.assertIn("ASTRABRIDGE_WORKSPACE_ROOT_WSL", applied["server"]["env_vars"])
            toml = service.render_toml()
            self.assertIn("[mcp_servers.yunwu_image]", toml)
            self.assertIn("yunwu_image_mcp_server.py", toml)
            self.assertIn('"-u"', toml)
            self.assertIn('"ASTRABRIDGE_WORKSPACE_ROOT"', toml)
            self.assertIn('"ASTRABRIDGE_WORKSPACE_ROOT_WSL"', toml)
            self.assertIn("[mcp_servers.yunwu_image.tools.yunwu_image_generate]", toml)
            self.assertIn("[mcp_servers.yunwu_image.tools.yunwu_image_transparent_asset]", toml)
            self.assertNotIn("Bearer", toml)

    def test_yunwu_image_mcp_normalizes_cross_host_paths(self) -> None:
        self.assertEqual(
            yunwu_image_normalize_path_for_os("/mnt/d/workflow/game workspace", "nt"),
            "D:\\workflow\\game workspace",
        )
        self.assertEqual(
            yunwu_image_normalize_path_for_os("D:\\workflow\\game workspace", "posix"),
            "/mnt/d/workflow/game workspace",
        )
        self.assertEqual(
            common_module.normalize_path_for_host("D:\\workflow\\game workspace", host_os_name="posix"),
            "/mnt/d/workflow/game workspace",
        )
        self.assertEqual(
            common_module.normalize_path_for_host("/mnt/d/workflow/game workspace", host_os_name="nt"),
            "D:\\workflow\\game workspace",
        )
        self.assertEqual(
            common_module.normalize_path_for_host(
                "/mnt/d/Google One/research-os-template/apps/astrabridge-sidecar/D:\\workflow\\magical-girl-tower-dogfood\\workspace",
                host_os_name="posix",
            ),
            "/mnt/d/workflow/magical-girl-tower-dogfood/workspace",
        )
        self.assertEqual(
            common_module.normalize_path_for_host(
                "C:\\repo\\apps\\astrabridge-sidecar\\/mnt/d/workflow/magical-girl-tower-dogfood/workspace",
                host_os_name="nt",
            ),
            "D:\\workflow\\magical-girl-tower-dogfood\\workspace",
        )

    def test_mcp_config_lcr_web_preset_toml_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = McpConfigService(Path(temp) / "mcp_servers.json")
            applied = service.apply_lcr_web_preset()
            self.assertEqual(applied["server"]["name"], "lcr_web")
            toml = service.render_toml()
            self.assertIn("[mcp_servers.lcr_web]", toml)
            self.assertIn("lcr_web_mcp_server.py", toml)
            self.assertIn('default_tools_approval_mode = "auto"', toml)
            self.assertIn("[mcp_servers.lcr_web.tools.lcr_web_search_batch]", toml)
            self.assertIn("[mcp_servers.lcr_web.tools.lcr_web_research_brief]", toml)
            self.assertIn("[mcp_servers.lcr_web.tools.lcr_web_search]", toml)
            self.assertIn("[mcp_servers.lcr_web.tools.lcr_web_fetch]", toml)
            self.assertIn('approval_mode = "auto"', toml)
            self.assertNotIn("Authorization", toml)

            tools = {tool["name"]: tool for tool in lcr_web_mcp_tools()}
            self.assertIn("lcr_web_search_batch", tools)
            self.assertIn("lcr_web_research_brief", tools)
            self.assertIn("lcr_web_search", tools)
            self.assertIn("lcr_web_fetch", tools)
            self.assertEqual(tools["lcr_web_search_batch"]["inputSchema"]["properties"]["queries"]["maxItems"], 8)
            self.assertIn("tool_context", tools["lcr_web_search_batch"]["inputSchema"]["properties"])
            self.assertEqual(tools["lcr_web_research_brief"]["inputSchema"]["properties"]["fetch_top_n"]["maximum"], 12)
            self.assertIn("tool_context", tools["lcr_web_research_brief"]["inputSchema"]["properties"])
            self.assertEqual(tools["lcr_web_search"]["inputSchema"]["properties"]["max_results"]["maximum"], 10)
            self.assertIn("tool_context", tools["lcr_web_fetch"]["inputSchema"]["properties"])

    def test_lcr_web_batch_and_research_brief_are_structured_and_sanitized(self) -> None:
        encoded = "a1" + base64.urlsafe_b64encode(b"https://developers.openai.com/codex/mcp").decode("ascii").rstrip("=")
        self.assertEqual(
            lcr_web_mcp_server._clean_bing_url(f"https://www.bing.com/ck/a?u={encoded}&ntb=1"),
            "https://developers.openai.com/codex/mcp",
        )

        original_search = lcr_web_mcp_server._search
        original_fetch = lcr_web_mcp_server._fetch

        def fake_search(query: str, *, max_results: int, timeout_sec: int) -> dict[str, object]:
            return {
                "tool": "lcr_web_search",
                "query": query,
                "results": [
                    {"title": f"{query} A", "url": "https://example.com/a?utm_source=x", "snippet": "alpha"},
                    {"title": f"{query} A duplicate", "url": "https://example.com/a", "snippet": "duplicate"},
                    {"title": f"{query} B", "url": f"https://example.com/{query.replace(' ', '-')}", "snippet": "beta"},
                ][:max_results],
                "result_count": min(max_results, 3),
                "warning": "",
            }

        def fake_fetch(url: str, *, max_chars: int, timeout_sec: int) -> dict[str, object]:
            return {
                "tool": "lcr_web_fetch",
                "url": url,
                "content_type": "text/html",
                "text": f"Fetched source text for {url}. X-Unit-Auth: Bearer unit",
                "truncated": False,
                "char_count": 80,
            }

        try:
            lcr_web_mcp_server._search = fake_search
            lcr_web_mcp_server._fetch = fake_fetch

            batch = lcr_web_mcp_server._search_batch(
                [{"query": "magic tower design", "max_results": 3}, {"query": "autotile rules", "max_results": 2}],
                dedupe=True,
                timeout_sec=5,
            )
            self.assertEqual(batch["tool"], "lcr_web_search_batch")
            self.assertEqual(batch["query_count"], 2)
            urls = [item["url"] for item in batch["merged_results"]]
            self.assertEqual(urls.count("https://example.com/a?utm_source=x"), 1)

            brief = lcr_web_mcp_server._research_brief(
                research_goal="magic tower RPG autotile visual design",
                queries=["magic tower design"],
                source_urls=["https://example.com/source"],
                search_top_k=2,
                fetch_top_n=2,
                max_chars_per_source=500,
                timeout_sec=5,
            )
            self.assertEqual(brief["tool"], "lcr_web_research_brief")
            self.assertGreaterEqual(brief["fetched_source_count"], 1)
            self.assertIn("citation_rule", brief)
            self.assertNotIn("unit_secret_test", json.dumps(brief))

            with self.assertRaises(ValueError):
                lcr_web_mcp_server._research_brief(
                    research_goal="bad",
                    queries=["X-Unit-Auth: Bearer unit"],
                    source_urls=[],
                    search_top_k=1,
                    fetch_top_n=1,
                    max_chars_per_source=500,
                    timeout_sec=5,
                )
        finally:
            lcr_web_mcp_server._search = original_search
            lcr_web_mcp_server._fetch = original_fetch

    def test_lcr_web_batch_repairs_ambiguous_magic_tower_queries(self) -> None:
        original_search = lcr_web_mcp_server._search

        def fake_search(query: str, *, max_results: int, timeout_sec: int) -> dict[str, object]:
            if "tower of the sorcerer" in query.lower() or "mota" in query.lower():
                results = [
                    {
                        "title": "Tower of the Sorcerer routing guide",
                        "url": "https://gamedev.stackexchange.com/questions/123/tower-of-the-sorcerer-routing",
                        "snippet": "Deterministic routing, keys, doors, and HP as currency in a puzzle dungeon.",
                    },
                    {
                        "title": "Top-down JRPG tilemaps",
                        "url": "https://developer.mozilla.org/en-US/docs/Games/Techniques/Tilemaps",
                        "snippet": "Tilemaps, layers, and reducing visible square-grid feeling.",
                    },
                ]
            else:
                results = [
                    {
                        "title": "Magic: The Gathering",
                        "url": "https://magic.wizards.com/en",
                        "snippet": "Trading card game.",
                    },
                    {
                        "title": "Magic definition",
                        "url": "https://www.merriam-webster.com/dictionary/magic",
                        "snippet": "Dictionary definition.",
                    },
                ]
            return {
                "tool": "lcr_web_search",
                "query": query,
                "results": results[:max_results],
                "result_count": min(max_results, len(results)),
                "warning": "",
            }

        try:
            lcr_web_mcp_server._search = fake_search
            batch = lcr_web_mcp_server._search_batch(
                [{"query": "magic tower game design deterministic resource planning", "max_results": 4}],
                dedupe=True,
                timeout_sec=5,
            )
            merged = batch["merged_results"]
            self.assertGreaterEqual(batch["results_by_query"][0]["variant_count"], 3)
            self.assertEqual(batch["source"], "duckduckgo_html_with_ranked_variants")
            self.assertEqual(merged[0]["url"], "https://gamedev.stackexchange.com/questions/123/tower-of-the-sorcerer-routing")
            self.assertGreater(merged[0]["relevance_score"], merged[-1]["relevance_score"])
            self.assertFalse(any(item["url"] == "https://magic.wizards.com/en" for item in merged[:2]))
        finally:
            lcr_web_mcp_server._search = original_search

    def test_lcr_web_research_brief_uses_hinted_tilemap_sources_when_search_is_thin(self) -> None:
        original_search = lcr_web_mcp_server._search
        original_fetch = lcr_web_mcp_server._fetch

        def fake_search(query: str, *, max_results: int, timeout_sec: int) -> dict[str, object]:
            return {
                "tool": "lcr_web_search",
                "query": query,
                "results": [],
                "result_count": 0,
                "warning": "No search results in unit test.",
            }

        def fake_fetch(url: str, *, max_chars: int, timeout_sec: int) -> dict[str, object]:
            return {
                "tool": "lcr_web_fetch",
                "url": url,
                "content_type": "text/html",
                "text": f"Fetched doc for {url}",
                "truncated": False,
                "char_count": len(url) + 20,
            }

        try:
            lcr_web_mcp_server._search = fake_search
            lcr_web_mcp_server._fetch = fake_fetch
            brief = lcr_web_mcp_server._research_brief(
                research_goal="How should an HTML5 tilemap/autotile route reduce visible square-grid feeling in a top-down RPG?",
                queries=None,
                source_urls=None,
                search_top_k=3,
                fetch_top_n=4,
                max_chars_per_source=600,
                timeout_sec=5,
            )
            hinted = [item for item in brief["sources"] if item.get("query") == "hinted_sources"]
            self.assertGreaterEqual(brief["fetched_source_count"], 1)
            self.assertGreaterEqual(len(hinted), 1)
            self.assertTrue(any("developer.mozilla.org" in str(item.get("url")) for item in hinted))
        finally:
            lcr_web_mcp_server._search = original_search
            lcr_web_mcp_server._fetch = original_fetch

    def test_yunwu_image_generation_payload_and_smoke_request(self) -> None:
        class YunwuHandler(BaseHTTPRequestHandler):
            request_payload: dict[str, object] = {}
            request_auth = ""
            transparent_png = _png_rgba(1, 1, (0, 0, 0, 0))

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                type(self).request_auth = str(self.headers.get("Authorization") or "")
                content_type = str(self.headers.get("Content-Type") or "")
                if "multipart/form-data" in content_type:
                    type(self).request_payload = {"multipart": raw.decode("utf-8", errors="replace")}
                    data = [{"revised_prompt": "", "b64_json": base64.b64encode(type(self).transparent_png).decode("ascii")}]
                else:
                    type(self).request_payload = json.loads(raw.decode("utf-8"))
                    if type(self).request_payload.get("response_format") == "b64_json":
                        data = [{"revised_prompt": "", "b64_json": base64.b64encode(type(self).transparent_png).decode("ascii")}]
                    else:
                        data = [{"revised_prompt": "", "url": "https://example.test/generated.webp"}]
                body = json.dumps(
                    {
                        "created": 1776909189,
                        "data": data,
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), YunwuHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            service = YunwuImageService(f"http://127.0.0.1:{server.server_address[1]}/v1")
            payload = service.generation_payload(
                prompt="merge the two references",
                size="2048x2048",
                n=10,
                quality="high",
                image_format="png",
                background="transparent",
                image_urls=["https://example.test/a.png", "https://example.test/b.jpg"],
                prompt_category="game_asset_japanese_anime",
                purpose="unit_door_sprite",
            )
            self.assertEqual(payload["model"], "gpt-image-2")
            self.assertEqual(payload["size"], "2048x2048")
            self.assertEqual(payload["n"], 10)
            self.assertEqual(payload["quality"], "high")
            self.assertEqual(payload["format"], "png")
            self.assertEqual(payload["background"], "transparent")
            self.assertEqual(payload["image"], ["https://example.test/a.png", "https://example.test/b.jpg"])
            self.assertEqual(payload["prompt_category"], "game_asset_japanese_anime")
            self.assertEqual(payload["prompt_guide_display_name"], "Japanese anime game asset")
            self.assertTrue(payload["prompt_enhancement_applied"])
            self.assertIn("Asset mode:", payload["prompt"])
            custom = service.generation_payload(prompt="custom", size="1280x768")
            self.assertEqual(custom["size"], "1280x768")
            with self.assertRaises(ValueError):
                service.generation_payload(prompt="bad", size="1200x700")
            with self.assertRaises(ValueError):
                service.generation_payload(prompt="bad", background="glass")

            protocol = service.protocol()
            self.assertEqual(protocol["schema_version"], 4)
            self.assertEqual(protocol["max_concurrency"], 5)
            self.assertIn("background", protocol["generation"]["parameters"])
            self.assertIn("transparent", protocol["edit"]["parameters"]["background"]["values"])
            self.assertEqual(protocol["transparent_asset_contract"]["default_params"]["background"], "transparent")
            self.assertIn("n_greater_than_1", protocol["count_contract"])
            self.assertIn("transparent_asset_edit_route", protocol)
            tools = {tool["name"]: tool for tool in yunwu_image_mcp_tools()}
            generate_props = tools["yunwu_image_generate"]["inputSchema"]["properties"]
            self.assertEqual(generate_props["quality"]["default"], "high")
            self.assertEqual(generate_props["background"]["default"], "auto")
            self.assertIn("output_format", generate_props)
            self.assertIn("yunwu_image_transparent_asset", tools)

            result = service.test_connectivity(api_key="unit-token-value")
            self.assertTrue(result["ok"])
            self.assertEqual(YunwuHandler.request_auth, "Bearer unit-token-value")
            self.assertEqual(YunwuHandler.request_payload["model"], "gpt-image-2")
            self.assertEqual(YunwuHandler.request_payload["size"], "1024x1024")
            self.assertEqual(result["data"][0]["url"], "https://example.test/generated.webp")
            self.assertNotIn("unit-token-value", json.dumps(result))

            with tempfile.TemporaryDirectory() as asset_temp:
                workspace = Path(asset_temp)
                persisted = service.generate(
                    prompt="asset test",
                    response_format="b64_json",
                    api_key="unit-token-value",
                    workspace_root=workspace,
                    purpose="unit_test_asset",
                    prompt_category="game_asset_japanese_anime",
                )
                manifest_path = workspace / ".astrabridge" / "assets" / "generated" / "asset_manifest.json"
                self.assertTrue(manifest_path.exists())
                manifest_text = manifest_path.read_text(encoding="utf-8")
                self.assertIn("unit_test_asset", manifest_text)
                self.assertIn("game_asset_japanese_anime", manifest_text)
                self.assertNotIn("unit-token-value", manifest_text)
                self.assertTrue(persisted["persisted_assets"][0]["local_path"])
                self.assertEqual(persisted["requested_n"], 1)
                self.assertEqual(persisted["actual_n"], 1)
                self.assertFalse(persisted["count_mismatch"])
                self.assertNotIn("b64_json", persisted["data"][0])
                self.assertTrue(persisted["data"][0]["b64_json_present"])
                self.assertTrue(persisted["data"][0]["local_path"])
                self.assertTrue(persisted["persisted_assets"][0]["has_alpha"])
                self.assertEqual(persisted["persisted_assets"][0]["actual_format"], "png")
                self.assertEqual(persisted["persisted_assets"][0]["actual_width"], 1)
                self.assertEqual(persisted["persisted_assets"][0]["prompt_category"], "game_asset_japanese_anime")
                self.assertTrue(persisted["persisted_assets"][0]["prompt_strategy_metadata"]["prompt_enhancement_applied"])

                transparent = service.transparent_asset(
                    prompt="single yellow magic tower key icon",
                    api_key="unit-token-value",
                    workspace_root=workspace,
                    purpose="unit_transparent_asset",
                    prompt_category="game_asset_japanese_anime",
                )
                self.assertTrue(transparent["persisted_assets"][0]["has_alpha"])
                self.assertNotIn("b64_json", transparent["data"][0])
                self.assertTrue(transparent["data"][0]["b64_json_present"])
                self.assertEqual(transparent["persisted_assets"][0]["requested_background"], "transparent")
                self.assertIn("alpha=0", transparent["persisted_assets"][0]["prompt"])
                self.assertEqual(transparent["persisted_assets"][0]["prompt_category"], "game_asset_japanese_anime")
                self.assertNotEqual(transparent["persisted_assets"][0]["prompt_strategy_metadata"]["asset_mode"], "reference_edit")
                self.assertIn('name="background"', str(YunwuHandler.request_payload.get("multipart") or ""))
                self.assertIn("transparent", str(YunwuHandler.request_payload.get("multipart") or ""))
        finally:
            server.shutdown()
            server.server_close()

    def test_yunwu_image_chat_style_response_and_prompt_guides(self) -> None:
        class ChatStyleHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                _ = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = json.dumps(
                    {
                        "id": "chatcmpl-image",
                        "object": "chat.completion",
                        "created": 1776909199,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "Generated: https://example.test/anime_asset.png",
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), ChatStyleHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as asset_temp:
                service = YunwuImageService(f"http://127.0.0.1:{server.server_address[1]}/v1")
                result = service.generate(
                    prompt="Japanese anime magical girl game asset",
                    quality="high",
                    image_format="png",
                    api_key="unit-token-value",
                    workspace_root=Path(asset_temp),
                    purpose="chat_style_response",
                )
                self.assertEqual(result["data"][0]["url"], "https://example.test/anime_asset.png")
                self.assertEqual(result["persisted_assets"][0]["quality"], "high")
                self.assertEqual(result["persisted_assets"][0]["format"], "png")
        finally:
            server.shutdown()
            server.server_close()

        guides = prompt_guides_payload()
        self.assertGreaterEqual(len(guides["guides"]), 12)
        self.assertEqual(guides["schema_version"], 3)
        self.assertIn("asset_mode", guides["rewrite_policy"]["required_json_fields"])
        self.assertIn("game_asset_policy", guides)
        self.assertIn(
            "game_asset_japanese_anime",
            {str(item.get("category_id")) for item in guides["guides"] if isinstance(item, dict)},
        )
        instruction = build_rewrite_instruction(
            category_id="game_asset_japanese_anime",
            user_prompt="tower game heroine sprites",
            size="2048x2048",
            transparent_background=True,
            reference_image_mode=True,
        )
        self.assertIn("Yunwu gpt-image-2", instruction["instruction"])
        self.assertIn("transparent background", instruction["instruction"])
        self.assertIn("asset_mode", instruction["instruction"])
        self.assertIn("terrain_tileset", instruction["instruction"])
        self.assertLessEqual(len(instruction["defaults"]["size"]), 16)
        background_prompt = apply_prompt_guide(
            category_id="game_asset_japanese_anime",
            user_prompt="top-down JRPG overworld grass background plate for a magical forest region",
            purpose="grass_background_plate",
            transparent_background=False,
        )
        self.assertEqual(background_prompt["asset_mode"], "background_plate")
        self.assertNotIn("alpha=0", background_prompt["prompt"])
        self.assertNotIn("transparent background only", background_prompt["prompt"].lower())

    def test_yunwu_image_retries_ssl_eof_before_success(self) -> None:
        class FakeResponse:
            def __init__(self, body: bytes) -> None:
                self._body = body

            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
                return None

            def read(self) -> bytes:
                return self._body

        attempts = {"count": 0}
        body = json.dumps(
            {
                "created": 1776909189,
                "data": [{"revised_prompt": "", "url": "https://example.test/retry-success.png"}],
            }
        ).encode("utf-8")

        def fake_urlopen(request, timeout=0):  # noqa: ANN001
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise urllib.error.URLError(ssl.SSLEOFError(8, "EOF occurred in violation of protocol"))
            return FakeResponse(body)

        service = YunwuImageService("https://example.test/v1")
        with patch("urllib.request.urlopen", side_effect=fake_urlopen), patch(
            "astrabridge_sidecar.yunwu_image_service.time.sleep",
            return_value=None,
        ) as sleep_mock:
            result = service.test_connectivity(api_key="unit-token-value")

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"][0]["url"], "https://example.test/retry-success.png")
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(sleep_mock.call_count, 2)
        door_prompt = apply_prompt_guide(
            category_id="game_asset_japanese_anime",
            user_prompt="yellow rune-sealed door sprite for a forest ruin map",
            purpose="yellow_door_retry_smoke",
            transparent_background=True,
        )
        self.assertEqual(door_prompt["asset_mode"], "single_transparent_asset")
        self.assertIn("single_transparent_asset", door_prompt["prompt"])
        self.assertIn("transparent", door_prompt["prompt"].lower())
        no_frame_prompt = apply_prompt_guide(
            category_id="game_asset_japanese_anime",
            user_prompt="single yellow key sprite, no frame, no extra props, transparent background",
            purpose="yellow_key_retry_smoke",
            transparent_background=True,
        )
        self.assertEqual(no_frame_prompt["asset_mode"], "single_transparent_asset")
        self.assertNotIn("Asset mode: animation_frame_set.", no_frame_prompt["prompt"])
        for prompt in (
            "single yellow magic card inventory sprite with star sigil, transparent background",
            "single blue magical barrier obstacle sprite for a meadow map, transparent background",
            "single teleport circle sprite for floor transition, transparent background",
        ):
            guided = apply_prompt_guide(
                category_id="game_asset_japanese_anime",
                user_prompt=prompt,
                purpose="magic_tower_prop_smoke",
                transparent_background=True,
            )
            self.assertEqual(guided["asset_mode"], "single_transparent_asset")
            self.assertIn("single_transparent_asset", guided["prompt"])

        with tempfile.TemporaryDirectory() as temp:
            image_path = Path(temp) / "input.png"
            mask_path = Path(temp) / "mask.png"
            image_path.write_bytes(b"fake")
            mask_path.write_bytes(b"mask")
            fields, files = YunwuImageService().edit_payload(
                prompt="convert into a transparent JRPG icon",
                image_paths=[str(image_path)],
                mask_path=str(mask_path),
                model="flux-kontext-pro",
                size="1024x1024",
                n=3,
                quality="high",
                background="transparent",
                moderation="low",
                prompt_category="image_edit_recreation",
                purpose="unit_edit_icon",
            )
            self.assertEqual(fields["model"], "flux-kontext-pro")
            self.assertEqual(fields["n"], "3")
            self.assertEqual(fields["background"], "transparent")
            self.assertEqual(fields["moderation"], "low")
            self.assertEqual(fields["prompt_category"], "image_edit_recreation")
            self.assertEqual(fields["asset_mode"], "reference_edit")
            self.assertEqual(fields["prompt_enhancement_applied"], "true")
            self.assertEqual([name for name, _ in files], ["image", "mask"])

    def test_asset_registry_rebuild_context_and_promote_are_secret_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            generated_root = workspace / ".astrabridge" / "assets" / "generated"
            sliced_root = workspace / ".astrabridge" / "assets" / "sliced" / "yunwu-asset-1"
            generated_root.mkdir(parents=True)
            sliced_root.mkdir(parents=True)
            source_png = generated_root / "yunwu-asset-1.png"
            slice_png = sliced_root / "heroine_fullbody_000.png"
            source_png.write_bytes(b"png source")
            slice_png.write_bytes(b"png slice")
            generated_manifest = {
                "assets": [
                    {
                        "asset_id": "yunwu-asset-1",
                        "provider": "yunwu",
                        "tool": "yunwu_image_generate",
                        "model": "gpt-image-2",
                        "purpose": "heroine_sprite_reference",
                        "prompt": "Original Japanese anime heroine sprite",
                        "local_path": str(source_png),
                        "generated_at": "2026-06-13T00:00:00+08:00",
                    }
                ]
            }
            (generated_root / "asset_manifest.json").write_text(json.dumps(generated_manifest), encoding="utf-8")
            per_sheet = {
                "asset_id": "yunwu-asset-1",
                "strategy": "heroine",
                "manual_review_needed": False,
                "quality_gate": {"passed": True},
                "assets": [
                    {
                        "asset_id": "yunwu-asset-1_heroine_fullbody_000",
                        "file": "heroine_fullbody_000.png",
                        "class": "heroine_fullbody",
                        "confidence": 1.0,
                        "quality_flags": [],
                    }
                ],
            }
            (sliced_root / "sliced_manifest.json").write_text(json.dumps(per_sheet), encoding="utf-8")
            aggregate = {
                "sheets": [
                    {
                        "asset_id": "yunwu-asset-1",
                        "strategy": "heroine",
                        "manifest_path": str(sliced_root / "sliced_manifest.json"),
                        "quality_gate_passed": True,
                        "manual_review_needed": False,
                    }
                ]
            }
            (workspace / ".astrabridge" / "assets" / "sliced" / "sliced_manifest.json").write_text(json.dumps(aggregate), encoding="utf-8")

            service = AssetRegistryService(projects)
            rebuilt = service.rebuild()
            registry_text = json.dumps(rebuilt, ensure_ascii=False)
            self.assertIn("yunwu-asset-1_heroine_fullbody_000", registry_text)
            self.assertIn("AstraBridge Asset Context Pack", rebuilt["context_pack"]["text"])
            self.assertNotIn("Bearer", registry_text)
            self.assertNotIn("api_key", registry_text.lower())

            promoted = service.promote(
                {
                    "asset_id": "yunwu-asset-1_heroine_fullbody_000",
                    "target_name": "heroine_walk_down_0.png",
                    "manifest_section": "sprites",
                    "entity": "heroine",
                    "state": "walk_down",
                }
            )
            target = workspace / "assets" / "images" / "sprites" / "heroine_walk_down_0.png"
            self.assertTrue(target.is_file())
            game_manifest = json.loads((workspace / "assets" / "images" / "sprites" / "sprite_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(game_manifest["sprites"]["heroine"]["walk_down"], "sprites/heroine_walk_down_0.png")
            self.assertEqual(promoted["asset"]["integration_status"], "promoted")
            rebuilt_after_promote = service.rebuild()
            heroine = next(
                item
                for item in rebuilt_after_promote["registry"]["assets"]
                if item.get("asset_id") == "yunwu-asset-1_heroine_fullbody_000"
            )
            self.assertEqual(heroine["asset_type"], "heroine")
            self.assertEqual(heroine["integration_status"], "in_use")
            self.assertTrue(heroine["in_use"])
            self.assertEqual(heroine["manifest_key"], "sprites.heroine.walk_down")
            self.assertIn("sprites.heroine.walk_down", heroine["manifest_keys"])
            self.assertIn("sprites/heroine_walk_down_0.png", heroine["game_refs"])
            self.assertIn("manifest=sprites.heroine.walk_down", rebuilt_after_promote["context_pack"]["text"])

    def test_asset_registry_promote_can_crop_resize_and_record_pivot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            generated_root = workspace / ".astrabridge" / "assets" / "generated"
            generated_root.mkdir(parents=True)
            source_png = generated_root / "yunwu-portal.png"
            source_png.write_bytes(_png_rgba_rect(32, 32, (10, 6, 23, 28), (80, 170, 255, 255)))
            generated_manifest = {
                "assets": [
                    {
                        "asset_id": "yunwu-portal",
                        "provider": "yunwu",
                        "tool": "yunwu_image_transparent_asset",
                        "model": "gpt-image-2",
                        "purpose": "ice portal",
                        "prompt": "Transparent JRPG portal",
                        "local_path": str(source_png),
                        "generated_at": "2026-06-16T00:00:00+08:00",
                    }
                ]
            }
            (generated_root / "asset_manifest.json").write_text(json.dumps(generated_manifest), encoding="utf-8")

            service = AssetRegistryService(projects)
            service.rebuild()
            promoted = service.promote(
                {
                    "asset_id": "yunwu-portal",
                    "target_name": "portal_ice_crystal_lcr.png",
                    "manifest_section": "tiles",
                    "tile_key": "portal_ice",
                    "role": "portal",
                    "crop_to_alpha": True,
                    "output_size": "96x96",
                    "pivot": "bottom_center",
                }
            )

            target = workspace / "assets" / "images" / "sprites" / "portal_ice_crystal_lcr.png"
            self.assertTrue(target.is_file())
            try:
                from PIL import Image  # type: ignore
            except Exception:  # pragma: no cover - mirrors optional runtime dependency
                self.skipTest("Pillow is not available")
            with Image.open(target) as image:
                self.assertEqual(image.size, (96, 96))
                self.assertEqual(image.mode, "RGBA")
            game_manifest = json.loads((workspace / "assets" / "images" / "sprites" / "sprite_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(game_manifest["tiles"]["portal_ice"], "sprites/portal_ice_crystal_lcr.png")
            transform = game_manifest["promoted_assets"]["yunwu-portal"]["transform"]
            self.assertTrue(transform["crop_to_alpha"])
            self.assertEqual(transform["output_width"], 96)
            self.assertEqual(transform["output_height"], 96)
            self.assertEqual(transform["pivot"], "bottom_center")
            self.assertEqual(promoted["asset"]["pivot"], "bottom_center")
            rebuilt = service.rebuild()
            portal = next(item for item in rebuilt["registry"]["assets"] if item.get("asset_id") == "yunwu-portal")
            self.assertEqual(portal["integration_status"], "in_use")
            self.assertEqual(portal["sprite_width"], 96)
            self.assertEqual(portal["sprite_height"], 96)
            self.assertEqual(portal["pivot"], "bottom_center")
            self.assertEqual(portal["manifest_keys"], ["tiles.portal_ice"])

    def test_asset_registry_rebuild_links_agent_copied_game_asset_by_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")

            generated_root = workspace / ".astrabridge" / "assets" / "generated"
            sprites_root = workspace / "assets" / "images" / "sprites"
            generated_root.mkdir(parents=True)
            sprites_root.mkdir(parents=True)

            generated_png = generated_root / "yunwu-door.png"
            game_png = sprites_root / "tile_door_new.png"
            generated_png.write_bytes(b"same transparent door bytes")
            game_png.write_bytes(b"same transparent door bytes")
            (generated_root / "asset_manifest.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "asset_id": "yunwu-door",
                                "provider": "yunwu",
                                "tool": "yunwu_image_transparent_asset",
                                "model": "gpt-image-2",
                                "purpose": "yellow magic door",
                                "local_path": str(generated_png),
                                "has_alpha": True,
                                "generated_at": "2026-06-16T00:00:00+08:00",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (sprites_root / "sprite_manifest.json").write_text(
                json.dumps({"tiles": {"door": "sprites/tile_door_new.png"}}),
                encoding="utf-8",
            )

            rebuilt = AssetRegistryService(projects).rebuild()
            assets = rebuilt["registry"]["assets"]
            door = next(item for item in assets if item.get("asset_id") == "yunwu-door")
            self.assertEqual(door["integration_status"], "in_use")
            self.assertEqual(door["promoted_path"], "assets/images/sprites/tile_door_new.png")
            self.assertIn("sprites/tile_door_new.png", door["game_refs"])
            self.assertIn("tiles.door", door["manifest_keys"])
            self.assertIn("linked_by_content_hash", door["warnings"])
            self.assertFalse(any(item.get("asset_id") == "game-tile_door_new" for item in assets))

    def test_runtime_injects_asset_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            registry_root = workspace / ".astrabridge" / "assets"
            registry_root.mkdir(parents=True)
            (registry_root / "asset_registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": "lcr-asset-registry-v1",
                        "assets": [
                            {
                                "asset_id": "sprite-1",
                                "stage": "sliced",
                                "kind": "heroine",
                                "role": "walk_down",
                                "status": "approved",
                                "quality_status": "passed",
                                "integration_status": "not_promoted",
                                "source_path": ".astrabridge/assets/sliced/sprite-1.png",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            assets = AssetRegistryService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), asset_registry=assets)
            inputs = runtime._build_user_inputs("Continue the tower game.", [])  # noqa: SLF001
            text = "\n".join(str(item.get("text") or "") for item in inputs if item.get("type") == "text")
            mentions = [item for item in inputs if item.get("type") == "mention"]
            self.assertIn("Continue the tower game.", text)
            self.assertIn("AstraBridge Asset Context Pack", text)
            self.assertIn("Do not call MCP resources/read", text)
            self.assertFalse(any(item.get("name") == "asset_registry.json" for item in mentions))

    def test_asset_registry_snapshot_rewrites_legacy_schema_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            registry_root = workspace / ".astrabridge" / "assets"
            registry_root.mkdir(parents=True)
            registry_path = registry_root / "asset_registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": "lcr-asset-registry-v1",
                        "assets": [
                            {
                                "asset_id": "sprite-1",
                                "stage": "generated",
                                "role": "yellow_key",
                                "status": "generated",
                                "quality_status": "passed",
                                "integration_status": "not_promoted",
                                "source_path": ".astrabridge/assets/generated/sprite-1.png",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = AssetRegistryService(projects).snapshot(rebuild_if_missing=False)
            saved = json.loads(registry_path.read_text(encoding="utf-8"))

            self.assertEqual(snapshot["registry"]["schema_version"], "astrabridge-asset-registry-v1")
            self.assertEqual(snapshot["context_pack"]["schema_version"], "astrabridge-asset-context-pack-v1")
            self.assertEqual(saved["schema_version"], "astrabridge-asset-registry-v1")
            self.assertEqual(
                json.loads((registry_root / "asset_context_pack.json").read_text(encoding="utf-8"))["schema_version"],
                "astrabridge-asset-context-pack-v1",
            )

    def test_asset_and_project_context_snapshots_record_task_context_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(thread_id="thread-ds", title="Dogfood task")
            registry_root = workspace / ".astrabridge" / "assets"
            registry_root.mkdir(parents=True)
            (registry_root / "asset_registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": "lcr-asset-registry-v1",
                        "assets": [
                            {
                                "asset_id": "sprite-1",
                                "stage": "generated",
                                "kind": "key",
                                "asset_type": "key",
                                "role": "yellow_key",
                                "status": "generated",
                                "quality_status": "passed",
                                "integration_status": "not_promoted",
                                "source_path": ".astrabridge/assets/generated/sprite-1.png",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            assets = AssetRegistryService(projects, tasks)
            project_context = ProjectContextService(projects, None, assets, tasks)

            asset_snapshot = assets.snapshot()
            project_snapshot = project_context.snapshot(thread_id="thread-ds")
            current = tasks.current_task()

            self.assertTrue(current["asset_context_refs"])
            self.assertEqual(current["asset_context_refs"][0]["pack_type"], "asset")
            self.assertEqual(current["asset_context_refs"][0]["path"], asset_snapshot["context_pack"]["context_pack_path"])
            self.assertTrue(current["context_pack_refs"])
            self.assertEqual(current["context_pack_refs"][0]["pack_type"], "project")
            self.assertEqual(current["context_pack_refs"][0]["path"], project_snapshot["context_pack_path"])

    def test_asset_registry_rebuild_mark_and_promote_record_task_context_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.ensure_default_task(thread_id="thread-ds", title="Dogfood task")

            generated_root = workspace / ".astrabridge" / "assets" / "generated"
            generated_root.mkdir(parents=True)
            source_png = generated_root / "yunwu-key.png"
            source_png.write_bytes(_png_rgba_rect(32, 32, (8, 8, 23, 23), (255, 215, 0, 255)))
            (generated_root / "asset_manifest.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "asset_id": "yunwu-key",
                                "provider": "yunwu",
                                "tool": "yunwu_image_transparent_asset",
                                "model": "gpt-image-2",
                                "purpose": "yellow_key_sprite",
                                "local_path": str(source_png),
                                "generated_at": "2026-06-17T00:00:00+08:00",
                                "has_alpha": True,
                                "transparency_status": "passed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            service = AssetRegistryService(projects, tasks)
            rebuilt = service.rebuild()
            current = tasks.current_task()
            self.assertTrue(current["asset_context_refs"])
            self.assertEqual(current["asset_context_refs"][0]["path"], rebuilt["context_pack"]["context_pack_path"])

            marked = service.mark({"asset_id": "yunwu-key", "quality_status": "passed", "status": "approved"})
            current = tasks.current_task()
            self.assertTrue(current["asset_context_refs"])
            self.assertEqual(current["asset_context_refs"][0]["path"], marked["context_pack"]["context_pack_path"])

            promoted = service.promote(
                {
                    "asset_id": "yunwu-key",
                    "target_name": "key_yellow_lcr.png",
                    "manifest_section": "tiles",
                    "tile_key": "yellow_key",
                    "role": "key",
                }
            )
            current = tasks.current_task()
            self.assertTrue(current["asset_context_refs"])
            self.assertEqual(current["asset_context_refs"][0]["path"], promoted["context_pack"]["context_pack_path"])
            self.assertEqual(current["asset_context_refs"][0]["pack_type"], "asset")

    def test_asset_registry_rebuild_falls_back_to_fresh_task_service_when_primary_task_service_does_not_persist(self) -> None:
        class BrokenTaskService:
            def __init__(self, projects: ProjectService) -> None:
                self._projects = projects

            def current_task(self) -> dict[str, Any] | None:
                return None

            def record_context_ref(self, **_kwargs: Any) -> None:
                return

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            real_tasks = TaskService(projects)
            real_tasks.ensure_default_task(thread_id="thread-ds", title="Dogfood task")

            generated_root = workspace / ".astrabridge" / "assets" / "generated"
            generated_root.mkdir(parents=True)
            source_png = generated_root / "yunwu-door.png"
            source_png.write_bytes(_png_rgba_rect(32, 32, (4, 4, 27, 27), (255, 215, 0, 255)))
            (generated_root / "asset_manifest.json").write_text(
                json.dumps(
                    {
                        "assets": [
                            {
                                "asset_id": "yunwu-door",
                                "provider": "yunwu",
                                "tool": "yunwu_image_transparent_asset",
                                "model": "gpt-image-2",
                                "purpose": "yellow_door_sprite",
                                "local_path": str(source_png),
                                "generated_at": "2026-06-17T00:00:00+08:00",
                                "has_alpha": True,
                                "transparency_status": "passed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            service = AssetRegistryService(projects, BrokenTaskService(projects))
            rebuilt = service.rebuild()

            current = TaskService(projects).current_task()
            self.assertTrue(current["asset_context_refs"])
            self.assertEqual(current["asset_context_refs"][0]["path"], rebuilt["context_pack"]["context_pack_path"])
            self.assertEqual(current["asset_context_refs"][0]["generated_at"], rebuilt["context_pack"]["generated_at"])

    def test_runtime_minimal_visual_context_skips_project_and_asset_packs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            registry_root = workspace / ".astrabridge" / "assets"
            registry_root.mkdir(parents=True)
            (registry_root / "asset_registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": "lcr-asset-registry-v1",
                        "assets": [
                            {
                                "asset_id": "sprite-1",
                                "kind": "heroine",
                                "quality_status": "passed",
                                "source_path": ".astrabridge/assets/sliced/sprite-1.png",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            image_path = root / "visual.png"
            image_path.write_bytes(_png_rgba(2, 2, (10, 20, 30, 255)))
            assets = AssetRegistryService(projects)
            context = ProjectContextService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), asset_registry=assets, project_context=context)

            inputs = runtime._build_user_inputs(  # noqa: SLF001
                "Visual micro-check: pass/retry/redraw only.",
                [{"path": str(image_path), "name": "visual.png", "mime_type": "image/png"}],
                context_mode="minimal_visual",
            )

            text = "\n".join(str(item.get("text") or "") for item in inputs if item.get("type") == "text")
            self.assertIn("AstraBridge minimal visual mode", text)
            self.assertIn("Visual micro-check", text)
            self.assertNotIn("AstraBridge Asset Context Pack", text)
            self.assertNotIn("AstraBridge Project Context Pack", text)
            self.assertEqual([item.get("type") for item in inputs].count("localImage"), 1)
            self.assertFalse(any(item.get("type") == "mention" and item.get("name") in {"asset_registry.json", "project_context_pack.json"} for item in inputs))

    def test_runtime_health_check_context_skips_project_and_asset_packs_without_visual_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            registry_root = workspace / ".astrabridge" / "assets"
            registry_root.mkdir(parents=True)
            (registry_root / "asset_registry.json").write_text(
                json.dumps({"schema_version": "lcr-asset-registry-v1", "assets": [{"asset_id": "sprite-1", "kind": "heroine"}]}),
                encoding="utf-8",
            )
            assets = AssetRegistryService(projects)
            context = ProjectContextService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), asset_registry=assets, project_context=context)

            inputs = runtime._build_user_inputs(  # noqa: SLF001
                "Post-compact health check. Reply exactly: ok",
                [],
                context_mode="health_check",
            )

            text = "\n".join(str(item.get("text") or "") for item in inputs if item.get("type") == "text")
            self.assertIn("Post-compact health check", text)
            self.assertNotIn("AstraBridge minimal visual mode", text)
            self.assertNotIn("AstraBridge Asset Context Pack", text)
            self.assertNotIn("AstraBridge Project Context Pack", text)
            self.assertFalse(any(item.get("type") == "mention" and item.get("name") in {"asset_registry.json", "project_context_pack.json"} for item in inputs))

    def test_runtime_accepts_multi_provider_handoff_context_alias(self) -> None:
        runtime = RuntimeService(None, ModalService(lambda: Path(tempfile.gettempdir())))

        self.assertEqual(runtime._normalize_context_mode("project"), "default")  # noqa: SLF001
        self.assertEqual(runtime._normalize_context_mode("project_context"), "default")  # noqa: SLF001
        self.assertEqual(runtime._normalize_context_mode("with_context"), "default")  # noqa: SLF001
        self.assertEqual(runtime._normalize_context_mode("health_check"), "minimal_text")  # noqa: SLF001
        self.assertEqual(runtime._normalize_context_mode("lightweight"), "minimal_text")  # noqa: SLF001
        self.assertEqual(runtime._normalize_context_mode("multi_provider_handoff"), "default")  # noqa: SLF001
        self.assertEqual(runtime._normalize_context_mode("multi_provider"), "default")  # noqa: SLF001
        self.assertEqual(runtime._normalize_context_mode("handoff"), "default")  # noqa: SLF001

    def test_runtime_task_thread_settings_preserve_collaboration_when_omitted(self) -> None:
        runtime = RuntimeService(None, ModalService(lambda: Path(tempfile.gettempdir())))

        implicit = runtime._task_thread_settings(  # noqa: SLF001
            {"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
            None,
            None,
            "auto",
        )
        explicit = runtime._task_thread_settings(  # noqa: SLF001
            {"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
            None,
            None,
            "auto",
            collaboration_mode="default",
        )

        self.assertNotIn("collaboration_mode", implicit)
        self.assertEqual(explicit["collaboration_mode"], "default")

    def test_runtime_context_mode_error_lists_supported_modes(self) -> None:
        runtime = RuntimeService(None, ModalService(lambda: Path(tempfile.gettempdir())))

        with self.assertRaisesRegex(ValueError, "Supported context modes"):
            runtime._normalize_context_mode("bogus")  # noqa: SLF001

    def test_asset_context_pack_injects_priority_slice_not_full_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            registry_root = workspace / ".astrabridge" / "assets"
            registry_root.mkdir(parents=True)
            assets = []
            for index in range(20):
                assets.append(
                    {
                        "asset_id": f"promoted-{index}",
                        "stage": "game_sprite",
                        "kind": "monster",
                        "role": "monster",
                        "quality_status": "passed",
                        "integration_status": "promoted",
                        "promoted_path": f"assets/images/sprites/monster_{index}.png",
                    }
                )
            for index in range(20):
                assets.append(
                    {
                        "asset_id": f"approved-{index}",
                        "stage": "sliced",
                        "kind": "terrain",
                        "role": "tile",
                        "quality_status": "passed",
                        "integration_status": "not_promoted",
                        "source_path": f".astrabridge/assets/sliced/tile_{index}.png",
                    }
                )
            (registry_root / "asset_registry.json").write_text(
                json.dumps({"schema_version": "lcr-asset-registry-v1", "assets": assets}),
                encoding="utf-8",
            )

            service = AssetRegistryService(projects)
            pack = service.context_pack()
            text = pack["text"]
            self.assertIn("Only a small priority slice is auto-injected", text)
            self.assertIn("10 more promoted/in-use assets", text)
            self.assertIn("14 more approved assets", text)
            self.assertIn("promoted-0", text)
            self.assertNotIn("promoted-19", text)
            self.assertIn("approved-0", text)
            self.assertNotIn("approved-19", text)
            self.assertLessEqual(len(text), 5000)

    def test_asset_context_pack_flags_missing_blocking_obstacle_sprites(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            registry_root = workspace / ".astrabridge" / "assets"
            registry_root.mkdir(parents=True)
            (registry_root / "asset_registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": "lcr-asset-registry-v1",
                        "assets": [
                            {
                                "asset_id": "yellow-key",
                                "kind": "key",
                                "role": "key",
                                "quality_status": "passed",
                                "promoted_path": "assets/images/sprites/tile_key.png",
                            },
                            {
                                "asset_id": "floor-tile",
                                "kind": "terrain",
                                "role": "floor",
                                "quality_status": "passed",
                                "promoted_path": "assets/images/sprites/tile_floor.png",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            service = AssetRegistryService(projects)
            pack = service.context_pack()

            self.assertIn("blocking_obstacle_sprites_missing", json.dumps(pack["asset_gaps"]))
            self.assertIn("Do not repurpose keys", pack["text"])
            self.assertIn("tree_wall", pack["text"])

            (registry_root / "asset_registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": "lcr-asset-registry-v1",
                        "assets": [
                            {
                                "asset_id": "forest-tree-wall",
                                "kind": "terrain",
                                "role": "tree_wall",
                                "quality_status": "passed",
                                "promoted_path": "assets/images/sprites/tree_wall.png",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertFalse(AssetRegistryService(projects).context_pack()["asset_gaps"])

    def test_project_context_pack_survives_thread_switch_and_plan_notifications(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Context Project", root / "context.abproj", workspace_root=workspace, entry_mode="existing")
            service = ProjectContextService(projects)
            service.record_thread_hint("thread-a", {"name": "Design", "model": "deepseek-v4-pro", "reasoning_effort": "max"})
            service.record_thread_hint("thread-b", {"name": "Implement", "model": "kimi-k2.6", "reasoning_effort": "xhigh"})
            projects.switch_thread("thread-b")
            service.record_runtime_notification(
                "turn/plan/updated",
                {
                    "threadId": "thread-b",
                    "turnId": "turn-1",
                    "explanation": "Implement safely",
                    "plan": [{"step": "Use promoted sprites", "status": "pending"}],
                },
            )
            service.record_runtime_notification(
                "thread/goal/updated",
                {
                    "threadId": "thread-b",
                    "goal": {"objective": "Ship a playable tower slice", "status": "active"},
                },
            )
            snapshot = service.snapshot(thread_id="thread-b")
            pack_text = snapshot["context_pack"]["text"]
            self.assertIn("Context Project", pack_text)
            self.assertIn("Current thread: thread-b", pack_text)
            self.assertIn("Ship a playable tower slice", pack_text)
            self.assertIn("Use promoted sprites", pack_text)
            self.assertTrue((workspace / ".astrabridge" / "project_context_pack.json").is_file())
            self.assertTrue((workspace / ".astrabridge" / "project_context_state.json").is_file())

    def test_project_context_pack_includes_secret_free_real_file_map(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "index.html").write_text("<div id='app'></div>\n", encoding="utf-8")
            (workspace / "README.md").write_text("# Demo\n", encoding="utf-8")
            (workspace / "css").mkdir()
            (workspace / "css" / "style.css").write_text("body { color: #111; }\n", encoding="utf-8")
            (workspace / "js").mkdir()
            (workspace / "js" / "data.js").write_text("export const floors = [];\n", encoding="utf-8")
            (workspace / "js" / "ui.js").write_text("export function render() {}\n", encoding="utf-8")
            (workspace / "assets" / "images" / "sprites").mkdir(parents=True)
            (workspace / "assets" / "images" / "sprites" / "sprite_manifest.json").write_text(
                '{"sprites": {"heroine": "heroine.png"}}\n',
                encoding="utf-8",
            )
            (workspace / ".astrabridge").mkdir()
            (workspace / ".astrabridge" / "runtime_events.jsonl").write_text("Bearer unit-test-should-not-surface\n", encoding="utf-8")
            (workspace / ".codex").mkdir()
            (workspace / ".codex" / "config.toml").write_text("model = 'test'\n", encoding="utf-8")
            (workspace / ".env").write_text("API_KEY=unit_secret_value\n", encoding="utf-8")
            (workspace / "token_notes.md").write_text("do not expose\n", encoding="utf-8")

            projects = ProjectService(root / "projects.json")
            projects.create_project("File Map Project", root / "file-map.abproj", workspace_root=workspace, entry_mode="existing")
            pack = ProjectContextService(projects).snapshot(thread_id="thread-a")["context_pack"]
            file_map = pack["project_file_map"]
            serialized = json.dumps(pack, ensure_ascii=False)
            source_paths = {str(item.get("path") or "") for item in file_map["source_files"]}
            top_level_paths = {str(item.get("path") or "") for item in file_map["top_level"]}

            self.assertEqual(file_map["status"], "ok")
            self.assertIn("index.html", file_map["entry_files"])
            self.assertIn("index.html", source_paths)
            self.assertIn("js/data.js", source_paths)
            self.assertIn("js/ui.js", source_paths)
            self.assertIn("css/style.css", source_paths)
            self.assertIn("assets/images/sprites/sprite_manifest.json", source_paths)
            self.assertIn("assets", top_level_paths)
            self.assertNotIn(".astrabridge", top_level_paths)
            self.assertNotIn(".codex", top_level_paths)
            self.assertNotIn(".env", top_level_paths)
            self.assertNotIn("token_notes.md", source_paths)
            self.assertIn("Project file map (real paths observed", pack["text"])
            self.assertIn("js/ui.js", pack["text"])
            self.assertIn("do not invent paths such as game/map/...", pack["text"])
            self.assertFalse(any(path.startswith(".astrabridge/") for path in source_paths))
            self.assertNotIn("unit_secret_value", serialized)
            self.assertNotIn("Bearer unit-test", serialized)

    def test_project_context_pack_falls_back_to_logical_missing_thread_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Context Project", root / "context.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Same task",
                thread_id="thread-kimi-missing",
                settings={
                    "profile_id": "kimi-k26",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "permission_mode": "auto",
                },
            )
            tasks.record_goal("thread-kimi-missing", {"objective": "Keep the same task alive", "status": "active"})
            tasks.mark_provider_thread_missing("thread-kimi-missing", reason="startup_thread_missing")
            service = ProjectContextService(projects, task_service=tasks)

            snapshot = service.snapshot()
            pack = snapshot["context_pack"]
            pack_text = pack["text"]

            self.assertEqual(pack["project"]["current_thread_id"], "thread-kimi-missing")
            self.assertEqual(pack["selected_thread"]["thread_id"], "thread-kimi-missing")
            self.assertEqual(pack["selected_thread"]["missing_reason"], "startup_thread_missing")
            self.assertIn("Current thread: thread-kimi-missing", pack_text)
            self.assertIn("Selected thread availability: missing (startup_thread_missing)", pack_text)
            self.assertEqual(pack["task"]["task_id"], task["task_id"])

    def test_project_context_pack_includes_fork_thread_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Context Project", root / "context.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-deepseek",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-fork-1",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                    "name": "Forked branch",
                },
                role="fork",
                make_active=False,
            )

            pack = ProjectContextService(projects, task_service=tasks).snapshot(thread_id="thread-deepseek")["context_pack"]

            self.assertTrue(pack["task"]["fork_threads"])
            self.assertEqual(pack["task"]["fork_threads"][0]["thread_id"], "thread-fork-1")
            self.assertEqual(pack["task"]["fork_threads"][0]["role"], "fork")

    def test_project_context_prefers_task_aligned_dogfood_summary_over_placeholder_milestone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Context Project", root / "context.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            dogfood = DogfoodRunService(projects)
            task = tasks.create_task(
                "Magic Tower",
                thread_id="thread-ds",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.record_goal(
                "thread-ds",
                {
                    "objective": "Build a publishable three-floor Japanese-anime magical tower game while preserving asset continuity."
                },
            )
            dogfood.save(
                {
                    "enabled": True,
                    "goal": "HTTP CLEAN PROCESS GOAL",
                    "current_provider": "yunwu_image",
                    "next_step": "HTTP CLEAN PROCESS NEXT",
                }
            )
            dogfood.add_milestone(
                {
                    "label": "real tower step",
                    "provider": "deepseek",
                    "goal": "Build a publishable three-floor Japanese-anime magical tower game while preserving asset continuity.",
                    "next_action": "Ask DeepSeek to switch to a continuous background plate route.",
                    "status": "verified",
                }
            )
            dogfood.add_milestone(
                {
                    "label": "HTTP milestone on clean quoted process",
                    "provider": "deepseek",
                    "goal": "HTTP CLEAN PROCESS GOAL",
                    "next_action": "HTTP CLEAN PROCESS NEXT",
                    "status": "verified",
                }
            )

            pack = ProjectContextService(projects, dogfood_service=dogfood, task_service=tasks).snapshot(thread_id=task["active_provider_thread_id"])["context_pack"]

            self.assertEqual(
                pack["dogfood"]["goal"],
                "Build a publishable three-floor Japanese-anime magical tower game while preserving asset continuity.",
            )
            self.assertEqual(pack["dogfood"]["current_provider"], "deepseek")
            self.assertEqual(pack["dogfood"]["next_step"], "Ask DeepSeek to switch to a continuous background plate route.")
            self.assertEqual(pack["dogfood"]["latest_milestone"]["label"], "real tower step")
            self.assertNotIn("HTTP CLEAN PROCESS GOAL", pack["text"])

    def test_project_context_keeps_live_dogfood_provider_when_goal_is_already_aligned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Context Project", root / "context.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            dogfood = DogfoodRunService(projects)
            task = tasks.create_task(
                "Magic Tower",
                thread_id="thread-ds",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            objective = "Build a publishable three-floor Japanese-anime magical tower game while preserving asset continuity."
            tasks.record_goal("thread-ds", {"objective": objective})
            dogfood.save(
                {
                    "enabled": True,
                    "goal": objective,
                    "current_provider": "deepseek",
                    "next_step": "Let DeepSeek use the meadow plate route now.",
                }
            )
            dogfood.add_milestone(
                {
                    "label": "older image retry",
                    "provider": "yunwu_image",
                    "goal": objective,
                    "next_action": "Tighten the next transparent asset prompt.",
                    "status": "partial_pass",
                }
            )

            pack = ProjectContextService(projects, dogfood_service=dogfood, task_service=tasks).snapshot(thread_id=task["active_provider_thread_id"])["context_pack"]

            self.assertEqual(pack["dogfood"]["goal"], objective)
            self.assertEqual(pack["dogfood"]["current_provider"], "deepseek")
            self.assertEqual(pack["dogfood"]["next_step"], "Let DeepSeek use the meadow plate route now.")
            self.assertEqual(pack["dogfood"]["latest_milestone"]["label"], "older image retry")
            self.assertIn("provider=deepseek", pack["text"])

    def test_project_context_prefers_active_task_provider_when_run_provider_was_polluted_by_tool_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Context Project", root / "context.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            dogfood = DogfoodRunService(projects)
            task = tasks.create_task(
                "Magic Tower",
                thread_id="thread-ds",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            objective = "Build a publishable three-floor Japanese-anime magical tower game while preserving asset continuity."
            tasks.record_goal("thread-ds", {"objective": objective})
            dogfood.save(
                {
                    "enabled": True,
                    "goal": objective,
                    "current_provider": "yunwu_image",
                    "next_step": "Let DeepSeek continue the meadow route.",
                }
            )
            dogfood.add_milestone(
                {
                    "label": "recent image tool smoke",
                    "provider": "yunwu_image",
                    "goal": objective,
                    "next_action": "Check transparency and retry bad key icons.",
                    "status": "verified",
                }
            )

            pack = ProjectContextService(projects, dogfood_service=dogfood, task_service=tasks).snapshot(thread_id=task["active_provider_thread_id"])["context_pack"]

            self.assertEqual(pack["dogfood"]["goal"], objective)
            self.assertEqual(pack["dogfood"]["current_provider"], "deepseek")
            self.assertEqual(pack["dogfood"]["next_step"], "Let DeepSeek continue the meadow route.")
            self.assertEqual(pack["dogfood"]["latest_milestone"]["label"], "recent image tool smoke")
            self.assertIn("provider=deepseek", pack["text"])

    def test_project_context_does_not_surface_completed_task_plan_as_active_next_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Context Project", root / "context.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            dogfood = DogfoodRunService(projects)
            task = tasks.create_task(
                "Magic Tower",
                thread_id="thread-ds",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.record_goal(
                "thread-ds",
                {
                    "objective": "Build a publishable three-floor Japanese-anime magical tower game while preserving asset continuity."
                },
            )
            tasks.record_plan(
                "thread-ds",
                {
                    "steps": [
                        {"step": "Old completed step A", "status": "completed"},
                        {"step": "Old completed step B", "status": "completed"},
                    ]
                },
            )
            dogfood.save(
                {
                    "enabled": True,
                    "goal": "Build a publishable three-floor Japanese-anime magical tower game while preserving asset continuity.",
                    "current_provider": "deepseek",
                    "next_step": "Implement the meadow background route and verify with browser smoke.",
                }
            )

            pack = ProjectContextService(projects, dogfood_service=dogfood, task_service=tasks).snapshot(thread_id=task["active_provider_thread_id"])["context_pack"]
            text = str(pack["text"] or "")

            self.assertIn("Task plan record: previously completed", text)
            self.assertIn("Dogfood next step: Implement the meadow background route and verify with browser smoke.", text)
            self.assertNotIn("- Old completed step A", text)
            self.assertNotIn("- Old completed step B", text)

    def test_runtime_injects_project_context_pack_across_threads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Generic Project", root / "generic.abproj", workspace_root=workspace, entry_mode="existing")
            context = ProjectContextService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), project_context=context)
            runtime._cache_thread_entry("thread-1", {"name": "First", "model": "deepseek-v4-pro"})  # noqa: SLF001
            runtime._cache_thread_entry("thread-2", {"name": "Second", "model": "kimi-k2.6"})  # noqa: SLF001
            projects.switch_thread("thread-2")
            inputs = runtime._build_user_inputs("Resume work.", [], thread_id="thread-2")  # noqa: SLF001
            text = "\n".join(str(item.get("text") or "") for item in inputs if item.get("type") == "text")
            mentions = [item for item in inputs if item.get("type") == "mention"]
            self.assertIn("AstraBridge Project Context Pack", text)
            self.assertIn("Current thread: thread-2", text)
            self.assertIn("Second", text)
            self.assertIn("Context pack JSON paths are orientation references only", text)
            self.assertFalse(any(item.get("name") == "project_context_pack.json" for item in mentions))

    def test_project_context_state_rewrites_legacy_schema_and_emits_astrabridge_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Generic Project", root / "generic.abproj", workspace_root=workspace, entry_mode="existing")
            state_root = workspace / ".astrabridge"
            state_root.mkdir(parents=True, exist_ok=True)
            (state_root / "project_context_state.json").write_text(
                json.dumps(
                    {
                        "schema_version": "lcr-project-context-pack-v1",
                        "threads": {
                            "thread-1": {
                                "thread_id": "thread-1",
                                "name": "First",
                                "model": "deepseek-v4-pro",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            service = ProjectContextService(projects)
            state = service._state()  # noqa: SLF001
            snapshot = service.snapshot(thread_id="thread-1")

            self.assertEqual(state["schema_version"], "astrabridge-project-context-state-v1")
            self.assertEqual(snapshot["context_pack"]["schema_version"], "astrabridge-project-context-pack-v1")
            self.assertEqual(
                json.loads((state_root / "project_context_pack.json").read_text(encoding="utf-8"))["schema_version"],
                "astrabridge-project-context-pack-v1",
            )
            self.assertEqual(
                json.loads((state_root / "project_context_state.json").read_text(encoding="utf-8"))["schema_version"],
                "astrabridge-project-context-state-v1",
            )

    def test_project_context_pack_sanitizes_thread_names_with_auto_injected_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Generic Project", root / "generic.abproj", workspace_root=workspace, entry_mode="existing")
            context = ProjectContextService(projects)
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), project_context=context)
            runtime._cache_thread_entry(  # noqa: SLF001
                "thread-1",
                {
                    "name": "Please audit the current workspace --- AstraBridge Project Context Pack (auto-injected, secret-free)",
                    "provider_id": "yunwu",
                    "model": "gpt-5.5",
                },
            )
            projects.switch_thread("thread-1")

            pack = context.snapshot(thread_id="thread-1")["context_pack"]
            text = str(pack["text"] or "")

            self.assertIn("Selected thread settings: name=Please audit the current workspace", text)
            self.assertNotIn("Selected thread settings: name=Please audit the current workspace --- AstraBridge Project Context Pack", text)

    def test_dogfood_run_service_project_local_and_secret_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            service = DogfoodRunService(projects)

            saved = service.save(
                {
                    "enabled": True,
                    "goal": "Build a tower game",
                    "phase": "dogfood",
                    "usage": {"deepseek_cny": 3, "yunwu_images": 2},
                }
            )
            self.assertTrue(saved["run"]["enabled"])
            self.assertEqual(saved["run"]["budgets"]["kimi_cny"], 50)
            self.assertEqual(saved["run"]["budgets"]["deepseek_cny"], 50)
            self.assertEqual(saved["run"]["budgets"]["yunwu_gpt_usd"], 50)
            self.assertEqual(saved["run"]["usage"]["deepseek_cny"], 3)
            self.assertTrue((workspace / ".astrabridge" / "dogfood_run.json").exists())
            self.assertNotIn(".codex", saved["path"])
            with self.assertRaises(ValueError):
                service.save({"notes": ["Bearer unit-test-token"]})

            actions = service._browser_actions(  # noqa: SLF001
                [
                    {"type": "click_selector", "selector": "#btn-new-game", "timeout_ms": 1500},
                    {"type": "click_text_until_absent", "text": "Next", "max_clicks": 12, "settle_ms": 100},
                    {"type": "wait_for_text_absent", "text": "Next", "timeout_ms": 1500},
                    {"type": "expect_selector", "selector": "#grid-container"},
                    {"type": "expect_text", "text": "Floor"},
                ]
            )
            self.assertEqual(actions[0]["selector"], "#btn-new-game")
            self.assertEqual(actions[1]["type"], "click_text_until_absent")
            self.assertEqual(actions[1]["max_clicks"], 12)
            self.assertEqual(actions[2]["type"], "wait_for_text_absent")
            self.assertEqual(actions[3]["type"], "expect_selector")
            self.assertEqual(actions[4]["text"], "Floor")
            long_timeout = service._browser_smoke_subprocess_timeout(  # noqa: SLF001
                [{"type": "click_text_until_absent", "text": "Next", "timeout_ms": 30000, "max_clicks": 30, "settle_ms": 250}]
            )
            self.assertGreaterEqual(long_timeout, 45)
            with self.assertRaises(ValueError):
                service._browser_actions([{"type": "click_selector", "selector": "Bearer unit-test-token"}])  # noqa: SLF001

            final_assertions = service._browser_final_assertion_actions(  # noqa: SLF001
                {
                    "expect_text": ["Floor 1", "HP"],
                    "expect_selector": "#grid-container",
                    "forbidden_text": "Next",
                    "assert_timeout_ms": 2500,
                }
            )
            self.assertEqual(
                [item["type"] for item in final_assertions],
                ["expect_text", "expect_text", "expect_selector", "wait_for_text_absent"],
            )
            self.assertEqual(final_assertions[-1]["text"], "Next")
            self.assertEqual(final_assertions[0]["timeout_ms"], 2500)
            nested_assertions = service._browser_final_assertion_actions(  # noqa: SLF001
                {
                    "final_assertions": {
                        "expect_text": "Floor 1",
                        "forbidden_text": ["New Game", "Next"],
                        "assert_timeout_ms": 1800,
                    }
                }
            )
            self.assertEqual(
                [item["type"] for item in nested_assertions],
                ["expect_text", "wait_for_text_absent", "wait_for_text_absent"],
            )
            self.assertEqual(nested_assertions[0]["timeout_ms"], 1800)
            explicit_assertions = service._browser_final_assertion_actions(  # noqa: SLF001
                {"finalAssertions": [{"type": "expect_text", "text": "Sunlit Meadow", "timeout_ms": 1200}]}
            )
            self.assertEqual(explicit_assertions, [{"type": "expect_text", "text": "Sunlit Meadow", "timeout_ms": 1200}])
            with self.assertRaises(ValueError):
                service._browser_final_assertion_actions({"forbidden_text": "Authorization: token"})  # noqa: SLF001

    def test_dogfood_browser_smoke_action_limit_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "index.html").write_text("<!doctype html><title>ok</title>", encoding="utf-8")
            screenshot = root / "capture.png"
            screenshot.write_bytes(b"png")
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = DogfoodRunService(projects)

            smoke_30 = dogfood.browser_smoke(
                {
                    "url": (workspace / "index.html").resolve().as_uri(),
                    "label": "long but complete smoke",
                    "screenshot_path": str(screenshot),
                    "actions": [{"type": "wait_ms", "ms": 1} for _ in range(30)],
                }
            )
            self.assertEqual(len(smoke_30["browser_smoke"]["actions"]), 30)
            self.assertNotIn("action_warning", smoke_30["browser_smoke"])

            smoke_85 = dogfood.browser_smoke(
                {
                    "url": (workspace / "index.html").resolve().as_uri(),
                    "label": "truncated smoke",
                    "screenshot_path": str(screenshot),
                    "actions": [{"type": "wait_ms", "ms": 1} for _ in range(85)],
                }
            )
            self.assertEqual(len(smoke_85["browser_smoke"]["actions"]), 80)
            self.assertEqual(smoke_85["browser_smoke"]["action_warning"], "truncated_to_80_actions")

    def test_checkpoint_service_git_save_load_without_git_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            subprocess = __import__("subprocess")
            subprocess.check_call(["git", "init"], cwd=str(workspace), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.check_call(["git", "config", "user.email", "lcr@example.invalid"], cwd=str(workspace))
            subprocess.check_call(["git", "config", "user.name", "LCR Test"], cwd=str(workspace))
            (workspace / "game.txt").write_text("v1\n", encoding="utf-8")
            subprocess.check_call(["git", "add", "game.txt"], cwd=str(workspace))
            subprocess.check_call(["git", "commit", "-m", "initial"], cwd=str(workspace), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            before_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(workspace), text=True).strip()
            (workspace / "game.txt").write_text("v2\n", encoding="utf-8")
            (workspace / "new.txt").write_text("new\n", encoding="utf-8")

            projects = ProjectService(root / "projects.json")
            project = projects.create_project("Checkpoint", root / "checkpoint.abproj", workspace_root=workspace, entry_mode="existing")
            projects.cache_threads([{"id": "thread-1", "name": "Checkpoint thread"}])
            projects.switch_thread("thread-1")
            service = CheckpointService(projects)
            save = service.create({"description": "", "provider": "deepseek", "model": "deepseek-v4-pro"})

            after_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(workspace), text=True).strip()
            self.assertEqual(before_head, after_head)
            self.assertEqual(save["save"]["schema_version"], "astrabridge-checkpoint-v1")
            self.assertTrue(save["save"]["git"]["is_repo"])
            self.assertTrue((workspace / ".astrabridge" / "saves" / save["save"]["save_id"] / "git.diff").is_file())
            self.assertIn("Checkpoint thread", save["save"]["description"])

            (workspace / "game.txt").write_text("broken\n", encoding="utf-8")
            preview = service.load({"save_id": save["save"]["save_id"], "preview": True})
            self.assertTrue(preview["dirty"]["dirty"])
            with self.assertRaises(ValueError):
                service.load({"save_id": save["save"]["save_id"]})
            loaded = service.load({"save_id": save["save"]["save_id"], "confirm_dirty": True})
            self.assertTrue(loaded["loaded"])
            self.assertEqual((workspace / "game.txt").read_text(encoding="utf-8"), "v2\n")
            self.assertNotIn("Bearer", json.dumps(save))
            self.assertEqual(Path(project["project_file"]).suffix, ".abproj")

    def test_checkpoint_service_non_git_snapshot_excludes_secrets_and_saves(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "index.html").write_text("<h1>ok</h1>\n", encoding="utf-8")
            (workspace / ".env").write_text("API_KEY=unit_secret_value\n", encoding="utf-8")
            projects = ProjectService(root / "projects.json")
            projects.create_project("Snapshot", root / "snapshot.abproj", workspace_root=workspace, entry_mode="existing")
            state_root = workspace / ".astrabridge"
            (state_root / "runtime_events.jsonl").write_text('{"large":"event"}\n', encoding="utf-8")
            (state_root / "approvals.jsonl").write_text('{"large":"approval"}\n', encoding="utf-8")
            (state_root / ".thread_cache.json.atomic.tmp").write_text('{"transient":true}\n', encoding="utf-8")
            service = CheckpointService(projects)
            save = service.create({"description": "manual save"})
            save_dir = workspace / ".astrabridge" / "saves" / save["save"]["save_id"]
            manifest_text = (save_dir / "manifest.json").read_text(encoding="utf-8")
            self.assertNotIn("unit_secret_value", manifest_text)
            excluded = json.dumps(save["save"]["workspace"]["excluded"])
            self.assertIn(".env", excluded)
            self.assertIn(".astrabridge/runtime_events.jsonl", excluded)
            self.assertIn(".astrabridge/approvals.jsonl", excluded)
            self.assertIn(".astrabridge/.thread_cache.json.atomic.tmp", excluded)
            with zipfile.ZipFile(save_dir / "workspace.zip", "r") as archive:
                self.assertNotIn(".astrabridge/.thread_cache.json.atomic.tmp", set(archive.namelist()))

            (workspace / "index.html").write_text("<h1>changed</h1>\n", encoding="utf-8")
            loaded = service.load({"save_id": save["save"]["save_id"], "confirm_dirty": True})
            self.assertTrue(loaded["loaded"])
            self.assertEqual((workspace / "index.html").read_text(encoding="utf-8"), "<h1>ok</h1>\n")

    def test_checkpoint_service_prunes_heavy_lcr_asset_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "index.html").write_text("<h1>ok</h1>\n", encoding="utf-8")
            assets_root = workspace / ".astrabridge" / "assets"
            (assets_root / "generated").mkdir(parents=True)
            (assets_root / "sliced").mkdir(parents=True)
            (assets_root / "sliced_failed_20260614_oversegmented").mkdir(parents=True)
            (assets_root / "asset_registry.json").write_text('{"assets":[]}\n', encoding="utf-8")
            (assets_root / "asset_context_pack.json").write_text('{"summary":{"total":0}}\n', encoding="utf-8")
            for directory in ["generated", "sliced", "sliced_failed_20260614_oversegmented"]:
                for index in range(8):
                    (assets_root / directory / f"artifact-{index}.png").write_bytes(b"\x89PNG\r\n")

            projects = ProjectService(root / "projects.json")
            projects.create_project("Snapshot", root / "snapshot.abproj", workspace_root=workspace, entry_mode="existing")
            service = CheckpointService(projects)
            save = service.create({"description": "pruned save"})

            save_dir = workspace / ".astrabridge" / "saves" / save["save"]["save_id"]
            with zipfile.ZipFile(save_dir / "workspace.zip", "r") as archive:
                names = set(archive.namelist())
            self.assertIn(".astrabridge/assets/asset_registry.json", names)
            self.assertIn(".astrabridge/assets/asset_context_pack.json", names)
            self.assertNotIn(".astrabridge/assets/generated/artifact-0.png", names)
            self.assertNotIn(".astrabridge/assets/sliced/artifact-0.png", names)
            excluded = json.dumps(save["save"]["workspace"]["excluded"])
            self.assertIn(".astrabridge/assets/generated", excluded)
            self.assertIn(".astrabridge/assets/sliced", excluded)
            self.assertIn(".astrabridge/assets/sliced_failed_20260614_oversegmented", excluded)

    def test_llm_api_manager_vault_login_password_change_and_no_plaintext(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profiles = ProfileService(root / "profiles.json")
            config = RouterConfigService(profiles, root / "router.json")
            manager = LlmApiManagerService(config, DummyRouter(), root / "manager")

            created = manager.create_user({"username": "user", "password": "correct horse battery staple"})
            self.assertEqual(created["session"]["mode"], "managed_user")
            self.assertNotIn("_unlock_key", created["session"])
            manager.save_key({"provider_id": "deepseek", "label": "DeepSeek main", "env_key": "DEEPSEEK_API_KEY", "secret": "unit_secret_deepseek_value"})

            vault_text = (root / "manager" / "users" / "user" / "vault.abvault").read_text(encoding="utf-8")
            self.assertNotIn("unit_secret_deepseek_value", vault_text)
            self.assertNotIn("correct horse", vault_text)

            manager.logout()
            with self.assertRaises(PermissionError):
                manager.login({"username": "user", "password": "wrong"})
            manager.login({"username": "user", "password": "correct horse battery staple"})
            self.assertEqual(manager.list_keys()["keys"][0]["fingerprint"], hashlib.sha256(b"unit_secret_deepseek_value").hexdigest()[:12])

            manager.change_password({"username": "user", "old_password": "correct horse battery staple", "new_password": "new battery staple"})
            manager.logout()
            with self.assertRaises(PermissionError):
                manager.login({"username": "user", "password": "correct horse battery staple"})
            relogged = manager.login({"username": "user", "password": "new battery staple"})
            self.assertEqual(relogged["session"]["key_count"], 1)

    def test_llm_api_manager_multi_user_isolation_key_redaction_and_env_cleanup(self) -> None:
        original = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                profiles = ProfileService(root / "profiles.json")
                config = RouterConfigService(profiles, root / "router.json")
                config.upsert_provider(
                    {
                        "id": "deepseek",
                        "display_name": "DeepSeek",
                        "adapter_type": "chat",
                        "base_url": "https://api.deepseek.com",
                        "default_model": "deepseek-v4-pro",
                        "env_key": "DEEPSEEK_API_KEY",
                    }
                )
                manager = LlmApiManagerService(config, DummyRouter(), root / "manager")

                manager.create_user({"username": "alice", "password": "alice-password-123"})
                saved = manager.save_key({"provider_id": "deepseek", "label": "Alice DS", "secret": "unit_secret_alice_deepseek", "env_key": "DEEPSEEK_API_KEY"})
                self.assertNotIn("secret", saved["key"])
                self.assertNotIn("unit_secret_alice", json.dumps(saved))

                profile = profiles.get_profile("deepseek-default")
                injected = manager.inject_profile_key(profile)
                self.assertTrue(injected["injected"])
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "unit_secret_alice_deepseek")
                manager.logout()
                self.assertNotIn("DEEPSEEK_API_KEY", os.environ)

                manager.create_user({"username": "bob", "password": "bob-password-123"})
                self.assertEqual(manager.list_keys()["keys"], [])
                manager.logout()
                os.environ["DEEPSEEK_API_KEY"] = "preexisting-env-key"
                manager.login({"username": "alice", "password": "alice-password-123"})
                self.assertEqual(len(manager.list_keys()["keys"]), 1)
                manager.inject_profile_key(profile)
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "unit_secret_alice_deepseek")
                manager.logout()
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "preexisting-env-key")
        finally:
            if original is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = original

    def test_llm_api_manager_user_profile_is_public_and_secret_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profiles = ProfileService(root / "profiles.json")
            config = RouterConfigService(profiles, root / "router.json")
            manager = LlmApiManagerService(config, DummyRouter(), root / "manager")
            manager.create_user({"username": "user", "password": "vault-password-123"})

            saved = manager.save_user_profile(
                {
                    "username": "user",
                    "display_name": "Cy User",
                    "avatar_path": "D:\\avatars\\cy.png",
                }
            )
            self.assertEqual(saved["profile"]["display_name"], "Cy User")
            self.assertEqual(saved["session"]["profile"]["avatar_path"], "D:\\avatars\\cy.png")
            profile_text = (root / "manager" / "users" / "user" / "profile.json").read_text(encoding="utf-8")
            self.assertNotIn("unit_secret_", profile_text)

            with self.assertRaises(ValueError):
                manager.save_user_profile({"username": "user", "avatar_path": "Bearer secret"})

    def test_llm_api_manager_effective_catalog_filters_managed_and_marks_anonymous_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profiles = ProfileService(root / "profiles.json")
            config = RouterConfigService(profiles, root / "router.json")
            config.upsert_provider(
                {
                    "id": "deepseek",
                    "display_name": "DeepSeek",
                    "adapter_type": "chat",
                    "base_url": "https://api.deepseek.com",
                    "default_model": "deepseek-v4-pro",
                    "env_key": "DEEPSEEK_API_KEY",
                }
            )
            config.upsert_provider(
                {
                    "id": "kimi",
                    "display_name": "Kimi",
                    "adapter_type": "chat",
                    "base_url": "https://api.moonshot.cn/v1",
                    "default_model": "kimi-k2.6",
                    "env_key": "KIMI_API_KEY",
                }
            )
            config.upsert_model(
                {
                    "id": "deepseek/deepseek-v4-pro",
                    "provider": "deepseek",
                    "native_model": "deepseek-v4-pro",
                    "display_name": "DeepSeek V4 Pro",
                    "enabled": True,
                    "advertised_context_window": 1000000,
                    "ui_context_hint_only": True,
                    "adapter_profile": "default",
                }
            )
            class DocsHandler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:  # noqa: N802
                    body = b"DeepSeek docs"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, format: str, *args) -> None:  # noqa: A003
                    return

            docs = ThreadingHTTPServer(("127.0.0.1", 0), DocsHandler)
            docs_thread = threading.Thread(target=docs.serve_forever, daemon=True)
            docs_thread.start()
            pro_model = next(item for item in config.models() if item["id"] == "deepseek/deepseek-v4-pro")
            config.upsert_model({**pro_model, "source_urls": [f"http://127.0.0.1:{docs.server_address[1]}/docs"]})
            manager = LlmApiManagerService(config, DummyRouter(), root / "manager")
            try:
                anonymous = manager.effective_catalog()
                self.assertEqual(anonymous["mode"], "anonymous")
                self.assertIn("deepseek/deepseek-v4-pro", {item["id"] for item in anonymous["models"]})

                manager.create_user({"username": "user", "password": "vault-password-123"})
                manager.save_key({"provider_id": "deepseek", "label": "DeepSeek", "secret": "unit_secret_deepseek_value", "env_key": "DEEPSEEK_API_KEY"})
                locked_down = manager.effective_catalog()
                self.assertEqual(locked_down["models"], [])

                health = manager.run_health({"model_ids": ["deepseek/deepseek-v4-pro"], "efforts": ["high"], "temperatures": [0], "web_smoke": True})
                self.assertEqual(health["model_health"]["deepseek/deepseek-v4-pro"]["tool_web_search_support"], "verified")
                self.assertEqual(health["model_health"]["deepseek/deepseek-v4-pro"]["web_smoke_status"], "pass")
                stream_health = manager.run_health({"model_ids": ["deepseek/deepseek-v4-pro"], "efforts": ["high"], "temperatures": [0], "stream": True})
                self.assertEqual(stream_health["model_health"]["deepseek/deepseek-v4-pro"]["streaming"], "pass")
                managed = manager.effective_catalog()
                self.assertEqual({item["id"] for item in managed["models"]}, {"deepseek/deepseek-v4-pro"})
                self.assertTrue(managed["models"][0]["verified"])
            finally:
                docs.shutdown()
                docs.server_close()

    def test_runtime_config_embeds_isolated_mcp_config(self) -> None:
        original = os.environ.pop("TEST_MCP_PROVIDER_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                mcp = McpConfigService(root / "mcp_servers.json")
                mcp.apply_context7_preset()
                service = RuntimeConfigService(root / "embedded_codex_home", mcp_config=mcp)
                service.load_secret(
                    {
                        "profile_id": "provider-test",
                        "label": "Provider Test",
                        "provider_id": "openai",
                        "base_url": "https://example.com/v1",
                        "model": "test-model",
                        "reasoning_effort": "high",
                        "wire_api": "responses",
                        "env_key": "TEST_MCP_PROVIDER_KEY",
                        "auth_mode": "session_paste",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    },
                    session_key="unit_secret_test_value_123456",
                )
                config_text = (root / "embedded_codex_home" / "config.toml").read_text(encoding="utf-8")
                self.assertIn("[mcp_servers.context7]", config_text)
                self.assertIn('command = "npx"', config_text)
                self.assertNotIn("unit_secret_test_value_123456", config_text)
        finally:
            if original is None:
                os.environ.pop("TEST_MCP_PROVIDER_KEY", None)
            else:
                os.environ["TEST_MCP_PROVIDER_KEY"] = original

    def test_runtime_service_rewrites_windows_mcp_paths_for_wsl(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project = ProjectService(root / "projects.json")
            project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(project, ModalService(project.require_shell_state_root))
            config_text = "\n".join(
                [
                    'model_catalog_json = "C:\\\\Users\\\\cyz19\\\\AppData\\\\Local\\\\LCR\\\\cx\\\\models\\\\astrabridge-models.json"',
                    'base_url = "http://127.0.0.1:8787/v1"',
                    "",
                    "[mcp_servers.yunwu_image]",
                    'command = "C:\\\\Users\\\\cyz19\\\\.cache\\\\codex-runtimes\\\\codex-primary-runtime\\\\dependencies\\\\python\\\\python.exe"',
                    'args = ["-u", "D:\\\\Google One\\\\research-os-template\\\\apps\\\\astrabridge-sidecar\\\\astrabridge_sidecar\\\\yunwu_image_mcp_server.py"]',
                    'cwd = "D:\\\\Google One\\\\research-os-template\\\\apps\\\\astrabridge-sidecar"',
                    "",
                    "[mcp_servers.yunwu_image.env]",
                    'PYTHONPATH = "D:\\\\Google One\\\\research-os-template\\\\apps\\\\astrabridge-sidecar"',
                ]
            )

            rewritten = runtime._rewrite_wsl_config_text(  # type: ignore[attr-defined]
                config_text,
                codex_home_wsl_abs="/home/user/.local/share/astrabridge/codex-home",
                router_base_url="http://10.255.255.254:8787",
                sidecar_source_wsl="/mnt/d/Google One/research-os-template/apps/astrabridge-sidecar",
                sidecar_link_wsl="/home/user/.local/share/astrabridge/sidecar-src",
            )

            self.assertIn('model_catalog_json = "/home/user/.local/share/astrabridge/codex-home/models/astrabridge-models.json"', rewritten)
            self.assertIn('base_url = "http://10.255.255.254:8787/v1"', rewritten)
            self.assertIn('command = "python3"', rewritten)
            self.assertIn('"/home/user/.local/share/astrabridge/sidecar-src/astrabridge_sidecar/yunwu_image_mcp_server.py"', rewritten)
            self.assertIn('cwd = "/home/user/.local/share/astrabridge/sidecar-src"', rewritten)
            self.assertIn('PYTHONPATH = "/home/user/.local/share/astrabridge/sidecar-src"', rewritten)
            self.assertNotIn("C:\\\\Users", rewritten)
            self.assertNotIn("D:\\\\Google One", rewritten)
            self.assertNotIn("/mnt/d/Google One", rewritten)

    def test_runtime_service_hydrates_recent_events_from_runtime_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project = ProjectService(root / "projects.json")
            project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            state_root = project.require_shell_state_root()
            events_path = state_root / "runtime_events.jsonl"
            persisted = [
                {
                    "index": 42,
                    "type": "notification",
                    "method": "thread/tokenUsage/updated",
                    "timestamp": "2026-06-12T00:00:01+00:00",
                    "params": {
                        "threadId": "thread-compact",
                        "tokenUsage": {"total": {"totalTokens": 91}, "modelContextWindow": 100},
                    },
                },
                {
                    "index": 43,
                    "type": "notification",
                    "method": "item/completed",
                    "timestamp": "2026-06-12T00:00:03+00:00",
                    "params": {
                        "threadId": "thread-compact",
                        "item": {"type": "contextCompaction", "id": "compact-1"},
                        "authorization": "Bearer unit",
                    },
                },
            ]
            events_path.write_text("\n".join(json.dumps(item) for item in persisted) + "\n", encoding="utf-8")

            runtime = RuntimeService(project, ModalService(project.require_shell_state_root))
            runtime.record_supervisor_event({"event": "session_started"})
            listed = runtime.list_events(after=0)
            self.assertEqual(listed["cursor"], 3)
            self.assertEqual(listed["events"][0]["index"], 0)
            self.assertEqual(listed["events"][1]["params"]["item"]["type"], "contextCompaction")
            self.assertEqual(listed["events"][2]["event"], "session_started")
            self.assertNotIn("unit_secret_test_value", json.dumps(listed))

    def test_runtime_service_restore_startup_runtime_marks_missing_thread(self) -> None:
        class FakeClient:
            def is_running(self) -> bool:
                return True

            def request(self, method, params, timeout=None):  # noqa: ANN001
                if method == "thread/read":
                    raise JsonRpcError("thread not found: thread-stale")
                raise AssertionError(f"Unexpected method: {method}")

        original = os.environ.pop("TEST_STARTUP_RUNTIME_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = root / "workspace"
                workspace.mkdir()
                projects = ProjectService(root / "projects.json")
                projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
                projects.switch_thread("thread-stale")
                tasks = TaskService(projects)
                tasks.create_task(
                    "Recovered task",
                    thread_id="thread-stale",
                    settings={
                        "profile_id": "deepseek-default",
                        "provider_id": "deepseek",
                        "model": "deepseek-v4-pro",
                        "reasoning_effort": "high",
                        "permission_mode": "auto",
                    },
                )
                runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
                runtime._ensure_client = lambda runtime_status: FakeClient()  # type: ignore[method-assign]  # noqa: ARG005

                result = runtime.restore_startup_runtime(
                    {
                        "profile_id": "deepseek-default",
                        "label": "DeepSeek",
                        "provider_id": "deepseek",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-v4-pro",
                        "reasoning_effort": "high",
                        "wire_api": "chat",
                        "env_key": "TEST_STARTUP_RUNTIME_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    },
                    thread_id="thread-stale",
                )

                self.assertTrue(result["restored"])
                self.assertTrue(result["client_started"])
                self.assertFalse(result["thread_exists"])
                current_task = tasks.current_task()
                provider_entry = current_task["provider_threads"][0]
                self.assertEqual(provider_entry["missing_reason"], "startup_thread_missing")
                self.assertTrue(
                    any(
                        event.get("type") == "startup_runtime_restored"
                        and event.get("thread_id") == "thread-stale"
                        and event.get("thread_exists") is False
                        for event in runtime._events
                    )
                )
        finally:
            if original is None:
                os.environ.pop("TEST_STARTUP_RUNTIME_KEY", None)
            else:
                os.environ["TEST_STARTUP_RUNTIME_KEY"] = original

    def test_runtime_service_permission_mapping_and_attachment_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project = ProjectService(root / "projects.json")
            project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(project, ModalService(project.require_shell_state_root))

            ask = runtime._turn_permission_overrides("ask")  # type: ignore[attr-defined]
            auto = runtime._turn_permission_overrides("auto")  # type: ignore[attr-defined]
            full = runtime._turn_permission_overrides("full")  # type: ignore[attr-defined]

            self.assertEqual(ask["approvalPolicy"], "untrusted")
            self.assertEqual(auto["sandboxPolicy"]["type"], "workspaceWrite")
            self.assertEqual(full["sandboxPolicy"]["type"], "dangerFullAccess")

            outside = root / "diagram.png"
            outside.write_bytes(b"png")
            staged = runtime._stage_attachment(str(outside), "diagram.png")  # type: ignore[attr-defined]
            self.assertTrue(staged.exists())
            self.assertIn(".astrabridge\\attachments", str(staged))

    def test_runtime_config_collaboration_and_compaction_metadata(self) -> None:
        original_key = os.environ.pop("TEST_DEEPSEEK_VERIFY_KEY", None)
        original_compact = os.environ.get("ASTRABRIDGE_AUTO_COMPACT_TOKEN_LIMIT")
        try:
            os.environ["ASTRABRIDGE_AUTO_COMPACT_TOKEN_LIMIT"] = "4096"
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config = RuntimeConfigService(root / "embedded_codex_home")
                profile = {
                    "profile_id": "deepseek-verify-default",
                    "label": "DeepSeek Verify",
                    "provider_id": "deepseek-verify",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "wire_api": "chat",
                    "env_key": "TEST_DEEPSEEK_VERIFY_KEY",
                    "auth_mode": "session_paste",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
                config.load_secret(profile, session_key="unit_secret_deepseek_test")
                config_text = (root / "embedded_codex_home" / "config.toml").read_text(encoding="utf-8")
                self.assertIn('model = "deepseek-verify/deepseek-v4-pro"', config_text)
                self.assertIn("model_catalog_json =", config_text)
                self.assertIn("model_context_window = 1000000", config_text)
                self.assertIn("model_auto_compact_token_limit = 4096", config_text)
                model_catalog = json.loads((root / "embedded_codex_home" / "models" / "astrabridge-models.json").read_text(encoding="utf-8"))
                model_info = model_catalog["models"][0]
                self.assertEqual(model_info["slug"], "deepseek-verify/deepseek-v4-pro")
                self.assertEqual(model_info["input_modalities"], ["text"])
                self.assertFalse(model_info["supports_parallel_tool_calls"])
                self.assertFalse(model_info["supports_search_tool"])
                self.assertIsNone(model_info["apply_patch_tool_type"])
                self.assertEqual(model_info["web_search_tool_type"], "text")
                self.assertEqual(model_info["auto_compact_token_limit"], 4096)

                project = ProjectService(root / "projects.json")
                workspace = root / "workspace"
                workspace.mkdir()
                project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
                runtime = RuntimeService(project, ModalService(project.require_shell_state_root), runtime_config=config)
                mode = runtime._collaboration_mode_params(  # type: ignore[attr-defined]
                    profile=profile,
                    model="deepseek-v4-pro",
                    effort="max",
                    collaboration_mode="plan",
                )
                self.assertEqual(mode["mode"], "plan")
                self.assertEqual(mode["settings"]["model"], "deepseek-verify/deepseek-v4-pro")
                self.assertIsNone(mode["settings"]["developer_instructions"])
        finally:
            if original_key is None:
                os.environ.pop("TEST_DEEPSEEK_VERIFY_KEY", None)
            else:
                os.environ["TEST_DEEPSEEK_VERIFY_KEY"] = original_key
            if original_compact is None:
                os.environ.pop("ASTRABRIDGE_AUTO_COMPACT_TOKEN_LIMIT", None)
            else:
                os.environ["ASTRABRIDGE_AUTO_COMPACT_TOKEN_LIMIT"] = original_compact

    def test_runtime_signature_ignores_require_secret_mode_but_tracks_key_fingerprint(self) -> None:
        original_key = os.environ.get("TEST_SIGNATURE_KEY")
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                config = RuntimeConfigService(root / "embedded_codex_home")
                profile = {
                    "profile_id": "signature-provider",
                    "label": "Signature Provider",
                    "provider_id": "signature-provider",
                    "base_url": "https://example.com",
                    "model": "signature-model",
                    "reasoning_effort": "high",
                    "wire_api": "chat",
                    "env_key": "TEST_SIGNATURE_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }

                os.environ["TEST_SIGNATURE_KEY"] = "unit_secret_signature_one"
                with_secret = config.prepare_profile(profile, require_secret=True)
                without_secret = config.prepare_profile(profile, require_secret=False)
                self.assertEqual(config.runtime_signature(with_secret), config.runtime_signature(without_secret))

                os.environ["TEST_SIGNATURE_KEY"] = "unit_secret_signature_two"
                rotated = config.prepare_profile(profile, require_secret=True)
                self.assertNotEqual(config.runtime_signature(with_secret), config.runtime_signature(rotated))

                with_image = config.prepare_profile({**profile, "input_modalities": ["text", "image"]}, require_secret=True)
                self.assertNotEqual(config.runtime_signature(rotated), config.runtime_signature(with_image))
        finally:
            if original_key is None:
                os.environ.pop("TEST_SIGNATURE_KEY", None)
            else:
                os.environ["TEST_SIGNATURE_KEY"] = original_key

    def test_runtime_service_wsl_probe_rejects_windowsapps_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project = ProjectService(root / "projects.json")
            project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            project.update_project({"ui_preferences": {"execution_host": "wsl", "wsl_distro": "Ubuntu-24.04"}})
            runtime = RuntimeService(project, ModalService(project.require_shell_state_root))

            def fake_capture(command: list[str]) -> dict[str, object]:
                joined = " ".join(command)
                if "-l -q" in joined:
                    return {"returncode": 0, "stdout": "Ubuntu-24.04\n", "stderr": ""}
                if "bash -lc" in joined:
                    return {
                        "returncode": 126,
                        "stdout": "",
                        "stderr": "codex resolves to WindowsApps inside WSL: /mnt/c/Program Files/WindowsApps/OpenAI.Codex/app/resources/codex",
                    }
                return {"returncode": 0, "stdout": "", "stderr": ""}

            runtime._run_capture = fake_capture  # type: ignore[method-assign]
            with self.assertRaisesRegex(RuntimeError, "Linux-native Codex CLI"):
                runtime._resolve_launch_target({"codex_home": str(root / "cx")})  # type: ignore[attr-defined]

    def test_runtime_service_records_stale_wsl_app_server_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project = ProjectService(root / "projects.json")
            project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(project, ModalService(project.require_shell_state_root))

            def fake_capture(command: list[str]) -> dict[str, object]:
                self.assertIn("astrabridge/bin/codex app-server", " ".join(command))
                return {"returncode": 0, "stdout": "101,202\n", "stderr": ""}

            runtime._run_capture = fake_capture  # type: ignore[method-assign]
            runtime._terminate_stale_astrabridge_wsl_app_servers("wsl.exe", ["-d", "Ubuntu-24.04"])  # type: ignore[attr-defined]

            cleanup_events = [
                event for event in runtime.list_events().get("events", []) if event.get("type") == "wsl_app_server_cleanup"
            ]
            self.assertEqual(cleanup_events[-1]["terminated_pids"], ["101", "202"])

    def test_router_service_auto_selects_another_port_when_requested_port_is_owned(self) -> None:
        class EmptyHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        listener = ThreadingHTTPServer(("127.0.0.1", 0), EmptyHandler)
        try:
            port = int(listener.server_address[1])
            profiles = ProfileService()
            router = RouterService(profiles, host="127.0.0.1", port=port)
            router.start()
            status = router.status()
            self.assertTrue(status["running"])
            self.assertTrue(status["port_auto_selected"])
            self.assertEqual(status["requested_port"], port)
            self.assertNotEqual(status["listen_port"], port)
            router.stop()
        finally:
            listener.server_close()

    def test_runtime_service_wsl_router_probe_requires_matching_current_router(self) -> None:
        original_port = os.environ.get("ASTRABRIDGE_PORT")
        original_fingerprint = os.environ.get("ASTRABRIDGE_TOKEN_FINGERPRINT")
        try:
            os.environ["ASTRABRIDGE_PORT"] = "8787"
            os.environ["ASTRABRIDGE_TOKEN_FINGERPRINT"] = "expected123"
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = root / "workspace"
                workspace.mkdir()
                project = ProjectService(root / "projects.json")
                project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
                runtime = RuntimeService(project, ModalService(project.require_shell_state_root))

                def fake_capture(command: list[str]) -> dict[str, object]:
                    joined = " ".join(command)
                    if "ip route show default" in joined:
                        return {"returncode": 0, "stdout": "default via 172.23.112.1 dev eth0\n", "stderr": ""}
                    if "cat /etc/resolv.conf" in joined:
                        return {"returncode": 0, "stdout": "nameserver 10.255.255.254\n", "stderr": ""}
                    if "/readyz" in joined:
                        return {
                            "returncode": 0,
                            "stdout": "\n".join(
                                [
                                    json.dumps(
                                        {
                                            "host": "172.23.112.1",
                                            "base_url": "http://172.23.112.1:8787",
                                            "service": "astrabridge",
                                            "token_fingerprint": "stale999",
                                        }
                                    ),
                                    json.dumps(
                                        {
                                            "host": "host.docker.internal",
                                            "base_url": "http://host.docker.internal:8787",
                                            "service": "astrabridge",
                                            "token_fingerprint": "expected123",
                                        }
                                    ),
                                ]
                            ),
                            "stderr": "",
                        }
                    return {"returncode": 0, "stdout": "", "stderr": ""}

                runtime._run_capture = fake_capture  # type: ignore[method-assign]
                self.assertEqual(
                    runtime._wsl_router_base_url("wsl.exe", ["-d", "Ubuntu-24.04"]),  # type: ignore[attr-defined]
                    "http://host.docker.internal:8787",
                )
        finally:
            if original_port is None:
                os.environ.pop("ASTRABRIDGE_PORT", None)
            else:
                os.environ["ASTRABRIDGE_PORT"] = original_port
            if original_fingerprint is None:
                os.environ.pop("ASTRABRIDGE_TOKEN_FINGERPRINT", None)
            else:
                os.environ["ASTRABRIDGE_TOKEN_FINGERPRINT"] = original_fingerprint

    def test_runtime_service_wsl_path_export_quotes_windows_path_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project = ProjectService(root / "projects.json")
            project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(project, ModalService(project.require_shell_state_root))

            path_export = runtime._wsl_codex_path_export()  # type: ignore[attr-defined]
            self.assertEqual(path_export, 'export PATH="$HOME/.local/share/astrabridge/bin:$PATH"; ')
            probe = runtime._wsl_codex_probe_command("$HOME/.local/share/astrabridge/bin/codex")  # type: ignore[attr-defined]
            self.assertIn("command -v codex", probe)
            self.assertNotIn("LCR_CODEX_BIN", probe)

    def test_runtime_service_wsl_launch_defaults_to_lcr_managed_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project = ProjectService(root / "projects.json")
            project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            project.update_project({"ui_preferences": {"execution_host": "wsl", "wsl_distro": "Ubuntu-24.04"}})
            codex_home = root / "cx"
            mcp_config = McpConfigService(root / "mcp_servers.json")
            mcp_config.apply_yunwu_image_preset()
            runtime_config = RuntimeConfigService(codex_home=codex_home, mcp_config=mcp_config)
            runtime = RuntimeService(project, ModalService(project.require_shell_state_root), runtime_config=runtime_config)
            (codex_home / "models").mkdir(parents=True)
            (codex_home / "config.toml").write_text('model_catalog_json = "C:\\\\tmp\\\\models\\\\astrabridge-models.json"\n', encoding="utf-8")
            (codex_home / "models" / "astrabridge-models.json").write_text('{"models":[]}', encoding="utf-8")
            original_router_token = os.environ.get("CODEX_ROUTER_API_KEY")
            original_yunwu_key = os.environ.get("YUNWU_API_KEY")
            os.environ["CODEX_ROUTER_API_KEY"] = "router-token-for-wsl-test"
            os.environ["YUNWU_API_KEY"] = "yunwu-token-for-wsl-test"

            def fake_capture(command: list[str]) -> dict[str, object]:
                joined = " ".join(command)
                if "-l -q" in joined:
                    return {"returncode": 0, "stdout": "Ubuntu-24.04\n", "stderr": ""}
                if 'printf "%s" "$HOME"' in joined:
                    return {"returncode": 0, "stdout": "/home/demo", "stderr": ""}
                if "ip route show default" in joined:
                    return {"returncode": 0, "stdout": "default via 10.255.255.254 dev eth0 proto kernel", "stderr": ""}
                if "nameserver" in joined and "/etc/resolv.conf" in joined:
                    return {"returncode": 0, "stdout": "10.255.255.254", "stderr": ""}
                if "astrabridge/bin/codex app-server" in joined and "/proc" in joined:
                    return {"returncode": 0, "stdout": "", "stderr": ""}
                if "/readyz" in joined:
                    return {
                        "returncode": 0,
                        "stdout": json.dumps(
                            {
                                "host": "10.255.255.254",
                                "base_url": "http://10.255.255.254:8787",
                                "service": "astrabridge",
                                "token_fingerprint": os.environ.get("ASTRABRIDGE_TOKEN_FINGERPRINT") or "test",
                            }
                        ),
                        "stderr": "",
                    }
                if "config.wsl.toml" in joined:
                    return {"returncode": 0, "stdout": "", "stderr": ""}
                if "bash -lc" in joined:
                    self.assertIn("command -v codex", joined)
                    return {"returncode": 0, "stdout": "codex-cli 0.139.0", "stderr": ""}
                return {"returncode": 0, "stdout": "", "stderr": ""}

            try:
                runtime._run_capture = fake_capture  # type: ignore[method-assign]
                target = runtime._resolve_launch_target({"codex_home": str(codex_home)})  # type: ignore[attr-defined]
                joined_launch = " ".join(target["launch_command"])
                self.assertIn("exec env -i", joined_launch)
                self.assertIn("/.astrabridge/runtime-cwd", joined_launch)
                self.assertTrue((workspace / ".astrabridge" / "runtime-cwd").is_dir())
                self.assertIn("PATH=/home/demo/.local/share/astrabridge/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", joined_launch)
                self.assertIn('CODEX_ROUTER_API_KEY="${CODEX_ROUTER_API_KEY:-}"', joined_launch)
                self.assertIn('YUNWU_API_KEY="${YUNWU_API_KEY:-}"', joined_launch)
                self.assertIn('ASTRABRIDGE_WORKSPACE_ROOT="${ASTRABRIDGE_WORKSPACE_ROOT:-}"', joined_launch)
                self.assertIn('ASTRABRIDGE_WORKSPACE_ROOT_WSL="${ASTRABRIDGE_WORKSPACE_ROOT_WSL:-}"', joined_launch)
                self.assertNotIn("router-token-for-wsl-test", joined_launch)
                self.assertNotIn("yunwu-token-for-wsl-test", joined_launch)
                self.assertEqual(target["env_updates"]["CODEX_ROUTER_API_KEY"], "router-token-for-wsl-test")
                self.assertEqual(target["env_updates"]["YUNWU_API_KEY"], "yunwu-token-for-wsl-test")
                self.assertEqual(target["env_updates"]["ASTRABRIDGE_WORKSPACE_ROOT"], str(workspace))
                self.assertTrue(str(target["env_updates"]["ASTRABRIDGE_WORKSPACE_ROOT_WSL"]).startswith("/mnt/"))
                self.assertIn("CODEX_ROUTER_API_KEY", target["env_updates"]["WSLENV"])
                self.assertIn("YUNWU_API_KEY", target["env_updates"]["WSLENV"])
                self.assertIn("ASTRABRIDGE_WORKSPACE_ROOT", target["env_updates"]["WSLENV"])
                self.assertIn("ASTRABRIDGE_WORKSPACE_ROOT_WSL", target["env_updates"]["WSLENV"])
                self.assertIn("/home/demo/.local/share/astrabridge/bin/codex app-server", joined_launch)
            finally:
                if original_router_token is None:
                    os.environ.pop("CODEX_ROUTER_API_KEY", None)
                else:
                    os.environ["CODEX_ROUTER_API_KEY"] = original_router_token
                if original_yunwu_key is None:
                    os.environ.pop("YUNWU_API_KEY", None)
                else:
                    os.environ["YUNWU_API_KEY"] = original_yunwu_key

    def test_runtime_load_secret_preserves_project_wsl_host(self) -> None:
        original_key = os.environ.pop("TEST_ASTRABRIDGE_WSL_SECRET_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = root / "workspace"
                workspace.mkdir()
                key_file = root / "provider.key"
                key_file.write_text("test-provider-key", encoding="utf-8")
                project = ProjectService(root / "projects.json")
                project.create_project("WSL Secret", root / "wsl-secret.abproj", workspace_root=workspace, entry_mode="existing")
                project.update_project({"ui_preferences": {"execution_host": "wsl", "wsl_distro": "Ubuntu-24.04"}})
                runtime = RuntimeService(project, ModalService(project.require_shell_state_root))
                status = runtime.load_secret(
                    {
                        "profile_id": "test-wsl",
                        "label": "Test WSL",
                        "provider_id": "deepseek",
                        "base_url": "https://api.deepseek.com",
                        "model": "deepseek-v4-pro",
                        "reasoning_effort": "max",
                        "wire_api": "chat",
                        "env_key": "TEST_ASTRABRIDGE_WSL_SECRET_KEY",
                        "auth_mode": "session_paste",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    },
                    key_file_path=str(key_file),
                )
                self.assertTrue(status["secret_loaded"])
                self.assertEqual(status["execution_host"], "wsl")
                self.assertEqual(status["wsl_distro"], "Ubuntu-24.04")
        finally:
            if original_key is None:
                os.environ.pop("TEST_ASTRABRIDGE_WSL_SECRET_KEY", None)
            else:
                os.environ["TEST_ASTRABRIDGE_WSL_SECRET_KEY"] = original_key

    def test_wsl_dependency_status_reports_codex_version_failure(self) -> None:
        service = WslDependencyService(Path(tempfile.mkdtemp()) / "bootstrap")

        def fake_run(command: list[str]) -> dict[str, object]:
            joined = " ".join(command)
            if "-l -v" in joined:
                return {"returncode": 0, "stdout": "  NAME            STATE           VERSION\n* Ubuntu-24.04    Stopped         2\n", "stderr": ""}
            if "cat /etc/os-release" in joined:
                return {"returncode": 0, "stdout": 'PRETTY_NAME="Ubuntu 24.04 LTS"', "stderr": ""}
            if "command -v codex" in joined:
                return {"returncode": 0, "stdout": "/mnt/c/Program Files/WindowsApps/OpenAI.Codex/app/resources/codex", "stderr": ""}
            if "codex --version" in joined:
                return {"returncode": 126, "stdout": "", "stderr": "Permission denied"}
            if "codex app-server" in joined:
                return {"returncode": 126, "stdout": "", "stderr": "Permission denied"}
            if any(item in joined for item in ("python3 --version", "git --version", "node --version", "npm --version", "npx --version", "bwrap --version")):
                return {"returncode": 0, "stdout": "ok", "stderr": ""}
            return {"returncode": 0, "stdout": "", "stderr": ""}

        service._run = fake_run  # type: ignore[method-assign]
        status = service.status("Ubuntu-24.04")
        by_id = {item["id"]: item for item in status["checks"]}
        self.assertFalse(status["ok"])
        self.assertEqual(by_id["codex_path"]["status"], "misconfigured")
        self.assertEqual(by_id["codex_version"]["status"], "missing")

    def test_wsl_dependency_scripts_do_not_contain_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = WslDependencyService(Path(temp) / "bootstrap")
            result = service.write_scripts("Ubuntu-24.04")
            windows_text = Path(result["windows_script_path"]).read_text(encoding="utf-8")
            wsl_text = Path(result["wsl_script_path"]).read_text(encoding="utf-8")
            combined = windows_text + "\n" + wsl_text
            self.assertIn("wsl.exe --install", combined)
            self.assertIn("CODEX_INSTALL_DIR", combined)
            self.assertNotIn("Authorization", combined)
            self.assertNotIn("Bearer ", combined)
            self.assertNotIn("unit_secret_", combined)

    def test_official_codex_product_path_is_disabled(self) -> None:
        status = disabled_status()
        self.assertTrue(status["disabled"])
        self.assertEqual(status["error"], OFFICIAL_CODEX_DISABLED_ERROR)
        self.assertFalse(status["router_configured"])
        self.assertFalse(status["managed_by_app"])
        self.assertEqual(status["backup_count"], 0)
        self.assertIn("does not patch official Codex account config", status["message"])

    def test_router_service_models_and_responses_passthrough(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            last_payload = None

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                UpstreamHandler.last_payload = payload
                body = json.dumps(
                    {
                        "id": "resp_test",
                        "object": "response",
                        "model": payload["model"],
                        "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_port = upstream.server_address[1]
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()

        original_router_token = os.environ.get(ROUTER_ENV_KEY)
        original_provider_token = os.environ.get("TEST_ROUTER_PROVIDER_KEY")
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                profiles.upsert_profile(
                    {
                        "profile_id": "router-openai",
                        "label": "Router OpenAI",
                        "type": "custom_provider",
                        "provider_id": "openai",
                        "base_url": f"http://127.0.0.1:{upstream_port}",
                        "model": "gpt-5.5",
                        "reasoning_effort": "high",
                        "wire_api": "responses",
                        "env_key": "TEST_ROUTER_PROVIDER_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    }
                )
                os.environ["TEST_ROUTER_PROVIDER_KEY"] = "unit_secret_provider_test"
                router = RouterService(profiles, port=0)
                router.start()
                token = os.environ[ROUTER_ENV_KEY]

                models_request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/models",
                    headers={"Authorization": f"Bearer {token}"},
                )
                with urllib.request.urlopen(models_request, timeout=5) as response:
                    models_payload = json.loads(response.read().decode("utf-8"))
                self.assertIn("openai/gpt-5.5", [item["id"] for item in models_payload["data"]])
                router_model = next(item for item in models_payload["data"] if item["id"] == "openai/gpt-5.5")
                self.assertEqual(router_model["input_modalities"], ["text"])
                self.assertEqual(router_model["effective_context_window_percent"], 80)
                self.assertEqual(router_model["auto_compact_token_limit"], 800000)
                self.assertFalse(router_model["supports_parallel_tool_calls"])
                self.assertIsNone(router_model["apply_patch_tool_type"])

                response_request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/responses",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    data=json.dumps({"model": "openai/gpt-5.5", "input": "hello", "stream": False}).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(response_request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self.assertEqual(payload["model"], "gpt-5.5")
                self.assertEqual(UpstreamHandler.last_payload["model"], "gpt-5.5")

                native_smoke = router.test_provider("openai", "gpt-5.5", stream=False)
                self.assertTrue(native_smoke["ok"])
                self.assertEqual(native_smoke["model"], "openai/gpt-5.5")
                self.assertEqual(UpstreamHandler.last_payload["model"], "gpt-5.5")
        finally:
            upstream.shutdown()
            upstream.server_close()
            if router is not None:
                router.stop()
            if original_router_token is None:
                os.environ.pop(ROUTER_ENV_KEY, None)
            else:
                os.environ[ROUTER_ENV_KEY] = original_router_token
            if original_provider_token is None:
                os.environ.pop("TEST_ROUTER_PROVIDER_KEY", None)
            else:
                os.environ["TEST_ROUTER_PROVIDER_KEY"] = original_provider_token

    def test_router_service_uses_instance_token_not_inherited_environment(self) -> None:
        original_router_token = os.environ.get(ROUTER_ENV_KEY)
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                os.environ[ROUTER_ENV_KEY] = "stale_router"
                profiles = ProfileService(Path(temp) / "profiles.json")
                router = RouterService(profiles, port=0)
                router.start()
                fresh_token = os.environ[ROUTER_ENV_KEY]
                self.assertNotEqual(fresh_token, "stale_router")

                stale_request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/models",
                    headers={"Authorization": "Bearer stale_router"},
                )
                with self.assertRaises(urllib.error.HTTPError) as captured:
                    urllib.request.urlopen(stale_request, timeout=5)
                self.assertEqual(captured.exception.code, 401)

                fresh_request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/models",
                    headers={"Authorization": f"Bearer {fresh_token}"},
                )
                with urllib.request.urlopen(fresh_request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
        finally:
            if router is not None:
                router.stop()
            if original_router_token is None:
                os.environ.pop(ROUTER_ENV_KEY, None)
            else:
                os.environ[ROUTER_ENV_KEY] = original_router_token

    def test_isolation_audit_reports_lcr_boundaries_without_secret_values(self) -> None:
        original_override = os.environ.get("ASTRABRIDGE_CODEX_HOME")
        original_appdata = os.environ.get("ASTRABRIDGE_APPDATA")
        try:
            os.environ.pop("ASTRABRIDGE_CODEX_HOME", None)
            os.environ.pop("ASTRABRIDGE_APPDATA", None)
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = root / "workspace"
                workspace.mkdir()
                project_service = ProjectService(root / "projects.json")
                project = project_service.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
                codex_home = root / "isolated-codex-home"
                codex_home.mkdir()
                (codex_home / "config.toml").write_text('model = "deepseek/deepseek-v4-pro"\n', encoding="utf-8")
                official_home = root / ".codex"
                official_home.mkdir()
                official_config = official_home / "config.toml"
                official_config.write_text('model = "gpt-5"\n', encoding="utf-8")
                audit = IsolationAuditService().snapshot(
                    current_project=project,
                    runtime_environment={
                        "running": False,
                        "codex_cli": "codex",
                        "execution_host": "windows",
                        "runtime_config": {"codex_home": str(codex_home)},
                    },
                    router_status={"listen_port": 8787, "base_url": "http://127.0.0.1:8787/v1"},
                    official_codex_status={
                        "config_path": str(official_config),
                        "exists": True,
                        "managed_by_app": False,
                        "router_configured": False,
                    },
                    sidecar_port=8790,
                )
                self.assertTrue(audit["ok"])
                self.assertEqual(audit["paths"]["astrabridge_state"], str(workspace / ".astrabridge"))
                self.assertIsNotNone(audit["official_codex"]["config_sha256"])
        finally:
            if original_override is None:
                os.environ.pop("ASTRABRIDGE_CODEX_HOME", None)
            else:
                os.environ["ASTRABRIDGE_CODEX_HOME"] = original_override
            if original_appdata is None:
                os.environ.pop("ASTRABRIDGE_APPDATA", None)
            else:
                os.environ["ASTRABRIDGE_APPDATA"] = original_appdata

    def test_isolation_audit_ignores_safe_env_key_and_token_limit_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            project_service = ProjectService(root / "projects.json")
            project = project_service.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            codex_home = root / "isolated-codex-home"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                'model_auto_compact_token_limit = 4096\n'
                'tool_output_token_limit = 12000\n'
                'env_key = "YUNWU_API_KEY"\n'
                'router_env_key = "CODEX_ROUTER_API_KEY"\n',
                encoding="utf-8",
            )
            audit = IsolationAuditService().snapshot(
                current_project=project,
                runtime_environment={
                    "running": False,
                    "codex_cli": "codex",
                    "execution_host": "windows",
                    "runtime_config": {"codex_home": str(codex_home)},
                },
                router_status={"listen_port": 8787, "base_url": "http://127.0.0.1:8787/v1"},
                official_codex_status={
                    "config_path": str(root / ".codex" / "config.toml"),
                    "exists": False,
                    "managed_by_app": False,
                    "router_configured": False,
                },
                sidecar_port=8790,
            )
            checks = {item["name"]: item for item in audit["checks"]}
            self.assertTrue(checks["isolated_codex_config_has_no_secret"]["ok"])

    def test_isolation_audit_requires_expected_codex_home_override_match(self) -> None:
        original_override = os.environ.get("ASTRABRIDGE_CODEX_HOME")
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = root / "workspace"
                workspace.mkdir()
                project_service = ProjectService(root / "projects.json")
                project = project_service.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
                expected_home = root / "expected-codex-home"
                expected_home.mkdir()
                (expected_home / "config.toml").write_text('model = "gpt-5.5"\n', encoding="utf-8")
                actual_home = root / "actual-codex-home"
                actual_home.mkdir()
                (actual_home / "config.toml").write_text('model = "gpt-5.5"\n', encoding="utf-8")
                os.environ["ASTRABRIDGE_CODEX_HOME"] = str(expected_home)

                mismatch_audit = IsolationAuditService().snapshot(
                    current_project=project,
                    runtime_environment={
                        "running": False,
                        "codex_cli": "codex",
                        "execution_host": "windows",
                        "runtime_config": {"codex_home": str(actual_home)},
                    },
                    router_status={"listen_port": 8787, "base_url": "http://127.0.0.1:8787/v1"},
                    official_codex_status={
                        "config_path": str(root / ".codex" / "config.toml"),
                        "exists": False,
                        "managed_by_app": False,
                        "router_configured": False,
                    },
                    sidecar_port=8790,
                )
                mismatch_checks = {item["name"]: item for item in mismatch_audit["checks"]}
                self.assertFalse(mismatch_audit["ok"])
                self.assertFalse(mismatch_checks["isolated_codex_home_matches_expected_override"]["ok"])
                self.assertEqual(mismatch_checks["isolated_codex_home_matches_expected_override"]["detail"]["expected"], str(expected_home.resolve()))
                self.assertEqual(mismatch_checks["isolated_codex_home_matches_expected_override"]["detail"]["actual"], str(actual_home.resolve()))

                matching_audit = IsolationAuditService().snapshot(
                    current_project=project,
                    runtime_environment={
                        "running": False,
                        "codex_cli": "codex",
                        "execution_host": "windows",
                        "runtime_config": {"codex_home": str(expected_home)},
                    },
                    router_status={"listen_port": 8787, "base_url": "http://127.0.0.1:8787/v1"},
                    official_codex_status={
                        "config_path": str(root / ".codex" / "config.toml"),
                        "exists": False,
                        "managed_by_app": False,
                        "router_configured": False,
                    },
                    sidecar_port=8790,
                )
                matching_checks = {item["name"]: item for item in matching_audit["checks"]}
                self.assertTrue(matching_audit["ok"])
                self.assertTrue(matching_checks["isolated_codex_home_matches_expected_override"]["ok"])
                self.assertEqual(matching_audit["paths"]["expected_codex_home"], str(expected_home.resolve()))
        finally:
            if original_override is None:
                os.environ.pop("ASTRABRIDGE_CODEX_HOME", None)
            else:
                os.environ["ASTRABRIDGE_CODEX_HOME"] = original_override

    def test_qwen_adapter_maps_effort_to_enable_thinking(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            last_payload = None

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                UpstreamHandler.last_payload = json.loads(self.rfile.read(length).decode("utf-8"))
                body = json.dumps({"id": "resp_qwen", "object": "response", "model": UpstreamHandler.last_payload["model"]}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_port = upstream.server_address[1]
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()

        original_router_token = os.environ.get(ROUTER_ENV_KEY)
        original_provider_token = os.environ.get("TEST_QWEN_PROVIDER_KEY")
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                profiles.upsert_profile(
                    {
                        "profile_id": "qwen-router",
                        "label": "Qwen Router",
                        "type": "custom_provider",
                        "provider_id": "qwen",
                        "base_url": f"http://127.0.0.1:{upstream_port}",
                        "model": "qwen3-coder-plus",
                        "reasoning_effort": "xhigh",
                        "wire_api": "responses",
                        "env_key": "TEST_QWEN_PROVIDER_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    }
                )
                os.environ["TEST_QWEN_PROVIDER_KEY"] = "unit_secret_qwen_test"
                router = RouterService(profiles, port=0)
                router.start()
                token = os.environ[ROUTER_ENV_KEY]

                response_request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/responses",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    data=json.dumps(
                        {
                            "model": "qwen/qwen3-coder-plus",
                            "input": "hello",
                            "stream": False,
                            "reasoning": {"effort": "off"},
                            "temperature": 0.2,
                        }
                    ).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(response_request, timeout=5):
                    pass

                self.assertEqual(UpstreamHandler.last_payload["model"], "qwen3-coder-plus")
                self.assertEqual(UpstreamHandler.last_payload["enable_thinking"], False)
                self.assertNotIn("reasoning", UpstreamHandler.last_payload)
                self.assertEqual(UpstreamHandler.last_payload["temperature"], 0.2)

                omitted = router.preview_payload(
                    {
                        "model": "qwen/qwen3-coder-plus",
                        "input": "hello",
                        "stream": False,
                        "temperature": 0,
                    }
                )
                self.assertNotIn("temperature", omitted["upstream_payload"])
                self.assertIn("omitted", omitted["warnings"][0])

                clamped = router.preview_payload(
                    {
                        "model": "qwen/qwen3-coder-plus",
                        "input": "hello",
                        "stream": False,
                        "temperature": 2,
                    }
                )
                self.assertEqual(clamped["upstream_payload"]["temperature"], 1.0)
                self.assertIn("caps", clamped["warnings"][0])
        finally:
            upstream.shutdown()
            upstream.server_close()
            if router is not None:
                router.stop()
            if original_router_token is None:
                os.environ.pop(ROUTER_ENV_KEY, None)
            else:
                os.environ[ROUTER_ENV_KEY] = original_router_token
            if original_provider_token is None:
                os.environ.pop("TEST_QWEN_PROVIDER_KEY", None)
            else:
                os.environ["TEST_QWEN_PROVIDER_KEY"] = original_provider_token

    def test_deepseek_adapter_converts_chat_completion_to_response(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            last_payload = None

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                UpstreamHandler.last_payload = json.loads(self.rfile.read(length).decode("utf-8"))
                body = json.dumps(
                    {
                        "id": "chatcmpl-deepseek",
                        "object": "chat.completion",
                        "created": 123,
                        "choices": [
                            {
                                "index": 0,
                                "message": {
                                    "role": "assistant",
                                    "content": "deepseek ok",
                                    "tool_calls": [
                                        {
                                            "id": "call_ds_1",
                                            "type": "function",
                                            "function": {"name": "update_plan", "arguments": "{\"step\":\"x\"}"},
                                        }
                                    ],
                                },
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 11, "completion_tokens": 17, "total_tokens": 28},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_port = upstream.server_address[1]
        threading.Thread(target=upstream.serve_forever, daemon=True).start()

        original_router_token = os.environ.get(ROUTER_ENV_KEY)
        original_provider_token = os.environ.get("TEST_DEEPSEEK_PROVIDER_KEY")
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                profiles.upsert_profile(
                    {
                        "profile_id": "deepseek-router",
                        "label": "DeepSeek Router",
                        "type": "custom_provider",
                        "provider_id": "deepseek",
                        "base_url": f"http://127.0.0.1:{upstream_port}",
                        "model": "deepseek-v4-pro",
                        "reasoning_effort": "xhigh",
                        "wire_api": "chat",
                        "env_key": "TEST_DEEPSEEK_PROVIDER_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    }
                )
                os.environ["TEST_DEEPSEEK_PROVIDER_KEY"] = "unit_secret_deepseek_test"
                router = RouterService(profiles, port=0)
                router.start()
                token = os.environ[ROUTER_ENV_KEY]

                request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/responses",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    data=json.dumps(
                        {
                            "model": "deepseek/deepseek-v4-pro",
                            "input": "hello",
                            "stream": False,
                            "reasoning": {"effort": "xhigh"},
                            "tools": [{"type": "function", "name": "update_plan", "description": "update", "parameters": {"type": "object"}}],
                        }
                    ).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(UpstreamHandler.last_payload["model"], "deepseek-v4-pro")
                self.assertEqual(UpstreamHandler.last_payload["thinking"]["type"], "enabled")
                self.assertEqual(UpstreamHandler.last_payload["reasoning_effort"], "max")
                self.assertEqual(UpstreamHandler.last_payload["tools"][0]["function"]["name"], "update_plan")
                self.assertEqual(payload["object"], "response")
                self.assertEqual(payload["output_text"], "deepseek ok")
                self.assertEqual(payload["output"][1]["type"], "function_call")
        finally:
            upstream.shutdown()
            upstream.server_close()
            if router is not None:
                router.stop()
            if original_router_token is None:
                os.environ.pop(ROUTER_ENV_KEY, None)
            else:
                os.environ[ROUTER_ENV_KEY] = original_router_token
            if original_provider_token is None:
                os.environ.pop("TEST_DEEPSEEK_PROVIDER_KEY", None)
            else:
                os.environ["TEST_DEEPSEEK_PROVIDER_KEY"] = original_provider_token

    def test_deepseek_adapter_preserves_reasoning_content_across_tool_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "deepseek-router",
                    "label": "DeepSeek Router",
                    "type": "custom_provider",
                    "provider_id": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_DEEPSEEK_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "deepseek/deepseek-v4-pro",
                    "input": [
                        {"type": "reasoning", "summary": ["hidden reasoning"]},
                        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "I will ask."}]},
                        {"type": "function_call", "call_id": "call_1", "name": "request_user_input", "arguments": "{}"},
                    ],
                    "stream": False,
                    "reasoning": {"effort": "xhigh"},
                }
            )
            assistant = next(
                message
                for message in preview["upstream_payload"]["messages"]
                if message.get("role") == "assistant" and message.get("tool_calls")
            )
            self.assertEqual(assistant["reasoning_content"], "hidden reasoning")
            self.assertEqual(assistant["content"], "I will ask.")
            self.assertEqual(assistant["tool_calls"][0]["id"], "call_1")

    def test_chat_adapter_pairs_codex_command_execution_with_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "deepseek-router",
                    "label": "DeepSeek Router",
                    "type": "custom_provider",
                    "provider_id": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_DEEPSEEK_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "deepseek/deepseek-v4-pro",
                    "input": [
                        {"type": "function_call", "call_id": "call_shell", "name": "shell", "arguments": "{\"cmd\":\"dir\"}"},
                        {
                            "type": "commandExecution",
                            "id": "call_shell",
                            "command": "dir",
                            "status": "completed",
                            "aggregatedOutput": "index.html",
                            "exitCode": 0,
                        },
                    ],
                    "stream": False,
                    "reasoning": {"effort": "xhigh"},
                }
            )
            messages = preview["upstream_payload"]["messages"]
            assistant = messages[-2]
            tool = messages[-1]
            self.assertEqual(assistant["role"], "assistant")
            self.assertEqual(assistant["tool_calls"][0]["id"], "call_shell")
            self.assertEqual(tool["role"], "tool")
            self.assertEqual(tool["tool_call_id"], "call_shell")
            self.assertIn("index.html", tool["content"])

    def test_chat_adapter_pairs_parallel_codex_command_executions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-router",
                    "label": "Kimi Router",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_KIMI_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "kimi/kimi-k2.6",
                    "input": [
                        {"type": "function_call", "call_id": "shell_command:2", "name": "shell_command", "arguments": "{\"command\":\"Get-Content index.html\"}"},
                        {"type": "function_call", "call_id": "shell_command:3", "name": "shell_command", "arguments": "{\"command\":\"Get-Content README.md\"}"},
                        {"type": "function_call", "call_id": "shell_command:4", "name": "shell_command", "arguments": "{\"command\":\"Get-Content js/main.js\"}"},
                        {"type": "commandExecution", "id": "shell_command:2", "command": "Get-Content index.html", "status": "completed", "aggregatedOutput": "<html>", "exitCode": 0},
                        {"type": "commandExecution", "id": "shell_command:3", "command": "Get-Content README.md", "status": "completed", "aggregatedOutput": "# Readme", "exitCode": 0},
                        {"type": "commandExecution", "id": "shell_command:4", "command": "Get-Content js/main.js", "status": "completed", "aggregatedOutput": "init()", "exitCode": 0},
                    ],
                    "stream": False,
                    "reasoning": {"effort": "xhigh"},
                }
            )
            messages = preview["upstream_payload"]["messages"]
            assistant_index = next(i for i, message in enumerate(messages) if message.get("role") == "assistant" and message.get("tool_calls"))
            assistant = messages[assistant_index]
            self.assertEqual([call["id"] for call in assistant["tool_calls"]], ["shell_command:2", "shell_command:3", "shell_command:4"])
            tool_ids = [messages[assistant_index + offset]["tool_call_id"] for offset in (1, 2, 3)]
            self.assertEqual(tool_ids, ["shell_command:2", "shell_command:3", "shell_command:4"])

    def test_kimi_adapter_encodes_local_image_as_base64_image_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            image_path = Path(temp) / "vision.png"
            image_path.write_bytes(_png_rgba(1, 1, (0, 64, 255, 255)))
            raw_path = str(image_path)
            if image_path.drive:
                drive = image_path.drive.rstrip(":").lower()
                tail = str(image_path)[len(image_path.drive) + 1 :].replace("\\", "/")
                raw_path = f"/mnt/{drive}/{tail}"

            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-router",
                    "label": "Kimi Router",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "off",
                    "wire_api": "chat",
                    "env_key": "TEST_KIMI_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            payload = {
                "model": "kimi/kimi-k2.6",
                "input": [
                    {"type": "text", "text": "What color is this image?"},
                    {"type": "localImage", "path": raw_path, "detail": "high"},
                ],
                "stream": False,
            }
            profile = router._resolve_profile(payload)  # noqa: SLF001
            upstream = router._adapter_for(profile).upstream_payload(payload)  # noqa: SLF001
            image_message = next(message for message in upstream["messages"] if isinstance(message.get("content"), list))
            image_part = next(part for part in image_message["content"] if part.get("type") == "image_url")
            self.assertTrue(image_part["image_url"]["url"].startswith("data:image/png;base64,"))
            self.assertIn(base64.b64encode(image_path.read_bytes()).decode("ascii"), image_part["image_url"]["url"])

            preview = router.preview_payload(payload)
            self.assertIn("[REDACTED_IMAGE_DATA_URL]", json.dumps(preview["upstream_payload"]))

    def test_kimi_adapter_keeps_thinking_for_visual_micro_check_with_large_output_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            image_path = Path(temp) / "vision.png"
            image_path.write_bytes(_png_rgba(2, 2, (0, 64, 255, 255)))
            raw_path = str(image_path)
            if image_path.drive:
                drive = image_path.drive.rstrip(":").lower()
                tail = str(image_path)[len(image_path.drive) + 1 :].replace("\\", "/")
                raw_path = f"/mnt/{drive}/{tail}"

            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-router",
                    "label": "Kimi Router",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_KIMI_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            payload = {
                "model": "kimi/kimi-k2.6",
                "input": [
                    {"type": "text", "text": "Visual micro-check only. Reply pass or retry."},
                    {"type": "localImage", "path": raw_path, "detail": "high"},
                ],
                "stream": False,
            }
            preview = router.preview_payload(payload)
            upstream = preview["upstream_payload"]
            self.assertEqual(upstream["thinking"], {"type": "enabled"})
            self.assertEqual(upstream["max_tokens"], 32768)
            self.assertIn("[REDACTED_IMAGE_DATA_URL]", json.dumps(upstream))

    def test_kimi_adapter_maps_app_server_input_image_to_chat_image_part(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-router",
                    "label": "Kimi Router",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_KIMI_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            payload = {
                "model": "kimi/kimi-k2.6",
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "Visual micro-check only."},
                            {"type": "input_image", "image_url": "data:image/png;base64,AAAA", "detail": "high"},
                        ],
                    }
                ],
                "stream": True,
                "reasoning": {"effort": "high"},
            }
            upstream = router.preview_payload(payload)["upstream_payload"]
            content = upstream["messages"][-1]["content"]
            image_part = next(part for part in content if part.get("type") == "image_url")
            self.assertEqual(image_part["image_url"]["url"], "[REDACTED_IMAGE_DATA_URL]")
            self.assertEqual(upstream["thinking"], {"type": "enabled"})
            self.assertEqual(upstream["max_tokens"], 32768)

    def test_kimi_adapter_recovers_app_server_embedded_input_image_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-router",
                    "label": "Kimi Router",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_KIMI_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            embedded = (
                'Look at this image.\n<image name=[Image #1] path="/tmp/asset.png">\n'
                '{"type": "input_image", "image_url": "data:image/png;base64,AAAA", "detail": "high"}\n'
                "</image>"
            )
            payload = {
                "model": "kimi/kimi-k2.6",
                "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": embedded}]}],
                "stream": True,
                "reasoning": {"effort": "high"},
            }
            upstream = router._adapter_for(router._resolve_profile(payload)).upstream_payload(payload)  # noqa: SLF001
            content = upstream["messages"][-1]["content"]
            self.assertIsInstance(content, list)
            self.assertTrue(any(part.get("type") == "image_url" for part in content))
            self.assertFalse("data:image/png;base64,AAAA" in json.dumps(router.preview_payload(payload)))
            self.assertIn("[REDACTED_IMAGE_DATA_URL]", json.dumps(router.preview_payload(payload)))
            self.assertEqual(upstream["thinking"], {"type": "enabled"})
            self.assertEqual(upstream["max_tokens"], 32768)

    def test_kimi_adapter_recovers_loose_embedded_image_url_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-router",
                    "label": "Kimi Router",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_KIMI_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            embedded = (
                'Look at this attachment.\n<image>\n'
                '{"detail": "high", "metadata": {"name": "asset.png"}, "type": "input_image", '
                '"image_url": "data:image/png;base64,BBBB"}\n'
                "</image>"
            )
            payload = {
                "model": "kimi/kimi-k2.6",
                "input": [{"type": "message", "role": "user", "content": [{"type": "text", "text": embedded}]}],
                "stream": True,
            }

            upstream = router._adapter_for(router._resolve_profile(payload)).upstream_payload(payload)  # noqa: SLF001
            content = upstream["messages"][-1]["content"]
            self.assertIsInstance(content, list)
            self.assertTrue(any(part.get("type") == "image_url" for part in content))
            self.assertFalse("data:image/png;base64,BBBB" in json.dumps(router.preview_payload(payload)))
            self.assertIn("[REDACTED_IMAGE_DATA_URL]", json.dumps(router.preview_payload(payload)))

    def test_kimi_adapter_keeps_explicit_deep_visual_reasoning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            image_path = Path(temp) / "vision.png"
            image_path.write_bytes(_png_rgba(2, 2, (0, 64, 255, 255)))
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-router",
                    "label": "Kimi Router",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "high",
                    "wire_api": "chat",
                    "env_key": "TEST_KIMI_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "kimi/kimi-k2.6",
                    "input": [
                        {"type": "text", "text": "Deeply inspect this image."},
                        {"type": "localImage", "path": str(image_path), "detail": "high"},
                    ],
                    "reasoning": {"effort": "max"},
                    "stream": False,
                }
            )
            upstream = preview["upstream_payload"]
            self.assertEqual(upstream["thinking"], {"type": "enabled", "keep": "all"})
            self.assertGreaterEqual(upstream["max_tokens"], 32768)

    def test_chat_adapter_repairs_missing_tool_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "deepseek-router",
                    "label": "DeepSeek Router",
                    "type": "custom_provider",
                    "provider_id": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_DEEPSEEK_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "deepseek/deepseek-v4-pro",
                    "input": [
                        {"type": "function_call", "call_id": "call_missing", "name": "shell", "arguments": "{}"},
                        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "continue"}]},
                    ],
                    "stream": False,
                    "reasoning": {"effort": "xhigh"},
                }
            )
            messages = preview["upstream_payload"]["messages"]
            assistant_index = next(i for i, message in enumerate(messages) if message.get("role") == "assistant" and message.get("tool_calls"))
            self.assertEqual(messages[assistant_index + 1]["role"], "tool")
            self.assertEqual(messages[assistant_index + 1]["tool_call_id"], "call_missing")
            self.assertIn("unavailable", messages[assistant_index + 1]["content"])

    def test_deepseek_adapter_repairs_tool_pairs_after_reasoning_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "deepseek-router",
                    "label": "DeepSeek Router",
                    "type": "custom_provider",
                    "provider_id": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_DEEPSEEK_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "deepseek/deepseek-v4-pro",
                    "input": [
                        {"type": "reasoning", "summary": ["compact summary before a tool call"]},
                        {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "I will inspect a file."}]},
                        {"type": "function_call", "call_id": "call_after_compact", "name": "shell", "arguments": "{\"cmd\":\"type js/data.js\"}"},
                        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "continue after compact"}]},
                        {"type": "function_call_output", "call_id": "call_after_compact", "output": "late tool output"},
                    ],
                    "stream": False,
                    "reasoning": {"effort": "xhigh"},
                }
            )
            messages = preview["upstream_payload"]["messages"]
            assistant_index = next(i for i, message in enumerate(messages) if message.get("role") == "assistant" and message.get("tool_calls"))
            assistant = messages[assistant_index]
            tool = messages[assistant_index + 1]
            self.assertEqual(assistant["reasoning_content"], "compact summary before a tool call")
            self.assertEqual(assistant["content"], "I will inspect a file.")
            self.assertEqual(tool["role"], "tool")
            self.assertEqual(tool["tool_call_id"], "call_after_compact")

    def test_chat_adapter_projects_review_and_compaction_transitions_as_assistant_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "deepseek-router",
                    "label": "DeepSeek Router",
                    "type": "custom_provider",
                    "provider_id": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_DEEPSEEK_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "deepseek/deepseek-v4-pro",
                    "input": [
                        {"type": "contextCompaction", "id": "compact-1"},
                        {"type": "enteredReviewMode", "id": "review-1", "review": "Inspect the latest diff for regressions."},
                        {"type": "exitedReviewMode", "id": "review-2", "review": "Review complete; continue coding."},
                    ],
                    "stream": False,
                }
            )

            messages = preview["upstream_payload"]["messages"]
            self.assertEqual([message["role"] for message in messages], ["assistant", "assistant", "assistant"])
            self.assertIn("[context compaction]", messages[0]["content"])
            self.assertIn("[review mode entered]", messages[1]["content"])
            self.assertIn("latest diff", messages[1]["content"])
            self.assertIn("[review mode exited]", messages[2]["content"])

    def test_chat_adapter_projects_collab_spawn_as_fork_transition_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "deepseek-router",
                    "label": "DeepSeek Router",
                    "type": "custom_provider",
                    "provider_id": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "xhigh",
                    "wire_api": "chat",
                    "env_key": "TEST_DEEPSEEK_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "deepseek/deepseek-v4-pro",
                    "input": [
                        {
                            "type": "collabAgentToolCall",
                            "id": "collab-1",
                            "tool": "spawnAgent",
                            "senderThreadId": "thread-main",
                            "receiverThreadIds": ["thread-fork-1"],
                            "prompt": "Review the CSS changes and report layout risks.",
                            "model": "deepseek-v4-pro",
                            "reasoningEffort": "high",
                            "agentsStates": {"thread-fork-1": {"status": "running"}},
                            "status": "completed",
                        }
                    ],
                    "stream": False,
                }
            )

            messages = preview["upstream_payload"]["messages"]
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["role"], "assistant")
            self.assertIn("[forked collaborator thread]", messages[0]["content"])
            self.assertIn("thread-fork-1", messages[0]["content"])
            self.assertIn("Review the CSS changes", messages[0]["content"])

    def test_responses_transport_projects_transition_items_as_assistant_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "openai/gpt-5.5",
                    "input": [
                        {"type": "contextCompaction", "id": "compact-1"},
                        {"type": "enteredReviewMode", "id": "review-1", "review": "Inspect the latest diff for regressions."},
                        {
                            "type": "collabAgentToolCall",
                            "id": "collab-1",
                            "tool": "spawnAgent",
                            "senderThreadId": "thread-main",
                            "receiverThreadIds": ["thread-fork-1"],
                            "prompt": "Review the CSS changes and report layout risks.",
                            "model": "gpt-5.5",
                            "reasoningEffort": "high",
                            "agentsStates": {"thread-fork-1": {"status": "running"}},
                        },
                    ],
                    "stream": False,
                }
            )

            items = preview["upstream_payload"]["input"]
            self.assertEqual([item["type"] for item in items], ["message", "message", "message"])
            self.assertEqual([item["role"] for item in items], ["assistant", "assistant", "assistant"])
            self.assertIn("[context compaction]", items[0]["content"][0]["text"])
            self.assertIn("[review mode entered]", items[1]["content"][0]["text"])
            self.assertIn("[forked collaborator thread]", items[2]["content"][0]["text"])

    def test_responses_transport_maps_command_execution_to_function_call_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)
            preview = router.preview_payload(
                {
                    "model": "openai/gpt-5.5",
                    "input": [
                        {
                            "type": "commandExecution",
                            "id": "call_shell",
                            "command": "dir",
                            "status": "completed",
                            "aggregatedOutput": "index.html",
                            "exitCode": 0,
                        }
                    ],
                    "stream": False,
                }
            )

            items = preview["upstream_payload"]["input"]
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["type"], "function_call_output")
            self.assertEqual(items[0]["call_id"], "call_shell")
            self.assertIn("command: dir", items[0]["output"])
            self.assertIn("exit_code: 0", items[0]["output"])

    def test_responses_transport_stream_events_mark_function_calls_completed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)
            adapter = router._adapter_for_provider("openai")  # noqa: SLF001

            upstream = {
                "id": "resp-openai",
                "object": "response",
                "status": "completed",
                "output": [
                    {
                        "id": "fc_call_1",
                        "type": "function_call",
                        "call_id": "call_1",
                        "name": "shell",
                        "arguments": "{\"cmd\":\"dir\"}",
                    }
                ],
            }

            events = adapter.client_stream_events_from_upstream_json(upstream, {"model": "openai/gpt-5.5"})
            added = [event for event in events if event.get("type") == "response.output_item.added"]
            done = [event for event in events if event.get("type") == "response.output_item.done"]

            self.assertEqual(len(added), 1)
            self.assertEqual(added[0]["item"]["type"], "function_call")
            self.assertEqual(len(done), 1)
            self.assertEqual(done[0]["item"]["type"], "function_call")
            self.assertEqual(done[0]["item"]["status"], "completed")

    def test_chat_transport_stream_events_keep_function_call_completion_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)
            adapter = router._adapter_for_provider("deepseek")  # noqa: SLF001

            upstream = {
                "id": "chatcmpl-deepseek",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I will inspect the file.",
                            "tool_calls": [
                                {
                                    "id": "call_after_compact",
                                    "type": "function",
                                    "function": {"name": "shell", "arguments": "{\"cmd\":\"type js/data.js\"}"},
                                }
                            ],
                        }
                    }
                ],
            }

            response = adapter.client_response_from_upstream_json(upstream, {"model": "deepseek/deepseek-v4-pro"})
            events = adapter.client_stream_events_from_upstream_json(upstream, {"model": "deepseek/deepseek-v4-pro"})
            response_function_calls = [item for item in response["output"] if item.get("type") == "function_call"]
            done = [event for event in events if event.get("type") == "response.output_item.done" and event.get("item", {}).get("type") == "function_call"]

            self.assertEqual(len(response_function_calls), 1)
            self.assertEqual(response_function_calls[0]["call_id"], "call_after_compact")
            self.assertEqual(len(done), 1)
            self.assertEqual(done[0]["item"]["call_id"], "call_after_compact")
            self.assertEqual(done[0]["item"]["status"], "completed")

    def test_responses_transport_stream_events_preserve_reasoning_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)
            adapter = router._adapter_for_provider("openai")  # noqa: SLF001

            upstream = {
                "id": "resp-openai-reasoning",
                "object": "response",
                "status": "completed",
                "output": [
                    {
                        "id": "reasoning_1",
                        "type": "reasoning",
                        "summary": ["first reasoning step", "second reasoning step"],
                        "content": ["first reasoning step", "second reasoning step"],
                    },
                    {
                        "id": "msg_1",
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Final answer."}],
                    },
                ],
            }

            events = adapter.client_stream_events_from_upstream_json(upstream, {"model": "openai/gpt-5.5"})
            reasoning_added = [event for event in events if event.get("type") == "response.output_item.added" and event.get("item", {}).get("type") == "reasoning"]
            reasoning_done = [event for event in events if event.get("type") == "response.output_item.done" and event.get("item", {}).get("type") == "reasoning"]

            self.assertEqual(len(reasoning_added), 1)
            self.assertEqual(reasoning_added[0]["item"]["id"], "reasoning_1")
            self.assertEqual(len(reasoning_done), 1)
            self.assertEqual(reasoning_done[0]["item"]["status"], "completed")

    def test_responses_transport_normalizes_reasoning_state_without_raw_payload_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)
            adapter = router._adapter_for_provider("openai")  # noqa: SLF001

            upstream = {
                "id": "resp-normalized-openai",
                "object": "response",
                "status": "completed",
                "output": [
                    {
                        "id": "reasoning_1",
                        "type": "reasoning",
                        "summary": ["first reasoning step"],
                        "content": ["first reasoning step"],
                    },
                    {
                        "id": "msg_1",
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Final answer."}],
                    },
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "output_tokens_details": {"reasoning_tokens": 3}},
            }

            normalized = adapter.normalize_response(upstream, {"model": "openai/gpt-5.5"})

            self.assertEqual(normalized.text, "Final answer.")
            self.assertEqual(normalized.reasoning_summary, "first reasoning step")
            self.assertIsNotNone(normalized.reasoning_state)
            self.assertEqual(normalized.reasoning_state.provider_id, "openai")
            self.assertEqual(normalized.reasoning_state.model_id, "openai/gpt-5.5")
            self.assertFalse(normalized.reasoning_state.replayable)
            self.assertIsNotNone(normalized.raw_ref)
            self.assertEqual(normalized.raw_ref.kind, "responses_output")
            self.assertEqual(normalized.raw_ref.locator, "resp-normalized-openai")
            self.assertNotIn("response", normalized.provider_data)
            self.assertEqual(normalized.provider_data["output_types"], ["reasoning", "message"])
            self.assertEqual(normalized.warnings, [])

    def test_chat_transport_normalizes_reasoning_notice_without_raw_payload_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)
            adapter = router._adapter_for_provider("deepseek")  # noqa: SLF001

            upstream = {
                "id": "chat-normalized-deepseek",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "Inspecting the repository state.",
                            "tool_calls": [],
                        },
                    }
                ],
            }

            normalized = adapter.normalize_response(upstream, {"model": "deepseek/deepseek-v4-pro"})

            self.assertIn("Provider returned reasoning content", normalized.text)
            self.assertEqual(normalized.reasoning_summary, "Inspecting the repository state.")
            self.assertIsNotNone(normalized.reasoning_state)
            self.assertEqual(normalized.reasoning_state.provider_id, "deepseek")
            self.assertEqual(normalized.reasoning_state.model_id, "deepseek/deepseek-v4-pro")
            self.assertIsNotNone(normalized.raw_ref)
            self.assertEqual(normalized.raw_ref.kind, "chat_completion_choice")
            self.assertEqual(normalized.raw_ref.locator, "chat-normalized-deepseek")
            self.assertNotIn("response", normalized.provider_data)
            self.assertTrue(any(item.code == "reasoning_only_notice_emitted" for item in normalized.warnings))

    def test_deepseek_adapter_uses_adapter_profile_not_exact_provider_id(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            last_payload = None
            last_path = None

            def do_POST(self) -> None:  # noqa: N802
                UpstreamHandler.last_path = self.path
                length = int(self.headers.get("Content-Length", "0"))
                UpstreamHandler.last_payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if self.path != "/chat/completions":
                    self.send_response(404)
                    self.end_headers()
                    return
                body = json.dumps(
                    {
                        "id": "chatcmpl-deepseek",
                        "object": "chat.completion",
                        "created": 123,
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_port = upstream.server_address[1]
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        original_provider_token = os.environ.get("TEST_DEEPSEEK_VERIFY_KEY")
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                config = RouterConfigService(profiles, Path(temp) / "router.json")
                config.upsert_provider(
                    {
                        "id": "deepseek-verify",
                        "display_name": "DeepSeek Verify",
                        "adapter_type": "chat",
                        "base_url": f"http://127.0.0.1:{upstream_port}",
                        "default_model": "deepseek-v4-pro",
                        "env_key": "TEST_DEEPSEEK_VERIFY_KEY",
                        "auth_mode": "env_ref",
                    }
                )
                config.upsert_model(
                    {
                        "id": "deepseek-verify/deepseek-v4-pro",
                        "provider": "deepseek-verify",
                        "native_model": "deepseek-v4-pro",
                        "display_name": "DeepSeek V4 Pro",
                        "enabled": True,
                        "advertised_context_window": 1000000,
                        "ui_context_hint_only": True,
                        "adapter_profile": "deepseek",
                    }
                )
                os.environ["TEST_DEEPSEEK_VERIFY_KEY"] = "unit_secret_deepseek_test"
                router = RouterService(profiles, config, port=0)
                router.start()
                token = os.environ[ROUTER_ENV_KEY]
                request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/responses",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    data=json.dumps(
                        {
                            "model": "deepseek-verify/deepseek-v4-pro",
                            "input": "hello",
                            "stream": False,
                            "reasoning": {"effort": "xhigh"},
                        }
                    ).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))

                self.assertEqual(UpstreamHandler.last_path, "/chat/completions")
                self.assertEqual(UpstreamHandler.last_payload["thinking"]["type"], "enabled")
                self.assertEqual(payload["output_text"], "ok")
        finally:
            upstream.shutdown()
            upstream.server_close()
            if router is not None:
                router.stop()
            if original_provider_token is None:
                os.environ.pop("TEST_DEEPSEEK_VERIFY_KEY", None)
            else:
                os.environ["TEST_DEEPSEEK_VERIFY_KEY"] = original_provider_token

    def test_chat_streaming_translates_tool_calls(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            last_payload = None

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                UpstreamHandler.last_payload = json.loads(self.rfile.read(length).decode("utf-8"))
                events = [
                    {"choices": [{"delta": {"reasoning_content": "hidden stream reasoning"}}]},
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "id": "call_ask",
                                            "type": "function",
                                            "function": {"name": "request_user_input", "arguments": '{"questions":['},
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {
                        "choices": [
                            {
                                "delta": {
                                    "tool_calls": [
                                        {
                                            "index": 0,
                                            "function": {"arguments": '{"id":"q","question":"Pick one"}'},
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                    {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "]}"}}]}}]},
                    {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}},
                ]
                body = "".join(f"data: {json.dumps(event)}\n\n" for event in events).encode("utf-8") + b"data: [DONE]\n\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_port = upstream.server_address[1]
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        original_provider_token = os.environ.get("TEST_DEEPSEEK_STREAM_KEY")
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                profiles.upsert_profile(
                    {
                        "profile_id": "deepseek-stream",
                        "label": "DeepSeek Stream",
                        "type": "custom_provider",
                        "provider_id": "deepseek-stream",
                        "base_url": f"http://127.0.0.1:{upstream_port}",
                        "model": "deepseek-v4-pro",
                        "reasoning_effort": "xhigh",
                        "wire_api": "chat",
                        "env_key": "TEST_DEEPSEEK_STREAM_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    }
                )
                os.environ["TEST_DEEPSEEK_STREAM_KEY"] = "unit_secret_deepseek_test"
                router = RouterService(profiles, port=0)
                router.start()
                token = os.environ[ROUTER_ENV_KEY]
                request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/responses",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    data=json.dumps(
                        {
                            "model": "deepseek-stream/deepseek-v4-pro",
                            "input": "ask",
                            "stream": True,
                            "tools": [{"type": "function", "name": "request_user_input", "parameters": {"type": "object"}}],
                        }
                    ).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    sse_text = response.read().decode("utf-8")

                self.assertIn('"type": "function_call"', sse_text)
                self.assertIn('"name": "request_user_input"', sse_text)
                self.assertIn('"call_id": "call_ask"', sse_text)
                self.assertIn('"type": "reasoning"', sse_text)
                self.assertIn("hidden stream reasoning", sse_text)
                self.assertLess(sse_text.index('"id": "reasoning_stream"'), sse_text.index('"type": "response.completed"'))
                self.assertEqual(UpstreamHandler.last_payload["stream_options"], {"include_usage": True})
                self.assertIn('"input_tokens": 10', sse_text)
        finally:
            upstream.shutdown()
            upstream.server_close()
            if router is not None:
                router.stop()
            if original_provider_token is None:
                os.environ.pop("TEST_DEEPSEEK_STREAM_KEY", None)
            else:
                os.environ["TEST_DEEPSEEK_STREAM_KEY"] = original_provider_token

    def test_chat_streaming_reasoning_only_has_visible_notice(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                _ = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                events = [
                    {"choices": [{"delta": {"reasoning_content": "thinking without final content"}}]},
                    {"choices": [], "usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10}},
                ]
                body = "".join(f"data: {json.dumps(event)}\n\n" for event in events).encode("utf-8") + b"data: [DONE]\n\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_port = upstream.server_address[1]
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        original_provider_token = os.environ.get("TEST_DEEPSEEK_REASONING_ONLY_KEY")
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                profiles.upsert_profile(
                    {
                        "profile_id": "deepseek-reasoning-only",
                        "label": "DeepSeek Reasoning Only",
                        "type": "custom_provider",
                        "provider_id": "deepseek",
                        "base_url": f"http://127.0.0.1:{upstream_port}",
                        "model": "deepseek-v4-pro",
                        "reasoning_effort": "xhigh",
                        "wire_api": "chat",
                        "env_key": "TEST_DEEPSEEK_REASONING_ONLY_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    }
                )
                os.environ["TEST_DEEPSEEK_REASONING_ONLY_KEY"] = "unit_secret_deepseek_test"
                router = RouterService(profiles, port=0)
                router.start()
                token = os.environ[ROUTER_ENV_KEY]
                request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/responses",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    data=json.dumps(
                        {
                            "model": "deepseek/deepseek-v4-pro",
                            "input": "reply ok",
                            "stream": True,
                        }
                    ).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    sse_text = response.read().decode("utf-8")

                self.assertIn("Provider returned reasoning content but no final assistant message", sse_text)
                self.assertIn("thinking without final content", sse_text)
                self.assertIn('"output_text": "(Provider returned reasoning content but no final assistant message.', sse_text)
        finally:
            upstream.shutdown()
            upstream.server_close()
            if router is not None:
                router.stop()
            if original_provider_token is None:
                os.environ.pop("TEST_DEEPSEEK_REASONING_ONLY_KEY", None)
            else:
                os.environ["TEST_DEEPSEEK_REASONING_ONLY_KEY"] = original_provider_token

    def test_kimi_adapter_maps_thinking_policy_and_streams_sse(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            last_payload = None

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                UpstreamHandler.last_payload = json.loads(self.rfile.read(length).decode("utf-8"))
                body = json.dumps(
                    {
                        "id": "chatcmpl-kimi",
                        "object": "chat.completion",
                        "created": 321,
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "kimi ok"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 15, "completion_tokens": 20, "total_tokens": 35},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_port = upstream.server_address[1]
        threading.Thread(target=upstream.serve_forever, daemon=True).start()

        original_router_token = os.environ.get(ROUTER_ENV_KEY)
        original_provider_token = os.environ.get("TEST_KIMI_PROVIDER_KEY")
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                profiles.upsert_profile(
                    {
                        "profile_id": "kimi-router",
                        "label": "Kimi Router",
                        "type": "custom_provider",
                        "provider_id": "kimi",
                        "base_url": f"http://127.0.0.1:{upstream_port}",
                        "model": "kimi-k2.6",
                        "reasoning_effort": "max",
                        "wire_api": "chat",
                        "env_key": "TEST_KIMI_PROVIDER_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    }
                )
                os.environ["TEST_KIMI_PROVIDER_KEY"] = "unit_secret_kimi_test"
                router = RouterService(profiles, port=0)
                router.start()
                token = os.environ[ROUTER_ENV_KEY]

                request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/responses",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    data=json.dumps(
                        {
                            "model": "kimi/kimi-k2.6",
                            "input": "hello",
                            "stream": True,
                            "tool_choice": "required",
                            "tools": [{"type": "function", "name": "update_plan", "description": "update", "parameters": {"type": "object"}}],
                        }
                    ).encode("utf-8"),
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    sse_text = response.read().decode("utf-8")

                self.assertEqual(UpstreamHandler.last_payload["model"], "kimi-k2.6")
                self.assertEqual(UpstreamHandler.last_payload["thinking"]["keep"], "all")
                self.assertEqual(UpstreamHandler.last_payload["tool_choice"], "auto")
                self.assertGreaterEqual(int(UpstreamHandler.last_payload["max_tokens"]), 32768)
                self.assertIn('"type": "response.created"', sse_text)
                self.assertIn('"type": "response.completed"', sse_text)
                self.assertIn('[DONE]', sse_text)
        finally:
            upstream.shutdown()
            upstream.server_close()
            if router is not None:
                router.stop()
            if original_router_token is None:
                os.environ.pop(ROUTER_ENV_KEY, None)
            else:
                os.environ[ROUTER_ENV_KEY] = original_router_token
            if original_provider_token is None:
                os.environ.pop("TEST_KIMI_PROVIDER_KEY", None)
            else:
                os.environ["TEST_KIMI_PROVIDER_KEY"] = original_provider_token

    def test_profile_service_rejects_secret_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ProfileService(Path(temp) / "profiles.json")
            with self.assertRaises(ValueError):
                service.upsert_profile(
                    {
                        "profile_id": "bad",
                        "label": "Bad",
                        "type": "custom_provider",
                        "provider_id": "openai",
                        "model": "gpt-test",
                        "reasoning_effort": "high",
                        "wire_api": "responses",
                        "env_key": "OPENAI_API_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                        "api_key": "should-not-be-here",
                    }
                )

    def test_profile_service_resolves_provider_id_for_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ProfileService(Path(temp) / "profiles.json")
            service.upsert_profile(
                {
                    "profile_id": "deepseek-default",
                    "label": "DeepSeek Default",
                    "type": "custom_provider",
                    "provider_id": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "wire_api": "responses",
                    "env_key": "DEEPSEEK_API_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            service.upsert_profile(
                {
                    "profile_id": "deepseek-v4-pro-max",
                    "label": "DeepSeek V4 Pro Max",
                    "type": "custom_provider",
                    "provider_id": "deepseek",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "wire_api": "responses",
                    "env_key": "DEEPSEEK_API_KEY",
                    "auth_mode": "session_paste",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            service.upsert_profile(
                {
                    "profile_id": "solo-provider-profile",
                    "label": "Solo Provider",
                    "type": "custom_provider",
                    "provider_id": "solo-provider",
                    "base_url": "https://example.invalid/v1",
                    "model": "solo-model",
                    "reasoning_effort": "high",
                    "wire_api": "responses",
                    "env_key": "SOLO_PROVIDER_API_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )

            self.assertEqual(service.resolve_runtime_profile("deepseek")["profile_id"], "deepseek-default")
            self.assertEqual(service.resolve_runtime_profile("deepseek-v4-pro-max")["provider_id"], "deepseek")
            self.assertEqual(service.resolve_runtime_profile("solo-provider")["profile_id"], "solo-provider-profile")

    def test_profile_service_resolves_provider_aliases_and_seeds_registry_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ProfileService(Path(temp) / "profiles.json")
            profiles = service.list_profiles()["profiles"]
            profile_ids = {item["profile_id"] for item in profiles}

            self.assertIn("qwen-default", profile_ids)
            self.assertIn("kimi-default", profile_ids)
            self.assertIn("glm-default", profile_ids)
            self.assertEqual(service.resolve_runtime_profile("dashscope")["provider_id"], "qwen")
            self.assertEqual(service.resolve_runtime_profile("moonshot")["provider_id"], "kimi")
            self.assertEqual(service.resolve_runtime_profile("zai")["provider_id"], "glm")

    def test_history_projector_repairs_missing_tool_results_and_drops_cross_provider_reasoning(self) -> None:
        projected = HistoryProjector().project(
            source_provider="deepseek",
            target_provider="glm",
            neutral_messages=[
                NeutralMessage(
                    role="assistant",
                    text="",
                    tool_call_id="call_1",
                    tool_name="update_plan",
                    provider_data={"arguments_json": "{\"status\":\"ok\"}"},
                ),
            ],
            artifacts=[
                ReasoningArtifact(
                    provider_id="deepseek",
                    model_id="deepseek-v4-pro",
                    kind="reasoning",
                    replayable=False,
                    payload={"summary": ["internal chain"]},
                )
            ],
        )

        self.assertEqual(projected.dropped_artifacts, 1)
        self.assertEqual(projected.repaired_tool_pairs, 1)
        self.assertTrue(any(item.get("role") == "tool" for item in projected.messages))
        self.assertTrue(any("Opaque provider reasoning artifacts were dropped" in warning for warning in projected.warnings))

    def test_router_config_tracks_models_and_sanitized_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            config = RouterConfigService(profiles, Path(temp) / "router.json")
            provider = config.upsert_provider(
                {
                    "id": "deepseek",
                    "display_name": "DeepSeek",
                    "adapter_type": "chat",
                    "base_url": "https://api.deepseek.com",
                    "default_model": "deepseek-v4-pro",
                    "env_key": "DEEPSEEK_API_KEY",
                    "auth_mode": "os_keychain",
                    "auth_key_ref": "wincred:deepseek",
                }
            )
            model = config.upsert_model(
                {
                    "id": "deepseek/deepseek-v4-flash",
                    "provider": "deepseek",
                    "native_model": "deepseek-v4-flash",
                    "display_name": "DeepSeek V4 Flash",
                    "enabled": True,
                    "advertised_context_window": 1000000,
                    "ui_context_hint_only": True,
                    "adapter_profile": "default",
                }
            )
            exported = config.export_sanitized()
            self.assertEqual(provider["id"], "deepseek")
            self.assertEqual(model["provider"], "deepseek")
            self.assertEqual(exported["providers"][0]["auth_key_ref"], None)
            self.assertIn("deepseek/deepseek-v4-flash", {item["id"] for item in exported["models"]})

    def test_provider_profiles_seed_reasoning_and_temperature_defaults(self) -> None:
        deepseek = get_provider_profile("deepseek").to_default_profile()
        qwen = get_provider_profile("qwen").to_default_profile()
        kimi = get_provider_profile("kimi").to_default_profile()

        self.assertEqual(deepseek["supported_reasoning_levels"], ["high", "xhigh", "max"])
        self.assertEqual(deepseek["default_reasoning_level"], "xhigh")
        self.assertEqual(qwen["temperature_adapter_policy"], "qwen_omit_zero_clamp_1")
        self.assertAlmostEqual(float(qwen["provider_temperature_min"]), 0.00001)
        self.assertEqual(kimi["temperature_default"], 1.0)
        self.assertEqual(kimi["provider_temperature_max"], 1.0)

    def test_router_config_uses_provider_profile_defaults_for_new_provider_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            config = RouterConfigService(profiles, Path(temp) / "router.json")
            provider = config.upsert_provider(
                {
                    "id": "deepseek-alt",
                    "display_name": "DeepSeek Alt",
                    "enabled": True,
                    "adapter_type": "chat",
                    "base_url": "https://api.deepseek.com",
                    "default_model": "deepseek-v4-pro",
                    "env_key": "DEEPSEEK_API_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            model = next(item for item in config.models() if item["id"] == "deepseek-alt/deepseek-v4-pro")
            profile = next(item for item in profiles.list_profiles()["profiles"] if item["profile_id"] == "deepseek-alt-default")

            self.assertEqual(provider["supported_reasoning_levels"], ["high", "xhigh", "max"])
            self.assertEqual(provider["default_reasoning_level"], "xhigh")
            self.assertEqual(model["supported_reasoning_levels"], ["high", "xhigh", "max"])
            self.assertEqual(model["default_reasoning_level"], "xhigh")
            self.assertEqual(model["temperature_adapter_policy"], "pass_through_0_2")
            self.assertEqual(profile["supported_reasoning_levels"], ["high", "xhigh", "max"])
            self.assertEqual(profile["reasoning_effort"], "xhigh")

    def test_model_catalog_known_functions_fall_back_to_provider_profiles(self) -> None:
        self.assertEqual(known_reasoning_efforts("deepseek", "deepseek-v4-pro"), ["high", "xhigh", "max"])
        self.assertEqual(known_input_modalities("glm", "glm-5.2"), ["text", "image"])
        self.assertEqual(known_context_window("qwen", "qwen3.7-plus"), 1_000_000)

    def test_metadata_seed_import_and_effective_catalog_are_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            config = RouterConfigService(profiles, Path(temp) / "router.json")
            router = RouterService(profiles, config, port=0)
            metadata = MetadataService(config, router, Path(temp) / "sources.json", Path(temp) / "report")

            imported = metadata.import_seed(apply=True)
            catalog = metadata.effective_catalog()
            catalog_ids = {item["id"] for item in catalog["models"]}
            deepseek = next(item for item in catalog["models"] if item["id"] == "deepseek/deepseek-v4-pro")
            glm = next(item for item in catalog["models"] if item["id"] == "glm/glm-5.2")
            kimi = next(item for item in config.models() if item["id"] == "kimi/kimi-k2.6")

            self.assertGreaterEqual(imported["model_count"], 10)
            self.assertNotIn("yunwu/gpt-image-2", catalog_ids)
            self.assertIn("deepseek/deepseek-v4-pro", catalog_ids)
            self.assertEqual(deepseek["input_modalities"], ["text"])
            self.assertFalse(deepseek["supports_parallel_tool_calls"])
            self.assertIsNone(deepseek["apply_patch_tool_type"])
            self.assertIn("max", {item["effort"] for item in deepseek["supported_reasoning_levels"]})
            self.assertEqual(deepseek["temperature_default"], 0.0)
            self.assertTrue(deepseek["supports_mcp_tools"])
            self.assertEqual(deepseek["mcp_tool_call_policy"], "conservative")
            self.assertIn("lcr_web", deepseek["mcp_verified_servers"])
            self.assertEqual(deepseek["mcp_smoke_status"], "pass_direct_tool_call")
            self.assertEqual(deepseek["tool_web_search_support"], "verified")
            self.assertIn("request_user_input", deepseek["codex_builtin_tools"])
            self.assertIn("structured_summary_quality", deepseek["context_compaction_support"])
            self.assertIn("glm/glm-5.2", catalog_ids)
            self.assertIn("image", glm["input_modalities"])
            self.assertEqual(glm["default_reasoning_level"], "high")
            self.assertIn("image", kimi["input_modalities"])
            self.assertIn("https://platform.moonshot.ai/docs/overview", kimi["source_urls"])
            self.assertEqual(kimi["modality_limits"]["image_transport"], "chat_completions_base64_image_url")
            self.assertFalse(kimi["modality_limits"]["remote_image_url_supported"])
            self.assertTrue(any(item["id"] == "kimi/kimi-k2.7-code" for item in catalog["models"]))

    def test_metadata_report_writes_sanitized_html_and_catalog_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            config = RouterConfigService(profiles, Path(temp) / "router.json")
            router = RouterService(profiles, config, port=0)
            metadata = MetadataService(config, router, Path(temp) / "sources.json", Path(temp) / "report")
            metadata.import_seed(apply=True)

            report = metadata.metadata_report()
            html_text = Path(report["path"]).read_text(encoding="utf-8")
            catalog = json.loads(Path(report["catalog_path"]).read_text(encoding="utf-8"))

            self.assertIn("AstraBridge Catalog Report", html_text)
            self.assertIn("Secrets are not included", html_text)
            self.assertIn("Recommended", html_text)
            self.assertIn("Confidence", html_text)
            self.assertNotIn("unit_secret_", html_text)
            self.assertTrue(any(item["id"] == "qwen/qwen3.7-plus" for item in catalog["models"]))

    def test_metadata_refresh_writes_source_level_artifacts_and_partial_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            config = RouterConfigService(profiles, Path(temp) / "router.json")
            router = RouterService(profiles, config, port=0)
            metadata = MetadataService(config, router, Path(temp) / "sources.json", Path(temp) / "report")

            def fake_fetch(provider_id: str, url: str) -> dict[str, object]:
                if provider_id == "deepseek":
                    return {
                        "provider_id": provider_id,
                        "url": url,
                        "ok": True,
                        "classification": "ok",
                        "status_code": 200,
                        "duration_ms": 120,
                        "bytes": 2048,
                    }
                return {
                    "provider_id": provider_id,
                    "url": url,
                    "ok": False,
                    "classification": "timeout",
                    "error_summary": "timed out",
                    "duration_ms": 4000,
                    "bytes": 0,
                }

            with patch("astrabridge_sidecar.metadata_service._fetch_source_status", side_effect=fake_fetch):
                result = metadata.refresh(apply=False)

            self.assertEqual(result["summary"]["status"], "partial")
            self.assertTrue(Path(result["artifact_paths"]["fetch_results_path"]).exists())
            self.assertTrue(Path(result["artifact_paths"]["proposal_path"]).exists())
            self.assertTrue(Path(result["artifact_paths"]["diff_summary_path"]).exists())
            fetch_payload = json.loads(Path(result["artifact_paths"]["fetch_results_path"]).read_text(encoding="utf-8"))
            self.assertIn("results", fetch_payload)
            self.assertTrue(any(item["classification"] == "timeout" for item in fetch_payload["results"]))
            report = metadata.metadata_report()
            html_text = Path(report["path"]).read_text(encoding="utf-8")
            self.assertIn("Fetch results", html_text)
            self.assertIn("timed out", html_text)

    def test_metadata_refresh_async_job_exposes_status_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            config = RouterConfigService(profiles, Path(temp) / "router.json")
            router = RouterService(profiles, config, port=0)
            metadata = MetadataService(config, router, Path(temp) / "sources.json", Path(temp) / "report")

            with patch(
                "astrabridge_sidecar.metadata_service._fetch_source_status",
                return_value={
                    "provider_id": "deepseek",
                    "url": "https://example.com",
                    "ok": True,
                    "classification": "ok",
                    "status_code": 200,
                    "duration_ms": 50,
                    "bytes": 256,
                },
            ):
                started = metadata.start_refresh(apply=True)
                deadline = time.time() + 5
                status = metadata.refresh_status(started["job_id"])
                while status["status"] == "running" and time.time() < deadline:
                    time.sleep(0.05)
                    status = metadata.refresh_status(started["job_id"])

            self.assertIn(status["status"], {"success", "partial"})
            result = metadata.refresh_result(started["job_id"])
            self.assertTrue(result["applied"])
            self.assertGreaterEqual(result["summary"]["ok_sources"], 1)
            self.assertEqual(metadata.refresh_status()["job_id"], started["job_id"])

    def test_router_temperature_policy_from_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            config = RouterConfigService(profiles, Path(temp) / "router.json")
            router = RouterService(profiles, config, port=0)
            metadata = MetadataService(config, router, Path(temp) / "sources.json", Path(temp) / "report")
            metadata.import_seed(apply=True)

            zero = router.preview_payload({"model": "qwen/qwen3.7-plus", "input": "hello", "temperature": 0})
            high = router.preview_payload({"model": "qwen/qwen3.7-plus", "input": "hello", "temperature": 2})

            self.assertNotIn("temperature", zero["upstream_payload"])
            self.assertIn("omitted", zero["warnings"][0])
            self.assertEqual(high["upstream_payload"]["temperature"], 1.0)
            self.assertIn("caps", high["warnings"][0])

            kimi = router.preview_payload({"model": "kimi/kimi-k2.6", "input": "hello", "temperature": 0.7})
            self.assertNotIn("temperature", kimi["upstream_payload"])
            self.assertIn("only accept temperature=1", kimi["warnings"][0])

    def test_router_service_normalizes_provider_error(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = json.dumps({"error": {"type": "invalid_request_error", "message": "context length exceeded"}}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        upstream_port = upstream.server_address[1]
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        original_provider_token = os.environ.get("TEST_DEEPSEEK_PROVIDER_KEY")
        router = None
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                config = RouterConfigService(profiles, Path(temp) / "router.json")
                config.upsert_provider(
                    {
                        "id": "deepseek",
                        "display_name": "DeepSeek",
                        "adapter_type": "chat",
                        "base_url": f"http://127.0.0.1:{upstream_port}",
                        "default_model": "deepseek-v4-pro",
                        "env_key": "TEST_DEEPSEEK_PROVIDER_KEY",
                        "auth_mode": "env_ref",
                    }
                )
                os.environ["TEST_DEEPSEEK_PROVIDER_KEY"] = "unit_secret_deepseek_test"
                router = RouterService(profiles, config, port=0)
                router.start()
                token = os.environ[ROUTER_ENV_KEY]
                request = urllib.request.Request(
                    f"http://127.0.0.1:{router.status()['listen_port']}/v1/responses",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    data=json.dumps({"model": "deepseek/deepseek-v4-pro", "input": "hello", "stream": False}).encode("utf-8"),
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as captured:
                    urllib.request.urlopen(request, timeout=5)
                payload = json.loads(captured.exception.read().decode("utf-8"))
                self.assertEqual(payload["error"]["type"], "provider_error")
                self.assertEqual(payload["error"]["provider"], "deepseek")
                self.assertIn("context limit", payload["error"]["actionable_hint"].lower())
        finally:
            upstream.shutdown()
            upstream.server_close()
            if router is not None:
                router.stop()
            if original_provider_token is None:
                os.environ.pop("TEST_DEEPSEEK_PROVIDER_KEY", None)
            else:
                os.environ["TEST_DEEPSEEK_PROVIDER_KEY"] = original_provider_token

    def test_dogfood_browser_smoke_and_milestone_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "index.html").write_text("<!doctype html><title>ok</title>", encoding="utf-8")
            screenshot = root / "capture.png"
            screenshot.write_bytes(b"png")
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = DogfoodRunService(projects)

            smoke = dogfood.browser_smoke(
                {
                    "url": (workspace / "index.html").resolve().as_uri(),
                    "label": "local file smoke",
                    "screenshot_path": str(screenshot),
                    "actions": [{"type": "wait", "ms": 10}],
                }
            )
            self.assertEqual(smoke["browser_smoke"]["status"], "pass")
            self.assertEqual(smoke["browser_smoke"]["verification_level"], "screenshot_only")
            self.assertIn("No final assertions", smoke["browser_smoke"]["verification_warning"])
            self.assertEqual(smoke["browser_smoke"]["actions"][0]["type"], "wait_ms")
            self.assertNotIn("run", smoke)
            self.assertEqual(smoke["run_summary"]["latest_capture"]["path"], str(screenshot))
            self.assertEqual(smoke["run_summary"]["latest_milestone"]["label"], "Browser smoke: local file smoke")
            full_smoke = dogfood.browser_smoke(
                {
                    "url": (workspace / "index.html").resolve().as_uri(),
                    "label": "local file smoke with full run",
                    "screenshot_path": str(screenshot),
                    "expect_text": "ok",
                    "include_run": True,
                }
            )
            self.assertEqual(full_smoke["browser_smoke"]["verification_level"], "asserted")
            self.assertEqual(full_smoke["browser_smoke"]["final_assertions"][0]["type"], "expect_text")
            self.assertEqual(full_smoke["run"]["captures"][0]["path"], str(screenshot))
            run_path = workspace / ".astrabridge" / "dogfood_run.json"
            run_data = json.loads(run_path.read_text(encoding="utf-8"))
            run_data["captures"].append(str(root / "legacy-string-capture.png"))
            run_path.write_text(json.dumps(run_data), encoding="utf-8")

            milestone = dogfood.add_milestone(
                {
                    "label": "asset smoke",
                    "provider": "kimi",
                    "model": "kimi-k2.6",
                    "goal": "Build tower game",
                    "plan_step": "asset smoke",
                    "validation": ["title rendered", "no console errors"],
                    "validation_result": {"fatal_console_errors": 0},
                    "captures": [{"path": str(screenshot), "label": "gameplay", "provider": "deepseek"}],
                    "next_action": "continue visual pass",
                    "sync_run_summary": True,
                }
            )
            self.assertEqual(milestone["milestone"]["label"], "asset smoke")
            self.assertNotIn("run", milestone)
            self.assertIn("run_summary", milestone)
            self.assertEqual(milestone["run_summary"]["latest_milestone"]["label"], "asset smoke")
            self.assertEqual(milestone["milestone"]["model"], "kimi-k2.6")
            self.assertEqual(milestone["milestone"]["capture_paths"], [str(screenshot)])
            self.assertEqual(milestone["milestone"]["captures"][0]["label"], "gameplay")
            self.assertEqual(milestone["milestone"]["captures"][0]["provider"], "deepseek")
            self.assertEqual(milestone["milestone"]["validation_result"]["fatal_console_errors"], "0")
            self.assertEqual(milestone["run_summary"]["goal"], "Build tower game")
            self.assertEqual(milestone["run_summary"]["current_provider"], "kimi")
            self.assertEqual(milestone["run_summary"]["next_step"], "continue visual pass")
            self.assertEqual(milestone["run_summary"]["latest_capture"]["path"], str(screenshot))
            self.assertEqual(milestone["run_summary"]["latest_capture"]["label"], "gameplay")
            self.assertEqual(milestone["run_summary"]["latest_capture"]["provider"], "deepseek")
            updated_run_data = json.loads(run_path.read_text(encoding="utf-8"))
            self.assertTrue(all(isinstance(item, dict) for item in updated_run_data["captures"]))
            full_milestone = dogfood.add_milestone({"label": "debug full run", "include_run": True})
            self.assertIn("run", full_milestone)
            self.assertEqual(full_milestone["run"]["milestones"][-1]["label"], "debug full run")

            audit = dogfood.add_milestone(
                {
                    "label": "isolation audit",
                    "validation": ["No API key, Authorization header, or cookie was written to reports."],
                }
            )
            self.assertEqual(audit["milestone"]["label"], "isolation audit")
            failure = dogfood.add_milestone(
                {
                    "label": "failing smoke",
                    "provider": "deepseek",
                    "status": "retry",
                    "failure_reason": "map still too blocky",
                    "sync_run_summary": True,
                }
            )
            self.assertEqual(failure["run_summary"]["current_provider"], "deepseek")
            self.assertEqual(failure["run_summary"]["blocker"], "map still too blocky")
            recovered = dogfood.add_milestone(
                {
                    "label": "recovered smoke",
                    "provider": "yunwu",
                    "status": "verified",
                    "sync_run_summary": True,
                }
            )
            self.assertEqual(recovered["run_summary"]["current_provider"], "yunwu")
            self.assertEqual(recovered["run_summary"]["blocker"], "")
            with self.assertRaises(ValueError):
                dogfood.add_milestone({"label": "bad", "validation": ["Bearer unit-test-token"]})

    def test_dogfood_add_milestone_repairs_stale_summary_after_first_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = DogfoodRunService(projects)

            original_write_json = common_module.write_json
            call_count = {"value": 0}

            def flaky_write_json(path: Path, payload: object) -> None:
                call_count["value"] += 1
                mutated = json.loads(json.dumps(payload))
                if call_count["value"] == 1 and path.name == "dogfood_run.json":
                    mutated["goal"] = "STALE GOAL"
                    mutated["current_provider"] = "stale"
                    mutated["next_step"] = "stale next"
                original_write_json(path, mutated)

            with patch("astrabridge_sidecar.dogfood_run_service.write_json", flaky_write_json):
                milestone = dogfood.add_milestone(
                    {
                        "label": "repair stale summary",
                        "provider": "deepseek",
                        "model": "deepseek-v4-pro",
                        "goal": "Fresh goal",
                        "plan_step": "repair",
                        "status": "verified",
                        "next_step": "Fresh next step",
                        "sync_run_summary": True,
                    }
                )

            self.assertGreaterEqual(call_count["value"], 2)
            self.assertEqual(milestone["run_summary"]["goal"], "Fresh goal")
            self.assertEqual(milestone["run_summary"]["current_provider"], "deepseek")
            self.assertEqual(milestone["run_summary"]["next_step"], "Fresh next step")
            run_data = json.loads((workspace / ".astrabridge" / "dogfood_run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_data["goal"], "Fresh goal")
            self.assertEqual(run_data["current_provider"], "deepseek")
            self.assertEqual(run_data["next_step"], "Fresh next step")

    def test_dogfood_browser_smoke_accepts_wsl_style_file_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            html = workspace / "index.html"
            html.write_text("<!doctype html><title>ok</title>", encoding="utf-8")
            screenshot = root / "capture.png"
            screenshot.write_bytes(b"png")
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = DogfoodRunService(projects)
            raw = str(html.resolve()).replace("\\", "/")
            if len(raw) >= 2 and raw[1] == ":":
                wsl_path = f"/mnt/{raw[0].lower()}/{raw[3:]}"
            else:
                wsl_path = raw

            smoke = dogfood.browser_smoke(
                {
                    "url": "file://" + wsl_path,
                    "label": "wsl file smoke",
                    "screenshot_path": str(screenshot),
                }
            )

            self.assertEqual(smoke["browser_smoke"]["http_status"], 200)
            self.assertEqual(smoke["browser_smoke"]["status"], "pass")

    def test_dogfood_browser_smoke_normalizes_wsl_file_url_for_playwright(self) -> None:
        class CaptureDogfoodRunService(DogfoodRunService):
            def _capture_with_playwright(self, url: str, label: str, record: dict[str, object], *, actions: list[dict[str, object]] | None = None) -> None:
                del label, actions
                captured_urls.append(url)
                screenshot.write_bytes(b"png")
                record["screenshot_path"] = str(screenshot)
                record["screenshot_status"] = "captured"
                record["http_status"] = 200
                record["console_errors"] = []

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            html = workspace / "index.html"
            html.write_text("<!doctype html><title>ok</title>", encoding="utf-8")
            screenshot = root / "capture.png"
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = CaptureDogfoodRunService(projects)
            raw = str(html.resolve()).replace("\\", "/")
            if len(raw) >= 2 and raw[1] == ":":
                wsl_path = f"/mnt/{raw[0].lower()}/{raw[3:]}"
            else:
                wsl_path = raw
            captured_urls: list[str] = []

            smoke = dogfood.browser_smoke(
                {
                    "url": "file://" + wsl_path,
                    "label": "wsl file capture smoke",
                }
            )

            self.assertEqual(smoke["browser_smoke"]["status"], "pass")
            self.assertEqual(smoke["browser_smoke"]["screenshot_status"], "captured")
            self.assertEqual(len(captured_urls), 1)
            self.assertTrue(captured_urls[0].startswith("file:///"))
            self.assertNotIn("/mnt/", captured_urls[0])
            self.assertEqual(smoke["browser_smoke"]["navigation_url"], captured_urls[0])

    def test_dogfood_browser_smoke_successful_capture_overrides_stale_preflight_failure(self) -> None:
        class CaptureDogfoodRunService(DogfoodRunService):
            def _capture_with_playwright(self, url: str, label: str, record: dict[str, object], *, actions: list[dict[str, object]] | None = None) -> None:
                del url, label, actions
                screenshot.write_bytes(b"png")
                record["screenshot_path"] = str(screenshot)
                record["screenshot_status"] = "captured"
                record["http_status"] = 200
                record["console_errors"] = []

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            screenshot = root / "capture.png"
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = CaptureDogfoodRunService(projects)

            smoke = dogfood.browser_smoke(
                {
                    "url": "file:///mnt/z/not-really-there/index.html",
                    "label": "capture recovers status",
                }
            )

            self.assertEqual(smoke["browser_smoke"]["screenshot_status"], "captured")
            self.assertEqual(smoke["browser_smoke"]["http_status"], 200)
            self.assertEqual(smoke["browser_smoke"]["status"], "pass")

    def test_dogfood_browser_smoke_uses_domcontentloaded_not_networkidle(self) -> None:
        source = inspect.getsource(DogfoodRunService._capture_with_playwright)

        self.assertIn("domcontentloaded", source)
        self.assertNotIn("networkidle", source)
        self.assertIn("captured_after_failure", source)
        self.assertIn("captured_viewport_fallback", source)
        self.assertIn("fullPage: false", source)

    def test_dogfood_browser_smoke_flags_broken_local_stylesheet(self) -> None:
        class CaptureDogfoodRunService(DogfoodRunService):
            def _capture_with_playwright(self, url: str, label: str, record: dict[str, object], *, actions: list[dict[str, object]] | None = None) -> None:
                del url, label, actions
                screenshot.write_bytes(b"png")
                record["screenshot_path"] = str(screenshot)
                record["screenshot_status"] = "captured"
                record["http_status"] = 200

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "index.html").write_text('<!doctype html><link rel="stylesheet" href="style.css"><title>ok</title>', encoding="utf-8")
            (workspace / "style.css").write_text(".grid { color: red;\n", encoding="utf-8")
            screenshot = root / "capture.png"
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = CaptureDogfoodRunService(projects)

            smoke = dogfood.browser_smoke({"url": (workspace / "index.html").resolve().as_uri(), "label": "broken css"})

            self.assertEqual(smoke["browser_smoke"]["status"], "fail")
            self.assertTrue(smoke["browser_smoke"]["stylesheet_warnings"])
            self.assertIn("unclosed brace", smoke["browser_smoke"]["stylesheet_warnings"][0])

    def test_dogfood_browser_smoke_flags_stylesheet_mojibake(self) -> None:
        class CaptureDogfoodRunService(DogfoodRunService):
            def _capture_with_playwright(self, url: str, label: str, record: dict[str, object], *, actions: list[dict[str, object]] | None = None) -> None:
                del url, label, actions
                screenshot.write_bytes(b"png")
                record["screenshot_path"] = str(screenshot)
                record["screenshot_status"] = "captured"
                record["http_status"] = 200

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "index.html").write_text('<!doctype html><link rel="stylesheet" href="style.css"><title>ok</title>', encoding="utf-8")
            (workspace / "style.css").write_text("/* mojibake marker: \u9225 */\n.grid { color: red; }\n", encoding="utf-8")
            screenshot = root / "capture.png"
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            dogfood = CaptureDogfoodRunService(projects)

            smoke = dogfood.browser_smoke({"url": (workspace / "index.html").resolve().as_uri(), "label": "mojibake css"})

            self.assertEqual(smoke["browser_smoke"]["status"], "fail")
            self.assertIn("possible mojibake", smoke["browser_smoke"]["stylesheet_warnings"][0])

    def test_runtime_service_repairs_thread_defaults_from_stale_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))

            runtime._cache_thread_entry(  # type: ignore[attr-defined]
                "thread-1",
                {
                    "profile_id": "deepseek",
                    "model": "openai/gpt-5.5",
                    "reasoning_effort": "bogus",
                    "permission_mode": "wild-west",
                    "collaboration_mode": "chaos",
                },
            )

            settings = runtime._thread_settings_for("thread-1")  # type: ignore[attr-defined]

            self.assertEqual(settings["profile_id"], "deepseek-default")
            self.assertEqual(settings["model"], "deepseek-v4-pro")
            self.assertEqual(settings["reasoning_effort"], "high")
            self.assertEqual(settings["permission_mode"], "auto")
            self.assertEqual(settings["collaboration_mode"], "default")

            cache = json.loads((projects.require_shell_state_root() / "thread_cache.json").read_text(encoding="utf-8"))
            entry = cache["by_id"]["thread-1"]
            self.assertEqual(entry["profile_id"], "deepseek-default")
            self.assertEqual(entry["model"], "deepseek-v4-pro")
            self.assertEqual(entry["reasoning_effort"], "high")
            self.assertEqual(entry["permission_mode"], "auto")
            self.assertEqual(entry["collaboration_mode"], "default")

    def test_runtime_supervisor_aggregates_plan_token_and_guard_without_secrets(self) -> None:
        class FakeProjects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-1",
                "default_profile_id": "deepseek",
                "default_model": "deepseek-v4-pro",
                "default_effort": "max",
                "ui_preferences": {},
            }

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            interrupted: list[tuple[dict[str, object], str, str]] = []
            supervisor_events: list[dict[str, object]] = []

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 3,
                    "events": [
                        {
                            "type": "notification",
                            "method": "turn/plan/updated",
                            "timestamp": "2026-06-12T00:00:00+00:00",
                            "params": {
                                "threadId": "thread-1",
                                "turnId": "turn-1",
                                "explanation": "test",
                                "plan": [{"step": "Run smoke", "status": "in_progress"}],
                            },
                        },
                        {
                            "type": "notification",
                            "method": "thread/tokenUsage/updated",
                            "timestamp": "2026-06-12T00:00:01+00:00",
                            "params": {
                                "threadId": "thread-1",
                                "turnId": "turn-1",
                                "tokenUsage": {
                                    "total": {"totalTokens": 91},
                                    "modelContextWindow": 100,
                                },
                            },
                        },
                        {
                            "type": "notification",
                            "method": "thread/status/changed",
                            "params": {"threadId": "thread-1", "status": {"type": "active"}},
                        },
                    ],
                }

            def compact_thread(self, profile, thread_id):  # noqa: ANN001
                return {"started": True, "thread_id": thread_id}

            def interrupt_turn(self, profile, thread_id, turn_id):  # noqa: ANN001
                self.interrupted.append((profile, thread_id, turn_id))
                return {"interrupt": {"ok": True}}

            def record_supervisor_event(self, event):  # noqa: ANN001
                self.supervisor_events.append(event)

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": True, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

            def add_note(self, note: str) -> None:
                self.note = note

        runtime = FakeRuntime()
        supervisor = RuntimeSupervisorService(FakeProjects(), runtime, FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-1", profile={"provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"})
        self.assertEqual(status["plan"]["steps"][0]["step"], "Run smoke")
        self.assertEqual(status["thread_status"]["thread_id"], "thread-1")
        self.assertEqual(status["guard"]["level"], "pause")
        self.assertFalse(status["guard"]["should_pause"])
        self.assertTrue(status["guard"]["requires_decision"])
        self.assertTrue(status["guard"]["deferred_until_turn_boundary"])
        self.assertEqual(runtime.interrupted, [])
        self.assertNotIn("auto_pause", status["guard"])
        self.assertEqual(runtime.supervisor_events[0]["event"], "context_guard")
        self.assertEqual(runtime.supervisor_events[0]["level"], "pause")

    def test_runtime_supervisor_falls_back_to_task_plan_after_handoff(self) -> None:
        class FakeProjects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-new",
                "default_profile_id": "deepseek",
                "default_model": "deepseek-v4-pro",
                "default_effort": "max",
                "ui_preferences": {},
            }

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeTasks:
            def current_task(self) -> dict[str, object]:
                return {
                    "active_provider_thread_id": "thread-new",
                    "plan": {
                        "turn_id": "turn-old",
                        "steps": [{"step": "Reuse task plan", "status": "in_progress"}],
                        "updated_at": "2026-06-19T00:00:00+00:00",
                    },
                }

            def active_provider_thread(self, include_missing_fallback: bool = False) -> dict[str, object]:  # noqa: FBT001, FBT002
                return {"thread_id": "thread-new"}

        class FakeRuntime:
            _tasks = FakeTasks()

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {"cursor": 0, "events": []}

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": True, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())
        status = supervisor.status(profile={"provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"})
        self.assertEqual(status["thread_id"], "thread-new")
        self.assertEqual(status["thread_status"]["thread_id"], "thread-new")
        self.assertEqual(status["plan"]["source"], "task/plan")
        self.assertEqual(status["plan"]["steps"][0]["step"], "Reuse task plan")

    def test_runtime_supervisor_does_not_auto_interrupt_pending_approval(self) -> None:
        class FakeProjects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-approval",
                "default_profile_id": "deepseek",
                "default_model": "deepseek-v4-pro",
                "default_effort": "max",
                "ui_preferences": {},
            }

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            interrupted: list[tuple[dict[str, object], str, str]] = []
            supervisor_events: list[dict[str, object]] = []

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 3,
                    "events": [
                        {
                            "type": "notification",
                            "method": "thread/tokenUsage/updated",
                            "timestamp": "2026-06-12T00:00:01+00:00",
                            "params": {
                                "threadId": "thread-approval",
                                "turnId": "turn-approval",
                                "tokenUsage": {"total": {"totalTokens": 95}, "modelContextWindow": 100},
                            },
                        },
                        {
                            "type": "notification",
                            "method": "thread/status/changed",
                            "timestamp": "2026-06-12T00:00:02+00:00",
                            "params": {
                                "threadId": "thread-approval",
                                "status": {"type": "active", "activeFlags": ["waitingOnApproval"]},
                            },
                        },
                    ],
                }

            def interrupt_turn(self, profile, thread_id, turn_id):  # noqa: ANN001
                self.interrupted.append((profile, thread_id, turn_id))
                return {"interrupt": {"ok": True}}

            def record_supervisor_event(self, event):  # noqa: ANN001
                self.supervisor_events.append(event)

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {
                    "modals": [
                        {
                            "thread_id": "thread-approval",
                            "turn_id": "turn-approval",
                            "params": {"authorization": "Bearer unit"},
                        }
                    ]
                }

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

            def add_note(self, note: str) -> None:
                self.note = note

        runtime = FakeRuntime()
        supervisor = RuntimeSupervisorService(FakeProjects(), runtime, FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-approval", profile={"provider_id": "deepseek"})
        self.assertEqual(status["guard"]["level"], "approval_wait")
        self.assertFalse(status["guard"]["should_pause"])
        self.assertEqual(status["watchdog"]["level"], "waiting")
        self.assertEqual(status["watchdog"]["recommended_action"], "resolve_approval")
        self.assertEqual(runtime.interrupted, [])
        self.assertNotIn("unit_secret", json.dumps(status))

    def test_runtime_supervisor_suppresses_stale_system_error_from_completed_thread_snapshot(self) -> None:
        class FakeProjects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-1",
                "default_profile_id": "qwen-default",
                "default_model": "qwen3.7-plus",
                "default_effort": "high",
                "ui_preferences": {},
            }

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            supervisor_events: list[dict[str, object]] = []

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 2,
                    "events": [
                        {
                            "type": "notification",
                            "method": "thread/status/changed",
                            "timestamp": "2026-06-12T00:00:00+00:00",
                            "params": {"threadId": "thread-1", "status": {"type": "systemError"}},
                        },
                        {
                            "type": "notification",
                            "method": "turn/completed",
                            "timestamp": "2026-06-12T00:00:01+00:00",
                            "params": {
                                "threadId": "thread-1",
                                "turn": {"id": "turn-1", "status": "completed", "error": None},
                            },
                        },
                    ],
                }

            def read_thread(self, profile, thread_id):  # noqa: ANN001
                return {
                    "thread": {
                        "id": thread_id,
                        "status": {"type": "systemError"},
                        "turns": [
                            {"id": "turn-1", "status": "completed", "error": None, "items": []},
                        ],
                    }
                }

            def record_supervisor_event(self, event):  # noqa: ANN001
                self.supervisor_events.append(event)

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-1", profile={"profile_id": "qwen-default", "provider_id": "qwen"})

        self.assertEqual(status["thread_status"]["type"], "idle")
        self.assertTrue(status["thread_status"]["stale_error_normalized"])
        self.assertIsNone(status["runtime_error"])

    def test_runtime_supervisor_suppresses_stale_not_loaded_from_completed_thread_snapshot(self) -> None:
        class FakeProjects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-1",
                "default_profile_id": "qwen-default",
                "default_model": "qwen3.7-plus",
                "default_effort": "high",
                "ui_preferences": {},
            }

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            supervisor_events: list[dict[str, object]] = []

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {"cursor": 0, "events": []}

            def read_thread(self, profile, thread_id):  # noqa: ANN001
                return {
                    "thread": {
                        "id": thread_id,
                        "status": {"type": "notLoaded"},
                        "turns": [
                            {"id": "turn-1", "status": "completed", "error": None, "items": []},
                        ],
                    }
                }

            def record_supervisor_event(self, event):  # noqa: ANN001
                self.supervisor_events.append(event)

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-1", profile={"profile_id": "qwen-default", "provider_id": "qwen"})

        self.assertEqual(status["thread_status"]["type"], "idle")
        self.assertTrue(status["thread_status"]["stale_error_normalized"])
        self.assertIsNone(status["runtime_error"])

    def test_runtime_supervisor_suppresses_runtime_error_when_snapshot_is_already_normalized_idle(self) -> None:
        class FakeProjects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-1",
                "default_profile_id": "qwen-default",
                "default_model": "qwen3.7-plus",
                "default_effort": "high",
                "ui_preferences": {},
            }

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            supervisor_events: list[dict[str, object]] = []

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 2,
                    "events": [
                        {
                            "type": "notification",
                            "method": "thread/status/changed",
                            "timestamp": "2026-06-12T00:00:00+00:00",
                            "params": {"threadId": "thread-1", "status": {"type": "systemError"}},
                        },
                        {
                            "type": "notification",
                            "method": "error",
                            "timestamp": "2026-06-12T00:00:01+00:00",
                            "params": {"threadId": "thread-1", "error": {"message": "stream closed"}},
                        },
                    ],
                }

            def read_thread(self, profile, thread_id):  # noqa: ANN001
                return {
                    "thread": {
                        "id": thread_id,
                        "status": {
                            "type": "idle",
                            "stale_error_type": "systemError",
                            "stale_error_normalized": True,
                        },
                        "turns": [
                            {"id": "turn-1", "status": "completed", "error": None, "items": []},
                        ],
                    }
                }

            def record_supervisor_event(self, event):  # noqa: ANN001
                self.supervisor_events.append(event)

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-1", profile={"profile_id": "qwen-default", "provider_id": "qwen"})

        self.assertEqual(status["thread_status"]["type"], "idle")
        self.assertTrue(status["thread_status"]["stale_error_normalized"])
        self.assertIsNone(status["runtime_error"])

    def test_runtime_supervisor_falls_back_to_plan_delta(self) -> None:
        class FakeProjects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-plan",
                "default_profile_id": "kimi",
                "default_model": "kimi-k2.6",
                "default_effort": "xhigh",
                "ui_preferences": {},
            }

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 2,
                    "events": [
                        {
                            "type": "notification",
                            "method": "item/plan/delta",
                            "timestamp": "2026-06-12T00:00:00+00:00",
                            "params": {"threadId": "thread-plan", "turnId": "turn-plan", "delta": "Plan\n- Inspect UI\n"},
                        },
                        {
                            "type": "notification",
                            "method": "item/plan/delta",
                            "timestamp": "2026-06-12T00:00:01+00:00",
                            "params": {"threadId": "thread-plan", "turnId": "turn-plan", "delta": "- Run smoke\n"},
                        },
                    ],
                }

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

            def add_note(self, note: str) -> None:
                self.note = note

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-plan", profile={"provider_id": "kimi", "model": "kimi-k2.6", "reasoning_effort": "xhigh"})
        self.assertEqual(status["plan"]["source"], "item/plan/delta")
        self.assertIn("Inspect UI", status["plan"]["steps"][1]["step"])

    def test_runtime_supervisor_compaction_completed_suppresses_stale_token_pause(self) -> None:
        class FakeProjects:
            current_project = {
                "name": "Demo",
                "current_thread_id": "thread-compact",
                "default_profile_id": "deepseek",
                "default_model": "deepseek-v4-pro",
                "default_effort": "max",
                "ui_preferences": {},
            }

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            interrupted: list[tuple[dict[str, object], str, str]] = []

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 5,
                    "events": [
                        {
                            "type": "notification",
                            "method": "thread/tokenUsage/updated",
                            "timestamp": "2026-06-12T00:00:01+00:00",
                            "params": {
                                "threadId": "thread-compact",
                                "turnId": "turn-before-compact",
                                "tokenUsage": {
                                    "total": {"totalTokens": 91},
                                    "modelContextWindow": 100,
                                },
                            },
                        },
                        {
                            "type": "notification",
                            "method": "item/started",
                            "timestamp": "2026-06-12T00:00:02+00:00",
                            "params": {
                                "threadId": "thread-compact",
                                "turnId": "turn-compact",
                                "item": {"type": "contextCompaction", "id": "compact-1"},
                            },
                        },
                        {
                            "type": "notification",
                            "method": "item/completed",
                            "timestamp": "2026-06-12T00:00:03+00:00",
                            "params": {
                                "threadId": "thread-compact",
                                "turnId": "turn-compact",
                                "item": {"type": "contextCompaction", "id": "compact-1"},
                            },
                        },
                        {
                            "type": "notification",
                            "method": "thread/status/changed",
                            "timestamp": "2026-06-12T00:00:04+00:00",
                            "params": {"threadId": "thread-compact", "status": {"type": "active"}},
                        },
                    ],
                }

            def interrupt_turn(self, profile, thread_id, turn_id):  # noqa: ANN001
                self.interrupted.append((profile, thread_id, turn_id))
                return {"interrupt": {"ok": True}}

            def record_supervisor_event(self, event):  # noqa: ANN001
                self.event = event

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

            def add_note(self, note: str) -> None:
                self.note = note

        runtime = FakeRuntime()
        supervisor = RuntimeSupervisorService(FakeProjects(), runtime, FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-compact", profile={"provider_id": "deepseek"})
        self.assertEqual(status["guard"]["level"], "compacted")
        self.assertEqual(status["guard"]["recommended_action"], "health_check")
        self.assertTrue(status["guard"]["stale_context_estimate"])
        self.assertEqual(status["compaction"]["status"], "completed")
        self.assertEqual(runtime.interrupted, [])

    def test_runtime_supervisor_marks_missing_thread_status(self) -> None:
        class FakeProjects:
            current_project = {"name": "Demo", "current_thread_id": "thread-missing", "ui_preferences": {}}

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 2,
                    "events": [
                        {
                            "type": "notification",
                            "method": "thread/status/changed",
                            "timestamp": "2026-06-12T00:00:00+00:00",
                            "params": {"threadId": "thread-missing", "status": {"type": "active"}},
                        },
                        {
                            "type": "provider_thread_missing",
                            "timestamp": "2026-06-12T00:00:01+00:00",
                            "thread_id": "thread-missing",
                            "reason": "turn_interrupt_thread_missing",
                        },
                    ],
                }

            def record_supervisor_event(self, event):  # noqa: ANN001
                self.event = event

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

            def add_note(self, note: str) -> None:
                self.note = note

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-missing", profile={"provider_id": "deepseek"})
        self.assertEqual(status["thread_status"]["type"], "missing")
        self.assertEqual(status["guard"]["level"], "ok")

    def test_runtime_supervisor_uses_effective_provider_route_thread_for_guard(self) -> None:
        class FakeProjects:
            current_project = {"name": "Demo", "current_thread_id": "thread-selected", "ui_preferences": {}}

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeTaskService:
            def current_task(self) -> dict[str, object]:
                return {
                    "provider_threads": [
                        {
                            "thread_id": "thread-selected",
                            "provider_id": "deepseek",
                            "model": "deepseek-v4-pro",
                            "reasoning_effort": "high",
                            "missing_at": "2026-06-16T19:00:00+08:00",
                        },
                        {
                            "thread_id": "thread-effective",
                            "provider_id": "deepseek",
                            "model": "deepseek/deepseek-v4-pro",
                            "reasoning_effort": "xhigh",
                        },
                    ]
                }

            def needs_provider_handoff(self, *, thread_id: str | None, profile_id: str | None, model: str | None, effort: str | None) -> bool:
                return True

            def find_provider_thread(self, *, profile_id: str | None, provider_id: str | None = None, model: str | None, effort: str | None):
                return {"thread_id": "thread-effective"}

        class FakeRuntime:
            _tasks = FakeTaskService()

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 2,
                    "events": [
                        {
                            "type": "notification",
                            "method": "thread/tokenUsage/updated",
                            "timestamp": "2026-06-12T00:00:01+00:00",
                            "params": {
                                "threadId": "thread-effective",
                                "turnId": "turn-effective",
                                "tokenUsage": {"total": {"totalTokens": 95}, "modelContextWindow": 100},
                            },
                        }
                    ],
                }

            def record_supervisor_event(self, event):  # noqa: ANN001
                self.event = event

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

            def add_note(self, note: str) -> None:
                self.note = note

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())
        status = supervisor.status(
            thread_id="thread-selected",
            profile={"provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
        )
        self.assertEqual(status["requested_thread_id"], "thread-selected")
        self.assertEqual(status["effective_thread_id"], "thread-effective")
        self.assertEqual(status["guard"]["level"], "pause")

    def test_runtime_supervisor_marks_compaction_running_as_stale_after_later_activity(self) -> None:
        class FakeProjects:
            current_project = {"name": "Demo", "current_thread_id": "thread-stale-compact", "ui_preferences": {}}

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {
                    "cursor": 3,
                    "events": [
                        {
                            "type": "notification",
                            "method": "item/started",
                            "timestamp": "2026-06-12T00:00:00+00:00",
                            "params": {
                                "threadId": "thread-stale-compact",
                                "turnId": "turn-compact",
                                "item": {"type": "contextCompaction", "id": "compact-1"},
                            },
                        },
                        {
                            "type": "notification",
                            "method": "thread/status/changed",
                            "timestamp": "2026-06-12T00:00:10+00:00",
                            "params": {"threadId": "thread-stale-compact", "status": {"type": "idle"}},
                        },
                    ],
                }

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

            def add_note(self, note: str) -> None:
                self.note = note

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())
        status = supervisor.status(thread_id="thread-stale-compact", profile={"provider_id": "deepseek"})
        self.assertEqual(status["compaction"]["status"], "stale_running")
        self.assertIn("stale", status["compaction"]["message"])

    def test_runtime_supervisor_decisions_call_runtime_actions(self) -> None:
        class FakeProjects:
            current_project = {"current_thread_id": "thread-1", "ui_preferences": {}}

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            continued: list[str] = []

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {"cursor": 0, "events": []}

            def compact_thread(self, profile, thread_id):  # noqa: ANN001
                return {"action": "compact", "thread_id": thread_id, "provider": profile.get("provider_id")}

            def fork_thread(self, profile, *, thread_id, model, effort, permission_mode, name=None):  # noqa: ANN001
                return {
                    "action": "fork",
                    "thread_id": thread_id,
                    "model": model,
                    "effort": effort,
                    "permission_mode": permission_mode,
                    "name": name,
                }

            def interrupt_turn(self, profile, thread_id, turn_id):  # noqa: ANN001
                return {"action": "interrupt", "thread_id": thread_id, "turn_id": turn_id}

            def allow_context_guard_continue_once(self, thread_id):  # noqa: ANN001
                self.continued.append(thread_id)
                return {"allowed": True, "thread_id": thread_id}

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            notes: list[str] = []

            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

            def add_note(self, note: str) -> None:
                self.notes.append(note)

        dogfood = FakeDogfood()
        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), dogfood)
        profile = {"provider_id": "deepseek"}

        compact = supervisor.decision({"action": "compact", "thread_id": "thread-1"}, profile)
        self.assertEqual(compact["result"]["action"], "compact")
        self.assertTrue(compact["health_check"]["recommended"])

        fork = supervisor.decision(
            {
                "action": "fork",
                "thread_id": "thread-1",
                "model": "deepseek-v4-pro",
                "effort": "max",
                "permission_mode": "auto",
            },
            profile,
        )
        self.assertEqual(fork["result"]["model"], "deepseek-v4-pro")

        interrupted = supervisor.decision({"action": "interrupt", "thread_id": "thread-1", "turn_id": "turn-1"}, profile)
        self.assertEqual(interrupted["result"]["turn_id"], "turn-1")
        continued = supervisor.decision({"action": "continue", "thread_id": "thread-1"}, profile)
        self.assertEqual(continued["result"]["allowed"], True)
        self.assertEqual(supervisor._runtime.continued, ["thread-1"])
        self.assertTrue(any("Runtime supervisor decision" in note for note in dogfood.notes))

    def test_runtime_service_blocks_start_turn_when_context_guard_requires_decision(self) -> None:
        class FakeProjects:
            def require_shell_state_root(self) -> Path:
                return Path(tempfile.mkdtemp())

        class FakeClient:
            def request(self, method, params, timeout=None):  # noqa: ANN001
                self.method = method
                self.params = params
                self.timeout = timeout
                return {"thread": {"id": params.get("threadId")}}

        runtime = RuntimeService(FakeProjects(), ModalService(FakeProjects().require_shell_state_root))
        runtime._events = [
            {
                "type": "notification",
                "method": "thread/tokenUsage/updated",
                "timestamp": "2026-06-12T00:00:01+00:00",
                "params": {
                    "threadId": "thread-hot",
                    "turnId": "turn-hot",
                    "tokenUsage": {"total": {"totalTokens": 95}, "modelContextWindow": 100},
                },
            }
        ]
        client = FakeClient()
        with self.assertRaisesRegex(RuntimeError, "Context is above 90%"):
            runtime._raise_if_context_guard_blocks_turn(client, "thread-hot")
        runtime.allow_context_guard_continue_once("thread-hot")
        runtime._raise_if_context_guard_blocks_turn(client, "thread-hot")
        with self.assertRaisesRegex(RuntimeError, "Context is above 90%"):
            runtime._raise_if_context_guard_blocks_turn(client, "thread-hot")

    def test_runtime_service_does_not_block_after_completed_compaction(self) -> None:
        class FakeProjects:
            def require_shell_state_root(self) -> Path:
                return Path(tempfile.mkdtemp())

        runtime = RuntimeService(FakeProjects(), ModalService(FakeProjects().require_shell_state_root))
        runtime._events = [
            {
                "type": "notification",
                "method": "thread/tokenUsage/updated",
                "timestamp": "2026-06-12T00:00:01+00:00",
                "params": {
                    "threadId": "thread-compact",
                    "turnId": "turn-before-compact",
                    "tokenUsage": {"total": {"totalTokens": 95}, "modelContextWindow": 100},
                },
            },
            {
                "type": "notification",
                "method": "item/completed",
                "timestamp": "2026-06-12T00:00:02+00:00",
                "params": {
                    "threadId": "thread-compact",
                    "turnId": "turn-compact",
                    "item": {"type": "contextCompaction", "id": "compact-1"},
                },
            },
        ]
        runtime._raise_if_context_guard_blocks_turn(object(), "thread-compact")

    def test_context_guard_uses_last_input_not_cumulative_thread_usage(self) -> None:
        """Codex app-server reports cumulative thread usage in total.totalTokens.

        Context guard decisions must use the latest turn input/context estimate
        instead; otherwise a compacted thread with a small health-check prompt
        still looks permanently above 90%.
        """

        class FakeProjects:
            current_project = {"current_thread_id": "thread-compact", "name": "Demo"}

            def __init__(self) -> None:
                self.workspace = Path(tempfile.mkdtemp())

            def refresh_current_project(self) -> dict[str, object]:
                return self.current_project

            def require_shell_state_root(self) -> Path:
                return self.workspace / ".astrabridge"

            def require_workspace_root(self) -> Path:
                return self.workspace

        class FakeRuntime(RuntimeService):
            def __init__(self, projects: FakeProjects, events: list[dict[str, object]]) -> None:
                super().__init__(projects, ModalService(projects.require_shell_state_root))
                self._events = events

            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {"cursor": len(self._events), "events": self._events}

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

        events: list[dict[str, object]] = [
            {
                "type": "notification",
                "method": "thread/tokenUsage/updated",
                "timestamp": "2026-06-19T13:01:46+08:00",
                "params": {
                    "threadId": "thread-compact",
                    "turnId": "turn-health",
                    "tokenUsage": {
                        "total": {"totalTokens": 2674975, "inputTokens": 2649784},
                        "last": {"totalTokens": 17020, "inputTokens": 16977, "outputTokens": 43},
                        "modelContextWindow": 800000,
                    },
                },
            }
        ]
        projects = FakeProjects()
        runtime = FakeRuntime(projects, events)

        state = runtime._context_guard_state("thread-compact")  # noqa: SLF001
        runtime._raise_if_context_guard_blocks_turn(object(), "thread-compact")  # noqa: SLF001
        supervisor = RuntimeSupervisorService(projects, runtime, FakeModals(), FakeDogfood())
        token = supervisor._latest_token_usage(events, "thread-compact")  # noqa: SLF001
        status = supervisor.status(thread_id="thread-compact", profile={"provider_id": "deepseek"})

        self.assertEqual(state["level"], "ok")
        self.assertAlmostEqual(state["context_percent"], 2.1)
        self.assertEqual(status["guard"]["level"], "ok")
        self.assertEqual(token["context_estimate_source"], "last.inputTokens")
        self.assertEqual(token["cumulative_total_tokens"], 2674975)

    def test_runtime_service_reports_running_compaction_before_hot_context_pause(self) -> None:
        class FakeProjects:
            def require_shell_state_root(self) -> Path:
                return Path(tempfile.mkdtemp())

        runtime = RuntimeService(FakeProjects(), ModalService(FakeProjects().require_shell_state_root))
        runtime._events = [
            {
                "type": "notification",
                "method": "item/started",
                "timestamp": "2026-06-12T00:00:01+00:00",
                "params": {
                    "threadId": "thread-compact",
                    "turnId": "turn-compact",
                    "item": {"type": "contextCompaction", "id": "compact-1"},
                },
            },
            {
                "type": "notification",
                "method": "thread/tokenUsage/updated",
                "timestamp": "2026-06-12T00:00:02+00:00",
                "params": {
                    "threadId": "thread-compact",
                    "turnId": "turn-compact",
                    "tokenUsage": {"total": {"totalTokens": 95}, "modelContextWindow": 100},
                },
            },
        ]

        state = runtime._context_guard_state("thread-compact")  # noqa: SLF001

        self.assertEqual(state["level"], "compacting")
        with self.assertRaisesRegex(RuntimeError, "compaction is still running"):
            runtime._raise_if_context_guard_blocks_turn(object(), "thread-compact")
        self.assertEqual(runtime.list_events()["events"][-1]["type"], "context_guard_compaction_in_progress")

    def test_context_guard_marks_missing_thread_before_blocking_hot_stale_thread(self) -> None:
        class FakeProjects:
            def require_shell_state_root(self) -> Path:
                return Path(tempfile.mkdtemp())

        class FakeClient:
            def request(self, method, params, timeout=None):  # noqa: ANN001
                raise JsonRpcError("thread not found: thread-hot")

        class FakeTasks:
            def __init__(self) -> None:
                self.missing: list[tuple[str, str | None]] = []

            def mark_provider_thread_missing(self, thread_id: str, *, reason: str | None = None) -> None:
                self.missing.append((thread_id, reason))

        runtime = RuntimeService(FakeProjects(), ModalService(FakeProjects().require_shell_state_root))
        runtime._tasks = FakeTasks()
        runtime._events = [
            {
                "type": "notification",
                "method": "thread/tokenUsage/updated",
                "timestamp": "2026-06-15T10:00:00+00:00",
                "params": {
                    "threadId": "thread-hot",
                    "turnId": "turn-old",
                    "tokenUsage": {"modelContextWindow": 100, "total": {"totalTokens": 95}},
                },
            }
        ]

        runtime._raise_if_context_guard_blocks_turn(FakeClient(), "thread-hot")

        self.assertEqual(runtime._tasks.missing, [("thread-hot", "context_guard_thread_missing")])
        self.assertTrue(
            any(
                event.get("type") == "provider_thread_missing"
                and event.get("reason") == "context_guard_thread_missing"
                for event in runtime._events
            )
        )

    def test_runtime_service_compact_returns_recoverable_thread_missing(self) -> None:
        class FakeProjects:
            def require_shell_state_root(self) -> Path:
                return Path(tempfile.mkdtemp())

        class FakeClient:
            def request(self, method, params):  # noqa: ANN001
                self.method = method
                self.params = params
                raise JsonRpcError("thread not found: thread-missing")

        class FakeTasks:
            def __init__(self) -> None:
                self.missing: list[tuple[str, str | None]] = []

            def mark_provider_thread_missing(self, thread_id: str, *, reason: str | None = None) -> None:
                self.missing.append((thread_id, reason))

        runtime = RuntimeService(FakeProjects(), ModalService(FakeProjects().require_shell_state_root))
        runtime._tasks = FakeTasks()
        runtime._prepare_runtime = lambda profile, require_secret=True: {"provider_id": profile.get("provider_id", "deepseek")}  # type: ignore[method-assign]
        runtime._ensure_client = lambda runtime_status: FakeClient()  # type: ignore[method-assign]

        result = runtime.compact_thread({"provider_id": "deepseek"}, "thread-missing")

        self.assertEqual(result["status"], "thread_missing")
        self.assertEqual(result["recommended_action"], "restart_runtime_lane")
        self.assertEqual(result["recoverability"], "recoverable")
        self.assertEqual(result["recommended_actions"][0]["action"], "restart_runtime_lane")
        self.assertTrue(result["recoverable"])
        self.assertEqual(runtime._tasks.missing, [("thread-missing", "compact_thread_not_found")])
        self.assertTrue(any(event.get("type") == "thread_compact_blocked" for event in runtime._events))

    def test_runtime_service_compact_thread_missing_reprojects_visible_fallback_thread(self) -> None:
        class FakeClient:
            def request(self, method, params):  # noqa: ANN001
                raise JsonRpcError("thread not found: thread-active")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-active",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-fallback",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-flash",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._prepare_runtime = lambda profile, require_secret=True: {"provider_id": profile.get("provider_id", "deepseek")}  # type: ignore[method-assign]
            runtime._ensure_client = lambda runtime_status: FakeClient()  # type: ignore[method-assign]

            result = runtime.compact_thread({"provider_id": "deepseek"}, "thread-active")

            self.assertEqual(result["status"], "thread_missing")
            current = tasks.current_task()
            self.assertEqual(current["active_provider_thread_id"], "thread-fallback")
            self.assertEqual(projects.current_project["current_thread_id"], "thread-fallback")
            missing = [item for item in current["provider_threads"] if item["thread_id"] == "thread-active"][0]
            self.assertEqual(missing["missing_reason"], "compact_thread_not_found")

    def test_context_guard_does_not_block_missing_provider_thread(self) -> None:
        class FakeProjects:
            def require_shell_state_root(self) -> Path:
                return Path(tempfile.mkdtemp())

        runtime = RuntimeService(FakeProjects(), ModalService(FakeProjects().require_shell_state_root))
        runtime._events = [
            {
                "type": "notification",
                "method": "thread/tokenUsage/updated",
                "timestamp": "2026-06-15T10:00:00+00:00",
                "params": {
                    "threadId": "thread-missing",
                    "turnId": "turn-old",
                    "tokenUsage": {
                        "modelContextWindow": 100,
                        "total": {"totalTokens": 95},
                    },
                },
            },
            {
                "type": "provider_thread_missing",
                "thread_id": "thread-missing",
                "reason": "compact_thread_not_found",
                "timestamp": "2026-06-15T10:01:00+00:00",
            },
        ]

        state = runtime._context_guard_state("thread-missing")  # noqa: SLF001

        self.assertEqual(state["level"], "missing")
        runtime._raise_if_context_guard_blocks_turn(object(), "thread-missing")  # noqa: SLF001

    def test_runtime_supervisor_normalizes_context_limit_and_auth_failures(self) -> None:
        class FakeProjects:
            current_project = {"ui_preferences": {}}

            def require_workspace_root(self) -> Path:
                return Path(tempfile.gettempdir())

        class FakeRuntime:
            def list_events(self, after: int = 0, limit: int | None = None) -> dict[str, object]:
                return {"cursor": 0, "events": []}

        class FakeModals:
            def list_pending(self) -> dict[str, object]:
                return {"modals": []}

        class FakeDogfood:
            def snapshot(self) -> dict[str, object]:
                return {"run": {"enabled": False, "browser_smokes": [], "milestones": [], "usage": {}, "budgets": {}}}

        supervisor = RuntimeSupervisorService(FakeProjects(), FakeRuntime(), FakeModals(), FakeDogfood())

        context_limit = supervisor._normalize_runtime_error('{"error":{"message":"context length exceeded","provider":"deepseek","model":"deepseek-v4-pro"}}')  # noqa: SLF001
        auth_failure = supervisor._normalize_runtime_error("401 unauthorized: invalid api key")  # noqa: SLF001

        self.assertEqual(context_limit["category"], "context_window_limit")
        self.assertTrue(context_limit["compact_recommended"])
        self.assertTrue(context_limit["fork_recommended"])
        self.assertEqual(context_limit["recoverability"], "recoverable")
        self.assertEqual(context_limit["recommended_action"], "compact_thread")
        self.assertEqual(context_limit["recommended_actions"][0]["action"], "compact_thread")
        self.assertTrue(context_limit["recommended_actions"][0]["transition"]["compact_before_send"])
        self.assertEqual(context_limit["recommended_actions"][2]["action"], "downgrade_reasoning")
        self.assertEqual(context_limit["recommended_actions"][2]["target"], "xhigh")
        self.assertEqual(context_limit["recommended_actions"][2]["transition"]["target"]["reasoning_policy_mode"], "reasoning_content")
        self.assertEqual(context_limit["fallback_models"], ["deepseek-v4-flash"])
        self.assertEqual(auth_failure["category"], "auth_failure")
        self.assertIn("key", auth_failure["actionable_hint"].lower())
        self.assertTrue(auth_failure["requires_key_check"])
        self.assertEqual(auth_failure["recoverability"], "requires_user_action")
        self.assertEqual(auth_failure["recommended_actions"][0]["action"], "refresh_provider_key")

    def test_runtime_failure_classifier_uses_current_profile_defaults(self) -> None:
        notice = classify_runtime_failure(
            "timeout while waiting for upstream model response",
            current_provider="qwen",
            current_model="qwen3.7-plus",
        ).to_payload()

        self.assertEqual(notice["category"], "provider_timeout")
        self.assertTrue(notice["retryable"])
        self.assertEqual(notice["recoverability"], "retryable")
        self.assertTrue(notice["provider_switch_recommended"])
        self.assertEqual(notice["fallback_models"], ["qwen3.7-max-2026-06-08", "qwen3.6-flash"])
        self.assertEqual(notice["recommended_actions"][1]["action"], "switch_model")
        self.assertEqual(notice["recommended_actions"][1]["target"], "qwen3.7-max-2026-06-08")
        self.assertEqual(notice["recommended_actions"][1]["transition"]["target"]["protocol"], "responses")
        self.assertEqual(notice["recommended_actions"][1]["transition"]["target"]["env_key"], "DASHSCOPE_API_KEY")

    def test_runtime_failure_classifier_emits_restart_transition_for_runtime_corruption(self) -> None:
        notice = classify_runtime_failure(
            '{"error":{"message":"provider thread missing","provider":"glm","model":"glm-5.2"}}'
        ).to_payload()

        self.assertEqual(notice["category"], "runtime_state_corruption")
        self.assertEqual(notice["recommended_action"], "restart_runtime_lane")
        self.assertEqual(notice["recommended_actions"][0]["action"], "restart_runtime_lane")
        self.assertTrue(notice["recommended_actions"][0]["transition"]["restart_runtime"])
        self.assertEqual(notice["recommended_actions"][0]["transition"]["target"]["base_url"], "https://open.bigmodel.cn/api/paas/v4")


if __name__ == "__main__":
    unittest.main()





