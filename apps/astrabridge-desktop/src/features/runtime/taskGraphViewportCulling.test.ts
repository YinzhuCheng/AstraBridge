import { describe, expect, it } from "vitest";

import type { TaskGraphDefinition } from "../../types";
import {
  collectVisibleTaskGraphElements,
  resolveTaskGraphStageViewport,
} from "./taskGraphViewportCulling";

const graph: TaskGraphDefinition = {
  schema_version: "astrabridge-task-graph-v1",
  graph_id: "graph-large",
  task_id: "task-large",
  title: "Large graph",
  template_id: "custom_blank_graph",
  status: "ready",
  created_at: "2026-07-17T09:00:00+09:00",
  updated_at: "2026-07-17T09:00:00+09:00",
  state_version: 1,
  graph_policy: {},
  nodes: [
    {
      node_id: "node_visible_a",
      graph_id: "graph-large",
      kind: "worker",
      label: "Visible A",
      agent_card_ref: "worker",
      execution_policy: {},
      output_contract: {},
      position: { x: 40, y: 80 },
      status: "ready",
    },
    {
      node_id: "node_visible_b",
      graph_id: "graph-large",
      kind: "worker",
      label: "Visible B",
      agent_card_ref: "worker",
      execution_policy: {},
      output_contract: {},
      position: { x: 280, y: 120 },
      status: "ready",
    },
    {
      node_id: "node_far_c",
      graph_id: "graph-large",
      kind: "worker",
      label: "Far C",
      agent_card_ref: "worker",
      execution_policy: {},
      output_contract: {},
      position: { x: 1880, y: 160 },
      status: "ready",
    },
    {
      node_id: "node_far_d",
      graph_id: "graph-large",
      kind: "worker",
      label: "Far D",
      agent_card_ref: "worker",
      execution_policy: {},
      output_contract: {},
      position: { x: 2140, y: 220 },
      status: "ready",
    },
  ],
  edges: [
    {
      edge_id: "edge_visible",
      graph_id: "graph-large",
      from_node_id: "node_visible_a",
      to_node_id: "node_visible_b",
      edge_type: "context_handoff",
      context_policy: {
        policy_id: "edge-visible",
        history_mode: "none",
        artifact_mode: "none",
        exclude_private_memory: true,
        include_machine_results: false,
        include_human_summaries: false,
      },
      status: "ready",
    },
    {
      edge_id: "edge_far",
      graph_id: "graph-large",
      from_node_id: "node_far_c",
      to_node_id: "node_far_d",
      edge_type: "context_handoff",
      context_policy: {
        policy_id: "edge-far",
        history_mode: "none",
        artifact_mode: "none",
        exclude_private_memory: true,
        include_machine_results: false,
        include_human_summaries: false,
      },
      status: "ready",
    },
  ],
};

describe("taskGraphViewportCulling", () => {
  it("uses the full stage when the canvas container is not yet measurable", () => {
    const viewport = resolveTaskGraphStageViewport(
      {
        scrollLeft: 0,
        scrollTop: 0,
        clientWidth: 0,
        clientHeight: 0,
      },
      1,
      2400,
      1200,
    );

    expect(viewport).toEqual({
      left: 0,
      top: 0,
      right: 2400,
      bottom: 1200,
    });
  });

  it("culls offscreen graph elements while preserving a forced selected edge and its nodes", () => {
    const viewport = resolveTaskGraphStageViewport(
      {
        scrollLeft: 0,
        scrollTop: 0,
        clientWidth: 640,
        clientHeight: 480,
      },
      1,
      2600,
      1200,
      0,
    );

    const visible = collectVisibleTaskGraphElements(graph, {}, viewport, {
      selectedEdgeId: "edge_far",
    });

    expect(Array.from(visible.visibleNodeIds).sort()).toEqual([
      "node_far_c",
      "node_far_d",
      "node_visible_a",
      "node_visible_b",
    ]);
    expect(Array.from(visible.visibleEdgeIds).sort()).toEqual([
      "edge_far",
      "edge_visible",
    ]);
  });

  it("drops fully offscreen nodes and edges when no state forces them visible", () => {
    const viewport = resolveTaskGraphStageViewport(
      {
        scrollLeft: 0,
        scrollTop: 0,
        clientWidth: 640,
        clientHeight: 480,
      },
      1,
      2600,
      1200,
      0,
    );

    const visible = collectVisibleTaskGraphElements(graph, {}, viewport);

    expect(Array.from(visible.visibleNodeIds).sort()).toEqual([
      "node_visible_a",
      "node_visible_b",
    ]);
    expect(Array.from(visible.visibleEdgeIds)).toEqual(["edge_visible"]);
  });
});
