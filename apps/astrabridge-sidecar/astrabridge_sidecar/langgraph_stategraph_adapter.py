from __future__ import annotations

import importlib.util
import json
import re
from copy import deepcopy
from typing import Any

from .agent_orchestration_contract import (
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    validate_agent_orchestration_graph,
)
from .common import now_iso
from .node_type_registry import resolve_node_type
from .protocol import validate_protocol_payload


LANGGRAPH_STATEGRAPH_ADAPTER_SCHEMA_VERSION = "astrabridge-langgraph-stategraph-adapter-v1"
LANGGRAPH_STATEGRAPH_SOURCE_FORMAT = "langgraph_stategraph_manifest"
LANGGRAPH_STATEGRAPH_EXTENSION_NAMESPACE = "astrabridge"
LANGGRAPH_STATEGRAPH_SUPPORTED_VERSIONS = ("1.0",)
LANGGRAPH_STATEGRAPH_DEFAULT_VERSION = "1.0"
LANGGRAPH_STATEGRAPH_START_NODE = "__start__"
LANGGRAPH_STATEGRAPH_END_NODE = "__end__"
LANGGRAPH_SUPPORTED_NODE_TYPES: dict[str, dict[str, Any]] = {
    "astrabridge/agent": {
        "type_id": "agent_model",
        "default_role": "worker",
        "title": "AstraBridge Agent",
    },
    "astrabridge/mcp_tool": {
        "type_id": "mcp_tool",
        "default_role": "custom",
        "title": "AstraBridge MCP Tool",
    },
    "astrabridge/mcp_resource": {
        "type_id": "mcp_resource",
        "default_role": "custom",
        "title": "AstraBridge MCP Resource",
    },
    "astrabridge/transform": {
        "type_id": "transform",
        "default_role": "custom",
        "title": "AstraBridge Transform",
    },
    "astrabridge/router_condition": {
        "type_id": "router_condition",
        "default_role": "custom",
        "title": "AstraBridge Router / Condition",
    },
    "astrabridge/subgraph": {
        "type_id": "subgraph",
        "default_role": "custom",
        "title": "AstraBridge Subgraph",
    },
    "astrabridge/human_approval": {
        "type_id": "human_approval",
        "default_role": "gate",
        "title": "AstraBridge Human Approval",
    },
    "astrabridge/artifact_source": {
        "type_id": "artifact_source",
        "default_role": "custom",
        "title": "AstraBridge Artifact Source",
    },
    "astrabridge/artifact_sink": {
        "type_id": "artifact_sink",
        "default_role": "custom",
        "title": "AstraBridge Artifact Sink",
    },
}
TYPE_ID_TO_LANGGRAPH_NODE_TYPE = {
    data["type_id"]: langgraph_type
    for langgraph_type, data in LANGGRAPH_SUPPORTED_NODE_TYPES.items()
}
LANGGRAPH_SUPPORTED_EDGE_KINDS = {"start", "edge", "conditional"}
LANGGRAPH_SUPPORTED_CHECKPOINTER_MODES = {"disabled", "memory", "inherit_parent"}
LANGGRAPH_SUPPORTED_REDUCERS = {"replace", "list_append"}
LANGGRAPH_GENERATED_PYTHON_EXECUTABLE_NODE_TYPES = {
    "astrabridge/artifact_source",
    "astrabridge/artifact_sink",
    "astrabridge/router_condition",
}
LANGGRAPH_GENERATED_PYTHON_EXECUTABLE_ROUTE_MODES = {"state_field_literal"}

CANONICAL_PORT_TYPES = {
    "text",
    "structured_json",
    "image",
    "audio",
    "video",
    "document",
    "code_diff",
    "dataset",
    "tool_result",
    "agent_report",
    "approval_record",
}
PORT_TYPE_ALIASES = {
    "string": "text",
    "text": "text",
    "json": "structured_json",
    "structured_json": "structured_json",
    "image": "image",
    "audio": "audio",
    "video": "video",
    "document": "document",
    "dataset": "dataset",
    "code_diff": "code_diff",
    "tool_result": "tool_result",
    "approval_record": "approval_record",
    "agent_report": "agent_report",
}
SAFE_IDENTIFIER_PATTERN = re.compile(r"[^A-Za-z0-9._:-]+")


class LangGraphStateGraphAdapterError(ValueError):
    pass


class LangGraphStateGraphLossError(LangGraphStateGraphAdapterError):
    def __init__(
        self,
        message: str,
        *,
        source_version: str | None,
        loss_report: dict[str, Any],
        adapter_manifest: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.public_payload = {
            "source_format": LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
            "source_version": source_version,
            "loss_report": loss_report,
            "adapter_manifest": adapter_manifest,
        }


def langgraph_optional_dependency_status() -> dict[str, Any]:
    return {
        "langgraph_installed": importlib.util.find_spec("langgraph") is not None,
        "langchain_installed": importlib.util.find_spec("langchain") is not None,
    }


def langgraph_stategraph_adapter_manifest() -> dict[str, Any]:
    return {
        "schema_version": LANGGRAPH_STATEGRAPH_ADAPTER_SCHEMA_VERSION,
        "adapter_id": "langgraph_stategraph",
        "source_format": LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
        "supported_versions": list(LANGGRAPH_STATEGRAPH_SUPPORTED_VERSIONS),
        "default_version": LANGGRAPH_STATEGRAPH_DEFAULT_VERSION,
        "extension_namespace": LANGGRAPH_STATEGRAPH_EXTENSION_NAMESPACE,
        "node_type_map": {
            langgraph_type: {
                "type_id": data["type_id"],
                "default_role": data["default_role"],
            }
            for langgraph_type, data in LANGGRAPH_SUPPORTED_NODE_TYPES.items()
        },
        "supported_edge_kinds": sorted(LANGGRAPH_SUPPORTED_EDGE_KINDS),
        "supported_checkpointer_modes": sorted(LANGGRAPH_SUPPORTED_CHECKPOINTER_MODES),
        "optional_dependencies": langgraph_optional_dependency_status(),
    }


def serialize_langgraph_stategraph_manifest(manifest: dict[str, Any]) -> str:
    if not isinstance(manifest, dict):
        raise TypeError("LangGraph StateGraph manifest must be a dict.")
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def looks_like_langgraph_stategraph_manifest(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    graph = payload.get("graph")
    return (
        str(payload.get("format") or "").strip() == LANGGRAPH_STATEGRAPH_SOURCE_FORMAT
        and isinstance(graph, dict)
        and isinstance(graph.get("nodes"), list)
        and isinstance(graph.get("edges"), list)
    )


def parse_langgraph_stategraph_manifest_text(
    text: str,
    *,
    source_name: str = "<memory>",
) -> dict[str, Any]:
    if not isinstance(text, str):
        raise TypeError("LangGraph StateGraph manifest text must be a string.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LangGraphStateGraphAdapterError(
            f"{source_name} is not valid JSON: {exc.msg}",
        ) from exc
    if not looks_like_langgraph_stategraph_manifest(payload):
        raise LangGraphStateGraphAdapterError(
            f"{source_name} is not a supported LangGraph StateGraph manifest payload.",
        )
    return deepcopy(payload)


def import_langgraph_stategraph_manifest(
    manifest: dict[str, Any],
    *,
    graph_id: str | None = None,
    task_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    adapter_manifest = langgraph_stategraph_adapter_manifest()
    normalized = parse_langgraph_stategraph_manifest_text(
        serialize_langgraph_stategraph_manifest(manifest),
        source_name="langgraph-stategraph-manifest",
    )
    source_version = _clean_text(normalized.get("version")) or LANGGRAPH_STATEGRAPH_DEFAULT_VERSION
    issues: list[dict[str, Any]] = []
    if source_version not in LANGGRAPH_STATEGRAPH_SUPPORTED_VERSIONS:
        issues.append(
            {
                "code": "unsupported_manifest_version",
                "severity": "blocked",
                "path": "version",
                "message": (
                    f"LangGraph manifest version `{source_version}` is not supported. "
                    f"Supported versions: {', '.join(LANGGRAPH_STATEGRAPH_SUPPORTED_VERSIONS)}."
                ),
                "action": "block_import",
            }
        )

    raw_graph = _as_dict(normalized.get("graph")) or {}
    raw_nodes = [deepcopy(item) for item in list(raw_graph.get("nodes") or []) if isinstance(item, dict)]
    raw_edges = [deepcopy(item) for item in list(raw_graph.get("edges") or []) if isinstance(item, dict)]
    raw_extensions = _as_dict(raw_graph.get("extensions")) or {}
    adapter_extensions = _as_dict(raw_extensions.get(LANGGRAPH_STATEGRAPH_EXTENSION_NAMESPACE)) or {}
    state_channels = _as_dict(raw_graph.get("state_channels")) or {}
    compile_config = _as_dict(raw_graph.get("compile")) or {}

    _validate_compile_config(compile_config, issues=issues)

    node_ids = {_clean_identifier(item.get("id")) for item in raw_nodes if _clean_identifier(item.get("id"))}
    supported_nodes: list[dict[str, Any]] = []
    for raw_node in raw_nodes:
        langgraph_type = _clean_text(raw_node.get("type"))
        node_id = _clean_identifier(raw_node.get("id"))
        if not node_id:
            issues.append(
                {
                    "code": "missing_node_id",
                    "severity": "blocked",
                    "path": "graph.nodes[].id",
                    "message": "A LangGraph manifest node is missing a stable `id`.",
                    "action": "block_import",
                }
            )
            continue
        if langgraph_type not in LANGGRAPH_SUPPORTED_NODE_TYPES:
            issues.append(
                {
                    "code": "unsupported_node_type",
                    "severity": "blocked",
                    "node_id": node_id,
                    "node_type": langgraph_type,
                    "message": f"Unsupported LangGraph node type `{langgraph_type}`.",
                    "action": "block_import",
                }
            )
            continue
        supported_nodes.append(raw_node)

    workflow_graph_id = _clean_identifier(graph_id) or _clean_identifier(raw_graph.get("graph_id")) or "graph_langgraph_stategraph"
    workflow_task_id = _clean_identifier(task_id) or _clean_identifier(raw_graph.get("task_id")) or "task_example"
    workflow_title = _clean_text(title) or _clean_text(raw_graph.get("title")) or "Imported LangGraph StateGraph"
    schema_registry = deepcopy(_as_dict(raw_graph.get("schema_registry")) or {})

    canonical_nodes: list[dict[str, Any]] = []
    node_overlays: dict[str, dict[str, Any]] = {}
    canonical_nodes_by_id: dict[str, dict[str, Any]] = {}
    for raw_node in supported_nodes:
        canonical = _import_supported_node(
            raw_node,
            workflow_graph_id=workflow_graph_id,
            schema_registry=schema_registry,
        )
        canonical_nodes.append(canonical["node"])
        node_overlays[canonical["node"]["node_id"]] = canonical["task_graph_overlay"]
        canonical_nodes_by_id[canonical["node"]["node_id"]] = canonical["node"]
        artifact_uri = _clean_text(canonical["task_graph_overlay"].get("node_type_config", {}).get("artifact_uri"))
        if artifact_uri:
            try:
                _validate_workspace_artifact_uri(artifact_uri, node_id=canonical["node"]["node_id"])
            except Exception as exc:  # noqa: BLE001
                issues.append(
                    {
                        "code": "unsafe_artifact_uri",
                        "severity": "blocked",
                        "node_id": canonical["node"]["node_id"],
                        "message": str(exc),
                        "action": "block_import",
                    }
                )

    entry_node_ids: list[str] = []
    start_edges: list[dict[str, Any]] = []
    end_edges: list[dict[str, Any]] = []
    canonical_edges: list[dict[str, Any]] = []
    for raw_edge in raw_edges:
        edge_id = _clean_identifier(raw_edge.get("id")) or f"edge_{len(raw_edges)}"
        edge_kind = _clean_text(raw_edge.get("kind")) or "edge"
        source = _clean_identifier(raw_edge.get("source"))
        target = _clean_identifier(raw_edge.get("target"))
        if edge_kind not in LANGGRAPH_SUPPORTED_EDGE_KINDS:
            issues.append(
                {
                    "code": "unsupported_edge_kind",
                    "severity": "blocked",
                    "edge_id": edge_id,
                    "message": f"Unsupported LangGraph edge kind `{edge_kind}`.",
                    "action": "block_import",
                }
            )
            continue
        if source == LANGGRAPH_STATEGRAPH_START_NODE:
            if edge_kind != "start":
                issues.append(
                    {
                        "code": "unsupported_start_edge_kind",
                        "severity": "blocked",
                        "edge_id": edge_id,
                        "message": "Only static start edges are supported from `__start__`.",
                        "action": "block_import",
                    }
                )
                continue
            if target not in canonical_nodes_by_id:
                issues.append(
                    {
                        "code": "unknown_start_target",
                        "severity": "blocked",
                        "edge_id": edge_id,
                        "message": f"Start edge `{edge_id}` references unknown target `{target}`.",
                        "action": "block_import",
                    }
                )
                continue
            start_edges.append(deepcopy(raw_edge))
            if target not in entry_node_ids:
                entry_node_ids.append(target)
            continue
        if target == LANGGRAPH_STATEGRAPH_END_NODE:
            end_edges.append(deepcopy(raw_edge))
            continue
        if source not in canonical_nodes_by_id or target not in canonical_nodes_by_id:
            issues.append(
                {
                    "code": "unknown_edge_endpoint",
                    "severity": "blocked",
                    "edge_id": edge_id,
                    "message": f"Edge `{edge_id}` references unknown source/target nodes.",
                    "action": "block_import",
                }
            )
            continue
        canonical_edges.append(
            _import_supported_edge(
                raw_edge,
                source_node=canonical_nodes_by_id[source],
                target_node=canonical_nodes_by_id[target],
            )
        )

    if not entry_node_ids and canonical_nodes:
        inbound_node_ids = {
            str(edge.get("to_node_id") or "").strip()
            for edge in canonical_edges
            if str(edge.get("to_node_id") or "").strip()
        }
        entry_node_ids = [
            str(node.get("node_id") or "").strip()
            for node in canonical_nodes
            if str(node.get("node_id") or "").strip() and str(node.get("node_id") or "").strip() not in inbound_node_ids
        ]
    if not entry_node_ids and canonical_nodes:
        entry_node_ids = [str(canonical_nodes[0].get("node_id") or "").strip()]

    loss_report = _build_loss_report(
        source_version=source_version,
        issues=issues,
        preserved_extensions={
            "start_edge_count": len(start_edges),
            "end_edge_count": len(end_edges),
            "state_channel_count": len(state_channels),
        },
    )
    if loss_report["status"] == "blocked":
        raise LangGraphStateGraphLossError(
            "LangGraph StateGraph import is blocked by unsupported or unsafe constructs.",
            source_version=source_version,
            loss_report=loss_report,
            adapter_manifest=adapter_manifest,
        )

    metadata = dict(raw_graph.get("metadata") or {})
    metadata.setdefault("created_at", now_iso())
    metadata["updated_at"] = now_iso()
    metadata.setdefault("description", "Imported from a supported LangGraph StateGraph manifest subset.")
    metadata.setdefault("tags", ["langgraph", "stategraph", "adapter"])
    metadata.setdefault("owners", [])
    metadata["adapter_manifest"] = adapter_manifest
    compile_config.setdefault("checkpointer", {"mode": "disabled"})
    compile_config.setdefault("interrupt_before", [])
    compile_config.setdefault("interrupt_after", [])
    migration = {
        "source_kind": "imported_file",
        "compiled_task_graph_version": "astrabridge-task-graph-v1",
        "adapter": {
            "adapter_id": "langgraph_stategraph",
            "schema_version": LANGGRAPH_STATEGRAPH_ADAPTER_SCHEMA_VERSION,
            "source_format": LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
            "source_version": source_version,
            "extension_namespace": LANGGRAPH_STATEGRAPH_EXTENSION_NAMESPACE,
            "graph_id": workflow_graph_id,
            "compile_config": deepcopy(compile_config),
            "state_channels": deepcopy(state_channels),
            "thread_lineage": {
                "thread_id_field": str(dict(compile_config.get("checkpointer") or {}).get("thread_id_field") or "thread_id"),
                "checkpoint_ns_field": str(dict(compile_config.get("checkpointer") or {}).get("checkpoint_ns_field") or "checkpoint_ns"),
                "checkpoint_id_field": str(dict(compile_config.get("checkpointer") or {}).get("checkpoint_id_field") or "checkpoint_id"),
                "astrabridge_task_id": workflow_task_id,
                "astrabridge_run_id_source": "durable_run.run_id",
            },
        },
        "warnings": [
            str(item.get("message") or "").strip()
            for item in issues
            if str(item.get("severity") or "").strip() == "warning"
        ],
        "adapter_extensions": {
            LANGGRAPH_STATEGRAPH_EXTENSION_NAMESPACE: {
                "start_edges": start_edges,
                "end_edges": end_edges,
                "extensions": raw_extensions,
                "state_channels": deepcopy(state_channels),
                "compile": deepcopy(compile_config),
                "graph_metadata": {
                    "graph_id": _clean_text(raw_graph.get("graph_id")),
                    "task_id": _clean_text(raw_graph.get("task_id")),
                    "title": _clean_text(raw_graph.get("title")),
                },
                "node_ids": sorted(node_ids),
                "adapter_extensions": deepcopy(adapter_extensions),
            }
        },
    }
    graph_policy = dict(raw_graph.get("graph_policy") or {})
    graph_policy.setdefault("entry_node_ids", entry_node_ids)
    graph_policy.setdefault("max_depth", max(2, len(canonical_nodes)))
    graph_policy.setdefault("default_permission_mode", "ask")
    graph_policy.setdefault("default_collaboration_mode", "default")
    graph_policy.setdefault("default_execution_backend", "app_server")
    graph_policy.setdefault("requires_dry_run_before_live", True)

    canonical_graph = validate_agent_orchestration_graph(
        {
            "schema_version": AGENT_ORCHESTRATION_SCHEMA_VERSION,
            "graph_id": workflow_graph_id,
            "task_id": workflow_task_id,
            "title": workflow_title,
            "template_id": _clean_text(raw_graph.get("template_id")) or "custom_blank_graph",
            "status": _clean_text(raw_graph.get("status")) or "ready",
            "metadata": metadata,
            "graph_policy": graph_policy,
            "nodes": canonical_nodes,
            "edges": canonical_edges,
            "schema_registry": schema_registry,
            "migration": migration,
            "state_version": int(raw_graph.get("state_version") or 1),
        }
    )
    return {
        "schema_version": LANGGRAPH_STATEGRAPH_ADAPTER_SCHEMA_VERSION,
        "source_format": LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
        "source_version": source_version,
        "adapter_manifest": adapter_manifest,
        "loss_report": loss_report,
        "orchestration_graph": canonical_graph,
        "task_graph_overlays": node_overlays,
    }


def export_langgraph_stategraph_manifest(
    orchestration_graph: dict[str, Any],
    *,
    task_graph: dict[str, Any] | None = None,
    emit_generated_python: bool = True,
) -> dict[str, Any]:
    adapter_manifest = langgraph_stategraph_adapter_manifest()
    canonical = validate_agent_orchestration_graph(orchestration_graph)
    issues: list[dict[str, Any]] = []
    task_nodes = {
        str(item.get("node_id") or "").strip(): dict(item)
        for item in list((task_graph or {}).get("nodes") or [])
        if isinstance(item, dict) and str(item.get("node_id") or "").strip()
    }
    adapter_extension_root = _as_dict(
        dict(dict(canonical.get("migration") or {}).get("adapter_extensions") or {}).get(LANGGRAPH_STATEGRAPH_EXTENSION_NAMESPACE)
    ) or {}
    compile_config = deepcopy(_as_dict(dict(dict(canonical.get("migration") or {}).get("adapter") or {}).get("compile_config")) or _as_dict(adapter_extension_root.get("compile")) or {})
    state_channels = deepcopy(_as_dict(dict(dict(canonical.get("migration") or {}).get("adapter") or {}).get("state_channels")) or _as_dict(adapter_extension_root.get("state_channels")) or {})
    start_edges = [deepcopy(item) for item in list(adapter_extension_root.get("start_edges") or []) if isinstance(item, dict)]
    end_edges = [deepcopy(item) for item in list(adapter_extension_root.get("end_edges") or []) if isinstance(item, dict)]
    raw_extensions = deepcopy(_as_dict(adapter_extension_root.get("extensions")) or {})
    adapter_extensions = deepcopy(_as_dict(adapter_extension_root.get("adapter_extensions")) or {})
    graph_metadata = deepcopy(_as_dict(adapter_extension_root.get("graph_metadata")) or {})

    manifest_nodes: list[dict[str, Any]] = []
    for node in list(canonical.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        resolved = resolve_node_type(str(node.get("kind") or ""), allow_unknown=True)
        resolved_type_id = str(node.get("resolved_node_type_id") or resolved.get("resolved_type_id") or "").strip()
        langgraph_type = TYPE_ID_TO_LANGGRAPH_NODE_TYPE.get(resolved_type_id)
        if not langgraph_type:
            issues.append(
                {
                    "code": "unsupported_export_node_type",
                    "severity": "blocked",
                    "node_id": str(node.get("node_id") or ""),
                    "node_type_id": resolved_type_id or str(node.get("kind") or ""),
                    "message": (
                        f"Node `{str(node.get('node_id') or '')}` uses unsupported type "
                        f"`{resolved_type_id or str(node.get('kind') or '')}` for LangGraph export."
                    ),
                    "action": "block_export",
                }
            )
            continue
        manifest_nodes.append(
            _export_supported_node(
                node,
                langgraph_type=langgraph_type,
                task_node=task_nodes.get(str(node.get("node_id") or "").strip()),
            )
        )

    manifest_edges: list[dict[str, Any]] = []
    for node_id in list(dict(canonical.get("graph_policy") or {}).get("entry_node_ids") or []):
        clean_node_id = _clean_identifier(node_id)
        if clean_node_id:
            manifest_edges.append(
                {
                    "id": f"start_{clean_node_id}",
                    "kind": "start",
                    "source": LANGGRAPH_STATEGRAPH_START_NODE,
                    "target": clean_node_id,
                }
            )
    for edge in start_edges:
        target = _clean_identifier(edge.get("target"))
        if target and not any(
            _clean_identifier(item.get("target")) == target and _clean_text(item.get("kind")) == "start"
            for item in manifest_edges
        ):
            manifest_edges.append(deepcopy(edge))

    conditional_groups: dict[str, list[dict[str, Any]]] = {}
    for edge in list(canonical.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        from_node_id = _clean_identifier(edge.get("from_node_id"))
        to_node_id = _clean_identifier(edge.get("to_node_id"))
        if not from_node_id or not to_node_id:
            issues.append(
                {
                    "code": "invalid_export_edge",
                    "severity": "blocked",
                    "edge_id": str(edge.get("edge_id") or ""),
                    "message": "A LangGraph export edge is missing a source or target node identifier.",
                    "action": "block_export",
                }
            )
            continue
        langgraph_meta = _as_dict(edge.get("langgraph")) or {}
        edge_kind = _clean_text(langgraph_meta.get("kind")) or "edge"
        if edge_kind == "conditional":
            branch = _clean_text(langgraph_meta.get("branch"))
            if not branch:
                issues.append(
                    {
                        "code": "missing_conditional_branch",
                        "severity": "blocked",
                        "edge_id": str(edge.get("edge_id") or ""),
                        "message": "Conditional LangGraph export edges must preserve a non-empty `branch` label.",
                        "action": "block_export",
                    }
                )
                continue
        manifest_edge = _export_supported_edge(edge)
        manifest_edge["kind"] = edge_kind
        conditional_groups.setdefault(from_node_id, []).append(manifest_edge) if edge_kind == "conditional" else manifest_edges.append(manifest_edge)

    for group in conditional_groups.values():
        manifest_edges.extend(group)
    manifest_edges.extend(end_edges)

    if not state_channels:
        state_channels = _infer_state_channels(canonical)
    compile_config = _normalize_compile_config_for_export(compile_config)

    loss_report = _build_loss_report(
        source_version=LANGGRAPH_STATEGRAPH_DEFAULT_VERSION,
        issues=issues,
        preserved_extensions={
            "start_edge_count": len(start_edges),
            "end_edge_count": len(end_edges),
            "state_channel_count": len(state_channels),
        },
    )
    if loss_report["status"] == "blocked":
        raise LangGraphStateGraphLossError(
            "LangGraph StateGraph export is blocked by unsupported node or edge constructs.",
            source_version=LANGGRAPH_STATEGRAPH_DEFAULT_VERSION,
            loss_report=loss_report,
            adapter_manifest=adapter_manifest,
        )

    manifest = {
        "format": LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
        "version": LANGGRAPH_STATEGRAPH_DEFAULT_VERSION,
        "graph": {
            "graph_id": _clean_text(graph_metadata.get("graph_id")) or str(canonical.get("graph_id") or ""),
            "task_id": _clean_text(graph_metadata.get("task_id")) or str(canonical.get("task_id") or ""),
            "title": _clean_text(graph_metadata.get("title")) or str(canonical.get("title") or ""),
            "template_id": canonical.get("template_id"),
            "status": canonical.get("status"),
            "metadata": {
                "description": str(dict(canonical.get("metadata") or {}).get("description") or ""),
                "tags": list(dict(canonical.get("metadata") or {}).get("tags") or []),
                "owners": list(dict(canonical.get("metadata") or {}).get("owners") or []),
                "created_at": dict(canonical.get("metadata") or {}).get("created_at"),
                "updated_at": dict(canonical.get("metadata") or {}).get("updated_at"),
            },
            "state_channels": state_channels,
            "compile": compile_config,
            "nodes": manifest_nodes,
            "edges": manifest_edges,
            "schema_registry": deepcopy(dict(canonical.get("schema_registry") or {})),
            "graph_policy": deepcopy(dict(canonical.get("graph_policy") or {})),
            "state_version": int(canonical.get("state_version") or 1),
            "extensions": {
                **raw_extensions,
                LANGGRAPH_STATEGRAPH_EXTENSION_NAMESPACE: {
                    "adapter_manifest": adapter_manifest,
                    "graph_id": str(canonical.get("graph_id") or ""),
                    "task_id": str(canonical.get("task_id") or ""),
                    "adapter_extensions": deepcopy(adapter_extensions),
                    "thread_lineage": deepcopy(dict(dict(canonical.get("migration") or {}).get("adapter") or {}).get("thread_lineage") or {}),
                },
            },
        },
    }
    generated_python = generate_langgraph_stategraph_python(manifest) if emit_generated_python else None
    return {
        "schema_version": LANGGRAPH_STATEGRAPH_ADAPTER_SCHEMA_VERSION,
        "export_format": LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
        "source_version": LANGGRAPH_STATEGRAPH_DEFAULT_VERSION,
        "adapter_manifest": adapter_manifest,
        "loss_report": loss_report,
        "manifest": manifest,
        "serialized_text": serialize_langgraph_stategraph_manifest(manifest),
        "generated_python": generated_python,
    }


def generate_langgraph_stategraph_python(
    manifest: dict[str, Any],
    *,
    module_name: str | None = None,
) -> str:
    parsed = parse_langgraph_stategraph_manifest_text(
        serialize_langgraph_stategraph_manifest(manifest),
        source_name="langgraph-stategraph-manifest",
    )
    graph = _as_dict(parsed.get("graph")) or {}
    adapter_manifest = langgraph_stategraph_adapter_manifest()
    source_version = _clean_text(parsed.get("version")) or LANGGRAPH_STATEGRAPH_DEFAULT_VERSION
    generated_python_issues = _collect_generated_python_support_issues(parsed)
    generated_python_loss_report = _build_loss_report(
        source_version=source_version,
        issues=generated_python_issues,
        preserved_extensions={"generated_python": {"requested": True}},
    )
    if generated_python_loss_report["status"] == "blocked":
        raise LangGraphStateGraphLossError(
            "LangGraph generated Python export is blocked because the manifest requires runtime bindings or node families outside the executable subset.",
            source_version=source_version,
            loss_report=generated_python_loss_report,
            adapter_manifest=adapter_manifest,
        )
    clean_module_name = _clean_identifier(module_name) or f"generated_{_clean_identifier(graph.get('graph_id')) or 'langgraph_stategraph'}"
    state_channels = _as_dict(graph.get("state_channels")) or {}
    compile_config = _as_dict(graph.get("compile")) or {}
    checkpointer_config = _as_dict(compile_config.get("checkpointer")) or {}
    nodes = [dict(item) for item in list(graph.get("nodes") or []) if isinstance(item, dict)]
    edges = [dict(item) for item in list(graph.get("edges") or []) if isinstance(item, dict)]

    lines: list[str] = [
        '"""Generated from an AstraBridge LangGraph StateGraph manifest."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "try:",
        "    from typing_extensions import TypedDict",
        "except ImportError:  # pragma: no cover",
        "    from typing import TypedDict  # type: ignore[assignment]",
        "",
        "from langgraph.graph import END, START, StateGraph",
        "try:",
        "    from langgraph.checkpoint.memory import InMemorySaver",
        "except Exception:  # pragma: no cover",
        "    InMemorySaver = None",
        "",
        f"MODULE_NAME = {json.dumps(clean_module_name)}",
        f"GRAPH_ID = {json.dumps(str(graph.get('graph_id') or ''))}",
        f"TASK_ID = {json.dumps(str(graph.get('task_id') or ''))}",
        "",
        "class State(TypedDict, total=False):",
    ]
    if state_channels:
        for key, channel in state_channels.items():
            clean_key = _clean_identifier(key)
            if not clean_key:
                continue
            lines.append(f"    {clean_key}: {_render_python_type(channel)}")
    else:
        lines.append("    data: dict[str, Any]")
    lines.extend(
        [
            "",
            "def build_langgraph_config(*, thread_id: str, checkpoint_ns: str | None = None, checkpoint_id: str | None = None, astrabridge_run_id: str | None = None) -> dict[str, Any]:",
            "    configurable = {",
            f"        {json.dumps(str(checkpointer_config.get('thread_id_field') or 'thread_id'))}: thread_id,",
            "    }",
            f"    checkpoint_ns_field = {json.dumps(str(checkpointer_config.get('checkpoint_ns_field') or 'checkpoint_ns'))}",
            f"    checkpoint_id_field = {json.dumps(str(checkpointer_config.get('checkpoint_id_field') or 'checkpoint_id'))}",
            "    if checkpoint_ns is not None:",
            "        configurable[checkpoint_ns_field] = checkpoint_ns",
            "    if checkpoint_id is not None:",
            "        configurable[checkpoint_id_field] = checkpoint_id",
            "    if astrabridge_run_id is not None:",
            '        configurable["astrabridge_run_id"] = astrabridge_run_id',
            "    return {\"configurable\": configurable}",
            "",
        ]
    )

    for node in nodes:
        node_id = _clean_identifier(node.get("id"))
        node_type = _clean_text(node.get("type"))
        node_type_config = _as_dict(node.get("node_type_config")) or {}
        fn_name = _render_node_fn_name(node_id)
        if node_type == "astrabridge/router_condition":
            route_name = _render_route_fn_name(node_id)
            lines.extend(
                [
                    f"def {fn_name}(state: State) -> dict[str, Any]:",
                    "    return {}",
                    "",
                    f"def {route_name}(state: State):",
                    f"    condition = {json.dumps(node_type_config.get('condition') or {}, ensure_ascii=False, sort_keys=True)}",
                    "    mode = str(condition.get(\"mode\") or \"state_field_literal\").strip() or \"state_field_literal\"",
                    "    if mode != \"state_field_literal\":",
                    "        raise ValueError(f\"Unsupported generated router condition mode: {mode}\")",
                    "    field = str(condition.get(\"field\") or \"route\").strip() or \"route\"",
                    "    branch_map = dict(condition.get(\"branch_map\") or {})",
                    "    value = state.get(field)",
                    "    if isinstance(value, list):",
                    "        return [branch_map.get(item, item) for item in value]",
                    "    return branch_map.get(value, value)",
                    "",
                ]
            )
            continue
        lines.extend(
            [
                f"def {fn_name}(state: State) -> dict[str, Any]:",
                "    return {}",
                "",
            ]
        )

    lines.extend(
        [
            "def build_graph(*, checkpointer: Any | None = None):",
            "    builder = StateGraph(State)",
        ]
    )
    for node in nodes:
        node_id = _clean_identifier(node.get("id"))
        fn_name = _render_node_fn_name(node_id)
        lines.append(f"    builder.add_node({json.dumps(node_id)}, {fn_name})")
    lines.append("")

    conditional_edges_by_source: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        edge_kind = _clean_text(edge.get("kind")) or "edge"
        source = _clean_identifier(edge.get("source"))
        target = _clean_identifier(edge.get("target"))
        if source == LANGGRAPH_STATEGRAPH_START_NODE and edge_kind == "start":
            lines.append(f"    builder.add_edge(START, {json.dumps(target)})")
            continue
        if edge_kind == "conditional":
            conditional_edges_by_source.setdefault(source, []).append(edge)
            continue
        if target == LANGGRAPH_STATEGRAPH_END_NODE:
            lines.append(f"    builder.add_edge({json.dumps(source)}, END)")
            continue
        lines.append(f"    builder.add_edge({json.dumps(source)}, {json.dumps(target)})")
    if edges:
        lines.append("")
    for source, group in conditional_edges_by_source.items():
        route_name = _render_route_fn_name(source)
        branch_map: dict[str, Any] = {}
        for edge in group:
            branch = _clean_text(edge.get("branch"))
            target = _clean_identifier(edge.get("target"))
            branch_map[branch] = "END" if target == LANGGRAPH_STATEGRAPH_END_NODE else target
        python_branch_map = "{\n" + "\n".join(
            [
                f"        {json.dumps(branch)}: {'END' if target == 'END' else json.dumps(target)},"
                for branch, target in branch_map.items()
            ]
        ) + "\n    }"
        lines.extend(
            [
                f"    builder.add_conditional_edges({json.dumps(source)}, {route_name}, {python_branch_map})",
            ]
        )
    if conditional_edges_by_source:
        lines.append("")

    lines.extend(
        [
            "    compile_kwargs: dict[str, Any] = {}",
            f"    checkpointer_mode = {json.dumps(str(checkpointer_config.get('mode') or 'disabled'))}",
            "    if checkpointer_mode == \"memory\" and checkpointer is None and InMemorySaver is not None:",
            "        checkpointer = InMemorySaver()",
            "    if checkpointer is not None:",
            '        compile_kwargs["checkpointer"] = checkpointer',
        ]
    )
    interrupt_before = [str(item).strip() for item in list(compile_config.get("interrupt_before") or []) if str(item).strip()]
    interrupt_after = [str(item).strip() for item in list(compile_config.get("interrupt_after") or []) if str(item).strip()]
    if interrupt_before:
        lines.append(f'    compile_kwargs["interrupt_before"] = {json.dumps(interrupt_before, ensure_ascii=False)}')
    if interrupt_after:
        lines.append(f'    compile_kwargs["interrupt_after"] = {json.dumps(interrupt_after, ensure_ascii=False)}')
    lines.extend(
        [
            "    return builder.compile(**compile_kwargs)",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _validate_compile_config(value: dict[str, Any], *, issues: list[dict[str, Any]]) -> None:
    checkpointer = _as_dict(value.get("checkpointer")) or {}
    mode = _clean_text(checkpointer.get("mode")) or "disabled"
    if mode not in LANGGRAPH_SUPPORTED_CHECKPOINTER_MODES:
        issues.append(
            {
                "code": "unsupported_checkpointer_mode",
                "severity": "blocked",
                "path": "graph.compile.checkpointer.mode",
                "message": f"Unsupported LangGraph checkpointer mode `{mode}`.",
                "action": "block_import",
            }
        )
    for key in ("interrupt_before", "interrupt_after"):
        raw_values = value.get(key)
        if raw_values is None:
            continue
        if not isinstance(raw_values, list) or any(not _clean_identifier(item) for item in raw_values):
            issues.append(
                {
                    "code": "invalid_interrupt_config",
                    "severity": "blocked",
                    "path": f"graph.compile.{key}",
                    "message": f"`graph.compile.{key}` must be a list of node ids.",
                    "action": "block_import",
                }
            )
    if value.get("dynamic_interrupts") is not None:
        issues.append(
            {
                "code": "unsupported_dynamic_interrupts",
                "severity": "blocked",
                "path": "graph.compile.dynamic_interrupts",
                "message": "Dynamic inline `interrupt()` bodies are outside the supported manifest subset. Use human_approval nodes or static compile interrupts instead.",
                "action": "block_import",
            }
        )
    if value.get("send_routes") is not None:
        issues.append(
            {
                "code": "unsupported_send_routes",
                "severity": "blocked",
                "path": "graph.compile.send_routes",
                "message": "Runtime-varying Send routes are outside the supported manifest subset.",
                "action": "block_import",
            }
        )


def _collect_generated_python_support_issues(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    graph = _as_dict(manifest.get("graph")) or {}
    nodes = [dict(item) for item in list(graph.get("nodes") or []) if isinstance(item, dict)]
    edges = [dict(item) for item in list(graph.get("edges") or []) if isinstance(item, dict)]
    node_types = {
        _clean_identifier(node.get("id")): _clean_text(node.get("type"))
        for node in nodes
        if _clean_identifier(node.get("id"))
    }
    issues: list[dict[str, Any]] = []
    for node in nodes:
        node_id = _clean_identifier(node.get("id"))
        node_type = _clean_text(node.get("type"))
        if node_type not in LANGGRAPH_GENERATED_PYTHON_EXECUTABLE_NODE_TYPES:
            issues.append(
                {
                    "code": "generated_python_unsupported_node_type",
                    "severity": "blocked",
                    "node_id": node_id,
                    "node_type": node_type,
                    "message": (
                        f"Generated Python export only supports executable node types "
                        f"{', '.join(sorted(LANGGRAPH_GENERATED_PYTHON_EXECUTABLE_NODE_TYPES))}; "
                        f"node `{node_id}` uses `{node_type}`."
                    ),
                    "action": "block_export",
                }
            )
            continue
        if node_type == "astrabridge/router_condition":
            condition = _as_dict(_as_dict(node.get("node_type_config")) or {}).get("condition")
            mode = _clean_text(_as_dict(condition or {}).get("mode")) or "state_field_literal"
            if mode not in LANGGRAPH_GENERATED_PYTHON_EXECUTABLE_ROUTE_MODES:
                issues.append(
                    {
                        "code": "generated_python_unsupported_router_mode",
                        "severity": "blocked",
                        "node_id": node_id,
                        "node_type": node_type,
                        "message": (
                            f"Generated Python export supports router condition modes "
                            f"{', '.join(sorted(LANGGRAPH_GENERATED_PYTHON_EXECUTABLE_ROUTE_MODES))}; "
                            f"node `{node_id}` uses `{mode}`."
                        ),
                        "action": "block_export",
                    }
                )
        prompt = _as_dict(node.get("prompt")) or {}
        if _clean_text(prompt.get("template_mode")) == "migration_stub":
            issues.append(
                {
                    "code": "generated_python_migration_stub_prompt",
                    "severity": "blocked",
                    "node_id": node_id,
                    "node_type": node_type,
                    "message": (
                        f"Node `{node_id}` still uses the retired `migration_stub` prompt mode. "
                        "Replace it with an inline or referenced prompt before export."
                    ),
                    "action": "block_export",
                }
            )
    conditional_sources = {
        _clean_identifier(edge.get("source"))
        for edge in edges
        if (_clean_text(edge.get("kind")) or "edge") == "conditional"
    }
    for source in sorted(item for item in conditional_sources if item):
        if node_types.get(source) != "astrabridge/router_condition":
            issues.append(
                {
                    "code": "generated_python_unsupported_conditional_source",
                    "severity": "blocked",
                    "node_id": source,
                    "node_type": node_types.get(source) or "",
                    "message": (
                        f"Generated Python conditional routing requires a router_condition source node; "
                        f"`{source}` is `{node_types.get(source) or 'unknown'}`."
                    ),
                    "action": "block_export",
                }
            )
    return issues


def _import_supported_node(
    raw_node: dict[str, Any],
    *,
    workflow_graph_id: str,
    schema_registry: dict[str, Any],
) -> dict[str, Any]:
    langgraph_type = _clean_text(raw_node.get("type"))
    mapping = dict(LANGGRAPH_SUPPORTED_NODE_TYPES[langgraph_type])
    type_id = str(mapping["type_id"])
    node_id = _clean_identifier(raw_node.get("id")) or f"node_{_clean_identifier(type_id)}"
    role = _clean_text(raw_node.get("role")) or str(mapping.get("default_role") or "custom")
    label = _clean_text(raw_node.get("label") or raw_node.get("title")) or str(mapping.get("title") or langgraph_type)
    node_type_config = deepcopy(_as_dict(raw_node.get("node_type_config")) or {})
    routing = deepcopy(_as_dict(raw_node.get("routing")) or {})
    if not _clean_text(routing.get("selection_mode")):
        if type_id == "agent_model" and _clean_text(routing.get("provider_id")) and _clean_text(routing.get("model_id")):
            routing["selection_mode"] = "explicit"
        else:
            routing["selection_mode"] = "none"
    prompt = deepcopy(_as_dict(raw_node.get("prompt")) or {"template_mode": "inline", "template": label})
    tools = deepcopy(_as_dict(raw_node.get("tools")) or {"approval_mode": "ask", "allowed_tool_classes": []})
    execution, safety = _default_execution_and_safety(type_id)
    execution.update(deepcopy(_as_dict(raw_node.get("execution")) or {}))
    safety.update(deepcopy(_as_dict(raw_node.get("safety")) or {}))
    default_inputs, default_outputs = _default_ports_for_type(type_id)
    raw_ports = _as_dict(raw_node.get("ports")) or {}
    raw_inputs = list(raw_ports.get("inputs") or [])
    raw_outputs = list(raw_ports.get("outputs") or [])
    inputs = (
        []
        if type_id == "artifact_source" and not raw_inputs
        else _import_ports(raw_inputs, fallback_ports=default_inputs, port_group="inputs")
    )
    outputs = _import_ports(raw_outputs, fallback_ports=default_outputs, port_group="outputs")
    input_contract = deepcopy(_as_dict(raw_node.get("input_contract")) or {})
    if not input_contract:
        if not inputs:
            input_contract = {"mode": "task_context"}
        else:
            input_contract = {
                "mode": "typed_ports" if any(item["port_id"] != "task_context" for item in inputs) else "task_context_and_typed_ports",
                "port_ids": [item["port_id"] for item in inputs],
            }
    output_contract = deepcopy(_as_dict(raw_node.get("output_contract")) or {})
    if not output_contract:
        schema_ref = next((_clean_text(item.get("schema_ref")) for item in outputs if _clean_text(item.get("schema_ref"))), "")
        artifact_specs = [
            {
                "kind": _clean_text(item.get("artifact_kind")) or "structured_json",
                "id": _clean_identifier(item.get("port_id")) or f"artifact_{index}",
            }
            for index, item in enumerate(outputs)
            if _clean_text(item.get("artifact_kind"))
        ]
        output_contract = {
            "mode": "structured_and_artifacts" if schema_ref else "artifact_only",
            "machine_result_schema_ref": schema_ref or None,
            "artifact_specs": artifact_specs,
            "human_summary_required": True,
        }
    _ensure_output_artifact_ports(outputs=outputs, output_contract=output_contract)
    if _clean_text(output_contract.get("machine_result_schema_ref")):
        schema_ref = _clean_text(output_contract.get("machine_result_schema_ref"))
        if schema_ref not in schema_registry:
            schema_registry[schema_ref] = {"type": "object"}
    ui = deepcopy(_as_dict(raw_node.get("ui")) or {})
    position = deepcopy(_as_dict(ui.get("position")) or {"x": 0, "y": 0})
    node = {
        "node_id": node_id,
        "kind": type_id,
        "label": label,
        "role": role,
        "card_ref": _clean_text(raw_node.get("card_ref")) or f"agent_card_{_clean_identifier(type_id)}",
        "routing": routing,
        "prompt": prompt,
        "tools": tools,
        "ports": {"inputs": inputs, "outputs": outputs},
        "input_contract": input_contract,
        "output_contract": output_contract,
        "execution": execution,
        "safety": safety,
        "ui": {
            "position": {"x": int(position.get("x") or 0), "y": int(position.get("y") or 0)},
            "layout_mode": _clean_text(ui.get("layout_mode")) or "canvas",
        },
        "status": _clean_text(raw_node.get("status")) or "ready",
        "langgraph": {
            "node_type": langgraph_type,
            "raw_node": deepcopy(raw_node),
            "subgraph": deepcopy(_as_dict(raw_node.get("subgraph")) or {}),
        },
        "resolved_node_type_id": type_id,
        "node_type_registry_fingerprint": str(resolve_node_type(type_id, allow_unknown=True).get("registry_fingerprint") or ""),
    }
    if type_id == "human_approval" and not _clean_text(safety.get("approval_kind")):
        node["safety"]["approval_kind"] = _clean_text(node_type_config.get("review_kind")) or "human_gate"
    return {
        "node": node,
        "task_graph_overlay": {
            "palette_role": role,
            "node_type_id": type_id,
            "node_type_registry_fingerprint": str(node.get("node_type_registry_fingerprint") or ""),
            "node_type_config": _build_node_type_config_for_import(
                type_id=type_id,
                raw_node=raw_node,
                routing=routing,
                prompt=prompt,
                execution=execution,
                safety=safety,
            ),
        },
    }


def _import_supported_edge(
    raw_edge: dict[str, Any],
    *,
    source_node: dict[str, Any],
    target_node: dict[str, Any],
) -> dict[str, Any]:
    edge_id = _clean_identifier(raw_edge.get("id")) or f"edge_{source_node['node_id']}_{target_node['node_id']}"
    edge_kind = _clean_text(raw_edge.get("kind")) or "edge"
    source_port_id = _clean_identifier(raw_edge.get("source_port_id")) or _resolve_default_source_port(source_node)
    target_port_id = _clean_identifier(raw_edge.get("target_port_id")) or _resolve_default_target_port(target_node)
    source_schema_ref = _clean_text(dict(source_node.get("output_contract") or {}).get("machine_result_schema_ref"))
    handoff_contract = deepcopy(_as_dict(raw_edge.get("handoff_contract")) or {})
    handoff_contract.setdefault(
        "message_template",
        f"Deliver the required output from {source_node['node_id']} to {target_node['node_id']}.",
    )
    handoff_contract.setdefault("message_part_modes", ["machine_result", "artifact_ref"])
    handoff_contract.setdefault(
        "required_output_schema_refs",
        [source_schema_ref] if source_schema_ref else [],
    )
    handoff_contract.setdefault(
        "port_bindings",
        [{"from_port_id": source_port_id, "to_port_id": target_port_id}],
    )
    context_policy = deepcopy(_as_dict(raw_edge.get("context_policy")) or {})
    context_policy.setdefault("policy_id", f"policy_{edge_id}")
    context_policy.setdefault("history_mode", "explicit_refs_only")
    context_policy.setdefault("artifact_mode", "required_output_only")
    context_policy.setdefault("exclude_private_memory", True)
    context_policy.setdefault("include_machine_results", True)
    context_policy.setdefault("include_human_summaries", True)
    context_policy.setdefault("summary_strategy", "human_and_machine")
    return {
        "edge_id": edge_id,
        "from_node_id": source_node["node_id"],
        "to_node_id": target_node["node_id"],
        "edge_type": _clean_text(raw_edge.get("edge_type")) or ("control_dependency" if edge_kind == "conditional" else "artifact_handoff"),
        "handoff_contract": handoff_contract,
        "context_policy": context_policy,
        "ui": {
            "position": {
                "x": int((int(source_node["ui"]["position"]["x"]) + int(target_node["ui"]["position"]["x"])) / 2),
                "y": int((int(source_node["ui"]["position"]["y"]) + int(target_node["ui"]["position"]["y"])) / 2),
            },
            "layout_mode": "canvas",
        },
        "status": _clean_text(raw_edge.get("status")) or "ready",
        "langgraph": {
            "kind": edge_kind,
            "branch": _clean_text(raw_edge.get("branch")) if edge_kind == "conditional" else "",
            "raw_edge": deepcopy(raw_edge),
            "source_port_id": source_port_id,
            "target_port_id": target_port_id,
        },
    }


def _export_supported_node(
    node: dict[str, Any],
    *,
    langgraph_type: str,
    task_node: dict[str, Any] | None,
) -> dict[str, Any]:
    type_id = str(LANGGRAPH_SUPPORTED_NODE_TYPES[langgraph_type]["type_id"])
    raw_node = deepcopy(_as_dict(dict(node.get("langgraph") or {}).get("raw_node")) or {})
    task_ui_hints = _as_dict((task_node or {}).get("ui_hints")) or {}
    node_type_config = deepcopy(
        _as_dict(task_ui_hints.get("node_type_config"))
        or _build_node_type_config_for_export(type_id=type_id, node=node)
    )
    raw_node.update(
        {
            "id": str(node.get("node_id") or ""),
            "type": langgraph_type,
            "label": str(node.get("label") or ""),
            "title": str(node.get("label") or ""),
            "role": str(node.get("role") or "custom"),
            "card_ref": str(node.get("card_ref") or ""),
            "node_type_config": deepcopy(node_type_config),
            "routing": deepcopy(dict(node.get("routing") or {})),
            "prompt": deepcopy(dict(node.get("prompt") or {})),
            "tools": deepcopy(dict(node.get("tools") or {})),
            "ports": deepcopy(dict(node.get("ports") or {})),
            "input_contract": deepcopy(dict(node.get("input_contract") or {})),
            "output_contract": deepcopy(dict(node.get("output_contract") or {})),
            "execution": deepcopy(dict(node.get("execution") or {})),
            "safety": deepcopy(dict(node.get("safety") or {})),
            "ui": deepcopy(dict(node.get("ui") or {})),
            "status": str(node.get("status") or "ready"),
        }
    )
    subgraph_meta = _as_dict(dict(node.get("langgraph") or {}).get("subgraph")) or {}
    if subgraph_meta:
        raw_node["subgraph"] = deepcopy(subgraph_meta)
    return raw_node


def _export_supported_edge(edge: dict[str, Any]) -> dict[str, Any]:
    langgraph_meta = _as_dict(edge.get("langgraph")) or {}
    bindings = [
        dict(item)
        for item in list(dict(edge.get("handoff_contract") or {}).get("port_bindings") or [])
        if isinstance(item, dict)
    ]
    source_port_id = _clean_identifier(langgraph_meta.get("source_port_id")) or _clean_identifier(bindings[0].get("from_port_id")) if bindings else ""
    target_port_id = _clean_identifier(langgraph_meta.get("target_port_id")) or _clean_identifier(bindings[0].get("to_port_id")) if bindings else ""
    exported = {
        "id": str(edge.get("edge_id") or ""),
        "source": str(edge.get("from_node_id") or ""),
        "target": str(edge.get("to_node_id") or ""),
        "kind": _clean_text(langgraph_meta.get("kind")) or "edge",
        "edge_type": str(edge.get("edge_type") or ""),
        "source_port_id": source_port_id or None,
        "target_port_id": target_port_id or None,
        "handoff_contract": deepcopy(dict(edge.get("handoff_contract") or {})),
        "context_policy": deepcopy(dict(edge.get("context_policy") or {})),
        "status": str(edge.get("status") or "ready"),
    }
    branch = _clean_text(langgraph_meta.get("branch"))
    if branch:
        exported["branch"] = branch
    return exported


def _build_node_type_config_for_import(
    *,
    type_id: str,
    raw_node: dict[str, Any],
    routing: dict[str, Any],
    prompt: dict[str, Any],
    execution: dict[str, Any],
    safety: dict[str, Any],
) -> dict[str, Any]:
    existing = deepcopy(_as_dict(raw_node.get("node_type_config")) or {})
    if existing:
        return existing
    if type_id == "agent_model":
        return {
            "routing": routing,
            "prompt": prompt,
            "execution": execution,
            "safety": safety,
        }
    if type_id == "mcp_tool":
        return {
            "tool": _clean_text(raw_node.get("tool")),
            "server": _clean_text(raw_node.get("server")),
        }
    if type_id == "mcp_resource":
        return {
            "resource": _clean_text(raw_node.get("resource")),
            "server": _clean_text(raw_node.get("server")),
        }
    if type_id == "transform":
        return {
            "transform_id": _clean_text(raw_node.get("transform_id")),
        }
    if type_id == "router_condition":
        return {
            "condition": deepcopy(_as_dict(raw_node.get("condition")) or {}),
        }
    if type_id == "subgraph":
        return {
            "graph_ref": _clean_text(raw_node.get("graph_ref") or dict(raw_node.get("subgraph") or {}).get("graph_ref")),
        }
    if type_id == "human_approval":
        return {
            "review_kind": _clean_text(raw_node.get("review_kind") or safety.get("approval_kind")),
        }
    if type_id == "artifact_source":
        return {
            "artifact_kind": _clean_text(raw_node.get("artifact_kind")),
            "artifact_uri": _clean_text(raw_node.get("artifact_uri")),
        }
    if type_id == "artifact_sink":
        return {
            "target_kind": _clean_text(raw_node.get("target_kind")),
        }
    return {}


def _build_node_type_config_for_export(*, type_id: str, node: dict[str, Any]) -> dict[str, Any]:
    if type_id == "agent_model":
        return {
            "routing": deepcopy(dict(node.get("routing") or {})),
            "prompt": deepcopy(dict(node.get("prompt") or {})),
            "execution": deepcopy(dict(node.get("execution") or {})),
            "safety": deepcopy(dict(node.get("safety") or {})),
        }
    if type_id == "mcp_tool":
        langgraph_node = _as_dict(node.get("langgraph")) or {}
        raw_node = _as_dict(langgraph_node.get("raw_node")) or {}
        return {
            "server": _clean_text(raw_node.get("server")),
            "tool": _clean_text(raw_node.get("tool")),
        }
    if type_id == "mcp_resource":
        langgraph_node = _as_dict(node.get("langgraph")) or {}
        raw_node = _as_dict(langgraph_node.get("raw_node")) or {}
        return {
            "server": _clean_text(raw_node.get("server")),
            "resource": _clean_text(raw_node.get("resource")),
        }
    if type_id == "transform":
        return {
            "transform_id": _clean_text(_as_dict(node.get("langgraph")) and dict(_as_dict(node.get("langgraph")) or {}).get("raw_node", {}).get("transform_id")),
        }
    if type_id == "router_condition":
        langgraph_node = _as_dict(node.get("langgraph")) or {}
        raw_node = _as_dict(langgraph_node.get("raw_node")) or {}
        return {
            "condition": deepcopy(_as_dict(raw_node.get("condition")) or {}),
        }
    if type_id == "subgraph":
        langgraph_node = _as_dict(node.get("langgraph")) or {}
        raw_node = _as_dict(langgraph_node.get("raw_node")) or {}
        return {
            "graph_ref": _clean_text(raw_node.get("graph_ref") or dict(raw_node.get("subgraph") or {}).get("graph_ref")),
        }
    if type_id == "human_approval":
        return {
            "review_kind": _clean_text(dict(node.get("safety") or {}).get("approval_kind")),
        }
    if type_id == "artifact_source":
        langgraph_node = _as_dict(node.get("langgraph")) or {}
        raw_node = _as_dict(langgraph_node.get("raw_node")) or {}
        return {
            "artifact_kind": _clean_text(raw_node.get("artifact_kind")),
            "artifact_uri": _clean_text(raw_node.get("artifact_uri")),
        }
    if type_id == "artifact_sink":
        langgraph_node = _as_dict(node.get("langgraph")) or {}
        raw_node = _as_dict(langgraph_node.get("raw_node")) or {}
        return {
            "target_kind": _clean_text(raw_node.get("target_kind")),
        }
    return {}


def _default_execution_and_safety(type_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = resolve_node_type(type_id, allow_unknown=True)
    spec = dict(resolved.get("spec") or {})
    default_policy = dict(spec.get("default_policy") or {})
    execution_backend = str(default_policy.get("execution_backend") or "app_server").strip() or "app_server"
    spawn_mode = str(default_policy.get("spawn_mode") or "inline_lane").strip() or "inline_lane"
    execution = {
        "spawn_mode": spawn_mode,
        "timeout_ms": 120000,
        "retry_policy": {"max_attempts": 1},
        "execution_backend": "human_review" if execution_backend == "human_review" else "app_server",
        "collaboration_mode": "default",
    }
    if spawn_mode == "subagent_worker":
        execution["subagent_policy"] = {
            "isolation_mode": "lane",
            "max_turns": 8,
            "allow_direct_teammate_messages": False,
            "share_worktree": False,
            "allow_nested_subagents": False,
        }
    safety = {
        "risk_class": "moderate" if type_id == "human_approval" else "low",
        "allow_provider_calls": type_id == "agent_model",
        "allow_code_changes": False,
        "allow_install": False,
        "requires_human_approval": type_id == "human_approval",
    }
    if type_id == "human_approval":
        safety["approval_kind"] = "human_gate"
    return execution, safety


def _default_ports_for_type(type_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    spec = dict(resolve_node_type(type_id, allow_unknown=True).get("spec") or {})
    typed_ports = dict(spec.get("typed_ports") or {})
    inputs = [
        {
            "port_id": _clean_identifier(item.get("port_id")) or f"input_{index}",
            "label": _clean_text(item.get("label")) or _clean_identifier(item.get("port_id")) or f"Input {index + 1}",
            "port_type": _normalize_port_type(item.get("port_type")),
            "shape": _clean_text(item.get("shape")) or "single",
            "required": bool(item.get("required")),
            **({"schema_ref": _clean_text(item.get("schema_ref"))} if _clean_text(item.get("schema_ref")) else {}),
            **({"artifact_kind": _clean_text(item.get("artifact_kind"))} if _clean_text(item.get("artifact_kind")) else {}),
        }
        for index, item in enumerate(list(typed_ports.get("inputs") or []))
        if isinstance(item, dict)
    ]
    outputs = [
        {
            "port_id": _clean_identifier(item.get("port_id")) or f"output_{index}",
            "label": _clean_text(item.get("label")) or _clean_identifier(item.get("port_id")) or f"Output {index + 1}",
            "port_type": _normalize_port_type(item.get("port_type")),
            "shape": _clean_text(item.get("shape")) or "single",
            "required": bool(item.get("required")),
            **({"schema_ref": _clean_text(item.get("schema_ref"))} if _clean_text(item.get("schema_ref")) else {}),
            **({"artifact_kind": _clean_text(item.get("artifact_kind"))} if _clean_text(item.get("artifact_kind")) else {}),
        }
        for index, item in enumerate(list(typed_ports.get("outputs") or []))
        if isinstance(item, dict)
    ]
    return inputs, outputs


def _import_ports(ports: list[Any], *, fallback_ports: list[dict[str, Any]], port_group: str) -> list[dict[str, Any]]:
    if not ports:
        return deepcopy(fallback_ports)
    imported: list[dict[str, Any]] = []
    for index, raw_port in enumerate(ports):
        port = _as_dict(raw_port) or {}
        fallback = deepcopy(fallback_ports[index]) if index < len(fallback_ports) else {}
        port_id = _clean_identifier(port.get("port_id") or port.get("id") or port.get("name")) or _clean_identifier(fallback.get("port_id")) or f"{port_group[:-1]}_{index}"
        imported.append(
            {
                "port_id": port_id,
                "label": _clean_text(port.get("label") or port.get("name")) or _clean_text(fallback.get("label")) or port_id,
                "port_type": _normalize_port_type(port.get("port_type") or port.get("type") or fallback.get("port_type")),
                "shape": _clean_text(port.get("shape") or fallback.get("shape")) or "single",
                "required": bool(port.get("required", fallback.get("required"))),
                **({"schema_ref": _clean_text(port.get("schema_ref") or fallback.get("schema_ref"))} if _clean_text(port.get("schema_ref") or fallback.get("schema_ref")) else {}),
                **({"artifact_kind": _clean_text(port.get("artifact_kind") or fallback.get("artifact_kind"))} if _clean_text(port.get("artifact_kind") or fallback.get("artifact_kind")) else {}),
            }
        )
    return imported


def _ensure_output_artifact_ports(*, outputs: list[dict[str, Any]], output_contract: dict[str, Any]) -> None:
    artifact_specs = [dict(item) for item in list(output_contract.get("artifact_specs") or []) if isinstance(item, dict)]
    declared_output_artifact_kinds = {
        _clean_text(item.get("artifact_kind"))
        for item in outputs
        if _clean_text(item.get("artifact_kind"))
    }
    for spec in artifact_specs:
        artifact_kind = _clean_text(spec.get("kind"))
        if not artifact_kind or artifact_kind in declared_output_artifact_kinds:
            continue
        preferred_port_id = _clean_identifier(spec.get("id"))
        existing_output = next(
            (
                item
                for item in outputs
                if _clean_identifier(item.get("port_id")) == preferred_port_id
            ),
            None,
        )
        if isinstance(existing_output, dict):
            existing_output["artifact_kind"] = artifact_kind
            declared_output_artifact_kinds.add(artifact_kind)


def _resolve_default_source_port(source_node: dict[str, Any]) -> str:
    ports = [dict(item) for item in list(dict(source_node.get("ports") or {}).get("outputs") or []) if isinstance(item, dict)]
    if not ports:
        raise LangGraphStateGraphAdapterError(f"Node `{source_node.get('node_id')}` does not expose any output ports.")
    return _clean_identifier(ports[0].get("port_id")) or "machine_result"


def _resolve_default_target_port(target_node: dict[str, Any]) -> str:
    ports = [dict(item) for item in list(dict(target_node.get("ports") or {}).get("inputs") or []) if isinstance(item, dict)]
    if not ports:
        return "task_context"
    return _clean_identifier(ports[0].get("port_id")) or "task_context"


def _infer_state_channels(canonical: dict[str, Any]) -> dict[str, Any]:
    channels: dict[str, Any] = {}
    for node in list(canonical.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        for port_group in ("inputs", "outputs"):
            for port in list(dict(node.get("ports") or {}).get(port_group) or []):
                if not isinstance(port, dict):
                    continue
                port_id = _clean_identifier(port.get("port_id"))
                if not port_id:
                    continue
                channels.setdefault(
                    port_id,
                    {
                        "value_type": _normalize_port_type(port.get("port_type")),
                        "reducer": "replace",
                    },
                )
    if not channels:
        channels["data"] = {"value_type": "structured_json", "reducer": "replace"}
    return channels


def _normalize_compile_config_for_export(value: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(value)
    checkpointer = _as_dict(normalized.get("checkpointer")) or {}
    mode = _clean_text(checkpointer.get("mode")) or "disabled"
    if mode not in LANGGRAPH_SUPPORTED_CHECKPOINTER_MODES:
        mode = "disabled"
    normalized["checkpointer"] = {
        "mode": mode,
        "thread_id_field": _clean_text(checkpointer.get("thread_id_field")) or "thread_id",
        "checkpoint_ns_field": _clean_text(checkpointer.get("checkpoint_ns_field")) or "checkpoint_ns",
        "checkpoint_id_field": _clean_text(checkpointer.get("checkpoint_id_field")) or "checkpoint_id",
    }
    normalized["interrupt_before"] = [
        _clean_identifier(item)
        for item in list(normalized.get("interrupt_before") or [])
        if _clean_identifier(item)
    ]
    normalized["interrupt_after"] = [
        _clean_identifier(item)
        for item in list(normalized.get("interrupt_after") or [])
        if _clean_identifier(item)
    ]
    return normalized


def _validate_workspace_artifact_uri(uri: str, *, node_id: str) -> None:
    validate_protocol_payload(
        "ArtifactRef",
        {
            "artifact_id": "artifact",
            "artifact_uri": uri,
            "media_type": "application/octet-stream",
            "status": "ready",
            "lineage": {
                "task_id": "task_example",
                "run_id": "run_example",
                "source_node_id": node_id,
            },
        },
    )


def _build_loss_report(
    *,
    source_version: str | None,
    issues: list[dict[str, Any]],
    preserved_extensions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocked_count = sum(1 for item in issues if _clean_text(item.get("severity")) == "blocked")
    warning_count = sum(1 for item in issues if _clean_text(item.get("severity")) == "warning")
    preserved_count = sum(
        1
        for item in issues
        if _clean_text(item.get("action")) == "preserve_in_extensions"
    )
    status = "blocked" if blocked_count else "warning" if warning_count else "pass"
    return {
        "schema_version": LANGGRAPH_STATEGRAPH_ADAPTER_SCHEMA_VERSION,
        "adapter_id": "langgraph_stategraph",
        "source_format": LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
        "source_version": source_version,
        "status": status,
        "summary": {
            "issue_count": len(issues),
            "blocked_count": blocked_count,
            "warning_count": warning_count,
            "preserved_count": preserved_count,
        },
        "issues": deepcopy(issues),
        "preserved_extensions": deepcopy(preserved_extensions or {}),
    }


def _render_python_type(channel: Any) -> str:
    data = _as_dict(channel) or {}
    value_type = _normalize_port_type(data.get("value_type"))
    mapping = {
        "text": "str",
        "structured_json": "dict[str, Any]",
        "image": "dict[str, Any]",
        "audio": "dict[str, Any]",
        "video": "dict[str, Any]",
        "document": "dict[str, Any]",
        "code_diff": "dict[str, Any]",
        "dataset": "dict[str, Any]",
        "tool_result": "dict[str, Any]",
        "agent_report": "dict[str, Any]",
        "approval_record": "dict[str, Any]",
    }
    if _clean_text(data.get("reducer")) == "list_append":
        return f"list[{mapping.get(value_type, 'dict[str, Any]')}]"
    return mapping.get(value_type, "dict[str, Any]")


def _render_node_fn_name(node_id: str) -> str:
    return f"node_{_clean_identifier(node_id).replace('-', '_').replace('.', '_')}"


def _render_route_fn_name(node_id: str) -> str:
    return f"route_{_clean_identifier(node_id).replace('-', '_').replace('.', '_')}"


def _as_dict(value: Any) -> dict[str, Any] | None:
    return deepcopy(value) if isinstance(value, dict) else None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_identifier(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    if text in {LANGGRAPH_STATEGRAPH_START_NODE, LANGGRAPH_STATEGRAPH_END_NODE}:
        return text
    normalized = SAFE_IDENTIFIER_PATTERN.sub("_", text).strip("._:-")
    if not normalized:
        return ""
    if not re.match(r"^[A-Za-z0-9_]", normalized):
        normalized = f"id_{normalized}"
    return normalized[:120]


def _normalize_port_type(value: Any) -> str:
    text = _clean_text(value).lower()
    normalized = PORT_TYPE_ALIASES.get(text, text or "structured_json")
    return normalized if normalized in CANONICAL_PORT_TYPES else "structured_json"
