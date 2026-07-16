from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_checks import (  # noqa: E402
    AGENT_ORCHESTRATION_DIFF_SCHEMA_VERSION,
    AGENT_ORCHESTRATION_DRY_RUN_SCHEMA_VERSION,
    AGENT_ORCHESTRATION_LINT_SCHEMA_VERSION,
    AGENT_ORCHESTRATION_MIGRATE_SCHEMA_VERSION,
    diff_agent_orchestration_graph_files,
    dry_run_agent_orchestration_graph_file,
    lint_agent_orchestration_graph_file,
    migrate_task_graph_file_to_orchestration,
    render_agent_orchestration_report_markdown,
)
from astrabridge_sidecar.agent_orchestration_file_format import (  # noqa: E402
    load_agent_orchestration_example,
    write_agent_orchestration_graph_file,
)
from astrabridge_sidecar.task_graph_contract import load_task_graph_fixture  # noqa: E402


class AgentOrchestrationChecksTests(unittest.TestCase):
    def test_lint_reports_pass_and_lowering_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "code_fix_review.json"
            write_agent_orchestration_graph_file(path, load_agent_orchestration_example("code_fix_review"))

            report = lint_agent_orchestration_graph_file(path)

            self.assertEqual(report["schema_version"], AGENT_ORCHESTRATION_LINT_SCHEMA_VERSION)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["lowering"]["status"], "pass")
            self.assertIn("Graph ID", render_agent_orchestration_report_markdown(report))

    def test_dry_run_reports_pass_for_example_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fanout_research_synthesis.json"
            write_agent_orchestration_graph_file(path, load_agent_orchestration_example("fanout_research_synthesis"))

            report = dry_run_agent_orchestration_graph_file(path)

            self.assertEqual(report["schema_version"], AGENT_ORCHESTRATION_DRY_RUN_SCHEMA_VERSION)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["summary"]["blocking_count"], 0)
            self.assertEqual(report["compiled_plan"]["graph_id"], "graph_fanout_research_synthesis_v1")
            self.assertEqual(report["compiled_plan"]["topology"]["parallel_group_count"], 3)
            self.assertIn("## Nodes", render_agent_orchestration_report_markdown(report))

    def test_dry_run_validates_multimodal_routes_against_configured_model_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "multimodal_capability_adapter.json"
            write_agent_orchestration_graph_file(path, load_agent_orchestration_example("multimodal_capability_adapter"))

            report = dry_run_agent_orchestration_graph_file(
                path,
                configured_models=[
                    {
                        "id": "qwen/qwen3-coder-plus",
                        "provider": "qwen",
                        "native_model": "qwen3-coder-plus",
                        "input_modalities": ["text", "image"],
                    }
                ],
            )

            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["summary"]["node_count"], 3)
            self.assertEqual(report["compiled_plan"]["graph_id"], "graph_multimodal_capability_adapter_v1")

    def test_dry_run_blocks_invalid_multimodal_route_for_text_only_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-multimodal-capability-adapter.json"
            write_agent_orchestration_graph_file(path, load_agent_orchestration_example("multimodal_capability_adapter"))

            with self.assertRaisesRegex(ValueError, "invalid provider/model modality claims"):
                dry_run_agent_orchestration_graph_file(
                    path,
                    configured_models=[
                        {
                            "id": "qwen/qwen3-coder-plus",
                            "provider": "qwen",
                            "native_model": "qwen3-coder-plus",
                            "input_modalities": ["text"],
                        }
                    ],
                )

    def test_dry_run_surfaces_warning_for_unpinned_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            graph = load_agent_orchestration_example("code_fix_review")
            graph["nodes"][0]["routing"] = {"selection_mode": "none"}
            path = Path(tmp) / "warning.json"
            write_agent_orchestration_graph_file(path, graph)

            report = dry_run_agent_orchestration_graph_file(path)

            self.assertEqual(report["status"], "warning")
            self.assertTrue(report["warnings"])

    def test_diff_reports_semantic_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_path = Path(tmp) / "old.json"
            new_path = Path(tmp) / "new.json"
            old_graph = load_agent_orchestration_example("provider_update_smoke")
            new_graph = load_agent_orchestration_example("provider_update_smoke")
            new_graph["nodes"][1]["prompt"]["template"] = "Run the compatibility smoke matrix and return a narrower blocked-case summary."
            new_graph["graph_policy"]["max_depth"] = 3
            write_agent_orchestration_graph_file(old_path, old_graph)
            write_agent_orchestration_graph_file(new_path, new_graph)

            report = diff_agent_orchestration_graph_files(old_path, new_path)

            self.assertEqual(report["schema_version"], AGENT_ORCHESTRATION_DIFF_SCHEMA_VERSION)
            self.assertEqual(report["status"], "changed")
            self.assertGreaterEqual(report["summary"]["change_count"], 2)
            change_types = {item["change_type"] for item in report["changes"]}
            self.assertIn("node_prompt_changed", change_types)
            self.assertIn("graph_policy_changed", change_types)
            self.assertIn("## Changes", render_agent_orchestration_report_markdown(report))

    def test_cli_commands_emit_json_and_markdown(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        sidecar_root = repo_root / "apps" / "astrabridge-sidecar"
        example_path = repo_root / "examples" / "agent-orchestration" / "code_fix_review.json"
        with tempfile.TemporaryDirectory() as tmp:
            markdown_path = Path(tmp) / "lint.md"
            lint_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "astrabridge_sidecar.agent_orchestration_cli",
                    "lint",
                    str(example_path),
                    "--markdown-out",
                    str(markdown_path),
                ],
                cwd=sidecar_root,
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(lint_result.stdout)
            self.assertEqual(payload["status"], "pass")
            self.assertTrue(markdown_path.exists())

            diff_markdown_path = Path(tmp) / "diff.md"
            mutated = load_agent_orchestration_example("code_fix_review")
            mutated["nodes"][0]["prompt"]["template"] = "Bound the file set, expected evidence, and rollback note."
            mutated_path = Path(tmp) / "mutated.json"
            write_agent_orchestration_graph_file(mutated_path, mutated)
            diff_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "astrabridge_sidecar.agent_orchestration_cli",
                    "diff",
                    str(example_path),
                    str(mutated_path),
                    "--markdown-out",
                    str(diff_markdown_path),
                ],
                cwd=sidecar_root,
                capture_output=True,
                text=True,
                check=True,
            )
            diff_payload = json.loads(diff_result.stdout)
            self.assertEqual(diff_payload["status"], "changed")
            self.assertTrue(diff_markdown_path.exists())

            task_graph_path = Path(tmp) / "legacy-task-graph.json"
            task_graph_path.write_text(json.dumps(load_task_graph_fixture("code_fix_test_review"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            migrated_path = Path(tmp) / "migrated.json"
            migrate_markdown_path = Path(tmp) / "migrate.md"
            migrate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "astrabridge_sidecar.agent_orchestration_cli",
                    "migrate-task-graph",
                    str(task_graph_path),
                    "--output",
                    str(migrated_path),
                    "--markdown-out",
                    str(migrate_markdown_path),
                ],
                cwd=sidecar_root,
                capture_output=True,
                text=True,
                check=True,
            )
            migrate_payload = json.loads(migrate_result.stdout)
            self.assertEqual(migrate_payload["schema_version"], AGENT_ORCHESTRATION_MIGRATE_SCHEMA_VERSION)
            self.assertEqual(migrate_payload["status"], "pass")
            self.assertTrue(migrated_path.exists())
            self.assertTrue(migrate_markdown_path.exists())

    def test_migrate_task_graph_file_lifts_legacy_graph_and_optionally_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "legacy.json"
            source_path.write_text(json.dumps(load_task_graph_fixture("supervisor_worker_synthesizer"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output_path = root / "canonical.json"

            report = migrate_task_graph_file_to_orchestration(source_path, output_path=output_path)

            self.assertEqual(report["schema_version"], AGENT_ORCHESTRATION_MIGRATE_SCHEMA_VERSION)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["source_graph_id"], "graph_fixture_supervisor_worker_synthesizer")
            self.assertEqual(report["graph_id"], "graph_fixture_supervisor_worker_synthesizer")
            self.assertTrue(report["warning_count"] > 0)
            self.assertTrue(output_path.exists())
            self.assertIn("Target schema version", render_agent_orchestration_report_markdown(report))


if __name__ == "__main__":
    unittest.main()
