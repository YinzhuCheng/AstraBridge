import { describe, expect, it } from "vitest";

import type { NodeTypeRegistrySnapshot } from "../../types";
import { buildTaskGraphNodeRegistryUi, taskGraphPaletteMeta } from "./taskGraphNodeRegistryUi";

const snapshot: NodeTypeRegistrySnapshot = {
  schema_version: "astrabridge-node-type-registry-v1",
  registry_fingerprint: "registry-fp",
  executor_registry_fingerprint: "executor-fp",
  role_ids: ["custom"],
  kind_aliases: {
    custom: "agent_model",
    mcp_tool: "mcp_tool",
  },
  node_types: [
    {
      type_id: "agent_model",
      version: 1,
      category: "agent",
      title: "Agent / Model",
      description: "Bounded provider-backed agent lane.",
      config_schema: {},
      typed_ports: { inputs: [], outputs: [] },
      compiler_executor_id: "agent_lane",
      default_policy: {},
      ui_hints: {
        palette_variants: [{ kind: "custom", label: "Custom", description: "Agent shell" }],
      },
      migration: {},
      registry_fingerprint: "node-agent",
      executor_capability: {
        executor_id: "agent_lane",
        executor_version: 1,
        executor_registry_fingerprint: "executor-fp",
        availability_summary: "live_and_fixture",
        supported_modes: {
          live_run: { available: true, status: "available", reason: "Live ready" },
          fixture_run: { available: true, status: "available", reason: "Fixture ready" },
        },
        effect_classification: "provider_lane",
        capability_dependencies: ["provider_profile"],
      },
    },
    {
      type_id: "mcp_tool",
      version: 1,
      category: "capability",
      title: "MCP Tool",
      description: "Calls one MCP tool.",
      config_schema: {},
      typed_ports: { inputs: [], outputs: [] },
      compiler_executor_id: "mcp_tool",
      default_policy: {},
      ui_hints: {},
      migration: {},
      registry_fingerprint: "node-mcp",
      executor_capability: {
        executor_id: "mcp_tool",
        executor_version: 1,
        executor_registry_fingerprint: "executor-fp",
        availability_summary: "fixture_only",
        supported_modes: {
          live_run: {
            available: false,
            status: "planned",
            reason: "Dedicated live MCP tool executor lands in Step 13.",
          },
          fixture_run: { available: true, status: "available", reason: "Fixture ready" },
        },
        effect_classification: "mcp_dispatch",
        capability_dependencies: ["mcp_broker"],
      },
    },
  ],
  executor_matrix: {
    schema_version: "astrabridge-executor-registry-v1",
    registry_fingerprint: "executor-fp",
    execution_modes: ["live_run", "fixture_run"],
    executors: [],
    node_types: [],
  },
};

describe("taskGraphNodeRegistryUi", () => {
  it("surfaces live and fixture availability in palette metadata", () => {
    const ui = buildTaskGraphNodeRegistryUi({ locale: "en", snapshot });

    const agent = taskGraphPaletteMeta(ui, "custom");
    const mcp = taskGraphPaletteMeta(ui, "mcp_tool");

    expect(agent.availabilitySummary).toBe("live_and_fixture");
    expect(agent.description).toContain("Availability: live + fixture.");
    expect(mcp.availabilitySummary).toBe("fixture_only");
    expect(mcp.description).toContain("Availability: fixture only.");
    expect(mcp.description).toContain("Step 13");
  });
});
