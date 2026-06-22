import type { Profile, RouterModelEntry, RouterProvider } from "../../types";

function normalizedList(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  return values.map((value) => String(value ?? "").trim()).filter(Boolean);
}

function appendUnique(target: string[], values: Array<string | null | undefined>) {
  for (const value of values) {
    const normalized = String(value ?? "").trim();
    if (!normalized || target.includes(normalized)) continue;
    target.push(normalized);
  }
}

function providerLevels(provider: RouterProvider | null | undefined): string[] {
  return normalizedList(provider?.supported_reasoning_levels);
}

function providerDefaultReasoningLevel(provider: RouterProvider | null | undefined): string {
  return String(provider?.default_reasoning_level ?? "").trim();
}

export function composerReasoningOptions(
  modelEntry: RouterModelEntry | null | undefined,
  profile: Profile | null | undefined,
  currentReasoningEffort?: string | null,
): string[] {
  const options = normalizedList(modelEntry?.supported_reasoning_levels);
  if (options.length === 0) {
    appendUnique(options, normalizedList(profile?.supported_reasoning_levels));
  }
  if (options.length === 0) {
    appendUnique(options, [profile?.default_reasoning_level, profile?.reasoning_effort, "high"]);
  }
  appendUnique(options, [modelEntry?.default_reasoning_level, profile?.default_reasoning_level, profile?.reasoning_effort, currentReasoningEffort]);
  return options;
}

export function providerReasoningOptions(
  provider: RouterProvider | null | undefined,
  currentReasoningEffort?: string | null,
): string[] {
  const options = providerLevels(provider);
  if (options.length === 0) {
    appendUnique(options, [providerDefaultReasoningLevel(provider), currentReasoningEffort, "high"]);
  } else {
    appendUnique(options, [providerDefaultReasoningLevel(provider), currentReasoningEffort]);
  }
  return options;
}

export function preferredReasoningEffort(
  modelEntry: RouterModelEntry | null | undefined,
  profile: Profile | null | undefined,
  currentReasoningEffort?: string | null,
): string {
  const options = composerReasoningOptions(modelEntry, profile, currentReasoningEffort);
  const preferred = [
    String(modelEntry?.default_reasoning_level ?? "").trim(),
    String(profile?.default_reasoning_level ?? "").trim(),
    String(profile?.reasoning_effort ?? "").trim(),
  ].find((value) => value && options.includes(value));
  return preferred || options[0] || "high";
}

export function preferredProviderReasoningEffort(
  provider: RouterProvider | null | undefined,
  currentReasoningEffort?: string | null,
): string {
  const options = providerReasoningOptions(provider, currentReasoningEffort);
  const preferred = [
    providerDefaultReasoningLevel(provider),
    String(currentReasoningEffort ?? "").trim(),
  ].find((value) => value && options.includes(value));
  return preferred || options[0] || "high";
}

export function providerTemperatureDefaults(provider: RouterProvider | null | undefined) {
  return {
    temperature_default: provider?.temperature_default ?? 0,
    temperature_ui_min: provider?.temperature_ui_min ?? 0,
    temperature_ui_max: provider?.temperature_ui_max ?? 2,
    provider_temperature_min: provider?.provider_temperature_min ?? 0,
    provider_temperature_max: provider?.provider_temperature_max ?? 2,
    temperature_adapter_policy: provider?.temperature_adapter_policy ?? "pass_through_0_2",
  };
}
