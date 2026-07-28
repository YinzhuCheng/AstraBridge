from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.coding_kernel import (  # noqa: E402
    ContextSection,
    build_context_budget,
    build_context_compaction_handoff_contract,
)
from astrabridge_sidecar.modal_service import ModalService  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.runtime_service import ContextBudgetPreflightError, RuntimeService  # noqa: E402


class EndpointAwareContextBudgetTests(unittest.TestCase):
    def test_report_records_endpoint_reserves_and_every_dropped_or_truncated_section(self) -> None:
        _text, report = build_context_budget(
            sections=[
                ContextSection("prompt", "Turn Prompt", 0, "p" * 800, essential=True),
                ContextSection("critical", "Critical Continuity", 1, "c" * 1_200, essential=True),
                ContextSection("file_map", "File Map", 2, "f" * 2_400),
            ],
            provider_id="deepseek",
            model_id="deepseek-v4-pro",
            context_window=1_100,
            effective_context_window_percent=100,
            auto_compact_token_limit=1_100,
            tool_schema_token_estimate=0,
            endpoint_protocol="chat",
            endpoint_fingerprint="endpointdigest123",
            endpoint_protocol_overhead_tokens=128,
            endpoint_overhead_status="verified",
            advertised_context_window_status="verified",
            attachments=[{"kind": "image", "size": 2_048}],
            supported_modalities=["text", "image"],
            output_reserve_tokens=128,
        )

        payload = report.to_dict()

        self.assertEqual(payload["schema_version"], "astrabridge-context-budget-v2")
        self.assertEqual(payload["advertised_context_window_tokens"], 1_100)
        self.assertEqual(payload["endpoint_protocol"], "chat")
        self.assertEqual(payload["endpoint_protocol_overhead_tokens"], 128)
        self.assertGreater(payload["attachment_modality_token_estimate"], 0)
        self.assertEqual(payload["output_reserve_tokens"], 128)
        self.assertIn("critical", payload["truncated_section_ids"])
        self.assertIn("file_map", payload["dropped_section_ids"])
        self.assertIn("essential_context_section_exceeds_safe_budget", payload["preflight_reasons"])
        self.assertEqual(payload["preflight_admission"], "blocked")
        self.assertEqual(payload["calculation_basis"]["endpoint"]["fingerprint"], "endpointdigest123")
        self.assertTrue(
            any(item["section_id"] == "critical" and item["truncated"] for item in payload["section_estimates"])
        )

    def test_unknown_budget_fails_closed_without_selecting_context(self) -> None:
        selected, report = build_context_budget(
            sections=[ContextSection("prompt", "Turn Prompt", 0, "short turn", essential=True)],
            provider_id="unknown",
            model_id="unknown-model",
            context_window=None,
            endpoint_protocol=None,
        )

        payload = report.to_dict()

        self.assertEqual(selected, "")
        self.assertEqual(payload["preflight_admission"], "downgrade_required")
        self.assertFalse(payload["safe_context_budget_established"])
        self.assertIsNone(payload["usable_prompt_budget_tokens"])
        self.assertIn("advertised_context_window_unknown", payload["preflight_reasons"])
        self.assertIn("endpoint_protocol_unknown", payload["preflight_reasons"])

    def test_constrained_long_context_preflight_compacts_then_produces_safe_neutral_handoff_contract(self) -> None:
        _source_text, source_report = build_context_budget(
            sections=[
                ContextSection("prompt", "Turn Prompt", 0, "Continue the coding task safely.", essential=True),
                ContextSection("task", "Neutral Task State", 1, "task state " * 20, essential=True),
                ContextSection("history", "History", 2, "history detail " * 900),
                ContextSection("file_map", "File Map", 3, "src/file.py\n" * 900),
            ],
            provider_id="deepseek",
            model_id="deepseek-v4-pro",
            context_window=4_096,
            effective_context_window_percent=40,
            auto_compact_token_limit=900,
            tool_schema_token_estimate=300,
            endpoint_protocol="chat",
            endpoint_fingerprint="sourceendpointdigest",
            endpoint_overhead_status="verified",
            advertised_context_window_status="verified",
            output_reserve_tokens=128,
        )
        _target_text, target_report = build_context_budget(
            sections=[ContextSection("neutral_summary", "Neutral Summary", 0, "safe neutral handoff", essential=True)],
            provider_id="kimi",
            model_id="kimi-k3",
            context_window=8_192,
            effective_context_window_percent=80,
            auto_compact_token_limit=4_096,
            tool_schema_token_estimate=300,
            endpoint_protocol="chat",
            endpoint_fingerprint="targetendpointdigest",
            endpoint_overhead_status="verified",
            advertised_context_window_status="verified",
            output_reserve_tokens=512,
        )

        contract = build_context_compaction_handoff_contract(
            source_route={
                "provider_id": "deepseek",
                "model_id": "deepseek-v4-pro",
                "endpoint_fingerprint": "sourceendpointdigest",
                "adapter_signature": "sourceadapterdigest",
            },
            target_route={
                "provider_id": "kimi",
                "model_id": "kimi-k3",
                "endpoint_fingerprint": "targetendpointdigest",
                "adapter_signature": "targetadapterdigest",
            },
            source_budget_report=source_report.to_dict(),
            target_budget_report=target_report.to_dict(),
        )

        self.assertEqual(source_report.to_dict()["preflight_admission"], "admitted_after_compaction")
        self.assertTrue(source_report.to_dict()["compact_recommended"])
        self.assertTrue(contract["target_compatible"])
        self.assertEqual(contract["status"], "ready_after_source_compaction")
        self.assertEqual(contract["summary_provenance"]["cross_route_reasoning_replay"], "forbidden")
        self.assertIn("opaque_provider_reasoning", contract["summary_provenance"]["forbidden_content"])
        self.assertGreaterEqual(contract["summary_provenance"]["target_summary_token_budget"], 128)
        self.assertNotIn("history detail", str(contract))

    def test_runtime_preflight_compacts_injected_context_but_blocks_unknown_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Budget", root / "budget.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root))
            profile = {
                "profile_id": "deepseek-test",
                "provider_id": "deepseek",
                "model": "deepseek-v4-pro",
                "wire_api": "chat",
                "context_window": 4_096,
                "effective_context_window_percent": 40,
                "auto_compact_token_limit": 900,
                "input_modalities": ["text"],
            }
            inputs = [
                {"type": "text", "text": "Fix the failing test.", "text_elements": []},
                {"type": "text", "text": "injected project context " * 1_000, "text_elements": []},
            ]

            prepared, report = runtime._apply_context_budget_preflight(  # noqa: SLF001
                inputs,
                profile=profile,
                runtime_status=profile,
                model="deepseek-v4-pro",
                thread_id="thread-budget",
                attachments=[],
                context_mode="default",
            )

            self.assertEqual(report["preflight_admission"], "admitted_after_compaction")
            self.assertEqual([item["text"] for item in prepared if item["type"] == "text"], ["Fix the failing test."])
            with self.assertRaises(ContextBudgetPreflightError) as raised:
                runtime._apply_context_budget_preflight(  # noqa: SLF001
                    [{"type": "text", "text": "Do work.", "text_elements": []}],
                    profile={"provider_id": "unmapped", "model": "unknown", "wire_api": "custom"},
                    runtime_status=None,
                    model="unknown",
                    thread_id="thread-unknown",
                    attachments=[],
                    context_mode="default",
                )
            self.assertEqual(raised.exception.report["preflight_admission"], "downgrade_required")


if __name__ == "__main__":
    unittest.main()
