export type TaskGraphWorkspaceInspectorWorkspace = "selection" | "run";

export type TaskGraphWorkspaceStoredState = {
  sidebarExpanded: boolean;
  inspectorExpanded: boolean;
  inspectorWorkspace: TaskGraphWorkspaceInspectorWorkspace;
  readinessExpanded: boolean;
  latestRunExpanded: boolean;
  recoveryExpanded: boolean;
};

export const TASK_GRAPH_SIDEBAR_WIDTH_STORAGE_KEY =
  "astrabridge.task_graph.sidebar_width";
export const TASK_GRAPH_WORKSPACE_STATE_STORAGE_KEY_PREFIX =
  "astrabridge.task_graph.workspace_state";
export const DEFAULT_TASK_GRAPH_SIDEBAR_WIDTH = 60;
export const MIN_TASK_GRAPH_SIDEBAR_WIDTH = 52;
const MAX_TASK_GRAPH_SIDEBAR_WIDTH = 80;

function clamp(value: number, min: number, max: number) {
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

function taskGraphPanelWidthRange(side: "left") {
  const viewportWidth =
    typeof window === "undefined" ? 1440 : window.innerWidth;
  return {
    min: MIN_TASK_GRAPH_SIDEBAR_WIDTH,
    max: Math.max(
      MIN_TASK_GRAPH_SIDEBAR_WIDTH,
      Math.min(
        MAX_TASK_GRAPH_SIDEBAR_WIDTH,
        Math.round(viewportWidth * 0.08),
      ),
    ),
  };
}

export function normalizeTaskGraphPanelWidth(side: "left", value: number) {
  const { min, max } = taskGraphPanelWidthRange(side);
  return clamp(Math.round(value), min, max);
}

export function readStoredTaskGraphPanelWidth(
  side: "left",
  storageKey: string,
  fallback: number,
) {
  if (typeof window === "undefined") return fallback;
  const rawValue = Number.parseFloat(
    window.localStorage.getItem(storageKey) || "",
  );
  if (!Number.isFinite(rawValue)) return fallback;
  return normalizeTaskGraphPanelWidth(side, rawValue);
}

export function writeStoredTaskGraphPanelWidth(
  storageKey: string,
  side: "left",
  value: number,
) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    storageKey,
    String(normalizeTaskGraphPanelWidth(side, value)),
  );
}

export function taskGraphWorkspaceStateStorageKey(
  taskId: string | undefined,
  graphId: string | undefined,
) {
  const normalizedTaskId = String(taskId || "").trim();
  const normalizedGraphId = String(graphId || "").trim();
  if (!normalizedTaskId || !normalizedGraphId) return null;
  return `${TASK_GRAPH_WORKSPACE_STATE_STORAGE_KEY_PREFIX}.${normalizedTaskId}.${normalizedGraphId}`;
}

export function buildPendingRunInspectorStorageKey(
  workspaceStateStorageKey: string | null,
) {
  return workspaceStateStorageKey
    ? `${workspaceStateStorageKey}.pending_run_inspector`
    : null;
}

export function readStoredTaskGraphWorkspaceState(
  storageKey: string,
): TaskGraphWorkspaceStoredState | null {
  if (typeof window === "undefined") return null;
  try {
    const rawValue = window.localStorage.getItem(storageKey);
    if (!rawValue) return null;
    const parsed = JSON.parse(rawValue) as Partial<TaskGraphWorkspaceStoredState>;
    if (
      parsed.inspectorWorkspace !== "selection" &&
      parsed.inspectorWorkspace !== "run"
    ) {
      return null;
    }
    return {
      sidebarExpanded: Boolean(parsed.sidebarExpanded),
      inspectorExpanded: Boolean(parsed.inspectorExpanded),
      inspectorWorkspace: parsed.inspectorWorkspace,
      readinessExpanded: Boolean(parsed.readinessExpanded),
      latestRunExpanded: Boolean(parsed.latestRunExpanded),
      recoveryExpanded: Boolean(parsed.recoveryExpanded),
    };
  } catch {
    return null;
  }
}

export function writeStoredTaskGraphWorkspaceState(
  storageKey: string | null,
  state: TaskGraphWorkspaceStoredState,
) {
  if (typeof window === "undefined" || !storageKey) return;
  window.localStorage.setItem(storageKey, JSON.stringify(state));
}

export function writePendingRunInspectorReopen(
  storageKey: string | null,
  value: boolean,
) {
  if (typeof window === "undefined" || !storageKey) return;
  try {
    if (value) {
      window.localStorage.setItem(storageKey, "1");
      return;
    }
    window.localStorage.removeItem(storageKey);
  } catch {
    // Ignore storage write failures; they only affect best-effort modal restore.
  }
}

export function consumePendingRunInspectorReopen(
  storageKey: string | null,
): boolean {
  if (typeof window === "undefined" || !storageKey) return false;
  try {
    const pending = window.localStorage.getItem(storageKey) === "1";
    if (pending) {
      window.localStorage.removeItem(storageKey);
    }
    return pending;
  } catch {
    return false;
  }
}
