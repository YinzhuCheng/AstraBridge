from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from ..common import now_iso, write_json
from ..security import redact_sensitive
from ..usage_signal import usage_not_available
from .specs import AutomationRun, assert_transition_run_status


AUTOMATION_ARTIFACT_MANIFEST_SCHEMA_VERSION = "astrabridge-automation-artifact-manifest-v1"
UTC = dt.timezone.utc


class AutomationTriageService:
    def __init__(self, project_service, store) -> None:
        self._projects = project_service
        self._store = store

    def finalize_run(
        self,
        automation: dict[str, Any],
        run: dict[str, Any],
        runner_result: dict[str, Any],
        *,
        workspace_session: Any | None = None,
        cleanup_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing_run = dict(run or {})
        result = dict(runner_result or {})
        classification = self._classify(automation, existing_run, result)
        artifact_ref = self._write_manifest(
            automation=automation,
            run=existing_run,
            result=result,
            classification=classification,
            workspace_session=workspace_session,
            cleanup_result=cleanup_result,
        )
        final_run = self._record_final_run(
            automation=automation,
            existing_run=existing_run,
            result=result,
            classification=classification,
            artifact_ref=artifact_ref,
        )
        inbox_item = self._finalize_inbox_item(automation=automation, run=final_run, classification=classification)
        return {
            "run": final_run,
            "inbox_item": inbox_item,
            "artifact_ref": artifact_ref,
            "disposition": classification["disposition"],
            "severity": classification["severity"],
        }

    def update_inbox_item(self, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return self._store.update_inbox_item(item_id, patch)

    def promote_inbox_item(self, item_id: str, promotion_ref: str) -> dict[str, Any]:
        return self._store.promote_inbox_item(item_id, promotion_ref)

    def classify_result(self, automation: dict[str, Any], run: dict[str, Any], runner_result: dict[str, Any]) -> dict[str, Any]:
        return self._classify(dict(automation or {}), dict(run or {}), dict(runner_result or {}))

    def _record_final_run(
        self,
        *,
        automation: dict[str, Any],
        existing_run: dict[str, Any],
        result: dict[str, Any],
        classification: dict[str, Any],
        artifact_ref: str,
    ) -> dict[str, Any]:
        previous_status = str(existing_run.get("status") or "queued").strip().lower()
        next_status = str(classification["status"])
        if previous_status != next_status and not (
            previous_status == "queued" and next_status in {"completed", "needs_review"}
        ):
            assert_transition_run_status(previous_status, next_status)
        artifact_refs = self._artifact_refs(artifact_ref, result.get("artifact_refs"))
        payload = {
            **existing_run,
            **{key: value for key, value in result.items() if key in AutomationRun.__dataclass_fields__},
            "status": next_status,
            "signal": classification["signal"],
            "artifact_refs": artifact_refs,
            "finished_at": result.get("finished_at") if next_status != "running" else None,
            "started_at": result.get("started_at") or existing_run.get("started_at"),
            "summary": str(result.get("summary") or "").strip(),
            "redacted_error": str(result.get("redacted_error") or "").strip() or None,
            "retry_count": int(result.get("retry_count") or existing_run.get("retry_count") or 0),
        }
        retry_count = int(payload.get("retry_count") or 0)
        if next_status == "failed":
            next_retry_at = self._next_retry_at(automation=automation, run=payload)
            payload["next_retry_at"] = next_retry_at
        else:
            payload["next_retry_at"] = None
        if next_status == "running":
            payload["finished_at"] = None
        return self._store.record_run(payload)

    def _finalize_inbox_item(
        self,
        *,
        automation: dict[str, Any],
        run: dict[str, Any],
        classification: dict[str, Any],
    ) -> dict[str, Any] | None:
        disposition = classification["disposition"]
        if not disposition:
            return None
        if run.get("next_retry_at") and disposition == "failure":
            return None
        triage_spec = dict(automation.get("triage") or {})
        notify_on = str(triage_spec.get("notify_on") or "finding").strip().lower()
        archive_no_signal = bool(triage_spec.get("archive_no_signal", True))
        state = "unread"
        if disposition == "no_signal":
            if archive_no_signal:
                state = "archived"
            elif notify_on != "every_run":
                return None
            else:
                state = "reviewed"
        title = self._item_title(automation, disposition)
        item = {
            "item_id": f"inbox-{run['run_id']}",
            "run_id": run["run_id"],
            "automation_id": run["automation_id"],
            "project_id": run["project_id"],
            "state": state,
            "disposition": disposition,
            "severity": classification["severity"],
            "title": title,
            "summary": str(run.get("summary") or "").strip(),
            "artifact_refs": list(run.get("artifact_refs") or []),
            "promotion_ref": None,
        }
        return self._store.upsert_inbox_item(item)

    def _classify(self, automation: dict[str, Any], run: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        status = str(result.get("status") or run.get("status") or "failed").strip().lower()
        signal = str(result.get("signal") or "").strip().lower()
        text = self._classification_text(result)
        if status == "running":
            return {"status": "running", "signal": signal or "unknown", "disposition": None, "severity": None}
        if status == "queued":
            return {"status": "queued", "signal": signal or "unknown", "disposition": None, "severity": None}
        if signal == "finding":
            return {"status": status, "signal": "finding", "disposition": "finding", "severity": "warning"}
        if signal == "no_signal":
            return {"status": status, "signal": "no_signal", "disposition": "no_signal", "severity": "info"}
        if self._approval_required(text):
            return {"status": "needs_review", "signal": "unknown", "disposition": "approval_required", "severity": "warning"}
        if status == "cancelled":
            return {"status": "cancelled", "signal": "unknown", "disposition": "failure", "severity": "warning"}
        if status == "failed":
            return {"status": "failed", "signal": "unknown", "disposition": "failure", "severity": "error"}
        if status == "needs_review" or self._has_finding_signal(automation, text):
            return {"status": "needs_review" if status == "needs_review" else "completed", "signal": "finding", "disposition": "finding", "severity": "warning"}
        if status in {"completed", "skipped"}:
            return {"status": status, "signal": "no_signal", "disposition": "no_signal", "severity": "info"}
        return {"status": "failed", "signal": "unknown", "disposition": "failure", "severity": "error"}

    def _write_manifest(
        self,
        *,
        automation: dict[str, Any],
        run: dict[str, Any],
        result: dict[str, Any],
        classification: dict[str, Any],
        workspace_session: Any | None,
        cleanup_result: dict[str, Any] | None,
    ) -> str:
        artifact_root = self._artifact_root(automation_id=str(run.get("automation_id") or ""), run_id=str(run.get("run_id") or ""))
        manifest_path = artifact_root / "manifest.json"
        max_bytes = int(((automation.get("limits") or {}).get("max_artifact_bytes")) or 2_000_000)
        text_limit = max(160, min(4096, max_bytes // 8))
        workspace = None
        if workspace_session is not None:
            workspace = {
                "mode": getattr(workspace_session, "mode", None),
                "execution_root": getattr(workspace_session, "execution_root", None),
                "workspace_root": getattr(workspace_session, "workspace_root", None),
                "cleanup_policy": getattr(workspace_session, "cleanup_policy", None),
                "worktree_path": getattr(workspace_session, "worktree_path", None),
            }
        manifest = {
            "schema_version": AUTOMATION_ARTIFACT_MANIFEST_SCHEMA_VERSION,
            "automation_id": run.get("automation_id"),
            "run_id": run.get("run_id"),
            "project_id": run.get("project_id"),
            "created_at": now_iso(),
            "status": classification["status"],
            "signal": classification["signal"],
            "disposition": classification["disposition"],
            "severity": classification["severity"],
            "summary": self._truncate(result.get("summary"), text_limit),
            "redacted_error": self._truncate(result.get("redacted_error"), text_limit),
            "stdout_excerpt": self._truncate(result.get("stdout_excerpt"), text_limit),
            "stderr_excerpt": self._truncate(result.get("stderr_excerpt"), text_limit),
            "diff_excerpt": self._truncate(result.get("diff_excerpt"), text_limit),
            "artifact_refs": self._artifact_refs(None, result.get("artifact_refs")),
            "exit_code": result.get("exit_code"),
            "thread_id": result.get("thread_id") or run.get("thread_id"),
            "turn_id": result.get("turn_id"),
            "watchdog": {
                "reason": result.get("watchdog_reason") or run.get("watchdog_reason"),
                "summary": result.get("watchdog_summary") or run.get("watchdog_summary"),
                "recovered_by": result.get("recovered_by") or run.get("recovered_by"),
                "recovered_at": result.get("recovered_at") or run.get("recovered_at"),
            },
            "usage_signal": result.get("usage_signal")
            or usage_not_available(
                source="automation_runtime",
                reason="automation_result_usage_not_reported",
                request_kind="automation_finalization",
            ),
            "workspace": workspace,
            "cleanup": redact_sensitive(cleanup_result or {}),
        }
        manifest = redact_sensitive(manifest)
        serialized = json.dumps(manifest, ensure_ascii=False)
        if len(serialized.encode("utf-8")) > max_bytes:
            overflow_limit = max(80, min(text_limit, max_bytes // 16))
            for field in ("summary", "redacted_error", "stdout_excerpt", "stderr_excerpt", "diff_excerpt"):
                manifest[field] = self._truncate(manifest.get(field), overflow_limit)
        write_json(manifest_path, manifest)
        return str(manifest_path.resolve())

    @staticmethod
    def _artifact_refs(primary: str | None, extra: Any) -> list[str]:
        refs: list[str] = []
        if isinstance(extra, list):
            values = extra
        elif isinstance(extra, tuple):
            values = list(extra)
        elif extra:
            values = [extra]
        else:
            values = []
        for value in [primary, *values]:
            text = str(value or "").strip()
            if text and text not in refs:
                refs.append(text)
        return refs

    def _artifact_root(self, *, automation_id: str, run_id: str) -> Path:
        runtime_root = self._projects.current_runtime_roots()["project_runtime_root"].resolve()
        path = runtime_root / "automations" / automation_id / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _classification_text(self, result: dict[str, Any]) -> str:
        parts = [
            result.get("summary"),
            result.get("redacted_error"),
            result.get("stdout_excerpt"),
            result.get("stderr_excerpt"),
            result.get("diff_excerpt"),
        ]
        return " ".join(str(part or "") for part in parts).strip().lower()

    def _next_retry_at(self, *, automation: dict[str, Any] | None, run: dict[str, Any]) -> str | None:
        current_retry = int(run.get("retry_count") or 0)
        limits = dict((automation or {}).get("limits") or {})
        if not limits:
            return None
        max_retries = int(limits.get("max_retries") or 0)
        if current_retry >= max_retries:
            return None
        backoff_sec = max(1, int(limits.get("retry_backoff_sec") or 300))
        multiplier = max(1, int(limits.get("retry_backoff_multiplier") or 2))
        max_backoff_sec = max(backoff_sec, int(limits.get("retry_backoff_max_sec") or 3600))
        delay = min(max_backoff_sec, backoff_sec * (multiplier ** current_retry))
        anchor = self._parse_iso(str(run.get("finished_at") or run.get("started_at") or now_iso()))
        return (anchor + dt.timedelta(seconds=delay)).astimezone(UTC).isoformat()

    @staticmethod
    def _parse_iso(value: str) -> dt.datetime:
        text = str(value or "").strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _approval_required(text: str) -> bool:
        return "approval_required" in text or "approval required" in text

    @staticmethod
    def _has_finding_signal(automation: dict[str, Any], text: str) -> bool:
        keywords = [str(item).strip().lower() for item in list(((automation.get("triage") or {}).get("finding_keywords")) or []) if str(item).strip()]
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _truncate(value: Any, limit: int) -> str | None:
        text = " ".join(str(redact_sensitive(value or "")).split()).strip()
        if not text:
            return None
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    @staticmethod
    def _item_title(automation: dict[str, Any], disposition: str) -> str:
        name = str(automation.get("name") or automation.get("automation_id") or "automation").strip()
        labels = {
            "finding": "Finding detected",
            "no_signal": "No signal",
            "failure": "Run failed",
            "approval_required": "Approval required",
        }
        return f"{name}: {labels.get(disposition, 'Update')}"
