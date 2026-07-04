import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AutomationInboxItem, AutomationRun, AutomationSpec, Profile } from "../../types";
import { AutomationsPanel, automationPayloadFromDraft, createEmptyAutomationDraft } from "./AutomationsPanel";

const profile: Profile = {
  profile_id: "qwen-default",
  label: "Qwen",
  type: "custom_provider",
  provider_id: "qwen",
  model: "qwen3.7-plus",
  reasoning_effort: "high",
  wire_api: "chat",
  env_key: "DASHSCOPE_API_KEY",
  auth_mode: "env_ref",
  proxy_mode: "direct",
  proxy_url: "",
};

const automation: AutomationSpec = {
  schema_version: "astrabridge-automation-spec-v1",
  automation_id: "auto-1",
  project_id: "demo",
  name: "Daily audit",
  description: "Checks the repo",
  enabled: true,
  kind: "standalone",
  prompt: "Audit the repo for TODOs",
  schedule: { mode: "interval", expression: "every:30m", timezone: "Asia/Shanghai", next_run_at: "2026-06-24T12:00:00Z", catch_up_policy: "skip_missed" },
  runtime: { profile_id: "qwen-default", model: "qwen3.7-plus", effort: "high", permission_mode: "workspace-write", execution_host: "auto", mcp_preset_ids: [], plugin_skill_preset_ids: [] },
  workspace: { mode: "dedicated_worktree", cleanup_policy: "keep_on_finding", base_branch: "main", worktree_root: null },
  triage: { archive_no_signal: true, notify_on: "finding", finding_keywords: ["todo"] },
  limits: { timeout_sec: 1800, max_retries: 0, max_artifact_bytes: 2_000_000, max_parallel_runs: 1 },
  created_at: "2026-06-24T00:00:00Z",
  updated_at: "2026-06-24T00:00:00Z",
  last_run_at: "2026-06-24T00:30:00Z",
  last_status: "completed",
  inbox_summary: { unread: 1, reviewed: 0, archived: 0, promoted: 0 },
};

const run: AutomationRun = {
  run_id: "run-1",
  automation_id: "auto-1",
  project_id: "demo",
  trigger: "manual",
  status: "completed",
  due_at: "2026-06-24T00:30:00Z",
  started_at: "2026-06-24T00:30:00Z",
  finished_at: "2026-06-24T00:31:00Z",
  signal: "finding",
  summary: "Found TODO in src/App.tsx",
  artifact_refs: ["D:\\AstraBridge\\.astrabridge\\automations\\runs\\run-1\\summary.json"],
};

const failedRun: AutomationRun = {
  ...run,
  run_id: "run-failed",
  status: "failed",
  signal: "unknown",
  summary: "Automation run failed before execution completed.",
  redacted_error: "dirty workspace blocks execution",
  stderr_excerpt: "workspace blocked",
};

const recoveredRun: AutomationRun = {
  ...run,
  run_id: "run-recovered",
  status: "failed",
  signal: "unknown",
  summary: "Automation run was interrupted before it wrote a final result.",
  redacted_error: "automation_runner_interrupted_after_service_restart",
  artifact_refs: ["D:\\AstraBridge\\.astrabridge\\automations\\runs\\run-recovered\\manifest.json"],
  watchdog_reason: "service_restart_interrupted",
  watchdog_summary: "AstraBridge found this run still marked active after the automation worker stopped, so it recovered the run into a reviewable failure.",
  recovered_by: "service_restart",
  recovered_at: "2026-06-24T00:31:30Z",
};

const staleRecoveredRun: AutomationRun = {
  ...run,
  run_id: "run-stale",
  status: "failed",
  signal: "unknown",
  summary: "Automation watchdog recovered a stale running run after the timeout window.",
  redacted_error: "automation_watchdog_stale_running_timeout",
  artifact_refs: ["D:\\AstraBridge\\.astrabridge\\automations\\runs\\run-stale\\manifest.json"],
  next_retry_at: "2026-06-24T01:00:00Z",
  watchdog_reason: "stale_running_timeout",
  watchdog_summary: "No final result was recorded within 1800 seconds, so the scheduler recovered the run for review.",
  recovered_by: "scheduler_watchdog",
  recovered_at: "2026-06-24T00:31:20Z",
};

const cancelledRun: AutomationRun = {
  ...run,
  run_id: "run-cancelled",
  status: "cancelled",
  signal: "unknown",
  summary: "queued by scheduler",
  redacted_error: "cancelled_by_user",
  artifact_refs: ["D:\\AstraBridge\\.astrabridge\\automations\\runs\\run-cancelled\\manifest.json"],
};

const runningRun: AutomationRun = {
  ...run,
  run_id: "run-active",
  status: "running",
  signal: "unknown",
  summary: "Automation run started",
};

const noSignalRun: AutomationRun = {
  ...run,
  run_id: "run-no-signal",
  signal: "no_signal",
  summary: "Repository clean.",
  artifact_refs: ["D:\\AstraBridge\\.astrabridge\\automations\\auto-1\\run-no-signal\\manifest.json"],
};

const noInboxRun: AutomationRun = {
  ...run,
  run_id: "run-no-inbox",
  signal: "no_signal",
  summary: "No issues found and no inbox item was requested.",
  artifact_refs: ["D:\\AstraBridge\\.astrabridge\\automations\\auto-1\\run-no-inbox\\manifest.json"],
};

const inboxItem: AutomationInboxItem = {
  item_id: "item-1",
  run_id: "run-1",
  automation_id: "auto-1",
  project_id: "demo",
  state: "unread",
  disposition: "finding",
  severity: "warning",
  title: "TODO found",
  summary: "A TODO marker is still present.",
  created_at: "2026-06-24T00:31:00Z",
  updated_at: "2026-06-24T00:31:00Z",
  promotion_ref: null,
};

const archivedNoSignalInboxItem: AutomationInboxItem = {
  ...inboxItem,
  item_id: "item-no-signal",
  run_id: "run-no-signal",
  state: "archived",
  disposition: "no_signal",
  severity: "info",
  title: "Repository clean",
  summary: "No follow-up needed.",
};

describe("AutomationsPanel", () => {
  afterEach(() => cleanup());

  it("builds manual and interval payloads with normalized nested fields", () => {
    const draft = createEmptyAutomationDraft("demo", [profile]);
    const manualPayload = automationPayloadFromDraft("demo", {
      ...draft,
      automation_id: "auto-manual",
      name: "Manual check",
      prompt: "Review recent changes",
      mcp_preset_ids: "astrabridge_web, astrabridge_capabilities",
      plugin_skill_preset_ids: "project-default, nightly-audit",
      finding_keywords: "todo, flaky",
    });

    expect(manualPayload).toMatchObject({
      automation_id: "auto-manual",
      project_id: "demo",
      schedule: { mode: "manual" },
      runtime: {
        profile_id: "qwen-default",
        permission_mode: "workspace-write",
        mcp_preset_ids: ["astrabridge_web", "astrabridge_capabilities"],
        plugin_skill_preset_ids: ["project-default", "nightly-audit"],
      },
      triage: { finding_keywords: ["todo", "flaky"] },
    });

    const intervalPayload = automationPayloadFromDraft("demo", {
      ...draft,
      automation_id: "auto-interval",
      name: "Interval check",
      prompt: "Watch the repo",
      schedule_mode: "interval",
      interval_minutes: 15,
      permission_mode: "full-access",
      dangerous_opt_in: true,
    });

    expect(intervalPayload).toMatchObject({
      schedule: { mode: "interval", interval_minutes: 15, timezone: expect.any(String) },
      runtime: { permission_mode: "full-access", dangerous_opt_in: true },
    });
  });

  it("renders automation data and routes actions through callbacks", () => {
    const onRunNow = vi.fn();
    const onMarkReviewed = vi.fn();
    const onPromote = vi.fn();

    render(
      <AutomationsPanel
        locale="en"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[run]}
        inboxItems={[inboxItem]}
        scheduler={{ running: true, active_run_count: 0, next_wake_up_at: null, inbox_summary: { unread: 1, reviewed: 0, archived: 0, promoted: 0 } }}
        supervisorAutomations={null}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={onRunNow}
        onCancelRun={vi.fn()}
        onMarkReviewed={onMarkReviewed}
        onArchive={vi.fn()}
        onPromote={onPromote}
      />,
    );

    expect(screen.getByText("Daily audit")).toBeInTheDocument();
    expect(screen.getByText("TODO found")).toBeInTheDocument();
    expect(screen.getByText("Found TODO in src/App.tsx")).toBeInTheDocument();
    expect(screen.getByTestId("automation-run-finalization")).toHaveTextContent("Review item created");
    expect(screen.getAllByText(/run-1 \/ summary\.json/)).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Run now" }));
    expect(onRunNow).toHaveBeenCalledWith("auto-1");

    fireEvent.click(screen.getByRole("button", { name: "Mark reviewed" }));
    expect(onMarkReviewed).toHaveBeenCalledWith("item-1");

    fireEvent.change(screen.getByLabelText("Promotion reference"), { target: { value: "task:123" } });
    fireEvent.click(screen.getByRole("button", { name: "Promote" }));
    expect(onPromote).toHaveBeenCalledWith("item-1", "task:123");
  });

  it("selects MCP and project plugin-skill presets through controlled chips", () => {
    const onUpdate = vi.fn();

    render(
      <AutomationsPanel
        locale="en"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[]}
        inboxItems={[]}
        scheduler={{ running: true, active_run_count: 0, next_wake_up_at: null, inbox_summary: { unread: 0, reviewed: 0, archived: 0, promoted: 0 } }}
        supervisorAutomations={null}
        mcpPresetOptions={[
          {
            preset_id: "astrabridge_capabilities",
            label: "AstraBridge Capability Runtime",
            description: "Multimodal routes for image, vision, and speech.",
            configured: true,
          },
        ]}
        pluginSkillPresetOptions={[
          {
            preset_id: "project-default",
            label: "Project default",
            plugin_count: 1,
            skill_count: 2,
            active: true,
          },
        ]}
        onCreate={vi.fn()}
        onUpdate={onUpdate}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={vi.fn()}
        onCancelRun={vi.fn()}
        onMarkReviewed={vi.fn()}
        onArchive={vi.fn()}
        onPromote={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /AstraBridge Capability Runtime/ }));
    fireEvent.click(screen.getByRole("button", { name: /Project default/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onUpdate).toHaveBeenCalledWith(
      "auto-1",
      expect.objectContaining({
        runtime: expect.objectContaining({
          mcp_preset_ids: ["astrabridge_capabilities"],
          plugin_skill_preset_ids: ["project-default"],
        }),
      }),
    );
  });

  it("renders localized failure review details and mutation errors", () => {
    render(
      <AutomationsPanel
        locale="zh-CN"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[failedRun]}
        inboxItems={[
          {
            ...inboxItem,
            item_id: "item-failure",
            run_id: "run-failed",
            state: "reviewed",
            disposition: "failure",
            severity: "error",
            title: "巡检失败",
            summary: "工作区阻止执行。",
          },
        ]}
        scheduler={{ running: true, active_run_count: 0, next_wake_up_at: null, inbox_summary: { unread: 0, reviewed: 1, archived: 0, promoted: 0 } }}
        supervisorAutomations={null}
        errorMessage="无法继续运行该自动化。"
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={vi.fn()}
        onCancelRun={vi.fn()}
        onMarkReviewed={vi.fn()}
        onArchive={vi.fn()}
        onPromote={vi.fn()}
      />,
    );

    expect(screen.getByTestId("automation-error-message")).toHaveTextContent("自动化操作失败");
    expect(screen.getByTestId("automation-error-message")).toHaveTextContent("无法继续运行该自动化。");
    expect(screen.getAllByText("失败").length).toBeGreaterThan(0);
    expect(screen.getByText("未知")).toBeInTheDocument();
    expect(screen.getByText("dirty workspace blocks execution")).toBeInTheDocument();
    expect(screen.getByText("工作区阻止执行。")).toBeInTheDocument();
  });

  it("explains archived no-signal finalization with the linked inbox state", () => {
    render(
      <AutomationsPanel
        locale="en"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[noSignalRun]}
        inboxItems={[archivedNoSignalInboxItem]}
        scheduler={{ running: true, active_run_count: 0, next_wake_up_at: null, inbox_summary: { unread: 0, reviewed: 0, archived: 1, promoted: 0 } }}
        supervisorAutomations={null}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={vi.fn()}
        onCancelRun={vi.fn()}
        onMarkReviewed={vi.fn()}
        onArchive={vi.fn()}
        onPromote={vi.fn()}
      />,
    );

    const finalization = screen.getByTestId("automation-run-finalization");
    expect(finalization).toHaveTextContent("Archived automatically");
    expect(finalization).toHaveTextContent("archived the no-signal inbox item automatically");
    expect(screen.getByText(/Repository clean .* No signal \/ Archived/)).toBeInTheDocument();
    expect(screen.getAllByText(/run-no-signal \/ manifest\.json/)).toHaveLength(2);
  });

  it("explains completed runs that finalized without creating an inbox item", () => {
    render(
      <AutomationsPanel
        locale="en"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[noInboxRun]}
        inboxItems={[]}
        scheduler={{ running: true, active_run_count: 0, next_wake_up_at: null, inbox_summary: { unread: 0, reviewed: 0, archived: 0, promoted: 0 } }}
        supervisorAutomations={null}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={vi.fn()}
        onCancelRun={vi.fn()}
        onMarkReviewed={vi.fn()}
        onArchive={vi.fn()}
        onPromote={vi.fn()}
      />,
    );

    expect(screen.getByTestId("automation-run-finalization")).toHaveTextContent("No inbox item created");
    expect(screen.getAllByText(/run-no-inbox \/ manifest\.json/)).toHaveLength(2);
  });

  it("allows cancelling an active run from the run detail view", () => {
    const onCancelRun = vi.fn();

    render(
      <AutomationsPanel
        locale="en"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[runningRun]}
        inboxItems={[]}
        scheduler={{ running: true, active_run_count: 1, next_wake_up_at: null, inbox_summary: { unread: 0, reviewed: 0, archived: 0, promoted: 0 } }}
        supervisorAutomations={null}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={vi.fn()}
        onCancelRun={onCancelRun}
        onMarkReviewed={vi.fn()}
        onArchive={vi.fn()}
        onPromote={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Cancel run" }));
    expect(onCancelRun).toHaveBeenCalledWith("run-active");
  });

  it("explains recovered interrupted runs without exposing only an internal code", () => {
    render(
      <AutomationsPanel
        locale="en"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[recoveredRun]}
        inboxItems={[]}
        scheduler={{ running: true, active_run_count: 0, next_wake_up_at: null, inbox_summary: { unread: 0, reviewed: 0, archived: 0, promoted: 0 } }}
        supervisorAutomations={null}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={vi.fn()}
        onCancelRun={vi.fn()}
        onMarkReviewed={vi.fn()}
        onArchive={vi.fn()}
        onPromote={vi.fn()}
      />,
    );

    const diagnostic = screen.getByTestId("automation-run-diagnostic");
    expect(diagnostic).toHaveTextContent("Run recovered");
    expect(diagnostic).toHaveTextContent("recovered the run into a reviewable failure");
    expect(diagnostic).toHaveTextContent("automation_runner_interrupted_after_service_restart");
    expect(screen.getByText("Recovery")).toBeInTheDocument();
    expect(screen.getByText("Next retry")).toBeInTheDocument();
    expect(screen.getAllByText("None").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/manifest\.json/).length).toBeGreaterThan(0);
  });

  it("explains watchdog-recovered stale runs and keeps retry timing visible", () => {
    render(
      <AutomationsPanel
        locale="en"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[staleRecoveredRun]}
        inboxItems={[]}
        scheduler={{ running: true, active_run_count: 0, next_wake_up_at: null, inbox_summary: { unread: 0, reviewed: 0, archived: 0, promoted: 0 } }}
        supervisorAutomations={null}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={vi.fn()}
        onCancelRun={vi.fn()}
        onMarkReviewed={vi.fn()}
        onArchive={vi.fn()}
        onPromote={vi.fn()}
      />,
    );

    const diagnostic = screen.getByTestId("automation-run-diagnostic");
    expect(diagnostic).toHaveTextContent("Watchdog recovered stale run");
    expect(diagnostic).toHaveTextContent("No final result was recorded within 1800 seconds");
    expect(screen.getByText("2026-06-24T01:00:00Z")).toBeInTheDocument();
    expect(screen.getAllByText(/run-stale \/ manifest\.json/)).toHaveLength(2);
  });

  it("explains cancelled runs with a user-facing reason instead of only the cancel code", () => {
    render(
      <AutomationsPanel
        locale="en"
        projectId="demo"
        profiles={[profile]}
        automations={[automation]}
        runs={[cancelledRun]}
        inboxItems={[]}
        scheduler={{ running: true, active_run_count: 0, next_wake_up_at: null, inbox_summary: { unread: 0, reviewed: 0, archived: 0, promoted: 0 } }}
        supervisorAutomations={null}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onPause={vi.fn()}
        onResume={vi.fn()}
        onRunNow={vi.fn()}
        onCancelRun={vi.fn()}
        onMarkReviewed={vi.fn()}
        onArchive={vi.fn()}
        onPromote={vi.fn()}
      />,
    );

    const diagnostic = screen.getByTestId("automation-run-diagnostic");
    expect(diagnostic).toHaveTextContent("Run cancelled");
    expect(diagnostic).toHaveTextContent("stopped by a user action");
    expect(diagnostic).toHaveTextContent("cancelled_by_user");
  });
});
