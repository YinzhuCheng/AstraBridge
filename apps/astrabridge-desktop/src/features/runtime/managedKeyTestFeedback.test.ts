import { describe, expect, it } from "vitest";

import type { RouterTestResult } from "../../types";
import { summarizeManagedKeyTest, summarizeManagedKeyTestError } from "./managedKeyTestFeedback";

function result(overrides: Partial<RouterTestResult> = {}): RouterTestResult {
  return {
    ok: true,
    provider: "deepseek",
    model: "deepseek-v4-pro",
    stream: false,
    status: 200,
    preview: {},
    response_excerpt: "ok",
    ...overrides,
  };
}

describe("managed key test feedback", () => {
  it("keeps a successful health result actionable when no diagnostic is returned", () => {
    expect(summarizeManagedKeyTest(result(), null)).toEqual({
      tone: "success",
      title: "Provider test passed",
      provider: "deepseek",
      model: "deepseek-v4-pro",
      status: 200,
      diagnostic: "The provider returned a terminal response.",
      nextAction: "You can continue with a bounded task on this route.",
    });
  });

  it("does not surface provider reasoning or response excerpts after a successful test", () => {
    const feedback = summarizeManagedKeyTest(
      result(),
      "Excerpt: ok\nReasoning: a provider-specific explanation that belongs in diagnostics, not a compact success state.",
    );

    expect(feedback.diagnostic).toBe("The provider returned a terminal response.");
  });

  it("keeps a failed result diagnostic and blocks a budgeted task", () => {
    const feedback = summarizeManagedKeyTest(result({ ok: false, status: 401 }), "Key rejected by provider.");

    expect(feedback.tone).toBe("danger");
    expect(feedback.diagnostic).toBe("Key rejected by provider.");
    expect(feedback.nextAction).toContain("before starting a budgeted task");
  });

  it("keeps transport failures visible even without a provider response", () => {
    expect(summarizeManagedKeyTestError("deepseek", "Connection timed out.")).toMatchObject({
      tone: "danger",
      provider: "deepseek",
      model: "not confirmed",
      status: null,
      diagnostic: "Connection timed out.",
    });
  });

  it("keeps failure diagnostics to a bounded single line", () => {
    const feedback = summarizeManagedKeyTestError("deepseek", `Failure ${"detail ".repeat(50)}`);

    expect(feedback.diagnostic).not.toContain("\n");
    expect(feedback.diagnostic.length).toBeLessThanOrEqual(220);
  });
});
