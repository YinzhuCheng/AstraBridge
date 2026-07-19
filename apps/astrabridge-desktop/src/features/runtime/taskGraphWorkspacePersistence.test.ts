import { afterEach, describe, expect, it } from "vitest";

import {
  buildPendingRunInspectorStorageKey,
  consumePendingRunInspectorReopen,
  DEFAULT_TASK_GRAPH_SIDEBAR_WIDTH,
  readStoredTaskGraphPanelWidth,
  readStoredTaskGraphWorkspaceState,
  taskGraphWorkspaceStateStorageKey,
  writePendingRunInspectorReopen,
  writeStoredTaskGraphPanelWidth,
  writeStoredTaskGraphWorkspaceState,
} from "./taskGraphWorkspacePersistence";

afterEach(() => {
  window.localStorage.clear();
});

describe("taskGraphWorkspacePersistence", () => {
  it("builds stable workspace storage keys only when task and graph ids exist", () => {
    expect(taskGraphWorkspaceStateStorageKey(undefined, "graph-1")).toBeNull();
    expect(taskGraphWorkspaceStateStorageKey("task-1", undefined)).toBeNull();
    expect(taskGraphWorkspaceStateStorageKey("task-1", "graph-1")).toBe(
      "astrabridge.task_graph.workspace_state.task-1.graph-1",
    );
    expect(
      buildPendingRunInspectorStorageKey(
        taskGraphWorkspaceStateStorageKey("task-1", "graph-1"),
      ),
    ).toBe(
      "astrabridge.task_graph.workspace_state.task-1.graph-1.pending_run_inspector",
    );
  });

  it("round-trips stored workspace state and rejects invalid inspector workspaces", () => {
    const storageKey = taskGraphWorkspaceStateStorageKey("task-1", "graph-1");
    expect(storageKey).toBeTruthy();
    writeStoredTaskGraphWorkspaceState(storageKey, {
      sidebarExpanded: true,
      inspectorExpanded: false,
      inspectorWorkspace: "run",
      readinessExpanded: true,
      latestRunExpanded: true,
      recoveryExpanded: false,
    });
    expect(readStoredTaskGraphWorkspaceState(storageKey!)).toEqual({
      sidebarExpanded: true,
      inspectorExpanded: false,
      inspectorWorkspace: "run",
      readinessExpanded: true,
      latestRunExpanded: true,
      recoveryExpanded: false,
    });

    window.localStorage.setItem(
      storageKey!,
      JSON.stringify({
        sidebarExpanded: true,
        inspectorExpanded: false,
        inspectorWorkspace: "invalid",
      }),
    );
    expect(readStoredTaskGraphWorkspaceState(storageKey!)).toBeNull();
  });

  it("normalizes persisted sidebar widths through the shared owner", () => {
    writeStoredTaskGraphPanelWidth(
      "astrabridge.task_graph.sidebar_width",
      "left",
      999,
    );
    expect(window.localStorage.getItem("astrabridge.task_graph.sidebar_width")).toBe(
      "80",
    );

    window.localStorage.setItem("astrabridge.task_graph.sidebar_width", "12");
    expect(
      readStoredTaskGraphPanelWidth(
        "left",
        "astrabridge.task_graph.sidebar_width",
        DEFAULT_TASK_GRAPH_SIDEBAR_WIDTH,
      ),
    ).toBe(52);
  });

  it("consumes the pending run inspector reopen marker exactly once", () => {
    const storageKey = buildPendingRunInspectorStorageKey(
      taskGraphWorkspaceStateStorageKey("task-1", "graph-1"),
    );
    writePendingRunInspectorReopen(storageKey, true);

    expect(consumePendingRunInspectorReopen(storageKey)).toBe(true);
    expect(window.localStorage.getItem(storageKey!)).toBeNull();
    expect(consumePendingRunInspectorReopen(storageKey)).toBe(false);
  });
});
