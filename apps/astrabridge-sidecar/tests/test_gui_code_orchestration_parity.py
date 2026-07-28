from __future__ import annotations

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
from run_gui_code_orchestration_parity import run_gui_code_orchestration_parity  # noqa: E402


class GuiCodeOrchestrationParityTests(unittest.TestCase):
    def test_reference_preserves_canonical_semantics_and_source_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = run_gui_code_orchestration_parity(Path(temp_dir) / "parity")

        self.assertEqual(evidence["mode"], "deterministic_provider_free")
        self.assertEqual(evidence["provider_calls"], [])
        self.assertFalse(evidence["network_calls_attempted"])
        self.assertEqual(evidence["reference"]["graph_id"], "graph_code_fix_review_v1")
        self.assertEqual(evidence["reference"]["template_id"], "code_fix_test_review")
        self.assertEqual(evidence["code_to_gui"]["status"], "pass")
        self.assertTrue(evidence["code_to_gui"]["semantic_projection_matches"])
        self.assertEqual(evidence["code_to_gui"]["gui_surface"]["node_count"], 4)
        self.assertEqual(evidence["code_to_gui"]["gui_surface"]["edge_count"], 3)
        self.assertEqual(
            evidence["code_to_gui"]["gui_surface"]["node_labels"],
            ["Plan Fix", "Apply Code Fix", "Run Tests", "Review Result"],
        )
        self.assertEqual(evidence["runtime"]["dry_run_status"], "pass")
        self.assertEqual(evidence["runtime"]["fixture_run_status"], "completed")
        self.assertEqual(evidence["authority_boundary"]["blocked_gui_edit"]["status"], "blocked_as_expected")
        self.assertEqual(evidence["authority_boundary"]["blocked_gui_edit"]["error"], "graph_source_owned")
        self.assertTrue(evidence["authority_boundary"]["permission_boundary"]["requires_human_approval"])
        self.assertEqual(
            evidence["authority_boundary"]["permission_boundary"]["approval_kind"],
            "filesystem_write_gate",
        )
        self.assertEqual(evidence["gui_to_code"]["status"], "pass")
        self.assertEqual(evidence["gui_to_code"]["round_trip_diff_status"], "no_change")
        self.assertEqual(evidence["gui_to_code"]["round_trip_change_count"], 0)
        assert_secret_free_agentic_update_payload(evidence, label="gui_code_orchestration_parity")


if __name__ == "__main__":
    unittest.main()
