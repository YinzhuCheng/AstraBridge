from __future__ import annotations

from .base import ChatCompletionsTransport


class OpenAIChatTransport(ChatCompletionsTransport):
    def describe(self) -> str:
        return "openai_chat"
