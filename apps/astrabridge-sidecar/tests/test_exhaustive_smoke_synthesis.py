from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.exhaustive_smoke_synthesis import (
    EXHAUSTIVE_SMOKE_CASE_MANIFEST_SCHEMA_VERSION,
    build_exhaustive_smoke_case_manifest,
    synthesize_exhaustive_smoke_cases,
)


class ExhaustiveSmokeSynthesisTests(unittest.TestCase):
    def test_synthesis_emits_deterministic_sorted_cases(self) -> None:
        scope_manifest = _fixture_scope_manifest()

        first = build_exhaustive_smoke_case_manifest(
            scope_manifest,
            source_manifest_path="PRIVATE/provider-compatibility/runs/fixture/manifest.json",
            run_id="fixture-run",
            generated_at="2026-07-06T16:00:00+09:00",
        )
        second = build_exhaustive_smoke_case_manifest(
            scope_manifest,
            source_manifest_path="PRIVATE/provider-compatibility/runs/fixture/manifest.json",
            run_id="fixture-run",
            generated_at="2026-07-06T16:00:00+09:00",
        )

        self.assertEqual(first["schema_version"], EXHAUSTIVE_SMOKE_CASE_MANIFEST_SCHEMA_VERSION)
        self.assertEqual(first, second)
        self.assertEqual(first["summary"]["case_count"], 7)
        self.assertEqual(
            [case["lane_group"] for case in first["cases"]],
            ["general_model", "general_model", "general_model", "general_model", "capability", "capability", "compact_handoff"],
        )
        json.dumps(first, ensure_ascii=False)

    def test_synthesis_preserves_explicit_provider_model_targeting_and_route_hints(self) -> None:
        cases = synthesize_exhaustive_smoke_cases(_fixture_scope_manifest())
        capability_case = next(case for case in cases if case["lane_id"] == "qwen/qwen3-vl-plus:vision.analyze")
        unsupported_case = next(case for case in cases if case["lane_id"] == "deepseek/deepseek-v4-pro:speech.synthesize")

        self.assertEqual(capability_case["provider_id"], "qwen")
        self.assertEqual(capability_case["model_id"], "qwen/qwen3-vl-plus")
        self.assertEqual(capability_case["native_model"], "qwen3-vl-plus")
        self.assertEqual(capability_case["capability_id"], "vision.analyze")
        self.assertEqual(capability_case["request_overrides"]["provider_id"], "qwen")
        self.assertEqual(capability_case["request_overrides"]["model"], "qwen3-vl-plus")
        self.assertEqual(capability_case["route_expectation"]["adapter_id"], "qwen.vision.chat.v1")
        self.assertTrue(capability_case["runner_hints"]["explicit_provider_model"])
        self.assertIn("scope_reason:", capability_case["notes"][0])
        self.assertEqual(unsupported_case["scope_decision"], "unsupported")
        self.assertEqual(unsupported_case["execution_policy"], "record_unsupported")
        self.assertEqual(unsupported_case["request_overrides"]["model"], "deepseek-v4-pro")
        self.assertFalse(unsupported_case["runner_hints"]["allow_provider"])

    def test_synthesis_covers_positive_unsupported_and_reduced_authority_paths(self) -> None:
        manifest = build_exhaustive_smoke_case_manifest(
            _fixture_scope_manifest(),
            run_id="fixture-run",
            generated_at="2026-07-06T16:00:00+09:00",
        )

        by_lane_id = {case["lane_id"]: case for case in manifest["cases"]}
        self.assertEqual(by_lane_id["glm/glm-5.2:agent.command_execution"]["scope_decision"], "reduced-authority")
        self.assertEqual(by_lane_id["glm/glm-5.2:agent.command_execution"]["execution_policy"], "confirm_reduced_authority")
        self.assertEqual(by_lane_id["glm/glm-5.2:agent.command_execution"]["runner_kind"], "task_runtime_validation")
        self.assertEqual(by_lane_id["deepseek/deepseek-v4-pro:speech.synthesize"]["scope_decision"], "unsupported")
        self.assertEqual(by_lane_id["openai/gpt-5.5:thread.compact"]["scope_decision"], "skip")
        self.assertEqual(manifest["summary"]["scope_decision_counts"]["run"], 4)
        self.assertEqual(manifest["summary"]["scope_decision_counts"]["unsupported"], 1)
        self.assertEqual(manifest["summary"]["scope_decision_counts"]["reduced-authority"], 1)
        self.assertEqual(manifest["summary"]["scope_decision_counts"]["skip"], 1)
        self.assertFalse(by_lane_id["openai/gpt-5.5:thread.compact"]["runner_hints"]["allow_provider"])

    def test_general_model_lanes_receive_execution_semantics_from_authority_metadata(self) -> None:
        cases = synthesize_exhaustive_smoke_cases(_fixture_scope_manifest())
        by_lane_id = {case["lane_id"]: case for case in cases}

        deepseek_text = by_lane_id["deepseek/deepseek-v4-pro:chat.text_health"]
        self.assertEqual(deepseek_text["request_profile"], "general_text_health_exact_short_answer")
        self.assertEqual(deepseek_text["fixture_id"], "exact_short_text")
        self.assertFalse(deepseek_text["request_overrides"]["stream"])
        self.assertEqual(deepseek_text["runner_hints"]["validation_surface"], "provider_key_test")
        self.assertEqual(deepseek_text["runner_hints"]["expected_signal"], "visible_text")

        deepseek_command = by_lane_id["deepseek/deepseek-v4-pro:agent.command_execution"]
        self.assertEqual(deepseek_command["request_profile"], "general_command_execution_read_only_shell_once")
        self.assertEqual(deepseek_command["fixture_id"], "read_only_shell_once")
        self.assertEqual(deepseek_command["runner_hints"]["validation_surface"], "runtime_turn")
        self.assertEqual(deepseek_command["runner_hints"]["expected_authority_outcome"], "command_execution_required")
        self.assertEqual(deepseek_command["runner_hints"]["success_signal"], "command_execution_required")
        self.assertTrue(deepseek_command["runner_hints"]["supports_tool_calls"])
        self.assertTrue(deepseek_command["runner_hints"]["supports_mcp_tools"])
        self.assertIn("authority_tier: B", deepseek_command["notes"])

        glm_command = by_lane_id["glm/glm-5.2:agent.command_execution"]
        self.assertEqual(glm_command["request_profile"], "general_command_execution_reduced_authority_probe")
        self.assertEqual(glm_command["fixture_id"], "read_only_shell_reduced_authority_probe")
        self.assertEqual(glm_command["runner_hints"]["expected_authority_outcome"], "reduced_authority_confirmation")
        self.assertEqual(glm_command["runner_hints"]["success_signal"], "command_execution_or_explicit_downgrade")
        self.assertFalse(glm_command["runner_hints"]["supports_tool_calls"])

        qwen_edit = by_lane_id["qwen/qwen3.7-plus:agent.edit_apply_patch"]
        self.assertEqual(qwen_edit["request_profile"], "general_edit_apply_patch_authority_probe")
        self.assertEqual(qwen_edit["fixture_id"], "scratch_patch_authority_probe")
        self.assertEqual(qwen_edit["runner_hints"]["expected_authority_outcome"], "authority_probe")
        self.assertEqual(qwen_edit["runner_hints"]["success_signal"], "apply_patch_or_propose_only_downgrade")
        self.assertTrue(qwen_edit["runner_hints"]["reclassification_allowed"])
        self.assertEqual(qwen_edit["runner_hints"]["preferred_edit_operation"], "propose_only_or_runtime_bridge")
        self.assertEqual(qwen_edit["request_overrides"]["permission_mode"], "full")
        self.assertEqual(qwen_edit["request_overrides"]["context_mode"], "no_context")

    def test_adapter_only_capability_lane_keeps_explicit_native_target(self) -> None:
        manifest = {
            "schema_version": "astrabridge-exhaustive-scope-manifest-v1",
            "run_id": "adapter-only",
            "capability_lanes": [
                {
                    "lane_id": "yunwu/gpt-image-2:image.generate:adapter-only",
                    "lane_group": "capability",
                    "lane_kind": "image.generate",
                    "provider_id": "yunwu",
                    "model_id": "yunwu/gpt-image-2",
                    "native_model": "gpt-image-2",
                    "classification": "run",
                    "reason": "Adapter-only image model remains in live scope.",
                    "lane_origin": "capability_adapter_only",
                    "adapter_id": "yunwu.image.generate.v1",
                    "candidate_snapshot": {
                        "provider_id": "yunwu",
                        "model": "gpt-image-2",
                        "adapter_id": "yunwu.image.generate.v1",
                    },
                }
            ],
        }

        cases = synthesize_exhaustive_smoke_cases(manifest, include_lane_groups=["capability"])
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case["model_id"], "yunwu/gpt-image-2")
        self.assertEqual(case["native_model"], "gpt-image-2")
        self.assertEqual(case["request_overrides"]["model"], "gpt-image-2")
        self.assertEqual(case["route_expectation"]["adapter_id"], "yunwu.image.generate.v1")
        self.assertIn("lane_origin: capability_adapter_only", case["notes"])


def _fixture_scope_manifest() -> dict:
    return {
        "schema_version": "astrabridge-exhaustive-scope-manifest-v1",
        "run_id": "step1-fixture",
        "scope_policy": {"definition": "exhaustive_over_current_astrabridge_contract"},
        "general_model_lanes": [
            {
                "lane_id": "deepseek/deepseek-v4-pro:chat.text_health",
                "lane_group": "general_model",
                "lane_kind": "chat.text_health",
                "provider_id": "deepseek",
                "model_id": "deepseek/deepseek-v4-pro",
                "native_model": "deepseek-v4-pro",
                "classification": "run",
                "reason": "Enabled catalog model remains in scope for exhaustive general text-health smoke.",
                "metadata_snapshot": {
                    "authority_tier": "B",
                    "authority_reason": "Model should stay in review/propose mode unless validation or approval promotes the action.",
                    "command_execution_status": "unknown",
                    "parallel_tool_call_status": "serial_only",
                    "tool_support": True,
                    "mcp_support": True,
                },
                "evidence_refs": ["PRIVATE/provider-compatibility/reports/step15-residual-risk-final-readiness-20260705.md"],
            },
            {
                "lane_id": "deepseek/deepseek-v4-pro:agent.command_execution",
                "lane_group": "general_model",
                "lane_kind": "agent.command_execution",
                "provider_id": "deepseek",
                "model_id": "deepseek/deepseek-v4-pro",
                "native_model": "deepseek-v4-pro",
                "classification": "run",
                "reason": "No standing scope exclusion exists; exhaustive batch A should resolve current command/edit behavior for this model.",
                "metadata_snapshot": {
                    "authority_tier": "B",
                    "authority_reason": "Model should stay in review/propose mode unless validation or approval promotes the action.",
                    "command_execution_status": "unknown",
                    "parallel_tool_call_status": "serial_only",
                    "tool_support": True,
                    "mcp_support": True,
                },
                "evidence_refs": ["PRIVATE/provider-compatibility/reports/step15-residual-risk-final-readiness-20260705.md"],
            },
            {
                "lane_id": "glm/glm-5.2:agent.command_execution",
                "lane_group": "general_model",
                "lane_kind": "agent.command_execution",
                "provider_id": "glm",
                "model_id": "glm/glm-5.2",
                "native_model": "glm-5.2",
                "classification": "reduced-authority",
                "reason": "GLM remains reduced-authority until command execution is observed.",
                "metadata_snapshot": {
                    "authority_tier": "C",
                    "authority_reason": "Model has no verified structured tool-calling surface.",
                    "command_execution_status": "partial_no_command_execution",
                    "parallel_tool_call_status": "disabled",
                    "tool_support": False,
                    "mcp_support": False,
                },
                "evidence_refs": ["PRIVATE/provider-compatibility/reports/step11-glm-code-agent-revalidation-20260705.md"],
            },
            {
                "lane_id": "qwen/qwen3.7-plus:agent.edit_apply_patch",
                "lane_group": "general_model",
                "lane_kind": "agent.edit_apply_patch",
                "provider_id": "qwen",
                "model_id": "qwen/qwen3.7-plus",
                "native_model": "qwen3.7-plus",
                "classification": "run",
                "reason": "No standing scope exclusion exists; exhaustive batch A should resolve current command/edit behavior for this model.",
                "metadata_snapshot": {
                    "authority_tier": "C",
                    "authority_reason": "Model has no verified structured tool-calling surface.",
                    "command_execution_status": "unknown",
                    "parallel_tool_call_status": "disabled",
                    "tool_support": False,
                    "mcp_support": False,
                },
                "evidence_refs": ["PRIVATE/provider-compatibility/reports/step15-residual-risk-final-readiness-20260705.md"],
            },
        ],
        "capability_lanes": [
            {
                "lane_id": "qwen/qwen3-vl-plus:vision.analyze",
                "lane_group": "capability",
                "lane_kind": "vision.analyze",
                "provider_id": "qwen",
                "model_id": "qwen/qwen3-vl-plus",
                "native_model": "qwen3-vl-plus",
                "classification": "run",
                "reason": "Declared capability route target for live smoke.",
                "adapter_id": "qwen.vision.chat.v1",
                "candidate_snapshot": {
                    "provider_id": "qwen",
                    "model": "qwen3-vl-plus",
                    "adapter_id": "qwen.vision.chat.v1",
                },
                "evidence_refs": ["PRIVATE/provider-compatibility/reports/step15-residual-risk-final-readiness-20260705.md"],
            },
            {
                "lane_id": "deepseek/deepseek-v4-pro:speech.synthesize",
                "lane_group": "capability",
                "lane_kind": "speech.synthesize",
                "provider_id": "deepseek",
                "model_id": "deepseek/deepseek-v4-pro",
                "native_model": "deepseek-v4-pro",
                "classification": "unsupported",
                "reason": "No current capability-registry route target exists for this provider/model/capability pair.",
                "evidence_refs": [],
            },
        ],
        "compact_handoff_lanes": [
            {
                "lane_id": "openai/gpt-5.5:thread.compact",
                "lane_group": "compact_handoff",
                "lane_kind": "thread.compact",
                "provider_id": "openai",
                "model_id": "openai/gpt-5.5",
                "native_model": "gpt-5.5",
                "classification": "skip",
                "reason": "Official OpenAI direct live verification is explicitly deferred by user direction for this execution slice.",
                "evidence_refs": ["PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md"],
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
