from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.router_service import RouterService


class ProviderTransportConformanceTests(unittest.TestCase):
    _MODEL_IDS = {
        "openai": "openai/gpt-5.5",
        "yunwu": "yunwu/gpt-5.5",
        "qwen": "qwen/qwen3.7-plus",
        "deepseek": "deepseek/deepseek-v4-pro",
        "kimi": "kimi/kimi-k2.6",
        "glm": "glm/glm-5.2",
    }

    def _router(self) -> RouterService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        profiles = ProfileService(Path(temp_dir.name) / "profiles.json")
        return RouterService(profiles, port=0)

    def test_built_in_transports_pass_shared_request_error_and_cancel_contract(self) -> None:
        router = self._router()
        for provider_id, model_id in self._MODEL_IDS.items():
            with self.subTest(provider=provider_id):
                adapter = router._adapter_for_provider(provider_id)  # noqa: SLF001
                request = adapter.build_request(
                    {
                        "model": model_id,
                        "input": [{"role": "user", "content": "Reply with ok"}],
                        "tools": [],
                    }
                )
                self.assertTrue(adapter.endpoint_path().startswith("/"))
                self.assertIn(adapter.wire_api(), {"chat", "responses"})
                self.assertEqual(len(adapter.transport_signature()), 16)
                self.assertIsInstance(request, dict)
                self.assertTrue(request)
                error = adapter.classify_error("429 rate limit retry-after: 0", model_id=model_id)
                self.assertEqual(error["category"], "rate_limit")
                cancel = adapter.cancellation_contract()
                self.assertEqual(cancel["owner"], "runtime_turn")
                self.assertEqual(cancel["strategy"], "interrupt_provider_thread")

    def test_built_in_transports_pass_shared_stream_and_response_normalization_contract(self) -> None:
        router = self._router()
        for provider_id, model_id in self._MODEL_IDS.items():
            with self.subTest(provider=provider_id):
                adapter = router._adapter_for_provider(provider_id)  # noqa: SLF001
                if adapter.wire_api() == "responses":
                    upstream = {
                        "id": f"resp-{provider_id}",
                        "object": "response",
                        "status": "completed",
                        "output": [
                            {"id": f"reasoning-{provider_id}", "type": "reasoning", "summary": ["plan"], "content": ["plan"]},
                            {"id": f"msg-{provider_id}", "type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Final answer."}]},
                        ],
                    }
                    events = adapter.client_stream_events_from_upstream_json(upstream, {"model": model_id})
                    normalized = adapter.normalize_response(upstream, {"model": model_id})
                    self.assertTrue(any(event.get("type") == "response.completed" for event in events))
                    self.assertEqual(normalized.text, "Final answer.")
                    self.assertIsNotNone(normalized.raw_ref)
                    self.assertNotIn("output", normalized.provider_data)
                else:
                    upstream = {
                        "id": f"chat-{provider_id}",
                        "choices": [
                            {
                                "finish_reason": "tool_calls",
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "reasoning_content": "Plan first.",
                                    "tool_calls": [
                                        {"id": f"call-{provider_id}", "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"}}
                                    ],
                                },
                            }
                        ],
                    }
                    response = adapter.client_response_from_upstream_json(upstream, {"model": model_id})
                    events = adapter.client_stream_events_from_upstream_json(response, {"model": model_id})
                    normalized = adapter.normalize_response(upstream, {"model": model_id})
                    self.assertTrue(any(event.get("type") == "response.completed" for event in events))
                    self.assertEqual(len(normalized.tool_calls), 1)
                    self.assertIsNotNone(normalized.raw_ref)
                    self.assertNotIn("choices", normalized.provider_data)


if __name__ == "__main__":
    unittest.main()
