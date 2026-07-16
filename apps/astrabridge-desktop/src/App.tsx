import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import {
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  ClipboardCopy,
  AlertTriangle,
  File as FileIcon,
  Image as ImageIcon,
  ListChecks,
  MessageSquareText,
  PauseCircle,
  Pencil,
  PlayCircle,
  Trash2,
  Workflow,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Save,
  Settings,
  ShieldCheck,
  Unlock,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ClipboardEvent, type DragEvent, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { ApiRequestError, api, projectFileMediaHref, projectFileReadHref } from "./api";
import { t, permissionLabel } from "./features/i18n/catalog";
import { AutomationsPanel, type AutomationMcpPresetOption, type AutomationPluginSkillPresetOption } from "./features/automations/AutomationsPanel";
import {
  updateAutomationSchedulerAfterRun,
  upsertAutomationInboxResponse,
  upsertAutomationListResponse,
  upsertAutomationRunsResponse,
} from "./features/automations/automationQueryCache";
import { ComposerStarTrack } from "./features/brand/ComposerStarTrack";
import { StarbridgeCornerConstellation } from "./features/brand/StarbridgeCornerConstellation";
import { StarbridgeCursorOverlay } from "./features/brand/StarbridgeCursorOverlay";
import { StarbridgeWaitingConstellation, type StarbridgeWaitingPhase } from "./features/brand/StarbridgeWaitingConstellation";
import { StarbridgeWaitingPreview } from "./features/brand/StarbridgeWaitingPreview";
import { buildRuntimeWaitingReplayState, resolveRuntimeWaitingState } from "./features/brand/runtimeWaitingState";
import {
  StarbridgeArchiveIcon,
  StarbridgeAttachIcon,
  StarbridgeCompactContextIcon,
  StarbridgeFileIcon,
  StarbridgeFolderIcon,
  StarbridgeForkTaskIcon,
  StarbridgeImageIcon,
  StarbridgePermissionAskIcon,
  StarbridgePermissionAutoIcon,
  StarbridgePermissionFullIcon,
  StarbridgeRenameIcon,
  StarbridgeSearchIcon,
  StarbridgeSendIcon,
  StarbridgeSessionIcon,
  StarbridgeSettingsIcon,
  StarbridgeTaskCreateIcon,
  StarbridgeVoiceIcon,
  StarbridgeWorkflowDefaultIcon,
  StarbridgeWorkflowGoalIcon,
  StarbridgeWorkflowPlanIcon,
} from "./features/brand/StarbridgeIcons";
import { CapabilityRoutesPanel, type CapabilityProviderCredentialStatus } from "./features/capabilities/CapabilityRoutesPanel";
import { DogfoodLedgerSummary } from "./features/dogfood/DogfoodLedgerSummary";
import { PluginSkillInventoryPanel } from "./features/extensions/PluginSkillInventoryPanel";
import {
  ABILITY_ENTRY_DEFINITIONS,
  API_MANAGER_TABS,
  SETUP_ROUTE_TABS,
  type AbilityEntryDefinition,
  type SetupRouteTab,
} from "./features/navigation/abilityEntries";
import { ProjectTaskTree, sidebarProjectKey } from "./features/navigation/ProjectTaskTree";
import { RecentProjectButton } from "./features/navigation/RecentProjectButton";
import { isSidebarTaskAlreadySelected } from "./features/navigation/sidebarTaskSelection";
import { launcherSidecarGateMessage } from "./features/navigation/launcherSidecarGate";
import { visibleTaskTitle, visibleThreadTitle } from "./features/navigation/displayTitle";
import { isCompactShellViewport, resolveSidebarVisible } from "./features/navigation/shellLayout";
import { SetupLandingPanel, type SetupLandingAction, type SetupLandingMetric } from "./features/navigation/SetupLandingPanel";
import { ViewWorkspacePanel } from "./features/navigation/ViewWorkspacePanel";
import { WebToolsPanel } from "./features/web/WebToolsPanel";
import { summarizeCodingEventInspector } from "./features/runtime/codingEventInspector";
import {
  BrowserInspectorPanel,
  FilesInspectorPanel,
  InspectorTabBar,
  type InspectorTab,
  ReviewInspectorPanel,
  WorkflowEvidencePanel,
} from "./features/runtime/InspectorPanels";
import { isolationAuditSummary, projectCaptureRoot, suggestedDogfoodScreenshotPath } from "./features/runtime/isolationAudit";
import { QueuedInstructionQueue } from "./features/runtime/QueuedInstructionQueue";
import { RuntimeKernelStatusPanel } from "./features/runtime/RuntimeKernelStatusPanel";
import { McpToolDiagnosticsPanel } from "./features/runtime/McpToolDiagnosticsPanel";
import { RuntimeActivityRow } from "./features/runtime/RuntimeActivityRow";
import { mergeComposerCatalogModels } from "./features/runtime/composerModelCatalog";
import { imageAttachmentRouteState } from "./features/runtime/attachmentRoute";
import { TaskGraphWorkspace } from "./features/runtime/TaskGraphWorkspace";
import {
  hasTaskGraphLiveDispatchTimedOut,
  resolveTaskGraphRunPrecondition,
  shouldPromoteDryRunToLiveRun,
  type TaskGraphRequestedRunIntent,
} from "./features/runtime/taskGraphRunDispatch";
import { summarizeManagedKeyTest, summarizeManagedKeyTestError, type ManagedKeyTestFeedback } from "./features/runtime/managedKeyTestFeedback";
import {
  buildFallbackTaskGraphFromTemplate,
  createFallbackTaskGraphNode,
  isFallbackTaskGraph,
  readFallbackTaskGraph,
  removeFallbackTaskGraphEdge,
  taskGraphNeedsServerPersistence,
  upsertFallbackTaskGraphEdge,
  writeFallbackTaskGraph,
  updateFallbackTaskGraphNodeConfiguration,
  updateFallbackTaskGraphNodePosition,
} from "./features/runtime/taskGraphFallbackState";
import {
  createOptimisticTaskGraphLiveRunRef,
  selectCurrentTaskGraphRunRef,
  selectLatestTaskGraphRunRef,
} from "./features/runtime/taskGraphRunRefs";
import { hasRenderableTaskGraphStructure, resolvePreferredTaskGraphId } from "./features/runtime/taskGraphSelection";
import { resolveTaskGraphRouteUnavailable } from "./features/runtime/taskGraphSelection";
import { FALLBACK_TASK_GRAPH_TEMPLATES } from "./features/runtime/taskGraphTemplateFallbacks";
import {
  fallbackThreadIdForEmptyTaskContext,
  resolveCurrentProjectTask,
  resolveSelectedThreadProfileId,
  resolveTaskIdForNewThread,
  resolveTaskSendTargetThreadId,
  resolveVisibleCurrentProjectTask,
  shouldUseSelectedRuntimeThread,
} from "./features/runtime/taskThreadRestore";
import { AgenticUpdateReviewPanel } from "./features/updates/AgenticUpdateReviewPanel";
import { evaluateLaunchIsolation } from "./features/runtime/launchIsolation";
import { normalizeRuntimeActivity } from "./features/runtime/runtimeActivity";
import { summarizeTaskInspectorEvidence } from "./features/runtime/taskInspectorEvidence";
import { modelAuthorityState } from "./features/runtime/modelAuthorityNotice";
import { contextGuardLevel, extractProposedPlanText, hasUnsafeWindowsWrite, parsePlanCard, readsExplosiveAstraBridgeLog } from "./features/runtime/planRendering";
import { resolveRecoveryComposerPatch } from "./features/runtime/runtimeRecoveryPlan";
import { formatResponseDiagnostics, summarizeResponseDiagnosticsInline } from "./features/runtime/responseDiagnostics";
import { composerReasoningOptions, preferredProviderReasoningEffort, preferredReasoningEffort, providerModelDraftDefaults, providerReasoningOptions } from "./features/runtime/reasoningOptions";
import { shouldShowGoalDock as resolveGoalDockVisibility } from "./features/runtime/goalDockVisibility";
import { composerFailureNoticeText, latestCompletedTurnSuppressesRuntimeError, runtimeErrorNoticeActions, runtimeErrorNoticeInline, runtimeErrorNoticeText, type RuntimeErrorAction } from "./features/runtime/runtimeErrorNotice";
import { invalidateRestoreStateQueries } from "./features/runtime/restoreInvalidation";
import { summarizeTaskWorkflowFacts, type TaskWorkflowFacts } from "./features/runtime/taskWorkflowFacts";
import {
  describeConversationRenderState,
  hasPersistedRenderableTurnContent,
  hasRenderableThreadContent,
  itemActivityFromPayload,
  summarizeTurnBlocks,
  type ConversationRenderState,
} from "./features/runtime/threadRendering";
import { useAppStore } from "./store";
import { chooseProjectSavePath, selectAttachmentDirectory, selectAttachmentFiles, selectDirectory, selectExistingProject, selectFiles } from "./tauriDialog";
import type {
  AutomationInboxItem,
  AutomationInboxResponse,
  AutomationListResponse,
  AutomationRun,
  AutomationRunsResponse,
  AutomationSchedulerStatus,
  AutomationSpec,
  AppearancePreset,
  AssetRegistryEntry,
  AttachmentDiagnostics,
  AttachmentStageFile,
  AttachmentDraft,
  CapabilityRouteEntry,
  CapabilitySmokeResult,
  CollaborationMode,
  CursorEnhancementPreference,
  DogfoodRun,
  ExecutionHost,
  GoalResponse,
  LlmManagerKey,
  LocaleCode,
  McpServerConfig,
  PermissionMode,
  TurnExecutionPolicy,
  Profile,
  ProjectCheckpoint,
  ProjectFile,
  ProjectFilePreview,
  ProjectFilesTree,
  ProjectReviewDiff,
  ProjectReviewStatus,
  ProjectTasksResponse,
  TaskGraphDefinition,
  TaskGraphDryRunResult,
  TaskGraphRunRef,
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
  SidebarProjectNode,
  SidebarTaskNode,
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
const SETUP_TABS = SETUP_ROUTE_TABS;

type SetupTab = SetupRouteTab;
type ExtensionInventoryInitialKind = "all" | "plugins" | "skills";
type GoalDockTab = "goal" | "plan";
type ComposerWorkflowMode = "default" | "goal" | "plan";
type ComposerExecutionPolicy = TurnExecutionPolicy;
type VoiceRecorderState = "idle" | "recording" | "transcribing";
type ThreadCreateRecovery = { operationId: string; profileId: string };
const THREAD_CREATE_RECOVERY_MAX_ATTEMPTS = 12;
const THREAD_CREATE_RECOVERY_DELAY_MS = 750;
type QueuedInstruction = {
  id: string;
  text: string;
  attachments: AttachmentDraft[];
  targetThreadId: string | null;
};
type DisplayGoal = {
  objective: string;
  status: string;
  source: "thread" | "task" | "dogfood";
  tokenBudget?: number | null;
  tokensUsed?: number;
  timeUsedSeconds?: number;
  updatedAt?: number;
};
type AppMenuItem = {
  id: string;
  label: string;
  action: () => void;
  active?: boolean;
  disabled?: boolean;
  hint?: string;
  meta?: string;
  testId?: string;
};
type AppMenuSection = {
  id: string;
  label: string;
  active?: boolean;
  defaultAction?: () => void;
  items: AppMenuItem[];
};
type StatusAttentionItem = {
  id: string;
  severity: "info" | "warning" | "danger";
  label: string;
  detail: string;
};
type StatusEvidenceItem = {
  id: string;
  label: string;
  value: string;
  detail?: string;
};
type AutomationOperationNotice = {
  tone: "info" | "success";
  title: string;
  detail: string;
};

const SIDEBAR_EXPANDED_PROJECTS_KEY = "astrabridge.sidebar.expandedProjects";
const TITLE_SUGGESTION_PREFIX = "astrabridge.titleSuggestion.";
const TASK_GRAPH_SELECTION_PREFIX = "astrabridge.taskGraphSelection.";
const GENERIC_PROJECT_TITLES = new Set(["", "untitled", "untitled project", "new project", "default project", "project", "astrabridge-project", "codex-workspace"]);
const GENERIC_TASK_TITLES = new Set(["", "untitled", "untitled task", "new task", "default task", "task"]);
const COMPOSER_INPUT_HEIGHT_KEY = "astrabridge.composer.inputHeight";
const COMPOSER_INPUT_HEIGHT_MIN = 96;
const COMPOSER_INPUT_HEIGHT_MAX = 320;

function clampComposerInputHeight(value: number) {
  return Math.min(COMPOSER_INPUT_HEIGHT_MAX, Math.max(COMPOSER_INPUT_HEIGHT_MIN, Math.round(value)));
}

function loadStringSet(key: string) {
  if (typeof window === "undefined") return new Set<string>();
  try {
    const value = JSON.parse(window.localStorage.getItem(key) || "[]");
    return new Set(Array.isArray(value) ? value.map(String) : []);
  } catch {
    return new Set<string>();
  }
}

function saveStringSet(key: string, value: Set<string>) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify([...value]));
}

function loadStoredNumber(key: string, fallback: number) {
  if (typeof window === "undefined") return fallback;
  const raw = Number.parseFloat(window.localStorage.getItem(key) || "");
  return Number.isFinite(raw) ? raw : fallback;
}

function titleSuggestionAlreadyAttempted(key: string) {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(`${TITLE_SUGGESTION_PREFIX}${key}`) === "1";
}

function markTitleSuggestionAttempted(key: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(`${TITLE_SUGGESTION_PREFIX}${key}`, "1");
}

function newThreadCreateOperationId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `thread-create-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function loadStoredString(key: string) {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(key);
  return value ? String(value) : null;
}

function saveStoredString(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  if (!value) {
    window.localStorage.removeItem(key);
    return;
  }
  window.localStorage.setItem(key, value);
}

function taskGraphSelectionStorageKey(projectId: string, taskId: string) {
  return `${TASK_GRAPH_SELECTION_PREFIX}${projectId}:${taskId}`;
}

function looksGenericProjectTitle(project: Pick<SidebarProjectNode, "name" | "project_id">) {
  const title = String(project.name || "").trim();
  return GENERIC_PROJECT_TITLES.has(title.toLowerCase()) || Boolean(title && title === String(project.project_id || "").trim());
}

function looksGenericTaskTitle(task: Pick<SidebarTaskNode, "title">, project: Pick<SidebarProjectNode, "name">) {
  const title = visibleTaskTitle(task.title);
  return GENERIC_TASK_TITLES.has(title.toLowerCase()) || Boolean(title && title === String(project.name || "").trim());
}

function localAssetUrl(path: string) {
  return isTauri() ? convertFileSrc(path) : projectFileMediaHref(path);
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

function brandWaitingPreviewMode() {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("brand_waiting_preview") === "1";
}

function brandWaitingReplayPhase() {
  if (typeof window === "undefined") return null;
  const phase = new URLSearchParams(window.location.search).get("brand_waiting_replay");
  if (
    phase === "thinking" ||
    phase === "tools" ||
    phase === "web" ||
    phase === "files" ||
    phase === "automation" ||
    phase === "approval"
  ) {
    return phase as StarbridgeWaitingPhase;
  }
  return null;
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

function inheritedGoalFrom(value: unknown, source: "task" | "dogfood"): DisplayGoal | null {
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

function taskVisibleThreadId(task: ProjectTask | null | undefined) {
  if (!task) return null;
  const active = String(task.active_provider_thread_id ?? "").trim();
  if (active) return active;
  const providerThreads = Array.isArray(task.provider_threads) ? task.provider_threads : [];
  const liveProvider = providerThreads.find((thread) => !thread.missing_at)?.thread_id;
  return liveProvider ?? providerThreads[0]?.thread_id ?? null;
}

function mergeProjectTaskResponse(current: ProjectTasksResponse | undefined, task: ProjectTask): ProjectTasksResponse {
  const tasks = current?.tasks ?? [];
  const nextTasks = [task, ...tasks.filter((item) => item.task_id !== task.task_id)];
  return {
    schema_version: current?.schema_version ?? task.schema_version ?? "astrabridge-project-tasks-v1",
    current_task: task,
    tasks: nextTasks,
    updated_at: task.updated_at ?? current?.updated_at,
  };
}

function optimisticSidebarTask(project: SidebarProjectNode, task: SidebarTaskNode): ProjectTask {
  return {
    schema_version: "astrabridge-task-state-v1",
    task_id: task.task_id,
    project_id: project.project_id,
    title: visibleTaskTitle(task.title),
    status: task.status || "active",
    handoff_policy: "multi_provider_handoff",
    active_provider_thread_id: String(task.active_provider_thread_id ?? "").trim() || null,
    provider_threads: [],
    fork_threads: [],
    handoff_events: [],
    goal: null,
    plan: null,
    checkpoint_refs: [],
    verification_refs: [],
    diagnostic_refs: [],
    asset_context_refs: [],
    context_pack_refs: [],
    graph_definitions: [],
    graph_run_refs: [],
    graph_snapshot_refs: [],
    graph_activity_summary: {
      graph_count: 0,
      run_count: 0,
      latest_graph_id: null,
      latest_run_id: null,
      latest_run_status: null,
      latest_updated_at: null,
      graph_status_counts: {},
      run_status_counts: {},
    },
    created_at: String(task.updated_at || ""),
    updated_at: String(task.updated_at || ""),
  };
}

function goalStatusLabel(locale: "en" | "zh-CN", status: string, source?: DisplayGoal["source"]) {
  if (source && source !== "thread") {
    if (source === "task") return locale === "zh-CN" ? "继承自任务" : "Inherited from task";
    return locale === "zh-CN" ? "继承自狗粮运行" : "Inherited from dogfood";
  }
  const labels: Record<string, { en: string; zh: string }> = {
    active: { en: "Active goal", zh: "运行中的目标" },
    paused: { en: "Paused goal", zh: "已暂停的目标" },
    blocked: { en: "Blocked goal", zh: "受阻目标" },
    usageLimited: { en: "Usage limited", zh: "用量受限" },
    budgetLimited: { en: "Budget limited", zh: "预算受限" },
    complete: { en: "Complete", zh: "已完成" },
  };
  const label = labels[status];
  return locale === "zh-CN" ? label?.zh ?? status : label?.en ?? status;
}

function goalCanAutoContinue(status: string) {
  return status === "active";
}

function taskGraphNodeOverrideKey(_graphId: string, nodeId: string) {
  return `${_graphId}::${nodeId}`;
}

function applyTaskGraphNodeOverrides(
  graph: TaskGraphDefinition | null,
  overrides: Record<string, Partial<TaskGraphDefinition["nodes"][number]>>,
): TaskGraphDefinition | null {
  if (!graph) return null;
  if (!Object.keys(overrides).length) return graph;
  let changed = false;
  const nodes = graph.nodes.map((node) => {
    const override = overrides[taskGraphNodeOverrideKey(graph.graph_id, node.node_id)];
    if (!override) return node;
    changed = true;
    return {
      ...node,
      ...override,
      position: override.position ?? node.position,
      ui_hints: override.ui_hints ?? node.ui_hints,
    };
  });
  if (!changed) return graph;
  return {
    ...graph,
    nodes,
  };
}

function taskGraphTimestamp(value: string | null | undefined) {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function latestTaskGraphDefinition(graphs: TaskGraphDefinition[] | null | undefined) {
  if (!graphs?.length) return null;
  return graphs.reduce<TaskGraphDefinition | null>((latest, candidate) => {
    if (!latest) return candidate;
    const candidateTime = Math.max(taskGraphTimestamp(candidate.updated_at), taskGraphTimestamp(candidate.created_at));
    const latestTime = Math.max(taskGraphTimestamp(latest.updated_at), taskGraphTimestamp(latest.created_at));
    return candidateTime >= latestTime ? candidate : latest;
  }, null);
}

function isTaskGraphNewer(candidate: TaskGraphDefinition | null | undefined, baseline: TaskGraphDefinition | null | undefined) {
  if (!candidate) return false;
  if (!baseline) return true;
  if (candidate.graph_id !== baseline.graph_id) return false;
  const candidateVersion = Number(candidate.state_version ?? 0);
  const baselineVersion = Number(baseline.state_version ?? 0);
  if (candidateVersion !== baselineVersion) return candidateVersion > baselineVersion;
  const candidateTime = Math.max(taskGraphTimestamp(candidate.updated_at), taskGraphTimestamp(candidate.created_at));
  const baselineTime = Math.max(taskGraphTimestamp(baseline.updated_at), taskGraphTimestamp(baseline.created_at));
  return candidateTime > baselineTime;
}

const TASK_GRAPH_DEBUG_DATASET_KEY = "taskGraphDebug";
const TASK_GRAPH_STATE_DATASET_KEY = "taskGraphState";
const TASK_GRAPH_FIXTURE_PENDING_MIN_MS = 1500;
const TASK_GRAPH_LIVE_RUN_PENDING_REFRESH_MS = 2500;
const TASK_GRAPH_LIVE_DISPATCH_CONFIRMATION_TIMEOUT_MS = 4000;

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
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".md") || lower.endsWith(".markdown")) return "text/markdown";
  if (lower.endsWith(".txt") || lower.endsWith(".log")) return "text/plain";
  if (lower.endsWith(".csv")) return "text/csv";
  if (lower.endsWith(".json")) return "application/json";
  if (lower.endsWith(".docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  if (lower.endsWith(".xlsx")) return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  if (lower.endsWith(".pptx")) return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
  if (lower.endsWith(".zip")) return "application/zip";
  if (lower.endsWith(".mp3")) return "audio/mpeg";
  if (lower.endsWith(".wav")) return "audio/wav";
  if (lower.endsWith(".mp4")) return "video/mp4";
  return "application/octet-stream";
}

const BROWSER_ATTACHMENT_MAX_FILES = 200;
const BROWSER_ATTACHMENT_MAX_TOTAL_BYTES = 64 * 1024 * 1024;
const VOICE_RECORDING_MAX_BYTES = 25 * 1024 * 1024;
const VOICE_RECORDING_MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/wav"];

type BrowserAttachmentCandidate = {
  file: File;
  relativePath?: string;
};

type WebkitFileSystemEntry = {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
};

type WebkitFileSystemFileEntry = WebkitFileSystemEntry & {
  file: (success: (file: File) => void, failure?: (error: DOMException) => void) => void;
};

type WebkitFileSystemDirectoryEntry = WebkitFileSystemEntry & {
  createReader: () => {
    readEntries: (success: (entries: WebkitFileSystemEntry[]) => void, failure?: (error: DOMException) => void) => void;
  };
};

function attachmentNameFromPath(path: string) {
  return path.split(/[\\/]/).pop() || path || "attachment";
}

function attachmentDraftFromPath(path: string, kind?: AttachmentDraft["kind"]): AttachmentDraft {
  const name = attachmentNameFromPath(path);
  const mimeType = kind === "folder" ? "inode/directory" : detectMime(path);
  const resolvedKind = kind ?? (mimeType.startsWith("image/") ? "image" : "file");
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}-${name}`,
    path,
    name,
    mimeType,
    kind: resolvedKind,
    previewUrl: resolvedKind === "image" ? localAssetUrl(path) : undefined,
    source: "local_path",
  };
}

function normalizeStagedAttachmentDraft(attachment: AttachmentDraft): AttachmentDraft {
  const mimeType = attachment.mimeType || detectMime(attachment.path || attachment.name);
  const kind = attachment.kind ?? (mimeType.startsWith("image/") ? "image" : "file");
  return {
    ...attachment,
    id: attachment.id || `${Date.now()}-${Math.random().toString(16).slice(2)}-${attachment.name}`,
    mimeType,
    kind,
    previewUrl: kind === "image" ? attachment.previewUrl ?? localAssetUrl(attachment.path) : undefined,
    source: attachment.source ?? "staged",
  };
}

function attachmentIdentity(attachment: AttachmentDraft) {
  const path = attachment.path.trim().toLowerCase();
  if (path) return `path:${path}`;
  return `name:${attachment.name.toLowerCase()}:${attachment.size ?? ""}:${attachment.relativePath ?? ""}`;
}

function formatAttachmentSize(value: number | null | undefined) {
  if (!value || !Number.isFinite(value)) return "";
  if (value < 1024) return `${value} B`;
  const kb = value / 1024;
  if (kb < 1024) return `${kb.toFixed(kb >= 100 ? 0 : 1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(mb >= 100 ? 0 : 1)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)} GB`;
}

function attachmentKindLabel(locale: LocaleCode, attachment: AttachmentDraft) {
  if (attachment.error) return locale === "zh-CN" ? "未加入" : "Not added";
  if (attachment.kind === "folder") {
    const count = attachment.fileCount ? (locale === "zh-CN" ? `${attachment.fileCount} 个文件` : `${attachment.fileCount} files`) : "";
    return [locale === "zh-CN" ? "文件夹" : "Folder", count].filter(Boolean).join(" · ");
  }
  if (attachment.kind === "image") return locale === "zh-CN" ? "图片" : "Image";
  const size = formatAttachmentSize(attachment.size);
  const subtype = attachment.mimeType === "application/octet-stream" ? (locale === "zh-CN" ? "文件" : "File") : attachment.mimeType.split("/").pop()?.toUpperCase();
  return [subtype || (locale === "zh-CN" ? "文件" : "File"), size].filter(Boolean).join(" · ");
}

function attachmentRouteSummary(locale: LocaleCode, attachments: AttachmentDraft[]) {
  const usable = attachments.filter((attachment) => !attachment.error && attachment.path.trim());
  if (usable.length === 0) return "";
  const imageCount = usable.filter((attachment) => attachment.kind === "image").length;
  const folderCount = usable.filter((attachment) => attachment.kind === "folder").length;
  const fileCount = Math.max(0, usable.length - imageCount - folderCount);
  const parts = [locale === "zh-CN" ? `${usable.length} 个附件` : `${usable.length} attachment${usable.length === 1 ? "" : "s"}`];
  if (imageCount) parts.push(locale === "zh-CN" ? `${imageCount} 张图片` : `${imageCount} image${imageCount === 1 ? "" : "s"}`);
  if (fileCount) parts.push(locale === "zh-CN" ? `${fileCount} 个文件` : `${fileCount} file${fileCount === 1 ? "" : "s"}`);
  if (folderCount) parts.push(locale === "zh-CN" ? `${folderCount} 个文件夹` : `${folderCount} folder${folderCount === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

function sendStageWithAttachments(locale: LocaleCode, base: string, attachments: AttachmentDraft[]) {
  const summary = attachmentRouteSummary(locale, attachments);
  return summary ? `${base} · ${summary}` : base;
}

function attachmentPendingNotice(locale: LocaleCode, diagnostics?: AttachmentDiagnostics, warning?: string) {
  const count = diagnostics?.total_count ?? 0;
  if (!count) return "";
  const route = diagnostics?.route;
  const routed = [
    route?.local_image_items ? (locale === "zh-CN" ? `${route.local_image_items} 张图片输入` : `${route.local_image_items} image input${route.local_image_items === 1 ? "" : "s"}`) : "",
    route?.mention_items ? (locale === "zh-CN" ? `${route.mention_items} 个文件引用` : `${route.mention_items} file mention${route.mention_items === 1 ? "" : "s"}`) : "",
  ].filter(Boolean).join(" · ");
  const modelLabel = [route?.provider_id, route?.model_id].filter(Boolean).join(" / ");
  const detail = [routed, modelLabel].filter(Boolean).join(" · ");
  const prefix = locale === "zh-CN" ? `已提交 ${count} 个附件` : `Submitted ${count} attachment${count === 1 ? "" : "s"}`;
  const suffix = warning
    ? locale === "zh-CN"
      ? "；模型启动响应超时，可能仍在后台运行。"
      : "; the model start response timed out and may still be running in the background."
    : "";
  return `${prefix}${detail ? ` · ${detail}` : ""}${suffix}`;
}

async function fileToStageFile(candidate: BrowserAttachmentCandidate): Promise<AttachmentStageFile> {
  const buffer = new Uint8Array(await candidate.file.arrayBuffer());
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < buffer.length; index += chunkSize) {
    binary += String.fromCharCode(...buffer.subarray(index, index + chunkSize));
  }
  return {
    name: candidate.file.name || "attachment",
    mime_type: candidate.file.type || detectMime(candidate.file.name),
    data_base64: btoa(binary),
    relative_path: candidate.relativePath || (candidate.file as File & { webkitRelativePath?: string }).webkitRelativePath || undefined,
    size: candidate.file.size,
  };
}

function supportedVoiceRecordingMimeType() {
  if (typeof window === "undefined" || typeof window.MediaRecorder === "undefined") return "";
  return VOICE_RECORDING_MIME_TYPES.find((mimeType) => window.MediaRecorder.isTypeSupported(mimeType)) ?? "";
}

async function blobToDataUri(blob: Blob) {
  const buffer = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  const chunkSize = 0x8000;
  for (let index = 0; index < buffer.length; index += chunkSize) {
    binary += String.fromCharCode(...buffer.subarray(index, index + chunkSize));
  }
  return `data:${blob.type || "audio/webm"};base64,${btoa(binary)}`;
}

async function readDirectoryEntry(entry: WebkitFileSystemDirectoryEntry): Promise<WebkitFileSystemEntry[]> {
  const reader = entry.createReader();
  const entries: WebkitFileSystemEntry[] = [];
  for (;;) {
    const batch = await new Promise<WebkitFileSystemEntry[]>((resolve, reject) => {
      reader.readEntries(resolve, reject);
    });
    if (batch.length === 0) break;
    entries.push(...batch);
  }
  return entries;
}

async function filesFromWebkitEntry(entry: WebkitFileSystemEntry, prefix = ""): Promise<BrowserAttachmentCandidate[]> {
  const relativePath = `${prefix}${entry.name}`;
  if (entry.isFile) {
    const file = await new Promise<File>((resolve, reject) => {
      (entry as WebkitFileSystemFileEntry).file(resolve, reject);
    });
    return [{ file, relativePath }];
  }
  if (entry.isDirectory) {
    const children = await readDirectoryEntry(entry as WebkitFileSystemDirectoryEntry);
    const nested = await Promise.all(children.map((child) => filesFromWebkitEntry(child, `${relativePath}/`)));
    return nested.flat();
  }
  return [];
}

async function filesFromDataTransfer(dataTransfer: DataTransfer): Promise<BrowserAttachmentCandidate[]> {
  const directFiles: BrowserAttachmentCandidate[] = [];
  const directoryEntries: WebkitFileSystemEntry[] = [];
  for (const item of [...dataTransfer.items].filter((entry) => entry.kind === "file")) {
    const getAsEntry = (item as unknown as { webkitGetAsEntry?: () => WebkitFileSystemEntry | null }).webkitGetAsEntry;
    const entry = getAsEntry ? getAsEntry.call(item) : null;
    if (entry?.isDirectory) {
      directoryEntries.push(entry);
      continue;
    }
    const file = item.getAsFile();
    if (file) {
      directFiles.push({ file, relativePath: entry?.name || undefined });
    }
  }
  if (directoryEntries.length > 0) {
    const nested = await Promise.all(directoryEntries.map((entry) => filesFromWebkitEntry(entry)));
    return [...directFiles, ...nested.flat()];
  }
  if (directFiles.length > 0) {
    return directFiles;
  }
  return [...dataTransfer.files].map((file) => ({
    file,
    relativePath: (file as File & { webkitRelativePath?: string }).webkitRelativePath || undefined,
  }));
}

function directoryNameFromCandidates(candidates: BrowserAttachmentCandidate[]) {
  const first = candidates.find((candidate) => candidate.relativePath?.includes("/"))?.relativePath;
  return first ? first.split("/").filter(Boolean)[0] : null;
}

function dataTransferHasFiles(dataTransfer: DataTransfer) {
  return [...dataTransfer.types].includes("Files") || dataTransfer.files.length > 0;
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
        ? `${stageLabel}: Codex 运行时意外关闭。请点右侧“重启运行时”后重试；如果任务运行时已经创建，应用会尝试从本地 .astrabridge 缓存恢复。`
        : `${stageLabel}: The Codex runtime closed unexpectedly. Restart Runtime and retry; if the task runtime was created, the app will try to recover it from local .astrabridge cache.`;
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

function runtimeStateLabel(locale: LocaleCode, options: { waitingOnApproval: boolean; sending: boolean; activeStatusType: string }) {
  if (options.waitingOnApproval) return locale === "zh-CN" ? "等待审批" : "Waiting for approval";
  if (options.sending) return locale === "zh-CN" ? "正在发送" : "Sending";
  if (options.activeStatusType === "active") return locale === "zh-CN" ? "运行中" : "Running";
  return locale === "zh-CN" ? "空闲" : "Idle";
}

function contextUsageLabel(supervisor?: RuntimeSupervisorState) {
  const token = supervisor?.token;
  if (!token?.context_window) return "n/a";
  return `${token.context_percent}% · ${token.total_tokens.toLocaleString()} / ${token.context_window.toLocaleString()}`;
}

function workflowRecoveryLabel(locale: LocaleCode, facts: TaskWorkflowFacts) {
  if (facts.recoveredCommandCount > 0) return locale === "zh-CN" ? `${facts.recoveredCommandCount} 条已恢复` : `${facts.recoveredCommandCount} recovered`;
  if (facts.failedCommandCount > 0) return locale === "zh-CN" ? `${facts.failedCommandCount} 条待处理` : `${facts.failedCommandCount} pending`;
  return locale === "zh-CN" ? "正常" : "Clear";
}

function isRecentBrowserSignal(browser: RuntimeSupervisorState["browser"] | undefined, maxAgeMs = 30 * 60 * 1000) {
  const createdAt = String(browser?.created_at || "").trim();
  if (!createdAt) return false;
  const parsed = Date.parse(createdAt);
  if (!Number.isFinite(parsed)) return false;
  return Date.now() - parsed <= maxAgeMs;
}

function actionableWorkflowDiagnostics(facts: TaskWorkflowFacts) {
  return facts.diagnosticRefs.filter((item) => item.kind !== "provider_handoff");
}

function buildStatusAttentionItems({
  locale,
  supervisor,
  workflowFacts,
  capabilityWarnings,
}: {
  locale: LocaleCode;
  supervisor?: RuntimeSupervisorState;
  workflowFacts: TaskWorkflowFacts;
  capabilityWarnings: string[];
}): StatusAttentionItem[] {
  const items: StatusAttentionItem[] = [];
  const guardLevel = supervisor?.guard.level ?? "ok";
  const browserStatus = supervisor?.browser?.status;
  const browserSignalIsRecent = isRecentBrowserSignal(supervisor?.browser);
  const mcpStatus = supervisor?.environment?.mcp?.status;
  const git = supervisor?.environment?.git;
  if (supervisor?.runtime_error) {
    items.push({
      id: "runtime-error",
      severity: "danger",
      label: locale === "zh-CN" ? "运行错误" : "Runtime error",
      detail: runtimeErrorNoticeText(supervisor.runtime_error),
    });
  }
  if (guardLevel && guardLevel !== "ok") {
    items.push({
      id: "context-guard",
      severity: guardLevel === "pause" || guardLevel === "danger" ? "danger" : "warning",
      label: locale === "zh-CN" ? "上下文风险" : "Context risk",
      detail: supervisor?.guard.message || contextUsageLabel(supervisor),
    });
  }
  if (browserSignalIsRecent && browserStatus && browserStatus !== "pass") {
    items.push({
      id: "browser",
      severity: "warning",
      label: locale === "zh-CN" ? "浏览器异常" : "Browser issue",
      detail: productStatusLabel(browserStatus),
    });
  }
  if (mcpStatus && !["ok", "pass", "listed"].includes(String(mcpStatus).toLowerCase())) {
    items.push({
      id: "mcp",
      severity: "warning",
      label: "MCP",
      detail: productStatusLabel(mcpStatus),
    });
  }
  if (git?.is_repo && (git.changed_files > 0 || git.added > 0 || git.deleted > 0)) {
    items.push({
      id: "git-dirty",
      severity: "info",
      label: locale === "zh-CN" ? "Git 有改动" : "Git changes",
      detail: `${git.branch || "repo"} · ${git.changed_files} files · +${git.added} -${git.deleted}`,
    });
  }
  if (workflowFacts.failedCommandCount > 0) {
    const failedCommands = (workflowFacts.commandRefs ?? []).filter((item) => String(item.status ?? "").toLowerCase() === "failed");
    items.push({
      id: "failed-commands",
      severity: "warning",
      label: locale === "zh-CN" ? "失败命令" : "Failed commands",
      detail: failedCommands.slice(-2).map((item) => `${item.command} (${item.status ?? "failed"})`).join(" / "),
    });
  }
  const actionableDiagnostics = actionableWorkflowDiagnostics(workflowFacts);
  if (actionableDiagnostics.length > 0) {
    items.push({
      id: "diagnostics",
      severity: "warning",
      label: locale === "zh-CN" ? "诊断事件" : "Diagnostics",
      detail: actionableDiagnostics.slice(-2).map((item) => item.summary).join(" / "),
    });
  }
  capabilityWarnings.slice(0, 3).forEach((warning, index) => {
    items.push({
      id: `capability-${index}`,
      severity: "warning",
      label: locale === "zh-CN" ? "能力限制" : "Capability limit",
      detail: warning,
    });
  });
  return items;
}

function buildStatusEvidenceItems({
  locale,
  supervisor,
  workflowFacts,
  goal,
}: {
  locale: LocaleCode;
  supervisor?: RuntimeSupervisorState;
  workflowFacts: TaskWorkflowFacts;
  goal: DisplayGoal | null;
}): StatusEvidenceItem[] {
  const items: StatusEvidenceItem[] = [];
  if (supervisor?.token?.context_window) {
    items.push({
      id: "context",
      label: locale === "zh-CN" ? "上下文" : "Context",
      value: contextUsageLabel(supervisor),
    });
  }
  if (goal?.tokensUsed || goal?.tokenBudget) {
    items.push({
      id: "goal-token",
      label: "Token",
      value: `${goal.tokensUsed ?? 0}${goal.tokenBudget ? ` / ${goal.tokenBudget}` : ""}`,
    });
  }
  const latestCheckpoint = workflowFacts.checkpointRefs[workflowFacts.checkpointRefs.length - 1];
  if (latestCheckpoint) {
    items.push({
      id: "checkpoint",
      label: locale === "zh-CN" ? "最近保存点" : "Latest checkpoint",
      value: latestCheckpoint.description || latestCheckpoint.save_id,
      detail: latestCheckpoint.save_id,
    });
  }
  const latestDiagnostic = workflowFacts.diagnosticRefs[workflowFacts.diagnosticRefs.length - 1];
  if (latestDiagnostic) {
    items.push({
      id: "diagnostic",
      label: locale === "zh-CN" ? "最近诊断" : "Latest diagnostic",
      value: latestDiagnostic.summary,
      detail: latestDiagnostic.kind,
    });
  }
  if (!items.length && (workflowFacts.failedCommandCount > 0 || workflowFacts.recoveredCommandCount > 0)) {
    items.push({
      id: "workflow",
      label: locale === "zh-CN" ? "工作流" : "Workflow",
      value: workflowRecoveryLabel(locale, workflowFacts),
    });
  }
  return items;
}

function dogfoodStatusLabel(locale: LocaleCode, value: string | null | undefined) {
  const normalized = String(value || "idle").trim().toLowerCase();
  if (locale !== "zh-CN") return normalized || "idle";
  const labels: Record<string, string> = {
    idle: "空闲",
    running: "运行中",
    waiting: "等待中",
    blocked: "已阻塞",
    complete: "已完成",
  };
  return labels[normalized] ?? normalized;
}

function dogfoodPhaseLabel(locale: LocaleCode, value: string | null | undefined) {
  const normalized = String(value || "").trim();
  if (locale !== "zh-CN" || !normalized) return normalized;
  const labels: Record<string, string> = {
    not_started: "尚未开始",
    astrabridge_autonomy_hardening: "自治能力加固",
  };
  return labels[normalized] ?? normalized;
}

function manifestSectionLabel(locale: LocaleCode, value: string) {
  if (locale !== "zh-CN") return value;
  const labels: Record<string, string> = {
    sprites: "角色与精灵",
    tiles: "地图瓦片",
    hud: "界面元素",
  };
  return labels[value] ?? value;
}

function dogfoodRecordText(locale: LocaleCode, value: string) {
  if (locale !== "zh-CN") return value;
  return [
    ["Browser smoke", "浏览器烟测"],
    ["URL status", "URL 状态"],
    ["status", "状态"],
    ["local", "本地"],
    ["fail", "失败"],
    ["pass", "通过"],
  ].reduce((text, [from, to]) => text.split(from).join(to), value);
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

function permissionModeCopy(locale: LocaleCode, mode: PermissionMode) {
  const label = permissionLabel(locale, mode);
  if (locale === "zh-CN") {
    if (mode === "ask") {
      return {
        label,
        detail: "每个可能修改文件、执行命令、访问网络或提升权限的动作都会先停下来让你确认，最保守，适合不确定任务。",
      };
    }
    if (mode === "full") {
      return {
        label,
        detail: "允许模型在当前项目和本机环境中直接执行，等同于 danger-full-access。只在你信任任务和仓库状态时使用。",
      };
    }
    return {
      label,
      detail: "默认推荐。模型可以自动完成低风险读写和常规命令，遇到高风险或越权操作时再请求确认。",
    };
  }
  if (mode === "ask") {
    return {
      label,
      detail: "Review each file change, command, network access, or permission escalation before it runs. Safest for uncertain tasks.",
    };
  }
  if (mode === "full") {
    return {
      label,
      detail: "Let the model run directly with danger-full-access in this local environment. Use only when you trust the task and workspace.",
    };
  }
  return {
    label,
    detail: "Recommended default. Routine low-risk work can run automatically; higher-risk or out-of-policy actions still ask for approval.",
  };
}

function PermissionModeIcon({ mode, size = 14 }: { mode: PermissionMode; size?: number }) {
  if (mode === "ask") return <StarbridgePermissionAskIcon size={size} strokeWidth={1.9} aria-hidden="true" />;
  if (mode === "full") return <StarbridgePermissionFullIcon size={size} strokeWidth={1.9} aria-hidden="true" />;
  return <StarbridgePermissionAutoIcon size={size} strokeWidth={1.9} aria-hidden="true" />;
}

function PermissionModePicker({
  locale,
  value,
  onChange,
}: {
  locale: LocaleCode;
  value: PermissionMode;
  onChange: (value: PermissionMode) => void;
}) {
  const [open, setOpen] = useState(false);
  const [previewMode, setPreviewMode] = useState<PermissionMode>(value);
  const modes: PermissionMode[] = ["ask", "auto", "full"];
  const selected = permissionModeCopy(locale, value);
  const preview = permissionModeCopy(locale, previewMode);
  useEffect(() => {
    setPreviewMode(value);
  }, [value]);
  return (
    <div
      className={`permission-picker ${permissionClass(value)} ${open ? "permission-picker-open" : ""}`}
      onBlur={(event) => {
        const nextTarget = event.relatedTarget;
        if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) {
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        className="permission-trigger"
        data-composer="permission"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${t(locale, "title_permission")}: ${selected.label}`}
        title={`${selected.label}: ${selected.detail}`}
        onClick={() => {
          setPreviewMode(value);
          setOpen((current) => !current);
        }}
      >
        <span className="permission-mode-icon">
          <PermissionModeIcon mode={value} />
        </span>
        <span>{selected.label}</span>
        <ChevronDown size={13} strokeWidth={1.8} aria-hidden="true" />
      </button>
      {open ? (
        <div className="permission-menu" role="menu" aria-label={t(locale, "title_permission")}>
          {modes.map((mode) => {
            const copy = permissionModeCopy(locale, mode);
            return (
              <button
                type="button"
                key={mode}
                className={`permission-menu-option ${permissionClass(mode)} ${mode === value ? "permission-menu-option-active" : ""}`}
                role="menuitemradio"
                aria-checked={mode === value}
                aria-describedby="permission-mode-detail-card"
                onMouseEnter={() => setPreviewMode(mode)}
                onFocus={() => setPreviewMode(mode)}
                onClick={() => {
                  onChange(mode);
                  setOpen(false);
                }}
              >
                <span className="permission-mode-icon">
                  <PermissionModeIcon mode={mode} />
                </span>
                <span>{copy.label}</span>
                {mode === value ? <CheckCircle2 size={13} strokeWidth={1.8} aria-hidden="true" /> : null}
              </button>
            );
          })}
          <aside className={`permission-mode-card ${permissionClass(previewMode)}`} id="permission-mode-detail-card" role="tooltip">
            <span className="permission-mode-icon">
              <PermissionModeIcon mode={previewMode} size={15} />
            </span>
            <strong>{preview.label}</strong>
            <span>{preview.detail}</span>
          </aside>
        </div>
      ) : null}
    </div>
  );
}

function executionPolicyCopy(locale: LocaleCode, policy: ComposerExecutionPolicy) {
  if (policy === "patch_only") {
    return locale === "zh-CN"
      ? { label: "仅补丁", detail: "只允许经验证的原生 apply_patch 路径；当前运行时若无法证明该约束，会在请求模型前拒绝执行。" }
      : { label: "Patch only", detail: "Requires a verified native apply_patch-only boundary. AstraBridge refuses the turn before dispatch if it cannot prove that boundary." };
  }
  return locale === "zh-CN"
    ? { label: "标准执行", detail: "使用当前权限模式。命令与文件变更仍会遵循审批与运行时审计。" }
    : { label: "Standard", detail: "Uses the selected permission mode. Commands and file changes remain subject to approval and runtime audit." };
}

function ExecutionPolicyPicker({
  locale,
  value,
  onChange,
}: {
  locale: LocaleCode;
  value: ComposerExecutionPolicy;
  onChange: (value: ComposerExecutionPolicy) => void;
}) {
  const [open, setOpen] = useState(false);
  const policies: ComposerExecutionPolicy[] = ["standard", "patch_only"];
  const selected = executionPolicyCopy(locale, value);
  const label = locale === "zh-CN" ? "执行约束" : "Execution policy";
  return (
    <div
      className={`execution-policy-picker ${open ? "execution-policy-picker-open" : ""}`}
      onBlur={(event) => {
        const nextTarget = event.relatedTarget;
        if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) setOpen(false);
      }}
    >
      <button
        type="button"
        className="execution-policy-trigger"
        data-composer="execution-policy"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${label}: ${selected.label}`}
        title={`${selected.label}: ${selected.detail}`}
        onClick={() => setOpen((current) => !current)}
      >
        <ShieldCheck size={14} strokeWidth={1.9} aria-hidden="true" />
        <span>{selected.label}</span>
        <ChevronDown size={13} strokeWidth={1.8} aria-hidden="true" />
      </button>
      {open ? (
        <div className="execution-policy-menu" role="menu" aria-label={label}>
          {policies.map((policy) => {
            const copy = executionPolicyCopy(locale, policy);
            return (
              <button
                type="button"
                key={policy}
                role="menuitemradio"
                aria-checked={policy === value}
                title={copy.detail}
                onClick={() => {
                  onChange(policy);
                  setOpen(false);
                }}
              >
                <ShieldCheck size={13} strokeWidth={1.9} aria-hidden="true" />
                <span>{copy.label}</span>
                {policy === value ? <CheckCircle2 size={13} strokeWidth={1.8} aria-hidden="true" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function workflowModeCopy(locale: LocaleCode, mode: ComposerWorkflowMode) {
  if (locale === "zh-CN") {
    if (mode === "plan") {
      return {
        label: t(locale, "mode_plan"),
        detail: "先组织实施计划，适合需要核对范围、步骤或风险的任务。",
      };
    }
    if (mode === "goal") {
      return {
        label: "目标",
        detail: "设置持续目标，让任务围绕长期目标推进；非目标任务不会占用目标面板空间。",
      };
    }
    return {
      label: t(locale, "mode_default"),
      detail: "普通对话框与直接执行模式。第一次进入任务默认使用这个模式。",
    };
  }
  if (mode === "plan") {
    return {
      label: t(locale, "mode_plan"),
      detail: "Plan first, then ask for confirmation before implementation.",
    };
  }
  if (mode === "goal") {
    return {
      label: "Goal",
      detail: "Set a persistent objective for this task without showing the goal panel during normal chat.",
    };
  }
  return {
    label: t(locale, "mode_default"),
    detail: "Default chat and execution mode. New tasks start here.",
  };
}

function WorkflowModeIcon({ mode, size = 14 }: { mode: ComposerWorkflowMode; size?: number }) {
  if (mode === "plan") return <StarbridgeWorkflowPlanIcon size={size} strokeWidth={1.9} aria-hidden="true" />;
  if (mode === "goal") return <StarbridgeWorkflowGoalIcon size={size} strokeWidth={1.9} aria-hidden="true" />;
  return <StarbridgeWorkflowDefaultIcon size={size} strokeWidth={1.9} aria-hidden="true" />;
}

function WorkflowModePicker({
  locale,
  value,
  onChange,
}: {
  locale: LocaleCode;
  value: ComposerWorkflowMode;
  onChange: (value: ComposerWorkflowMode) => void;
}) {
  const [open, setOpen] = useState(false);
  const [previewMode, setPreviewMode] = useState<ComposerWorkflowMode>(value);
  const modes: ComposerWorkflowMode[] = ["default", "plan", "goal"];
  const selected = workflowModeCopy(locale, value);
  const preview = workflowModeCopy(locale, previewMode);
  const label = locale === "zh-CN" ? "工作模式" : "Workflow mode";
  useEffect(() => {
    setPreviewMode(value);
  }, [value]);
  return (
    <div
      className={`workflow-mode-picker workflow-mode-${value} ${open ? "workflow-mode-picker-open" : ""}`}
      data-composer="workflow-mode"
      onBlur={(event) => {
        const nextTarget = event.relatedTarget;
        if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) {
          setOpen(false);
        }
      }}
    >
      <button
        type="button"
        className="workflow-mode-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${label}: ${selected.label}`}
        title={`${selected.label}: ${selected.detail}`}
        onClick={() => {
          setPreviewMode(value);
          setOpen((current) => !current);
        }}
      >
        <span className="workflow-mode-icon">
          <WorkflowModeIcon mode={value} />
        </span>
        <span>{selected.label}</span>
        <ChevronDown size={13} strokeWidth={1.8} aria-hidden="true" />
      </button>
      {open ? (
        <div className="workflow-mode-menu" role="menu" aria-label={label}>
          {modes.map((mode) => {
            const copy = workflowModeCopy(locale, mode);
            return (
              <button
                type="button"
                key={mode}
                className={`workflow-mode-option ${mode === value ? "workflow-mode-option-active" : ""}`}
                role="menuitemradio"
                aria-checked={mode === value}
                aria-describedby="workflow-mode-detail-card"
                onMouseEnter={() => setPreviewMode(mode)}
                onFocus={() => setPreviewMode(mode)}
                onClick={() => {
                  onChange(mode);
                  setOpen(false);
                }}
              >
                <span className="workflow-mode-icon">
                  <WorkflowModeIcon mode={mode} />
                </span>
                <span>{copy.label}</span>
                {mode === value ? <CheckCircle2 size={13} strokeWidth={1.8} aria-hidden="true" /> : null}
              </button>
            );
          })}
          <aside className="workflow-mode-card" id="workflow-mode-detail-card" role="tooltip">
            <span className="workflow-mode-icon">
              <WorkflowModeIcon mode={previewMode} size={15} />
            </span>
            <strong>{preview.label}</strong>
            <span>{preview.detail}</span>
          </aside>
        </div>
      ) : null}
    </div>
  );
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

const STATUS_NOTICE_PREVIEW_ITEMS = 3;

function ConversationNoticeBar({
  locale,
  notices,
  onOpenSetup,
}: {
  locale: LocaleCode;
  notices: Array<{ key: string; text: string; tone?: "warning" | "danger" | "info"; action?: "setup" }>;
  onOpenSetup: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  if (notices.length === 0) return null;
  const primaryNotice = notices.find((notice) => notice.tone === "danger") ?? notices[0];
  const collapsedNotices = [primaryNotice, ...notices.filter((notice) => notice.key !== primaryNotice.key)].slice(
    0,
    STATUS_NOTICE_PREVIEW_ITEMS,
  );
  const visibleNotices = expanded ? notices : collapsedNotices;
  const hiddenCount = Math.max(notices.length - visibleNotices.length, 0);
  const toggleLabel =
    locale === "zh-CN"
      ? expanded
        ? "收起"
        : `还有 ${hiddenCount} 条`
      : expanded
        ? "Collapse"
        : `${hiddenCount} more`;
  return (
    <div className={`conversation-notice-bar ${expanded ? "conversation-notice-bar-expanded" : ""}`} role="status">
      <div className="conversation-notice-list">
        {visibleNotices.map((notice) => (
          <div className="conversation-notice-row" key={notice.key}>
            <div className={`conversation-notice conversation-notice-${notice.tone ?? "warning"}`}>
              <span className="notice-dot" aria-hidden="true" />
              {notice.action === "setup" ? (
                <button type="button" className="notice-link" onClick={onOpenSetup}>
                  {notice.text}
                </button>
              ) : (
                <span>{notice.text}</span>
              )}
            </div>
          </div>
        ))}
      </div>
      {hiddenCount > 0 ? (
        <button type="button" className="conversation-notice-toggle" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
          <span>{toggleLabel}</span>
          {expanded ? <ChevronUp size={14} strokeWidth={1.8} aria-hidden="true" /> : <ChevronDown size={14} strokeWidth={1.8} aria-hidden="true" />}
        </button>
      ) : null}
    </div>
  );
}

function conversationStateCopy(locale: LocaleCode, state: ConversationRenderState) {
  if (locale !== "zh-CN") return { title: state.title, detail: "detail" in state ? state.detail : "" };
  if (state.kind === "loading") {
    return { title: "正在加载任务", detail: "AstraBridge 正在刷新任务对话和内部执行线路。" };
  }
  if (state.kind === "empty") {
    if (state.emptyKind === "terminal_empty") {
      return { title: "这一轮已结束但没有可见输出", detail: "最新 turn 已完成，但没有 assistant、工具、计划、artifact 或诊断内容可显示。" };
    }
    return { title: "还没有对话轮次", detail: "先输入提示词或添加附件。" };
  }
  if (state.kind === "diagnostic") {
    switch (state.diagnosticKind) {
      case "runtime_error":
        return { title: "任务运行时错误", detail: "运行时报告了 systemError。请查看右侧 inspector 的恢复控制，或重启后重试。" };
      case "thread_not_loaded":
        return { title: "执行线路尚未载入", detail: "运行时还没有载入当前任务的执行线路。请刷新任务，或切回当前任务的活动 provider 线路。" };
      case "turn_failed":
        return { title: "上一轮执行失败", detail: state.detail || "上一轮在生成可见 assistant 响应前失败。" };
      case "turn_interrupted":
        return { title: "上一轮已中断", detail: "turn 在完成前被中断。你可以继续、重试，或从当前任务创建一个更窄的分支任务。" };
      case "turn_cancelled":
        return { title: "上一轮已取消", detail: "turn 在产生可见 assistant 响应前被取消。" };
      case "render_mismatch":
        return { title: "任务数据需要检查", detail: "API 返回了 turn 数据，但聊天区无法渲染为可见消息。请查看 inspector 里的执行线路和 task-conversation 证据。" };
      case "stale_runtime_error":
        return { title: "已恢复旧运行时错误状态", detail: "运行时之前报告过错误，但最新完成的 turn 是干净的；原始状态已保留在诊断信息中。" };
    }
  }
  return { title: state.title, detail: "detail" in state ? state.detail : "" };
}

function ConversationEmptyState({ locale, state }: { locale: LocaleCode; state: ConversationRenderState }) {
  const copy = conversationStateCopy(locale, state);
  const role = state.kind === "diagnostic" && state.tone === "danger" ? "alert" : "status";
  return (
    <div className={`empty-state conversation-empty-state conversation-empty-${state.tone}`} role={role} data-testid="conversation-empty-state">
      <strong>{copy.title}</strong>
      {copy.detail ? <span>{copy.detail}</span> : null}
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
  if (activity.kind === "fork") return "创建分支任务";
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
  onAcceptPlan,
  onRequestPlanChanges,
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
  onAcceptPlan?: () => void;
  onRequestPlanChanges?: (feedback: string) => void;
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
          <MessageBlockContent
            block={block}
            locale={locale}
            reasoningDisplayPolicy={reasoningDisplayPolicy}
            onAcceptPlan={onAcceptPlan}
            onRequestPlanChanges={onRequestPlanChanges}
          />
        </div>
        {!isUser ? (
          <footer className="chat-message-footer">
            {duration ? <span>{duration}</span> : <span>-</span>}
            <button type="button" className="message-action-button" title={t(locale, "fork_thread")} aria-label={t(locale, "fork_thread")} onClick={onFork}>
              <StarbridgeForkTaskIcon size={14} strokeWidth={1.9} aria-hidden="true" />
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

function MessageBlockContent({
  block,
  locale,
  reasoningDisplayPolicy,
  onAcceptPlan,
  onRequestPlanChanges,
}: {
  block: ThreadRenderBlock;
  locale: "en" | "zh-CN";
  reasoningDisplayPolicy?: string;
  onAcceptPlan?: () => void;
  onRequestPlanChanges?: (feedback: string) => void;
}) {
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
    return extractProposedPlanText(block.text) ? (
      <PlanRenderer text={block.text} locale={locale} onAcceptPlan={onAcceptPlan} onRequestPlanChanges={onRequestPlanChanges} />
    ) : (
      <CollapsibleTextBlock text={block.text || " "} />
    );
  }
  if (block.role === "plan") return <PlanRenderer text={block.text} locale={locale} onAcceptPlan={onAcceptPlan} onRequestPlanChanges={onRequestPlanChanges} />;
  if (block.role === "reasoning") {
    return <ReasoningPreview text={block.text} source={block.source} live={block.live} displayPolicy={reasoningDisplayPolicy} />;
  }
  if (block.role === "activity") {
    const entry = normalizeRuntimeActivity(block);
    return entry ? <RuntimeActivityRow entry={entry} locale={locale} /> : null;
  }
  if (block.role === "command") {
    const entry = normalizeRuntimeActivity(block);
    return entry ? <RuntimeActivityRow entry={entry} locale={locale} /> : null;
  }
  if (block.role === "file_change") {
    const entry = normalizeRuntimeActivity(block);
    return entry ? <RuntimeActivityRow entry={entry} locale={locale} /> : null;
  }
  if (block.role === "tool") {
    const entry = normalizeRuntimeActivity(block);
    return entry ? <RuntimeActivityRow entry={entry} locale={locale} /> : null;
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

type PlanRendererProps = {
  text: string;
  compact?: boolean;
  locale?: "en" | "zh-CN";
  onAcceptPlan?: () => void;
  onRequestPlanChanges?: (feedback: string) => void;
};

function PlanRenderer({ text, compact = false, locale = "zh-CN", onAcceptPlan, onRequestPlanChanges }: PlanRendererProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [adjustmentOpen, setAdjustmentOpen] = useState(false);
  const [adjustmentText, setAdjustmentText] = useState("");
  const card = useMemo(() => parsePlanCard(text), [text]);
  const sectionLimit = compact ? 2 : expanded ? card.sections.length : 4;
  const visibleSections = card.sections.slice(0, sectionLimit);
  const hiddenSectionCount = Math.max(card.sections.length - visibleSections.length, 0);
  const hasStructuredContent = card.sections.length > 0;
  const shouldShowExpand = card.isLong || hiddenSectionCount > 0;
  const showRaw = !hasStructuredContent && (expanded || !card.isLong);
  const hasPlanActions = !compact && Boolean(onAcceptPlan || onRequestPlanChanges);
  const labels =
    locale === "zh-CN"
      ? {
          badge: "计划",
          copy: copied ? "已复制" : "复制",
          collapse: "收起计划",
          expand: "展开计划",
          hidden: (count: number) => `还有 ${count} 个部分，展开查看。`,
          summary: "概要",
          steps: "实现步骤",
          approve: "同意并开始实施",
          adjust: "需要调整",
          adjustmentPlaceholder: "写下需要调整的点。提交后会要求重新制定计划。",
          submitAdjustment: "提交调整",
          raw: "计划原文",
        }
      : {
          badge: "Plan",
          copy: copied ? "Copied" : "Copy",
          collapse: "Collapse plan",
          expand: "Expand plan",
          hidden: (count: number) => `${count} more section${count === 1 ? "" : "s"} hidden. Expand to review.`,
          summary: "Summary",
          steps: "Implementation Steps",
          approve: "Approve and start",
          adjust: "Request changes",
          adjustmentPlaceholder: "Describe what should change. Submitting will ask the agent to revise the plan.",
          submitAdjustment: "Submit changes",
          raw: "Raw plan",
        };

  async function copyPlan() {
    try {
      await navigator.clipboard?.writeText(card.raw);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  function submitAdjustment() {
    const feedback = adjustmentText.trim();
    if (!feedback || !onRequestPlanChanges) return;
    onRequestPlanChanges(feedback);
    setAdjustmentText("");
    setAdjustmentOpen(false);
  }

  return (
    <article className={`plan-artifact-card ${compact ? "plan-artifact-card-compact" : ""}`} data-testid="plan-artifact-card">
      <div className="plan-artifact-toolbar">
        <span className="plan-artifact-badge">{labels.badge}</span>
        {!compact ? (
          <div className="plan-artifact-actions">
            <button type="button" className="plan-artifact-icon-button" onClick={copyPlan} title={labels.copy}>
              <ClipboardCopy size={14} strokeWidth={1.8} aria-hidden="true" />
              <span>{labels.copy}</span>
            </button>
            {shouldShowExpand ? (
              <button type="button" className="plan-artifact-icon-button" onClick={() => setExpanded((value) => !value)} title={expanded ? labels.collapse : labels.expand}>
                {expanded ? <ChevronUp size={14} strokeWidth={1.8} aria-hidden="true" /> : <ChevronDown size={14} strokeWidth={1.8} aria-hidden="true" />}
                <span>{expanded ? labels.collapse : labels.expand}</span>
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      <header className="plan-artifact-header">
        <h3>{card.title}</h3>
        {card.summary[0] ? <p>{renderPlanInline(card.summary[0])}</p> : null}
      </header>

      {hasStructuredContent ? (
        <div className="plan-artifact-sections">
          {visibleSections.map((section, index) => (
            <PlanArtifactSection key={`${section.title}-${index}`} section={section} compact={compact} />
          ))}
          {hiddenSectionCount > 0 ? <p className="plan-artifact-hidden">{labels.hidden(hiddenSectionCount)}</p> : null}
        </div>
      ) : (
        <div className="plan-artifact-sections">
          {card.summary.length > 0 ? (
            <section className="plan-artifact-section">
              <h4>{labels.summary}</h4>
              <ul>
                {card.summary.slice(0, compact ? 3 : 6).map((item) => (
                  <li key={item}>{renderPlanInline(item)}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {card.steps.length > 0 ? (
            <section className="plan-artifact-section">
              <h4>{labels.steps}</h4>
              <ul>
                {card.steps.slice(0, compact ? 4 : 8).map((step, index) => (
                  <li key={`${step}-${index}`}>{renderPlanInline(step)}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      )}

      {showRaw ? (
        <details className="plan-artifact-raw" open={!card.isLong}>
          <summary>{labels.raw}</summary>
          <pre>{card.raw}</pre>
        </details>
      ) : null}

      {hasPlanActions ? (
        <div className="plan-approval-panel">
          <div className="plan-approval-actions">
            {onAcceptPlan ? (
              <button type="button" className="primary-button plan-approval-primary" onClick={onAcceptPlan}>
                <CheckCircle2 size={15} strokeWidth={1.9} aria-hidden="true" />
                <span>{labels.approve}</span>
              </button>
            ) : null}
            {onRequestPlanChanges ? (
              <button type="button" className="ghost-button plan-approval-secondary" onClick={() => setAdjustmentOpen((value) => !value)}>
                <StarbridgeWorkflowDefaultIcon size={15} strokeWidth={1.9} aria-hidden="true" />
                <span>{labels.adjust}</span>
              </button>
            ) : null}
          </div>
          {adjustmentOpen && onRequestPlanChanges ? (
            <div className="plan-adjustment-box">
              <textarea rows={3} value={adjustmentText} onChange={(event) => setAdjustmentText(event.target.value)} placeholder={labels.adjustmentPlaceholder} />
              <button type="button" className="primary-button" disabled={!adjustmentText.trim()} onClick={submitAdjustment}>
                {labels.submitAdjustment}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function PlanArtifactSection({ section, compact }: { section: { title: string; body: string[]; items: string[] }; compact: boolean }) {
  const bodyLimit = compact ? 1 : section.body.length;
  const itemLimit = compact ? 3 : section.items.length;
  return (
    <section className="plan-artifact-section">
      <h4>{section.title}</h4>
      {section.body.slice(0, bodyLimit).map((line, index) => (
        <p key={`${section.title}-body-${index}`}>{renderPlanInline(line)}</p>
      ))}
      {section.items.length > 0 ? (
        <ul>
          {section.items.slice(0, itemLimit).map((item, index) => (
            <li key={`${section.title}-item-${index}`}>{renderPlanInline(item)}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function renderPlanInline(text: string): ReactNode {
  const parts = String(text || "").split(/(`[^`]+`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code className="plan-inline-code" key={`${part}-${index}`}>
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

function GoalModeDock({
  locale,
  goal,
  draft,
  onDraftChange,
  canWriteGoal,
  editMode,
  onEditModeChange,
  activeTab,
  onTabChange,
  runnerArmed,
  queueCount,
  plan,
  proposedPlanText,
  onSetActive,
  onPause,
  onResume,
  onClear,
}: {
  locale: "en" | "zh-CN";
  goal: DisplayGoal | null | undefined;
  draft: string;
  onDraftChange: (value: string) => void;
  canWriteGoal: boolean;
  editMode: boolean;
  onEditModeChange: (value: boolean) => void;
  activeTab: GoalDockTab;
  onTabChange: (value: GoalDockTab) => void;
  runnerArmed: boolean;
  queueCount: number;
  plan: RuntimeSupervisorState["plan"] | undefined | null;
  proposedPlanText: string;
  onSetActive: () => void;
  onPause: () => void;
  onResume: () => void;
  onClear: () => void;
}) {
  const hasGoal = Boolean(goal?.objective);
  const status = String(goal?.status ?? "paused");
  const statusText = hasGoal ? goalStatusLabel(locale, status, goal?.source) : locale === "zh-CN" ? "未设置目标" : "No goal";
  const canControl = canWriteGoal && hasGoal && goal?.source === "thread";
  const paused = !goalCanAutoContinue(status);
  const modeTitle = activeTab === "plan" ? (locale === "zh-CN" ? "计划模式" : "Plan mode") : statusText;
  return (
    <section className={`goal-mode-dock goal-mode-${hasGoal ? status : "empty"}`} data-testid="goal-mode-dock">
      <div className="goal-mode-head">
        <div className="goal-mode-title">
          {activeTab === "plan" ? <StarbridgeWorkflowPlanIcon size={16} strokeWidth={1.95} aria-hidden="true" /> : <StarbridgeWorkflowGoalIcon size={16} strokeWidth={1.95} aria-hidden="true" />}
          <span>{modeTitle}</span>
          {runnerArmed && goalCanAutoContinue(status) ? <em>{locale === "zh-CN" ? "持续执行" : "auto-run"}</em> : null}
          {queueCount > 0 ? <em>{locale === "zh-CN" ? `队列 ${queueCount}` : `queue ${queueCount}`}</em> : null}
        </div>
        {activeTab === "goal" ? <div className="goal-mode-actions">
          <button type="button" className="icon-button" disabled={!canWriteGoal} onClick={() => { onEditModeChange(true); onTabChange("goal"); }} title={locale === "zh-CN" ? "编辑目标" : "Edit goal"} aria-label={locale === "zh-CN" ? "编辑目标" : "Edit goal"}>
            <Pencil size={14} strokeWidth={1.8} aria-hidden="true" />
          </button>
          {paused ? (
            <button type="button" className="icon-button" disabled={!canControl} onClick={onResume} title={locale === "zh-CN" ? "恢复目标" : "Resume goal"} aria-label={locale === "zh-CN" ? "恢复目标" : "Resume goal"}>
              <PlayCircle size={15} strokeWidth={1.8} aria-hidden="true" />
            </button>
          ) : (
            <button type="button" className="icon-button" disabled={!canControl} onClick={onPause} title={locale === "zh-CN" ? "暂停目标" : "Pause goal"} aria-label={locale === "zh-CN" ? "暂停目标" : "Pause goal"}>
              <PauseCircle size={15} strokeWidth={1.8} aria-hidden="true" />
            </button>
          )}
          <button type="button" className="icon-button" disabled={!canControl} onClick={onClear} title={locale === "zh-CN" ? "删除目标" : "Delete goal"} aria-label={locale === "zh-CN" ? "删除目标" : "Delete goal"}>
            <Trash2 size={14} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </div> : null}
      </div>

      <div className="goal-mode-details">
          {activeTab === "goal" ? (
            <div className="goal-mode-panel">
              {editMode || !hasGoal ? (
                <>
                  <textarea value={draft} onChange={(event) => onDraftChange(event.target.value)} rows={3} placeholder={locale === "zh-CN" ? "写下这个任务需要持续推进的目标。" : "Describe the goal this task should keep working toward."} />
                  <div className="goal-mode-panel-actions">
                    <button type="button" className="primary-button" disabled={!canWriteGoal || !draft.trim()} onClick={onSetActive}>
                      {locale === "zh-CN" ? "保存并恢复目标" : "Save and resume"}
                    </button>
                    {hasGoal ? (
                      <button type="button" className="ghost-button" onClick={() => onEditModeChange(false)}>
                        {locale === "zh-CN" ? "取消" : "Cancel"}
                      </button>
                    ) : null}
                  </div>
                </>
              ) : (
                <>
                  <p>{goal?.objective}</p>
                  <div className="goal-mode-facts">
                    <span>{locale === "zh-CN" ? "状态" : "Status"} <strong>{statusText}</strong></span>
                    <span>{locale === "zh-CN" ? "Token" : "Tokens"} <strong>{goal?.tokensUsed ?? 0}{goal?.tokenBudget ? ` / ${goal.tokenBudget}` : ""}</strong></span>
                    <span>{locale === "zh-CN" ? "用时" : "Time"} <strong>{goal?.timeUsedSeconds ? formatDuration(goal.timeUsedSeconds * 1000) : "-"}</strong></span>
                  </div>
                </>
              )}
            </div>
          ) : null}

          {activeTab === "plan" ? (
            <div className="goal-mode-panel">
              {plan ? <PlanProgressTimeline plan={plan} /> : proposedPlanText ? <PlanRenderer text={proposedPlanText} locale={locale} compact /> : <p className="muted">{locale === "zh-CN" ? "当前还没有计划。" : "No plan yet."}</p>}
            </div>
          ) : null}
        </div>
    </section>
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
}: {
  locale: "en" | "zh-CN";
  supervisor?: RuntimeSupervisorState;
  fallback: { permission?: string };
}) {
  const environment = supervisor?.environment;
  const token = supervisor?.token;
  const git = environment?.git;
  const browser = supervisor?.browser;
  const runtimeError = supervisor?.runtime_error;
  const guardLevel = contextGuardLevel(token?.context_percent ?? 0);
  const contextLabel = token?.context_window ? `${token.context_percent}%` : "n/a";
  const browserHealthy = !isRecentBrowserSignal(browser) || !browser?.status || browser.status === "pass";
  const mcpStatus = environment?.mcp?.status;
  const mcpHealthy = !mcpStatus || ["ok", "pass", "listed"].includes(String(mcpStatus).toLowerCase());
  const gitDirty = Boolean(git?.is_repo && (git.changed_files > 0 || git.added > 0 || git.deleted > 0));
  const issueCount = Number(Boolean(runtimeError)) + Number(guardLevel !== "ok") + Number(!browserHealthy) + Number(!mcpHealthy) + Number(gitDirty);
  const healthy = issueCount === 0;
  return (
    <section className={`pane-section inspector-section compact-status-section environment-strip guard-${guardLevel}`} data-testid="status-environment-strip">
      {healthy ? (
        <div className="environment-strip-row environment-strip-wide environment-ok-row" data-testid="status-environment-ok">
          <span>{locale === "zh-CN" ? "环境" : "Environment"}</span>
          <strong>{locale === "zh-CN" ? "环境正常" : "Environment healthy"}</strong>
        </div>
      ) : (
        <div className="environment-strip-row environment-strip-wide environment-ok-row">
          <span>{locale === "zh-CN" ? "环境" : "Environment"}</span>
          <strong>{locale === "zh-CN" ? `${issueCount} 项异常已归入上方注意事项` : `${issueCount} issue${issueCount === 1 ? "" : "s"} listed above`}</strong>
        </div>
      )}
      <div className="environment-strip-row">
        <span>{t(locale, "inspector_permission")}</span>
        <strong>{environment?.permission || fallback.permission || "-"}</strong>
      </div>
      {guardLevel !== "ok" || token?.context_window ? (
        <div className="environment-strip-row">
          <span>{t(locale, "inspector_context")}</span>
          <strong>{contextLabel}</strong>
        </div>
      ) : null}
    </section>
  );
}

function RuntimeStatusSummary({
  locale,
  activeStatusType,
  waitingOnApproval,
  sending,
  queueCount,
  canInterrupt,
  goal,
}: {
  locale: LocaleCode;
  activeStatusType: string;
  waitingOnApproval: boolean;
  sending: boolean;
  queueCount: number;
  canInterrupt: boolean;
  goal: DisplayGoal | null;
}) {
  const state = runtimeStateLabel(locale, { waitingOnApproval, sending, activeStatusType });
  const goalLabel = goal ? goalStatusLabel(locale, goal.status, goal.source) : (locale === "zh-CN" ? "无目标" : "No goal");
  const facts = [
    queueCount > 0 ? { id: "queue", label: locale === "zh-CN" ? "排队" : "Queue", value: String(queueCount) } : null,
    canInterrupt ? { id: "interrupt", label: locale === "zh-CN" ? "中断" : "Interrupt", value: locale === "zh-CN" ? "可用" : "Ready" } : null,
    goal ? { id: "goal", label: locale === "zh-CN" ? "目标" : "Goal", value: goalLabel } : null,
  ].filter(Boolean) as Array<{ id: string; label: string; value: string }>;
  return (
    <section className="pane-section inspector-section compact-status-section" data-testid="runtime-status-summary">
      <div className="status-summary-headline">
        <span className="status-summary-label">{locale === "zh-CN" ? "运行状态" : "Runtime Status"}</span>
        <span className={`status-pill status-pill-${waitingOnApproval ? "warning" : activeStatusType === "active" || sending ? "active" : "idle"}`}>{state}</span>
      </div>
      {facts.length ? (
        <div className="status-inline-list">
          {facts.map((fact) => (
            <div className="status-inline-item" key={fact.id}>
              <span>{fact.label}</span>
              <strong>{fact.value}</strong>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function RuntimeAttentionPanel({
  locale,
  items,
}: {
  locale: LocaleCode;
  items: StatusAttentionItem[];
}) {
  const [expanded, setExpanded] = useState(false);
  if (!items.length) return null;
  const visibleItems = expanded ? items : items.slice(0, STATUS_NOTICE_PREVIEW_ITEMS);
  const hiddenCount = Math.max(items.length - visibleItems.length, 0);
  return (
    <section className="pane-section inspector-section compact-status-section" data-testid="runtime-attention-panel">
      <div className="section-header">
        <h2>{locale === "zh-CN" ? "需要注意" : "Needs Attention"}</h2>
        <div className="status-attention-header-actions">
          {hiddenCount > 0 ? (
            <button type="button" className="ghost-button compact-inline-button status-attention-toggle" onClick={() => setExpanded((value) => !value)}>
              {expanded
                ? (locale === "zh-CN" ? "收起" : "Collapse")
                : (locale === "zh-CN" ? `还有 ${hiddenCount} 条` : `${hiddenCount} more`)}
            </button>
          ) : null}
          <span className={`mini-guard mini-guard-${items.some((item) => item.severity === "danger") ? "danger" : "warning"}`}>
            {String(items.length)}
          </span>
        </div>
      </div>
      <div className="status-attention-list" role="list">
        {visibleItems.map((item) => (
          <div className={`status-attention-row status-attention-${item.severity}`} role="listitem" key={item.id}>
            <strong>{item.label}</strong>
            <span>{item.detail}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecoveryActionsPanel({
  locale,
  actions,
  pendingAction,
  onAction,
}: {
  locale: LocaleCode;
  actions: RuntimeErrorAction[];
  pendingAction: string | null;
  onAction: (action: RuntimeErrorAction) => void;
}) {
  if (!actions.length) return null;
  return (
    <section className="pane-section inspector-section compact-status-section" data-testid="runtime-recovery-panel">
      <div className="section-header">
        <h2>{locale === "zh-CN" ? "恢复操作" : "Recovery"}</h2>
      </div>
      <div className="inspector-actions inspector-actions-single recovery-action-list">
        {actions.map((action) => {
          const pending = pendingAction === action.action;
          return (
            <button
              key={`${action.action}:${action.target ?? ""}:${action.label}`}
              type="button"
              className="ghost-button"
              disabled={pending}
              onClick={() => onAction(action)}
            >
              {pending ? t(locale, "inspector_processing") : action.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function CompactGoalStatusPanel({
  locale,
  goal,
  draft,
  editMode,
  canWriteGoal,
  onDraftChange,
  onEditModeChange,
  onSetActive,
  onPauseResume,
  onClear,
}: {
  locale: LocaleCode;
  goal: DisplayGoal | null;
  draft: string;
  editMode: boolean;
  canWriteGoal: boolean;
  onDraftChange: (value: string) => void;
  onEditModeChange: (value: boolean) => void;
  onSetActive: () => void;
  onPauseResume: () => void;
  onClear: () => void;
}) {
  if (!goal && !editMode) return null;
  const status = goal ? goalStatusLabel(locale, goal.status, goal.source) : (locale === "zh-CN" ? "未设置目标" : "No goal");
  return (
    <section className="pane-section inspector-section compact-status-section" data-testid="status-panel-goal">
      <div className="section-header">
        <h2>{t(locale, "goal")}</h2>
        <button type="button" className="ghost-button compact-inline-button" onClick={() => onEditModeChange(!editMode)}>
          {editMode ? (locale === "zh-CN" ? "收起" : "Collapse") : (locale === "zh-CN" ? "编辑目标" : "Edit goal")}
        </button>
      </div>
      <div className="compact-goal-row">
        <strong>{status}</strong>
        <span>{goal?.objective || (locale === "zh-CN" ? "当前任务还没有目标。" : "This task has no goal.")}</span>
      </div>
      {editMode ? (
        <>
          <label className="field">
            <textarea aria-label={t(locale, "goal")} value={draft} onChange={(event) => onDraftChange(event.target.value)} rows={3} placeholder={t(locale, "goal_placeholder")} />
          </label>
          <div className="inspector-actions">
            <button type="button" className="primary-button" disabled={!canWriteGoal || !draft.trim()} onClick={onSetActive}>
              {t(locale, "goal_set")}
            </button>
            <button type="button" className="ghost-button" disabled={!canWriteGoal || !goal?.objective} onClick={onPauseResume}>
              {goal?.status === "active" ? (locale === "zh-CN" ? "暂停" : "Pause") : (locale === "zh-CN" ? "恢复" : "Resume")}
            </button>
            <button type="button" className="ghost-button" disabled={!canWriteGoal || goal?.source !== "thread"} onClick={onClear}>
              {t(locale, "goal_clear")}
            </button>
          </div>
        </>
      ) : null}
    </section>
  );
}

function CompactPlanStatusPanel({
  locale,
  plan,
  planText,
  expanded,
  onToggle,
}: {
  locale: LocaleCode;
  plan: RuntimeSupervisorState["plan"] | null;
  planText: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  if (!plan && !planText) return null;
  const stepCount = plan?.steps.length ?? 0;
  const completed = plan?.steps.filter((step) => String(step.status || "").toLowerCase() === "completed").length ?? 0;
  const summary = plan ? `${completed}/${stepCount}` : (locale === "zh-CN" ? "草稿计划" : "Draft plan");
  return (
    <section className="pane-section inspector-section compact-status-section" data-testid="status-panel-plan">
      <div className="section-header">
        <h2>{t(locale, "plan")}</h2>
        <button type="button" className="ghost-button compact-inline-button" onClick={onToggle}>
          {expanded ? (locale === "zh-CN" ? "收起" : "Collapse") : (locale === "zh-CN" ? "查看计划" : "View plan")}
        </button>
      </div>
      <div className="compact-goal-row">
        <strong>{summary}</strong>
        <span>{plan?.explanation || (locale === "zh-CN" ? "计划已准备。" : "Plan is available.")}</span>
      </div>
      {expanded ? (
        plan ? <PlanProgressTimeline plan={plan} /> : <PlanRenderer text={planText} locale={locale} compact />
      ) : null}
    </section>
  );
}

function StatusEvidencePanel({
  locale,
  items,
}: {
  locale: LocaleCode;
  items: StatusEvidenceItem[];
}) {
  if (!items.length) return null;
  return (
    <section className="pane-section inspector-section compact-status-section" data-testid="status-evidence-panel">
      <div className="status-evidence-list">
        {items.map((item) => (
          <div className="status-evidence-row" key={item.id}>
            <span>{item.label}</span>
            <strong title={item.detail || item.value}>{item.value}</strong>
          </div>
        ))}
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
          <button type="button" className="ghost-button" onClick={() => onDecision("fork")}>创建分支任务</button>
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

function useCompactShellViewport() {
  const [compact, setCompact] = useState(() => typeof window !== "undefined" && isCompactShellViewport(window.innerWidth));

  useEffect(() => {
    function syncViewport() {
      setCompact(isCompactShellViewport(window.innerWidth));
    }

    syncViewport();
    window.addEventListener("resize", syncViewport);
    return () => window.removeEventListener("resize", syncViewport);
  }, []);

  return compact;
}

function useComposerInputResize() {
  const [height, setHeight] = useState(() => clampComposerInputHeight(loadStoredNumber(COMPOSER_INPUT_HEIGHT_KEY, 112)));
  const draggingRef = useRef<null | { startY: number; startHeight: number }>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(COMPOSER_INPUT_HEIGHT_KEY, String(height));
  }, [height]);

  useEffect(() => {
    function onMove(event: PointerEvent) {
      if (!draggingRef.current) return;
      const deltaY = draggingRef.current.startY - event.clientY;
      setHeight(clampComposerInputHeight(draggingRef.current.startHeight + deltaY));
    }

    function onUp() {
      if (!draggingRef.current) return;
      draggingRef.current = null;
      document.body.classList.remove("composer-resizing");
    }

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, []);

  return {
    height,
    setHeightByDelta(delta: number) {
      setHeight((current) => clampComposerInputHeight(current + delta));
    },
    bind: {
      onPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
        event.preventDefault();
        draggingRef.current = { startY: event.clientY, startHeight: height };
        document.body.classList.add("composer-resizing");
      },
    },
  };
}

function RouterControlCenter({
  locale,
  queryClient,
  fallbackCheckpoints,
  initialTab = "login",
  initialExtensionsKind = "all",
  leftSidebarOpen,
  rightSidebarOpen,
  archivedVisible,
  onToggleLeftSidebar,
  onToggleRightSidebar,
  onOpenSearch,
  onOpenArchived,
  onReturnToChat,
  onCreateThread,
  onTabChange,
}: {
  locale: "en" | "zh-CN";
  queryClient: ReturnType<typeof useQueryClient>;
  fallbackCheckpoints: ProjectCheckpoint[];
  initialTab?: SetupTab;
  initialExtensionsKind?: ExtensionInventoryInitialKind;
  leftSidebarOpen: boolean;
  rightSidebarOpen: boolean;
  archivedVisible: boolean;
  onToggleLeftSidebar: () => void;
  onToggleRightSidebar: () => void;
  onOpenSearch: () => void;
  onOpenArchived: () => void;
  onReturnToChat: () => void;
  onCreateThread: () => void;
  onTabChange?: (tab: SetupTab) => void;
}) {
  const project = useAppStore((store) => store.project);
  const setProject = useAppStore((store) => store.setProject);
  const setLocale = useAppStore((store) => store.setLocale);
  const appearance = useAppStore((store) => store.appearance);
  const setAppearance = useAppStore((store) => store.setAppearance);
  const cursorEnhancement = useAppStore((store) => store.cursorEnhancement);
  const setCursorEnhancement = useAppStore((store) => store.setCursorEnhancement);
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
  const appHealth = useQuery({
    queryKey: ["app-health", project?.project_id],
    queryFn: api.health,
    enabled: Boolean(project?.project_id),
    refetchInterval: 15000,
    staleTime: 10000,
  });
  const [tab, setTab] = useState<SetupTab>(initialTab);
  const [extensionKind, setExtensionKind] = useState<ExtensionInventoryInitialKind>(initialExtensionsKind);
  const selectSetupTab = (nextTab: SetupTab, options?: { extensionKind?: ExtensionInventoryInitialKind }) => {
    if (options?.extensionKind) setExtensionKind(options.extensionKind);
    setTab(nextTab);
    onTabChange?.(nextTab);
  };
  useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);
  useEffect(() => {
    setExtensionKind(initialExtensionsKind);
  }, [initialExtensionsKind]);
  const capabilityArtifacts = useQuery({ queryKey: ["capability-artifacts"], queryFn: () => api.capabilityArtifacts(20), enabled: tab === "capabilities", refetchInterval: 10000, retry: false });
  const [providerDraft, setProviderDraft] = useState<RouterProvider | null>(null);
  const [modelDraft, setModelDraft] = useState<RouterModelEntry | null>(null);
  const [mcpDraft, setMcpDraft] = useState<McpServerConfig | null>(null);
  const [reasoningDraft, setReasoningDraft] = useState<ReasoningConfig | null>(null);
  const [importDraft, setImportDraft] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [managerUsername, setManagerUsername] = useState("");
  const [managerPassword, setManagerPassword] = useState("");
  const [managerNewPassword, setManagerNewPassword] = useState("");
  const [managerOldPassword, setManagerOldPassword] = useState("");
  const [managerDisplayName, setManagerDisplayName] = useState("");
  const [managerAvatarPath, setManagerAvatarPath] = useState("");
  const [managedKeyDraft, setManagedKeyDraft] = useState({ label: "", secret: "", env_key: "" });
  const [selectedKeyId, setSelectedKeyId] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState("");
  useEffect(() => {
    if (managerUsername.trim()) return;
    const preferred = llmSession.data?.preferred_username ?? llmSession.data?.users?.[0]?.username ?? "";
    if (preferred) setManagerUsername(preferred);
  }, [llmSession.data?.preferred_username, llmSession.data?.users, managerUsername]);
  const [capabilityRouteDrafts, setCapabilityRouteDrafts] = useState<Record<string, { mode: "auto" | "pinned"; provider_id?: string | null; model?: string | null }>>({});
  const [capabilitySmokeResults, setCapabilitySmokeResults] = useState<Record<string, CapabilitySmokeResult>>({});
  const mcpStatus = useQuery({ queryKey: ["mcp-status", selectedProviderId], queryFn: () => api.mcpStatus({ profile_id: selectedProviderId ? `${selectedProviderId}-default` : undefined, detail: "toolsAndAuthOnly" }), enabled: (tab === "mcp" || tab === "capabilities") && Boolean(selectedProviderId), refetchInterval: 7000, retry: false });
  const [wslSetupDistro, setWslSetupDistro] = useState("Ubuntu-24.04");
  const wslDependencies = useQuery({ queryKey: ["wsl-dependencies", wslSetupDistro], queryFn: () => api.wslDependencies(wslSetupDistro), refetchInterval: 15000, retry: false });
  const runtimeKernelProbe = useQuery({
    queryKey: ["runtime-kernel-probe", project?.project_id],
    queryFn: () => api.runtimeKernelProbe(),
    enabled: (tab === "runtime" || tab === "runtime_overview") && Boolean(project?.project_id),
    refetchInterval: 15000,
    retry: false,
  });
  const runtimePluginSkillRegistry = useQuery({
    queryKey: ["runtime-plugin-skill-registry", project?.project_id],
    queryFn: () => api.runtimePluginSkillRegistry(),
    enabled: (tab === "extensions" || tab === "capabilities" || tab === "tools") && Boolean(project?.project_id),
    refetchInterval: 15000,
    retry: false,
  });
  const [modelSearch, setModelSearch] = useState("");
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [managedKeyTestFeedback, setManagedKeyTestFeedback] = useState<ManagedKeyTestFeedback | null>(null);
  const [metadataOutput, setMetadataOutput] = useState<string>("");
  const [healthResultsExpanded, setHealthResultsExpanded] = useState(false);
  const [metadataRefreshJobId, setMetadataRefreshJobId] = useState<string | null>(null);
  const [mcpOutput, setMcpOutput] = useState<string>("");
  const [wslSetupOutput, setWslSetupOutput] = useState("");
  const [dogfoodDraft, setDogfoodDraft] = useState<DogfoodRun | null>(null);
  const [dogfoodSmokeUrl, setDogfoodSmokeUrl] = useState("http://127.0.0.1:8123/");
  const [dogfoodSmokeLabel, setDogfoodSmokeLabel] = useState("浏览器烟测");
  const [dogfoodScreenshotPath, setDogfoodScreenshotPath] = useState("");
  const [dogfoodMilestoneLabel, setDogfoodMilestoneLabel] = useState("里程碑");
  const [dogfoodMilestoneValidation, setDogfoodMilestoneValidation] = useState("浏览器烟测通过");
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
  const [automationOperationNotice, setAutomationOperationNotice] = useState<AutomationOperationNotice | null>(null);

  const invalidateAutomationQueries = () => {
    queryClient.invalidateQueries({ queryKey: ["automations", project?.project_id] });
    queryClient.invalidateQueries({ queryKey: ["automations-runs", project?.project_id] });
    queryClient.invalidateQueries({ queryKey: ["automations-inbox", project?.project_id] });
    queryClient.invalidateQueries({ queryKey: ["automations-scheduler", project?.project_id] });
    queryClient.invalidateQueries({ queryKey: ["runtime-supervisor"] });
  };
  const createAutomation = useMutation({ mutationFn: api.createAutomation });
  const updateAutomation = useMutation({
    mutationFn: ({ automationId, patch }: { automationId: string; patch: Record<string, unknown> }) => api.updateAutomation(automationId, patch),
  });
  const deleteAutomation = useMutation({ mutationFn: (automationId: string) => api.deleteAutomation(automationId) });
  const pauseAutomation = useMutation({ mutationFn: (automationId: string) => api.pauseAutomation(automationId) });
  const resumeAutomation = useMutation({ mutationFn: (automationId: string) => api.resumeAutomation(automationId) });
  const runAutomationNow = useMutation({ mutationFn: (automationId: string) => api.runAutomationNow(automationId) });
  const cancelAutomationRun = useMutation({ mutationFn: (runId: string) => api.cancelAutomationRun(runId) });
  const updateAutomationInboxItem = useMutation({
    mutationFn: ({ itemId, patch }: { itemId: string; patch: Record<string, unknown> }) => api.updateAutomationInboxItem(itemId, patch),
  });
  const promoteAutomationInboxItem = useMutation({
    mutationFn: ({ itemId, promotionRef }: { itemId: string; promotionRef: string }) => api.promoteAutomationInboxItem(itemId, promotionRef),
  });
  const resetAutomationMutationState = () => {
    createAutomation.reset();
    updateAutomation.reset();
    deleteAutomation.reset();
    pauseAutomation.reset();
    resumeAutomation.reset();
    runAutomationNow.reset();
    cancelAutomationRun.reset();
    updateAutomationInboxItem.reset();
    promoteAutomationInboxItem.reset();
  };
  const clearAutomationOperationState = () => {
    setAutomationOperationNotice(null);
    resetAutomationMutationState();
  };
  const syncAutomationRecord = (automation: AutomationSpec) => {
    queryClient.setQueryData<AutomationListResponse>(["automations", project?.project_id], (current) =>
      upsertAutomationListResponse(current, automation),
    );
  };
  const syncAutomationRun = (run: AutomationRun, scheduler?: AutomationSchedulerStatus | null) => {
    queryClient.setQueryData<AutomationRunsResponse>(["automations-runs", project?.project_id], (current) =>
      upsertAutomationRunsResponse(current, run),
    );
    queryClient.setQueryData<{ scheduler: AutomationSchedulerStatus }>(["automations-scheduler", project?.project_id], (current) => ({
      scheduler: scheduler ?? updateAutomationSchedulerAfterRun(current?.scheduler, run),
    }));
  };
  const syncAutomationInboxItem = (item: AutomationInboxItem) => {
    queryClient.setQueryData<AutomationInboxResponse>(["automations-inbox", project?.project_id], (current) =>
      upsertAutomationInboxResponse(current, item),
    );
  };
  const savedAutomationNotice = (automation: AutomationSpec): AutomationOperationNotice => ({
    tone: "success",
    title: locale === "zh-CN" ? "自动化已保存" : "Automation saved",
    detail: automation.name || automation.automation_id,
  });
  const runAutomationNotice = (run: AutomationRun): AutomationOperationNotice => ({
    tone: run.status === "failed" || run.status === "cancelled" ? "info" : "success",
    title:
      locale === "zh-CN"
        ? run.status === "completed"
          ? "自动化已完成"
          : run.status === "running" || run.status === "queued"
            ? "自动化已启动"
            : "自动化已记录"
        : run.status === "completed"
          ? "Automation completed"
          : run.status === "running" || run.status === "queued"
            ? "Automation started"
            : "Automation updated",
    detail: run.summary || run.run_id,
  });
  const automationErrorMessage = useMemo(() => {
    const mutationError =
      createAutomation.error ||
      updateAutomation.error ||
      deleteAutomation.error ||
      pauseAutomation.error ||
      resumeAutomation.error ||
      runAutomationNow.error ||
      cancelAutomationRun.error ||
      updateAutomationInboxItem.error ||
      promoteAutomationInboxItem.error;
    return mutationError ? String((mutationError as Error).message ?? mutationError) : null;
  }, [
    cancelAutomationRun.error,
    createAutomation.error,
    deleteAutomation.error,
    pauseAutomation.error,
    promoteAutomationInboxItem.error,
    resumeAutomation.error,
    runAutomationNow.error,
    updateAutomation.error,
    updateAutomationInboxItem.error,
  ]);
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
      setMcpOutput("AstraBridge Multimodal Capability Runtime installed. It exposes multimodal routes plus image, vision, speech transcribe, and speech synthesize tools through the current capability routing config.");
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
    onSuccess: (data) => {
      setManagerPassword("");
      if (data.session.username) setManagerUsername(data.session.username);
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
    onMutate: () => {
      setManagedKeyTestFeedback(null);
    },
    onSuccess: (data) => {
      const diagnosticsText = formatResponseDiagnostics(data.result.response_diagnostics);
      const failureText = runtimeErrorNoticeText(data.result.failure_notice ?? null);
      setManagedKeyTestFeedback(summarizeManagedKeyTest(data.result, diagnosticsText ?? failureText));
      queryClient.invalidateQueries({ queryKey: ["llm-manager-keys"] });
      queryClient.invalidateQueries({ queryKey: ["llm-manager-catalog"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    },
    onError: (error, variables) => {
      setManagedKeyTestFeedback(summarizeManagedKeyTestError(
        variables.provider_id,
        error instanceof Error ? error.message : "The app did not receive a usable health-test result.",
      ));
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
      invalidateRestoreStateQueries(queryClient);
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
  const pluginInventory = runtimePluginSkillRegistry.data;
  const pluginInventoryNoteMap = Object.fromEntries(
    (pluginInventory?.notes ?? [])
      .map((note) => {
        const text = String(note || "").trim();
        const separator = text.indexOf(":");
        return separator > 0 ? [text.slice(0, separator), text.slice(separator + 1)] : null;
      })
      .filter((entry): entry is [string, string] => Boolean(entry)),
  );
  const pluginListStatus = String(pluginInventoryNoteMap.plugin_list_status ?? (pluginInventory ? "supported" : "unknown"));
  const skillListStatus = String(pluginInventoryNoteMap.skill_list_status ?? (pluginInventory ? "supported" : "unknown"));
  const latestHealthResults = useMemo(
    () => (llmHealth.data?.results ?? []).slice(-12).reverse(),
    [llmHealth.data?.results],
  );
  const visibleHealthResults = healthResultsExpanded
    ? latestHealthResults
    : latestHealthResults.slice(0, 3);
  const hiddenHealthResultsCount = Math.max(
    latestHealthResults.length - visibleHealthResults.length,
    0,
  );
  useEffect(() => {
    setHealthResultsExpanded(false);
  }, [llmHealth.data?.updated_at, llmHealth.data?.results?.length]);
  const fileLandingMetrics: SetupLandingMetric[] = [
    {
      id: "tasks",
      label: locale === "zh-CN" ? "当前任务" : "Current tasks",
      value: String(project?.recent_tasks?.length ?? (project?.current_task_id ? 1 : 0)),
    },
    {
      id: "saves",
      label: locale === "zh-CN" ? "检查点" : "Checkpoints",
      value: String(visibleCheckpoints.length),
    },
    {
      id: "captures",
      label: locale === "zh-CN" ? "截图" : "Captures",
      value: String(dogfoodRun.data?.run?.captures.length ?? 0),
    },
    {
      id: "boundary",
      label: locale === "zh-CN" ? "项目状态" : "Project state",
      value: project?.project_file ? ".abproj" : (locale === "zh-CN" ? "未打开" : "none"),
    },
  ];
  const fileLandingActions: SetupLandingAction[] = [
    {
      id: "new-task",
      icon: <MessageSquareText size={15} />,
      title: locale === "zh-CN" ? "新建任务" : "Create task",
      detail: locale === "zh-CN" ? "保持在当前项目内启动新的任务窗口。" : "Start a fresh task inside the current project.",
      status: locale === "zh-CN" ? "当前项目" : "current project",
      actionLabel: locale === "zh-CN" ? "创建" : "Create",
      onClick: onCreateThread,
    },
    {
      id: "saves",
      icon: <Save size={15} />,
      title: t(locale, "setup_tab_saves"),
      detail: locale === "zh-CN" ? "查看本地检查点、预览可载入状态，并保持 Git 只读。" : "Inspect local checkpoints and preview restore state without mutating Git.",
      status: `${visibleCheckpoints.length}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("saves"),
    },
    {
      id: "reports",
      icon: <ClipboardCopy size={15} />,
      title: t(locale, "setup_tab_reports"),
      detail: locale === "zh-CN" ? "查看项目内的验收记录、截图登记和导出报告。" : "Inspect project-local acceptance records, captures, and exportable reports.",
      status: locale === "zh-CN" ? "项目内" : "project local",
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("reports"),
    },
    {
      id: "chat",
      icon: <FileIcon size={15} />,
      title: locale === "zh-CN" ? "返回任务窗口" : "Return to task window",
      detail: locale === "zh-CN" ? "离开文件落地页，回到当前任务会话。" : "Leave the file landing page and return to the active task window.",
      status: locale === "zh-CN" ? "主画布" : "main canvas",
      actionLabel: locale === "zh-CN" ? "返回" : "Return",
      onClick: onReturnToChat,
    },
  ];
  const toolsLandingMetrics: SetupLandingMetric[] = [
    {
      id: "plugins",
      label: locale === "zh-CN" ? "插件" : "Plugins",
      value: String(pluginInventory?.plugins.length ?? 0),
    },
    {
      id: "skills",
      label: locale === "zh-CN" ? "技能" : "Skills",
      value: String(pluginInventory?.skills.length ?? 0),
    },
    {
      id: "automations",
      label: locale === "zh-CN" ? "自动化" : "Automations",
      value: String(automations.data?.automations.length ?? 0),
    },
    {
      id: "web",
      label: locale === "zh-CN" ? "联网" : "Web",
      value: skillListStatus === "supported"
        ? (locale === "zh-CN" ? "已接线" : "wired")
        : (locale === "zh-CN" ? "待检查" : "check"),
    },
  ];
  const toolsLandingActions: SetupLandingAction[] = [
    {
      id: "plugins",
      icon: <Settings size={15} />,
      title: locale === "zh-CN" ? "插件与扩展" : "Plugins and extensions",
      detail: locale === "zh-CN" ? "查看插件清单、来源、安装计划和项目预设。" : "Inspect plugin inventory, source boundaries, install plans, and project presets.",
      status: `${pluginInventory?.plugins.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("extensions", { extensionKind: "plugins" }),
    },
    {
      id: "skills",
      icon: <Bot size={15} />,
      title: locale === "zh-CN" ? "技能" : "Skills",
      detail: locale === "zh-CN" ? "查看技能启用状态、挂载来源和受控任务证据。" : "Inspect skill enablement, ownership, and controlled-task evidence.",
      status: `${pluginInventory?.skills.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("extensions", { extensionKind: "skills" }),
    },
    {
      id: "automations",
      icon: <ListChecks size={15} />,
      title: t(locale, "setup_tab_automations"),
      detail: locale === "zh-CN" ? "管理计划任务、收件箱和调度器健康状态。" : "Manage scheduled tasks, inbox items, and scheduler health.",
      status: `${automations.data?.automations.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("automations"),
    },
    {
      id: "multimodal",
      icon: <ImageIcon size={15} />,
      title: t(locale, "setup_tab_capabilities"),
      detail: locale === "zh-CN" ? "配置多模态能力路由、烟测与产物检查。" : "Configure multimodal routes, smoke tests, and generated artifacts.",
      status: `${capabilityManagement.data?.capabilities.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("capabilities"),
    },
    {
      id: "web",
      icon: <CircleHelp size={15} />,
      title: t(locale, "setup_tab_web"),
      detail: locale === "zh-CN" ? "执行联网搜索、研究摘要和来源检查。" : "Run web search, research briefs, and source inspection.",
      status: locale === "zh-CN" ? "独立通道" : "dedicated lane",
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("web"),
    },
    {
      id: "dogfood",
      icon: <ClipboardCopy size={15} />,
      title: t(locale, "setup_tab_dogfood"),
      detail: locale === "zh-CN" ? "进入真实狗粮运行台账、预算和截图监督界面。" : "Open the real dogfood ledger for budgets, captures, and execution supervision.",
      status: dogfoodRun.data?.run?.enabled ? (locale === "zh-CN" ? "运行中" : "active") : (locale === "zh-CN" ? "空闲" : "idle"),
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("dogfood"),
    },
  ];
  const runtimeLandingMetrics: SetupLandingMetric[] = [
    {
      id: "runtime",
      label: locale === "zh-CN" ? "运行时" : "Runtime",
      value: wslDependencies.data?.ok ? (locale === "zh-CN" ? "已就绪" : "ready") : (locale === "zh-CN" ? "待设置" : "setup"),
    },
    {
      id: "audit",
      label: locale === "zh-CN" ? "隔离检查" : "Isolation audit",
      value: `${isolationSummary.passed}/${isolationSummary.total}`,
    },
    {
      id: "mcp",
      label: "MCP",
      value: String(mcpConfig.data?.servers.length ?? 0),
    },
    {
      id: "kernel",
      label: locale === "zh-CN" ? "内核探测" : "Kernel probe",
      value: runtimeKernelProbe.data?.inferred.compatibility_status
        ? String(runtimeKernelProbe.data.inferred.compatibility_status)
        : (locale === "zh-CN" ? "待验证" : "pending"),
    },
  ];
  const runtimeLandingActions: SetupLandingAction[] = [
    {
      id: "runtime",
      icon: <Settings size={15} />,
      title: t(locale, "setup_tab_runtime"),
      detail: locale === "zh-CN" ? "检查 WSL 依赖、隔离状态和运行时脚本。" : "Check WSL dependencies, isolation state, and runtime installer scripts.",
      status: wslDependencies.data?.ok ? (locale === "zh-CN" ? "已就绪" : "ready") : (locale === "zh-CN" ? "待设置" : "setup"),
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("runtime"),
    },
    {
      id: "mcp",
      icon: <Bot size={15} />,
      title: t(locale, "setup_tab_mcp"),
      detail: locale === "zh-CN" ? "查看 MCP 服务器、暴露工具和预设安装状态。" : "Inspect MCP servers, exposed tools, and preset install state.",
      status: `${mcpConfig.data?.servers.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("mcp"),
    },
    {
      id: "health",
      icon: <ListChecks size={15} />,
      title: t(locale, "setup_tab_health"),
      detail: locale === "zh-CN" ? "运行密钥、提供方和模型健康检查，收敛恢复入口。" : "Run key, provider, and model health checks with recovery-oriented output.",
      status: `${llmHealth.data?.results.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("health"),
    },
    {
      id: "chat",
      icon: <MessageSquareText size={15} />,
      title: locale === "zh-CN" ? "返回任务窗口" : "Return to task window",
      detail: locale === "zh-CN" ? "退出运行时落地页，回到当前任务会话。" : "Leave the runtime landing page and return to the active task window.",
      status: locale === "zh-CN" ? "主画布" : "main canvas",
      actionLabel: locale === "zh-CN" ? "返回" : "Return",
      onClick: onReturnToChat,
    },
  ];
  const settingsLandingMetrics: SetupLandingMetric[] = [
    {
      id: "mode",
      label: locale === "zh-CN" ? "登录模式" : "Session mode",
      value: managerMode === "managed_user" ? (locale === "zh-CN" ? "托管密钥库" : "managed") : managerMode,
    },
    {
      id: "users",
      label: locale === "zh-CN" ? "用户" : "Users",
      value: String(llmSession.data?.users.length ?? 0),
    },
    {
      id: "keys",
      label: locale === "zh-CN" ? "密钥" : "Keys",
      value: String(llmSession.data?.key_count ?? 0),
    },
    {
      id: "providers",
      label: locale === "zh-CN" ? "提供方" : "Providers",
      value: String(routerConfig.data?.providers.length ?? 0),
    },
  ];
  const settingsLandingActions: SetupLandingAction[] = [
    {
      id: "login",
      icon: <Unlock size={15} />,
      title: t(locale, "provider_keys"),
      detail: locale === "zh-CN" ? "进入登录、托管密钥库和当前会话状态入口。" : "Open login, managed vault, and current session controls.",
      status: managerStatusLabel,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("login"),
    },
    {
      id: "users",
      icon: <Bot size={15} />,
      title: t(locale, "setup_tab_users"),
      detail: locale === "zh-CN" ? "管理托管账号、显示名、头像和密码。" : "Manage managed users, display names, avatars, and passwords.",
      status: `${llmSession.data?.users.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("users"),
    },
    {
      id: "keys",
      icon: <Save size={15} />,
      title: t(locale, "setup_tab_keys"),
      detail: locale === "zh-CN" ? "检查 provider key、托管密钥可用性和写入状态。" : "Inspect provider keys, managed key availability, and stored secret state.",
      status: `${llmSession.data?.key_count ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("keys"),
    },
    {
      id: "providers",
      icon: <Settings size={15} />,
      title: t(locale, "setup_tab_providers"),
      detail: locale === "zh-CN" ? "管理提供方、默认模型和适配器配置。" : "Manage providers, default models, and adapter settings.",
      status: `${routerConfig.data?.providers.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("providers"),
    },
    {
      id: "models",
      icon: <FileIcon size={15} />,
      title: t(locale, "setup_tab_models"),
      detail: locale === "zh-CN" ? "检查模型目录、上下文窗口和推荐状态。" : "Inspect model catalog entries, context windows, and recommendation state.",
      status: `${llmCatalog.data?.verified_model_ids.length ?? 0}`,
      actionLabel: locale === "zh-CN" ? "打开" : "Open",
      onClick: () => selectSetupTab("models"),
    },
  ];

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
    setManagedKeyTestFeedback(null);
    try {
      const result = await api.testProvider({ provider_id: sourceProvider.id, model_id: modelDraft?.id, stream });
      const diagnosticsText = formatResponseDiagnostics(result.response_diagnostics);
      const failureText = runtimeErrorNoticeText(result.failure_notice ?? null);
      setManagedKeyTestFeedback(summarizeManagedKeyTest(result, diagnosticsText ?? failureText));
      queryClient.invalidateQueries({ queryKey: ["router-config"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
    } catch (error) {
      setManagedKeyTestFeedback(summarizeManagedKeyTestError(
        sourceProvider.id,
        error instanceof Error ? error.message : "The app did not receive a usable provider-test result.",
      ));
    }
  }

  async function handleProviderVisionTest() {
    const sourceProvider = (routerConfig.data?.providers ?? []).find((provider) => provider.id === modelDraft?.provider) ?? providerDraft ?? selectedProvider;
    if (!sourceProvider) return;
    const sourceProfileId =
      (profiles.data?.profiles ?? []).find((profile) => {
        const providerId = profile.provider_id || profile.profile_id.replace(/-default$/, "");
        return providerId === sourceProvider.id;
      })?.profile_id ??
      `${sourceProvider.id}-default`;
    setManagedKeyTestFeedback(null);
    try {
      const result = await api.verifyAppServerImageRoute({
        provider_id: sourceProvider.id,
        model_id: modelDraft?.id,
        profile_id: sourceProfileId || undefined,
      });
      const diagnosticsText = formatResponseDiagnostics(result.response_diagnostics);
      const failureText = runtimeErrorNoticeText(result.failure_notice ?? null);
      setManagedKeyTestFeedback(summarizeManagedKeyTest(result, diagnosticsText ?? failureText));
      queryClient.invalidateQueries({ queryKey: ["router-config"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-environment"] });
      queryClient.invalidateQueries({ queryKey: ["effective-catalog"] });
    } catch (error) {
      setManagedKeyTestFeedback(summarizeManagedKeyTestError(
        sourceProvider.id,
        error instanceof Error ? error.message : "The app did not receive a usable vision-test result.",
      ));
    }
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
      description: "Multimodal routes for image generation, vision, speech transcription, and speech synthesis.",
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
  const automationProfiles = useMemo(() => {
    const loadedProviders = new Set(
      (appHealth.data?.runtime.router?.providers ?? [])
        .filter((provider) => provider.secret_loaded)
        .map((provider) => provider.provider_id),
    );
    return [...(profiles.data?.profiles ?? [])].sort((left, right) => {
      const rightLoaded = loadedProviders.has(String(right.provider_id || "")) ? 1 : 0;
      const leftLoaded = loadedProviders.has(String(left.provider_id || "")) ? 1 : 0;
      if (rightLoaded !== leftLoaded) return rightLoaded - leftLoaded;
      return String(left.label || left.profile_id || "").localeCompare(String(right.label || right.profile_id || ""));
    });
  }, [appHealth.data?.runtime.router?.providers, profiles.data?.profiles]);
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
  const isApiManagerTab = API_MANAGER_TABS.includes(tab);

  return (
    <section className={isApiManagerTab ? "settings-shell starbridge-surface-frame" : "settings-shell settings-shell-single starbridge-surface-frame"}>
      {isApiManagerTab ? (
      <aside className="settings-nav" aria-label={t(locale, "provider_model_settings")}>
        <div className="settings-nav-heading">
          <span className="eyebrow">{t(locale, "provider_model_settings")}</span>
          <strong>{managerStatusLabel}</strong>
          <small>{t(locale, "manager_nav_summary")}</small>
        </div>
        <div className="settings-nav-list">
          {API_MANAGER_TABS.map((item) => (
            <button
              key={item}
              type="button"
              data-testid={`setup-tab-${item}`}
              className={tab === item ? "settings-nav-item active" : "settings-nav-item"}
              onClick={() => selectSetupTab(item)}
            >
              <span>{t(locale, `setup_tab_${item}`)}</span>
            </button>
          ))}
        </div>
      </aside>
      ) : null}
      <div className="settings-content">
      <StarbridgeCornerConstellation variant="settings" />

      {tab === "file" ? (
        <SetupLandingPanel
          testId="file-landing-panel"
          eyebrow={locale === "zh-CN" ? "项目文件" : "Project files"}
          title={locale === "zh-CN" ? "文件" : "File"}
          summary={locale === "zh-CN"
            ? "把新建任务、检查点和项目报告放到一个清晰入口里。这里是文件类操作的落地页。"
            : "Gather task creation, checkpoints, and project reports in one clear landing page for file-oriented actions."}
          stateLabel={locale === "zh-CN" ? "当前状态" : "Current state"}
          stateItems={fileLandingMetrics}
          sectionTitle={locale === "zh-CN" ? "快速操作" : "Quick actions"}
          actions={fileLandingActions}
        />
      ) : null}

      {tab === "view" ? (
        <ViewWorkspacePanel
          locale={locale}
          leftSidebarOpen={leftSidebarOpen}
          rightSidebarOpen={rightSidebarOpen}
          archivedVisible={archivedVisible}
          onOpenSearch={onOpenSearch}
          onOpenArchived={onOpenArchived}
          onReturnToChat={onReturnToChat}
          onToggleLeftSidebar={onToggleLeftSidebar}
          onToggleRightSidebar={onToggleRightSidebar}
        />
      ) : null}

      {tab === "tools" ? (
        <SetupLandingPanel
          testId="tools-landing-panel"
          eyebrow={locale === "zh-CN" ? "能力入口" : "Capability entry"}
          title={locale === "zh-CN" ? "工具" : "Tools"}
          summary={locale === "zh-CN"
            ? "统一承接插件、技能、自动化、联网和多模态能力入口。先进入这里，再按需展开子菜单。"
            : "Use this landing page as the shared entry for plugins, skills, automations, web, and multimodal tools before drilling into submenu items."}
          stateLabel={locale === "zh-CN" ? "当前状态" : "Current state"}
          stateItems={toolsLandingMetrics}
          sectionTitle={locale === "zh-CN" ? "快速操作" : "Quick actions"}
          actions={toolsLandingActions}
        />
      ) : null}

      {tab === "runtime_overview" ? (
        <SetupLandingPanel
          testId="runtime-landing-panel"
          eyebrow={locale === "zh-CN" ? "运行边界" : "Runtime boundary"}
          title={locale === "zh-CN" ? "运行时" : "Runtime"}
          summary={locale === "zh-CN"
            ? "把运行时设置、MCP 和健康检查收拢成一个落地页。先看整体状态，再进入具体诊断页。"
            : "Use this landing page to orient runtime setup, MCP, and health checks before opening a specific diagnostic surface."}
          stateLabel={locale === "zh-CN" ? "当前状态" : "Current state"}
          stateItems={runtimeLandingMetrics}
          sectionTitle={locale === "zh-CN" ? "快速操作" : "Quick actions"}
          actions={runtimeLandingActions}
        />
      ) : null}

      {tab === "settings_overview" ? (
        <>
          <SetupLandingPanel
            testId="settings-landing-panel"
            eyebrow={locale === "zh-CN" ? "提供方与密钥" : "Providers and keys"}
            title={locale === "zh-CN" ? "设置" : "Settings"}
            summary={locale === "zh-CN"
              ? "把登录、用户、密钥、提供方和模型入口收在这里，避免一级菜单直接把你丢到某个细页。"
              : "Use this landing page for login, users, keys, providers, and models instead of jumping directly into a detailed subpage."}
            stateLabel={locale === "zh-CN" ? "当前状态" : "Current state"}
            stateItems={settingsLandingMetrics}
            sectionTitle={locale === "zh-CN" ? "快速操作" : "Quick actions"}
            actions={settingsLandingActions}
          />
          <section className="manager-section">
            <h4>{locale === "zh-CN" ? "交互偏好" : "Interaction preferences"}</h4>
            <div className="settings-strip">
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
              <div className="settings-strip-section">
                <strong>{t(locale, "cursor_enhancement")}</strong>
                <div className="segmented">
                  {(["auto", "off"] as CursorEnhancementPreference[]).map((item) => (
                    <button key={item} type="button" className={cursorEnhancement === item ? "segmented-active" : ""} onClick={() => setCursorEnhancement(item)}>
                      {t(locale, `cursor_enhancement_${item}`)}
                    </button>
                  ))}
                </div>
                <p className="muted compact-copy">{t(locale, cursorEnhancement === "off" ? "cursor_enhancement_hint_off" : "cursor_enhancement_hint_auto")}</p>
              </div>
            </div>
          </section>
        </>
      ) : null}

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
              <label className="field"><span>{t(locale, "manager_login_username")}</span><select value={managerUsername} onChange={(event) => setManagerUsername(event.target.value)} disabled={(llmSession.data?.users ?? []).length === 0}><option value="" disabled>{locale === "zh-CN" ? "选择托管用户" : "Choose a managed user"}</option>{(llmSession.data?.users ?? []).map((user) => <option key={user.username} value={user.username}>{user.display_name || user.username}</option>)}</select></label>
              <label className="field"><span>{t(locale, "manager_login_password")}</span><input type="password" autoComplete="current-password" data-sensitive-field="true" value={managerPassword} onChange={(event) => setManagerPassword(event.target.value)} placeholder={t(locale, "manager_login_password_placeholder")} /></label>
              <div className="field-row">
                <button type="button" className="primary-button" disabled={!managerUsername.trim() || !managerPassword.trim() || loginManager.isPending} onClick={() => loginManager.mutate({ mode: "managed_user", username: managerUsername, password: managerPassword })}>{t(locale, "manager_login_button")}</button>
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
          <div className="manager-hero">
            <div>
              <span className="eyebrow">{t(locale, "manager_users_title")}</span>
              <h3>{locale === "zh-CN" ? "用户与资料" : "Users and profile"}</h3>
              <p className="muted compact-copy">{locale === "zh-CN" ? "集中管理托管用户、显示名、头像和密码。" : "Manage vault users, display identity, avatar, and password from one shared surface."}</p>
            </div>
            <span className={`session-badge session-badge-${managerMode}`}>{llmSession.data?.users.length ?? 0}</span>
          </div>
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
              <label className="field"><span>{t(locale, "manager_user_new_password")}</span><input type="password" autoComplete="new-password" data-sensitive-field="true" value={managerPassword} onChange={(event) => setManagerPassword(event.target.value)} /></label>
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
              <label className="field"><span>{t(locale, "manager_password_old")}</span><input type="password" autoComplete="current-password" data-sensitive-field="true" value={managerOldPassword} onChange={(event) => setManagerOldPassword(event.target.value)} /></label>
              <label className="field"><span>{t(locale, "manager_password_new")}</span><input type="password" autoComplete="new-password" data-sensitive-field="true" value={managerNewPassword} onChange={(event) => setManagerNewPassword(event.target.value)} /></label>
              <button type="button" className="primary-button" disabled={!managerOldPassword.trim() || !managerNewPassword.trim()} onClick={() => changeManagerPassword.mutate({ username: managerUsername, old_password: managerOldPassword, new_password: managerNewPassword })}>{t(locale, "manager_password_change")}</button>
              {changeManagerPassword.error ? <p className="error-text">{String(changeManagerPassword.error as Error)}</p> : null}
            </section>
          </div>
        </div>
      ) : null}

      {tab === "providers" ? (
        <div className="manager-panel">
          <div className="manager-hero">
            <div>
              <span className="eyebrow">{t(locale, "setup_tab_providers")}</span>
              <h3>{locale === "zh-CN" ? "提供方目录" : "Provider catalog"}</h3>
              <p className="muted compact-copy">{locale === "zh-CN" ? "统一维护路由提供方、默认模型、适配器和品牌展示元数据。" : "Manage routing providers, default models, adapters, and branded metadata from one catalog."}</p>
            </div>
            <span className="session-badge">{routerConfig.data?.providers.length ?? 0}</span>
          </div>
          <div className="metadata-editor metadata-editor-provider">
            <div className="metadata-list-pane">
              <div className="metadata-pane-head">
                <div>
                  <span className="eyebrow">{locale === "zh-CN" ? "提供方" : "Providers"}</span>
                  <strong>{locale === "zh-CN" ? "目录" : "Catalog"}</strong>
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
              </div>
              <div className="thread-list provider-thread-list">
                {(routerConfig.data?.providers ?? []).map((provider) => (
                  <button key={provider.id} type="button" className={providerDraft?.id === provider.id ? "thread-row thread-row-active" : "thread-row"} onClick={() => setProviderDraft(provider)}>
                    <strong>{provider.display_name}</strong>
                    <span>{provider.id} / {provider.default_model}</span>
                  </button>
                ))}
              </div>
            </div>
            {providerDraft ? (
              <div className="metadata-detail-pane">
                <div className="metadata-detail-header">
                  <div>
                    <span className="eyebrow">{t(locale, "setup_tab_providers")}</span>
                    <h3>{providerDraft.display_name || providerDraft.id || t(locale, "manager_provider_new")}</h3>
                  </div>
                  <div className="field-row">
                    <button type="button" className="primary-button" onClick={() => saveProvider.mutate(providerDraft)}>{t(locale, "manager_provider_save")}</button>
                    {providerDraft.id ? <button type="button" className="ghost-button" onClick={() => api.deleteProvider(providerDraft.id).then(() => queryClient.invalidateQueries({ queryKey: ["router-config"] }))}>{t(locale, "manager_delete")}</button> : null}
                  </div>
                </div>
                <div className="metadata-section">
                  <h4>{locale === "zh-CN" ? "连接与展示" : "Connection and presentation"}</h4>
                  <label className="field"><span>ID</span><input value={providerDraft.id} onChange={(event) => setProviderDraft({ ...providerDraft, id: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "provider_label")}</span><input value={providerDraft.display_name} onChange={(event) => setProviderDraft({ ...providerDraft, display_name: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "base_url")}</span><input value={providerDraft.base_url} onChange={(event) => setProviderDraft({ ...providerDraft, base_url: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_provider_adapter")}</span><select value={providerDraft.adapter_type} onChange={(event) => setProviderDraft({ ...providerDraft, adapter_type: event.target.value })}><option value="responses">responses</option><option value="chat">chat</option></select></label>
                  <label className="field"><span>{t(locale, "manager_provider_default_model")}</span><input value={providerDraft.default_model} onChange={(event) => setProviderDraft({ ...providerDraft, default_model: event.target.value })} /></label>
                  <label className="field"><span>{t(locale, "manager_provider_logo_source_url")}</span><input value={providerDraft.logo_source_url ?? ""} onChange={(event) => setProviderDraft({ ...providerDraft, logo_source_url: event.target.value })} placeholder={t(locale, "manager_provider_logo_source_placeholder")} /></label>
                  <label className="field"><span>{t(locale, "manager_provider_logo_asset_path")}</span><input value={providerDraft.logo_asset_path ?? ""} onChange={(event) => setProviderDraft({ ...providerDraft, logo_asset_path: event.target.value })} placeholder={t(locale, "manager_provider_logo_asset_placeholder")} /></label>
                  <label className="field"><span>{t(locale, "manager_provider_accent_color")}</span><input value={providerDraft.accent_color ?? ""} onChange={(event) => setProviderDraft({ ...providerDraft, accent_color: event.target.value })} placeholder="#1f2937" /></label>
                  <label className="field"><span>{t(locale, "manager_provider_logo_license_note")}</span><textarea rows={2} value={providerDraft.logo_license_note ?? ""} onChange={(event) => setProviderDraft({ ...providerDraft, logo_license_note: event.target.value })} /></label>
                </div>
              </div>
            ) : null}
          </div>
        </div>
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
            onRunProviderSmoke={(capabilityId) => runCapabilitySmoke.mutate({ capability_id: capabilityId, mode: "provider", allow_provider: true })}
          />
        </div>
      ) : null}

      {tab === "web" ? (
        <WebToolsPanel
          locale={locale}
          onSearchBatch={(payload) => api.webSearchBatch(payload)}
          onResearchBrief={(payload) => api.webResearchBrief(payload)}
        />
      ) : null}

      {tab === "models" ? (
        <div className="manager-panel">
          <div className="manager-hero">
            <div>
              <span className="eyebrow">{t(locale, "setup_tab_models")}</span>
              <h3>{locale === "zh-CN" ? "模型目录" : "Model catalog"}</h3>
              <p className="muted compact-copy">{locale === "zh-CN" ? "统一维护模型合同、上下文窗口、能力标记和推荐状态。" : "Manage model contracts, context windows, capability flags, and recommendation state in one catalog."}</p>
            </div>
            <span className="session-badge">{filteredModels.length}</span>
          </div>
          <div className="metadata-editor">
            <div className="metadata-list-pane">
              <div className="metadata-pane-head">
                <label className="field">
                  <span>{t(locale, "manager_model_search")}</span>
                  <input value={modelSearch} onChange={(event) => setModelSearch(event.target.value)} placeholder={t(locale, "manager_model_search_placeholder")} />
                </label>
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
            </div>
            {modelDraft ? (
              <div
                className="metadata-detail-pane"
                data-testid="metadata-model-detail-pane"
                tabIndex={0}
                aria-label={locale === "zh-CN" ? "模型契约编辑器，可滚动" : "Scrollable model contract editor"}
              >
              <div className="metadata-detail-header">
                <div>
                  <span className="eyebrow">{t(locale, "manager_model_contract")}</span>
                  <h3>{modelDraft.display_name || modelDraft.id || t(locale, "manager_model_new")}</h3>
                </div>
                <div className="field-row">
                  {modelDraft.input_modalities?.includes("image") ? (
                    <button
                      type="button"
                      className="icon-button"
                      aria-label={locale === "zh-CN" ? "验证图片输入路由" : "Verify image input route"}
                      title={locale === "zh-CN" ? "验证图片输入路由" : "Verify image input route"}
                      onClick={handleProviderVisionTest}
                    >
                      <ImageIcon aria-hidden="true" size={15} />
                    </button>
                  ) : null}
                  {managedKeyTestFeedback ? (
                    <span
                      className={`session-badge session-badge-${managedKeyTestFeedback.tone === "success" ? "managed_user" : "anonymous"}`}
                      title={`${managedKeyTestFeedback.title}\n${managedKeyTestFeedback.diagnostic}\n${managedKeyTestFeedback.nextAction}`}
                    >
                      {managedKeyTestFeedback.tone === "success"
                        ? (locale === "zh-CN" ? "视觉通过" : "Vision passed")
                        : (locale === "zh-CN" ? "视觉失败" : "Vision failed")}
                    </span>
                  ) : null}
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
          <McpToolDiagnosticsPanel
            locale={locale}
            status={mcpStatus.data}
            isLoading={mcpStatus.isLoading || mcpStatus.isFetching}
            error={mcpStatus.error}
            profileId={selectedProviderId ? `${selectedProviderId}-default` : undefined}
            onCallTool={(payload) => api.callMcpTool(payload)}
          />
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
            initialKind={extensionKind}
            onProjectChanged={(nextProject) => setProject(nextProject)}
            onRegistryChanged={async () => {
              const result = await runtimePluginSkillRegistry.refetch();
              if (result.error) {
                throw result.error;
              }
            }}
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
          {wslDependencies.error ? (
            <p className="error-text">
              <strong>{t(locale, "manager_runtime_dependency_check_failed")}</strong>
              <span>{t(locale, "manager_runtime_dependency_check_failed_hint")}</span>
              <code>{String((wslDependencies.error as Error).message ?? wslDependencies.error)}</code>
            </p>
          ) : null}
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
                <span>{t(locale, "manager_runtime_sidecar_origin")} {isolationAudit.data.sidecar?.origin ?? isolationAudit.data.process_boundary.sidecar_origin ?? "unknown"}</span>
                <span>sidecar {isolationAudit.data.ports.sidecar ?? "n/a"}</span>
                <span>{t(locale, "manager_runtime_sidecar_owner")} {isolationAudit.data.sidecar?.port_owner?.pid ?? isolationAudit.data.ports.sidecar_owner_pid ?? "n/a"} {isolationAudit.data.sidecar?.port_owner?.status ?? isolationAudit.data.ports.sidecar_owner_status ?? ""}</span>
                <span>router {isolationAudit.data.ports.router ?? "n/a"}</span>
              </div>
              <div className="env-list">
                <div><span>{t(locale, "manager_runtime_launcher_mode")}</span><strong>{isolationAudit.data.sidecar?.launcher_mode ?? isolationAudit.data.process_boundary.sidecar_launcher_mode ?? "unknown"}</strong></div>
                <div><span>{t(locale, "manager_runtime_source_root")}</span><strong>{isolationAudit.data.sidecar?.source_root || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_workspace_state")}</span><strong>{isolationAudit.data.paths.astrabridge_state || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_project_root")}</span><strong>{isolationAudit.data.paths.project_runtime_root || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_isolated_home")}</span><strong>{isolationAudit.data.paths.isolated_codex_home || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_downloads_root")}</span><strong>{isolationAudit.data.paths.downloads_root || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_caches_root")}</span><strong>{isolationAudit.data.paths.caches_root || "n/a"}</strong></div>
                <div><span>{t(locale, "manager_runtime_temp_root")}</span><strong>{isolationAudit.data.paths.tmp_root || "n/a"}</strong></div>
              </div>
              {isolationSummary.failed ? (
                <div className="manager-list runtime-audit-check-list">
                  {isolationSummary.failedChecks.slice(0, 8).map((check) => (
                    <div className="manager-row runtime-audit-check" key={check.name}>
                      <span className="runtime-audit-check-heading">
                        <strong>{check.name}</strong>
                        <small>{t(locale, "manager_runtime_check_failed")}</small>
                      </span>
                      <code className="runtime-audit-check-detail">{stringifyDetail(check.detail) || t(locale, "manager_runtime_no_detail")}</code>
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
          profiles={automationProfiles}
          automations={automations.data?.automations ?? []}
          runs={automationRuns.data?.runs ?? []}
          inboxItems={automationInbox.data?.items ?? []}
          scheduler={automationScheduler.data?.scheduler ?? null}
          supervisorAutomations={null}
          mcpPresetOptions={automationMcpPresetOptions}
          pluginSkillPresetOptions={automationPluginSkillPresetOptions}
          catalogModels={mergeComposerCatalogModels(llmSession.data?.mode, llmCatalog.data?.models ?? [], routerConfig.data?.models ?? [])}
          runtimeProviders={appHealth.data?.runtime.router?.providers ?? []}
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
          operationNotice={automationOperationNotice}
          errorMessage={automationErrorMessage}
          onCreate={(payload) => {
            clearAutomationOperationState();
            createAutomation.mutate(payload, {
              onSuccess: (response) => {
                syncAutomationRecord(response.automation);
                invalidateAutomationQueries();
                resetAutomationMutationState();
                setAutomationOperationNotice(savedAutomationNotice(response.automation));
              },
            });
          }}
          onUpdate={(automationId, patch) => {
            clearAutomationOperationState();
            updateAutomation.mutate(
              { automationId, patch },
              {
                onSuccess: (response) => {
                  syncAutomationRecord(response.automation);
                  invalidateAutomationQueries();
                  resetAutomationMutationState();
                  setAutomationOperationNotice(savedAutomationNotice(response.automation));
                },
              },
            );
          }}
          onDelete={(automationId) => {
            clearAutomationOperationState();
            deleteAutomation.mutate(automationId, {
              onSuccess: (response) => {
                syncAutomationRecord(response.automation);
                invalidateAutomationQueries();
                resetAutomationMutationState();
                setAutomationOperationNotice({
                  tone: "success",
                  title: locale === "zh-CN" ? "自动化已归档" : "Automation archived",
                  detail: response.automation.name || response.automation.automation_id,
                });
              },
            });
          }}
          onPause={(automationId) => {
            clearAutomationOperationState();
            pauseAutomation.mutate(automationId, {
              onSuccess: (response) => {
                syncAutomationRecord(response.automation);
                invalidateAutomationQueries();
                resetAutomationMutationState();
                setAutomationOperationNotice({
                  tone: "success",
                  title: locale === "zh-CN" ? "自动化已暂停" : "Automation paused",
                  detail: response.automation.name || response.automation.automation_id,
                });
              },
            });
          }}
          onResume={(automationId) => {
            clearAutomationOperationState();
            resumeAutomation.mutate(automationId, {
              onSuccess: (response) => {
                syncAutomationRecord(response.automation);
                invalidateAutomationQueries();
                resetAutomationMutationState();
                setAutomationOperationNotice({
                  tone: "success",
                  title: locale === "zh-CN" ? "自动化已恢复" : "Automation resumed",
                  detail: response.automation.name || response.automation.automation_id,
                });
              },
            });
          }}
          onRunNow={(automationId) => {
            clearAutomationOperationState();
            runAutomationNow.mutate(automationId, {
              onSuccess: (response) => {
                syncAutomationRun(response.run, response.scheduler);
                if (response.inbox_item) {
                  syncAutomationInboxItem(response.inbox_item);
                }
                invalidateAutomationQueries();
                resetAutomationMutationState();
                setAutomationOperationNotice(runAutomationNotice(response.run));
              },
            });
          }}
          onCancelRun={(runId) => {
            clearAutomationOperationState();
            cancelAutomationRun.mutate(runId, {
              onSuccess: (response) => {
                syncAutomationRun(response.run);
                invalidateAutomationQueries();
                resetAutomationMutationState();
                setAutomationOperationNotice({
                  tone: "success",
                  title: locale === "zh-CN" ? "运行已取消" : "Run cancelled",
                  detail: response.run.summary || response.run.run_id,
                });
              },
            });
          }}
          onMarkReviewed={(itemId) => {
            clearAutomationOperationState();
            updateAutomationInboxItem.mutate(
              { itemId, patch: { state: "reviewed" } },
              {
                onSuccess: (response) => {
                  syncAutomationInboxItem(response.item);
                  invalidateAutomationQueries();
                  resetAutomationMutationState();
                  setAutomationOperationNotice({
                    tone: "success",
                    title: locale === "zh-CN" ? "收件箱已标记" : "Inbox item updated",
                    detail: response.item.title || response.item.item_id,
                  });
                },
              },
            );
          }}
          onArchive={(itemId) => {
            clearAutomationOperationState();
            updateAutomationInboxItem.mutate(
              { itemId, patch: { state: "archived" } },
              {
                onSuccess: (response) => {
                  syncAutomationInboxItem(response.item);
                  invalidateAutomationQueries();
                  resetAutomationMutationState();
                  setAutomationOperationNotice({
                    tone: "success",
                    title: locale === "zh-CN" ? "收件箱已归档" : "Inbox item archived",
                    detail: response.item.title || response.item.item_id,
                  });
                },
              },
            );
          }}
          onPromote={(itemId, promotionRef) => {
            clearAutomationOperationState();
            promoteAutomationInboxItem.mutate(
              { itemId, promotionRef },
              {
                onSuccess: (response) => {
                  syncAutomationInboxItem(response.item);
                  invalidateAutomationQueries();
                  resetAutomationMutationState();
                  setAutomationOperationNotice({
                    tone: "success",
                    title: locale === "zh-CN" ? "条目已提升" : "Inbox item promoted",
                    detail: response.item.promotion_ref || response.item.title || response.item.item_id,
                  });
                },
              },
            );
          }}
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
                      <small>{save.project_name} / {save.thread_name || "任务"} / {formatMessageTime(save.created_at)}</small>
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
              <span className="eyebrow">{locale === "zh-CN" ? "狗粮运行" : "Dogfood Run"}</span>
              <h3>{activeDogfood?.enabled ? dogfoodPhaseLabel(locale, activeDogfood.phase) || (locale === "zh-CN" ? "运行中" : "active") : locale === "zh-CN" ? "未启用" : "Not active"}</h3>
              <p className="muted">{locale === "zh-CN" ? "项目内的自治运行监督台账。用于记录预算、截图、阻塞和下一步，数据只写入 .astrabridge。" : "Project-local supervision ledger for autonomous model runs. It records budgets, screenshots, blockers, and next steps under .astrabridge only."}</p>
            </div>
            <span className={`session-badge ${activeDogfood?.enabled ? "capability-ok" : ""}`}>{dogfoodStatusLabel(locale, activeDogfood?.status)}</span>
          </div>
          <DogfoodLedgerSummary locale={locale} />
          {activeDogfood ? (
            <div className="manager-grid">
              <section className="manager-section">
                <h4>{locale === "zh-CN" ? "运行控制" : "Run control"}</h4>
                <div className="check-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={activeDogfood.enabled}
                      onChange={(event) => setDogfoodDraft({ ...activeDogfood, enabled: event.target.checked })}
                    />
                    {locale === "zh-CN" ? "启用" : "Enabled"}
                  </label>
                </div>
                <label className="field"><span>{locale === "zh-CN" ? "目标" : "Goal"}</span><textarea rows={3} value={activeDogfood.goal} onChange={(event) => setDogfoodDraft({ ...activeDogfood, goal: event.target.value })} /></label>
                <div className="form-grid">
                  <label className="field"><span>{locale === "zh-CN" ? "阶段" : "Phase"}</span><input value={dogfoodPhaseLabel(locale, activeDogfood.phase)} onChange={(event) => setDogfoodDraft({ ...activeDogfood, phase: event.target.value })} placeholder={locale === "zh-CN" ? "例如：自治能力加固" : "for example: autonomy hardening"} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "状态" : "Status"}</span><select value={activeDogfood.status} onChange={(event) => setDogfoodDraft({ ...activeDogfood, status: event.target.value })}><option value="idle">{dogfoodStatusLabel(locale, "idle")}</option><option value="running">{dogfoodStatusLabel(locale, "running")}</option><option value="waiting">{dogfoodStatusLabel(locale, "waiting")}</option><option value="blocked">{dogfoodStatusLabel(locale, "blocked")}</option><option value="complete">{dogfoodStatusLabel(locale, "complete")}</option></select></label>
                  <label className="field"><span>{locale === "zh-CN" ? "当前提供方" : "Current provider"}</span><input value={activeDogfood.current_provider} onChange={(event) => setDogfoodDraft({ ...activeDogfood, current_provider: event.target.value })} placeholder="deepseek / kimi / yunwu_image" /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "预警百分比" : "Warn percent"}</span><input type="number" value={activeDogfood.budgets.warn_percent} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, warn_percent: Number(event.target.value) || 80 } })} /></label>
                </div>
                <label className="field"><span>{locale === "zh-CN" ? "阻塞" : "Blocker"}</span><textarea rows={2} value={activeDogfood.blocker} onChange={(event) => setDogfoodDraft({ ...activeDogfood, blocker: event.target.value })} /></label>
                <label className="field"><span>{locale === "zh-CN" ? "下一步" : "Next step"}</span><textarea rows={2} value={activeDogfood.next_step} onChange={(event) => setDogfoodDraft({ ...activeDogfood, next_step: event.target.value })} /></label>
                <div className="field-row">
                  <button type="button" className="primary-button" disabled={saveDogfood.isPending} onClick={() => saveDogfood.mutate(activeDogfood)}>{locale === "zh-CN" ? "保存运行" : "Save run"}</button>
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
                    {locale === "zh-CN" ? "使用塔防游戏默认值" : "Use tower-game defaults"}
                  </button>
                </div>
                {saveDogfood.error ? <p className="error-text">{String(saveDogfood.error as Error)}</p> : null}
                <p className="muted">{locale === "zh-CN" ? "台账路径" : "Ledger path"}: {dogfoodRun.data?.path ?? ""}</p>
              </section>
              <section className="manager-section">
                <h4>{locale === "zh-CN" ? "资源记忆" : "Asset memory"}</h4>
                <p className="muted">{locale === "zh-CN" ? "生成和切片后的资源会作为项目记忆追踪，并在后续 DS/Kimi/Yunwu 轮次中以紧凑上下文包注入。" : "Generated and sliced assets are tracked as project memory, then auto-injected into future DS/Kimi/Yunwu turns as a compact context pack."}</p>
                <div className="dogfood-summary-list" aria-label={locale === "zh-CN" ? "资源摘要" : "Asset summary"}>
                  <div className="dogfood-summary-row"><span>{locale === "zh-CN" ? "资源总数" : "Total assets"}</span><strong>{assetSummaryCount(assetSummary, "total")}</strong></div>
                  <div className="dogfood-summary-row"><span>{locale === "zh-CN" ? "已进入游戏" : "In game"}</span><strong>{assetSummaryCount(assetSummary, "promoted_or_in_use")}</strong></div>
                  <div className="dogfood-summary-row"><span>{locale === "zh-CN" ? "已通过未使用" : "Approved, not used"}</span><strong>{assetSummaryCount(assetSummary, "approved_unpromoted")}</strong></div>
                  <div className="dogfood-summary-row"><span>{locale === "zh-CN" ? "需要复核" : "Needs review"}</span><strong>{assetSummaryCount(assetSummary, "needs_review")}</strong></div>
                </div>
                <div className="field-row">
                  <button type="button" className="ghost-button" onClick={() => rebuildDogfoodAssets.mutate()} disabled={rebuildDogfoodAssets.isPending}>{locale === "zh-CN" ? "重建登记表" : "Rebuild registry"}</button>
                  <span className="muted">{assetRegistry?.rebuilt_at ? `${locale === "zh-CN" ? "已重建" : "rebuilt"} ${summarizeRelativeTime(assetRegistry.rebuilt_at)}` : locale === "zh-CN" ? "尚未构建登记表" : "registry not built"}</span>
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
                  {assetRegistry && assetRegistry.assets.length === 0 ? <p className="muted">{locale === "zh-CN" ? "还没有登记生成或切片资源。" : "No generated or sliced assets registered yet."}</p> : null}
                  {dogfoodAssets.error ? <p className="error-text">{String((dogfoodAssets.error as Error).message ?? dogfoodAssets.error)}</p> : null}
                </div>
                <div className="form-grid">
                  <label className="field"><span>{locale === "zh-CN" ? "资源 ID" : "Asset ID"}</span><input value={assetPromoteDraft.asset_id} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, asset_id: event.target.value })} placeholder="yunwu-..._heroine_fullbody_000" /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "目标文件" : "Target file"}</span><input value={assetPromoteDraft.target_name} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, target_name: event.target.value })} placeholder="heroine_walk_down_0.png" /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "清单分区" : "Manifest section"}</span><select value={assetPromoteDraft.manifest_section} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, manifest_section: event.target.value as "sprites" | "tiles" | "hud" })}><option value="sprites">{manifestSectionLabel(locale, "sprites")}</option><option value="tiles">{manifestSectionLabel(locale, "tiles")}</option><option value="hud">{manifestSectionLabel(locale, "hud")}</option></select></label>
                  <label className="field"><span>{locale === "zh-CN" ? "实体" : "Entity"}</span><input value={assetPromoteDraft.entity} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, entity: event.target.value })} placeholder="heroine / shadow_sprite" /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "状态或瓦片键" : "State or tile key"}</span><input value={assetPromoteDraft.state} onChange={(event) => setAssetPromoteDraft({ ...assetPromoteDraft, state: event.target.value })} placeholder="walk_down / forest_edge" /></label>
                </div>
                <button type="button" className="primary-button" onClick={() => promoteDogfoodAsset.mutate()} disabled={promoteDogfoodAsset.isPending || !assetPromoteDraft.asset_id.trim()}>{locale === "zh-CN" ? "写入游戏清单" : "Promote to game manifest"}</button>
                {promoteDogfoodAsset.error ? <p className="error-text">{String((promoteDogfoodAsset.error as Error).message ?? promoteDogfoodAsset.error)}</p> : null}
                <p className="muted">{locale === "zh-CN" ? "上下文包" : "Context pack"}: {assetContextPack?.context_pack_path ?? (locale === "zh-CN" ? "尚未写入" : "not written yet")}</p>
              </section>
              <section className="manager-section">
                <h4>{locale === "zh-CN" ? "预算" : "Budgets"}</h4>
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
                  <label className="field"><span>{locale === "zh-CN" ? "Kimi 预算" : "Kimi cap"}</span><input type="number" value={activeDogfood.budgets.kimi_cny} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, kimi_cny: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "Kimi 已用" : "Kimi used"}</span><input type="number" value={activeDogfood.usage.kimi_cny} onChange={(event) => setDogfoodDraft({ ...activeDogfood, usage: { ...activeDogfood.usage, kimi_cny: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "DeepSeek 预算" : "DeepSeek cap"}</span><input type="number" value={activeDogfood.budgets.deepseek_cny} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, deepseek_cny: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "DeepSeek 已用" : "DeepSeek used"}</span><input type="number" value={activeDogfood.usage.deepseek_cny} onChange={(event) => setDogfoodDraft({ ...activeDogfood, usage: { ...activeDogfood.usage, deepseek_cny: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "云雾 GPT 预算" : "Yunwu GPT cap"}</span><input type="number" value={activeDogfood.budgets.yunwu_gpt_usd ?? 50} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, yunwu_gpt_usd: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "云雾 GPT 已用" : "Yunwu GPT used"}</span><input type="number" value={activeDogfood.usage.yunwu_gpt_usd ?? 0} onChange={(event) => setDogfoodDraft({ ...activeDogfood, usage: { ...activeDogfood.usage, yunwu_gpt_usd: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "图片预算" : "Image cap"}</span><input type="number" value={activeDogfood.budgets.yunwu_images} onChange={(event) => setDogfoodDraft({ ...activeDogfood, budgets: { ...activeDogfood.budgets, yunwu_images: Number(event.target.value) || 0 } })} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "图片已用" : "Images used"}</span><input type="number" value={activeDogfood.usage.yunwu_images} onChange={(event) => setDogfoodDraft({ ...activeDogfood, usage: { ...activeDogfood.usage, yunwu_images: Number(event.target.value) || 0 } })} /></label>
                </div>
              </section>
              <section className="manager-section">
                <h4>{locale === "zh-CN" ? "最近截图" : "Recent captures"}</h4>
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
                  {activeDogfood.captures.length === 0 ? <p className="muted">{locale === "zh-CN" ? `还没有登记截图。浏览器 smoke 会自动保存到 ${captureRoot || "项目 .astrabridge/captures 目录"}，手动截图也可以从那里登记。` : `No screenshots registered yet. Browser smoke auto-saves under ${captureRoot || "the project .astrabridge/captures root"} and manual captures can be registered from there.`}</p> : null}
                </div>
              </section>
              <section className="manager-section">
                <h4>{locale === "zh-CN" ? "浏览器烟测" : "Browser smoke"}</h4>
                <p className="muted">{locale === "zh-CN" ? "仅本地执行的浏览器烟测。AstraBridge 会访问 URL，在可用时截图、记录控制台问题，并写入自动里程碑。" : "Local-only browser smoke. AstraBridge visits the URL, tries to capture a screenshot with Playwright when available, records console issues, and writes an automatic milestone."}</p>
                <label className="field"><span>URL</span><input value={dogfoodSmokeUrl} onChange={(event) => setDogfoodSmokeUrl(event.target.value)} /></label>
                <div className="form-grid">
                  <label className="field"><span>{locale === "zh-CN" ? "标签" : "Label"}</span><input value={dogfoodSmokeLabel} onChange={(event) => setDogfoodSmokeLabel(event.target.value)} /></label>
                  <label className="field"><span>{locale === "zh-CN" ? "截图路径" : "Screenshot path"}</span><input value={dogfoodScreenshotPath} onChange={(event) => setDogfoodScreenshotPath(event.target.value)} placeholder={suggestedScreenshotPath || ".astrabridge\\captures\\browser-smoke.png"} /></label>
                </div>
                <p className="muted">{locale === "zh-CN" ? "建议保留默认截图路径，以确保截图留在当前项目边界内。" : "Leave the screenshot path as suggested to keep captures inside the current project boundary."}</p>
                <button type="button" className="ghost-button" onClick={() => runDogfoodBrowserSmoke.mutate()} disabled={runDogfoodBrowserSmoke.isPending}>{locale === "zh-CN" ? "运行浏览器烟测" : "Run browser smoke"}</button>
                {activeDogfood.browser_smokes?.slice(-3).reverse().map((smoke) => (
                  <div className={`manager-row dogfood-smoke-${smoke.status}`} key={`${smoke.url}-${smoke.created_at}`}>
                    <span><strong>{smoke.label}</strong><small>{smoke.status} · {smoke.http_status ?? "n/a"} · {smoke.screenshot_status ?? "screenshot n/a"}</small></span>
                    <code>{smoke.url}</code>
                  </div>
                ))}
                {runDogfoodBrowserSmoke.error ? <p className="error-text">{String((runDogfoodBrowserSmoke.error as Error).message ?? runDogfoodBrowserSmoke.error)}</p> : null}
              </section>
              <section className="manager-section">
                <h4>{locale === "zh-CN" ? "里程碑记录" : "Milestone note"}</h4>
                <label className="field"><span>{locale === "zh-CN" ? "标签" : "Label"}</span><input value={dogfoodMilestoneLabel} onChange={(event) => setDogfoodMilestoneLabel(event.target.value)} /></label>
                <label className="field"><span>{locale === "zh-CN" ? "验收说明" : "Validation"}</span><textarea rows={3} value={dogfoodMilestoneValidation} onChange={(event) => setDogfoodMilestoneValidation(event.target.value)} /></label>
                <button type="button" className="primary-button" onClick={() => saveDogfoodMilestone.mutate()} disabled={saveDogfoodMilestone.isPending}>{locale === "zh-CN" ? "保存里程碑" : "Save milestone"}</button>
                {activeDogfood.milestones?.slice(-3).reverse().map((milestone) => (
                  <div className="manager-row" key={`${milestone.label}-${milestone.created_at}`}>
                    <span><strong>{dogfoodRecordText(locale, milestone.label)}</strong><small>{milestone.provider || "provider n/a"} · {dogfoodRecordText(locale, milestone.status)}</small></span>
                    <code>{dogfoodRecordText(locale, milestone.validation.slice(0, 2).join(" · "))}</code>
                  </div>
                ))}
                {saveDogfoodMilestone.error ? <p className="error-text">{String((saveDogfoodMilestone.error as Error).message ?? saveDogfoodMilestone.error)}</p> : null}
              </section>
              <section className="manager-section">
                <h4>{locale === "zh-CN" ? "下一轮自治规则" : "Autonomy rules for the next agent turn"}</h4>
                <p className="muted">{locale === "zh-CN" ? "运行开始或恢复时可把这段交给下一轮 DS/Kimi。它会避免模型读取庞大的 .astrabridge 日志，并要求自检。" : "Paste this into the next DS/Kimi turn when the run starts or resumes. It keeps the model from reading huge .astrabridge logs and forces self-verification."}</p>
                <pre className="modal-json">{locale === "zh-CN"
                  ? `除非用户明确要求，不要读取 .astrabridge/runtime_events.jsonl 或 .astrabridge/approvals.jsonl。优先使用项目摘要、截图和 asset_manifest.json。每个里程碑后：运行项目，检查控制台错误，把截图保存到 ${captureRoot || ".astrabridge\\captures"}，说明问题，再修复。遵守预算：Kimi 50 CNY、DeepSeek 50 CNY、云雾 GPT 50 USD、云雾图片 200 张。达到 100% 停止，达到 80% 预警。`
                  : `Do not read .astrabridge/runtime_events.jsonl or .astrabridge/approvals.jsonl unless the user explicitly asks. Use project summaries, screenshots, and asset_manifest.json instead. After each milestone: run the game, inspect console errors, save a screenshot to ${captureRoot || ".astrabridge\\captures"}, describe the issue, then fix it. Respect budgets: Kimi 50 CNY, DeepSeek 50 CNY, Yunwu GPT 50 USD, Yunwu image 200 images. Stop at 100% and warn at 80%.`}</pre>
              </section>
            </div>
          ) : (
            <div className="empty-state">Dogfood run state is loading.</div>
          )}
        </div>
      ) : null}

      {tab === "updates" ? (
        <AgenticUpdateReviewPanel
          locale={locale}
          providers={routerConfig.data?.providers ?? []}
        />
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
              <div className="section-header manager-section-header">
                <h4>Latest results</h4>
                {hiddenHealthResultsCount > 0 ? (
                  <button
                    type="button"
                    className="ghost-button compact-inline-button"
                    onClick={() => setHealthResultsExpanded((value) => !value)}
                    aria-expanded={healthResultsExpanded}
                  >
                    {healthResultsExpanded
                      ? (locale === "zh-CN" ? "收起" : "Collapse")
                      : (locale === "zh-CN"
                        ? `还有 ${hiddenHealthResultsCount} 条`
                        : `${hiddenHealthResultsCount} more`)}
                  </button>
                ) : null}
              </div>
              <div className="manager-list manager-list-tall health-result-list">
                {visibleHealthResults.map((result, index) => {
                  const diagnosticsSummary = summarizeResponseDiagnosticsInline(result.response_diagnostics);
                  const failureSummary = runtimeErrorNoticeInline((result.failure_notice as RuntimeFailureNotice | null | undefined) ?? null);
                  const status = result.ok ? "pass" : result.skipped ? "blocked" : "fail";
                  const model = String(result.model ?? "-");
                  const meta = `${String(result.provider ?? "")} / ${String(result.effort ?? "")} / web ${String(result.web_smoke_status ?? "n/a")} / ${String(result.connectivity ?? result.reason ?? "")}`;
                  const detail = diagnosticsSummary || failureSummary;
                  const tooltip = [model, meta, detail].filter(Boolean).join("\n");
                  return (
                    <div className="manager-row health-result-row" key={`${String(result.run_id ?? "run")}-${index}`} title={tooltip || undefined}>
                      <span className="health-result-copy">
                        <strong className="health-result-model">{model}</strong>
                        <small className="health-result-meta">{meta}</small>
                      </span>
                      <span className="manager-row-side">
                        <small className={`health-result-status health-result-status-${status}`}>{status}</small>
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
              <label className="field"><span>Provider API key</span><input type="password" autoComplete="off" data-sensitive-field="true" value={managedKeyDraft.secret} onChange={(event) => setManagedKeyDraft({ ...managedKeyDraft, secret: event.target.value })} placeholder={managerMode === "managed_user" ? "Stored encrypted in this user's vault" : "Login first to save in the vault"} /></label>
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
                <button type="button" className="ghost-button" disabled={!selectedManagedKey || testManagedKey.isPending} onClick={() => testManagedKey.mutate({ key_id: selectedManagedKey?.key_id, provider_id: selectedManagedKey?.provider_id })}>{testManagedKey.isPending ? "Testing selected" : "Test selected"}</button>
              </div>
              {saveManagedKey.error ? <p className="error-text">{String(saveManagedKey.error)}</p> : null}
              {managedKeyTestFeedback ? (
                <section
                  className={`managed-key-test-result managed-key-test-result-${managedKeyTestFeedback.tone}`}
                  data-testid="managed-key-test-result"
                  role={managedKeyTestFeedback.tone === "danger" ? "alert" : "status"}
                  aria-live={managedKeyTestFeedback.tone === "danger" ? "assertive" : "polite"}
                  aria-atomic="true"
                >
                  <div className="managed-key-test-result-head">
                    {managedKeyTestFeedback.tone === "success" ? <CheckCircle2 aria-hidden="true" size={15} /> : <AlertTriangle aria-hidden="true" size={15} />}
                    <strong>{managedKeyTestFeedback.title}</strong>
                    <span>{managedKeyTestFeedback.provider} / {managedKeyTestFeedback.model}</span>
                  </div>
                  <p>{managedKeyTestFeedback.diagnostic}</p>
                  <dl className="managed-key-test-result-meta">
                    <div><dt>HTTP</dt><dd>{managedKeyTestFeedback.status ?? "not available"}</dd></div>
                    <div><dt>Usage</dt><dd>not available</dd></div>
                    <div><dt>Cost</dt><dd>not available</dd></div>
                  </dl>
                  <small>{managedKeyTestFeedback.nextAction}</small>
                </section>
              ) : null}
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
                {!llmKeys.data?.locked && (llmKeys.data?.keys?.length ?? 0) === 0 ? <p className="muted">{locale === "zh-CN" ? "当前还没有托管密钥。" : "No managed keys yet."}</p> : null}
              </div>
              <div className="field-row">
                <button type="button" className="ghost-button" disabled={!selectedManagedKey} onClick={() => selectedManagedKey && api.llmManagerDeleteKey(selectedManagedKey.key_id).then(() => queryClient.invalidateQueries({ queryKey: ["llm-manager-keys"] }))}>Delete selected</button>
              </div>
            </section>
          </div>
          <section className="manager-section">
            <h4>Anonymous/session key fallback</h4>
            <p className="muted">{t(locale, "key_setup_summary_compact")}</p>
            <label className="field"><span>{t(locale, "runtime_secret")}</span><input type="password" autoComplete="off" data-sensitive-field="true" value={secretValue} onChange={(event) => setSecretValue(event.target.value)} placeholder={t(locale, "key_setup_input_placeholder")} /></label>
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
  const cursorEnhancement = useAppStore((store) => store.cursorEnhancement);
  const setCursorEnhancement = useAppStore((store) => store.setCursorEnhancement);
  const setProject = useAppStore((store) => store.setProject);
  const project = useAppStore((store) => store.project);
  const health = useQuery({
    queryKey: ["launcher-health"],
    queryFn: api.health,
    retry: false,
    refetchInterval: 15000,
    staleTime: 5000,
  });
  const current = useQuery({
    queryKey: ["project"],
    queryFn: api.currentProject,
    retry: false,
    refetchInterval: project ? false : 5000,
    staleTime: project ? 60_000 : 0,
  });
  const recent = useQuery({ queryKey: ["recent-projects"], queryFn: api.recentProjects });
  const [name, setName] = useState("Codex Workspace");
  const [projectFile, setProjectFile] = useState("");
  const [workspaceRoot, setWorkspaceRoot] = useState("");
  const [entryMode, setEntryMode] = useState<ProjectFile["entry_mode"]>("existing");
  const [openPath, setOpenPath] = useState("");
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  useEffect(() => {
    if (current.data?.project) {
      setProject(current.data.project);
    }
  }, [current.data?.project, setProject]);

  const launcherSidecarGateText = launcherSidecarGateMessage(locale, {
    error: health.error,
    pending: health.isPending,
  });
  const launcherSidecarUnavailable =
    !current.data?.project && (health.isPending || Boolean(health.error));

  const createProject = useMutation({
    mutationFn: api.createProject,
    onSuccess: (data) => {
      setProject({
        ...data.project,
        ui_preferences: {
          ...data.project.ui_preferences,
          cursor_enhancement: cursorEnhancement,
        },
      });
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
    if (typeof document === "undefined") return;
    document.documentElement.dataset.appBootstrapDebug = JSON.stringify({
      surface: "launcher",
      storeProjectId: project?.project_id ?? null,
      currentProjectId: current.data?.project?.project_id ?? null,
      currentStatus: current.status,
      currentFetchStatus: current.fetchStatus,
      currentError: current.error instanceof Error ? current.error.message : current.error ? String(current.error) : null,
      healthStatus: health.status,
      healthFetchStatus: health.fetchStatus,
      healthError: health.error instanceof Error ? health.error.message : health.error ? String(health.error) : null,
      recentStatus: recent.status,
      recentFetchStatus: recent.fetchStatus,
      recentCount: recent.data?.projects?.length ?? null,
      openProjectPending: openProject.isPending,
      at: Date.now(),
    });
  }, [
    current.data?.project?.project_id,
    current.error,
    current.fetchStatus,
    current.status,
    health.error,
    health.fetchStatus,
    health.status,
    openProject.isPending,
    project?.project_id,
    recent.data?.projects?.length,
    recent.fetchStatus,
    recent.status,
  ]);

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
        <div className="launcher-hero-meta muted">
          <span>{t(locale, "setup_first")}</span>
          <button
            type="button"
            className="icon-button launcher-inline-help"
            title={t(locale, "project_suffix_note")}
            aria-label={t(locale, "project_suffix_note")}
          >
            <CircleHelp size={14} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </div>
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
            <div className="status-panel">
              <strong>{t(locale, "cursor_enhancement")}</strong>
              <span>{t(locale, cursorEnhancement === "off" ? "cursor_enhancement_hint_off" : "cursor_enhancement_hint_auto")}</span>
            </div>
            <div className="segmented">
              {(["auto", "off"] as CursorEnhancementPreference[]).map((item) => (
                <button key={item} type="button" className={cursorEnhancement === item ? "segmented-active" : ""} onClick={() => setCursorEnhancement(item)}>
                  {t(locale, `cursor_enhancement_${item}`)}
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="launcher-panel">
        <div className="launcher-recent-column">
          <h2>{t(locale, "recent_projects")}</h2>
          {launcherSidecarGateText ? (
            <p
              className={health.error ? "error-text launcher-sidecar-gate" : "muted launcher-sidecar-gate"}
              data-testid="launcher-sidecar-gate"
            >
              {launcherSidecarGateText}
            </p>
          ) : null}
          <div className="launcher-recent">
            {(recent.data?.projects ?? []).map((project) => {
              return (
                <RecentProjectButton
                  key={project.project_file}
                  project={project}
                  relativeTimeLabel={summarizeRelativeTime(project.updated_at)}
                  disabled={openProject.isPending}
                  onOpen={(projectFile) => openProject.mutate(projectFile)}
                />
              );
            })}
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

function AppShell({ bootstrapProject = null }: { bootstrapProject?: ProjectFile | null } = {}) {
  const queryClient = useQueryClient();
  const project = useAppStore((store) => store.project) ?? bootstrapProject!;
  const locale = useAppStore((store) => store.locale);
  const appearance = useAppStore((store) => store.appearance);
  const cursorEnhancement = useAppStore((store) => store.cursorEnhancement);
  const setProject = useAppStore((store) => store.setProject);
  const eventCursor = useAppStore((store) => store.eventCursor);
  const setEventCursor = useAppStore((store) => store.setEventCursor);
  const eventSnapshot = useAppStore((store) => store.eventSnapshot);
  const eventCursorRef = useRef(eventCursor);
  const handleEventsRef = useRef<(events: RuntimeEvent[]) => void>(() => undefined);
  const queuedInstructionInFlightRef = useRef(false);
  const goalContinuationKeyRef = useRef("");
  const smokeWaitingReplayRef = useRef<null | { threadId: string; turnId: string }>(null);
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
  const leftSidebarOpen = useAppStore((store) => store.leftSidebarOpen);
  const toggleLeftSidebar = useAppStore((store) => store.toggleLeftSidebar);
  const rightSidebarOpen = useAppStore((store) => store.rightSidebarOpen);
  const toggleRightSidebar = useAppStore((store) => store.toggleRightSidebar);
  const commandPaletteOpen = useAppStore((store) => store.commandPaletteOpen);
  const setCommandPaletteOpen = useAppStore((store) => store.setCommandPaletteOpen);
  const leftPane = useResizablePane("left");
  const rightPane = useResizablePane("right");
  const composerInputResize = useComposerInputResize();
  const compactShellViewport = useCompactShellViewport();
  const [compactSidebarOpen, setCompactSidebarOpen] = useState(false);
  const sidebarVisible = resolveSidebarVisible({
    compactViewport: compactShellViewport,
    compactSidebarOpen,
    desktopSidebarOpen: leftSidebarOpen,
  });

  useEffect(() => {
    if (!compactShellViewport) setCompactSidebarOpen(false);
  }, [compactShellViewport]);

  function toggleNavigationSidebar() {
    if (compactShellViewport) {
      setCompactSidebarOpen((current) => !current);
      return;
    }
    toggleLeftSidebar();
  }

  function closeCompactNavigation() {
    if (compactShellViewport) setCompactSidebarOpen(false);
  }

  const [composerText, setComposerText] = useState("");
  const [composerExecutionPolicy, setComposerExecutionPolicy] = useState<ComposerExecutionPolicy>("standard");
  const [attachments, setAttachments] = useState<AttachmentDraft[]>([]);
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [attachmentDropActive, setAttachmentDropActive] = useState(false);
  const [attachmentNotice, setAttachmentNotice] = useState<string | null>(null);
  const [voiceRecorderState, setVoiceRecorderState] = useState<VoiceRecorderState>("idle");
  const voiceRecorderRef = useRef<MediaRecorder | null>(null);
  const voiceStreamRef = useRef<MediaStream | null>(null);
  const voiceChunksRef = useRef<Blob[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const directoryInputRef = useRef<HTMLInputElement | null>(null);
  const [secretValue, setSecretValue] = useState("");
  const [profileForm, setProfileForm] = useState<Profile | null>(null);
  const [goalDraft, setGoalDraft] = useState("");
  const [goalDockExpanded, setGoalDockExpanded] = useState(false);
  const [goalEditMode, setGoalEditMode] = useState(false);
  const [goalDockTab, setGoalDockTab] = useState<GoalDockTab>("goal");
  const [goalRunnerArmed, setGoalRunnerArmed] = useState(false);
  const [instructionQueue, setInstructionQueue] = useState<QueuedInstruction[]>([]);
  const [instructionQueueExpanded, setInstructionQueueExpanded] = useState(false);
  const [instructionQueueEditingId, setInstructionQueueEditingId] = useState<string | null>(null);
  const [instructionQueueBusyId, setInstructionQueueBusyId] = useState<string | null>(null);
  const [instructionQueueBlockedId, setInstructionQueueBlockedId] = useState<string | null>(null);
  const [archivedVisible, setArchivedVisible] = useState(false);
  const [routerBaseUrl, setRouterBaseUrl] = useState("http://127.0.0.1:8787/v1");
  const [mainView, setMainView] = useState<"chat" | "setup">("chat");
  const [setupInitialTab, setSetupInitialTab] = useState<SetupTab>("login");
  const [setupExtensionsKind, setSetupExtensionsKind] = useState<ExtensionInventoryInitialKind>("all");
  const [topMenuOpen, setTopMenuOpen] = useState<string | null>(null);
  const [sendStage, setSendStage] = useState<string | null>(null);
  const [sendFailure, setSendFailure] = useState<string | null>(null);
  const runtimeErrorsByTurnRef = useRef<Record<string, string>>({});
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
  const [statusPlanExpanded, setStatusPlanExpanded] = useState(false);
  const [graphWorkspaceOpen, setGraphWorkspaceOpen] = useState(false);
  const chatCanvasRef = useRef<HTMLDivElement | null>(null);
  const [selectedTaskGraphId, setSelectedTaskGraphId] = useState<string | null>(null);
  const [selectedTaskGraphNodeId, setSelectedTaskGraphNodeId] = useState<string | null>(null);
  const [selectedTaskGraphEdgeId, setSelectedTaskGraphEdgeId] = useState<string | null>(null);
  const [fallbackTaskGraph, setFallbackTaskGraph] = useState<TaskGraphDefinition | null>(null);
  const [taskGraphNodeOverrides, setTaskGraphNodeOverrides] = useState<Record<string, Partial<TaskGraphDefinition["nodes"][number]>>>({});
  const [taskGraphNodeSaveError, setTaskGraphNodeSaveError] = useState<string | null>(null);
  const [taskGraphEdgeSaveError, setTaskGraphEdgeSaveError] = useState<string | null>(null);
const [taskGraphDryRunResult, setTaskGraphDryRunResult] = useState<TaskGraphDryRunResult | null>(null);
const [taskGraphDryRunError, setTaskGraphDryRunError] = useState<string | null>(null);
const [taskGraphFixtureRunError, setTaskGraphFixtureRunError] = useState<string | null>(null);
const taskGraphRequestedRunIntentRef = useRef<TaskGraphRequestedRunIntent | null>(null);
  const [taskGraphLiveDispatchStarted, setTaskGraphLiveDispatchStarted] = useState(false);
  const [taskGraphOptimisticLiveRunRefs, setTaskGraphOptimisticLiveRunRefs] = useState<Record<string, TaskGraphRunRef>>({});
  const [taskGraphLiveRunRefs, setTaskGraphLiveRunRefs] = useState<Record<string, TaskGraphRunRef>>({});
  const [taskGraphImportExportError, setTaskGraphImportExportError] = useState<string | null>(null);
  const [taskGraphLastImportedPath, setTaskGraphLastImportedPath] = useState<string | null>(null);
  const [taskGraphLastExportedPath, setTaskGraphLastExportedPath] = useState<string | null>(null);
  const [taskGraphLastExportPreview, setTaskGraphLastExportPreview] = useState<string | null>(null);
  const [taskGraphSnapshotError, setTaskGraphSnapshotError] = useState<string | null>(null);
  const [taskGraphSnapshotStatus, setTaskGraphSnapshotStatus] = useState<string | null>(null);
  const [taskGraphSnapshotDiffMarkdown, setTaskGraphSnapshotDiffMarkdown] = useState<string | null>(null);
  const [selectedTaskGraphSnapshotId, setSelectedTaskGraphSnapshotId] = useState<string | null>(null);
  const taskGraphSelectionHydrationKeyRef = useRef<string | null>(null);
  const [taskGraphFixturePendingVisible, setTaskGraphFixturePendingVisible] = useState(false);
  const taskGraphFixturePendingStartedAtRef = useRef<number | null>(null);
  const taskGraphFixturePendingTimerRef = useRef<number | null>(null);
  const smokeMode = useMemo(() => browserSmokeMode(), []);
  const [expandedSidebarProjects, setExpandedSidebarProjects] = useState<Set<string>>(() => loadStringSet(SIDEBAR_EXPANDED_PROJECTS_KEY));
  const [sidebarSelectionBusy, setSidebarSelectionBusy] = useState(false);
  const [sidebarSelectionError, setSidebarSelectionError] = useState<string | null>(null);
  const [pendingSidebarProjectKey, setPendingSidebarProjectKey] = useState<string | null>(null);
  const [pendingSidebarTask, setPendingSidebarTask] = useState<ProjectTask | null>(null);
  const [taskSelectionGuard, setTaskSelectionGuard] = useState<ProjectTask | null>(null);
  const selectedTaskScopeRef = useRef<string | null>(null);
  const [threadCreateRecovery, setThreadCreateRecovery] = useState<ThreadCreateRecovery | null>(null);
  const [taskCreationPending, setTaskCreationPending] = useState<{ name: string; operationId: string; recoveryAttempts: number } | null>(null);

  const profiles = useQuery({ queryKey: ["profiles"], queryFn: api.profiles, refetchInterval: 5000 });
  const routerConfig = useQuery({ queryKey: ["router-config"], queryFn: api.routerConfig, refetchInterval: 5000 });
  const llmSession = useQuery({ queryKey: ["llm-manager-session"], queryFn: api.llmManagerSession, refetchInterval: 5000 });
  const llmCatalog = useQuery({ queryKey: ["llm-manager-catalog"], queryFn: api.llmManagerEffectiveCatalog, refetchInterval: 5000 });
  const mcpConfig = useQuery({ queryKey: ["mcp-config"], queryFn: api.mcpConfig, refetchInterval: 7000 });
  const projectSidebar = useQuery({
    queryKey: ["project-sidebar", project.project_id],
    queryFn: api.projectSidebar,
    enabled: Boolean(project.project_id),
    refetchInterval: smokeMode ? false : 7000,
    retry: smokeMode ? false : undefined,
  });
  const runtime = useQuery({
    queryKey: ["runtime-environment"],
    queryFn: api.runtimeEnvironment,
    refetchInterval: smokeMode ? false : 5000,
    retry: smokeMode ? false : undefined,
    staleTime: smokeMode ? 60_000 : 0,
  });
  useEffect(() => {
    saveStringSet(SIDEBAR_EXPANDED_PROJECTS_KEY, expandedSidebarProjects);
  }, [expandedSidebarProjects]);
  useEffect(() => {
    const currentProject = projectSidebar.data?.projects.find((item: SidebarProjectNode) => item.is_current);
    if (!currentProject) return;
    const projectKey = sidebarProjectKey(currentProject);
    setExpandedSidebarProjects((current: Set<string>) => (current.has(projectKey) ? current : new Set([...current, projectKey])));
  }, [projectSidebar.data?.projects]);
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
  const sidebarAutomations = useQuery({
    queryKey: ["sidebar-automations", project.project_id],
    queryFn: api.automations,
    enabled: Boolean(project.project_id),
    refetchInterval: smokeMode ? false : 15000,
    retry: false,
  });
  const sidebarPluginSkillRegistry = useQuery({
    queryKey: ["sidebar-plugin-skill-registry", project.project_id],
    queryFn: () => api.runtimePluginSkillRegistry(),
    enabled: Boolean(project.project_id),
    refetchInterval: smokeMode ? false : 30000,
    retry: false,
    staleTime: 15000,
  });
  useEffect(() => {
    if (!project.project_id) return;
    void api.ensureAdminSession().catch(() => {
      // Keep mutations as the authoritative error surface. This prewarm path
      // only reduces first-click latency and browser dogfood timeout races.
    });
  }, [project.project_id]);

  const resolvedCurrentTask = useMemo(
    () => resolveCurrentProjectTask(project, projectTasks.data),
    [project, projectTasks.data],
  );
  const currentTask = useMemo(
    () =>
      resolveVisibleCurrentProjectTask({
        pendingSidebarTask,
        taskSelectionGuard,
        resolvedCurrentTask,
      }),
    [pendingSidebarTask, resolvedCurrentTask, taskSelectionGuard],
  );
  const taskGraphHydrationTaskId = currentTask?.task_id ?? project.current_task_id ?? null;
  useEffect(() => {
    if (!selectedTaskScopeRef.current && currentTask?.task_id) {
      selectedTaskScopeRef.current = currentTask.task_id;
    }
  }, [currentTask?.task_id]);
  useEffect(() => {
    if (!pendingSidebarTask) return;
    const reconciledTask = resolvedCurrentTask;
    if (project.current_task_id !== pendingSidebarTask.task_id || reconciledTask?.task_id !== pendingSidebarTask.task_id) return;
    setPendingSidebarProjectKey(null);
    setPendingSidebarTask(null);
  }, [pendingSidebarTask, project.current_task_id, resolvedCurrentTask]);
  useEffect(() => {
    if (!taskSelectionGuard) return;
    const reconciledTask = resolvedCurrentTask;
    if (project.current_task_id !== taskSelectionGuard.task_id || reconciledTask?.task_id !== taskSelectionGuard.task_id) return;
    setTaskSelectionGuard(null);
  }, [project.current_task_id, resolvedCurrentTask, taskSelectionGuard]);
  function cacheProjectTask(task: ProjectTask | null | undefined) {
    if (!task) return;
    setTaskSelectionGuard((current) => (current?.task_id === task.task_id ? task : current));
    queryClient.setQueryData<ProjectTasksResponse>(["project-tasks", project.project_id], (current) => mergeProjectTaskResponse(current, task));
  }
  const activeTaskGraphId =
    selectedTaskGraphId ??
    latestTaskGraphDefinition(currentTask?.graph_definitions)?.graph_id ??
    fallbackTaskGraph?.graph_id ??
    null;
  const taskGraphTemplates = useQuery({
    queryKey: ["task-graph-templates"],
    queryFn: api.taskGraphTemplates,
    enabled: mainView === "chat",
    staleTime: 30000,
  });
  const taskGraph = useQuery({
    queryKey: ["task-graph", project.project_id, taskGraphHydrationTaskId, activeTaskGraphId],
    queryFn: () => api.taskGraph(activeTaskGraphId),
    enabled: Boolean(graphWorkspaceOpen && taskGraphHydrationTaskId && activeTaskGraphId),
    refetchInterval: smokeMode ? false : graphWorkspaceOpen ? 4000 : false,
    retry: smokeMode ? false : undefined,
  });
  const taskGraphTemplateList =
    taskGraphTemplates.data?.templates?.length
      ? taskGraphTemplates.data.templates
      : taskGraphTemplates.error
        ? FALLBACK_TASK_GRAPH_TEMPLATES
        : taskGraphTemplates.data?.templates ?? [];
  const taskGraphTemplatesLoading = taskGraphTemplateList.length === 0 && taskGraphTemplates.isLoading;
  const taskGraphLoading = taskGraph.isLoading && !taskGraph.error;
  const taskGraphRouteUnavailable = resolveTaskGraphRouteUnavailable({
    templatesError: Boolean(taskGraphTemplates.error),
    taskGraphErrorMessage: (taskGraph.error as Error | null)?.message ?? null,
    routeGraph: taskGraph.data?.graph ?? null,
    persistedGraphs: currentTask?.graph_definitions ?? [],
    fallbackGraph: fallbackTaskGraph,
  });
  const clearTaskGraphFixturePendingTimer = () => {
    if (typeof window !== "undefined" && taskGraphFixturePendingTimerRef.current != null) {
      window.clearTimeout(taskGraphFixturePendingTimerRef.current);
      taskGraphFixturePendingTimerRef.current = null;
    }
  };
  const startVisibleTaskGraphFixturePending = () => {
    clearTaskGraphFixturePendingTimer();
    taskGraphFixturePendingStartedAtRef.current = Date.now();
    setTaskGraphFixturePendingVisible(true);
  };
  const settleVisibleTaskGraphFixturePending = () => {
    const startedAt = taskGraphFixturePendingStartedAtRef.current;
    if (startedAt == null) {
      setTaskGraphFixturePendingVisible(false);
      return;
    }
    const elapsed = Date.now() - startedAt;
    const remaining = Math.max(0, TASK_GRAPH_FIXTURE_PENDING_MIN_MS - elapsed);
    clearTaskGraphFixturePendingTimer();
    if (remaining === 0) {
      taskGraphFixturePendingStartedAtRef.current = null;
      setTaskGraphFixturePendingVisible(false);
      return;
    }
    if (typeof window !== "undefined") {
      taskGraphFixturePendingTimerRef.current = window.setTimeout(() => {
        taskGraphFixturePendingStartedAtRef.current = null;
        taskGraphFixturePendingTimerRef.current = null;
        setTaskGraphFixturePendingVisible(false);
      }, remaining);
    }
  };
  useEffect(
    () => () => {
      clearTaskGraphFixturePendingTimer();
    },
    [],
  );
  const taskGraphProviderOptions = useMemo(
    () =>
      Array.from(
        new Set(
          (profiles.data?.profiles ?? [])
            .map((profile) => profile.provider_id?.trim())
            .filter((value): value is string => Boolean(value)),
        ),
      ).sort(),
    [profiles.data?.profiles],
  );
  const taskGraphModelSuggestions = useMemo(
    () =>
      Array.from(
        new Set(
          (profiles.data?.profiles ?? [])
            .map((profile) => profile.model?.trim())
            .filter((value): value is string => Boolean(value)),
        ),
      ).sort(),
    [profiles.data?.profiles],
  );
  useEffect(() => {
    if (!taskGraphHydrationTaskId) {
      setFallbackTaskGraph(null);
      setTaskGraphNodeOverrides({});
      setSelectedTaskGraphEdgeId(null);
      setTaskGraphDryRunResult(null);
      setTaskGraphDryRunError(null);
      setTaskGraphFixtureRunError(null);
      setTaskGraphImportExportError(null);
      setTaskGraphLastImportedPath(null);
      setTaskGraphLastExportedPath(null);
      setTaskGraphLastExportPreview(null);
      setTaskGraphSnapshotError(null);
      setTaskGraphSnapshotStatus(null);
      setTaskGraphSnapshotDiffMarkdown(null);
      setSelectedTaskGraphSnapshotId(null);
      return;
    }
    setFallbackTaskGraph(readFallbackTaskGraph(project.project_id, taskGraphHydrationTaskId));
    setTaskGraphNodeOverrides({});
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    setTaskGraphImportExportError(null);
    setTaskGraphLastImportedPath(null);
    setTaskGraphLastExportedPath(null);
    setTaskGraphLastExportPreview(null);
    setTaskGraphSnapshotError(null);
    setTaskGraphSnapshotStatus(null);
    setTaskGraphSnapshotDiffMarkdown(null);
    setSelectedTaskGraphSnapshotId(null);
  }, [project.project_id, taskGraphHydrationTaskId]);
  useEffect(() => {
    if (!taskGraphHydrationTaskId) {
      taskGraphSelectionHydrationKeyRef.current = null;
      setSelectedTaskGraphId(null);
      setSelectedTaskGraphNodeId(null);
      setSelectedTaskGraphEdgeId(null);
      return;
    }
    const selectionKey = taskGraphSelectionStorageKey(project.project_id, taskGraphHydrationTaskId);
    const firstHydrationForTask = taskGraphSelectionHydrationKeyRef.current !== selectionKey;
    taskGraphSelectionHydrationKeyRef.current = selectionKey;
    const persistedGraphId = loadStoredString(taskGraphSelectionStorageKey(project.project_id, taskGraphHydrationTaskId));
    const latestGraphDefinition = latestTaskGraphDefinition(currentTask?.graph_definitions);
    const latestGraphId = taskGraphRouteUnavailable
      ? fallbackTaskGraph?.graph_id ?? latestGraphDefinition?.graph_id ?? null
      : taskGraph.data?.graph?.graph_id ?? latestGraphDefinition?.graph_id ?? fallbackTaskGraph?.graph_id ?? null;
    setSelectedTaskGraphId((current) => {
      return resolvePreferredTaskGraphId({
        currentGraphId: current,
        persistedGraphId,
        routeGraphId: taskGraph.data?.graph?.graph_id ?? null,
        latestGraphId,
        fallbackGraphId: fallbackTaskGraph?.graph_id ?? null,
        taskGraphIds: [
          ...(currentTask?.graph_definitions ?? []).map((graph) => graph.graph_id),
          ...(fallbackTaskGraph?.graph_id ? [fallbackTaskGraph.graph_id] : []),
        ],
        taskGraphRouteUnavailable,
        firstHydrationForTask,
      });
    });
  }, [currentTask, fallbackTaskGraph?.graph_id, project.project_id, taskGraph.data?.graph?.graph_id, taskGraphHydrationTaskId, taskGraphRouteUnavailable]);
  useEffect(() => {
    if (!taskGraphHydrationTaskId) return;
    saveStoredString(taskGraphSelectionStorageKey(project.project_id, taskGraphHydrationTaskId), selectedTaskGraphId);
  }, [project.project_id, selectedTaskGraphId, taskGraphHydrationTaskId]);
  useEffect(() => {
    const snapshotRefs = currentTask?.graph_snapshot_refs ?? [];
    if (!snapshotRefs.length) {
      setSelectedTaskGraphSnapshotId(null);
      return;
    }
    setSelectedTaskGraphSnapshotId((current) => {
      if (current && snapshotRefs.some((item) => item.snapshot_id === current)) {
        return current;
      }
      return snapshotRefs[0]?.snapshot_id ?? null;
    });
  }, [currentTask?.graph_snapshot_refs]);
  useEffect(() => {
    if (mainView !== "chat" || !graphWorkspaceOpen) return;
    chatCanvasRef.current?.scrollTo({ top: 0, left: 0 });
  }, [graphWorkspaceOpen, mainView, currentTask?.task_id, activeTaskGraphId]);
  useEffect(() => {
    const nodes =
      (taskGraphRouteUnavailable
        ? fallbackTaskGraph?.nodes
        : taskGraph.data?.graph?.nodes ??
          currentTask?.graph_definitions?.find((graph) => graph.graph_id === activeTaskGraphId)?.nodes ??
          latestTaskGraphDefinition(currentTask?.graph_definitions)?.nodes) ??
      fallbackTaskGraph?.nodes ??
      [];
    if (!nodes.length) {
      setSelectedTaskGraphNodeId(null);
      return;
    }
    setSelectedTaskGraphNodeId((current) => (current && nodes.some((node) => node.node_id === current) ? current : nodes[0]?.node_id ?? null));
  }, [activeTaskGraphId, currentTask?.graph_definitions, fallbackTaskGraph?.nodes, taskGraph.data?.graph, taskGraphRouteUnavailable]);
  useEffect(() => {
    const edges =
      (taskGraphRouteUnavailable
        ? fallbackTaskGraph?.edges
        : taskGraph.data?.graph?.edges ??
          currentTask?.graph_definitions?.find((graph) => graph.graph_id === activeTaskGraphId)?.edges ??
          latestTaskGraphDefinition(currentTask?.graph_definitions)?.edges) ??
      fallbackTaskGraph?.edges ??
      [];
    if (!edges.length) {
      setSelectedTaskGraphEdgeId(null);
      return;
    }
    setSelectedTaskGraphEdgeId((current) => (current && edges.some((edge) => edge.edge_id === current) ? current : edges[0]?.edge_id ?? null));
  }, [activeTaskGraphId, currentTask?.graph_definitions, fallbackTaskGraph?.edges, taskGraph.data?.graph, taskGraphRouteUnavailable]);
  const selectedThreadId = taskVisibleThreadId(currentTask) ?? (!currentTask ? project.current_thread_id ?? threads.data?.threads[0]?.id ?? null : null);
  const sendTargetThreadId = resolveTaskSendTargetThreadId({
    currentTask,
    selectedThreadId,
  });
  const selectedThreadSummary = threads.data?.threads.find((thread) => thread.id === selectedThreadId);
  const currentTaskProviderThreads = Array.isArray(currentTask?.provider_threads) ? currentTask.provider_threads : [];
  const selectedTaskProviderThread = currentTaskProviderThreads.find((thread) => thread.thread_id === selectedThreadId) ?? null;
  const selectedThreadProfileId = resolveSelectedThreadProfileId({
    currentTask,
    selectedThreadId,
    threadSettingsProfileId: threadSettingsDraft[selectedThreadId ?? ""]?.profile_id ?? null,
    selectedThreadSummary,
    projectDefaultProfileId: project.default_profile_id,
    listProfileId,
  });
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

  const openProjectFromSidebar = useMutation({
    mutationFn: api.openProject,
    onSuccess: (data) => {
      setProject(data.project);
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["threads"] });
      queryClient.invalidateQueries({ queryKey: ["thread"] });
      invalidateRestoreStateQueries(queryClient);
    },
  });
  const switchThread = useMutation({
    mutationFn: api.switchThread,
    onSuccess: (data) => {
      setProject(data.project);
      cacheProjectTask(data.task);
      invalidateRestoreStateQueries(queryClient);
    },
  });
  const switchTask = useMutation({
    mutationFn: api.switchTask,
    onSuccess: (data) => {
      setProject(data.project);
      cacheProjectTask(data.task);
      invalidateRestoreStateQueries(queryClient);
    },
  });
  const suggestProjectTitle = useMutation({
    mutationFn: () => api.suggestProjectTitle(false),
    onSuccess: (data) => {
      if (data.project) setProject(data.project);
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["recent-projects"] });
    },
  });
  const suggestTaskTitle = useMutation({
    mutationFn: () => api.suggestTaskTitle(false),
    onSuccess: (data) => {
      if (data.project) setProject(data.project);
      cacheProjectTask(data.task);
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
    },
  });
  const instantiateTaskGraph = useMutation({
    mutationFn: ({ templateId, title }: { templateId: string; title?: string | null }) =>
      api.instantiateTaskGraph({ template_id: templateId, title }),
    onSuccess: (data) => {
      setTaskGraphNodeSaveError(null);
      setTaskGraphEdgeSaveError(null);
      setTaskGraphDryRunResult(null);
      setTaskGraphDryRunError(null);
      cacheProjectTask(data.task);
      if (data.graph) {
        setFallbackTaskGraph(data.graph);
        persistFallbackTaskGraph(data.graph);
        setGraphWorkspaceOpen(true);
        setSelectedTaskGraphId(data.graph.graph_id);
        setSelectedTaskGraphNodeId(data.graph.nodes[0]?.node_id ?? null);
        setSelectedTaskGraphEdgeId(data.graph.edges[0]?.edge_id ?? null);
        if (data.task?.task_id) {
          saveStoredString(taskGraphSelectionStorageKey(project.project_id, data.task.task_id), data.graph.graph_id);
        }
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
  });
  const updateTaskGraphNode = useMutation({
    mutationFn: api.updateTaskGraphNode,
    onSuccess: (data) => {
      setTaskGraphNodeSaveError(null);
      setTaskGraphDryRunResult(null);
      setTaskGraphDryRunError(null);
      if (data.graph && data.node?.node_id) {
        setTaskGraphNodeOverrides((current) => {
          const next = { ...current };
          delete next[taskGraphNodeOverrideKey(data.graph.graph_id, data.node.node_id)];
          return next;
        });
      }
      cacheProjectTask(data.task);
      if (data.graph) {
        setFallbackTaskGraph(data.graph);
        persistFallbackTaskGraph(data.graph);
        setSelectedTaskGraphId(data.graph.graph_id);
        setSelectedTaskGraphNodeId(data.node?.node_id ?? null);
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphNodeSaveError(error instanceof Error ? error.message : "Failed to save the selected node.");
    },
  });
  const updateTaskGraphEdge = useMutation({
    mutationFn: api.updateTaskGraphEdge,
    onSuccess: (data) => {
      setTaskGraphEdgeSaveError(null);
      setTaskGraphDryRunResult(null);
      setTaskGraphDryRunError(null);
      cacheProjectTask(data.task);
      if (data.graph) {
        setFallbackTaskGraph(data.graph);
        persistFallbackTaskGraph(data.graph);
        setSelectedTaskGraphId(data.graph.graph_id);
        setSelectedTaskGraphEdgeId(data.edge?.edge_id ?? null);
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphEdgeSaveError(error instanceof Error ? error.message : "Failed to save the selected edge.");
    },
  });
  const saveTaskGraphDefinition = useMutation({
    mutationFn: api.saveTaskGraph,
    onSuccess: (data) => {
      setTaskGraphEdgeSaveError(null);
      setTaskGraphDryRunResult(null);
      setTaskGraphDryRunError(null);
      if (data.graph) {
        setTaskGraphNodeOverrides((current) => {
          const next = { ...current };
          for (const node of data.graph.nodes ?? []) {
            delete next[taskGraphNodeOverrideKey(data.graph.graph_id, node.node_id)];
          }
          return next;
        });
      }
      cacheProjectTask(data.task);
      if (data.graph) {
        setFallbackTaskGraph(data.graph);
        persistFallbackTaskGraph(data.graph);
        setSelectedTaskGraphId(data.graph.graph_id);
        setSelectedTaskGraphEdgeId((current) => (current && data.graph.edges.some((edge) => edge.edge_id === current) ? current : data.graph.edges[0]?.edge_id ?? null));
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphEdgeSaveError(error instanceof Error ? error.message : "Failed to save the task graph.");
    },
  });
  const dryRunTaskGraph = useMutation({
    mutationFn: api.dryRunTaskGraph,
    onSuccess: (data) => {
      setTaskGraphDryRunError(null);
      setTaskGraphDryRunResult(data.dry_run);
      cacheProjectTask(data.task);
      if (data.graph) {
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      const fallbackLiveRun = shouldPromoteDryRunToLiveRun({
        intent: taskGraphRequestedRunIntentRef.current,
        dryRunGraphId: data.graph?.graph_id,
        dryRunOverallStatus: data.dry_run?.overall_status,
        liveRunPending: runTaskGraph.isPending,
      });
      if (fallbackLiveRun) {
        taskGraphRequestedRunIntentRef.current = {
          kind: "live",
          graphId: fallbackLiveRun.graphId,
          tokenBudget: fallbackLiveRun.tokenBudget,
          fallbackTriggered: true,
        };
        primeTaskGraphOptimisticLiveRunRef({
          graphId: fallbackLiveRun.graphId,
          taskId: String(data.task?.task_id ?? currentTask?.task_id ?? "").trim(),
          entryNodeIds: data.graph?.graph_policy?.entry_node_ids,
          budget: { status: "pending", run: { limits: { total_tokens: fallbackLiveRun.tokenBudget } } },
          templateId: data.graph?.template_id,
        });
        runTaskGraph.mutate({
          graph_id: fallbackLiveRun.graphId,
          budget: { limits: { total_tokens: fallbackLiveRun.tokenBudget } },
        });
        return;
      }
      taskGraphRequestedRunIntentRef.current = null;
    },
    onError: (error) => {
      taskGraphRequestedRunIntentRef.current = null;
      setTaskGraphDryRunError(error instanceof Error ? error.message : "Dry-run failed.");
    },
  });
  const runTaskGraph = useMutation({
    mutationFn: (payload: { graph_id: string; budget: { limits: { total_tokens: number } } }) =>
      api.runTaskGraph(payload, {
        onRequestStage: (stage) => {
          if (
            stage === "run_fetch_started" ||
            stage === "run_response_received" ||
            stage === "run_fetch_threw"
          ) {
            setTaskGraphLiveDispatchStarted(true);
          }
        },
      }),
    onSuccess: (data) => {
      taskGraphRequestedRunIntentRef.current = null;
      setTaskGraphLiveDispatchStarted(false);
      setTaskGraphFixtureRunError(null);
      clearTaskGraphOptimisticLiveRunRef(data.graph?.graph_id ?? data.live_run?.run_ref?.graph_id);
      cacheTaskGraphLiveRunRef(data.live_run?.run_ref);
      cacheProjectTask(data.task);
      if (data.graph) {
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      taskGraphRequestedRunIntentRef.current = null;
      setTaskGraphLiveDispatchStarted(false);
      applyTaskGraphRunFailurePayload(error, activeTaskGraphId);
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({ queryKey: ["task-graph", project.project_id, currentTask?.task_id, activeTaskGraphId] });
      setTaskGraphFixtureRunError(error instanceof Error ? error.message : "Live run failed.");
    },
  });
  const taskGraphLiveRunUiPending =
    runTaskGraph.isPending && taskGraphLiveDispatchStarted;
  useEffect(() => {
    if (!taskGraphLiveRunUiPending) return undefined;
    const refresh = () => {
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      if (activeTaskGraphId) {
        queryClient.invalidateQueries({
          queryKey: [
            "task-graph",
            project.project_id,
            currentTask?.task_id ?? null,
            activeTaskGraphId,
          ],
        });
      }
    };
    refresh();
    const timer = window.setInterval(
      refresh,
      TASK_GRAPH_LIVE_RUN_PENDING_REFRESH_MS,
    );
    return () => window.clearInterval(timer);
  }, [
    activeTaskGraphId,
    currentTask?.task_id,
    project.project_id,
    queryClient,
    taskGraphLiveRunUiPending,
  ]);
  const importTaskGraphFile = useMutation({
    mutationFn: api.importTaskGraphFile,
    onSuccess: (data) => {
      setTaskGraphImportExportError(null);
      setTaskGraphNodeSaveError(null);
      setTaskGraphEdgeSaveError(null);
      setTaskGraphDryRunResult(null);
      setTaskGraphDryRunError(null);
      setTaskGraphFixtureRunError(null);
      setTaskGraphLastImportedPath(data.import_path ?? null);
      setTaskGraphLastExportedPath(null);
      setTaskGraphLastExportPreview(null);
      cacheProjectTask(data.task);
      if (data.graph) {
        setFallbackTaskGraph(data.graph);
        persistFallbackTaskGraph(data.graph);
        setGraphWorkspaceOpen(true);
        setSelectedTaskGraphId(data.graph.graph_id);
        setSelectedTaskGraphNodeId(data.graph.nodes[0]?.node_id ?? null);
        setSelectedTaskGraphEdgeId(data.graph.edges[0]?.edge_id ?? null);
        if (data.task?.task_id) {
          saveStoredString(taskGraphSelectionStorageKey(project.project_id, data.task.task_id), data.graph.graph_id);
        }
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphImportExportError(error instanceof Error ? error.message : "Failed to import the graph file.");
    },
  });
  const exportTaskGraphFile = useMutation({
    mutationFn: api.exportTaskGraphFile,
    onSuccess: (data) => {
      setTaskGraphImportExportError(null);
      setTaskGraphLastImportedPath(null);
      setTaskGraphLastExportedPath(data.export_path ?? null);
      setTaskGraphLastExportPreview(data.serialized_text ?? null);
      cacheProjectTask(data.task);
      if (data.graph) {
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphImportExportError(error instanceof Error ? error.message : "Failed to export the graph file.");
    },
  });
  const createTaskGraphSnapshot = useMutation({
    mutationFn: api.createTaskGraphSnapshot,
    onSuccess: (data) => {
      setTaskGraphSnapshotError(null);
      setTaskGraphSnapshotStatus(`Snapshot created: ${data.snapshot.label ?? data.snapshot.snapshot_id}`);
      setSelectedTaskGraphSnapshotId(data.snapshot.snapshot_id);
      cacheProjectTask(data.task);
      if (data.graph) {
        setFallbackTaskGraph(data.graph);
        persistFallbackTaskGraph(data.graph);
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphSnapshotError(error instanceof Error ? error.message : "Failed to create a graph snapshot.");
    },
  });
  const diffTaskGraphSnapshot = useMutation({
    mutationFn: api.diffTaskGraphSnapshot,
    onSuccess: (data) => {
      setTaskGraphSnapshotError(null);
      setTaskGraphSnapshotStatus(
        `Compared ${data.snapshot.label ?? data.snapshot.snapshot_id} with ${data.compared_label ?? "current graph"}.`,
      );
      setTaskGraphSnapshotDiffMarkdown(data.diff_markdown);
      setSelectedTaskGraphSnapshotId(data.snapshot.snapshot_id);
      cacheProjectTask(data.task);
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphSnapshotError(error instanceof Error ? error.message : "Failed to compare the selected graph snapshot.");
    },
  });
  const rollbackTaskGraphToSnapshot = useMutation({
    mutationFn: api.rollbackTaskGraphToSnapshot,
    onSuccess: (data) => {
      setTaskGraphSnapshotError(null);
      setTaskGraphSnapshotStatus(`Rolled back to ${data.rolled_back_to_snapshot.label ?? data.rolled_back_to_snapshot.snapshot_id}.`);
      setTaskGraphSnapshotDiffMarkdown(null);
      setSelectedTaskGraphSnapshotId(data.snapshot.snapshot_id);
      cacheProjectTask(data.task);
      if (data.graph) {
        setFallbackTaskGraph(data.graph);
        persistFallbackTaskGraph(data.graph);
        setSelectedTaskGraphId(data.graph.graph_id);
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphSnapshotError(error instanceof Error ? error.message : "Failed to roll back to the selected graph snapshot.");
    },
  });
  const cacheTaskGraphLiveRunRef = (runRef: TaskGraphRunRef | null | undefined) => {
    if (!runRef) return;
    const graphId = String(runRef.graph_id ?? "").trim();
    if (!graphId) return;
    setTaskGraphOptimisticLiveRunRefs((current) => {
      if (!(graphId in current)) return current;
      const next = { ...current };
      delete next[graphId];
      return next;
    });
    setTaskGraphLiveRunRefs((current) => {
      const existing = current[graphId];
      const next =
        selectLatestTaskGraphRunRef(graphId, [[runRef], existing ? [existing] : []]) ?? runRef;
      if (existing === next) return current;
      return {
        ...current,
        [graphId]: next,
      };
    });
  };
  const primeTaskGraphOptimisticLiveRunRef = ({
    graphId,
    taskId,
    entryNodeIds,
    budget,
    templateId,
  }: {
    graphId: string;
    taskId: string;
    entryNodeIds?: readonly string[] | null | undefined;
    budget?: TaskGraphRunRef["budget"];
    templateId?: string | null | undefined;
  }) => {
    const cleanGraphId = String(graphId ?? "").trim();
    const cleanTaskId = String(taskId ?? "").trim();
    if (!cleanGraphId || !cleanTaskId) return;
    const optimistic = createOptimisticTaskGraphLiveRunRef({
      graphId: cleanGraphId,
      taskId: cleanTaskId,
      entryNodeIds,
      budget,
      templateId,
    });
    setTaskGraphOptimisticLiveRunRefs((current) => ({
      ...current,
      [cleanGraphId]: optimistic,
    }));
  };
  const clearTaskGraphOptimisticLiveRunRef = (graphId: string | null | undefined) => {
    const cleanGraphId = String(graphId ?? "").trim();
    if (!cleanGraphId) return;
    setTaskGraphOptimisticLiveRunRefs((current) => {
      if (!(cleanGraphId in current)) return current;
      const next = { ...current };
      delete next[cleanGraphId];
      return next;
    });
  };
  const applyTaskGraphRunFailurePayload = (
    error: unknown,
    fallbackGraphId: string | null | undefined,
  ) => {
    clearTaskGraphOptimisticLiveRunRef(fallbackGraphId);
    if (!(error instanceof ApiRequestError) || !error.data || typeof error.data !== "object") {
      return;
    }
    const payload = error.data as {
      task?: ProjectTask | null;
      graph?: TaskGraphDefinition | null;
      live_run?: {
        run_ref?: TaskGraphRunRef | null;
      } | null;
    };
    cacheTaskGraphLiveRunRef(payload.live_run?.run_ref);
    cacheProjectTask(payload.task);
    const graphId = String(payload.graph?.graph_id ?? fallbackGraphId ?? "").trim();
    if (graphId && payload.graph) {
      queryClient.setQueryData(
        ["task-graph", project.project_id, payload.task?.task_id ?? currentTask?.task_id ?? null, graphId],
        {
          graph: payload.graph,
          task: payload.task ?? currentTask,
        },
      );
    }
  };
  const fixtureRunTaskGraph = useMutation({
    mutationFn: api.fixtureRunTaskGraph,
    onSuccess: (data) => {
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "fixture_run_success",
          graphId: data.graph?.graph_id ?? null,
          runId: String((data.fixture_run as { run_id?: string } | null)?.run_id ?? ""),
          taskGraphCount: data.task?.graph_definitions?.length ?? null,
          at: Date.now(),
        });
      }
      setTaskGraphFixtureRunError(null);
      cacheTaskGraphLiveRunRef(data.fixture_run?.run_ref);
      cacheProjectTask(data.task);
      if (data.graph) {
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "fixture_run_error",
          error: error instanceof Error ? error.message : String(error),
          at: Date.now(),
        });
      }
      setTaskGraphFixtureRunError(error instanceof Error ? error.message : "Fixture run failed.");
    },
    onSettled: () => {
      settleVisibleTaskGraphFixturePending();
    },
  });
  const cancelTaskGraphRun = useMutation({
    mutationFn: api.cancelTaskGraphRun,
    onSuccess: (data) => {
      setTaskGraphFixtureRunError(null);
      cacheTaskGraphLiveRunRef(data.run_ref);
      cacheProjectTask(data.task);
      if (data.graph) {
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphFixtureRunError(error instanceof Error ? error.message : "Run cancellation failed.");
    },
  });
  const recoverTaskGraphRun = useMutation({
    mutationFn: api.recoverTaskGraphRun,
    onSuccess: (data) => {
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "recover_run_success",
          runId: String(data.fixture_run?.run_ref?.run_id ?? ""),
          strategy: String(data.recovery?.strategy ?? ""),
          sourceRunId: String(data.recovery?.source_run_id ?? ""),
          at: Date.now(),
        });
      }
      setTaskGraphFixtureRunError(null);
      cacheTaskGraphLiveRunRef(data.fixture_run?.run_ref);
      cacheProjectTask(data.task);
      if (data.graph) {
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "recover_run_error",
          error: error instanceof Error ? error.message : String(error),
          at: Date.now(),
        });
      }
      setTaskGraphFixtureRunError(error instanceof Error ? error.message : "Run recovery failed.");
    },
  });
  const resolveTaskGraphApproval = useMutation({
    mutationFn: api.resolveTaskGraphApproval,
    onSuccess: (data) => {
      setTaskGraphFixtureRunError(null);
      cacheTaskGraphLiveRunRef(data.run_ref);
      cacheProjectTask(data.task);
      if (data.graph) {
        queryClient.setQueryData(["task-graph", project.project_id, data.task?.task_id ?? currentTask?.task_id ?? null, data.graph.graph_id], {
          graph: data.graph,
          task: data.task ?? currentTask,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
    },
    onError: (error) => {
      setTaskGraphFixtureRunError(error instanceof Error ? error.message : "Approval decision failed.");
    },
  });
  const persistFallbackTaskGraph = (graph: TaskGraphDefinition | null) => {
    if (!currentTask?.task_id) return;
    setFallbackTaskGraph(graph);
    writeFallbackTaskGraph(project.project_id, currentTask.task_id, graph);
  };
  const instantiateFallbackTaskGraph = (templateId: string) => {
    if (!currentTask?.task_id) return;
    const template = taskGraphTemplateList.find((item) => item.template_id === templateId);
    if (!template) return;
    const graph = buildFallbackTaskGraphFromTemplate({
      projectId: project.project_id,
      taskId: currentTask.task_id,
      template,
    });
    persistFallbackTaskGraph(graph);
    setTaskGraphNodeSaveError(null);
    setTaskGraphEdgeSaveError(null);
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setGraphWorkspaceOpen(true);
    setSelectedTaskGraphId(graph.graph_id);
    setSelectedTaskGraphNodeId(graph.nodes[0]?.node_id ?? null);
    setSelectedTaskGraphEdgeId(graph.edges[0]?.edge_id ?? null);
  };
  const saveTaskGraphNodeConfiguration = (nodeId: string, configuration: {
    label: string;
    provider_id: string;
    model_id: string;
    reasoning_effort: string;
    permission_mode: string;
    collaboration_mode: string;
    execution_backend: string;
    human_summary_template: string;
    machine_result_schema: Record<string, unknown>;
    execution_policy: Record<string, unknown>;
    output_contract: Record<string, unknown>;
    approval_gate?: Record<string, unknown>;
    ui_hints: Record<string, unknown>;
  }) => {
    if (!currentTaskGraph) return;
    const optimisticGraph = updateFallbackTaskGraphNodeConfiguration(currentTaskGraph, nodeId, configuration);
    persistFallbackTaskGraph(optimisticGraph);
    setTaskGraphNodeOverrides((current) => ({
      ...current,
      [taskGraphNodeOverrideKey(optimisticGraph.graph_id, nodeId)]: {
        ...(current[taskGraphNodeOverrideKey(optimisticGraph.graph_id, nodeId)] ?? {}),
        ...configuration,
      },
    }));
    setSelectedTaskGraphId(optimisticGraph.graph_id);
    setSelectedTaskGraphNodeId(nodeId);
    setTaskGraphNodeSaveError(null);
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    if (isFallbackTaskGraph(currentTaskGraph) || taskGraphRouteUnavailable) {
      return;
    }
    updateTaskGraphNode.mutate({
      graph_id: currentTaskGraph.graph_id,
      node_id: nodeId,
      configuration,
    });
  };
  const createTaskGraphNode = (payload: {
    kind: string;
    position?: { x: number; y: number } | null;
  }) => {
    if (!currentTaskGraph) return;
    const runtimeKind =
      payload.kind === "planner"
        ? "supervisor"
        : payload.kind === "coder"
          ? "worker"
          : payload.kind === "researcher"
            ? "extractor"
            : payload.kind === "custom"
              ? "artifact_source"
              : payload.kind;
    const uiHints = {
      context_policy_preset: "task_digest",
      palette_role: payload.kind,
    };
    const fallbackCreated = createFallbackTaskGraphNode(currentTaskGraph, {
      kind: runtimeKind,
      position: payload.position,
      ui_hints: uiHints,
    });
    persistFallbackTaskGraph(fallbackCreated.graph);
    setSelectedTaskGraphId(fallbackCreated.graph.graph_id);
    setSelectedTaskGraphNodeId(fallbackCreated.node.node_id);
    setSelectedTaskGraphEdgeId(null);
    setTaskGraphNodeSaveError(null);
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    if (isFallbackTaskGraph(currentTaskGraph) || taskGraphRouteUnavailable) {
      return;
    }
    updateTaskGraphNode.mutate({
      graph_id: currentTaskGraph.graph_id,
      node_id: fallbackCreated.node.node_id,
      create: {
        kind: runtimeKind,
        position: payload.position ?? null,
      },
      configuration: {
        ui_hints: uiHints,
      },
    });
  };
  const moveTaskGraphNode = (nodeId: string, position: { x: number; y: number }) => {
    if (!currentTaskGraph) return;
    const optimisticGraph = updateFallbackTaskGraphNodePosition(currentTaskGraph, nodeId, position);
    persistFallbackTaskGraph(optimisticGraph);
    setTaskGraphNodeOverrides((current) => ({
      ...current,
      [taskGraphNodeOverrideKey(optimisticGraph.graph_id, nodeId)]: {
        ...(current[taskGraphNodeOverrideKey(optimisticGraph.graph_id, nodeId)] ?? {}),
        position,
      },
    }));
    setSelectedTaskGraphId(optimisticGraph.graph_id);
    setSelectedTaskGraphNodeId(nodeId);
    setTaskGraphNodeSaveError(null);
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    if (isFallbackTaskGraph(currentTaskGraph) || taskGraphRouteUnavailable) {
      return;
    }
    updateTaskGraphNode.mutate({
      graph_id: currentTaskGraph.graph_id,
      node_id: nodeId,
      position,
    });
  };
  const saveTaskGraphEdgeConfiguration = (payload: {
    edge_id?: string;
    from_node_id: string;
    to_node_id: string;
    edge_type: string;
    handoff_contract?: TaskGraphDefinition["edges"][number]["handoff_contract"];
    context_policy: TaskGraphDefinition["edges"][number]["context_policy"];
    status?: string;
  }) => {
    if (!currentTaskGraph) return;
    const optimisticGraph = upsertFallbackTaskGraphEdge(currentTaskGraph, {
      edge_id: payload.edge_id,
      from_node_id: payload.from_node_id,
      to_node_id: payload.to_node_id,
      edge_type: payload.edge_type,
      handoff_contract: payload.handoff_contract,
      context_policy: payload.context_policy,
      status: payload.status,
    });
    persistFallbackTaskGraph(optimisticGraph);
    const nextEdge =
      optimisticGraph.edges.find((edge) => edge.edge_id === (payload.edge_id || "")) ??
      optimisticGraph.edges[optimisticGraph.edges.length - 1] ??
      null;
    if (nextEdge) {
      setSelectedTaskGraphEdgeId(nextEdge.edge_id);
    }
    setSelectedTaskGraphId(optimisticGraph.graph_id);
    setTaskGraphEdgeSaveError(null);
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    if (isFallbackTaskGraph(currentTaskGraph) || taskGraphRouteUnavailable) {
      return;
    }
    queryClient.setQueryData(["task-graph", project.project_id, currentTask?.task_id ?? null, optimisticGraph.graph_id], {
      graph: optimisticGraph,
      task: currentTask,
    });
    updateTaskGraphEdge.mutate({
      graph_id: currentTaskGraph.graph_id,
      edge_id: payload.edge_id,
      from_node_id: payload.from_node_id,
      to_node_id: payload.to_node_id,
      edge_type: payload.edge_type,
      handoff_contract: payload.handoff_contract,
      context_policy: payload.context_policy,
      status: payload.status,
    });
  };
  const deleteTaskGraphEdge = (edgeId: string) => {
    if (!currentTaskGraph) return;
    const optimisticGraph = removeFallbackTaskGraphEdge(currentTaskGraph, edgeId);
    if (optimisticGraph === currentTaskGraph) {
      return;
    }
    persistFallbackTaskGraph(optimisticGraph);
    setSelectedTaskGraphId(optimisticGraph.graph_id);
    setSelectedTaskGraphEdgeId(optimisticGraph.edges[0]?.edge_id ?? null);
    setTaskGraphEdgeSaveError(null);
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    if (isFallbackTaskGraph(currentTaskGraph) || taskGraphRouteUnavailable) {
      return;
    }
    queryClient.setQueryData(["task-graph", project.project_id, currentTask?.task_id ?? null, optimisticGraph.graph_id], {
      graph: optimisticGraph,
      task: currentTask,
    });
    saveTaskGraphDefinition.mutate({
      graph: optimisticGraph,
    });
  };
  const openTaskGraphTemplate = (templateId: string) => {
    if (typeof window !== "undefined") {
      document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
        stage: "open_template_requested",
        templateId,
        taskGraphRouteUnavailable,
        currentGraphId: currentTaskGraph?.graph_id ?? null,
        currentTemplateId: currentTaskGraph?.template_id ?? null,
        at: Date.now(),
      });
    }
    console.warn("[task-graph] open template requested", {
      templateId,
      taskGraphRouteUnavailable,
      currentGraphId: currentTaskGraph?.graph_id ?? null,
      currentTemplateId: currentTaskGraph?.template_id ?? null,
    });
    setTaskGraphNodeSaveError(null);
    setTaskGraphEdgeSaveError(null);
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphImportExportError(null);
    if (taskGraphRouteUnavailable) {
      instantiateFallbackTaskGraph(templateId);
      return;
    }
    instantiateTaskGraph.mutate(
      { templateId },
      {
        onSuccess: (data) => {
          if (typeof window !== "undefined") {
            document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
              stage: "open_template_success",
              templateId,
              graphId: data.graph?.graph_id ?? null,
              graphTemplateId: data.graph?.template_id ?? null,
              taskGraphCount: data.task?.graph_definitions?.length ?? null,
              at: Date.now(),
            });
          }
          console.warn("[task-graph] open template mutate success", {
            templateId,
            graphId: data.graph?.graph_id ?? null,
            graphTemplateId: data.graph?.template_id ?? null,
            taskGraphCount: data.task?.graph_definitions?.length ?? null,
          });
        },
        onError: (error) => {
          if (typeof window !== "undefined") {
            document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
              stage: "open_template_error",
              templateId,
              error: error instanceof Error ? error.message : String(error),
              at: Date.now(),
            });
          }
          console.error("[task-graph] open template mutate error", {
            templateId,
            error: error instanceof Error ? error.message : String(error),
          });
          if (error instanceof Error && error.message.includes("Not found")) {
            instantiateFallbackTaskGraph(templateId);
            return;
          }
          setTaskGraphNodeSaveError(error instanceof Error ? error.message : "Failed to instantiate the selected template.");
        },
      },
    );
  };
  const ensurePersistedCurrentTaskGraph = async () => {
    const graphId = currentTaskGraph?.graph_id ?? activeTaskGraphId ?? null;
    if (!graphId || !currentTaskGraph || taskGraphRouteUnavailable) {
      return {
        graphId,
        graph: currentTaskGraph,
      };
    }
    const persistedGraph =
      currentTask?.graph_definitions?.find((graph) => graph.graph_id === graphId) ?? null;
    const persistedGraphIds = (currentTask?.graph_definitions ?? [])
      .map((graph) => graph?.graph_id)
      .filter((value): value is string => Boolean(value));
    const routeGraphId = taskGraph.data?.graph?.graph_id ?? null;
    if (
      !taskGraphNeedsServerPersistence({
        graph: currentTaskGraph,
        persistedGraphIds,
        persistedGraph,
        routeGraphId,
        routeUnavailable: taskGraphRouteUnavailable,
      })
    ) {
      return {
        graphId,
        graph: currentTaskGraph,
      };
    }
    const saved = await saveTaskGraphDefinition.mutateAsync({
      graph: currentTaskGraph,
    });
    return {
      graphId: saved.graph.graph_id,
      graph: saved.graph,
    };
  };
  const runTaskGraphDryRun = async ({ tokenBudget }: { tokenBudget: number }) => {
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    const blockedReason = resolveTaskGraphRunPrecondition({
      actionLabel: "Dry-run",
      currentTaskGraph,
      graphId: currentTaskGraph?.graph_id ?? activeTaskGraphId ?? null,
      routeUnavailable: taskGraphRouteUnavailable,
    });
    if (blockedReason) {
      setTaskGraphDryRunError(blockedReason);
      return;
    }
    try {
      const ensured = await ensurePersistedCurrentTaskGraph();
      if (!ensured.graphId) {
        setTaskGraphDryRunError(
          resolveTaskGraphRunPrecondition({
            actionLabel: "Dry-run",
            currentTaskGraph: ensured.graph,
            graphId: ensured.graphId,
            routeUnavailable: taskGraphRouteUnavailable,
          }) ?? "Dry-run failed.",
        );
        return;
      }
      taskGraphRequestedRunIntentRef.current = {
        kind: "dry_run",
        graphId: ensured.graphId,
        tokenBudget,
        fallbackTriggered: false,
      };
      dryRunTaskGraph.mutate({
        graph_id: ensured.graphId,
        validation_mode: "live",
        budget: { limits: { total_tokens: tokenBudget } },
      });
    } catch (error) {
      taskGraphRequestedRunIntentRef.current = null;
      setTaskGraphDryRunError(error instanceof Error ? error.message : "Dry-run failed.");
    }
  };
  const runTaskGraphLive = async ({ tokenBudget }: { tokenBudget: number }) => {
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    setTaskGraphLiveDispatchStarted(false);
    const blockedReason = resolveTaskGraphRunPrecondition({
      actionLabel: "直接运行",
      currentTaskGraph,
      graphId: currentTaskGraph?.graph_id ?? activeTaskGraphId ?? null,
      routeUnavailable: taskGraphRouteUnavailable,
    });
    if (blockedReason) {
      setTaskGraphFixtureRunError(blockedReason);
      return;
    }
    try {
      const ensured = await ensurePersistedCurrentTaskGraph();
      if (!ensured.graphId) {
        setTaskGraphFixtureRunError(
          resolveTaskGraphRunPrecondition({
            actionLabel: "直接运行",
            currentTaskGraph: ensured.graph,
            graphId: ensured.graphId,
            routeUnavailable: taskGraphRouteUnavailable,
          }) ?? "Live run failed.",
        );
        return;
      }
      taskGraphRequestedRunIntentRef.current = {
        kind: "live",
        graphId: ensured.graphId,
        tokenBudget,
        fallbackTriggered: false,
      };
      primeTaskGraphOptimisticLiveRunRef({
        graphId: ensured.graphId,
        taskId: String(currentTask?.task_id ?? "").trim(),
        entryNodeIds: ensured.graph?.graph_policy?.entry_node_ids,
        budget: { status: "pending", run: { limits: { total_tokens: tokenBudget } } },
        templateId: ensured.graph?.template_id,
      });
      runTaskGraph.mutate({
        graph_id: ensured.graphId,
        budget: { limits: { total_tokens: tokenBudget } },
      });
    } catch (error) {
      taskGraphRequestedRunIntentRef.current = null;
      setTaskGraphLiveDispatchStarted(false);
      clearTaskGraphOptimisticLiveRunRef(currentTaskGraph?.graph_id);
      setTaskGraphFixtureRunError(error instanceof Error ? error.message : "Live run failed.");
    }
  };
  const runTaskGraphFixture = async () => {
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    const blockedReason = resolveTaskGraphRunPrecondition({
      actionLabel: "夹具运行",
      currentTaskGraph,
      graphId: currentTaskGraph?.graph_id ?? activeTaskGraphId ?? null,
      routeUnavailable: taskGraphRouteUnavailable,
    });
    if (blockedReason) {
      setTaskGraphFixtureRunError(blockedReason);
      return;
    }
    try {
      const ensured = await ensurePersistedCurrentTaskGraph();
      if (!ensured.graphId || !ensured.graph) {
        setTaskGraphFixtureRunError(
          resolveTaskGraphRunPrecondition({
            actionLabel: "夹具运行",
            currentTaskGraph: ensured.graph,
            graphId: ensured.graphId,
            routeUnavailable: taskGraphRouteUnavailable,
          }) ?? "Fixture run failed.",
        );
        return;
      }
      startVisibleTaskGraphFixturePending();
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "fixture_run_requested",
          graphId: ensured.graphId,
          templateId: ensured.graph.template_id ?? null,
          taskGraphRouteUnavailable,
          at: Date.now(),
        });
      }
      fixtureRunTaskGraph.mutate({
        graph_id: ensured.graphId,
        branch_behaviors:
          ensured.graph.template_id === "fanout_fanin_research"
            ? { node_research_a: "completed", node_research_b: "blocked" }
            : undefined,
      });
    } catch (error) {
      setTaskGraphFixtureRunError(error instanceof Error ? error.message : "Fixture run failed.");
    }
  };
  const runTaskGraphCancellableFixture = async () => {
    setTaskGraphDryRunResult(null);
    setTaskGraphDryRunError(null);
    setTaskGraphFixtureRunError(null);
    const blockedReason = resolveTaskGraphRunPrecondition({
      actionLabel: "可取消夹具",
      currentTaskGraph,
      graphId: currentTaskGraph?.graph_id ?? activeTaskGraphId ?? null,
      routeUnavailable: taskGraphRouteUnavailable,
    });
    if (blockedReason) {
      setTaskGraphFixtureRunError(blockedReason);
      return;
    }
    try {
      const ensured = await ensurePersistedCurrentTaskGraph();
      if (!ensured.graphId || !ensured.graph) {
        setTaskGraphFixtureRunError(
          resolveTaskGraphRunPrecondition({
            actionLabel: "可取消夹具",
            currentTaskGraph: ensured.graph,
            graphId: ensured.graphId,
            routeUnavailable: taskGraphRouteUnavailable,
          }) ?? "Cancellable fixture run failed.",
        );
        return;
      }
      startVisibleTaskGraphFixturePending();
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "fixture_run_requested",
          graphId: ensured.graphId,
          templateId: ensured.graph.template_id ?? null,
          executionMode: "cancellable",
          taskGraphRouteUnavailable,
          at: Date.now(),
        });
      }
      fixtureRunTaskGraph.mutate({
        graph_id: ensured.graphId,
        execution_mode: "cancellable",
      });
    } catch (error) {
      setTaskGraphFixtureRunError(error instanceof Error ? error.message : "Fixture run failed.");
    }
  };
  const importTaskGraphThroughWorkspace = async () => {
    const graphPath = await promptForText({
      title: "Import orchestration graph",
      label: "Graph file path",
      defaultValue: "examples/agent-orchestration/code_fix_review.json",
      placeholder: "examples/agent-orchestration/code_fix_review.json",
      description: "Use a workspace-relative JSON graph file. The imported graph will become the current task graph in this task.",
      submitLabel: "Import",
    });
    if (graphPath === null) return;
    setTaskGraphImportExportError(null);
    importTaskGraphFile.mutate({ graph_path: graphPath.trim() });
  };
  const exportTaskGraphThroughWorkspace = async () => {
    const ensured = await ensurePersistedCurrentTaskGraph().catch((error) => {
      setTaskGraphImportExportError(error instanceof Error ? error.message : "Failed to prepare the current graph for export.");
      return null;
    });
    const graphId = ensured?.graphId ?? null;
    if (!graphId) return;
    const exportPath = await promptForText({
      title: "Export orchestration graph",
      label: "Export file path",
      defaultValue: `PRIVATE/agent-orchestration/productization/step7/20260707/${graphId}.json`,
      placeholder: `PRIVATE/agent-orchestration/productization/step7/20260707/${graphId}.json`,
      description: "Use a workspace-relative JSON path. The export preview summary will stay visible in the workspace after the file is written.",
      submitLabel: "Export",
    });
    if (exportPath === null) return;
    setTaskGraphImportExportError(null);
    exportTaskGraphFile.mutate({ graph_id: graphId, export_path: exportPath.trim() });
  };
  const createTaskGraphSnapshotFromWorkspace = async () => {
    setTaskGraphSnapshotError(null);
    try {
      const ensured = await ensurePersistedCurrentTaskGraph();
      if (!ensured.graphId) return;
      createTaskGraphSnapshot.mutate({
        graph_id: ensured.graphId,
        reason: "manual_snapshot",
        source_action: "workspace_snapshot",
      });
    } catch (error) {
      setTaskGraphSnapshotError(error instanceof Error ? error.message : "Failed to create a snapshot.");
    }
  };
  const compareSelectedTaskGraphSnapshot = () => {
    const snapshotId = selectedTaskGraphSnapshot?.snapshot_id ?? null;
    if (!snapshotId) return;
    setTaskGraphSnapshotError(null);
    diffTaskGraphSnapshot.mutate({
      snapshot_id: snapshotId,
    });
  };
  const rollbackSelectedTaskGraphSnapshot = () => {
    const snapshotId = selectedTaskGraphSnapshot?.snapshot_id ?? null;
    if (!snapshotId) return;
    setTaskGraphSnapshotError(null);
    rollbackTaskGraphToSnapshot.mutate({
      snapshot_id: snapshotId,
    });
  };
  const cancelLatestTaskGraphRun = () => {
    if (!currentTaskGraphRunRef || taskGraphRouteUnavailable) return;
    setTaskGraphFixtureRunError(null);
    cancelTaskGraphRun.mutate({
      run_id: currentTaskGraphRunRef.run_id,
      notes: "Cancelled from the task graph workspace.",
    });
  };
  const recoverLatestTaskGraphRun = (payload: {
    strategy:
      | "resume_run"
      | "retry_failed_nodes"
      | "rerun_selected_nodes"
      | "partial_execution";
    selectedNodeIds?: string[];
  }) => {
    if (!currentTaskGraphRunRef || taskGraphRouteUnavailable) return;
    if (typeof window !== "undefined") {
      document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
        stage: "recover_run_requested",
        runId: currentTaskGraphRunRef.run_id,
        strategy: payload.strategy,
        selectedNodeIds: payload.selectedNodeIds ?? [],
        at: Date.now(),
      });
    }
    setTaskGraphFixtureRunError(null);
    recoverTaskGraphRun.mutate({
      run_id: currentTaskGraphRunRef.run_id,
      strategy: payload.strategy,
      selected_node_ids: payload.selectedNodeIds ?? null,
    });
  };
  const approveTaskGraphPendingRun = () => {
    if (!currentTaskGraphRunRef || taskGraphRouteUnavailable) return;
    setTaskGraphFixtureRunError(null);
    resolveTaskGraphApproval.mutate({
      run_id: currentTaskGraphRunRef.run_id,
      decision: "approve",
      notes: "Approved from the task graph review gate.",
    });
  };
  const rejectTaskGraphPendingRun = () => {
    if (!currentTaskGraphRunRef || taskGraphRouteUnavailable) return;
    setTaskGraphFixtureRunError(null);
    resolveTaskGraphApproval.mutate({
      run_id: currentTaskGraphRunRef.run_id,
      decision: "reject",
      notes: "Rejected from the task graph review gate.",
    });
  };
  const inspectTaskGraphArtifactPath = (path: string) => {
    setInspectorTab("files");
    setInspectorFileQuery("");
    setInspectorFilePath(path);
    if (!rightSidebarOpen) toggleRightSidebar();
  };
  useEffect(() => {
    const currentProjectNode = projectSidebar.data?.projects.find((item) => item.is_current);
    if (!currentProjectNode || suggestProjectTitle.isPending || !looksGenericProjectTitle(currentProjectNode)) return;
    const key = `project:${currentProjectNode.project_file}:${currentProjectNode.name}`;
    if (titleSuggestionAlreadyAttempted(key)) return;
    markTitleSuggestionAttempted(key);
    suggestProjectTitle.mutate();
  }, [projectSidebar.data?.projects, suggestProjectTitle]);
  useEffect(() => {
    const currentProjectNode = projectSidebar.data?.projects.find((item) => item.is_current);
    const currentTaskNode = currentProjectNode?.tasks.find((item) => item.is_current);
    if (!currentProjectNode || !currentTaskNode || suggestTaskTitle.isPending || !looksGenericTaskTitle(currentTaskNode, currentProjectNode)) return;
    const key = `task:${currentProjectNode.project_file}:${currentTaskNode.task_id}:${currentTaskNode.title}`;
    if (titleSuggestionAlreadyAttempted(key)) return;
    markTitleSuggestionAttempted(key);
    suggestTaskTitle.mutate();
  }, [projectSidebar.data?.projects, suggestTaskTitle]);

  function applyCreatedThread(data: { thread: ShellThread; project?: ProjectFile; task?: ProjectTask }) {
    if (data.task?.task_id) selectedTaskScopeRef.current = data.task.task_id;
    if (data.task) setTaskSelectionGuard(data.task);
    setProject(data.project ?? { ...project, current_thread_id: data.thread.id, recent_threads: [data.thread.id, ...project.recent_threads.filter((id) => id !== data.thread.id)].slice(0, 20) });
    cacheProjectTask(data.task);
    if (data.thread.shellSettings) {
      setThreadSettingsDraft(data.thread.id, data.thread.shellSettings);
    }
    setThreadCreateRecovery(null);
    setTaskCreationPending(null);
    invalidateRestoreStateQueries(queryClient);
  }

  const createThread = useMutation({ mutationFn: api.createThread });

  const beginThreadCreate = useMutation({
    mutationFn: api.beginThreadCreate,
    onSuccess: (data) => {
      if (data.status === "completed" && data.thread) {
        applyCreatedThread({ thread: data.thread, project: data.project, task: data.task });
      }
    },
  });

  const recoverThreadCreate = useMutation({
    mutationFn: api.recoverThreadCreate,
    onSuccess: (data) => {
      if (data.status !== "completed" || !data.thread) return;
      applyCreatedThread({ thread: data.thread, project: data.project, task: data.task });
      createThread.reset();
    },
  });

  useEffect(() => {
    if (!taskCreationPending || beginThreadCreate.isPending || recoverThreadCreate.isPending) return;
    if (!threadCreateRecovery || threadCreateRecovery.operationId !== taskCreationPending.operationId) return;
    if (taskCreationPending.recoveryAttempts >= THREAD_CREATE_RECOVERY_MAX_ATTEMPTS) {
      setTaskCreationPending(null);
      return;
    }
    const timeoutId = window.setTimeout(() => {
      void recoverThreadCreate
        .mutateAsync({ profile_id: threadCreateRecovery.profileId, operation_id: taskCreationPending.operationId })
        .then((data) => {
          if (data.status === "failed") {
            setTaskCreationPending(null);
            return;
          }
          if (data.status === "pending") {
            setTaskCreationPending((current) => {
              if (!current || current.operationId !== taskCreationPending.operationId) return current;
              return { ...current, recoveryAttempts: current.recoveryAttempts + 1 };
            });
          }
        })
        .catch(() => {
          setTaskCreationPending((current) => {
            if (!current || current.operationId !== taskCreationPending.operationId) return current;
            return { ...current, recoveryAttempts: current.recoveryAttempts + 1 };
          });
        });
    }, THREAD_CREATE_RECOVERY_DELAY_MS);
    return () => window.clearTimeout(timeoutId);
  }, [beginThreadCreate.isPending, recoverThreadCreate, taskCreationPending, threadCreateRecovery]);

  const forkThread = useMutation({
    mutationFn: api.forkThread,
    onSuccess: (data) => {
      setProject(data.project ?? { ...project, current_thread_id: data.thread.id, recent_threads: [data.thread.id, ...project.recent_threads.filter((id) => id !== data.thread.id)].slice(0, 20) });
      cacheProjectTask(data.task);
      invalidateRestoreStateQueries(queryClient);
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
      cacheProjectTask(data.task);
      setComposerText("");
      setAttachments([]);
      setSendFailure(null);
      setSendStage(null);
      invalidateRestoreStateQueries(queryClient);
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
    const fallbackThreadId = fallbackThreadIdForEmptyTaskContext({
      currentTask,
      selectedThreadId,
      threads: threads.data?.threads ?? null,
    });
    if (fallbackThreadId) {
      switchThread.mutate(fallbackThreadId);
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
    ? {
        objective: goal.data.goal.objective,
        status: goal.data.goal.status,
        source: "thread" as const,
        tokenBudget: goal.data.goal.tokenBudget,
        tokensUsed: goal.data.goal.tokensUsed,
        timeUsedSeconds: goal.data.goal.timeUsedSeconds,
        updatedAt: goal.data.goal.updatedAt,
      }
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
  const inspectorFileMediaUrl = useQuery({
    queryKey: ["project-file-media-url", inspectorFilePath],
    queryFn: () => api.projectFileMediaUrl(inspectorFilePath),
    enabled: inspectorTab === "files" && Boolean(inspectorFilePath),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const inspectorFilePreviewError =
    inspectorFilePreview.error instanceof Error ? inspectorFilePreview.error.message : inspectorFilePreview.error ? String(inspectorFilePreview.error) : "";
  const inspectorFileMediaError =
    inspectorFileMediaUrl.error instanceof Error ? inspectorFileMediaUrl.error.message : inspectorFileMediaUrl.error ? String(inspectorFileMediaUrl.error) : "";
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
    const workflowModeControl = root?.querySelector('[data-composer="workflow-mode"]') as HTMLSelectElement | null;
    const legacyCollaborationModeControl = root?.querySelector('[data-composer="collaboration-mode"]') as HTMLSelectElement | null;
    const workflowMode = workflowModeControl?.value;
    const domSettings = {
      profile_id: profileControl?.value,
      model: modelControl?.value,
      reasoning_effort: effortControl?.value,
      permission_mode: permissionControl?.value as PermissionMode | undefined,
      collaboration_mode: (workflowMode ? (workflowMode === "plan" ? "plan" : "default") : legacyCollaborationModeControl?.value) as CollaborationMode | undefined,
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
  const mergedComposerCatalogModels = useMemo(
    () => mergeComposerCatalogModels(llmSession.data?.mode, llmCatalog.data?.models ?? [], routerConfig.data?.models ?? []),
    [llmCatalog.data?.models, llmSession.data?.mode, routerConfig.data?.models],
  );
  const pickPreferredModelForProvider = (providerId: string) => {
    const candidates = mergedComposerCatalogModels
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
    for (const model of mergedComposerCatalogModels) {
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
  }, [activeProfile?.model, activeProfile?.provider_id, activeSettings.model, llmSession.data?.mode, mergedComposerCatalogModels, runtimeModelList.data?.models]);
  const activeModelEntry = useMemo(() => {
    const providerId = activeProfile?.provider_id ?? "";
    return (
      mergedComposerCatalogModels.find((model) => model.provider === providerId && model.native_model === activeSettings.model) ??
      null
    );
  }, [activeProfile?.provider_id, activeSettings.model, mergedComposerCatalogModels]);
  const activeModelAuthority = useMemo(() => modelAuthorityState(activeModelEntry), [activeModelEntry]);
  const speechTranscribeRoute = useMemo(
    () => (routerConfig.data?.capability_routes ?? []).find((route) => route.capability_id === "speech.transcribe") ?? null,
    [routerConfig.data?.capability_routes],
  );
  const speechTranscribeReady = speechTranscribeRoute?.resolution_status === "ok" && Boolean(speechTranscribeRoute.resolved_candidate);
  const voiceButtonTitle =
    voiceRecorderState === "recording"
      ? locale === "zh-CN"
        ? "停止录音并识别"
        : "Stop recording and transcribe"
      : voiceRecorderState === "transcribing"
        ? locale === "zh-CN"
          ? "正在识别语音"
          : "Transcribing speech"
        : speechTranscribeReady
          ? locale === "zh-CN"
            ? "语音输入"
            : "Voice input"
          : locale === "zh-CN"
            ? "配置语音识别模型"
            : "Configure speech recognition";
  const composerEffortOptions = useMemo(
    () => composerReasoningOptions(activeModelEntry, activeProfile, activeSettings.reasoning_effort),
    [activeModelEntry, activeProfile, activeSettings.reasoning_effort],
  );
  const sendableAttachments = attachments.filter((attachment) => !attachment.error && attachment.path.trim());
  const imageAttachmentRoute = imageAttachmentRouteState({
    hasImageAttachments: sendableAttachments.some((attachment) => attachment.kind === "image"),
    model: activeModelEntry,
  });
  const imageAttachmentUnsupported = imageAttachmentRoute !== "ready";
  const imageAttachmentRouteMessage = imageAttachmentRoute === "runtime_unverified"
    ? locale === "zh-CN"
      ? "当前 App Server 路由尚未验证图片传输；请改用已验证视觉路由。"
      : "The current App Server route has not verified image transport. Choose a verified vision route."
    : locale === "zh-CN"
      ? "当前模型不支持图片输入；请移除图片或切换视觉模型。"
      : "The current model does not support image input. Remove images or choose a vision model.";
  const attachmentRouteLine = sendableAttachments.length
    ? [
        attachmentRouteSummary(locale, sendableAttachments),
        imageAttachmentUnsupported
          ? locale === "zh-CN"
            ? "图片输入未验证"
            : "Image input unverified"
          : [activeProfile?.provider_id, activeSettings.model].filter(Boolean).join(" / "),
      ]
        .filter(Boolean)
        .join(" · ")
    : "";
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
  const suppressStaleRuntimeError = latestCompletedTurnSuppressesRuntimeError(selectedThread.data?.thread);
  const displayedRuntimeError = suppressStaleRuntimeError ? null : supervisor.data?.runtime_error ?? null;
  const supervisorForDisplay = suppressStaleRuntimeError && supervisor.data
    ? { ...supervisor.data, runtime_error: null }
    : supervisor.data;
  const runtimeRecoveryActions = runtimeErrorNoticeActions(displayedRuntimeError);
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
  const runtimeErrorText = runtimeErrorNoticeText(displayedRuntimeError);
  const composerFailureNotice = keySetupMessage
    ? ""
    : composerFailureNoticeText(sendFailure, displayedRuntimeError);
  const conversationNotices = [
    ...(needsKeySetup ? [{ key: "key-setup", text: t(locale, "key_setup_missing_inline"), tone: "danger" as const, action: "setup" as const }] : []),
    ...(keySetupMessage ? [{ key: "key-failure", text: keySetupMessage, tone: "danger" as const, action: "setup" as const }] : []),
    ...capabilityWarnings.map((warning, index) => ({ key: `capability-${index}`, text: warning, tone: "warning" as const })),
    ...(runtimeErrorText ? [{
      key: "runtime-error",
      text: runtimeErrorText,
      tone: "danger" as const,
    }] : []),
    ...(composerFailureNotice ? [{ key: "composer-failure", text: composerFailureNotice, tone: "danger" as const }] : []),
    ...(supervisor.data?.guard.message ? [{ key: "context-guard", text: supervisor.data.guard.message, tone: supervisor.data.guard.level === "pause" ? "danger" as const : "warning" as const }] : []),
    ...(supervisor.data?.watchdog?.message ? [{ key: "turn-watchdog", text: supervisor.data.watchdog.message, tone: supervisor.data.watchdog.level === "pause" ? "danger" as const : "warning" as const }] : []),
  ];

  useEffect(() => {
    document.documentElement.dataset.appearance = appearance;
  }, [appearance]);

  useEffect(() => () => cleanupVoiceRecordingResources(), []);

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
        cursor_enhancement: cursorEnhancement,
        execution_host: executionHostDraft,
        wsl_distro: executionHostDraft === "wsl" ? wslDistroDraft : "",
        left_sidebar_open: leftSidebarOpen,
        left_sidebar_width: leftPane.width,
        right_sidebar_width: rightPane.width,
        right_sidebar_open: rightSidebarOpen,
      });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [appearance, cursorEnhancement, executionHostDraft, leftPane.width, leftSidebarOpen, locale, project?.project_id, rightPane.width, rightSidebarOpen, wslDistroDraft]);

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
        mergedComposerCatalogModels.find((model) => model.provider === activeProfile.provider_id && model.native_model === nextModel) ??
        null;
      const nextEfforts = composerReasoningOptions(nextModelEntry, activeProfile, activeSettings.reasoning_effort);
      updateComposerSettings({
        model: nextModel,
        reasoning_effort: nextEfforts.includes(activeSettings.reasoning_effort ?? "")
          ? activeSettings.reasoning_effort
          : preferredReasoningEffort(nextModelEntry, activeProfile, activeSettings.reasoning_effort),
      });
    }
  }, [activeProfile, activeSettings.model, activeSettings.reasoning_effort, composerModelOptions, mergedComposerCatalogModels]);

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
      } else if (method === "error") {
        const scopedThreadId = threadId || selectedThreadId || "";
        const latestSnapshot = useAppStore.getState().eventSnapshot;
        const scopedTurnId = turnId || (scopedThreadId ? latestSnapshot.latestTurnIdByThread[scopedThreadId] ?? "" : "");
        const message = String(params.message ?? params.additionalDetails ?? "Model runtime ended with an error.")
          .replace(/\s+/g, " ")
          .trim()
          .slice(0, 280);
        if (scopedTurnId) runtimeErrorsByTurnRef.current[scopedTurnId] = message;
      } else if (method === "item/completed") {
        const item = (params.item as Record<string, unknown> | undefined) ?? {};
        const activity = itemActivityFromPayload(item, "completed");
        if (activity && threadId && turnId) setTurnActivity(threadId, turnId, activity);
        if (item.type === "contextCompaction") threadRefresh = true;
      } else if (method === "turn/completed") {
        const scopedThreadId = threadId || selectedThreadId || "";
        const latestSnapshot = useAppStore.getState().eventSnapshot;
        const latestLiveTurnId = scopedThreadId ? latestSnapshot.latestTurnIdByThread[scopedThreadId] ?? "" : "";
        const scopedTurnId = turnId || latestLiveTurnId;
        const isCurrentLiveTurn = Boolean(scopedThreadId && scopedTurnId && latestLiveTurnId === scopedTurnId);
        const terminalError = scopedTurnId ? runtimeErrorsByTurnRef.current[scopedTurnId] : undefined;
        if (scopedTurnId) delete runtimeErrorsByTurnRef.current[scopedTurnId];
        if (scopedThreadId) {
          setThreadStatus(scopedThreadId, { type: "idle" });
          if (scopedTurnId && isCurrentLiveTurn) clearLiveTurn(scopedThreadId, scopedTurnId);
        }
        if (terminalError && isCurrentLiveTurn) {
          setSendStage(null);
          setSendFailure(locale === "zh-CN" ? `模型运行失败：${terminalError}` : `Model run failed: ${terminalError}`);
        } else if (isCurrentLiveTurn) {
          setSendStage(null);
          setSendFailure(null);
        }
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
            detail: "Task context was compacted and the surviving summary is now the active continuation point.",
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

  function openSetupTab(nextTab: SetupTab, options?: { extensionKind?: ExtensionInventoryInitialKind }) {
    if (options?.extensionKind) setSetupExtensionsKind(options.extensionKind);
    setSetupInitialTab(nextTab);
    setMainView("setup");
  }

  async function handleCreateThread() {
    if (createThread.isPending || beginThreadCreate.isPending || taskCreationPending) return;
    const name = await promptForText({
      title: t(locale, "new_thread"),
      label: t(locale, "title_thread"),
      defaultValue: "",
      placeholder: t(locale, "new_thread"),
      submitLabel: t(locale, "new_thread"),
    });
    if (name === null) return;
    const settings = currentComposerSettings();
    const profileId = settings.profile_id ?? project.default_profile_id;
    const operationId = newThreadCreateOperationId();
    const taskName = name.trim() || t(locale, "new_thread");
    // A new task must not race an auto-continuing goal from the task being left.
    pauseGoalForUserInsertion();
    createThread.reset();
    beginThreadCreate.reset();
    recoverThreadCreate.reset();
    setThreadCreateRecovery({ operationId, profileId });
    setTaskCreationPending({ name: taskName, operationId, recoveryAttempts: 0 });
    try {
      const started = await beginThreadCreate.mutateAsync({
        profile_id: profileId,
        model: settings.model,
        effort: settings.reasoning_effort,
        permission_mode: settings.permission_mode,
        name: name.trim() || undefined,
        operation_id: operationId,
      });
      if (started.status === "failed") {
        setTaskCreationPending(null);
      }
    } catch {
      // The start request can be interrupted after the sidecar accepted the
      // operation. Keep the same idempotent operation pending so the existing
      // recovery loop can read its terminal state without starting a second
      // provider thread or returning the user to the old task context.
    }
  }

  async function handleForkThread() {
    if (!selectedThreadId) return;
    const name = await promptForText({
      title: locale === "zh-CN" ? "创建分支任务" : t(locale, "fork_thread"),
      label: t(locale, "title_thread"),
      defaultValue: "",
      placeholder: activeThreadName,
      submitLabel: locale === "zh-CN" ? "创建分支任务" : t(locale, "fork_thread"),
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

  function toggleSidebarProject(projectKey: string) {
    setExpandedSidebarProjects((current) => {
      const next = new Set(current);
      if (next.has(projectKey)) next.delete(projectKey);
      else next.add(projectKey);
      return next;
    });
  }

  function cacheSidebarTask(projectId: string, task: ProjectTask | null | undefined) {
    if (!task) return;
    queryClient.setQueryData<ProjectTasksResponse>(["project-tasks", projectId], (current) => mergeProjectTaskResponse(current, task));
  }

  function invalidateSidebarSelection(projectId?: string) {
    queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
    queryClient.invalidateQueries({ queryKey: ["threads"] });
    queryClient.invalidateQueries({ queryKey: ["thread"] });
    queryClient.invalidateQueries({ queryKey: ["task-conversation"] });
    if (projectId) queryClient.invalidateQueries({ queryKey: ["project-tasks", projectId] });
    invalidateRestoreStateQueries(queryClient);
  }

  async function ensureSidebarProjectOpen(projectNode: SidebarProjectNode) {
    if (projectNode.is_current || projectNode.project_file === project.project_file) return project;
    const opened = await openProjectFromSidebar.mutateAsync(projectNode.project_file);
    return opened.project;
  }

  async function selectSidebarTask(projectNode: SidebarProjectNode, taskNode: SidebarTaskNode) {
    if (
      isSidebarTaskAlreadySelected({
        currentProject: project,
        currentTask,
        projectNode,
        taskNode,
      })
    ) {
      selectedTaskScopeRef.current = taskNode.task_id;
      setSidebarSelectionError(null);
      setPendingSidebarProjectKey(null);
      setPendingSidebarTask(null);
      setMainView("chat");
      return;
    }
    const previousTaskScopeId = selectedTaskScopeRef.current;
    selectedTaskScopeRef.current = taskNode.task_id;
    setSidebarSelectionBusy(true);
    setSidebarSelectionError(null);
    setPendingSidebarProjectKey(sidebarProjectKey(projectNode));
    setPendingSidebarTask(optimisticSidebarTask(projectNode, taskNode));
    try {
      setMainView("chat");
      const openedProject = await ensureSidebarProjectOpen(projectNode);
      const switched = await api.switchTask(taskNode.task_id);
      setProject(switched.project);
      setPendingSidebarTask(switched.task ?? optimisticSidebarTask(projectNode, taskNode));
      setTaskSelectionGuard(switched.task);
      cacheSidebarTask(switched.project.project_id || openedProject.project_id, switched.task);
      invalidateSidebarSelection(switched.project.project_id || openedProject.project_id);
    } catch (error) {
      selectedTaskScopeRef.current = previousTaskScopeId;
      setPendingSidebarProjectKey(null);
      setPendingSidebarTask(null);
      setSidebarSelectionError(error instanceof Error ? error.message : "Unable to switch tasks.");
    } finally {
      setSidebarSelectionBusy(false);
    }
  }

  async function selectSidebarProject(projectNode: SidebarProjectNode) {
    setSidebarSelectionBusy(true);
    try {
      setMainView("chat");
      await ensureSidebarProjectOpen(projectNode);
      setExpandedSidebarProjects((current) => new Set([...current, sidebarProjectKey(projectNode)]));
    } finally {
      setSidebarSelectionBusy(false);
    }
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
    const currentTitle = visibleThreadTitle(current?.displayName);
    const name = await promptForText({
      title: t(locale, "rename_thread"),
      label: t(locale, "title_thread"),
      defaultValue: currentTitle,
      placeholder: currentTitle,
      submitLabel: t(locale, "rename_thread"),
    });
    if (name && name.trim()) {
      renameThread.mutate({ threadId, name: name.trim() });
    }
  }

  function appendAttachmentDrafts(drafts: AttachmentDraft[]) {
    if (drafts.length === 0) return;
    let duplicateCount = 0;
    setAttachments((current) => {
      const seen = new Set(current.map(attachmentIdentity));
      const next = [...current];
      for (const draft of drafts) {
        const normalized = normalizeStagedAttachmentDraft(draft);
        const key = attachmentIdentity(normalized);
        if (seen.has(key)) {
          duplicateCount += 1;
          continue;
        }
        seen.add(key);
        next.push(normalized);
      }
      return next;
    });
    if (duplicateCount > 0) {
      setAttachmentNotice(locale === "zh-CN" ? `已跳过 ${duplicateCount} 个重复附件。` : `Skipped ${duplicateCount} duplicate attachment${duplicateCount === 1 ? "" : "s"}.`);
    }
  }

  function attachmentErrorDraft(name: string, reason: string): AttachmentDraft {
    return {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}-${name}`,
      path: "",
      name,
      mimeType: "application/octet-stream",
      kind: "file",
      error: reason,
      source: "browser_upload",
    };
  }

  async function stageBrowserAttachmentCandidates(candidates: BrowserAttachmentCandidate[], directoryName?: string | null) {
    const usable = candidates.slice(0, BROWSER_ATTACHMENT_MAX_FILES);
    const skippedForCount = Math.max(0, candidates.length - usable.length);
    const totalBytes = usable.reduce((total, candidate) => total + candidate.file.size, 0);
    if (totalBytes > BROWSER_ATTACHMENT_MAX_TOTAL_BYTES) {
      appendAttachmentDrafts([
        attachmentErrorDraft(
          directoryName || (locale === "zh-CN" ? "附件过大" : "Attachment too large"),
          locale === "zh-CN" ? "附件总大小超过浏览器上传上限，请改用本地路径或拆分后再添加。" : "The selected attachments exceed the browser upload limit. Split them or add fewer files.",
        ),
      ]);
      return;
    }
    try {
      setAttachmentNotice(locale === "zh-CN" ? "正在添加附件..." : "Adding attachments...");
      const files = await Promise.all(usable.map(fileToStageFile));
      const response = await api.stageAttachments({ files, directory_name: directoryName ?? null });
      appendAttachmentDrafts(response.attachments);
      const skipped = [...(response.skipped ?? [])];
      if (skippedForCount > 0) skipped.push({ name: "limit", reason: `${skippedForCount} files exceeded the count limit.` });
      if (skipped.length > 0) {
        setAttachmentNotice(locale === "zh-CN" ? `${skipped.length} 个附件未加入；可展开附件卡查看或重试。` : `${skipped.length} attachment${skipped.length === 1 ? "" : "s"} could not be added.`);
        appendAttachmentDrafts(skipped.slice(0, 3).map((item) => attachmentErrorDraft(item.name, item.reason)));
      } else {
        setAttachmentNotice(null);
      }
    } catch (error) {
      setAttachmentNotice(describeSendError(locale === "zh-CN" ? "添加附件" : "add attachments", error));
    }
  }

  async function handleBrowserFileSelection(fileList: FileList | null, directoryMode = false) {
    const candidates = [...(fileList ?? [])].map((file) => ({
      file,
      relativePath: (file as File & { webkitRelativePath?: string }).webkitRelativePath || undefined,
    }));
    if (candidates.length === 0) return;
    await stageBrowserAttachmentCandidates(candidates, directoryMode ? directoryNameFromCandidates(candidates) : null);
  }

  function handleAddAttachments() {
    setAttachmentMenuOpen((value) => !value);
  }

  async function chooseAttachmentFiles() {
    setAttachmentMenuOpen(false);
    if (isTauri()) {
      const paths = await selectAttachmentFiles(t(locale, "add_files"));
      appendAttachmentDrafts(paths.map((path) => attachmentDraftFromPath(path)));
      return;
    }
    fileInputRef.current?.click();
  }

  async function chooseAttachmentFolder() {
    setAttachmentMenuOpen(false);
    if (isTauri()) {
      const path = await selectAttachmentDirectory(locale === "zh-CN" ? "选择附件文件夹" : "Select attachment folder");
      if (path) appendAttachmentDrafts([attachmentDraftFromPath(path, "folder")]);
      return;
    }
    directoryInputRef.current?.click();
  }

  async function handleComposerDrop(event: DragEvent<HTMLElement>) {
    if (!dataTransferHasFiles(event.dataTransfer)) return;
    event.preventDefault();
    setAttachmentDropActive(false);
    const candidates = await filesFromDataTransfer(event.dataTransfer);
    if (candidates.length === 0) return;
    await stageBrowserAttachmentCandidates(candidates, directoryNameFromCandidates(candidates));
  }

  async function handleComposerPaste(event: ClipboardEvent<HTMLElement>) {
    const clipboardData = event.clipboardData;
    if (!clipboardData || !dataTransferHasFiles(clipboardData)) return;
    event.preventDefault();
    const candidates = await filesFromDataTransfer(clipboardData);
    if (candidates.length === 0) return;
    await stageBrowserAttachmentCandidates(candidates, directoryNameFromCandidates(candidates));
  }

  function cleanupVoiceRecordingResources() {
    voiceRecorderRef.current = null;
    voiceChunksRef.current = [];
    if (voiceStreamRef.current) {
      for (const track of voiceStreamRef.current.getTracks()) {
        track.stop();
      }
      voiceStreamRef.current = null;
    }
  }

  function openSpeechTranscribeSetup(message?: string) {
    const routeError = String(speechTranscribeRoute?.error || "").trim();
    const suffix = message || routeError;
    setSendStage(null);
    setSendFailure(
      locale === "zh-CN"
        ? `请先在“设置 -> 更多能力 -> 多模态能力”中配置语音识别模型。${suffix ? ` ${suffix}` : ""}`
        : `Configure a speech recognition model in Settings -> More abilities -> Multimodal capabilities first.${suffix ? ` ${suffix}` : ""}`,
    );
    openSetupTab("capabilities");
  }

  async function transcribeVoiceBlob(blob: Blob) {
    if (blob.size <= 0) {
      setVoiceRecorderState("idle");
      setSendStage(null);
      setSendFailure(locale === "zh-CN" ? "没有录到可识别的音频，请重试。" : "No usable audio was recorded. Try again.");
      return;
    }
    if (blob.size > VOICE_RECORDING_MAX_BYTES) {
      setVoiceRecorderState("idle");
      setSendStage(null);
      setSendFailure(locale === "zh-CN" ? "录音过长，请缩短后重试。" : "The recording is too large. Try a shorter recording.");
      return;
    }
    try {
      setVoiceRecorderState("transcribing");
      setSendFailure(null);
      setSendStage(locale === "zh-CN" ? "正在识别语音..." : "Transcribing speech...");
      const dataUri = await blobToDataUri(blob);
      const response = await api.invokeCapability({
        capability_id: "speech.transcribe",
        payload: {
          audio_inputs: [{ data_uri: dataUri, mime_type: blob.type || "audio/webm" }],
          language_hint: locale === "zh-CN" ? "zh" : "",
          enable_itn: true,
        },
      });
      const text = typeof response.result.text === "string" ? response.result.text.trim() : "";
      if (!text) {
        throw new Error(locale === "zh-CN" ? "语音识别没有返回文本。" : "Speech transcription returned no text.");
      }
      setComposerText((current) => (current.trim() ? `${current.trimEnd()}\n${text}` : text));
      setSendStage(null);
      setSendFailure(null);
    } catch (error) {
      setSendStage(null);
      setSendFailure(describeSendError(locale === "zh-CN" ? "语音识别" : "speech transcription", error));
    } finally {
      setVoiceRecorderState("idle");
    }
  }

  function stopVoiceRecording() {
    const recorder = voiceRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
      return;
    }
    cleanupVoiceRecordingResources();
    setVoiceRecorderState("idle");
    setSendStage(null);
  }

  async function handleVoiceTranscribeClick() {
    if (voiceRecorderState === "transcribing") return;
    if (voiceRecorderState === "recording") {
      stopVoiceRecording();
      return;
    }
    if (!speechTranscribeReady) {
      openSpeechTranscribeSetup();
      return;
    }
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia || typeof window.MediaRecorder === "undefined") {
      setSendFailure(locale === "zh-CN" ? "当前浏览器不支持麦克风录音，请使用支持 MediaRecorder 的桌面环境。" : "This browser does not support microphone recording. Use a desktop environment with MediaRecorder support.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = supportedVoiceRecordingMimeType();
      const recorder = new window.MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      voiceChunksRef.current = [];
      voiceStreamRef.current = stream;
      voiceRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          voiceChunksRef.current.push(event.data);
        }
      };
      recorder.onerror = () => {
        cleanupVoiceRecordingResources();
        setVoiceRecorderState("idle");
        setSendStage(null);
        setSendFailure(locale === "zh-CN" ? "录音失败，请检查麦克风权限后重试。" : "Recording failed. Check microphone permissions and try again.");
      };
      recorder.onstop = () => {
        const chunks = [...voiceChunksRef.current];
        const recordedMimeType = recorder.mimeType || mimeType || "audio/webm";
        cleanupVoiceRecordingResources();
        void transcribeVoiceBlob(new Blob(chunks, { type: recordedMimeType }));
      };
      recorder.start();
      setVoiceRecorderState("recording");
      setSendFailure(null);
      setSendStage(locale === "zh-CN" ? "正在录音... 再次点击麦克风结束并识别。" : "Recording... Click the microphone again to stop and transcribe.");
    } catch (error) {
      cleanupVoiceRecordingResources();
      setVoiceRecorderState("idle");
      setSendStage(null);
      setSendFailure(describeSendError(locale === "zh-CN" ? "访问麦克风" : "microphone access", error));
    }
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

  function setThreadGoal(status: "active" | "paused" | "blocked" | "usageLimited" | "budgetLimited" | "complete", objective?: string) {
    const text = (objective ?? goalDraft ?? displayGoal?.objective ?? "").trim();
    if (!selectedThreadId || !text) return;
    setGoalMutation.mutate({
      thread_id: selectedThreadId,
      profile_id: activeSettings.profile_id,
      objective: text,
      status,
      token_budget: goal.data?.goal?.tokenBudget ?? null,
    });
    setGoalRunnerArmed(status === "active");
    if (status === "active") {
      setGoalEditMode(false);
      setGoalDockExpanded(true);
    }
  }

  function clearThreadGoal() {
    if (!selectedThreadId) return;
    setGoalRunnerArmed(false);
    setGoalDockExpanded(false);
    setGoalEditMode(false);
    clearGoalMutation.mutate({ threadId: selectedThreadId, profileId: activeSettings.profile_id });
  }

  function pauseGoalForUserInsertion() {
    if (goal.data?.goal?.status !== "active" || !selectedThreadId) return;
    setGoalRunnerArmed(false);
    setGoalMutation.mutate({
      thread_id: selectedThreadId,
      profile_id: activeSettings.profile_id,
      objective: goal.data.goal.objective,
      status: "paused",
      token_budget: goal.data.goal.tokenBudget ?? null,
    });
  }

  async function submitTurnText(text: string, draftAttachments: AttachmentDraft[] = []) {
    setSendFailure(null);
    const trimmedText = text.trim();
    if (!trimmedText && draftAttachments.length === 0) return false;
    if (!sendTargetThreadId) {
      const threadStage = t(locale, "send_stage_thread");
      const turnStage = sendStageWithAttachments(locale, t(locale, "send_stage_turn"), draftAttachments);
      let currentStage = threadStage;
      const settings = currentComposerSettings();
      try {
        setSendStage(currentStage);
        const operationId = newThreadCreateOperationId();
        const profileId = settings.profile_id ?? project.default_profile_id;
        setThreadCreateRecovery({ operationId, profileId });
        const selectedTaskId = resolveTaskIdForNewThread({
          selectedTaskId: selectedTaskScopeRef.current,
          conversationTaskId: taskConversation.data?.task?.task_id,
          currentTask,
        });
        const created = await createThread.mutateAsync({
          profile_id: profileId,
          model: settings.model,
          effort: settings.reasoning_effort,
          permission_mode: settings.permission_mode,
          task_id: selectedTaskId,
          operation_id: operationId,
        });
        if (selectedTaskId && created.task?.task_id && created.task.task_id !== selectedTaskId) {
          setSendFailure(locale === "zh-CN"
            ? "新建执行线路未绑定到当前任务，已阻止发送。请重新选择任务后重试。"
            : "The new execution lane was not bound to the selected task. Sending was blocked; select the task again and retry.");
          setSendStage(null);
          return false;
        }
        applyCreatedThread(created);
        currentStage = turnStage;
        setSendStage(currentStage);
        const result = await startTurn.mutateAsync({
          thread_id: created.thread.id,
          profile_id: settings.profile_id,
          text: trimmedText,
          attachments: draftAttachments,
          model: settings.model,
          effort: settings.reasoning_effort,
          permission_mode: settings.permission_mode,
          collaboration_mode: settings.collaboration_mode,
          execution_policy: composerExecutionPolicy,
        });
        const pendingNotice = result.background_start ? attachmentPendingNotice(locale, result.attachment_diagnostics, result.warning) : "";
        setSendStage(pendingNotice || null);
        return true;
      } catch (error) {
        setSendFailure(describeSendError(currentStage, error));
        setSendStage(null);
        return false;
      }
    }
      const turnStage = sendStageWithAttachments(locale, t(locale, "send_stage_turn"), draftAttachments);
      const settings = currentComposerSettings();
      try {
        setSendStage(turnStage);
        const result = await startTurn.mutateAsync({
          thread_id: sendTargetThreadId,
          profile_id: settings.profile_id,
          text: trimmedText,
          attachments: draftAttachments,
          model: settings.model,
        effort: settings.reasoning_effort,
        permission_mode: settings.permission_mode,
        collaboration_mode: settings.collaboration_mode,
        execution_policy: composerExecutionPolicy,
      });
      const pendingNotice = result.background_start ? attachmentPendingNotice(locale, result.attachment_diagnostics, result.warning) : "";
      setSendStage(pendingNotice || null);
      return true;
    } catch (error) {
      setSendFailure(describeSendError(turnStage, error));
      setSendStage(null);
      return false;
    }
  }

  async function handleSend() {
    const text = composerText.trim();
    const draftAttachments = sendableAttachments;
    if (!text && draftAttachments.length === 0) return;

    if (canInterrupt && liveTurnId && selectedThreadId) {
      pauseGoalForUserInsertion();
      setInstructionQueue((current) => [
        ...current,
        {
          id: `${Date.now()}-${current.length}`,
          text,
          attachments: draftAttachments,
          targetThreadId: sendTargetThreadId ?? selectedThreadId,
        },
      ]);
      setInstructionQueueExpanded(true);
      setInstructionQueueEditingId(null);
      setInstructionQueueBlockedId(null);
      setComposerText("");
      setAttachments([]);
      setSendFailure(null);
      setSendStage(locale === "zh-CN" ? "已加入指令队列，当前轮结束后优先处理。" : "Queued. It will run after the current turn finishes.");
      return;
    }

    await submitTurnText(text, draftAttachments);
  }

  function submitPlanFeedback(kind: "approve" | "adjust", feedback?: string) {
    const text =
      kind === "approve"
        ? locale === "zh-CN"
          ? "我同意这个计划，请开始实施。"
          : "I approve this plan. Please start implementation."
        : locale === "zh-CN"
          ? `请根据以下调整重新制定计划：\n${feedback?.trim() ?? ""}`
          : `Please revise the plan with these changes:\n${feedback?.trim() ?? ""}`;
    if (!sendTargetThreadId) {
      setComposerText(text);
      return;
    }
    void submitTurnText(text, []);
  }

  function saveQueuedInstruction(id: string, text: string) {
    setInstructionQueue((current) =>
      current.map((item) => (item.id === id ? { ...item, text: text.trim() } : item)),
    );
    setInstructionQueueEditingId(null);
    setInstructionQueueBlockedId(null);
  }

  function editQueuedInstruction(id: string) {
    setInstructionQueueExpanded(true);
    setInstructionQueueEditingId(id);
    setInstructionQueueBlockedId(null);
  }

  async function sendQueuedInstructionNow(id: string) {
    const item = instructionQueue.find((candidate) => candidate.id === id);
    if (!item || instructionQueueBusyId) return;
    setInstructionQueueBusyId(id);
    setInstructionQueueBlockedId(null);
    setInstructionQueueEditingId(null);
    try {
      if (canInterrupt && liveTurnId && selectedThreadId) {
        pauseGoalForUserInsertion();
        setSendFailure(null);
        setSendStage(locale === "zh-CN" ? "正在打断当前轮次…" : "Interrupting current turn...");
        await interruptTurn.mutateAsync({ threadId: selectedThreadId, turnId: liveTurnId, profileId: selectedThreadProfileId ?? undefined });
      }
      const sent = await submitTurnText(item.text, item.attachments);
      if (sent) {
        setInstructionQueue((current) => current.filter((candidate) => candidate.id !== id));
      } else {
        setInstructionQueueBlockedId(id);
      }
    } catch (error) {
      setSendFailure(describeSendError(locale === "zh-CN" ? "立即发送" : "send now", error));
      setSendStage(null);
      setInstructionQueueBlockedId(id);
    } finally {
      setInstructionQueueBusyId(null);
    }
  }

  const taskConversationThread = taskConversation.data?.thread ?? null;
  const selectedRuntimeThread = shouldUseSelectedRuntimeThread({ currentTask, selectedThreadId })
    ? selectedThread.data?.thread ?? null
    : null;
  const activeThread =
    hasRenderableThreadContent(taskConversationThread) || !hasRenderableThreadContent(selectedRuntimeThread)
      ? taskConversationThread ?? selectedRuntimeThread
      : selectedRuntimeThread;
  const activeExecutionThread = selectedThread.data?.thread;
  const currentTaskGraphBase = useMemo(() => {
    if (taskGraphRouteUnavailable) {
      return fallbackTaskGraph ?? null;
    }
    const latestSelectedGraph = latestTaskGraphDefinition(currentTask?.graph_definitions);
    const latestRenderableGraph = hasRenderableTaskGraphStructure(latestSelectedGraph)
      ? latestSelectedGraph
      : null;
    const selectedTaskGraph = activeTaskGraphId
      ? currentTask?.graph_definitions?.find((graph) => graph.graph_id === activeTaskGraphId) ?? null
      : latestSelectedGraph ?? null;
    const selectedRenderableGraph = hasRenderableTaskGraphStructure(selectedTaskGraph)
      ? selectedTaskGraph
      : null;
    const routeGraph =
      activeTaskGraphId == null
        ? taskGraph.data?.graph ?? null
        : taskGraph.data?.graph?.graph_id === activeTaskGraphId
          ? taskGraph.data.graph
          : null;
    const preferredServerGraph =
      routeGraph ?? selectedRenderableGraph ?? latestRenderableGraph ?? null;
    if (isTaskGraphNewer(fallbackTaskGraph, preferredServerGraph)) {
      return fallbackTaskGraph;
    }
    if (activeTaskGraphId) {
      if (routeGraph?.graph_id === activeTaskGraphId) {
        return routeGraph;
      }
      if (selectedRenderableGraph) {
        return selectedRenderableGraph;
      }
      if (fallbackTaskGraph?.graph_id === activeTaskGraphId) {
        return fallbackTaskGraph;
      }
      return preferredServerGraph ?? null;
    }
    return preferredServerGraph ?? fallbackTaskGraph ?? null;
  }, [activeTaskGraphId, currentTask?.graph_definitions, fallbackTaskGraph, taskGraph.data?.graph, taskGraphRouteUnavailable]);
  const currentTaskGraph = useMemo(
    () => applyTaskGraphNodeOverrides(currentTaskGraphBase, taskGraphNodeOverrides),
    [currentTaskGraphBase, taskGraphNodeOverrides],
  );
  const taskGraphRunActionBlockedReason = useMemo(
    () =>
      resolveTaskGraphRunPrecondition({
        actionLabel: "任务图运行",
        currentTaskGraph,
        graphId: currentTaskGraph?.graph_id ?? activeTaskGraphId ?? null,
        routeUnavailable: taskGraphRouteUnavailable,
      }),
    [activeTaskGraphId, currentTaskGraph, taskGraphRouteUnavailable],
  );
  const currentTaskGraphSnapshotRefs = useMemo(() => {
    const graphId = currentTaskGraph?.graph_id ?? activeTaskGraphId;
    if (!graphId) return [];
    return (currentTask?.graph_snapshot_refs ?? []).filter((item) => item.graph_id === graphId);
  }, [activeTaskGraphId, currentTask?.graph_snapshot_refs, currentTaskGraph?.graph_id]);
  const selectedTaskGraphSnapshot = useMemo(
    () => currentTaskGraphSnapshotRefs.find((item) => item.snapshot_id === selectedTaskGraphSnapshotId) ?? currentTaskGraphSnapshotRefs[0] ?? null,
    [currentTaskGraphSnapshotRefs, selectedTaskGraphSnapshotId],
  );
  useEffect(() => {
    if (typeof window === "undefined") return;
    const latestCurrentTaskGraph = latestTaskGraphDefinition(currentTask?.graph_definitions);
    const routeGraphId = taskGraph.data?.graph?.graph_id ?? null;
    const routeTaskGraphIds = (taskGraph.data?.task?.graph_definitions ?? []).map((graph) => graph.graph_id);
    const currentTaskGraphIds = (currentTask?.graph_definitions ?? []).map((graph) => graph.graph_id);
    document.documentElement.dataset[TASK_GRAPH_STATE_DATASET_KEY] = JSON.stringify({
      at: Date.now(),
      graphWorkspaceOpen,
      selectedTaskGraphId,
      activeTaskGraphId,
      fallbackGraphId: fallbackTaskGraph?.graph_id ?? null,
      routeGraphId,
      routeTaskGraphIds,
      currentTaskGraphIds,
      latestCurrentTaskGraphId: latestCurrentTaskGraph?.graph_id ?? null,
      currentTaskGraphBaseId: currentTaskGraphBase?.graph_id ?? null,
      currentTaskGraphId: currentTaskGraph?.graph_id ?? null,
      currentTaskGraphTemplateId: currentTaskGraph?.template_id ?? null,
    });
  }, [
    activeTaskGraphId,
    currentTask?.graph_definitions,
    currentTaskGraph?.graph_id,
    currentTaskGraph?.template_id,
    currentTaskGraphBase?.graph_id,
    fallbackTaskGraph?.graph_id,
    graphWorkspaceOpen,
    selectedTaskGraphId,
    taskGraph.data?.graph?.graph_id,
    taskGraph.data?.task?.graph_definitions,
  ]);
  const currentTaskGraphRunRef = useMemo(() => {
    const graphId = currentTaskGraph?.graph_id ?? activeTaskGraphId;
    return selectCurrentTaskGraphRunRef({
      graphId,
      optimisticRunRefs: Object.values(taskGraphOptimisticLiveRunRefs),
      liveRunRefs: Object.values(taskGraphLiveRunRefs),
      routeTaskRunRefs: taskGraph.data?.task?.graph_run_refs,
      currentTaskRunRefs: currentTask?.graph_run_refs,
      dryRunRunRef: taskGraphDryRunResult?.run_ref ?? null,
      allowCachedActiveRunRef:
        runTaskGraph.isPending && taskGraphLiveDispatchStarted,
      allowOptimisticActiveRunRef: taskGraphLiveDispatchStarted,
    });
  }, [
    activeTaskGraphId,
    currentTask?.graph_run_refs,
    currentTaskGraph?.graph_id,
    runTaskGraph.isPending,
    taskGraphLiveDispatchStarted,
    taskGraphOptimisticLiveRunRefs,
    taskGraph.data?.task?.graph_run_refs,
    taskGraphDryRunResult?.run_ref,
    taskGraphLiveRunRefs,
  ]);
  const authoritativeActiveTaskGraphRunRef = useMemo(() => {
    const graphId = currentTaskGraph?.graph_id ?? activeTaskGraphId;
    return selectLatestTaskGraphRunRef(graphId, [
      (taskGraph.data?.task?.graph_run_refs ?? []).filter(
        (item) =>
          item &&
          String(item.status ?? "").trim() !== "" &&
          ["queued", "running", "paused_for_review"].includes(String(item.status ?? "").trim()),
      ),
      (currentTask?.graph_run_refs ?? []).filter(
        (item) =>
          item &&
          String(item.status ?? "").trim() !== "" &&
          ["queued", "running", "paused_for_review"].includes(String(item.status ?? "").trim()),
      ),
    ]);
  }, [
    activeTaskGraphId,
    currentTask?.graph_run_refs,
    currentTaskGraph?.graph_id,
    taskGraph.data?.task?.graph_run_refs,
  ]);
  useEffect(() => {
    if (!taskGraphLiveDispatchStarted) {
      return undefined;
    }
    const intent = taskGraphRequestedRunIntentRef.current;
    if (!intent || intent.kind !== "live") {
      return undefined;
    }
    const optimisticRunRef = taskGraphOptimisticLiveRunRefs[intent.graphId];
    if (!optimisticRunRef) {
      return undefined;
    }
    if (
      authoritativeActiveTaskGraphRunRef &&
      String(authoritativeActiveTaskGraphRunRef.graph_id ?? "").trim() === intent.graphId
    ) {
      return undefined;
    }
    const createdAtMs = Date.parse(String(optimisticRunRef.created_at ?? ""));
    if (!Number.isFinite(createdAtMs)) {
      return undefined;
    }
    const timeoutAtMs =
      createdAtMs + TASK_GRAPH_LIVE_DISPATCH_CONFIRMATION_TIMEOUT_MS;
    const handleTimeout = () => {
      const latestIntent = taskGraphRequestedRunIntentRef.current;
      if (!hasTaskGraphLiveDispatchTimedOut({
        intent: latestIntent,
        optimisticRunCreatedAt: optimisticRunRef.created_at,
        hasAuthoritativeActiveRun:
          Boolean(authoritativeActiveTaskGraphRunRef) &&
          String(authoritativeActiveTaskGraphRunRef?.graph_id ?? "").trim() === intent.graphId,
        timeoutMs: TASK_GRAPH_LIVE_DISPATCH_CONFIRMATION_TIMEOUT_MS,
      })) {
        return;
      }
      taskGraphRequestedRunIntentRef.current = null;
      setTaskGraphLiveDispatchStarted(false);
      clearTaskGraphOptimisticLiveRunRef(intent.graphId);
      queryClient.invalidateQueries({ queryKey: ["project-sidebar"] });
      queryClient.invalidateQueries({ queryKey: ["project-tasks"] });
      queryClient.invalidateQueries({
        queryKey: [
          "task-graph",
          project.project_id,
          currentTask?.task_id ?? null,
          intent.graphId,
        ],
      });
      setTaskGraphFixtureRunError(
        locale === "zh-CN"
          ? "直接运行请求已发出，但在 4 秒内没有生成新的运行记录。已回退到最近一次已确认结果，请检查运行检查或 sidecar 日志。"
          : "The live run request was sent, but no new run record appeared within 4 seconds. AstraBridge reverted to the latest confirmed result. Check run diagnostics or the sidecar log.",
      );
    };
    const delayMs = Math.max(0, timeoutAtMs - Date.now());
    if (delayMs === 0) {
      handleTimeout();
      return undefined;
    }
    const timer = window.setTimeout(handleTimeout, delayMs);
    return () => window.clearTimeout(timer);
  }, [
    activeTaskGraphId,
    authoritativeActiveTaskGraphRunRef,
    currentTask?.task_id,
    locale,
    project.project_id,
    queryClient,
    taskGraphLiveDispatchStarted,
    taskGraphOptimisticLiveRunRefs,
  ]);
  const taskGraphDryRunReportHref = taskGraphDryRunResult?.artifact_paths?.report_md
    ? projectFileReadHref(taskGraphDryRunResult.artifact_paths.report_md)
    : null;
  const taskInspectorEvidence = useMemo(() => summarizeTaskInspectorEvidence(currentTask, activeThread), [activeThread, currentTask]);
  const workflowFacts = useMemo(
    () => summarizeTaskWorkflowFacts(currentTask, activeExecutionThread ?? null, taskInspectorEvidence),
    [activeExecutionThread, currentTask, taskInspectorEvidence],
  );
  const activeExecutionBackendLabel = workflowFacts.backend === "native_kernel" ? "native kernel" : "app server";
  const activeThreadName = visibleThreadTitle(activeThread?.displayName ?? selectedThreadSummary?.displayName) || t(locale, "title_thread");
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
  const runtimeGuardVisible = Boolean(liveTurnId && activeStatusType === "active") || waitingOnApproval || startTurn.isPending || createThread.isPending || beginThreadCreate.isPending || Boolean(taskCreationPending);
  const runtimeRouteLabel = [activeProfile?.label, activeSettings.model].filter(Boolean).join(" · ");
  const runtimeWaitingState = useMemo(
    () =>
      resolveRuntimeWaitingState({
        locale,
        routeLabel: runtimeRouteLabel,
        liveActivity,
        liveDiff,
        waitingOnApproval,
        activeStatusType,
        startPending: startTurn.isPending,
        createThreadPending: createThread.isPending || beginThreadCreate.isPending || Boolean(taskCreationPending),
        creatingTaskName: taskCreationPending?.name,
      }),
    [activeStatusType, beginThreadCreate.isPending, createThread.isPending, liveActivity, liveDiff, locale, runtimeRouteLabel, startTurn.isPending, taskCreationPending, waitingOnApproval],
  );
  const runtimeGuardStateText = runtimeStateLabel(locale, {
    waitingOnApproval,
    sending: startTurn.isPending || createThread.isPending || beginThreadCreate.isPending || Boolean(taskCreationPending),
    activeStatusType,
  });
  const waitingReplayPhase = smokeMode ? brandWaitingReplayPhase() : null;
  const statusAttentionItems = useMemo(
    () => buildStatusAttentionItems({ locale, supervisor: supervisorForDisplay, workflowFacts, capabilityWarnings }),
    [capabilityWarnings, locale, supervisorForDisplay, workflowFacts],
  );
  const statusEvidenceItems = useMemo(
    () => buildStatusEvidenceItems({ locale, supervisor: supervisor.data, workflowFacts, goal: displayGoal }),
    [displayGoal, locale, supervisor.data, workflowFacts],
  );
  const showWorkflowEvidencePanel = useMemo(
    () => workflowFacts.failedCommandCount > 0 || workflowFacts.checkpointRefs.length > 0 || actionableWorkflowDiagnostics(workflowFacts).length > 0,
    [workflowFacts],
  );
  const fallbackSetupCheckpoints = useMemo<ProjectCheckpoint[]>(
    () => {
      const checkpoints: ProjectCheckpoint[] = [];
      for (const item of currentTask?.checkpoint_refs ?? []) {
          const saveId = String(item?.save_id ?? "").trim();
          if (!saveId) continue;
          const providerThread = currentTaskProviderThreads.find((thread) => thread.thread_id === String(item?.thread_id ?? currentTask?.active_provider_thread_id ?? ""));
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
    if (instructionQueue.length === 0) {
      queuedInstructionInFlightRef.current = false;
      setInstructionQueueBlockedId(null);
      setInstructionQueueBusyId(null);
      setInstructionQueueEditingId(null);
      return;
    }
    if (queuedInstructionInFlightRef.current || taskCreationPending || activeStatusType === "active" || waitingOnApproval || startTurn.isPending || createThread.isPending || beginThreadCreate.isPending) return;
    const [next] = instructionQueue;
    if (!next) return;
    if (next.targetThreadId && next.targetThreadId !== sendTargetThreadId) {
      setInstructionQueueBlockedId(next.id);
      return;
    }
    if (instructionQueueBlockedId === next.id) return;
    queuedInstructionInFlightRef.current = true;
    setInstructionQueueBusyId(next.id);
    void submitTurnText(next.text, next.attachments).finally(() => {
      setInstructionQueueBusyId(null);
      queuedInstructionInFlightRef.current = false;
    }).then((sent) => {
      if (sent) {
        setInstructionQueue((current) => current[0]?.id === next.id ? current.slice(1) : current.filter((item) => item.id !== next.id));
        setInstructionQueueBlockedId((current) => current === next.id ? null : current);
        return;
      }
      setInstructionQueueBlockedId(next.id);
    });
  }, [activeStatusType, beginThreadCreate.isPending, createThread.isPending, instructionQueue, instructionQueueBlockedId, sendTargetThreadId, startTurn.isPending, taskCreationPending, waitingOnApproval]);

  useEffect(() => {
    const threadGoal = goal.data?.goal;
    if (!threadGoal || !selectedThreadId || !goalRunnerArmed) return;
    if (!goalCanAutoContinue(threadGoal.status) || taskCreationPending || instructionQueue.length > 0 || activeStatusType === "active" || waitingOnApproval || startTurn.isPending || createThread.isPending || beginThreadCreate.isPending) return;
    const key = `${selectedThreadId}:${threadGoal.updatedAt}:${threadGoal.tokensUsed}:${threadGoal.status}`;
    if (goalContinuationKeyRef.current === key) return;
    goalContinuationKeyRef.current = key;
    const prompt =
      locale === "zh-CN"
        ? `继续推进当前目标：${threadGoal.objective}\n如果目标已经完成，请明确说明并将目标状态更新为 complete；如果需要用户确认，请先暂停并提出问题。`
        : `Continue working toward the active goal: ${threadGoal.objective}\nIf the goal is complete, say so and mark it complete; if user confirmation is needed, pause and ask first.`;
    void submitTurnText(prompt, []);
  }, [activeStatusType, beginThreadCreate.isPending, createThread.isPending, goal.data?.goal, goalRunnerArmed, instructionQueue.length, locale, selectedThreadId, startTurn.isPending, taskCreationPending, waitingOnApproval]);

  useEffect(() => {
    if (!selectedThreadId || !liveTurnId || !activeThread) return;
    const persistedTurn = (activeThread.turns ?? []).find((turn) => turn.id === liveTurnId);
    if (!hasPersistedRenderableTurnContent(persistedTurn)) return;
    clearLiveTurn(selectedThreadId, liveTurnId);
  }, [activeThread, clearLiveTurn, liveTurnId, selectedThreadId]);

  useEffect(() => {
    const previous = smokeWaitingReplayRef.current;
    if (!smokeMode || !waitingReplayPhase || !selectedThreadId) {
      if (previous) {
        clearLiveTurn(previous.threadId, previous.turnId);
        setThreadStatus(previous.threadId, { type: "idle", activeFlags: [] });
        smokeWaitingReplayRef.current = null;
      }
      return;
    }

    const turnId = `smoke-brand-waiting-${waitingReplayPhase}`;
    if (previous && previous.threadId === selectedThreadId && previous.turnId === turnId) return;
    if (previous) {
      clearLiveTurn(previous.threadId, previous.turnId);
    }

    const replay = buildRuntimeWaitingReplayState(waitingReplayPhase, locale);
    setThreadStatus(selectedThreadId, replay.status);
    if (replay.diff) {
      setTurnDiff(selectedThreadId, turnId, replay.diff);
    } else if (replay.activity) {
      setTurnActivity(selectedThreadId, turnId, replay.activity);
    }
    smokeWaitingReplayRef.current = { threadId: selectedThreadId, turnId };
  }, [clearLiveTurn, locale, selectedThreadId, setThreadStatus, setTurnActivity, setTurnDiff, smokeMode, waitingReplayPhase]);

  const blocks = summarizeTurnBlocks(activeThread, liveText, liveReasoning, liveActivity, liveDiff, liveTurnId);
  const conversationRenderState = describeConversationRenderState({
    activeThread,
    selectedRuntimeThread,
    taskConversationThread,
    blocks,
    isLoading: selectedThread.isLoading || taskConversation.isLoading,
  });
  const hasRenderedPlanBlock = blocks.some((block) => block.role === "plan" || (("text" in block) && typeof block.text === "string" && extractProposedPlanText(block.text)));
  const inspectorPlan = supervisor.data?.plan ?? (activePlan ? {
    thread_id: selectedThreadId ?? "",
    turn_id: liveTurnId ?? "",
    explanation: activePlan.explanation,
    steps: activePlan.plan,
    last_updated_at: null,
    source: "local-events",
  } : null);
  const hasGoalContent = Boolean(displayGoal?.objective);
  const composerWorkflowMode: ComposerWorkflowMode =
    goalDockExpanded ? goalDockTab : activeSettings.collaboration_mode === "plan" ? "plan" : "default";
  const shouldShowGoalDock = resolveGoalDockVisibility({
    workflowMode: composerWorkflowMode,
    hasPlan: Boolean(inspectorPlan),
    hasProposedPlan: Boolean((livePlanText || proposedPlanText).trim()),
  });
  const composerRailState =
    attachmentDropActive
      ? "drop"
      : sendFailure
        ? "error"
        : voiceRecorderState === "recording"
          ? "recording"
          : voiceRecorderState === "transcribing" || startTurn.isPending || createThread.isPending || beginThreadCreate.isPending || Boolean(taskCreationPending)
            ? "sending"
            : "idle";
  const composerRailArmed = Boolean(composerText.trim() || attachments.length > 0);
  const conversationVisuallyEmpty = !selectedThread.isLoading && !taskConversation.isLoading && blocks.length === 0;
  function setComposerWorkflowMode(nextMode: ComposerWorkflowMode) {
    if (nextMode === "goal") {
      updateComposerSettings({ collaboration_mode: "default" });
      setGoalDockExpanded(true);
      setGoalDockTab("goal");
      if (!hasGoalContent) setGoalEditMode(true);
      return;
    }
    if (nextMode === "plan") {
      updateComposerSettings({ collaboration_mode: "plan" });
      setGoalDockExpanded(true);
      setGoalDockTab("plan");
      setGoalEditMode(false);
      return;
    }
    updateComposerSettings({ collaboration_mode: "default" });
    setGoalDockExpanded(false);
    setGoalEditMode(false);
  }
  const messagePlanAnchor = inspectorPlan && !hasRenderedPlanBlock ? inspectorPlan : null;
  const sidebarProjects = !archivedVisible ? (projectSidebar.data?.projects ?? []) : [];
  const sidebarTaskCount = sidebarProjects.reduce((count, item) => count + item.tasks.length, 0);
  const sidebarAutomationCount = sidebarAutomations.data?.automations.length ?? 0;
  const sidebarPluginCount = sidebarPluginSkillRegistry.data?.plugins.length ?? 0;
  const sidebarSkillCount = sidebarPluginSkillRegistry.data?.skills.length ?? 0;
  const sidebarAutomationCountLabel = sidebarAutomations.isLoading && !sidebarAutomations.data ? "…" : String(sidebarAutomationCount);
  const sidebarPluginCountLabel = sidebarPluginSkillRegistry.isLoading && !sidebarPluginSkillRegistry.data ? "…" : String(sidebarPluginCount);
  const sidebarSkillCountLabel = sidebarPluginSkillRegistry.isLoading && !sidebarPluginSkillRegistry.data ? "…" : String(sidebarSkillCount);
  const setupTabActive = (targetTab: SetupTab, extensionKind?: ExtensionInventoryInitialKind) =>
    mainView === "setup" &&
    setupInitialTab === targetTab &&
    (!extensionKind || setupExtensionsKind === extensionKind);
  const apiManagerSetupActive = mainView === "setup" && API_MANAGER_TABS.includes(setupInitialTab);
  const setupLandingMeta: Partial<Record<SetupTab, { title: string; eyebrow: string; subtitle: string }>> = {
    file: {
      title: locale === "zh-CN" ? "文件" : "File",
      eyebrow: locale === "zh-CN" ? "项目文件" : "Project files",
      subtitle: locale === "zh-CN" ? "新建任务、检查点和项目报告。" : "Task creation, checkpoints, and project reports.",
    },
    view: {
      title: locale === "zh-CN" ? "视图" : "View",
      eyebrow: locale === "zh-CN" ? "工作区" : "Workspace",
      subtitle: locale === "zh-CN" ? "搜索、归档任务入口和左右栏显隐。" : "Search, archived tasks, and layout visibility.",
    },
    tools: {
      title: locale === "zh-CN" ? "工具" : "Tools",
      eyebrow: locale === "zh-CN" ? "能力入口" : "Capability entry",
      subtitle: locale === "zh-CN" ? "插件、技能、自动化、联网和多模态入口。" : "Plugins, skills, automations, web, and multimodal entry points.",
    },
    runtime_overview: {
      title: locale === "zh-CN" ? "运行时" : "Runtime",
      eyebrow: locale === "zh-CN" ? "运行边界" : "Runtime boundary",
      subtitle: locale === "zh-CN" ? "运行时设置、MCP 和健康检查。" : "Runtime setup, MCP, and health checks.",
    },
    settings_overview: {
      title: locale === "zh-CN" ? "设置" : "Settings",
      eyebrow: locale === "zh-CN" ? "提供方与密钥" : "Providers and keys",
      subtitle: locale === "zh-CN" ? "登录、用户、密钥、提供方和模型入口。" : "Login, users, keys, providers, and model entry points.",
    },
  };
  const currentSetupLanding = setupLandingMeta[setupInitialTab];
  const setupTitle = apiManagerSetupActive
    ? t(locale, "provider_model_settings")
    : currentSetupLanding
      ? currentSetupLanding.title
      : t(locale, `setup_tab_${setupInitialTab}`);
  const setupEyebrow = apiManagerSetupActive
    ? providerSetupLabel(locale)
    : currentSetupLanding
      ? currentSetupLanding.eyebrow
    : setupInitialTab === "automations" || setupInitialTab === "extensions" || setupInitialTab === "capabilities" || setupInitialTab === "web"
      ? t(locale, "sidebar_capability_tools")
      : setupInitialTab === "health"
        ? t(locale, "sidebar_group_settings")
        : t(locale, "sidebar_group_developer");
  const setupSubtitle = apiManagerSetupActive ? t(locale, "provider_settings_subtitle") : currentSetupLanding?.subtitle ?? "";
  const primaryAbilityEntries = ABILITY_ENTRY_DEFINITIONS.filter((entry) => entry.placement === "primary");
  const moreAbilityEntries = ABILITY_ENTRY_DEFINITIONS.filter((entry) => entry.placement === "more");
  const sidebarAbilityCountLabel = (entry: AbilityEntryDefinition) =>
    entry.countMode === "automation"
      ? sidebarAutomationCountLabel
      : entry.countMode === "plugin"
        ? sidebarPluginCountLabel
        : entry.countMode === "skill"
          ? sidebarSkillCountLabel
          : null;
  const moreAbilitiesActive = moreAbilityEntries.some((entry) => setupTabActive(entry.targetTab, entry.extensionKind));
  const allAbilityEntries = [...primaryAbilityEntries, ...moreAbilityEntries];
  const appMenuCopy = locale === "zh-CN"
    ? {
        file: "文件",
        view: "视图",
        tools: "工具",
        runtime: "运行时",
        settings: "设置",
        showLeft: "显示左侧栏",
        hideLeft: "隐藏左侧栏",
        showInspector: "显示检查器",
        hideInspector: "隐藏检查器",
      }
    : {
        file: "File",
        view: "View",
        tools: "Tools",
        runtime: "Runtime",
        settings: "Settings",
        showLeft: "Show sidebar",
        hideLeft: "Hide sidebar",
        showInspector: "Show inspector",
        hideInspector: "Hide inspector",
      };
  const topMenuSections: AppMenuSection[] = [
    {
      id: "file",
      label: appMenuCopy.file,
      active: setupTabActive("file") || setupTabActive("saves") || setupTabActive("reports"),
      defaultAction: () => openSetupTab("file"),
      items: [
        {
          id: "file-home",
          label: locale === "zh-CN" ? "文件概览" : "File overview",
          active: setupTabActive("file"),
          action: () => openSetupTab("file"),
        },
        {
          id: "new-thread",
          label: t(locale, "new_thread"),
          hint: t(locale, "new_thread_hint"),
          action: () => {
            setMainView("chat");
            void handleCreateThread();
          },
        },
        {
          id: "saves",
          label: t(locale, "setup_tab_saves"),
          testId: "sidebar-nav-saves",
          active: setupTabActive("saves"),
          action: () => openSetupTab("saves"),
        },
        {
          id: "reports",
          label: t(locale, "setup_tab_reports"),
          testId: "sidebar-nav-reports",
          active: setupTabActive("reports"),
          action: () => openSetupTab("reports"),
        },
        {
          id: "close-project",
          label: t(locale, "close_project"),
          disabled: closeProject.isPending,
          action: () => closeProject.mutate(),
        },
      ],
    },
    {
      id: "view",
      label: appMenuCopy.view,
      active: setupTabActive("view") || archivedVisible,
      defaultAction: () => openSetupTab("view"),
      items: [
        {
          id: "workspace-view",
          label: locale === "zh-CN" ? "工作区视图" : "Workspace view",
          active: setupTabActive("view"),
          action: () => openSetupTab("view"),
        },
        {
          id: "search",
          label: t(locale, "search"),
          hint: t(locale, "command_k_hint"),
          action: () => {
            setArchivedVisible(false);
            setMainView("chat");
            setCommandPaletteOpen(true);
          },
        },
        {
          id: "toggle-left-sidebar",
          label: leftSidebarOpen ? appMenuCopy.hideLeft : appMenuCopy.showLeft,
          action: toggleNavigationSidebar,
        },
        {
          id: "toggle-inspector",
          label: rightSidebarOpen ? appMenuCopy.hideInspector : appMenuCopy.showInspector,
          action: toggleRightSidebar,
        },
        {
          id: "archived",
          label: t(locale, "archived_threads"),
          testId: "sidebar-nav-archived",
          active: archivedVisible,
          action: () => {
            setMainView("chat");
            setArchivedVisible((value) => !value);
          },
        },
      ],
    },
    {
      id: "tools",
      label: appMenuCopy.tools,
      active: setupTabActive("tools") || moreAbilitiesActive || primaryAbilityEntries.some((entry) => setupTabActive(entry.targetTab, entry.extensionKind)) || setupTabActive("dogfood"),
      defaultAction: () => openSetupTab("tools"),
      items: [
        {
          id: "tools-home",
          label: locale === "zh-CN" ? "工具概览" : "Tools overview",
          active: setupTabActive("tools"),
          action: () => openSetupTab("tools"),
        },
        ...allAbilityEntries.map((entry) => ({
          id: entry.id,
          label: t(locale, entry.labelKey),
          meta: sidebarAbilityCountLabel(entry) ?? undefined,
          testId: entry.testId,
          active: setupTabActive(entry.targetTab, entry.extensionKind),
          action: () => openSetupTab(entry.targetTab, entry.extensionKind ? { extensionKind: entry.extensionKind } : undefined),
        })),
        {
          id: "dogfood",
          label: t(locale, "setup_tab_dogfood"),
          testId: "sidebar-nav-dogfood",
          active: setupTabActive("dogfood"),
          action: () => openSetupTab("dogfood"),
        },
      ],
    },
    {
      id: "runtime",
      label: appMenuCopy.runtime,
      active: setupTabActive("runtime_overview") || setupTabActive("runtime") || setupTabActive("mcp") || setupTabActive("health"),
      defaultAction: () => openSetupTab("runtime_overview"),
      items: [
        {
          id: "runtime-home",
          label: locale === "zh-CN" ? "运行时概览" : "Runtime overview",
          active: setupTabActive("runtime_overview"),
          action: () => openSetupTab("runtime_overview"),
        },
        {
          id: "runtime",
          label: t(locale, "setup_tab_runtime"),
          testId: "sidebar-nav-runtime",
          active: setupTabActive("runtime"),
          action: () => openSetupTab("runtime"),
        },
        {
          id: "mcp",
          label: t(locale, "setup_tab_mcp"),
          testId: "sidebar-nav-mcp",
          active: setupTabActive("mcp"),
          action: () => openSetupTab("mcp"),
        },
        {
          id: "health",
          label: t(locale, "setup_tab_health"),
          testId: "sidebar-nav-health",
          active: setupTabActive("health"),
          action: () => openSetupTab("health"),
        },
      ],
    },
    {
      id: "settings",
      label: appMenuCopy.settings,
      active: setupTabActive("settings_overview") || apiManagerSetupActive || setupTabActive("users"),
      defaultAction: () => openSetupTab("settings_overview"),
      items: [
        {
          id: "settings-home",
          label: locale === "zh-CN" ? "设置概览" : "Settings overview",
          active: setupTabActive("settings_overview"),
          action: () => openSetupTab("settings_overview"),
        },
        {
          id: "providers-keys",
          label: t(locale, "provider_keys"),
          testId: "sidebar-nav-provider-keys",
          active: apiManagerSetupActive,
          action: () => openSetupTab("login"),
        },
        {
          id: "users",
          label: t(locale, "setup_tab_users"),
          active: setupTabActive("users"),
          action: () => openSetupTab("users"),
        },
        {
          id: "keys",
          label: t(locale, "setup_tab_keys"),
          active: setupTabActive("keys"),
          action: () => openSetupTab("keys"),
        },
        {
          id: "providers",
          label: t(locale, "setup_tab_providers"),
          active: setupTabActive("providers"),
          action: () => openSetupTab("providers"),
        },
        {
          id: "models",
          label: t(locale, "setup_tab_models"),
          active: setupTabActive("models"),
          action: () => openSetupTab("models"),
        },
      ],
    },
  ];
  const topMenuLandingTabs: Record<string, SetupTab> = {
    file: "file",
    view: "view",
    tools: "tools",
    runtime: "runtime_overview",
    settings: "settings_overview",
  };
  const inspectorVisible = mainView === "chat" && rightSidebarOpen && !compactShellViewport;
  const shellColumns = [
    ...(sidebarVisible && !compactShellViewport ? [`${leftPane.width}px`, "0px"] : []),
    "minmax(0, 1fr)",
    ...(inspectorVisible ? ["0px", `${rightPane.width}px`] : []),
  ].join(" ");
  return (
    <div
      data-testid="app-shell"
      className={`shell-grid${compactShellViewport ? " shell-grid-compact" : ""}`}
      style={{
        gridTemplateColumns: shellColumns,
      }}
      >
      {sidebarVisible ? (
      <aside className={`sidebar app-sidebar${compactShellViewport ? " app-sidebar-drawer" : ""}`}>
        <div className="sidebar-brandbar" aria-label="AstraBridge">
          <div className="sidebar-brandmark" aria-hidden="true">
            <span className="sidebar-brandmark-ring" />
            <span className="sidebar-brandmark-core" />
            <span className="sidebar-brandmark-node sidebar-brandmark-node-top" />
            <span className="sidebar-brandmark-node sidebar-brandmark-node-right" />
          </div>
          <div className="sidebar-brandcopy">
            <strong>AstraBridge</strong>
            <span>{locale === "zh-CN" ? "观测台" : "Observatory"}</span>
          </div>
        </div>
        <nav className="sidebar-nav" aria-label="Primary">
          <button type="button" className="nav-row nav-row-primary" disabled={createThread.isPending || beginThreadCreate.isPending || Boolean(taskCreationPending)} onClick={() => { closeCompactNavigation(); setMainView("chat"); void handleCreateThread(); }}>
            <span className="nav-icon" aria-hidden="true"><StarbridgeTaskCreateIcon size={15} strokeWidth={1.95} /></span>
            <span>{t(locale, "new_thread")}</span>
            <kbd>{t(locale, "new_thread_hint")}</kbd>
          </button>
          <button type="button" className="nav-row" onClick={() => { closeCompactNavigation(); setCommandPaletteOpen(true); }}>
            <span className="nav-icon" aria-hidden="true"><StarbridgeSearchIcon size={14} strokeWidth={1.95} /></span>
            <span>{t(locale, "search")}</span>
            <kbd>{t(locale, "command_k_hint")}</kbd>
          </button>
        </nav>

        <section className="sidebar-group sidebar-thread-group grow">
          <div className="sidebar-heading">
            <span>{t(locale, "sidebar_threads")}</span>
            <span className="sidebar-count">{projectSidebar.isLoading && !projectSidebar.data ? "…" : sidebarTaskCount || threads.data?.threads.length || 0}</span>
          </div>
          <div className="official-thread-list">
            {sidebarSelectionError ? (
              <p className="sidebar-selection-error" role="alert" data-testid="sidebar-task-selection-error">
                {locale === "zh-CN" ? `任务切换失败：${sidebarSelectionError}` : `Task switch failed: ${sidebarSelectionError}`}
              </p>
            ) : null}
            {sidebarProjects.length > 0 ? (
              <ProjectTaskTree
                locale={locale}
                projects={sidebarProjects}
                expandedProjects={expandedSidebarProjects}
                selectedProjectKey={pendingSidebarProjectKey}
                selectedTaskId={pendingSidebarTask?.task_id ?? currentTask?.task_id ?? null}
                formatTime={summarizeRelativeTime}
                busy={sidebarSelectionBusy || openProjectFromSidebar.isPending}
                onToggleProject={toggleSidebarProject}
                onSelectProject={(projectNode) => { closeCompactNavigation(); void selectSidebarProject(projectNode); }}
                onSelectTask={(projectNode, taskNode) => { closeCompactNavigation(); void selectSidebarTask(projectNode, taskNode); }}
              />
            ) : null}
            {sidebarProjects.length === 0 ? (threads.data?.threads ?? []).map((thread) => {
              const threadTitle = visibleThreadTitle(thread.displayName) || t(locale, "title_thread");
              const threadPreview = visibleThreadTitle(thread.preview);
              return (
                <div key={thread.id} className={`codex-thread-item ${thread.id === selectedThreadId ? "codex-thread-item-active" : ""}`}>
                  <button
                    type="button"
                    className="thread-select-row"
                    title={[threadTitle, threadPreview, thread.id].filter(Boolean).join("\n")}
                    onClick={() => { setMainView("chat"); switchThread.mutate(thread.id); }}
                  >
                    <span className="row-icon" aria-hidden="true"><StarbridgeWorkflowDefaultIcon size={14} strokeWidth={1.9} /></span>
                    <span className="thread-copy">
                      <span className="thread-title-line">
                        <strong>{threadTitle}</strong>
                        <time>{summarizeRelativeTime(thread.updatedAt)}</time>
                      </span>
                      <span className="thread-route-line">
                        <span>{thread.shellSettings.model ?? thread.modelProvider}</span>
                        <span>{thread.shellSettings.reasoning_effort ?? project.default_effort}</span>
                      </span>
                    </span>
                  </button>
                  <div className="thread-hover-actions" aria-label={locale === "zh-CN" ? "任务操作" : "Task actions"}>
                    <button type="button" className="icon-button" title={t(locale, "rename_thread")} onClick={() => handleRenameThread(thread.id)}>
                      <StarbridgeRenameIcon size={13} strokeWidth={1.85} aria-hidden="true" />
                    </button>
                    <button type="button" className="icon-button" title={t(locale, "archive_thread")} onClick={() => archiveThread.mutate(thread.id)}>
                      <StarbridgeArchiveIcon size={13} strokeWidth={1.85} aria-hidden="true" />
                    </button>
                  </div>
                </div>
              );
            }) : null}
            {!projectSidebar.isLoading && !threads.isLoading && sidebarProjects.length === 0 && (threads.data?.threads ?? []).length === 0 ? <p className="muted">{t(locale, "no_threads")}</p> : null}
          </div>
        </section>

        <div className="sidebar-footer">
          <button type="button" className="nav-row nav-row-session" onClick={() => { closeCompactNavigation(); openSetupTab("login"); }}>
            <span className="nav-icon" aria-hidden="true"><StarbridgeSessionIcon size={15} strokeWidth={1.9} /></span>
            <span>
              {llmSession.data?.mode === "managed_user" ? t(locale, "manager_status_managed").replace("{user}", llmSession.data.username ?? "user") : t(locale, "manager_status_anonymous")}
            </span>
          </button>
          <button type="button" className="nav-row nav-row-settings" onClick={() => { closeCompactNavigation(); openSetupTab("login"); }}>
            <span className="nav-icon" aria-hidden="true"><StarbridgeSettingsIcon size={15} strokeWidth={1.9} /></span>
            <span>{t(locale, "sidebar_group_settings")}</span>
          </button>
        </div>
      </aside>
      ) : null}

      {compactShellViewport && compactSidebarOpen ? (
        <button
          type="button"
          className="sidebar-scrim"
          aria-label={t(locale, "hide_sidebar")}
          title={t(locale, "hide_sidebar")}
          onClick={closeCompactNavigation}
        />
      ) : null}

      {sidebarVisible && !compactShellViewport ? <div className="resize-handle" {...leftPane.bind} /> : null}

      <section
        className={`workspace ${mainView === "chat" ? "workspace-chat" : "workspace-setup"}${mainView === "chat" && graphWorkspaceOpen ? " workspace-chat-task-graph" : ""}`}
      >
        <header className="workspace-topbar">
          <button
            type="button"
            className="icon-button pane-toggle-button"
            data-testid="topbar-toggle-left-sidebar"
            title={sidebarVisible ? t(locale, "hide_sidebar") : t(locale, "show_sidebar")}
            aria-label={sidebarVisible ? t(locale, "hide_sidebar") : t(locale, "show_sidebar")}
            onClick={toggleNavigationSidebar}
          >
            {sidebarVisible ? <PanelLeftClose size={16} aria-hidden="true" /> : <PanelLeftOpen size={16} aria-hidden="true" />}
          </button>
          <nav className="app-menu-bar" aria-label={locale === "zh-CN" ? "应用菜单" : "Application menu"}>
            {topMenuSections.map((section) => (
              <div className="app-menu" key={section.id}>
                <button
                  type="button"
                  className={`app-menu-trigger ${section.active ? "app-menu-trigger-active" : ""}`}
                  aria-expanded={topMenuOpen === section.id}
                  onClick={() => {
                    const landingTab = topMenuLandingTabs[section.id];
                    const landingActive = landingTab ? mainView === "setup" && setupInitialTab === landingTab : false;
                    if (landingActive || !section.defaultAction) {
                      setTopMenuOpen((current) => (current === section.id ? null : section.id));
                      return;
                    }
                    setTopMenuOpen(null);
                    section.defaultAction();
                  }}
                >
                  {section.label}
                </button>
                {topMenuOpen === section.id ? (
                  <div className="app-menu-popover" role="menu">
                    {section.items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        role="menuitem"
                        data-testid={item.testId}
                        className={`app-menu-item ${item.active ? "app-menu-item-active" : ""}`}
                        disabled={item.disabled}
                        onClick={() => {
                          setTopMenuOpen(null);
                          item.action();
                        }}
                      >
                        <span>{item.label}</span>
                        {item.meta ? <small>{item.meta}</small> : null}
                        {item.hint ? <kbd>{item.hint}</kbd> : null}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </nav>
          {mainView === "setup" ? (
            <div className="title-stack">
              <p className="eyebrow">{setupEyebrow}</p>
              <h2>{setupTitle}</h2>
              <p className="route-subtitle">{setupSubtitle}</p>
            </div>
          ) : null}
          <div className="topbar-actions">
            {mainView === "chat" ? (
              <>
                <button
                  type="button"
                  className="ghost-button topbar-compact-action topbar-action-with-icon"
                  data-testid="topbar-compact"
                  disabled={!selectedThreadId || compactThread.isPending}
                  onClick={() => compactThread.mutate({ threadId: selectedThreadId ?? "", profileId: activeSettings.profile_id })}
                >
                  <span className="topbar-action-icon" aria-hidden="true"><StarbridgeCompactContextIcon size={14} strokeWidth={1.9} /></span>
                  {compactThread.isPending ? t(locale, "loading") : t(locale, "compact_context")}
                </button>
                <button type="button" className="ghost-button topbar-action-with-icon" data-testid="topbar-fork" onClick={handleForkThread} disabled={!selectedThreadId}>
                  <span className="topbar-action-icon" aria-hidden="true"><StarbridgeForkTaskIcon size={14} strokeWidth={1.9} /></span>
                  {locale === "zh-CN" ? "创建分支任务" : t(locale, "fork_thread")}
                </button>
                <button
                  type="button"
                  className={`ghost-button topbar-action-with-icon ${graphWorkspaceOpen ? "topbar-action-active" : ""}`}
                  data-testid="topbar-open-task-graph"
                  onClick={() => setGraphWorkspaceOpen((value) => !value)}
                  aria-label={graphWorkspaceOpen ? t(locale, "back_to_chat") : (locale === "zh-CN" ? "任务图" : "Task graph")}
                  title={graphWorkspaceOpen ? t(locale, "back_to_chat") : (locale === "zh-CN" ? "任务图" : "Task graph")}
                >
                  <span className="topbar-action-icon" aria-hidden="true"><Workflow size={14} strokeWidth={1.9} /></span>
                  {graphWorkspaceOpen ? t(locale, "back_to_chat") : (locale === "zh-CN" ? "任务图" : "Task graph")}
                </button>
                <button
                  type="button"
                  className="icon-button pane-toggle-button"
                  data-testid="topbar-toggle-inspector"
                  title={rightSidebarOpen ? t(locale, "hide_inspector") : t(locale, "show_inspector")}
                  aria-label={rightSidebarOpen ? t(locale, "hide_inspector") : t(locale, "show_inspector")}
                  onClick={toggleRightSidebar}
                >
                  {rightSidebarOpen ? <PanelRightClose size={16} aria-hidden="true" /> : <PanelRightOpen size={16} aria-hidden="true" />}
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
              initialTab={setupInitialTab}
              initialExtensionsKind={setupExtensionsKind}
              leftSidebarOpen={sidebarVisible}
              rightSidebarOpen={rightSidebarOpen}
              archivedVisible={archivedVisible}
              onToggleLeftSidebar={toggleNavigationSidebar}
              onToggleRightSidebar={toggleRightSidebar}
              onOpenSearch={() => {
                setArchivedVisible(false);
                setMainView("chat");
                setCommandPaletteOpen(true);
              }}
              onOpenArchived={() => {
                setArchivedVisible(true);
                setMainView("chat");
              }}
              onReturnToChat={() => {
                setArchivedVisible(false);
                setMainView("chat");
              }}
              onCreateThread={handleCreateThread}
              onTabChange={setSetupInitialTab}
            />
          </div>
        ) : (
          <>
        <div className="chat-canvas-shell">
        <div className="chat-canvas" data-testid="chat-canvas" ref={chatCanvasRef}>

        <ConversationNoticeBar
          locale={locale}
          notices={conversationNotices}
          onOpenSetup={() => setMainView("setup")}
        />

        {runtimeGuardVisible ? (
          <section className={`runtime-guard ${waitingOnApproval ? "runtime-guard-waiting" : ""}`}>
            <StarbridgeWaitingConstellation
              variant="inline"
              phase={runtimeWaitingState.phase}
              label={runtimeWaitingState.label}
              title={runtimeWaitingState.title}
              detail={runtimeWaitingState.detail}
              className="runtime-guard-waiting-state"
            />
            <div className="runtime-guard-actions">
              <span className="pill">{runtimeGuardStateText}</span>
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

        {graphWorkspaceOpen ? (
          <TaskGraphWorkspace
            locale={locale}
            templates={taskGraphTemplateList}
            graph={currentTaskGraph}
            selectedNodeId={selectedTaskGraphNodeId}
            selectedEdgeId={selectedTaskGraphEdgeId}
            providerOptions={taskGraphProviderOptions}
            modelSuggestions={taskGraphModelSuggestions}
            nodeSaveError={taskGraphNodeSaveError}
            edgeSaveError={taskGraphEdgeSaveError}
            dryRunResult={taskGraphDryRunResult}
            dryRunError={taskGraphFixtureRunError || taskGraphDryRunError}
            reportHref={taskGraphDryRunReportHref}
            latestRunRef={currentTaskGraphRunRef}
            artifactHrefFor={projectFileReadHref}
            onInspectArtifactPath={inspectTaskGraphArtifactPath}
            onSelectNode={(nodeId) => {
              setSelectedTaskGraphNodeId(nodeId);
              setSelectedTaskGraphEdgeId(null);
            }}
            onSelectEdge={setSelectedTaskGraphEdgeId}
              onInstantiateTemplate={openTaskGraphTemplate}
            onCreateNode={createTaskGraphNode}
            onMoveNode={moveTaskGraphNode}
            onSaveNode={saveTaskGraphNodeConfiguration}
            onSaveEdge={saveTaskGraphEdgeConfiguration}
            onDeleteEdge={deleteTaskGraphEdge}
            onRunDryRun={runTaskGraphDryRun}
            onRunLive={runTaskGraphLive}
            onRunFixture={runTaskGraphFixture}
            onRunCancellableFixture={runTaskGraphCancellableFixture}
            onCancelLatestRun={cancelLatestTaskGraphRun}
            onRecoverLatestRun={recoverLatestTaskGraphRun}
            onApprovePendingRun={approveTaskGraphPendingRun}
            onRejectPendingRun={rejectTaskGraphPendingRun}
            onImportGraph={importTaskGraphThroughWorkspace}
            onExportGraph={exportTaskGraphThroughWorkspace}
            snapshotRefs={currentTaskGraphSnapshotRefs}
            selectedSnapshotId={selectedTaskGraphSnapshot?.snapshot_id ?? null}
            onSelectSnapshot={setSelectedTaskGraphSnapshotId}
            onCreateSnapshot={createTaskGraphSnapshotFromWorkspace}
            onCompareSnapshot={compareSelectedTaskGraphSnapshot}
            onRollbackSnapshot={rollbackSelectedTaskGraphSnapshot}
            onClose={() => setGraphWorkspaceOpen(false)}
            importExportError={taskGraphImportExportError}
            lastImportedPath={taskGraphLastImportedPath}
            lastExportedPath={taskGraphLastExportedPath}
            lastExportPreview={taskGraphLastExportPreview}
            snapshotError={taskGraphSnapshotError}
            snapshotStatus={taskGraphSnapshotStatus}
            snapshotDiffMarkdown={taskGraphSnapshotDiffMarkdown}
            isInstantiating={instantiateTaskGraph.isPending}
            isLoadingTemplates={taskGraphTemplatesLoading}
            isLoadingGraph={taskGraphLoading}
            isSavingNode={updateTaskGraphNode.isPending}
            isSavingEdge={updateTaskGraphEdge.isPending || saveTaskGraphDefinition.isPending}
            isDryRunPending={dryRunTaskGraph.isPending}
            isLiveRunPending={taskGraphLiveRunUiPending}
            showLiveRunPendingChrome={taskGraphLiveRunUiPending}
            isFixtureRunPending={fixtureRunTaskGraph.isPending || taskGraphFixturePendingVisible}
            runActionDisabledReason={taskGraphRunActionBlockedReason}
            isRunCancellationPending={cancelTaskGraphRun.isPending}
            isRunRecoveryPending={recoverTaskGraphRun.isPending}
            isApprovalDecisionPending={resolveTaskGraphApproval.isPending}
            isImportingGraph={importTaskGraphFile.isPending}
            isExportingGraph={exportTaskGraphFile.isPending}
            isSnapshotPending={createTaskGraphSnapshot.isPending}
            isSnapshotDiffPending={diffTaskGraphSnapshot.isPending}
            isSnapshotRollbackPending={rollbackTaskGraphToSnapshot.isPending}
          />
        ) : (
        <div className={`message-stream ${conversationVisuallyEmpty ? "message-stream-empty" : ""}`} data-testid="message-stream">
          {activeThread?.forkedFromId ? (
            <div className="task-fork-row">
              <span>分支来源任务</span>
              <strong>{activeThread.forkedFromId}</strong>
              <span>{activeThread.parentThreadId ? `父执行线路 ${activeThread.parentThreadId}` : "独立后续分支"}</span>
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
                onAcceptPlan={() => submitPlanFeedback("approve")}
                onRequestPlanChanges={(feedback) => submitPlanFeedback("adjust", feedback)}
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
          {(createThread.error || beginThreadCreate.error || beginThreadCreate.data?.status === "failed" || recoverThreadCreate.data?.status === "pending" || recoverThreadCreate.data?.status === "failed" || recoverThreadCreate.error) ? (
            <div className="error-text thread-create-error">
              <span>{beginThreadCreate.data?.status === "failed"
                ? beginThreadCreate.data.error
                : recoverThreadCreate.data?.status === "pending"
                  ? (locale === "zh-CN" ? "任务仍在初始化；可继续检查状态。" : "The task is still initializing; you can check its status again.")
                  : recoverThreadCreate.data?.status === "failed"
                    ? recoverThreadCreate.data.error
                    : describeSendError(t(locale, "new_thread"), createThread.error ?? beginThreadCreate.error ?? recoverThreadCreate.error)}</span>
              {threadCreateRecovery ? (
                <button
                  type="button"
                  className="ghost-button thread-create-recovery-action"
                  title={locale === "zh-CN" ? "只查询这次创建的最终状态，不会再次创建线程。" : "Checks this creation operation without starting another thread."}
                  disabled={recoverThreadCreate.isPending}
                  onClick={() => recoverThreadCreate.mutate({ profile_id: threadCreateRecovery.profileId, operation_id: threadCreateRecovery.operationId })}
                >
                  {recoverThreadCreate.isPending
                    ? (locale === "zh-CN" ? "正在检查" : "Checking")
                    : (locale === "zh-CN" ? "检查创建状态" : "Check creation status")}
                </button>
              ) : null}
              {recoverThreadCreate.data?.status === "pending" ? <small>{locale === "zh-CN" ? "线程仍在初始化；稍后再次检查。" : "The thread is still initializing; check again shortly."}</small> : null}
              {recoverThreadCreate.data?.status === "failed" ? <small>{recoverThreadCreate.data.error}</small> : null}
              {recoverThreadCreate.error ? <small>{String((recoverThreadCreate.error as Error).message ?? recoverThreadCreate.error)}</small> : null}
            </div>
          ) : null}
          {forkThread.error ? <div className="error-text">{describeSendError(t(locale, "fork_thread"), forkThread.error)}</div> : null}
          {conversationVisuallyEmpty ? <ConversationEmptyState locale={locale} state={conversationRenderState} /> : null}
        </div>
        )}

        {!graphWorkspaceOpen ? (
        <footer
          className={`composer ${attachmentDropActive ? "composer-drop-active" : ""}`}
          data-composer-rail-state={composerRailState}
          data-composer-rail-armed={composerRailArmed ? "true" : "false"}
          data-testid="composer"
          onDragEnter={(event) => {
            if (!dataTransferHasFiles(event.dataTransfer)) return;
            event.preventDefault();
            setAttachmentDropActive(true);
          }}
          onDragOver={(event) => {
            if (!dataTransferHasFiles(event.dataTransfer)) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
            setAttachmentDropActive(true);
          }}
          onDragLeave={(event) => {
            const nextTarget = event.relatedTarget;
            if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) {
              setAttachmentDropActive(false);
            }
          }}
          onDrop={(event) => void handleComposerDrop(event)}
          onPaste={(event) => void handleComposerPaste(event)}
        >
          {attachmentDropActive ? (
            <div className="composer-drop-hint" aria-live="polite">
              <StarbridgeAttachIcon size={15} strokeWidth={1.9} aria-hidden="true" />
              <span>{locale === "zh-CN" ? "松开即可添加附件" : "Drop to add attachments"}</span>
            </div>
          ) : null}
          <input
            ref={fileInputRef}
            className="hidden-file-input"
            type="file"
            multiple
            onChange={(event) => {
              void handleBrowserFileSelection(event.currentTarget.files, false);
              event.currentTarget.value = "";
            }}
          />
          <input
            ref={(node) => {
              directoryInputRef.current = node;
              if (node) {
                node.setAttribute("webkitdirectory", "");
                node.setAttribute("directory", "");
              }
            }}
            className="hidden-file-input"
            type="file"
            multiple
            onChange={(event) => {
              void handleBrowserFileSelection(event.currentTarget.files, true);
              event.currentTarget.value = "";
            }}
          />
          <div className="attachment-bar" aria-live="polite">
            {attachments.map((attachment, index) => (
              <div className={`attachment-card ${attachment.error ? "attachment-card-error" : ""}`} key={attachment.id} title={attachment.error || attachment.path || attachment.name}>
                {attachment.error ? (
                  <div className="attachment-file attachment-file-error">
                    <AlertTriangle size={15} strokeWidth={1.9} aria-hidden="true" />
                  </div>
                ) : attachment.kind === "image" && attachment.previewUrl ? (
                  <img src={attachment.previewUrl} alt={attachment.name} />
                ) : (
                  <div className="attachment-file">
                    {attachment.kind === "folder" ? (
                      <StarbridgeFolderIcon size={15} strokeWidth={1.85} aria-hidden="true" />
                    ) : attachment.kind === "image" ? (
                      <StarbridgeImageIcon size={15} strokeWidth={1.85} aria-hidden="true" />
                    ) : (
                      <StarbridgeFileIcon size={15} strokeWidth={1.85} aria-hidden="true" />
                    )}
                  </div>
                )}
                <div className="attachment-copy">
                  <strong>{attachment.name}</strong>
                  <span>{attachment.error || attachmentKindLabel(locale, attachment)}</span>
                </div>
                <div className="attachment-card-actions">
                  <button type="button" className="icon-button" disabled={index === 0} title={locale === "zh-CN" ? "上移" : "Move up"} aria-label={locale === "zh-CN" ? "上移附件" : "Move attachment up"} onClick={() => setAttachments((current) => current.map((item, itemIndex) => (itemIndex === index - 1 ? current[index] : itemIndex === index ? current[index - 1] : item)))}>
                    <ChevronUp size={13} strokeWidth={1.8} aria-hidden="true" />
                  </button>
                  <button type="button" className="icon-button" disabled={index === attachments.length - 1} title={locale === "zh-CN" ? "下移" : "Move down"} aria-label={locale === "zh-CN" ? "下移附件" : "Move attachment down"} onClick={() => setAttachments((current) => current.map((item, itemIndex) => (itemIndex === index + 1 ? current[index] : itemIndex === index ? current[index + 1] : item)))}>
                    <ChevronDown size={13} strokeWidth={1.8} aria-hidden="true" />
                  </button>
                  <button type="button" className="icon-button" title={locale === "zh-CN" ? "移除" : "Remove"} aria-label={locale === "zh-CN" ? "移除附件" : "Remove attachment"} onClick={() => setAttachments((current) => current.filter((item) => item.id !== attachment.id))}>
                    <X size={13} strokeWidth={1.9} aria-hidden="true" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          {attachmentRouteLine ? (
            <p
              className={`attachment-route-note ${imageAttachmentUnsupported ? "attachment-route-warning" : ""}`}
              title={
                imageAttachmentUnsupported
                  ? imageAttachmentRouteMessage
                  : locale === "zh-CN"
                    ? "附件会随下一轮发送。图片将作为视觉输入，普通文件和文件夹将作为文件引用。"
                    : "Attachments will be sent with the next turn. Images route as visual input; files and folders route as file mentions."
              }
            >
              {imageAttachmentUnsupported ? `${attachmentRouteSummary(locale, sendableAttachments)} · ${imageAttachmentRouteMessage}` : attachmentRouteLine}
            </p>
          ) : null}
          {attachmentNotice ? <p className="attachment-notice">{attachmentNotice}</p> : null}
          {shouldShowGoalDock ? (
            <GoalModeDock
              locale={locale}
              goal={displayGoal}
              draft={goalDraft}
              onDraftChange={setGoalDraft}
              canWriteGoal={Boolean(selectedThreadId)}
              editMode={goalEditMode}
              onEditModeChange={setGoalEditMode}
              activeTab={composerWorkflowMode === "plan" ? "plan" : "goal"}
              onTabChange={setGoalDockTab}
              runnerArmed={goalRunnerArmed}
              queueCount={instructionQueue.length}
              plan={inspectorPlan}
              proposedPlanText={livePlanText || proposedPlanText}
              onSetActive={() => setThreadGoal("active")}
              onPause={() => setThreadGoal("paused")}
              onResume={() => setThreadGoal("active")}
              onClear={clearThreadGoal}
            />
          ) : null}
          <QueuedInstructionQueue
            locale={locale}
            items={instructionQueue}
            expanded={instructionQueueExpanded}
            editingId={instructionQueueEditingId}
            busyId={instructionQueueBusyId}
            blockedId={instructionQueueBlockedId}
            onToggleExpanded={() => setInstructionQueueExpanded((value) => !value)}
            onEdit={editQueuedInstruction}
            onCancelEdit={() => setInstructionQueueEditingId(null)}
            onSaveEdit={saveQueuedInstruction}
            onSendNow={(id) => void sendQueuedInstructionNow(id)}
          />
          <div className="composer-surface">
            <div
              className="composer-resize-grip"
              role="separator"
              aria-orientation="horizontal"
              aria-label={locale === "zh-CN" ? "拖动以调整对话框输入高度" : "Drag to resize composer input height"}
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === "ArrowUp") {
                  event.preventDefault();
                  composerInputResize.setHeightByDelta(18);
                } else if (event.key === "ArrowDown") {
                  event.preventDefault();
                  composerInputResize.setHeightByDelta(-18);
                }
              }}
              {...composerInputResize.bind}
            />
            <textarea
              data-testid="composer-input"
              value={composerText}
              onChange={(event) => setComposerText(event.target.value)}
              rows={6}
              style={{ height: `${composerInputResize.height}px` }}
              placeholder={t(locale, "composer_placeholder")}
            />
            <div className="composer-controls composer-toolbar">
              <div className="composer-toolbar-left">
              <div
                className="attachment-picker"
                onBlur={(event) => {
                  const nextTarget = event.relatedTarget;
                  if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) {
                    setAttachmentMenuOpen(false);
                  }
                }}
              >
                <button
                  type="button"
                  className="composer-plus"
                  onClick={handleAddAttachments}
                  aria-label={t(locale, "add_files")}
                  aria-haspopup="menu"
                  aria-expanded={attachmentMenuOpen}
                  title={t(locale, "add_files")}
                >
                  <StarbridgeAttachIcon size={15} strokeWidth={1.9} aria-hidden="true" />
                </button>
                {attachmentMenuOpen ? (
                  <div className="attachment-menu" role="menu" aria-label={t(locale, "add_files")}>
                    <button type="button" role="menuitem" onClick={() => void chooseAttachmentFiles()}>
                      <StarbridgeFileIcon size={14} strokeWidth={1.85} aria-hidden="true" />
                      <span>{locale === "zh-CN" ? "选择文件" : "Choose files"}</span>
                    </button>
                    <button type="button" role="menuitem" onClick={() => void chooseAttachmentFolder()}>
                      <StarbridgeFolderIcon size={14} strokeWidth={1.85} aria-hidden="true" />
                      <span>{locale === "zh-CN" ? "选择文件夹" : "Choose folder"}</span>
                    </button>
                  </div>
                ) : null}
              </div>
              <PermissionModePicker
                locale={locale}
                value={activeSettings.permission_mode}
                onChange={(value) => updateComposerSettings({ permission_mode: value })}
              />
              <ExecutionPolicyPicker locale={locale} value={composerExecutionPolicy} onChange={setComposerExecutionPolicy} />
              <WorkflowModePicker locale={locale} value={composerWorkflowMode} onChange={setComposerWorkflowMode} />
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
                    mergedComposerCatalogModels.find((model) => model.provider === nextProviderId && model.native_model === nextModel) ??
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
                    mergedComposerCatalogModels.find((model) => model.provider === activeProfile?.provider_id && model.native_model === event.target.value) ??
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
              <button
                type="button"
                className={`voice-transcribe-button compact-action voice-transcribe-${voiceRecorderState} ${speechTranscribeReady ? "" : "voice-transcribe-needs-setup"}`}
                data-testid="composer-voice-transcribe"
                onClick={() => void handleVoiceTranscribeClick()}
                disabled={voiceRecorderState === "transcribing"}
                title={voiceButtonTitle}
                aria-label={voiceButtonTitle}
                aria-pressed={voiceRecorderState === "recording"}
              >
                <StarbridgeVoiceIcon size={15} strokeWidth={1.9} aria-hidden="true" />
                {voiceRecorderState === "recording" ? <span className="voice-recording-dot" aria-hidden="true" /> : null}
              </button>
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
                    sidebarSelectionBusy ||
                    (!composerText.trim() && sendableAttachments.length === 0) ||
                    startTurn.isPending ||
                    createThread.isPending ||
                    beginThreadCreate.isPending ||
                    Boolean(taskCreationPending)
                  }
                  onClick={handleSend}
                  aria-label={startTurn.isPending || createThread.isPending || beginThreadCreate.isPending || taskCreationPending ? t(locale, "loading") : t(locale, "send")}
                >
                <span className="composer-send-label">{startTurn.isPending || createThread.isPending || beginThreadCreate.isPending || taskCreationPending ? t(locale, "loading") : t(locale, "send")}</span>
                <span className="composer-send-icon" aria-hidden="true"><StarbridgeSendIcon size={14} strokeWidth={1.95} /></span>
                </button>
              </div>
            </div>
            <ComposerStarTrack state={composerRailState} armed={composerRailArmed} />
          </div>
          {sendStage ? <p className="send-stage">{sendStage}</p> : null}
        </footer>
        ) : null}
        </div>
        </div>
          </>
        )}
      </section>

      {inspectorVisible ? <div className="resize-handle" {...rightPane.bind} /> : null}

      {inspectorVisible ? (
        <aside className="inspector">
          <InspectorTabBar locale={locale} activeTab={inspectorTab} onChange={setInspectorTab} />
          <div className="inspector-scroll-shell starbridge-surface-panel">
            {inspectorTab === "status" ? (
              <>
                <RuntimeStatusSummary
                  locale={locale}
                  activeStatusType={activeStatusType}
                  waitingOnApproval={waitingOnApproval}
                  sending={startTurn.isPending || createThread.isPending || beginThreadCreate.isPending || Boolean(taskCreationPending)}
                  queueCount={instructionQueue.length}
                  canInterrupt={canInterrupt}
                  goal={displayGoal}
                />
                <RuntimeAttentionPanel locale={locale} items={statusAttentionItems} />
                <RecoveryActionsPanel
                  locale={locale}
                  actions={runtimeRecoveryActions}
                  pendingAction={runtimeRecoveryPendingAction}
                  onAction={handleRuntimeRecoveryAction}
                />
                <CompactGoalStatusPanel
                  locale={locale}
                  goal={displayGoal}
                  draft={goalDraft}
                  editMode={goalEditMode}
                  canWriteGoal={Boolean(selectedThreadId)}
                  onDraftChange={setGoalDraft}
                  onEditModeChange={setGoalEditMode}
                  onSetActive={() => setThreadGoal("active")}
                  onPauseResume={() => (displayGoal?.status === "active" ? setThreadGoal("paused") : setThreadGoal("active"))}
                  onClear={clearThreadGoal}
                />
                <CompactPlanStatusPanel
                  locale={locale}
                  plan={inspectorPlan}
                  planText={livePlanText || proposedPlanText || ""}
                  expanded={statusPlanExpanded}
                  onToggle={() => setStatusPlanExpanded((value) => !value)}
                />
                <EnvironmentStrip
                  locale={locale}
                  supervisor={supervisorForDisplay}
                  fallback={{
                    permission: permissionLabel(locale, activeSettings.permission_mode),
                  }}
                />
                <StatusEvidencePanel locale={locale} items={statusEvidenceItems} />
                {showWorkflowEvidencePanel ? <WorkflowEvidencePanel locale={locale} facts={workflowFacts} /> : null}
              </>
            ) : null}
            {inspectorTab === "review" ? (
              <ReviewInspectorPanel
                locale={locale}
                supervisor={supervisorForDisplay}
                review={inspectorReview.data}
                diff={inspectorReviewDiff.data}
                fallback={taskInspectorEvidence}
                selectedPath={inspectorReviewPath}
                onSelectPath={setInspectorReviewPath}
              />
            ) : null}
            {inspectorTab === "browser" ? (
                <BrowserInspectorPanel
                  locale={locale}
                  supervisor={supervisorForDisplay}
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
                mediaUrl={inspectorFileMediaUrl.data}
                previewLoading={inspectorFilePreview.isFetching}
                previewError={inspectorFilePreviewError}
                mediaError={inspectorFileMediaError}
                fallback={taskInspectorEvidence}
                query={inspectorFileQuery}
                selectedPath={inspectorFilePath}
                onQueryChange={setInspectorFileQuery}
                onSelectPath={setInspectorFilePath}
              />
            ) : null}
          </div>
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
            <button type="button" className="command-item" onClick={() => { setCommandPaletteOpen(false); toggleLeftSidebar(); }}>
              {t(locale, "command_toggle_sidebar")}
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
                  {options.map((option, index) => {
                    const selected = entry.option === option.label;
                    const description = String(option.description ?? "");
                    const tooltipId = `${id}-${index}-choice-detail`;
                    return (
                      <label
                        className={`choice-row ${selected ? "choice-row-selected" : ""} ${index === 0 ? "choice-row-recommended" : ""}`}
                        key={`${id}-${option.label}`}
                        title={description}
                      >
                        <input
                          type="radio"
                          checked={selected}
                          aria-describedby={description ? tooltipId : undefined}
                          onChange={() => setAnswers((current) => ({ ...current, [id]: { ...current[id], option: option.label } }))}
                        />
                        <div className="choice-copy">
                          <span>
                            {option.label} {index === 0 ? <em>{t(locale, "request_recommended")}</em> : null}
                          </span>
                          {description ? <small>{description}</small> : null}
                        </div>
                        {description ? (
                          <span className="choice-tooltip" id={tooltipId} role="tooltip">
                            {description}
                          </span>
                        ) : null}
                      </label>
                    );
                  })}
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

function LaunchIsolationScreen({ reason }: { reason: string }) {
  return (
    <main className="launch-isolation-shell">
      <section className="launch-isolation-card starbridge-surface-panel starbridge-surface-guard" role="alert" aria-live="polite">
        <span className="eyebrow">AstraBridge</span>
        <h1>请从星桥桌面入口打开</h1>
        <p>
          当前页面是本地开发服务的非受控入口。为避免其他客户端误连星桥 dev 端口后进入项目状态，星桥不会在这个入口渲染项目界面。
        </p>
        <div className="launch-isolation-facts">
          <div>
            <span>当前入口</span>
            <strong>{typeof window === "undefined" ? "unknown" : window.location.origin}</strong>
          </div>
          <div>
            <span>隔离原因</span>
            <strong>{reason}</strong>
          </div>
        </div>
        <p className="muted">
          请使用星桥桌面窗口，或使用带 <code>astrabridge_launch</code> / <code>ab_session</code> 标记的受控测试入口。仅有 <code>sidecar</code> 或 <code>smoke</code> 参数不会打开项目界面。
        </p>
        <StarbridgeCornerConstellation variant="guard" />
      </section>
    </main>
  );
}

export default function App() {
  const cursorEnhancement = useAppStore((store) => store.cursorEnhancement);
  const launchIsolation = evaluateLaunchIsolation(typeof window === "undefined" ? "" : window.location.href, {
    isDev: import.meta.env.DEV,
    isTauri: isTauri(),
    allowBareDev: import.meta.env.VITE_ASTRABRIDGE_ALLOW_BARE_DEV === "1",
  });
  if (!launchIsolation.allowed) {
    return (
      <>
        <StarbridgeCursorOverlay preference={cursorEnhancement} />
        <LaunchIsolationScreen reason={launchIsolation.reason} />
      </>
    );
  }
  if (brandWaitingPreviewMode()) {
    return (
      <>
        <StarbridgeCursorOverlay preference={cursorEnhancement} />
        <StarbridgeWaitingPreview />
      </>
    );
  }

  const setProject = useAppStore((store) => store.setProject);
  const project = useAppStore((store) => store.project);
  const current = useQuery({
    queryKey: ["project"],
    queryFn: api.currentProject,
    retry: false,
    refetchInterval: project ? false : 5000,
    staleTime: project ? 60_000 : 0,
  });

  useEffect(() => {
    if (current.data?.project) {
      setProject(current.data.project);
    }
  }, [current.data?.project, setProject]);

  const bootstrapProject = current.data?.project ?? null;
  const hasProject = Boolean(project ?? bootstrapProject);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.dataset.appBootstrapDebug = JSON.stringify({
      surface: hasProject ? "app-shell" : "root-launcher-gate",
      hasProject,
      storeProjectId: project?.project_id ?? null,
      bootstrapProjectId: bootstrapProject?.project_id ?? null,
      currentStatus: current.status,
      currentFetchStatus: current.fetchStatus,
      currentError: current.error instanceof Error ? current.error.message : current.error ? String(current.error) : null,
      at: Date.now(),
    });
  }, [
    bootstrapProject?.project_id,
    current.error,
    current.fetchStatus,
    current.status,
    hasProject,
    project?.project_id,
  ]);

  return (
    <>
      <StarbridgeCursorOverlay preference={cursorEnhancement} />
      {hasProject ? <AppShell bootstrapProject={bootstrapProject} /> : <Launcher />}
    </>
  );
}


