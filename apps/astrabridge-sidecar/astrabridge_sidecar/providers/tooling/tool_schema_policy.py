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
        function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
        source = function if function else tool
        parameters, removed = sanitize_function_parameters(source.get("parameters") or {})
        if removed:
            warnings.append(
                f"Stripped unsupported schema keys from tool {source.get('name') or 'tool'}: {', '.join(sorted(removed))}."
            )
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": source.get("name") or "tool",
                    "description": source.get("description") or "",
                    "parameters": parameters,
                },
            }
        )
    return converted, warnings


def sanitize_function_parameters(parameters: Any) -> tuple[dict[str, Any], set[str]]:
    removed: set[str] = set()

    def _sanitize(value: Any, *, in_properties: bool = False) -> Any:
        nonlocal removed
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            if in_properties:
                for key, item in value.items():
                    result[str(key)] = _sanitize(item)
                return result
            for key, item in value.items():
                if key not in ALLOWED_PARAMETER_KEYS:
                    removed.add(str(key))
                    continue
                if key == "properties":
                    result[str(key)] = _sanitize(item, in_properties=True)
                    continue
                result[str(key)] = _sanitize(item)
            return result
        if isinstance(value, list):
            return [_sanitize(item) for item in value]
        return value

    root = parameters if isinstance(parameters, dict) else {}
    return _sanitize(root), removed
