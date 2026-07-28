# AstraBridge Multi-Provider Stability Hardening Handoff Plan

## Plan Authority And Existing-Plan Relationship

This file is the durable handoff and forward-execution control surface for the
next AstraBridge hardening round focused on product stability, standards
discipline, and operational closure for AstraBridge's stated positioning:

- a multi-provider, multi-model Codex shell;
- one canonical internal agent communication contract;
- MCP-normalized multimodal, tool, and resource execution, including internal
  loopback paths;
- cross-provider and cross-peer agent interoperability through an explicit A2A
  boundary;
- GUI-authored and code-authored agent orchestration over one canonical graph;
- supervised, track-separated, rollback-safe upgrade behavior.

This plan is a successor handoff surface, not a work reset. It preserves the
validated implementation and evidence already recorded in:

- `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`
- `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`
- `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`
- `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`

Those files remain authoritative evidence for completed work and baseline
constraints. They are not parallel schedulers for the remaining hardening work.
Future agents working on this exact product-hardening scope should continue from
this file and use the older execution plan as preserved baseline evidence.

## Total Objective

Make AstraBridge stable enough to credibly operate as a multi-provider,
multi-model Codex shell whose advertised capabilities remain truthful,
recoverable, interoperable, and upgrade-safe under real product conditions.

Concretely, the hardened product must satisfy all of the following:

1. multimodal, tool, and resource execution go through MCP contracts, including
   first-party internal loopback paths that still obey the same policy,
   timeout, cancellation, audit, and typed-result surface;
2. cross-provider and cross-peer agent communication terminates in one
   AstraBridge-owned durable internal envelope and delivery ABI rather than a
   growing set of provider-specific message shapes;
3. external A2A compatibility is explicit, versioned, bounded, and tested as a
   gateway boundary rather than allowed to leak into internal runtime state;
4. GUI orchestration and code orchestration remain projections over one
   canonical graph, executor registry, and runtime contract, while still
   supporting ComfyUI-, LangChain-, and LangGraph-class authoring patterns;
5. provider/model capability claims degrade truthfully under uncertainty,
   partial support, or reduced authority instead of defaulting to optimistic
   flags;
6. automatic upgrade behavior stays supervised, track-separated, journaled,
   health-checked, cohort-aware, and rollback-safe across metadata, kernel,
   plugin, executor, and desktop lanes;
7. the above guarantees are enforced by tests, drift checks, chaos/fault
   evidence, support runbooks, and promotion gates rather than product prose.

## Deliverables

- A single hardening execution source for the remaining multi-provider product
  closure work.
- A locked product-boundary contract covering MCP, internal envelopes, A2A,
  canonical orchestration graphs, and upgrade tracks.
- An authoritative provider/model/capability truthfulness surface with explicit
  downgrade semantics.
- A durable cross-provider agent-delivery contract with bounded A2A gateway
  compatibility and conformance evidence.
- Canonical GUI/code orchestration parity evidence across graph import/export,
  compile/lower, run, diff, and recovery paths.
- A supervised auto-upgrade controller with policy, journaling, staged cohort
  rollout, pause/kill-switch behavior, and rollback evidence.
- A fault-injection and soak-test pack covering provider, A2A, MCP, graph, and
  upgrade lanes.
- Release and support evidence that future operators can use without relying on
  chat history.

## Constraints And Attention Notes

1. Preserve `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md` and
   `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`
   as historical execution records.
2. Preserve `.abproj`, workspace-local `.astrabridge/`, `PRIVATE/**`, logs,
   caches, raw experiment traces, screenshots, and validation reports by
   default.
3. Never persist or stage API keys, bearer tokens, cookies, authorization
   headers, provider raw secrets, or unredacted peer credentials.
4. Do not reintroduce `.lcr*`, `.codexproj`, `.codex-shell`, official OpenAI
   account login, or normal writes to official Codex configuration paths.
5. Do not create a second internal agent-message ABI. All provider-specific or
   external-A2A shapes must adapt back into one durable AstraBridge-owned
   envelope and delivery vocabulary.
6. Do not create provider-direct multimodal, tool, or resource execution paths
   that bypass MCP merely for convenience or performance.
7. Do not let GUI-only metadata, export-only metadata, or generated code become
   a second execution truth distinct from the canonical graph and executor
   runtime.
8. Do not claim provider/model capability support without preserved evidence and
   explicit downgrade semantics for `partial`, `unsupported`,
   `reduced-authority`, `blocked`, or `unknown`.
9. Do not convert automatic upgrade work into ad hoc installer logic that skips
   staging inventories, trust checks, journals, health gates, or rollback
   readiness.
10. Before and after sidecar or desktop runtime work, audit AstraBridge-owned
    ports, listeners, and stale launcher processes; reap only clearly owned
    stale state.
11. Rewriting this plan from Step 0 is a plan-document reset, not a work reset.
    Carry forward validated repository evidence unless new evidence contradicts
    it.
12. Each execution turn under this plan should complete exactly one full
    numbered step, update current progress plus the progress log, and stop at
    the next entry point.

## Adjustment Policy

Agents may reasonably adjust substeps, filenames, commands, sequencing, test
shapes, and implementation details when repository evidence requires it.
Adjustments must not:

- weaken the product boundary around MCP, internal envelopes, or A2A;
- lower the truthfulness bar for provider/model/capability claims;
- split GUI/code orchestration into parallel graphs or runtimes;
- weaken upgrade, rollback, or trust guarantees;
- replace runtime evidence with documentation-only claims;
- discard validated artifacts or preserved evidence without contradictory proof.

If a core route becomes stale, record the blocker, inspected evidence, attempted
paths, invariant that must not be weakened, and the exact next step.

## Evidence Review And Plan Revision Policy

Before executing the next step, inspect the owner files, tests, and latest
preserved evidence for that step's lane. Trigger a bounded plan review when any
of these occur:

1. repository code contradicts this plan's baseline assumptions;
2. a step would introduce a parallel contract, runtime, or compatibility source
   of truth;
3. provider, MCP, A2A, or update claims are backed only by docs, fixtures, or
   UI projection rather than an executable runtime path;
4. the next step is no longer the highest-leverage hardening move;
5. repeated continuations are producing packaging or planning artifacts while
   the real blocker remains in runtime behavior, compatibility drift, or
   operator recovery.

When triggered, revise minimally: record evidence, diagnosis, route change,
what must not be weakened, and the exact next step. Restore one executable work
unit rather than expanding documentation indefinitely.

## Execution Rules

1. Classify each future turn as planning mode or execution mode. Requests to
   continue, implement, execute, fix, advance, or resume default to execution
   mode.
2. In execution mode, start from the earliest non-completed numbered step
   unless the user explicitly redirects the work.
3. Name one bounded current work unit before implementation, including expected
   output and acceptance check.
4. Complete exactly one full numbered step per user-facing execution round.
5. A step is complete only after its acceptance criteria and proportionate
   validation evidence pass.
6. Update only Current Progress, Current Work Unit, completed step status, and
   the append-only Progress Log unless evidence requires a route change.
7. If blocked, record concrete evidence and the exact next action. Do not
   substitute repeated plan maintenance for executable work.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Hardening Handoff Plan
- Current step: Step 1, Freeze Product Boundary And Stability Closure Contract
- Next step: Step 1, Freeze Product Boundary And Stability Closure Contract
- Last updated: 2026-07-27

## Current Work Unit

- ID: step-1-boundary-freeze
- Goal: Convert the current product positioning into one explicit closure
  contract that future execution steps cannot silently violate.
- Inputs:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`,
  `PLAN/ASTRABRIDGE_MULTI_PROVIDER_ADAPTATION_UPGRADE_HANDOFF_PLAN.md`,
  `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`,
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`,
  `PRIVATE/provider-compatibility/reports/step13-adaptation-upgrade-closure-20260727.md`,
  and the relevant sidecar/desktop owner files.
- Expected output: A short contract artifact or plan update that locks the
  non-negotiable boundaries for MCP, internal envelopes, A2A, canonical graph
  ownership, provider downgrade semantics, and upgrade tracks.
- Acceptance check: A future agent can point to one explicit source that says
  what must not be violated while hardening the product.
- Status: queued
- Next action: Draft and land the stability closure contract using the incoming
  adaptation evidence as a hard provider-truthfulness constraint, then update
  this plan to Step 2.

## Execution Steps

### 0. Create Durable Hardening Handoff Plan

Goal: Create the persistent execution contract for the remaining hardening work.

Main actions:

- Define the total objective, constraints, adjustment policy, execution rules,
  and numbered steps.
- Preserve the relationship to the existing large stability/interoperability
  execution plan.
- Leave an unambiguous next entry point.

Acceptance criteria:

- Plan file exists on disk.
- Plan preserves validated prior work instead of restarting it.
- Next step is explicitly identified.

Status: completed

### 1. Freeze Product Boundary And Stability Closure Contract

Goal: Lock the non-negotiable product contract that future hardening steps must
enforce.

Main actions:

- Write or update one contract artifact that freezes:
  - MCP-only multimodal/tool/resource execution;
  - one internal durable agent-envelope and delivery ABI;
  - external A2A as an explicit gateway boundary;
  - one canonical graph/executor/runtime contract for GUI and code;
  - track-separated upgrade lanes and trust policies.
- List the precise places where the current repository still risks boundary
  drift.
- Define what counts as a release-blocking violation versus a degradable
  warning.

Acceptance criteria:

- One durable boundary contract exists on disk.
- The contract explicitly covers MCP, internal envelopes, A2A, orchestration,
  provider truthfulness, and upgrade tracks.
- Release-blocking versus warning-level violations are distinguishable.

Status: not started

### 2. Harden Provider Capability Truthfulness And Drift Detection

Goal: Make provider/model capability claims stable, evidence-backed, and
truthful under drift.

Main actions:

- Reduce optimistic defaults in provider/model/capability surfaces.
- Tighten official-source evidence flow, downgrade semantics, and route-status
  reporting.
- Add or refine drift checks that fail when runtime claims outrun preserved
  evidence.

Acceptance criteria:

- Provider capability surfaces have explicit downgrade semantics.
- Drift checks exist for declared-versus-runtime-versus-evidence mismatches.
- The next agent can tell which lanes are verified, partial, blocked, or
  unsupported without reading chat history.

Status: not started

### 3. Close Cross-Provider Internal Agent Delivery Semantics

Goal: Ensure agent-to-agent communication remains durable and uniform across
  provider boundaries.

Main actions:

- Audit and tighten the internal envelope, artifact, acknowledgement, retry,
  idempotency, expiry, and terminal-outcome vocabulary.
- Remove or adapt any provider-specific or peer-specific message shapes that do
  not round-trip through the canonical internal ABI.
- Add regression checks for cross-provider continuity, lineage, cancellation,
  and recovery.

Acceptance criteria:

- Cross-provider agent delivery paths map back into one internal ABI.
- Delivery semantics cover acknowledgement, retry, expiry, and terminal
  outcomes.
- Regression evidence exists for at least one multi-provider handoff path.

Status: not started

### 4. Harden External A2A Gateway Compatibility And Conformance

Goal: Make external A2A support bounded, explicit, and safe to evolve.

Main actions:

- Add or refine Agent Card, version negotiation, cancellation, streaming,
  artifact exchange, and trust policy handling.
- Ensure gateway adapters terminate at the boundary and do not leak external
  wire state into the internal store.
- Preserve conformance evidence and downgrade behavior for unsupported or
  partially supported peer capabilities.

Acceptance criteria:

- External A2A compatibility is versioned and gateway-bounded.
- Conformance or interoperability evidence exists for the supported window.
- Unsupported peer behavior degrades explicitly rather than corrupting internal
  state.

Status: not started

### 5. Enforce MCP As The Normal Capability Plane

Goal: Remove remaining ambiguity about where multimodal, tool, and resource
execution are allowed to happen.

Main actions:

- Inventory and close any remaining provider-direct or ad hoc capability paths
  that bypass MCP contracts.
- Tighten internal loopback MCP behavior so timeout, cancellation, audit, and
  typed-result semantics match remote MCP behavior.
- Add contract or runtime checks that fail if a public capability surface
  escapes the MCP plane.

Acceptance criteria:

- Public multimodal/tool/resource lanes are MCP-normalized.
- Internal loopback and remote MCP paths obey the same policy surface.
- Contract or runtime checks prevent new bypass paths from landing silently.

Status: not started

### 6. Prove GUI And Code Orchestration Parity

Goal: Keep visual and code authoring as two views over one canonical graph and
runtime.

Main actions:

- Tighten canonical graph ownership, revision control, and GUI/code round-trip
  semantics.
- Preserve explicit mappings for ComfyUI-, LangChain-, and LangGraph-style
  authoring patterns without creating a second graph truth.
- Add parity checks for import/export, compile/lower, diff, run, rollback, and
  recovery behavior.

Acceptance criteria:

- GUI and code flows round-trip through one canonical graph contract.
- Round-trip evidence exists for the supported authoring families.
- No GUI-only or code-only metadata becomes required runtime truth.

Status: not started

### 7. Complete Executor Coverage And Code-Orchestration Tooling

Goal: Ensure every public graph node type has a real executable owner and that
code-authored graphs are practical to validate.

Main actions:

- Audit registry coverage for all public graph nodes and execution modes.
- Close scaffold-only or generated-not-implemented gaps in graph export or
  lowering surfaces.
- Tighten Python/TypeScript graph tooling for lint, compile, diff, dry-run,
  and recoverability checks.

Acceptance criteria:

- Every public graph node type maps to an executable owner or is explicitly
  hidden/degraded.
- Scaffold-only graph export or lowering gaps are removed or blocked.
- Code-authored graph workflows have runnable validation tooling.

Status: not started

### 8. Land A Supervised Track-Separated Auto-Upgrade Controller

Goal: Turn upgrade support into a controlled operational lane rather than a
proposal-only helper.

Main actions:

- Add a supervised controller for allowed update tracks with policy, cohort,
  pause, dependency, and kill-switch handling.
- Preserve apply journals, health verdicts, rollback manifests, and operator
  summaries.
- Keep unsupported or higher-risk tracks disabled by default until the trust
  and recovery evidence exists.

Acceptance criteria:

- A supervised auto-upgrade controller exists for the allowed tracks.
- Journaling, containment, and rollback evidence are preserved automatically.
- Riskier tracks remain explicit opt-in or blocked by policy rather than
  silently entering automation.

Status: not started

### 9. Harden Plugin, Executor, And Compatibility Lifecycle Governance

Goal: Keep plugin, skill, executor, and provider-surface growth from becoming a
new instability source.

Main actions:

- Define compatibility gates for plugins, skills, node executors, and provider
  metadata.
- Add staged promotion rules, incompatibility quarantine behavior, and
  visibility for reduced-authority or degraded routes.
- Ensure lifecycle tooling updates the same compatibility truth surfaces rather
  than inventing side metadata.

Acceptance criteria:

- Compatibility governance exists for plugins, skills, executors, and provider
  surfaces.
- Broken or incompatible additions degrade safely instead of poisoning the
  product baseline.
- Promotion or quarantine behavior is evidence-backed.

Status: not started

### 10. Build Fault-Injection, Soak, And Recovery Evidence

Goal: Prove the product remains stable under realistic failures rather than
only under happy-path tests.

Main actions:

- Expand the fault matrix across provider lanes, A2A gateway, MCP execution,
  graph runtime, and upgrade/interruption behavior.
- Run bounded soak or chaos scenarios that preserve supportable evidence.
- Verify recovery paths, support bundle contents, and operator-visible failure
  states.

Acceptance criteria:

- Preserved fault evidence exists across the major runtime lanes.
- Recovery behavior is visible and supportable.
- The next agent can identify unresolved reliability gaps from preserved
  artifacts rather than rerunning the whole matrix.

Status: not started

### 11. Close Release, Support, And Operator Readiness

Goal: Make the hardened product operable by release and support functions, not
just by developers who know the repository.

Main actions:

- Tighten promotion gates, support runbooks, inventory surfaces, and support
  bundles around the hardened contracts.
- Ensure the upgrade lane, provider truthfulness lane, A2A lane, and graph
  lane all produce operator-readable evidence.
- Define the exact closure bar for this hardening round.

Acceptance criteria:

- Promotion and support surfaces reflect the hardened contracts.
- Support bundles and runbooks cover the main failure and rollback paths.
- A clear closure checklist exists for the round.

Status: not started

### 12. Run Final Product Hardening Closure

Goal: Produce the final evidence-backed verdict on whether AstraBridge is
stable enough for its intended positioning.

Main actions:

- Run the final bounded closure suite across provider truthfulness,
  cross-provider delivery, A2A interoperability, MCP enforcement,
  GUI/code-orchestration parity, and supervised upgrade behavior.
- Preserve final reports, unresolved gaps, and recommended follow-up work.
- Decide release-blocking versus deferred issues using the frozen closure
  contract.

Acceptance criteria:

- Final closure evidence exists on disk.
- Release-blocking versus deferrable residual risks are explicit.
- The next operator can decide whether the product is ready without
  reconstructing chat history.

Status: not started

## Progress Log

### 2026-07-19 - Step 0

- Completed: Created the durable hardening handoff plan for the remaining
  multi-provider stability scope.
- Evidence inspected:
  `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`,
  `PLAN/MULTI_AGENT_GUI_ORCHESTRATION_HANDOFF_PLAN.md`,
  `PLAN/AGENT_ORCHESTRATION_GRAPH_CONTRACT.md`,
  `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`, and
  `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`.
- Diagnosis: the repository already had a large execution baseline and several
  narrower subplans, but it still benefited from one compact forward-looking
  handoff surface for the remaining product-hardening work centered on
  multi-provider truthfulness, A2A boundaries, MCP enforcement, orchestration
  parity, and supervised upgrades.
- Route change: introduced this file as the preferred handoff entry point for
  this remaining hardening lane while preserving prior validated execution
  evidence instead of restarting the work.
- What must not be weakened: MCP as the normal capability plane, one durable
  internal agent-delivery ABI, explicit A2A boundary, one canonical graph, and
  track-separated rollback-safe upgrades.
- Next step: Step 1, Freeze Product Boundary And Stability Closure Contract.

### 2026-07-27 - Incoming Adaptation Upgrade Closure Evidence

- Evidence received:
  `PLAN/ASTRABRIDGE_MULTI_PROVIDER_ADAPTATION_UPGRADE_HANDOFF_PLAN.md`,
  `PRIVATE/provider-compatibility/reports/step13-adaptation-upgrade-closure-20260727.md`,
  `PRIVATE/agentic-update-pipeline/runs/step13-provider-capability-closure-20260727-r2/`,
  and
  `PRIVATE/agentic-update-pipeline/runs/step13-four-provider-reference-cohort-closure-20260727-r1/`.
- What it proves: the adaptation slice now has exact-route contracts for
  Qwen, DeepSeek, Kimi K3, and GLM; deterministic conformance, neutral
  handoff, receipt, fallback, context, route-promotion, and runtime-admission
  regressions pass; the provider capability gate passes without network or
  provider calls; and Kimi K3 follows the shared promotion lifecycle without
  a Kimi-only bypass.
- Truthfulness boundary: the four selected external routes remain
  `documented` / `review_only` / `reduced_authority` until route-specific
  adapter dry-run and explicitly authorized provider smoke evidence exist.
  This incoming evidence does not verify, recommend, default, or automatically
  fallback any external route.
- Parent impact: no parent numbered step is marked complete by this handoff.
  Step 1 remains the exact next work unit and must encode the above downgrade,
  evidence-binding, and supervised-promotion constraints in the product
  closure contract before broader hardening work resumes.
