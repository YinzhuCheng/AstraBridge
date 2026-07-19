from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .agent_orchestration_compiler import compile_agent_orchestration_graph
from .agent_orchestration_contract import (
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    lower_agent_orchestration_graph_to_task_graph,
    validate_agent_orchestration_graph,
)


DEFAULT_METADATA_CREATED_AT = "2026-07-07T00:00:00+09:00"
DEFAULT_METADATA_UPDATED_AT = "2026-07-07T00:05:00+09:00"
DEFAULT_COMPILED_TASK_GRAPH_VERSION = "astrabridge-task-graph-v1"
DEFAULT_COMPATIBILITY_NOTES = (
    "Canonical graphs remain the source of truth for GUI, code, dry-run, and runtime work.",
    "Lowering into legacy task graphs is a compatibility shim while the generic scheduler is still under construction.",
)


def _deepcopy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return deepcopy(dict(value or {}))


@dataclass(slots=True)
class CapabilityClaimsSpec:
    input_port_types: Sequence[str] = ()
    output_port_types: Sequence[str] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "input_port_types": [str(item) for item in self.input_port_types],
            "output_port_types": [str(item) for item in self.output_port_types],
        }


@dataclass(slots=True)
class RoutingSpec:
    selection_mode: str = "none"
    provider_id: str | None = None
    model_id: str | None = None
    profile_id: str | None = None
    capability_claims: CapabilityClaimsSpec | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"selection_mode": self.selection_mode}
        if self.provider_id:
            payload["provider_id"] = self.provider_id
        if self.model_id:
            payload["model_id"] = self.model_id
        if self.profile_id:
            payload["profile_id"] = self.profile_id
        if self.capability_claims is not None:
            payload["capability_claims"] = self.capability_claims.to_payload()
        return payload


@dataclass(slots=True)
class PromptSpec:
    template: str
    template_mode: str = "inline"

    def to_payload(self) -> dict[str, Any]:
        return {
            "template_mode": self.template_mode,
            "template": self.template,
        }


@dataclass(slots=True)
class ToolsSpec:
    approval_mode: str = "ask"
    allowed_tool_classes: Sequence[str] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "approval_mode": self.approval_mode,
            "allowed_tool_classes": [str(item) for item in self.allowed_tool_classes],
        }


@dataclass(slots=True)
class PortSpec:
    port_id: str
    label: str
    port_type: str
    shape: str = "single"
    required: bool = True
    schema_ref: str | None = None
    artifact_kind: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "port_id": self.port_id,
            "label": self.label,
            "port_type": self.port_type,
            "shape": self.shape,
            "required": self.required,
        }
        if self.schema_ref is not None:
            payload["schema_ref"] = self.schema_ref
        if self.artifact_kind is not None:
            payload["artifact_kind"] = self.artifact_kind
        return payload


@dataclass(slots=True)
class InputContractSpec:
    mode: str
    port_ids: Sequence[str]

    def to_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "port_ids": [str(item) for item in self.port_ids],
        }


@dataclass(slots=True)
class ArtifactSpec:
    kind: str
    id: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
        }


@dataclass(slots=True)
class OutputContractSpec:
    mode: str
    machine_result_schema_ref: str | None = None
    artifact_specs: Sequence[ArtifactSpec] = ()
    human_summary_required: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "machine_result_schema_ref": self.machine_result_schema_ref,
            "artifact_specs": [item.to_payload() for item in self.artifact_specs],
            "human_summary_required": self.human_summary_required,
        }


@dataclass(slots=True)
class RetryPolicySpec:
    max_attempts: int = 1

    def to_payload(self) -> dict[str, Any]:
        return {"max_attempts": self.max_attempts}


@dataclass(slots=True)
class SubagentPolicySpec:
    isolation_mode: str = "lane"
    max_turns: int = 8
    allow_direct_teammate_messages: bool = False
    share_worktree: bool = False
    allow_nested_subagents: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "isolation_mode": self.isolation_mode,
            "max_turns": self.max_turns,
            "allow_direct_teammate_messages": self.allow_direct_teammate_messages,
            "share_worktree": self.share_worktree,
            "allow_nested_subagents": self.allow_nested_subagents,
        }


@dataclass(slots=True)
class ExecutionSpec:
    spawn_mode: str
    timeout_ms: int
    retry_policy: RetryPolicySpec = field(default_factory=RetryPolicySpec)
    execution_backend: str = "app_server"
    collaboration_mode: str = "default"
    subagent_policy: SubagentPolicySpec | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "spawn_mode": self.spawn_mode,
            "timeout_ms": self.timeout_ms,
            "retry_policy": self.retry_policy.to_payload(),
            "execution_backend": self.execution_backend,
            "collaboration_mode": self.collaboration_mode,
            "subagent_policy": self.subagent_policy.to_payload() if self.subagent_policy is not None else None,
        }


@dataclass(slots=True)
class SafetySpec:
    risk_class: str
    allow_provider_calls: bool
    allow_code_changes: bool
    allow_install: bool
    requires_human_approval: bool
    approval_kind: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "risk_class": self.risk_class,
            "allow_provider_calls": self.allow_provider_calls,
            "allow_code_changes": self.allow_code_changes,
            "allow_install": self.allow_install,
            "requires_human_approval": self.requires_human_approval,
        }
        if self.approval_kind is not None:
            payload["approval_kind"] = self.approval_kind
        return payload


@dataclass(slots=True)
class PositionSpec:
    x: int
    y: int

    def to_payload(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass(slots=True)
class UiSpec:
    position: PositionSpec
    layout_mode: str = "canvas"

    def to_payload(self) -> dict[str, Any]:
        return {
            "position": self.position.to_payload(),
            "layout_mode": self.layout_mode,
        }


@dataclass(slots=True)
class NodeSpec:
    node_id: str
    kind: str
    label: str
    role: str
    card_ref: str
    routing: RoutingSpec
    prompt: PromptSpec
    tools: ToolsSpec
    inputs: Sequence[PortSpec]
    outputs: Sequence[PortSpec]
    input_contract: InputContractSpec
    output_contract: OutputContractSpec
    execution: ExecutionSpec
    safety: SafetySpec
    ui: UiSpec
    status: str = "ready"

    def to_payload(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "label": self.label,
            "role": self.role,
            "card_ref": self.card_ref,
            "routing": self.routing.to_payload(),
            "prompt": self.prompt.to_payload(),
            "tools": self.tools.to_payload(),
            "ports": {
                "inputs": [item.to_payload() for item in self.inputs],
                "outputs": [item.to_payload() for item in self.outputs],
            },
            "input_contract": self.input_contract.to_payload(),
            "output_contract": self.output_contract.to_payload(),
            "execution": self.execution.to_payload(),
            "safety": self.safety.to_payload(),
            "ui": self.ui.to_payload(),
            "status": self.status,
        }


@dataclass(slots=True)
class PortBindingSpec:
    from_port_id: str
    to_port_id: str

    def to_payload(self) -> dict[str, str]:
        return {
            "from_port_id": self.from_port_id,
            "to_port_id": self.to_port_id,
        }


@dataclass(slots=True)
class HandoffContractSpec:
    message_template: str
    required_output_schema_refs: Sequence[str]
    port_bindings: Sequence[PortBindingSpec]
    message_part_modes: Sequence[str] = ("machine_result", "human_summary")

    def to_payload(self) -> dict[str, Any]:
        return {
            "message_template": self.message_template,
            "message_part_modes": [str(item) for item in self.message_part_modes],
            "required_output_schema_refs": [str(item) for item in self.required_output_schema_refs],
            "port_bindings": [item.to_payload() for item in self.port_bindings],
        }


@dataclass(slots=True)
class ContextPolicySpec:
    policy_id: str
    history_mode: str = "latest_summary_only"
    artifact_mode: str = "required_output_only"
    exclude_private_memory: bool = True
    include_machine_results: bool = True
    include_human_summaries: bool = True
    summary_strategy: str = "human_and_machine"
    history_length: int | None = None
    resource_refs: Sequence[str] = ()
    included_artifacts: Sequence[str] = ()

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "policy_id": self.policy_id,
            "history_mode": self.history_mode,
            "artifact_mode": self.artifact_mode,
            "exclude_private_memory": self.exclude_private_memory,
            "include_machine_results": self.include_machine_results,
            "include_human_summaries": self.include_human_summaries,
            "summary_strategy": self.summary_strategy,
        }
        if self.history_length is not None:
            payload["history_length"] = self.history_length
        if self.resource_refs:
            payload["resource_refs"] = [str(item) for item in self.resource_refs]
        if self.included_artifacts:
            payload["included_artifacts"] = [str(item) for item in self.included_artifacts]
        return payload


@dataclass(slots=True)
class EdgeSpec:
    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_type: str
    handoff_contract: HandoffContractSpec
    context_policy: ContextPolicySpec
    ui: UiSpec
    status: str = "ready"

    def to_payload(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type,
            "handoff_contract": self.handoff_contract.to_payload(),
            "context_policy": self.context_policy.to_payload(),
            "ui": self.ui.to_payload(),
            "status": self.status,
        }


@dataclass(slots=True)
class GraphMetadataSpec:
    description: str
    tags: Sequence[str] = ()
    owners: Sequence[str] = ()
    created_at: str = DEFAULT_METADATA_CREATED_AT
    updated_at: str = DEFAULT_METADATA_UPDATED_AT

    def to_payload(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "tags": [str(item) for item in self.tags],
            "owners": [str(item) for item in self.owners],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(slots=True)
class GraphPolicySpec:
    entry_node_ids: Sequence[str]
    max_depth: int = 2
    default_permission_mode: str = "ask"
    default_collaboration_mode: str = "default"
    default_execution_backend: str = "app_server"
    requires_dry_run_before_live: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "entry_node_ids": [str(item) for item in self.entry_node_ids],
            "max_depth": self.max_depth,
            "default_permission_mode": self.default_permission_mode,
            "default_collaboration_mode": self.default_collaboration_mode,
            "default_execution_backend": self.default_execution_backend,
            "requires_dry_run_before_live": self.requires_dry_run_before_live,
        }


@dataclass(slots=True)
class CompatibilitySpec:
    lowering_mode: str = "lossy_legacy_task_graph"
    preserves_unknown_fields: bool = False
    notes: Sequence[str] = DEFAULT_COMPATIBILITY_NOTES

    def to_payload(self) -> dict[str, Any]:
        return {
            "lowering_mode": self.lowering_mode,
            "preserves_unknown_fields": self.preserves_unknown_fields,
            "notes": [str(item) for item in self.notes],
        }


@dataclass(slots=True)
class MigrationSpec:
    source_kind: str = "native_authoring"
    compiled_task_graph_version: str = DEFAULT_COMPILED_TASK_GRAPH_VERSION
    compatibility: CompatibilitySpec = field(default_factory=CompatibilitySpec)

    def to_payload(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "compiled_task_graph_version": self.compiled_task_graph_version,
            "compatibility": self.compatibility.to_payload(),
        }


@dataclass(slots=True)
class AgentOrchestrationGraphBuilder:
    graph_id: str
    task_id: str
    title: str
    metadata: GraphMetadataSpec
    graph_policy: GraphPolicySpec
    template_id: str = ""
    status: str = "ready"
    state_version: int = 1
    migration: MigrationSpec = field(default_factory=MigrationSpec)
    prompt_registry: Mapping[str, Any] | None = None
    external_agent_card_registry: Mapping[str, Any] | None = None
    nodes: list[NodeSpec] = field(default_factory=list)
    edges: list[EdgeSpec] = field(default_factory=list)
    schema_registry: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: NodeSpec) -> AgentOrchestrationGraphBuilder:
        self.nodes.append(node)
        return self

    def add_edge(self, edge: EdgeSpec) -> AgentOrchestrationGraphBuilder:
        self.edges.append(edge)
        return self

    def register_schema(self, schema_ref: str, schema: Mapping[str, Any]) -> AgentOrchestrationGraphBuilder:
        self.schema_registry[str(schema_ref)] = _deepcopy_mapping(schema)
        return self

    def build(self) -> dict[str, Any]:
        payload = self._build_payload()
        validate_agent_orchestration_graph(payload)
        return payload

    def _build_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": AGENT_ORCHESTRATION_SCHEMA_VERSION,
            "graph_id": self.graph_id,
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "metadata": self.metadata.to_payload(),
            "graph_policy": self.graph_policy.to_payload(),
            "nodes": [item.to_payload() for item in self.nodes],
            "edges": [item.to_payload() for item in self.edges],
            "schema_registry": _deepcopy_mapping(self.schema_registry),
            "migration": self.migration.to_payload(),
            "state_version": self.state_version,
        }
        if self.template_id:
            payload["template_id"] = self.template_id
        if self.prompt_registry:
            payload["prompt_registry"] = _deepcopy_mapping(self.prompt_registry)
        if self.external_agent_card_registry:
            payload["external_agent_card_registry"] = _deepcopy_mapping(self.external_agent_card_registry)
        return payload

    def compile(self, **kwargs: Any) -> dict[str, Any]:
        return compile_agent_orchestration_graph(self.build(), **kwargs)

    def lower_to_task_graph(self) -> dict[str, Any]:
        return lower_agent_orchestration_graph_to_task_graph(self.build())

    def to_json(self) -> str:
        return json.dumps(self.build(), ensure_ascii=False, indent=2) + "\n"

    def write_json(self, path: str | Path) -> Path:
        file_path = Path(path)
        if file_path.suffix.lower() != ".json":
            raise ValueError("Python SDK graph output path must use the .json extension.")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(self.to_json(), encoding="utf-8")
        return file_path
