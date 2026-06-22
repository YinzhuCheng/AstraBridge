from __future__ import annotations

import hashlib
import json
from typing import Any


def repair_tool_arguments(value: Any) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")), warnings
    text = str(value or "").strip()
    if not text:
        return "{}", warnings
    if text.startswith("```"):
        stripped = text.strip("`").strip()
        if "\n" in stripped:
            stripped = stripped.split("\n", 1)[1].strip()
        text = stripped
        warnings.append("Repaired fenced tool-call arguments into JSON payload text.")
    try:
        json.loads(text)
        return text, warnings
    except Exception:
        repaired = json.dumps({"raw": text}, ensure_ascii=False, separators=(",", ":"))
        warnings.append("Wrapped malformed tool-call arguments in a JSON object under raw.")
        return repaired, warnings


def normalize_tool_calls(
    value: Any,
    *,
    allow_parallel: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        return [], []
    warnings: list[str] = []
    calls: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, call in enumerate(value):
        if not isinstance(call, dict):
            continue
        function = dict(call.get("function") or {})
        name = str(function.get("name") or call.get("name") or "tool").strip() or "tool"
        arguments, arg_warnings = repair_tool_arguments(function.get("arguments") or call.get("arguments"))
        warnings.extend(arg_warnings)
        call_id = str(call.get("id") or call.get("call_id") or "").strip()
        if not call_id:
            call_id = _deterministic_call_id(name=name, arguments_json=arguments, index=index)
            warnings.append(f"Assigned deterministic tool call id {call_id} because the provider omitted one.")
        if call_id in seen_ids:
            original = call_id
            call_id = _deterministic_call_id(name=name, arguments_json=arguments, index=index)
            warnings.append(f"Repaired duplicate tool call id {original} -> {call_id}.")
        seen_ids.add(call_id)
        calls.append(
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": arguments,
                },
            }
        )
    if not allow_parallel and len(calls) > 1:
        warnings.append("Dropped extra parallel tool calls because the selected model is not verified for parallel tool execution.")
        calls = calls[:1]
    return calls, warnings


def enforce_tool_message_sequence(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    repaired: list[dict[str, Any]] = []
    warnings: list[str] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            if message.get("role") == "tool":
                warnings.append("Repaired orphan tool result into a user-visible fallback message.")
                repaired.append(
                    {
                        "role": "user",
                        "content": f"[orphan tool output for {message.get('tool_call_id') or 'unknown'}]\n{message.get('content') or ''}".strip(),
                    }
                )
            else:
                repaired.append(message)
            index += 1
            continue

        merged_assistant = dict(message)
        merged_calls = [dict(call) for call in list(message.get("tool_calls") or []) if isinstance(call, dict)]
        merged_content = _flatten_content(merged_assistant.get("content"))
        index += 1
        while index < len(messages) and messages[index].get("role") == "assistant" and messages[index].get("tool_calls"):
            next_assistant = dict(messages[index])
            next_content = _flatten_content(next_assistant.get("content"))
            if next_content and next_content not in merged_content:
                merged_content = f"{merged_content}\n{next_content}".strip()
            if next_assistant.get("reasoning_content") and not merged_assistant.get("reasoning_content"):
                merged_assistant["reasoning_content"] = next_assistant.get("reasoning_content")
            merged_calls.extend(dict(call) for call in list(next_assistant.get("tool_calls") or []) if isinstance(call, dict))
            index += 1
        merged_assistant["tool_calls"] = merged_calls
        merged_assistant["content"] = merged_content or None
        repaired.append(merged_assistant)
        expected = [str(call.get("id") or "") for call in merged_calls if isinstance(call, dict)]
        seen: set[str] = set()
        while index < len(messages) and messages[index].get("role") == "tool":
            tool_message = dict(messages[index])
            tool_id = str(tool_message.get("tool_call_id") or "")
            if tool_id:
                seen.add(tool_id)
            repaired.append(tool_message)
            index += 1
        for tool_id in expected:
            if tool_id and tool_id not in seen:
                warnings.append(f"Inserted placeholder tool result for missing tool_call_id {tool_id}.")
                repaired.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": "Tool result was unavailable in Codex history; continue from the available context.",
                    }
                )
    return repaired, warnings


def _deterministic_call_id(*, name: str, arguments_json: str, index: int) -> str:
    digest = hashlib.sha1(f"{name}\n{arguments_json}\n{index}".encode("utf-8")).hexdigest()[:12]
    return f"call_{digest}"


def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [_flatten_content(item) for item in content]
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        item_type = str(content.get("type") or "")
        if item_type in {"input_text", "output_text", "text"}:
            return str(content.get("text") or "")
        if item_type == "localImage":
            return f"[local_image:{content.get('path')}]"
        if item_type == "mention":
            return f"[file:{content.get('path') or content.get('name')}]"
        if item_type == "function_call":
            return str(content.get("arguments") or "")
        if "text" in content:
            return str(content.get("text") or "")
        if "content" in content:
            return _flatten_content(content.get("content"))
    return json.dumps(content, ensure_ascii=False) if content is not None else ""
