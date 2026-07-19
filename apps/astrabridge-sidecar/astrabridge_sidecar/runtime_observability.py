from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import PROJECT_SCHEMA_VERSION, WORKSPACE_STATE_DIRNAME, now_iso, write_json
from .durable_run_store import DURABLE_RUN_STORE_SCHEMA_VERSION
from .providers import classify_runtime_failure
from .release_identity import release_product_version
from .security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, redact_sensitive


RUNTIME_OBSERVABILITY_SCHEMA_VERSION = "astrabridge-runtime-observability-v1"
RUNTIME_TRACE_SCHEMA_VERSION = "astrabridge-runtime-trace-lineage-v1"
RUNTIME_DIAGNOSTIC_SCHEMA_VERSION = "astrabridge-runtime-diagnostic-v1"
HOST_LINEAGE_EVENT_SCHEMA_VERSION = "astrabridge-runtime-host-lineage-v1"
RUNTIME_SUPPORT_BUNDLE_SCHEMA_VERSION = "astrabridge-runtime-support-bundle-v1"
RUNTIME_SUPPORT_BUNDLE_SECRET_SCAN_SCHEMA_VERSION = "astrabridge-runtime-support-bundle-secret-scan-v1"
HOST_LINEAGE_RELATIVE_PATH = Path(WORKSPACE_STATE_DIRNAME) / "desktop-sidecar" / "logs" / "sidecar-host.jsonl"
RUNTIME_OBSERVABILITY_SNAPSHOT_RELATIVE_PATH = Path(WORKSPACE_STATE_DIRNAME) / "desktop-sidecar" / "observability" / "runtime-observability-summary.json"
RUNTIME_SUPPORT_BUNDLE_RELATIVE_PATH = Path(WORKSPACE_STATE_DIRNAME) / "desktop-sidecar" / "support" / "runtime-support-bundle.json"
RUNTIME_SUPPORT_BUNDLE_REPORT_RELATIVE_PATH = Path(WORKSPACE_STATE_DIRNAME) / "desktop-sidecar" / "support" / "runtime-support-bundle.md"
RUNTIME_SUPPORT_BUNDLE_SECRET_SCAN_RELATIVE_PATH = Path(WORKSPACE_STATE_DIRNAME) / "desktop-sidecar" / "support" / "runtime-support-bundle-secret-scan.json"
HOST_LINEAGE_TAIL_LIMIT = 400
RECENT_DIAGNOSTIC_LIMIT = 12
TRACE_LINEAGE_STEP_LIMIT = 24
SUPPORT_BUNDLE_EVENT_LIMIT = 16
RUNTIME_OBSERVABILITY_WINDOWS = (
    ("5m", 5 * 60),
    ("1h", 60 * 60),
    ("24h", 24 * 60 * 60),
)

_TEXT_SUFFIXES = {
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".txt",
    ".toml",
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

RUNTIME_OBSERVABILITY_METRICS = {
    "handoff_success_rate": {
        "label": "Cross-provider handoff success",
        "unit": "ratio",
        "good_threshold": 0.95,
        "warn_threshold": 0.80,
        "minimum_sample_size": 3,
        "otel_mapping": {
            "instrument": "gauge",
            "kind": "reliability_rate",
            "semantic_bridge": "custom->gen_ai.operation",
            "attributes": ["astrabridge.trace_id", "astrabridge.run_id", "gen_ai.provider.name"],
        },
    },
    "stale_run_rate": {
        "label": "Stale run rate",
        "unit": "ratio",
        "good_threshold": 0.05,
        "warn_threshold": 0.15,
        "minimum_sample_size": 3,
        "otel_mapping": {
            "instrument": "gauge",
            "kind": "recovery_rate_inverse",
            "semantic_bridge": "custom->service.recovery",
            "attributes": ["astrabridge.trace_id", "astrabridge.run_id"],
        },
    },
    "crash_recovery_success_rate": {
        "label": "Crash recovery success",
        "unit": "ratio",
        "good_threshold": 0.90,
        "warn_threshold": 0.70,
        "minimum_sample_size": 2,
        "otel_mapping": {
            "instrument": "gauge",
            "kind": "recovery_success",
            "semantic_bridge": "custom->service.recovery",
            "attributes": ["astrabridge.trace_id", "astrabridge.run_id", "astrabridge.recovery_kind"],
        },
    },
    "duplicate_effect_count": {
        "label": "Duplicate-effect count",
        "unit": "count",
        "good_threshold": 0.0,
        "warn_threshold": 1.0,
        "minimum_sample_size": 1,
        "otel_mapping": {
            "instrument": "counter",
            "kind": "duplicate_effect",
            "semantic_bridge": "custom->idempotency",
            "attributes": ["astrabridge.trace_id", "astrabridge.run_id", "astrabridge.operation_id"],
        },
    },
    "terminal_projection_lag_p95_ms": {
        "label": "Terminal projection lag p95",
        "unit": "ms",
        "good_threshold": 5000.0,
        "warn_threshold": 15000.0,
        "minimum_sample_size": 2,
        "otel_mapping": {
            "instrument": "histogram",
            "kind": "latency",
            "semantic_bridge": "custom->gen_ai.client.latency",
            "attributes": ["astrabridge.trace_id", "astrabridge.run_id", "astrabridge.turn_id"],
        },
    },
    "mcp_conformance_rate": {
        "label": "MCP conformance",
        "unit": "ratio",
        "good_threshold": 0.95,
        "warn_threshold": 0.80,
        "minimum_sample_size": 2,
        "otel_mapping": {
            "instrument": "gauge",
            "kind": "conformance_rate",
            "semantic_bridge": "custom->mcp.tool.call",
            "attributes": ["mcp.server", "mcp.tool", "mcp.protocol_version"],
        },
    },
    "node_latency_p95_ms": {
        "label": "Node latency p95",
        "unit": "ms",
        "good_threshold": 120000.0,
        "warn_threshold": 300000.0,
        "minimum_sample_size": 2,
        "otel_mapping": {
            "instrument": "histogram",
            "kind": "latency",
            "semantic_bridge": "custom->gen_ai.operation",
            "attributes": ["astrabridge.trace_id", "astrabridge.run_id", "astrabridge.node_id"],
        },
    },
    "first_token_latency_p95_ms": {
        "label": "First-token latency p95",
        "unit": "ms",
        "good_threshold": 15000.0,
        "warn_threshold": 30000.0,
        "minimum_sample_size": 2,
        "otel_mapping": {
            "instrument": "histogram",
            "kind": "latency",
            "semantic_bridge": "custom->gen_ai.client.ttft",
            "attributes": ["astrabridge.thread_id", "astrabridge.turn_id", "gen_ai.provider.name"],
        },
    },
}


def load_host_lineage_events(workspace_root: Path | None) -> list[dict[str, Any]]:
    if workspace_root is None:
        return []
    path = Path(workspace_root).expanduser().resolve() / HOST_LINEAGE_RELATIVE_PATH
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-HOST_LINEAGE_TAIL_LIMIT:]
    events: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        host_event = str(payload.get("event") or "").strip()
        event_payload = dict(payload.get("payload") or {})
        event = {
            "schema_version": HOST_LINEAGE_EVENT_SCHEMA_VERSION,
            "type": "host_event",
            "timestamp": str(payload.get("ts") or now_iso()),
            "host_event_type": host_event,
            "instance_id": str(payload.get("instance_id") or "").strip() or None,
            **event_payload,
        }
        events.append(enrich_runtime_event(event))
    return events


def enrich_runtime_event(event: dict[str, Any]) -> dict[str, Any]:
    clean = redact_sensitive(dict(event or {}))
    trace = extract_trace_context(clean)
    diagnostic = classify_runtime_diagnostic(clean, trace=trace)
    if trace:
        clean["trace"] = trace
        clean.setdefault("trace_id", trace.get("trace_id"))
        clean.setdefault("run_id", trace.get("run_id"))
        clean.setdefault("node_id", trace.get("node_id"))
        clean.setdefault("thread_id", trace.get("thread_id"))
        clean.setdefault("turn_id", trace.get("turn_id"))
    if diagnostic is not None:
        clean["diagnostic"] = diagnostic
    return clean


def build_runtime_observability_summary(
    events: list[dict[str, Any]],
    *,
    workspace_root: Path | None = None,
    current_task: dict[str, Any] | None = None,
    thread_id: str | None = None,
    external_operations: list[dict[str, Any]] | None = None,
    configured_models: list[dict[str, Any]] | None = None,
    selected_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_events = [enrich_runtime_event(item) for item in list(events or []) if isinstance(item, dict)]
    host_events = load_host_lineage_events(workspace_root)
    all_events = _merge_events(merged_events, host_events)
    graph_events = _graph_trace_events(current_task)
    diagnostics = _recent_diagnostics(all_events, graph_events)
    latest_trace = _latest_trace_lineage(all_events, graph_events)
    metrics = _build_metrics(
        all_events,
        graph_events,
        external_operations=external_operations or [],
        selected_thread_id=str(thread_id or "").strip(),
    )
    degraded_authority = _degraded_authority_signals(
        all_events,
        configured_models=configured_models or [],
        selected_thread_id=str(thread_id or "").strip(),
        selected_profile=selected_profile or {},
    )
    multimodal_quality = _multimodal_quality_signals(all_events)
    windows = _windowed_observability(
        all_events,
        graph_events,
        external_operations=external_operations or [],
        selected_thread_id=str(thread_id or "").strip(),
        configured_models=configured_models or [],
        selected_profile=selected_profile or {},
    )
    return redact_sensitive(
        {
            "schema_version": RUNTIME_OBSERVABILITY_SCHEMA_VERSION,
            "generated_at": now_iso(),
            "source": {
                "runtime_event_count": len(merged_events),
                "host_event_count": len(host_events),
                "graph_event_count": len(graph_events),
                "merged_event_count": len(all_events),
                "event_stream": "runtime_events_jsonl",
                "host_lineage": str(HOST_LINEAGE_RELATIVE_PATH).replace("\\", "/"),
                "ui_source": "runtime-supervisor",
            },
            "trace_lineage": latest_trace,
            "metrics": metrics,
            "slos": [_metric_slo(metric) for metric in metrics],
            "degraded_authority": degraded_authority,
            "multimodal_quality": multimodal_quality,
            "windows": windows,
            "domain_counts": _diagnostic_domain_counts(diagnostics),
            "recent_diagnostics": diagnostics,
        }
    )


def persist_runtime_observability_summary(summary: dict[str, Any], *, workspace_root: Path | None) -> str | None:
    if workspace_root is None:
        return None
    target = Path(workspace_root).expanduser().resolve() / RUNTIME_OBSERVABILITY_SNAPSHOT_RELATIVE_PATH
    write_json(target, redact_sensitive(summary))
    return str(target)


def build_runtime_support_bundle(
    *,
    observability_summary: dict[str, Any],
    runtime_events: list[dict[str, Any]],
    workspace_root: Path | None,
    environment: dict[str, Any],
    thread_status: dict[str, Any],
    runtime_error: dict[str, Any] | None,
    guard: dict[str, Any],
    watchdog: dict[str, Any],
) -> dict[str, Any]:
    clean_events = [redact_sensitive(dict(item)) for item in list(runtime_events or []) if isinstance(item, dict)]
    host_process_events = _support_bundle_host_process_events(clean_events)
    bundle = {
        "schema_version": RUNTIME_SUPPORT_BUNDLE_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "versions": {
            "product_version": release_product_version(),
            "python_version": sys.version.split()[0],
            "observability_schema_version": RUNTIME_OBSERVABILITY_SCHEMA_VERSION,
            "support_bundle_schema_version": RUNTIME_SUPPORT_BUNDLE_SCHEMA_VERSION,
            "durable_run_store_schema_version": DURABLE_RUN_STORE_SCHEMA_VERSION,
            "project_schema_version": PROJECT_SCHEMA_VERSION,
        },
        "paths": {
            "workspace_root": str(Path(workspace_root).expanduser().resolve()) if workspace_root is not None else None,
            "host_lineage": str(HOST_LINEAGE_RELATIVE_PATH).replace("\\", "/"),
            "observability_snapshot": str(RUNTIME_OBSERVABILITY_SNAPSHOT_RELATIVE_PATH).replace("\\", "/"),
        },
        "fingerprints": {
            "observability_sha256": _sha256_json(observability_summary),
            "recent_events_sha256": _sha256_json(clean_events[-SUPPORT_BUNDLE_EVENT_LIMIT:]),
            "trace_id": str(dict(observability_summary.get("trace_lineage") or {}).get("trace_id") or "").strip() or None,
            "git_branch": str(dict(environment.get("git") or {}).get("branch") or "").strip() or None,
            "git_changed_files": int(dict(environment.get("git") or {}).get("changed_files") or 0),
        },
        "environment": {
            "project_name": str(environment.get("project_name") or "").strip() or None,
            "cwd": str(environment.get("cwd") or "").strip() or None,
            "provider": str(environment.get("provider") or "").strip() or None,
            "model": str(environment.get("model") or "").strip() or None,
            "effort": str(environment.get("effort") or "").strip() or None,
            "permission": str(environment.get("permission") or "").strip() or None,
            "git": redact_sensitive(dict(environment.get("git") or {})),
            "mcp": redact_sensitive(dict(environment.get("mcp") or {})),
        },
        "health": {
            "thread_status": redact_sensitive(dict(thread_status or {})),
            "runtime_error": redact_sensitive(dict(runtime_error or {})) if isinstance(runtime_error, dict) else None,
            "guard": redact_sensitive(dict(guard or {})),
            "watchdog": redact_sensitive(dict(watchdog or {})),
            "release_gate": {
                "overall": all(bool(item.get("release_gate")) for item in list(observability_summary.get("slos") or [])),
                "current_window_5m": _window_release_gate(observability_summary, "5m"),
                "unknown_required_slos_5m": _window_unknown_required_slos(observability_summary, "5m"),
            },
        },
        "capability_visibility": {
            "degraded_authority": redact_sensitive(dict(observability_summary.get("degraded_authority") or {})),
            "multimodal_quality": redact_sensitive(dict(observability_summary.get("multimodal_quality") or {})),
        },
        "events": {
            "recent_runtime_events": [_support_bundle_event_excerpt(item) for item in clean_events[-SUPPORT_BUNDLE_EVENT_LIMIT:]],
            "recent_diagnostics": redact_sensitive(list(observability_summary.get("recent_diagnostics") or [])),
            "trace_lineage": redact_sensitive(dict(observability_summary.get("trace_lineage") or {})),
        },
        "process_ownership": {
            "host_event_count": sum(1 for item in clean_events if str(item.get("type") or "").strip() == "host_event"),
            "recent_host_process_events": host_process_events,
        },
        "recovery_guidance": _support_bundle_recovery_guidance(
            observability_summary=observability_summary,
            runtime_error=runtime_error,
            guard=guard,
            watchdog=watchdog,
        ),
    }
    return redact_sensitive(bundle)


def persist_runtime_support_bundle(bundle: dict[str, Any], *, workspace_root: Path | None) -> dict[str, Any] | None:
    if workspace_root is None:
        return None
    root = Path(workspace_root).expanduser().resolve()
    bundle_path = root / RUNTIME_SUPPORT_BUNDLE_RELATIVE_PATH
    report_path = root / RUNTIME_SUPPORT_BUNDLE_REPORT_RELATIVE_PATH
    scan_path = root / RUNTIME_SUPPORT_BUNDLE_SECRET_SCAN_RELATIVE_PATH
    write_json(bundle_path, redact_sensitive(bundle))
    report_path.write_text(render_runtime_support_bundle_report(bundle), encoding="utf-8")
    secret_scan = scan_runtime_support_bundle_artifacts(scan_path.parent)
    write_json(scan_path, secret_scan)
    return {
        "bundle_path": str(bundle_path),
        "report_path": str(report_path),
        "redaction_scan_path": str(scan_path),
        "redaction_scan": secret_scan,
    }


def extract_trace_context(event: dict[str, Any]) -> dict[str, Any] | None:
    params = dict(event.get("params") or {}) if isinstance(event.get("params"), dict) else {}
    mcp_audit = dict(event.get("mcp_audit_event") or {}) if isinstance(event.get("mcp_audit_event"), dict) else {}
    trace_context = dict(event.get("trace") or {}) if isinstance(event.get("trace"), dict) else {}
    if not trace_context:
        trace_context = dict(mcp_audit.get("trace_context") or {}) if isinstance(mcp_audit.get("trace_context"), dict) else {}
    trace_id = (
        str(event.get("trace_id") or "").strip()
        or str(trace_context.get("trace_id") or "").strip()
        or str(mcp_audit.get("trace_id") or "").strip()
    )
    run_id = (
        str(event.get("run_id") or "").strip()
        or str(trace_context.get("run_id") or "").strip()
        or str(mcp_audit.get("run_id") or "").strip()
    )
    node_id = (
        str(event.get("node_id") or "").strip()
        or str(trace_context.get("node_id") or "").strip()
        or str(mcp_audit.get("node_id") or "").strip()
    )
    attempt_count = _as_int(
        event.get("attempt_count")
        or trace_context.get("attempt_count")
        or mcp_audit.get("attempt_count")
    )
    thread_id = (
        str(event.get("thread_id") or "").strip()
        or str(params.get("threadId") or "").strip()
        or str(trace_context.get("thread_id") or "").strip()
        or str(mcp_audit.get("thread_id") or "").strip()
    )
    turn_id = (
        str(event.get("turn_id") or "").strip()
        or str(params.get("turnId") or "").strip()
        or str(trace_context.get("turn_id") or "").strip()
        or str(mcp_audit.get("turn_id") or "").strip()
    )
    operation_id = (
        str(event.get("operation_id") or "").strip()
        or str(event.get("mcp_operation_id") or "").strip()
        or str(trace_context.get("operation_id") or "").strip()
        or str(mcp_audit.get("operation_id") or "").strip()
    )
    message_id = (
        str(event.get("message_id") or "").strip()
        or str(event.get("envelope_id") or "").strip()
        or str(trace_context.get("message_id") or "").strip()
    )
    artifact_id = str(event.get("artifact_id") or "").strip() or None
    boot_id = str(event.get("boot_id") or event.get("host_boot_id") or "").strip() or None
    if not any([trace_id, run_id, node_id, thread_id, turn_id, operation_id, message_id, artifact_id, boot_id]):
        return None
    if not trace_id and run_id:
        trace_id = f"trace-{run_id}"
    return {
        "schema_version": RUNTIME_TRACE_SCHEMA_VERSION,
        "trace_id": trace_id or None,
        "run_id": run_id or None,
        "node_id": node_id or None,
        "attempt_count": attempt_count,
        "thread_id": thread_id or None,
        "turn_id": turn_id or None,
        "operation_id": operation_id or None,
        "message_id": message_id or None,
        "artifact_id": artifact_id,
        "boot_id": boot_id,
    }


def classify_runtime_diagnostic(event: dict[str, Any], *, trace: dict[str, Any] | None = None) -> dict[str, Any] | None:
    event_type = str(event.get("type") or "").strip()
    host_event_type = str(event.get("host_event_type") or "").strip()
    method = str(event.get("method") or "").strip()
    summary = str(event.get("summary") or event.get("message") or event.get("error") or event_type or method).strip()
    severity = "info"
    domain = "scheduler"
    if event_type == "host_event" or host_event_type.startswith("sidecar_") or host_event_type.startswith("desktop_sidecar_"):
        domain = "host"
    elif event_type.startswith("mcp_") or "mcp" in event_type or event_type in {"dynamic_tool_called", "dynamic_tool_policy_blocked"}:
        domain = "mcp" if event_type.startswith("mcp_") else "tool"
    elif event_type.startswith("asset_") or event_type.startswith("artifact_") or event_type in {"asset_registry_refreshed", "asset_registry_refresh_failed"}:
        domain = "artifact"
    elif "handoff_contract" in event_type or "schema" in event_type or "invalid structured handoff" in summary.lower():
        domain = "schema"
    elif "policy" in event_type or "context_guard" in event_type:
        domain = "policy"
    elif event_type.startswith("provider_") or "provider" in event_type or method in {"error", "thread/status/changed"}:
        domain = "provider"
    elif "transport" in summary.lower() or "timeout" in event_type.lower():
        domain = "transport"
    elif "reconciled" in event_type or "reconcile" in event_type or "scheduler" in event_type or event.get("event_type"):
        domain = "scheduler"
    if (
        "failed" in event_type
        or "error" in event_type
        or "needs_review" in event_type
        or "blocked" in event_type
        or "delivery_failed" in str(event.get("event_type") or "")
        or "timeout" in summary.lower()
    ):
        severity = "error"
    elif "warning" in event_type or "retry" in event_type or "reconciled" in event_type or "continue_once" in event_type:
        severity = "warning"
    notable = severity != "info" or domain in {"host", "provider", "transport", "schema", "policy", "mcp", "tool", "artifact"}
    if not notable:
        return None
    return {
        "schema_version": RUNTIME_DIAGNOSTIC_SCHEMA_VERSION,
        "domain": domain,
        "severity": severity,
        "event_type": event_type or method or host_event_type or str(event.get("event_type") or ""),
        "summary": summary[:240],
        "timestamp": str(event.get("timestamp") or now_iso()),
        "trace_id": str((trace or {}).get("trace_id") or "").strip() or None,
        "run_id": str((trace or {}).get("run_id") or "").strip() or None,
        "node_id": str((trace or {}).get("node_id") or "").strip() or None,
        "operation_id": str((trace or {}).get("operation_id") or "").strip() or None,
    }


def _merge_events(runtime_events: list[dict[str, Any]], host_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*runtime_events, *host_events]:
        fingerprint = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        merged.append(item)
    merged.sort(key=lambda item: str(item.get("timestamp") or ""))
    return merged


def _graph_trace_events(current_task: dict[str, Any] | None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not isinstance(current_task, dict):
        return events
    for run_ref in list(current_task.get("graph_run_refs") or []):
        if not isinstance(run_ref, dict):
            continue
        run_id = str(run_ref.get("run_id") or "").strip()
        trace_id = str(run_ref.get("trace_id") or f"trace-{run_id}").strip()
        run_status = str(run_ref.get("status") or "").strip()
        for item in list(run_ref.get("timeline_events") or []):
            if not isinstance(item, dict):
                continue
            events.append(
                enrich_runtime_event(
                    {
                        "type": "graph_timeline_event",
                        "timestamp": str(item.get("created_at") or now_iso()),
                        "trace_id": trace_id,
                        "run_id": run_id,
                        "node_id": str(item.get("node_id") or "").strip() or None,
                        "artifact_id": str(item.get("artifact_id") or "").strip() or None,
                        "event_type": str(item.get("event_type") or "").strip(),
                        "summary": str(item.get("summary") or "").strip(),
                        "status": str(item.get("status") or run_status).strip() or run_status,
                    }
                )
            )
    return events


def _latest_trace_lineage(runtime_events: list[dict[str, Any]], graph_events: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: dict[str, dict[str, Any]] = {}
    for event in [*graph_events, *runtime_events]:
        trace = dict(event.get("trace") or {})
        trace_id = str(trace.get("trace_id") or "").strip()
        if not trace_id:
            continue
        bucket = candidates.setdefault(
            trace_id,
            {
                "trace_id": trace_id,
                "run_id": str(trace.get("run_id") or "").strip() or None,
                "thread_id": str(trace.get("thread_id") or "").strip() or None,
                "latest_at": str(event.get("timestamp") or ""),
                "steps": [],
                "domains": set(),
            },
        )
        bucket["latest_at"] = max(str(bucket.get("latest_at") or ""), str(event.get("timestamp") or ""))
        domain = str(dict(event.get("diagnostic") or {}).get("domain") or _event_domain_guess(event)).strip() or "scheduler"
        bucket["domains"].add(domain)
        bucket["steps"].append(
            {
                "timestamp": str(event.get("timestamp") or ""),
                "source": "graph_timeline" if event.get("type") == "graph_timeline_event" else "runtime_event",
                "domain": domain,
                "event_type": str(event.get("event_type") or event.get("type") or ""),
                "summary": str(event.get("summary") or event.get("message") or event.get("host_event_type") or event.get("type") or "")[:220],
                "node_id": trace.get("node_id"),
                "operation_id": trace.get("operation_id"),
                "artifact_id": trace.get("artifact_id"),
            }
        )
    if not candidates:
        return None
    latest = sorted(candidates.values(), key=lambda item: str(item.get("latest_at") or ""), reverse=True)[0]
    steps = sorted(list(latest["steps"]), key=lambda item: str(item.get("timestamp") or ""))[-TRACE_LINEAGE_STEP_LIMIT:]
    domains = set(latest["domains"])
    return {
        "trace_id": latest["trace_id"],
        "run_id": latest.get("run_id"),
        "thread_id": latest.get("thread_id"),
        "latest_at": latest.get("latest_at"),
        "domain_sequence": list(sorted(latest["domains"])),
        "steps": steps,
        "complete": len(steps) > 0 and ("scheduler" in domains) and bool({"tool", "mcp", "artifact"}.intersection(domains)),
    }


def _build_metrics(
    runtime_events: list[dict[str, Any]],
    graph_events: list[dict[str, Any]],
    *,
    external_operations: list[dict[str, Any]],
    selected_thread_id: str,
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    handoff_created = sum(1 for event in graph_events if str(event.get("event_type") or "") == "handoff_created")
    handoff_success = sum(1 for event in graph_events if str(event.get("event_type") or "") == "handoff_acknowledged")
    metrics.append(_ratio_metric("handoff_success_rate", handoff_success, handoff_created))

    graph_trace_ids = {
        str(dict(event.get("trace") or {}).get("trace_id") or "").strip()
        for event in graph_events
        if str(dict(event.get("trace") or {}).get("trace_id") or "").strip()
    }
    stale_trace_ids = {
        str(dict(event.get("trace") or {}).get("trace_id") or "").strip()
        for event in [*graph_events, *runtime_events]
        if str(event.get("event_type") or event.get("type") or "").strip()
        in {"turn_reconciled", "task_graph_turn_reconciled", "runtime_turn_terminal_notification_reconciled"}
    }
    metrics.append(_ratio_metric("stale_run_rate", len(stale_trace_ids), len(graph_trace_ids)))

    recovery_success = sum(
        1
        for event in runtime_events
        if str(event.get("type") or "") in {"task_graph_turn_reconciled", "runtime_turn_terminal_notification_reconciled"}
    )
    recovery_failures = sum(
        1
        for event in runtime_events
        if str(event.get("type") or "") in {"durable_graph_scheduler_reconcile_failed"}
    ) + sum(1 for event in runtime_events if str(event.get("host_event_type") or "") in {"sidecar_circuit_breaker_opened", "sidecar_launch_timed_out"})
    metrics.append(_ratio_metric("crash_recovery_success_rate", recovery_success, recovery_success + recovery_failures))

    duplicate_effect_count = sum(
        1
        for event in runtime_events
        if str(event.get("type") or "").strip() == "duplicate_effect_suppressed"
    )
    metrics.append(_count_metric("duplicate_effect_count", duplicate_effect_count))

    terminal_projection_lags = [
        float(event.get("terminal_projection_lag_ms") or 0)
        for event in runtime_events
        if _as_float(event.get("terminal_projection_lag_ms")) is not None
    ]
    metrics.append(_distribution_metric("terminal_projection_lag_p95_ms", terminal_projection_lags))

    mcp_audited = [
        event
        for event in runtime_events
        if str(event.get("type") or "").strip() == "dynamic_tool_called"
    ]
    mcp_conformant = [
        event
        for event in mcp_audited
        if isinstance(event.get("mcp_audit_event"), dict)
        and str(dict(event.get("mcp_audit_event") or {}).get("protocol_version") or "").strip()
        and bool(dict(event.get("mcp_policy_decision") or {}).get("server_enabled", True))
    ]
    metrics.append(_ratio_metric("mcp_conformance_rate", len(mcp_conformant), len(mcp_audited)))

    node_latencies = _node_latency_samples(graph_events)
    metrics.append(_distribution_metric("node_latency_p95_ms", node_latencies))

    first_token_latencies = _first_token_latency_samples(runtime_events, selected_thread_id=selected_thread_id)
    metrics.append(_distribution_metric("first_token_latency_p95_ms", first_token_latencies))

    return metrics


def _windowed_observability(
    runtime_events: list[dict[str, Any]],
    graph_events: list[dict[str, Any]],
    *,
    external_operations: list[dict[str, Any]],
    selected_thread_id: str,
    configured_models: list[dict[str, Any]],
    selected_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    latest_timestamp = _latest_event_timestamp([*runtime_events, *graph_events])
    windows: list[dict[str, Any]] = []
    for window_id, duration_sec in RUNTIME_OBSERVABILITY_WINDOWS:
        runtime_window = _filter_events_for_window(runtime_events, latest_timestamp=latest_timestamp, duration_sec=duration_sec)
        graph_window = _filter_events_for_window(graph_events, latest_timestamp=latest_timestamp, duration_sec=duration_sec)
        metrics = _build_metrics(
            runtime_window,
            graph_window,
            external_operations=external_operations,
            selected_thread_id=selected_thread_id,
        )
        slos = [_metric_slo(metric) for metric in metrics]
        window_events = [*runtime_window, *graph_window]
        windows.append(
            {
                "window_id": window_id,
                "duration_sec": duration_sec,
                "event_count": len(runtime_window) + len(graph_window),
                "metrics": metrics,
                "slos": slos,
                "signals": {
                    "degraded_authority": _degraded_authority_signals(
                        window_events,
                        configured_models=configured_models,
                        selected_thread_id=selected_thread_id,
                        selected_profile=selected_profile,
                        recent_limit=4,
                    ),
                    "multimodal_quality": _multimodal_quality_signals(window_events, recent_limit=4),
                },
                "release_gate": all(bool(item.get("release_gate")) for item in slos),
                "unknown_required_slos": [
                    str(item.get("metric_id") or "")
                    for item in slos
                    if str(item.get("status") or "") == "unknown"
                ],
            }
        )
    return windows


def _recent_diagnostics(
    runtime_events: list[dict[str, Any]],
    graph_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for event in [*runtime_events, *graph_events]:
        diagnostic = dict(event.get("diagnostic") or {})
        if not diagnostic:
            continue
        diagnostics.append(diagnostic)
    diagnostics.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in diagnostics:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= RECENT_DIAGNOSTIC_LIMIT:
            break
    return deduped


def _diagnostic_domain_counts(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for item in diagnostics:
        domain = str(item.get("domain") or "scheduler")
        bucket = counts.setdefault(domain, {"domain": domain, "count": 0, "error_count": 0, "warning_count": 0})
        bucket["count"] += 1
        if str(item.get("severity") or "") == "error":
            bucket["error_count"] += 1
        elif str(item.get("severity") or "") == "warning":
            bucket["warning_count"] += 1
    return sorted(counts.values(), key=lambda item: (-int(item["count"]), str(item["domain"])))


def _ratio_metric(metric_id: str, numerator: int, denominator: int, *, invert: bool = False) -> dict[str, Any]:
    value = None if denominator <= 0 else float(numerator) / float(denominator)
    if invert and value is not None:
        value = 1.0 - value
    return _metric(metric_id, value=value, sample_size=denominator, numerator=numerator, denominator=denominator)


def _count_metric(metric_id: str, value: int) -> dict[str, Any]:
    return _metric(metric_id, value=float(value), sample_size=value)


def _distribution_metric(metric_id: str, values: list[float]) -> dict[str, Any]:
    return _metric(metric_id, value=_p95(values), sample_size=len(values), distribution={"count": len(values), "p95": _p95(values), "max": max(values) if values else None})


def _metric(
    metric_id: str,
    *,
    value: float | None,
    sample_size: int,
    numerator: int | None = None,
    denominator: int | None = None,
    distribution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(RUNTIME_OBSERVABILITY_METRICS[metric_id])
    status = _metric_status(value=value, metric_id=metric_id)
    return {
        "metric_id": metric_id,
        "label": metadata["label"],
        "value": value,
        "unit": metadata["unit"],
        "sample_size": sample_size,
        "numerator": numerator,
        "denominator": denominator,
        "distribution": distribution,
        "status": status,
        "otel_mapping": metadata["otel_mapping"],
    }


def _metric_status(*, value: float | None, metric_id: str) -> str:
    if value is None:
        return "unknown"
    metadata = RUNTIME_OBSERVABILITY_METRICS[metric_id]
    good = float(metadata["good_threshold"])
    warn = float(metadata["warn_threshold"])
    if metric_id in {"stale_run_rate", "duplicate_effect_count", "terminal_projection_lag_p95_ms", "node_latency_p95_ms", "first_token_latency_p95_ms"}:
        if value <= good:
            return "pass"
        if value <= warn:
            return "warning"
        return "fail"
    if value >= good:
        return "pass"
    if value >= warn:
        return "warning"
    return "fail"


def _metric_slo(metric: dict[str, Any]) -> dict[str, Any]:
    metadata = RUNTIME_OBSERVABILITY_METRICS[str(metric.get("metric_id") or "")]
    minimum_sample_size = int(metadata.get("minimum_sample_size") or 1)
    sample_size = int(metric.get("sample_size") or 0)
    sample_status = "sufficient" if sample_size >= minimum_sample_size else "insufficient"
    status = str(metric.get("status") or "unknown")
    effective_status = status if sample_status == "sufficient" else "unknown"
    return {
        "metric_id": metric.get("metric_id"),
        "status": effective_status,
        "observed_status": status,
        "good_threshold": metadata["good_threshold"],
        "warn_threshold": metadata["warn_threshold"],
        "unit": metadata["unit"],
        "minimum_sample_size": minimum_sample_size,
        "sample_size": sample_size,
        "sample_status": sample_status,
        "burn_rate_alert": _burn_rate_alert(metric_id=str(metric.get("metric_id") or ""), value=metric.get("value"), status=effective_status),
        "release_gate": effective_status not in {"fail", "unknown"},
    }


def _burn_rate_alert(*, metric_id: str, value: Any, status: str) -> dict[str, Any]:
    if status == "unknown":
        return {"status": "unknown", "level": "insufficient_samples", "ratio": None}
    numeric_value = _as_float(value)
    if numeric_value is None:
        return {"status": "unknown", "level": "no_value", "ratio": None}
    metadata = RUNTIME_OBSERVABILITY_METRICS[metric_id]
    good = float(metadata["good_threshold"])
    warn = float(metadata["warn_threshold"])
    inverse = metric_id in {"stale_run_rate", "duplicate_effect_count", "terminal_projection_lag_p95_ms", "node_latency_p95_ms", "first_token_latency_p95_ms"}
    if inverse:
        span = max(warn - good, 1e-9)
        ratio = max(0.0, (numeric_value - good) / span)
    else:
        span = max(good - warn, 1e-9)
        ratio = max(0.0, (good - numeric_value) / span)
    if ratio >= 1.0:
        level = "page"
    elif ratio >= 0.5:
        level = "ticket"
    else:
        level = "none"
    return {"status": "evaluated", "level": level, "ratio": round(ratio, 3)}


def _node_latency_samples(graph_events: list[dict[str, Any]]) -> list[float]:
    started_at: dict[tuple[str, str], datetime] = {}
    samples: list[float] = []
    terminal_events = {"node_completed", "node_failed", "node_blocked", "node_needs_review", "node_cancelled"}
    for event in sorted(graph_events, key=lambda item: str(item.get("timestamp") or "")):
        trace = dict(event.get("trace") or {})
        run_id = str(trace.get("run_id") or "").strip()
        node_id = str(trace.get("node_id") or event.get("node_id") or "").strip()
        if not run_id or not node_id:
            continue
        event_type = str(event.get("event_type") or "").strip()
        timestamp = _parse_iso(str(event.get("timestamp") or ""))
        if timestamp is None:
            continue
        key = (run_id, node_id)
        if event_type == "node_started":
            started_at[key] = timestamp
        elif event_type in terminal_events and key in started_at:
            samples.append(max(0.0, (timestamp - started_at[key]).total_seconds() * 1000.0))
            started_at.pop(key, None)
    return samples


def _first_token_latency_samples(runtime_events: list[dict[str, Any]], *, selected_thread_id: str) -> list[float]:
    started_at: dict[tuple[str, str], datetime] = {}
    samples: list[float] = []
    first_token_methods = {"item/agentMessage/delta", "item/reasoning/textDelta", "item/reasoning/summaryTextDelta"}
    for event in sorted(runtime_events, key=lambda item: str(item.get("timestamp") or "")):
        if str(event.get("type") or "") != "notification":
            continue
        method = str(event.get("method") or "")
        params = dict(event.get("params") or {})
        thread_id = str(params.get("threadId") or "").strip()
        turn_id = str(params.get("turnId") or "").strip()
        if selected_thread_id and thread_id and thread_id != selected_thread_id:
            continue
        timestamp = _parse_iso(str(event.get("timestamp") or ""))
        if timestamp is None or not thread_id or not turn_id:
            continue
        key = (thread_id, turn_id)
        if method == "turn/started":
            started_at[key] = timestamp
        elif method in first_token_methods and key in started_at:
            samples.append(max(0.0, (timestamp - started_at[key]).total_seconds() * 1000.0))
            started_at.pop(key, None)
    return samples


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_event_timestamp(events: list[dict[str, Any]]) -> datetime | None:
    timestamps = [_parse_iso(str(item.get("timestamp") or "")) for item in events]
    valid = [item for item in timestamps if item is not None]
    if not valid:
        return None
    return max(valid)


def _filter_events_for_window(
    events: list[dict[str, Any]],
    *,
    latest_timestamp: datetime | None,
    duration_sec: int,
) -> list[dict[str, Any]]:
    if latest_timestamp is None:
        return []
    cutoff = latest_timestamp.timestamp() - float(duration_sec)
    filtered: list[dict[str, Any]] = []
    for item in events:
        timestamp = _parse_iso(str(item.get("timestamp") or ""))
        if timestamp is None:
            continue
        if timestamp.timestamp() >= cutoff:
            filtered.append(item)
    return filtered


def _event_domain_guess(event: dict[str, Any]) -> str:
    diagnostic = dict(event.get("diagnostic") or {})
    if diagnostic:
        return str(diagnostic.get("domain") or "scheduler")
    if str(event.get("type") or "") == "host_event":
        return "host"
    return "scheduler"


def scan_runtime_support_bundle_artifacts(run_dir: str | Path) -> dict[str, Any]:
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
                        "message": "Desktop key-file path leaked into runtime support-bundle evidence.",
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
                            "message": "Secret-like content found in runtime support-bundle evidence.",
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
                            "message": "Secret-like query parameter found in runtime support-bundle evidence.",
                            "excerpt": excerpt,
                        }
                    )
    return {
        "schema_version": RUNTIME_SUPPORT_BUNDLE_SECRET_SCAN_SCHEMA_VERSION,
        "status": "pass" if not findings else "fail",
        "scanned_root": str(root),
        "scanned_files": scanned_files,
        "finding_count": len(findings),
        "findings": findings,
    }


def render_runtime_support_bundle_report(bundle: dict[str, Any]) -> str:
    lines = [
        "# Runtime Support Bundle",
        "",
        f"- Generated: `{bundle.get('generated_at')}`",
        f"- Product version: `{dict(bundle.get('versions') or {}).get('product_version')}`",
        f"- Provider/model: `{dict(bundle.get('environment') or {}).get('provider')}` / `{dict(bundle.get('environment') or {}).get('model')}`",
        f"- Git branch: `{dict(dict(bundle.get('environment') or {}).get('git') or {}).get('branch')}`",
        "",
        "## Health",
        "",
        f"- Thread status: `{dict(dict(bundle.get('health') or {}).get('thread_status') or {}).get('type')}`",
        f"- Guard level: `{dict(dict(bundle.get('health') or {}).get('guard') or {}).get('level')}`",
        f"- Watchdog level: `{dict(dict(bundle.get('health') or {}).get('watchdog') or {}).get('level')}`",
        f"- Release gate 5m: `{dict(dict(bundle.get('health') or {}).get('release_gate') or {}).get('current_window_5m')}`",
        "",
        "## Capability Visibility",
        "",
        f"- Structured tool status: `{dict(dict(dict(bundle.get('capability_visibility') or {}).get('degraded_authority') or {}).get('selected_route') or {}).get('structured_tool_status')}`",
        f"- MCP tool status: `{dict(dict(dict(bundle.get('capability_visibility') or {}).get('degraded_authority') or {}).get('selected_route') or {}).get('mcp_tool_status')}`",
        f"- Multimodal no-final-answer incidents: `{dict(dict(bundle.get('capability_visibility') or {}).get('multimodal_quality') or {}).get('no_final_answer_incident_count')}`",
        "",
        "## Recovery Guidance",
        "",
    ]
    for item in list(bundle.get("recovery_guidance") or []):
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def _degraded_authority_signals(
    events: list[dict[str, Any]],
    *,
    configured_models: list[dict[str, Any]],
    selected_thread_id: str,
    selected_profile: dict[str, Any],
    recent_limit: int = 6,
) -> dict[str, Any]:
    model_index = _configured_model_index(configured_models)
    turn_events = [item for item in events if str(item.get("type") or "").strip() == "turn_started_request"]
    route_checks: list[dict[str, Any]] = []
    for event in turn_events:
        route_state = _route_authority_state_for_event(event, model_index)
        route_checks.append(
            {
                "timestamp": str(event.get("timestamp") or ""),
                "thread_id": str(event.get("thread_id") or "").strip() or None,
                "turn_id": str(event.get("turn_id") or "").strip() or None,
                **route_state,
            }
        )
    degraded_turns = [item for item in route_checks if bool(item.get("downgraded"))]
    structured_warning_turns = [item for item in route_checks if str(item.get("structured_tool_status") or "") == "warning_gated"]
    mcp_warning_turns = [item for item in route_checks if str(item.get("mcp_tool_status") or "") == "warning_gated"]
    unknown_turns = [item for item in route_checks if str(item.get("route_state") or "") == "unknown"]
    selected_route = _selected_route_authority_state(
        route_checks,
        model_index=model_index,
        selected_thread_id=selected_thread_id,
        selected_profile=selected_profile,
    )
    return {
        "turns_evaluated": len(route_checks),
        "degraded_turns": len(degraded_turns),
        "warning_gated_structured_turns": len(structured_warning_turns),
        "warning_gated_mcp_turns": len(mcp_warning_turns),
        "unknown_turns": len(unknown_turns),
        "route_downgrade_rate": _ratio_or_none(len(degraded_turns), len(route_checks)),
        "selected_route": selected_route,
        "recent_exposures": sorted(
            [
                {
                    "timestamp": item.get("timestamp"),
                    "thread_id": item.get("thread_id"),
                    "turn_id": item.get("turn_id"),
                    "provider_id": item.get("provider_id"),
                    "model_id": item.get("model_id"),
                    "authority_tier": item.get("authority_tier"),
                    "structured_tool_status": item.get("structured_tool_status"),
                    "mcp_tool_status": item.get("mcp_tool_status"),
                    "parallel_tool_call_status": item.get("parallel_tool_call_status"),
                    "command_execution_status": item.get("command_execution_status"),
                    "ui_warnings": item.get("ui_warnings"),
                }
                for item in degraded_turns
            ],
            key=lambda item: str(item.get("timestamp") or ""),
            reverse=True,
        )[:recent_limit],
    }


def _multimodal_quality_signals(
    events: list[dict[str, Any]],
    *,
    recent_limit: int = 6,
) -> dict[str, Any]:
    multimodal_turns: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        if str(event.get("type") or "").strip() != "turn_started_request":
            continue
        thread_id = str(event.get("thread_id") or "").strip()
        turn_id = str(event.get("turn_id") or "").strip()
        diagnostics = dict(event.get("attachment_diagnostics") or {})
        if not thread_id or not turn_id:
            continue
        image_count = int(diagnostics.get("image_count") or 0)
        route = dict(diagnostics.get("route") or {})
        if image_count <= 0 and int(route.get("local_image_items") or 0) <= 0:
            continue
        runtime = dict(event.get("runtime") or {})
        multimodal_turns[(thread_id, turn_id)] = {
            "timestamp": str(event.get("timestamp") or ""),
            "thread_id": thread_id,
            "turn_id": turn_id,
            "provider_id": str(runtime.get("provider_id") or route.get("provider_id") or "").strip() or None,
            "model_id": str(runtime.get("model") or route.get("model_id") or "").strip() or None,
            "image_count": image_count,
            "local_image_items": int(route.get("local_image_items") or 0),
            "context_mode": str(route.get("context_mode") or "").strip() or None,
        }
    incidents: list[dict[str, Any]] = []
    seen_incidents: set[tuple[str, str, str]] = set()
    for event in events:
        incident = _multimodal_incident_from_event(event)
        if incident is None:
            continue
        key = (str(incident.get("thread_id") or ""), str(incident.get("turn_id") or ""))
        if key not in multimodal_turns:
            continue
        dedupe_key = (
            key[0],
            key[1],
            str(incident.get("category") or ""),
        )
        if dedupe_key in seen_incidents:
            continue
        seen_incidents.add(dedupe_key)
        incidents.append({**multimodal_turns[key], **incident})
    no_final_answer = [item for item in incidents if str(item.get("category") or "") == "semantic_no_output"]
    timeout_incidents = [
        item
        for item in incidents
        if str(item.get("category") or "") in {"provider_timeout", "transport_failure"}
    ]
    return {
        "multimodal_turns": len(multimodal_turns),
        "incident_turns": len(incidents),
        "no_final_answer_incident_count": len(no_final_answer),
        "timeout_incident_count": len(timeout_incidents),
        "incident_rate": _ratio_or_none(len(incidents), len(multimodal_turns)),
        "recent_incidents": sorted(incidents, key=lambda item: str(item.get("timestamp") or ""), reverse=True)[:recent_limit],
    }


def _multimodal_incident_from_event(event: dict[str, Any]) -> dict[str, Any] | None:
    if str(event.get("type") or "").strip() != "notification":
        return None
    method = str(event.get("method") or "").strip()
    params = dict(event.get("params") or {})
    thread_id = str(params.get("threadId") or "").strip()
    turn_id = str(params.get("turnId") or "").strip()
    message = ""
    provider_id = ""
    model_id = ""
    if method == "error":
        error = params.get("error") or {}
        message = str(error.get("message") or error).strip()
    elif method == "turn/completed":
        turn = dict(params.get("turn") or {})
        if str(turn.get("status") or "").strip().lower() != "failed":
            return None
        turn_id = str(turn.get("id") or turn_id).strip()
        error = turn.get("error") or {}
        message = str(error.get("message") or error).strip()
        provider_id = str(turn.get("provider_id") or turn.get("providerId") or "").strip()
        model_id = str(turn.get("model") or "").strip()
    else:
        return None
    if not thread_id or not turn_id or not message:
        return None
    notice = classify_runtime_failure(message, current_provider=provider_id or None, current_model=model_id or None).to_payload()
    category = str(notice.get("category") or "").strip()
    if category not in {"semantic_no_output", "provider_timeout", "transport_failure"}:
        return None
    return {
        "timestamp": str(event.get("timestamp") or ""),
        "thread_id": thread_id,
        "turn_id": turn_id,
        "category": category,
        "summary": str(notice.get("summary") or "").strip(),
        "recommended_action": str(notice.get("recommended_action") or "").strip() or None,
        "provider_id": provider_id or None,
        "model_id": model_id or None,
    }


def _selected_route_authority_state(
    route_checks: list[dict[str, Any]],
    *,
    model_index: dict[tuple[str, str], dict[str, Any]],
    selected_thread_id: str,
    selected_profile: dict[str, Any],
) -> dict[str, Any] | None:
    if selected_thread_id:
        for item in sorted(route_checks, key=lambda entry: str(entry.get("timestamp") or ""), reverse=True):
            if str(item.get("thread_id") or "") == selected_thread_id:
                return _selected_route_projection(item)
    if route_checks:
        latest = sorted(route_checks, key=lambda entry: str(entry.get("timestamp") or ""), reverse=True)[0]
        return _selected_route_projection(latest)
    provider_id = str(selected_profile.get("provider_id") or "").strip()
    model_id = str(selected_profile.get("model") or "").strip()
    if not provider_id and not model_id:
        return None
    event = {"runtime": {"provider_id": provider_id, "model": model_id}}
    return _selected_route_projection(_route_authority_state_for_event(event, model_index))


def _selected_route_projection(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_id": item.get("provider_id"),
        "model_id": item.get("model_id"),
        "authority_tier": item.get("authority_tier"),
        "authority_reason": item.get("authority_reason"),
        "structured_tool_status": item.get("structured_tool_status"),
        "mcp_tool_status": item.get("mcp_tool_status"),
        "parallel_tool_call_status": item.get("parallel_tool_call_status"),
        "command_execution_status": item.get("command_execution_status"),
        "route_state": item.get("route_state"),
        "downgraded": bool(item.get("downgraded")),
        "ui_warnings": list(item.get("ui_warnings") or []),
    }


def _route_authority_state_for_event(
    event: dict[str, Any],
    model_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    runtime = dict(event.get("runtime") or {})
    provider_id = str(runtime.get("provider_id") or event.get("provider_id") or "").strip()
    model_id = str(runtime.get("model") or event.get("model") or "").strip()
    record = _lookup_model_record(model_index, provider_id=provider_id, model_id=model_id)
    if record is None:
        return {
            "provider_id": provider_id or None,
            "model_id": model_id or None,
            "authority_tier": None,
            "authority_reason": None,
            "structured_tool_status": "unknown",
            "mcp_tool_status": "unknown",
            "parallel_tool_call_status": "unknown",
            "command_execution_status": "unknown",
            "route_state": "unknown",
            "downgraded": False,
            "ui_warnings": [],
        }
    authority_tier = str(record.get("authority_tier") or "").strip().upper() or None
    structured_tool_status = "verified" if authority_tier == "A" else "warning_gated"
    supports_mcp_tools = bool(record.get("supports_mcp_tools", False))
    mcp_policy = str(record.get("mcp_tool_call_policy") or "").strip().lower()
    mcp_smoke_status = str(record.get("mcp_smoke_status") or "").strip().lower()
    if not supports_mcp_tools:
        mcp_tool_status = "unsupported"
    elif mcp_policy == "verified" and (mcp_smoke_status == "verified" or mcp_smoke_status.startswith("pass")):
        mcp_tool_status = "verified"
    else:
        mcp_tool_status = "warning_gated"
    parallel_tool_call_status = str(record.get("parallel_tool_call_status") or "").strip() or "unknown"
    command_execution_status = str(record.get("command_execution_status") or "").strip() or "unknown"
    downgraded = (
        structured_tool_status == "warning_gated"
        or mcp_tool_status == "warning_gated"
        or parallel_tool_call_status in {"serial_only", "disabled"}
        or command_execution_status in {"partial_no_command_execution", "completed_without_command_execution"}
    )
    return {
        "provider_id": provider_id or None,
        "model_id": model_id or None,
        "authority_tier": authority_tier,
        "authority_reason": str(record.get("authority_reason") or "").strip() or None,
        "structured_tool_status": structured_tool_status,
        "mcp_tool_status": mcp_tool_status,
        "parallel_tool_call_status": parallel_tool_call_status,
        "command_execution_status": command_execution_status,
        "route_state": "known",
        "downgraded": downgraded,
        "ui_warnings": list(record.get("ui_warnings") or record.get("authority_ui_warnings") or []),
    }


def _configured_model_index(configured_models: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for item in list(configured_models or []):
        if not isinstance(item, dict):
            continue
        provider_id = str(item.get("provider_id") or "").strip()
        model_id = str(item.get("model") or "").strip()
        combined_id = str(item.get("id") or "").strip()
        if combined_id and (not provider_id or not model_id) and "/" in combined_id:
            provider_part, model_part = combined_id.split("/", 1)
            provider_id = provider_id or provider_part.strip()
            model_id = model_id or model_part.strip()
        if not provider_id or not model_id:
            continue
        index[(provider_id, model_id)] = dict(item)
    return index


def _lookup_model_record(
    model_index: dict[tuple[str, str], dict[str, Any]],
    *,
    provider_id: str,
    model_id: str,
) -> dict[str, Any] | None:
    if not provider_id or not model_id:
        return None
    return dict(model_index.get((provider_id, model_id)) or {}) or None


def _ratio_or_none(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def _support_bundle_host_process_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    process_events: list[dict[str, Any]] = []
    for item in sorted(events, key=lambda event: str(event.get("timestamp") or ""), reverse=True):
        if str(item.get("type") or "").strip() != "host_event":
            continue
        process_events.append(
            {
                "timestamp": str(item.get("timestamp") or ""),
                "instance_id": str(item.get("instance_id") or "").strip() or None,
                "boot_id": str(item.get("boot_id") or item.get("host_boot_id") or "").strip() or None,
                "pid": _as_int(item.get("pid")),
                "host_event_type": str(item.get("host_event_type") or "").strip() or None,
                "status": str(item.get("status") or "").strip() or None,
            }
        )
        if len(process_events) >= 6:
            break
    return process_events


def _support_bundle_recovery_guidance(
    *,
    observability_summary: dict[str, Any],
    runtime_error: dict[str, Any] | None,
    guard: dict[str, Any],
    watchdog: dict[str, Any],
) -> list[str]:
    guidance: list[str] = []
    if isinstance(runtime_error, dict) and runtime_error:
        guidance.append(
            f"Runtime error category `{runtime_error.get('category')}` recommends `{runtime_error.get('recommended_action')}`."
        )
        for item in list(runtime_error.get("recommended_actions") or [])[:3]:
            if isinstance(item, dict) and str(item.get("label") or "").strip():
                guidance.append(f"{item.get('label')}: {str(item.get('reason') or '').strip()}")
    selected_route = dict(dict(observability_summary.get("degraded_authority") or {}).get("selected_route") or {})
    if bool(selected_route.get("downgraded")):
        guidance.append(
            "Selected route is downgraded or warning-gated; keep approvals and verification enabled until a verified capability lane is available."
        )
    multimodal = dict(observability_summary.get("multimodal_quality") or {})
    if int(multimodal.get("no_final_answer_incident_count") or 0) > 0:
        guidance.append(
            "Multimodal attachment turns have produced no-visible-final-answer incidents; retry with simpler fixtures or switch to a verified image-capable route."
        )
    if str(guard.get("level") or "") in {"warning", "danger", "pause"}:
        guidance.append(f"Context guard is `{guard.get('level')}`; follow `{guard.get('recommended_action')}` before the next long turn.")
    if str(watchdog.get("level") or "") in {"warning", "danger", "pause"}:
        guidance.append(f"Watchdog is `{watchdog.get('level')}` after `{watchdog.get('idle_seconds')}` idle seconds; use `{watchdog.get('recommended_action')}` if the lane remains stalled.")
    if not guidance:
        guidance.append("No immediate recovery action is required; use this bundle as the redacted baseline before escalation or release-gate triage.")
    return guidance


def _support_bundle_event_excerpt(event: dict[str, Any]) -> dict[str, Any]:
    trace = dict(event.get("trace") or {})
    diagnostic = dict(event.get("diagnostic") or {})
    params = dict(event.get("params") or {}) if isinstance(event.get("params"), dict) else {}
    item = params.get("item") if isinstance(params, dict) else None
    return redact_sensitive(
        {
            "timestamp": str(event.get("timestamp") or ""),
            "type": str(event.get("type") or "").strip() or None,
            "method": str(event.get("method") or "").strip() or None,
            "event_type": str(event.get("event_type") or "").strip() or None,
            "thread_id": str(event.get("thread_id") or params.get("threadId") or "").strip() or None,
            "turn_id": str(event.get("turn_id") or params.get("turnId") or "").strip() or None,
            "host_event_type": str(event.get("host_event_type") or "").strip() or None,
            "summary": str(event.get("summary") or event.get("message") or event.get("error") or diagnostic.get("summary") or "")[:220] or None,
            "trace_id": str(trace.get("trace_id") or "").strip() or None,
            "run_id": str(trace.get("run_id") or "").strip() or None,
            "node_id": str(trace.get("node_id") or "").strip() or None,
            "item_type": str(dict(item or {}).get("type") or "").strip() or None if isinstance(item, dict) else None,
            "diagnostic_domain": str(diagnostic.get("domain") or "").strip() or None,
            "diagnostic_severity": str(diagnostic.get("severity") or "").strip() or None,
        }
    )


def _window_release_gate(summary: dict[str, Any], window_id: str) -> bool | None:
    for item in list(summary.get("windows") or []):
        if str(dict(item).get("window_id") or "") == window_id:
            return bool(dict(item).get("release_gate"))
    return None


def _window_unknown_required_slos(summary: dict[str, Any], window_id: str) -> list[str]:
    for item in list(summary.get("windows") or []):
        if str(dict(item).get("window_id") or "") == window_id:
            return [str(value) for value in list(dict(item).get("unknown_required_slos") or []) if str(value).strip()]
    return []


def _sha256_json(payload: Any) -> str:
    rendered = json.dumps(redact_sensitive(payload), ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _is_redacted_or_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    return normalized in {
        "[redacted]",
        "<redacted>",
        "example",
        "dummy",
        "fixture",
        "test",
        "unit",
        "not_available",
    }


def _as_int(value: Any) -> int | None:
    try:
        if value in {None, ""}:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        if value in {None, ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def load_external_operations_for_observability(db_path: Path | None) -> list[dict[str, Any]]:
    if db_path is None or not Path(db_path).is_file():
        return []
    query = "SELECT operation_id, run_id, kind, classification, status, external_handle, created_at, updated_at, payload_json FROM external_operations ORDER BY updated_at, operation_id"
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()
    payloads: list[dict[str, Any]] = []
    for row in rows:
        payload_json = row["payload_json"]
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            payload = {}
        payloads.append(
            redact_sensitive(
                {
                    "operation_id": row["operation_id"],
                    "run_id": row["run_id"],
                    "kind": row["kind"],
                    "classification": row["classification"],
                    "status": row["status"],
                    "external_handle": row["external_handle"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "payload": payload,
                }
            )
        )
    return payloads
