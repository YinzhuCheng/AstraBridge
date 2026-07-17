import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TaskGraphWorkspace } from "./TaskGraphWorkspace";
import type {
  NodeTypeRegistrySnapshot,
  TaskGraphDefinition,
  TaskGraphDryRunResult,
  TaskGraphRunRef,
  TaskGraphTemplateSummary,
} from "../../types";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

const templates: TaskGraphTemplateSummary[] = [
  {
    template_id: "fanout_fanin_research",
    title: "Fan-out / Fan-in Research",
    summary:
      "One planner fans out bounded research branches and one synthesizer merges their artifacts.",
    node_count: 4,
    edge_count: 4,
    entry_node_ids: ["node_supervisor"],
    node_kinds: ["supervisor", "worker", "worker", "synthesizer"],
    recommended_provider_ids: ["qwen", "kimi"],
    recommended_model_ids: ["qwen3-coder-plus", "kimi-k2.6"],
    artifact_expectations: [
      "Branch research notes",
      "Merge summary",
      "Attributed branch outputs",
    ],
    validation_hints: [
      "Validate every fan-out edge policy.",
      "Keep branch outputs bounded before merge.",
    ],
    constraints: [
      "Parallel branch lanes.",
      "Synthesizer consumes declared artifacts only.",
    ],
    preview_graph: {
      title: "Fan-out / Fan-in Research",
      nodes: [
        {
          node_id: "node_supervisor",
          kind: "supervisor",
          label: "Research Planner",
          position: { x: 80, y: 160 },
        },
        {
          node_id: "node_research_a",
          kind: "worker",
          label: "Research Branch A",
          position: { x: 300, y: 80 },
        },
        {
          node_id: "node_research_b",
          kind: "worker",
          label: "Research Branch B",
          position: { x: 300, y: 240 },
        },
        {
          node_id: "node_merge",
          kind: "synthesizer",
          label: "Research Synthesizer",
          position: { x: 560, y: 160 },
        },
      ],
      edges: [
        {
          edge_id: "edge_plan_a",
          from_node_id: "node_supervisor",
          to_node_id: "node_research_a",
          edge_type: "fanout_branch",
        },
        {
          edge_id: "edge_plan_b",
          from_node_id: "node_supervisor",
          to_node_id: "node_research_b",
          edge_type: "fanout_branch",
        },
      ],
    },
  },
  {
    template_id: "provider_update_smoke_gate",
    title: "Provider Update / Smoke / Gate",
    summary:
      "Metadata discovery, smoke validation, and manual promotion gate for provider updates.",
    node_count: 3,
    edge_count: 2,
    entry_node_ids: ["node_discover"],
    node_kinds: ["extractor", "validator", "gate"],
    recommended_provider_ids: ["qwen", "glm"],
    recommended_model_ids: ["qwen3-coder-plus", "glm-4.5"],
    artifact_expectations: [
      "Provider diff bundle",
      "Smoke matrix",
      "Promotion decision record",
    ],
    validation_hints: [
      "Dry-run should surface blocked provider cases.",
      "Promotion remains gated until review.",
    ],
    constraints: [
      "Human approval before promotion.",
      "No silent external writeback.",
    ],
    preview_graph: {
      title: "Provider Update / Smoke / Gate",
      nodes: [
        {
          node_id: "node_discover",
          kind: "extractor",
          label: "Discover",
          position: { x: 80, y: 160 },
        },
        {
          node_id: "node_smoke",
          kind: "validator",
          label: "Smoke",
          position: { x: 320, y: 160 },
        },
      ],
      edges: [
        {
          edge_id: "edge_discover_smoke",
          from_node_id: "node_discover",
          to_node_id: "node_smoke",
          edge_type: "artifact_handoff",
        },
      ],
    },
  },
  {
    template_id: "custom_blank_graph",
    title: "Custom Blank Graph",
    summary:
      "Minimal starter graph with one neutral entry node for custom orchestration authoring.",
    node_count: 1,
    edge_count: 0,
    entry_node_ids: ["node_start_here"],
    node_kinds: ["artifact_source"],
    recommended_provider_ids: ["qwen"],
    recommended_model_ids: ["qwen3-coder-plus"],
    artifact_expectations: ["Starter graph manifest"],
    validation_hints: ["Rename the seed node before dry-run."],
    constraints: [
      "Treat this as an authoring scaffold, not a finished workflow.",
    ],
    preview_graph: {
      title: "Custom Blank Graph",
      nodes: [
        {
          node_id: "node_start_here",
          kind: "artifact_source",
          label: "Start Here",
          position: { x: 120, y: 180 },
        },
      ],
      edges: [],
    },
  },
];

const nodeTypeRegistry: NodeTypeRegistrySnapshot = {
  schema_version: "astrabridge-node-type-registry-v1",
  registry_fingerprint: "registry-test",
  role_ids: [
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
  ],
  kind_aliases: {
    supervisor: "agent_model",
    worker: "agent_model",
    synthesizer: "agent_model",
    extractor: "agent_model",
    validator: "agent_model",
    reviewer: "agent_model",
    planner: "agent_model",
    coder: "agent_model",
    researcher: "agent_model",
    custom: "agent_model",
    gate: "human_approval",
  },
  node_types: [
    {
      type_id: "agent_model",
      version: 1,
      category: "agent",
      title: "Agent / Model",
      description:
        "Bounded provider-backed agent lane with explicit routing, prompt, and typed input/output ports.",
      config_schema: {
        type: "object",
        properties: {
          routing: { type: "object", title: "Routing" },
          prompt: { type: "object", title: "Prompt" },
          execution: { type: "object", title: "Execution" },
          safety: { type: "object", title: "Safety" },
        },
      },
      typed_ports: { inputs: [], outputs: [] },
      compiler_executor_id: "agent_lane",
      default_policy: {},
      ui_hints: {
        palette_role: "custom",
        palette_sections: ["planning", "execution"],
        icon: "bot",
        tone: "neutral",
        palette_variants: [
          {
            kind: "supervisor",
            label: "Supervisor",
            description:
              "Plans the bounded workflow and coordinates downstream workers.",
            palette_sections: ["planning"],
            icon: "compass",
            tone: "planner",
          },
          {
            kind: "planner",
            label: "Planner",
            description:
              "Breaks work into explicit steps and hands them to other agents.",
            palette_sections: ["planning"],
            icon: "file-text",
            tone: "planner",
          },
          {
            kind: "researcher",
            label: "Researcher",
            description:
              "Collects evidence, docs, or comparisons before synthesis.",
            palette_sections: ["planning"],
            icon: "search",
            tone: "extractor",
          },
          {
            kind: "extractor",
            label: "Extractor",
            description:
              "Pulls structured facts from files, docs, or provider metadata.",
            palette_sections: ["planning"],
            icon: "database",
            tone: "extractor",
          },
          {
            kind: "worker",
            label: "Worker",
            description:
              "Executes the main task and returns the primary artifact.",
            palette_sections: ["execution"],
            icon: "wrench",
            tone: "worker",
          },
          {
            kind: "coder",
            label: "Coder",
            description:
              "Applies code or document changes in a bounded implementation lane.",
            palette_sections: ["execution"],
            icon: "braces",
            tone: "worker",
          },
          {
            kind: "synthesizer",
            label: "Synthesizer",
            description:
              "Merges branch outputs into one bounded answer or artifact set.",
            palette_sections: ["execution"],
            icon: "sparkles",
            tone: "synthesizer",
          },
          {
            kind: "reviewer",
            label: "Reviewer",
            description:
              "Reads outputs critically and returns review feedback or approval.",
            palette_sections: ["execution"],
            icon: "eye",
            tone: "reviewer",
          },
          {
            kind: "validator",
            label: "Validator",
            description:
              "Runs checks, tests, or smoke validation before promotion.",
            palette_sections: ["execution"],
            icon: "shield-check",
            tone: "validator",
          },
          {
            kind: "custom",
            label: "Custom",
            description:
              "Starts as a neutral agent shell with the default fallback icon.",
            palette_sections: ["control"],
            icon: "bot",
            tone: "neutral",
          },
        ],
      },
      migration: {},
      registry_fingerprint: "agent-registry-test",
    },
    {
      type_id: "human_approval",
      version: 1,
      category: "approval",
      title: "Human Approval",
      description:
        "Pauses execution behind an explicit review and approval decision.",
      config_schema: {
        type: "object",
        properties: {
          review_kind: { type: "string", title: "Review kind" },
        },
      },
      typed_ports: { inputs: [], outputs: [] },
      compiler_executor_id: "human_approval",
      default_policy: {},
      ui_hints: {
        palette_role: "gate",
        palette_sections: ["control"],
        icon: "lock",
        tone: "gate",
      },
      migration: {},
      registry_fingerprint: "gate-registry-test",
    },
    {
      type_id: "mcp_tool",
      version: 1,
      category: "mcp",
      title: "MCP Tool",
      description:
        "Executes one declared MCP tool/resource operation through the broker boundary.",
      config_schema: {
        type: "object",
        properties: {
          tool: { type: "string", title: "Tool" },
          server: { type: "string", title: "Server" },
        },
      },
      typed_ports: { inputs: [], outputs: [] },
      compiler_executor_id: "mcp_tool",
      default_policy: {},
      ui_hints: {
        palette_role: "custom",
        palette_sections: ["control"],
        icon: "wrench",
        tone: "neutral",
      },
      migration: {},
      registry_fingerprint: "mcp-registry-test",
    },
  ],
};

const graph: TaskGraphDefinition = {
  schema_version: "astrabridge-task-graph-v1",
  graph_id: "graph_test",
  task_id: "task_test",
  title: "Provider Update / Smoke / Gate",
  template_id: "provider_update_smoke_gate",
  status: "ready",
  graph_policy: { entry_node_ids: ["node_discover"] },
  created_at: "2026-07-07T00:00:00+09:00",
  updated_at: "2026-07-07T00:00:00+09:00",
  state_version: 1,
  orchestration_graph: {
    schema_version: "astrabridge-agent-orchestration-graph-v1",
    graph_id: "graph_test",
    task_id: "task_test",
    title: "Provider Update / Smoke / Gate",
    template_id: "provider_update_smoke_gate",
    status: "ready",
    metadata: {},
    graph_policy: {},
    nodes: [
      {
        node_id: "node_discover",
        ports: {
          inputs: [{ port_id: "task_context", label: "Task Context", port_type: "text" }],
          outputs: [
            { port_id: "machine_result", label: "Machine Result", port_type: "structured_json" },
            { port_id: "diff_bundle", label: "Diff Bundle", port_type: "document" },
          ],
        },
      },
      {
        node_id: "node_smoke",
        ports: {
          inputs: [
            { port_id: "discover_result", label: "Discover Result", port_type: "structured_json" },
            { port_id: "diff_bundle", label: "Diff Bundle", port_type: "document" },
          ],
          outputs: [
            { port_id: "machine_result", label: "Machine Result", port_type: "structured_json" },
            { port_id: "smoke_matrix", label: "Smoke Matrix", port_type: "dataset" },
          ],
        },
      },
      {
        node_id: "node_gate",
        ports: {
          inputs: [{ port_id: "smoke_matrix", label: "Smoke Matrix", port_type: "dataset" }],
          outputs: [{ port_id: "approval_record", label: "Approval", port_type: "approval_record" }],
        },
      },
    ],
    edges: [
      {
        edge_id: "edge_discover_smoke",
        handoff_contract: {
          port_bindings: [
            { from_port_id: "machine_result", to_port_id: "discover_result" },
            { from_port_id: "diff_bundle", to_port_id: "diff_bundle" },
          ],
        },
      },
    ],
    schema_registry: {},
    prompt_registry: {},
    migration: {},
    state_version: 1,
  },
  nodes: [
    {
      node_id: "node_discover",
      graph_id: "graph_test",
      kind: "extractor",
      label: "Discover Provider Update",
      agent_card_ref: "agent_card_provider_discovery",
      execution_policy: {},
      output_contract: {},
      position: { x: 80, y: 160 },
      status: "ready",
      provider_id: "qwen",
      model_id: "qwen3-coder-plus",
      reasoning_effort: "medium",
      permission_mode: "ask",
      collaboration_mode: "default",
      execution_backend: "app_server",
      ui_hints: { context_policy_preset: "task_digest" },
    },
    {
      node_id: "node_smoke",
      graph_id: "graph_test",
      kind: "validator",
      label: "Generate Smoke Matrix",
      agent_card_ref: "agent_card_provider_smoke",
      execution_policy: {},
      output_contract: {},
      position: { x: 340, y: 160 },
      status: "ready",
      provider_id: "qwen",
      model_id: "qwen3-coder-plus",
      reasoning_effort: "high",
      permission_mode: "auto",
      collaboration_mode: "plan",
      execution_backend: "native_kernel",
      ui_hints: { context_policy_preset: "artifact_first" },
    },
    {
      node_id: "node_gate",
      graph_id: "graph_test",
      kind: "gate",
      label: "Approve Promotion",
      agent_card_ref: "agent_card_provider_gate",
      execution_policy: {},
      output_contract: {},
      position: { x: 580, y: 160 },
      status: "ready",
      ui_hints: { context_policy_preset: "latest_summary_only" },
    },
  ],
  edges: [
    {
      edge_id: "edge_discover_smoke",
      graph_id: "graph_test",
      from_node_id: "node_discover",
      to_node_id: "node_smoke",
      edge_type: "artifact_handoff",
      context_policy: {
        policy_id: "policy_discover_smoke",
        history_mode: "latest_summary_only",
        artifact_mode: "required_output_only",
        exclude_private_memory: true,
        include_machine_results: true,
        include_human_summaries: true,
        summary_strategy: "human_summary_only",
        history_length: 1,
        included_artifacts: ["required_output"],
        resource_refs: ["PRIVATE/provider-smoke/latest.json"],
      },
      status: "ready",
    },
  ],
};

const dryRunResult: TaskGraphDryRunResult = {
  schema_version: "astrabridge-task-graph-dry-run-v1",
  run_id: "graph-dry-run-test",
  graph_id: "graph_test",
  task_id: "task_test",
  created_at: "2026-07-07T00:05:00+09:00",
  overall_status: "warning",
  status_counts: {
    pass: 1,
    warning: 1,
    blocked: 1,
  },
  graph_result: {
    status: "warning",
    reasons: [
      "Provider is set without a pinned model; route resolution is under-specified.",
    ],
  },
  node_results: [
    {
      node_id: "node_discover",
      label: "Discover Provider Update",
      status: "pass",
      reasons: [],
    },
    {
      node_id: "node_smoke",
      label: "Generate Smoke Matrix",
      status: "warning",
      reasons: [
        "Provider is set without a pinned model; route resolution is under-specified.",
      ],
    },
    {
      node_id: "node_gate",
      label: "Approve Promotion",
      status: "blocked",
      reasons: ["Output contract does not declare any artifact outputs."],
    },
  ],
  edge_results: [
    {
      edge_id: "edge_discover_smoke",
      label: "node_discover -> node_smoke",
      status: "pass",
      reasons: [],
    },
  ],
  artifact_paths: {
    summary_json: "PRIVATE/task-graph/dry-run/graph-dry-run-test/summary.json",
    report_md: "PRIVATE/task-graph/dry-run/graph-dry-run-test/report.md",
  },
};

const latestRunRef: TaskGraphRunRef = {
  run_id: "graph-run-worker-1",
  graph_id: "graph_test",
  task_id: "task_test",
  status: "completed",
  created_at: "2026-07-07T00:06:00+09:00",
  updated_at: "2026-07-07T00:07:00+09:00",
  entry_node_ids: ["node_discover"],
  node_status_counts: { completed: 2, waiting_on_dependencies: 1 },
  artifact_count: 3,
  event_count: 4,
  metrics: {
    status: "available",
    elapsed_ms: 4200,
    max_parallelism: 2,
    artifact_count: 3,
    event_count: 4,
    retry_count: 1,
    failure_count: 0,
    approval_count: 0,
    provider_call_count: 1,
    tool_call_count: 2,
    token_usage: {
      status: "available",
      total_tokens: 1500,
    },
    cost: {
      status: "estimated",
      currency: "USD",
      total_cost: 0.0042,
    },
    unknown_fields: [],
  },
  budget: {
    status: "within_budget",
    enforcement: "fail_fast_static_then_report_only_dynamic",
  },
  worker_count: 1,
  worker_bindings: [
    {
      binding_id: "binding_worker_1",
      graph_id: "graph_test",
      run_id: "graph-run-worker-1",
      node_id: "node_smoke",
      worker_thread_id: "thread-worker-1",
      parent_thread_id: "thread-parent-1",
      spawn_mode: "subagent_worker",
      worker_origin: "codex_subagent",
      agent_role: "validator",
      agent_nickname: "Smoke worker",
      status: "completed",
      execution_backend: "app_server",
      artifact_refs: [
        {
          artifact_id: "thread-worker-1-summary-md",
          artifact_kind: "text_report",
          path: "PRIVATE/task-graph/workers/graph-run-worker-1/node_smoke/summary.md",
          status: "ready",
        },
      ],
      output_summary: {
        human_summary:
          "Worker produced a smoke matrix and ready-for-gate summary.",
        machine_result_preview: '{"matrix": ["qwen", "kimi"]}',
        next_action_hints: ["Route gate to the updated provider set."],
      },
      downstream_handoffs: [
        {
          edge_id: "edge_smoke_gate",
          to_node_id: "node_gate",
          edge_type: "approval_dependency",
          context_policy: {
            history_mode: "explicit_refs_only",
            artifact_mode: "explicit_artifacts",
            exclude_private_memory: true,
            include_machine_results: true,
            include_human_summaries: true,
            summary_strategy: "human_and_machine",
            history_length: 0,
            included_artifacts: ["smoke_matrix"],
            resource_refs: ["PRIVATE/provider-smoke/report.md"],
          },
          downstream_input: {
            source: "artifact_refs_and_context_policy",
            run_id: "graph-run-worker-1",
            artifact_paths: [
              "PRIVATE/task-graph/workers/graph-run-worker-1/node_smoke/output.json",
            ],
            human_summary_path:
              "PRIVATE/task-graph/workers/graph-run-worker-1/node_smoke/summary.md",
            machine_result_path:
              "PRIVATE/task-graph/workers/graph-run-worker-1/node_smoke/output.json",
          },
        },
      ],
      created_at: "2026-07-07T00:06:00+09:00",
      updated_at: "2026-07-07T00:07:00+09:00",
    },
  ],
};

const pendingApprovalRunRef: TaskGraphRunRef = {
  ...latestRunRef,
  run_id: "graph-run-gate-1",
  status: "paused_for_review",
  approval_state: "pending",
  approval_details: {
    status: "pending",
    review_kind: "provider_call_gate",
    node_id: "node_gate",
    reason:
      "Provider promotion is a high-risk action and requires human approval before execution continues.",
    requested_at: "2026-07-07T00:08:00+09:00",
  },
  worker_bindings: [
    ...latestRunRef.worker_bindings!,
    {
      binding_id: "binding_gate_1",
      graph_id: "graph_test",
      run_id: "graph-run-gate-1",
      node_id: "node_gate",
      worker_thread_id: "thread-gate-1",
      parent_thread_id: "thread-parent-1",
      spawn_mode: "manual_only",
      worker_origin: "manual",
      agent_role: "gate",
      agent_nickname: "Approve Promotion",
      status: "waiting_on_approval",
      execution_backend: "human_review",
      artifact_refs: [],
      created_at: "2026-07-07T00:08:00+09:00",
      updated_at: "2026-07-07T00:08:00+09:00",
    },
  ],
  worker_count: 2,
};

const cancellableRunningRunRef: TaskGraphRunRef = {
  run_id: "graph-run-running-1",
  graph_id: "graph_test",
  task_id: "task_test",
  status: "running",
  created_at: "2026-07-07T00:09:00+09:00",
  updated_at: "2026-07-07T00:10:00+09:00",
  entry_node_ids: ["node_discover"],
  node_status_counts: { completed: 1, running: 1, waiting_on_dependencies: 2 },
  artifact_count: 2,
  event_count: 4,
  timeline_events: [
    {
      event_id: "graph-run-running-1-created",
      event_type: "run_created",
      created_at: "2026-07-07T00:09:00+09:00",
      summary: "Cancellable fan-out fixture run created.",
      status: "pending",
    },
    {
      event_id: "graph-run-running-1-branch-a-started",
      event_type: "node_started",
      created_at: "2026-07-07T00:09:10+09:00",
      summary: "Branch A started its bounded research fixture run.",
      node_id: "node_smoke",
      status: "in_progress",
    },
  ],
  worker_count: 1,
  worker_bindings: [
    {
      binding_id: "binding_running_1",
      graph_id: "graph_test",
      run_id: "graph-run-running-1",
      node_id: "node_smoke",
      worker_thread_id: "thread-running-1",
      parent_thread_id: "thread-parent-1",
      spawn_mode: "subagent_worker",
      worker_origin: "codex_subagent",
      agent_role: "validator",
      agent_nickname: "Running worker",
      status: "running",
      execution_backend: "app_server",
      artifact_refs: [],
      output_summary: {
        human_summary: "Worker is still gathering bounded branch evidence.",
      },
      created_at: "2026-07-07T00:09:05+09:00",
      updated_at: "2026-07-07T00:10:00+09:00",
    },
  ],
};

const queuedAuthoritativeRunRef: TaskGraphRunRef = {
  ...latestRunRef,
  run_id: "graph-run-queued-1",
  status: "running",
  created_at: "2099-07-15T11:23:43+09:00",
  updated_at: "2099-07-15T11:23:44+09:00",
  artifact_count: 0,
  event_count: 2,
  node_status_counts: {
    queued: 1,
    waiting_on_dependencies: 4,
  },
  timeline_events: [
    {
      event_id: "graph-run-queued-1-created",
      event_type: "run_created",
      created_at: "2026-07-15T11:23:43+09:00",
      summary: "Live run created and queued for execution.",
      status: "pending",
    },
    {
      event_id: "graph-run-queued-1-planner-queued",
      event_type: "node_queued",
      created_at: "2026-07-15T11:23:44+09:00",
      summary: "Planner queued for live execution.",
      node_id: "node_discover",
      status: "pending",
    },
  ],
  worker_count: 0,
  worker_bindings: [],
};

const recoveredRunRef: TaskGraphRunRef = {
  ...latestRunRef,
  run_id: "graph-run-recovered-1",
  status: "completed",
  node_status_counts: { completed: 3, partial: 1 },
  node_outcome_counts: { completed: 3, partial: 1 },
  artifact_refs: [
    {
      artifact_id: "graph-run-recovered-1-recovery-manifest-json",
      artifact_kind: "structured_json",
      path: "PRIVATE/task-graph/recovery/graph-recovery-1/manifest.json",
      status: "ready",
    },
    {
      artifact_id: "graph-run-recovered-1-recovery-report-md",
      artifact_kind: "run_summary",
      path: "PRIVATE/task-graph/recovery/graph-recovery-1/report.md",
      status: "ready",
    },
  ],
  policy_snapshot: {
    mode: "fixture_run",
    recovery: {
      recovery_id: "graph-recovery-1",
      source_run_id: "graph-run-running-1",
      strategy: "partial_execution",
      selected_node_ids: ["node_smoke"],
      rerun_node_ids: ["node_smoke", "node_gate"],
      reused_node_ids: ["node_discover"],
    },
  },
};

function buildWorkspaceProps(
  overrides?: Partial<ComponentProps<typeof TaskGraphWorkspace>>,
) {
  return {
    locale: "en",
    templates,
    graph,
    selectedNodeId: "node_smoke",
    selectedEdgeId: null,
    providerOptions: ["qwen", "kimi"],
    modelSuggestions: ["qwen3-coder-plus", "kimi-k2.6"],
    nodeTypeRegistry,
    nodeSaveError: null,
    edgeSaveError: null,
    dryRunResult: null,
    dryRunError: null,
    reportHref: null,
    latestRunRef: null,
    artifactHrefFor: (path: string) =>
      `/api/project/files/read?path=${encodeURIComponent(path)}`,
    onInspectArtifactPath: vi.fn(),
    onSelectNode: vi.fn(),
    onSelectEdge: vi.fn(),
    onInstantiateTemplate: vi.fn(),
    onCreateNode: vi.fn(),
    onMoveNode: vi.fn(),
    onSaveNode: vi.fn(),
    onSaveEdge: vi.fn(),
    onDeleteEdge: vi.fn(),
    onRunDryRun: vi.fn(),
    onRunLive: vi.fn(),
    onRunFixture: vi.fn(),
    onRunCancellableFixture: vi.fn(),
    onCancelLatestRun: vi.fn(),
    onRecoverLatestRun: vi.fn(),
    onApprovePendingRun: vi.fn(),
    onRejectPendingRun: vi.fn(),
    onImportGraph: vi.fn(),
    onExportGraph: vi.fn(),
    snapshotRefs: [],
    selectedSnapshotId: null,
    onSelectSnapshot: vi.fn(),
    onCreateSnapshot: vi.fn(),
    onCompareSnapshot: vi.fn(),
    onRollbackSnapshot: vi.fn(),
    onClose: vi.fn(),
    importExportError: null,
    lastImportedPath: null,
    lastExportedPath: null,
    lastExportPreview: null,
    snapshotError: null,
    snapshotStatus: null,
    snapshotDiffMarkdown: null,
    isInstantiating: false,
    isLoadingTemplates: false,
    isLoadingGraph: false,
    isSavingNode: false,
    isSavingEdge: false,
    isDryRunPending: false,
    isLiveRunPending: false,
    isFixtureRunPending: false,
    isRunCancellationPending: false,
    isRunRecoveryPending: false,
    isApprovalDecisionPending: false,
    isImportingGraph: false,
    isExportingGraph: false,
    isSnapshotPending: false,
    isSnapshotDiffPending: false,
    isSnapshotRollbackPending: false,
    ...overrides,
  } satisfies ComponentProps<typeof TaskGraphWorkspace>;
}

function renderWorkspace(
  overrides?: Partial<ComponentProps<typeof TaskGraphWorkspace>>,
) {
  return render(<TaskGraphWorkspace {...buildWorkspaceProps(overrides)} />);
}

function expandSidebar() {
  fireEvent.click(screen.getByTestId("task-graph-sidebar-toggle"));
}

function openSidebarSection(label: string) {
  if (label === "Edges") {
    fireEvent.click(screen.getByTestId("task-graph-sidebar-pane-edges"));
    return;
  }
  if (label === "Nodes") {
    fireEvent.click(screen.getByTestId("task-graph-sidebar-pane-nodes"));
    return;
  }
  fireEvent.click(screen.getByText(label));
}

function openSidebarPane(pane: "nodes" | "edges") {
  fireEvent.click(screen.getByTestId(`task-graph-sidebar-pane-${pane}`));
}

function openTemplateBrowser() {
  fireEvent.click(screen.getByTestId("task-graph-open-template-browser"));
}

function expandInspector() {
  fireEvent.click(screen.getByTestId("task-graph-inspector-toggle"));
}

function expandRecoveryPanel() {
  const panel = screen.getByTestId("task-graph-recovery-panel");
  if (!panel.hasAttribute("open")) {
    fireEvent.click(within(panel).getByText("Recovery"));
  }
}

describe("TaskGraphWorkspace", () => {
  it("renders when runtime array props are temporarily missing", () => {
    renderWorkspace({
      templates: undefined as unknown as TaskGraphTemplateSummary[],
      providerOptions: undefined as unknown as string[],
      modelSuggestions: undefined as unknown as string[],
      snapshotRefs: undefined as unknown as ComponentProps<
        typeof TaskGraphWorkspace
      >["snapshotRefs"],
    });

    expect(screen.getByTestId("task-graph-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-canvas")).toBeInTheDocument();
  });

  it("renders template cards, canvas nodes, and editable node inspector content", () => {
    renderWorkspace();
    expandSidebar();
    expandInspector();
    openTemplateBrowser();

    expect(screen.getByTestId("task-graph-workspace")).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-template-provider_update_smoke_gate"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-template-summary-panel"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-template-instantiate"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-canvas")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-node-node_smoke")).toHaveTextContent(
      "Generate Smoke Matrix",
    );
    expect(screen.getByTestId("task-graph-inspector-model")).toHaveValue(
      "qwen3-coder-plus",
    );
    expect(
      screen.getByTestId("task-graph-inspector-context-policy"),
    ).toHaveValue("artifact_first");
  });

  it("lets the user resize task-graph sidebars and persists the widths", () => {
    renderWorkspace();
    expandSidebar();

    const grid = screen.getByTestId("task-graph-grid");
    expect(grid.style.getPropertyValue("--task-graph-sidebar-width")).toBe(
      "60px",
    );

    fireEvent.mouseDown(
      screen.getByTestId("task-graph-sidebar-resize-handle"),
      { clientX: 160 },
    );
    fireEvent.mouseMove(window, { clientX: 220 });
    fireEvent.mouseUp(window, { clientX: 220 });

    expect(grid.style.getPropertyValue("--task-graph-sidebar-width")).toBe(
      "80px",
    );
    expect(
      window.localStorage.getItem("astrabridge.task_graph.sidebar_width"),
    ).toBe("80");
  });

  it("switches the inspector between selection and run workspaces", () => {
    renderWorkspace({ latestRunRef });
    expandInspector();

    expect(
      screen.getByTestId("task-graph-inspector-run-workspace"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-run-panel")).toBeInTheDocument();

    fireEvent.click(
      screen.getByTestId("task-graph-inspector-workspace-selection"),
    );

    expect(
      screen.getByTestId("task-graph-inspector-provider"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("task-graph-inspector-workspace-run"));

    expect(
      screen.getByTestId("task-graph-inspector-run-workspace"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-run-panel")).toBeInTheDocument();
  });

  it("lets an explicit selection take priority over a prior run", () => {
    renderWorkspace({ latestRunRef });
    expandInspector();

    fireEvent.click(
      screen.getByTestId("task-graph-inspector-workspace-selection"),
    );

    expect(
      screen.getByTestId("task-graph-inspector-provider"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("task-graph-run-panel")).not.toBeInTheDocument();
  });

  it("keeps the current dry-run result primary instead of mixing in run history", () => {
    renderWorkspace({ latestRunRef: cancellableRunningRunRef, dryRunResult });
    expandInspector();

    expect(screen.getByTestId("task-graph-dry-run-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("task-graph-run-panel")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-inspector-run-workspace"),
    ).toHaveTextContent("Run readiness");
  });

  it("labels an old active run as stale instead of claiming it is still running", () => {
    renderWorkspace({ latestRunRef: cancellableRunningRunRef });
    expandInspector();

    expect(screen.getByTestId("task-graph-latest-run-status")).toHaveTextContent(
      "stale",
    );
  });

  it("lets the user preview a template before instantiating it", () => {
    const onInstantiateTemplate = vi.fn();
    renderWorkspace({ onInstantiateTemplate });
    openTemplateBrowser();

    fireEvent.click(
      screen.getByTestId("task-graph-template-custom_blank_graph"),
    );

    expect(
      screen.getByTestId("task-graph-template-summary-panel"),
    ).toHaveTextContent("Custom Blank Graph");
    expect(screen.getByTestId("task-graph-template-preview")).toHaveTextContent(
      "Start Here",
    );

    fireEvent.click(screen.getByTestId("task-graph-template-instantiate"));
    expect(onInstantiateTemplate).toHaveBeenCalledWith("custom_blank_graph");
  });

  it("shows recent snapshots and exposes compare and rollback actions", () => {
    const onSelectSnapshot = vi.fn();
    const onCreateSnapshot = vi.fn();
    const onCompareSnapshot = vi.fn();
    const onRollbackSnapshot = vi.fn();
    renderWorkspace({
      latestRunRef,
      snapshotRefs: [
        {
          snapshot_id: "graph-snapshot-4",
          task_id: "task_step11",
          graph_id: "graph_step11",
          label: "Before save: API debug instantiate probe 8843b",
          state_version: 6,
          created_at: "2026-07-08T08:02:00Z",
          updated_at: "2026-07-08T08:02:00Z",
          artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-4.json" },
        },
        {
          snapshot_id: "graph-snapshot-3",
          task_id: "task_step11",
          graph_id: "graph_step11",
          label: "After node update: node_supervisor_v4",
          state_version: 5,
          created_at: "2026-07-08T08:01:00Z",
          updated_at: "2026-07-08T08:01:00Z",
          artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-3.json" },
        },
        {
          snapshot_id: "graph-snapshot-2",
          task_id: "task_step11",
          graph_id: "graph_step11",
          label: "After edge update",
          state_version: 4,
          created_at: "2026-07-08T08:00:00Z",
          updated_at: "2026-07-08T08:00:00Z",
          artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-2.json" },
        },
        {
          snapshot_id: "graph-snapshot-1",
          task_id: "task_step11",
          graph_id: "graph_step11",
          label: "Before edge update",
          state_version: 3,
          created_at: "2026-07-08T07:59:00Z",
          updated_at: "2026-07-08T07:59:00Z",
          artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-1.json" },
        },
        {
          snapshot_id: "graph-snapshot-0",
          task_id: "task_step11",
          graph_id: "graph_step11",
          label: "Before node update",
          state_version: 2,
          created_at: "2026-07-08T07:58:00Z",
          updated_at: "2026-07-08T07:58:00Z",
          artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-0.json" },
        },
        {
          snapshot_id: "graph-snapshot-initial",
          task_id: "task_step11",
          graph_id: "graph_step11",
          label: "Initial graph",
          state_version: 1,
          created_at: "2026-07-08T07:57:00Z",
          updated_at: "2026-07-08T07:57:00Z",
          artifact_paths: {
            manifest_json: "PRIVATE/step16/snapshot-initial.json",
          },
        },
      ],
      selectedSnapshotId: "graph-snapshot-2",
      snapshotStatus: "Snapshot created: After edge update",
      snapshotDiffMarkdown: "# Diff\n- edge changed",
      onSelectSnapshot,
      onCreateSnapshot,
      onCompareSnapshot,
      onRollbackSnapshot,
    });

    fireEvent.click(screen.getByTestId("task-graph-snapshot"));
    fireEvent.click(screen.getByTestId("task-graph-compare-snapshot"));
    fireEvent.click(screen.getByTestId("task-graph-rollback-snapshot"));

    expect(onCreateSnapshot).toHaveBeenCalled();
    expect(onCompareSnapshot).toHaveBeenCalled();
    expect(onRollbackSnapshot).toHaveBeenCalled();
    expect(screen.queryByText("Before edge update")).not.toBeInTheDocument();
    expect(screen.queryByText("Initial graph")).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("list", { name: "Recent snapshots" })).getAllByRole(
        "listitem",
      ),
    ).toHaveLength(3);
    expect(
      screen.getByTestId("task-graph-snapshot-preview-meta"),
    ).toHaveTextContent("Showing 3 of 6");

    const snapshotToggle = screen.getByTestId("task-graph-snapshot-toggle");
    expect(snapshotToggle).toHaveAttribute("aria-expanded", "false");
    expect(snapshotToggle).toHaveAccessibleName("3 more");
    fireEvent.click(snapshotToggle);
    expect(screen.getByText("Initial graph")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Before edge update"));
    expect(onSelectSnapshot).toHaveBeenCalledWith("graph-snapshot-1");
    expect(
      within(screen.getByRole("list", { name: "Recent snapshots" })).getAllByRole(
        "listitem",
      ),
    ).toHaveLength(6);
    expect(snapshotToggle).toHaveAttribute("aria-expanded", "true");
    expect(snapshotToggle).toHaveAccessibleName("Show less");
    fireEvent.click(snapshotToggle);
    expect(screen.queryByText("Initial graph")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-snapshot-diff-markdown"),
    ).toHaveTextContent("edge changed");
  });

  it("omits a missing snapshot version instead of rendering an undefined placeholder", () => {
    renderWorkspace({
      snapshotRefs: [
        {
          snapshot_id: "legacy-snapshot",
          task_id: "task_step11",
          graph_id: "graph_step11",
          label: "Legacy snapshot",
          state_version: undefined,
          created_at: "2026-07-08T08:02:00Z",
          updated_at: "2026-07-08T08:02:00Z",
          artifact_paths: { manifest_json: "PRIVATE/legacy.json" },
        },
      ],
    });

    const item = screen.getByRole("listitem", { name: "Legacy snapshot" });
    expect(item).toHaveTextContent("Legacy snapshot");
    expect(item).not.toHaveTextContent("undefined");
    expect(item).toHaveAttribute("title", "Legacy snapshot");
  });

  it("re-collapses recent snapshots when the snapshot list changes", () => {
    const onSelectSnapshot = vi.fn();
    const initialSnapshotRefs = [
      {
        snapshot_id: "graph-snapshot-2",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "After edge update",
        state_version: 4,
        created_at: "2026-07-08T08:00:00Z",
        updated_at: "2026-07-08T08:00:00Z",
        artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-2.json" },
      },
      {
        snapshot_id: "graph-snapshot-1",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "Before edge update",
        state_version: 3,
        created_at: "2026-07-08T07:59:00Z",
        updated_at: "2026-07-08T07:59:00Z",
        artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-1.json" },
      },
      {
        snapshot_id: "graph-snapshot-0",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "Before node update",
        state_version: 2,
        created_at: "2026-07-08T07:58:00Z",
        updated_at: "2026-07-08T07:58:00Z",
        artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-0.json" },
      },
      {
        snapshot_id: "graph-snapshot-initial",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "Initial graph",
        state_version: 1,
        created_at: "2026-07-08T07:57:00Z",
        updated_at: "2026-07-08T07:57:00Z",
        artifact_paths: {
          manifest_json: "PRIVATE/step16/snapshot-initial.json",
        },
      },
    ];
    const updatedSnapshotRefs = [
      {
        snapshot_id: "graph-snapshot-3",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "Before save: node_supervisor_v4",
        state_version: 5,
        created_at: "2026-07-08T08:01:00Z",
        updated_at: "2026-07-08T08:01:00Z",
        artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-3.json" },
      },
      ...initialSnapshotRefs,
    ];
    const view = renderWorkspace({
      snapshotRefs: initialSnapshotRefs,
      selectedSnapshotId: "graph-snapshot-2",
      onSelectSnapshot,
    });

    const snapshotToggle = screen.getByTestId("task-graph-snapshot-toggle");
    fireEvent.click(snapshotToggle);
    expect(snapshotToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Initial graph")).toBeInTheDocument();

    view.rerender(
      <TaskGraphWorkspace
        {...buildWorkspaceProps({
          snapshotRefs: updatedSnapshotRefs,
          selectedSnapshotId: "graph-snapshot-3",
          onSelectSnapshot,
        })}
      />,
    );

    expect(
      screen.getByTestId("task-graph-snapshot-toggle"),
    ).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Initial graph")).not.toBeInTheDocument();
  });

  it("re-collapses recent snapshots when a new latest run arrives", () => {
    const snapshotRefs = [
      {
        snapshot_id: "graph-snapshot-3",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "Before save: node_supervisor_v4",
        state_version: 5,
        created_at: "2026-07-08T08:01:00Z",
        updated_at: "2026-07-08T08:01:00Z",
        artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-3.json" },
      },
      {
        snapshot_id: "graph-snapshot-2",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "After edge update",
        state_version: 4,
        created_at: "2026-07-08T08:00:00Z",
        updated_at: "2026-07-08T08:00:00Z",
        artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-2.json" },
      },
      {
        snapshot_id: "graph-snapshot-1",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "Before edge update",
        state_version: 3,
        created_at: "2026-07-08T07:59:00Z",
        updated_at: "2026-07-08T07:59:00Z",
        artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-1.json" },
      },
      {
        snapshot_id: "graph-snapshot-0",
        task_id: "task_step11",
        graph_id: "graph_step11",
        label: "Before node update",
        state_version: 2,
        created_at: "2026-07-08T07:58:00Z",
        updated_at: "2026-07-08T07:58:00Z",
        artifact_paths: { manifest_json: "PRIVATE/step16/snapshot-0.json" },
      },
    ];
    const view = renderWorkspace({
      latestRunRef,
      snapshotRefs,
      selectedSnapshotId: "graph-snapshot-3",
    });

    fireEvent.click(screen.getByTestId("task-graph-snapshot-toggle"));
    expect(
      screen.getByTestId("task-graph-snapshot-toggle"),
    ).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Before node update")).toBeInTheDocument();

    view.rerender(
      <TaskGraphWorkspace
        {...buildWorkspaceProps({
          latestRunRef: {
            ...latestRunRef,
            run_id: "graph-run-worker-2",
            updated_at: "2026-07-07T00:09:00+09:00",
          },
          snapshotRefs,
          selectedSnapshotId: "graph-snapshot-3",
        })}
      />,
    );

    expect(
      screen.getByTestId("task-graph-snapshot-toggle"),
    ).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Before node update")).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("list", { name: "Recent snapshots" })).getAllByRole(
        "listitem",
      ),
    ).toHaveLength(3);
  });

  it("instantiates the latest clicked template even when the action follows immediately", () => {
    const onInstantiateTemplate = vi.fn();
    renderWorkspace({ onInstantiateTemplate });
    openTemplateBrowser();

    const instantiateButton = screen.getByTestId(
      "task-graph-template-instantiate",
    );

    fireEvent.click(
      screen.getByTestId("task-graph-template-custom_blank_graph"),
    );
    fireEvent.click(instantiateButton);

    expect(onInstantiateTemplate).toHaveBeenCalledWith("custom_blank_graph");
  });

  it("renders empty state cleanly before a graph is instantiated", () => {
    renderWorkspace({
      graph: null,
      selectedNodeId: null,
      selectedEdgeId: null,
    });
    expandSidebar();
    openSidebarPane("nodes");

    expect(screen.getByTestId("task-graph-empty")).toHaveTextContent(
      "No graph yet",
    );
    expect(screen.getByTestId("task-graph-node-palette")).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-empty-open-template-browser"),
    ).toBeInTheDocument();

    openTemplateBrowser();
    expect(screen.getByTestId("task-graph-template-list")).toBeInTheDocument();
  });

  it("does not show the loading placeholder when a graph is already renderable", () => {
    renderWorkspace({
      isLoadingGraph: true,
    });

    expect(screen.queryByText("Loading graph...")).not.toBeInTheDocument();
    expect(screen.getByTestId("task-graph-canvas")).toBeInTheDocument();
  });

  it("adds compact agent nodes from the visible palette and shows a fallback icon for custom nodes", () => {
    const onCreateNode = vi.fn();
    renderWorkspace({ onCreateNode });
    expandSidebar();
    openSidebarPane("nodes");

    expect(screen.getByTestId("task-graph-palette-add-supervisor")).toHaveAttribute(
      "title",
      "Supervisor: Plans the bounded workflow and coordinates downstream workers.",
    );
    expect(screen.getByTestId("task-graph-palette-add-coder")).toHaveAttribute(
      "title",
      "Coder: Applies code or document changes in a bounded implementation lane.",
    );
    expect(screen.getByTestId("task-graph-palette-add-extractor")).toHaveAttribute(
      "title",
      "Extractor: Pulls structured facts from files, docs, or provider metadata.",
    );

    fireEvent.click(screen.getByTestId("task-graph-palette-add-supervisor"));
    fireEvent.click(screen.getByTestId("task-graph-palette-add-validator"));
    fireEvent.click(screen.getByTestId("task-graph-palette-add-custom"));

    expect(onCreateNode).toHaveBeenNthCalledWith(1, {
      kind: "supervisor",
      position: undefined,
    });
    expect(onCreateNode).toHaveBeenNthCalledWith(2, {
      kind: "validator",
      position: undefined,
    });
    expect(onCreateNode).toHaveBeenNthCalledWith(3, {
      kind: "custom",
      position: undefined,
    });
    expect(screen.getByTestId("task-graph-palette-add-custom")).toHaveAttribute(
      "title",
      "Custom: Starts as a neutral agent shell with the default fallback icon.",
    );
  });

  it("saves registry-driven node type config back into ui_hints", () => {
    const onSaveNode = vi.fn();
    const mcpGraph: TaskGraphDefinition = {
      ...graph,
      nodes: graph.nodes.map((node) =>
        node.node_id === "node_smoke"
          ? {
              ...node,
              kind: "mcp_tool",
              label: "Search Tool",
              ui_hints: {
                context_policy_preset: "task_digest",
                node_type_config: {
                  tool: "web.search",
                  server: "astrabridge_web",
                },
              },
            }
          : node,
      ),
    };

    renderWorkspace({
      graph: mcpGraph,
      selectedNodeId: "node_smoke",
      onSaveNode,
    });
    expandInspector();

    fireEvent.change(
      screen.getByTestId("task-graph-inspector-node-type-config-field-tool"),
      {
        target: { value: "read_file" },
      },
    );
    fireEvent.change(
      screen.getByTestId("task-graph-inspector-node-type-config-field-server"),
      {
        target: { value: "workspace_files" },
      },
    );
    fireEvent.click(screen.getByTestId("task-graph-inspector-save"));

    expect(onSaveNode).toHaveBeenCalledWith(
      "node_smoke",
      expect.objectContaining({
        ui_hints: expect.objectContaining({
          node_type_config: {
            tool: "read_file",
            server: "workspace_files",
          },
          node_type_id: "mcp_tool",
        }),
      }),
    );
  });

  it("exposes collapsed rail entry points and reopens the requested pane", () => {
    renderWorkspace();

    expect(screen.getByTestId("task-graph-sidebar-rail-nodes")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-sidebar-rail-edges")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("task-graph-sidebar-rail-nodes"));

    expect(screen.getByTestId("task-graph-sidebar-pane-nodes")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("task-graph-node-palette")).toBeInTheDocument();
  });

  it("shows compact typed port summaries on nodes and default canvas edges", () => {
    renderWorkspace({
      dryRunResult,
    });

    expect(
      within(
        screen.getByTestId("task-graph-node-ports-node_discover"),
      ).getAllByTitle(/Task Context/).length,
    ).toBeGreaterThan(0);
    expect(
      within(
        screen.getByTestId("task-graph-node-ports-node_smoke"),
      ).getAllByTitle(/Discover Result/).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByTestId("task-graph-canvas-edge-chip-edge_discover_smoke"),
    ).toHaveAttribute("title", expect.stringContaining("Artifact"));
    expect(
      screen.getByTestId("task-graph-canvas-edge-chip-edge_discover_smoke"),
    ).toHaveAttribute("title", expect.stringContaining("Discover Result"));
  });

  it("shows readable typed port details in the node inspector", () => {
    renderWorkspace();
    expandInspector();

    expect(
      screen.getByTestId("task-graph-inspector-node-ports"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-inspector-node-port-inputs"),
    ).toHaveTextContent("Discover Result");
    expect(
      screen.getByTestId("task-graph-inspector-node-port-inputs"),
    ).toHaveTextContent("Structured JSON");
    expect(
      screen.getByTestId("task-graph-inspector-node-port-outputs"),
    ).toHaveTextContent("Smoke Matrix");
    expect(
      screen.getByTestId("task-graph-inspector-node-port-outputs"),
    ).toHaveTextContent("Dataset");
  });

  it("derives typed node ports from orchestration contracts when explicit ports are absent", () => {
    const contractGraph: TaskGraphDefinition = {
      ...graph,
      orchestration_graph: {
        ...graph.orchestration_graph!,
        nodes: [
          {
            node_id: "node_discover",
            input_contract: { mode: "task_context" },
            output_contract: {
              machine_result_schema_ref: "schema.node_discover.machine_result",
              artifact_specs: [{ kind: "structured_json", id: "structured_json" }],
            },
          },
          {
            node_id: "node_smoke",
            input_contract: { mode: "task_context" },
            output_contract: {
              machine_result_schema_ref: "schema.node_smoke.machine_result",
              artifact_specs: [{ kind: "validation_report", id: "validation_report" }],
            },
          },
          {
            node_id: "node_gate",
            input_contract: { mode: "task_context" },
            output_contract: {
              machine_result_schema_ref: "schema.node_gate.machine_result",
              artifact_specs: [{ kind: "approval_record", id: "approval_record" }],
            },
          },
        ],
      },
    };

    renderWorkspace({
      graph: contractGraph,
      dryRunResult,
      selectedEdgeId: "edge_discover_smoke",
    });

    expect(
      within(
        screen.getByTestId("task-graph-node-ports-node_discover"),
      ).getAllByTitle(/Task Context/).length,
    ).toBeGreaterThan(0);
    expect(
      within(
        screen.getByTestId("task-graph-node-ports-node_discover"),
      ).getAllByTitle(/Machine Result/).length,
    ).toBeGreaterThan(0);
    expect(
      within(screen.getByTestId("task-graph-node-ports-node_gate")).getAllByTitle(
        /approval_record/i,
      ).length,
    ).toBeGreaterThan(0);
  });

  it("shows an inspector warning for incomplete newly added nodes", () => {
    const incompleteGraph: TaskGraphDefinition = {
      ...graph,
      nodes: [
        ...graph.nodes,
        {
          node_id: "node_custom",
          graph_id: "graph_test",
          kind: "custom",
          label: "Custom Agent",
          agent_card_ref: "agent_card_custom",
          execution_policy: {},
          output_contract: {},
          position: { x: 80, y: 340 },
          status: "draft",
          ui_hints: {
            context_policy_preset: "task_digest",
            palette_role: "custom",
          },
        },
      ],
    };
    renderWorkspace({
      graph: incompleteGraph,
      selectedNodeId: "node_custom",
    });
    expandInspector();

    expect(
      screen.getByTestId("task-graph-inspector-warning"),
    ).toHaveTextContent(
      "This agent is still missing provider and model settings.",
    );
    expect(
      screen.getByTestId("task-graph-node-kind-node_custom"),
    ).toHaveAttribute("title", "Custom");
  });

  it("saves prompt, schema, tool, and memory settings from the node inspector", () => {
    const onSaveNode = vi.fn();
    renderWorkspace({ onSaveNode });
    expandInspector();

    fireEvent.change(screen.getByTestId("task-graph-inspector-memory-policy"), {
      target: { value: "ephemeral" },
    });
    fireEvent.change(
      screen.getByTestId("task-graph-inspector-prompt-template"),
      {
        target: {
          value: "Summarize {{node_label}} for {{provider_id}} / {{model_id}}.",
        },
      },
    );
    fireEvent.change(screen.getByTestId("task-graph-inspector-output-schema"), {
      target: { value: '{\n  "type": "object",\n  "required": ["matrix"]\n}' },
    });
    fireEvent.change(
      screen.getByTestId("task-graph-inspector-artifact-outputs"),
      {
        target: { value: "validation_report, smoke_matrix" },
      },
    );
    fireEvent.click(
      screen.getByTestId("task-graph-inspector-allow-code-changes"),
    );
    fireEvent.click(
      screen.getByTestId("task-graph-inspector-requires-approval"),
    );
    fireEvent.change(screen.getByTestId("task-graph-inspector-approval-kind"), {
      target: { value: "filesystem_write_gate" },
    });
    fireEvent.click(screen.getByTestId("task-graph-inspector-save"));

    expect(screen.queryByTestId("task-graph-inspector")).not.toBeInTheDocument();
    expandInspector();
    expect(
      screen.getByTestId("task-graph-inspector-prompt-preview"),
    ).toHaveTextContent(
      "Summarize Generate Smoke Matrix for qwen / qwen3-coder-plus.",
    );
    expect(onSaveNode).toHaveBeenCalledWith(
      "node_smoke",
      expect.objectContaining({
        human_summary_template:
          "Summarize {{node_label}} for {{provider_id}} / {{model_id}}.",
        machine_result_schema: {
          type: "object",
          required: ["matrix"],
        },
        ui_hints: expect.objectContaining({
          context_policy_preset: "artifact_first",
          memory_policy_preset: "ephemeral",
        }),
        execution_policy: expect.objectContaining({
          allow_code_changes: true,
          requires_human_approval: true,
        }),
        output_contract: expect.objectContaining({
          artifact_outputs: ["validation_report", "smoke_matrix"],
        }),
        approval_gate: {
          review_kind: "filesystem_write_gate",
        },
      }),
    );
    expect(screen.getByTestId("task-graph-inspector-save")).toBeDisabled();
    expect(screen.getByTestId("task-graph-inspector-reset")).toBeDisabled();

    fireEvent.change(screen.getByTestId("task-graph-inspector-label"), {
      target: { value: "Temporary Label" },
    });
    expect(screen.getByTestId("task-graph-inspector-save")).toBeEnabled();
    fireEvent.click(screen.getByTestId("task-graph-inspector-reset"));
    expect(screen.getByTestId("task-graph-inspector-label")).toHaveValue(
      "Generate Smoke Matrix",
    );
    expect(screen.getByTestId("task-graph-inspector-prompt-template")).toHaveValue(
      "Summarize {{node_label}} for {{provider_id}} / {{model_id}}.",
    );
  });

  it("blocks unknown prompt variables before node save", () => {
    renderWorkspace();
    expandInspector();

    fireEvent.change(
      screen.getByTestId("task-graph-inspector-prompt-template"),
      {
        target: { value: "Use {{missing_variable}} in the summary." },
      },
    );

    expect(
      screen.getByTestId("task-graph-inspector-validation"),
    ).toHaveTextContent("Unknown prompt variables: missing_variable.");
    expect(screen.getByTestId("task-graph-inspector-save")).toBeDisabled();
  });

  it("blocks unsafe tool settings without approval", () => {
    renderWorkspace();
    expandInspector();

    fireEvent.click(screen.getByTestId("task-graph-inspector-allow-install"));

    expect(
      screen.getByTestId("task-graph-inspector-validation"),
    ).toHaveTextContent(
      "Code changes or install access require human approval.",
    );
    expect(screen.getByTestId("task-graph-inspector-save")).toBeDisabled();
  });

  it("adds concise help titles to the primary graph controls", () => {
    renderWorkspace();
    expandSidebar();
    openSidebarPane("edges");

    expect(screen.getByTestId("task-graph-run-live")).toHaveAttribute(
      "title",
      "Start a provider-backed task-graph run and retain per-node artifacts plus parallel execution evidence.",
    );
    expect(screen.getByTestId("task-graph-run-fixture")).toHaveAttribute(
      "title",
      "Use fixture data to validate the graph path without depending on real task context.",
    );
    expect(screen.getByTestId("task-graph-run-dry-run")).toHaveAttribute(
      "title",
      "Validate graph structure, permissions, and route compatibility without starting execution.",
    );
    expect(screen.getByTestId("task-graph-create-edge")).toHaveAttribute(
      "title",
      "Create a new connection between nodes and edit its context policy.",
    );
    expect(screen.getByTestId("task-graph-fit-view")).toHaveAttribute(
      "title",
      "Scale the graph so the current node layout fits within the visible canvas.",
    );
    expect(screen.getByTestId("task-graph-reset-view")).toHaveAttribute(
      "title",
      "Restore the default zoom level and return to the canvas origin.",
    );
  });

  it("keeps icon-only canvas controls named and palette help available on keyboard focus", () => {
    renderWorkspace();

    expect(screen.getByTestId("task-graph-open-run-inspection")).toHaveAccessibleName(
      "Inspect run details",
    );
    expect(screen.getByTestId("task-graph-import")).toHaveAccessibleName(
      "Import",
    );
    expect(screen.getByTestId("task-graph-export")).toHaveAccessibleName(
      "Export",
    );
    expect(screen.getByTestId("task-graph-snapshot")).toHaveAccessibleName(
      "Snapshot",
    );
    expect(screen.getByTestId("task-graph-compare-snapshot")).toHaveAccessibleName(
      "Compare with current graph",
    );
    expect(screen.getByTestId("task-graph-rollback-snapshot")).toHaveAccessibleName(
      "Rollback",
    );
    expect(screen.getByTestId("task-graph-fit-view")).toHaveAccessibleName(
      "Fit view",
    );
    expect(screen.getByTestId("task-graph-reset-view")).toHaveAccessibleName(
      "Reset view",
    );
    expect(screen.getByTestId("task-graph-zoom-out")).toHaveAccessibleName(
      "Zoom out to inspect more of the graph at once.",
    );
    expect(screen.getByTestId("task-graph-zoom-in")).toHaveAccessibleName(
      "Zoom in for more precise node and edge edits.",
    );

    expandSidebar();
    openSidebarPane("nodes");
    const supervisor = screen.getByTestId("task-graph-palette-add-supervisor");
    fireEvent.focus(supervisor);

    expect(supervisor).toHaveAccessibleName("Supervisor");
    expect(supervisor).toHaveAttribute(
      "aria-describedby",
      "task-graph-palette-tooltip-supervisor",
    );
    expect(screen.getByTestId("task-graph-palette-tooltip-supervisor")).toHaveAttribute(
      "role",
      "tooltip",
    );
    expect(supervisor).toHaveClass("task-graph-palette-item-hover");
  });

  it("dispatches import and export actions from visible toolbar controls", () => {
    const onImportGraph = vi.fn();
    const onExportGraph = vi.fn();
    renderWorkspace({ onImportGraph, onExportGraph });

    fireEvent.click(screen.getByTestId("task-graph-import"));
    fireEvent.click(screen.getByTestId("task-graph-export"));

    expect(onImportGraph).toHaveBeenCalledTimes(1);
    expect(onExportGraph).toHaveBeenCalledTimes(1);
  });

  it("shows import-export status after a round-trip action", () => {
    renderWorkspace({
      lastImportedPath: "examples/agent-orchestration/code_fix_review.json",
      lastExportedPath:
        "PRIVATE/agent-orchestration/productization/step7/20260707/graph_test.json",
      lastExportPreview:
        '{\n  "schema_version": "astrabridge-agent-orchestration-v1"\n}\n',
    });

    expect(
      screen.getByTestId("task-graph-import-export-status"),
    ).toHaveTextContent(
      "Imported: examples/agent-orchestration/code_fix_review.json",
    );
    expect(
      screen.getByTestId("task-graph-import-export-status"),
    ).toHaveTextContent(
      "Exported: PRIVATE/agent-orchestration/productization/step7/20260707/graph_test.json",
    );
    expect(
      screen.getByTestId("task-graph-last-export-preview"),
    ).toHaveTextContent("Export preview: 3 lines");
  });

  it("updates the canvas scale through fit, zoom, and reset controls", () => {
    renderWorkspace();

    const canvas = screen.getByTestId("task-graph-canvas");
    const stage = screen.getByTestId("task-graph-stage");
    Object.defineProperty(canvas, "clientWidth", {
      value: 640,
      configurable: true,
    });
    Object.defineProperty(canvas, "clientHeight", {
      value: 360,
      configurable: true,
    });
    canvas.scrollTo = vi.fn();

    fireEvent.click(screen.getByTestId("task-graph-zoom-out"));
    expect(stage).toHaveAttribute("data-canvas-scale", "0.85");

    fireEvent.click(screen.getByTestId("task-graph-zoom-in"));
    expect(stage).toHaveAttribute("data-canvas-scale", "1.00");

    fireEvent.click(screen.getByTestId("task-graph-fit-view"));
    expect(Number(stage.getAttribute("data-canvas-scale"))).toBeLessThan(1);

    fireEvent.click(screen.getByTestId("task-graph-reset-view"));
    expect(stage).toHaveAttribute("data-canvas-scale", "1.00");
  });

  it("renders the zh-CN task-graph shell structure", () => {
    renderWorkspace({
      locale: "zh-CN",
      graph: null,
      selectedNodeId: null,
      selectedEdgeId: null,
    });

    expect(screen.getByTestId("task-graph-canvas")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-close")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-empty")).toBeInTheDocument();
  });

  it("renders stable node role and status pills for at-a-glance canvas scanning", () => {
    renderWorkspace({
      dryRunResult,
    });

    expect(screen.getByTestId("task-graph-node-node_discover")).toHaveAttribute(
      "data-node-kind",
      "extractor",
    );
    expect(
      screen.getByTestId("task-graph-node-kind-node_discover"),
    ).toHaveAttribute("title", "Extractor");
    expect(
      screen.getByTestId("task-graph-node-status-node_smoke"),
    ).toHaveTextContent("warning");
    expect(
      screen.getByTestId("task-graph-node-node_smoke").className,
    ).toContain("task-graph-node-tone-validator");
  });

  it("saves edited node configuration through the inspector", () => {
    const onSaveNode = vi.fn();
    renderWorkspace({ onSaveNode });
    expandInspector();

    fireEvent.change(screen.getByTestId("task-graph-inspector-provider"), {
      target: { value: "kimi" },
    });
    fireEvent.change(screen.getByTestId("task-graph-inspector-model"), {
      target: { value: "kimi-k2.6" },
    });
    fireEvent.change(
      screen.getByTestId("task-graph-inspector-context-policy"),
      { target: { value: "isolated_artifacts_only" } },
    );
    fireEvent.click(screen.getByTestId("task-graph-inspector-save"));

    expect(onSaveNode).toHaveBeenCalledWith(
      "node_smoke",
      expect.objectContaining({
        provider_id: "kimi",
        model_id: "kimi-k2.6",
        ui_hints: expect.objectContaining({
          context_policy_preset: "isolated_artifacts_only",
          memory_policy_preset: "default",
        }),
      }),
    );
  });

  it("shows validation when a model is set without a provider", () => {
    renderWorkspace();
    expandInspector();

    fireEvent.change(screen.getByTestId("task-graph-inspector-provider"), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByTestId("task-graph-inspector-model"), {
      target: { value: "qwen3-coder-plus" },
    });

    expect(
      screen.getByTestId("task-graph-inspector-validation"),
    ).toHaveTextContent("Provider is required");
  });

  it("inserts an upstream prompt variable and renders node payload preview", () => {
    renderWorkspace();
    expandInspector();

    fireEvent.click(
      screen.getByTestId("task-graph-prompt-variable-upstream_node_labels"),
    );

    expect(
      screen.getByTestId("task-graph-inspector-prompt-template"),
    ).toHaveValue("{{upstream_node_labels}}");
    expect(
      screen.getByTestId("task-graph-inspector-prompt-preview"),
    ).toHaveTextContent("Discover Provider Update");
    expect(
      screen.getByTestId("task-graph-inspector-payload-preview"),
    ).toHaveTextContent('"upstream_context"');
    expect(
      screen.getByTestId("task-graph-inspector-payload-preview"),
    ).toHaveTextContent("Discover Provider Update");
  });

  it("shows schema validation feedback for invalid JSON schema text", () => {
    renderWorkspace();
    expandInspector();

    fireEvent.change(screen.getByTestId("task-graph-inspector-output-schema"), {
      target: { value: '{"type":"object"' },
    });

    expect(
      screen.getByTestId("task-graph-inspector-validation"),
    ).toHaveTextContent("Output schema must be a valid JSON object.");
    expect(screen.getByTestId("task-graph-inspector-save")).toBeDisabled();
  });

  it("edits an existing edge through the edge inspector", () => {
    const onSaveEdge = vi.fn();
    renderWorkspace({
      selectedEdgeId: "edge_discover_smoke",
      onSaveEdge,
    });
    expandInspector();

    fireEvent.change(screen.getByTestId("task-graph-edge-history-length"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByTestId("task-graph-edge-message-template"), {
      target: { value: "Deliver the latest smoke bundle to the validator." },
    });
    fireEvent.change(screen.getByTestId("task-graph-edge-included-artifacts"), {
      target: { value: "required_output, smoke_matrix" },
    });
    fireEvent.change(screen.getByTestId("task-graph-edge-resource-refs"), {
      target: {
        value:
          "PRIVATE/provider-smoke/latest.json\nPRIVATE/provider-smoke/summary.md",
      },
    });
    fireEvent.click(screen.getByTestId("task-graph-edge-save"));

    expect(onSaveEdge).toHaveBeenCalledWith(
      expect.objectContaining({
        edge_id: "edge_discover_smoke",
        handoff_contract: expect.objectContaining({
          message_template: "Deliver the latest smoke bundle to the validator.",
          message_part_modes: ["machine_result", "human_summary"],
          required_output_schema_refs: ["schema.node_discover.machine_result"],
          port_bindings: [
            { from_port_id: "machine_result", to_port_id: "discover_result" },
            { from_port_id: "diff_bundle", to_port_id: "diff_bundle" },
          ],
        }),
        context_policy: expect.objectContaining({
          history_length: 3,
          included_artifacts: ["smoke_matrix"],
          resource_refs: [
            "PRIVATE/provider-smoke/latest.json",
            "PRIVATE/provider-smoke/summary.md",
          ],
        }),
      }),
    );
    expect(screen.queryByTestId("task-graph-inspector")).not.toBeInTheDocument();
    expandInspector();
    expect(screen.getByTestId("task-graph-edge-save")).toBeDisabled();
    expect(screen.getByTestId("task-graph-edge-reset")).toBeDisabled();

    fireEvent.change(screen.getByTestId("task-graph-edge-message-template"), {
      target: { value: "Temporary handoff copy." },
    });
    expect(screen.getByTestId("task-graph-edge-save")).toBeEnabled();
    fireEvent.click(screen.getByTestId("task-graph-edge-reset"));
    expect(screen.getByTestId("task-graph-edge-message-template")).toHaveValue(
      "Deliver the latest smoke bundle to the validator.",
    );
  });

  it("shows source-target typed compatibility details for edge editing", () => {
    renderWorkspace({
      selectedEdgeId: "edge_discover_smoke",
    });
    expandInspector();

    expect(
      screen.getByTestId("task-graph-edge-compatibility-status"),
    ).toHaveTextContent("Typed ports can connect.");
    expect(
      screen.getByTestId("task-graph-edge-compatibility-source"),
    ).toHaveTextContent("Diff Bundle");
    expect(
      screen.getByTestId("task-graph-edge-compatibility-target"),
    ).toHaveTextContent("Discover Result");
    expect(
      screen.getByTestId("task-graph-edge-compatibility-matches"),
    ).toHaveTextContent("Machine Result");
  });

  it("inserts edge message variables and renders the downstream payload preview", () => {
    renderWorkspace({
      selectedEdgeId: "edge_discover_smoke",
    });
    expandInspector();

    fireEvent.click(
      screen.getByTestId("task-graph-edge-variable-source_node_label"),
    );

    expect(screen.getByTestId("task-graph-edge-message-template")).toHaveValue(
      "Deliver the required output from node_discover to node_smoke. {{source_node_label}}",
    );
    expect(
      screen.getByTestId("task-graph-edge-payload-preview"),
    ).toHaveTextContent('"resolved_message"');
    expect(
      screen.getByTestId("task-graph-edge-payload-preview"),
    ).toHaveTextContent("Discover Provider Update");
    expect(
      screen.getByTestId("task-graph-edge-payload-preview"),
    ).toHaveTextContent('"required_output_schema_refs"');
  });

  it("keeps compact edge glyphs visible and expands emphasis for the active edge", () => {
    renderWorkspace({
      dryRunResult,
      selectedEdgeId: "edge_discover_smoke",
    });

    expect(
      screen.getByTestId("task-graph-canvas-edge-chip-edge_discover_smoke"),
    ).toBeInTheDocument();
    expect(
      screen
        .getByTestId("task-graph-canvas-edge-chip-edge_discover_smoke")
        .getAttribute("class"),
    ).toContain("task-graph-canvas-edge-chip-active");
    expect(
      screen
        .getByTestId("task-graph-canvas-edge-chip-edge_discover_smoke")
        .getAttribute("class"),
    ).toContain("task-graph-canvas-edge-chip-expanded");
    expect(
      screen
        .getByTestId("task-graph-edge-edge_discover_smoke")
        .getAttribute("class"),
    ).toContain("task-graph-edge-active");
    expect(
      screen
        .getByTestId("task-graph-edge-edge_discover_smoke")
        .getAttribute("class"),
    ).toContain("task-graph-edge-pass");
  });

  it("selects an edge directly from the canvas hit path", () => {
    const onSelectEdge = vi.fn();
    renderWorkspace({ onSelectEdge });

    fireEvent.click(
      screen.getByTestId("task-graph-edge-hit-edge_discover_smoke"),
    );

    expect(onSelectEdge).toHaveBeenCalledWith("edge_discover_smoke");
  });

  it("starts a direct canvas connection from a node output and completes it on the target node", () => {
    renderWorkspace({
      selectedNodeId: "node_discover",
      selectedEdgeId: null,
    });

    fireEvent.click(screen.getByTestId("task-graph-node-output-node_discover"));
    fireEvent.click(screen.getByTestId("task-graph-node-input-node_smoke"));

    expect(screen.getByTestId("task-graph-edge-from")).toHaveValue(
      "node_discover",
    );
    expect(screen.getByTestId("task-graph-edge-to")).toHaveValue(
      "node_smoke",
    );
    expect(
      screen.getByTestId("task-graph-node-node_discover").className,
    ).toContain("task-graph-node-card-connection-source");
  });

  it("uses labelled direction icons instead of in/out text for node ports", () => {
    renderWorkspace();

    const inputPort = screen.getByTestId("task-graph-node-input-node_discover");
    const outputPort = screen.getByTestId("task-graph-node-output-node_discover");

    expect(inputPort).toHaveAccessibleName(/Inputs:/);
    expect(outputPort).toHaveAccessibleName(/Outputs:/);
    expect(inputPort).not.toHaveTextContent(/^in$/i);
    expect(outputPort).not.toHaveTextContent(/^out$/i);
  });

  it("deletes an edge from the canvas with a context-menu gesture", () => {
    const onDeleteEdge = vi.fn();
    renderWorkspace({ onDeleteEdge });

    fireEvent.contextMenu(
      screen.getByTestId("task-graph-edge-hit-edge_discover_smoke"),
    );

    expect(onDeleteEdge).toHaveBeenCalledWith("edge_discover_smoke");
  });

  it("creates a new edge from gui controls", () => {
    const onSaveEdge = vi.fn();
    renderWorkspace({ onSaveEdge });
    expandSidebar();
    openSidebarSection("Edges");
    expandInspector();

    fireEvent.click(screen.getByTestId("task-graph-create-edge"));
    fireEvent.change(screen.getByTestId("task-graph-edge-to"), {
      target: { value: "node_gate" },
    });
    fireEvent.change(screen.getByTestId("task-graph-edge-type"), {
      target: { value: "approval_dependency" },
    });
    fireEvent.click(screen.getByTestId("task-graph-edge-save"));

    expect(onSaveEdge).toHaveBeenCalledWith(
      expect.objectContaining({
        edge_id: undefined,
        to_node_id: "node_gate",
        edge_type: "approval_dependency",
        handoff_contract: expect.objectContaining({
          required_output_schema_refs: ["schema.node_smoke.machine_result"],
          port_bindings: [
            { from_port_id: "smoke_matrix", to_port_id: "smoke_matrix" },
          ],
        }),
        context_policy: expect.objectContaining({
          included_artifacts: [],
        }),
      }),
    );
  });

  it("hides required_output placeholders for required-output-only edges", () => {
    renderWorkspace({
      selectedEdgeId: "edge_discover_smoke",
    });
    expandInspector();

    expect(
      screen.getByTestId("task-graph-edge-included-artifacts"),
    ).toHaveValue("");
  });

  it("starts create-edge mode from the explicit create-edge control", () => {
    renderWorkspace();
    expandSidebar();
    openSidebarSection("Edges");

    fireEvent.click(screen.getByTestId("task-graph-create-edge"));

    expect(screen.getByTestId("task-graph-edge-from")).toHaveValue(
      "node_smoke",
    );
    expect(
      screen.getByTestId("task-graph-node-node_smoke").className,
    ).toContain("task-graph-node-card-connection-source");
  });

  it("selects the edge target directly from another canvas node while creating", () => {
    renderWorkspace();
    expandSidebar();
    openSidebarSection("Edges");

    fireEvent.click(screen.getByTestId("task-graph-create-edge"));
    fireEvent.click(screen.getByTestId("task-graph-node-node_gate"));

    expect(screen.getByTestId("task-graph-edge-to")).toHaveValue("node_gate");
  });

  it("blocks same-node edge creation when the source node is reused as the target", () => {
    renderWorkspace();
    expandSidebar();
    openSidebarSection("Edges");

    fireEvent.click(screen.getByTestId("task-graph-create-edge"));
    fireEvent.change(screen.getByTestId("task-graph-edge-to"), {
      target: { value: "node_smoke" },
    });

    expect(screen.getByTestId("task-graph-edge-validation")).toHaveTextContent(
      "Source and target must be different nodes.",
    );
    expect(screen.getByTestId("task-graph-edge-save")).toBeDisabled();
  });

  it("moves a node through mouse drag interactions", () => {
    const onMoveNode = vi.fn();
    renderWorkspace({ onMoveNode });

    const node = screen.getByTestId("task-graph-node-node_smoke");
    fireEvent.mouseDown(node, { button: 0, clientX: 380, clientY: 180 });
    fireEvent.mouseMove(window, { clientX: 452, clientY: 236 });
    fireEvent.mouseUp(window, { clientX: 452, clientY: 236 });

    expect(onMoveNode).toHaveBeenCalledWith(
      "node_smoke",
      expect.objectContaining({
        x: expect.any(Number),
        y: expect.any(Number),
      }),
    );
  });

  it("stays in create-edge mode even when another edge is selected", () => {
    const onSaveEdge = vi.fn();
    renderWorkspace({
      selectedEdgeId: "edge_discover_smoke",
      onSaveEdge,
    });
    expandSidebar();
    openSidebarSection("Edges");
    expandInspector();

    fireEvent.click(screen.getByTestId("task-graph-create-edge"));
    fireEvent.change(screen.getByTestId("task-graph-edge-to"), {
      target: { value: "node_gate" },
    });
    fireEvent.change(screen.getByTestId("task-graph-edge-type"), {
      target: { value: "approval_dependency" },
    });
    fireEvent.click(screen.getByTestId("task-graph-edge-save"));

    expect(onSaveEdge).toHaveBeenCalledWith(
      expect.objectContaining({
        edge_id: undefined,
        to_node_id: "node_gate",
        edge_type: "approval_dependency",
      }),
    );
  });

  it("blocks invalid edge policy edits before saving", () => {
    renderWorkspace({
      selectedEdgeId: "edge_discover_smoke",
    });
    expandInspector();

    fireEvent.click(
      screen.getByTestId("task-graph-edge-exclude-private-memory"),
    );

    expect(screen.getByTestId("task-graph-edge-validation")).toHaveTextContent(
      "Private memory exclusion is required",
    );
    expect(screen.getByTestId("task-graph-edge-save")).toBeDisabled();
  });

  it("blocks invalid handoff contract edits before saving", () => {
    renderWorkspace({
      selectedEdgeId: "edge_discover_smoke",
    });
    expandInspector();

    fireEvent.change(
      screen.getByTestId("task-graph-edge-required-schema-refs"),
      { target: { value: "" } },
    );

    expect(screen.getByTestId("task-graph-edge-validation")).toHaveTextContent(
      "At least one required input schema ref is required.",
    );
    expect(screen.getByTestId("task-graph-edge-save")).toBeDisabled();
  });

  it("blocks incompatible typed connections during edge creation and marks the target node", () => {
    const incompatibleGraph: TaskGraphDefinition = {
      ...graph,
      orchestration_graph: {
        ...graph.orchestration_graph!,
        nodes: [
          {
            node_id: "node_discover",
            ports: {
              inputs: [{ port_id: "task_context", label: "Task Context", port_type: "text" }],
              outputs: [{ port_id: "audio_clip", label: "Audio Clip", port_type: "audio" }],
            },
          },
          {
            node_id: "node_smoke",
            ports: {
              inputs: [{ port_id: "policy_doc", label: "Policy Doc", port_type: "document" }],
              outputs: [{ port_id: "smoke_matrix", label: "Smoke Matrix", port_type: "dataset" }],
            },
          },
          {
            node_id: "node_gate",
            ports: {
              inputs: [{ port_id: "approval_record", label: "Approval", port_type: "approval_record" }],
              outputs: [{ port_id: "approval_record", label: "Approval", port_type: "approval_record" }],
            },
          },
        ],
        edges: [],
      },
      edges: [],
    };

    renderWorkspace({
      graph: incompatibleGraph,
      selectedNodeId: "node_discover",
      selectedEdgeId: null,
    });
    expandSidebar();
    openSidebarSection("Edges");
    expandInspector();

    fireEvent.click(screen.getByTestId("task-graph-create-edge"));
    fireEvent.change(screen.getByTestId("task-graph-edge-to"), {
      target: { value: "node_smoke" },
    });

    expect(screen.getByTestId("task-graph-edge-validation")).toHaveTextContent(
      "No compatible typed ports",
    );
    expect(
      screen.getByTestId("task-graph-edge-compatibility-status"),
    ).toHaveTextContent("No compatible typed ports");
    expect(
      screen.getByTestId("task-graph-node-node_smoke").className,
    ).toContain("task-graph-node-card-incompatible-target");
    expect(screen.getByTestId("task-graph-edge-save")).toBeDisabled();
  });

  it("renders dry-run readiness state and opens the report link", () => {
    const onRunDryRun = vi.fn();
    const crowdedDryRunResult: TaskGraphDryRunResult = {
      ...dryRunResult,
      graph_result: {
        ...dryRunResult.graph_result,
        reasons: [
          "Provider is set without a pinned model; route resolution is under-specified.",
          "Node prompt is missing.",
          "Provider calls are disabled.",
          "Entry node is not declared.",
          "Output contract is incomplete.",
          "Live execution requires an explicit node prompt; generic fallback prompts are not allowed.",
        ],
      },
    };
    renderWorkspace({
      dryRunResult: crowdedDryRunResult,
      reportHref: "/artifacts/task-graph/report.md",
      onRunDryRun,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-dry-run-panel")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-dry-run-summary")).toHaveTextContent(
      "1 / 1 / 1",
    );
    expect(screen.getByTestId("task-graph-dry-run-summary")).toHaveAttribute(
      "title",
      "1 pass / 1 warning / 1 blocked\nShowing 3 of 6",
    );
    expect(
      screen.getByTestId("task-graph-dry-run-preview-meta"),
    ).toHaveTextContent("Showing 3 of 6");
    const reasonsList = screen.getByTestId("task-graph-dry-run-reasons");
    expect(within(reasonsList).getAllByRole("listitem")).toHaveLength(3);
    expect(reasonsList).toHaveTextContent(
      "Provider is set without a pinned model",
    );
    expect(reasonsList).toHaveTextContent("Provider calls are disabled.");
    expect(screen.queryByText("Entry node is not declared.")).not.toBeInTheDocument();

    const reasonsToggle = screen.getByTestId(
      "task-graph-dry-run-reasons-toggle",
    );
    expect(reasonsToggle).toHaveAttribute("aria-expanded", "false");
    expect(reasonsToggle).toHaveAccessibleName("3 more");
    fireEvent.click(reasonsToggle);
    expect(screen.getByText("Entry node is not declared.")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("task-graph-dry-run-reasons")).getAllByRole(
        "listitem",
      ),
    ).toHaveLength(6);
    expect(reasonsToggle).toHaveAttribute("aria-expanded", "true");
    expect(reasonsToggle).toHaveAccessibleName("Show less");
    fireEvent.click(reasonsToggle);
    expect(screen.queryByText("Entry node is not declared.")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-node-node_smoke").className,
    ).toContain("task-graph-node-card-warning");
    expect(
      screen
        .getByTestId("task-graph-edge-edge_discover_smoke")
        .getAttribute("class"),
    ).toContain("task-graph-edge-pass");
    expect(
      screen.getByTestId("task-graph-open-dry-run-report"),
    ).toHaveAttribute("href", "/artifacts/task-graph/report.md");

    fireEvent.click(screen.getByTestId("task-graph-run-dry-run"));
    expect(onRunDryRun).toHaveBeenCalledWith({ tokenBudget: 80_000 });
  });

  it("deduplicates repeated dry-run reasons before applying the collapsed preview", () => {
    const repeatedDryRunResult: TaskGraphDryRunResult = {
      ...dryRunResult,
      graph_result: {
        ...dryRunResult.graph_result,
        reasons: [
          "Live execution requires an explicit node prompt; generic fallback prompts are not allowed.",
          "Live execution requires an explicit node prompt; generic fallback prompts are not allowed.",
          "Live execution requires an explicit node prompt; generic fallback prompts are not allowed.",
          "Provider calls are disabled.",
          "Output contract is incomplete.",
          "Entry node is not declared.",
        ],
      },
    };

    renderWorkspace({ dryRunResult: repeatedDryRunResult });
    expandInspector();

    const reasonsList = screen.getByTestId("task-graph-dry-run-reasons");
    expect(within(reasonsList).getAllByRole("listitem")).toHaveLength(3);
    expect(reasonsList).toHaveTextContent("Live execution requires an explicit node prompt");
    expect(reasonsList).toHaveTextContent("x3");
    expect(screen.queryByText("Entry node is not declared.")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-dry-run-reasons-toggle"),
    ).toHaveAccessibleName("1 more");
  });

  it("normalizes whitespace when deduplicating dry-run reasons", () => {
    const repeatedDryRunResult: TaskGraphDryRunResult = {
      ...dryRunResult,
      graph_result: {
        ...dryRunResult.graph_result,
        reasons: [
          "Live execution requires an explicit node prompt; generic fallback prompts are not allowed.",
          "Live   execution requires an explicit node prompt;  generic fallback prompts are not allowed.",
          "Live execution requires an explicit node prompt ; generic fallback prompts are not allowed.",
          "Provider calls are disabled.",
          "Output contract is incomplete.",
          "Entry node is not declared.",
        ],
      },
    };

    renderWorkspace({ dryRunResult: repeatedDryRunResult });
    expandInspector();

    const reasonsList = screen.getByTestId("task-graph-dry-run-reasons");
    expect(within(reasonsList).getAllByRole("listitem")).toHaveLength(3);
    expect(reasonsList).toHaveTextContent("Live execution requires an explicit node prompt");
    expect(reasonsList).toHaveTextContent("x3");
    expect(screen.queryByText("Entry node is not declared.")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-dry-run-reasons-toggle"),
    ).toHaveAccessibleName("1 more");
  });

  it("re-collapses dry-run reasons when a new result arrives", () => {
    const firstDryRunResult: TaskGraphDryRunResult = {
      ...dryRunResult,
      graph_result: {
        ...dryRunResult.graph_result,
        reasons: [
          "Provider is set without a pinned model; route resolution is under-specified.",
          "Node prompt is missing.",
          "Provider calls are disabled.",
          "Entry node is not declared.",
        ],
      },
    };
    const secondDryRunResult: TaskGraphDryRunResult = {
      ...firstDryRunResult,
      graph_result: {
        ...firstDryRunResult.graph_result,
        reasons: [
          "New run: provider is still not pinned.",
          "New run: node prompt is missing.",
          "New run: provider calls are disabled.",
          "New run: entry node is not declared.",
        ],
      },
    };
    const view = renderWorkspace({ dryRunResult: firstDryRunResult });
    expandInspector();

    fireEvent.click(screen.getByTestId("task-graph-dry-run-reasons-toggle"));
    expect(screen.getByText("Entry node is not declared.")).toBeInTheDocument();

    view.rerender(
      <TaskGraphWorkspace
        {...buildWorkspaceProps({ dryRunResult: secondDryRunResult })}
      />,
    );

    expect(
      screen.getByTestId("task-graph-dry-run-reasons-toggle"),
    ).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByText("New run: entry node is not declared."),
    ).not.toBeInTheDocument();
  });

  it("re-collapses dry-run reasons when a new run keeps the same reasons", () => {
    const firstDryRunResult: TaskGraphDryRunResult = {
      ...dryRunResult,
      run_id: "graph-dry-run-a",
      graph_result: {
        ...dryRunResult.graph_result,
        reasons: [
          "Live execution requires an explicit node prompt; generic fallback prompts are not allowed.",
          "Provider calls are disabled.",
          "Entry node is not declared.",
          "Output contract is incomplete.",
        ],
      },
    };
    const secondDryRunResult: TaskGraphDryRunResult = {
      ...firstDryRunResult,
      run_id: "graph-dry-run-b",
      created_at: "2026-07-07T00:06:30+09:00",
    };
    const view = renderWorkspace({ dryRunResult: firstDryRunResult });
    expandInspector();

    fireEvent.click(screen.getByTestId("task-graph-dry-run-reasons-toggle"));
    expect(screen.getByText("Output contract is incomplete.")).toBeInTheDocument();

    view.rerender(
      <TaskGraphWorkspace
        {...buildWorkspaceProps({ dryRunResult: secondDryRunResult })}
      />,
    );

    expect(
      screen.getByTestId("task-graph-dry-run-reasons-toggle"),
    ).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByText("Output contract is incomplete."),
    ).not.toBeInTheDocument();
  });

  it("uses the compact token limit for dry-run and live-run requests", () => {
    const onRunDryRun = vi.fn();
    const onRunLive = vi.fn();
    renderWorkspace({ onRunDryRun, onRunLive });
    const budgetInput = screen.getByTestId("task-graph-run-token-budget");

    fireEvent.change(budgetInput, { target: { value: "42000" } });
    fireEvent.click(screen.getByTestId("task-graph-run-dry-run"));
    fireEvent.click(screen.getByTestId("task-graph-run-live"));

    expect(onRunDryRun).toHaveBeenCalledWith({ tokenBudget: 42_000 });
    expect(onRunLive).toHaveBeenCalledWith({ tokenBudget: 42_000 });
  });

  it("opens the run inspector when dry-run is triggered from the toolbar", () => {
    const onRunDryRun = vi.fn();
    renderWorkspace({
      onRunDryRun,
      selectedNodeId: null,
      selectedEdgeId: null,
    });

    fireEvent.click(screen.getByTestId("task-graph-run-dry-run"));
    expect(onRunDryRun).toHaveBeenCalledTimes(1);
    expect(
      screen.getByTestId("task-graph-inspector-toggle"),
    ).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByTestId("task-graph-inspector-workspace-run"),
    ).toHaveAttribute("aria-selected", "true");
  });

  it("triggers fixture run from the toolbar", () => {
    const onRunLive = vi.fn();
    const onRunFixture = vi.fn();
    const onRunCancellableFixture = vi.fn();
    renderWorkspace({
      graph: { ...graph, template_id: "fanout_fanin_research" },
      onRunLive,
      onRunFixture,
      onRunCancellableFixture,
    });

    fireEvent.click(screen.getByTestId("task-graph-run-live"));
    fireEvent.click(screen.getByTestId("task-graph-run-fixture"));
    fireEvent.click(screen.getByTestId("task-graph-run-cancellable-fixture"));

    expect(onRunLive).toHaveBeenCalledWith({ tokenBudget: 80_000 });
    expect(onRunFixture).toHaveBeenCalledTimes(1);
    expect(onRunCancellableFixture).toHaveBeenCalledTimes(1);
  });

  it("does not dispatch dry-run when direct-run is clicked", () => {
    const onRunLive = vi.fn();
    const onRunDryRun = vi.fn();
    renderWorkspace({
      onRunLive,
      onRunDryRun,
    });

    fireEvent.click(screen.getByTestId("task-graph-run-live"));

    expect(onRunLive).toHaveBeenCalledTimes(1);
    expect(onRunLive).toHaveBeenCalledWith({ tokenBudget: 80_000 });
    expect(onRunDryRun).not.toHaveBeenCalled();
  });

  it("dispatches direct-run from the standard button click", () => {
    const onRunLive = vi.fn();
    renderWorkspace({ onRunLive });
    const liveButton = screen.getByTestId("task-graph-run-live");

    fireEvent.click(liveButton);

    expect(onRunLive).toHaveBeenCalledTimes(1);
    expect(onRunLive).toHaveBeenCalledWith({ tokenBudget: 80_000 });
  });

  it("dispatches dry-run from the standard keyboard click sequence", () => {
    const onRunDryRun = vi.fn();
    renderWorkspace({ onRunDryRun });
    const dryRunButton = screen.getByTestId("task-graph-run-dry-run");

    fireEvent.keyDown(dryRunButton, { key: "Enter" });
    fireEvent.click(dryRunButton);

    expect(onRunDryRun).toHaveBeenCalledTimes(1);
    expect(onRunDryRun).toHaveBeenCalledWith({ tokenBudget: 80_000 });
  });

  it("disables run toolbar actions when the app provides a blocked-run reason", () => {
    renderWorkspace({
      runActionDisabledReason:
        "任务图运行已被阻止：任务图运行路由当前不可用。请刷新任务图或检查 sidecar 路由状态后重试。",
    });

    expect(screen.getByTestId("task-graph-run-live")).toBeDisabled();
    expect(screen.getByTestId("task-graph-run-dry-run")).toBeDisabled();
  });

  it("renders latest worker output artifacts and downstream handoff chips", () => {
    renderWorkspace({
      latestRunRef,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-run-panel")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-run-id")).toHaveTextContent(
      "graph-run-worker-1",
    );
    expect(
      screen.getByTestId("task-graph-worker-node_smoke"),
    ).toHaveTextContent("Smoke worker");
    expect(
      screen.getByTestId("task-graph-worker-handoffs-node_smoke"),
    ).toHaveTextContent("approval_dependency");
    expect(
      screen.getByTestId(
        "task-graph-worker-artifact-node_smoke-thread-worker-1-summary-md",
      ),
    ).toHaveTextContent("text_report: summary.md");
    expect(screen.getByTestId("task-graph-replay-fixture")).toBeInTheDocument();
  });

  it("restores the run inspection workspace after remounting the same graph", () => {
    const firstRender = renderWorkspace({
      latestRunRef,
      selectedNodeId: null,
    });
    expandInspector();

    fireEvent.click(screen.getByText("Latest run"));
    expect(screen.getByTestId("task-graph-run-meta")).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-inspector-toggle"),
    ).toHaveAttribute("aria-expanded", "true");

    firstRender.unmount();

    renderWorkspace({
      latestRunRef,
      selectedNodeId: null,
    });

    expect(
      screen.getByTestId("task-graph-inspector-toggle"),
    ).toHaveAttribute("aria-expanded", "false");
    expandInspector();
    expect(
      screen.getByTestId("task-graph-inspector-workspace-run"),
    ).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("task-graph-run-meta")).toBeInTheDocument();
  });

  it("shows node-scoped run details in the selection workspace for the selected node", () => {
    renderWorkspace({
      latestRunRef,
      selectedNodeId: "node_smoke",
    });
    expandInspector();
    fireEvent.click(screen.getByTestId("task-graph-inspector-workspace-selection"));

    expect(
      screen.getByTestId("task-graph-selection-node-run-panel"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-selection-node-run-status"),
    ).toHaveTextContent("completed");
    expect(
      screen.getByTestId("task-graph-selection-node-run-summary"),
    ).toHaveTextContent("Worker produced a smoke matrix");
    expect(
      screen.getByTestId("task-graph-selection-node-run-hints"),
    ).toHaveTextContent("Route gate to the updated provider set.");
  });

  it("shows edge-scoped handoff details and a canvas runtime badge for the selected edge", () => {
    renderWorkspace({
      selectedNodeId: null,
      selectedEdgeId: "edge_discover_smoke",
      latestRunRef: {
        ...latestRunRef,
        timeline_events: [
          ...(latestRunRef.timeline_events ?? []),
          {
            event_id: "graph-run-worker-1-edge-discover-smoke",
            event_type: "handoff_created",
            created_at: "2026-07-07T00:06:40+09:00",
            summary: "Discover handoff delivered to smoke matrix.",
            edge_id: "edge_discover_smoke",
            status: "completed",
          },
        ],
        worker_bindings: [
          {
            ...latestRunRef.worker_bindings![0],
            downstream_handoffs: [
              {
                edge_id: "edge_discover_smoke",
                to_node_id: "node_smoke",
                edge_type: "artifact_handoff",
                context_policy: {
                  history_mode: "latest_summary_only",
                  artifact_mode: "required_output_only",
                  exclude_private_memory: true,
                  include_machine_results: true,
                  include_human_summaries: true,
                  summary_strategy: "human_summary_only",
                  history_length: 1,
                  included_artifacts: ["required_output"],
                  resource_refs: [],
                },
                downstream_input: {
                  source: "worker_output_envelope",
                  run_id: "graph-run-worker-1",
                  artifact_paths: [
                    "PRIVATE/task-graph/workers/graph-run-worker-1/node_discover/output.json",
                  ],
                  human_summary_path:
                    "PRIVATE/task-graph/workers/graph-run-worker-1/node_discover/summary.md",
                  machine_result_path:
                    "PRIVATE/task-graph/workers/graph-run-worker-1/node_discover/output.json",
                },
              },
            ],
          },
        ],
      },
    });
    expandInspector();
    fireEvent.click(screen.getByTestId("task-graph-inspector-workspace-selection"));

    expect(
      screen.getByTestId("task-graph-selection-edge-run-panel"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-selection-edge-run-status"),
    ).toHaveTextContent("completed");
    expect(
      screen.getByTestId("task-graph-selection-edge-run-handoff"),
    ).toHaveTextContent("worker_output_envelope");
    expect(
      screen.getByTestId("task-graph-selection-edge-run-event"),
    ).toHaveTextContent("Discover handoff delivered to smoke matrix.");
    expect(
      screen.getByTestId("task-graph-canvas-edge-status-edge_discover_smoke"),
    ).toHaveTextContent("done");
  });

  it("opens run artifacts through the in-app inspector callback", () => {
    const onInspectArtifactPath = vi.fn();
    renderWorkspace({
      latestRunRef,
      onInspectArtifactPath,
    });
    expandInspector();

    fireEvent.click(
      screen.getByTestId(
        "task-graph-worker-artifact-node_smoke-thread-worker-1-summary-md",
      ),
    );

    expect(onInspectArtifactPath).toHaveBeenCalledWith(
      "PRIVATE/task-graph/workers/graph-run-worker-1/node_smoke/summary.md",
    );
  });

  it("renders pending approval state and dispatches approve and reject actions", () => {
    const onApprovePendingRun = vi.fn();
    const onRejectPendingRun = vi.fn();
    renderWorkspace({
      latestRunRef: pendingApprovalRunRef,
      onApprovePendingRun,
      onRejectPendingRun,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-approval-panel")).toHaveTextContent(
      "Approval required",
    );
    expect(screen.getByTestId("task-graph-approval-reason")).toHaveTextContent(
      "requires human approval",
    );

    fireEvent.click(screen.getByTestId("task-graph-approval-approve"));
    fireEvent.click(screen.getByTestId("task-graph-approval-reject"));

    expect(onApprovePendingRun).toHaveBeenCalledTimes(1);
    expect(onRejectPendingRun).toHaveBeenCalledTimes(1);
  });

  it("renders run timeline, diagnostics, and a cancel action for active runs", () => {
    const onCancelLatestRun = vi.fn();
    renderWorkspace({
      graph: { ...graph, template_id: "fanout_fanin_research" },
      latestRunRef: {
        ...cancellableRunningRunRef,
        diagnostic_refs: [
          {
            artifact_id: "cancel-report",
            artifact_kind: "validation_report",
            path: "PRIVATE/task-graph/cancelled/graph-run-running-1/report.md",
            status: "ready",
            label: "Cancellation report",
          },
        ],
      },
      onCancelLatestRun,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-run-timeline")).toBeInTheDocument();
    expect(
      screen.getByTestId(
        "task-graph-run-event-graph-run-running-1-branch-a-started",
      ),
    ).toHaveTextContent("Branch A started");
    expect(
      screen.getByTestId("task-graph-run-primary-artifacts"),
    ).toHaveTextContent("Cancellation report");
    expect(
      screen.getByTestId("task-graph-run-diagnostic-cancel-report"),
    ).toHaveTextContent("Cancellation report");
    expect(screen.getByTestId("task-graph-worker-timeline")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("task-graph-cancel-run"));
    expect(onCancelLatestRun).toHaveBeenCalledTimes(1);
  });

  it("shows compact run metrics without adding a separate canvas card", () => {
    renderWorkspace({
      latestRunRef,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-run-metric-tokens")).toHaveTextContent(
      "1,500",
    );
    expect(screen.getByTestId("task-graph-run-metric-calls")).toHaveTextContent(
      "P1 / T2",
    );
    expect(screen.getByTestId("task-graph-run-metric-budget")).toHaveTextContent(
      "within budget",
    );
    expect(screen.getByTestId("task-graph-run-metric-cost")).toHaveTextContent(
      "USD 0.0042",
    );
  });

  it("surfaces recovery actions for cancelled and failed runs", () => {
    const onRecoverLatestRun = vi.fn();
    renderWorkspace({
      latestRunRef: {
        ...latestRunRef,
        run_id: "graph-run-cancelled-1",
        status: "cancelled",
        node_status_counts: { completed: 1, cancelled: 2 },
        node_outcome_counts: { completed: 1, blocked: 1 },
      },
      onRecoverLatestRun,
    });
    expandInspector();
    expect(screen.getByTestId("task-graph-recovery-panel")).not.toHaveAttribute(
      "open",
    );
    expandRecoveryPanel();
    expect(screen.getByTestId("task-graph-recovery-panel")).toHaveAttribute(
      "open",
    );

    fireEvent.click(screen.getByTestId("task-graph-recovery-resume"));
    fireEvent.click(screen.getByTestId("task-graph-recovery-retry-failed"));
    fireEvent.click(screen.getByTestId("task-graph-recovery-rerun-selected"));
    fireEvent.click(screen.getByTestId("task-graph-recovery-partial-selected"));

    expect(onRecoverLatestRun).toHaveBeenNthCalledWith(1, {
      strategy: "resume_run",
    });
    expect(onRecoverLatestRun).toHaveBeenNthCalledWith(2, {
      strategy: "retry_failed_nodes",
    });
    expect(onRecoverLatestRun).toHaveBeenNthCalledWith(3, {
      strategy: "rerun_selected_nodes",
      selectedNodeIds: ["node_smoke"],
    });
    expect(onRecoverLatestRun).toHaveBeenNthCalledWith(4, {
      strategy: "partial_execution",
      selectedNodeIds: ["node_smoke"],
    });
  });

  it("shows recovery summary, rerun versus reused nodes, and recovery artifacts", () => {
    const onInspectArtifactPath = vi.fn();
    renderWorkspace({
      latestRunRef: recoveredRunRef,
      onInspectArtifactPath,
    });
    expandInspector();
    expect(screen.getByTestId("task-graph-recovery-panel")).toHaveAttribute(
      "open",
    );

    expect(screen.getByTestId("task-graph-recovery-summary")).toHaveTextContent(
      "Source run",
    );
    expect(screen.getByTestId("task-graph-recovery-summary")).toHaveTextContent(
      "graph-run-running-1",
    );
    expect(
      screen.getByTestId("task-graph-recovery-rerun-node_smoke"),
    ).toHaveTextContent("Generate Smoke Matrix");
    expect(
      screen.getByTestId("task-graph-recovery-reused-node_discover"),
    ).toHaveTextContent("Discover Provider Update");

    fireEvent.click(
      screen.getByTestId(
        "task-graph-recovery-artifact-graph-run-recovered-1-recovery-manifest-json",
      ),
    );
    fireEvent.click(
      screen.getByTestId(
        "task-graph-recovery-artifact-graph-run-recovered-1-recovery-report-md",
      ),
    );

    expect(onInspectArtifactPath).toHaveBeenNthCalledWith(
      1,
      "PRIVATE/task-graph/recovery/graph-recovery-1/manifest.json",
    );
    expect(onInspectArtifactPath).toHaveBeenNthCalledWith(
      2,
      "PRIVATE/task-graph/recovery/graph-recovery-1/report.md",
    );
  });

  it("maps a selected timeline event back to the related node on the canvas", () => {
    const onSelectNode = vi.fn();
    renderWorkspace({
      latestRunRef: cancellableRunningRunRef,
      onSelectNode,
      selectedNodeId: null,
    });
    expandInspector();

    fireEvent.click(
      screen.getByTestId(
        "task-graph-run-event-graph-run-running-1-branch-a-started",
      ),
    );

    expect(onSelectNode).toHaveBeenCalledWith("node_smoke");
    expect(screen.getByTestId("task-graph-run-event-focus")).toHaveTextContent(
      "Node",
    );
    expect(screen.getByTestId("task-graph-run-event-focus")).toHaveTextContent(
      "Generate Smoke Matrix",
    );
    expect(screen.getByTestId("task-graph-node-node_smoke")).toHaveAttribute(
      "data-trace-highlighted",
      "true",
    );
  });

  it("falls back to the approval node when selecting an approval_requested event", () => {
    const onSelectNode = vi.fn();
    renderWorkspace({
      latestRunRef: {
        ...pendingApprovalRunRef,
        timeline_events: [
          {
            event_id: "graph-run-gate-1-approval-requested",
            event_type: "approval_requested",
            created_at: "2026-07-07T00:08:00+09:00",
            summary: "Manual promotion gate requested approval.",
            status: "in_progress",
          },
        ],
      },
      onSelectNode,
      selectedNodeId: null,
    });
    expandInspector();

    fireEvent.click(
      screen.getByTestId(
        "task-graph-run-event-graph-run-gate-1-approval-requested",
      ),
    );

    expect(onSelectNode).toHaveBeenCalledWith("node_gate");
    expect(screen.getByTestId("task-graph-run-event-focus")).toHaveTextContent(
      "Approve Promotion",
    );
  });

  it("retries a dry-run from the latest run dock when the latest run is a dry-run", () => {
    const onRunDryRun = vi.fn();
    renderWorkspace({
      latestRunRef: {
        ...latestRunRef,
        status: "dry_run_passed",
      },
      onRunDryRun,
    });
    expandInspector();

    fireEvent.click(screen.getByTestId("task-graph-retry-dry-run"));
    expect(onRunDryRun).toHaveBeenCalledTimes(1);
  });

  it("surfaces a synthetic running dock while fixture launch is still pending", () => {
    renderWorkspace({
      graph: {
        ...graph,
        template_id: "code_fix_test_review",
        title: "Code Fix / Test / Review",
      },
      latestRunRef: null,
      isFixtureRunPending: true,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-run-panel")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-run-id")).toHaveTextContent(
      "pending-graph_test",
    );
    expect(screen.getByTestId("task-graph-run-timeline")).toHaveTextContent(
      "Running fixture...",
    );
    expect(screen.getByTestId("task-graph-cancel-run")).toBeInTheDocument();
  });

  it("surfaces a synthetic running dock while live launch is still pending", () => {
    renderWorkspace({
      latestRunRef: null,
      isLiveRunPending: true,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-run-panel")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByTestId("task-graph-run-id")).toHaveTextContent(
      "pending-graph_test",
    );
    expect(screen.getByTestId("task-graph-run-timeline")).toHaveTextContent(
      "Starting live run...",
    );
    expect(screen.getByTestId("task-graph-run-live")).toHaveTextContent(
      "Starting live run...",
    );
  });

  it("surfaces authoritative queued progress before workers start", () => {
    renderWorkspace({
      latestRunRef: queuedAuthoritativeRunRef,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-run-panel")).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-latest-run-summary-meta"),
    ).toHaveTextContent("1 queued / 4 waiting");
    expect(
      screen.getByTestId("task-graph-run-primary-status"),
    ).toHaveTextContent("Planner queued for live execution.");
    expect(screen.getByTestId("task-graph-run-meta")).toHaveTextContent(
      "0",
    );
  });

  it("does not mask an authoritative failed run with synthetic live pending chrome", () => {
    renderWorkspace({
      latestRunRef: {
        ...latestRunRef,
        run_id: "graph-run-live-terminal-1",
        status: "failed",
        node_status_counts: { failed: 1, blocked: 2 },
        timeline_events: [
          {
            event_id: "graph-run-live-terminal-1-failed",
            event_type: "run_failed",
            created_at: "2026-07-15T06:44:01+09:00",
            summary: "Planner failed after terminal collection timed out.",
            status: "failed",
          },
        ],
      },
      isLiveRunPending: true,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-run-id")).toHaveTextContent(
      "graph-run-live-terminal-1",
    );
    expect(screen.queryByText("pending-graph_test")).not.toBeInTheDocument();
    expect(screen.queryByText("Starting live run...")).not.toBeInTheDocument();
    expect(screen.getByTestId("task-graph-run-timeline")).toHaveTextContent(
      "Planner failed after terminal collection timed out.",
    );
  });

  it("keeps the real approval panel visible when fixture launch pending overlaps a waiting approval run", () => {
    renderWorkspace({
      latestRunRef: pendingApprovalRunRef,
      isFixtureRunPending: true,
    });
    expandInspector();

    expect(screen.getByTestId("task-graph-run-id")).toHaveTextContent(
      pendingApprovalRunRef.run_id,
    );
    expect(screen.getByTestId("task-graph-approval-panel")).toHaveTextContent(
      "Approval required",
    );
    expect(screen.queryByText("pending-graph_test")).not.toBeInTheDocument();
  });
});
