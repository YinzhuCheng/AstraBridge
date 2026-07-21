from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import astrabridge_sidecar.skill_orchestration_evaluation_gate as evaluation_gate  # noqa: E402


class SkillOrchestrationEvaluationGateTests(unittest.TestCase):
    def test_structural_evaluation_covers_the_finite_builtin_set_without_provider_calls(self) -> None:
        with tempfile.TemporaryDirectory(prefix="astrabridge-skill-eval-") as temp_dir:
            summary = evaluation_gate.run_skill_orchestration_evaluation_gate(
                mode="evaluate",
                artifact_root=Path(temp_dir),
                run_id="structural",
                fixture_runs=False,
            )
            self.assertEqual(summary["status"], "pass")
            self.assertFalse(summary["promotion_ready"])
            self.assertEqual(summary["pattern_count"], 5)
            self.assertEqual(summary["evaluation_policy"]["provider_calls"], 0)
            self.assertEqual(summary["evaluation_policy"]["network_discovery_calls"], 0)
            self.assertTrue(all(item["status"] == "pass" for item in summary["patterns"]))
            for item in summary["patterns"]:
                self.assertEqual(item["fixture"]["outcome"], "disabled_for_test")
                self.assertEqual(item["checks"]["manifest_content_scan"]["status"], "pass")
            artifact_paths = summary["artifact_paths"]
            self.assertTrue(Path(artifact_paths["summary_json"]).exists())
            self.assertTrue(Path(artifact_paths["report_md"]).exists())
            self.assertEqual(json.loads(Path(artifact_paths["summary_json"]).read_text(encoding="utf-8")), summary)

    def test_promotion_mode_fails_closed_for_candidate_skill_without_fixture_completion(self) -> None:
        with tempfile.TemporaryDirectory(prefix="astrabridge-skill-promotion-") as temp_dir:
            summary = evaluation_gate.run_skill_orchestration_evaluation_gate(
                mode="promotion",
                artifact_root=Path(temp_dir),
                run_id="promotion",
                skill_ids=["astrabridge.supervisor-worker-synthesizer"],
                fixture_runs=False,
            )
            self.assertEqual(summary["status"], "fail")
            self.assertFalse(summary["promotion_ready"])
            self.assertIn(
                "astrabridge.supervisor-worker-synthesizer:skill_status_not_productized:candidate",
                summary["promotion_blockers"],
            )
            self.assertIn(
                "astrabridge.supervisor-worker-synthesizer:fixture_not_completed:disabled_for_test",
                summary["promotion_blockers"],
            )

    def test_typed_fixture_outputs_cover_code_diff_and_image_artifact_ports(self) -> None:
        selected = [
            "astrabridge.review-fix-verify",
            "astrabridge.multimodal-capability-adapter",
        ]
        with tempfile.TemporaryDirectory(prefix="astrabridge-skill-fixture-") as temp_dir:
            summary = evaluation_gate.run_skill_orchestration_evaluation_gate(
                mode="evaluate",
                artifact_root=Path(temp_dir),
                run_id="typed-fixtures",
                skill_ids=selected,
                fixture_runs=True,
            )
            self.assertEqual(summary["status"], "pass")
            self.assertTrue(all(item["fixture"]["outcome"] == "completed" for item in summary["patterns"]))
            workspace = Path(summary["artifact_paths"]["workspace_dir"])
            bounded_patch = next(workspace.rglob("node_apply_fix/output.json"))
            input_image = next(workspace.rglob("node_probe_input/output.json"))
            patch_output = json.loads(bounded_patch.read_text(encoding="utf-8"))
            image_output = json.loads(input_image.read_text(encoding="utf-8"))
            self.assertTrue(str(patch_output["typed_output_values"]["bounded_patch"]["artifact_uri"]).startswith("workspace://"))
            self.assertTrue(str(image_output["typed_output_values"]["input_image"]["artifact_uri"]).startswith("workspace://"))
            self.assertTrue((bounded_patch.parent / "bounded_patch.diff").exists())
            self.assertTrue((input_image.parent / "input_image.json").exists())

    def test_injected_resolution_blocker_is_reported_as_a_safety_failure(self) -> None:
        original = evaluation_gate.resolve_skill_to_graph

        def blocked_resolution(*args: object, **kwargs: object) -> dict[str, object]:
            resolution = dict(original(*args, **kwargs))
            resolution["blockers"] = ["injected_safety_blocker"]
            return resolution

        with tempfile.TemporaryDirectory(prefix="astrabridge-skill-blocked-") as temp_dir:
            with patch.object(evaluation_gate, "resolve_skill_to_graph", side_effect=blocked_resolution):
                summary = evaluation_gate.run_skill_orchestration_evaluation_gate(
                    mode="evaluate",
                    artifact_root=Path(temp_dir),
                    run_id="blocked",
                    skill_ids=["astrabridge.supervisor-worker-synthesizer"],
                    fixture_runs=False,
                )
            self.assertEqual(summary["status"], "fail")
            self.assertFalse(summary["promotion_ready"])
            self.assertIn(
                "astrabridge.supervisor-worker-synthesizer:injected_safety_blocker",
                summary["safety_failures"],
            )


if __name__ == "__main__":
    unittest.main()
