import { describe, expect, it } from "vitest";

import type { TaskGraphDefinition } from "../../types";
import { taskGraphNeedsServerPersistence } from "./taskGraphFallbackState";

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
