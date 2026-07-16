import { describe, expect, it } from "vitest";

import type { TaskGraphRunRef } from "../../types";
import {
  createOptimisticTaskGraphLiveRunRef,
  isTaskGraphRunRefStale,
  selectCurrentTaskGraphRunRef,
  selectLatestTaskGraphRunRef,
} from "./taskGraphRunRefs";

function buildRunRef(overrides: Partial<TaskGraphRunRef> & Pick<TaskGraphRunRef, "run_id" | "graph_id" | "task_id" | "status" | "created_at" | "updated_at" >): TaskGraphRunRef {
  const { run_id, graph_id, task_id, status, created_at, updated_at, ...rest } = overrides;
  return {
    run_id,
    graph_id,
    task_id,
    status,
    created_at,
    updated_at,
    entry_node_ids: [],
    node_status_counts: {},
    artifact_count: 0,
    event_count: 0,
    ...rest,
  };
}

describe("selectLatestTaskGraphRunRef", () => {
  it("selects a live local run ref when query-backed sources are empty", () => {
    const liveLocal = buildRunRef({
      run_id: "run-live-local",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "paused_for_review",
      created_at: "2026-07-09T15:24:02.000000+09:00",
      updated_at: "2026-07-09T15:24:05.000000+09:00",
      approval_state: "pending",
    });

    const selected = selectLatestTaskGraphRunRef("graph-a", [[liveLocal], [], []]);

    expect(selected?.run_id).toBe("run-live-local");
    expect(selected?.status).toBe("paused_for_review");
  });

  it("prefers the newest run across multiple sources for the same graph", () => {
    const older = buildRunRef({
      run_id: "run-old",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "cancelled",
      created_at: "2026-07-07T06:35:04.458704+09:00",
      updated_at: "2026-07-07T06:38:15.678531+09:00",
    });
    const newer = buildRunRef({
      run_id: "run-new",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-07T06:41:57.507757+09:00",
      updated_at: "2026-07-07T06:41:57.507757+09:00",
    });

    const selected = selectLatestTaskGraphRunRef("graph-a", [[older], [newer]]);

    expect(selected?.run_id).toBe("run-new");
    expect(selected?.status).toBe("running");
  });

  it("deduplicates repeated run ids and keeps the freshest copy", () => {
    const stale = buildRunRef({
      run_id: "run-same",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-07T06:41:57.507757+09:00",
      updated_at: "2026-07-07T06:41:57.507757+09:00",
      artifact_count: 1,
    });
    const fresh = buildRunRef({
      run_id: "run-same",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "completed",
      created_at: "2026-07-07T06:41:57.507757+09:00",
      updated_at: "2026-07-07T06:45:00.000000+09:00",
      artifact_count: 3,
    });

    const selected = selectLatestTaskGraphRunRef("graph-a", [[stale], [fresh]]);

    expect(selected?.status).toBe("completed");
    expect(selected?.artifact_count).toBe(3);
  });

  it("merges rich worker evidence and keeps a terminal status for the same run", () => {
    const terminal = buildRunRef({
      run_id: "run-same",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "completed",
      created_at: "2026-07-13T10:00:00.000+09:00",
      updated_at: "2026-07-13T10:04:00.000+09:00",
      artifact_count: 2,
      worker_count: 1,
      worker_bindings: [
        {
          binding_id: "binding-planner",
          graph_id: "graph-a",
          run_id: "run-same",
          node_id: "node-planner",
          worker_thread_id: "thread-planner",
          status: "completed",
          artifact_refs: [],
          output_summary: { human_summary: "Planner completed." },
          created_at: "2026-07-13T10:00:01.000+09:00",
          updated_at: "2026-07-13T10:01:00.000+09:00",
        },
      ],
    });
    const staleThinRef = buildRunRef({
      run_id: "run-same",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-13T10:00:00.000+09:00",
      updated_at: "2026-07-13T10:05:00.000+09:00",
      artifact_count: 0,
      worker_count: 0,
      worker_bindings: [],
    });

    const selected = selectLatestTaskGraphRunRef("graph-a", [[terminal], [staleThinRef]]);

    expect(selected?.status).toBe("completed");
    expect(selected?.worker_count).toBe(1);
    expect(selected?.worker_bindings?.[0]?.output_summary?.human_summary).toBe(
      "Planner completed.",
    );
  });

  it("ignores runs from other graphs", () => {
    const otherGraph = buildRunRef({
      run_id: "run-other",
      graph_id: "graph-b",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-07T06:41:57.507757+09:00",
      updated_at: "2026-07-07T06:41:57.507757+09:00",
    });

    const selected = selectLatestTaskGraphRunRef("graph-a", [[otherGraph]]);

    expect(selected).toBeNull();
  });
});

describe("selectCurrentTaskGraphRunRef", () => {
  it("prefers an optimistic live ref over stale dry-run query refs for the same graph", () => {
    const staleDryRun = buildRunRef({
      run_id: "graph-dry-run-old",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "dry_run_passed",
      created_at: "2026-07-14T05:36:35.000+09:00",
      updated_at: "2026-07-14T05:36:35.000+09:00",
    });
    const optimisticLive = createOptimisticTaskGraphLiveRunRef({
      graphId: "graph-a",
      taskId: "task-a",
      entryNodeIds: ["node-planner"],
      nowIso: "2026-07-14T05:36:43.000+09:00",
    });

    const selected = selectCurrentTaskGraphRunRef({
      graphId: "graph-a",
      optimisticRunRefs: [optimisticLive],
      routeTaskRunRefs: [staleDryRun],
      currentTaskRunRefs: [staleDryRun],
      dryRunRunRef: staleDryRun,
    });

    expect(selected?.run_id).toBe(optimisticLive.run_id);
    expect(selected?.status).toBe("running");
  });

  it("suppresses an optimistic live ref until the live dispatch has actually started", () => {
    const staleDryRun = buildRunRef({
      run_id: "graph-dry-run-old",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "dry_run_passed",
      created_at: "2026-07-14T05:36:35.000+09:00",
      updated_at: "2026-07-14T05:36:35.000+09:00",
    });
    const optimisticLive = createOptimisticTaskGraphLiveRunRef({
      graphId: "graph-a",
      taskId: "task-a",
      entryNodeIds: ["node-planner"],
      nowIso: "2026-07-14T05:36:43.000+09:00",
    });

    const selected = selectCurrentTaskGraphRunRef({
      graphId: "graph-a",
      optimisticRunRefs: [optimisticLive],
      routeTaskRunRefs: [staleDryRun],
      currentTaskRunRefs: [staleDryRun],
      dryRunRunRef: staleDryRun,
      allowOptimisticActiveRunRef: false,
    });

    expect(selected?.run_id).toBe(staleDryRun.run_id);
    expect(selected?.status).toBe("dry_run_passed");
  });

  it("prefers an active live run ref over a newer dry-run record for the same graph", () => {
    const baseTime = Date.now();
    const activeCreatedAt = new Date(baseTime - 90_000).toISOString();
    const activeUpdatedAt = new Date(baseTime - 45_000).toISOString();
    const dryRunUpdatedAt = new Date(baseTime - 5_000).toISOString();
    const activeLive = buildRunRef({
      run_id: "graph-run-live-current",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: activeCreatedAt,
      updated_at: activeUpdatedAt,
    });
    const newerDryRun = buildRunRef({
      run_id: "graph-dry-run-newer",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "dry_run_passed",
      created_at: activeCreatedAt,
      updated_at: dryRunUpdatedAt,
    });

    const selected = selectCurrentTaskGraphRunRef({
      graphId: "graph-a",
      routeTaskRunRefs: [newerDryRun, activeLive],
      currentTaskRunRefs: [newerDryRun, activeLive],
      dryRunRunRef: newerDryRun,
    });

    expect(selected?.run_id).toBe("graph-run-live-current");
    expect(selected?.status).toBe("running");
  });

  it("prefers an authoritative active live run over a newer optimistic placeholder", () => {
    const optimisticLive = createOptimisticTaskGraphLiveRunRef({
      graphId: "graph-a",
      taskId: "task-a",
      entryNodeIds: ["node-planner"],
      nowIso: "2026-07-15T07:14:19.751Z",
    });
    const authoritativeLive = buildRunRef({
      run_id: "graph-run-live-20260715T071419700000-abcd12",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-15T07:14:19.100Z",
      updated_at: "2026-07-15T07:14:19.100Z",
      latest_event_type: "run_created",
    });

    const selected = selectCurrentTaskGraphRunRef({
      graphId: "graph-a",
      optimisticRunRefs: [optimisticLive],
      routeTaskRunRefs: [authoritativeLive],
    });

    expect(selected?.run_id).toBe(authoritativeLive.run_id);
    expect(selected?.status).toBe("running");
  });

  it("does not keep showing an unconfirmed cached active run after pending settles", () => {
    const cachedActive = buildRunRef({
      run_id: "graph-run-live-cached",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-15T07:14:19.100Z",
      updated_at: "2026-07-15T07:14:29.100Z",
    });

    const selected = selectCurrentTaskGraphRunRef({
      graphId: "graph-a",
      liveRunRefs: [cachedActive],
    });

    expect(selected).toBeNull();
  });

  it("keeps a cached active run only while the live run request is still pending", () => {
    const cachedActive = buildRunRef({
      run_id: "graph-run-live-cached",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-15T07:14:19.100Z",
      updated_at: "2026-07-15T07:14:29.100Z",
    });

    const selected = selectCurrentTaskGraphRunRef({
      graphId: "graph-a",
      liveRunRefs: [cachedActive],
      allowCachedActiveRunRef: true,
    });

    expect(selected?.run_id).toBe("graph-run-live-cached");
    expect(selected?.status).toBe("running");
  });

  it("still falls back to a cached terminal run when authoritative refs are absent", () => {
    const cachedFailed = buildRunRef({
      run_id: "graph-run-live-failed",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "failed",
      created_at: "2026-07-15T07:14:19.100Z",
      updated_at: "2026-07-15T07:14:39.100Z",
    });

    const selected = selectCurrentTaskGraphRunRef({
      graphId: "graph-a",
      liveRunRefs: [cachedFailed],
    });

    expect(selected?.run_id).toBe("graph-run-live-failed");
    expect(selected?.status).toBe("failed");
  });

  it("falls back to the current dry-run result when no matching live refs exist", () => {
    const dryRun = buildRunRef({
      run_id: "graph-dry-run-current",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "dry_run_blocked",
      created_at: "2026-07-14T05:36:35.000+09:00",
      updated_at: "2026-07-14T05:36:35.000+09:00",
    });

    const selected = selectCurrentTaskGraphRunRef({
      graphId: "graph-a",
      dryRunRunRef: dryRun,
    });

    expect(selected?.run_id).toBe("graph-dry-run-current");
    expect(selected?.status).toBe("dry_run_blocked");
  });
});

describe("isTaskGraphRunRefStale", () => {
  it("marks an inactive running ref stale after the bounded activity window", () => {
    const running = buildRunRef({
      run_id: "run-stale",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-13T12:00:00.000+09:00",
      updated_at: "2026-07-13T12:05:00.000+09:00",
    });

    expect(
      isTaskGraphRunRefStale(
        running,
        Date.parse("2026-07-13T12:21:00.000+09:00"),
      ),
    ).toBe(true);
  });

  it("keeps recent active refs and every terminal ref non-stale", () => {
    const recent = buildRunRef({
      run_id: "run-recent",
      graph_id: "graph-a",
      task_id: "task-a",
      status: "running",
      created_at: "2026-07-13T12:00:00.000+09:00",
      updated_at: "2026-07-13T12:10:00.000+09:00",
    });
    const terminal = { ...recent, status: "completed" };
    const now = Date.parse("2026-07-13T12:20:00.000+09:00");

    expect(isTaskGraphRunRefStale(recent, now)).toBe(false);
    expect(isTaskGraphRunRefStale(terminal, now)).toBe(false);
  });
});
