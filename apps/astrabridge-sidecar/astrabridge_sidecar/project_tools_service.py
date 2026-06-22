from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import subprocess
from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, now_iso
from .coding_kernel import (
    EditExecutor,
    available_operations_for_request,
    edit_operation_to_coding_event,
    request_from_payload,
    select_edit_strategy,
)
from .providers import get_provider_profile


TEXT_EXTENSIONS = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".agents",
    ".codex",
    ".astrabridge",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}
SKIP_LCR_DIRS = {"saves", "runtime_events.jsonl", "approvals.jsonl"}
SECRET_NAME_PARTS = ("secret", "token", "apikey", "api_key", "authorization", "cookie", "password", ".env")
MAX_TEXT_BYTES = 1_000_000
MAX_IMAGE_BYTES = 2_500_000
MAX_TREE_ITEMS = 500


class ProjectToolsService:
    """Bounded project tools for the inspector and coding workflow surfaces.

    This intentionally exposes summaries, bounded previews, and guarded edit
    operations rather than raw project logs. The UI can inspect useful
    workspace state without creating a second uncontrolled file/terminal
    surface.
    """

    def __init__(self, projects, runtime, *, checkpoints=None, tasks=None, profiles=None, router_config=None) -> None:
        self._projects = projects
        self._runtime = runtime
        self._checkpoints = checkpoints
        self._tasks = tasks
        self._profiles = profiles
        self._router_config = router_config

    def review_status(self) -> dict[str, Any]:
        root = self._workspace_root()
        git = self._git_summary(root)
        files = git.get("files") or self._recent_files(root)
        return {
            "workspace_root": str(root),
            "git": {key: value for key, value in git.items() if key != "files"},
            "files": files[:80],
            "updated_at": now_iso(),
        }

    def review_diff(self, rel_path: str | None = None) -> dict[str, Any]:
        root = self._workspace_root()
        if rel_path:
            target = self._safe_rel_path(root, rel_path, allow_lcr=False)
            display_path = target.relative_to(root).as_posix()
            args = ["git", "-C", str(root), "diff", "--", display_path]
        else:
            args = ["git", "-C", str(root), "diff", "--stat", "--", "."]
        result = self._run(args, timeout=10)
        if result["ok"]:
            diff = str(result["stdout"] or "")
            if rel_path and not diff.strip():
                synthetic = self._synthetic_file_diff(root, target)
                if synthetic:
                    return {"ok": True, "path": rel_path or "", "diff": synthetic[:120_000], "truncated": len(synthetic) > 120_000, "synthetic": True}
            return {"ok": True, "path": rel_path or "", "diff": diff[:120_000], "truncated": len(diff) > 120_000}
        if rel_path:
            synthetic = self._synthetic_file_diff(root, target)
            if synthetic:
                return {"ok": True, "path": rel_path or "", "diff": synthetic[:120_000], "truncated": len(synthetic) > 120_000, "synthetic": True}
        return {"ok": False, "path": rel_path or "", "diff": "", "error": result["stderr"] or result["error"]}

    def files_tree(self, query: str | None = None, limit: int = MAX_TREE_ITEMS) -> dict[str, Any]:
        root = self._workspace_root()
        query_text = (query or "").strip().lower()
        items: list[dict[str, Any]] = []
        limit = max(50, min(int(limit or MAX_TREE_ITEMS), 1000))
        for current, dirs, files in os.walk(root):
            current_path = Path(current)
            rel_dir = current_path.relative_to(root)
            dirs[:] = [name for name in sorted(dirs) if not self._skip_dir(rel_dir / name)]
            for name in sorted(files):
                rel = rel_dir / name
                rel_text = rel.as_posix()
                if rel_text == WORKSPACE_STATE_DIRNAME or rel_text.startswith(f"{WORKSPACE_STATE_DIRNAME}/"):
                    continue
                if self._skip_file(rel):
                    continue
                if query_text and query_text not in rel_text.lower():
                    continue
                path = current_path / name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                items.append(
                    {
                        "path": rel_text,
                        "name": name,
                        "kind": self._file_kind(path),
                        "size": stat.st_size,
                        "updated_at": stat.st_mtime,
                    }
                )
                if len(items) >= limit:
                    return {"workspace_root": str(root), "filter_version": "skip-astrabridge-v1", "items": items, "truncated": True, "updated_at": now_iso()}
        return {"workspace_root": str(root), "filter_version": "skip-astrabridge-v1", "items": items, "truncated": False, "updated_at": now_iso()}

    def read_file(self, rel_path: str) -> dict[str, Any]:
        root = self._workspace_root()
        path = self._safe_rel_path(root, rel_path, allow_lcr=True)
        stat = path.stat()
        kind = self._file_kind(path)
        payload: dict[str, Any] = {
            "path": path.relative_to(root).as_posix(),
            "name": path.name,
            "kind": kind,
            "size": stat.st_size,
            "updated_at": stat.st_mtime,
        }
        if kind == "text":
            if stat.st_size > MAX_TEXT_BYTES:
                return {**payload, "kind": "too_large", "message": f"Text preview is limited to {MAX_TEXT_BYTES} bytes."}
            payload["content"] = path.read_text(encoding="utf-8-sig", errors="replace")
            return payload
        if kind == "image":
            if stat.st_size > MAX_IMAGE_BYTES:
                return {**payload, "kind": "too_large", "message": f"Image preview is limited to {MAX_IMAGE_BYTES} bytes."}
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            payload["mime_type"] = mime
            payload["data_url"] = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
            return payload
        return {**payload, "message": "Binary preview is not supported yet."}

    def terminal_history(self, limit: int = 30) -> dict[str, Any]:
        root = self._workspace_root()
        events = self._runtime.list_events(after=0, limit=250).get("events") or []
        commands: list[dict[str, Any]] = []
        for event in reversed(events):
            command = self._extract_command(event)
            if not command:
                continue
            commands.append(
                {
                    "timestamp": event.get("timestamp"),
                    "status": self._extract_status(event),
                    "command": command[:600],
                    "summary": " ".join(command.split())[:180],
                }
            )
            if len(commands) >= limit:
                break
        return {
            "workspace_root": str(root),
            "execution_host": (self._projects.current_project or {}).get("ui_preferences", {}).get("execution_host", "unknown"),
            "commands": list(reversed(commands)),
            "updated_at": now_iso(),
        }

    def list_checkpoints(self, limit: int = 20) -> dict[str, Any]:
        if self._checkpoints is None:
            return {"saves": [], "saves_root": "", "available": False}
        response = dict(self._checkpoints.list_saves() or {})
        saves = list(response.get("saves") or [])
        bounded_limit = max(1, min(int(limit or 20), 100))
        response["saves"] = saves[:bounded_limit]
        response["available"] = True
        response["truncated"] = len(saves) > bounded_limit
        response["updated_at"] = now_iso()
        return response

    def create_checkpoint(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._checkpoints is None:
            raise ValueError("Checkpoint service is not available.")
        request = dict(payload or {})
        context = self._edit_context(request, target_exists=False)
        thread_name = "Current thread"
        if self._tasks is not None:
            active = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
            thread_name = str(active.get("name") or "").strip() or thread_name
        save_payload = {
            "thread_id": context.get("execution_thread_id"),
            "thread_name": request.get("thread_name") or thread_name,
            "description": request.get("description") or "",
            "provider": context.get("provider_id") or "",
            "model": context.get("model_id") or "",
        }
        response = self._checkpoints.create(save_payload, system=bool(request.get("system")))
        manifest = (response.get("save") or response.get("manifest") or response) if isinstance(response, dict) else {}
        if isinstance(manifest, dict) and self._tasks is not None:
            try:
                self._tasks.record_checkpoint(manifest)
            except Exception:
                pass
        return response

    def resolve_model_record(self, provider_id: str | None, model_id: str | None, *, target_exists: bool = False) -> dict[str, Any]:
        return self._resolve_model_record(provider_id, model_id, target_exists=target_exists)

    def edit_preview(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._edit_operation(payload or {}, apply=False)

    def edit_apply(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._edit_operation(payload or {}, apply=True)

    def _workspace_root(self) -> Path:
        return self._projects.require_workspace_root().resolve()

    def _edit_operation(self, payload: dict[str, Any], *, apply: bool) -> dict[str, Any]:
        root = self._workspace_root()
        request = request_from_payload(payload)
        executor = EditExecutor(root)
        target_exists = executor.target_exists(request.path)
        available_operations = available_operations_for_request(request, target_exists=target_exists)
        context = self._edit_context(payload, target_exists=target_exists)
        estimated_bytes = self._estimate_edit_bytes(request)
        decision = select_edit_strategy(
            model=context["model_record"],
            requested_operation=payload.get("operation"),
            available_operations=available_operations,
            target_exists=target_exists,
            estimated_bytes=estimated_bytes,
            edit_count=len(request.edits),
            profile_id=context["profile_id"],
            provider_id=context["provider_id"],
            model_id=context["model_id"],
        )
        prepared = executor.prepare(request, operation=decision.selected_operation)
        checkpoint = None
        applied = False
        if apply and prepared.changed and decision.selected_operation != "propose_only":
            checkpoint = self._create_edit_checkpoint(prepared, context)
            executor.apply(prepared)
            applied = True
        verification = executor.verification_hook(prepared, checkpoint=checkpoint)
        event_payload = {
            "event_id": f"edit:{hashlib.sha1(f'{prepared.relative_path}:{prepared.operation}:{prepared.changed}:{prepared.added_lines}:{prepared.removed_lines}'.encode('utf-8')).hexdigest()[:16]}",
            "timestamp": now_iso(),
            "path": prepared.relative_path,
            "requested_operation": decision.requested_operation,
            "policy_operation": decision.policy_operation,
            "selected_operation": decision.selected_operation,
            "size_class": decision.size_class,
            "authority_tier": decision.authority_tier,
            "changed": prepared.changed,
            "applied": applied,
            "checkpoint_save_id": ((checkpoint or {}).get("save") or {}).get("save_id"),
            "verification": verification,
            "added_lines": prepared.added_lines,
            "removed_lines": prepared.removed_lines,
            "reason": decision.reason,
        }
        event = edit_operation_to_coding_event(
            task_id=context["task_id"],
            visible_thread_id=context["visible_thread_id"],
            execution_thread_id=context["execution_thread_id"],
            provider_id=context["provider_id"],
            model_id=context["model_id"],
            operation=event_payload,
        )
        if apply and applied:
            self._record_edit_event(event)
        return {
            "ok": True,
            "mode": "apply" if apply else "preview",
            "applied": applied,
            "no_op": not prepared.changed,
            "path": prepared.relative_path,
            "strategy": decision.to_dict(),
            "preview": prepared.preview_payload(),
            "checkpoint": (checkpoint or {}).get("save"),
            "verification": verification,
            "event": event,
        }

    def _create_edit_checkpoint(self, prepared, context: dict[str, Any]) -> dict[str, Any] | None:
        if self._checkpoints is None:
            return None
        description = (
            f"Edit {prepared.relative_path} via {prepared.operation} "
            f"({context.get('provider_id') or 'provider'} / {context.get('model_id') or 'model'})"
        )
        payload = {
            "thread_id": context.get("execution_thread_id"),
            "thread_name": f"Edit {prepared.relative_path}",
            "description": description,
            "provider": context.get("provider_id") or "",
            "model": context.get("model_id") or "",
        }
        return self._checkpoints.create(payload, system=True)

    def _record_edit_event(self, event: dict[str, Any]) -> None:
        record = getattr(self._runtime, "record_supervisor_event", None)
        if not callable(record):
            return
        try:
            record({"event": "edit_operation_applied", "coding_event": event, "path": event.get("payload", {}).get("path")})
        except Exception:
            return

    def _edit_context(self, payload: dict[str, Any], *, target_exists: bool) -> dict[str, Any]:
        profile = self._resolve_profile(payload)
        provider_id = str(payload.get("provider_id") or profile.get("provider_id") or "").strip() or None
        model_id = str(payload.get("model") or payload.get("model_id") or profile.get("model") or "").strip() or None
        model_record = self._resolve_model_record(provider_id, model_id, target_exists=target_exists)
        task = self._tasks.current_task() if self._tasks is not None else None
        active_provider_thread = self._tasks.active_provider_thread(include_missing_fallback=True) if self._tasks is not None else None
        return {
            "profile_id": str(profile.get("profile_id") or payload.get("profile_id") or "").strip() or None,
            "provider_id": provider_id,
            "model_id": model_id,
            "model_record": model_record,
            "task_id": str((task or {}).get("task_id") or ""),
            "visible_thread_id": str(self._tasks.visible_provider_thread_id(include_missing_fallback=True) if self._tasks is not None else ""),
            "execution_thread_id": str((active_provider_thread or {}).get("thread_id") or "") or None,
        }

    def _resolve_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(payload.get("profile_id") or "").strip()
        if profile_id and self._profiles is not None:
            try:
                return dict(self._profiles.resolve_runtime_profile(profile_id))
            except Exception:
                return {"profile_id": profile_id}
        project = self._projects.current_project or {}
        fallback_profile_id = str(project.get("default_profile_id") or "").strip()
        if self._tasks is not None:
            task = self._tasks.current_task() or {}
            active = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
            fallback_profile_id = str(
                payload.get("profile_id")
                or active.get("profile_id")
                or (task.get("composer_settings") or {}).get("profile_id")
                or fallback_profile_id
            ).strip()
        if fallback_profile_id and self._profiles is not None:
            try:
                return dict(self._profiles.resolve_runtime_profile(fallback_profile_id))
            except Exception:
                return {"profile_id": fallback_profile_id}
        return {}

    def _resolve_model_record(self, provider_id: str | None, model_id: str | None, *, target_exists: bool) -> dict[str, Any]:
        if self._router_config is not None and provider_id and model_id:
            full_id = f"{provider_id}/{model_id}"
            for item in self._router_config.models():
                if str(item.get("id") or "") in {model_id, full_id}:
                    return dict(item)
                if str(item.get("provider") or "") == provider_id and str(item.get("native_model") or "") == model_id:
                    return dict(item)
        if provider_id:
            try:
                profile = get_provider_profile(provider_id)
                record = {
                    "id": f"{provider_id}/{model_id or profile.default_model}",
                    "provider": provider_id,
                    "native_model": model_id or profile.default_model,
                    **profile.default_model_config(),
                    "edit_policy": profile.edit_policy_payload(),
                }
                if target_exists:
                    record.setdefault("authority_tier", "B")
                return record
            except Exception:
                pass
        return {
            "id": model_id or "unknown",
            "provider": provider_id or "",
            "native_model": model_id or "",
            "edit_policy": {"small": "patch", "medium": "patch", "large": "replace"},
            "authority_tier": "B",
        }

    def _estimate_edit_bytes(self, request) -> int:
        if request.content is not None:
            return len(request.content.encode("utf-8"))
        return sum(len(item.search.encode("utf-8")) + len(item.replace.encode("utf-8")) for item in request.edits)

    def _safe_rel_path(self, root: Path, rel_path: str, *, allow_lcr: bool) -> Path:
        raw = str(rel_path or "").strip().replace("\\", "/").lstrip("/")
        if not raw:
            raise ValueError("path is required.")
        candidate = (root / raw).resolve()
        if root not in candidate.parents and candidate != root:
            raise ValueError("Path escapes the workspace.")
        rel = candidate.relative_to(root)
        if self._looks_secret(rel):
            raise ValueError("Refusing to preview secret-like file names.")
        if rel.parts and rel.parts[0] == WORKSPACE_STATE_DIRNAME and self._skip_file(rel):
            raise ValueError("This .astrabridge file is intentionally summarized elsewhere and is not exposed as raw preview.")
        if not allow_lcr and rel.parts and rel.parts[0] == WORKSPACE_STATE_DIRNAME:
            raise ValueError("Raw .astrabridge files are not exposed through the file preview.")
        if not candidate.is_file():
            raise ValueError("File does not exist or is not a regular file.")
        return candidate

    def _skip_dir(self, rel: Path) -> bool:
        if not rel.parts:
            return False
        name = rel.name
        if name in SKIP_DIRS:
            return True
        return self._looks_secret(rel)

    def _skip_file(self, rel: Path) -> bool:
        if self._looks_secret(rel):
            return True
        if rel.parts and rel.parts[0] == WORKSPACE_STATE_DIRNAME:
            return True
        return False

    def _looks_secret(self, rel: Path) -> bool:
        text = rel.as_posix().lower()
        return any(part in text for part in SECRET_NAME_PARTS)

    def _file_kind(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in TEXT_EXTENSIONS:
            return "text"
        return "binary"

    def _git_summary(self, root: Path) -> dict[str, Any]:
        branch_result = self._run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
        if not branch_result["ok"]:
            return {"is_repo": False, "branch": "", "changed_files": 0, "added": 0, "deleted": 0, "files": []}
        top_result = self._run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], timeout=5)
        repo_root = Path(str(top_result.get("stdout") or root).strip()).resolve() if top_result["ok"] else root
        status_result = self._run(["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all", "--", "."], timeout=8)
        numstat_result = self._run(["git", "-C", str(root), "diff", "--numstat", "--", "."], timeout=8)
        files = self._parse_git_status(status_result.get("stdout") or "", root=root, repo_root=repo_root)
        added, deleted = self._parse_numstat(numstat_result.get("stdout") or "")
        return {
            "is_repo": True,
            "branch": str(branch_result["stdout"]).strip(),
            "git_root": str(repo_root),
            "changed_files": len(files),
            "added": added,
            "deleted": deleted,
            "files": files,
        }

    def _parse_git_status(self, text: str, *, root: Path | None = None, repo_root: Path | None = None) -> list[dict[str, Any]]:
        files = []
        for line in text.splitlines():
            if not line.strip() or len(line) < 4:
                continue
            status = line[:2].strip() or "modified"
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            path = self._workspace_relative_git_path(path, root=root, repo_root=repo_root)
            rel = Path(path) if path else Path()
            if path and not self._skip_file(rel):
                files.append({"path": path, "status": status})
        return files

    def _workspace_relative_git_path(self, path: str, *, root: Path | None, repo_root: Path | None) -> str:
        normalized = path.replace("\\", "/").strip().strip('"')
        if not normalized or not root or not repo_root:
            return normalized
        try:
            root_rel = root.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return normalized
        if not root_rel or root_rel == ".":
            return normalized
        prefix = f"{root_rel}/"
        if normalized == root_rel:
            return ""
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
        return normalized

    def _synthetic_file_diff(self, root: Path, target: Path) -> str:
        try:
            rel = target.relative_to(root).as_posix()
            if self._file_kind(target) != "text":
                return ""
            stat = target.stat()
            if stat.st_size > MAX_TEXT_BYTES:
                return ""
            content = target.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return ""
        lines = content.splitlines()
        output = [
            f"diff --astrabridge a/{rel} b/{rel}",
            "new file mode 100644",
            "--- /dev/null",
            f"+++ b/{rel}",
            f"@@ -0,0 +1,{len(lines)} @@",
        ]
        output.extend(f"+{line}" for line in lines)
        if content.endswith("\n"):
            output.append("")
        return "\n".join(output)

    def _parse_numstat(self, text: str) -> tuple[int, int]:
        added = 0
        deleted = 0
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                added += int(parts[0]) if parts[0] != "-" else 0
                deleted += int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                continue
        return added, deleted

    def _recent_files(self, root: Path) -> list[dict[str, Any]]:
        candidates: list[tuple[float, str]] = []
        for current, dirs, files in os.walk(root):
            current_path = Path(current)
            rel_dir = current_path.relative_to(root)
            dirs[:] = [name for name in sorted(dirs) if not self._skip_dir(rel_dir / name)]
            for name in files:
                rel = rel_dir / name
                if self._skip_file(rel):
                    continue
                try:
                    candidates.append(((current_path / name).stat().st_mtime, rel.as_posix()))
                except OSError:
                    continue
        candidates.sort(reverse=True)
        return [{"path": path, "status": "recent"} for _, path in candidates[:40]]

    def _run(self, args: list[str], *, timeout: int) -> dict[str, Any]:
        try:
            completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
            return {"ok": completed.returncode == 0, "stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "stdout": "", "stderr": "", "error": str(exc)}

    def _extract_command(self, value: Any) -> str:
        if isinstance(value, dict):
            for key in ("command", "cmd", "launch_command"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
                if isinstance(candidate, list) and candidate:
                    return " ".join(str(part) for part in candidate)
            for item in value.values():
                found = self._extract_command(item)
                if found:
                    return found
        if isinstance(value, list):
            for item in value:
                found = self._extract_command(item)
                if found:
                    return found
        return ""

    def _extract_status(self, value: Any) -> str:
        if isinstance(value, dict):
            status = value.get("status") or value.get("type") or value.get("method")
            if status:
                return str(status)[:80]
        return "event"

