import { describe, expect, it } from "vitest";

import type {
  ProjectTask,
  TaskGraphCommandLogEntry,
  TaskGraphDefinition,
  TaskGraphRunRef,
  TaskGraphSnapshotRef,
} from "../../types";
import type { TaskGraphEditHistoryState } from "./taskGraphEditHistory";
import {
  selectTaskGraphAppState,
  taskGraphNodeOverrideKey,
} from "./taskGraphAppState";
import { createOptimisticTaskGraphLiveRunRef } from "./taskGraphRunRefs";

function buildGraph(
  overrides: Partial<TaskGraphDefinition> & Pick<TaskGraphDefinition, "graph_id" | "task_id">,
): TaskGraphDefinition {
  const {
    graph_id,
    task_id,
    title = `Graph ${graph_id}`,
    template_id = `template-${graph_id}`,
    status = "draft",
    nodes,
    edges,
    graph_policy,
    created_at = "2026-07-18T00:00:00.000Z",
    updated_at = "2026-07-18T00:00:00.000Z",
    state_version = 1,
    schema_version = "astrabridge-task-graph-v1",
    ...rest
  } = overrides;
  return {
    schema_version,
    graph_id,
    task_id,
    title,
    template_id,
    status,
    nodes:
      nodes ??
      [
        {
          node_id: `${graph_id}-node-1`,
          graph_id,
          kind: "planner",
          label: "Planner",
          agent_card_ref: "agent://planner",
          execution_policy: {},
          output_contract: {},
          position: { x: 0, y: 0 },
          status: "ready",
        },
      ],
    edges:
      edges ??
      [
        {
          edge_id: `${graph_id}-edge-1`,
          graph_id,
          from_node_id: `${graph_id}-node-1`,
          to_node_id: `${graph_id}-node-1`,
          edge_type: "next",
          context_policy: {
            policy_id: "policy-default",
            history_mode: "inherit",
            artifact_mode: "inherit",
            exclude_private_memory: false,
            include_machine_results: true,
            include_human_summaries: true,
          },
          status: "ready",
        },
      ],
    graph_policy: graph_policy ?? { entry_node_ids: [`${graph_id}-node-1`] },
    created_at,
    updated_at,
    state_version,
    ...rest,
  };
}

function buildRunRef(
  overrides: Partial<TaskGraphRunRef> &
    Pick<TaskGraphRunRef, "run_id" | "graph_id" | "task_id" | "status" | "created_at" | "updated_at">,
): TaskGraphRunRef {
  const { run_id, graph_id, task_id, status, created_at, updated_at, ...rest } = overrides;
  return {
    run_id,
    graph_id,
    task_id,
    status,
    created_at,
    updated_at,
    entry_node_ids: [],
    node_status_counts: {},
    artifact_count: 0,
    event_count: 0,
    ...rest,
  };
}

function buildSnapshotRef(
  overrides: Partial<TaskGraphSnapshotRef> &
    Pick<TaskGraphSnapshotRef, "snapshot_id" | "task_id" | "graph_id" | "created_at" | "updated_at">,
): TaskGraphSnapshotRef {
  return {
    artifact_paths: {},
    ...overrides,
  };
}

function buildCommandLogEntry(
  overrides: Partial<TaskGraphCommandLogEntry> &
    Pick<
      TaskGraphCommandLogEntry,
      "entry_id" | "graph_id" | "action" | "target_kind" | "summary" | "status" | "created_at" | "updated_at"
    >,
): TaskGraphCommandLogEntry {
  return {
    ...overrides,
  };
}

function buildEditHistoryState(graph: TaskGraphDefinition): TaskGraphEditHistoryState {
  return {
    cursor: 1,
    entries: [
      {
        entry_id: `history-${graph.graph_id}`,
        graph_id: graph.graph_id,
        action: "delete_node",
        summary: "Deleted a node",
        graph_before: graph,
        graph_after: graph,
        selection_before: { selectedNodeId: null, selectedEdgeId: null },
        selection_after: { selectedNodeId: null, selectedEdgeId: null },
        created_at: "2026-07-18T00:00:00.000Z",
      },
    ],
  };
}

function buildTask(
  overrides: Partial<ProjectTask> & Pick<ProjectTask, "task_id">,
): ProjectTask {
  const {
    task_id,
    title = `Task ${task_id}`,
    status = "active",
    graph_definitions = [],
    graph_run_refs = [],
    graph_snapshot_refs = [],
    created_at = "2026-07-18T00:00:00.000Z",
    updated_at = "2026-07-18T00:00:00.000Z",
    schema_version = "astrabridge-task-v1",
    provider_threads = [],
    handoff_events = [],
    handoff_policy = "multi_provider_handoff",
    ...rest
  } = overrides;
  return {
    schema_version,
    task_id,
    title,
    status,
    handoff_policy,
    provider_threads,
    handoff_events,
    graph_definitions,
    graph_run_refs,
    graph_snapshot_refs,
    created_at,
    updated_at,
    ...rest,
  };
}

describe("selectTaskGraphAppState", () => {
  it("prefers a newer fallback graph and applies node overrides", () => {
    const serverGraph = buildGraph({
      graph_id: "graph-a",
      task_id: "task-a",
      state_version: 1,
      updated_at: "2026-07-18T00:00:00.000Z",
    });
    const fallbackGraph = buildGraph({
      graph_id: "graph-a",
      task_id: "task-a",
      state_version: 2,
      updated_at: "2026-07-18T00:05:00.000Z",
    });

    const selection = selectTaskGraphAppState({
      activeTaskGraphId: "graph-a",
      selectedTaskGraphId: "graph-a",
      currentTask: buildTask({
        task_id: "task-a",
        graph_definitions: [serverGraph],
      }),
      routeGraph: serverGraph,
      routeTaskGraphDefinitions: [serverGraph],
      fallbackTaskGraph: fallbackGraph,
      taskGraphRouteUnavailable: false,
      taskGraphNodeOverrides: {
        [taskGraphNodeOverrideKey("graph-a", "graph-a-node-1")]: {
          label: "Planner (edited)",
          position: { x: 42, y: 9 },
          ui_hints: { collapsed: true },
        },
      },
      taskGraphEditHistoryByGraphId: {},
      taskGraphCommandLog: [],
      selectedTaskGraphSnapshotId: null,
      taskGraphOptimisticLiveRunRefs: {},
      taskGraphLiveRunRefs: {},
      taskGraphDryRunRunRef: null,
      runTaskGraphPending: false,
      taskGraphLiveDispatchStarted: false,
      graphWorkspaceOpen: true,
      nowMs: 1234,
    });

    expect(selection.currentTaskGraphBase).toBe(fallbackGraph);
    expect(selection.currentTaskGraph?.nodes[0]?.label).toBe("Planner (edited)");
    expect(selection.currentTaskGraph?.nodes[0]?.position).toEqual({ x: 42, y: 9 });
    expect(selection.datasetState.currentTaskGraphBaseId).toBe("graph-a");
    expect(selection.datasetState.currentTaskGraphId).toBe("graph-a");
    expect(selection.datasetState.at).toBe(1234);
  });

  it("filters snapshots, edit history, and command log to the active graph", () => {
    const graphA = buildGraph({ graph_id: "graph-a", task_id: "task-a" });
    const graphB = buildGraph({ graph_id: "graph-b", task_id: "task-a" });
    const historyA = buildEditHistoryState(graphA);
    const historyB = buildEditHistoryState(graphB);

    const selection = selectTaskGraphAppState({
      activeTaskGraphId: "graph-a",
      selectedTaskGraphId: "graph-a",
      currentTask: buildTask({
        task_id: "task-a",
        graph_definitions: [graphA, graphB],
        graph_snapshot_refs: [
          buildSnapshotRef({
            snapshot_id: "snap-a-1",
            task_id: "task-a",
            graph_id: "graph-a",
            created_at: "2026-07-18T00:00:00.000Z",
            updated_at: "2026-07-18T00:00:00.000Z",
          }),
          buildSnapshotRef({
            snapshot_id: "snap-a-2",
            task_id: "task-a",
            graph_id: "graph-a",
            created_at: "2026-07-18T00:10:00.000Z",
            updated_at: "2026-07-18T00:10:00.000Z",
          }),
          buildSnapshotRef({
            snapshot_id: "snap-b-1",
            task_id: "task-a",
            graph_id: "graph-b",
            created_at: "2026-07-18T00:20:00.000Z",
            updated_at: "2026-07-18T00:20:00.000Z",
          }),
        ],
      }),
      routeGraph: graphA,
      routeTaskGraphDefinitions: [graphA, graphB],
      fallbackTaskGraph: null,
      taskGraphRouteUnavailable: false,
      taskGraphNodeOverrides: {},
      taskGraphEditHistoryByGraphId: {
        "graph-a": historyA,
        "graph-b": historyB,
      },
      taskGraphCommandLog: [
        buildCommandLogEntry({
          entry_id: "log-a",
          graph_id: "graph-a",
          action: "save_node",
          target_kind: "node",
          summary: "Saved graph A node",
          status: "applied",
          created_at: "2026-07-18T00:00:00.000Z",
          updated_at: "2026-07-18T00:00:01.000Z",
        }),
        buildCommandLogEntry({
          entry_id: "log-b",
          graph_id: "graph-b",
          action: "save_node",
          target_kind: "node",
          summary: "Saved graph B node",
          status: "applied",
          created_at: "2026-07-18T00:00:02.000Z",
          updated_at: "2026-07-18T00:00:03.000Z",
        }),
      ],
      selectedTaskGraphSnapshotId: "snap-a-2",
      taskGraphOptimisticLiveRunRefs: {},
      taskGraphLiveRunRefs: {},
      taskGraphDryRunRunRef: null,
      runTaskGraphPending: false,
      taskGraphLiveDispatchStarted: false,
      graphWorkspaceOpen: false,
    });

    expect(selection.currentTaskGraphSnapshotRefs.map((item) => item.snapshot_id)).toEqual([
      "snap-a-1",
      "snap-a-2",
    ]);
    expect(selection.selectedTaskGraphSnapshot?.snapshot_id).toBe("snap-a-2");
    expect(selection.currentTaskGraphEditHistory).toEqual(historyA);
    expect(selection.currentTaskGraphCommandLog.map((item) => item.entry_id)).toEqual([
      "log-a",
    ]);
  });

  it("prefers an authoritative active live run and exposes it as the authoritative ref", () => {
    const graphA = buildGraph({ graph_id: "graph-a", task_id: "task-a" });
    const optimisticLive = createOptimisticTaskGraphLiveRunRef({
      graphId: "graph-a",
      taskId: "task-a",
      entryNodeIds: ["graph-a-node-1"],
      nowIso: "2026-07-18T01:01:00.000Z",
    });
    const authoritativeLive = buildRunRef({
      run_id: "run-authoritative",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-18T01:00:30.000Z",
      updated_at: "2026-07-18T01:02:00.000Z",
    });
    const staleDryRun = buildRunRef({
      run_id: "run-dry",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "dry_run_passed",
      created_at: "2026-07-18T00:50:00.000Z",
      updated_at: "2026-07-18T00:50:00.000Z",
    });

    const selection = selectTaskGraphAppState({
      activeTaskGraphId: "graph-a",
      selectedTaskGraphId: "graph-a",
      currentTask: buildTask({
        task_id: "task-a",
        graph_definitions: [graphA],
        graph_run_refs: [authoritativeLive, staleDryRun],
      }),
      routeGraph: graphA,
      routeTaskGraphDefinitions: [graphA],
      routeTaskRunRefs: [staleDryRun, authoritativeLive],
      fallbackTaskGraph: null,
      taskGraphRouteUnavailable: false,
      taskGraphNodeOverrides: {},
      taskGraphEditHistoryByGraphId: {},
      taskGraphCommandLog: [],
      selectedTaskGraphSnapshotId: null,
      taskGraphOptimisticLiveRunRefs: { "graph-a": optimisticLive },
      taskGraphLiveRunRefs: {},
      taskGraphDryRunRunRef: staleDryRun,
      runTaskGraphPending: true,
      taskGraphLiveDispatchStarted: true,
      graphWorkspaceOpen: true,
    });

    expect(selection.currentTaskGraphRunRef?.run_id).toBe("run-authoritative");
    expect(selection.authoritativeActiveTaskGraphRunRef?.run_id).toBe("run-authoritative");
  });

  it("uses the route graph and optimistic live run when authoritative state is not available", () => {
    const currentTaskGraph = buildGraph({
      graph_id: "graph-local",
      task_id: "task-a",
      updated_at: "2026-07-18T00:00:00.000Z",
    });
    const routeGraph = buildGraph({
      graph_id: "graph-route",
      task_id: "task-a",
      updated_at: "2026-07-18T01:00:00.000Z",
    });
    const optimisticLive = createOptimisticTaskGraphLiveRunRef({
      graphId: "graph-route",
      taskId: "task-a",
      entryNodeIds: ["graph-route-node-1"],
      nowIso: "2026-07-18T01:05:00.000Z",
    });

    const selection = selectTaskGraphAppState({
      activeTaskGraphId: null,
      selectedTaskGraphId: "graph-route",
      currentTask: buildTask({
        task_id: "task-a",
        graph_definitions: [currentTaskGraph],
      }),
      routeGraph,
      routeTaskGraphDefinitions: [routeGraph],
      fallbackTaskGraph: null,
      taskGraphRouteUnavailable: false,
      taskGraphNodeOverrides: {},
      taskGraphEditHistoryByGraphId: {},
      taskGraphCommandLog: [],
      selectedTaskGraphSnapshotId: null,
      taskGraphOptimisticLiveRunRefs: { "graph-route": optimisticLive },
      taskGraphLiveRunRefs: {},
      taskGraphDryRunRunRef: null,
      runTaskGraphPending: true,
      taskGraphLiveDispatchStarted: true,
      graphWorkspaceOpen: true,
      nowMs: 5678,
    });

    expect(selection.currentTaskGraphBase?.graph_id).toBe("graph-route");
    expect(selection.currentTaskGraphRunRef?.run_id).toBe(optimisticLive.run_id);
    expect(selection.authoritativeActiveTaskGraphRunRef).toBeNull();
    expect(selection.datasetState.routeGraphId).toBe("graph-route");
    expect(selection.datasetState.routeTaskGraphIds).toEqual(["graph-route"]);
    expect(selection.datasetState.currentTaskGraphIds).toEqual(["graph-local"]);
    expect(selection.datasetState.latestCurrentTaskGraphId).toBe("graph-local");
    expect(selection.datasetState.currentTaskGraphId).toBe("graph-route");
    expect(selection.datasetState.at).toBe(5678);
  });
});
