import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ComposerStarTrack } from "./ComposerStarTrack";

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

describe("ComposerStarTrack", () => {
  afterEach(() => cleanup());

  it("renders armed state with live traveler by default", () => {
    stubMatchMedia(false);
    render(<ComposerStarTrack state="sending" armed />);

    expect(screen.getByTestId("composer-star-track")).toHaveAttribute("data-state", "sending");
    expect(screen.getByTestId("composer-star-track")).toHaveAttribute("data-armed", "true");
    expect(screen.getByTestId("composer-star-track")).toHaveAttribute("data-motion", "animated");
    expect(screen.getByTestId("composer-star-track-traveler")).toBeInTheDocument();
  });

  it("drops the traveler under reduced motion", () => {
    stubMatchMedia(true);
    render(<ComposerStarTrack state="idle" armed={false} />);

    expect(screen.getByTestId("composer-star-track")).toHaveAttribute("data-motion", "reduced");
    expect(screen.queryByTestId("composer-star-track-traveler")).toBeNull();
  });
});
