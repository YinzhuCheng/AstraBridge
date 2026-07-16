import type { TaskGraphRunRef } from "../../types";

export const OPTIMISTIC_TASK_GRAPH_RUN_ID_PREFIX = "optimistic-live:";

function runRefTimestamp(value: TaskGraphRunRef): number {
  const updatedAt = Date.parse(value.updated_at ?? "");
  if (Number.isFinite(updatedAt)) return updatedAt;
  const createdAt = Date.parse(value.created_at ?? "");
  if (Number.isFinite(createdAt)) return createdAt;
  return Number.NEGATIVE_INFINITY;
}

const ACTIVE_RUN_STATUSES = new Set(["queued", "running", "paused_for_review"]);
const TERMINAL_RUN_STATUSES = new Set([
  "completed",
  "failed",
  "cancelled",
  "partial",
  "dry_run_passed",
  "dry_run_blocked",
]);
export const TASK_GRAPH_RUN_STALE_AFTER_MS = 15 * 60 * 1000;

function runRefStatus(value: TaskGraphRunRef | null | undefined): string {
  return String(value?.status ?? "").trim();
}

function isDryRunRunRef(value: TaskGraphRunRef | null | undefined): boolean {
  return runRefStatus(value).startsWith("dry_run");
}

function mergeCountMap(
  left: Record<string, number> | undefined,
  right: Record<string, number> | undefined,
): Record<string, number> {
  const merged = { ...(left ?? {}) };
  for (const [key, value] of Object.entries(right ?? {})) {
    merged[key] = Math.max(Number(merged[key] ?? 0), Number(value ?? 0));
  }
  return merged;
}

function mergeObjectArray<T extends Record<string, unknown>>(
  preferred: readonly T[] | null | undefined,
  fallback: readonly T[] | null | undefined,
  keyFor: (value: T) => string,
): T[] {
  const merged = new Map<string, T>();
  for (const item of fallback ?? []) {
    const key = keyFor(item);
    if (key) merged.set(key, item);
  }
  for (const item of preferred ?? []) {
    const key = keyFor(item);
    if (!key) continue;
    merged.set(key, { ...(merged.get(key) ?? {}), ...item } as T);
  }
  return [...merged.values()];
}

function mergeRunRefs(left: TaskGraphRunRef, right: TaskGraphRunRef): TaskGraphRunRef {
  const leftTerminal = TERMINAL_RUN_STATUSES.has(String(left.status ?? "").trim());
  const rightTerminal = TERMINAL_RUN_STATUSES.has(String(right.status ?? "").trim());
  const rightPreferred = rightTerminal !== leftTerminal
    ? rightTerminal
    : runRefTimestamp(right) >= runRefTimestamp(left);
  const preferred = rightPreferred ? right : left;
  const fallback = rightPreferred ? left : right;
  const workerBindings = mergeObjectArray(
    preferred.worker_bindings,
    fallback.worker_bindings,
    (item) => String(item.binding_id ?? item.node_id ?? "").trim(),
  );
  const artifactRefs = mergeObjectArray(
    preferred.artifact_refs,
    fallback.artifact_refs,
    (item) => `${String(item.artifact_id ?? "").trim()}|${String(item.path ?? "").trim()}`,
  );
  const timelineEvents = mergeObjectArray(
    preferred.timeline_events,
    fallback.timeline_events,
    (item) => String(item.event_id ?? "").trim(),
  ).sort((a, b) => Date.parse(String(a.created_at ?? "")) - Date.parse(String(b.created_at ?? "")));
  const diagnosticRefs = mergeObjectArray(
    preferred.diagnostic_refs,
    fallback.diagnostic_refs,
    (item) => `${String(item.artifact_id ?? "").trim()}|${String(item.path ?? "").trim()}`,
  );
  return {
    ...fallback,
    ...preferred,
    node_status_counts: mergeCountMap(fallback.node_status_counts, preferred.node_status_counts),
    node_outcome_counts: mergeCountMap(fallback.node_outcome_counts, preferred.node_outcome_counts),
    artifact_refs: artifactRefs,
    timeline_events: timelineEvents,
    diagnostic_refs: diagnosticRefs,
    worker_bindings: workerBindings,
    worker_count: Math.max(
      Number(fallback.worker_count ?? 0),
      Number(preferred.worker_count ?? 0),
      workerBindings.length,
    ),
    artifact_count: Math.max(
      Number(fallback.artifact_count ?? 0),
      Number(preferred.artifact_count ?? 0),
      artifactRefs.length,
    ),
    event_count: Math.max(
      Number(fallback.event_count ?? 0),
      Number(preferred.event_count ?? 0),
      timelineEvents.length,
    ),
    metrics: preferred.metrics ?? fallback.metrics ?? null,
    budget: preferred.budget ?? fallback.budget ?? null,
  };
}

export function isTaskGraphRunRefStale(
  value: TaskGraphRunRef | null | undefined,
  nowMs = Date.now(),
  staleAfterMs = TASK_GRAPH_RUN_STALE_AFTER_MS,
): boolean {
  if (!value || !ACTIVE_RUN_STATUSES.has(String(value.status ?? "").trim())) return false;
  const timestamp = runRefTimestamp(value);
  if (!Number.isFinite(timestamp)) return true;
  return nowMs - timestamp >= staleAfterMs;
}

export function selectLatestTaskGraphRunRef(
  graphId: string | null | undefined,
  sources: Array<readonly TaskGraphRunRef[] | null | undefined>,
): TaskGraphRunRef | null {
  const normalizedGraphId = String(graphId ?? "").trim();
  if (!normalizedGraphId) return null;
  const deduped = new Map<string, TaskGraphRunRef>();
  for (const source of sources) {
    for (const item of source ?? []) {
      if (!item || String(item.graph_id ?? "").trim() !== normalizedGraphId) continue;
      const runId = String(item.run_id ?? "").trim();
      if (!runId) continue;
      const existing = deduped.get(runId);
      deduped.set(runId, existing ? mergeRunRefs(existing, item) : item);
    }
  }
  const candidates = [...deduped.values()];
  if (!candidates.length) return null;
  candidates.sort((left, right) => {
    const delta = runRefTimestamp(right) - runRefTimestamp(left);
    if (delta !== 0) return delta;
    return String(right.run_id ?? "").localeCompare(String(left.run_id ?? ""));
  });
  return candidates[0] ?? null;
}

export function selectCurrentTaskGraphRunRef({
  graphId,
  optimisticRunRefs,
  liveRunRefs,
  routeTaskRunRefs,
  currentTaskRunRefs,
  dryRunRunRef,
  allowCachedActiveRunRef = false,
  allowOptimisticActiveRunRef = true,
}: {
  graphId: string | null | undefined;
  optimisticRunRefs?: readonly TaskGraphRunRef[] | null | undefined;
  liveRunRefs?: readonly TaskGraphRunRef[] | null | undefined;
  routeTaskRunRefs?: readonly TaskGraphRunRef[] | null | undefined;
  currentTaskRunRefs?: readonly TaskGraphRunRef[] | null | undefined;
  dryRunRunRef?: TaskGraphRunRef | null | undefined;
  allowCachedActiveRunRef?: boolean;
  allowOptimisticActiveRunRef?: boolean;
}): TaskGraphRunRef | null {
  const normalizedGraphId = String(graphId ?? "").trim();
  if (!normalizedGraphId) {
    return dryRunRunRef ?? null;
  }
  const authoritativeActiveLiveMatching = selectLatestTaskGraphRunRef(normalizedGraphId, [
    (routeTaskRunRefs ?? []).filter(
      (item) =>
        item &&
        !isDryRunRunRef(item) &&
        ACTIVE_RUN_STATUSES.has(runRefStatus(item)) &&
        !isTaskGraphRunRefStale(item),
    ),
    (currentTaskRunRefs ?? []).filter(
      (item) =>
        item &&
        !isDryRunRunRef(item) &&
        ACTIVE_RUN_STATUSES.has(runRefStatus(item)) &&
        !isTaskGraphRunRefStale(item),
    ),
  ]);
  if (authoritativeActiveLiveMatching) return authoritativeActiveLiveMatching;
  const optimisticActiveLiveMatching = selectLatestTaskGraphRunRef(normalizedGraphId, [
    (optimisticRunRefs ?? []).filter(
      (item) => item && !isDryRunRunRef(item) && !isTaskGraphRunRefStale(item),
    ),
  ]);
  if (optimisticActiveLiveMatching && allowOptimisticActiveRunRef) {
    return optimisticActiveLiveMatching;
  }
  const cachedActiveLiveMatching = selectLatestTaskGraphRunRef(normalizedGraphId, [
    (liveRunRefs ?? []).filter(
      (item) =>
        item &&
        !isDryRunRunRef(item) &&
        ACTIVE_RUN_STATUSES.has(runRefStatus(item)) &&
        (allowCachedActiveRunRef || !isTaskGraphRunRefStale(item)),
    ),
  ]);
  if (cachedActiveLiveMatching && allowCachedActiveRunRef) {
    return cachedActiveLiveMatching;
  }
  const authoritativeMatching = selectLatestTaskGraphRunRef(normalizedGraphId, [
    (routeTaskRunRefs ?? []).filter((item) => item && !isDryRunRunRef(item)),
    (currentTaskRunRefs ?? []).filter((item) => item && !isDryRunRunRef(item)),
  ]);
  if (authoritativeMatching) return authoritativeMatching;
  const cachedMatching = selectLatestTaskGraphRunRef(normalizedGraphId, [
    (liveRunRefs ?? []).filter(
      (item) =>
        item &&
        !isDryRunRunRef(item) &&
        !ACTIVE_RUN_STATUSES.has(runRefStatus(item)),
    ),
  ]);
  if (cachedMatching) return cachedMatching;
  const matching = selectLatestTaskGraphRunRef(normalizedGraphId, [
    optimisticRunRefs,
  ]);
  if (matching && allowOptimisticActiveRunRef) return matching;
  return dryRunRunRef?.graph_id === normalizedGraphId ? dryRunRunRef : null;
}

export function createOptimisticTaskGraphLiveRunRef({
  graphId,
  taskId,
  entryNodeIds,
  budget,
  templateId,
  nowIso = new Date().toISOString(),
}: {
  graphId: string;
  taskId: string;
  entryNodeIds?: readonly string[] | null | undefined;
  budget?: TaskGraphRunRef["budget"];
  templateId?: string | null | undefined;
  nowIso?: string;
}): TaskGraphRunRef {
  return {
    run_id: `${OPTIMISTIC_TASK_GRAPH_RUN_ID_PREFIX}${graphId}:${nowIso}`,
    graph_id: graphId,
    task_id: taskId,
    status: "running",
    created_at: nowIso,
    updated_at: nowIso,
    entry_node_ids: [...(entryNodeIds ?? [])],
    node_status_counts: { queued: Math.max(1, (entryNodeIds ?? []).length || 1) },
    artifact_count: 0,
    event_count: 0,
    latest_event_type: "graph_run_requested",
    latest_event_at: nowIso,
    policy_snapshot: {
      execution_mode: "live",
      template_id: String(templateId ?? "").trim() || null,
      budget: budget ?? null,
    },
    budget: budget ?? null,
    worker_count: 0,
    worker_bindings: [],
    artifact_refs: [],
    timeline_events: [],
    diagnostic_refs: [],
  };
}
