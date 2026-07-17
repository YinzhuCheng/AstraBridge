from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from astrabridge_sidecar.runtime_observability import (
    build_runtime_observability_summary,
    enrich_runtime_event,
)


class RuntimeObservabilityTests(unittest.TestCase):
    def test_enrich_runtime_event_projects_trace_from_nested_mcp_audit(self) -> None:
        event = enrich_runtime_event(
            {
                "type": "dynamic_tool_called",
                "timestamp": "2026-07-17T12:00:01+09:00",
                "thread_id": "thread-worker",
                "turn_id": "turn-worker",
                "mcp_audit_event": {
                    "trace_context": {
                        "trace_id": "trace-graph-run-1",
                        "run_id": "graph-run-1",
                        "node_id": "worker",
                        "attempt_count": 2,
                        "thread_id": "thread-worker",
                        "turn_id": "turn-worker",
                        "operation_id": "mcp-op-123",
                    }
                },
            }
        )

        self.assertEqual(event["trace"]["trace_id"], "trace-graph-run-1")
        self.assertEqual(event["trace"]["run_id"], "graph-run-1")
        self.assertEqual(event["trace"]["node_id"], "worker")
        self.assertEqual(event["trace"]["operation_id"], "mcp-op-123")
        self.assertEqual(event["diagnostic"]["domain"], "tool")

    def test_build_runtime_observability_summary_computes_trace_metrics_and_host_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            host_log = workspace / ".astrabridge" / "desktop-sidecar" / "logs"
            host_log.mkdir(parents=True)
            (host_log / "sidecar-host.jsonl").write_text(
                json.dumps(
                    {
                        "ts": "2026-07-17T12:00:06+09:00",
                        "event": "sidecar_exit_observed",
                        "instance_id": "desktop-1",
                        "payload": {
                            "boot_id": "sidecar-boot-1",
                            "pid": 4567,
                            "status": "Exit code 1",
                            "token": "secret-value-should-not-leak",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            current_task = {
                "graph_run_refs": [
                    {
                        "run_id": "graph-run-1",
                        "trace_id": "trace-graph-run-1",
                        "status": "completed",
                        "timeline_events": [
                            {
                                "event_id": "graph-run-1-created",
                                "event_type": "run_created",
                                "created_at": "2026-07-17T12:00:00+09:00",
                                "summary": "Run admitted.",
                            },
                            {
                                "event_id": "graph-run-1-worker-started",
                                "event_type": "node_started",
                                "created_at": "2026-07-17T12:00:02+09:00",
                                "summary": "Worker started.",
                                "node_id": "worker",
                            },
                            {
                                "event_id": "graph-run-1-handoff-created",
                                "event_type": "handoff_created",
                                "created_at": "2026-07-17T12:00:03+09:00",
                                "summary": "Handoff persisted.",
                                "node_id": "worker",
                            },
                            {
                                "event_id": "graph-run-1-handoff-ack",
                                "event_type": "handoff_acknowledged",
                                "created_at": "2026-07-17T12:00:04+09:00",
                                "summary": "Handoff acknowledged.",
                                "node_id": "worker",
                            },
                            {
                                "event_id": "graph-run-1-worker-complete",
                                "event_type": "node_completed",
                                "created_at": "2026-07-17T12:00:06+09:00",
                                "summary": "Worker completed.",
                                "node_id": "worker",
                            },
                            {
                                "event_id": "graph-run-1-artifact",
                                "event_type": "artifact_ready",
                                "created_at": "2026-07-17T12:00:07+09:00",
                                "summary": "Summary artifact written.",
                                "artifact_id": "graph-run-1-summary-json",
                                "node_id": "worker",
                            },
                        ],
                    }
                ]
            }
            events = [
                {
                    "type": "notification",
                    "method": "turn/started",
                    "timestamp": "2026-07-17T12:00:01+09:00",
                    "params": {"threadId": "thread-worker", "turnId": "turn-worker"},
                },
                {
                    "type": "notification",
                    "method": "item/agentMessage/delta",
                    "timestamp": "2026-07-17T12:00:02+09:00",
                    "params": {"threadId": "thread-worker", "turnId": "turn-worker", "delta": "hello"},
                },
                {
                    "type": "dynamic_tool_called",
                    "timestamp": "2026-07-17T12:00:05+09:00",
                    "thread_id": "thread-worker",
                    "turn_id": "turn-worker",
                    "mcp_policy_decision": {"server_enabled": True},
                    "mcp_audit_event": {
                        "protocol_version": "2025-11-25",
                        "trace_context": {
                            "trace_id": "trace-graph-run-1",
                            "run_id": "graph-run-1",
                            "node_id": "worker",
                            "attempt_count": 1,
                            "thread_id": "thread-worker",
                            "turn_id": "turn-worker",
                            "operation_id": "mcp-op-1",
                        },
                    },
                },
                {
                    "type": "runtime_turn_terminal_notification_reconciled",
                    "timestamp": "2026-07-17T12:00:07+09:00",
                    "thread_id": "thread-worker",
                    "turn_id": "turn-worker",
                    "terminal_projection_lag_ms": 1200,
                },
                {
                    "type": "duplicate_effect_suppressed",
                    "timestamp": "2026-07-17T12:00:08+09:00",
                    "trace_id": "trace-graph-run-1",
                    "run_id": "graph-run-1",
                    "node_id": "worker",
                    "attempt_count": 1,
                    "operation_id": "mcp-op-1",
                },
            ]

            summary = build_runtime_observability_summary(
                events,
                workspace_root=workspace,
                current_task=current_task,
                thread_id="thread-worker",
            )

            self.assertEqual(summary["schema_version"], "astrabridge-runtime-observability-v1")
            self.assertEqual(summary["trace_lineage"]["trace_id"], "trace-graph-run-1")
            self.assertTrue(summary["trace_lineage"]["complete"])
            metric_map = {item["metric_id"]: item for item in summary["metrics"]}
            self.assertEqual(metric_map["handoff_success_rate"]["value"], 1.0)
            self.assertEqual(metric_map["duplicate_effect_count"]["value"], 1.0)
            self.assertEqual(metric_map["mcp_conformance_rate"]["value"], 1.0)
            self.assertEqual(metric_map["terminal_projection_lag_p95_ms"]["value"], 1200.0)
            self.assertEqual(metric_map["node_latency_p95_ms"]["value"], 4000.0)
            self.assertEqual(metric_map["first_token_latency_p95_ms"]["value"], 1000.0)
            domains = {item["domain"] for item in summary["recent_diagnostics"]}
            self.assertIn("host", domains)
            self.assertIn("tool", domains)
            rendered = json.dumps(summary, ensure_ascii=False)
            self.assertNotIn("secret-value-should-not-leak", rendered)


if __name__ == "__main__":
    unittest.main()
