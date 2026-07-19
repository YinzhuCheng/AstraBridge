import { expect, test, type Page, type Route } from "@playwright/test";

const NOW = "2026-07-17T08:00:00Z";
const PROJECT_ID = "project-provider-updates";
const TASK_ID = "task-provider-updates";
const THREAD_ID = "thread-provider-updates";
const GRAPH_ID = "graph-provider-update-gate";
const RUN_ID = "run-provider-update-gate";

function buildProject() {
  return {
    schema_version: "astrabridge-project-v1",
    project_id: PROJECT_ID,
    name: "Provider Update Stability",
    project_file: "D:/AstraBridge/PRIVATE/provider-update-stability.abproj",
    workspace_root: "D:/AstraBridge",
    entry_mode: "existing",
    default_profile_id: "profile-qwen",
    default_model: "qwen3-coder-plus",
    default_effort: "medium",
    current_thread_id: THREAD_ID,
    current_task_id: TASK_ID,
    recent_threads: [THREAD_ID],
    recent_tasks: [TASK_ID],
    ui_preferences: {
      locale: "en",
      left_sidebar_open: true,
      right_sidebar_open: true,
    },
    created_at: NOW,
    updated_at: NOW,
  };
}

function buildGraph() {
  return {
    schema_version: "astrabridge-task-graph-v1",
    graph_id: GRAPH_ID,
    task_id: TASK_ID,
    title: "Provider Update / Smoke / Gate",
    template_id: "provider_update_smoke_gate",
    status: "active",
    nodes: [
      {
        node_id: "node_discover",
        graph_id: GRAPH_ID,
        kind: "extractor",
        label: "Discover",
        agent_card_ref: "agent-discover",
        execution_policy: {},
        output_contract: {},
        position: { x: 120, y: 180 },
        status: "ready",
        provider_id: "qwen",
        model_id: "qwen3-coder-plus",
        reasoning_effort: "medium",
        permission_mode: "default",
        collaboration_mode: "structured_handoff",
        execution_backend: "app_server",
      },
      {
        node_id: "node_smoke",
        graph_id: GRAPH_ID,
        kind: "validator",
        label: "Smoke",
        agent_card_ref: "agent-smoke",
        execution_policy: {},
        output_contract: {},
        position: { x: 390, y: 180 },
        status: "ready",
        provider_id: "qwen",
        model_id: "qwen3-coder-plus",
        reasoning_effort: "medium",
        permission_mode: "default",
        collaboration_mode: "structured_handoff",
        execution_backend: "app_server",
      },
      {
        node_id: "node_gate",
        graph_id: GRAPH_ID,
        kind: "gate",
        label: "Promote",
        agent_card_ref: "agent-gate",
        execution_policy: {},
        output_contract: {},
        position: { x: 660, y: 180 },
        status: "waiting_approval",
        execution_backend: "app_server",
        approval_gate: {
          review_kind: "provider_promotion",
        },
      },
    ],
    edges: [
      {
        edge_id: "edge-discover-smoke",
        graph_id: GRAPH_ID,
        from_node_id: "node_discover",
        to_node_id: "node_smoke",
        edge_type: "artifact_handoff",
        status: "ready",
        context_policy: {
          policy_id: "context-discover-smoke",
          history_mode: "last_turn_only",
          artifact_mode: "explicit_only",
          exclude_private_memory: true,
          include_machine_results: true,
          include_human_summaries: true,
        },
      },
      {
        edge_id: "edge-smoke-gate",
        graph_id: GRAPH_ID,
        from_node_id: "node_smoke",
        to_node_id: "node_gate",
        edge_type: "approval_gate",
        status: "ready",
        handoff_contract: {
          message_template: "Summarize the smoke results and request approval.",
          message_part_modes: ["machine_result", "human_summary"],
        },
        context_policy: {
          policy_id: "context-smoke-gate",
          history_mode: "last_turn_only",
          artifact_mode: "explicit_only",
          exclude_private_memory: true,
          include_machine_results: true,
          include_human_summaries: true,
        },
      },
    ],
    graph_policy: {
      entry_node_ids: ["node_discover"],
    },
    graph_document: {
      source_ownership: {
        ownership_mode: "detached",
        can_write_from_gui: true,
      },
    },
    created_at: NOW,
    updated_at: NOW,
    state_version: 3,
  };
}

function buildRunRef(status: "approval_required" | "completed", approvalStatus: "pending" | "approved") {
  return {
    run_id: RUN_ID,
    graph_id: GRAPH_ID,
    task_id: TASK_ID,
    status,
    created_at: NOW,
    updated_at: NOW,
    entry_node_ids: ["node_discover"],
    node_status_counts: {
      completed: approvalStatus === "approved" ? 3 : 2,
      waiting_approval: approvalStatus === "approved" ? 0 : 1,
    },
    node_outcome_counts: {
      passed: approvalStatus === "approved" ? 3 : 2,
      pending: approvalStatus === "approved" ? 0 : 1,
    },
    artifact_count: 2,
    event_count: approvalStatus === "approved" ? 4 : 3,
    approval_state: approvalStatus,
    approval_details: {
      status: approvalStatus,
      review_kind: "provider_promotion",
      node_id: "node_gate",
      reason: "Promote only after the smoke matrix passes.",
      requested_at: NOW,
      resolved_at: approvalStatus === "approved" ? NOW : null,
      decision: approvalStatus === "approved" ? "approve" : null,
      notes: approvalStatus === "approved" ? "Approved in deterministic Playwright E2E." : null,
      resolution_summary: approvalStatus === "approved" ? "Approval recorded and the promotion gate closed." : null,
      allowed_actions: approvalStatus === "approved" ? [] : ["approve", "reject"],
      blocked_actions: [],
    },
    latest_event_type: approvalStatus === "approved" ? "approval_resolved" : "approval_requested",
    latest_event_at: NOW,
    timeline_events: [
      {
        event_id: "event-discover",
        event_type: "node_completed",
        created_at: NOW,
        summary: "Discover lane finished provider metadata collection.",
        node_id: "node_discover",
        status: "completed",
      },
      {
        event_id: "event-smoke",
        event_type: "node_completed",
        created_at: NOW,
        summary: "Smoke lane validated the provider bundle.",
        node_id: "node_smoke",
        status: "completed",
      },
      {
        event_id: "event-gate",
        event_type: approvalStatus === "approved" ? "approval_resolved" : "approval_requested",
        created_at: NOW,
        summary: approvalStatus === "approved" ? "Promotion approval recorded." : "Promotion is waiting for human approval.",
        node_id: "node_gate",
        status: approvalStatus,
      },
    ],
    artifact_refs: [
      {
        artifact_id: "artifact-smoke-report",
        artifact_kind: "markdown",
        path: "PRIVATE/provider-smoke/report.md",
        status: "ready",
        label: "Smoke report",
      },
    ],
    diagnostic_refs: [
      {
        artifact_id: "artifact-health-matrix",
        artifact_kind: "json",
        path: "PRIVATE/provider-smoke/health-matrix.json",
        status: "ready",
        label: "Health matrix",
      },
    ],
    policy_snapshot: {
      mode: "approval_gate",
      scheduler: "deterministic_fixture",
      template_id: "provider_update_smoke_gate",
      execution_mode: "fixture_run",
      max_parallelism: 2,
      parallel_group_count: 2,
      budget: {
        graph: {
          limits: { total_tokens: 20000 },
          observed: { total_tokens: approvalStatus === "approved" ? 1600 : 1200 },
        },
      },
    },
    metrics: {
      status: approvalStatus === "approved" ? "completed" : "waiting_approval",
      elapsed_ms: 1800,
      artifact_count: 2,
      event_count: approvalStatus === "approved" ? 4 : 3,
      approval_count: approvalStatus === "approved" ? 1 : 0,
      provider_call_count: 2,
      tool_call_count: 1,
      token_usage: {
        total_tokens: approvalStatus === "approved" ? 1600 : 1200,
        input_tokens: 800,
        output_tokens: 400,
        reasoning_tokens: 400,
      },
      cost: {
        currency: "USD",
        total_cost: 0.12,
      },
    },
    budget: {
      graph: {
        limits: { total_tokens: 20000 },
        observed: { total_tokens: approvalStatus === "approved" ? 1600 : 1200 },
      },
    },
    worker_count: 2,
    worker_bindings: [
      {
        node_id: "node_discover",
        label: "Discover",
        worker_thread_id: "worker-discover",
        status: "completed",
      },
      {
        node_id: "node_smoke",
        label: "Smoke",
        worker_thread_id: "worker-smoke",
        status: "completed",
      },
    ],
  };
}

function buildTask(runRef: ReturnType<typeof buildRunRef>) {
  return {
    schema_version: "astrabridge-project-task-v1",
    task_id: TASK_ID,
    project_id: PROJECT_ID,
    title: "Provider update stability gate",
    status: "active",
    handoff_policy: "multi_provider_handoff",
    active_provider_thread_id: THREAD_ID,
    provider_threads: [
      {
        thread_id: THREAD_ID,
        role: "provider",
        profile_id: "profile-qwen",
        provider_id: "qwen",
        model: "qwen3-coder-plus",
        reasoning_effort: "medium",
        permission_mode: "default",
        collaboration_mode: "structured_handoff",
        name: "Qwen provider lane",
        created_at: NOW,
        updated_at: NOW,
      },
    ],
    handoff_events: [],
    graph_definitions: [buildGraph()],
    graph_run_refs: [runRef],
    graph_snapshot_refs: [],
    graph_activity_summary: {
      graph_id: GRAPH_ID,
      latest_run_id: RUN_ID,
      latest_run_status: runRef.status,
    },
    created_at: NOW,
    updated_at: NOW,
  };
}

function buildThread() {
  return {
    id: THREAD_ID,
    created_at: NOW,
    updated_at: NOW,
    createdAt: NOW,
    updatedAt: NOW,
    name: "Qwen provider lane",
    displayName: "Qwen provider lane",
    preview: "Promotion gate is waiting for approval.",
    status: "idle",
    turns: [],
    shellSettings: {
      profile_id: "profile-qwen",
      model: "qwen3-coder-plus",
      reasoning_effort: "medium",
      permission_mode: "default",
      collaboration_mode: "structured_handoff",
      execution_backend: "app_server",
    },
    task_id: TASK_ID,
    active_provider_thread_id: THREAD_ID,
    provider_threads: [
      {
        thread_id: THREAD_ID,
        profile_id: "profile-qwen",
        provider_id: "qwen",
        model: "qwen3-coder-plus",
        reasoning_effort: "medium",
      },
    ],
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installApiFixtures(page: Page) {
  const project = buildProject();
  const graph = buildGraph();
  const thread = buildThread();
  let latestRunRef = buildRunRef("approval_required", "pending");
  let currentTask = buildTask(latestRunRef);
  const recentProjects = {
    projects: [
      {
        project_id: PROJECT_ID,
        name: project.name,
        project_file: project.project_file,
        workspace_root: project.workspace_root,
        entry_mode: project.entry_mode,
        updated_at: NOW,
      },
    ],
  };
  const runtimeEnvironment = {
    execution_host: "windows",
    workspace_root: "D:/AstraBridge",
    runtime_config: {
      base_url: "http://127.0.0.1:8852",
      secret_loaded: true,
    },
    sidecar: {
      base_url: "http://127.0.0.1:8852",
      status: "ready",
    },
    router: {
      providers: [
        {
          provider_id: "qwen",
          display_name: "Qwen",
          secret_loaded: true,
          status: "ready",
        },
      ],
    },
  };
  const runtimeSupervisorState = {
    thread_id: THREAD_ID,
    updated_at: NOW,
    plan: null,
    token: {
      total_tokens: 1200,
      context_window: 131072,
      context_percent: 1,
      turn_id: null,
      last_updated_at: NOW,
    },
    guard: {
      level: "ok",
      recommended_action: "none",
      should_pause: false,
      message: "",
    },
    watchdog: {
      level: "ok",
      idle_seconds: 0,
      recommended_action: "none",
      message: "",
      turn_id: null,
    },
    thread_status: {
      type: "idle",
      activeFlags: [],
    },
    runtime_error: null,
    environment: {
      project_name: project.name,
      cwd: "D:/AstraBridge",
      provider: "qwen",
      model: "qwen3-coder-plus",
      effort: "medium",
      permission: "default",
      git: {
        is_repo: true,
        branch: "main",
        changed_files: 0,
        added: 0,
        deleted: 0,
      },
      mcp: {
        status: "listed",
        count: 0,
        last_updated_at: NOW,
      },
    },
    browser: {
      status: "pass",
      created_at: NOW,
    },
    observability: null,
    dogfood: {
      enabled: false,
      phase: "idle",
      status: "idle",
      current_provider: "qwen",
      next_step: "none",
      usage: {},
      budgets: {},
      latest_milestone: null,
    },
    modal: {
      pending_count: 0,
      current: null,
    },
    automations: {
      scheduler: {
        status: "idle",
        next_run_at: null,
        now: NOW,
      },
      active_runs: [],
      last_failure: null,
      next_due: null,
      inbox_summary: {
        unread: 0,
        reviewed: 0,
        archived: 0,
        promoted: 0,
      },
    },
  };

  await page.addInitScript(() => {
    class FakeEventSource {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSED = 2;
      readonly url: string;
      readonly withCredentials = false;
      readyState = FakeEventSource.OPEN;
      onerror: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent<string>) => void) | null = null;
      onopen: ((event: Event) => void) | null = null;

      constructor(url: string) {
        this.url = url;
      }

      addEventListener() {}
      removeEventListener() {}
      dispatchEvent() {
        return true;
      }
      close() {
        this.readyState = FakeEventSource.CLOSED;
      }
    }

    Object.defineProperty(window, "EventSource", {
      configurable: true,
      writable: true,
      value: FakeEventSource,
    });
  });

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.startsWith("/__astrabridge_proxy__/")
      ? url.pathname.slice("/__astrabridge_proxy__".length)
      : url.pathname;

    if (path === "/health") {
      await fulfillJson(route, {
        ok: true,
        service: "astrabridge-sidecar",
        runtime: runtimeEnvironment,
        router: runtimeEnvironment.router,
      });
      return;
    }

    if (!path.startsWith("/api/")) {
      await route.continue();
      return;
    }

    if (path === "/api/projects/current") {
      await fulfillJson(route, { project });
      return;
    }

    if (path === "/api/projects/recent") {
      await fulfillJson(route, recentProjects);
      return;
    }

    if (path === "/api/projects/sidebar") {
      await fulfillJson(route, {
        schema_version: "astrabridge-sidebar-v1",
        projects: [
          {
            project_id: PROJECT_ID,
            name: project.name,
            project_file: project.project_file,
            workspace_root: project.workspace_root,
            updated_at: NOW,
            is_current: true,
            tasks: [
              {
                task_id: TASK_ID,
                title: currentTask.title,
                status: currentTask.status,
                updated_at: NOW,
                is_current: true,
                active_provider_thread_id: THREAD_ID,
                threads: [
                  {
                    id: THREAD_ID,
                    displayName: "Qwen provider lane",
                    preview: "Promotion gate is waiting for approval.",
                    shellSettings: {
                      model: "qwen3-coder-plus",
                      reasoning_effort: "medium",
                    },
                  },
                ],
                provider_id: "qwen",
                model: "qwen3-coder-plus",
                reasoning_effort: "medium",
                lane_count: 1,
                handoff_count: 0,
                project_file: project.project_file,
              },
            ],
          },
        ],
        updated_at: NOW,
      });
      return;
    }

    if (path === "/api/admin/session") {
      await fulfillJson(route, {
        admin_session_token: "playwright-admin-session-token",
      });
      return;
    }

    if (path === "/api/project/tasks") {
      await fulfillJson(route, {
        schema_version: "astrabridge-project-tasks-v1",
        current_task: currentTask,
        tasks: [currentTask],
        updated_at: NOW,
      });
      return;
    }

    if (path === "/api/project/task-conversation") {
      await fulfillJson(route, {
        thread,
        task: currentTask,
        updated_at: NOW,
      });
      return;
    }

    if (path === "/api/task-graphs/templates") {
      await fulfillJson(route, {
        schema_version: "astrabridge-task-graph-templates-v1",
        templates: [
          {
            template_id: "provider_update_smoke_gate",
            title: "Provider Update / Smoke / Gate",
            summary: "Metadata discovery, smoke validation, and promotion gate.",
            node_count: 3,
            edge_count: 2,
            entry_node_ids: ["node_discover"],
            node_kinds: ["extractor", "validator", "gate"],
            recommended_provider_ids: ["qwen"],
            recommended_model_ids: ["qwen3-coder-plus"],
            preview_graph: {
              title: "Provider Update / Smoke / Gate",
              nodes: graph.nodes.map((node) => ({
                node_id: node.node_id,
                kind: node.kind,
                label: node.label,
                position: node.position,
              })),
              edges: graph.edges.map((edge) => ({
                edge_id: edge.edge_id,
                from_node_id: edge.from_node_id,
                to_node_id: edge.to_node_id,
                edge_type: edge.edge_type,
              })),
            },
          },
        ],
      });
      return;
    }

    if (path === "/api/task-graphs/node-types") {
      await fulfillJson(route, {
        schema_version: "astrabridge-node-type-registry-v1",
        registry_fingerprint: "playwright-deterministic-fixture",
        role_ids: ["extractor", "validator", "gate"],
        kind_aliases: {
          extractor: "agent_model",
          validator: "agent_model",
          gate: "human_approval",
        },
        node_types: [
          {
            type_id: "agent_model",
            version: 1,
            category: "agent",
            title: "Agent / Model",
            description: "Provider-backed task lane.",
            config_schema: {
              type: "object",
              properties: {},
            },
            typed_ports: { inputs: [], outputs: [] },
            compiler_executor_id: "agent_lane",
            default_policy: {},
            ui_hints: {
              palette_role: "custom",
              palette_sections: ["planning"],
              palette_variants: [
                { kind: "extractor", label: "Extractor", description: "Collect metadata." },
                { kind: "validator", label: "Validator", description: "Run smoke validation." },
              ],
            },
          },
          {
            type_id: "human_approval",
            version: 1,
            category: "control",
            title: "Human approval",
            description: "Manual gate before promotion.",
            config_schema: {
              type: "object",
              properties: {},
            },
            typed_ports: { inputs: [], outputs: [] },
            compiler_executor_id: "approval_lane",
            default_policy: {},
            ui_hints: {
              palette_role: "gate",
              palette_sections: ["control"],
              palette_variants: [{ kind: "gate", label: "Gate", description: "Approval gate." }],
            },
          },
        ],
      });
      return;
    }

    if (path === "/api/task-graphs/graph") {
      await fulfillJson(route, {
        graph,
        task: currentTask,
      });
      return;
    }

    if (path === "/api/task-graphs/approval/resolve" && request.method() === "POST") {
      latestRunRef = buildRunRef("completed", "approved");
      currentTask = buildTask(latestRunRef);
      await fulfillJson(route, {
        approval: {
          decision: "approve",
          resolved_at: NOW,
        },
        run_ref: latestRunRef,
        graph,
        task: currentTask,
      });
      return;
    }

    if (path === "/api/profiles") {
      await fulfillJson(route, {
        profiles: [
          {
            profile_id: "profile-qwen",
            label: "Qwen default",
            type: "provider",
            provider_id: "qwen",
            model: "qwen3-coder-plus",
            reasoning_effort: "medium",
          },
        ],
      });
      return;
    }

    if (path === "/api/router/config") {
      await fulfillJson(route, {
        providers: [
          {
            id: "provider-qwen",
            provider_id: "qwen",
            display_name: "Qwen",
            enabled: true,
            adapter_type: "openai_compatible",
            base_url: "https://example.invalid/qwen",
            default_model: "qwen3-coder-plus",
            request_timeout_ms: 60000,
            stream_idle_timeout_ms: 60000,
            env_key: "QWEN_API_KEY",
            auth_mode: "env_ref",
            proxy_mode: "direct",
            proxy_url: "",
            supported_reasoning_levels: ["low", "medium", "high"],
            default_reasoning_level: "medium",
            input_modalities: ["text"],
            supports_search_tool: true,
            supports_mcp_tools: true,
          },
        ],
        models: [
          {
            id: "qwen3-coder-plus",
            provider: "qwen",
            native_model: "qwen3-coder-plus",
            display_name: "Qwen3 Coder Plus",
            enabled: true,
            advertised_context_window: 131072,
            ui_context_hint_only: false,
            adapter_profile: "default",
            supported_reasoning_levels: ["low", "medium", "high"],
            default_reasoning_level: "medium",
            input_modalities: ["text"],
          },
        ],
        reasoning: {
          effort_options: ["low", "medium", "high"],
          default_effort: "medium",
        },
        enabled_model_count: 1,
      });
      return;
    }

    if (path === "/api/runtime/environment") {
      await fulfillJson(route, runtimeEnvironment);
      return;
    }

    if (path === "/api/runtime/threads") {
      await fulfillJson(route, {
        threads: [thread],
        next_cursor: null,
        backwards_cursor: null,
      });
      return;
    }

    if (path === "/api/runtime/thread") {
      await fulfillJson(route, {
        thread,
        task: currentTask,
        project,
      });
      return;
    }

    if (path === "/api/runtime/modals") {
      await fulfillJson(route, { modals: [] });
      return;
    }

    if (path === "/api/runtime/events") {
      await fulfillJson(route, {
        cursor: 0,
        events: [],
      });
      return;
    }

    if (path === "/api/runtime/supervisor/status") {
      await fulfillJson(route, runtimeSupervisorState);
      return;
    }

    if (path === "/api/runtime/plugin-skill-registry") {
      await fulfillJson(route, {
        schema_version: "astrabridge-plugin-skill-registry-v1",
        records: [],
        plugins: [],
        skills: [],
        updated_at: NOW,
      });
      return;
    }

    if (path === "/api/runtime/kernel-probe") {
      await fulfillJson(route, {
        status: "ready",
        inferred: {
          compatibility_status: "compatible",
        },
      });
      return;
    }

    if (path === "/api/router/status") {
      await fulfillJson(route, runtimeEnvironment.router);
      return;
    }

    if (path === "/api/llm-manager/session") {
      await fulfillJson(route, {
        mode: "anonymous",
        authenticated: false,
        profile: null,
        users: [],
      });
      return;
    }

    if (path === "/api/llm-manager/catalog/effective") {
      await fulfillJson(route, {
        providers: [],
        models: [],
        verified_model_ids: [],
      });
      return;
    }

    if (path === "/api/llm-manager/keys") {
      await fulfillJson(route, {
        keys: [],
      });
      return;
    }

    if (path === "/api/llm-manager/health/results") {
      await fulfillJson(route, {
        results: [],
      });
      return;
    }

    if (path === "/api/router/metadata/sources") {
      await fulfillJson(route, {
        sources: [],
        updated_at: NOW,
      });
      return;
    }

    if (path === "/api/router/mcp/config") {
      await fulfillJson(route, {
        servers: [],
        environment: {
          node: process.execPath,
          npx: "npx",
          python: "python",
        },
      });
      return;
    }

    if (path === "/api/dogfood/run") {
      await fulfillJson(route, {
        run: null,
      });
      return;
    }

    if (path === "/api/dogfood/assets") {
      await fulfillJson(route, {
        registry: {
          assets: [],
          summary: {},
        },
        context_pack: {
          approved_unpromoted: [],
          promoted: [],
          needs_review: [],
        },
      });
      return;
    }

    if (path === "/api/project/saves") {
      await fulfillJson(route, {
        saves: [],
        workspace_root: "D:/AstraBridge",
        updated_at: NOW,
      });
      return;
    }

    if (path === "/api/automations") {
      await fulfillJson(route, {
        automations: [],
      });
      return;
    }

    if (path === "/api/automations/runs") {
      await fulfillJson(route, {
        runs: [],
        scheduler: null,
        items: [],
      });
      return;
    }

    if (path === "/api/automations/inbox") {
      await fulfillJson(route, {
        items: [],
        summary: {
          unread: 0,
          reviewed: 0,
          archived: 0,
          promoted: 0,
        },
      });
      return;
    }

    if (path === "/api/automations/scheduler/status") {
      await fulfillJson(route, {
        scheduler: {
          status: "idle",
          next_run_at: null,
          now: NOW,
        },
      });
      return;
    }

    if (path === "/api/runtime/capability-routes") {
      await fulfillJson(route, {
        routes: [],
        updated_at: NOW,
      });
      return;
    }

    if (path === "/api/runtime/capability-management") {
      await fulfillJson(route, {
        capabilities: [],
        providers: [],
        updated_at: NOW,
      });
      return;
    }

    if (path === "/api/runtime/mcp/servers") {
      await fulfillJson(route, {
        servers: [],
        next_cursor: null,
      });
      return;
    }

    if (path === "/api/runtime/models") {
      await fulfillJson(route, {
        models: [{ id: "qwen3-coder-plus", name: "Qwen3 Coder Plus" }],
        next_cursor: null,
      });
      return;
    }

    if (path === "/api/goal") {
      await fulfillJson(route, {
        goal: null,
      });
      return;
    }

    if (path === "/api/admin/session/ensure") {
      await fulfillJson(route, { ok: true });
      return;
    }

    await fulfillJson(route, {});
  });
}

test("task graph workspace supports deterministic inspection and approval review flow", async ({ page }) => {
  const taskGraphToggle = page.getByRole("button", { name: /Task graph|任务图/ });
  page.on("pageerror", (error) => {
    console.log(`[pageerror] ${error.stack || error.message}`);
  });
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      console.log(`[browser:${message.type()}] ${message.text()}`);
    }
  });
  await installApiFixtures(page);
  await page.goto("/?astrabridge_launch=playwright-e2e");

  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30000 });
  await expect(taskGraphToggle).toBeVisible({ timeout: 15000 });
  await taskGraphToggle.click();

  await expect(page.getByTestId("task-graph-workspace")).toBeVisible();
  await expect(page.getByTestId("task-graph-node-node_discover")).toBeVisible();
  await expect(page.getByTestId("task-graph-node-node_gate")).toBeVisible();

  await page.getByTestId("task-graph-node-node_discover").click();
  await expect(page.getByTestId("task-graph-inspector")).toBeVisible();
  await expect(page.getByTestId("task-graph-inspector-workspace-selection")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("task-graph-inspector-label")).toHaveValue("Discover");
  await expect(page.getByTestId("task-graph-inspector-provider")).toHaveValue("qwen");
  await page.getByTestId("task-graph-inspector-close").click();
  await expect(page.getByTestId("task-graph-inspector")).toBeHidden();

  await page.getByTestId("task-graph-open-run-inspection").click();
  await expect(page.getByTestId("task-graph-inspector")).toBeVisible();
  await expect(page.getByTestId("task-graph-inspector-workspace-run")).toHaveAttribute("aria-selected", "true");
  const latestRunPanel = page.getByTestId("task-graph-run-panel");
  await expect(latestRunPanel).toBeVisible();
  if (!(await latestRunPanel.evaluate((element) => element.hasAttribute("open")))) {
    await latestRunPanel.locator("summary").first().click();
  }
  await expect(page.getByTestId("task-graph-approval-panel")).toBeVisible();
  await expect(page.getByTestId("task-graph-approval-approve")).toBeVisible();
  await expect(page.getByTestId("task-graph-run-timeline")).toContainText("Promotion is waiting for human approval.");

  await page.getByTestId("task-graph-approval-approve").click();

  await expect(page.getByTestId("task-graph-approval-approve")).toBeHidden();
  await expect(page.getByTestId("task-graph-approval-resolution")).toContainText("Approval recorded and the promotion gate closed.");
  await expect(page.getByTestId("task-graph-run-timeline")).toContainText("Promotion approval recorded.");
});
