import { describe, expect, it } from "vitest";

import type { Profile, RouterModelEntry, RuntimeFailureAction } from "../../types";
import { resolveRecoveryComposerPatch, resolveRecoveryProfile } from "./runtimeRecoveryPlan";

const profiles: Profile[] = [
  {
    profile_id: "deepseek-default",
    label: "DeepSeek Default",
    type: "custom_provider",
    provider_id: "deepseek",
    base_url: "https://api.deepseek.com",
    model: "deepseek-v4-pro",
    reasoning_effort: "xhigh",
    wire_api: "chat",
    env_key: "DEEPSEEK_API_KEY",
    auth_mode: "env_ref",
    proxy_mode: "direct",
    proxy_url: "",
    supported_reasoning_levels: ["high", "xhigh"],
    default_reasoning_level: "xhigh",
  },
  {
    profile_id: "qwen-default",
    label: "Qwen Default",
    type: "custom_provider",
    provider_id: "qwen",
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen3.7-plus",
    reasoning_effort: "high",
    wire_api: "responses",
    env_key: "DASHSCOPE_API_KEY",
    auth_mode: "env_ref",
    proxy_mode: "direct",
    proxy_url: "",
    supported_reasoning_levels: ["low", "medium", "high"],
    default_reasoning_level: "high",
  },
  {
    profile_id: "qwen-mirror",
    label: "Qwen Mirror",
    type: "custom_provider",
    provider_id: "qwen",
    base_url: "https://mirror.example/v1",
    model: "qwen3.6-flash",
    reasoning_effort: "medium",
    wire_api: "responses",
    env_key: "MIRROR_QWEN_KEY",
    auth_mode: "env_ref",
    proxy_mode: "direct",
    proxy_url: "",
    supported_reasoning_levels: ["low", "medium"],
    default_reasoning_level: "medium",
  },
];

const models: RouterModelEntry[] = [
  {
    id: "deepseek/deepseek-v4-pro",
    provider: "deepseek",
    native_model: "deepseek-v4-pro",
    display_name: "DeepSeek V4 Pro",
    enabled: true,
    advertised_context_window: 1000000,
    ui_context_hint_only: true,
    adapter_profile: "default",
    supported_reasoning_levels: ["high", "xhigh"],
    default_reasoning_level: "xhigh",
  },
  {
    id: "deepseek/deepseek-v4-flash",
    provider: "deepseek",
    native_model: "deepseek-v4-flash",
    display_name: "DeepSeek V4 Flash",
    enabled: true,
    advertised_context_window: 512000,
    ui_context_hint_only: true,
    adapter_profile: "default",
    supported_reasoning_levels: ["high", "xhigh"],
    default_reasoning_level: "high",
  },
  {
    id: "qwen/qwen3.7-max-2026-06-08",
    provider: "qwen",
    native_model: "qwen3.7-max-2026-06-08",
    display_name: "Qwen 3.7 Max",
    enabled: true,
    advertised_context_window: 1000000,
    ui_context_hint_only: true,
    adapter_profile: "default",
    supported_reasoning_levels: ["low", "medium", "high"],
    default_reasoning_level: "high",
    default_for_provider: true,
  },
  {
    id: "qwen/qwen3.6-flash",
    provider: "qwen",
    native_model: "qwen3.6-flash",
    display_name: "Qwen 3.6 Flash",
    enabled: true,
    advertised_context_window: 512000,
    ui_context_hint_only: true,
    adapter_profile: "default",
    supported_reasoning_levels: ["low", "medium"],
    default_reasoning_level: "medium",
  },
];

describe("runtime recovery plan", () => {
  it("prefers the transition-target profile over a generic provider match", () => {
    const profile = resolveRecoveryProfile(
      {
        provider_id: "qwen",
        model_id: "qwen/qwen3.6-flash",
        base_url: "https://mirror.example/v1",
        env_key: "MIRROR_QWEN_KEY",
      },
      profiles,
      profiles[0],
    );

    expect(profile?.profile_id).toBe("qwen-mirror");
  });

  it("uses the transition target to hand off to the intended provider and model", () => {
    const action: RuntimeFailureAction = {
      action: "handoff_provider",
      label: "Switch Provider",
      reason: "Move to another provider lane.",
      transition: {
        action: "handoff_provider",
        reason: "Move to qwen",
        reasoning_effort: "medium",
        target: {
          provider_id: "qwen",
          model_id: "qwen/qwen3.6-flash",
          base_url: "https://mirror.example/v1",
          env_key: "MIRROR_QWEN_KEY",
        },
      },
    };

    const patch = resolveRecoveryComposerPatch({
      action,
      current: { profile_id: "deepseek-default", model: "deepseek-v4-pro", reasoning_effort: "xhigh" },
      activeProfile: profiles[0],
      profiles,
      models,
    });

    expect(patch).toEqual({
      profile_id: "qwen-mirror",
      model: "qwen3.6-flash",
      reasoning_effort: "medium",
    });
  });

  it("applies switch_model on the current provider using the transition model target", () => {
    const action: RuntimeFailureAction = {
      action: "switch_model",
      label: "Try Fallback Model",
      reason: "Use a smaller model.",
      target: "deepseek-v4-flash",
      transition: {
        action: "switch_model",
        reason: "fallback",
        target: {
          provider_id: "deepseek",
          model_id: "deepseek/deepseek-v4-flash",
        },
      },
    };

    const patch = resolveRecoveryComposerPatch({
      action,
      current: { profile_id: "deepseek-default", model: "deepseek-v4-pro", reasoning_effort: "xhigh" },
      activeProfile: profiles[0],
      profiles,
      models,
    });

    expect(patch).toEqual({
      model: "deepseek-v4-flash",
    });
  });

  it("uses the downgraded reasoning level from the recovery action when available", () => {
    const action: RuntimeFailureAction = {
      action: "downgrade_reasoning",
      label: "Lower Reasoning",
      reason: "Reduce context pressure.",
      target: "high",
      transition: {
        action: "downgrade_reasoning",
        reason: "lower effort",
        reasoning_effort: "high",
        target: {
          provider_id: "deepseek",
          model_id: "deepseek/deepseek-v4-pro",
        },
      },
    };

    const patch = resolveRecoveryComposerPatch({
      action,
      current: { profile_id: "deepseek-default", model: "deepseek-v4-pro", reasoning_effort: "xhigh" },
      activeProfile: profiles[0],
      profiles,
      models,
    });

    expect(patch).toEqual({
      reasoning_effort: "high",
    });
  });

  it("fails closed when the transition targets a provider with no matching local profile", () => {
    const action: RuntimeFailureAction = {
      action: "handoff_provider",
      label: "Switch Provider",
      reason: "Move to another provider lane.",
      transition: {
        action: "handoff_provider",
        reason: "move to glm",
        target: {
          provider_id: "glm",
          model_id: "glm/glm-5.2",
          base_url: "https://open.bigmodel.cn/api/paas/v4",
          env_key: "GLM_API_KEY",
        },
      },
    };

    const patch = resolveRecoveryComposerPatch({
      action,
      current: { profile_id: "deepseek-default", model: "deepseek-v4-pro", reasoning_effort: "xhigh" },
      activeProfile: profiles[0],
      profiles,
      models,
    });

    expect(patch).toBeNull();
  });
});
