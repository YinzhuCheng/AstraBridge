from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .common import (
    PROJECT_FILE_SUFFIX,
    PROJECT_SCHEMA_VERSION,
    WORKSPACE_STATE_DIRNAME,
    app_data_dir,
    now_iso,
    read_json,
    slugify,
    write_json,
)
from .wsl_dependency_service import DEFAULT_WSL_DISTRO, ASTRABRIDGE_WSL_CODEX_HOME, ASTRABRIDGE_WSL_ROOT


DEFAULT_RUNTIME_HOST_ENV = "ASTRABRIDGE_DEFAULT_EXECUTION_HOST"
DEFAULT_RUNTIME_WSL_DISTRO_ENV = "ASTRABRIDGE_DEFAULT_WSL_DISTRO"
_DEFAULT_RUNTIME_PREFS_CACHE: dict[str, str] | None = None


class ProjectService:
    def __init__(self, store_path: Path | None = None, session_path: Path | None = None) -> None:
        self.store_path = store_path or (app_data_dir() / "projects.json")
        self.session_path = session_path or self.store_path.with_name("current_project.json")
        self.current_project: dict[str, Any] | None = None
        self._restore_current_project()

    def create_project(
        self,
        name: str,
        project_file: str | Path,
        workspace_root: str | Path | None = None,
        entry_mode: str = "existing",
    ) -> dict[str, Any]:
        project_path = self._normalize_project_path(project_file)
        if entry_mode not in {"existing", "new"}:
            raise ValueError("entry_mode must be existing or new.")
        resolved_workspace = Path(workspace_root).expanduser().resolve() if workspace_root else project_path.with_suffix("")
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
            "default_profile_id": "yunwu-gpt-55-xhigh",
            "default_model": "gpt-5.5",
            "default_effort": "xhigh",
            "current_thread_id": None,
            "recent_threads": [],
            "current_task_id": None,
            "recent_tasks": [],
            "ui_preferences": ui_preferences,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self._ensure_workspace_state(resolved_workspace)
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
        before_preferences = dict(payload.get("ui_preferences") or {})
        payload["ui_preferences"] = self._normalize_ui_preferences(before_preferences)
        self._ensure_workspace_state(workspace_root)
        if payload["ui_preferences"] != before_preferences or missing_task_fields:
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
        payload.setdefault("recent_threads", [])
        payload.setdefault("current_task_id", None)
        payload.setdefault("recent_tasks", [])
        payload["ui_preferences"] = self._normalize_ui_preferences(dict(payload.get("ui_preferences") or {}))
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

    def require_workspace_root(self) -> Path:
        if not self.current_project:
            raise ValueError("No project is open.")
        return Path(str(self.current_project["workspace_root"])).resolve()

    def require_shell_state_root(self) -> Path:
        return self.require_workspace_root() / WORKSPACE_STATE_DIRNAME

    def update_project(self, patch: dict[str, Any]) -> dict[str, Any]:
        if not self.current_project:
            raise ValueError("No project is open.")
        for key in {"schema_version", "project_file", "workspace_root"}:
            patch.pop(key, None)
        if "ui_preferences" in patch:
            patch["ui_preferences"] = self._normalize_ui_preferences(dict(patch.get("ui_preferences") or {}))
        self.current_project.update(patch)
        self.current_project["updated_at"] = now_iso()
        path = Path(str(self.current_project["project_file"]))
        write_json(path, self.current_project)
        self._remember_project(self.current_project)
        return self.current_project

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
            by_id[thread_id] = {
                **current,
                "thread_id": thread_id,
                "name": thread.get("name") or thread.get("displayName") or current.get("name"),
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

    def _ensure_workspace_state(self, workspace_root: Path) -> None:
        shell_root = workspace_root / WORKSPACE_STATE_DIRNAME
        for path in [
            shell_root / "attachments",
            shell_root / "runtime_events.jsonl",
            shell_root / "approvals.jsonl",
            shell_root / "thread_cache.json",
            shell_root / "ui_state.json",
        ]:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".json":
                if not path.exists():
                    write_json(path, {})
            elif path.suffix == ".jsonl":
                path.touch(exist_ok=True)
            else:
                path.mkdir(parents=True, exist_ok=True)
        self._ensure_git_exclude(workspace_root)

    def _ensure_git_exclude(self, workspace_root: Path) -> None:
        git_root = workspace_root / ".git"
        if not git_root.exists() or not git_root.is_dir():
            return
        exclude_file = git_root / "info" / "exclude"
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude_file.read_text(encoding="utf-8") if exclude_file.exists() else ""
        additions = []
        if f"{WORKSPACE_STATE_DIRNAME}/" not in existing:
            additions.append(f"{WORKSPACE_STATE_DIRNAME}/")
        if additions:
            suffix = "\n".join(additions) + "\n"
            exclude_file.write_text(existing.rstrip() + ("\n" if existing and not existing.endswith("\n") else "") + suffix, encoding="utf-8")

    def _default_ui_preferences(self) -> dict[str, Any]:
        runtime = self._default_runtime_preferences()
        return {
            "locale": "zh-CN",
            "appearance": "codex",
            "execution_host": runtime["execution_host"],
            "wsl_distro": runtime["wsl_distro"],
            "left_sidebar_width": 288,
            "right_sidebar_width": 328,
            "right_sidebar_open": True,
        }

    def _normalize_ui_preferences(self, preferences: dict[str, Any]) -> dict[str, Any]:
        defaults = self._default_ui_preferences()
        merged = {**defaults, **preferences}
        host = str(merged.get("execution_host") or "").strip().lower()
        if host not in {"windows", "wsl"}:
            host = defaults["execution_host"]
        merged["execution_host"] = host
        if host == "wsl":
            merged["wsl_distro"] = str(merged.get("wsl_distro") or defaults["wsl_distro"] or DEFAULT_WSL_DISTRO)
        else:
            merged["wsl_distro"] = str(merged.get("wsl_distro") or "")
        return merged

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

