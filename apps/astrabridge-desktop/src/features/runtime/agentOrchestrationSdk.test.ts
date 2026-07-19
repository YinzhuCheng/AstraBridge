import { describe, expect, it } from "vitest";

import { AgentOrchestrationGraphBuilder, buildCustomBlankGraphFixture } from "./agentOrchestrationSdk";
import tsFixture from "./fixtures/customBlankGraph.fromTs.json";

describe("AgentOrchestrationGraphBuilder", () => {
  it("emits the shared custom blank graph fixture with deterministic JSON", () => {
    const builder = buildCustomBlankGraphFixture();
    const jsonText = builder.toJson();
    const tsFixtureText = `${JSON.stringify(tsFixture, null, 2)}\n`;

    expect(jsonText).toBe(tsFixtureText);
    expect(JSON.parse(jsonText)).toEqual(tsFixture);
    expect(builder.toJson()).toBe(jsonText);
  });

  it("supports the generic builder surface without introducing runtime-derived fields", () => {
    const builder = new AgentOrchestrationGraphBuilder({
      graph_id: "graph_custom_blank_graph_v1",
      task_id: "task_example",
      title: "Custom Blank Graph",
      template_id: "custom_blank_graph",
      metadata: {
        description: "Custom Blank Graph",
        tags: ["custom", "blank", "starter"],
        owners: [],
        created_at: "2026-07-07T00:00:00+09:00",
        updated_at: "2026-07-07T00:05:00+09:00",
      },
      graph_policy: {
        entry_node_ids: ["node_start_here"],
        max_depth: 2,
        default_permission_mode: "ask",
        default_collaboration_mode: "default",
        default_execution_backend: "app_server",
        requires_dry_run_before_live: true,
      },
      migration: {
        source_kind: "native_authoring",
        compiled_task_graph_version: "astrabridge-task-graph-v1",
        compatibility: {
          lowering_mode: "lossy_legacy_task_graph",
          preserves_unknown_fields: false,
          notes: [
            "Canonical graphs remain the source of truth for GUI, code, dry-run, and runtime work.",
            "Lowering into legacy task graphs is a compatibility shim while the generic scheduler is still under construction.",
          ],
        },
      },
    });
    builder.registerSchema("schema.blank_entry", {
      type: "object",
      required: ["goal", "next_nodes"],
    });
    builder.addNode({
      node_id: "node_start_here",
      kind: "artifact_source",
      label: "Start Here",
      role: "custom",
      card_ref: "agent_card_blank_entry",
      routing: {
        selection_mode: "none",
      },
      prompt: {
        template_mode: "inline",
        template: "Use this starter node as the seed for a custom graph.",
      },
      tools: {
        approval_mode: "ask",
        allowed_tool_classes: [],
      },
      inputs: [
        {
          port_id: "task_context",
          label: "Task Context",
          port_type: "text",
          shape: "single",
          required: true,
        },
      ],
      outputs: [
        {
          port_id: "machine_result",
          label: "Machine Result",
          port_type: "structured_json",
          shape: "single",
          required: true,
          schema_ref: "schema.blank_entry",
        },
      ],
      input_contract: {
        mode: "task_context_and_typed_ports",
        port_ids: ["task_context"],
      },
      output_contract: {
        mode: "structured_only",
        machine_result_schema_ref: "schema.blank_entry",
        artifact_specs: [],
        human_summary_required: true,
      },
      execution: {
        spawn_mode: "inline_lane",
        timeout_ms: 60000,
        retry_policy: {
          max_attempts: 1,
        },
        execution_backend: "app_server",
        collaboration_mode: "default",
        subagent_policy: null,
      },
      safety: {
        risk_class: "low",
        allow_provider_calls: false,
        allow_code_changes: false,
        allow_install: false,
        requires_human_approval: false,
      },
      ui: {
        position: {
          x: 140,
          y: 200,
        },
        layout_mode: "canvas",
      },
    });

    const graph = builder.build() as Record<string, unknown>;
    const node = ((graph.nodes as Array<Record<string, unknown>> | undefined) ?? [])[0] ?? {};

    expect(graph.template_id).toBe("custom_blank_graph");
    expect(node.resolved_node_type_id).toBeUndefined();
    expect(node.node_type_registry_fingerprint).toBeUndefined();
  });
});
