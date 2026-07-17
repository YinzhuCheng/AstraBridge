from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .common import now_iso, slugify, write_json
from .project_service import ProjectService
from .security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, redact_sensitive
from .task_service import TaskService


RUNTIME_STABILITY_GATE_SCHEMA_VERSION = "astrabridge-runtime-stability-gate-v1"
RUNTIME_STABILITY_SECRET_SCAN_SCHEMA_VERSION = "astrabridge-runtime-stability-secret-scan-v1"
RUNTIME_STABILITY_FIXTURE_EVIDENCE_SCHEMA_VERSION = "astrabridge-runtime-stability-fixture-evidence-v1"
RUNTIME_STABILITY_PROCESS_INVENTORY_SCHEMA_VERSION = "astrabridge-runtime-stability-process-inventory-v1"
DEFAULT_CRITICAL_ITERATIONS = 20

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
_DESKTOP_TAURI_ROOT = _REPO_ROOT / "apps" / "astrabridge-desktop" / "src-tauri"

_TEXT_SUFFIXES = {
    ".json",
    ".jsonl",
    ".log",
    ".md",
    ".ps1",
    ".py",
    ".rs",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}

_SECRET_CONTENT_REGEXES = [
    re.compile(r"Authorization\s*:\s*Bearer\s+(?!\[?REDACTED\]?|<|xxx|example)[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(
        r"\b(api[_-]?key|token|secret|password|cookie|authorization)\b\s*[:=]\s*[\"']?"
        r"(?!\[?REDACTED\]?|<|xxx|example|dummy|fixture|unit|test|not_available|source|status|reason)"
        r"[A-Za-z0-9._~+/=-]{12,}[\"']?",
        re.I,
    ),
]

CommandRunner = Callable[[list[str], Path], dict[str, Any]]
ProcessInventoryProvider = Callable[[Path], dict[str, Any]]


def runtime_stability_gate_suite_specs() -> tuple[dict[str, Any], ...]:
    return (
        {
            "label": "scheduler_recovery_and_idempotency",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_graph_scheduler.DurableGraphSchedulerTests.test_crash_before_provider_dispatch_replays_after_recovery",
                "tests.test_graph_scheduler.DurableGraphSchedulerTests.test_known_external_handle_reattaches_without_restarting_turn",
                "tests.test_graph_scheduler.DurableGraphSchedulerTests.test_ambiguous_non_idempotent_dispatch_becomes_needs_review",
                "tests.test_graph_scheduler.DurableGraphSchedulerTests.test_live_cancel_interrupts_running_turn_and_marks_run_cancelled",
                "tests.test_graph_scheduler.DurableGraphSchedulerTests.test_duplicate_delivery_idempotency_key_does_not_start_target_twice",
            ),
            "covers": (
                "crash_before_dispatch",
                "remote_accept_before_local_commit",
                "ambiguous_external_effect_needs_review",
                "cancel_completion_race",
                "duplicate_handoff_suppression",
            ),
            "fast_iterations": 1,
            "release_iterations": DEFAULT_CRITICAL_ITERATIONS,
            "fast_required_passes": 1,
            "release_required_passes": DEFAULT_CRITICAL_ITERATIONS,
            "internal_passes_per_run": 1,
            "critical": True,
        },
        {
            "label": "terminal_projection_and_stream_recovery",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_turn_aborted_notification_reconciles_as_cancelled_terminal",
                "tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_reconcile_graph_live_started_turns_commits_terminal_output_after_interrupt_timeout",
                "tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_terminal_notification_reconciles_nested_turn_id_with_stale_thread_projection",
                "tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_wait_for_probe_turn_terminal_recovers_after_thread_read_timeout_when_terminal_notification_exists",
                "tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_wait_for_probe_turn_terminal_recovers_when_follow_on_turn_hides_target_turn",
            ),
            "covers": (
                "out_of_order_terminal_events",
                "stream_loss_recovery",
                "terminal_projection_reconciliation",
                "follow_on_turn_visibility_recovery",
                "interrupt_timeout_recovery",
            ),
            "fast_iterations": 1,
            "release_iterations": DEFAULT_CRITICAL_ITERATIONS,
            "fast_required_passes": 1,
            "release_required_passes": DEFAULT_CRITICAL_ITERATIONS,
            "internal_passes_per_run": 1,
            "critical": True,
        },
        {
            "label": "mcp_timeout_cancel_and_policy_fail_closed",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_mcp_server_core.McpServerCoreTests.test_tool_call_timeout_returns_error",
                "tests.test_mcp_server_core.McpServerCoreTests.test_cancel_notification_suppresses_in_flight_response",
                "tests.test_mcp_broker_service.McpBrokerServiceTests.test_broker_denies_node_policy_before_capability_side_effect",
            ),
            "covers": (
                "mcp_timeout",
                "mcp_cancel_notification",
                "mcp_policy_fail_closed",
            ),
            "fast_iterations": 1,
            "release_iterations": DEFAULT_CRITICAL_ITERATIONS,
            "fast_required_passes": 1,
            "release_required_passes": DEFAULT_CRITICAL_ITERATIONS,
            "internal_passes_per_run": 1,
            "critical": True,
        },
        {
            "label": "client_disconnect_and_disk_write_recovery",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_runtime_client_pool.RuntimeClientPoolTests.test_restart_limit_is_bounded_per_lane",
                "tests.test_sidecar_services.AstraBridgeServiceTests.test_write_json_retries_transient_replace_permission_error",
                "tests.test_sidecar_services.AstraBridgeServiceTests.test_write_json_retries_transient_replace_file_not_found",
                "tests.test_sidecar_services.AstraBridgeServiceTests.test_app_server_client_is_not_running_after_reader_disconnect",
                "tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_request_client_retries_one_transport_disconnect",
                "tests.test_sidecar_services.AstraBridgeServiceTests.test_thread_create_recovery_reports_pending_without_starting_a_duplicate",
                "tests.test_sidecar_services.AstraBridgeServiceTests.test_server_send_ignores_client_disconnect_without_writing_a_second_response",
            ),
            "covers": (
                "lane_restart_limit",
                "disk_write_failure_retry",
                "reader_disconnect_recovery",
                "transport_disconnect_retry",
                "duplicate_recovery_start_suppression",
                "ui_sse_disconnect_safety",
            ),
            "fast_iterations": 1,
            "release_iterations": DEFAULT_CRITICAL_ITERATIONS,
            "fast_required_passes": 1,
            "release_required_passes": DEFAULT_CRITICAL_ITERATIONS,
            "internal_passes_per_run": 1,
            "critical": True,
        },
        {
            "label": "provider_contracts_and_redaction_matrix",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_provider_handoff_compatibility.ProviderHandoffCompatibilityTests.test_cross_provider_projection_warning_path_keeps_lane_state_secret_free",
                "tests.test_provider_compatibility_smoke.ProviderCompatibilitySmokeTests.test_runner_records_failed_provider_errors_without_raw_secret",
                "tests.test_provider_compatibility_smoke.ProviderCompatibilitySmokeTests.test_runner_fails_closed_on_provider_model_mismatch",
                "tests.test_provider_model_compatibility_matrix.ProviderModelCompatibilityMatrixTests.test_secret_free_assertion_accepts_usage_tokens_and_evidence_paths",
                "tests.test_provider_model_compatibility_matrix.ProviderModelCompatibilityMatrixTests.test_secret_free_assertion_rejects_secret_like_fields",
                "tests.test_runtime_failure_taxonomy",
            ),
            "covers": (
                "cross_provider_projection_redaction",
                "provider_failure_redaction",
                "provider_model_mismatch_fail_closed",
                "bounded_provider_pair_matrix",
                "failure_taxonomy_projection",
            ),
            "fast_iterations": 1,
            "release_iterations": 1,
            "fast_required_passes": 1,
            "release_required_passes": 1,
            "internal_passes_per_run": 1,
            "critical": False,
        },
        {
            "label": "desktop_forced_exit_restart",
            "kind": "cargo_test",
            "cwd": _DESKTOP_TAURI_ROOT,
            "filter": "supervisor_restarts_after_forced_sidecar_exit",
            "covers": ("sidecar_restart_after_forced_exit",),
            "fast_iterations": 0,
            "release_iterations": DEFAULT_CRITICAL_ITERATIONS,
            "fast_required_passes": 0,
            "release_required_passes": DEFAULT_CRITICAL_ITERATIONS,
            "internal_passes_per_run": 1,
            "critical": True,
        },
        {
            "label": "desktop_circuit_breaker_recovery",
            "kind": "cargo_test",
            "cwd": _DESKTOP_TAURI_ROOT,
            "filter": "supervisor_opens_circuit_breaker_after_repeated_launch_failures",
            "covers": ("sidecar_crash_loop_circuit_breaker",),
            "fast_iterations": 0,
            "release_iterations": DEFAULT_CRITICAL_ITERATIONS,
            "fast_required_passes": 0,
            "release_required_passes": DEFAULT_CRITICAL_ITERATIONS,
            "internal_passes_per_run": 1,
            "critical": True,
        },
        {
            "label": "desktop_unrelated_listener_preserved",
            "kind": "cargo_test",
            "cwd": _DESKTOP_TAURI_ROOT,
            "filter": "supervisor_does_not_kill_unrelated_listener_on_preferred_port",
            "covers": ("unrelated_listener_preserved",),
            "fast_iterations": 0,
            "release_iterations": 1,
            "fast_required_passes": 0,
            "release_required_passes": 1,
            "internal_passes_per_run": 1,
            "critical": False,
        },
        {
            "label": "desktop_shared_sidecar_without_cross_termination",
            "kind": "cargo_test",
            "cwd": _DESKTOP_TAURI_ROOT,
            "filter": "two_supervisors_share_one_valid_sidecar_without_cross_termination",
            "covers": ("shared_sidecar_without_cross_termination",),
            "fast_iterations": 0,
            "release_iterations": 1,
            "fast_required_passes": 0,
            "release_required_passes": 1,
            "internal_passes_per_run": 1,
            "critical": False,
        },
        {
            "label": "desktop_twenty_restart_cycles_no_orphans",
            "kind": "cargo_test",
            "cwd": _DESKTOP_TAURI_ROOT,
            "filter": "twenty_restart_cycles_leave_no_orphan_sidecar_processes",
            "covers": ("host_loops_leave_zero_owned_orphans",),
            "fast_iterations": 0,
            "release_iterations": 1,
            "fast_required_passes": 0,
            "release_required_passes": DEFAULT_CRITICAL_ITERATIONS,
            "internal_passes_per_run": DEFAULT_CRITICAL_ITERATIONS,
            "critical": True,
        },
    )


def run_runtime_stability_gate(
    *,
    workspace_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
    mode: str = "release",
    python_executable: str | None = None,
    cargo_executable: str | None = None,
    include_fixture_evidence: bool = True,
    include_process_inventory: bool = True,
    command_runner: CommandRunner | None = None,
    process_inventory_provider: ProcessInventoryProvider | None = None,
) -> dict[str, Any]:
    resolved_mode = str(mode or "release").strip().lower() or "release"
    if resolved_mode not in {"fast", "release"}:
        raise ValueError("mode must be fast or release.")
    root = Path(workspace_root).expanduser().resolve() if workspace_root else _REPO_ROOT
    created_at = now_iso()
    resolved_run_id = slugify(run_id or f"runtime-stability-gate-{created_at}", default="runtime-stability-gate")
    gate_run_dir = _resolve_gate_run_dir(root=root, artifact_root=artifact_root, run_id=resolved_run_id)
    raw_dir = gate_run_dir / "raw"
    reports_dir = gate_run_dir / "reports"
    validations_dir = gate_run_dir / "validations"
    command_dir = raw_dir / "commands"
    process_dir = raw_dir / "process-inventory"
    fixture_dir = raw_dir / "fixture-evidence"
    for path in (gate_run_dir, raw_dir, reports_dir, validations_dir, command_dir):
        path.mkdir(parents=True, exist_ok=True)

    command_runner = command_runner or _default_command_runner
    process_inventory_provider = process_inventory_provider or _default_process_inventory_provider
    python_cmd = python_executable or sys.executable
    cargo_cmd = cargo_executable or "cargo"
    suites = runtime_stability_gate_suite_specs()

    process_inventory_before: dict[str, Any] | None = None
    process_inventory_after: dict[str, Any] | None = None
    if include_process_inventory:
        process_dir.mkdir(parents=True, exist_ok=True)
        process_inventory_before = process_inventory_provider(process_dir / "before")
        write_json(validations_dir / "process-inventory-before.json", process_inventory_before)

    suite_results: list[dict[str, Any]] = []
    overall_status = "pass"
    for spec in suites:
        iteration_count = int(spec.get("fast_iterations") if resolved_mode == "fast" else spec.get("release_iterations") or 0)
        if iteration_count <= 0:
            continue
        suite_result = _run_suite(
            spec=spec,
            mode=resolved_mode,
            iteration_count=iteration_count,
            python_executable=python_cmd,
            cargo_executable=cargo_cmd,
            command_dir=command_dir,
            command_runner=command_runner,
        )
        suite_results.append(suite_result)
        if suite_result["status"] != "pass":
            overall_status = "fail"

    fixture_evidence: dict[str, Any] | None = None
    if include_fixture_evidence:
        fixture_dir.mkdir(parents=True, exist_ok=True)
        try:
            fixture_evidence = capture_runtime_stability_fixture_evidence(output_dir=fixture_dir)
        except Exception as exc:  # noqa: BLE001 - the gate reports failures as durable data.
            fixture_evidence = {
                "schema_version": RUNTIME_STABILITY_FIXTURE_EVIDENCE_SCHEMA_VERSION,
                "status": "fail",
                "error_type": type(exc).__name__,
                "error": str(redact_sensitive(str(exc)))[:240],
                "artifact_paths": {
                    "output_dir": str(fixture_dir),
                },
            }
            overall_status = "fail"
        write_json(validations_dir / "fixture-evidence.json", redact_sensitive(fixture_evidence))

    if include_process_inventory:
        process_inventory_after = process_inventory_provider(process_dir / "after")
        write_json(validations_dir / "process-inventory-after.json", process_inventory_after)

    secret_scan = scan_runtime_stability_artifacts(gate_run_dir)
    write_json(validations_dir / "secret-scan.json", secret_scan)
    if str(secret_scan.get("status") or "") != "pass":
        overall_status = "fail"

    summary_path = reports_dir / "summary.json"
    report_path = reports_dir / "report.md"
    summary = {
        "schema_version": RUNTIME_STABILITY_GATE_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": created_at,
        "status": overall_status,
        "mode": resolved_mode,
        "suite_count": len(suite_results),
        "critical_suite_count": sum(1 for item in suite_results if item.get("critical")),
        "critical_suite_pass_count": sum(1 for item in suite_results if item.get("critical") and item.get("status") == "pass"),
        "suites": suite_results,
        "fixture_evidence": fixture_evidence,
        "secret_scan": {
            "status": secret_scan.get("status"),
            "finding_count": secret_scan.get("finding_count"),
            "report_path": str(validations_dir / "secret-scan.json"),
        },
        "process_inventories": {
            "before": str(validations_dir / "process-inventory-before.json") if process_inventory_before is not None else None,
            "after": str(validations_dir / "process-inventory-after.json") if process_inventory_after is not None else None,
        },
        "artifact_paths": {
            "run_dir": str(gate_run_dir),
            "raw_dir": str(raw_dir),
            "reports_dir": str(reports_dir),
            "validations_dir": str(validations_dir),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
        },
        "policy": {
            "live_provider_calls": False,
            "preserve_failed_evidence": True,
            "secret_scan_scope": "runtime_stability_artifacts_only",
            "normal_gate_mode": "fast",
            "release_gate_mode": "release",
        },
    }
    write_json(summary_path, summary)
    report_path.write_text(render_runtime_stability_gate_report(summary), encoding="utf-8", newline="\n")
    return summary


def capture_runtime_stability_fixture_evidence(*, output_dir: str | Path) -> dict[str, Any]:
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    fixture_root = target_dir / "fx"
    workspace = fixture_root / "ws"
    (workspace / "PRIVATE").mkdir(parents=True, exist_ok=True)
    (workspace / ".astrabridge").mkdir(parents=True, exist_ok=True)
    projects = ProjectService(
        store_path=fixture_root / "projects.json",
        session_path=fixture_root / "current_project.json",
    )
    projects.create_project(
        "Runtime stability gate fixture",
        fixture_root / "gate.abproj",
        workspace_root=workspace,
    )
    tasks = TaskService(projects)
    tasks.create_task(
        "Runtime stability gate fixture task",
        thread_id="thread-parent",
        settings={
            "profile_id": "qwen-default",
            "provider_id": "qwen",
            "model": "qwen3-coder-plus",
            "reasoning_effort": "high",
            "permission_mode": "auto",
        },
    )

    provider_gate_graph = tasks.instantiate_graph_template("provider_update_smoke_gate")["graph"]
    provider_pending = tasks.execute_fixture_graph({"graph_id": provider_gate_graph["graph_id"]})["fixture_run"]
    provider_approved = tasks.resolve_graph_run_approval(
        {
            "run_id": provider_pending["run_id"],
            "decision": "approve",
            "notes": "Runtime stability gate fixture approval.",
        }
    )
    provider_approved_run = provider_approved["run_ref"]

    recovery_graph = tasks.instantiate_graph_template("fanout_fanin_research")["graph"]
    recovery_running = tasks.execute_fixture_graph(
        {"graph_id": recovery_graph["graph_id"], "execution_mode": "cancellable"}
    )["fixture_run"]
    cancelled = tasks.cancel_graph_run(
        {
            "run_id": recovery_running["run_id"],
            "notes": "Runtime stability gate fixture cancelled before deterministic resume.",
        }
    )
    resumed = tasks.recover_graph_run(
        {
            "run_id": recovery_running["run_id"],
            "strategy": "resume_run",
        }
    )

    copied_artifacts = []
    copied_artifacts.extend(
        _copy_fixture_run_artifacts(
            workspace_root=workspace,
            run_payload=provider_pending,
            target_dir=target_dir / "copied" / "provider-pending",
        )
    )
    copied_artifacts.extend(
        _copy_fixture_run_artifacts(
            workspace_root=workspace,
            run_payload=resumed["fixture_run"],
            target_dir=target_dir / "copied" / "recovery-resumed",
        )
    )
    durable_store_path = _copy_durable_store_snapshot(tasks=tasks, target_dir=target_dir)

    task_view = tasks.task_view(tasks.current_task(), compact_graph_runs=True)
    evidence = {
        "schema_version": RUNTIME_STABILITY_FIXTURE_EVIDENCE_SCHEMA_VERSION,
        "status": "pass",
        "captured_at": now_iso(),
        "workspace_root": str(workspace),
        "provider_gate": {
            "graph_id": provider_gate_graph["graph_id"],
            "pending_run_id": provider_pending["run_id"],
            "approved_run_id": provider_approved_run["run_id"],
            "approved_status": provider_approved_run["status"],
            "approval_state": provider_approved_run.get("approval_state"),
            "timeline_event_count": provider_approved_run.get("event_count"),
        },
        "recovery": {
            "graph_id": recovery_graph["graph_id"],
            "cancelled_run_id": cancelled["run_ref"]["run_id"],
            "cancelled_status": cancelled["run_ref"]["status"],
            "resumed_run_id": resumed["fixture_run"]["run_id"],
            "resumed_status": resumed["fixture_run"]["run_ref"]["status"],
            "recovery_strategy": (((resumed["fixture_run"]["run_ref"] or {}).get("policy_snapshot") or {}).get("recovery") or {}).get("strategy"),
        },
        "artifact_paths": {
            "workspace_root": str(workspace),
            "copied_artifacts": copied_artifacts,
            "durable_store_snapshot": durable_store_path,
            "fixture_summary_json": str(target_dir / "fixture-summary.json"),
            "provider_pending_run_json": str(target_dir / "provider-pending-run.json"),
            "provider_approved_run_json": str(target_dir / "provider-approved-run.json"),
            "cancelled_run_json": str(target_dir / "cancelled-run.json"),
            "resumed_run_json": str(target_dir / "resumed-run.json"),
            "task_view_json": str(target_dir / "task-view.json"),
        },
    }
    write_json(target_dir / "provider-pending-run.json", redact_sensitive(provider_pending))
    write_json(target_dir / "provider-approved-run.json", redact_sensitive(provider_approved_run))
    write_json(target_dir / "cancelled-run.json", redact_sensitive(cancelled["run_ref"]))
    write_json(target_dir / "resumed-run.json", redact_sensitive(resumed["fixture_run"]["run_ref"]))
    write_json(target_dir / "task-view.json", redact_sensitive(task_view))
    write_json(target_dir / "fixture-summary.json", redact_sensitive(evidence))
    return evidence


def scan_runtime_stability_artifacts(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    findings: list[dict[str, Any]] = []
    scanned_files = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        scanned_files += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(
                {
                    "severity": "error",
                    "code": "artifact-read-failed",
                    "path": str(path.relative_to(root)),
                    "line": 0,
                    "message": f"Could not read artifact for secret scan: {type(exc).__name__}",
                    "excerpt": "",
                }
            )
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            excerpt = str(redact_sensitive(line)).strip()[:180]
            if DESKTOP_KEY_PATH_RE.search(line):
                findings.append(
                    {
                        "severity": "error",
                        "code": "desktop-key-path",
                        "path": str(path.relative_to(root)),
                        "line": line_number,
                        "message": "Desktop key-file path leaked into runtime-stability evidence.",
                        "excerpt": excerpt,
                    }
                )
                continue
            secret_match = False
            for pattern in _SECRET_CONTENT_REGEXES:
                if pattern.search(line):
                    findings.append(
                        {
                            "severity": "error",
                            "code": "secret-like",
                            "path": str(path.relative_to(root)),
                            "line": line_number,
                            "message": "Secret-like content found in runtime-stability evidence.",
                            "excerpt": excerpt,
                        }
                    )
                    secret_match = True
                    break
            if secret_match:
                continue
            for match in SECRET_QUERY_RE.finditer(line):
                value = str(match.group(2) or "")
                if not _is_redacted_or_placeholder(value):
                    findings.append(
                        {
                            "severity": "error",
                            "code": "secret-query",
                            "path": str(path.relative_to(root)),
                            "line": line_number,
                            "message": "Secret-like query parameter found in runtime-stability evidence.",
                            "excerpt": excerpt,
                        }
                    )
    return {
        "schema_version": RUNTIME_STABILITY_SECRET_SCAN_SCHEMA_VERSION,
        "status": "pass" if not findings else "fail",
        "scanned_root": str(root),
        "scanned_files": scanned_files,
        "finding_count": len(findings),
        "findings": findings,
    }


def render_runtime_stability_gate_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Runtime Stability Gate",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Created: `{summary.get('created_at')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Mode: `{summary.get('mode')}`",
        f"- Critical suites passed: `{summary.get('critical_suite_pass_count')}` / `{summary.get('critical_suite_count')}`",
        "",
        "## Suite Results",
        "",
    ]
    for suite in list(summary.get("suites") or []):
        lines.extend(
            [
                f"- `{suite.get('label')}` status=`{suite.get('status')}`",
                f"  - covers: `{', '.join(list(suite.get('covers') or []))}`",
                f"  - command: `{_shell_line(list(suite.get('command') or []))}`",
                f"  - iterations: executed=`{suite.get('executed_iterations')}` required_passes=`{suite.get('required_pass_count')}` consecutive_passes=`{suite.get('max_consecutive_passes')}` internal_passes_per_run=`{suite.get('internal_passes_per_run')}`",
            ]
        )
        for iteration in list(suite.get("iterations") or []):
            lines.extend(
                [
                    f"  - iter `{iteration.get('iteration')}` exit=`{iteration.get('exit_code')}` duration_ms=`{iteration.get('duration_ms')}`",
                    f"    - stdout: `{iteration.get('stdout_path')}`",
                    f"    - stderr: `{iteration.get('stderr_path')}`",
                ]
            )
    fixture = dict(summary.get("fixture_evidence") or {})
    if fixture:
        lines.extend(
            [
                "",
                "## Fixture Evidence",
                "",
                f"- Status: `{fixture.get('status')}`",
                f"- Workspace root: `{fixture.get('workspace_root')}`",
                f"- Summary JSON: `{((fixture.get('artifact_paths') or {}).get('fixture_summary_json'))}`",
                f"- Durable store snapshot: `{((fixture.get('artifact_paths') or {}).get('durable_store_snapshot'))}`",
            ]
        )
    secret_scan = dict(summary.get("secret_scan") or {})
    lines.extend(
        [
            "",
            "## Secret Scan",
            "",
            f"- Status: `{secret_scan.get('status')}`",
            f"- Finding count: `{secret_scan.get('finding_count')}`",
            f"- Report: `{secret_scan.get('report_path')}`",
        ]
    )
    process_inventories = dict(summary.get("process_inventories") or {})
    if process_inventories:
        lines.extend(
            [
                "",
                "## Process Inventories",
                "",
                f"- Before: `{process_inventories.get('before')}`",
                f"- After: `{process_inventories.get('after')}`",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _resolve_gate_run_dir(*, root: Path, artifact_root: str | Path | None, run_id: str) -> Path:
    if artifact_root:
        return Path(artifact_root).expanduser().resolve() / run_id
    return root / "PRIVATE" / "runtime-stability" / run_id


def _default_command_runner(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }
    return {
        "exit_code": int(completed.returncode),
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }


def _default_process_inventory_provider(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    commands: list[tuple[str, list[str]]] = []
    if os_name := platform.system().lower():
        if os_name.startswith("win"):
            commands = [
                ("tasklist_csv", ["tasklist", "/fo", "csv", "/nh"]),
                ("netstat_ano", ["netstat", "-ano"]),
            ]
        else:
            commands = [
                ("process_table", ["ps", "-ax", "-o", "pid=,ppid=,comm=,args="]),
                ("listening_sockets", ["sh", "-lc", "ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null || true"]),
            ]
    records: list[dict[str, Any]] = []
    for label, command in commands:
        result = _default_command_runner(command, _REPO_ROOT)
        suffix = ".csv" if label.endswith("_csv") else ".txt"
        stdout_path = output_dir / f"{label}.stdout{suffix}"
        stderr_path = output_dir / f"{label}.stderr.log"
        stdout_path.write_text(result["stdout"], encoding="utf-8", newline="\n")
        stderr_path.write_text(result["stderr"], encoding="utf-8", newline="\n")
        records.append(
            {
                "label": label,
                "command": command,
                "exit_code": result["exit_code"],
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )
    return {
        "schema_version": RUNTIME_STABILITY_PROCESS_INVENTORY_SCHEMA_VERSION,
        "captured_at": now_iso(),
        "platform": platform.platform(),
        "records": records,
    }


def _run_suite(
    *,
    spec: dict[str, Any],
    mode: str,
    iteration_count: int,
    python_executable: str,
    cargo_executable: str,
    command_dir: Path,
    command_runner: CommandRunner,
) -> dict[str, Any]:
    suite_label = str(spec.get("label") or "suite")
    suite_dir = command_dir / suite_label
    suite_dir.mkdir(parents=True, exist_ok=True)
    command = _suite_command(spec=spec, python_executable=python_executable, cargo_executable=cargo_executable)
    cwd = Path(spec.get("cwd") or _REPO_ROOT)
    internal_passes_per_run = int(spec.get("internal_passes_per_run") or 1)
    required_pass_count = int(spec.get("fast_required_passes") if mode == "fast" else spec.get("release_required_passes") or 1)

    iterations: list[dict[str, Any]] = []
    consecutive_passes = 0
    max_consecutive_passes = 0
    status = "pass"
    for iteration in range(1, iteration_count + 1):
        started = time.monotonic()
        result = command_runner(command, cwd)
        duration_ms = int(round((time.monotonic() - started) * 1000))
        stdout_path = suite_dir / f"iteration-{iteration:03d}.stdout.log"
        stderr_path = suite_dir / f"iteration-{iteration:03d}.stderr.log"
        stdout_path.write_text(str(result.get("stdout") or ""), encoding="utf-8", newline="\n")
        stderr_path.write_text(str(result.get("stderr") or ""), encoding="utf-8", newline="\n")
        exit_code = int(result.get("exit_code") or 0)
        if exit_code == 0:
            consecutive_passes += internal_passes_per_run
            max_consecutive_passes = max(max_consecutive_passes, consecutive_passes)
        else:
            consecutive_passes = 0
            status = "fail"
        iterations.append(
            {
                "iteration": iteration,
                "exit_code": exit_code,
                "duration_ms": duration_ms,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )
    if max_consecutive_passes < required_pass_count:
        status = "fail"
    return {
        "label": suite_label,
        "kind": spec.get("kind"),
        "critical": bool(spec.get("critical")),
        "covers": list(spec.get("covers") or []),
        "cwd": str(cwd),
        "command": command,
        "status": status,
        "executed_iterations": iteration_count,
        "required_pass_count": required_pass_count,
        "max_consecutive_passes": max_consecutive_passes,
        "internal_passes_per_run": internal_passes_per_run,
        "iterations": iterations,
    }


def _suite_command(*, spec: dict[str, Any], python_executable: str, cargo_executable: str) -> list[str]:
    kind = str(spec.get("kind") or "").strip()
    if kind == "python_unittest":
        return [python_executable, "-m", "unittest", *[str(item) for item in list(spec.get("targets") or [])]]
    if kind == "cargo_test":
        return [cargo_executable, "test", str(spec.get("filter") or ""), "--", "--exact", "--nocapture"]
    raise ValueError(f"Unsupported runtime stability gate suite kind: {kind}")


def _copy_fixture_run_artifacts(*, workspace_root: Path, run_payload: dict[str, Any], target_dir: Path) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = dict(run_payload.get("artifact_paths") or {})
    copied: list[str] = []
    for key in ("summary_json", "report_md", "compiled_plan_json", "run_manifest_json"):
        relative_path = str(artifact_paths.get(key) or "").strip()
        if not relative_path:
            continue
        source = workspace_root / relative_path
        if not source.exists():
            continue
        target = target_dir / source.name
        shutil.copy2(source, target)
        copied.append(str(target))
    return copied


def _copy_durable_store_snapshot(*, tasks: TaskService, target_dir: Path) -> str | None:
    try:
        store = tasks.durable_run_store()
    except Exception:  # noqa: BLE001 - evidence capture is best-effort.
        return None
    db_path = Path(store.db_path)
    if not db_path.exists():
        return None
    target = target_dir / db_path.name
    shutil.copy2(db_path, target)
    return str(target)


def _is_redacted_or_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    return normalized in {
        "[redacted]",
        "<redacted>",
        "example",
        "dummy",
        "fixture",
        "test",
        "not_available",
    }


def _shell_line(command: list[str]) -> str:
    return " ".join(str(item) for item in command)
