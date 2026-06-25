import { invoke, isTauri } from "@tauri-apps/api/core";
import type {
  AppearancePreset,
  AutomationInboxItem,
  AutomationInboxResponse,
  AutomationListResponse,
  AutomationRun,
  AutomationRunsResponse,
  AutomationSchedulerStatus,
  AutomationSpec,
  AssetRegistryResponse,
  AttachmentDraft,
  CapabilityArtifactsResponse,
  CollaborationMode,
  CapabilityManagementResponse,
  CapabilityRouteEntry,
  CapabilityRouteRecord,
  CapabilitySmokeResponse,
  CodexPluginInstallExecution,
  CodexKernelProbeSnapshot,
  CodexPluginInstallPlan,
  CodexPluginSkillRegistrySnapshot,
  ContextMode,
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
  ProjectSummary,
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
  ProjectTerminalHistory,
  ShellThread,
  TaskConversationResponse,
  TestMatrixResponse,
  ThreadListResponse,
  ThreadReadResponse,
  TurnStartResponse,
  WslBootstrapScriptsResponse,
  WslDependencyStatus,
  YunwuImageSmokeResponse,
} from "./types";

let sidecarBaseUrlPromise: Promise<string> | null = null;
let adminTokenPromise: Promise<string> | null = null;

const SIDECAR_URL_STORAGE_KEY = "astrabridge.sidecarBaseUrl";

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

function browserSidecarBaseUrl() {
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

async function sidecarBaseUrl() {
  if (!sidecarBaseUrlPromise) {
    sidecarBaseUrlPromise = (async () => {
      if (isTauri()) {
        return invoke<string>("sidecar_url");
      }
      return browserSidecarBaseUrl();
    })();
  }
  return sidecarBaseUrlPromise;
}

type RequestWithTimeout = RequestInit & { timeoutMs?: number };

async function request<T>(path: string, init?: RequestWithTimeout): Promise<T> {
  const base = await sidecarBaseUrl();
  const isMutation = (init?.method ?? "GET").toUpperCase() !== "GET";
  const timeoutMs = init?.timeoutMs ?? (isMutation ? 65000 : 15000);
  const cacheMode = init?.cache ?? (isMutation ? "no-store" : "no-store");
  const headers: Record<string, string> = { "Content-Type": "application/json", ...((init?.headers ?? {}) as Record<string, string>) };
  if (isMutation) {
    if (!adminTokenPromise) {
      adminTokenPromise = fetch(`${base}/api/admin/session`)
        .then((response) => response.json())
        .then((data) => String(data.admin_session_token ?? ""));
    }
    headers["X-Admin-Token"] = await adminTokenPromise;
  }
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      headers,
      cache: cacheMode,
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    window.clearTimeout(timer);
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`The desktop sidecar did not respond in time for ${path}. Open Runtime and verify Codex login, provider key, model, and router health.`);
    }
    throw error;
  }
  window.clearTimeout(timer);
  let data: Record<string, unknown> = {};
  try {
    data = (await response.json()) as Record<string, unknown>;
  } catch {
    data = {};
  }
  if (!response.ok || data.ok === false) {
    throw new Error(String(data.error ?? `Request failed: ${path}`));
  }
  return data as T;
}

function jsonRequest<T>(path: string, payload: Record<string, unknown>) {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export const api = {
  health: () => request<{ ok: boolean; service: string; runtime: RuntimeEnvironment }>("/health"),
  currentProject: () => request<{ project: ProjectFile | null }>("/api/projects/current"),
  recentProjects: () => request<{ projects: ProjectSummary[] }>("/api/projects/recent"),
  createProject: (payload: {
    name: string;
    project_file: string;
    workspace_root?: string;
    entry_mode: "existing" | "new";
  }) => jsonRequest<{ project: ProjectFile }>("/api/projects/create", payload),
  openProject: (projectFile: string) => jsonRequest<{ project: ProjectFile }>("/api/projects/open", { project_file: projectFile }),
  closeProject: () => jsonRequest<{ closed: boolean }>("/api/projects/close", {}),
  updateProjectPreferences: (payload: {
    locale?: ProjectFile["ui_preferences"]["locale"];
    appearance?: AppearancePreset;
    execution_host?: ExecutionHost;
    wsl_distro?: string;
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
  projectTerminalHistory: () => request<ProjectTerminalHistory>("/api/project/terminal/history?limit=30"),
  projectTasks: () => request<ProjectTasksResponse>("/api/project/tasks"),
  taskConversation: (taskId?: string | null) => {
    const params = new URLSearchParams();
    if (taskId) params.set("task_id", taskId);
    const suffix = params.toString();
    return request<TaskConversationResponse>(`/api/project/task-conversation${suffix ? `?${suffix}` : ""}`);
  },
  createTask: (title?: string) => jsonRequest<{ task: ProjectTasksResponse["tasks"][number]; project: ProjectFile }>("/api/project/tasks/create", { title }),
  switchTask: (taskId: string) => jsonRequest<{ task: ProjectTasksResponse["tasks"][number]; project: ProjectFile }>("/api/project/tasks/switch", { task_id: taskId }),
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
  runAutomationNow: (automationId: string) => jsonRequest<{ run: AutomationRun; inbox_item?: AutomationInboxItem | null; scheduler: AutomationSchedulerStatus }>("/api/automations/run-now", { automation_id: automationId }),
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
  saveCapabilityRoute: (payload: CapabilityRouteRecord) => jsonRequest<{ route: CapabilityRouteEntry }>("/api/runtime/capability-routes/save", payload),
  llmManagerSession: () => request<LlmManagerSession>("/api/llm-manager/session"),
  llmManagerLogin: (payload: { username?: string; password?: string; mode?: "managed_user" | "anonymous" }) =>
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
  isolationAudit: () => request<IsolationAuditResponse>("/api/audit/isolation"),
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
  runtimeEvents: (after: number) => request<{ cursor: number; events: RuntimeEvent[] }>(`/api/runtime/events?after=${after}`),
  runtimeEventsStreamUrl: async (after: number) => {
    const base = await sidecarBaseUrl();
    const params = new URLSearchParams({ after: String(Math.max(0, after)), seconds: "60" });
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
    return request<ThreadListResponse>(`/api/runtime/threads?${params.toString()}`);
  },
  readThread: (threadId: string, profileId?: string) => {
    const params = new URLSearchParams({ thread_id: threadId });
    if (profileId) params.set("profile_id", profileId);
    return request<ThreadReadResponse>(`/api/runtime/thread?${params.toString()}`);
  },
  createThread: (payload: {
    profile_id: string;
    model?: string;
    effort?: string;
    permission_mode: PermissionMode;
    name?: string;
  }) => jsonRequest<ThreadReadResponse>("/api/runtime/threads/create", payload),
  forkThread: (payload: {
    thread_id: string;
    profile_id?: string;
    model?: string;
    effort?: string;
    permission_mode: PermissionMode;
    name?: string;
  }) => jsonRequest<ThreadReadResponse>("/api/runtime/threads/fork", payload),
  renameThread: (threadId: string, name: string, profileId?: string) =>
    jsonRequest<{ thread: { thread_id: string; name: string } }>("/api/runtime/threads/rename", {
      thread_id: threadId,
      name,
      profile_id: profileId,
    }),
  archiveThread: (threadId: string, profileId?: string) =>
    jsonRequest<{ archived: string }>("/api/runtime/threads/archive", { thread_id: threadId, profile_id: profileId }),
  switchThread: (threadId: string | null) => jsonRequest<{ project: ProjectFile }>("/api/runtime/threads/switch", { thread_id: threadId }),
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
  setGoal: (payload: { thread_id: string; profile_id?: string; objective: string; token_budget?: number | null }) =>
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
  }) => jsonRequest<TurnStartResponse>("/api/runtime/turns/start", payload),
  interruptTurn: (threadId: string, turnId: string, profileId?: string) =>
    jsonRequest<{ interrupt: unknown }>("/api/runtime/turns/interrupt", {
      thread_id: threadId,
      turn_id: turnId,
      profile_id: profileId,
    }),
};


