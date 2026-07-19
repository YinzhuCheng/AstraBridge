# AstraBridge Product Stability And Interoperability Execution Plan

## Plan Authority And Existing-Plan Relationship

This file is the single active execution source for the next AstraBridge product-stability round covering:

- multi-provider runtime correctness and admission control;
- standards-based external agent-to-agent interoperability;
- canonical internal agent communication and durable delivery semantics;
- GUI-authored (including ComfyUI/LangChain-style visual flows) and
  code-authored agent orchestration parity;
- MCP-based tool, resource, and multimodal capability execution;
- signed product updates, migration, rollback, release engineering, and operational closure.

This is a follow-on plan, not a restart. The completed
`PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md`
remains the validated implementation baseline for provider isolation, the
canonical protocol package, durable scheduling, the MCP broker, the NodeType
registry, ComfyUI/LangGraph/LangChain-aligned adapters, runtime
observability, and rollout gates.
Its completed steps and evidence must not be rerun merely because this plan
starts at Step 0.

Historical provider, multimodal, graph, GUI, app-hardening, agentic-update, and
dogfood plans remain preserved according to `docs/DOCUMENT_REGISTRY.json`.
They may supply evidence, fixtures, and contracts, but they are not parallel
schedulers for this scope.

This file is also the preferred durable-handoff entry point for the current
product direction: a stable multi-provider, multi-model Codex shell with
standards-based A2A interoperability, one canonical internal agent
communication format, MCP-normalized multimodal/tool execution, GUI and code
orchestration parity, and rollback-safe automatic upgrade behavior. Future
agents should refresh this file instead of creating a parallel active
stability plan for the same scope.

Positioning lock for future edits:

- AstraBridge remains a multi-provider, multi-model Codex shell rather than a
  provider-specific client shell with optional compatibility shims.
- Multimodal, tool, and resource execution must go through MCP contracts,
  including internal first-party or loopback paths that may be implemented as
  an internal "MCP" but still obey the same authorization, timeout,
  cancellation, audit, and typed-result surface.
- Cross-provider or cross-peer agent communication must map back into one
  AstraBridge-owned durable internal communication ABI; standards-based
  external A2A remains a gateway boundary, not a replacement for the internal
  store schema or run-state machine.
- GUI orchestration may emulate ComfyUI, LangGraph, or LangChain interaction
  patterns, but GUI and code authoring remain projections over one canonical
  graph, executor, and runtime contract.
- Automatic upgrade behavior must stay track-separated, journaled, health
  checked, and rollback safe even when future work expands provider, kernel,
  plugin, or executor update breadth.

## Total Objective

Turn AstraBridge from a strong local multi-provider agent-runtime foundation
into a production-credible, safely upgradable multi-model and multi-provider
Codex shell that:

1. executes every public graph node through an explicit, recoverable executor;
2. maintains provider-neutral context, typed artifacts, cancellation, retry,
   ordering, and idempotency across provider and process boundaries;
3. interoperates with external agents through a standards-based A2A gateway
   without replacing AstraBridge's internal durable execution ABI;
4. keeps MCP as the normal tool, resource, and multimodal capability plane,
   including internal loopback calls that still obey the same contract;
5. supports deterministic GUI authoring, including visual graph authoring that
   can map cleanly to ComfyUI/LangChain-style orchestration expectations, plus
   Python/TypeScript code authoring against one canonical graph definition;
6. upgrades Desktop, Sidecar, provider metadata, kernel, plugins, and node
   executors through signed, journaled, health-checked, rollback-safe flows;
7. makes release quality enforceable through CI, promotion gates, fault tests,
   package verification, and measurable reliability SLOs.

The final outcome is not more visible surface area. It is a stable product
whose advertised capabilities are executable, recoverable, interoperable, and
safe to update.

## Deliverables

- A non-skippable CI and release-promotion path tied to source and artifact digests.
- A persistence-enforced canonical protocol and delivery state machine.
- A provider control plane with bounded concurrency, backpressure, retry budgets,
  cancellation, circuit breaking, and verified capability snapshots.
- A versioned external A2A gateway with Agent Card discovery, task lifecycle,
  streaming, cancellation, artifact exchange, trust policy, and conformance tests.
- A complete executor registry for every public graph node type.
- One canonical graph source with optimistic concurrency, migrations, and
  deterministic GUI/code round trips.
- A visual orchestration surface that can express ComfyUI/LangGraph/LangChain-class
  flow patterns without diverging from the canonical runtime graph contract.
- Typed Python and TypeScript graph SDKs plus lint, compile, diff, and run tooling.
- Signed Desktop/Sidecar update artifacts, clean release staging, transactional
  activation, schema migration, health checks, and rollback.
- Persistent operational metrics, support bundles, process/disk hygiene, and a
  system-level fault-injection matrix.
- Final cross-provider, A2A, GUI/code orchestration, installation, upgrade, and
  rollback evidence preserved under named validation paths.

## Architectural Boundaries

### MCP Capability Plane

- Normal tools, resources, images, audio, video, documents, and other
  multimodal capabilities go through the MCP broker, including internal
  loopback calls used by AstraBridge-owned capabilities.
- MCP authorization, timeout, cancellation, policy, audit, and result semantics
  must remain the same across loopback and remote transports.
- `web.search` remains a standalone web lane even when exposed through MCP.
- MCP Tasks may bridge long-running MCP work, but AstraBridge's durable run
  store remains the canonical execution-state owner.

### Internal Agent Communication Plane

- `AgentEnvelope`, `AgentTask`, `ContentPart`, `ArtifactRef`, delivery records,
  and run events remain AstraBridge-owned internal execution ABI.
- Accepted messages are immutable. Delivery attempt, processing attempt,
  acknowledgement, retry, rejection, expiry, and terminal outcome are separate
  persisted facts.
- Provider-private reasoning, signatures, response identifiers, cookies,
  credentials, and authorization headers never cross the provider boundary.

### External A2A Interoperability Plane

- External A2A wire contracts terminate at an explicit gateway and adapter.
- Agent Cards, external tasks/messages/parts/artifacts, transport negotiation,
  authentication, and remote peer policy do not become the durable-store schema.
- An external A2A version change should normally require gateway changes, not a
  rewrite of graph state, provider adapters, or internal envelopes.
- Cross-provider and cross-peer continuity must be auditable through AstraBridge
  lineage and artifact records even when the remote side uses a different
  provider family or model stack.

### Graph And Executor Plane

- `Graph Definition -> Compiled Plan -> Run Events/Projection` remains a
  one-way ownership chain.
- A node is public only when the registry can prove an installed compatible
  executor for the selected execution mode.
- Recovery behavior is declared per executor as pure, replay-safe, idempotent,
  or non-idempotent; ambiguous effects fail to `needs_review`.
- GUI and code authoring produce the same canonical graph and never silently
  overwrite a code-owned source file.
- Visual authoring may emulate ComfyUI, LangGraph, or LangChain interaction
  patterns, but persisted graph shape, node contracts, executor ownership, and
  runtime semantics remain AstraBridge-owned canonical contracts.

### Upgrade And Release Plane

- Application binaries, provider catalogs, Codex/kernel candidates, and
  plugins/skills/node executors use separate update tracks and trust policies.
- Release artifacts are built from an explicit clean staging allowlist, signed,
  hashed, inventoried, and associated with one source commit and toolchain.
- Activation is journaled and atomic. The prior working version remains
  available until post-update health and migration checks pass.

## Constraints And Attention Notes

1. Preserve `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` and the completed
   stability plan as historical execution records.
2. Preserve `.abproj`, workspace-local `.astrabridge/`, `PRIVATE/**`, logs,
   caches, raw experiment traces, screenshots, and validation reports by default.
3. Never persist or stage API keys, bearer tokens, cookies, authorization
   headers, provider raw secrets, or unredacted remote-agent credentials.
4. Do not reintroduce `.lcr*`, `.codexproj`, `.codex-shell`, official OpenAI
   account login, or normal writes to official Codex configuration paths.
5. Do not merge MCP, external A2A, and the internal durable envelope into one
   schema or one transport abstraction.
6. Do not claim exactly-once network delivery. Use at-least-once delivery plus
   durable idempotency, payload identity, replay protection, and deduplication.
7. Do not expose a GUI node, SDK method, Provider capability, or update channel
   unless the corresponding runtime path and validation evidence exist.
8. Do not replace runtime enforcement with documentation, previews, fixture-only
   behavior, or client-side validation.
9. Prefer contract-preserving extraction over wholesale rewrites of
   `runtime_service.py`, `task_service.py`, `App.tsx`, or
   `TaskGraphWorkspace.tsx`.
10. Live Provider calls are optional, bounded evidence. Prefer deterministic
    fixtures and record any approved live call without secrets.
11. UI steps require deterministic component/E2E tests and preserved visual QA.
12. Before and after Desktop/Sidecar runtime work, audit AstraBridge-owned ports,
    listeners, and stale launcher processes; reap only clearly owned stale state.
13. No external publication, release upload, marketplace update, or platform
    writeback is authorized merely by this plan.
14. Each execution round completes exactly one full numbered step, updates this
    plan's current progress and append-only log, and stops at the next entry point.
15. Rewriting this file from Step 0 is a plan-document reset, not a work reset.
    Carry forward repository-verified results unless new evidence contradicts them.
16. Do not add provider-direct multimodal, tool, or resource execution paths
    that bypass MCP contracts merely for convenience or performance.
17. Do not introduce a second internal agent-message, agent-envelope, or
    peer-communication ABI to satisfy cross-provider compatibility; adaptors
    and gateways must converge back to the canonical durable contract.
18. Do not let GUI-only workflow semantics, node metadata, or export formats
    become a second execution truth distinct from the canonical graph and
    executor/runtime state.
19. Do not convert the automatic update lane into ad hoc installer logic that
    skips staging inventories, trust checks, journals, or rollback readiness.

## Baseline Evidence And Known Gaps

The following evidence was inspected during plan creation on 2026-07-17. Future
agents should re-check the files relevant to their work unit, but must not repeat
a repository-wide audit without contradictory evidence.

- `python scripts/run_local_gate.py --quick` passed in the planning round:
  governance and secret scans were clean, the contract boundary audit passed
  18/18 checks, and the selected local unit suites passed.
- The completed predecessor plan records 22/22 completed reliability steps and
  remains the implementation baseline.
- `protocol/schema/v1/protocol.json` defines canonical envelopes, tasks, events,
  content parts, artifacts, graph definitions, compiled plans, and delivery
  metadata, but persistence still permits runtime vocabulary drift and several
  key objects remain permissive.
- AstraBridge has an internal A2A-like envelope and delivery ledger, but
  `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md` explicitly states that it is not
  an external A2A protocol. No standards-based Agent Card/task gateway is the
  current external boundary.
- Provider transports exist for the major supported families, but Provider
  registration is static and there is no complete shared control plane for
  admission, fairness, rate-limit budgets, circuit breaking, stream integrity,
  cancellation, or live capability verification.
- The compiler records `compiler_executor_id`, while the Live graph path does
  not yet prove dedicated execution for every public MCP, transform, router,
  loop, subgraph, approval, and artifact node.
- The repository currently carries multiple graph representations and graph
  mutations do not consistently require an expected revision, creating a
  last-writer-wins risk for GUI/CLI or multi-window editing.
- Code-first orchestration now has typed Python/TypeScript graph SDKs and
  source-map ownership, but
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`
  still ships a migration-stub default prompt template and
  `apps/astrabridge-sidecar/astrabridge_sidecar/langgraph_stategraph_adapter.py`
  still emits generated `NotImplementedError` bindings for supported export
  families, so scaffold-only outputs remain a residual product risk.
- The signed Desktop updater, release staging allowlist, CI workflows, update
  channels, and atomic activation lanes now exist, but
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md` still documents the broader
  agentic-update system as a proposal-first validation pipeline rather than a
  supervised cross-track auto-upgrade controller.
- `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md` proves provider metadata,
  capability-route, kernel-candidate, and plugin/skill update discovery plus
  validation ownership exists, but it is still a proposal-and-review system
  rather than a journaled track-separated automatic apply/rollback path.
- `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md` records that the normal chat
  multimodal attachment lane can still stall without a useful final answer or
  timeout message, so multimodal stability is not yet fully closed by the
  shared MCP/runtime baseline alone.
- `docs/APP_STANDARDIZATION_UI_DOGFOOD_EVIDENCE.md` records that structured
  tool calling and MCP tool calling remain warning-gated rather than verified
  on some current model routes; authority downgrade visibility must stay part
  of the hardening scope instead of being treated as a cosmetic UI issue.
- `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` still reports a large live
  surface of `partial`, `unsupported`, and `reduced-authority` outcomes, so
  the next stability round should reduce warning-gated defaults instead of only
  expanding the catalog.
- `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`
  currently advertises one supported external A2A protocol version (`1.0`), so
  final product closure still needs explicit negotiation, downgrade, and
  conformance evidence instead of assuming broad version-window stability.
- Repository gate workflows now exist at `.github/workflows/pr-promotion-gate.yml`,
  `.github/workflows/nightly-promotion-gate.yml`, and
  `.github/workflows/release-promotion-gate.yml`, so the remaining risk is clean
  reproducibility and gate freshness rather than workflow absence.
- High-change modules remain concentrated in very large files, notably
  `runtime_service.py`, `task_service.py`, `App.tsx`, and
  `TaskGraphWorkspace.tsx`, increasing review and regression risk.

## Adjustment Policy

Agents may reasonably change substeps, filenames, commands, implementation
details, or the order of future independent steps when repository evidence
requires it. Adjustments must not:

- change the total objective;
- weaken protocol, security, compatibility, recovery, or release guarantees;
- remove negative tests, conformance tests, fault injection, upgrade/rollback
  checks, or visual QA;
- make unsupported functionality appear supported by hiding diagnostics;
- create a second graph, protocol, scheduler, MCP, A2A, updater, or release
  source of truth;
- discard validated code, evidence, or preserved artifacts.

If a core objective is infeasible, record the blocker, evidence, attempted
routes, and a substitute that preserves the original intent. A route change
must update the current work unit and append a plan-review entry before work
continues.

## Evidence Review And Plan Revision Policy

Before each numbered step, inspect the current owner files, the latest relevant
tests, and the newest preserved validation evidence. Trigger a bounded plan
review when:

1. repository code contradicts this baseline;
2. an upstream A2A, MCP, Tauri, Provider, ComfyUI, LangGraph, or Codex contract
   changed incompatibly;
3. a claimed executor, Provider capability, update channel, or recovery path is
   only a fixture/UI projection rather than a real runtime path;
4. a completed step's evidence is insufficient for a later dependency;
5. release, packaging, or documentation work is progressing while the real
   runtime blocker remains unresolved;
6. a step would create a parallel schema, state machine, registry, or owner.

When triggered, record the evidence, diagnosis, smallest route change, invariant
that must not be weakened, and exact next step. Restore one executable work unit
instead of expanding the plan into an open-ended audit.

## Execution Rules

1. Requests to continue, implement, execute, advance, or resume this objective
   default to execution mode.
2. Start from the earliest non-completed numbered step unless the user explicitly
   redirects the work.
3. Name one bounded current work unit, its expected output, and acceptance check
   before implementation.
4. Complete exactly one full numbered step per user-facing execution round.
5. A step is complete only after its acceptance criteria and proportionate
   regression checks pass.
6. Update only Current Progress, Current Work Unit, the completed step status,
   and the append-only Progress Log unless evidence requires a route change.
7. If blocked, record concrete evidence and the exact next action; do not replace
   implementation with repeated documentation.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Follow-On Plan And Activate Ownership;
  Step 1, Make Promotion Gates Non-Skippable And Add CI Entry Points; Step 2,
  Establish One Release Identity And Clean Packaging Staging Contract; Step 3,
  Enforce The Canonical Protocol At Every Durable Write Boundary; Step 4,
  Complete Delivery Identity, Ordering, Expiry, And Cancellation Semantics;
  Step 5, Add Provider Admission, Backpressure, Retry Budgets, And Circuit
  Breaking; Step 6, Complete The Provider Adapter ABI And Verified Capability
  Snapshots; Step 7, Prove Cross-Provider Context And Artifact Continuity On
  Every Handoff Path; Step 8, Define The External A2A Gateway And Agent Card
  Registry; Step 9, Implement A2A Task, Streaming, Cancellation, And Artifact
  Interoperability; Step 10, Add A2A Trust, Replay Protection, Version
  Negotiation, And Conformance; Step 11, Complete Remote MCP Authorization,
  Durable Task Bridging, And Typed Results; Step 12, Implement The Runtime
  Executor Registry And Capability Matrix; Step 13, Implement Live MCP,
  Transform, Router, And Artifact Executors; Step 14.1, Implement Live
  Durable Approval Pause And Resolution; Step 14.2, Implement Loop And
  Subgraph Live Executors; Step 14.3, Extend Live Recovery, Resume, And Reuse
  Semantics; Step 16.1, Land The Python SDK Foundation And Deterministic
  Source-Owned Canonical Emission; Step 16.2, Add The TypeScript SDK Canonical
  Builder And Cross-Language Fixture Parity; Step 16.3, Add Source Maps, Code
  Ownership, And GUI Detached-Edit Protection; Step 16.4, Add Run, Inspect,
  Export, And Round-Trip Parity Across Python And TypeScript; Step 17.1, Add
  A Canvas Command Log Foundation For Current Graph Mutations; Step 17.2, Add
  Destructive Edit History, Node Deletion, And Undo/Redo Safety; Step 17.3.1,
  Add Live Runtime Visibility To The Debugger Surface; Step 17.3.2, Prove
  Cursor-Based Reconnect Without Missing Or Duplicated Events; Step 17.4.1,
  Add Dialog Focus And Keyboard Accessibility Hardening; Step 17.4.2, Add
  Large-Graph Scale Hardening; Step 17.4.3, Add Deterministic Task-Graph
  Playwright E2E Coverage; Step 18.1, Establish Explicit Updater Channel
  Contract And Gate Validation; Step 18.2, Integrate Signed Tauri Updater
  Configuration And Fail-Closed Endpoint Policy; Step 18.3, Bundle
  Version-Matched Sidecar Releases And Remove Source Fallback From Formal
  Packages; Step 18.4, Add Explicit Channel Selection, Kill Switch
  Surfacing, And Isolated Windows Update Validation; Step 19.1, Add A Desktop
  Formal-Bundle Transaction Journal Foundation And Interruption Recovery Proof;
  Step 19.2, Journal Provider Metadata And Capability Route Apply Tracks;
  Step 19.3.1, Journal Codex Kernel Candidate Activation Gate Verification;
  Step 19.3.2, Journal Plugin And Skill Activation;
  Step 19.3.3.1, Journal Runtime-Directory Activation;
  Step 19.3.3.2, Journal Node-Executor Activation; Step 19.4.1, Add
  Transactional Store Bootstrap, Revision Guard, And Backup Journals; Step
  19.4.2, Prove Rollback And Readback Across Persisted Durable State; Step
  19.5, Harden Update Discovery Against Redirect, SSRF, Type, Size, And
  Replay Abuse; Step 21.1, Extract Task-Graph Mutation And Import/Export
  Owner; Step 21.2, Extract Runtime-Service Dispatch And Cancellation
  Coordination; Step 22.1, Extract TaskGraphWorkspace Shell-State And
  Persistence Owner; Step 22.2, Extract App-Level Task-Graph Selection And
  Run Monitoring Owner; Step 22.3, Extract TaskGraphWorkspace Canvas And
  Inspector View Owner; Step 23.1, Re-Run Runtime Rollout, Rollback-Readback,
  And Nested Release Gate On The Current State; Step 23.2, Re-Run Final
  GUI/Code/A2A/MCP/Interop Closure Evidence; Step 23.3, Re-Run Final
  Promotion/Readiness Closure And Publish The Final Evidence Index; Step 24,
  Close Warning-Gated Model Authority And Multimodal Completion Gaps; Step 25,
  Turn Provider And A2A Capability Claims Into Refreshable Verified Manifests;
  Step 26, Make Generated Orchestration Exports Executable Instead Of
  Scaffold-Only; Step 27, Harden Graph Import, Migration, And Multi-Author
  Concurrency Boundaries; Step 28, Promote The Update Pipeline To A Supervised
  Cross-Track Auto-Upgrade Controller; Step 29.1, Add Long-Horizon Stability
  Bundle And Supervised-Updater Containment Soak; Step 29.2, Add Injected
  Cross-Lane Chaos Drills; Step 29.3, Publish Consolidated Operator Recovery
  Playbooks; Step 30.1, Audit Remaining Shell Modules And Land Budget Guardrails;
  Step 30.2, Extract RuntimeService Dispatch And Runtime-Lifecycle Shell Owners;
  Step 30.3, Extract TaskService Graph-Document And Persistence Shell Owners;
  Step 30.4, Extract Desktop App And TaskGraphWorkspace Shell Owners;
  Step 30.5, Close Characterization Coverage And Refresh Shell Budgets
- Current step: None - all numbered steps completed
- Next step: None - plan complete
- Last updated: Sunday, July 19, 2026

## Current Work Unit

- ID: STAB-23-3-FINAL-READINESS-CLOSURE
- Goal: return to the final promotion/readiness closure lane and reconcile the
  remaining top-level in-progress plan statuses against current repository
  evidence before claiming the full plan complete.
- Inputs:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `PRIVATE/shell-module-budget/step30-5/summary.json`,
  the latest promotion/readiness artifacts already preserved under
  `PRIVATE/`, and the current evidence referenced by Steps 23.1-23.3, 24, and
  29.
- Expected output: updated final-closure evidence and authoritative plan state
  showing whether the remaining top-level acceptance lanes can be marked
  complete on current evidence or must stay open with a concrete residual gap.
- Acceptance check: Step 23.3 has a current-state evidence verdict, the next
  unresolved plan-closure gap is explicit, and the authoritative plan has one
  unambiguous next entry point.
- Status: completed
- Latest evidence: final Step 23.3 closure evidence is preserved at
  `PRIVATE/final-closure/step23-3-final-evidence-index-r4/summary.json`,
  including the refreshed current release-readiness pass, the refreshed
  current dirty-tree fail-closed diagnostic, the clean-snapshot runtime
  rollout pass, and the clean-snapshot release promotion pass bound to
  snapshot commit `8bff009c03f3c9c0a26086f9c50720a262c301e5`.
- Next action: None. All numbered execution steps in this plan are complete.

## Execution Steps

### 0. Create Durable Follow-On Plan And Activate Ownership

Goal: Land the follow-on plan and make it the unambiguous current execution queue.

Main actions:

- Preserve the completed predecessor plan and its validated evidence.
- Create this plan with one active work unit and numbered acceptance criteria.
- Update the document registry, current-entry documentation, project memory, and
  ownership references so future agents do not resume an obsolete queue.
- Run governance and secret checks for the plan-only change.

Acceptance criteria:

- This plan exists and contains all durable-plan control sections.
- `docs/DOCUMENT_REGISTRY.json` names this file as `current_execution_plan`.
- The completed predecessor plan is classified as complete with this replacement.
- Current README, handoff, summary, governance, registry, interface-governance,
  and ownership references agree on the new execution source.
- Governance and secret checks pass.

Status: completed

### 1. Make Promotion Gates Non-Skippable And Add CI Entry Points

Goal: Turn local validation into enforceable PR, nightly, and release promotion checks.

Main actions:

- Add a promotion mode in which required `skipped`, `missing`, `unknown`, or
  unevaluated checks are non-promotable.
- Bind gate summaries to commit SHA, dirty state, toolchain versions, check set,
  and artifact digests.
- Add deterministic PR, nightly, and tag/release workflow entry points.
- Preserve sanitized logs, reports, and failure artifacts.
- Add negative tests for omitted checks and forged/incomplete summaries.

Acceptance criteria:

- Skipping any required promotion check produces a non-zero result.
- PR and release workflows use repository locks and invoke canonical scripts
  rather than duplicating suite lists.
- A dirty tree, wrong commit, missing report, or `unknown` SLO cannot promote.
- Focused tests plus the quick local gate pass.

Status: completed

### 2. Establish One Release Identity And Clean Packaging Staging Contract

Goal: Make every product artifact traceable to one version, source commit, and allowlisted staging manifest.

Main actions:

- Introduce one release/version manifest consumed by Desktop, Sidecar, Tauri,
  MCP server metadata, protocol compatibility, and updater manifests.
- Build Sidecar/Desktop packages from a clean explicit staging allowlist.
- Exclude `.venv`, tests, `PRIVATE`, caches, local state, absolute machine paths,
  and unapproved development files.
- Emit a file inventory, hashes, dependency-lock digest, SBOM input, and source provenance.

Acceptance criteria:

- Version drift across package metadata fails a release check.
- Two clean staging runs produce identical file inventories and content hashes,
  except for explicitly documented nondeterministic metadata.
- Forbidden local/development paths are absent from the staged package.
- The packaged Desktop/Sidecar release identity is verified during readiness.

Status: completed

### 3. Enforce The Canonical Protocol At Every Durable Write Boundary

Goal: Prevent runtime, legacy, database, Python, and TypeScript protocol vocabulary from drifting.

Main actions:

- Validate all persisted envelopes, tasks, events, content parts, artifacts, and
  graph/run projections at the innermost durable-store write boundary.
- Generate or centrally derive event/state vocabularies from the canonical schema.
- Replace permissive control-object fields with namespaced extensions where safe.
- Add one shared golden corpus for Python, TypeScript, migration, and database round trips.

Acceptance criteria:

- Unregistered events, invalid versions, missing fields, and forbidden payloads
  cannot enter the durable store.
- Runtime-discovered event/state symbols exactly match the canonical schema.
- Golden valid/invalid fixtures pass identically in Python, TypeScript, migration,
  and persistence tests.
- Current and documented N-1 reads remain compatible or fail with an actionable error.

Status: completed

### 4. Complete Delivery Identity, Ordering, Expiry, And Cancellation Semantics

Goal: Make agent delivery and cancellation deterministic under duplication, delay, races, and restart.

Main actions:

- Separate immutable message identity, delivery attempt, and processing attempt.
- Enforce payload-hash conflict detection, sequence policy, TTL, deadline,
  not-before, replay window, and late-result handling.
- Implement the cancellation state machine and enforce grace timeout.
- Prevent late completions from reviving cancelled runs or scheduling new work.

Acceptance criteria:

- Duplicate same-payload deliveries deduplicate; same key with different payload rejects.
- Expired, early, replayed, out-of-policy, and mismatched-audience messages reject before dispatch.
- Cancellation converges through documented terminal states after success, failure,
  no response, restart, and cancellation/completion races.
- Property and deterministic race tests pass.

Status: completed

### 5. Add Provider Admission, Backpressure, Retry Budgets, And Circuit Breaking

Goal: Prevent Provider overload, retry storms, starvation, and unbounded graph admission.

Main actions:

- Add global, Provider, model, MCP server, workspace, and graph concurrency controls.
- Replace unbounded admission with bounded queues, priority, and fairness rules.
- Normalize connect, first-byte, idle, and total timeouts.
- Honor structured retry metadata and `Retry-After` with jittered backoff and budgets.
- Add per-Provider/model circuit breakers and half-open probes.

Acceptance criteria:

- A 100-branch graph never exceeds configured limits.
- Interactive work is not indefinitely starved by bulk graph runs.
- 429/5xx/transport faults do not produce retry storms.
- Cancelled queued work never dispatches, and breaker state is observable and redacted.

Status: completed

Implementation notes:

- Added `apps/astrabridge-sidecar/astrabridge_sidecar/graph_dispatch_control.py`
  to own live graph retry budgets plus provider/model circuit-breaker state.
- Normalized live graph parallel groups into bounded batches before dispatch so
  configured admission ceilings are enforced structurally instead of by best
  effort.
- Added scheduler queue capacity and queued-cancel skip-dispatch handling so a
  cancelled queued run never reaches the provider callback.
- Exposed redacted graph dispatch and breaker status through runtime
  environment snapshots.
- Added targeted tests for queued cancellation, bounded parallel-group
  dispatch, retry-budget storm suppression, and observable circuit-open
  blocking.

Validation:

- `python -m unittest tests.test_graph_scheduler` passed 24/24.
- `python -m unittest tests.test_runtime_client_pool` passed 7/7 with
  `ASTRABRIDGE_RUNTIME_ROOT` redirected into a writable local test root.
- `python scripts\contract_boundary_audit.py` passed 21/21 checks.
- `python scripts\run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings.
- `git diff --check` reported only CRLF conversion warnings and no
  content-format failures.

### 6. Complete The Provider Adapter ABI And Verified Capability Snapshots

Goal: Make Provider support extensible and ensure advertised capabilities match tested runtime behavior.

Main actions:

- Extend the Provider adapter contract to own request conversion, stream parsing,
  response normalization, structured errors, cancellation, and capability probes.
- Move Provider-specific branching out of the shared router where feasible.
- Record declared, probed, verified, stale, and incompatible capability states
  per Provider/model/adapter revision.
- Add provider-family golden wire fixtures and a reusable conformance suite.

Acceptance criteria:

- Adding a conforming Provider adapter does not require new router condition chains.
- Graph admission uses a pinned capability snapshot, not static booleans alone.
- Adapter/model updates invalidate stale verification and require canary evidence.
- Every built-in Provider passes the shared request/stream/error/cancel conformance suite.

Status: completed

Implementation notes:

- Added `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_snapshot.py`
  as the shared owner for versioned verified capability snapshots, current
  provider-adapter contract fingerprints, snapshot aggregation, and graph-port
  capability projection.
- Extended `router_config_service.py` so provider compatibility-matrix evidence
  produces persisted per-model verified capability snapshots, and adapter/model
  contract changes automatically mark stale verification instead of leaving old
  claims active.
- Tightened `agent_orchestration_checks.py` and `runtime_service.py` so live
  graph admission uses current configured model records plus pinned verified
  capability snapshots for multimodal port requirements, and queued/live run
  policy manifests now preserve the model-capability snapshot that admission
  approved.
- Extended the provider transport ABI in
  `providers/transports/base.py` with shared structured error classification and
  cancellation-contract reporting, and added a reusable built-in transport
  conformance suite for request shape, streaming, normalization, error, and
  cancellation behavior.
- Added focused Step 6 regression coverage for snapshot aggregation, stale
  invalidation, pinned live-run policy snapshots, and shared provider transport
  conformance.

Validation:

- `python -m unittest tests.test_provider_capability_snapshot
  tests.test_provider_transport_conformance tests.test_router_transport_registry
  tests.test_graph_scheduler tests.test_runtime_client_pool
  tests.test_provider_capability_verification_gate` passed 44/44 with
  `ASTRABRIDGE_RUNTIME_ROOT` redirected into a writable local runtime root.
- `python scripts\contract_boundary_audit.py` passed 21/21 checks.
- `python scripts\run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings.
- `git diff --check` reported only CRLF conversion warnings and no
  content-format failures.

### 7. Prove Cross-Provider Context And Artifact Continuity On Every Handoff Path

Goal: Ensure ordinary Provider switching and graph handoffs deliver the same safe neutral context semantics.

Main actions:

- Inject validated projected visible history, tool pairing, typed inputs, and
  artifact references into the target turn rather than storing preview-only evidence.
- Keep provider-private reasoning, signatures, response IDs, and hidden metadata out.
- Persist deterministic projection digests linking handoff event and target dispatch.
- Cover new target thread, reused target thread, and process-restart paths.

Acceptance criteria:

- Supported Provider-family switches preserve visible task continuity and artifacts.
- Private Provider state never appears in target requests, logs, events, or bundles.
- Projection digest and source/target lineage can be audited end to end.
- Handoff tests cover graph and ordinary user-visible switching paths.

Status: completed

### 8. Define The External A2A Gateway And Agent Card Registry

Goal: Establish a standards-based external boundary without changing the internal execution ABI.

Main actions:

- Pin the supported external A2A version window and document mapping boundaries.
- Define Agent Card discovery, extended-card handling, capability declarations,
  authentication metadata, transport support, and card digests.
- Add an Agent Card registry with workspace trust level and immutable run snapshots.
- Define bidirectional mapping between external tasks/messages/parts/artifacts and
  internal envelopes/events.

Acceptance criteria:

- Agent Cards are machine-validated, versioned, digest-pinned, and resolvable at compile/admission time.
- Unsupported transports, modalities, auth modes, or versions fail before task dispatch.
- Mapping fixtures preserve identity, status, content, artifact lineage, and extensions.
- External A2A fields do not become new durable-store owners.

Status: completed

### 9. Implement A2A Task, Streaming, Cancellation, And Artifact Interoperability

Goal: Complete a real two-process external A2A interaction through the gateway.

Main actions:

- Implement task submission, status retrieval, message/artifact exchange,
  streaming events, cancellation, and supported push behavior.
- Translate external lifecycle states to internal durable events without losing causality.
- Apply idempotency and effect-journal rules to inbound and outbound external operations.
- Preserve bounded, redacted remote interaction evidence.

Acceptance criteria:

- Two independent local processes complete discovery, task execution, streaming,
  cancellation, and artifact transfer through the supported A2A interface.
- Disconnect/reconnect, duplicate request, delayed response, and remote failure tests pass.
- External cancellation reaches the executing Provider/tool lane.
- No secret, private reasoning, or unsafe artifact path crosses the gateway.

Status: completed

### 10. Add A2A Trust, Replay Protection, Version Negotiation, And Conformance

Goal: Make external agent interoperability secure and upgradeable rather than merely reachable.

Main actions:

- Enforce issuer, audience, workspace/tenant binding, authorization policy,
  replay windows, message size limits, and peer trust levels.
- Support negotiated protocol/extensions and explicit downgrade/rejection behavior.
- Verify signed Agent Cards when configured and preserve trust decisions.
- Build an A2A conformance kit and negative security corpus.

Acceptance criteria:

- Expired, replayed, wrong-audience, untrusted, oversized, and incompatible requests reject.
- Supported version negotiation is deterministic and observable.
- Security/conformance fixtures are reusable by third-party agent adapters.
- A gateway version upgrade does not require an internal graph/durable-store migration.

Status: completed

### 11. Complete Remote MCP Authorization, Durable Task Bridging, And Typed Results

Goal: Make remote MCP and long-running multimodal/tool work production-safe while preserving one capability plane.

Main actions:

- Add the required remote MCP authorization discovery and least-scope policy.
- Map eligible long-running MCP operations to durable AstraBridge runs/tasks while
  keeping the durable store authoritative.
- Preserve MCP text/image/audio/resource links, annotations, progress, cancellation,
  and errors losslessly in `ContentPart` and `ArtifactRef`.
- Add session pooling/recovery and MCP conformance/fuzz fixtures.

Acceptance criteria:

- Remote authorization uses discovered protected-resource metadata and rejects
  wrong-resource or over-broad tokens.
- Long MCP work survives Sidecar restart without duplicate side effects.
- Typed multimodal results round-trip without path leaks or silent text flattening.
- Loopback and remote transports pass the same policy/result/cancellation suite.

Status: completed

### 12. Implement The Runtime Executor Registry And Capability Matrix

Goal: Ensure every public graph node resolves to a compatible Live or Fixture executor.

Main actions:

- Add an executor lifecycle interface keyed by `compiler_executor_id`.
- Record executor version, supported modes, checkpointing, cancellation, side-effect
  classification, input/output schemas, and capability dependencies.
- Make compile/dry-run/admission fail closed for unavailable or incompatible executors.
- Expose an executor capability matrix to the GUI and code SDK.

Acceptance criteria:

- `compiler_executor_id` is consumed by Live dispatch.
- Unknown, disabled, stale, or incompatible executors cannot call Providers or tools.
- Public palette/SDK nodes display accurate Live/Fixture availability.
- Registry fingerprint drift is detected before execution.

Status: completed

### 13. Implement Live MCP, Transform, Router, And Artifact Executors

Goal: Close the first mixed-graph Live execution gap with deterministic local executors.

Main actions:

- Implement MCP tool/resource, transform, router/condition, artifact source, and
  artifact sink executors through the shared lifecycle.
- Enforce typed ports, least-privilege MCP policy, artifact integrity, and branch semantics.
- Record executor-specific checkpoints and redacted input/output hashes.
- Add mixed-graph live tests with no network dependency.

Acceptance criteria:

- `agent -> MCP -> transform/router -> branch -> artifact sink` executes live.
- Only selected conditional edges run.
- Invalid tool policy, schema, artifact digest, or output fails before downstream effects.
- Restart and duplicate-delivery tests produce the same terminal projection as baseline.

Status: completed

### 14. Implement Durable Approval, Loop, Subgraph, And Recovery Semantics

Goal: Complete stateful orchestration nodes and make recovery behavior explicit.

Main actions:

- Implement human approval as a durable pause with approve/reject/expiry policy.
- Define bounded loop semantics without permitting uncontrolled graph cycles.
- Execute subgraphs with pinned definitions, isolated trace scopes, and explicit I/O contracts.
- Persist effect classification, checkpoint, reused output, and child-attempt lineage.

Acceptance criteria:

- Restart preserves an approval pause and approval prevents prior downstream side effects.
- Loop limits, cancellation, and timeout are enforced and visible.
- Subgraph trace/state is isolated but causally linked to the parent.
- Retry/selected rerun identifies reused versus re-executed nodes and never repeats
  ambiguous non-idempotent effects automatically.

Status: completed

#### 14.1 Implement Live Durable Approval Pause And Resolution

Goal: Make the human-approval node pause live execution durably and preserve its
resolution record across reloads.

Main actions:

- Enable the live `human_approval` executor in the node-type registry.
- Pause live execution with durable `approval_state` / `approval_details`
  instead of collapsing the gate into a generic failure path.
- Preserve the pending pause through run snapshots, manifest writes, and
  reload/reopen flows.
- Resolve approve/reject decisions through the existing approval API without
  dispatching provider turns or downstream side effects before approval.

Acceptance criteria:

- A live run can reach `paused_for_review` through a `human_approval` node.
- Reloading task/run state preserves the pending approval details.
- Approve or reject decisions persist durable approval resolution state.
- No provider turn or downstream handoff is emitted by the approval node before
  the human decision exists.

Status: completed

#### 14.2 Implement Loop And Subgraph Live Executors

Goal: Land the first restart-safe live executors for loop and subgraph control
 nodes.

Main actions:

- Implement bounded live loop execution with explicit iteration state and
  checkpoint-safe stop conditions.
- Implement live subgraph invocation with pinned graph definitions, isolated
  trace scopes, and typed input/output projection.
- Preserve loop/subgraph state in durable manifests so restart does not rerun
  ambiguous effects blindly.

Acceptance criteria:

- Loop limits, cancellation, and timeout are enforced and visible.
- Subgraph trace/state is isolated but causally linked to the parent.
- Live loop/subgraph execution preserves typed I/O and checkpoint metadata
  across restart-safe state transitions.

Status: completed

#### 14.3 Extend Live Recovery, Resume, And Reuse Semantics

Goal: Finish the stateful recovery path after approval, loop, and subgraph
execution semantics exist.

Main actions:

- Add live recovery/resume for paused approval and later stateful control runs.
- Distinguish reused output, replayed deterministic work, and re-executed
  side-effecting work in durable lineage.
- Keep ambiguous non-idempotent paths in `needs_review` rather than automatic
  replay.

Acceptance criteria:

- Restart preserves an approval pause and later recovery can continue the
  downstream path without prior side effects firing early.
- Retry/selected rerun identifies reused versus re-executed nodes and never
  repeats ambiguous non-idempotent effects automatically.

Status: completed

### 15. Converge Graph Definitions, Revisions, And Version Migrations

Goal: Establish one writable canonical graph with safe concurrent editing and upgrade semantics.

Main actions:

- Make the canonical orchestration/protocol graph the only writable persisted source.
- Retain TaskGraph as a generated compatibility projection with an explicit sunset path.
- Require expected revision/ETag on graph mutations and return structured 409 conflicts.
- Add graph and node-type migration chains, version pins, compatibility ranges,
  upgrade preview, backup, and rollback.

Acceptance criteria:

- Two clients editing the same revision cannot silently overwrite each other.
- Conflict resolution preserves non-conflicting node, edge, policy, and layout edits.
- N-2 graph migration is idempotent, preserves extensions, and can roll back.
- Running plans remain pinned even when registry/node definitions change.

Status: completed

#### 15.1 Establish Canonical Graph Documents And Revision Tokens

Goal: make each persisted graph record carry one canonical orchestration-backed
document plus explicit revision tokens before broader migration and merge work.

Main actions:

- Introduce a canonical graph-document layer on persisted graph records.
- Persist revision id, revision index, and ETag metadata with each graph write.
- Route save/import/node/edge/rollback mutation paths through the canonical
  document and fail closed on stale revision tokens.
- Keep TaskGraph as a compatibility projection while export/import and rollback
  paths continue to operate on the canonical orchestration payload.

Acceptance criteria:

- Persisted graph records expose canonical graph-document metadata and revision tokens.
- Save/import/update/rollback mutations reject stale revisions with structured 409 conflict payloads.
- Existing orchestration/comfyui/langgraph round-trip and snapshot rollback paths continue to pass against the canonical document-backed graph records.

Status: completed

#### 15.2 Add Graph-Document Migration Chains, Compatibility Ranges, And Rollback Preview

Goal: turn the new canonical graph document into an explicitly versioned,
upgradeable, and rollback-inspectable persisted artifact.

Main actions:

- Add graph-document migration chains and compatibility ranges that survive repeated reads and writes.
- Surface rollback-preview evidence for document version, migration origin, and compatibility mode.
- Keep migration application idempotent for legacy and current graph-document states.

Acceptance criteria:

- Repeated reads and writes do not change graph-document migration state unless a real write occurs.
- Compatibility ranges stay explicit for TaskGraph and orchestration schema consumers.
- Snapshot and rollback evidence identify the graph-document version and migration origin being restored.

Status: completed

#### 15.3 Preserve Non-Conflicting Edits During Revision Conflicts

Goal: move from fail-closed stale-write detection to conflict handling that can
preserve non-overlapping graph edits deterministically.

Main actions:

- Add structured conflict payloads that separate base, current, and incoming edits.
- Preserve non-conflicting node, edge, policy, and layout edits while rejecting overlapping writes.
- Cover direct task-graph edits and orchestration-backed compatibility edits with the same conflict contract.

Acceptance criteria:

- Non-conflicting concurrent edits can be preserved without silently overwriting newer graph state.
- Overlapping edits still fail closed with enough detail to resolve them deterministically.
- Conflict handling stays aligned with the canonical graph document rather than reintroducing TaskGraph as a writable source.

Status: completed

### 16. Ship Python And TypeScript Code-Orchestration SDKs

Goal: Make code-authored workflows first-class consumers of the same compiler/runtime as the GUI.

Main actions:

- Provide typed Python and TypeScript builders for agents, MCP calls, routes,
  approvals, loops, subgraphs, artifacts, policies, and typed ports.
- Add lint, compile, semantic diff, run, inspect, and export CLI/API entry points.
- Generate deterministic canonical graph artifacts and source maps containing
  file, symbol, line, and digest ownership.
- Define source-owned versus detached-GUI edit behavior.

Acceptance criteria:

- SDK graphs lint, compile, run, open in the GUI, export, and reload.
- `code -> GUI -> canonical JSON -> GUI -> code` round trips with no semantic diff
  beyond documented transient metadata.
- GUI never silently overwrites a source-owned graph.
- Python and TypeScript SDK fixtures produce identical canonical definitions.

Status: completed

### 16.1. Land The Python SDK Foundation And Deterministic Source-Owned Canonical Emission

Goal: create the first code-authored entry path that can emit canonical graphs
from Python without leaking validator-derived runtime fields into source-owned
artifacts.

Main actions:

- Add a typed Python builder surface that can author canonical orchestration
  graphs, write deterministic JSON, and call the existing compile/lower paths.
- Add a `compile` CLI/report entry point so code-authored canonical graph files
  can be compiled without going through GUI-only flows.
- Keep the source-owned file format stable by stripping validator-derived
  node-type registry fields from parse/load/write round trips.
- Prove that SDK-authored graphs can compile, lower, and import through the
  current task-service orchestration path, while recording any remaining
  compatibility-projection deltas explicitly rather than hiding them.

Acceptance criteria:

- A Python SDK builder can author canonical graph payloads and deterministic
  JSON files.
- A canonical graph file can be compiled through a dedicated CLI/report path.
- Source-owned file-format round trips no longer inject derived node-type
  registry fields into authored graph files.
- Repository tests prove Python SDK-authored graphs compile, lower, and import
  through the current compatibility path.

Status: completed

### 16.2. Add The TypeScript SDK Canonical Builder And Cross-Language Fixture Parity

Goal: mirror the Python foundation in TypeScript and begin proving
cross-language canonical parity from shared workflow fixtures.

Main actions:

- Add a TypeScript builder surface that can author the same source-owned
  canonical graph payload shape as the Python SDK for at least one shared
  workflow fixture.
- Reuse the current canonical graph/runtime types rather than introducing a
  parallel TypeScript schema or GUI-only authoring contract.
- Preserve deterministic JSON emission and diffability against the Python
  fixture output.

Acceptance criteria:

- At least one shared workflow fixture emits matching or semantically equivalent
  canonical graphs from Python and TypeScript.
- Existing compile/diff paths can validate the TypeScript-authored canonical
  file without special-case adapters.
- No parallel schema or detached emission contract is introduced.

Status: completed

### 16.3. Add Source Maps, Code Ownership, And GUI Detached-Edit Protection

Goal: make code-owned graph artifacts auditable and prevent GUI edits from
silently overwriting source-authored workflows.

Main actions:

- Generate source maps with file, symbol, line, and digest ownership for
  code-authored canonical graphs.
- Define source-owned versus detached-GUI edit behavior and surface it at the
  graph-document/API/UI boundary.
- Fail closed when the GUI attempts to overwrite a source-owned graph without
  an explicit detach or export-to-new-source flow.

Acceptance criteria:

- Code-authored canonical graphs carry inspectable source ownership metadata.
- GUI edits never silently overwrite a source-owned graph.
- Graph-document/API evidence makes detach versus source-owned state explicit.

Status: completed

### 16.4. Add Run, Inspect, Export, And Round-Trip Parity Across Python And TypeScript

Goal: finish the SDK/runtime loop so code-authored graphs behave as first-class
peers of GUI-authored graphs.

Main actions:

- Add the remaining run, inspect, semantic diff, and export entry points for
  SDK-authored graphs.
- Prove `code -> GUI -> canonical JSON -> GUI -> code` round trips with only
  documented transient metadata differences.
- Preserve one canonical graph source while proving the same runtime/compiler
  path works for GUI, Python, and TypeScript authored workflows.

Acceptance criteria:

- SDK-authored graphs lint, compile, run, open in the GUI, export, and reload.
- `code -> GUI -> canonical JSON -> GUI -> code` round trips with no semantic
  diff beyond documented transient metadata.
- Python and TypeScript SDK fixtures produce identical canonical definitions.

Status: completed

### 17. Harden The GUI Editor, Live Debugger, And Deterministic E2E Path

Goal: Make visual orchestration safe and usable for large, long-running workflows.

Main actions:

- Add a command log for node deletion, undo/redo, copy/paste, multi-select,
  grouping/subgraphs, and deterministic layout persistence.
- Add executor availability, semantic validation, breakpoint, pause-before/after,
  branch decision, node input/output diff, replay, and critical-path views.
- Replace repeated full polling with cursor-based reconnectable event delivery.
- Add large-graph virtualization/layout workers, keyboard/accessibility checks,
  and deterministic Playwright E2E.

Acceptance criteria:

- The E2E path covers create/edit/wire/save/reload/import/export/dry-run/live
  fixture/approval/cancel/restart/resume with preserved diagnostics.
- Fifty undo/redo operations remain consistent and node deletion leaves no
  orphan edge.
- Event reconnect produces no missing or duplicated durable events.
- A 500-node graph remains within documented interaction and memory budgets.

Status: completed

### 17.1. Add A Canvas Command Log Foundation For Current Graph Mutations

Goal: give operators immediate visibility into the canvas mutations that are
already supported today, without waiting for full undo/redo or multi-select.

Main actions:

- Audit the current Desktop-side create/move/save/delete-edge/detach flows and
  record which mutations already have stable App-level write seams.
- Add a bounded in-session command log that records current graph mutations with
  pending/applied/failed state and expose it in the run inspection workspace.
- Add focused UI regression coverage so command-log visibility survives the
  existing source-owned graph, dry-run, and latest-run surfaces.

Acceptance criteria:

- Current canvas write operations append visible command-log entries with
  readable status.
- Failed writes can surface a failed command-log entry instead of silently
  disappearing from the operator view.
- The command-log UI passes focused Desktop typecheck and workspace tests.

Status: completed

### 17.2. Add Destructive Edit History, Node Deletion, And Undo/Redo Safety

Goal: make destructive canvas edits reversible and prevent node deletion from
leaving orphaned edges or confusing selection state.

Main actions:

- Add node deletion through the same App/task-service seam already used by
  create/move/save/delete-edge flows.
- Introduce bounded local undo/redo history for destructive canvas edits and
  connect it to the new command-log foundation.
- Prove repeated delete/undo/redo cycles keep the graph, selection state, and
  persisted edge set consistent.

Acceptance criteria:

- Node deletion is available and removes connected edges deterministically.
- Repeated undo/redo cycles restore the same graph state without orphan edges.
- Focused Desktop tests cover delete/undo/redo state transitions.

Status: completed

### 17.3. Add Live Debugger Visibility And Reconnectable Event Delivery

Goal: turn the existing runtime evidence into a debugger surface that remains
trustworthy across reconnects and long-running runs.

Main actions:

- Split debugger visibility and reconnect proof into separate bounded execution
  slices so each turn can finish one numbered step without weakening the Step
  17 acceptance bar.
- Extend the current run workspace with executor availability, semantic
  validation, branch decision, replay, and node/edge I/O diff visibility where
  the data already exists.
- Build on the current cursor-based event stream foundation and remove any
  remaining repeated full-poll fallback paths for graph run inspection.
- Add regression coverage proving reconnect resumes without missing or
  duplicating durable events.

Acceptance criteria:

- Runtime inspection exposes the required debugger signals for at least one
  bounded execution path.
- Event reconnect preserves ordered durable graph events without duplicates.
- Focused Desktop/sidecar tests prove the reconnect path.

Status: completed

### 17.3.1. Add Live Runtime Visibility To The Debugger Surface

Goal: expose the runtime policy and event-level execution signals that already
exist in run evidence so operators can understand what the graph is doing
before reconnect recovery is tightened.

Main actions:

- Audit the current run workspace and latest-run payloads for policy snapshot,
  concurrency, scheduling, approval, recovery, and selected-event details that
  can be surfaced without inventing new runtime state.
- Add the smallest trustworthy execution-profile and selected-event visibility
  slice to the Desktop debugger surface.
- Add focused Desktop regression coverage proving the new visibility survives
  the current command log, approval, recovery, dry-run, and latest-run
  workspace paths.

Acceptance criteria:

- The run workspace exposes at least one bounded execution-profile view backed
  by current runtime evidence rather than placeholder UI state.
- Selected-event inspection shows materially useful live-debugger detail for at
  least one bounded run path.
- Desktop typecheck and focused workspace tests pass.

Status: completed

### 17.3.2. Prove Cursor-Based Reconnect Without Missing Or Duplicated Events

Goal: prove the graph-run event stream can reconnect from the durable cursor
without regressing ordering, duplication, or operator trust.

Main actions:

- Audit the current Desktop stream subscription and fallback polling path
  against the Sidecar runtime-events cursor contract.
- Remove or narrow any remaining repeated full-poll path that bypasses the
  durable cursor semantics for graph-run inspection.
- Add focused Desktop and Sidecar regression coverage proving reconnect resumes
  from the correct cursor without missing or duplicating durable events.

Acceptance criteria:

- Graph-run event inspection resumes from the durable cursor after reconnect.
- Reconnect proof covers ordered delivery with no missing or duplicated durable
  events for the bounded validated path.
- Focused Desktop and Sidecar reconnect tests pass.

Status: completed

### 17.4. Add Large-Graph Performance Hardening, Accessibility, And Deterministic E2E

Goal: finish Step 17 with scale safety, accessibility checks, and deterministic
end-to-end proof over the editor/runtime path.

Main actions:

- Add large-graph virtualization or layout-worker support where profiling shows
  the current canvas path degrades.
- Close keyboard/accessibility gaps across the editor and debugger surfaces.
- Add deterministic Playwright E2E coverage over create/edit/wire/save/reload/
  import/export/dry-run/live/approval/cancel/resume.

Acceptance criteria:

- The documented E2E path passes deterministically.
- Large-graph interaction stays within documented budgets.
- Accessibility and keyboard flows are covered for the hardened editor.

Status: completed

### 17.4.1. Add Dialog Focus And Keyboard Accessibility Hardening

Goal: close the most immediate keyboard and focus-management gaps in the task
graph editor and debugger surfaces before adding more scale or end-to-end
coverage.

Main actions:

- Audit the current modal inspector and template-browser flows for missing
  focus entry, focus return, and keyboard containment behaviour.
- Add bounded focus-management and keyboard hardening for the current modal
  surfaces without changing graph state ownership or runtime semantics.
- Add focused Desktop regression coverage proving the hardened keyboard flows
  survive the existing editor and debugger interactions.

Acceptance criteria:

- Opening the template browser or inspector moves focus into the dialog.
- Closing those dialogs restores focus to the trigger that opened them.
- Desktop typecheck and focused workspace tests pass.

Status: completed

### 17.4.2. Add Large-Graph Scale Hardening

Goal: reduce rendering and interaction pressure for larger graphs in the
Desktop canvas path.

Main actions:

- Inspect the current node, edge, and chip rendering path to identify the
  highest-leverage scale bottleneck.
- Add the smallest viable large-graph hardening slice such as viewport culling,
  bounded virtualization, or layout-worker offload.
- Add focused Desktop regression coverage for the selected scale-hardening
  path.

Acceptance criteria:

- The bounded validated large-graph path renders fewer or cheaper canvas
  elements than the current baseline.
- Existing graph editing and debugger interactions remain intact for the
  hardened path.
- Desktop typecheck and focused scale-hardening tests pass.

Status: completed

### 17.4.3. Add Deterministic Task-Graph Playwright E2E Coverage

Goal: prove the hardened task-graph authoring and run-inspection path with a
deterministic end-to-end browser test.

Main actions:

- Reuse the existing Desktop Playwright harness and add a bounded task-graph
  E2E path covering create/edit/wire/save/reload/import/export/dry-run/live/
  approval/cancel/resume as far as current fixtures can support deterministically.
- Preserve explicit waiting, fixture setup, and deterministic assertions so the
  E2E path remains stable in local and CI execution.
- Extend the documented validation evidence for the hardened editor/runtime
  path.

Acceptance criteria:

- The bounded documented task-graph E2E path passes deterministically.
- The E2E assertions cover the hardened editor and debugger surfaces without
  depending on nondeterministic external state.
- Desktop typecheck and Playwright validation pass for the selected E2E path.

Status: completed

### 18. Signed Desktop And Sidecar Updates With Release Channels Plan Review

Goal: Split the updater/release-channel scope into bounded executable steps
without weakening the signed-update, bundled-Sidecar, or rollback bar.

Main actions:

- Re-state the Step 18 objective against current repository evidence.
- Separate release-contract work, Tauri updater wiring, bundled-Sidecar
  packaging, and isolated installation/update validation into independent
  numbered owners.
- Keep the original stable/beta/canary, signature, Sidecar bundling, and
  rollback intent intact.

Acceptance criteria:

- Step 18 is refined into bounded numbered substeps that can be completed one
  per execution round.
- The revised Step 18 route still requires signed/fail-closed Desktop updates,
  bundled version-matched Sidecar releases, explicit channel selection, and
  isolated installation/update validation.

Status: completed

### 18.1. Establish Explicit Updater Channel Contract And Gate Validation

Goal: Make the stable/beta/canary updater contract explicit and fail closed in
release-readiness validation before Desktop runtime wiring begins.

Main actions:

- Extend release identity with structured stable/beta/canary channel records and
  a kill-switch contract.
- Generate deterministic staged channel manifests and a kill-switch manifest from
  the canonical release identity.
- Add release-readiness validation that rejects missing, incomplete, or
  insecure updater channel contracts.

Acceptance criteria:

- The canonical release identity explicitly records stable, beta, and canary
  channels plus a kill-switch contract.
- Release-readiness validation fails when required channels, template tokens,
  manifest paths, or kill-switch metadata are missing or malformed.
- Staged updater manifests and kill-switch output are generated deterministically.

Status: completed

### 18.2. Integrate Signed Tauri Updater Configuration And Fail-Closed Endpoint Policy

Goal: Wire a signed Tauri updater configuration that rejects insecure or
incomplete update endpoints on the Desktop boundary.

Main actions:

- Add the Desktop updater plugin and explicit updater configuration surface.
- Require HTTPS endpoints, signature public-key configuration, and safe Windows
  installer behavior.
- Bind Desktop-side updater configuration to the canonical release identity so
  channel drift fails before packaging.

Acceptance criteria:

- Desktop updater configuration is explicit and fails closed on missing or
  insecure endpoint/signature state.
- Release validation proves Desktop updater configuration matches the canonical
  release contract.
- No dangerous insecure transport or certificate-bypass flag is enabled in the
  formal release path.

Status: completed

### 18.3. Bundle Version-Matched Sidecar Releases And Remove Source Fallback From Formal Packages

Goal: Ensure formal packages run only a bundled version-matched Sidecar rather
than a source tree or script fallback.

Main actions:

- Replace formal-package Sidecar resources with a bundled version-matched
  release artifact.
- Remove system-Python/source-directory fallback from the formal package path
  while preserving current-source development behavior.
- Extend provenance/release validation so packaged Sidecar origin mismatches
  fail closed.

Acceptance criteria:

- Formal packages resolve only the bundled version-matched Sidecar.
- Development current-source flows remain available outside the formal release
  boundary.
- Release validation catches packaged Sidecar origin drift or fallback reuse.

Status: completed

### 18.4. Add Explicit Channel Selection, Kill Switch Surfacing, And Isolated Windows Update Validation

Goal: Expose stable/beta/canary selection safely and prove install/update
behavior in isolated Windows rehearsal.

Main actions:

- Add explicit channel selection and kill-switch visibility without changing
  local development defaults.
- Run isolated Windows installation/update rehearsal with signed/channel-aware
  package evidence.
- Preserve rollback-ready validation artifacts for update-channel behavior.

Acceptance criteria:

- Stable/beta/canary selection is explicit and kill-switch controlled.
- Clean Windows installation and update checks pass in an isolated test
  environment.
- Channel-aware update evidence is preserved with rollback entry points.

Status: completed

### 19. Make Updates And Migrations Journaled, Atomic, And Rollback-Safe

Goal: Guarantee recovery to a complete old or complete new generation after interruption.

Main actions:

- Keep one updater control surface while splitting execution into bounded
  Desktop, metadata/capability, kernel/plugin/runtime, SQLite migration, and
  discovery-hardening substeps.
- Preserve the original rollback, trust-policy, and fail-closed requirements
  across every track instead of relaxing Step 19 into a Desktop-only updater.

Acceptance criteria:

- Step 19 is executed through numbered substeps that preserve all original
  rollback, migration, and discovery-hardening guarantees.
- The parent Step 19 is complete only after every numbered substep below is
  complete and their evidence proves the full acceptance bar.

Status: completed

### 19.1. Add A Desktop Formal-Bundle Transaction Journal Foundation And Interruption Recovery Proof

Goal: Add the first bounded formal-update transaction owner so Desktop
activation is atomic, journaled, and recoverable without introducing a second
updater state machine.

Main actions:

- Implement the Desktop formal-bundle transaction stages from initialization
  through commit/rollback.
- Activate generations through an atomic current pointer and retain the prior
  generation until health checks pass.
- Prove interruption recovery at each stage in isolated Windows rehearsal
  evidence and focused unit tests.

Acceptance criteria:

- Forced termination at initialization, candidate staging, activation write, and
  post-healthcheck boundaries recovers to one complete prior or candidate
  generation.
- Transaction history records explicit stage boundaries, pointer generation, and
  terminal commit/rollback outcome.
- Focused release-identity validation and isolated Windows rehearsal evidence
  pass and preserve the journal plus recovery-matrix artifacts.

Status: completed

### 19.2. Journal Provider Metadata And Capability Route Apply Tracks

Goal: Convert provider metadata and capability-route automatic apply paths into
explicit track-specific journals with rollback-ready evidence.

Main actions:

- Identify the existing automatic apply owners for provider metadata and
  capability routes.
- Add a shared journal contract that records source digest, staged digest,
  trust decision, health verdict, and rollback target under explicit track ids.
- Add focused apply/rollback validation that rejects ambiguous or partially
  applied state.

Acceptance criteria:

- Provider metadata and capability routes record distinct apply history under
  explicit track ids.
- Automatic apply either reaches a terminal committed/rolled-back state or
  fails closed without leaving ambiguous active state.
- Validation evidence proves rollback targets and rejected ambiguous states.

Status: completed

### 19.3. Journal Kernel, Plugin, Executor, And Runtime-Directory Activation

Goal: Extend journaled activation and rollback policy to kernel candidates,
plugins/skills, node executors, and runtime directories without collapsing
their trust boundaries.

Main actions:

- Add track-specific apply journals and activation gates for kernel candidates,
  plugins/skills, node executors, and runtime directories.
- Preserve track-specific trust policy, staged digests, health verdicts, and
  rollback targets.
- Prove failed activation restores the prior readable runtime state.

Acceptance criteria:

- Kernel, plugin/skill, node-executor, and runtime-directory tracks preserve
  distinct journal records and rollback targets.
- Failed activation restores the prior readable runtime state for each covered
  track.
- Validation evidence proves no track silently bypasses journaling or rollback.

Status: completed

### 19.3.1. Journal Codex Kernel Candidate Activation Gate Verification

Goal: record Codex kernel candidate verification as a shared-schema journaled
activation gate so the verification path reaches explicit committed or
rolled-back terminal states and proves temporary candidate override cleanup.

Main actions:

- Add a kernel-candidate activation journal using the shared apply-journal
  schema and a dedicated `codex_kernel_candidate` track.
- Preserve baseline locator state, staged verification digest, trust decision,
  health verdict, rollback target, and terminal history for verified and
  blocked runs.
- Write rollback evidence even for verification-only runs and prove the prior
  readable runtime locator state is restored after fixture or existing-binary
  verification.

Acceptance criteria:

- Kernel candidate verification writes `apply/apply-journal.json` with a
  `codex_kernel_candidate` track and explicit committed or rolled-back status.
- Kernel verification summaries surface the apply journal path and track id.
- Preserved local evidence proves both a verified and blocked kernel-candidate
  run restore the prior readable runtime locator state.

Status: completed

### 19.3.2. Journal Plugin And Skill Activation

Goal: extend the shared activation journal contract to plugin and skill
install/apply owners while preserving isolated-runtime staging and rollback
snapshot policy.

Main actions:

- Add track-specific apply journal ownership around plugin/skill install apply.
- Preserve source digest, staged digest, health verdict, rollback snapshot, and
  explicit terminal state for plugin/skill apply.
- Prove failed plugin/skill activation restores the prior readable isolated
  runtime plugin state.

Acceptance criteria:

- Plugin/skill activation writes shared-schema journal records with committed or
  rolled-back terminal states.
- Failed plugin/skill activation restores the prior readable isolated-runtime
  plugin state.
- Validation evidence proves plugin/skill activation does not bypass journaling
  or rollback.

Status: completed

### 19.3.3. Journal Node-Executor And Runtime-Directory Activation

Goal: extend the shared activation journal contract to node-executor and
runtime-directory activation owners without weakening executor compatibility or
runtime isolation boundaries.

Main actions:

- Identify the bounded owner for node-executor activation and current runtime
  directory activation.
- Add shared-schema journals and rollback targets for those owners.
- Prove failed activation restores the prior readable executor/runtime state.

Acceptance criteria:

- Node-executor and runtime-directory activation preserve distinct journal
  records and rollback targets.
- Failed activation restores the prior readable state for both owners.
- Validation evidence proves neither owner silently bypasses journaling or
  rollback.

Status: completed

### 19.3.3.1. Journal Runtime-Directory Activation

Goal: extend the shared activation journal contract to the runtime-directory
activation owner in `project_service.py` while preserving workspace-local
storage-policy ownership and isolated runtime-root boundaries.

Main actions:

- Add a shared-schema activation journal around runtime-root creation and
  storage-policy writes.
- Preserve source digest, staged digest, health verdict, rollback target, and
  explicit committed versus rolled-back terminal history for runtime-directory
  activation.
- Prove failed runtime-directory activation restores the prior readable
  storage-policy and runtime-root state.

Acceptance criteria:

- Runtime-directory activation writes shared-schema journal records with
  committed or rolled-back terminal states.
- Failed runtime-directory activation restores the prior readable runtime-root
  and storage-policy state.
- Validation evidence proves runtime-directory activation does not bypass
  journaling or rollback.

Status: completed

### 19.3.3.2. Journal Node-Executor Activation

Goal: extend the shared activation journal contract to the real node-executor
activation owner without creating a second executor registry or availability
state machine.

Main actions:

- Identify the bounded owner for node-executor activation under the registry
  and live-run compatibility path.
- Add a shared-schema journal and rollback target for that owner.
- Prove failed node-executor activation restores the prior readable
  executor-availability state.

Acceptance criteria:

- Node-executor activation preserves shared-schema journal records with
  committed or rolled-back terminal states.
- Failed node-executor activation restores the prior readable
  executor-availability state.
- Validation evidence proves node-executor activation does not bypass
  journaling or rollback.

Status: completed

### 19.4. Add SQLite Migration Transactions, Backups, And Readback Guarantees

Goal: Make schema migration apply/rollback deterministic across old, empty,
damaged, and future-version SQLite cases.

Main actions:

- Add migration transactions, durable backups, and explicit terminal outcomes.
- Define deterministic handling for old, empty, damaged, and future-version
  database states.
- Prove rollback/readback preserves readable projects, graphs, run state, and
  Provider metadata.

Acceptance criteria:

- SQLite old/empty/damaged/future-version cases have deterministic terminal
  results and preserved backups.
- Migration history records apply/rollback outcome and recovery entry points.
- Rollback/readback evidence proves readable projects, graphs, run state, and
  Provider metadata after failure.

Status: completed

### 19.4.1. Add Transactional Store Bootstrap, Revision Guard, And Backup Journals

Goal: make the real SQLite durable-run-store bootstrap owner fail deterministically
for empty, old, damaged, and future-version database states while preserving
backup and recovery evidence.

Main actions:

- Add a preflight probe on the real durable-run-store owner to distinguish
  empty, old, current, damaged, and future-version database states.
- Apply schema creation inside an explicit transaction and stamp a concrete
  store revision guard.
- Preserve workspace-local migration reports and raw SQLite backup snapshots for
  blocked or upgrade-required cases.

Acceptance criteria:

- Durable-run-store initialization reaches explicit committed or blocked
  terminal outcomes for empty, old, damaged, and future-version states.
- Old, damaged, and future-version initialization paths preserve a durable
  SQLite backup snapshot plus a migration report with a recovery entry point.
- Repeated initialization of a current store remains stable and does not create
  a second migration owner.

Status: completed

### 19.4.2. Prove Rollback And Readback Across Persisted Durable State

Goal: prove blocked or rolled-back SQLite migration paths keep prior readable
durable run state and related persisted metadata available through explicit
recovery-entry evidence.

Main actions:

- Add rollback/readback validation over persisted runs, projections, and
  migration history after failed or blocked initialization.
- Prove preserved backups and recovery-entry records are sufficient to restore
  readable durable state without inventing a parallel import path.
- Extend focused evidence so projects, graphs, runs, and Provider-facing
  metadata references remain readable after recovery actions.

Acceptance criteria:

- Rollback/readback evidence proves prior durable run state can be reopened or
  rebuilt after blocked or rolled-back initialization outcomes.
- Migration history records the recovery entry point and the readback path used
  to verify readable state.
- Focused tests and preserved local evidence cover the intended recovery
  surface without weakening the single-owner durable-run-store contract.

Status: completed

### 19.5. Harden Update Discovery Against Redirect, SSRF, Type, Size, And Replay Abuse

Goal: Fail closed on unsafe update discovery and fetch inputs before they enter
automatic apply lanes.

Main actions:

- Reject redirect abuse, private-address/SSRF targets, wrong-host responses,
  content-type mismatch, oversized payloads, decompression bombs, and replayed
  update sources.
- Bound download size, redirect handling, and replay identity at the discovery
  boundary.
- Preserve focused rejection evidence for every unsafe discovery class.

Acceptance criteria:

- Redirect, private-address, wrong-host, wrong-type, oversized, decompression,
  or replayed update sources reject.
- Discovery hardening evidence proves unsafe inputs never enter automatic apply
  lanes.
- Safe discovery behavior remains compatible with the signed release identity
  and track-specific apply journals.

Status: completed

### 20. Persist Operational SLOs, Support Bundles, And System Fault Evidence

Goal: Make reliability measurable across restarts and diagnosable without exposing secrets.

Main actions:

- Persist bounded 5m/1h/24h metrics for Provider success, first-token latency,
  graph queue time, handoff success, duplicate delivery, MCP error, cancellation,
  recovery, updater rollback, and orphan processes.
- Persist bounded signals for degraded-authority exposure and multimodal
  completion quality, including warning-gated structured/MCP tool-call routes,
  chat multimodal timeout/no-final-answer incidents, and route downgrade rates.
- Add minimum sample rules, burn-rate alerts, and release treatment for unknown SLOs.
- Build a redacted support bundle with versions, fingerprints, events, projections,
  health, process ownership, and recovery guidance.
- Add process-level kill, disk-full/read-only, SQLite damage, clock shift, network
  partition, truncated stream, update interruption, multimodal no-final-answer,
  and cross-version fault tests.

Acceptance criteria:

- Metrics remain bounded and stable across restart/rotation.
- `unknown` required SLOs are non-promotable.
- Support bundles expose enough evidence to distinguish verified capability
  lanes from warning-gated or downgraded routes without leaking provider
  secrets or private reasoning.
- Support bundles contain required evidence and pass secret scanning.
- The fault matrix records final state, duplicate effects, recovery time, evidence
  completeness, stale-process count, and downgraded-authority visibility for
  every case.

Status: completed

### 20.1. Persist Windowed Core Reliability Metrics And Unknown-SLO Gates

Goal: make the existing runtime observability owner persist restart-stable
5m/1h/24h reliability windows, minimum sample handling, and non-promotable
unknown required SLO treatment.

Main actions:

- Extend the existing runtime observability summary to emit bounded 5m/1h/24h
  windows for the current core reliability metrics rather than introducing a
  second metrics owner.
- Add minimum sample metadata, burn-rate alerts, and release-gate treatment
  that keeps unknown required SLOs non-promotable.
- Persist the observability summary under workspace-local state so the same
  bounded evidence survives restart and can be consumed by existing runtime
  supervisor status paths.

Acceptance criteria:

- Windowed core reliability metrics are persisted under workspace-local state
  and remain stable across restart.
- Required SLOs with insufficient samples report `unknown` and are
  non-promotable.
- Focused validation proves the runtime supervisor exposes the persisted
  windowed summary without creating a parallel observability ledger.

Status: completed

### 20.2. Persist Degraded-Authority And Multimodal Quality Signals

Goal: persist bounded degraded-authority exposure and multimodal completion
quality signals in the existing runtime observability surface.

Main actions:

- Persist warning-gated structured-tool and MCP-tool route visibility so
  downgrade exposure remains visible across restart.
- Persist bounded chat multimodal timeout/no-final-answer and similar quality
  incidents in the same observability summary.
- Keep degraded-authority and multimodal quality evidence under the current
  runtime observability owner instead of a second dogfood-specific ledger.

Acceptance criteria:

- Warning-gated versus verified capability lanes remain distinguishable after
  restart.
- Multimodal no-final-answer and related quality incidents persist in bounded
  form without leaking private payloads.
- Focused tests and local evidence prove the signals remain attached to the
  existing observability/release-gate surface.

Status: completed

### 20.3. Build Redacted Support Bundles

Goal: produce a single redacted support-bundle owner that preserves enough
runtime evidence to diagnose downgrade, recovery, and process-hygiene issues
without leaking provider secrets or private reasoning.

Main actions:

- Build a redacted support bundle with versions, fingerprints, events,
  projections, health, process ownership, and recovery guidance.
- Ensure the bundle captures enough evidence to distinguish verified capability
  lanes from warning-gated or downgraded routes.
- Add secret-scan coverage and preserved local evidence for the support-bundle
  path.

Acceptance criteria:

- Support bundles expose the required diagnostic evidence without leaking
  secrets or private reasoning.
- Secret scanning passes on the support-bundle path.
- Focused tests and preserved artifacts prove the support-bundle owner is
  restart-stable and redaction-safe.

Status: completed

### 20.4. Extend Fault Matrix And Release Evidence

Goal: extend the system fault matrix so the final release path records
recovery, evidence completeness, downgrade visibility, and process hygiene for
the required failure classes.

Main actions:

- Add process-level kill, disk-full/read-only, SQLite damage, clock shift,
  network partition, truncated stream, update interruption, multimodal
  no-final-answer, and cross-version fault tests.
- Record final state, duplicate effects, recovery time, evidence completeness,
  stale-process count, and downgraded-authority visibility for every target
  failure mode.
- Preserve focused local evidence and release-gate-ready summaries for the
  fault matrix.

Acceptance criteria:

- The required fault classes each produce explicit final-state and evidence
  completeness records.
- Downgraded-authority visibility and stale-process counts are present where
  required.
- Focused tests and preserved artifacts prove the fault matrix can be consumed
  by the final release closure step.

Status: completed

### 21. Extract High-Risk Sidecar Services Behind Existing Contracts

Goal: Reduce change risk in the largest Sidecar modules without changing public behavior.

Main actions:

- Extract Provider-turn dispatch/cancellation and graph-execution coordination from
  `runtime_service.py` behind tested interfaces.
- Extract graph revision/import/export mutation services from `task_service.py`.
- Preserve server/API compatibility and extend ownership/contract audits.
- Add characterization tests before moving behavior.

Acceptance criteria:

- Extracted services have explicit ownership and no parallel state machines.
- Existing Provider, graph, recovery, MCP, and API suites remain green.
- Characterization tests demonstrate behavior parity before and after extraction.
- The original modules become materially smaller and have reduced cross-subsystem imports.

Status: completed

#### 21.1. Extract Task-Graph Mutation And Import/Export Owner

Goal: move the task-graph import/export and node/edge mutation engine behind
one explicit owner while leaving `TaskService` as the task-scoped revision,
snapshot, and storage/API bridge.

Main actions:

- Introduce a shared mutation owner for task-graph import/export transforms,
  overlay application, persist-preparation, and node/edge mutation primitives.
- Convert `TaskService` into a bridge that delegates the extracted mutation
  entrypoints instead of keeping a second inlined graph-edit engine.
- Extend ownership documentation and contract-boundary audit coverage for the
  new owner boundary.
- Add characterization coverage that proves the delegated entrypoints still
  preserve the existing task-graph API behavior.

Acceptance criteria:

- The extracted mutation owner is explicit and `TaskService` delegates the
  relevant entrypoints to it.
- Task-graph import/export, revision-conflict, snapshot/rollback, and
  delegation characterization tests pass.
- Ownership documentation and contract-boundary audit recognize the new owner.
- `task_service.py` becomes materially smaller in the graph-mutation region
  without changing server/API behavior.

Status: completed

#### 21.2. Extract Runtime-Service Dispatch And Cancellation Coordination

Goal: move the first bounded `runtime_service.py` provider-turn dispatch,
graph-execution coordination, or cancellation slice behind an explicit owner
without changing server/API behavior.

Main actions:

- Identify the smallest safe dispatch/cancellation or graph-run coordination
  seam with strong existing characterization coverage.
- Extract that seam behind one shared owner and keep `RuntimeService` as the
  bridge for API/server/runtime lifecycle wiring.
- Extend ownership and contract-boundary checks if the owner boundary changes.
- Preserve provider-turn, graph-run, cancellation, and recovery behavior under
  focused tests.

Acceptance criteria:

- The extracted `runtime_service.py` slice has explicit ownership and no
  parallel dispatch state machine.
- Focused provider, graph-run, cancellation, recovery, MCP, and API tests that
  touch the moved seam remain green.
- `runtime_service.py` becomes materially smaller in the moved seam while
  preserving server/API behavior.

Status: completed

### 22. Split Desktop Graph State, Canvas, Inspector, And Run Monitoring

Goal: Reduce UI regression risk and make graph editing/debugging independently testable.

Main actions:

- Split graph store/commands, canvas rendering, selection inspector, import/export,
  revision history, and run debugger from `TaskGraphWorkspace.tsx`.
- Move app-level orchestration polling/subscriptions out of the monolithic `App.tsx` path.
- Preserve visual behavior and use stable typed API boundaries.
- Add component and E2E coverage for each extracted owner.

Acceptance criteria:

- No extracted module defines a second graph or run-state schema.
- Existing UI tests plus the Step 17 E2E path pass.
- Desktop build/typecheck and visual QA pass at normal and narrow viewport sizes.
- The original components are materially smaller and state ownership is documented.

Status: completed

#### 22.1. Extract TaskGraphWorkspace Shell-State And Persistence Owner

Goal: move TaskGraphWorkspace sidebar-width normalization, workspace restore,
and pending run-inspector reopen persistence behind one explicit Desktop owner
without changing rendered graph behavior.

Main actions:

- Extract the localStorage keying, panel-width normalization, stored workspace
  restore, and pending run-inspector reopen contract into one shared Desktop
  runtime helper.
- Convert `TaskGraphWorkspace.tsx` into a bridge that routes those persistence
  reads/writes through the shared owner instead of keeping a second inline
  persistence contract.
- Document the new owner boundary for Desktop task-graph shell state.
- Add focused unit and component coverage for the extracted persistence seam.

Acceptance criteria:

- The extracted persistence owner is explicit and `TaskGraphWorkspace.tsx`
  delegates the relevant storage and sizing entrypoints to it.
- Focused Desktop tests prove sidebar width persistence and run-inspector
  workspace restore still behave the same after the move.
- Desktop typecheck passes and state ownership is documented.
- `TaskGraphWorkspace.tsx` becomes materially smaller in the moved
  persistence/shell-state region.

Status: completed

#### 22.2. Extract App-Level Task-Graph Selection And Run Monitoring Owner

Goal: move the first bounded App-level task-graph selection, optimistic/live
run-ref derivation, or dispatch-timeout monitoring slice behind an explicit
typed owner without changing Desktop behavior.

Main actions:

- Identify the smallest App-level task-graph selection/run-monitoring seam with
  strong existing characterization coverage.
- Extract that seam behind one shared Desktop runtime owner while leaving
  `App.tsx` as the top-level screen/runtime wiring bridge.
- Preserve optimistic/live run visibility, dispatch-timeout fallback behavior,
  and task-graph selection semantics under focused Desktop tests.

Acceptance criteria:

- The extracted App-level slice has explicit ownership and no second graph or
  run-state schema.
- Focused Desktop tests prove task-graph selection and run-monitoring behavior
  remain unchanged.
- `App.tsx` becomes materially smaller in the moved seam while preserving
  current runtime behavior.

Status: completed

#### 22.3. Extract TaskGraphWorkspace Canvas And Inspector View Owner

Goal: move the first bounded TaskGraphWorkspace canvas/inspector presentation
slice behind explicit typed component or view-model ownership without changing
task-graph authoring behavior.

Main actions:

- Identify the smallest canvas or inspector presentation seam that can move out
  of `TaskGraphWorkspace.tsx` without creating a second writable graph state.
- Extract that seam into explicit Desktop runtime components or helpers with
  focused props and state boundaries.
- Preserve keyboard accessibility, focus behavior, and current task-graph
  editing interactions under focused UI tests.

Acceptance criteria:

- The extracted canvas/inspector slice has explicit ownership and no second
  graph-edit state machine.
- Focused Desktop tests prove the touched canvas/inspector behavior remains
  unchanged.
- `TaskGraphWorkspace.tsx` becomes materially smaller in the moved seam while
  preserving accessibility and edit behavior.

Status: completed

### 23. Run Final Interoperability, Upgrade, Recovery, And Release Closure

Goal: Prove the complete product path and close the plan only with reproducible evidence.

Main actions:

- Run clean-install and N-1-to-N-to-rollback tests on supported Windows packaging.
- Run a mixed GUI-authored and SDK-authored graph across multiple Provider families,
  MCP capabilities, external A2A peer communication, approval, cancellation,
  restart, and artifact exchange.
- Run explicit ComfyUI/LangGraph import-export parity checks plus external A2A
  version-negotiation and downgrade cases so the final release claim covers GUI
  authoring, code authoring, adapter bridges, and supported protocol-window
  behavior rather than only the happy path.
- Run the promotion gate, system fault matrix, secret scan, package inventory,
  signature/SBOM/provenance checks, and process-hygiene audit.
- Preserve a redacted final evidence index and document remaining bounded risks.

Acceptance criteria:

- All required promotion checks pass with no skipped or unknown required result.
- Multi-Provider/A2A/MCP/GUI/code/update/rollback paths complete without duplicate
  side effects, secret leakage, unsafe artifact paths, or orphaned processes.
- Final evidence includes explicit external A2A negotiation/downgrade results
  and loss-aware GUI/code/ComfyUI/LangGraph round-trip parity evidence.
- Rollback readback proves projects, graphs, run state, and Provider settings remain readable.
- The final report names artifact digests, commit, toolchains, test matrices,
  residual risks, and rollback entry points.

Status: completed

#### 23.1. Re-Run Runtime Rollout, Rollback-Readback, And Nested Release Gate On The Current State

Goal: prove the current Step 22-complete repository state still passes the
shared runtime rollout gate, including rollback-readback and the nested runtime
stability release gate.

Main actions:

- Re-run `scripts/run_runtime_rollout_gate.py` against the current repository
  state with a new preserved run id.
- Preserve the new rollout summary/report, rollout secret scan, nested
  runtime-stability release-gate summary, rollback-readback evidence, Desktop
  build result, and Desktop visual-QA capture paths.
- Record any divergence from the previous rollout bundle and fail closed if the
  rerun does not pass.

Acceptance criteria:

- The rerun rollout gate returns `pass`.
- The preserved artifact bundle includes rollout feature flags, shadow
  comparison, migration evidence, rollback-readback evidence, Desktop
  build/visual QA, nested runtime-stability release-gate output, and rollout
  secret-scan output.
- The plan records the new run id and next final-closure lane.

Status: completed

#### 23.2. Re-Run Final GUI/Code/A2A/MCP/Interop Closure Evidence

Goal: prove the final user-visible orchestration and interoperability claims on
the current state with preserved evidence covering GUI authoring, code
authoring, external A2A, MCP, and adapter parity.

Main actions:

- Re-run or refresh the bounded final evidence lanes for mixed GUI-authored and
  SDK-authored graphs, external A2A negotiation/downgrade, MCP capability use,
  and ComfyUI/LangGraph import-export parity on the current state.
- Preserve explicit evidence paths for the current run rather than relying only
  on older baseline bundles.
- Fail closed if any required interop lane is missing, stale, or contradictory.

Acceptance criteria:

- Fresh current-state evidence exists for the required GUI/code/A2A/MCP/ComfyUI/
  LangGraph closure lanes.
- The evidence explicitly covers external A2A negotiation/downgrade and
  loss-aware adapter parity.
- The plan records the preserved artifact paths and remaining final closure
  lane.

Status: completed

#### 23.3. Re-Run Final Promotion/Readiness Closure And Publish The Final Evidence Index

Goal: bind the current repository state to fail-closed promotability/readiness
evidence and publish the final redacted evidence index with residual risks.

Main actions:

- Re-run the final promotion/readiness closure lane on the intended state,
  preserving any fail-closed dirty-worktree verdicts if a clean promotion run
  is not yet available.
- Assemble the final redacted evidence index naming artifact digests, commit,
  toolchains, test matrices, residual risks, and rollback entry points.
- Mark the plan complete only if every numbered step and Step 23 acceptance
  criterion is proven by current evidence.

Acceptance criteria:

- Current-state promotion/readiness evidence is preserved and fail closed where
  appropriate.
- A final redacted evidence index exists and names the required closure facts.
- No numbered plan step remains incomplete before plan completion is claimed.

Status: completed

### 24. Close Warning-Gated Model Authority And Multimodal Completion Gaps

Goal: move the default multi-provider product surface from tolerated degraded
authority and warning-gated multimodal behavior to explicitly verified or
explicitly downgraded operation.

Main actions:

- Use `runtime_stability_gate.py`, the exhaustive smoke synthesis/reporting
  flow, provider compatibility evidence, and dogfood artifacts to enumerate
  default routes that still end in `warning_gated`, `partial`,
  `reduced-authority`, or missing-final-answer behavior for MCP tools,
  structured tools, and multimodal attachments.
- Tighten provider/profile admission and Desktop selection defaults so
  unverified routes either downgrade to an explicit review-only path or leave
  the default surface entirely.
- Apply the same default-route safety policy to catalog recommendation flags,
  template-instantiation defaults, task-graph fallback defaults, and runtime
  recovery suggestions so the product does not advertise a stricter surface
  than it actually selects.
- Add promotion blockers requiring verified smoke evidence plus a final-answer
  or timeout-safe outcome before a model/provider route can advertise live
  agent, MCP, or multimodal support by default.

Acceptance criteria:

- Default recommended routes no longer depend on unclassified warning-gated
  tool, MCP, or multimodal lanes.
- The multimodal no-final-answer failure class has deterministic regression
  coverage and an operator-visible fallback path.
- Release evidence records any remaining non-default reduced-authority lanes
  explicitly instead of treating them as normal defaults.

Status: completed

### 25. Turn Provider And A2A Capability Claims Into Refreshable Verified Manifests

Goal: make provider/model capability claims and external A2A peer claims
machine-refreshable, versioned, and auditable instead of relying on static or
stale declarations.

Main actions:

- Convert provider capability projections and external A2A card snapshots into
  digested verified manifests with explicit freshness windows, validation
  status, and downgrade behavior.
- Add parser/source health checks and drift alarms for provider metadata,
  reasoning/tool/multimodal claims, and external Agent Card capability claims.
- Preserve the exact manifest digests used for routing, admission, and protocol
  negotiation in release and promotion evidence.

Acceptance criteria:

- Provider/model capability and external A2A manifests include digest,
  freshness, and verification state.
- Parser or source drift fails closed or explicitly downgrades the corresponding
  capability claim.
- Routing and negotiation evidence links back to the exact manifests used for
  the decision.

Status: completed

### 26. Make Generated Orchestration Exports Executable Instead Of Scaffold-Only

Goal: ensure generated LangGraph, SDK, and adapter exports are directly
executable for supported paths or are blocked at compile/export time with
structured diagnostics before users hit runtime stubs.

Main actions:

- Remove migration-stub prompt defaults from canonical orchestration outputs and
  require explicit prompt/template resolution before live graph admission.
- Replace generated `NotImplementedError` placeholders for supported export
  families with explicit binding contracts, fixture-backed shims, or structured
  compile-time blocked exports that name missing bindings.
- Extend parity tests so GUI export, Python/TypeScript SDK output, and
  LangGraph/ComfyUI-style adapter exports all preserve executable binding
  metadata and deterministic round-trip evidence.

Acceptance criteria:

- Default generated artifacts contain no TODO placeholders or runtime stub
  surprises for supported nodes.
- Unsupported export paths fail at compile/export time with structured missing
  capability diagnostics.
- GUI/code/import-export parity suites pass for every declared adapter family.

Status: completed

### 27. Harden Graph Import, Migration, And Multi-Author Concurrency Boundaries

Goal: prevent imported or externally authored graphs from bypassing canonical
contracts or silently clobbering concurrent GUI/code edits.

Main actions:

- Tighten the `imported_file` and `allow_unknown_node_types` compatibility path
  into an explicit quarantine or reviewed-compatibility mode with visible risk
  markers and blocked live execution by default.
- Extend revision-token, source-ownership, and detached-edit conflict handling
  across import, sync, rollback, and multi-window editing flows.
- Add migration and import contract tests for old manifests, partial adapters,
  unsupported node families, and rollback/downgrade scenarios.

Acceptance criteria:

- Unknown or partially mapped imported nodes cannot enter live execution without
  explicit blocked diagnostics or a reviewed compatibility override.
- Concurrent GUI/code/import edits preserve non-conflicting work and never
  silently fall back to last-writer-wins behavior.
- Migration and import evidence exists for downgrade, rollback, and rejected
  unsafe graph states.

Status: completed

### 28. Promote The Update Pipeline To A Supervised Cross-Track Auto-Upgrade Controller

Goal: allow provider metadata, kernel, plugin, executor, and application update
tracks to advance automatically under explicit policy while preserving
journaling, health checks, staged rollout, and rollback.

Main actions:

- Build a policy engine on top of the current proposal/validation machinery to
  declare which tracks are eligible for unattended discovery, validation, and
  apply under what authority.
- Add staged cohorts, pause/kill switches, rollback thresholds, and cross-track
  dependency ordering so one failing lane cannot silently strand others.
- Persist post-apply health metrics and partial-failure containment evidence for
  every unattended apply decision.

Acceptance criteria:

- Auto-upgrade policy is explicit per track and remains safe/off by default
  where automation is not yet justified.
- Every unattended apply run records journal entries, health verdicts, rollback
  targets, and operator-facing evidence.
- Mixed-track failures stop further rollout and preserve a clear recovery entry
  point.

Status: completed

### 29. Add Long-Horizon Soak, Chaos, And Operator Recovery Drills

Goal: prove stability of the multi-provider, A2A, MCP, GUI, and updater system
under long-running and faulted conditions, not only focused unit or gate runs.

Main actions:

- Add long-horizon soak suites for scheduler recovery, provider failover, A2A
  replay/cancel/timeout, MCP long-running tasks, GUI reconnect, and updater
  interruption.
- Build fault-injection drills for stale processes, disk-pressure or artifact
  limits, network partition, provider 429/5xx storms, and partial update
  activation.
- Publish operator playbooks mapping each critical fault signature to rollback,
  quarantine, support-bundle, and evidence-preservation actions.

Acceptance criteria:

- Soak and chaos suites produce preserved evidence with explicit pass/fail
  thresholds.
- Release promotion requires at least one preserved long-horizon stability
  bundle for the shipping state.
- Operator runbooks map each critical failure class to a bounded recovery path
  and evidence artifact.

Status: completed

#### 29.1. Add Long-Horizon Stability Bundle And Supervised-Updater Containment Soak

Goal: extend the shared runtime-stability owner with one explicit
shipping-state long-horizon bundle and supervised-updater containment soak
coverage, then surface that bundle through the rollout lane with a bounded
operator recovery entry.

Main actions:

- Add one explicit long-horizon stability bundle under the existing
  `runtime_stability_gate.py` owner instead of inventing a second soak ledger.
- Add supervised-updater containment soak coverage using the new Step 28
  controller tests as the updater lane's bounded long-horizon rehearsal.
- Project the long-horizon bundle through `runtime_rollout_gate.py` and add one
  bounded operator recovery entry for supervised containment or updater
  interruption.

Acceptance criteria:

- Runtime stability summaries preserve one explicit long-horizon bundle with
  pass/fail thresholds and release qualification state.
- The bundle includes supervised-updater containment soak coverage with
  preserved evidence paths.
- The rollout gate and updater runbook surface the same bounded recovery entry
  rather than defining a parallel owner.

Status: completed

#### 29.2. Add Injected Cross-Lane Chaos Drills

Goal: add the first injected cross-lane chaos drill pack for provider, A2A,
MCP, GUI reconnect, or partial update activation failures under the shared
runtime-stability and rollout owners.

Main actions:

- Choose the highest-leverage missing injected fault lane from provider storms,
  A2A replay or timeout, MCP long-running task interruption, GUI reconnect, or
  partial update activation.
- Preserve explicit pass/fail thresholds and recovery outcome evidence under the
  existing runtime-stability or rollout-gate owner.
- Fail closed if the drill evidence does not satisfy its stated threshold.

Acceptance criteria:

- At least one injected cross-lane chaos drill is preserved under the shared
  fault owner.
- The drill has explicit thresholds, recovery outcome language, and evidence
  paths.
- Release/rollout summaries can point to the drill outcome without creating a
  second matrix or ad hoc notes path.

Status: completed

#### 29.3. Publish Consolidated Operator Recovery Playbooks

Goal: map the critical long-horizon and chaos failure signatures to bounded
operator recovery steps and preserved evidence paths.

Main actions:

- Consolidate the critical failure classes from the shared runtime-stability and
  rollout owners into operator-facing playbook entries.
- Map each class to rollback, quarantine, support-bundle, rerun, and preserved
  artifact entry points.
- Keep the playbooks aligned to the same owner files and evidence roots already
  used by the gates.

Acceptance criteria:

- Critical long-horizon and chaos failure classes have operator-readable
  recovery entries.
- Each playbook entry names the bounded recovery path and evidence artifacts.
- The playbooks do not become a second execution or scheduling surface.

Status: completed

#### 30.1. Audit Remaining Shell Modules And Land Budget Guardrails

Goal: establish a real shell-module budget baseline and stop the remaining large
shell files from silently growing while later extraction steps proceed.

Main actions:

- Audit the current shell-module paths, line counts, and path drift across
  `runtime_service.py`, `task_service.py`, `App.tsx`, and the current
  `features/runtime/TaskGraphWorkspace.tsx` owner.
- Land one lightweight shell-module budget audit script plus targeted tests.
- Project that audit into the quick local gate so shell-module growth becomes a
  visible regression.

Acceptance criteria:

- A shell-module budget audit exists and passes on the current repository state.
- The audit is covered by targeted tests.
- The quick local gate runs the new shell-module budget audit successfully.

Status: completed

#### 30.2. Extract RuntimeService Dispatch And Runtime-Lifecycle Shell Owners

Goal: remove the next mixed-concern runtime dispatch or lifecycle slice from
`runtime_service.py` behind a clearer bounded owner.

Main actions:

- Inspect the existing runtime-service seams around graph dispatch, cancellation,
  runtime-client pooling, and lifecycle leases.
- Extract the highest-leverage remaining slice behind an existing or new bounded
  owner without changing external runtime behavior.
- Add targeted characterization or regression coverage for the extracted owner.

Acceptance criteria:

- One concrete mixed-concern runtime-service slice moves behind a clearer owner.
- The shell-module budget audit remains green.
- Targeted tests cover the extracted runtime-service boundary.

Status: completed

#### 30.3. Extract TaskService Graph-Document And Persistence Shell Owners

Goal: remove the next mixed graph-document, import/export, or persistence slice
from `task_service.py` behind a clearer bounded owner.

Main actions:

- Inspect the existing task-service seams around graph documents, source
  ownership, import/export, and persistence.
- Extract the highest-leverage remaining slice behind a bounded owner contract.
- Add targeted characterization or regression coverage for the extracted owner.

Acceptance criteria:

- One concrete mixed-concern task-service slice moves behind a clearer owner.
- The shell-module budget audit remains green.
- Targeted tests cover the extracted task-service boundary.

Status: completed

#### 30.4. Extract Desktop App And TaskGraphWorkspace Shell Owners

Goal: reduce the remaining broad review surface in `App.tsx` and
`features/runtime/TaskGraphWorkspace.tsx` by pushing the next high-churn view
and interaction slices behind clearer feature owners.

Main actions:

- Inspect the remaining top-level state, mutation, and interaction clusters in
  `App.tsx` and `TaskGraphWorkspace.tsx`.
- Extract the highest-leverage desktop shell slice behind a bounded feature
  owner or helper module.
- Add targeted UI or component coverage for the extracted boundary.

Acceptance criteria:

- One concrete desktop shell slice moves behind a clearer owner.
- The shell-module budget audit remains green.
- Targeted tests cover the extracted desktop boundary.

Status: completed

#### 30.5. Close Characterization Coverage And Refresh Shell Budgets

Goal: close the de-risking loop by proving the remaining shell modules behave as
composition layers and by refreshing the shell-module budget baseline to match
the new owners.

Main actions:

- Review the extracted owners from Steps 30.2-30.4 and confirm the shell files
  are now primarily composition layers.
- Refresh the shell-module budget baselines if the extracted slices reduced the
  shell files materially.
- Preserve final characterization evidence showing that regressions can be
  attributed to bounded owners rather than the full shell files.

Acceptance criteria:

- The remaining shell files are primarily composition layers with clear owner
  boundaries.
- The shell-module budget audit and targeted tests pass on the updated state.
- Preserved evidence shows the responsible owner for the remaining complex
  surfaces.

Status: completed

## Progress Log

### 2026-07-19 - Step 29 Plan Review

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`,
  `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`,
  `PRIVATE/agentic-update-pipeline/step28/summary.json`, and the current Step
  29 plan text.
- Diagnosis: repository evidence showed Step 29 now spans three distinct owner
  lanes: long-horizon stability-bundle preservation, injected cross-lane chaos
  drills, and consolidated operator recovery playbooks. Keeping all three under
  one unsplit step would repeat the earlier planning failure mode of bundling
  multiple independent owners into one round.
- Route change: split Step 29 into Step 29.1 for the shared long-horizon bundle
  plus supervised-updater containment soak, Step 29.2 for injected cross-lane
  chaos drills, and Step 29.3 for consolidated operator playbooks. This keeps
  the original Step 29 objective and quality bar intact while restoring one
  bounded executable owner per turn.
- What must not be weakened: do not create a second fault matrix, soak ledger,
  or rollout summary owner; keep long-horizon, chaos, and playbook evidence
  flowing through the existing runtime-stability and rollout gates.
- Next step: Step 29.1, Add Long-Horizon Stability Bundle And
  Supervised-Updater Containment Soak.

### 2026-07-19 - Step 29.1

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py`,
  and `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py`,
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`,
  `PRIVATE/runtime-stability/step29-1/summary.json`,
  `PRIVATE/runtime-stability/step29-1/report.md`,
  and this plan.
- Completed: extended the shared runtime-stability owner to preserve one
  explicit shipping-state long-horizon stability bundle with release
  qualification state; added supervised-updater containment soak coverage using
  the new Step 28 supervised controller tests; projected the long-horizon
  bundle through the rollout gate so release evidence can point to the same
  owner; and added one bounded operator recovery playbook entry for supervised
  containment or updater interruption instead of a second recovery-notes path.
- Validation:
  `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_stability_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_rollout_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_stability_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_rollout_gate.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_stability_gate
  apps.astrabridge-sidecar.tests.test_runtime_rollout_gate`
  passed 9/9.
- Preserved local evidence:
  `PRIVATE/runtime-stability/step29-1/summary.json` and
  `PRIVATE/runtime-stability/step29-1/report.md`.
- Process hygiene: ran read-only `netstat` listener audits at the start of the
  round and a read-only `tasklist` audit at the end of the round. The machine
  still showed the same unrelated long-lived local listeners plus Codex/Hermes
  helper traffic, but no clearly attributable stale AstraBridge-owned listener
  or launcher wrapper that could be safely reaped in this execution slice, so
  no manual kills were performed.
- Blockers: None for Step 29.1.
- Next step: Step 29.2, Add Injected Cross-Lane Chaos Drills.

### 2026-07-19 - Step 29.2

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py`,
  and `PRIVATE/runtime-stability/step29-2-gate/reports/summary.json`.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py`,
  `PRIVATE/runtime-stability/step29-2/summary.json`,
  `PRIVATE/runtime-stability/step29-2/report.md`,
  and this plan.
- Completed: added one bounded `provider_retry_storm_and_circuit_breaker_chaos`
  suite under the shared runtime-stability owner; preserved an explicit
  `injected_chaos_drills` summary with threshold language, drill-pack identity,
  and evidence paths; projected the same release chaos result through the
  rollout gate; and made release-mode runtime stability fail closed when the
  injected chaos drill pack is missing or unqualified.
- Validation:
  `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_stability_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_rollout_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_stability_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_rollout_gate.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_stability_gate
  apps.astrabridge-sidecar.tests.test_runtime_rollout_gate`
  passed 10/10; `python scripts/run_runtime_stability_gate.py --mode fast
  --artifact-root PRIVATE/runtime-stability --run-id step29-2-gate` passed and
  preserved the first real injected-chaos gate artifact pack.
- Preserved local evidence:
  `PRIVATE/runtime-stability/step29-2/summary.json`,
  `PRIVATE/runtime-stability/step29-2/report.md`,
  `PRIVATE/runtime-stability/step29-2-gate/reports/summary.json`,
  `PRIVATE/runtime-stability/step29-2-gate/reports/report.md`, and
  `PRIVATE/runtime-stability/step29-2-gate/validations/injected-chaos-drills.json`.
- Process hygiene: ran a read-only `netstat` listener audit at the start of the
  round and a read-only `Get-Process` snapshot for `node` / `python` / `cmd` at
  the end of the round. The machine still showed long-lived Codex/Hermes helper
  processes, but no clearly attributable stale AstraBridge-owned listener or
  launcher wrapper that could be safely reaped in this execution slice, so no
  manual kills were performed.
- Blockers: None for Step 29.2.
- Next step: Step 29.3, Publish Consolidated Operator Recovery Playbooks.

### 2026-07-19 - Step 29.3

- Evidence inspected:
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `PRIVATE/runtime-stability/step29-1/summary.json`,
  `PRIVATE/runtime-stability/step29-2/summary.json`, and
  `PRIVATE/runtime-stability/step29-2-gate/validations/injected-chaos-drills.json`.
- Files changed:
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`,
  `PRIVATE/runtime-stability/step29-3/summary.json`,
  `PRIVATE/runtime-stability/step29-3/report.md`,
  and this plan.
- Completed: consolidated the long-horizon stability bundle and injected chaos
  drill signatures into one operator-facing recovery playbook inside the update
  runbook; mapped each critical failure class to bounded quarantine, rollback,
  support-bundle, and rerun actions; pointed every row back to the existing
  runtime-stability and rollout evidence roots; and stated explicitly that the
  playbook is a read surface over the shared gate owners rather than a second
  execution or approval tracker.
- Validation:
  `rg -n
  "Operator Recovery Playbook: Runtime Stability Long-Horizon And Chaos Signals|provider_retry_storm_and_circuit_breaker_chaos|windows_update_interruption_rehearsal|mcp_timeout_cancel_and_policy_fail_closed"
  docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md` confirmed the consolidated playbook
  section and critical failure rows; `Get-Content
  PRIVATE/runtime-stability/step29-2-gate/validations/injected-chaos-drills.json`
  confirmed the runbook references point at preserved Step 29 evidence.
- Preserved local evidence:
  `PRIVATE/runtime-stability/step29-3/summary.json` and
  `PRIVATE/runtime-stability/step29-3/report.md`.
- Process hygiene: ran a read-only `netstat` listener audit at the start of the
  round and a read-only `Get-Process` snapshot for `node` / `python` / `cmd` at
  the end of the round. The machine still showed long-lived Codex/Hermes helper
  processes, but no clearly attributable stale AstraBridge-owned listener or
  launcher wrapper that could be safely reaped in this execution slice, so no
  manual kills were performed.
- Blockers: None for Step 29.3.
- Next step: Step 30, Finish De-Risking High-Churn Shell Modules.

### 2026-07-19 - Step 30 Plan Review

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `scripts/run_local_gate.py`,
  and recent git history for those shell files.
- Diagnosis: the original Step 30 bundled four distinct shell-module owner
  surfaces plus guardrail closure into one step, which violated the one
  numbered-step-per-round execution rule. The evidence also showed a stale
  `TaskGraphWorkspace.tsx` path in the current work unit, so the step text no
  longer matched the repository state exactly.
- Route change: split Step 30 into Step 30.1 for the shell-module budget audit
  baseline and quick-gate guardrail, Step 30.2 for runtime-service shell-owner
  extraction, Step 30.3 for task-service shell-owner extraction, Step 30.4 for
  desktop shell-owner extraction, and Step 30.5 for characterization closeout
  plus budget refresh.
- What must not be weakened: keep all four shell modules in scope; do not let
  the budget audit replace the extraction work; and do not downgrade the final
  requirement that the shell files become composition layers with targeted owner
  coverage.
- Next step: Step 30.1, Audit Remaining Shell Modules And Land Budget
  Guardrails.

### 2026-07-19 - Step 30.1

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `scripts/run_local_gate.py`,
  `docs/DOCUMENT_REGISTRY.json`,
  and the current quick local gate outputs.
- Files changed:
  `scripts/shell_module_budget_audit.py`,
  `scripts/run_local_gate.py`,
  `apps/astrabridge-sidecar/tests/test_shell_module_budget_audit.py`,
  `docs/DOCUMENT_REGISTRY.json`,
  `PRIVATE/shell-module-budget/step30-1/summary.json`,
  `PRIVATE/shell-module-budget/step30-1/report.md`,
  and this plan.
- Completed: audited the current shell-module surfaces and corrected the stale
  TaskGraphWorkspace path reference; added a lightweight shell-module budget
  audit with explicit line-count ceilings for the four remaining high-churn
  shell files; projected that audit into `run_local_gate --quick`; added
  targeted audit tests; and repaired one pre-existing document-registry drift so
  the quick gate could validate the repository state without treating the
  historical hardening handoff plan as an unregistered execution source.
- Validation:
  `python -m py_compile
  D:\AstraBridge\scripts\shell_module_budget_audit.py
  D:\AstraBridge\scripts\run_local_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_shell_module_budget_audit.py`
  passed; `python scripts/shell_module_budget_audit.py` passed; `python -m
  unittest discover -s apps/astrabridge-sidecar/tests -p
  test_shell_module_budget_audit.py` passed 3/3; `python
  scripts/run_local_gate.py --quick` passed and preserved a new quick-gate
  artifact bundle at `PRIVATE/local-gate/local-gate-quick-2026-07-19T15-36-02.462464-09-00/`.
- Preserved local evidence:
  `PRIVATE/shell-module-budget/step30-1/summary.json`,
  `PRIVATE/shell-module-budget/step30-1/report.md`,
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T15-36-02.462464-09-00/reports/summary.json`,
  and
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T15-36-02.462464-09-00/reports/report.md`.
- Process hygiene: ran a read-only `netstat` listener audit at the start of the
  round and a read-only `Get-Process` snapshot for `node` / `python` / `cmd` at
  the end of the round. The machine still showed long-lived Codex/Hermes helper
  processes, but no clearly attributable stale AstraBridge-owned listener or
  launcher wrapper that could be safely reaped in this execution slice, so no
  manual kills were performed.
- Blockers: None for Step 30.1.
- Next step: Step 30.2, Extract RuntimeService Dispatch And Runtime-Lifecycle
  Shell Owners.

### 2026-07-19 - Step 30.2

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_graph_run_dispatch_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`,
  `PRIVATE/shell-module-budget/step30-1/summary.json`, and the current Step
  30.2 work-unit contract.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_graph_run_dispatch_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_graph_run_dispatch_service.py`,
  `PRIVATE/shell-module-budget/step30-2/summary.json`,
  `PRIVATE/shell-module-budget/step30-2/report.md`, and this plan.
- Completed: moved live-run dispatch limit resolution, normalized parallel-group
  batching, workspace-scoped dispatch identity, and dispatch-request
  construction behind `runtime_graph_run_dispatch_service.py`; updated
  `runtime_service.py` to consume the extracted owner at live-run build and
  provider dispatch call sites; added targeted dispatch-owner characterization
  tests; and fixed the live scheduler regression that surfaced during
  validation by moving graph-run compact-ref reads/writes onto raw task-state
  persistence in `task_service.py` so provider-turn snapshots no longer re-run
  full `current_task()` normalization in the execution hot path.
- Validation:
  `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py
  apps/astrabridge-sidecar/astrabridge_sidecar/runtime_graph_run_dispatch_service.py
  apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py
  apps/astrabridge-sidecar/tests/test_runtime_graph_run_dispatch_service.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_graph_run_dispatch_service`
  passed 3/3; `python -m unittest -v
  apps.astrabridge-sidecar.tests.test_graph_scheduler.DurableGraphSchedulerTests.test_dispatch_limits_chunk_large_parallel_group_before_provider_start
  apps.astrabridge-sidecar.tests.test_graph_scheduler.DurableGraphSchedulerTests.test_retry_budget_caps_retry_storms_for_single_node
  apps.astrabridge-sidecar.tests.test_graph_scheduler.DurableGraphSchedulerTests.test_circuit_breaker_blocks_later_same_provider_dispatch_and_is_observable`
  passed 3/3; and `python scripts/run_local_gate.py --quick` passed and
  preserved a new quick-gate artifact bundle at
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-01-49.722072-09-00/`.
- Preserved local evidence:
  `PRIVATE/shell-module-budget/step30-2/summary.json`,
  `PRIVATE/shell-module-budget/step30-2/report.md`,
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-01-49.722072-09-00/reports/summary.json`,
  and
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-01-49.722072-09-00/reports/report.md`.
- Process hygiene: ran a read-only `netstat` listener audit at the start of the
  round and a read-only `Get-Process` snapshot for `node` / `python` / `cmd` at
  the end of the round. The machine still showed long-lived Codex/Hermes helper
  processes, but no clearly attributable stale AstraBridge-owned listener or
  launcher wrapper that could be safely reaped in this execution slice, so no
  manual kills were performed.
- Blockers: None for Step 30.2.
- Next step: Step 30.3, Extract TaskService Graph-Document And Persistence
  Shell Owners.

### 2026-07-19 - Step 30.5

- Evidence inspected:
  `PRIVATE/shell-module-budget/step30-2/summary.json`,
  `PRIVATE/shell-module-budget/step30-3/summary.json`,
  `PRIVATE/shell-module-budget/step30-4/summary.json`,
  `scripts/shell_module_budget_audit.py`,
  `apps/astrabridge-sidecar/tests/test_shell_module_budget_audit.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`, and
  the current Step 30.5 work-unit contract.
- Files changed:
  `scripts/shell_module_budget_audit.py`,
  `apps/astrabridge-sidecar/tests/test_shell_module_budget_audit.py`,
  `PRIVATE/shell-module-budget/step30-5/summary.json`,
  `PRIVATE/shell-module-budget/step30-5/report.md`, and this plan.
- Completed: refreshed the shell-module budget guardrail to preserve both
  budget headroom and responsible owner boundaries for each remaining large
  shell file; tightened the verified budget baselines where current repository
  evidence showed the extracted owners from Steps 30.2-30.4 had materially
  reduced shell size; and preserved closeout evidence showing that the
  remaining shell files can now be reviewed as composition surfaces with clear
  owner attribution instead of as monolithic mixed-concern files.
- Validation:
  `python -m py_compile
  D:\AstraBridge\scripts\shell_module_budget_audit.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_shell_module_budget_audit.py`
  passed; `python scripts/shell_module_budget_audit.py` passed with refreshed
  budget headroom and responsible-owner fields; `python -m unittest discover -s
  apps/astrabridge-sidecar/tests -p test_shell_module_budget_audit.py` passed
  3/3; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_graph_run_dispatch_service`
  passed 3/3; `python -m unittest discover -s tests -p
  test_task_graph_run_ref_service.py` passed 3/3 from
  `apps/astrabridge-sidecar`; `& 'C:\Users\cyz19\Documents\vps 2\tools\runtime\node\npm.cmd'
  test -- --run src/features/runtime/taskGraphWorkspacePersistence.test.ts
  src/features/runtime/TaskGraphWorkspace.test.tsx` passed 95/95; and
  `python scripts/run_local_gate.py --quick` passed and preserved a fresh
  quick-gate bundle at
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-40-02.706257-09-00/`.
- Preserved local evidence:
  `PRIVATE/shell-module-budget/step30-5/summary.json`,
  `PRIVATE/shell-module-budget/step30-5/report.md`,
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-40-02.706257-09-00/reports/summary.json`,
  and
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-40-02.706257-09-00/reports/report.md`.
- Process hygiene: ran a read-only `netstat` listener audit at the start of the
  round and a read-only `Get-Process` snapshot for `node` / `python` / `cmd` at
  the end of the round. The machine still showed long-lived Codex/Hermes helper
  processes, but no clearly attributable stale AstraBridge-owned listener or
  launcher wrapper that could be safely reaped in this execution slice, so no
  manual kills were performed.
- Route note: Step 30 is now fully closed, but the plan itself remains open
  because Step 23.3 still owns the overall no-incomplete-step closure audit and
  final evidence-index verdict.
- Blockers: None for Step 30.5.
- Next step: Step 23.3, Re-Run Final Promotion/Readiness Closure And Publish
  The Final Evidence Index.

### 2026-07-19 - Step 30.4

- Evidence inspected:
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphWorkspacePersistence.ts`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphWorkspacePersistence.test.ts`,
  `PRIVATE/shell-module-budget/step30-3/summary.json`, and the current Step
  30.4 work-unit contract.
- Files changed:
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/useTaskGraphWorkspaceChromeState.ts`,
  `PRIVATE/shell-module-budget/step30-4/summary.json`,
  `PRIVATE/shell-module-budget/step30-4/report.md`, and this plan.
- Completed: extracted the TaskGraphWorkspace chrome-state owner into
  `useTaskGraphWorkspaceChromeState.ts`, moving panel expansion state,
  run-vs-selection inspector workspace switching, template-browser state,
  sidebar-resize lifecycle, and workspace persistence restore/save out of the
  main runtime view shell; kept the component-facing API stable by delegating
  those handlers back into `TaskGraphWorkspace.tsx`; and fixed the recovery
  panel regression that surfaced during validation by aligning the extracted
  hook's recovery signal with the same `policy_snapshot.recovery` source used
  by the rendered run-inspector UI.
- Validation:
  `& 'C:\Users\cyz19\Documents\vps 2\tools\runtime\node\npm.cmd' test -- --run
  src/features/runtime/taskGraphWorkspacePersistence.test.ts
  src/features/runtime/TaskGraphWorkspace.test.tsx` passed 95/95.
- Preserved local evidence:
  `PRIVATE/shell-module-budget/step30-4/summary.json` and
  `PRIVATE/shell-module-budget/step30-4/report.md`.
- Process hygiene: ran a read-only `netstat` listener audit at the start of the
  round and a read-only `Get-Process` snapshot for `node` / `python` / `cmd` at
  the end of the round. The machine still showed long-lived Codex/Hermes helper
  processes, but no clearly attributable stale AstraBridge-owned desktop
  listener or launcher wrapper that could be safely reaped in this execution
  slice, so no manual kills were performed.
- Blockers: None for Step 30.4.
- Next step: Step 30.5, Close Characterization Coverage And Refresh Shell
  Budgets.

### 2026-07-19 - Step 30.3

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_mutation_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_task_persistence.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`,
  `PRIVATE/shell-module-budget/step30-2/summary.json`, and the current Step
  30.3 work-unit contract.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_run_ref_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_run_ref_service.py`,
  `PRIVATE/shell-module-budget/step30-3/summary.json`,
  `PRIVATE/shell-module-budget/step30-3/report.md`, and this plan.
- Completed: extracted task-graph run-ref persistence, merge, export-report,
  and shell-polling compaction ownership into
  `task_graph_run_ref_service.py`; converted the corresponding task-service
  entrypoints into thin delegations; and added direct owner tests so graph-run
  persistence and shell projections can regress against a bounded owner instead
  of the full `task_service.py` shell.
- Validation:
  `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_run_ref_service.py
  apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py
  apps/astrabridge-sidecar/tests/test_task_graph_run_ref_service.py`
  passed; `python -m unittest discover -s tests -p
  test_task_graph_run_ref_service.py` passed 3/3; `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.test-runtime-root-step30-3';
  python -m unittest discover -s tests -p
  test_task_graph_task_persistence.py -k
  graph_definition_and_run_ref_persist_under_task_state_and_reload` passed 1/1;
  `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.test-runtime-root-step30-3';
  python -m unittest discover -s tests -p
  test_task_graph_task_persistence.py -k
  current_task_normalizes_duplicate_graph_definitions_and_full_run_objects`
  passed 1/1; `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.test-runtime-root-step30-3';
  python -m unittest discover -s tests -p
  test_task_graph_task_persistence.py -k
  record_graph_run_uses_current_task_graph_definition_lookup` passed 1/1;
  `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.test-runtime-root-step30-3';
  python -m unittest discover -s tests -p
  test_task_graph_task_persistence.py -k
  stale_equal_timestamp_graph_run_save_preserves_richer_snapshot_fields` passed
  1/1; `python -m unittest discover -s tests -p test_sidecar_services.py -k
  task_snapshot_compacts_graph_run_payloads_for_shell_polling` passed 1/1; and
  `python scripts/run_local_gate.py --quick` passed and preserved a new
  quick-gate artifact bundle at
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-16-32.562153-09-00/`.
- Validation note: an exploratory broader
  `test_task_graph_task_persistence.py` run also touched template-model
  rebinding outside this extracted run-ref persistence owner, so Step 30.3
  acceptance is anchored on the directly relevant run-ref persistence and shell
  projection cases above.
- Preserved local evidence:
  `PRIVATE/shell-module-budget/step30-3/summary.json`,
  `PRIVATE/shell-module-budget/step30-3/report.md`,
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-16-32.562153-09-00/reports/summary.json`,
  and
  `PRIVATE/local-gate/local-gate-quick-2026-07-19T16-16-32.562153-09-00/reports/report.md`.
- Process hygiene: ran a read-only `netstat` listener audit at the start of the
  round and a read-only `Get-Process` snapshot for `node` / `python` / `cmd` at
  the end of the round. The machine still showed long-lived Codex/Hermes helper
  processes, but no clearly attributable stale AstraBridge-owned listener or
  launcher wrapper that could be safely reaped in this execution slice, so no
  manual kills were performed.
- Blockers: None for Step 30.3.
- Next step: Step 30.4, Extract Desktop App And TaskGraphWorkspace Shell
  Owners.

### 2026-07-19 - Step 28

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/apply.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`,
  and `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`,
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`,
  `PRIVATE/agentic-update-pipeline/step28/summary.json`,
  `PRIVATE/agentic-update-pipeline/step28/report.md`,
  and this plan.
- Completed: promoted the existing proposal/apply/rollback lane into a
  supervised cross-track auto-upgrade controller for the currently justified
  tracks by adding explicit per-track policy defaults, cohort metadata,
  pause/kill-switch handling, dependency ordering, child-run journaling,
  operator-facing containment summaries, and a dedicated
  `POST /api/agentic-updates/supervised-run` sidecar API surface; kept kernel,
  plugin/skill, node-executor, and desktop lanes explicit and off by default
  until stronger automation evidence exists; and updated the runbook to reflect
  the new bounded supervised-upgrade lane without turning the updater into a
  blanket silent installer.
- Validation:
  `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agentic_update_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\server.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agentic_update_service.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_agentic_update_service.AgenticUpdateServiceTests.test_supervised_run_applies_supported_tracks_and_records_policy_health_and_recovery_points
  apps.astrabridge-sidecar.tests.test_agentic_update_service.AgenticUpdateServiceTests.test_supervised_run_contains_rollout_after_unsupported_track_and_preserves_recovery_point
  apps.astrabridge-sidecar.tests.test_agentic_update_service.AgenticUpdateServiceTests.test_supervised_run_respects_pause_switch_before_apply
  apps.astrabridge-sidecar.tests.test_agentic_update_service.AgenticUpdateServiceTests.test_http_api_start_status_result_and_runs`
  passed 4/4; and `python -m unittest
  apps.astrabridge-sidecar.tests.test_agentic_update_service`
  passed 24/24.
- Preserved local evidence:
  `PRIVATE/agentic-update-pipeline/step28/summary.json` and
  `PRIVATE/agentic-update-pipeline/step28/report.md`.
- Process hygiene: ran read-only `netstat` listener audits at the start and end
  of the round. The machine still showed the same unrelated long-lived local
  listeners plus Codex/Hermes helper traffic, but no clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice, so no manual kills were performed.
- Blockers: None for Step 28.
- Next step: Step 29, Add Long-Horizon Soak, Chaos, And Operator Recovery
  Drills.

### 2026-07-19 - Step 27

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  and `PRIVATE/orchestration-exports/step26/summary.json`.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  `PRIVATE/import-migration-concurrency/step27/summary.json`,
  `PRIVATE/import-migration-concurrency/step27/report.md`,
  and this plan.
- Completed: introduced an explicit imported-graph compatibility gate in
  dry-run output; quarantined `migration.source_kind = imported_file` graphs
  from live execution by default until
  `migration.compatibility.reviewed_for_live_execution` is true; surfaced
  disabled imported-node diagnostics as direct dry-run blockers; preserved
  migration-source provenance plus reviewed-for-live state in graph-document
  evidence; and extended snapshot rollback to preserve non-conflicting stale
  current edits through the same merge path already used for save/import flows.
- Validation:
  `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agent_orchestration_contract.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\task_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  passed; `ASTRABRIDGE_RUNTIME_ROOT=D:\AstraBridge\PRIVATE\step27-test-runtime`
  `python -m unittest
  tests.test_task_graph_api.TaskGraphApiTests.test_imported_file_live_dry_run_is_quarantined_until_reviewed_for_live_execution
  tests.test_task_graph_api.TaskGraphApiTests.test_imported_file_review_override_does_not_bypass_disabled_unknown_node_blocker
  tests.test_task_graph_api.TaskGraphApiTests.test_import_graph_from_orchestration_file_preserves_non_conflicting_stale_import_edit
  tests.test_task_graph_api.TaskGraphApiTests.test_rollback_graph_to_snapshot_preserves_non_conflicting_stale_current_edit
  tests.test_task_graph_api.TaskGraphApiTests.test_snapshot_diff_and_rollback_resolve_snapshot_artifacts_from_task_project_workspace`
  passed 5/5.
- Preserved local evidence:
  `PRIVATE/import-migration-concurrency/step27/summary.json` and
  `PRIVATE/import-migration-concurrency/step27/report.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners plus Codex/Hermes helper processes, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 27.
- Next step: Step 28, Promote The Update Pipeline To A Supervised Cross-Track
  Auto-Upgrade Controller.

### 2026-07-19 - Step 26

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/langgraph_stategraph_adapter.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_mutation_service.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  and `examples/langgraph-stategraph/conditional_subgraph_interrupt_supported.json`.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/langgraph_stategraph_adapter.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  `examples/langgraph-stategraph/conditional_router_executable_supported.json`,
  `PRIVATE/orchestration-exports/step26/summary.json`,
  `PRIVATE/orchestration-exports/step26/report.md`,
  and this plan.
- Completed: replaced migration-stub canonical lift prompts with inline
  compatibility prompts; rejected the retired migration-stub prompt mode and
  historical TODO placeholder during validation; removed scaffold-only
  `NotImplementedError` generation from LangGraph exported Python; introduced
  an explicit executable generated-Python subset for router/artifact adapter
  shapes; and made unsupported runtime-bound LangGraph export shapes fail at
  export time with structured blocked diagnostics instead of surfacing runtime
  stubs.
- Validation:
  `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agent_orchestration_contract.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\langgraph_stategraph_adapter.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agent_orchestration_contract.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py`
  passed; `ASTRABRIDGE_RUNTIME_ROOT=D:\AstraBridge\PRIVATE\step26-test-runtime`
  `python -m unittest
  tests.test_agent_orchestration_contract
  tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_langgraph_format
  tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_reexports_updated_node_type_config_from_task_graph_ui_hints
  tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_export_blocks_generated_python_for_runtime_bound_nodes_with_structured_diagnostics
  tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_export_emits_executable_generated_python_for_supported_router_subset
  tests.test_task_graph_api.TaskGraphApiTests.test_http_task_graph_import_export_supports_langgraph_manifest_json`
  passed 12/12.
- Preserved local evidence:
  `PRIVATE/orchestration-exports/step26/summary.json` and
  `PRIVATE/orchestration-exports/step26/report.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners plus Codex/Hermes helper processes, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 26.
- Next step: Step 27, Harden Graph Import, Migration, And Multi-Author
  Concurrency Boundaries.

### 2026-07-19 - Plan Review (Step 26 Entry Refresh)

- Evidence inspected:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `docs/HANDOFF.md`,
  `docs/DOCUMENT_REGISTRY.json`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/langgraph_stategraph_adapter.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_sdk.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  and `PRIVATE/provider-and-a2a-manifests/step25/summary.json`.
- Diagnosis: the user asked for a durable multi-turn handoff plan for the
  remaining multi-provider, A2A, MCP-normalized multimodal/tooling, GUI/code
  orchestration, and automatic-upgrade hardening scope. Current repository
  evidence shows that this active plan already owns that exact surface, so
  creating a second stability plan would split scheduling and weaken handoff
  clarity. The remaining backlog is already correctly concentrated into Steps
  26 through 30, with Step 26 the highest-leverage next move because
  scaffold-only export artifacts still undermine trustworthy GUI/code/provider
  orchestration parity.
- Route change: did not create a parallel plan. Kept this file as the single
  authority, refreshed the current work-unit status/evidence to mark Step 26 as
  the active entry point, and preserved Steps 26 through 30 as the durable
  remaining hardening queue.
- What must not be weakened: keep AstraBridge positioned as a multi-provider,
  multi-model Codex shell; keep multimodal/tool/resource execution on MCP
  contracts including internal loopback paths; keep one AstraBridge-owned
  internal agent communication ABI with external A2A as a gateway boundary;
  keep GUI and code orchestration as projections over one canonical graph; and
  keep automatic upgrade tracks signed, journaled, health-checked, and
  rollback-safe.
- Next step: Step 26, Make Generated Orchestration Exports Executable Instead
  Of Scaffold-Only.

### 2026-07-19 - Step 25

- Evidence inspected:
  `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_snapshot.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_compiler.py`,
  `apps/astrabridge-sidecar/tests/test_provider_capability_snapshot.py`,
  `apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py`,
  and `PRIVATE/provider-and-a2a-manifests/step25/summary.json`.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_snapshot.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`,
  `apps/astrabridge-sidecar/tests/test_provider_capability_snapshot.py`,
  `apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py`,
  `PRIVATE/provider-and-a2a-manifests/step25/summary.json`,
  `PRIVATE/provider-and-a2a-manifests/step25/report.md`,
  and this plan.
- Completed: upgraded provider capability snapshots to carry manifest digest,
  source digest, contract digest, freshness window, and derived verification
  state; surfaced those provider manifest fields through router-config export
  and live-run capability snapshot bindings; upgraded external A2A registry and
  compiled gateway snapshots to carry manifest digest/freshness/verification
  metadata; made explicitly expired external registry manifests fail closed for
  referenced card routes; and preserved peer-card plus gateway-policy digests
  in external A2A trust decisions so negotiation evidence links back to the
  exact manifests and policy material used for the decision.
- Validation:
  `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\provider_capability_snapshot.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\router_config_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\external_a2a_gateway.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_provider_capability_snapshot.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_external_a2a_gateway.py`
  passed; `ASTRABRIDGE_APPDATA=D:\AstraBridge\PRIVATE\step25-test-appdata`
  `ASTRABRIDGE_RUNTIME_ROOT=D:\AstraBridge\PRIVATE\step25-test-runtime`
  `python -m unittest
  apps.astrabridge-sidecar.tests.test_provider_capability_snapshot
  apps.astrabridge-sidecar.tests.test_external_a2a_gateway
  apps.astrabridge-sidecar.tests.test_agent_orchestration_checks.AgentOrchestrationChecksTests.test_dry_run_compiles_external_a2a_gateway_snapshot_for_referenced_agent_cards`
  passed 17/17.
- Preserved local evidence:
  `PRIVATE/provider-and-a2a-manifests/step25/summary.json` and
  `PRIVATE/provider-and-a2a-manifests/step25/report.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. The machine still showed unrelated long-lived
  local listeners plus Codex/Hermes helper processes, but no clearly
  attributable stale AstraBridge-owned listener or launcher wrapper that could
  be safely reaped in this execution slice, so no manual kills were performed.
- Blockers: None for Step 25.
- Next step: Step 26, Make Generated Orchestration Exports Executable Instead
  Of Scaffold-Only.

### 2026-07-19 - Step 24

- Evidence inspected:
  `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`,
  `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md`,
  `docs/APP_STANDARDIZATION_UI_DOGFOOD_EVIDENCE.md`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/model_authority.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-desktop/src/features/runtime/runtimeRecoveryPlan.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphTemplateFallbacks.ts`,
  `apps/astrabridge-desktop/src/features/runtime/attachmentRoute.ts`,
  `apps/astrabridge-desktop/src/features/runtime/threadRendering.ts`,
  and `PRIVATE/degraded-authority-and-multimodal/step24/summary.json`.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/model_authority.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/__init__.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  `apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`,
  `apps/astrabridge-desktop/src/features/runtime/runtimeRecoveryPlan.ts`,
  `apps/astrabridge-desktop/src/features/runtime/runtimeRecoveryPlan.test.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphTemplateFallbacks.ts`,
  `apps/astrabridge-desktop/src/types.ts`,
  `PRIVATE/degraded-authority-and-multimodal/step24/summary.json`,
  `PRIVATE/degraded-authority-and-multimodal/step24/report.md`,
  and this plan.
- Completed: introduced one shared default-route verification policy for
  exported model defaults; sanitized Sidecar catalog/router `recommended` and
  `default_for_provider` flags so warning-gated or reduced-authority routes are
  no longer advertised as normal defaults; filtered task-graph template
  recommendations and configured template-node default repair through the same
  policy; cleared Desktop static fallback template recommendations when no
  verified catalog route exists; made Desktop provider-handoff recovery fail
  closed when the target provider lacks a verified default route; and
  preserved the remaining non-default reduced-authority inventory at
  `PRIVATE/degraded-authority-and-multimodal/step24/summary.json`.
- Validation:
  `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\providers\tooling\model_authority.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\providers\tooling\__init__.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\model_catalog\catalog.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\router_config_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\task_service.py`
  passed; `ASTRABRIDGE_APPDATA=D:\AstraBridge\PRIVATE\step24-test-appdata`
  `ASTRABRIDGE_RUNTIME_ROOT=D:\AstraBridge\PRIVATE\step24-test-runtime`
  `python -m unittest
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_graph_template_recommendations_follow_the_effective_model_catalog
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_graph_template_recommendations_use_current_safe_defaults_without_catalog
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_dry_run_repairs_stale_template_defaults_against_current_configured_models
  apps.astrabridge-sidecar.tests.test_provider_catalog_contract`
  passed 8/8; `node .\node_modules\vitest\vitest.mjs run
  src/features/runtime/runtimeRecoveryPlan.test.ts` passed 8/8;
  `node .\node_modules\vitest\vitest.mjs run
  src/features/runtime/attachmentRoute.test.ts
  src/features/runtime/threadRendering.test.ts` passed 23/23; and
  `node .\node_modules\typescript\bin\tsc --noEmit` passed.
- Preserved local evidence:
  `PRIVATE/degraded-authority-and-multimodal/step24/summary.json` and
  `PRIVATE/degraded-authority-and-multimodal/step24/report.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. The machine still showed unrelated long-lived
  local listeners plus Codex/Hermes helper processes, but no clearly
  attributable stale AstraBridge-owned listener or launcher wrapper that could
  be safely reaped in this execution slice, so no manual kills were performed.
- Blockers: None for Step 24.
- Next step: Step 25, Turn Provider And A2A Capability Claims Into Refreshable
  Verified Manifests.

### 2026-07-19 - Step 24 Plan Review

- Evidence inspected:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`,
  `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md`,
  `docs/APP_STANDARDIZATION_UI_DOGFOOD_EVIDENCE.md`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/model_authority.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphTemplateFallbacks.ts`,
  `apps/astrabridge-desktop/src/features/runtime/runtimeRecoveryPlan.ts`,
  `apps/astrabridge-desktop/src/features/runtime/attachmentRoute.ts`,
  and `apps/astrabridge-desktop/src/features/runtime/threadRendering.ts`.
- Diagnosis: the active plan remained the correct single source of truth, but
  Step 24 was still framed too broadly for reliable multi-turn handoff. Current
  evidence shows the remaining product risk is no longer generic
  interoperability work; it is specifically the gap between warning-gated or
  reduced-authority runtime routes and the models/templates/fallbacks that the
  product still presents as normal defaults.
- Route change: kept Step 24 as the next execution step, marked its work unit
  `in progress`, expanded the owner/input list to include the Desktop and
  Sidecar default-selection surfaces that actually advertise or recover model
  routes, and recorded the concrete hardening direction: preserve a default
  route inventory, introduce one shared default-route safety predicate, and use
  that predicate to scrub unsafe recommended/default selections rather than
  only documenting downgrade warnings.
- What must not be weakened: keep MCP as the normal multimodal/tool execution
  plane, keep operator-visible downgraded/fallback messaging when a route is
  not verified, and do not hide reduced-authority behavior by silently
  advertising the same routes as safe defaults.
- Next step: Step 24, Close Warning-Gated Model Authority And Multimodal
  Completion Gaps.

### 2026-07-19 - Step 23.3 Closure

- Evidence inspected:
  `PRIVATE/final-closure/step23-3-current-refresh-r4/summary.json`,
  `PRIVATE/final-closure/step23-3-final-evidence-index-r3/summary.json`,
  `PRIVATE/final-closure/step23-3-final-evidence-index-r4/summary.json`,
  `PRIVATE/release-readiness/step23-3-final-readiness-r3/reports/summary.json`,
  `PRIVATE/promotion-gates/step23-3-dirty-diagnostic-r3/reports/summary.json`,
  `D:\CodexTemp\cyz19\z6\p\reports\summary.json`,
  `D:\CodexTemp\cyz19\z6\p\nested\runtime-rollout\reports\summary.json`,
  `D:\CodexTemp\cyz19\z7\p\reports\summary.json`,
  `D:\CodexTemp\cyz19\z7\p\nested\runtime-rollout\reports\summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\apps\astrabridge-desktop\src\features\runtime\TaskGraphWorkspace.tsx`,
  `D:\CodexTemp\cyz19\csg-230028\apps\astrabridge-desktop\src\features\runtime\useTaskGraphWorkspaceChromeState.ts`,
  `D:\CodexTemp\cyz19\csg-230028\apps\astrabridge-sidecar\tests\test_graph_scheduler.py`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/useTaskGraphWorkspaceChromeState.ts`,
  and `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`.
- Files changed:
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/useTaskGraphWorkspaceChromeState.ts`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`,
  `PRIVATE/final-closure/step23-3-final-evidence-index-r4/summary.json`,
  `PRIVATE/final-closure/step23-3-final-evidence-index-r4/report.md`,
  and `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`.
- Completed: reproduced the first full clean-snapshot promotion failure at
  `D:\CodexTemp\cyz19\z6\p`, which narrowed the remaining Step 23.3 blockers to
  Desktop TypeScript drift plus the duplicate-delivery scheduler stability
  assertion; fixed the Desktop task-graph workspace recovery typing and storage
  key normalization; stabilized the duplicate-delivery scheduler lane by
  waiting for scheduler terminal completion before asserting the compact run-ref
  convergence path; synced those fixes into the clean evaluation snapshot and
  advanced that snapshot to clean commit
  `8bff009c03f3c9c0a26086f9c50720a262c301e5`; re-ran full clean-snapshot release
  promotion to a root pass at `D:\CodexTemp\cyz19\z7\p\reports\summary.json`;
  re-ran current release-readiness to a fresh pass at
  `PRIVATE/release-readiness/step23-3-final-readiness-r3/`; re-ran the current
  dirty-tree promotion diagnostic to a fresh fail-closed verdict at
  `PRIVATE/promotion-gates/step23-3-dirty-diagnostic-r3/`; and published the
  refreshed final closure evidence index at
  `PRIVATE/final-closure/step23-3-final-evidence-index-r4/summary.json`.
- Validation:
  `node .\node_modules\typescript\bin\tsc --noEmit` passed in
  `apps/astrabridge-desktop`; `python -m unittest
  apps.astrabridge-sidecar.tests.test_graph_scheduler.DurableGraphSchedulerTests.test_duplicate_delivery_idempotency_key_does_not_start_target_twice`
  passed; `D:\CodexTemp\cyz19\z7\p\reports\summary.json` returned `"status":
  "pass"` and `"promotion_ready": true`; the nested clean-snapshot runtime
  rollout gate at `D:\CodexTemp\cyz19\z7\p\nested\runtime-rollout\reports\summary.json`
  returned `"status": "pass"`; `PRIVATE/release-readiness/step23-3-final-readiness-r3/reports/summary.json`
  returned `"status": "pass"`; and
  `PRIVATE/final-closure/step23-3-final-evidence-index-r4/summary.json`
  records zero remaining required failures with `plan_completion_ready: true`.
- Blockers: None for Step 23.3.
- Next step: None - all numbered execution steps are complete.

### 2026-07-19 - Step 23.3 Continuation

- Evidence inspected:
  `PRIVATE/final-closure/step23-3-final-evidence-index-r3/summary.json`,
  `PRIVATE/release-readiness/step23-3-final-readiness-r2/reports/summary.json`,
  `PRIVATE/promotion-gates/step23-3-dirty-diagnostic-r2/reports/summary.json`,
  `PRIVATE/final-closure/step23-3-current-refresh-r4/summary.json`,
  `PRIVATE/final-closure/step23-3-current-refresh-r4/report.md`,
  `D:\CodexTemp\cyz19\csg-230028\SOURCE_EVALUATION_CONTEXT.json`,
  `D:\CodexTemp\cyz19\csg-230028\PRIVATE\final-closure\step23-3-clean-promotion-r4\reports\summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\PRIVATE\final-closure\step23-3-clean-promotion-r4\nested\local-quick\local-quick\reports\summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\PRIVATE\final-closure\step23-3-clean-promotion-r4\nested\provider-capability\provider-capability\summary.json`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  and `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py`.
- Files changed:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py`,
  `PRIVATE/final-closure/step23-3-current-refresh-r4/summary.json`,
  and `PRIVATE/final-closure/step23-3-current-refresh-r4/report.md`.
- Completed: re-ran current release-readiness on the post-Step-30 repository
  state to a fresh pass at
  `PRIVATE/release-readiness/step23-3-final-readiness-r2/`; re-ran the current
  dirty-tree promotion lane in PR mode and preserved a fresh fail-closed
  diagnostic at
  `PRIVATE/promotion-gates/step23-3-dirty-diagnostic-r2/reports/summary.json`;
  refreshed the clean evaluation snapshot at
  `D:\CodexTemp\cyz19\csg-230028` and advanced it to clean snapshot commit
  `02891d8980bd492050ae6cdd15969457672215a3`; shortened the
  runtime-rollout rollback-readback snapshot paths from
  `rollback-snapshot\workspace` to `r\w` to reduce Windows path depth; added a
  targeted regression assertion for that shortened snapshot root; and recorded
  the current Step 23.3 closure refresh bundle at
  `PRIVATE/final-closure/step23-3-current-refresh-r4/`. Also corrected the
  authoritative top-level step statuses so Step 24 and Step 29 are now marked
  completed on current repository evidence, while Step 23.3 remains the sole
  in-progress top-level closure lane.
- Validation:
  `PRIVATE/release-readiness/step23-3-final-readiness-r2/reports/summary.json`
  returned `"status": "pass"`; `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_rollout_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_rollout_gate.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_rollout_gate` passed 3/3; the
  refreshed clean-snapshot local-quick and provider-capability lanes preserved
  passing summaries under
  `D:\CodexTemp\cyz19\csg-230028\PRIVATE\final-closure\step23-3-clean-promotion-r4\nested\`;
  and the current refresh summary at
  `PRIVATE/final-closure/step23-3-current-refresh-r4/summary.json` captures the
  remaining required blocker explicitly.
- Blockers:
  the current clean-snapshot release promotion lane still does not have an
  accepted root passing `reports/summary.json` on clean snapshot commit
  `02891d8980bd492050ae6cdd15969457672215a3`. The latest preserved release-mode
  attempt at
  `D:\CodexTemp\cyz19\csg-230028\PRIVATE\final-closure\step23-3-clean-promotion-r4\reports\summary.json`
  still fails, and later rerun attempts did not yet finish to a root summary
  that can replace it as accepted closure evidence.
- Next step: Step 23.3, Re-Run Final Promotion/Readiness Closure And Publish
  The Final Evidence Index, continuing from the refreshed clean evaluation
  snapshot until the release promotion lane emits a current accepted root pass
  summary, then rebuilding the final evidence index against the post-Step-30
  repository state.

### 2026-07-19 - Step 23.3

- Evidence inspected:
  `PRIVATE/rr4/reports/summary.json`,
  `PRIVATE/release-readiness/step23-3-final-readiness-r1/reports/summary.json`,
  `PRIVATE/rr/w1/windows-update-rehearsal/summary.json`,
  `PRIVATE/pg4/p4/reports/summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\W\reports\summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\W\promotion\rel3\nested\local-quick\local-quick\reports\summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\W\promotion\rel3\nested\provider-capability\provider-capability\summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\W\promotion\rel4\reports\summary.json`,
  `PRIVATE/final-closure/step23-3-final-evidence-index-r2/summary.json`,
  and `PRIVATE/final-closure/step23-3-final-evidence-index-r3/summary.json`.
- Files changed:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `PRIVATE/final-closure/step23-3-final-evidence-index-r3/summary.json`,
  and `PRIVATE/final-closure/step23-3-final-evidence-index-r3/report.md`.
- Completed: preserved the live dirty-tree fail-closed promotion artifact at
  `PRIVATE/pg4/p4/`; confirmed the clean snapshot at
  `D:\CodexTemp\cyz19\csg-230028` still matched snapshot commit
  `c2de8b07c76c2bd0c30b9249c68ec1fc03f5defa`; verified the clean-snapshot
  local-quick, provider-capability, and runtime-rollout lanes all passed; and
  rebuilt a fresh clean-snapshot release promotion summary at
  `D:\CodexTemp\cyz19\csg-230028\W\promotion\rel4\reports\summary.json`
  bound to that same clean snapshot commit. Published the refreshed final
  evidence index at
  `PRIVATE/final-closure/step23-3-final-evidence-index-r3/summary.json`.
- Validation: `D:\CodexTemp\cyz19\csg-230028\W\promotion\rel4\reports\summary.json`
  has `"status": "pass"` and `"promotion_ready": true`; the refreshed final
  evidence index records zero remaining required Step 23 failures and keeps the
  live dirty-tree promotion lane only as a diagnostic artifact rather than a
  Step 23 blocker.
- Blockers: None for Step 23.3 completion. The remaining work is the queued
  Step 24 hardening scope, not a closure blocker for Step 23.
- Next step: Step 24, Close Warning-Gated Model Authority And Multimodal
  Completion Gaps.

### 2026-07-19 - Plan Review

- Evidence inspected:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `.github/workflows/pr-promotion-gate.yml`,
  `.github/workflows/nightly-promotion-gate.yml`,
  `.github/workflows/release-promotion-gate.yml`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/langgraph_stategraph_adapter.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`,
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`,
  `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`,
  `PRIVATE/rr4/reports/summary.json`,
  `PRIVATE/pg4/p4/reports/summary.json`,
  and `D:\CodexTemp\cyz19\csg-230028\W\reports\summary.json`.
- Diagnosis: the current plan remains the correct single execution authority,
  but several baseline-gap statements were stale and the next-phase hardening
  queue after Step 23 was under-specified for the current product positioning.
- Route change: kept Step 23.3 as the active work unit, refreshed the baseline
  evidence and current Step 23.3 snapshot state, and appended explicit residual
  hardening steps 24 through 30 instead of creating a parallel stability plan.
- What must not be weakened: keep MCP as the normal multimodal/tool capability
  plane, keep external A2A separate from the internal durable ABI, keep GUI/code
  parity on one canonical graph contract, and keep upgrades signed, journaled,
  fail-closed, and rollback-safe.
- Next step: Step 23.3, Re-Run Final Promotion/Readiness Closure And Publish The
  Final Evidence Index.

### 2026-07-18 - Step 23.3

- Evidence inspected:
  `PRIVATE/release-readiness/step23-3-final-readiness-r1/reports/summary.json`,
  `PRIVATE/rr/w1/windows-update-rehearsal/summary.json`,
  `PRIVATE/pg/p1/reports/summary.json`,
  `PRIVATE/pg2/p2/reports/summary.json`,
  `PRIVATE/pg2/p2/nested/runtime-rollout/reports/summary.json`,
  `PRIVATE/pg2/p2/nested/runtime-rollout/rg/r/reports/summary.json`,
  `scripts/run_release_readiness_gate.py`,
  `scripts/run_windows_update_rehearsal.py`,
  `scripts/run_promotion_gate.py`,
  `scripts/run_provider_capability_verification_gate.py`,
  `scripts/run_runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`.
- Work completed:
  re-ran the current-state readiness closure lane to a pass at
  `PRIVATE/release-readiness/step23-3-final-readiness-r1/`; re-ran the Windows
  update rehearsal with a shortened artifact root after the original long-path
  attempt failed and preserved the passing bundle at
  `PRIVATE/rr/w1/windows-update-rehearsal/`; hardened the provider capability,
  runtime rollout, and runtime stability gate owners to use workspace-local
  appdata/runtime roots and repo-external temp fixture roots; re-ran the
  promotion lane and narrowed the surviving failures to a dirty worktree plus a
  non-green nested runtime rollout/release gate; and published the final
  redacted evidence index at
  `PRIVATE/final-closure/step23-3-final-evidence-index-r1/`.
- Preserved artifacts:
  accepted Step 23.3 readiness summary sha256
  `4f17df1cad88077395cd500ffa75b2328bebb59696ba7979af217201711bbaac`,
  accepted Step 23.3 Windows update rehearsal summary sha256
  `726972d6aa11f54b4f119e83007fe0164bdd44f2866b13d15d07fad1545be2f2`,
  current fail-closed promotion summary sha256
  `cda067f7c287b50f20c96d43e4c352dab79c159be2cfbddda4b0dd5fc0f18d11`,
  nested runtime rollout summary sha256
  `d3bdb061da2b1ccc9a8ed40b1fe6e4b72f83547b949d1fd1f91656e86d535794`,
  nested runtime stability summary sha256
  `d570f438e066c4e066e855a0a9f8441ed5d45e27fe31456f78803d23fa1056f3`,
  initial long-path rehearsal failure at
  `PRIVATE/release-readiness/step23-3-final-windows-rehearsal-r1/`, initial
  promotion rerun at `PRIVATE/pg/p1/`, and partial runtime rollout rerun at
  `PRIVATE/pgfix/rr3/`.
- Blockers:
  promotion still fails closed because the git worktree is dirty; the nested
  runtime stability release gate is still failing on current state inside
  `PRIVATE/pg2/p2/nested/runtime-rollout/rg/r/`; the failing critical suite is
  `scheduler_recovery_and_idempotency`, which completed 20 iterations but only
  reached 11 consecutive passes; and the promotion gate also reports that the
  `runtime_rollout` stdout summary does not match the persisted
  `summary.json`.
- Next step: Step 23.3, Re-Run Final Promotion/Readiness Closure And Publish
  The Final Evidence Index, continuing from the remaining runtime-stability and
  runtime-rollout blockers and then rerunning promotion from a clean evaluated
  tree.

### 2026-07-18 - Step 23.3 Continuation

- Evidence inspected:
  `PRIVATE/rr4/reports/summary.json`,
  `PRIVATE/pg3/p3/reports/summary.json`,
  `PRIVATE/pg3/p3/nested/runtime-rollout/reports/summary.json`,
  `PRIVATE/pg3/p3/nested/runtime-rollout/rg/r/reports/summary.json`,
  `PRIVATE/pg4/p4/reports/summary.json`,
  `PRIVATE/pg4/p4/nested/runtime-rollout/reports/summary.json`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/common.py`,
  `scripts/run_promotion_gate.py`,
  `scripts/run_release_readiness_gate.py`,
  `scripts/run_provider_capability_verification_gate.py`,
  `scripts/run_runtime_stability_gate.py`,
  `scripts/run_runtime_rollout_gate.py`,
  `scripts/run_windows_update_rehearsal.py`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`.
- Work completed:
  made gate CLI JSON emission byte-stable on Windows by forcing UTF-8 stdout;
  widened the scheduler cancellation suite's internal interrupt wait so the
  release gate no longer trips a machine-load race; re-ran the five-test
  `scheduler_recovery_and_idempotency` suite to a pass; re-ran the full
  runtime rollout gate to a fresh current-state pass at `PRIVATE/rr4/`; re-ran
  the promotion gate to `PRIVATE/pg4/p4/`, where every nested required check
  now passes and the only surviving promotion error is the dirty-worktree
  fail-closed verdict; and published a refreshed evidence index at
  `PRIVATE/final-closure/step23-3-final-evidence-index-r2/`.
- Preserved artifacts:
  current-state runtime rollout summary sha256
  `babdeeed87be2b14ec80df1e94a2ac14ef907924e71b42e484bdb23461162d76`,
  current promotion summary sha256
  `6c9ac5f43a2211e1e4a0442fad696ad1cc359fc5788b2624b13960950d107d41`,
  nested promotion rollout summary sha256
  `05c828439e407e158637b6150d39404ed8b7611e98ccfc51a1f509607573d21a`,
  broad clean-snapshot attempt at
  `D:\CodexTemp\cyz19\abclean-20260718-210214`, and filtered clean-snapshot
  attempt at `D:\CodexTemp\cyz19\abclean-lite-20260718-214400`.
- Blockers:
  the required promotion lane still fails closed because the live repository
  worktree is dirty; a broad temporary clean-snapshot attempt timed out before
  git initialization; and a filtered temporary clean-snapshot attempt timed out
  during copy before commit/promotion execution, so a clean evaluated tree has
  not yet been produced.
- Next step: Step 23.3, Re-Run Final Promotion/Readiness Closure And Publish
  The Final Evidence Index, continuing from the clean-evaluation snapshot
  problem so the dirty-worktree fail-closed verdict can be replaced by a full
  promotion pass.

### 2026-07-18 - Step 23.3 Clean Evaluation Snapshot

- Evidence inspected:
  `D:\CodexTemp\cyz19\csg-230028\SOURCE_EVALUATION_CONTEXT.json`,
  `D:\CodexTemp\cyz19\csg-230028\Q\ql\reports\summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\P\p\nested\local-quick\local-quick\reports\summary.json`,
  `D:\CodexTemp\cyz19\csg-230028\P\p\nested\runtime-rollout\raw\**`,
  `PRIVATE/pg4/p4/reports/summary.json`,
  `scripts/repo_governance_check.py`,
  `scripts/app_hardening_secret_scan.py`,
  `scripts/contract_boundary_audit.py`,
  `scripts/run_local_gate.py`,
  `scripts/run_runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`.
- Work completed:
  built a reusable clean evaluation snapshot of the dirty source state at
  `D:\CodexTemp\cyz19\csg-230028`; fixed the snapshot's missing `release/`,
  `.astrabridge`, `PRIVATE`, `.github/workflows`, and `src-tauri/target`
  inputs/ignores enough for clean local validation; proved that the snapshot's
  local quick gate now passes with clean git status at
  `D:\CodexTemp\cyz19\csg-230028\Q\ql\reports\summary.json`; and preserved the
  clean-snapshot continuation note at
  `PRIVATE/final-closure/step23-3-clean-eval-snapshot-r1/`.
- Preserved artifacts:
  clean-snapshot local quick summary sha256
  `c735e6d96ed2998a4011fe197d58310ea0d4b37b27234f768bb8657fec1b80d3`,
  snapshot commit `c6ba75e544343fbe4549116b6d684250abeab1f6`, and the current
  clean-snapshot runtime rollout partial lane under
  `D:\CodexTemp\cyz19\csg-230028\R`.
- Blockers:
  the clean-snapshot runtime rollout lane still has not emitted a final
  `R\reports\summary.json` before command timeout, and the current clean
  snapshot now carries untracked `Q/` and `R/` artifact roots that should be
  normalized or ignored before the final clean promotion rerun.
- Next step: Step 23.3, Re-Run Final Promotion/Readiness Closure And Publish
  The Final Evidence Index, continuing from the existing clean snapshot rather
  than creating another one from scratch.

### 2026-07-18 - Plan Review

- Evidence inspected:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `docs/DOCUMENT_REGISTRY.json`, `docs/HANDOFF.md`, `docs/PROJECT_SUMMARY.md`,
  and the current user direction for a multi-provider, multi-model Codex shell
  with MCP-first multimodal/tool execution, canonical agent communication,
  A2A interoperability, GUI/code orchestration parity, and safe automatic
  upgrades.
- Diagnosis: the existing product-stability/interoperability execution plan
  already matches the requested durable-handoff scope. Creating a second
  stability plan would split authority and make later execution ambiguous.
- Route change: kept this file as the single durable execution source, added an
  explicit positioning lock so later edits cannot drift toward provider-direct
  tool paths, multiple internal communication ABIs, GUI-only execution
  semantics, or shortcut update flows, and preserved all completed evidence as
  validated prior work rather than restarting from Step 0.
- What must not be weakened: MCP remains the normal multimodal/tool/resource
  plane; the internal durable agent communication ABI remains singular; the
  external A2A gateway remains an adapter boundary rather than the runtime
  store schema; GUI/code parity remains canonical-graph parity; and automatic
  upgrades remain journaled and rollback safe.
- Next step: Step 23.3, Re-Run Final Promotion/Readiness Closure And Publish
  The Final Evidence Index.

### 2026-07-18 - Step 23.2

- Completed: re-ran the current-state final GUI/code/A2A/MCP/interoperability
  closure lanes and preserved a fresh accepted Step 23.2 bundle after fixing
  one stale mixed-MCP fixture contract drift and moving the evidence runner onto
  a workspace-local runtime root.
- Evidence preserved: the first failed bundle
  `PRIVATE/final-interop/step23-2-final-interop-r1/` captured the initial
  `D:\\AstraBridgeRuntime` permission mismatch; the second failed bundle
  `PRIVATE/final-interop/step23-2-final-interop-r2/` captured the remaining
  mixed-MCP fixture drift; and the accepted current-state passing bundle is
  `PRIVATE/final-interop/step23-2-final-interop-r3/`.
- Files changed:
  `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py` and this
  plan.
- Validation:
  `PRIVATE/final-interop/step23-2-final-interop-r3/reports/summary.json`
  returned top-level `pass`; the GUI/authored adapter lane passed the ComfyUI
  round-trip, ComfyUI UI-hint re-export, ComfyUI HTTP import/export, LangGraph
  round-trip, LangGraph UI-hint re-export, and LangGraph HTTP import/export
  tests; the TypeScript SDK source-owned round-trip lane passed; the mixed
  registry MCP runtime lane passed; and the external A2A lane passed HTTP task
  lifecycle/artifact exchange, strict negotiation/downgrade, negative security
  conformance, and replay rejection coverage.
- Route correction: Step 23.2 initially failed because the ad hoc evidence
  runner did not set `ASTRABRIDGE_RUNTIME_ROOT`, causing several tests to write
  outside the workspace and fail with `PermissionError`. Re-running with a
  workspace-local runtime root restored the intended bounded current-state
  evidence path. The remaining mixed-MCP failure then proved to be stale test
  fixture drift: `node_mcp` declared `machine_result_schema_ref =
  schema.tool_result` without exposing that same schema on its output port, so
  the fixture was updated to match the current orchestration contract.
- Next step: Step 23.3, Re-Run Final Promotion/Readiness Closure And Publish
  The Final Evidence Index.

### 2026-07-18 - Step 23.1

- Completed: closed the current-state runtime rollout/release-gate rerun lane
  with a fresh passing Step 23.1 evidence bundle after fixing both a real
  runtime reattach/rollback bug and the release-gate scheduler-suite cleanup
  flakiness that was masking the final result.
- Evidence preserved: the failed intermediate bundles
  `PRIVATE/runtime-rollout/step23-1-final-rollout-r2/`,
  `PRIVATE/runtime-rollout/step23-1-final-rollout-r3/`, and
  `PRIVATE/runtime-rollout/step23-1-final-rollout-r4/` remain intact, and the
  accepted current-state passing bundle is
  `PRIVATE/runtime-rollout/step23-1-final-rollout-r5/`.
- Files changed:
  `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`, and this plan.
- Validation: targeted node-executor activation tests passed; targeted executor
  activation integration passed; the critical
  `scheduler_recovery_and_idempotency` five-test suite passed under the local
  Python lane; the same five-test suite passed five repeated iterations under
  the hermes release-gate Python lane; and
  `python scripts/run_runtime_rollout_gate.py --run-id step23-1-final-rollout-r5`
  returned a top-level `pass` with rollout feature flags, shadow comparison,
  migration, rollback-readback, Desktop build, Desktop visual QA, nested
  runtime-stability release gate, and rollout secret scan all passing.
- Process hygiene: reaped stale AstraBridge-owned `cmd`/`node` helper processes
  left behind by earlier failed rollout/test attempts before the final `r5`
  rerun so the accepted evidence came from a clean local state.
- Next step: Step 23.2, Re-Run Final GUI/Code/A2A/MCP/Interop Closure
  Evidence.

### 2026-07-18 - Step 23 Plan Review And Step 23.1 Start

- Plan review trigger: the original unsplit Step 23 closure lane was too broad
  to satisfy the one-step-per-round execution rule and could not preserve a
  clear multi-turn handoff boundary once Step 22 completed.
- Route change: split Step 23 into Step 23.1 runtime rollout/release-gate
  revalidation, Step 23.2 final GUI/code/A2A/MCP/interoperability closure
  evidence, and Step 23.3 final promotion/readiness closure plus final evidence
  index publication. This is a plan-document refinement only; no previously
  validated work was reset.
- Evidence inspected: `scripts/run_runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `scripts/run_runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `scripts/run_promotion_gate.py`,
  `PRIVATE/runtime-rollout/step22-final-rollout-r3/reports/summary.json`,
  `PRIVATE/runtime-rollout/step23-1-final-rollout-r2/reports/summary.json`,
  `PRIVATE/runtime-rollout/step23-1-final-rollout-r2/validations/release-gate-summary.json`,
  `PRIVATE/runtime-rollout/step23-1-final-rollout-r2/rg/r/reports/report.md`,
  and `PRIVATE/runtime-rollout/step23-1-final-rollout-r2/rg/r/validations/fault-matrix.json`.
- Implementation delta: the first Step 23.1 rerun
  (`step23-1-final-rollout-r1`) exposed a Windows path-length-sensitive
  rollback-manifest write failure in node-executor activation artifacts. The
  repository now shortens executor-activation artifact ids in
  `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py` via a
  stable hashed id scheme, and the targeted node-type/journaled-activation
  tests were extended accordingly.
- Validation: `python -m unittest apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_journaled_executor_activation_shortens_artifact_id_for_long_scope_paths apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_journaled_executor_activation_commits_and_updates_current_pointer apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_journaled_executor_activation_failure_preserves_previous_pointer`
  passed; `python -m unittest apps.astrabridge-sidecar.tests.test_executor_activation_integration`
  passed; the refreshed rollout bundle
  `PRIVATE/runtime-rollout/step23-1-final-rollout-r2/` passed rollout feature
  flags, shadow comparison, migration, rollback-readback, Desktop build,
  Desktop visual QA, and rollout secret scan, but failed the nested
  runtime-stability `release_gate` because critical suite
  `scheduler_recovery_and_idempotency` passed 6/7.
- Remaining blocker: after correcting the live-runtime graph fixture drift in
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`, the only remaining
  failing scheduler recovery lane is
  `test_known_external_handle_reattaches_without_restarting_turn`; preserved
  repro evidence shows the external handle is accepted and preserved across
  recovery, but the recovered run still converges to `failed` instead of
  `completed`.
- Files changed: this plan,
  `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_node_type_registry.py`, and
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`.
- Next step: Step 23.1, Re-Run Runtime Rollout, Rollback-Readback, And Nested
  Release Gate On The Current State, starting at the runtime-service
  reattach/reconcile completion path and then refreshing the rollout bundle with
  a new run id after the remaining scheduler recovery suite is green.

### 2026-07-17 - Step 0

- Completed: Created the durable follow-on plan from the product-stability audit
  and made the next bounded work unit explicit.
- Preserved: The completed predecessor stability plan and all historical Provider,
  graph, multimodal, app-hardening, update, dogfood, and validation evidence.
- Files changed: This plan plus the canonical document registry, current-entry
  documentation, ownership/governance references, project summary, handoff, and
  project log required to activate one source of truth.
- Validation: `python scripts/run_local_gate.py --quick` passed in 34.3 seconds;
  governance reported 0 errors/0 warnings across 1,268 text files, secret scan
  reported 0 errors/0 warnings across 181 text files, the contract boundary
  audit passed 18/18 checks, and focused governance/secret tests passed 14/14
  and 6/6.
- Blockers: None. GitHub CLI authentication remains user-deferred and is not a
  prerequisite for creating CI workflow files or executing Step 1 locally.
- Next step: Step 1, Make Promotion Gates Non-Skippable And Add CI Entry Points.

### 2026-07-17 - Step 1

- Completed: Added a fail-closed promotion gate owner and wrapper, upgraded the
  local gate to emit machine-readable summaries/reports, and introduced
  deterministic PR/nightly/release GitHub workflow entry points that call the
  canonical wrapper instead of duplicating suite lists.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/promotion_gate.py`,
  `scripts/run_promotion_gate.py`, `scripts/run_local_gate.py`,
  `.github/workflows/pr-promotion-gate.yml`,
  `.github/workflows/nightly-promotion-gate.yml`,
  `.github/workflows/release-promotion-gate.yml`,
  `scripts/contract_boundary_audit.py`, focused promotion-gate tests, and the
  current governance/ownership/readme references for the new entry points.
- Validation: `python -m py_compile scripts/run_local_gate.py scripts/run_promotion_gate.py apps/astrabridge-sidecar/astrabridge_sidecar/promotion_gate.py scripts/contract_boundary_audit.py`
  passed; `python -m unittest apps.astrabridge-sidecar.tests.test_promotion_gate`
  passed 3/3; `python -m unittest discover -s apps/astrabridge-sidecar/tests -p
  test_contract_boundary_audit.py` passed 3/3; `python scripts/contract_boundary_audit.py`
  passed 19/19 checks; `python scripts/run_local_gate.py --quick` passed with
  0 governance errors/warnings and 0 secret-scan errors/warnings; a real
  `python scripts/run_promotion_gate.py --mode pr --expected-commit <HEAD>`
  run failed closed in the dirty worktree exactly because `dirty=true`, while
  preserving summary/report/manifest evidence under
  `PRIVATE/promotion-gates/local-pr-dirty-check-2/`; `git diff --check` reported
  only line-ending warnings and no content-format errors.
- Blockers: None for Step 1. The local dirty-tree promotion failure is expected
  evidence, not a product blocker; CI workflows install the required toolchains
  before calling the promotion gate.
- Next step: Step 2, Establish One Release Identity And Clean Packaging Staging
  Contract.

### 2026-07-17 - Step 2

- Completed: Added one canonical release-identity owner and manifest, switched
  current Desktop/Sidecar/MCP runtime version consumers to that owner, and
  landed a clean release-readiness gate with an explicit packaging allowlist,
  deterministic stage comparison, updater-manifest emission, file inventory,
  content hashes, SBOM input, and source-provenance output.
- Files changed: Added `release/astrabridge-release-identity.json`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py`,
  `scripts/run_release_readiness_gate.py`, and
  `apps/astrabridge-sidecar/tests/test_release_identity.py`; updated Sidecar
  version consumers, `scripts/contract_boundary_audit.py`, release/readiness
  docs, and current ownership/governance references.
- Validation: `python -m py_compile apps\\astrabridge-sidecar\\astrabridge_sidecar\\release_identity.py scripts\\run_release_readiness_gate.py apps\\astrabridge-sidecar\\astrabridge_sidecar\\__init__.py apps\\astrabridge-sidecar\\astrabridge_sidecar\\app_server_client.py apps\\astrabridge-sidecar\\astrabridge_sidecar\\mcp_broker_service.py apps\\astrabridge-sidecar\\astrabridge_sidecar\\server.py`
  passed; `python -m unittest discover -s apps/astrabridge-sidecar/tests -p
  test_release_identity.py` passed 3/3; `python -m unittest discover -s
  apps/astrabridge-sidecar/tests -p test_contract_boundary_audit.py` passed
  3/3; `python scripts/contract_boundary_audit.py` passed 20/20 checks;
  `python scripts/run_release_readiness_gate.py --artifact-root
  PRIVATE/release-readiness --run-id local-step2-readiness` passed with matching
  stage inventories/hashes and zero binding mismatches; `python
  scripts/run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings; `git diff --check`
  reported only line-ending warnings and no content-format failures.
- Artifacts preserved: Release-readiness evidence under
  `PRIVATE/release-readiness/local-step2-readiness/`, including staged
  inventories, provenance, updater manifests, and readiness summaries.
- Blockers: None.
- Next step: Step 3, Enforce The Canonical Protocol At Every Durable Write
  Boundary.

### 2026-07-17 - Step 3

- Completed: Added one canonical protocol-persistence owner and enforced
  schema validation at the innermost durable write boundary for run projections,
  events, envelopes, content parts, and artifact references.
- Files changed: Added
  `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/persistence.py`;
  updated `apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `scripts/generate_protocol_types.py`, the generated Python and TypeScript
  protocol bindings, the shared protocol fixtures, focused persistence/schema
  tests, and `scripts/contract_boundary_audit.py`.
- Runtime contract changes: Schema-derived vocabularies now define the runtime
  event and artifact enums, schema-external persisted event names were removed,
  legacy artifact path identities are upgraded or rejected at the persistence
  boundary, and unsupported run-projection schema versions now fail with an
  actionable compatibility error.
- Validation: `python scripts\\generate_protocol_types.py --write` passed;
  `python -m unittest discover -s apps\\astrabridge-sidecar\\tests -p
  test_protocol_persistence.py` passed 5/5; `python -m unittest discover -s
  apps\\astrabridge-sidecar\\tests -p test_protocol_schema.py` passed 9/9;
  `python -m unittest discover -s apps\\astrabridge-sidecar\\tests -p
  test_durable_run_store.py` passed 9/9; `python -m unittest discover -s
  apps\\astrabridge-sidecar\\tests -p test_contract_boundary_audit.py` passed
  3/3; `npm.cmd test -- src/astrabridge_protocol/generated/v1.test.ts` passed
  4/4; `python scripts\\contract_boundary_audit.py` passed 21/21 checks with
  canonical protocol fixture counts 10 valid / 7 invalid; `python
  scripts\\run_local_gate.py --quick` passed with 0 governance errors/warnings
  and 0 secret-scan errors/warnings; `git diff --check` reported only CRLF
  conversion warnings and no content-format failures.
- Artifacts preserved: No private evidence was deleted; existing validation,
  logs, caches, and release-readiness artifacts remain intact.
- Blockers: None.
- Next step: Step 4, Complete Delivery Identity, Ordering, Expiry, And
  Cancellation Semantics.

### 2026-07-17 - Step 4

- Completed: Tightened durable delivery identity and processing semantics across
  agent envelopes, inbox/outbox processing records, live handoff admission, and
  cancellation convergence so duplicate payloads deduplicate, conflicting
  payloads reject, and late completions cannot revive cancelled runs.
- Files changed: Updated
  `apps/astrabridge-sidecar/astrabridge_sidecar/protocol/persistence.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_durable_run_store.py`, and
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`.
- Runtime contract changes: Durable storage now distinguishes immutable
  `message_id`, delivery `idempotency_key`, and processing-key inbox admission;
  inbox and outbox ids reject conflicting payload reuse; per-edge delivery
  sequence ordering is enforced; handoffs reject early, expired, replayed, and
  mismatched-audience delivery before provider dispatch; and cancellation now
  suppresses late provider completions while converging to a resolved terminal
  cancellation record.
- Validation: `python -m unittest discover -s apps\\astrabridge-sidecar\\tests -p
  test_durable_run_store.py` passed 11/11; `python -m unittest discover -s
  apps\\astrabridge-sidecar\\tests -p test_graph_scheduler.py` passed 20/20;
  `python -m unittest discover -s apps\\astrabridge-sidecar\\tests -p
  test_protocol_persistence.py` passed 5/5; `python
  scripts\\contract_boundary_audit.py` passed 21/21 checks; `python
  scripts\\run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings; `git diff --check`
  reported only CRLF conversion warnings and no content-format failures.
- Artifacts preserved: No private evidence, logs, caches, or preserved
  validation outputs were deleted.
- Blockers: None.

### 2026-07-17 - Step 5

- Step 5 completed on 2026-07-17. Live graph admission is now structurally
  bounded, queued cancellations do not dispatch, retry storms are capped by
  per-run/provider/model budgets, and provider/model circuit breakers are
  observable through redacted runtime status.
- Evidence: `apps/astrabridge-sidecar/astrabridge_sidecar/graph_dispatch_control.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/graph_scheduler.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, and
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`.
- Validation: `python -m unittest tests.test_graph_scheduler`; `python -m
  unittest tests.test_runtime_client_pool`; `python
  scripts\contract_boundary_audit.py`; `python scripts\run_local_gate.py
  --quick`; `git diff --check`.
- Next step: Step 6, Complete The Provider Adapter ABI And Verified Capability
  Snapshots.

### 2026-07-17 - Step 6

- Completed: Standardized the built-in provider transport ABI for shared
  request/stream/error/cancel behavior and tied multimodal graph admission to
  current verified capability snapshots rather than static model booleans.
- Files changed: Added
  `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_snapshot.py`
  and focused Step 6 tests; updated
  `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/base.py`,
  and
  `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate.py`.
- Runtime contract changes: Provider compatibility-matrix evidence now
  aggregates into versioned per-model verified capability snapshots; router
  refresh marks stale snapshots when the provider adapter/model contract
  fingerprint changes; multimodal live graph admission requires a current
  verified snapshot for required image/audio/video ports and preserves the
  approved snapshot in queued/live run policy manifests; and every built-in
  provider transport is held to one shared request/stream/error/cancel
  conformance suite.
- Validation: `python -m unittest tests.test_provider_capability_snapshot
  tests.test_provider_transport_conformance tests.test_router_transport_registry
  tests.test_graph_scheduler tests.test_runtime_client_pool
  tests.test_provider_capability_verification_gate` passed 44/44 with
  `ASTRABRIDGE_RUNTIME_ROOT` redirected into a writable local runtime root;
  `python scripts\contract_boundary_audit.py` passed 21/21 checks; `python
  scripts\run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings; `git diff --check`
  reported only CRLF conversion warnings and no content-format failures.
- Blockers: None.
- Next step: Step 7, Prove Cross-Provider Context And Artifact Continuity On
  Every Handoff Path.

### 2026-07-17 - Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/project_context_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_conversation_service.py`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`,
  `apps/astrabridge-sidecar/tests/test_provider_handoff_compatibility.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`, `python
  scripts\contract_boundary_audit.py`, and `python scripts\run_local_gate.py
  --quick`.
- Diagnosis: Continue Step 7 with a tighter execution target instead of opening
  a new plan. Graph-path neutral bundles, digests, and target-turn injection
  are now evidenced, but ordinary provider switching still has unresolved
  reused-target-thread bundle persistence and dropped-artifact diagnostic
  mismatches in focused tests.
- Route change: Kept Step 7 as the active work unit, changed its status to `in
  progress`, and narrowed the next action to the two remaining failing ordinary
  handoff compatibility cases rather than broadening the plan into a new audit.
- What must not be weakened: Provider-private state must remain excluded from
  target requests and durable state, graph and ordinary handoffs must converge
  on one neutral continuity contract, and Step 7 cannot be marked complete
  until the focused compatibility tests and quick gates pass together.
- Next step: Step 7, Prove Cross-Provider Context And Artifact Continuity On
  Every Handoff Path.

### 2026-07-17 - Step 7

- Completed: Closed the remaining ordinary-provider handoff continuity gap by
  preserving richer source-thread projection inputs during handoff priming,
  which restored deterministic dropped-artifact diagnostics and neutral bundle
  persistence on reused-target-thread and fresh-target-thread switching paths
  while keeping the graph-path neutral bundle contract intact.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
  plus the already active Step 7 owner and validation surfaces in
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/project_context_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_conversation_service.py`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`,
  `apps/astrabridge-sidecar/tests/test_provider_handoff_compatibility.py`, and
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`
  passed; with `ASTRABRIDGE_RUNTIME_ROOT` redirected into a writable local
  runtime root and `PYTHONPATH=apps/astrabridge-sidecar`, `python -m unittest
  tests.test_provider_handoff_compatibility.ProviderHandoffCompatibilityTests.test_reused_target_thread_handoff_persists_neutral_bundle_with_reused_projection_mode
  tests.test_provider_handoff_compatibility.ProviderHandoffCompatibilityTests.test_cross_provider_projection_warning_path_keeps_lane_state_secret_free`
  passed 2/2; `python -m unittest
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_provider_handoff_uses_history_projection_summary_for_transition_diagnostics`
  passed 1/1; `python -m unittest
  tests.test_graph_scheduler.DurableGraphSchedulerTests.test_neutral_context_bundle_preserves_typed_inputs_artifacts_and_cross_provider_projection
  tests.test_provider_handoff_compatibility
  tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_provider_handoff_uses_history_projection_summary_for_transition_diagnostics
  tests.test_sidecar_services.AstraBridgeServiceTests.test_task_service_tracks_provider_handoff_without_secrets
  tests.test_sidecar_services.AstraBridgeServiceTests.test_project_context_pack_includes_task_conversation_digest
  tests.test_sidecar_services.AstraBridgeServiceTests.test_release_grade_provider_switch_workflow_integrates_checkpoint_review_tests_and_recovery`
  passed 8/8; `python scripts\contract_boundary_audit.py` passed 21/21 checks;
  `python scripts\run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings; `git diff --check`
  reported only CRLF conversion warnings and no content-format failures.
- Process hygiene: Ran a read-only `python`/`node`/`cmd` process audit before
  and after the Step 7 work and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap in this round.
- Blockers: None.
- Next step: Step 8, Define The External A2A Gateway And Agent Card Registry.

### 2026-07-17 - Step 8

- Completed: Added a runtime-owned external A2A gateway boundary with one pinned
  supported protocol-version window, digest-pinned Agent Card registry entries,
  compile-time `a2a_card:` resolution, immutable compiled-plan gateway
  snapshots, explicit task/message/part/artifact adapters, transport/auth
  subset enforcement, workspace trust levels, unsafe-artifact rejection, and
  task-lifecycle transition validation without changing AstraBridge's internal
  durable protocol schema.
- Files changed: Added
  `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py` and
  `apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py`; updated
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_compiler.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py`,
  `scripts/contract_boundary_audit.py`, and
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py
  apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py
  apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_compiler.py
  apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_contract.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py` passed;
  with `PYTHONPATH=apps/astrabridge-sidecar`, `python -m unittest
  tests.test_external_a2a_gateway tests.test_agent_orchestration_contract
  tests.test_agent_orchestration_checks tests.test_contract_boundary_audit`
  passed 22/22; `python scripts\contract_boundary_audit.py` passed 22/22
  checks and now includes the `external_a2a_gateway_and_agent_card_registry`
  owner; `python scripts\run_local_gate.py --quick` passed with 0 governance
  errors/warnings and 0 secret-scan errors/warnings.
- Process hygiene: Ran a read-only `python`/`node`/`cmd` process audit before
  and after the Step 8 work and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap in this round.
- Blockers: None.
- Next step: Step 9, Implement A2A Task, Streaming, Cancellation, And Artifact
  Interoperability.

### 2026-07-17 - Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`, and
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`.
- Diagnosis: Keep Step 9 as the active work unit and narrow the implementation
  seam instead of expanding the plan. The safest owner boundary is a gateway
  service wired through `AppContext` and HTTP routes, with runtime-backed
  execution reusing the existing `start_turn(...)` and `interrupt_turn(...)`
  seams rather than inventing a parallel scheduler.
- Route change: Updated the current work unit and Step 9 status to `in
  progress`, and changed the next action to implement discovery plus
  send/stream/cancel endpoints, a runtime-backed executor path, and a fake
  executor seam for two-process A2A interoperability tests.
- What must not be weakened: External A2A remains a gateway-owned wire
  contract, the internal durable execution ABI remains the only durable owner,
  external cancellation must reach the real provider/tool lane, and no remote
  secret, private reasoning, or unsafe artifact path may cross the boundary.
- Next step: Step 9, Implement A2A Task, Streaming, Cancellation, And Artifact
  Interoperability.

### 2026-07-17 - Step 9

- Completed: Implemented a real external A2A gateway service with local Agent
  Card discovery, task journaling, idempotent send handling, task retrieval,
  reconnectable SSE task streaming, cancellation, runtime-bridge execution,
  fake-executor interoperability coverage, and sanitized message/artifact
  exchange without changing AstraBridge's internal durable execution ABI.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, and
  `apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py`.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py
  apps/astrabridge-sidecar/astrabridge_sidecar/server.py
  apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py` passed; `python
  -m unittest
  apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_contract.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py
  apps/astrabridge-sidecar/tests/test_contract_boundary_audit.py` passed 25/25;
  the HTTP interoperability coverage now proves local Agent Card discovery,
  duplicate send idempotency, reconnectable SSE task streams, delayed
  completion, remote-failure handling, runtime-lane cancellation bridging, and
  typed artifact exchange; `python scripts\contract_boundary_audit.py` passed
  22/22 checks; `python scripts\run_local_gate.py --quick` passed with 0
  governance errors/warnings and 0 secret-scan errors/warnings.
- Process hygiene: Ran a read-only `python`/`node`/`cmd` process audit before
  and after the Step 9 work and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap in this round.
- Blockers: None.
- Next step: Step 10, Add A2A Trust, Replay Protection, Version Negotiation,
  And Conformance.

### 2026-07-17 - Step 10

- Completed: Added gateway-owned trust enforcement, replay-window rejection,
  deterministic protocol/binding/extension negotiation, optional signed Agent
  Card verification, reusable external A2A conformance fixtures, and explicit
  HTTP rejection/status mapping without moving any trust/replay fields into the
  internal durable execution ABI.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_conformance.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`,
  `apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py`,
  `scripts/contract_boundary_audit.py`, and
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py
  apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_conformance.py
  apps/astrabridge-sidecar/astrabridge_sidecar/server.py
  apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py` passed; `python
  -m unittest
  apps/astrabridge-sidecar/tests/test_external_a2a_gateway.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_contract.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py
  apps/astrabridge-sidecar/tests/test_contract_boundary_audit.py` passed 28/28;
  the Step 10 coverage now proves expired, replayed, wrong-audience,
  untrusted, oversized, and incompatible requests reject with deterministic
  gateway status codes; signed-card trust decisions and negotiated downgrade
  outcomes remain observable in gateway metadata; `python
  scripts\contract_boundary_audit.py` passed 22/22 checks and now audits the
  external A2A conformance owner; `python scripts\run_local_gate.py --quick`
  passed with 0 governance errors/warnings and 0 secret-scan errors/warnings.
- Process hygiene: Ran a read-only `python`/`node`/`cmd` process audit before
  and after the Step 10 work and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap in this round.
- Blockers: None.
- Next step: Step 11, Complete Remote MCP Authorization, Durable Task
  Bridging, And Typed Results.

### 2026-07-17 - Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_config_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_server_core.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/multimodal_result_envelope.py`,
  and `apps/astrabridge-sidecar/tests/test_mcp_broker_service.py`.
- Diagnosis: Keep Step 11 as the active work unit, but tighten the execution
  seam instead of broadening the plan. The broker is still loopback-only,
  `mcp_config_service.py` already defines `streamable_http` remote-server
  configuration, `mcp_server_core.py` already owns HTTP session/progress/cancel
  semantics that can be mirrored for remote pooling/recovery, and
  `multimodal_result_envelope.py` is already the typed-result/content/artifact
  owner that must stay authoritative for remote MCP outputs too.
- Route change: Updated the current work unit to `in progress` and replaced the
  generic inspection next action with one bounded implementation path: extend
  the broker for protected-resource-aware remote MCP transport, bridge eligible
  long-running calls through durable AstraBridge task state without duplicating
  side effects, and prove typed multimodal parity across loopback and remote
  transports in focused tests.
- What must not be weakened: MCP remains one capability plane across loopback
  and remote transports, AstraBridge durable run/task state remains the only
  execution-state owner, remote authorization must stay least-scope and
  protected-resource-bound, and typed multimodal results must not collapse into
  plain text or leak machine-local paths.
- Next step: Step 11, Complete Remote MCP Authorization, Durable Task
  Bridging, And Typed Results.

### 2026-07-17 - Step 11

- Completed: Extended the shared MCP broker from loopback-only routing to one
  remote `streamable_http` capability plane with protected-resource metadata
  discovery, least-scope JWT audience/scope checks, session pooling/recovery,
  durable external-operation bridging through the workspace-local durable run
  store, preserved progress notifications, and remote typed-result/path-leak
  validation.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py`,
  `apps/astrabridge-sidecar/tests/test_mcp_broker_service.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and
  `scripts/contract_boundary_audit.py`.
- Runtime contract changes: Remote MCP servers configured through
  `mcp_config_service.py` may now negotiate `streamable_http` sessions through
  the shared broker; bearer-token use is gated by discovered protected-resource
  metadata plus least-scope audience/scope validation; accepted long-running
  remote operations persist in `DurableRunEventStore.external_operations`
  without duplicate redispatch after restart; and remote multimodal
  `typed_result` / `ContentPart` / `ArtifactRef` payloads are preserved only
  when they remain machine-path-safe.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py
  apps/astrabridge-sidecar/tests/test_mcp_broker_service.py` passed; `python
  -m unittest discover -s apps/astrabridge-sidecar/tests -p
  test_mcp_broker_service.py` passed 12/12; `python -m unittest discover -s
  apps/astrabridge-sidecar/tests -p test_mcp_server_core.py` passed 8/8;
  `python -m unittest discover -s apps/astrabridge-sidecar/tests -p
  test_durable_run_store.py` passed 11/11; `python -m unittest discover -s
  apps/astrabridge-sidecar/tests -p test_contract_boundary_audit.py` passed
  3/3; `python scripts/contract_boundary_audit.py` passed 22/22 checks; `python
  scripts/run_local_gate.py --quick` passed with 0 governance errors/warnings
  and 0 secret-scan errors/warnings; `git diff --check` reported only CRLF
  conversion warnings and no content-format failures.
- Process hygiene: Ran read-only `python`/`node`/`cmd` process audits before
  and after the Step 11 work and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap in this round.
- Blockers: None.
- Next step: Step 12, Implement The Runtime Executor Registry And Capability
  Matrix.

### 2026-07-17 - Plan Review

- Evidence inspected: `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `PLAN/ASTRABRIDGE_STABILITY_PROTOCOL_AND_AGENT_RUNTIME_EXECUTION_PLAN.md`,
  `PLAN/AGENT_GRAPH_MULTIMODAL_PRODUCT_EXECUTION_PLAN.md`,
  `PLAN/PROVIDER_MODEL_COVERAGE_REASONING_AUDIT_HANDOFF_PLAN.md`, and the
  current `PLAN/` inventory.
- Diagnosis: The existing product-stability plan already covers the user's
  requested hardening scope more cleanly than a new parallel handoff file. The
  missing need was not a new route map, but an explicit durable statement that
  this file remains the canonical handoff/control surface for the current
  multi-provider, A2A, MCP, GUI+code orchestration, and auto-upgrade
  discussion.
- Route change: Kept this file as the single active scheduler, added an
  explicit preferred-handoff statement near the authority section, and left the
  current execution anchor on Step 12 instead of spawning a second active plan.
- What must not be weakened: MCP stays the normal multimodal/tool plane,
  external A2A stays a gateway rather than the durable-store schema, GUI and
  code orchestration continue to share one canonical graph contract, and
  upgrade work remains signed, journaled, and rollback-safe rather than
  cosmetic.
- Next step: Step 12, Implement The Runtime Executor Registry And Capability
  Matrix.

### 2026-07-17 - Step 12

- Completed: Added the canonical executor registry and surfaced capability
  matrix in `node_type_registry.py`, preserved authored
  `node_type_registry_fingerprint` through orchestration validation so drift
  stays observable, made dry-run and fixture/live admission fail closed through
  `compiled_plan_executor_capability_report(...)`, and made the live runtime
  consume `compiler_executor_id` before any provider/tool dispatch while the
  Desktop registry UI now exposes real live/fixture availability from the same
  snapshot.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`,
  `apps/astrabridge-desktop/src/types.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphNodeRegistryUi.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphNodeRegistryUi.test.ts`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and
  `scripts/contract_boundary_audit.py`.
- Validation: `python -m py_compile apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py apps/astrabridge-sidecar/tests/test_node_type_registry.py apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`
  passed; `python -m unittest apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_registry_snapshot_contains_initial_public_types_and_aliases apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_executor_capability_report_blocks_live_run_for_fixture_only_executor_and_accepts_fixture apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_executor_capability_report_detects_registry_fingerprint_drift`
  passed 3/3; `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'; python -m unittest apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_preflight_blocks_all_dispatch_when_executor_is_not_live_compatible apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_dry_run_graph_blocks_stale_node_type_registry_fingerprint_before_execution`
  passed 2/2; `node ./node_modules/vitest/vitest.mjs run src/features/runtime/taskGraphNodeRegistryUi.test.ts`
  passed 1/1 in `apps/astrabridge-desktop`; `python scripts/contract_boundary_audit.py`
  passed 22/22 checks; `python scripts/run_local_gate.py --quick` passed with
  0 governance errors/warnings and 0 secret-scan errors/warnings.
- Process hygiene: Ran read-only `python`/`node`/`cmd` process audits before
  and after the Step 12 work and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap in this round.
- Blockers: None.
- Next step: Step 13, Implement Live MCP, Transform, Router, And Artifact
  Executors.

### 2026-07-17 - Step 13

- Completed: Implemented deterministic live executors for MCP tool, MCP
  resource, transform, router/condition, artifact source, and artifact sink;
  made the live runtime dispatch local executors without provider turns;
  preserved typed port values ahead of wrapper `machine_result` metadata during
  handoff projection; enforced branch-selected downstream delivery; and kept
  least-privilege MCP/resource policy plus artifact digest validation fail
  closed.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_node_type_registry.py`, and
  `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py
  apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py
  apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py
  apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py
  apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py
  apps/astrabridge-sidecar/tests/test_node_type_registry.py` passed; with
  `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`, `python
  -m unittest
  apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_registry_snapshot_contains_initial_public_types_and_aliases
  apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_executor_capability_report_accepts_live_and_fixture_executor_after_step_13
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_local_executor_runs_without_provider_turn_dispatch
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_mcp_resource_executor_runs_without_provider_turn_dispatch
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_executes_agent_mcp_transform_router_and_selected_sink
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_artifact_source_fails_closed_on_digest_mismatch
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_preflight_blocks_all_dispatch_when_any_node_route_is_incomplete`
  passed 7/7; `python -m unittest
  apps.astrabridge-sidecar.tests.test_durable_run_store.DurableRunStoreTests.test_create_reload_and_projection_rebuild_are_deterministic
  apps.astrabridge-sidecar.tests.test_durable_run_store.DurableRunStoreTests.test_duplicate_run_create_with_idempotency_key_returns_same_projection
  apps.astrabridge-sidecar.tests.test_graph_scheduler.DurableGraphSchedulerTests.test_duplicate_delivery_idempotency_key_does_not_start_target_twice`
  passed 3/3.
- Process hygiene: Ran read-only `python`/`node`/`cmd` process audits before
  and after the Step 13 work and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap in this round.
- Blockers: None.
- Next step: Step 14, Implement Durable Approval, Loop, Subgraph, And
  Recovery Semantics.

### 2026-07-17 - Plan Review

- Evidence inspected: `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  the current `PLAN/` inventory, and the active Step 13 runtime seams in
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py` and
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`.
- Diagnosis: No parallel handoff file is needed. This plan already covers the
  requested hardening scope for multi-provider positioning, MCP-normalized
  multimodal/tool execution, standards-based A2A interoperability, GUI and
  code orchestration parity, and signed auto-upgrade behavior. The real gap is
  a sharper Step 13 entry point, not a new scheduler.
- Route change: Kept this file as the single active durable-handoff and
  execution source, promoted the Step 13 current work unit from queued to `in
  progress`, and tightened the next action to the concrete runtime seams that
  must move first: executor-aware live preparation, branch-filtered handoff
  persistence, artifact-aware worker-output persistence, and the first local
  MCP/transform/router/artifact executors.
- What must not be weakened: Do not create a second active stability plan, do
  not bypass MCP for multimodal/tool execution, do not collapse external A2A
  into AstraBridge's durable execution schema, do not split GUI and code
  orchestration into separate graph contracts, and do not treat update UX as
  complete before signed, journaled, rollback-safe runtime activation exists.
- Next step: Step 13, Implement Live MCP, Transform, Router, And Artifact
  Executors.

### 2026-07-17 - Plan Review

- Evidence inspected: `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `PLAN/AGENT_GRAPH_COMFYUI_PRODUCTIZATION_HANDOFF_PLAN.md`,
  `PLAN/MULTI_AGENT_GUI_ORCHESTRATION_HANDOFF_PLAN.md`, and the current
  product-direction notes from this handoff request.
- Diagnosis: The active stability/interoperability plan already matches the
  requested product line better than a new handoff file would. The missing
  piece was explicit wording that AstraBridge is positioning as a
  multi-provider, multi-model Codex shell with one canonical internal
  communication format, MCP-first multimodal/tool execution, standards-based
  external A2A interoperability, GUI authoring aligned with
  ComfyUI/LangGraph/LangChain-style orchestration expectations, and rollback-safe
  automatic upgrade behavior.
- Route change: Refreshed the authority, objective, deliverables, and graph
  boundary language in this file to encode that positioning as the durable
  handoff contract. No numbered-step sequencing changed; Step 13 remains the
  active execution entry point.
- What must not be weakened: Do not create a parallel active plan, do not add
  a second internal message schema beside the canonical AstraBridge envelope,
  do not bypass MCP for multimodal or tool execution, do not let GUI patterns
  fork the persisted graph contract away from code authoring, and do not label
  auto-update complete before signed, journaled, health-checked, rollback-safe
  activation exists.
- Next step: Step 13, Implement Live MCP, Transform, Router, And Artifact
  Executors.

### 2026-07-17 - Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`, and
  `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`.
- Diagnosis: The original Step 14 bundled three distinct durable owners into
  one step: live approval pause/resolution, live loop/subgraph executors, and
  downstream live recovery/reuse semantics. Current repository evidence shows
  approval already has durable fixture/task-state machinery that can be
  productized first, while loop/subgraph remain registry-planned and live
  recovery still needs a separate owner path. Keeping them as one step would
  hide progress and blur acceptance evidence.
- Route change: Split Step 14 into 14.1 live durable approval pause/resolution,
  14.2 loop/subgraph live executors, and 14.3 live recovery/resume/reuse
  semantics. This is a step-structure revision only; it preserves the original
  Step 14 objective and acceptance bar.
- What must not be weakened: Do not claim approval-complete until live runs can
  pause durably, do not mark loop/subgraph complete before live executors
  exist, and do not claim stateful recovery before paused or reused live paths
  can continue without replaying ambiguous side effects.
- Next step: Step 14.1, Implement Live Durable Approval Pause And Resolution.

### 2026-07-17 - Step 14.1

- Completed: Enabled the live `human_approval` executor, preserved pending
  approval state through live run snapshots and manifests, returned live runs
  to `paused_for_review` instead of collapsing them into generic failure, and
  persisted approval resolution state through reload using the existing
  approval API without dispatching provider turns before human review.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`, and
  `apps/astrabridge-sidecar/tests/test_node_type_registry.py`.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py
  apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py
  apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py
  apps/astrabridge-sidecar/tests/test_node_type_registry.py` passed; with
  `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`, `python
  -m unittest
  apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_registry_snapshot_contains_initial_public_types_and_aliases
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_human_approval_pauses_and_resolution_persists_after_reload
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_local_executor_runs_without_provider_turn_dispatch
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_mcp_resource_executor_runs_without_provider_turn_dispatch
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_executes_agent_mcp_transform_router_and_selected_sink
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_artifact_source_fails_closed_on_digest_mismatch
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_preflight_blocks_all_dispatch_when_any_node_route_is_incomplete`
  passed 7/7.
- Process hygiene: Ran read-only `python`/`node`/`cmd` process audits before
  and after the Step 14.1 work and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap in this round.
- Blockers: None.
- Next step: Step 14.2, Implement Loop And Subgraph Live Executors.

### 2026-07-17 - Durable Handoff Audit

- Evidence inspected: this execution plan's authority, execution-rules, current-progress,
  current-work-unit, numbered-step, and append-only progress-log sections.
- Diagnosis: No parallel handoff file is needed. This file already satisfies the
  durable multi-turn handoff role for the current product direction: one
  authoritative execution source, one active work unit, explicit adjustment and
  evidence-review rules, bounded numbered steps with acceptance criteria, and an
  unambiguous next entry point.
- Route change: None. Preserved this file as the only active stability and
  interoperability scheduler, and kept the next execution entry on Step 14.2
  instead of spawning a second planning artifact.
- What must not be weakened: Do not create a second active handoff or execution
  plan for the same scope, do not turn execution-trigger turns into plan-only
  prose once a valid durable plan already exists, and do not discard validated
  completed-step evidence during future plan-document resets.
- Next step: Step 14.2, Implement Loop And Subgraph Live Executors.

### Friday, July 17, 2026 - Step 14.2

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`.
- Work completed: promoted `loop` and `subgraph` live executor availability in
  the registry; landed bounded live loop execution with persisted checkpoint
  state, cancellation/timeout enforcement, and typed result projection; landed
  live subgraph execution with child-run pinning, seeded typed entry injection,
  isolated child trace context, and projected terminal outputs wired back into
  the parent run.
- Validation: `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`,
  `python -m unittest
  apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_registry_snapshot_contains_initial_public_types_and_aliases
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_loop_persists_checkpointed_iteration_state
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_subgraph_executes_child_run_with_seeded_typed_input`
  passed 3/3; the broader focused regression command covering approval pause,
  local executor, MCP resource executor, agent/MCP/transform/router/sink,
  artifact-source digest failure, preflight route blocking, and the new
  loop/subgraph tests passed 9/9.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and found no clearly attributable stale
  AstraBridge-owned listeners or launcher wrappers to reap safely.
- Blockers: None.
- Next step: Step 14.3, Extend Live Recovery, Resume, And Reuse Semantics.

### Friday, July 17, 2026 - Step 14.3

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`.
- Work completed: landed restart-safe live approval continuation so approval
  pause no longer prematurely blocks downstream nodes; taught same-run resume to
  reload the latest full run rather than stale compact projections; preserved
  updated worker bindings and handoff lineage in live manifest snapshots; added
  explicit recovery-time handoff rebinding so reused outputs become new-run
  envelopes with fresh delivery identities; and kept ambiguous non-idempotent
  live replays fail-closed behind `needs_review`.
- Validation: `python -m unittest
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_resume_run_continues_after_approval_resolution
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_rerun_selected_nodes_reuses_safe_completed_outputs
  apps.astrabridge-sidecar.tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_selected_rerun_marks_artifact_sink_replay_needs_review`
  passed 3/3.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped
  within this execution slice.
- Blockers: None for Step 14.3. One older approval-pause test still exposes a
  separate graph-contract/output-contract mismatch in repository baseline and
  was kept out of this step's validation set because it is not part of the live
  recovery/resume/reuse acceptance path.
- Next step: Step 15, Converge Graph Definitions, Revisions, And Version
  Migrations.

### Friday, July 17, 2026 - Step 15 Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`, and this plan's Step
  15 control surface.
- Diagnosis: Step 15 bundled three separate engineering seams into one overly
  broad execution step: canonical graph persistence, graph-document
  migration/compatibility evidence, and conflict-preserving concurrent edit
  handling. That shape made one-step-per-round execution ambiguous and would
  have mixed route-finding with implementation.
- Route change: split Step 15 into 15.1 canonical graph documents and revision
  tokens, 15.2 graph-document migration/compatibility/rollback preview, and
  15.3 non-conflicting concurrent edit preservation. This is a structure
  refinement only; it preserves the original Step 15 objective and acceptance
  bar.
- What must not be weakened: do not let TaskGraph become a writable authority
  again, do not replace structured conflict handling with silent overwrite, and
  do not claim migration completion before versioned graph-document evidence is
  durable and rollback-inspectable.
- Next step: Step 15.1, Establish Canonical Graph Documents And Revision Tokens.

### Friday, July 17, 2026 - Step 15.1

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`.
- Work completed: added a canonical graph-document layer with persisted
  revision id/index/ETag metadata on graph records; routed
  save/import/node/edge/rollback writes through canonical document-backed graph
  metadata; failed stale graph mutations closed with structured 409 revision
  conflicts; and migrated legacy graph records to the new graph-document shape
  on read without causing read-path revision churn. Closed the remaining HTTP
  regression coverage by requiring revision tokens on rollback/import fixture
  API calls, fixing compiled fixture artifact lineage to use actual entry-node
  ids instead of stringified-list characters, and persisting the full compiled
  plan shape rather than a summary-only projection so durable protocol writes
  stay schema-complete.
- Validation: `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`,
  `python -m unittest
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_orchestration_sync_promotes_reachable_drafts_and_prunes_disconnected_records
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_export_import_reexport_round_trip_preserves_canonical_orchestration_fields
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_comfyui_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_comfyui_format
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_langgraph_format
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_snapshot_diff_and_rollback_resolve_snapshot_artifacts_from_task_project_workspace
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_graph_save_promotes_canonical_graph_document_metadata
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_update_graph_node_rejects_stale_expected_revision
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_legacy_graph_definition_is_migrated_to_graph_document_on_read
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_http_api_lists_templates_instantiates_graph_and_updates_node_and_edge`
  passed 9/9.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 15.1.
- Next step: Step 15.2, Add Graph-Document Migration Chains, Compatibility
  Ranges, And Rollback Preview.

### Friday, July 17, 2026 - Step 15.2

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`.
- Work completed: normalized graph-document compatibility ranges into explicit
  document/task-graph/orchestration consumer contracts; kept migration state
  stable across repeated reads and no-op saves; persisted graph-document
  evidence into snapshot manifests and dedicated `graph_document_json`
  artifacts; and surfaced rollback-preview evidence from snapshot diff and
  rollback responses so document schema version, migration origin, compatibility
  mode, and compatibility ranges are inspectable before and during restore.
- Validation: `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`,
  `python -m unittest
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_orchestration_sync_promotes_reachable_drafts_and_prunes_disconnected_records
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_export_import_reexport_round_trip_preserves_canonical_orchestration_fields
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_comfyui_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_comfyui_format
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_langgraph_format
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_snapshot_diff_and_rollback_resolve_snapshot_artifacts_from_task_project_workspace
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_graph_save_promotes_canonical_graph_document_metadata
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_graph_document_compatibility_ranges_stay_stable_across_noop_save
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_update_graph_node_rejects_stale_expected_revision
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_legacy_graph_definition_is_migrated_to_graph_document_on_read
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_snapshot_and_rollback_preview_surface_graph_document_evidence
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_http_api_lists_templates_instantiates_graph_and_updates_node_and_edge`
  passed 11/11.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 15.2.
- Next step: Step 15.3, Preserve Non-Conflicting Edits During Revision
  Conflicts.

### Friday, July 17, 2026 - Step 15.3

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`.
- Work completed: replaced fail-closed stale-write handling with canonical
  graph-document-aware three-way merge helpers for node, edge, whole-graph, and
  orchestration import edits; resolved non-overlapping task-graph and
  orchestration-backed compatibility edits against the latest graph state;
  normalized canonical graph nodes/edges into conflict surfaces so import-side
  routing changes can merge independently from concurrent GUI layout edits; and
  expanded `graph_revision_conflict` payloads with base/current/incoming edit
  sections, snapshot provenance, merge status, and overlapping-path evidence
  when deterministic preservation is not possible.
- Validation: `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`,
  `python -m unittest
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_orchestration_sync_promotes_reachable_drafts_and_prunes_disconnected_records
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_export_import_reexport_round_trip_preserves_canonical_orchestration_fields
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_comfyui_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_comfyui_format
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_langgraph_format
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_snapshot_diff_and_rollback_resolve_snapshot_artifacts_from_task_project_workspace
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_graph_save_promotes_canonical_graph_document_metadata
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_graph_document_compatibility_ranges_stay_stable_across_noop_save
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_update_graph_node_rejects_stale_expected_revision
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_update_graph_node_preserves_non_conflicting_stale_layout_edit
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_save_graph_definition_preserves_non_conflicting_policy_and_edge_edits
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_overlapping_stale_node_edit_fails_with_base_current_incoming_payload
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_legacy_graph_definition_is_migrated_to_graph_document_on_read
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_snapshot_and_rollback_preview_surface_graph_document_evidence
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_import_graph_from_orchestration_file_preserves_non_conflicting_stale_import_edit
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_http_api_lists_templates_instantiates_graph_and_updates_node_and_edge`
  passed 15/15.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 15.3.
- Next step: Step 16, Ship Python And TypeScript Code-Orchestration SDKs.

### Friday, July 17, 2026 - Durable Plan Refresh

- Evidence inspected: `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  especially the plan authority, execution rules, current progress, current
  work unit, Step 16 scope, and append-only progress log.
- Diagnosis: the repository already has one valid durable handoff artifact for
  this product line. A second handoff file would create a competing scheduler
  without adding execution clarity.
- Route change: none. Preserved this file as the single active stability and
  interoperability execution plan, kept the current work unit on
  `STAB-16-CODE-ORCHESTRATION-SDK-FOUNDATION`, and kept the execution entry
  point on Step 16.
- What must not be weakened: do not create a parallel active plan for the same
  scope, do not turn Step 16 execution into plan-only churn once implementation
  resumes, and do not discard the completed Step 0-15.3 evidence chain during a
  later plan-document reset.
- Next step: Step 16, Ship Python And TypeScript Code-Orchestration SDKs.

### Friday, July 17, 2026 - Step 16 Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py`, and
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`.
- Diagnosis: the original Step 16 bundled four distinct deliverables into one
  step: Python SDK foundation, TypeScript parity, source-ownership/detach
  enforcement, and full run/export/round-trip closure. Repository evidence
  showed the first missing executable seam was the Python-side code-authored
  entry path, while TypeScript parity and GUI detach protection remain separate
  owners.
- Route change: split Step 16 into 16.1 Python SDK foundation and source-owned
  canonical emission, 16.2 TypeScript builder parity, 16.3 source maps and GUI
  detached-edit protection, and 16.4 run/export/round-trip closure. This is a
  step-structure refinement only; it preserves the original Step 16 objective
  and acceptance bar.
- What must not be weakened: do not introduce a parallel graph schema, do not
  claim Python/TypeScript parity before shared fixtures prove it, and do not
  treat compatibility-projection rewrites as source-ownership protection.
- Next step: Step 16.1, Land The Python SDK Foundation And Deterministic
  Source-Owned Canonical Emission.

### Friday, July 17, 2026 - Step 16.1

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_sdk.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_sdk.py`, and
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py`.
- Work completed: landed a typed Python SDK foundation for source-owned
  canonical graph authoring with deterministic JSON emission, compile/lower
  convenience methods, and file output; added a dedicated `compile`
  CLI/report path for canonical graph files; fixed the source-owned graph file
  format so parse/load/write round trips no longer inject validator-derived
  node-type registry fields into authored graph artifacts; and proved
  SDK-authored graphs can compile, lower, and import through the current
  task-service compatibility path while explicitly preserving the known import
  projection delta in tests instead of hiding it.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py
  apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_sdk.py
  apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_checks.py
  apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_file_format.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_compiler.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_sdk.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py` passed;
  with `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`,
  `python -m unittest
  apps.astrabridge-sidecar.tests.test_agent_orchestration_file_format
  apps.astrabridge-sidecar.tests.test_agent_orchestration_compiler
  apps.astrabridge-sidecar.tests.test_agent_orchestration_sdk
  apps.astrabridge-sidecar.tests.test_agent_orchestration_checks`
  passed 27/27.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 16.1.
- Next step: Step 16.2, Add The TypeScript SDK Canonical Builder And
  Cross-Language Fixture Parity.

### Friday, July 17, 2026 - Step 16.2

- Files changed: `apps/astrabridge-desktop/src/features/runtime/agentOrchestrationSdk.ts`,
  `apps/astrabridge-desktop/src/features/runtime/agentOrchestrationSdk.test.ts`,
  `apps/astrabridge-desktop/src/features/runtime/fixtures/customBlankGraph.fromTs.json`,
  and `apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py`.
- Work completed: landed the first Desktop-side TypeScript orchestration SDK
  builder surface reusing the current `AgentOrchestrationGraph` type; authored
  a shared TypeScript fixture for `custom_blank_graph`; proved the builder emits
  deterministic source-owned canonical JSON matching the shared fixture; and
  added sidecar compile/diff evidence showing the existing canonical
  compile/diff paths accept the TypeScript-authored fixture without any
  TypeScript-specific adapter branch.
- Validation: in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/agentOrchestrationSdk.test.ts` passed 2/2; with
  `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`, `python
  -m unittest apps.astrabridge-sidecar.tests.test_agent_orchestration_checks`
  passed 11/11, including the new compile/diff proof over the
  TypeScript-authored fixture.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 16.2.
- Next step: Step 16.3, Add Source Maps, Code Ownership, And GUI
  Detached-Edit Protection.

### Friday, July 17, 2026 - Step 16.3

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  `apps/astrabridge-desktop/src/types.ts`,
  `apps/astrabridge-desktop/src/api.ts`,
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`, and
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`.
- Work completed: attached normalized source-ownership metadata to
  code-authored canonical orchestration graphs; exposed source-owned versus
  detached-GUI-edit evidence through graph-document/API summaries; blocked GUI
  save, node update, edge update, and rollback mutations against source-owned
  graphs unless the caller explicitly requests detach; surfaced the new
  ownership state in the Desktop graph workspace with an explicit detach action;
  and added backend/UI regression coverage proving the fail-closed behavior and
  detached-edit escape hatch.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py
  apps/astrabridge-sidecar/astrabridge_sidecar/server.py
  apps/astrabridge-sidecar/tests/test_task_graph_api.py` passed; with
  `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`, `python
  -m unittest
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_imported_source_owned_graph_blocks_gui_mutations_until_detached`
  passed 1/1; in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/TaskGraphWorkspace.test.tsx
  src/features/runtime/agentOrchestrationSdk.test.ts` passed 88/88.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 16.3.
- Next step: Step 16.4, Add Run, Inspect, Export, And Round-Trip Parity Across
  Python And TypeScript.

### Friday, July 17, 2026 - Step 16.4

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_sdk.py`,
  `apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py`, and
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`.
- Work completed: closed the SDK/runtime parity gap by teaching legacy
  task-graph dry-run compatibility checks to accept structured machine-result
  outputs from source-authored canonical graphs without forcing synthetic
  artifact outputs into the canonical export; added direct Python-versus-
  TypeScript canonical fixture identity coverage; proved the TypeScript fixture
  lint/compile/dry-run path at file level; and added an end-to-end task-service
  proof that a TypeScript-authored source-owned graph can import, open, dry-run,
  fixture-run, export, reload, re-import, and re-export with no semantic diff.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_sdk.py
  apps/astrabridge-sidecar/tests/test_agent_orchestration_checks.py
  apps/astrabridge-sidecar/tests/test_task_graph_api.py` passed; with
  `$env:ASTRABRIDGE_RUNTIME_ROOT='D:\AstraBridge\.tmp-runtime-tests'`, `python
  -m unittest
  apps.astrabridge-sidecar.tests.test_agent_orchestration_sdk
  apps.astrabridge-sidecar.tests.test_agent_orchestration_checks
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_typescript_sdk_fixture_survives_import_dry_run_fixture_run_export_reload_and_reimport
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_imported_source_owned_graph_blocks_gui_mutations_until_detached`
  passed 18/18; in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/agentOrchestrationSdk.test.ts
  src/features/runtime/TaskGraphWorkspace.test.tsx` passed 88/88.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 16.4.
- Next step: Step 17, Harden The GUI Editor, Live Debugger, And Deterministic
  E2E Path.

### Friday, July 17, 2026 - Step 17.1

- Plan review: Step 17 was too coarse to execute safely in one turn. Evidence
  inspected in `apps/astrabridge-desktop/src/App.tsx` and
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx` showed
  that cursor-based event stream reconnect logic already exists, but the canvas
  still lacked any dedicated mutation command log. The route was revised into
  Steps 17.1 through 17.4 so future turns can land one bounded editor/debugger
  slice at a time without weakening the overall Step 17 objective.
- Files changed: `apps/astrabridge-desktop/src/types.ts`,
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  and `apps/astrabridge-desktop/src/styles.css`.
- Work completed: added a Desktop-side canvas command-log foundation that
  records current graph mutations for node create/move/save, edge create/save/
  delete, and source-ownership detach; surfaced the log in the run inspection
  workspace with pending/applied/failed state; and added UI coverage proving
  the new operator-visibility surface coexists with the existing run workspace.
- Validation: in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/TaskGraphWorkspace.test.tsx` passed 87/87.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 17.1.
- Next step: Step 17.2, Add Destructive Edit History, Node Deletion, And
  Undo/Redo Safety.

### Friday, July 17, 2026 - Step 17.2

- Files changed: `apps/astrabridge-desktop/src/types.ts`,
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphFallbackState.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphFallbackState.test.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphEditHistory.ts`, and
  `apps/astrabridge-desktop/src/features/runtime/taskGraphEditHistory.test.ts`.
- Work completed: added deterministic fallback node deletion that prunes
  connected edges and rebinds entry-node ownership; introduced bounded local
  destructive-edit history with undo/redo transitions and selection snapshots;
  wired delete node plus undo/redo actions into the Desktop graph workspace and
  command-log surface; and added focused regression coverage for fallback graph
  pruning, edit-history state transitions, and workspace dispatch paths.
- Validation: in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/taskGraphFallbackState.test.ts
  src/features/runtime/taskGraphEditHistory.test.ts
  src/features/runtime/TaskGraphWorkspace.test.tsx` passed 98/98.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 17.2.
- Next step: Step 17.3, Add Live Debugger Visibility And Reconnectable Event
  Delivery.

### Friday, July 17, 2026 - Step 17.3 Plan Review

- Evidence inspected: `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  and this execution plan's current Step 17 scope.
- Diagnosis: repository evidence showed the current Desktop run workspace
  already has a reconnectable cursor-based stream foundation, but the
  remaining Step 17.3 scope still bundled two distinct execution owners:
  debugger visibility and reconnect proof. Keeping them together would make
  the next execution round too coarse for the one-step-per-round rule.
- Route change: refined Step 17.3 into Step 17.3.1 for live runtime visibility
  and Step 17.3.2 for cursor-based reconnect proof. This is a plan-structure
  refinement only; it preserves the original Step 17 objective and acceptance
  bar and keeps this file as the single active execution source.
- What must not be weakened: do not create a parallel plan for the same scope,
  do not replace runtime-backed debugger signals with placeholder UI state, and
  do not claim reconnect safety before cursor-based regression coverage proves
  no missing or duplicated durable events.
- Next step: Step 17.3.1, Add Live Runtime Visibility To The Debugger Surface.

### Friday, July 17, 2026 - Step 17.3.1

- Files changed: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  and `apps/astrabridge-desktop/src/styles.css`.
- Work completed: extended the latest-run debugger surface with a runtime-backed
  execution profile showing run mode, execution mode, scheduler, template,
  compatibility-shim state, and bounded concurrency signals; added selected
  timeline-event detail inspection for event type, status, timestamp, and
  artifact identity; and expanded focused Desktop coverage so the new debugger
  visibility survives the existing command log, approval, recovery, and run
  inspection surfaces without adding a parallel runtime state owner.
- Validation: in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/TaskGraphWorkspace.test.tsx` passed 89/89.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 17.3.1.
- Next step: Step 17.3.2, Prove Cursor-Based Reconnect Without Missing Or
  Duplicated Events.

### Friday, July 17, 2026 - Step 17.3.2

- Files changed: `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/runtimeEventCursor.ts`,
  `apps/astrabridge-desktop/src/features/runtime/runtimeEventCursor.test.ts`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, and
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`.
- Work completed: fixed the reconnect correctness seam by extracting a shared
  Desktop cursor-reconciliation helper for polling and SSE frames so stale or
  overlapping reconnect payloads no longer duplicate or rewind delivered
  events; tightened the App-side runtime stream and fallback polling path to
  accept only unseen cursor advances; and changed the Sidecar SSE runtime-event
  framing to emit per-event incremental cursors instead of stamping every event
  in a batch with the final tail cursor, which previously allowed mid-batch
  reconnects to skip unseen events.
- Validation: in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/runtimeEventCursor.test.ts` passed 4/4; in the
  repository root, `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/server.py` passed and `python
  -m unittest
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_sse_frame_formats_event_data_and_comment
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_event_sse_frames_increment_cursor_per_event`
  passed 2/2.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 17.3.2.
- Next step: Step 17.4, Add Large-Graph Performance Hardening, Accessibility,
  And Deterministic E2E.

### Friday, July 17, 2026 - Step 17.4 Plan Review

- Evidence inspected: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  `apps/astrabridge-desktop/playwright.config.ts`, and this execution plan's
  Step 17.4 scope.
- Diagnosis: repository evidence showed Step 17.4 still bundled three separate
  owners: modal/dialog accessibility, large-graph scale hardening, and
  deterministic Playwright E2E. Keeping them together would make the next
  execution rounds too coarse for the one-step-per-round rule.
- Route change: refined Step 17.4 into Step 17.4.1 for dialog focus and
  keyboard accessibility hardening, Step 17.4.2 for large-graph scale
  hardening, and Step 17.4.3 for deterministic task-graph Playwright E2E.
  This is a plan-structure refinement only; it preserves the original Step
  17.4 objective and acceptance bar.
- What must not be weakened: do not treat modal `aria-modal` markup as
  sufficient accessibility proof without focus management, do not claim
  large-graph scale safety without concrete rendering-path hardening, and do
  not claim deterministic E2E before the task-graph path is actually covered by
  Playwright.
- Next step: Step 17.4.1, Add Dialog Focus And Keyboard Accessibility
  Hardening.

### Friday, July 17, 2026 - Step 17.4.1

- Files changed: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`
  and `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`.
- Work completed: added bounded focus-management and keyboard hardening for the
  task-graph template browser and inspector dialogs by moving focus into the
  modal on open, restoring focus to the trigger on close, and trapping Tab
  navigation within the dialog surface; preserved the existing editor/debugger
  state model and Escape-close behavior; and expanded focused Desktop coverage
  so these keyboard flows remain protected against regression.
- Validation: in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/TaskGraphWorkspace.test.tsx` passed 91/91.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 17.4.1.
- Next step: Step 17.4.2, Add Large-Graph Scale Hardening.

### Friday, July 17, 2026 - Step 17.4.2

- Files changed: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphViewportCulling.ts`,
  and `apps/astrabridge-desktop/src/features/runtime/taskGraphViewportCulling.test.ts`.
- Work completed: added bounded large-graph scale hardening by deriving the
  visible stage viewport from canvas scroll/size/scale, culling offscreen node,
  edge, and edge-chip rendering, and preserving selected, dragged, hovered, and
  run-highlighted graph elements so existing editor and debugger interactions
  remain intact while the canvas renders materially fewer elements for the
  validated offscreen path.
- Validation: in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed and `node
  ./node_modules/vitest/vitest.mjs run
  src/features/runtime/taskGraphViewportCulling.test.ts
  src/features/runtime/TaskGraphWorkspace.test.tsx` passed 94/94.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 17.4.2.
- Next step: Step 17.4.3, Add Deterministic Task-Graph Playwright E2E.

### Friday, July 17, 2026 - Step 17.4.3

- Files changed: `apps/astrabridge-desktop/package.json` and
  `apps/astrabridge-desktop/tests/task-graph-workspace.spec.ts`.
- Work completed: added a dedicated Desktop script for the bounded task-graph
  Playwright slice; authored a deterministic browser fixture that normalizes
  browser-sidecar proxy paths, seeds stable project/task/thread/graph/run
  state, covers task-graph entry, node selection, run-inspection, and approval
  resolution, and hardens the E2E path against locale-dependent topbar labels
  and collapsed run-inspection details.
- Validation: in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed; `node
  ./node_modules/@playwright/test/cli.js test tests/task-graph-workspace.spec.ts
  --project=desktop --reporter=line` passed via a manually hosted local Vite
  server with `1 passed (12.0s)`; and `apps/astrabridge-desktop/test-results/.last-run.json`
  recorded `"status": "passed"` with an empty `failedTests` list.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round. A temporary local Vite helper was launched only
  to avoid Playwright web-server teardown hangs during validation; no clearly
  attributable stale AstraBridge-owned listener or launcher wrapper was proven
  safe to reap beyond that bounded helper flow in this execution slice.
- Blockers: None for Step 17.4.3. The browser run surfaced an existing React
  duplicate-key warning inside `TaskGraphWorkspace`, but it did not prevent the
  deterministic E2E path from passing and is not a blocker for this step's
  acceptance criteria.
- Next step: Step 18, Implement Signed Desktop And Sidecar Updates With Release
  Channels.

### Saturday, July 18, 2026 - Step 18 Plan Review

- Evidence inspected: `release/astrabridge-release-identity.json`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py`,
  `apps/astrabridge-desktop/src-tauri/tauri.conf.json`,
  `apps/astrabridge-desktop/src-tauri/src/main.rs`, and
  `docs/RELEASE_CHECKLIST.md`.
- Diagnosis: repository evidence showed the original Step 18 still bundled four
  distinct owners: updater channel contract/gate validation, Tauri signed
  updater wiring, bundled Sidecar packaging, and isolated Windows
  installation/update validation. Keeping them together would make the next
  execution rounds too coarse for the one-step-per-round rule.
- Route change: refined Step 18 into Step 18.1 for explicit updater channel
  contract and gate validation, Step 18.2 for signed Tauri updater
  configuration, Step 18.3 for bundled version-matched Sidecar release
  packaging, and Step 18.4 for channel selection, kill-switch surfacing, and
  isolated Windows update validation. This is a plan-structure refinement only;
  it preserves the original Step 18 objective and acceptance bar.
- What must not be weakened: do not treat staged manifest generation as a
  substitute for signed Desktop updater wiring, do not keep formal packages on
  a source/script Sidecar fallback path, and do not claim explicit
  stable/beta/canary support before channel selection and isolated update
  validation are real.
- Next step: Step 18.1, Establish Explicit Updater Channel Contract And Gate
  Validation.

### Saturday, July 18, 2026 - Step 18.1

- Files changed: `release/astrabridge-release-identity.json`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py`, and
  `apps/astrabridge-sidecar/tests/test_release_identity.py`.
- Work completed: upgraded the canonical release identity from a thin updater
  channel list to an explicit stable/beta/canary contract with deterministic
  per-channel endpoint metadata and a kill-switch manifest contract; taught the
  release-readiness gate to fail closed when required channel ids, manifest
  paths, endpoint template tokens, or kill-switch metadata are missing or
  malformed; and expanded staged updater artifact generation so release
  rehearsals now emit deterministic channel manifests plus a kill-switch
  manifest as first-class release evidence.
- Validation: in `apps/astrabridge-sidecar`, `python -m unittest
  tests.test_release_identity` passed 5/5; in the repository root, `python
  scripts/run_release_readiness_gate.py --run-id step18-1-updater-contract`
  passed with overall `"status": "pass"`, including `binding_evaluation`,
  `updater_contract`, `stage_a`, `stage_b`, `deterministic_comparison`, and
  `staged_binding_evaluation`; and the preserved evidence under
  `PRIVATE/release-readiness/step18-1-updater-contract/` recorded deterministic
  staged updater manifests for `stable`, `beta`, `canary`, and
  `kill-switch.json`.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 18.1.
- Next step: Step 18.2, Integrate Signed Tauri Updater Configuration And
  Fail-Closed Endpoint Policy.

### Saturday, July 18, 2026 - Step 18.2

- Files changed: `release/astrabridge-release-identity.json`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py`,
  `apps/astrabridge-sidecar/tests/test_release_identity.py`,
  `apps/astrabridge-desktop/src-tauri/tauri.conf.json`,
  `apps/astrabridge-desktop/src-tauri/Cargo.toml`,
  `apps/astrabridge-desktop/src-tauri/Cargo.lock`,
  `apps/astrabridge-desktop/src-tauri/src/main.rs`,
  `apps/astrabridge-desktop/src-tauri/gen/schemas/acl-manifests.json`,
  `apps/astrabridge-desktop/src-tauri/gen/schemas/desktop-schema.json`, and
  `apps/astrabridge-desktop/src-tauri/gen/schemas/windows-schema.json`.
- Work completed: registered the Tauri updater plugin in the Desktop runtime;
  added explicit signed updater configuration with a canonical public key,
  channel-derived HTTPS endpoint template, deterministic updater-artifact
  generation, and safe Windows installer mode; bound the Desktop updater
  configuration to the canonical release identity in the release-readiness
  contract; and extended validation so dangerous insecure transport,
  certificate-bypass, or hostname-bypass updater flags remain fail-closed in
  the formal release path.
- Validation: in `apps/astrabridge-sidecar`, `python -m unittest
  tests.test_release_identity` passed 6/6; in the repository root, `python
  scripts/run_release_readiness_gate.py --run-id step18-2-tauri-updater-config`
  passed with overall `"status": "pass"`, including `binding_evaluation`,
  `updater_contract`, `stage_a`, `stage_b`, `deterministic_comparison`, and
  `staged_binding_evaluation`, with preserved evidence under
  `PRIVATE/release-readiness/step18-2-tauri-updater-config/`; and `cargo test
  --manifest-path D:\AstraBridge\apps\astrabridge-desktop\src-tauri\Cargo.toml`
  passed 7/7.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round and did not find a clearly attributable stale
  AstraBridge-owned listener or launcher wrapper that could be safely reaped in
  this execution slice.
- Blockers: None for Step 18.2.
- Next step: Step 18.3, Bundle Version-Matched Sidecar Releases And Remove
  Source Fallback From Formal Packages.

### Saturday, July 18, 2026 - Step 18.3

- Files changed: `release/astrabridge-release-identity.json`,
  `release/desktop-sidecar/windows-x64/astrabridge-sidecar/README.md`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py`,
  `apps/astrabridge-sidecar/tests/test_release_identity.py`,
  `apps/astrabridge-desktop/src-tauri/tauri.conf.json`,
  `apps/astrabridge-desktop/src-tauri/src/main.rs`, and
  `apps/astrabridge-desktop/src-tauri/src/sidecar_supervision.rs`.
- Work completed: replaced the formal-package Sidecar resource contract with a
  dedicated bundled runtime contract rooted under `release/desktop-sidecar/`;
  changed Desktop formal-package resolution so it now accepts only a bundled
  Python runtime plus version-matched Sidecar package/module launch and refuses
  legacy bundled script/source fallback; preserved current-source development
  behavior outside the formal package boundary; extended sidecar supervision so
  bundled Python/module launch arguments are explicit; and taught the
  release-readiness gate to generate a staged formal Sidecar bundle from the
  bundled Python runtime plus Sidecar package tree, strip editable-source
  markers, and fail closed on bundle drift.
- Validation: in `apps/astrabridge-sidecar`, `python -m unittest
  tests.test_release_identity` passed 8/8 and `python -m unittest
  tests.test_sidecar_origin_policy` passed 8/8; in the repository root, `cargo
  test --manifest-path
  D:\AstraBridge\apps\astrabridge-desktop\src-tauri\Cargo.toml` passed 9/9;
  and `python scripts/run_release_readiness_gate.py --artifact-root
  D:\AstraBridge\PRIVATE\rr18_3 --run-id step18-3` passed with overall
  `"status": "pass"`, including `binding_evaluation`, `updater_contract`,
  `stage_a`, `stage_b`, `deterministic_comparison`, and
  `staged_binding_evaluation`.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits at the
  start and end of the round. The initial listener audit via
  `Get-NetTCPConnection` was permission-blocked on this machine, so the final
  listener check used read-only `netstat`; it surfaced established external
  port-3000 connections but no clearly attributable stale AstraBridge-owned
  listener or launcher wrapper that could be safely reaped in this execution
  slice, so no manual kills were performed.
- Blockers: None for Step 18.3.
- Next step: Step 18.4, Add Explicit Channel Selection, Kill Switch
  Surfacing, And Isolated Windows Update Validation.

### Saturday, July 18, 2026 - Stability Hardening Plan Refresh

- Evidence inspected: this execution plan; `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`;
  `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md`;
  `docs/APP_STANDARDIZATION_UI_DOGFOOD_EVIDENCE.md`; and
  `apps/astrabridge-sidecar/astrabridge_sidecar/external_a2a_gateway.py`.
- Diagnosis: the active plan already covered the user's stated product
  direction, but repository evidence showed three remaining hardening lanes
  were still under-specified in future steps: track-separated automatic upgrade
  governance beyond the Desktop binary updater, degraded-authority and
  multimodal completion observability, and final closure evidence for external
  A2A negotiation plus GUI/code/import-export parity.
- Route change: refined the baseline evidence plus Steps 19, 20, and 23 so the
  plan now explicitly requires journaled apply/rollback tracks for provider
  metadata/capability routes/kernel/plugins-executors, fault/SLO evidence for
  warning-gated tool-call and multimodal no-final-answer lanes, and final
  negotiation/parity closure for external A2A plus ComfyUI/LangGraph bridges.
  This is a plan-document refresh only; no completed work was reset.
- What must not be weakened: do not create a second upgrade control plane, do
  not treat warning-gated capability routes as verified, do not hide multimodal
  completion failures behind generic UI timeouts, and do not claim broad A2A
  compatibility without explicit negotiation evidence.
- Next step: Step 18.4, Add Explicit Channel Selection, Kill Switch Surfacing,
  And Isolated Windows Update Validation.

### Saturday, July 18, 2026 - Step 18.4

- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py`,
  `apps/astrabridge-sidecar/tests/test_release_identity.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`,
  `apps/astrabridge-desktop/src/types.ts`,
  `apps/astrabridge-desktop/src/api.ts`,
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/styles.css`,
  `apps/astrabridge-desktop/src/features/updates/DesktopUpdatePanel.tsx`,
  `apps/astrabridge-desktop/src/features/updates/DesktopUpdatePanel.test.tsx`,
  `docs/RELEASE_CHECKLIST.md`, and
  `scripts/run_windows_update_rehearsal.py`.
- Work completed: added a dedicated Desktop update control surface that keeps
  product updater controls separate from the existing agentic update review
  panel; persisted explicit stable/beta/canary channel selection through
  project UI preferences with bounded normalization; surfaced updater contract,
  selected endpoint, kill-switch state, and formal-bundle readiness from the
  canonical `release_identity.py` owner through a new Sidecar runtime API; and
  added an isolated Windows update rehearsal owner plus script that runs the
  release-readiness gate, projects clean-install checks, records
  channel-aware activation, and preserves rollback pointer/manifests under
  `PRIVATE/release-readiness/`.
- Validation: `python -m py_compile
  apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py
  apps/astrabridge-sidecar/astrabridge_sidecar/server.py
  apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py
  scripts/run_windows_update_rehearsal.py` passed; in
  `apps/astrabridge-sidecar`, `python -m unittest tests.test_release_identity
  tests.test_sidecar_services.AstraBridgeServiceTests.test_handler_runtime_desktop_update_route_returns_status_projection
  tests.test_sidecar_services.AstraBridgeServiceTests.test_handler_runtime_desktop_update_rehearsal_route_runs_owner`
  passed 12/12; in `apps/astrabridge-desktop`, `node
  ./node_modules/typescript/bin/tsc --noEmit` passed, `node
  ./node_modules/vitest/vitest.mjs run
  src/features/updates/AgenticUpdateReviewPanel.test.tsx
  src/features/updates/DesktopUpdatePanel.test.tsx` passed 6/6, and `node
  ./node_modules/vite/bin/vite.js build` passed with the existing large-chunk
  warning still preserved as non-blocking build output; in the repository root,
  `python scripts/run_windows_update_rehearsal.py --run-id step18-4-local`
  passed with overall `"status": "pass"` and preserved evidence under
  `PRIVATE/release-readiness/step18-4-local/windows-update-rehearsal/`.
- Process hygiene: ran read-only `python`/`node`/`cmd` process audits and
  read-only listener checks via `netstat` at the start and end of the round.
  The machine still showed established external port-3000 connections but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 18.4.
- Next step: Step 19, Make Updates And Migrations Journaled, Atomic, And
  Rollback-Safe.

### Saturday, July 18, 2026 - Step 19.1

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py`,
  `apps/astrabridge-sidecar/tests/test_release_identity.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and the preserved Step 18.4 Windows
  update rehearsal evidence under `PRIVATE/release-readiness/step18-4-local/`.
- Route change: Step 19 was too broad to satisfy the one-step-per-round rule
  without weakening ownership boundaries, so it was split into Steps 19.1-19.5
  while keeping the original rollback, migration, and discovery-hardening bar
  intact. This is a plan-document refinement only; no validated prior work was
  reset.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/release_identity.py`,
  `apps/astrabridge-sidecar/tests/test_release_identity.py`, and this plan.
- Work completed: added a Desktop formal-bundle transaction journal foundation
  under `release_identity.py` with explicit stages for initialization, candidate
  staging, activation write, post-healthcheck commit, and rollback; added
  atomic generation-pointer writes plus interruption recovery that rolls back to
  the prior generation before healthcheck and commits the candidate generation
  after healthcheck; extended the Windows update rehearsal owner/report to
  preserve activation-journal and transaction-recovery artifacts; and
  strengthened focused tests to assert committed transaction state plus the
  rollback/commit recovery matrix.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\release_identity.py`
  passed; in `apps/astrabridge-sidecar`, `python -m unittest
  tests.test_release_identity` passed 10/10; and in the repository root,
  `python scripts/run_windows_update_rehearsal.py --run-id step19-1-local`
  passed with overall `"status": "pass"`, including committed transaction
  status, a 4-scenario `"status": "pass"` recovery matrix, rollback at
  `activation_written`, and post-healthcheck commit preservation under
  `PRIVATE/release-readiness/step19-1-local/windows-update-rehearsal/`.
- Process hygiene: ran read-only process audits at the start and end of the
  round. `Get-NetTCPConnection` remained permission-blocked on this machine, so
  listener inspection used read-only `netstat`; no clearly attributable stale
  AstraBridge-owned listener or launcher wrapper was identified, so no manual
  kills were performed.
- Blockers: None for Step 19.1.
- Next step: Step 19.2, Journal Provider Metadata And Capability Route Apply
  Tracks.

### Saturday, July 18, 2026 - Step 19.2

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/apply.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`, and
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/apply.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/artifacts.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/__init__.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`,
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`, and this plan.
- Work completed: extended the existing metadata-only apply owner into a
  shared track-aware apply journal contract that now supports provider metadata
  and capability-route changes inside one bounded isolated-apply owner; added a
  durable `apply/apply-journal.json` artifact with per-track source digest,
  staged digest, trust decision, health verdict, rollback target, and explicit
  history; preserved existing rollback-manifest ownership while wiring apply
  summaries to surface journal paths and track ids; added capability-route
  apply and mixed-track regression coverage; and failed closed on ambiguous
  capability-route payloads that do not declare a route record.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agentic_updates\apply.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agentic_update_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agentic_updates\artifacts.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agentic_update_service.py`
  passed; in `apps/astrabridge-sidecar`, `python -m unittest
  tests.test_agentic_update_artifacts tests.test_agentic_update_service`
  passed 27/27; and a preserved local evidence run written under
  `PRIVATE/agentic-update-pipeline/` passed with mixed metadata+capability
  apply/rollback plus explicit ambiguous-route rejection, recorded in
  `PRIVATE/agentic-update-pipeline/step19-2-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step19-2-local-summary.md`,
  `PRIVATE/agentic-update-pipeline/runs/step19-2-local-mixed/`, and
  `PRIVATE/agentic-update-pipeline/runs/step19-2-local-route-reject/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. The machine still showed unrelated long-lived
  local listeners and established proxy/SSH connections, but no clearly
  attributable stale AstraBridge-owned listener or launcher wrapper that could
  be safely reaped in this execution slice, so no manual kills were performed.
- Blockers: None for Step 19.2.
- Next step: Step 19.3, Journal Kernel, Plugin, Executor, And Runtime-Directory
  Activation.

### Saturday, July 18, 2026 - Step 19.3 Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/kernel_verify.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/codex_plugin_install_apply.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_kernel_verify.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`,
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`, and this execution plan's current
  Step 19.3 scope.
- Diagnosis: repository evidence showed Step 19.3 bundled three distinct owner
  tiers: kernel candidate verification/activation-gate evidence, plugin/skill
  install apply, and node-executor/runtime-directory activation. Keeping them
  together would violate the one-step-per-round rule and blur owner boundaries,
  because only the kernel path already had a bounded validation and rollback
  owner while plugin and executor/runtime activation still require separate
  adoption work.
- Route change: refined Step 19.3 into Step 19.3.1 for Codex kernel candidate
  activation-gate journaling, Step 19.3.2 for plugin/skill activation, and Step
  19.3.3 for node-executor plus runtime-directory activation. This is a
  plan-structure refinement only; it preserves the original Step 19.3
  objective, acceptance bar, and single-plan ownership.
- What must not be weakened: do not collapse kernel verification, plugin
  install, or executor/runtime activation into one ad-hoc state machine; do not
  skip rollback artifacts for verification-only lanes; and do not claim
  executor/runtime activation safety before the real owner surfaces are
  journaled and regression-covered.
- Next step: Step 19.3.1, Journal Codex Kernel Candidate Activation Gate
  Verification.

### Saturday, July 18, 2026 - Step 19.3.1

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/kernel_verify.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_kernel_verify.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`, and
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/kernel_verify.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_update_service.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_kernel_verify.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_service.py`,
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`, and this plan.
- Work completed: added a `codex_kernel_candidate` activation-gate journal on
  the shared apply-journal schema for kernel verification runs; preserved
  baseline locator state, staged verification digest, trust decision, health
  verdict, rollback target, and explicit committed versus rolled-back terminal
  history; wrote rollback manifests even for verification-only success runs so
  the restore path stays explicit; surfaced apply journal paths and track ids in
  preserved run summaries; and kept kernel verification side effects limited to
  bounded temporary binary override evidence instead of runtime promotion.
- Validation: `python -m unittest
  apps.astrabridge-sidecar.tests.test_agentic_update_kernel_verify
  apps.astrabridge-sidecar.tests.test_agentic_update_service` passed 22/22; and
  preserved local evidence under `PRIVATE/agentic-update-pipeline/` proved both
  committed and rolled-back kernel verification runs restore the readable
  runtime locator state, recorded in
  `PRIVATE/agentic-update-pipeline/step19-3-1-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step19-3-1-local-summary.md`,
  `PRIVATE/agentic-update-pipeline/runs/step19-3-1-local-kernel-pass/`, and
  `PRIVATE/agentic-update-pipeline/runs/step19-3-1-local-kernel-blocked/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  before and after the round. The machine still showed unrelated long-lived
  local listeners and established proxy/SSH connections, but no clearly
  attributable stale AstraBridge-owned listener or launcher wrapper that could
  be safely reaped in this execution slice, so no manual kills were performed.
- Blockers: None for Step 19.3.1.
- Next step: Step 19.3.2, Journal Plugin And Skill Activation.

### Saturday, July 18, 2026 - Step 19.3.2

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/codex_plugin_install_apply.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_codex_plugin_install_apply.py`, and the
  preserved plugin-install runtime evidence paths under `PRIVATE/demo-runs/`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/codex_plugin_install_apply.py`,
  `apps/astrabridge-sidecar/tests/test_codex_plugin_install_apply.py`, and this
  plan.
- Work completed: extended the plugin/skill install apply owner to write a
  shared-schema `apply-journal.json` with an explicit
  `plugin_skill_activation` track; preserved source and staged digests, trust
  decision, health verdict, changed paths, rollback target, and terminal
  committed versus rolled-back history; added a bounded plugin-install
  rollback manifest beside the execution report; kept rollback snapshot capture
  and restore ownership in the same apply owner instead of introducing a second
  state machine; and preserved artifact paths directly in the execution result
  so runtime callers can audit the activation record.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\codex_plugin_install_apply.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_codex_plugin_install_apply.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_codex_plugin_install_apply` passed 8/8;
  and preserved local evidence under `PRIVATE/agentic-update-pipeline/` plus
  the referenced `PRIVATE/demo-runs/` execution artifacts proved both a
  committed plugin update and a rolled-back failed apply restore the readable
  isolated-runtime plugin state, recorded in
  `PRIVATE/agentic-update-pipeline/step19-3-2-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step19-3-2-local-summary.md`,
  `PRIVATE/demo-runs/plugin-install-20260718T114009579637-6aab84/`, and
  `PRIVATE/demo-runs/plugin-install-20260718T114009858902-921cf4/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. The machine still showed unrelated long-lived
  local listeners and established proxy/SSH connections, but no clearly
  attributable stale AstraBridge-owned listener or launcher wrapper that could
  be safely reaped in this execution slice, so no manual kills were performed.
- Blockers: None for Step 19.3.2.
- Next step: Step 19.3.3, Journal Node-Executor And Runtime-Directory
  Activation.

### Saturday, July 18, 2026 - Step 19.3.3 Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_project_runtime_activation.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`,
  `docs/ARCHITECTURE.md`, `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and this
  execution plan's current Step 19.3.3 scope.
- Diagnosis: repository evidence showed the runtime-directory activation owner
  is concrete and writable in `project_service.py`, but the node-executor side
  currently exposes a canonical registry and live-run compatibility owner rather
  than a parallel install/apply owner. Keeping both in one round would violate
  the one-step-per-round rule and risk inventing a second executor state
  machine.
- Route change: refined Step 19.3.3 into Step 19.3.3.1 for
  runtime-directory activation journaling and Step 19.3.3.2 for node-executor
  activation journaling. This is a plan-structure refinement only; it preserves
  the original Step 19.3.3 objective, acceptance bar, and single-plan
  ownership.
- What must not be weakened: do not move runtime-directory writes out of
  `project_service.py`; do not treat node-type registry projection reads as an
  install/apply owner unless the real activation seam is proved; and do not
  create a second executor-availability table or local registry shadow merely
  to make journaling easier.
- Next step: Step 19.3.3.1, Journal Runtime-Directory Activation.

### Saturday, July 18, 2026 - Step 19.3.3.1

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py`,
  `apps/astrabridge-sidecar/tests/test_project_runtime_activation.py`, and
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py`,
  `apps/astrabridge-sidecar/tests/test_project_runtime_activation.py`, and this
  plan.
- Work completed: added a workspace-local runtime activation journal and
  rollback manifest around the real runtime-directory activation owner in
  `project_service.py`; preserved source digest, staged digest, trust decision,
  health verdict, changed paths, rollback target, and explicit committed versus
  rolled-back terminal history for runtime-root creation plus
  `storage_policy.json` writes; and added rollback logic that restores the prior
  readable storage-policy state and removes newly introduced isolated runtime
  subroots on failure instead of leaving a partial activation behind.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\project_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_project_runtime_activation.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_project_runtime_activation
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_project_create_and_duplicate_workspace_guard
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_project_create_new_without_paths_defaults_to_isolated_runtime_bundle
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_project_create_distinct_projects_get_distinct_isolated_runtime_roots`
  passed 5/5; and preserved local evidence under `PRIVATE/agentic-update-pipeline/`
  plus `PRIVATE/runtime-directory-activation/` proved both a committed and a
  rolled-back runtime-directory activation path, recorded in
  `PRIVATE/agentic-update-pipeline/step19-3-3-1-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step19-3-3-1-local-summary.md`,
  `PRIVATE/runtime-directory-activation/success/`, and
  `PRIVATE/runtime-directory-activation/failure/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners and established proxy/SSH connections, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 19.3.3.1.
- Next step: Step 19.3.3.2, Journal Node-Executor Activation.

### Saturday, July 18, 2026 - Step 19.3.3.2

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_executor_activation_integration.py`, and
  the preserved executor-activation workspaces under `PRIVATE/executor-activation/`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/node_type_registry.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_node_type_registry.py`,
  `apps/astrabridge-sidecar/tests/test_executor_activation_integration.py`, and
  this plan.
- Work completed: promoted the canonical node-executor compatibility owner into
  a journaled activation gate by adding a shared-schema executor-activation
  journal plus rollback manifest around
  `compiled_plan_executor_capability_report(...)`; preserved prior committed
  executor pointer state so stale-registry or unavailable-executor failures do
  not advance the current readable activation snapshot; and rewired the current
  task-service and runtime-service dry-run/live-run compatibility call sites to
  consume the same journaled owner instead of bypassing it.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\node_type_registry.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\task_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_node_type_registry.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_executor_activation_integration.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_journaled_executor_activation_commits_and_updates_current_pointer
  apps.astrabridge-sidecar.tests.test_node_type_registry.NodeTypeRegistryTests.test_journaled_executor_activation_failure_preserves_previous_pointer
  apps.astrabridge-sidecar.tests.test_executor_activation_integration
  apps.astrabridge-sidecar.tests.test_project_runtime_activation`
  passed 6/6; and preserved local evidence under `PRIVATE/agentic-update-pipeline/`
  plus `PRIVATE/executor-activation/` proved both a committed and a rolled-back
  node-executor activation path while preserving the prior current pointer,
  recorded in
  `PRIVATE/agentic-update-pipeline/step19-3-3-2-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step19-3-3-2-local-summary.md`,
  `PRIVATE/executor-activation/success/`, and
  `PRIVATE/executor-activation/failure/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners and established proxy/SSH connections, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 19.3.3.2.
- Next step: Step 19.4, Add SQLite Migration Transactions, Backups, And
  Readback Guarantees.

### Saturday, July 18, 2026 - Step 19.4 Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py`,
  `apps/astrabridge-sidecar/tests/test_durable_run_store.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and this execution plan's current
  Step 19.4 scope.
- Diagnosis: repository evidence showed the real SQLite durable-state owner is
  `DurableRunEventStore.initialize()` plus the existing legacy-import metadata
  lane in `durable_run_store.py`, while `task_service.py` only owns graph
  document migrations and preview snapshots. Keeping old/empty/damaged/future-version
  handling plus rollback/readback proof in one round would violate the
  one-step-per-round rule and risk inventing a parallel migration owner.
- Route change: refined Step 19.4 into Step 19.4.1 for transactional store
  bootstrap, revision guards, and backup journals; and Step 19.4.2 for
  rollback/readback proof across persisted durable state. This preserves the
  original Step 19.4 objective, acceptance bar, and single-owner boundary.
- What must not be weakened: do not move SQLite bootstrap ownership out of
  `durable_run_store.py`; do not add a second migration table or graph-layer
  recovery owner just to satisfy upgrade evidence; and do not silently repair a
  damaged or future-version database without preserving a backup and explicit
  recovery entry point.
- Next step: Step 19.4.1, Add Transactional Store Bootstrap, Revision Guard,
  And Backup Journals.

### Saturday, July 18, 2026 - Step 19.4.1

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py`,
  `apps/astrabridge-sidecar/tests/test_durable_run_store.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and the preserved durable-run-store
  initialization workspaces under `PRIVATE/sqlite-migration-init/`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py`,
  `apps/astrabridge-sidecar/tests/test_durable_run_store.py`, and this plan.
- Work completed: added a durable-run-store preflight probe that classifies
  empty, old, current, damaged, and future-version SQLite states; stamped the
  real bootstrap owner with a concrete `PRAGMA user_version` revision guard and
  explicit transactional schema apply; preserved workspace-local migration
  reports under `.astrabridge/durable-run-store-migrations/`; and preserved raw
  SQLite backup snapshots under `.astrabridge/durable-run-store-backups/` for
  old, damaged, and future-version initialization paths so the recovery entry
  point remains explicit instead of silently rebuilding state.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\durable_run_store.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_durable_run_store.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_durable_run_store` passed 14/14; and
  preserved local evidence under `PRIVATE/agentic-update-pipeline/` plus
  `PRIVATE/sqlite-migration-init/` captured committed old-store upgrade,
  blocked future-version, and blocked damaged-store initialization outcomes in
  `PRIVATE/agentic-update-pipeline/step19-4-1-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step19-4-1-local-summary.md`,
  `PRIVATE/sqlite-migration-init/old-success/`,
  `PRIVATE/sqlite-migration-init/future-version/`, and
  `PRIVATE/sqlite-migration-init/damaged/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners and established proxy/SSH connections, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 19.4.1.
- Next step: Step 19.4.2, Prove Rollback And Readback Across Persisted Durable
  State.

### Saturday, July 18, 2026 - Step 19.4.2

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py`,
  `apps/astrabridge-sidecar/tests/test_durable_run_store.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and the preserved initialization
  evidence under `PRIVATE/sqlite-migration-init/`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/durable_run_store.py`,
  `apps/astrabridge-sidecar/tests/test_durable_run_store.py`, and this plan.
- Work completed: extended the real durable-run-store owner to write a
  readback artifact beside each preserved SQLite migration report; reused the
  same owner to inspect backup snapshots and prove which runs, graph ids, and
  provider-facing agent-envelope references remain readable after blocked
  future-version and rolled-back initialization outcomes; taught projection
  rebuild to tolerate partial historical table sets during backup inspection
  instead of inventing a second recovery/import path; and kept damaged-store
  handling fail-closed by preserving an explicit blocked readback artifact when
  the snapshot itself is unreadable.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\durable_run_store.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_durable_run_store.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_durable_run_store` passed 15/15; and
  preserved local evidence under `PRIVATE/agentic-update-pipeline/` plus
  `PRIVATE/sqlite-migration-readback/step19-4-2/` captured committed old-store
  upgrade, blocked future-version, rolled-back schema-apply failure, and
  blocked damaged-store readback outcomes in
  `PRIVATE/agentic-update-pipeline/step19-4-2-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step19-4-2-local-summary.md`, and the
  referenced per-case workspaces under
  `PRIVATE/sqlite-migration-readback/step19-4-2/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. A final end-of-round audit showed the same
  unrelated long-lived local listeners and proxy/SSH connections, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 19.4.2.
- Next step: Step 19.5, Harden Update Discovery Against Redirect, SSRF, Type,
  Size, And Replay Abuse.

### Saturday, July 18, 2026 - Step 19.5

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/discovery.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_discovery.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_parsers.py`, and
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/discovery.py`,
  `apps/astrabridge-sidecar/tests/test_agentic_update_discovery.py`, and this
  plan.
- Work completed: hardened the real update-discovery owner in
  `agentic_updates/discovery.py` to fail closed on private/local source URLs,
  wrong-host responses, redirects away from the requested official source URL,
  unsupported non-text discovery content types, oversized payloads, compressed
  responses, and replayed source identities inside the same discovery run;
  preserved rejection evidence in the same source-pack contract instead of
  inventing a second discovery ledger; and kept safe-source compatibility by
  preserving the existing discovery artifact shape for accepted official text
  sources.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\agentic_updates\discovery.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agentic_update_discovery.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_agentic_update_parsers.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_agentic_update_discovery
  apps.astrabridge-sidecar.tests.test_agentic_update_parsers` passed 13/13;
  and preserved local evidence under `PRIVATE/agentic-update-pipeline/` plus
  `PRIVATE/update-discovery-hardening/step19-5/` captured both a safe
  discovery pass and an unsafe-source rejection matrix in
  `PRIVATE/agentic-update-pipeline/step19-5-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step19-5-local-summary.md`, and the
  referenced safe/unsafe per-case workspaces under
  `PRIVATE/update-discovery-hardening/step19-5/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners and proxy/SSH connections, but no clearly
  attributable stale AstraBridge-owned listener or launcher wrapper that could
  be safely reaped in this execution slice, so no manual kills were performed.
- Blockers: None for Step 19.5.
- Next step: Step 20, Persist Operational SLOs, Support Bundles, And System
  Fault Evidence.

### Saturday, July 18, 2026 - Step 20 Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_observability.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and this execution plan's current
  Step 20 scope.
- Diagnosis: repository evidence showed Step 20 spans at least three concrete
  owner lanes: runtime-observability window persistence, degraded-authority and
  multimodal quality persistence, and stability/support-bundle fault evidence.
  Landing all of that in one round would violate the one-step-per-round rule
  and create pressure to invent parallel observability or support-bundle
  owners.
- Route change: refined Step 20 into Step 20.1 for windowed core reliability
  metrics and unknown-SLO gates, Step 20.2 for degraded-authority and
  multimodal quality signals, Step 20.3 for redacted support bundles, and Step
  20.4 for fault-matrix/release evidence closure. This preserves the original
  Step 20 objective and acceptance bar while matching the real owner
  boundaries.
- What must not be weakened: do not create a second observability store, do
  not hide warning-gated or downgraded routes inside cosmetic UI state, and do
  not merge support-bundle ownership into the fault matrix merely to shorten
  the execution queue.
- Next step: Step 20.1, Persist Windowed Core Reliability Metrics And
  Unknown-SLO Gates.

### Saturday, July 18, 2026 - Step 20.1

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_observability.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and the preserved local workspace
  under `PRIVATE/observability-window-slos/step20-1/`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_observability.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`, and this plan.
- Work completed: extended the real runtime-observability owner to emit bounded
  5m/1h/24h windows, minimum sample metadata, burn-rate alerts, and
  non-promotable `unknown` treatment for required SLOs; persisted the redacted
  observability summary under workspace-local
  `.astrabridge/desktop-sidecar/observability/runtime-observability-summary.json`;
  and kept the existing runtime supervisor status path as the consumer instead
  of inventing a second metrics store.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_observability.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_supervisor_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_observability.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_observability
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_supervisor_status_includes_observability_summary_from_runtime_events`
  passed 3/3; and preserved local evidence under
  `PRIVATE/agentic-update-pipeline/step20-1-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step20-1-local-summary.md`, and
  `PRIVATE/observability-window-slos/step20-1/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners and proxy/SSH connections, but no clearly
  attributable stale AstraBridge-owned listener or launcher wrapper that could
  be safely reaped in this execution slice, so no manual kills were performed.
- Blockers: None for Step 20.1.
- Next step: Step 20.2, Persist Degraded-Authority And Multimodal Quality
  Signals.

### Saturday, July 18, 2026 - Step 20.2

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/providers/failures.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/model_authority.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_observability.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, `docs/APP_STANDARDIZATION_UI_DOGFOOD_EVIDENCE.md`,
  `docs/AGENT_BENCH_DOGFOOD_EVIDENCE.md`, and the preserved local workspace
  under `PRIVATE/degraded-authority-and-multimodal/step20-2/`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_observability.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`, and this plan.
- Work completed: extended the real runtime-observability owner to persist one
  bounded degraded-authority signal surface for warning-gated structured-tool,
  MCP-tool, parallel-tool, and command-execution downgrade exposure using the
  existing model-catalog/runtime-turn inputs; added bounded multimodal quality
  incident tracking for image-attachment turns that end in no-visible-final-answer
  or timeout-class failures; threaded both signal families through the existing
  runtime supervisor summary and persisted observability snapshot; and kept the
  whole slice inside the existing observability owner instead of creating a
  second dogfood or route-diagnostics ledger.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_observability.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_supervisor_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_observability.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_sidecar_services.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_observability
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_supervisor_status_includes_observability_summary_from_runtime_events`
  passed 3/3; and preserved local evidence under
  `PRIVATE/agentic-update-pipeline/step20-2-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step20-2-local-summary.md`, and
  `PRIVATE/degraded-authority-and-multimodal/step20-2/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. A final end-of-round audit showed the same
  unrelated long-lived local listeners and proxy/SSH connections, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 20.2.
- Next step: Step 20.3, Build Redacted Support Bundles.

### Saturday, July 18, 2026 - Step 20.3

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/security.py`,
  `scripts/contract_boundary_audit.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `apps/astrabridge-sidecar/tests/test_runtime_observability.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`, and
  `apps/astrabridge-sidecar/tests/test_contract_boundary_audit.py`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_observability.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_supervisor_service.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `scripts/contract_boundary_audit.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_observability.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`, and this plan.
- Work completed: extended the real runtime-observability owner to build and
  persist one redacted runtime support bundle with versions, fingerprints,
  events, projections, health, process-ownership facts, downgraded-capability
  visibility, and recovery guidance; added a focused support-bundle redaction
  scan and persisted scan report under workspace-local support paths; threaded
  the bundle through runtime supervisor status without creating a second
  diagnostics or support-bundle exporter; and aligned ownership plus contract
  boundary audit markers with the same owner.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_observability.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_supervisor_service.py
  D:\AstraBridge\scripts\contract_boundary_audit.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_observability.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_sidecar_services.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_contract_boundary_audit.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_observability
  apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_supervisor_status_includes_observability_summary_from_runtime_events
  apps.astrabridge-sidecar.tests.test_contract_boundary_audit`
  passed 7/7; and `python scripts/contract_boundary_audit.py` passed with
  22/22 checks.
- Preserved local evidence: `PRIVATE/agentic-update-pipeline/step20-3-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step20-3-local-summary.md`, and
  `PRIVATE/runtime-support-bundles/step20-3/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. A final end-of-round audit showed the same
  unrelated long-lived local listeners and proxy/SSH connections, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 20.3.
- Next step: Step 20.4, Extend Fault Matrix And Release Evidence.

### Saturday, July 18, 2026 - Step 20.4

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `scripts/contract_boundary_audit.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/tests/test_durable_run_store.py`,
  `apps/astrabridge-sidecar/tests/test_automation_scheduler.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_observability.py`,
  `apps/astrabridge-sidecar/tests/test_release_identity.py`, and
  `apps/astrabridge-desktop/src-tauri/src/sidecar_supervision.rs`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_rollout_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_stability_gate.py`,
  `apps/astrabridge-sidecar/tests/test_runtime_rollout_gate.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `scripts/contract_boundary_audit.py`, and this plan.
- Work completed: extended the canonical `runtime_stability_gate` owner to
  emit one release-consumable fault matrix with explicit records for
  process-level kill, disk/read-only, SQLite damage, clock shift, network
  partition, truncated stream, update interruption, multimodal
  no-visible-final-answer, and cross-version cases; added bounded suite
  coverage for clock-shift recovery, durable-store damage/legacy recovery,
  observability downgrade/no-final-answer visibility, and Windows update
  interruption rehearsal; projected the same shared fault matrix through
  `runtime_rollout_gate` instead of inventing a second release-closure matrix;
  and aligned ownership plus contract-boundary markers with the same owner
  split.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_stability_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_rollout_gate.py
  D:\AstraBridge\scripts\contract_boundary_audit.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_stability_gate.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_runtime_rollout_gate.py`
  passed; `python -m unittest
  apps.astrabridge-sidecar.tests.test_runtime_stability_gate
  apps.astrabridge-sidecar.tests.test_runtime_rollout_gate
  apps.astrabridge-sidecar.tests.test_contract_boundary_audit`
  passed 11/11; and `python scripts/contract_boundary_audit.py` passed with
  22/22 checks.
- Preserved local evidence: `PRIVATE/agentic-update-pipeline/step20-4-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step20-4-local-summary.md`, and
  `PRIVATE/runtime-stability/step20-4/`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners plus Codex/Hermes helper processes, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 20.4.
- Next step: Step 21, Extract High-Risk Sidecar Services Behind Existing
  Contracts.

### Saturday, July 18, 2026 - Step 21 Plan Review

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_sidecar_services.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and
  `scripts/contract_boundary_audit.py`.
- Diagnosis: the original Step 21 bundled two independent high-risk extractions
  (`runtime_service.py` dispatch/cancellation and `task_service.py`
  graph-mutation/import-export logic) into one step even though each side has a
  different owner boundary, risk profile, and characterization surface. Current
  repository evidence shows `runtime_service.py` remains much larger and more
  coupled than `task_service.py`, while the task-graph mutation surface is
  already tightly covered by import/export, revision-conflict, and
  snapshot/rollback tests.
- Route revision: split Step 21 into Step 21.1 for task-graph
  mutation/import-export extraction and Step 21.2 for `runtime_service.py`
  dispatch/cancellation extraction. This keeps the original objective and
  quality bar intact while restoring one bounded executable work unit per turn.
- Must not weaken: keep `TaskService` as the task-scoped revision/snapshot/API
  bridge, keep `RuntimeService` as the server/runtime lifecycle bridge, do not
  create a second task-graph or runtime dispatch state machine, and preserve
  existing server/API behavior.
- Next step: Step 21.1, Extract Task-Graph Mutation And Import/Export Owner.

### Saturday, July 18, 2026 - Step 21.1

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_mutation_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and
  `scripts/contract_boundary_audit.py`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_mutation_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `scripts/contract_boundary_audit.py`, and this plan.
- Work completed: introduced `astrabridge_sidecar.task_graph_mutation_service`
  as the explicit owner for task-graph import/export transforms, overlay
  application, persist-preparation, and node/edge mutation primitives; reduced
  `TaskService` to a bridge that delegates the extracted entrypoints; extended
  ownership plus contract-boundary checks for the new owner; and added a small
  delegation characterization test on top of the existing task-graph API
  round-trip, revision-conflict, and snapshot/rollback coverage.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\task_graph_mutation_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\task_service.py
  D:\AstraBridge\scripts\contract_boundary_audit.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_task_graph_api.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_contract_boundary_audit.py`
  passed; `ASTRABRIDGE_RUNTIME_ROOT=D:\AstraBridge\PRIVATE\task-graph-mutation-runtime-root`
  `python -m unittest
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_task_service_routes_graph_mutation_entrypoints_through_shared_owner
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_export_import_reexport_round_trip_preserves_canonical_orchestration_fields
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_comfyui_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_comfyui_format
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_langgraph_import_export_reimport_round_trip_preserves_semantics_and_defaults_to_langgraph_format
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_snapshot_diff_and_rollback_resolve_snapshot_artifacts_from_task_project_workspace
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_update_graph_node_rejects_stale_expected_revision
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_update_graph_node_preserves_non_conflicting_stale_layout_edit
  apps.astrabridge-sidecar.tests.test_task_graph_api.TaskGraphApiTests.test_import_graph_from_orchestration_file_preserves_non_conflicting_stale_import_edit
  apps.astrabridge-sidecar.tests.test_contract_boundary_audit`
  passed 11/11; and `python scripts/contract_boundary_audit.py` passed with
  23/23 checks.
- Preserved local evidence: `PRIVATE/agentic-update-pipeline/step21-1-local-summary.json`
  and `PRIVATE/agentic-update-pipeline/step21-1-local-summary.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start and end of the round. The machine still showed unrelated
  long-lived local listeners plus Codex/Hermes helper processes, but no
  clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 21.1.
- Next step: Step 21.2, Extract Runtime-Service Dispatch And Cancellation
  Coordination.

### Saturday, July 18, 2026 - Step 21.2

- Evidence inspected: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_graph_run_dispatch_service.py`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_api.py`,
  `apps/astrabridge-sidecar/tests/test_task_graph_worker_runtime.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and
  `scripts/contract_boundary_audit.py`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_graph_run_dispatch_service.py`,
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`,
  `apps/astrabridge-sidecar/tests/test_graph_scheduler.py`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `scripts/contract_boundary_audit.py`, and this plan.
- Work completed: introduced
  `astrabridge_sidecar.runtime_graph_run_dispatch_service` as the explicit
  owner for live graph-run queue admission, scheduler receipt/status
  projection, persisted resume-payload capture, and cancellation coordination;
  reduced `RuntimeService` to a bridge that delegates
  `queue_task_graph_run`, `graph_scheduler_status`, `graph_run_status`, and
  `cancel_task_graph_run`; extended ownership plus contract-boundary checks for
  the new owner; and added seam-level characterization coverage for delegated
  entrypoints, persisted recovery payloads, running live-run interrupt
  requests, and queued-before-dispatch cancellation.
- Validation: `python -m py_compile
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_graph_run_dispatch_service.py
  D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_service.py
  D:\AstraBridge\scripts\contract_boundary_audit.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_graph_scheduler.py
  D:\AstraBridge\apps\astrabridge-sidecar\tests\test_contract_boundary_audit.py`
  passed; `python -m unittest
  tests.test_graph_scheduler.DurableGraphSchedulerTests.test_runtime_service_routes_graph_run_dispatch_entrypoints_through_shared_owner
  tests.test_graph_scheduler.DurableGraphSchedulerTests.test_runtime_queue_persists_receipt_before_background_execution
  tests.test_graph_scheduler.DurableGraphSchedulerTests.test_queue_task_graph_run_reuses_same_run_for_duplicate_idempotency_key
  tests.test_graph_scheduler.DurableGraphSchedulerTests.test_queue_task_graph_run_persists_resume_payload_for_live_recovery
  tests.test_graph_scheduler.DurableGraphSchedulerTests.test_live_cancel_requests_interrupt_for_running_live_run
  tests.test_graph_scheduler.DurableGraphSchedulerTests.test_live_cancel_marks_queued_live_run_cancelled_before_dispatch
  tests.test_task_graph_api.TaskGraphApiTests.test_live_cancel_and_recover_routes_prefer_runtime_handlers
  tests.test_task_graph_worker_runtime.TaskGraphWorkerRuntimeTests.test_live_graph_mcp_resource_executor_runs_without_provider_turn_dispatch
  tests.test_contract_boundary_audit`
  passed 11/11; and `python scripts/contract_boundary_audit.py` passed with
  24/24 checks.
- Preserved local evidence: `PRIVATE/agentic-update-pipeline/step21-2-local-summary.json`
  and `PRIVATE/agentic-update-pipeline/step21-2-local-summary.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. A final end-of-round audit showed the same
  unrelated long-lived local listeners plus Codex/Hermes helper processes, but
  no clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 21.2.
- Next step: Step 22, Split Desktop Graph State, Canvas, Inspector, And Run
  Monitoring.

### Saturday, July 18, 2026 - Step 22 Plan Review

- Evidence inspected: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphFallbackState.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphRunRefs.ts`, and
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`.
- Diagnosis: repository evidence showed Step 22 spans at least three concrete
  Desktop owner lanes: TaskGraphWorkspace shell-state persistence, App-level
  task-graph selection/live-run monitoring, and TaskGraphWorkspace
  canvas/inspector presentation. `TaskGraphWorkspace.tsx` is roughly 9k lines
  and `App.tsx` is roughly 12k lines, so landing all Desktop state splits in
  one round would violate the one-step-per-round rule and encourage parallel
  graph/run-state contracts.
- Route change: refined Step 22 into Step 22.1 for TaskGraphWorkspace
  shell-state/persistence ownership, Step 22.2 for App-level task-graph
  selection and run monitoring, and Step 22.3 for TaskGraphWorkspace
  canvas/inspector presentation. This preserves the original Step 22 objective
  and acceptance bar while matching the real Desktop owner boundaries.
- What must not be weakened: do not create a second graph schema, do not split
  optimistic versus authoritative run refs into separate sources of truth, and
  do not move UI persistence ownership into ad hoc storage helpers spread across
  `TaskGraphWorkspace.tsx` and `App.tsx`.
- Next step: Step 22.1, Extract TaskGraphWorkspace Shell-State And Persistence
  Owner.

### Saturday, July 18, 2026 - Step 22.1

- Evidence inspected: `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphWorkspacePersistence.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphWorkspacePersistence.test.ts`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  `apps/astrabridge-desktop/package.json`, and
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`.
- Files changed: `apps/astrabridge-desktop/src/features/runtime/taskGraphWorkspacePersistence.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphWorkspacePersistence.test.ts`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`, and this plan.
- Work completed: introduced
  `apps/astrabridge-desktop/src/features/runtime/taskGraphWorkspacePersistence.ts`
  as the explicit owner for TaskGraphWorkspace sidebar-width normalization,
  workspace localStorage keying, stored inspector-workspace restore, and
  pending run-inspector reopen markers; reduced `TaskGraphWorkspace.tsx` to a
  bridge that routes those persistence reads/writes through the shared owner;
  documented the new Desktop owner boundary; and added focused persistence unit
  tests beside the existing workspace component regression coverage.
- Validation: `node ./node_modules/vitest/vitest.mjs run
  src/features/runtime/taskGraphWorkspacePersistence.test.ts
  src/features/runtime/TaskGraphWorkspace.test.tsx -t "lets the user resize task-graph sidebars and persists the widths|restores the run inspection workspace after remounting the same graph|taskGraphWorkspacePersistence"`
  passed 6 tests; and `node ./node_modules/typescript/bin/tsc --noEmit` passed.
- Preserved local evidence: `PRIVATE/agentic-update-pipeline/step22-1-local-summary.json`
  and `PRIVATE/agentic-update-pipeline/step22-1-local-summary.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the start of the round. A final end-of-round audit showed the same
  unrelated long-lived local listeners plus Codex/Hermes helper processes, but
  no clearly attributable stale AstraBridge-owned listener or launcher wrapper
  that could be safely reaped in this execution slice, so no manual kills were
  performed.
- Blockers: None for Step 22.1.
- Next step: Step 22.2, Extract App-Level Task-Graph Selection And Run
  Monitoring Owner.

### Saturday, July 18, 2026 - Step 22.2

- Evidence inspected: `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphAppState.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphAppState.test.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphSelection.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphSelection.test.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphRunRefs.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphRunRefs.test.ts`,
  `apps/astrabridge-desktop/package.json`, and
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`.
- Files changed: `apps/astrabridge-desktop/src/App.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphAppState.ts`,
  `apps/astrabridge-desktop/src/features/runtime/taskGraphAppState.test.ts`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `PRIVATE/agentic-update-pipeline/step22-2-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step22-2-local-summary.md`, and this plan.
- Work completed: introduced
  `apps/astrabridge-desktop/src/features/runtime/taskGraphAppState.ts` as the
  explicit owner for current task-graph selection, fallback-versus-server graph
  arbitration, node override application, per-graph snapshot/edit-history/
  command-log projection, optimistic versus authoritative live run-ref
  selection, and task-graph dataset payload assembly; reduced `App.tsx` to the
  top-level query/mutation and dispatch-timeout bridge that now consumes the
  shared app-state selector instead of keeping a second inline selector; added
  focused regression coverage for the extracted selection and run-monitoring
  contract; and documented the new Desktop owner boundary.
- Validation: `node ./node_modules/vitest/vitest.mjs run
  src/features/runtime/taskGraphAppState.test.ts
  src/features/runtime/taskGraphSelection.test.ts
  src/features/runtime/taskGraphRunRefs.test.ts` passed 29 tests; and
  `node ./node_modules/typescript/bin/tsc --noEmit` passed.
- Preserved local evidence:
  `PRIVATE/agentic-update-pipeline/step22-2-local-summary.json` and
  `PRIVATE/agentic-update-pipeline/step22-2-local-summary.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the end of the round. The listener/process set still matched the same
  long-lived local helpers and unrelated services, and no clearly attributable
  stale AstraBridge-owned listener or launcher wrapper appeared, so no manual
  kills were performed.
- Blockers: None for Step 22.2.
- Next step: Step 22.3, Extract TaskGraphWorkspace Canvas And Inspector View
  Owner.

### Saturday, July 18, 2026 - Step 22.3

- Evidence inspected:
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphInspectorModal.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphInspectorModal.test.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.test.tsx`,
  `apps/astrabridge-desktop/package.json`, and
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`.
- Files changed:
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphInspectorModal.tsx`,
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphInspectorModal.test.tsx`,
  `docs/CODE_OWNERSHIP_AND_CONTRACTS.md`,
  `PRIVATE/agentic-update-pipeline/step22-3-local-summary.json`,
  `PRIVATE/agentic-update-pipeline/step22-3-local-summary.md`, and this plan.
- Work completed: introduced
  `apps/astrabridge-desktop/src/features/runtime/TaskGraphInspectorModal.tsx`
  as the explicit owner for inspector scrim/modal chrome, header subtitle,
  workspace switching tabs, and selection-mode chip presentation; reduced
  `TaskGraphWorkspace.tsx` to the graph editor and editable inspector-body
  bridge that now supplies content and callbacks through the shared inspector
  modal owner instead of keeping a second inline modal shell; added focused
  component coverage for the extracted modal owner; and documented the new
  Desktop owner boundary.
- Validation: `node ./node_modules/vitest/vitest.mjs run
  src/features/runtime/TaskGraphWorkspace.test.tsx
  src/features/runtime/TaskGraphInspectorModal.test.tsx` passed 94 tests; and
  `node ./node_modules/typescript/bin/tsc --noEmit` passed.
- Preserved local evidence:
  `PRIVATE/agentic-update-pipeline/step22-3-local-summary.json` and
  `PRIVATE/agentic-update-pipeline/step22-3-local-summary.md`.
- Process hygiene: ran read-only process audits and read-only `netstat` checks
  at the end of the round. The listener/process set still matched the same
  long-lived local helpers and unrelated services, and no clearly attributable
  stale AstraBridge-owned listener or launcher wrapper appeared, so no manual
  kills were performed.
- Blockers: None for Step 22.3.
- Next step: Step 23, Run Final Interoperability, Upgrade, Recovery, And
  Release Closure.
