import { describe, expect, it } from "vitest";

import { summarizeTaskWorkflowFacts } from "./taskWorkflowFacts";
import type { ProjectTask, ShellThread } from "../../types";

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
    checkpoint_refs: [],
    created_at: "2026-06-22T00:00:00Z",
    updated_at: "2026-06-22T00:00:00Z",
    ...overrides,
  };
}

function buildThread(backend: "app_server" | "native_kernel"): Pick<ShellThread, "shellSettings"> {
  return {
    shellSettings: {
      execution_backend: backend,
    },
  };
}

describe("task workflow facts", () => {
  it("summarizes provider lanes, handoffs, checkpoints, and native backend", () => {
    const facts = summarizeTaskWorkflowFacts(
      buildTask({
        provider_threads: [
          { thread_id: "thread-1", provider_id: "deepseek", model: "deepseek-v4-pro" },
          { thread_id: "thread-2", provider_id: "kimi", model: "kimi-k2.6" },
        ],
        handoff_events: [{ event_id: "handoff-1", type: "provider_handoff", to_thread_id: "thread-2", created_at: "2026-06-22T00:10:00Z" }],
        checkpoint_refs: [{ save_id: "save-1" }, { save_id: "save-2" }],
      }),
      buildThread("native_kernel"),
    );

    expect(facts).toEqual({
      laneCount: 2,
      handoffCount: 1,
      checkpointCount: 2,
      commandCount: 0,
      diagnosticCount: 0,
      backend: "native_kernel",
    });
  });

  it("fails closed to app_server when execution backend is absent", () => {
    const facts = summarizeTaskWorkflowFacts(buildTask(), null);
    expect(facts.backend).toBe("app_server");
    expect(facts.laneCount).toBe(1);
    expect(facts.handoffCount).toBe(0);
    expect(facts.commandCount).toBe(0);
    expect(facts.diagnosticCount).toBe(0);
  });

  it("uses coding-event fallback for checkpoints, commands, and diagnostics", () => {
    const facts = summarizeTaskWorkflowFacts(
      buildTask({ handoff_events: [], checkpoint_refs: [] }),
      null,
      {
        checkpointRefs: [{ save_id: "save-1", description: "Event checkpoint" }],
        commandRefs: [{ command: "python -m unittest", status: "ok" }],
        diagnosticRefs: [{ kind: "provider_handoff", summary: "handoff" }, { kind: "runtime_transition", summary: "transition" }],
      },
    );

    expect(facts).toEqual({
      laneCount: 1,
      handoffCount: 1,
      checkpointCount: 1,
      commandCount: 1,
      diagnosticCount: 2,
      backend: "app_server",
    });
  });
});
