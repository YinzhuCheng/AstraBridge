import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StarbridgeWaitingConstellation } from "./StarbridgeWaitingConstellation";

function stubMatchMedia(matches: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("StarbridgeWaitingConstellation", () => {
  afterEach(() => cleanup());

  it("renders animated inline waiting state by default", () => {
    stubMatchMedia(false);
    render(<StarbridgeWaitingConstellation phase="thinking" title="Thinking" detail="Preparing the next step." />);

    expect(screen.getByTestId("starbridge-waiting")).toHaveAttribute("data-variant", "inline");
    expect(screen.getByTestId("starbridge-waiting")).toHaveAttribute("data-phase", "thinking");
    expect(screen.getByTestId("starbridge-waiting")).toHaveAttribute("data-motion", "animated");
    expect(screen.getByTestId("starbridge-waiting-traveler-0")).toBeInTheDocument();
    expect(screen.getByText("Thinking")).toBeInTheDocument();
  });

  it("supports the panel variant with explicit labels", () => {
    stubMatchMedia(false);
    render(
      <StarbridgeWaitingConstellation
        variant="panel"
        phase="files"
        label="Medium wait"
        title="Editing files"
        detail="Tracking diffs before the response lands."
      />,
    );

    expect(screen.getByTestId("starbridge-waiting")).toHaveAttribute("data-variant", "panel");
    expect(screen.getByText("Medium wait")).toBeInTheDocument();
    expect(screen.getByText("Editing files")).toBeInTheDocument();
  });

  it("drops traveler motion under reduced motion", () => {
    stubMatchMedia(true);
    render(<StarbridgeWaitingConstellation variant="panel" phase="approval" />);

    expect(screen.getByTestId("starbridge-waiting")).toHaveAttribute("data-motion", "reduced");
    expect(screen.queryByTestId("starbridge-waiting-traveler-0")).toBeNull();
  });
});
