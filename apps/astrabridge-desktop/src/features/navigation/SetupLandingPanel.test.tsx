import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SetupLandingPanel } from "./SetupLandingPanel";

describe("SetupLandingPanel", () => {
  it("renders metrics and action rows", () => {
    render(
      <SetupLandingPanel
        testId="setup-landing"
        eyebrow="Workspace"
        title="File"
        summary="A compact landing page."
        stateLabel="Current state"
        stateItems={[
          { id: "a", label: "Tasks", value: "12" },
          { id: "b", label: "Reports", value: "3" },
        ]}
        sectionTitle="Quick actions"
        actions={[
          {
            id: "open",
            icon: <span>O</span>,
            title: "Open reports",
            detail: "Inspect recent output.",
            status: "3 items",
            actionLabel: "Open",
            onClick: vi.fn(),
          },
        ]}
      />,
    );

    expect(screen.getByTestId("setup-landing")).toBeTruthy();
    expect(screen.getByText("File")).toBeTruthy();
    expect(screen.getByText("Tasks")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy();
    expect(screen.getByText("Open reports")).toBeTruthy();
    expect(screen.getByText("3 items")).toBeTruthy();
  });

  it("wires action callbacks", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();

    render(
      <SetupLandingPanel
        testId="setup-landing"
        eyebrow="Workspace"
        title="Tools"
        summary="A compact landing page."
        stateLabel="Current state"
        stateItems={[{ id: "a", label: "Skills", value: "8" }]}
        sectionTitle="Quick actions"
        actions={[
          {
            id: "open",
            icon: <span>T</span>,
            title: "Open skills",
            detail: "Inspect the registry.",
            status: "8 ready",
            actionLabel: "Open",
            onClick,
          },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Open skills/i }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
