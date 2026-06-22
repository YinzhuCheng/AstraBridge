import { describe, expect, it } from "vitest";

import type { Profile, RouterModelEntry, RouterProvider } from "../../types";
import { composerReasoningOptions, preferredProviderReasoningEffort, preferredReasoningEffort, providerReasoningOptions, providerTemperatureDefaults } from "./reasoningOptions";

describe("reasoning options", () => {
  it("prefers model metadata over provider heuristics", () => {
    const profile = {
      profile_id: "deepseek-default",
      label: "DeepSeek",
      type: "custom_provider",
      provider_id: "deepseek",
      model: "deepseek-v4-pro",
      reasoning_effort: "xhigh",
      wire_api: "chat",
      env_key: "DEEPSEEK_API_KEY",
      auth_mode: "env_ref",
      proxy_mode: "direct",
      proxy_url: "",
      supported_reasoning_levels: ["high", "xhigh", "max"],
      default_reasoning_level: "xhigh",
    } satisfies Profile;
    const model = {
      id: "deepseek/deepseek-v4-flash",
      provider: "deepseek",
      native_model: "deepseek-v4-flash",
      display_name: "DeepSeek V4 Flash",
      enabled: true,
      advertised_context_window: 1_000_000,
      ui_context_hint_only: true,
      adapter_profile: "default",
      supported_reasoning_levels: ["off", "high"],
      default_reasoning_level: "high",
    } satisfies RouterModelEntry;

    expect(composerReasoningOptions(model, profile, null)).toEqual(["off", "high", "xhigh"]);
    expect(preferredReasoningEffort(model, profile, null)).toBe("high");
  });

  it("falls back to provider profile defaults when model metadata is missing", () => {
    const profile = {
      profile_id: "qwen-default",
      label: "Qwen",
      type: "custom_provider",
      provider_id: "qwen",
      model: "qwen3.7-plus",
      reasoning_effort: "high",
      wire_api: "responses",
      env_key: "DASHSCOPE_API_KEY",
      auth_mode: "env_ref",
      proxy_mode: "direct",
      proxy_url: "",
      supported_reasoning_levels: ["low", "medium", "high", "xhigh"],
      default_reasoning_level: "high",
    } satisfies Profile;

    expect(composerReasoningOptions(null, profile, null)).toEqual(["low", "medium", "high", "xhigh"]);
    expect(preferredReasoningEffort(null, profile, null)).toBe("high");
  });

  it("uses provider metadata for provider-only reasoning defaults", () => {
    const provider = {
      id: "deepseek",
      display_name: "DeepSeek",
      enabled: true,
      adapter_type: "chat",
      base_url: "https://api.deepseek.com",
      default_model: "deepseek-v4-pro",
      request_timeout_ms: 300000,
      stream_idle_timeout_ms: 300000,
      env_key: "DEEPSEEK_API_KEY",
      auth_mode: "env_ref",
      proxy_mode: "direct",
      proxy_url: "",
      supported_reasoning_levels: ["high", "xhigh", "max"],
      default_reasoning_level: "xhigh",
    } satisfies RouterProvider;

    expect(providerReasoningOptions(provider, null)).toEqual(["high", "xhigh", "max"]);
    expect(preferredProviderReasoningEffort(provider, null)).toBe("xhigh");
  });

  it("uses provider metadata for temperature defaults", () => {
    const provider = {
      id: "kimi",
      display_name: "Kimi",
      enabled: true,
      adapter_type: "chat",
      base_url: "https://api.moonshot.cn/v1",
      default_model: "kimi-k2.6",
      request_timeout_ms: 300000,
      stream_idle_timeout_ms: 300000,
      env_key: "KIMI_API_KEY",
      auth_mode: "env_ref",
      proxy_mode: "direct",
      proxy_url: "",
      temperature_default: 1,
      temperature_ui_min: 1,
      temperature_ui_max: 1,
      provider_temperature_min: 1,
      provider_temperature_max: 1,
      temperature_adapter_policy: "kimi_only_temperature_1",
    } satisfies RouterProvider;

    expect(providerTemperatureDefaults(provider)).toEqual({
      temperature_default: 1,
      temperature_ui_min: 1,
      temperature_ui_max: 1,
      provider_temperature_min: 1,
      provider_temperature_max: 1,
      temperature_adapter_policy: "kimi_only_temperature_1",
    });
  });
});
