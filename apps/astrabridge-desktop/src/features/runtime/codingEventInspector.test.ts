import { describe, expect, it } from "vitest";

import { summarizeCodingEventInspector } from "./codingEventInspector";

describe("coding event inspector summary", () => {
  it("collects changed, read, verified files and checkpoint refs from coding events", () => {
    const summary = summarizeCodingEventInspector({
      turns: [
        {
          provider_id: "deepseek",
          model: "deepseek-v4-pro",
          coding_events: [
            {
              event_type: "file_read",
              payload: { path: "README.md", kind: "text", ok: true },
            },
            {
              event_type: "edit_operation",
              payload: {
                path: "src/App.tsx",
                changed: true,
                applied: true,
                checkpoint_save_id: "save-before-app",
                review_diff_path: ".astrabridge/review/src-App.diff",
              },
            },
            {
              event_type: "verification_result",
              payload: {
                tool: "review_diff",
                files: ["src/App.tsx"],
                paths: ["src/routes.ts"],
                save_ids: ["save-listed-1"],
              },
            },
            {
              event_type: "checkpoint_created",
              payload: { save_id: "save-final", description: "After verification" },
            },
            {
              event_type: "command_execution",
              payload: { command: "python -m unittest -q test_scorecard", status: "failed", exit_code: 1 },
            },
            {
              event_type: "provider_handoff",
              payload: { provider_id: "kimi", model: "kimi-k2.7-code", to_thread_id: "thread-kimi" },
            },
          ],
        },
      ],
    } as never);

    expect(summary.reviewFiles).toEqual([
      { path: "README.md", status: "read" },
      { path: "src/App.tsx", status: "changed" },
      { path: "src/routes.ts", status: "verified" },
    ]);
    expect(summary.recentFiles.map((item) => item.path)).toEqual(["README.md", "src/App.tsx", "src/routes.ts"]);
    expect(summary.detailByPath["src/App.tsx"]).toContain("Applied edit.");
    expect(summary.detailByPath["src/App.tsx"]).toContain("Review diff artifact");
    expect(summary.detailByPath["src/routes.ts"]).toContain("Referenced by review_diff.");
    expect(summary.checkpointRefs).toEqual([
      {
        save_id: "save-before-app",
        description: "Checkpoint before editing src/App.tsx",
        provider_id: "deepseek",
        model_id: "deepseek-v4-pro",
      },
      {
        save_id: "save-listed-1",
        description: "Checkpoint listed by review_diff",
        provider_id: "deepseek",
        model_id: "deepseek-v4-pro",
      },
      {
        save_id: "save-final",
        description: "After verification",
        provider_id: "deepseek",
        model_id: "deepseek-v4-pro",
      },
    ]);
    expect(summary.commandRefs).toEqual([
      {
        command: "python -m unittest -q test_scorecard",
        status: "failed",
        exit_code: 1,
        provider_id: "deepseek",
        model_id: "deepseek-v4-pro",
      },
    ]);
    expect(summary.diagnosticRefs).toEqual([
      {
        kind: "provider_handoff",
        summary: "Handoff to kimi kimi-k2.7-code",
        provider_id: "deepseek",
        model_id: "deepseek-v4-pro",
        to_thread_id: "thread-kimi",
      },
    ]);
  });

  it("deduplicates repeated file and checkpoint references", () => {
    const summary = summarizeCodingEventInspector({
      turns: [
        {
          provider_id: "glm",
          model: "glm-5.2",
          coding_events: [
            { event_type: "file_change", payload: { paths: ["src/App.tsx"] } },
            { event_type: "verification_result", payload: { tool: "review_status", files: ["src/App.tsx"], save_ids: ["save-1", "save-1"] } },
            { event_type: "checkpoint_created", payload: { save_id: "save-1", description: "Existing" } },
            { event_type: "command_execution", payload: { command: "npm test", status: "ok", exit_code: 0 } },
            { event_type: "command_execution", payload: { command: "npm test", status: "ok", exit_code: 0 } },
          ],
        },
      ],
    } as never);

    expect(summary.reviewFiles).toEqual([{ path: "src/App.tsx", status: "changed" }]);
    expect(summary.checkpointRefs).toEqual([
      {
        save_id: "save-1",
        description: "Checkpoint listed by review_status",
        provider_id: "glm",
        model_id: "glm-5.2",
      },
    ]);
    expect(summary.commandRefs).toEqual([
      {
        command: "npm test",
        status: "ok",
        exit_code: 0,
        provider_id: "glm",
        model_id: "glm-5.2",
      },
    ]);
  });
});
