from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import default_capability_registry
from astrabridge_sidecar import astrabridge_web_mcp_server
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.web_tool_service import AstraBridgeWebService, web_lane_descriptor


class WebLaneTests(unittest.TestCase):
    def tearDown(self) -> None:
        astrabridge_web_mcp_server._FETCH_CACHE.clear()
        super().tearDown()

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
            self.assertEqual(result["usage_signal"]["status"], "not_available")
            self.assertEqual(result["usage_signal"]["reason"], "standalone_web_lane_no_provider_tokens")
            saved = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["schema_version"], "astrabridge-web-research-record-v1")
            self.assertEqual(saved["usage_signal"]["source"], "web_lane")
            self.assertEqual(saved["result"]["tool"], "astrabridge_web_search_batch")

    def test_openai_structured_outputs_research_uses_first_party_hints(self) -> None:
        goal = "Summarize current public documentation guidance for OpenAI Responses API structured outputs, citing official source pages only."

        with patch.object(astrabridge_web_mcp_server, "_search_batch", side_effect=AssertionError("live search should be skipped")):
            with patch.object(
                astrabridge_web_mcp_server,
                "_fetch",
                side_effect=lambda url, **_: {
                    "url": url,
                    "content_type": "text/html",
                    "text": f"OpenAI official documentation page for {url}",
                    "truncated": False,
                },
            ):
                result = astrabridge_web_mcp_server._research_brief(
                    research_goal=goal,
                    queries=None,
                    source_urls=None,
                    search_top_k=4,
                    fetch_top_n=4,
                    max_chars_per_source=1200,
                    timeout_sec=20,
                )

        self.assertEqual(result["tool"], "astrabridge_web_research_brief")
        self.assertIn("OpenAI Responses API structured outputs official documentation", result["query_plan"])
        self.assertEqual(result["search"]["query_count"], 0)
        self.assertTrue(result["search"]["warnings"])
        urls = [item["url"] for item in result["sources"]]
        self.assertIn("https://platform.openai.com/docs/guides/structured-outputs", urls)
        self.assertTrue(all("openai.com" in url for url in urls))

    def test_pinned_source_urls_skip_derived_search_by_default(self) -> None:
        source_urls = [
            "https://genai.owasp.org/llm-top-10/",
            "https://airc.nist.gov/airmf-resources/airmf/5-sec-core/",
        ]

        with patch.object(astrabridge_web_mcp_server, "_search_batch", side_effect=AssertionError("derived search should be skipped")):
            with patch.object(
                astrabridge_web_mcp_server,
                "_fetch",
                side_effect=lambda url, **_: {
                    "url": url,
                    "content_type": "text/html",
                    "text": f"Official pinned source text for {url}",
                    "truncated": False,
                },
            ):
                result = astrabridge_web_mcp_server._research_brief(
                    research_goal="Summarize official agent risk controls.",
                    queries=None,
                    source_urls=source_urls,
                    search_top_k=4,
                    fetch_top_n=6,
                    max_chars_per_source=1200,
                    timeout_sec=20,
                )

        self.assertEqual(result["search"]["query_count"], 0)
        self.assertEqual(result["search"]["result_count"], 0)
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["fetched_source_count"], 2)
        self.assertEqual(result["query_plan"], [])
        self.assertEqual(result["source_policy"]["mode"], "pinned_source_urls")
        self.assertEqual(result["source_policy"]["search_expansion"], "skipped")
        self.assertEqual(result["source_policy"]["pinned_source_count"], 2)
        self.assertTrue(result["search"]["warnings"])
        self.assertEqual([item["url"] for item in result["sources"]], source_urls)
        self.assertTrue(all(item["query"] == "source_urls" for item in result["sources"]))
        self.assertTrue(all(item["source_origin"] == "pinned_source_url" for item in result["sources"]))

    def test_pinned_source_urls_with_explicit_queries_keep_search_expansion(self) -> None:
        source_urls = ["https://example.com/pinned"]

        with patch.object(
            astrabridge_web_mcp_server,
            "_search_batch",
            return_value={
                "query_count": 1,
                "result_count": 1,
                "warnings": [],
                "merged_results": [{"title": "Search result", "url": "https://example.com/search", "snippet": "Search snippet", "query": "agent risks"}],
            },
        ) as search_batch:
            with patch.object(
                astrabridge_web_mcp_server,
                "_fetch",
                side_effect=lambda url, **_: {
                    "url": url,
                    "content_type": "text/html",
                    "text": f"Fetched text for {url}",
                    "truncated": False,
                },
            ):
                result = astrabridge_web_mcp_server._research_brief(
                    research_goal="Summarize official agent risk controls.",
                    queries=["agent risks"],
                    source_urls=source_urls,
                    search_top_k=4,
                    fetch_top_n=6,
                    max_chars_per_source=1200,
                    timeout_sec=20,
                )

        search_batch.assert_called_once()
        self.assertEqual(result["source_policy"]["mode"], "search_expanded")
        self.assertEqual(result["source_policy"]["search_expansion"], "enabled")
        self.assertEqual([item["source_origin"] for item in result["sources"]], ["pinned_source_url", "search_result"])

    def test_fetch_uses_cache_and_reports_access_date(self) -> None:
        astrabridge_web_mcp_server._FETCH_CACHE.clear()
        with patch.object(astrabridge_web_mcp_server, "_validate_public_url", return_value=None):
            with patch.object(
                astrabridge_web_mcp_server,
                "_download_text",
                return_value=("<html><body>Cached doc</body></html>", "https://example.com/docs/page?utm_source=test", "text/html", 200),
            ) as download:
                first = astrabridge_web_mcp_server._fetch("https://example.com/docs/page?utm_source=test", max_chars=6000, timeout_sec=5)
                second = astrabridge_web_mcp_server._fetch("https://example.com/docs/page", max_chars=6000, timeout_sec=5)

        download.assert_called_once()
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["source_host"], "example.com")
        self.assertEqual(second["source_host"], "example.com")
        self.assertEqual(first["access_date"], str(first["fetched_at"])[:10])
        self.assertEqual(second["access_date"], str(first["fetched_at"])[:10])
        self.assertEqual(first["status_code"], 200)

    def test_research_brief_reports_fetch_failures_cache_hits_and_source_pack_status(self) -> None:
        astrabridge_web_mcp_server._FETCH_CACHE.clear()
        source_urls = ["https://example.com/good", "https://example.com/bad"]

        def fake_download(url: str, *, timeout_sec: int) -> tuple[str, str, str, int]:  # noqa: ARG001
            if url.endswith("/bad"):
                raise RuntimeError("upstream 502")
            return ("<html><body>Official good source.</body></html>", url, "text/html", 200)

        with patch.object(astrabridge_web_mcp_server, "_validate_public_url", return_value=None):
            with patch.object(astrabridge_web_mcp_server, "_download_text", side_effect=fake_download):
                first = astrabridge_web_mcp_server._research_brief(
                    research_goal="Summarize deterministic source evidence.",
                    queries=None,
                    source_urls=source_urls,
                    search_top_k=4,
                    fetch_top_n=4,
                    max_chars_per_source=1200,
                    timeout_sec=10,
                )
                second = astrabridge_web_mcp_server._research_brief(
                    research_goal="Summarize deterministic source evidence.",
                    queries=None,
                    source_urls=source_urls,
                    search_top_k=4,
                    fetch_top_n=4,
                    max_chars_per_source=1200,
                    timeout_sec=10,
                )

        self.assertEqual(first["evidence_kind"], "source_pack_only")
        self.assertEqual(first["conclusion_status"], "not_synthesized")
        self.assertIn("access_date", first["citation_rule"])
        self.assertEqual(first["fetch_summary"]["requested_count"], 2)
        self.assertEqual(first["fetch_summary"]["ok_count"], 1)
        self.assertEqual(first["fetch_summary"]["failed_count"], 1)
        self.assertEqual(first["fetch_summary"]["cache_hit_count"], 0)
        self.assertEqual(first["failures"][0]["source_origin"], "pinned_source_url")
        self.assertEqual(first["failures"][0]["source_host"], "example.com")
        self.assertTrue(first["sources"][0]["fetch_ok"])
        self.assertFalse(first["sources"][0]["cache_hit"])
        self.assertTrue(first["sources"][0]["access_date"])
        self.assertFalse(first["sources"][1]["fetch_ok"])
        self.assertIn("RuntimeError: upstream 502", first["sources"][1]["warning"])

        self.assertEqual(second["fetch_summary"]["cache_hit_count"], 1)
        self.assertTrue(second["sources"][0]["cache_hit"])


if __name__ == "__main__":
    unittest.main()
