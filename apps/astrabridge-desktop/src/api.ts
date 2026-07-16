import { invoke, isTauri } from "@tauri-apps/api/core";
import type {
  AppearancePreset,
  AgenticUpdateJobStatus,
  AgenticUpdateProposalResult,
  AgenticUpdateRunList,
  AgenticUpdateStartPayload,
  AutomationInboxItem,
  AutomationInboxResponse,
  AutomationListResponse,
  AutomationRun,
  AutomationRunsResponse,
  AutomationSchedulerStatus,
  AutomationSpec,
  AssetRegistryResponse,
  AttachmentDraft,
  AttachmentStageFile,
  AttachmentStageResponse,
  BrowserWorkbenchCreateRequest,
  BrowserWorkbenchLayoutRequest,
  BrowserWorkbenchNavigateRequest,
  BrowserWorkbenchSession,
  ComputerUseBrowserScenarioReport,
  CapabilityArtifactsResponse,
  CapabilityInvokeResponse,
  CollaborationMode,
  CapabilityManagementResponse,
  CapabilityRouteEntry,
  CapabilityRouteRecord,
  CapabilitySmokeResponse,
  CodexPluginInstallExecution,
  CodexKernelProbeSnapshot,
  CodexPluginInstallPlan,
  CodexPluginSkillRegistrySnapshot,
  SkillPluginCreatorScenarioExecution,
  ContextMode,
  CursorEnhancementPreference,
  DogfoodRun,
  DogfoodRunResponse,
  EffectiveCatalogResponse,
  ExecutionHost,
  GoalResponse,
  IsolationAuditResponse,
  LlmEffectiveCatalogResponse,
  LlmHealthResultsResponse,
  LlmManagerKeysResponse,
  LlmManagerSession,
  MetadataRefreshResponse,
  MetadataRefreshJobStartResponse,
  MetadataRefreshJobStatusResponse,
  MetadataReportResponse,
  MetadataSourcesResponse,
  NativeKernelDemoResponse,
  McpConfigResponse,
  McpServerConfig,
  McpStatusResponse,
  PermissionMode,
  TurnExecutionPolicy,
  Profile,
  ProjectFile,
  ProjectFilePreview,
  ProjectFilesTree,
  ProjectReviewDiff,
  ProjectReviewStatus,
  ReleaseWorkflowDemoResponse,
  ProjectContextPackResponse,
  ProjectSaveCreateResponse,
  ProjectSaveLoadResponse,
  ProjectSavesResponse,
  SidebarProjectsResponse,
  ProjectSummary,
  ProjectTask,
  ProjectTasksResponse,
  ReasoningConfig,
  RouterConfigResponse,
  RouterModelEntry,
  RouterProvider,
  RouterTestResult,
  RuntimeEnvironment,
  RuntimeEvent,
  RuntimeModal,
  RuntimeSupervisorState,
  AgentOrchestrationGraphExportResponse,
  AgentOrchestrationGraphImportResponse,
  ProjectTerminalHistory,
  ShellThread,
  TaskGraphDefinition,
  TaskGraphDryRunResult,
  TaskGraphNode,
  TaskGraphRecoverySummary,
  TaskGraphRollbackResponse,
  TaskGraphRunRef,
  TaskGraphSnapshotDiffResponse,
  TaskGraphSnapshotResponse,
  TaskGraphTemplateSummary,
  TaskConversationResponse,
  TestMatrixResponse,
  TitleSuggestionResponse,
  ThreadListResponse,
  ThreadCreateRecoveryResponse,
  ThreadReadResponse,
  TurnStartResponse,
  WebFetchRequest,
  WebFetchResponse,
  WebResearchBriefRequest,
  WebResearchBriefResponse,
  WebSearchBatchRequest,
  WebSearchBatchResponse,
  WslBootstrapScriptsResponse,
  WslDependencyStatus,
  YunwuImageSmokeResponse,
} from "./types";
import { requestWebFetch, requestWebResearchBrief, requestWebSearchBatch } from "./features/web/webToolClient";
import { visibleTaskTitle, visibleThreadTitle } from "./features/navigation/displayTitle";

let sidecarBaseUrlPromise: Promise<string> | null = null;
type AdminSessionTokenCacheEntry = {
  promise: Promise<string>;
  startedAt: number;
  purpose: "prewarm" | "mutation";
  settled: boolean;
};
type AdminSessionTokenCacheRecord = AdminSessionTokenCacheEntry | Promise<string>;
const adminTokenPromises = new Map<string, AdminSessionTokenCacheRecord>();
const TASK_GRAPH_DEBUG_DATASET_KEY = "taskGraphDebug";
const ADMIN_SESSION_TIMEOUT_MS = 12000;
const BROWSER_SIDECAR_PROXY_PREFIX = "/__astrabridge_proxy__";

const SIDECAR_URL_STORAGE_KEY = "astrabridge.sidecarBaseUrl";
const THREAD_CREATE_RECEIPT_TIMEOUT_MS = 20000;

function writeRequestDebugDataset(key: string, value: Record<string, unknown>) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset[key] = JSON.stringify({
    ...value,
    at: Date.now(),
  });
}

export class ApiRequestError extends Error {
  status?: number;
  data?: Record<string, unknown>;

  constructor(message: string, options?: { status?: number; data?: Record<string, unknown> }) {
    super(message);
    this.name = "ApiRequestError";
    this.status = options?.status;
    this.data = options?.data;
  }
}

function normalizeSidecarBaseUrl(value: string | null | undefined) {
  const trimmed = value?.trim();
  if (!trimmed) return "";
  try {
    const url = new URL(trimmed);
    if (!["http:", "https:"].includes(url.protocol)) return "";
    url.pathname = url.pathname.replace(/\/+$/, "");
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch {
    return "";
  }
}

function normalizeProjectFilePath(value: string | null | undefined) {
  return String(value ?? "")
    .trim()
    .replace(/\\/g, "/")
    .replace(/\/+/g, "/")
    .toLowerCase();
}

function isAdminSessionTokenCacheEntry(
  value: AdminSessionTokenCacheRecord | undefined,
): value is AdminSessionTokenCacheEntry {
  if (!value || typeof value !== "object") return false;
  return "promise" in value && "startedAt" in value && "purpose" in value && "settled" in value;
}

function configuredBrowserSidecarTargetBaseUrl() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = normalizeSidecarBaseUrl(params.get("sidecar"));
  if (fromQuery) {
    window.localStorage.setItem(SIDECAR_URL_STORAGE_KEY, fromQuery);
    return fromQuery;
  }
  const fromStorage = normalizeSidecarBaseUrl(window.localStorage.getItem(SIDECAR_URL_STORAGE_KEY));
  if (fromStorage) return fromStorage;
  const fromEnv = normalizeSidecarBaseUrl(import.meta.env.VITE_ASTRABRIDGE_SIDECAR_URL);
  if (fromEnv) return fromEnv;
  return "http://127.0.0.1:8790";
}

function shouldUseBrowserSidecarProxy() {
  if (typeof window === "undefined" || isTauri()) return false;
  const userAgent = window.navigator?.userAgent ?? "";
  return !/\bjsdom\b/i.test(userAgent);
}

function browserSidecarProxyUrl(suffix: string) {
  const url = new URL(`${BROWSER_SIDECAR_PROXY_PREFIX}${suffix}`, window.location.origin);
  url.searchParams.set("__sidecar", configuredBrowserSidecarTargetBaseUrl());
  return url.toString();
}

function browserSidecarBaseUrl() {
  if (shouldUseBrowserSidecarProxy()) {
    return `${window.location.origin}${BROWSER_SIDECAR_PROXY_PREFIX}`;
  }
  return configuredBrowserSidecarTargetBaseUrl();
}

function querySidecarBaseUrl() {
  if (typeof window === "undefined") return "";
  return normalizeSidecarBaseUrl(new URLSearchParams(window.location.search).get("sidecar"));
}

function hasConfiguredBrowserSidecarBaseUrl() {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  if (normalizeSidecarBaseUrl(params.get("sidecar"))) return true;
  if (normalizeSidecarBaseUrl(window.localStorage.getItem(SIDECAR_URL_STORAGE_KEY))) return true;
  return Boolean(normalizeSidecarBaseUrl(import.meta.env.VITE_ASTRABRIDGE_SIDECAR_URL));
}

async function sidecarBaseUrl() {
  if (!isTauri()) {
    // Browser dogfood can intentionally switch ?sidecar= between isolated
    // processes, but all browser requests should still stay on the same-origin
    // proxy when that proxy is active. The proxy target itself is derived from
    // the current query/storage config inside browserSidecarBaseUrl().
    return browserSidecarBaseUrl();
  }
  // A URL route is an explicit operator choice for the desktop host. Honor it
  // before checking the bound sidecar so embedded launchers do not accidentally
  // reuse another desktop-side session.
  const fromQuery = querySidecarBaseUrl();
  if (fromQuery) return fromQuery;
  if (!sidecarBaseUrlPromise) {
    sidecarBaseUrlPromise = invoke<string>("sidecar_url");
  }
  return sidecarBaseUrlPromise;
}

function normalizeProviderThreadName<T extends { name?: string | null }>(thread: T): T {
  if (typeof thread.name !== "string") return thread;
  const visibleName = visibleThreadTitle(thread.name);
  if (visibleName === thread.name) return thread;
  return {
    ...thread,
    name: visibleName,
  };
}

export function normalizeProjectTask(task: ProjectTask): ProjectTask {
  return {
    ...task,
    title: visibleTaskTitle(task.title),
    provider_threads: Array.isArray(task.provider_threads) ? task.provider_threads.map(normalizeProviderThreadName) : [],
    fork_threads: Array.isArray(task.fork_threads) ? task.fork_threads.map(normalizeProviderThreadName) : [],
  };
}

export function normalizeShellThread(thread: ShellThread): ShellThread {
  return {
    ...thread,
    name: thread.name ? visibleThreadTitle(thread.name) : thread.name,
    displayName: visibleThreadTitle(thread.displayName),
    preview: visibleThreadTitle(thread.preview),
    provider_threads: Array.isArray(thread.provider_threads) ? thread.provider_threads.map(normalizeProviderThreadName) : thread.provider_threads,
  };
}

export function normalizeSidebarProjectsResponse(response: SidebarProjectsResponse): SidebarProjectsResponse {
  return {
    ...response,
    projects: response.projects.map((project) => ({
      ...project,
      tasks: project.tasks.map((task) => ({
        ...task,
        title: visibleTaskTitle(task.title),
        active_lane_label: task.active_lane_label ? visibleThreadTitle(task.active_lane_label) : task.active_lane_label,
        previous_lane_label: task.previous_lane_label ? visibleThreadTitle(task.previous_lane_label) : task.previous_lane_label,
        threads: Array.isArray(task.threads)
          ? task.threads.map((thread) => ({
              ...thread,
              title: visibleThreadTitle(thread.title),
            }))
          : [],
      })),
    })),
  };
}

export function normalizeProjectTasksResponse(response: ProjectTasksResponse): ProjectTasksResponse {
  return {
    ...response,
    current_task: response.current_task ? normalizeProjectTask(response.current_task) : null,
    tasks: response.tasks.map(normalizeProjectTask),
  };
}

export function normalizeThreadListResponse(response: ThreadListResponse): ThreadListResponse {
  return {
    ...response,
    threads: response.threads.map(normalizeShellThread),
  };
}

export function normalizeThreadReadResponse(response: ThreadReadResponse): ThreadReadResponse {
  return {
    ...response,
    thread: normalizeShellThread(response.thread),
    task: response.task ? normalizeProjectTask(response.task) : response.task,
  };
}

export function normalizeTaskConversationResponse(response: TaskConversationResponse): TaskConversationResponse {
  return {
    ...response,
    thread: normalizeShellThread(response.thread),
    task: response.task ? normalizeProjectTask(response.task) : response.task,
  };
}

export function projectFileMediaHref(path: string) {
  const suffix = `/api/project/files/media?path=${encodeURIComponent(path)}`;
  if (typeof window === "undefined") {
    return suffix;
  }
  if (shouldUseBrowserSidecarProxy()) {
    return browserSidecarProxyUrl(suffix);
  }
  return `${browserSidecarBaseUrl()}${suffix}`;
}

export function projectFileReadHref(path: string) {
  const suffix = `/api/project/files/read?path=${encodeURIComponent(path)}`;
  if (typeof window === "undefined") {
    return suffix;
  }
  if (shouldUseBrowserSidecarProxy()) {
    return browserSidecarProxyUrl(suffix);
  }
  return `${browserSidecarBaseUrl()}${suffix}`;
}

type RequestWithTimeout = RequestInit & {
  timeoutMs?: number;
  acceptOkFalse?: boolean;
  onRequestStage?: (stage: string) => void;
};

function requestAbortTimer(callback: () => void, timeoutMs: number) {
  if (typeof window !== "undefined" && typeof window.setTimeout === "function") {
    return window.setTimeout(callback, timeoutMs);
  }
  return globalThis.setTimeout(callback, timeoutMs);
}

function clearRequestAbortTimer(timer: ReturnType<typeof setTimeout>) {
  if (typeof window !== "undefined" && typeof window.clearTimeout === "function") {
    window.clearTimeout(timer);
    return;
  }
  globalThis.clearTimeout(timer);
}

function timeoutError(path: string) {
  return new Error(
    `The desktop sidecar did not respond in time for ${path}. Open Runtime and verify Codex login, provider key, model, and router health.`,
  );
}

class ResponseBodyTimeoutError extends Error {
  path: string;

  constructor(path: string) {
    super(`Timed out while reading the response body for ${path}.`);
    this.name = "ResponseBodyTimeoutError";
    this.path = path;
  }
}

async function readJsonResponseWithTimeout(
  response: Response,
  options: {
    path: string;
    controller: AbortController;
    timeoutMs: number;
  },
) {
  let data: Record<string, unknown> = {};
  let rawBody = "";
  let bodyTimer: ReturnType<typeof setTimeout> | null = null;
  try {
    rawBody = (await Promise.race([
      (typeof response.text === "function"
        ? response.text()
        : (response.json() as Promise<unknown>).then((value) => JSON.stringify(value))) as Promise<string>,
      new Promise<never>((_, reject) => {
        bodyTimer = requestAbortTimer(() => {
          options.controller.abort();
          reject(new ResponseBodyTimeoutError(options.path));
        }, options.timeoutMs);
      }),
    ])) as string;
  } catch (error) {
    if (error instanceof ResponseBodyTimeoutError) {
      throw timeoutError(options.path);
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw timeoutError(options.path);
    }
    rawBody = "";
  } finally {
    if (bodyTimer) {
      clearRequestAbortTimer(bodyTimer);
    }
  }
  if (!rawBody.trim()) return data;
  try {
    data = JSON.parse(rawBody) as Record<string, unknown>;
  } catch {
    data = {};
  }
  return data;
}

async function fetchAdminSessionToken(base: string, options?: { refresh?: boolean; purpose?: "prewarm" | "mutation" }) {
  const purpose = options?.purpose ?? "mutation";
  if (options?.refresh) {
    adminTokenPromises.delete(base);
  } else {
    const existing = adminTokenPromises.get(base);
    if (existing) {
      if (isAdminSessionTokenCacheEntry(existing)) {
        const stalePending = !existing.settled && Date.now() - existing.startedAt >= ADMIN_SESSION_TIMEOUT_MS;
        const prewarmPendingForMutation =
          !existing.settled && existing.purpose === "prewarm" && purpose === "mutation";
        if (!stalePending && !prewarmPendingForMutation) {
          return existing.promise;
        }
      } else if (purpose === "prewarm") {
        return existing;
      }
      adminTokenPromises.delete(base);
    }
  }
  const entry: AdminSessionTokenCacheEntry = {
    promise: Promise.resolve(""),
    startedAt: Date.now(),
    purpose,
    settled: false,
  };
  const adminTokenPromise = (async () => {
    const controller = new AbortController();
    const timer = requestAbortTimer(() => controller.abort(), ADMIN_SESSION_TIMEOUT_MS);
    try {
      const headers: Record<string, string> = {};
      const adminSessionBase = shouldUseBrowserSidecarProxy()
        ? configuredBrowserSidecarTargetBaseUrl()
        : base;
      const response = await fetch(`${adminSessionBase}/api/admin/session`, {
        headers,
        cache: "no-store",
        signal: controller.signal,
      });
      const data = await readJsonResponseWithTimeout(response, {
        path: "/api/admin/session",
        controller,
        timeoutMs: ADMIN_SESSION_TIMEOUT_MS,
      });
      if (!response.ok) {
        throw new ApiRequestError(String(data.error ?? "Failed to establish desktop admin session."), {
          status: response.status,
          data,
        });
      }
      const token = String(data.admin_session_token ?? "").trim();
      if (!token) {
        throw new Error("The desktop sidecar returned an empty admin session token.");
      }
      return token;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw timeoutError("/api/admin/session");
      }
      throw error;
    } finally {
      entry.settled = true;
      clearRequestAbortTimer(timer);
    }
  })();
  entry.promise = adminTokenPromise;
  adminTokenPromises.set(base, entry);
  adminTokenPromise.catch(() => {
    if (adminTokenPromises.get(base) === entry) {
      adminTokenPromises.delete(base);
    }
  });
  return adminTokenPromise;
}

export function seedLegacyAdminSessionTokenPromiseForTests(base: string, promise: Promise<string>) {
  adminTokenPromises.set(base, promise);
}

function shouldRefreshAdminSession(response: Response, data: Record<string, unknown>, alreadyRetried: boolean) {
  if (alreadyRetried) return false;
  if (response.status === 401 || response.status === 403) return true;
  if (response.status !== 400) return false;
  return typeof data.error === "string" && data.error.toLowerCase().includes("admin session token");
}

export function resetApiModuleStateForTests() {
  sidecarBaseUrlPromise = null;
  adminTokenPromises.clear();
}

async function request<T>(path: string, init?: RequestWithTimeout): Promise<T> {
  const base = await sidecarBaseUrl();
  const isTaskGraphInstantiate = path === "/api/task-graphs/instantiate";
  const isTaskGraphRun = path === "/api/task-graphs/run";
  const isCurrentProjectRequest = path === "/api/projects/current";
  const isHealthRequest = path === "/health";
  const fetchInit = { ...(init ?? {}) };
  const acceptOkFalse = Boolean(fetchInit.acceptOkFalse);
  const onRequestStage = fetchInit.onRequestStage;
  delete fetchInit.timeoutMs;
  delete fetchInit.acceptOkFalse;
  delete fetchInit.onRequestStage;
  const isMutation = (init?.method ?? "GET").toUpperCase() !== "GET";
  const timeoutMs = init?.timeoutMs ?? (isMutation ? 65000 : 15000);
  const cacheMode = init?.cache ?? (isMutation ? "no-store" : "no-store");
  const headers: Record<string, string> = { ...((fetchInit.headers ?? {}) as Record<string, string>) };
  if (shouldUseBrowserSidecarProxy()) {
    headers["X-AstraBridge-Sidecar-Base"] = configuredBrowserSidecarTargetBaseUrl();
  }
  if (isMutation || fetchInit.body) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
  }
  if (isMutation) {
    if (isTaskGraphRun && typeof window !== "undefined") {
      document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
        stage: "run_token_requested",
        base,
        path,
        at: Date.now(),
      });
    }
    onRequestStage?.("run_token_requested");
    headers["X-Admin-Token"] = await fetchAdminSessionToken(base);
    if (isTaskGraphRun && typeof window !== "undefined") {
      document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
        stage: "run_token_prepared",
        base,
        tokenLength: headers["X-Admin-Token"]?.length ?? 0,
        path,
        at: Date.now(),
      });
    }
    onRequestStage?.("run_token_prepared");
    if (isTaskGraphInstantiate) {
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "instantiate_token_prepared",
          base,
          tokenLength: headers["X-Admin-Token"]?.length ?? 0,
          path,
          at: Date.now(),
        });
      }
      console.warn("[task-graph] instantiate token prepared", {
        base,
        tokenLength: headers["X-Admin-Token"]?.length ?? 0,
      });
    }
  }
  const controller = new AbortController();
  const timer = requestAbortTimer(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    if (isCurrentProjectRequest) {
      writeRequestDebugDataset("appRequestCurrentProjectDebug", {
        stage: "fetch_started",
        base,
        timeoutMs,
      });
    }
    if (isHealthRequest) {
      writeRequestDebugDataset("appRequestHealthDebug", {
        stage: "fetch_started",
        base,
        timeoutMs,
      });
    }
    if (isTaskGraphRun && typeof window !== "undefined") {
      document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
        stage: "run_fetch_started",
        base,
        path,
        timeoutMs,
        at: Date.now(),
      });
    }
    onRequestStage?.("run_fetch_started");
    if (isTaskGraphInstantiate && typeof window !== "undefined") {
      document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
        stage: "instantiate_fetch_started",
        path,
        at: Date.now(),
      });
    }
    response = await fetch(`${base}${path}`, {
      headers,
      cache: cacheMode,
      ...fetchInit,
      signal: controller.signal,
    });
    if (isCurrentProjectRequest) {
      writeRequestDebugDataset("appRequestCurrentProjectDebug", {
        stage: "fetch_resolved",
        status: response.status,
        ok: response.ok,
      });
    }
    if (isHealthRequest) {
      writeRequestDebugDataset("appRequestHealthDebug", {
        stage: "fetch_resolved",
        status: response.status,
        ok: response.ok,
      });
    }
  } catch (error) {
    clearRequestAbortTimer(timer);
    if (error instanceof DOMException && error.name === "AbortError") {
      throw timeoutError(path);
    }
    if (isTaskGraphRun && typeof window !== "undefined") {
      document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
        stage: "run_fetch_threw",
        base,
        path,
        error: String(error),
        at: Date.now(),
      });
    }
    onRequestStage?.("run_fetch_threw");
    if (isTaskGraphInstantiate) {
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "instantiate_fetch_threw",
          error: String(error),
          at: Date.now(),
        });
      }
      console.error("[task-graph] instantiate fetch threw", error);
    }
    if (isCurrentProjectRequest) {
      writeRequestDebugDataset("appRequestCurrentProjectDebug", {
        stage: "fetch_threw",
        error: String(error),
      });
    }
    if (isHealthRequest) {
      writeRequestDebugDataset("appRequestHealthDebug", {
        stage: "fetch_threw",
        error: String(error),
      });
    }
    throw error;
  }
  clearRequestAbortTimer(timer);
  let data = await readJsonResponseWithTimeout(response, {
    path,
    controller,
    timeoutMs,
  });
  if (isCurrentProjectRequest) {
    writeRequestDebugDataset("appRequestCurrentProjectDebug", {
      stage: "body_resolved",
      status: response.status,
      ok: response.ok,
      hasProject: Boolean((data as { project?: unknown }).project),
    });
  }
  if (isHealthRequest) {
    writeRequestDebugDataset("appRequestHealthDebug", {
      stage: "body_resolved",
      status: response.status,
      ok: response.ok,
      service: (data as { service?: unknown }).service ?? null,
    });
  }
  if (isTaskGraphRun && typeof window !== "undefined") {
    document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
      stage: "run_response_received",
      base,
      path,
      status: response.status,
      responseOk: response.ok,
      error: data.error ?? null,
      ok: data.ok ?? null,
      at: Date.now(),
    });
  }
  if (isTaskGraphRun) {
    onRequestStage?.("run_response_received");
  }
  if (isTaskGraphInstantiate) {
    if (typeof window !== "undefined") {
      document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
        stage: "instantiate_response_received",
        status: response.status,
        responseOk: response.ok,
        error: data.error ?? null,
        graphId: data.graph && typeof data.graph === "object" ? (data.graph as Record<string, unknown>).graph_id ?? null : null,
        at: Date.now(),
      });
    }
    console.warn("[task-graph] instantiate response", {
      status: response.status,
      ok: response.ok,
      error: data.error ?? null,
      graphId: data.graph && typeof data.graph === "object" ? (data.graph as Record<string, unknown>).graph_id ?? null : null,
    });
  }
  if (isMutation && shouldRefreshAdminSession(response, data, false)) {
    headers["X-Admin-Token"] = await fetchAdminSessionToken(base, { refresh: true });
    if (isTaskGraphInstantiate) {
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "instantiate_token_refreshed",
          base,
          tokenLength: headers["X-Admin-Token"]?.length ?? 0,
          at: Date.now(),
        });
      }
      console.warn("[task-graph] instantiate token refreshed", {
        base,
        tokenLength: headers["X-Admin-Token"]?.length ?? 0,
      });
    }
    const retryController = new AbortController();
    const retryTimer = requestAbortTimer(() => retryController.abort(), timeoutMs);
    try {
      response = await fetch(`${base}${path}`, {
        headers,
        cache: cacheMode,
        ...fetchInit,
        signal: retryController.signal,
      });
      data = await readJsonResponseWithTimeout(response, {
        path,
        controller: retryController,
        timeoutMs,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw timeoutError(path);
      }
      throw error;
    } finally {
      clearRequestAbortTimer(retryTimer);
    }
    if (isTaskGraphInstantiate) {
      if (typeof window !== "undefined") {
        document.documentElement.dataset[TASK_GRAPH_DEBUG_DATASET_KEY] = JSON.stringify({
          stage: "instantiate_retry_response_received",
          status: response.status,
          responseOk: response.ok,
          error: data.error ?? null,
          graphId: data.graph && typeof data.graph === "object" ? (data.graph as Record<string, unknown>).graph_id ?? null : null,
          at: Date.now(),
        });
      }
      console.warn("[task-graph] instantiate retried response", {
        status: response.status,
        ok: response.ok,
        error: data.error ?? null,
        graphId: data.graph && typeof data.graph === "object" ? (data.graph as Record<string, unknown>).graph_id ?? null : null,
      });
    }
  }
  if (!response.ok || (!acceptOkFalse && data.ok === false)) {
    if (isCurrentProjectRequest) {
      writeRequestDebugDataset("appRequestCurrentProjectDebug", {
        stage: "request_rejected",
        status: response.status,
        ok: response.ok,
        error: String(data.error ?? `Request failed: ${path}`),
      });
    }
    if (isHealthRequest) {
      writeRequestDebugDataset("appRequestHealthDebug", {
        stage: "request_rejected",
        status: response.status,
        ok: response.ok,
        error: String(data.error ?? `Request failed: ${path}`),
      });
    }
    throw new ApiRequestError(String(data.error ?? `Request failed: ${path}`), {
      status: response.status,
      data,
    });
  }
  if (isCurrentProjectRequest) {
    writeRequestDebugDataset("appRequestCurrentProjectDebug", {
      stage: "request_resolved",
      status: response.status,
      ok: response.ok,
      hasProject: Boolean((data as { project?: unknown }).project),
    });
  }
  if (isHealthRequest) {
    writeRequestDebugDataset("appRequestHealthDebug", {
      stage: "request_resolved",
      status: response.status,
      ok: response.ok,
      service: (data as { service?: unknown }).service ?? null,
    });
  }
  return data as T;
}

function jsonRequest<T>(path: string, payload: Record<string, unknown>, init?: RequestWithTimeout) {
  return request<T>(path, {
    ...init,
    method: "POST",
    body: JSON.stringify(payload),
  });
}

let browserWorkbenchFallbackSessions: BrowserWorkbenchSession[] = [];

function normalizeWorkbenchUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) throw new Error("URL is required.");
  const candidate = /^[a-z][a-z0-9+.-]*:/i.test(trimmed)
    ? trimmed
    : /^(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(\/|$)/i.test(trimmed)
      ? `http://${trimmed}`
      : `https://${trimmed}`;
  const url = new URL(candidate);
  if (!["http:", "https:"].includes(url.protocol)) {
    throw new Error("Only http and https URLs are supported.");
  }
  return url.toString();
}

function fallbackBrowserToken(value: string) {
  const token = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return token || "browser";
}

function fallbackBrowserId(payload: Pick<BrowserWorkbenchCreateRequest, "id" | "role">) {
  const token = fallbackBrowserToken(payload.id || payload.role || "browser");
  return token.startsWith("ab-browser-") ? token : `ab-browser-${token}`;
}

function fallbackBrowserRole(role?: string) {
  const value = role?.trim();
  return value ? value.slice(0, 40) : "Browser";
}

function browserRoleFromId(id: string) {
  return fallbackBrowserRole(id.replace(/^ab-browser-/, "").replace(/-/g, " "));
}

function browserFallbackDesktopUrl(rawUrl: string) {
  try {
    const parsed = new URL(rawUrl);
    const host = parsed.hostname.toLowerCase();
    if (host === "google.com" || host === "www.google.com") {
      parsed.hostname = "www.google.com";
      parsed.searchParams.delete("igu");
      if (parsed.pathname === "/webhp" && !parsed.searchParams.toString()) {
        parsed.pathname = "/";
      }
      return parsed.toString();
    }
    if (host === "m.youtube.com") {
      parsed.hostname = "www.youtube.com";
      return parsed.toString();
    }
    if (host === "m.facebook.com") {
      parsed.hostname = "www.facebook.com";
      return parsed.toString();
    }
    const wikipediaMatch = host.match(/^([a-z0-9-]+)\.m\.wikipedia\.org$/i);
    if (wikipediaMatch?.[1]) {
      parsed.hostname = `${wikipediaMatch[1]}.wikipedia.org`;
      return parsed.toString();
    }
    return parsed.toString();
  } catch {
    return rawUrl;
  }
}

function browserKnownMobileHost(rawUrl: string) {
  try {
    const parsed = new URL(rawUrl);
    const host = parsed.hostname.toLowerCase();
    if (host === "google.com" || host === "www.google.com") {
      parsed.hostname = "www.google.com";
      if (!parsed.pathname || parsed.pathname === "/") {
        parsed.pathname = "/webhp";
      }
      parsed.searchParams.set("igu", "1");
      return { url: parsed.toString(), strategy: "mobile_host_rewrite_viewport" as const };
    }
    if (host === "m.youtube.com" || host === "m.facebook.com" || /\.m\.wikipedia\.org$/i.test(host)) {
      return { url: parsed.toString(), strategy: "mobile_host_rewrite_viewport" as const };
    }
    if (host === "youtube.com" || host === "www.youtube.com") {
      parsed.hostname = "m.youtube.com";
      return { url: parsed.toString(), strategy: "mobile_host_rewrite_viewport" as const };
    }
    if (host === "youtu.be") {
      const videoId = parsed.pathname.replace(/^\/+|\/+$/g, "");
      if (videoId && !parsed.searchParams.has("v")) parsed.searchParams.set("v", videoId);
      parsed.hostname = "m.youtube.com";
      parsed.pathname = "/watch";
      return { url: parsed.toString(), strategy: "mobile_host_rewrite_viewport" as const };
    }
    if (host === "facebook.com" || host === "www.facebook.com") {
      parsed.hostname = "m.facebook.com";
      return { url: parsed.toString(), strategy: "mobile_host_rewrite_viewport" as const };
    }
    const wikipediaMatch = host.match(/^([a-z0-9-]+)\.wikipedia\.org$/i);
    if (wikipediaMatch?.[1] && wikipediaMatch[1] !== "www" && wikipediaMatch[1] !== "m") {
      parsed.hostname = `${wikipediaMatch[1]}.m.wikipedia.org`;
      return { url: parsed.toString(), strategy: "mobile_host_rewrite_viewport" as const };
    }
    return null;
  } catch {
    return null;
  }
}

function browserFallbackMobileResolution(rawUrl: string, layoutMode?: "desktop" | "mobile") {
  if (layoutMode !== "mobile") {
    return { url: browserFallbackDesktopUrl(rawUrl), strategy: "desktop_viewport" as const };
  }
  // Product strategy for tall/narrow browser surfaces:
  // 1. Prefer explicit mobile-entry URLs for the common sites we can verify.
  // 2. Otherwise keep the canonical URL and rely on mobile viewport + user-agent responsive rendering.
  // The rewrite set stays intentionally small so the browser never guesses unsupported mobile hosts.
  try {
    const knownMobileHost = browserKnownMobileHost(rawUrl);
    if (knownMobileHost) return knownMobileHost;
    const parsed = new URL(rawUrl);
    return { url: parsed.toString(), strategy: "mobile_user_agent_viewport" as const };
  } catch {
    return { url: rawUrl, strategy: layoutMode === "mobile" ? "mobile_user_agent_viewport" as const : "desktop_viewport" as const };
  }
}

function nativeBrowserSession(session: BrowserWorkbenchSession): BrowserWorkbenchSession {
  return {
    ...session,
    preview_mode: "native",
    supervision_session_id: session.supervision_session_id || session.id,
    supervision_status: session.supervision_status || "starting",
  };
}

function mergeBrowserSupervisor(nativeSession: BrowserWorkbenchSession, supervisor?: BrowserWorkbenchSession) {
  if (!supervisor) return nativeBrowserSession(nativeSession);
  return nativeBrowserSession({
    ...nativeSession,
    page_title: supervisor.page_title || nativeSession.page_title,
    viewport_width: supervisor.viewport_width ?? nativeSession.viewport_width,
    viewport_height: supervisor.viewport_height ?? nativeSession.viewport_height,
    can_go_back: supervisor.can_go_back ?? nativeSession.can_go_back,
    can_go_forward: supervisor.can_go_forward ?? nativeSession.can_go_forward,
    loading: supervisor.loading ?? nativeSession.loading,
    screenshot_path: supervisor.screenshot_path || nativeSession.screenshot_path,
    updated_at: supervisor.updated_at || nativeSession.updated_at,
    supervision_status: supervisor.status === "error" ? "error" : "ready",
    supervision_session_id: supervisor.id,
    supervision_error: supervisor.error ?? null,
  });
}

async function browserSupervisorCreate(payload: BrowserWorkbenchCreateRequest & { id: string }) {
  return jsonRequest<BrowserWorkbenchSession>("/api/browser/workbench/create", payload, { timeoutMs: 120000 });
}

async function browserSupervisorNavigate(payload: BrowserWorkbenchNavigateRequest & { role?: string }) {
  try {
    return await jsonRequest<BrowserWorkbenchSession>("/api/browser/workbench/navigate", payload, { timeoutMs: 120000 });
  } catch {
    return browserSupervisorCreate({
      id: payload.id,
      role: payload.role || browserRoleFromId(payload.id),
      url: payload.url,
    });
  }
}

async function mergeNativeBrowserSupervisors(nativeSessions: BrowserWorkbenchSession[]) {
  if (!nativeSessions.length) return nativeSessions;
  try {
    const supervisors = await request<BrowserWorkbenchSession[]>("/api/browser/workbench/sessions", { timeoutMs: 3500 });
    const supervisorsById = new Map(supervisors.map((session) => [session.id, session]));
    return nativeSessions.map((session) => mergeBrowserSupervisor(session, supervisorsById.get(session.id)));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return nativeSessions.map((session) =>
      nativeBrowserSession({
        ...session,
        supervision_status: session.supervision_status === "ready" ? "ready" : "unavailable",
        supervision_error: message,
      }),
    );
  }
}

async function browserCreate(payload: BrowserWorkbenchCreateRequest) {
  const normalized = { ...payload, url: normalizeWorkbenchUrl(payload.url) };
  if (isTauri()) {
    const session = nativeBrowserSession(await invoke<BrowserWorkbenchSession>("browser_create", { request: normalized }));
    void browserSupervisorCreate({ ...normalized, id: session.id, role: session.role }).catch(() => undefined);
    return session;
  }
  if (hasConfiguredBrowserSidecarBaseUrl()) {
    return jsonRequest<BrowserWorkbenchSession>("/api/browser/workbench/create", normalized, { timeoutMs: 120000 });
  }
  const fallbackMobile = browserFallbackMobileResolution(normalized.url, normalized.layout_mode);
  const role = fallbackBrowserRole(normalized.role);
  const session: BrowserWorkbenchSession = {
    id: fallbackBrowserId(normalized),
    role,
    title: `AstraBridge Browser - ${role}`,
    url: fallbackMobile.url,
    status: "web_fallback",
    error: null,
    layout_mode: normalized.layout_mode,
    mobile_strategy: fallbackMobile.strategy,
  };
  browserWorkbenchFallbackSessions = [
    ...browserWorkbenchFallbackSessions.filter((item) => item.id !== session.id),
    session,
  ];
  return session;
}

async function browserNavigate(payload: BrowserWorkbenchNavigateRequest) {
  const normalizedUrl = normalizeWorkbenchUrl(payload.url);
  if (isTauri()) {
    const session = nativeBrowserSession(await invoke<BrowserWorkbenchSession>("browser_navigate", { request: { ...payload, url: normalizedUrl } }));
    void browserSupervisorNavigate({ id: session.id, role: session.role, url: normalizedUrl }).catch(() => undefined);
    return session;
  }
  if (hasConfiguredBrowserSidecarBaseUrl()) {
    return jsonRequest<BrowserWorkbenchSession>("/api/browser/workbench/navigate", { ...payload, url: normalizedUrl }, { timeoutMs: 120000 });
  }
  const current = browserWorkbenchFallbackSessions.find((item) => item.id === payload.id);
  if (!current) throw new Error(`Browser window not found: ${payload.id}`);
  const fallbackMobile = browserFallbackMobileResolution(normalizedUrl, payload.layout_mode);
  const next = {
    ...current,
    url: fallbackMobile.url,
    status: "web_fallback",
    layout_mode: payload.layout_mode ?? current.layout_mode,
    layout_reason: payload.layout_reason ?? current.layout_reason,
    mobile_strategy: payload.layout_mode ? fallbackMobile.strategy : current.mobile_strategy,
  };
  browserWorkbenchFallbackSessions = browserWorkbenchFallbackSessions.map((item) => (item.id === payload.id ? next : item));
  return next;
}

async function browserList() {
  if (isTauri()) {
    const sessions = await invoke<BrowserWorkbenchSession[]>("browser_list");
    return mergeNativeBrowserSupervisors(sessions.map(nativeBrowserSession));
  }
  if (hasConfiguredBrowserSidecarBaseUrl()) {
    return request<BrowserWorkbenchSession[]>("/api/browser/workbench/sessions");
  }
  return browserWorkbenchFallbackSessions;
}

async function browserFocus(id: string) {
  if (isTauri()) {
    return nativeBrowserSession(await invoke<BrowserWorkbenchSession>("browser_focus", { id }));
  }
  if (hasConfiguredBrowserSidecarBaseUrl()) {
    return jsonRequest<BrowserWorkbenchSession>("/api/browser/workbench/focus", { id });
  }
  const current = browserWorkbenchFallbackSessions.find((item) => item.id === id);
  if (!current) throw new Error(`Browser window not found: ${id}`);
  return { ...current, status: "web_fallback" };
}

async function browserClose(id: string) {
  if (isTauri()) {
    const sessions = await invoke<BrowserWorkbenchSession[]>("browser_close", { id });
    void jsonRequest<BrowserWorkbenchSession[]>("/api/browser/workbench/close", { id }).catch(() => undefined);
    return mergeNativeBrowserSupervisors(sessions.map(nativeBrowserSession));
  }
  if (hasConfiguredBrowserSidecarBaseUrl()) {
    return jsonRequest<BrowserWorkbenchSession[]>("/api/browser/workbench/close", { id });
  }
  browserWorkbenchFallbackSessions = browserWorkbenchFallbackSessions.filter((item) => item.id !== id);
  return browserWorkbenchFallbackSessions;
}

async function browserTileTwoUp(ids: string[]) {
  if (isTauri()) {
    const sessions = await invoke<BrowserWorkbenchSession[]>("browser_tile_two_up", { ids });
    return mergeNativeBrowserSupervisors(sessions.map(nativeBrowserSession));
  }
  if (hasConfiguredBrowserSidecarBaseUrl()) {
    return jsonRequest<BrowserWorkbenchSession[]>("/api/browser/workbench/tile-two-up", { ids });
  }
  if (ids.length !== 2) throw new Error("Two browser window ids are required.");
  return browserWorkbenchFallbackSessions;
}

async function browserAction(payload: {
  id: string;
  action: "click" | "double_click" | "scroll" | "back" | "forward" | "reload" | "press" | "type_text";
  x?: number;
  y?: number;
  delta_x?: number;
  delta_y?: number;
  key?: string;
  text?: string;
}) {
  if (!hasConfiguredBrowserSidecarBaseUrl()) {
    throw new Error("Interactive browser actions need a connected AstraBridge sidecar.");
  }
  return jsonRequest<BrowserWorkbenchSession>("/api/browser/workbench/action", payload, { timeoutMs: 120000 });
}

async function openProjectWithCurrentProjectShortCircuit(projectFile: string) {
  const requestedProjectFile = normalizeProjectFilePath(projectFile);
  if (requestedProjectFile) {
    try {
      const current = await request<{ project: ProjectFile | null }>("/api/projects/current");
      if (normalizeProjectFilePath(current.project?.project_file) === requestedProjectFile && current.project) {
        return { project: current.project };
      }
    } catch {
      // Fall through to the normal admin-session-backed open path.
    }
  }
  return jsonRequest<{ project: ProjectFile }>("/api/projects/open", { project_file: projectFile }, { timeoutMs: 30000 });
}

async function browserLayout(payload: BrowserWorkbenchLayoutRequest) {
  if (hasConfiguredBrowserSidecarBaseUrl()) {
    return jsonRequest<BrowserWorkbenchSession>("/api/browser/workbench/layout", payload, { timeoutMs: 120000 });
  }
  const current = browserWorkbenchFallbackSessions.find((item) => item.id === payload.id);
  if (!current) throw new Error(`Browser window not found: ${payload.id}`);
  const viewport = payload.layout_mode === "mobile" ? { width: 390, height: 844 } : { width: 1365, height: 900 };
  const fallbackMobile = browserFallbackMobileResolution(current.url, payload.layout_mode);
  const next: BrowserWorkbenchSession = {
    ...current,
    url: fallbackMobile.url,
    layout_mode: payload.layout_mode,
    layout_reason: payload.layout_reason,
    viewport_width: viewport.width,
    viewport_height: viewport.height,
    mobile_strategy: fallbackMobile.strategy,
  };
  browserWorkbenchFallbackSessions = browserWorkbenchFallbackSessions.map((item) => (item.id === payload.id ? next : item));
  return next;
}

function browserWorkbenchFrameHref(sessionId: string, revision?: string | null) {
  const params = new URLSearchParams();
  params.set("id", sessionId);
  if (revision) params.set("rev", revision);
  const suffix = `/api/browser/workbench/frame?${params.toString()}`;
  if (typeof window === "undefined") return suffix;
  if (shouldUseBrowserSidecarProxy()) {
    return browserSidecarProxyUrl(suffix);
  }
  return `${browserSidecarBaseUrl()}${suffix}`;
}

type HealthResponse = {
  ok: boolean;
  service: string;
  sidecar?: RuntimeEnvironment["sidecar"];
  runtime: RuntimeEnvironment;
  router?: RuntimeEnvironment["router"];
};

function normalizeHealthResponse(payload: HealthResponse): HealthResponse {
  const runtimeRouter = payload.runtime?.router ?? payload.router ?? undefined;
  return {
    ...payload,
    runtime: {
      ...payload.runtime,
      router: runtimeRouter,
    },
  };
}

export const api = {
  ensureAdminSession: async () => {
    const base = await sidecarBaseUrl();
    await fetchAdminSessionToken(base, { purpose: "prewarm" });
  },
  health: async () => normalizeHealthResponse(await request<HealthResponse>("/health")),
  currentProject: () => request<{ project: ProjectFile | null }>("/api/projects/current"),
  recentProjects: () => request<{ projects: ProjectSummary[] }>("/api/projects/recent"),
  projectSidebar: async () => normalizeSidebarProjectsResponse(await request<SidebarProjectsResponse>("/api/projects/sidebar")),
  createProject: (payload: {
    name: string;
    project_file: string;
    workspace_root?: string;
    entry_mode: "existing" | "new";
  }) => jsonRequest<{ project: ProjectFile }>("/api/projects/create", payload),
  openProject: (projectFile: string) => openProjectWithCurrentProjectShortCircuit(projectFile),
  closeProject: () => jsonRequest<{ closed: boolean }>("/api/projects/close", {}),
  suggestProjectTitle: (force = false) => jsonRequest<TitleSuggestionResponse>("/api/project/title/suggest", { force }),
  updateProjectPreferences: (payload: {
    locale?: ProjectFile["ui_preferences"]["locale"];
    appearance?: AppearancePreset;
    cursor_enhancement?: CursorEnhancementPreference;
    execution_host?: ExecutionHost;
    wsl_distro?: string;
    left_sidebar_open?: boolean;
    left_sidebar_width?: number;
    right_sidebar_width?: number;
    right_sidebar_open?: boolean;
  }) => jsonRequest<{ project: ProjectFile }>("/api/projects/preferences", { ui_preferences: payload }),
  updateProjectPluginSkillPresets: (payload: {
    operation: "add_plugin" | "remove_plugin" | "add_skill" | "remove_skill" | "reset";
    preset_id?: string;
    plugin_ref?: {
      plugin_id: string;
      source_catalog_id?: string | null;
      display_name?: string | null;
    };
    skill_ref?: {
      record_id: string;
      skill_name: string;
      owner_plugin_id?: string | null;
      source_catalog_id?: string | null;
      display_name?: string | null;
    };
  }) => jsonRequest<{ project: ProjectFile }>("/api/projects/plugin-skill-presets", payload),
  projectSaves: () => request<ProjectSavesResponse>("/api/project/saves"),
  projectReviewStatus: () => request<ProjectReviewStatus>("/api/project/review/status"),
  projectReviewDiff: (path?: string) => {
    const suffix = path ? `?path=${encodeURIComponent(path)}` : "";
    return request<ProjectReviewDiff>(`/api/project/review/diff${suffix}`);
  },
  projectFilesTree: (query?: string) => {
    const params = new URLSearchParams();
    if (query?.trim()) params.set("query", query.trim());
    params.set("limit", "500");
    return request<ProjectFilesTree>(`/api/project/files/tree?${params.toString()}`);
  },
  projectFileRead: (path: string) => request<ProjectFilePreview>(`/api/project/files/read?path=${encodeURIComponent(path)}`),
  projectFileMediaHref,
  browserWorkbenchFrameHref,
  projectFileMediaUrl: async (path: string) => `${await sidecarBaseUrl()}/api/project/files/media?path=${encodeURIComponent(path)}`,
  stageAttachments: (payload: { files: AttachmentStageFile[]; directory_name?: string | null }) =>
    jsonRequest<AttachmentStageResponse>("/api/project/attachments/stage", payload, { timeoutMs: 30000 }),
  projectTerminalHistory: () => request<ProjectTerminalHistory>("/api/project/terminal/history?limit=30"),
  projectTasks: async () => normalizeProjectTasksResponse(await request<ProjectTasksResponse>("/api/project/tasks")),
  taskGraphTemplates: () => request<{ schema_version: string; templates: TaskGraphTemplateSummary[] }>("/api/task-graphs/templates"),
  taskGraph: (graphId?: string | null) => {
    const params = new URLSearchParams();
    if (graphId) params.set("graph_id", graphId);
    const suffix = params.toString();
    return request<{ graph: TaskGraphDefinition | null; task: ProjectTask | null }>(`/api/task-graphs/graph${suffix ? `?${suffix}` : ""}`);
  },
  currentTaskGraph: (graphId?: string | null) => {
    const params = new URLSearchParams();
    if (graphId) params.set("graph_id", graphId);
    const suffix = params.toString();
    return request<{ graph: TaskGraphDefinition | null; task: ProjectTask | null }>(`/api/task-graphs/current${suffix ? `?${suffix}` : ""}`);
  },
  instantiateTaskGraph: (payload: { template_id: string; title?: string | null }) =>
    jsonRequest<{ graph: TaskGraphDefinition; task: ProjectTask | null }>("/api/task-graphs/instantiate", payload),
  updateTaskGraphNode: (payload: {
    graph_id: string;
    node_id: string;
    position?: { x: number; y: number } | null;
    configuration?: Record<string, unknown> | null;
    create?: {
      kind: string;
      label?: string | null;
      position?: { x: number; y: number } | null;
    } | null;
  }) => jsonRequest<{ graph: TaskGraphDefinition; node: TaskGraphNode; task: ProjectTask | null }>("/api/task-graphs/node/update", payload),
  updateTaskGraphEdge: (payload: {
    graph_id: string;
    edge_id?: string | null;
    from_node_id?: string | null;
    to_node_id?: string | null;
    edge_type?: string | null;
    handoff_contract?: Record<string, unknown> | null;
    context_policy?: Record<string, unknown> | null;
    status?: string | null;
  }) =>
    jsonRequest<{ graph: TaskGraphDefinition; edge: TaskGraphDefinition["edges"][number]; task: ProjectTask | null }>(
      "/api/task-graphs/edge/update",
      payload,
    ),
  dryRunTaskGraph: (payload: {
    graph_id: string;
    validation_mode?: "live";
    budget?: { limits: { total_tokens: number } };
  }) =>
    jsonRequest<{ schema_version: string; dry_run: TaskGraphDryRunResult; graph: TaskGraphDefinition; task: ProjectTask | null }>(
      "/api/task-graphs/dry-run",
      payload,
    ),
  runTaskGraph: (
    payload: {
      graph_id: string;
      budget: { limits: { total_tokens: number } };
    },
    init?: RequestWithTimeout,
  ) =>
    jsonRequest<{
      schema_version: string;
      live_run: {
        run_id: string;
        run_status: string;
        run_ref: TaskGraphRunRef;
        artifact_paths?: Record<string, string>;
      };
      graph: TaskGraphDefinition;
      task: ProjectTask | null;
    }>("/api/task-graphs/run", payload, { timeoutMs: 300000, ...(init ?? {}) }),
  importTaskGraphFile: (payload: { graph_path?: string | null; graph_text?: string | null }) =>
    jsonRequest<AgentOrchestrationGraphImportResponse>("/api/task-graphs/import", payload),
  exportTaskGraphFile: (payload: { graph_id: string; export_path?: string | null }) =>
    jsonRequest<AgentOrchestrationGraphExportResponse>("/api/task-graphs/export", payload),
  createTaskGraphSnapshot: (payload: {
    graph_id: string;
    label?: string | null;
    reason?: string | null;
    source_action?: string | null;
  }) => jsonRequest<TaskGraphSnapshotResponse>("/api/task-graphs/snapshot", payload),
  diffTaskGraphSnapshot: (payload: {
    snapshot_id: string;
    compare_to_snapshot_id?: string | null;
  }) => jsonRequest<TaskGraphSnapshotDiffResponse>("/api/task-graphs/snapshot/diff", payload),
  rollbackTaskGraphToSnapshot: (payload: { snapshot_id: string; label?: string | null }) =>
    jsonRequest<TaskGraphRollbackResponse>("/api/task-graphs/rollback", payload),
  saveTaskGraph: (payload: { graph: TaskGraphDefinition }) =>
    jsonRequest<{ schema_version: string; graph: TaskGraphDefinition; task: ProjectTask | null }>("/api/task-graphs/save", payload),
  fixtureRunTaskGraph: (payload: {
    graph_id: string;
    branch_behaviors?: Record<string, string> | null;
    execution_mode?: "default" | "cancellable" | null;
  }) =>
    jsonRequest<{
      schema_version: string;
      fixture_run: {
        run_ref?: TaskGraphRunRef;
      } & Record<string, unknown>;
      graph: TaskGraphDefinition;
      task: ProjectTask | null;
    }>("/api/task-graphs/fixture-run", payload),
  cancelTaskGraphRun: (payload: { run_id: string; notes?: string | null }) =>
    jsonRequest<{
      cancellation: Record<string, unknown>;
      run_ref: TaskGraphRunRef;
      graph: TaskGraphDefinition;
      task: ProjectTask | null;
    }>("/api/task-graphs/run/cancel", payload),
  recoverTaskGraphRun: (payload: {
    run_id: string;
    strategy:
      | "resume_run"
      | "retry_failed_nodes"
      | "rerun_selected_nodes"
      | "partial_execution";
    selected_node_ids?: string[] | null;
    node_behaviors?: Record<string, string> | null;
  }) =>
    jsonRequest<{
      recovery: TaskGraphRecoverySummary & {
        artifact_paths?: Record<string, string>;
        requested_at?: string;
      };
      fixture_run: {
        run_ref: TaskGraphRunRef;
      } & Record<string, unknown>;
      graph: TaskGraphDefinition;
      task: ProjectTask | null;
    }>("/api/task-graphs/run/recover", payload),
  resolveTaskGraphApproval: (payload: { run_id: string; decision: "approve" | "reject"; notes?: string | null }) =>
    jsonRequest<{
      approval: Record<string, unknown>;
      run_ref: TaskGraphRunRef;
      graph: TaskGraphDefinition;
      task: ProjectTask | null;
    }>("/api/task-graphs/approval/resolve", payload),
  recordTaskGraphWorkerOutput: (payload: {
    graph_id: string;
    run_id: string;
    node_id: string;
    worker_thread_id: string;
    human_summary?: string | null;
    machine_result?: Record<string, unknown> | null;
    confidence?: unknown;
    next_action_hints?: string[] | null;
    status?: string | null;
  }) =>
    jsonRequest<{
      worker_binding: Record<string, unknown>;
      run_ref: Record<string, unknown>;
      task: ProjectTask | null;
      artifact_bundle: Record<string, unknown>;
    }>("/api/task-graphs/worker/output", payload),
  taskConversation: (taskId?: string | null) => {
    const params = new URLSearchParams();
    if (taskId) params.set("task_id", taskId);
    const suffix = params.toString();
    return request<TaskConversationResponse>(`/api/project/task-conversation${suffix ? `?${suffix}` : ""}`).then(normalizeTaskConversationResponse);
  },
  createTask: (title?: string) =>
    jsonRequest<{ task: ProjectTasksResponse["tasks"][number]; project: ProjectFile }>("/api/project/tasks/create", { title }).then((response) => ({
      ...response,
      task: normalizeProjectTask(response.task),
    })),
  switchTask: (taskId: string) =>
    jsonRequest<{ task: ProjectTasksResponse["tasks"][number]; project: ProjectFile }>("/api/project/tasks/switch", { task_id: taskId }).then((response) => ({
      ...response,
      task: normalizeProjectTask(response.task),
    })),
  suggestTaskTitle: (force = false) => jsonRequest<TitleSuggestionResponse>("/api/project/tasks/title/suggest", { force }),
  createProjectSave: (payload: { thread_id?: string | null; description?: string; provider?: string; model?: string }) =>
    jsonRequest<ProjectSaveCreateResponse>("/api/project/saves/create", payload),
  loadProjectSave: (payload: { save_id: string; preview?: boolean; confirm_dirty?: boolean }) =>
    jsonRequest<ProjectSaveLoadResponse>("/api/project/saves/load", payload),
  deleteProjectSave: (saveId: string) =>
    request<{ deleted: string }>(`/api/project/saves/delete?save_id=${encodeURIComponent(saveId)}`, { method: "DELETE" }),
  projectContext: (threadId?: string) => {
    const suffix = threadId ? `?thread_id=${encodeURIComponent(threadId)}` : "";
    return request<ProjectContextPackResponse>(`/api/project/context${suffix}`);
  },
  rebuildProjectContext: (threadId?: string) => jsonRequest<ProjectContextPackResponse>("/api/project/context/rebuild", { thread_id: threadId }),
  agenticUpdateStart: (payload: AgenticUpdateStartPayload) =>
    jsonRequest<AgenticUpdateJobStatus>("/api/agentic-updates/start", payload as unknown as Record<string, unknown>, { timeoutMs: 120000 }),
  agenticUpdateRuns: (limit = 25) => request<AgenticUpdateRunList>(`/api/agentic-updates/runs?limit=${encodeURIComponent(String(limit))}`),
  agenticUpdateStatus: (jobId?: string | null) =>
    request<AgenticUpdateJobStatus>(`/api/agentic-updates/status${jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""}`),
  agenticUpdateResult: (jobId?: string | null) =>
    request<AgenticUpdateProposalResult>(`/api/agentic-updates/result${jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""}`),
  profiles: () => request<{ profiles: Profile[] }>("/api/profiles"),
  routerConfig: () => request<RouterConfigResponse>("/api/router/config"),
  automations: () => request<AutomationListResponse>("/api/automations"),
  createAutomation: (payload: Record<string, unknown>) => jsonRequest<{ automation: AutomationSpec }>("/api/automations/create", payload),
  updateAutomation: (automationId: string, patch: Record<string, unknown>) =>
    jsonRequest<{ automation: AutomationSpec }>("/api/automations/update", { automation_id: automationId, ...patch }),
  deleteAutomation: (automationId: string, reason?: string) =>
    jsonRequest<{ automation: AutomationSpec }>("/api/automations/delete", { automation_id: automationId, reason }),
  pauseAutomation: (automationId: string) => jsonRequest<{ automation: AutomationSpec }>("/api/automations/pause", { automation_id: automationId }),
  resumeAutomation: (automationId: string) => jsonRequest<{ automation: AutomationSpec }>("/api/automations/resume", { automation_id: automationId }),
  runAutomationNow: (automationId: string) =>
    jsonRequest<{ run: AutomationRun; inbox_item?: AutomationInboxItem | null; scheduler: AutomationSchedulerStatus }>(
      "/api/automations/run-now",
      { automation_id: automationId },
      { timeoutMs: 30000 },
    ),
  automationRuns: (automationId?: string | null) => {
    const params = new URLSearchParams();
    if (automationId) params.set("automation_id", automationId);
    const suffix = params.toString();
    return request<AutomationRunsResponse>(`/api/automations/runs${suffix ? `?${suffix}` : ""}`);
  },
  automationRun: (runId: string) => request<{ run: AutomationRun }>(`/api/automations/run?run_id=${encodeURIComponent(runId)}`),
  cancelAutomationRun: (runId: string) => jsonRequest<{ run: AutomationRun }>("/api/automations/runs/cancel", { run_id: runId }),
  automationInbox: (automationId?: string | null, includeArchived = true) => {
    const params = new URLSearchParams();
    if (automationId) params.set("automation_id", automationId);
    params.set("include_archived", includeArchived ? "true" : "false");
    return request<AutomationInboxResponse>(`/api/automations/inbox?${params.toString()}`);
  },
  updateAutomationInboxItem: (itemId: string, patch: Record<string, unknown>) =>
    jsonRequest<{ item: AutomationInboxItem }>("/api/automations/inbox/update", { item_id: itemId, ...patch }),
  promoteAutomationInboxItem: (itemId: string, promotionRef: string) =>
    jsonRequest<{ item: AutomationInboxItem }>("/api/automations/inbox/promote", { item_id: itemId, promotion_ref: promotionRef }),
  automationSchedulerStatus: () => request<{ scheduler: AutomationSchedulerStatus }>("/api/automations/scheduler/status"),
  capabilityRoutes: () => request<{ routes: CapabilityRouteEntry[]; updated_at: string }>("/api/runtime/capability-routes"),
  capabilityManagement: () => request<CapabilityManagementResponse>("/api/runtime/capability-management"),
  capabilityArtifacts: (limit = 20) => request<CapabilityArtifactsResponse>(`/api/runtime/capability-artifacts?limit=${encodeURIComponent(String(limit))}`),
  capabilitySmoke: (payload: { capability_id: string; mode?: "dry_run" | "provider"; allow_provider?: boolean }) =>
    jsonRequest<CapabilitySmokeResponse>("/api/runtime/capability-smoke", payload),
  invokeCapability: (payload: { capability_id: string; payload: Record<string, unknown> }) =>
    jsonRequest<CapabilityInvokeResponse>("/api/runtime/capability-invoke", payload, { timeoutMs: 180000 }),
  saveCapabilityRoute: (payload: CapabilityRouteRecord) => jsonRequest<{ route: CapabilityRouteEntry }>("/api/runtime/capability-routes/save", payload),
  webSearchBatch: (payload: WebSearchBatchRequest) =>
    requestWebSearchBatch((path, body) => jsonRequest<WebSearchBatchResponse>(path, body), payload),
  webResearchBrief: (payload: WebResearchBriefRequest) =>
    requestWebResearchBrief((path, body) => jsonRequest<WebResearchBriefResponse>(path, body, { timeoutMs: 120000 }), payload),
  webFetch: (payload: WebFetchRequest) =>
    requestWebFetch((path, body) => jsonRequest<WebFetchResponse>(path, body), payload),
  llmManagerSession: () => request<LlmManagerSession>("/api/llm-manager/session"),
  llmManagerLogin: (payload: { username?: string; password?: string; mode?: "managed_user" | "anonymous"; use_desktop_key_file?: boolean }) =>
    jsonRequest<{ session: LlmManagerSession }>("/api/llm-manager/login", payload),
  llmManagerLogout: () => jsonRequest<{ session: LlmManagerSession }>("/api/llm-manager/logout", {}),
  llmManagerCreateUser: (payload: { username: string; password?: string; use_desktop_key_file?: boolean }) =>
    jsonRequest<{ session: LlmManagerSession; user: { username: string; created: boolean } }>("/api/llm-manager/users/create", payload),
  llmManagerSwitchUser: (payload: { username: string; password: string }) =>
    jsonRequest<{ session: LlmManagerSession }>("/api/llm-manager/users/switch", payload),
  llmManagerChangePassword: (payload: { username?: string; old_password: string; new_password: string }) =>
    jsonRequest<{ changed: boolean; session: LlmManagerSession }>("/api/llm-manager/users/change-password", payload),
  llmManagerSaveUserProfile: (payload: { username?: string; display_name?: string; avatar_path?: string }) =>
    jsonRequest<{ profile: NonNullable<LlmManagerSession["profile"]>; session: LlmManagerSession }>("/api/llm-manager/users/profile", payload),
  llmManagerKeys: () => request<LlmManagerKeysResponse>("/api/llm-manager/keys"),
  llmManagerSaveKey: (payload: { key_id?: string; provider_id: string; label: string; env_key?: string; secret: string; enabled?: boolean; make_default?: boolean }) =>
    jsonRequest<{ key: LlmManagerKeysResponse["keys"][number]; keys: LlmManagerKeysResponse["keys"] }>("/api/llm-manager/keys/save", payload),
  llmManagerDeleteKey: (keyId: string) => jsonRequest<LlmManagerKeysResponse & { deleted: string }>("/api/llm-manager/keys/delete", { key_id: keyId }),
  llmManagerTestKey: (payload: { provider_id?: string; key_id?: string; model_id?: string; stream?: boolean }) =>
    jsonRequest<{ ok: boolean; result: RouterTestResult; key: LlmManagerKeysResponse["keys"][number]; keys: LlmManagerKeysResponse["keys"] }>("/api/llm-manager/keys/test", payload),
  llmManagerEffectiveCatalog: () => request<LlmEffectiveCatalogResponse>("/api/llm-manager/catalog/effective"),
  llmManagerRunHealth: (payload: { model_ids?: string[]; model_id?: string; efforts?: string[]; temperatures?: number[]; stream?: boolean; web_smoke?: boolean }) =>
    jsonRequest<LlmHealthResultsResponse>("/api/llm-manager/health/run", payload),
  llmManagerHealthResults: () => request<LlmHealthResultsResponse>("/api/llm-manager/health/results"),
  saveProfile: (profile: Profile) => jsonRequest<{ profile: Profile }>("/api/profiles", profile),
  deleteProfile: (profileId: string) => jsonRequest<{ deleted: string }>("/api/profiles/delete", { profile_id: profileId }),
  loadSecret: (profileId: string, payload: { session_key?: string; key_file_path?: string; persist_to_keychain?: boolean }) =>
    jsonRequest<{ runtime_config: RuntimeEnvironment["runtime_config"] }>("/api/profiles/load-secret", {
      profile_id: profileId,
      ...payload,
    }),
  saveProvider: (payload: RouterProvider) => jsonRequest<{ provider: RouterProvider }>("/api/router/providers/save", payload),
  deleteProvider: (providerId: string) => jsonRequest<{ deleted: string }>("/api/router/providers/delete", { provider_id: providerId }),
  saveModelCatalogEntry: (payload: RouterModelEntry) => jsonRequest<{ model: RouterModelEntry }>("/api/router/models/save", payload),
  deleteModelCatalogEntry: (modelId: string) => jsonRequest<{ deleted: string }>("/api/router/models/delete", { model_id: modelId }),
  saveReasoningConfig: (payload: ReasoningConfig) => jsonRequest<{ reasoning: ReasoningConfig }>("/api/router/reasoning/save", payload),
  previewPayload: (payload: Record<string, unknown>) => jsonRequest<{ provider: string; model: string; adapter: string; warnings?: string[]; upstream_payload: Record<string, unknown> }>("/api/router/payload-preview", payload),
  testProvider: (payload: { provider_id: string; model_id?: string; stream?: boolean }) => jsonRequest<RouterTestResult>("/api/router/test-provider", payload),
  testProviderVision: (payload: { provider_id: string; model_id?: string; stream?: boolean }) => jsonRequest<RouterTestResult>("/api/router/test-provider-vision", payload),
  verifyAppServerImageRoute: (payload: { provider_id: string; model_id?: string; profile_id?: string }) =>
    jsonRequest<RouterTestResult>("/api/runtime/verify-app-server-image-route", payload, { timeoutMs: 120000 }),
  exportRouterConfig: () => jsonRequest<RouterConfigResponse>("/api/router/export-config", {}),
  importRouterConfig: (payload: RouterConfigResponse) => jsonRequest<RouterConfigResponse>("/api/router/import-config", payload),
  rotateRouterToken: () => jsonRequest<RuntimeEnvironment["router"]>("/api/router/token/rotate", {}),
  metadataSources: () => request<MetadataSourcesResponse>("/api/router/metadata/sources"),
  saveMetadataSources: (payload: MetadataSourcesResponse) => jsonRequest<MetadataSourcesResponse>("/api/router/metadata/sources/save", payload),
  refreshMetadata: (apply: boolean) => jsonRequest<MetadataRefreshResponse>("/api/router/metadata/refresh", { apply }),
  startMetadataRefresh: (apply: boolean) => jsonRequest<MetadataRefreshJobStartResponse>("/api/router/metadata/refresh/start", { apply }),
  metadataRefreshStatus: (jobId?: string | null) => request<MetadataRefreshJobStatusResponse>(`/api/router/metadata/refresh/status${jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""}`),
  metadataRefreshResult: (jobId?: string | null) => request<MetadataRefreshResponse>(`/api/router/metadata/refresh/result${jobId ? `?job_id=${encodeURIComponent(jobId)}` : ""}`),
  importMetadataSeed: (apply = true) => jsonRequest<{ applied: boolean; providers: RouterProvider[]; models: RouterModelEntry[]; model_count: number }>("/api/router/metadata/import-seed", { apply }),
  effectiveCatalog: (modelId?: string) => {
    const suffix = modelId ? `?model_id=${encodeURIComponent(modelId)}` : "";
    return request<EffectiveCatalogResponse>(`/api/router/models/effective-catalog${suffix}`);
  },
  testMatrix: (payload: { model_ids?: string[]; efforts?: string[]; temperatures?: number[]; max_cases?: number }) =>
    jsonRequest<TestMatrixResponse>("/api/router/models/test-matrix", payload),
  metadataReport: () => request<MetadataReportResponse>("/api/router/metadata/report"),
  mcpConfig: () => request<McpConfigResponse>("/api/router/mcp/config"),
  saveMcpServer: (payload: McpServerConfig) => jsonRequest<{ server: McpServerConfig; config: McpConfigResponse }>("/api/router/mcp/config/save", payload),
  deleteMcpServer: (name: string) => jsonRequest<{ deleted: string; config: McpConfigResponse }>("/api/router/mcp/config/delete", { name }),
  applyContext7Preset: () => jsonRequest<{ server: McpServerConfig; config: McpConfigResponse }>("/api/router/mcp/preset/context7", {}),
  applyYunwuImagePreset: () => jsonRequest<{ server: McpServerConfig; config: McpConfigResponse }>("/api/router/mcp/preset/yunwu-image", {}),
  applyAstraBridgeCapabilitiesPreset: () => jsonRequest<{ server: McpServerConfig; config: McpConfigResponse }>("/api/router/mcp/preset/astrabridge-capabilities", {}),
  testYunwuImage: (payload?: { session_key?: string; key_file_path?: string }) =>
    jsonRequest<YunwuImageSmokeResponse>("/api/router/image/yunwu/test", payload ?? {}),
  generateYunwuImage: (payload: { prompt: string; model?: string; size?: string; n?: number; purpose?: string; session_key?: string; key_file_path?: string }) =>
    jsonRequest<Record<string, unknown>>("/api/router/image/yunwu/generate", payload),
  dogfoodRun: () => request<DogfoodRunResponse>("/api/dogfood/run"),
  saveDogfoodRun: (payload: Partial<DogfoodRun>) => jsonRequest<DogfoodRunResponse>("/api/dogfood/run/save", payload as Record<string, unknown>),
  browserCreate,
  browserNavigate,
  browserList,
  browserFocus,
  browserClose,
  browserTileTwoUp,
  browserAction,
  browserLayout,
  addDogfoodCapture: (payload: { path: string; label?: string; provider?: string }) =>
    jsonRequest<DogfoodRunResponse & { capture: Record<string, unknown> }>("/api/dogfood/captures/add", payload),
  dogfoodBrowserSmoke: (payload: { url: string; label?: string; preset?: string; screenshot_path?: string; console_errors?: string[]; auto_milestone?: boolean; include_run?: boolean; actions?: Array<Record<string, unknown>> }) =>
    jsonRequest<Partial<DogfoodRunResponse> & { browser_smoke: Record<string, unknown>; run_summary?: Record<string, unknown> }>("/api/dogfood/browser-smoke", payload),
  dogfoodMilestone: (payload: { label: string; provider?: string; model?: string; goal?: string; plan_step?: string; status?: string; captures?: string[]; capture_paths?: string[]; validation?: string[] | Record<string, unknown>; validation_result?: string | Record<string, unknown>; failure_reason?: string; next_step?: string; next_action?: string; include_run?: boolean }) =>
    jsonRequest<Partial<DogfoodRunResponse> & { milestone: Record<string, unknown>; run_summary?: Record<string, unknown> }>("/api/dogfood/milestone", payload),
  dogfoodAssets: () => request<AssetRegistryResponse>("/api/dogfood/assets"),
  rebuildDogfoodAssets: () => jsonRequest<AssetRegistryResponse>("/api/dogfood/assets/rebuild", {}),
  prepareReleaseWorkflowDemo: () => jsonRequest<ReleaseWorkflowDemoResponse>("/api/project/demo/release-workflow/prepare", {}),
  prepareNativeKernelWorkflowDemo: (payload?: {
    profile_id?: string;
    provider_id?: string;
    model?: string;
    effort?: string;
    reasoning_effort?: string;
    permission_mode?: PermissionMode;
    collaboration_mode?: CollaborationMode;
  }) => jsonRequest<NativeKernelDemoResponse>("/api/project/demo/native-kernel/prepare", payload ?? {}),
  isolationAudit: () => request<IsolationAuditResponse>("/api/audit/isolation", { acceptOkFalse: true }),
  markDogfoodAsset: (payload: { asset_id: string; status?: string; quality_status?: string; integration_status?: string; role?: string; purpose?: string; notes?: string }) =>
    jsonRequest<AssetRegistryResponse>("/api/dogfood/assets/mark", payload),
  promoteDogfoodAsset: (payload: { asset_id: string; target_name?: string; manifest_section?: "sprites" | "tiles" | "hud"; entity?: string; state?: string; tile_key?: string; role?: string }) =>
    jsonRequest<AssetRegistryResponse & { asset: Record<string, unknown>; target_path: string; game_ref: string; game_manifest_path: string }>("/api/dogfood/assets/promote", payload),
  reloadMcp: (profileId?: string) => jsonRequest<{ reloaded: boolean; result: unknown }>("/api/runtime/mcp/reload", { profile_id: profileId }),
  mcpStatus: (payload?: { profile_id?: string; thread_id?: string; detail?: "full" | "toolsAndAuthOnly" }) => {
    const params = new URLSearchParams();
    if (payload?.profile_id) params.set("profile_id", payload.profile_id);
    if (payload?.thread_id) params.set("thread_id", payload.thread_id);
    if (payload?.detail) params.set("detail", payload.detail);
    return request<McpStatusResponse>(`/api/runtime/mcp/status?${params.toString()}`, { timeoutMs: 45000 });
  },
  callMcpTool: (payload: { profile_id?: string; thread_id: string; server: string; tool: string; arguments?: Record<string, unknown> }) =>
    jsonRequest<{ result: Record<string, unknown> }>("/api/runtime/mcp/tool-call", payload),
  runtimeEnvironment: () => request<RuntimeEnvironment>("/api/runtime/environment"),
  runtimeKernelProbe: (profileId?: string) =>
    request<CodexKernelProbeSnapshot>(
      `/api/runtime/kernel-probe${profileId ? `?profile_id=${encodeURIComponent(profileId)}` : ""}`,
      { timeoutMs: 90000 },
    ),
  runtimePluginSkillRegistry: (profileId?: string) =>
      request<CodexPluginSkillRegistrySnapshot>(
        `/api/runtime/plugin-skill-registry${profileId ? `?profile_id=${encodeURIComponent(profileId)}` : ""}`,
        { timeoutMs: 90000 },
      ),
  runtimeSkillEnablementUpdate: (payload: {
    profile_id?: string;
    record_id: string;
    scope: "global" | "project";
    enablement_status: "enabled" | "disabled" | "inherited";
  }) => jsonRequest<CodexPluginSkillRegistrySnapshot>("/api/runtime/skill-enablement", payload),
  runtimePluginInstallPlan: (payload: { profile_id?: string; plugin_id: string; source_catalog_id?: string }) =>
    jsonRequest<CodexPluginInstallPlan>("/api/runtime/plugin-install-plan", payload),
  runtimePluginInstallApply: (payload: { profile_id?: string; plugin_id: string; source_catalog_id?: string }) =>
    jsonRequest<CodexPluginInstallExecution>("/api/runtime/plugin-install-apply", payload),
  runtimeSkillPluginCreatorFixtureScenario: (payload?: { profile_id?: string; skill_name?: string }) =>
    jsonRequest<SkillPluginCreatorScenarioExecution>("/api/runtime/skill-scenario/plugin-creator-fixture", payload ?? {}),
  runtimeComputerUseBrowserScenario: (payload?: {
    profile_id?: string;
    run_model?: boolean;
    include_yunwu?: boolean;
    allow_fallback_sites?: boolean;
    max_wait_sec?: number;
  }) =>
    jsonRequest<ComputerUseBrowserScenarioReport>("/api/runtime/computer-use/browser-scenario", payload ?? {}),
  wslDependencies: (distro?: string) => {
    const suffix = distro ? `?distro=${encodeURIComponent(distro)}` : "";
    return request<WslDependencyStatus>(`/api/runtime/dependencies/wsl${suffix}`, { timeoutMs: 45000 });
  },
  writeWslBootstrapScripts: (distro?: string) => jsonRequest<WslBootstrapScriptsResponse>("/api/runtime/dependencies/wsl/scripts", { distro }),
  launchWslBootstrapInstaller: (distro?: string) => jsonRequest<WslBootstrapScriptsResponse>("/api/runtime/dependencies/wsl/install", { distro }),
  runtimeSupervisor: (payload?: { thread_id?: string; profile_id?: string }) => {
    const params = new URLSearchParams();
    if (payload?.thread_id) params.set("thread_id", payload.thread_id);
    if (payload?.profile_id) params.set("profile_id", payload.profile_id);
    return request<RuntimeSupervisorState>(`/api/runtime/supervisor/status?${params.toString()}`);
  },
  runtimeSupervisorDecision: (payload: { action: "continue" | "compact" | "fork" | "interrupt"; thread_id: string; turn_id?: string; profile_id?: string; model?: string; effort?: string; permission_mode?: PermissionMode; name?: string }) =>
    jsonRequest<Record<string, unknown>>("/api/runtime/supervisor/decision", payload),
  routerStatus: () => request<RuntimeEnvironment["router"]>("/api/router/status"),
  restartRuntime: () => jsonRequest<{ runtime: RuntimeEnvironment }>("/api/runtime/restart", {}),
  runtimeEvents: (after: number) =>
    request<{ cursor: number; events: RuntimeEvent[] }>(`/api/runtime/events?after=${after}`, { timeoutMs: 65000 }),
  runtimeEventsStreamUrl: async (after: number) => {
    const base = await sidecarBaseUrl();
    const params = new URLSearchParams({ after: String(Math.max(0, after)), seconds: "60" });
    if (shouldUseBrowserSidecarProxy()) {
      return browserSidecarProxyUrl(`/api/events/stream?${params.toString()}`);
    }
    return `${base}/api/events/stream?${params.toString()}`;
  },
  pendingModals: () => request<{ modals: RuntimeModal[] }>("/api/runtime/modals"),
  resolveModal: (modalId: string, payload: Record<string, unknown>) =>
    jsonRequest<{ modal: RuntimeModal }>("/api/runtime/modals/resolve", { modal_id: modalId, ...payload }),
  createFakeModal: (kind: string, params?: Record<string, unknown>) =>
    jsonRequest<{ modal: RuntimeModal }>("/api/runtime/modals/fake", { kind, params: params ?? {} }),
  models: (profileId: string) => request<{ models: Array<{ id: string; name?: string }>; next_cursor: string | null }>(`/api/runtime/models?profile_id=${encodeURIComponent(profileId)}`),
  threads: (profileId?: string, archived = false) => {
    const params = new URLSearchParams();
    if (profileId) params.set("profile_id", profileId);
    if (archived) params.set("archived", "true");
    return request<ThreadListResponse>(`/api/runtime/threads?${params.toString()}`).then(normalizeThreadListResponse);
  },
  readThread: (threadId: string, profileId?: string) => {
    const params = new URLSearchParams({ thread_id: threadId });
    if (profileId) params.set("profile_id", profileId);
    return request<ThreadReadResponse>(`/api/runtime/thread?${params.toString()}`).then(normalizeThreadReadResponse);
  },
  createThread: (payload: {
    profile_id: string;
    model?: string;
    effort?: string;
    permission_mode: PermissionMode;
    task_id?: string;
    name?: string;
    operation_id?: string;
  }) => jsonRequest<ThreadReadResponse>("/api/runtime/threads/create", payload).then(normalizeThreadReadResponse),
  beginThreadCreate: (payload: {
    profile_id: string;
    model?: string;
    effort?: string;
    permission_mode: PermissionMode;
    name?: string;
    operation_id: string;
  }) =>
    jsonRequest<ThreadCreateRecoveryResponse>("/api/runtime/threads/create/start", payload, { timeoutMs: THREAD_CREATE_RECEIPT_TIMEOUT_MS }).then((response) => ({
      ...response,
      thread: response.thread ? normalizeShellThread(response.thread) : response.thread,
      task: response.task ? normalizeProjectTask(response.task) : response.task,
    })),
  recoverThreadCreate: (payload: { profile_id: string; operation_id: string }) =>
    jsonRequest<ThreadCreateRecoveryResponse>("/api/runtime/threads/create/recover", payload, { timeoutMs: THREAD_CREATE_RECEIPT_TIMEOUT_MS }).then((response) => ({
      ...response,
      thread: response.thread ? normalizeShellThread(response.thread) : response.thread,
      task: response.task ? normalizeProjectTask(response.task) : response.task,
    })),
  forkThread: (payload: {
    thread_id: string;
    profile_id?: string;
    model?: string;
    effort?: string;
    permission_mode: PermissionMode;
    name?: string;
  }) => jsonRequest<ThreadReadResponse>("/api/runtime/threads/fork", payload).then(normalizeThreadReadResponse),
  renameThread: (threadId: string, name: string, profileId?: string) =>
    jsonRequest<{ thread: { thread_id: string; name: string } }>("/api/runtime/threads/rename", {
      thread_id: threadId,
      name,
      profile_id: profileId,
    }),
  archiveThread: (threadId: string, profileId?: string) =>
    jsonRequest<{ archived: string }>("/api/runtime/threads/archive", { thread_id: threadId, profile_id: profileId }),
  switchThread: (threadId: string | null) =>
    jsonRequest<{ project: ProjectFile; task?: ProjectTasksResponse["tasks"][number] | null }>("/api/runtime/threads/switch", { thread_id: threadId }).then((response) => ({
      ...response,
      task: response.task ? normalizeProjectTask(response.task) : response.task,
    })),
  saveThreadSettings: (payload: {
    thread_id: string;
    profile_id?: string;
    model?: string;
    effort?: string;
    permission_mode?: PermissionMode;
    collaboration_mode?: CollaborationMode;
  }) => jsonRequest<{ settings: ShellThread["shellSettings"] }>("/api/runtime/thread-settings", payload),
  getGoal: (threadId: string, profileId?: string) => {
    const params = new URLSearchParams({ thread_id: threadId });
    if (profileId) params.set("profile_id", profileId);
    return request<GoalResponse>(`/api/runtime/goal?${params.toString()}`);
  },
  setGoal: (payload: { thread_id: string; profile_id?: string; objective: string; status?: "active" | "paused" | "blocked" | "usageLimited" | "budgetLimited" | "complete"; token_budget?: number | null }) =>
    jsonRequest<GoalResponse>("/api/runtime/goal/set", payload),
  clearGoal: (threadId: string, profileId?: string) =>
    jsonRequest<GoalResponse>("/api/runtime/goal/clear", { thread_id: threadId, profile_id: profileId }),
  compactThread: (threadId: string, profileId?: string) =>
    jsonRequest<{ started: boolean; thread_id: string }>("/api/runtime/thread/compact", { thread_id: threadId, profile_id: profileId }),
  startTurn: (payload: {
    thread_id: string;
    profile_id?: string;
    text: string;
    attachments: AttachmentDraft[];
    model?: string;
    effort?: string;
    permission_mode: PermissionMode;
    collaboration_mode?: CollaborationMode;
    context_mode?: ContextMode;
    execution_policy?: TurnExecutionPolicy;
  }) => jsonRequest<TurnStartResponse>("/api/runtime/turns/start", payload, { timeoutMs: 120000 }),
  interruptTurn: (threadId: string, turnId: string, profileId?: string) =>
    jsonRequest<{ interrupt: unknown }>("/api/runtime/turns/interrupt", {
      thread_id: threadId,
      turn_id: turnId,
      profile_id: profileId,
    }),
};


