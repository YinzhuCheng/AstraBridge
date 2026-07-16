import { describe, expect, it } from "vitest";

import type { TaskGraphDefinition } from "../../types";
import {
  hasRenderableTaskGraphStructure,
  resolvePreferredTaskGraphId,
  resolveTaskGraphRouteUnavailable,
} from "./taskGraphSelection";

describe("hasRenderableTaskGraphStructure", () => {
  it("accepts a full task-graph definition", () => {
    const graph = {
      graph_id: "graph-1",
      nodes: [],
      edges: [],
    } as unknown as TaskGraphDefinition;

    expect(hasRenderableTaskGraphStructure(graph)).toBe(true);
  });

  it("rejects summary-only graph definitions from task state", () => {
    const graph = {
      graph_id: "graph-1",
      title: "Summary only",
      node_count: 4,
      edge_count: 3,
    } as unknown as TaskGraphDefinition;

    expect(hasRenderableTaskGraphStructure(graph)).toBe(false);
  });
});

describe("resolvePreferredTaskGraphId", () => {
  it("prefers the live route graph on first hydration even when a stale persisted graph exists", () => {
    expect(
      resolvePreferredTaskGraphId({
        currentGraphId: null,
        persistedGraphId: "graph-old",
        routeGraphId: "graph-live",
        latestGraphId: "graph-live",
        fallbackGraphId: null,
        taskGraphIds: ["graph-live", "graph-old"],
        taskGraphRouteUnavailable: false,
        firstHydrationForTask: true,
      }),
    ).toBe("graph-live");
  });

  it("prefers the latest task graph on first hydration before the route graph payload is loaded", () => {
    expect(
      resolvePreferredTaskGraphId({
        currentGraphId: null,
        persistedGraphId: "graph-old",
        routeGraphId: null,
        latestGraphId: "graph-live",
        fallbackGraphId: null,
        taskGraphIds: ["graph-live", "graph-old"],
        taskGraphRouteUnavailable: false,
        firstHydrationForTask: true,
      }),
    ).toBe("graph-live");
  });

  it("rebinds to the fallback graph on first hydration when current-task details have not loaded yet", () => {
    expect(
      resolvePreferredTaskGraphId({
        currentGraphId: null,
        persistedGraphId: "graph-live",
        routeGraphId: null,
        latestGraphId: "graph-live",
        fallbackGraphId: "graph-live",
        taskGraphIds: ["graph-live"],
        taskGraphRouteUnavailable: false,
        firstHydrationForTask: true,
      }),
    ).toBe("graph-live");
  });

  it("preserves an already selected in-task graph after the first hydration pass", () => {
    expect(
      resolvePreferredTaskGraphId({
        currentGraphId: "graph-old",
        persistedGraphId: "graph-old",
        routeGraphId: "graph-live",
        latestGraphId: "graph-live",
        fallbackGraphId: null,
        taskGraphIds: ["graph-live", "graph-old"],
        taskGraphRouteUnavailable: false,
        firstHydrationForTask: false,
      }),
    ).toBe("graph-old");
  });
});

describe("resolveTaskGraphRouteUnavailable", () => {
  it("stays available when the task-graph route 404s but a persisted renderable graph still exists", () => {
    expect(
      resolveTaskGraphRouteUnavailable({
        templatesError: false,
        taskGraphErrorMessage: "Not found",
        routeGraph: null,
        persistedGraphs: [
          {
            graph_id: "graph-live",
            nodes: [],
            edges: [],
          } as unknown as TaskGraphDefinition,
        ],
        fallbackGraph: null,
      }),
    ).toBe(false);
  });

  it("stays available when only a fallback graph is currently renderable", () => {
    expect(
      resolveTaskGraphRouteUnavailable({
        templatesError: false,
        taskGraphErrorMessage: "Not found",
        routeGraph: null,
        persistedGraphs: [],
        fallbackGraph: {
          graph_id: "fallback_graph_task-1_template-1",
          nodes: [],
          edges: [],
        } as unknown as TaskGraphDefinition,
      }),
    ).toBe(false);
  });

  it("stays available when templates fail but the live route graph is already renderable", () => {
    expect(
      resolveTaskGraphRouteUnavailable({
        templatesError: true,
        taskGraphErrorMessage: null,
        routeGraph: {
          graph_id: "graph-live",
          nodes: [],
          edges: [],
        } as unknown as TaskGraphDefinition,
        persistedGraphs: [],
        fallbackGraph: null,
      }),
    ).toBe(false);
  });

  it("remains unavailable when templates fail or no renderable graph source exists", () => {
    expect(
      resolveTaskGraphRouteUnavailable({
        templatesError: true,
        taskGraphErrorMessage: null,
        routeGraph: null,
        persistedGraphs: [],
        fallbackGraph: null,
      }),
    ).toBe(true);
    expect(
      resolveTaskGraphRouteUnavailable({
        templatesError: false,
        taskGraphErrorMessage: "Not found",
        routeGraph: null,
        persistedGraphs: [],
        fallbackGraph: null,
      }),
    ).toBe(true);
  });
});
