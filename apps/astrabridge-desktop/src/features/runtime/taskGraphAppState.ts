import type {
  ProjectTask,
  TaskGraphCommandLogEntry,
  TaskGraphDefinition,
  TaskGraphRunRef,
  TaskGraphSnapshotRef,
} from "../../types";
import {
  emptyTaskGraphEditHistoryState,
  type TaskGraphEditHistoryState,
} from "./taskGraphEditHistory";
import {
  selectCurrentTaskGraphRunRef,
  selectLatestTaskGraphRunRef,
} from "./taskGraphRunRefs";
import { hasRenderableTaskGraphStructure } from "./taskGraphSelection";

export function taskGraphNodeOverrideKey(graphId: string, nodeId: string) {
  return `${graphId}::${nodeId}`;
}

function taskGraphTimestamp(value: string | null | undefined) {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function latestTaskGraphDefinition(
  graphs: TaskGraphDefinition[] | null | undefined,
) {
  if (!graphs?.length) return null;
  return graphs.reduce<TaskGraphDefinition | null>((latest, candidate) => {
    if (!latest) return candidate;
    const candidateTime = Math.max(
      taskGraphTimestamp(candidate.updated_at),
      taskGraphTimestamp(candidate.created_at),
    );
    const latestTime = Math.max(
      taskGraphTimestamp(latest.updated_at),
      taskGraphTimestamp(latest.created_at),
    );
    return candidateTime >= latestTime ? candidate : latest;
  }, null);
}

export function isTaskGraphNewer(
  candidate: TaskGraphDefinition | null | undefined,
  baseline: TaskGraphDefinition | null | undefined,
) {
  if (!candidate) return false;
  if (!baseline) return true;
  if (candidate.graph_id !== baseline.graph_id) return false;
  const candidateVersion = Number(candidate.state_version ?? 0);
  const baselineVersion = Number(baseline.state_version ?? 0);
  if (candidateVersion !== baselineVersion) return candidateVersion > baselineVersion;
  const candidateTime = Math.max(
    taskGraphTimestamp(candidate.updated_at),
    taskGraphTimestamp(candidate.created_at),
  );
  const baselineTime = Math.max(
    taskGraphTimestamp(baseline.updated_at),
    taskGraphTimestamp(baseline.created_at),
  );
  return candidateTime > baselineTime;
}

export function applyTaskGraphNodeOverrides(
  graph: TaskGraphDefinition | null,
  overrides: Record<string, Partial<TaskGraphDefinition["nodes"][number]>>,
): TaskGraphDefinition | null {
  if (!graph) return null;
  if (!Object.keys(overrides).length) return graph;
  let changed = false;
  const nodes = graph.nodes.map((node) => {
    const override = overrides[taskGraphNodeOverrideKey(graph.graph_id, node.node_id)];
    if (!override) return node;
    changed = true;
    return {
      ...node,
      ...override,
      position: override.position ?? node.position,
      ui_hints: override.ui_hints ?? node.ui_hints,
    };
  });
  if (!changed) return graph;
  return {
    ...graph,
    nodes,
  };
}

type TaskGraphStateDatasetPayload = {
  at: number;
  graphWorkspaceOpen: boolean;
  selectedTaskGraphId: string | null;
  activeTaskGraphId: string | null;
  fallbackGraphId: string | null;
  routeGraphId: string | null;
  routeTaskGraphIds: string[];
  currentTaskGraphIds: string[];
  latestCurrentTaskGraphId: string | null;
  currentTaskGraphBaseId: string | null;
  currentTaskGraphId: string | null;
  currentTaskGraphTemplateId: string | null;
};

export type TaskGraphAppStateSelection = {
  currentTaskGraphBase: TaskGraphDefinition | null;
  currentTaskGraph: TaskGraphDefinition | null;
  currentTaskGraphSnapshotRefs: TaskGraphSnapshotRef[];
  currentTaskGraphEditHistory: TaskGraphEditHistoryState;
  currentTaskGraphCommandLog: TaskGraphCommandLogEntry[];
  selectedTaskGraphSnapshot: TaskGraphSnapshotRef | null;
  currentTaskGraphRunRef: TaskGraphRunRef | null;
  authoritativeActiveTaskGraphRunRef: TaskGraphRunRef | null;
  datasetState: TaskGraphStateDatasetPayload;
};

export function selectTaskGraphAppState(args: {
  activeTaskGraphId: string | null;
  selectedTaskGraphId: string | null;
  currentTask: ProjectTask | null;
  routeGraph: TaskGraphDefinition | null | undefined;
  routeTaskGraphDefinitions?: TaskGraphDefinition[] | null | undefined;
  routeTaskRunRefs?: TaskGraphRunRef[] | null | undefined;
  fallbackTaskGraph: TaskGraphDefinition | null;
  taskGraphRouteUnavailable: boolean;
  taskGraphNodeOverrides: Record<string, Partial<TaskGraphDefinition["nodes"][number]>>;
  taskGraphEditHistoryByGraphId: Record<string, TaskGraphEditHistoryState>;
  taskGraphCommandLog: TaskGraphCommandLogEntry[];
  selectedTaskGraphSnapshotId: string | null;
  taskGraphOptimisticLiveRunRefs: Record<string, TaskGraphRunRef>;
  taskGraphLiveRunRefs: Record<string, TaskGraphRunRef>;
  taskGraphDryRunRunRef: TaskGraphRunRef | null;
  runTaskGraphPending: boolean;
  taskGraphLiveDispatchStarted: boolean;
  graphWorkspaceOpen: boolean;
  nowMs?: number;
}): TaskGraphAppStateSelection {
  const latestSelectedGraph = latestTaskGraphDefinition(
    args.currentTask?.graph_definitions,
  );
  const latestRenderableGraph = hasRenderableTaskGraphStructure(latestSelectedGraph)
    ? latestSelectedGraph
    : null;
  const selectedTaskGraph = args.activeTaskGraphId
    ? args.currentTask?.graph_definitions?.find(
        (graph) => graph.graph_id === args.activeTaskGraphId,
      ) ?? null
    : latestSelectedGraph ?? null;
  const selectedRenderableGraph = hasRenderableTaskGraphStructure(selectedTaskGraph)
    ? selectedTaskGraph
    : null;
  const routeGraph =
    args.activeTaskGraphId == null
      ? args.routeGraph ?? null
      : args.routeGraph?.graph_id === args.activeTaskGraphId
        ? args.routeGraph
        : null;
  const preferredServerGraph =
    routeGraph ?? selectedRenderableGraph ?? latestRenderableGraph ?? null;
  const currentTaskGraphBase = (() => {
    if (args.taskGraphRouteUnavailable) {
      return args.fallbackTaskGraph ?? null;
    }
    if (isTaskGraphNewer(args.fallbackTaskGraph, preferredServerGraph)) {
      return args.fallbackTaskGraph;
    }
    if (args.activeTaskGraphId) {
      if (routeGraph?.graph_id === args.activeTaskGraphId) {
        return routeGraph;
      }
      if (selectedRenderableGraph) {
        return selectedRenderableGraph;
      }
      if (args.fallbackTaskGraph?.graph_id === args.activeTaskGraphId) {
        return args.fallbackTaskGraph;
      }
      return preferredServerGraph ?? null;
    }
    return preferredServerGraph ?? args.fallbackTaskGraph ?? null;
  })();

  const currentTaskGraph = applyTaskGraphNodeOverrides(
    currentTaskGraphBase,
    args.taskGraphNodeOverrides,
  );
  const graphId = currentTaskGraph?.graph_id ?? args.activeTaskGraphId;
  const currentTaskGraphSnapshotRefs = graphId
    ? (args.currentTask?.graph_snapshot_refs ?? []).filter(
        (item) => item.graph_id === graphId,
      )
    : [];
  const currentTaskGraphEditHistory = graphId
    ? args.taskGraphEditHistoryByGraphId[graphId] ??
      emptyTaskGraphEditHistoryState()
    : emptyTaskGraphEditHistoryState();
  const currentTaskGraphCommandLog = graphId
    ? args.taskGraphCommandLog.filter((item) => item.graph_id === graphId)
    : [];
  const selectedTaskGraphSnapshot =
    currentTaskGraphSnapshotRefs.find(
      (item) => item.snapshot_id === args.selectedTaskGraphSnapshotId,
    ) ??
    currentTaskGraphSnapshotRefs[0] ??
    null;
  const currentTaskGraphRunRef = selectCurrentTaskGraphRunRef({
    graphId,
    optimisticRunRefs: Object.values(args.taskGraphOptimisticLiveRunRefs),
    liveRunRefs: Object.values(args.taskGraphLiveRunRefs),
    routeTaskRunRefs: args.routeTaskRunRefs,
    currentTaskRunRefs: args.currentTask?.graph_run_refs,
    dryRunRunRef: args.taskGraphDryRunRunRef ?? null,
    allowCachedActiveRunRef:
      args.runTaskGraphPending && args.taskGraphLiveDispatchStarted,
    allowOptimisticActiveRunRef: args.taskGraphLiveDispatchStarted,
  });
  const authoritativeActiveTaskGraphRunRef = selectLatestTaskGraphRunRef(
    graphId,
    [
      (args.routeTaskRunRefs ?? []).filter(
        (item) =>
          item &&
          String(item.status ?? "").trim() !== "" &&
          ["queued", "running", "paused_for_review"].includes(
            String(item.status ?? "").trim(),
          ),
      ),
      (args.currentTask?.graph_run_refs ?? []).filter(
        (item) =>
          item &&
          String(item.status ?? "").trim() !== "" &&
          ["queued", "running", "paused_for_review"].includes(
            String(item.status ?? "").trim(),
          ),
      ),
    ],
  );
  return {
    currentTaskGraphBase,
    currentTaskGraph,
    currentTaskGraphSnapshotRefs,
    currentTaskGraphEditHistory,
    currentTaskGraphCommandLog,
    selectedTaskGraphSnapshot,
    currentTaskGraphRunRef,
    authoritativeActiveTaskGraphRunRef,
    datasetState: {
      at: args.nowMs ?? Date.now(),
      graphWorkspaceOpen: args.graphWorkspaceOpen,
      selectedTaskGraphId: args.selectedTaskGraphId,
      activeTaskGraphId: args.activeTaskGraphId,
      fallbackGraphId: args.fallbackTaskGraph?.graph_id ?? null,
      routeGraphId: args.routeGraph?.graph_id ?? null,
      routeTaskGraphIds: (
        args.routeTaskGraphDefinitions ?? []
      ).map((graph) => graph.graph_id),
      currentTaskGraphIds: (args.currentTask?.graph_definitions ?? []).map(
        (graph) => graph.graph_id,
      ),
      latestCurrentTaskGraphId: latestSelectedGraph?.graph_id ?? null,
      currentTaskGraphBaseId: currentTaskGraphBase?.graph_id ?? null,
      currentTaskGraphId: currentTaskGraph?.graph_id ?? null,
      currentTaskGraphTemplateId: currentTaskGraph?.template_id ?? null,
    },
  };
}
