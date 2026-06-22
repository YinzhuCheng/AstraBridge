from __future__ import annotations

from typing import Any


ALLOWED_PARAMETER_KEYS = {
    "type",
    "properties",
    "required",
    "description",
    "items",
    "enum",
    "oneOf",
    "anyOf",
    "allOf",
    "additionalProperties",
    "format",
    "default",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "nullable",
}


def sanitize_tool_definitions(tools: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(tools, list):
        return [], []
    converted: list[dict[str, Any]] = []
    warnings: list[str] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if str(tool.get("type") or "") != "function":
            continue
        parameters, removed = sanitize_function_parameters(tool.get("parameters") or {})
        if removed:
            warnings.append(
                f"Stripped unsupported schema keys from tool {tool.get('name') or 'tool'}: {', '.join(sorted(removed))}."
            )
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name") or "tool",
                    "description": tool.get("description") or "",
                    "parameters": parameters,
                },
            }
        )
    return converted, warnings


def sanitize_function_parameters(parameters: Any) -> tuple[dict[str, Any], set[str]]:
    removed: set[str] = set()

    def _sanitize(value: Any) -> Any:
        nonlocal removed
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                if key not in ALLOWED_PARAMETER_KEYS:
                    removed.add(str(key))
                    continue
                result[str(key)] = _sanitize(item)
            return result
        if isinstance(value, list):
            return [_sanitize(item) for item in value]
        return value

    root = parameters if isinstance(parameters, dict) else {}
    return _sanitize(root), removed
