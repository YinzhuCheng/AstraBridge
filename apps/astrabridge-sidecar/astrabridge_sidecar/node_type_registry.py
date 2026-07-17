from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, TypedDict


NODE_TYPE_REGISTRY_SCHEMA_VERSION = "astrabridge-node-type-registry-v1"
OPAQUE_DISABLED_NODE_TYPE_ID = "opaque_disabled"
NODE_TYPE_ROLE_IDS = (
    "supervisor",
    "worker",
    "synthesizer",
    "extractor",
    "validator",
    "reviewer",
    "planner",
    "coder",
    "researcher",
    "gate",
    "custom",
)


class NodeTypeSpec(TypedDict, total=False):
    type_id: str
    version: int
    category: str
    title: str
    description: str
    config_schema: dict[str, Any]
    typed_ports: dict[str, list[dict[str, Any]]]
    compiler_executor_id: str
    default_policy: dict[str, Any]
    ui_hints: dict[str, Any]
    migration: dict[str, Any]
    internal_only: bool
    registry_fingerprint: str


def task_graph_node_kind_ids() -> tuple[str, ...]:
    registry = build_node_type_registry()
    ordered: list[str] = []
    for spec in list(registry["node_types"] or []):
        type_id = str(spec.get("type_id") or "").strip()
        if type_id and type_id not in ordered:
            ordered.append(type_id)
        for alias in list(dict(spec.get("migration") or {}).get("legacy_kind_aliases") or []):
            alias_text = str(alias or "").strip()
            if alias_text and alias_text not in ordered:
                ordered.append(alias_text)
    if OPAQUE_DISABLED_NODE_TYPE_ID not in ordered:
        ordered.append(OPAQUE_DISABLED_NODE_TYPE_ID)
    return tuple(ordered)


def build_node_type_registry(
    *,
    extra_specs: list[dict[str, Any]] | None = None,
    include_internal: bool = True,
) -> dict[str, Any]:
    raw_specs = [deepcopy(spec) for spec in _base_node_type_specs()]
    raw_specs.extend(deepcopy(item) for item in list(extra_specs or []) if isinstance(item, dict))
    node_types: list[NodeTypeSpec] = []
    by_type_id: dict[str, NodeTypeSpec] = {}
    kind_aliases: dict[str, str] = {}
    seen_type_ids: set[str] = set()
    for raw in raw_specs:
        spec = _normalize_spec(raw)
        type_id = str(spec.get("type_id") or "").strip()
        version = int(spec.get("version") or 0)
        if not type_id:
            raise ValueError("NodeTypeSpec.type_id is required.")
        if version <= 0:
            raise ValueError(f"NodeTypeSpec.version must be positive for {type_id}.")
        if type_id in seen_type_ids:
            raise ValueError(f"Duplicate or conflicting node type registration: {type_id}@v{version}")
        seen_type_ids.add(type_id)
        for alias in [type_id, *list(dict(spec.get("migration") or {}).get("legacy_kind_aliases") or [])]:
            alias_text = str(alias or "").strip()
            if not alias_text:
                continue
            existing = kind_aliases.get(alias_text)
            if existing and existing != type_id:
                raise ValueError(f"Conflicting node type alias registration: {alias_text} -> {existing} vs {type_id}")
            kind_aliases[alias_text] = type_id
        node_types.append(spec)
        by_type_id[type_id] = spec
    execution_view = [
        _execution_fingerprint_view(spec)
        for spec in sorted(node_types, key=lambda item: (str(item.get("type_id") or ""), int(item.get("version") or 0)))
        if include_internal or not bool(spec.get("internal_only"))
    ]
    registry_fingerprint = _fingerprint(execution_view)
    public_node_types = [
        deepcopy(spec)
        for spec in node_types
        if include_internal or not bool(spec.get("internal_only"))
    ]
    return {
        "schema_version": NODE_TYPE_REGISTRY_SCHEMA_VERSION,
        "registry_fingerprint": registry_fingerprint,
        "node_types": public_node_types,
        "kind_aliases": {
            alias: target
            for alias, target in sorted(kind_aliases.items())
            if include_internal or not bool(by_type_id.get(target, {}).get("internal_only"))
        },
        "role_ids": list(NODE_TYPE_ROLE_IDS),
        "_all_node_types": node_types,
        "_by_type_id": by_type_id,
    }


def node_type_registry_snapshot(*, extra_specs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    registry = build_node_type_registry(extra_specs=extra_specs, include_internal=False)
    return {
        "schema_version": NODE_TYPE_REGISTRY_SCHEMA_VERSION,
        "registry_fingerprint": registry["registry_fingerprint"],
        "role_ids": list(registry["role_ids"]),
        "kind_aliases": dict(registry["kind_aliases"]),
        "node_types": [deepcopy(spec) for spec in list(registry["node_types"] or [])],
    }


def default_role_for_kind(kind: str) -> str:
    resolved = resolve_node_type(kind, allow_unknown=True)
    spec = dict(resolved.get("spec") or {})
    migration = dict(spec.get("migration") or {})
    alias_defaults = dict(migration.get("default_role_by_kind") or {})
    return str(alias_defaults.get(str(kind or "").strip()) or migration.get("default_role") or "custom")


def compatible_roles_for_kind(kind: str) -> set[str]:
    resolved = resolve_node_type(kind, allow_unknown=True)
    spec = dict(resolved.get("spec") or {})
    migration = dict(spec.get("migration") or {})
    roles = {
        str(item).strip()
        for item in list(migration.get("compatible_roles") or [])
        if str(item or "").strip()
    }
    return roles or {"custom"}


def resolve_node_type(kind: str, *, allow_unknown: bool = False) -> dict[str, Any]:
    registry = build_node_type_registry(include_internal=True)
    by_type_id = dict(registry.get("_by_type_id") or {})
    kind_text = str(kind or "").strip()
    resolved_type_id = str(dict(registry.get("kind_aliases") or {}).get(kind_text) or kind_text).strip()
    spec = deepcopy(by_type_id.get(resolved_type_id) or {})
    if spec:
        migration = dict(spec.get("migration") or {})
        alias_defaults = dict(migration.get("default_role_by_kind") or {})
        return {
            "known": True,
            "source_kind": kind_text,
            "resolved_type_id": resolved_type_id,
            "spec": spec,
            "default_role": str(alias_defaults.get(kind_text) or migration.get("default_role") or "custom"),
            "registry_fingerprint": str(registry.get("registry_fingerprint") or ""),
            "diagnostics": [],
        }
    if not allow_unknown:
        raise ValueError(f"Unknown node type: {kind_text}")
    opaque = deepcopy(by_type_id[OPAQUE_DISABLED_NODE_TYPE_ID])
    return {
        "known": False,
        "source_kind": kind_text,
        "resolved_type_id": OPAQUE_DISABLED_NODE_TYPE_ID,
        "spec": opaque,
        "default_role": "custom",
        "registry_fingerprint": str(registry.get("registry_fingerprint") or ""),
        "diagnostics": [
            {
                "code": "unknown_node_type",
                "severity": "warning",
                "source_kind": kind_text,
                "resolved_type_id": OPAQUE_DISABLED_NODE_TYPE_ID,
                "message": f"Unknown node type `{kind_text}` was preserved as an opaque disabled node.",
            }
        ],
    }


def project_task_graph_kind(*, authored_kind: str, allow_unknown: bool = False) -> str:
    authored = str(authored_kind or "").strip()
    known = set(task_graph_node_kind_ids())
    if authored in known:
        return authored
    resolved = resolve_node_type(authored, allow_unknown=allow_unknown)
    spec = dict(resolved.get("spec") or {})
    migration = dict(spec.get("migration") or {})
    candidate = str(migration.get("task_graph_projection_kind") or resolved.get("resolved_type_id") or "").strip()
    if candidate in known:
        return candidate
    return OPAQUE_DISABLED_NODE_TYPE_ID


def _normalize_spec(value: dict[str, Any]) -> NodeTypeSpec:
    spec = deepcopy(value)
    spec["type_id"] = str(spec.get("type_id") or "").strip()
    spec["version"] = int(spec.get("version") or 1)
    spec["category"] = str(spec.get("category") or "").strip() or "custom"
    spec["title"] = str(spec.get("title") or "").strip() or spec["type_id"]
    spec["description"] = str(spec.get("description") or "").strip()
    spec["config_schema"] = deepcopy(dict(spec.get("config_schema") or {}))
    typed_ports = dict(spec.get("typed_ports") or {})
    spec["typed_ports"] = {
        "inputs": [deepcopy(item) for item in list(typed_ports.get("inputs") or []) if isinstance(item, dict)],
        "outputs": [deepcopy(item) for item in list(typed_ports.get("outputs") or []) if isinstance(item, dict)],
    }
    spec["compiler_executor_id"] = str(spec.get("compiler_executor_id") or "").strip() or spec["type_id"]
    spec["default_policy"] = deepcopy(dict(spec.get("default_policy") or {}))
    spec["ui_hints"] = deepcopy(dict(spec.get("ui_hints") or {}))
    spec["migration"] = deepcopy(dict(spec.get("migration") or {}))
    spec["internal_only"] = bool(spec.get("internal_only"))
    spec["registry_fingerprint"] = _fingerprint(_execution_fingerprint_view(spec))
    return spec


def _execution_fingerprint_view(spec: NodeTypeSpec) -> dict[str, Any]:
    return {
        "type_id": spec.get("type_id"),
        "version": spec.get("version"),
        "category": spec.get("category"),
        "config_schema": spec.get("config_schema"),
        "typed_ports": spec.get("typed_ports"),
        "compiler_executor_id": spec.get("compiler_executor_id"),
        "default_policy": spec.get("default_policy"),
        "migration": spec.get("migration"),
        "internal_only": bool(spec.get("internal_only")),
    }


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _base_node_type_specs() -> tuple[NodeTypeSpec, ...]:
    agent_roles = list(NODE_TYPE_ROLE_IDS)
    return (
        {
            "type_id": "agent_model",
            "version": 1,
            "category": "agent",
            "title": "Agent / Model",
            "description": "Bounded provider-backed agent lane with explicit routing, prompt, and typed input/output ports.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "routing": {"type": "object", "title": "Routing"},
                    "prompt": {"type": "object", "title": "Prompt"},
                    "execution": {"type": "object", "title": "Execution"},
                    "safety": {"type": "object", "title": "Safety"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "task_context", "port_type": "text", "shape": "single", "required": True}],
                "outputs": [{"port_id": "machine_result", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "agent_lane",
            "default_policy": {
                "execution_backend": "app_server",
                "spawn_mode": "isolated_lane",
                "approval_mode": "ask",
            },
            "ui_hints": {
                "palette_role": "custom",
                "palette_sections": ["planning", "execution"],
                "icon": "bot",
                "tone": "neutral",
                "palette_variants": [
                    {
                        "kind": "supervisor",
                        "label": "Supervisor",
                        "description": "Plans the bounded workflow and coordinates downstream workers.",
                        "palette_sections": ["planning"],
                        "icon": "compass",
                        "tone": "planner",
                    },
                    {
                        "kind": "planner",
                        "label": "Planner",
                        "description": "Breaks work into explicit steps and hands them to other agents.",
                        "palette_sections": ["planning"],
                        "icon": "file-text",
                        "tone": "planner",
                    },
                    {
                        "kind": "researcher",
                        "label": "Researcher",
                        "description": "Collects evidence, docs, or comparisons before synthesis.",
                        "palette_sections": ["planning"],
                        "icon": "search",
                        "tone": "extractor",
                    },
                    {
                        "kind": "extractor",
                        "label": "Extractor",
                        "description": "Pulls structured facts from files, docs, or provider metadata.",
                        "palette_sections": ["planning"],
                        "icon": "database",
                        "tone": "extractor",
                    },
                    {
                        "kind": "worker",
                        "label": "Worker",
                        "description": "Executes the main task and returns the primary artifact.",
                        "palette_sections": ["execution"],
                        "icon": "wrench",
                        "tone": "worker",
                    },
                    {
                        "kind": "coder",
                        "label": "Coder",
                        "description": "Applies code or document changes in a bounded implementation lane.",
                        "palette_sections": ["execution"],
                        "icon": "braces",
                        "tone": "worker",
                    },
                    {
                        "kind": "synthesizer",
                        "label": "Synthesizer",
                        "description": "Merges branch outputs into one bounded answer or artifact set.",
                        "palette_sections": ["execution"],
                        "icon": "sparkles",
                        "tone": "synthesizer",
                    },
                    {
                        "kind": "reviewer",
                        "label": "Reviewer",
                        "description": "Reads outputs critically and returns review feedback or approval.",
                        "palette_sections": ["execution"],
                        "icon": "eye",
                        "tone": "reviewer",
                    },
                    {
                        "kind": "validator",
                        "label": "Validator",
                        "description": "Runs checks, tests, or smoke validation before promotion.",
                        "palette_sections": ["execution"],
                        "icon": "shield-check",
                        "tone": "validator",
                    },
                    {
                        "kind": "custom",
                        "label": "Custom",
                        "description": "Starts as a neutral agent shell with the default fallback icon.",
                        "palette_sections": ["control"],
                        "icon": "bot",
                        "tone": "neutral",
                    },
                ],
            },
            "migration": {
                "legacy_kind_aliases": [
                    "supervisor",
                    "worker",
                    "synthesizer",
                    "extractor",
                    "validator",
                    "reviewer",
                    "planner",
                    "coder",
                    "researcher",
                    "custom",
                ],
                "compatible_roles": agent_roles,
                "default_role": "custom",
                "default_role_by_kind": {
                    "supervisor": "supervisor",
                    "worker": "worker",
                    "synthesizer": "synthesizer",
                    "extractor": "extractor",
                    "validator": "validator",
                    "reviewer": "reviewer",
                    "planner": "planner",
                    "coder": "coder",
                    "researcher": "researcher",
                    "custom": "custom",
                },
                "task_graph_projection_kind": "agent_model",
            },
        },
        {
            "type_id": "mcp_tool",
            "version": 1,
            "category": "mcp",
            "title": "MCP Tool",
            "description": "Executes one declared MCP tool/resource operation through the broker boundary.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "title": "Tool"},
                    "server": {"type": "string", "title": "Server"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "task_context", "port_type": "text", "shape": "single", "required": True}],
                "outputs": [{"port_id": "tool_result", "port_type": "tool_result", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "mcp_tool",
            "default_policy": {"execution_backend": "app_server", "spawn_mode": "inline_lane", "approval_mode": "ask"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "wrench", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "mcp_tool"},
        },
        {
            "type_id": "mcp_resource",
            "version": 1,
            "category": "mcp",
            "title": "MCP Resource",
            "description": "Reads declared MCP resources and projects them into a typed port.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "resource": {"type": "string", "title": "Resource"},
                    "server": {"type": "string", "title": "Server"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "task_context", "port_type": "text", "shape": "single", "required": True}],
                "outputs": [{"port_id": "resource_payload", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "mcp_resource",
            "default_policy": {"execution_backend": "app_server", "spawn_mode": "inline_lane", "approval_mode": "ask"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "database", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "mcp_resource"},
        },
        {
            "type_id": "transform",
            "version": 1,
            "category": "transform",
            "title": "Transform",
            "description": "Applies deterministic shaping or schema transformation between typed ports.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "transform_id": {"type": "string", "title": "Transform id"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "input_payload", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "machine_result", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "transform",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["execution"], "icon": "repeat", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "transform"},
        },
        {
            "type_id": "router_condition",
            "version": 1,
            "category": "control",
            "title": "Router / Condition",
            "description": "Routes control flow based on deterministic conditions or structured guards.",
            "config_schema": {"type": "object", "properties": {"condition": {"type": "object"}}},
            "typed_ports": {
                "inputs": [{"port_id": "input_payload", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "route_decision", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "router_condition",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "git-branch", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "router_condition"},
        },
        {
            "type_id": "loop",
            "version": 1,
            "category": "control",
            "title": "Loop",
            "description": "Repeats a bounded subpath with explicit retry/iteration controls.",
            "config_schema": {"type": "object", "properties": {"max_iterations": {"type": "integer", "minimum": 1}}},
            "typed_ports": {
                "inputs": [{"port_id": "loop_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "loop_result", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "loop",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "repeat", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "loop"},
        },
        {
            "type_id": "subgraph",
            "version": 1,
            "category": "graph",
            "title": "Subgraph",
            "description": "Invokes a nested bounded graph with explicit inputs and outputs.",
            "config_schema": {"type": "object", "properties": {"graph_ref": {"type": "string"}}},
            "typed_ports": {
                "inputs": [{"port_id": "subgraph_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "subgraph_result", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "subgraph",
            "default_policy": {"execution_backend": "app_server", "spawn_mode": "subagent_worker", "approval_mode": "ask"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "boxes", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "subgraph"},
        },
        {
            "type_id": "human_approval",
            "version": 1,
            "category": "approval",
            "title": "Human Approval",
            "description": "Pauses execution behind an explicit review and approval decision.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "review_kind": {"type": "string", "title": "Review kind"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "approval_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "approval_record", "port_type": "approval_record", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "human_approval",
            "default_policy": {"execution_backend": "human_review", "spawn_mode": "manual_only", "approval_mode": "manual"},
            "ui_hints": {"palette_role": "gate", "palette_sections": ["control"], "icon": "lock", "tone": "gate"},
            "migration": {
                "legacy_kind_aliases": ["gate"],
                "compatible_roles": ["gate"],
                "default_role": "gate",
                "default_role_by_kind": {"gate": "gate"},
                "task_graph_projection_kind": "human_approval",
            },
        },
        {
            "type_id": "artifact_source",
            "version": 1,
            "category": "artifact",
            "title": "Artifact Source",
            "description": "Introduces an external or preserved artifact into the graph as a typed source node.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "artifact_kind": {"type": "string", "title": "Artifact kind"},
                    "artifact_uri": {"type": "string", "title": "Artifact URI"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "task_context", "port_type": "text", "shape": "single", "required": False}],
                "outputs": [{"port_id": "artifact_output", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "artifact_source",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "file-text", "tone": "neutral"},
            "migration": {
                "legacy_kind_aliases": ["artifact_source"],
                "compatible_roles": ["custom"],
                "default_role": "custom",
                "default_role_by_kind": {"artifact_source": "custom"},
                "task_graph_projection_kind": "artifact_source",
            },
        },
        {
            "type_id": "artifact_sink",
            "version": 1,
            "category": "artifact",
            "title": "Artifact Sink",
            "description": "Persists or promotes a typed artifact or structured payload as a terminal sink.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "target_kind": {"type": "string", "title": "Target kind"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "artifact_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "artifact_record", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "artifact_sink",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "square-stack", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "artifact_sink"},
        },
        {
            "type_id": OPAQUE_DISABLED_NODE_TYPE_ID,
            "version": 1,
            "category": "opaque",
            "title": "Opaque Disabled Node",
            "description": "Fallback placeholder used to preserve unknown imported node types without executing them.",
            "config_schema": {"type": "object", "properties": {"original_node_type_kind": {"type": "string"}}},
            "typed_ports": {
                "inputs": [{"port_id": "opaque_input", "port_type": "structured_json", "shape": "single", "required": False}],
                "outputs": [{"port_id": "opaque_output", "port_type": "structured_json", "shape": "single", "required": False}],
            },
            "compiler_executor_id": OPAQUE_DISABLED_NODE_TYPE_ID,
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "manual_only", "approval_mode": "manual"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "bot", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": OPAQUE_DISABLED_NODE_TYPE_ID},
            "internal_only": True,
        },
    )
