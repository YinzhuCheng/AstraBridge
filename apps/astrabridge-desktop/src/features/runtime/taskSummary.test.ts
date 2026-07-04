import { describe, expect, it } from "vitest";

import { summarizeTaskCard } from "./taskSummary";
import type { ProjectTask } from "../../types";

function buildTask(overrides: Partial<ProjectTask> = {}): ProjectTask {
  return {
    schema_version: "astrabridge-task-state-v1",
    task_id: "task-1",
    title: "Demo task",
    status: "active",
    handoff_policy: "multi_provider_handoff",
    active_provider_thread_id: "thread-1",
    provider_threads: [
      {
        thread_id: "thread-1",
        profile_id: "deepseek-default",
        provider_id: "deepseek",
        model: "deepseek-v4-pro",
        reasoning_effort: "high",
      },
    ],
    handoff_events: [],
    created_at: "2026-06-21T00:00:00Z",
    updated_at: "2026-06-21T00:00:00Z",
    ...overrides,
  };
}

describe("task summary", () => {
  it("shows route, fork, checkpoint, and missing status", () => {
    const summary = summarizeTaskCard(
      buildTask({
        handoff_events: [
          {
            event_id: "handoff-1",
            type: "provider_handoff",
            to_thread_id: "thread-1",
            profile_id: "deepseek-default",
            provider_id: "deepseek",
            model: "deepseek-v4-pro",
            created_at: "2026-06-21T00:00:00Z",
          },
        ],
        fork_threads: [{ thread_id: "fork-1", role: "fork", model: "deepseek-v4-pro", reasoning_effort: "high" }],
        checkpoint_refs: [{ save_id: "save-1" }],
        provider_threads: [
          { thread_id: "thread-1", profile_id: "deepseek-default", provider_id: "deepseek", model: "deepseek-v4-pro", reasoning_effort: "high" },
          { thread_id: "thread-missing", profile_id: "deepseek-default", provider_id: "deepseek", model: "deepseek-v4-flash", reasoning_effort: "high", missing_at: "2026-06-21T00:01:00Z" },
        ],
      }),
    );

    expect(summary.subtitle).toContain("已切换到 deepseek");
    expect(summary.routeProvider).toBe("deepseek");
    expect(summary.routeModel).toBe("deepseek-v4-pro");
    expect(summary.routeEffort).toBe("high");
    expect(summary.stats).toEqual(["1 个分支", "1 个检查点", "1 条异常线路"]);
    expect(summary.tone).toBe("warning");
  });

  it("falls back to execution thread count when no handoff exists", () => {
    const summary = summarizeTaskCard(buildTask());
    expect(summary.subtitle).toBe("1 条执行线路");
    expect(summary.routeProvider).toBe("deepseek");
    expect(summary.stats).toEqual([]);
    expect(summary.tone).toBe("default");
  });
});
