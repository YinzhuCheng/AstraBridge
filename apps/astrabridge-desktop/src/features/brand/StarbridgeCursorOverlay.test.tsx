import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StarbridgeCursorOverlay } from "./StarbridgeCursorOverlay";

function stubMatchMedia(map: Record<string, boolean>) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: map[query] ?? false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("StarbridgeCursorOverlay", () => {
  afterEach(() => cleanup());

  it("tracks passive cursor semantics across default, hover, and text targets", () => {
    stubMatchMedia({
      "(pointer: fine)": true,
      "(prefers-reduced-motion: reduce)": false,
    });

    render(
      <div>
        <StarbridgeCursorOverlay />
        <div data-testid="plain">Plain</div>
        <button type="button">Hover me</button>
        <textarea aria-label="Composer input" />
      </div>,
    );

    const overlay = screen.getByTestId("starbridge-cursor-overlay");
    fireEvent.pointerMove(screen.getByTestId("plain"), { clientX: 48, clientY: 32, pointerType: "mouse" });
    expect(overlay).toHaveAttribute("data-visible", "true");
    expect(overlay).toHaveAttribute("data-mode", "default");

    fireEvent.pointerMove(screen.getByRole("button", { name: "Hover me" }), { clientX: 58, clientY: 34, pointerType: "mouse" });
    expect(overlay).toHaveAttribute("data-mode", "hover");

    fireEvent.pointerMove(screen.getByLabelText("Composer input"), { clientX: 60, clientY: 36, pointerType: "mouse" });
    expect(overlay).toHaveAttribute("data-mode", "text");
  });

  it("switches into drag mode only while a drag-capable control is pressed", () => {
    stubMatchMedia({
      "(pointer: fine)": true,
      "(prefers-reduced-motion: reduce)": false,
    });

    render(
      <div>
        <StarbridgeCursorOverlay />
        <div role="separator" data-testid="drag-handle">
          Resize
        </div>
      </div>,
    );

    const overlay = screen.getByTestId("starbridge-cursor-overlay");
    const handle = screen.getByTestId("drag-handle");

    fireEvent.pointerMove(handle, { clientX: 70, clientY: 48, pointerType: "mouse" });
    expect(overlay).toHaveAttribute("data-mode", "hover");

    fireEvent.pointerDown(handle, { clientX: 70, clientY: 48, pointerType: "mouse", buttons: 1 });
    fireEvent.pointerMove(handle, { clientX: 92, clientY: 48, pointerType: "mouse", buttons: 1 });
    expect(overlay).toHaveAttribute("data-mode", "drag");

    fireEvent.pointerUp(handle, { clientX: 92, clientY: 48, pointerType: "mouse" });
    expect(overlay).toHaveAttribute("data-mode", "hover");
  });

  it("drops dust travelers under reduced motion", () => {
    stubMatchMedia({
      "(pointer: fine)": true,
      "(prefers-reduced-motion: reduce)": true,
    });

    render(<StarbridgeCursorOverlay />);

    const overlay = screen.getByTestId("starbridge-cursor-overlay");
    expect(overlay).toHaveAttribute("data-motion", "reduced");
    expect(overlay).toHaveAttribute("data-quality", "minimal");
    expect(document.querySelector(".starbridge-cursor-anchor-dust")).toBeNull();
    expect(document.querySelector(".starbridge-cursor-anchor-trail")).toBeNull();
  });

  it("respects the explicit off preference", () => {
    stubMatchMedia({
      "(pointer: fine)": true,
      "(prefers-reduced-motion: reduce)": false,
    });

    render(<StarbridgeCursorOverlay preference="off" />);

    expect(screen.queryByTestId("starbridge-cursor-overlay")).toBeNull();
  });

  it("falls back to economy mode on low-power devices", () => {
    stubMatchMedia({
      "(pointer: fine)": true,
      "(prefers-reduced-motion: reduce)": false,
    });
    Object.defineProperty(window.navigator, "hardwareConcurrency", {
      configurable: true,
      value: 4,
    });

    render(<StarbridgeCursorOverlay />);

    const overlay = screen.getByTestId("starbridge-cursor-overlay");
    expect(overlay).toHaveAttribute("data-quality", "economy");
    expect(document.querySelector(".starbridge-cursor-anchor-trail")).not.toBeNull();
    expect(document.querySelector(".starbridge-cursor-anchor-dust")).toBeNull();
  });

  it("starts its animation frame loop only after pointer activity", () => {
    stubMatchMedia({
      "(pointer: fine)": true,
      "(prefers-reduced-motion: reduce)": false,
    });

    const raf = vi.fn(() => 1);
    const caf = vi.fn();
    Object.defineProperty(window, "requestAnimationFrame", {
      configurable: true,
      value: raf,
    });
    Object.defineProperty(window, "cancelAnimationFrame", {
      configurable: true,
      value: caf,
    });

    render(
      <div>
        <StarbridgeCursorOverlay />
        <button type="button">Wake overlay</button>
      </div>,
    );

    expect(raf).not.toHaveBeenCalled();

    fireEvent.pointerMove(screen.getByRole("button", { name: "Wake overlay" }), { clientX: 84, clientY: 44, pointerType: "mouse" });
    expect(raf).toHaveBeenCalledTimes(1);

    fireEvent.blur(window);
    expect(caf).toHaveBeenCalledWith(1);
  });
});
