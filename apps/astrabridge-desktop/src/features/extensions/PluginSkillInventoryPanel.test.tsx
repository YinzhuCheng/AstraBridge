import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CodexPluginSkillRegistrySnapshot, ProjectFile } from "../../types";
import { api } from "../../api";
import { PluginSkillInventoryPanel } from "./PluginSkillInventoryPanel";

vi.mock("../../api", () => ({
  api: {
    updateProjectPluginSkillPresets: vi.fn(),
    runtimeSkillEnablementUpdate: vi.fn(),
    runtimePluginInstallPlan: vi.fn(),
    runtimePluginInstallApply: vi.fn(),
    runtimeSkillPluginCreatorFixtureScenario: vi.fn(),
    projectFileRead: vi.fn(),
  },
}));

const project: ProjectFile = {
  schema_version: "astrabridge-project-v1",
  project_id: "demo-project",
  name: "Demo project",
  project_file: "D:/AstraBridge/PRIVATE/demo.abproj",
  workspace_root: "D:/AstraBridge/workspace",
  entry_mode: "existing",
  default_profile_id: "openai-compatible",
  default_model: "gpt-5.5",
  default_effort: "high",
  current_thread_id: null,
  recent_threads: [],
  current_task_id: null,
  recent_tasks: [],
  plugin_skill_presets: {
    schema_version: "astrabridge-project-plugin-skill-presets-v1",
    active_preset_id: "project-default",
    presets: [
      {
        preset_id: "project-default",
        display_name: "Project default",
        plugin_refs: [],
        skill_refs: [],
        updated_at: "2026-06-25T20:40:00+08:00",
      },
    ],
    updated_at: "2026-06-25T20:40:00+08:00",
  },
  ui_preferences: {
    locale: "en",
    appearance: "codex",
    execution_host: "windows",
    left_sidebar_width: 300,
    right_sidebar_width: 340,
    right_sidebar_open: true,
  },
  created_at: "2026-06-25T20:40:00+08:00",
  updated_at: "2026-06-25T20:40:00+08:00",
};

const snapshot: CodexPluginSkillRegistrySnapshot = {
  schema_version: "astrabridge-plugin-skill-registry-v1",
  generated_at: "2026-06-25T18:00:00+08:00",
  source_catalogs: [
    {
      schema_version: "astrabridge-plugin-skill-registry-v1",
      source_catalog_id: "official::github",
      kind: "official",
      display_name: "Official GitHub catalog",
      writable: false,
      source_url: "https://github.com/openai",
    },
    {
      schema_version: "astrabridge-plugin-skill-registry-v1",
      source_catalog_id: "local::legacy",
      kind: "local",
      display_name: "Legacy local catalog",
      writable: true,
      source_path: "D:/AstraBridge/.astrabridge/codex-home/plugins",
    },
  ],
  plugins: [
    {
      schema_version: "astrabridge-plugin-skill-registry-v1",
      record_id: "plugin:github",
      plugin_id: "github",
      source_catalog_id: "official::github",
      display_name: "GitHub",
      install_status: "installed",
      enablement_status: "enabled",
      compatibility_status: "compatible",
      version: "0.1.5",
      description: "Official GitHub plugin.",
      permission_hints: ["declares_mcp_servers", "tool_search"],
      declared_app_ids: ["github"],
      declared_hook_keys: ["review_comments"],
      declared_mcp_servers: ["github"],
      provenance: {
        schema_version: "astrabridge-plugin-skill-registry-v1",
        manifest_path: "D:/AstraBridge/.astrabridge/codex-home/plugins/github/.codex-plugin/plugin.json",
      },
      compatibility_warnings: [],
      notes: ["catalog:official"],
    },
    {
      schema_version: "astrabridge-plugin-skill-registry-v1",
      record_id: "plugin:legacy",
      plugin_id: "legacy-helper",
      source_catalog_id: "local::legacy",
      display_name: "Legacy Helper",
      install_status: "available",
      enablement_status: "disabled",
      compatibility_status: "warning",
      version: "0.0.9",
      description: "Legacy local helper plugin.",
      permission_hints: ["filesystem_write"],
      declared_app_ids: [],
      declared_hook_keys: [],
      declared_mcp_servers: [],
      provenance: {
        schema_version: "astrabridge-plugin-skill-registry-v1",
        manifest_path: "D:/AstraBridge/.astrabridge/codex-home/plugins/legacy-helper/.codex-plugin/plugin.json",
      },
      compatibility_warnings: [
        {
          schema_version: "astrabridge-plugin-skill-registry-v1",
          code: "legacy-kernel-warning",
          severity: "warning",
          message: "Legacy plugin has not been revalidated on the current kernel.",
        },
      ],
      notes: ["local_marketplace"],
    },
  ],
  skills: [
    {
      schema_version: "astrabridge-plugin-skill-registry-v1",
      record_id: "skill:github:address-comments",
      skill_name: "github:gh-address-comments",
      source_catalog_id: "official::github",
      display_name: "Address comments",
      install_status: "installed",
      enablement_status: "enabled",
      compatibility_status: "warning",
      owner_plugin_id: "github",
      description: "Legacy pull request review helper.",
      short_description: "Address actionable pull request review comments.",
      trigger_hints: ["pull request review"],
      permission_hints: ["tool_search"],
      observed_enablement_status: "enabled",
      global_enablement_status: "enabled",
      project_enablement_status: "inherited",
      effective_enablement_status: "enabled",
      enablement_source: "runtime_observed",
      project_override_supported: true,
      global_state_path: "D:/AstraBridge/.astrabridge/codex-home/astrabridge-managed/skill-enablement.global.json",
      project_state_path: "D:/AstraBridge/workspace/.astrabridge/extensions/skill-enablement.json",
      provenance: {
        schema_version: "astrabridge-plugin-skill-registry-v1",
        source_path: "D:/AstraBridge/.astrabridge/codex-home/plugins/github/skills/gh-address-comments/SKILL.md",
      },
      compatibility_warnings: [
        {
          schema_version: "astrabridge-plugin-skill-registry-v1",
          code: "skill-revalidation-pending",
          severity: "warning",
          message: "Skill metadata still needs kernel-line validation.",
        },
      ],
      notes: ["plugin_owned"],
    },
  ],
  notes: ["plugin_list_status:supported", "skill_list_status:supported"],
};

const snapshotWithPluginCreator: CodexPluginSkillRegistrySnapshot = {
  ...snapshot,
  skills: [
    ...snapshot.skills,
    {
      schema_version: "astrabridge-plugin-skill-registry-v1",
      record_id: "skill:system:plugin-creator",
      skill_name: "plugin-creator",
      source_catalog_id: "local::legacy",
      display_name: "Plugin Creator",
      install_status: "installed",
      enablement_status: "enabled",
      compatibility_status: "compatible",
      owner_plugin_id: null,
      description: "Scaffold a controlled plugin fixture from a fixed brief.",
      short_description: "Generate a deterministic plugin scaffold for dogfood validation.",
      trigger_hints: ["plugin scaffold", "fixture plugin"],
      permission_hints: ["filesystem_write"],
      observed_enablement_status: "enabled",
      global_enablement_status: "enabled",
      project_enablement_status: "inherited",
      effective_enablement_status: "enabled",
      enablement_source: "runtime_observed",
      project_override_supported: true,
      global_state_path: "D:/AstraBridge/.astrabridge/codex-home/astrabridge-managed/skill-enablement.global.json",
      project_state_path: "D:/AstraBridge/workspace/.astrabridge/extensions/skill-enablement.json",
      provenance: {
        schema_version: "astrabridge-plugin-skill-registry-v1",
        source_path: "C:/Users/cyz19/.codex/skills/.system/plugin-creator/SKILL.md",
      },
      compatibility_warnings: [],
      notes: ["system_skill"],
    },
  ],
};

describe("PluginSkillInventoryPanel", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    vi.mocked(api.updateProjectPluginSkillPresets).mockReset();
    vi.mocked(api.runtimeSkillEnablementUpdate).mockReset();
    vi.mocked(api.runtimePluginInstallPlan).mockReset();
    vi.mocked(api.runtimePluginInstallApply).mockReset();
    vi.mocked(api.runtimeSkillPluginCreatorFixtureScenario).mockReset();
    vi.mocked(api.projectFileRead).mockReset();
  });

  it("renders inventory counts and opens skill details", () => {
    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} />);

    expect(screen.getByText("Extensions")).toBeInTheDocument();
    expect(screen.getByTestId("extensions-summary-plugins")).toHaveTextContent("Plugins");
    expect(screen.getByTestId("extensions-summary-plugins")).toHaveTextContent("2");
    expect(screen.getByTestId("extensions-summary-sources")).toHaveTextContent("2");

    fireEvent.click(screen.getByRole("button", { name: /Address comments/i }));

    expect(screen.getAllByText("Owning plugin").length).toBeGreaterThan(0);
    expect(screen.getAllByText("github").length).toBeGreaterThan(0);
    expect(screen.getAllByText("pull request review").length).toBeGreaterThan(0);
    expect(screen.getAllByText("tool_search").length).toBeGreaterThan(0);
    expect(screen.getByText("Skill controls")).toBeInTheDocument();
  });

  it("shows plugin-focused inventory state with controlled install guidance", () => {
    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} initialKind="plugins" />);

    expect(screen.getByRole("heading", { name: "Plugins" })).toBeInTheDocument();
    expect(screen.getByTestId("extensions-summary-installed")).toHaveTextContent("1");
    expect(screen.getByTestId("extensions-summary-available")).toHaveTextContent("1");
    expect(screen.getByTestId("extensions-summary-attention")).toHaveTextContent("1");

    fireEvent.click(screen.getByRole("button", { name: /Legacy Helper/i }));

    expect(screen.getByText("Operation guidance")).toBeInTheDocument();
    expect(screen.getByText("All plugin writes stay inside AstraBridge-managed isolated runtime roots and evidence directories.")).toBeInTheDocument();
    expect(screen.getByText("This plugin is ready to install from an AstraBridge-managed local source. Applying the plan copies files into the isolated runtime and records rollback evidence.")).toBeInTheDocument();
    expect(screen.getAllByText("Contributions").length).toBeGreaterThan(0);
  });

  it("filters inventory by search, type, and status", () => {
    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} />);

    fireEvent.change(screen.getByLabelText("Search inventory"), { target: { value: "legacy" } });
    fireEvent.click(screen.getByRole("button", { name: "Skills" }));
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "attention" } });

    expect(screen.getByRole("button", { name: /Address comments/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Legacy Helper/i })).not.toBeInTheDocument();
  });

  it("shows unsupported-kernel inventory state clearly", () => {
    render(
      <PluginSkillInventoryPanel
        locale="en"
        snapshot={{
          schema_version: "astrabridge-plugin-skill-registry-v1",
          generated_at: "2026-06-25T18:00:00+08:00",
          source_catalogs: [],
          plugins: [],
          skills: [],
          notes: ["plugin_list_status:unsupported", "skill_list_status:unsupported"],
        }}
        isLoading={false}
      />,
    );

    expect(screen.getByText("Kernel does not expose plugin or skill inventory on this runtime yet.")).toBeInTheDocument();
    expect(screen.getAllByText("Plugin list: unsupported").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Skill list: unsupported").length).toBeGreaterThan(0);
  });

  it("rerenders from loading to loaded inventory without hook-order errors", () => {
    const { rerender } = render(<PluginSkillInventoryPanel locale="en" snapshot={null} isLoading project={project} />);

    expect(screen.getByText("Loading plugin and skill inventory...")).toBeInTheDocument();

    rerender(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} project={project} />);

    expect(screen.getByText("Project default")).toBeInTheDocument();
    expect(screen.getAllByText("Address comments").length).toBeGreaterThan(0);
  });

  it("falls back to text badges for local icon asset paths in web preview", () => {
    const snapshotWithLocalIcon: CodexPluginSkillRegistrySnapshot = {
      ...snapshot,
      skills: snapshot.skills.map((skill) => ({
        ...skill,
        icon: {
          schema_version: "astrabridge-plugin-skill-registry-v1",
          provenance_kind: "bundled_local",
          validated: true,
          label: "AC",
          asset_path: "D:/AstraBridge/PRIVATE/demo/icon.png",
        },
      })),
    };

    const { container } = render(<PluginSkillInventoryPanel locale="en" snapshot={snapshotWithLocalIcon} isLoading={false} />);

    expect(container.querySelector('img[alt="Address comments icon"]')).toBeNull();
    expect(screen.getAllByText("AC").length).toBeGreaterThan(0);
  });

  it("loads and renders a plugin install plan preview", async () => {
    vi.mocked(api.runtimePluginInstallPlan).mockResolvedValue({
      schema_version: "astrabridge-plugin-install-plan-v1",
      generated_at: "2026-06-25T19:00:00+08:00",
      action: "install",
      status: "ready",
      reason: "install_available_plugin",
      plugin: {
        record_id: "plugin:legacy",
        plugin_id: "legacy-helper",
        display_name: "Legacy Helper",
        source_catalog_id: "local::legacy",
        install_status: "available",
        enablement_status: "disabled",
        compatibility_status: "warning",
      },
      source: {
        source_catalog_id: "local::legacy",
        kind: "local",
        display_name: "Legacy local catalog",
        source_path: "D:/AstraBridge/.astrabridge/codex-home/marketplace/legacy-helper",
        source_url: "https://example.com/plugin.zip?token=[REDACTED]",
        writable: true,
      },
      versions: {
        current_version: null,
        target_version: "0.0.9",
        installed_version: null,
        available_version: "0.0.9",
      },
      permission_hints: ["filesystem_write"],
      declared_app_ids: ["legacy-app"],
      mcp_changes: {
        declared_servers: ["legacy-mcp"],
      },
      skill_changes: {
        declared_skills: ["legacy:helper"],
        detected_installed_skills: [],
      },
      files: {
        source_root: "D:/AstraBridge/.astrabridge/codex-home/marketplace/legacy-helper",
        target_root: "D:/AstraBridge/.astrabridge/codex-home/plugins/legacy-helper",
        source_file_count: 2,
        existing_target_file_count: 0,
        planned_write_count: 2,
        source_files: [{ relative_path: "SKILL.md", path: "D:/src/SKILL.md", bytes: 128 }],
        existing_target_files: [],
        planned_write_files: [{ relative_path: "SKILL.md", path: "D:/dst/SKILL.md", bytes: 128 }],
      },
      rollback_snapshot: {
        status: "planned",
        snapshot_id: "plugin-legacy-helper-abc123",
        snapshot_root: "D:/AstraBridge/.astrabridge/codex-home/plugin-rollbacks/plugin-legacy-helper-abc123",
        captured_file_count: 0,
        captured_files: [],
        notes: ["created_on_apply_only"],
      },
      warnings: [],
      errors: [],
      notes: ["planning_only"],
    });

    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} />);

    fireEvent.click(screen.getByRole("button", { name: /Legacy Helper/i }));
    fireEvent.click(screen.getByRole("button", { name: "Preview plan" }));

    await waitFor(() => expect(api.runtimePluginInstallPlan).toHaveBeenCalledWith({
      plugin_id: "legacy-helper",
      source_catalog_id: "local::legacy",
    }));

    expect(screen.getByText("Install plan")).toBeInTheDocument();
    expect(screen.getByText("install available plugin")).toBeInTheDocument();
    expect(screen.getByText("https://example.com/plugin.zip?token=[REDACTED]")).toBeInTheDocument();
    expect(screen.getByText("legacy-mcp")).toBeInTheDocument();
    expect(screen.getByText("legacy:helper")).toBeInTheDocument();
  });

  it("renders actionable unsupported plan errors", async () => {
    vi.mocked(api.runtimePluginInstallPlan).mockResolvedValue({
      schema_version: "astrabridge-plugin-install-plan-v1",
      generated_at: "2026-06-25T19:05:00+08:00",
      action: "unsupported",
      status: "unsupported",
      reason: "plugin_source_unsupported",
      plugin: {
        record_id: "plugin:github",
        plugin_id: "github",
        display_name: "GitHub",
        source_catalog_id: "official::github",
        install_status: "installed",
        enablement_status: "enabled",
        compatibility_status: "compatible",
      },
      source: {
        source_catalog_id: "official::github",
        kind: "official",
        display_name: "Official GitHub catalog",
        source_url: "https://plugins.example.com/github?token=[REDACTED]",
        writable: false,
      },
      versions: {
        current_version: "0.1.5",
        target_version: "0.1.5",
        installed_version: "0.1.5",
        available_version: null,
      },
      permission_hints: ["declares_mcp_servers"],
      declared_app_ids: ["github"],
      mcp_changes: {
        declared_servers: ["github"],
      },
      skill_changes: {
        declared_skills: ["github:gh-address-comments"],
        detected_installed_skills: ["github:gh-address-comments"],
      },
      files: {
        source_root: null,
        target_root: "D:/AstraBridge/.astrabridge/codex-home/plugins/github",
        source_file_count: 0,
        existing_target_file_count: 2,
        planned_write_count: 0,
        source_files: [],
        existing_target_files: [],
        planned_write_files: [],
      },
      rollback_snapshot: {
        status: "planned",
        snapshot_id: "plugin-github-abc123",
        snapshot_root: "D:/AstraBridge/.astrabridge/codex-home/plugin-rollbacks/plugin-github-abc123",
        captured_file_count: 2,
        captured_files: [],
      },
      warnings: [],
      errors: [
        {
          schema_version: "astrabridge-plugin-skill-warning-v1",
          code: "plugin-source-unsupported",
          severity: "error",
          message: "Remote or curated plugin sources are not plannable yet. Mirror the plugin into an AstraBridge-managed local source before applying changes.",
          field: "source_catalog_id",
        },
      ],
      notes: ["planning_only"],
    });

    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} />);

    fireEvent.click(screen.getAllByRole("button", { name: /GitHub/i })[1]);
    fireEvent.click(screen.getByRole("button", { name: "Preview plan" }));

    await waitFor(() => expect(screen.getByText("plugin-source-unsupported")).toBeInTheDocument());
    expect(screen.getByText(/Mirror the plugin into an AstraBridge-managed local source/)).toBeInTheDocument();
  });

  it("applies a ready plugin install plan after explicit user action", async () => {
    const onRegistryChanged = vi.fn();
    vi.mocked(api.runtimePluginInstallPlan).mockResolvedValue({
      schema_version: "astrabridge-plugin-install-plan-v1",
      generated_at: "2026-06-25T19:10:00+08:00",
      action: "install",
      status: "ready",
      reason: "install_available_plugin",
      plugin: {
        record_id: "plugin:legacy",
        plugin_id: "legacy-helper",
        display_name: "Legacy Helper",
        source_catalog_id: "local::legacy",
        install_status: "available",
        enablement_status: "disabled",
        compatibility_status: "warning",
      },
      source: {
        source_catalog_id: "local::legacy",
        kind: "local",
        display_name: "Legacy local catalog",
        writable: true,
      },
      versions: {
        current_version: null,
        target_version: "0.0.9",
        installed_version: null,
        available_version: "0.0.9",
      },
      permission_hints: [],
      declared_app_ids: [],
      mcp_changes: { declared_servers: [] },
      skill_changes: { declared_skills: [], detected_installed_skills: [] },
      files: {
        source_root: "D:/src",
        target_root: "D:/dst",
        source_file_count: 1,
        existing_target_file_count: 0,
        planned_write_count: 1,
        source_files: [],
        existing_target_files: [],
        planned_write_files: [],
      },
      rollback_snapshot: {
        status: "not_present",
        captured_file_count: 0,
        captured_files: [],
      },
      warnings: [],
      errors: [],
      notes: [],
    });
    vi.mocked(api.runtimePluginInstallApply).mockResolvedValue({
      schema_version: "astrabridge-plugin-install-execution-v1",
      execution_id: "plugin-install-123",
      executed_at: "2026-06-25T19:12:00+08:00",
      status: "applied",
      action: "install",
      plugin: {
        record_id: "plugin:legacy",
        plugin_id: "legacy-helper",
        display_name: "Legacy Helper",
        source_catalog_id: "local::legacy",
        install_status: "available",
        enablement_status: "disabled",
        compatibility_status: "warning",
      },
      plan: {} as any,
      artifact_paths: {
        report_root: "D:/AstraBridge/PRIVATE/demo-runs/plugin-install-123",
        plan_path: "D:/AstraBridge/PRIVATE/demo-runs/plugin-install-123/plan.json",
        events_path: "D:/AstraBridge/PRIVATE/demo-runs/plugin-install-123/events.jsonl",
        result_path: "D:/AstraBridge/PRIVATE/demo-runs/plugin-install-123/result.json",
      },
      source: {
        source_catalog_id: "local::legacy",
        kind: "local",
        display_name: "Legacy local catalog",
        writable: true,
      },
      target_root: "D:/AstraBridge/.astrabridge/codex-home/plugins/legacy-helper",
      changes: {
        written_file_count: 1,
        target_file_count: 1,
      },
      rollback_snapshot: {
        status: "not_present",
        captured_file_count: 0,
        captured_files: [],
      },
      warnings: [],
      errors: [],
      notes: ["apply_succeeded"],
    });

    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} onRegistryChanged={onRegistryChanged} />);

    fireEvent.click(screen.getByRole("button", { name: /Legacy Helper/i }));
    fireEvent.click(screen.getByRole("button", { name: "Preview plan" }));
    await waitFor(() => expect(api.runtimePluginInstallPlan).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(api.runtimePluginInstallApply).toHaveBeenCalledWith({
      plugin_id: "legacy-helper",
      source_catalog_id: "local::legacy",
    }));
    await waitFor(() => expect(onRegistryChanged).toHaveBeenCalled());
    expect(screen.getByText("Execution result")).toBeInTheDocument();
    expect(screen.getByText("D:/AstraBridge/PRIVATE/demo-runs/plugin-install-123/result.json")).toBeInTheDocument();
  });

  it("keeps a ready plugin install plan actionable across registry refreshes", async () => {
    vi.mocked(api.runtimePluginInstallPlan).mockResolvedValue({
      schema_version: "astrabridge-plugin-install-plan-v1",
      generated_at: "2026-06-25T19:10:00+08:00",
      action: "install",
      status: "ready",
      reason: "install_available_plugin",
      plugin: {
        record_id: "plugin:legacy",
        plugin_id: "legacy-helper",
        display_name: "Legacy Helper",
        source_catalog_id: "local::legacy",
        install_status: "available",
        enablement_status: "disabled",
        compatibility_status: "warning",
      },
      source: {
        source_catalog_id: "local::legacy",
        kind: "local",
        display_name: "Legacy local catalog",
        writable: true,
      },
      versions: {
        current_version: null,
        target_version: "0.0.9",
        installed_version: null,
        available_version: "0.0.9",
      },
      permission_hints: [],
      declared_app_ids: [],
      mcp_changes: { declared_servers: [] },
      skill_changes: { declared_skills: [], detected_installed_skills: [] },
      files: {
        source_root: "D:/src",
        target_root: "D:/dst",
        source_file_count: 1,
        existing_target_file_count: 0,
        planned_write_count: 1,
        source_files: [],
        existing_target_files: [],
        planned_write_files: [],
      },
      rollback_snapshot: {
        status: "planned",
        snapshot_id: "plugin-legacy-helper-abc123",
        captured_file_count: 0,
        captured_files: [],
      },
      warnings: [],
      errors: [],
      notes: [],
    });

    const refreshedSnapshot: CodexPluginSkillRegistrySnapshot = {
      ...snapshot,
      generated_at: "2026-06-25T19:11:00+08:00",
      plugins: snapshot.plugins.map((plugin) =>
        plugin.record_id === "plugin:legacy"
          ? { ...plugin, install_status: "installed" }
          : plugin,
      ),
    };

    const { rerender } = render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} />);

    fireEvent.click(screen.getByRole("button", { name: /Legacy Helper/i }));
    fireEvent.click(screen.getByRole("button", { name: "Preview plan" }));

    await waitFor(() => expect(api.runtimePluginInstallPlan).toHaveBeenCalledWith({
      plugin_id: "legacy-helper",
      source_catalog_id: "local::legacy",
    }));
    expect(screen.getByRole("button", { name: "Apply" })).toBeEnabled();

    rerender(<PluginSkillInventoryPanel locale="en" snapshot={refreshedSnapshot} isLoading={false} />);

    expect(screen.getByRole("button", { name: "Apply" })).toBeEnabled();
    expect(screen.getByText("install available plugin")).toBeInTheDocument();
    expect(screen.getByText("plugin-legacy-helper-abc123")).toBeInTheDocument();
  });

  it("adds a plugin to the active project preset", async () => {
    const onProjectChanged = vi.fn();
    vi.mocked(api.updateProjectPluginSkillPresets).mockResolvedValue({
      project: {
        ...project,
        plugin_skill_presets: {
          ...project.plugin_skill_presets!,
          presets: [
            {
              ...project.plugin_skill_presets!.presets[0],
              plugin_refs: [
                {
                  plugin_id: "github",
                  source_catalog_id: "official::github",
                  display_name: "GitHub",
                },
              ],
            },
          ],
        },
      },
    });

    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} project={project} onProjectChanged={onProjectChanged} />);

    fireEvent.click(screen.getAllByRole("button", { name: /GitHub/i })[1]);
    fireEvent.click(screen.getByRole("button", { name: "Add to project preset" }));

    await waitFor(() => expect(api.updateProjectPluginSkillPresets).toHaveBeenCalledWith({
      operation: "add_plugin",
      preset_id: "project-default",
      plugin_ref: {
        plugin_id: "github",
        source_catalog_id: "official::github",
        display_name: "GitHub",
      },
    }));
    expect(onProjectChanged).toHaveBeenCalled();
  });

  it("adds and resets skill references in the active project preset", async () => {
    const onProjectChanged = vi.fn();
    const projectWithSkillPreset: ProjectFile = {
      ...project,
      plugin_skill_presets: {
        ...project.plugin_skill_presets!,
        presets: [
          {
            ...project.plugin_skill_presets!.presets[0],
            skill_refs: [
              {
                record_id: "skill:github:address-comments",
                skill_name: "github:gh-address-comments",
                owner_plugin_id: "github",
                source_catalog_id: "official::github",
                display_name: "Address comments",
              },
            ],
          },
        ],
      },
    };
    vi.mocked(api.updateProjectPluginSkillPresets)
      .mockResolvedValueOnce({ project: projectWithSkillPreset })
      .mockResolvedValueOnce({ project });

    const { rerender } = render(
      <PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} project={project} onProjectChanged={onProjectChanged} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Address comments/i }));
    fireEvent.click(screen.getByRole("button", { name: "Add to project preset" }));

    await waitFor(() => expect(api.updateProjectPluginSkillPresets).toHaveBeenCalledWith({
      operation: "add_skill",
      preset_id: "project-default",
      skill_ref: {
        record_id: "skill:github:address-comments",
        skill_name: "github:gh-address-comments",
        owner_plugin_id: "github",
        source_catalog_id: "official::github",
        display_name: "Address comments",
      },
    }));

    rerender(
      <PluginSkillInventoryPanel
        locale="en"
        snapshot={snapshot}
        isLoading={false}
        project={projectWithSkillPreset}
        onProjectChanged={onProjectChanged}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Reset preset" })[0]);
    await waitFor(() => expect(api.updateProjectPluginSkillPresets).toHaveBeenLastCalledWith({
      operation: "reset",
      preset_id: "project-default",
    }));
    expect(onProjectChanged).toHaveBeenCalled();
  });

  it("updates skill enablement globally and per project", async () => {
    const onRegistryChanged = vi.fn();
    vi.mocked(api.runtimeSkillEnablementUpdate).mockResolvedValue(snapshot);

    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} onRegistryChanged={onRegistryChanged} />);

    fireEvent.click(screen.getByRole("button", { name: /Address comments/i }));
    fireEvent.click(screen.getByRole("button", { name: "Disable globally" }));

    await waitFor(() => expect(api.runtimeSkillEnablementUpdate).toHaveBeenCalledWith({
      record_id: "skill:github:address-comments",
      scope: "global",
      enablement_status: "disabled",
    }));

    fireEvent.click(screen.getByRole("button", { name: "Enable for project" }));
    await waitFor(() => expect(api.runtimeSkillEnablementUpdate).toHaveBeenCalledWith({
      record_id: "skill:github:address-comments",
      scope: "project",
      enablement_status: "enabled",
    }));
    expect(onRegistryChanged).toHaveBeenCalled();
    expect(screen.getByText("Global state path")).toBeInTheDocument();
    expect(screen.getByText("Project state path")).toBeInTheDocument();
  });

  it("refreshes the registry on demand and keeps the latest snapshot visible while loading", async () => {
    const onRegistryChanged = vi.fn().mockResolvedValue(undefined);

    const { rerender } = render(
      <PluginSkillInventoryPanel
        locale="en"
        snapshot={snapshot}
        isLoading={false}
        onRegistryChanged={onRegistryChanged}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Refresh registry" }));
    await waitFor(() => expect(onRegistryChanged).toHaveBeenCalledTimes(1));

    rerender(
      <PluginSkillInventoryPanel
        locale="en"
        snapshot={snapshot}
        isLoading
        onRegistryChanged={onRegistryChanged}
      />,
    );

    expect(screen.getByText("Refreshing inventory while keeping the last verified snapshot visible.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Address comments" })).toBeInTheDocument();
  });

  it("localizes registry refresh and discovery state in Chinese", () => {
    render(
      <PluginSkillInventoryPanel
        locale="zh-CN"
        snapshot={snapshot}
        isLoading
        onRegistryChanged={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "刷新清单" })).toBeInTheDocument();
    expect(screen.getByText("正在刷新清单，并保留上一份已验证快照可见。")).toBeInTheDocument();
    expect(screen.getByText("插件发现: 已支持")).toBeInTheDocument();
    expect(screen.getByText("技能发现: 已支持")).toBeInTheDocument();
  });

  it("surfaces pending approval and blocked ownership reasons for skills", () => {
    render(
      <PluginSkillInventoryPanel
        locale="en"
        snapshot={{
          ...snapshot,
          skills: [
            {
              ...snapshot.skills[0],
              record_id: "skill:pending",
              display_name: "Pending skill",
              skill_name: "plugin:pending",
              global_enablement_status: "disabled",
              effective_enablement_status: "disabled",
              enablement_status: "disabled",
              enablement_source: "global_default",
              notes: ["enablement_pending_user_approval"],
            },
            {
              ...snapshot.skills[0],
              record_id: "skill:blocked",
              display_name: "Blocked skill",
              skill_name: "plugin:blocked",
              owner_plugin_id: "missing-plugin",
              effective_enablement_status: "blocked",
              enablement_status: "enabled",
              enablement_source: "blocked",
              enablement_block_reason: "owner_plugin_unavailable",
              notes: ["plugin_owned"],
            },
          ],
        }}
        isLoading={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Pending skill/i }));
    expect(screen.getAllByText("Waiting for approval").length).toBeGreaterThan(0);
    expect(screen.getByText("This skill came from a newly installed plugin and remains disabled until you explicitly approve it.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Blocked skill/i }));
    expect(screen.getByText("Owning plugin unavailable")).toBeInTheDocument();
    expect(screen.getByText("AstraBridge cannot enable this skill until its owning plugin becomes available again. (owner plugin unavailable)")).toBeInTheDocument();
  });

  it("renders Plugin Creator controlled task evidence paths in Chinese", () => {
    render(<PluginSkillInventoryPanel locale="zh-CN" snapshot={snapshotWithPluginCreator} isLoading={false} />);

    fireEvent.click(screen.getByRole("button", { name: /Plugin Creator/i }));

    expect(screen.getByTestId("plugin-creator-skill-scenario-panel")).toBeInTheDocument();
    expect(screen.getByText("受控任务")).toBeInTheDocument();
    expect(screen.getByText("固定 brief 路径")).toBeInTheDocument();
    expect(screen.getByText("apps/astrabridge-sidecar/tests/fixtures/skill_plugin_creator_fixture/input/plugin-creator-brief.md")).toBeInTheDocument();
    expect(screen.getByText("apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step10-skills-plugin-creator-report-partial.json")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "运行受控任务" })).toBeInTheDocument();
  });

  it("renders the latest Plugin Creator controlled task execution evidence after a run", async () => {
    vi.mocked(api.runtimeSkillPluginCreatorFixtureScenario).mockResolvedValue({
      schema_version: "astrabridge-skill-plugin-creator-scenario-v1",
      execution_id: "skill-plugin-creator-123",
      scenario_id: "skills_plugin_creator_fixture_scaffold",
      capability: "skills",
      skill_name: "plugin-creator",
      skill_display_name: "Plugin Creator",
      skill_record_id: "skill:system:plugin-creator",
      started_at: "2026-06-26T12:30:00+08:00",
      completed_at: "2026-06-26T12:31:00+08:00",
      status: "pass",
      failure_reason: "",
      input: {
        fixture_contract_path: "apps/astrabridge-sidecar/tests/fixtures/skill_plugin_creator_fixture/fixture-contract.json",
        brief_path: "apps/astrabridge-sidecar/tests/fixtures/skill_plugin_creator_fixture/input/plugin-creator-brief.md",
      },
      output: {
        run_root: "PRIVATE/demo-runs/skills-plugin-creator-scenario/",
        execution_root: "PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/",
        plugin_root: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/",
        manifest_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/.codex-plugin/plugin.json",
        marketplace_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/.agents/plugins/marketplace.json",
        required_paths: [],
      },
      artifact_paths: {
        events_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/events.jsonl",
        result_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/result.json",
        report_seed_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/dogfood-report-seed.json",
      },
      verification_commands: [],
      command_results: [],
      checks: [
        { label: "plugin-root-exists", passed: true, message: "Plugin root was created." },
        { label: "manifest-plugin-name", passed: true, message: "Generated manifest uses the fixed plugin name." },
      ],
      notes: [],
      report_seed: {
        schema_version: "astrabridge-real-scenario-dogfood-report-seed-v1",
        step_id: "step_12",
        capability: "skills",
        scenario_id: "skills_plugin_creator_fixture_scaffold",
        trigger_path: "能力 -> 技能 -> Plugin Creator",
        suggested_report_path: "apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step12-skills-plugin-creator-pass.json",
        suggested_screenshots: [],
      },
    });

    render(<PluginSkillInventoryPanel locale="en" snapshot={snapshotWithPluginCreator} isLoading={false} />);

    fireEvent.click(screen.getByRole("button", { name: /Plugin Creator/i }));
    fireEvent.click(screen.getByRole("button", { name: "Run controlled task" }));

    await waitFor(() => expect(api.runtimeSkillPluginCreatorFixtureScenario).toHaveBeenCalledWith({
      skill_name: "plugin-creator",
    }));

    expect(screen.getByText("Latest execution")).toBeInTheDocument();
    expect(screen.getByText("skill-plugin-creator-123")).toBeInTheDocument();
    expect(screen.getByText("PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/result.json")).toBeInTheDocument();
    expect(screen.getByText("apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step12-skills-plugin-creator-pass.json")).toBeInTheDocument();
  });

  it("can preview the generated Plugin Creator manifest after a successful run", async () => {
    vi.mocked(api.runtimeSkillPluginCreatorFixtureScenario).mockResolvedValue({
      schema_version: "astrabridge-skill-plugin-creator-scenario-v1",
      execution_id: "skill-plugin-creator-123",
      scenario_id: "skills_plugin_creator_fixture_scaffold",
      capability: "skills",
      skill_name: "plugin-creator",
      skill_display_name: "Plugin Creator",
      skill_record_id: "skill:system:plugin-creator",
      started_at: "2026-06-26T12:30:00+08:00",
      completed_at: "2026-06-26T12:31:00+08:00",
      status: "pass",
      failure_reason: "",
      input: {
        fixture_contract_path: "apps/astrabridge-sidecar/tests/fixtures/skill_plugin_creator_fixture/fixture-contract.json",
        brief_path: "apps/astrabridge-sidecar/tests/fixtures/skill_plugin_creator_fixture/input/plugin-creator-brief.md",
      },
      output: {
        run_root: "PRIVATE/demo-runs/skills-plugin-creator-scenario/",
        execution_root: "PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/",
        plugin_root: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/",
        manifest_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/.codex-plugin/plugin.json",
        marketplace_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/.agents/plugins/marketplace.json",
        required_paths: [],
      },
      artifact_paths: {
        events_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/events.jsonl",
        result_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/result.json",
        report_seed_path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/executions/skill-plugin-creator-123/dogfood-report-seed.json",
      },
      verification_commands: [],
      command_results: [],
      checks: [],
      notes: [],
      report_seed: {
        schema_version: "astrabridge-real-scenario-dogfood-report-seed-v1",
        step_id: "step_12",
        capability: "skills",
        scenario_id: "skills_plugin_creator_fixture_scaffold",
        trigger_path: "能力 -> 技能 -> Plugin Creator",
        suggested_report_path: "apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step12-skills-plugin-creator-pass.json",
        suggested_screenshots: [],
      },
    });
    vi.mocked(api.projectFileRead).mockResolvedValue({
      path: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/.codex-plugin/plugin.json",
      name: "plugin.json",
      kind: "json",
      size: 128,
      updated_at: Date.parse("2026-06-26T12:31:00+08:00"),
      content: "{\"name\":\"astrabridge-skills-dogfood-sample\"}",
    });

    render(<PluginSkillInventoryPanel locale="zh-CN" snapshot={snapshotWithPluginCreator} isLoading={false} />);

    fireEvent.click(screen.getByRole("button", { name: /Plugin Creator/i }));
    fireEvent.click(screen.getByRole("button", { name: "运行受控任务" }));

    await waitFor(() => expect(api.runtimeSkillPluginCreatorFixtureScenario).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "预览 Manifest" }));

    await waitFor(() =>
      expect(api.projectFileRead).toHaveBeenCalledWith(
        "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/.codex-plugin/plugin.json",
      ),
    );
    expect(screen.getByTestId("plugin-creator-artifact-preview")).toBeInTheDocument();
    expect(screen.getByText(/"name": "astrabridge-skills-dogfood-sample"/i)).toBeInTheDocument();
  });

  it("can reset a project override back to the global skill setting", async () => {
    vi.mocked(api.runtimeSkillEnablementUpdate).mockResolvedValue(snapshot);

    render(
      <PluginSkillInventoryPanel
        locale="en"
        snapshot={{
          ...snapshot,
          skills: [
            {
              ...snapshot.skills[0],
              project_enablement_status: "enabled",
              effective_enablement_status: "enabled",
              enablement_status: "enabled",
              enablement_source: "project_override",
            },
          ],
        }}
        isLoading={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Address comments/i }));
    fireEvent.click(screen.getByRole("button", { name: "Use global setting" }));

    await waitFor(() => expect(api.runtimeSkillEnablementUpdate).toHaveBeenCalledWith({
      record_id: "skill:github:address-comments",
      scope: "project",
      enablement_status: "inherited",
    }));
  });

  it("disables enable actions when the owning plugin is unavailable", () => {
    render(
      <PluginSkillInventoryPanel
        locale="en"
        snapshot={{
          ...snapshot,
          skills: [
            {
              ...snapshot.skills[0],
              owner_plugin_id: "missing-plugin",
              enablement_status: "blocked",
              effective_enablement_status: "blocked",
              enablement_block_reason: "owner_plugin_unavailable",
              compatibility_warnings: [
                {
                  schema_version: "astrabridge-plugin-skill-warning-v1",
                  code: "skill-owning-plugin-missing",
                  severity: "warning",
                  message: "Owning plugin missing-plugin is not available in the current registry snapshot.",
                  field: "owner_plugin_id",
                },
              ],
            },
          ],
        }}
        isLoading={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Address comments/i }));
    expect(screen.getByRole("button", { name: "Enable globally" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Enable for project" })).toBeDisabled();
    expect(screen.getByText("Owning plugin unavailable")).toBeInTheDocument();
  });
});
