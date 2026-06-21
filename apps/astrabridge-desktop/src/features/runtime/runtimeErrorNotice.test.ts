import { describe, expect, it } from "vitest";

import type { RuntimeSupervisorState } from "../../types";
import { runtimeErrorNoticeText } from "./runtimeErrorNotice";

describe("runtime error notice", () => {
  it("combines summary, hint, and suggested recovery actions", () => {
    const runtimeError = {
      level: "danger",
      category: "context_window_limit",
      summary: "The request exceeded the model context window.",
      actionable_hint: "Compact the thread before retrying.",
      recommended_actions: [
        { action: "compact_thread", label: "Compact", reason: "Summarize the thread before retrying.", target: null },
        { action: "fork_followup", label: "Fork Narrower", reason: "Continue in a smaller thread.", target: null },
        { action: "compact_thread", label: "Compact", reason: "Duplicate labels should dedupe.", target: null },
      ],
    } satisfies NonNullable<RuntimeSupervisorState["runtime_error"]>;

    expect(runtimeErrorNoticeText(runtimeError)).toBe(
      "The request exceeded the model context window. Compact the thread before retrying. Suggested: Compact, Fork Narrower.",
    );
  });

  it("returns an empty string when no runtime error is present", () => {
    expect(runtimeErrorNoticeText(null)).toBe("");
  });
});
