import { describe, expect, it } from "vitest";

import type { Profile, RouterModelEntry } from "../../types";
import { composerReasoningOptions, preferredReasoningEffort } from "./reasoningOptions";

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
});
