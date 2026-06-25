from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import default_capability_registry
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.web_tool_service import AstraBridgeWebService, web_lane_descriptor


class WebLaneTests(unittest.TestCase):
    def test_web_lane_descriptor_marks_lane_as_non_model_routed(self) -> None:
        descriptor = web_lane_descriptor()

        self.assertEqual(descriptor["lane_type"], "web_standalone")
        self.assertFalse(descriptor["model_routing_enabled"])
        self.assertTrue(descriptor["llm_interprets_results"])
        self.assertEqual(descriptor["capability_id"], "web.search")
        self.assertEqual(
            [item["tool_name"] for item in descriptor["tools"]],
            [
                "astrabridge_web_search_batch",
                "astrabridge_web_research_brief",
                "astrabridge_web_search",
                "astrabridge_web_fetch",
            ],
        )

    def test_capability_registry_refuses_to_route_web_lane_as_model_backed(self) -> None:
        registry = default_capability_registry()

        lane = registry.resolve_web_lane("web.search")
        self.assertEqual(lane["source"], "standalone_lane")
        self.assertEqual(lane["lane_descriptor"]["lane_type"], "web_standalone")

        with self.assertRaises(ValueError):
            registry.resolve_model_backed_candidates("web.search")

        model_candidates = registry.resolve_model_backed_candidates("image.generate")
        self.assertTrue(model_candidates)
        self.assertEqual(model_candidates[0]["lane_type"], "model_backed")

    def test_astrabridge_web_service_exposes_lane_descriptor_and_persists_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Dogfood", root / "dogfood.abproj", workspace_root=workspace, entry_mode="existing")
            service = AstraBridgeWebService(projects)

            descriptor = service.lane_descriptor()
            self.assertEqual(descriptor["lane_type"], "web_standalone")

            with patch(
                "astrabridge_sidecar.web_tool_service._search_batch",
                return_value={"tool": "astrabridge_web_search_batch", "results": [{"title": "Result"}]},
            ):
                result = service.search_batch({"queries": [{"query": "astrabridge"}]})

            self.assertTrue(result["ok"])
            self.assertIn("record_id", result)
            record_path = Path(result["path"])
            self.assertTrue(record_path.is_file())
            saved = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], "astrabridge-web-research-record-v1")
            self.assertEqual(saved["result"]["tool"], "astrabridge_web_search_batch")


if __name__ == "__main__":
    unittest.main()
