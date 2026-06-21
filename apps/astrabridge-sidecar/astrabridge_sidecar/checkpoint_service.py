from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, now_iso, read_json, slugify, write_json
from .security import SECRET_RE, SecurityError, assert_no_secret_path, redact_sensitive, scan_text_for_secrets


EXCLUDED_DIR_NAMES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "target",
    "coverage",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    ".vite",
}
EXCLUDED_LCR_LOG_NAMES = {
    "approvals.jsonl",
    "runtime_events.jsonl",
}
EXCLUDED_LCR_ASSET_DIR_NAMES = {
    "generated",
    "refs",
    "sliced",
}
MAX_TEXT_SCAN_BYTES = 512 * 1024


class CheckpointService:
    """Project-local save/load checkpoints for AstraBridge.

    Checkpoints are deliberately stored under `.astrabridge/saves` and never create Git
    commits/tags or write official Codex state.
    """

    def __init__(self, project_service) -> None:
        self._projects = project_service

    def list_saves(self) -> dict[str, Any]:
        saves_root = self._saves_root()
        saves: list[dict[str, Any]] = []
        if saves_root.exists():
            for manifest_path in sorted(saves_root.glob("*/manifest.json")):
                try:
                    saves.append(read_json(manifest_path, {}))
                except Exception:
                    continue
        saves.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return {"saves": [self._public_manifest(item) for item in saves], "saves_root": str(saves_root)}

    def create(self, payload: dict[str, Any] | None = None, *, system: bool = False) -> dict[str, Any]:
        payload = dict(payload or {})
        workspace = self._workspace_root()
        project = self._projects.current_project or {}
        thread_id = str(payload.get("thread_id") or project.get("current_thread_id") or "")
        thread_name = str(payload.get("thread_name") or self._thread_name(thread_id) or "Current thread")
        default_description = self._default_description(str(project.get("name") or "Project"), thread_name)
        description = str(payload.get("description") or "").strip() or default_description
        save_id = self._save_id(description)
        save_dir = self._saves_root() / save_id
        save_dir.mkdir(parents=True, exist_ok=False)

        git = self._git_snapshot(save_dir, workspace)
        files, excluded = self._write_workspace_zip(save_dir / "workspace.zip", workspace)
        project_copy = self._copy_project_file(save_dir)
        manifest = {
            "schema_version": "astrabridge-checkpoint-v1",
            "save_id": save_id,
            "created_at": now_iso(),
            "project_id": project.get("project_id"),
            "project_name": project.get("name"),
            "project_file": project.get("project_file"),
            "project_file_snapshot": project_copy,
            "workspace_root": str(workspace),
            "thread_id": thread_id,
            "thread_name": thread_name,
            "provider": payload.get("provider") or "",
            "model": payload.get("model") or "",
            "description": description,
            "default_description": default_description,
            "system": bool(system),
            "workspace": {
                "zip_path": "workspace.zip",
                "file_count": len(files),
                "excluded_count": len(excluded),
                "files": files[:500],
                "excluded": excluded[:200],
            },
            "git": git,
        }
        self._reject_secret_like(manifest)
        write_json(save_dir / "manifest.json", manifest)
        return {"save": self._public_manifest(manifest), "path": str(save_dir)}

    def load(self, payload: dict[str, Any]) -> dict[str, Any]:
        save_id = str(payload.get("save_id") or "").strip()
        if not save_id:
            raise ValueError("save_id is required.")
        save_dir = self._save_dir(save_id)
        manifest = read_json(save_dir / "manifest.json", {})
        if not manifest:
            raise ValueError(f"Save does not exist: {save_id}")
        dirty = self._dirty_state()
        if bool(payload.get("preview")):
            return {"save": self._public_manifest(manifest), "dirty": dirty, "preview": True}
        if dirty.get("dirty") and not bool(payload.get("confirm_dirty")):
            raise ValueError("Workspace has uncommitted or untracked changes. Preview the save and confirm before loading.")

        restore = self.create(
            {
                "thread_id": manifest.get("thread_id"),
                "thread_name": manifest.get("thread_name"),
                "description": f"Pre-load restore point before {save_id}",
                "provider": manifest.get("provider"),
                "model": manifest.get("model"),
            },
            system=True,
        )
        self._restore_workspace_zip(save_dir / "workspace.zip", self._workspace_root())
        project_snapshot = save_dir / str(manifest.get("project_file_snapshot") or "")
        project_file = Path(str((self._projects.current_project or {}).get("project_file") or ""))
        if project_snapshot.is_file() and project_file:
            shutil.copy2(project_snapshot, project_file)
            try:
                reopened = self._projects.open_project(project_file)
            except Exception:
                reopened = self._projects.current_project
        else:
            reopened = self._projects.current_project
        return {
            "loaded": True,
            "save": self._public_manifest(manifest),
            "preload_restore": restore.get("save"),
            "project": reopened,
        }

    def delete(self, save_id: str) -> dict[str, Any]:
        save_dir = self._save_dir(save_id)
        if not save_dir.exists():
            raise ValueError(f"Save does not exist: {save_id}")
        shutil.rmtree(save_dir)
        return {"deleted": save_id}

    def _workspace_root(self) -> Path:
        return self._projects.require_workspace_root().resolve()

    def _saves_root(self) -> Path:
        return self._projects.require_shell_state_root() / "saves"

    def _save_dir(self, save_id: str) -> Path:
        candidate = (self._saves_root() / str(save_id or "").strip()).resolve()
        root = self._saves_root().resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("Save path escapes .astrabridge/saves.")
        return candidate

    def _save_id(self, description: str) -> str:
        stamp = now_iso().replace(":", "").replace(".", "-")
        return slugify(f"{stamp}-{description}", "save")[:120]

    def _default_description(self, project_name: str, thread_name: str) -> str:
        return f"{project_name} / {thread_name} · {now_iso()[:16].replace('T', ' ')}"

    def _thread_name(self, thread_id: str) -> str:
        if not thread_id:
            return ""
        cache = read_json(self._projects.require_shell_state_root() / "thread_cache.json", {})
        entry = (cache.get("by_id") or {}).get(thread_id) or {}
        return str(entry.get("name") or entry.get("displayName") or thread_id)

    def _copy_project_file(self, save_dir: Path) -> str:
        project = self._projects.current_project or {}
        project_file = Path(str(project.get("project_file") or ""))
        if not project_file.is_file():
            return ""
        target = save_dir / "project.abproj"
        shutil.copy2(project_file, target)
        return target.name

    def _git_snapshot(self, save_dir: Path, workspace: Path) -> dict[str, Any]:
        if not (workspace / ".git").exists():
            return {"is_repo": False, "base_commit": "", "status_path": "", "diff_path": "", "untracked": []}
        status = self._git(workspace, ["status", "--porcelain"], required=False)
        diff = self._git(workspace, ["diff", "--binary"], required=False)
        base = self._git(workspace, ["rev-parse", "HEAD"], required=False).strip()
        (save_dir / "git_status.txt").write_text(status, encoding="utf-8")
        (save_dir / "git.diff").write_text(diff, encoding="utf-8")
        return {
            "is_repo": True,
            "base_commit": base,
            "dirty": bool(status.strip()),
            "status_path": "git_status.txt",
            "diff_path": "git.diff",
            "untracked": [line[3:] for line in status.splitlines() if line.startswith("?? ")][:200],
        }

    def _dirty_state(self) -> dict[str, Any]:
        workspace = self._workspace_root()
        if not (workspace / ".git").exists():
            return {"is_repo": False, "dirty": False, "changed_paths": []}
        status = self._git(workspace, ["status", "--porcelain"], required=False)
        changed = [line[3:].strip() for line in status.splitlines() if line.strip()]
        return {"is_repo": True, "dirty": bool(changed), "changed_paths": changed[:200]}

    def _write_workspace_zip(self, target: Path, workspace: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        files: list[dict[str, Any]] = []
        excluded: list[dict[str, str]] = []
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for root, dirnames, filenames in os.walk(workspace):
                root_path = Path(root)
                kept_dirs: list[str] = []
                for dirname in sorted(dirnames):
                    dir_path = root_path / dirname
                    relative = dir_path.relative_to(workspace)
                    reason = self._exclude_reason(relative, dir_path)
                    if reason:
                        excluded.append({"path": relative.as_posix(), "reason": reason})
                    else:
                        kept_dirs.append(dirname)
                dirnames[:] = kept_dirs

                for filename in sorted(filenames):
                    path = root_path / filename
                    relative = path.relative_to(workspace)
                    reason = self._exclude_reason(relative, path)
                    if reason:
                        excluded.append({"path": relative.as_posix(), "reason": reason})
                        continue
                    try:
                        if not path.is_file():
                            continue
                    except OSError:
                        excluded.append({"path": relative.as_posix(), "reason": "Could not inspect file type."})
                        continue
                    try:
                        assert_no_secret_path(path)
                        self._scan_small_text(path)
                    except SecurityError as exc:
                        excluded.append({"path": relative.as_posix(), "reason": str(exc)})
                        continue
                    archive.write(path, relative.as_posix())
                    files.append(
                        {
                            "path": relative.as_posix(),
                            "size": path.stat().st_size,
                            "sha256": self._sha256(path),
                        }
                    )
        return files, excluded

    def _restore_workspace_zip(self, source: Path, workspace: Path) -> None:
        if not source.is_file():
            raise FileNotFoundError(f"Workspace snapshot is missing: {source}")
        with zipfile.ZipFile(source, "r") as archive:
            for member in archive.infolist():
                target = (workspace / member.filename).resolve()
                if target != workspace.resolve() and workspace.resolve() not in target.parents:
                    raise ValueError(f"Snapshot member escapes workspace: {member.filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as reader, target.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)

    def _exclude_reason(self, relative: Path, path: Path) -> str | None:
        parts = [part.lower() for part in relative.parts]
        if len(parts) >= 3 and parts[0] == WORKSPACE_STATE_DIRNAME and parts[1] == "saves":
            return "Excluded AstraBridge checkpoint store."
        if len(parts) >= 3 and parts[0] == WORKSPACE_STATE_DIRNAME and parts[1] == "assets":
            asset_dir = parts[2]
            if asset_dir in EXCLUDED_LCR_ASSET_DIR_NAMES or asset_dir.startswith("sliced_failed"):
                return "Excluded heavy AstraBridge generated/sliced asset artifact directory; asset registry keeps references."
        if parts and parts[0] == WORKSPACE_STATE_DIRNAME and path.is_file() and path.name.startswith(".") and path.name.endswith(".tmp"):
            return "Excluded transient AstraBridge atomic-write temp file."
        if len(parts) == 2 and parts[0] == WORKSPACE_STATE_DIRNAME and parts[1] in EXCLUDED_LCR_LOG_NAMES:
            return "Excluded verbose AstraBridge runtime log; source log remains in project state."
        if parts and parts[0] == WORKSPACE_STATE_DIRNAME and any(part.startswith("venv") or part.endswith("-venv") for part in parts):
            return "Excluded AstraBridge local Python virtual environment."
        if any(part in EXCLUDED_DIR_NAMES for part in parts):
            return "Excluded build, dependency, cache, or VCS directory."
        if path.is_symlink():
            return "Excluded symlink."
        try:
            if path.stat().st_size > 25 * 1024 * 1024:
                return "Excluded file larger than 25MB."
        except OSError:
            return "Could not stat file."
        return None

    def _scan_small_text(self, path: Path) -> None:
        try:
            if path.stat().st_size > MAX_TEXT_SCAN_BYTES:
                return
        except OSError:
            return
        scan_text_for_secrets(path)

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _git(self, cwd: Path, args: list[str], *, required: bool) -> str:
        try:
            return subprocess.check_output(
                ["git", *args],
                cwd=str(cwd),
                text=True,
                encoding="utf-8",
                errors="replace",
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except Exception:
            if required:
                raise
            return ""

    def _reject_secret_like(self, payload: dict[str, Any]) -> None:
        serialized = str(redact_sensitive(payload))
        if SECRET_RE.search(serialized):
            raise SecurityError("Checkpoint metadata cannot contain API keys, tokens, Authorization headers, cookies, or secret-like values.")

    def _public_manifest(self, manifest: dict[str, Any]) -> dict[str, Any]:
        safe = redact_sensitive(dict(manifest or {}))
        workspace = dict(safe.get("workspace") or {})
        if "files" in workspace:
            workspace["files"] = list(workspace.get("files") or [])[:40]
        if "excluded" in workspace:
            workspace["excluded"] = list(workspace.get("excluded") or [])[:40]
        safe["workspace"] = workspace
        return safe

