import type { Profile, RouterModelEntry } from "../../types";

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
