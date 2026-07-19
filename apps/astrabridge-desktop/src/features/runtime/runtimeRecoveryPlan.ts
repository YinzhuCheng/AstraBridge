import type { Profile, RouterModelEntry, RuntimeFailureAction, RuntimeFailureTransitionTarget } from "../../types";
import { composerReasoningOptions, preferredReasoningEffort } from "./reasoningOptions";

export type ComposerRecoverySettings = {
  profile_id: string;
  model: string;
  reasoning_effort: string;
};

type RecoveryContext = {
  action: RuntimeFailureAction;
  current: ComposerRecoverySettings;
  activeProfile: Profile | null | undefined;
  profiles: Profile[];
  models: RouterModelEntry[];
};

function nativeModelId(value: string | null | undefined): string {
  const text = String(value ?? "").trim();
  if (!text) return "";
  return text.includes("/") ? text.split("/", 2)[1] : text;
}

function transitionTargetScore(target: RuntimeFailureTransitionTarget | undefined, profile: Profile, activeProfile: Profile | null | undefined): number {
  if (!target) {
    return activeProfile?.profile_id === profile.profile_id ? 1 : 0;
  }
  const targetProviderId = String(target.provider_id ?? "").trim();
  if (targetProviderId && profile.provider_id !== targetProviderId) {
    return Number.NEGATIVE_INFINITY;
  }
  let score = targetProviderId ? 100 : 0;
  const targetRuntimeBackend = String(target.runtime_backend ?? "").trim();
  if (targetRuntimeBackend) {
    const profileBackend = String(profile.execution_backend ?? "").trim();
    if (profileBackend && profileBackend !== targetRuntimeBackend) {
      return Number.NEGATIVE_INFINITY;
    }
    if (profileBackend === targetRuntimeBackend) score += 24;
  }
  if (target.base_url && profile.base_url === target.base_url) score += 20;
  if (target.env_key && profile.env_key === target.env_key) score += 16;
  const targetModel = nativeModelId(target.model_id);
  if (targetModel && profile.model === targetModel) score += 8;
  if (activeProfile?.profile_id === profile.profile_id) score += 4;
  if (profile.profile_id.endsWith("-default")) score += 1;
  return score;
}

export function resolveRecoveryProfile(
  target: RuntimeFailureTransitionTarget | undefined,
  profiles: Profile[],
  activeProfile: Profile | null | undefined,
): Profile | null {
  let best: Profile | null = null;
  let bestScore = Number.NEGATIVE_INFINITY;
  for (const profile of profiles) {
    const score = transitionTargetScore(target, profile, activeProfile);
    if (score > bestScore) {
      best = profile;
      bestScore = score;
    }
  }
  return bestScore > Number.NEGATIVE_INFINITY ? best : null;
}

function resolveRecoveryModelEntry(providerId: string, nativeModel: string, models: RouterModelEntry[]): RouterModelEntry | null {
  if (!providerId || !nativeModel) return null;
  return models.find((model) => model.provider === providerId && (model.native_model === nativeModel || model.id === `${providerId}/${nativeModel}`)) ?? null;
}

function defaultRouteVerified(model: RouterModelEntry): boolean {
  if (model.default_route_verified !== undefined) return Boolean(model.default_route_verified);
  const authorityTier = String(model.authority_tier ?? "").trim().toUpperCase();
  if (authorityTier !== "A") return false;
  const commandExecutionStatus = String(model.command_execution_status ?? "unknown").trim().toLowerCase();
  if (commandExecutionStatus === "partial_no_command_execution" || commandExecutionStatus === "completed_without_command_execution") {
    return false;
  }
  if (model.supports_mcp_tools) {
    const mcpPolicy = String(model.mcp_tool_call_policy ?? "unsupported").trim().toLowerCase();
    const mcpSmokeStatus = String(model.mcp_smoke_status ?? "untested").trim().toLowerCase();
    if (mcpPolicy !== "verified") return false;
    if (!(mcpSmokeStatus === "verified" || mcpSmokeStatus.startsWith("pass"))) return false;
  }
  return true;
}

function preferredProviderModel(providerId: string, models: RouterModelEntry[], profile: Profile | null | undefined, currentModel: string): string {
  const providerModels = models
    .filter((model) => model.provider === providerId && model.enabled !== false && defaultRouteVerified(model))
    .sort((left, right) => {
      const leftDeprecated = Number(Boolean(left.deprecated));
      const rightDeprecated = Number(Boolean(right.deprecated));
      if (leftDeprecated !== rightDeprecated) return leftDeprecated - rightDeprecated;
      const leftDefault = Number(Boolean(left.default_for_provider));
      const rightDefault = Number(Boolean(right.default_for_provider));
      if (leftDefault !== rightDefault) return rightDefault - leftDefault;
      const leftRecommended = Number(Boolean(left.recommended));
      const rightRecommended = Number(Boolean(right.recommended));
      if (leftRecommended !== rightRecommended) return rightRecommended - leftRecommended;
      return String(left.native_model ?? left.id ?? "").localeCompare(String(right.native_model ?? right.id ?? ""));
    });
  const exactDefault = providerModels[0] ?? null;
  if (exactDefault?.native_model) return exactDefault.native_model;
  const profileModelEntry = resolveRecoveryModelEntry(providerId, String(profile?.model ?? "").trim(), models);
  if (profileModelEntry && defaultRouteVerified(profileModelEntry)) {
    return String(profileModelEntry.native_model ?? profileModelEntry.id ?? "").trim();
  }
  const currentModelEntry = resolveRecoveryModelEntry(providerId, currentModel, models);
  if (currentModelEntry && defaultRouteVerified(currentModelEntry)) {
    return String(currentModelEntry.native_model ?? currentModelEntry.id ?? "").trim();
  }
  return "";
}

export function resolveRecoveryComposerPatch(context: RecoveryContext): Partial<ComposerRecoverySettings> | null {
  const { action, current, activeProfile, profiles, models } = context;
  if (!["switch_model", "downgrade_reasoning", "handoff_provider"].includes(action.action)) {
    return null;
  }
  const transition = action.transition ?? null;
  const target = transition?.target;
  const resolvedProfile = resolveRecoveryProfile(target ?? undefined, profiles, activeProfile) ?? activeProfile ?? null;
  const nextProviderId = String(target?.provider_id ?? resolvedProfile?.provider_id ?? activeProfile?.provider_id ?? "").trim();
  if (nextProviderId && (!resolvedProfile || resolvedProfile.provider_id !== nextProviderId)) {
    return null;
  }
  const nextModel =
    nativeModelId(target?.model_id)
    || (action.action === "switch_model" ? nativeModelId(action.target) : "")
    || (action.action === "handoff_provider" ? preferredProviderModel(nextProviderId, models, resolvedProfile, current.model) : current.model);
  if (action.action === "handoff_provider" && !nextModel) {
    return null;
  }
  const nextModelEntry = resolveRecoveryModelEntry(nextProviderId, nextModel, models);
  const reasoningOptions = composerReasoningOptions(nextModelEntry, resolvedProfile, current.reasoning_effort);
  const requestedReasoning =
    (action.action === "downgrade_reasoning" ? String(action.target ?? "").trim() : "")
    || String(transition?.reasoning_effort ?? "").trim()
    || String(resolvedProfile?.reasoning_effort ?? "").trim();
  const nextReasoning = requestedReasoning && reasoningOptions.includes(requestedReasoning)
    ? requestedReasoning
    : preferredReasoningEffort(nextModelEntry, resolvedProfile, current.reasoning_effort);
  const patch: Partial<ComposerRecoverySettings> = {};
  if (resolvedProfile?.profile_id && resolvedProfile.profile_id !== current.profile_id) {
    patch.profile_id = resolvedProfile.profile_id;
  }
  if (nextModel && nextModel !== current.model) {
    patch.model = nextModel;
  }
  if (nextReasoning && nextReasoning !== current.reasoning_effort) {
    patch.reasoning_effort = nextReasoning;
  }
  return Object.keys(patch).length > 0 ? patch : {};
}
