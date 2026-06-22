from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from .registry import get_provider_profile


PRIVATE_PROVIDER_KEYS = {
    "encrypted_reasoning",
    "private_reasoning",
    "provider_response_id",
    "reasoning_blob",
    "reasoning_signature",
    "response_id",
    "signed_thinking",
    "thought_signature",
    "vendor_id",
}


def sanitize_provider_private_state(value: Any) -> tuple[Any, list[str]]:
    stripped: set[str] = set()

    def _sanitize(current: Any) -> Any:
        if isinstance(current, dict):
            sanitized: dict[str, Any] = {}
            for key, item in current.items():
                clean_key = str(key).strip()
                if clean_key.lower() in PRIVATE_PROVIDER_KEYS:
                    stripped.add(clean_key)
                    continue
                sanitized[key] = _sanitize(item)
            return sanitized
        if isinstance(current, list):
            return [_sanitize(item) for item in current]
        return current

    return _sanitize(value), sorted(stripped)


def provider_private_warning(stripped_keys: list[str]) -> str | None:
    if not stripped_keys:
        return None
    return f"Stripped provider-private fields during history projection: {', '.join(sorted(set(stripped_keys)))}."


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
    content_parts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ProjectionResult:
    messages: list[dict[str, Any]]
    dropped_artifacts: int
    repaired_tool_pairs: int
    warnings: list[str]
    replayable_artifacts: list[dict[str, Any]] = field(default_factory=list)


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
        target_profile = self._target_profile(target)
        target_known = target_profile is not None
        text_only_mode = not target_known
        supports_tool_result_images = bool(target_profile and target_profile.capabilities.supports_tool_result_images)

        dropped = 0
        repaired_tool_pairs = 0
        warnings: list[str] = []
        replayable_artifacts: list[dict[str, Any]] = []
        projected: list[dict[str, Any]] = []
        expected_tool_ids: list[str] = []
        seen_tool_ids: set[str] = set()
        artifact_summaries: list[str] = []

        if text_only_mode:
            warnings.append("Unknown target provider; projected text-only history summary and dropped provider-private replay state.")

        for message in neutral_messages:
            sanitized_provider_data, stripped_provider_keys = sanitize_provider_private_state(message.provider_data)
            private_warning = provider_private_warning(stripped_provider_keys)
            if private_warning:
                warnings.append(private_warning)

            if message.role == "tool":
                tool_content, tool_warning = self._project_tool_result_content(
                    message,
                    supports_tool_result_images=supports_tool_result_images,
                    text_only_mode=text_only_mode,
                )
                if tool_warning:
                    warnings.append(tool_warning)
                if not message.tool_call_id:
                    repaired_tool_pairs += 1
                    warnings.append("Dropped orphan tool result without tool_call_id.")
                    continue
                seen_tool_ids.add(message.tool_call_id)
                projected.append(
                    {
                        "role": "tool",
                        "tool_call_id": message.tool_call_id,
                        "content": tool_content,
                    }
                )
                continue

            if message.role == "assistant" and message.tool_call_id and message.tool_name:
                expected_tool_ids.append(message.tool_call_id)
                if text_only_mode:
                    projected.append(
                        {
                            "role": "assistant",
                            "content": self._text_only_tool_call_summary(message),
                        }
                    )
                    continue
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
                                    "arguments": self._safe_arguments_json(sanitized_provider_data.get("arguments_json")),
                                },
                            }
                        ],
                    }
                )
                continue

            content = message.text
            if message.content_parts:
                content_parts_text, content_warning = self._parts_to_text_summary(
                    message.content_parts,
                    supports_images=supports_tool_result_images,
                    for_tool=False,
                )
                if content_warning:
                    warnings.append(content_warning)
                if content_parts_text:
                    content = "\n".join(part for part in [content, content_parts_text] if part).strip()
            projected.append({"role": message.role, "content": content})

        for artifact in artifacts:
            sanitized_payload, stripped_provider_keys = sanitize_provider_private_state(dict(artifact.payload or {}))
            private_warning = provider_private_warning(stripped_provider_keys)
            if private_warning:
                warnings.append(private_warning)
            summary = self._artifact_summary(artifact.kind, sanitized_payload)
            same_provider = bool(source and artifact.provider_id.strip().lower() == target)
            if same_provider and artifact.replayable and not text_only_mode:
                replayable_artifacts.append(
                    {
                        "provider_id": artifact.provider_id,
                        "model_id": artifact.model_id,
                        "kind": artifact.kind,
                        "payload": sanitized_payload,
                    }
                )
                continue
            dropped += 1
            if summary:
                artifact_summaries.append(summary)

        if dropped and source and source != target:
            warnings.append("Opaque provider reasoning artifacts were dropped during cross-provider projection.")
        elif dropped and text_only_mode:
            warnings.append("Provider reasoning artifacts were reduced to text-only summaries for an unknown target provider.")

        if artifact_summaries and (text_only_mode or (source and source != target)):
            projected.append(
                {
                    "role": "system",
                    "content": "Prior provider summary:\n" + "\n".join(f"- {item}" for item in artifact_summaries[:4]),
                }
            )

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
            clean = str(warning or "").strip()
            if clean and clean not in deduped_warnings:
                deduped_warnings.append(clean)

        return ProjectionResult(
            messages=projected,
            dropped_artifacts=dropped,
            repaired_tool_pairs=repaired_tool_pairs,
            warnings=deduped_warnings,
            replayable_artifacts=replayable_artifacts,
        )

    def _target_profile(self, provider_id: str):
        try:
            return get_provider_profile(provider_id) if provider_id else None
        except ValueError:
            return None

    def _safe_arguments_json(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        text = str(value or "").strip()
        if not text:
            return "{}"
        try:
            json.loads(text)
            return text
        except Exception:
            return json.dumps({"raw": text}, ensure_ascii=False, separators=(",", ":"))

    def _project_tool_result_content(
        self,
        message: NeutralMessage,
        *,
        supports_tool_result_images: bool,
        text_only_mode: bool,
    ) -> tuple[str, str | None]:
        parts = list(message.content_parts or list(message.provider_data.get("content_parts") or []))
        if not parts:
            return message.text, None
        text_summary, warning = self._parts_to_text_summary(parts, supports_images=supports_tool_result_images, for_tool=True)
        if text_only_mode:
            text_summary = "\n".join(part for part in [message.text, text_summary] if part).strip()
            return text_summary or message.text, warning
        return "\n".join(part for part in [message.text, text_summary] if part).strip() or message.text, warning

    def _parts_to_text_summary(
        self,
        parts: list[dict[str, Any]],
        *,
        supports_images: bool,
        for_tool: bool,
    ) -> tuple[str, str | None]:
        chunks: list[str] = []
        image_count = 0
        for part in parts:
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type") or "").strip().lower()
            if part_type in {"text", "output_text"} and str(part.get("text") or "").strip():
                chunks.append(str(part.get("text") or "").strip())
                continue
            if part_type in {"image", "image_url", "input_image", "output_image"}:
                image_count += 1
                if supports_images:
                    chunks.append(f"[image result retained as metadata: {part_type}]")
                else:
                    detail = str(part.get("detail") or part.get("mime_type") or part.get("format") or "").strip()
                    suffix = f" ({detail})" if detail else ""
                    chunks.append(f"[image result omitted{suffix}]")
        warning = None
        if image_count and not supports_images:
            warning = (
                "Downgraded image tool result to text metadata because the target provider does not support tool-result images."
                if for_tool
                else "Downgraded image content part to text metadata for the target provider."
            )
        return "\n".join(chunk for chunk in chunks if chunk).strip(), warning

    def _text_only_tool_call_summary(self, message: NeutralMessage) -> str:
        base = str(message.text or "").strip()
        tool = str(message.tool_name or "tool").strip()
        summary = f"Assistant requested tool call: {tool}."
        return "\n".join(part for part in [base, summary] if part).strip()

    def _artifact_summary(self, kind: str, payload: dict[str, Any]) -> str:
        summary = payload.get("summary")
        if isinstance(summary, list):
            text = " ".join(str(item).strip() for item in summary if str(item).strip())
            if text:
                return self._clip(f"{kind}: {text}", 320)
        if isinstance(summary, str) and summary.strip():
            return self._clip(f"{kind}: {summary.strip()}", 320)
        visible = payload.get("visible_summary") or payload.get("text")
        if isinstance(visible, str) and visible.strip():
            return self._clip(f"{kind}: {visible.strip()}", 320)
        return ""

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."
