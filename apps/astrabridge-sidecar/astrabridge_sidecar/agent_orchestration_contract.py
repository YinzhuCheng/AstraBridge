from __future__ import annotations

from copy import deepcopy
from typing import Any

from .mcp_node_policy import resolve_node_mcp_tool_policy
from .node_type_registry import (
    NODE_TYPE_ROLE_IDS,
    compatible_roles_for_kind,
    default_role_for_kind,
    project_task_graph_kind,
    resolve_node_type,
)
from .security import DESKTOP_KEY_PATH_RE, SECRET_RE, SecurityError
from .task_graph_contract import (
    ARTIFACT_KINDS,
    EDGE_STATUSES,
    EDGE_TYPES,
    NODE_DEFINITION_STATUSES,
    NODE_KINDS,
    REVIEW_KINDS,
    SPAWN_MODES,
    SUMMARY_STRATEGIES,
    validate_graph_definition,
)


AGENT_ORCHESTRATION_SCHEMA_VERSION = "astrabridge-agent-orchestration-graph-v1"
GRAPH_POLICY_PERMISSION_MODES = ("ask", "allow", "deny", "manual")
COLLABORATION_MODES = ("default", "plan")
EXECUTION_BACKENDS = ("app_server", "human_review", "local_only")
SELECTION_MODES = ("none", "explicit", "profile")
PROMPT_TEMPLATE_MODES = ("inline", "reference", "migration_stub")
TOOL_APPROVAL_MODES = ("ask", "allow", "deny", "manual")
OUTPUT_MODES = ("artifact_only", "structured_only", "structured_and_artifacts")
RISK_CLASSES = ("low", "moderate", "high", "critical")
INPUT_CONTRACT_MODES = ("task_context", "structured_inputs_and_artifacts", "typed_ports", "task_context_and_typed_ports")
PORT_TYPES = ("text", "structured_json", "image", "audio", "video", "document", "code_diff", "dataset", "tool_result", "agent_report", "approval_record")
PORT_SHAPES = ("single", "list")
SUBAGENT_ISOLATION_MODES = ("lane", "worktree")
UI_LAYOUT_MODES = ("canvas", "inspector_only")
MESSAGE_PART_MODES = ("machine_result", "human_summary", "artifact_ref", "structured_json", "text")
SOURCE_KINDS = ("native_authoring", "legacy_task_graph", "imported_file")

_DEFAULT_CREATED_AT = "2026-07-07T00:00:00+09:00"
_DEFAULT_UPDATED_AT = "2026-07-07T00:05:00+09:00"
_DEFAULT_PROMPT = "TODO: replace migration stub with a canonical prompt template."


def validate_agent_orchestration_graph(
    graph: dict[str, Any],
    *,
    known_profile_ids: set[str] | None = None,
    known_provider_ids: set[str] | None = None,
    known_model_ids: set[str] | None = None,
    known_model_capabilities: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(graph, dict):
        raise TypeError("Agent orchestration graph must be a dict.")
    _reject_secret_like(graph, path="agent_orchestration_graph")
    normalized = deepcopy(graph)
    _require_fields(
        normalized,
        "agent_orchestration_graph",
        (
            "schema_version",
            "graph_id",
            "task_id",
            "title",
            "status",
            "metadata",
            "graph_policy",
            "nodes",
            "edges",
            "migration",
            "state_version",
        ),
    )
    if normalized["schema_version"] != AGENT_ORCHESTRATION_SCHEMA_VERSION:
        raise ValueError("Unexpected agent orchestration schema version.")
    _require_non_empty_string(normalized["graph_id"], field="agent_orchestration_graph.graph_id")
    _require_non_empty_string(normalized["task_id"], field="agent_orchestration_graph.task_id")
    _require_non_empty_string(normalized["title"], field="agent_orchestration_graph.title")
    _require_enum(normalized["status"], field="agent_orchestration_graph.status", allowed=NODE_DEFINITION_STATUSES)
    if not isinstance(normalized["nodes"], list) or not normalized["nodes"]:
        raise ValueError("agent_orchestration_graph.nodes must be a non-empty list.")
    if not isinstance(normalized["edges"], list):
        raise ValueError("agent_orchestration_graph.edges must be a list.")
    if not isinstance(normalized["state_version"], int) or normalized["state_version"] <= 0:
        raise ValueError("agent_orchestration_graph.state_version must be a positive integer.")
    prompt_registry = _ensure_registry(normalized.get("prompt_registry"), label="agent_orchestration_graph.prompt_registry")
    schema_registry = _ensure_registry(normalized.get("schema_registry"), label="agent_orchestration_graph.schema_registry")
    _validate_metadata(normalized["metadata"])
    _validate_migration(normalized["migration"])
    _validate_graph_policy(normalized["graph_policy"])

    node_ids: set[str] = set()
    node_schema_refs: dict[str, str] = {}
    node_ports: dict[str, dict[str, dict[str, Any]]] = {}
    allow_unknown_node_types = str(dict(normalized.get("migration") or {}).get("source_kind") or "").strip() == "imported_file"
    validated_nodes: list[dict[str, Any]] = []
    for node in normalized["nodes"]:
        validated_node = _validate_node(
            node,
            graph_id=str(normalized["graph_id"]),
            prompt_registry=prompt_registry,
            schema_registry=schema_registry,
            known_profile_ids=known_profile_ids or set(),
            known_provider_ids=known_provider_ids or set(),
            known_model_ids=known_model_ids or set(),
            known_model_capabilities=known_model_capabilities or {},
            allow_unknown_node_types=allow_unknown_node_types,
        )
        node_id = validated_node["node_id"]
        if node_id in node_ids:
            raise ValueError(f"agent_orchestration_graph has duplicate node_id: {node_id}")
        node_ids.add(node_id)
        schema_ref = str(validated_node["output_contract"].get("machine_result_schema_ref") or "").strip()
        if schema_ref:
            node_schema_refs[node_id] = schema_ref
        ports = dict(validated_node.get("ports") or {})
        node_ports[node_id] = {
            "inputs": {str(item["port_id"]): item for item in list(ports.get("inputs") or []) if isinstance(item, dict)},
            "outputs": {str(item["port_id"]): item for item in list(ports.get("outputs") or []) if isinstance(item, dict)},
        }
        validated_nodes.append(validated_node)
    normalized["nodes"] = validated_nodes

    edge_ids: set[str] = set()
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in normalized["edges"]:
        validated_edge = _validate_edge(
            edge,
            graph_id=str(normalized["graph_id"]),
            known_node_ids=node_ids,
            schema_registry=schema_registry,
            node_ports=node_ports,
        )
        edge_id = validated_edge["edge_id"]
        if edge_id in edge_ids:
            raise ValueError(f"agent_orchestration_graph has duplicate edge_id: {edge_id}")
        edge_ids.add(edge_id)
        adjacency[validated_edge["from_node_id"]].append(validated_edge["to_node_id"])
        _validate_edge_schema_refs(validated_edge, source_schema_refs=node_schema_refs)

    entry_node_ids = _normalize_string_list(normalized["graph_policy"].get("entry_node_ids"), field="graph_policy.entry_node_ids", required=True)
    if not entry_node_ids:
        raise ValueError("agent_orchestration_graph entry nodes must not be empty.")
    unknown_entry_ids = sorted(set(entry_node_ids).difference(node_ids))
    if unknown_entry_ids:
        raise ValueError(f"agent_orchestration_graph entry nodes reference unknown node ids: {', '.join(unknown_entry_ids)}")
    normalized["graph_policy"]["entry_node_ids"] = entry_node_ids

    depth = _compute_graph_depth(entry_node_ids=entry_node_ids, adjacency=adjacency, node_ids=node_ids)
    max_depth = int(normalized["graph_policy"]["max_depth"])
    if depth > max_depth:
        raise ValueError(f"agent_orchestration_graph depth {depth} exceeds max_depth {max_depth}.")

    _reject_secret_like(normalized, path="agent_orchestration_graph")
    return normalized


def lift_task_graph_to_agent_orchestration_graph(task_graph: dict[str, Any]) -> dict[str, Any]:
    legacy = validate_graph_definition(task_graph)
    warnings: list[str] = []
    schema_registry: dict[str, Any] = {}
    nodes: list[dict[str, Any]] = []
    positions: dict[str, dict[str, float]] = {}
    node_schema_refs: dict[str, str] = {}

    for node in legacy["nodes"]:
        role = _default_role_for_kind(str(node["kind"]))
        execution_policy = dict(node["execution_policy"])
        output_contract = dict(node["output_contract"])
        machine_schema = output_contract.get("machine_result_schema")
        schema_ref = ""
        if isinstance(machine_schema, dict) and machine_schema:
            schema_ref = f"schema.{node['node_id']}.machine_result"
            schema_registry[schema_ref] = deepcopy(machine_schema)
        elif not bool(output_contract.get("artifact_only")):
            warnings.append(f"node:{node['node_id']}: missing explicit machine_result_schema in legacy graph")
        artifact_outputs = _normalized_legacy_artifact_outputs(
            output_contract.get("artifact_outputs"),
            node_id=str(node["node_id"]),
            has_machine_schema=bool(schema_ref),
            warnings=warnings,
        )
        prompt_template = str(node.get("human_summary_template") or "").strip() or _DEFAULT_PROMPT
        warnings.append(f"node:{node['node_id']}: lifted legacy graph without first-class prompt definition")
        if not isinstance(node.get("tools"), dict):
            warnings.append(f"node:{node['node_id']}: lifted legacy graph without explicit tool policy")
        positions[str(node["node_id"])] = deepcopy(node["position"])
        node_schema_refs[str(node["node_id"])] = schema_ref
        lifted_tools = (
            deepcopy(node.get("tools"))
            if isinstance(node.get("tools"), dict)
            else {
                "approval_mode": "ask",
                "allowed_tool_classes": [],
                "supports_mcp": False,
                "supports_web": False,
                "supports_apply_patch": bool(execution_policy.get("allow_code_changes")),
                "supports_shell": bool(execution_policy.get("allow_code_changes") or execution_policy.get("allow_install")),
            }
        )
        nodes.append(
            {
                "node_id": node["node_id"],
                "kind": node["kind"],
                "label": node["label"],
                "role": role,
                "card_ref": node["agent_card_ref"],
                "routing": {"selection_mode": "none"},
                "prompt": {
                    "template_mode": "migration_stub",
                    "template": prompt_template,
                },
                "tools": lifted_tools,
                "ports": {
                    "inputs": [
                        {
                            "port_id": "task_context",
                            "label": "Task Context",
                            "port_type": "text",
                            "shape": "single",
                            "required": True,
                        }
                    ],
                    "outputs": _legacy_output_ports(
                        node=node,
                        schema_ref=schema_ref,
                        artifact_outputs=artifact_outputs,
                    ),
                },
                "input_contract": {"mode": "task_context_and_typed_ports", "port_ids": ["task_context"]},
                "output_contract": {
                    "mode": "artifact_only" if bool(output_contract.get("artifact_only")) else "structured_and_artifacts",
                    "machine_result_schema_ref": schema_ref or None,
                    "artifact_specs": [
                        {"kind": artifact_kind, "id": f"{node['node_id']}_{artifact_kind}"}
                        for artifact_kind in artifact_outputs
                    ],
                    "human_summary_required": bool(output_contract.get("human_summary_required")),
                },
                "execution": {
                    "spawn_mode": execution_policy["spawn_mode"],
                    "timeout_ms": execution_policy["timeout_ms"],
                    "retry_policy": deepcopy(execution_policy["retry_policy"]),
                    "execution_backend": "human_review" if execution_policy["spawn_mode"] == "manual_only" else "app_server",
                    "collaboration_mode": "default",
                    "subagent_policy": _legacy_subagent_policy(execution_policy=execution_policy),
                },
                "safety": {
                    "risk_class": _risk_class_for_legacy_policy(execution_policy),
                    "allow_provider_calls": bool(execution_policy["allow_provider_calls"]),
                    "allow_code_changes": bool(execution_policy["allow_code_changes"]),
                    "allow_install": bool(execution_policy["allow_install"]),
                    "requires_human_approval": bool(execution_policy["requires_human_approval"]),
                    "approval_kind": dict(node.get("approval_gate") or {}).get("review_kind"),
                },
                "ui": {"position": deepcopy(node["position"]), "layout_mode": "canvas"},
                "status": node["status"],
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in legacy["edges"]:
        warnings.append(f"edge:{edge['edge_id']}: lifted legacy graph without first-class handoff_contract")
        edges.append(
            {
                "edge_id": edge["edge_id"],
                "from_node_id": edge["from_node_id"],
                "to_node_id": edge["to_node_id"],
                "edge_type": edge["edge_type"],
                "handoff_contract": {
                    "message_template": f"Deliver the required output from {edge['from_node_id']} to {edge['to_node_id']}.",
                    "message_part_modes": ["machine_result", "human_summary"],
                    "required_output_schema_refs": _required_refs_for_edge(edge, node_schema_refs=node_schema_refs),
                    "port_bindings": _legacy_port_bindings(edge=edge, node_schema_refs=node_schema_refs, legacy=legacy),
                },
                "context_policy": deepcopy(edge["context_policy"]),
                "ui": {"position": _edge_midpoint(edge=edge, positions=positions), "layout_mode": "canvas"},
                "status": edge["status"],
            }
        )

    legacy_graph_policy = deepcopy(dict(legacy.get("graph_policy") or {}))
    raw_max_depth = legacy_graph_policy.get("max_depth")
    if isinstance(raw_max_depth, int) and raw_max_depth > 0:
        max_depth = raw_max_depth
    else:
        warnings.append("graph: lifted legacy task graph without graph_policy.max_depth; defaulted to 2")
        max_depth = 2
    lifted = {
        "schema_version": AGENT_ORCHESTRATION_SCHEMA_VERSION,
        "graph_id": legacy["graph_id"],
        "task_id": legacy["task_id"],
        "title": legacy["title"],
        "template_id": legacy.get("template_id"),
        "status": legacy["status"],
        "metadata": {
            "description": f"Lifted from legacy task graph template {legacy.get('template_id')}.",
            "tags": ["legacy-lift"],
            "owners": [],
            "created_at": legacy.get("created_at") or _DEFAULT_CREATED_AT,
            "updated_at": legacy.get("updated_at") or _DEFAULT_UPDATED_AT,
        },
        "graph_policy": {
            "entry_node_ids": list(dict(legacy["graph_policy"]).get("entry_node_ids") or []),
            "max_depth": max_depth,
            "default_permission_mode": "ask",
            "default_collaboration_mode": "default",
            "default_execution_backend": "app_server",
            "requires_dry_run_before_live": True,
            "mcp_policy": deepcopy(legacy_graph_policy.get("mcp_policy") or {}),
        },
        "nodes": nodes,
        "edges": edges,
        "schema_registry": schema_registry,
        "migration": {
            "source_kind": "legacy_task_graph",
            "compiled_task_graph_version": legacy["schema_version"],
            "warnings": warnings,
            "compatibility": {
                "lowering_mode": "lossy_legacy_task_graph",
                "preserves_unknown_fields": False,
                "notes": [
                    "Legacy task graphs are upgraded into typed ports with migration stubs.",
                    "Lowering back to task graph preserves execution, safety, context, and artifact semantics, but not all canonical typed-port metadata.",
                ],
            },
        },
        "state_version": int(legacy.get("state_version") or 1),
    }
    return validate_agent_orchestration_graph(lifted)


def lower_agent_orchestration_graph_to_task_graph(graph: dict[str, Any]) -> dict[str, Any]:
    canonical = validate_agent_orchestration_graph(graph)
    schema_registry = dict(canonical.get("schema_registry") or {})
    nodes: list[dict[str, Any]] = []
    for node in canonical["nodes"]:
        output_contract = dict(node["output_contract"])
        machine_schema_ref = output_contract.get("machine_result_schema_ref")
        artifact_only = output_contract["mode"] == "artifact_only"
        lowered_node: dict[str, Any] = {
            "node_id": node["node_id"],
            "graph_id": canonical["graph_id"],
            "kind": project_task_graph_kind(authored_kind=str(node["kind"]), allow_unknown=True),
            "label": node["label"],
            "agent_card_ref": node["card_ref"],
            "tools": deepcopy(dict(node.get("tools") or {})),
            "execution_policy": {
                "spawn_mode": node["execution"]["spawn_mode"],
                "retry_policy": deepcopy(node["execution"]["retry_policy"]),
                "timeout_ms": max(1, int(node["execution"]["timeout_ms"])),
                "allow_provider_calls": bool(node["safety"]["allow_provider_calls"]),
                "allow_code_changes": bool(node["safety"]["allow_code_changes"]),
                "allow_install": bool(node["safety"]["allow_install"]),
                "requires_human_approval": bool(node["safety"]["requires_human_approval"]),
            },
            "output_contract": {
                "human_summary_required": bool(output_contract.get("human_summary_required")),
                "artifact_outputs": [spec["kind"] for spec in list(output_contract.get("artifact_specs") or [])],
                "artifact_only": artifact_only,
            },
            "position": deepcopy(node["ui"]["position"]),
            "status": node["status"],
            "ui_hints": {
                "node_type_id": str(node.get("resolved_node_type_id") or ""),
                "node_type_registry_fingerprint": str(node.get("node_type_registry_fingerprint") or ""),
                "palette_role": str(node.get("role") or "custom"),
            },
        }
        if machine_schema_ref:
            lowered_node["output_contract"]["machine_result_schema"] = deepcopy(schema_registry.get(machine_schema_ref) or {"type": "object"})
        approval_kind = str(node["safety"].get("approval_kind") or "").strip()
        if approval_kind:
            lowered_node["approval_gate"] = {"review_kind": approval_kind}
        diagnostics = [
            deepcopy(item)
            for item in list(node.get("node_type_diagnostics") or [])
            if isinstance(item, dict)
        ]
        if diagnostics:
            lowered_node["status"] = "disabled"
            lowered_node["ui_hints"]["node_type_diagnostics"] = diagnostics
            lowered_node["ui_hints"]["original_node_type_kind"] = str(node.get("kind") or "")
        nodes.append(lowered_node)

    edges: list[dict[str, Any]] = []
    for edge in canonical["edges"]:
        edges.append(
            {
                "edge_id": edge["edge_id"],
                "graph_id": canonical["graph_id"],
                "from_node_id": edge["from_node_id"],
                "to_node_id": edge["to_node_id"],
                "edge_type": edge["edge_type"],
                "context_policy": deepcopy(edge["context_policy"]),
                "status": edge["status"],
            }
        )

    lowered = {
        "schema_version": "astrabridge-task-graph-v1",
        "graph_id": canonical["graph_id"],
        "task_id": canonical["task_id"],
        "title": canonical["title"],
        "template_id": canonical.get("template_id") or "supervisor_worker_synthesizer",
        "status": canonical["status"],
        "nodes": nodes,
        "edges": edges,
        "graph_policy": {
            "entry_node_ids": list(canonical["graph_policy"]["entry_node_ids"]),
            "mcp_policy": deepcopy(dict(canonical["graph_policy"]).get("mcp_policy") or {}),
        },
        "created_at": canonical["metadata"]["created_at"],
        "updated_at": canonical["metadata"]["updated_at"],
        "state_version": canonical["state_version"],
    }
    return validate_graph_definition(lowered)


def _validate_metadata(value: Any) -> None:
    data = _ensure_dict(value, "metadata")
    _require_fields(data, "metadata", ("description", "created_at", "updated_at"))
    _require_non_empty_string(data["description"], field="metadata.description")
    _require_non_empty_string(data["created_at"], field="metadata.created_at")
    _require_non_empty_string(data["updated_at"], field="metadata.updated_at")


def _validate_migration(value: Any) -> None:
    data = _ensure_dict(value, "migration")
    _require_fields(data, "migration", ("source_kind", "compiled_task_graph_version"))
    _require_enum(data["source_kind"], field="migration.source_kind", allowed=SOURCE_KINDS)
    _require_non_empty_string(data["compiled_task_graph_version"], field="migration.compiled_task_graph_version")
    warnings = data.get("warnings")
    if warnings is not None:
        if not isinstance(warnings, list) or not all(isinstance(item, str) and item.strip() for item in warnings):
            raise ValueError("migration.warnings must be a list of non-empty strings when present.")
    compatibility = data.get("compatibility")
    if compatibility is not None:
        compat = _ensure_dict(compatibility, "migration.compatibility")
        _require_fields(compat, "migration.compatibility", ("lowering_mode", "preserves_unknown_fields", "notes"))
        _require_non_empty_string(compat["lowering_mode"], field="migration.compatibility.lowering_mode")
        _require_bool(compat["preserves_unknown_fields"], field="migration.compatibility.preserves_unknown_fields")
        if not isinstance(compat["notes"], list) or not all(isinstance(item, str) and item.strip() for item in compat["notes"]):
            raise ValueError("migration.compatibility.notes must be a list of non-empty strings.")


def _validate_graph_policy(value: Any) -> None:
    data = _ensure_dict(value, "graph_policy")
    _require_fields(
        data,
        "graph_policy",
        (
            "entry_node_ids",
            "max_depth",
            "default_permission_mode",
            "default_collaboration_mode",
            "default_execution_backend",
            "requires_dry_run_before_live",
        ),
    )
    _normalize_string_list(data["entry_node_ids"], field="graph_policy.entry_node_ids", required=True)
    if not isinstance(data["max_depth"], int) or data["max_depth"] <= 0:
        raise ValueError("graph_policy.max_depth must be a positive integer.")
    _require_enum(data["default_permission_mode"], field="graph_policy.default_permission_mode", allowed=GRAPH_POLICY_PERMISSION_MODES)
    _require_enum(data["default_collaboration_mode"], field="graph_policy.default_collaboration_mode", allowed=COLLABORATION_MODES)
    _require_enum(data["default_execution_backend"], field="graph_policy.default_execution_backend", allowed=EXECUTION_BACKENDS)
    _require_bool(data["requires_dry_run_before_live"], field="graph_policy.requires_dry_run_before_live")
    if data.get("mcp_policy") is not None:
        resolve_node_mcp_tool_policy(
            tools={},
            graph_policy={"mcp_policy": deepcopy(data.get("mcp_policy"))},
            mcp_preset_ids=[],
            node_id="graph_policy_validation",
        )


def _validate_node(
    value: Any,
    *,
    graph_id: str,
    prompt_registry: dict[str, Any],
    schema_registry: dict[str, Any],
    known_profile_ids: set[str],
    known_provider_ids: set[str],
    known_model_ids: set[str],
    known_model_capabilities: dict[str, dict[str, Any]],
    allow_unknown_node_types: bool,
) -> dict[str, Any]:
    data = _ensure_dict(value, "agent_orchestration_node")
    _require_fields(
        data,
        "agent_orchestration_node",
        ("node_id", "kind", "label", "role", "card_ref", "routing", "prompt", "tools", "ports", "input_contract", "output_contract", "execution", "safety", "ui", "status"),
    )
    validated = deepcopy(data)
    validated["node_id"] = _require_non_empty_string(validated["node_id"], field="agent_orchestration_node.node_id")
    validated["kind"] = _require_non_empty_string(validated["kind"], field="agent_orchestration_node.kind")
    _require_non_empty_string(validated["label"], field="agent_orchestration_node.label")
    _require_enum(validated["role"], field="agent_orchestration_node.role", allowed=NODE_TYPE_ROLE_IDS)
    _require_non_empty_string(validated["card_ref"], field="agent_orchestration_node.card_ref")
    _require_enum(validated["status"], field="agent_orchestration_node.status", allowed=NODE_DEFINITION_STATUSES)
    resolved_node_type = resolve_node_type(str(validated["kind"]), allow_unknown=allow_unknown_node_types)
    allowed_roles = compatible_roles_for_kind(str(validated["kind"]))
    if str(validated["role"]) not in allowed_roles:
        raise ValueError(f"agent_orchestration_node.role {validated['role']} is incompatible with kind {validated['kind']}.")
    validated["resolved_node_type_id"] = str(resolved_node_type.get("resolved_type_id") or "")
    validated["resolved_node_type_version"] = int(dict(resolved_node_type.get("spec") or {}).get("version") or 1)
    validated["node_type_registry_fingerprint"] = str(resolved_node_type.get("registry_fingerprint") or "")
    diagnostics = [deepcopy(item) for item in list(resolved_node_type.get("diagnostics") or []) if isinstance(item, dict)]
    if diagnostics:
        validated["status"] = "disabled"
        validated["node_type_diagnostics"] = diagnostics
    _validate_prompt(validated["prompt"], node_id=validated["node_id"], prompt_registry=prompt_registry)
    _validate_tools(validated["tools"], node_id=validated["node_id"])
    _validate_output_contract(validated["output_contract"], node_id=validated["node_id"], schema_registry=schema_registry)
    port_summary = _validate_ports(validated["ports"], node_id=validated["node_id"], schema_registry=schema_registry, output_contract=validated["output_contract"])
    _validate_input_contract(validated["input_contract"], node_id=validated["node_id"], schema_registry=schema_registry, input_port_ids=port_summary["input_port_ids"])
    _validate_routing(
        validated["routing"],
        node_id=validated["node_id"],
        known_profile_ids=known_profile_ids,
        known_provider_ids=known_provider_ids,
        known_model_ids=known_model_ids,
        known_model_capabilities=known_model_capabilities,
        input_port_types=port_summary["input_port_types"],
        output_port_types=port_summary["output_port_types"],
    )
    _validate_execution(validated["execution"], node_id=validated["node_id"])
    _validate_safety(validated["safety"], node_id=validated["node_id"])
    _validate_ui(validated["ui"], label=f"agent_orchestration_node.ui[{validated['node_id']}]")
    return validated


def _validate_edge(value: Any, *, graph_id: str, known_node_ids: set[str], schema_registry: dict[str, Any], node_ports: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    data = _ensure_dict(value, "agent_orchestration_edge")
    _require_fields(
        data,
        "agent_orchestration_edge",
        ("edge_id", "from_node_id", "to_node_id", "edge_type", "handoff_contract", "context_policy", "ui", "status"),
    )
    validated = deepcopy(data)
    validated["edge_id"] = _require_non_empty_string(validated["edge_id"], field="agent_orchestration_edge.edge_id")
    validated["from_node_id"] = _require_non_empty_string(validated["from_node_id"], field="agent_orchestration_edge.from_node_id")
    validated["to_node_id"] = _require_non_empty_string(validated["to_node_id"], field="agent_orchestration_edge.to_node_id")
    if validated["from_node_id"] == validated["to_node_id"]:
        raise ValueError(f"agent_orchestration_edge {validated['edge_id']} must not connect a node to itself.")
    if validated["from_node_id"] not in known_node_ids or validated["to_node_id"] not in known_node_ids:
        raise ValueError(f"agent_orchestration_edge {validated['edge_id']} references unknown node ids.")
    _require_enum(validated["edge_type"], field="agent_orchestration_edge.edge_type", allowed=EDGE_TYPES)
    _require_enum(validated["status"], field="agent_orchestration_edge.status", allowed=EDGE_STATUSES)
    _validate_handoff_contract(
        validated["handoff_contract"],
        edge_id=validated["edge_id"],
        schema_registry=schema_registry,
        source_ports=dict(node_ports.get(validated["from_node_id"]) or {}).get("outputs", {}),
        target_ports=dict(node_ports.get(validated["to_node_id"]) or {}).get("inputs", {}),
    )
    _validate_context_policy(validated["context_policy"], edge_id=validated["edge_id"])
    _validate_ui(validated["ui"], label=f"agent_orchestration_edge.ui[{validated['edge_id']}]")
    return validated


def _validate_routing(
    value: Any,
    *,
    node_id: str,
    known_profile_ids: set[str],
    known_provider_ids: set[str],
    known_model_ids: set[str],
    known_model_capabilities: dict[str, dict[str, Any]],
    input_port_types: set[str],
    output_port_types: set[str],
) -> None:
    data = _ensure_dict(value, f"routing[{node_id}]")
    _require_fields(data, f"routing[{node_id}]", ("selection_mode",))
    selection_mode = _require_enum(data["selection_mode"], field=f"routing[{node_id}].selection_mode", allowed=SELECTION_MODES)
    capability_claims = data.get("capability_claims")
    declared_inputs: set[str] = set()
    declared_outputs: set[str] = set()
    if capability_claims is not None:
        claims = _ensure_dict(capability_claims, f"routing[{node_id}].capability_claims")
        declared_inputs = _normalize_enum_list(
            claims.get("input_port_types"),
            field=f"routing[{node_id}].capability_claims.input_port_types",
            allowed=PORT_TYPES,
        )
        declared_outputs = _normalize_enum_list(
            claims.get("output_port_types"),
            field=f"routing[{node_id}].capability_claims.output_port_types",
            allowed=PORT_TYPES,
        )
        if input_port_types and not input_port_types.issubset(declared_inputs):
            raise ValueError(f"routing[{node_id}] capability claims must include every declared input port type.")
        if output_port_types and not output_port_types.issubset(declared_outputs):
            raise ValueError(f"routing[{node_id}] capability claims must include every declared output port type.")
    if selection_mode == "profile":
        profile_id = _require_non_empty_string(data.get("profile_id"), field=f"routing[{node_id}].profile_id")
        if known_profile_ids and profile_id not in known_profile_ids:
            raise ValueError(f"routing[{node_id}].profile_id references unknown profile: {profile_id}")
        return
    if selection_mode == "explicit":
        provider_id = _require_non_empty_string(data.get("provider_id"), field=f"routing[{node_id}].provider_id")
        model_id = _require_non_empty_string(data.get("model_id"), field=f"routing[{node_id}].model_id")
        if known_provider_ids and provider_id not in known_provider_ids:
            raise ValueError(f"routing[{node_id}].provider_id references unknown provider: {provider_id}")
        if known_model_ids and model_id not in known_model_ids:
            raise ValueError(f"routing[{node_id}].model_id references unknown model: {model_id}")
        model_caps = dict(known_model_capabilities.get(model_id) or {})
        if model_caps:
            supported_inputs = _normalize_enum_list(
                model_caps.get("input_port_types"),
                field=f"known_model_capabilities[{model_id}].input_port_types",
                allowed=PORT_TYPES,
            )
            supported_outputs = _normalize_enum_list(
                model_caps.get("output_port_types"),
                field=f"known_model_capabilities[{model_id}].output_port_types",
                allowed=PORT_TYPES,
            )
            unsupported_inputs = sorted(input_port_types.difference(supported_inputs))
            unsupported_outputs = sorted(output_port_types.difference(supported_outputs))
            if unsupported_inputs or unsupported_outputs:
                issues: list[str] = []
                if unsupported_inputs:
                    issues.append(f"unsupported input port types: {', '.join(unsupported_inputs)}")
                if unsupported_outputs:
                    issues.append(f"unsupported output port types: {', '.join(unsupported_outputs)}")
                raise ValueError(f"routing[{node_id}] declares invalid provider/model modality claims for model {model_id}: {'; '.join(issues)}")


def _validate_prompt(value: Any, *, node_id: str, prompt_registry: dict[str, Any]) -> None:
    data = _ensure_dict(value, f"prompt[{node_id}]")
    _require_fields(data, f"prompt[{node_id}]", ("template_mode",))
    template_mode = _require_enum(data["template_mode"], field=f"prompt[{node_id}].template_mode", allowed=PROMPT_TEMPLATE_MODES)
    if template_mode == "reference":
        template_ref = _require_non_empty_string(data.get("template_ref"), field=f"prompt[{node_id}].template_ref")
        if prompt_registry and template_ref not in prompt_registry:
            raise ValueError(f"prompt[{node_id}].template_ref references unknown prompt template: {template_ref}")
        return
    _require_non_empty_string(data.get("template"), field=f"prompt[{node_id}].template")


def _validate_tools(value: Any, *, node_id: str) -> None:
    data = _ensure_dict(value, f"tools[{node_id}]")
    _require_fields(data, f"tools[{node_id}]", ("approval_mode", "allowed_tool_classes"))
    _require_enum(data["approval_mode"], field=f"tools[{node_id}].approval_mode", allowed=TOOL_APPROVAL_MODES)
    if not isinstance(data["allowed_tool_classes"], list) or not all(isinstance(item, str) for item in data["allowed_tool_classes"]):
        raise ValueError(f"tools[{node_id}].allowed_tool_classes must be a list of strings.")
    resolve_node_mcp_tool_policy(
        tools=deepcopy(data),
        mcp_preset_ids=[
            str(item).strip()
            for item in list(data.get("mcp_preset_ids") or [])
            if str(item or "").strip()
        ],
        graph_policy={},
        node_id=node_id,
    )


def _validate_input_contract(value: Any, *, node_id: str, schema_registry: dict[str, Any], input_port_ids: set[str]) -> None:
    data = _ensure_dict(value, f"input_contract[{node_id}]")
    _require_fields(data, f"input_contract[{node_id}]", ("mode",))
    mode = _require_enum(data["mode"], field=f"input_contract[{node_id}].mode", allowed=INPUT_CONTRACT_MODES)
    for ref in list(data.get("required_schema_refs") or []):
        ref_text = _require_non_empty_string(ref, field=f"input_contract[{node_id}].required_schema_refs")
        if schema_registry and ref_text not in schema_registry:
            raise ValueError(f"input_contract[{node_id}] references unknown schema: {ref_text}")
    declared_port_ids = _normalize_string_list(data.get("port_ids"), field=f"input_contract[{node_id}].port_ids", required=False)
    unknown_port_ids = sorted(set(declared_port_ids).difference(input_port_ids))
    if unknown_port_ids:
        raise ValueError(f"input_contract[{node_id}] references unknown input ports: {', '.join(unknown_port_ids)}")
    if mode in {"typed_ports", "task_context_and_typed_ports"} and not declared_port_ids:
        raise ValueError(f"input_contract[{node_id}] must declare port_ids for typed port modes.")


def _validate_output_contract(value: Any, *, node_id: str, schema_registry: dict[str, Any]) -> None:
    data = _ensure_dict(value, f"output_contract[{node_id}]")
    _require_fields(data, f"output_contract[{node_id}]", ("mode", "artifact_specs"))
    mode = _require_enum(data["mode"], field=f"output_contract[{node_id}].mode", allowed=OUTPUT_MODES)
    artifact_specs = data["artifact_specs"]
    if not isinstance(artifact_specs, list):
        raise ValueError(f"output_contract[{node_id}].artifact_specs must be a list.")
    for spec in artifact_specs:
        _validate_artifact_spec(spec, node_id=node_id)
    schema_ref = data.get("machine_result_schema_ref")
    if mode == "artifact_only":
        if schema_ref not in (None, ""):
            _require_non_empty_string(schema_ref, field=f"output_contract[{node_id}].machine_result_schema_ref")
        return
    schema_ref_text = _require_non_empty_string(schema_ref, field=f"output_contract[{node_id}].machine_result_schema_ref")
    if schema_registry and schema_ref_text not in schema_registry:
        raise ValueError(f"output_contract[{node_id}] references unknown schema: {schema_ref_text}")


def _validate_ports(value: Any, *, node_id: str, schema_registry: dict[str, Any], output_contract: dict[str, Any]) -> dict[str, Any]:
    data = _ensure_dict(value, f"ports[{node_id}]")
    _require_fields(data, f"ports[{node_id}]", ("inputs", "outputs"))
    inputs = data["inputs"]
    outputs = data["outputs"]
    if not isinstance(inputs, list):
        raise ValueError(f"ports[{node_id}].inputs must be a list.")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError(f"ports[{node_id}].outputs must be a non-empty list.")
    seen: set[str] = set()
    input_port_ids: set[str] = set()
    input_port_types: set[str] = set()
    output_port_types: set[str] = set()
    output_schema_refs: set[str] = set()
    output_artifact_kinds: set[str] = set()
    for item in inputs:
        summary = _validate_port_spec(item, node_id=node_id, port_group="inputs", schema_registry=schema_registry, seen=seen)
        input_port_ids.add(summary["port_id"])
        input_port_types.add(summary["port_type"])
    for item in outputs:
        summary = _validate_port_spec(item, node_id=node_id, port_group="outputs", schema_registry=schema_registry, seen=seen)
        output_port_types.add(summary["port_type"])
        if summary["schema_ref"]:
            output_schema_refs.add(summary["schema_ref"])
        if summary["artifact_kind"]:
            output_artifact_kinds.add(summary["artifact_kind"])
    schema_ref = str(output_contract.get("machine_result_schema_ref") or "").strip()
    if schema_ref and schema_ref not in output_schema_refs:
        raise ValueError(f"ports[{node_id}] must expose machine_result_schema_ref {schema_ref} on an output port.")
    artifact_specs = list(output_contract.get("artifact_specs") or [])
    declared_artifacts = {str(spec.get("kind") or "").strip() for spec in artifact_specs if isinstance(spec, dict)}
    missing_artifacts = sorted(kind for kind in declared_artifacts if kind and kind not in output_artifact_kinds)
    if missing_artifacts:
        raise ValueError(f"ports[{node_id}] must expose output artifact kinds declared in output_contract: {', '.join(missing_artifacts)}")
    return {
        "input_port_ids": input_port_ids,
        "input_port_types": input_port_types,
        "output_port_types": output_port_types,
    }


def _validate_port_spec(
    value: Any,
    *,
    node_id: str,
    port_group: str,
    schema_registry: dict[str, Any],
    seen: set[str],
) -> dict[str, str]:
    data = _ensure_dict(value, f"ports[{node_id}].{port_group}")
    _require_fields(data, f"ports[{node_id}].{port_group}", ("port_id", "port_type", "shape"))
    port_id = _require_non_empty_string(data["port_id"], field=f"ports[{node_id}].{port_group}.port_id")
    if port_id in seen:
        raise ValueError(f"ports[{node_id}] has duplicate port_id: {port_id}")
    seen.add(port_id)
    port_type = _require_enum(data["port_type"], field=f"ports[{node_id}].{port_group}.port_type", allowed=PORT_TYPES)
    _require_enum(data["shape"], field=f"ports[{node_id}].{port_group}.shape", allowed=PORT_SHAPES)
    if "required" in data and data["required"] is not None:
        _require_bool(data["required"], field=f"ports[{node_id}].{port_group}.required")
    if "label" in data and data["label"] is not None:
        _require_non_empty_string(data["label"], field=f"ports[{node_id}].{port_group}.label")
    schema_ref = str(data.get("schema_ref") or "").strip()
    artifact_kind = str(data.get("artifact_kind") or "").strip()
    if schema_ref:
        if schema_registry and schema_ref not in schema_registry:
            raise ValueError(f"ports[{node_id}].{port_group} references unknown schema: {schema_ref}")
    if artifact_kind:
        _require_enum(artifact_kind, field=f"ports[{node_id}].{port_group}.artifact_kind", allowed=ARTIFACT_KINDS)
    return {"port_id": port_id, "port_type": port_type, "schema_ref": schema_ref, "artifact_kind": artifact_kind}


def _validate_execution(value: Any, *, node_id: str) -> None:
    data = _ensure_dict(value, f"execution[{node_id}]")
    _require_fields(data, f"execution[{node_id}]", ("spawn_mode", "timeout_ms", "retry_policy"))
    spawn_mode = _require_enum(data["spawn_mode"], field=f"execution[{node_id}].spawn_mode", allowed=SPAWN_MODES)
    if not isinstance(data["timeout_ms"], int) or data["timeout_ms"] < 0:
        raise ValueError(f"execution[{node_id}].timeout_ms must be a non-negative integer.")
    if not isinstance(data["retry_policy"], dict):
        raise ValueError(f"execution[{node_id}].retry_policy must be a dict.")
    backend = data.get("execution_backend")
    if backend is not None:
        _require_enum(backend, field=f"execution[{node_id}].execution_backend", allowed=EXECUTION_BACKENDS)
    collaboration_mode = data.get("collaboration_mode")
    if collaboration_mode is not None:
        _require_enum(collaboration_mode, field=f"execution[{node_id}].collaboration_mode", allowed=COLLABORATION_MODES)
    subagent_policy = data.get("subagent_policy")
    if spawn_mode == "subagent_worker":
        if not isinstance(subagent_policy, dict):
            raise ValueError(f"execution[{node_id}].subagent_policy is required for subagent_worker nodes.")
        _validate_subagent_policy(subagent_policy, node_id=node_id)
    elif subagent_policy is not None:
        _validate_subagent_policy(subagent_policy, node_id=node_id)


def _validate_safety(value: Any, *, node_id: str) -> None:
    data = _ensure_dict(value, f"safety[{node_id}]")
    _require_fields(
        data,
        f"safety[{node_id}]",
        ("risk_class", "allow_provider_calls", "allow_code_changes", "allow_install", "requires_human_approval"),
    )
    risk_class = _require_enum(data["risk_class"], field=f"safety[{node_id}].risk_class", allowed=RISK_CLASSES)
    _require_bool(data["allow_provider_calls"], field=f"safety[{node_id}].allow_provider_calls")
    allow_code_changes = _require_bool(data["allow_code_changes"], field=f"safety[{node_id}].allow_code_changes")
    allow_install = _require_bool(data["allow_install"], field=f"safety[{node_id}].allow_install")
    requires_human_approval = _require_bool(data["requires_human_approval"], field=f"safety[{node_id}].requires_human_approval")
    approval_kind = data.get("approval_kind")
    if approval_kind not in (None, ""):
        _require_enum(approval_kind, field=f"safety[{node_id}].approval_kind", allowed=REVIEW_KINDS)
    if (allow_code_changes or allow_install or risk_class in {"high", "critical"}) and not requires_human_approval:
        raise ValueError(f"safety[{node_id}] must require human approval for high-risk permissions.")


def _validate_handoff_contract(value: Any, *, edge_id: str, schema_registry: dict[str, Any], source_ports: dict[str, dict[str, Any]], target_ports: dict[str, dict[str, Any]]) -> None:
    data = _ensure_dict(value, f"handoff_contract[{edge_id}]")
    _require_fields(data, f"handoff_contract[{edge_id}]", ("message_template", "message_part_modes", "required_output_schema_refs", "port_bindings"))
    _require_non_empty_string(data["message_template"], field=f"handoff_contract[{edge_id}].message_template")
    if not isinstance(data["message_part_modes"], list) or not data["message_part_modes"]:
        raise ValueError(f"handoff_contract[{edge_id}].message_part_modes must be a non-empty list.")
    for item in data["message_part_modes"]:
        _require_enum(item, field=f"handoff_contract[{edge_id}].message_part_modes", allowed=MESSAGE_PART_MODES)
    refs = _normalize_string_list(data["required_output_schema_refs"], field=f"handoff_contract[{edge_id}].required_output_schema_refs", required=True)
    if schema_registry:
        for ref in refs:
            if ref not in schema_registry:
                raise ValueError(f"handoff_contract[{edge_id}] references unknown schema: {ref}")
    bindings = data["port_bindings"]
    if not isinstance(bindings, list) or not bindings:
        raise ValueError(f"handoff_contract[{edge_id}].port_bindings must be a non-empty list.")
    for item in bindings:
        binding = _ensure_dict(item, f"handoff_contract[{edge_id}].port_bindings")
        _require_fields(binding, f"handoff_contract[{edge_id}].port_bindings", ("from_port_id", "to_port_id"))
        from_port_id = _require_non_empty_string(binding["from_port_id"], field=f"handoff_contract[{edge_id}].port_bindings.from_port_id")
        to_port_id = _require_non_empty_string(binding["to_port_id"], field=f"handoff_contract[{edge_id}].port_bindings.to_port_id")
        if from_port_id not in source_ports:
            raise ValueError(f"handoff_contract[{edge_id}] references unknown source output port: {from_port_id}")
        if to_port_id not in target_ports:
            raise ValueError(f"handoff_contract[{edge_id}] references unknown target input port: {to_port_id}")


def _validate_context_policy(value: Any, *, edge_id: str) -> None:
    data = _ensure_dict(value, f"context_policy[{edge_id}]")
    _require_fields(
        data,
        f"context_policy[{edge_id}]",
        ("policy_id", "history_mode", "artifact_mode", "exclude_private_memory", "include_machine_results", "include_human_summaries"),
    )
    _require_non_empty_string(data["policy_id"], field=f"context_policy[{edge_id}].policy_id")
    _require_non_empty_string(data["history_mode"], field=f"context_policy[{edge_id}].history_mode")
    _require_non_empty_string(data["artifact_mode"], field=f"context_policy[{edge_id}].artifact_mode")
    if "summary_strategy" in data and data["summary_strategy"] is not None:
        _require_enum(data["summary_strategy"], field=f"context_policy[{edge_id}].summary_strategy", allowed=SUMMARY_STRATEGIES)
    if not bool(data["exclude_private_memory"]):
        raise ValueError(f"context_policy[{edge_id}] must set exclude_private_memory=true for worker-safe handoff.")
    _require_bool(data["include_machine_results"], field=f"context_policy[{edge_id}].include_machine_results")
    _require_bool(data["include_human_summaries"], field=f"context_policy[{edge_id}].include_human_summaries")


def _validate_ui(value: Any, *, label: str) -> None:
    data = _ensure_dict(value, label)
    _require_fields(data, label, ("position",))
    position = _ensure_dict(data["position"], f"{label}.position")
    _require_fields(position, f"{label}.position", ("x", "y"))
    for axis in ("x", "y"):
        if not isinstance(position[axis], (int, float)):
            raise ValueError(f"{label}.position.{axis} must be numeric.")
    layout_mode = data.get("layout_mode")
    if layout_mode is not None:
        _require_enum(layout_mode, field=f"{label}.layout_mode", allowed=UI_LAYOUT_MODES)


def _validate_artifact_spec(value: Any, *, node_id: str) -> None:
    data = _ensure_dict(value, f"artifact_spec[{node_id}]")
    _require_fields(data, f"artifact_spec[{node_id}]", ("kind", "id"))
    _require_enum(data["kind"], field=f"artifact_spec[{node_id}].kind", allowed=ARTIFACT_KINDS)
    _require_non_empty_string(data["id"], field=f"artifact_spec[{node_id}].id")


def _validate_edge_schema_refs(edge: dict[str, Any], *, source_schema_refs: dict[str, str]) -> None:
    expected = str(source_schema_refs.get(str(edge["from_node_id"])) or "").strip()
    if not expected:
        return
    refs = list(dict(edge["handoff_contract"]).get("required_output_schema_refs") or [])
    if expected not in refs:
        raise ValueError(f"handoff_contract[{edge['edge_id']}] must include the source node output schema ref {expected}.")


def _validate_subagent_policy(value: Any, *, node_id: str) -> None:
    data = _ensure_dict(value, f"execution[{node_id}].subagent_policy")
    _require_fields(
        data,
        f"execution[{node_id}].subagent_policy",
        ("isolation_mode", "max_turns", "allow_direct_teammate_messages", "share_worktree", "allow_nested_subagents"),
    )
    isolation_mode = _require_enum(data["isolation_mode"], field=f"execution[{node_id}].subagent_policy.isolation_mode", allowed=SUBAGENT_ISOLATION_MODES)
    if not isinstance(data["max_turns"], int) or data["max_turns"] <= 0:
        raise ValueError(f"execution[{node_id}].subagent_policy.max_turns must be a positive integer.")
    _require_bool(data["allow_direct_teammate_messages"], field=f"execution[{node_id}].subagent_policy.allow_direct_teammate_messages")
    share_worktree = _require_bool(data["share_worktree"], field=f"execution[{node_id}].subagent_policy.share_worktree")
    _require_bool(data["allow_nested_subagents"], field=f"execution[{node_id}].subagent_policy.allow_nested_subagents")
    if share_worktree and isolation_mode != "worktree":
        raise ValueError(f"execution[{node_id}].subagent_policy.share_worktree requires isolation_mode=worktree.")


def _compute_graph_depth(*, entry_node_ids: list[str], adjacency: dict[str, list[str]], node_ids: set[str]) -> int:
    visited: set[str] = set()
    stack: set[str] = set()
    memo: dict[str, int] = {}

    def visit(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]
        if node_id in stack:
            raise ValueError(f"agent_orchestration_graph contains a disallowed cycle at node {node_id}.")
        stack.add(node_id)
        children = adjacency.get(node_id, [])
        depth = 0
        for child in children:
            depth = max(depth, 1 + visit(child))
        stack.remove(node_id)
        visited.add(node_id)
        memo[node_id] = depth
        return depth

    max_depth = 0
    for entry_node_id in entry_node_ids:
        max_depth = max(max_depth, visit(entry_node_id))
    unreachable = sorted(node_ids.difference(visited))
    if unreachable:
        raise ValueError(f"agent_orchestration_graph has unreachable nodes: {', '.join(unreachable)}")
    return max_depth


def _required_refs_for_edge(edge: dict[str, Any], *, node_schema_refs: dict[str, str]) -> list[str]:
    ref = str(node_schema_refs.get(str(edge["from_node_id"])) or "").strip()
    return [ref] if ref else ["schema.migration.missing_source_output"]


def _legacy_output_ports(
    *,
    node: dict[str, Any],
    schema_ref: str,
    artifact_outputs: list[str] | None = None,
) -> list[dict[str, Any]]:
    output_contract = dict(node.get("output_contract") or {})
    ports: list[dict[str, Any]] = []
    if schema_ref:
        ports.append(
            {
                "port_id": "machine_result",
                "label": "Machine Result",
                "port_type": "structured_json",
                "shape": "single",
                "required": True,
                "schema_ref": schema_ref,
            }
        )
    resolved_artifact_outputs = (
        list(artifact_outputs)
        if artifact_outputs is not None
        else list(output_contract.get("artifact_outputs") or [])
    )
    for artifact_kind in resolved_artifact_outputs:
        ports.append(
            {
                "port_id": f"artifact_{artifact_kind}",
                "label": artifact_kind.replace("_", " ").title(),
                "port_type": _artifact_kind_to_port_type(str(artifact_kind)),
                "shape": "single",
                "required": False,
                "artifact_kind": artifact_kind,
            }
        )
    if not ports:
        ports.append({"port_id": "human_summary", "label": "Human Summary", "port_type": "text", "shape": "single", "required": True})
    return ports


def _legacy_subagent_policy(*, execution_policy: dict[str, Any]) -> dict[str, Any] | None:
    spawn_mode = str(execution_policy.get("spawn_mode") or "").strip()
    if spawn_mode != "subagent_worker":
        return None
    return {
        "isolation_mode": "lane",
        "max_turns": 8,
        "allow_direct_teammate_messages": False,
        "share_worktree": False,
        "allow_nested_subagents": False,
    }


def _legacy_port_bindings(*, edge: dict[str, Any], node_schema_refs: dict[str, str], legacy: dict[str, Any]) -> list[dict[str, Any]]:
    source_schema = str(node_schema_refs.get(str(edge["from_node_id"])) or "").strip()
    if source_schema:
        target_node = next((item for item in list(legacy.get("nodes") or []) if str(item.get("node_id") or "").strip() == str(edge["to_node_id"])), {})
        target_schema = dict(target_node.get("output_contract") or {}).get("machine_result_schema")
        target_port_id = "task_context"
        if isinstance(target_schema, dict) and target_schema:
            target_port_id = "task_context"
        return [{"from_port_id": "machine_result", "to_port_id": target_port_id}]
    return [{"from_port_id": "human_summary", "to_port_id": "task_context"}]


def _edge_midpoint(*, edge: dict[str, Any], positions: dict[str, dict[str, float]]) -> dict[str, float]:
    start = dict(positions.get(str(edge["from_node_id"])) or {"x": 0, "y": 0})
    end = dict(positions.get(str(edge["to_node_id"])) or {"x": 0, "y": 0})
    return {"x": (float(start["x"]) + float(end["x"])) / 2, "y": (float(start["y"]) + float(end["y"])) / 2}


def _risk_class_for_legacy_policy(execution_policy: dict[str, Any]) -> str:
    if bool(execution_policy.get("allow_install")):
        return "critical"
    if bool(execution_policy.get("allow_code_changes")):
        return "high"
    if bool(execution_policy.get("allow_provider_calls")):
        return "moderate"
    return "low"


def _default_role_for_kind(kind: str) -> str:
    return default_role_for_kind(kind)


def _artifact_kind_to_port_type(kind: str) -> str:
    mapping = {
        "image": "image",
        "audio": "audio",
        "video": "video",
        "document_extract": "document",
        "code_diff": "code_diff",
        "structured_json": "structured_json",
        "validation_report": "agent_report",
        "run_summary": "agent_report",
        "approval_record": "approval_record",
        "tool_result": "tool_result",
        "dataset": "dataset",
        "text_report": "text",
        "test_report": "agent_report",
    }
    return mapping.get(kind, "text")


def _normalized_legacy_artifact_outputs(
    value: Any,
    *,
    node_id: str,
    has_machine_schema: bool,
    warnings: list[str],
) -> list[str]:
    legacy_aliases = {
        "smoke_matrix": "validation_report",
    }
    outputs: list[str] = []
    for item in list(value or []):
        artifact_kind = str(item or "").strip()
        if artifact_kind == "required_output":
            artifact_kind = "structured_json" if has_machine_schema else "text_report"
            warnings.append(
                f"node:{node_id}: normalized legacy required_output artifact to {artifact_kind}"
            )
        elif artifact_kind in legacy_aliases:
            normalized_kind = legacy_aliases[artifact_kind]
            warnings.append(
                f"node:{node_id}: normalized legacy {artifact_kind} artifact to {normalized_kind}"
            )
            artifact_kind = normalized_kind
        if artifact_kind and artifact_kind not in outputs:
            outputs.append(artifact_kind)
    return outputs


def _ensure_registry(value: Any, *, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    data = _ensure_dict(value, label)
    for key in data:
        _require_non_empty_string(key, field=label)
    return data


def _ensure_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a dict.")
    return value


def _require_fields(data: dict[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if field not in data:
            raise ValueError(f"{label} is missing required field: {field}")


def _require_non_empty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string.")
    text = value.strip()
    if not text:
        raise ValueError(f"{field} must not be empty.")
    return text


def _require_enum(value: Any, *, field: str, allowed: tuple[str, ...]) -> str:
    text = _require_non_empty_string(value, field=field)
    if text not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(allowed)}")
    return text


def _require_bool(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a bool.")
    return value


def _normalize_string_list(value: Any, *, field: str, required: bool = False) -> list[str]:
    if value is None:
        if required:
            raise ValueError(f"{field} is required.")
        return []
    items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _require_non_empty_string(item, field=field)
        if text not in seen:
            normalized.append(text)
            seen.add(text)
    return normalized


def _normalize_enum_list(value: Any, *, field: str, allowed: tuple[str, ...]) -> set[str]:
    items = _normalize_string_list(value, field=field, required=False)
    normalized: set[str] = set()
    for item in items:
        normalized.add(_require_enum(item, field=field, allowed=allowed))
    return normalized


def _reject_secret_like(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_secret_like(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_like(child, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if DESKTOP_KEY_PATH_RE.search(value) or SECRET_RE.search(value):
        raise SecurityError(f"Secret-like content detected in {path}")
