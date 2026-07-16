from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from ..common import now_iso
from ..security import redact_sensitive
from ..usage_signal import usage_not_available


UTC = dt.timezone.utc


class AutomationRunner:
    def __init__(
        self,
        project_service,
        *,
        runtime_service: Any | None = None,
        profile_service: Any | None = None,
        runtime_config: Any | None = None,
        agentic_update_service: Any | None = None,
        subprocess_run: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        now_fn: Callable[[], dt.datetime] | None = None,
    ) -> None:
        self._projects = project_service
        self._runtime = runtime_service
        self._profiles = profile_service
        self._runtime_config = runtime_config
        self._agentic_updates = agentic_update_service
        self._subprocess_run = subprocess_run or subprocess.run
        self._now_fn = now_fn or (lambda: dt.datetime.now(UTC))

    def execute(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        self._assert_execution_policy(automation, workspace_session)
        kind = str(automation.get("kind") or "standalone").strip().lower()
        if kind == "standalone":
            return self._execute_standalone(automation, run, workspace_session)
        if kind == "thread":
            return self._execute_thread(automation, run, workspace_session)
        if kind == "agentic_update_check":
            return self._execute_agentic_update_check(automation, run, workspace_session)
        raise ValueError(f"Unsupported automation kind: {kind or '<missing>'}.")

    def _execute_standalone(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        started_at = now_iso()
        profile = self._resolve_profile(dict(automation.get("runtime") or {}))
        try:
            env = self._standalone_env(profile=profile, workspace_session=workspace_session, automation=automation, run=run)
        except RuntimeError as exc:
            raw_message = str(exc)
            secret_missing = raw_message.startswith("runtime_secret_missing:")
            message = self._safe_excerpt(raw_message)
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=started_at,
                finished_at=now_iso(),
                exit_code=1,
                summary="Standalone automation was blocked before provider dispatch.",
                redacted_error="standalone_runtime_key_missing" if secret_missing else (message or "standalone_runtime_not_ready"),
                stdout_excerpt=None,
                stderr_excerpt=None,
            )
        blocked = self._standalone_profile_blocked_result(
            profile=profile,
            automation=automation,
            run=run,
            workspace_session=workspace_session,
            started_at=started_at,
            env=env,
        )
        if blocked is not None:
            return blocked
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

    def _execute_agentic_update_check(
        self,
        automation: dict[str, Any],
        run: dict[str, Any],
        workspace_session: Any,
    ) -> dict[str, Any]:
        started_at = now_iso()
        if self._agentic_updates is None:
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=started_at,
                finished_at=now_iso(),
                exit_code=None,
                summary="Agentic update automation service is not configured.",
                redacted_error="agentic_update_service_not_configured",
                stdout_excerpt=None,
                stderr_excerpt=None,
                signal="unknown",
                usage_signal=usage_not_available(
                    source="automation_agentic_update",
                    reason="agentic_update_service_not_configured",
                    request_kind="automation_agentic_update_check",
                ),
            )
        update_spec = dict(automation.get("agentic_update") or {})
        try:
            self._assert_agentic_update_check_policy(automation, update_spec)
            update_payload = self._agentic_update_payload(update_spec, run=run)
            status = self._agentic_updates.start(update_payload)
            if str(status.get("status") or "").lower() != "success":
                return self._normalized_result(
                    run=run,
                    workspace_session=workspace_session,
                    status="failed",
                    started_at=started_at,
                    finished_at=now_iso(),
                    exit_code=None,
                    summary="Agentic update proposal check failed.",
                    redacted_error=str(status.get("error") or "agentic_update_check_failed"),
                    stdout_excerpt=None,
                    stderr_excerpt=None,
                    signal="unknown",
                    usage_signal=usage_not_available(
                        source="automation_agentic_update",
                        reason="agentic_update_proposal_check_failed",
                        request_kind="automation_agentic_update_check",
                    ),
                )
            result = self._agentic_updates.result(str(status.get("job_id") or ""))
        except Exception as exc:  # noqa: BLE001
            message = self._safe_excerpt(str(exc))
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=started_at,
                finished_at=now_iso(),
                exit_code=None,
                summary="Agentic update proposal check could not complete.",
                redacted_error=message or "agentic_update_check_failed",
                stdout_excerpt=None,
                stderr_excerpt=None,
                signal="unknown",
                usage_signal=usage_not_available(
                    source="automation_agentic_update",
                    reason="agentic_update_proposal_check_exception",
                    request_kind="automation_agentic_update_check",
                ),
            )
        summary = dict(result.get("summary") or {})
        change_count = int(summary.get("change_count") or 0)
        risk_class = str(summary.get("risk_class") or "unknown").strip() or "unknown"
        proposal_status = str(summary.get("proposal_status") or "").strip() or str(
            dict(result.get("diff") or {}).get("status") or "unknown"
        )
        signal = "finding" if change_count > 0 or proposal_status == "changes_detected" else "no_signal"
        artifact_refs = self._agentic_update_artifact_refs(result)
        short_summary = (
            f"Agentic update {summary.get('status') or 'proposal check'} for {result.get('run_id')}: "
            f"{change_count} change(s), risk={risk_class}."
        )
        diff_excerpt = self._agentic_update_diff_excerpt(result)
        return self._normalized_result(
            run=run,
            workspace_session=workspace_session,
            status="completed",
            started_at=started_at,
            finished_at=now_iso(),
            exit_code=0,
            summary=short_summary,
            redacted_error=None,
            stdout_excerpt=str(Path(str(summary.get("artifact_root") or "")).resolve()) if summary.get("artifact_root") else None,
            stderr_excerpt=None,
            signal=signal,
            artifact_refs=artifact_refs,
            diff_excerpt=diff_excerpt,
            usage_signal=usage_not_available(
                source="automation_agentic_update",
                reason="proposal_only_update_check_has_no_provider_usage",
                request_kind="automation_agentic_update_check",
            ),
        )

    def _standalone_env(
        self,
        *,
        profile: dict[str, Any],
        workspace_session: Any,
        automation: dict[str, Any],
        run: dict[str, Any],
        require_secret: bool = True,
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
            runtime_status = self._runtime_config.prepare_profile(profile, require_secret=require_secret)
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

    def _standalone_profile_blocked_result(
        self,
        *,
        profile: dict[str, Any],
        automation: dict[str, Any],
        run: dict[str, Any],
        workspace_session: Any,
        started_at: str,
        env: dict[str, str],
    ) -> dict[str, Any] | None:
        authority = self._standalone_model_authority(env, profile=profile, automation=automation)
        authority_tier = str(authority.get("authority_tier") or "").strip().upper()
        authority_reason = str(authority.get("authority_reason") or "").strip()
        command_execution_status = str(authority.get("command_execution_status") or "").strip().lower()
        command_execution_note = str(authority.get("command_execution_note") or "").strip()
        permission_mode = str(dict(automation.get("runtime") or {}).get("permission_mode") or "workspace-write").strip().lower()

        if command_execution_status in {"partial_no_command_execution", "completed_without_command_execution"}:
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=started_at,
                finished_at=now_iso(),
                exit_code=1,
                summary="Standalone automation was blocked before provider dispatch.",
                redacted_error=command_execution_note or "standalone_profile_command_execution_unverified",
                stdout_excerpt=None,
                stderr_excerpt=None,
            )

        if authority_tier == "A":
            return None
        if authority_tier == "B" and permission_mode == "read-only":
            return None

        if authority_tier == "B":
            return self._normalized_result(
                run=run,
                workspace_session=workspace_session,
                status="failed",
                started_at=started_at,
                finished_at=now_iso(),
                exit_code=1,
                summary="Standalone automation requires a higher-authority model for write-capable execution.",
                redacted_error=authority_reason or "standalone_profile_requires_read_only_review_mode",
                stdout_excerpt=None,
                stderr_excerpt=None,
            )

        return self._normalized_result(
            run=run,
            workspace_session=workspace_session,
            status="failed",
            started_at=started_at,
            finished_at=now_iso(),
            exit_code=1,
            summary="Standalone automation was blocked before provider dispatch.",
            redacted_error=authority_reason or "standalone_profile_unverified_for_shell",
            stdout_excerpt=None,
            stderr_excerpt=None,
        )

    def _standalone_model_authority(
        self,
        env: dict[str, str],
        *,
        profile: dict[str, Any] | None = None,
        automation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        authority_keys = (
            "authority_tier",
            "authority_reason",
            "command_execution_status",
            "command_execution_note",
        )

        def authority_from(record: dict[str, Any]) -> dict[str, Any]:
            return {key: record.get(key) for key in authority_keys if key in record}

        selected_profile = dict(profile or {})
        if any(key in selected_profile for key in authority_keys):
            return authority_from(selected_profile)

        codex_home = Path(str(env.get("CODEX_HOME") or "")).expanduser()
        catalog_path = codex_home / "models" / "astrabridge-models.json"
        if not catalog_path.exists():
            return {}
        try:
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        models = list(dict(payload or {}).get("models") or [])
        if not models:
            return {}
        runtime_spec = dict((automation or {}).get("runtime") or {})
        provider_id = str(selected_profile.get("provider_id") or runtime_spec.get("provider_id") or "").strip().lower()
        model_id = str(
            selected_profile.get("model")
            or runtime_spec.get("model")
            or ""
        ).strip().lower()
        for candidate in models:
            record = dict(candidate or {})
            candidate_provider = str(record.get("provider") or record.get("provider_id") or "").strip().lower()
            candidate_model = str(
                record.get("native_model")
                or record.get("model")
                or record.get("id")
                or ""
            ).strip().lower()
            if (provider_id and candidate_provider == provider_id and model_id and candidate_model == model_id) or (
                model_id and candidate_model in {model_id, f"{provider_id}/{model_id}"}
            ):
                return authority_from(record)
        return {}

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
        signal: str = "unknown",
        artifact_refs: list[str] | None = None,
        diff_excerpt: str | None = None,
        usage_signal: dict[str, Any] | None = None,
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
            "signal": signal,
            "summary": self._safe_excerpt(summary),
            "artifact_refs": list(artifact_refs or []),
            "usage_signal": usage_signal
            or usage_not_available(
                source="automation_runtime",
                reason="standalone_codex_cli_usage_not_reported",
                request_kind="automation_standalone",
            ),
            "redacted_error": self._safe_excerpt(redacted_error) if redacted_error else None,
            "next_retry_at": None,
            "retry_count": int(run.get("retry_count") or 0),
            "stdout_excerpt": self._safe_excerpt(stdout_excerpt) if stdout_excerpt else None,
            "stderr_excerpt": self._safe_excerpt(stderr_excerpt) if stderr_excerpt else None,
            "diff_excerpt": self._safe_excerpt(diff_excerpt) if diff_excerpt else None,
        }

    def _assert_execution_policy(self, automation: dict[str, Any], workspace_session: Any) -> None:
        runtime_spec = dict(automation.get("runtime") or {})
        permission_mode = str(runtime_spec.get("permission_mode") or "workspace-write").strip().lower()
        if permission_mode == "full-access" and runtime_spec.get("dangerous_opt_in") is not True:
            raise ValueError("full-access automation runtime requires dangerous_opt_in=true.")
        if permission_mode == "full-access" and str(getattr(workspace_session, "mode", "") or "") != "dedicated_worktree":
            raise ValueError("full-access automation requires dedicated_worktree isolation.")

    def _assert_agentic_update_check_policy(self, automation: dict[str, Any], update_spec: dict[str, Any]) -> None:
        runtime_spec = dict(automation.get("runtime") or {})
        permission_mode = str(runtime_spec.get("permission_mode") or "").strip().lower()
        if permission_mode != "read-only":
            raise ValueError("agentic_update_check requires read-only automation runtime.")
        contract = dict(update_spec.get("run_contract") or {})
        if str(contract.get("apply_mode") or "proposal_only") not in {"discover_only", "proposal_only"}:
            raise ValueError("agentic_update_check only supports discover_only or proposal_only apply_mode.")
        if contract.get("allow_provider_calls"):
            raise ValueError("agentic_update_check cannot call providers.")
        if contract.get("allow_install"):
            raise ValueError("agentic_update_check cannot install binaries or dependencies.")
        if contract.get("allow_code_changes"):
            raise ValueError("agentic_update_check cannot change code.")
        effects = dict(update_spec.get("allowed_side_effects") or {})
        if any(bool(effects.get(key)) for key in ("apply_changes", "install_binaries", "provider_calls", "code_changes")):
            raise ValueError("agentic_update_check side effects must remain disabled.")

    def _agentic_update_payload(self, update_spec: dict[str, Any], *, run: dict[str, Any]) -> dict[str, Any]:
        max_records = max(1, int(update_spec.get("max_source_records") or 10))
        payload: dict[str, Any] = {
            "run_id": self._agentic_update_run_id(run),
            "run_contract": dict(update_spec.get("run_contract") or {}),
        }
        for key in (
            "fixture_sources",
            "provider_fixture_sources",
            "current_models",
            "complete_provider_snapshot",
            "kernel_fixture_sources",
        ):
            if key in update_spec:
                payload[key] = update_spec.get(key)
        if "provider_sources" in update_spec:
            payload["provider_sources"] = self._limited_provider_sources(update_spec.get("provider_sources"), max_records=max_records)
        if "kernel_source_records" in update_spec:
            payload["kernel_source_records"] = self._limited_records(update_spec.get("kernel_source_records"), max_records=max_records)
        return payload

    def _agentic_update_run_id(self, run: dict[str, Any]) -> str:
        run_id = str(run.get("run_id") or "run").strip()
        safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in run_id).strip("-_")
        return f"automation-{safe or 'run'}"

    def _limited_provider_sources(self, value: Any, *, max_records: int) -> list[dict[str, Any]]:
        providers = [dict(item) for item in list(value or []) if isinstance(item, dict)]
        remaining = max_records
        limited: list[dict[str, Any]] = []
        for provider in providers:
            source_records = [dict(item) for item in list(provider.get("source_records") or []) if isinstance(item, dict)]
            if remaining <= 0:
                provider["source_records"] = []
            else:
                provider["source_records"] = source_records[:remaining]
                remaining -= len(provider["source_records"])
            limited.append(provider)
        return limited

    def _limited_records(self, value: Any, *, max_records: int) -> list[dict[str, Any]]:
        return [dict(item) for item in list(value or []) if isinstance(item, dict)][:max_records]

    def _agentic_update_artifact_refs(self, result: dict[str, Any]) -> list[str]:
        refs: list[str] = []
        artifact_paths = dict(result.get("artifact_paths") or {})
        for value in artifact_paths.values():
            text = str(value or "").strip()
            if text and text not in refs:
                refs.append(text)
        diff_paths = dict(dict(result.get("diff") or {}).get("artifact_paths") or {})
        for value in diff_paths.values():
            text = str(value or "").strip()
            if text and text not in refs:
                refs.append(text)
        return refs

    def _agentic_update_diff_excerpt(self, result: dict[str, Any]) -> str | None:
        diff = dict(result.get("diff") or {})
        changes = list(diff.get("changes") or [])
        if not changes:
            return None
        lines = []
        for change in changes[:5]:
            if not isinstance(change, dict):
                continue
            lines.append(
                f"{change.get('change_type') or 'change'} {change.get('target') or change.get('model_id') or ''} "
                f"risk={change.get('risk_class') or 'unknown'}"
            )
        return "\n".join(line.strip() for line in lines if line.strip()) or None

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
