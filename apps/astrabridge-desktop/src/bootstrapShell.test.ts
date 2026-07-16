import { describe, expect, it, vi } from "vitest";

import {
  bootstrapFail,
  bootstrapFailureMessage,
  bootstrapNote,
  bootstrapReady,
  bootstrapState,
  bootstrapStalled,
  scheduleBootstrapReady,
} from "./bootstrapShell";

describe("bootstrapShell", () => {
  it("formats useful startup failures", () => {
    expect(bootstrapFailureMessage(new Error("module import timed out"))).toContain("module import timed out");
    expect(bootstrapFailureMessage("bad root")).toContain("bad root");
    expect(bootstrapFailureMessage({ reason: "network" })).toContain("network");
    expect(bootstrapFailureMessage(null)).toBe("AstraBridge 前端入口未能完成启动。");
  });

  it("proxies bootstrap shell status updates through the window contract", () => {
    const note = vi.fn();
    const ready = vi.fn();
    const stalled = vi.fn();
    const fail = vi.fn();
    const state = vi.fn(() => "loading" as const);

    window.__AB_BOOTSTRAP__ = { note, ready, stalled, fail, state };

    bootstrapNote("connecting");
    bootstrapReady("mounted");
    bootstrapStalled("slow");
    bootstrapFail(new Error("entry failed"), "startup failed");

    expect(note).toHaveBeenCalledWith("connecting");
    expect(ready).toHaveBeenCalledWith("mounted");
    expect(stalled).toHaveBeenCalledWith("slow");
    expect(fail).toHaveBeenCalledWith("startup failed entry failed");
    expect(bootstrapState()).toBe("loading");
  });

  it("waits for a visible shell surface before marking bootstrap ready", () => {
    const ready = vi.fn();
    const stalled = vi.fn();
    window.__AB_BOOTSTRAP__ = { ready };
    window.__AB_BOOTSTRAP__.stalled = stalled;

    const frameQueue: FrameRequestCallback[] = [];
    const originalRequestAnimationFrame = window.requestAnimationFrame;
    const originalQuerySelector = document.querySelector.bind(document);
    window.requestAnimationFrame = vi.fn((callback: FrameRequestCallback) => {
      frameQueue.push(callback);
      return frameQueue.length;
    });
    let hasReadySurface = false;
    document.querySelector = vi.fn((selector: string) => {
      if (selector === "[data-testid='app-shell']" && hasReadySurface) {
        return document.body;
      }
      return null;
    }) as typeof document.querySelector;

    scheduleBootstrapReady("visible");

    expect(ready).not.toHaveBeenCalled();
    expect(frameQueue).toHaveLength(1);

    frameQueue.shift()?.(16.7);
    expect(ready).not.toHaveBeenCalled();
    expect(frameQueue).toHaveLength(1);

    hasReadySurface = true;
    frameQueue.shift()?.(33.4);
    expect(ready).toHaveBeenCalledWith("visible");
    expect(stalled).not.toHaveBeenCalled();

    window.requestAnimationFrame = originalRequestAnimationFrame;
    document.querySelector = originalQuerySelector;
  });

  it("still clears the bootstrap shell when the app shell appears after an error state", () => {
    const ready = vi.fn();
    const state = vi.fn(() => "error" as const);
    window.__AB_BOOTSTRAP__ = { ready, state };

    const frameQueue: FrameRequestCallback[] = [];
    const originalRequestAnimationFrame = window.requestAnimationFrame;
    const originalQuerySelector = document.querySelector.bind(document);
    window.requestAnimationFrame = vi.fn((callback: FrameRequestCallback) => {
      frameQueue.push(callback);
      return frameQueue.length;
    });
    let hasReadySurface = false;
    document.querySelector = vi.fn((selector: string) => {
      if (selector === "[data-testid='app-shell']" && hasReadySurface) {
        return document.body;
      }
      return null;
    }) as typeof document.querySelector;

    scheduleBootstrapReady("late visible");

    expect(frameQueue).toHaveLength(1);
    frameQueue.shift()?.(16.7);
    expect(ready).not.toHaveBeenCalled();

    hasReadySurface = true;
    frameQueue.shift()?.(33.4);
    expect(ready).toHaveBeenCalledWith("late visible");

    window.requestAnimationFrame = originalRequestAnimationFrame;
    document.querySelector = originalQuerySelector;
  });
});
