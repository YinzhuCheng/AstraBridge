from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any, Callable

from .agentic_updates.apply import AGENTIC_UPDATE_APPLY_JOURNAL_SCHEMA_VERSION
from .common import append_jsonl, new_id, now_iso, write_json
from .codex_plugin_install_plan import build_plugin_install_plan
from .security import SecurityError, SECRET_QUERY_RE, redact_sensitive, resolve_under


PLUGIN_INSTALL_EXECUTION_SCHEMA_VERSION = "astrabridge-plugin-install-execution-v1"
PLUGIN_INSTALL_ROLLBACK_MANIFEST_SCHEMA_VERSION = "astrabridge-plugin-install-rollback-manifest-v1"
PLUGIN_INSTALL_TRACK_ID = "plugin_skill_activation"
_SENSITIVE_FIELD_MARKERS = ("api_key", "apikey", "authorization", "cookie", "password", "secret", "token")
_VALUE_SECRET_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._-]{12,}|authorization\s*:|cookie\s*:|ssh-rsa|BEGIN\s+(RSA|OPENSSH|EC|DSA)\s+PRIVATE\s+KEY|sk-[a-z0-9_-]{12,})"
)
_TEXT_CONFIG_SUFFIXES = {".env", ".ini", ".json", ".toml", ".yaml", ".yml"}

CopyTreeFn = Callable[..., Any]
MoveFn = Callable[..., Any]
RemoveTreeFn = Callable[..., Any]


def execute_plugin_install(
    *,
    registry_snapshot: dict[str, Any],
    plugin_id: str,
    source_catalog_id: str | None,
    codex_home: Path,
    workspace_root: Path,
    generated_at: str | None = None,
    copytree_fn: CopyTreeFn = shutil.copytree,
    move_fn: MoveFn = shutil.move,
    rmtree_fn: RemoveTreeFn = shutil.rmtree,
) -> dict[str, Any]:
    execution_id = new_id("plugin-install")
    executed_at = generated_at or now_iso()
    codex_home = codex_home.expanduser().resolve()
    workspace_root = workspace_root.expanduser().resolve()
    report_root = (workspace_root / "PRIVATE" / "demo-runs" / execution_id).resolve()
    report_root.mkdir(parents=True, exist_ok=True)
    events_path = report_root / "events.jsonl"
    plan_path = report_root / "plan.json"
    result_path = report_root / "result.json"
    apply_journal_path = report_root / "apply-journal.json"
    rollback_manifest_path = report_root / "rollback-manifest.json"

    plan = build_plugin_install_plan(
        registry_snapshot=registry_snapshot,
        plugin_id=plugin_id,
        source_catalog_id=source_catalog_id,
        codex_home=codex_home,
        generated_at=executed_at,
    )
    write_json(plan_path, redact_sensitive(plan))

    target_root = _required_under(
        codex_home,
        Path(str(((plan.get("files") or {}).get("target_root") or "")).strip() or codex_home / "plugins" / plugin_id),
    )
    stage_root = _required_under(codex_home, Path("plugin-staging") / execution_id / str(plan.get("plugin", {}).get("plugin_id") or plugin_id))
    snapshot_root = _required_under(codex_home, Path("plugin-rollbacks") / str(plan.get("plugin", {}).get("plugin_id") or plugin_id) / execution_id)
    source_root_text = str(((plan.get("files") or {}).get("source_root") or "")).strip()
    source_root = Path(source_root_text).expanduser().resolve() if source_root_text else None

    result: dict[str, Any] = {
        "schema_version": PLUGIN_INSTALL_EXECUTION_SCHEMA_VERSION,
        "execution_id": execution_id,
        "executed_at": executed_at,
        "status": "failed",
        "action": str(plan.get("action") or "unsupported"),
        "plugin": dict(plan.get("plugin") or {}),
        "plan": plan,
        "artifact_paths": {
            "report_root": str(report_root),
            "plan_path": str(plan_path),
            "events_path": str(events_path),
            "result_path": str(result_path),
            "apply_journal_path": str(apply_journal_path),
            "rollback_manifest_path": str(rollback_manifest_path),
        },
        "source": dict(plan.get("source") or {}),
        "target_root": str(target_root),
        "changes": {
            "written_file_count": 0,
            "target_file_count": 0,
        },
        "rollback_snapshot": {
            **dict(plan.get("rollback_snapshot") or {}),
            "snapshot_root": str(snapshot_root),
            "status": "not_started",
        },
        "warnings": list(plan.get("warnings") or []),
        "errors": [],
        "notes": ["execution_started"],
    }
    _append_event(events_path, {"event": "execution_started", "plugin_id": plugin_id, "action": result["action"]})

    plan_errors = [dict(item) for item in list(plan.get("errors") or []) if isinstance(item, dict)]
    if result["action"] == "noop":
        target_state_before = _plugin_tree_state(target_root)
        source_state = _plugin_tree_state(Path(source_root_text).expanduser().resolve()) if source_root_text else {"exists": False, "files": [], "digest": _tree_digest([])}
        journal = _initialize_plugin_apply_journal(
            execution_id=execution_id,
            executed_at=executed_at,
            plugin=plan.get("plugin") or {},
            source=plan.get("source") or {},
            action="noop",
            source_state=source_state,
            target_state_before=target_state_before,
        )
        result["status"] = "noop"
        result["notes"].append("already_current")
        result["rollback_snapshot"]["status"] = "not_needed"
        result["rollback_manifest"] = _write_plugin_rollback_manifest(
            rollback_manifest_path=rollback_manifest_path,
            execution_id=execution_id,
            executed_at=executed_at,
            plugin=plan.get("plugin") or {},
            action="noop",
            target_root=target_root,
            snapshot_root=snapshot_root,
            target_state_before=target_state_before,
            target_state_after=target_state_before,
            restored_state=target_state_before,
            restore_status="not_needed",
            target_existed_before=target_root.exists(),
        )
        _finalize_plugin_apply_journal(
            journal,
            apply_journal_path,
            terminal_status="committed",
            staged_state=source_state,
            health_verdict="pass",
            changed_paths=[],
            rollback_target=_plugin_rollback_target(
                rollback_manifest_path=rollback_manifest_path,
                snapshot_root=snapshot_root,
                restore_status="not_needed",
                target_state_before=target_state_before,
                target_state_after=target_state_before,
                target_existed_before=target_root.exists(),
            ),
        )
        _append_event(events_path, {"event": "noop", "reason": plan.get("reason")})
        return _write_result(result_path, result)
    if str(plan.get("status") or "") != "ready" or result["action"] not in {"install", "update"}:
        result["errors"] = plan_errors or [_error("plugin-plan-not-ready", f"Plugin plan is not ready for execution: {plan.get('reason') or 'unknown'}", field="reason")]
        result["rollback_snapshot"]["status"] = "not_started"
        _append_event(events_path, {"event": "plan_rejected", "errors": result["errors"]})
        return _write_result(result_path, result)
    if source_root is None or not source_root.exists() or not source_root.is_dir():
        result["errors"] = [_error("plugin-source-missing", "Plugin source root is missing or unreadable.", field="source_root")]
        _append_event(events_path, {"event": "source_missing", "source_root": source_root_text or None})
        return _write_result(result_path, result)

    source_state = _plugin_tree_state(source_root)
    target_state_before = _plugin_tree_state(target_root)
    journal = _initialize_plugin_apply_journal(
        execution_id=execution_id,
        executed_at=executed_at,
        plugin=plan.get("plugin") or {},
        source=plan.get("source") or {},
        action=result["action"],
        source_state=source_state,
        target_state_before=target_state_before,
    )
    _write_plugin_apply_journal(apply_journal_path, journal)
    _append_plugin_apply_stage(
        journal,
        apply_journal_path,
        stage="baseline_captured",
        target_digest=target_state_before["digest"],
        target_exists=target_state_before["exists"],
    )

    try:
        scanned_files = _scan_plugin_source_for_raw_secrets(source_root)
        result["notes"].append(f"secret_scan_files:{len(scanned_files)}")
        _append_plugin_apply_stage(journal, apply_journal_path, stage="source_scanned", file_count=len(scanned_files))
        _append_event(events_path, {"event": "source_scanned", "file_count": len(scanned_files)})
    except SecurityError as exc:
        result["errors"] = [_error("plugin-secret-scan-failed", str(exc), field="source_root")]
        result["notes"].append("secret_scan_failed")
        _append_event(events_path, {"event": "secret_scan_failed", "error": str(exc)})
        return _write_result(result_path, result)

    try:
        if stage_root.exists():
            rmtree_fn(stage_root)
        stage_root.parent.mkdir(parents=True, exist_ok=True)
        copytree_fn(source_root, stage_root)
        staged_files = _list_relative_files(stage_root)
        staged_state = _plugin_tree_state(stage_root)
        result["notes"].append(f"staged_files:{len(staged_files)}")
        _append_plugin_apply_stage(
            journal,
            apply_journal_path,
            stage="staged",
            staged_digest=staged_state["digest"],
            staged_file_count=len(staged_files),
        )
        _append_event(events_path, {"event": "source_staged", "file_count": len(staged_files), "stage_root": str(stage_root)})
    except Exception as exc:  # noqa: BLE001
        result["errors"] = [_error("plugin-stage-copy-failed", f"Failed to stage plugin source: {str(exc)[:300]}", field="source_root")]
        result["notes"].append("stage_copy_failed")
        _append_event(events_path, {"event": "stage_copy_failed", "error": str(exc)[:300]})
        return _write_result(result_path, result)

    if target_root.exists():
        try:
            if snapshot_root.exists():
                rmtree_fn(snapshot_root)
            snapshot_root.parent.mkdir(parents=True, exist_ok=True)
            copytree_fn(target_root, snapshot_root)
            snapshot_files = _list_relative_files(snapshot_root)
            result["rollback_snapshot"] = {
                **result["rollback_snapshot"],
                "status": "captured",
                "captured_file_count": len(snapshot_files),
                "captured_files": snapshot_files[:24],
            }
            _append_plugin_apply_stage(
                journal,
                apply_journal_path,
                stage="rollback_snapshot_captured",
                snapshot_digest=_plugin_tree_state(snapshot_root)["digest"],
                snapshot_file_count=len(snapshot_files),
            )
            _append_event(events_path, {"event": "snapshot_captured", "file_count": len(snapshot_files), "snapshot_root": str(snapshot_root)})
        except Exception as exc:  # noqa: BLE001
            result["errors"] = [_error("plugin-rollback-snapshot-failed", f"Failed to snapshot current plugin state: {str(exc)[:300]}", field="target_root")]
            result["notes"].append("snapshot_failed")
            _append_event(events_path, {"event": "snapshot_failed", "error": str(exc)[:300]})
            return _write_result(result_path, result)
    else:
        result["rollback_snapshot"] = {
            **result["rollback_snapshot"],
            "status": "not_present",
            "captured_file_count": 0,
            "captured_files": [],
        }
        _append_plugin_apply_stage(journal, apply_journal_path, stage="rollback_snapshot_skipped", reason="target_missing")
        _append_event(events_path, {"event": "snapshot_skipped", "reason": "target_missing"})

    target_removed = False
    try:
        target_root.parent.mkdir(parents=True, exist_ok=True)
        if target_root.exists():
            rmtree_fn(target_root)
            target_removed = True
        move_fn(stage_root, target_root)
        target_files = _list_relative_files(target_root)
        target_state_after = _plugin_tree_state(target_root)
        health_verdict = "pass" if target_state_after["digest"] == staged_state["digest"] else "fail"
        if health_verdict != "pass":
            raise RuntimeError("target plugin state digest does not match staged plugin state")
        result["status"] = "applied"
        result["changes"] = {
            "written_file_count": len(target_files),
            "target_file_count": len(target_files),
        }
        result["notes"].append("apply_succeeded")
        result["rollback_manifest"] = _write_plugin_rollback_manifest(
            rollback_manifest_path=rollback_manifest_path,
            execution_id=execution_id,
            executed_at=executed_at,
            plugin=plan.get("plugin") or {},
            action=result["action"],
            target_root=target_root,
            snapshot_root=snapshot_root,
            target_state_before=target_state_before,
            target_state_after=target_state_after,
            restored_state=target_state_after,
            restore_status="available_for_manual_restore",
            target_existed_before=target_state_before["exists"],
        )
        _finalize_plugin_apply_journal(
            journal,
            apply_journal_path,
            terminal_status="committed",
            staged_state=staged_state,
            health_verdict=health_verdict,
            changed_paths=_plugin_changed_paths(codex_home=codex_home, target_root=target_root),
            rollback_target=_plugin_rollback_target(
                rollback_manifest_path=rollback_manifest_path,
                snapshot_root=snapshot_root,
                restore_status="available_for_manual_restore",
                target_state_before=target_state_before,
                target_state_after=target_state_after,
                target_existed_before=target_state_before["exists"],
            ),
        )
        _append_event(events_path, {"event": "apply_succeeded", "file_count": len(target_files), "target_root": str(target_root)})
    except Exception as exc:  # noqa: BLE001
        rollback_status = _restore_from_snapshot(
            target_root=target_root,
            snapshot_root=snapshot_root,
            copytree_fn=copytree_fn,
            rmtree_fn=rmtree_fn,
        )
        restored_state = _plugin_tree_state(target_root)
        result["rollback_snapshot"] = {
            **result["rollback_snapshot"],
            "status": rollback_status,
        }
        result["errors"] = [_error("plugin-apply-failed", f"Failed to write plugin into isolated runtime root: {str(exc)[:300]}", field="target_root")]
        result["notes"].append("apply_failed")
        if target_removed:
            result["notes"].append("target_removed_before_failure")
        result["rollback_manifest"] = _write_plugin_rollback_manifest(
            rollback_manifest_path=rollback_manifest_path,
            execution_id=execution_id,
            executed_at=executed_at,
            plugin=plan.get("plugin") or {},
            action=result["action"],
            target_root=target_root,
            snapshot_root=snapshot_root,
            target_state_before=target_state_before,
            target_state_after=_plugin_tree_state(stage_root if stage_root.exists() else target_root),
            restored_state=restored_state,
            restore_status=rollback_status,
            target_existed_before=target_state_before["exists"],
        )
        _finalize_plugin_apply_journal(
            journal,
            apply_journal_path,
            terminal_status="rolled_back",
            staged_state=staged_state if 'staged_state' in locals() else source_state,
            health_verdict="fail",
            changed_paths=_plugin_changed_paths(codex_home=codex_home, target_root=target_root),
            rollback_target=_plugin_rollback_target(
                rollback_manifest_path=rollback_manifest_path,
                snapshot_root=snapshot_root,
                restore_status=rollback_status,
                target_state_before=target_state_before,
                target_state_after=restored_state,
                target_existed_before=target_state_before["exists"],
            ),
        )
        _append_event(events_path, {"event": "apply_failed", "error": str(exc)[:300], "rollback_status": rollback_status})
        return _write_result(result_path, result)
    finally:
        if stage_root.exists():
            try:
                rmtree_fn(stage_root)
            except Exception:  # noqa: BLE001
                pass

    return _write_result(result_path, result)


def _required_under(root: Path, candidate: Path) -> Path:
    return resolve_under(root, candidate).resolve()


def _write_plugin_apply_journal(path: Path, journal: dict[str, Any]) -> None:
    write_json(path, redact_sensitive(journal))


def _initialize_plugin_apply_journal(
    *,
    execution_id: str,
    executed_at: str,
    plugin: dict[str, Any],
    source: dict[str, Any],
    action: str,
    source_state: dict[str, Any],
    target_state_before: dict[str, Any],
) -> dict[str, Any]:
    plugin_id = str(plugin.get("plugin_id") or "unknown-plugin")
    source_catalog_id = str(plugin.get("source_catalog_id") or source.get("source_catalog_id") or "").strip()
    return {
        "schema_version": AGENTIC_UPDATE_APPLY_JOURNAL_SCHEMA_VERSION,
        "apply_id": execution_id,
        "run_id": execution_id,
        "status": "running",
        "mode": "plugin_skill_activation",
        "started_at": executed_at,
        "completed_at": None,
        "risk_class": "plugin_skill_install",
        "approval": {
            "approved": True,
            "approved_by": "runtime_plugin_install_apply",
            "approved_at": executed_at,
            "approval_note": action,
        },
        "tracks": [
            {
                "track_id": PLUGIN_INSTALL_TRACK_ID,
                "status": "running",
                "source_digest": str(source_state.get("digest") or ""),
                "staged_digest": None,
                "trust_decision": f"plugin_source_catalog:{source_catalog_id or 'unspecified'}",
                "health_verdict": "not_run",
                "changed_paths": [],
                "change_ids": [plugin_id],
                "rollback_target": {
                    "target_state_before_digest": str(target_state_before.get("digest") or ""),
                    "target_existed_before": bool(target_state_before.get("exists")),
                },
                "history": [
                    {
                        "stage": "initialized",
                        "at": executed_at,
                        "plugin_id": plugin_id,
                        "action": action,
                    }
                ],
            }
        ],
    }


def _append_plugin_apply_stage(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    stage: str,
    **details: Any,
) -> None:
    track = _plugin_apply_track(journal)
    history = list(track.get("history") or [])
    entry = {"stage": stage, "at": now_iso()}
    for key, value in details.items():
        if value is not None:
            entry[key] = value
    history.append(entry)
    track["history"] = history
    _write_plugin_apply_journal(journal_path, journal)


def _finalize_plugin_apply_journal(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    terminal_status: str,
    staged_state: dict[str, Any],
    health_verdict: str,
    changed_paths: list[str],
    rollback_target: dict[str, Any],
) -> None:
    journal["status"] = terminal_status
    journal["completed_at"] = now_iso()
    track = _plugin_apply_track(journal)
    track["status"] = terminal_status
    track["staged_digest"] = str(staged_state.get("digest") or "")
    track["health_verdict"] = health_verdict
    track["changed_paths"] = list(changed_paths)
    track["rollback_target"] = dict(rollback_target)
    history = list(track.get("history") or [])
    history.append({"stage": "healthcheck_completed", "at": now_iso(), "verdict": health_verdict})
    history.append({"stage": terminal_status, "at": now_iso()})
    track["history"] = history
    _write_plugin_apply_journal(journal_path, journal)


def _plugin_apply_track(journal: dict[str, Any]) -> dict[str, Any]:
    for track in list(journal.get("tracks") or []):
        if str(track.get("track_id") or "") == PLUGIN_INSTALL_TRACK_ID:
            return track
    raise ValueError("Missing plugin install apply journal track.")


def _write_plugin_rollback_manifest(
    *,
    rollback_manifest_path: Path,
    execution_id: str,
    executed_at: str,
    plugin: dict[str, Any],
    action: str,
    target_root: Path,
    snapshot_root: Path,
    target_state_before: dict[str, Any],
    target_state_after: dict[str, Any],
    restored_state: dict[str, Any],
    restore_status: str,
    target_existed_before: bool,
) -> dict[str, Any]:
    manifest = {
        "schema_version": PLUGIN_INSTALL_ROLLBACK_MANIFEST_SCHEMA_VERSION,
        "execution_id": execution_id,
        "generated_at": executed_at,
        "plugin_id": str(plugin.get("plugin_id") or ""),
        "action": action,
        "target_root": str(target_root),
        "snapshot_root": str(snapshot_root),
        "restore_status": restore_status,
        "target_existed_before": target_existed_before,
        "target_state_before": deepcopy(target_state_before),
        "target_state_after": deepcopy(target_state_after),
        "restored_state": deepcopy(restored_state),
        "steps": [
            {
                "step_id": "plugin_runtime_restore",
                "status": "ready" if restore_status == "available_for_manual_restore" else restore_status,
                "target_root": str(target_root),
                "snapshot_root": str(snapshot_root),
                "target_existed_before": target_existed_before,
                "restore_mode": "restore_snapshot" if target_existed_before else "remove_target_if_no_prior_state",
            }
        ],
    }
    write_json(rollback_manifest_path, redact_sensitive(manifest))
    return redact_sensitive(manifest)


def _plugin_rollback_target(
    *,
    rollback_manifest_path: Path,
    snapshot_root: Path,
    restore_status: str,
    target_state_before: dict[str, Any],
    target_state_after: dict[str, Any],
    target_existed_before: bool,
) -> dict[str, Any]:
    return {
        "rollback_manifest_path": str(rollback_manifest_path),
        "snapshot_root": str(snapshot_root),
        "restore_status": restore_status,
        "target_existed_before": target_existed_before,
        "target_state_before_digest": str(target_state_before.get("digest") or ""),
        "target_state_after_digest": str(target_state_after.get("digest") or ""),
    }


def _plugin_tree_state(root: Path) -> dict[str, Any]:
    files = _list_relative_files(root)
    return {
        "exists": bool(root.exists() and root.is_dir()),
        "root": str(root),
        "files": [{"relative_path": item["relative_path"], "bytes": item["bytes"]} for item in files],
        "digest": _tree_digest(files),
    }


def _tree_digest(files: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for item in files:
        digest.update(str(item.get("relative_path") or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item.get("bytes") or 0).encode("utf-8"))
        digest.update(b"\0")
        path_text = str(item.get("path") or "").strip()
        if path_text:
            try:
                digest.update(Path(path_text).read_bytes())
            except Exception:
                pass
        digest.update(b"\0")
    return digest.hexdigest()


def _plugin_changed_paths(*, codex_home: Path, target_root: Path) -> list[str]:
    paths: list[str] = []
    for item in _list_relative_files(target_root):
        file_path = Path(str(item.get("path") or ""))
        try:
            relative = file_path.resolve().relative_to(codex_home.resolve()).as_posix()
        except Exception:
            relative = str(file_path)
        paths.append(relative)
    return paths


def _write_result(path: Path, result: dict[str, Any]) -> dict[str, Any]:
    write_json(path, redact_sensitive(result))
    return redact_sensitive(result)


def _append_event(path: Path, payload: dict[str, Any]) -> None:
    append_jsonl(path, redact_sensitive({"at": now_iso(), **payload}))


def _list_relative_files(root: Path) -> list[dict[str, Any]]:
    if not root.exists() or not root.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for file_path in sorted(path for path in root.rglob("*") if path.is_file()):
        try:
            entries.append(
                {
                    "relative_path": file_path.relative_to(root).as_posix(),
                    "path": str(file_path),
                    "bytes": file_path.stat().st_size,
                }
            )
        except Exception:
            continue
    return entries


def _restore_from_snapshot(
    *,
    target_root: Path,
    snapshot_root: Path,
    copytree_fn: CopyTreeFn,
    rmtree_fn: RemoveTreeFn,
) -> str:
    if not snapshot_root.exists():
        return "not_present"
    try:
        if target_root.exists():
            rmtree_fn(target_root)
        target_root.parent.mkdir(parents=True, exist_ok=True)
        copytree_fn(snapshot_root, target_root)
        return "restored_after_failure"
    except Exception:  # noqa: BLE001
        return "restore_failed"


def _scan_plugin_source_for_raw_secrets(source_root: Path) -> list[str]:
    scanned: list[str] = []
    for file_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
        if not _looks_like_manifest_or_config(file_path):
            continue
        _scan_manifest_file_for_raw_secrets(file_path)
        scanned.append(str(file_path))
    return scanned


def _looks_like_manifest_or_config(path: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in _TEXT_CONFIG_SUFFIXES:
        return True
    return name in {"plugin.json", "marketplace.json", "config"}


def _scan_manifest_file_for_raw_secrets(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
        if payload is not None:
            _scan_structured_payload(path, payload)
            return
    if suffix == ".toml":
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
        if payload is not None:
            _scan_structured_payload(path, payload)
            return
    _scan_text_manifest(path)


def _scan_structured_payload(path: Path, payload: Any, prefix: tuple[str, ...] = ()) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            field = str(key or "").strip()
            next_prefix = (*prefix, field) if field else prefix
            lowered = field.lower()
            if any(marker in lowered for marker in _SENSITIVE_FIELD_MARKERS) and isinstance(value, str):
                _reject_if_raw_secret(path, ".".join(next_prefix), value)
            _scan_structured_payload(path, value, next_prefix)
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            _scan_structured_payload(path, item, (*prefix, str(index)))
        return
    if isinstance(payload, str):
        _reject_if_secret_value(path, ".".join(prefix) or path.name, payload)


def _scan_text_manifest(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*[:=]\s*(.+?)\s*$", line)
        if match:
            key = str(match.group(1) or "").strip().lower()
            value = str(match.group(2) or "").strip().strip("\"'")
            if any(marker in key for marker in _SENSITIVE_FIELD_MARKERS):
                _reject_if_raw_secret(path, f"{path.name}:{line_no}", value)
            else:
                _reject_if_secret_value(path, f"{path.name}:{line_no}", value)
            continue
        _reject_if_secret_value(path, f"{path.name}:{line_no}", line)


def _reject_if_raw_secret(path: Path, field: str, value: str) -> None:
    normalized = str(value or "").strip()
    if not normalized or _looks_like_placeholder(normalized):
        return
    raise SecurityError(f"Raw secret-like value detected in {path} at {field}.")


def _reject_if_secret_value(path: Path, field: str, value: str) -> None:
    normalized = str(value or "").strip()
    if not normalized or _looks_like_placeholder(normalized):
        return
    if SECRET_QUERY_RE.search(normalized) or _VALUE_SECRET_RE.search(normalized):
        raise SecurityError(f"Raw secret-like value detected in {path} at {field}.")


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    if lowered in {"api_key", "apikey", "token", "secret", "password", "authorization", "cookie"}:
        return True
    if lowered.startswith(("env:", "${", "$", "%")):
        return True
    return any(marker in lowered for marker in ("example", "placeholder", "changeme", "replace-me", "replace_me", "redacted", "dummy"))


def _error(code: str, message: str, *, field: str | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": "astrabridge-plugin-skill-warning-v1",
        "code": code,
        "severity": "error",
        "message": message,
    }
    if field:
        payload["field"] = field
    return payload
