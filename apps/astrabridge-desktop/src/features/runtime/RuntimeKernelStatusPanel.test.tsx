import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CodexKernelProbeSnapshot } from "../../types";
import { RuntimeKernelStatusPanel } from "./RuntimeKernelStatusPanel";

type DeepPartial<T> = {
  [K in keyof T]?: T[K] extends Array<infer _U>
    ? T[K]
    : T[K] extends object
      ? DeepPartial<T[K]>
      : T[K];
};

function makeSnapshot(
  patch: DeepPartial<CodexKernelProbeSnapshot> = {},
): CodexKernelProbeSnapshot {
  const observed = (patch.observed ?? {}) as DeepPartial<CodexKernelProbeSnapshot["observed"]>;
  const inferred = (patch.inferred ?? {}) as DeepPartial<CodexKernelProbeSnapshot["inferred"]>;
  const evidence = (patch.evidence ?? {}) as DeepPartial<CodexKernelProbeSnapshot["evidence"]>;
  const protocolFeaturesPatch = (observed.protocol_features ?? {}) as DeepPartial<CodexKernelProbeSnapshot["observed"]["protocol_features"]>;
  const {
    client_methods: protocolClientMethods,
    server_notifications: protocolServerNotifications,
    ...protocolFeaturesRest
  } = protocolFeaturesPatch as DeepPartial<CodexKernelProbeSnapshot["observed"]["protocol_features"]> & {
    client_methods?: Record<string, string>;
    server_notifications?: Record<string, string>;
  };
  return {
    schema_version: "codex-kernel-probe-v1",
    generated_at: "2026-06-25T12:00:00+08:00",
    probe_run_id: "codex-kernel-probe-test",
    observed: {
      binary: {
        path: "D:/Tools/OpenAI/Codex/bin/codex.EXE",
        path_source: "which",
        version_text: "codex-cli 0.137.0",
        version_semver: "0.137.0",
        version_parse_status: "ok",
        launch_descriptor: "D:/Tools/OpenAI/Codex/bin/codex.EXE",
        ...(observed.binary ?? {}),
      },
      platform: {
        execution_host: "windows",
        platform_family: "windows",
        platform_os: "windows",
        wsl_distro: null,
        ...(observed.platform ?? {}),
      },
      runtime_roots: {
        isolated_codex_home: "D:/AstraBridge/.astrabridge/codex-home",
        codex_home_source: "resolver",
        project_runtime_root: "D:/AstraBridge/.astrabridge/runtime",
        workspace_runtime_cwd: "D:/AstraBridge/.astrabridge/runtime-cwd",
        ...(observed.runtime_roots ?? {}),
      },
      app_server: {
        transport: "stdio",
        launch_mode: "reused_client",
        available: true,
        initialize_status: "supported",
        thread_start_status: "not_checked",
        thread_resume_status: "not_checked",
        turn_start_status: "not_checked",
        approval_events_status: "not_checked",
        mcp_elicitation_status: "not_checked",
        disconnect_status: "not_observed",
        error_shape_status: "not_checked",
        last_checked_at: "2026-06-25T12:00:00+08:00",
        ...(observed.app_server ?? {}),
      },
      protocol_features: {
        ...protocolFeaturesRest,
        source_kind: protocolFeaturesRest.source_kind ?? "generated_types_only",
        client_methods: { ...(protocolClientMethods ?? {}) },
        server_notifications: { ...(protocolServerNotifications ?? {}) },
        notes: protocolFeaturesRest.notes ?? [],
      },
      mcp_features: {
        config_render_status: "supported",
        config_updated_at: "2026-06-25T11:00:00+08:00",
        reload_status: "supported",
        server_status_list_status: "supported",
        expected_servers: ["astrabridge_capabilities"],
        visible_servers: ["astrabridge_capabilities"],
        expected_tools: ["astrabridge_capability_routes"],
        visible_tools: ["astrabridge_capability_routes"],
        notes: [],
        ...(observed.mcp_features ?? {}),
      },
      plugin_features: {
        config_feature_state: "enabled",
        list_status: "supported",
        installed_status: "supported",
        read_status: "supported",
        install_status: "declared",
        uninstall_status: "declared",
        share_status: "declared",
        marketplace_status: "supported",
        discovered_plugins: [],
        notes: [],
        ...(observed.plugin_features ?? {}),
      },
      skill_features: {
        list_status: "supported",
        extra_roots_status: "declared",
        config_write_status: "declared",
        change_notification_status: "declared",
        discovered_roots: ["D:/AstraBridge/.astrabridge/skills"],
        discovered_skills: [],
        notes: [],
        ...(observed.skill_features ?? {}),
      },
    },
    inferred: {
      compatibility_status: "verified",
      compatibility_summary: "This kernel is verified.",
      kernel_upgrade_readiness: "ready",
      plugin_integration_readiness: "ready",
      skill_integration_readiness: "ready",
      risk_flags: [],
      required_follow_up_checks: [],
      ...inferred,
    },
    known_warnings: patch.known_warnings ?? [],
    evidence: {
      sources: [],
      commands: [],
      artifacts: [],
      ...evidence,
    },
  };
}

describe("RuntimeKernelStatusPanel", () => {
  afterEach(() => cleanup());

  it("renders a verified baseline snapshot", () => {
    render(<RuntimeKernelStatusPanel locale="en" snapshot={makeSnapshot()} isLoading={false} />);

    expect(screen.getByText("Codex kernel compatibility")).toBeInTheDocument();
    expect(screen.getAllByText("verified").length).toBeGreaterThan(0);
    expect(screen.getByText("D:/Tools/OpenAI/Codex/bin/codex.EXE")).toBeInTheDocument();
    expect(screen.getAllByText("0.137.0").length).toBeGreaterThan(0);
    expect(screen.getByText("Isolated home")).toBeInTheDocument();
    expect(screen.getByText("Compatibility: verified")).toBeInTheDocument();
    expect(screen.getByText("App-server: supported")).toBeInTheDocument();
    expect(screen.getByText("MCP: supported")).toBeInTheDocument();
    expect(screen.getByText("Plugins: supported")).toBeInTheDocument();
    expect(screen.getByText("Skills: supported")).toBeInTheDocument();
    expect(screen.getByText("No probe warnings.")).toBeInTheDocument();
  });

  it("renders an unknown newer version without claiming verification", () => {
    render(
      <RuntimeKernelStatusPanel
        locale="en"
        snapshot={makeSnapshot({
          observed: { binary: { version_text: "codex-cli 0.200.0", version_semver: "0.200.0" } },
          inferred: {
            compatibility_status: "unknown",
            compatibility_summary: "AstraBridge has not yet classified this newer kernel.",
            kernel_upgrade_readiness: "unknown",
          },
        })}
        isLoading={false}
      />,
    );

    expect(screen.getByText("Compatibility: unknown")).toBeInTheDocument();
    expect(screen.getAllByText("0.200.0").length).toBeGreaterThan(0);
    expect(screen.getByText("AstraBridge has not yet classified this newer kernel.")).toBeInTheDocument();
  });

  it("renders a missing binary as not detected", () => {
    render(
      <RuntimeKernelStatusPanel
        locale="en"
        snapshot={makeSnapshot({
          observed: {
            binary: {
              path: null,
              version_text: null,
              version_semver: null,
              version_parse_status: "missing",
              launch_descriptor: null,
            },
          },
          inferred: {
            compatibility_status: "blocked",
            compatibility_summary: "Codex binary is missing for the active runtime lane.",
            kernel_upgrade_readiness: "blocked",
          },
        })}
        isLoading={false}
      />,
    );

    expect(screen.getByText("Codex binary is missing for the active runtime lane.")).toBeInTheDocument();
    expect(screen.getAllByText("not detected").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Compatibility: blocked")).toBeInTheDocument();
  });

  it("renders incompatible probe states and surfaced warnings", () => {
    render(
      <RuntimeKernelStatusPanel
        locale="en"
        snapshot={makeSnapshot({
          observed: {
            app_server: { initialize_status: "unsupported", available: false, transport: "websocket", launch_mode: "wsl_exec" },
            mcp_features: { server_status_list_status: "error", config_render_status: "supported" },
            plugin_features: { config_feature_state: "disabled_by_app", list_status: "unsupported" },
            skill_features: { list_status: "error" },
          },
          inferred: {
            compatibility_status: "partial",
            compatibility_summary: "The kernel is reachable, but multiple probe surfaces are incompatible.",
            plugin_integration_readiness: "blocked_by_app_config",
            skill_integration_readiness: "unknown",
          },
          known_warnings: ["rendered_config_disables_plugins", "kernel_probe_app_server_initialize_jsonrpc:-32601"],
        })}
        isLoading={false}
      />,
    );

    expect(screen.getByText("App-server: unsupported")).toBeInTheDocument();
    expect(screen.getByText("MCP: error")).toBeInTheDocument();
    expect(screen.getByText("Plugins: disabled by app")).toBeInTheDocument();
    expect(screen.getByText("Skills: error")).toBeInTheDocument();
    expect(screen.getByText("rendered_config_disables_plugins")).toBeInTheDocument();
    expect(screen.getByText("kernel_probe_app_server_initialize_jsonrpc:-32601")).toBeInTheDocument();
  });
});
