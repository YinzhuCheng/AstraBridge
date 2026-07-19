from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .agent_orchestration_contract import (
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    PORT_TYPES,
    lift_task_graph_to_agent_orchestration_graph,
    lower_agent_orchestration_graph_to_task_graph,
    validate_agent_orchestration_graph,
)
from .agent_orchestration_compiler import compile_agent_orchestration_graph
from .agent_orchestration_file_format import load_agent_orchestration_graph_file, serialize_agent_orchestration_graph, write_agent_orchestration_graph_file
from .model_catalog.catalog import effective_model_records
from .provider_capability_snapshot import graph_port_capabilities_from_snapshot
from .providers import get_provider_profile, resolve_provider_id
from .task_graph_contract import validate_graph_definition


AGENT_ORCHESTRATION_LINT_SCHEMA_VERSION = "astrabridge-agent-orchestration-lint-v1"
AGENT_ORCHESTRATION_COMPILE_SCHEMA_VERSION = "astrabridge-agent-orchestration-compile-v1"
AGENT_ORCHESTRATION_DRY_RUN_SCHEMA_VERSION = "astrabridge-agent-orchestration-dry-run-v1"
AGENT_ORCHESTRATION_DIFF_SCHEMA_VERSION = "astrabridge-agent-orchestration-diff-v1"
AGENT_ORCHESTRATION_MIGRATE_SCHEMA_VERSION = "astrabridge-agent-orchestration-migrate-v1"
_GENERIC_INPUT_PORT_TYPES = {"text", "structured_json", "document", "code_diff", "dataset", "tool_result", "agent_report", "approval_record"}
_GENERIC_OUTPUT_PORT_TYPES = {"text", "structured_json", "document", "code_diff", "dataset", "tool_result", "agent_report", "approval_record"}
_MODALITY_TO_PORT_TYPE = {
    "text": "text",
    "image": "image",
    "audio": "audio",
    "video": "video",
    "file": "document",
}


def build_known_model_capabilities(
    *,
    graph: dict[str, Any] | None = None,
    configured_models: list[dict[str, Any]] | None = None,
    profile_records: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    capabilities: dict[str, dict[str, Any]] = {}
    for model in effective_model_records(configured_models, include_disabled=True):
        if not isinstance(model, dict):
            continue
        _merge_model_capability_source(
            capabilities,
            _capability_keys_for_model(
                provider_id=str(model.get("provider") or "").strip(),
                model_id=str(model.get("native_model") or model.get("id") or "").strip(),
                full_model_id=str(model.get("id") or "").strip(),
            ),
            _port_capabilities_for_record(model),
        )
    for profile in list(profile_records or []):
        if not isinstance(profile, dict):
            continue
        provider_id = resolve_provider_id(str(profile.get("provider_id") or "").strip())
        model_id = str(profile.get("model") or profile.get("native_model") or "").strip()
        if not provider_id or not model_id:
            continue
        _merge_model_capability_source(
            capabilities,
            _capability_keys_for_model(provider_id=provider_id, model_id=model_id),
            _port_capabilities_for_record(profile),
        )
    if isinstance(graph, dict):
        for node in list(graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            routing = dict(node.get("routing") or {})
            provider_id_raw = str(routing.get("provider_id") or "").strip()
            provider_id = resolve_provider_id(provider_id_raw) if provider_id_raw else ""
            model_id = str(routing.get("model_id") or "").strip()
            keys = _capability_keys_for_model(provider_id=provider_id, model_id=model_id)
            if not provider_id or not model_id or any(key in capabilities for key in keys):
                continue
            profile = get_provider_profile(provider_id)
            if profile is None:
                continue
            _merge_model_capability_source(
                capabilities,
                keys,
                _port_capabilities_for_record(
                    {
                        "provider_id": provider_id,
                        "model": model_id,
                        "input_modalities": list(profile.context_policy.default_input_modalities),
                        "capabilities": profile.capability_payload(),
                    }
                ),
            )
    return capabilities


def _capability_keys_for_model(*, provider_id: str, model_id: str, full_model_id: str | None = None) -> list[str]:
    native = str(model_id or "").strip()
    provider_raw = str(provider_id or "").strip()
    provider = resolve_provider_id(provider_raw) if provider_raw else ""
    explicit_full = str(full_model_id or "").strip()
    generated_full = f"{provider}/{native}" if provider and native else ""
    keys: list[str] = []
    for candidate in (native, explicit_full, generated_full):
        if candidate and candidate not in keys:
            keys.append(candidate)
    return keys


def _merge_model_capability_source(target: dict[str, dict[str, Any]], keys: list[str], source: dict[str, Any]) -> None:
    input_port_types = sorted({str(item).strip() for item in list(source.get("input_port_types") or []) if str(item).strip() in PORT_TYPES})
    output_port_types = sorted({str(item).strip() for item in list(source.get("output_port_types") or []) if str(item).strip() in PORT_TYPES})
    if not input_port_types and not output_port_types:
        return
    for key in keys:
        current = dict(target.get(key) or {})
        merged_inputs = sorted({*list(current.get("input_port_types") or []), *input_port_types})
        merged_outputs = sorted({*list(current.get("output_port_types") or []), *output_port_types})
        target[key] = {
            "input_port_types": merged_inputs,
            "output_port_types": merged_outputs,
        }


def _port_capabilities_for_record(record: dict[str, Any]) -> dict[str, Any]:
    input_port_types = set(_GENERIC_INPUT_PORT_TYPES)
    output_port_types = set(_GENERIC_OUTPUT_PORT_TYPES)
    snapshot = dict(record.get("verified_capability_snapshot") or {})
    snapshot_status = str(record.get("verified_capability_snapshot_status") or snapshot.get("status") or "").strip().lower()
    snapshot_ports = graph_port_capabilities_from_snapshot(snapshot) if snapshot_status in {"verified", "partial"} else {}
    for port_type in list(snapshot_ports.get("input_port_types") or []):
        if str(port_type).strip() in PORT_TYPES:
            input_port_types.add(str(port_type).strip())
    for port_type in list(snapshot_ports.get("output_port_types") or []):
        if str(port_type).strip() in PORT_TYPES:
            output_port_types.add(str(port_type).strip())
    input_modalities = [str(item).strip().lower() for item in list(record.get("input_modalities") or []) if str(item).strip()]
    for modality in input_modalities:
        port_type = _MODALITY_TO_PORT_TYPE.get(modality)
        if port_type:
            input_port_types.add(port_type)
            if port_type != "text":
                output_port_types.add(port_type)
    capabilities = dict(record.get("capabilities") or {})
    if bool(capabilities.get("supports_vision")):
        input_port_types.add("image")
        output_port_types.add("image")
    if bool(capabilities.get("supports_tool_result_images")):
        output_port_types.add("image")
    return {
        "input_port_types": sorted(input_port_types),
        "output_port_types": sorted(output_port_types),
    }


def lint_agent_orchestration_graph_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    graph = load_agent_orchestration_graph_file(file_path)
    lowered = lower_agent_orchestration_graph_to_task_graph(graph)
    node_count = len(list(graph.get("nodes") or []))
    edge_count = len(list(graph.get("edges") or []))
    return {
        "schema_version": AGENT_ORCHESTRATION_LINT_SCHEMA_VERSION,
        "status": "pass",
        "file_path": str(file_path),
        "graph_id": graph["graph_id"],
        "graph_schema_version": graph["schema_version"],
        "node_count": node_count,
        "edge_count": edge_count,
        "lowering": {
            "status": "pass",
            "task_graph_schema_version": lowered["schema_version"],
            "template_id": lowered["template_id"],
        },
        "warnings": [],
    }


def compile_agent_orchestration_graph_file(
    path: str | Path,
    *,
    known_profile_ids: set[str] | None = None,
    known_provider_ids: set[str] | None = None,
    known_model_ids: set[str] | None = None,
    configured_models: list[dict[str, Any]] | None = None,
    profile_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    file_path = Path(path)
    graph = load_agent_orchestration_graph_file(file_path)
    known_model_capabilities = build_known_model_capabilities(
        graph=graph,
        configured_models=configured_models,
        profile_records=profile_records,
    )
    graph = validate_agent_orchestration_graph(
        graph,
        known_profile_ids=known_profile_ids,
        known_provider_ids=known_provider_ids,
        known_model_ids=known_model_ids,
        known_model_capabilities=known_model_capabilities,
    )
    compiled_plan = compile_agent_orchestration_graph(
        graph,
        known_profile_ids=known_profile_ids,
        known_provider_ids=known_provider_ids,
        known_model_ids=known_model_ids,
        known_model_capabilities=known_model_capabilities,
    )
    lowered = lower_agent_orchestration_graph_to_task_graph(graph)
    return {
        "schema_version": AGENT_ORCHESTRATION_COMPILE_SCHEMA_VERSION,
        "status": "pass",
        "file_path": str(file_path),
        "graph_id": graph["graph_id"],
        "graph_schema_version": graph["schema_version"],
        "summary": {
            "node_count": len(list(graph.get("nodes") or [])),
            "edge_count": len(list(graph.get("edges") or [])),
            "parallel_group_count": int(dict(compiled_plan.get("topology") or {}).get("parallel_group_count") or 0),
            "approval_node_count": len(list(compiled_plan.get("approval_nodes") or [])),
            "task_graph_schema_version": lowered["schema_version"],
        },
        "lowering": {
            "status": "pass",
            "task_graph_schema_version": lowered["schema_version"],
            "template_id": lowered["template_id"],
        },
        "compiled_plan": compiled_plan,
        "warnings": [],
    }


def dry_run_agent_orchestration_graph_file(
    path: str | Path,
    *,
    known_profile_ids: set[str] | None = None,
    known_provider_ids: set[str] | None = None,
    known_model_ids: set[str] | None = None,
    configured_models: list[dict[str, Any]] | None = None,
    profile_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    file_path = Path(path)
    graph = load_agent_orchestration_graph_file(file_path)
    known_model_capabilities = build_known_model_capabilities(
        graph=graph,
        configured_models=configured_models,
        profile_records=profile_records,
    )
    graph = validate_agent_orchestration_graph(
        graph,
        known_profile_ids=known_profile_ids,
        known_provider_ids=known_provider_ids,
        known_model_ids=known_model_ids,
        known_model_capabilities=known_model_capabilities,
    )
    compiled_plan = compile_agent_orchestration_graph(
        graph,
        known_profile_ids=known_profile_ids,
        known_provider_ids=known_provider_ids,
        known_model_ids=known_model_ids,
        known_model_capabilities=known_model_capabilities,
    )
    lowered = lower_agent_orchestration_graph_to_task_graph(graph)
    node_results = [_dry_run_node_result(node) for node in list(graph.get("nodes") or []) if isinstance(node, dict)]
    output_schema_by_node = {
        str(node.get("node_id") or "").strip(): str(dict(node.get("output_contract") or {}).get("machine_result_schema_ref") or "").strip()
        for node in list(graph.get("nodes") or [])
        if isinstance(node, dict)
    }
    edge_results = [
        _dry_run_edge_result(edge, output_schema_by_node=output_schema_by_node)
        for edge in list(graph.get("edges") or [])
        if isinstance(edge, dict)
    ]
    warnings = [reason for item in [*node_results, *edge_results] for reason in list(item.get("reasons") or []) if item.get("status") == "warning"]
    blockers = [reason for item in [*node_results, *edge_results] for reason in list(item.get("reasons") or []) if item.get("status") == "blocked"]
    overall_status = "blocked" if blockers else "warning" if warnings else "pass"
    return {
        "schema_version": AGENT_ORCHESTRATION_DRY_RUN_SCHEMA_VERSION,
        "status": overall_status,
        "file_path": str(file_path),
        "graph_id": graph["graph_id"],
        "graph_schema_version": graph["schema_version"],
        "summary": {
            "node_count": len(node_results),
            "edge_count": len(edge_results),
            "blocking_count": len(blockers),
            "warning_count": len(warnings),
            "task_graph_schema_version": lowered["schema_version"],
            "parallel_group_count": int(dict(compiled_plan.get("topology") or {}).get("parallel_group_count") or 0),
        },
        "node_results": node_results,
        "edge_results": edge_results,
        "compiled_plan": compiled_plan,
        "warnings": warnings,
        "blockers": blockers,
    }


def diff_agent_orchestration_graph_files(old_path: str | Path, new_path: str | Path) -> dict[str, Any]:
    old_file = Path(old_path)
    new_file = Path(new_path)
    old_graph = load_agent_orchestration_graph_file(old_file)
    new_graph = load_agent_orchestration_graph_file(new_file)
    return diff_agent_orchestration_graphs(
        old_graph,
        new_graph,
        old_file_path=str(old_file),
        new_file_path=str(new_file),
    )


def migrate_task_graph_file_to_orchestration(
    path: str | Path,
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    file_path = Path(path)
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    task_graph = validate_graph_definition(payload)
    orchestration_graph = lift_task_graph_to_agent_orchestration_graph(task_graph)
    serialized = serialize_agent_orchestration_graph(orchestration_graph)
    written_path: str | None = None
    if output_path is not None:
        written = write_agent_orchestration_graph_file(output_path, orchestration_graph)
        written_path = str(written)
    return {
        "schema_version": AGENT_ORCHESTRATION_MIGRATE_SCHEMA_VERSION,
        "status": "pass",
        "source_file_path": str(file_path),
        "source_graph_id": task_graph["graph_id"],
        "source_schema_version": task_graph["schema_version"],
        "graph_id": orchestration_graph["graph_id"],
        "graph_schema_version": orchestration_graph["schema_version"],
        "warning_count": len(list(dict(orchestration_graph.get("migration") or {}).get("warnings") or [])),
        "output_path": written_path,
        "serialized_text": serialized,
        "orchestration_graph": orchestration_graph,
    }


def diff_agent_orchestration_graphs(
    old_graph: dict[str, Any],
    new_graph: dict[str, Any],
    *,
    old_file_path: str | None = None,
    new_file_path: str | None = None,
) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []

    _compare_top_level(old_graph, new_graph, changes=changes)
    _compare_nodes(old_graph, new_graph, changes=changes)
    _compare_edges(old_graph, new_graph, changes=changes)

    change_types = sorted({str(item.get("change_type") or "") for item in changes if str(item.get("change_type") or "")})
    return {
        "schema_version": AGENT_ORCHESTRATION_DIFF_SCHEMA_VERSION,
        "status": "changed" if changes else "no_change",
        "old_file_path": old_file_path,
        "new_file_path": new_file_path,
        "old_graph_id": old_graph["graph_id"],
        "new_graph_id": new_graph["graph_id"],
        "summary": {
            "change_count": len(changes),
            "change_types": change_types,
            "old_node_count": len(list(old_graph.get("nodes") or [])),
            "new_node_count": len(list(new_graph.get("nodes") or [])),
            "old_edge_count": len(list(old_graph.get("edges") or [])),
            "new_edge_count": len(list(new_graph.get("edges") or [])),
        },
        "changes": changes,
    }


def render_agent_orchestration_report_markdown(report: dict[str, Any]) -> str:
    if not isinstance(report, dict):
        raise TypeError("Report must be a dict.")
    schema_version = str(report.get("schema_version") or "")
    if schema_version == AGENT_ORCHESTRATION_LINT_SCHEMA_VERSION:
        return _render_lint_markdown(report)
    if schema_version == AGENT_ORCHESTRATION_COMPILE_SCHEMA_VERSION:
        return _render_compile_markdown(report)
    if schema_version == AGENT_ORCHESTRATION_DRY_RUN_SCHEMA_VERSION:
        return _render_dry_run_markdown(report)
    if schema_version == AGENT_ORCHESTRATION_DIFF_SCHEMA_VERSION:
        return _render_diff_markdown(report)
    if schema_version == AGENT_ORCHESTRATION_MIGRATE_SCHEMA_VERSION:
        return _render_migrate_markdown(report)
    raise ValueError("Unknown report schema version.")


def _dry_run_node_result(node: dict[str, Any]) -> dict[str, Any]:
    node_id = str(node.get("node_id") or "").strip()
    reasons: list[str] = []
    status = "pass"
    routing = dict(node.get("routing") or {})
    selection_mode = str(routing.get("selection_mode") or "").strip()
    tools = dict(node.get("tools") or {})
    output_contract = dict(node.get("output_contract") or {})
    execution = dict(node.get("execution") or {})
    safety = dict(node.get("safety") or {})

    if selection_mode == "none" and str(node.get("kind") or "") != "gate":
        status = _promote_status(status, "warning")
        reasons.append("Node does not pin a provider/model or profile route.")
    if str(tools.get("approval_mode") or "") == "allow":
        status = _promote_status(status, "warning")
        reasons.append("Tool approval mode is allow; review before live execution.")
    if str(output_contract.get("mode") or "") != "structured_only" and not list(output_contract.get("artifact_specs") or []):
        status = "blocked"
        reasons.append("Output contract does not declare artifact_specs.")
    if str(output_contract.get("mode") or "") != "artifact_only" and not str(output_contract.get("machine_result_schema_ref") or "").strip():
        status = "blocked"
        reasons.append("Output contract is missing machine_result_schema_ref.")
    if int(execution.get("timeout_ms") or 0) <= 0:
        status = "blocked"
        reasons.append("Execution timeout must be positive for dry-run readiness.")
    if (bool(safety.get("allow_code_changes")) or bool(safety.get("allow_install")) or str(safety.get("risk_class") or "") in {"high", "critical"}) and not bool(
        safety.get("requires_human_approval")
    ):
        status = "blocked"
        reasons.append("High-risk node is missing requires_human_approval.")
    return {
        "node_id": node_id,
        "label": str(node.get("label") or node_id),
        "status": status,
        "reasons": reasons,
    }


def _dry_run_edge_result(edge: dict[str, Any], *, output_schema_by_node: dict[str, str]) -> dict[str, Any]:
    edge_id = str(edge.get("edge_id") or "").strip()
    reasons: list[str] = []
    status = "pass"
    handoff_contract = dict(edge.get("handoff_contract") or {})
    context_policy = dict(edge.get("context_policy") or {})
    source_node_id = str(edge.get("from_node_id") or "").strip()
    source_schema_ref = str(output_schema_by_node.get(source_node_id) or "").strip()
    declared_refs = [str(item).strip() for item in list(handoff_contract.get("required_output_schema_refs") or []) if str(item).strip()]

    if not declared_refs:
        status = "blocked"
        reasons.append("Handoff contract does not declare required_output_schema_refs.")
    elif source_schema_ref and source_schema_ref not in declared_refs:
        status = "blocked"
        reasons.append(f"Handoff contract does not include the source schema ref {source_schema_ref}.")
    if str(context_policy.get("history_mode") or "") == "explicit_refs_only":
        if not list(context_policy.get("resource_refs") or []) and not list(context_policy.get("included_artifacts") or []):
            status = _promote_status(status, "warning")
            reasons.append("Edge uses explicit_refs_only without resource_refs or included_artifacts.")
    if not bool(context_policy.get("exclude_private_memory")):
        status = "blocked"
        reasons.append("Edge does not exclude private memory.")
    return {
        "edge_id": edge_id,
        "label": f"{edge.get('from_node_id')} -> {edge.get('to_node_id')}",
        "status": status,
        "reasons": reasons,
    }


def _compare_top_level(old_graph: dict[str, Any], new_graph: dict[str, Any], *, changes: list[dict[str, Any]]) -> None:
    for field in ("title", "template_id", "status"):
        if old_graph.get(field) != new_graph.get(field):
            changes.append(
                {
                    "change_type": f"graph_{field}_changed",
                    "field": field,
                    "old": old_graph.get(field),
                    "new": new_graph.get(field),
                }
            )
    old_policy = dict(old_graph.get("graph_policy") or {})
    new_policy = dict(new_graph.get("graph_policy") or {})
    for field in ("max_depth", "default_permission_mode", "default_collaboration_mode", "default_execution_backend", "requires_dry_run_before_live"):
        if old_policy.get(field) != new_policy.get(field):
            changes.append(
                {
                    "change_type": "graph_policy_changed",
                    "field": field,
                    "old": old_policy.get(field),
                    "new": new_policy.get(field),
                }
            )


def _compare_nodes(old_graph: dict[str, Any], new_graph: dict[str, Any], *, changes: list[dict[str, Any]]) -> None:
    old_nodes = {str(item.get("node_id") or ""): dict(item) for item in list(old_graph.get("nodes") or []) if isinstance(item, dict)}
    new_nodes = {str(item.get("node_id") or ""): dict(item) for item in list(new_graph.get("nodes") or []) if isinstance(item, dict)}
    for node_id in sorted(set(new_nodes).difference(old_nodes)):
        changes.append({"change_type": "node_added", "node_id": node_id, "new": {"label": new_nodes[node_id].get("label"), "kind": new_nodes[node_id].get("kind")}})
    for node_id in sorted(set(old_nodes).difference(new_nodes)):
        changes.append({"change_type": "node_removed", "node_id": node_id, "old": {"label": old_nodes[node_id].get("label"), "kind": old_nodes[node_id].get("kind")}})
    for node_id in sorted(set(old_nodes).intersection(new_nodes)):
        old_node = old_nodes[node_id]
        new_node = new_nodes[node_id]
        _compare_field_group("node_routing_changed", node_id, old_node.get("routing"), new_node.get("routing"), changes=changes)
        _compare_field_group("node_prompt_changed", node_id, old_node.get("prompt"), new_node.get("prompt"), changes=changes)
        _compare_field_group("node_tools_changed", node_id, old_node.get("tools"), new_node.get("tools"), changes=changes)
        _compare_field_group("node_output_changed", node_id, old_node.get("output_contract"), new_node.get("output_contract"), changes=changes)
        _compare_field_group("node_execution_changed", node_id, old_node.get("execution"), new_node.get("execution"), changes=changes)
        _compare_field_group("node_safety_changed", node_id, old_node.get("safety"), new_node.get("safety"), changes=changes)


def _compare_edges(old_graph: dict[str, Any], new_graph: dict[str, Any], *, changes: list[dict[str, Any]]) -> None:
    old_edges = {str(item.get("edge_id") or ""): dict(item) for item in list(old_graph.get("edges") or []) if isinstance(item, dict)}
    new_edges = {str(item.get("edge_id") or ""): dict(item) for item in list(new_graph.get("edges") or []) if isinstance(item, dict)}
    for edge_id in sorted(set(new_edges).difference(old_edges)):
        changes.append({"change_type": "edge_added", "edge_id": edge_id, "new": {"from": new_edges[edge_id].get("from_node_id"), "to": new_edges[edge_id].get("to_node_id")}})
    for edge_id in sorted(set(old_edges).difference(new_edges)):
        changes.append({"change_type": "edge_removed", "edge_id": edge_id, "old": {"from": old_edges[edge_id].get("from_node_id"), "to": old_edges[edge_id].get("to_node_id")}})
    for edge_id in sorted(set(old_edges).intersection(new_edges)):
        old_edge = old_edges[edge_id]
        new_edge = new_edges[edge_id]
        if old_edge.get("edge_type") != new_edge.get("edge_type"):
            changes.append({"change_type": "edge_type_changed", "edge_id": edge_id, "old": old_edge.get("edge_type"), "new": new_edge.get("edge_type")})
        _compare_field_group("edge_handoff_changed", edge_id, old_edge.get("handoff_contract"), new_edge.get("handoff_contract"), changes=changes, id_field="edge_id")
        _compare_field_group("edge_context_policy_changed", edge_id, old_edge.get("context_policy"), new_edge.get("context_policy"), changes=changes, id_field="edge_id")


def _compare_field_group(change_type: str, item_id: str, old_value: Any, new_value: Any, *, changes: list[dict[str, Any]], id_field: str = "node_id") -> None:
    if _stable_json(old_value) == _stable_json(new_value):
        return
    changes.append(
        {
            "change_type": change_type,
            id_field: item_id,
            "old": deepcopy(old_value),
            "new": deepcopy(new_value),
        }
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _promote_status(current: str, next_status: str) -> str:
    rank = {"pass": 0, "warning": 1, "blocked": 2}
    return next_status if rank.get(next_status, 0) > rank.get(current, 0) else current


def _render_lint_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Orchestration Graph Lint",
        "",
        f"- File: `{report.get('file_path')}`",
        f"- Graph ID: `{report.get('graph_id')}`",
        f"- Status: `{report.get('status')}`",
        f"- Schema version: `{report.get('graph_schema_version')}`",
        f"- Node count: `{report.get('node_count')}`",
        f"- Edge count: `{report.get('edge_count')}`",
        f"- Lowering: `{dict(report.get('lowering') or {}).get('status')}` into `{dict(report.get('lowering') or {}).get('task_graph_schema_version')}`",
    ]
    return "\n".join(lines).strip() + "\n"


def _render_dry_run_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Orchestration Graph Dry Run",
        "",
        f"- File: `{report.get('file_path')}`",
        f"- Graph ID: `{report.get('graph_id')}`",
        f"- Status: `{report.get('status')}`",
        f"- Blocking count: `{dict(report.get('summary') or {}).get('blocking_count')}`",
        f"- Warning count: `{dict(report.get('summary') or {}).get('warning_count')}`",
        "",
        "## Nodes",
    ]
    for item in list(report.get("node_results") or []):
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('node_id')}` / `{item.get('status')}`")
        for reason in list(item.get("reasons") or []):
            lines.append(f"  - {reason}")
    lines.extend(["", "## Edges"])
    for item in list(report.get("edge_results") or []):
        if not isinstance(item, dict):
            continue
        lines.append(f"- `{item.get('edge_id')}` / `{item.get('status')}`")
        for reason in list(item.get("reasons") or []):
            lines.append(f"  - {reason}")
    return "\n".join(lines).strip() + "\n"


def _render_compile_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Orchestration Graph Compile",
        "",
        f"- File: `{report.get('file_path')}`",
        f"- Graph ID: `{report.get('graph_id')}`",
        f"- Status: `{report.get('status')}`",
        f"- Node count: `{dict(report.get('summary') or {}).get('node_count')}`",
        f"- Edge count: `{dict(report.get('summary') or {}).get('edge_count')}`",
        f"- Parallel group count: `{dict(report.get('summary') or {}).get('parallel_group_count')}`",
        f"- Approval node count: `{dict(report.get('summary') or {}).get('approval_node_count')}`",
        "",
        "## Lowering",
        f"- Task graph schema version: `{dict(report.get('lowering') or {}).get('task_graph_schema_version')}`",
        f"- Template ID: `{dict(report.get('lowering') or {}).get('template_id')}`",
    ]
    return "\n".join(lines).strip() + "\n"


def _render_diff_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Orchestration Graph Diff",
        "",
        f"- Old file: `{report.get('old_file_path')}`",
        f"- New file: `{report.get('new_file_path')}`",
        f"- Status: `{report.get('status')}`",
        f"- Change count: `{dict(report.get('summary') or {}).get('change_count')}`",
        "",
        "## Changes",
    ]
    for item in list(report.get("changes") or []):
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("node_id") or item.get("edge_id") or item.get("field") or "").strip()
        lines.append(f"- `{item.get('change_type')}` `{identifier}`")
    return "\n".join(lines).strip() + "\n"


def _render_migrate_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Orchestration Graph Migration",
        "",
        f"- Source file: `{report.get('source_file_path')}`",
        f"- Source graph ID: `{report.get('source_graph_id')}`",
        f"- Source schema version: `{report.get('source_schema_version')}`",
        f"- Target graph ID: `{report.get('graph_id')}`",
        f"- Target schema version: `{report.get('graph_schema_version')}`",
        f"- Warning count: `{report.get('warning_count')}`",
        f"- Output path: `{report.get('output_path')}`",
    ]
    return "\n".join(lines).strip() + "\n"
