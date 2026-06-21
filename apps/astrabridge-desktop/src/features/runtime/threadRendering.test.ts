import { describe, expect, it } from "vitest";

import { hasPersistedRenderableTurnContent, itemActivityFromPayload, renderBlocksForItem, summarizeTurnBlocks } from "./threadRendering";
import type { ShellThread } from "../../types";

describe("thread rendering helpers", () => {
  it("renders verified dynamic tool evidence into the tool block", () => {
    const blocks = renderBlocksForItem({
      type: "dynamicToolCall",
      id: "tool-1",
      namespace: "lcr_browser",
      tool: "lcr_browser_smoke",
      arguments: { url: "http://127.0.0.1:4174" },
      status: "completed",
      contentItems: null,
      success: true,
      durationMs: 1234,
      lcrVerifiedEvidence: {
        verified: true,
        label: "tool-event verified",
        summary: ["browser smoke app pass"],
        paths: ["D:/workspace/.astrabridge/captures/app.png"],
      },
    } as never);

    expect(blocks).toHaveLength(1);
    expect(blocks[0].role).toBe("tool");
    expect(blocks[0]).toMatchObject({
      title: "lcr_browser.lcr_browser_smoke",
      status: "completed",
    });
    if (blocks[0].role !== "tool") throw new Error("expected tool block");
    expect(blocks[0].detail).toContain("tool-event verified");
    expect(blocks[0].detail).toContain("browser smoke app pass");
    expect(blocks[0].detail).toContain("D:/workspace/.astrabridge/captures/app.png");
  });

  it("renders MCP tool results from text content before falling back to raw JSON", () => {
    const [block] = renderBlocksForItem({
      type: "mcpToolCall",
      id: "mcp-1",
      server: "filesystem",
      tool: "read_file",
      status: "completed",
      arguments: { path: "README.md" },
      pluginId: null,
      durationMs: 25,
      error: null,
      result: {
        content: [
          { type: "text", text: "README first line" },
          { type: "text", text: "README second line" },
        ],
        structuredContent: { summary: "structured fallback" },
        _meta: null,
      },
    } as never);

    expect(block.role).toBe("tool");
    if (block.role !== "tool") throw new Error("expected tool block");
    expect(block.detail).toContain("README first line");
    expect(block.detail).toContain("README second line");
  });

  it("renders dynamic tool output text and image counts", () => {
    const [block] = renderBlocksForItem({
      type: "dynamicToolCall",
      id: "tool-2",
      namespace: "browser",
      tool: "capture",
      arguments: { url: "http://127.0.0.1:4174" },
      status: "completed",
      success: true,
      durationMs: 200,
      contentItems: [
        { type: "inputText", text: "browser smoke passed" },
        { type: "inputImage", imageUrl: "file:///capture.png" },
      ],
    } as never);

    expect(block.role).toBe("tool");
    if (block.role !== "tool") throw new Error("expected tool block");
    expect(block.detail).toContain("browser smoke passed");
    expect(block.detail).toContain("1 image item");
  });

  it("renders review mode items as activity blocks", () => {
    const [entered] = renderBlocksForItem({
      type: "enteredReviewMode",
      id: "review-1",
      review: "Detached review requested",
    } as never);
    const [exited] = renderBlocksForItem({
      type: "exitedReviewMode",
      id: "review-2",
      review: "Review complete",
    } as never);

    expect(entered.role).toBe("activity");
    expect(exited.role).toBe("activity");
    if (entered.role !== "activity" || exited.role !== "activity") throw new Error("expected activity blocks");
    expect(entered.activity.kind).toBe("review");
    expect(entered.activity.preview).toBe("Detached review requested");
    expect(exited.activity.kind).toBe("review");
  });

  it("renders file changes with diff counts and detail excerpts", () => {
    const [block] = renderBlocksForItem({
      type: "fileChange",
      id: "file-1",
      status: "accepted",
      changes: [
        {
          path: "src/App.tsx",
          kind: { type: "update", move_path: null },
          diff: [
            "--- a/src/App.tsx",
            "+++ b/src/App.tsx",
            "@@",
            "-old line",
            "+new line",
            "+second line",
          ].join("\n"),
        },
        {
          path: "src/new.ts",
          kind: { type: "add" },
          diff: [
            "--- /dev/null",
            "+++ b/src/new.ts",
            "@@",
            "+export const value = 1;",
          ].join("\n"),
        },
      ],
    } as never);

    expect(block.role).toBe("file_change");
    if (block.role !== "file_change") throw new Error("expected file change block");
    expect(block.files).toEqual(["src/App.tsx", "src/new.ts"]);
    expect(block.added).toBe(3);
    expect(block.deleted).toBe(1);
    expect(block.detail).toContain("src/App.tsx");
    expect(block.detail).toContain("src/new.ts");
    expect(block.detail).toContain("新增");
  });

  it("surfaces suspect turn completion quality as a follow-up warning block", () => {
    const thread = {
      turns: [
        {
          id: "turn-1",
          status: "completed",
          startedAt: 1,
          completedAt: 2,
          durationMs: 1000,
          items: [
            { type: "agentMessage", id: "agent-1", text: "done", phase: null, memoryCitation: null },
          ],
          lcrCompletionQuality: {
            status: "suspect",
            reason: "completed_with_short_or_progress_only_final_after_verified_activity",
            recommended_action: "continue_or_retry_final_answer",
            final_preview: "Now let me produce the full answer.",
          },
        },
      ],
    } as unknown as Pick<ShellThread, "turns">;

    const blocks = summarizeTurnBlocks(thread);
    const warning = blocks.find((block) => block.role === "activity");

    expect(warning).toBeTruthy();
    if (!warning || warning.role !== "activity") throw new Error("expected warning activity");
    expect(warning.activity.label).toBe("Final answer may need a follow-up");
    expect(warning.activity.preview).toContain("Now let me produce the full answer.");
    expect(warning.activity.detail).toContain("continue_or_retry_final_answer");
  });

  it("carries provider metadata from composite task turns onto render blocks", () => {
    const thread = {
      turns: [
        {
          id: "turn-1",
          startedAt: 1,
          completedAt: 2,
          source_thread_id: "thread-deepseek",
          provider_id: "deepseek",
          profile_id: "deepseek-default",
          model: "deepseek-v4-pro",
          reasoning_effort: "max",
          items: [
            { type: "agentMessage", id: "agent-1", text: "implemented", phase: null, memoryCitation: null },
          ],
        },
      ],
    } as unknown as Pick<ShellThread, "turns">;

    const [block] = summarizeTurnBlocks(thread);

    expect(block.providerId).toBe("deepseek");
    expect(block.profileId).toBe("deepseek-default");
    expect(block.model).toBe("deepseek-v4-pro");
    expect(block.reasoningEffort).toBe("max");
    expect(block.sourceThreadId).toBe("thread-deepseek");
  });

  it("renders live active-provider updates when composite task turns have not caught up yet", () => {
    const thread = {
      turns: [
        {
          id: "turn-old",
          startedAt: 1,
          completedAt: 2,
          provider_id: "deepseek",
          items: [
            { type: "agentMessage", id: "agent-old", text: "first lane done", phase: null, memoryCitation: null },
          ],
        },
      ],
    } as unknown as Pick<ShellThread, "turns">;

    const blocks = summarizeTurnBlocks(
      thread,
      "continuing in Kimi",
      undefined,
      { kind: "thinking", label: "正在思考", status: "active" },
      undefined,
      "turn-kimi-live",
    );

    expect(blocks.some((block) => block.turnId === "turn-kimi-live" && block.role === "activity")).toBe(true);
    expect(blocks.some((block) => block.turnId === "turn-kimi-live" && block.role === "assistant_live")).toBe(true);
  });

  it("classifies collab spawn events as fork activity for live updates", () => {
    const activity = itemActivityFromPayload({
      type: "collabAgentToolCall",
      id: "collab-1",
      tool: "spawnAgent",
      receiverThreadIds: ["thread-fork-1"],
      model: "deepseek-v4-pro",
      reasoningEffort: "high",
      prompt: "Review the CSS changes and report layout risks.",
      agentsStates: { agent_a: { status: "running" } },
    }, "active");

    expect(activity).toBeTruthy();
    expect(activity?.kind).toBe("fork");
    expect(activity?.preview).toContain("thread-fork-1");
    expect(activity?.detail).toContain("deepseek-v4-pro");
    expect(activity?.detail).toContain("Review the CSS changes");
  });

  it("uses readable localized labels for normalized live activity", () => {
    const compact = itemActivityFromPayload({ type: "contextCompaction", id: "compact-1" }, "completed");
    const review = itemActivityFromPayload({ type: "enteredReviewMode", id: "review-1", review: "Inspect diff" }, "completed");

    expect(compact?.label).toBe("上下文已压缩");
    expect(review?.label).toBe("进入审查模式");
  });

  it("detects when a completed persisted turn is ready to replace live content", () => {
    expect(
      hasPersistedRenderableTurnContent({
        completedAt: 10,
        items: [{ type: "userMessage", id: "user-1", content: [{ type: "text", text: "hi" }] } as never],
      }),
    ).toBe(false);

    expect(
      hasPersistedRenderableTurnContent({
        completedAt: 10,
        items: [
          { type: "userMessage", id: "user-1", content: [{ type: "text", text: "hi" }] } as never,
          { type: "agentMessage", id: "assistant-1", text: "done", phase: null, memoryCitation: null } as never,
        ],
      }),
    ).toBe(true);
  });
});
