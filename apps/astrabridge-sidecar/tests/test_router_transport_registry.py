from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import astrabridge_sidecar.router_service as router_service_module
from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.providers.transports import (
    ACTIVE_PROVIDER_FAMILY_TRANSPORTS,
    WIRE_API_FALLBACK_TRANSPORTS,
    DeepSeekChatTransport,
    GlmChatTransport,
    KimiChatTransport,
    OpenAIChatTransport,
    OpenAIResponsesTransport,
    QwenResponsesTransport,
    transport_class_for_profile,
)
from astrabridge_sidecar.router_service import RouterService


class RouterTransportRegistryTests(unittest.TestCase):
    def test_router_module_does_not_retain_historical_inline_adapter_classes(self) -> None:
        for symbol in (
            "ProviderAdapter",
            "QwenResponsesAdapter",
            "ChatCompletionsAdapter",
            "DeepSeekChatAdapter",
            "KimiChatAdapter",
        ):
            self.assertFalse(hasattr(router_service_module, symbol), symbol)

    def test_transport_registry_declares_current_provider_owners(self) -> None:
        self.assertIs(ACTIVE_PROVIDER_FAMILY_TRANSPORTS["qwen"], QwenResponsesTransport)
        self.assertIs(ACTIVE_PROVIDER_FAMILY_TRANSPORTS["deepseek"], DeepSeekChatTransport)
        self.assertIs(ACTIVE_PROVIDER_FAMILY_TRANSPORTS["kimi"], KimiChatTransport)
        self.assertIs(ACTIVE_PROVIDER_FAMILY_TRANSPORTS["glm"], GlmChatTransport)
        self.assertIs(WIRE_API_FALLBACK_TRANSPORTS["chat"], OpenAIChatTransport)
        self.assertIs(WIRE_API_FALLBACK_TRANSPORTS["responses"], OpenAIResponsesTransport)

    def test_router_adapter_selection_uses_transport_registry_for_current_providers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)

            expected = {
                "openai": OpenAIResponsesTransport,
                "yunwu": OpenAIResponsesTransport,
                "deepseek": DeepSeekChatTransport,
                "qwen": QwenResponsesTransport,
                "kimi": KimiChatTransport,
                "glm": GlmChatTransport,
            }
            for provider_id, expected_class in expected.items():
                adapter = router._adapter_for_provider(provider_id)  # noqa: SLF001
                self.assertIsInstance(adapter, expected_class, msg=provider_id)

    def test_transport_registry_prefers_provider_family_before_wire_api_fallback(self) -> None:
        self.assertIs(
            transport_class_for_profile(
                {
                    "provider_id": "deepseek-alt",
                    "provider_family": "deepseek",
                    "wire_api": "responses",
                    "model": "deepseek-v4-pro",
                },
                provider_family="deepseek",
            ),
            DeepSeekChatTransport,
        )
        self.assertIs(
            transport_class_for_profile({"provider_id": "custom-chat", "wire_api": "chat", "model": "custom-model"}),
            OpenAIChatTransport,
        )
        self.assertIs(
            transport_class_for_profile({"provider_id": "custom-responses", "wire_api": "responses", "model": "custom-model"}),
            OpenAIResponsesTransport,
        )

    def test_qwen_vision_probe_uses_a_bounded_image_input_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)
            captured: dict[str, object] = {}
            router._provider_by_id = lambda provider_id: {"provider_id": provider_id, "model": "qwen3.7-plus"}  # type: ignore[method-assign]
            router._normalize_model_id = lambda provider_id, model_id: str(model_id)  # type: ignore[method-assign]
            router._provider_test_result = lambda payload, stream: captured.update({"payload": payload, "stream": stream}) or {  # type: ignore[method-assign]
                "ok": True,
                "response_excerpt": "red",
            }

            result = router.test_provider_vision("qwen", "qwen3.7-plus")

            payload = captured["payload"]
            self.assertIsInstance(payload, dict)
            content = payload["input"][0]["content"]
            image = next(item for item in content if item.get("type") == "input_image")
            self.assertTrue(str(image["image_url"]).startswith("data:image/png;base64,"))
            self.assertEqual(image["detail"], "low")
            self.assertEqual(payload["reasoning"], {"effort": "off"})
            self.assertTrue(result["image_probe"]["grounded"])


if __name__ == "__main__":
    unittest.main()
