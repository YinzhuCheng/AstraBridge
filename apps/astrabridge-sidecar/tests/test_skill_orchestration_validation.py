from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.skill_orchestration_validation import (  # noqa: E402
    SKILL_GRAPH_RESOLUTION_SCHEMA_VERSION,
    SKILL_ORCHESTRATION_VALIDATION_SCHEMA_VERSION,
    compile_skill_orchestration,
    diff_skill_orchestrations,
    dry_run_skill_orchestration,
    lint_skill_orchestration,
    load_skill_orchestration_manifest,
    render_skill_orchestration_report_markdown,
    resolve_skill_to_graph,
    validate_skill_orchestration,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


PARAMETERS = {
    "astrabridge-supervisor-worker-synthesizer": {"task_goal": "Bound a worker task."},
    "astrabridge-review-fix-verify": {
        "task_goal": "Bound a small fix.",
        "target_files": ["README.md"],
        "test_command": "python -m unittest",
    },
    "astrabridge-fanout-research-synthesis": {
        "research_goal": "Bound a research question.",
        "branch_scopes": ["official docs", "compatibility notes"],
    },
    "astrabridge-provider-update-smoke": {
        "update_goal": "Qualify a catalog update.",
        "provider_ids": ["qwen"],
        "smoke_cases": ["catalog"],
        "promotion_owner": "owner",
    },
    "agentic-update-pipeline": {
        "update_goal": "Discover official provider changes and produce proposal-only evidence.",
        "provider_ids": ["qwen", "deepseek", "kimi", "glm"],
        "model_ids": ["qwen3.7-plus", "deepseek-v4-pro", "kimi-k3", "glm-5.2"],
        "smoke_cases": ["provider-free proposal validation"],
        "promotion_owner": "manual-review",
    },
    "astrabridge-multimodal-capability-adapter": {
        "task_goal": "Adapt one image request.",
        "capability_id": "vision.analyze",
        "input_artifacts": [{"kind": "image", "ref": "artifact.image"}],
        "desired_output": "structured result",
    },
}


class SkillOrchestrationValidationTests(unittest.TestCase):
    def test_all_candidate_skills_resolve_to_one_canonical_graph_with_stable_digests(self) -> None:
        for skill_id, parameters in PARAMETERS.items():
            with self.subTest(skill_id=skill_id):
                manifest = load_skill_orchestration_manifest(skill_id)
                first = resolve_skill_to_graph(skill_id, parameters)
                second = resolve_skill_to_graph(skill_id, parameters)
                self.assertEqual(manifest["status"], "candidate")
                self.assertEqual(first["schema_version"], SKILL_GRAPH_RESOLUTION_SCHEMA_VERSION)
                self.assertNotEqual(first["blockers"], ["placeholder"])
                self.assertEqual(first["status"], "candidate")
                self.assertIsInstance(first["canonical_graph"], dict)
                self.assertEqual(first["canonical_graph"]["schema_version"], "astrabridge-agent-orchestration-graph-v1")
                self.assertEqual(first["manifest_digest"], second["manifest_digest"])
                self.assertEqual(first["graph_digest"], second["graph_digest"])
                self.assertEqual(first["provenance"]["live_provider_calls"], 0)
                self.assertEqual(first["provenance"]["mcp_calls"], 0)
                self.assertEqual(first["provenance"]["agent_invocations"], 0)
                binding = first["provider_a2a_binding"]
                self.assertIsInstance(binding, dict)
                self.assertIn(binding["status"], {"downgraded", "qualified"})
                self.assertEqual(binding["provenance"]["provider_calls"], 0)
                self.assertEqual(binding["provenance"]["network_discovery_calls"], 0)

    def test_lint_compile_and_dry_run_reuse_canonical_check_owners(self) -> None:
        lint = lint_skill_orchestration("astrabridge-review-fix-verify", PARAMETERS["astrabridge-review-fix-verify"])
        compile_report = compile_skill_orchestration("astrabridge-review-fix-verify", PARAMETERS["astrabridge-review-fix-verify"])
        dry_run = dry_run_skill_orchestration("astrabridge-review-fix-verify", PARAMETERS["astrabridge-review-fix-verify"])
        self.assertEqual(lint["schema_version"], SKILL_ORCHESTRATION_VALIDATION_SCHEMA_VERSION)
        self.assertEqual(lint["status"], "pass")
        self.assertEqual(lint["checks"]["lint"]["status"], "pass")
        self.assertEqual(compile_report["checks"]["compile"]["status"], "pass")
        self.assertEqual(dry_run["checks"]["dry_run"]["status"], "pass")
        self.assertIn("Graph digest", render_skill_orchestration_report_markdown(lint))

    def test_provider_smoke_dry_run_accepts_long_lived_manual_gate_without_executing_it(self) -> None:
        report = dry_run_skill_orchestration(
            "astrabridge-provider-update-smoke",
            PARAMETERS["astrabridge-provider-update-smoke"],
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["resolution"]["provenance"]["live_provider_calls"], 0)

    def test_missing_unknown_and_secret_parameters_fail_closed_without_echoing_values(self) -> None:
        missing = resolve_skill_to_graph("astrabridge-supervisor-worker-synthesizer", {})
        self.assertTrue(any("required property" in item for item in missing["blockers"]))
        unknown = resolve_skill_to_graph(
            "astrabridge-supervisor-worker-synthesizer",
            {"task_goal": "ok", "unexpected": "value"},
        )
        self.assertTrue(any("parameter_not_declared" in item for item in unknown["blockers"]))
        secret_value = "Authorization: Bearer abcdefghijklmnop"
        secret = resolve_skill_to_graph(
            "astrabridge-supervisor-worker-synthesizer",
            {"task_goal": secret_value},
        )
        self.assertTrue(any("secret_like_content" in item for item in secret["blockers"]))
        self.assertNotIn(secret_value, json.dumps(secret, ensure_ascii=False))

    def test_unknown_template_unsafe_policy_and_policy_widening_are_actionable(self) -> None:
        manifest = load_skill_orchestration_manifest("astrabridge-supervisor-worker-synthesizer")
        unknown_template = copy.deepcopy(manifest)
        unknown_template["resolution"]["graph_template_ref"] = "not_a_template"
        unknown_report = resolve_skill_to_graph(unknown_template, PARAMETERS["astrabridge-supervisor-worker-synthesizer"])
        self.assertTrue(any("unknown graph_template_ref" in item for item in unknown_report["blockers"]))

        unsafe = copy.deepcopy(manifest)
        unsafe["policies"]["subagent"]["allow_nested_subagents"] = True
        unsafe_report = resolve_skill_to_graph(unsafe, PARAMETERS["astrabridge-supervisor-worker-synthesizer"])
        self.assertTrue(any("manifest_schema" in item or "nested_subagents" in item for item in unsafe_report["blockers"]))

        widened_route = resolve_skill_to_graph(
            "astrabridge-supervisor-worker-synthesizer",
            PARAMETERS["astrabridge-supervisor-worker-synthesizer"],
            requested_route={"provider_id": "glm"},
        )
        self.assertTrue(any("widens_provider" in item for item in widened_route["blockers"]))
        widened_budget = resolve_skill_to_graph(
            "astrabridge-review-fix-verify",
            PARAMETERS["astrabridge-review-fix-verify"],
            requested_budget={"max_total_agents": 1},
        )
        self.assertTrue(any("exceeds_total_agents" in item for item in widened_budget["blockers"]))

    def test_diff_tracks_graph_and_parameter_changes_without_raw_values(self) -> None:
        unchanged = diff_skill_orchestrations(
            "astrabridge-supervisor-worker-synthesizer",
            "astrabridge-supervisor-worker-synthesizer",
            PARAMETERS["astrabridge-supervisor-worker-synthesizer"],
            PARAMETERS["astrabridge-supervisor-worker-synthesizer"],
        )
        self.assertEqual(unchanged["status"], "no_change")
        changed_parameters = {"task_goal": "A different bounded task."}
        changed = diff_skill_orchestrations(
            "astrabridge-supervisor-worker-synthesizer",
            "astrabridge-supervisor-worker-synthesizer",
            PARAMETERS["astrabridge-supervisor-worker-synthesizer"],
            changed_parameters,
        )
        self.assertEqual(changed["status"], "changed")
        self.assertTrue(any(item["change_type"] == "skill_parameters_changed" for item in changed["graph_diff"]["changes"]))
        self.assertNotIn("A different bounded task.", json.dumps(changed, ensure_ascii=False))

    def test_validate_runs_all_three_checks_and_cli_emits_redacted_json(self) -> None:
        report = validate_skill_orchestration(
            "astrabridge-fanout-research-synthesis",
            PARAMETERS["astrabridge-fanout-research-synthesis"],
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(set(report["checks"]), {"lint", "compile", "dry_run"})
        self.assertTrue(all(report["checks"][name]["status"] == "pass" for name in report["checks"]))

        sidecar_root = REPO_ROOT / "apps" / "astrabridge-sidecar"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "astrabridge_sidecar.agent_orchestration_cli",
                "skill-lint",
                "astrabridge-supervisor-worker-synthesizer",
                "--parameters-json",
                json.dumps(PARAMETERS["astrabridge-supervisor-worker-synthesizer"]),
            ],
            cwd=sidecar_root,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["operation"], "lint")
        self.assertEqual(payload["status"], "pass")


if __name__ == "__main__":
    unittest.main()
