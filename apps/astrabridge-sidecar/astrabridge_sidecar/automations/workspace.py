from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..common import now_iso


@dataclass(frozen=True)
class AutomationWorkspaceSession:
    automation_id: str
    run_id: str
    mode: str
    execution_root: str
    workspace_root: str
    cleanup_policy: str
    base_branch: str | None
    worktree_path: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "run_id": self.run_id,
            "mode": self.mode,
            "execution_root": self.execution_root,
            "workspace_root": self.workspace_root,
            "cleanup_policy": self.cleanup_policy,
            "base_branch": self.base_branch,
            "worktree_path": self.worktree_path,
            "created_at": self.created_at,
        }


class AutomationWorkspaceManager:
    def __init__(self, project_service) -> None:
        self._projects = project_service

    def prepare_workspace(self, automation: dict[str, Any], run: dict[str, Any]) -> AutomationWorkspaceSession:
        workspace_root = self._projects.require_workspace_root().resolve()
        automation_id = str(automation.get("automation_id") or "").strip()
        run_id = str(run.get("run_id") or "").strip()
        workspace_spec = dict(automation.get("workspace") or {})
        runtime_spec = dict(automation.get("runtime") or {})
        mode = str(workspace_spec.get("mode") or "dedicated_worktree").strip().lower()
        cleanup_policy = str(workspace_spec.get("cleanup_policy") or "keep_on_finding").strip().lower()
        base_branch = str(workspace_spec.get("base_branch") or "").strip() or None

        if mode == "current_workspace":
            self._assert_current_workspace_allowed(workspace_root, runtime_spec)
            return AutomationWorkspaceSession(
                automation_id=automation_id,
                run_id=run_id,
                mode=mode,
                execution_root=str(workspace_root),
                workspace_root=str(workspace_root),
                cleanup_policy=cleanup_policy,
                base_branch=base_branch,
                worktree_path=None,
                created_at=now_iso(),
            )
        if mode != "dedicated_worktree":
            raise ValueError(f"Unsupported automation workspace mode: {mode or '<missing>'}.")
        repo_root = self._git_repo_root(workspace_root)
        if repo_root is None:
            raise ValueError("git_required_for_worktree")
        worktree_root = self._worktree_root(automation, run)
        source_ref = base_branch or "HEAD"
        self._run_git(repo_root, ["worktree", "add", "--detach", str(worktree_root), source_ref])
        return AutomationWorkspaceSession(
            automation_id=automation_id,
            run_id=run_id,
            mode=mode,
            execution_root=str(worktree_root),
            workspace_root=str(workspace_root),
            cleanup_policy=cleanup_policy,
            base_branch=base_branch,
            worktree_path=str(worktree_root),
            created_at=now_iso(),
        )

    def finalize_workspace(
        self,
        session: AutomationWorkspaceSession,
        *,
        signal: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        retained = self._should_retain(session.cleanup_policy, signal=signal, status=status)
        if session.mode != "dedicated_worktree" or not session.worktree_path:
            return {"cleaned": False, "retained": retained, "worktree_path": session.worktree_path}
        if retained:
            return {"cleaned": False, "retained": True, "worktree_path": session.worktree_path}
        worktree_path = Path(session.worktree_path).resolve()
        if worktree_path.exists():
            git_cwd = self._git_repo_root(Path(session.workspace_root).resolve()) or Path(session.workspace_root).resolve()
            self._run_git(git_cwd, ["worktree", "remove", "--force", str(worktree_path)])
        shutil.rmtree(worktree_path, ignore_errors=True)
        return {"cleaned": True, "retained": False, "worktree_path": str(worktree_path)}

    def _assert_current_workspace_allowed(self, workspace_root: Path, runtime_spec: dict[str, Any]) -> None:
        permission_mode = str(runtime_spec.get("permission_mode") or "workspace-write").strip().lower()
        if permission_mode == "read-only":
            return
        repo_root = self._git_repo_root(workspace_root)
        if repo_root is None:
            return
        if self._workspace_is_dirty(repo_root):
            raise ValueError("dirty_workspace_blocks_current_workspace_run")

    def _workspace_is_dirty(self, repo_root: Path) -> bool:
        completed = self._run_git(repo_root, ["status", "--porcelain"], check=False)
        return bool(str(completed.stdout or "").strip())

    def _worktree_root(self, automation: dict[str, Any], run: dict[str, Any]) -> Path:
        workspace_spec = dict(automation.get("workspace") or {})
        configured_root = str(workspace_spec.get("worktree_root") or "").strip()
        if configured_root:
            candidate = Path(configured_root).expanduser().resolve()
        else:
            runtime_root = self._projects.current_runtime_roots()["project_runtime_root"].resolve()
            candidate = runtime_root / "automation-worktrees" / str(automation.get("automation_id") or "automation") / str(
                run.get("run_id") or "run"
            )
        runtime_root = self._projects.current_runtime_roots()["project_runtime_root"].resolve()
        if runtime_root not in candidate.parents and candidate != runtime_root:
            raise ValueError("worktree_root_must_live_under_project_runtime_root")
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    def _should_retain(self, cleanup_policy: str, *, signal: str | None, status: str | None) -> bool:
        normalized_policy = str(cleanup_policy or "").strip().lower()
        normalized_signal = str(signal or "").strip().lower()
        normalized_status = str(status or "").strip().lower()
        if normalized_policy == "manual":
            return True
        if normalized_policy == "keep_on_failure" and normalized_status == "failed":
            return True
        if normalized_policy == "keep_on_finding" and normalized_signal == "finding":
            return True
        if normalized_policy == "delete_on_no_signal":
            return normalized_signal != "no_signal"
        return True

    def _git_repo_root(self, workspace_root: Path) -> Path | None:
        completed = self._run_git(workspace_root, ["rev-parse", "--show-toplevel"], check=False)
        if completed.returncode != 0:
            return None
        candidate = str(completed.stdout or "").strip()
        if not candidate:
            return None
        return Path(candidate).expanduser().resolve()

    def _run_git(self, cwd: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=20,
        )
        if check and completed.returncode != 0:
            stderr = str(completed.stderr or "").strip() or str(completed.stdout or "").strip() or "git command failed"
            raise ValueError(stderr)
        return completed
