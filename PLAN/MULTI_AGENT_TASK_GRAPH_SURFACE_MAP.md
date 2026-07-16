# Multi Agent Task Graph Surface Map

Last updated: 2026-07-07

## Purpose

This document maps AstraBridge's existing task, lane, artifact, update-pipeline,
and desktop workflow surfaces to the internal multi-agent task graph contract
defined in `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md`.

The goal is reuse, not duplication. AstraBridge already has durable task-owned
lane state, handoff evidence, artifact references, update-run contracts, and UI
workflow summaries. The task graph system should extend those surfaces where
they are already aligned and only add new state where the current product model
does not yet represent graph definitions or graph runs.

## Boundary Reminder

- User-visible boundary remains `Project -> Task`.
- Provider threads, runtime threads, Codex threads, and future subagent lanes
  remain internal execution details unless deliberately surfaced as workflow
  nodes or timeline rows.
- Secrets, provider-private reasoning, and opaque provider artifacts must not be
  promoted into reusable graph artifacts or downstream machine inputs.

This boundary is already reflected in:

- `docs/APP_HARDENING_STATE_INVARIANTS.md:18-21`
- `docs/APP_HARDENING_STATE_INVARIANTS.md:36-52`
- `docs/ARCHITECTURE.md:149-180`

## Reuse Map

### 1. Task State Is The Correct Graph Owner

Current state:

- `task_service.py` creates task-owned durable state with `task_id`, title,
  active provider thread, provider thread entries, handoff events, goal, plan,
  and artifact reference buckets.
- See `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py:592-616`.

Contract mapping:

- `graph_definition.task_id` should point to the existing AstraBridge task id.
- `task_graph_run.task_id` should also point to the existing task id.
- Graphs and runs should be persisted under task-owned state rather than under a
  new product-level root.

Implication:

- Step 5 should extend task state with graph refs and run refs instead of
  creating a parallel graph store that bypasses the task.

### 2. Provider Thread Entries Are The Closest Existing Runtime Carrier For Node Runs

Current state:

- Task binding already stores route-authoritative runtime metadata per provider
  thread: `thread_id`, `profile_id`, `provider_id`, `model`,
  `reasoning_effort`, `permission_mode`, `collaboration_mode`,
  `execution_backend`, `name`, `created_at`, and `updated_at`.
- See `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py:618-681`.

Contract mapping:

- `agent_node.provider_id`, `agent_node.model_id`, `agent_node.reasoning_effort`,
  `agent_node.permission_mode`, `agent_node.collaboration_mode`, and
  `agent_node.execution_backend` can reuse the same route vocabulary.
- `task_graph_run.node_runs[*].runtime_lane_ref` should initially resolve to a
  provider thread entry or a future subagent lane entry, not to a new free-form
  runtime object.

What stays internal:

- Raw `thread_id` remains an internal execution reference. It can appear inside
  node-run state and diagnostics, but it must not become the primary user-level
  object in the graph UI.

### 3. Handoff Events Already Model Controlled Cross-Lane Transitions

Current state:

- `record_provider_handoff()` binds the target lane, records source and target
  route metadata, projection warnings, dropped artifacts, repaired tool pairs,
  replayable artifact counts, and timestamps.
- `lane_state()` already summarizes `lane_count`, `handoff_count`, active lane,
  previous lane, and latest compact handoff.
- See `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py:345-485`.

Contract mapping:

- Existing provider handoff records are natural predecessors for
  `run_event.type = lane_transition`, `artifact_projection_warning`, and
  `node_retry`.
- `transition_summary` already contains several fields that belong in graph run
  diagnostics: projection mode, warning list, dropped artifacts, and replayable
  artifact counts.

Gap:

- Handoff events are lane-centric, not node-centric. The graph runtime still
  needs first-class `run_event` records keyed by `run_id` and `node_id`, with
  the current handoff object reused as one event subtype rather than as the full
  graph timeline.

### 4. Task Conversation Projection Already Hides Internal Thread Churn Behind One Task View

Current state:

- `TaskConversationService.conversation()` merges turns from task-owned provider
  threads and projects handoff events into one composite task thread.
- `digest()` builds a task-level secret-redacted summary over turns and handoff
  events.
- See `apps/astrabridge-sidecar/astrabridge_sidecar/task_conversation_service.py:46-133`.

Contract mapping:

- The graph UI should preserve the same product rule: users interact with one
  task, while node activity and worker churn are projected into that task as
  structured run rows and node timeline entries.
- `message_envelope` and `message_part` should be normalized graph execution
  structures, but their user-facing projection should follow the same
  composite-task rendering strategy.

Gap:

- The current conversation service is transcript-first. The graph runtime needs
  artifact-first node outputs and explicit machine-result storage, with
  conversation projection treated as a read model instead of the durable source
  of truth.

### 5. Existing Artifact Ref Buckets Already Match The Contract Direction

Current state:

- Task state already owns `checkpoint_refs`, `verification_refs`,
  `diagnostic_refs`, `asset_context_refs`, and `context_pack_refs`.
- See `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py:536-588`
  and `:592-616`.

Contract mapping:

- These buckets are the nearest existing substrate for `artifact_ref` storage.
- The graph runtime should categorize worker outputs and validation reports into
  the same controlled artifact families rather than inventing incompatible
  attachment paths.
- `context_policy.resource_refs` can align with `context_pack_refs` and
  `asset_context_refs`.

Gap:

- Current refs are task-scoped lists, not graph-run-scoped objects with stable
  `artifact_id`, `produced_by_node_id`, `run_id`, output schema, provenance, and
  lifecycle state. Step 5 or Step 12 needs that graph-specific extension.

### 6. Desktop Workflow Facts Already Provide A Minimal Timeline Summary Surface

Current state:

- `taskWorkflowFacts.ts` summarizes lane count, handoff count, checkpoint count,
  command count, diagnostic count, backend, and merged checkpoint/command/
  diagnostic refs from task state plus event summaries.
- See `apps/astrabridge-desktop/src/features/runtime/taskWorkflowFacts.ts`.

Contract mapping:

- This is the right starting point for graph workspace summary chips, a run
  readiness panel, and a timeline sidebar.
- Existing workflow facts can be extended with graph-specific counts such as
  node count, ready/blocked node count, approval gate count, run status, and
  artifact count.

Gap:

- The current summary model has no awareness of `graph_definition`, `agent_node`,
  `agent_edge`, `task_graph_run`, or node-level status. It is an input to the
  future graph UI shell, not a substitute for graph state.

### 7. Agentic Update Pipeline Already Has The Strongest Existing Run Contract

Current state:

- `AgenticUpdateService` already supports `start`, `status`, `result`,
  `validate`, `apply`, `rollback`, code-change planning, and kernel verify.
- It uses a durable `run_id`, `run_contract`, artifact paths, summaries,
  validation reports, apply manifests, and rollback manifests.
- See `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py:56-160`.

Contract mapping:

- The graph runtime should reuse this discipline for run lifecycle,
  human-approval gates, validation artifacts, apply/rollback evidence, and
  secret-free summaries.
- Step 14 should explicitly align node-level approvals and rollback-capable
  actions with this update-pipeline pattern instead of inventing a weaker
  approval model.

Gap:

- The update pipeline is single-run-contract orchestration, not a reusable
  graph-definition system. It does not persist nodes, edges, or per-node
  context policies.

### 8. Automation Architecture Is Relevant As A Trigger And Inbox Pattern, Not As Graph State

Current state:

- Architecture docs already describe automation definitions, runs, inbox items,
  and durable state under `.astrabridge/automations/`.
- See `docs/ARCHITECTURE.md:149-180`.

Contract mapping:

- Automation can later become a graph-run trigger or a consumer of graph
  artifacts and approvals.
- Inbox patterns are relevant for pending review gates and post-run summaries.

What must remain separate:

- Automation ownership and scheduling state should not become the primary store
  for graph definitions or graph execution runs inside a live user task.

## Extension Map

The following contract objects do not have a direct product-grade home yet and
must be added:

### Missing persisted objects

- `graph_definition`
- `agent_node`
- `agent_edge`
- `context_policy`
- `task_graph_run`
- node-run state keyed by `run_id` and `node_id`
- graph-scoped `artifact_ref` records with stable `artifact_id`
- graph validator fixtures and schema versions

### Missing APIs

- list templates
- instantiate template into current task
- read graph definition
- update node position/configuration
- update edge/context policy
- dry-run graph validation
- create/cancel/read graph runs

### Missing GUI surfaces

- graph workspace entrypoint in task UI
- template picker
- graph canvas
- node inspector
- edge inspector
- run timeline with node status and artifact chips
- approval/review gate panel

## Internal-Only Fields And Behaviors

The following should remain internal implementation details even after graph
support lands:

- raw provider `thread_id`
- provider-private reasoning or hidden thinking payloads
- provider-private opaque response ids when they are not needed for user-visible
  troubleshooting
- scratchpad or unreviewed subagent internal notes
- raw vault contents, API keys, bearer tokens, cookies, auth headers, and
  request payload secrets

These may appear in transient runtime memory where necessary, but not as normal
graph artifacts, reusable machine input, or default GUI-visible fields.

## Concrete Design Consequences

1. Persist graph objects inside task state, with task-owned refs to graph
   definitions and run summaries.
2. Reuse existing route and lane metadata vocabulary from provider thread
   entries for executable nodes.
3. Treat provider handoff records as one event family inside a richer graph run
   timeline, not as the full graph execution model.
4. Reuse artifact buckets and evidence discipline from task state and agentic
   update runs.
5. Keep the UI task-first: graph nodes and worker runs are projected views over
   internal execution lanes, not a new top-level product boundary.
6. Build validators and fixtures before persistence or UI so these mappings do
   not drift into ad hoc objects.

## Unambiguous Next Step

The next implementation step is Step 4 from the execution plan:

- add contract validators for graph definitions and graph runs
- add positive fixtures for the five v1 templates
- add negative fixtures for missing context policy, invalid artifact refs,
  unsafe write permissions, and missing machine-result schema

Those validators should enforce the reuse and boundary decisions from this
surface map so later persistence and UI code do not fork the model.
