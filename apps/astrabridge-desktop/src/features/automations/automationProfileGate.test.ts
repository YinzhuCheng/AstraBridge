import { describe, expect, it } from "vitest";

import type { Profile, RouterModelEntry } from "../../types";
import { resolveStandaloneAutomationProfileGate } from "./automationProfileGate";

const baseProfile: Profile = {
  profile_id: "qwen-default",
  label: "Qwen / DashScope",
  type: "custom_provider",
  provider_id: "qwen",
  model: "qwen3.7-plus",
  reasoning_effort: "high",
  wire_api: "responses",
  env_key: "DASHSCOPE_API_KEY",
  auth_mode: "env_ref",
  proxy_mode: "direct",
  proxy_url: "",
};

const baseModel: RouterModelEntry = {
  id: "qwen/qwen3.7-plus",
  provider: "qwen",
  native_model: "qwen3.7-plus",
  display_name: "Qwen 3.7 Plus",
  enabled: true,
  advertised_context_window: 1_000_000,
  ui_context_hint_only: false,
  adapter_profile: "qwen-default",
};

describe("resolveStandaloneAutomationProfileGate", () => {
  it("blocks models whose authority tier is not verified for tool workflows", () => {
    const gate = resolveStandaloneAutomationProfileGate(
      baseProfile,
      [
        {
          ...baseModel,
          authority_tier: "C",
          authority_reason: "Model has no verified structured tool-calling surface.",
        },
      ],
      "read-only",
    );
    expect(gate.status).toBe("blocked");
    expect(gate.code).toBe("authority_unverified_for_tools");
  });

  it("allows tier-B models only for read-only standalone runs", () => {
    const readOnlyGate = resolveStandaloneAutomationProfileGate(
      baseProfile,
      [
        {
          ...baseModel,
          authority_tier: "B",
          authority_reason: "Model should stay in review/propose mode unless validation promotes the action.",
        },
      ],
      "read-only",
    );
    expect(readOnlyGate.status).toBe("warn");
    expect(readOnlyGate.code).toBe("read_only_review_mode");

    const writeGate = resolveStandaloneAutomationProfileGate(
      baseProfile,
      [
        {
          ...baseModel,
          authority_tier: "B",
          authority_reason: "Model should stay in review/propose mode unless validation promotes the action.",
        },
      ],
      "workspace-write",
    );
    expect(writeGate.status).toBe("blocked");
    expect(writeGate.code).toBe("authority_requires_read_only");
  });

  it("blocks models whose command execution validation already failed", () => {
    const gate = resolveStandaloneAutomationProfileGate(
      baseProfile,
      [
        {
          ...baseModel,
          authority_tier: "A",
          command_execution_status: "partial_no_command_execution",
          command_execution_note: "Runtime turn completed but no commandExecution event was observed.",
        },
      ],
      "read-only",
    );
    expect(gate.status).toBe("blocked");
    expect(gate.code).toBe("command_execution_unverified");
  });
});
