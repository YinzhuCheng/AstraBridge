import type { LlmManagerSession, RouterModelEntry } from "../../types";

export type ComposerCatalogModel = RouterModelEntry & {
  verified?: boolean;
  health?: Record<string, unknown>;
};

function modelKey(model: Pick<RouterModelEntry, "provider" | "native_model" | "id">) {
  const provider = String(model.provider || "").trim();
  const nativeModel = String(model.native_model || "").trim();
  if (provider && nativeModel) return `${provider}:${nativeModel}`;
  return String(model.id || "").trim();
}

export function mergeComposerCatalogModels(
  managerMode: LlmManagerSession["mode"] | null | undefined,
  managedModels: ComposerCatalogModel[],
  routerModels: ComposerCatalogModel[],
): ComposerCatalogModel[] {
  if (managerMode !== "managed_user" || managedModels.length === 0) return [...routerModels];
  const merged: ComposerCatalogModel[] = [];
  const seen = new Set<string>();
  for (const model of managedModels) {
    const key = modelKey(model);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    merged.push(model);
  }
  for (const model of routerModels) {
    const key = modelKey(model);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    merged.push(model);
  }
  return merged;
}
