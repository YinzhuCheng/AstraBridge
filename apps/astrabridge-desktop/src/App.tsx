import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { GitFork, Save } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import { t, permissionLabel } from "./features/i18n/catalog";
import { AutomationsPanel, type AutomationMcpPresetOption, type AutomationPluginSkillPresetOption } from "./features/automations/AutomationsPanel";
import { CapabilityRoutesPanel, type CapabilityProviderCredentialStatus } from "./features/capabilities/CapabilityRoutesPanel";
import { PluginSkillInventoryPanel } from "./features/extensions/PluginSkillInventoryPanel";
import { summarizeCodingEventInspector } from "./features/runtime/codingEventInspector";
import {
  BrowserInspectorPanel,
  FilesInspectorPanel,
  InspectorTabBar,
  type InspectorTab,
  ReviewInspectorPanel,
  TerminalInspectorPanel,
  WorkflowEvidencePanel,
} from "./features/runtime/InspectorPanels";
import { isolationAuditSummary, projectCaptureRoot, suggestedDogfoodScreenshotPath } from "./features/runtime/isolationAudit";
import { RuntimeKernelStatusPanel } from "./features/runtime/RuntimeKernelStatusPanel";
import { summarizeTaskInspectorEvidence } from "./features/runtime/taskInspectorEvidence";
import { modelAuthorityState } from "./features/runtime/modelAuthorityNotice";
import { contextGuardLevel, extractProposedPlanText, hasUnsafeWindowsWrite, parsePlanCard, readsExplosiveAstraBridgeLog } from "./features/runtime/planRendering";
import { resolveRecoveryComposerPatch } from "./features/runtime/runtimeRecoveryPlan";
import { formatResponseDiagnostics, summarizeResponseDiagnosticsInline } from "./features/runtime/responseDiagnostics";
import { composerReasoningOptions, preferredProviderReasoningEffort, preferredReasoningEffort, providerModelDraftDefaults, providerReasoningOptions } from "./features/runtime/reasoningOptions";
import { runtimeErrorNoticeActions, runtimeErrorNoticeInline, runtimeErrorNoticeText, type RuntimeErrorAction } from "./features/runtime/runtimeErrorNotice";
import { summarizeTaskCard } from "./features/runtime/taskSummary";
import { summarizeTaskWorkflowFacts } from "./features/runtime/taskWorkflowFacts";
import { hasPersistedRenderableTurnContent, itemActivityFromPayload, summarizeTurnBlocks } from "./features/runtime/threadRendering";
import { useAppStore } from "./store";
import { chooseProjectSavePath, selectDirectory, selectExistingProject, selectFiles } from "./tauriDialog";
import type {
  AppearancePreset,
  AssetRegistryEntry,
  AttachmentDraft,
  CapabilityRouteEntry,
  CapabilitySmokeResult,
  CollaborationMode,
  DogfoodRun,
  ExecutionHost,
  GoalResponse,
  LlmManagerKey,
  McpServerConfig,
  PermissionMode,
  Profile,
  ProjectCheckpoint,
  ProjectFile,
  ProjectFilePreview,
  ProjectFilesTree,
  ProjectReviewDiff,
  ProjectReviewStatus,
  ProjectTerminalHistory,
  ReasoningConfig,
  RuntimeFailureNotice,
  RouterConfigResponse,
  RouterModelEntry,
  RouterProvider,
  RuntimeEvent,
  RuntimeActivityState,
  RuntimeDiffSummary,
  RuntimeModal,
  RuntimeSupervisorState,
  ShellThread,
  ThreadRenderBlock,
  ProjectTask,
} from "./types";

const DEFAULT_GAMEPLAY_SMOKE_ACTIONS: Array<Record<string, unknown>> = [
  { type: "click_text", text: "New Game", timeout_ms: 5000 },
  { type: "wait_ms", ms: 800 },
  { type: "click_text_until_absent", text: "Next", max_clicks: 12, settle_ms: 250, timeout_ms: 5000 },
  { type: "expect_text", text: "Floor 1", timeout_ms: 10000 },
  { type: "press", key: "ArrowRight" },
  { type: "press", key: "ArrowRight" },
  { type: "press", key: "ArrowUp" },
  { type: "press", key: "ArrowUp" },
  { type: "wait_ms", ms: 1200 },
];

const RELEASE_WORKFLOW_SMOKE_PRESET = "astrabridge_release_workflow_v1";
const PROVIDER_SWITCH_WORKFLOW_SMOKE_PRESET = "astrabridge_provider_switch_workflow_v1";
const NATIVE_KERNEL_WORKFLOW_SMOKE_PRESET = "astrabridge_native_kernel_workflow_v1";

function localAssetUrl(path: string) {
  return isTauri() ? convertFileSrc(path) : `file://${path.replace(/\\/g, "/")}`;
}

function currentBrowserSmokeUrl() {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8123/";
  }
  const url = new URL(window.location.href);
  url.searchParams.set("smoke", "1");
  return url.toString();
}

function browserSmokeMode() {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("smoke") === "1";
}

function stringifyDetail(value: unknown) {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function summarizeRelativeTime(value: number | string | null | undefined) {
  if (!value) return "";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  const time = date.getTime();
  if (!Number.isFinite(time)) return "";
  const diffSeconds = Math.max(0, Math.round((Date.now() - time) / 1000));
  if (diffSeconds < 60) return "now";
  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatMessageTime(value: number | string | null | undefined) {
  if (!value) return "";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "";
  const seconds = Math.max(0, Math.round(value / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  if (minutes < 60) return `${minutes}m ${rest}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function taskStatKey(task: ProjectTask, stat: string) {
  return `${task.task_id}:${stat}`;
}

function inheritedGoalFrom(value: unknown, source: "task" | "dogfood") {
  if (!value) return null;
  if (typeof value === "string") {
    const objective = value.trim();
    return objective ? { objective, status: source === "task" ? "task inherited" : "dogfood inherited", source } : null;
  }
  if (typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  const objective = String(record.objective ?? record.goal ?? record.text ?? "").trim();
  if (!objective) return null;
  return {
    objective,
    status: String(record.status ?? (source === "task" ? "task inherited" : "dogfood inherited")),
    source,
  };
}

function countDiffLines(diff: string | null | undefined): RuntimeDiffSummary {
  const text = String(diff || "");
  let added = 0;
  let deleted = 0;
  const files = new Set<string>();
  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith("diff --git ")) {
      const match = line.match(/^diff --git a\/(.+?) b\//);
      if (match?.[1]) files.add(match[1]);
      continue;
    }
    if (line.startsWith("+++") || line.startsWith("---")) continue;
    if (line.startsWith("+")) added += 1;
    if (line.startsWith("-")) deleted += 1;
  }
  const filePaths = [...files];
  return {
    added,
    deleted,
    files: files.size,
    diff: text,
    file_paths: filePaths,
    detail: filePaths.length > 0 ? filePaths.join("\n") : undefined,
  };
}

function countFileChanges(changes: unknown): RuntimeDiffSummary {
  const list = Array.isArray(changes) ? changes : [];
  let added = 0;
  let deleted = 0;
  const files = new Set<string>();
  const detailLines: string[] = [];
  for (const change of list) {
    if (!change || typeof change !== "object") continue;
    const item = change as Record<string, unknown>;
    const path = String(item.path ?? item.newPath ?? item.file ?? "");
    if (path) files.add(path);
    const diff = String(item.diff ?? item.unified_diff ?? "");
    const counted = countDiffLines(diff);
    added += counted.added;
    deleted += counted.deleted;
    const kind = (item.kind as { type?: string; move_path?: string | null } | undefined)?.type ?? "update";
    const movePath = (item.kind as { move_path?: string | null } | undefined)?.move_path ?? null;
    const action = kind === "add" ? "新增" : kind === "delete" ? "删除" : movePath ? `更新并移动到 ${movePath}` : "更新";
    if (path) detailLines.push(`${path} · ${action} · +${counted.added} -${counted.deleted}`);
  }
  return {
    added,
    deleted,
    files: files.size || list.length,
    file_paths: [...files],
    detail: detailLines.join("\n"),
  };
}

function decodeBase64Utf8(value: unknown) {
  const input = String(value ?? "");
  if (!input) return "";
  try {
    const binary = atob(input);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return new TextDecoder().decode(bytes);
  } catch {
    return "";
  }
}

function initials(value: string | null | undefined) {
  const cleaned = String(value || "?").trim();
  if (!cleaned) return "?";
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return cleaned.slice(0, 2).toUpperCase();
}

function isLocalImagePath(value: string | null | undefined) {
  if (!value) return false;
  return /^[a-z]:[\\/]/i.test(value) || value.startsWith("/") || value.startsWith("\\\\") || value.startsWith("file:");
}

function detectMime(path: string) {
  const lower = path.toLowerCase();
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".webp")) return "image/webp";
  if (lower.endsWith(".gif")) return "image/gif";
  if (lower.endsWith(".svg")) return "image/svg+xml";
  return "application/octet-stream";
}

function latestProposedPlan(thread?: ShellThread | null) {
  if (!thread) return "";
  for (const turn of [...(thread.turns ?? [])].reverse()) {
    for (const item of [...(turn.items ?? [])].reverse()) {
      if (item.type !== "agentMessage") continue;
      const match = item.text.match(/<proposed_plan>([\s\S]*?)<\/proposed_plan>/i);
      if (match?.[1]) return match[1].trim();
    }
  }
  return "";
}

function describeSendError(stageLabel: string, error: unknown) {
  if (error instanceof Error && error.message.trim()) {
    const message = error.message.trim();
    const zh = /[\u4e00-\u9fff]/.test(stageLabel);
    if (message.includes("codex_app_server_closed") || message.includes("codex_app_server_disconnected")) {
      return zh
        ? `${stageLabel}: Codex 运行时意外关闭。请点右侧“重启运行时”后重试；如果线程已经创建，应用会尝试从本地 .astrabridge 缓存恢复。`
        : `${stageLabel}: The Codex runtime closed unexpectedly. Restart Runtime and retry; if the thread was created, the app will try to recover it from local .astrabridge cache.`;
    }
    if (message.includes("runtime_secret_missing")) {
      return zh
        ? `${stageLabel}: 当前 provider key 还没有加载。请在 Provider Key 卡片粘贴 key，或选择“从 key 文件载入”。`
        : `${stageLabel}: The selected provider key is not loaded. Paste it in the Provider Key card or load it from a local key file.`;
    }
    return `${stageLabel}: ${message}`;
  }
  return `${stageLabel}: Send failed before the runtime returned a usable error.`;
}

function profileAuthGuide(locale: "en" | "zh-CN", authMode: Profile["auth_mode"]) {
  if (authMode === "key_file") return t(locale, "key_setup_mode_file");
  if (authMode === "os_keychain") return t(locale, "key_setup_mode_keychain");
  if (authMode === "session_paste") return t(locale, "key_setup_mode_session");
  return t(locale, "key_setup_mode_env");
}

function providerSetupLabel(locale: "en" | "zh-CN") {
  return locale === "zh-CN" ? "提供方与密钥" : "Providers & keys";
}

function fallbackRouteLabel(locale: "en" | "zh-CN") {
  return locale === "zh-CN" ? "当前路由" : "Current route";
}

function localizedAuthorityNotice(locale: "en" | "zh-CN", notice: string) {
  const known: Record<string, string> = {
    "Parallel tool calls are disabled for this model unless a parallel smoke test passes.": "authority_warning_parallel_disabled",
    "This model should stay in propose-first mode for apply or execute actions.": "authority_warning_propose_first",
    "This model should stay in review or explain mode because structured tool use is not verified.": "authority_warning_review_only",
    "This model is not eligible for AstraBridge agent mode.": "authority_warning_agent_disabled",
    "Model authority is unknown. Keep approvals and verification on until this model is classified.": "authority_warning_unknown",
    "Image attachments are not verified for this model; send them as file context only or choose an image-capable model.": "authority_warning_image_unverified",
    "MCP tool use is unverified for this model. Keep MCP tools approval-gated until a smoke test passes.": "authority_warning_mcp_unverified",
  };
  const key = known[notice];
  return key ? t(locale, key) : notice;
}

function safeParseObject(text: string) {
  try {
    const parsed = JSON.parse(text || "{}");
    return parsed && typeof parsed === "object" ? parsed as Record<string, string> : {};
  } catch {
    return {};
  }
}

function safeParseStringMap(text: string) {
  const parsed = safeParseObject(text);
  return Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, String(value)]));
}

function safeParseToolMap(text: string) {
  const parsed = safeParseObject(text);
  const result: Record<string, { approval_mode?: string }> = {};
  for (const [key, value] of Object.entries(parsed)) {
    if (value && typeof value === "object") {
      result[key] = { approval_mode: String((value as Record<string, unknown>).approval_mode ?? "") };
    } else if (typeof value === "string") {
      result[key] = { approval_mode: value };
    }
  }
  return result;
}

function splitList(text: string) {
  return text
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(values: string[] | undefined) {
  return (values ?? []).join(", ");
}

function optionalNumber(value: string) {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function budgetPercent(used: number | undefined, cap: number | undefined) {
  if (!cap || cap <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round(((used ?? 0) / cap) * 100)));
}

function productStatusLabel(value: string | null | undefined) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) return "未知";
  if (normalized === "ok") return "正常";
  if (normalized === "pass") return "通过";
  if (normalized === "fail" || normalized === "failed") return "失败";
  if (normalized === "unknown") return "未知";
  if (normalized === "warning") return "警告";
  return String(value);
}

function capturePath(capture: unknown) {
  return typeof capture === "string" ? capture : String((capture as { path?: string } | null)?.path ?? "");
}

function captureLabel(capture: unknown) {
  return typeof capture === "string" ? "capture" : String((capture as { label?: string } | null)?.label ?? "capture");
}

function captureProvider(capture: unknown) {
  return typeof capture === "string" ? "manual" : String((capture as { provider?: string } | null)?.provider ?? "manual");
}

function captureCreatedAt(capture: unknown) {
  return typeof capture === "string" ? "" : String((capture as { created_at?: string } | null)?.created_at ?? "");
}

function assetSummaryCount(summary: Record<string, unknown> | undefined, key: string) {
  const value = summary?.[key];
  return typeof value === "number" ? value : 0;
}

function compactAssetLabel(asset: AssetRegistryEntry) {
  const role = asset.role || asset.kind || "asset";
  const status = asset.integration_status || asset.quality_status || asset.status;
  return `${role} · ${status}`;
}

function permissionClass(mode: PermissionMode) {
  if (mode === "ask") return "permission-ask";
  if (mode === "full") return "permission-full";
  return "permission-auto";
}

function approvalSummary(modal: RuntimeModal) {
  const params = modal.params as Record<string, unknown>;
  const command = [
    params.command,
    params.cmd,
    params.commandLine,
    params.script,
    Array.isArray(params.commandActions) ? params.commandActions.map((item) => JSON.stringify(item)).join("\n") : "",
  ]
    .map((item) => String(item ?? "").trim())
    .find(Boolean) ?? "";
  const paths = extractApprovalPaths(params).slice(0, 8);
  const cwd = String(params.cwd ?? params.workingDirectory ?? "");
  const action =
    modal.method.includes("command") || modal.method.includes("exec")
      ? "Run command"
      : modal.method.includes("file") || modal.method.includes("Patch")
        ? "Modify files"
        : modal.method.includes("permissions")
          ? "Grant permission"
          : "Use tool";
  const risk = approvalRisk(modal.method, command, params);
  return {
    action,
    risk,
    cwd,
    command,
    paths,
    encodingRisk: hasUnsafeWindowsWrite(command),
    astrabridgeLogRisk: readsExplosiveAstraBridgeLog(command),
    reason: String(params.reason ?? params.explanation ?? params.description ?? "Codex needs your approval to continue this turn."),
  };
}

function approvalRisk(method: string, command: string, params: Record<string, unknown>) {
  const haystack = `${method}\n${command}\n${JSON.stringify(params).slice(0, 4000)}`.toLowerCase();
  if (haystack.includes("dangerfullaccess") || haystack.includes("danger-full-access") || haystack.includes("permissions")) return "high";
  if (/(remove-item|rm -rf|rmdir|del \/|format-|set-executionpolicy|reg delete|takeown|icacls|netsh|shutdown)/i.test(haystack)) return "high";
  if (/(invoke-webrequest|curl |wget |npm install|pip install|start-process|powershell|pwsh|python -c|node -e)/i.test(haystack)) return "medium";
  if (command.length > 700 || haystack.includes("write") || haystack.includes("patch")) return "medium";
  return "low";
}

function extractApprovalPaths(value: unknown, found: string[] = []): string[] {
  if (found.length >= 12) return found;
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (/^[A-Za-z]:[\\/]/.test(trimmed) || trimmed.startsWith("/") || trimmed.includes(".astrabridge") || trimmed.includes(".")) {
      if (trimmed.length < 260 && !found.includes(trimmed)) found.push(trimmed);
    }
    return found;
  }
  if (Array.isArray(value)) {
    for (const item of value) extractApprovalPaths(item, found);
    return found;
  }
  if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      if (/path|file|cwd|directory|root|target/i.test(key)) extractApprovalPaths(item, found);
    }
  }
  return found;
}

function clippedCommand(command: string) {
  const clean = command.replace(/\s+/g, " ").trim();
  if (!clean) return "No command text was provided by the runtime.";
  return clean.length > 220 ? `${clean.slice(0, 220)}...` : clean;
}

function ConversationNoticeBar({
  notices,
  onOpenSetup,
}: {
  notices: Array<{ key: string; text: string; tone?: "warning" | "danger" | "info"; action?: "setup" }>;
  onOpenSetup: () => void;
}) {
  if (notices.length === 0) return null;
  return (
    <div className="conversation-notice-bar" role="status">
      {notices.map((notice) => (
        <div className={`conversation-notice conversation-notice-${notice.tone ?? "warning"}`} key={notice.key}>
          <span className="notice-dot" aria-hidden="true" />
          {notice.action === "setup" ? (
            <button type="button" className="notice-link" onClick={onOpenSetup}>
              {notice.text}
            </button>
          ) : (
            <span>{notice.text}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function AvatarBadge({ label, imagePath, accentColor }: { label: string; imagePath?: string; accentColor?: string }) {
  const canRenderImage = isLocalImagePath(imagePath);
  return (
    <span className="message-avatar" style={{ ["--avatar-accent" as string]: accentColor || undefined }}>
      {canRenderImage ? <img src={imagePath!.startsWith("file:") ? imagePath! : localAssetUrl(imagePath!)} alt={label} /> : <span>{initials(label)}</span>}
    </span>
  );
}

function ReasoningPreview({ text, source, live, displayPolicy = "collapsed_3_lines" }: { text: string[]; source?: string; live?: boolean; displayPolicy?: string }) {
  const [expanded, setExpanded] = useState(displayPolicy === "expanded");
  const content = text.join("\n").trim();
  if (displayPolicy === "hidden") return null;
  if (!content) return null;
  const lines = content.split(/\r?\n/);
  const isLong = lines.length > 3 || content.length > 360;
  return (
    <section className={`reasoning-preview ${live ? "reasoning-preview-live" : ""}`}>
      <div className="reasoning-preview-header">
        <span>{source || "provider reasoning"}</span>
        {live ? <ActivityLine label="正在思考" compact /> : null}
      </div>
      <pre className={expanded ? "reasoning-preview-text expanded" : "reasoning-preview-text"}>{content}</pre>
      <div className="reasoning-preview-actions">
        {isLong ? (
          <button type="button" className="inline-link-button" onClick={() => setExpanded((value) => !value)}>
            {expanded ? "收起推理" : "展开全文"}
          </button>
        ) : null}
        <button type="button" className="inline-link-button" onClick={() => navigator.clipboard?.writeText(content).catch(() => undefined)}>
          复制
        </button>
      </div>
    </section>
  );
}

function ActivityLine({ label, compact = false }: { label: string; compact?: boolean }) {
  return (
    <span className={`activity-line ${compact ? "activity-line-compact" : ""}`}>
      <span className="activity-line-icon" aria-hidden="true" />
      <span className="activity-line-text">{label}</span>
    </span>
  );
}

function ExpandableActivityPreview({
  preview,
  detail,
  label = "Details",
}: {
  preview?: string;
  detail?: string;
  label?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const cleanPreview = String(preview || detail || "").replace(/\s+/g, " ").trim();
  const cleanDetail = String(detail || preview || "").trim();
  if (!cleanPreview && !cleanDetail) return null;
  return (
    <div className="activity-preview">
      <button type="button" className="activity-preview-toggle" onClick={() => setExpanded((value) => !value)} title={label}>
        <span aria-hidden="true">&gt;</span>
        <span>{cleanPreview || label}</span>
      </button>
      {expanded ? <pre>{cleanDetail || cleanPreview}</pre> : null}
    </div>
  );
}

function DiffProgressPill({ diff }: { diff?: RuntimeDiffSummary }) {
  if (!diff || (diff.added === 0 && diff.deleted === 0 && diff.files === 0)) return null;
  return (
    <span className="diff-progress-pill" title={`${diff.files} changed files`}>
      <span className="diff-added">+{diff.added.toLocaleString()}</span>
      <span className="diff-deleted">-{diff.deleted.toLocaleString()}</span>
    </span>
  );
}

function CollapsibleTextBlock({ text, maxLines = 5 }: { text: string; maxLines?: number }) {
  const [expanded, setExpanded] = useState(false);
  const cleanText = text || " ";
  const lineCount = cleanText.split(/\r?\n/).length;
  const isLong = lineCount > maxLines || cleanText.length > 620;
  return (
    <div className="collapsible-text">
      <p className={expanded || !isLong ? "collapsible-text-body" : "collapsible-text-body collapsed"}>{cleanText}</p>
      {isLong ? (
        <button type="button" className="inline-link-button collapsible-text-toggle" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "收起" : "... 展开"}
        </button>
      ) : null}
    </div>
  );
}

function activityLabel(activity: RuntimeActivityState) {
  if (activity.kind === "thinking") return "正在思考";
  if (activity.kind === "web_search") return "正在搜索";
  if (activity.kind === "command") return "正在执行命令";
  if (activity.kind === "file_change") return "正在修改文件";
  if (activity.kind === "compact") return "正在压缩上下文";
  if (activity.kind === "review") return "审查模式更新";
  if (activity.kind === "fork") return "创建协作线程";
  if (activity.kind === "mcp") return "正在调用 MCP 工具";
  if (activity.kind === "tool") return "正在调用工具";
  return activity.label || "正在等待";
}

function ActivityBlock({ activity, diff }: { activity: RuntimeActivityState; diff?: RuntimeDiffSummary }) {
  const active = activity.status === "active" || activity.status === "pending" || activity.status === "inProgress";
  return (
    <section className={`activity-block activity-${activity.kind} ${active ? "activity-active" : "activity-done"}`}>
      <div className="activity-block-head">
        {active ? <ActivityLine label={activityLabel(activity)} /> : <span className="activity-static-label">{activity.label}</span>}
        <DiffProgressPill diff={diff} />
        <span className="status-tag">{activity.status}</span>
      </div>
      <ExpandableActivityPreview preview={activity.preview} detail={activity.detail} label={activity.label} />
    </section>
  );
}

function ChatMessageRow({
  locale,
  block,
  providerName,
  modelName,
  providerLogoPath,
  providerAccent,
  userName,
  userAvatarPath,
  reasoningDisplayPolicy,
  onFork,
  onSave,
}: {
  locale: "en" | "zh-CN";
  block: ThreadRenderBlock;
  providerName: string;
  modelName: string;
  providerLogoPath?: string;
  providerAccent?: string;
  userName: string;
  userAvatarPath?: string;
  reasoningDisplayPolicy?: string;
  onFork: () => void;
  onSave: () => void;
}) {
  const isUser = block.role === "user";
  const isLive = block.role === "assistant_live";
  const actorName = isUser ? userName : modelName || providerName || "Assistant";
  const actorDetail = isUser ? t(locale, "manager_fact_users") : [providerName, modelName].filter(Boolean).join(" / ");
  const timeLabel = formatMessageTime(block.startedAt);
  const duration = isLive ? t(locale, "loading") : formatDuration(block.durationMs);
  return (
    <article className={`chat-message-row chat-message-${block.role}`}>
      <AvatarBadge
        label={actorName}
        imagePath={isUser ? userAvatarPath : providerLogoPath}
        accentColor={isUser ? undefined : providerAccent}
      />
      <div className="chat-message-shell">
        <header className="chat-message-meta">
          <strong>{actorName}</strong>
          <span>{actorDetail}</span>
          {timeLabel ? <time>{timeLabel}</time> : null}
        </header>
        <div className="chat-message-content">
          <MessageBlockContent block={block} reasoningDisplayPolicy={reasoningDisplayPolicy} />
        </div>
        {!isUser ? (
          <footer className="chat-message-footer">
            {duration ? <span>{duration}</span> : <span>-</span>}
            <button type="button" className="message-action-button" title={t(locale, "fork_thread")} aria-label={t(locale, "fork_thread")} onClick={onFork}>
              <GitFork size={14} strokeWidth={1.8} aria-hidden="true" />
            </button>
            <button type="button" data-testid="checkpoint-open" className="message-action-button" title={t(locale, "checkpoint_title")} aria-label={t(locale, "checkpoint_title")} onClick={onSave}>
              <Save size={14} strokeWidth={1.8} aria-hidden="true" />
            </button>
          </footer>
        ) : null}
      </div>
    </article>
  );
}

function MessageBlockContent({ block, reasoningDisplayPolicy }: { block: ThreadRenderBlock; reasoningDisplayPolicy?: string }) {
  if (block.role === "user") {
    return (
      <>
        <CollapsibleTextBlock text={block.text || " "} />
        {(block.attachments ?? []).length > 0 ? (
          <div className="attachment-list-inline">
            {(block.attachments ?? []).map((name) => (
              <span className="attachment-inline" key={name}>
                {name}
              </span>
            ))}
          </div>
        ) : null}
      </>
    );
  }
  if (block.role === "assistant" || block.role === "assistant_live") {
    return extractProposedPlanText(block.text) ? <PlanRenderer text={block.text} /> : <CollapsibleTextBlock text={block.text || " "} />;
  }
  if (block.role === "plan") return <PlanRenderer text={block.text} />;
  if (block.role === "reasoning") {
    return <ReasoningPreview text={block.text} source={block.source} live={block.live} displayPolicy={reasoningDisplayPolicy} />;
  }
  if (block.role === "activity") {
    return <ActivityBlock activity={block.activity} diff={block.diff} />;
  }
  if (block.role === "command") {
    return (
      <div className="command-activity-card">
        <ExpandableActivityPreview preview={block.command} detail={[block.command, block.output].filter(Boolean).join("\n\n")} label="命令" />
        <span className="status-tag">{block.status}</span>
      </div>
    );
  }
  if (block.role === "file_change") {
    const summaryBits = [
      typeof block.added === "number" ? `+${block.added}` : "",
      typeof block.deleted === "number" ? `-${block.deleted}` : "",
    ].filter(Boolean);
    return (
      <div className="change-card">
        <div className="change-card-header">
          <span className="change-card-icon">+</span>
          <strong>{block.status}</strong>
          <span>{block.files.length} 个文件</span>
          {summaryBits.length > 0 ? <span>{summaryBits.join(" / ")}</span> : null}
        </div>
        {block.detail ? <ExpandableActivityPreview preview={block.files.slice(0, 3).join(", ")} detail={block.detail} label="文件变更" /> : null}
        <div className="change-file-list">
          {block.files.map((file) => (
            <a className="change-file-link" href={`#${encodeURIComponent(file)}`} onClick={(event) => event.preventDefault()} title={file} key={file}>
              {file}
            </a>
          ))}
        </div>
      </div>
    );
  }
  if (block.role === "tool") {
    return (
      <div className="tool-activity-card">
        <ExpandableActivityPreview preview={block.title} detail={block.detail} label={block.title} />
        <span className="status-tag">{block.status}</span>
      </div>
    );
  }
  if (block.role === "image") return <img className="inline-image" src={localAssetUrl(block.path)} alt={block.path} />;
  return null;
}

function SaveCheckpointModal({
  locale,
  description,
  defaultDescription,
  projectName,
  threadName,
  isPending,
  error,
  onDescriptionChange,
  onCancel,
  onSave,
}: {
  locale: "en" | "zh-CN";
  description: string;
  defaultDescription: string;
  projectName: string;
  threadName: string;
  isPending: boolean;
  error: unknown;
  onDescriptionChange: (value: string) => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  return (
    <div className="modal-scrim">
      <div className="modal-card checkpoint-modal" data-testid="checkpoint-modal">
        <div className="card-header">
          <h2>{t(locale, "checkpoint_title")}</h2>
          <span className="status-tag">.astrabridge/saves</span>
        </div>
        <p className="muted compact-copy">{t(locale, "checkpoint_summary")}</p>
        <div className="checkpoint-facts">
          <div><span>{t(locale, "checkpoint_project")}</span><strong>{projectName}</strong></div>
          <div><span>{t(locale, "checkpoint_thread")}</span><strong>{threadName}</strong></div>
          <div><span>{t(locale, "checkpoint_default_description")}</span><strong>{defaultDescription}</strong></div>
        </div>
        <label className="field">
          <span>{t(locale, "checkpoint_description")}</span>
          <textarea rows={3} value={description} onChange={(event) => onDescriptionChange(event.target.value)} placeholder={defaultDescription} />
        </label>
        {error ? <p className="error-text">{String((error as Error).message ?? error)}</p> : null}
        <div className="modal-actions">
          <button type="button" data-testid="checkpoint-save" className="primary-button" disabled={isPending} onClick={onSave}>
            {isPending ? t(locale, "checkpoint_saving") : t(locale, "checkpoint_save")}
          </button>
          <button type="button" data-testid="checkpoint-cancel" className="ghost-button" onClick={onCancel}>{t(locale, "cancel")}</button>
        </div>
      </div>
    </div>
  );
}

type TextEntryRequest = {
  title: string;
  label: string;
  defaultValue: string;
  placeholder?: string;
  description?: string;
  submitLabel?: string;
  multiline?: boolean;
  resolve: (value: string | null) => void;
};

function TextEntryModal({
  request,
  onCancel,
  onSubmit,
}: {
  request: TextEntryRequest;
  onCancel: () => void;
  onSubmit: (value: string) => void;
}) {
  const [value, setValue] = useState(request.defaultValue);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select?.();
  }, [request]);

  return (
    <div className="modal-scrim">
      <div className="modal-card checkpoint-modal" data-testid="checkpoint-modal">
        <div className="card-header">
          <h2>{request.title}</h2>
        </div>
        {request.description ? <p className="muted">{request.description}</p> : null}
        <label className="field">
          <span>{request.label}</span>
          {request.multiline ? (
            <textarea
              ref={inputRef as React.RefObject<HTMLTextAreaElement>}
              rows={4}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder={request.placeholder ?? request.defaultValue}
            />
          ) : (
            <input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              type="text"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder={request.placeholder ?? request.defaultValue}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  onSubmit(value);
                }
              }}
            />
          )}
        </label>
        <div className="modal-actions">
          <button type="button" className="primary-button" onClick={() => onSubmit(value)}>
            {request.submitLabel ?? "Continue"}
          </button>
          <button type="button" className="ghost-button" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

function PlanRenderer({ text, compact = false }: { text: string; compact?: boolean }) {
  const [expanded, setExpanded] = useState(false);
  const card = useMemo(() => parsePlanCard(text), [text]);
  const showRaw = expanded || !card.isLong;
  return (
    <div className={`plan-card-rendered ${compact ? "plan-card-compact" : ""}`}>
      <div className="plan-card-topline">
        <span className="plan-card-icon">○</span>
        <div>
          <strong>{card.title}</strong>
          {card.summary.length > 0 ? <p>{card.summary[0]}</p> : null}
        </div>
      </div>
      {card.summary.length > 1 ? (
        <ul className="plan-card-summary">
          {card.summary.slice(1, compact ? 3 : 5).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {card.steps.length > 0 ? (
        <div className="plan-card-steps">
          {card.steps.slice(0, compact ? 4 : 8).map((step, index) => (
            <span key={`${step}-${index}`}>{step}</span>
          ))}
        </div>
      ) : null}
      {card.isLong ? (
        <button type="button" className="inline-link-button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Collapse plan" : "Show full plan"}
        </button>
      ) : null}
      {showRaw ? <pre className="plan-card-raw">{card.raw}</pre> : null}
    </div>
  );
}

function PlanProgressTimeline({ plan }: { plan: RuntimeSupervisorState["plan"] | undefined | null }) {
  const steps = plan?.steps ?? [];
  if (steps.length === 0) return <p className="muted">当前还没有结构化计划。</p>;
  const currentIndex = steps.findIndex((step) => ["inProgress", "in_progress"].includes(String(step.status)));
  return (
    <div className="plan-timeline">
      {plan?.explanation ? <p className="plan-timeline-explanation">{plan.explanation}</p> : null}
      {steps.map((step, index) => {
        const status = String(step.status || "pending");
        const normalizedStatus = status.replace(/([a-z])([A-Z])/g, "$1_$2").toLowerCase();
        const active = index === currentIndex || (currentIndex < 0 && status === "pending");
        const label =
          normalizedStatus === "in_progress"
            ? "in progress"
            : normalizedStatus === "completed"
              ? "completed"
              : normalizedStatus === "failed" || normalizedStatus === "cancelled"
                ? normalizedStatus
                : "pending";
        return (
          <div className={`timeline-step timeline-${normalizedStatus} ${active ? "timeline-active" : ""}`} key={`${step.step}-${index}`}>
            <span className="timeline-dot" aria-hidden="true" />
            <div>
              <small>{label}</small>
              <strong>{step.step}</strong>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EnvironmentStrip({
  locale,
  supervisor,
  fallback,
  recoveryActions = [],
  recoveryPendingAction = null,
  onRecoveryAction,
}: {
  locale: "en" | "zh-CN";
  supervisor?: RuntimeSupervisorState;
  fallback: { provider?: string; model?: string; effort?: string; permission?: string };
  recoveryActions?: RuntimeErrorAction[];
  recoveryPendingAction?: string | null;
  onRecoveryAction?: (action: RuntimeErrorAction) => void;
}) {
  const environment = supervisor?.environment;
  const token = supervisor?.token;
  const git = environment?.git;
  const browser = supervisor?.browser;
  const watchdog = supervisor?.watchdog;
  const runtimeError = supervisor?.runtime_error;
  const guardLevel = contextGuardLevel(token?.context_percent ?? 0);
  const contextLabel = token?.context_window ? `${token.context_percent}%` : "n/a";
  return (
    <section className={`environment-strip guard-${guardLevel}`}>
      {runtimeError ? (
        <>
          <div className="environment-strip-row environment-strip-wide environment-error-row">
            <span>{t(locale, "inspector_runtime")}</span>
            <strong>{runtimeError.category === "provider_timeout" ? "provider 超时" : runtimeError.category || "错误"}</strong>
          </div>
          <div className="environment-strip-row environment-strip-wide environment-error-copy">
            <span>{t(locale, "inspector_recovery")}</span>
            <strong>{runtimeErrorNoticeText(runtimeError)}</strong>
            {recoveryActions.length > 0 ? (
              <div className="environment-error-actions">
                {recoveryActions.map((action) => {
                  const pending = recoveryPendingAction === action.action;
                  return (
                    <button
                      key={`${action.action}:${action.target ?? ""}:${action.label}`}
                      type="button"
                      className="ghost-button environment-action-button"
                      disabled={pending || !onRecoveryAction}
                      onClick={() => onRecoveryAction?.(action)}
                    >
                      {pending ? t(locale, "inspector_processing") : action.label}
                    </button>
                  );
                })}
              </div>
            ) : null}
          </div>
        </>
      ) : null}
      <div className="environment-strip-row">
        <span>{t(locale, "inspector_provider")}</span>
        <strong>{fallback.provider || environment?.provider || "-"}</strong>
      </div>
      <div className="environment-strip-row">
        <span>{t(locale, "inspector_model")}</span>
        <strong>{environment?.model || fallback.model || "-"}</strong>
      </div>
      <div className="environment-strip-row">
        <span>{t(locale, "inspector_effort")}</span>
        <strong>{environment?.effort || fallback.effort || "-"}</strong>
      </div>
      <div className="environment-strip-row">
        <span>{t(locale, "inspector_permission")}</span>
        <strong>{environment?.permission || fallback.permission || "-"}</strong>
      </div>
      <div className="environment-strip-row">
        <span>{t(locale, "inspector_context")}</span>
        <strong>{contextLabel}</strong>
      </div>
      <div className="environment-strip-row">
        <span>{t(locale, "inspector_idle")}</span>
        <strong>{watchdog?.idle_seconds ? `${watchdog.idle_seconds}s` : t(locale, "inspector_normal")}</strong>
      </div>
      <div className="environment-strip-row">
        <span>{t(locale, "inspector_git")}</span>
        <strong>{git?.is_repo ? `${git.branch || "repo"} · +${git.added} -${git.deleted}` : t(locale, "inspector_non_git")}</strong>
      </div>
      <div className="environment-strip-row environment-strip-wide">
        <span>{t(locale, "inspector_browser")}</span>
        <strong>{browser?.status === "pass" ? `${t(locale, "inspector_pass")} · ${browser.label || browser.url}` : browser?.status ? productStatusLabel(browser.status) : t(locale, "inspector_not_run")}</strong>
      </div>
      <div className="environment-strip-row environment-strip-wide">
        <span>{t(locale, "inspector_mcp")}</span>
        <strong>{productStatusLabel(environment?.mcp?.status)}</strong>
      </div>
    </section>
  );
}

function SupervisorGuardModal({
  supervisor,
  onDecision,
  onDismiss,
}: {
  supervisor: RuntimeSupervisorState;
  onDecision: (action: "continue" | "compact" | "fork" | "interrupt") => void;
  onDismiss: () => void;
}) {
  return (
    <div className="modal-scrim">
      <div className="modal-card supervisor-modal">
        <div className="card-header">
          <h2>上下文保护</h2>
          <span className={`status-tag guard-tag-${supervisor.guard.level}`}>{supervisor.guard.level}</span>
        </div>
        <p>{supervisor.guard.message || "当前回合已经接近长任务安全上限。"}</p>
        {supervisor.guard.auto_pause ? (
          <p className={`guard-auto-pause guard-auto-pause-${supervisor.guard.auto_pause.status}`}>
            自动暂停：{supervisor.guard.auto_pause.status}
            {supervisor.guard.auto_pause.error ? ` · ${supervisor.guard.auto_pause.error}` : ""}
          </p>
        ) : null}
        <div className="context-meter">
          <div style={{ width: `${Math.min(100, supervisor.token.context_percent)}%` }} />
        </div>
        <p className="muted">
          {supervisor.token.total_tokens.toLocaleString()} / {supervisor.token.context_window.toLocaleString()} tokens
        </p>
        <div className="modal-actions modal-actions-wrap">
          <button type="button" className="primary-button" onClick={() => onDecision("compact")}>压缩后继续</button>
          <button type="button" className="ghost-button" onClick={() => onDecision("fork")}>创建分支线程</button>
          <button type="button" className="ghost-button" onClick={() => onDecision("continue")}>继续下一回合</button>
          <button type="button" className="danger-button" onClick={() => onDecision("interrupt")}>中断</button>
          <button type="button" className="ghost-button" onClick={onDismiss}>稍后处理</button>
        </div>
      </div>
    </div>
  );
}

function useResizablePane(kind: "left" | "right") {
  const width = useAppStore((store) => (kind === "left" ? store.leftSidebarWidth : store.rightSidebarWidth));
  const setWidth = useAppStore((store) => (kind === "left" ? store.setLeftSidebarWidth : store.setRightSidebarWidth));
  const draggingRef = useRef(false);

  useEffect(() => {
    function onMove(event: MouseEvent) {
      if (!draggingRef.current) return;
      if (kind === "left") {
        setWidth(event.clientX);
      } else {
        setWidth(window.innerWidth - event.clientX);
      }
    }
    function onUp() {
      draggingRef.current = false;
      document.body.classList.remove("resizing");
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [kind, setWidth]);

  return {
    width,
    bind: {
      onMouseDown: () => {
        draggingRef.current = true;
        document.body.classList.add("resizing");
      },
    },
  };
}

function RouterControlCenter({
  locale,
  queryClient,
  fallbackCheckpoints,
}: {
  locale: "en" | "zh-CN";
  queryClient: ReturnType<typeof useQueryClient>;
  fallbackCheckpoints: ProjectCheckpoint[];
}) {
  const project = useAppStore((store) => store.project);
  const setProject = useAppStore((store) => store.setProject);
  const setLocale = useAppStore((store) => store.setLocale);
  const appearance = useAppStore((store) => store.appearance);
  const setAppearance = useAppStore((store) => store.setAppearance);
  const profiles = useQuery({ queryKey: ["profiles"], queryFn: api.profiles, refetchInterval: 10000 });
  const routerConfig = useQuery({ queryKey: ["router-config"], queryFn: api.routerConfig, refetchInterval: 5000 });
  const capabilityRoutes = useQuery({ queryKey: ["capability-routes"], queryFn: api.capabilityRoutes, refetchInterval: 5000 });
  const capabilityManagement = useQuery({ queryKey: ["capability-management"], queryFn: api.capabilityManagement, refetchInterval: 5000 });
  const llmSession = useQuery({ queryKey: ["llm-manager-session"], queryFn: api.llmManagerSession, refetchInterval: 5000 });
  const llmKeys = useQuery({ queryKey: ["llm-manager-keys"], queryFn: api.llmManagerKeys, refetchInterval: 5000 });
  const llmCatalog = useQuery({ queryKey: ["llm-manager-catalog"], queryFn: api.llmManagerEffectiveCatalog, refetchInterval: 5000 });
  const llmHealth = useQuery({ queryKey: ["llm-manager-health"], queryFn: api.llmManagerHealthResults, refetchInterval: 7000 });
  const metadataSources = useQuery({ queryKey: ["metadata-sources"], queryFn: api.metadataSources });
  const mcpConfig = useQuery({ queryKey: ["mcp-config"], queryFn: api.mcpConfig, refetchInterval: 5000 });
  const dogfoodRun = useQuery({ queryKey: ["dogfood-run"], queryFn: api.dogfoodRun, refetchInterval: 5000 });
  const dogfoodAssets = useQuery({ queryKey: ["dogfood-assets"], queryFn: api.dogfoodAssets, refetchInterval: 7000, retry: false });
  const projectSaves = useQuery({ queryKey: ["project-saves", project?.project_id], queryFn: api.projectSaves, refetchInterval: 7000 });
  const automations = useQuery({
    queryKey: ["automations", project?.project_id],
    queryFn: api.automations,
    enabled: Boolean(project?.project_id),
    refetchInterval: 7000,
  });
  const automationRuns = useQuery({
    queryKey: ["automations-runs", project?.project_id],
    queryFn: () => api.automationRuns(),
    enabled: Boolean(project?.project_id),
    refetchInterval: 7000,
  });
  const automationInbox = useQuery({
    queryKey: ["automations-inbox", project?.project_id],
    queryFn: () => api.automationInbox(null, true),
    enabled: Boolean(project?.project_id),
    refetchInterval: 7000,
  });
  const automationScheduler = useQuery({
    queryKey: ["automations-scheduler", project?.project_id],
    queryFn: api.automationSchedulerStatus,
    enabled: Boolean(project?.project_id),
    refetchInterval: 7000,
  });
  const setupTabs = ["login", "users", "keys", "providers", "models", "capabilities", "health", "mcp", "extensions", "runtime", "automations", "saves", "dogfood", "reports"] as const;
  const [tab, setTab] = useState<(typeof setupTabs)[number]>("login");
  const capabilityArtifacts = useQuery({ queryKey: ["capability-artifacts"], queryFn: () => api.capabilityArtifacts(20), enabled: tab === "capabilities", refetchInterval: 10000, retry: false });
  const [providerDraft, setProviderDraft] = useState<RouterProvider | null>(null);
  const [modelDraft, setModelDraft] = useState<RouterModelEntry | null>(null);
  const [mcpDraft, setMcpDraft] = useState<McpServerConfig | null>(null);
  const [reasoningDraft, setReasoningDraft] = useState<ReasoningConfig | null>(null);
  const [importDraft, setImportDraft] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [managerUsername, setManagerUsername] = useState("user");
  const [managerPassword, setManagerPassword] = useState("");
  const [managerNewPassword, setManagerNewPassword] = useState("");
  const [managerOldPassword, setManagerOldPassword] = useState("");
  const [managerDisplayName, setManagerDisplayName] = useState("");
  const [managerAvatarPath, setManagerAvatarPath] = useState("");
  const [managedKeyDraft, setManagedKeyDraft] = useState({ label: "", secret: "", env_key: "" });
  const [selectedKeyId, setSelectedKeyId] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [capabilityRouteDrafts, setCapabilityRouteDrafts] = useState<Record<string, { mode: "auto" | "pinned"; provider_id?: string | null; model?: string | null }>>({});
  const [capabilitySmokeResults, setCapabilitySmokeResults] = useState<Record<string, CapabilitySmokeResult>>({});
  const mcpStatus = useQuery({ queryKey: ["mcp-status", selectedProviderId], queryFn: () => api.mcpStatus({ profile_id: selectedProviderId ? `${selectedProviderId}-default` : undefined, detail: "toolsAndAuthOnly" }), enabled: (tab === "mcp" || tab === "capabilities") && Boolean(selectedProviderId), refetchInterval: 7000, retry: false });
  const [wslSetupDistro, setWslSetupDistro] = useState("Ubuntu-24.04");
  const wslDependencies = useQuery({ queryKey: ["wsl-dependencies", wslSetupDistro], queryFn: () => api.wslDependencies(wslSetupDistro), refetchInterval: 15000, retry: false });
  const runtimeKernelProbe = useQuery({
    queryKey: ["runtime-kernel-probe", project?.project_id],
    queryFn: () => api.runtimeKernelProbe(),
    enabled: tab === "runtime" && Boolean(project?.project_id),
    refetchInterval: 15000,
    retry: false,
  });
  const runtimePluginSkillRegistry = useQuery({
    queryKey: ["runtime-plugin-skill-registry", project?.project_id],
    queryFn: () => api.runtimePluginSkillRegistry(),
    enabled: (tab === "extensions" || tab === "capabilities") && Boolean(project?.project_id),
    refetchInterval: 15000,
    retry: false,
  });
  const [modelSearch, setModelSearch] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [testOutput, setTestOutput] = useState<string>("");
  const [metadataOutput, setMetadataOutput] = useState<string>("");
  const [metadataRefreshJobId, setMetadataRefreshJobId] = useState<string | null>(null);
  const [mcpOutput, setMcpOutput] = useState<string>("");
  const [wslSetupOutput, setWslSetupOutput] = useState("");
  const [dogfoodDraft, setDogfoodDraft] = useState<DogfoodRun | null>(null);
  const [dogfoodSmokeUrl, setDogfoodSmokeUrl] = useState("http://127.0.0.1:8123/");
  const [dogfoodSmokeLabel, setDogfoodSmokeLabel] = useState("game smoke");
  const [dogfoodScreenshotPath, setDogfoodScreenshotPath] = useState("");
  const [dogfoodMilestoneLabel, setDogfoodMilestoneLabel] = useState("Milestone");
  const [dogfoodMilestoneValidation, setDogfoodMilestoneValidation] = useState("Browser smoke passed");
  const [assetPromoteDraft, setAssetPromoteDraft] = useState({ asset_id: "", target_name: "", manifest_section: "sprites" as "sprites" | "tiles" | "hud", entity: "", state: "" });
  const effectiveCatalog = useQuery({
    queryKey: ["effective-catalog", modelDraft?.id],
    queryFn: () => api.effectiveCatalog(modelDraft?.id),
    enabled: Boolean(modelDraft?.id),
  });
  const isolationAudit = useQuery({
    queryKey: ["isolation-audit", project?.project_id],
    queryFn: api.isolationAudit,
    enabled: Boolean(project?.project_id),
    refetchInterval: 15000,
    retry: false,
  });
  const captureRoot = useMemo(() => projectCaptureRoot(project), [project]);
  const suggestedScreenshotPath = useMemo(
    () => suggestedDogfoodScreenshotPath(project, dogfoodSmokeLabel),
    [project, dogfoodSmokeLabel],
  );
  const isolationSummary = useMemo(() => isolationAuditSummary(isolationAudit.data), [isolationAudit.data]);
  const visibleCheckpoints = useMemo(() => {
    const saves = projectSaves.data?.saves ?? [];
    return saves.length > 0 ? saves : fallbackCheckpoints;
  }, [fallbackCheckpoints, projectSaves.data?.saves]);

  useEffect(() => {
    const current = dogfoodScreenshotPath.trim();
    if (!suggestedScreenshotPath) return;
    const usingLegacyDefault = /^d:\\workflow(\\|$)/i.test(current);
    if ((!current || usingLegacyDefault) && current !== suggestedScreenshotPath) {
      setDogfoodScreenshotPath(suggestedScreenshotPath);
    }
  }, [dogfoodScreenshotPath, suggestedScreenshotPath]);

  useEffect(() => {
    const next: Record<string, { mode: "auto" | "pinned"; provider_id?: string | null; model?: string | null }> = {};
    for (const route of capabilityManagement.data?.routes ?? capabilityRoutes.data?.routes ?? routerConfig.data?.capability_routes ?? []) {
      next[route.capability_id] = {
        mode: route.route_record.mode,
        provider_id: route.route_record.provider_id ?? null,
        model: route.route_record.model ?? null,
      };
    }
    if (Object.keys(next).length > 0) {
      setCapabilityRouteDrafts(next);
    }
  }, [capabilityManagement.data?.routes, capabilityRoutes.data?.routes, routerConfig.data?.capability_routes]);

  const saveProvider = useMutation({
    mutationFn: api.saveProvider,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["router-config"] }),
  });
  const saveModel = useMutation({
    mutationFn: api.saveModelCatalogEntry,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["router-config"] }),
  });
  const saveReasoning = useMutation({
    mutationFn: api.saveReasoningConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["router-config"] }),
  });
  const saveCapabilityRoute = useMutation({
    mutationFn: api.saveCapabilityRoute,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["router-config"] });
      queryClient.invalidateQueries({ queryKey: ["capability-routes"] });
      queryClient.invalidateQueries({ queryKey: ["capability-management"] });
      queryClient.invalidateQueries({ queryKey: ["capability-artifacts"] });
    },
  });
  const runCapabilitySmoke = useMutation({
    mutationFn: api.capabilitySmoke,
    onSuccess: (response) => {
      setCapabilitySmokeResults((current) => ({
        ...current,
        [response.smoke.capability_id]: response.smoke,
      }));
      queryClient.invalidateQueries({ queryKey: ["capability-management"] });
    },
  });
  const invalidateAutomationQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["automations", project?.project_id] });
    queryClient.invalidateQueries({ queryKey: ["automations-runs", project?.project_id] });
    queryClient.invalidateQueries({ queryKey: ["automations-inbox", project?.project_id] });
    queryClient.invalidateQueries({ queryKey: ["automations-scheduler", project?.project_id] });
    queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
  };
  const createAutomation = useMutation({ mutationFn: api.createAutomation, onSuccess: invalidateAutomationQueries });
  const updateAutomation = useMutation({
    mutationFn: ({ automationId, patch }: { automationId: string; patch: Record<string, unknown> }) => api.updateAutomation(automationId, patch),
    onSuccess: invalidateAutomationQueries,
  });
  const deleteAutomation = useMutation({ mutationFn: (automationId: string) => api.deleteAutomation(automationId), onSuccess: invalidateAutomationQueries });
  const pauseAutomation = useMutation({ mutationFn: (automationId: string) => api.pauseAutomation(automationId), onSuccess: invalidateAutomationQueries });
  const resumeAutomation = useMutation({ mutationFn: (automationId: string) => api.resumeAutomation(automationId), onSuccess: invalidateAutomationQueries });
  const runAutomationNow = useMutation({ mutationFn: (automationId: string) => api.runAutomationNow(automationId), onSuccess: invalidateAutomationQueries });
  const cancelAutomationRun = useMutation({ mutationFn: (runId: string) => api.cancelAutomationRun(runId), onSuccess: invalidateAutomationQueries });
  const updateAutomationInboxItem = useMutation({
    mutationFn: ({ itemId, patch }: { itemId: string; patch: Record<string, unknown> }) => api.updateAutomationInboxItem(itemId, patch),
    onSuccess: invalidateAutomationQueries,
  });
  const promoteAutomationInboxItem = useMutation({
    mutationFn: ({ itemId, promotionRef }: { itemId: string; promotionRef: string }) => api.promoteAutomationInboxItem(itemId, promotionRef),
    onSuccess: invalidateAutomationQueries,
  });
  const importSeed = useMutation({
    mutationFn: () => api.importMetadataSeed(true),
    onSuccess: (data) => {
      setMetadataOutput(`Imported ${data.providers.length} providers and ${data.model_count} model records.`);
      queryClient.invalidateQueries({ queryKey: ["router-config"] });
      queryClient.invalidateQueries({ queryKey: ["effective-catalog"] });
    },
  });
  const metadataRefreshStatus = useQuery({
    queryKey: ["metadata-refresh-status", metadataRefreshJobId],
    queryFn: () => api.metadataRefreshStatus(metadataRefreshJobId),
    enabled: Boolean(metadataRefreshJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" ? 1200 : false;
    },
  });
  const startMetadataRefresh = useMutation({
    mutationFn: (apply: boolean) => api.startMetadataRefresh(apply),
    onSuccess: (data) => {
      setMetadataRefreshJobId(data.job_id);
      setMetadataOutput(`${data.apply ? "Apply" : "Preview"} refresh started.\nJob: ${data.job_id}`);
    },
  });
  useEffect(() => {
    const status = metadataRefreshStatus.data;
    if (!status || !metadataRefreshJobId || status.job_id !== metadataRefreshJobId || status.status === "running" || status.status === "idle") return;
    const summary = status.summary;
    const rows = (status.source_results ?? []).map((item) => {
      const record = item as Record<string, unknown>;
      const state = String(record.classification ?? (record.ok ? "ok" : "warn"));
      return `${String(record.provider_id ?? "-")}: ${state} ${String(record.url ?? "")}`.trim();
    });
    const artifactLines = Object.entries(status.artifact_paths ?? {})
      .filter(([, value]) => Boolean(value))
      .map(([key, value]) => `${key}: ${value}`);
    setMetadataOutput(
      [
        `Refresh ${status.status}.`,
        summary ? `Sources ${summary.ok_sources}/${summary.total_sources} ok.` : "",
        ...rows,
        ...artifactLines,
      ].filter(Boolean).join("\n"),
    );
    queryClient.invalidateQueries({ queryKey: ["router-config"] });
    queryClient.invalidateQueries({ queryKey: ["metadata-sources"] });
    queryClient.invalidateQueries({ queryKey: ["effective-catalog"] });
  }, [metadataRefreshStatus.data, metadataRefreshJobId, queryClient]);
  const runMatrix = useMutation({
    mutationFn: () => api.testMatrix({ model_ids: modelDraft?.id ? [modelDraft.id] : undefined, temperatures: [0, 0.7, 1, 2], max_cases: modelDraft?.id ? 8 : 24 }),
    onSuccess: (data) => {
      const passCount = data.results.filter((item) => item.ok).length;
      setMetadataOutput(`Matrix finished: ${passCount}/${data.results.length} passed. Report: ${data.report.path}`);
    },
  });
  const generateReport = useMutation({
    mutationFn: api.metadataReport,
    onSuccess: (data) => setMetadataOutput(`Report written: ${data.path}`),
  });
  const applyContext7 = useMutation({
    mutationFn: api.applyContext7Preset,
    onSuccess: (data) => {
      setMcpDraft(data.server);
      setMcpOutput("Context7 preset installed. Reload runtime MCP to expose it to Codex.");
      queryClient.invalidateQueries({ queryKey: ["mcp-config"] });
    },
  });
  const applyYunwuImage = useMutation({
    mutationFn: api.applyYunwuImagePreset,
    onSuccess: (data) => {
      setMcpDraft(data.server);
      setMcpOutput("Yunwu Image Tool installed. It reads YUNWU_API_KEY from the runtime environment and uses approval prompts by default.");
      queryClient.invalidateQueries({ queryKey: ["mcp-config"] });
    },
  });
  const applyAstraBridgeCapabilities = useMutation({
    mutationFn: api.applyAstraBridgeCapabilitiesPreset,
    onSuccess: (data) => {
      setMcpDraft(data.server);
      setMcpOutput("AstraBridge Capability Runtime installed. It exposes capability routes plus image, vision, speech transcribe, and speech synthesize tools through the current capability routing config.");
      queryClient.invalidateQueries({ queryKey: ["mcp-config"] });
      queryClient.invalidateQueries({ queryKey: ["capability-management"] });
      queryClient.invalidateQueries({ queryKey: ["mcp-status", selectedProviderId] });
    },
  });
  const testYunwuImage = useMutation({
    mutationFn: () => api.testYunwuImage(),
    onSuccess: (data) => {
      const urls = data.data.map((item) => item.url).filter(Boolean).join("\n");
      setMcpOutput(`Yunwu image smoke passed in ${data.elapsed_ms}ms.\n${urls || "No URL returned; inspect response format."}`);
    },
    onError: (error) => setMcpOutput(String((error as Error).message ?? error)),
  });
  const saveMcpServer = useMutation({
    mutationFn: api.saveMcpServer,
    onSuccess: (data) => {
      setMcpDraft(data.server);
      queryClient.invalidateQueries({ queryKey: ["mcp-config"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    },
  });
  const reloadMcp = useMutation({
    mutationFn: () => api.reloadMcp(selectedProviderId ? `${selectedProviderId}-default` : undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mcp-status"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    },
  });
  const writeWslScripts = useMutation({
    mutationFn: () => api.writeWslBootstrapScripts(wslSetupDistro),
    onSuccess: async (data) => {
      const output = `Scripts written.\nWindows: ${data.windows_script_path}\nWSL: ${data.wsl_script_path}\nRun: ${data.run_command}`;
      setWslSetupOutput(output);
      await navigator.clipboard?.writeText(data.run_command).catch(() => undefined);
      queryClient.invalidateQueries({ queryKey: ["wsl-dependencies"] });
    },
  });
  const launchWslInstaller = useMutation({
    mutationFn: () => api.launchWslBootstrapInstaller(wslSetupDistro),
    onSuccess: (data) => {
      setWslSetupOutput(`Installer launched in a separate terminal.\nWindows: ${data.windows_script_path}\nRun: ${data.run_command}`);
      queryClient.invalidateQueries({ queryKey: ["wsl-dependencies"] });
    },
  });
  const loadSecret = useMutation({
    mutationFn: ({ profileId, payload }: { profileId: string; payload: { session_key?: string; persist_to_keychain?: boolean } }) =>
      api.loadSecret(profileId, payload),
    onSuccess: () => {
      setSecretValue("");
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    },
  });
  const loginManager = useMutation({
    mutationFn: api.llmManagerLogin,
    onSuccess: () => {
      setManagerPassword("");
      queryClient.invalidateQueries({ queryKey: ["llm-manager-session"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-keys"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-catalog"] });
    },
  });
  const logoutManager = useMutation({
    mutationFn: api.llmManagerLogout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["llm-manager-session"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-keys"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-catalog"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    },
  });
  const createManagerUser = useMutation({
    mutationFn: api.llmManagerCreateUser,
    onSuccess: () => {
      setManagerPassword("");
      queryClient.invalidateQueries({ queryKey: ["llm-manager-session"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-keys"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-catalog"] });
    },
  });
  const changeManagerPassword = useMutation({
    mutationFn: api.llmManagerChangePassword,
    onSuccess: () => {
      setManagerOldPassword("");
      setManagerNewPassword("");
      queryClient.invalidateQueries({ queryKey: ["llm-manager-session"] });
    },
  });
  const saveManagerProfile = useMutation({
    mutationFn: api.llmManagerSaveUserProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["llm-manager-session"] });
    },
  });
  const saveManagedKey = useMutation({
    mutationFn: api.llmManagerSaveKey,
    onSuccess: () => {
      setManagedKeyDraft({ label: "", secret: "", env_key: "" });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-keys"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-catalog"] });
    },
  });
  const testManagedKey = useMutation({
    mutationFn: api.llmManagerTestKey,
    onSuccess: (data) => {
      const diagnosticsText = formatResponseDiagnostics(data.result.response_diagnostics);
      const failureText = runtimeErrorNoticeText(data.result.failure_notice ?? null);
      setTestOutput(diagnosticsText ?? (failureText || data.result.response_excerpt || JSON.stringify(data.result, null, 2)));
      queryClient.invalidateQueries({ queryKey: ["llm-manager-keys"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-catalog"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    },
  });
  const runHealth = useMutation({
    mutationFn: api.llmManagerRunHealth,
    onSuccess: (data) => {
      setMetadataOutput(`Health check updated ${Object.keys(data.model_health ?? {}).length} model records.`);
      queryClient.invalidateQueries({ queryKey: ["llm-manager-health"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-catalog"] });
      queryClient.invalidateQueries({ queryKey: ["router-config"] });
    },
  });
  const saveDogfood = useMutation({
    mutationFn: api.saveDogfoodRun,
    onSuccess: (data) => {
      setDogfoodDraft(data.run);
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });
  const rebuildDogfoodAssets = useMutation({
    mutationFn: api.rebuildDogfoodAssets,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dogfood-assets"] });
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });
  const promoteDogfoodAsset = useMutation({
    mutationFn: () => api.promoteDogfoodAsset({
      asset_id: assetPromoteDraft.asset_id,
      target_name: assetPromoteDraft.target_name || undefined,
      manifest_section: assetPromoteDraft.manifest_section,
      entity: assetPromoteDraft.entity || undefined,
      state: assetPromoteDraft.state || undefined,
      tile_key: assetPromoteDraft.manifest_section === "tiles" ? assetPromoteDraft.state || undefined : undefined,
    }),
    onSuccess: () => {
      setAssetPromoteDraft({ asset_id: "", target_name: "", manifest_section: "sprites", entity: "", state: "" });
      queryClient.invalidateQueries({ queryKey: ["dogfood-assets"] });
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });
  const runDogfoodBrowserSmoke = useMutation({
    mutationFn: () => api.dogfoodBrowserSmoke({ url: dogfoodSmokeUrl, label: dogfoodSmokeLabel, screenshot_path: dogfoodScreenshotPath || undefined, actions: DEFAULT_GAMEPLAY_SMOKE_ACTIONS }),
    onSuccess: (data) => {
      if (data.run) {
        setDogfoodDraft(data.run);
      }
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });
  const previewCheckpoint = useMutation({
    mutationFn: (saveId: string) => api.loadProjectSave({ save_id: saveId, preview: true }),
  });
  const loadCheckpoint = useMutation({
    mutationFn: (saveId: string) => api.loadProjectSave({ save_id: saveId, confirm_dirty: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-saves"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
    },
  });
  const deleteCheckpoint = useMutation({
    mutationFn: api.deleteProjectSave,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-saves"] }),
  });
  const saveDogfoodMilestone = useMutation({
    mutationFn: () => {
      const currentDogfood = dogfoodDraft ?? dogfoodRun.data?.run ?? null;
      return api.dogfoodMilestone({
        label: dogfoodMilestoneLabel,
        provider: currentDogfood?.current_provider,
        model: modelDraft?.id,
        goal: currentDogfood?.goal,
        plan_step: currentDogfood?.phase,
        status: "recorded",
        captures: (currentDogfood?.captures ?? []).slice(0, 4).map(capturePath),
        validation: dogfoodMilestoneValidation.split(/\n/).map((line) => line.trim()).filter(Boolean),
        next_step: currentDogfood?.next_step,
        next_action: currentDogfood?.next_step,
      });
    },
    onSuccess: (data) => {
      if (data.run) setDogfoodDraft(data.run);
      else setDogfoodDraft(null);
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });

  const selectedProvider = routerConfig.data?.providers.find((item) => item.id === selectedProviderId) ?? null;
  const selectedManagedKey = (llmKeys.data?.keys ?? []).find((item) => item.key_id === selectedKeyId) ?? null;
  const managerMode = llmSession.data?.mode ?? "anonymous";
  const managerStatusLabel =
    managerMode === "managed_user"
      ? t(locale, "manager_status_managed").replace("{user}", llmSession.data?.username ?? "user")
      : t(locale, "manager_status_anonymous");

  useEffect(() => {
    if (!providerDraft && routerConfig.data?.providers?.[0]) setProviderDraft(routerConfig.data.providers[0]);
    if (!selectedProviderId && routerConfig.data?.providers?.[0]?.id) setSelectedProviderId(routerConfig.data.providers[0].id);
    if (!modelDraft && routerConfig.data?.models?.[0]) setModelDraft(routerConfig.data.models[0]);
    if (!mcpDraft && mcpConfig.data?.servers?.[0]) setMcpDraft(mcpConfig.data.servers[0]);
    if (!reasoningDraft && routerConfig.data?.reasoning) setReasoningDraft(routerConfig.data.reasoning);
  }, [mcpConfig.data, mcpDraft, modelDraft, providerDraft, reasoningDraft, routerConfig.data, selectedProviderId]);

  useEffect(() => {
    if (!dogfoodDraft && dogfoodRun.data?.run) setDogfoodDraft(dogfoodRun.data.run);
  }, [dogfoodDraft, dogfoodRun.data?.run]);

  useEffect(() => {
    const profile = llmSession.data?.profile;
    if (!profile) return;
    setManagerDisplayName(profile.display_name ?? "");
    setManagerAvatarPath(profile.avatar_path ?? "");
  }, [llmSession.data?.profile]);

  useEffect(() => {
    const providerKeys = (llmKeys.data?.keys ?? []).filter((item) => item.provider_id === selectedProviderId);
    if (!providerKeys.some((item) => item.key_id === selectedKeyId)) {
      setSelectedKeyId(providerKeys[0]?.key_id ?? "");
    }
    if (selectedProvider && !managedKeyDraft.env_key) {
      setManagedKeyDraft((current) => ({ ...current, env_key: selectedProvider.env_key ?? "" }));
    }
  }, [llmKeys.data?.keys, managedKeyDraft.env_key, selectedKeyId, selectedProvider, selectedProviderId]);
  const filteredModels = useMemo(() => {
    const needle = modelSearch.trim().toLowerCase();
    const models = routerConfig.data?.models ?? [];
    if (!needle) return models;
    return models.filter((model) =>
      [model.id, model.display_name, model.provider, model.native_model, model.source_status ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(needle),
    );
  }, [modelSearch, routerConfig.data?.models]);
  const selectedCatalogEntry = useMemo(() => {
    const entries = effectiveCatalog.data?.models ?? [];
    const selectedId = modelDraft?.id ?? "";
    if (!selectedId) {
      return entries[0] ?? null;
    }
    return entries.find((item) => item.id === selectedId) ?? null;
  }, [effectiveCatalog.data?.models, modelDraft?.id]);

  async function handlePayloadPreview() {
    const sourceProvider = providerDraft ?? selectedProvider;
    if (!sourceProvider) return;
    const model = modelDraft?.id || `${sourceProvider.id}/${sourceProvider.default_model}`;
    const response = await api.previewPayload({ model, input: "Reply with exactly: ok", stream: false });
    setPreview(response.upstream_payload);
  }

  async function handleProviderTest(stream: boolean) {
    const sourceProvider = providerDraft ?? selectedProvider;
    if (!sourceProvider) return;
    const result = await api.testProvider({ provider_id: sourceProvider.id, model_id: modelDraft?.id, stream });
    const diagnosticsText = formatResponseDiagnostics(result.response_diagnostics);
    const failureText = runtimeErrorNoticeText(result.failure_notice ?? null);
    setTestOutput(diagnosticsText ?? (failureText || result.response_excerpt));
    queryClient.invalidateQueries({ queryKey: ["router-config"] });
    queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
  }

  async function handleExport() {
    const exported = await api.exportRouterConfig();
    setImportDraft(JSON.stringify(exported, null, 2));
  }

  async function handleImport() {
    const parsed = JSON.parse(importDraft) as RouterConfigResponse;
    await api.importRouterConfig(parsed);
    queryClient.invalidateQueries({ queryKey: ["router-config"] });
  }

  const capabilityRouteEntries: CapabilityRouteEntry[] = capabilityManagement.data?.routes ?? capabilityRoutes.data?.routes ?? routerConfig.data?.capability_routes ?? [];
  const capabilityMcpPreset = capabilityManagement.data?.mcp_preset ?? null;
  const capabilityMcpRuntime = mcpStatus.data?.servers.find((server) => server.name === "astrabridge_capabilities") ?? null;
  const capabilityMcpRuntimeVisible = capabilityMcpRuntime ? true : mcpStatus.data ? false : null;
  const capabilityMcpRuntimeToolCount = capabilityMcpRuntime ? Object.keys(capabilityMcpRuntime.tools ?? {}).length : 0;
  const managedKeyAvailability = new Map((llmCatalog.data?.providers ?? []).map((provider) => [provider.id, Boolean(provider.managed_key_available)]));
  const capabilityProviderCredentials: Record<string, CapabilityProviderCredentialStatus> = Object.fromEntries(
    (routerConfig.data?.providers ?? []).map((provider) => {
      let status: CapabilityProviderCredentialStatus["status"] = "missing";
      if (!provider.enabled) {
        status = "disabled";
      } else if (provider.auth_mode === "env_ref") {
        status = "check_environment";
      } else if (provider.auth_mode === "os_keychain" && (provider.auth_key_ref || managedKeyAvailability.get(provider.id))) {
        status = "configured";
      } else if (provider.auth_mode === "session_paste" || provider.auth_mode === "key_file") {
        status = "session_required";
      }
      return [
        provider.id,
        {
          provider_id: provider.id,
          label: provider.display_name || provider.id,
          enabled: provider.enabled,
          auth_mode: provider.auth_mode,
          env_key: provider.auth_mode === "env_ref" ? provider.env_key : null,
          status,
        },
      ];
    }),
  );
  const automationMcpPresetOptions: AutomationMcpPresetOption[] = [
    {
      preset_id: "astrabridge_capabilities",
      label: "AstraBridge Capability Runtime",
      description: "Capability routes for image generation, vision, speech transcription, and speech synthesis.",
      configured: Boolean(capabilityMcpPreset?.configured),
    },
    ...(mcpConfig.data?.servers ?? [])
      .filter((server) => server.name !== "astrabridge_capabilities")
      .map((server) => ({
        preset_id: server.name,
        label: server.display_name || server.name,
        description: server.trust_note || server.source_url || server.name,
        configured: Boolean(server.enabled),
      })),
  ];
  const automationPluginSkillPresetOptions: AutomationPluginSkillPresetOption[] = (project?.plugin_skill_presets?.presets ?? []).map((preset) => ({
    preset_id: preset.preset_id,
    label: preset.display_name || preset.preset_id,
    plugin_count: (preset.plugin_refs ?? []).length,
    skill_count: (preset.skill_refs ?? []).length,
    active: preset.preset_id === project?.plugin_skill_presets?.active_preset_id,
  }));

  const activeDogfood = dogfoodDraft ?? dogfoodRun.data?.run ?? null;
  const dogfoodBudgetRows = activeDogfood
    ? [
        { key: "kimi_cny", label: "Kimi CNY", cap: activeDogfood.budgets.kimi_cny, used: activeDogfood.usage.kimi_cny },
        { key: "deepseek_cny", label: "DeepSeek CNY", cap: activeDogfood.budgets.deepseek_cny, used: activeDogfood.usage.deepseek_cny },
        { key: "yunwu_gpt_usd", label: "Yunwu GPT USD", cap: activeDogfood.budgets.yunwu_gpt_usd ?? 50, used: activeDogfood.usage.yunwu_gpt_usd ?? 0 },
        { key: "yunwu_images", label: "Yunwu images", cap: activeDogfood.budgets.yunwu_images, used: activeDogfood.usage.yunwu_images },
      ]
    : [];
  const assetRegistry = dogfoodAssets.data?.registry ?? null;
  const assetContextPack = dogfoodAssets.data?.context_pack ?? null;
  const assetSummary = assetRegistry?.summary as Record<string, unknown> | undefined;
  const approvedAssets = assetContextPack?.approved_unpromoted ?? [];
  const promotedAssets = assetContextPack?.promoted ?? [];
  const reviewAssets = assetContextPack?.needs_review ?? [];

  return (
    <section className="settings-shell">
      <aside className="settings-nav" aria-label={t(locale, "provider_model_settings")}>
        <div className="settings-nav-heading">
          <span className="eyebrow">{t(locale, "provider_model_settings")}</span>
          <strong>{managerStatusLabel}</strong>
          <small>{t(locale, "manager_nav_summary")}</small>
        </div>
        <div className="settings-nav-list">
          {setupTabs.map((item) => (
            <button
              key={item}
              type="button"
              data-testid={`setup-tab-${item}`}
              className={tab === item ? "settings-nav-item active" : "settings-nav-item"}
              onClick={() => setTab(item as typeof tab)}
            >
              <span>{t(locale, `setup_tab_${item}`)}</span>
            </button>
          ))}
        </div>
        <section className="settings-nav-preferences" aria-label={t(locale, "user_settings")}>
          <div className="settings-strip-section">
            <strong>{t(locale, "locale")}</strong>
            <div className="segmented">
              <button type="button" className={locale === "zh-CN" ? "segmented-active" : ""} onClick={() => setLocale("zh-CN")}>
                {t(locale, "locale_zh")}
              </button>
              <button type="button" className={locale === "en" ? "segmented-active" : ""} onClick={() => setLocale("en")}>
                {t(locale, "locale_en")}
              </button>
            </div>
          </div>
          <div className="settings-strip-section">
            <strong>{t(locale, "appearance")}</strong>
            <div className="segmented segmented-wrap">
              {(["codex", "paper", "slate", "cobalt", "sunrise"] as AppearancePreset[]).map((item) => (
                <button key={item} type="button" className={appearance === item ? "segmented-active" : ""} onClick={() => setAppearance(item)}>
                  {t(locale, `appearance_${item}`)}
                </button>
              ))}
            </div>
          </div>
        </section>
      </aside>
      <div className="settings-content">

      {tab === "login" ? (
        <div className="manager-panel">
          <div className="manager-hero">
            <div>
              <span className="eyebrow">{t(locale, "provider_model_settings")}</span>
              <h3>{managerStatusLabel}</h3>
              <p className="muted compact-copy">{t(locale, "manager_login_summary")}</p>
            </div>
            <span className={`session-badge session-badge-${managerMode}`}>{managerStatusLabel}</span>
          </div>
          <div className="manager-grid">
            <section className="manager-section">
              <h4>{t(locale, "manager_login_managed_title")}</h4>
              <label className="field"><span>{t(locale, "manager_login_username")}</span><input value={managerUsername} onChange={(event) => setManagerUsername(event.target.value)} placeholder="user" /></label>
              <label className="field"><span>{t(locale, "manager_login_password")}</span><input type="password" value={managerPassword} onChange={(event) => setManagerPassword(event.target.value)} placeholder={t(locale, "manager_login_password_placeholder")} /></label>
              <div className="field-row">
                <button type="button" className="primary-button" disabled={!managerUsername.trim() || !managerPassword.trim() || loginManager.isPending} onClick={() => loginManager.mutate({ mode: "managed_user", username: managerUsername, password: managerPassword })}>{t(locale, "manager_login_button")}</button>
                <button type="button" className="ghost-button" disabled={createManagerUser.isPending} onClick={() => createManagerUser.mutate({ username: "user", use_desktop_key_file: true })}>{t(locale, "manager_login_init_desktop")}</button>
              </div>
              {loginManager.error || createManagerUser.error ? <p className="error-text">{String((loginManager.error || createManagerUser.error) as Error)}</p> : null}
            </section>
            <section className="manager-section">
              <h4>{t(locale, "manager_login_other_title")}</h4>
              <p className="muted compact-copy">{t(locale, "manager_login_other_summary")}</p>
              <div className="field-row">
                <button type="button" className="ghost-button" onClick={() => loginManager.mutate({ mode: "anonymous" })}>{t(locale, "manager_login_anonymous")}</button>
                <button type="button" className="ghost-button" onClick={() => logoutManager.mutate()}>{t(locale, "manager_login_logout")}</button>
              </div>
              <dl className="manager-facts">
                <div><dt>{t(locale, "manager_fact_users")}</dt><dd>{llmSession.data?.users.length ?? 0}</dd></div>
                <div><dt>{t(locale, "manager_fact_keys")}</dt><dd>{llmSession.data?.key_count ?? 0}</dd></div>
                <div><dt>{t(locale, "manager_fact_models")}</dt><dd>{llmCatalog.data?.verified_model_ids.length ?? 0}</dd></div>
              </dl>
            </section>
          </div>
        </div>
      ) : null}

      {tab === "users" ? (
        <div className="manager-panel">
          <div className="manager-grid">
            <section className="manager-section">
              <h4>{t(locale, "manager_users_title")}</h4>
              <div className="manager-list">
                {(llmSession.data?.users ?? []).map((user) => (
                  <div className="manager-row" key={user.username}>
                    <span>{user.username}</span>
                    <small>{user.has_vault ? t(locale, "manager_vault_ready") : t(locale, "manager_vault_missing")}</small>
                  </div>
                ))}
                {(llmSession.data?.users ?? []).length === 0 ? <p className="muted compact-copy">{t(locale, "manager_users_empty")}</p> : null}
              </div>
              <label className="field"><span>{t(locale, "manager_user_new_username")}</span><input value={managerUsername} onChange={(event) => setManagerUsername(event.target.value)} /></label>
              <label className="field"><span>{t(locale, "manager_user_new_password")}</span><input type="password" value={managerPassword} onChange={(event) => setManagerPassword(event.target.value)} /></label>
              <button type="button" className="primary-button" disabled={!managerUsername.trim() || !managerPassword.trim()} onClick={() => createManagerUser.mutate({ username: managerUsername, password: managerPassword })}>{t(locale, "manager_user_create")}</button>
            </section>
            <section className="manager-section">
              <h4>{t(locale, "manager_profile_title")}</h4>
              <p className="muted compact-copy">{t(locale, "manager_profile_summary")}</p>
              <label className="field"><span>{t(locale, "manager_profile_display_name")}</span><input value={managerDisplayName} onChange={(event) => setManagerDisplayName(event.target.value)} placeholder={llmSession.data?.username ?? "user"} /></label>
              <label className="field"><span>{t(locale, "manager_profile_avatar_path")}</span><input value={managerAvatarPath} onChange={(event) => setManagerAvatarPath(event.target.value)} placeholder="D:\\avatars\\me.png" /></label>
              <button
                type="button"
                className="primary-button"
                disabled={saveManagerProfile.isPending}
                onClick={() => saveManagerProfile.mutate({ username: llmSession.data?.username ?? managerUsername, display_name: managerDisplayName, avatar_path: managerAvatarPath })}
              >
                {t(locale, "manager_profile_save")}
              </button>
              {saveManagerProfile.error ? <p className="error-text">{String((saveManagerProfile.error as Error).message ?? saveManagerProfile.error)}</p> : null}
            </section>
            <section className="manager-section">
              <h4>{t(locale, "manager_password_title")}</h4>
              <p className="muted compact-copy">{t(locale, "manager_password_summary")}</p>
              <label className="field"><span>{t(locale, "manager_password_old")}</span><input type="password" value={managerOldPassword} onChange={(event) => setManagerOldPassword(event.target.value)} /></label>
              <label className="field"><span>{t(locale, "manager_password_new")}</span><input type="password" value={managerNewPassword} onChange={(event) => setManagerNewPassword(event.target.value)} /></label>
              <button type="button" className="primary-button" disabled={!managerOldPassword.trim() || !managerNewPassword.trim()} onClick={() => changeManagerPassword.mutate({ username: managerUsername, old_password: managerOldPassword, new_password: managerNewPassword })}>{t(locale, "manager_password_change")}</button>
              {changeManagerPassword.error ? <p className="error-text">{String(changeManagerPassword.error as Error)}</p> : null}
            </section>
          </div>
        </div>
      ) : null}

      {tab === "providers" ? (
        <>
          <div className="thread-list">
            {(routerConfig.data?.providers ?? []).map((provider) => (
              <button key={provider.id} type="button" className={providerDraft?.id === provider.id ? "thread-row thread-row-active" : "thread-row"} onClick={() => setProviderDraft(provider)}>
                <strong>{provider.display_name}</strong>
                <span>{provider.id} / {provider.default_model}</span>
              </button>
            ))}
          </div>
          <button
            type="button"
            className="ghost-button"
            onClick={() =>
              setProviderDraft({
                id: "",
                display_name: "",
                enabled: true,
                adapter_type: "responses",
                runtime_backend: "app_server",
                base_url: "",
                auth_key_ref: null,
                default_model: "",
                request_timeout_ms: 300000,
                stream_idle_timeout_ms: 300000,
                env_key: "OPENAI_API_KEY",
                auth_mode: "os_keychain",
                proxy_mode: "direct",
                proxy_url: "",
                logo_source_url: "",
                logo_asset_path: "",
                logo_license_note: "",
                accent_color: "",
              })
            }
          >
            {t(locale, "manager_provider_new")}
          </button>
          {providerDraft ? (
            <>
              <label className="field"><span>ID</span><input value={providerDraft.id} onChange={(event) => setProviderDraft({ ...providerDraft, id: event.target.value })} /></label>
              <label className="field"><span>{t(locale, "provider_label")}</span><input value={providerDraft.display_name} onChange={(event) => setProviderDraft({ ...providerDraft, display_name: event.target.value })} /></label>
              <label className="field"><span>{t(locale, "base_url")}</span><input value={providerDraft.base_url} onChange={(event) => setProviderDraft({ ...providerDraft, base_url: event.target.value })} /></label>
              <label className="field"><span>{t(locale, "manager_provider_adapter")}</span><select value={providerDraft.adapter_type} onChange={(event) => setProviderDraft({ ...providerDraft, adapter_type: event.target.value })}><option value="responses">responses</option><option value="chat">chat</option></select></label>
              <label className="field"><span>{t(locale, "manager_provider_default_model")}</span><input value={providerDraft.default_model} onChange={(event) => setProviderDraft({ ...providerDraft, default_model: event.target.value })} /></label>
              <label className="field"><span>{t(locale, "manager_provider_logo_source_url")}</span><input value={providerDraft.logo_source_url ?? ""} onChange={(event) => setProviderDraft({ ...providerDraft, logo_source_url: event.target.value })} placeholder={t(locale, "manager_provider_logo_source_placeholder")} /></label>
              <label className="field"><span>{t(locale, "manager_provider_logo_asset_path")}</span><input value={providerDraft.logo_asset_path ?? ""} onChange={(event) => setProviderDraft({ ...providerDraft, logo_asset_path: event.target.value })} placeholder={t(locale, "manager_provider_logo_asset_placeholder")} /></label>
              <label className="field"><span>{t(locale, "manager_provider_accent_color")}</span><input value={providerDraft.accent_color ?? ""} onChange={(event) => setProviderDraft({ ...providerDraft, accent_color: event.target.value })} placeholder="#1f2937" /></label>
              <label className="field"><span>{t(locale, "manager_provider_logo_license_note")}</span><textarea rows={2} value={providerDraft.logo_license_note ?? ""} onChange={(event) => setProviderDraft({ ...providerDraft, logo_license_note: event.target.value })} /></label>
              <div className="field-row">
                <button type="button" className="primary-button" onClick={() => saveProvider.mutate(providerDraft)}>{t(locale, "manager_provider_save")}</button>
                {providerDraft.id ? <button type="button" className="ghost-button" onClick={() => api.deleteProvider(providerDraft.id).then(() => queryClient.invalidateQueries({ queryKey: ["router-config"] }))}>{t(locale, "manager_delete")}</button> : null}
              </div>
            </>
          ) : null}
        </>
      ) : null}

      {tab === "capabilities" ? (
        <div className="manager-panel">
          <CapabilityRoutesPanel
            locale={locale}
            routes={capabilityRouteEntries}
            managementEntries={capabilityManagement.data?.capabilities ?? []}
            mcpPreset={capabilityMcpPreset}
            pluginSkillRegistry={runtimePluginSkillRegistry.data ?? null}
            pluginSkillRegistryLoading={runtimePluginSkillRegistry.isLoading || runtimePluginSkillRegistry.isFetching}
            pluginSkillRegistryError={runtimePluginSkillRegistry.isError}
            drafts={capabilityRouteDrafts}
            setDrafts={setCapabilityRouteDrafts}
            isLoading={capabilityManagement.isLoading}
            isError={capabilityManagement.isError}
            isSaving={saveCapabilityRoute.isPending}
            smokeResults={capabilitySmokeResults}
            smokePendingCapabilityId={(runCapabilitySmoke.variables as { capability_id?: string } | undefined)?.capability_id ?? null}
            isSmokePending={runCapabilitySmoke.isPending}
            artifacts={capabilityArtifacts.data?.artifacts ?? []}
            artifactsLoading={capabilityArtifacts.isLoading}
            artifactsError={capabilityArtifacts.isError}
            providerCredentials={capabilityProviderCredentials}
            mcpRuntimeVisible={capabilityMcpRuntimeVisible}
            mcpRuntimeToolCount={capabilityMcpRuntimeToolCount}
            mcpVisibilityLoading={mcpStatus.isLoading}
            mcpVisibilityError={mcpStatus.isError}
            isInstallingMcpPreset={applyAstraBridgeCapabilities.isPending}
            toMediaSrc={localAssetUrl}
            onInstallMcpPreset={() => applyAstraBridgeCapabilities.mutate()}
            onSave={(route, draft) =>
              saveCapabilityRoute.mutate({
                capability_id: route.capability_id,
                mode: draft.mode,
                provider_id: draft.mode === "pinned" ? draft.provider_id ?? null : null,
                model: draft.mode === "pinned" ? draft.model ?? null : null,
              })
            }
            onRunSmoke={(capabilityId) => runCapabilitySmoke.mutate({ capability_id: capabilityId, mode: "dry_run" })}
          />
        </div>
      ) : null}

      {tab === "models" ? (
        <div className="metadata-editor">
          <div className="metadata-list-pane">
            <label className="field">
              <span>{t(locale, "manager_model_search")}</span>
              <input value={modelSearch} onChange={(event) => setModelSearch(event.target.value)} placeholder={t(locale, "manager_model_search_placeholder")} />
            </label>
            <div className="metadata-model-list" role="list">
              {filteredModels.map((model) => (
                <button key={model.id} type="button" className={modelDraft?.id === model.id ? "metadata-row metadata-row-active" : "metadata-row"} onClick={() => setModelDraft(model)}>
                  <span className="metadata-row-title">{model.display_name}</span>
                  <span className="metadata-row-id">{model.id}</span>
                  <span className="metadata-row-badges">
                    <span>{model.provider}</span>
                    <span>{model.advertised_context_window?.toLocaleString?.() ?? model.advertised_context_window}</span>
                    <span>{model.source_status ?? "seeded"}</span>
                    {model.recommended ? <span>recommended</span> : null}
                    {model.deprecated ? <span>deprecated</span> : null}
                  </span>
                </button>
              ))}
            </div>
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                const providerDraftDefaults = providerModelDraftDefaults(selectedProvider);
                setModelDraft({
                  id: "",
                  provider: selectedProvider?.id ?? "",
                  native_model: "",
                  display_name: "",
                  enabled: true,
                  ...providerDraftDefaults,
                  advertised_context_window: providerDraftDefaults.advertised_context_window ?? 1000000,
                  ui_context_hint_only: providerDraftDefaults.ui_context_hint_only ?? true,
                  adapter_profile: providerDraftDefaults.adapter_profile ?? "default",
                });
              }}
            >
              {t(locale, "manager_model_new")}
            </button>
          </div>
          {modelDraft ? (
            <div className="metadata-detail-pane">
              <div className="metadata-detail-header">
                <div>
                  <span className="eyebrow">{t(locale, "manager_model_contract")}</span>
                  <h3>{modelDraft.display_name || modelDraft.id || t(locale, "manager_model_new")}</h3>
                </div>
                <div className="field-row">
                  <button type="button" className="primary-button" onClick={() => saveModel.mutate(modelDraft)}>{t(locale, "manager_model_save")}</button>
                  {modelDraft.id ? <button type="button" className="ghost-button" onClick={() => api.deleteModelCatalogEntry(modelDraft.id).then(() => queryClient.invalidateQueries({ queryKey: ["router-config"] }))}>{t(locale, "manager_delete")}</button> : null}
                </div>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_identity")}</h4>
                <div className="form-grid">
                  <label className="field"><span>ID</span><input value={modelDraft.id} onChange={(event) => setModelDraft({ ...modelDraft, id: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "title_provider")}</span><input value={modelDraft.provider} onChange={(event) => setModelDraft({ ...modelDraft, provider: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_native")}</span><input value={modelDraft.native_model} onChange={(event) => setModelDraft({ ...modelDraft, native_model: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_display_name")}</span><input value={modelDraft.display_name} onChange={(event) => setModelDraft({ ...modelDraft, display_name: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_kind")}</span><input value={modelDraft.model_kind ?? "chat"} onChange={(event) => setModelDraft({ ...modelDraft, model_kind: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_adapter_profile")}</span><input value={modelDraft.adapter_profile} onChange={(event) => setModelDraft({ ...modelDraft, adapter_profile: event.target.value })} /></label>
                </div>
                <div className="check-row">
                  <label><input type="checkbox" checked={modelDraft.enabled} onChange={(event) => setModelDraft({ ...modelDraft, enabled: event.target.checked })} /> {t(locale, "manager_model_enabled")}</label>
                  <label><input type="checkbox" checked={modelDraft.codex_agent_enabled ?? true} onChange={(event) => setModelDraft({ ...modelDraft, codex_agent_enabled: event.target.checked })} /> {t(locale, "manager_model_expose_codex")}</label>
                </div>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_context")}</h4>
                <div className="form-grid">
                  <label className="field"><span>{t(locale, "manager_model_context_window")}</span><input type="number" value={modelDraft.advertised_context_window} onChange={(event) => setModelDraft({ ...modelDraft, advertised_context_window: Number(event.target.value) || 0 })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_effective_percent")}</span><input type="number" value={modelDraft.effective_context_window_percent ?? 80} onChange={(event) => setModelDraft({ ...modelDraft, effective_context_window_percent: Number(event.target.value) || 80 })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_auto_compact_limit")}</span><input value={modelDraft.auto_compact_token_limit ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, auto_compact_token_limit: optionalNumber(event.target.value) })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_tool_output_limit")}</span><input value={modelDraft.tool_output_token_limit ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, tool_output_token_limit: optionalNumber(event.target.value) })} /></label>
                </div>
                <label className="field"><span>{t(locale, "manager_model_input_modalities")}</span><input value={joinList(modelDraft.input_modalities)} onChange={(event) => setModelDraft({ ...modelDraft, input_modalities: splitList(event.target.value) })} /></label>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_reasoning_temp")}</h4>
                <div className="form-grid">
                  <label className="field"><span>{t(locale, "manager_model_reasoning_levels")}</span><input value={joinList(modelDraft.supported_reasoning_levels)} onChange={(event) => setModelDraft({ ...modelDraft, supported_reasoning_levels: splitList(event.target.value) })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_default_reasoning")}</span><input value={modelDraft.default_reasoning_level ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, default_reasoning_level: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_reasoning_display")}</span><select value={modelDraft.reasoning_display_policy ?? "collapsed_3_lines"} onChange={(event) => setModelDraft({ ...modelDraft, reasoning_display_policy: event.target.value })}><option value="collapsed_3_lines">collapsed 3 lines</option><option value="hidden">hidden</option><option value="expanded">expanded</option></select></label>
                  <label className="field"><span>{t(locale, "manager_model_temperature_default")}</span><input type="number" step="0.1" value={modelDraft.temperature_default ?? 0} onChange={(event) => setModelDraft({ ...modelDraft, temperature_default: Number(event.target.value) })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_ui_range")}</span><input value={`${modelDraft.temperature_ui_min ?? 0}, ${modelDraft.temperature_ui_max ?? 2}`} onChange={(event) => {
                    const [min, max] = splitList(event.target.value).map(Number);
                    setModelDraft({ ...modelDraft, temperature_ui_min: Number.isFinite(min) ? min : 0, temperature_ui_max: Number.isFinite(max) ? max : 2 });
                  }} /></label>
                  <label className="field"><span>{t(locale, "manager_model_provider_range")}</span><input value={`${modelDraft.provider_temperature_min ?? 0}, ${modelDraft.provider_temperature_max ?? 2}`} onChange={(event) => {
                    const [min, max] = splitList(event.target.value).map(Number);
                    setModelDraft({ ...modelDraft, provider_temperature_min: Number.isFinite(min) ? min : 0, provider_temperature_max: Number.isFinite(max) ? max : 2 });
                  }} /></label>
                  <label className="field"><span>{t(locale, "manager_model_adapter_policy")}</span><select value={modelDraft.temperature_adapter_policy ?? "pass_through_0_2"} onChange={(event) => setModelDraft({ ...modelDraft, temperature_adapter_policy: event.target.value })}><option value="pass_through_0_2">OpenAI compatible 0-2</option><option value="qwen_omit_zero_clamp_1">Qwen omit 0, clamp to 1</option><option value="kimi_only_temperature_1">Kimi only temperature=1</option></select></label>
                </div>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_pricing")}</h4>
                <div className="form-grid">
                  <label className="field"><span>{t(locale, "manager_model_currency")}</span><input value={modelDraft.pricing_currency ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, pricing_currency: event.target.value })} placeholder="USD / CNY" /></label>
                  <label className="field"><span>{t(locale, "manager_model_input_price")}</span><input type="number" step="0.0001" value={modelDraft.pricing_input_per_mtok ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, pricing_input_per_mtok: optionalNumber(event.target.value) })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_output_price")}</span><input type="number" step="0.0001" value={modelDraft.pricing_output_per_mtok ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, pricing_output_per_mtok: optionalNumber(event.target.value) })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_cached_input_price")}</span><input type="number" step="0.0001" value={modelDraft.pricing_cached_input_per_mtok ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, pricing_cached_input_per_mtok: optionalNumber(event.target.value) })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_pricing_status")}</span><input value={modelDraft.pricing_status ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, pricing_status: event.target.value })} placeholder="official_docs / screenshot_seed" /></label>
                  <label className="field"><span>{t(locale, "manager_model_pricing_source_url")}</span><input value={modelDraft.pricing_source_url ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, pricing_source_url: event.target.value })} /></label>
                </div>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_tools")}</h4>
                <div className="check-row">
                  <label><input type="checkbox" checked={modelDraft.supports_reasoning_summaries ?? false} onChange={(event) => setModelDraft({ ...modelDraft, supports_reasoning_summaries: event.target.checked })} /> {t(locale, "manager_model_reasoning_summaries")}</label>
                  <label><input type="checkbox" checked={modelDraft.supports_parallel_tool_calls ?? false} onChange={(event) => setModelDraft({ ...modelDraft, supports_parallel_tool_calls: event.target.checked })} /> {t(locale, "manager_model_parallel_tools")}</label>
                  <label><input type="checkbox" checked={modelDraft.supports_search_tool ?? false} onChange={(event) => setModelDraft({ ...modelDraft, supports_search_tool: event.target.checked })} /> {t(locale, "manager_model_search_tool")}</label>
                  <label><input type="checkbox" checked={modelDraft.use_responses_lite ?? false} onChange={(event) => setModelDraft({ ...modelDraft, use_responses_lite: event.target.checked })} /> {t(locale, "manager_model_responses_lite")}</label>
                </div>
                <div className="form-grid">
                  <label className="field"><span>{t(locale, "manager_model_apply_patch_tool")}</span><input value={modelDraft.apply_patch_tool_type ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, apply_patch_tool_type: event.target.value || null })} placeholder={t(locale, "manager_model_blank_unless_verified")} /></label>
                  <label className="field"><span>{t(locale, "manager_model_web_search_tool")}</span><input value={modelDraft.web_search_tool_type ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, web_search_tool_type: event.target.value || null })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_tool_mode")}</span><input value={modelDraft.tool_mode ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, tool_mode: event.target.value || null })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_multi_agent_version")}</span><input value={modelDraft.multi_agent_version ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, multi_agent_version: event.target.value || null })} /></label>
                </div>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_web_capability")}</h4>
                <div className="form-grid">
                  <label className="field"><span>{t(locale, "manager_model_native_web_search")}</span><select value={modelDraft.native_web_search_support ?? "unverified"} onChange={(event) => setModelDraft({ ...modelDraft, native_web_search_support: event.target.value })}><option value="unverified">unverified</option><option value="unsupported">unsupported</option><option value="verified">verified</option></select></label>
                  <label className="field"><span>{t(locale, "manager_model_tool_web_search")}</span><select value={modelDraft.tool_web_search_support ?? "unverified"} onChange={(event) => setModelDraft({ ...modelDraft, tool_web_search_support: event.target.value })}><option value="unverified">unverified</option><option value="not_requested">not requested</option><option value="verified">verified</option><option value="fail">fail</option></select></label>
                  <label className="field"><span>{t(locale, "manager_model_mcp_web")}</span><input value={modelDraft.mcp_web_support ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, mcp_web_support: event.target.value })} placeholder="context7 pass / unverified" /></label>
                  <label className="field"><span>{t(locale, "manager_model_web_smoke")}</span><select value={modelDraft.web_smoke_status ?? "untested"} onChange={(event) => setModelDraft({ ...modelDraft, web_smoke_status: event.target.value })}><option value="untested">untested</option><option value="not_requested">not requested</option><option value="pass">pass</option><option value="fail">fail</option><option value="blocked_no_source">blocked no source</option></select></label>
                  <label className="field"><span>{t(locale, "manager_model_citation_quality")}</span><input value={modelDraft.citation_quality ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, citation_quality: event.target.value })} placeholder="source_url_verified / untested" /></label>
                  <label className="field"><span>{t(locale, "manager_model_last_web_verified")}</span><input value={modelDraft.last_web_verified_at ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, last_web_verified_at: event.target.value || null })} /></label>
                </div>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_codex_mcp")}</h4>
                <div className="check-row">
                  <label><input type="checkbox" checked={modelDraft.supports_mcp_tools ?? false} onChange={(event) => setModelDraft({ ...modelDraft, supports_mcp_tools: event.target.checked })} /> {t(locale, "manager_model_mcp_verified")}</label>
                </div>
                <div className="form-grid">
                  <label className="field"><span>{t(locale, "manager_model_mcp_policy")}</span><select value={modelDraft.mcp_tool_call_policy ?? "unsupported"} onChange={(event) => setModelDraft({ ...modelDraft, mcp_tool_call_policy: event.target.value })}><option value="unsupported">unsupported</option><option value="conservative">conservative</option><option value="verified">verified</option></select></label>
                  <label className="field"><span>{t(locale, "manager_model_mcp_smoke")}</span><select value={modelDraft.mcp_smoke_status ?? "untested"} onChange={(event) => setModelDraft({ ...modelDraft, mcp_smoke_status: event.target.value })}><option value="untested">untested</option><option value="pass">pass</option><option value="warn">warn</option><option value="fail">fail</option></select></label>
                  <label className="field"><span>{t(locale, "manager_model_argument_validation")}</span><select value={modelDraft.mcp_tool_argument_validation ?? "unsupported"} onChange={(event) => setModelDraft({ ...modelDraft, mcp_tool_argument_validation: event.target.value })}><option value="unsupported">unsupported</option><option value="router_repair">router repair</option><option value="native">native</option></select></label>
                  <label className="field"><span>{t(locale, "manager_model_verified_mcp_servers")}</span><input value={joinList(modelDraft.mcp_verified_servers)} onChange={(event) => setModelDraft({ ...modelDraft, mcp_verified_servers: splitList(event.target.value) })} placeholder="context7" /></label>
                </div>
                <label className="field"><span>{t(locale, "manager_model_planner_json")}</span><textarea rows={3} value={JSON.stringify(modelDraft.planner_support ?? {}, null, 2)} onChange={(event) => setModelDraft({ ...modelDraft, planner_support: safeParseStringMap(event.target.value) })} /></label>
                <label className="field"><span>{t(locale, "manager_model_compaction_json")}</span><textarea rows={3} value={JSON.stringify(modelDraft.context_compaction_support ?? {}, null, 2)} onChange={(event) => setModelDraft({ ...modelDraft, context_compaction_support: safeParseStringMap(event.target.value) })} /></label>
                <label className="field"><span>{t(locale, "manager_model_ui_warnings")}</span><textarea rows={3} value={(modelDraft.ui_warnings ?? []).join("\n")} onChange={(event) => setModelDraft({ ...modelDraft, ui_warnings: splitList(event.target.value) })} /></label>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_provenance")}</h4>
                <div className="form-grid">
                  <label className="field"><span>{t(locale, "manager_model_source_status")}</span><input value={modelDraft.source_status ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, source_status: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_model_last_verified")}</span><input value={modelDraft.last_verified_at ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, last_verified_at: event.target.value || null })} /></label>
                </div>
                <label className="field"><span>{t(locale, "manager_model_source_urls")}</span><textarea rows={3} value={(modelDraft.source_urls ?? []).join("\n")} onChange={(event) => setModelDraft({ ...modelDraft, source_urls: splitList(event.target.value) })} /></label>
                <label className="field"><span>{t(locale, "manager_model_verification_notes")}</span><textarea rows={3} value={modelDraft.verification_notes ?? ""} onChange={(event) => setModelDraft({ ...modelDraft, verification_notes: event.target.value })} /></label>
              </div>
              <div className="metadata-section" data-testid="metadata-model-generated-catalog-provenance">
                <h4>{t(locale, "manager_model_generated_catalog")}</h4>
                <div className="form-grid">
                  <label className="field" data-testid="metadata-model-catalog-version"><span>{t(locale, "manager_model_catalog_version")}</span><input value={effectiveCatalog.data?.catalog_version ?? ""} readOnly /></label>
                  <label className="field" data-testid="metadata-model-models-lock"><span>{t(locale, "manager_model_models_lock")}</span><input value={effectiveCatalog.data?.models_lock_path ?? ""} readOnly /></label>
                  <label className="field" data-testid="metadata-model-sources-lock"><span>{t(locale, "manager_model_sources_lock")}</span><input value={effectiveCatalog.data?.sources_lock_path ?? ""} readOnly /></label>
                  <label className="field" data-testid="metadata-model-review-path"><span>{t(locale, "manager_model_review")}</span><input value={effectiveCatalog.data?.review_path ?? ""} readOnly /></label>
                  <label className="field" data-testid="metadata-model-source-status"><span>{t(locale, "manager_model_source_status")}</span><input value={selectedCatalogEntry?.source_status ?? ""} readOnly /></label>
                  <label className="field" data-testid="metadata-model-source-provenance"><span>{t(locale, "manager_model_source_provenance")}</span><input value={JSON.stringify(selectedCatalogEntry?.source_provenance ?? {})} readOnly /></label>
                  <label className="field" data-testid="metadata-model-catalog-version-model"><span>{t(locale, "manager_model_catalog_version_model")}</span><input value={selectedCatalogEntry?.catalog_version ?? ""} readOnly /></label>
                </div>
                <label className="field" data-testid="metadata-model-recommended-defaults"><span>{t(locale, "manager_model_recommended_defaults")}</span><input value={`recommended=${selectedCatalogEntry?.recommended ? "yes" : "no"} default=${selectedCatalogEntry?.default_for_provider ? "yes" : "no"} deprecated=${selectedCatalogEntry?.deprecated ? "yes" : "no"}`} readOnly /></label>
              </div>
              <div className="metadata-section">
                <h4>{t(locale, "manager_model_effective_preview")}</h4>
                {selectedCatalogEntry ? <pre className="json-preview">{JSON.stringify(selectedCatalogEntry, null, 2)}</pre> : <p className="muted">{t(locale, "manager_model_disabled_preview")}</p>}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {tab === "mcp" ? (
        <div className="mcp-dashboard">
          <div className="metadata-actions">
            <div>
              <span className="eyebrow">{t(locale, "manager_mcp_servers")}</span>
              <h3>{t(locale, "manager_mcp_context_tools")}</h3>
              <p className="muted">{t(locale, "manager_mcp_summary")}</p>
            </div>
            <div className="field-row">
              <button type="button" className="ghost-button" onClick={() => applyContext7.mutate()} disabled={applyContext7.isPending}>{t(locale, "manager_mcp_install_context7")}</button>
              <button type="button" className="ghost-button" onClick={() => applyYunwuImage.mutate()} disabled={applyYunwuImage.isPending}>{t(locale, "manager_mcp_install_yunwu")}</button>
              <button type="button" className="ghost-button" onClick={() => applyAstraBridgeCapabilities.mutate()} disabled={applyAstraBridgeCapabilities.isPending}>{t(locale, "manager_mcp_install_capabilities")}</button>
              <button type="button" className="ghost-button" onClick={() => testYunwuImage.mutate()} disabled={testYunwuImage.isPending}>{t(locale, "manager_mcp_test_yunwu")}</button>
              <button type="button" className="primary-button" onClick={() => reloadMcp.mutate()} disabled={!selectedProviderId || reloadMcp.isPending}>{t(locale, "manager_mcp_reload")}</button>
            </div>
          </div>
          <div className="mcp-health-row">
            <span className={mcpConfig.data?.environment.node ? "capability-ok" : "capability-warn"}>Node {mcpConfig.data?.environment.node ? t(locale, "manager_mcp_ready") : t(locale, "manager_mcp_missing")}</span>
            <span className={mcpConfig.data?.environment.npx ? "capability-ok" : "capability-warn"}>npx {mcpConfig.data?.environment.npx ? t(locale, "manager_mcp_ready") : t(locale, "manager_mcp_missing")}</span>
            <span className={mcpConfig.data?.environment.python ? "capability-ok" : "capability-warn"}>Python {mcpConfig.data?.environment.python ? t(locale, "manager_mcp_ready") : t(locale, "manager_mcp_missing")}</span>
            <span>{mcpConfig.data?.servers.length ?? 0} {t(locale, "manager_mcp_configured")}</span>
            <span>{mcpStatus.data?.servers.length ?? 0} {t(locale, "manager_mcp_runtime_visible")}</span>
          </div>
          {mcpOutput ? <pre className="json-preview compact-preview">{mcpOutput}</pre> : null}
          <div className="metadata-editor mcp-editor">
            <div className="metadata-list-pane">
              {(mcpConfig.data?.servers ?? []).map((server) => (
                <button key={server.name} type="button" className={mcpDraft?.name === server.name ? "metadata-row metadata-row-active" : "metadata-row"} onClick={() => setMcpDraft(server)}>
                  <span className="metadata-row-title">{server.display_name}</span>
                  <span className="metadata-row-id">{server.name} / {server.transport}</span>
                  <span className="metadata-row-badges">
                    <span>{server.enabled ? "enabled" : "disabled"}</span>
                    <span>{server.default_tools_approval_mode}</span>
                  </span>
                </button>
              ))}
              <button
                type="button"
                className="ghost-button"
                onClick={() =>
                  setMcpDraft({
                    name: "",
                    display_name: "",
                    enabled: true,
                    transport: "stdio",
                    command: "",
                    args: [],
                    cwd: null,
                    env: {},
                    env_vars: [],
                    url: "",
                    bearer_token_env_var: null,
                    http_headers: {},
                    env_http_headers: {},
                    startup_timeout_sec: 20,
                    tool_timeout_sec: 60,
                    required: false,
                    default_tools_approval_mode: "prompt",
                    enabled_tools: [],
                    disabled_tools: [],
                    tools: {},
                    trust_note: "",
                    source_url: "",
                  })
                }
              >
                {t(locale, "manager_mcp_new")}
              </button>
              {mcpStatus.error ? <p className="error-text">{String((mcpStatus.error as Error).message ?? mcpStatus.error)}</p> : null}
              {(mcpStatus.data?.servers ?? []).map((server) => (
                <section key={server.name} className="mcp-status-card">
                  <strong>{server.name}</strong>
                  <span>{Object.keys(server.tools ?? {}).length} {t(locale, "manager_mcp_tools_count")}</span>
                  <small>{t(locale, "manager_mcp_auth")}: {typeof server.authStatus === "string" ? server.authStatus : JSON.stringify(server.authStatus)}</small>
                </section>
              ))}
            </div>
            {mcpDraft ? (
              <div className="metadata-detail-pane">
                <div className="metadata-detail-header">
                  <div>
                    <span className="eyebrow">{t(locale, "manager_mcp_contract")}</span>
                    <h3>{mcpDraft.display_name || mcpDraft.name || t(locale, "manager_mcp_new")}</h3>
                  </div>
                  <div className="field-row">
                    <button type="button" className="primary-button" onClick={() => saveMcpServer.mutate(mcpDraft)} disabled={saveMcpServer.isPending}>{t(locale, "manager_mcp_save")}</button>
                    {mcpDraft.name ? <button type="button" className="ghost-button" onClick={() => api.deleteMcpServer(mcpDraft.name).then(() => queryClient.invalidateQueries({ queryKey: ["mcp-config"] }))}>{t(locale, "manager_delete")}</button> : null}
                  </div>
                </div>
                <div className="metadata-section">
                  <h4>{t(locale, "manager_mcp_server")}</h4>
                  <div className="form-grid">
                    <label className="field"><span>{t(locale, "manager_mcp_name")}</span><input value={mcpDraft.name} onChange={(event) => setMcpDraft({ ...mcpDraft, name: event.target.value })} /></label>
                    <label className="field"><span>{t(locale, "manager_model_display_name")}</span><input value={mcpDraft.display_name} onChange={(event) => setMcpDraft({ ...mcpDraft, display_name: event.target.value })} /></label>
                    <label className="field"><span>{t(locale, "manager_mcp_transport")}</span><select value={mcpDraft.transport} onChange={(event) => setMcpDraft({ ...mcpDraft, transport: event.target.value as McpServerConfig["transport"] })}><option value="stdio">stdio</option><option value="streamable_http">streamable HTTP</option></select></label>
                    <label className="field"><span>{t(locale, "manager_mcp_approval")}</span><select value={mcpDraft.default_tools_approval_mode} onChange={(event) => setMcpDraft({ ...mcpDraft, default_tools_approval_mode: event.target.value as McpServerConfig["default_tools_approval_mode"] })}><option value="prompt">prompt</option><option value="auto">auto</option><option value="approve">approve</option></select></label>
                  </div>
                  <div className="check-row">
                    <label><input type="checkbox" checked={mcpDraft.enabled} onChange={(event) => setMcpDraft({ ...mcpDraft, enabled: event.target.checked })} /> {t(locale, "manager_mcp_enabled")}</label>
                    <label><input type="checkbox" checked={mcpDraft.required} onChange={(event) => setMcpDraft({ ...mcpDraft, required: event.target.checked })} /> {t(locale, "manager_mcp_required")}</label>
                  </div>
                </div>
                <div className="metadata-section">
                  <h4>{t(locale, "manager_mcp_transport_details")}</h4>
                  <div className="form-grid">
                    <label className="field"><span>{t(locale, "manager_mcp_command")}</span><input value={mcpDraft.command} onChange={(event) => setMcpDraft({ ...mcpDraft, command: event.target.value })} placeholder="npx" /></label>
                    <label className="field"><span>{t(locale, "manager_mcp_args")}</span><input value={joinList(mcpDraft.args)} onChange={(event) => setMcpDraft({ ...mcpDraft, args: splitList(event.target.value) })} placeholder="-y, @upstash/context7-mcp" /></label>
                    <label className="field"><span>URL</span><input value={mcpDraft.url} onChange={(event) => setMcpDraft({ ...mcpDraft, url: event.target.value })} placeholder="https://..." /></label>
                    <label className="field"><span>{t(locale, "manager_mcp_bearer_env")}</span><input value={mcpDraft.bearer_token_env_var ?? ""} onChange={(event) => setMcpDraft({ ...mcpDraft, bearer_token_env_var: event.target.value || null })} placeholder="CONTEXT7_API_KEY" /></label>
                    <label className="field"><span>{t(locale, "manager_mcp_startup_timeout")}</span><input type="number" value={mcpDraft.startup_timeout_sec} onChange={(event) => setMcpDraft({ ...mcpDraft, startup_timeout_sec: Number(event.target.value) || 20 })} /></label>
                    <label className="field"><span>{t(locale, "manager_mcp_tool_timeout")}</span><input type="number" value={mcpDraft.tool_timeout_sec} onChange={(event) => setMcpDraft({ ...mcpDraft, tool_timeout_sec: Number(event.target.value) || 60 })} /></label>
                  </div>
                  <label className="field"><span>{t(locale, "manager_mcp_env_vars")}</span><input value={joinList(mcpDraft.env_vars)} onChange={(event) => setMcpDraft({ ...mcpDraft, env_vars: splitList(event.target.value) })} placeholder="LOCAL_TOKEN, CONTEXT7_API_KEY" /></label>
                </div>
                <div className="metadata-section">
                  <h4>{t(locale, "manager_mcp_tools_trust")}</h4>
                  <div className="form-grid">
                    <label className="field"><span>{t(locale, "manager_mcp_enabled_tools")}</span><input value={joinList(mcpDraft.enabled_tools)} onChange={(event) => setMcpDraft({ ...mcpDraft, enabled_tools: splitList(event.target.value) })} /></label>
                    <label className="field"><span>{t(locale, "manager_mcp_disabled_tools")}</span><input value={joinList(mcpDraft.disabled_tools)} onChange={(event) => setMcpDraft({ ...mcpDraft, disabled_tools: splitList(event.target.value) })} /></label>
                  </div>
                  <label className="field"><span>{t(locale, "manager_mcp_approvals_json")}</span><textarea rows={4} value={JSON.stringify(mcpDraft.tools, null, 2)} onChange={(event) => setMcpDraft({ ...mcpDraft, tools: safeParseToolMap(event.target.value) })} /></label>
                  <label className="field"><span>{t(locale, "manager_mcp_headers_json")}</span><textarea rows={3} value={JSON.stringify(mcpDraft.http_headers, null, 2)} onChange={(event) => setMcpDraft({ ...mcpDraft, http_headers: safeParseStringMap(event.target.value) })} /></label>
                  <label className="field"><span>{t(locale, "manager_mcp_trust_note")}</span><textarea rows={3} value={mcpDraft.trust_note} onChange={(event) => setMcpDraft({ ...mcpDraft, trust_note: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_mcp_source_url")}</span><input value={mcpDraft.source_url} onChange={(event) => setMcpDraft({ ...mcpDraft, source_url: event.target.value })} /></label>
                </div>
              </div>
            ) : (
              <div className="metadata-detail-pane empty-state">{t(locale, "manager_mcp_empty")}</div>
            )}
          </div>
        </div>
      ) : null}

        {tab === "extensions" ? (
          <PluginSkillInventoryPanel
            locale={locale}
            snapshot={runtimePluginSkillRegistry.data}
            isLoading={runtimePluginSkillRegistry.isLoading || runtimePluginSkillRegistry.isFetching}
            error={runtimePluginSkillRegistry.error}
            project={project}
            onProjectChanged={(nextProject) => setProject(nextProject)}
            onRegistryChanged={() => runtimePluginSkillRegistry.refetch()}
          />
        ) : null}

      {tab === "runtime" ? (
        <div className="manager-panel">
          <div className="manager-hero">
            <div>
              <span className="eyebrow">{t(locale, "manager_runtime_setup")}</span>
              <h3>{wslDependencies.data?.ok ? t(locale, "manager_runtime_ready_title") : t(locale, "manager_runtime_needs_setup_title")}</h3>
              <p className="muted">{t(locale, "manager_runtime_summary")}</p>
            </div>
            <span className={`session-badge ${wslDependencies.data?.ok ? "capability-ok" : "capability-warn"}`}>
              {wslDependencies.data?.ok ? t(locale, "manager_runtime_ready") : t(locale, "manager_runtime_needs_setup")}
            </span>
          </div>
          <div className="metadata-actions">
            <label className="field wsl-distro-field">
              <span>{t(locale, "manager_runtime_distro")}</span>
              <input value={wslSetupDistro} onChange={(event) => setWslSetupDistro(event.target.value)} placeholder="Ubuntu-24.04" />
            </label>
            <div className="field-row">
              <button type="button" className="ghost-button" onClick={() => wslDependencies.refetch()} disabled={wslDependencies.isFetching}>{t(locale, "manager_runtime_recheck")}</button>
              <button type="button" className="ghost-button" onClick={() => isolationAudit.refetch()} disabled={isolationAudit.isFetching}>{t(locale, "manager_runtime_refresh_audit")}</button>
              <button type="button" className="ghost-button" onClick={() => writeWslScripts.mutate()} disabled={writeWslScripts.isPending}>{t(locale, "manager_runtime_generate_scripts")}</button>
              <button type="button" className="primary-button" onClick={() => launchWslInstaller.mutate()} disabled={launchWslInstaller.isPending}>{t(locale, "manager_runtime_run_installer")}</button>
            </div>
          </div>
          {wslDependencies.error ? <p className="error-text">{String((wslDependencies.error as Error).message ?? wslDependencies.error)}</p> : null}
          <RuntimeKernelStatusPanel
            locale={locale}
            snapshot={runtimeKernelProbe.data}
            isLoading={runtimeKernelProbe.isLoading || runtimeKernelProbe.isFetching}
            error={runtimeKernelProbe.error}
          />
          {isolationAudit.error ? <p className="error-text">{String((isolationAudit.error as Error).message ?? isolationAudit.error)}</p> : null}
          {isolationAudit.data ? (
            <section className="metadata-section">
              <div className="section-header">
                <h4>{t(locale, "manager_runtime_audit")}</h4>
                <span className={`status-tag ${isolationAudit.data.ok ? "status-ok" : ""}`}>
                  {isolationSummary.failed === 0 ? "pass" : `${isolationSummary.failed} fail`}
                </span>
              </div>
              <div className="mcp-health-row">
                <span>{isolationSummary.passed}/{isolationSummary.total} {t(locale, "manager_runtime_checks_passed")}</span>
                <span>{isolationAudit.data.process_boundary.execution_host || t(locale, "manager_runtime_unknown_host")}</span>
                <span>sidecar {isolationAudit.data.ports.sidecar ?? "n/a"}</span>
                <span>router {isolationAudit.data.ports.router ?? "n/a"}</span>
              </div>
              <div className="env-list">
                <div><span>{t(locale, "manager_runtime_workspace_state")}</span><strong>{isolationAudit.data.paths.astrabridge_state || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_project_root")}</span><strong>{isolationAudit.data.paths.project_runtime_root || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_isolated_home")}</span><strong>{isolationAudit.data.paths.isolated_codex_home || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_downloads_root")}</span><strong>{isolationAudit.data.paths.downloads_root || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_caches_root")}</span><strong>{isolationAudit.data.paths.caches_root || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_temp_root")}</span><strong>{isolationAudit.data.paths.tmp_root || "n/a"}</strong></div>
              </div>
              {isolationSummary.failed ? (
                <div className="manager-list">
                  {isolationSummary.failedChecks.slice(0, 8).map((check) => (
                    <div className="manager-row" key={check.name}>
                      <span>
                        <strong>{check.name}</strong>
                        <small>{t(locale, "manager_runtime_check_failed")}</small>
                      </span>
                      <code>{stringifyDetail(check.detail) || t(locale, "manager_runtime_no_detail")}</code>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">{t(locale, "manager_runtime_audit_pass_summary")}</p>
              )}
            </section>
          ) : null}
          {writeWslScripts.error || launchWslInstaller.error ? <p className="error-text">{String(((writeWslScripts.error || launchWslInstaller.error) as Error).message ?? writeWslScripts.error ?? launchWslInstaller.error)}</p> : null}
          <div className="wsl-check-grid">
            {(wslDependencies.data?.checks ?? []).map((check) => (
              <section key={check.id} className={`wsl-check-card wsl-check-${check.status}`}>
                <div className="wsl-check-head">
                  <strong>{check.label}</strong>
                  <span>{check.status}</span>
                </div>
                <p>{check.detail}</p>
                {check.remediation ? <small>{check.remediation}</small> : null}
              </section>
            ))}
          </div>
          <div className="metadata-section">
            <h4>{t(locale, "manager_runtime_managed_paths")}</h4>
            <div className="env-list">
              <div><span>{t(locale, "manager_runtime_codex_bin")}</span><strong>{wslDependencies.data?.paths.astrabridge_wsl_codex_bin ?? "$HOME/.local/share/astrabridge/bin/codex"}</strong></div>
              <div><span>CODEX_HOME</span><strong>{wslDependencies.data?.paths.astrabridge_wsl_codex_home ?? "$HOME/.local/share/astrabridge/codex-home"}</strong></div>
              <div><span>{t(locale, "manager_runtime_installed_distros")}</span><strong>{(wslDependencies.data?.distros ?? []).map((item) => `${item.name}${item.version ? ` WSL${item.version}` : ""}`).join(", ") || t(locale, "manager_runtime_none_detected")}</strong></div>
            </div>
          </div>
          {wslSetupOutput ? <pre className="json-preview compact-preview">{wslSetupOutput}</pre> : null}
        </div>
      ) : null}

      {tab === "automations" ? (
        <AutomationsPanel
          locale={locale}
          projectId={project?.project_id ?? ""}
          profiles={profiles.data?.profiles ?? []}
          automations={automations.data?.automations ?? []}
          runs={automationRuns.data?.runs ?? []}
          inboxItems={automationInbox.data?.items ?? []}
          scheduler={automationScheduler.data?.scheduler ?? null}
          supervisorAutomations={null}
          mcpPresetOptions={automationMcpPresetOptions}
          pluginSkillPresetOptions={automationPluginSkillPresetOptions}
          isBusy={
            createAutomation.isPending ||
            updateAutomation.isPending ||
            deleteAutomation.isPending ||
            pauseAutomation.isPending ||
            resumeAutomation.isPending ||
            runAutomationNow.isPending ||
            cancelAutomationRun.isPending ||
            updateAutomationInboxItem.isPending ||
            promoteAutomationInboxItem.isPending
          }
          onCreate={(payload) => createAutomation.mutate(payload)}
          onUpdate={(automationId, patch) => updateAutomation.mutate({ automationId, patch })}
          onDelete={(automationId) => deleteAutomation.mutate(automationId)}
          onPause={(automationId) => pauseAutomation.mutate(automationId)}
          onResume={(automationId) => resumeAutomation.mutate(automationId)}
          onRunNow={(automationId) => runAutomationNow.mutate(automationId)}
          onCancelRun={(runId) => cancelAutomationRun.mutate(runId)}
          onMarkReviewed={(itemId) => updateAutomationInboxItem.mutate({ itemId, patch: { state: "reviewed" } })}
          onArchive={(itemId) => updateAutomationInboxItem.mutate({ itemId, patch: { state: "archived" } })}
          onPromote={(itemId, promotionRef) => promoteAutomationInboxItem.mutate({ itemId, promotionRef })}
        />
      ) : null}

      {tab === "saves" ? (
        <div className="manager-panel" data-testid="saves-panel">
          <div className="manager-hero">
            <div>
              <span className="eyebrow">检查点</span>
              <h3>保存 / 载入</h3>
              <p className="muted">本地检查点保存在工作区 `.astrabridge/saves` 下。这里对 Git 只读，不会创建 commit、tag、remote，也不会改 Git 配置。</p>
            </div>
            <span className="session-badge">{visibleCheckpoints.length} 个检查点</span>
          </div>
          <div className="manager-grid">
            <section className="manager-section manager-section-wide">
              <h4>已保存的检查点</h4>
              <div className="checkpoint-list">
                {visibleCheckpoints.map((save) => (
                  <div className="checkpoint-row" data-testid="checkpoint-row" key={save.save_id}>
                    <div className="checkpoint-copy">
                      <strong>{save.description || save.default_description}</strong>
                      <small>{save.project_name} / {save.thread_name || "线程"} / {formatMessageTime(save.created_at)}</small>
                      <span>{save.workspace.is_git_repo ? `Git ${save.workspace.base_commit?.slice(0, 8) ?? "unknown"}${save.workspace.dirty ? " / dirty" : ""}` : "工作区快照"} / {save.workspace.file_count ?? 0} 个文件</span>
                    </div>
                    <div className="checkpoint-actions">
                      <button
                        type="button"
                        data-testid="checkpoint-preview-button"
                        className="ghost-button"
                        onClick={() => previewCheckpoint.mutate(save.save_id)}
                        disabled={previewCheckpoint.isPending}
                      >
                        预览
                      </button>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={async () => {
                          const previewResult = await api.loadProjectSave({ save_id: save.save_id, preview: true });
                          const message = previewResult.dirty
                            ? `当前工作区有未保存变化。AstraBridge 会先创建一个载入前恢复点，然后再载入“${save.description || save.default_description}”。继续吗？`
                            : `要载入“${save.description || save.default_description}”吗？`;
                          if (window.confirm(message)) loadCheckpoint.mutate(save.save_id);
                        }}
                        disabled={loadCheckpoint.isPending}
                      >
                        载入
                      </button>
                      <button type="button" className="ghost-button" onClick={() => window.confirm("确定删除这个检查点吗？") && deleteCheckpoint.mutate(save.save_id)} disabled={deleteCheckpoint.isPending}>删除</button>
                    </div>
                  </div>
                ))}
                {visibleCheckpoints.length === 0 ? <p className="muted">还没有检查点。可以在助手消息右下角点击“保存”。</p> : null}
              </div>
            </section>
            <section className="manager-section">
              <h4>预览</h4>
              {previewCheckpoint.data ? (
                <div className="checkpoint-preview" data-testid="checkpoint-preview-panel">
                  <strong>{previewCheckpoint.data.save.description || previewCheckpoint.data.save.default_description}</strong>
                  <span>{previewCheckpoint.data.dirty ? "当前工作区有未保存变化" : "当前工作区状态适合直接载入"}</span>
                  <small>{(previewCheckpoint.data.changed_files ?? []).slice(0, 8).join("\n") || "没有报告变化文件。"}</small>
                </div>
              ) : (
                <p className="muted">载入前先预览，可以看到当前工作区是否存在未保存变化。</p>
              )}
              {previewCheckpoint.error ? <p className="error-text">{String((previewCheckpoint.error as Error).message ?? previewCheckpoint.error)}</p> : null}
              {loadCheckpoint.error ? <p className="error-text">{String((loadCheckpoint.error as Error).message ?? loadCheckpoint.error)}</p> : null}
              {deleteCheckpoint.error ? <p className="error-text">{String((deleteCheckpoint.error as Error).message ?? deleteCheckpoint.error)}</p> : null}
            </section>
          </div>
        </div>
      ) : null}

      {tab === "dogfood" ? (
        <div className="manager-panel">
          <div className="manager-hero">
            <div>
              <span className="eyebrow">Dogfood Run</span>
              <h3>{activeDogfood?.enabled ? activeDogfood.phase || "active" : "Not active"}</h3>
              <p className="muted">Project-local supervision ledger for autonomous model runs. It records budgets, screenshots, blockers, and next steps under .astrabridge only.</p>
            </div>
            <span className={`session-badge ${activeDogfood?.enabled ? "capability-ok" : ""}`}>{activeDogfood?.status ?? "idle"}</span>
          </div>
          {activeDogfood ? (
            <div className="manager-grid">
              <section className="manager-section">
                <h4>Run control</h4>
                <div className="check-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={activeDogfood.enabled}
                      onChange={(event) => setDogfoodDraft({ ...activeDogfood, enabled: event.target.checked })}
                    />
                    Enabled
                  </label>
                </div>
                <label className="field"><span>Goal</span><textarea rows={3} value={activeDogfood.goal} onChange={(event) => setDogfoodDraft({ ...activeDogfood, goal: event.target.value })} /></label>
                <div className="form-grid">
                  <label className="field"><span>Phase</span><input value={activeDogfood.phase} onChange={(event) => setDogfoodDraft({ ...activeDogfood, phase: event.target.value })} /></label>
                  <label className="field"><span>Status</span><select value={activeDogfood.status} onChange={(event) => setDogfoodDraft({ ...activeDogfood, status: event.target.value })}><option value="idle">idle</option><option value="running">running</option><option value="waiting">waiting</option><option value="blocked">blocked</option><option value="complete">complete</option></select></label>
                  <label className="field"><span>Current provider</span><input value={activeDogfood.current_provider} onChange={(event) => setDogfoodDraft({ ...activeDogfood, current_provider: event.target.value })} placeholder="deepseek / kimi / yunwu_image" /></label>
                  <label className="field"><span>Warn percent</span><input type="number" value={activeDogfood.budgets.warn_percent} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, warn_percent: Number(event.target.value) || 80 } })} /></label>
                </div>
                <label className="field"><span>Blocker</span><textarea rows={2} value={activeDogfood.blocker} onChange={(event) => setDogfoodDraft({ ...activeDogfood, blocker: event.target.value })} /></label>
                <label className="field"><span>Next step</span><textarea rows={2} value={activeDogfood.next_step} onChange={(event) => setDogfoodDraft({ ...activeDogfood, next_step: event.target.value })} /></label>
                <div className="field-row">
                  <button type="button" className="primary-button" disabled={saveDogfood.isPending} onClick={() => saveDogfood.mutate(activeDogfood)}>Save run</button>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => setDogfoodDraft({
                      ...activeDogfood,
                      enabled: true,
                      phase: "astrabridge_autonomy_hardening",
                      status: "running",
                      goal: activeDogfood.goal || "Build a playable original anime magical-girl tower game while evaluating AstraBridge autonomy.",
                      current_provider: activeDogfood.current_provider || "deepseek",
                      budgets: { ...activeDogfood.budgets, kimi_cny: 50, deepseek_cny: 50, yunwu_gpt_usd: 50, yunwu_images: 200, warn_percent: 80 },
                    })}
                  >
                    Use tower-game defaults
                  </button>
                </div>
                {saveDogfood.error ? <p className="error-text">{String(saveDogfood.error as Error)}</p> : null}
                <p className="muted">Ledger path: {dogfoodRun.data?.path ?? ""}</p>
              </section>
              <section className="manager-section">
                <h4>Asset memory</h4>
                <p className="muted">Generated and sliced assets are tracked as project memory, then auto-injected into future DS/Kimi/Yunwu turns as a compact context pack.</p>
                <div className="dogfood-budget-list">
                  <div className="dogfood-budget">
                    <div><strong>Total assets</strong><span>{assetSummaryCount(assetSummary, "total")}</span></div>
                  </div>
                  <div className="dogfood-budget">
                    <div><strong>In game</strong><span>{assetSummaryCount(assetSummary, "promoted_or_in_use")}</span></div>
                  </div>
                  <div className="dogfood-budget">
                    <div><strong>Approved, not used</strong><span>{assetSummaryCount(assetSummary, "approved_unpromoted")}</span></div>
                  </div>
                  <div className="dogfood-budget">
                    <div><strong>Needs review</strong><span>{assetSummaryCount(assetSummary, "needs_review")}</span></div>
                  </div>
                </div>
                <div className="field-row">
                  <button type="button" className="ghost-button" onClick={() => rebuildDogfoodAssets.mutate()} disabled={rebuildDogfoodAssets.isPending}>Rebuild registry</button>
                  <span className="muted">{assetRegistry?.rebuilt_at ? `rebuilt ${summarizeRelativeTime(assetRegistry.rebuilt_at)}` : "registry not built"}</span>
                </div>
                <div className="manager-list manager-list-tall">
                  {[...promotedAssets.slice(0, 4), ...approvedAssets.slice(0, 6), ...reviewAssets.slice(0, 4)].map((asset) => (
                    <div className="manager-row" key={asset.asset_id}>
                      <span>
                        <strong>{asset.asset_id}</strong>
                        <small>{compactAssetLabel(asset)}</small>
                      </span>
                      <code>{asset.promoted_path || asset.source_path || asset.sliced_manifest_path || "path n/a"}</code>
                    </div>
                  ))}
                  {assetRegistry && assetRegistry.assets.length === 0 ? <p className="muted">No generated or sliced assets registered yet.</p> : null}
                  {dogfoodAssets.error ? <p className="error-text">{String((dogfoodAssets.error as Error).message ?? dogfoodAssets.error)}</p> : null}
                </div>
                <div className="form-grid">
                  <label className="field"><span>Asset ID</span><input value={assetPromoteDraft.asset_id} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, asset_id: event.target.value })} placeholder="yunwu-..._heroine_fullbody_000" /></label>
                  <label className="field"><span>Target file</span><input value={assetPromoteDraft.target_name} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, target_name: event.target.value })} placeholder="heroine_walk_down_0.png" /></label>
                  <label className="field"><span>Manifest section</span><select value={assetPromoteDraft.manifest_section} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, manifest_section: event.target.value as "sprites" | "tiles" | "hud" })}><option value="sprites">sprites</option><option value="tiles">tiles</option><option value="hud">hud</option></select></label>
                  <label className="field"><span>Entity</span><input value={assetPromoteDraft.entity} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, entity: event.target.value })} placeholder="heroine / shadow_sprite" /></label>
                  <label className="field"><span>State or tile key</span><input value={assetPromoteDraft.state} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, state: event.target.value })} placeholder="walk_down / forest_edge" /></label>
                </div>
                <button type="button" className="primary-button" onClick={() => promoteDogfoodAsset.mutate()} disabled={promoteDogfoodAsset.isPending || !assetPromoteDraft.asset_id.trim()}>Promote to game manifest</button>
                {promoteDogfoodAsset.error ? <p className="error-text">{String((promoteDogfoodAsset.error as Error).message ?? promoteDogfoodAsset.error)}</p> : null}
                <p className="muted">Context pack: {assetContextPack?.context_pack_path ?? "not written yet"}</p>
              </section>
              <section className="manager-section">
                <h4>Budgets</h4>
                <div className="dogfood-budget-list">
                  {dogfoodBudgetRows.map((row) => {
                    const percent = budgetPercent(row.used, row.cap);
                    const danger = percent >= 100;
                    const warn = percent >= activeDogfood.budgets.warn_percent;
                    return (
                      <div className={`dogfood-budget ${danger ? "dogfood-budget-danger" : warn ? "dogfood-budget-warn" : ""}`} key={row.key}>
                        <div>
                          <strong>{row.label}</strong>
                          <span>{row.used} / {row.cap}</span>
                        </div>
                        <div className="dogfood-meter" aria-label={`${row.label} ${percent}%`}>
                          <span style={{ width: `${percent}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="form-grid">
                  <label className="field"><span>Kimi cap</span><input type="number" value={activeDogfood.budgets.kimi_cny} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, kimi_cny: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>Kimi used</span><input type="number" value={activeDogfood.usage.kimi_cny} onChange={(event) => setDogfoodDraft({ ...activeDogfood, usage: { ...activeDogfood.usage, kimi_cny: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>DeepSeek cap</span><input type="number" value={activeDogfood.budgets.deepseek_cny} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, deepseek_cny: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>DeepSeek used</span><input type="number" value={activeDogfood.usage.deepseek_cny} onChange={(event) => setDogfoodDraft({ ...activeDogfood, usage: { ...activeDogfood.usage, deepseek_cny: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>Yunwu GPT cap</span><input type="number" value={activeDogfood.budgets.yunwu_gpt_usd ?? 50} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, yunwu_gpt_usd: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>Yunwu GPT used</span><input type="number" value={activeDogfood.usage.yunwu_gpt_usd ?? 0} onChange={(event) => setDogfoodDraft({ ...activeDogfood, usage: { ...activeDogfood.usage, yunwu_gpt_usd: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>Image cap</span><input type="number" value={activeDogfood.budgets.yunwu_images} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, yunwu_images: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>Images used</span><input type="number" value={activeDogfood.usage.yunwu_images} onChange={(event) => setDogfoodDraft({ ...activeDogfood, usage: { ...activeDogfood.usage, yunwu_images: Number(event.target.value) || 0 } })} /></label>
                </div>
              </section>
              <section className="manager-section">
                <h4>Recent captures</h4>
                <div className="manager-list manager-list-tall">
                  {activeDogfood.captures.slice(0, 12).map((capture) => (
                    <div className="manager-row" key={`${capturePath(capture)}-${captureCreatedAt(capture)}`}>
                      <span>
                        <strong>{captureLabel(capture)}</strong>
                        <small>{capture.provider || "manual"} · {capture.created_at ? summarizeRelativeTime(capture.created_at) : ""}</small>
                      </span>
                      <code>{capturePath(capture)}</code>
                    </div>
                  ))}
                  {activeDogfood.captures.length === 0 ? <p className="muted">No screenshots registered yet. Browser smoke auto-saves under {captureRoot || "the project .astrabridge/captures root"} and manual captures can be registered from there.</p> : null}
                </div>
              </section>
              <section className="manager-section">
                <h4>Browser smoke</h4>
                <p className="muted">Local-only browser smoke. AstraBridge visits the URL, tries to capture a screenshot with Playwright when available, records console issues, and writes an automatic milestone.</p>
                <label className="field"><span>URL</span><input value={dogfoodSmokeUrl} onChange={(event) => setDogfoodSmokeUrl(event.target.value)} /></label>
                <div className="form-grid">
                  <label className="field"><span>Label</span><input value={dogfoodSmokeLabel} onChange={(event) => setDogfoodSmokeLabel(event.target.value)} /></label>
                  <label className="field"><span>Screenshot path</span><input value={dogfoodScreenshotPath} onChange={(event) => setDogfoodScreenshotPath(event.target.value)} placeholder={suggestedScreenshotPath || ".astrabridge\\captures\\browser-smoke.png"} /></label>
                </div>
                <p className="muted">Leave the screenshot path as suggested to keep captures inside the current project boundary.</p>
                <button type="button" className="ghost-button" onClick={() => runDogfoodBrowserSmoke.mutate()} disabled={runDogfoodBrowserSmoke.isPending}>Run browser smoke</button>
                {activeDogfood.browser_smokes?.slice(-3).reverse().map((smoke) => (
                  <div className={`manager-row dogfood-smoke-${smoke.status}`} key={`${smoke.url}-${smoke.created_at}`}>
                    <span><strong>{smoke.label}</strong><small>{smoke.status} · {smoke.http_status ?? "n/a"} · {smoke.screenshot_status ?? "screenshot n/a"}</small></span>
                    <code>{smoke.url}</code>
                  </div>
                ))}
                {runDogfoodBrowserSmoke.error ? <p className="error-text">{String((runDogfoodBrowserSmoke.error as Error).message ?? runDogfoodBrowserSmoke.error)}</p> : null}
              </section>
              <section className="manager-section">
                <h4>Milestone note</h4>
                <label className="field"><span>Label</span><input value={dogfoodMilestoneLabel} onChange={(event) => setDogfoodMilestoneLabel(event.target.value)} /></label>
                <label className="field"><span>Validation</span><textarea rows={3} value={dogfoodMilestoneValidation} onChange={(event) => setDogfoodMilestoneValidation(event.target.value)} /></label>
                <button type="button" className="primary-button" onClick={() => saveDogfoodMilestone.mutate()} disabled={saveDogfoodMilestone.isPending}>Save milestone</button>
                {activeDogfood.milestones?.slice(-3).reverse().map((milestone) => (
                  <div className="manager-row" key={`${milestone.label}-${milestone.created_at}`}>
                    <span><strong>{milestone.label}</strong><small>{milestone.provider || "provider n/a"} · {milestone.status}</small></span>
                    <code>{milestone.validation.slice(0, 2).join(" · ")}</code>
                  </div>
                ))}
                {saveDogfoodMilestone.error ? <p className="error-text">{String((saveDogfoodMilestone.error as Error).message ?? saveDogfoodMilestone.error)}</p> : null}
              </section>
              <section className="manager-section">
                <h4>Autonomy rules for the next agent turn</h4>
                <p className="muted">Paste this into the next DS/Kimi turn when the run starts or resumes. It keeps the model from reading huge .astrabridge logs and forces self-verification.</p>
                <pre className="modal-json">{`Do not read .astrabridge/runtime_events.jsonl or .astrabridge/approvals.jsonl unless the user explicitly asks. Use project summaries, screenshots, and asset_manifest.json instead. After each milestone: run the game, inspect console errors, save a screenshot to ${captureRoot || ".astrabridge\\captures"}, describe the issue, then fix it. Respect budgets: Kimi 50 CNY, DeepSeek 50 CNY, Yunwu GPT 50 USD, Yunwu image 200 images. Stop at 100% and warn at 80%.`}</pre>
              </section>
            </div>
          ) : (
            <div className="empty-state">Dogfood run state is loading.</div>
          )}
        </div>
      ) : null}

      {tab === "reports" ? (
        <div className="metadata-dashboard">
          <div className="metadata-actions">
            <div>
              <span className="eyebrow">Curator skill</span>
              <h3>Reports and metadata refresh</h3>
              <p className="muted">Fetch official source status, rebuild the generated catalog, preview review artifacts, and generate sanitized reports. Key files are read only during health checks.</p>
            </div>
            <div className="field-row">
              <button type="button" className="ghost-button" onClick={() => importSeed.mutate()} disabled={importSeed.isPending}>Import seed</button>
              <button type="button" className="ghost-button" onClick={() => startMetadataRefresh.mutate(false)} disabled={startMetadataRefresh.isPending || metadataRefreshStatus.data?.running}>Dry refresh</button>
              <button type="button" className="primary-button" onClick={() => startMetadataRefresh.mutate(true)} disabled={startMetadataRefresh.isPending || metadataRefreshStatus.data?.running}>Apply refresh</button>
            </div>
          </div>
          {metadataRefreshStatus.data ? (
            <section className="metadata-source-card">
              <div>
                <strong>Latest refresh</strong>
                <span>{metadataRefreshStatus.data.status}</span>
              </div>
              <p>
                {metadataRefreshStatus.data.summary
                  ? `${metadataRefreshStatus.data.summary.ok_sources}/${metadataRefreshStatus.data.summary.total_sources} sources ok`
                  : "No refresh summary yet."}
              </p>
              {metadataRefreshStatus.data.started_at ? <p className="muted">Started: {metadataRefreshStatus.data.started_at}</p> : null}
              {metadataRefreshStatus.data.finished_at ? <p className="muted">Finished: {metadataRefreshStatus.data.finished_at}</p> : null}
              {metadataRefreshStatus.data.error ? <p className="error-text">{metadataRefreshStatus.data.error}</p> : null}
            </section>
          ) : null}
          <div className="metadata-source-list">
            {(metadataSources.data?.providers ?? []).map((source) => {
              const latest = (metadataRefreshStatus.data?.source_results ?? []).find((item) => String((item as Record<string, unknown>).provider_id ?? "") === source.provider_id) as Record<string, unknown> | undefined;
              return (
              <section key={source.provider_id} className="metadata-source-card">
                <div>
                  <strong>{source.display_name}</strong>
                  <span>{String(latest?.classification ?? source.source_status)}</span>
                </div>
                <p>{source.notes}</p>
                {latest ? <p className="muted">Latest: {String(latest.classification ?? "")} {String(latest.status_code ?? "")} {String(latest.duration_ms ?? "")}ms</p> : null}
                <ul>
                  {source.urls.map((url) => (
                    <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>
                  ))}
                </ul>
              </section>
            )})}
          </div>
          <div className="metadata-actions metadata-actions-compact">
            <div>
              <h3>Validation</h3>
              <p className="muted">Run a short matrix for the selected model, or generate the latest internal HTML report.</p>
            </div>
            <div className="field-row">
              <button type="button" className="ghost-button" onClick={() => runMatrix.mutate()} disabled={runMatrix.isPending}>{modelDraft?.id ? "Test selected model" : "Test small matrix"}</button>
              <button type="button" className="ghost-button" onClick={() => generateReport.mutate()} disabled={generateReport.isPending}>Generate report</button>
            </div>
          </div>
          {metadataOutput ? <pre className="json-preview">{metadataOutput}</pre> : null}
        </div>
      ) : null}

      {tab === "health" ? (
        <div className="manager-panel">
          <div className="manager-hero">
            <div>
              <span className="eyebrow">Capability health</span>
              <h3>Model checks</h3>
              <p className="muted">Short health checks update safe public metadata for connectivity, effort, temperature policy, web/source access, MCP/tool confidence, plan, goal, and context compaction readiness.</p>
            </div>
            <span className="session-badge">{llmHealth.data?.updated_at ? summarizeRelativeTime(llmHealth.data.updated_at) : "untested"}</span>
          </div>
          <div className="manager-grid">
            <section className="manager-section">
              <h4>Run check</h4>
              <label className="field"><span>Model</span><select value={modelDraft?.id ?? ""} onChange={(event) => setModelDraft((routerConfig.data?.models ?? []).find((model) => model.id === event.target.value) ?? null)}>{(routerConfig.data?.models ?? []).map((model) => <option key={model.id} value={model.id}>{model.id}</option>)}</select></label>
              <label className="field"><span>Efforts</span><input value={joinList(modelDraft?.supported_reasoning_levels?.length ? modelDraft.supported_reasoning_levels : providerReasoningOptions(selectedProvider, null))} readOnly /></label>
              <div className="field-row">
                <button
                  type="button"
                  className="primary-button"
                  disabled={!modelDraft?.id || runHealth.isPending}
                  onClick={() => {
                    const modelEfforts = modelDraft?.supported_reasoning_levels?.length ? modelDraft.supported_reasoning_levels : providerReasoningOptions(selectedProvider, null);
                    const preferredEffort = String(modelDraft?.default_reasoning_level ?? preferredProviderReasoningEffort(selectedProvider, null)).trim();
                    const prioritizedEfforts = [...new Set([preferredEffort, ...modelEfforts].filter(Boolean))];
                    runHealth.mutate({ model_ids: modelDraft?.id ? [modelDraft.id] : [], efforts: prioritizedEfforts.slice(0, 2), temperatures: [0], web_smoke: true });
                  }}
                >
                  Run selected model + web
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={runHealth.isPending}
                  onClick={() => {
                    const providerMap = new Map((routerConfig.data?.providers ?? []).map((provider) => [provider.id, provider]));
                    const efforts = Array.from(
                      new Set(
                        (routerConfig.data?.models ?? [])
                          .slice(0, 4)
                          .map((model) => {
                            const provider = providerMap.get(model.provider);
                            return String(model.default_reasoning_level ?? preferredProviderReasoningEffort(provider, null)).trim();
                          })
                          .filter(Boolean),
                      ),
                    );
                    runHealth.mutate({ model_ids: (routerConfig.data?.models ?? []).slice(0, 4).map((model) => model.id), efforts: efforts.length ? efforts : ["high"], temperatures: [0], web_smoke: true });
                  }}
                >
                  Run small set + web
                </button>
              </div>
              {runHealth.error ? <p className="error-text">{String(runHealth.error as Error)}</p> : null}
              {metadataOutput ? <pre className="modal-json">{metadataOutput}</pre> : null}
            </section>
            <section className="manager-section">
              <h4>Latest results</h4>
              <div className="manager-list manager-list-tall">
                {(llmHealth.data?.results ?? []).slice(-12).reverse().map((result, index) => {
                  const diagnosticsSummary = summarizeResponseDiagnosticsInline(result.response_diagnostics);
                  const failureSummary = runtimeErrorNoticeInline((result.failure_notice as RuntimeFailureNotice | null | undefined) ?? null);
                  return (
                    <div className="manager-row" key={`${String(result.run_id ?? "run")}-${index}`}>
                      <span>
                        <strong>{String(result.model ?? "-")}</strong>
                        <small>{String(result.provider ?? "")} / {String(result.effort ?? "")} / web {String(result.web_smoke_status ?? "n/a")} / {String(result.connectivity ?? result.reason ?? "")}</small>
                        {diagnosticsSummary ? <small>{diagnosticsSummary}</small> : failureSummary ? <small>{failureSummary}</small> : null}
                      </span>
                      <span className="manager-row-side">
                        <small>{result.ok ? "pass" : result.skipped ? "blocked" : "fail"}</small>
                      </span>
                    </div>
                  );
                })}
                {(llmHealth.data?.results ?? []).length === 0 ? <p className="muted">No health checks have been run yet.</p> : null}
              </div>
            </section>
          </div>
        </div>
      ) : null}

      {tab === "keys" ? (
        <div className="manager-panel">
          <div className="manager-hero">
            <div>
              <span className="eyebrow">Encrypted key vault</span>
              <h3>API Keys</h3>
              <p className="muted">Managed keys are AES-GCM encrypted per user. They are only injected into the sidecar process environment when Codex needs the selected provider.</p>
            </div>
            <span className={`session-badge session-badge-${managerMode}`}>{managerStatusLabel}</span>
          </div>
          <div className="manager-grid">
            <section className="manager-section">
              <h4>Add or replace key</h4>
              <label className="field"><span>{t(locale, "title_provider")}</span><select value={selectedProviderId} onChange={(event) => setSelectedProviderId(event.target.value)}>{(routerConfig.data?.providers ?? []).map((provider) => <option key={provider.id} value={provider.id}>{provider.display_name || provider.id}</option>)}</select></label>
              <label className="field"><span>Key label</span><input value={managedKeyDraft.label} onChange={(event) => setManagedKeyDraft({ ...managedKeyDraft, label: event.target.value })} placeholder={`${selectedProviderId || "provider"} primary`} /></label>
              <label className="field"><span>Env var name</span><input value={managedKeyDraft.env_key || selectedProvider?.env_key || ""} onChange={(event) => setManagedKeyDraft({ ...managedKeyDraft, env_key: event.target.value })} placeholder={selectedProvider?.env_key ?? "PROVIDER_API_KEY"} /></label>
              <label className="field"><span>Provider API key</span><input type="password" value={managedKeyDraft.secret} onChange={(event) => setManagedKeyDraft({ ...managedKeyDraft, secret: event.target.value })} placeholder={managerMode === "managed_user" ? "Stored encrypted in this user's vault" : "Login first to save in the vault"} /></label>
              <div className="field-row">
                <button
                  type="button"
                  className="primary-button"
                  disabled={managerMode !== "managed_user" || !selectedProviderId || !managedKeyDraft.secret.trim()}
                  onClick={() => saveManagedKey.mutate({
                    provider_id: selectedProviderId,
                    label: managedKeyDraft.label || `${selectedProviderId} key`,
                    env_key: managedKeyDraft.env_key || selectedProvider?.env_key,
                    secret: managedKeyDraft.secret,
                    make_default: true,
                  })}
                >
                  Save encrypted key
                </button>
                <button type="button" className="ghost-button" disabled={!selectedManagedKey} onClick={() => testManagedKey.mutate({ key_id: selectedManagedKey?.key_id, provider_id: selectedManagedKey?.provider_id })}>Test selected</button>
              </div>
              {saveManagedKey.error || testManagedKey.error ? <p className="error-text">{String((saveManagedKey.error || testManagedKey.error) as Error)}</p> : null}
              {testOutput ? <pre className="modal-json">{testOutput}</pre> : null}
            </section>
            <section className="manager-section">
              <h4>Managed keys</h4>
              <div className="manager-list">
                {((llmKeys.data?.keys ?? []) as LlmManagerKey[]).map((key) => (
                  <button key={key.key_id} type="button" className={selectedKeyId === key.key_id ? "manager-row manager-row-active" : "manager-row"} onClick={() => setSelectedKeyId(key.key_id)}>
                    <span>
                      <strong>{key.label}</strong>
                      <small>{key.provider_id} 路 {key.env_key}</small>
                    </span>
                    <span className="manager-row-side">
                      <code>{key.fingerprint}</code>
                      <small>{key.last_test_status ?? "untested"}</small>
                    </span>
                  </button>
                ))}
                {llmKeys.data?.locked ? <p className="muted">Unlock a managed user to list encrypted keys.</p> : null}
              </div>
              <div className="field-row">
                <button type="button" className="ghost-button" disabled={!selectedManagedKey} onClick={() => selectedManagedKey && api.llmManagerDeleteKey(selectedManagedKey.key_id).then(() => queryClient.invalidateQueries({ queryKey: ["llm-manager-keys"] }))}>Delete selected</button>
              </div>
            </section>
          </div>
          <section className="manager-section">
            <h4>Anonymous/session key fallback</h4>
            <p className="muted">{t(locale, "key_setup_summary_compact")}</p>
            <label className="field"><span>{t(locale, "runtime_secret")}</span><input type="password" value={secretValue} onChange={(event) => setSecretValue(event.target.value)} placeholder={t(locale, "key_setup_input_placeholder")} /></label>
            <div className="field-row">
              <button type="button" className="ghost-button" disabled={!selectedProviderId || !secretValue.trim()} onClick={() => loadSecret.mutate({ profileId: `${selectedProviderId}-default`, payload: { session_key: secretValue, persist_to_keychain: false } })}>{t(locale, "key_setup_use")}</button>
              <button type="button" className="ghost-button" disabled={!selectedProviderId} onClick={() => handleProviderTest(false)}>{t(locale, "key_setup_test")}</button>
            </div>
          </section>
        </div>
      ) : null}

      </div>
    </section>
  );
}

function Launcher() {
  const queryClient = useQueryClient();
  const locale = useAppStore((store) => store.locale);
  const setLocale = useAppStore((store) => store.setLocale);
  const appearance = useAppStore((store) => store.appearance);
  const setAppearance = useAppStore((store) => store.setAppearance);
  const setProject = useAppStore((store) => store.setProject);
  const recent = useQuery({ queryKey: ["recent-projects"], queryFn: api.recentProjects });
  const [name, setName] = useState("Codex Workspace");
  const [projectFile, setProjectFile] = useState("");
  const [workspaceRoot, setWorkspaceRoot] = useState("");
  const [entryMode, setEntryMode] = useState<ProjectFile["entry_mode"]>("existing");
  const [openPath, setOpenPath] = useState("");
  const [settingsExpanded, setSettingsExpanded] = useState(false);

  const createProject = useMutation({
    mutationFn: api.createProject,
    onSuccess: (data) => {
      setProject(data.project);
      queryClient.invalidateQueries({ queryKey: ["recent-projects"] });
    },
  });

  const openProject = useMutation({
    mutationFn: api.openProject,
    onSuccess: (data) => {
      setProject(data.project);
      queryClient.invalidateQueries({ queryKey: ["recent-projects"] });
    },
  });

  useEffect(() => {
    document.documentElement.dataset.appearance = appearance;
  }, [appearance]);

  async function browseProjectFile() {
    const defaultPath = projectFile || `${workspaceRoot || name || "codex-workspace"}.abproj`;
    const selected = await chooseProjectSavePath(defaultPath);
    if (selected) setProjectFile(selected);
  }

  async function browseWorkspace() {
    const selected = await selectDirectory(t(locale, "browse_workspace"));
    if (selected) setWorkspaceRoot(selected);
  }

  async function browseExistingProject() {
    const selected = await selectExistingProject();
    if (selected) setOpenPath(selected);
  }

  return (
    <main className="launcher-shell">
      <section className="launcher-hero">
        <p className="eyebrow">{t(locale, "app_title")}</p>
        <h1>{t(locale, "create_project")}</h1>
        <p>{t(locale, "launcher_summary")}</p>
        <p className="muted">{t(locale, "setup_first")}</p>
        <p className="muted">{t(locale, "project_suffix_note")}</p>
        <div className="topbar-actions">
          <button type="button" className="ghost-button" onClick={() => setSettingsExpanded((value) => !value)}>
            {t(locale, "user_settings")}
          </button>
        </div>
        {settingsExpanded ? (
          <div className="stack">
            <div className="status-panel">
              <strong>{t(locale, "locale")}</strong>
              <span>{t(locale, "locale_note")}</span>
            </div>
            <div className="segmented">
              <button type="button" className={locale === "zh-CN" ? "segmented-active" : ""} onClick={() => setLocale("zh-CN")}>
                {t(locale, "locale_zh")}
              </button>
              <button type="button" className={locale === "en" ? "segmented-active" : ""} onClick={() => setLocale("en")}>
                {t(locale, "locale_en")}
              </button>
            </div>
            <div className="segmented segmented-wrap">
              {(["codex", "paper", "slate", "cobalt", "sunrise"] as AppearancePreset[]).map((item) => (
                <button key={item} type="button" className={appearance === item ? "segmented-active" : ""} onClick={() => setAppearance(item)}>
                  {t(locale, `appearance_${item}`)}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="launcher-panel">
        <div className="launcher-recent-column">
          <h2>{t(locale, "recent_projects")}</h2>
          <div className="launcher-recent">
            {(recent.data?.projects ?? []).map((project) => (
              <button
                type="button"
                key={project.project_file}
                className="recent-project"
                onClick={() => openProject.mutate(project.project_file)}
              >
                <strong>{project.name}</strong>
                <span>{project.workspace_root}</span>
                <time>{summarizeRelativeTime(project.updated_at)}</time>
              </button>
            ))}
            {!recent.isLoading && (recent.data?.projects ?? []).length === 0 ? <p className="muted">{t(locale, "project_none")}</p> : null}
          </div>
        </div>

        <div className="launcher-form-column">
        <div className="launcher-section stack">
          <div className="card-header">
            <h2>{t(locale, "create_project")}</h2>
            <span className="shortcut-hint">{t(locale, "new_project_hint")}</span>
          </div>
          <label className="field">
            <span>{t(locale, "project_name")}</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="field">
            <span>{t(locale, "project_file")}</span>
            <div className="field-row">
              <input value={projectFile} onChange={(event) => setProjectFile(event.target.value)} placeholder="D:/work/demo.abproj" />
              <button type="button" className="ghost-button" onClick={browseProjectFile}>
                {t(locale, "browse")}
              </button>
            </div>
          </label>
          <label className="field">
            <span>{t(locale, "workspace_root")}</span>
            <div className="field-row">
              <input value={workspaceRoot} onChange={(event) => setWorkspaceRoot(event.target.value)} placeholder="D:/work/demo" />
              <button type="button" className="ghost-button" onClick={browseWorkspace}>
                {t(locale, "browse")}
              </button>
            </div>
          </label>
          <div className="field">
            <span>{t(locale, "entry_mode")}</span>
            <div className="segmented">
              <button type="button" className={entryMode === "existing" ? "segmented-active" : ""} onClick={() => setEntryMode("existing")}>
                {t(locale, "entry_existing")}
              </button>
              <button type="button" className={entryMode === "new" ? "segmented-active" : ""} onClick={() => setEntryMode("new")}>
                {t(locale, "entry_new")}
              </button>
            </div>
          </div>
          <button
            type="button"
            className="primary-button"
            disabled={!name.trim() || (entryMode !== "new" && !projectFile.trim()) || createProject.isPending}
            onClick={() =>
              createProject.mutate({
                name,
                project_file: projectFile || "",
                workspace_root: workspaceRoot || undefined,
                entry_mode: entryMode,
              })
            }
          >
            {createProject.isPending ? t(locale, "loading") : t(locale, "create")}
          </button>
          {createProject.error ? <p className="error-text">{createProject.error.message}</p> : null}
        </div>

        <div className="launcher-section stack">
          <div className="card-header">
            <h2>{t(locale, "open_project")}</h2>
          </div>
          <label className="field">
            <span>{t(locale, "project_file")}</span>
            <div className="field-row">
              <input value={openPath} onChange={(event) => setOpenPath(event.target.value)} placeholder="D:/work/demo.abproj" />
              <button type="button" className="ghost-button" onClick={browseExistingProject}>
                {t(locale, "browse")}
              </button>
            </div>
          </label>
          <button
            type="button"
            className="primary-button"
            disabled={!openPath.trim() || openProject.isPending}
            onClick={() => openProject.mutate(openPath)}
          >
            {openProject.isPending ? t(locale, "loading") : t(locale, "open")}
          </button>
          {openProject.error ? <p className="error-text">{openProject.error.message}</p> : null}
        </div>
        </div>
      </section>
    </main>
  );
}

function AppShell() {
  const queryClient = useQueryClient();
  const project = useAppStore((store) => store.project)!;
  const locale = useAppStore((store) => store.locale);
  const appearance = useAppStore((store) => store.appearance);
  const setProject = useAppStore((store) => store.setProject);
  const eventCursor = useAppStore((store) => store.eventCursor);
  const setEventCursor = useAppStore((store) => store.setEventCursor);
  const eventSnapshot = useAppStore((store) => store.eventSnapshot);
  const eventCursorRef = useRef(eventCursor);
  const handleEventsRef = useRef<(events: RuntimeEvent[]) => void>(() => undefined);
  const [eventStreamActive, setEventStreamActive] = useState(false);
  const applyAgentDelta = useAppStore((store) => store.applyAgentDelta);
  const applyPlanDelta = useAppStore((store) => store.applyPlanDelta);
  const appendReasoningDelta = useAppStore((store) => store.appendReasoningDelta);
  const setTurnActivity = useAppStore((store) => store.setTurnActivity);
  const setTurnDiff = useAppStore((store) => store.setTurnDiff);
  const setPlan = useAppStore((store) => store.setPlan);
  const setTokenUsage = useAppStore((store) => store.setTokenUsage);
  const setThreadStatus = useAppStore((store) => store.setThreadStatus);
  const clearLiveTurn = useAppStore((store) => store.clearLiveTurn);
  const threadSettingsDraft = useAppStore((store) => store.threadSettingsDraft);
  const setThreadSettingsDraft = useAppStore((store) => store.setThreadSettingsDraft);
  const rightSidebarOpen = useAppStore((store) => store.rightSidebarOpen);
  const toggleRightSidebar = useAppStore((store) => store.toggleRightSidebar);
  const commandPaletteOpen = useAppStore((store) => store.commandPaletteOpen);
  const setCommandPaletteOpen = useAppStore((store) => store.setCommandPaletteOpen);
  const leftPane = useResizablePane("left");
  const rightPane = useResizablePane("right");

  const [composerText, setComposerText] = useState("");
  const [attachments, setAttachments] = useState<AttachmentDraft[]>([]);
  const [secretValue, setSecretValue] = useState("");
  const [profileForm, setProfileForm] = useState<Profile | null>(null);
  const [goalDraft, setGoalDraft] = useState("");
  const [archivedVisible, setArchivedVisible] = useState(false);
  const [routerBaseUrl, setRouterBaseUrl] = useState("http://127.0.0.1:8787/v1");
  const [mainView, setMainView] = useState<"chat" | "setup">("chat");
  const [sendStage, setSendStage] = useState<string | null>(null);
  const [sendFailure, setSendFailure] = useState<string | null>(null);
  const [executionHostDraft, setExecutionHostDraft] = useState<ExecutionHost>((project.ui_preferences.execution_host as ExecutionHost) ?? "windows");
  const [wslDistroDraft, setWslDistroDraft] = useState(project.ui_preferences.wsl_distro ?? "");
  const [guardDismissedFor, setGuardDismissedFor] = useState<string | null>(null);
  const [saveModal, setSaveModal] = useState<{ open: boolean; block?: ThreadRenderBlock | null }>({ open: false });
  const [saveDescription, setSaveDescription] = useState("");
  const [textEntryRequest, setTextEntryRequest] = useState<TextEntryRequest | null>(null);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("status");
  const [inspectorReviewPath, setInspectorReviewPath] = useState("");
  const [inspectorFileQuery, setInspectorFileQuery] = useState("");
  const [inspectorFilePath, setInspectorFilePath] = useState("");
  const smokeMode = useMemo(() => browserSmokeMode(), []);

  const profiles = useQuery({ queryKey: ["profiles"], queryFn: api.profiles, refetchInterval: 5000 });
  const routerConfig = useQuery({ queryKey: ["router-config"], queryFn: api.routerConfig, refetchInterval: 5000 });
  const llmSession = useQuery({ queryKey: ["llm-manager-session"], queryFn: api.llmManagerSession, refetchInterval: 5000 });
  const llmCatalog = useQuery({ queryKey: ["llm-manager-catalog"], queryFn: api.llmManagerEffectiveCatalog, refetchInterval: 5000 });
  const mcpConfig = useQuery({ queryKey: ["mcp-config"], queryFn: api.mcpConfig, refetchInterval: 7000 });
  const runtime = useQuery({
    queryKey: ["runtime-environment"],
    queryFn: api.runtimeEnvironment,
    refetchInterval: smokeMode ? false : 5000,
    retry: smokeMode ? false : undefined,
    staleTime: smokeMode ? 60_000 : 0,
  });
  const newThreadDraft = threadSettingsDraft["__new__"] ?? {};
  const listProfileId = newThreadDraft.profile_id ?? project.default_profile_id;
  const threads = useQuery({
    queryKey: ["threads", project.project_id, listProfileId, archivedVisible],
    queryFn: () => api.threads(listProfileId, archivedVisible),
    refetchInterval: smokeMode ? false : 4000,
    retry: smokeMode ? false : undefined,
  });
  const projectTasks = useQuery({
    queryKey: ["project-tasks", project.project_id],
    queryFn: api.projectTasks,
    refetchInterval: smokeMode ? false : 4000,
    retry: smokeMode ? false : undefined,
  });

  const currentTask = projectTasks.data?.current_task ?? null;
  const selectedThreadId = project.current_thread_id ?? currentTask?.active_provider_thread_id ?? threads.data?.threads[0]?.id ?? null;
  const sendTargetThreadId = currentTask?.active_provider_thread_id ?? selectedThreadId;
  const selectedThreadSummary = threads.data?.threads.find((thread) => thread.id === selectedThreadId);
  const selectedTaskProviderThread = currentTask?.provider_threads.find((thread) => thread.thread_id === selectedThreadId) ?? null;
  const selectedThreadProfileId =
    selectedTaskProviderThread?.profile_id ??
    threadSettingsDraft[selectedThreadId ?? ""]?.profile_id ??
    selectedThreadSummary?.shellSettings?.profile_id ??
    (!selectedThreadId ? listProfileId : null);
  const selectedThreadProfileReady = !selectedThreadId || Boolean(selectedThreadProfileId);
  const selectedThread = useQuery({
    queryKey: ["thread", selectedThreadId, selectedThreadProfileId],
    queryFn: () => api.readThread(selectedThreadId!, selectedThreadProfileId ?? undefined),
    enabled: Boolean(selectedThreadId && selectedThreadProfileReady),
    refetchInterval: smokeMode ? false : 4000,
    retry: smokeMode ? false : undefined,
  });
  const taskConversation = useQuery({
    queryKey: ["task-conversation", project.project_id, currentTask?.task_id, selectedThreadId],
    queryFn: () => api.taskConversation(currentTask?.task_id),
    enabled: Boolean(currentTask?.task_id),
    refetchInterval: smokeMode ? false : 4000,
    retry: smokeMode ? false : undefined,
  });
  const goal = useQuery({
    queryKey: ["goal", selectedThreadId, selectedThreadProfileId],
    queryFn: () => api.getGoal(selectedThreadId!, selectedThreadProfileId ?? undefined),
    enabled: Boolean(selectedThreadId && selectedThreadProfileReady),
    refetchInterval: smokeMode ? false : mainView === "chat" ? 4000 : false,
    retry: smokeMode ? false : undefined,
  });
  const pendingModals = useQuery({
    queryKey: ["pending-modals"],
    queryFn: api.pendingModals,
    refetchInterval: smokeMode ? false : 1000,
    retry: smokeMode ? false : undefined,
  });

  const switchThread = useMutation({
    mutationFn: api.switchThread,
    onSuccess: (data) => setProject(data.project),
  });
  const switchTask = useMutation({
    mutationFn: api.switchTask,
    onSuccess: (data) => {
      setProject(data.project);
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["goal"] });
    },
  });

  const createThread = useMutation({
    mutationFn: api.createThread,
    onSuccess: (data) => {
      setProject(data.project ?? { ...project, current_thread_id: data.thread.id, recent_threads: [data.thread.id, ...project.recent_threads.filter((id) => id !== data.thread.id)].slice(0, 20) });
      if (data.thread.shellSettings) {
        setThreadSettingsDraft(data.thread.id, data.thread.shellSettings);
      }
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
    },
  });

  const forkThread = useMutation({
    mutationFn: api.forkThread,
    onSuccess: (data) => {
      setProject(data.project ?? { ...project, current_thread_id: data.thread.id, recent_threads: [data.thread.id, ...project.recent_threads.filter((id) => id !== data.thread.id)].slice(0, 20) });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
    },
  });

  const renameThread = useMutation({
    mutationFn: ({ threadId, name }: { threadId: string; name: string }) => api.renameThread(threadId, name, selectedThreadProfileId ?? undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
    },
  });

  const archiveThread = useMutation({
    mutationFn: (threadId: string) => api.archiveThread(threadId, selectedThreadProfileId ?? undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["goal"] });
    },
  });

  const saveThreadSettings = useMutation({
    mutationFn: api.saveThreadSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["threads"] }),
  });

  const saveProfile = useMutation({
    mutationFn: api.saveProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    },
  });

  const loadSecret = useMutation({
    mutationFn: ({ profileId, payload }: { profileId: string; payload: { session_key?: string; key_file_path?: string; persist_to_keychain?: boolean } }) => api.loadSecret(profileId, payload),
    onSuccess: () => {
      setSecretValue("");
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    },
  });

  const setGoalMutation = useMutation({
    mutationFn: api.setGoal,
    onSuccess: (data) => {
      queryClient.setQueryData<GoalResponse>(["goal", selectedThreadId, selectedThreadProfileId], data);
      setGoalDraft(data.goal?.objective ?? "");
    },
  });

  const clearGoalMutation = useMutation({
    mutationFn: ({ threadId, profileId }: { threadId: string; profileId?: string }) => api.clearGoal(threadId, profileId),
    onSuccess: () => {
      setGoalDraft("");
      queryClient.invalidateQueries({ queryKey: ["goal"] });
    },
  });

  const startTurn = useMutation({
    mutationFn: api.startTurn,
    onSuccess: (data) => {
      if (data.project) {
        setProject(data.project);
      } else if (data.thread_id && data.thread_id !== selectedThreadId) {
        setProject({ ...project, current_thread_id: data.thread_id, recent_threads: [data.thread_id, ...project.recent_threads.filter((id) => id !== data.thread_id)].slice(0, 20) });
      }
      setComposerText("");
      setAttachments([]);
      setSendFailure(null);
      setSendStage(null);
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
    },
  });

  const interruptTurn = useMutation({
    mutationFn: ({ threadId, turnId, profileId }: { threadId: string; turnId: string; profileId?: string }) => api.interruptTurn(threadId, turnId, profileId),
  });
  const compactThread = useMutation({
    mutationFn: ({ threadId, profileId }: { threadId: string; profileId?: string }) => api.compactThread(threadId, profileId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
    },
  });
  const restartRuntime = useMutation({
    mutationFn: api.restartRuntime,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
    },
  });
  const supervisorDecision = useMutation({
    mutationFn: ({ action, threadId, turnId, profileId, model, effort, permissionMode }: { action: "continue" | "compact" | "fork" | "interrupt"; threadId: string; turnId?: string; profileId?: string; model?: string; effort?: string; permissionMode?: PermissionMode }) =>
      api.runtimeSupervisorDecision({ action, thread_id: threadId, turn_id: turnId, profile_id: profileId, model, effort, permission_mode: permissionMode }),
    onSuccess: () => {
      setGuardDismissedFor(liveTurnId ?? selectedThreadId ?? "dismissed");
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
    },
  });
  const inspectorBrowserSmoke = useMutation({
    mutationFn: () =>
      api.dogfoodBrowserSmoke({
        url: currentBrowserSmokeUrl(),
        label: "inspector release workflow smoke",
        preset: RELEASE_WORKFLOW_SMOKE_PRESET,
        include_run: true,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });
  const prepareReleaseWorkflowDemo = useMutation({
    mutationFn: api.prepareReleaseWorkflowDemo,
    onSuccess: (response) => {
      if (response.task?.task_id) {
        queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
        queryClient.invalidateQueries({ queryKey: ["task-conversation", response.task.task_id] });
      }
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
      queryClient.invalidateQueries({ queryKey: ["project-review-status"] });
      queryClient.invalidateQueries({ queryKey: ["project-files-tree"] });
      queryClient.invalidateQueries({ queryKey: ["project-terminal-history"] });
      queryClient.invalidateQueries({ queryKey: ["project-saves"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });
  const prepareNativeKernelWorkflowDemo = useMutation({
    mutationFn: () => {
      const settings = currentComposerSettings();
      return api.prepareNativeKernelWorkflowDemo({
        profile_id: settings.profile_id ?? undefined,
        provider_id: activeProfile?.provider_id ?? undefined,
        model: settings.model ?? undefined,
        effort: settings.reasoning_effort ?? undefined,
        permission_mode: settings.permission_mode,
        collaboration_mode: settings.collaboration_mode,
      });
    },
    onSuccess: (response) => {
      if (response.task?.task_id) {
        queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
        queryClient.invalidateQueries({ queryKey: ["task-conversation", response.task.task_id] });
      }
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
      queryClient.invalidateQueries({ queryKey: ["project-review-status"] });
      queryClient.invalidateQueries({ queryKey: ["project-files-tree"] });
      queryClient.invalidateQueries({ queryKey: ["project-terminal-history"] });
      queryClient.invalidateQueries({ queryKey: ["project-saves"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
    },
  });
  const inspectorProviderSwitchSmoke = useMutation({
    mutationFn: () =>
      api.dogfoodBrowserSmoke({
        url: currentBrowserSmokeUrl(),
        label: "inspector provider switch workflow smoke",
        preset: PROVIDER_SWITCH_WORKFLOW_SMOKE_PRESET,
        include_run: true,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });
  const inspectorNativeKernelSmoke = useMutation({
    mutationFn: () =>
      api.dogfoodBrowserSmoke({
        url: currentBrowserSmokeUrl(),
        label: "inspector native kernel workflow smoke",
        preset: NATIVE_KERNEL_WORKFLOW_SMOKE_PRESET,
        include_run: true,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
    },
  });

  const closeProject = useMutation({
    mutationFn: api.closeProject,
    onSuccess: () => setProject(null),
  });
  const saveProjectPreferences = useMutation({
    mutationFn: api.updateProjectPreferences,
    onSuccess: (data) => setProject(data.project),
  });
  const createCheckpoint = useMutation({
    mutationFn: api.createProjectSave,
    onSuccess: () => {
      setSaveModal({ open: false });
      setSaveDescription("");
      queryClient.invalidateQueries({ queryKey: ["project-saves"] });
    },
  });

  useEffect(() => {
    if (!selectedThreadId && currentTask?.active_provider_thread_id) {
      switchThread.mutate(currentTask.active_provider_thread_id);
      return;
    }
    if (!selectedThreadId && threads.data?.threads?.[0]) {
      switchThread.mutate(threads.data.threads[0].id);
    }
  }, [currentTask?.active_provider_thread_id, selectedThreadId, switchThread, threads.data?.threads]);

  useEffect(() => {
    if (!selectedThreadId || !selectedThread.data?.thread) return;
    if (threadSettingsDraft[selectedThreadId]) return;
    const settings = selectedThread.data.thread.shellSettings;
    setThreadSettingsDraft(selectedThreadId, settings);
  }, [selectedThreadId, selectedThread.data?.thread, setThreadSettingsDraft, threadSettingsDraft]);

  const activeSettings = useMemo(() => {
    const laneSettings = {
      profile_id: selectedTaskProviderThread?.profile_id,
      model: selectedTaskProviderThread?.model,
      reasoning_effort: selectedTaskProviderThread?.reasoning_effort,
      permission_mode: selectedTaskProviderThread?.permission_mode,
      collaboration_mode: selectedTaskProviderThread?.collaboration_mode,
    };
    const saved = selectedThread.data?.thread.shellSettings ?? {};
    const draft = threadSettingsDraft[selectedThreadId ?? "__new__"] ?? {};
    return {
      profile_id: draft.profile_id ?? laneSettings.profile_id ?? saved.profile_id ?? project.default_profile_id,
      model: draft.model ?? laneSettings.model ?? saved.model ?? project.default_model,
      reasoning_effort: draft.reasoning_effort ?? laneSettings.reasoning_effort ?? saved.reasoning_effort ?? project.default_effort,
      permission_mode: (draft.permission_mode ?? laneSettings.permission_mode ?? saved.permission_mode ?? "auto") as PermissionMode,
      collaboration_mode: (draft.collaboration_mode ?? laneSettings.collaboration_mode ?? saved.collaboration_mode ?? "default") as CollaborationMode,
    };
  }, [project.default_effort, project.default_model, project.default_profile_id, selectedTaskProviderThread, selectedThread.data?.thread.shellSettings, selectedThreadId, threadSettingsDraft]);
  const selectedThreadStatusType = selectedThread.data?.thread.status?.type ?? "idle";
  const supervisor = useQuery({
    queryKey: ["runtime-supervisor", selectedThreadId, activeSettings.profile_id],
    queryFn: () => api.runtimeSupervisor({ thread_id: selectedThreadId ?? undefined, profile_id: activeSettings.profile_id }),
    enabled: Boolean(selectedThreadId),
    refetchInterval: smokeMode ? false : mainView === "chat" && selectedThreadStatusType === "active" ? 2500 : false,
    retry: smokeMode ? false : undefined,
  });
  const inheritedTaskGoal = inheritedGoalFrom(currentTask?.goal, "task");
  const inheritedDogfoodGoal = inheritedGoalFrom(supervisor.data?.dogfood?.latest_milestone?.goal, "dogfood");
  const displayGoal = goal.data?.goal
    ? { objective: goal.data.goal.objective, status: goal.data.goal.status, source: "thread" as const }
    : inheritedTaskGoal ?? inheritedDogfoodGoal;
  const inspectorReview = useQuery({
    queryKey: ["project-review-status"],
    queryFn: api.projectReviewStatus,
    enabled: inspectorTab === "review",
    refetchInterval: smokeMode ? false : 5000,
    retry: smokeMode ? false : undefined,
  });
  const inspectorReviewDiff = useQuery({
    queryKey: ["project-review-diff", inspectorReviewPath],
    queryFn: () => api.projectReviewDiff(inspectorReviewPath),
    enabled: inspectorTab === "review" && Boolean(inspectorReviewPath),
  });
  const inspectorTerminal = useQuery({
    queryKey: ["project-terminal-history"],
    queryFn: api.projectTerminalHistory,
    enabled: inspectorTab === "terminal",
    refetchInterval: smokeMode ? false : 5000,
    retry: smokeMode ? false : undefined,
  });
  const inspectorDogfoodRun = useQuery({
    queryKey: ["dogfood-run"],
    queryFn: api.dogfoodRun,
    enabled: inspectorTab === "browser",
    refetchInterval: smokeMode ? false : 2500,
    retry: smokeMode ? false : undefined,
  });
  const inspectorFiles = useQuery({
    queryKey: ["project-files-tree", inspectorFileQuery],
    queryFn: () => api.projectFilesTree(inspectorFileQuery),
    enabled: inspectorTab === "files",
    refetchInterval: smokeMode ? false : 7000,
    retry: smokeMode ? false : undefined,
  });
  const inspectorFilePreview = useQuery({
    queryKey: ["project-file-preview", inspectorFilePath],
    queryFn: () => api.projectFileRead(inspectorFilePath),
    enabled: inspectorTab === "files" && Boolean(inspectorFilePath),
  });
  const settingsDraftTarget = selectedThreadId ?? "__new__";
  const latestComposerSettingsRef = useRef(activeSettings);
  const lastSavedThreadSettingsRef = useRef("");

  useEffect(() => {
    latestComposerSettingsRef.current = activeSettings;
  }, [activeSettings]);

  function updateComposerSettings(patch: Partial<typeof activeSettings>) {
    latestComposerSettingsRef.current = { ...latestComposerSettingsRef.current, ...patch };
    setThreadSettingsDraft(settingsDraftTarget, patch);
  }

  function currentComposerSettings() {
    const root = document.querySelector(".composer-controls");
    const profileControl = root?.querySelector('[data-composer="profile"]') as HTMLSelectElement | null;
    const modelControl = root?.querySelector('[data-composer="model"]') as HTMLSelectElement | HTMLInputElement | null;
    const effortControl = root?.querySelector('[data-composer="effort"]') as HTMLSelectElement | null;
    const permissionControl = root?.querySelector('[data-composer="permission"]') as HTMLSelectElement | null;
    const collaborationModeControl = root?.querySelector('[data-composer="collaboration-mode"]') as HTMLSelectElement | null;
    const domSettings = {
      profile_id: profileControl?.value,
      model: modelControl?.value,
      reasoning_effort: effortControl?.value,
      permission_mode: permissionControl?.value as PermissionMode | undefined,
      collaboration_mode: collaborationModeControl?.value as CollaborationMode | undefined,
    };
    const merged = {
      ...latestComposerSettingsRef.current,
      ...Object.fromEntries(Object.entries(domSettings).filter(([, value]) => value)),
    };
    latestComposerSettingsRef.current = merged;
    return merged;
  }

  const activeProfile = useMemo(() => {
    const list = profiles.data?.profiles ?? [];
    return list.find((profile) => profile.profile_id === activeSettings.profile_id) ?? list[0] ?? null;
  }, [activeSettings.profile_id, profiles.data?.profiles]);
  const providerOptions = useMemo(() => {
    const managerMode = llmSession.data?.mode ?? "anonymous";
    if (managerMode === "managed_user" && (llmCatalog.data?.providers ?? []).length > 0) {
      return (llmCatalog.data?.providers ?? [])
        .map((provider) => ({
          providerId: provider.id,
          profileId: `${provider.id}-default`,
          label: provider.id,
          title: provider.display_name || provider.id,
        }))
        .sort((left, right) => left.label.localeCompare(right.label));
    }
    const providerNames = new Map((routerConfig.data?.providers ?? []).map((provider) => [provider.id, provider.display_name]));
    const byProvider = new Map<string, { providerId: string; profileId: string; label: string; title: string }>();
    for (const profile of profiles.data?.profiles ?? []) {
      const providerId = profile.provider_id || profile.profile_id.replace(/-default$/, "");
      if (!providerId || byProvider.has(providerId)) continue;
      byProvider.set(providerId, {
        providerId,
        profileId: profile.profile_id,
        label: providerId,
        title: providerNames.get(providerId) || profile.label || providerId,
      });
    }
    return Array.from(byProvider.values()).sort((left, right) => left.label.localeCompare(right.label));
  }, [llmCatalog.data?.providers, llmSession.data?.mode, profiles.data?.profiles, routerConfig.data?.providers]);
  const metadataProviderForActiveModel = useMemo(() => {
    const models = [...(llmCatalog.data?.models ?? []), ...(routerConfig.data?.models ?? [])];
    return models.find((model) => model.native_model === activeSettings.model || model.id === activeSettings.model)?.provider ?? null;
  }, [activeSettings.model, llmCatalog.data?.models, routerConfig.data?.models]);
  const composerProviderOptions = useMemo(() => {
    let options = [...providerOptions];
    if (activeSettings.profile_id && !options.some((option) => option.profileId === activeSettings.profile_id)) {
      const providerId = activeProfile?.provider_id || metadataProviderForActiveModel || activeSettings.profile_id.replace(/-default$/, "") || activeSettings.profile_id;
      options = options.filter((option) => option.providerId !== providerId);
      options.push({
        providerId,
        profileId: activeSettings.profile_id,
        label: providerId,
        title: activeProfile?.label || providerId,
      });
    }
    return options.sort((left, right) => left.label.localeCompare(right.label));
  }, [activeProfile?.label, activeProfile?.provider_id, activeSettings.profile_id, metadataProviderForActiveModel, providerOptions]);
  const activeProviderDisplay = useMemo(() => {
    const option = composerProviderOptions.find((item) => item.profileId === activeSettings.profile_id);
    return option?.label || activeProfile?.provider_id || activeProfile?.label || activeSettings.profile_id || "-";
  }, [activeProfile?.label, activeProfile?.provider_id, activeSettings.profile_id, composerProviderOptions]);
  const activeProviderMeta = useMemo(() => {
    const providerId = activeProfile?.provider_id || activeProviderDisplay;
    return (routerConfig.data?.providers ?? []).find((provider) => provider.id === providerId) ?? null;
  }, [activeProfile?.provider_id, activeProviderDisplay, routerConfig.data?.providers]);
  const providerMetaById = useMemo(() => {
    const entries = new Map<string, RouterProvider>();
    for (const provider of routerConfig.data?.providers ?? []) {
      entries.set(provider.id, provider);
    }
    return entries;
  }, [routerConfig.data?.providers]);
  const pickPreferredModelForProvider = (providerId: string) => {
    const managerMode = llmSession.data?.mode ?? "anonymous";
    const sourceModels = managerMode === "managed_user" && (llmCatalog.data?.models ?? []).length > 0
      ? llmCatalog.data?.models ?? []
      : routerConfig.data?.models ?? [];
    const candidates = sourceModels
      .filter((model) => model.enabled && model.provider === providerId)
      .sort((left, right) => {
        const leftDeprecated = Number(Boolean(left.deprecated));
        const rightDeprecated = Number(Boolean(right.deprecated));
        if (leftDeprecated !== rightDeprecated) return leftDeprecated - rightDeprecated;
        const leftDefault = Number(Boolean(left.default_for_provider));
        const rightDefault = Number(Boolean(right.default_for_provider));
        if (leftDefault !== rightDefault) return rightDefault - leftDefault;
        const leftRecommended = Number(Boolean(left.recommended));
        const rightRecommended = Number(Boolean(right.recommended));
        if (leftRecommended !== rightRecommended) return rightRecommended - leftRecommended;
        return String(left.display_name || left.native_model).localeCompare(String(right.display_name || right.native_model));
      });
    return candidates[0]?.native_model ?? null;
  };
  const userDisplayName = llmSession.data?.profile?.display_name || llmSession.data?.username || (llmSession.data?.mode === "anonymous" ? t(locale, "manager_status_anonymous") : t(locale, "manager_fact_users"));
  const userAvatarPath = llmSession.data?.profile?.avatar_path || "";
  const runtimeModelList = useQuery({
    queryKey: ["runtime-models", activeSettings.profile_id],
    queryFn: () => api.models(activeSettings.profile_id),
    enabled: Boolean(activeSettings.profile_id) && mainView === "chat" && selectedThreadProfileReady,
    retry: false,
    staleTime: 60_000,
  });
  const composerModelOptions = useMemo(() => {
    const providerId = activeProfile?.provider_id ?? "";
    const values = new Map<string, string>();
    const managerMode = llmSession.data?.mode ?? "anonymous";
    const catalogModels = llmCatalog.data?.models ?? [];
    const sourceModels = managerMode === "managed_user" && catalogModels.length > 0 ? catalogModels : routerConfig.data?.models ?? [];
    for (const model of sourceModels) {
      if (!model.enabled || model.provider !== providerId) continue;
      const verifiedPrefix = managerMode === "anonymous" && (model as { verified?: boolean }).verified ? "✓ " : "";
      values.set(model.native_model, `${verifiedPrefix}${model.display_name || model.native_model}`);
    }
    for (const model of runtimeModelList.data?.models ?? []) {
      const id = model.id.startsWith(`${providerId}/`) ? model.id.slice(providerId.length + 1) : model.id;
      if (managerMode !== "managed_user" || values.has(id)) {
        values.set(id, values.get(id) ?? model.name ?? id);
      }
    }
    if (activeProfile?.model && (values.size === 0 || values.has(activeProfile.model))) values.set(activeProfile.model, values.get(activeProfile.model) ?? activeProfile.model);
    if (activeSettings.model && (values.size === 0 || values.has(activeSettings.model))) values.set(activeSettings.model, values.get(activeSettings.model) ?? activeSettings.model);
    return Array.from(values, ([value, label]) => ({ value, label }));
  }, [activeProfile?.model, activeProfile?.provider_id, activeSettings.model, llmCatalog.data?.models, llmSession.data?.mode, routerConfig.data?.models, runtimeModelList.data?.models]);
  const activeModelEntry = useMemo(() => {
    const providerId = activeProfile?.provider_id ?? "";
    return (
      (llmCatalog.data?.models ?? []).find((model) => model.provider === providerId && model.native_model === activeSettings.model) ??
      (routerConfig.data?.models ?? []).find((model) => model.provider === providerId && model.native_model === activeSettings.model) ??
      null
    );
  }, [activeProfile?.provider_id, activeSettings.model, llmCatalog.data?.models, routerConfig.data?.models]);
  const activeModelAuthority = useMemo(() => modelAuthorityState(activeModelEntry), [activeModelEntry]);
  const composerEffortOptions = useMemo(
    () => composerReasoningOptions(activeModelEntry, activeProfile, activeSettings.reasoning_effort),
    [activeModelEntry, activeProfile, activeSettings.reasoning_effort],
  );
  const imageAttachmentUnsupported = attachments.some((attachment) => attachment.kind === "image") && !(activeModelEntry?.input_modalities ?? ["text"]).includes("image");
  const mcpEnabled = (mcpConfig.data?.servers ?? []).some((server) => server.enabled);
  const mcpUnverified = mcpEnabled && activeModelEntry && !activeModelEntry.supports_mcp_tools;
  const rawAuthorityWarnings = activeModelAuthority?.notices ?? [];
  const authorityWarnings = rawAuthorityWarnings.map((notice) => localizedAuthorityNotice(locale, notice));
  const capabilityWarnings = [
    ...authorityWarnings,
    ...(imageAttachmentUnsupported ? [t(locale, "capability_warning_image")] : []),
    ...(mcpUnverified ? [t(locale, "capability_warning_mcp")] : []),
    ...((activeModelEntry?.ui_warnings ?? [])
      .filter((warning) => !rawAuthorityWarnings.includes(warning))
      .slice(0, 2)
      .map((warning) => localizedAuthorityNotice(locale, warning))),
  ];
  const runtimeRecoveryActions = runtimeErrorNoticeActions(supervisor.data?.runtime_error ?? null);
  const runtimeRecoveryPendingAction = restartRuntime.isPending
    ? "restart_runtime_lane"
    : compactThread.isPending
      ? "compact_thread"
      : forkThread.isPending
        ? "fork_followup"
        : null;
  const runtimeSecretLoaded = Boolean(runtime.data?.runtime_config.secret_loaded);
  const managerMode = llmSession.data?.mode ?? "anonymous";
  const managedKeyAvailable = managerMode === "managed_user" && Boolean((llmCatalog.data?.providers ?? []).find((provider) => provider.id === activeProfile?.provider_id)?.managed_key_available);
  const needsKeySetup = Boolean(activeProfile?.env_key) && !runtimeSecretLoaded && !managedKeyAvailable;
  const keySetupMessage = sendFailure && sendFailure.includes("runtime_secret_missing") ? sendFailure : null;
  const conversationNotices = [
    ...(needsKeySetup ? [{ key: "key-setup", text: t(locale, "key_setup_missing_inline"), tone: "danger" as const, action: "setup" as const }] : []),
    ...(keySetupMessage ? [{ key: "key-failure", text: keySetupMessage, tone: "danger" as const, action: "setup" as const }] : []),
    ...capabilityWarnings.map((warning, index) => ({ key: `capability-${index}`, text: warning, tone: "warning" as const })),
    ...(supervisor.data?.runtime_error?.summary ? [{
      key: "runtime-error",
      text: runtimeErrorNoticeText(supervisor.data.runtime_error),
      tone: "danger" as const,
    }] : []),
    ...(supervisor.data?.guard.message ? [{ key: "context-guard", text: supervisor.data.guard.message, tone: supervisor.data.guard.level === "pause" ? "danger" as const : "warning" as const }] : []),
    ...(supervisor.data?.watchdog?.message ? [{ key: "turn-watchdog", text: supervisor.data.watchdog.message, tone: supervisor.data.watchdog.level === "pause" ? "danger" as const : "warning" as const }] : []),
  ];

  useEffect(() => {
    document.documentElement.dataset.appearance = appearance;
  }, [appearance]);

  useEffect(() => {
    setExecutionHostDraft((project.ui_preferences.execution_host as ExecutionHost) ?? "windows");
    setWslDistroDraft(project.ui_preferences.wsl_distro ?? "");
  }, [project.project_id, project.ui_preferences.execution_host, project.ui_preferences.wsl_distro]);

  useEffect(() => {
    if (activeProfile) setProfileForm(activeProfile);
  }, [activeProfile]);

  useEffect(() => {
    if (runtime.data?.runtime_config.base_url) {
      setRouterBaseUrl("http://127.0.0.1:8787/v1");
    }
  }, [runtime.data?.runtime_config.base_url]);

  useEffect(() => {
    if (!selectedThreadId) return;
    const payload = {
        thread_id: selectedThreadId,
        profile_id: activeSettings.profile_id,
        model: activeSettings.model,
        effort: activeSettings.reasoning_effort,
        permission_mode: activeSettings.permission_mode,
        collaboration_mode: activeSettings.collaboration_mode,
      };
    const signature = JSON.stringify(payload);
    if (signature === lastSavedThreadSettingsRef.current) return;
    const timer = window.setTimeout(() => {
      lastSavedThreadSettingsRef.current = signature;
      saveThreadSettings.mutate(payload);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [activeSettings.collaboration_mode, activeSettings.model, activeSettings.permission_mode, activeSettings.profile_id, activeSettings.reasoning_effort, saveThreadSettings, selectedThreadId]);

  useEffect(() => {
    if (!project?.project_id) return;
    const timer = window.setTimeout(() => {
      saveProjectPreferences.mutate({
        locale,
        appearance,
        execution_host: executionHostDraft,
        wsl_distro: executionHostDraft === "wsl" ? wslDistroDraft : "",
        left_sidebar_width: leftPane.width,
        right_sidebar_width: rightPane.width,
        right_sidebar_open: rightSidebarOpen,
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [appearance, executionHostDraft, leftPane.width, locale, project?.project_id, rightPane.width, rightSidebarOpen, wslDistroDraft]);

  useEffect(() => {
    if (providerOptions.length === 0) return;
    if (providerOptions.some((option) => option.profileId === activeSettings.profile_id)) return;
    const fallbackProviderId = metadataProviderForActiveModel || activeProfile?.provider_id || providerOptions[0]?.providerId;
    const nextProfile = providerOptions.find((option) => option.providerId === fallbackProviderId) ?? providerOptions[0];
    if (!nextProfile || nextProfile.profileId === activeSettings.profile_id) return;
    updateComposerSettings({ profile_id: nextProfile.profileId });
  }, [activeProfile?.provider_id, activeSettings.profile_id, metadataProviderForActiveModel, providerOptions]);

  useEffect(() => {
    if (!activeProfile?.provider_id || composerModelOptions.length === 0) return;
    const validModels = new Set(composerModelOptions.map((option) => option.value));
    if (!validModels.has(activeSettings.model ?? "")) {
      const nextModel = pickPreferredModelForProvider(activeProfile.provider_id) ?? composerModelOptions[0]?.value;
      if (!nextModel) return;
      const nextModelEntry =
        (llmCatalog.data?.models ?? []).find((model) => model.provider === activeProfile.provider_id && model.native_model === nextModel) ??
        (routerConfig.data?.models ?? []).find((model) => model.provider === activeProfile.provider_id && model.native_model === nextModel) ??
        null;
      const nextEfforts = composerReasoningOptions(nextModelEntry, activeProfile, activeSettings.reasoning_effort);
      updateComposerSettings({
        model: nextModel,
        reasoning_effort: nextEfforts.includes(activeSettings.reasoning_effort ?? "")
          ? activeSettings.reasoning_effort
          : preferredReasoningEffort(nextModelEntry, activeProfile, activeSettings.reasoning_effort),
      });
    }
  }, [activeProfile, activeSettings.model, activeSettings.reasoning_effort, composerModelOptions, llmCatalog.data?.models, routerConfig.data?.models]);

  useEffect(() => {
    if (composerEffortOptions.length === 0) return;
    if (!composerEffortOptions.includes(activeSettings.reasoning_effort ?? "")) {
      updateComposerSettings({ reasoning_effort: preferredReasoningEffort(activeModelEntry, activeProfile, activeSettings.reasoning_effort) });
    }
  }, [activeModelEntry, activeProfile, activeSettings.reasoning_effort, composerEffortOptions]);

  useEffect(() => {
    if (displayGoal?.objective) {
      setGoalDraft(displayGoal.objective);
    }
  }, [displayGoal?.objective]);

  useEffect(() => {
    eventCursorRef.current = eventCursor;
  }, [eventCursor]);

  useEffect(() => {
    if (smokeMode) {
      setEventStreamActive(false);
      return;
    }
    if (eventStreamActive) return;
    let cancelled = false;
    const timeout = window.setTimeout(async function tick() {
      if (!project) return;
      try {
        const payload = await api.runtimeEvents(eventCursor);
        if (cancelled) return;
        if (payload.events.length > 0) {
          handleEvents(payload.events);
        }
        setEventCursor(payload.cursor);
      } catch (error) {
        console.warn("AstraBridge runtime event polling failed", error);
      } finally {
        if (!cancelled) {
          window.setTimeout(tick, 1000);
        }
      }
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [eventCursor, eventStreamActive, project, setEventCursor, smokeMode]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.ctrlKey && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandPaletteOpen(true);
      }
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "n") {
        event.preventDefault();
        closeProject.mutate();
      }
      if (event.ctrlKey && !event.shiftKey && event.key.toLowerCase() === "n") {
        event.preventDefault();
        handleCreateThread();
      }
      if (event.ctrlKey && event.key === ",") {
        event.preventDefault();
        if (!rightSidebarOpen) toggleRightSidebar();
      }
      if (event.key === "Escape") {
        setCommandPaletteOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeProject, rightSidebarOpen, setCommandPaletteOpen, toggleRightSidebar]);

  function handleEvents(events: RuntimeEvent[]) {
    let threadRefresh = false;
    let goalRefresh = false;
    let runtimeRefresh = false;
    for (const event of events) {
      if (event.type !== "notification") continue;
      const method = String(event.method ?? "");
      const params = (event.params ?? {}) as Record<string, unknown>;
      const threadId = String(params.threadId ?? "");
      const turnId = String(params.turnId ?? "");
      if (method === "item/agentMessage/delta") {
        applyAgentDelta(threadId, turnId, String(params.delta ?? ""));
      } else if (method === "item/plan/delta") {
        applyPlanDelta(threadId, turnId, String(params.delta ?? ""));
      } else if (method === "item/reasoning/textDelta" || method === "item/reasoning/summaryTextDelta") {
        appendReasoningDelta(
          threadId,
          turnId,
          String(params.delta ?? ""),
          method,
          method.includes("summary") ? "reasoning summary" : "raw provider reasoning",
        );
      } else if (method === "item/started") {
        const item = (params.item as Record<string, unknown> | undefined) ?? {};
        const activity = itemActivityFromPayload(item, "active");
        if (activity && threadId && turnId) setTurnActivity(threadId, turnId, activity);
      } else if (method === "item/commandExecution/outputDelta") {
        setTurnActivity(threadId, turnId, {
          kind: "command",
          label: "正在执行命令",
          status: "active",
          detail: String(params.delta ?? ""),
          item_id: String(params.itemId ?? ""),
        });
      } else if (method === "command/exec/outputDelta" || method === "process/outputDelta") {
        const scopedThreadId = threadId || selectedThreadId || "";
        const latestSnapshot = useAppStore.getState().eventSnapshot;
        const scopedTurnId = turnId || (scopedThreadId ? latestSnapshot.latestTurnIdByThread[scopedThreadId] ?? "" : "");
        const decoded = decodeBase64Utf8(params.deltaBase64);
        const handle = String(params.processId ?? params.processHandle ?? "");
        if (scopedThreadId && scopedTurnId) {
          setTurnActivity(scopedThreadId, scopedTurnId, {
            kind: "command",
            label: method === "process/outputDelta" ? "正在执行进程" : "正在执行命令",
            status: "active",
            preview: [method === "process/outputDelta" ? "process" : "command", handle, params.stream].filter(Boolean).join(" "),
            detail: decoded,
            item_id: handle || method,
          });
        }
      } else if (method === "process/exited") {
        const scopedThreadId = threadId || selectedThreadId || "";
        const latestSnapshot = useAppStore.getState().eventSnapshot;
        const scopedTurnId = turnId || (scopedThreadId ? latestSnapshot.latestTurnIdByThread[scopedThreadId] ?? "" : "");
        const handle = String(params.processHandle ?? "");
        if (scopedThreadId && scopedTurnId) {
          setTurnActivity(scopedThreadId, scopedTurnId, {
            kind: "command",
            label: "进程已结束",
            status: Number(params.exitCode ?? 0) === 0 ? "completed" : "failed",
            preview: `process ${handle} exited ${params.exitCode ?? ""}`.trim(),
            detail: [params.stdout, params.stderr].map((value) => String(value ?? "").trim()).filter(Boolean).join("\n\n"),
            item_id: handle || method,
          });
        }
      } else if (method === "item/fileChange/outputDelta") {
        setTurnActivity(threadId, turnId, {
          kind: "file_change",
          label: "正在修改文件",
          status: "active",
          detail: String(params.delta ?? ""),
          item_id: String(params.itemId ?? ""),
        });
      } else if (method === "item/fileChange/patchUpdated") {
        setTurnDiff(threadId, turnId, countFileChanges(params.changes));
      } else if (method === "turn/diff/updated") {
        setTurnDiff(threadId, turnId, countDiffLines(String(params.diff ?? "")));
      } else if (method === "item/mcpToolCall/progress") {
        setTurnActivity(threadId, turnId, {
          kind: "mcp",
          label: "正在调用 MCP 工具",
          status: "active",
          preview: String(params.message ?? params.progress ?? params.tool ?? "").trim(),
          detail: JSON.stringify(params, null, 2),
          item_id: String(params.itemId ?? ""),
        });
      } else if (method === "turn/started") {
        const turn = (params.turn as Record<string, unknown> | undefined) ?? {};
        setTurnActivity(threadId, String(turn.id ?? turnId), {
          kind: "thinking",
          label: "正在思考",
          status: "active",
          preview: "Waiting for the first model signal",
        });
      } else if (method === "turn/plan/updated") {
        setPlan(threadId, turnId, (params.explanation as string | null) ?? null, (params.plan as []) ?? []);
        queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      } else if (method === "thread/tokenUsage/updated") {
        setTokenUsage(threadId, turnId, (params.tokenUsage as never) ?? {});
        queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      } else if (method === "thread/status/changed") {
        const status = (params.status as { type?: string; activeFlags?: string[] } | undefined) ?? {};
        setThreadStatus(threadId, { type: String(status.type ?? "unknown"), activeFlags: status.activeFlags ?? [] });
        queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
      } else if (method === "item/completed") {
        const item = (params.item as Record<string, unknown> | undefined) ?? {};
        const activity = itemActivityFromPayload(item, "completed");
        if (activity && threadId && turnId) setTurnActivity(threadId, turnId, activity);
        if (item.type === "contextCompaction") threadRefresh = true;
      } else if (method === "turn/completed") {
        setThreadStatus(threadId, { type: "idle" });
        threadRefresh = true;
        goalRefresh = true;
      } else if (method === "thread/goal/updated" || method === "thread/goal/cleared") {
        goalRefresh = true;
      } else if (method === "thread/compacted") {
        const scopedThreadId = threadId || selectedThreadId || "";
        const latestSnapshot = useAppStore.getState().eventSnapshot;
        const scopedTurnId = turnId || (scopedThreadId ? latestSnapshot.latestTurnIdByThread[scopedThreadId] ?? "" : "");
        if (scopedThreadId && scopedTurnId) {
          setTurnActivity(scopedThreadId, scopedTurnId, {
            kind: "compact",
            label: "上下文已压缩",
            status: "completed",
            preview: "Context compaction completed",
            detail: "Thread context was compacted and the surviving summary is now the active continuation point.",
            item_id: "thread/compacted",
          });
        }
        threadRefresh = true;
      } else if (method === "thread/started" || method === "thread/name/updated" || method === "thread/settings/updated") {
        threadRefresh = true;
      } else if (method === "runtime/disconnected") {
        runtimeRefresh = true;
      }
    }
    if (threadRefresh) {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
    }
    if (goalRefresh) {
      queryClient.invalidateQueries({ queryKey: ["goal"] });
    }
    if (runtimeRefresh) {
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    }
  }

  function refreshSharedStateQueries(event?: RuntimeEvent) {
    const eventType = String(event?.type ?? "");
    const supervisorEvent = String(((event ?? {}) as Record<string, unknown>).event ?? "");
    const method = String(event?.method ?? "");
    queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
    if (eventType === "runtime_supervisor" || supervisorEvent) {
      queryClient.invalidateQueries({ queryKey: ["dogfood-run"] });
      queryClient.invalidateQueries({ queryKey: ["dogfood-assets"] });
      queryClient.invalidateQueries({ queryKey: ["project-saves"] });
      queryClient.invalidateQueries({ queryKey: ["project-review-status"] });
      queryClient.invalidateQueries({ queryKey: ["project-terminal-history"] });
      queryClient.invalidateQueries({ queryKey: ["project-files-tree"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
    }
    if (method.startsWith("thread/") || method.startsWith("turn/")) {
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
    }
  }

  useEffect(() => {
    handleEventsRef.current = handleEvents;
  });

  useEffect(() => {
    if (smokeMode) {
      setEventStreamActive(false);
      return;
    }
    if (!project?.project_id || typeof EventSource === "undefined") {
      setEventStreamActive(false);
      return;
    }
    let cancelled = false;
    let source: EventSource | null = null;
    let reconnectTimer: number | null = null;

    async function connect() {
      try {
        const url = await api.runtimeEventsStreamUrl(eventCursorRef.current);
        if (cancelled) return;
        setEventStreamActive(true);
        source = new EventSource(url);

        const handleHelloEvent = (rawData: string | null) => {
          try {
            if (!rawData) return;
            const payload = JSON.parse(rawData) as { cursor?: number };
            if (typeof payload.cursor === "number") {
              eventCursorRef.current = payload.cursor;
              setEventCursor(payload.cursor);
            }
          } catch {
            return;
          }
        };
        const handleRuntimeEvent = (rawData: string | null) => {
          try {
            if (!rawData) return;
            const payload = JSON.parse(rawData) as { cursor?: number; event?: RuntimeEvent };
            const event = payload.event;
            if (event) {
              handleEventsRef.current([event]);
              refreshSharedStateQueries(event);
            }
            if (typeof payload.cursor === "number") {
              eventCursorRef.current = payload.cursor;
              setEventCursor(payload.cursor);
            }
          } catch {
            return;
          }
        };
        source.addEventListener("astrabridge.hello", (message) => {
          handleHelloEvent((message as MessageEvent).data);
        });
        source.addEventListener("astrabridge.event", (message) => {
          handleRuntimeEvent((message as MessageEvent).data);
        });
        source.onerror = () => {
          source?.close();
          source = null;
          setEventStreamActive(false);
          if (!cancelled) {
            reconnectTimer = window.setTimeout(connect, 2500);
          }
        };
      } catch {
        setEventStreamActive(false);
        if (!cancelled) {
          reconnectTimer = window.setTimeout(connect, 2500);
        }
      }
    }

    connect();
    return () => {
      cancelled = true;
      setEventStreamActive(false);
      source?.close();
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
    };
  }, [project?.project_id, queryClient, setEventCursor, smokeMode]);

  async function promptForText(options: {
    title: string;
    label: string;
    defaultValue?: string;
    placeholder?: string;
    description?: string;
    submitLabel?: string;
    multiline?: boolean;
  }) {
    const defaultValue = options.defaultValue ?? "";
    return await new Promise<string | null>((resolve) => {
      setTextEntryRequest({
        title: options.title,
        label: options.label,
        defaultValue,
        placeholder: options.placeholder,
        description: options.description,
        submitLabel: options.submitLabel,
        multiline: options.multiline,
        resolve,
      });
    });
  }

  async function handleCreateThread() {
    const name = await promptForText({
      title: t(locale, "new_thread"),
      label: t(locale, "title_thread"),
      defaultValue: "",
      placeholder: t(locale, "new_thread"),
      submitLabel: t(locale, "new_thread"),
    });
    if (name === null) return;
    const settings = currentComposerSettings();
    createThread.mutate({
      profile_id: settings.profile_id ?? project.default_profile_id,
      model: settings.model,
      effort: settings.reasoning_effort,
      permission_mode: settings.permission_mode,
      name: name.trim() || undefined,
    });
  }

  async function handleForkThread() {
    if (!selectedThreadId) return;
    const name = await promptForText({
      title: locale === "zh-CN" ? "创建分支线程" : t(locale, "fork_thread"),
      label: t(locale, "title_thread"),
      defaultValue: "",
      placeholder: activeThreadName,
      submitLabel: locale === "zh-CN" ? "创建分支线程" : t(locale, "fork_thread"),
    });
    if (name === null) return;
    forkThread.mutate({
      thread_id: selectedThreadId,
      profile_id: activeSettings.profile_id,
      model: activeSettings.model,
      effort: activeSettings.reasoning_effort,
      permission_mode: activeSettings.permission_mode,
      name: name.trim() || undefined,
    });
  }

  function handleRuntimeRecoveryAction(action: RuntimeErrorAction) {
    const recoveryPatch = resolveRecoveryComposerPatch({
      action,
      current: {
        profile_id: activeSettings.profile_id,
        model: activeSettings.model,
        reasoning_effort: activeSettings.reasoning_effort,
      },
      activeProfile,
      profiles: profiles.data?.profiles ?? [],
      models: [
        ...(llmCatalog.data?.models ?? []),
        ...(routerConfig.data?.models ?? []),
      ],
    });
    switch (action.action) {
      case "restart_runtime_lane":
        restartRuntime.mutate();
        return;
      case "compact_thread":
        if (selectedThreadId) {
          compactThread.mutate({ threadId: selectedThreadId, profileId: activeSettings.profile_id });
        }
        return;
      case "fork_followup":
        void handleForkThread();
        return;
      case "switch_model":
        if (recoveryPatch && Object.keys(recoveryPatch).length > 0) {
          updateComposerSettings(recoveryPatch);
          setMainView("chat");
        }
        return;
      case "downgrade_reasoning":
        if (recoveryPatch && Object.keys(recoveryPatch).length > 0) {
          updateComposerSettings(recoveryPatch);
          setMainView("chat");
        }
        return;
      case "refresh_provider_key":
      case "verify_secret_mapping":
        setMainView("setup");
        return;
      case "handoff_provider": {
        if (recoveryPatch && Object.keys(recoveryPatch).length > 0) {
          updateComposerSettings(recoveryPatch);
          setMainView("chat");
          return;
        }
        setMainView("setup");
        return;
      }
      case "disable_feature":
        setMainView("setup");
        return;
      case "retry_same_lane":
      case "inspect_runtime_notice":
        setInspectorTab("status");
        if (!rightSidebarOpen) toggleRightSidebar();
        queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
        queryClient.invalidateQueries({ queryKey: ["thread"] });
        return;
      default:
        setInspectorTab("status");
        if (!rightSidebarOpen) toggleRightSidebar();
    }
  }

  function openSaveCheckpoint(block?: ThreadRenderBlock | null) {
    setSaveModal({ open: true, block: block ?? null });
    setSaveDescription("");
  }

  function handleCreateCheckpoint() {
    createCheckpoint.mutate({
      thread_id: selectedThreadId,
      description: saveDescription.trim(),
      provider: activeProviderDisplay,
      model: activeSettings.model,
    });
  }

  async function handleRenameThread(threadId: string) {
    const current = threads.data?.threads.find((item) => item.id === threadId);
    const name = await promptForText({
      title: t(locale, "rename_thread"),
      label: t(locale, "title_thread"),
      defaultValue: current?.displayName ?? "",
      placeholder: current?.displayName ?? "",
      submitLabel: t(locale, "rename_thread"),
    });
    if (name && name.trim()) {
      renameThread.mutate({ threadId, name: name.trim() });
    }
  }

  async function handleAddAttachments() {
    if (isTauri()) {
      const paths = await selectFiles(t(locale, "add_files"));
      const drafts = paths.map((path) => {
        const name = path.split(/[\\/]/).pop() ?? path;
        const mimeType = detectMime(path);
        return {
          id: `${Date.now()}-${name}`,
          path,
          name,
          mimeType,
          kind: mimeType.startsWith("image/") ? "image" : "file",
          previewUrl: mimeType.startsWith("image/") ? localAssetUrl(path) : undefined,
        } satisfies AttachmentDraft;
      });
      setAttachments((current) => [...current, ...drafts]);
      return;
    }
      const manual = await promptForText({
        title: t(locale, "add_files"),
        label: "Paths",
        defaultValue: "",
        placeholder: "D:\\path\\to\\file.txt; D:\\path\\to\\image.png",
        description: "Enter absolute file paths separated by semicolons.",
        submitLabel: t(locale, "add_files"),
        multiline: true,
      });
      if (!manual) return;
    const drafts = manual
      .split(";")
      .map((part) => part.trim())
      .filter(Boolean)
      .map((path) => {
        const name = path.split(/[\\/]/).pop() ?? path;
        const mimeType = detectMime(path);
        return {
          id: `${Date.now()}-${name}`,
          path,
          name,
          mimeType,
          kind: mimeType.startsWith("image/") ? "image" : "file",
          previewUrl: mimeType.startsWith("image/") ? localAssetUrl(path) : undefined,
        } satisfies AttachmentDraft;
      });
    setAttachments((current) => [...current, ...drafts]);
  }

  async function handleQuickKeyFileLoad() {
    const files = await selectFiles(t(locale, "runtime_secret_file"));
    if (!files[0] || !activeProfile) return;
    loadSecret.mutate({ profileId: activeProfile.profile_id, payload: { key_file_path: files[0] } });
  }

  function handleQuickKeyLoad(persistToKeychain: boolean) {
    if (!activeProfile || !secretValue.trim()) return;
    loadSecret.mutate({
      profileId: activeProfile.profile_id,
      payload: { session_key: secretValue.trim(), persist_to_keychain: persistToKeychain },
    });
  }

  async function handleSend() {
    setSendFailure(null);
    if (!sendTargetThreadId) {
      const threadStage = t(locale, "send_stage_thread");
      const turnStage = t(locale, "send_stage_turn");
      let currentStage = threadStage;
      const settings = currentComposerSettings();
      try {
        setSendStage(currentStage);
        const created = await createThread.mutateAsync({
          profile_id: settings.profile_id ?? project.default_profile_id,
          model: settings.model,
          effort: settings.reasoning_effort,
          permission_mode: settings.permission_mode,
        });
        currentStage = turnStage;
        setSendStage(currentStage);
        await startTurn.mutateAsync({
          thread_id: created.thread.id,
          profile_id: settings.profile_id,
          text: composerText,
          attachments,
          model: settings.model,
          effort: settings.reasoning_effort,
          permission_mode: settings.permission_mode,
          collaboration_mode: settings.collaboration_mode,
        });
        setSendStage(null);
        return;
      } catch (error) {
        setSendFailure(describeSendError(currentStage, error));
        setSendStage(null);
        return;
      }
    }
      const turnStage = t(locale, "send_stage_turn");
      const settings = currentComposerSettings();
      try {
        setSendStage(turnStage);
        await startTurn.mutateAsync({
          thread_id: sendTargetThreadId,
          profile_id: settings.profile_id,
          text: composerText,
          attachments,
          model: settings.model,
        effort: settings.reasoning_effort,
        permission_mode: settings.permission_mode,
        collaboration_mode: settings.collaboration_mode,
      });
      setSendStage(null);
    } catch (error) {
      setSendFailure(describeSendError(turnStage, error));
      setSendStage(null);
    }
  }

  const activeThread = taskConversation.data?.thread ?? selectedThread.data?.thread;
  const activeExecutionThread = selectedThread.data?.thread;
  const taskInspectorEvidence = useMemo(() => summarizeTaskInspectorEvidence(currentTask, activeThread), [activeThread, currentTask]);
  const workflowFacts = useMemo(
    () => summarizeTaskWorkflowFacts(currentTask, activeExecutionThread ?? null, taskInspectorEvidence),
    [activeExecutionThread, currentTask, taskInspectorEvidence],
  );
  const activeExecutionBackendLabel = workflowFacts.backend === "native_kernel" ? "native kernel" : "app server";
  const activeThreadName = activeThread?.displayName ?? selectedThreadSummary?.displayName ?? "Thread";
  const checkpointDefaultDescription = `${project.name} / ${activeThreadName} · ${new Date().toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })}`;
  const proposedPlanText = latestProposedPlan(activeThread);
  const activePlan = selectedThreadId ? eventSnapshot.planByThread[selectedThreadId] : undefined;
  const liveTurnId = selectedThreadId ? eventSnapshot.latestTurnIdByThread[selectedThreadId] : undefined;
  const liveText = liveTurnId ? eventSnapshot.liveTextByTurn[liveTurnId] : undefined;
  const livePlanText = liveTurnId ? eventSnapshot.livePlanTextByTurn[liveTurnId] : undefined;
  const liveReasoning = liveTurnId ? eventSnapshot.liveReasoningByTurn[liveTurnId] : undefined;
  const liveActivity = liveTurnId ? eventSnapshot.activityByTurn[liveTurnId] : undefined;
  const liveDiff = liveTurnId ? eventSnapshot.diffByTurn[liveTurnId] : undefined;
  const modal = pendingModals.data?.modals?.[0] ?? null;
  const activeThreadStatus = selectedThreadId ? eventSnapshot.threadStatusByThread[selectedThreadId] : undefined;
  const statusFromThread = activeExecutionThread?.status as { type?: string; activeFlags?: string[] } | undefined;
  const activeStatusType = activeThreadStatus?.type ?? statusFromThread?.type ?? "idle";
  const activeFlags = activeThreadStatus?.activeFlags ?? statusFromThread?.activeFlags ?? [];
  const waitingOnApproval = activeFlags.includes("waitingOnApproval") || Boolean(modal?.kind === "approval" && modal.thread_id === selectedThreadId);
  const canInterrupt = Boolean(liveTurnId && activeStatusType === "active");
  const runtimeGuardVisible = Boolean(liveTurnId && activeStatusType === "active") || waitingOnApproval || startTurn.isPending;
  const fallbackSetupCheckpoints = useMemo<ProjectCheckpoint[]>(
    () => {
      const checkpoints: ProjectCheckpoint[] = [];
      for (const item of currentTask?.checkpoint_refs ?? []) {
          const saveId = String(item?.save_id ?? "").trim();
          if (!saveId) continue;
          const providerThread = currentTask?.provider_threads.find((thread) => thread.thread_id === String(item?.thread_id ?? currentTask?.active_provider_thread_id ?? ""));
          const providerId = String(item?.provider_id ?? providerThread?.provider_id ?? "");
          const model = String(item?.model ?? providerThread?.model ?? "");
          checkpoints.push({
            save_id: saveId,
            save_dir: "",
            created_at: String(item?.created_at ?? currentTask?.updated_at ?? project.updated_at ?? ""),
            project_name: project.name,
            thread_id: String(item?.thread_id ?? providerThread?.thread_id ?? currentTask?.active_provider_thread_id ?? "") || null,
            thread_name: String(item?.thread_name ?? providerThread?.name ?? t(locale, "title_thread")),
            description: String(item?.description ?? ""),
            default_description: String(item?.description ?? saveId),
            provider: providerId || null,
            model: model || null,
            workspace: {
              is_git_repo: false,
              base_commit: null,
              dirty: false,
            },
            project_file: project.project_file,
          });
        }
      return checkpoints;
    },
    [currentTask, project.name, project.project_file, project.updated_at],
  );
  const supervisorGuardKey = `${selectedThreadId ?? "none"}:${liveTurnId ?? "none"}:${supervisor.data?.guard.level ?? "ok"}`;
  const supervisorGuardVisible = Boolean(supervisor.data?.guard.level === "pause" && supervisor.data.guard.should_pause && guardDismissedFor !== supervisorGuardKey);

  useEffect(() => {
    if (!selectedThreadId || !liveTurnId || !activeThread) return;
    const persistedTurn = (activeThread.turns ?? []).find((turn) => turn.id === liveTurnId);
    if (!hasPersistedRenderableTurnContent(persistedTurn)) return;
    clearLiveTurn(selectedThreadId, liveTurnId);
  }, [activeThread, clearLiveTurn, liveTurnId, selectedThreadId]);

  const blocks = summarizeTurnBlocks(activeThread, liveText, liveReasoning, liveActivity, liveDiff, liveTurnId);
  const hasRenderedPlanBlock = blocks.some((block) => block.role === "plan" || (("text" in block) && typeof block.text === "string" && extractProposedPlanText(block.text)));
  const inspectorPlan = supervisor.data?.plan ?? (activePlan ? {
    thread_id: selectedThreadId ?? "",
    turn_id: liveTurnId ?? "",
    explanation: activePlan.explanation,
    steps: activePlan.plan,
    last_updated_at: null,
    source: "local-events",
  } : null);
  const messagePlanAnchor = inspectorPlan && !hasRenderedPlanBlock ? inspectorPlan : null;
  const sidebarTasks = !archivedVisible ? (projectTasks.data?.tasks ?? []) : [];
  const inspectorVisible = mainView === "chat" && rightSidebarOpen;
  return (
    <div
      data-testid="app-shell"
      className="shell-grid"
      style={{
        gridTemplateColumns: `${leftPane.width}px 8px minmax(0, 1fr) ${inspectorVisible ? `8px ${rightPane.width}px` : ""}`,
      }}
    >
      <aside className="sidebar app-sidebar">
        <nav className="sidebar-nav" aria-label="Primary">
          <button type="button" className="nav-row nav-row-primary" onClick={() => { setMainView("chat"); handleCreateThread(); }}>
            <span className="nav-icon" aria-hidden="true">+</span>
            <span>{t(locale, "new_thread")}</span>
            <kbd>{t(locale, "new_thread_hint")}</kbd>
          </button>
          <button type="button" className="nav-row" onClick={() => setCommandPaletteOpen(true)}>
            <span className="nav-icon" aria-hidden="true">⌕</span>
            <span>{t(locale, "search")}</span>
            <kbd>{t(locale, "command_k_hint")}</kbd>
          </button>
          <button type="button" data-testid="sidebar-nav-setup" className={`nav-row ${mainView === "setup" ? "nav-row-active" : ""}`} onClick={() => setMainView("setup")}>
            <span className="nav-icon" aria-hidden="true">◎</span>
            <span>{providerSetupLabel(locale)}</span>
          </button>
          <button type="button" className={`nav-row ${archivedVisible ? "nav-row-active" : ""}`} onClick={() => setArchivedVisible((value) => !value)}>
            <span className="nav-icon" aria-hidden="true">◷</span>
            <span>{t(locale, "archived_threads")}</span>
          </button>
        </nav>

        <section className="sidebar-group">
          <div className="sidebar-heading">
            <span>{t(locale, "sidebar_projects")}</span>
          </div>
          <button type="button" className="bookmark-row bookmark-row-active" onClick={() => setMainView("chat")}>
            <span className="row-icon" aria-hidden="true">▣</span>
            <span className="bookmark-copy">
              <strong>{project.name}</strong>
              <small>{project.workspace_root}</small>
            </span>
            <time>{summarizeRelativeTime(project.updated_at)}</time>
          </button>
        </section>

        <section className="sidebar-group sidebar-thread-group grow">
          <div className="sidebar-heading">
            <span>{t(locale, "sidebar_threads")}</span>
            <span className="sidebar-count">{sidebarTasks.length || threads.data?.threads.length || 0}</span>
          </div>
          <div className="official-thread-list">
            {sidebarTasks.map((task) => {
              const summary = summarizeTaskCard(task);
              const active = task.task_id === currentTask?.task_id;
              return (
                <div key={task.task_id} className={`codex-thread-item ${active ? "codex-thread-item-active" : ""} ${summary.tone === "warning" ? "codex-thread-item-warning" : ""}`}>
                  <button type="button" className="thread-select-row" onClick={() => { setMainView("chat"); switchTask.mutate(task.task_id); }}>
                    <span className="row-icon" aria-hidden="true">□</span>
                    <span className="thread-copy">
                      <span className="thread-title-line">
                        <strong>{task.title}</strong>
                        <time>{summarizeRelativeTime(task.updated_at)}</time>
                      </span>
                      <small>{summary.subtitle}</small>
                      <span className="thread-route-line">
                        <span>{summary.routeModel || project.default_model}</span>
                        <span>{summary.routeEffort || project.default_effort}</span>
                      </span>
                      {summary.stats.length > 0 ? (
                        <span className="thread-stat-row">
                          {summary.stats.map((stat) => (
                            <span key={taskStatKey(task, stat)} className={`thread-stat-pill ${stat.includes("异常") ? "thread-stat-pill-warning" : ""}`}>
                              {stat}
                            </span>
                          ))}
                        </span>
                      ) : null}
                    </span>
                  </button>
                </div>
              );
            })}
            {sidebarTasks.length === 0 ? (threads.data?.threads ?? []).map((thread) => (
              <div key={thread.id} className={`codex-thread-item ${thread.id === selectedThreadId ? "codex-thread-item-active" : ""}`}>
                <button type="button" className="thread-select-row" onClick={() => { setMainView("chat"); switchThread.mutate(thread.id); }}>
                  <span className="row-icon" aria-hidden="true">□</span>
                  <span className="thread-copy">
                    <span className="thread-title-line">
                      <strong>{thread.displayName}</strong>
                      <time>{summarizeRelativeTime(thread.updatedAt)}</time>
                    </span>
                    <small>{thread.preview || thread.id}</small>
                    <span className="thread-route-line">
                      <span>{thread.shellSettings.model ?? thread.modelProvider}</span>
                      <span>{thread.shellSettings.reasoning_effort ?? project.default_effort}</span>
                    </span>
                  </span>
                </button>
                <div className="thread-hover-actions" aria-label="Thread actions">
                  <button type="button" className="icon-button" title={t(locale, "rename_thread")} onClick={() => handleRenameThread(thread.id)}>
                    ✎
                  </button>
                  <button type="button" className="icon-button" title={t(locale, "archive_thread")} onClick={() => archiveThread.mutate(thread.id)}>
                    ×
                  </button>
                </div>
              </div>
            )) : null}
            {!projectTasks.isLoading && !threads.isLoading && sidebarTasks.length === 0 && (threads.data?.threads ?? []).length === 0 ? <p className="muted">{t(locale, "no_threads")}</p> : null}
          </div>
        </section>

        <div className="sidebar-footer">
          <button type="button" className="nav-row nav-row-session" onClick={() => setMainView("setup")}>
            <span className="nav-icon" aria-hidden="true">●</span>
            <span>
              {llmSession.data?.mode === "managed_user" ? t(locale, "manager_status_managed").replace("{user}", llmSession.data.username ?? "user") : t(locale, "manager_status_anonymous")}
            </span>
          </button>
          <button type="button" className="nav-row" onClick={() => closeProject.mutate()}>
            <span className="nav-icon" aria-hidden="true">↩</span>
            <span>{t(locale, "close_project")}</span>
          </button>
        </div>
      </aside>

      <div className="resize-handle" {...leftPane.bind} />

      <section className="workspace">
        <header className="workspace-topbar">
          <div className="title-stack">
            <p className="eyebrow">{mainView === "setup" ? providerSetupLabel(locale) : t(locale, "title_thread")}</p>
            <h2>{mainView === "setup" ? t(locale, "provider_model_settings") : activeThread?.displayName ?? t(locale, "no_threads")}</h2>
            {mainView === "chat" ? (
              <>
                <p className="route-subtitle" data-testid="route-summary">
                  {activeProfile?.label ?? fallbackRouteLabel(locale)} · {activeSettings.model} · {activeSettings.reasoning_effort} · {permissionLabel(locale, activeSettings.permission_mode)} · {activeExecutionBackendLabel}
                </p>
                <div className="thread-stat-row" data-testid="task-workflow-facts">
                  <span className="thread-stat-pill" data-testid="task-fact-lanes">{workflowFacts.laneCount} lanes</span>
                  <span className="thread-stat-pill" data-testid="task-fact-handoffs">{workflowFacts.handoffCount} handoffs</span>
                  <span className="thread-stat-pill" data-testid="task-fact-checkpoints">{workflowFacts.checkpointCount} checkpoints</span>
                  <span className="thread-stat-pill" data-testid="task-fact-backend">{activeExecutionBackendLabel}</span>
                </div>
              </>
            ) : (
              <p className="route-subtitle">{t(locale, "provider_settings_subtitle")}</p>
            )}
          </div>
          <div className="topbar-actions">
            {mainView === "chat" ? (
              <>
                <button
                  type="button"
                  className="ghost-button topbar-compact-action"
                  data-testid="topbar-compact"
                  disabled={!selectedThreadId || compactThread.isPending}
                  onClick={() => compactThread.mutate({ threadId: selectedThreadId ?? "", profileId: activeSettings.profile_id })}
                >
                  {compactThread.isPending ? t(locale, "loading") : t(locale, "compact_context")}
                </button>
                <button type="button" className="ghost-button" data-testid="topbar-fork" onClick={handleForkThread} disabled={!selectedThreadId}>
                  {locale === "zh-CN" ? "创建分支线程" : t(locale, "fork_thread")}
                </button>
                <button type="button" className="ghost-button" data-testid="topbar-toggle-inspector" onClick={toggleRightSidebar}>
                  {rightSidebarOpen ? t(locale, "hide_inspector") : t(locale, "show_inspector")}
                </button>
              </>
            ) : (
              <button type="button" data-testid="setup-back-to-chat" className="ghost-button" onClick={() => setMainView("chat")}>
                {t(locale, "back_to_chat")}
              </button>
            )}
          </div>
        </header>

        {mainView === "setup" ? (
          <div className="settings-workspace">
            <RouterControlCenter
              locale={locale}
              queryClient={queryClient}
              fallbackCheckpoints={fallbackSetupCheckpoints}
            />
          </div>
        ) : (
          <>

        <ConversationNoticeBar
          notices={conversationNotices}
          onOpenSetup={() => setMainView("setup")}
        />

        {runtimeGuardVisible ? (
          <section className={`runtime-guard ${waitingOnApproval ? "runtime-guard-waiting" : ""}`}>
            <div className="runtime-guard-copy">
              <span className="setup-badge">{t(locale, "runtime_guard_badge")}</span>
              <strong>{waitingOnApproval ? t(locale, "runtime_guard_waiting") : t(locale, "runtime_guard_active")}</strong>
              <p>
                {t(locale, "runtime_guard_detail")} {activeProfile?.label ?? "-"} · {activeSettings.model ?? "-"}
              </p>
            </div>
            <div className="runtime-guard-actions">
              <span className="pill">{activeStatusType}</span>
              {canInterrupt ? (
                <button
                  type="button"
                  className="danger-button"
                  onClick={() => interruptTurn.mutate({ threadId: selectedThreadId ?? "", turnId: liveTurnId ?? "", profileId: selectedThreadProfileId ?? undefined })}
                >
                  {t(locale, "interrupt")}
                </button>
              ) : null}
            </div>
          </section>
        ) : null}

        <div className="message-stream" data-testid="message-stream">
          {activeThread?.forkedFromId ? (
            <div className="task-fork-row">
              <span>分支来源线程</span>
              <strong>{activeThread.forkedFromId}</strong>
              <span>{activeThread.parentThreadId ? `父线程 ${activeThread.parentThreadId}` : "独立后续分支"}</span>
            </div>
          ) : null}
          {blocks.map((block) => {
            const blockProviderId = block.providerId || activeProfile?.provider_id || activeProviderDisplay;
            const blockProviderMeta = providerMetaById.get(blockProviderId) ?? activeProviderMeta;
            return (
              <ChatMessageRow
                key={block.key}
                locale={locale}
                block={block}
                providerName={blockProviderMeta?.display_name || blockProviderId || activeProviderDisplay}
                modelName={block.model || activeSettings.model || blockProviderMeta?.default_model || "Assistant"}
                providerLogoPath={blockProviderMeta?.logo_asset_path}
                providerAccent={blockProviderMeta?.accent_color}
                userName={userDisplayName}
                userAvatarPath={userAvatarPath}
                reasoningDisplayPolicy={activeModelEntry?.reasoning_display_policy}
                onFork={handleForkThread}
                onSave={() => openSaveCheckpoint(block)}
              />
            );
          })}
          {messagePlanAnchor ? (
            <article className="message-card message-plan message-plan-anchor">
              <div className="plan-anchor-head">
                <span className="plan-anchor-dot" aria-hidden="true" />
                <div>
                  <strong>计划已更新</strong>
                  <small>
                    {messagePlanAnchor.source}
                    {messagePlanAnchor.last_updated_at ? ` · ${summarizeRelativeTime(messagePlanAnchor.last_updated_at)}` : ""}
                  </small>
                </div>
              </div>
              <PlanProgressTimeline plan={messagePlanAnchor} />
            </article>
          ) : null}
          {createThread.error ? <div className="error-text">{describeSendError(t(locale, "new_thread"), createThread.error)}</div> : null}
          {forkThread.error ? <div className="error-text">{describeSendError(t(locale, "fork_thread"), forkThread.error)}</div> : null}
          {!selectedThread.isLoading && !taskConversation.isLoading && blocks.length === 0 ? <div className="empty-state">{t(locale, "no_messages")}</div> : null}
        </div>

        <footer className="composer" data-testid="composer">
          <div className="attachment-bar">
            {attachments.map((attachment, index) => (
              <div className="attachment-card" key={attachment.id}>
                {attachment.kind === "image" && attachment.previewUrl ? <img src={attachment.previewUrl} alt={attachment.name} /> : <div className="attachment-file">{attachment.name.slice(0, 1).toUpperCase()}</div>}
                <div className="attachment-copy">
                  <strong>{attachment.name}</strong>
                  <span>{attachment.kind}</span>
                </div>
                <div className="attachment-card-actions">
                  <button type="button" className="icon-button" disabled={index === 0} onClick={() => setAttachments((current) => current.map((item, itemIndex) => (itemIndex === index - 1 ? current[index] : itemIndex === index ? current[index - 1] : item)))}>
                    ↑
                  </button>
                  <button type="button" className="icon-button" disabled={index === attachments.length - 1} onClick={() => setAttachments((current) => current.map((item, itemIndex) => (itemIndex === index + 1 ? current[index] : itemIndex === index ? current[index + 1] : item)))}>
                    ↓
                  </button>
                  <button type="button" className="icon-button" onClick={() => setAttachments((current) => current.filter((item) => item.id !== attachment.id))}>
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>
          <textarea data-testid="composer-input" value={composerText} onChange={(event) => setComposerText(event.target.value)} rows={6} placeholder={t(locale, "composer_placeholder")} />
          <div className="composer-controls composer-toolbar">
            <div className="composer-toolbar-left">
              <button type="button" className="composer-plus" onClick={handleAddAttachments} aria-label={t(locale, "add_files")}>
                +
              </button>
              <label className={`permission-picker ${permissionClass(activeSettings.permission_mode)}`}>
                <span className="permission-dot" aria-hidden="true" />
                <select
                  data-composer="permission"
                  value={activeSettings.permission_mode}
                  onChange={(event) => updateComposerSettings({ permission_mode: event.target.value as PermissionMode })}
                  aria-label={t(locale, "title_permission")}
                >
                  {(["ask", "auto", "full"] as PermissionMode[]).map((value) => (
                    <option key={value} value={value}>
                      {permissionLabel(locale, value)}
                    </option>
                  ))}
                </select>
              </label>
              <select
                className="mode-picker"
                data-composer="collaboration-mode"
                value={activeSettings.collaboration_mode}
                onChange={(event) => updateComposerSettings({ collaboration_mode: event.target.value as CollaborationMode })}
                aria-label={t(locale, "title_collaboration_mode")}
              >
                <option value="default">{t(locale, "mode_default")}</option>
                <option value="plan">{t(locale, "mode_plan")}</option>
              </select>
            </div>
            <div className="composer-toolbar-right">
              <select
                data-testid="composer-profile"
                data-composer="profile"
                value={activeSettings.profile_id}
                onChange={(event) => {
                  const nextProfile = (profiles.data?.profiles ?? []).find((profile) => profile.profile_id === event.target.value);
                  const nextProviderId = nextProfile?.provider_id ?? "";
                  const nextCatalogModel = pickPreferredModelForProvider(nextProviderId);
                  const nextModel = nextCatalogModel ?? nextProfile?.model ?? activeSettings.model;
                  const nextModelEntry =
                    (llmCatalog.data?.models ?? []).find((model) => model.provider === nextProviderId && model.native_model === nextModel) ??
                    (routerConfig.data?.models ?? []).find((model) => model.provider === nextProviderId && model.native_model === nextModel) ??
                    null;
                  const nextEfforts = composerReasoningOptions(nextModelEntry, nextProfile, activeSettings.reasoning_effort);
                  const nextEffort = nextEfforts.includes(nextProfile?.reasoning_effort ?? "")
                    ? nextProfile?.reasoning_effort
                    : preferredReasoningEffort(nextModelEntry, nextProfile, activeSettings.reasoning_effort);
                  updateComposerSettings({
                    profile_id: event.target.value,
                    model: nextModel,
                    reasoning_effort: nextEffort ?? activeSettings.reasoning_effort,
                  });
                }}
                aria-label={t(locale, "title_provider")}
                title={composerProviderOptions.find((option) => option.profileId === activeSettings.profile_id)?.title}
              >
                {composerProviderOptions.map((provider) => (
                  <option key={provider.profileId} value={provider.profileId}>
                    {provider.label}
                  </option>
                ))}
              </select>
              <select
                data-testid="composer-model"
                data-composer="model"
                value={activeSettings.model ?? ""}
                onChange={(event) => {
                  const nextModelEntry =
                    (llmCatalog.data?.models ?? []).find((model) => model.provider === activeProfile?.provider_id && model.native_model === event.target.value) ??
                    (routerConfig.data?.models ?? []).find((model) => model.provider === activeProfile?.provider_id && model.native_model === event.target.value) ??
                    null;
                  const nextEfforts = composerReasoningOptions(nextModelEntry, activeProfile, activeSettings.reasoning_effort);
                  updateComposerSettings({
                    model: event.target.value,
                    reasoning_effort: nextEfforts.includes(activeSettings.reasoning_effort ?? "")
                      ? activeSettings.reasoning_effort
                      : preferredReasoningEffort(nextModelEntry, activeProfile, activeSettings.reasoning_effort),
                  });
                }}
                aria-label={t(locale, "title_model")}
              >
                {composerModelOptions.map((model) => (
                  <option key={model.value} value={model.value}>
                    {model.label}
                  </option>
                ))}
              </select>
              <select
                data-testid="composer-effort"
                data-composer="effort"
                value={activeSettings.reasoning_effort ?? preferredReasoningEffort(activeModelEntry, activeProfile, null)}
                onChange={(event) => updateComposerSettings({ reasoning_effort: event.target.value })}
                aria-label={t(locale, "title_effort")}
              >
                {composerEffortOptions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
              {canInterrupt ? (
                <button
                  type="button"
                  className="danger-button compact-action"
                  onClick={() => interruptTurn.mutate({ threadId: selectedThreadId ?? "", turnId: liveTurnId ?? "", profileId: selectedThreadProfileId ?? undefined })}
                >
                  {t(locale, "interrupt")}
                </button>
              ) : null}
              <button
              type="button"
              className="primary-button composer-send"
              data-testid="composer-send"
              disabled={
                imageAttachmentUnsupported ||
                Boolean(activeModelAuthority?.sendBlocked) ||
                (!composerText.trim() && attachments.length === 0) ||
                startTurn.isPending ||
                createThread.isPending
              }
              onClick={handleSend}
              aria-label={startTurn.isPending || createThread.isPending ? t(locale, "loading") : t(locale, "send")}
            >
                <span className="composer-send-label">{startTurn.isPending || createThread.isPending ? t(locale, "loading") : t(locale, "send")}</span>
                <span className="composer-send-icon" aria-hidden="true">&uarr;</span>
                {/*
              <span className="composer-send-icon" aria-hidden="true">↑</span>
                */}
              </button>
            </div>
          </div>
          {sendStage ? <p className="send-stage">{sendStage}</p> : null}
          {sendFailure ? <p className="error-text">{sendFailure}</p> : null}
        </footer>
          </>
        )}
      </section>

      {inspectorVisible ? <div className="resize-handle" {...rightPane.bind} /> : null}

      {inspectorVisible ? (
        <aside className="inspector">
          <InspectorTabBar locale={locale} activeTab={inspectorTab} onChange={setInspectorTab} />

          {inspectorTab === "status" ? (
            <>
              <section className="pane-section inspector-section" data-testid="status-panel-goal">
                <div className="section-header">
                  <h2>{t(locale, "goal")}</h2>
                </div>
                <label className="field">
                  <textarea aria-label={t(locale, "goal")} value={goalDraft} onChange={(event) => setGoalDraft(event.target.value)} rows={4} placeholder={t(locale, "goal_placeholder")} />
                </label>
                <div className="inspector-actions">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={!selectedThreadId || !goalDraft.trim()}
                    onClick={() =>
                      setGoalMutation.mutate({
                        thread_id: selectedThreadId ?? "",
                        profile_id: activeSettings.profile_id,
                        objective: goalDraft,
                        token_budget: null,
                      })
                    }
                  >
                    {t(locale, "goal_set")}
                  </button>
                  <button type="button" className="ghost-button" disabled={!selectedThreadId} onClick={() => clearGoalMutation.mutate({ threadId: selectedThreadId ?? "", profileId: activeSettings.profile_id })}>
                    {t(locale, "goal_clear")}
                  </button>
                </div>
                {displayGoal ? (
                  <div className="status-panel">
                    <strong>{displayGoal.status}</strong>
                    <span>{displayGoal.objective}</span>
                  </div>
                ) : (
                  <p className="muted">{t(locale, "empty_goal")}</p>
                )}
              </section>

              <section className="pane-section inspector-section">
                <div className="section-header">
                  <h2>{t(locale, "plan")}</h2>
                </div>
                {inspectorPlan ? (
                  <PlanProgressTimeline plan={inspectorPlan} />
                ) : livePlanText || proposedPlanText ? (
                  <PlanRenderer text={livePlanText || proposedPlanText} compact />
                ) : (
                  <p className="muted">{t(locale, "empty_plan")}</p>
                )}
              </section>

              <section className="pane-section inspector-section inspector-environment-section">
                <div className="section-header">
                  <h2>{t(locale, "inspector_environment")}</h2>
                  <span className={`mini-guard mini-guard-${supervisor.data?.guard.level ?? "ok"}`}>{productStatusLabel(supervisor.data?.guard.level ?? "ok")}</span>
                </div>
                <EnvironmentStrip
                  locale={locale}
                  supervisor={supervisor.data}
                  fallback={{
                    provider: activeProviderDisplay,
                    model: activeSettings.model,
                    effort: activeSettings.reasoning_effort,
                    permission: permissionLabel(locale, activeSettings.permission_mode),
                  }}
                  recoveryActions={runtimeRecoveryActions}
                  recoveryPendingAction={runtimeRecoveryPendingAction}
                  onRecoveryAction={handleRuntimeRecoveryAction}
                />
                {supervisor.data?.guard.message ? <p className={`guard-copy guard-copy-${supervisor.data.guard.level}`}>{supervisor.data.guard.message}</p> : null}
              </section>

              <WorkflowEvidencePanel locale={locale} facts={workflowFacts} />
            </>
          ) : null}
          {inspectorTab === "review" ? (
            <ReviewInspectorPanel
              locale={locale}
              supervisor={supervisor.data}
              review={inspectorReview.data}
              diff={inspectorReviewDiff.data}
              fallback={taskInspectorEvidence}
              selectedPath={inspectorReviewPath}
              onSelectPath={setInspectorReviewPath}
            />
          ) : null}
          {inspectorTab === "terminal" ? <TerminalInspectorPanel locale={locale} supervisor={supervisor.data} history={inspectorTerminal.data} fallback={taskInspectorEvidence} /> : null}
          {inspectorTab === "browser" ? (
              <BrowserInspectorPanel
                locale={locale}
                supervisor={supervisor.data}
                latestSmoke={(inspectorDogfoodRun.data?.run?.browser_smokes ?? []).slice(-1)[0] ?? null}
                statusLabel={productStatusLabel}
                isPreparingWorkflowDemo={prepareReleaseWorkflowDemo.isPending}
                isPreparingNativeKernelDemo={prepareNativeKernelWorkflowDemo.isPending}
                isRunningReleaseSmoke={inspectorBrowserSmoke.isPending}
                isRunningProviderSwitchSmoke={inspectorProviderSwitchSmoke.isPending}
                isRunningNativeKernelSmoke={inspectorNativeKernelSmoke.isPending}
                onPrepareWorkflowDemo={() => prepareReleaseWorkflowDemo.mutate()}
                onPrepareNativeKernelDemo={() => prepareNativeKernelWorkflowDemo.mutate()}
                onRunReleaseSmoke={() => inspectorBrowserSmoke.mutate()}
                onRunProviderSwitchSmoke={() => inspectorProviderSwitchSmoke.mutate()}
                onRunNativeKernelSmoke={() => inspectorNativeKernelSmoke.mutate()}
              />
          ) : null}
          {inspectorTab === "files" ? (
            <FilesInspectorPanel
              locale={locale}
              project={project}
              tree={inspectorFiles.data}
              preview={inspectorFilePreview.data}
              fallback={taskInspectorEvidence}
              query={inspectorFileQuery}
              selectedPath={inspectorFilePath}
              onQueryChange={setInspectorFileQuery}
              onSelectPath={setInspectorFilePath}
            />
          ) : null}

        </aside>
      ) : null}

      {commandPaletteOpen ? (
        <div className="modal-scrim" onClick={() => setCommandPaletteOpen(false)}>
          <div className="command-palette" onClick={(event) => event.stopPropagation()}>
            <div className="card-header">
              <h2>{t(locale, "command_palette")}</h2>
            </div>
            <button type="button" className="command-item" onClick={() => { setCommandPaletteOpen(false); handleCreateThread(); }}>
              {t(locale, "command_new_thread")}
            </button>
            <button type="button" className="command-item" onClick={() => { setCommandPaletteOpen(false); closeProject.mutate(); }}>
              {t(locale, "command_new_project")}
            </button>
            <button type="button" className="command-item" onClick={() => { setCommandPaletteOpen(false); toggleRightSidebar(); }}>
              {t(locale, "command_toggle_inspector")}
            </button>
          </div>
        </div>
      ) : null}

      {supervisorGuardVisible && supervisor.data ? (
        <SupervisorGuardModal
          supervisor={supervisor.data}
          onDismiss={() => setGuardDismissedFor(supervisorGuardKey)}
          onDecision={(action) =>
            supervisorDecision.mutate({
              action,
              threadId: selectedThreadId ?? "",
              turnId: liveTurnId,
              profileId: activeSettings.profile_id,
              model: activeSettings.model,
              effort: activeSettings.reasoning_effort,
              permissionMode: activeSettings.permission_mode,
            })
          }
        />
      ) : null}
      {modal ? <ModalHost modal={modal} locale={locale} queryClient={queryClient} /> : null}
      {saveModal.open ? (
        <SaveCheckpointModal
          locale={locale}
          description={saveDescription}
          defaultDescription={checkpointDefaultDescription}
          projectName={project.name}
          threadName={activeThreadName}
          isPending={createCheckpoint.isPending}
          error={createCheckpoint.error}
          onDescriptionChange={setSaveDescription}
          onCancel={() => {
            setSaveModal({ open: false });
            setSaveDescription("");
          }}
          onSave={handleCreateCheckpoint}
        />
      ) : null}
      {textEntryRequest ? (
        <TextEntryModal
          request={textEntryRequest}
          onCancel={() => {
            const request = textEntryRequest;
            setTextEntryRequest(null);
            request.resolve(null);
          }}
          onSubmit={(value) => {
            const request = textEntryRequest;
            setTextEntryRequest(null);
            request.resolve(value);
          }}
        />
      ) : null}
    </div>
  );
}

function ModalHost({ modal, locale, queryClient }: { modal: RuntimeModal; locale: "en" | "zh-CN"; queryClient: ReturnType<typeof useQueryClient> }) {
  const [decision, setDecision] = useState("approve");
  const [scope, setScope] = useState("turn");
  const [answers, setAnswers] = useState<Record<string, { option?: string; freeText?: string }>>({});
  const [mcpValues, setMcpValues] = useState<Record<string, unknown>>({});
  const resolveModal = useMutation({
    mutationFn: ({ modalId, payload }: { modalId: string; payload: Record<string, unknown> }) => api.resolveModal(modalId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-modals"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
    },
  });

  const params = modal.params as Record<string, unknown>;
  const questions = (params.questions as Array<Record<string, unknown>> | undefined) ?? [];
  const requestedSchema = (params.requestedSchema as Record<string, unknown> | undefined) ?? {};
  const mcpProperties = (requestedSchema.properties as Record<string, Record<string, unknown>> | undefined) ?? {};
  const approval = modal.kind === "approval" ? approvalSummary(modal) : null;

  function submitUserInput() {
    const payload = {
      answers: Object.fromEntries(
        questions.map((question) => {
          const id = String(question.id ?? "");
          const entry = answers[id] ?? {};
          const submitted = [entry.option, entry.freeText].filter(Boolean);
          return [id, { answers: submitted }];
        })
      ),
    };
    resolveModal.mutate({ modalId: modal.modal_id, payload });
  }

  function submitApproval(choice: string) {
    const payload: Record<string, unknown> = { decision: choice, scope };
    if (modal.method === "item/permissions/requestApproval" && choice === "approve") {
      payload.permissions = params.permissions ?? {};
    }
    resolveModal.mutate({ modalId: modal.modal_id, payload });
  }

  function mcpValueFor(key: string, schema: Record<string, unknown>) {
    if (key in mcpValues) return mcpValues[key];
    if ("default" in schema) return schema.default;
    return schema.type === "boolean" ? false : "";
  }

  function submitMcpElicitation(action: "accept" | "decline" | "cancel") {
    const content = Object.fromEntries(
      Object.entries(mcpProperties).map(([key, schema]) => {
        const value = mcpValueFor(key, schema);
        if (schema.type === "number" || schema.type === "integer") return [key, Number(value)];
        if (schema.type === "boolean") return [key, Boolean(value)];
        return [key, value];
      }),
    );
    resolveModal.mutate({ modalId: modal.modal_id, payload: { action, content: action === "accept" ? content : null, _meta: null } });
  }

  return (
    <div className="modal-scrim">
      <div className="modal-card">
        <div className="card-header">
          <h2>{modal.kind === "user_input" ? t(locale, "user_input_title") : modal.kind === "mcp_elicitation" ? t(locale, "modal_mcp_input") : t(locale, "approval_title")}</h2>
          <span className="status-tag">{modal.method}</span>
        </div>
        {modal.kind === "mcp_elicitation" ? (
          <div className="stack">
            <p>{String(params.message ?? t(locale, "modal_mcp_default_message"))}</p>
            <span className="status-tag">{String(params.serverName ?? "mcp")}</span>
            {params.mode === "url" ? (
              <p className="muted">
                {t(locale, "modal_mcp_open_url")} <a href={String(params.url ?? "#")} target="_blank" rel="noreferrer">{String(params.url ?? "")}</a>
              </p>
            ) : null}
            {Object.entries(mcpProperties).map(([key, schema]) => {
              const value = mcpValueFor(key, schema);
              const enumValues = (schema.enum as string[] | undefined) ?? [];
              return (
                <label className="field" key={key}>
                  <span>{String(schema.title ?? key)}</span>
                  {enumValues.length > 0 ? (
                    <select value={String(value ?? "")} onChange={(event) => setMcpValues((current) => ({ ...current, [key]: event.target.value }))}>
                      {enumValues.map((option) => <option key={option} value={option}>{option}</option>)}
                    </select>
                  ) : schema.type === "boolean" ? (
                    <input type="checkbox" checked={Boolean(value)} onChange={(event) => setMcpValues((current) => ({ ...current, [key]: event.target.checked }))} />
                  ) : (
                    <input type={schema.type === "number" || schema.type === "integer" ? "number" : "text"} value={String(value ?? "")} onChange={(event) => setMcpValues((current) => ({ ...current, [key]: event.target.value }))} />
                  )}
                  {schema.description ? <small>{String(schema.description)}</small> : null}
                </label>
              );
            })}
            {Object.keys(mcpProperties).length === 0 && params.mode !== "url" ? <pre className="modal-json">{JSON.stringify(params, null, 2)}</pre> : null}
            <div className="field-row">
              <button type="button" className="primary-button" onClick={() => submitMcpElicitation("accept")}>{t(locale, "approval_approve")}</button>
              <button type="button" className="ghost-button" onClick={() => submitMcpElicitation("decline")}>{t(locale, "approval_decline")}</button>
              <button type="button" className="ghost-button" onClick={() => submitMcpElicitation("cancel")}>{t(locale, "approval_cancel")}</button>
            </div>
          </div>
        ) : modal.kind === "user_input" ? (
          <div className="stack">
            {questions.map((question) => {
              const id = String(question.id ?? "");
              const options = (question.options as Array<{ label: string; description: string }> | null) ?? [];
              const entry = answers[id] ?? {};
              return (
                <div className="question-card" key={id}>
                  <strong>{String(question.header ?? "")}</strong>
                  <p>{String(question.question ?? "")}</p>
                  {options.map((option, index) => (
                    <label className="choice-row" key={`${id}-${option.label}`}>
                      <input
                        type="radio"
                        checked={entry.option === option.label}
                        onChange={() => setAnswers((current) => ({ ...current, [id]: { ...current[id], option: option.label } }))}
                      />
                      <div>
                        <span>
                          {option.label} {index === 0 ? <em>{t(locale, "request_recommended")}</em> : null}
                        </span>
                        <small>{option.description}</small>
                      </div>
                    </label>
                  ))}
                  <textarea
                    rows={3}
                    value={entry.freeText ?? ""}
                    onChange={(event) => setAnswers((current) => ({ ...current, [id]: { ...current[id], freeText: event.target.value } }))}
                    placeholder={t(locale, "modal_freeform_answer")}
                  />
                </div>
              );
            })}
            <button type="button" className="primary-button" onClick={submitUserInput}>
              {t(locale, "user_input_submit")}
            </button>
          </div>
        ) : (
          <div className="stack">
            {approval ? (
              <div className={`approval-summary approval-risk-${approval.risk}`}>
                <div className="approval-summary-head">
                  <span className="approval-action">{approval.action}</span>
                  <span className="approval-risk">{approval.risk} {t(locale, "approval_risk_suffix")}</span>
                </div>
                <p>{approval.reason}</p>
                {approval.encodingRisk ? (
                  <div className="approval-warning">
                    <strong>{t(locale, "approval_encoding_risk")}</strong>
                    <span>{t(locale, "approval_encoding_risk_detail")}</span>
                  </div>
                ) : null}
                {approval.astrabridgeLogRisk ? (
                  <div className="approval-warning">
                    <strong>{t(locale, "approval_context_risk")}</strong>
                    <span>{t(locale, "approval_context_risk_detail")}</span>
                  </div>
                ) : null}
                {approval.cwd ? (
                  <div className="approval-fact">
                    <span>{t(locale, "approval_working_directory")}</span>
                    <code>{approval.cwd}</code>
                  </div>
                ) : null}
                <div className="approval-fact">
                  <span>{t(locale, "approval_action_preview")}</span>
                  <code>{clippedCommand(approval.command)}</code>
                </div>
                {approval.paths.length > 0 ? (
                  <div className="approval-paths">
                    <span>{t(locale, "approval_target_paths")}</span>
                    {approval.paths.map((path) => (
                      <code key={path}>{path}</code>
                    ))}
                  </div>
                ) : null}
                <details className="approval-raw">
                  <summary>{t(locale, "approval_show_raw")}</summary>
                  <pre className="modal-json">{JSON.stringify(params, null, 2)}</pre>
                </details>
              </div>
            ) : (
              <pre className="modal-json">{JSON.stringify(params, null, 2)}</pre>
            )}
            {modal.method === "item/permissions/requestApproval" ? (
              <div className="segmented">
                <button type="button" className={scope === "turn" ? "segmented-active" : ""} onClick={() => setScope("turn")}>
                  {t(locale, "approval_scope_turn")}
                </button>
                <button type="button" className={scope === "session" ? "segmented-active" : ""} onClick={() => setScope("session")}>
                  {t(locale, "approval_scope_session")}
                </button>
              </div>
            ) : null}
            <div className="field-row">
              <button type="button" className="primary-button" onClick={() => submitApproval("approve")}>
                {t(locale, "approval_approve")}
              </button>
              <button type="button" className="ghost-button" onClick={() => submitApproval("approve_session")}>
                {t(locale, "approval_approve_session")}
              </button>
              <button type="button" className="ghost-button" onClick={() => submitApproval("decline")}>
                {t(locale, "approval_decline")}
              </button>
              <button type="button" className="ghost-button" onClick={() => submitApproval("cancel")}>
                {t(locale, "approval_cancel")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const setProject = useAppStore((store) => store.setProject);
  const project = useAppStore((store) => store.project);
  const current = useQuery({ queryKey: ["project"], queryFn: api.currentProject, retry: false });

  useEffect(() => {
    if (current.data?.project) {
      setProject(current.data.project);
    }
  }, [current.data?.project, setProject]);

  return project ? <AppShell /> : <Launcher />;
}


