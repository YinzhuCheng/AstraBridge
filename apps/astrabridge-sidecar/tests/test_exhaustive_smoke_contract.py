from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.exhaustive_smoke_contract import (
    EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION,
    EXHAUSTIVE_SMOKE_RESULT_SCHEMA_VERSION,
    ExhaustiveSmokeCase,
    ExhaustiveSmokeResult,
    assert_secret_free_exhaustive_smoke_case,
    assert_secret_free_exhaustive_smoke_result,
    default_artifact_expectations,
    default_execution_policy,
    default_fixture_kind,
    default_runner_kind,
    outcome_from_lower_level_status,
)


class ExhaustiveSmokeContractTests(unittest.TestCase):
    def test_capability_case_defaults_align_with_provider_compatibility_smoke(self) -> None:
        case = ExhaustiveSmokeCase.from_any(
            {
                "case_id": "qwen-vision-plus",
                "lane_id": "qwen/qwen3-vl-plus:vision.analyze",
                "lane_group": "capability",
                "lane_kind": "vision.analyze",
                "provider_id": "qwen",
                "model_id": "qwen/qwen3-vl-plus",
                "native_model": "qwen3-vl-plus",
                "capability_id": "vision.analyze",
                "scope_decision": "run",
            }
        )

        self.assertEqual(case.schema_version, EXHAUSTIVE_SMOKE_CASE_SCHEMA_VERSION)
        self.assertEqual(case.execution_policy, "run_live")
        self.assertEqual(case.runner_kind, "provider_compatibility_smoke")
        self.assertEqual(case.fixture_kind, "vision_fixture")
        self.assertEqual(case.runner_hints["mode"], "provider")
        self.assertTrue(case.runner_hints["allow_provider"])
        self.assertEqual(case.artifact_expectations[0].artifact_key, "case_summary")
        self.assertEqual(case.artifact_expectations[1].artifact_key, "visible_text_signal")
        assert_secret_free_exhaustive_smoke_case(case)
        json.dumps(case.to_dict(), ensure_ascii=False)

    def test_general_and_compact_lane_defaults_cover_remaining_families(self) -> None:
        general_case = ExhaustiveSmokeCase.from_any(
            {
                "case_id": "kimi-command",
                "lane_id": "kimi/kimi-k2.7-code:agent.command_execution",
                "lane_group": "general_model",
                "lane_kind": "agent.command_execution",
                "provider_id": "kimi",
                "model_id": "kimi/kimi-k2.7-code",
                "scope_decision": "reduced-authority",
            }
        )
        compact_case = ExhaustiveSmokeCase.from_any(
            {
                "case_id": "deepseek-compact",
                "lane_id": "deepseek/deepseek-v4-pro:thread.compact",
                "lane_group": "compact_handoff",
                "lane_kind": "thread.compact",
                "provider_id": "deepseek",
                "model_id": "deepseek/deepseek-v4-pro",
                "scope_decision": "run",
            }
        )

        self.assertEqual(general_case.execution_policy, "confirm_reduced_authority")
        self.assertEqual(general_case.runner_kind, "task_runtime_validation")
        self.assertEqual(general_case.fixture_kind, "command_execution")
        self.assertEqual(general_case.artifact_expectations[1].artifact_key, "command_execution_signal")
        self.assertEqual(compact_case.runner_kind, "compact_validation")
        self.assertEqual(compact_case.fixture_kind, "long_context_compact")
        self.assertEqual(compact_case.artifact_expectations[1].artifact_key, "compact_summary_signal")

    def test_outcome_mapping_covers_run_skip_unsupported_and_reduced_authority(self) -> None:
        self.assertEqual(outcome_from_lower_level_status("pass", scope_decision="run"), "pass")
        self.assertEqual(outcome_from_lower_level_status("partial", scope_decision="run"), "partial")
        self.assertEqual(outcome_from_lower_level_status("blocked", scope_decision="run"), "fail")
        self.assertEqual(outcome_from_lower_level_status("pass", scope_decision="skip"), "skipped")
        self.assertEqual(outcome_from_lower_level_status("fail", scope_decision="unsupported"), "unsupported")
        self.assertEqual(
            outcome_from_lower_level_status(
                "partial",
                scope_decision="reduced-authority",
                execution_policy="confirm_reduced_authority",
            ),
            "reduced-authority",
        )
        self.assertEqual(
            outcome_from_lower_level_status(
                "pass",
                scope_decision="reduced-authority",
                execution_policy="confirm_reduced_authority",
            ),
            "pass",
        )

    def test_result_serialization_is_secret_free_and_uses_expected_defaults(self) -> None:
        result = ExhaustiveSmokeResult.from_any(
            {
                "case_id": "yunwu-image",
                "lane_id": "yunwu/gpt-image-2:image.generate",
                "lane_group": "capability",
                "lane_kind": "image.generate",
                "provider_id": "yunwu",
                "model_id": "yunwu/gpt-image-2",
                "capability_id": "image.generate",
                "scope_decision": "run",
                "runner_kind": "provider_compatibility_smoke",
                "lower_level_status": "pass",
                "route_observed": {"provider_id": "yunwu", "model": "gpt-image-2", "adapter_id": "yunwu.image.generate.v1"},
                "artifact_observations": [
                    {
                        "artifact_key": "image_artifact",
                        "artifact_type": "image_file",
                        "status": "pass",
                        "observed": True,
                        "path": "D:/AstraBridge/PRIVATE/provider-compatibility/fake-image.png",
                    },
                    {
                        "artifact_key": "asset_manifest",
                        "artifact_type": "manifest",
                        "status": "pass",
                        "observed": True,
                        "path": "D:/AstraBridge/PRIVATE/provider-compatibility/asset_manifest.json",
                    },
                ],
                "evidence_paths": [
                    "PRIVATE/provider-compatibility/runs/example/cases/yunwu-image.json",
                    "PRIVATE/provider-compatibility/runs/example/summary.json",
                ],
            }
        )

        self.assertEqual(result.schema_version, EXHAUSTIVE_SMOKE_RESULT_SCHEMA_VERSION)
        self.assertEqual(result.outcome, "pass")
        self.assertEqual(result.execution_policy, "run_live")
        self.assertEqual(result.artifact_observations[0].status, "pass")
        assert_secret_free_exhaustive_smoke_result(result)
        json.dumps(result.to_dict(), ensure_ascii=False)

    def test_contract_rejects_secret_like_case_content(self) -> None:
        with self.assertRaisesRegex(ValueError, "Secret-like (field name|value) detected"):
            ExhaustiveSmokeCase.from_any(
                {
                    "case_id": "bad-case",
                    "lane_id": "qwen/qwen3-vl-plus:vision.analyze",
                    "lane_group": "capability",
                    "lane_kind": "vision.analyze",
                    "provider_id": "qwen",
                    "model_id": "qwen/qwen3-vl-plus",
                    "native_model": "qwen3-vl-plus",
                    "capability_id": "vision.analyze",
                    "request_overrides": {"authorization": "Bearer abcdefghijklmnopqrstuvwxyz"},
                }
            )

    def test_default_helpers_cover_known_lane_kinds(self) -> None:
        self.assertEqual(default_execution_policy("skip"), "skip_case")
        self.assertEqual(default_execution_policy("unsupported"), "record_unsupported")
        self.assertEqual(default_execution_policy("reduced-authority"), "confirm_reduced_authority")
        self.assertEqual(default_runner_kind("capability", "speech.synthesize"), "provider_compatibility_smoke")
        self.assertEqual(default_runner_kind("compact_handoff", "thread.compact"), "compact_validation")
        self.assertEqual(default_fixture_kind("general_model", "chat.text_health"), "text_health")
        self.assertEqual(default_fixture_kind("capability", "speech.transcribe"), "audio_fixture")
        expectations = default_artifact_expectations("capability", "speech.synthesize")
        self.assertEqual(expectations[1]["artifact_key"], "audio_artifact")
        self.assertEqual(expectations[2]["artifact_key"], "transcript_sidecar")


if __name__ == "__main__":
    unittest.main()
