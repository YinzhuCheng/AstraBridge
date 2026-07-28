from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.compact_validation_harness import (
    build_compact_validation_case,
    build_compact_validation_report,
    post_compact_continuation_state,
)
from astrabridge_sidecar.coding_kernel import ContextSection, build_context_budget
from astrabridge_sidecar.model_catalog import resolved_runtime_provider_contract_fields
from astrabridge_sidecar.providers import classify_runtime_failure
from astrabridge_sidecar.runtime_config_service import RuntimeConfigService


class ContextGateCompatibilityTests(unittest.TestCase):
    def test_context_budget_report_exposes_preflight_and_compaction_status(self) -> None:
        _text, report = build_context_budget(
            sections=[
                ContextSection("intro", "Intro", 0, "alpha beta gamma delta", essential=True),
                ContextSection("rules", "Rules", 1, "line\n" * 120),
            ],
            provider_id="deepseek",
            model_id="deepseek-v4-pro",
            context_window=4096,
            effective_context_window_percent=40,
            auto_compact_token_limit=900,
            tool_output_token_limit=16000,
            manual_compact_status="app_server_native",
            auto_compact_status="configured_unverified",
            compact_summary_quality_status="untested",
            tool_schema_token_estimate=300,
            endpoint_protocol="chat",
        )

        payload = report.to_dict()

        self.assertEqual(payload["schema_version"], "astrabridge-context-budget-v2")
        self.assertEqual(payload["provider_id"], "deepseek")
        self.assertEqual(payload["model_id"], "deepseek-v4-pro")
        self.assertEqual(payload["effective_context_budget_tokens"], 1638)
        self.assertEqual(payload["advertised_context_window_tokens"], 4096)
        self.assertEqual(payload["endpoint_protocol_overhead_tokens"], 128)
        self.assertEqual(payload["output_reserve_tokens"], 128)
        self.assertEqual(payload["usable_coding_context_status"], "conservative_estimate")
        self.assertIsNone(payload["verified_usable_coding_context_tokens"])
        self.assertEqual(payload["auto_compact_token_limit"], 900)
        self.assertEqual(payload["tool_output_token_limit"], 16000)
        self.assertEqual(payload["manual_compact_status"], "app_server_native")
        self.assertEqual(payload["auto_compact_status"], "configured_unverified")
        self.assertEqual(payload["compact_summary_quality_status"], "untested")
        self.assertEqual(payload["preflight_budgeting_status"], "budgeted_before_send")
        self.assertFalse(payload["automatic_request_truncation"])
        self.assertEqual(payload["provider_rejection_category"], "context_window_limit")

    def test_runtime_provider_contract_exposes_context_gate_fields(self) -> None:
        contract = resolved_runtime_provider_contract_fields(
            {
                "provider": "deepseek",
                "native_model": "deepseek-v4-pro",
                "context_window": 4096,
                "effective_context_window_percent": 40,
                "auto_compact_token_limit": 900,
                "tool_output_token_limit": 16000,
                "supports_mcp_tools": True,
                "mcp_tool_call_policy": "conservative",
                "context_compaction_support": {
                    "manual_compact": "app_server_native",
                    "auto_compact": "configured_unverified",
                    "structured_summary_quality": "untested",
                },
                "context_budget_policy": {
                    "advertised_context_window_status": "verified",
                    "endpoint_protocol_overhead_tokens": 192,
                    "endpoint_overhead_status": "verified",
                    "output_reserve_tokens": 512,
                    "reasoning_artifact_policy": "neutral_summary_only",
                },
            }
        )

        context_gate = contract["capability_metadata"]["context_window"]

        self.assertEqual(contract["codex_runtime_metadata"]["context_window"], 4096)
        self.assertEqual(contract["codex_runtime_metadata"]["effective_context_budget_tokens"], 1638)
        self.assertEqual(context_gate["declared_context_window"], 4096)
        self.assertEqual(context_gate["advertised_context_window_tokens"], 4096)
        self.assertEqual(context_gate["usable_coding_context_status"], "requires_endpoint_preflight")
        self.assertIsNone(context_gate["verified_usable_coding_context_tokens"])
        self.assertEqual(context_gate["context_budget_policy"]["endpoint_protocol_overhead_tokens"], 192)
        self.assertEqual(context_gate["effective_context_window_percent"], 40)
        self.assertEqual(context_gate["effective_context_budget_tokens"], 1638)
        self.assertEqual(context_gate["auto_compact_token_limit"], 900)
        self.assertEqual(context_gate["auto_compact_limit_source"], "configured")
        self.assertEqual(context_gate["tool_output_token_limit"], 16000)
        self.assertEqual(context_gate["tool_output_limit_source"], "configured")
        self.assertEqual(context_gate["manual_compact_status"], "app_server_native")
        self.assertEqual(context_gate["auto_compact_status"], "configured_unverified")
        self.assertEqual(context_gate["compact_summary_quality_status"], "untested")
        self.assertEqual(context_gate["preflight_budgeting_status"], "budgeted_before_send")
        self.assertFalse(context_gate["automatic_request_truncation"])
        self.assertEqual(context_gate["provider_rejection_category"], "context_window_limit")

    def test_runtime_status_exposes_context_limits_and_compaction_support(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = RuntimeConfigService(
                root / "codex_home",
                configured_models_resolver=lambda: [
                    {
                        "id": "context/context-model",
                        "provider": "context",
                        "native_model": "context-model",
                        "display_name": "Context Model",
                        "advertised_context_window": 32768,
                        "effective_context_window_percent": 55,
                        "auto_compact_token_limit": 12000,
                        "tool_output_token_limit": 6000,
                        "context_compaction_support": {
                            "manual_compact": "app_server_native",
                            "auto_compact": "configured_unverified",
                            "structured_summary_quality": "untested",
                        },
                        "context_budget_policy": {
                            "advertised_context_window_status": "verified",
                            "endpoint_protocol_overhead_tokens": 176,
                            "endpoint_overhead_status": "verified",
                            "output_reserve_tokens": 384,
                        },
                    }
                ],
            )

            status = service.prepare_profile(
                {
                    "profile_id": "context-profile",
                    "label": "Context",
                    "provider_id": "context",
                    "base_url": "https://context.example/v1",
                    "model": "context-model",
                    "reasoning_effort": "high",
                    "wire_api": "chat",
                    "env_key": "TEST_CONTEXT_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                },
                require_secret=False,
            )

            self.assertEqual(status["context_window"], 32768)
            self.assertEqual(status["effective_context_window_percent"], 55)
            self.assertEqual(status["auto_compact_token_limit"], 12000)
            self.assertEqual(status["tool_output_token_limit"], 6000)
            self.assertEqual(status["usable_coding_context_status"], "requires_endpoint_preflight")
            self.assertIsNone(status["verified_usable_coding_context_tokens"])
            self.assertEqual(status["advertised_context_window_status"], "verified")
            self.assertEqual(status["context_budget_policy"]["endpoint_protocol_overhead_tokens"], 176)
            self.assertEqual(status["context_compaction_support"]["auto_compact"], "configured_unverified")
            self.assertEqual(status["context_compaction_support"]["structured_summary_quality"], "untested")

    def test_preflight_budgeting_and_provider_rejection_are_distinct_signals(self) -> None:
        _text, report = build_context_budget(
            sections=[ContextSection("intro", "Intro", 0, "budgeted context", essential=True)],
            provider_id="qwen",
            model_id="qwen3.7-plus",
            context_window=8192,
            effective_context_window_percent=80,
            auto_compact_token_limit=4096,
            endpoint_protocol="chat",
        )
        failure = classify_runtime_failure(
            '{"error":{"message":"context length exceeded","provider":"qwen","model":"qwen3.7-plus"}}'
        ).to_payload()

        self.assertEqual(report.to_dict()["preflight_budgeting_status"], "budgeted_before_send")
        self.assertEqual(failure["category"], "context_window_limit")
        self.assertTrue(failure["compact_recommended"])
        self.assertEqual(failure["recommended_action"], "compact_thread")

    def test_compact_validation_harness_case_records_budget_and_post_compact_continuation(self) -> None:
        case = build_compact_validation_case(
            {
                "id": "deepseek/deepseek-v4-pro",
                "provider": "deepseek",
                "native_model": "deepseek-v4-pro",
                "advertised_context_window": 4096,
                "effective_context_window_percent": 40,
                "auto_compact_token_limit": 900,
                "tool_output_token_limit": 16000,
                "supports_mcp_tools": True,
                "context_compaction_support": {
                    "manual_compact": "app_server_native",
                    "auto_compact": "configured_unverified",
                    "structured_summary_quality": "untested",
                },
            }
        )

        self.assertEqual(case["status"], "pass")
        self.assertEqual(case["capability_id"], "thread.compact")
        self.assertTrue(case["context_window_summary"]["compact_recommended"])
        self.assertEqual(case["context_limit_classification"]["recommended_action"], "compact_thread")
        self.assertEqual(case["post_compact_continuation"]["recommended_action"], "health_check")
        self.assertTrue(case["post_compact_continuation"]["stale_context_estimate"])
        self.assertEqual(case["validated_evidence_preview"]["validation_status"], "pass")
        self.assertIn("dry_run_context_budget_report", case["validated_evidence_preview"]["validation_scope"])
        self.assertNotIn("src/module_000", str(case))

    def test_compact_validation_harness_report_is_matrix_ready_without_raw_prompt_text(self) -> None:
        report = build_compact_validation_report(
            run_id="step12-test",
            created_at="2026-07-05T16:00:00+09:00",
            models=[
                {
                    "id": "qwen/qwen3.7-plus",
                    "provider": "qwen",
                    "native_model": "qwen3.7-plus",
                    "advertised_context_window": 8192,
                    "effective_context_window_percent": 80,
                    "auto_compact_token_limit": 4096,
                    "tool_output_token_limit": 32000,
                    "context_compaction_support": {
                        "manual_compact": "app_server_native",
                        "auto_compact": "configured_unverified",
                        "structured_summary_quality": "untested",
                    },
                },
                {
                    "id": "glm/glm-5.2",
                    "provider": "glm",
                    "native_model": "glm-5.2",
                    "advertised_context_window": 8192,
                    "effective_context_window_percent": 80,
                    "auto_compact_token_limit": 4096,
                    "tool_output_token_limit": 32000,
                    "context_compaction_support": {
                        "manual_compact": "app_server_native",
                        "auto_compact": "configured_unverified",
                        "structured_summary_quality": "untested",
                    },
                },
            ],
        )

        self.assertEqual(report["status"], "pass")
        self.assertEqual(len(report["matrix_updates"]), 2)
        self.assertTrue(all(update["validation_status"] == "pass" for update in report["matrix_updates"]))
        self.assertTrue(all(update["capability_id"] == "thread.compact" for update in report["matrix_updates"]))
        self.assertNotIn("src/module_000", str(report))

    def test_post_compact_continuation_state_requires_health_check_when_compaction_is_newer(self) -> None:
        continuation = post_compact_continuation_state(
            token_last_updated_at="2026-07-05T12:00:00+09:00",
            compacted_at="2026-07-05T12:03:00+09:00",
        )
        self.assertEqual(continuation["level"], "compacted")
        self.assertEqual(continuation["recommended_action"], "health_check")
        self.assertTrue(continuation["stale_context_estimate"])


if __name__ == "__main__":
    unittest.main()
