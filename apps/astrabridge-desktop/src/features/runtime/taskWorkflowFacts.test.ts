import { describe, expect, it } from "vitest";

import { summarizeTaskWorkflowFacts } from "./taskWorkflowFacts";
import { summarizeTaskInspectorEvidence } from "./taskInspectorEvidence";
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
      failedCommandCount: 0,
      recoveredCommandCount: 0,
      backend: "native_kernel",
      checkpointRefs: [
        { save_id: "save-1", description: "save-1" },
        { save_id: "save-2", description: "save-2" },
      ],
      diagnosticRefs: [],
    });
  });

  it("fails closed to app_server when execution backend is absent", () => {
    const facts = summarizeTaskWorkflowFacts(buildTask(), null);
    expect(facts.backend).toBe("app_server");
    expect(facts.laneCount).toBe(1);
    expect(facts.handoffCount).toBe(0);
    expect(facts.commandCount).toBe(0);
    expect(facts.diagnosticCount).toBe(0);
    expect(facts.failedCommandCount).toBe(0);
    expect(facts.recoveredCommandCount).toBe(0);
    expect(facts.checkpointRefs).toEqual([]);
    expect(facts.diagnosticRefs).toEqual([]);
  });

  it("uses coding-event fallback for checkpoints, commands, and diagnostics", () => {
    const facts = summarizeTaskWorkflowFacts(
      buildTask({ handoff_events: [], checkpoint_refs: [] }),
      null,
      {
        checkpointRefs: [{ save_id: "save-1", description: "Event checkpoint" }],
        commandRefs: [
          { command: "python -m unittest", status: "failed" },
          { command: "python -m unittest", status: "completed" },
        ],
        diagnosticRefs: [{ kind: "provider_handoff", summary: "handoff" }, { kind: "runtime_transition", summary: "transition" }],
      },
    );

    expect(facts).toEqual({
      laneCount: 1,
      handoffCount: 1,
      checkpointCount: 1,
      commandCount: 2,
      diagnosticCount: 2,
      failedCommandCount: 1,
      recoveredCommandCount: 1,
      backend: "app_server",
      checkpointRefs: [{ save_id: "save-1", description: "Event checkpoint" }],
      commandRefs: [
        { command: "python -m unittest", status: "failed" },
        { command: "python -m unittest", status: "completed" },
      ],
      diagnosticRefs: [
        { key: "provider_handoff:handoff:", kind: "provider_handoff", summary: "handoff" },
        { key: "runtime_transition:transition:", kind: "runtime_transition", summary: "transition" },
      ],
    });
  });

  it("merges persisted task diagnostic and checkpoint refs with live event summaries", () => {
    const facts = summarizeTaskWorkflowFacts(
      buildTask({
        checkpoint_refs: [{ save_id: "save-1", description: "Persisted checkpoint" }],
        diagnostic_refs: [
          { event_id: "handoff-1", kind: "provider_handoff", provider_id: "kimi", model: "kimi-k2.6", to_thread_id: "thread-2" },
          { event_id: "cmd-1", kind: "command_execution", command: "npm test", status: "failed" },
        ],
      }),
      null,
      {
        checkpointRefs: [{ save_id: "save-2", description: "Event checkpoint" }],
        commandRefs: [{ command: "npm test", status: "failed" }],
        diagnosticRefs: [{ kind: "runtime_transition", summary: "Runtime transition: review_entered" }],
      },
    );

    expect(facts.checkpointCount).toBe(2);
    expect(facts.diagnosticCount).toBe(3);
    expect(facts.handoffCount).toBe(1);
    expect(facts.checkpointRefs.map((item) => item.save_id)).toEqual(["save-1", "save-2"]);
    expect(facts.diagnosticRefs.map((item) => item.kind)).toEqual(["provider_handoff", "command_execution", "runtime_transition"]);
    expect(facts.diagnosticRefs[0]?.summary).toBe("Handoff to kimi kimi-k2.6");
    expect(facts.diagnosticRefs[1]?.summary).toBe("npm test (failed)");
  });

  it("counts persisted command diagnostics even when no live command events are present", () => {
    const facts = summarizeTaskWorkflowFacts(
      buildTask({
        diagnostic_refs: [
          { event_id: "cmd-1", kind: "command_execution", command: "npm test", status: "failed" },
          { event_id: "cmd-2", kind: "command_execution", command: "npm test", status: "completed" },
        ],
      }),
      null,
      null,
    );

    expect(facts.commandCount).toBe(2);
    expect(facts.failedCommandCount).toBe(1);
    expect(facts.recoveredCommandCount).toBe(1);
  });

  it("accepts task inspector evidence as the single workflow summary input", () => {
    const task = buildTask({
      checkpoint_refs: [{ save_id: "save-1", description: "Persisted checkpoint" }],
      verification_refs: [
        {
          event_id: "verify-1",
          kind: "verification_result",
          tool: "review_diff",
          files: ["src/scorecard.py"],
        },
      ],
      diagnostic_refs: [
        { event_id: "handoff-1", kind: "provider_handoff", provider_id: "kimi", model: "kimi-k2.6", to_thread_id: "thread-2" },
        { event_id: "cmd-1", kind: "command_execution", command: "python -m unittest", status: "failed" },
        { event_id: "cmd-2", kind: "command_execution", command: "python -m unittest", status: "completed" },
      ],
    });
    const evidence = summarizeTaskInspectorEvidence(task, { turns: [] });
    const facts = summarizeTaskWorkflowFacts(task, buildThread("app_server"), evidence);

    expect(facts.laneCount).toBe(1);
    expect(facts.handoffCount).toBe(1);
    expect(facts.checkpointCount).toBe(1);
    expect(facts.commandCount).toBe(2);
    expect(facts.failedCommandCount).toBe(1);
    expect(facts.recoveredCommandCount).toBe(1);
    expect(facts.diagnosticRefs[0]?.kind).toBe("provider_handoff");
    expect(facts.diagnosticRefs[0]?.summary).toBe("Handoff to kimi kimi-k2.6");
  });
});
