import { describe, expect, it } from "vitest";

import { normalizeCursorEnhancementPreference, resolveCursorRenderQuality } from "./cursorEnhancement";

describe("cursorEnhancement", () => {
  it("normalizes unknown preferences back to auto", () => {
    expect(normalizeCursorEnhancementPreference("off")).toBe("off");
    expect(normalizeCursorEnhancementPreference("sparkles")).toBe("auto");
    expect(normalizeCursorEnhancementPreference(null)).toBe("auto");
  });

  it("hides the overlay when disabled or when no fine pointer is present", () => {
    expect(
      resolveCursorRenderQuality("off", {
        hasFinePointer: true,
        prefersReducedMotion: false,
      }),
    ).toBe("hidden");
    expect(
      resolveCursorRenderQuality("auto", {
        hasFinePointer: false,
        prefersReducedMotion: false,
      }),
    ).toBe("hidden");
  });

  it("downgrades to minimal on reduced motion and economy on low-power hints", () => {
    expect(
      resolveCursorRenderQuality("auto", {
        hasFinePointer: true,
        prefersReducedMotion: true,
      }),
    ).toBe("minimal");
    expect(
      resolveCursorRenderQuality("auto", {
        hasFinePointer: true,
        prefersReducedMotion: false,
        saveData: true,
      }),
    ).toBe("economy");
    expect(
      resolveCursorRenderQuality("auto", {
        hasFinePointer: true,
        prefersReducedMotion: false,
        hardwareConcurrency: 4,
      }),
    ).toBe("economy");
  });

  it("keeps the full overlay when no downgrade signal is active", () => {
    expect(
      resolveCursorRenderQuality("auto", {
        hasFinePointer: true,
        prefersReducedMotion: false,
        hardwareConcurrency: 8,
        deviceMemory: 8,
      }),
    ).toBe("full");
  });
});
