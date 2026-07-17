from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agent_orchestration_checks import diff_agent_orchestration_graphs  # noqa: E402
from astrabridge_sidecar.langgraph_stategraph_adapter import (  # noqa: E402
    LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
    LangGraphStateGraphLossError,
    export_langgraph_stategraph_manifest,
    generate_langgraph_stategraph_python,
    import_langgraph_stategraph_manifest,
    langgraph_optional_dependency_status,
    langgraph_stategraph_adapter_manifest,
    looks_like_langgraph_stategraph_manifest,
)


LANGGRAPH_EXAMPLE_ROOT = REPO_ROOT / "examples" / "langgraph-stategraph"


def _load_example(name: str) -> dict[str, object]:
    return json.loads((LANGGRAPH_EXAMPLE_ROOT / name).read_text(encoding="utf-8"))


class LangGraphStateGraphAdapterTests(unittest.TestCase):
    def test_supported_manifest_round_trips_and_generates_langgraph_python(self) -> None:
        manifest = _load_example("conditional_subgraph_interrupt_supported.json")

        imported = import_langgraph_stategraph_manifest(manifest, task_id="task_unit")
        exported = export_langgraph_stategraph_manifest(imported["orchestration_graph"])
        reimported = import_langgraph_stategraph_manifest(json.loads(exported["serialized_text"]), task_id="task_unit")
        diff_report = diff_agent_orchestration_graphs(imported["orchestration_graph"], reimported["orchestration_graph"])
        generated_python = exported["generated_python"]

        self.assertTrue(looks_like_langgraph_stategraph_manifest(json.loads(exported["serialized_text"])))
        self.assertEqual(imported["source_format"], LANGGRAPH_STATEGRAPH_SOURCE_FORMAT)
        self.assertEqual(imported["loss_report"]["status"], "pass")
        self.assertEqual(exported["export_format"], LANGGRAPH_STATEGRAPH_SOURCE_FORMAT)
        self.assertEqual(diff_report["status"], "no_change")
        self.assertEqual(diff_report["summary"]["change_count"], 0)
        self.assertIn("builder.add_conditional_edges", generated_python)
        self.assertIn("interrupt_before", generated_python)
        self.assertIn("InMemorySaver", generated_python)
        self.assertIn("Replace `node_review_subgraph` with a compiled LangGraph subgraph", generated_python)
        self.assertIn("build_langgraph_config", generated_python)

    def test_unsupported_dynamic_interrupt_manifest_blocks_with_loss_report(self) -> None:
        manifest = _load_example("unsupported_dynamic_interrupt.json")

        with self.assertRaises(LangGraphStateGraphLossError) as exc:
            import_langgraph_stategraph_manifest(manifest, task_id="task_unit")

        payload = exc.exception.public_payload
        issue_codes = {item["code"] for item in payload["loss_report"]["issues"]}
        self.assertEqual(payload["source_format"], LANGGRAPH_STATEGRAPH_SOURCE_FORMAT)
        self.assertEqual(payload["loss_report"]["status"], "blocked")
        self.assertIn("unsupported_dynamic_interrupts", issue_codes)

    def test_optional_dependency_status_can_be_absent_without_blocking_codegen(self) -> None:
        manifest = _load_example("conditional_subgraph_interrupt_supported.json")

        with patch("astrabridge_sidecar.langgraph_stategraph_adapter.importlib.util.find_spec", return_value=None):
            dependency_status = langgraph_optional_dependency_status()
            adapter_manifest = langgraph_stategraph_adapter_manifest()
            generated_python = generate_langgraph_stategraph_python(manifest)

        self.assertFalse(dependency_status["langgraph_installed"])
        self.assertFalse(dependency_status["langchain_installed"])
        self.assertFalse(adapter_manifest["optional_dependencies"]["langgraph_installed"])
        self.assertIn("from langgraph.graph import END, START, StateGraph", generated_python)


if __name__ == "__main__":
    unittest.main()
