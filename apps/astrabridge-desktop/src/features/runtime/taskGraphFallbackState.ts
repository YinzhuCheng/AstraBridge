import type { TaskGraphDefinition, TaskGraphNode, TaskGraphNodePosition, TaskGraphTemplateSummary } from "../../types";

const FALLBACK_GRAPH_PREFIX = "fallback_graph_";
const STORAGE_PREFIX = "astrabridge.taskGraphFallback";
const HASH_PREFIX = "#abtg=";

type NodeConfigurationPatch = {
  label?: string;
  provider_id?: string;
  model_id?: string;
  reasoning_effort?: string;
  permission_mode?: string;
  collaboration_mode?: string;
  execution_backend?: string;
  human_summary_template?: string;
  machine_result_schema?: Record<string, unknown>;
  execution_policy?: Record<string, unknown>;
  output_contract?: Record<string, unknown>;
  approval_gate?: Record<string, unknown>;
  ui_hints?: Record<string, unknown>;
};

type CreateNodeSpec = {
  kind: string;
  label?: string | null;
  position?: TaskGraphNodePosition | null;
  ui_hints?: Record<string, unknown> | null;
};

type EdgeConfigurationPatch = {
  edge_id?: string;
  from_node_id: string;
  to_node_id: string;
  edge_type: string;
  handoff_contract?: TaskGraphDefinition["edges"][number]["handoff_contract"];
  context_policy: TaskGraphDefinition["edges"][number]["context_policy"];
  status?: string;
};

export function fallbackTaskGraphStorageKey(projectId: string, taskId: string) {
  return `${STORAGE_PREFIX}:${projectId}:${taskId}`;
}

export function isFallbackTaskGraph(graph: TaskGraphDefinition | null | undefined) {
  return Boolean(graph?.graph_id?.startsWith(FALLBACK_GRAPH_PREFIX));
}

export function taskGraphNeedsServerPersistence(args: {
  graph: TaskGraphDefinition | null | undefined;
  persistedGraphIds?: string[] | null;
  persistedGraph?: TaskGraphDefinition | null;
  routeGraphId?: string | null;
  routeUnavailable?: boolean;
}) {
  const { graph, persistedGraphIds, persistedGraph, routeGraphId, routeUnavailable } = args;
  if (!graph || routeUnavailable) return false;
  if (isFallbackTaskGraph(graph)) return true;
  if (persistedGraph && persistedGraph.graph_id === graph.graph_id) {
    const graphVersion = Number(graph.state_version ?? 0);
    const persistedVersion = Number(persistedGraph.state_version ?? 0);
    if (graphVersion !== persistedVersion) return graphVersion > persistedVersion;
    const graphUpdatedAt = Date.parse(graph.updated_at ?? "");
    const persistedUpdatedAt = Date.parse(persistedGraph.updated_at ?? "");
    if (Number.isFinite(graphUpdatedAt) && Number.isFinite(persistedUpdatedAt) && graphUpdatedAt !== persistedUpdatedAt) {
      return graphUpdatedAt > persistedUpdatedAt;
    }
  }
  const persistedIds = new Set((persistedGraphIds ?? []).filter((value): value is string => Boolean(value)));
  if (persistedIds.has(graph.graph_id)) return false;
  return routeGraphId !== graph.graph_id;
}

export function readFallbackTaskGraph(projectId: string, taskId: string) {
  if (typeof window === "undefined") return null;
  try {
    const raw = readStorageRecord(fallbackTaskGraphStorageKey(projectId, taskId));
    if (!raw) return null;
    return JSON.parse(raw) as TaskGraphDefinition;
  } catch {
    return null;
  }
}

export function writeFallbackTaskGraph(projectId: string, taskId: string, graph: TaskGraphDefinition | null) {
  if (typeof window === "undefined") return;
  const storageKey = fallbackTaskGraphStorageKey(projectId, taskId);
  if (!graph) {
    writeStorageRecord(storageKey, null);
    return;
  }
  writeStorageRecord(storageKey, JSON.stringify(graph));
}

export function buildFallbackTaskGraphFromTemplate(args: {
  projectId: string;
  taskId: string;
  template: TaskGraphTemplateSummary;
}) {
  const { taskId, template } = args;
  const stamp = new Date().toISOString();
  const graphId = `${FALLBACK_GRAPH_PREFIX}${taskId}_${template.template_id}`;
  const nodes: TaskGraphNode[] = template.preview_graph.nodes.map((node) => ({
    node_id: node.node_id,
    graph_id: graphId,
    kind: node.kind,
    label: node.label,
    agent_card_ref: `fallback_agent_card_${node.kind}`,
    execution_policy: {
      spawn_mode: "isolated_lane",
      retry_policy: { max_attempts: 1 },
      timeout_ms: 180000,
      allow_provider_calls: true,
      allow_code_changes: false,
      allow_install: false,
      requires_human_approval: false,
    },
    output_contract: {
      human_summary_required: true,
      artifact_outputs: ["required_output"],
      machine_result_schema: { type: "object", required: ["result"] },
      artifact_only: false,
    },
    position: { ...node.position },
    status: "ready",
    permission_mode: "ask",
    collaboration_mode: "default",
    execution_backend: "app_server",
    ui_hints: { context_policy_preset: "task_digest" },
  }));
  return {
    schema_version: "astrabridge-task-graph-v1",
    graph_id: graphId,
    task_id: taskId,
    title: template.title,
    template_id: template.template_id,
    status: "draft",
    graph_policy: { entry_node_ids: [...template.entry_node_ids] },
    created_at: stamp,
    updated_at: stamp,
    state_version: 1,
    nodes,
    edges: template.preview_graph.edges.map((edge) => ({
      edge_id: edge.edge_id,
      graph_id: graphId,
      from_node_id: edge.from_node_id,
      to_node_id: edge.to_node_id,
      edge_type: edge.edge_type,
      context_policy: {
        policy_id: `fallback_${edge.edge_id}`,
        history_mode: "latest_summary_only",
        artifact_mode: "required_output_only",
        exclude_private_memory: true,
        include_machine_results: true,
        include_human_summaries: true,
        summary_strategy: "latest_task_digest",
        history_length: 1,
      },
      status: "ready",
    })),
  } satisfies TaskGraphDefinition;
}

export function updateFallbackTaskGraphNodePosition(
  graph: TaskGraphDefinition,
  nodeId: string,
  position: TaskGraphNodePosition,
) {
  return {
    ...graph,
    updated_at: new Date().toISOString(),
    state_version: graph.state_version + 1,
    nodes: graph.nodes.map((node) =>
      node.node_id === nodeId
        ? {
            ...node,
            position: { x: Math.round(position.x), y: Math.round(position.y) },
          }
        : node,
    ),
  } satisfies TaskGraphDefinition;
}

export function updateFallbackTaskGraphNodeConfiguration(
  graph: TaskGraphDefinition,
  nodeId: string,
  patch: NodeConfigurationPatch,
) {
  return {
    ...graph,
    updated_at: new Date().toISOString(),
    state_version: graph.state_version + 1,
    nodes: graph.nodes.map((node) =>
      node.node_id === nodeId
        ? {
            ...node,
            ...patch,
            ui_hints: patch.ui_hints ? { ...(asRecord(node.ui_hints) ?? {}), ...patch.ui_hints } : node.ui_hints,
          }
        : node,
    ),
  } satisfies TaskGraphDefinition;
}

export function createFallbackTaskGraphNode(
  graph: TaskGraphDefinition,
  spec: CreateNodeSpec,
) {
  const nodeId = nextFallbackNodeId(graph, spec.kind);
  const position = spec.position ? { ...spec.position } : nextFallbackNodePosition(graph);
  const label = String(spec.label || defaultNodeLabel(spec.kind)).trim() || defaultNodeLabel(spec.kind);
  const nextNode: TaskGraphNode = {
    node_id: nodeId,
    graph_id: graph.graph_id,
    kind: spec.kind,
    label,
    agent_card_ref: `fallback_agent_card_${sanitizeToken(spec.kind) || "custom"}`,
    execution_policy: {
      spawn_mode: "isolated_lane",
      retry_policy: { max_attempts: 1 },
      timeout_ms: 180000,
      allow_provider_calls: true,
      allow_code_changes: false,
      allow_install: false,
      requires_human_approval: false,
    },
    output_contract: {},
    position,
    status: "draft",
    permission_mode: "ask",
    collaboration_mode: "default",
    execution_backend: "app_server",
    ui_hints: { context_policy_preset: "task_digest", ...(spec.ui_hints ?? {}) },
  };
  const entryNodeIds = Array.isArray(graph.graph_policy?.entry_node_ids) ? [...graph.graph_policy.entry_node_ids] : [];
  if (!entryNodeIds.length) entryNodeIds.push(nodeId);
  return {
    graph: {
      ...graph,
      updated_at: new Date().toISOString(),
      state_version: graph.state_version + 1,
      graph_policy: {
        ...(graph.graph_policy ?? {}),
        entry_node_ids: entryNodeIds,
      },
      nodes: [...graph.nodes, nextNode],
    } satisfies TaskGraphDefinition,
    node: nextNode,
  };
}

export function upsertFallbackTaskGraphEdge(
  graph: TaskGraphDefinition,
  patch: EdgeConfigurationPatch,
) {
  const nextEdgeId = patch.edge_id?.trim() || `fallback_edge_${graph.state_version + 1}`;
  const nextEdge = {
    edge_id: nextEdgeId,
    graph_id: graph.graph_id,
    from_node_id: patch.from_node_id,
    to_node_id: patch.to_node_id,
    edge_type: patch.edge_type,
    ...(patch.handoff_contract ? { handoff_contract: { ...patch.handoff_contract } } : {}),
    context_policy: { ...patch.context_policy },
    status: patch.status?.trim() || "ready",
  };
  const existing = graph.edges.some((edge) => edge.edge_id === nextEdgeId);
  return {
    ...graph,
    updated_at: new Date().toISOString(),
    state_version: graph.state_version + 1,
    edges: existing
      ? graph.edges.map((edge) => (edge.edge_id === nextEdgeId ? nextEdge : edge))
      : [...graph.edges, nextEdge],
  } satisfies TaskGraphDefinition;
}

export function removeFallbackTaskGraphEdge(
  graph: TaskGraphDefinition,
  edgeId: string,
) {
  const normalizedEdgeId = edgeId.trim();
  const nextEdges = graph.edges.filter((edge) => edge.edge_id !== normalizedEdgeId);
  if (nextEdges.length === graph.edges.length) {
    return graph;
  }
  return {
    ...graph,
    updated_at: new Date().toISOString(),
    state_version: graph.state_version + 1,
    edges: nextEdges,
  } satisfies TaskGraphDefinition;
}

function asRecord(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function sanitizeToken(value: string) {
  return String(value || "").trim().replace(/[^a-z0-9_]+/gi, "_").replace(/^_+|_+$/g, "").toLowerCase();
}

function defaultNodeLabel(kind: string) {
  switch (sanitizeToken(kind)) {
    case "supervisor":
      return "Supervisor";
    case "planner":
      return "Planner";
    case "worker":
      return "Worker";
    case "coder":
      return "Coder";
    case "reviewer":
      return "Reviewer";
    case "validator":
      return "Validator";
    case "researcher":
      return "Researcher";
    case "extractor":
      return "Extractor";
    case "synthesizer":
      return "Synthesizer";
    case "gate":
      return "Gate";
    default:
      return "Custom Agent";
  }
}

function nextFallbackNodeId(graph: TaskGraphDefinition, kind: string) {
  const base = `node_${sanitizeToken(kind) || "custom"}`;
  const existingIds = new Set(graph.nodes.map((node) => node.node_id));
  if (!existingIds.has(base)) return base;
  let index = 2;
  while (existingIds.has(`${base}_${index}`)) index += 1;
  return `${base}_${index}`;
}

function nextFallbackNodePosition(graph: TaskGraphDefinition) {
  if (!graph.nodes.length) return { x: 80, y: 160 };
  const positions = graph.nodes.map((node) => node.position).filter(Boolean);
  const minX = Math.min(...positions.map((position) => position.x));
  const minY = Math.min(...positions.map((position) => position.y));
  const nextIndex = graph.nodes.length;
  const column = nextIndex % 3;
  const row = Math.floor(nextIndex / 3);
  return {
    x: minX + column * 260,
    y: minY + row * 180,
  };
}

function readStorageRecord(key: string) {
  if (typeof window === "undefined") return "";
  if (typeof window.localStorage !== "undefined") return window.localStorage.getItem(key) ?? "";
  const state = readHashState();
  return typeof state[key] === "string" ? state[key] : "";
}

function writeStorageRecord(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  if (typeof window.localStorage !== "undefined") {
    if (value == null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
    return;
  }
  const state = readHashState();
  if (value == null) {
    delete state[key];
  } else {
    state[key] = value;
  }
  const encoded = encodeURIComponent(JSON.stringify(state));
  const nextHash = `${HASH_PREFIX}${encoded}`;
  if (window.location.hash !== nextHash) {
    const historyApi = window.history as { replaceState?: ((data: unknown, unused: string, url?: string | URL | null) => void) | undefined } | undefined;
    if (typeof historyApi?.replaceState === "function") {
      historyApi.replaceState(null, "", `${window.location.pathname}${window.location.search}${nextHash}`);
      return;
    }
    window.location.hash = nextHash;
  }
}

function readHashState() {
  if (typeof window === "undefined") return {} as Record<string, string>;
  const raw = window.location.hash || "";
  if (!raw.startsWith(HASH_PREFIX)) return {} as Record<string, string>;
  try {
    const parsed = JSON.parse(decodeURIComponent(raw.slice(HASH_PREFIX.length)));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, string>) : {};
  } catch {
    return {} as Record<string, string>;
  }
}
