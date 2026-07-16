import { describe, expect, it } from "vitest";

import { launcherSidecarGateMessage } from "./launcherSidecarGate";

describe("launcherSidecarGateMessage", () => {
  it("returns a localized pending copy", () => {
    expect(
      launcherSidecarGateMessage("zh-CN", { error: null, pending: true }),
    ).toBe("正在检查本地 sidecar 状态...");
    expect(
      launcherSidecarGateMessage("en", { error: null, pending: true }),
    ).toBe("Checking local sidecar status...");
  });

  it("normalizes fetch failures into a user-facing sidecar warning", () => {
    expect(
      launcherSidecarGateMessage("zh-CN", {
        error: new Error("Failed to fetch"),
        pending: false,
      }),
    ).toContain("当前本地 sidecar 不可用");
    expect(
      launcherSidecarGateMessage("en", {
        error: new Error("The desktop sidecar did not respond in time for /health."),
        pending: false,
      }),
    ).toContain("The local sidecar is unavailable");
  });

  it("falls back to the original error message when it is already specific", () => {
    expect(
      launcherSidecarGateMessage("en", {
        error: new Error("Workspace root does not exist."),
        pending: false,
      }),
    ).toBe("Workspace root does not exist.");
  });
});
