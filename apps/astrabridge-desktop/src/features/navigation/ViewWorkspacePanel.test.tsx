import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ViewWorkspacePanel } from "./ViewWorkspacePanel";

describe("ViewWorkspacePanel", () => {
  it("renders current workspace state and quick actions", () => {
    render(
      <ViewWorkspacePanel
        locale="zh-CN"
        leftSidebarOpen={true}
        rightSidebarOpen={false}
        archivedVisible={true}
        onOpenSearch={vi.fn()}
        onOpenArchived={vi.fn()}
        onReturnToChat={vi.fn()}
        onToggleLeftSidebar={vi.fn()}
        onToggleRightSidebar={vi.fn()}
      />,
    );

    expect(screen.getByTestId("workspace-view-panel")).toBeTruthy();
    expect(screen.getByText("视图")).toBeTruthy();
    expect(screen.getByText("搜索当前工作区")).toBeTruthy();
    expect(screen.getByText("归档任务")).toBeTruthy();
    expect(screen.getAllByText("Ctrl+K")).toHaveLength(2);
  });

  it("wires actions to the provided callbacks", () => {
    const onOpenSearch = vi.fn();
    const onOpenArchived = vi.fn();
    const onReturnToChat = vi.fn();
    const onToggleLeftSidebar = vi.fn();
    const onToggleRightSidebar = vi.fn();

    render(
      <ViewWorkspacePanel
        locale="en"
        leftSidebarOpen={false}
        rightSidebarOpen={true}
        archivedVisible={false}
        onOpenSearch={onOpenSearch}
        onOpenArchived={onOpenArchived}
        onReturnToChat={onReturnToChat}
        onToggleLeftSidebar={onToggleLeftSidebar}
        onToggleRightSidebar={onToggleRightSidebar}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Search the workspace/i }));
    fireEvent.click(screen.getByRole("button", { name: /Open archived tasks/i }));
    fireEvent.click(screen.getByRole("button", { name: /Show left sidebar/i }));
    fireEvent.click(screen.getByRole("button", { name: /Hide right inspector/i }));
    fireEvent.click(screen.getByRole("button", { name: /Return to current chat/i }));

    expect(onOpenSearch).toHaveBeenCalledTimes(1);
    expect(onOpenArchived).toHaveBeenCalledTimes(1);
    expect(onToggleLeftSidebar).toHaveBeenCalledTimes(1);
    expect(onToggleRightSidebar).toHaveBeenCalledTimes(1);
    expect(onReturnToChat).toHaveBeenCalledTimes(1);
  });
});
