"""Typed handoff and communication-isolation admission for agent graphs.

This module is a policy validator only.  It does not create envelopes, move
artifacts, call providers, or introduce another message protocol.  The graph
handoff contract remains the source of truth; this validator proves that the
declared contract is safe to project into the existing AstraBridge protocol
envelope at both skill resolution and live-run admission.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

from .agent_orchestration_contract import (
    MESSAGE_PART_MODES,
    validate_agent_orchestration_graph,
)
from .security import DESKTOP_KEY_PATH_RE, SECRET_RE, redact_sensitive
from .task_graph_contract import ARTIFACT_MODES, HISTORY_MODES


COMMUNICATION_ISOLATION_SCHEMA_VERSION = "astrabridge-communication-isolation-decision-v1"
COMMUNICATION_ISOLATION_VALIDATOR_VERSION = "astrabridge-typed-handoff-isolation-v1"

_UNSAFE_HISTORY_MODES = {"all", "full", "full_history", "unrestricted", "transcript", "conversation"}
_UNSAFE_MARKER_RE = re.compile(
    r"(?i)(?:private[\s_-]*(?:memory|reasoning)|provider[\s_-]*private|raw[\s_-]*(?:prompt|transcript|response)|full[\s_-]*history|conversation[\s_-]*history)"
)
_DIRECT_MESSAGE_KEYS = {
    "allow_direct_teammate_messages",
    "allow_direct_messages",
    "direct_teammate_messages",
    "direct_messages",
}
_PRIVATE_BOUNDARY_KEYS = {
    "private_memory",
    "private_reasoning",
    "provider_private_reasoning",
    "raw_prompt",
    "raw_transcript",
    "raw_response",
    "full_history",
    "conversation_history",
}


def validate_typed_communication_isolation(
    graph: dict[str, Any],
    compiled_plan: dict[str, Any] | None = None,
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Return a deterministic, redacted admission decision for graph handoffs.

    The result is intentionally a decision/report rather than a replacement
    envelope.  A caller must treat ``status=blocked`` as fail-closed before
    provider or MCP admission.
    """

    blockers: list[str] = []
    warnings: list[str] = []
    edge_results: list[dict[str, Any]] = []
    canonical: dict[str, Any] | None = None
    graph_id = ""
    task_id = ""
    try:
        if not isinstance(graph, dict):
            raise TypeError("graph must be an object")
        graph_id = str(graph.get("graph_id") or "").strip()
        task_id = str(graph.get("task_id") or "").strip()
        # Reuse the canonical graph validator.  It owns schema, port, output
        # schema, and graph topology validation; this module adds isolation
        # invariants that are intentionally not encoded in the envelope.
        canonical = validate_agent_orchestration_graph(deepcopy(graph))
        graph_id = str(canonical.get("graph_id") or graph_id).strip()
        task_id = str(canonical.get("task_id") or task_id).strip()
    except Exception as exc:  # fail closed without echoing graph contents
        blockers.append(
            "canonical_graph_validation_failed: "
            f"{type(exc).__name__}: {redact_sensitive(str(exc))}"
        )
        # Continue with a redacted structural inspection so callers receive
        # the isolation-specific reason as well (for example full-history or
        # private-memory widening), even when the schema owner rejects the
        # same graph earlier.  The raw graph is never copied into the result.
        if isinstance(graph, dict):
            canonical = deepcopy(graph)

    node_map = {
        str(item.get("node_id") or "").strip(): dict(item)
        for item in list((canonical or {}).get("nodes") or [])
        if isinstance(item, dict) and str(item.get("node_id") or "").strip()
    }
    edges = [item for item in list((canonical or {}).get("edges") or []) if isinstance(item, dict)]
    incoming_targets: dict[str, set[str]] = {node_id: set() for node_id in node_map}
    for edge in edges:
        result = _validate_edge(edge, node_map=node_map, schema_registry=dict((canonical or {}).get("schema_registry") or {}), strict=strict)
        edge_results.append(result)
        blockers.extend(str(item) for item in result.get("blockers") or [])
        warnings.extend(str(item) for item in result.get("warnings") or [])
        target_id = str(edge.get("to_node_id") or "").strip()
        for binding in list(dict(edge.get("handoff_contract") or {}).get("port_bindings") or []):
            if isinstance(binding, dict):
                target_port_id = str(binding.get("to_port_id") or "").strip()
                if target_id and target_port_id:
                    incoming_targets.setdefault(target_id, set()).add(target_port_id)

    # Required typed inputs may only be satisfied by an explicit incoming
    # binding.  task_context is the legacy ambient input and is excluded.
    for node_id, node in node_map.items():
        ports = dict(node.get("ports") or {})
        incoming = incoming_targets.get(node_id, set())
        for port in list(ports.get("inputs") or []):
            if not isinstance(port, dict) or not bool(port.get("required")):
                continue
            port_id = str(port.get("port_id") or "").strip()
            if port_id and port_id != "task_context" and port_id not in incoming:
                blockers.append(f"node:{node_id}:required_input_port_not_bound:{port_id}")

        _validate_node_isolation(node, blockers)

    if isinstance(compiled_plan, dict):
        _validate_compiled_projection(canonical, compiled_plan, blockers)

    blockers = _unique(blockers)
    warnings = _unique(warnings)
    policy_snapshot = {
        "private_memory_excluded": not any("private_memory" in item for item in blockers),
        "direct_teammate_messages": False,
        "history_modes": sorted({str(item.get("history_mode") or "") for item in edge_results if item.get("history_mode")}),
        "artifact_modes": sorted({str(item.get("artifact_mode") or "") for item in edge_results if item.get("artifact_mode")}),
        "typed_port_edges": sum(1 for item in edge_results if item.get("typed_port_bindings")),
        "edge_count": len(edges),
    }
    status = "blocked" if blockers else "pass"
    decision: dict[str, Any] = {
        "schema_version": COMMUNICATION_ISOLATION_SCHEMA_VERSION,
        "validator_version": COMMUNICATION_ISOLATION_VALIDATOR_VERSION,
        "status": status,
        "graph_id": graph_id or None,
        "task_id": task_id or None,
        "edge_count": len(edges),
        "edge_results": edge_results,
        "policy_snapshot": policy_snapshot,
        "warnings": warnings,
        "blockers": blockers,
        "provenance": {
            "provider_calls": 0,
            "mcp_calls": 0,
            "agent_invocations": 0,
            "protocol_owner": "astrabridge_sidecar.protocol",
        },
    }
    decision["decision_digest"] = _digest(decision)
    return decision


def _validate_edge(
    edge: dict[str, Any],
    *,
    node_map: dict[str, dict[str, Any]],
    schema_registry: dict[str, Any],
    strict: bool,
) -> dict[str, Any]:
    edge_id = str(edge.get("edge_id") or "").strip() or "<edge>"
    source_id = str(edge.get("from_node_id") or "").strip()
    target_id = str(edge.get("to_node_id") or "").strip()
    handoff = dict(edge.get("handoff_contract") or {})
    context = dict(edge.get("context_policy") or {})
    edge_blockers: list[str] = []
    edge_warnings: list[str] = []
    modes = [str(item).strip() for item in list(handoff.get("message_part_modes") or []) if str(item or "").strip()]
    mode_set = set(modes)
    if not modes:
        edge_blockers.append(f"edge:{edge_id}:message_part_modes_must_not_be_empty")
    unknown_modes = sorted(mode_set.difference(MESSAGE_PART_MODES))
    if unknown_modes:
        edge_blockers.append(f"edge:{edge_id}:undeclared_message_part_modes:{','.join(unknown_modes)}")
    if len(modes) != len(mode_set):
        edge_blockers.append(f"edge:{edge_id}:duplicate_message_part_modes")
    _reject_boundary_content(handoff, f"edge:{edge_id}.handoff_contract", edge_blockers)
    _reject_boundary_content(context, f"edge:{edge_id}.context_policy", edge_blockers)

    history_mode = str(context.get("history_mode") or "").strip()
    artifact_mode = str(context.get("artifact_mode") or "").strip()
    if history_mode not in HISTORY_MODES:
        if history_mode in _UNSAFE_HISTORY_MODES:
            edge_blockers.append(f"edge:{edge_id}:unsafe_history_mode:{history_mode}")
        else:
            edge_blockers.append(f"edge:{edge_id}:unknown_history_mode:{history_mode or '<empty>'}")
    if history_mode in _UNSAFE_HISTORY_MODES:
        edge_blockers.append(f"edge:{edge_id}:unsafe_history_mode:{history_mode}")
    if history_mode == "last_n_messages":
        history_length = context.get("history_length")
        if not isinstance(history_length, int) or isinstance(history_length, bool) or history_length <= 0:
            edge_blockers.append(f"edge:{edge_id}:last_n_messages_requires_positive_history_length")
    if history_mode == "explicit_refs_only" and not list(context.get("resource_refs") or []) and not list(context.get("included_artifacts") or []):
        edge_warnings.append(f"edge:{edge_id}:explicit_refs_only_has_no_declared_refs")
    if artifact_mode not in ARTIFACT_MODES:
        edge_blockers.append(f"edge:{edge_id}:unknown_artifact_mode:{artifact_mode or '<empty>'}")
    if context.get("exclude_private_memory") is not True:
        edge_blockers.append(f"edge:{edge_id}:exclude_private_memory_must_be_true")
    if _truthy_direct_message(context) or _truthy_direct_message(handoff):
        edge_blockers.append(f"edge:{edge_id}:direct_teammate_messages_must_be_disabled")

    source = node_map.get(source_id) or {}
    target = node_map.get(target_id) or {}
    source_ports = _port_map(source, "outputs")
    target_ports = _port_map(target, "inputs")
    declared_artifacts = _declared_artifacts(source)
    included_artifacts = [str(item).strip() for item in list(context.get("included_artifacts") or []) if str(item or "").strip()]
    unknown_artifacts = sorted(
        item for item in set(included_artifacts)
        if item != "required_output" and item not in declared_artifacts
    )
    if unknown_artifacts:
        edge_blockers.append(f"edge:{edge_id}:undeclared_artifacts:{','.join(unknown_artifacts)}")
    if artifact_mode == "explicit_artifacts" and not included_artifacts:
        edge_blockers.append(f"edge:{edge_id}:explicit_artifacts_requires_included_artifacts")
    source_has_artifacts = bool(declared_artifacts)
    if artifact_mode == "required_output_only" and not source_has_artifacts and not _source_has_machine_result(source):
        edge_blockers.append(f"edge:{edge_id}:required_output_has_no_declared_source_artifact")
    if "artifact_ref" in mode_set and (artifact_mode == "none" or not source_has_artifacts):
        edge_blockers.append(f"edge:{edge_id}:artifact_ref_requires_declared_artifact_output")
    if "machine_result" in mode_set and not _source_has_machine_result(source):
        edge_blockers.append(f"edge:{edge_id}:machine_result_is_not_declared_by_source_output")
    if "structured_json" in mode_set and not any(str(port.get("port_type") or "").strip() == "structured_json" for port in source_ports.values()):
        edge_blockers.append(f"edge:{edge_id}:structured_json_is_not_declared_by_source_port")
    if "human_summary" in mode_set and context.get("include_human_summaries") is not True:
        edge_blockers.append(f"edge:{edge_id}:human_summary_requires_include_human_summaries")
    if ("machine_result" in mode_set or "structured_json" in mode_set) and context.get("include_machine_results") is not True:
        edge_blockers.append(f"edge:{edge_id}:machine_result_requires_include_machine_results")
    if "artifact_ref" in mode_set and artifact_mode == "none":
        edge_blockers.append(f"edge:{edge_id}:artifact_ref_requires_non_none_artifact_mode")

    declared_schema_refs = {
        str(item).strip()
        for item in list(handoff.get("required_output_schema_refs") or [])
        if str(item or "").strip()
    }
    source_schema_ref = str(dict(source.get("output_contract") or {}).get("machine_result_schema_ref") or "").strip()
    if source_schema_ref and source_schema_ref not in declared_schema_refs:
        edge_blockers.append(f"edge:{edge_id}:source_output_schema_ref_not_declared")
    for ref in declared_schema_refs:
        if schema_registry and ref not in schema_registry:
            edge_blockers.append(f"edge:{edge_id}:unknown_output_schema_ref:{ref}")

    bindings = list(handoff.get("port_bindings") or [])
    if not bindings:
        edge_blockers.append(f"edge:{edge_id}:typed_port_bindings_required")
    seen_targets: set[str] = set()
    typed_port_bindings: list[dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            edge_blockers.append(f"edge:{edge_id}:port_binding_must_be_object")
            continue
        from_port_id = str(binding.get("from_port_id") or "").strip()
        to_port_id = str(binding.get("to_port_id") or "").strip()
        source_port = source_ports.get(from_port_id) or {}
        target_port = target_ports.get(to_port_id) or {}
        if not source_port:
            edge_blockers.append(f"edge:{edge_id}:unknown_source_output_port:{from_port_id or '<empty>'}")
        if not target_port:
            edge_blockers.append(f"edge:{edge_id}:unknown_target_input_port:{to_port_id or '<empty>'}")
        if to_port_id in seen_targets and to_port_id:
            edge_blockers.append(f"edge:{edge_id}:duplicate_target_input_port:{to_port_id}")
        seen_targets.add(to_port_id)
        if source_port and target_port:
            source_type = str(source_port.get("port_type") or "").strip()
            target_type = str(target_port.get("port_type") or "").strip()
            source_shape = str(source_port.get("shape") or "single").strip()
            target_shape = str(target_port.get("shape") or "single").strip()
            if source_shape != target_shape:
                edge_blockers.append(f"edge:{edge_id}:port_shape_mismatch:{from_port_id}->{to_port_id}")
            # The canonical compiler allows the legacy text task_context
            # adapter.  Preserve that compatibility exception explicitly;
            # all other crossings must be type-identical.
            if source_type and target_type and source_type != target_type and not (to_port_id == "task_context" and target_type == "text"):
                edge_blockers.append(f"edge:{edge_id}:port_type_mismatch:{from_port_id}->{to_port_id}")
            typed_port_bindings.append(
                {
                    "from_port_id": from_port_id,
                    "to_port_id": to_port_id,
                    "source_port_type": source_type,
                    "target_port_type": target_type,
                    "source_schema_ref": str(source_port.get("schema_ref") or "").strip() or None,
                    "target_schema_ref": str(target_port.get("schema_ref") or "").strip() or None,
                }
            )
    return {
        "edge_id": edge_id,
        "source_node_id": source_id,
        "target_node_id": target_id,
        "status": "blocked" if edge_blockers else "pass",
        "history_mode": history_mode,
        "artifact_mode": artifact_mode,
        "message_part_modes": sorted(mode_set),
        "typed_port_bindings": typed_port_bindings,
        "declared_artifacts": sorted(declared_artifacts),
        "blockers": _unique(edge_blockers),
        "warnings": _unique(edge_warnings),
    }


def _validate_node_isolation(node: dict[str, Any], blockers: list[str]) -> None:
    node_id = str(node.get("node_id") or "").strip() or "<node>"
    if _truthy_direct_message(node):
        blockers.append(f"node:{node_id}:direct_teammate_messages_must_be_disabled")
    execution = dict(node.get("execution") or {})
    if _truthy_direct_message(execution):
        blockers.append(f"node:{node_id}:direct_teammate_messages_must_be_disabled")
    subagent = dict(execution.get("subagent_policy") or {})
    if _truthy_direct_message(subagent):
        blockers.append(f"node:{node_id}:direct_teammate_messages_must_be_disabled")
    if subagent.get("allow_nested_subagents") is True:
        blockers.append(f"node:{node_id}:nested_subagents_must_be_disabled")
    for container_name, container in (("node", node), ("execution", execution), ("subagent_policy", subagent)):
        _reject_boundary_content(container, f"node:{node_id}.{container_name}", blockers)


def _validate_compiled_projection(canonical: dict[str, Any] | None, compiled: dict[str, Any], blockers: list[str]) -> None:
    if not canonical:
        blockers.append("compiled_projection_requires_valid_canonical_graph")
        return
    if str(compiled.get("graph_id") or "").strip() != str(canonical.get("graph_id") or "").strip():
        blockers.append("compiled_projection_graph_id_mismatch")
    if str(compiled.get("task_id") or "").strip() != str(canonical.get("task_id") or "").strip():
        blockers.append("compiled_projection_task_id_mismatch")
    graph_edges = {
        str(item.get("edge_id") or "").strip(): dict(item)
        for item in list(canonical.get("edges") or [])
        if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
    }
    compiled_edges = {
        str(item.get("edge_id") or "").strip(): dict(item)
        for item in list(compiled.get("edges") or [])
        if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
    }
    if set(graph_edges) != set(compiled_edges):
        blockers.append("compiled_projection_edge_set_mismatch")
    for edge_id in sorted(set(graph_edges).intersection(compiled_edges)):
        graph_edge = graph_edges[edge_id]
        compiled_edge = compiled_edges[edge_id]
        graph_bindings = _binding_signature(list(dict(graph_edge.get("handoff_contract") or {}).get("port_bindings") or []))
        compiled_bindings = _binding_signature(list(compiled_edge.get("port_bindings") or []))
        if graph_bindings != compiled_bindings:
            blockers.append(f"compiled_projection_port_bindings_mismatch:{edge_id}")
        context = dict(graph_edge.get("context_policy") or {})
        envelope = dict(compiled_edge.get("context_envelope") or {})
        for field in ("history_mode", "artifact_mode", "include_machine_results", "include_human_summaries", "exclude_private_memory", "summary_strategy", "resource_refs", "included_artifacts"):
            graph_value = context.get(field)
            compiled_value = envelope.get(field)
            if field in {"resource_refs", "included_artifacts"}:
                graph_value = list(graph_value or [])
                compiled_value = list(compiled_value or [])
            if _stable_value(graph_value) != _stable_value(compiled_value):
                blockers.append(f"compiled_projection_context_mismatch:{edge_id}:{field}")


def _port_map(node: dict[str, Any], direction: str) -> dict[str, dict[str, Any]]:
    ports = dict(node.get("ports") or {})
    return {
        str(item.get("port_id") or "").strip(): dict(item)
        for item in list(ports.get(direction) or [])
        if isinstance(item, dict) and str(item.get("port_id") or "").strip()
    }


def _declared_artifacts(source: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for spec in list(dict(source.get("output_contract") or {}).get("artifact_specs") or []):
        if not isinstance(spec, dict):
            continue
        for key in ("id", "kind"):
            value = str(spec.get(key) or "").strip()
            if value:
                result.add(value)
    for port in _port_map(source, "outputs").values():
        for key in ("port_id", "artifact_kind"):
            value = str(port.get(key) or "").strip()
            if value:
                result.add(value)
    return result


def _source_has_machine_result(source: dict[str, Any]) -> bool:
    output_contract = dict(source.get("output_contract") or {})
    if str(output_contract.get("machine_result_schema_ref") or "").strip():
        return True
    return any(str(port.get("port_id") or "").strip() == "machine_result" for port in _port_map(source, "outputs").values())


def _truthy_direct_message(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    for key, item in value.items():
        clean = str(key or "").strip().lower()
        if clean in _DIRECT_MESSAGE_KEYS and item is True:
            return True
    return False


def _reject_boundary_content(value: Any, path: str, blockers: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            clean_key = str(key or "").strip().lower()
            if clean_key in _PRIVATE_BOUNDARY_KEYS and item not in (None, False, "", [], {}):
                blockers.append(f"{path}:private_boundary_field_not_allowed:{clean_key}")
            if clean_key in _DIRECT_MESSAGE_KEYS and item is True:
                blockers.append(f"{path}:direct_teammate_messages_must_be_disabled")
            _reject_boundary_content(item, f"{path}.{clean_key or '<key>'}", blockers)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_boundary_content(item, f"{path}[{index}]", blockers)
    elif isinstance(value, str):
        if SECRET_RE.search(value) or DESKTOP_KEY_PATH_RE.search(value) or _UNSAFE_MARKER_RE.search(value):
            blockers.append(f"{path}:provider_private_or_secret_like_content_not_allowed")


def _binding_signature(bindings: list[Any]) -> list[tuple[str, str]]:
    return sorted(
        (str(item.get("from_port_id") or "").strip(), str(item.get("to_port_id") or "").strip())
        for item in bindings
        if isinstance(item, dict)
    )


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: dict[str, Any]) -> str:
    payload = {key: value[key] for key in value if key != "decision_digest"}
    return hashlib.sha256(_stable_value(payload).encode("utf-8")).hexdigest()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))


__all__ = [
    "COMMUNICATION_ISOLATION_SCHEMA_VERSION",
    "COMMUNICATION_ISOLATION_VALIDATOR_VERSION",
    "validate_typed_communication_isolation",
]
