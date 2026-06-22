import { describe, expect, it } from "vitest";

import type { RuntimeSupervisorState } from "../../types";
import { runtimeErrorNoticeActions, runtimeErrorNoticeInline, runtimeErrorNoticeText } from "./runtimeErrorNotice";

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

  it("summarizes inline failure text without the suggested-actions suffix", () => {
    const runtimeError = {
      level: "danger",
      category: "auth_failure",
      summary: "Provider authentication failed.",
      actionable_hint: "Reload the provider key before retrying.",
      recommended_actions: [{ action: "refresh_provider_key", label: "Reload Key", reason: "Reload the key.", target: null }],
    } satisfies NonNullable<RuntimeSupervisorState["runtime_error"]>;

    expect(runtimeErrorNoticeInline(runtimeError)).toBe("Provider authentication failed. Reload the provider key before retrying.");
  });

  it("deduplicates and caps recovery actions", () => {
    const runtimeError = {
      level: "danger",
      category: "context_window_limit",
      summary: "The request exceeded the model context window.",
      recommended_actions: [
        { action: "compact_thread", label: "Compact", reason: "Summarize the thread before retrying.", target: null },
        { action: "compact_thread", label: "Compact", reason: "Duplicate labels should dedupe.", target: null },
        { action: "fork_followup", label: "Fork Narrower", reason: "Continue in a smaller thread.", target: null },
        { action: "switch_model", label: "Try Fallback Model", reason: "Use a smaller model.", target: "mini" },
        { action: "retry_same_lane", label: "Retry", reason: "Retry once.", target: null },
      ],
    } satisfies NonNullable<RuntimeSupervisorState["runtime_error"]>;

    expect(runtimeErrorNoticeActions(runtimeError)).toEqual([
      { action: "compact_thread", label: "Compact", reason: "Summarize the thread before retrying.", target: null },
      { action: "fork_followup", label: "Fork Narrower", reason: "Continue in a smaller thread.", target: null },
      { action: "switch_model", label: "Try Fallback Model", reason: "Use a smaller model.", target: "mini" },
    ]);
  });
});
