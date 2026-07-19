import type { AgentOrchestrationGraph } from "../../types";

export const AGENT_ORCHESTRATION_GRAPH_SCHEMA_VERSION = "astrabridge-agent-orchestration-graph-v1";

export type CapabilityClaimsSpec = {
  input_port_types?: string[];
  output_port_types?: string[];
};

export type RoutingSpec = {
  selection_mode: string;
  provider_id?: string;
  model_id?: string;
  profile_id?: string;
  capability_claims?: CapabilityClaimsSpec;
};

export type PromptSpec = {
  template_mode: string;
  template: string;
};

export type ToolsSpec = {
  approval_mode: string;
  allowed_tool_classes: string[];
};

export type PortSpec = {
  port_id: string;
  label: string;
  port_type: string;
  shape: string;
  required: boolean;
  schema_ref?: string;
  artifact_kind?: string;
};

export type InputContractSpec = {
  mode: string;
  port_ids: string[];
};

export type ArtifactSpec = {
  kind: string;
  id: string;
};

export type OutputContractSpec = {
  mode: string;
  machine_result_schema_ref: string | null;
  artifact_specs: ArtifactSpec[];
  human_summary_required: boolean;
};

export type RetryPolicySpec = {
  max_attempts: number;
};

export type SubagentPolicySpec = {
  isolation_mode: string;
  max_turns: number;
  allow_direct_teammate_messages: boolean;
  share_worktree: boolean;
  allow_nested_subagents: boolean;
};

export type ExecutionSpec = {
  spawn_mode: string;
  timeout_ms: number;
  retry_policy: RetryPolicySpec;
  execution_backend: string;
  collaboration_mode: string;
  subagent_policy: SubagentPolicySpec | null;
};

export type SafetySpec = {
  risk_class: string;
  allow_provider_calls: boolean;
  allow_code_changes: boolean;
  allow_install: boolean;
  requires_human_approval: boolean;
  approval_kind?: string;
};

export type PositionSpec = {
  x: number;
  y: number;
};

export type UiSpec = {
  position: PositionSpec;
  layout_mode: string;
};

export type NodeSpec = {
  node_id: string;
  kind: string;
  label: string;
  role: string;
  card_ref: string;
  routing: RoutingSpec;
  prompt: PromptSpec;
  tools: ToolsSpec;
  inputs: PortSpec[];
  outputs: PortSpec[];
  input_contract: InputContractSpec;
  output_contract: OutputContractSpec;
  execution: ExecutionSpec;
  safety: SafetySpec;
  ui: UiSpec;
  status?: string;
};

export type PortBindingSpec = {
  from_port_id: string;
  to_port_id: string;
};

export type HandoffContractSpec = {
  message_template: string;
  message_part_modes: string[];
  required_output_schema_refs: string[];
  port_bindings: PortBindingSpec[];
};

export type ContextPolicySpec = {
  policy_id: string;
  history_mode: string;
  artifact_mode: string;
  exclude_private_memory: boolean;
  include_machine_results: boolean;
  include_human_summaries: boolean;
  summary_strategy: string;
  history_length?: number;
  resource_refs?: string[];
  included_artifacts?: string[];
};

export type EdgeSpec = {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  edge_type: string;
  handoff_contract: HandoffContractSpec;
  context_policy: ContextPolicySpec;
  ui: UiSpec;
  status?: string;
};

export type GraphMetadataSpec = {
  description: string;
  tags: string[];
  owners: string[];
  created_at: string;
  updated_at: string;
};

export type GraphPolicySpec = {
  entry_node_ids: string[];
  max_depth: number;
  default_permission_mode: string;
  default_collaboration_mode: string;
  default_execution_backend: string;
  requires_dry_run_before_live: boolean;
};

export type CompatibilitySpec = {
  lowering_mode: string;
  preserves_unknown_fields: boolean;
  notes: string[];
};

export type MigrationSpec = {
  source_kind: string;
  compiled_task_graph_version: string;
  compatibility: CompatibilitySpec;
};

export type AgentOrchestrationGraphBuilderArgs = {
  graph_id: string;
  task_id: string;
  title: string;
  template_id?: string;
  status?: string;
  metadata: GraphMetadataSpec;
  graph_policy: GraphPolicySpec;
  migration: MigrationSpec;
  state_version?: number;
  prompt_registry?: Record<string, unknown>;
  external_agent_card_registry?: Record<string, unknown>;
};

function cloneRecord<T extends Record<string, unknown>>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function buildRouting(routing: RoutingSpec) {
  const payload: Record<string, unknown> = {
    selection_mode: routing.selection_mode,
  };
  if (routing.provider_id) payload.provider_id = routing.provider_id;
  if (routing.model_id) payload.model_id = routing.model_id;
  if (routing.profile_id) payload.profile_id = routing.profile_id;
  if (routing.capability_claims) {
    payload.capability_claims = {
      input_port_types: [...(routing.capability_claims.input_port_types ?? [])],
      output_port_types: [...(routing.capability_claims.output_port_types ?? [])],
    };
  }
  return payload;
}

function buildPort(port: PortSpec) {
  const payload: Record<string, unknown> = {
    port_id: port.port_id,
    label: port.label,
    port_type: port.port_type,
    shape: port.shape,
    required: port.required,
  };
  if (port.schema_ref !== undefined) payload.schema_ref = port.schema_ref;
  if (port.artifact_kind !== undefined) payload.artifact_kind = port.artifact_kind;
  return payload;
}

function buildNode(node: NodeSpec) {
  return {
    node_id: node.node_id,
    kind: node.kind,
    label: node.label,
    role: node.role,
    card_ref: node.card_ref,
    routing: buildRouting(node.routing),
    prompt: {
      template_mode: node.prompt.template_mode,
      template: node.prompt.template,
    },
    tools: {
      approval_mode: node.tools.approval_mode,
      allowed_tool_classes: [...node.tools.allowed_tool_classes],
    },
    ports: {
      inputs: node.inputs.map(buildPort),
      outputs: node.outputs.map(buildPort),
    },
    input_contract: {
      mode: node.input_contract.mode,
      port_ids: [...node.input_contract.port_ids],
    },
    output_contract: {
      mode: node.output_contract.mode,
      machine_result_schema_ref: node.output_contract.machine_result_schema_ref,
      artifact_specs: node.output_contract.artifact_specs.map((item) => ({
        kind: item.kind,
        id: item.id,
      })),
      human_summary_required: node.output_contract.human_summary_required,
    },
    execution: {
      spawn_mode: node.execution.spawn_mode,
      timeout_ms: node.execution.timeout_ms,
      retry_policy: {
        max_attempts: node.execution.retry_policy.max_attempts,
      },
      execution_backend: node.execution.execution_backend,
      collaboration_mode: node.execution.collaboration_mode,
      subagent_policy: node.execution.subagent_policy
        ? {
            isolation_mode: node.execution.subagent_policy.isolation_mode,
            max_turns: node.execution.subagent_policy.max_turns,
            allow_direct_teammate_messages: node.execution.subagent_policy.allow_direct_teammate_messages,
            share_worktree: node.execution.subagent_policy.share_worktree,
            allow_nested_subagents: node.execution.subagent_policy.allow_nested_subagents,
          }
        : null,
    },
    safety: {
      risk_class: node.safety.risk_class,
      allow_provider_calls: node.safety.allow_provider_calls,
      allow_code_changes: node.safety.allow_code_changes,
      allow_install: node.safety.allow_install,
      requires_human_approval: node.safety.requires_human_approval,
      ...(node.safety.approval_kind ? { approval_kind: node.safety.approval_kind } : {}),
    },
    ui: {
      position: {
        x: node.ui.position.x,
        y: node.ui.position.y,
      },
      layout_mode: node.ui.layout_mode,
    },
    status: node.status ?? "ready",
  };
}

function buildEdge(edge: EdgeSpec) {
  const contextPolicy: Record<string, unknown> = {
    policy_id: edge.context_policy.policy_id,
    history_mode: edge.context_policy.history_mode,
    artifact_mode: edge.context_policy.artifact_mode,
    exclude_private_memory: edge.context_policy.exclude_private_memory,
    include_machine_results: edge.context_policy.include_machine_results,
    include_human_summaries: edge.context_policy.include_human_summaries,
    summary_strategy: edge.context_policy.summary_strategy,
  };
  if (edge.context_policy.history_length !== undefined) {
    contextPolicy.history_length = edge.context_policy.history_length;
  }
  if (edge.context_policy.resource_refs?.length) {
    contextPolicy.resource_refs = [...edge.context_policy.resource_refs];
  }
  if (edge.context_policy.included_artifacts?.length) {
    contextPolicy.included_artifacts = [...edge.context_policy.included_artifacts];
  }
  return {
    edge_id: edge.edge_id,
    from_node_id: edge.from_node_id,
    to_node_id: edge.to_node_id,
    edge_type: edge.edge_type,
    handoff_contract: {
      message_template: edge.handoff_contract.message_template,
      message_part_modes: [...edge.handoff_contract.message_part_modes],
      required_output_schema_refs: [...edge.handoff_contract.required_output_schema_refs],
      port_bindings: edge.handoff_contract.port_bindings.map((item) => ({
        from_port_id: item.from_port_id,
        to_port_id: item.to_port_id,
      })),
    },
    context_policy: contextPolicy,
    ui: {
      position: {
        x: edge.ui.position.x,
        y: edge.ui.position.y,
      },
      layout_mode: edge.ui.layout_mode,
    },
    status: edge.status ?? "ready",
  };
}

export class AgentOrchestrationGraphBuilder {
  private readonly args: AgentOrchestrationGraphBuilderArgs;
  private readonly nodes: NodeSpec[] = [];
  private readonly edges: EdgeSpec[] = [];
  private readonly schemaRegistry: Record<string, unknown> = {};

  constructor(args: AgentOrchestrationGraphBuilderArgs) {
    this.args = args;
  }

  addNode(node: NodeSpec) {
    this.nodes.push(node);
    return this;
  }

  addEdge(edge: EdgeSpec) {
    this.edges.push(edge);
    return this;
  }

  registerSchema(schemaRef: string, schema: Record<string, unknown>) {
    this.schemaRegistry[schemaRef] = cloneRecord(schema);
    return this;
  }

  build(): AgentOrchestrationGraph {
    const graph = {
      schema_version: AGENT_ORCHESTRATION_GRAPH_SCHEMA_VERSION,
      graph_id: this.args.graph_id,
      task_id: this.args.task_id,
      title: this.args.title,
      ...(this.args.template_id ? { template_id: this.args.template_id } : {}),
      status: this.args.status ?? "ready",
      metadata: {
        description: this.args.metadata.description,
        tags: [...this.args.metadata.tags],
        owners: [...this.args.metadata.owners],
        created_at: this.args.metadata.created_at,
        updated_at: this.args.metadata.updated_at,
      },
      graph_policy: {
        entry_node_ids: [...this.args.graph_policy.entry_node_ids],
        max_depth: this.args.graph_policy.max_depth,
        default_permission_mode: this.args.graph_policy.default_permission_mode,
        default_collaboration_mode: this.args.graph_policy.default_collaboration_mode,
        default_execution_backend: this.args.graph_policy.default_execution_backend,
        requires_dry_run_before_live: this.args.graph_policy.requires_dry_run_before_live,
      },
      nodes: this.nodes.map(buildNode),
      edges: this.edges.map(buildEdge),
      schema_registry: cloneRecord(this.schemaRegistry),
      ...(this.args.prompt_registry ? { prompt_registry: cloneRecord(this.args.prompt_registry) } : {}),
      ...(this.args.external_agent_card_registry
        ? { external_agent_card_registry: cloneRecord(this.args.external_agent_card_registry) }
        : {}),
      migration: {
        source_kind: this.args.migration.source_kind,
        compiled_task_graph_version: this.args.migration.compiled_task_graph_version,
        compatibility: {
          lowering_mode: this.args.migration.compatibility.lowering_mode,
          preserves_unknown_fields: this.args.migration.compatibility.preserves_unknown_fields,
          notes: [...this.args.migration.compatibility.notes],
        },
      },
      state_version: this.args.state_version ?? 1,
    } satisfies AgentOrchestrationGraph;
    return graph;
  }

  toJson() {
    return `${JSON.stringify(this.build(), null, 2)}\n`;
  }
}

export function buildCustomBlankGraphFixture(taskId = "task_example") {
  const builder = new AgentOrchestrationGraphBuilder({
    graph_id: "graph_custom_blank_graph_v1",
    task_id: taskId,
    title: "Custom Blank Graph",
    template_id: "custom_blank_graph",
    metadata: {
      description: "Custom Blank Graph",
      tags: ["custom", "blank", "starter"],
      owners: [],
      created_at: "2026-07-07T00:00:00+09:00",
      updated_at: "2026-07-07T00:05:00+09:00",
    },
    graph_policy: {
      entry_node_ids: ["node_start_here"],
      max_depth: 2,
      default_permission_mode: "ask",
      default_collaboration_mode: "default",
      default_execution_backend: "app_server",
      requires_dry_run_before_live: true,
    },
    migration: {
      source_kind: "native_authoring",
      compiled_task_graph_version: "astrabridge-task-graph-v1",
      compatibility: {
        lowering_mode: "lossy_legacy_task_graph",
        preserves_unknown_fields: false,
        notes: [
          "Canonical graphs remain the source of truth for GUI, code, dry-run, and runtime work.",
          "Lowering into legacy task graphs is a compatibility shim while the generic scheduler is still under construction.",
        ],
      },
    },
  });

  builder.registerSchema("schema.blank_entry", {
    type: "object",
    required: ["goal", "next_nodes"],
  });

  builder.addNode({
    node_id: "node_start_here",
    kind: "artifact_source",
    label: "Start Here",
    role: "custom",
    card_ref: "agent_card_blank_entry",
    routing: {
      selection_mode: "none",
    },
    prompt: {
      template_mode: "inline",
      template: "Use this starter node as the seed for a custom graph.",
    },
    tools: {
      approval_mode: "ask",
      allowed_tool_classes: [],
    },
    inputs: [
      {
        port_id: "task_context",
        label: "Task Context",
        port_type: "text",
        shape: "single",
        required: true,
      },
    ],
    outputs: [
      {
        port_id: "machine_result",
        label: "Machine Result",
        port_type: "structured_json",
        shape: "single",
        required: true,
        schema_ref: "schema.blank_entry",
      },
    ],
    input_contract: {
      mode: "task_context_and_typed_ports",
      port_ids: ["task_context"],
    },
    output_contract: {
      mode: "structured_only",
      machine_result_schema_ref: "schema.blank_entry",
      artifact_specs: [],
      human_summary_required: true,
    },
    execution: {
      spawn_mode: "inline_lane",
      timeout_ms: 60000,
      retry_policy: {
        max_attempts: 1,
      },
      execution_backend: "app_server",
      collaboration_mode: "default",
      subagent_policy: null,
    },
    safety: {
      risk_class: "low",
      allow_provider_calls: false,
      allow_code_changes: false,
      allow_install: false,
      requires_human_approval: false,
    },
    ui: {
      position: {
        x: 140,
        y: 200,
      },
      layout_mode: "canvas",
    },
  });

  return builder;
}
