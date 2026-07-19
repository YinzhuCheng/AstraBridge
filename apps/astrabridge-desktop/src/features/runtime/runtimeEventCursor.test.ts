import { describe, expect, it } from "vitest";

import type { RuntimeEvent } from "../../types";
import {
  reconcileRuntimeEventBatch,
  reconcileRuntimeEventFrame,
} from "./runtimeEventCursor";

function runtimeEvent(index: number, method: string): RuntimeEvent {
  return {
    index,
    timestamp: `2026-07-17T12:00:0${index}+09:00`,
    type: "notification",
    method,
    params: { threadId: "thread-1" },
  };
}

describe("runtimeEventCursor", () => {
  it("does not rewind the cursor on a stale hello frame", () => {
    const result = reconcileRuntimeEventFrame(5, { cursor: 3 });

    expect(result.nextCursor).toBe(5);
    expect(result.acceptedEvents).toEqual([]);
  });

  it("accepts only unseen tail events from an overlapping batch", () => {
    const result = reconcileRuntimeEventBatch(4, 3, {
      cursor: 5,
      events: [
        runtimeEvent(4, "turn/started"),
        runtimeEvent(5, "turn/completed"),
      ],
    });

    expect(result.nextCursor).toBe(5);
    expect(result.acceptedEvents.map((event) => event.method)).toEqual([
      "turn/completed",
    ]);
  });

  it("does not skip unseen events when a limited batch reports a later tail cursor", () => {
    const result = reconcileRuntimeEventBatch(3, 3, {
      cursor: 7,
      events: [
        runtimeEvent(4, "item/started"),
        runtimeEvent(5, "item/completed"),
      ],
    });

    expect(result.nextCursor).toBe(5);
    expect(result.acceptedEvents.map((event) => event.method)).toEqual([
      "item/started",
      "item/completed",
    ]);
  });

  it("drops duplicate stream frames that reconnect from an already delivered cursor", () => {
    const result = reconcileRuntimeEventFrame(6, {
      cursor: 6,
      event: runtimeEvent(6, "thread/status/changed"),
    });

    expect(result.nextCursor).toBe(6);
    expect(result.acceptedEvents).toEqual([]);
  });
});
