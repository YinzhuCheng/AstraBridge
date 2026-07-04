import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StarbridgeCornerConstellation } from "./StarbridgeCornerConstellation";

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

describe("StarbridgeCornerConstellation", () => {
  afterEach(() => cleanup());

  it("renders animated travelers by default", () => {
    stubMatchMedia(false);
    render(<StarbridgeCornerConstellation variant="settings" />);

    expect(screen.getByTestId("starbridge-corner-accent")).toHaveAttribute("data-motion", "animated");
    expect(screen.getByTestId("starbridge-traveler-0")).toBeInTheDocument();
  });

  it("drops live motion layers under reduced motion", () => {
    stubMatchMedia(true);
    render(<StarbridgeCornerConstellation variant="guard" />);

    expect(screen.getByTestId("starbridge-corner-accent")).toHaveAttribute("data-motion", "reduced");
    expect(screen.queryByTestId("starbridge-traveler-0")).toBeNull();
  });
});
