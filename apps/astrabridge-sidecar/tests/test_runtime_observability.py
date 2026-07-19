from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.runtime_observability import (
    build_runtime_observability_summary,
    build_runtime_support_bundle,
    enrich_runtime_event,
    persist_runtime_support_bundle,
    scan_runtime_support_bundle_artifacts,
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
                    "type": "turn_started_request",
                    "timestamp": "2026-07-17T12:00:00+09:00",
                    "thread_id": "thread-worker",
                    "turn_id": "turn-worker",
                    "runtime": {"provider_id": "deepseek", "model": "deepseek-v4-pro"},
                    "attachment_diagnostics": {
                        "image_count": 1,
                        "route": {
                            "provider_id": "deepseek",
                            "model_id": "deepseek-v4-pro",
                            "context_mode": "default",
                            "local_image_items": 1,
                        },
                    },
                },
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
                {
                    "type": "notification",
                    "method": "error",
                    "timestamp": "2026-07-17T12:00:09+09:00",
                    "params": {
                        "threadId": "thread-worker",
                        "turnId": "turn-worker",
                        "error": {"message": "Provider route completed but returned no visible final answer."},
                    },
                },
            ]

            summary = build_runtime_observability_summary(
                events,
                workspace_root=workspace,
                current_task=current_task,
                thread_id="thread-worker",
                configured_models=[
                    {
                        "id": "deepseek/deepseek-v4-pro",
                        "provider_id": "deepseek",
                        "model": "deepseek-v4-pro",
                        "authority_tier": "B",
                        "authority_reason": "Model should stay in review/propose mode unless validation or approval promotes the action.",
                        "supports_mcp_tools": True,
                        "mcp_tool_call_policy": "conservative",
                        "mcp_smoke_status": "pass_direct_tool_call",
                        "parallel_tool_call_status": "serial_only",
                        "command_execution_status": "verified",
                        "ui_warnings": [
                            "This model should propose changes before apply/execute actions.",
                            "Parallel tool calls are disabled unless this model is explicitly verified for parallel execution.",
                        ],
                    }
                ],
                selected_profile={"provider_id": "deepseek", "model": "deepseek-v4-pro"},
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
            window_map = {item["window_id"]: item for item in summary["windows"]}
            self.assertEqual(sorted(window_map), ["1h", "24h", "5m"])
            self.assertFalse(window_map["5m"]["release_gate"])
            self.assertEqual(summary["degraded_authority"]["degraded_turns"], 1)
            self.assertEqual(summary["degraded_authority"]["selected_route"]["structured_tool_status"], "warning_gated")
            self.assertEqual(summary["degraded_authority"]["selected_route"]["mcp_tool_status"], "warning_gated")
            self.assertEqual(summary["multimodal_quality"]["multimodal_turns"], 1)
            self.assertEqual(summary["multimodal_quality"]["no_final_answer_incident_count"], 1)
            self.assertEqual(window_map["5m"]["signals"]["multimodal_quality"]["incident_turns"], 1)
            handoff_slo = next(item for item in window_map["5m"]["slos"] if item["metric_id"] == "handoff_success_rate")
            self.assertEqual(handoff_slo["status"], "unknown")
            self.assertEqual(handoff_slo["sample_status"], "insufficient")
            self.assertFalse(handoff_slo["release_gate"])
            duplicate_slo = next(item for item in window_map["5m"]["slos"] if item["metric_id"] == "duplicate_effect_count")
            self.assertEqual(duplicate_slo["status"], "warning")
            self.assertEqual(duplicate_slo["burn_rate_alert"]["level"], "page")
            support_bundle = build_runtime_support_bundle(
                observability_summary=summary,
                runtime_events=events,
                workspace_root=workspace,
                environment={
                    "project_name": "Demo",
                    "cwd": str(workspace),
                    "git": {"branch": "main", "changed_files": 2},
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
                    "effort": "xhigh",
                    "permission": "auto",
                    "mcp": {"status": "listed", "count": 1},
                },
                thread_status={"type": "systemError"},
                runtime_error={
                    "category": "semantic_no_output",
                    "recommended_action": "mark_capability_unverified",
                    "recommended_actions": [{"label": "Mark Unverified", "reason": "Keep the lane partial until fixed."}],
                },
                guard={"level": "warning", "recommended_action": "watch"},
                watchdog={"level": "danger", "idle_seconds": 181, "recommended_action": "watch_or_interrupt"},
            )
            persisted_bundle = persist_runtime_support_bundle(support_bundle, workspace_root=workspace)
            self.assertEqual(support_bundle["schema_version"], "astrabridge-runtime-support-bundle-v1")
            self.assertEqual(support_bundle["capability_visibility"]["degraded_authority"]["selected_route"]["structured_tool_status"], "warning_gated")
            self.assertEqual(support_bundle["capability_visibility"]["multimodal_quality"]["no_final_answer_incident_count"], 1)
            self.assertEqual(dict(persisted_bundle["redaction_scan"]).get("status"), "pass")
            self.assertTrue(Path(str(persisted_bundle["bundle_path"])).exists())
            domains = {item["domain"] for item in summary["recent_diagnostics"]}
            self.assertIn("host", domains)
            self.assertIn("tool", domains)
            rendered = json.dumps(summary, ensure_ascii=False)
            self.assertNotIn("secret-value-should-not-leak", rendered)

    def test_runtime_support_bundle_secret_scan_flags_secret_like_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle_dir = root / ".astrabridge" / "desktop-sidecar" / "support"
            bundle_dir.mkdir(parents=True)
            (bundle_dir / "runtime-support-bundle.md").write_text("Authorization: Bearer sk-test-secret-123456789012\n", encoding="utf-8")

            result = scan_runtime_support_bundle_artifacts(bundle_dir)

            self.assertEqual(result["status"], "fail")
            self.assertGreaterEqual(result["finding_count"], 1)
            self.assertEqual(result["findings"][0]["code"], "secret-like")


if __name__ == "__main__":
    unittest.main()
