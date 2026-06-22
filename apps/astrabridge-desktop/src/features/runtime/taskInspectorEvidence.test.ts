import { describe, expect, it } from "vitest";

import type { ProjectTask, ShellThread } from "../../types";
import { summarizeTaskInspectorEvidence } from "./taskInspectorEvidence";

function buildTask(overrides: Partial<ProjectTask> = {}): ProjectTask {
  return {
    schema_version: "astrabridge-task-state-v1",
    task_id: "task-1",
    title: "Demo task",
    status: "active",
    handoff_policy: "multi_provider_handoff",
    active_provider_thread_id: "thread-1",
    provider_threads: [{ thread_id: "thread-1", provider_id: "deepseek", model: "deepseek-v4-pro", reasoning_effort: "high" }],
    handoff_events: [],
    checkpoint_refs: [],
    verification_refs: [],
    diagnostic_refs: [],
    created_at: "2026-06-22T00:00:00Z",
    updated_at: "2026-06-22T00:00:00Z",
    ...overrides,
  };
}

function buildThread(overrides: Partial<ShellThread> = {}): Pick<ShellThread, "turns"> {
  return {
    turns: [],
    ...overrides,
  };
}

describe("task inspector evidence", () => {
  it("merges persisted verification and diagnostic refs into fallback inspector evidence", () => {
    const summary = summarizeTaskInspectorEvidence(
      buildTask({
        checkpoint_refs: [{ save_id: "save-1", description: "Persisted checkpoint" }],
        verification_refs: [
          {
            event_id: "verify-1",
            kind: "edit_operation",
            tool: "edit_apply",
            path: "src/App.tsx",
            checkpoint_save_id: "save-1",
            review_diff_path: "/api/project/review/diff?path=src/App.tsx",
            provider_id: "deepseek",
            model: "deepseek-v4-pro",
          },
          {
            event_id: "verify-2",
            kind: "verification_result",
            tool: "review_diff",
            files: ["src/routes.ts"],
          },
        ],
        diagnostic_refs: [
          {
            event_id: "cmd-1",
            kind: "command_execution",
            command: "npm test",
            status: "failed",
            provider_id: "deepseek",
            model: "deepseek-v4-pro",
          },
          {
            event_id: "handoff-1",
            kind: "provider_handoff",
            provider_id: "kimi",
            model: "kimi-k2.6",
            to_thread_id: "thread-2",
          },
        ],
      }),
      buildThread(),
    );

    expect(summary.reviewFiles).toEqual([
      { path: "src/App.tsx", status: "changed" },
      { path: "src/routes.ts", status: "verified" },
    ]);
    expect(summary.detailByPath["src/App.tsx"]).toContain("Persisted task edit evidence.");
    expect(summary.detailByPath["src/App.tsx"]).toContain("Review diff artifact");
    expect(summary.detailByPath["src/routes.ts"]).toContain("Persisted task evidence from review_diff.");
    expect(summary.checkpointRefs).toEqual([
      {
        save_id: "save-1",
        description: "Checkpoint referenced by edit_apply",
        provider_id: "deepseek",
        model_id: "deepseek-v4-pro",
      },
    ]);
    expect(summary.commandRefs).toEqual([
      {
        command: "npm test",
        status: "failed",
        exit_code: null,
        provider_id: "deepseek",
        model_id: "deepseek-v4-pro",
      },
    ]);
    expect(summary.diagnosticRefs).toEqual([
      {
        kind: "command_execution",
        summary: "npm test (failed)",
        provider_id: "deepseek",
        model_id: "deepseek-v4-pro",
        to_thread_id: undefined,
      },
      {
        kind: "provider_handoff",
        summary: "Handoff to kimi kimi-k2.6",
        provider_id: "kimi",
        model_id: "kimi-k2.6",
        to_thread_id: "thread-2",
      },
    ]);
  });

  it("preserves live thread evidence and adds missing persisted records without duplication", () => {
    const summary = summarizeTaskInspectorEvidence(
      buildTask({
        verification_refs: [
          {
            event_id: "verify-1",
            kind: "edit_operation",
            path: "src/App.tsx",
            checkpoint_save_id: "save-1",
          },
        ],
      }),
      buildThread({
        turns: [
          {
            provider_id: "deepseek",
            model: "deepseek-v4-pro",
            coding_events: [
              {
                event_type: "edit_operation",
                payload: { path: "src/App.tsx", checkpoint_save_id: "save-1" },
              },
            ],
          } as never,
        ],
      }),
    );

    expect(summary.reviewFiles).toEqual([{ path: "src/App.tsx", status: "reviewed" }]);
    expect(summary.checkpointRefs).toHaveLength(1);
    expect(summary.checkpointRefs[0]?.save_id).toBe("save-1");
  });
});
