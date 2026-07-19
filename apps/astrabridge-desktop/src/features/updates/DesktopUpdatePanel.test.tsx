import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  DesktopUpdateRehearsalResult,
  DesktopUpdateStatus,
  ProjectFile,
} from "../../types";
import { DesktopUpdatePanel } from "./DesktopUpdatePanel";

afterEach(() => cleanup());

const project: ProjectFile = {
  schema_version: "astrabridge-project-v1",
  project_id: "project-1",
  name: "AstraBridge",
  project_file: "D:\\AstraBridge\\demo.abproj",
  workspace_root: "D:\\AstraBridge",
  entry_mode: "existing",
  default_profile_id: "openai-compatible",
  default_model: "gpt-5",
  default_effort: "high",
  current_thread_id: null,
  recent_threads: [],
  ui_preferences: {
    locale: "en",
    appearance: "codex",
    execution_host: "windows",
    wsl_distro: "",
    update_channel: "beta",
  },
  created_at: "2026-07-18T00:00:00Z",
  updated_at: "2026-07-18T00:00:00Z",
};

const statusPayload: DesktopUpdateStatus = {
  schema_version: "astrabridge-desktop-update-status-v1",
  generated_at: "2026-07-18T01:00:00Z",
  release_version: "0.1.0",
  selected_channel: "beta",
  default_channel: "stable",
  channels: [
    {
      channel: "stable",
      manifest_path: "release/updater/stable.json",
      endpoint: "https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}",
      rollout: "general_availability",
      selected: false,
      default: true,
    },
    {
      channel: "beta",
      manifest_path: "release/updater/beta.json",
      endpoint: "https://updates.astrabridge.app/beta/{{target}}/{{arch}}/{{current_version}}",
      rollout: "release_candidate",
      selected: true,
      default: false,
    },
    {
      channel: "canary",
      manifest_path: "release/updater/canary.json",
      endpoint: "https://updates.astrabridge.app/canary/{{target}}/{{arch}}/{{current_version}}",
      rollout: "internal_preview",
      selected: false,
      default: false,
    },
  ],
  selected_endpoint: "https://updates.astrabridge.app/beta/{{target}}/{{arch}}/{{current_version}}",
  updater_contract_status: "pass",
  kill_switch: {
    manifest_path: "release/updater/kill-switch.json",
    source_path: "D:\\AstraBridge\\release\\updater\\kill-switch.json",
    loaded_from_disk: false,
    default_mode: "allow",
    active_mode: "allow",
    allow_disable_updates: true,
    updates_enabled: true,
  },
  formal_bundle: {
    status: "ready",
    resource_path: "release/desktop-sidecar/windows-x64/astrabridge-sidecar",
    launcher_path: "D:\\AstraBridge\\release\\desktop-sidecar\\windows-x64\\astrabridge-sidecar\\python-runtime\\python.exe",
    bundle_manifest_path: "D:\\AstraBridge\\release\\desktop-sidecar\\windows-x64\\astrabridge-sidecar\\bundle-manifest.json",
    bundle_manifest_exists: true,
    launcher_exists: true,
    package_root: "D:\\AstraBridge\\release\\desktop-sidecar\\windows-x64\\astrabridge-sidecar\\astrabridge_sidecar",
    package_root_exists: true,
    skills_root: "D:\\AstraBridge\\release\\desktop-sidecar\\windows-x64\\astrabridge-sidecar\\skills",
    skills_root_exists: true,
  },
  tauri_runtime: {
    schema_version: "tauri-v2-updater-plugin-config",
    create_updater_artifacts: true,
    pubkey: "untrusted",
    endpoints: ["https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}"],
    dangerous_insecure_transport_protocol: false,
    dangerous_accept_invalid_certs: false,
    dangerous_accept_invalid_hostnames: false,
    windows_install_mode: "passive",
    default_channel: "stable",
  },
  latest_rehearsal: {
    status: "pass",
    run_id: "windows-update-rehearsal-stable",
    selected_channel: "stable",
    created_at: "2026-07-18T01:30:00Z",
    summary_json: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-stable\\windows-update-rehearsal\\summary.json",
    report_md: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-stable\\windows-update-rehearsal\\report.md",
    run_root: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-stable",
  },
  warnings: [],
  project_update_channel: "beta",
};

const rehearsalPayload: DesktopUpdateRehearsalResult = {
  schema_version: "astrabridge-windows-update-rehearsal-v1",
  run_id: "windows-update-rehearsal-beta",
  created_at: "2026-07-18T02:00:00Z",
  status: "pass",
  release_version: "0.1.0",
  selected_channel: "beta",
  default_channel: "stable",
  kill_switch: statusPayload.kill_switch,
  updater_contract_status: "pass",
  release_readiness_run_root: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta",
  release_readiness_summary_json: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta\\reports\\summary.json",
  clean_install_check: {
    status: "pass",
    staged_bundle_root: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta\\stages\\stage-a\\workspace\\release\\desktop-sidecar\\windows-x64\\astrabridge-sidecar",
    bundle_manifest_path: "bundle-manifest.json",
    launcher_path: "python-runtime\\python.exe",
    package_root: "astrabridge_sidecar",
    skills_root: "skills",
    selected_channel_manifest_path: "release\\updater\\beta.json",
    kill_switch_manifest_path: "release\\updater\\kill-switch.json",
    selected_channel_manifest_sha256: "abc",
    kill_switch_manifest_sha256: "def",
    bundle_manifest_sha256: "ghi",
    checks: {
      bundle_manifest_exists: true,
      launcher_exists: true,
      package_root_exists: true,
      skills_root_exists: true,
      channel_manifest_exists: true,
      kill_switch_manifest_exists: true,
    },
    notes: [],
  },
  update_check: {
    status: "pass",
    selected_channel: "beta",
    selected_endpoint: statusPayload.selected_endpoint,
    kill_switch_mode: "allow",
    updates_enabled: true,
    channel_manifest_path: "release\\updater\\beta.json",
    channel_manifest_sha256: "123",
    activation_journal_path: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta\\windows-update-rehearsal\\reports\\activation-journal.json",
  },
  rollback_check: {
    status: "pass",
    current_pointer_path: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta\\windows-update-rehearsal\\isolated-install-root\\current-generation.json",
    rollback_generation_id: "generation-0000-prior",
    rollback_entry_manifest_path: "prior-manifest.json",
    rollback_entry_manifest_sha256: "456",
  },
  artifact_paths: {
    run_root: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta",
    rehearsal_root: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta\\windows-update-rehearsal",
    summary_json: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta\\windows-update-rehearsal\\summary.json",
    report_md: "D:\\AstraBridge\\PRIVATE\\release-readiness\\windows-update-rehearsal-beta\\windows-update-rehearsal\\report.md",
    activation_journal_json: "activation-journal.json",
    current_pointer_json: "current-generation.json",
    prior_generation_manifest_json: "prior-manifest.json",
    candidate_generation_manifest_json: "candidate-manifest.json",
  },
  errors: [],
};

function renderPanel(overrides?: {
  status?: ReturnType<typeof vi.fn>;
  saveChannel?: ReturnType<typeof vi.fn>;
  rehearsal?: ReturnType<typeof vi.fn>;
  onProjectUpdated?: ReturnType<typeof vi.fn>;
}) {
  const status = overrides?.status ?? vi.fn(async () => statusPayload);
  const saveChannel = overrides?.saveChannel ?? vi.fn(async (channel: string) => ({
    project: {
      ...project,
      ui_preferences: {
        ...project.ui_preferences,
        update_channel: channel as ProjectFile["ui_preferences"]["update_channel"],
      },
    },
  }));
  const rehearsal = overrides?.rehearsal ?? vi.fn(async () => rehearsalPayload);
  const onProjectUpdated = overrides?.onProjectUpdated ?? vi.fn();
  render(
    <DesktopUpdatePanel
      locale="en"
      project={project}
      onProjectUpdated={onProjectUpdated}
      api={{ status, saveChannel, rehearsal }}
    />,
  );
  return { status, saveChannel, rehearsal, onProjectUpdated };
}

describe("DesktopUpdatePanel", () => {
  it("renders selected channel, kill-switch state, and latest rehearsal metadata", async () => {
    renderPanel();

    expect(await screen.findByText("Desktop channels and isolated rehearsal")).toBeInTheDocument();
    expect(screen.getByDisplayValue("beta")).toBeInTheDocument();
    expect(screen.getByText("https://updates.astrabridge.app/beta/{{target}}/{{arch}}/{{current_version}}")).toBeInTheDocument();
    expect(screen.getAllByText("allow")[0]).toBeInTheDocument();
    expect(screen.getByText("windows-update-rehearsal-stable")).toBeInTheDocument();
  });

  it("persists an explicit channel selection through project preferences", async () => {
    const user = userEvent.setup();
    const { saveChannel, onProjectUpdated } = renderPanel();

    await screen.findByText("Desktop channels and isolated rehearsal");
    await user.selectOptions(screen.getByTestId("desktop-update-channel"), "canary");

    await waitFor(() => expect(saveChannel).toHaveBeenCalledWith("canary"));
    expect(onProjectUpdated).toHaveBeenCalledTimes(1);
  });

  it("runs the isolated rehearsal and renders pass/fail checks", async () => {
    const user = userEvent.setup();
    const { rehearsal } = renderPanel();

    await screen.findByText("Desktop channels and isolated rehearsal");
    await user.click(screen.getByTestId("desktop-update-run-rehearsal"));

    await waitFor(() => expect(rehearsal).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("windows-update-rehearsal-beta")).toBeInTheDocument();
    expect(screen.getByText("Clean install check")).toBeInTheDocument();
    expect(screen.getAllByText("pass").length).toBeGreaterThan(2);
  });
});
