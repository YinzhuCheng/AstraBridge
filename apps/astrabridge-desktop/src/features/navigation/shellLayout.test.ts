import { describe, expect, it } from "vitest";

import { COMPACT_SHELL_BREAKPOINT, isCompactShellViewport, resolveSidebarVisible } from "./shellLayout";

describe("shell layout policy", () => {
  it("keeps the compact breakpoint explicit", () => {
    expect(isCompactShellViewport(COMPACT_SHELL_BREAKPOINT)).toBe(true);
    expect(isCompactShellViewport(COMPACT_SHELL_BREAKPOINT + 1)).toBe(false);
  });

  it("uses the drawer state on compact viewports and preserves the desktop preference otherwise", () => {
    expect(resolveSidebarVisible({ compactViewport: true, compactSidebarOpen: false, desktopSidebarOpen: true })).toBe(false);
    expect(resolveSidebarVisible({ compactViewport: true, compactSidebarOpen: true, desktopSidebarOpen: false })).toBe(true);
    expect(resolveSidebarVisible({ compactViewport: false, compactSidebarOpen: false, desktopSidebarOpen: true })).toBe(true);
  });
});
