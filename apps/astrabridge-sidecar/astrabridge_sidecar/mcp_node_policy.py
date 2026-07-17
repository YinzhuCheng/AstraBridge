from __future__ import annotations

from copy import deepcopy
import fnmatch
import hashlib
import json
from typing import Any

from .common import now_iso
from .mcp_config_service import (
    CONTEXT7_PRESET,
    astrabridge_capabilities_preset,
    astrabridge_probe_fixture_preset,
    astrabridge_web_preset,
    yunwu_image_preset,
)


MCP_NODE_TOOL_POLICY_SCHEMA_VERSION = "astrabridge-mcp-node-tool-policy-v1"
MCP_NODE_TOOL_POLICY_REVISION = 1
MCP_NODE_TOOL_APPROVAL_MODES = ("allow", "ask", "deny", "manual")
MCP_NODE_TOOL_EFFECT_CLASSES = ("read_only", "network_read", "provider_call", "file_write", "side_effect")
_RESOURCE_URI_FIELD_NAMES = frozenset(
    {
        "resource_uri",
        "resource_ref",
        "resource_refs",
        "artifact_uri",
        "artifact_ref",
        "artifact_refs",
        "workspace_uri",
        "path",
        "paths",
        "relative_path",
        "relative_paths",
    }
)


class McpToolPolicyDenied(PermissionError):
    def __init__(self, message: str, *, decision: dict[str, Any]) -> None:
        super().__init__(message)
        self.decision = deepcopy(decision)


def builtin_mcp_preset_catalog() -> dict[str, dict[str, Any]]:
    presets = [
        deepcopy(CONTEXT7_PRESET),
        yunwu_image_preset(),
        astrabridge_web_preset(),
        astrabridge_capabilities_preset(),
        astrabridge_probe_fixture_preset(),
    ]
    return {
        str(preset.get("name") or "").strip(): preset
        for preset in presets
        if str(preset.get("name") or "").strip()
    }


def resolve_node_mcp_tool_policy(
    *,
    tools: dict[str, Any] | None,
    mcp_preset_ids: list[str] | None = None,
    graph_policy: dict[str, Any] | None = None,
    enabled_servers: list[dict[str, Any]] | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    tool_config = dict(tools or {})
    graph_config = dict(graph_policy or {})
    node_rules = _normalize_rule_config(
        tool_config.get("mcp_policy"),
        label=f"tools[{str(node_id or '').strip() or 'node'}].mcp_policy",
        default_approval_mode=str(tool_config.get("approval_mode") or "").strip().lower() or "ask",
    )
    graph_rules = _normalize_rule_config(
        graph_config.get("mcp_policy"),
        label="graph_policy.mcp_policy",
        default_approval_mode="allow",
    )
    preset_ids = [
        str(item).strip()
        for item in list(mcp_preset_ids or [])
        if str(item or "").strip()
    ]
    builtin_catalog = builtin_mcp_preset_catalog()
    server_catalog = _server_catalog(enabled_servers, builtin_catalog=builtin_catalog)
    available_server_names = (
        {
            str(item.get("name") or "").strip()
            for item in list(enabled_servers or [])
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }
        if enabled_servers is not None
        else set(server_catalog)
    )
    explicit_node_rules = _expand_rules(
        node_rules.get("tool_rules"),
        server_catalog=server_catalog,
        inherited_resource_uri_patterns=list(node_rules.get("resource_uri_patterns") or []),
        source="node_policy",
    )
    explicit_graph_rules = _expand_rules(
        graph_rules.get("tool_rules"),
        server_catalog=server_catalog,
        inherited_resource_uri_patterns=list(graph_rules.get("resource_uri_patterns") or []),
        source="graph_policy",
    )
    legacy_rules, legacy_migration = _legacy_supports_mcp_rules(
        tool_config=tool_config,
        preset_ids=preset_ids,
        server_catalog=server_catalog,
        available_server_names=available_server_names,
    )
    node_rule_map = {key: deepcopy(value) for key, value in legacy_rules.items()}
    for key, value in explicit_node_rules.items():
        node_rule_map[key] = _merge_rule(
            node_rule_map.get(key),
            value,
            prefer_source="node_policy",
        )
    graph_rule_map = {key: deepcopy(value) for key, value in explicit_graph_rules.items()}
    graph_has_ceiling = bool(graph_rule_map)
    if graph_has_ceiling:
        keys = sorted(set(node_rule_map).intersection(graph_rule_map))
    else:
        keys = sorted(node_rule_map)
    effective_rules: list[dict[str, Any]] = []
    for key in keys:
        node_rule = dict(node_rule_map.get(key) or {})
        graph_rule = dict(graph_rule_map.get(key) or {})
        combined = _combine_effective_rule(
            key=key,
            node_rule=node_rule,
            graph_rule=graph_rule,
            graph_has_ceiling=graph_has_ceiling,
            available_server_names=available_server_names,
            server_catalog=server_catalog,
        )
        if combined:
            effective_rules.append(combined)
    exposed_tools = [
        {
            "server": rule["server"],
            "tool": rule["tool"],
            "approval_mode": rule["approval_mode"],
            "effect_class": rule["effect_class"],
            "timeout_ms": rule["timeout_ms"],
        }
        for rule in effective_rules
        if bool(rule.get("available")) and str(rule.get("approval_mode") or "") != "deny"
    ]
    payload = {
        "schema_version": MCP_NODE_TOOL_POLICY_SCHEMA_VERSION,
        "revision": MCP_NODE_TOOL_POLICY_REVISION,
        "node_id": str(node_id or "").strip() or None,
        "supports_mcp": bool(tool_config.get("supports_mcp"))
        or bool(explicit_node_rules)
        or bool(preset_ids),
        "graph_has_ceiling": graph_has_ceiling,
        "allowed_tool_classes": [
            str(item).strip()
            for item in list(tool_config.get("allowed_tool_classes") or [])
            if str(item or "").strip()
        ],
        "mcp_preset_ids": preset_ids,
        "tool_rules": effective_rules,
        "exposed_tools": exposed_tools,
        "legacy_migration": legacy_migration,
        "available_servers": sorted(available_server_names),
        "catalog_servers": sorted(server_catalog),
        "compiled_at": now_iso(),
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def allowed_mcp_dynamic_tool_names(policy: dict[str, Any] | None) -> set[str]:
    return {
        str(item.get("tool") or "").strip()
        for item in list(dict(policy or {}).get("exposed_tools") or [])
        if isinstance(item, dict) and str(item.get("tool") or "").strip()
    }


def authorize_mcp_tool_call(
    policy: dict[str, Any] | None,
    *,
    server: str,
    tool: str,
    arguments: dict[str, Any] | None,
    caller: str,
    state: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(policy or {})
    tool_key = _tool_key(server=server, tool=tool)
    rule = next(
        (
            dict(item)
            for item in list(payload.get("tool_rules") or [])
            if isinstance(item, dict) and _tool_key(server=str(item.get("server") or ""), tool=str(item.get("tool") or "")) == tool_key
        ),
        None,
    )
    clean_context = {
        "run_id": str(dict(context or {}).get("run_id") or "").strip() or None,
        "node_id": str(dict(context or {}).get("node_id") or "").strip() or None,
        "attempt_count": int(dict(context or {}).get("attempt_count") or 0) or None,
        "caller": str(caller or "").strip() or "internal",
    }
    if not rule:
        decision = _decision(
            decision="deny",
            reason="undeclared_tool",
            policy=payload,
            context=clean_context,
            server=server,
            tool=tool,
        )
        raise McpToolPolicyDenied(
            f"AstraBridge MCP node policy denied undeclared tool `{tool}` on server `{server}`.",
            decision=decision,
        )
    if not bool(rule.get("available")):
        decision = _decision(
            decision="deny",
            reason="server_unavailable_or_disabled",
            policy=payload,
            context=clean_context,
            server=server,
            tool=tool,
            rule=rule,
        )
        raise McpToolPolicyDenied(
            f"AstraBridge MCP node policy denied unavailable tool `{tool}` on server `{server}`.",
            decision=decision,
        )
    clean_state = dict(state or {})
    resource_verdict = _resource_uri_verdict(rule, arguments or {})
    if resource_verdict["status"] != "allow":
        decision = _decision(
            decision="deny",
            reason="resource_uri_not_allowlisted",
            policy=payload,
            context=clean_context,
            server=server,
            tool=tool,
            rule=rule,
            resource_access=resource_verdict,
        )
        raise McpToolPolicyDenied(
            f"AstraBridge MCP node policy denied resource access for `{tool}` on `{server}`.",
            decision=decision,
        )
    budget = _budget_verdict(rule, clean_state)
    if budget["status"] != "allow":
        decision = _decision(
            decision="deny",
            reason="budget_exhausted",
            policy=payload,
            context=clean_context,
            server=server,
            tool=tool,
            rule=rule,
            budget=budget,
            resource_access=resource_verdict,
        )
        raise McpToolPolicyDenied(
            f"AstraBridge MCP node policy exhausted the tool budget for `{tool}` on `{server}`.",
            decision=decision,
        )
    approval = _approval_verdict(rule, clean_state)
    if approval["status"] != "allow":
        decision = _decision(
            decision="deny",
            reason="approval_required",
            policy=payload,
            context=clean_context,
            server=server,
            tool=tool,
            rule=rule,
            budget=budget,
            resource_access=resource_verdict,
            approval=approval,
        )
        raise McpToolPolicyDenied(
            f"AstraBridge MCP node policy requires approval before `{tool}` on `{server}` can execute.",
            decision=decision,
        )
    return _decision(
        decision="allow",
        reason=approval["reason"] or "allowlisted_tool",
        policy=payload,
        context=clean_context,
        server=server,
        tool=tool,
        rule=rule,
        budget=budget,
        resource_access=resource_verdict,
        approval=approval,
    )


def _normalize_rule_config(value: Any, *, label: str, default_approval_mode: str) -> dict[str, Any]:
    if value is None:
        return {"resource_uri_patterns": [], "tool_rules": [], "default_approval_mode": default_approval_mode}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict when present.")
    approval_mode = str(value.get("approval_mode") or default_approval_mode or "ask").strip().lower() or "ask"
    if approval_mode not in MCP_NODE_TOOL_APPROVAL_MODES:
        raise ValueError(f"{label}.approval_mode must be one of: {', '.join(MCP_NODE_TOOL_APPROVAL_MODES)}.")
    tool_rules = []
    for item in list(value.get("tool_rules") or []):
        if not isinstance(item, dict):
            raise ValueError(f"{label}.tool_rules entries must be objects.")
        server = str(item.get("server") or "").strip()
        if not server:
            raise ValueError(f"{label}.tool_rules.server is required.")
        tools = [
            str(entry).strip()
            for entry in list(item.get("tools") or item.get("tool_names") or [])
            if str(entry or "").strip()
        ]
        if not tools:
            tools = ["*"]
        item_approval = str(item.get("approval_mode") or approval_mode).strip().lower() or approval_mode
        if item_approval not in MCP_NODE_TOOL_APPROVAL_MODES:
            raise ValueError(f"{label}.tool_rules[{server}].approval_mode must be one of: {', '.join(MCP_NODE_TOOL_APPROVAL_MODES)}.")
        effect_class = str(item.get("effect_class") or "").strip().lower() or ""
        if effect_class and effect_class not in MCP_NODE_TOOL_EFFECT_CLASSES:
            raise ValueError(f"{label}.tool_rules[{server}].effect_class must be one of: {', '.join(MCP_NODE_TOOL_EFFECT_CLASSES)}.")
        timeout_ms = int(item.get("timeout_ms") or 0)
        budget = dict(item.get("budget") or {})
        max_calls = int(budget.get("max_calls") or 0) or None
        tool_rules.append(
            {
                "server": server,
                "tools": tools,
                "approval_mode": item_approval,
                "effect_class": effect_class or None,
                "timeout_ms": timeout_ms if timeout_ms > 0 else None,
                "budget": {"max_calls": max_calls} if max_calls else {},
                "resource_uri_patterns": _string_list(item.get("resource_uri_patterns")),
            }
        )
    return {
        "default_approval_mode": approval_mode,
        "resource_uri_patterns": _string_list(value.get("resource_uri_patterns")),
        "tool_rules": tool_rules,
    }


def _server_catalog(
    enabled_servers: list[dict[str, Any]] | None,
    *,
    builtin_catalog: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    catalog = {name: deepcopy(value) for name, value in builtin_catalog.items()}
    for server in list(enabled_servers or []):
        if not isinstance(server, dict):
            continue
        name = str(server.get("name") or "").strip()
        if not name:
            continue
        catalog[name] = deepcopy(server)
    return catalog


def _expand_rules(
    rules: dict[str, Any] | list[dict[str, Any]] | None,
    *,
    server_catalog: dict[str, dict[str, Any]],
    inherited_resource_uri_patterns: list[str],
    source: str,
) -> dict[str, dict[str, Any]]:
    expanded: dict[str, dict[str, Any]] = {}
    for rule in list(rules or []):
        if not isinstance(rule, dict):
            continue
        server = str(rule.get("server") or "").strip()
        if not server:
            continue
        server_tools = _tool_names_for_server(server, server_catalog)
        selected_tools = list(server_tools) if "*" in list(rule.get("tools") or []) else [
            tool_name for tool_name in list(rule.get("tools") or []) if tool_name in server_tools
        ]
        for tool in selected_tools:
            key = _tool_key(server=server, tool=tool)
            expanded[key] = {
                "server": server,
                "tool": tool,
                "approval_mode": str(rule.get("approval_mode") or "ask"),
                "effect_class": str(rule.get("effect_class") or _default_effect_class(server)).strip() or _default_effect_class(server),
                "timeout_ms": int(rule.get("timeout_ms") or _default_timeout_ms(server, server_catalog)) or None,
                "budget": deepcopy(dict(rule.get("budget") or {})),
                "resource_uri_patterns": _dedupe_preserve_order(
                    [*inherited_resource_uri_patterns, *_string_list(rule.get("resource_uri_patterns"))]
                ),
                "source": source,
            }
    return expanded


def _legacy_supports_mcp_rules(
    *,
    tool_config: dict[str, Any],
    preset_ids: list[str],
    server_catalog: dict[str, dict[str, Any]],
    available_server_names: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not bool(tool_config.get("supports_mcp")):
        return {}, {"applied": False, "source": "supports_mcp_false"}
    selected_servers = preset_ids or sorted(available_server_names)
    rules: dict[str, dict[str, Any]] = {}
    for server in selected_servers:
        for tool_name in _tool_names_for_server(server, server_catalog):
            key = _tool_key(server=server, tool=tool_name)
            rules[key] = {
                "server": server,
                "tool": tool_name,
                "approval_mode": "allow",
                "effect_class": _default_effect_class(server),
                "timeout_ms": _default_timeout_ms(server, server_catalog),
                "budget": {},
                "resource_uri_patterns": [],
                "source": "legacy_supports_mcp",
            }
    return rules, {
        "applied": True,
        "source": "supports_mcp_true",
        "selected_servers": selected_servers,
        "tool_count": len(rules),
    }


def _merge_rule(existing: dict[str, Any] | None, rule: dict[str, Any], *, prefer_source: str) -> dict[str, Any]:
    if not existing:
        return deepcopy(rule)
    merged = deepcopy(existing)
    merged.update({key: deepcopy(value) for key, value in rule.items() if value not in (None, [], {}, "")})
    merged["source"] = prefer_source
    return merged


def _combine_effective_rule(
    *,
    key: str,
    node_rule: dict[str, Any],
    graph_rule: dict[str, Any],
    graph_has_ceiling: bool,
    available_server_names: set[str],
    server_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    base = deepcopy(node_rule)
    if not base and graph_has_ceiling:
        return None
    if graph_has_ceiling:
        if not graph_rule:
            return None
        base["approval_mode"] = _strictest_approval_mode(
            str(node_rule.get("approval_mode") or "allow"),
            str(graph_rule.get("approval_mode") or "allow"),
        )
        base["timeout_ms"] = _min_positive(node_rule.get("timeout_ms"), graph_rule.get("timeout_ms"))
        base["budget"] = {
            "max_calls": _min_positive(
                dict(node_rule.get("budget") or {}).get("max_calls"),
                dict(graph_rule.get("budget") or {}).get("max_calls"),
            )
        }
        base["resource_uri_patterns"] = {
            "node": _string_list(node_rule.get("resource_uri_patterns")),
            "graph": _string_list(graph_rule.get("resource_uri_patterns")),
        }
        base["source"] = "graph_intersection"
    else:
        base["resource_uri_patterns"] = {
            "node": _string_list(node_rule.get("resource_uri_patterns")),
            "graph": [],
        }
    server = str(base.get("server") or "").strip()
    tool = str(base.get("tool") or "").strip()
    if not server or not tool:
        return None
    preset = dict(server_catalog.get(server) or {})
    base["available"] = server in available_server_names
    base["server_enabled"] = server in available_server_names
    base["default_tools_approval_mode"] = str(preset.get("default_tools_approval_mode") or "").strip() or None
    base["tool_timeout_ms"] = _default_timeout_ms(server, server_catalog)
    base["budget"]["max_calls"] = int(dict(base.get("budget") or {}).get("max_calls") or 0) or None
    base["policy_key"] = key
    return base


def _resource_uri_verdict(rule: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    uris = _collect_resource_uris(arguments)
    patterns = dict(rule.get("resource_uri_patterns") or {})
    node_patterns = _string_list(patterns.get("node"))
    graph_patterns = _string_list(patterns.get("graph"))
    if not uris:
        return {"status": "allow", "uris": [], "node_patterns": node_patterns, "graph_patterns": graph_patterns}
    for uri in uris:
        if node_patterns and not any(fnmatch.fnmatch(uri, pattern) for pattern in node_patterns):
            return {"status": "deny", "uri": uri, "uris": uris, "node_patterns": node_patterns, "graph_patterns": graph_patterns}
        if graph_patterns and not any(fnmatch.fnmatch(uri, pattern) for pattern in graph_patterns):
            return {"status": "deny", "uri": uri, "uris": uris, "node_patterns": node_patterns, "graph_patterns": graph_patterns}
    return {"status": "allow", "uris": uris, "node_patterns": node_patterns, "graph_patterns": graph_patterns}


def _budget_verdict(rule: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    max_calls = int(dict(rule.get("budget") or {}).get("max_calls") or 0) or None
    counter_key = str(rule.get("policy_key") or _tool_key(server=str(rule.get("server") or ""), tool=str(rule.get("tool") or "")))
    observed = int(dict(state.get("tool_call_counts") or {}).get(counter_key) or 0)
    if max_calls is not None and observed >= max_calls:
        return {
            "status": "deny",
            "counter_key": counter_key,
            "observed_calls_before": observed,
            "observed_calls_after": observed,
            "max_calls": max_calls,
        }
    return {
        "status": "allow",
        "counter_key": counter_key,
        "observed_calls_before": observed,
        "observed_calls_after": observed + 1,
        "max_calls": max_calls,
    }


def _approval_verdict(rule: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    approval_mode = str(rule.get("approval_mode") or "allow").strip().lower() or "allow"
    cache_key = str(rule.get("policy_key") or "")
    cache = dict(state.get("approval_cache") or {})
    if approval_mode == "deny":
        return {"status": "deny", "approval_mode": approval_mode, "cache_key": cache_key, "reason": "approval_mode_deny"}
    if approval_mode in {"allow"}:
        return {"status": "allow", "approval_mode": approval_mode, "cache_key": cache_key, "reason": "allow_mode"}
    if cache_key and cache_key in cache:
        return {
            "status": "allow",
            "approval_mode": approval_mode,
            "cache_key": cache_key,
            "reason": "approval_reused",
            "reused": True,
            "approved_at": dict(cache.get(cache_key) or {}).get("approved_at"),
        }
    explicit_grants = dict(state.get("approval_grants") or {})
    if cache_key and explicit_grants.get(cache_key):
        return {
            "status": "allow",
            "approval_mode": approval_mode,
            "cache_key": cache_key,
            "reason": "approval_grant",
            "reused": False,
        }
    if bool(state.get("auto_bootstrap_approval")):
        return {
            "status": "allow",
            "approval_mode": approval_mode,
            "cache_key": cache_key,
            "reason": "ask_auto_bootstrap",
            "reused": False,
            "cache_entry": {"approved_at": now_iso(), "source": "graph_worker_runtime_contract"},
        }
    return {"status": "deny", "approval_mode": approval_mode, "cache_key": cache_key, "reason": "approval_required"}


def _decision(
    *,
    decision: str,
    reason: str,
    policy: dict[str, Any],
    context: dict[str, Any],
    server: str,
    tool: str,
    rule: dict[str, Any] | None = None,
    budget: dict[str, Any] | None = None,
    resource_access: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_rule = dict(rule or {})
    return {
        "decision": decision,
        "reason": reason,
        "server": str(server or "").strip(),
        "tool": str(tool or "").strip(),
        "policy_schema_version": str(policy.get("schema_version") or MCP_NODE_TOOL_POLICY_SCHEMA_VERSION),
        "policy_revision": int(policy.get("revision") or MCP_NODE_TOOL_POLICY_REVISION),
        "policy_fingerprint": str(policy.get("fingerprint") or "").strip() or None,
        "approval_mode": str(clean_rule.get("approval_mode") or dict(approval or {}).get("approval_mode") or "").strip() or None,
        "approval_decision": str(dict(approval or {}).get("reason") or "").strip() or None,
        "approval_reused": bool(dict(approval or {}).get("reused")),
        "effect_class": str(clean_rule.get("effect_class") or "").strip() or None,
        "timeout_ms": int(clean_rule.get("timeout_ms") or 0) or None,
        "budget": deepcopy(dict(budget or {})),
        "resource_access": deepcopy(dict(resource_access or {})),
        "context": deepcopy(context),
        "rule_source": str(clean_rule.get("source") or "").strip() or None,
        "available": bool(clean_rule.get("available")) if clean_rule else None,
    }


def _collect_resource_uris(value: Any) -> list[str]:
    collected: list[str] = []

    def visit(item: Any, *, key: str | None = None) -> None:
        if isinstance(item, dict):
            for child_key, child_value in item.items():
                visit(child_value, key=str(child_key or ""))
            return
        if isinstance(item, list):
            for child in item:
                visit(child, key=key)
            return
        if not isinstance(item, str):
            return
        text = item.strip()
        if not text:
            return
        normalized_key = str(key or "").strip().lower()
        if normalized_key in _RESOURCE_URI_FIELD_NAMES and (
            text.startswith("workspace://")
            or text.startswith("ab-artifact://")
            or text.startswith("PRIVATE/")
            or text.startswith(".astrabridge/")
            or ":/" in text
        ):
            collected.append(text)

    visit(value)
    return _dedupe_preserve_order(collected)


def _tool_names_for_server(server: str, server_catalog: dict[str, dict[str, Any]]) -> list[str]:
    tools = dict(dict(server_catalog.get(server) or {}).get("tools") or {})
    return sorted(str(name).strip() for name in tools if str(name).strip())


def _default_timeout_ms(server: str, server_catalog: dict[str, dict[str, Any]]) -> int | None:
    raw = int(dict(server_catalog.get(server) or {}).get("tool_timeout_sec") or 0)
    return raw * 1000 if raw > 0 else None


def _default_effect_class(server: str) -> str:
    if server == "astrabridge_web" or server == "context7":
        return "network_read"
    if server in {"astrabridge_capabilities", "yunwu_image"}:
        return "provider_call"
    return "read_only"


def _strictest_approval_mode(left: str, right: str) -> str:
    order = {"allow": 0, "ask": 1, "manual": 1, "deny": 2}
    normalized_left = str(left or "allow").strip().lower() or "allow"
    normalized_right = str(right or "allow").strip().lower() or "allow"
    return normalized_left if order.get(normalized_left, 0) >= order.get(normalized_right, 0) else normalized_right


def _min_positive(left: Any, right: Any) -> int | None:
    values = [int(item) for item in (left, right) if int(item or 0) > 0]
    return min(values) if values else None


def _tool_key(*, server: str, tool: str) -> str:
    return f"{str(server or '').strip()}::{str(tool or '').strip()}"


def _string_list(value: Any) -> list[str]:
    return _dedupe_preserve_order(
        [
            str(item).strip()
            for item in list(value or [])
            if str(item or "").strip()
        ]
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _fingerprint(payload: dict[str, Any]) -> str:
    stable = {
        key: value
        for key, value in deepcopy(payload).items()
        if key not in {"fingerprint", "compiled_at"}
    }
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
