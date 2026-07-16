from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.task_graph_contract import (
    GRAPH_TEMPLATE_IDS,
    TASK_GRAPH_RUN_SCHEMA_VERSION,
    TASK_GRAPH_SCHEMA_DEFINITIONS_VERSION,
    TASK_GRAPH_SCHEMA_VERSION,
    load_negative_task_graph_fixture,
    load_task_graph_fixture,
    load_task_graph_run_fixture,
    task_graph_fixture_catalog,
    task_graph_schema_definitions,
    validate_graph_definition,
    validate_task_graph_run,
)


class TaskGraphContractTests(unittest.TestCase):
    def test_schema_definitions_cover_graph_and_run_objects(self) -> None:
        definitions = task_graph_schema_definitions()

        self.assertEqual(definitions["schema_version"], TASK_GRAPH_SCHEMA_DEFINITIONS_VERSION)
        for name in (
            "graph_definition",
            "agent_node",
            "agent_edge",
            "context_policy",
            "artifact_ref",
            "task_graph_run",
            "node_run_state",
            "run_event",
            "approval_state",
        ):
            self.assertIn(name, definitions["definitions"])

    def test_five_v1_template_fixtures_load_without_side_effects(self) -> None:
        fixtures = task_graph_fixture_catalog()

        self.assertEqual(set(fixtures), set(GRAPH_TEMPLATE_IDS))
        for template_id in GRAPH_TEMPLATE_IDS:
            with self.subTest(template_id=template_id):
                graph = load_task_graph_fixture(template_id)
                validated = validate_graph_definition(graph)
                self.assertEqual(validated["schema_version"], TASK_GRAPH_SCHEMA_VERSION)
                self.assertEqual(validated["template_id"], template_id)
                self.assertTrue(list(validated["graph_policy"]["entry_node_ids"]))

    def test_fixture_run_validates_against_fixture_graph(self) -> None:
        run = load_task_graph_run_fixture("provider_update_smoke_gate")

        self.assertEqual(run["schema_version"], TASK_GRAPH_RUN_SCHEMA_VERSION)
        self.assertEqual(run["status"], "ready_for_dry_run")
        self.assertEqual(run["event_refs"][0]["event_type"], "run_created")

    def test_invalid_graphs_and_runs_fail_with_actionable_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "PRIVATE").mkdir()
            (workspace / ".astrabridge").mkdir()

            cases = [
                ("missing_context_policy", "context_policy"),
                ("unsafe_write_without_review", "review path"),
                ("missing_machine_result_schema", "machine_result_schema"),
                ("invalid_artifact_ref_path", "allowed workspace"),
            ]
            for case_id, expected in cases:
                with self.subTest(case_id=case_id):
                    fixture = load_negative_task_graph_fixture(case_id)
                    with self.assertRaises(ValueError) as exc:
                        if fixture["target"] == "graph_definition":
                            validate_graph_definition(fixture["payload"])
                        else:
                            validate_task_graph_run(fixture["payload"], workspace_root=workspace)
                    self.assertIn(expected, str(exc.exception))

    def test_duplicate_node_ids_are_rejected(self) -> None:
        graph = load_task_graph_fixture("supervisor_worker_synthesizer")
        duplicate = dict(graph["nodes"][0])
        duplicate["label"] = "Duplicate Supervisor"
        graph["nodes"].append(duplicate)

        with self.assertRaises(ValueError) as exc:
            validate_graph_definition(graph)
        self.assertIn("duplicate node_id", str(exc.exception))

    def test_run_alias_fields_are_normalized(self) -> None:
        graph = load_task_graph_fixture("document_extract_analyze_report")
        run = load_task_graph_run_fixture("document_extract_analyze_report")
        run["node_runs"] = run.pop("node_run_states")
        run["artifacts"] = run.pop("artifact_refs")
        run["events"] = run.pop("event_refs")

        validated = validate_task_graph_run(run, graph_definition=graph)

        self.assertIn("node_run_states", validated)
        self.assertIn("artifact_refs", validated)
        self.assertIn("event_refs", validated)


if __name__ == "__main__":
    unittest.main()
