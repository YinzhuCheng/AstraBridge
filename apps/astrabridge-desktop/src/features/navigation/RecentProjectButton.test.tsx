import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProjectSummary } from "../../types";
import { RecentProjectButton } from "./RecentProjectButton";

function buildProject(overrides: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    project_id: "demo",
    name: "Provider Switch Live 20260622-224524\nD:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace",
    project_file: "D:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/demo.abproj",
    workspace_root: "D:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace",
    entry_mode: "new",
    updated_at: "2026-07-11T15:52:21.351304+09:00",
    ...overrides,
  };
}

describe("RecentProjectButton", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows only the compact title while keeping full paths in the tooltip", () => {
    render(
      <RecentProjectButton
        project={buildProject()}
        relativeTimeLabel="now"
        onOpen={vi.fn()}
      />,
    );

    const button = screen.getByRole("button", { name: "Provider Switch Live 20260622-224524" });
    expect(button).toHaveAttribute(
      "title",
      "Provider Switch Live 20260622-224524\nD:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace\nD:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/demo.abproj",
    );
    expect(screen.queryByText(/D:\/AstraBridge\/PRIVATE/i)).toBeNull();
    expect(screen.getByText("now")).toBeTruthy();
  });

  it("opens the selected project file", async () => {
    const onOpen = vi.fn();
    const user = userEvent.setup();
    const project = buildProject();

    render(
      <RecentProjectButton
        project={project}
        relativeTimeLabel="2d"
        onOpen={onOpen}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Provider Switch Live 20260622-224524" }));
    expect(onOpen).toHaveBeenCalledWith(project.project_file);
  });

  it("does not open when disabled", async () => {
    const onOpen = vi.fn();
    const user = userEvent.setup();

    render(
      <RecentProjectButton
        project={buildProject()}
        relativeTimeLabel="2d"
        onOpen={onOpen}
        disabled
      />,
    );

    const button = screen.getByRole("button", { name: "Provider Switch Live 20260622-224524" });
    expect(button).toBeDisabled();
    await user.click(button);
    expect(onOpen).not.toHaveBeenCalled();
  });
});
