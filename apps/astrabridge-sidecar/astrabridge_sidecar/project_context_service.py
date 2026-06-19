from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, now_iso, read_json, write_json
from .security import SECRET_RE, SecurityError, redact_sensitive


PROJECT_CONTEXT_SCHEMA_VERSION = "lcr-project-context-pack-v1"
PROJECT_FILE_MAP_MAX_FILES = 80
PROJECT_FILE_MAP_TEXT_MAX_FILES = 36
PROJECT_FILE_MAP_MAX_TOP_LEVEL = 60
PROJECT_FILE_MAP_EXCLUDED_DIRS = {
    WORKSPACE_STATE_DIRNAME,
    ".codex",
    ".codex-shell",
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "playwright-report",
    "target",
    "test-results",
    "tmp",
}
PROJECT_FILE_MAP_SOURCE_EXTENSIONS = {
    ".c",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".rs",
    ".svelte",
    ".toml",
    ".ts",
    ".tsx",
    ".vue",
    ".yaml",
    ".yml",
}
PROJECT_FILE_MAP_ENTRY_PATHS = {
    "app.py",
    "cargo.toml",
    "index.html",
    "main.py",
    "package.json",
    "pyproject.toml",
    "readme.md",
    "src/app.jsx",
    "src/app.tsx",
    "src/main.jsx",
    "src/main.tsx",
    "vite.config.js",
    "vite.config.ts",
}
PROJECT_FILE_MAP_SENSITIVE_MARKERS = {
    "apikey",
    "api_key",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
}


class ProjectContextService:
    """Durable, lightweight project memory injected across thread switches.

    This is deliberately an index of project state, not a transcript archive.
    It keeps DS/Kimi/Yunwu oriented after switching threads, compacting, or
    restarting the sidecar without exposing raw runtime logs or secrets.
    """

    def __init__(self, project_service, dogfood_service=None, asset_registry_service=None, task_service=None) -> None:
        self._projects = project_service
        self._dogfood = dogfood_service
        self._assets = asset_registry_service
        self._tasks = task_service

    def snapshot(self, *, thread_id: str | None = None) -> dict[str, Any]:
        pack = self._build_pack(thread_id=thread_id)
        write_json(self._path(), pack)
        path = str(self._path())
        if self._tasks is not None:
            try:
                self._tasks.record_context_ref(
                    pack_type="project",
                    path=path,
                    generated_at=str(pack.get("generated_at") or now_iso()),
                    summary={
                        "thread_id": str((pack.get("project") or {}).get("current_thread_id") or ""),
                        "task_id": str((pack.get("project") or {}).get("current_task_id") or ""),
                    },
                )
            except Exception:
                pass
        return {"context_pack": pack, "path": path, "context_pack_path": path}

    def context_inputs(self, *, thread_id: str | None = None) -> list[dict[str, Any]]:
        try:
            pack = self.snapshot(thread_id=thread_id)["context_pack"]
        except Exception:
            return []
        text = str(pack.get("text") or "").strip()
        if not text:
            return []
        return [{"type": "text", "text": text, "text_elements": []}]

    def record_runtime_notification(self, method: str, params: Any) -> None:
        if not isinstance(params, dict):
            return
        method = str(method or "")
        if method not in {
            "turn/plan/updated",
            "thread/goal/updated",
            "thread/goal/cleared",
            "thread/settings/updated",
            "thread/compacted",
            "thread/name/updated",
            "thread/started",
        }:
            return
        current = self._state()
        thread_id = self._thread_id_from_params(params)
        if not thread_id:
            return
        threads = dict(current.get("threads") or {})
        entry = dict(threads.get(thread_id) or {"thread_id": thread_id})
        if method == "turn/plan/updated":
            entry["latest_plan"] = {
                "turn_id": str(params.get("turnId") or ""),
                "explanation": params.get("explanation"),
                "steps": list(params.get("plan") or []),
                "updated_at": now_iso(),
            }
        elif method == "thread/goal/updated":
            entry["goal"] = params.get("goal") or {}
            entry["goal_updated_at"] = now_iso()
        elif method == "thread/goal/cleared":
            entry["goal"] = None
            entry["goal_updated_at"] = now_iso()
        elif method == "thread/settings/updated":
            entry["settings"] = dict(params.get("settings") or params)
            entry["settings_updated_at"] = now_iso()
        elif method == "thread/compacted":
            entry["last_compacted_at"] = now_iso()
            entry["compact"] = dict(params)
        elif method == "thread/name/updated":
            entry["name"] = params.get("threadName") or entry.get("name") or ""
        elif method == "thread/started":
            thread = dict(params.get("thread") or {})
            entry["name"] = thread.get("name") or entry.get("name") or ""
        entry["updated_at"] = now_iso()
        threads[thread_id] = entry
        current["threads"] = threads
        current["updated_at"] = now_iso()
        self._reject_secret_like(current)
        write_json(self._state_path(), current)

    def record_thread_hint(self, thread_id: str, patch: dict[str, Any]) -> None:
        if not str(thread_id or "").strip():
            return
        current = self._state()
        threads = dict(current.get("threads") or {})
        entry = dict(threads.get(thread_id) or {"thread_id": thread_id})
        allowed = {
            "name",
            "profile_id",
            "provider_id",
            "model",
            "reasoning_effort",
            "permission_mode",
            "collaboration_mode",
        }
        for key in allowed:
            if key in patch and patch.get(key) is not None:
                entry[key] = patch.get(key)
        entry["updated_at"] = now_iso()
        threads[thread_id] = entry
        current["threads"] = threads
        current["updated_at"] = now_iso()
        self._reject_secret_like(current)
        write_json(self._state_path(), current)

    def _build_pack(self, *, thread_id: str | None) -> dict[str, Any]:
        project = dict(self._projects.current_project or {})
        state = self._state()
        thread_cache = read_json(self._shell_root() / "thread_cache.json", {"by_id": {}})
        task_full = self._task_full()
        logical_thread = self._logical_task_thread(task_full)
        selected_thread_id = str(
            thread_id
            or (task_full or {}).get("active_provider_thread_id")
            or project.get("current_thread_id")
            or (logical_thread or {}).get("thread_id")
            or ""
        )
        thread_entry = self._thread_entry(selected_thread_id, state, thread_cache)
        if logical_thread:
            thread_entry = self._compact_thread_entry({**logical_thread, **thread_entry, "thread_id": selected_thread_id})
        recent_threads = self._recent_threads(project, state, thread_cache)
        task = self._task_summary(task_full)
        dogfood = self._dogfood_summary(task=task)
        assets = self._asset_summary()
        file_map = self._project_file_map()
        text = self._text(project, selected_thread_id, thread_entry, recent_threads, task, dogfood, assets, file_map)
        pack = {
            "schema_version": PROJECT_CONTEXT_SCHEMA_VERSION,
            "generated_at": now_iso(),
            "project": {
                "name": project.get("name") or "",
                "project_file": project.get("project_file") or "",
                "workspace_root": project.get("workspace_root") or "",
                "current_thread_id": selected_thread_id,
                "default_profile_id": project.get("default_profile_id") or "",
                "default_model": project.get("default_model") or "",
                "default_effort": project.get("default_effort") or "",
                "execution_host": dict(project.get("ui_preferences") or {}).get("execution_host") or "",
                "wsl_distro": dict(project.get("ui_preferences") or {}).get("wsl_distro") or "",
                "current_task_id": project.get("current_task_id") or "",
            },
            "task": task,
            "selected_thread": thread_entry,
            "recent_threads": recent_threads,
            "dogfood": dogfood,
            "assets": assets,
            "project_file_map": file_map,
            "rules": [
                "Use this project context pack after thread switches, compact, fork, or sidecar restart.",
                "Do not read .lcr/runtime_events.jsonl or .lcr/approvals.jsonl unless the user explicitly asks.",
                "Use compact summaries, project_context_pack.json, asset_context_pack.json, screenshots, and manifests before raw logs.",
                "For public web research, prefer LCR built-in tools lcr_web_research_brief and lcr_web_search_batch; avoid raw curl, wget, or python urllib unless the LCR web tools fail or the user explicitly asks.",
                "When resuming another thread, verify the current thread id, goal, latest plan, and project files before editing.",
            ],
            "text": text[:8000],
        }
        self._reject_secret_like(pack)
        return pack

    def _text(
        self,
        project: dict[str, Any],
        thread_id: str,
        thread_entry: dict[str, Any],
        recent_threads: list[dict[str, Any]],
        task: dict[str, Any],
        dogfood: dict[str, Any],
        assets: dict[str, Any],
        file_map: dict[str, Any],
    ) -> str:
        lines = [
            "LCR Project Context Pack (auto-injected, secret-free)",
            "Freshness rule: this pack supersedes any older auto-injected LCR Project/Asset Context Pack text already present in the thread history.",
            "If counts, paths, goals, plans, or asset refs conflict, use this newest pack and the referenced JSON files.",
            f"Project: {project.get('name') or 'untitled'}",
            f"Workspace: {project.get('workspace_root') or ''}",
            f"Current task: {task.get('title') or task.get('task_id') or 'none'}",
            f"Current thread: {thread_id or 'none'}",
            f"Default runtime: profile={project.get('default_profile_id') or ''} model={project.get('default_model') or ''} effort={project.get('default_effort') or ''}",
        ]
        if file_map.get("status") == "ok":
            entry_files = list(file_map.get("entry_files") or [])
            source_files = list(file_map.get("source_files") or [])
            if entry_files or source_files:
                lines.append("Project file map (real paths observed at context-pack generation time):")
                if entry_files:
                    lines.append("Entry files: " + ", ".join(str(item) for item in entry_files[:12]))
                if source_files:
                    lines.append("Source files include:")
                    for item in source_files[:PROJECT_FILE_MAP_TEXT_MAX_FILES]:
                        if isinstance(item, dict):
                            lines.append(f"- {item.get('path')} role={item.get('role')}")
                    omitted = int(file_map.get("omitted") or 0)
                    if omitted > 0:
                        lines.append(f"- ... {omitted} more source files omitted from this text; inspect the workspace before naming unlisted paths.")
                lines.append(
                    "File-map rule: use only listed real paths unless you first inspect/list the workspace; "
                    "do not invent paths such as game/map/... from project type alone."
                )
        elif file_map.get("status"):
            lines.append(f"Project file map: unavailable ({file_map.get('status')}); list the workspace before naming files.")
        provider_threads = list(task.get("provider_threads") or [])
        if task:
            lines.append(
                "Task continuity: provider switches are internal handoffs within this same user-visible task; "
                "do not treat a provider-thread switch as a new objective."
            )
            if task.get("goal"):
                goal = task.get("goal")
                if isinstance(goal, dict) and goal.get("objective"):
                    lines.append(f"Task goal: {goal.get('objective')}")
                elif isinstance(goal, str):
                    lines.append(f"Task goal: {goal}")
            if task.get("plan"):
                plan = dict(task.get("plan") or {})
                steps = [str(item.get("step") or item) for item in list(plan.get("steps") or plan.get("plan") or [])[:6]]
                if steps and not self._plan_is_completed(plan):
                    lines.append("Task plan:")
                    lines.extend(f"- {step}" for step in steps)
                elif steps:
                    lines.append("Task plan record: previously completed; use the dogfood next step or the next real plan update for the active step.")
            if provider_threads:
                lines.append("Provider threads for this task:")
                for item in provider_threads[:8]:
                    lines.append(
                        f"- {item.get('thread_id')} profile={item.get('profile_id') or ''} "
                        f"model={item.get('model') or ''} effort={item.get('reasoning_effort') or ''}"
                    )
            handoff_events = list(task.get("handoff_events") or [])
            if handoff_events:
                latest = dict(handoff_events[-1])
                lines.append(
                    f"Latest provider handoff: {latest.get('from_thread_id') or 'none'} -> {latest.get('to_thread_id') or ''} "
                    f"profile={latest.get('profile_id') or ''} model={latest.get('model') or ''} effort={latest.get('reasoning_effort') or ''}"
                )
        if thread_entry:
            lines.append(
                "Selected thread settings: "
                f"name={thread_entry.get('name') or ''} model={thread_entry.get('model') or ''} "
                f"effort={thread_entry.get('reasoning_effort') or ''} permission={thread_entry.get('permission_mode') or ''}"
            )
            if thread_entry.get("missing_reason"):
                lines.append(
                    f"Selected thread availability: missing ({thread_entry.get('missing_reason')}); "
                    "continue this same task by recovering or handoffing the provider thread, not by inventing a new objective."
                )
            goal = thread_entry.get("goal")
            if isinstance(goal, dict) and goal.get("objective"):
                lines.append(f"Selected thread goal: {goal.get('objective')}")
            latest_plan = thread_entry.get("latest_plan")
            if isinstance(latest_plan, dict):
                steps = [str(item.get("step") or item) for item in list(latest_plan.get("steps") or [])[:6]]
                if steps:
                    lines.append("Latest selected-thread plan:")
                    lines.extend(f"- {step}" for step in steps)
        if dogfood.get("enabled"):
            lines.append(
                f"Dogfood: phase={dogfood.get('phase')} status={dogfood.get('status')} provider={dogfood.get('current_provider')}"
            )
            if dogfood.get("goal"):
                lines.append(f"Dogfood goal: {dogfood.get('goal')}")
            if dogfood.get("next_step"):
                lines.append(f"Dogfood next step: {dogfood.get('next_step')}")
            if dogfood.get("latest_milestone"):
                milestone = dict(dogfood.get("latest_milestone") or {})
                lines.append(f"Latest milestone: {milestone.get('label')} status={milestone.get('status')}")
        if assets.get("total"):
            lines.append(
                f"Asset memory: total={assets.get('total')} promoted_or_in_use={assets.get('promoted_or_in_use')} "
                f"approved_unpromoted={assets.get('approved_unpromoted')} needs_review={assets.get('needs_review')}"
            )
            lines.append(f"Asset context: {assets.get('context_pack_path') or ''}")
        if recent_threads:
            lines.append("Recent threads:")
            for item in recent_threads[:8]:
                lines.append(
                    f"- {item.get('thread_id')} name={item.get('name') or ''} model={item.get('model') or ''} updated={item.get('updated_at') or ''}"
                )
        lines.extend(
            [
                "Rules:",
                "- Treat this pack as an orientation index, not as complete truth; inspect referenced project files before editing.",
                "- Context pack JSON paths are orientation references only; do not call MCP resources/read for them unless LCR explicitly exposes a matching MCP server.",
                "- Do not use generated/sliced assets in game code until they are promoted into the game manifest.",
                "- If context seems stale after thread switching, ask for or trigger a project-context refresh before continuing.",
                "- Ignore older auto-injected Project/Asset Context Pack blocks when this pack has a newer generated_at timestamp.",
                "- On provider handoff, continue the same task goal/plan/assets unless the user explicitly creates a new chat/task or fork branch.",
                "- For web research, use lcr_web_research_brief for multi-source briefs and lcr_web_search_batch for one or more search queries; do not run raw curl/wget/python HTTP loops unless those tools fail and you explain why.",
            ]
        )
        return "\n".join(lines)

    def _project_file_map(self) -> dict[str, Any]:
        try:
            workspace = self._projects.require_workspace_root()
        except Exception:
            return {"status": "unavailable", "reason": "no_workspace"}
        try:
            workspace = workspace.resolve()
        except Exception:
            return {"status": "unavailable", "reason": "workspace_unresolved"}
        if not workspace.exists() or not workspace.is_dir():
            return {"status": "unavailable", "reason": "workspace_missing"}

        top_level: list[dict[str, Any]] = []
        try:
            children = sorted(workspace.iterdir(), key=lambda item: item.name.lower())
        except Exception:
            children = []
        for child in children:
            rel = Path(child.name)
            if self._is_excluded_relative_path(rel):
                continue
            try:
                kind = "dir" if child.is_dir() else "file"
            except Exception:
                kind = "unknown"
            top_level.append({"path": rel.as_posix(), "kind": kind})
            if len(top_level) >= PROJECT_FILE_MAP_MAX_TOP_LEVEL:
                break

        files: list[dict[str, Any]] = []
        total_candidates = 0
        for root_dir, dir_names, file_names in os.walk(workspace):
            root_path = Path(root_dir)
            try:
                rel_root = root_path.relative_to(workspace)
            except ValueError:
                continue
            dir_names[:] = [
                name
                for name in dir_names
                if not self._is_excluded_relative_path((rel_root / name) if str(rel_root) != "." else Path(name))
            ]
            for file_name in sorted(file_names, key=str.lower):
                rel = (rel_root / file_name) if str(rel_root) != "." else Path(file_name)
                if self._is_excluded_relative_path(rel) or not self._is_source_file(rel):
                    continue
                path = root_path / file_name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                total_candidates += 1
                files.append(
                    {
                        "path": rel.as_posix(),
                        "role": self._file_role(rel),
                        "size_bytes": int(stat.st_size),
                        "modified_unix": int(stat.st_mtime),
                    }
                )

        files.sort(key=self._file_map_sort_key)
        selected = files[:PROJECT_FILE_MAP_MAX_FILES]
        entry_files = [str(item.get("path") or "") for item in selected if item.get("role") == "entry"]
        return {
            "status": "ok",
            "workspace_root": str(workspace),
            "top_level": top_level,
            "entry_files": entry_files[:20],
            "source_files": selected,
            "total_source_candidates": total_candidates,
            "omitted": max(0, total_candidates - len(selected)),
            "rules": [
                "Use only listed real paths unless you inspect the workspace first.",
                "If a needed path is not listed, list/read the directory before naming or editing it.",
                "Runtime state and credential-like files are intentionally excluded.",
            ],
        }

    def _is_source_file(self, rel: Path) -> bool:
        return rel.suffix.lower() in PROJECT_FILE_MAP_SOURCE_EXTENSIONS

    def _file_role(self, rel: Path) -> str:
        lower_path = rel.as_posix().lower()
        name = rel.name.lower()
        suffix = rel.suffix.lower()
        if lower_path in PROJECT_FILE_MAP_ENTRY_PATHS or name in PROJECT_FILE_MAP_ENTRY_PATHS:
            return "entry"
        if name in {"sprite_manifest.json", "asset_manifest.json"} or lower_path.endswith("/sprite_manifest.json"):
            return "asset_manifest"
        if suffix in {".css", ".scss"}:
            return "style"
        if suffix in {".json", ".yaml", ".yml", ".toml"}:
            return "config"
        if suffix in {".md"}:
            return "doc"
        return "source"

    def _file_map_sort_key(self, item: dict[str, Any]) -> tuple[int, int, str]:
        role_order = {
            "entry": 0,
            "asset_manifest": 1,
            "source": 2,
            "style": 3,
            "config": 4,
            "doc": 5,
        }
        path = str(item.get("path") or "")
        return (role_order.get(str(item.get("role") or ""), 9), path.count("/"), path.lower())

    def _is_excluded_relative_path(self, rel: Path) -> bool:
        parts = [part.lower() for part in rel.parts if part not in {"", "."}]
        if not parts:
            return False
        if any(part in PROJECT_FILE_MAP_EXCLUDED_DIRS for part in parts):
            return True
        if any(part.startswith(".") for part in parts):
            return True
        return any(self._looks_credential_like(part) for part in parts)

    def _looks_credential_like(self, value: str) -> bool:
        lowered = str(value or "").lower()
        if lowered.startswith(".env"):
            return True
        compact = lowered.replace("-", "_")
        return any(marker in compact for marker in PROJECT_FILE_MAP_SENSITIVE_MARKERS)

    def _task_full(self) -> dict[str, Any]:
        if self._tasks is None:
            return {}
        try:
            task = self._tasks.current_task()
        except Exception:
            return {}
        return dict(task or {})

    def _logical_task_thread(self, task: dict[str, Any]) -> dict[str, Any]:
        if not task:
            return {}
        provider_threads = [
            dict(item)
            for item in list(task.get("provider_threads") or [])
            if isinstance(item, dict) and _provider_model_pair_is_plausible(item)
        ]
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        if active_thread_id:
            for item in provider_threads:
                if str(item.get("thread_id") or "").strip() == active_thread_id:
                    return item
        live_threads = [item for item in provider_threads if not item.get("missing_at")]
        if live_threads:
            live_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return live_threads[0]
        provider_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return provider_threads[0] if provider_threads else {}

    def _task_summary(self, task: dict[str, Any] | None = None) -> dict[str, Any]:
        if task is None:
            task = self._task_full()
        if not task:
            return {}
        keys = {
            "task_id",
            "title",
            "status",
            "handoff_policy",
            "active_provider_thread_id",
            "provider_threads",
            "handoff_events",
            "goal",
            "plan",
            "checkpoint_refs",
            "asset_context_refs",
            "context_pack_refs",
            "updated_at",
        }
        compact = {key: task.get(key) for key in keys if key in task}
        compact["provider_threads"] = [
            self._compact_provider_thread(item)
            for item in list(compact.get("provider_threads") or [])
            if _provider_model_pair_is_plausible(item)
        ][:10]
        compact["handoff_events"] = [
            self._compact_handoff_event(item)
            for item in list(compact.get("handoff_events") or [])
            if _provider_model_pair_is_plausible(item)
        ][-10:]
        compact["checkpoint_refs"] = list(compact.get("checkpoint_refs") or [])[:10]
        compact["asset_context_refs"] = list(compact.get("asset_context_refs") or [])[:10]
        compact["context_pack_refs"] = list(compact.get("context_pack_refs") or [])[:10]
        return compact

    def _compact_provider_thread(self, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {}
        return {
            "thread_id": item.get("thread_id"),
            "profile_id": item.get("profile_id"),
            "provider_id": item.get("provider_id"),
            "model": item.get("model"),
            "reasoning_effort": item.get("reasoning_effort"),
            "permission_mode": item.get("permission_mode"),
            "role": item.get("role"),
            "missing_at": item.get("missing_at"),
            "missing_reason": item.get("missing_reason"),
            "updated_at": item.get("updated_at"),
        }

    def _compact_handoff_event(self, item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            return {}
        return {
            "event_id": item.get("event_id"),
            "type": item.get("type"),
            "from_thread_id": item.get("from_thread_id"),
            "to_thread_id": item.get("to_thread_id"),
            "profile_id": item.get("profile_id"),
            "provider_id": item.get("provider_id"),
            "model": item.get("model"),
            "reasoning_effort": item.get("reasoning_effort"),
            "reused_existing": item.get("reused_existing"),
            "created_at": item.get("created_at"),
        }

    def _recent_threads(self, project: dict[str, Any], state: dict[str, Any], thread_cache: dict[str, Any]) -> list[dict[str, Any]]:
        by_id = {**dict(thread_cache.get("by_id") or {}), **dict(state.get("threads") or {})}
        ids = [str(item) for item in list(project.get("recent_threads") or []) if str(item).strip()]
        result = []
        for thread_id in ids:
            entry = dict(by_id.get(thread_id) or {"thread_id": thread_id})
            entry.setdefault("thread_id", thread_id)
            if _provider_model_pair_is_plausible(entry):
                result.append(self._compact_thread_entry(entry))
        return result

    def _thread_entry(self, thread_id: str, state: dict[str, Any], thread_cache: dict[str, Any]) -> dict[str, Any]:
        if not thread_id:
            return {}
        entry = {
            **dict(thread_cache.get("by_id", {}).get(thread_id) or {}),
            **dict(state.get("threads", {}).get(thread_id) or {}),
        }
        entry.setdefault("thread_id", thread_id)
        return self._compact_thread_entry(entry)

    def _compact_thread_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        keys = {
            "thread_id",
            "name",
            "profile_id",
            "provider_id",
            "model",
            "reasoning_effort",
            "permission_mode",
            "collaboration_mode",
            "latest_plan",
            "goal",
            "last_compacted_at",
            "missing_at",
            "missing_reason",
            "updated_at",
        }
        return {key: entry.get(key) for key in keys if key in entry}

    def _dogfood_summary(self, *, task: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._dogfood is None:
            return {"enabled": False}
        try:
            run = dict(self._dogfood.snapshot().get("run") or {})
        except Exception:
            return {"enabled": False, "status": "unavailable"}
        milestones = list(run.get("milestones") or [])
        captures = list(run.get("captures") or [])
        task_goal = self._task_goal_text(task or {})
        latest_milestone = self._select_relevant_milestone(milestones, task_goal)
        run_goal = str(run.get("goal") or "")
        goal = run_goal[:1000]
        current_provider = str(run.get("current_provider") or "")
        next_step = str(run.get("next_step") or "")[:1000]
        goal_aligned = bool(task_goal and goal and self._goals_related(goal, task_goal))
        active_task_provider = self._task_active_provider(task or {})
        if task_goal:
            if not goal_aligned:
                goal = task_goal[:1000]
            if latest_milestone is not None and not goal_aligned:
                milestone_provider = str(latest_milestone.get("provider") or "").strip()
                milestone_next = str(latest_milestone.get("next_action") or latest_milestone.get("next_step") or "").strip()
                if milestone_provider:
                    current_provider = milestone_provider[:80]
                if milestone_next:
                    next_step = milestone_next[:1000]
            elif not goal_aligned:
                current_provider = ""
                next_step = ""
            elif active_task_provider:
                current_provider = active_task_provider
        return {
            "enabled": bool(run.get("enabled")),
            "goal": goal,
            "phase": str(run.get("phase") or ""),
            "status": str(run.get("status") or ""),
            "current_provider": current_provider,
            "next_step": next_step,
            "budgets": run.get("budgets") or {},
            "usage": run.get("usage") or {},
            "latest_milestone": self._compact_milestone(latest_milestone) if latest_milestone else None,
            "latest_capture": self._compact_capture(captures[0]) if captures else None,
        }

    def _task_goal_text(self, task: dict[str, Any]) -> str:
        goal = task.get("goal")
        if isinstance(goal, dict):
            return str(goal.get("objective") or "").strip()
        return str(goal or "").strip()

    def _task_active_provider(self, task: dict[str, Any]) -> str:
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        provider_threads = list(task.get("provider_threads") or [])
        for item in provider_threads:
            if not isinstance(item, dict):
                continue
            if str(item.get("thread_id") or "").strip() != active_thread_id:
                continue
            provider = str(item.get("provider_id") or "").strip()
            if provider:
                return provider[:80]
        if self._tasks is not None:
            try:
                active = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
            except Exception:
                active = {}
            provider = str(active.get("provider_id") or "").strip()
            if provider:
                return provider[:80]
        return ""

    def _plan_is_completed(self, plan: dict[str, Any]) -> bool:
        steps = list(plan.get("steps") or plan.get("plan") or [])
        if not steps:
            return False
        statuses = [str((item.get("status") if isinstance(item, dict) else "") or "").strip().lower() for item in steps]
        meaningful = [status for status in statuses if status]
        return bool(meaningful) and all(status == "completed" for status in meaningful)

    def _select_relevant_milestone(self, milestones: list[Any], task_goal: str) -> dict[str, Any] | None:
        if not milestones:
            return None
        if not task_goal:
            last = milestones[-1]
            return dict(last) if isinstance(last, dict) else None
        for item in reversed(milestones):
            if not isinstance(item, dict):
                continue
            milestone_goal = str(item.get("goal") or "").strip()
            if not milestone_goal or self._goals_related(milestone_goal, task_goal):
                return dict(item)
        return None

    def _goals_related(self, left: str, right: str) -> bool:
        left_norm = self._normalize_goal_text(left)
        right_norm = self._normalize_goal_text(right)
        if not left_norm or not right_norm:
            return False
        if left_norm == right_norm:
            return True
        if len(left_norm) >= 24 and left_norm in right_norm:
            return True
        if len(right_norm) >= 24 and right_norm in left_norm:
            return True
        left_tokens = {token for token in left_norm.split() if len(token) >= 3}
        right_tokens = {token for token in right_norm.split() if len(token) >= 3}
        if not left_tokens or not right_tokens:
            return False
        overlap = left_tokens & right_tokens
        if len(overlap) >= 4:
            return True
        min_size = min(len(left_tokens), len(right_tokens))
        return min_size > 0 and (len(overlap) / min_size) >= 0.5

    def _normalize_goal_text(self, text: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())
        return re.sub(r"\s+", " ", normalized).strip()

    def _compact_milestone(self, milestone: Any) -> dict[str, Any] | None:
        if not isinstance(milestone, dict):
            return None
        return {
            "label": str(milestone.get("label") or "")[:240],
            "provider": str(milestone.get("provider") or "")[:80],
            "model": str(milestone.get("model") or "")[:120],
            "plan_step": str(milestone.get("plan_step") or "")[:240],
            "status": str(milestone.get("status") or "")[:80],
            "next_action": str(milestone.get("next_action") or milestone.get("next_step") or "")[:500],
            "created_at": str(milestone.get("created_at") or "")[:80],
        }

    def _compact_capture(self, capture: Any) -> dict[str, Any] | str | None:
        if isinstance(capture, str):
            return capture[:500]
        if not isinstance(capture, dict):
            return None
        return {
            "path": str(capture.get("path") or "")[:500],
            "label": str(capture.get("label") or "")[:160],
            "provider": str(capture.get("provider") or "")[:120],
            "created_at": str(capture.get("created_at") or "")[:80],
        }

    def _asset_summary(self) -> dict[str, Any]:
        if self._assets is None:
            return {}
        try:
            pack = self._assets.snapshot()
            context = pack.get("context_pack") or {}
            summary = dict((pack.get("registry") or {}).get("summary") or {})
            return {
                **summary,
                "summary": summary,
                "registry_path": pack.get("path"),
                "context_pack_path": context.get("context_pack_path"),
            }
        except Exception:
            return {"status": "unavailable"}

    def _thread_id_from_params(self, params: dict[str, Any]) -> str:
        thread_id = str(params.get("threadId") or params.get("thread_id") or "")
        if thread_id:
            return thread_id
        thread = params.get("thread")
        if isinstance(thread, dict):
            return str(thread.get("id") or thread.get("thread_id") or "")
        return ""

    def _state(self) -> dict[str, Any]:
        return dict(read_json(self._state_path(), {"schema_version": PROJECT_CONTEXT_SCHEMA_VERSION, "threads": {}}))

    def _path(self) -> Path:
        return self._shell_root() / "project_context_pack.json"

    def _state_path(self) -> Path:
        return self._shell_root() / "project_context_state.json"

    def _shell_root(self) -> Path:
        return self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME

    def _reject_secret_like(self, payload: dict[str, Any]) -> None:
        serialized = str(redact_sensitive(payload))
        if SECRET_RE.search(serialized):
            raise SecurityError("Secret-like content is not allowed in project context pack records.")


def _provider_model_pair_is_plausible(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    provider = str(item.get("provider_id") or "").strip().lower()
    profile = str(item.get("profile_id") or "").strip().lower()
    model = _canonical_model_key(item.get("model"))
    if not model or (not provider and not profile):
        return True
    if provider.startswith("deepseek"):
        return model.startswith("deepseek")
    if provider in {"kimi", "moonshot"} or profile.startswith(("kimi", "moonshot")):
        return model.startswith(("kimi", "moonshot"))
    if provider in {"qwen", "dashscope"} or profile.startswith(("qwen", "dashscope")):
        return model.startswith("qwen")
    return True


def _canonical_model_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "/" in text:
        text = text.split("/", 1)[1]
    return text

