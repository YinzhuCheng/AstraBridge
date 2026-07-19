import { describe, expect, it } from "vitest";

import type { TaskGraphDefinition } from "../../types";
import { removeFallbackTaskGraphNode, taskGraphNeedsServerPersistence } from "./taskGraphFallbackState";

function graph(graphId: string) {
  return {
    schema_version: "astrabridge-task-graph-v1",
    graph_id: graphId,
    task_id: "task-1",
    title: "Graph",
    template_id: "template-1",
    status: "draft",
    nodes: [],
    edges: [],
    graph_policy: {},
    created_at: "2026-07-12T00:00:00Z",
    updated_at: "2026-07-12T00:00:00Z",
    state_version: 1,
  } satisfies TaskGraphDefinition;
}

describe("taskGraphNeedsServerPersistence", () => {
  it("requires persistence for fallback graphs even when the route is available", () => {
    expect(
      taskGraphNeedsServerPersistence({
        graph: graph("fallback_graph_task-1_supervisor_worker_synthesizer"),
        persistedGraphIds: [],
        routeGraphId: null,
        routeUnavailable: false,
      }),
    ).toBe(true);
  });

  it("requires persistence when the graph is not fallback but is missing from task state and route state", () => {
    expect(
      taskGraphNeedsServerPersistence({
        graph: graph("graph-missing"),
        persistedGraphIds: ["graph-other"],
        routeGraphId: null,
        routeUnavailable: false,
      }),
    ).toBe(true);
  });

  it("skips persistence when the graph already exists in task state", () => {
    expect(
      taskGraphNeedsServerPersistence({
        graph: graph("graph-present"),
        persistedGraphIds: ["graph-present"],
        persistedGraph: graph("graph-present"),
        routeGraphId: null,
        routeUnavailable: false,
      }),
    ).toBe(false);
  });

  it("requires persistence when the current graph version is newer than the persisted task graph", () => {
    expect(
      taskGraphNeedsServerPersistence({
        graph: { ...graph("graph-present"), state_version: 3 },
        persistedGraphIds: ["graph-present"],
        persistedGraph: { ...graph("graph-present"), state_version: 2 },
        routeGraphId: "graph-present",
        routeUnavailable: false,
      }),
    ).toBe(true);
  });

  it("requires persistence when the current graph timestamp is newer than the persisted task graph", () => {
    expect(
      taskGraphNeedsServerPersistence({
        graph: { ...graph("graph-present"), updated_at: "2026-07-12T01:00:00Z" },
        persistedGraphIds: ["graph-present"],
        persistedGraph: { ...graph("graph-present"), updated_at: "2026-07-12T00:00:00Z" },
        routeGraphId: "graph-present",
        routeUnavailable: false,
      }),
    ).toBe(true);
  });

  it("skips persistence when the route is unavailable because the graph remains local-only", () => {
    expect(
      taskGraphNeedsServerPersistence({
        graph: graph("fallback_graph_task-1_supervisor_worker_synthesizer"),
        persistedGraphIds: [],
        routeGraphId: null,
        routeUnavailable: true,
      }),
    ).toBe(false);
  });
});

describe("removeFallbackTaskGraphNode", () => {
  it("removes the node, prunes connected edges, and rebinds entry nodes", () => {
    const graphWithNode = {
      ...graph("fallback_graph_task-1_supervisor_worker_synthesizer"),
      graph_policy: { entry_node_ids: ["node_start"] },
      nodes: [
        {
          node_id: "node_start",
          graph_id: "fallback_graph_task-1_supervisor_worker_synthesizer",
          kind: "artifact_source",
          label: "Start",
          agent_card_ref: "agent_card_start",
          execution_policy: {},
          output_contract: {},
          position: { x: 80, y: 160 },
          status: "draft",
          permission_mode: "ask",
          collaboration_mode: "default",
          execution_backend: "app_server",
          ui_hints: {},
        },
        {
          node_id: "node_review",
          graph_id: "fallback_graph_task-1_supervisor_worker_synthesizer",
          kind: "validator",
          label: "Review",
          agent_card_ref: "agent_card_review",
          execution_policy: {},
          output_contract: {},
          position: { x: 340, y: 160 },
          status: "draft",
          permission_mode: "ask",
          collaboration_mode: "default",
          execution_backend: "app_server",
          ui_hints: {},
        },
      ],
      edges: [
        {
          edge_id: "edge_start_review",
          graph_id: "fallback_graph_task-1_supervisor_worker_synthesizer",
          from_node_id: "node_start",
          to_node_id: "node_review",
          edge_type: "context_handoff",
          context_policy: {
            policy_id: "edge_start_review",
            history_mode: "latest_summary_only",
            artifact_mode: "required_output_only",
            exclude_private_memory: true,
            include_machine_results: true,
            include_human_summaries: true,
            summary_strategy: "latest_task_digest",
          },
          status: "ready",
        },
      ],
    } satisfies TaskGraphDefinition;

    const removed = removeFallbackTaskGraphNode(graphWithNode, "node_start");

    expect(removed.node?.node_id).toBe("node_start");
    expect(removed.removedEdgeIds).toEqual(["edge_start_review"]);
    expect(removed.graph.nodes.map((node) => node.node_id)).toEqual(["node_review"]);
    expect(removed.graph.edges).toEqual([]);
    expect(removed.graph.graph_policy.entry_node_ids).toEqual(["node_review"]);
  });
});
