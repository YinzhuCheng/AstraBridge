from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, now_iso
from .security import redact_sensitive


RUNTIME_OBSERVABILITY_SCHEMA_VERSION = "astrabridge-runtime-observability-v1"
RUNTIME_TRACE_SCHEMA_VERSION = "astrabridge-runtime-trace-lineage-v1"
RUNTIME_DIAGNOSTIC_SCHEMA_VERSION = "astrabridge-runtime-diagnostic-v1"
HOST_LINEAGE_EVENT_SCHEMA_VERSION = "astrabridge-runtime-host-lineage-v1"
HOST_LINEAGE_RELATIVE_PATH = Path(WORKSPACE_STATE_DIRNAME) / "desktop-sidecar" / "logs" / "sidecar-host.jsonl"
HOST_LINEAGE_TAIL_LIMIT = 400
RECENT_DIAGNOSTIC_LIMIT = 12
TRACE_LINEAGE_STEP_LIMIT = 24

RUNTIME_OBSERVABILITY_METRICS = {
    "handoff_success_rate": {
        "label": "Cross-provider handoff success",
        "unit": "ratio",
        "good_threshold": 0.95,
        "warn_threshold": 0.80,
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
            "domain_counts": _diagnostic_domain_counts(diagnostics),
            "recent_diagnostics": diagnostics,
        }
    )


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
    return {
        "metric_id": metric.get("metric_id"),
        "status": metric.get("status"),
        "good_threshold": metadata["good_threshold"],
        "warn_threshold": metadata["warn_threshold"],
        "unit": metadata["unit"],
        "release_gate": metric.get("status") != "fail",
    }


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


def _event_domain_guess(event: dict[str, Any]) -> str:
    diagnostic = dict(event.get("diagnostic") or {})
    if diagnostic:
        return str(diagnostic.get("domain") or "scheduler")
    if str(event.get("type") or "") == "host_event":
        return "host"
    return "scheduler"


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
