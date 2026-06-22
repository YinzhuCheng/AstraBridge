from __future__ import annotations

import json
from typing import Any


DEFAULT_TOOL_OUTPUT_CHAR_LIMIT = 4000
MAX_TOOL_OUTPUT_CHAR_LIMIT = 32000
APPROX_CHARS_PER_TOKEN = 4


def tool_output_char_limit(token_limit: Any, *, default: int = DEFAULT_TOOL_OUTPUT_CHAR_LIMIT) -> int:
    try:
        parsed = int(token_limit)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return max(default, min(MAX_TOOL_OUTPUT_CHAR_LIMIT, parsed * APPROX_CHARS_PER_TOKEN))


def summarize_tool_output(value: Any, *, char_limit: int = DEFAULT_TOOL_OUTPUT_CHAR_LIMIT) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if isinstance(value, str):
        text = value
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        text = str(value or "")
    if len(text) > char_limit:
        warnings.append(f"Summarized oversized tool output from {len(text)} to {char_limit} characters.")
        text = text[:char_limit].rstrip() + "\n[truncated]"
    return text, warnings


def project_tool_result_parts(parts: Any, *, supports_image_result: bool) -> tuple[str, list[str]]:
    if not isinstance(parts, list):
        return "", []
    warnings: list[str] = []
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
            if supports_image_result:
                chunks.append(f"[image result retained as metadata: {part_type}]")
            else:
                detail = str(part.get("detail") or part.get("mime_type") or part.get("format") or "").strip()
                suffix = f" ({detail})" if detail else ""
                chunks.append(f"[image result omitted{suffix}]")
    if image_count and not supports_image_result:
        warnings.append("Downgraded image tool result to text metadata because the target/provider surface does not support image tool results.")
    return "\n".join(chunk for chunk in chunks if chunk).strip(), warnings
