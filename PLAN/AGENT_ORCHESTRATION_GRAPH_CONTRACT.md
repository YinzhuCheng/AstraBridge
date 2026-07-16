# Agent Orchestration Graph Contract

Last updated: 2026-07-07

## Purpose

This document defines AstraBridge's canonical agent orchestration graph
contract.

The contract is the single source of truth for:

- GUI authoring
- code-first graph files
- runtime lowering into the existing task-graph engine
- dry-run validation
- import/export round-trip
- main-agent orchestration skill behavior
- migration and rollback

This contract is not an external A2A protocol. It is the product's internal
orchestration model.

## Decision Summary

### Contract shape

Decision:

- Introduce a new canonical wrapper contract named
  `AgentOrchestrationGraph`.
- In the short term, compile that wrapper into the current
  `TaskGraphDefinition` plus a small set of orchestration-specific extension
  records.

This is a wrapper-and-compiler design, not a pure in-place extension of
`TaskGraphDefinition`.

### Why this decision

`TaskGraphDefinition` already covers:

- graph topology
- node and edge identity
- basic provider/model routing
- context policy
- run/dry-run alignment
- fixture execution
- review and artifact support

But it is still execution-oriented and task-graph-shaped. It does not cleanly
model these as first-class authoring concepts:

- prompt templates and prompt variables
- tool contracts and tool policies
- output schemas and artifact contracts
- edge communication formats
- graph file import/export
- code-reviewable graph metadata
- UI authoring metadata distinct from execution metadata

If AstraBridge keeps stretching `TaskGraphDefinition` directly, it will blur the
boundary between:

- authoring contract
- execution contract
- run-state contract

That makes migration, review, and GUI/code round-trip harder.

The wrapper design keeps one canonical graph while still reusing the proven
runtime under it.

## Relationship To Existing Task Graph

### Current state

The current runtime already has these stable concepts:

- `TaskGraphDefinition`
- `TaskGraphNode`
- `TaskGraphEdge`
- `TaskGraphContextPolicy`
- `TaskGraphRunRef`
- dry-run reporting
- fixture execution
- approval and worker artifact support

These remain valuable and should not be discarded.

### Target state

`AgentOrchestrationGraph` becomes the authoring and interchange contract.

The existing task-graph runtime becomes the first lowering target:

1. GUI or graph file edits produce `AgentOrchestrationGraph`.
2. Validation and migration run on `AgentOrchestrationGraph`.
3. A compiler lowers that graph into `TaskGraphDefinition` plus runtime-ready
   execution payloads.
4. Existing `task_service.py` execution, dry-run, fixture, artifact, and
   approval paths consume the lowered representation.

Rule:

- GUI and code files never become a parallel runtime.
- `TaskGraphDefinition` becomes a compiled execution representation during the
  transition period.

## Canonical Object Model

## Top-Level Shape

### `AgentOrchestrationGraph`

```json
{
  "schema_version": "astrabridge-agent-orchestration-graph-v1",
  "graph_id": "graph_code_fix_review_v1",
  "task_id": "task_123",
  "title": "Code Fix / Test / Review",
  "template_id": "code_fix_test_review",
  "status": "draft",
  "metadata": {
    "description": "Bounded coding workflow with validation and review.",
    "tags": ["coding", "review", "bounded-change"],
    "owners": [],
    "created_at": "2026-07-07T00:00:00+09:00",
    "updated_at": "2026-07-07T00:00:00+09:00"
  },
  "graph_policy": {
    "entry_node_ids": ["node_plan_fix"],
    "max_depth": 2,
    "default_permission_mode": "ask",
    "default_collaboration_mode": "default",
    "default_execution_backend": "app_server",
    "requires_dry_run_before_live": true
  },
  "nodes": [],
  "edges": [],
  "ui": {
    "layout_version": 1,
    "viewport_hints": {
      "canvas_priority": "high"
    }
  },
  "migration": {
    "source_kind": "native_authoring",
    "compiled_task_graph_version": "astrabridge-task-graph-v1"
  },
  "state_version": 1
}
```

## Major Sub-Objects

### `metadata`

Purpose:

- authoring and governance metadata that should not directly affect execution

Required fields:

- `description`
- `created_at`
- `updated_at`

Important optional fields:

- `tags`
- `owners`
- `source_file`
- `notes`
- `compatibility_targets`

### `graph_policy`

Purpose:

- graph-wide defaults and safety boundaries

Required fields:

- `entry_node_ids`
- `max_depth`
- `requires_dry_run_before_live`

Important optional fields:

- `default_permission_mode`
- `default_collaboration_mode`
- `default_execution_backend`
- `default_context_policy_id`
- `allow_parallel_branches`
- `requires_user_approval_for_depth_gt`
- `required_profiles`

### `AgentOrchestrationNode`

Purpose:

- canonical authoring-time node model

Required fields:

- `node_id`
- `kind`
- `label`
- `role`
- `card_ref`
- `routing`
- `prompt`
- `tools`
- `input_contract`
- `output_contract`
- `execution`
- `safety`
- `ui`

Important optional fields:

- `memory`
- `artifacts`
- `approval_gate`
- `notes`

### `AgentOrchestrationEdge`

Purpose:

- canonical authoring-time communication and dependency model

Required fields:

- `edge_id`
- `from_node_id`
- `to_node_id`
- `edge_type`
- `handoff_contract`
- `context_policy`
- `ui`

Important optional fields:

- `required`
- `notes`

## Node Model

### `role`

This is the human and skill-facing semantic role, distinct from implementation
kind.

Allowed starter values:

- `supervisor`
- `worker`
- `synthesizer`
- `extractor`
- `validator`
- `reviewer`
- `planner`
- `coder`
- `researcher`
- `gate`
- `custom`

Rule:

- `kind` remains execution-compatible with current task-graph kinds.
- `role` is allowed to be richer than `kind`.

Example:

- `kind = worker`
- `role = coder`

### `routing`

Purpose:

- model/provider/profile selection and reasoning behavior

Required fields:

- `selection_mode`

Important optional fields:

- `provider_id`
- `model_id`
- `profile_id`
- `reasoning_effort`
- `temperature`
- `supports_vision`
- `supports_audio`
- `fallback_route_ids`

Rule:

- `profile_id` is preferred when a curated local profile exists.
- `provider_id` and `model_id` remain explicit to support cross-provider graph
  review and migration.

### `prompt`

Purpose:

- first-class prompt definition

Required fields:

- `template_mode`
- `template`

Important optional fields:

- `system_template`
- `developer_template`
- `user_template`
- `variable_schema`
- `sample_inputs`
- `preview_render`

Rule:

- prompt templates are canonical graph content
- compiled runtime prompts are derived artifacts

### `tools`

Purpose:

- explicit tool and integration policy

Required fields:

- `approval_mode`
- `allowed_tool_classes`

Important optional fields:

- `allowed_tool_ids`
- `blocked_tool_ids`
- `supports_mcp`
- `supports_web`
- `supports_apply_patch`
- `supports_shell`

### `input_contract`

Purpose:

- describe what the node expects from upstream

Required fields:

- `mode`

Important optional fields:

- `required_artifact_kinds`
- `required_schema_refs`
- `required_message_parts`
- `accepts_human_summary`
- `accepts_machine_result`

### `output_contract`

Purpose:

- describe what the node must produce

Required fields:

- `mode`
- `machine_result_schema_ref`
- `artifact_specs`

Important optional fields:

- `human_summary_required`
- `confidence_required`
- `next_action_hints_allowed`
- `blocking_issue_schema_ref`

Rule:

- if `mode = artifact_only`, `machine_result_schema_ref` may be null
- otherwise a structured machine output is mandatory

### `execution`

Purpose:

- execution policy that can lower into current runtime policies

Required fields:

- `spawn_mode`
- `timeout_ms`
- `retry_policy`

Important optional fields:

- `budget`
- `allow_parallel_children`
- `execution_backend`
- `collaboration_mode`

### `safety`

Purpose:

- explicit risk, approval, and mutation boundaries

Required fields:

- `risk_class`
- `allow_provider_calls`
- `allow_code_changes`
- `allow_install`
- `requires_human_approval`

Important optional fields:

- `approval_kind`
- `external_write_policy`
- `secret_handling_policy`

### `memory`

Purpose:

- node-local memory policy

Required fields:

- `private_memory_mode`

Important optional fields:

- `shared_memory_refs`
- `summary_retention`
- `context_budget_hint`

Rule:

- private memory is excluded from downstream handoff unless explicitly allowed
  by edge policy

## Edge Model

### `handoff_contract`

Purpose:

- first-class communication format between agents

Required fields:

- `message_template`
- `message_part_modes`
- `required_output_schema_refs`

Important optional fields:

- `artifact_bundle_policy`
- `preview_payload`
- `termination_signal`

This is the key authoring concept missing from the current task graph.

### `context_policy`

Purpose:

- shared with the current task-graph concept, but remains canonical here

Required fields:

- `policy_id`
- `history_mode`
- `artifact_mode`
- `exclude_private_memory`
- `include_machine_results`
- `include_human_summaries`

Important optional fields:

- `history_length`
- `included_artifacts`
- `resource_refs`
- `summary_strategy`
- `field_acl`

### `ui`

Purpose:

- non-authoritative editing metadata

Required fields:

- `position`

Important optional fields:

- `collapsed`
- `inspector_group`
- `icon_hint`
- `color_hint`
- `notes_visible`

Rule:

- UI metadata must never change execution by itself

## Schema Ownership And Type Sync

Decision:

- the authoritative schema definition should live in the sidecar repository
  layer because validation, migration, and runtime lowering are backend-owned
  concerns

Planned ownership:

- authoritative contract module:
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
- JSON-schema export artifact:
  `apps/astrabridge-sidecar/astrabridge_sidecar/schema/agent_orchestration_graph.schema.json`
- frontend generated or synchronized types:
  `apps/astrabridge-desktop/src/types.ts`

Sync rule:

1. Python contract definitions own the canonical validation vocabulary.
2. JSON schema is exported from that canonical definition.
3. Desktop TypeScript types are generated from JSON schema where practical, or
   updated from the same authoritative field list in a checked sync step.
4. GUI-only helper types may exist in desktop code, but canonical graph fields
   must not be invented frontend-first.

## Lowering Strategy

## Phase 1 Lowering Target

Compile `AgentOrchestrationGraph` into:

- `TaskGraphDefinition`
- task-graph node `execution_policy`
- task-graph node `output_contract`
- task-graph edge `context_policy`
- optional orchestration extension metadata stored in:
  - node `ui_hints`
  - node `machine_result_schema`
  - node `human_summary_template`
  - future graph-level extension block

### Lowering rules

#### Node lowering

- `role` lowers into:
  - direct `kind` when compatible
  - `ui_hints.role` when richer than current runtime kind vocabulary
- `routing.*` lowers into current provider/model/reasoning/profile fields
- `prompt.*` lowers into extension metadata until prompt execution consumes the
  canonical field directly
- `tools.*` lowers into `execution_policy` and future runtime tool-policy
  fields
- `output_contract.*` lowers into current `output_contract` plus
  `machine_result_schema`
- `safety.*` lowers into `execution_policy` and `approval_gate`

#### Edge lowering

- `handoff_contract` lowers into edge extension metadata
- `context_policy` lowers directly into current `TaskGraphContextPolicy`
- richer schema references lower into extension metadata until the runtime reads
  them directly

#### Graph lowering

- `graph_policy.entry_node_ids` lowers directly
- `graph_policy.max_depth` and other authoring-only defaults remain canonical
  graph metadata until runtime validators consume them

## Compatibility With Existing Graph Definitions

### Direction

Existing `TaskGraphDefinition` records remain readable.

Migration path:

1. Parse legacy `TaskGraphDefinition`.
2. Lift it into `AgentOrchestrationGraph`.
3. Fill missing canonical fields with explicit defaults and migration warnings.

### Legacy-to-canonical field mapping

| Existing `TaskGraphDefinition` field | Canonical destination |
| --- | --- |
| `graph_id` | `graph_id` |
| `task_id` | `task_id` |
| `title` | `title` |
| `template_id` | `template_id` |
| `status` | `status` |
| `graph_policy.entry_node_ids` | `graph_policy.entry_node_ids` |
| node `kind` | node `kind` and default `role` |
| node `label` | node `label` |
| node `agent_card_ref` | node `card_ref` |
| node provider/model/reasoning fields | node `routing.*` |
| node `execution_policy` | node `execution.*` and part of `safety.*` |
| node `output_contract` | node `output_contract` |
| node `machine_result_schema` | node `output_contract.machine_result_schema_ref` or inline lifted schema |
| node `human_summary_template` | node `prompt` or output summary template extension, depending on usage |
| node `ui_hints` | node `ui` plus extension migration payload |
| edge `edge_type` | edge `edge_type` |
| edge `context_policy` | edge `context_policy` |
| node `position` | node `ui.position` |

### Required migration defaults

When lifting a legacy graph, the migrator must add warnings for:

- missing first-class `prompt`
- missing first-class `tools`
- missing `handoff_contract`
- missing explicit `role` when only `kind` is known
- missing graph-level `max_depth`
- machine-result schema embedded in legacy shape rather than a stable schema ref

### Compatibility rule

Legacy graphs are allowed to load if they can be deterministically lifted into
canonical form with warnings.

They must fail migration if:

- duplicate ids exist
- context policy is missing
- executable nodes have no output contract
- unsafe execution lacks an approval path
- secret-like content appears in graph metadata

## Example 1: Code Fix / Test / Review

### YAML

```yaml
schema_version: astrabridge-agent-orchestration-graph-v1
graph_id: graph_code_fix_review_v1
task_id: task_example
title: Code Fix / Test / Review
template_id: code_fix_test_review
status: draft
metadata:
  description: Bounded code change with validation and review.
  tags: [coding, tests, review]
  created_at: 2026-07-07T00:00:00+09:00
  updated_at: 2026-07-07T00:00:00+09:00
graph_policy:
  entry_node_ids: [node_plan_fix]
  max_depth: 2
  default_permission_mode: ask
  default_collaboration_mode: default
  default_execution_backend: app_server
  requires_dry_run_before_live: true
nodes:
  - node_id: node_plan_fix
    kind: supervisor
    role: planner
    label: Plan Fix
    card_ref: agent_card_code_supervisor
    routing:
      selection_mode: explicit
      provider_id: qwen
      model_id: qwen3-coder-plus
      reasoning_effort: medium
    prompt:
      template_mode: inline
      template: |
        Review the issue, bound the file set, and declare expected evidence.
      variable_schema:
        type: object
        required: [task_goal]
    tools:
      approval_mode: ask
      allowed_tool_classes: [web, read_file]
      supports_mcp: true
    input_contract:
      mode: task_context
    output_contract:
      mode: structured_and_artifacts
      machine_result_schema_ref: schema.plan_fix_result
      artifact_specs:
        - kind: structured_json
          id: plan_manifest
      human_summary_required: true
    execution:
      spawn_mode: inline_lane
      timeout_ms: 120000
      retry_policy:
        max_attempts: 1
      execution_backend: app_server
    safety:
      risk_class: moderate
      allow_provider_calls: true
      allow_code_changes: false
      allow_install: false
      requires_human_approval: false
    ui:
      position: { x: 60, y: 160 }
  - node_id: node_code_fix
    kind: worker
    role: coder
    label: Apply Code Fix
    card_ref: agent_card_code_worker
    routing:
      selection_mode: explicit
      provider_id: qwen
      model_id: qwen3-coder-plus
      reasoning_effort: high
    prompt:
      template_mode: inline
      template: |
        Apply the bounded fix only within the approved file set.
    tools:
      approval_mode: ask
      allowed_tool_classes: [read_file, edit_file, shell]
      supports_apply_patch: true
    input_contract:
      mode: structured_inputs_and_artifacts
      required_artifact_kinds: [structured_json]
    output_contract:
      mode: structured_and_artifacts
      machine_result_schema_ref: schema.code_fix_result
      artifact_specs:
        - kind: code_diff
          id: bounded_patch
        - kind: text_report
          id: fix_summary
      human_summary_required: true
    execution:
      spawn_mode: subagent_worker
      timeout_ms: 180000
      retry_policy:
        max_attempts: 1
      execution_backend: app_server
    safety:
      risk_class: high
      allow_provider_calls: true
      allow_code_changes: true
      allow_install: false
      requires_human_approval: true
      approval_kind: filesystem_write_gate
    ui:
      position: { x: 300, y: 160 }
edges:
  - edge_id: edge_plan_fix
    from_node_id: node_plan_fix
    to_node_id: node_code_fix
    edge_type: context_handoff
    handoff_contract:
      message_template: |
        Use the approved file set and implementation plan.
      message_part_modes: [structured_json, human_summary]
      required_output_schema_refs: [schema.plan_fix_result]
    context_policy:
      policy_id: policy_plan_fix
      history_mode: latest_summary_only
      artifact_mode: required_output_only
      exclude_private_memory: true
      include_machine_results: true
      include_human_summaries: true
      summary_strategy: human_and_machine
    ui:
      position: { x: 180, y: 160 }
state_version: 1
```

## Example 2: Provider Update / Smoke / Gate

### JSON

```json
{
  "schema_version": "astrabridge-agent-orchestration-graph-v1",
  "graph_id": "graph_provider_update_smoke_v1",
  "task_id": "task_example",
  "title": "Provider Update / Smoke / Gate",
  "template_id": "provider_update_smoke_gate",
  "status": "draft",
  "metadata": {
    "description": "Provider/model update detection with smoke validation and manual promotion gate.",
    "tags": ["providers", "smoke", "gate"],
    "created_at": "2026-07-07T00:00:00+09:00",
    "updated_at": "2026-07-07T00:00:00+09:00"
  },
  "graph_policy": {
    "entry_node_ids": ["node_discover"],
    "max_depth": 2,
    "default_permission_mode": "ask",
    "default_collaboration_mode": "default",
    "default_execution_backend": "app_server",
    "requires_dry_run_before_live": true
  },
  "nodes": [
    {
      "node_id": "node_discover",
      "kind": "extractor",
      "role": "researcher",
      "label": "Discover Provider Update",
      "card_ref": "agent_card_provider_discovery",
      "routing": {
        "selection_mode": "explicit",
        "provider_id": "qwen",
        "model_id": "qwen3-coder-plus",
        "reasoning_effort": "medium"
      },
      "prompt": {
        "template_mode": "inline",
        "template": "Collect provider/model release changes and normalize the findings."
      },
      "tools": {
        "approval_mode": "ask",
        "allowed_tool_classes": ["web", "read_file"],
        "supports_web": true
      },
      "input_contract": {
        "mode": "task_context"
      },
      "output_contract": {
        "mode": "structured_and_artifacts",
        "machine_result_schema_ref": "schema.provider_update_discovery",
        "artifact_specs": [
          { "kind": "structured_json", "id": "provider_change_bundle" }
        ],
        "human_summary_required": true
      },
      "execution": {
        "spawn_mode": "isolated_lane",
        "timeout_ms": 120000,
        "retry_policy": { "max_attempts": 1 },
        "execution_backend": "app_server"
      },
      "safety": {
        "risk_class": "moderate",
        "allow_provider_calls": false,
        "allow_code_changes": false,
        "allow_install": false,
        "requires_human_approval": false
      },
      "ui": {
        "position": { "x": 80, "y": 160 }
      }
    },
    {
      "node_id": "node_gate",
      "kind": "gate",
      "role": "gate",
      "label": "Manual Promotion Gate",
      "card_ref": "agent_card_manual_gate",
      "routing": {
        "selection_mode": "none"
      },
      "prompt": {
        "template_mode": "inline",
        "template": "Present the smoke and compatibility evidence for human approval."
      },
      "tools": {
        "approval_mode": "ask",
        "allowed_tool_classes": []
      },
      "input_contract": {
        "mode": "structured_inputs_and_artifacts",
        "required_artifact_kinds": ["validation_report"]
      },
      "output_contract": {
        "mode": "structured_and_artifacts",
        "machine_result_schema_ref": "schema.provider_gate_decision",
        "artifact_specs": [
          { "kind": "approval_record", "id": "promotion_decision" }
        ],
        "human_summary_required": true
      },
      "execution": {
        "spawn_mode": "manual_only",
        "timeout_ms": 0,
        "retry_policy": { "max_attempts": 1 },
        "execution_backend": "human_review"
      },
      "safety": {
        "risk_class": "high",
        "allow_provider_calls": false,
        "allow_code_changes": false,
        "allow_install": false,
        "requires_human_approval": true,
        "approval_kind": "provider_call_gate"
      },
      "ui": {
        "position": { "x": 620, "y": 160 }
      }
    }
  ],
  "edges": [
    {
      "edge_id": "edge_smoke_gate",
      "from_node_id": "node_smoke",
      "to_node_id": "node_gate",
      "edge_type": "approval_dependency",
      "handoff_contract": {
        "message_template": "Review the smoke matrix and blocked cases before promoting this update.",
        "message_part_modes": ["structured_json", "artifact_ref", "human_summary"],
        "required_output_schema_refs": ["schema.provider_smoke_matrix"]
      },
      "context_policy": {
        "policy_id": "policy_smoke_gate",
        "history_mode": "explicit_refs_only",
        "artifact_mode": "required_output_only",
        "exclude_private_memory": true,
        "include_machine_results": true,
        "include_human_summaries": true,
        "summary_strategy": "human_and_machine",
        "history_length": 0,
        "included_artifacts": ["smoke_matrix", "compatibility_report"]
      },
      "ui": {
        "position": { "x": 500, "y": 160 }
      }
    }
  ],
  "ui": {
    "layout_version": 1,
    "viewport_hints": {
      "canvas_priority": "high"
    }
  },
  "migration": {
    "source_kind": "native_authoring",
    "compiled_task_graph_version": "astrabridge-task-graph-v1"
  },
  "state_version": 1
}
```

## Validation Expectations For Step 4

The next step should validate at least:

1. graph id, node id, and edge id uniqueness
2. legal role/kind combinations
3. legal edge type and handoff-contract requirements
4. provider/model/profile references
5. prompt variable schema shape
6. output schema and artifact spec presence
7. explicit safety gates for high-risk nodes
8. depth limits and recursion limits
9. migration from existing `TaskGraphDefinition`
10. lowering compatibility into `TaskGraphDefinition`

## Product Boundary Rules

Rules frozen by this contract:

1. `Task` remains the user-visible work unit.
2. The graph is an execution surface inside the task.
3. Internal threads and provider lanes remain implementation details unless
   surfaced as artifacts, node state, or timeline facts.
4. Code-first graph files are product artifacts, not debug leftovers.
5. Prompt contracts, output contracts, and handoff contracts are user-visible
   editing concepts.
6. Secrets and provider-private opaque reasoning are never canonical graph
   content or normal artifact payloads.

## Step 3 Acceptance Check

This document satisfies Step 3 because:

- it defines a versioned `AgentOrchestrationGraph` contract
- it explicitly chooses a wrapper that compiles to current
  `TaskGraphDefinition`
- it includes two example graph payloads
- it includes compatibility and migration notes for existing task graphs
- it defines schema ownership and type synchronization direction
