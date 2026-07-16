import { describe, expect, it } from "vitest";

import { visibleTaskTitle, visibleThreadTitle } from "./displayTitle";

describe("displayTitle", () => {
  it("strips smoke source prefixes from task titles", () => {
    expect(visibleTaskTitle("Step 11 source for compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run")).toBe(
      "compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run",
    );
  });

  it("strips smoke target prefixes from thread titles", () => {
    expect(visibleThreadTitle("Step 12 target for compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run")).toBe(
      "compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run",
    );
  });

  it("keeps ordinary titles unchanged", () => {
    expect(visibleTaskTitle("DG Multimodal UI 01 Recovery 10")).toBe("DG Multimodal UI 01 Recovery 10");
  });
});
