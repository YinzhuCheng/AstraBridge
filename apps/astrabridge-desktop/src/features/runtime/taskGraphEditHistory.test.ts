import { describe, expect, it } from "vitest";

import type { TaskGraphDefinition } from "../../types";
import {
  canRedoTaskGraphEditHistory,
  canUndoTaskGraphEditHistory,
  emptyTaskGraphEditHistoryState,
  pushTaskGraphEditHistory,
  redoTaskGraphEditHistory,
  undoTaskGraphEditHistory,
} from "./taskGraphEditHistory";

function graph(graphId: string, nodeIds: string[], edgeIds: string[] = []) {
  return {
    schema_version: "astrabridge-task-graph-v1",
    graph_id: graphId,
    task_id: "task-1",
    title: "Graph",
    template_id: "template-1",
    status: "draft",
    nodes: nodeIds.map((nodeId, index) => ({
      node_id: nodeId,
      graph_id: graphId,
      kind: "artifact_source",
      label: nodeId,
      agent_card_ref: `agent_card_${nodeId}`,
      execution_policy: {},
      output_contract: {},
      position: { x: 80 + index * 260, y: 160 },
      status: "draft",
      permission_mode: "ask",
      collaboration_mode: "default",
      execution_backend: "app_server",
      ui_hints: {},
    })),
    edges: edgeIds.map((edgeId) => ({
      edge_id: edgeId,
      graph_id: graphId,
      from_node_id: nodeIds[0] ?? "",
      to_node_id: nodeIds[1] ?? "",
      edge_type: "context_handoff",
      context_policy: {
        policy_id: edgeId,
        history_mode: "latest_summary_only",
        artifact_mode: "required_output_only",
        exclude_private_memory: true,
        include_machine_results: true,
        include_human_summaries: true,
        summary_strategy: "latest_task_digest",
      },
      status: "ready",
    })),
    graph_policy: { entry_node_ids: nodeIds.slice(0, 1) },
    created_at: "2026-07-17T09:00:00+09:00",
    updated_at: "2026-07-17T09:00:00+09:00",
    state_version: 1,
  } satisfies TaskGraphDefinition;
}

describe("taskGraphEditHistory", () => {
  it("undoes and redoes a destructive edit while preserving selection snapshots", () => {
    const before = graph("graph-1", ["node_a", "node_b"], ["edge_a_b"]);
    const after = graph("graph-1", ["node_b"], []);
    const state = pushTaskGraphEditHistory(emptyTaskGraphEditHistoryState(), {
      entry_id: "entry-1",
      graph_id: "graph-1",
      action: "delete_node",
      summary: "Deleted node node_a",
      graph_before: before,
      graph_after: after,
      selection_before: { selectedNodeId: "node_a", selectedEdgeId: null },
      selection_after: { selectedNodeId: "node_b", selectedEdgeId: null },
      created_at: "2026-07-17T09:05:00+09:00",
    });

    expect(canUndoTaskGraphEditHistory(state)).toBe(true);
    expect(canRedoTaskGraphEditHistory(state)).toBe(false);

    const undone = undoTaskGraphEditHistory(state);
    expect(undone?.graph.nodes.map((node) => node.node_id)).toEqual(["node_a", "node_b"]);
    expect(undone?.selection).toEqual({ selectedNodeId: "node_a", selectedEdgeId: null });
    expect(canRedoTaskGraphEditHistory(undone?.state)).toBe(true);

    const redone = redoTaskGraphEditHistory(undone?.state);
    expect(redone?.graph.nodes.map((node) => node.node_id)).toEqual(["node_b"]);
    expect(redone?.selection).toEqual({ selectedNodeId: "node_b", selectedEdgeId: null });
    expect(canUndoTaskGraphEditHistory(redone?.state)).toBe(true);
  });

  it("drops redo history when a new destructive edit is recorded after undo", () => {
    const base = graph("graph-1", ["node_a", "node_b"], ["edge_a_b"]);
    const afterDeleteEdge = graph("graph-1", ["node_a", "node_b"], []);
    const afterDeleteNode = graph("graph-1", ["node_b"], []);

    const first = pushTaskGraphEditHistory(emptyTaskGraphEditHistoryState(), {
      entry_id: "entry-1",
      graph_id: "graph-1",
      action: "delete_edge",
      summary: "Deleted edge edge_a_b",
      graph_before: base,
      graph_after: afterDeleteEdge,
      selection_before: { selectedNodeId: null, selectedEdgeId: "edge_a_b" },
      selection_after: { selectedNodeId: "node_a", selectedEdgeId: null },
      created_at: "2026-07-17T09:05:00+09:00",
    });
    const undone = undoTaskGraphEditHistory(first);
    const second = pushTaskGraphEditHistory(undone?.state, {
      entry_id: "entry-2",
      graph_id: "graph-1",
      action: "delete_node",
      summary: "Deleted node node_a",
      graph_before: base,
      graph_after: afterDeleteNode,
      selection_before: { selectedNodeId: "node_a", selectedEdgeId: null },
      selection_after: { selectedNodeId: "node_b", selectedEdgeId: null },
      created_at: "2026-07-17T09:06:00+09:00",
    });

    expect(second.entries.map((entry) => entry.entry_id)).toEqual(["entry-2"]);
    expect(canRedoTaskGraphEditHistory(second)).toBe(false);
  });
});
