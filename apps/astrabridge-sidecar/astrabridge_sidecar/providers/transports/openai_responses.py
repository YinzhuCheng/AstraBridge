from __future__ import annotations

from .base import ResponsesTransport


class OpenAIResponsesTransport(ResponsesTransport):
    def describe(self) -> str:
        return "openai_responses"
