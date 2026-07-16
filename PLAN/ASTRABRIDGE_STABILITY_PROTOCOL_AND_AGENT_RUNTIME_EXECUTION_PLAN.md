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

- Current status: In progress
- Completed steps: Step 0, Create Durable Execution Plan; Step 1, Reconcile Plan And Contract Ownership; Step 2, Isolate Provider Runtime Client Lanes; Step 3, Establish Canonical Protocol Schemas And Code Generation; Step 4, Add The Workspace-Local Durable Run And Event Store
- Current step: Step 5, Move Live Graph Execution To An Asynchronous Durable Scheduler
- Next step: Step 5, Move Live Graph Execution To An Asynchronous Durable Scheduler
- Last updated: 2026-07-16

## Current Work Unit

- ID: STAB-05
- Goal: Move live graph execution behind an asynchronous scheduler whose durable store is the only state-advancing authority.
- Inputs: `DurableRunEventStore`; `task_service.py` compatibility bridge; `runtime_service.py` graph execution path; Step 4 CAS/lease/outbox primitives.
- Expected output: queued run receipt, background scheduler loop, dependency/parallel dispatch, attempt leases, and projection/event reads without HTTP-lifetime coupling.
- Acceptance check: slow fake-provider creation returns within the bounded receipt budget; closing the caller does not stop the run; dependency ordering and `max_parallelism` hold; only the scheduler advances live state.
- Status: queued
- Next action: Trace the current synchronous live graph entry path and define the smallest scheduler receipt/worker seam without duplicating provider or UI execution.

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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

Status: not started

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
