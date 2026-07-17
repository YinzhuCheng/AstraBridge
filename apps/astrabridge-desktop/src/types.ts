import type {
  Thread,
  ThreadGoal,
  ThreadItem,
  ThreadTokenUsage,
  TurnPlanStep,
} from "./protocol/generated/v2";

export type LocaleCode = "en" | "zh-CN";
export type PermissionMode = "ask" | "auto" | "full";
export type TurnExecutionPolicy = "standard" | "patch_only";
export type CollaborationMode = "default" | "plan";
export type AppearancePreset = "codex" | "paper" | "slate" | "cobalt" | "sunrise";
export type CursorEnhancementPreference = "auto" | "off";
export type ExecutionHost = "windows" | "wsl";

export type ProjectPluginSkillPresetPluginRef = {
  plugin_id: string;
  source_catalog_id?: string | null;
  display_name?: string | null;
};

export type ProjectPluginSkillPresetSkillRef = {
  record_id: string;
  skill_name: string;
  owner_plugin_id?: string | null;
  source_catalog_id?: string | null;
  display_name?: string | null;
};

export type ProjectPluginSkillPreset = {
  preset_id: string;
  display_name: string;
  plugin_refs: ProjectPluginSkillPresetPluginRef[];
  skill_refs: ProjectPluginSkillPresetSkillRef[];
  created_at?: string;
  updated_at?: string;
  notes?: string[];
};

export type ProjectPluginSkillPresetsState = {
  schema_version: string;
  active_preset_id: string;
  presets: ProjectPluginSkillPreset[];
  updated_at?: string;
  notes?: string[];
};

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
  plugin_skill_presets?: ProjectPluginSkillPresetsState;
  ui_preferences: {
    locale?: LocaleCode;
    appearance?: AppearancePreset;
    cursor_enhancement?: CursorEnhancementPreference;
    execution_host?: ExecutionHost;
    wsl_distro?: string;
    left_sidebar_open?: boolean;
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

export type TaskLaneSummary = {
  thread_id?: string | null;
  profile_id?: string | null;
  provider_id?: string | null;
  model?: string | null;
  reasoning_effort?: string | null;
  permission_mode?: PermissionMode | string | null;
  collaboration_mode?: CollaborationMode | string | null;
  name?: string | null;
  label?: string | null;
  missing_at?: string | null;
  missing_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ContextMode = "default" | "minimal_visual" | "no_context";

export type ProjectTaskHandoffEvent = {
  event_id: string;
  type: "provider_handoff" | string;
  handoff_policy?: string;
  from_thread_id?: string | null;
  from_profile_id?: string;
  from_provider_id?: string;
  from_model?: string;
  from_reasoning_effort?: string;
  from_permission_mode?: PermissionMode;
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
    warning_count?: number;
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
  lane_state?: {
    lane_count: number;
    handoff_count: number;
    active_lane?: TaskLaneSummary | null;
    previous_lane?: TaskLaneSummary | null;
    latest_handoff?: ProjectTaskHandoffEvent | null;
  };
  provider_threads: ProjectTaskProviderThread[];
  fork_threads?: ProjectTaskProviderThread[];
  handoff_events: ProjectTaskHandoffEvent[];
  goal?: unknown;
  plan?: unknown;
  checkpoint_refs?: Array<Record<string, unknown>>;
  verification_refs?: Array<Record<string, unknown>>;
  diagnostic_refs?: Array<Record<string, unknown>>;
  asset_context_refs?: Array<Record<string, unknown>>;
  context_pack_refs?: Array<Record<string, unknown>>;
  graph_definitions?: TaskGraphDefinition[];
  graph_run_refs?: TaskGraphRunRef[];
  graph_snapshot_refs?: TaskGraphSnapshotRef[];
  graph_activity_summary?: TaskGraphActivitySummary;
  created_at: string;
  updated_at: string;
};

export type TaskGraphNodePosition = {
  x: number;
  y: number;
};

export type TaskGraphContextPolicy = {
  policy_id: string;
  history_mode: string;
  artifact_mode: string;
  exclude_private_memory: boolean;
  include_machine_results: boolean;
  include_human_summaries: boolean;
  summary_strategy?: string;
  history_length?: number;
  included_artifacts?: string[];
  resource_refs?: string[];
};

export type TaskGraphNode = {
  node_id: string;
  graph_id: string;
  kind: string;
  label: string;
  agent_card_ref: string;
  execution_policy: Record<string, unknown>;
  output_contract: Record<string, unknown>;
  position: TaskGraphNodePosition;
  status: string;
  provider_id?: string;
  model_id?: string;
  reasoning_effort?: string;
  permission_mode?: string;
  collaboration_mode?: string;
  execution_backend?: string;
  budget?: unknown;
  human_summary_template?: string;
  machine_result_schema?: unknown;
  ui_hints?: unknown;
  artifact_requirements?: unknown;
  approval_gate?: Record<string, unknown>;
};

export type TaskGraphEdge = {
  edge_id: string;
  graph_id: string;
  from_node_id: string;
  to_node_id: string;
  edge_type: string;
  handoff_contract?: {
    message_template?: string;
    message_part_modes?: string[];
    required_output_schema_refs?: string[];
    port_bindings?: Array<{
      from_port_id: string;
      to_port_id: string;
    }>;
  };
  context_policy: TaskGraphContextPolicy;
  status: string;
};

export type TaskGraphDefinition = {
  schema_version: string;
  graph_id: string;
  task_id: string;
  title: string;
  template_id: string;
  status: string;
  nodes: TaskGraphNode[];
  edges: TaskGraphEdge[];
  graph_policy: {
    entry_node_ids?: string[];
  };
  orchestration_graph?: AgentOrchestrationGraph;
  created_at: string;
  updated_at: string;
  state_version: number;
};

export type TaskGraphBudgetSection = {
  status?: string | null;
  limits?: Record<string, number>;
  observed?: Record<string, number | null>;
  exceeded_fields?: string[];
  unknown_fields?: string[];
};

export type TaskGraphRunBudget = {
  status?: string | null;
  enforcement?: string | null;
  graph?: TaskGraphBudgetSection | null;
  run?: TaskGraphBudgetSection | null;
  nodes?: Array<TaskGraphBudgetSection & {
    node_id?: string | null;
    label?: string | null;
  }>;
  provider_models?: Array<TaskGraphBudgetSection & {
    provider_id?: string | null;
    model_id?: string | null;
  }>;
  static_blockers?: string[];
};

export type TaskGraphRunRef = {
  run_id: string;
  graph_id: string;
  task_id: string;
  trace_id?: string;
  context_id?: string;
  status: string;
  created_at: string;
  updated_at: string;
  state_version?: number;
  entry_node_ids: string[];
  node_status_counts: Record<string, number>;
  node_outcome_counts?: Record<string, number>;
  artifact_count: number;
  event_count: number;
  approval_state?: string | null;
  approval_details?: {
    status: string;
    review_kind?: string | null;
    node_id?: string | null;
    reason?: string | null;
    requested_at?: string | null;
    resolved_at?: string | null;
    decision?: string | null;
    notes?: string | null;
    resolution_summary?: string | null;
    worker_thread_id?: string | null;
    allowed_actions?: string[];
    blocked_actions?: string[];
  } | null;
  latest_event_type?: string | null;
  latest_event_at?: string | null;
  timeline_events?: TaskGraphRunTimelineEvent[];
  diagnostic_refs?: TaskGraphRunDiagnosticRef[];
  artifact_refs?: TaskGraphRunArtifactRef[];
  policy_snapshot?: {
    mode?: string | null;
    scheduler?: string | null;
    template_id?: string | null;
    execution_mode?: string | null;
    compatibility_shim?: boolean;
    parallel_group_count?: number;
    max_parallelism?: number;
    parallel_group_ids?: string[];
    recovery?: TaskGraphRecoverySummary | null;
    budget?: TaskGraphRunBudget | null;
  } | null;
  metrics?: {
    status?: string | null;
    elapsed_ms?: number | null;
    max_parallelism?: number | null;
    artifact_count?: number | null;
    event_count?: number | null;
    retry_count?: number | null;
    failure_count?: number | null;
    approval_count?: number | null;
    provider_call_count?: number | null;
    tool_call_count?: number | null;
    token_usage?: {
      status?: string | null;
      reason?: string | null;
      input_tokens?: number | null;
      output_tokens?: number | null;
      reasoning_tokens?: number | null;
      cached_input_tokens?: number | null;
      total_tokens?: number | null;
    } | null;
    cost?: {
      status?: string | null;
      reason?: string | null;
      currency?: string | null;
      total_cost?: number | null;
    } | null;
    unknown_fields?: string[];
  } | null;
  budget?: TaskGraphRunBudget | null;
  worker_count?: number;
  worker_bindings?: TaskGraphWorkerBinding[];
};

export type TaskGraphSnapshotRef = {
  snapshot_id: string;
  task_id: string;
  graph_id: string;
  label?: string | null;
  reason?: string | null;
  source_action?: string | null;
  state_version?: number | null;
  based_on_snapshot_id?: string | null;
  rollback_source_snapshot_id?: string | null;
  created_at: string;
  updated_at: string;
  artifact_paths: Record<string, string>;
  summary?: {
    node_count?: number;
    edge_count?: number;
    change_count?: number;
    change_types?: string[];
  };
  comparison?: {
    status?: string;
    change_count?: number;
    change_types?: string[];
  };
};

export type TaskGraphRunTimelineEvent = {
  event_id: string;
  event_type: string;
  created_at: string;
  summary?: string | null;
  node_id?: string | null;
  edge_id?: string | null;
  artifact_id?: string | null;
  status?: string | null;
};

export type TaskGraphRunDiagnosticRef = {
  artifact_id: string;
  artifact_kind: string;
  path: string;
  status: string;
  label?: string | null;
};

export type TaskGraphRunArtifactRef = {
  artifact_id: string;
  artifact_kind: string;
  path: string;
  status: string;
  label?: string | null;
};

export type TaskGraphRecoverySummary = {
  recovery_id?: string | null;
  source_run_id?: string | null;
  strategy?: string | null;
  selected_node_ids?: string[];
  rerun_node_ids?: string[];
  reused_node_ids?: string[];
};

export type TaskGraphWorkerArtifactRef = {
  artifact_id: string;
  artifact_kind: string;
  path: string;
  status: string;
};

export type TaskGraphWorkerOutputSummary = {
  human_summary?: string;
  machine_result_preview?: string;
  confidence?: unknown;
  next_action_hints?: string[];
  artifact_bundle_path?: string;
};

export type TaskGraphWorkerHandoff = {
  edge_id: string;
  to_node_id: string;
  edge_type: string;
  context_policy: {
    history_mode: string;
    artifact_mode: string;
    exclude_private_memory: boolean;
    include_machine_results: boolean;
    include_human_summaries: boolean;
    summary_strategy?: string;
    history_length?: number;
    included_artifacts?: string[];
    resource_refs?: string[];
  };
  downstream_input: {
    source: string;
    run_id: string;
    artifact_paths: string[];
    human_summary_path?: string | null;
    machine_result_path?: string | null;
  };
};

export type TaskGraphWorkerBinding = {
  binding_id: string;
  graph_id: string;
  run_id: string;
  node_id: string;
  worker_thread_id: string;
  parent_thread_id?: string;
  spawn_mode?: string;
  worker_origin?: string;
  agent_role?: string;
  agent_nickname?: string;
  status: string;
  execution_backend?: string;
  artifact_refs: TaskGraphWorkerArtifactRef[];
  output_summary?: TaskGraphWorkerOutputSummary;
  downstream_handoffs?: TaskGraphWorkerHandoff[];
  created_at: string;
  updated_at: string;
};

export type TaskGraphActivitySummary = {
  graph_count: number;
  run_count: number;
  latest_graph_id?: string | null;
  latest_run_id?: string | null;
  latest_run_status?: string | null;
  latest_updated_at?: string | null;
  graph_status_counts?: Record<string, number>;
  run_status_counts?: Record<string, number>;
};

export type TaskGraphTemplateSummary = {
  template_id: string;
  title: string;
  summary: string;
  node_count: number;
  edge_count: number;
  entry_node_ids: string[];
  node_kinds: string[];
  recommended_provider_ids?: string[];
  recommended_model_ids?: string[];
  artifact_expectations?: string[];
  validation_hints?: string[];
  constraints?: string[];
  preview_graph: {
    title: string;
    nodes: Array<{
      node_id: string;
      kind: string;
      label: string;
      position: TaskGraphNodePosition;
    }>;
    edges: Array<{
      edge_id: string;
      from_node_id: string;
      to_node_id: string;
      edge_type: string;
    }>;
  };
};

export type NodeTypeRegistryPortSpec = {
  port_id: string;
  port_type: string;
  shape?: string;
  required?: boolean;
  schema_ref?: string;
  artifact_kind?: string;
  label?: string;
};

export type NodeTypeRegistryEntry = {
  type_id: string;
  version: number;
  category: string;
  title: string;
  description?: string;
  config_schema: Record<string, unknown>;
  typed_ports: {
    inputs: NodeTypeRegistryPortSpec[];
    outputs: NodeTypeRegistryPortSpec[];
  };
  compiler_executor_id: string;
  default_policy: Record<string, unknown>;
  ui_hints: Record<string, unknown>;
  migration: Record<string, unknown>;
  registry_fingerprint: string;
  internal_only?: boolean;
};

export type NodeTypeRegistrySnapshot = {
  schema_version: string;
  registry_fingerprint: string;
  role_ids: string[];
  kind_aliases: Record<string, string>;
  node_types: NodeTypeRegistryEntry[];
};

export type TaskGraphDryRunStatus = "pass" | "warning" | "blocked" | string;

export type TaskGraphDryRunNodeResult = {
  node_id: string;
  label: string;
  status: TaskGraphDryRunStatus;
  reasons: string[];
};

export type TaskGraphDryRunEdgeResult = {
  edge_id: string;
  label: string;
  status: TaskGraphDryRunStatus;
  reasons: string[];
};

export type TaskGraphDryRunResult = {
  schema_version: string;
  run_id: string;
  graph_id: string;
  task_id: string;
  created_at: string;
  overall_status: TaskGraphDryRunStatus;
  status_counts: Record<string, number>;
  graph_result: {
    status: TaskGraphDryRunStatus;
    reasons: string[];
  };
  node_results: TaskGraphDryRunNodeResult[];
  edge_results: TaskGraphDryRunEdgeResult[];
  artifact_paths: {
    summary_json: string;
    report_md: string;
  };
  run_status?: string;
  artifact_refs?: Array<{
    artifact_id: string;
    artifact_kind: string;
    path: string;
    media_type: string;
    status: string;
    created_at: string;
  }>;
  run_ref?: TaskGraphRunRef;
};

export type AgentOrchestrationGraph = {
  schema_version: string;
  graph_id: string;
  task_id: string;
  title: string;
  template_id?: string | null;
  status: string;
  metadata: Record<string, unknown>;
  graph_policy: Record<string, unknown>;
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  schema_registry?: Record<string, unknown>;
  prompt_registry?: Record<string, unknown>;
  migration: Record<string, unknown>;
  state_version: number;
};

export type AgentOrchestrationGraphExportResponse = {
  schema_version: string;
  graph: TaskGraphDefinition;
  task: ProjectTask | null;
  orchestration_graph: AgentOrchestrationGraph;
  serialized_text: string;
  source_format?: string | null;
  export_format?: string | null;
  source_version?: string | null;
  adapter_manifest?: Record<string, unknown> | null;
  loss_report?: Record<string, unknown> | null;
  export_path?: string | null;
};

export type AgentOrchestrationGraphImportResponse = {
  schema_version: string;
  graph: TaskGraphDefinition;
  task: ProjectTask | null;
  orchestration_graph: AgentOrchestrationGraph;
  source_format?: string | null;
  source_version?: string | null;
  adapter_manifest?: Record<string, unknown> | null;
  loss_report?: Record<string, unknown> | null;
  import_path?: string | null;
  snapshot?: TaskGraphSnapshotRef;
};

export type TaskGraphSnapshotResponse = {
  schema_version: string;
  graph: TaskGraphDefinition;
  snapshot: TaskGraphSnapshotRef;
  task: ProjectTask | null;
};

export type TaskGraphSnapshotDiffResponse = {
  schema_version: string;
  snapshot: TaskGraphSnapshotRef;
  compared_snapshot?: TaskGraphSnapshotRef | null;
  compared_label?: string | null;
  diff_report: Record<string, unknown>;
  diff_markdown: string;
  task: ProjectTask | null;
};

export type TaskGraphRollbackResponse = {
  schema_version: string;
  graph: TaskGraphDefinition;
  snapshot: TaskGraphSnapshotRef;
  rolled_back_to_snapshot: TaskGraphSnapshotRef;
  task: ProjectTask | null;
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

export type SidebarThreadNode = {
  thread_id: string;
  title: string;
  role?: string;
  profile_id?: string;
  provider_id?: string;
  model?: string;
  reasoning_effort?: string;
  updated_at?: string;
  created_at?: string;
  missing_at?: string | null;
  missing_reason?: string | null;
  is_active?: boolean;
};

export type SidebarTaskNode = {
  task_id: string;
  title: string;
  status: string;
  updated_at: string;
  is_current: boolean;
  active_provider_thread_id?: string | null;
  threads: SidebarThreadNode[];
  provider_id?: string;
  model?: string;
  reasoning_effort?: string;
  thread_count?: number;
  lane_count?: number;
  active_lane_label?: string;
  previous_lane_label?: string;
  latest_lane_status?: string;
  handoff_count?: number;
  checkpoint_count?: number;
  missing_thread_count?: number;
  project_file?: string;
};

export type SidebarProjectNode = {
  project_id: string;
  name: string;
  project_file: string;
  workspace_root: string;
  updated_at: string;
  is_current: boolean;
  tasks: SidebarTaskNode[];
  warnings?: string[];
};

export type SidebarProjectsResponse = {
  schema_version: string;
  projects: SidebarProjectNode[];
  updated_at?: string;
};

export type TitleSuggestionResponse = {
  title: string;
  source: "llm" | "heuristic" | "unchanged" | "failed";
  changed: boolean;
  project?: ProjectFile | null;
  task?: ProjectTask | null;
  error?: string | null;
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
  command_execution_status?: string;
  command_execution_note?: string;
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

export type SidecarProvenance = {
  schema_version: "astrabridge-sidecar-provenance-v1" | string;
  origin: "current_source" | "app_managed" | "unknown" | string;
  launcher_mode: string;
  pid: number;
  command_line: string;
  command_argv: string[];
  command_line_redaction: string;
  executable: string;
  cwd: string;
  seed_root?: string | null;
  source_root: string;
  repo_root?: string | null;
  current_source_match: boolean;
  listen_host: string;
  listen_port?: number | null;
  port_owner: {
    status: "self" | "different_process" | "self_reported" | "unknown" | string;
    method: string;
    pid?: number | null;
    expected_pid?: number | null;
    listen_host?: string | null;
    listen_port?: number | null;
  };
};

export type RuntimeEnvironment = {
  codex_cli: string | null;
  execution_host?: ExecutionHost;
  wsl_distro?: string | null;
  running: boolean;
  admin_session_token?: string;
  sidecar?: SidecarProvenance | null;
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

export type CodexKernelProtocolStatus =
  | "supported"
  | "declared"
  | "unsupported"
  | "disabled_by_app"
  | "not_checked"
  | "error"
  | "unknown"
  | string;

export type CodexKernelCompatibilityStatus = "verified" | "probed" | "partial" | "blocked" | "unknown" | string;

export type CodexKernelProbeCommandEvidence = {
  command: string;
  status: "ok" | "failed" | "skipped" | string;
  summary?: string | null;
};

export type CodexKernelPluginRecord = {
  plugin_id: string;
  display_name: string | null;
  version: string | null;
  source_kind: "local_marketplace" | "remote_marketplace" | "installed_root" | "shared_remote" | "unknown" | string;
  availability: "installed" | "available" | "unavailable" | "unknown" | string;
};

export type CodexKernelSkillRecord = {
  skill_name: string;
  display_name: string | null;
  source_kind: "local_skill_root" | "plugin" | "project_root" | "remote_catalog" | "unknown" | string;
  owner_plugin_id: string | null;
  enablement: "enabled" | "disabled" | "unknown" | string;
};

export type CodexKernelProbeSnapshot = {
  schema_version: string;
  generated_at: string;
  probe_run_id: string;
  observed: {
    binary: {
      path: string | null;
      path_source: "env_override" | "which" | "wsl_default" | "runtime_status" | "unknown" | string;
      version_text: string | null;
      version_semver: string | null;
      version_parse_status: "ok" | "missing" | "unparseable" | "error" | "not_checked" | string;
      launch_descriptor: string | null;
    };
    platform: {
      execution_host: "windows" | "wsl" | "unknown" | string;
      platform_family: string | null;
      platform_os: string | null;
      wsl_distro: string | null;
    };
    runtime_roots: {
      isolated_codex_home: string | null;
      codex_home_source: "ASTRABRIDGE_CODEX_HOME" | "astrabridge_default" | "resolver" | "runtime_status" | "unknown" | string;
      project_runtime_root: string | null;
      workspace_runtime_cwd: string | null;
    };
    app_server: {
      transport: "stdio" | "websocket" | "unknown" | string;
      launch_mode: "direct" | "wsl_exec" | "reused_client" | "unknown" | string;
      available: boolean;
      initialize_status: CodexKernelProtocolStatus;
      thread_start_status: CodexKernelProtocolStatus;
      thread_resume_status: CodexKernelProtocolStatus;
      turn_start_status: CodexKernelProtocolStatus;
      approval_events_status: CodexKernelProtocolStatus;
      mcp_elicitation_status: CodexKernelProtocolStatus;
      disconnect_status: "not_observed" | "clean" | "unexpected" | "error" | "unknown" | string;
      error_shape_status: CodexKernelProtocolStatus;
      last_checked_at: string | null;
    };
    protocol_features: {
      source_kind: "runtime_only" | "generated_types_only" | "generated_types_and_runtime" | "unknown" | string;
      client_methods: Record<string, CodexKernelProtocolStatus>;
      server_notifications: Record<string, CodexKernelProtocolStatus>;
      notes: string[];
    };
    mcp_features: {
      config_render_status: CodexKernelProtocolStatus;
      config_updated_at: string | null;
      reload_status: CodexKernelProtocolStatus;
      server_status_list_status: CodexKernelProtocolStatus;
      expected_servers: string[];
      visible_servers: string[];
      expected_tools: string[];
      visible_tools: string[];
      notes: string[];
    };
    plugin_features: {
      config_feature_state: "enabled" | "disabled_by_app" | "unknown" | string;
      list_status: CodexKernelProtocolStatus;
      installed_status: CodexKernelProtocolStatus;
      read_status: CodexKernelProtocolStatus;
      install_status: CodexKernelProtocolStatus;
      uninstall_status: CodexKernelProtocolStatus;
      share_status: CodexKernelProtocolStatus;
      marketplace_status: CodexKernelProtocolStatus;
      discovered_plugins: CodexKernelPluginRecord[];
      notes: string[];
    };
    skill_features: {
      list_status: CodexKernelProtocolStatus;
      extra_roots_status: CodexKernelProtocolStatus;
      config_write_status: CodexKernelProtocolStatus;
      change_notification_status: CodexKernelProtocolStatus;
      discovered_roots: string[];
      discovered_skills: CodexKernelSkillRecord[];
      notes: string[];
    };
  };
  inferred: {
    compatibility_status: CodexKernelCompatibilityStatus;
    compatibility_summary: string | null;
    kernel_upgrade_readiness: "ready" | "partial" | "blocked" | "unknown" | string;
    plugin_integration_readiness: "ready" | "partial" | "blocked_by_app_config" | "declared_not_probed" | "unknown" | string;
    skill_integration_readiness: "ready" | "partial" | "declared_not_probed" | "unknown" | string;
    risk_flags: string[];
    required_follow_up_checks: string[];
  };
  known_warnings: string[];
  evidence: {
    sources: string[];
    commands: CodexKernelProbeCommandEvidence[];
    artifacts: string[];
  };
};

export type CodexRegistrySourceKind = "official" | "curated" | "local" | "project_local" | "manual";
export type CodexRegistryInstallStatus =
  | "installed"
  | "available"
  | "update_available"
  | "incompatible"
  | "malformed"
  | "unavailable"
  | "unknown";
export type CodexRegistryEnablementStatus = "enabled" | "disabled" | "inherited" | "blocked" | "unknown";
export type CodexRegistryCompatibilityStatus = "compatible" | "warning" | "incompatible" | "unknown";
export type CodexRegistryIconProvenanceKind = "official" | "bundled_local" | "generated_fallback" | "none";
export type CodexRegistryWarningSeverity = "info" | "warning" | "error";

export type CodexRegistrySourceCatalog = {
  schema_version: string;
  source_catalog_id: string;
  kind: CodexRegistrySourceKind | string;
  display_name: string;
  description?: string | null;
  source_url?: string | null;
  source_path?: string | null;
  catalog_path?: string | null;
  catalog_version?: string | null;
  checksum_algorithm?: string | null;
  checksum_value?: string | null;
  writable: boolean;
  notes?: string[];
};

export type CodexRegistryProvenance = {
  schema_version: string;
  source_path?: string | null;
  source_url?: string | null;
  manifest_path?: string | null;
  relative_root?: string | null;
  checksum_algorithm?: string | null;
  checksum_value?: string | null;
  last_verified_at?: string | null;
  notes?: string[];
};

export type CodexRegistryIconMetadata = {
  schema_version: string;
  provenance_kind: CodexRegistryIconProvenanceKind | string;
  label?: string | null;
  asset_path?: string | null;
  asset_url?: string | null;
  mime_type?: string | null;
  checksum_algorithm?: string | null;
  checksum_value?: string | null;
  validated: boolean;
  notes?: string[];
};

export type CodexRegistryCompatibilityWarning = {
  schema_version: string;
  code: string;
  severity: CodexRegistryWarningSeverity | string;
  message: string;
  field?: string | null;
  documentation_url?: string | null;
};

export type CodexPluginRegistryRecord = {
  schema_version: string;
  record_id: string;
  plugin_id: string;
  source_catalog_id: string;
  display_name: string;
  install_status: CodexRegistryInstallStatus | string;
  enablement_status: CodexRegistryEnablementStatus | string;
  compatibility_status: CodexRegistryCompatibilityStatus | string;
  version?: string | null;
  installed_version?: string | null;
  available_version?: string | null;
  description?: string | null;
  remote_plugin_id?: string | null;
  install_root?: string | null;
  keywords?: string[];
  declared_app_ids?: string[];
  declared_hook_keys?: string[];
  declared_mcp_servers?: string[];
  permission_hints?: string[];
  provenance?: CodexRegistryProvenance | null;
  icon?: CodexRegistryIconMetadata | null;
  compatibility_warnings?: CodexRegistryCompatibilityWarning[];
  notes?: string[];
};

export type CodexSkillRegistryRecord = {
  schema_version: string;
  record_id: string;
  skill_name: string;
  source_catalog_id: string;
  display_name: string;
  install_status: CodexRegistryInstallStatus | string;
  enablement_status: CodexRegistryEnablementStatus | string;
  compatibility_status: CodexRegistryCompatibilityStatus | string;
  owner_plugin_id?: string | null;
  description?: string | null;
  short_description?: string | null;
  owning_plugin_version?: string | null;
  trigger_hints?: string[];
  permission_hints?: string[];
  provenance?: CodexRegistryProvenance | null;
  icon?: CodexRegistryIconMetadata | null;
  observed_enablement_status?: CodexRegistryEnablementStatus | string;
  global_enablement_status?: CodexRegistryEnablementStatus | string;
  project_enablement_status?: CodexRegistryEnablementStatus | string;
  effective_enablement_status?: CodexRegistryEnablementStatus | string;
  enablement_source?: string | null;
  enablement_block_reason?: string | null;
  project_override_supported?: boolean;
  global_state_path?: string | null;
  project_state_path?: string | null;
  compatibility_warnings?: CodexRegistryCompatibilityWarning[];
  notes?: string[];
};

export type CodexPluginSkillRegistrySnapshot = {
  schema_version: string;
  generated_at: string;
  source_catalogs: CodexRegistrySourceCatalog[];
  plugins: CodexPluginRegistryRecord[];
  skills: CodexSkillRegistryRecord[];
  notes?: string[];
};

export type CodexPluginInstallPlanFileEntry = {
  relative_path: string;
  path: string;
  bytes?: number | null;
};

export type CodexPluginInstallPlan = {
  schema_version: string;
  generated_at: string;
  action: "install" | "update" | "noop" | "unsupported" | string;
  status: "ready" | "unsupported" | string;
  reason: string;
  plugin: {
    record_id: string;
    plugin_id: string;
    display_name: string;
    source_catalog_id: string;
    install_status: CodexRegistryInstallStatus | string;
    enablement_status: CodexRegistryEnablementStatus | string;
    compatibility_status: CodexRegistryCompatibilityStatus | string;
  };
  source: {
    source_catalog_id: string;
    kind: CodexRegistrySourceKind | string;
    display_name: string;
    source_path?: string | null;
    source_url?: string | null;
    catalog_path?: string | null;
    writable: boolean;
  };
  versions: {
    current_version?: string | null;
    target_version?: string | null;
    installed_version?: string | null;
    available_version?: string | null;
  };
  permission_hints: string[];
  declared_app_ids?: string[];
  mcp_changes: {
    declared_servers: string[];
  };
  skill_changes: {
    declared_skills: string[];
    detected_installed_skills: string[];
  };
  files: {
    source_root?: string | null;
    target_root?: string | null;
    source_file_count: number;
    existing_target_file_count: number;
    planned_write_count: number;
    source_files: CodexPluginInstallPlanFileEntry[];
    existing_target_files: CodexPluginInstallPlanFileEntry[];
    planned_write_files: CodexPluginInstallPlanFileEntry[];
  };
  rollback_snapshot: {
    status: string;
    snapshot_id?: string | null;
    snapshot_root?: string | null;
    captured_file_count: number;
    captured_files: CodexPluginInstallPlanFileEntry[];
    notes?: string[];
  };
  warnings?: CodexRegistryCompatibilityWarning[];
  errors?: CodexRegistryCompatibilityWarning[];
  notes?: string[];
};

export type CodexPluginInstallExecution = {
  schema_version: string;
  execution_id: string;
  executed_at: string;
  status: "applied" | "noop" | "failed" | string;
  action: "install" | "update" | "noop" | "unsupported" | string;
  plugin: CodexPluginInstallPlan["plugin"];
  plan: CodexPluginInstallPlan;
  artifact_paths: {
    report_root: string;
    plan_path: string;
    events_path: string;
    result_path: string;
  };
  source: CodexPluginInstallPlan["source"];
  target_root: string;
  changes: {
    written_file_count: number;
    target_file_count: number;
  };
  rollback_snapshot: {
    status: string;
    snapshot_id?: string | null;
    snapshot_root?: string | null;
    captured_file_count?: number;
    captured_files?: CodexPluginInstallPlanFileEntry[];
    notes?: string[];
  };
  warnings?: CodexRegistryCompatibilityWarning[];
  errors?: CodexRegistryCompatibilityWarning[];
  notes?: string[];
};

export type SkillScenarioCheck = {
  label: string;
  passed: boolean;
  message: string;
};

export type SkillScenarioVerificationCommand = {
  command: string;
  cwd: string;
  exit_code?: number | null;
  summary?: string | null;
};

export type SkillScenarioCommandResult = {
  label: string;
  command: string;
  cwd: string;
  exit_code: number;
  stdout_path?: string | null;
  stderr_path?: string | null;
};

export type SkillScenarioSuggestedScreenshot = {
  kind: string;
  path: string;
  note?: string | null;
};

export type SkillScenarioReportSeed = {
  schema_version: string;
  step_id: string;
  capability: string;
  scenario_id: string;
  trigger_path: string;
  suggested_report_path: string;
  suggested_screenshots: SkillScenarioSuggestedScreenshot[];
};

export type SkillPluginCreatorScenarioExecution = {
  schema_version: string;
  execution_id: string;
  scenario_id: string;
  capability: string;
  skill_name: string;
  skill_display_name: string;
  skill_record_id?: string | null;
  started_at: string;
  completed_at: string;
  status: string;
  failure_reason?: string | null;
  input: {
    fixture_contract_path: string;
    brief_path: string;
  };
  output: {
    run_root: string;
    execution_root: string;
    plugin_root: string;
    manifest_path: string;
    marketplace_path: string;
    required_paths: string[];
  };
  artifact_paths: {
    events_path: string;
    result_path: string;
    report_seed_path: string;
  };
  verification_commands: SkillScenarioVerificationCommand[];
  command_results: SkillScenarioCommandResult[];
  checks: SkillScenarioCheck[];
  notes?: string[];
  report_seed?: SkillScenarioReportSeed | null;
};

export type IsolationAuditCheck = {
  name: string;
  ok: boolean;
  detail?: unknown;
};

export type IsolationAuditResponse = {
  ok: boolean;
  checks: IsolationAuditCheck[];
  paths: {
    project_file?: string | null;
    workspace_root?: string | null;
    astrabridge_state?: string | null;
    managed_state_roots?: Record<string, string>;
    isolated_codex_home?: string | null;
    project_runtime_root?: string | null;
    downloads_root?: string | null;
    caches_root?: string | null;
    tmp_root?: string | null;
    official_codex_config?: string | null;
    expected_appdata?: string | null;
    expected_codex_home?: string | null;
  };
  official_codex: {
    exists: boolean;
    managed_by_app: boolean;
    router_configured: boolean;
    config_sha256?: string | null;
  };
  ports: {
    sidecar?: number | null;
    router?: number | null;
    router_base_url?: string | null;
    sidecar_owner_pid?: number | null;
    sidecar_owner_status?: string | null;
  };
  sidecar?: SidecarProvenance | null;
  process_boundary: {
    app_server_running: boolean;
    codex_cli?: string | null;
    execution_host?: string | null;
    sidecar_origin?: string | null;
    sidecar_launcher_mode?: string | null;
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
  model_defaults?: Partial<RouterModelEntry>;
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
  capability_summary?: Record<string, { available?: boolean; candidate_models?: string[]; input_modalities?: string[] }>;
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
  command_execution_status?: string;
  command_execution_note?: string;
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
  source_id?: string;
  url?: string;
  source_type?: string;
  trust_level?: string;
  channel?: string;
  parser_strategy?: string;
  stale_after_days?: number;
  promotable?: boolean;
  requires_manual_review?: boolean;
  notes?: string;
};

export type MetadataSourcePromotionPolicy = {
  promotable?: boolean;
  requires_manual_review?: boolean;
  reason?: string;
};

export type MetadataProviderSourceRecord = {
  provider_id: string;
  display_name: string;
  urls: string[];
  source_status: string;
  source_type?: string;
  trust_level?: string;
  channel?: string;
  parser_strategy?: string;
  stale_after_days?: number;
  promotion_policy?: MetadataSourcePromotionPolicy;
  source_registry_schema?: string;
  source_records?: MetadataSourceRecord[];
  source_provenance?: Record<string, unknown>;
  notes?: string;
};

export type MetadataSourcesResponse = {
  providers: MetadataProviderSourceRecord[];
  updated_at: string;
  catalog_schema?: string;
  source_registry_schema?: string;
};

export type CodexModelCatalogEntry = Record<string, unknown> & {
  id: string;
  name?: string;
  model: string;
  context_window?: number;
  source_status?: string;
  catalog_version?: string | null;
  source_provenance?: Record<string, unknown>;
  recommended?: boolean;
  default_for_provider?: boolean;
  deprecated?: boolean;
  verification_notes?: string;
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
  preferred_username?: string | null;
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

export type AgenticUpdateScope =
  | "provider_metadata"
  | "provider_adapter"
  | "capability_routes"
  | "codex_kernel"
  | "plugin_skill_surface"
  | "docs_only";

export type AgenticUpdateVersionPolicy =
  | "pinned"
  | "stable"
  | "latest"
  | "deprecated_check"
  | "security_fix_only";

export type AgenticUpdateApplyMode =
  | "discover_only"
  | "proposal_only"
  | "isolated_apply"
  | "verify_candidate"
  | "promote_after_smoke";

export type AgenticUpdateApprovalPolicy = "manual_review_required" | "preapproved_discovery_only";

export type AgenticUpdateRunContract = {
  schema_version?: string;
  normalized_at?: string;
  scope: AgenticUpdateScope[];
  providers?: string[];
  models?: string[];
  version_policy: AgenticUpdateVersionPolicy;
  target_version?: string | null;
  apply_mode: AgenticUpdateApplyMode;
  allow_network: boolean;
  allow_provider_calls: boolean;
  allow_install: boolean;
  allow_code_changes: boolean;
  approval_policy: AgenticUpdateApprovalPolicy;
};

export type AgenticUpdateStartPayload = {
  run_id?: string;
  run_contract: AgenticUpdateRunContract;
  provider_sources?: Array<Record<string, unknown>>;
  fixture_sources?: Record<string, unknown>;
  kernel_source_records?: Array<Record<string, unknown>>;
  kernel_fixture_sources?: Record<string, unknown>;
  current_models?: Array<Record<string, unknown>>;
  complete_provider_snapshot?: boolean;
};

export type AgenticUpdateJobStatus = {
  schema_version: string;
  job_id: string | null;
  run_id: string | null;
  status: "idle" | "running" | "success" | "failed" | string;
  running: boolean;
  latest_job_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  run_contract?: AgenticUpdateRunContract;
  summary?: Record<string, unknown>;
  artifact_paths?: Record<string, string | null | undefined>;
  error?: string | null;
};

export type AgenticUpdateRunList = {
  schema_version: string;
  generated_at: string;
  runs: AgenticUpdateJobStatus[];
  run_count: number;
  total_known_runs: number;
  latest_job_id?: string | null;
};

export type AgenticUpdateProposal = {
  schema_version?: string;
  run_id?: string;
  created_at?: string;
  run_contract?: AgenticUpdateRunContract;
  discovery_result?: {
    sources?: Array<Record<string, unknown>>;
    findings?: Array<Record<string, unknown>>;
    warnings?: string[];
    [key: string]: unknown;
  };
  diff?: {
    status?: string;
    risk_class?: string | null;
    summary?: Record<string, unknown>;
    changes?: Array<Record<string, unknown>>;
    warnings?: string[];
    artifact_paths?: Record<string, string | null | undefined>;
    [key: string]: unknown;
  };
  validation_result?: {
    status?: string;
    gates?: Array<Record<string, unknown>>;
    evidence_paths?: string[];
    warnings?: string[];
    [key: string]: unknown;
  };
  approval_state?: {
    status?: string;
    policy?: string;
    [key: string]: unknown;
  };
  apply_manifest?: {
    changed_paths?: string[];
    warnings?: string[];
    [key: string]: unknown;
  };
  rollback_manifest?: {
    reversible?: boolean;
    steps?: Array<Record<string, unknown>>;
    evidence_paths?: string[];
    warnings?: string[];
    [key: string]: unknown;
  };
};

export type AgenticUpdateProposalResult = {
  schema_version: string;
  generated_at: string;
  run_id: string;
  run_contract: AgenticUpdateRunContract;
  summary: Record<string, unknown>;
  discovery?: {
    sources?: Array<Record<string, unknown>>;
    warnings?: string[];
    [key: string]: unknown;
  } | null;
  parser_output?: Record<string, unknown> | null;
  kernel_candidates?: Record<string, unknown> | null;
  diff?: AgenticUpdateProposal["diff"];
  proposal?: AgenticUpdateProposal;
  artifact_paths?: Record<string, string | null | undefined>;
  mutations?: Record<string, unknown>;
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
  capability_routes?: CapabilityRouteEntry[];
  latest_test?: RouterTestResult | null;
  enabled_model_count: number;
};

export type CapabilityRouteRecord = {
  capability_id: string;
  mode: "auto" | "pinned";
  provider_id?: string | null;
  model?: string | null;
  updated_at?: string;
};

export type CapabilityRouteCandidate = {
  capability_id: string;
  adapter_id: string;
  provider_id?: string | null;
  model?: string | null;
  lane_type: string;
  transport_mode: string;
  source: string;
  catalog_present?: boolean;
  default_for_provider?: boolean;
  recommended?: boolean;
  input_modalities?: string[];
  catalog_input_modalities?: string[];
  provider_default_model?: string | null;
  provider_fallback_models?: string[];
  eligibility_notes?: string[];
  model_record?: Record<string, unknown>;
};

export type CapabilityRouteEntry = {
  capability_id: string;
  display_name: string;
  lane_type: "model_backed" | "web_standalone" | string;
  transport_mode: string;
  route_mode: "auto" | "pinned" | string;
  route_record: CapabilityRouteRecord;
  resolution_status: "ok" | "standalone" | "no_capability_candidate" | string;
  resolved_candidate?: CapabilityRouteCandidate | null;
  candidates: CapabilityRouteCandidate[];
  error?: string | null;
  updated_at?: string;
};

export type CapabilitySchemaField = {
  name: string;
  value_type: string;
  required?: boolean;
  description?: string;
  repeated?: boolean;
};

export type CapabilitySchema = {
  fields: CapabilitySchemaField[];
  required_fields?: string[];
};

export type CapabilityContract = {
  schema_version: string;
  capability_id: string;
  display_name: string;
  lane_type: "model_backed" | "web_standalone" | string;
  transport_mode: "request_response" | "stream_sse" | "realtime_ws" | string;
  input_schema: CapabilitySchema;
  output_schema: CapabilitySchema;
  artifact_policy: string;
  provider_eligibility_rule: string;
  default_timeout_sec: number;
  smoke_status: string;
  notes?: string[];
};

export type CapabilityAdapterContract = {
  schema_version: string;
  adapter_id: string;
  capability_id: string;
  provider_id: string;
  model_match: string[];
  supports_streaming: boolean;
  supports_batch: boolean;
  normalization_rules: string[];
  request_builder: string;
  response_parser: string;
  artifact_persister: string;
  smoke_case_id: string;
};

export type CapabilityAvailability = {
  available: boolean;
  candidate_count: number;
  resolution_status: "ok" | "standalone" | "no_capability_candidate" | string;
  error?: string | null;
};

export type CapabilitySmokeSummary = {
  status: string;
  case_ids: string[];
  last_result?: Record<string, unknown> | null;
  evidence_refs: Array<Record<string, unknown>>;
};

export type CapabilitySmokeResult = {
  schema_version: "astrabridge-capability-smoke-result-v1" | string;
  capability_id: string;
  mode: "dry_run" | "provider" | string;
  status: "pass" | "warn" | "fail" | "provider_not_run" | string;
  provider_invoked: boolean;
  provider_requested: boolean;
  case_id: string;
  route: {
    route_mode?: string | null;
    resolution_status?: string | null;
    resolved_candidate?: CapabilityRouteCandidate | null;
    error?: string | null;
  };
  sanitized_request: Record<string, unknown>;
  sanitized_response: Record<string, unknown>;
  artifact_refs: Array<Record<string, unknown>>;
  evidence_refs: Array<Record<string, unknown>>;
  created_at: string;
};

export type CapabilitySmokeResponse = {
  smoke: CapabilitySmokeResult;
};

export type CapabilityInvokeResponse = {
  result: Record<string, unknown>;
  mcp?: Record<string, unknown>;
};

export type CapabilityArtifactSummary = {
  policy: string;
  recent_refs: Array<Record<string, unknown>>;
};

export type CapabilityArtifactRef = {
  artifact_type: string;
  path: string;
  relative_path: string;
  exists: boolean;
  mime_type: string;
  artifact_uri?: string;
  size_bytes?: number;
  digest_sha256?: string;
  lineage?: Record<string, unknown>;
};

export type CapabilityArtifactEntry = {
  artifact_id: string;
  capability_id: string;
  provider_id: string;
  model: string;
  saved_at: string;
  summary_path: string;
  relative_summary_path: string;
  artifact_refs: CapabilityArtifactRef[];
  preview: {
    kind: "image" | "audio" | "text" | "json" | string;
    text: string;
    audio_path: string;
    image_path: string;
  };
  metadata: Record<string, unknown>;
};

export type CapabilityArtifactsResponse = {
  schema_version: "astrabridge-capability-artifacts-v1" | string;
  workspace_root: string;
  artifacts: CapabilityArtifactEntry[];
  count: number;
  total_count: number;
};

export type CapabilityMcpPresetStatus = {
  server_name: "astrabridge_capabilities" | string;
  configured: boolean;
  enabled: boolean;
  runtime_visible?: boolean | null;
  tool_names: string[];
  expected_tool_names?: string[];
  missing_tool_names?: string[];
  configured_tool_count?: number;
  health_status?: "missing" | "disabled" | "partial" | "configured" | string;
  approval_modes: Record<string, string | null | undefined>;
};

export type CapabilityManagementEntry = {
  capability_id: string;
  display_name: string;
  lane_type: "model_backed" | "web_standalone" | string;
  transport_mode: "request_response" | "stream_sse" | "realtime_ws" | string;
  route: CapabilityRouteEntry;
  availability: CapabilityAvailability;
  contract: CapabilityContract;
  adapters: CapabilityAdapterContract[];
  smoke: CapabilitySmokeSummary;
  artifacts: CapabilityArtifactSummary;
};

export type CapabilityManagementResponse = {
  schema_version: "astrabridge-capability-management-v1" | string;
  capabilities: CapabilityManagementEntry[];
  routes: CapabilityRouteEntry[];
  mcp_preset: CapabilityMcpPresetStatus;
  updated_at: string;
};

export type WebToolContext = Record<string, unknown> | null;

export type WebSearchQueryInput = {
  query: string;
  max_results?: number;
  domains?: string[];
  exclude_domains?: string[];
};

export type WebSearchBatchRequest = {
  queries: WebSearchQueryInput[];
  dedupe?: boolean;
  timeout_sec?: number;
  tool_context?: WebToolContext;
};

export type WebSearchResultItem = {
  title: string;
  url: string;
  snippet: string;
  query?: string;
  query_variant?: string;
};

export type WebSearchResultsByQuery = {
  query: string;
  variant_count: number;
  result_count: number;
  results: WebSearchResultItem[];
  warning?: string;
};

export type WebSearchBatchResult = {
  tool: "astrabridge_web_search_batch" | string;
  source: string;
  query_count: number;
  result_count: number;
  results_by_query: WebSearchResultsByQuery[];
  merged_results: WebSearchResultItem[];
  warnings: string[];
  note: string;
};

export type WebResearchBriefRequest = {
  research_goal: string;
  queries?: string[];
  source_urls?: string[];
  search_top_k?: number;
  fetch_top_n?: number;
  max_chars_per_source?: number;
  timeout_sec?: number;
  tool_context?: WebToolContext;
};

export type WebResearchSource = {
  title: string;
  url: string;
  query: string;
  source_origin?: string;
  source_host?: string;
  snippet: string;
  fetch_ok: boolean;
  cache_hit?: boolean;
  excerpt: string;
  truncated: boolean;
  content_type: string;
  fetched_at?: string;
  access_date?: string;
  status_code?: number;
  warning?: string;
};

export type WebResearchFailure = {
  url: string;
  warning: string;
  source_origin?: string;
  query?: string;
  source_host?: string;
};

export type WebResearchSourcePolicy = {
  mode?: string;
  pinned_source_count?: number;
  hinted_source_count?: number;
  search_expansion?: string;
  search_result_count?: number;
  reason?: string;
};

export type WebResearchBriefResult = {
  tool: "astrabridge_web_research_brief" | string;
  research_goal: string;
  query_plan: string[];
  source_policy?: WebResearchSourcePolicy;
  fetch_summary?: {
    requested_count?: number;
    ok_count?: number;
    failed_count?: number;
    cache_hit_count?: number;
  };
  evidence_kind?: string;
  conclusion_status?: string;
  conclusion_note?: string;
  search: {
    query_count?: number;
    result_count?: number;
    warnings: string[];
  };
  sources: WebResearchSource[];
  source_count: number;
  fetched_source_count: number;
  failures: WebResearchFailure[];
  brief: unknown;
  unresolved_questions: string[];
  suggested_followup_queries: string[];
  citation_rule: string;
};

export type WebFetchRequest = {
  url: string;
  max_chars?: number;
  timeout_sec?: number;
  tool_context?: WebToolContext;
};

export type WebFetchResult = {
  tool: "astrabridge_web_fetch" | string;
  url: string;
  source_host?: string;
  content_type: string;
  text: string;
  truncated: boolean;
  char_count: number;
  cache_hit?: boolean;
  fetched_at?: string;
  access_date?: string;
  status_code?: number;
};

export type WebToolResponse<T> = {
  ok: boolean;
  record_id: string;
  tool_event_verified: boolean;
  tool_context: WebToolContext;
  path: string;
  mcp?: Record<string, unknown>;
  result: T;
};

export type WebSearchBatchResponse = WebToolResponse<WebSearchBatchResult>;
export type WebResearchBriefResponse = WebToolResponse<WebResearchBriefResult>;
export type WebFetchResponse = WebToolResponse<WebFetchResult>;

export type AutomationPermissionMode = "read-only" | "workspace-write" | "full-access";
export type AutomationKind = "standalone" | "thread";
export type AutomationScheduleMode = "manual" | "interval" | "daily";
export type AutomationExecutionHost = "windows" | "wsl" | "auto";
export type AutomationWorkspaceMode = "current_workspace" | "dedicated_worktree";
export type AutomationCleanupPolicy = "keep_on_finding" | "keep_on_failure" | "delete_on_no_signal" | "manual";
export type AutomationNotifyOn = "finding" | "failure" | "every_run";
export type AutomationInboxState = "unread" | "reviewed" | "archived" | "promoted";
export type AutomationRunStatus = "queued" | "running" | "needs_review" | "completed" | "failed" | "skipped" | "cancelled";
export type AutomationSignal = "finding" | "no_signal" | "unknown";

export type AutomationSpec = {
  schema_version: string;
  automation_id: string;
  project_id: string;
  name: string;
  description: string;
  enabled: boolean;
  kind: AutomationKind;
  prompt: string;
  schedule: {
    mode: AutomationScheduleMode;
    expression: string;
    timezone: string;
    next_run_at: string;
    catch_up_policy: "skip_missed" | "run_once";
  };
  runtime: {
    profile_id?: string | null;
    model?: string | null;
    effort?: string | null;
    permission_mode: AutomationPermissionMode;
    collaboration_mode?: string | null;
    execution_host: AutomationExecutionHost;
    mcp_preset_ids: string[];
    plugin_skill_preset_ids?: string[];
    dangerous_opt_in?: boolean;
    prompt_snapshot?: Record<string, unknown>;
  };
  workspace: {
    mode: AutomationWorkspaceMode;
    base_branch?: string | null;
    worktree_root?: string | null;
    cleanup_policy: AutomationCleanupPolicy;
  };
  triage: {
    archive_no_signal: boolean;
    notify_on: AutomationNotifyOn;
    finding_keywords: string[];
  };
  limits: {
    timeout_sec: number;
    max_retries: number;
    max_artifact_bytes: number;
    max_parallel_runs: number;
  };
  created_at: string;
  updated_at: string;
  last_run_at?: string | null;
  last_status?: string | null;
  archived_at?: string | null;
  archived_reason?: string | null;
  inbox_summary?: {
    unread: number;
    reviewed: number;
    archived: number;
    promoted: number;
  };
};

export type AutomationRun = {
  schema_version?: string;
  run_id: string;
  automation_id: string;
  project_id: string;
  trigger: "schedule" | "manual" | "retry";
  status: AutomationRunStatus;
  due_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  thread_id?: string | null;
  turn_id?: string | null;
  worktree_path?: string | null;
  runtime_profile_id?: string | null;
  exit_code?: number | null;
  signal: AutomationSignal;
  summary: string;
  artifact_refs: string[];
  redacted_error?: string | null;
  next_retry_at?: string | null;
  stdout_excerpt?: string | null;
  stderr_excerpt?: string | null;
  diff_excerpt?: string | null;
  watchdog_reason?: string | null;
  watchdog_summary?: string | null;
  recovered_by?: string | null;
  recovered_at?: string | null;
};

export type AutomationInboxItem = {
  schema_version?: string;
  item_id: string;
  run_id: string;
  automation_id: string;
  project_id: string;
  state: AutomationInboxState;
  disposition: "finding" | "no_signal" | "failure" | "approval_required";
  severity: "info" | "warning" | "error";
  title: string;
  summary: string;
  created_at: string;
  updated_at: string;
  promotion_ref?: string | null;
};

export type AutomationListResponse = {
  automations: AutomationSpec[];
  count: number;
};

export type AutomationRunsResponse = {
  runs: AutomationRun[];
  count: number;
};

export type AutomationInboxResponse = {
  items: AutomationInboxItem[];
  count: number;
};

export type AutomationSchedulerStatus = {
  running: boolean;
  active_run_count: number;
  next_wake_up_at?: string | null;
  active_runs?: Array<{
    run_id: string;
    automation_id: string;
    status: AutomationRunStatus;
    due_at?: string | null;
  }>;
  last_failure?: AutomationRun | null;
  next_due?: { automation_id?: string; name?: string; next_run_at?: string | null } | null;
  inbox_summary?: { unread: number; reviewed: number; archived: number; promoted: number };
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

export type BrowserWorkbenchSession = {
  id: string;
  role: string;
  title: string;
  url: string;
  status: string;
  error?: string | null;
  page_title?: string;
  preview_mode?: "remote" | "native" | "external" | "web_fallback" | string;
  supervision_status?: "starting" | "ready" | "unavailable" | "error" | string;
  supervision_session_id?: string;
  supervision_error?: string | null;
  viewport_width?: number;
  viewport_height?: number;
  layout_mode?: "desktop" | "mobile" | string;
  layout_reason?: string;
  mobile_optimized?: boolean | null;
  has_viewport_meta?: boolean | null;
  horizontal_overflow_ratio?: number | null;
  wide_element_count?: number | null;
  mobile_strategy?: "desktop_viewport" | "mobile_user_agent_viewport" | "mobile_host_rewrite_viewport" | string;
  responsive_fit_score?: number | null;
  can_go_back?: boolean;
  can_go_forward?: boolean;
  loading?: boolean;
  screenshot_path?: string;
  updated_at?: string;
};

export type BrowserWorkbenchCreateRequest = {
  id?: string;
  role?: string;
  url: string;
  layout_mode?: "desktop" | "mobile";
  layout_reason?: string;
};

export type BrowserWorkbenchNavigateRequest = {
  id: string;
  url: string;
  layout_mode?: "desktop" | "mobile";
  layout_reason?: string;
};

export type BrowserWorkbenchLayoutRequest = {
  id: string;
  layout_mode: "desktop" | "mobile";
  layout_reason?: string;
};

export type ComputerUseBrowserScenarioReport = {
  schema_version: string;
  scenario_id: string;
  scenario: string;
  generated_at: string;
  status: string;
  artifact_path: string;
  browser_targets: Array<Record<string, unknown>>;
  app_server_plugin_gate?: Record<string, unknown>;
  attempts?: Array<Record<string, unknown>>;
  model_comparison?: Record<string, unknown>;
  notes?: string[];
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
  observability?: {
    schema_version: string;
    generated_at: string;
    source: {
      runtime_event_count: number;
      host_event_count: number;
      graph_event_count: number;
      merged_event_count: number;
      event_stream: string;
      host_lineage: string;
      ui_source: string;
    };
    trace_lineage?: {
      trace_id?: string | null;
      run_id?: string | null;
      thread_id?: string | null;
      latest_at?: string | null;
      domain_sequence?: string[];
      complete?: boolean;
      steps?: Array<{
        timestamp?: string | null;
        source?: string | null;
        domain?: string | null;
        event_type?: string | null;
        summary?: string | null;
        node_id?: string | null;
        operation_id?: string | null;
        artifact_id?: string | null;
      }>;
    } | null;
    metrics?: Array<{
      metric_id: string;
      label: string;
      value?: number | null;
      unit: string;
      sample_size: number;
      numerator?: number | null;
      denominator?: number | null;
      distribution?: {
        count?: number | null;
        p95?: number | null;
        max?: number | null;
      } | null;
      status: "pass" | "warning" | "fail" | "unknown" | string;
      otel_mapping?: {
        instrument?: string;
        kind?: string;
        semantic_bridge?: string;
        attributes?: string[];
      } | null;
    }>;
    slos?: Array<{
      metric_id: string;
      status: string;
      good_threshold: number;
      warn_threshold: number;
      unit: string;
      release_gate: boolean;
    }>;
    domain_counts?: Array<{
      domain: string;
      count: number;
      error_count: number;
      warning_count: number;
    }>;
    recent_diagnostics?: Array<{
      schema_version?: string;
      domain: string;
      severity: string;
      event_type: string;
      summary: string;
      timestamp: string;
      trace_id?: string | null;
      run_id?: string | null;
      node_id?: string | null;
      operation_id?: string | null;
    }>;
  } | null;
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
  automations?: {
    scheduler: AutomationSchedulerStatus;
    active_runs: Array<{
      run_id: string;
      automation_id: string;
      status: AutomationRunStatus;
      due_at?: string | null;
    }>;
    last_failure?: AutomationRun | null;
    next_due?: { automation_id?: string; name?: string; next_run_at?: string | null } | null;
    inbox_summary: { unread: number; reviewed: number; archived: number; promoted: number };
  };
};

export type ProjectReviewFile = {
  path: string;
  status: string;
  updated_at?: number | string | null;
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
  profile_id?: string;
  provider_id?: string;
  model_id?: string;
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
  kind: "text" | "markdown" | "json" | "image" | "pdf" | "audio" | "video" | "binary" | string;
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
  kind: "text" | "markdown" | "json" | "image" | "pdf" | "audio" | "video" | "binary" | "too_large" | string;
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
  thread_id?: string | null;
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
  lane_state?: ProjectTask["lane_state"];
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
  kind: "image" | "file" | "folder";
  previewUrl?: string;
  size?: number;
  source?: "local_path" | "browser_upload" | "drop" | "staged";
  relativePath?: string;
  fileCount?: number;
  error?: string;
};

export type AttachmentStageFile = {
  name: string;
  mime_type?: string;
  data_base64: string;
  relative_path?: string;
  size?: number;
};

export type AttachmentStageSkipped = {
  name: string;
  reason: string;
};

export type AttachmentStageResponse = {
  attachments: AttachmentDraft[];
  skipped: AttachmentStageSkipped[];
};

export type AttachmentDiagnostics = {
  total_count?: number;
  image_count?: number;
  file_count?: number;
  folder_count?: number;
  total_size?: number;
  items?: Array<{
    name?: string;
    kind?: string;
    mime_type?: string;
    extension?: string;
    source?: string;
    size?: number;
  }>;
  route?: {
    provider_id?: string;
    model_id?: string;
    context_mode?: string;
    text_items?: number;
    local_image_items?: number;
    mention_items?: number;
  };
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
  | "web"
  | "browser"
  | "command"
  | "file_change"
  | "file_edit"
  | "multimodal"
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

export type RuntimeActivityEntry = {
  id: string;
  kind: RuntimeActivityKind;
  status: "active" | "completed" | "failed" | "pending" | string;
  label: string;
  preview?: string;
  detail?: string;
  files?: string[];
  diff?: RuntimeDiffSummary;
  toolName?: string;
  startedAt?: number | null;
  completedAt?: number | null;
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
export type ThreadCreateRecoveryResponse = Partial<ThreadReadResponse> & {
  operation_id: string;
  status: "pending" | "completed" | "failed";
  retry_after_ms?: number | null;
  error?: string;
  warning?: string;
};
export type TaskConversationResponse = { thread: ShellThread; task?: ProjectTask; transcript_path?: string; updated_at?: string };
export type ThreadListResponse = { threads: ShellThread[]; next_cursor: string | null; backwards_cursor: string | null };
export type TurnStartResponse = {
  turn: { id: string; status: string };
  thread_id?: string;
  handoff?: ProjectTaskHandoffEvent | null;
  project?: ProjectFile;
  task?: ProjectTask;
  background_start?: boolean;
  warning?: string;
  attachment_diagnostics?: AttachmentDiagnostics;
};
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


