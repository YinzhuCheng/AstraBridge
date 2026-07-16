# Multi Agent Task Graph Internal Contract

Last updated: 2026-07-07

## Purpose

This document defines the internal contract for AstraBridge's multi-agent task
graph system.

The contract is intentionally internal-first. It is not yet an external A2A
wire protocol. Its job is to give AstraBridge one stable source of truth for:

- graph node and edge persistence
- task-graph validation
- run creation and inspection
- subagent or execution-lane spawning
- artifact-first handoff
- GUI editing and dry-run review

The contract must make it possible for a later agent to implement validators,
APIs, state migrations, and GUI editing without reconstructing intent from chat
history.

## Design Rules

1. The graph exists inside one AstraBridge task. It must not replace the task as
   the user-visible work unit.
2. Critical machine-to-machine state must be structured. Natural-language
   summaries are informational, not authoritative.
3. Message history is not durable state. Durable outputs must be artifacts or
   normalized run records.
4. Every edge must carry a context policy. "Share everything" is not a valid
   implicit default.
5. Every executable node must declare its output contract, risk posture, and
   required permissions before execution starts.
6. Worker execution may map to Codex subagent threads, provider lanes, or other
   isolated runtime projections, but those internal details must remain
   subordinate to the graph contract.
7. Secrets and provider-private reasoning must never become normal artifact
   content or downstream machine inputs.
8. The contract must align with existing AstraBridge concepts such as `task_id`,
   `provider_threads`, `diagnostic_refs`, `verification_refs`, and artifact
   paths.

## Object Model

The core object families are:

- `agent_card`
- `graph_definition`
- `agent_node`
- `agent_edge`
- `message_envelope`
- `message_part`
- `context_policy`
- `artifact_ref`
- `task_graph_run`
- `run_event`

## Identifier Model

Every persisted graph or run object must use stable IDs from these families:

- `graph_id`: stable graph definition id inside one task
- `task_id`: owning AstraBridge task id
- `trace_id`: end-to-end request or run lineage id
- `context_id`: shared business or task context id
- `run_id`: execution instance id for one graph run
- `node_id`: stable node id inside one graph
- `edge_id`: stable edge id inside one graph
- `artifact_id`: durable output id
- `event_id`: stable run event id
- `state_version`: optimistic concurrency or reducer version

Rule:

- `graph_id`, `node_id`, and `edge_id` are definition-time ids
- `run_id`, `event_id`, and `artifact_id` are execution-time ids
- `trace_id` spans graph execution and descendant workers

## Top-Level Shapes

### `graph_definition`

```json
{
  "schema_version": "astrabridge-task-graph-v1",
  "graph_id": "graph_...",
  "task_id": "task_...",
  "title": "Code Fix / Test / Review",
  "template_id": "code_fix_test_review",
  "status": "draft",
  "nodes": [],
  "edges": [],
  "graph_policy": {},
  "created_at": "2026-07-07T00:00:00+09:00",
  "updated_at": "2026-07-07T00:00:00+09:00",
  "state_version": 1
}
```

### `task_graph_run`

```json
{
  "schema_version": "astrabridge-task-graph-run-v1",
  "run_id": "graph-run_...",
  "graph_id": "graph_...",
  "task_id": "task_...",
  "trace_id": "trace_...",
  "context_id": "ctx_...",
  "status": "queued",
  "node_runs": [],
  "artifacts": [],
  "events": [],
  "created_at": "2026-07-07T00:00:00+09:00",
  "updated_at": "2026-07-07T00:00:00+09:00",
  "state_version": 1
}
```

## `agent_card`

Purpose:

- describes what a node or worker can do before it is instantiated into a graph

Required fields:

- `agent_card_id`
- `display_name`
- `role`
- `execution_kind`
- `input_modes`
- `output_modes`
- `supported_templates`
- `allowed_tools`
- `default_output_schema`
- `default_context_policy`
- `risk_class`

Important optional fields:

- `provider_preferences`
- `model_preferences`
- `permission_requirements`
- `approval_requirements`
- `artifact_kinds_produced`
- `artifact_kinds_consumed`
- `max_parallelism`
- `supports_subagent_spawn`

`execution_kind` allowed values:

- `supervisor`
- `worker`
- `synthesizer`
- `extractor`
- `validator`
- `reviewer`
- `gate`
- `human_review`

`risk_class` allowed values:

- `low`
- `moderate`
- `high`
- `restricted`

Rule:

- `agent_card` is a reusable capability declaration
- `agent_node` is the graph-specific instantiation of that capability

## `agent_node`

Purpose:

- represents one graph node inside a task graph

Required fields:

- `node_id`
- `graph_id`
- `kind`
- `label`
- `agent_card_ref`
- `execution_policy`
- `output_contract`
- `position`
- `status`

Important optional fields:

- `provider_id`
- `model_id`
- `reasoning_effort`
- `permission_mode`
- `collaboration_mode`
- `execution_backend`
- `budget`
- `human_summary_template`
- `machine_result_schema`
- `ui_hints`
- `artifact_requirements`
- `approval_gate`

`kind` allowed values:

- `supervisor`
- `worker`
- `synthesizer`
- `extractor`
- `validator`
- `reviewer`
- `gate`
- `artifact_source`

`status` allowed values for definitions:

- `draft`
- `ready`
- `invalid`
- `disabled`

`execution_policy` minimum fields:

- `spawn_mode`
- `retry_policy`
- `timeout_ms`
- `allow_provider_calls`
- `allow_code_changes`
- `allow_install`
- `requires_human_approval`

`spawn_mode` allowed values:

- `inline_lane`
- `isolated_lane`
- `subagent_worker`
- `manual_only`

## `agent_edge`

Purpose:

- describes directed information flow between two nodes

Required fields:

- `edge_id`
- `graph_id`
- `from_node_id`
- `to_node_id`
- `edge_type`
- `context_policy`
- `status`

Important optional fields:

- `label`
- `required`
- `input_schema_override`
- `artifact_filters`
- `human_review_required`

`edge_type` allowed values:

- `context_handoff`
- `artifact_handoff`
- `control_dependency`
- `approval_dependency`
- `fanout_branch`
- `fanin_merge`

`status` allowed values:

- `draft`
- `ready`
- `invalid`
- `disabled`

Rule:

- every executable edge must contain a `context_policy`
- every edge must be valid without requiring access to full chat history

## `context_policy`

Purpose:

- defines exactly what a downstream node may see

Required fields:

- `policy_id`
- `history_mode`
- `artifact_mode`
- `exclude_private_memory`
- `include_machine_results`
- `include_human_summaries`

Important optional fields:

- `history_length`
- `artifact_ids`
- `artifact_kinds`
- `resource_refs`
- `field_acl`
- `summary_strategy`
- `provenance_required`

`history_mode` allowed values:

- `none`
- `last_n_messages`
- `latest_summary_only`
- `latest_machine_result_only`
- `explicit_refs_only`

`artifact_mode` allowed values:

- `none`
- `explicit_artifacts`
- `latest_matching_kind`
- `required_output_only`

`summary_strategy` allowed values:

- `no_summary`
- `human_summary_only`
- `machine_result_only`
- `human_and_machine`

Hard rule:

- `exclude_private_memory=true` should be the default expectation for worker
  handoff unless a later policy artifact explicitly permits otherwise

## `message_envelope`

Purpose:

- normalized machine-to-machine transfer object used when one node hands off to
  another or when the runtime spawns a worker execution

Required fields:

- `message_id`
- `trace_id`
- `context_id`
- `task_id`
- `run_id`
- `source_node_id`
- `target_node_id`
- `intent`
- `parts`
- `output_schema`
- `context_policy_snapshot`
- `created_at`

Important optional fields:

- `reference_event_ids`
- `reference_artifact_ids`
- `budget`
- `provenance`
- `metadata`

Rule:

- downstream machine execution must depend on structured fields, not on parsing
  human prose from the summary text

## `message_part`

Purpose:

- typed content fragment inside a `message_envelope`

Required fields:

- `part_id`
- `kind`

Important optional fields by kind:

- `text`
- `data`
- `uri`
- `media_type`
- `artifact_ref`
- `evidence_locations`

`kind` allowed values:

- `text`
- `data`
- `artifact_ref`
- `resource_ref`
- `uri`
- `approval_token`
- `diagnostic_ref`

Rule:

- raw provider-private reasoning is not a valid part kind

## `artifact_ref`

Purpose:

- durable pointer to a produced or consumed output object

Required fields:

- `artifact_id`
- `artifact_kind`
- `task_id`
- `run_id`
- `source_node_id`
- `path`
- `media_type`
- `status`
- `created_at`

Important optional fields:

- `summary`
- `structured_index`
- `source_artifact_ids`
- `provenance`
- `redaction_status`
- `previewable`

`artifact_kind` allowed values:

- `text_report`
- `structured_json`
- `code_diff`
- `test_report`
- `validation_report`
- `screenshot`
- `image`
- `audio`
- `video`
- `document_extract`
- `graph_definition`
- `run_summary`
- `approval_record`
- `diagnostic_bundle`

`status` allowed values:

- `pending`
- `ready`
- `partial`
- `blocked`
- `redacted`
- `failed`

Hard rule:

- artifacts must point to allowed workspace or product-controlled paths only
- secrets and provider-private opaque reasoning cannot be stored as normal
  artifacts

## `output_contract`

Purpose:

- describes what an executing node must produce

Required fields:

- `machine_result_schema`
- `human_summary_required`
- `artifact_outputs`

Important optional fields:

- `confidence_required`
- `next_action_hints_allowed`
- `provenance_required`
- `blocking_issue_schema`

Rule:

- every executable node must declare a machine result schema or explicitly
  declare that it is artifact-only

## `task_graph_run`

Required fields beyond the top-level shape:

- `status`
- `entry_node_ids`
- `node_run_states`
- `artifact_refs`
- `event_refs`
- `approval_state`
- `run_policy_snapshot`

`status` allowed values:

- `queued`
- `ready_for_dry_run`
- `dry_run_running`
- `dry_run_blocked`
- `dry_run_passed`
- `running`
- `paused_for_review`
- `partial`
- `cancelled`
- `failed`
- `completed`
- `rolled_back`

## `node_run_state`

Purpose:

- runtime projection of one node during a specific run

Required fields:

- `node_id`
- `run_id`
- `status`
- `attempt_count`
- `started_at`
- `updated_at`

Important optional fields:

- `execution_thread_ref`
- `provider_id`
- `model_id`
- `worker_origin`
- `artifact_ids`
- `latest_event_id`
- `blocked_reason`
- `approval_state`
- `warnings`

`status` allowed values:

- `queued`
- `waiting_on_dependencies`
- `ready`
- `dry_run_blocked`
- `dry_run_passed`
- `running`
- `waiting_on_approval`
- `waiting_on_artifact`
- `partial`
- `blocked`
- `cancelled`
- `failed`
- `completed`

`worker_origin` allowed values:

- `provider_lane`
- `codex_subagent`
- `manual`
- `automation`
- `fixture_runner`

## `run_event`

Purpose:

- append-only durable execution event

Required fields:

- `event_id`
- `run_id`
- `task_id`
- `trace_id`
- `event_type`
- `created_at`

Important optional fields:

- `node_id`
- `edge_id`
- `artifact_id`
- `thread_ref`
- `summary`
- `machine_payload`
- `diagnostic_ref`

`event_type` allowed values:

- `run_created`
- `run_dry_run_started`
- `run_dry_run_completed`
- `node_queued`
- `node_started`
- `node_progress`
- `node_completed`
- `node_blocked`
- `node_failed`
- `node_cancelled`
- `artifact_created`
- `artifact_redacted`
- `approval_requested`
- `approval_resolved`
- `handoff_created`
- `run_cancel_requested`
- `run_cancelled`
- `run_completed`
- `run_failed`
- `run_rolled_back`

Rule:

- `run_event` is append-only durable state
- reducers may build UI state from events, but events are the audit record

## Review And Approval State

### `approval_state`

Allowed values:

- `not_required`
- `pending`
- `approved`
- `rejected`
- `expired`

### `review_kind`

Allowed values:

- `human_gate`
- `policy_gate`
- `provider_call_gate`
- `filesystem_write_gate`
- `external_write_gate`
- `install_gate`

Hard rule:

- a node with `requires_human_approval=true` cannot enter `running` until
  approval state is `approved`

## Route-Authoritative vs UI-Informational Fields

### Route-authoritative fields

These may affect execution, validation, or safety:

- node `kind`
- node `execution_policy`
- node `output_contract`
- node `provider_id`
- node `model_id`
- edge `edge_type`
- edge `context_policy`
- run `status`
- node-run `status`
- approval state
- artifact `status`

### UI-informational fields

These may shape presentation but must not by themselves change execution:

- `label`
- `display_name`
- `summary`
- `ui_hints`
- `previewable`
- visual position fields

### Verification-only fields

These prove or explain behavior but do not by themselves execute it:

- `diagnostic_ref`
- `provenance`
- `warnings`
- `redaction_status`
- `reference_event_ids`
- `reference_artifact_ids`

## Minimum Validation Rules

At minimum, a validator should reject:

1. a graph with duplicate `node_id` or `edge_id`
2. an executable edge without a `context_policy`
3. an executable node without an `output_contract`
4. a node that requests high-risk execution without a review path
5. an edge that references unknown node ids
6. a graph whose entry nodes are empty
7. an artifact ref outside allowed workspace or product-controlled paths
8. a machine result schema that is missing for nodes that are not artifact-only
9. a node or edge status not in the allowed vocabulary
10. a worker handoff policy that implicitly shares full private memory

## Relationship To Existing AstraBridge State

This contract should map onto existing product state as follows:

- `task_id` maps to AstraBridge task identity
- `execution_thread_ref` may point to a provider thread or Codex thread, but
  remains internal
- `artifact_ref` should align with existing `verification_refs`,
  `diagnostic_refs`, `checkpoint_refs`, or future graph-specific refs
- `run_event` should be renderable into task activity and diagnostics without
  creating separate user-visible thread objects

## Entry Criteria For Step 3

The next step may assume:

- graph execution is task-owned, not thread-owned
- artifacts and run events are the durable cross-node boundary
- context policy is mandatory on every executable edge
- node/run status vocabularies are now fixed enough to map against current
  task/lane/artifact/update-pipeline surfaces
