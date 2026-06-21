from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ReasoningArtifact:
    provider_id: str
    model_id: str
    kind: str
    replayable: bool
    payload: dict[str, Any]


@dataclass
class NeutralMessage:
    role: Literal["user", "assistant", "tool", "system"]
    text: str
    tool_call_id: str | None = None
    tool_name: str | None = None
    provider_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectionResult:
    messages: list[dict[str, Any]]
    dropped_artifacts: int
    repaired_tool_pairs: int
    warnings: list[str]


class HistoryProjector:
    def project(
        self,
        *,
        neutral_messages: list[NeutralMessage],
        artifacts: list[ReasoningArtifact],
        source_provider: str | None,
        target_provider: str,
    ) -> ProjectionResult:
        source = str(source_provider or "").strip().lower() or None
        target = str(target_provider or "").strip().lower()
        dropped = 0
        repaired_tool_pairs = 0
        warnings: list[str] = []

        projected: list[dict[str, Any]] = []
        expected_tool_ids: list[str] = []
        seen_tool_ids: set[str] = set()

        for message in neutral_messages:
            if message.role == "tool":
                if not message.tool_call_id:
                    repaired_tool_pairs += 1
                    warnings.append("Dropped orphan tool result without tool_call_id.")
                    continue
                seen_tool_ids.add(message.tool_call_id)
                projected.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.tool_call_id,
                        "content": message.text,
                    }
                )
                continue

            if message.role == "assistant" and message.tool_call_id and message.tool_name:
                expected_tool_ids.append(message.tool_call_id)
                projected.append(
                    {
                        "role": "assistant",
                        "content": message.text or None,
                        "tool_calls": [
                            {
                                "id": message.tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": message.tool_name,
                                    "arguments": str(message.provider_data.get("arguments_json") or "{}"),
                                },
                            }
                        ],
                    }
                )
                continue

            projected.append({"role": message.role, "content": message.text})

        for artifact in artifacts:
            same_provider = source and artifact.provider_id.strip().lower() == target
            if same_provider and artifact.replayable:
                continue
            dropped += 1

        if dropped and source and source != target:
            warnings.append("Opaque provider reasoning artifacts were dropped during cross-provider projection.")

        for tool_id in expected_tool_ids:
            if tool_id and tool_id not in seen_tool_ids:
                repaired_tool_pairs += 1
                projected.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": "Tool result was unavailable in Codex history; continue from the available context.",
                    }
                )

        deduped_warnings: list[str] = []
        for warning in warnings:
            if warning not in deduped_warnings:
                deduped_warnings.append(warning)

        return ProjectionResult(
            messages=projected,
            dropped_artifacts=dropped,
            repaired_tool_pairs=repaired_tool_pairs,
            warnings=deduped_warnings,
        )
