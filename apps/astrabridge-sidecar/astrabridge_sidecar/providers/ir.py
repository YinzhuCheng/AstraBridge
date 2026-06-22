from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
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


def _coerce_plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[truncated]"


def summarize_provider_warning(value: ProviderWarning | dict[str, Any] | str, *, message_limit: int = 400) -> dict[str, Any]:
    warning = _coerce_plain(value)
    if isinstance(warning, dict):
        return {
            "code": str(warning.get("code") or "")[:120],
            "severity": str(warning.get("severity") or "")[:32],
            "message": _clip(str(warning.get("message") or ""), message_limit),
        }
    return {"message": _clip(str(warning or ""), message_limit)}


def summarize_reasoning_state(value: ReasoningState | dict[str, Any] | None, *, summary_limit: int = 800) -> dict[str, Any] | None:
    reasoning_state = _coerce_plain(value)
    if not isinstance(reasoning_state, dict):
        return None
    return {
        "provider_id": str(reasoning_state.get("provider_id") or "")[:120],
        "model_id": str(reasoning_state.get("model_id") or "")[:200],
        "replayable": bool(reasoning_state.get("replayable")),
        "visible_summary": _clip(str(reasoning_state.get("visible_summary") or ""), summary_limit) or None,
        "opaque_artifact_count": len(list(reasoning_state.get("opaque_artifacts") or [])),
    }


def summarize_raw_ref(value: RawProviderArtifactRef | dict[str, Any] | None, *, locator_limit: int = 300, summary_limit: int = 300) -> dict[str, Any] | None:
    raw_ref = _coerce_plain(value)
    if not isinstance(raw_ref, dict):
        return None
    return {
        "kind": str(raw_ref.get("kind") or "")[:120],
        "locator": _clip(str(raw_ref.get("locator") or ""), locator_limit),
        "redaction_status": str(raw_ref.get("redaction_status") or "")[:32],
        "summary": _clip(str(raw_ref.get("summary") or ""), summary_limit) or None,
    }


def summarize_normalized_response(
    value: NormalizedResponse | dict[str, Any],
    *,
    text_limit: int = 1200,
    reasoning_limit: int = 800,
    warning_limit: int = 400,
    locator_limit: int = 300,
    tool_limit: int = 8,
    provider_key_limit: int = 20,
) -> dict[str, Any]:
    normalized = _coerce_plain(value)
    if not isinstance(normalized, dict):
        return {"text": _clip(str(normalized or ""), text_limit)}
    tool_calls = []
    for item in list(normalized.get("tool_calls") or []):
        tool_call = _coerce_plain(item)
        if not isinstance(tool_call, dict):
            continue
        tool_calls.append(
            {
                "id": str(tool_call.get("id") or "")[:120],
                "name": str(tool_call.get("name") or "")[:120],
            }
        )
    usage = _coerce_plain(normalized.get("usage"))
    usage_summary = {}
    if isinstance(usage, dict):
        usage_summary = {
            key: usage.get(key)
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens")
            if usage.get(key) is not None
        }
    provider_data = _coerce_plain(normalized.get("provider_data"))
    provider_data_keys = sorted(str(key) for key in provider_data.keys()) if isinstance(provider_data, dict) else []
    result = {
        "text": _clip(str(normalized.get("text") or ""), text_limit),
        "reasoning_summary": _clip(str(normalized.get("reasoning_summary") or ""), reasoning_limit) or None,
        "tool_calls": tool_calls[:tool_limit],
        "finish_reason": _clip(str(normalized.get("finish_reason") or ""), 120) or None,
        "warnings": [
            summarize_provider_warning(item, message_limit=warning_limit)
            for item in list(normalized.get("warnings") or [])[:8]
        ],
        "provider_data_keys": provider_data_keys[:provider_key_limit],
    }
    if usage_summary:
        result["usage"] = usage_summary
    reasoning_state = summarize_reasoning_state(normalized.get("reasoning_state"), summary_limit=reasoning_limit)
    if reasoning_state:
        result["reasoning_state"] = reasoning_state
    raw_ref = summarize_raw_ref(normalized.get("raw_ref"), locator_limit=locator_limit, summary_limit=locator_limit)
    if raw_ref:
        result["raw_ref"] = raw_ref
    return result


def summarize_response_diagnostics(
    value: NormalizedResponse | dict[str, Any],
    *,
    text_limit: int = 300,
    reasoning_limit: int = 240,
    warning_limit: int = 240,
    locator_limit: int = 240,
) -> dict[str, Any]:
    summary = summarize_normalized_response(
        value,
        text_limit=text_limit,
        reasoning_limit=reasoning_limit,
        warning_limit=warning_limit,
        locator_limit=locator_limit,
        tool_limit=4,
        provider_key_limit=12,
    )
    text_excerpt = str(summary.pop("text", "") or "")
    diagnostics = dict(summary)
    diagnostics["text_excerpt"] = text_excerpt or None
    return diagnostics
