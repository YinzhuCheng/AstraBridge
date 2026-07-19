from __future__ import annotations

from contextlib import contextmanager
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from .common import now_iso, slugify, write_json
from .project_service import ProjectService
from .security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, redact_sensitive
from .task_service import TaskService


RUNTIME_STABILITY_GATE_SCHEMA_VERSION = "astrabridge-runtime-stability-gate-v1"
RUNTIME_STABILITY_FAULT_MATRIX_SCHEMA_VERSION = "astrabridge-runtime-stability-fault-matrix-v1"
RUNTIME_STABILITY_LONG_HORIZON_BUNDLE_SCHEMA_VERSION = "astrabridge-runtime-stability-long-horizon-bundle-v1"
RUNTIME_STABILITY_INJECTED_CHAOS_DRILLS_SCHEMA_VERSION = "astrabridge-runtime-stability-injected-chaos-drills-v1"
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
            "label": "automation_clock_shift_and_scheduler_recovery",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_automation_scheduler.AutomationSchedulerTests.test_daily_schedule_and_next_wake_up_use_timezone",
                "tests.test_automation_scheduler.AutomationSchedulerTests.test_missed_run_policies_skip_or_queue_once",
                "tests.test_automation_scheduler.AutomationSchedulerTests.test_stale_running_run_is_recovered_and_not_reclaimed_until_cleared",
            ),
            "covers": (
                "clock_shift_schedule_recovery",
                "missed_run_policy_reconciliation",
                "watchdog_stale_run_recovery",
            ),
            "fast_iterations": 1,
            "release_iterations": 1,
            "fast_required_passes": 1,
            "release_required_passes": 1,
            "internal_passes_per_run": 1,
            "critical": False,
        },
        {
            "label": "durable_store_damage_and_legacy_recovery",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_durable_run_store.DurableRunStoreTests.test_initialize_blocks_damaged_store_and_preserves_backup",
                "tests.test_durable_run_store.DurableRunStoreTests.test_empty_migration_is_deterministic_and_does_not_create_legacy_files",
                "tests.test_durable_run_store.DurableRunStoreTests.test_legacy_migration_preserves_source_redacts_secrets_and_marks_active_or_external_runs",
            ),
            "covers": (
                "sqlite_damage_guard",
                "legacy_readback_determinism",
                "cross_version_needs_review_projection",
            ),
            "fast_iterations": 1,
            "release_iterations": 1,
            "fast_required_passes": 1,
            "release_required_passes": 1,
            "internal_passes_per_run": 1,
            "critical": False,
        },
        {
            "label": "observability_fault_visibility_and_support_bundle",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_runtime_observability.RuntimeObservabilityTests.test_build_runtime_observability_summary_computes_trace_metrics_and_host_diagnostics",
                "tests.test_runtime_observability.RuntimeObservabilityTests.test_runtime_support_bundle_secret_scan_flags_secret_like_content",
                "tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_supervisor_status_includes_observability_summary_from_runtime_events",
            ),
            "covers": (
                "multimodal_no_visible_final_answer_visibility",
                "downgraded_authority_projection_visibility",
                "support_bundle_redaction_scan",
            ),
            "fast_iterations": 1,
            "release_iterations": 1,
            "fast_required_passes": 1,
            "release_required_passes": 1,
            "internal_passes_per_run": 1,
            "critical": False,
        },
        {
            "label": "windows_update_interruption_rehearsal",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_release_identity.ReleaseIdentityTests.test_run_windows_update_rehearsal_records_clean_install_update_and_rollback",
            ),
            "covers": (
                "windows_update_interruption_rehearsal",
                "rollback_readback_after_update",
            ),
            "fast_iterations": 1,
            "release_iterations": 1,
            "fast_required_passes": 1,
            "release_required_passes": 1,
            "internal_passes_per_run": 1,
            "critical": False,
        },
        {
            "label": "supervised_update_policy_and_containment",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_agentic_update_service.AgenticUpdateServiceTests.test_supervised_run_applies_supported_tracks_and_records_policy_health_and_recovery_points",
                "tests.test_agentic_update_service.AgenticUpdateServiceTests.test_supervised_run_contains_rollout_after_unsupported_track_and_preserves_recovery_point",
                "tests.test_agentic_update_service.AgenticUpdateServiceTests.test_supervised_run_respects_pause_switch_before_apply",
            ),
            "covers": (
                "supervised_policy_defaults",
                "mixed_track_containment",
                "pause_switch_fail_closed",
            ),
            "fast_iterations": 1,
            "release_iterations": 8,
            "fast_required_passes": 1,
            "release_required_passes": 8,
            "internal_passes_per_run": 1,
            "critical": False,
        },
        {
            "label": "provider_retry_storm_and_circuit_breaker_chaos",
            "kind": "python_unittest",
            "cwd": _SIDECAR_ROOT,
            "targets": (
                "tests.test_graph_scheduler.DurableGraphSchedulerTests.test_retry_budget_caps_retry_storms_for_single_node",
                "tests.test_graph_scheduler.DurableGraphSchedulerTests.test_circuit_breaker_blocks_later_same_provider_dispatch_and_is_observable",
            ),
            "covers": (
                "provider_429_retry_storm_budget",
                "provider_429_circuit_breaker_fanout_containment",
                "cross_lane_provider_dispatch_backpressure_visibility",
            ),
            "fast_iterations": 1,
            "release_iterations": 8,
            "fast_required_passes": 1,
            "release_required_passes": 8,
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
    state_root = gate_run_dir / "state"
    for path in (gate_run_dir, raw_dir, reports_dir, validations_dir, command_dir, state_root):
        path.mkdir(parents=True, exist_ok=True)

    command_runner = command_runner or _default_command_runner
    process_inventory_provider = process_inventory_provider or _default_process_inventory_provider
    python_cmd = python_executable or sys.executable
    cargo_cmd = cargo_executable or "cargo"
    suites = runtime_stability_gate_suite_specs()

    with _temporary_env(
        {
            "ASTRABRIDGE_APPDATA": str(state_root / "appdata"),
            "ASTRABRIDGE_RUNTIME_ROOT": str(state_root / "runtime"),
        }
    ):
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

    fault_matrix = build_runtime_stability_fault_matrix(
        mode=resolved_mode,
        suite_results=suite_results,
        fixture_evidence=fixture_evidence,
    )
    write_json(validations_dir / "fault-matrix.json", fault_matrix)
    long_horizon_bundle = build_runtime_stability_long_horizon_bundle(
        mode=resolved_mode,
        suite_results=suite_results,
    )
    write_json(validations_dir / "long-horizon-bundle.json", long_horizon_bundle)
    injected_chaos_drills = build_runtime_stability_injected_chaos_drills(
        mode=resolved_mode,
        suite_results=suite_results,
    )
    write_json(validations_dir / "injected-chaos-drills.json", injected_chaos_drills)
    if resolved_mode == "release" and not bool(fault_matrix.get("release_ready")):
        overall_status = "fail"
    if resolved_mode == "release" and not bool(long_horizon_bundle.get("release_qualified")):
        overall_status = "fail"
    if resolved_mode == "release" and not bool(injected_chaos_drills.get("release_qualified")):
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
        "fault_matrix": fault_matrix,
        "long_horizon_bundle": long_horizon_bundle,
        "injected_chaos_drills": injected_chaos_drills,
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
            "state_root": str(state_root),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
            "fault_matrix_json": str(validations_dir / "fault-matrix.json"),
            "long_horizon_bundle_json": str(validations_dir / "long-horizon-bundle.json"),
            "injected_chaos_drills_json": str(validations_dir / "injected-chaos-drills.json"),
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
    fixture_root = Path(tempfile.mkdtemp(prefix="astrabridge-stability-fixture-")).resolve()
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
    fault_matrix = dict(summary.get("fault_matrix") or {})
    if fault_matrix:
        lines.extend(
            [
                "",
                "## Fault Matrix",
                "",
                f"- Status: `{fault_matrix.get('status')}`",
                f"- Release ready: `{fault_matrix.get('release_ready')}`",
                f"- Case count: `{fault_matrix.get('case_count')}`",
                f"- Matrix JSON: `{((summary.get('artifact_paths') or {}).get('fault_matrix_json'))}`",
                "",
            ]
        )
        for case in list(fault_matrix.get("cases") or []):
            lines.extend(
                [
                    f"- `{case.get('fault_id')}` status=`{case.get('status')}` final_state=`{case.get('final_state')}`",
                    f"  - recovery_time: `{dict(case.get('recovery_time') or {}).get('summary')}`",
                    f"  - duplicate_effects: `{case.get('duplicate_effects')}`",
                    f"  - evidence_completeness: `{dict(case.get('evidence_completeness') or {}).get('status')}`",
                    f"  - stale_process_count: `{dict(case.get('stale_process_count') or {}).get('value')}`",
                    f"  - downgraded_authority_visibility: `{dict(case.get('downgraded_authority_visibility') or {}).get('status')}`",
                ]
            )
    long_horizon_bundle = dict(summary.get("long_horizon_bundle") or {})
    if long_horizon_bundle:
        lines.extend(
            [
                "",
                "## Long-Horizon Stability Bundle",
                "",
                f"- Status: `{long_horizon_bundle.get('status')}`",
                f"- Release qualified: `{long_horizon_bundle.get('release_qualified')}`",
                f"- Bundle id: `{long_horizon_bundle.get('bundle_id')}`",
                f"- Bundle JSON: `{((summary.get('artifact_paths') or {}).get('long_horizon_bundle_json'))}`",
                "",
            ]
        )
        for suite in list(long_horizon_bundle.get("suites") or []):
            lines.extend(
                [
                    f"- `{suite.get('label')}` status=`{suite.get('status')}`",
                    f"  - iterations: `{suite.get('executed_iterations')}` required_passes=`{suite.get('required_pass_count')}` consecutive_passes=`{suite.get('max_consecutive_passes')}`",
                    f"  - covers: `{', '.join(list(suite.get('covers') or []))}`",
                ]
            )
    injected_chaos_drills = dict(summary.get("injected_chaos_drills") or {})
    if injected_chaos_drills:
        lines.extend(
            [
                "",
                "## Injected Cross-Lane Chaos Drills",
                "",
                f"- Status: `{injected_chaos_drills.get('status')}`",
                f"- Release qualified: `{injected_chaos_drills.get('release_qualified')}`",
                f"- Drill pack id: `{injected_chaos_drills.get('drill_pack_id')}`",
                f"- Drill JSON: `{((summary.get('artifact_paths') or {}).get('injected_chaos_drills_json'))}`",
                "",
            ]
        )
        for drill in list(injected_chaos_drills.get("drills") or []):
            lines.extend(
                [
                    f"- `{drill.get('label')}` status=`{drill.get('status')}`",
                    f"  - iterations: `{drill.get('executed_iterations')}` required_passes=`{drill.get('required_pass_count')}` consecutive_passes=`{drill.get('max_consecutive_passes')}`",
                    f"  - failure_classes: `{', '.join(list(drill.get('failure_classes') or []))}`",
                    f"  - covers: `{', '.join(list(drill.get('covers') or []))}`",
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


@contextmanager
def _temporary_env(updates: dict[str, str]) -> Any:
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


def build_runtime_stability_fault_matrix(
    *,
    mode: str,
    suite_results: list[dict[str, Any]],
    fixture_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    suite_by_label = {str(item.get("label") or ""): item for item in suite_results}
    cases = [
        _build_fault_case(
            fault_id="process_level_kill",
            label="Process-level kill and host-owned restart recovery",
            suite_by_label=suite_by_label,
            suite_labels=("desktop_forced_exit_restart", "desktop_twenty_restart_cycles_no_orphans"),
            final_state="sidecar_restart_recovered_without_owned_orphans",
            duplicate_effects="suppressed",
            recovery_summary="bounded host restart after forced exit",
            stale_process_required=True,
            stale_process_value=0,
        ),
        _build_fault_case(
            fault_id="disk_full_or_read_only",
            label="Disk-full / read-only write retry and duplicate suppression",
            suite_by_label=suite_by_label,
            suite_labels=("client_disconnect_and_disk_write_recovery",),
            final_state="write_retry_completed_without_duplicate_response",
            duplicate_effects="suppressed",
            recovery_summary="bounded retry after transient write failure",
        ),
        _build_fault_case(
            fault_id="sqlite_damage",
            label="SQLite damage guard with preserved backup",
            suite_by_label=suite_by_label,
            suite_labels=("durable_store_damage_and_legacy_recovery",),
            final_state="damaged_store_blocked_and_backup_preserved",
            duplicate_effects="not_applicable",
            recovery_summary="operator repair required before restart",
        ),
        _build_fault_case(
            fault_id="clock_shift",
            label="Clock shift / schedule jump reconciliation",
            suite_by_label=suite_by_label,
            suite_labels=("automation_clock_shift_and_scheduler_recovery",),
            final_state="schedule_recomputed_and_missed_run_policy_applied",
            duplicate_effects="queued_once_or_skipped",
            recovery_summary="next scheduler tick after clock jump",
        ),
        _build_fault_case(
            fault_id="network_partition",
            label="Network partition / disconnect retry handling",
            suite_by_label=suite_by_label,
            suite_labels=("client_disconnect_and_disk_write_recovery",),
            final_state="single_retry_or_clean_disconnect_recovered",
            duplicate_effects="second_response_suppressed",
            recovery_summary="bounded single transport retry or disconnect cleanup",
        ),
        _build_fault_case(
            fault_id="truncated_stream",
            label="Truncated stream / terminal projection recovery",
            suite_by_label=suite_by_label,
            suite_labels=("terminal_projection_and_stream_recovery",),
            final_state="terminal_projection_reconciled_after_stream_loss",
            duplicate_effects="suppressed",
            recovery_summary="post-timeout or follow-on-turn reconciliation",
        ),
        _build_fault_case(
            fault_id="update_interruption",
            label="Updater interruption with rollback readback preserved",
            suite_by_label=suite_by_label,
            suite_labels=("windows_update_interruption_rehearsal",),
            final_state="clean_install_update_and_rollback_rehearsed",
            duplicate_effects="suppressed",
            recovery_summary="rollback/readback rehearsal closes the update path",
        ),
        _build_fault_case(
            fault_id="multimodal_no_final_answer",
            label="Multimodal no-visible-final-answer visibility",
            suite_by_label=suite_by_label,
            suite_labels=("observability_fault_visibility_and_support_bundle",),
            final_state="incident_persisted_in_observability_and_support_bundle",
            duplicate_effects="not_applicable",
            recovery_summary="incident remains operator-visible until route is repaired",
            downgraded_authority_required=True,
            downgraded_authority_status="pass",
            downgraded_authority_summary="visible_in_observability_summary_and_support_bundle",
        ),
        _build_fault_case(
            fault_id="cross_version",
            label="Cross-version legacy readback and migration compatibility",
            suite_by_label=suite_by_label,
            suite_labels=("durable_store_damage_and_legacy_recovery",),
            final_state="legacy_reads_preserved_and_repeated_migration_stable",
            duplicate_effects="idempotent_repeated_migration",
            recovery_summary="legacy inputs are imported or marked needs_review without mutating source state",
        ),
    ]
    pass_count = sum(1 for item in cases if item.get("status") == "pass")
    partial_count = sum(1 for item in cases if item.get("status") == "partial")
    fail_count = sum(1 for item in cases if item.get("status") == "fail")
    release_ready = all(item.get("status") == "pass" for item in cases)
    if release_ready:
        status = "pass"
    elif mode == "fast" and fail_count == 0:
        status = "partial"
    else:
        status = "fail" if fail_count else "partial"
    return {
        "schema_version": RUNTIME_STABILITY_FAULT_MATRIX_SCHEMA_VERSION,
        "mode": mode,
        "status": status,
        "release_ready": release_ready,
        "case_count": len(cases),
        "pass_count": pass_count,
        "partial_count": partial_count,
        "fail_count": fail_count,
        "fixture_evidence_status": str((fixture_evidence or {}).get("status") or "not_captured"),
        "cases": cases,
    }


def build_runtime_stability_long_horizon_bundle(
    *,
    mode: str,
    suite_results: list[dict[str, Any]],
) -> dict[str, Any]:
    suite_by_label = {str(item.get("label") or ""): item for item in suite_results}
    selected_labels = (
        "scheduler_recovery_and_idempotency",
        "terminal_projection_and_stream_recovery",
        "mcp_timeout_cancel_and_policy_fail_closed",
        "windows_update_interruption_rehearsal",
        "supervised_update_policy_and_containment",
    )
    selected = [suite_by_label[label] for label in selected_labels if label in suite_by_label]
    missing = [label for label in selected_labels if label not in suite_by_label]
    any_failed = any(str(item.get("status") or "") == "fail" for item in selected)
    all_passed = bool(selected) and all(str(item.get("status") or "") == "pass" for item in selected) and not missing
    if mode == "release" and all_passed:
        status = "pass"
    elif any_failed:
        status = "fail"
    else:
        status = "partial"
    return {
        "schema_version": RUNTIME_STABILITY_LONG_HORIZON_BUNDLE_SCHEMA_VERSION,
        "mode": mode,
        "status": status,
        "release_qualified": bool(mode == "release" and status == "pass"),
        "bundle_id": "shipping_state_long_horizon_stability",
        "bundle_label": "Shipping-state long-horizon stability bundle",
        "suite_count": len(selected_labels),
        "executed_suite_count": len(selected),
        "missing_suite_labels": missing,
        "suite_labels": list(selected_labels),
        "suites": [
            {
                "label": str(item.get("label") or ""),
                "status": str(item.get("status") or ""),
                "executed_iterations": int(item.get("executed_iterations") or 0),
                "required_pass_count": int(item.get("required_pass_count") or 0),
                "max_consecutive_passes": int(item.get("max_consecutive_passes") or 0),
                "covers": list(item.get("covers") or []),
            }
            for item in selected
        ],
        "thresholds": {
            "promotion_mode_required": "release",
            "all_selected_suites_must_pass": True,
            "selected_suite_labels": list(selected_labels),
        },
    }


def build_runtime_stability_injected_chaos_drills(
    *,
    mode: str,
    suite_results: list[dict[str, Any]],
) -> dict[str, Any]:
    suite_by_label = {str(item.get("label") or ""): item for item in suite_results}
    selected_labels = ("provider_retry_storm_and_circuit_breaker_chaos",)
    selected = [suite_by_label[label] for label in selected_labels if label in suite_by_label]
    missing = [label for label in selected_labels if label not in suite_by_label]
    any_failed = any(str(item.get("status") or "") == "fail" for item in selected)
    all_passed = bool(selected) and all(str(item.get("status") or "") == "pass" for item in selected) and not missing
    if mode == "release" and all_passed:
        status = "pass"
    elif any_failed:
        status = "fail"
    else:
        status = "partial"
    drills: list[dict[str, Any]] = []
    for item in selected:
        evidence_paths: list[str] = []
        for iteration in list(item.get("iterations") or []):
            evidence_paths.extend(
                [str(iteration.get("stdout_path") or ""), str(iteration.get("stderr_path") or "")]
            )
        drills.append(
            {
                "drill_id": "provider_retry_storm_and_circuit_breaker",
                "label": str(item.get("label") or ""),
                "status": str(item.get("status") or ""),
                "executed_iterations": int(item.get("executed_iterations") or 0),
                "required_pass_count": int(item.get("required_pass_count") or 0),
                "max_consecutive_passes": int(item.get("max_consecutive_passes") or 0),
                "covers": list(item.get("covers") or []),
                "failure_classes": [
                    "provider_429_retry_storm",
                    "provider_429_circuit_breaker_open",
                    "cross_lane_provider_dispatch_backpressure",
                ],
                "thresholds": {
                    "retry_budget_exhaustion_stops_after_single_retry": True,
                    "later_same_provider_dispatch_must_be_denied_when_breaker_opens": True,
                    "breaker_state_must_remain_operator_visible": True,
                },
                "evidence_paths": [path for path in evidence_paths if path],
            }
        )
    return {
        "schema_version": RUNTIME_STABILITY_INJECTED_CHAOS_DRILLS_SCHEMA_VERSION,
        "mode": mode,
        "status": status,
        "release_qualified": bool(mode == "release" and status == "pass"),
        "drill_pack_id": "cross_lane_injected_chaos",
        "drill_pack_label": "Injected cross-lane chaos drills",
        "drill_count": len(selected_labels),
        "executed_drill_count": len(selected),
        "missing_drill_labels": missing,
        "drill_labels": list(selected_labels),
        "drills": drills,
        "thresholds": {
            "promotion_mode_required": "release",
            "all_selected_drills_must_pass": True,
            "selected_drill_labels": list(selected_labels),
        },
    }


def _build_fault_case(
    *,
    fault_id: str,
    label: str,
    suite_by_label: dict[str, dict[str, Any]],
    suite_labels: tuple[str, ...],
    final_state: str,
    duplicate_effects: str,
    recovery_summary: str,
    stale_process_required: bool = False,
    stale_process_value: int | None = None,
    downgraded_authority_required: bool = False,
    downgraded_authority_status: str = "not_required",
    downgraded_authority_summary: str = "not_required",
) -> dict[str, Any]:
    matched = [suite_by_label[label] for label in suite_labels if label in suite_by_label]
    evidence_paths: list[str] = []
    for suite in matched:
        for iteration in list(suite.get("iterations") or []):
            evidence_paths.extend(
                [str(iteration.get("stdout_path") or ""), str(iteration.get("stderr_path") or "")]
            )
    observed_fields = ["final_state", "duplicate_effects", "recovery_time", "evidence_paths"]
    missing_fields: list[str] = []
    if stale_process_required:
        if matched:
            observed_fields.append("stale_process_count")
        else:
            missing_fields.append("stale_process_count")
    if downgraded_authority_required:
        if matched:
            observed_fields.append("downgraded_authority_visibility")
        else:
            missing_fields.append("downgraded_authority_visibility")
    all_passed = bool(matched) and all(str(item.get("status") or "") == "pass" for item in matched)
    if all_passed:
        status = "pass"
        completeness_status = "pass"
    elif matched:
        status = "fail"
        completeness_status = "partial"
    else:
        status = "partial"
        completeness_status = "partial"
        missing_fields.append("suite_execution")
    return {
        "fault_id": fault_id,
        "label": label,
        "status": status,
        "final_state": final_state,
        "duplicate_effects": duplicate_effects,
        "recovery_time": {
            "summary": recovery_summary,
            "duration_ms_upper_bound": _suite_duration_upper_bound(matched),
        },
        "evidence_completeness": {
            "status": completeness_status,
            "observed_fields": observed_fields,
            "missing_fields": sorted(set(missing_fields)),
        },
        "stale_process_count": {
            "required": stale_process_required,
            "status": "pass" if stale_process_required and all_passed else ("not_required" if not stale_process_required else "partial"),
            "value": stale_process_value if stale_process_required and all_passed else None,
        },
        "downgraded_authority_visibility": {
            "required": downgraded_authority_required,
            "status": downgraded_authority_status if downgraded_authority_required and all_passed else ("not_required" if not downgraded_authority_required else "partial"),
            "summary": downgraded_authority_summary if downgraded_authority_required and all_passed else ("not_required" if not downgraded_authority_required else "evidence_not_executed"),
        },
        "evidence_paths": [path for path in evidence_paths if path],
        "suite_labels": list(suite_labels),
    }


def _suite_duration_upper_bound(suites: list[dict[str, Any]]) -> int | None:
    durations = [
        int(iteration.get("duration_ms") or 0)
        for suite in suites
        for iteration in list(suite.get("iterations") or [])
        if iteration.get("duration_ms") is not None
    ]
    if not durations:
        return None
    return max(durations)


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
