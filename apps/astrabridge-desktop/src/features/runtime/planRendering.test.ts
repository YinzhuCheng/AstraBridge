import { describe, expect, it } from "vitest";
import { contextGuardLevel, extractProposedPlanText, hasUnsafeWindowsWrite, parsePlanCard, readsExplosiveAstraBridgeLog } from "./planRendering";

describe("plan rendering helpers", () => {
  it("extracts and summarizes proposed plans", () => {
    const parsed = parsePlanCard(`<proposed_plan>
# Demo Plan
## Summary
- Keep the inspector compact.
- Render plan updates clearly.
## Key Changes
- Add PlanRenderer.
- Run tests.
</proposed_plan>`);
    expect(extractProposedPlanText(parsed.raw)).toBe("");
    expect(parsed.title).toBe("Demo Plan");
    expect(parsed.summary).toContain("Keep the inspector compact.");
    expect(parsed.steps).toContain("Add PlanRenderer.");
  });

  it("maps context guard thresholds", () => {
    expect(contextGuardLevel(69.9)).toBe("ok");
    expect(contextGuardLevel(70)).toBe("warning");
    expect(contextGuardLevel(80)).toBe("danger");
    expect(contextGuardLevel(90)).toBe("pause");
  });

  it("flags risky Windows write and .astrabridge log reads", () => {
    expect(hasUnsafeWindowsWrite("Set-Content index.html $html")).toBe(true);
    expect(hasUnsafeWindowsWrite("[IO.File]::WriteAllText($p, $html, [Text.UTF8Encoding]::new($false))")).toBe(false);
    expect(readsExplosiveAstraBridgeLog("Get-Content .astrabridge/runtime_events.jsonl")).toBe(true);
  });
});

