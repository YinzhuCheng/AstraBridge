from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "interface_registry_audit.py"

spec = importlib.util.spec_from_file_location("interface_registry_audit", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
interface_registry_audit = importlib.util.module_from_spec(spec)
sys.modules["interface_registry_audit"] = interface_registry_audit
spec.loader.exec_module(interface_registry_audit)


class InterfaceRegistryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = interface_registry_audit.build_registry(REPO_ROOT)
        cls.by_id = {item["id"]: item for item in cls.registry["interfaces"]}

    def test_registry_validates_and_covers_desktop_http_paths(self) -> None:
        self.assertEqual(interface_registry_audit.validate_registry(self.registry, REPO_ROOT), [])
        self.assertEqual(self.registry["coverage"]["desktop_paths_missing_definition"], [])
        self.assertGreater(self.registry["summary"]["desktop_literal_http_paths"], 100)

    def test_known_current_and_alias_routes_are_classified_explicitly(self) -> None:
        self.assertEqual(self.by_id["http.GET./api/projects/current"]["status"], "current")
        alias = self.by_id["http.GET./api/project/current"]
        self.assertEqual(alias["status"], "shim-only")
        self.assertEqual(alias["replacement"], "GET /api/projects/current")
        disabled = self.by_id["http.POST./api/official-codex/apply"]
        self.assertEqual(disabled["status"], "deprecated")
        self.assertEqual(disabled["replacement"], "POST /api/llm-manager/login")

    def test_sse_payload_provider_and_cli_families_are_present(self) -> None:
        for interface_id in (
            "sse.astrabridge.event",
            "payload.runtime-event",
            "provider.profile",
            "provider.runtime-contract",
            "cli.sidecar-module",
            "mcp.capabilities",
        ):
            self.assertIn(interface_id, self.by_id)
            self.assertEqual(self.by_id[interface_id]["status"], "current")

    def test_archived_router_adapter_is_not_an_actionable_cleanup_candidate(self) -> None:
        adapter = self.by_id["shim.router-inline-adapters"]
        self.assertEqual(adapter["status"], "historical")
        self.assertFalse(adapter["cleanup_candidate"])
        self.assertEqual(adapter["schema"]["removed_from_runtime_source_on"], "2026-07-10")

    def test_cleanup_candidates_have_definition_and_consumer_evidence(self) -> None:
        candidates = [item for item in self.registry["interfaces"] if item["cleanup_candidate"]]
        self.assertGreater(len(candidates), 0)
        for item in candidates:
            self.assertTrue(item["definition_evidence"], item["id"])
            self.assertTrue(item["consumer_search_evidence"]["searched_scopes"], item["id"])
            self.assertIn("matches", item["consumer_search_evidence"], item["id"])
            self.assertTrue(item["removal_prerequisites"], item["id"])
            self.assertFalse(item["safe_to_remove"], item["id"])
            if item["status"] == "unknown":
                self.assertTrue(item["next_investigation"], item["id"])


if __name__ == "__main__":
    unittest.main()
