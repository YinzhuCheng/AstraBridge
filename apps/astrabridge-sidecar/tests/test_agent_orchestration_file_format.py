from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_contract import lower_agent_orchestration_graph_to_task_graph  # noqa: E402
from astrabridge_sidecar.agent_orchestration_file_format import (  # noqa: E402
    AGENT_ORCHESTRATION_FILE_EXTENSIONS,
    AGENT_ORCHESTRATION_FILE_FORMAT_VERSION,
    EXAMPLE_GRAPH_IDS,
    agent_orchestration_example_catalog,
    agent_orchestration_file_format_spec,
    load_agent_orchestration_example,
    load_agent_orchestration_graph_file,
    parse_agent_orchestration_graph_text,
    serialize_agent_orchestration_graph,
    write_agent_orchestration_graph_file,
)


class AgentOrchestrationFileFormatTests(unittest.TestCase):
    def test_file_format_spec_declares_json_v1(self) -> None:
        spec = agent_orchestration_file_format_spec()

        self.assertEqual(spec["format_version"], AGENT_ORCHESTRATION_FILE_FORMAT_VERSION)
        self.assertEqual(tuple(spec["extensions"]), AGENT_ORCHESTRATION_FILE_EXTENSIONS)
        self.assertEqual(spec["content_type"], "application/json")

    def test_example_catalog_covers_required_workflows(self) -> None:
        examples = agent_orchestration_example_catalog()

        self.assertEqual(set(examples), set(EXAMPLE_GRAPH_IDS))
        for example_id in EXAMPLE_GRAPH_IDS:
            with self.subTest(example_id=example_id):
                graph = load_agent_orchestration_example(example_id)
                self.assertEqual(graph["status"], "ready")
                self.assertTrue(graph["graph_policy"]["entry_node_ids"])
                lowered = lower_agent_orchestration_graph_to_task_graph(graph)
                self.assertEqual(lowered["graph_id"], graph["graph_id"])

    def test_repository_example_files_match_the_example_catalog(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        examples_root = repo_root / "examples" / "agent-orchestration"
        catalog = agent_orchestration_example_catalog()

        for example_id in EXAMPLE_GRAPH_IDS:
            with self.subTest(example_id=example_id):
                path = examples_root / f"{example_id}.json"
                self.assertTrue(path.exists())
                loaded = load_agent_orchestration_graph_file(path)
                self.assertEqual(loaded, catalog[example_id])

    def test_graph_text_round_trip_preserves_required_semantics(self) -> None:
        for example_id in EXAMPLE_GRAPH_IDS:
            with self.subTest(example_id=example_id):
                graph = load_agent_orchestration_example(example_id)
                serialized = serialize_agent_orchestration_graph(graph)
                reparsed = parse_agent_orchestration_graph_text(serialized, source_name=f"{example_id}.json")
                self.assertEqual(reparsed, graph)

    def test_graph_file_round_trip_persists_readable_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for example_id in EXAMPLE_GRAPH_IDS:
                with self.subTest(example_id=example_id):
                    graph = load_agent_orchestration_example(example_id)
                    path = root / f"{example_id}.json"
                    write_agent_orchestration_graph_file(path, graph)
                    loaded = load_agent_orchestration_graph_file(path)
                    self.assertEqual(loaded, graph)
                    raw = path.read_text(encoding="utf-8")
                    self.assertTrue(raw.endswith("\n"))
                    parsed = json.loads(raw)
                    self.assertEqual(parsed["graph_id"], graph["graph_id"])

    def test_invalid_extension_and_invalid_json_fail_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "broken.json"
            json_path.write_text("{not-json}", encoding="utf-8")
            with self.assertRaises(ValueError) as invalid_json:
                load_agent_orchestration_graph_file(json_path)
            self.assertIn("not valid JSON", str(invalid_json.exception))

            bad_extension = root / "graph.yaml"
            bad_extension.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError) as invalid_extension:
                load_agent_orchestration_graph_file(bad_extension)
            self.assertIn("Unsupported", str(invalid_extension.exception))


if __name__ == "__main__":
    unittest.main()
