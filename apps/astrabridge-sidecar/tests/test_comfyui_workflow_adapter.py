from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agent_orchestration_checks import diff_agent_orchestration_graphs  # noqa: E402
from astrabridge_sidecar.comfyui_workflow_adapter import (  # noqa: E402
    COMFYUI_WORKFLOW_SOURCE_FORMAT,
    ComfyUiWorkflowLossError,
    export_comfyui_workflow,
    import_comfyui_workflow,
    looks_like_comfyui_workflow,
)


COMFYUI_EXAMPLE_ROOT = REPO_ROOT / "examples" / "comfyui-workflow"


def _load_example(name: str) -> dict[str, object]:
    return json.loads((COMFYUI_EXAMPLE_ROOT / name).read_text(encoding="utf-8"))


class ComfyUiWorkflowAdapterTests(unittest.TestCase):
    def test_supported_branched_multimodal_example_round_trips_semantically(self) -> None:
        workflow = _load_example("branched_multimodal_supported.json")

        imported = import_comfyui_workflow(workflow, task_id="task_unit")
        exported = export_comfyui_workflow(imported["orchestration_graph"])
        reimported = import_comfyui_workflow(json.loads(exported["serialized_text"]), task_id="task_unit")
        diff_report = diff_agent_orchestration_graphs(imported["orchestration_graph"], reimported["orchestration_graph"])

        self.assertTrue(looks_like_comfyui_workflow(json.loads(exported["serialized_text"])))
        self.assertEqual(imported["source_format"], COMFYUI_WORKFLOW_SOURCE_FORMAT)
        self.assertEqual(imported["loss_report"]["status"], "pass")
        self.assertEqual(exported["export_format"], COMFYUI_WORKFLOW_SOURCE_FORMAT)
        self.assertEqual(diff_report["status"], "no_change")
        self.assertEqual(diff_report["summary"]["change_count"], 0)

        imported_nodes = {item["node_id"]: item for item in imported["orchestration_graph"]["nodes"]}
        self.assertEqual(imported_nodes["node_multimodal_agent"]["ports"]["inputs"][1]["port_type"], "image")
        self.assertEqual(imported_nodes["node_manual_gate"]["output_contract"]["artifact_specs"][0]["kind"], "approval_record")

    def test_disconnected_unsupported_example_preserves_opaque_extensions_with_warning(self) -> None:
        workflow = _load_example("unsupported_disconnected_preserved.json")

        imported = import_comfyui_workflow(workflow, task_id="task_unit")
        extensions = imported["orchestration_graph"]["migration"]["adapter_extensions"]["astrabridge"]

        self.assertEqual(imported["loss_report"]["status"], "warning")
        self.assertEqual(imported["loss_report"]["summary"]["preserved_count"], 1)
        self.assertEqual(len(extensions["opaque_nodes"]), 1)
        self.assertEqual(extensions["opaque_nodes"][0]["type"], "vendor_magic/disconnected_probe")

    def test_connected_unsupported_example_blocks_with_machine_readable_loss_report(self) -> None:
        workflow = _load_example("unsupported_connected.json")

        with self.assertRaises(ComfyUiWorkflowLossError) as exc:
            import_comfyui_workflow(workflow, task_id="task_unit")

        payload = exc.exception.public_payload
        issue_codes = {item["code"] for item in payload["loss_report"]["issues"]}
        self.assertEqual(payload["source_format"], COMFYUI_WORKFLOW_SOURCE_FORMAT)
        self.assertEqual(payload["loss_report"]["status"], "blocked")
        self.assertIn("unsupported_connected_node_type", issue_codes)

    def test_external_artifact_uri_is_blocked(self) -> None:
        workflow = deepcopy(_load_example("branched_multimodal_supported.json"))
        artifact_node = workflow["nodes"][0]
        artifact_meta = artifact_node["properties"]["astrabridge"]
        artifact_meta["artifact_uri"] = "C:/outside/input.md"
        artifact_meta["node_type_config"]["artifact_uri"] = "C:/outside/input.md"

        with self.assertRaises(ComfyUiWorkflowLossError) as exc:
            import_comfyui_workflow(workflow, task_id="task_unit")

        issues = exc.exception.public_payload["loss_report"]["issues"]
        self.assertTrue(any(item["code"] == "unsafe_artifact_uri" for item in issues))


if __name__ == "__main__":
    unittest.main()
