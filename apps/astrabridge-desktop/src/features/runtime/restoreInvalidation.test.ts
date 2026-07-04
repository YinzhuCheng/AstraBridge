import { describe, expect, it, vi } from "vitest";

import { invalidateRestoreStateQueries, RESTORE_STATE_INVALIDATION_QUERY_KEYS } from "./restoreInvalidation";

describe("restore state invalidation", () => {
  it("covers project, task, conversation, thread, goal, and inspector state", () => {
    const invalidateQueries = vi.fn();

    invalidateRestoreStateQueries({ invalidateQueries });

    const invalidatedKeys = invalidateQueries.mock.calls.map(([request]) => request.queryKey);
    expect(invalidatedKeys).toEqual(RESTORE_STATE_INVALIDATION_QUERY_KEYS.map((queryKey) => [...queryKey]));
    expect(invalidatedKeys).toEqual(
      expect.arrayContaining([
        ["project"],
        ["project-tasks"],
        ["task-conversation"],
        ["thread"],
        ["goal"],
        ["runtime-supervisor"],
        ["project-review-status"],
      ]),
    );
  });
});
