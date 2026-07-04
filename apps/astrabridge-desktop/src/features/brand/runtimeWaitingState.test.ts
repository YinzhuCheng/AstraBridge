import { describe, expect, it } from "vitest";

import { buildRuntimeWaitingReplayState, resolveRuntimeWaitingState } from "./runtimeWaitingState";

describe("runtimeWaitingState", () => {
  it("prioritizes approval over other activity", () => {
    const state = resolveRuntimeWaitingState({
      locale: "en",
      routeLabel: "DeepSeek · deepseek-v4-pro",
      waitingOnApproval: true,
      activeStatusType: "active",
      liveActivity: {
        kind: "tool",
        label: "Calling tool",
        status: "active",
        preview: "filesystem.read_file",
      },
    });

    expect(state.phase).toBe("approval");
    expect(state.label).toContain("Live run");
    expect(state.title).toContain("approval");
    expect(state.detail).toContain("filesystem.read_file");
  });

  it("maps file diffs to the files phase with diff detail", () => {
    const state = resolveRuntimeWaitingState({
      locale: "en",
      routeLabel: "Qwen · qwen3.7-plus",
      waitingOnApproval: false,
      activeStatusType: "active",
      liveDiff: {
        files: 2,
        added: 9,
        deleted: 3,
        file_paths: ["apps/astrabridge-desktop/src/App.tsx", "apps/astrabridge-desktop/src/store.ts"],
      },
    });

    expect(state.phase).toBe("files");
    expect(state.title).toContain("Editing 2 files");
    expect(state.detail).toContain("App.tsx");
    expect(state.detail).toContain("+9 -3");
  });

  it("maps web-like tool activity to the web phase", () => {
    const state = resolveRuntimeWaitingState({
      locale: "zh-CN",
      routeLabel: "Kimi · kimi-k2",
      waitingOnApproval: false,
      activeStatusType: "active",
      liveActivity: {
        kind: "tool",
        label: "正在调用工具",
        status: "active",
        preview: "astrabridge_web_search_batch · sources: 3",
      },
    });

    expect(state.phase).toBe("web");
    expect(state.detail).toContain("sources: 3");
    expect(state.detail).toContain("当前路由");
  });

  it("follows the latest activity instead of a stale diff summary", () => {
    const state = resolveRuntimeWaitingState({
      locale: "en",
      routeLabel: "DeepSeek · deepseek-v4-pro",
      waitingOnApproval: false,
      activeStatusType: "active",
      liveDiff: {
        files: 1,
        added: 4,
        deleted: 1,
        file_paths: ["apps/astrabridge-desktop/src/App.tsx"],
      },
      liveActivity: {
        kind: "web_search",
        label: "Searching the web",
        status: "active",
        preview: "sources: 2",
      },
    });

    expect(state.phase).toBe("web");
    expect(state.title).toContain("Collecting web evidence");
  });

  it("falls back to thinking while a turn is still being started", () => {
    const state = resolveRuntimeWaitingState({
      locale: "en",
      routeLabel: "DeepSeek · deepseek-v4-pro",
      waitingOnApproval: false,
      activeStatusType: "idle",
      startPending: true,
    });

    expect(state.phase).toBe("thinking");
    expect(state.title).toContain("Preparing the next turn");
  });

  it("builds replay payloads with the expected runtime shape", () => {
    const replay = buildRuntimeWaitingReplayState("files", "en");

    expect(replay.status.type).toBe("active");
    expect(replay.diff?.files).toBe(2);
    expect(replay.activity).toBeUndefined();
  });
});
