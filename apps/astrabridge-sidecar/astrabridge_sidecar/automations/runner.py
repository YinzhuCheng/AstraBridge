from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from ..common import now_iso
from ..security import redact_sensitive


UTC = dt.timezone.utc


class AutomationRunner:
    def __init__(
        self,
        project_service,
        *,
        runtime_service: Any | None = None,
        profile_service: Any | None = None,
        runtime_config: Any | None = None,
        subprocess_run: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        now_fn: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._projects = project_service
        self._runtime = runtime_service
        self._profiles = profile_service
        self._runtime_config = runtime_config
        self._subprocess_run = subprocess_run or subprocess.run
        self._now_fn = now_fn or (lambda: dt.datetime.now(UTC))

    def execute(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        self._assert_execution_policy(automation, workspace_session)
        kind = str(automation.get("kind") or "standalone").strip().lower()
        if kind == "standalone":
            return self._execute_standalone(automation, run, workspace_session)
        if kind == "thread":
            return self._execute_thread(automation, run, workspace_session)
        raise ValueError(f"Unsupported automation kind: {kind or '<missing>'}.")

    def _execute_standalone(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        started_at = now_iso()
        profile = self._resolve_profile(dict(automation.get("runtime") or {}))
        env = self._standalone_env(profile=profile, workspace_session=workspace_session, automation=automation, run=run)
        command = self._standalone_command(automation, workspace_session)
        timeout_sec = int(((automation.get("limits") or {}).get("timeout_sec")) or 1800)
        try:
            completed = self._subprocess_run(
                command,
                cwd=str(Path(workspace_session.execution_root).resolve()),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=started_at,
                finished_at=now_iso(),
                exit_code=None,
                summary="Standalone automation timed out.",
                redacted_error=self._safe_excerpt(f"timeout: {exc}"),
                stdout_excerpt=None,
                stderr_excerpt=None,
            )
        stdout = self._safe_excerpt(getattr(completed, "stdout", ""))
        stderr = self._safe_excerpt(getattr(completed, "stderr", ""))
        if int(getattr(completed, "returncode", 1) or 0) == 0:
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="completed",
                started_at=started_at,
                finished_at=now_iso(),
                exit_code=int(completed.returncode),
                summary=stdout or "Standalone automation completed successfully.",
                redacted_error=stderr or None,
                stdout_excerpt=stdout or None,
                stderr_excerpt=stderr or None,
            )
        return self._normalized_result(
            run=run,
            workspace_session=workspace_session,
            status="failed",
            started_at=started_at,
            finished_at=now_iso(),
            exit_code=int(getattr(completed, "returncode", 1) or 1),
            summary=stdout or stderr or "Standalone automation failed.",
            redacted_error=stderr or stdout or "codex_exec_failed",
            stdout_excerpt=stdout or None,
            stderr_excerpt=stderr or None,
        )

    def _execute_thread(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        if self._runtime is None:
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=now_iso(),
                finished_at=now_iso(),
                exit_code=None,
                summary="Thread automation runtime is not configured.",
                redacted_error="runtime_not_configured",
                stdout_excerpt=None,
                stderr_excerpt=None,
            )
        profile = self._resolve_profile(dict(automation.get("runtime") or {}))
        thread_id = str(run.get("thread_id") or "").strip()
        if not thread_id:
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=now_iso(),
                finished_at=now_iso(),
                exit_code=None,
                summary="Thread automation requires a target thread.",
                redacted_error="thread_not_found",
                stdout_excerpt=None,
                stderr_excerpt=None,
            )
        runtime_spec = dict(automation.get("runtime") or {})
        permission_mode = self._runtime_permission_mode(str(runtime_spec.get("permission_mode") or "workspace-write"))
        try:
            response = self._runtime.start_turn(
                profile,
                thread_id=thread_id,
                text=str(automation.get("prompt") or ""),
                attachments=[],
                model=runtime_spec.get("model"),
                effort=runtime_spec.get("effort"),
                permission_mode=permission_mode,
                collaboration_mode=runtime_spec.get("collaboration_mode"),
            )
        except Exception as exc:  # noqa: BLE001
            message = self._safe_excerpt(str(exc))
            error_code = "thread_not_found" if "thread" in message.lower() and "not" in message.lower() else "runtime_not_configured"
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=now_iso(),
                finished_at=now_iso(),
                exit_code=None,
                summary="Thread automation failed to start.",
                redacted_error=error_code if error_code == "thread_not_found" else message or "runtime_not_configured",
                stdout_excerpt=None,
                stderr_excerpt=None,
            )
        turn = dict((response or {}).get("turn") or {})
        effective_thread_id = str((response or {}).get("thread_id") or thread_id)
        return self._normalized_result(
            run={**run, "thread_id": effective_thread_id},
            workspace_session=workspace_session,
            status="running",
            started_at=now_iso(),
            finished_at=None,
            exit_code=None,
            summary="Thread automation turn started.",
            redacted_error=None,
            stdout_excerpt=None,
            stderr_excerpt=None,
            turn_id=str(turn.get("id") or "") or None,
            runtime_profile_id=str(profile.get("profile_id") or "") or None,
        )

    def _standalone_env(
        self,
        *,
        profile: dict[str, Any],
        workspace_session: Any,
        automation: dict[str, Any],
        run: dict[str, Any],
    ) -> dict[str, str]:
        env = self._base_subprocess_env(profile=profile)
        runtime_roots = self._projects.current_runtime_roots()
        codex_home = runtime_roots["codex_home_root"].resolve()
        codex_home.mkdir(parents=True, exist_ok=True)
        env["CODEX_HOME"] = str(codex_home)
        env["ASTRABRIDGE_PROJECT_RUNTIME_ROOT"] = str(runtime_roots["project_runtime_root"].resolve())
        env["ASTRABRIDGE_AUTOMATION_ID"] = str(automation.get("automation_id") or "")
        env["ASTRABRIDGE_AUTOMATION_RUN_ID"] = str(run.get("run_id") or "")
        env["ASTRABRIDGE_AUTOMATION_WORKSPACE_MODE"] = str(getattr(workspace_session, "mode", "") or "")
        if self._runtime_config is not None and profile:
            runtime_status = self._runtime_config.prepare_profile(profile, require_secret=False)
            env["CODEX_HOME"] = str(runtime_status.get("codex_home") or env["CODEX_HOME"])
        return {key: str(value) for key, value in env.items()}

    def _standalone_command(self, automation: dict[str, Any], workspace_session: Any) -> list[str]:
        runtime_spec = dict(automation.get("runtime") or {})
        command = ["codex", "exec", str(automation.get("prompt") or "")]
        permission_mode = str(runtime_spec.get("permission_mode") or "workspace-write").strip().lower()
        if permission_mode == "read-only":
            command.extend(["--sandbox", "read-only"])
        elif permission_mode == "full-access":
            command.extend(["--sandbox", "danger-full-access"])
        else:
            command.extend(["--sandbox", "workspace-write"])
        if runtime_spec.get("model"):
            command.extend(["--model", str(runtime_spec.get("model"))])
        return command

    def _resolve_profile(self, runtime_spec: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(runtime_spec.get("profile_id") or "").strip()
        if self._profiles is not None and profile_id:
            return dict(self._profiles.resolve_runtime_profile(profile_id))
        return {
            "profile_id": profile_id or "openai-compatible",
            "provider_id": str(runtime_spec.get("provider_id") or "openai-compatible"),
            "model": runtime_spec.get("model"),
            "reasoning_effort": runtime_spec.get("effort"),
        }

    def _runtime_permission_mode(self, permission_mode: str) -> str:
        normalized = str(permission_mode or "").strip().lower()
        if normalized == "full-access":
            return "full"
        if normalized == "read-only":
            return "ask"
        return "auto"

    def _normalized_result(
        self,
        *,
        run: dict[str, Any],
        workspace_session: Any,
        status: str,
        started_at: str | None,
        finished_at: str | None,
        exit_code: int | None,
        summary: str,
        redacted_error: str | None,
        stdout_excerpt: str | None,
        stderr_excerpt: str | None,
        turn_id: str | None = None,
        runtime_profile_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "run_id": str(run.get("run_id") or ""),
            "automation_id": str(run.get("automation_id") or ""),
            "project_id": str(run.get("project_id") or ""),
            "trigger": str(run.get("trigger") or "manual"),
            "status": status,
            "due_at": str(run.get("due_at") or now_iso()),
            "started_at": started_at,
            "finished_at": finished_at,
            "thread_id": str(run.get("thread_id") or "") or None,
            "turn_id": turn_id,
            "worktree_path": str(getattr(workspace_session, "worktree_path", "") or "") or None,
            "runtime_profile_id": runtime_profile_id,
            "exit_code": exit_code,
            "signal": "unknown",
            "summary": self._safe_excerpt(summary),
            "artifact_refs": [],
            "redacted_error": self._safe_excerpt(redacted_error) if redacted_error else None,
            "next_retry_at": None,
            "retry_count": int(run.get("retry_count") or 0),
            "stdout_excerpt": self._safe_excerpt(stdout_excerpt) if stdout_excerpt else None,
            "stderr_excerpt": self._safe_excerpt(stderr_excerpt) if stderr_excerpt else None,
        }

    def _assert_execution_policy(self, automation: dict[str, Any], workspace_session: Any) -> None:
        runtime_spec = dict(automation.get("runtime") or {})
        permission_mode = str(runtime_spec.get("permission_mode") or "workspace-write").strip().lower()
        if permission_mode == "full-access" and runtime_spec.get("dangerous_opt_in") is not True:
            raise ValueError("full-access automation runtime requires dangerous_opt_in=true.")
        if permission_mode == "full-access" and str(getattr(workspace_session, "mode", "") or "") != "dedicated_worktree":
            raise ValueError("full-access automation requires dedicated_worktree isolation.")

    def _base_subprocess_env(self, *, profile: dict[str, Any]) -> dict[str, str]:
        allowed_exact = {
            "APPDATA",
            "COMSPEC",
            "HOME",
            "HOMEDRIVE",
            "HOMEPATH",
            "LOCALAPPDATA",
            "NUMBER_OF_PROCESSORS",
            "OS",
            "PATH",
            "PATHEXT",
            "PROCESSOR_ARCHITECTURE",
            "PROCESSOR_IDENTIFIER",
            "PROCESSOR_LEVEL",
            "PROCESSOR_REVISION",
            "PROGRAMDATA",
            "SYSTEMDRIVE",
            "SYSTEMROOT",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "USERNAME",
            "WINDIR",
        }
        selected_env_key = str(profile.get("env_key") or "").strip().upper()
        env: dict[str, str] = {}
        for key, value in os.environ.items():
            upper = str(key or "").upper()
            if upper in allowed_exact or upper.startswith("ASTRABRIDGE_"):
                env[key] = str(value)
                continue
            if selected_env_key and upper == selected_env_key:
                env[key] = str(value)
        return env

    def _safe_excerpt(self, value: Any, *, limit: int = 600) -> str:
        redacted = redact_sensitive(str(value or ""))
        text = " ".join(str(redacted or "").split())
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."
