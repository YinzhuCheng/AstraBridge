from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.profile_service import ProfileService  # noqa: E402
from astrabridge_sidecar.providers.transports import (  # noqa: E402
    ACTIVE_PROVIDER_FAMILY_TRANSPORTS,
    SEMANTIC_CONFORMANCE_SCHEMA_VERSION,
)
from astrabridge_sidecar.router_service import RouterService  # noqa: E402


CORPUS_PATH = Path(__file__).resolve().parent / "fixtures" / "provider_semantic_conformance_v1.json"


class ProviderSemanticConformanceCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        cls.corpus = corpus
        cls.cases = [dict(item) for item in list(corpus.get("cases") or []) if isinstance(item, dict)]

    def _router(self) -> RouterService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return RouterService(ProfileService(Path(temp_dir.name) / "profiles.json"), port=0)

    @staticmethod
    def _adapter(router: RouterService, case: dict[str, Any]):
        provider = router._provider_by_id(str(case["provider_id"]))  # noqa: SLF001
        profile = {
            **provider,
            "provider_id": case["provider_id"],
            "provider_family": case["provider_id"],
            "model": case["native_model"],
        }
        return router._adapter_for(profile)  # noqa: SLF001

    def test_corpus_covers_every_active_external_provider_family_once(self) -> None:
        self.assertEqual(self.corpus["schema_version"], SEMANTIC_CONFORMANCE_SCHEMA_VERSION)
        providers = [str(case["provider_id"]) for case in self.cases]
        self.assertEqual(set(providers), set(ACTIVE_PROVIDER_FAMILY_TRANSPORTS))
        self.assertEqual(len(providers), len(set(providers)))

    def test_each_fixture_proves_request_response_stream_and_cancel_contracts(self) -> None:
        router = self._router()
        for case in self.cases:
            with self.subTest(provider=case["provider_id"]):
                adapter = self._adapter(router, case)
                request = dict(case["request"])
                upstream_request = adapter.build_request(request)
                contract = adapter.semantic_conformance_contract()
                normalized = adapter.normalize_response(case["upstream_response"], request)
                events = adapter.client_stream_events_from_upstream_json(case["upstream_response"], request)
                error = adapter.classify_error(case["error_message"], model_id=case["model_id"])

                self.assertEqual(adapter.describe(), case["adapter"])
                self.assertEqual(adapter.wire_api(), case["wire_api"])
                self.assertEqual(contract["schema_version"], SEMANTIC_CONFORMANCE_SCHEMA_VERSION)
                self.assertEqual(contract["request"]["reasoning_controls"], case["reasoning_semantics"])
                self.assertEqual(contract["streaming"]["mode"], case["stream_mode"])
                self.assertEqual(contract["request"]["image_attachments"], case["image_attachments"])
                self.assertEqual(contract["request"]["tool_definitions"], "requires_execution_route_evidence")
                self.assertEqual(contract["cancellation"]["owner"], "runtime_turn")
                self.assertEqual(contract["cancellation"]["strategy"], "interrupt_provider_thread")
                self.assertFalse(contract["cancellation"]["supports_explicit_provider_abort"])
                self.assertEqual(error["category"], case["expected_error_category"])
                self.assertTrue(error["actionable_hint"])

                self.assertEqual(upstream_request["model"], case["native_model"])
                self.assertTrue(upstream_request.get("stream"))
                self.assertTrue(upstream_request.get("tools"))
                if case["wire_api"] == "responses":
                    self.assertEqual(upstream_request["instructions"], request["instructions"])
                    self.assertTrue(
                        any(
                            item.get("type") == "function_call_output"
                            for item in list(upstream_request.get("input") or [])
                            if isinstance(item, dict)
                        )
                    )
                else:
                    messages = list(upstream_request.get("messages") or [])
                    self.assertEqual(messages[0]["role"], "system")
                    self.assertIn(request["instructions"], str(messages[0].get("content") or ""))
                    self.assertTrue(any(item.get("role") == "tool" for item in messages if isinstance(item, dict)))
                    self.assertEqual(upstream_request["stream_options"], {"include_usage": True})

                self.assertEqual(normalized.text, case["expected_text"])
                self.assertEqual([call.name for call in normalized.tool_calls], [case["expected_tool_name"]])
                self.assertEqual(adapter.response_semantic_status(normalized)["status"], "normalized")
                self.assertTrue(any(event.get("type") == "response.created" for event in events))
                self.assertTrue(any(event.get("type") == "response.completed" for event in events))
                self.assertTrue(
                    any(
                        event.get("type") == "response.output_item.done"
                        and str((event.get("item") or {}).get("type") or "") == "function_call"
                        for event in events
                    )
                )

    def test_router_projects_text_transport_success_as_review_only_until_route_evidence_exists(self) -> None:
        router = self._router()
        for case in self.cases:
            with self.subTest(provider=case["provider_id"]):
                preview = router.preview_payload(
                    {
                        "model": case["model_id"],
                        "input": "Reply with one sentence.",
                        "stream": True,
                    }
                )
                semantic = dict(preview["semantic_conformance"])
                route = dict(semantic["execution_route"])

                self.assertEqual(preview["execution_route_status"], "review_only")
                self.assertEqual(route["coding_agent_semantics"], "review_only")
                self.assertIn("Do not treat protocol/text success", route["action"])
                self.assertEqual(semantic["request"]["tool_definitions"], "requires_execution_route_evidence")

    def test_unsupported_image_attachment_fails_closed_with_actionable_downgrade(self) -> None:
        router = self._router()
        image_input = [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Describe the image."},
                    {"type": "input_image", "image_url": "data:image/png;base64,AA=="},
                ],
            }
        ]
        for case in self.cases:
            with self.subTest(provider=case["provider_id"]):
                payload = {"model": case["model_id"], "input": image_input}
                if case["image_attachments"] == "supported":
                    preview = router.preview_payload(payload)
                    self.assertEqual(preview["semantic_conformance"]["request"]["image_attachments"], "supported")
                else:
                    with self.assertRaisesRegex(ValueError, "Remove the image attachment or select a Qwen/Kimi image-capable route"):
                        router.preview_payload(payload)

    def test_malformed_provider_output_is_blocked_without_raw_payload_leakage(self) -> None:
        router = self._router()
        for case in self.cases:
            with self.subTest(provider=case["provider_id"]):
                adapter = self._adapter(router, case)
                normalized = adapter.normalize_response({"opaque_fixture_marker": "must-not-leak"}, dict(case["request"]))
                observation = adapter.response_semantic_status(normalized)
                events = adapter.client_stream_events_from_upstream_json(
                    {"opaque_fixture_marker": "must-not-leak"},
                    dict(case["request"]),
                )

                self.assertIn("malformed_provider_response", [warning.code for warning in normalized.warnings])
                self.assertEqual(observation["status"], "blocked")
                self.assertIn("retry a simpler fixture", observation["action"])
                self.assertNotIn("must-not-leak", json.dumps(normalized.provider_data))
                completed = next(event for event in events if event.get("type") == "response.completed")
                self.assertEqual(completed["response"]["status"], "invalid_response")

    def test_kimi_k3_reasoning_off_remains_an_explicit_request_shape_downgrade(self) -> None:
        router = self._router()
        with self.assertRaisesRegex(ValueError, "always-thinking"):
            router.preview_payload(
                {
                    "model": "kimi/kimi-k3",
                    "input": "Reply with one sentence.",
                    "reasoning": {"effort": "off"},
                }
            )


if __name__ == "__main__":
    unittest.main()
