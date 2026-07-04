import type { CursorEnhancementPreference } from "../../types";

export type CursorRenderQuality = "full" | "economy" | "minimal" | "hidden";

export type CursorEnvironmentState = {
  hasFinePointer: boolean;
  prefersReducedMotion: boolean;
  saveData?: boolean;
  hardwareConcurrency?: number | null;
  deviceMemory?: number | null;
};

export function normalizeCursorEnhancementPreference(value: unknown): CursorEnhancementPreference {
  return value === "off" ? "off" : "auto";
}

export function resolveCursorRenderQuality(
  preference: CursorEnhancementPreference,
  environment: CursorEnvironmentState,
): CursorRenderQuality {
  if (preference === "off" || !environment.hasFinePointer) {
    return "hidden";
  }
  if (environment.prefersReducedMotion) {
    return "minimal";
  }
  if (environment.saveData) {
    return "economy";
  }
  if (typeof environment.deviceMemory === "number" && environment.deviceMemory > 0 && environment.deviceMemory <= 4) {
    return "economy";
  }
  if (typeof environment.hardwareConcurrency === "number" && environment.hardwareConcurrency > 0 && environment.hardwareConcurrency <= 4) {
    return "economy";
  }
  return "full";
}
