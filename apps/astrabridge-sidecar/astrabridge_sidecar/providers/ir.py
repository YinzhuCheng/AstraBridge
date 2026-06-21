from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ToolCall:
    id: str
    name: str
    arguments_json: str
    provider_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class ProviderWarning:
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


@dataclass
class RawProviderArtifactRef:
    kind: str
    locator: str
    redaction_status: Literal["redacted", "secret_free", "blocked"] = "redacted"
    summary: str | None = None


@dataclass
class ReasoningState:
    provider_id: str
    model_id: str
    replayable: bool
    visible_summary: str | None
    opaque_artifacts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class NormalizedResponse:
    text: str
    reasoning_summary: str | None
    reasoning_state: ReasoningState | None
    tool_calls: list[ToolCall]
    usage: Usage | None
    finish_reason: str | None
    provider_data: dict[str, Any] = field(default_factory=dict)
    warnings: list[ProviderWarning] = field(default_factory=list)
    raw_ref: RawProviderArtifactRef | None = None
