# AstraBridge Stability, Protocol, And Agent Runtime Execution Plan

## Plan Authority And Existing-Plan Relationship

This file is the single execution source of truth for the following scope:

- reliable multi-provider runtime isolation;
- durable task-graph scheduling, cancellation, retry, resume, and recovery;
- canonical protocol schemas and cross-provider agent communication;
- one MCP tool/resource/multimodal capability plane;
- Graph Definition / Compiled Plan / Run Event separation;
- registry-driven graph authoring and optional ComfyUI/LangGraph interoperability;
- observability, fault injection, migration, and release gates for the above.

Existing plans and artifacts remain preserved. This plan does not restart or invalidate work that is still proved by repository evidence.

| Existing source | Relationship to this plan | Execution rule |
| --- | --- | --- |
| `PLAN/ASTRABRIDGE_STANDARDIZATION_UI_LIVE_DOGFOOD_EXECUTION_PLAN.md` | completed product and live-dogfood evidence | inherit evidence; do not reopen |
| `PLAN/AGENT_ORCHESTRATION_PRODUCTIZATION_HANDOFF_PLAN.md` | completed orchestration productization baseline | inherit contracts, UI, fixtures, and reports; do not reopen |
| `PLAN/MULTI_AGENT_TASK_GRAPH_EXECUTION_PLAN.md` and completed graph/runtime follow-ons | completed task-graph baseline | preserve implementation and regression evidence; do not restart |
| `PLAN/ASTRABRIDGE_APP_HARDENING_EXECUTION_PLAN.md` | completed 20/20 hardening round | reuse process, MCP, artifact, redaction, and UI evidence |
| provider compatibility and multimodal adapter plans marked complete | provider/model truth and modality qualification evidence | remain independent maintenance inputs; may not define a second agent envelope, run state, or MCP contract |
| `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md` and other `*_CONTRACT.md` files | normative input and migration evidence | preserve; reconcile into canonical schemas rather than copying fields ad hoc |
| `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` | stale progress record with overlapping MCP/capability work | reconcile in Step 1; overlapping runtime/MCP work is owned here |
| Step-0-only communication, GUI orchestration, ComfyUI, multimodal graph, and graph-product plans | stale or overlapping product breadth plans | their unfinished stability/protocol goals are absorbed here; do not execute them in parallel while this plan is active |
| benchmark and future product-breadth plans | deferred reference | reconsider only after Step 22 closes the reliability gate |

In particular, this plan absorbs the overlapping unfinished goals in:

- `PLAN/MULTI_AGENT_COMMUNICATION_UI_EXECUTION_PLAN.md`;
- `PLAN/MULTI_AGENT_COMMUNICATION_GUI_HANDOFF_PLAN.md`;
- `PLAN/MULTI_AGENT_GUI_ORCHESTRATION_HANDOFF_PLAN.md`;
- `PLAN/AGENT_GRAPH_COMFYUI_PRODUCTIZATION_HANDOFF_PLAN.md`;
- `PLAN/AGENT_GRAPH_MULTIMODAL_PRODUCT_EXECUTION_PLAN.md`;
- the Step-0-only Agent Graph product/visual/orchestrator plans.

Those files remain historical evidence or future product-breadth references. They are not coequal schedulers for this scope.

## Total Objective

Upgrade AstraBridge from a feature-rich multi-provider Codex shell into a dependable multi-provider agent runtime with explicit, enforceable protocol boundaries:

1. Provider adapters translate provider/model protocols into a canonical model IR and never own cross-agent workflow state.
2. MCP is the only normal tool, resource, and multimodal capability plane, including internal loopback calls.
3. Agent-to-agent communication uses a versioned AstraBridge envelope aligned with A2A concepts, not MCP tool calls and not provider-private transcripts.
4. The graph kernel owns durable scheduling, retries, cancellation, recovery, idempotency, and run events independently of HTTP/UI lifetimes.
5. The graph GUI edits canonical definitions through a NodeType registry; compiled plans and run events remain separate projections.
6. Cross-provider fan-out/fan-in, handoff, crash recovery, and tool execution are proved by deterministic fault tests and release gates.

The final outcome is not merely a new document or a redesigned canvas. It is a production-credible reliability spine whose behavior remains correct across provider switches, parallel agents, process restarts, connection loss, duplicate delivery, and malformed external responses.

## Deliverables

- A provider/runtime client pool with isolated, concurrently safe lanes.
- A versioned canonical protocol schema package with deterministic Python and TypeScript generation/validation.
- A workspace-local durable run/event store and asynchronous graph scheduler.
- A versioned Agent Envelope, delivery ledger, typed port projection, and cross-provider context bridge.
- A shared MCP core and internal broker used by all normal tool/resource/multimodal invocation paths.
- Structured multimodal MCP results, workspace-scoped artifact references, and node-level least-privilege policy enforcement.
- Desktop-Sidecar supervision with readiness, bounded restart, logs, and active-run reattachment.
- Cross-layer tracing, reliability SLOs, deterministic failure injection, and release gates.
- A canonical NodeType registry, registry-driven graph GUI, and optional ComfyUI/LangGraph adapters with explicit loss reports.
- Migration, rollout, rollback, dogfood, and final validation evidence preserved under named workspace-local validation paths.

## Architectural Invariants

### Provider Plane

- Provider-specific request/response formats terminate at provider adapters.
- Provider-private reasoning state, encrypted state, hidden tool metadata, and raw authentication material must never enter the canonical Agent Envelope.
- Provider/model selection is configuration on an agent node or execution lane, not a new task or user-visible project boundary.
- Concurrent provider lanes must not share mutable client lifecycle, process-global credentials, or callback state.

### MCP Capability Plane

- All normal tools, resources, image, vision, audio, video, document, and other capability invocations pass through the MCP broker contract.
- Internal calls may use an in-process loopback transport, but must retain the same MCP request/result, policy, audit, timeout, and error semantics.
- `web.search` remains a standalone web lane. Exposing or invoking it through the MCP broker does not turn it into a model-backed capability.
- MCP exposure filtering is not a security boundary. The broker must re-authorize every dispatch against run, node, attempt, user/project, and approval context.
- MCP Tasks may be used only behind negotiated capability flags while the upstream feature remains experimental; they are not AstraBridge's canonical run-state source.

### Agent Communication Plane

- Agent communication uses AstraBridge-owned, versioned `AgentEnvelope`, `AgentTask`, `ContentPart`, `ArtifactRef`, and delivery events aligned with A2A concepts.
- Delivery semantics are at-least-once plus durable idempotency and deduplication. The product must not claim network-level exactly-once delivery.
- A message is immutable after acceptance. Acknowledgement, rejection, retry, and delivery status are separate events.
- Typed content and artifact references are authoritative; human summaries and UI previews are projections only.
- Context policies are explicit, budgeted, persisted, and validated before provider dispatch.

### Graph Plane

- `Graph Definition -> Compiled Plan -> Run Events/Projection` is a one-way ownership chain.
- The GUI edits Graph Definition only. A running graph must not mutate its definition to record runtime state.
- The scheduler and durable store are the only owners allowed to advance live run/node state.
- Terminal states are monotonic and protected by state-version compare-and-swap.
- Retries create attempts; they do not overwrite earlier attempt evidence.

### Artifact And Security Plane

- Normal project state remains under `.abproj` and workspace-local `.astrabridge/` only.
- Artifact references use workspace-scoped URIs, media type, size, digest, and lineage. Provider-returned filesystem paths are untrusted input.
- URI resolution must re-check that the target remains in the current workspace allowlist.
- Durable logs, traces, validation artifacts, and reports must be redacted before persistence and must never contain API keys, bearer tokens, cookies, authorization headers, or provider raw secrets.

## Constraints And Attention Notes

1. Preserve `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` exactly as the completed historical execution record unless the user explicitly asks to change it.
2. Preserve existing `.abproj`, `.astrabridge/`, `PRIVATE/**`, fixtures, raw experiment records, logs, caches, screenshots, and validation reports by default.
3. Do not reintroduce `.lcr*`, `.codexproj`, `.codex-shell`, official OpenAI account login, or writes to official Codex configuration.
4. Do not read plaintext Desktop key files or other secret sources unless the user explicitly authorizes that exact read for the current task.
5. Prefer a strangler migration behind validated contracts. Do not rewrite `runtime_service.py`, `task_service.py`, or `TaskGraphWorkspace.tsx` wholesale.
6. Generated AstraBridge protocol types must use a directory distinct from the existing Codex/app-server generated protocol tree so upstream refreshes cannot overwrite them.
7. Schema writers support the current version; readers support the explicitly documented compatibility window, initially current and N-1 where feasible.
8. No compatibility fallback may silently discard typed parts, artifacts, node configuration, security policy, or unsupported external workflow nodes.
9. Real provider calls are optional evidence, not the primary test mechanism. Prefer deterministic fake providers and MCP fixtures; record and bound any approved live cost-bearing smoke.
10. No external platform writeback is authorized by this plan.
11. Before and after local Desktop/Sidecar development, audit expected ports and AstraBridge-owned processes. Reap only clearly stale AstraBridge instances, using launch records and listeners rather than parent PID alone.
12. If a step touches UI behavior, perform visual QA and preserve screenshots. Documentation is not a substitute for usable UI.
13. If a step changes a canonical owner or bridge, update `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` and `scripts/contract_boundary_audit.py` in the same step.
14. Rewriting this plan from Step 0 is a plan-document reset, not a work reset. Preserve validated code and evidence unless current evidence contradicts it.
15. Each execution round completes exactly one full numbered step, then updates this file's status and append-only progress log before stopping.

## Baseline Evidence And Known Gaps

The following evidence was verified during plan creation on 2026-07-16. Future agents must re-check the relevant code before implementation, but must not repeat a repository-wide audit without contradictory evidence.

- `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/base.py:35` and `providers/ir.py:7` prove that provider transports and a normalized response IR already exist.
- `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py:164` still owns one mutable `_client` and `_runtime_signature`; signature changes close the current client near `runtime_service.py:6387`.
- `runtime_service.py:6273` mutates process-global environment during runtime preparation, which is unsafe for concurrent provider lanes and must be replaced with per-process/per-lane injection.
- `apps/astrabridge-sidecar/astrabridge_sidecar/server.py:1165` directly waits for `execute_task_graph_run`; the live graph run is still coupled to the request lifetime.
- Live attempts are recorded as one near `runtime_service.py:1962` and `runtime_service.py:2165` even though retry policy exists in compiled graphs.
- `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py:3855` primarily changes persisted cancellation state without reliably interrupting the active live worker; live recovery remains fixture-only near `task_service.py:4028`.
- `PLAN/MULTI_AGENT_TASK_GRAPH_INTERNAL_CONTRACT.md:341` already specifies a message envelope concept, while the live path still relies heavily on summary/preview/path handoff near `runtime_service.py:2520`.
- The canonical orchestration contract already has typed ports and handoff validation in `agent_orchestration_contract.py:20` and `agent_orchestration_contract.py:767`; the missing work is enforcing them in the live path.
- Cross-provider history projection creates neutral messages, but the live handoff path mainly records counts, warnings, and preview near `runtime_service.py:7699` instead of injecting the full validated neutral payload.
- Dynamic capabilities can still call Python services directly near `runtime_service.py:7356`, bypassing a single MCP transport/policy/audit path.
- `astrabridge_capabilities_mcp_server.py:42` echoes a requested protocol version, `:185` serializes results primarily as text JSON, and `:207` implements bespoke framing; other in-repo MCP servers duplicate similar protocol code.
- Node tool policy is coarse near `runtime_service.py:3408`; enabling tools can expose a much wider dynamic tool set than the node-specific contract implies.
- `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx:291` hard-codes palette roles in a very large component rather than projecting a canonical NodeType registry.
- `apps/astrabridge-desktop/src-tauri/src/main.rs:11` uses a fixed Sidecar port and the launcher path near `main.rs:153` lacks a complete readiness/restart/log supervision state machine.
- `docs/INTERFACE_GOVERNANCE.md:116` records that many request/response contracts remain inline Python/TypeScript rather than generated JSON Schema.

## Adjustment Policy

Agents may reasonably adjust substeps, filenames, commands, storage details, or sequencing when repository evidence requires it. Such adjustments must not:

- change the total objective;
- weaken protocol or reliability guarantees;
- remove negative tests, fault injection, compatibility gates, or security checks;
- replace runtime enforcement with documentation or UI-only projections;
- turn MCP into the agent message bus;
- turn the Agent Envelope into a provider transcript;
- silently drop unsupported data to make an adapter appear compatible;
- discard prior artifacts or validated work.

If a core objective becomes infeasible, record the blocker, inspected evidence, attempted approaches, and a substitute that preserves the original intent. A route change must update the current work unit and append a plan-review log entry before execution continues.

## Evidence Review And Plan Revision Policy

Before starting the next numbered step, inspect the current owner files and the latest relevant validation evidence. Trigger a bounded plan review if any of these are true:

1. current code contradicts the baseline recorded above;
2. a completed step's acceptance evidence does not support its claimed invariant;
3. the next step would build on a schema, store, scheduler, or broker that is no longer the canonical owner;
4. repeated fixes address projections while the durable state or delivery source remains wrong;
5. an upstream MCP, A2A, ComfyUI, LangGraph, Codex/app-server, or provider contract changed incompatibly;
6. the next step would create a second source of truth or silently weaken the objective.

When triggered, record:

- evidence inspected;
- diagnosis;
- the smallest route change;
- what must not be weakened;
- exact next step.

Then execute the revised highest-leverage work unit in the same turn when feasible. Do not turn plan review into a new open-ended audit.

## Execution Rules

1. Requests to continue, execute, implement, build, fix, resume, or advance this objective are execution-mode requests.
2. Start from the earliest incomplete numbered step unless the user explicitly redirects to another step.
3. Complete exactly one full numbered step per user-facing execution round.
4. State the bounded work unit, expected output, and acceptance check before implementation.
5. A step is `completed` only after every listed acceptance criterion is satisfied with observable evidence.
6. Partial work remains `in progress`; do not mark it complete because the turn is ending.
7. If blocked, record the concrete blocker, evidence, attempted routes, and exact next entry point. Do not write vague continuation notes.
8. Update only Current Progress, Current Work Unit, the affected step status, and an append-only Progress Log entry unless evidence requires a route revision.
9. Preserve raw and parsed validation evidence with secrets removed. Do not clean intermediate artifacts unless the user names the cleanup targets.
10. Run tests proportional to risk. A fixture-only result cannot close a live-provider/runtime acceptance criterion that explicitly requires live-path semantics.
11. Before any commit or push, run the applicable local gate and a quick secret scan; never stage raw secret-bearing artifacts.
12. Do not create another active plan for a subpart of this scope. A finite validation checklist or evidence report may be created, but this file remains the scheduler.

## Current Progress

- Current status: Complete
- Completed steps: Step 0, Create Durable Execution Plan; Step 1, Reconcile Plan And Contract Ownership; Step 2, Isolate Provider Runtime Client Lanes; Step 3, Establish Canonical Protocol Schemas And Code Generation; Step 4, Add The Workspace-Local Durable Run And Event Store; Step 5, Move Live Graph Execution To An Asynchronous Durable Scheduler; Step 6, Add Leases, Checkpoints, Startup Reconciliation, And Effect Journaling; Step 7, Implement Production Cancel, Retry, Resume, And Provider Failover Semantics; Step 8, Implement The Versioned Agent Envelope And Delivery Ledger; Step 9, Enforce Typed Port Bindings And Output Schemas In The Live Path; Step 10, Complete Cross-Provider Context Projection And Handoff Continuity; Step 11, Replace Duplicated MCP Protocol Code With One Shared Core; Step 12, Route Every Normal Capability Invocation Through The MCP Broker; Step 13, Add Structured Multimodal MCP Results And Safe Artifact References; Step 14, Enforce Per-Node MCP Tool And Resource Policy; Step 15, Add Desktop-Sidecar Host Supervision And Run Reattachment; Step 16, Add Cross-Layer Tracing, Reliability SLOs, And Redacted Diagnostics; Step 17, Build Deterministic Fault Injection And Conformance Release Gates; Step 18, Introduce The Canonical NodeType Registry And Compiler Interface; Step 19, Make The Graph GUI Registry-Driven And Separate Definition, Plan, And Run; Step 20, Add A Loss-Aware ComfyUI Workflow Adapter; Step 21, Add An Optional LangGraph Adapter Without Core Coupling; Step 22, Migrate, Roll Out, Dogfood, And Close The Reliability Gate
- Current step: Plan complete
- Next step: None. Optional future work only, including the user-deferred Git/GitHub CLI connection revisit after plan completion.
- Last updated: 2026-07-17
- Git/GitHub CLI connection: explicitly abandoned by user for the duration of this execution plan on 2026-07-17; do not retry or treat it as a blocker until every numbered step is complete. Preserve the independent Git remote credential path and all existing working-tree artifacts.

## Current Work Unit

- ID: STAB-22
- Goal: Migrate the new reliability spine through rollout and dogfood without losing graphs, runs, artifacts, or rollback visibility.
- Inputs: the completed protocol/runtime/adapter boundaries from Steps 1-21, durable run state, stability gate infrastructure, migration/rollback constraints, and preserved validation evidence.
- Expected output: a feature-flagged rollout/migration/rollback path with shadow comparison, dogfood evidence, deterministic release-gate coverage, and explicit terminal handling for legacy runs.
- Acceptance check: repeated migration is idempotent, shadow comparison explains no state deltas, rollback preserves inspectability, and the full release gate closes with owned orphan listeners/processes at zero.
- Status: completed
- Next action: Plan complete. Preserve the passing rollout/release evidence, and treat any further work as optional follow-on breadth or the separately deferred Git/GitHub CLI reconnection task.

## Execution Steps

### 0. Create Durable Execution Plan

Goal: Create the durable plan, preserve validated prior work, and define one exact next entry point.

Main actions:

- Record the product objective, protocol boundaries, constraints, evidence baseline, and plan authority.
- Absorb overlapping unfinished stability goals without rewriting completed histories.
- Define bounded steps and observable acceptance criteria.
- Set the first work unit to the finite ownership reconciliation needed before code migration.

Acceptance criteria:

- This plan exists under `PLAN/`.
- It includes objective, deliverables, constraints, adjustment policy, evidence review policy, current progress, current work unit, numbered steps, acceptance criteria, and progress log.
- Completed repository work is explicitly inherited rather than restarted.
- The next execution entry point is unambiguous.

Status: completed

### 1. Reconcile Plan And Contract Ownership

Goal: Eliminate conflicting execution entry points and name the canonical owner for every high-risk contract in this scope.

Main actions:

- Classify relevant plans as `inherited`, `absorbed`, `deferred`, `independent`, or `historical` using current disk evidence.
- Reconcile `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` with the capability/MCP implementation already present and delegate overlapping stability work to this plan.
- Update `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` for canonical protocol schemas, Agent Envelope/delivery events, MCP broker, durable run store/scheduler, NodeType registry, and Desktop projections.
- Extend `scripts/contract_boundary_audit.py` so a second canonical owner or forbidden direct bridge fails deterministically where feasible.
- Add narrow redirect notes only to stale plans that would otherwise remain a conflicting active entry point; preserve their histories and artifacts.

Acceptance criteria:

- Every relevant plan has one recorded relationship to this plan.
- `CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md` no longer schedules overlapping MCP/runtime work as though later implementation did not exist.
- Each protocol/state concern has exactly one named code owner and explicit compatibility/projection boundaries.
- The boundary audit covers the newly named owners and passes.
- Completed plans, reports, fixtures, and validation evidence remain intact.

Status: completed

### 2. Isolate Provider Runtime Client Lanes

Goal: Prevent concurrent provider/model executions from closing, reconfiguring, or contaminating each other's runtime clients.

Main actions:

- Introduce a `RuntimeClientPool` keyed by an immutable, redacted runtime signature.
- Give each lane its own client, lifecycle lock, callback context, active-turn leases, concurrency limit, idle TTL, and bounded restart behavior.
- Reuse one client for equal signatures while allowing different signatures to remain live concurrently.
- Remove process-global `os.environ.update` from concurrent runtime preparation; pass provider configuration only to the owned client/subprocess without logging secrets.
- Update graph and normal-turn callers incrementally; preserve single-lane compatibility during migration.

Acceptance criteria:

- A barrier-controlled test keeps two different provider lanes alive concurrently and both turns finish.
- Closing, restarting, or failing one lane does not terminate another lane's turn.
- Four concurrent acquisitions of the same signature create exactly one client.
- Idle reaping never closes a lane with an active turn lease; shutdown closes all owned lanes cleanly.
- Lane keys, snapshots, and logs contain no credential values.
- Existing single-lane and task-graph runtime tests pass, and the local process audit finds no new stale AstraBridge processes.

Status: completed

### 3. Establish Canonical Protocol Schemas And Code Generation

Goal: Create one versioned JSON Schema 2020-12 source for cross-language runtime and protocol contracts.

Main actions:

- Create a backend-owned schema package for at least `ArtifactRef`, `ContentPart`, `AgentEnvelope`, `AgentTask`, `RunEvent`, capability input/output, Graph Definition, and Compiled Plan.
- Give each schema a stable `$id`, explicit version, shared definitions, and compatibility/migration manifest.
- Generate or deterministically derive Python validators/types and TypeScript types in an AstraBridge-specific generated directory separate from Codex/app-server generated files.
- Provide current-write and documented compatibility-read rules, initially current and N-1 where feasible.
- Migrate existing inline validators through explicit adapters; do not create another independent truth source.

Acceptance criteria:

- The same positive and negative fixtures receive the same verdict in Python and TypeScript.
- Invalid port types, schema references, artifact URIs, private-reasoning fields, and required envelope fields are rejected.
- Migration fixtures are idempotent and preserve IDs, topology, artifact lineage, and security policy.
- Generation is deterministic and a freshness command fails when generated files drift.
- Contract ownership documentation and boundary audit reflect the new schema owner.

Status: completed

### 4. Add The Workspace-Local Durable Run And Event Store

Goal: Establish a transactional source of truth for graph scheduling while retaining current JSON/manifests as exports and UI projections.

Main actions:

- Add a versioned SQLite/WAL store under workspace-local `.astrabridge/` for runs, node attempts, ordered events, leases, outbox, inbox, and external operations.
- Use transactions, unique constraints, and `state_version` compare-and-swap to advance state and append events atomically.
- Make terminal states monotonic and preserve every attempt rather than overwriting evidence.
- Keep current task JSON, manifests, diagnostics, and `PRIVATE/**` reports as preserved projections/exports, not schedulers.
- Define idempotent migration for empty, existing, and legacy-active workspaces; classify unsafe legacy activity as `needs_review` rather than guessing.

Acceptance criteria:

- Empty workspace, existing workspace, and repeated migration all succeed deterministically.
- Concurrent complete/cancel writes yield one valid terminal transition and cannot regress.
- Run and node projections rebuild identically from persisted events after process restart.
- Event plus projection updates cannot be observed half-committed.
- No secret-bearing value is persisted, and legacy manifests/artifacts are not deleted or overwritten.

Status: completed

### 5. Move Live Graph Execution To An Asynchronous Durable Scheduler

Goal: Decouple run execution from HTTP and UI lifetimes and give the scheduler sole authority to advance live state.

Main actions:

- Change live run creation to validate, compile, persist, and quickly return a receipt containing `run_id`, queued status, status endpoint, and event cursor.
- Run dependency resolution, join modes, parallel limits, and attempt dispatch in a background scheduler backed by the durable store.
- Give each attempt an owner boot ID, lease, heartbeat, and expiration.
- Make UI and APIs read projections/events; they must not schedule or advance nodes.
- Retain the synchronous path only as an explicit compatibility adapter during migration, without waiting inline for the entire graph.

Acceptance criteria:

- With a deliberately slow fake provider, run creation returns its receipt within a deterministic 500 ms test budget.
- Closing the HTTP client or Desktop after receiving the receipt does not stop the run.
- Independent nodes execute concurrently up to `max_parallelism`; dependent nodes wait for validated inputs.
- Only the scheduler can move an executing node to its next state.
- Existing graph definition, compilation, and run API compatibility fixtures pass.

Status: completed

### 6. Add Leases, Checkpoints, Startup Reconciliation, And Effect Journaling

Goal: Resume safe work after crashes without duplicating provider turns, handoffs, or external side effects.

Main actions:

- Checkpoint at node-attempt boundaries and persist dispatch intent before external calls.
- Generate stable `operation_id` values and write outbox entries for provider, Agent Envelope, and MCP dispatches.
- Persist known external thread/turn/tool handles and use inbox deduplication for completion/events.
- On startup, reclaim expired leases and reconcile external handles before deciding whether to resume, reattach, retry, or require review.
- Classify operations as `read_only`, `idempotent_write`, or `non_idempotent_write`; never blindly replay an ambiguous non-idempotent effect.

Acceptance criteria:

- Duplicate run-create requests with one idempotency key return the same run.
- Replayed completion and delivery events do not duplicate metrics, handoffs, or downstream nodes.
- A crash before the external call is safely replayed; a crash after a known external handle is accepted reattaches to that handle.
- An ambiguous non-idempotent operation becomes `needs_review` and is never automatically repeated.
- Deduplication and operation evidence survive Sidecar restart.

Status: completed

### 7. Implement Production Cancel, Retry, Resume, And Provider Failover Semantics

Goal: Make live provider-backed behavior match declared graph policies instead of fixture-only projections.

Main actions:

- Persist cancellation tokens, stop new dispatch, and send interrupt to the exact runtime lane/thread/turn.
- Define cancellation grace periods and explicit `cancel_timeout`/`needs_review` outcomes.
- Execute compiled retry policies with failure classification, exponential backoff, jitter, `Retry-After`, and run/node budgets.
- Retry only safe operations; attach new attempts to the same run with complete lineage.
- Add policy-controlled provider fallback at node boundaries without mutating the graph definition or hiding the original failure.
- Promote live recovery to the normal API while preserving explicit fixture compatibility.

Acceptance criteria:

- Cancelling a live fake-provider turn sends an actual interrupt and prevents later provider/tool dispatch.
- Cancel/completion races produce one terminal state; stale snapshots cannot revive a cancelled run.
- 429, temporary 5xx, and safe connection failures increase the real attempt count according to policy.
- Invalid output, permission denial, schema rejection, and ambiguous side effects do not retry automatically.
- Provider failover preserves envelope/artifact lineage and records both the original and fallback attempt.
- Restart recovery safely resumes eligible attempts and surfaces ineligible attempts for review.

Status: completed

### 8. Implement The Versioned Agent Envelope And Delivery Ledger

Goal: Make structured, provider-neutral agent communication the real persisted and delivered payload.

Main actions:

- Implement immutable envelopes with message/idempotency IDs, trace/span, context/task/run, source/target agent-node-provider-model, intent, sequence, correlation/causation, attempt, deadline/TTL, typed parts, schema references, context-policy snapshot, budget, and provenance.
- Model acknowledgement, rejection, retry, and delivery failure as ordered Run Events.
- Map A2A Message/Task/Part/Artifact/AgentCard concepts without binding the internal ABI directly to an external A2A wire version.
- Exclude provider-private reasoning and secrets at construction and validation boundaries.
- Persist envelopes and delivery state in the durable store and expose redacted projections to the UI.

Acceptance criteria:

- A provider-X agent can drive a provider-Y fixture using structured parts only; removing the human summary does not break it.
- Missing or invalid envelope fields fail before the target provider is started.
- Replaying one idempotency key does not execute the target twice.
- Events remain ordered and trace/correlation lineage is queryable end to end.
- Persisted and UI forms are traceable to the same immutable message while remaining redacted.

Status: completed

### 9. Enforce Typed Port Bindings And Output Schemas In The Live Path

Goal: Make compiled port contracts and machine-output schemas operational rather than prompt-only metadata.

Main actions:

- Project edge payloads from compiled `port_bindings`, not summary concatenation.
- Validate the source output, projected payload, target input, and returned machine result against canonical schemas.
- Deliver typed attachments and artifact references through envelope parts.
- Keep raw-text compatibility only behind an explicit migration flag with diagnostics and a removal gate.
- Prevent a node from being marked passed when its declared machine result is invalid.

Acceptance criteria:

- A port type/schema mismatch fails deterministically before provider dispatch.
- A valid structured artifact flows through fan-out/fan-in without relying on preview text or local path parsing.
- Invalid provider output creates a schema failure, not a passed `raw_text` result.
- Both send-side and receive-side validation are covered by positive and negative fixtures.
- Existing v1 graphs either migrate successfully or emit an explicit compatibility diagnostic without silent data loss.

Status: completed

### 10. Complete Cross-Provider Context Projection And Handoff Continuity

Goal: Transfer the validated neutral conversation/task context across provider lanes without leaking provider-private state or relying on truncated previews.

Main actions:

- Feed validated projected messages/envelopes into the target context rather than recording only counts, warnings, and previews.
- Apply persisted context policy, history budget, artifact policy, and provenance at the handoff boundary.
- Repair tool-call/result pairing in the neutral representation before target dispatch.
- Keep provider-native thread state isolated and create a new lane/thread when required.
- Add a small pairwise compatibility matrix across transport families rather than an unbounded provider-by-provider transcript matrix.

Acceptance criteria:

- An A -> B -> C fixture preserves typed content, artifacts, task IDs, and provenance through three different provider transport families.
- Provider-private reasoning/encrypted state is absent from the target payload and durable envelope.
- Context truncation is deterministic, budgeted, and visibly diagnosed.
- Tool-call/result pairs remain valid after projection.
- The target can complete from the neutral payload when provider-specific transcript fields are removed.

Status: completed

### 11. Replace Duplicated MCP Protocol Code With One Shared Core

Goal: Provide one conformant MCP lifecycle and transport implementation for internal and external use.

Main actions:

- Re-verify the current MCP specification and supported protocol versions at execution time.
- Prefer the official SDK when compatibility evidence supports it; otherwise implement one spec-conformant shared core with documented gaps.
- Centralize initialization/version negotiation, capabilities, tools/resources/prompts, errors, timeout, cancellation, progress, payload limits, stdio, and Streamable HTTP behavior.
- Move legacy Content-Length or other custom framing behind an explicit compatibility adapter with telemetry and a removal gate.
- Migrate production MCP servers away from duplicate `_read_message`/dispatch implementations.

Acceptance criteria:

- Supported versions negotiate correctly; unsupported versions fail or downgrade only through documented rules.
- Standard-client golden tests cover multiple stdio messages, notifications, invalid JSON-RPC, timeout, cancellation, and Streamable HTTP session behavior.
- Production MCP servers no longer each define their own protocol reader/lifecycle.
- Loopback, stdio, and Streamable HTTP return semantically equivalent results for one deterministic tool.
- Protocol logs remain redacted and bounded.

Status: completed

### 12. Route Every Normal Capability Invocation Through The MCP Broker

Goal: Eliminate REST/dynamic-tool/automation bypasses while preserving external API compatibility as thin broker clients.

Main actions:

- Introduce an internal MCP broker with in-process loopback plus standard transport adapters.
- Generate MCP tool schemas from canonical capability specifications.
- Route runtime dynamic tools, capability REST handlers, automation calls, web tools, and built-in multimodal tools through the broker.
- Centralize timeout, cancellation, approval, audit, error mapping, replay identity, and artifact handling.
- Add a boundary guard so only broker adapters may directly invoke underlying capability implementations.

Acceptance criteria:

- Instrumentation proves that each normal internal tool/capability call has an MCP request ID, policy decision, operation ID, and audit event.
- A direct call from RuntimeService or a normal API handler to a capability implementation fails a boundary test.
- Existing capability behavior and deterministic fixtures retain parity through the broker.
- The standalone web lane remains independent while its tool invocation uses the shared MCP contract.
- No subprocess is required for safe in-process loopback, but its semantics match external MCP calls.

Status: completed

### 13. Add Structured Multimodal MCP Results And Safe Artifact References

Goal: Preserve modality and artifact semantics instead of reducing results to text JSON and filesystem paths.

Main actions:

- Add `outputSchema`, `structuredContent`, typed image/audio content, resource links, and embedded-resource policy where appropriate.
- Externalize large media to workspace-scoped artifact URIs with media type, size, digest, lineage, and preview metadata.
- Set hard limits for inline binary/text content and frame sizes.
- Revalidate every provider-returned path through the current workspace artifact resolver.
- Update Desktop renderers to consume typed results while retaining safe textual compatibility summaries.

Acceptance criteria:

- Image generation, vision analysis, speech transcription, speech synthesis, and web search each have validated input/output fixtures.
- Image/audio/document results retain media type, digest, size, and lineage and are not represented only by a text path.
- Large payloads are externalized; inline limits are enforced before durable logging.
- URI escape and untrusted provider-path tests fail safely.
- Desktop typed rendering passes component tests and visual QA without exposing unsafe absolute paths.

Status: completed

### 14. Enforce Per-Node MCP Tool And Resource Policy

Goal: Apply least privilege both when tools are exposed and again when they are dispatched.

Main actions:

- Define exact server/tool selectors, resource URI patterns, approval mode, timeout, budget, and effect class on node policy.
- Compute effective policy as graph ceiling intersected with node, project/user, approval, and server availability policy.
- Expand presets at compile time and snapshot the effective policy into the Compiled Plan/run manifest.
- Default to deny for undeclared tools and side effects; migrate coarse `allowed_tool_classes`/`supports_mcp` explicitly.
- Reauthorize broker dispatch using run/node/attempt context even if a model forges a tool name.

Acceptance criteria:

- A node sees and invokes only its allowlisted tools/resources.
- Forged names and direct broker calls are denied before side effects.
- `allow`, `deny`, `ask`, preset drift, approval reuse, budget exhaustion, and resource URI escape fixtures pass.
- Audit events record policy revision, effective policy fingerprint, approval decision, and attempt context without secrets.
- Run replay uses the snapshotted policy rather than silently adopting later preset changes.

Status: completed

### 15. Add Desktop-Sidecar Host Supervision And Run Reattachment

Goal: Give Sidecar launch, readiness, crash recovery, logs, and shutdown clear ownership.

Main actions:

- Replace the fixed-port assumption with a reserved/dynamic port or an equivalent collision-safe handshake.
- Persist a redacted launch record with session/boot ID, PID, port, creation time, executable identity, and owner.
- Add `/readyz` validation for boot ID, build/runtime version, and store schema before the Desktop declares readiness.
- Capture, redact, and rotate stdout/stderr instead of discarding them.
- Monitor child exit with bounded exponential restart and crash-loop circuit breaker; after restart, trigger lease reconciliation and UI run reattachment.
- Use graceful shutdown first and ownership-verified process-tree termination only after timeout.

Acceptance criteria:

- Killing the Sidecar during an active fake run results in safe recovery, reattachment, or explicit review.
- Repeated start failures open a circuit breaker and produce an actionable UI diagnostic rather than an infinite loop.
- Twenty start/exit cycles leave no AstraBridge-owned orphan listener or launcher.
- An unrelated process on a candidate port is never killed.
- Two Desktop instances do not terminate each other's valid Sidecar.
- Logs contain boot/exit lineage but no secrets.

Status: completed

### 16. Add Cross-Layer Tracing, Reliability SLOs, And Redacted Diagnostics

Goal: Make failures attributable across graph, provider, Agent Envelope, MCP, artifact, and host boundaries.

Main actions:

- Propagate trace/run/node/attempt/message/operation IDs across the scheduler, provider lanes, Agent Envelope, MCP broker, and Desktop projections.
- Add stable internal metrics and a mapping layer to current OpenTelemetry semantic conventions rather than binding internal storage to evolving names.
- Record latency, first-token, attempt, retry, provider/model, tool/server, usage/cost when available, error class, cancellation, lease, and recovery outcomes.
- Make content capture opt-in and redacted; arguments/results that may contain user data or secrets are excluded by default.
- Define reliability SLOs and release thresholds.

Acceptance criteria:

- One mixed graph run can be followed from admission through provider/MCP/handoff/artifact completion with one trace lineage.
- Required metrics include cross-provider handoff success, stale run rate, crash recovery success, duplicate-effect count, terminal projection lag, MCP conformance, and p95 node latency.
- Diagnostics distinguish provider, transport, schema, policy, scheduler, tool, artifact, and host failures.
- Secret/redaction tests pass for traces, logs, events, and reports.
- UI diagnostics use the same event source rather than inventing independent state.

Status: completed

### 17. Build Deterministic Fault Injection And Conformance Release Gates

Goal: Prove recovery and interoperability under controlled failure rather than relying on accidental live-provider outages.

Main actions:

- Build fake App Server, provider, MCP, network, and host failpoints.
- Cover crash before dispatch, remote accept before local commit, stream loss, duplicate/out-of-order terminal events, 429/5xx/timeout/malformed response, cancel/completion race, lane crash, Sidecar restart, crash loop, disk write failure, and UI/SSE disconnect.
- Add provider-adapter contract fixtures against the canonical IR/envelope and a bounded cross-provider pair matrix.
- Preserve redacted raw calls, events, store snapshots, process inventories, and validation reports under `PRIVATE/runtime-stability/<run-id>/`.
- Put fast deterministic tests in the normal gate and restart/soak/conformance suites in the release gate.

Acceptance criteria:

- Each critical kill point passes at least twenty consecutive deterministic iterations.
- Recoverable windows recover completely; ambiguous side-effect windows always become reviewable and never blindly replay.
- Duplicate external effects, duplicate handoffs, terminal-state regressions, and cross-lane collateral failures are zero.
- Host loops leave zero owned orphan processes/listeners.
- All reports parse and pass the secret scan; failed evidence is preserved rather than cleaned.

Status: completed

### 18. Introduce The Canonical NodeType Registry And Compiler Interface

Goal: Make node types extensible and shared by compiler and GUI instead of hard-coded role lists.

Main actions:

- Define `NodeTypeSpec` with type/version/category/title, config schema, typed ports, compiler/executor ID, default policy, UI hints, migration, and registry fingerprint.
- Register initial agent/model, MCP tool, MCP resource, transform, router/condition, loop, subgraph, human approval, and artifact source/sink types.
- Represent existing supervisor/planner/worker/coder/reviewer roles as compatible aliases/configurations rather than rewriting v1 graphs.
- Expose a registry API and make compilation resolve executable behavior from the registry.
- Preserve unknown imported nodes as opaque/disabled with diagnostics; never silently delete them.

Acceptance criteria:

- A fixture NodeType added to the backend registry appears in the registry API and compiles without a hard-coded Desktop palette edit.
- Duplicate or conflicting type/version registration fails at startup.
- Old graphs migrate without changing graph/node/edge/artifact identity.
- Unknown nodes round-trip as opaque/disabled with machine-readable diagnostics.
- UI hints do not affect execution hashes; compiler behavior is covered by registry fingerprint tests.

Status: completed

### 19. Make The Graph GUI Registry-Driven And Separate Definition, Plan, And Run

Goal: Provide ComfyUI-style authoring ergonomics on the canonical AstraBridge graph model without coupling UI state to runtime state.

Main actions:

- Generate palette entries, inspectors, forms, typed ports, defaults, and validation from registry/schema data.
- Incrementally extract registry adapter, graph reducer, canvas, inspector, and run overlay from the large workspace component.
- Block invalid saves/runs client-side and revalidate server-side.
- Add reusable templates/subgraphs, canonical import/export/diff, live run overlays, typed artifact previews, and clear diagnostics.
- Keep Compiled Plan read-only and Run Event overlays independent of Definition edits.

Acceptance criteria:

- The hard-coded role palette is no longer a schema source of truth.
- Scalar, enum, list, reference, and structured-JSON fallback forms have component tests.
- Incompatible edges are rejected in the UI and again by the Sidecar.
- Canonical Definition round-trip is semantically equal after excluding documented volatile UI fields.
- A mixed `Agent -> MCP tool/multimodal -> Transform -> Approval -> Agent/Artifact sink` fixture passes dry-run and fixture-live execution.
- Desktop build/tests and wide/narrow visual QA pass without regressing existing graphs.

Status: completed

### 20. Add A Loss-Aware ComfyUI Workflow Adapter

Goal: Import and export a documented ComfyUI Workflow JSON subset without making ComfyUI a core runtime dependency.

Main actions:

- Define an adapter SPI, supported-version manifest, node/port/config mapping, and extension namespace.
- Import supported workflows into canonical Graph Definitions and export the supported subset back to Workflow JSON.
- Preserve unsupported nodes/configuration as opaque extension data when safe, otherwise block with a machine-readable loss report.
- Map media/artifact references through the workspace artifact model rather than trusting external paths.
- Add representative workflows for linear, branched, multimodal, and unsupported-node cases.

Acceptance criteria:

- Supported subset import -> canonical -> export is repeatable and semantically equivalent.
- Unsupported fixtures produce an explicit machine-readable loss report and never silently drop nodes or edges.
- Adapter version changes affect only adapter conformance tests, not native graph execution.
- Imported artifacts remain workspace-scoped and pass URI safety validation.
- The GUI can open, diagnose, edit, and re-export supported imported workflows.

Status: completed

### 21. Add An Optional LangGraph Adapter Without Core Coupling

Goal: Support LangGraph-oriented interoperability and persistence concepts while keeping AstraBridge's kernel and schemas authoritative.

Main actions:

- Implement an optional adapter/plugin that maps supported StateGraph nodes, edges, subgraphs, interrupts, and checkpointer semantics to canonical definitions or generated integration code.
- Publish supported-version and mapping manifests plus explicit loss reports.
- Map LangGraph thread/checkpoint identifiers to AstraBridge context/run lineage without making them the durable source of truth.
- Keep the core fully functional when LangGraph/LangChain packages are absent.
- Document the future external A2A gateway boundary separately from the internal Envelope; do not add a second internal bus.

Acceptance criteria:

- Supported sample graphs round-trip or compile with equivalent routing, interrupts, and subgraph boundaries.
- Unsupported constructs produce explicit diagnostics/loss reports.
- Native AstraBridge graphs and the full core test suite pass with LangGraph dependencies uninstalled.
- External dependency/version changes are isolated to adapter conformance tests.
- The adapter cannot bypass MCP policy, Agent Envelope validation, or the durable scheduler.

Status: completed

### 22. Migrate, Roll Out, Dogfood, And Close The Reliability Gate

Goal: Enable the new reliability spine without losing existing graphs, runs, or evidence and prove rollback before default enablement.

Main actions:

- Introduce feature flags and an explicit compatibility window for client pool, schemas, scheduler, Agent Envelope, and MCP broker migrations.
- Compare old/new projections in shadow mode without executing provider or tool effects twice.
- Migrate fixture workspaces, then a bounded dogfood workspace; classify active legacy runs as terminal, safely recoverable, or `needs_review`.
- Run the complete deterministic gate, restart/soak suite, MCP/provider conformance, process audit, Desktop visual QA, and secret scan.
- Prove rollback can read new evidence and does not delete the durable store/events.
- Publish the migration/rollback/maintenance boundary and close this plan only after all prior gates pass.

Acceptance criteria:

- Repeated migration of the same workspace is idempotent and preserves graph/run/artifact identity.
- Shadow comparison finds no unexplained differences for completed, failed, cancelled, approval, retry, and artifact states.
- No run or side effect is double-executed during rollout.
- Rollback preserves and can inspect new-kernel runs and diagnostics.
- Steps 1-21 are complete, all release gates pass, reports are preserved and redacted, and owned orphan processes/listeners are zero.
- Current Progress is marked complete with no remaining required work and the final log names only optional future product breadth.

Status: completed

## Progress Log

### 2026-07-16 - Step 0

- Completed: Created the durable stability, protocol, and agent-runtime execution plan.
- Evidence inspected: repository execution rules; completed normalization record; architecture and contract ownership docs; provider transport/IR; runtime client lifecycle; graph execution/cancel/recovery paths; Agent orchestration contract/compiler; current MCP servers/configuration; Task Graph internal contract; Desktop graph workspace; Tauri Sidecar launcher; completed and overlapping plans under `PLAN/`.
- Preserved prior work: completed normalization, app hardening, task graph, orchestration productization, provider compatibility, multimodal qualification, live dogfood, fixtures, reports, and raw validation artifacts remain valid inputs and are not restarted.
- Route decision: use this file as the only scheduler for cross-domain stability/protocol work; absorb overlapping unfinished goals from stale Step-0-only plans; begin with one bounded ownership reconciliation, then move directly to runtime client isolation.
- Files changed: `PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md`.
- Validation: required durable-plan sections, one active work unit, 23 numbered steps including Step 0, per-step acceptance criteria, explicit next entry point, and preservation/adjustment rules checked.
- Blockers: None.
- Next step: Step 1, Reconcile Plan And Contract Ownership.

### 2026-07-16 - Step 1

- Completed: Reconciled plan and contract ownership for the stability/protocol scope.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/__init__.py`, `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, `docs/INTERFACE_GOVERNANCE.md`, `PLAN/CAPABILITY_RUNTIME_IMPLEMENTATION_PLAN.md`, `scripts/contract_boundary_audit.py`, and this plan's progress/current-work sections.
- Validation: `python scripts/contract_boundary_audit.py` passed all four checks; focused `test_contract_boundary_audit.py` passed 3 tests; trailing-whitespace and secret-pattern scans were run before staging; existing provider and graph fixture checks remained passing.
- Preserved: completed plans, stale plan histories, fixtures, raw reports, and unrelated working-tree changes were not deleted or staged.
- Blockers: None for Step 1. No pull request was attempted because the user requested commit/push only.
- Next step: Step 2, Isolate Provider Runtime Client Lanes.

### 2026-07-16 - Step 2

- Completed: Isolated provider runtime client lanes with a redacted-signature `RuntimeClientPool`, per-lane leases, lifecycle locks, bounded concurrency/restart behavior, idle reaping, and pool shutdown.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_client_pool.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/secret_service.py`, `apps/astrabridge-sidecar/tests/test_runtime_client_pool.py`, `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, `docs/INTERFACE_GOVERNANCE.md`, `scripts/contract_boundary_audit.py`, and this plan.
- Validation: provider lane tests passed 7/7; `test_sidecar_services.py` passed 382 tests; `test_task_graph_worker_runtime.py` passed 39 tests plus 3 subtests; `python scripts/contract_boundary_audit.py` passed 4/4; relevant Python compilation passed; stale-process audit reported no clearly stale AstraBridge wrappers.
- Security and preservation: lane IDs/snapshots are opaque digests; private provider environments are passed without mutating process-global configuration; no credential-bearing artifacts were staged; unrelated UI, graph, provider, diagnostics, and raw validation changes remain unstaged and preserved.
- Blockers: None for Step 2. GitHub CLI authentication is still invalid (HTTP 401), but the Git remote credential path is available for the requested push; no merge conflict or unmerged path exists.
- Next step: Step 3, Establish Canonical Protocol Schemas And Code Generation.

### 2026-07-16 - Step 3

- Completed: Established the backend-owned JSON Schema 2020-12 source at `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/schema/v1/protocol.json` with stable `$id`, explicit `astrabridge-protocol-v1` version, shared definitions for ArtifactRef/ContentPart/AgentEnvelope/AgentTask/RunEvent/capability input-output/GraphDefinition/CompiledPlan, port and schema-reference constraints, and forbidden security fields.
- Generated projections: `protocol/generated/v1.py` and `apps/astrabridge-desktop/src/astrabridge_protocol/generated/v1.ts` are produced only by `scripts/generate_protocol_types.py`; `--check` is the deterministic freshness gate and the AstraBridge directory is separate from the official app-server `src/protocol/generated` directory.
- Compatibility: `protocol/compatibility.py` and `compatibility_manifest.json` define current-write/legacy-read rules, idempotent graph and compiled-plan migration, artifact URI adaptation, and preservation of graph IDs, topology, artifact lineage, and security policy.
- Fixtures and ownership: shared positive/negative fixtures live at `apps/astrabridge-desktop/src/astrabridge_protocol/fixtures/protocol_v1.json`; Python and Vitest suites exercise the same fixture catalog; ownership docs and `scripts/contract_boundary_audit.py` now require the schema/codegen owner and freshness check.
- Validation: `python -m unittest -v apps.astrabridge-sidecar.tests.test_protocol_schema` passed 8 tests; `cmd /c npm test -- --run src/astrabridge_protocol/generated/v1.test.ts` passed 3 tests; `python scripts/generate_protocol_types.py --check` passed; `python scripts/contract_boundary_audit.py` passed 5/5 checks; JSON Schema 2020-12 meta-schema validation and secret-field rejection passed; Desktop build passed earlier in this round.
- Security and preservation: no provider credentials, raw secrets, cookies, or authorization headers were written to the schema, fixtures, generated outputs, or reports; preserved `.pnpm-store/`, `.tmp/`, and `tmp/` remain untracked and were not staged.
- Blockers: None for Step 3.
- Next step: Step 4, Add The Workspace-Local Durable Run And Event Store.

### 2026-07-16 - Step 4

- Completed: Added `astrabridge_sidecar.durable_run_store.DurableRunEventStore`, a workspace-local versioned SQLite/WAL source of truth under `.astrabridge/durable_runs.sqlite3` for runs, attempts, ordered events, leases, inbox/outbox, and external operations. Transactions use state-version CAS, immutable evidence keys, terminal monotonicity with an explicit dry-run-to-live compatibility promotion, and atomic event/projection updates.
- Migration and projections: Added deterministic empty/existing/repeated legacy migration, redacted secret-safe payload storage, outside-workspace path markers, active-legacy `needs_review` classification, idempotent run/event/artifact merging, and deterministic projection rebuilds. Existing task JSON, manifests, diagnostics, `PRIVATE/**`, and raw evidence remain untouched compatibility exports.
- Integration and ownership: `TaskService` lazily initializes/migrates the durable store and mirrors full/compact graph run writes; ownership docs and `scripts/contract_boundary_audit.py` now name and verify `DurableRunEventStore` as the durable state owner.
- Validation: `test_durable_run_store.py` passed 8 tests (including concurrent CAS, rollback atomicity, idempotency, leases, migration, redaction, and projection determinism); focused task-graph persistence passed 5/5 with `ASTRABRIDGE_RUNTIME_ROOT` redirected to workspace `.tmp`; live graph worker and full `test_task_graph_api.py` passed (12/12); protocol/graph/compiler tests passed 21/21; contract audit passed 6/6; governance passed 0 errors/0 warnings; focused and app-hardening secret scans passed; stale-process helper found no clearly stale owned wrappers.
- Environment note: task-graph tests require the existing writable runtime-root override on this machine because the default `D:\AstraBridgeRuntime` is access-denied; no product files or historical artifacts were cleaned.
- Blockers: None for Step 4.
- Next step: Step 5, Move Live Graph Execution To An Asynchronous Durable Scheduler.

### 2026-07-16 - Step 5

- Completed: Added `DurableGraphScheduler` with bounded daemon workers, redacted job metadata, idempotent submission, wait/status/shutdown controls, and a runtime callback seam. The normal `/api/task-graphs/run` route now admits a durable queued run and returns a receipt; `RuntimeService.execute_task_graph_run` remains an explicit synchronous compatibility adapter and honors scheduler-owned run IDs only.
- Durable projection/API: queued manifests are persisted through `TaskService.record_graph_run`/`DurableRunEventStore` before dispatch; scheduler workers promote the durable projection to `running`; `graph_run_status` returns the durable run plus ordered events and scheduler metadata; Desktop API and App polling read the status projection rather than keeping request-local execution state.
- Dependency/parallel evidence: compiled plans now expose `topology.max_parallelism` derived from independent groups; the existing live path starts all runnable turns in a dependency group before waiting, while scheduler tests prove bounded independent dispatch and the durable receipt boundary.
- Validation: `test_graph_scheduler.py` passed 4/4 (sub-500 ms receipt, caller-disconnect lifetime, two-worker concurrency, failure redaction, runtime queued receipt); `test_task_graph_worker_runtime.py` passed 39/39; `test_task_graph_api.py` passed 12/12; compiler tests passed 7/7; contract audit passed 7/7; Desktop Vitest/build passed (62 files, 451 tests, production build).
- Security and preservation: scheduler job/status payloads never expose callback payloads; callback errors are redacted; no secrets or provider credentials were staged; `.pnpm-store/`, `.tmp/`, and `tmp/` remain untracked and preserved; stale-process helper remained clean.
- Blockers: None for Step 5. Full crash recovery, leases, checkpoints, and effect journaling remain intentionally owned by Step 6.
- Next step: Step 6, Add Leases, Checkpoints, Startup Reconciliation, And Effect Journaling.

### 2026-07-16 - Git connection deferral

- Decision: Per user instruction, stop GitHub CLI login and Git connection troubleshooting until all numbered stability/protocol/Agent Runtime steps are complete.
- Evidence: `gh auth status` remained unauthenticated after the device flow reached GitHub's additional email-verification page; no token, cookie, or authorization header was read or persisted. The waiting `gh` process was terminated after the user abandoned this work.
- Route impact: This is an explicitly deferred external integration, not a blocker for Step 6 or the plan's runtime acceptance criteria. Do not create a retry step or revisit it during intermediate execution rounds.
- Next step: Continue Step 6, Add Leases, Checkpoints, Startup Reconciliation, And Effect Journaling.

### 2026-07-16 - Step 6

- Completed: Extended the durable graph runtime with stable per-node `operation_id` journaling, durable outbox/external-operation records, lease-backed dispatch checkpoints, lease heartbeats/releases, and scheduler startup reconciliation that requeues eligible `queued`/`running` runs from the durable store instead of relying on HTTP lifetime.
- Recovery semantics: duplicate run admission now reuses one deterministic run for the same idempotency key; crash-before-dispatch leaves a durable queued attempt plus pending outbox that safely replays after lease expiry; crash-after-handle persists the accepted remote thread/turn handle and reattaches without starting a second provider turn; ambiguous non-idempotent dispatch errors settle as `needs_review` instead of silently replaying.
- Contract/state updates: added `needs_review` to live run/node statuses and event types; durable store now exposes lease/outbox/external-operation reads and outbox status updates; compact run-ref syncing normalizes `approval_state` back into full-run shape for the durable store; zero-attempt queued nodes no longer create immutable attempt rows prematurely.
- Validation: `python -m unittest -v tests.test_graph_scheduler tests.test_durable_run_store` passed 16/16, covering idempotent admission, crash-before-dispatch replay, reattach via known external handle, ambiguous non-idempotent `needs_review`, scheduler queue timing, failure redaction, durable store CAS/idempotency, leases, inbox/outbox, and migration. Targeted `py_compile` checks over the modified sidecar/runtime/test files passed.
- Process hygiene: end-of-round local process audit found no clearly AstraBridge-owned stale `python`/`node`/`cmd` wrappers remaining after the focused test run.
- Blockers: None for Step 6.
- Next step: Step 7, Implement Production Cancel, Retry, Resume, And Provider Failover Semantics.

### 2026-07-16 - Step 7

- Completed: promoted live task-graph cancellation, retry, recovery, and provider-failover behavior from fixture-only placeholders into the durable runtime. Live cancel/recover HTTP routes now prefer `RuntimeService`; cancelling a running live node sends a real interrupt against the tracked runtime lane/thread/turn and prevents later retry dispatches.
- Runtime/state updates: live execution now carries declared retry policy through the real wait loop, respects zero-delay retry configuration, classifies retryable 429/5xx/transport failures before scheduling a new attempt, records fallback-model lineage per attempt, keeps terminal `cancelled` events explicit, and stops treating live compact run snapshots as immutable attempt inserts in the durable store. `graph_run_status()` overlays the latest live run ref so status, recovery, and cancellation read current node state instead of stale attempt rows.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py apps/astrabridge-sidecar/astrabridge_sidecar/server.py apps/astrabridge-sidecar/tests/test_graph_scheduler.py apps/astrabridge-sidecar/tests/test_task_graph_api.py` passed. `python -m unittest -v apps/astrabridge-sidecar/tests/test_graph_scheduler.py` passed 11/11, covering live cancel interrupts, retryable 429/5xx/transport retries, invalid-output / permission-denied / invalid-request-shape no-retry behavior, crash replay, reattach, and ambiguous dispatch `needs_review`. A targeted live-route HTTP regression run with a temporary runtime root passed 2/2 for `test_http_api_exposes_live_task_graph_run_route` and `test_live_cancel_and_recover_routes_prefer_runtime_handlers`.
- Process hygiene: end-of-round audit found no clearly AstraBridge-owned stale `python`/`node`/`cmd` wrappers attributable to this Step 7 validation round.
- Blockers: None for Step 7.
- Next step: Step 8, Implement The Versioned Agent Envelope And Delivery Ledger.

### 2026-07-16 - Step 8

- Completed: promoted cross-node task-graph handoffs into immutable protocol-validated agent envelopes persisted in the workspace-local durable store instead of leaving structured communication as prompt-only metadata. Source worker output now writes canonical per-edge `AgentEnvelope` artifacts with stable message, envelope, correlation, causation, and delivery idempotency identifiers, plus redacted provider-neutral content parts and artifact lineage.
- Runtime/state updates: live scheduler admission now validates incoming agent envelopes before target provider dispatch, rejects malformed or mismatched envelopes without starting the target provider lane, deduplicates repeated delivery idempotency keys before downstream execution, and records `handoff_created`, `handoff_acknowledged`, `handoff_rejected`, `handoff_retry_scheduled`, and `handoff_delivery_failed` as ordered durable run events. The durable run store now persists immutable `agent_envelopes` and exposes a derived `delivery_ledger` projection through `graph_run_status()` so UI/status views can trace the same redacted message identity end to end.
- Protocol updates: extended `protocol/schema/v1/protocol.json` delivery-ledger event coverage and regenerated the sidecar and desktop protocol projections with `python scripts/generate_protocol_types.py --write` so schema, Python validator, and TypeScript projection remain in sync.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py apps/astrabridge-sidecar/tests/test_graph_scheduler.py apps/astrabridge-sidecar/tests/test_durable_run_store.py apps/astrabridge-sidecar/tests/test_protocol_schema.py` passed. `python -m unittest -v apps/astrabridge-sidecar/tests/test_durable_run_store.py apps/astrabridge-sidecar/tests/test_protocol_schema.py apps/astrabridge-sidecar/tests/test_graph_scheduler.py` passed 31/31, covering immutable envelope persistence, protocol projection freshness, structured-part delivery without a human summary, invalid-envelope pre-dispatch rejection, duplicate delivery idempotency dedupe, and the existing Step 7 live-runtime recovery/retry envelope interactions.
- Process hygiene: end-of-round audit found no clearly AstraBridge-owned stale `python`/`node`/`cmd` wrappers attributable to this Step 8 validation round.
- Blockers: None for Step 8.
- Next step: Step 9, Enforce Typed Port Bindings And Output Schemas In The Live Path.

### 2026-07-16 - Step 9

- Completed: made typed handoff contracts operational in the live path instead of leaving them as prompt-only metadata. Live worker output now projects edge payloads from compiled `port_bindings`, persists validated typed input maps inside the immutable `AgentEnvelope`, and rejects missing/legacy raw-text-only typed projections with an explicit compatibility diagnostic instead of silently degrading.
- Runtime/state updates: the sidecar now validates source output ports, projected payloads, target input ports, and node `machine_result` objects against the declared schemas before downstream provider dispatch or terminal success marking. Legacy task-graph migration now infers deterministic typed input ports per edge when the source graph lacks first-class ports, while preserving imported explicit orchestration bindings. Failed or blocked worker outputs no longer emit downstream handoffs, and compiled fixture runs auto-fill schema-required machine-result fields so fixture coverage stays aligned with the live contract.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py apps/astrabridge-sidecar/tests/test_graph_scheduler.py apps/astrabridge-sidecar/tests/test_task_graph_api.py` passed. `python -m unittest -v apps/astrabridge-sidecar/tests/test_graph_scheduler.py` passed 17/17, adding positive/negative Step 9 fixtures for fan-out/fan-in typed inputs, machine-result schema fail-closed behavior, and explicit typed-handoff compatibility rejection. With `ASTRABRIDGE_RUNTIME_ROOT` redirected to a workspace-local temp root, `python -m unittest -v apps/astrabridge-sidecar/tests/test_task_graph_api.py` passed 13/13. The combined Step 9 regression lane `python -m unittest -v apps/astrabridge-sidecar/tests/test_graph_scheduler.py apps/astrabridge-sidecar/tests/test_task_graph_api.py apps/astrabridge-sidecar/tests/test_durable_run_store.py apps/astrabridge-sidecar/tests/test_protocol_schema.py` passed 47/47.
- Process hygiene: end-of-round read-only listener audit found no clearly AstraBridge-owned stale `python`/`node`/`cmd` wrappers attributable to this Step 9 validation round.
- Blockers: None for Step 9.
- Next step: Step 10, Complete Cross-Provider Context Projection And Handoff Continuity.

### 2026-07-16 - Step 10

- Completed: promoted cross-provider handoff continuity from prompt previews into an explicit neutral context bundle that is attached to downstream live dispatch. Each downstream node now receives a deterministic `neutral-context-attempt-<n>.json` bundle containing validated typed inputs, preserved artifact references, edge/schema provenance, and projected cross-provider history/tool state rather than only summary counts or preview text.
- Runtime/state updates: the live scheduler now builds per-node neutral context bundles from immutable agent envelopes, runs `HistoryProjector` against the source worker thread when visible history exists, strips provider-private reasoning fields, records repaired tool-call/result pairing, and attaches the resulting neutral context plus declared artifact files to downstream provider turns while keeping `context_mode="no_context"` so provider-native transcript state remains isolated. Neutral projection truncation is deterministic and diagnosed through per-handoff limits, warnings, and bundle-level truncation metadata. Local handoff artifacts with workspace-relative paths now project into downstream attachments without requiring a prior protocol ArtifactRef conversion.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py apps/astrabridge-sidecar/tests/test_graph_scheduler.py` passed. `python -m unittest -v apps/astrabridge-sidecar/tests/test_graph_scheduler.py` passed 19/19, adding Step 10 fixtures for A -> B -> C neutral context continuity across `qwen -> kimi -> glm`, provider-private reasoning stripping, repaired tool-call/result projection, artifact carry-through, and deterministic projection truncation. With `ASTRABRIDGE_RUNTIME_ROOT` redirected to a workspace-local temp root, the broader validation lane `python -m unittest -v apps/astrabridge-sidecar/tests/test_graph_scheduler.py apps/astrabridge-sidecar/tests/test_task_graph_api.py apps/astrabridge-sidecar/tests/test_durable_run_store.py apps/astrabridge-sidecar/tests/test_protocol_schema.py` passed 49/49.
- Process hygiene: end-of-round read-only listener audit found no clearly AstraBridge-owned stale `python`/`node`/`cmd` wrappers attributable to this Step 10 validation round.
- Blockers: None for Step 10.
- Next step: Step 11, Replace Duplicated MCP Protocol Code With One Shared Core.

### 2026-07-16 - Step 11

- Completed: replaced the duplicated MCP stdio reader/lifecycle code in the capability, web, Yunwu image, and probe-fixture servers with one shared `astrabridge_sidecar.mcp_server_core` owner. The shared core now owns version negotiation, JSON-RPC request handling, tools/resources listing, raw-stdio compatibility framing, bounded log redaction, timeout handling, cancellation, progress notifications, loopback calls, and Streamable HTTP session adapters.
- Runtime/state updates: production stdio servers now instantiate `McpServerCore` and route their tool catalogs/execution through thin adapters instead of defining private `_read_first_nonempty_byte`, `_read_json_object`, and custom initialize/dispatch loops. The negotiated protocol surface now supports current `2025-11-25` plus legacy `2024-11-05` reads through explicit downgrade rules rather than echoing arbitrary requested versions. `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` and `scripts/contract_boundary_audit.py` now name `mcp_server_core.py` as the canonical MCP lifecycle owner and fail if those production adapters regress into duplicate framing helpers.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/mcp_server_core.py apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_web_mcp_server.py apps/astrabridge-sidecar/astrabridge_sidecar/yunwu_image_mcp_server.py apps/astrabridge-sidecar/astrabridge_sidecar/codex_mcp_probe_fixture_server.py` passed. `python -m unittest -v apps/astrabridge-sidecar/tests/test_mcp_server_core.py apps/astrabridge-sidecar/tests/test_capability_mcp_server.py apps/astrabridge-sidecar/tests/test_mcp_stdio_servers.py` passed 14/14, covering stdio raw/header framing, invalid JSON parse error, current/legacy/unsupported version negotiation, cancellation, timeout, progress, loopback parity, and Streamable HTTP session behavior. The broader MCP regression lane `python -m unittest -v apps/astrabridge-sidecar/tests/test_codex_app_server_probe.py apps/astrabridge-sidecar/tests/test_capability_mcp_server.py apps/astrabridge-sidecar/tests/test_mcp_server_core.py apps/astrabridge-sidecar/tests/test_mcp_stdio_servers.py` passed 18/18. `python scripts/contract_boundary_audit.py` passed 8/8 checks, including the new shared-core ownership audit.
- Process hygiene: pre/post round read-only listener audits found no clearly AstraBridge-owned stale `python`/`node`/`cmd` wrappers attributable to this Step 11 implementation and validation round.
- Blockers: None for Step 11. Git/GitHub CLI connection remains explicitly deferred by user and is not part of this step's acceptance path.
- Next step: Step 12, Route Every Normal Capability Invocation Through The MCP Broker.

### 2026-07-17 - Step 12

- Completed: added `astrabridge_sidecar.mcp_broker_service.McpBrokerService` as the canonical internal broker seam for normal capability invocation and routed the live HTTP/runtime capability surfaces through it instead of calling capability/web/Yunwu implementations directly. `runtime_service.py` dynamic capability/web/Yunwu tools, `web_tool_service.py`, `server.py` normal Yunwu routes, and `/api/runtime/capability-invoke` now carry MCP request/operation/policy/audit metadata on the normal path.
- Result-shape and compatibility updates: `mcp_server_core.py` now preserves tool-call `_meta` on `McpToolCallContext`; `yunwu_image_mcp_server.py` now keeps compatibility text summaries while returning raw structured results, honors broker-injected workspace roots/timeouts, and accepts loopback-only internal API-key metadata without exposing it as tool arguments or durable output. The Yunwu summary path now preserves `b64_json_present` markers instead of dropping them during dynamic-tool summarization.
- Ownership and guardrails: `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names `mcp_broker_service.McpBrokerService` as part of the canonical MCP boundary. `scripts/contract_boundary_audit.py` now requires the broker owner, verifies runtime/server/web broker usage, and raises the ownership audit to 9 checks. New `test_mcp_broker_service.py` adds broker metadata, HTTP route, web-lane persistence, and direct-bypass source guards so normal `RuntimeService`/`server.py` regressions fail deterministically.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/mcp_server_core.py apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py apps/astrabridge-sidecar/astrabridge_sidecar/yunwu_image_mcp_server.py apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py apps/astrabridge-sidecar/astrabridge_sidecar/server.py apps/astrabridge-sidecar/tests/test_mcp_broker_service.py` passed. `python -m unittest -v apps.astrabridge-sidecar.tests.test_mcp_broker_service` passed 6/6. `python -m unittest -v apps.astrabridge-sidecar.tests.test_contract_boundary_audit` passed 3/3. `python -m unittest -v apps.astrabridge-sidecar.tests.test_mcp_server_core apps.astrabridge-sidecar.tests.test_capability_mcp_server apps.astrabridge-sidecar.tests.test_mcp_stdio_servers` passed 14/14. Targeted runtime regressions `test_runtime_dynamic_yunwu_tool_call_returns_app_server_content_items`, `test_runtime_dynamic_astrabridge_web_tool_call_returns_research_brief_content_primary`, `test_runtime_dynamic_astrabridge_web_search_alias_preserves_default_tool_context`, and `test_runtime_dynamic_astrabridge_web_tool_call_returns_research_brief_content` passed 4/4. `test_yunwu_image_generation_payload_and_smoke_request` passed 1/1. `python scripts/contract_boundary_audit.py` passed 9/9 checks.
- Process hygiene: pre/post round read-only listener audits found no clearly AstraBridge-owned stale listener or launcher that needed reaping during this Step 12 implementation/validation round.
- Blockers: None for Step 12. Git/GitHub CLI connection remains explicitly deferred by user and is not part of this step's acceptance path.
- Next step: Step 13, Add Structured Multimodal MCP Results And Safe Artifact References.

### 2026-07-17 - Step 13

- Completed: introduced `astrabridge_sidecar.multimodal_result_envelope` as the shared typed multimodal MCP-result bridge for capability, Yunwu image, and standalone web-lane results. Normal multimodal result paths now project protocol-safe artifact refs, diagnostic refs, content parts, inline-externalization policy, and typed summary envelopes instead of relying only on raw text/path payloads.
- Runtime/result updates: `YunwuImageGenerateAdapter`, `DashScopeImageGenerateAdapter`, `vision_analyze_adapter.py`, `speech_transcribe_adapter.py`, `speech_synthesize_adapter.py`, `astrabridge_web_mcp_server.py`, `web_tool_service.py`, and `yunwu_image_mcp_server.py` now enrich normal results with workspace-safe `workspace://` artifact URIs, media type, digest, size, lineage, typed content parts, and MCP text summaries that avoid dumping large inline payloads or absolute artifact paths. Speech synthesis now externalizes `audio_bytes_base64` once durable audio artifacts exist and records an inline-policy marker instead of returning large inline audio blobs. Provider-path escape outside the workspace allowlist now fails closed for protocol artifact projection.
- Desktop/result consumption: `capabilities/artifacts.py` now projects protocol-safe artifact metadata into capability artifact snapshots, and the Desktop `CapabilityRoutesPanel` now renders visible typed artifact metadata (`artifact_uri`, `mime_type`, `size`, `sha256`) while keeping media preview loading internal and avoiding visible absolute-path spill. The visual QA harness and preserved screenshot live under `apps/astrabridge-desktop/output/playwright/capability-panel-harness/`, with the verified screenshot at `capability-panel-qa-http-2026-07-17.png`.
- Ownership and guardrails: `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names `multimodal_result_envelope.py` as the canonical typed multimodal MCP-result and safe-artifact projection owner. `scripts/contract_boundary_audit.py` now requires that owner and verifies the capability/web/Yunwu adapters plus capability artifact snapshots remain wired to the shared typed-result bridge, raising the audit to 10 checks.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/multimodal_result_envelope.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/image_generate_adapter.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/dashscope_image_generate_adapter.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/vision_analyze_adapter.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_transcribe_adapter.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/artifacts.py apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_web_mcp_server.py apps/astrabridge-sidecar/astrabridge_sidecar/web_tool_service.py apps/astrabridge-sidecar/astrabridge_sidecar/yunwu_image_mcp_server.py` passed. `python -m unittest -v apps.astrabridge-sidecar.tests.test_image_generate_adapter apps.astrabridge-sidecar.tests.test_vision_analyze_adapter apps.astrabridge-sidecar.tests.test_speech_transcribe_adapter apps.astrabridge-sidecar.tests.test_speech_synthesize_adapter apps.astrabridge-sidecar.tests.test_capability_artifacts apps.astrabridge-sidecar.tests.test_web_lane apps.astrabridge-sidecar.tests.test_capability_smoke apps.astrabridge-sidecar.tests.test_capability_mcp_server` passed 54/54. `python -m unittest -v apps.astrabridge-sidecar.tests.test_mcp_broker_service apps.astrabridge-sidecar.tests.test_contract_boundary_audit apps.astrabridge-sidecar.tests.test_mcp_server_core apps.astrabridge-sidecar.tests.test_mcp_stdio_servers` passed 18/18. Targeted runtime regressions in `test_sidecar_services.py` for Yunwu/web dynamic tool calls passed 4/4. Desktop `cmd /c npm test -- --run src/features/capabilities/CapabilityRoutesPanel.test.tsx` passed 13/13 and `cmd /c npm run build` passed. Visual QA harness build passed, and the preserved screenshot confirms visible typed artifact metadata without absolute-path text exposure. `python scripts/contract_boundary_audit.py` passed 10/10 checks.
- Process hygiene: pre/post round read-only listener audits were run; the temporary local HTTP server used for visual QA was explicitly terminated via `taskkill /PID 13708 /T /F`, and the final listener audit showed no remaining Step 13 QA listener on port 43123.
- Blockers: None for Step 13. Git/GitHub CLI connection remains explicitly deferred by user and is not part of this step's acceptance path.
- Next step: Step 14, Enforce Per-Node MCP Tool And Resource Policy.

### 2026-07-17 - Plan Note: Git/GitHub CLI Connection Deferred

- Decision: the user explicitly directed the plan to stop all GitHub CLI / `gh` authentication and connection troubleshooting until every numbered step in this execution plan is complete.
- Execution effect: do not spend Step 14+ rounds on `gh auth`, device login, token repair, or related GitHub CLI setup; do not treat GitHub CLI connection state as a blocker for any numbered step in this plan unless the user explicitly reopens that topic after plan completion.
- Scope note: existing Git remote credential behavior remains an independent path and does not change the defer/abandon decision for GitHub CLI work.

### 2026-07-17 - Step 14

- Completed: introduced `astrabridge_sidecar.mcp_node_policy` as the canonical owner for per-node MCP least-privilege policy, including exact server/tool selectors, resource URI allowlists, approval mode, effect class, call budget, policy fingerprinting, and deny-before-side-effect authorization. Graph/node authoring, compiled-plan snapshots, live run manifests, worker runtime contracts, exposed dynamic-tool filtering, and broker dispatch now consume the same normalized policy owner instead of re-encoding coarse `supports_mcp` behavior ad hoc.
- Runtime/policy updates: `agent_orchestration_contract.py` now validates graph/node MCP policy fields and preserves them across lift/lower bridges; `agent_orchestration_compiler.py` snapshots planned node `mcp_tool_policy` into compiled nodes; `task_service.py` persists node MCP policy snapshots into `run_policy_snapshot.node_mcp_tool_policies` and worker `runtime_contract.tool_policy.mcp_tool_policy`; `runtime_service.py` now filters `dynamicTools` at thread exposure time, carries snapshotted MCP policy plus run/node/attempt context through `start_turn`, records per-turn policy lineage, reuses approval/bootstrap state within the active turn, and uses snapshotted node MCP policy during replay/retry rather than silently widening to later enabled-server drift. `mcp_broker_service.py` now re-authorizes loopback dispatch against the node snapshot when graph-worker policy metadata is present and fails closed before tool execution on undeclared, denied, exhausted, or resource-escape calls.
- Ownership and guardrails: `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names `astrabridge_sidecar.mcp_node_policy` as the canonical owner for per-node MCP tool/resource policy. `scripts/contract_boundary_audit.py` now requires that owner and verifies contract/compiler/runtime/task/broker bridges remain wired to the shared policy owner, raising the ownership audit to 11 checks.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/mcp_node_policy.py apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_compiler.py apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` passed. `python -m unittest -v apps.astrabridge-sidecar.tests.test_mcp_node_policy apps.astrabridge-sidecar.tests.test_mcp_broker_service apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime` passed 52/52, covering allow/deny/ask, approval reuse, budget exhaustion, resource URI escape, broker pre-dispatch denial, graph-worker snapshot drift, and live graph runtime regressions. `python -m unittest -v apps.astrabridge-sidecar.tests.test_contract_boundary_audit apps.astrabridge-sidecar.tests.test_task_graph_api apps.astrabridge-sidecar.tests.test_graph_scheduler` passed 35/35. `python scripts/contract_boundary_audit.py` passed 11/11 checks, including the new `node_scoped_mcp_tool_and_resource_policy` audit.
- Process hygiene: pre/post round read-only listener and process audits were run. No clearly AstraBridge-owned stale listener or launcher required reaping during Step 14 implementation and validation.
- Blockers: None for Step 14. Git/GitHub CLI connection remains explicitly deferred by user and is not part of this step's acceptance path.
- Next step: Step 15, Add Desktop-Sidecar Host Supervision And Run Reattachment.

### 2026-07-17 - Plan Note: Git/GitHub CLI Connection Explicitly Abandoned Until Plan Completion

- Decision: the user reaffirmed that all GitHub CLI / `gh` authentication, token, and connection work is abandoned for the duration of this execution plan and may be revisited only after every numbered step is complete.
- Execution effect: do not retry `gh auth`, device login, token repair, token inspection, or related GitHub CLI diagnostics during Step 15+ rounds; do not spend execution time on GitHub CLI unless the user explicitly reopens it after plan completion.
- Scope note: Git remote push credentials remain a separate path, but they do not authorize or require GitHub CLI work while this plan is still active.

### 2026-07-17 - Step 15

- Completed: replaced the fixed-port Desktop-sidecar launcher with `apps/astrabridge-desktop/src-tauri/src/sidecar_supervision.rs`, which now owns collision-safe launch/reattach, workspace-scoped launch records and lease files, `/readyz` boot/build/store validation, bounded restart/backoff/circuit-breaking, redacted stdout/stderr capture, host lineage logs, and ownership-verified graceful shutdown before any hard kill. `main.rs` now wires that owner into Tauri state, and Desktop `src/api.ts` now resolves the bound sidecar URL through the supervisor on each Tauri request so post-restart port rebinding does not strand the UI on a stale cached port.
- Sidecar contract updates: `apps/astrabridge-sidecar/astrabridge_sidecar/server.py` now owns `/readyz` plus `/host/shutdown`, writes ready/stopped launch-record updates, reports boot/build/runtime/store schema metadata, preserves startup runtime restore results for reattachment diagnostics, and allows dynamic port `0` binding through a reusable-address HTTP server. This keeps Desktop supervision and Sidecar readiness/shutdown on one explicit contract instead of fixed-port guessing or kill-by-port behavior.
- Ownership and guardrails: `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names Desktop-sidecar host supervision plus Sidecar `/readyz`/shutdown as a canonical boundary. `scripts/contract_boundary_audit.py` now verifies that `sidecar_supervision.rs`, `main.rs`, `src/api.ts`, and `server.py` remain wired to that owner and raises the audit to 12 checks.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/server.py` passed. `cmd /c npm test -- --run src/api.test.ts` passed 11/11. `cmd /c npm run build` passed. `python -m unittest -v apps/astrabridge-sidecar/tests/test_sidecar_services.py` passed 384/384, including the new `/readyz` and `/host/shutdown` route tests. `cargo test -- --test-threads=1` in `apps/astrabridge-desktop/src-tauri` passed 7/7, covering restart-after-forced-exit, circuit breaker on repeated launch failure, unrelated candidate-port listener preservation, two-supervisor shared-sidecar coexistence, and 20 start/exit churn cycles without orphan sidecar processes. `python -m unittest -v apps.astrabridge-sidecar.tests.test_graph_scheduler.DurableGraphSchedulerTests.test_crash_before_provider_dispatch_replays_after_recovery apps.astrabridge-sidecar.tests.test_graph_scheduler.DurableGraphSchedulerTests.test_known_external_handle_reattaches_without_restarting_turn apps.astrabridge-sidecar.tests.test_graph_scheduler.DurableGraphSchedulerTests.test_ambiguous_non_idempotent_dispatch_becomes_needs_review` passed 3/3, and `python -m unittest -v apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_live_cancel_and_recover_routes_prefer_runtime_handlers` passed 1/1. Together these runtime recovery tests plus the new host restart tests satisfy the Step 15 acceptance path for recovery/reattach or explicit `needs_review` after forced Sidecar death.
- Process hygiene: pre/post round read-only listener audits were run. During Rust supervision test iteration, clearly stale AstraBridge-owned test sidecar roots were manually reaped with `taskkill /PID <root> /T /F` for the stale parent PIDs `14224, 27068, 14504, 7264, 26728, 33736, 22712, 6976, 30068, 9816`; the final listener and process audits showed no remaining AstraBridge-owned stale sidecar listener or launcher.
- Blockers: None for Step 15. Git/GitHub CLI connection remains explicitly abandoned by user and is not part of this step's acceptance path.
- Next step: Step 16, Add Cross-Layer Tracing, Reliability SLOs, And Redacted Diagnostics.

### 2026-07-17 - Step 16

- Completed: added `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py` as the canonical owner for cross-layer trace lineage, reliability metrics/SLOs, host-lineage ingestion, OpenTelemetry mapping metadata, and redacted diagnostic summaries. The runtime now enriches persisted/live events through that owner, hydrates Desktop-sidecar host lineage logs into the same runtime event stream, and projects one stable `observability` payload through `RuntimeSupervisorService.status()` instead of inventing a separate UI state source.
- Runtime/bridge updates: `runtime_service.py` now records explicit `astrabridge_trace` context across graph/MCP execution, emits `duplicate_effect_suppressed` plus `terminal_projection_lag_ms` runtime events, and enriches all recorded/hydrated events through the observability owner. `mcp_broker_service.py` now preserves trace context on broker audit events. Desktop `src/types.ts` and `src/App.tsx` now consume the supervisor `observability` projection to show latest trace lineage, recent diagnostics, and reliability summaries from the same underlying event source.
- Ownership and guardrails: `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names cross-layer trace lineage, reliability metrics/SLOs, and redacted diagnostics as a canonical boundary owned by `astrabridge_sidecar.runtime_observability`. `scripts/contract_boundary_audit.py` now enforces that `runtime_observability.py` remains the only owner while `runtime_service.py`, `runtime_supervisor_service.py`, and Desktop stay bridge/projection layers.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py` passed. With `PYTHONPATH=D:\\AstraBridge\\apps\\astrabridge-sidecar`, `python -m unittest -v apps.astrabridge-sidecar.tests.test_runtime_observability apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_supervisor_status_includes_observability_summary_from_runtime_events` passed 3/3. With the same `PYTHONPATH`, `python scripts/contract_boundary_audit.py` passed all 13/13 checks. `cmd /c npm run build` passed in `apps/astrabridge-desktop`. Earlier in the same execution round, `cmd /c npm test -- --run src/api.test.ts` passed 11/11 and `cargo test --no-run` passed in `apps/astrabridge-desktop/src-tauri`.
- Process hygiene: start/end listener audits found no AstraBridge-owned listeners on the standard local development ports and no clearly stale AstraBridge-owned `python`/`node`/`cmd` launchers requiring termination during this step.
- Blockers: None for Step 16. Git/GitHub CLI connection remains explicitly abandoned by user and is not part of this step's acceptance path.
- Next step: Step 17, Build Deterministic Fault Injection And Conformance Release Gates.

### 2026-07-17 - Step 17

- Completed: added `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py` as the canonical owner for deterministic runtime fault-injection suite definitions, `PRIVATE/runtime-stability/<run-id>/` artifact layout, preserved fixture evidence capture, secret-scan policy, and fast-vs-release gate mode semantics. Added the CLI wrapper `scripts/run_runtime_stability_gate.py` and wired `scripts/run_local_gate.py --full` to call the shared fast mode instead of defining a second suite list.
- Ownership and guardrails: `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names deterministic fault injection and the runtime stability release gate as a canonical boundary owned by `astrabridge_sidecar.runtime_stability_gate`. `scripts/contract_boundary_audit.py` now enforces that the shared gate owner, wrapper script, and local fast-gate projection stay aligned and raises the audit to 14 checks.
- Runtime-stability gate implementation: the shared gate now groups canonical Python and Rust suites for scheduler recovery/idempotency, terminal projection reconciliation, MCP timeout/cancel/policy fail-close behavior, disk-write and client-disconnect recovery, bounded provider redaction/contract coverage, forced-exit restart, crash-loop circuit breaker behavior, unrelated-listener preservation, shared-sidecar coexistence, and 20-cycle orphan-free host restart churn. The gate preserves raw command logs, before/after process inventories, fixture store/timeline artifacts, and validation reports under `PRIVATE/runtime-stability/<run-id>/`, then applies a focused artifact secret scan without deleting failed evidence.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py scripts/run_runtime_stability_gate.py scripts/run_local_gate.py scripts/contract_boundary_audit.py` passed. With `PYTHONPATH=D:\\AstraBridge\\apps\\astrabridge-sidecar`, `python -m unittest -v apps.astrabridge-sidecar.tests.test_runtime_stability_gate` passed 4/4. With the same `PYTHONPATH`, `python scripts/contract_boundary_audit.py` passed all 14/14 checks. `python scripts/run_runtime_stability_gate.py --mode fast --run-id step17-fast-validation` passed and preserved fast-mode evidence under `PRIVATE/runtime-stability/step17-fast-validation/`. `python scripts/run_runtime_stability_gate.py --mode release --run-id step17-release-validation` passed and preserved release evidence under `PRIVATE/runtime-stability/step17-release-validation/`, including: `scheduler_recovery_and_idempotency` 20/20 consecutive passes; `terminal_projection_and_stream_recovery` 20/20; `mcp_timeout_cancel_and_policy_fail_closed` 20/20; `client_disconnect_and_disk_write_recovery` 20/20; `desktop_forced_exit_restart` 20/20; `desktop_circuit_breaker_recovery` 20/20; `desktop_twenty_restart_cycles_no_orphans` one run with `internal_passes_per_run=20` and `max_consecutive_passes=20`; provider/redaction matrix pass; fixture evidence pass; and runtime-stability secret scan pass with 0 findings over 330 scanned text artifacts.
- Process hygiene: the gate captured before/after process inventories in its preserved artifacts, and the round-closing read-only listener audit again found no AstraBridge-owned listeners on the standard local development ports and no clearly stale AstraBridge-owned `python`/`node`/`cmd` launchers requiring termination.
- Blockers: None for Step 17. Git/GitHub CLI connection remains explicitly abandoned by user and is not part of this step's acceptance path.
- Next step: Step 18, Introduce The Canonical NodeType Registry And Compiler Interface.

### 2026-07-17 - Step 18

- Completed: added `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py` as the canonical owner for `NodeTypeSpec`, legacy kind alias resolution, registry fingerprints, task-graph/orchestration projection defaults, and the backend node-type registry snapshot. The registry now publishes initial `agent_model`, `mcp_tool`, `mcp_resource`, `transform`, `router_condition`, `loop`, `subgraph`, `human_approval`, `artifact_source`, and `artifact_sink` types, while preserving an internal `opaque_disabled` placeholder for unknown imported node types.
- Contract/compiler updates: `task_graph_contract.py` now derives allowed node kinds from the shared registry instead of a private tuple. `agent_orchestration_contract.py` now resolves node kinds through the registry, treats existing supervisor/planner/worker/coder/reviewer/researcher/custom/gate kinds as compatible aliases/configurations instead of a second hard-coded contract, projects registry metadata onto validated canonical nodes, and lowers unknown imported node types into disabled compatibility placeholders with machine-readable diagnostics rather than silently dropping them. `agent_orchestration_compiler.py` now emits resolved node type ids, compiler executor ids, and a registry fingerprint into compiled plans instead of inferring execution metadata from local role tables alone.
- Bridge/API updates: `task_service.py` now exposes `node_type_registry_snapshot()` and preserves unknown imported node kinds/diagnostics across orchestration import and task-graph synchronization. `server.py` now serves `/api/task-graphs/node-types`, and Desktop `src/types.ts` plus `src/api.ts` now expose typed registry snapshot payloads for Step 19 consumers without yet making the GUI palette registry-driven.
- Ownership and guardrails: `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names `astrabridge_sidecar.node_type_registry` plus compiler projection as the canonical NodeType boundary. `scripts/contract_boundary_audit.py` now verifies the shared registry owner, contract/compiler consumers, task-graph allowlist derivation, task-service snapshot, server registry route, and Desktop API projection, raising the audit to 15 checks.
- Validation: with `PYTHONPYCACHEPREFIX=D:\\AstraBridge\\PRIVATE\\tmp\\pycache-step18`, `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_compiler.py apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py apps/astrabridge-sidecar/astrabridge_sidecar/server.py scripts/contract_boundary_audit.py scripts/run_local_gate.py scripts/run_runtime_stability_gate.py` passed. With `PYTHONPATH=D:\\AstraBridge\\apps\\astrabridge-sidecar`, `python -m unittest -v apps.astrabridge-sidecar.tests.test_node_type_registry apps.astrabridge-sidecar.tests.test_agent_orchestration_contract apps.astrabridge-sidecar.tests.test_agent_orchestration_compiler` passed 20/20, covering registry snapshot content, duplicate-registration failure, UI-hint-insensitive registry fingerprints, fixture node-type registration + compiler resolution, imported unknown node preservation/disable diagnostics, HTTP registry route, legacy lift/lower identity preservation, and compiler fingerprint/executor projection. With the same `PYTHONPATH`, `python scripts/contract_boundary_audit.py` passed all 15/15 checks. Desktop `cmd /c npm run build` passed, and `cmd /c npm test -- --run src/api.test.ts` passed 11/11.
- Process hygiene: start/end read-only listener audits found no AstraBridge-owned listeners on the standard local development ports and no clearly stale AstraBridge-owned `python`/`node`/`cmd` launchers requiring termination during this step.
- Blockers: None for Step 18. Git/GitHub CLI connection remains explicitly abandoned by user and is not part of this step's acceptance path.
- Next step: Step 19, Make The Graph GUI Registry-Driven And Separate Definition, Plan, And Run.

### 2026-07-17 - Step 19

- Completed: the Desktop graph editor now consumes the Step 18 node-type registry instead of hard-coded palette metadata as its primary node-authoring source. `apps/astrabridge-desktop/src/features/runtime/taskGraphNodeRegistryUi.ts` projects registry snapshot data into palette sections, human-readable labels, tones, and icon ids; `App.tsx` now queries `/api/task-graphs/node-types` and passes the snapshot into `TaskGraphWorkspace`; and `TaskGraphWorkspace.tsx` now renders registry-driven palette entries, registry-aware node badges, and a schema-backed node-type config section while preserving Definition edits separately from run overlays.
- Schema/form updates: added `TaskGraphSchemaForm.tsx` plus focused component coverage for scalar, enum, list, reference, and structured-JSON fallback controls. Node saves now preserve merged `ui_hints`, `node_type_config`, `node_type_id`, and registry fingerprints rather than collapsing back to the old palette-only contract. `node_type_registry.py` now exposes explicit agent palette variants so legacy agent roles remain human-readable aliases on top of the canonical `agent_model` node type.
- Runtime/contract updates: `agent_orchestration_contract.py` now preserves legacy task-graph `graph_policy.max_depth` when lifting back into canonical orchestration graphs instead of hard-defaulting to depth 2. `task_service.py` now persists approval-resolution state back into the full fixture run manifest, so post-approval recovery uses the same canonical node/run truth as compact run refs. This was required to validate a mixed registry graph that includes a downstream sink after an approval gate.
- Validation: Desktop `cmd /c npm run build` passed. Frontend targeted tests passed with `node .\\node_modules\\vitest\\vitest.mjs run src/features/runtime/TaskGraphSchemaForm.test.tsx --reporter=verbose` (2/2) and `node .\\node_modules\\vitest\\vitest.mjs run src/features/runtime/TaskGraphWorkspace.test.tsx --reporter=verbose` (84/84). Backend targeted validation passed with `python -m unittest -v apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_provider_gate_fixture_requires_approval_and_persists_resolution apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_mixed_registry_graph_passes_dry_run_and_fixture_execution_after_approval apps.astrabridge-sidecar.tests.test_node_type_registry` (9/9), `python -m unittest -v apps.astrabridge-sidecar.tests.test_agent_orchestration_contract` (5/5), `python scripts/contract_boundary_audit.py` (15/15 pass), and focused `py_compile` checks for the touched sidecar contract/task-service files.
- Mixed-fixture evidence: the new `test_mixed_registry_graph_passes_dry_run_and_fixture_execution_after_approval` proves a registry-native `agent_model -> mcp_tool -> transform -> human_approval -> artifact_sink` path can dry-run cleanly, pause for approval at the gate, and then finish the sink through the existing fixture recovery/resume semantics after the approval manifest is updated. This closes the Step 19 requirement that registry-era mixed graphs remain executable rather than UI-only.
- UI QA note: this round preserved narrow UI QA through the targeted workspace/component Vitest render coverage that exercises palette, inspector, node badges, typed ports, run docks, and registry-backed node-type config surfaces under both empty and populated graph states. No additional local browser-only screenshot sweep was needed to clear the changed surfaces in this step.
- Process hygiene: end-of-round listener/process audits found no AstraBridge-owned local listeners on the standard development ports and no clearly stale AstraBridge-owned `python`/`node`/`cmd` launchers attributable to this step.
- Blockers: None for Step 19. Git/GitHub CLI connection remains explicitly abandoned by user and is not part of this step's acceptance path.
- Next step: Step 20, Add A Loss-Aware ComfyUI Workflow Adapter.

### 2026-07-17 - Step 20

- Completed: added `apps/astrabridge-sidecar/astrabridge_sidecar/comfyui_workflow_adapter.py` as the canonical loss-aware ComfyUI workflow bridge for the supported save-workflow subset. The adapter now declares its own manifest/version surface, detects ComfyUI workflow JSON by content, maps supported AstraBridge node types/typed ports/config into canonical orchestration graphs, exports the supported subset back to ComfyUI JSON, preserves disconnected unsupported nodes as opaque extension data when safe, and blocks unsafe or connected unsupported constructs with machine-readable loss reports.
- Import/export bridge updates: `task_service.py` now auto-detects ComfyUI workflow JSON during graph import, applies adapter-provided `task_graph_overlays` into `ui_hints.node_type_config`, infers `comfyui_workflow` as the default export format for imported graphs, preserves GUI edits back into ComfyUI node metadata/widgets on re-export, and uses a ComfyUI-specific synchronization fallback when the persisted task-graph projection cannot fully reconstruct typed edge/schema metadata on its own. Desktop `src/types.ts`, `src/api.ts`, and `src/App.tsx` now expose/source the adapter metadata (`source_format`, `export_format`, `loss_report`, `adapter_manifest`), default import/export prompts to task graph/workflow wording, default ComfyUI-origin graphs back to ComfyUI export paths, and surface machine-readable loss diagnostics through the existing import/export error lane.
- Fixture and ownership updates: added representative workflow fixtures under `examples/comfyui-workflow/` for supported linear, supported branched multimodal, unsupported connected, and unsupported disconnected-preserved cases. `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names `astrabridge_sidecar.comfyui_workflow_adapter` as the canonical owner for the ComfyUI subset map, extension namespace, loss reports, and workspace-safe artifact URI validation. `scripts/contract_boundary_audit.py` now audits that owner plus the `task_service.py`/Desktop bridges, raising the governance suite to 16 checks.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/comfyui_workflow_adapter.py apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py apps/astrabridge-sidecar/tests/test_comfyui_workflow_adapter.py apps/astrabridge-sidecar/tests/test_task_graph_api.py` passed. With `PYTHONPATH=D:\\AstraBridge\\apps\\astrabridge-sidecar`, `python -m unittest -v apps.astrabridge-sidecar.tests.test_comfyui_workflow_adapter apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_comfyui_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_comfyui_format apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_comfyui_import_reexports_updated_node_type_config_from_task_graph_ui_hints apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_http_task_graph_import_export_supports_comfyui_workflow_json` passed 7/7, covering supported linear/branched round-trip semantics, disconnected opaque preservation warnings, connected unsupported-node blocking, unsafe artifact URI rejection, UI edit re-export fidelity, and HTTP import/export default-format inference. `python scripts/contract_boundary_audit.py` passed all 16/16 checks. Desktop `cmd /c npm run build` passed after the App/API/type changes.
- Process hygiene: start/end read-only listener/process audits found no AstraBridge-owned local listeners on the standard development ports and no clearly stale AstraBridge-owned `python`/`node`/`cmd` launchers attributable to this step.
- Blockers: None for Step 20. Git/GitHub CLI connection remains explicitly abandoned by user and is not part of this step's acceptance path.
- Next step: Step 21, Add An Optional LangGraph Adapter Without Core Coupling.

### 2026-07-17 - Step 21

- Completed: added `apps/astrabridge-sidecar/astrabridge_sidecar/langgraph_stategraph_adapter.py` as the canonical optional LangGraph StateGraph interop owner. The adapter now defines a supported `langgraph_stategraph_manifest` subset with versioned adapter/format manifests, supported node/edge/checkpointer rules, optional dependency detection, machine-readable loss reports, and generated Python integration code that targets `StateGraph`, static `interrupt_before`/`interrupt_after`, conditional edges, `START`/`END`, and memory/inherited checkpointer seams without pulling LangGraph or LangChain into the core runtime.
- Import/export bridge updates: `task_service.py` now auto-detects LangGraph StateGraph manifests during graph import, applies adapter-provided `task_graph_overlays` into `ui_hints.node_type_config`, defaults LangGraph-origin graphs back to `langgraph_stategraph_manifest` on export, returns generated LangGraph Python integration code in export responses, and extends the interop synchronization fallback so imported LangGraph graphs preserve their typed ports/conditional-edge metadata instead of being degraded by the lossy task-graph lift/lower bridge. Desktop `src/App.tsx` now recognizes LangGraph-origin graphs for default export-path selection and user-facing import/export diagnostics.
- Fixture and ownership updates: added representative LangGraph fixtures under `examples/langgraph-stategraph/`, including `conditional_subgraph_interrupt_supported.json` for supported conditional routing + subgraph + static interrupt + checkpointer coverage and `unsupported_dynamic_interrupt.json` for explicit dynamic-interrupt blocking. `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names `astrabridge_sidecar.langgraph_stategraph_adapter` as the canonical owner for the supported manifest subset, compile-config mapping, thread/checkpoint lineage projection, and generated-code contract. `scripts/contract_boundary_audit.py` now audits that owner plus the `task_service.py`/Desktop bridges, raising the governance suite to 17 checks.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/langgraph_stategraph_adapter.py apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py apps/astrabridge-sidecar/tests/test_langgraph_stategraph_adapter.py apps/astrabridge-sidecar/tests/test_task_graph_api.py` passed. With `PYTHONPATH=D:\\AstraBridge\\apps\\astrabridge-sidecar`, `python -m unittest -v apps.astrabridge-sidecar.tests.test_langgraph_stategraph_adapter apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_langgraph_format apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_reexports_updated_node_type_config_from_task_graph_ui_hints apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_http_task_graph_import_export_supports_langgraph_manifest_json` passed 6/6. The broader native graph/core suite `python -m unittest -v apps.astrabridge-sidecar.tests.test_agent_orchestration_contract apps.astrabridge-sidecar.tests.test_agent_orchestration_compiler apps.astrabridge-sidecar.tests.test_node_type_registry apps.astrabridge-sidecar.tests.test_task_graph_api` passed 39/39 while the current environment confirmed `langgraph` and `langchain` are both absent. `python -m unittest -v apps.astrabridge-sidecar.tests.test_langgraph_stategraph_adapter apps.astrabridge-sidecar.tests.test_comfyui_workflow_adapter apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_langgraph_format apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_reexports_updated_node_type_config_from_task_graph_ui_hints apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_http_task_graph_import_export_supports_langgraph_manifest_json apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_comfyui_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_comfyui_format apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_comfyui_import_reexports_updated_node_type_config_from_task_graph_ui_hints apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_http_task_graph_import_export_supports_comfyui_workflow_json` passed 13/13, proving the new interop fallback did not regress Step 20. `python scripts/contract_boundary_audit.py` passed all 17/17 checks. Desktop `cmd /c npm run build` passed after the App export-path changes.
- External-contract evidence: Step 21 mapping terminology was aligned against current official LangGraph documentation for Graph API, subgraphs, persistence/checkpointers, and interrupts: [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), [Subgraphs](https://docs.langchain.com/oss/python/langgraph/subgraphs), [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence), and [Interrupts / Human-in-the-loop](https://docs.langchain.com/oss/python/langgraph/interrupts).
- Process hygiene: end-of-round read-only listener/process audit again found no AstraBridge-owned local listeners on the standard development ports; the only `:3000` activity was outbound established traffic to a remote host, not a local AstraBridge listener, and no clearly stale AstraBridge-owned `python`/`node`/`cmd` launchers attributable to this step required termination.
- Blockers: None for Step 21. Git/GitHub CLI connection remains explicitly abandoned by user and is not part of this step's acceptance path.
- Next step: Step 22, Migrate, Roll Out, Dogfood, And Close The Reliability Gate.

### 2026-07-17 - Step 22

- Completed: added `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py` as the canonical final rollout owner, `scripts/run_runtime_rollout_gate.py` as its CLI wrapper, `docs/RUNTIME_ROLLOUT_AND_MAINTENANCE_RUNBOOK.md` as the rollout/maintenance boundary, and `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py` as the targeted rollout regression suite. The rollout owner now captures the final feature-flag manifest, compatibility window, single-execution shadow comparison, repeated migration evidence, rollback readback, nested release-gate evidence, Desktop build/capture evidence, and rollout secret scan under `PRIVATE/runtime-rollout/<run-id>/`.
- Stability fixes required to close the gate: fixed `_capture_desktop_visual_qa()` so a successful `returncode=0` capture is not misclassified as failure; fixed live cancel CAS races in `runtime_service.cancel_task_graph_run()` by reloading/retrying on `StateVersionConflict` and short-circuiting when a concurrent update already pushed the durable run into a terminal state; and shortened the nested release-gate / fixture-evidence artifact roots in `runtime_rollout_gate.py` and `runtime_stability_gate.py` so Windows path depth no longer breaks the final release-gate fixture capture. These close-out fixes preserved the earlier Step 22 cancellation truth fix in `task_service.cancel_graph_run()` plus the compact-to-durable artifact sync in `durable_run_store.py`, which were required for shadow-comparison parity.
- Governance updates: `docs/CODE_OWNERSHIP_AND_CONTRACTS.md` now names `astrabridge_sidecar.runtime_rollout_gate` as the only owner for the final rollout feature-flag manifest, compatibility window, shadow-comparison rule, bounded dogfood migration copy, rollback-readback proof, and release-closure evidence bundle. `scripts/contract_boundary_audit.py` now audits that owner, its wrapper, and the rollout runbook, raising the governance suite to 18 checks.
- Validation: focused compilation passed for `runtime_rollout_gate.py`, `runtime_stability_gate.py`, `runtime_service.py`, `durable_run_store.py`, `task_service.py`, `scripts/run_runtime_rollout_gate.py`, and the touched scheduler tests. With `PYTHONPATH=D:\\AstraBridge\\apps\\astrabridge-sidecar`, `python -m unittest discover -s apps/astrabridge-sidecar/tests -p 'test_runtime_rollout_gate.py' -v` passed 3/3; `python -m unittest discover -s apps/astrabridge-sidecar/tests -p 'test_runtime_stability_gate.py' -v` passed 4/4; `python -m unittest -v tests.test_graph_scheduler.DurableGraphSchedulerTests.test_live_cancel_interrupts_running_turn_and_marks_run_cancelled` passed; the five-test scheduler recovery/idempotency suite passed 5/5; the duplicate-delivery scheduler test passed in repeated single-test runs; and `python scripts/contract_boundary_audit.py` passed all 18/18 checks.
- Final rollout evidence: `python scripts/run_runtime_rollout_gate.py --run-id step22-final-rollout-r3` passed with all rollout checks green and preserved the final close-out bundle under `PRIVATE/runtime-rollout/step22-final-rollout-r3/`. The rollout secret scan passed with 0 findings across 514 scanned text artifacts. The nested release gate at `PRIVATE/runtime-rollout/step22-final-rollout-r3/rg/r/` passed in release mode, including `scheduler_recovery_and_idempotency` 20/20 consecutive passes, `terminal_projection_and_stream_recovery` 20/20, `desktop_twenty_restart_cycles_no_orphans` with `internal_passes_per_run=20`, fixture evidence pass, and release-gate secret scan pass.
- Migration / rollback evidence: the Step 22 rollout summary preserved shadow-comparison parity for completed, failed, retry-recovered, cancelled, and approval-pending cases with no mismatches; repeated migration remained idempotent for both the controlled fixture workspace and the bounded dogfood copy of the repository `.astrabridge/tasks.json`; the fixture migration intentionally classified active legacy runs as `needs_review` rather than resuming them; and rollback readback preserved the durable-store hash while rebuilding a projection from the copied snapshot.
- Process hygiene: read-only listener audits before and after the closing rollout round found no AstraBridge-owned listeners on the standard development ports. The nested release gate also preserved before/after process inventories at `PRIVATE/runtime-rollout/step22-final-rollout-r3/rg/r/validations/process-inventory-before.json` and `.../process-inventory-after.json`, and the Desktop orphan-restart suite passed.
- Blockers: None for Step 22. Git/GitHub CLI connection remains explicitly abandoned by user for the duration of this plan and was not retried or treated as a blocker.
- Next step: Plan complete. Optional future work only: revisit the deferred Git/GitHub CLI connection task after this completed plan, and separately reconsider the deferred product-breadth plans referenced in the authority section.
