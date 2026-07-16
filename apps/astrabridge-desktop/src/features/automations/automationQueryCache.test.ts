import { describe, expect, it } from "vitest";

import type {
  AutomationInboxItem,
  AutomationInboxResponse,
  AutomationListResponse,
  AutomationRun,
  AutomationRunsResponse,
  AutomationSchedulerStatus,
  AutomationSpec,
} from "../../types";
import {
  updateAutomationSchedulerAfterRun,
  upsertAutomationInboxResponse,
  upsertAutomationListResponse,
  upsertAutomationRunsResponse,
} from "./automationQueryCache";

const automationA: AutomationSpec = {
  schema_version: "astrabridge-automation-spec-v1",
  automation_id: "auto-a",
  project_id: "demo",
  name: "Automation A",
  description: "First",
  enabled: true,
  kind: "standalone",
  prompt: "A",
  schedule: { mode: "manual", expression: "", timezone: "UTC", next_run_at: "", catch_up_policy: "skip_missed" },
  runtime: { profile_id: "deepseek-default", model: "deepseek-chat", effort: "high", permission_mode: "read-only", execution_host: "auto", mcp_preset_ids: [], plugin_skill_preset_ids: [] },
  workspace: { mode: "current_workspace", cleanup_policy: "manual", base_branch: null, worktree_root: null },
  triage: { archive_no_signal: true, notify_on: "finding", finding_keywords: [] },
  limits: { timeout_sec: 1800, max_retries: 0, max_artifact_bytes: 2000000, max_parallel_runs: 1 },
  created_at: "2026-07-15T10:00:00Z",
  updated_at: "2026-07-15T10:00:00Z",
  inbox_summary: { unread: 0, reviewed: 0, archived: 0, promoted: 0 },
};

const automationB: AutomationSpec = {
  ...automationA,
  automation_id: "auto-b",
  name: "Automation B",
  updated_at: "2026-07-15T11:00:00Z",
};

const runQueued: AutomationRun = {
  run_id: "run-queued",
  automation_id: "auto-a",
  project_id: "demo",
  trigger: "manual",
  status: "queued",
  due_at: "2026-07-15T12:00:00Z",
  started_at: null,
  finished_at: null,
  signal: "unknown",
  summary: "queued by scheduler",
  artifact_refs: [],
};

const runFailed: AutomationRun = {
  ...runQueued,
  run_id: "run-failed",
  status: "failed",
  finished_at: "2026-07-15T12:05:00Z",
  summary: "automation failed",
  redacted_error: "failed",
};

const inboxItem: AutomationInboxItem = {
  item_id: "item-1",
  run_id: "run-failed",
  automation_id: "auto-a",
  project_id: "demo",
  state: "unread",
  disposition: "finding",
  severity: "warning",
  title: "Finding",
  summary: "Something changed",
  created_at: "2026-07-15T12:05:00Z",
  updated_at: "2026-07-15T12:05:00Z",
  promotion_ref: null,
};

describe("automationQueryCache", () => {
  it("upserts automations and keeps newest first", () => {
    const current: AutomationListResponse = { automations: [automationA], count: 1 };

    const updated = upsertAutomationListResponse(current, automationB);
    expect(updated.automations.map((item) => item.automation_id)).toEqual(["auto-b", "auto-a"]);
    expect(updated.count).toBe(2);

    const replacement = upsertAutomationListResponse(updated, { ...automationA, updated_at: "2026-07-15T13:00:00Z" });
    expect(replacement.automations.map((item) => item.automation_id)).toEqual(["auto-a", "auto-b"]);
    expect(replacement.count).toBe(2);
  });

  it("upserts runs and keeps newest first", () => {
    const current: AutomationRunsResponse = { runs: [{ ...runQueued, run_id: "run-old", due_at: "2026-07-15T10:00:00Z" }], count: 1 };
    const updated = upsertAutomationRunsResponse(current, runQueued);
    expect(updated.runs.map((item) => item.run_id)).toEqual(["run-queued", "run-old"]);
    expect(updated.count).toBe(2);
  });

  it("upserts inbox items and keeps latest first", () => {
    const current: AutomationInboxResponse = {
      items: [{ ...inboxItem, item_id: "item-0", updated_at: "2026-07-15T09:00:00Z" }],
      count: 1,
    };
    const updated = upsertAutomationInboxResponse(current, inboxItem);
    expect(updated.items.map((item) => item.item_id)).toEqual(["item-1", "item-0"]);
    expect(updated.count).toBe(2);
  });

  it("projects run state into scheduler status", () => {
    const current: AutomationSchedulerStatus = {
      running: true,
      active_run_count: 0,
      next_wake_up_at: null,
      active_runs: [],
      last_failure: null,
      next_due: null,
      inbox_summary: { unread: 0, reviewed: 0, archived: 0, promoted: 0 },
    };

    const queued = updateAutomationSchedulerAfterRun(current, runQueued);
    expect(queued.active_run_count).toBe(1);
    expect(queued.active_runs?.[0]).toMatchObject({ run_id: "run-queued", status: "queued" });

    const failed = updateAutomationSchedulerAfterRun(queued, runFailed);
    expect(failed.active_run_count).toBe(1);
    expect(failed.active_runs?.[0]).toMatchObject({ run_id: "run-queued", status: "queued" });
    expect(failed.last_failure?.run_id).toBe("run-failed");
  });
});
