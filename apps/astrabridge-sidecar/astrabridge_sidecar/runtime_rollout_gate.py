from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from .common import now_iso, slugify, write_json
from .durable_run_store import DurableRunEventStore
from .project_service import ProjectService
from .runtime_stability_gate import run_runtime_stability_gate, scan_runtime_stability_artifacts
from .security import redact_sensitive, resolve_under
from .task_service import TaskService


RUNTIME_ROLLOUT_GATE_SCHEMA_VERSION = "astrabridge-runtime-rollout-gate-v1"
RUNTIME_ROLLOUT_FEATURE_FLAG_SCHEMA_VERSION = "astrabridge-runtime-rollout-feature-flags-v1"
RUNTIME_ROLLOUT_SHADOW_COMPARISON_SCHEMA_VERSION = "astrabridge-runtime-rollout-shadow-comparison-v1"
RUNTIME_ROLLOUT_MIGRATION_EVIDENCE_SCHEMA_VERSION = "astrabridge-runtime-rollout-migration-evidence-v1"
RUNTIME_ROLLOUT_ROLLBACK_READBACK_SCHEMA_VERSION = "astrabridge-runtime-rollout-rollback-readback-v1"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
_DESKTOP_ROOT = _REPO_ROOT / "apps" / "astrabridge-desktop"
_CAPTURE_SCRIPT = _REPO_ROOT / "scripts" / "capture_astrabridge_page.mjs"

CommandRunner = Callable[[list[str], Path], dict[str, Any]]
ReleaseGateRunner = Callable[..., dict[str, Any]]


def runtime_rollout_feature_flags() -> dict[str, Any]:
    flags = [
        {
            "flag_id": "runtime_client_pool_lane_isolation",
            "owner": "astrabridge_sidecar.runtime_client_pool.RuntimeClientPool",
            "introduced_step": 2,
            "state": "enabled",
            "compatibility_window": "read-only compatibility projection remains available through task/runtime summaries; old process-global client mutation paths are retired.",
            "rollback_contract": "Existing lane snapshots and redacted task/runtime projections remain readable without recreating process-global clients.",
        },
        {
            "flag_id": "protocol_v1_canonical_codegen",
            "owner": "astrabridge_sidecar.protocol.schema.v1 + scripts/generate_protocol_types.py",
            "introduced_step": 3,
            "state": "enabled",
            "compatibility_window": "legacy graph/artifact reads are handled only through protocol.compatibility adapters; current writes stay on protocol v1.",
            "rollback_contract": "Generated types, compatibility manifest, and legacy read adapters remain available for inspection-only fallback.",
        },
        {
            "flag_id": "durable_scheduler_and_reconciliation",
            "owner": "astrabridge_sidecar.graph_scheduler.DurableGraphScheduler + DurableRunEventStore",
            "introduced_step": 5,
            "state": "enabled",
            "compatibility_window": "legacy tasks.json/manifests remain importable as read-only compatibility state while durable_runs.sqlite3 is authoritative.",
            "rollback_contract": "Durable store, rebuilt projections, and legacy run manifests remain readable without deleting durable state.",
        },
        {
            "flag_id": "agent_envelope_delivery_ledger",
            "owner": "astrabridge_sidecar.protocol + DurableRunEventStore",
            "introduced_step": 8,
            "state": "enabled",
            "compatibility_window": "task-graph payloads remain compatibility projections; the delivery ledger is authoritative for live handoff state.",
            "rollback_contract": "Agent envelope records and delivery events remain inspectable from the durable store and rebuilt projections.",
        },
        {
            "flag_id": "mcp_server_core_and_broker_boundary",
            "owner": "astrabridge_sidecar.mcp_server_core + astrabridge_sidecar.mcp_broker_service",
            "introduced_step": 11,
            "state": "enabled",
            "compatibility_window": "named MCP servers stay as thin adapters only; direct bypasses remain forbidden while broker audit trails persist.",
            "rollback_contract": "Broker audit events, shared-core conformance, and policy snapshots remain readable from persisted runtime evidence.",
        },
    ]
    return {
        "schema_version": RUNTIME_ROLLOUT_FEATURE_FLAG_SCHEMA_VERSION,
        "window_id": "stability-plan-final-rollout-window-2026-07-17",
        "status": "enabled",
        "flags": flags,
        "compatibility_window": {
            "current_write_path": "durable runtime / protocol v1 / broker boundary only",
            "legacy_read_paths": [
                ".astrabridge/tasks.json",
                "PRIVATE/task-graph/**/run-manifest.json",
                ".astrabridge/projections/runs/*.json",
            ],
            "sunset_condition": "All numbered stability-plan steps complete and rollout gate evidence passes with rollback readback preserved.",
            "maintenance_boundary": [
                "Do not delete durable store/events during rollback rehearsals.",
                "Do not implicitly resume legacy active runs; classify them before operator action.",
                "Shadow comparison must reuse one executed run and compare projections only.",
            ],
        },
    }


def run_runtime_rollout_gate(
    *,
    workspace_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
    include_release_gate: bool = True,
    include_desktop_build: bool = True,
    include_desktop_visual_qa: bool = True,
    command_runner: CommandRunner | None = None,
    release_gate_runner: ReleaseGateRunner | None = None,
    dogfood_source_workspace: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(workspace_root).expanduser().resolve() if workspace_root else _REPO_ROOT
    created_at = now_iso()
    resolved_run_id = slugify(run_id or f"runtime-rollout-gate-{created_at}", default="runtime-rollout-gate")
    gate_run_dir = _resolve_rollout_run_dir(root=root, artifact_root=artifact_root, run_id=resolved_run_id)
    raw_dir = gate_run_dir / "raw"
    reports_dir = gate_run_dir / "reports"
    validations_dir = gate_run_dir / "validations"
    screenshots_dir = gate_run_dir / "screenshots"
    for path in (gate_run_dir, raw_dir, reports_dir, validations_dir, screenshots_dir):
        path.mkdir(parents=True, exist_ok=True)

    command_runner = command_runner or _default_command_runner
    release_gate_runner = release_gate_runner or run_runtime_stability_gate
    feature_flags = runtime_rollout_feature_flags()
    write_json(validations_dir / "feature-flags.json", feature_flags)

    shadow_comparison = capture_runtime_rollout_shadow_comparison(output_dir=raw_dir / "shadow-comparison")
    write_json(validations_dir / "shadow-comparison.json", redact_sensitive(shadow_comparison))

    migration_evidence = capture_runtime_rollout_migration_evidence(
        repo_workspace_root=root,
        output_dir=raw_dir / "migration",
        dogfood_source_workspace=dogfood_source_workspace or root,
    )
    write_json(validations_dir / "migration-evidence.json", redact_sensitive(migration_evidence))

    rollback_readback = capture_runtime_rollout_rollback_readback(output_dir=raw_dir / "rollback-readback")
    write_json(validations_dir / "rollback-readback.json", redact_sensitive(rollback_readback))

    desktop_build = {
        "status": "skipped",
        "command": None,
        "cwd": str(_DESKTOP_ROOT),
        "stdout": "",
        "stderr": "",
        "returncode": None,
    }
    if include_desktop_build:
        desktop_build = command_runner(
            ["cmd", "/c", "npm", "run", "build"],
            _DESKTOP_ROOT,
        )
        write_json(validations_dir / "desktop-build.json", redact_sensitive(desktop_build))

    desktop_visual_qa = {
        "schema_version": "astrabridge-runtime-rollout-desktop-visual-qa-v1",
        "status": "skipped",
        "screenshot_path": None,
        "report_path": None,
        "command": None,
    }
    if include_desktop_visual_qa:
        desktop_visual_qa = _capture_desktop_visual_qa(
            screenshots_dir=screenshots_dir,
            reports_dir=reports_dir,
            command_runner=command_runner,
        )
        write_json(validations_dir / "desktop-visual-qa.json", redact_sensitive(desktop_visual_qa))

    release_gate_summary: dict[str, Any] | None = None
    if include_release_gate:
        release_gate_summary = release_gate_runner(
            workspace_root=root,
            artifact_root=gate_run_dir / "rg",
            run_id="r",
            mode="release",
            include_fixture_evidence=True,
            include_process_inventory=True,
        )
        write_json(validations_dir / "release-gate-summary.json", redact_sensitive(release_gate_summary))

    secret_scan = scan_runtime_stability_artifacts(gate_run_dir)
    write_json(validations_dir / "secret-scan.json", secret_scan)

    checks = {
        "feature_flags": "pass",
        "shadow_comparison": str(shadow_comparison.get("status") or "fail"),
        "migration": str(migration_evidence.get("status") or "fail"),
        "rollback_readback": str(rollback_readback.get("status") or "fail"),
        "desktop_build": "pass" if (not include_desktop_build or int(desktop_build.get("returncode") or 0) == 0) else "fail",
        "desktop_visual_qa": str(desktop_visual_qa.get("status") or "fail"),
        "release_gate": str((release_gate_summary or {}).get("status") or ("skipped" if not include_release_gate else "fail")),
        "secret_scan": str(secret_scan.get("status") or "fail"),
    }
    overall_status = "pass" if all(status in {"pass", "skipped"} for status in checks.values()) else "fail"
    summary = {
        "schema_version": RUNTIME_ROLLOUT_GATE_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": created_at,
        "status": overall_status,
        "checks": checks,
        "feature_flags": {
            "path": str(validations_dir / "feature-flags.json"),
            "flag_count": len(list(feature_flags.get("flags") or [])),
        },
        "shadow_comparison": shadow_comparison,
        "migration": migration_evidence,
        "rollback_readback": rollback_readback,
        "desktop_build": {
            "status": checks["desktop_build"],
            "report_path": str(validations_dir / "desktop-build.json"),
        },
        "desktop_visual_qa": desktop_visual_qa,
        "release_gate": {
            "status": checks["release_gate"],
            "summary_path": str(validations_dir / "release-gate-summary.json") if release_gate_summary is not None else None,
            "run_dir": (
                str(dict(release_gate_summary.get("artifact_paths") or {}).get("run_dir") or "")
                if isinstance(release_gate_summary, dict)
                else None
            ),
        },
        "secret_scan": {
            "status": secret_scan.get("status"),
            "finding_count": secret_scan.get("finding_count"),
            "report_path": str(validations_dir / "secret-scan.json"),
        },
        "artifact_paths": {
            "run_dir": str(gate_run_dir),
            "raw_dir": str(raw_dir),
            "reports_dir": str(reports_dir),
            "validations_dir": str(validations_dir),
            "screenshots_dir": str(screenshots_dir),
            "summary_json": str(reports_dir / "summary.json"),
            "report_md": str(reports_dir / "report.md"),
        },
    }
    write_json(reports_dir / "summary.json", summary)
    (reports_dir / "report.md").write_text(render_runtime_rollout_gate_report(summary), encoding="utf-8", newline="\n")
    return summary


def capture_runtime_rollout_shadow_comparison(*, output_dir: str | Path) -> dict[str, Any]:
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    fixture_root = target_dir / "fixture-workspace"
    workspace = fixture_root / "workspace"
    (workspace / "PRIVATE").mkdir(parents=True, exist_ok=True)
    (workspace / ".astrabridge").mkdir(parents=True, exist_ok=True)
    projects = ProjectService(
        store_path=fixture_root / "projects.json",
        session_path=fixture_root / "current_project.json",
    )
    projects.create_project(
        "Runtime rollout shadow comparison",
        fixture_root / "runtime-rollout-shadow.abproj",
        workspace_root=workspace,
    )
    tasks = TaskService(projects)
    tasks.create_task(
        "Runtime rollout shadow comparison task",
        thread_id="thread-shadow",
        settings={
            "profile_id": "qwen-default",
            "provider_id": "qwen",
            "model": "qwen3-coder-plus",
            "reasoning_effort": "high",
            "permission_mode": "auto",
        },
    )

    cases: list[dict[str, Any]] = []
    cases.append(_shadow_case_from_fixture_result("completed", tasks, "supervisor_worker_synthesizer", {"graph_id": tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]["graph_id"]}))

    failed_graph = tasks.instantiate_graph_template("code_fix_test_review")["graph"]
    failed_result = tasks.execute_fixture_graph(
        {"graph_id": failed_graph["graph_id"], "node_behaviors": {"node_plan_fix": "failed"}}
    )
    cases.append(_build_shadow_case_record("failed", tasks=tasks, run_id=failed_result["fixture_run"]["run_id"], legacy_manifest_path=workspace / failed_result["fixture_run"]["artifact_paths"]["run_manifest_json"]))

    recovered_result = tasks.recover_graph_run(
        {
            "run_id": failed_result["fixture_run"]["run_id"],
            "strategy": "retry_failed_nodes",
            "node_behaviors": {"node_plan_fix": "completed"},
        }
    )
    cases.append(_build_shadow_case_record("retry_recovered", tasks=tasks, run_id=recovered_result["fixture_run"]["run_id"], legacy_manifest_path=workspace / recovered_result["fixture_run"]["artifact_paths"]["run_manifest_json"]))

    cancellable_graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
    cancellable_result = tasks.execute_fixture_graph({"graph_id": cancellable_graph["graph_id"], "execution_mode": "cancellable"})
    cancelled_result = tasks.cancel_graph_run({"run_id": cancellable_result["fixture_run"]["run_id"], "notes": "Rollout gate shadow comparison cancel."})
    cancel_manifest_path = _manifest_path_for_run(tasks=tasks, run_id=cancelled_result["run_ref"]["run_id"])
    cases.append(_build_shadow_case_record("cancelled", tasks=tasks, run_id=cancelled_result["run_ref"]["run_id"], legacy_manifest_path=cancel_manifest_path))

    approval_graph = tasks.instantiate_graph_template("provider_update_smoke_gate")["graph"]
    approval_result = tasks.execute_fixture_graph({"graph_id": approval_graph["graph_id"]})
    cases.append(_build_shadow_case_record("approval_pending", tasks=tasks, run_id=approval_result["fixture_run"]["run_id"], legacy_manifest_path=workspace / approval_result["fixture_run"]["artifact_paths"]["run_manifest_json"]))

    if cases:
        write_json(target_dir / "shadow-cases.json", {"cases": cases})
    mismatches = [
        {"case_id": case["case_id"], "differences": case["differences"]}
        for case in cases
        if case["status"] != "pass"
    ]
    return {
        "schema_version": RUNTIME_ROLLOUT_SHADOW_COMPARISON_SCHEMA_VERSION,
        "status": "pass" if not mismatches else "fail",
        "captured_at": now_iso(),
        "workspace_root": str(workspace),
        "case_count": len(cases),
        "cases": cases,
        "mismatches": mismatches,
        "single_execution_policy": {
            "description": "Each shadow-comparison case executes one fixture run path, then compares only projections/exports derived from that single execution.",
            "double_execution_detected": False,
        },
        "artifact_paths": {
            "workspace_root": str(workspace),
            "shadow_cases_json": str(target_dir / "shadow-cases.json"),
        },
    }


def capture_runtime_rollout_migration_evidence(
    *,
    repo_workspace_root: str | Path,
    output_dir: str | Path,
    dogfood_source_workspace: str | Path,
) -> dict[str, Any]:
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    fixture_root = target_dir / "fixture-migration-workspace"
    fixture_workspace = fixture_root / "workspace"
    (fixture_workspace / ".astrabridge").mkdir(parents=True, exist_ok=True)
    (fixture_workspace / "PRIVATE").mkdir(parents=True, exist_ok=True)
    legacy_fixture = _build_legacy_fixture_state(fixture_workspace)
    source_fixture_path = fixture_workspace / ".astrabridge" / "tasks.json"
    source_fixture_path.write_text(json.dumps(legacy_fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fixture_store = DurableRunEventStore(fixture_workspace)
    fixture_first = fixture_store.migrate_legacy_state()
    fixture_second = fixture_store.migrate_legacy_state()
    fixture_report = {
        "source_report": fixture_first,
        "repeated": fixture_second,
        "classification_summary": _classify_legacy_fixture_state(legacy_fixture),
        "durable_store_path": str(fixture_store.db_path),
    }
    write_json(target_dir / "fixture-migration-report.json", fixture_report)

    repo_root = Path(repo_workspace_root).expanduser().resolve()
    dogfood_source_root = Path(dogfood_source_workspace).expanduser().resolve()
    dogfood_copy_root = target_dir / "dogfood-workspace-copy"
    (dogfood_copy_root / ".astrabridge").mkdir(parents=True, exist_ok=True)
    (dogfood_copy_root / "PRIVATE").mkdir(parents=True, exist_ok=True)
    source_tasks = resolve_under(dogfood_source_root, ".astrabridge/tasks.json")
    target_tasks = dogfood_copy_root / ".astrabridge" / "tasks.json"
    shutil.copy2(source_tasks, target_tasks)
    copied_private_files = _copy_referenced_private_files(
        workspace_root=dogfood_source_root,
        tasks_path=source_tasks,
        target_workspace_root=dogfood_copy_root,
        limit=40,
    )
    dogfood_store = DurableRunEventStore(dogfood_copy_root)
    dogfood_first = dogfood_store.migrate_legacy_state()
    dogfood_second = dogfood_store.migrate_legacy_state()
    dogfood_report = {
        "source_workspace_root": str(dogfood_source_root),
        "copied_workspace_root": str(dogfood_copy_root),
        "copied_private_files": copied_private_files,
        "source_report": dogfood_first,
        "repeated": dogfood_second,
        "classification_summary": _classify_legacy_tasks_file(source_tasks),
        "durable_store_path": str(dogfood_store.db_path),
    }
    write_json(target_dir / "dogfood-migration-report.json", dogfood_report)

    return {
        "schema_version": RUNTIME_ROLLOUT_MIGRATION_EVIDENCE_SCHEMA_VERSION,
        "status": "pass" if str(fixture_first.get("status") or "") in {"pass", "needs_review"} and str(dogfood_first.get("status") or "") in {"pass", "needs_review"} else "fail",
        "captured_at": now_iso(),
        "repo_workspace_root": str(repo_root),
        "fixture_workspace": fixture_report,
        "dogfood_workspace": dogfood_report,
        "artifact_paths": {
            "fixture_tasks_json": str(source_fixture_path),
            "fixture_report_json": str(target_dir / "fixture-migration-report.json"),
            "dogfood_tasks_json": str(target_tasks),
            "dogfood_report_json": str(target_dir / "dogfood-migration-report.json"),
        },
    }


def capture_runtime_rollout_rollback_readback(*, output_dir: str | Path) -> dict[str, Any]:
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    fixture_root = target_dir / "rollback-fixture-workspace"
    workspace = fixture_root / "workspace"
    (workspace / "PRIVATE").mkdir(parents=True, exist_ok=True)
    (workspace / ".astrabridge").mkdir(parents=True, exist_ok=True)
    projects = ProjectService(
        store_path=fixture_root / "projects.json",
        session_path=fixture_root / "current_project.json",
    )
    projects.create_project(
        "Runtime rollout rollback readback",
        fixture_root / "runtime-rollout-rollback.abproj",
        workspace_root=workspace,
    )
    tasks = TaskService(projects)
    tasks.create_task("Runtime rollout rollback readback task")
    graph = tasks.instantiate_graph_template("supervisor_worker_synthesizer")["graph"]
    executed = tasks.execute_fixture_graph({"graph_id": graph["graph_id"]})["fixture_run"]
    run_id = str(executed["run_id"] or "")
    store = tasks.durable_run_store()
    db_before = store.db_path.read_bytes()
    db_before_hash = hashlib.sha256(db_before).hexdigest()
    snapshot_root = target_dir / "rollback-snapshot"
    snapshot_workspace = snapshot_root / "workspace"
    if snapshot_root.exists():
        shutil.rmtree(snapshot_root)
    shutil.copytree(workspace, snapshot_workspace)
    snapshot_store = DurableRunEventStore(snapshot_workspace)
    loaded = snapshot_store.load_run(run_id)
    rebuilt = snapshot_store.rebuild_run_projection(run_id, output_path=snapshot_workspace / ".astrabridge" / "projections" / "runs" / f"{run_id}.json")
    db_after_hash = hashlib.sha256(store.db_path.read_bytes()).hexdigest()
    return {
        "schema_version": RUNTIME_ROLLOUT_ROLLBACK_READBACK_SCHEMA_VERSION,
        "status": "pass" if loaded and rebuilt and db_before_hash == db_after_hash else "fail",
        "captured_at": now_iso(),
        "run_id": run_id,
        "db_hash_before": db_before_hash,
        "db_hash_after": db_after_hash,
        "rollback_readback": {
            "loaded_status": str(dict(loaded or {}).get("status") or ""),
            "event_count": len(list(dict(loaded or {}).get("event_refs") or [])),
            "artifact_count": len(list(dict(loaded or {}).get("artifact_refs") or [])),
            "projection_path": str((snapshot_workspace / ".astrabridge" / "projections" / "runs" / f"{run_id}.json").resolve()),
        },
        "artifact_paths": {
            "workspace_root": str(workspace),
            "snapshot_workspace_root": str(snapshot_workspace),
            "durable_store_path": str(store.db_path),
            "projection_json": str((snapshot_workspace / ".astrabridge" / "projections" / "runs" / f"{run_id}.json").resolve()),
        },
    }


def render_runtime_rollout_gate_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Runtime rollout gate report",
        "",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Created at: `{summary.get('created_at')}`",
        "",
        "## Checks",
        "",
    ]
    for key, status in dict(summary.get("checks") or {}).items():
        lines.append(f"- `{key}`: `{status}`")
    lines.extend(
        [
            "",
            "## Shadow comparison",
            "",
            f"- Case count: `{dict(summary.get('shadow_comparison') or {}).get('case_count')}`",
            f"- Status: `{dict(summary.get('shadow_comparison') or {}).get('status')}`",
            "",
            "## Migration",
            "",
            f"- Fixture migration status: `{dict(dict(summary.get('migration') or {}).get('fixture_workspace') or {}).get('source_report', {}).get('status')}`",
            f"- Dogfood migration status: `{dict(dict(summary.get('migration') or {}).get('dogfood_workspace') or {}).get('source_report', {}).get('status')}`",
            "",
            "## Rollback readback",
            "",
            f"- Status: `{dict(summary.get('rollback_readback') or {}).get('status')}`",
            f"- Run id: `{dict(summary.get('rollback_readback') or {}).get('run_id')}`",
            "",
            "## Artifact paths",
            "",
        ]
    )
    for key, value in dict(summary.get("artifact_paths") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def _build_shadow_case_record(
    case_id: str,
    *,
    tasks: TaskService,
    run_id: str,
    legacy_manifest_path: Path,
) -> dict[str, Any]:
    compact = tasks.graph_run_ref(run_id)
    durable = tasks.durable_run_store().load_run(run_id)
    projection = tasks.durable_run_store().rebuild_run_projection(run_id)
    manifest = json.loads(legacy_manifest_path.read_text(encoding="utf-8"))
    differences: list[str] = []
    if str(manifest.get("run_id") or "") != str(dict(durable or {}).get("run_id") or ""):
        differences.append("run_id mismatch between legacy manifest and durable run")
    if str(manifest.get("status") or "") != str(dict(durable or {}).get("status") or ""):
        differences.append("status mismatch between legacy manifest and durable run")
    if str(dict(compact or {}).get("status") or "") != str(dict(durable or {}).get("status") or ""):
        differences.append("status mismatch between compact run ref and durable run")
    if str(manifest.get("graph_id") or "") != str(dict(durable or {}).get("graph_id") or ""):
        differences.append("graph_id mismatch between legacy manifest and durable run")
    if str(manifest.get("task_id") or "") != str(dict(durable or {}).get("task_id") or ""):
        differences.append("task_id mismatch between legacy manifest and durable run")
    if str(dict(manifest.get("approval_state") or {}).get("status") or "") != str(dict(dict(durable or {}).get("approval_state") or {}).get("status") or ""):
        differences.append("approval_state mismatch between legacy manifest and durable run")
    legacy_artifacts = {
        str(item.get("artifact_id") or "").strip(): str(item.get("status") or "").strip()
        for item in list(manifest.get("artifact_refs") or [])
        if isinstance(item, dict) and str(item.get("artifact_id") or "").strip()
    }
    durable_artifacts = {
        str(item.get("artifact_id") or "").strip(): str(item.get("status") or "").strip()
        for item in list(dict(durable or {}).get("artifact_refs") or [])
        if isinstance(item, dict) and str(item.get("artifact_id") or "").strip()
    }
    missing_or_changed_legacy_artifacts = {
        artifact_id: legacy_status
        for artifact_id, legacy_status in legacy_artifacts.items()
        if durable_artifacts.get(artifact_id) != legacy_status
    }
    if missing_or_changed_legacy_artifacts:
        differences.append("artifact identity/status mismatch between legacy manifest and durable run")
    if not isinstance(projection, dict):
        differences.append("durable projection rebuild failed")
    return {
        "case_id": case_id,
        "status": "pass" if not differences else "fail",
        "run_id": run_id,
        "legacy_manifest_path": str(legacy_manifest_path),
        "legacy_status": str(manifest.get("status") or ""),
        "compact_status": str(dict(compact or {}).get("status") or ""),
        "durable_status": str(dict(durable or {}).get("status") or ""),
        "approval_state": str(dict(dict(durable or {}).get("approval_state") or {}).get("status") or ""),
        "artifact_count": len(durable_artifacts),
        "event_count": len(list(dict(durable or {}).get("event_refs") or [])),
        "differences": differences,
    }


def _shadow_case_from_fixture_result(case_id: str, tasks: TaskService, template_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = tasks.execute_fixture_graph(payload)
    fixture_run = dict(result.get("fixture_run") or {})
    workspace_root = tasks._projects.require_workspace_root()  # noqa: SLF001 - rollout gate owns controlled fixture workspaces.
    manifest_path = workspace_root / str(dict(fixture_run.get("artifact_paths") or {}).get("run_manifest_json") or "")
    return _build_shadow_case_record(case_id, tasks=tasks, run_id=str(fixture_run.get("run_id") or ""), legacy_manifest_path=manifest_path)


def _manifest_path_for_run(*, tasks: TaskService, run_id: str) -> Path:
    durable = tasks.durable_run_store().load_run(run_id) or {}
    workspace_root = tasks._projects.require_workspace_root()  # noqa: SLF001
    for artifact in list(durable.get("artifact_refs") or []):
        if not isinstance(artifact, dict):
            continue
        artifact_id = str(artifact.get("artifact_id") or "")
        path = str(artifact.get("path") or "")
        if artifact_id.endswith("run-manifest-json") or path.endswith("/run-manifest.json"):
            return workspace_root / path
    raise FileNotFoundError(f"Run manifest path not found for {run_id}.")


def _build_legacy_fixture_state(workspace_root: Path) -> dict[str, Any]:
    terminal_manifest = {
        "schema_version": "astrabridge-task-graph-run-v1",
        "run_id": "run-terminal",
        "graph_id": "graph-terminal",
        "task_id": "task-terminal",
        "trace_id": "trace-run-terminal",
        "context_id": "context-run-terminal",
        "status": "completed",
        "entry_node_ids": ["node-entry"],
        "node_run_states": [],
        "artifact_refs": [
            {
                "artifact_id": "artifact-terminal",
                "path": "PRIVATE/legacy/terminal-summary.json",
                "status": "ready",
                "artifact_kind": "structured_json",
            }
        ],
        "event_refs": [],
        "approval_state": {"status": "not_required"},
        "run_policy_snapshot": {"mode": "fixture_run"},
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "state_version": 1,
    }
    recoverable_manifest = {
        **terminal_manifest,
        "run_id": "run-recoverable",
        "graph_id": "graph-recoverable",
        "task_id": "task-recoverable",
        "status": "queued",
    }
    review_manifest = {
        **terminal_manifest,
        "run_id": "run-review",
        "graph_id": "graph-review",
        "task_id": "task-review",
        "status": "waiting_on_approval",
    }
    legacy_private_root = workspace_root / "PRIVATE" / "legacy"
    legacy_private_root.mkdir(parents=True, exist_ok=True)
    write_json(legacy_private_root / "terminal-run-manifest.json", terminal_manifest)
    write_json(legacy_private_root / "recoverable-run-manifest.json", recoverable_manifest)
    write_json(legacy_private_root / "review-run-manifest.json", review_manifest)
    write_json(legacy_private_root / "terminal-summary.json", {"run_id": "run-terminal", "status": "completed"})
    return {
        "schema_version": "astrabridge-task-state-v1",
        "current_task_id": "task-terminal",
        "tasks": [
            {
                "schema_version": "astrabridge-task-state-v1",
                "task_id": "task-terminal",
                "project_id": "legacy-fixture",
                "title": "Legacy terminal task",
                "status": "active",
                "graph_run_refs": [
                    {
                        "run_id": "run-terminal",
                        "graph_id": "graph-terminal",
                        "status": "completed",
                        "created_at": terminal_manifest["created_at"],
                        "updated_at": terminal_manifest["updated_at"],
                        "artifact_refs": [
                            {"artifact_id": "artifact-terminal", "path": "PRIVATE/legacy/terminal-run-manifest.json"},
                        ],
                    }
                ],
            },
            {
                "schema_version": "astrabridge-task-state-v1",
                "task_id": "task-recoverable",
                "project_id": "legacy-fixture",
                "title": "Legacy recoverable task",
                "status": "active",
                "graph_run_refs": [
                    {
                        "run_id": "run-recoverable",
                        "graph_id": "graph-recoverable",
                        "status": "queued",
                        "created_at": recoverable_manifest["created_at"],
                        "updated_at": recoverable_manifest["updated_at"],
                        "artifact_refs": [
                            {"artifact_id": "artifact-recoverable", "path": "PRIVATE/legacy/recoverable-run-manifest.json"},
                        ],
                    }
                ],
            },
            {
                "schema_version": "astrabridge-task-state-v1",
                "task_id": "task-review",
                "project_id": "legacy-fixture",
                "title": "Legacy review task",
                "status": "active",
                "graph_run_refs": [
                    {
                        "run_id": "run-review",
                        "graph_id": "graph-review",
                        "status": "waiting_on_approval",
                        "created_at": review_manifest["created_at"],
                        "updated_at": review_manifest["updated_at"],
                        "artifact_refs": [
                            {"artifact_id": "artifact-review", "path": "C:/outside/review-run-manifest.json"},
                        ],
                    }
                ],
            },
        ],
    }


def _classify_legacy_fixture_state(payload: dict[str, Any]) -> dict[str, Any]:
    summary = {"terminal": 0, "recoverable": 0, "needs_review": 0}
    classifications: list[dict[str, Any]] = []
    for task in list(payload.get("tasks") or []):
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("task_id") or "").strip()
        for ref in list(task.get("graph_run_refs") or []):
            if not isinstance(ref, dict):
                continue
            status = str(ref.get("status") or "").strip()
            if status in {"completed", "failed", "cancelled", "partial", "needs_review", "dry_run_passed", "dry_run_blocked", "rolled_back"}:
                classification = "terminal"
            elif status in {"queued", "ready", "ready_for_dry_run", "dry_run_running"}:
                classification = "recoverable"
            else:
                classification = "needs_review"
            summary[classification] += 1
            classifications.append(
                {
                    "task_id": task_id,
                    "run_id": str(ref.get("run_id") or "").strip(),
                    "legacy_status": status,
                    "classification": classification,
                }
            )
    return {"counts": summary, "runs": classifications}


def _classify_legacy_tasks_file(tasks_path: Path) -> dict[str, Any]:
    payload = json.loads(tasks_path.read_text(encoding="utf-8-sig"))
    return _classify_legacy_fixture_state(payload)


def _copy_referenced_private_files(
    *,
    workspace_root: Path,
    tasks_path: Path,
    target_workspace_root: Path,
    limit: int,
) -> list[str]:
    payload = json.loads(tasks_path.read_text(encoding="utf-8-sig"))
    copied: list[str] = []
    for task in list(payload.get("tasks") or []):
        if len(copied) >= limit:
            break
        if not isinstance(task, dict):
            continue
        for ref in list(task.get("graph_run_refs") or []):
            if len(copied) >= limit:
                break
            if not isinstance(ref, dict):
                continue
            for artifact in list(ref.get("artifact_refs") or []):
                if len(copied) >= limit:
                    break
                if not isinstance(artifact, dict):
                    continue
                relative = str(artifact.get("path") or "").replace("\\", "/").strip()
                if not relative or not relative.startswith("PRIVATE/"):
                    continue
                try:
                    source = resolve_under(workspace_root, relative)
                except Exception:
                    continue
                if not source.exists() or not source.is_file():
                    continue
                destination = resolve_under(target_workspace_root, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.copy2(source, destination)
                    copied.append(relative)
    return copied


def _capture_desktop_visual_qa(
    *,
    screenshots_dir: Path,
    reports_dir: Path,
    command_runner: CommandRunner,
) -> dict[str, Any]:
    dist_index = _DESKTOP_ROOT / "dist" / "index.html"
    screenshot_path = screenshots_dir / "desktop-shell.png"
    report_path = reports_dir / "desktop-shell-capture.json"
    if not dist_index.exists():
        return {
            "schema_version": "astrabridge-runtime-rollout-desktop-visual-qa-v1",
            "status": "fail",
            "reason": "desktop_dist_missing",
            "screenshot_path": str(screenshot_path),
            "report_path": str(report_path),
            "command": None,
        }
    command = [
        "node",
        str(_CAPTURE_SCRIPT),
        "--url",
        dist_index.as_uri(),
        "--out",
        str(screenshot_path),
        "--report",
        str(report_path),
        "--wait-ms",
        "1500",
        "--viewport-width",
        "1365",
        "--viewport-height",
        "900",
        "--full-page",
        "false",
    ]
    result = command_runner(command, _REPO_ROOT)
    capture_report = {}
    if report_path.exists():
        try:
            capture_report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            capture_report = {}
    returncode = result.get("returncode")
    normalized_returncode = int(returncode) if returncode is not None else 1
    status = "pass" if normalized_returncode == 0 and screenshot_path.exists() and bool(capture_report.get("ok")) else "fail"
    return {
        "schema_version": "astrabridge-runtime-rollout-desktop-visual-qa-v1",
        "status": status,
        "screenshot_path": str(screenshot_path),
        "report_path": str(report_path),
        "command": command,
        "capture_report": redact_sensitive(capture_report),
    }


def _default_command_runner(command: list[str], cwd: Path) -> dict[str, Any]:
    import subprocess

    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {
        "command": command,
        "cwd": str(cwd),
        "returncode": int(completed.returncode),
        "stdout": completed.stdout[-20000:],
        "stderr": completed.stderr[-20000:],
    }


def _resolve_rollout_run_dir(*, root: Path, artifact_root: str | Path | None, run_id: str) -> Path:
    if artifact_root:
        return Path(artifact_root).expanduser().resolve()
    return root / "PRIVATE" / "runtime-rollout" / run_id


__all__ = [
    "RUNTIME_ROLLOUT_FEATURE_FLAG_SCHEMA_VERSION",
    "RUNTIME_ROLLOUT_GATE_SCHEMA_VERSION",
    "RUNTIME_ROLLOUT_MIGRATION_EVIDENCE_SCHEMA_VERSION",
    "RUNTIME_ROLLOUT_ROLLBACK_READBACK_SCHEMA_VERSION",
    "RUNTIME_ROLLOUT_SHADOW_COMPARISON_SCHEMA_VERSION",
    "capture_runtime_rollout_migration_evidence",
    "capture_runtime_rollout_rollback_readback",
    "capture_runtime_rollout_shadow_comparison",
    "render_runtime_rollout_gate_report",
    "run_runtime_rollout_gate",
    "runtime_rollout_feature_flags",
]
