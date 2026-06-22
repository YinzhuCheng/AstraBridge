import { describe, expect, it } from "vitest";

import { modelAuthorityState } from "./modelAuthorityNotice";

describe("model authority notice", () => {
  it("reports Tier A models as full agent lanes without blocking send", () => {
    const state = modelAuthorityState({
      authority_tier: "A",
      authority_reason: "Model can participate in read/write/tool workflows with guarded tool execution.",
      parallel_tool_call_status: "verified",
    });

    expect(state).toMatchObject({
      tier: "A",
      label: "Tier A agent",
      tone: "ok",
      sendBlocked: false,
    });
    expect(state?.notices).toEqual([]);
  });

  it("adds propose-first and serial tool warnings for Tier B models", () => {
    const state = modelAuthorityState({
      authority_tier: "B",
      authority_reason: "Model should stay in review/propose mode unless validation or approval promotes the action.",
      parallel_tool_call_status: "serial_only",
    });

    expect(state).toMatchObject({
      tier: "B",
      label: "Tier B propose-first",
      tone: "warning",
      sendBlocked: false,
    });
    expect(state?.notices[0]).toContain("review/propose mode");
    expect(state?.notices[1]).toContain("Parallel tool calls are disabled");
  });

  it("blocks send for Tier D models", () => {
    const state = modelAuthorityState({
      authority_tier: "D",
      authority_reason: "Model is not exposed as a Codex agent model.",
      parallel_tool_call_status: "disabled",
    });

    expect(state).toMatchObject({
      tier: "D",
      label: "Tier D agent disabled",
      tone: "danger",
      sendBlocked: true,
    });
    expect(state?.notices).toEqual(["Model is not exposed as a Codex agent model."]);
  });
});
