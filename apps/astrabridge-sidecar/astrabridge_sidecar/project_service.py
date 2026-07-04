from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from .common import (
    PROJECT_FILE_SUFFIX,
    PROJECT_SCHEMA_VERSION,
    WORKSPACE_STATE_DIRNAME,
    app_data_dir,
    app_runtime_dir,
    default_codex_home,
    now_iso,
    read_json,
    slugify,
    write_json,
)
from .codex_plugin_skill_project_presets import normalize_project_plugin_skill_presets
from .profile_service import ProfileService
from .model_catalog import preferred_provider_model_record
from .security import SECRET_RE, SecurityError, redact_sensitive
from .wsl_dependency_service import DEFAULT_WSL_DISTRO, ASTRABRIDGE_WSL_CODEX_HOME, ASTRABRIDGE_WSL_ROOT


DEFAULT_RUNTIME_HOST_ENV = "ASTRABRIDGE_DEFAULT_EXECUTION_HOST"
DEFAULT_RUNTIME_WSL_DISTRO_ENV = "ASTRABRIDGE_DEFAULT_WSL_DISTRO"
_DEFAULT_RUNTIME_PREFS_CACHE: dict[str, str] | None = None
_VALID_REASONING_EFFORTS = {"off", "auto", "minimal", "low", "medium", "high", "xhigh"}
MANAGED_STATE_DIRS = (
    "attachments",
    "captures",
    "downloads",
    "caches",
    "reviews",
    "tmp",
    "runtime-cwd",
)
MANAGED_STATE_FILES = (
    "runtime_events.jsonl",
    "approvals.jsonl",
    "thread_cache.json",
    "ui_state.json",
)
STORAGE_POLICY_SCHEMA_VERSION = "astrabridge-storage-policy-v1"
SIDEBAR_SCHEMA_VERSION = "astrabridge-sidebar-v1"
SIDEBAR_TASK_STATE_SCHEMA_VERSION = "astrabridge-task-state-v1"
_OPENAI_DEFAULT_MODEL = str(
    (preferred_provider_model_record("openai", include_deprecated=False) or {}).get("native_model") or "gpt-5.5"
)


class ProjectService:
    def __init__(self, store_path: Path | None = None, session_path: Path | None = None) -> None:
        self.store_path = store_path or (app_data_dir() / "projects.json")
        self.session_path = session_path or self.store_path.with_name("current_project.json")
        self._profiles = ProfileService()
        self.current_project: dict[str, Any] | None = None
        self._restore_current_project()

    def create_project(
        self,
        name: str,
        project_file: str | Path,
        workspace_root: str | Path | None = None,
        entry_mode: str = "existing",
    ) -> dict[str, Any]:
        if entry_mode not in {"existing", "new"}:
            raise ValueError("entry_mode must be existing or new.")
        requested_workspace = Path(workspace_root).expanduser().resolve() if workspace_root else None
        project_path, resolved_workspace = self._resolve_creation_paths(
            name=name,
            project_file=project_file,
            workspace_root=requested_workspace,
            entry_mode=entry_mode,
        )
        if entry_mode == "existing":
            if not resolved_workspace.exists() or not resolved_workspace.is_dir():
                raise ValueError(f"Existing workspace does not exist: {resolved_workspace}")
        else:
            resolved_workspace.mkdir(parents=True, exist_ok=True)
        self._validate_duplicate_workspace(resolved_workspace, project_path)
        project_path.parent.mkdir(parents=True, exist_ok=True)
        project_id = slugify(project_path.stem or name)
        ui_preferences = self._default_ui_preferences()
        payload = {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "project_id": project_id,
            "name": name.strip() or project_id,
            "project_file": str(project_path),
            "workspace_root": str(resolved_workspace),
            "entry_mode": entry_mode,
            "default_profile_id": "openai-compatible",
            "default_model": _OPENAI_DEFAULT_MODEL,
            "default_effort": "high",
            "current_thread_id": None,
            "recent_threads": [],
            "current_task_id": None,
            "recent_tasks": [],
            "ui_preferences": ui_preferences,
            "plugin_skill_presets": normalize_project_plugin_skill_presets(None),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        payload = self._normalize_project_runtime_defaults(payload)
        self._ensure_workspace_state(resolved_workspace, project_path=project_path, entry_mode=entry_mode)
        write_json(project_path, payload)
        self._remember_project(payload)
        self.current_project = payload
        self._remember_current_project(payload)
        return payload

    def open_project(self, project_file: str | Path) -> dict[str, Any]:
        project_path = self._normalize_existing_project_path(project_file)
        payload = read_json(project_path, {})
        schema_version = payload.get("schema_version")
        if schema_version != PROJECT_SCHEMA_VERSION:
            raise ValueError("Unsupported or missing .abproj schema_version.")
        workspace_root = Path(str(payload.get("workspace_root") or "")).expanduser().resolve()
        if not workspace_root.exists() or not workspace_root.is_dir():
            raise ValueError(f"Workspace root does not exist: {workspace_root}")
        self._validate_duplicate_workspace(workspace_root, project_path, allow_existing=True)
        payload["project_file"] = str(project_path)
        payload["workspace_root"] = str(workspace_root)
        missing_task_fields = "current_task_id" not in payload or "recent_tasks" not in payload
        payload.setdefault("recent_threads", [])
        payload.setdefault("current_task_id", None)
        payload.setdefault("recent_tasks", [])
        before_presets = deepcopy(payload.get("plugin_skill_presets"))
        payload["plugin_skill_presets"] = normalize_project_plugin_skill_presets(payload.get("plugin_skill_presets"))
        before_runtime = {
            "default_profile_id": payload.get("default_profile_id"),
            "default_model": payload.get("default_model"),
            "default_effort": payload.get("default_effort"),
        }
        payload = self._normalize_project_runtime_defaults(payload)
        before_preferences = dict(payload.get("ui_preferences") or {})
        payload["ui_preferences"] = self._normalize_ui_preferences(before_preferences)
        self._ensure_workspace_state(
            workspace_root,
            project_path=project_path,
            entry_mode=str(payload.get("entry_mode") or "existing"),
        )
        runtime_changed = before_runtime != {
            "default_profile_id": payload.get("default_profile_id"),
            "default_model": payload.get("default_model"),
            "default_effort": payload.get("default_effort"),
        }
        if payload["ui_preferences"] != before_preferences or missing_task_fields or runtime_changed or payload["plugin_skill_presets"] != before_presets:
            payload["updated_at"] = now_iso()
            write_json(project_path, payload)
        self._remember_project(payload)
        self.current_project = payload
        self._remember_current_project(payload)
        return payload

    def close_project(self) -> dict[str, Any]:
        self.current_project = None
        write_json(
            self.session_path,
            {
                "project_file": "",
                "closed": True,
                "updated_at": now_iso(),
            },
        )
        return {"closed": True}

    def refresh_current_project(self) -> dict[str, Any] | None:
        if not self.current_project:
            return None
        project_file = str(self.current_project.get("project_file") or "").strip()
        if not project_file:
            return self.current_project
        path = Path(project_file).expanduser()
        if not path.exists():
            return self.current_project
        payload = read_json(path, {})
        if not isinstance(payload, dict) or not payload:
            return self.current_project
        before_runtime = {
            "default_profile_id": payload.get("default_profile_id"),
            "default_model": payload.get("default_model"),
            "default_effort": payload.get("default_effort"),
        }
        before_preferences = dict(payload.get("ui_preferences") or {})
        before_presets = deepcopy(payload.get("plugin_skill_presets"))
        payload.setdefault("recent_threads", [])
        payload.setdefault("current_task_id", None)
        payload.setdefault("recent_tasks", [])
        payload["plugin_skill_presets"] = normalize_project_plugin_skill_presets(payload.get("plugin_skill_presets"))
        payload = self._normalize_project_runtime_defaults(payload)
        payload["ui_preferences"] = self._normalize_ui_preferences(before_preferences)
        runtime_changed = before_runtime != {
            "default_profile_id": payload.get("default_profile_id"),
            "default_model": payload.get("default_model"),
            "default_effort": payload.get("default_effort"),
        }
        if runtime_changed or payload["ui_preferences"] != before_preferences or payload["plugin_skill_presets"] != before_presets:
            payload["updated_at"] = now_iso()
            write_json(path, payload)
        self.current_project = payload
        return self.current_project

    def reconcile_task_projection(self, task: dict[str, Any] | None) -> dict[str, Any] | None:
        """Keep the project-level task/thread pointers aligned with live task state.

        The UI and several sidecar routes still read project.current_thread_id as the
        default thread focus. Make the projection explicit so a stale project snapshot
        cannot drift away from the real active provider thread for the visible task.
        """
        project = self.refresh_current_project()
        if not project or not task:
            return project
        task_id = str(task.get("task_id") or "").strip() or None
        active_thread = str(task.get("active_provider_thread_id") or "").strip() or None
        recent_tasks = [
            item
            for item in list(project.get("recent_tasks") or [])
            if isinstance(item, str) and item != task_id
        ]
        if task_id:
            recent_tasks.insert(0, task_id)
        recent_threads = [
            item
            for item in list(project.get("recent_threads") or [])
            if isinstance(item, str) and item != active_thread
        ]
        if active_thread:
            recent_threads.insert(0, active_thread)
        patch = {
            "current_task_id": task_id,
            "recent_tasks": recent_tasks[:50],
            "current_thread_id": active_thread,
            "recent_threads": recent_threads[:20],
        }
        needs_update = any(project.get(key) != value for key, value in patch.items())
        if needs_update:
            return self.update_project(patch)
        return project

    def list_recent(self) -> dict[str, Any]:
        payload = read_json(self.store_path, {"projects": []})
        projects = []
        for item in payload.get("projects") or []:
            project_file = Path(str(item.get("project_file") or "")).expanduser()
            if project_file.exists():
                projects.append(item)
        if projects != payload.get("projects"):
            payload["projects"] = projects
            write_json(self.store_path, payload)
        return payload

    def sidebar_snapshot(self, *, project_limit: int = 20, task_limit: int = 30, thread_limit: int = 20) -> dict[str, Any]:
        """Return a compact recent-project tree without switching projects.

        This intentionally reads recent project files and their workspace-local
        task state directly. It must not call open_project or mutate the active
        runtime because the left sidebar is a navigation preview.
        """
        current_file = str((self.current_project or {}).get("project_file") or "")
        recent_items = list(self.list_recent().get("projects") or [])
        project_nodes: list[dict[str, Any]] = []
        seen_files: set[str] = set()

        if self.current_project:
            current_node = self._sidebar_project_node(
                dict(self.current_project),
                current_file=current_file,
                task_limit=task_limit,
                thread_limit=thread_limit,
            )
            project_nodes.append(current_node)
            seen_files.add(str(current_node.get("project_file") or ""))

        for item in recent_items:
            if len(project_nodes) >= project_limit:
                break
            project_file = str((item or {}).get("project_file") or "").strip()
            if not project_file or project_file in seen_files:
                continue
            node = self._sidebar_project_node_from_recent(
                item,
                current_file=current_file,
                task_limit=task_limit,
                thread_limit=thread_limit,
            )
            if node is None:
                continue
            project_nodes.append(node)
            seen_files.add(str(node.get("project_file") or ""))

        return {
            "schema_version": SIDEBAR_SCHEMA_VERSION,
            "projects": project_nodes,
            "updated_at": now_iso(),
        }

    def require_workspace_root(self) -> Path:
        if not self.current_project:
            raise ValueError("No project is open.")
        return Path(str(self.current_project["workspace_root"])).resolve()

    def require_shell_state_root(self) -> Path:
        return self.require_workspace_root() / WORKSPACE_STATE_DIRNAME

    def require_shell_subdir(self, *parts: str) -> Path:
        path = self.require_shell_state_root().joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def require_managed_state_dir(self, name: str, *parts: str) -> Path:
        normalized = str(name or "").strip().lower()
        if normalized not in MANAGED_STATE_DIRS:
            raise ValueError(f"Unsupported managed AstraBridge state directory: {name}")
        return self.require_shell_subdir(normalized, *parts)

    def current_runtime_roots(self) -> dict[str, Path]:
        project = self.current_project or {}
        project_file = str(project.get("project_file") or "").strip()
        workspace_root = str(project.get("workspace_root") or "").strip()
        if not project_file or not workspace_root:
            fallback = default_codex_home().resolve()
            runtime_root = fallback.parent.resolve()
            return {
                "project_runtime_root": runtime_root,
                "codex_home_root": fallback,
                "downloads_root": (runtime_root / "downloads").resolve(),
                "caches_root": (runtime_root / "caches").resolve(),
                "tmp_root": (runtime_root / "tmp").resolve(),
            }
        return self._runtime_roots_for_project(
            Path(project_file).expanduser().resolve(),
            Path(workspace_root).expanduser().resolve(),
        )

    def current_runtime_codex_home(self) -> Path:
        return self.current_runtime_roots()["codex_home_root"]

    def update_project(self, patch: dict[str, Any]) -> dict[str, Any]:
        if not self.current_project:
            raise ValueError("No project is open.")
        for key in {"schema_version", "project_file", "workspace_root"}:
            patch.pop(key, None)
        runtime_keys = {"default_profile_id", "default_model", "default_effort"}
        if "ui_preferences" in patch:
            patch["ui_preferences"] = self._normalize_ui_preferences(dict(patch.get("ui_preferences") or {}))
        if "plugin_skill_presets" in patch:
            patch["plugin_skill_presets"] = normalize_project_plugin_skill_presets(patch.get("plugin_skill_presets"))
        self.current_project.update(patch)
        if runtime_keys.intersection(patch.keys()):
            self.current_project = self._normalize_project_runtime_defaults(self.current_project)
        self.current_project["updated_at"] = now_iso()
        path = Path(str(self.current_project["project_file"]))
        write_json(path, self.current_project)
        self._remember_project(self.current_project)
        return self.current_project

    def update_project_title(self, title: str) -> dict[str, Any]:
        clean_title = str(title or "").strip()
        if not clean_title:
            raise ValueError("Project title cannot be empty.")
        redacted_title = str(redact_sensitive(clean_title)).strip()
        if SECRET_RE.search(redacted_title):
            raise SecurityError("Secret-like content is not allowed in project titles.")
        return self.update_project({"name": redacted_title[:160]})

    def switch_thread(self, thread_id: str | None) -> dict[str, Any]:
        if not self.current_project:
            raise ValueError("No project is open.")
        thread_ids = [item for item in self.current_project.get("recent_threads", []) if isinstance(item, str) and item != thread_id]
        if thread_id:
            thread_ids.insert(0, thread_id)
        return self.update_project({"current_thread_id": thread_id, "recent_threads": thread_ids[:20]})

    def cache_threads(self, threads: list[dict[str, Any]]) -> None:
        cache_path = self.require_shell_state_root() / "thread_cache.json"
        existing = read_json(cache_path, {})
        by_id = dict(existing.get("by_id") or {})
        for thread in threads:
            thread_id = str(thread.get("id") or thread.get("thread_id") or "")
            if not thread_id:
                continue
            current = dict(by_id.get(thread_id) or {})
            status = thread.get("status")
            by_id[thread_id] = {
                **current,
                "thread_id": thread_id,
                "name": thread.get("name") or thread.get("displayName") or current.get("name"),
                "status": dict(status) if isinstance(status, dict) else current.get("status"),
                "updated_at": now_iso(),
            }
        write_json(
            cache_path,
            {
                **existing,
                "updated_at": now_iso(),
                "threads": threads,
                "by_id": by_id,
            },
        )

    def _remember_project(self, project: dict[str, Any]) -> None:
        payload = self.list_recent()
        projects = [item for item in payload.get("projects") or [] if item.get("project_file") != project.get("project_file")]
        projects.insert(
            0,
            {
                "project_id": project.get("project_id"),
                "name": project.get("name"),
                "project_file": project.get("project_file"),
                "workspace_root": project.get("workspace_root"),
                "entry_mode": project.get("entry_mode"),
                "updated_at": now_iso(),
            },
        )
        payload["projects"] = projects[:20]
        write_json(self.store_path, payload)

    def _sidebar_project_node_from_recent(
        self,
        item: dict[str, Any],
        *,
        current_file: str,
        task_limit: int,
        thread_limit: int,
    ) -> dict[str, Any] | None:
        project_file = str((item or {}).get("project_file") or "").strip()
        if not project_file:
            return None
        project_path = Path(project_file).expanduser()
        if not project_path.exists():
            return None
        warnings: list[str] = []
        try:
            project = read_json(project_path, {})
        except Exception as exc:
            project = dict(item)
            warnings.append(f"project_read_failed: {type(exc).__name__}")
        if not isinstance(project, dict):
            project = dict(item)
            warnings.append("project_read_failed: invalid_payload")
        if str(project.get("schema_version") or "") != PROJECT_SCHEMA_VERSION:
            project = {**dict(item), **{key: project.get(key) for key in ("project_id", "name", "workspace_root", "updated_at") if isinstance(project, dict)}}
            warnings.append("project_schema_unsupported")
        project.setdefault("project_file", project_file)
        if warnings:
            project["_sidebar_warnings"] = warnings
        return self._sidebar_project_node(project, current_file=current_file, task_limit=task_limit, thread_limit=thread_limit)

    def _sidebar_project_node(
        self,
        project: dict[str, Any],
        *,
        current_file: str,
        task_limit: int,
        thread_limit: int,
    ) -> dict[str, Any]:
        project_file = str(project.get("project_file") or "")
        workspace_root = str(project.get("workspace_root") or "")
        current_task_id = str(project.get("current_task_id") or "")
        task_state, warnings = self._sidebar_task_state(project)
        tasks = [
            self._sidebar_task_node(task, project=project, current_task_id=current_task_id, thread_limit=thread_limit)
            for task in list(task_state.get("tasks") or [])[:task_limit]
            if isinstance(task, dict)
        ]
        return {
            "project_id": str(project.get("project_id") or ""),
            "name": str(redact_sensitive(project.get("name") or Path(project_file).stem or "Project"))[:160],
            "project_file": project_file,
            "workspace_root": workspace_root,
            "updated_at": str(project.get("updated_at") or task_state.get("updated_at") or ""),
            "is_current": bool(project_file and current_file and project_file == current_file),
            "tasks": tasks,
            "warnings": [*list(project.get("_sidebar_warnings") or []), *warnings],
        }

    def _sidebar_task_state(self, project: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        workspace_root = str(project.get("workspace_root") or "").strip()
        if not workspace_root:
            return {"schema_version": SIDEBAR_TASK_STATE_SCHEMA_VERSION, "tasks": []}, ["missing_workspace_root"]
        task_path = Path(workspace_root).expanduser() / WORKSPACE_STATE_DIRNAME / "tasks.json"
        try:
            state = read_json(task_path, {"schema_version": SIDEBAR_TASK_STATE_SCHEMA_VERSION, "current_task_id": None, "tasks": []})
        except Exception as exc:
            return {"schema_version": SIDEBAR_TASK_STATE_SCHEMA_VERSION, "tasks": []}, [f"task_state_read_failed: {type(exc).__name__}"]
        if not isinstance(state, dict):
            return {"schema_version": SIDEBAR_TASK_STATE_SCHEMA_VERSION, "tasks": []}, ["task_state_invalid"]
        tasks = state.get("tasks")
        if not isinstance(tasks, list):
            state["tasks"] = []
            warnings.append("task_state_tasks_invalid")
        return state, warnings

    def _sidebar_task_node(self, task: dict[str, Any], *, project: dict[str, Any], current_task_id: str, thread_limit: int) -> dict[str, Any]:
        active_thread_id = str(task.get("active_provider_thread_id") or "")
        provider_threads = [dict(item) for item in list(task.get("provider_threads") or []) if isinstance(item, dict)]
        fork_threads = [dict(item) for item in list(task.get("fork_threads") or []) if isinstance(item, dict)]
        thread_nodes = self._sidebar_thread_nodes(provider_threads, fork_threads, active_thread_id=active_thread_id, limit=thread_limit)
        active_lane = self._sidebar_active_lane([*provider_threads, *fork_threads], active_thread_id=active_thread_id)
        missing_count = len([item for item in provider_threads if item.get("missing_at")])
        return {
            "task_id": str(task.get("task_id") or ""),
            "title": str(redact_sensitive(task.get("title") or "New task"))[:160],
            "status": str(task.get("status") or ""),
            "updated_at": str(task.get("updated_at") or task.get("created_at") or ""),
            "is_current": bool(current_task_id and str(task.get("task_id") or "") == current_task_id),
            "active_provider_thread_id": active_thread_id or None,
            "threads": thread_nodes,
            "provider_id": str((provider_threads[0] if provider_threads else {}).get("provider_id") or ""),
            "model": str((provider_threads[0] if provider_threads else {}).get("model") or ""),
            "reasoning_effort": str((provider_threads[0] if provider_threads else {}).get("reasoning_effort") or ""),
            "thread_count": len(thread_nodes),
            "lane_count": len(thread_nodes),
            "active_lane_label": self._sidebar_thread_title(active_lane) if active_lane else "",
            "latest_lane_status": self._sidebar_lane_status(active_lane),
            "handoff_count": len(list(task.get("handoff_events") or [])),
            "checkpoint_count": len(list(task.get("checkpoint_refs") or [])),
            "missing_thread_count": missing_count,
            "project_file": str(project.get("project_file") or ""),
        }

    def _sidebar_active_lane(self, lanes: list[dict[str, Any]], *, active_thread_id: str) -> dict[str, Any]:
        clean_active = str(active_thread_id or "").strip()
        if clean_active:
            for item in lanes:
                if str(item.get("thread_id") or "").strip() == clean_active:
                    return dict(item)
        live_lanes = [dict(item) for item in lanes if not item.get("missing_at")]
        if live_lanes:
            live_lanes.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return live_lanes[0]
        return dict(lanes[0]) if lanes else {}

    def _sidebar_lane_status(self, lane: dict[str, Any]) -> str:
        status = lane.get("status")
        if isinstance(status, dict):
            return str(status.get("type") or status.get("status") or "").strip()[:80]
        return str(status or "").strip()[:80]

    def _sidebar_thread_nodes(
        self,
        provider_threads: list[dict[str, Any]],
        fork_threads: list[dict[str, Any]],
        *,
        active_thread_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*provider_threads, *fork_threads]:
            thread_id = str(item.get("thread_id") or "").strip()
            if not thread_id or thread_id in seen:
                continue
            seen.add(thread_id)
            nodes.append(
                {
                    "thread_id": thread_id,
                    "title": self._sidebar_thread_title(item),
                    "role": str(item.get("role") or "provider"),
                    "profile_id": str(item.get("profile_id") or ""),
                    "provider_id": str(item.get("provider_id") or ""),
                    "model": str(item.get("model") or ""),
                    "reasoning_effort": str(item.get("reasoning_effort") or ""),
                    "updated_at": str(item.get("updated_at") or item.get("created_at") or ""),
                    "created_at": str(item.get("created_at") or ""),
                    "missing_at": str(item.get("missing_at") or "") or None,
                    "missing_reason": str(item.get("missing_reason") or "") or None,
                    "is_active": bool(active_thread_id and thread_id == active_thread_id),
                }
            )
            if len(nodes) >= limit:
                break
        return nodes

    def _sidebar_thread_title(self, item: dict[str, Any]) -> str:
        name = str(item.get("name") or "").strip()
        if name:
            return str(redact_sensitive(name))[:160]
        provider = str(item.get("provider_id") or item.get("profile_id") or "").strip()
        model = str(item.get("model") or "").strip()
        if provider and model:
            return f"{provider} / {model}"
        if model:
            return model
        return str(item.get("thread_id") or "Thread")

    def _remember_current_project(self, project: dict[str, Any] | None) -> None:
        payload = {
            "project_file": str((project or {}).get("project_file") or ""),
            "closed": False,
            "updated_at": now_iso(),
        }
        write_json(self.session_path, payload)

    def _restore_current_project(self) -> None:
        session_exists = self.session_path.exists()
        payload = read_json(self.session_path, {})
        project_file = str(payload.get("project_file") or "").strip()
        session_closed = bool(payload.get("closed")) and not project_file
        if session_closed:
            self.current_project = None
            return
        candidates: list[str] = []
        if project_file:
            candidates.append(project_file)
        recent = self.list_recent().get("projects") or []
        for item in recent:
            candidate = str((item or {}).get("project_file") or "").strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        for candidate in candidates:
            try:
                self.open_project(candidate)
                return
            except Exception:
                continue
        self.current_project = None
        if project_file and not Path(project_file).expanduser().exists():
            self._remember_current_project(None)

    def _validate_duplicate_workspace(self, workspace_root: Path, project_file: Path, allow_existing: bool = False) -> None:
        recent = self.list_recent().get("projects") or []
        for item in recent:
            item_root = Path(str(item.get("workspace_root") or "")).expanduser()
            item_file = Path(str(item.get("project_file") or "")).expanduser()
            if item_root.resolve() == workspace_root.resolve() and item_file.resolve() != project_file.resolve():
                raise ValueError(
                    f"Workspace is already attached to another .abproj: {item_file}"
                )
        if allow_existing:
            return
        if project_file.exists():
            raise ValueError(f"Project file already exists: {project_file}")

    def _ensure_workspace_state(self, workspace_root: Path, *, project_path: Path | None = None, entry_mode: str | None = None) -> None:
        shell_root = workspace_root / WORKSPACE_STATE_DIRNAME
        for dirname in MANAGED_STATE_DIRS:
            path = shell_root / dirname
            path.mkdir(parents=True, exist_ok=True)
        if project_path is not None:
            for runtime_root in self._runtime_roots_for_project(project_path.resolve(), workspace_root.resolve()).values():
                runtime_root.mkdir(parents=True, exist_ok=True)
        for filename in MANAGED_STATE_FILES:
            path = shell_root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".json":
                if not path.exists():
                    write_json(path, {})
            else:
                path.touch(exist_ok=True)
        self._write_storage_policy(
            workspace_root,
            project_path=project_path,
            entry_mode=entry_mode,
        )
        self._ensure_git_exclude(workspace_root)

    def _write_storage_policy(
        self,
        workspace_root: Path,
        *,
        project_path: Path | None = None,
        entry_mode: str | None = None,
    ) -> None:
        shell_root = workspace_root / WORKSPACE_STATE_DIRNAME
        policy_path = shell_root / "storage_policy.json"
        runtime_roots = self._runtime_roots_for_project(
            (project_path or Path(str((self.current_project or {}).get("project_file") or "")).expanduser()).resolve(),
            workspace_root.resolve(),
        )
        payload = {
            "schema_version": STORAGE_POLICY_SCHEMA_VERSION,
            "workspace_root": str(workspace_root.resolve()),
            "state_root": str(shell_root.resolve()),
            "project_file": str(project_path.resolve()) if project_path else str((self.current_project or {}).get("project_file") or ""),
            "entry_mode": str(entry_mode or (self.current_project or {}).get("entry_mode") or ""),
            "managed_dirs": {
                dirname: str((shell_root / dirname).resolve())
                for dirname in MANAGED_STATE_DIRS
            },
            "managed_files": {
                filename: str((shell_root / filename).resolve())
                for filename in MANAGED_STATE_FILES
            },
            "runtime": {
                "app_data_root": str(app_data_dir()),
                "project_runtime_root": str(runtime_roots["project_runtime_root"]),
                "codex_home_root": str(runtime_roots["codex_home_root"]),
                "downloads_root": str(runtime_roots["downloads_root"]),
                "caches_root": str(runtime_roots["caches_root"]),
                "tmp_root": str(runtime_roots["tmp_root"]),
            },
            "updated_at": now_iso(),
        }
        write_json(policy_path, payload)

    def _resolve_creation_paths(
        self,
        *,
        name: str,
        project_file: str | Path,
        workspace_root: Path | None,
        entry_mode: str,
    ) -> tuple[Path, Path]:
        clean_project = str(project_file or "").strip()
        if clean_project:
            project_path = self._normalize_project_path(clean_project)
            if workspace_root is not None:
                return project_path, workspace_root
            if entry_mode == "new":
                return project_path, project_path.parent / "workspace"
            return project_path, project_path.with_suffix("")
        if entry_mode != "new":
            raise ValueError("project_file is required for existing-workspace projects.")
        if workspace_root is not None:
            project_path = self._unique_project_path(workspace_root.parent, slugify(name or workspace_root.name or "astrabridge-project"))
            return project_path, workspace_root
        isolated_root, project_path = self._unique_isolated_project_bundle(slugify(name or "astrabridge-project"))
        return project_path, isolated_root / "workspace"

    def _unique_project_path(self, base_dir: Path, slug: str) -> Path:
        candidate_dir = base_dir.expanduser().resolve()
        candidate_dir.mkdir(parents=True, exist_ok=True)
        for index in range(1, 200):
            suffix = "" if index == 1 else f"-{index}"
            candidate = candidate_dir / f"{slug}{suffix}{PROJECT_FILE_SUFFIX}"
            if not candidate.exists():
                return candidate
        raise ValueError(f"Could not allocate a unique AstraBridge project file under {candidate_dir}")

    def _unique_isolated_project_bundle(self, slug: str) -> tuple[Path, Path]:
        projects_root = app_runtime_dir("projects")
        for index in range(1, 200):
            suffix = "" if index == 1 else f"-{index}"
            bundle_root = (projects_root / f"{slug}{suffix}").resolve()
            project_path = bundle_root / f"{slug}{suffix}{PROJECT_FILE_SUFFIX}"
            workspace_root = bundle_root / "workspace"
            if bundle_root.exists() or project_path.exists() or workspace_root.exists():
                continue
            return bundle_root, project_path
        raise ValueError(f"Could not allocate an isolated AstraBridge project root under {projects_root}")

    def _runtime_roots_for_project(self, project_path: Path, workspace_root: Path) -> dict[str, Path]:
        project_path = project_path.expanduser().resolve()
        workspace_root = workspace_root.expanduser().resolve()
        slug = slugify(project_path.stem or workspace_root.name or "astrabridge-project")
        digest = hashlib.sha256(str(project_path).encode("utf-8")).hexdigest()[:12]
        runtime_root = app_runtime_dir("project_runtime", f"{slug}-{digest}")
        return {
            "project_runtime_root": runtime_root.resolve(),
            "codex_home_root": (runtime_root / "codex_home").resolve(),
            "downloads_root": (runtime_root / "downloads").resolve(),
            "caches_root": (runtime_root / "caches").resolve(),
            "tmp_root": (runtime_root / "tmp").resolve(),
        }

    def _ensure_git_exclude(self, workspace_root: Path) -> None:
        repo_root = self._git_repo_root_for_workspace(workspace_root)
        if repo_root is None:
            return
        git_root = repo_root / ".git"
        if not git_root.exists() or not git_root.is_dir():
            return
        exclude_file = git_root / "info" / "exclude"
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude_file.read_text(encoding="utf-8") if exclude_file.exists() else ""
        additions = []
        pattern = self._git_exclude_pattern(repo_root, workspace_root)
        if pattern and pattern not in existing:
            additions.append(pattern)
        if additions:
            suffix = "\n".join(additions) + "\n"
            exclude_file.write_text(existing.rstrip() + ("\n" if existing and not existing.endswith("\n") else "") + suffix, encoding="utf-8")

    def _git_repo_root_for_workspace(self, workspace_root: Path) -> Path | None:
        try:
            completed = subprocess.run(
                ["git", "-C", str(workspace_root), "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=5,
            )
        except Exception:
            return None
        if completed.returncode != 0:
            return None
        candidate = str(completed.stdout or "").strip()
        if not candidate:
            return None
        try:
            return Path(candidate).expanduser().resolve()
        except OSError:
            return None

    def _git_exclude_pattern(self, repo_root: Path, workspace_root: Path) -> str:
        try:
            relative_workspace = workspace_root.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return f"{WORKSPACE_STATE_DIRNAME}/"
        if not relative_workspace or relative_workspace == ".":
            return f"{WORKSPACE_STATE_DIRNAME}/"
        return f"{relative_workspace}/{WORKSPACE_STATE_DIRNAME}/"

    def _default_ui_preferences(self) -> dict[str, Any]:
        runtime = self._default_runtime_preferences()
        return {
            "locale": "zh-CN",
            "appearance": "codex",
            "cursor_enhancement": "auto",
            "execution_host": runtime["execution_host"],
            "wsl_distro": runtime["wsl_distro"],
            "left_sidebar_open": True,
            "left_sidebar_width": 288,
            "right_sidebar_width": 328,
            "right_sidebar_open": True,
        }

    def _normalize_ui_preferences(self, preferences: dict[str, Any]) -> dict[str, Any]:
        defaults = self._default_ui_preferences()
        merged = {**defaults, **preferences}
        cursor_enhancement = str(merged.get("cursor_enhancement") or defaults["cursor_enhancement"]).strip().lower()
        if cursor_enhancement not in {"auto", "off"}:
            cursor_enhancement = defaults["cursor_enhancement"]
        merged["cursor_enhancement"] = cursor_enhancement
        host = str(merged.get("execution_host") or "").strip().lower()
        if host not in {"windows", "wsl"}:
            host = defaults["execution_host"]
        merged["execution_host"] = host
        if host == "wsl":
            merged["wsl_distro"] = str(merged.get("wsl_distro") or defaults["wsl_distro"] or DEFAULT_WSL_DISTRO)
        else:
            merged["wsl_distro"] = str(merged.get("wsl_distro") or "")
        return merged

    def _normalize_project_runtime_defaults(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = dict(payload)
        requested_profile = str(merged.get("default_profile_id") or "").strip()
        profile = self._resolve_default_profile(requested_profile)
        provider_id = str(profile.get("provider_id") or "openai").strip() or "openai"
        default_profile_id = str(profile.get("profile_id") or requested_profile or "openai-compatible").strip()
        requested_model = self._normalize_native_model(merged.get("default_model"), provider_id)
        profile_model = self._normalize_native_model(profile.get("model"), provider_id)
        if not requested_model or self._model_provider_mismatch(requested_model, provider_id):
            requested_model = profile_model
        requested_effort = self._normalize_reasoning_effort(merged.get("default_effort"))
        profile_effort = self._normalize_reasoning_effort(profile.get("reasoning_effort"))
        merged["default_profile_id"] = default_profile_id
        merged["default_model"] = requested_model or profile_model or self._default_provider_model(provider_id)
        merged["default_effort"] = requested_effort or profile_effort or "high"
        return merged

    def _resolve_default_profile(self, requested_profile: str) -> dict[str, Any]:
        fallback_profile_id = "openai-compatible"
        try:
            return self._profiles.resolve_runtime_profile(requested_profile or fallback_profile_id)
        except Exception:
            try:
                return self._profiles.resolve_runtime_profile(fallback_profile_id)
            except Exception:
                return {
                    "profile_id": fallback_profile_id,
                    "provider_id": "openai",
                    "model": _OPENAI_DEFAULT_MODEL,
                    "reasoning_effort": "high",
                }

    @staticmethod
    def _default_provider_model(provider_id: str) -> str:
        provider = str(provider_id or "openai").strip() or "openai"
        preferred_model = (preferred_provider_model_record(provider, include_deprecated=False) or {}).get("native_model")
        return str(preferred_model or _OPENAI_DEFAULT_MODEL).strip() or _OPENAI_DEFAULT_MODEL

    def _normalize_native_model(self, value: Any, provider_id: str) -> str:
        model = str(value or "").strip()
        if not model:
            return ""
        if "/" not in model:
            return model
        model_provider, native_model = model.split("/", 1)
        if model_provider.strip().lower() == provider_id.strip().lower() and native_model.strip():
            return native_model.strip()
        return model

    def _model_provider_mismatch(self, model: str, provider_id: str) -> bool:
        if "/" not in model:
            return False
        model_provider, _native_model = model.split("/", 1)
        return model_provider.strip().lower() != provider_id.strip().lower()

    def _normalize_reasoning_effort(self, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        if normalized == "max":
            return "xhigh"
        if normalized in _VALID_REASONING_EFFORTS:
            return normalized
        return ""

    def _default_runtime_preferences(self) -> dict[str, str]:
        forced_host = os.environ.get(DEFAULT_RUNTIME_HOST_ENV, "").strip().lower()
        forced_distro = os.environ.get(DEFAULT_RUNTIME_WSL_DISTRO_ENV, "").strip() or DEFAULT_WSL_DISTRO
        if forced_host == "wsl":
            return {"execution_host": "wsl", "wsl_distro": forced_distro}
        if forced_host == "windows":
            return {"execution_host": "windows", "wsl_distro": ""}

        global _DEFAULT_RUNTIME_PREFS_CACHE
        if _DEFAULT_RUNTIME_PREFS_CACHE is None:
            if self._astrabridge_wsl_quick_ready(forced_distro):
                _DEFAULT_RUNTIME_PREFS_CACHE = {"execution_host": "wsl", "wsl_distro": forced_distro}
            else:
                _DEFAULT_RUNTIME_PREFS_CACHE = {"execution_host": "windows", "wsl_distro": ""}
        return dict(_DEFAULT_RUNTIME_PREFS_CACHE)

    def _astrabridge_wsl_quick_ready(self, distro: str) -> bool:
        wsl_executable = shutil.which("wsl.exe") or shutil.which("wsl")
        if not wsl_executable:
            return False
        command = (
            f'export CODEX_HOME="{ASTRABRIDGE_WSL_CODEX_HOME}"; '
            f'export PATH="{ASTRABRIDGE_WSL_ROOT}/bin:$PATH"; '
            "command -v codex >/dev/null 2>&1 && codex --version >/dev/null 2>&1"
        )
        try:
            completed = subprocess.run(
                [wsl_executable, "-d", distro, "bash", "-lc", command],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=6,
            )
        except Exception:
            return False
        return completed.returncode == 0

    def _normalize_project_path(self, project_file: str | Path) -> Path:
        path = Path(project_file).expanduser().resolve()
        if path.suffix.lower() != PROJECT_FILE_SUFFIX:
            raise ValueError("AstraBridge projects must use the .abproj suffix.")
        return path

    def _normalize_existing_project_path(self, project_file: str | Path) -> Path:
        requested = Path(project_file).expanduser().resolve()
        if requested.suffix.lower() != PROJECT_FILE_SUFFIX:
            raise ValueError("AstraBridge projects must use the .abproj suffix.")
        return requested

