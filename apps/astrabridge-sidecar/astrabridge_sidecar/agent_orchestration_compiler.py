from __future__ import annotations

from copy import deepcopy
from typing import Any

from .agent_orchestration_contract import validate_agent_orchestration_graph
from .common import now_iso


AGENT_ORCHESTRATION_COMPILED_PLAN_VERSION = "astrabridge-agent-orchestration-compiled-plan-v1"


def compile_agent_orchestration_graph(
    graph: dict[str, Any],
    *,
    known_profile_ids: set[str] | None = None,
    known_provider_ids: set[str] | None = None,
    known_model_ids: set[str] | None = None,
    known_model_capabilities: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canonical = validate_agent_orchestration_graph(
        graph,
        known_profile_ids=known_profile_ids,
        known_provider_ids=known_provider_ids,
        known_model_ids=known_model_ids,
        known_model_capabilities=known_model_capabilities,
    )
    node_map = {
        str(item.get("node_id") or "").strip(): dict(item)
        for item in list(canonical.get("nodes") or [])
        if isinstance(item, dict)
    }
    edge_map = {
        str(item.get("edge_id") or "").strip(): dict(item)
        for item in list(canonical.get("edges") or [])
        if isinstance(item, dict)
    }
    incoming_edges: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in node_map}
    outgoing_edges: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in node_map}
    indegree: dict[str, int] = {node_id: 0 for node_id in node_map}
    node_input_ports: dict[str, dict[str, dict[str, Any]]] = {}
    node_output_ports: dict[str, dict[str, dict[str, Any]]] = {}
    for node_id, node in node_map.items():
        ports = dict(node.get("ports") or {})
        node_input_ports[node_id] = {
            str(item.get("port_id") or "").strip(): dict(item)
            for item in list(ports.get("inputs") or [])
            if isinstance(item, dict) and str(item.get("port_id") or "").strip()
        }
        node_output_ports[node_id] = {
            str(item.get("port_id") or "").strip(): dict(item)
            for item in list(ports.get("outputs") or [])
            if isinstance(item, dict) and str(item.get("port_id") or "").strip()
        }
    for edge_id, edge in edge_map.items():
        from_node_id = str(edge.get("from_node_id") or "").strip()
        to_node_id = str(edge.get("to_node_id") or "").strip()
        incoming_edges.setdefault(to_node_id, []).append(edge)
        outgoing_edges.setdefault(from_node_id, []).append(edge)
        indegree[to_node_id] = int(indegree.get(to_node_id, 0)) + 1
        _validate_compiler_edge(edge_id=edge_id, edge=edge, source_ports=node_output_ports.get(from_node_id, {}), target_ports=node_input_ports.get(to_node_id, {}))

    for node_id, node in node_map.items():
        _validate_required_input_dependencies(
            node_id=node_id,
            node=node,
            input_ports=node_input_ports.get(node_id, {}),
            incoming_edges=incoming_edges.get(node_id, []),
        )

    entry_node_ids = list(dict(canonical.get("graph_policy") or {}).get("entry_node_ids") or [])
    parallel_groups = _parallel_groups(entry_node_ids=entry_node_ids, indegree=indegree, outgoing_edges=outgoing_edges)
    node_to_group = {
        node_id: item["group_id"]
        for item in parallel_groups
        for node_id in list(item.get("node_ids") or [])
    }
    compiled_nodes: list[dict[str, Any]] = []
    approval_nodes: list[str] = []
    for node_id, node in node_map.items():
        execution = dict(node.get("execution") or {})
        safety = dict(node.get("safety") or {})
        incoming = incoming_edges.get(node_id, [])
        join_mode = _join_mode(node=node, incoming_edges=incoming)
        manual_gate = str(execution.get("spawn_mode") or "") == "manual_only"
        approval_required = bool(safety.get("requires_human_approval")) or manual_gate or any(
            str(edge.get("edge_type") or "").strip() == "approval_dependency" for edge in incoming
        )
        if approval_required:
            approval_nodes.append(node_id)
        compiled_nodes.append(
            {
                "node_id": node_id,
                "label": str(node.get("label") or node_id),
                "kind": str(node.get("kind") or ""),
                "role": str(node.get("role") or ""),
                "parallel_group_id": node_to_group.get(node_id),
                "dependency_node_ids": sorted({str(edge.get("from_node_id") or "").strip() for edge in incoming if str(edge.get("from_node_id") or "").strip()}),
                "dependency_edge_ids": sorted(str(edge.get("edge_id") or "").strip() for edge in incoming if str(edge.get("edge_id") or "").strip()),
                "outgoing_edge_ids": sorted(str(edge.get("edge_id") or "").strip() for edge in outgoing_edges.get(node_id, []) if str(edge.get("edge_id") or "").strip()),
                "join_mode": join_mode,
                "ready_condition": {
                    "entry_node": node_id in entry_node_ids,
                    "join_mode": join_mode,
                    "requires_all_dependencies": join_mode in {"all_required", "approval_gate_required"},
                },
                "execution": {
                    "spawn_mode": str(execution.get("spawn_mode") or ""),
                    "execution_backend": str(execution.get("execution_backend") or ""),
                    "timeout_ms": int(execution.get("timeout_ms") or 0),
                    "retry_policy": deepcopy(execution.get("retry_policy") or {}),
                    "collaboration_mode": str(execution.get("collaboration_mode") or ""),
                    "subagent_policy": deepcopy(execution.get("subagent_policy") or {}),
                },
                "approval_required": approval_required,
                "approval_kind": str(safety.get("approval_kind") or "").strip() or None,
                "input_ports": [
                    {
                        "port_id": str(item.get("port_id") or ""),
                        "port_type": str(item.get("port_type") or ""),
                        "required": bool(item.get("required")),
                    }
                    for item in list(dict(node.get("ports") or {}).get("inputs") or [])
                    if isinstance(item, dict)
                ],
                "output_ports": [
                    {
                        "port_id": str(item.get("port_id") or ""),
                        "port_type": str(item.get("port_type") or ""),
                    }
                    for item in list(dict(node.get("ports") or {}).get("outputs") or [])
                    if isinstance(item, dict)
                ],
            }
        )
    compiled_edges: list[dict[str, Any]] = []
    for edge_id, edge in edge_map.items():
        handoff_contract = dict(edge.get("handoff_contract") or {})
        context_policy = dict(edge.get("context_policy") or {})
        compiled_edges.append(
            {
                "edge_id": edge_id,
                "from_node_id": str(edge.get("from_node_id") or ""),
                "to_node_id": str(edge.get("to_node_id") or ""),
                "edge_type": str(edge.get("edge_type") or ""),
                "required_output_schema_refs": list(handoff_contract.get("required_output_schema_refs") or []),
                "port_bindings": deepcopy(list(handoff_contract.get("port_bindings") or [])),
                "context_envelope": {
                    "history_mode": str(context_policy.get("history_mode") or ""),
                    "artifact_mode": str(context_policy.get("artifact_mode") or ""),
                    "include_machine_results": bool(context_policy.get("include_machine_results")),
                    "include_human_summaries": bool(context_policy.get("include_human_summaries")),
                    "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
                    "summary_strategy": str(context_policy.get("summary_strategy") or ""),
                    "resource_refs": deepcopy(list(context_policy.get("resource_refs") or [])),
                    "included_artifacts": deepcopy(list(context_policy.get("included_artifacts") or [])),
                },
            }
        )
    return {
        "schema_version": AGENT_ORCHESTRATION_COMPILED_PLAN_VERSION,
        "graph_id": canonical["graph_id"],
        "task_id": canonical["task_id"],
        "graph_schema_version": canonical["schema_version"],
        "compiled_at": now_iso(),
        "entry_node_ids": entry_node_ids,
        "topology": {
            "node_count": len(compiled_nodes),
            "edge_count": len(compiled_edges),
            "parallel_group_count": len(parallel_groups),
            "max_parallelism": max(
                1,
                max((len(list(group.get("node_ids") or [])) for group in parallel_groups), default=1),
            ),
            "approval_node_count": len(approval_nodes),
            "max_depth": int(dict(canonical.get("graph_policy") or {}).get("max_depth") or 0),
        },
        "parallel_groups": parallel_groups,
        "approval_nodes": approval_nodes,
        "nodes": compiled_nodes,
        "edges": compiled_edges,
    }


def _validate_compiler_edge(*, edge_id: str, edge: dict[str, Any], source_ports: dict[str, dict[str, Any]], target_ports: dict[str, dict[str, Any]]) -> None:
    context_policy = dict(edge.get("context_policy") or {})
    history_mode = str(context_policy.get("history_mode") or "").strip()
    if history_mode == "last_n_messages":
        history_length = int(context_policy.get("history_length") or 0)
        if history_length <= 0:
            raise ValueError(f"compiled_plan[{edge_id}] rejects unsafe implicit full-history sharing; last_n_messages requires a positive history_length.")
    for binding in list(dict(edge.get("handoff_contract") or {}).get("port_bindings") or []):
        if not isinstance(binding, dict):
            continue
        from_port_id = str(binding.get("from_port_id") or "").strip()
        to_port_id = str(binding.get("to_port_id") or "").strip()
        source_port = dict(source_ports.get(from_port_id) or {})
        target_port = dict(target_ports.get(to_port_id) or {})
        source_type = str(source_port.get("port_type") or "").strip()
        target_type = str(target_port.get("port_type") or "").strip()
        if to_port_id == "task_context" and target_type == "text":
            continue
        if source_type and target_type and source_type != target_type:
            raise ValueError(f"compiled_plan[{edge_id}] has unsupported port binding {from_port_id}->{to_port_id}: {source_type} != {target_type}")


def _validate_required_input_dependencies(*, node_id: str, node: dict[str, Any], input_ports: dict[str, dict[str, Any]], incoming_edges: list[dict[str, Any]]) -> None:
    bound_target_ports: set[str] = set()
    for edge in incoming_edges:
        for binding in list(dict(edge.get("handoff_contract") or {}).get("port_bindings") or []):
            if isinstance(binding, dict):
                target = str(binding.get("to_port_id") or "").strip()
                if target:
                    bound_target_ports.add(target)
    for port_id, port in input_ports.items():
        if port_id == "task_context":
            continue
        if not bool(port.get("required")):
            continue
        if port_id not in bound_target_ports:
            raise ValueError(f"compiled_plan[{node_id}] is missing dependency for required input port {port_id}.")


def _parallel_groups(*, entry_node_ids: list[str], indegree: dict[str, int], outgoing_edges: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    remaining = {key: int(value) for key, value in indegree.items()}
    ready = [node_id for node_id in entry_node_ids if node_id in remaining]
    if not ready:
        ready = [node_id for node_id, value in remaining.items() if value == 0]
    groups: list[dict[str, Any]] = []
    visited: set[str] = set()
    group_index = 0
    while ready:
        current_group = sorted({node_id for node_id in ready if node_id not in visited})
        if not current_group:
            break
        group_id = f"group_{group_index}"
        groups.append({"group_id": group_id, "node_ids": current_group})
        group_index += 1
        next_ready: list[str] = []
        for node_id in current_group:
            visited.add(node_id)
            for edge in list(outgoing_edges.get(node_id) or []):
                target_id = str(edge.get("to_node_id") or "").strip()
                if not target_id or target_id not in remaining:
                    continue
                remaining[target_id] = int(remaining.get(target_id, 0)) - 1
                if remaining[target_id] == 0:
                    next_ready.append(target_id)
        ready = next_ready
    if len(visited) != len(remaining):
        unresolved = sorted(set(remaining).difference(visited))
        raise ValueError(f"compiled_plan has unresolved topology after compilation: {', '.join(unresolved)}")
    return groups


def _join_mode(*, node: dict[str, Any], incoming_edges: list[dict[str, Any]]) -> str:
    execution = dict(node.get("execution") or {})
    if str(execution.get("spawn_mode") or "").strip() == "manual_only":
        return "approval_gate_required"
    edge_types = {str(edge.get("edge_type") or "").strip() for edge in incoming_edges}
    if "approval_dependency" in edge_types:
        return "approval_gate_required"
    if "fanin_merge" in edge_types:
        return "all_required"
    return "all_required"
