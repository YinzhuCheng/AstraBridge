import type {
  Thread,
  ThreadGoal,
  ThreadItem,
  ThreadTokenUsage,
  TurnPlanStep,
} from "./protocol/generated/v2";

export type LocaleCode = "en" | "zh-CN";
export type PermissionMode = "ask" | "auto" | "full";
export type CollaborationMode = "default" | "plan";
export type AppearancePreset = "codex" | "paper" | "slate" | "cobalt" | "sunrise";
export type ExecutionHost = "windows" | "wsl";

export type ProjectFile = {
  schema_version: string;
  project_id: string;
  name: string;
  project_file: string;
  workspace_root: string;
  entry_mode: "existing" | "new";
  default_profile_id: string;
  default_model: string;
  default_effort: string;
  current_thread_id: string | null;
  recent_threads: string[];
  current_task_id?: string | null;
  recent_tasks?: string[];
  ui_preferences: {
    locale?: LocaleCode;
    appearance?: AppearancePreset;
    execution_host?: ExecutionHost;
    wsl_distro?: string;
    left_sidebar_width?: number;
    right_sidebar_width?: number;
    right_sidebar_open?: boolean;
  };
  created_at: string;
  updated_at: string;
};

export type ProjectTaskProviderThread = {
  thread_id: string;
  role?: "provider" | "fork" | string;
  profile_id?: string;
  provider_id?: string;
  model?: string;
  reasoning_effort?: string;
  permission_mode?: PermissionMode;
  collaboration_mode?: CollaborationMode;
  name?: string;
  missing_at?: string;
  missing_reason?: string;
  created_at?: string;
  updated_at?: string;
};

export type ContextMode = "default" | "minimal_visual" | "no_context";

export type ProjectTaskHandoffEvent = {
  event_id: string;
  type: "provider_handoff" | string;
  handoff_policy?: string;
  from_thread_id?: string | null;
  to_thread_id: string;
  profile_id?: string;
  provider_id?: string;
  model?: string;
  reasoning_effort?: string;
  permission_mode?: PermissionMode;
  reused_existing?: boolean;
  transition_summary?: {
    from_provider?: string | null;
    to_provider?: string;
    to_model?: string;
    projection_mode?: string;
    dropped_artifacts?: number;
    repaired_tool_pairs?: number;
    replayable_artifact_count?: number;
    projection_preview?: string | null;
    warnings?: string[];
    target_runtime?: Record<string, unknown>;
    transition_plan?: Record<string, unknown>;
  };
  created_at: string;
};

export type ProjectTask = {
  schema_version: string;
  task_id: string;
  project_id?: string;
  title: string;
  status: string;
  handoff_policy: "multi_provider_handoff" | string;
  active_provider_thread_id?: string | null;
  provider_threads: ProjectTaskProviderThread[];
  fork_threads?: ProjectTaskProviderThread[];
  handoff_events: ProjectTaskHandoffEvent[];
  goal?: unknown;
  plan?: unknown;
  checkpoint_refs?: Array<Record<string, unknown>>;
  verification_refs?: Array<Record<string, unknown>>;
  diagnostic_refs?: Array<Record<string, unknown>>;
  asset_context_refs?: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
};

export type ProjectTasksResponse = {
  schema_version: string;
  current_task: ProjectTask | null;
  tasks: ProjectTask[];
  updated_at?: string;
};

export type ProjectSummary = {
  project_id: string;
  name: string;
  project_file: string;
  workspace_root: string;
  entry_mode: "existing" | "new";
  updated_at: string;
};

export type Profile = {
  profile_id: string;
  label: string;
  type: string;
  provider_id: string;
  base_url?: string;
  model: string;
  reasoning_effort: string;
  wire_api: string;
  execution_backend?: string;
  env_key: string;
  auth_mode: "session_paste" | "env_ref" | "key_file" | "os_keychain";
  proxy_mode: "direct" | "system" | "custom";
  proxy_url: string;
  supported_reasoning_levels?: string[];
  default_reasoning_level?: string | null;
  reasoning_policy_mode?: string;
  input_modalities?: string[];
  capabilities?: Record<string, unknown>;
  edit_policy?: Record<string, string>;
  apply_patch_tool_type?: string | null;
  web_search_tool_type?: string | null;
  supports_search_tool?: boolean;
  supports_mcp_tools?: boolean;
  mcp_tool_call_policy?: string;
  mcp_verified_servers?: string[];
  mcp_smoke_status?: string;
  mcp_tool_argument_validation?: string;
  native_web_search_support?: string;
  tool_web_search_support?: string;
  mcp_web_support?: string;
  web_smoke_status?: string;
  citation_quality?: string;
  codex_builtin_tools?: Record<string, { support?: string; notes?: string; last_verified_at?: string | null }>;
  planner_support?: Record<string, string>;
  goal_support?: Record<string, string>;
  context_compaction_support?: Record<string, string>;
  temperature_default?: number;
  temperature_ui_min?: number;
  temperature_ui_max?: number;
  provider_temperature_min?: number;
  provider_temperature_max?: number;
  temperature_adapter_policy?: string;
  created_at?: string;
  updated_at?: string;
};

export type RuntimeEnvironment = {
  codex_cli: string | null;
  execution_host?: ExecutionHost;
  wsl_distro?: string | null;
  running: boolean;
  admin_session_token?: string;
  router?: {
    ok: boolean;
    service: string;
    running: boolean;
    listen_host: string;
    listen_port: number;
    base_url: string;
    router_env_key: string;
    token_loaded: boolean;
    provider_count: number;
    model_count: number;
    latest_test?: RouterTestResult | null;
    providers: Array<{
      provider_id: string;
      label: string;
      base_url: string;
      model: string;
      wire_api: string;
      secret_loaded: boolean;
    }>;
  };
  runtime_config: {
    configured: boolean;
    codex_home: string;
    provider_id: string | null;
    provider_name: string | null;
    base_url: string | null;
    model: string | null;
    reasoning_effort: string | null;
    wire_api: string | null;
    env_key: string | null;
    secret_loaded: boolean;
    proxy_mode: string;
    proxy_url: string;
    execution_host?: ExecutionHost;
    wsl_distro?: string | null;
    secret_source?: string | null;
    secret_fingerprint?: string | null;
  };
};

export type WslDependencyCheck = {
  id: string;
  label: string;
  status: "ok" | "missing" | "failed" | "warning" | "misconfigured" | string;
  detail: string;
  required: boolean;
  remediation?: string | null;
};

export type WslDependencyStatus = {
  ok: boolean;
  generated_at: string;
  default_distro: string;
  selected_distro: string;
  wsl_executable: string | null;
  distros: Array<{ name: string; state?: string; version?: string }>;
  checks: WslDependencyCheck[];
  paths: {
    astrabridge_wsl_codex_bin: string;
    astrabridge_wsl_codex_home: string;
    script_root: string;
  };
};

export type WslBootstrapScriptsResponse = {
  ok: boolean;
  distro: string;
  windows_script_path: string;
  wsl_script_path: string;
  run_command: string;
  launched?: boolean;
};

export type RouterProvider = {
  id: string;
  provider_id?: string;
  display_name: string;
  enabled: boolean;
  adapter_type: string;
  runtime_backend?: string;
  base_url: string;
  auth_key_ref?: string | null;
  default_model: string;
  request_timeout_ms: number;
  stream_idle_timeout_ms: number;
  env_key: string;
  auth_mode: "session_paste" | "env_ref" | "key_file" | "os_keychain";
  proxy_mode: "direct" | "system" | "custom";
  proxy_url: string;
  logo_source_url?: string;
  logo_asset_path?: string;
  logo_license_note?: string;
  accent_color?: string;
  supported_reasoning_levels?: string[];
  default_reasoning_level?: string | null;
  reasoning_policy_mode?: string;
  input_modalities?: string[];
  capabilities?: Record<string, unknown>;
  edit_policy?: Record<string, string>;
  apply_patch_tool_type?: string | null;
  web_search_tool_type?: string | null;
  supports_search_tool?: boolean;
  supports_mcp_tools?: boolean;
  mcp_tool_call_policy?: string;
  mcp_verified_servers?: string[];
  mcp_smoke_status?: string;
  mcp_tool_argument_validation?: string;
  native_web_search_support?: string;
  tool_web_search_support?: string;
  mcp_web_support?: string;
  web_smoke_status?: string;
  citation_quality?: string;
  codex_builtin_tools?: Record<string, { support?: string; notes?: string; last_verified_at?: string | null }>;
  planner_support?: Record<string, string>;
  goal_support?: Record<string, string>;
  context_compaction_support?: Record<string, string>;
  temperature_default?: number;
  temperature_ui_min?: number;
  temperature_ui_max?: number;
  provider_temperature_min?: number;
  provider_temperature_max?: number;
  temperature_adapter_policy?: string;
  created_at?: string;
  updated_at?: string;
};

export type RouterModelEntry = {
  id: string;
  provider: string;
  native_model: string;
  display_name: string;
  enabled: boolean;
  advertised_context_window: number;
  ui_context_hint_only: boolean;
  adapter_profile: string;
  model_kind?: string;
  codex_agent_enabled?: boolean;
  input_modalities?: string[];
  supports_reasoning_summaries?: boolean;
  reasoning_display_policy?: "collapsed_3_lines" | "hidden" | "expanded" | string;
  supported_reasoning_levels?: string[];
  default_reasoning_level?: string | null;
  supports_parallel_tool_calls?: boolean;
  apply_patch_tool_type?: string | null;
  supports_search_tool?: boolean;
  native_web_search_support?: string;
  tool_web_search_support?: string;
  mcp_web_support?: string;
  web_smoke_status?: string;
  citation_quality?: string;
  last_web_verified_at?: string | null;
  web_search_tool_type?: string | null;
  tool_mode?: string | null;
  multi_agent_version?: string | null;
  use_responses_lite?: boolean;
  supports_image_detail_original?: boolean;
  effective_context_window_percent?: number;
  auto_compact_token_limit?: number | null;
  tool_output_token_limit?: number | null;
  temperature_default?: number;
  temperature_ui_min?: number;
  temperature_ui_max?: number;
  provider_temperature_min?: number;
  provider_temperature_max?: number;
  temperature_adapter_policy?: string;
  pricing_currency?: string;
  pricing_input_per_mtok?: number | null;
  pricing_output_per_mtok?: number | null;
  pricing_cached_input_per_mtok?: number | null;
  pricing_source_url?: string;
  pricing_status?: string;
  experimental_supported_tools?: string[];
  supports_mcp_tools?: boolean;
  mcp_tool_call_policy?: "verified" | "conservative" | "unsupported" | string;
  mcp_verified_servers?: string[];
  mcp_smoke_status?: "untested" | "pass" | "warn" | "fail" | string;
  mcp_tool_argument_validation?: "native" | "router_repair" | "unsupported" | string;
  codex_builtin_tools?: Record<string, { support?: string; notes?: string; last_verified_at?: string | null }>;
  planner_support?: Record<string, string>;
  goal_support?: Record<string, string>;
  context_compaction_support?: Record<string, string>;
  modality_limits?: Record<string, unknown>;
  ui_warnings?: string[];
  authority_tier?: "A" | "B" | "C" | "D" | string;
  authority_reason?: string;
  parallel_tool_call_status?: "verified" | "serial_only" | "disabled" | string;
  source_urls?: string[];
  source_status?: string;
  recommended?: boolean;
  default_for_provider?: boolean;
  deprecated?: boolean;
  deprecated_after?: string | null;
  confidence?: string | null;
  catalog_version?: string | null;
  source_provenance?: Record<string, unknown>;
  last_verified_at?: string | null;
  verification_notes?: string;
  created_at?: string;
  updated_at?: string;
};

export type MetadataSourceRecord = {
  provider_id: string;
  display_name: string;
  urls: string[];
  source_status: string;
  notes?: string;
};

export type MetadataSourcesResponse = {
  providers: MetadataSourceRecord[];
  updated_at: string;
  catalog_schema?: string;
};

export type CodexModelCatalogEntry = Record<string, unknown> & {
  id: string;
  name?: string;
  model: string;
  context_window?: number;
};

export type EffectiveCatalogResponse = {
  models: CodexModelCatalogEntry[];
  model_count: number;
  generated_at: string;
  catalog_version?: string;
  review_path?: string;
  models_lock_path?: string;
  sources_lock_path?: string;
};

export type LlmManagerSession = {
  mode: "managed_user" | "anonymous";
  username: string | null;
  unlocked: boolean;
  started_at: string;
  auth_surface: string;
  users: Array<{ username: string; has_vault: boolean; display_name?: string; avatar_path?: string; updated_at?: string | null }>;
  profile?: { display_name: string; avatar_path: string; updated_at?: string | null };
  key_count: number;
  active_key_ids: Record<string, string>;
};

export type ProjectCheckpoint = {
  save_id: string;
  save_dir: string;
  created_at: string;
  project_name: string;
  thread_id: string | null;
  thread_name: string;
  description: string;
  default_description: string;
  provider?: string | null;
  model?: string | null;
  workspace: {
    is_git_repo: boolean;
    base_commit: string | null;
    dirty: boolean;
    file_count?: number;
    excluded?: Array<{ path: string; reason: string }>;
  };
  project_file?: string;
};

export type ProjectSavesResponse = {
  saves: ProjectCheckpoint[];
  saves_root: string;
};

export type ProjectSaveCreateResponse = {
  save: ProjectCheckpoint;
};

export type ProjectSaveLoadResponse = {
  save: ProjectCheckpoint;
  preview?: boolean;
  loaded?: boolean;
  restore_point?: ProjectCheckpoint | null;
  dirty?: boolean;
  changed_files?: string[];
  message?: string;
};

export type LlmManagerKey = {
  key_id: string;
  provider_id: string;
  label: string;
  env_key: string;
  fingerprint: string;
  enabled: boolean;
  last_test_status?: "pass" | "fail" | string | null;
  last_test_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type LlmManagerKeysResponse = {
  keys: LlmManagerKey[];
  active_key_ids: Record<string, string>;
  locked?: boolean;
};

export type LlmEffectiveCatalogResponse = {
  mode: LlmManagerSession["mode"];
  username: string | null;
  providers: Array<RouterProvider & { managed_key_available?: boolean }>;
  models: Array<RouterModelEntry & { verified?: boolean; health?: Record<string, unknown> }>;
  model_count: number;
  verified_model_ids: string[];
  warnings: string[];
  generated_at: string;
};

export type LlmHealthResultsResponse = {
  updated_at?: string | null;
  results: Array<Record<string, unknown>>;
  model_health: Record<string, Record<string, unknown>>;
};

export type MetadataRefreshResponse = {
  applied: boolean;
  fetched: Array<Record<string, unknown>>;
  source_results?: Array<Record<string, unknown>>;
  summary?: {
    status: "idle" | "success" | "partial" | "failed" | string;
    total_sources: number;
    ok_sources: number;
    failed_sources: number;
    by_classification: Record<string, number>;
  };
  proposed: {
    providers: RouterProvider[];
    models: RouterModelEntry[];
    model_count: number;
  };
  updated_at: string;
  catalog_version?: string;
  review_path?: string;
  models_lock_path?: string;
  sources_lock_path?: string;
  artifact_paths?: Record<string, string>;
};

export type MetadataRefreshJobStartResponse = {
  job_id: string;
  status: "running" | string;
  apply: boolean;
  started_at: string;
};

export type MetadataRefreshJobStatusResponse = {
  job_id: string | null;
  status: "idle" | "running" | "success" | "partial" | "failed" | string;
  running: boolean;
  apply?: boolean;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  summary?: MetadataRefreshResponse["summary"];
  source_results?: Array<Record<string, unknown>>;
  artifact_paths?: Record<string, string>;
  latest_job_id?: string | null;
};

export type MetadataReportResponse = {
  path: string;
  catalog_path: string;
  config_path: string;
  review_path?: string;
  models_lock_path?: string;
  sources_lock_path?: string;
};

export type TestMatrixResponse = {
  generated_at: string;
  stopped_early: boolean;
  results: Array<Record<string, unknown>>;
  report: MetadataReportResponse;
};

export type ReasoningConfig = {
  global_effort: string;
  provider_overrides: Record<string, string>;
  model_overrides: Record<string, string>;
  native_parameter_overrides: Record<string, Record<string, unknown>>;
  updated_at?: string;
};

export type ResponseDiagnosticsWarning = {
  code?: string;
  severity?: string;
  message?: string;
};

export type ResponseDiagnosticsReasoningState = {
  provider_id?: string;
  model_id?: string;
  replayable?: boolean;
  visible_summary?: string | null;
  opaque_artifact_count?: number;
};

export type ResponseDiagnosticsRawRef = {
  kind?: string;
  locator?: string;
  redaction_status?: string;
  summary?: string | null;
};

export type ResponseDiagnostics = {
  text_excerpt?: string | null;
  reasoning_summary?: string | null;
  finish_reason?: string | null;
  warnings?: ResponseDiagnosticsWarning[];
  provider_data_keys?: string[];
  tool_calls?: Array<{ id?: string; name?: string }>;
  usage?: Record<string, unknown>;
  reasoning_state?: ResponseDiagnosticsReasoningState;
  raw_ref?: ResponseDiagnosticsRawRef;
};

export type RuntimeFailureTransitionTarget = {
  provider_id?: string;
  model_id?: string;
  protocol?: string;
  runtime_backend?: string;
  env_key?: string;
  base_url?: string;
  reasoning_effort?: string;
  reasoning_policy_mode?: string;
};

export type RuntimeFailureTransition = {
  action?: string;
  reason?: string;
  reasoning_effort?: string | null;
  context_strategy?: string;
  restart_runtime?: boolean;
  compact_before_send?: boolean;
  drop_reasoning_replay?: boolean;
  notes?: string[];
  target?: RuntimeFailureTransitionTarget;
} | null;

export type RuntimeFailureAction = {
  action: string;
  label: string;
  reason: string;
  target?: string | null;
  transition?: RuntimeFailureTransition;
};

export type RuntimeFailureNotice = {
  level: "warning" | "danger" | string;
  category: string;
  provider?: string;
  model?: string;
  summary: string;
  message?: string;
  actionable_hint?: string;
  recommended_action?: string;
  recoverability?: "retryable" | "recoverable" | "requires_user_action" | "fail_closed" | string;
  fallback_models?: string[];
  reasoning_downgrade_levels?: string[];
  requires_key_check?: boolean;
  provider_switch_recommended?: boolean;
  native_status?: number;
  native_code?: string | null;
  recommended_actions?: RuntimeFailureAction[];
  thread_id?: string;
  turn_id?: string;
  last_updated_at?: string | null;
};

export type RouterTestResult = {
  ok: boolean;
  provider: string;
  model: string;
  stream: boolean;
  status: number;
  content_type?: string;
  preview: Record<string, unknown>;
  response_excerpt: string;
  preview_warnings?: string[];
  response_diagnostics?: ResponseDiagnostics | null;
  failure_notice?: RuntimeFailureNotice | null;
  timestamp?: string;
};

export type RouterConfigResponse = {
  providers: RouterProvider[];
  models: RouterModelEntry[];
  reasoning: ReasoningConfig;
  latest_test?: RouterTestResult | null;
  enabled_model_count: number;
};

export type McpServerConfig = {
  name: string;
  display_name: string;
  enabled: boolean;
  transport: "stdio" | "streamable_http";
  command: string;
  args: string[];
  cwd?: string | null;
  env: Record<string, string>;
  env_vars: string[];
  url: string;
  bearer_token_env_var?: string | null;
  http_headers: Record<string, string>;
  env_http_headers: Record<string, string>;
  startup_timeout_sec: number;
  tool_timeout_sec: number;
  required: boolean;
  default_tools_approval_mode: "auto" | "prompt" | "approve";
  enabled_tools: string[];
  disabled_tools: string[];
  tools: Record<string, { approval_mode?: "auto" | "prompt" | "approve" | string }>;
  trust_note: string;
  source_url: string;
  created_at?: string;
  updated_at?: string;
};

export type McpConfigResponse = {
  servers: McpServerConfig[];
  updated_at: string;
  environment: { node: boolean; npx: boolean; python?: boolean };
};

export type YunwuImageSmokeResponse = {
  ok: boolean;
  provider: string;
  tool: string;
  model: string;
  elapsed_ms: number;
  created?: number;
  data: Array<{ url?: string; revised_prompt?: string; b64_json_bytes?: number }>;
  timestamp: string;
};

export type DogfoodRun = {
  enabled: boolean;
  goal: string;
  phase: string;
  status: string;
  current_provider: string;
  blocker: string;
  next_step: string;
  budgets: {
    kimi_cny: number;
    deepseek_cny: number;
    yunwu_gpt_usd?: number;
    yunwu_images: number;
    warn_percent: number;
  };
  usage: {
    kimi_cny: number;
    deepseek_cny: number;
    yunwu_gpt_usd?: number;
    yunwu_images: number;
  };
  captures: Array<{ path: string; label?: string; provider?: string; created_at?: string }>;
  browser_smokes?: DogfoodBrowserSmoke[];
  milestones?: DogfoodMilestone[];
  notes: Array<string | Record<string, unknown>>;
  updated_at: string;
};

export type DogfoodRunResponse = {
  run: DogfoodRun;
  path: string;
};

export type AssetRegistryEntry = {
  asset_id: string;
  parent_asset_id?: string;
  stage: string;
  kind: string;
  role: string;
  purpose?: string;
  status: string;
  quality_status: string;
  integration_status: string;
  provider?: string;
  model?: string;
  tool?: string;
  source?: string;
  source_path?: string;
  sliced_manifest_path?: string;
  promoted_path?: string;
  game_refs?: string[];
  warnings?: string[];
  prompt_excerpt?: string;
  updated_at?: string;
};

export type AssetContextPack = {
  schema_version: string;
  generated_at: string;
  registry_path: string;
  context_pack_path: string;
  summary: Record<string, unknown>;
  rules: string[];
  promoted: AssetRegistryEntry[];
  approved_unpromoted: AssetRegistryEntry[];
  needs_review: AssetRegistryEntry[];
  text: string;
};

export type AssetRegistryResponse = {
  registry: {
    schema_version: string;
    rebuilt_at: string;
    workspace_root: string;
    sources: Record<string, string>;
    assets: AssetRegistryEntry[];
    summary: Record<string, unknown>;
  };
  path: string;
  context_pack: AssetContextPack;
};

export type ProjectContextPackResponse = {
  context_pack: {
    schema_version: string;
    generated_at: string;
    project: Record<string, unknown>;
    task?: Record<string, unknown>;
    selected_thread: Record<string, unknown>;
    recent_threads: Array<Record<string, unknown>>;
    dogfood: Record<string, unknown>;
    assets: Record<string, unknown>;
    rules: string[];
    text: string;
  };
  path: string;
  context_pack_path?: string;
};

export type DogfoodBrowserSmoke = {
  label: string;
  url: string;
  status: string;
  http_status?: number | null;
  console_errors?: string[];
  request_failures?: Array<{
    url?: string;
    method?: string;
    resource_type?: string;
    error_text?: string;
  }>;
  screenshot_path?: string;
  screenshot_status?: string;
  screenshot_error?: string;
  created_at: string;
  error?: string;
};

export type DogfoodMilestone = {
  label: string;
  provider: string;
  model?: string;
  goal?: string;
  plan_step?: string;
  status: string;
  captures: string[];
  capture_paths?: string[];
  validation: string[];
  validation_result?: string | Record<string, unknown>;
  failure_reason?: string;
  next_step?: string;
  next_action?: string;
  created_at: string;
};

export type PlanDisplayState = {
  thread_id: string;
  turn_id: string;
  explanation: string | null;
  steps: TurnPlanStep[];
  last_updated_at: string | null;
  source: string;
};

export type RuntimeSupervisorState = {
  thread_id: string;
  updated_at: string;
  plan: PlanDisplayState | null;
  token: {
    total_tokens: number;
    context_window: number;
    context_percent: number;
    turn_id?: string;
    last?: Record<string, unknown>;
    last_updated_at?: string | null;
  };
  guard: {
    level: "ok" | "warning" | "danger" | "pause" | string;
    recommended_action: string;
    should_pause: boolean;
    message: string;
    auto_pause?: {
      attempted: boolean;
      status: string;
      error?: string;
      result?: Record<string, unknown>;
    };
  };
  watchdog?: {
    level: "ok" | "warning" | "danger" | "pause" | string;
    idle_seconds: number;
    recommended_action: string;
    message: string;
    turn_id?: string;
  };
  thread_status: { type?: string; activeFlags?: string[]; [key: string]: unknown };
  runtime_error?: RuntimeFailureNotice | null;
  environment: {
    project_name?: string;
    cwd?: string;
    provider?: string;
    model?: string;
    effort?: string;
    permission?: string;
    git?: { is_repo: boolean; branch: string; changed_files: number; added: number; deleted: number };
    mcp?: { status: string; count?: number | null; last_updated_at?: string | null };
  };
  browser: DogfoodBrowserSmoke;
  dogfood: {
    enabled: boolean;
    phase: string;
    status: string;
    current_provider: string;
    next_step: string;
    usage: Record<string, number>;
    budgets: Record<string, number>;
    latest_milestone?: DogfoodMilestone | null;
  };
  modal: {
    pending_count: number;
    current: RuntimeModal | null;
  };
};

export type ProjectReviewFile = {
  path: string;
  status: string;
};

export type ProjectReviewStatus = {
  workspace_root: string;
  git: {
    is_repo: boolean;
    branch: string;
    changed_files: number;
    added: number;
    deleted: number;
  };
  files: ProjectReviewFile[];
  updated_at: string;
};

export type ProjectReviewDiff = {
  ok: boolean;
  path: string;
  diff: string;
  truncated?: boolean;
  error?: string;
};

export type ReleaseWorkflowDemoResponse = {
  ok: boolean;
  workspace_root: string;
  task?: ProjectTask | null;
  review_status?: ProjectReviewStatus;
  terminal_history?: ProjectTerminalHistory;
  checkpoints?: ProjectSavesResponse;
  baseline_commit?: string;
  review_artifact?: string;
  failed_run?: Record<string, unknown>;
  recovered_run?: Record<string, unknown>;
  provider_switch_present?: boolean;
  updated_at?: string;
};

export type NativeKernelDemoResponse = {
  ok: boolean;
  workspace_root: string;
  task?: ProjectTask | null;
  thread_id?: string;
  execution_backend?: string;
  review_status?: ProjectReviewStatus;
  terminal_history?: ProjectTerminalHistory;
  checkpoints?: ProjectSavesResponse;
  baseline_commit?: string;
  updated_at?: string;
};

export type ProjectFileTreeItem = {
  path: string;
  name: string;
  kind: "text" | "image" | "binary" | string;
  size: number;
  updated_at: number;
};

export type ProjectFilesTree = {
  workspace_root: string;
  items: ProjectFileTreeItem[];
  truncated: boolean;
  updated_at: string;
};

export type ProjectFilePreview = {
  path: string;
  name: string;
  kind: "text" | "image" | "binary" | "too_large" | string;
  size: number;
  updated_at: number;
  content?: string;
  mime_type?: string;
  data_url?: string;
  message?: string;
};

export type ProjectTerminalHistory = {
  workspace_root: string;
  execution_host: string;
  commands: Array<{
    timestamp?: string;
    status: string;
    command: string;
    summary: string;
  }>;
  updated_at: string;
};

export type McpRuntimeStatus = {
  name: string;
  serverInfo: Record<string, unknown> | null;
  tools: Record<string, Record<string, unknown>>;
  resources: Array<Record<string, unknown>>;
  resourceTemplates: Array<Record<string, unknown>>;
  authStatus: Record<string, unknown> | string;
};

export type McpStatusResponse = {
  servers: McpRuntimeStatus[];
  next_cursor: string | null;
};

export type ShellThreadSettings = {
  profile_id?: string;
  model?: string;
  reasoning_effort?: string;
  permission_mode?: PermissionMode;
  collaboration_mode?: CollaborationMode;
  execution_backend?: string;
};

export type ShellThread = Thread & {
  displayName: string;
  shellSettings: ShellThreadSettings;
  isCompositeTaskThread?: boolean;
  task_id?: string;
  active_provider_thread_id?: string | null;
  provider_threads?: ProjectTaskProviderThread[];
};

export type RuntimeModal = {
  modal_id: string;
  kind: "approval" | "user_input" | "mcp_elicitation";
  method: string;
  thread_id: string | null;
  turn_id: string | null;
  item_id: string | null;
  status: string;
  created_at: string;
  resolved_at?: string | null;
  params: Record<string, unknown>;
  resolution?: Record<string, unknown> | null;
};

export type AttachmentDraft = {
  id: string;
  path: string;
  name: string;
  mimeType: string;
  kind: "image" | "file";
  previewUrl?: string;
};

export type ThreadRenderMeta = {
  key: string;
  turnId?: string;
  startedAt?: number | null;
  completedAt?: number | null;
  durationMs?: number | null;
  sourceThreadId?: string;
  profileId?: string;
  providerId?: string;
  model?: string;
  reasoningEffort?: string;
};

export type ThreadRenderBlock =
  | (ThreadRenderMeta & { role: "user"; text: string; attachments?: string[] })
  | (ThreadRenderMeta & { role: "assistant"; text: string })
  | (ThreadRenderMeta & { role: "assistant_live"; text: string })
  | (ThreadRenderMeta & { role: "activity"; activity: RuntimeActivityState; diff?: RuntimeDiffSummary })
  | (ThreadRenderMeta & { role: "plan"; text: string })
  | (ThreadRenderMeta & { role: "reasoning"; text: string[]; source?: string; live?: boolean })
  | (ThreadRenderMeta & { role: "command"; command: string; output: string; status: string })
  | (ThreadRenderMeta & { role: "file_change"; files: string[]; status: string; added?: number; deleted?: number; detail?: string })
  | (ThreadRenderMeta & { role: "tool"; title: string; status: string; detail?: string })
  | (ThreadRenderMeta & { role: "image"; path: string });

export type EventSnapshot = {
  liveTextByTurn: Record<string, string>;
  livePlanTextByTurn: Record<string, string>;
  liveReasoningByTurn: Record<string, { text: string; source: string; label: string }>;
  activityByTurn: Record<string, RuntimeActivityState>;
  diffByTurn: Record<string, RuntimeDiffSummary>;
  planByThread: Record<string, { explanation: string | null; plan: TurnPlanStep[] }>;
  tokenUsageByThread: Record<string, ThreadTokenUsage>;
  latestTurnIdByThread: Record<string, string>;
  threadStatusByThread: Record<string, { type: string; activeFlags?: string[] }>;
};

export type RuntimeActivityKind =
  | "thinking"
  | "web_search"
  | "command"
  | "file_change"
  | "compact"
  | "review"
  | "fork"
  | "mcp"
  | "tool"
  | "waiting"
  | "completed";

export type RuntimeActivityState = {
  kind: RuntimeActivityKind;
  label: string;
  status: "active" | "completed" | "failed" | "pending" | string;
  preview?: string;
  detail?: string;
  item_id?: string;
  updated_at?: string;
};

export type RuntimeDiffSummary = {
  added: number;
  deleted: number;
  files: number;
  diff?: string;
  file_paths?: string[];
  detail?: string;
  updated_at?: string;
};

export type ThreadReadResponse = { thread: ShellThread; project?: ProjectFile; task?: ProjectTask };
export type TaskConversationResponse = { thread: ShellThread; task?: ProjectTask; transcript_path?: string; updated_at?: string };
export type ThreadListResponse = { threads: ShellThread[]; next_cursor: string | null; backwards_cursor: string | null };
export type TurnStartResponse = { turn: { id: string; status: string }; thread_id?: string; handoff?: ProjectTaskHandoffEvent | null; project?: ProjectFile; task?: ProjectTask };
export type GoalResponse = { goal: ThreadGoal | null };

export type RuntimeEvent = {
  index: number;
  timestamp: string;
  type: string;
  method?: string;
  params?: Record<string, unknown>;
  line?: string;
  [key: string]: unknown;
};

export type ThreadMessageSource = ThreadItem;


