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
    expect(parsed.sections.map((section) => section.title)).toEqual(["Summary", "Key Changes"]);
    expect(parsed.sections[1].items).toContain("Run tests.");
  });

  it("keeps plan sections and inline code intact for artifact rendering", () => {
    const parsed = parsePlanCard(`# Smart VPN Client 后续收口计划
Summary
除了 \`TCP fallback\` 之外，下一轮按稳定、功能、交付顺序做。

Test Plan
- 命令级检查：\`/healthz\` 返回 200。
- App 级检查：预检失败不启动 TUN。

Assumptions
- 不新增 AWS 付费资源。`);

    expect(parsed.title).toBe("Smart VPN Client 后续收口计划");
    expect(parsed.sections.map((section) => section.title)).toEqual(["Summary", "Test Plan", "Assumptions"]);
    expect(parsed.summary[0]).toContain("`TCP fallback`");
    expect(parsed.sections[1].items[0]).toContain("`/healthz`");
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

