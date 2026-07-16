import { useEffect, useMemo, useRef, useState } from "react";

import { t } from "../i18n/catalog";
import type {
  AutomationInboxItem,
  AutomationKind,
  AutomationNotifyOn,
  AutomationPermissionMode,
  AutomationRun,
  AutomationSchedulerStatus,
  AutomationSpec,
  RouterModelEntry,
  AutomationWorkspaceMode,
  LocaleCode,
  Profile,
  RuntimeSupervisorState,
} from "../../types";
import { resolveStandaloneAutomationProfileGate, type AutomationRuntimeProviderStatus } from "./automationProfileGate";

export type AutomationFormState = {
  automation_id: string;
  name: string;
  description: string;
  kind: AutomationKind;
  prompt: string;
  enabled: boolean;
  schedule_mode: "manual" | "interval" | "daily";
  interval_minutes: number;
  daily_hour: string;
  daily_minute: string;
  timezone: string;
  profile_id: string;
  model: string;
  effort: string;
  permission_mode: AutomationPermissionMode;
  dangerous_opt_in: boolean;
  collaboration_mode: string;
  execution_host: "windows" | "wsl" | "auto";
  mcp_preset_ids: string;
  plugin_skill_preset_ids: string;
  workspace_mode: AutomationWorkspaceMode;
  base_branch: string;
  cleanup_policy: "keep_on_finding" | "keep_on_failure" | "delete_on_no_signal" | "manual";
  archive_no_signal: boolean;
  notify_on: AutomationNotifyOn;
  finding_keywords: string;
  timeout_sec: number;
  max_retries: number;
  max_parallel_runs: number;
};

export type AutomationMcpPresetOption = {
  preset_id: string;
  label: string;
  description: string;
  configured?: boolean;
};

export type AutomationPluginSkillPresetOption = {
  preset_id: string;
  label: string;
  plugin_count: number;
  skill_count: number;
  active?: boolean;
};

export function createEmptyAutomationDraft(projectId: string, profiles: Profile[]): AutomationFormState {
  const preferredProfile = profiles[0];
  return {
    automation_id: `auto-${projectId || "project"}-${Date.now()}`,
    name: "",
    description: "",
    kind: "standalone",
    prompt: "",
    enabled: true,
    schedule_mode: "manual",
    interval_minutes: 60,
    daily_hour: "09",
    daily_minute: "00",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    profile_id: preferredProfile?.profile_id ?? "",
    model: "",
    effort: "",
    permission_mode: "workspace-write",
    dangerous_opt_in: false,
    collaboration_mode: "",
    execution_host: "auto",
    mcp_preset_ids: "",
    plugin_skill_preset_ids: "",
    workspace_mode: "dedicated_worktree",
    base_branch: "",
    cleanup_policy: "keep_on_finding",
    archive_no_signal: true,
    notify_on: "finding",
    finding_keywords: "",
    timeout_sec: 1800,
    max_retries: 0,
    max_parallel_runs: 1,
  };
}

export function draftFromAutomation(automation: AutomationSpec): AutomationFormState {
  const [dailyHour = "09", dailyMinute = "00"] = String(automation.schedule.expression || "09:00").split(":");
  const intervalMinutes = String(automation.schedule.expression || "").match(/^every:(\d+)m$/)?.[1];
  return {
    automation_id: automation.automation_id,
    name: automation.name,
    description: automation.description || "",
    kind: automation.kind,
    prompt: automation.prompt,
    enabled: automation.enabled,
    schedule_mode: automation.schedule.mode,
    interval_minutes: Number(intervalMinutes || 60),
    daily_hour: dailyHour.padStart(2, "0"),
    daily_minute: dailyMinute.padStart(2, "0"),
    timezone: automation.schedule.timezone || "UTC",
    profile_id: automation.runtime.profile_id || "",
    model: automation.runtime.model || "",
    effort: automation.runtime.effort || "",
    permission_mode: automation.runtime.permission_mode,
    dangerous_opt_in: Boolean(automation.runtime.dangerous_opt_in),
    collaboration_mode: automation.runtime.collaboration_mode || "",
    execution_host: automation.runtime.execution_host,
    mcp_preset_ids: (automation.runtime.mcp_preset_ids || []).join(", "),
    plugin_skill_preset_ids: (automation.runtime.plugin_skill_preset_ids || []).join(", "),
    workspace_mode: automation.workspace.mode,
    base_branch: automation.workspace.base_branch || "",
    cleanup_policy: automation.workspace.cleanup_policy,
    archive_no_signal: automation.triage.archive_no_signal,
    notify_on: automation.triage.notify_on,
    finding_keywords: (automation.triage.finding_keywords || []).join(", "),
    timeout_sec: automation.limits.timeout_sec,
    max_retries: automation.limits.max_retries,
    max_parallel_runs: automation.limits.max_parallel_runs,
  };
}

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinPresetIds(ids: string[]) {
  return Array.from(new Set(ids.map((item) => item.trim()).filter(Boolean))).join(", ");
}

export function automationPayloadFromDraft(projectId: string, draft: AutomationFormState) {
  const schedule =
    draft.schedule_mode === "manual"
      ? { mode: "manual" }
      : draft.schedule_mode === "interval"
        ? { mode: "interval", interval_minutes: Math.max(1, Number(draft.interval_minutes) || 1), timezone: draft.timezone || "UTC" }
        : {
            mode: "daily",
            hour: String(draft.daily_hour || "09").padStart(2, "0"),
            minute: String(draft.daily_minute || "00").padStart(2, "0"),
            timezone: draft.timezone || "UTC",
          };

  return {
    automation_id: draft.automation_id.trim(),
    project_id: projectId,
    name: draft.name.trim(),
    description: draft.description.trim(),
    enabled: draft.enabled,
    kind: draft.kind,
    prompt: draft.prompt.trim(),
    schedule,
    runtime: {
      profile_id: draft.profile_id.trim() || null,
      model: draft.model.trim() || null,
      effort: draft.effort.trim() || null,
      permission_mode: draft.permission_mode,
      dangerous_opt_in: draft.permission_mode === "full-access" ? draft.dangerous_opt_in : false,
      collaboration_mode: draft.collaboration_mode.trim() || null,
      execution_host: draft.execution_host,
      mcp_preset_ids: splitList(draft.mcp_preset_ids),
      plugin_skill_preset_ids: splitList(draft.plugin_skill_preset_ids),
    },
    workspace: {
      mode: draft.workspace_mode,
      base_branch: draft.base_branch.trim() || null,
      cleanup_policy: draft.cleanup_policy,
    },
    triage: {
      archive_no_signal: draft.archive_no_signal,
      notify_on: draft.notify_on,
      finding_keywords: splitList(draft.finding_keywords),
    },
    limits: {
      timeout_sec: Math.max(60, Number(draft.timeout_sec) || 1800),
      max_retries: Math.max(0, Number(draft.max_retries) || 0),
      max_parallel_runs: Math.max(1, Number(draft.max_parallel_runs) || 1),
    },
  };
}

function relativeTimeLabel(value?: string | null) {
  if (!value) return "";
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "";
  const diffSeconds = Math.round((timestamp - Date.now()) / 1000);
  const absolute = Math.abs(diffSeconds);
  if (absolute < 60) return diffSeconds >= 0 ? "soon" : "now";
  const minutes = Math.round(absolute / 60);
  if (minutes < 60) return diffSeconds >= 0 ? `in ${minutes}m` : `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return diffSeconds >= 0 ? `in ${hours}h` : `${hours}h ago`;
  const days = Math.round(hours / 24);
  return diffSeconds >= 0 ? `in ${days}d` : `${days}d ago`;
}

function statusTone(status: string) {
  if (["completed", "reviewed", "archived"].includes(status)) return "status-ok";
  if (["failed", "cancelled", "error", "promoted"].includes(status)) return "status-tag-warning";
  return "";
}

function kindLabel(locale: LocaleCode, value: AutomationKind) {
  if (value === "standalone") return t(locale, "automations_kind_standalone");
  if (value === "thread") return t(locale, "automations_kind_thread");
  return value;
}

function scheduleLabel(locale: LocaleCode, value: AutomationFormState["schedule_mode"]) {
  if (value === "manual") return t(locale, "automations_schedule_manual");
  if (value === "interval") return t(locale, "automations_schedule_interval");
  if (value === "daily") return t(locale, "automations_schedule_daily");
  return value;
}

function permissionModeLabel(locale: LocaleCode, value: AutomationPermissionMode) {
  if (value === "read-only") return t(locale, "automations_permission_read_only");
  if (value === "workspace-write") return t(locale, "automations_permission_workspace_write");
  if (value === "full-access") return t(locale, "automations_permission_full_access");
  return value;
}

function executionHostLabel(locale: LocaleCode, value: AutomationFormState["execution_host"]) {
  if (value === "auto") return t(locale, "automations_execution_host_auto");
  if (value === "windows") return t(locale, "automations_execution_host_windows");
  if (value === "wsl") return t(locale, "automations_execution_host_wsl");
  return value;
}

function workspaceModeLabel(locale: LocaleCode, value: AutomationWorkspaceMode) {
  if (value === "dedicated_worktree") return t(locale, "automations_workspace_dedicated_worktree");
  if (value === "current_workspace") return t(locale, "automations_workspace_current_workspace");
  return value;
}

function cleanupPolicyLabel(locale: LocaleCode, value: AutomationFormState["cleanup_policy"]) {
  if (value === "keep_on_finding") return t(locale, "automations_cleanup_keep_on_finding");
  if (value === "keep_on_failure") return t(locale, "automations_cleanup_keep_on_failure");
  if (value === "delete_on_no_signal") return t(locale, "automations_cleanup_delete_on_no_signal");
  if (value === "manual") return t(locale, "automations_cleanup_manual");
  return value;
}

function notifyOnLabel(locale: LocaleCode, value: AutomationNotifyOn) {
  if (value === "finding") return t(locale, "automations_notify_finding");
  if (value === "failure") return t(locale, "automations_notify_failure");
  if (value === "every_run") return t(locale, "automations_notify_every_run");
  return value;
}

function triggerLabel(locale: LocaleCode, value: string) {
  if (value === "manual") return t(locale, "automations_trigger_manual");
  if (value === "schedule") return t(locale, "automations_trigger_schedule");
  if (value === "retry") return t(locale, "automations_trigger_retry");
  return value;
}

function runStatusLabel(locale: LocaleCode, value: string) {
  if (value === "queued") return t(locale, "automations_status_queued");
  if (value === "running") return t(locale, "automations_status_running");
  if (value === "needs_review") return t(locale, "automations_status_needs_review");
  if (value === "completed") return t(locale, "automations_status_completed");
  if (value === "failed") return t(locale, "automations_status_failed");
  if (value === "skipped") return t(locale, "automations_status_skipped");
  if (value === "cancelled") return t(locale, "automations_status_cancelled");
  return value;
}

function signalLabel(locale: LocaleCode, value: string) {
  if (value === "finding") return t(locale, "automations_signal_finding");
  if (value === "no_signal") return t(locale, "automations_signal_no_signal");
  if (value === "unknown") return t(locale, "automations_signal_unknown");
  return value;
}

function inboxStateLabel(locale: LocaleCode, value: string) {
  if (value === "unread") return t(locale, "automations_state_unread");
  if (value === "reviewed") return t(locale, "automations_state_reviewed");
  if (value === "archived") return t(locale, "automations_state_archived");
  if (value === "promoted") return t(locale, "automations_state_promoted");
  return value;
}

function inboxDispositionLabel(locale: LocaleCode, value: string) {
  if (value === "finding") return t(locale, "automations_disposition_finding");
  if (value === "no_signal") return t(locale, "automations_disposition_no_signal");
  if (value === "failure") return t(locale, "automations_disposition_failure");
  if (value === "approval_required") return t(locale, "automations_disposition_approval_required");
  return value;
}

function severityLabel(locale: LocaleCode, value: string) {
  if (value === "info") return t(locale, "automations_severity_info");
  if (value === "warning") return t(locale, "automations_severity_warning");
  if (value === "error") return t(locale, "automations_severity_error");
  return value;
}

function runDiagnosticNotice(locale: LocaleCode, run: AutomationRun) {
  const error = String(run.redacted_error || "").trim();
  const watchdogReason = String(run.watchdog_reason || "").trim().toLowerCase();
  const watchdogSummary = String(run.watchdog_summary || "").trim();
  if (watchdogReason === "stale_running_timeout" || ["automation_watchdog_stale_running_timeout", "stale_run_recovered"].includes(error)) {
    return {
      title: t(locale, "automations_run_watchdog_title"),
      body: locale === "en" && watchdogSummary ? watchdogSummary : t(locale, "automations_run_watchdog_body"),
      raw: error || watchdogReason,
    };
  }
  if (!error) return null;
  if (watchdogReason === "service_restart_interrupted" || error === "automation_runner_interrupted_after_service_restart") {
    return {
      title: t(locale, "automations_run_recovered_title"),
      body: locale === "en" && watchdogSummary ? watchdogSummary : t(locale, "automations_run_recovered_body"),
      raw: error,
    };
  }
  if (run.status === "cancelled" && error === "cancelled_by_user") {
    return {
      title: t(locale, "automations_run_cancelled_title"),
      body: t(locale, "automations_run_cancelled_body"),
      raw: error,
    };
  }
  if (["failed", "cancelled", "needs_review"].includes(run.status)) {
    return {
      title: t(locale, "automations_run_diagnostic_title"),
      body: error,
      raw: null,
    };
  }
  return null;
}

type AutomationRunNotice = {
  title: string;
  body: string;
  raw: string | null;
  tone: "warning" | "success" | "neutral";
};

function compactArtifactPath(path: string) {
  const segments = String(path || "")
    .split(/[\\/]+/)
    .map((segment) => segment.trim())
    .filter(Boolean);
  if (segments.length === 0) return path;
  if (segments.length === 1) return segments[0];
  return segments.slice(-2).join(" / ");
}

function runFinalizationNotice(locale: LocaleCode, run: AutomationRun, inboxItem: AutomationInboxItem | null): AutomationRunNotice | null {
  const status = String(run.status || "").trim().toLowerCase();
  if (!["completed", "skipped"].includes(status)) return null;
  if (inboxItem?.disposition === "finding") {
    return {
      title: t(locale, "automations_run_finalized_finding_title"),
      body: t(locale, "automations_run_finalized_finding_body"),
      raw: null,
      tone: "success",
    };
  }
  if (inboxItem?.disposition === "no_signal") {
    if (String(inboxItem.state || "").trim().toLowerCase() === "archived") {
      return {
        title: t(locale, "automations_run_finalized_archived_title"),
        body: t(locale, "automations_run_finalized_archived_body"),
        raw: null,
        tone: "neutral",
      };
    }
    return {
      title: t(locale, "automations_run_finalized_recorded_title"),
      body: t(locale, "automations_run_finalized_recorded_body"),
      raw: null,
      tone: "neutral",
    };
  }
  return {
    title: t(locale, "automations_run_finalized_no_inbox_title"),
    body: t(locale, "automations_run_finalized_no_inbox_body"),
    raw: null,
    tone: "neutral",
  };
}

function runNoticeClassName(notice: AutomationRunNotice) {
  if (notice.tone === "success") return "automation-run-notice automation-run-notice-success";
  if (notice.tone === "neutral") return "automation-run-notice automation-run-notice-neutral";
  return "automation-run-notice";
}

function runRecoveryLabel(locale: LocaleCode, run: AutomationRun) {
  const watchdogReason = String(run.watchdog_reason || "").trim().toLowerCase();
  if (watchdogReason === "stale_running_timeout") return t(locale, "automations_run_watchdog_title");
  if (watchdogReason === "service_restart_interrupted") return t(locale, "automations_run_recovered_title");
  if (run.status === "cancelled" && String(run.redacted_error || "").trim() === "cancelled_by_user") {
    return t(locale, "automations_run_cancelled_title");
  }
  return t(locale, "automations_none");
}

type Props = {
  locale: LocaleCode;
  projectId: string;
  profiles: Profile[];
  automations: AutomationSpec[];
  runs: AutomationRun[];
  inboxItems: AutomationInboxItem[];
  scheduler: AutomationSchedulerStatus | null;
  supervisorAutomations?: RuntimeSupervisorState["automations"] | null;
  mcpPresetOptions?: AutomationMcpPresetOption[];
  pluginSkillPresetOptions?: AutomationPluginSkillPresetOption[];
  catalogModels?: RouterModelEntry[];
  runtimeProviders?: AutomationRuntimeProviderStatus[];
  isBusy?: boolean;
  operationNotice?: { tone: "info" | "success"; title: string; detail: string } | null;
  errorMessage?: string | null;
  onCreate: (payload: ReturnType<typeof automationPayloadFromDraft>) => void;
  onUpdate: (automationId: string, patch: ReturnType<typeof automationPayloadFromDraft>) => void;
  onDelete: (automationId: string) => void;
  onPause: (automationId: string) => void;
  onResume: (automationId: string) => void;
  onRunNow: (automationId: string) => void;
  onCancelRun: (runId: string) => void;
  onMarkReviewed: (itemId: string) => void;
  onArchive: (itemId: string) => void;
  onPromote: (itemId: string, promotionRef: string) => void;
};

export function AutomationsPanel({
  locale,
  projectId,
  profiles,
  automations,
  runs,
  inboxItems,
  scheduler,
  supervisorAutomations,
  mcpPresetOptions = [],
  pluginSkillPresetOptions = [],
  catalogModels = [],
  runtimeProviders = [],
  isBusy,
  operationNotice,
  errorMessage,
  onCreate,
  onUpdate,
  onDelete,
  onPause,
  onResume,
  onRunNow,
  onCancelRun,
  onMarkReviewed,
  onArchive,
  onPromote,
}: Props) {
  const [selectedAutomationId, setSelectedAutomationId] = useState<string>("");
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [promotionRef, setPromotionRef] = useState("task:");
  const [draft, setDraft] = useState<AutomationFormState>(() => createEmptyAutomationDraft(projectId, profiles));
  const [activityExpanded, setActivityExpanded] = useState<boolean>(true);
  const lastHydratedAutomationId = useRef<string>("");

  useEffect(() => {
    if (automations.length === 0) {
      const shouldResetDraft = Boolean(selectedAutomationId || lastHydratedAutomationId.current);
      setSelectedAutomationId("");
      lastHydratedAutomationId.current = "";
      if (shouldResetDraft) {
        setDraft(createEmptyAutomationDraft(projectId, profiles));
      }
      setActivityExpanded(true);
      return;
    }
    if (!selectedAutomationId || !automations.some((item) => item.automation_id === selectedAutomationId)) {
      setSelectedAutomationId(automations[0].automation_id);
    }
  }, [automations, profiles, projectId, selectedAutomationId]);

  useEffect(() => {
    if (automations.length > 0 || selectedAutomationId || isBusy || operationNotice || errorMessage) {
      setActivityExpanded(true);
    }
  }, [automations.length, errorMessage, isBusy, operationNotice, selectedAutomationId]);

  const selectedAutomation = useMemo(
    () => automations.find((item) => item.automation_id === selectedAutomationId) ?? null,
    [automations, selectedAutomationId],
  );
  const selectedAutomationProfile = useMemo(() => {
    if (!selectedAutomation) return null;
    const selectedProfileId = String(selectedAutomation.runtime.profile_id || "").trim();
    if (!selectedProfileId) return null;
    return profiles.find((profile) => String(profile.profile_id || "").trim() === selectedProfileId) ?? null;
  }, [profiles, selectedAutomation]);
  const standaloneProfileGate = useMemo(() => {
    if (!selectedAutomation || selectedAutomation.kind !== "standalone") return null;
    return resolveStandaloneAutomationProfileGate(
      selectedAutomationProfile,
      catalogModels,
      selectedAutomation.runtime.permission_mode,
      runtimeProviders,
    );
  }, [catalogModels, runtimeProviders, selectedAutomation, selectedAutomationProfile]);

  useEffect(() => {
    if (!selectedAutomationId) return;
    if (lastHydratedAutomationId.current === selectedAutomationId) return;
    const next = automations.find((item) => item.automation_id === selectedAutomationId);
    if (next) {
      setDraft(draftFromAutomation(next));
      lastHydratedAutomationId.current = selectedAutomationId;
    }
  }, [automations, selectedAutomationId]);

  const filteredRuns = useMemo(
    () => runs.filter((run) => !selectedAutomationId || run.automation_id === selectedAutomationId),
    [runs, selectedAutomationId],
  );

  const filteredInbox = useMemo(
    () => inboxItems.filter((item) => !selectedAutomationId || item.automation_id === selectedAutomationId),
    [inboxItems, selectedAutomationId],
  );

  useEffect(() => {
    if (filteredRuns.length === 0) {
      setSelectedRunId("");
      return;
    }
    if (!selectedRunId || !filteredRuns.some((item) => item.run_id === selectedRunId)) {
      setSelectedRunId(filteredRuns[0].run_id);
    }
  }, [filteredRuns, selectedRunId]);

  const selectedRun = filteredRuns.find((run) => run.run_id === selectedRunId) ?? filteredRuns[0] ?? null;
  const selectedRunInboxItem = selectedRun ? filteredInbox.find((item) => item.run_id === selectedRun.run_id) ?? null : null;
  const selectedRunFinalization = selectedRun ? runFinalizationNotice(locale, selectedRun, selectedRunInboxItem) : null;
  const selectedRunNotice = selectedRun ? runDiagnosticNotice(locale, selectedRun) : null;
  const runNowBlocked = standaloneProfileGate?.status === "blocked";
  const showStandaloneProfileGate = Boolean(standaloneProfileGate && standaloneProfileGate.status !== "ready");
  const standaloneProfileGateTitle =
    locale === "zh-CN"
      ? runNowBlocked
        ? "当前模型已阻止直接运行"
        : "当前模型将以审查模式运行"
      : runNowBlocked
        ? "Current model is blocked for direct automation runs"
        : "Current model will stay in review mode";
  const standaloneProfileGateDetail =
    locale === "zh-CN"
      ? `${standaloneProfileGate?.detail ?? ""}${selectedAutomationProfile ? ` 当前 profile: ${selectedAutomationProfile.label}.` : ""}`
      : `${standaloneProfileGate?.detail ?? ""}${selectedAutomationProfile ? ` Active profile: ${selectedAutomationProfile.label}.` : ""}`;
  const summary = supervisorAutomations?.inbox_summary ?? scheduler?.inbox_summary ?? { unread: 0, reviewed: 0, archived: 0, promoted: 0 };
  const configuredPresetIds = splitList(draft.mcp_preset_ids);
  const knownPresetIds = new Set(mcpPresetOptions.map((item) => item.preset_id));
  const customPresetIds = configuredPresetIds.filter((id) => !knownPresetIds.has(id));
  const configuredPluginSkillPresetIds = splitList(draft.plugin_skill_preset_ids);
  const knownPluginSkillPresetIds = new Set(pluginSkillPresetOptions.map((item) => item.preset_id));
  const customPluginSkillPresetIds = configuredPluginSkillPresetIds.filter((id) => !knownPluginSkillPresetIds.has(id));

  function toggleMcpPreset(presetId: string) {
    const selected = new Set(splitList(draft.mcp_preset_ids));
    if (selected.has(presetId)) {
      selected.delete(presetId);
    } else {
      selected.add(presetId);
    }
    setDraft({ ...draft, mcp_preset_ids: joinPresetIds([...selected]) });
  }

  function togglePluginSkillPreset(presetId: string) {
    const selected = new Set(splitList(draft.plugin_skill_preset_ids));
    if (selected.has(presetId)) {
      selected.delete(presetId);
    } else {
      selected.add(presetId);
    }
    setDraft({ ...draft, plugin_skill_preset_ids: joinPresetIds([...selected]) });
  }

  const submitPayload = automationPayloadFromDraft(projectId, draft);

  if (!projectId) {
    return (
      <div className="manager-panel" data-testid="automations-panel">
        <div className="empty-state">{t(locale, "project_none")}</div>
      </div>
    );
  }

  return (
    <div className="manager-panel" data-testid="automations-panel">
      <div className="manager-hero">
        <div>
          <span className="eyebrow">{t(locale, "setup_tab_automations")}</span>
          <h3>{t(locale, "automations_title")}</h3>
          <p className="muted compact-copy">{t(locale, "automations_summary")}</p>
        </div>
        <div className="field-row">
          <span className={`status-tag ${scheduler?.running ? "status-ok" : ""}`}>{scheduler?.running ? t(locale, "automations_scheduler_running") : t(locale, "automations_scheduler_stopped")}</span>
          <button
            type="button"
            className="ghost-button"
            onClick={() => {
              setActivityExpanded(true);
              setSelectedAutomationId("");
              lastHydratedAutomationId.current = "";
              setDraft(createEmptyAutomationDraft(projectId, profiles));
            }}
          >
            {t(locale, "automations_new")}
          </button>
        </div>
      </div>

      <div className="manager-facts automation-summary-grid">
        <div><dt>{t(locale, "automations_unread")}</dt><dd>{summary.unread}</dd></div>
        <div><dt>{t(locale, "automations_active_runs")}</dt><dd>{scheduler?.active_run_count ?? supervisorAutomations?.active_runs.length ?? 0}</dd></div>
        <div><dt>{t(locale, "automations_next_due")}</dt><dd>{relativeTimeLabel((scheduler?.next_due?.next_run_at || supervisorAutomations?.next_due?.next_run_at) ?? null) || t(locale, "automations_none")}</dd></div>
      </div>

      <details className="manager-disclosure automation-activity-disclosure" open={activityExpanded}>
        <summary
          onClick={(event) => {
            event.preventDefault();
            setActivityExpanded((value) => !value);
          }}
        >
          <span>{t(locale, "automations_activity_details")}</span>
        </summary>
        <div className="automation-columns">
        <section className="manager-section">
          <h4>{t(locale, "automations_list_title")}</h4>
          <div className="manager-list manager-list-tall">
            {automations.length === 0 ? <div className="empty-state">{t(locale, "automations_empty")}</div> : null}
            {automations.map((automation) => (
              <button
                key={automation.automation_id}
                type="button"
                className={selectedAutomationId === automation.automation_id ? "manager-row manager-row-active" : "manager-row"}
                onClick={() => {
                  setActivityExpanded(true);
                  setSelectedAutomationId(automation.automation_id);
                }}
              >
                <span>
                  <strong>{automation.name}</strong>
                  <small>{kindLabel(locale, automation.kind)} / {scheduleLabel(locale, automation.schedule.mode)} / {permissionModeLabel(locale, automation.runtime.permission_mode)}</small>
                </span>
                <span className="manager-row-side">
                  <span className={`status-tag ${statusTone(automation.last_status || (automation.enabled ? "enabled" : "paused"))}`}>
                    {automation.archived_at ? t(locale, "automations_archived") : automation.enabled ? t(locale, "automations_enabled") : t(locale, "automations_paused")}
                  </span>
                  <code>{automation.inbox_summary?.unread ?? 0} {t(locale, "automations_unread").toLowerCase()}</code>
                </span>
              </button>
            ))}
          </div>
        </section>

        <section className="manager-section">
          <div className="field-row" style={{ justifyContent: "space-between" }}>
            <h4>{selectedAutomation ? t(locale, "automations_edit") : t(locale, "automations_create")}</h4>
            <div className="field-row">
              <button type="button" className="primary-button" disabled={isBusy || !draft.name.trim() || !draft.prompt.trim()} onClick={() => (selectedAutomation ? onUpdate(selectedAutomation.automation_id, submitPayload) : onCreate(submitPayload))}>
                {selectedAutomation ? t(locale, "automations_save") : t(locale, "automations_create_button")}
              </button>
              {selectedAutomation ? (
                <button
                  type="button"
                  className="ghost-button"
                  disabled={isBusy || runNowBlocked}
                  title={runNowBlocked ? standaloneProfileGate?.detail : undefined}
                  onClick={() => onRunNow(selectedAutomation.automation_id)}
                >
                  {t(locale, "automations_run_now")}
                </button>
              ) : null}
            </div>
          </div>

          {operationNotice ? (
            <div
              className={operationNotice.tone === "success" ? "automation-operation-notice automation-operation-notice-success" : "automation-operation-notice"}
              role="status"
            >
              <strong>{operationNotice.title}</strong>
              <span>{operationNotice.detail}</span>
            </div>
          ) : null}

          {errorMessage ? (
            <div className="automation-operation-error" data-testid="automation-error-message" role="alert">
              <strong>{t(locale, "automations_operation_error")}</strong>
              <span>{errorMessage}</span>
            </div>
          ) : null}

          <div className="automation-safety-note">
            <strong>{t(locale, "automations_safety_title")}</strong>
            <span>{t(locale, "automations_safety_summary")}</span>
          </div>
          {showStandaloneProfileGate && standaloneProfileGate ? (
            <div
              className={
                standaloneProfileGate.status === "blocked"
                  ? "automation-run-notice"
                  : "automation-run-notice automation-run-notice-neutral"
              }
              data-testid="automation-profile-gate"
              role="status"
            >
              <strong>{standaloneProfileGateTitle}</strong>
              <span>{standaloneProfileGateDetail}</span>
            </div>
          ) : null}

          <div className="form-grid">
            <label className="field"><span>{t(locale, "automations_id")}</span><input value={draft.automation_id} onChange={(event) => setDraft({ ...draft, automation_id: event.target.value })} disabled={Boolean(selectedAutomation)} /></label>
            <label className="field"><span>{t(locale, "automations_name")}</span><input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
            <label className="field"><span>{t(locale, "automations_kind")}</span><select value={draft.kind} onChange={(event) => setDraft({ ...draft, kind: event.target.value as AutomationKind })}><option value="standalone">{kindLabel(locale, "standalone")}</option><option value="thread">{kindLabel(locale, "thread")}</option></select></label>
            <label className="field"><span>{t(locale, "automations_schedule")}</span><select value={draft.schedule_mode} onChange={(event) => setDraft({ ...draft, schedule_mode: event.target.value as AutomationFormState["schedule_mode"] })}><option value="manual">{scheduleLabel(locale, "manual")}</option><option value="interval">{scheduleLabel(locale, "interval")}</option><option value="daily">{scheduleLabel(locale, "daily")}</option></select></label>
            <label className="field"><span>{t(locale, "automations_profile")}</span>
              <select value={draft.profile_id} onChange={(event) => setDraft({ ...draft, profile_id: event.target.value })}>
                <option value="">{t(locale, "automations_none")}</option>
                {profiles.map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.label} ({profile.profile_id})</option>)}
              </select>
            </label>
            <label className="field"><span>{t(locale, "automations_permission")}</span><select value={draft.permission_mode} onChange={(event) => setDraft({ ...draft, permission_mode: event.target.value as AutomationPermissionMode })}><option value="read-only">{permissionModeLabel(locale, "read-only")}</option><option value="workspace-write">{permissionModeLabel(locale, "workspace-write")}</option><option value="full-access">{permissionModeLabel(locale, "full-access")}</option></select></label>
            {draft.schedule_mode === "interval" ? <label className="field"><span>{t(locale, "automations_interval_minutes")}</span><input type="number" min={1} value={draft.interval_minutes} onChange={(event) => setDraft({ ...draft, interval_minutes: Number(event.target.value) || 1 })} /></label> : null}
            {draft.schedule_mode === "daily" ? <label className="field"><span>{t(locale, "automations_daily_time")}</span><input value={`${draft.daily_hour}:${draft.daily_minute}`} onChange={(event) => {
              const [hour = "09", minute = "00"] = event.target.value.split(":", 2);
              setDraft({ ...draft, daily_hour: hour.padStart(2, "0"), daily_minute: minute.padStart(2, "0") });
            }} /></label> : null}
          </div>

          <details className="manager-disclosure automation-advanced-settings">
            <summary><span>{t(locale, "automations_advanced_settings")}</span></summary>
            <div className="form-grid">
            <label className="field"><span>{t(locale, "automations_timezone")}</span><input value={draft.timezone} onChange={(event) => setDraft({ ...draft, timezone: event.target.value })} /></label>
            <label className="field"><span>{t(locale, "automations_execution_host")}</span><select value={draft.execution_host} onChange={(event) => setDraft({ ...draft, execution_host: event.target.value as AutomationFormState["execution_host"] })}><option value="auto">{executionHostLabel(locale, "auto")}</option><option value="windows">{executionHostLabel(locale, "windows")}</option><option value="wsl">{executionHostLabel(locale, "wsl")}</option></select></label>
            <label className="field"><span>{t(locale, "automations_model")}</span><input value={draft.model} onChange={(event) => setDraft({ ...draft, model: event.target.value })} /></label>
            <label className="field"><span>{t(locale, "automations_effort")}</span><input value={draft.effort} onChange={(event) => setDraft({ ...draft, effort: event.target.value })} /></label>
            <label className="field"><span>{t(locale, "automations_workspace_mode")}</span><select value={draft.workspace_mode} onChange={(event) => setDraft({ ...draft, workspace_mode: event.target.value as AutomationWorkspaceMode })}><option value="dedicated_worktree">{workspaceModeLabel(locale, "dedicated_worktree")}</option><option value="current_workspace">{workspaceModeLabel(locale, "current_workspace")}</option></select></label>
            <label className="field"><span>{t(locale, "automations_cleanup_policy")}</span><select value={draft.cleanup_policy} onChange={(event) => setDraft({ ...draft, cleanup_policy: event.target.value as AutomationFormState["cleanup_policy"] })}><option value="keep_on_finding">{cleanupPolicyLabel(locale, "keep_on_finding")}</option><option value="keep_on_failure">{cleanupPolicyLabel(locale, "keep_on_failure")}</option><option value="delete_on_no_signal">{cleanupPolicyLabel(locale, "delete_on_no_signal")}</option><option value="manual">{cleanupPolicyLabel(locale, "manual")}</option></select></label>
            <label className="field"><span>{t(locale, "automations_base_branch")}</span><input value={draft.base_branch} onChange={(event) => setDraft({ ...draft, base_branch: event.target.value })} placeholder="main" /></label>
            <label className="field"><span>{t(locale, "automations_notify_on")}</span><select value={draft.notify_on} onChange={(event) => setDraft({ ...draft, notify_on: event.target.value as AutomationNotifyOn })}><option value="finding">{notifyOnLabel(locale, "finding")}</option><option value="failure">{notifyOnLabel(locale, "failure")}</option><option value="every_run">{notifyOnLabel(locale, "every_run")}</option></select></label>
            <label className="field"><span>{t(locale, "automations_timeout_sec")}</span><input type="number" min={60} value={draft.timeout_sec} onChange={(event) => setDraft({ ...draft, timeout_sec: Number(event.target.value) || 1800 })} /></label>
            <label className="field"><span>{t(locale, "automations_max_retries")}</span><input type="number" min={0} value={draft.max_retries} onChange={(event) => setDraft({ ...draft, max_retries: Number(event.target.value) || 0 })} /></label>
            <label className="field"><span>{t(locale, "automations_parallel_runs")}</span><input type="number" min={1} value={draft.max_parallel_runs} onChange={(event) => setDraft({ ...draft, max_parallel_runs: Number(event.target.value) || 1 })} /></label>
            <div className="field automation-preset-field">
              <span>{t(locale, "automations_mcp_presets")}</span>
              <div className="automation-preset-picker" aria-label={t(locale, "automations_mcp_preset_picker")}>
                {mcpPresetOptions.map((preset) => {
                  const selected = configuredPresetIds.includes(preset.preset_id);
                  return (
                    <button
                      key={preset.preset_id}
                      type="button"
                      className={selected ? "automation-preset-chip automation-preset-chip-selected" : "automation-preset-chip"}
                      aria-pressed={selected}
                      onClick={() => toggleMcpPreset(preset.preset_id)}
                    >
                      <strong>{preset.label}</strong>
                      <small>{preset.configured ? t(locale, "automations_mcp_preset_configured") : t(locale, "automations_mcp_preset_available")}</small>
                    </button>
                  );
                })}
                {customPresetIds.map((presetId) => (
                  <span className="automation-preset-chip automation-preset-chip-custom" key={presetId}>
                    <strong>{presetId}</strong>
                    <small>{t(locale, "automations_mcp_preset_custom")}</small>
                  </span>
                ))}
              </div>
              <small className="muted compact-copy">{t(locale, "automations_mcp_preset_hint")}</small>
            </div>
            <div className="field automation-preset-field">
              <span>{t(locale, "automations_plugin_skill_presets")}</span>
              <div className="automation-preset-picker" aria-label={t(locale, "automations_plugin_skill_preset_picker")}>
                {pluginSkillPresetOptions.map((preset) => {
                  const selected = configuredPluginSkillPresetIds.includes(preset.preset_id);
                  return (
                    <button
                      key={preset.preset_id}
                      type="button"
                      className={selected ? "automation-preset-chip automation-preset-chip-selected" : "automation-preset-chip"}
                      aria-pressed={selected}
                      onClick={() => togglePluginSkillPreset(preset.preset_id)}
                    >
                      <strong>{preset.label}</strong>
                      <small>
                        {preset.plugin_count}P / {preset.skill_count}S
                        {preset.active ? ` · ${t(locale, "automations_plugin_skill_preset_active")}` : ""}
                      </small>
                    </button>
                  );
                })}
                {customPluginSkillPresetIds.map((presetId) => (
                  <span className="automation-preset-chip automation-preset-chip-custom" key={presetId}>
                    <strong>{presetId}</strong>
                    <small>{t(locale, "automations_plugin_skill_preset_custom")}</small>
                  </span>
                ))}
              </div>
              <small className="muted compact-copy">{t(locale, "automations_plugin_skill_preset_hint")}</small>
            </div>
            </div>
          </details>

          <label className="field"><span>{t(locale, "automations_description")}</span><textarea rows={2} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
          <label className="field"><span>{t(locale, "automations_prompt")}</span><textarea rows={6} value={draft.prompt} onChange={(event) => setDraft({ ...draft, prompt: event.target.value })} /></label>
          <label className="field"><span>{t(locale, "automations_finding_keywords")}</span><input value={draft.finding_keywords} onChange={(event) => setDraft({ ...draft, finding_keywords: event.target.value })} placeholder="todo, flaky, regression" /></label>

          <div className="check-row">
            <label><input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} /> {t(locale, "automations_enabled")}</label>
            <label><input type="checkbox" checked={draft.archive_no_signal} onChange={(event) => setDraft({ ...draft, archive_no_signal: event.target.checked })} /> {t(locale, "automations_archive_no_signal")}</label>
            <label><input type="checkbox" checked={draft.dangerous_opt_in} onChange={(event) => setDraft({ ...draft, dangerous_opt_in: event.target.checked })} disabled={draft.permission_mode !== "full-access"} /> {t(locale, "automations_dangerous_opt_in")}</label>
          </div>

          {selectedAutomation ? (
            <div className="field-row">
              <button type="button" className="ghost-button" disabled={isBusy} onClick={() => (selectedAutomation.enabled ? onPause(selectedAutomation.automation_id) : onResume(selectedAutomation.automation_id))}>
                {selectedAutomation.enabled ? t(locale, "automations_pause") : t(locale, "automations_resume")}
              </button>
              <button type="button" className="ghost-button" disabled={isBusy} onClick={() => onDelete(selectedAutomation.automation_id)}>{t(locale, "automations_delete")}</button>
              {selectedAutomation.archived_at ? <small>{selectedAutomation.archived_reason || t(locale, "automations_archived")}</small> : null}
            </div>
          ) : null}
        </section>
      </div>

      <div className="automation-columns">
        <section className="manager-section">
          <h4>{t(locale, "automations_inbox_title")}</h4>
          <div className="manager-list manager-list-tall">
            {filteredInbox.length === 0 ? <div className="empty-state">{t(locale, "automations_inbox_empty")}</div> : null}
            {filteredInbox.map((item) => (
              <div className="manager-row" key={item.item_id} style={{ display: "block" }}>
                <div className="field-row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                  <span>
                    <strong>{item.title}</strong>
                    <small>{inboxDispositionLabel(locale, item.disposition)} / {inboxStateLabel(locale, item.state)} / {relativeTimeLabel(item.updated_at)}</small>
                  </span>
                  <span className={`status-tag ${statusTone(item.state)}`}>{severityLabel(locale, item.severity)}</span>
                </div>
                <small>{item.summary}</small>
                <div className="field-row automation-inbox-actions">
                  {item.state !== "reviewed" ? <button type="button" className="ghost-button" onClick={() => onMarkReviewed(item.item_id)}>{t(locale, "automations_mark_reviewed")}</button> : null}
                  {item.state !== "archived" ? <button type="button" className="ghost-button" onClick={() => onArchive(item.item_id)}>{t(locale, "automations_archive")}</button> : null}
                  <input className="automation-promotion-input" value={promotionRef} onChange={(event) => setPromotionRef(event.target.value)} aria-label={t(locale, "automations_promotion_ref")} placeholder="task:123" />
                  <button type="button" className="primary-button" onClick={() => onPromote(item.item_id, promotionRef)}>{t(locale, "automations_promote")}</button>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="manager-section">
          <h4>{t(locale, "automations_runs_title")}</h4>
          <div className="manager-list">
            {filteredRuns.length === 0 ? <div className="empty-state">{t(locale, "automations_runs_empty")}</div> : null}
            {filteredRuns.map((run) => (
              <button key={run.run_id} type="button" className={selectedRunId === run.run_id ? "manager-row manager-row-active" : "manager-row"} onClick={() => setSelectedRunId(run.run_id)}>
                <span>
                  <strong>{runStatusLabel(locale, run.status)}</strong>
                  <small>{triggerLabel(locale, run.trigger)} / {signalLabel(locale, run.signal)} / {relativeTimeLabel(run.finished_at || run.started_at || run.due_at)}</small>
                </span>
                <span className="manager-row-side">
                  <span className={`status-tag ${statusTone(run.status)}`}>{runStatusLabel(locale, run.status)}</span>
                </span>
              </button>
            ))}
          </div>
          {selectedRun ? (
            <div className="automation-run-detail">
              <div className="field-row" style={{ justifyContent: "space-between" }}>
                <strong>{selectedRun.run_id}</strong>
                {["queued", "running", "needs_review"].includes(selectedRun.status) ? <button type="button" className="ghost-button" onClick={() => onCancelRun(selectedRun.run_id)}>{t(locale, "automations_cancel_run")}</button> : null}
              </div>
              <p className="muted compact-copy">{selectedRun.summary || t(locale, "automations_none")}</p>
              <div className="automation-detail-grid">
                <div><dt>{t(locale, "status")}</dt><dd>{runStatusLabel(locale, selectedRun.status)}</dd></div>
                <div><dt>{t(locale, "automations_signal")}</dt><dd>{signalLabel(locale, selectedRun.signal)}</dd></div>
                <div><dt>{t(locale, "automations_due_at")}</dt><dd>{selectedRun.due_at || t(locale, "automations_none")}</dd></div>
                <div><dt>{t(locale, "automations_worktree")}</dt><dd>{selectedRun.worktree_path || t(locale, "automations_none")}</dd></div>
                <div><dt>{t(locale, "automations_run_recovery")}</dt><dd>{runRecoveryLabel(locale, selectedRun)}</dd></div>
                <div><dt>{t(locale, "automations_run_retry_at")}</dt><dd>{selectedRun.next_retry_at || t(locale, "automations_none")}</dd></div>
                <div>
                  <dt>{t(locale, "automations_run_inbox_item")}</dt>
                  <dd>
                    {selectedRunInboxItem
                      ? `${selectedRunInboxItem.title} · ${inboxDispositionLabel(locale, selectedRunInboxItem.disposition)} / ${inboxStateLabel(locale, selectedRunInboxItem.state)}`
                      : t(locale, "automations_none")}
                  </dd>
                </div>
                <div>
                  <dt>{t(locale, "automations_run_manifest")}</dt>
                  <dd>{selectedRun.artifact_refs.length > 0 ? selectedRun.artifact_refs.map(compactArtifactPath).join(", ") : t(locale, "automations_none")}</dd>
                </div>
              </div>
              {selectedRunFinalization ? (
                <div className={runNoticeClassName(selectedRunFinalization)} data-testid="automation-run-finalization" role="status">
                  <strong>{selectedRunFinalization.title}</strong>
                  <span>{selectedRunFinalization.body}</span>
                </div>
              ) : null}
              {selectedRunNotice ? (
                <div className="automation-run-notice" data-testid="automation-run-diagnostic" role="status">
                  <strong>{selectedRunNotice.title}</strong>
                  <span>{selectedRunNotice.body}</span>
                  {selectedRunNotice.raw ? <code>{selectedRunNotice.raw}</code> : null}
                </div>
              ) : null}
              {selectedRun.artifact_refs.length > 0 ? (
                <div className="field">
                  <span>{t(locale, "automations_artifacts")}</span>
                  <div className="manager-list">
                    {selectedRun.artifact_refs.map((path) => <code key={path} title={path}>{compactArtifactPath(path)}</code>)}
                  </div>
                </div>
              ) : null}
              {selectedRun.stdout_excerpt ? <pre className="json-preview compact-preview">{selectedRun.stdout_excerpt}</pre> : null}
              {selectedRun.stderr_excerpt ? <pre className="json-preview compact-preview">{selectedRun.stderr_excerpt}</pre> : null}
              {selectedRun.redacted_error && !selectedRunNotice ? <p className="error-text">{selectedRun.redacted_error}</p> : null}
            </div>
          ) : null}
        </section>
        </div>
      </details>
    </div>
  );
}
