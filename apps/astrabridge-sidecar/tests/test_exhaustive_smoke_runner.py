from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.common import read_json
from astrabridge_sidecar.exhaustive_smoke_runner import (
    EXHAUSTIVE_SMOKE_BATCH_MANIFEST_SCHEMA_VERSION,
    EXHAUSTIVE_SMOKE_BATCH_PLAN_SCHEMA_VERSION,
    build_exhaustive_smoke_batch_manifest,
    build_exhaustive_smoke_batch_plan,
    execute_exhaustive_smoke_batch,
    materialize_exhaustive_smoke_run,
    run_exhaustive_smoke_preflight,
)


class ExhaustiveSmokeRunnerTests(unittest.TestCase):
    def test_build_batch_plan_groups_execution_families_and_chunks(self) -> None:
        manifest = _fixture_case_manifest()

        plan = build_exhaustive_smoke_batch_plan(
            manifest,
            run_id="fixture-run",
            generated_at="2026-07-06T18:00:00+09:00",
            batch_size=2,
        )

        self.assertEqual(plan["schema_version"], EXHAUSTIVE_SMOKE_BATCH_PLAN_SCHEMA_VERSION)
        self.assertEqual(plan["summary"]["case_count"], 7)
        self.assertEqual(plan["summary"]["batch_count"], 5)
        batches = {batch["batch_id"]: batch for batch in plan["batches"]}
        self.assertIn("batch-a-general-model-01", batches)
        self.assertIn("batch-a-general-model-02", batches)
        self.assertIn("batch-b-vision-analyze-01", batches)
        self.assertIn("batch-e-image-generate-01", batches)
        self.assertEqual(batches["batch-a-general-model-01"]["summary"]["case_count"], 2)
        self.assertEqual(batches["batch-a-general-model-02"]["summary"]["case_count"], 1)
        self.assertEqual(batches["batch-f-continuation-01"]["step_id"], "11")
        json.dumps(plan, ensure_ascii=False)

    def test_execute_nonlive_batch_persists_results_and_resumes_remaining_cases(self) -> None:
        manifest = _fixture_case_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            materialized = materialize_exhaustive_smoke_run(
                manifest,
                run_dir=run_dir,
                run_id="fixture-run",
                generated_at="2026-07-06T18:00:00+09:00",
                batch_size=2,
            )
            image_batch = next(batch for batch in materialized["batch_plan"]["batches"] if batch["batch_id"] == "batch-e-image-generate-01")

            first = execute_exhaustive_smoke_batch(image_batch, run_dir=run_dir, max_cases=1)
            self.assertEqual(first["executed_case_ids"], ["case-image-unsupported"])
            self.assertEqual(first["deferred_case_ids"], ["case-image-skip"])
            state_after_first = read_json(run_dir / "run-state.json", {})
            self.assertEqual(state_after_first["completed_case_count"], 1)
            self.assertEqual(state_after_first["resume_markers"]["next_batch_id"], "batch-a-general-model-01")

            second = execute_exhaustive_smoke_batch(image_batch, run_dir=run_dir)
            self.assertEqual(second["executed_case_ids"], ["case-image-skip"])
            self.assertEqual(second["resumed_case_ids"], ["case-image-unsupported"])
            case_one = read_json(run_dir / "batches" / "batch-e-image-generate-01" / "cases" / "case-image-unsupported.json", {})
            case_two = read_json(run_dir / "batches" / "batch-e-image-generate-01" / "cases" / "case-image-skip.json", {})
            self.assertEqual(case_one["outcome"], "unsupported")
            self.assertEqual(case_two["outcome"], "skipped")
            self.assertIn("unsupported", case_one["reasons"][0].lower())
            batch_summary = read_json(run_dir / "batches" / "batch-e-image-generate-01" / "summary.json", {})
            self.assertEqual(batch_summary["batch_status"]["status"], "completed")

    def test_execute_runnable_batch_uses_executor_and_preserves_reduced_authority_outcome(self) -> None:
        batch = build_exhaustive_smoke_batch_manifest(
            [
                _case(
                    "case-run",
                    lane_group="general_model",
                    lane_kind="agent.command_execution",
                    provider_id="deepseek",
                    model_id="deepseek/deepseek-v4-pro",
                    scope_decision="run",
                ),
                _case(
                    "case-reduced",
                    lane_group="general_model",
                    lane_kind="agent.command_execution",
                    provider_id="glm",
                    model_id="glm/glm-5.2",
                    scope_decision="reduced-authority",
                ),
            ],
            run_id="fixture-run",
            generated_at="2026-07-06T18:00:00+09:00",
            batch_id="batch-a-general-model-01",
            family_id="batch-a-general-model",
            family_label="Batch A",
            step_id="6",
            source_case_manifest={"run_id": "fixture-cases"},
            selection_policy={"lane_group": "general_model", "batch_size": 2, "chunk_index": 1, "chunk_count": 1},
        )
        calls: list[str] = []

        def fake_executor(case: dict) -> dict:
            calls.append(str(case.get("case_id") or ""))
            if str(case.get("case_id")) == "case-run":
                return {"lower_level_status": "pass", "reasons": [], "notes": ["fake_executor"]}
            return {"lower_level_status": "partial", "reasons": ["command not observed"], "notes": ["fake_executor"]}

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            materialize_exhaustive_smoke_run(
                {"run_id": "fixture-run", "cases": batch["cases"], "source_manifest": {}, "scope_policy": {}},
                run_dir=run_dir,
                run_id="fixture-run",
                generated_at="2026-07-06T18:00:00+09:00",
                batch_size=5,
            )

            first = execute_exhaustive_smoke_batch(batch, run_dir=run_dir, executor=fake_executor, max_cases=1)
            second = execute_exhaustive_smoke_batch(batch, run_dir=run_dir, executor=fake_executor)

            self.assertEqual(first["executed_case_ids"], ["case-run"])
            self.assertEqual(second["executed_case_ids"], ["case-reduced"])
            self.assertEqual(second["resumed_case_ids"], ["case-run"])
            self.assertEqual(calls, ["case-run", "case-reduced"])
            run_result = read_json(run_dir / "batches" / "batch-a-general-model-01" / "cases" / "case-run.json", {})
            reduced_result = read_json(run_dir / "batches" / "batch-a-general-model-01" / "cases" / "case-reduced.json", {})
            self.assertEqual(run_result["outcome"], "pass")
            self.assertEqual(reduced_result["outcome"], "reduced-authority")

    def test_preflight_summarizes_session_and_provider_availability(self) -> None:
        manifest = _fixture_case_manifest()
        responses = {
            "http://sidecar/api/health": {
                "service": "astrabridge-sidecar",
                "sidecar": {"listen_port": 8791},
                "runtime": {"running": True},
                "router": {"running": True, "provider_count": 5, "model_count": 18},
            },
            "http://sidecar/api/llm-manager/session": {
                "mode": "managed_user",
                "username": "astra",
                "unlocked": True,
                "key_count": 2,
                "active_key_ids": {"deepseek": "k1", "glm": "k2"},
            },
            "http://sidecar/api/profiles": {
                "profiles": [
                    {"provider_id": "deepseek", "profile_id": "deepseek-default"},
                    {"provider_id": "glm", "profile_id": "glm-default"},
                ]
            },
        }

        def fake_get(url: str) -> dict:
            return dict(responses[url])

        with tempfile.TemporaryDirectory() as tmp:
            preflight = run_exhaustive_smoke_preflight(
                manifest,
                run_dir=Path(tmp),
                sidecar_base_url="http://sidecar",
                http_get_json=fake_get,
            )

        self.assertTrue(preflight["ok"])
        checks = {item["check_id"]: item for item in preflight["checks"]}
        self.assertEqual(checks["sidecar_reachability"]["status"], "pass")
        self.assertEqual(checks["managed_vault_session"]["status"], "pass")
        self.assertEqual(checks["provider_availability"]["status"], "pass")
        self.assertEqual(checks["provider_availability"]["details"]["expected_provider_ids"], ["deepseek", "glm"])

    def test_executor_exception_persists_fail_result(self) -> None:
        batch = build_exhaustive_smoke_batch_manifest(
            [
                _case(
                    "case-runtime-fail",
                    lane_group="general_model",
                    lane_kind="agent.edit_apply_patch",
                    provider_id="deepseek",
                    model_id="deepseek/deepseek-v4-pro",
                    scope_decision="run",
                )
            ],
            run_id="fixture-run",
            generated_at="2026-07-06T18:00:00+09:00",
            batch_id="batch-a-general-model-01",
            family_id="batch-a-general-model",
            family_label="Batch A",
            step_id="6",
            source_case_manifest={"run_id": "fixture-cases"},
            selection_policy={"lane_group": "general_model", "batch_size": 1, "chunk_index": 1, "chunk_count": 1},
        )

        def failing_executor(case: dict) -> dict:
            raise RuntimeError(f"boom:{case['case_id']}")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            materialize_exhaustive_smoke_run(
                {"run_id": "fixture-run", "cases": batch["cases"], "source_manifest": {}, "scope_policy": {}},
                run_dir=run_dir,
                run_id="fixture-run",
                generated_at="2026-07-06T18:00:00+09:00",
                batch_size=5,
            )
            execute_exhaustive_smoke_batch(batch, run_dir=run_dir, executor=failing_executor)
            result = read_json(run_dir / "batches" / "batch-a-general-model-01" / "cases" / "case-runtime-fail.json", {})
            self.assertEqual(result["outcome"], "fail")
            self.assertIn("boom:case-runtime-fail", result["reasons"][0])


def _fixture_case_manifest() -> dict:
    return {
        "schema_version": "astrabridge-exhaustive-smoke-case-manifest-v1",
        "run_id": "fixture-cases",
        "generated_at": "2026-07-06T18:00:00+09:00",
        "case_schema_version": "astrabridge-exhaustive-smoke-case-v1",
        "source_manifest": {"run_id": "step1-fixture", "path": "PRIVATE/provider-compatibility/runs/fixture/manifest.json"},
        "scope_policy": {"definition": "fixture"},
        "cases": [
            _case("case-text", lane_group="general_model", lane_kind="chat.text_health", provider_id="deepseek", model_id="deepseek/deepseek-v4-pro", scope_decision="run"),
            _case("case-command", lane_group="general_model", lane_kind="agent.command_execution", provider_id="glm", model_id="glm/glm-5.2", scope_decision="reduced-authority"),
            _case("case-edit", lane_group="general_model", lane_kind="agent.edit_apply_patch", provider_id="openai", model_id="openai/gpt-5.5", scope_decision="skip"),
            _case("case-vision", lane_group="capability", lane_kind="vision.analyze", provider_id="deepseek", model_id="deepseek/deepseek-v4-pro", scope_decision="unsupported"),
            _case("case-image-unsupported", lane_group="capability", lane_kind="image.generate", provider_id="deepseek", model_id="deepseek/deepseek-v4-pro", scope_decision="unsupported"),
            _case("case-image-skip", lane_group="capability", lane_kind="image.generate", provider_id="openai", model_id="openai/gpt-5.5", scope_decision="skip"),
            _case("case-compact", lane_group="compact_handoff", lane_kind="thread.compact", provider_id="deepseek", model_id="deepseek/deepseek-v4-pro", scope_decision="run"),
        ],
    }


def _case(
    case_id: str,
    *,
    lane_group: str,
    lane_kind: str,
    provider_id: str,
    model_id: str,
    scope_decision: str,
) -> dict:
    native_model = model_id.split("/", 1)[1] if "/" in model_id else model_id
    payload = {
        "schema_version": "astrabridge-exhaustive-smoke-case-v1",
        "case_id": case_id,
        "lane_id": f"{model_id}:{lane_kind}",
        "lane_group": lane_group,
        "lane_kind": lane_kind,
        "provider_id": provider_id,
        "model_id": model_id,
        "native_model": native_model,
        "scope_decision": scope_decision,
        "request_profile": "fixture",
        "request_overrides": {"provider_id": provider_id, "model": native_model},
        "route_expectation": {"provider_id": provider_id, "model": native_model},
        "runner_hints": {"scope_reason": f"{scope_decision} fixture"},
        "notes": [f"scope_reason: {scope_decision} fixture"],
    }
    if lane_group == "capability":
        payload["capability_id"] = lane_kind
    return payload


if __name__ == "__main__":
    unittest.main()
