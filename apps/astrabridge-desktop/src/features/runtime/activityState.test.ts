import { describe, expect, it, beforeEach } from "vitest";

import { useAppStore } from "../../store";

function resetEvents() {
  useAppStore.setState({
    eventSnapshot: {
      liveTextByTurn: {},
      livePlanTextByTurn: {},
      liveReasoningByTurn: {},
      activityByTurn: {},
      diffByTurn: {},
      planByThread: {},
      tokenUsageByThread: {},
      latestTurnIdByThread: {},
      threadStatusByThread: {},
    },
  });
}

describe("runtime activity state", () => {
  beforeEach(() => resetEvents());

  it("accumulates provider reasoning and marks the turn as thinking", () => {
    const store = useAppStore.getState();

    store.appendReasoningDelta("thread-1", "turn-1", "first line\n", "item/reasoning/textDelta", "raw provider reasoning");
    store.appendReasoningDelta("thread-1", "turn-1", "second line", "item/reasoning/textDelta", "raw provider reasoning");

    const snapshot = useAppStore.getState().eventSnapshot;
    expect(snapshot.liveReasoningByTurn["turn-1"].text).toBe("first line\nsecond line");
    expect(snapshot.liveReasoningByTurn["turn-1"].label).toBe("raw provider reasoning");
    expect(snapshot.activityByTurn["turn-1"].kind).toBe("thinking");
    expect(snapshot.latestTurnIdByThread["thread-1"]).toBe("turn-1");
  });

  it("keeps command preview stable while appending output details", () => {
    const store = useAppStore.getState();

    store.setTurnActivity("thread-1", "turn-1", {
      kind: "command",
      label: "Running command",
      status: "active",
      preview: "npm test",
      detail: "start",
      item_id: "cmd-1",
    });
    store.setTurnActivity("thread-1", "turn-1", {
      kind: "command",
      label: "Running command",
      status: "active",
      detail: "done",
      item_id: "cmd-1",
    });

    const activity = useAppStore.getState().eventSnapshot.activityByTurn["turn-1"];
    expect(activity.preview).toBe("npm test");
    expect(activity.detail).toContain("start");
    expect(activity.detail).toContain("done");
  });

  it("tracks diff progress and clears live turn state", () => {
    const store = useAppStore.getState();

    store.setTurnDiff("thread-1", "turn-1", { files: 2, added: 12, deleted: 5 });
    expect(useAppStore.getState().eventSnapshot.diffByTurn["turn-1"]).toMatchObject({ files: 2, added: 12, deleted: 5 });
    expect(useAppStore.getState().eventSnapshot.activityByTurn["turn-1"].preview).toBe("2 files, +12 -5");

    store.clearLiveTurn("thread-1", "turn-1");
    const snapshot = useAppStore.getState().eventSnapshot;
    expect(snapshot.diffByTurn["turn-1"]).toBeUndefined();
    expect(snapshot.activityByTurn["turn-1"]).toBeUndefined();
  });
});

