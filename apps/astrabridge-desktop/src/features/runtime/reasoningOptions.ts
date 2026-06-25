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

function providerModelDefaults(provider: RouterProvider | null | undefined): Partial<RouterModelEntry> {
  return provider?.model_defaults && typeof provider.model_defaults === "object" ? provider.model_defaults : {};
}

function providerLevels(provider: RouterProvider | null | undefined): string[] {
  const modelDefaults = providerModelDefaults(provider);
  return normalizedList(modelDefaults.supported_reasoning_levels ?? provider?.supported_reasoning_levels);
}

function providerDefaultReasoningLevel(provider: RouterProvider | null | undefined): string {
  const modelDefaults = providerModelDefaults(provider);
  return String(modelDefaults.default_reasoning_level ?? provider?.default_reasoning_level ?? "").trim();
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
  const modelDefaults = providerModelDefaults(provider);
  return {
    temperature_default: modelDefaults.temperature_default ?? provider?.temperature_default ?? 0,
    temperature_ui_min: modelDefaults.temperature_ui_min ?? provider?.temperature_ui_min ?? 0,
    temperature_ui_max: modelDefaults.temperature_ui_max ?? provider?.temperature_ui_max ?? 2,
    provider_temperature_min: modelDefaults.provider_temperature_min ?? provider?.provider_temperature_min ?? 0,
    provider_temperature_max: modelDefaults.provider_temperature_max ?? provider?.provider_temperature_max ?? 2,
    temperature_adapter_policy: modelDefaults.temperature_adapter_policy ?? provider?.temperature_adapter_policy ?? "pass_through_0_2",
  };
}

function providerCapabilityRecord(provider: RouterProvider | null | undefined): Record<string, unknown> {
  const capabilities = provider?.capabilities;
  return capabilities && typeof capabilities === "object" ? capabilities : {};
}

function providerInputModalities(provider: RouterProvider | null | undefined): string[] {
  const modelDefaults = providerModelDefaults(provider);
  const topLevel = normalizedList(modelDefaults.input_modalities ?? provider?.input_modalities);
  if (topLevel.length > 0) return topLevel;
  const visionSummary = provider?.capability_summary?.["vision.analyze"];
  const summaryModalities = normalizedList(visionSummary?.input_modalities);
  if (summaryModalities.length > 0) return summaryModalities;
  const capabilityModalities = normalizedList(providerCapabilityRecord(provider).input_modalities);
  if (capabilityModalities.length > 0) return capabilityModalities;
  if (providerCapabilityRecord(provider).supports_vision === true) return ["text", "image"];
  return ["text"];
}

function builtinToolDefaults(provider: RouterProvider | null | undefined) {
  const modelDefaults = providerModelDefaults(provider);
  return modelDefaults.codex_builtin_tools ?? provider?.codex_builtin_tools ?? {};
}

function plannerSupportDefaults(provider: RouterProvider | null | undefined) {
  const modelDefaults = providerModelDefaults(provider);
  return modelDefaults.planner_support ?? provider?.planner_support ?? {};
}

function goalSupportDefaults(provider: RouterProvider | null | undefined) {
  const modelDefaults = providerModelDefaults(provider);
  return modelDefaults.goal_support ?? provider?.goal_support ?? { thread_goal: "app_server_native" };
}

function contextCompactionDefaults(provider: RouterProvider | null | undefined) {
  const modelDefaults = providerModelDefaults(provider);
  return modelDefaults.context_compaction_support ?? provider?.context_compaction_support ?? {
    manual_compact: "app_server_native",
    auto_compact: "configured_unverified",
    structured_summary_quality: "untested",
  };
}

export function providerModelDraftDefaults(provider: RouterProvider | null | undefined): Partial<RouterModelEntry> {
  const modelDefaults = providerModelDefaults(provider);
  const capabilityRecord = providerCapabilityRecord(provider);
  const inputModalities = providerInputModalities(provider);
  const advertisedContextWindow =
    Number(modelDefaults.advertised_context_window ?? 0) > 0
      ? Number(modelDefaults.advertised_context_window)
      : Number(capabilityRecord.max_context_tokens ?? 0) > 0
        ? Number(capabilityRecord.max_context_tokens)
        : 1_000_000;
  const supportsParallelToolCalls =
    typeof modelDefaults.supports_parallel_tool_calls === "boolean"
      ? modelDefaults.supports_parallel_tool_calls
      : capabilityRecord.supports_parallel_tool_calls === true;
  return {
    ...modelDefaults,
    advertised_context_window: advertisedContextWindow,
    ui_context_hint_only: modelDefaults.ui_context_hint_only ?? true,
    adapter_profile: modelDefaults.adapter_profile ?? "default",
    codex_agent_enabled: modelDefaults.codex_agent_enabled ?? true,
    input_modalities: inputModalities,
    supported_reasoning_levels: providerReasoningOptions(provider, null),
    default_reasoning_level: preferredProviderReasoningEffort(provider, null),
    reasoning_display_policy: modelDefaults.reasoning_display_policy ?? "collapsed_3_lines",
    supports_parallel_tool_calls: supportsParallelToolCalls,
    supports_search_tool: modelDefaults.supports_search_tool ?? provider?.supports_search_tool ?? false,
    supports_mcp_tools: modelDefaults.supports_mcp_tools ?? provider?.supports_mcp_tools ?? false,
    mcp_tool_call_policy: modelDefaults.mcp_tool_call_policy ?? provider?.mcp_tool_call_policy ?? "unsupported",
    mcp_verified_servers: modelDefaults.mcp_verified_servers ?? provider?.mcp_verified_servers ?? [],
    mcp_smoke_status: modelDefaults.mcp_smoke_status ?? provider?.mcp_smoke_status ?? "untested",
    mcp_tool_argument_validation: modelDefaults.mcp_tool_argument_validation ?? provider?.mcp_tool_argument_validation ?? "unsupported",
    codex_builtin_tools: builtinToolDefaults(provider),
    planner_support: plannerSupportDefaults(provider),
    goal_support: goalSupportDefaults(provider),
    context_compaction_support: contextCompactionDefaults(provider),
    modality_limits: modelDefaults.modality_limits ?? {
      text: true,
      image_input: inputModalities.includes("image"),
      file_mentions: true,
      image_generation: false,
    },
    ui_warnings: modelDefaults.ui_warnings ?? [],
    apply_patch_tool_type: modelDefaults.apply_patch_tool_type ?? provider?.apply_patch_tool_type ?? null,
    web_search_tool_type: modelDefaults.web_search_tool_type ?? provider?.web_search_tool_type ?? "text",
    supports_image_detail_original:
      modelDefaults.supports_image_detail_original ?? (provider?.capabilities && capabilityRecord.supports_image_detail_original === true),
    source_status: modelDefaults.source_status ?? "manual",
    source_urls: modelDefaults.source_urls ?? [],
    ...providerTemperatureDefaults(provider),
  };
}
