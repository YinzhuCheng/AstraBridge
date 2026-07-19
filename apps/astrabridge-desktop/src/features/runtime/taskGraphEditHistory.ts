import type { TaskGraphDefinition } from "../../types";

export type TaskGraphEditHistorySelection = {
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
};

export type TaskGraphEditHistoryAction = "delete_node" | "delete_edge";

export type TaskGraphEditHistoryEntry = {
  entry_id: string;
  graph_id: string;
  action: TaskGraphEditHistoryAction;
  summary: string;
  graph_before: TaskGraphDefinition;
  graph_after: TaskGraphDefinition;
  selection_before: TaskGraphEditHistorySelection;
  selection_after: TaskGraphEditHistorySelection;
  created_at: string;
};

export type TaskGraphEditHistoryState = {
  entries: TaskGraphEditHistoryEntry[];
  cursor: number;
};

export type TaskGraphEditHistoryTransition = {
  state: TaskGraphEditHistoryState;
  graph: TaskGraphDefinition;
  selection: TaskGraphEditHistorySelection;
  entry: TaskGraphEditHistoryEntry;
};

export function emptyTaskGraphEditHistoryState(): TaskGraphEditHistoryState {
  return { entries: [], cursor: 0 };
}

export function canUndoTaskGraphEditHistory(state: TaskGraphEditHistoryState | null | undefined) {
  return Boolean(state && state.cursor > 0 && state.entries.length);
}

export function canRedoTaskGraphEditHistory(state: TaskGraphEditHistoryState | null | undefined) {
  return Boolean(state && state.cursor < state.entries.length);
}

export function pushTaskGraphEditHistory(
  state: TaskGraphEditHistoryState | null | undefined,
  entry: TaskGraphEditHistoryEntry,
  limit = 20,
): TaskGraphEditHistoryState {
  const current = state ?? emptyTaskGraphEditHistoryState();
  const truncated = current.entries.slice(0, current.cursor);
  const nextEntries = [...truncated, entry];
  const boundedEntries =
    nextEntries.length > limit ? nextEntries.slice(nextEntries.length - limit) : nextEntries;
  return {
    entries: boundedEntries,
    cursor: boundedEntries.length,
  };
}

export function undoTaskGraphEditHistory(
  state: TaskGraphEditHistoryState | null | undefined,
): TaskGraphEditHistoryTransition | null {
  const current = state ?? emptyTaskGraphEditHistoryState();
  if (!canUndoTaskGraphEditHistory(current)) return null;
  const entry = current.entries[current.cursor - 1];
  return {
    state: {
      entries: current.entries,
      cursor: current.cursor - 1,
    },
    graph: entry.graph_before,
    selection: entry.selection_before,
    entry,
  };
}

export function redoTaskGraphEditHistory(
  state: TaskGraphEditHistoryState | null | undefined,
): TaskGraphEditHistoryTransition | null {
  const current = state ?? emptyTaskGraphEditHistoryState();
  if (!canRedoTaskGraphEditHistory(current)) return null;
  const entry = current.entries[current.cursor];
  return {
    state: {
      entries: current.entries,
      cursor: current.cursor + 1,
    },
    graph: entry.graph_after,
    selection: entry.selection_after,
    entry,
  };
}
