from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
SIDECAR_ROOT = Path(__file__).resolve().parents[1]

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload  # noqa: E402
from run_public_quality_reliability_dossier import run_public_quality_reliability_dossier  # noqa: E402


class PublicQualityReliabilityDossierTests(unittest.TestCase):
    def test_dossier_preserves_passes_and_exposes_every_non_pass_card(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _write_inputs(root)
            evidence = run_public_quality_reliability_dossier(root / "dossier", **paths)

        dossier = evidence["dossier"]
        self.assertEqual(evidence["mode"], "deterministic_provider_free")
        self.assertEqual(evidence["provider_calls"], [])
        self.assertFalse(evidence["network_calls_attempted"])
        self.assertEqual(dossier["status"], "pass")
        self.assertEqual(dossier["card_count"], 7)
        self.assertEqual(dossier["positive_card_count"], 3)
        self.assertEqual(dossier["negative_card_count"], 4)
        self.assertEqual(
            {card["claim_id"] for card in dossier["negative_ledger"]},
            {
                "four_provider_reference_routes",
                "first_extension_candidate",
                "security_and_privacy_boundary",
                "package_and_update_baseline",
            },
        )
        self.assertEqual(evidence["input_evidence"]["provider_cohort"]["classification"], "reduced_authority")
        self.assertEqual(evidence["input_evidence"]["extension_candidate"]["widening_boundary"], "blocked")
        self.assertEqual(evidence["input_evidence"]["preview_baseline"]["release_blocker_count"], 5)
        assert_secret_free_agentic_update_payload(evidence, label="public_quality_reliability_dossier")

    def test_dossier_rejects_any_attempt_to_hide_a_public_release_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _write_inputs(root)
            preview = json.loads(paths["preview_baseline_evidence"].read_text(encoding="utf-8"))
            preview["public_release"]["status"] = "pass"
            paths["preview_baseline_evidence"].write_text(json.dumps(preview), encoding="utf-8")

            with self.assertRaisesRegex(AssertionError, "Public release must remain blocked"):
                run_public_quality_reliability_dossier(root / "dossier", **paths)


def _write_inputs(root: Path) -> dict[str, Path]:
    payloads = {
        "flagship_evidence": {
            "schema_version": "astrabridge-flagship-coding-agent-evidence-v1",
            "provider_calls": [],
            "dry_run": {"status": "pass"},
            "failure_exercise": {"status": "failed"},
            "recovery_exercise": {"status": "completed"},
        },
        "provider_cohort_report": {
            "schema_version": "astrabridge-four-provider-reference-cohort-v1",
            "status": "pass",
            "provider_calls_attempted": False,
            "network_calls_attempted": False,
            "live_smoke": {"status": "deferred"},
            "routes": [{"classification": "reduced_authority"} for _ in range(4)],
        },
        "gui_parity_evidence": {
            "schema_version": "astrabridge-gui-code-orchestration-parity-evidence-v1",
            "provider_calls": [],
            "network_calls_attempted": False,
            "code_to_gui": {"status": "pass"},
            "runtime": {"fixture_run_status": "completed"},
            "gui_to_code": {"round_trip_diff_status": "no_change"},
            "authority_boundary": {"blocked_gui_edit": {"status": "blocked_as_expected"}},
        },
        "extension_evidence": {
            "schema_version": "astrabridge-first-contribution-extension-evidence-v1",
            "mode": "deterministic_provider_free",
            "provider_calls": [],
            "network_calls_attempted": False,
            "extension": {"classification": "experimental_candidate"},
            "validation": {"status": "pass"},
            "failure_boundary": {"status": "blocked"},
        },
        "preview_baseline_evidence": {
            "schema_version": "astrabridge-developer-preview-baseline-evidence-v1",
            "mode": "deterministic_provider_free",
            "provider_calls": [],
            "package_contract": {"status": "pass"},
            "update_rehearsal": {"status": "pass"},
            "public_release": {"status": "blocked", "blockers": [{"id": f"blocker-{index}"} for index in range(5)]},
        },
        "security_scan_report": {"ok": True, "counts": {"error": 0, "warning": 0}},
    }
    paths: dict[str, Path] = {}
    for name, payload in payloads.items():
        path = root / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path
    return paths


if __name__ == "__main__":
    unittest.main()
