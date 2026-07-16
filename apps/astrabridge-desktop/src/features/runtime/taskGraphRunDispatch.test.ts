import { describe, expect, it } from "vitest";

import {
  hasTaskGraphLiveDispatchTimedOut,
  resolveTaskGraphRunPrecondition,
  shouldPromoteDryRunToLiveRun,
  type TaskGraphRequestedRunIntent,
} from "./taskGraphRunDispatch";

function liveIntent(
  overrides: Partial<TaskGraphRequestedRunIntent> = {},
): TaskGraphRequestedRunIntent {
  return {
    kind: "live",
    graphId: "graph-1",
    tokenBudget: 80_000,
    fallbackTriggered: false,
    ...overrides,
  };
}

describe("shouldPromoteDryRunToLiveRun", () => {
  it("promotes a successful dry-run back into a live run when the current intent is live", () => {
    expect(
      shouldPromoteDryRunToLiveRun({
        intent: liveIntent(),
        dryRunGraphId: "graph-1",
        dryRunOverallStatus: "pass",
        liveRunPending: false,
      }),
    ).toEqual({ graphId: "graph-1", tokenBudget: 80_000 });
  });

  it("does not promote a user-requested dry-run", () => {
    expect(
      shouldPromoteDryRunToLiveRun({
        intent: {
          kind: "dry_run",
          graphId: "graph-1",
          tokenBudget: 80_000,
          fallbackTriggered: false,
        },
        dryRunGraphId: "graph-1",
        dryRunOverallStatus: "pass",
        liveRunPending: false,
      }),
    ).toBeNull();
  });

  it("does not promote if the dry-run was for a different graph", () => {
    expect(
      shouldPromoteDryRunToLiveRun({
        intent: liveIntent(),
        dryRunGraphId: "graph-2",
        dryRunOverallStatus: "pass",
        liveRunPending: false,
      }),
    ).toBeNull();
  });

  it("does not promote blocked dry-runs or duplicate fallback dispatches", () => {
    expect(
      shouldPromoteDryRunToLiveRun({
        intent: liveIntent(),
        dryRunGraphId: "graph-1",
        dryRunOverallStatus: "blocked",
        liveRunPending: false,
      }),
    ).toBeNull();
    expect(
      shouldPromoteDryRunToLiveRun({
        intent: liveIntent({ fallbackTriggered: true }),
        dryRunGraphId: "graph-1",
        dryRunOverallStatus: "pass",
        liveRunPending: false,
      }),
    ).toBeNull();
  });
});

describe("resolveTaskGraphRunPrecondition", () => {
  it("blocks runs when the graph is still missing", () => {
    expect(
      resolveTaskGraphRunPrecondition({
        actionLabel: "Live run",
        currentTaskGraph: null,
        graphId: null,
        routeUnavailable: false,
      }),
    ).toContain("Live run");
  });

  it("blocks runs when the runtime route is unavailable", () => {
    expect(
      resolveTaskGraphRunPrecondition({
        actionLabel: "Dry-run",
        currentTaskGraph: { graph_id: "graph-1" } as never,
        graphId: "graph-1",
        routeUnavailable: true,
      }),
    ).toContain("sidecar");
  });

  it("blocks runs when the graph id is missing", () => {
    expect(
      resolveTaskGraphRunPrecondition({
        actionLabel: "Fixture run",
        currentTaskGraph: {} as never,
        graphId: "",
        routeUnavailable: false,
      }),
    ).toContain("graph id");
  });

  it("returns null when the run preconditions are satisfied", () => {
    expect(
      resolveTaskGraphRunPrecondition({
        actionLabel: "Live run",
        currentTaskGraph: { graph_id: "graph-1" } as never,
        graphId: "graph-1",
        routeUnavailable: false,
      }),
    ).toBeNull();
  });
});

describe("hasTaskGraphLiveDispatchTimedOut", () => {
  it("times out an unconfirmed live dispatch after the bounded window", () => {
    expect(
      hasTaskGraphLiveDispatchTimedOut({
        intent: liveIntent(),
        optimisticRunCreatedAt: "2026-07-15T11:00:00.000Z",
        hasAuthoritativeActiveRun: false,
        timeoutMs: 4_000,
        nowMs: Date.parse("2026-07-15T11:00:04.001Z"),
      }),
    ).toBe(true);
  });

  it("stays pending while still inside the confirmation window", () => {
    expect(
      hasTaskGraphLiveDispatchTimedOut({
        intent: liveIntent(),
        optimisticRunCreatedAt: "2026-07-15T11:00:00.000Z",
        hasAuthoritativeActiveRun: false,
        timeoutMs: 4_000,
        nowMs: Date.parse("2026-07-15T11:00:03.999Z"),
      }),
    ).toBe(false);
  });

  it("does not time out once an authoritative active run exists", () => {
    expect(
      hasTaskGraphLiveDispatchTimedOut({
        intent: liveIntent(),
        optimisticRunCreatedAt: "2026-07-15T11:00:00.000Z",
        hasAuthoritativeActiveRun: true,
        timeoutMs: 4_000,
        nowMs: Date.parse("2026-07-15T11:00:10.000Z"),
      }),
    ).toBe(false);
  });
});
