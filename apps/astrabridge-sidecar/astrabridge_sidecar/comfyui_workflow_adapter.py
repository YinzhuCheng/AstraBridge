from __future__ import annotations

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


COMFYUI_WORKFLOW_ADAPTER_SCHEMA_VERSION = "astrabridge-comfyui-workflow-adapter-v1"
COMFYUI_WORKFLOW_SOURCE_FORMAT = "comfyui_workflow"
COMFYUI_WORKFLOW_SAVE_VARIANT = "save"
COMFYUI_WORKFLOW_EXTENSION_NAMESPACE = "astrabridge"
COMFYUI_WORKFLOW_SUPPORTED_VERSIONS = ("0.4", "1.0")
COMFYUI_WORKFLOW_DEFAULT_VERSION = "1.0"

COMFYUI_SUPPORTED_NODE_TYPES: dict[str, dict[str, Any]] = {
    "astrabridge/agent": {
        "type_id": "agent_model",
        "default_role": "worker",
        "card_ref": "agent_card_comfyui_agent",
        "title": "AstraBridge Agent",
        "size": [280, 180],
    },
    "astrabridge/mcp_tool": {
        "type_id": "mcp_tool",
        "default_role": "custom",
        "card_ref": "agent_card_comfyui_mcp_tool",
        "title": "AstraBridge MCP Tool",
        "size": [260, 160],
    },
    "astrabridge/mcp_resource": {
        "type_id": "mcp_resource",
        "default_role": "custom",
        "card_ref": "agent_card_comfyui_mcp_resource",
        "title": "AstraBridge MCP Resource",
        "size": [260, 160],
    },
    "astrabridge/transform": {
        "type_id": "transform",
        "default_role": "custom",
        "card_ref": "agent_card_comfyui_transform",
        "title": "AstraBridge Transform",
        "size": [240, 160],
    },
    "astrabridge/human_approval": {
        "type_id": "human_approval",
        "default_role": "gate",
        "card_ref": "agent_card_comfyui_human_approval",
        "title": "AstraBridge Human Approval",
        "size": [240, 160],
    },
    "astrabridge/artifact_source": {
        "type_id": "artifact_source",
        "default_role": "custom",
        "card_ref": "agent_card_comfyui_artifact_source",
        "title": "AstraBridge Artifact Source",
        "size": [240, 150],
    },
    "astrabridge/artifact_sink": {
        "type_id": "artifact_sink",
        "default_role": "custom",
        "card_ref": "agent_card_comfyui_artifact_sink",
        "title": "AstraBridge Artifact Sink",
        "size": [240, 150],
    },
}

TYPE_ID_TO_COMFYUI_NODE_TYPE = {
    data["type_id"]: comfy_type
    for comfy_type, data in COMFYUI_SUPPORTED_NODE_TYPES.items()
}

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


class ComfyUiWorkflowAdapterError(ValueError):
    pass


class ComfyUiWorkflowLossError(ComfyUiWorkflowAdapterError):
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
            "source_format": COMFYUI_WORKFLOW_SOURCE_FORMAT,
            "source_version": source_version,
            "loss_report": loss_report,
            "adapter_manifest": adapter_manifest,
        }


def comfyui_workflow_adapter_manifest() -> dict[str, Any]:
    return {
        "schema_version": COMFYUI_WORKFLOW_ADAPTER_SCHEMA_VERSION,
        "adapter_id": "comfyui_workflow",
        "source_format": COMFYUI_WORKFLOW_SOURCE_FORMAT,
        "variant": COMFYUI_WORKFLOW_SAVE_VARIANT,
        "supported_versions": list(COMFYUI_WORKFLOW_SUPPORTED_VERSIONS),
        "default_version": COMFYUI_WORKFLOW_DEFAULT_VERSION,
        "extension_namespace": COMFYUI_WORKFLOW_EXTENSION_NAMESPACE,
        "node_type_map": {
            comfy_type: {
                "type_id": data["type_id"],
                "default_role": data["default_role"],
            }
            for comfy_type, data in COMFYUI_SUPPORTED_NODE_TYPES.items()
        },
    }


def serialize_comfyui_workflow(workflow: dict[str, Any]) -> str:
    if not isinstance(workflow, dict):
        raise TypeError("ComfyUI workflow payload must be a dict.")
    return json.dumps(workflow, ensure_ascii=False, indent=2) + "\n"


def looks_like_comfyui_workflow(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    nodes = payload.get("nodes")
    links = payload.get("links")
    version = payload.get("version")
    return isinstance(nodes, list) and isinstance(links, list) and version is not None


def parse_comfyui_workflow_text(
    text: str,
    *,
    source_name: str = "<memory>",
) -> dict[str, Any]:
    if not isinstance(text, str):
        raise TypeError("ComfyUI workflow text must be a string.")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ComfyUiWorkflowAdapterError(
            f"{source_name} is not valid JSON: {exc.msg}",
        ) from exc
    if not looks_like_comfyui_workflow(payload):
        raise ComfyUiWorkflowAdapterError(
            f"{source_name} is not a supported ComfyUI workflow JSON payload.",
        )
    return deepcopy(payload)


def import_comfyui_workflow(
    workflow: dict[str, Any],
    *,
    graph_id: str | None = None,
    task_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    manifest = comfyui_workflow_adapter_manifest()
    normalized = parse_comfyui_workflow_text(
        serialize_comfyui_workflow(workflow),
        source_name="comfyui-workflow",
    )
    source_version = _workflow_version_text(normalized)
    issues: list[dict[str, Any]] = []
    if source_version not in COMFYUI_WORKFLOW_SUPPORTED_VERSIONS:
        issues.append(
            {
                "code": "unsupported_workflow_version",
                "severity": "blocked",
                "path": "version",
                "message": (
                    f"ComfyUI workflow version `{source_version}` is not supported. "
                    f"Supported versions: {', '.join(COMFYUI_WORKFLOW_SUPPORTED_VERSIONS)}."
                ),
                "action": "block_import",
            }
        )

    raw_nodes = [deepcopy(item) for item in list(normalized.get("nodes") or []) if isinstance(item, dict)]
    raw_links = [deepcopy(item) for item in list(normalized.get("links") or [])]
    node_by_numeric_id = {
        _workflow_node_id(item): deepcopy(item)
        for item in raw_nodes
        if _workflow_node_id(item) is not None
    }
    link_records = [_normalize_link_record(item) for item in raw_links]
    incident_links: dict[int, list[dict[str, Any]]] = {}
    for link in link_records:
        source_id = link.get("source_node_id")
        target_id = link.get("target_node_id")
        if isinstance(source_id, int):
            incident_links.setdefault(source_id, []).append(link)
        if isinstance(target_id, int):
            incident_links.setdefault(target_id, []).append(link)

    supported_nodes: list[dict[str, Any]] = []
    supported_numeric_ids: set[int] = set()
    opaque_nodes: list[dict[str, Any]] = []
    opaque_links: list[Any] = []
    raw_groups = [deepcopy(item) for item in list(normalized.get("groups") or [])]
    raw_config = deepcopy(normalized.get("config") or {})
    raw_extra = _as_dict(normalized.get("extra")) or {}
    adapter_extra = _as_dict(raw_extra.get(COMFYUI_WORKFLOW_EXTENSION_NAMESPACE)) or {}

    for raw_node in raw_nodes:
        numeric_id = _workflow_node_id(raw_node)
        if numeric_id is None:
            issues.append(
                {
                    "code": "invalid_node_id",
                    "severity": "blocked",
                    "path": "nodes[].id",
                    "message": "A ComfyUI workflow node is missing a numeric `id`.",
                    "action": "block_import",
                }
            )
            continue
        comfy_type = _clean_text(raw_node.get("type"))
        if comfy_type in COMFYUI_SUPPORTED_NODE_TYPES:
            supported_numeric_ids.add(numeric_id)
            supported_nodes.append(raw_node)
            continue
        incident = incident_links.get(numeric_id) or []
        if any(
            (
                isinstance(item.get("source_node_id"), int)
                and item.get("source_node_id") != numeric_id
                and item.get("source_node_id") in supported_numeric_ids
            )
            or (
                isinstance(item.get("target_node_id"), int)
                and item.get("target_node_id") != numeric_id
                and item.get("target_node_id") in supported_numeric_ids
            )
            for item in incident
        ):
            issues.append(
                {
                    "code": "unsupported_connected_node_type",
                    "severity": "blocked",
                    "node_id": numeric_id,
                    "node_type": comfy_type,
                    "message": (
                        f"Unsupported ComfyUI node `{comfy_type}` is connected to "
                        "the supported AstraBridge subgraph and cannot be preserved losslessly."
                    ),
                    "action": "block_import",
                }
            )
            continue
        opaque_nodes.append(raw_node)
        issues.append(
            {
                "code": "opaque_node_preserved",
                "severity": "warning",
                "node_id": numeric_id,
                "node_type": comfy_type,
                "message": (
                    f"Unsupported disconnected ComfyUI node `{comfy_type}` was preserved as opaque extension data."
                ),
                "action": "preserve_in_extensions",
            }
        )

    opaque_numeric_ids = {_workflow_node_id(item) for item in opaque_nodes if _workflow_node_id(item) is not None}
    supported_links: list[dict[str, Any]] = []
    for raw_link, link in zip(raw_links, link_records):
        source_id = link.get("source_node_id")
        target_id = link.get("target_node_id")
        if not isinstance(source_id, int) or not isinstance(target_id, int):
            issues.append(
                {
                    "code": "invalid_link_shape",
                    "severity": "blocked",
                    "link_id": link.get("link_id"),
                    "message": "A ComfyUI workflow link is missing required endpoint metadata.",
                    "action": "block_import",
                }
            )
            continue
        if source_id in supported_numeric_ids and target_id in supported_numeric_ids:
            supported_links.append(link)
            continue
        if source_id in opaque_numeric_ids and target_id in opaque_numeric_ids:
            opaque_links.append(deepcopy(raw_link))
            continue
        issues.append(
            {
                "code": "unsupported_cross_boundary_link",
                "severity": "blocked",
                "link_id": link.get("link_id"),
                "message": (
                    "A link crosses the supported AstraBridge subgraph boundary and cannot be preserved safely."
                ),
                "action": "block_import",
            }
        )

    if not supported_nodes:
        issues.append(
            {
                "code": "no_supported_nodes",
                "severity": "blocked",
                "message": "The workflow does not contain any supported AstraBridge ComfyUI nodes.",
                "action": "block_import",
            }
        )

    metadata = dict(adapter_extra.get("metadata") or {})
    schema_registry = dict(adapter_extra.get("schema_registry") or {})
    graph_policy = dict(adapter_extra.get("graph_policy") or {})
    source_migration = dict(adapter_extra.get("migration") or {})
    workflow_title = _clean_text(title) or _clean_text(metadata.get("title")) or "Imported ComfyUI Workflow"
    workflow_graph_id = _clean_identifier(graph_id) or _clean_identifier(adapter_extra.get("graph_id")) or "graph_comfyui_workflow"
    workflow_task_id = _clean_identifier(task_id) or _clean_identifier(adapter_extra.get("task_id")) or "task_example"

    canonical_nodes: list[dict[str, Any]] = []
    node_overlays: dict[str, dict[str, Any]] = {}
    canonical_by_numeric_id: dict[int, dict[str, Any]] = {}
    for raw_node in supported_nodes:
        canonical = _import_supported_node(
            raw_node,
            workflow_graph_id=workflow_graph_id,
            schema_registry=schema_registry,
        )
        canonical_nodes.append(canonical["node"])
        node_overlays[canonical["node"]["node_id"]] = canonical["task_graph_overlay"]
        canonical_by_numeric_id[_workflow_node_id(raw_node) or 0] = canonical["node"]
        artifact_uri = _clean_text(canonical["task_graph_overlay"].get("node_type_config", {}).get("artifact_uri"))
        if artifact_uri:
            try:
                _validate_workspace_artifact_uri(
                    artifact_uri,
                    node_id=canonical["node"]["node_id"],
                )
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

    canonical_edges: list[dict[str, Any]] = []
    for link in supported_links:
        try:
            canonical_edges.append(
                _import_supported_link(
                    link,
                    canonical_by_numeric_id=canonical_by_numeric_id,
                    extra_link_metadata=_as_dict(dict(adapter_extra.get("links") or {}).get(str(link["link_id"]))) or {},
                )
            )
        except Exception as exc:  # noqa: BLE001
            issues.append(
                {
                    "code": "invalid_supported_link",
                    "severity": "blocked",
                    "link_id": link.get("link_id"),
                    "message": str(exc),
                    "action": "block_import",
                }
            )

    incoming_node_ids = {
        str(edge.get("to_node_id") or "").strip()
        for edge in canonical_edges
        if str(edge.get("to_node_id") or "").strip()
    }
    entry_node_ids = [
        str(node.get("node_id") or "").strip()
        for node in canonical_nodes
        if str(node.get("node_id") or "").strip() and str(node.get("node_id") or "").strip() not in incoming_node_ids
    ]
    if not entry_node_ids and canonical_nodes:
        entry_node_ids = [str(canonical_nodes[0].get("node_id") or "").strip()]
    graph_policy.setdefault("entry_node_ids", entry_node_ids)
    graph_policy.setdefault("max_depth", max(2, len(canonical_nodes)))
    graph_policy.setdefault("default_permission_mode", "ask")
    graph_policy.setdefault("default_collaboration_mode", "default")
    graph_policy.setdefault("default_execution_backend", "app_server")
    graph_policy.setdefault("requires_dry_run_before_live", True)

    loss_report = _build_loss_report(
        source_version=source_version,
        issues=issues,
        preserved_extensions={
            "opaque_node_count": len(opaque_nodes),
            "opaque_link_count": len(opaque_links),
            "group_count": len(raw_groups),
        },
    )
    if loss_report["status"] == "blocked":
        raise ComfyUiWorkflowLossError(
            "ComfyUI workflow import is blocked by unsupported or unsafe constructs.",
            source_version=source_version,
            loss_report=loss_report,
            adapter_manifest=manifest,
        )

    source_migration_clean = {
        str(key): deepcopy(value)
        for key, value in source_migration.items()
        if str(key).strip() and str(key).strip() != "source_kind"
    }
    migration = {
        "source_kind": "imported_file",
        "compiled_task_graph_version": "astrabridge-task-graph-v1",
        **source_migration_clean,
        "adapter": {
            "adapter_id": "comfyui_workflow",
            "schema_version": COMFYUI_WORKFLOW_ADAPTER_SCHEMA_VERSION,
            "source_format": COMFYUI_WORKFLOW_SOURCE_FORMAT,
            "variant": COMFYUI_WORKFLOW_SAVE_VARIANT,
            "source_version": source_version,
            "extension_namespace": COMFYUI_WORKFLOW_EXTENSION_NAMESPACE,
            "graph_id": workflow_graph_id,
        },
        "warnings": [
            str(item.get("message") or "").strip()
            for item in issues
            if str(item.get("severity") or "").strip() == "warning"
        ],
        "adapter_extensions": {
            COMFYUI_WORKFLOW_EXTENSION_NAMESPACE: {
                "opaque_nodes": opaque_nodes,
                "opaque_links": opaque_links,
                "groups": raw_groups,
                "config": raw_config,
                "extra": deepcopy(raw_extra),
            }
        },
    }
    metadata.setdefault("created_at", now_iso())
    metadata["updated_at"] = now_iso()
    metadata.setdefault("description", "Imported from a supported ComfyUI workflow subset.")
    metadata.setdefault("tags", ["comfyui", "adapter"])
    metadata.setdefault("owners", [])
    metadata["adapter_manifest"] = manifest
    canonical_graph = validate_agent_orchestration_graph(
        {
            "schema_version": AGENT_ORCHESTRATION_SCHEMA_VERSION,
            "graph_id": workflow_graph_id,
            "task_id": workflow_task_id,
            "title": workflow_title,
            "template_id": _clean_text(metadata.get("template_id")) or "custom_blank_graph",
            "status": "ready",
            "metadata": metadata,
            "graph_policy": graph_policy,
            "nodes": canonical_nodes,
            "edges": canonical_edges,
            "schema_registry": schema_registry,
            "migration": migration,
            "state_version": int(adapter_extra.get("state_version") or 1),
        }
    )
    return {
        "schema_version": COMFYUI_WORKFLOW_ADAPTER_SCHEMA_VERSION,
        "source_format": COMFYUI_WORKFLOW_SOURCE_FORMAT,
        "source_version": source_version,
        "adapter_manifest": manifest,
        "loss_report": loss_report,
        "orchestration_graph": canonical_graph,
        "task_graph_overlays": node_overlays,
    }


def export_comfyui_workflow(
    orchestration_graph: dict[str, Any],
    *,
    task_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = comfyui_workflow_adapter_manifest()
    canonical = validate_agent_orchestration_graph(orchestration_graph)
    issues: list[dict[str, Any]] = []
    task_nodes = {
        str(item.get("node_id") or "").strip(): dict(item)
        for item in list((task_graph or {}).get("nodes") or [])
        if isinstance(item, dict) and str(item.get("node_id") or "").strip()
    }

    opaque_extension_root = _as_dict(
        dict(dict(canonical.get("migration") or {}).get("adapter_extensions") or {}).get(COMFYUI_WORKFLOW_EXTENSION_NAMESPACE)
    ) or {}
    opaque_nodes = [deepcopy(item) for item in list(opaque_extension_root.get("opaque_nodes") or []) if isinstance(item, dict)]
    opaque_links = [deepcopy(item) for item in list(opaque_extension_root.get("opaque_links") or [])]
    groups = [deepcopy(item) for item in list(opaque_extension_root.get("groups") or [])]
    config = deepcopy(opaque_extension_root.get("config") or {})
    extra = _as_dict(opaque_extension_root.get("extra")) or {}

    workflow_nodes: list[dict[str, Any]] = []
    node_numeric_ids: dict[str, int] = {}
    for index, node in enumerate(list(canonical.get("nodes") or []), start=1):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or "").strip()
        resolved = resolve_node_type(str(node.get("kind") or ""), allow_unknown=True)
        resolved_type_id = str(
            node.get("resolved_node_type_id")
            or resolved.get("resolved_type_id")
            or ""
        ).strip()
        comfy_type = TYPE_ID_TO_COMFYUI_NODE_TYPE.get(resolved_type_id)
        if not comfy_type:
            issues.append(
                {
                    "code": "unsupported_export_node_type",
                    "severity": "blocked",
                    "node_id": node_id,
                    "node_type_id": resolved_type_id or str(node.get("kind") or ""),
                    "message": (
                        f"Node `{node_id}` uses unsupported type `{resolved_type_id or str(node.get('kind') or '')}` "
                        "for ComfyUI export."
                    ),
                    "action": "block_export",
                }
            )
            continue
        node_numeric_ids[node_id] = index
        workflow_nodes.append(
            _export_supported_node(
                node,
                comfy_type=comfy_type,
                numeric_id=index,
                task_node=task_nodes.get(node_id),
            )
        )

    links: list[list[Any]] = []
    link_metadata: dict[str, Any] = {}
    output_links_by_node_slot: dict[tuple[int, int], list[int]] = {}
    input_link_by_node_slot: dict[tuple[int, int], int] = {}
    for link_index, edge in enumerate(list(canonical.get("edges") or []), start=1):
        if not isinstance(edge, dict):
            continue
        from_node_id = str(edge.get("from_node_id") or "").strip()
        to_node_id = str(edge.get("to_node_id") or "").strip()
        source_numeric = node_numeric_ids.get(from_node_id)
        target_numeric = node_numeric_ids.get(to_node_id)
        if source_numeric is None or target_numeric is None:
            issues.append(
                {
                    "code": "unsupported_export_edge_boundary",
                    "severity": "blocked",
                    "edge_id": str(edge.get("edge_id") or ""),
                    "message": "A ComfyUI export edge references a node that could not be exported.",
                    "action": "block_export",
                }
            )
            continue
        source_node = next(
            (
                item
                for item in workflow_nodes
                if int(item.get("id") or 0) == source_numeric
            ),
            None,
        )
        target_node = next(
            (
                item
                for item in workflow_nodes
                if int(item.get("id") or 0) == target_numeric
            ),
            None,
        )
        if source_node is None or target_node is None:
            continue
        source_port_id, target_port_id, port_type = _resolve_edge_port_binding(
            edge=edge,
            source_node=source_node,
            target_node=target_node,
        )
        source_slot = _port_index_by_id(source_node.get("outputs"), source_port_id)
        target_slot = _port_index_by_id(target_node.get("inputs"), target_port_id)
        if source_slot is None or target_slot is None:
            issues.append(
                {
                    "code": "unsupported_export_port_binding",
                    "severity": "blocked",
                    "edge_id": str(edge.get("edge_id") or ""),
                    "message": "A ComfyUI export edge could not resolve its source/target port slots.",
                    "action": "block_export",
                }
            )
            continue
        if (target_numeric, target_slot) in input_link_by_node_slot:
            issues.append(
                {
                    "code": "unsupported_multi_link_input",
                    "severity": "blocked",
                    "edge_id": str(edge.get("edge_id") or ""),
                    "message": "A ComfyUI input slot can only accept one link in the supported subset.",
                    "action": "block_export",
                }
            )
            continue
        input_link_by_node_slot[(target_numeric, target_slot)] = link_index
        output_links_by_node_slot.setdefault((source_numeric, source_slot), []).append(link_index)
        links.append([link_index, source_numeric, source_slot, target_numeric, target_slot, port_type])
        link_metadata[str(link_index)] = {
            "edge_id": str(edge.get("edge_id") or ""),
            "edge_type": str(edge.get("edge_type") or ""),
            "handoff_contract": deepcopy(dict(edge.get("handoff_contract") or {})),
            "context_policy": deepcopy(dict(edge.get("context_policy") or {})),
            "status": str(edge.get("status") or ""),
            "source_port_id": source_port_id,
            "target_port_id": target_port_id,
        }

    loss_report = _build_loss_report(
        source_version=COMFYUI_WORKFLOW_DEFAULT_VERSION,
        issues=issues,
        preserved_extensions={
            "opaque_node_count": len(opaque_nodes),
            "opaque_link_count": len(opaque_links),
            "group_count": len(groups),
        },
    )
    if loss_report["status"] == "blocked":
        raise ComfyUiWorkflowLossError(
            "ComfyUI workflow export is blocked by unsupported node or edge constructs.",
            source_version=COMFYUI_WORKFLOW_DEFAULT_VERSION,
            loss_report=loss_report,
            adapter_manifest=manifest,
        )

    for node in workflow_nodes:
        numeric_id = int(node.get("id") or 0)
        for slot_index, port in enumerate(list(node.get("inputs") or [])):
            if not isinstance(port, dict):
                continue
            node["inputs"][slot_index]["link"] = input_link_by_node_slot.get((numeric_id, slot_index))
        for slot_index, port in enumerate(list(node.get("outputs") or [])):
            if not isinstance(port, dict):
                continue
            node["outputs"][slot_index]["links"] = output_links_by_node_slot.get((numeric_id, slot_index), []) or None

    all_numeric_node_ids = [
        int(item.get("id") or 0)
        for item in [*workflow_nodes, *opaque_nodes]
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    all_numeric_link_ids = [
        int(_normalize_link_record(item).get("link_id") or 0)
        for item in [*links, *opaque_links]
        if _normalize_link_record(item).get("link_id") is not None
    ]
    workflow = {
        "version": float(COMFYUI_WORKFLOW_DEFAULT_VERSION),
        "state": {
            "lastNodeId": max(all_numeric_node_ids or [0]),
            "lastLinkId": max(all_numeric_link_ids or [0]),
        },
        "last_node_id": max(all_numeric_node_ids or [0]),
        "last_link_id": max(all_numeric_link_ids or [0]),
        "nodes": [*workflow_nodes, *opaque_nodes],
        "links": [*links, *opaque_links],
        "groups": groups,
        "config": config,
        "extra": {
            **extra,
            COMFYUI_WORKFLOW_EXTENSION_NAMESPACE: {
                "adapter_manifest": manifest,
                "graph_id": str(canonical.get("graph_id") or ""),
                "task_id": str(canonical.get("task_id") or ""),
                "metadata": {
                    "title": str(canonical.get("title") or ""),
                    "template_id": canonical.get("template_id"),
                },
                "graph_policy": deepcopy(dict(canonical.get("graph_policy") or {})),
                "schema_registry": deepcopy(dict(canonical.get("schema_registry") or {})),
                "migration": deepcopy(dict(canonical.get("migration") or {})),
                "links": link_metadata,
                "state_version": int(canonical.get("state_version") or 1),
            },
        },
    }
    return {
        "schema_version": COMFYUI_WORKFLOW_ADAPTER_SCHEMA_VERSION,
        "export_format": COMFYUI_WORKFLOW_SOURCE_FORMAT,
        "source_version": COMFYUI_WORKFLOW_DEFAULT_VERSION,
        "adapter_manifest": manifest,
        "loss_report": loss_report,
        "workflow": workflow,
        "serialized_text": serialize_comfyui_workflow(workflow),
    }


def _as_dict(value: Any) -> dict[str, Any] | None:
    return deepcopy(value) if isinstance(value, dict) else None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_identifier(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    normalized = SAFE_IDENTIFIER_PATTERN.sub("_", text).strip("._:-")
    if not normalized:
        return ""
    if not re.match(r"^[A-Za-z0-9]", normalized):
        normalized = f"id_{normalized}"
    return normalized[:120]


def _workflow_version_text(workflow: dict[str, Any]) -> str:
    raw = workflow.get("version")
    if isinstance(raw, (int, float)):
        return f"{raw:.1f}".rstrip("0").rstrip(".") if raw != int(raw) else f"{int(raw)}.0"
    return _clean_text(raw) or COMFYUI_WORKFLOW_DEFAULT_VERSION


def _workflow_node_id(node: dict[str, Any]) -> int | None:
    raw = node.get("id")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    text = _clean_text(raw)
    if text.isdigit():
        return int(text)
    return None


def _normalize_link_record(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "link_id": _optional_int(value.get("id") or value.get("link_id")),
            "source_node_id": _optional_int(value.get("from_node_id") or value.get("origin_id") or value.get("source_node_id")),
            "source_slot": _optional_int(value.get("from_slot") or value.get("origin_slot") or value.get("source_slot")),
            "target_node_id": _optional_int(value.get("to_node_id") or value.get("target_id") or value.get("target_node_id")),
            "target_slot": _optional_int(value.get("to_slot") or value.get("target_slot")),
            "type": _normalize_port_type(value.get("type")),
        }
    if isinstance(value, list) and len(value) >= 6:
        return {
            "link_id": _optional_int(value[0]),
            "source_node_id": _optional_int(value[1]),
            "source_slot": _optional_int(value[2]),
            "target_node_id": _optional_int(value[3]),
            "target_slot": _optional_int(value[4]),
            "type": _normalize_port_type(value[5]),
        }
    return {
        "link_id": None,
        "source_node_id": None,
        "source_slot": None,
        "target_node_id": None,
        "target_slot": None,
        "type": "structured_json",
    }


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = _clean_text(value)
    if text and re.fullmatch(r"-?\d+", text):
        return int(text)
    return None


def _normalize_port_type(value: Any) -> str:
    text = _clean_text(value).lower()
    normalized = PORT_TYPE_ALIASES.get(text, text or "structured_json")
    return normalized if normalized in CANONICAL_PORT_TYPES else "structured_json"


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


def _import_supported_node(
    raw_node: dict[str, Any],
    *,
    workflow_graph_id: str,
    schema_registry: dict[str, Any],
) -> dict[str, Any]:
    comfy_type = _clean_text(raw_node.get("type"))
    mapping = dict(COMFYUI_SUPPORTED_NODE_TYPES[comfy_type])
    type_id = str(mapping["type_id"])
    node_meta = _as_dict(dict(_as_dict(raw_node.get("properties")) or {}).get(COMFYUI_WORKFLOW_EXTENSION_NAMESPACE)) or {}
    node_id = _clean_identifier(node_meta.get("node_id")) or f"node_{_clean_identifier(type_id)}_{_workflow_node_id(raw_node)}"
    role = _clean_text(node_meta.get("role")) or str(mapping.get("default_role") or "custom")
    label = _clean_text(node_meta.get("label")) or _clean_text(raw_node.get("title")) or str(mapping.get("title") or comfy_type)
    routing = deepcopy(_as_dict(node_meta.get("routing")) or {})
    if not _clean_text(routing.get("selection_mode")):
        if type_id == "agent_model" and _clean_text(routing.get("provider_id")) and _clean_text(routing.get("model_id")):
            routing["selection_mode"] = "explicit"
        else:
            routing["selection_mode"] = "none"
    prompt = deepcopy(_as_dict(node_meta.get("prompt")) or {"template_mode": "inline", "template": label})
    tools = deepcopy(_as_dict(node_meta.get("tools")) or {"approval_mode": "ask", "allowed_tool_classes": []})
    execution, safety = _default_execution_and_safety(type_id)
    execution.update(deepcopy(_as_dict(node_meta.get("execution")) or {}))
    safety.update(deepcopy(_as_dict(node_meta.get("safety")) or {}))
    position = _workflow_node_position(raw_node)
    default_inputs, default_outputs = _default_ports_for_type(type_id)
    raw_inputs = list(raw_node.get("inputs") or [])
    raw_outputs = list(raw_node.get("outputs") or [])
    inputs = (
        []
        if type_id == "artifact_source" and not raw_inputs
        else _import_ports(
            ports=raw_inputs,
            fallback_ports=default_inputs,
            port_group="inputs",
        )
    )
    outputs = _import_ports(
        ports=raw_outputs,
        fallback_ports=default_outputs,
        port_group="outputs",
    )
    input_contract = deepcopy(_as_dict(node_meta.get("input_contract")) or {})
    input_mode = _clean_text(input_contract.get("mode"))
    input_port_ids = [str(item).strip() for item in list(input_contract.get("port_ids") or []) if str(item).strip()]
    if (
        not input_contract
        or (
            input_mode in {"typed_ports", "task_context_and_typed_ports"}
            and not input_port_ids
            and not inputs
        )
    ):
        if not inputs:
            input_contract = {"mode": "task_context"}
        else:
            input_contract = {
                "mode": "typed_ports" if any(item["port_id"] != "task_context" for item in inputs) else "task_context_and_typed_ports",
                "port_ids": [item["port_id"] for item in inputs],
            }
    output_contract = deepcopy(_as_dict(node_meta.get("output_contract")) or {})
    if not output_contract:
        machine_schema_ref = next(
            (
                _clean_text(item.get("schema_ref"))
                for item in outputs
                if _clean_text(item.get("schema_ref"))
            ),
            "",
        )
        artifact_specs = [
            {
                "kind": _clean_text(item.get("artifact_kind")) or "structured_json",
                "id": _clean_identifier(item.get("port_id")) or f"artifact_{index}",
            }
            for index, item in enumerate(outputs)
            if _clean_text(item.get("artifact_kind"))
        ]
        output_contract = {
            "mode": "structured_and_artifacts" if machine_schema_ref else "artifact_only",
            "machine_result_schema_ref": machine_schema_ref or None,
            "artifact_specs": artifact_specs,
            "human_summary_required": True,
        }
    artifact_specs = [
        dict(item)
        for item in list(output_contract.get("artifact_specs") or [])
        if isinstance(item, dict)
    ]
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
    raw_node_copy = deepcopy(raw_node)
    if _clean_text(output_contract.get("machine_result_schema_ref")):
        schema_ref = _clean_text(output_contract.get("machine_result_schema_ref"))
        if schema_ref not in schema_registry:
            schema_registry[schema_ref] = {"type": "object"}
    node_type_config = _build_node_type_config_for_import(
        type_id=type_id,
        node_meta=node_meta,
        routing=routing,
        prompt=prompt,
        execution=execution,
        safety=safety,
    )
    node = {
        "node_id": node_id,
        "kind": type_id,
        "label": label,
        "role": role,
        "card_ref": _clean_text(node_meta.get("card_ref")) or str(mapping.get("card_ref") or f"agent_card_{_clean_identifier(type_id)}"),
        "routing": routing,
        "prompt": prompt,
        "tools": tools,
        "ports": {"inputs": inputs, "outputs": outputs},
        "input_contract": input_contract,
        "output_contract": output_contract,
        "execution": execution,
        "safety": safety,
        "ui": {
            "position": position,
            "layout_mode": "canvas",
        },
        "status": _clean_text(node_meta.get("status")) or "ready",
        "comfyui": {
            "node_type": comfy_type,
            "numeric_id": _workflow_node_id(raw_node),
            "raw_node": raw_node_copy,
        },
        "resolved_node_type_id": type_id,
        "node_type_registry_fingerprint": str(resolve_node_type(type_id, allow_unknown=True).get("registry_fingerprint") or ""),
    }
    if type_id == "human_approval" and not _clean_text(safety.get("approval_kind")):
        node["safety"]["approval_kind"] = "human_gate"
    return {
        "node": node,
        "task_graph_overlay": {
            "palette_role": role,
            "node_type_id": type_id,
            "node_type_registry_fingerprint": str(node.get("node_type_registry_fingerprint") or ""),
            "node_type_config": node_type_config,
        },
    }


def _workflow_node_position(raw_node: dict[str, Any]) -> dict[str, int]:
    pos = raw_node.get("pos")
    if isinstance(pos, list) and len(pos) >= 2:
        x = _optional_int(pos[0])
        y = _optional_int(pos[1])
        if x is not None and y is not None:
            return {"x": x, "y": y}
    return {"x": 0, "y": 0}


def _import_ports(
    *,
    ports: list[Any],
    fallback_ports: list[dict[str, Any]],
    port_group: str,
) -> list[dict[str, Any]]:
    if not ports:
        return deepcopy(fallback_ports)
    imported: list[dict[str, Any]] = []
    for index, raw_port in enumerate(ports):
        port = _as_dict(raw_port) or {}
        fallback = deepcopy(fallback_ports[index]) if index < len(fallback_ports) else {}
        port_id = _clean_identifier(port.get("id") or port.get("name")) or _clean_identifier(fallback.get("port_id")) or f"{port_group[:-1]}_{index}"
        imported.append(
            {
                "port_id": port_id,
                "label": _clean_text(port.get("label") or port.get("name")) or _clean_text(fallback.get("label")) or port_id,
                "port_type": _normalize_port_type(port.get("type") or fallback.get("port_type")),
                "shape": _clean_text(port.get("shape") or fallback.get("shape")) or "single",
                "required": bool(port.get("required", fallback.get("required"))),
                **({"schema_ref": _clean_text(port.get("schema_ref") or fallback.get("schema_ref"))} if _clean_text(port.get("schema_ref") or fallback.get("schema_ref")) else {}),
                **({"artifact_kind": _clean_text(port.get("artifact_kind") or fallback.get("artifact_kind"))} if _clean_text(port.get("artifact_kind") or fallback.get("artifact_kind")) else {}),
            }
        )
    return imported


def _build_node_type_config_for_import(
    *,
    type_id: str,
    node_meta: dict[str, Any],
    routing: dict[str, Any],
    prompt: dict[str, Any],
    execution: dict[str, Any],
    safety: dict[str, Any],
) -> dict[str, Any]:
    existing = deepcopy(_as_dict(node_meta.get("node_type_config")) or {})
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
            "tool": _clean_text(node_meta.get("tool")),
            "server": _clean_text(node_meta.get("server")),
        }
    if type_id == "mcp_resource":
        return {
            "resource": _clean_text(node_meta.get("resource")),
            "server": _clean_text(node_meta.get("server")),
        }
    if type_id == "transform":
        return {
            "transform_id": _clean_text(node_meta.get("transform_id")),
        }
    if type_id == "human_approval":
        return {
            "review_kind": _clean_text(node_meta.get("review_kind") or safety.get("approval_kind")),
        }
    if type_id == "artifact_source":
        return {
            "artifact_kind": _clean_text(node_meta.get("artifact_kind")),
            "artifact_uri": _clean_text(node_meta.get("artifact_uri")),
        }
    if type_id == "artifact_sink":
        return {
            "target_kind": _clean_text(node_meta.get("target_kind")),
        }
    return {}


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


def _import_supported_link(
    link: dict[str, Any],
    *,
    canonical_by_numeric_id: dict[int, dict[str, Any]],
    extra_link_metadata: dict[str, Any],
) -> dict[str, Any]:
    source_node = canonical_by_numeric_id[int(link["source_node_id"])]
    target_node = canonical_by_numeric_id[int(link["target_node_id"])]
    source_output = _port_by_index(source_node.get("ports", {}).get("outputs"), int(link["source_slot"] or 0))
    target_input = _port_by_index(target_node.get("ports", {}).get("inputs"), int(link["target_slot"] or 0))
    source_port_id = _clean_identifier(extra_link_metadata.get("source_port_id")) or _clean_identifier(source_output.get("port_id")) or "machine_result"
    target_port_id = _clean_identifier(extra_link_metadata.get("target_port_id")) or _clean_identifier(target_input.get("port_id")) or "task_context"
    edge_id = _clean_identifier(extra_link_metadata.get("edge_id")) or f"edge_{source_node['node_id']}_{target_node['node_id']}_{int(link['link_id'] or 0)}"
    source_schema_ref = _clean_text(
        dict(source_node.get("output_contract") or {}).get("machine_result_schema_ref")
    )
    handoff_contract = deepcopy(extra_link_metadata.get("handoff_contract") or {})
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
    context_policy = deepcopy(extra_link_metadata.get("context_policy") or {})
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
        "edge_type": _clean_text(extra_link_metadata.get("edge_type")) or "artifact_handoff",
        "handoff_contract": handoff_contract,
        "context_policy": context_policy,
        "ui": {
            "position": {
                "x": int((int(source_node["ui"]["position"]["x"]) + int(target_node["ui"]["position"]["x"])) / 2),
                "y": int((int(source_node["ui"]["position"]["y"]) + int(target_node["ui"]["position"]["y"])) / 2),
            },
            "layout_mode": "canvas",
        },
        "status": _clean_text(extra_link_metadata.get("status")) or "ready",
        "comfyui": {
            "link_id": int(link["link_id"] or 0),
            "raw_link": deepcopy(link),
        },
    }


def _port_by_index(ports: Any, index: int) -> dict[str, Any]:
    items = [dict(item) for item in list(ports or []) if isinstance(item, dict)]
    if index < 0 or index >= len(items):
        raise ComfyUiWorkflowAdapterError(f"Port index {index} is out of range.")
    return items[index]


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
        "schema_version": COMFYUI_WORKFLOW_ADAPTER_SCHEMA_VERSION,
        "adapter_id": "comfyui_workflow",
        "source_format": COMFYUI_WORKFLOW_SOURCE_FORMAT,
        "variant": COMFYUI_WORKFLOW_SAVE_VARIANT,
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


def _export_supported_node(
    node: dict[str, Any],
    *,
    comfy_type: str,
    numeric_id: int,
    task_node: dict[str, Any] | None,
) -> dict[str, Any]:
    mapping = dict(COMFYUI_SUPPORTED_NODE_TYPES[comfy_type])
    resolved_type_id = str(mapping["type_id"])
    orchestration_properties = dict(node.get("comfyui") or {})
    raw_node = deepcopy(dict(orchestration_properties.get("raw_node") or {}))
    ui = dict(node.get("ui") or {})
    position = dict(ui.get("position") or {})
    base_properties = _as_dict(raw_node.get("properties")) or {}
    base_astrabridge = _as_dict(base_properties.get(COMFYUI_WORKFLOW_EXTENSION_NAMESPACE)) or {}
    task_ui_hints = _as_dict((task_node or {}).get("ui_hints")) or {}
    node_type_config = deepcopy(_as_dict(task_ui_hints.get("node_type_config")) or _as_dict(base_astrabridge.get("node_type_config")) or {})
    routing = deepcopy(
        _as_dict(node_type_config.get("routing"))
        if resolved_type_id == "agent_model"
        else None
        or _as_dict(node.get("routing"))
        or {}
    )
    prompt = deepcopy(
        _as_dict(node_type_config.get("prompt"))
        if resolved_type_id == "agent_model"
        else None
        or _as_dict(node.get("prompt"))
        or {}
    )
    execution = deepcopy(
        _as_dict(node_type_config.get("execution"))
        if resolved_type_id == "agent_model"
        else None
        or _as_dict(node.get("execution"))
        or {}
    )
    safety = deepcopy(
        _as_dict(node_type_config.get("safety"))
        if resolved_type_id == "agent_model"
        else None
        or _as_dict(node.get("safety"))
        or {}
    )
    inputs = _export_ports(list(dict(node.get("ports") or {}).get("inputs") or []))
    outputs = _export_ports(list(dict(node.get("ports") or {}).get("outputs") or []))
    raw_node.update(
        {
            "id": numeric_id,
            "type": comfy_type,
            "title": str(node.get("label") or mapping.get("title") or comfy_type),
            "pos": [int(position.get("x") or 0), int(position.get("y") or 0)],
            "size": list(raw_node.get("size") or mapping.get("size") or [240, 160]),
            "order": int(raw_node.get("order") or numeric_id),
            "mode": int(raw_node.get("mode") or 0),
            "inputs": inputs,
            "outputs": outputs,
            "widgets_values": _export_widget_values(
                resolved_type_id=resolved_type_id,
                node=node,
                node_type_config=node_type_config,
            ),
            "properties": {
                **base_properties,
                "Node name for S&R": base_properties.get("Node name for S&R") or mapping.get("title") or comfy_type,
                COMFYUI_WORKFLOW_EXTENSION_NAMESPACE: {
                    **base_astrabridge,
                    "node_id": str(node.get("node_id") or ""),
                    "label": str(node.get("label") or ""),
                    "role": str(node.get("role") or "custom"),
                    "card_ref": str(node.get("card_ref") or mapping.get("card_ref") or ""),
                    "node_type_id": resolved_type_id,
                    "node_type_config": deepcopy(node_type_config),
                    "routing": routing,
                    "prompt": prompt,
                    "tools": deepcopy(dict(node.get("tools") or {})),
                    "input_contract": deepcopy(dict(node.get("input_contract") or {})),
                    "output_contract": deepcopy(dict(node.get("output_contract") or {})),
                    "execution": execution,
                    "safety": safety,
                    "status": str(node.get("status") or "ready"),
                },
            },
        }
    )
    return raw_node


def _export_ports(ports: list[Any]) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for index, raw_port in enumerate(ports):
        if not isinstance(raw_port, dict):
            continue
        port_id = _clean_identifier(raw_port.get("port_id")) or f"port_{index}"
        exported.append(
            {
                "name": _clean_text(raw_port.get("label")) or port_id,
                "type": _normalize_port_type(raw_port.get("port_type")),
                "id": port_id,
                "shape": _clean_text(raw_port.get("shape")) or "single",
                "required": bool(raw_port.get("required")),
                **({"schema_ref": _clean_text(raw_port.get("schema_ref"))} if _clean_text(raw_port.get("schema_ref")) else {}),
                **({"artifact_kind": _clean_text(raw_port.get("artifact_kind"))} if _clean_text(raw_port.get("artifact_kind")) else {}),
            }
        )
    return exported


def _export_widget_values(
    *,
    resolved_type_id: str,
    node: dict[str, Any],
    node_type_config: dict[str, Any],
) -> list[Any]:
    if resolved_type_id == "agent_model":
        routing = dict(node_type_config.get("routing") or node.get("routing") or {})
        return [
            str(node.get("label") or ""),
            str(node.get("role") or "custom"),
            str(routing.get("provider_id") or ""),
            str(routing.get("model_id") or ""),
        ]
    if resolved_type_id == "mcp_tool":
        return [
            str(node_type_config.get("server") or ""),
            str(node_type_config.get("tool") or ""),
        ]
    if resolved_type_id == "mcp_resource":
        return [
            str(node_type_config.get("server") or ""),
            str(node_type_config.get("resource") or ""),
        ]
    if resolved_type_id == "transform":
        return [str(node_type_config.get("transform_id") or "")]
    if resolved_type_id == "human_approval":
        return [str(node_type_config.get("review_kind") or dict(node.get("safety") or {}).get("approval_kind") or "human_gate")]
    if resolved_type_id == "artifact_source":
        return [
            str(node_type_config.get("artifact_kind") or ""),
            str(node_type_config.get("artifact_uri") or ""),
        ]
    if resolved_type_id == "artifact_sink":
        return [str(node_type_config.get("target_kind") or "")]
    return [str(node.get("label") or "")]


def _resolve_edge_port_binding(
    *,
    edge: dict[str, Any],
    source_node: dict[str, Any],
    target_node: dict[str, Any],
) -> tuple[str, str, str]:
    handoff_contract = dict(edge.get("handoff_contract") or {})
    bindings = [
        dict(item)
        for item in list(handoff_contract.get("port_bindings") or [])
        if isinstance(item, dict)
    ]
    if bindings:
        source_port_id = _clean_identifier(bindings[0].get("from_port_id")) or "machine_result"
        target_port_id = _clean_identifier(bindings[0].get("to_port_id")) or "task_context"
    else:
        source_port_id = _clean_identifier(_port_by_index(source_node.get("outputs"), 0).get("id")) or "machine_result"
        target_port_id = _clean_identifier(_port_by_index(target_node.get("inputs"), 0).get("id")) or "task_context"
    source_port = _port_by_id(source_node.get("outputs"), source_port_id)
    port_type = _normalize_port_type(source_port.get("type") or "structured_json")
    return source_port_id, target_port_id, port_type


def _port_by_id(ports: Any, port_id: str) -> dict[str, Any]:
    items = [dict(item) for item in list(ports or []) if isinstance(item, dict)]
    for item in items:
        if _clean_identifier(item.get("id") or item.get("port_id") or item.get("name")) == port_id:
            return item
    raise ComfyUiWorkflowAdapterError(f"Unknown port id: {port_id}")


def _port_index_by_id(ports: Any, port_id: str) -> int | None:
    items = [dict(item) for item in list(ports or []) if isinstance(item, dict)]
    for index, item in enumerate(items):
        clean = _clean_identifier(item.get("id") or item.get("name") or item.get("port_id"))
        if clean == port_id:
            return index
    return None
