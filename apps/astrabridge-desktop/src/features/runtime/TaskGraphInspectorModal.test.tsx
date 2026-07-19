import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TaskGraphInspectorModal } from "./TaskGraphInspectorModal";

afterEach(() => {
  cleanup();
});

function renderModal(
  overrides: Partial<Parameters<typeof TaskGraphInspectorModal>[0]> = {},
) {
  const onClose = vi.fn();
  const onSelectWorkspace = vi.fn();
  const onSelectNode = vi.fn();
  const onSelectEdge = vi.fn();

  render(
    <TaskGraphInspectorModal
      dialogRef={createRef<HTMLDivElement>()}
      inspectorLabel="Inspector"
      subtitle="Selection workspace"
      workspace="selection"
      selectionWorkspaceLabel="Selection"
      selectionWorkspaceHint="Edit current selection"
      runWorkspaceLabel="Latest run"
      runWorkspaceHint="Inspect run readiness and output"
      collapseLabel="Collapse panel"
      onClose={onClose}
      onKeyDown={() => {}}
      onSelectWorkspace={onSelectWorkspace}
      selectionModeControls={{
        mode: "node",
        nodeLabel: "Node",
        nodeTitle: "Switch to node mode",
        edgeLabel: "Edge",
        edgeTitle: "Switch to edge mode",
        edgeDisabled: false,
        onSelectNode,
        onSelectEdge,
      }}
      {...overrides}
    >
      <div data-testid="task-graph-inspector-child">Child body</div>
    </TaskGraphInspectorModal>,
  );

  return { onClose, onSelectWorkspace, onSelectNode, onSelectEdge };
}

describe("TaskGraphInspectorModal", () => {
  it("renders workspace tabs and forwards close/workspace selection actions", () => {
    const { onClose, onSelectWorkspace } = renderModal({
      workspace: "run",
      subtitle: "Latest run",
      selectionModeControls: null,
    });

    expect(screen.getByTestId("task-graph-inspector")).toBeInTheDocument();
    expect(
      screen.getByTestId("task-graph-inspector-workspace-run"),
    ).toHaveAttribute("aria-selected", "true");

    fireEvent.click(screen.getByTestId("task-graph-inspector-workspace-selection"));
    expect(onSelectWorkspace).toHaveBeenCalledWith("selection");

    fireEvent.click(screen.getByTestId("task-graph-inspector-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders selection mode controls and forwards node/edge mode actions", () => {
    const { onSelectNode, onSelectEdge } = renderModal();

    fireEvent.click(screen.getByTestId("task-graph-mode-node"));
    expect(onSelectNode).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId("task-graph-mode-edge"));
    expect(onSelectEdge).toHaveBeenCalledTimes(1);
  });

  it("keeps the selection editor wrapper even when no mode controls are available", () => {
    renderModal({ selectionModeControls: null });

    expect(screen.getByTestId("task-graph-inspector-child")).toBeInTheDocument();
    expect(screen.queryByTestId("task-graph-mode-node")).not.toBeInTheDocument();
    expect(screen.queryByTestId("task-graph-mode-edge")).not.toBeInTheDocument();
  });
});
