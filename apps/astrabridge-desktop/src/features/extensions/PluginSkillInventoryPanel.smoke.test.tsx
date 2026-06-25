import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CodexPluginSkillRegistrySnapshot } from "../../types";
import { PluginSkillInventoryPanel } from "./PluginSkillInventoryPanel";

declare const process: {
  env: Record<string, string | undefined>;
};

const snapshot = loadSnapshot();

afterEach(() => cleanup());

describe("PluginSkillInventoryPanel smoke", () => {
  it("renders inventory summary counts for the smoke snapshot", () => {
    renderPanel();

    expect(screen.getByText("Extensions")).toBeInTheDocument();
    expect(screen.getByText(`Plugins: ${snapshot.plugins.length}`)).toBeInTheDocument();
    expect(screen.getByText(`Skills: ${snapshot.skills.length}`)).toBeInTheDocument();
  });

  it("renders declared MCP details for the smoke plugin fixture", () => {
    renderPanel();

    const plugin = snapshot.plugins[0];
    fireEvent.click(screen.getByRole("button", { name: new RegExp(escapeRegExp(plugin.display_name), "i") }));

    expect(screen.getByText("Declared MCP")).toBeInTheDocument();
    expect(screen.getByText("demo_mcp")).toBeInTheDocument();
  });

  it("renders owning plugin details for the smoke skill fixture", () => {
    renderPanel();

    const skill = snapshot.skills[0];
    fireEvent.click(screen.getByRole("button", { name: new RegExp(escapeRegExp(skill.display_name), "i") }));

    expect(screen.getAllByText("Owning plugin").length).toBeGreaterThan(0);
    expect(screen.getAllByText("demo-plugin-smoke").length).toBeGreaterThan(0);
  });
});

function renderPanel(): void {
  render(<PluginSkillInventoryPanel locale="en" snapshot={snapshot} isLoading={false} />);
}

function loadSnapshot(): CodexPluginSkillRegistrySnapshot {
  const payload = process.env.ASTRABRIDGE_PLUGIN_SKILL_SMOKE_SNAPSHOT_JSON;
  if (payload) {
    return JSON.parse(payload) as CodexPluginSkillRegistrySnapshot;
  }
  return fallbackSnapshot();
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function fallbackSnapshot(): CodexPluginSkillRegistrySnapshot {
  return {
    schema_version: "astrabridge-plugin-skill-registry-v1",
    generated_at: "2026-06-25T23:40:00+08:00",
    source_catalogs: [
      {
        schema_version: "astrabridge-plugin-skill-registry-v1",
        source_catalog_id: "local::smoke",
        kind: "local",
        display_name: "Smoke fixture catalog",
        source_path: "D:/AstraBridge/PRIVATE/demo-runs/plugin-skill-smoke-fixture",
        writable: true,
      },
    ],
    plugins: [
      {
        schema_version: "astrabridge-plugin-skill-registry-v1",
        record_id: "plugin:demo-plugin-smoke",
        plugin_id: "demo-plugin-smoke",
        source_catalog_id: "local::smoke",
        display_name: "Demo Plugin Smoke",
        install_status: "available",
        enablement_status: "disabled",
        compatibility_status: "compatible",
        declared_mcp_servers: ["demo_mcp"],
        permission_hints: ["declares_mcp_servers", "declares_apps", "declares_skills"],
        description: "Fixture plugin for plugin and skill smoke.",
        compatibility_warnings: [],
        notes: [],
      },
    ],
    skills: [
      {
        schema_version: "astrabridge-plugin-skill-registry-v1",
        record_id: "skill:demo-plugin-skill",
        skill_name: "demo-plugin-skill",
        source_catalog_id: "local::smoke",
        display_name: "demo-plugin-skill",
        install_status: "installed",
        enablement_status: "unknown",
        compatibility_status: "compatible",
        owner_plugin_id: "demo-plugin-smoke",
        description: "Fixture skill for plugin smoke tasks.",
        compatibility_warnings: [],
        notes: [],
      },
    ],
    notes: [],
  };
}
