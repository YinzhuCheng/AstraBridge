from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload  # noqa: E402
from astrabridge_sidecar.model_catalog.generated_catalog import current_generated_catalog  # noqa: E402
from astrabridge_sidecar.providers.reference_cohort import (  # noqa: E402
    REFERENCE_COHORT_SUBJECTS,
    build_reference_cohort_report,
)


CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "provider_semantic_conformance_v1.json"
COHORT_SCRIPT_DIR = Path(__file__).resolve().parents[1] / "skills" / "agentic-update-pipeline" / "scripts"
if str(COHORT_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(COHORT_SCRIPT_DIR))

from run_four_provider_reference_cohort import run_cohort  # noqa: E402


class ProviderReferenceCohortTests(unittest.TestCase):
    def _report(self, *, models: list[dict[str, object]] | None = None) -> dict[str, object]:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            return build_reference_cohort_report(
                catalog_models=models or current_generated_catalog().models,
                semantic_corpus=corpus,
                run_id="reference-cohort-test",
                ledger_root=Path(temp) / "ledgers",
                parser_coverage={
                    "status": "pass",
                    "deterministic": True,
                    "provider_calls_attempted": False,
                    "network_calls_attempted": False,
                    "providers": {subject["provider_id"]: [subject["model_id"]] for subject in REFERENCE_COHORT_SUBJECTS},
                },
            )

    def test_fixed_four_provider_cohort_is_deterministic_and_reduced_without_route_proof(self) -> None:
        report = self._report()
        routes = list(report["routes"])

        self.assertEqual(report["status"], "pass")
        self.assertFalse(report["provider_calls_attempted"])
        self.assertFalse(report["network_calls_attempted"])
        self.assertEqual([route["subject"]["model_id"] for route in routes], [subject["model_id"] for subject in REFERENCE_COHORT_SUBJECTS])
        self.assertEqual(report["classification_summary"], {"verified": 0, "partial": 0, "reduced_authority": 4, "blocked": 0, "deferred": 0})
        for route in routes:
            with self.subTest(model=route["subject"]["model_id"]):
                self.assertEqual(route["classification"], "reduced_authority")
                self.assertEqual(route["route"]["admission"], "review_only")
                self.assertEqual(route["runtime_admission"]["effective_execution_policy"], "no_tools")
                self.assertEqual(route["runtime_admission"]["effective_permission_mode"], "ask")
                self.assertEqual(route["deterministic_validation"]["status"], "pass")
                self.assertTrue(all(check["status"] == "pass" for check in route["deterministic_validation"]["checks"].values()))
                self.assertFalse(route["deterministic_validation"]["checks"]["fallback"]["automatic_fallback"])
                self.assertEqual(route["next_fix"]["next_gate"], "execution_route_adapter_dry_run")

        self.assertEqual(report["kimi_k3_generic_promotion_path"]["status"], "pass")
        self.assertFalse(report["kimi_k3_generic_promotion_path"]["kimi_only_bypass"])
        self.assertEqual(report["codex_control"]["status"], "recorded")
        assert_secret_free_agentic_update_payload(report, label="reference_cohort_test")

    def test_missing_exact_model_is_a_route_level_blocker_not_a_provider_wide_claim(self) -> None:
        models = [
            dict(item)
            for item in current_generated_catalog().models
            if str(item.get("id") or "") != "kimi/kimi-k3"
        ]
        report = self._report(models=models)
        kimi = next(route for route in report["routes"] if route["subject"]["provider_id"] == "kimi")

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(kimi["classification"], "blocked")
        self.assertEqual(kimi["runtime_admission"]["degradation_reasons"], ["catalog_exact_model_missing"])
        self.assertEqual(kimi["next_fix"]["next_gate"], "catalog_exact_model_missing")

    def test_runner_writes_a_normalized_provider_free_run_contract_before_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            report = run_cohort(workspace_root=workspace, run_id="reference-cohort-runner-test")
            contract_path = workspace / "PRIVATE" / "agentic-update-pipeline" / "runs" / "reference-cohort-runner-test" / "run-contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["artifact_paths"]["run_contract"], str(contract_path))
        self.assertEqual(contract["scope"], ["provider_metadata", "provider_adapter", "execution_routes"])
        self.assertEqual(contract["providers"], ["qwen", "deepseek", "kimi", "glm"])
        self.assertFalse(contract["allow_network"])
        self.assertFalse(contract["allow_provider_calls"])
        self.assertEqual(contract["cohort_mode"], "deterministic_provider_free")


if __name__ == "__main__":
    unittest.main()
