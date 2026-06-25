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
            description: "Capability routes for image, vision, and speech.",
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
});
