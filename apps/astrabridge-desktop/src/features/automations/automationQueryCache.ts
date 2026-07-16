import type {
  AutomationInboxItem,
  AutomationInboxResponse,
  AutomationListResponse,
  AutomationRun,
  AutomationRunsResponse,
  AutomationSchedulerStatus,
  AutomationSpec,
} from "../../types";

function sortAutomations(records: AutomationSpec[]) {
  return [...records].sort((left, right) => String(right.updated_at || "").localeCompare(String(left.updated_at || "")));
}

function sortRuns(records: AutomationRun[]) {
  return [...records].sort((left, right) => {
    const leftKey = String(left.due_at || left.started_at || left.finished_at || "");
    const rightKey = String(right.due_at || right.started_at || right.finished_at || "");
    return rightKey.localeCompare(leftKey);
  });
}

function sortInboxItems(records: AutomationInboxItem[]) {
  return [...records].sort((left, right) => {
    const leftKey = String(left.updated_at || left.created_at || "");
    const rightKey = String(right.updated_at || right.created_at || "");
    return rightKey.localeCompare(leftKey);
  });
}

export function upsertAutomationListResponse(
  current: AutomationListResponse | undefined,
  automation: AutomationSpec,
): AutomationListResponse {
  const nextAutomations = sortAutomations(
    [
      ...(automation.archived_at ? [] : [automation]),
      ...(current?.automations ?? []).filter((item) => item.automation_id !== automation.automation_id),
    ].filter((item) => !item.archived_at),
  );
  return {
    automations: nextAutomations,
    count: nextAutomations.length,
  };
}

export function upsertAutomationRunsResponse(
  current: AutomationRunsResponse | undefined,
  run: AutomationRun,
): AutomationRunsResponse {
  const nextRuns = sortRuns([run, ...(current?.runs ?? []).filter((item) => item.run_id !== run.run_id)]);
  return {
    runs: nextRuns,
    count: nextRuns.length,
  };
}

export function upsertAutomationInboxResponse(
  current: AutomationInboxResponse | undefined,
  item: AutomationInboxItem,
): AutomationInboxResponse {
  const nextItems = sortInboxItems([item, ...(current?.items ?? []).filter((entry) => entry.item_id !== item.item_id)]);
  return {
    items: nextItems,
    count: nextItems.length,
  };
}

export function updateAutomationSchedulerAfterRun(
  current: AutomationSchedulerStatus | undefined,
  run: AutomationRun,
): AutomationSchedulerStatus {
  const existingActiveRuns = Array.isArray(current?.active_runs) ? current.active_runs : [];
  const activeStatuses = new Set(["queued", "running", "needs_review"]);
  const nextActiveRuns = existingActiveRuns.filter((item) => item.run_id !== run.run_id);
  if (activeStatuses.has(run.status)) {
    nextActiveRuns.unshift({
      run_id: run.run_id,
      automation_id: run.automation_id,
      status: run.status,
      due_at: run.due_at ?? null,
    });
  }
  return {
    running: current?.running ?? true,
    active_run_count: nextActiveRuns.length,
    next_wake_up_at: current?.next_wake_up_at ?? null,
    active_runs: nextActiveRuns.slice(0, 10),
    last_failure:
      run.status === "failed" || run.status === "cancelled"
        ? run
        : current?.last_failure ?? null,
    next_due: current?.next_due ?? null,
    inbox_summary: current?.inbox_summary ?? { unread: 0, reviewed: 0, archived: 0, promoted: 0 },
  };
}
