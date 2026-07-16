import { describe, expect, it } from "vitest";

import { shouldShowGoalDock } from "./goalDockVisibility";

describe("shouldShowGoalDock", () => {
  it("keeps goal editing available even before a goal exists", () => {
    expect(shouldShowGoalDock({ workflowMode: "goal", hasPlan: false, hasProposedPlan: false })).toBe(true);
  });

  it("does not add an empty plan panel above the composer", () => {
    expect(shouldShowGoalDock({ workflowMode: "plan", hasPlan: false, hasProposedPlan: false })).toBe(false);
  });

  it("shows plan details only when the task has plan content", () => {
    expect(shouldShowGoalDock({ workflowMode: "plan", hasPlan: true, hasProposedPlan: false })).toBe(true);
    expect(shouldShowGoalDock({ workflowMode: "plan", hasPlan: false, hasProposedPlan: true })).toBe(true);
  });
});
