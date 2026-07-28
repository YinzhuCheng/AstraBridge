import { describe, expect, it } from "vitest";

import { modelRouteAdmissionState, routeAdmissionCopy } from "./routeAdmissionPresentation";

describe("route admission presentation", () => {
  it("keeps a documented model selectable while requiring review-mode confirmation", () => {
    const state = modelRouteAdmissionState({
      execution_route_status: "review_only",
      execution_route_warning: "This model is documented but has no current model-and-endpoint execution evidence; it remains review-only.",
      execution_route_default_eligible: false,
      codex_agent_enabled: true,
      authority_tier: "A",
    });

    expect(state).toMatchObject({
      label: "Preview / review route",
      tone: "warning",
      sendBlocked: false,
      requiresConfirmation: true,
    });
  });

  it("blocks a disabled model instead of describing it as review-ready", () => {
    const state = modelRouteAdmissionState({
      execution_route_status: "review_only",
      execution_route_default_eligible: false,
      codex_agent_enabled: false,
      authority_tier: "D",
    });

    expect(state).toMatchObject({
      label: "Blocked route",
      tone: "danger",
      sendBlocked: true,
      requiresConfirmation: false,
    });
  });

  it("explains that a confirmed degradation remains no-tools and never auto-falls back", () => {
    const copy = routeAdmissionCopy({
      schema_version: "astrabridge-runtime-route-admission-v1",
      status: "confirmation_required",
      route: { admission: "review_only" },
      effective: { execution_driver: "preview_review", execution_policy: "no_tools", permission_mode: "ask" },
      degradation: {
        requires_confirmation: true,
        reasons: [{ code: "tool_semantics_removed", message: "Tools are disabled." }],
      },
      fallback: { target_models: ["kimi/kimi-k4"], automatic_fallback: false },
    }, "en");

    expect(copy.canContinue).toBe(true);
    expect(copy.summary).toContain("read-only, no-tools");
    expect(copy.effectiveLine).toContain("no_tools");
    expect(copy.fallbackLine).toContain("will not switch models automatically");
  });
});
