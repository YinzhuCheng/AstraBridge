from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SIDECAR_ROOT.parents[1]
SURFACE_PATH = REPOSITORY_ROOT / "docs" / "PROVIDER_TRUTH_AND_AUTHORITY_SURFACE.md"
CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "provider_semantic_conformance_v1.json"

if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.model_catalog.generated_catalog import current_generated_catalog  # noqa: E402
from astrabridge_sidecar.providers.reference_cohort import (  # noqa: E402
    REFERENCE_COHORT_SUBJECTS,
    build_reference_cohort_report,
)
from astrabridge_sidecar.providers.registry import get_provider_profile  # noqa: E402


class ProviderTruthAuthoritySurfaceTests(unittest.TestCase):
    def _report(self) -> dict[str, object]:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            return build_reference_cohort_report(
                catalog_models=current_generated_catalog().models,
                semantic_corpus=corpus,
                run_id="provider-truth-surface-test",
                ledger_root=Path(temp) / "ledgers",
                parser_coverage={
                    "status": "pass",
                    "deterministic": True,
                    "provider_calls_attempted": False,
                    "network_calls_attempted": False,
                },
            )

    def test_public_metadata_rows_match_current_catalog_and_profiles(self) -> None:
        surface = SURFACE_PATH.read_text(encoding="utf-8")
        models = {str(model.get("id") or ""): model for model in current_generated_catalog().models}

        for subject in REFERENCE_COHORT_SUBJECTS:
            model = models[subject["model_id"]]
            profile = get_provider_profile(subject["provider_id"]).to_default_profile()
            expected_row = (
                f"| `{subject['model_id']}` | `{', '.join(model['input_modalities'])}` | "
                f"`{int(model['advertised_context_window']):,}` advertised | `{profile['wire_api']}` | "
                f"`{profile['reasoning_effort']}` | `documented` |"
            )
            with self.subTest(model=subject["model_id"]):
                self.assertIn(expected_row, surface)

    def test_public_authority_rows_follow_the_provider_free_reference_cohort(self) -> None:
        surface = SURFACE_PATH.read_text(encoding="utf-8")
        report = self._report()

        self.assertFalse(report["provider_calls_attempted"])
        self.assertFalse(report["network_calls_attempted"])
        self.assertEqual(report["live_smoke"]["status"], "deferred")
        for route in report["routes"]:
            subject = route["subject"]
            expected_row = (
                f"| `{subject['model_id']}` | `pass` | `review_only` / `reduced_authority` | "
                "`no_tools` / `ask` | `execution_route_adapter_dry_run` |"
            )
            with self.subTest(model=subject["model_id"]):
                self.assertEqual(route["classification"], "reduced_authority")
                self.assertEqual(route["route"]["admission"], "review_only")
                self.assertEqual(route["runtime_admission"]["effective_execution_policy"], "no_tools")
                self.assertEqual(route["runtime_admission"]["effective_permission_mode"], "ask")
                self.assertEqual(route["next_fix"]["next_gate"], "execution_route_adapter_dry_run")
                self.assertIn(expected_row, surface)

    def test_surface_keeps_kimi_and_live_smoke_claims_evidence_qualified(self) -> None:
        surface = SURFACE_PATH.read_text(encoding="utf-8")

        self.assertIn("Kimi K3 receives no\nbypass", surface)
        self.assertIn("No provider credential is required, read, stored, or sent", surface)
        self.assertIn("current cohort has no verified, experimental,\nor default external coding-route claim", surface)
        self.assertIn(
            "future operation requiring explicit current-turn authorization and a\nsecret-owning runner",
            surface,
        )


if __name__ == "__main__":
    unittest.main()
