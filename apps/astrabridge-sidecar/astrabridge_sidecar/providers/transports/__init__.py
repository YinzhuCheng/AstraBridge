from typing import Any

from .base import ChatCompletionsTransport, ProviderTransport, ResponsesTransport, SEMANTIC_CONFORMANCE_SCHEMA_VERSION
from .deepseek import DeepSeekChatTransport
from .moonshot_kimi import KimiChatTransport
from .openai_chat import OpenAIChatTransport
from .openai_responses import OpenAIResponsesTransport
from .qwen_dashscope import QwenResponsesTransport
from .zai_glm import GlmChatTransport

ACTIVE_PROVIDER_FAMILY_TRANSPORTS: dict[str, type[ProviderTransport]] = {
    "qwen": QwenResponsesTransport,
    "deepseek": DeepSeekChatTransport,
    "kimi": KimiChatTransport,
    "glm": GlmChatTransport,
}

WIRE_API_FALLBACK_TRANSPORTS: dict[str, type[ProviderTransport]] = {
    "chat": OpenAIChatTransport,
    "responses": OpenAIResponsesTransport,
}


def transport_class_for_profile(profile: dict[str, Any], *, provider_family: str | None = None) -> type[ProviderTransport]:
    family = str(provider_family or profile.get("provider_family") or profile.get("adapter_profile") or "").strip().lower()
    if family in ACTIVE_PROVIDER_FAMILY_TRANSPORTS:
        return ACTIVE_PROVIDER_FAMILY_TRANSPORTS[family]
    wire_api = str(profile.get("wire_api") or "").strip().lower()
    return WIRE_API_FALLBACK_TRANSPORTS["chat"] if wire_api == "chat" else WIRE_API_FALLBACK_TRANSPORTS["responses"]


__all__ = [
    "ACTIVE_PROVIDER_FAMILY_TRANSPORTS",
    "ChatCompletionsTransport",
    "DeepSeekChatTransport",
    "GlmChatTransport",
    "KimiChatTransport",
    "OpenAIChatTransport",
    "OpenAIResponsesTransport",
    "ProviderTransport",
    "QwenResponsesTransport",
    "ResponsesTransport",
    "SEMANTIC_CONFORMANCE_SCHEMA_VERSION",
    "WIRE_API_FALLBACK_TRANSPORTS",
    "transport_class_for_profile",
]
