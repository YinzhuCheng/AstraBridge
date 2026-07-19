import { Compass, ScanSearch, X } from "lucide-react";
import type {
  KeyboardEventHandler,
  ReactNode,
  Ref,
} from "react";

type InspectorWorkspace = "selection" | "run";
type InspectorSelectionMode = "node" | "edge";

type TaskGraphInspectorSelectionModeControls = {
  mode: InspectorSelectionMode;
  nodeLabel: string;
  nodeTitle: string;
  edgeLabel: string;
  edgeTitle: string;
  edgeDisabled: boolean;
  onSelectNode: () => void;
  onSelectEdge: () => void;
};

type TaskGraphInspectorModalProps = {
  dialogRef: Ref<HTMLDivElement>;
  inspectorLabel: string;
  subtitle: string;
  workspace: InspectorWorkspace;
  selectionWorkspaceLabel: string;
  selectionWorkspaceHint: string;
  runWorkspaceLabel: string;
  runWorkspaceHint: string;
  collapseLabel: string;
  onClose: () => void;
  onKeyDown: KeyboardEventHandler<HTMLDivElement>;
  onSelectWorkspace: (workspace: InspectorWorkspace) => void;
  selectionModeControls?: TaskGraphInspectorSelectionModeControls | null;
  children: ReactNode;
};

export function TaskGraphInspectorModal({
  dialogRef,
  inspectorLabel,
  subtitle,
  workspace,
  selectionWorkspaceLabel,
  selectionWorkspaceHint,
  runWorkspaceLabel,
  runWorkspaceHint,
  collapseLabel,
  onClose,
  onKeyDown,
  onSelectWorkspace,
  selectionModeControls,
  children,
}: TaskGraphInspectorModalProps) {
  return (
    <div
      className="modal-scrim task-graph-inspector-scrim"
      onClick={onClose}
    >
      <div
        className="modal-card task-graph-inspector task-graph-inspector-modal"
        data-testid="task-graph-inspector"
        role="dialog"
        aria-modal="true"
        aria-label={inspectorLabel}
        tabIndex={-1}
        ref={dialogRef}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={onKeyDown}
      >
        <div className="task-graph-inspector-modal-header">
          <div className="task-graph-inspector-modal-copy">
            <div className="task-graph-panel-title">
              <span className="task-graph-sidebar-icon" aria-hidden="true">
                {workspace === "run" ? (
                  <Compass size={15} />
                ) : (
                  <ScanSearch size={15} />
                )}
              </span>
              <span className="task-graph-panel-title-copy">
                <strong>{inspectorLabel}</strong>
                <span>{subtitle}</span>
              </span>
            </div>
          </div>
          <button
            type="button"
            className="task-graph-inline-action task-graph-canvas-icon-button"
            data-testid="task-graph-inspector-close"
            onClick={onClose}
            title={collapseLabel}
            aria-label={collapseLabel}
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
        <div className="task-graph-inspector-shell">
          <div
            className="task-graph-inspector-overview"
            data-testid="task-graph-inspector-overview"
          >
            <div
              className="task-graph-inspector-workspace-switch"
              role="tablist"
              aria-label={inspectorLabel}
              data-testid="task-graph-inspector-workspace-switch"
            >
              <button
                type="button"
                role="tab"
                aria-selected={workspace === "selection"}
                className={`task-graph-mode-chip ${workspace === "selection" ? "task-graph-mode-chip-active" : ""}`}
                data-testid="task-graph-inspector-workspace-selection"
                title={selectionWorkspaceHint}
                onClick={() => onSelectWorkspace("selection")}
              >
                {selectionWorkspaceLabel}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={workspace === "run"}
                className={`task-graph-mode-chip ${workspace === "run" ? "task-graph-mode-chip-active" : ""}`}
                data-testid="task-graph-inspector-workspace-run"
                title={runWorkspaceHint}
                onClick={() => onSelectWorkspace("run")}
              >
                {runWorkspaceLabel}
              </button>
            </div>
          </div>
          {workspace === "selection" ? (
            <div className="task-graph-inspector-editor">
              {selectionModeControls ? (
                <div className="task-graph-inspector-modebar">
                  <button
                    type="button"
                    className={`task-graph-mode-chip ${selectionModeControls.mode === "node" ? "task-graph-mode-chip-active" : ""}`}
                    data-testid="task-graph-mode-node"
                    title={selectionModeControls.nodeTitle}
                    onClick={selectionModeControls.onSelectNode}
                  >
                    {selectionModeControls.nodeLabel}
                  </button>
                  <button
                    type="button"
                    className={`task-graph-mode-chip ${selectionModeControls.mode === "edge" ? "task-graph-mode-chip-active" : ""}`}
                    data-testid="task-graph-mode-edge"
                    title={selectionModeControls.edgeTitle}
                    onClick={selectionModeControls.onSelectEdge}
                    disabled={selectionModeControls.edgeDisabled}
                  >
                    {selectionModeControls.edgeLabel}
                  </button>
                </div>
              ) : null}
              {children}
            </div>
          ) : (
            children
          )}
        </div>
      </div>
    </div>
  );
}
