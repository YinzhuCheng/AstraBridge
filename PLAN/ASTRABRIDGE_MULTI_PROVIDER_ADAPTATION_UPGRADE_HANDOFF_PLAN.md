# AstraBridge Multi-Provider Adaptation Upgrade Handoff Plan

## Plan Authority And Existing-Plan Relationship

This is the durable, narrow execution plan for upgrading AstraBridge's
multi-provider coding-agent adaptation architecture. Its explicit product
direction is:

- Codex remains AstraBridge's core coding-agent runtime and first-class
  execution experience;
- Hermes is a design reference only, not a runtime dependency, a product
  replacement, or code to copy wholesale;
- external providers must enter AstraBridge through explicit protocol,
  capability, authority, and execution-route contracts rather than by being
  treated as interchangeable Codex endpoints.

This plan is subordinate to, and must not replace,
`PLAN/ASTRABRIDGE_MULTI_PROVIDER_STABILITY_HARDENING_HANDOFF_PLAN.md`. The
parent plan owns the broader MCP, A2A, GUI/code orchestration, product
stability, release, and operator-readiness scope. This file owns only the
bounded provider-adaptation route described below, and its evidence should
feed the parent plan's provider-truthfulness, cross-provider delivery, and
supervised-upgrade work.

The completed `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md` remains the
source of truth for the existing proposal, validation, apply, rollback, and
managed-key update-pipeline substrate. This plan extends that substrate only
where model discovery must decide whether a provider/model/endpoint is safe to
enter a coding-agent execution route.

## Total Objective

Make AstraBridge able to upgrade and operate its supported external model lanes
without weakening Codex as the core runtime: each provider/model/endpoint must
have a truthful, evidence-backed execution route; cross-provider continuity
must preserve only safe neutral context; model-generated tools must be
authorized, validated, and recoverable without duplicate side effects; and a
self-update run must never promote documentation-derived metadata directly to
agent authority.

The target supported adaptation cohort is the existing provider-specific
transport families for Qwen, DeepSeek, Kimi, and GLM, with OpenAI/Codex and
Yunwu-compatible routes retained as separate existing lanes. Kimi K3 is the
reference model for proving the new promotion lifecycle after the generic
contracts exist; it is not a justification for a one-off Kimi-only design.

## Deliverables

- A durable Codex-core multi-provider execution contract that separates
  provider, model, endpoint, wire protocol, execution driver, authority, and
  validation evidence.
- Versioned runtime contracts and owner maps for `ProviderProfile`, model
  metadata, endpoint protocol adaptation, execution-route selection, neutral
  history projection, and failure transitions.
- A safe tool-action lifecycle covering request validation, authority,
  idempotency/receipt semantics, checkpoints, retry, handoff, and recovery.
- A provider-aware context, reasoning-artifact, streaming, cancellation, and
  fallback contract with explicit degradation behavior.
- Update-pipeline promotion gates that distinguish documented facts from
  adapter proof, provider smoke, coding-route verification, and default-route
  eligibility.
- Focused deterministic tests, secret-free dry-run artifacts, authorized
  bounded smoke evidence where justified, and user-visible route/status
  explanations.
- A final implementation and operator handoff that names verified,
  reduced-authority, blocked, and deferred routes.

## Constraints And Attention Notes

1. Codex is the AstraBridge core. Do not replace it with a generic external
   agent loop or model it merely as another `ProviderProfile`.
2. Hermes is reference material. Reuse its invariants where they fit, but do
   not vendor, copy, or make runtime behavior depend on Hermes source unless a
   later bounded implementation question requires source-level comparison.
3. Preserve `.abproj`, workspace-local `.astrabridge/`, `PRIVATE/**`,
   sanitized request/response traces, validation reports, caches, logs, and
   intermediate artifacts by default.
4. Never persist API keys, bearer tokens, cookies, authorization headers,
   vault contents, desktop plaintext key contents, opaque provider reasoning,
   signed thinking artifacts, or raw private provider state in source, plans,
   reports, logs, or git.
5. Provider-backed smoke, paid calls, installs, source-code mutation,
   promotion, external writeback, and branch/push actions require the specific
   authorization applicable to that future turn. A documentation update alone
   is not authority to run a live test.
6. Retain the existing conservative cross-provider rule: do not raw-fork a
   provider-owned thread into another provider. Use a neutral task/project
   context pack, explicit lineage, and safe summaries.
7. Do not create a second internal event or agent-message ABI. Reuse and
   extend the AstraBridge coding-event and durable task-envelope surfaces.
8. Do not convert an `OpenAI-compatible` HTTP success into a claim of coding
   agent compatibility. Tool, reasoning, streaming, attachments, cancellation,
   and side-effect semantics require independent evidence.
9. A new model may receive documented metadata automatically only through the
   supervised update pipeline. It may not become default, autonomous,
   tool-enabled, or route-eligible without the appropriate evidence stage.
10. Before and after sidecar or desktop runtime execution, audit clearly owned
    AstraBridge listeners and stale launchers; reap only clearly stale,
    AstraBridge-owned processes.
11. This plan's Step 0 is a document-creation step, not a restart of the
    existing provider, update-pipeline, or Codex compatibility work.

## Adjustment Policy

Agents may adjust file names, substep order, fixture shapes, protocol
implementation details, and the selected representative models when current
repository or official-provider evidence requires it. Such adjustments must
not change the total objective, weaken Codex's core role, lower evidence or
authority gates, remove rollback/recovery protections, or replace semantic
compatibility work with prompt-only work.

If the supplied Hermes mechanisms or current code prove a planned route stale,
record the evidence, diagnosis, route change, non-negotiable invariant, and
exact next work unit in the progress log. A plan rewrite is a document reset
only unless the user explicitly asks to rerun or discard validated work.

## Evidence Review And Plan Revision Policy

Before an execution step, inspect the active owner files, relevant tests, and
latest preserved provider evidence. Trigger a plan review when:

1. a runtime path contradicts an assumed adapter or execution-route contract;
2. a proposed change would cause an external provider to impersonate a Codex
   native thread or bypass the common tool/event policy;
3. documentation, static metadata, or dry-run evidence is being mistaken for
   provider-backed or coding-route proof;
4. a retry/handoff route could duplicate a tool side effect or lose a required
   checkpoint;
5. a provider release, endpoint change, or smoke result makes a capability
   claim stale; or
6. the next step no longer addresses the highest-risk source of misleading
   agent behavior.

When triggered, revise the smallest necessary part of this plan, preserve the
quality bar, and restore one bounded executable work unit. Do not use repeated
planning or inventory refreshes as a substitute for implementation evidence.

## Execution Rules

1. Classify future turns as planning mode or execution mode. Requests to
   continue, implement, execute, fix, advance, or resume are execution mode.
2. In execution mode, start from the earliest non-completed numbered step here
   unless the user explicitly redirects to another step.
3. Complete exactly one full numbered step per user-facing execution round.
4. Each execution turn must produce an observable delta: a contract, code and
   tests, a validated report, an accepted/rejected candidate, or an evidenced
   blocker.
5. Mark a step completed only after every listed acceptance criterion holds.
6. Update only Current Progress, Current Work Unit, the active step status,
   and the append-only Progress Log unless evidence requires a route change.
7. Preserve all evidence under the existing secret-free update and
   provider-compatibility artifact roots; do not create a parallel planner or
   undisclosed evidence store.

## Execution Status

| Step | Status |
| --- | --- |
| 0. Create Durable Adaptation Upgrade Plan | [x] completed |
| 1. Freeze The Codex-Core Multi-Provider Execution Contract | [x] completed |
| 2. Produce A Current Route And Semantic-Gap Baseline | [x] completed |
| 3. Define The Versioned Execution-Route And Evidence Lifecycle Contract | [x] completed |
| 4. Refactor Provider, Model, Endpoint, And Route Ownership | [x] completed |
| 5. Harden Protocol Adapters And Build A Semantic Conformance Corpus | [x] completed |
| 6. Formalize Neutral Transcript And Reasoning-Artifact Provenance | [x] completed |
| 7. Introduce A Tool Action Envelope And Side-Effect Receipt Ledger | [x] completed |
| 8. Make Fallback, Retry, And Handoff A Transactional Turn State Machine | [x] completed |
| 9. Make Context Budgeting And Compaction Endpoint-Aware | [x] completed |
| 10. Extend The Agentic Update Pipeline With Route-Promotion Gates | [x] completed |
| 11. Enforce Runtime Admission And Explain Degradation In The Product | [x] completed |
| 12. Run The Controlled Four-Provider/Kimi K3 Reference Cohort | [x] completed |
| 13. Close The Adaptation Upgrade Slice And Hand Back To Product Hardening | [x] completed |

## Current Progress

- Current status: Completed
- Completed steps: Step 0, Create Durable Adaptation Upgrade Plan; Step 1,
  Freeze The Codex-Core Multi-Provider Execution Contract; Step 2, Produce A
  Current Route And Semantic-Gap Baseline; Step 3, Define The Versioned
  Execution-Route And Evidence Lifecycle Contract; Step 4, Refactor Provider,
  Model, Endpoint, And Route Ownership; Step 5, Harden Protocol Adapters And
  Build A Semantic Conformance Corpus; Step 6, Formalize Neutral Transcript
  And Reasoning-Artifact Provenance; Step 7, Introduce A Tool Action Envelope
  And Side-Effect Receipt Ledger; Step 8, Make Fallback, Retry, And Handoff A
  Transactional Turn State Machine; Step 9, Make Context Budgeting And
  Compaction Endpoint-Aware; Step 10, Extend The Agentic Update Pipeline With
  Route-Promotion Gates; Step 11, Enforce Runtime Admission And Explain
  Degradation In The Product; Step 12, Run The Controlled Four-Provider/Kimi
  K3 Reference Cohort; Step 13, Close The Adaptation Upgrade Slice And Hand
  Back To Product Hardening
- Current step: None; this bounded adaptation-upgrade slice is complete.
- Next step: Parent hardening plan Step 1, Freeze Product Boundary And
  Stability Closure Contract, in
  `PLAN/ASTRABRIDGE_MULTI_PROVIDER_STABILITY_HARDENING_HANDOFF_PLAN.md`
- Last updated: 2026-07-27

## Current Work Unit

- ID: adaptation-upgrade-slice-complete
- Goal: Preserve the completed provider-adaptation evidence and hand the
  remaining product-hardening work to its parent plan.
- Inputs: The Step 13 closure report, final deterministic cohort, provider
  capability verification gate, updated operator runbook, and parent-plan
  incoming-evidence entry.
- Expected output: A future operator or agent can distinguish the completed
  deterministic adaptation work from the separately authorized provider-smoke
  and broader product-hardening work.
- Acceptance check: Every numbered step in this plan is complete, the four
  selected external routes remain truthfully reduced-authority, and the parent
  plan names its exact next work unit.
- Status: completed
- Next action: Continue only from parent hardening Step 1; do not treat this
  completed adaptation plan as authority for a live provider call or route
  promotion.

## Execution Steps

### 0. Create Durable Adaptation Upgrade Plan

Goal: Create the bounded execution contract and leave an unambiguous next
entry point.

Main actions:

- Record the Codex-core direction, Hermes-reference boundary, current
  repository evidence, constraints, execution rules, and step acceptance
  criteria.
- Establish the relationship to the broader stability handoff and the
  completed update-pipeline plan without replacing either.

Acceptance criteria:

- This file exists and contains a total objective, constraints, adjustment and
  evidence-review policies, current work unit, numbered steps, acceptance
  criteria, and progress log.
- The first implementation step and its owner files are unambiguous.
- No existing validated work is marked stale or discarded without evidence.

Status: completed

### 1. Freeze The Codex-Core Multi-Provider Execution Contract

Goal: Define the product boundary that all provider-adaptation changes must
obey.

Main actions:

- Create a focused contract artifact that separates: Codex-native driver,
  AstraBridge native-provider driver, and preview/review-only route.
- Define which decisions belong to provider profile, model contract, endpoint
  contract, execution route, task/tool policy, and validation evidence.
- Classify release-blocking violations, such as unsafe cross-provider private
  state replay or unverified autonomous tool execution, versus degradable
  warnings.

Acceptance criteria:

- One contract artifact identifies the authoritative owner of each decision.
- It explicitly says that Codex is core rather than a generic provider adapter.
- It gives a fail-closed rule for unsupported or unverified routes.

Status: completed

### 2. Produce A Current Route And Semantic-Gap Baseline

Goal: Convert the current implementation into a finite, evidence-backed queue
of adaptation gaps rather than an abstract architecture critique.

Main actions:

- Map shipped profiles, four provider-family transports, model catalog fields,
  execution-backend selection, native-kernel feature gate, history projection,
  tool execution, transition planning, and update-pipeline promotion surfaces.
- Record for each Qwen, DeepSeek, Kimi, and GLM representative route whether
  the current semantics are implemented, adapter-only, app-server-only,
  native-kernel-capable, verified, partial, or unknown.
- Separate repository-proven behavior from documentation assumptions and from
  live-provider evidence.

Acceptance criteria:

- A bounded route matrix and risk-ranked owner queue are preserved.
- Every high-risk gap names a concrete file/test owner and expected evidence.
- Kimi K3 is represented as a generic-contract reference case, not a special
  exception.

Status: completed

### 3. Define The Versioned Execution-Route And Evidence Lifecycle Contract

Goal: Make execution routing a model-and-endpoint-specific decision with
explicit evidence states.

Main actions:

- Specify a versioned `ExecutionRoute` contract containing provider, model,
  endpoint identity, protocol adapter/version, driver, authority, tool mode,
  context/reasoning policy, fallback targets, and evidence references.
- Define promotion states at minimum: `documented`, `adapter_dry_run_passed`,
  `provider_smoke_passed`, `tool_contract_passed`,
  `coding_route_verified`, and `default_route_eligible`.
- Define expiration/revalidation rules for endpoint or model drift and a
  conservative downgrade path when evidence is missing.

Acceptance criteria:

- The contract prevents a provider-wide flag from promoting all models.
- Every execution route has an explicit driver and authority ceiling.
- Evidence state, source provenance, verification date, and expiry behavior are
  machine-representable without storing secrets.

Status: completed

### 4. Refactor Provider, Model, Endpoint, And Route Ownership

Goal: Align the existing registry and model catalog with the new ownership
contract without losing existing compatible routes.

Main actions:

- Keep long-lived provider facts in `ProviderProfile`; move or derive
  model-specific and endpoint-specific choices from the new contracts.
- Make `runtime_backend` an evidence-qualified route choice rather than an
  unconditional provider default where current implementation permits it.
- Add migration/compatibility handling so existing user profiles and saved
  tasks continue to resolve to a safe route.

Acceptance criteria:

- The route resolver cannot silently grant a model more authority than its
  recorded evidence allows.
- Existing supported profiles resolve deterministically with a visible safe
  fallback or warning.
- Focused catalog, router, and migration tests pass.

Status: completed

### 5. Harden Protocol Adapters And Build A Semantic Conformance Corpus

Goal: Verify provider behavior at the wire and normalized-semantic layers,
not just through OpenAI-compatible request success.

Main actions:

- Expand transport fixtures for messages, system instructions, tools,
  tool-result turns, reasoning controls, attachments, streaming, cancellation,
  error responses, and malformed outputs.
- Preserve adapter-specific behavior for Qwen, DeepSeek, Kimi, and GLM while
  preventing protocol quirks from leaking upward into the common coding event
  contract.
- Add a native-protocol adapter design only when a target provider requires it;
  do not add speculative adapters solely for architectural symmetry.

Acceptance criteria:

- Each supported route has deterministic request/response and stream/cancel
  conformance fixtures.
- Transport conformance distinguishes textual success from coding-agent-safe
  semantics.
- Unsupported protocol features fail closed with an actionable downgrade.

Status: completed

### 6. Formalize Neutral Transcript And Reasoning-Artifact Provenance

Goal: Preserve task continuity safely while making artifact replay rules
explicit and auditable.

Main actions:

- Version the neutral transcript schema for user intent, visible assistant
  output, tool call/result summaries, checkpoints, task state, and artifact
  lineage.
- Add issuer, endpoint, model, turn/call lineage, replayability, retention,
  and redaction semantics for reasoning artifacts.
- Keep cross-provider handoff on fresh isolated threads and allow native
  artifact replay only when the issuer and target contract explicitly permit
  it.

Acceptance criteria:

- Cross-provider packets contain no opaque provider-private state or secrets.
- Same-provider replay cannot occur when artifact provenance is incomplete or
  stale.
- Regression tests prove safe summary continuity, tool-pair integrity, and
  explicit artifact drops.

Status: completed

### 7. Introduce A Tool Action Envelope And Side-Effect Receipt Ledger

Goal: Prevent malformed calls, retries, handoffs, or provider timeouts from
duplicating commands or workspace edits.

Main actions:

- Separate tool-call repair from tool authorization and execution.
- Require schema-valid normalized arguments, authority decision, task/turn
  lineage, idempotency key, workspace/checkpoint version, execution result,
  and durable receipt for side-effecting tools.
- Define repairable, retryable, terminal, and user-approval-required tool
  states; malformed side-effect requests must not silently execute.

Acceptance criteria:

- A route cannot execute a side-effecting tool from an unvalidated `raw`
  argument wrapper.
- Retry and handoff logic can determine whether a tool action already applied.
- File-edit and command tests cover duplicate, timeout, interrupted, and
  recovery cases.

Status: completed

### 8. Make Fallback, Retry, And Handoff A Transactional Turn State Machine

Goal: Turn failure recommendations into safe execution transitions across
Codex and external-provider lanes.

Main actions:

- Define transition stages: snapshot, receipt check, neutral projection,
  capability downgrade, target-route admission, fresh/reused lane start, and
  user-visible completion or failure.
- Integrate failure taxonomy, retry/backoff, context compaction, reasoning
  downgrade, and model/provider fallback with the tool receipt ledger.
- Preserve existing graph-run retry behavior while aligning ordinary turns to
  the same safety semantics.

Acceptance criteria:

- A failed turn cannot silently replay an already executed side effect.
- Every fallback records semantic loss, target route, and recovery evidence.
- Fault tests cover rate limit, context failure, missing thread, interrupted
  stream, provider timeout, and unsupported tool/reasoning paths.

Status: completed

### 9. Make Context Budgeting And Compaction Endpoint-Aware

Goal: Keep long coding tasks truthful and recoverable across different model
limits and protocol overheads.

Main actions:

- Extend the current context budget with endpoint/model token accounting,
  tool-schema cost, attachment/modality cost, output reserve, and safe
  reasoning-artifact policy.
- Define compaction inputs, summary trust boundaries, provenance, and target
  route compatibility.
- Refuse or downgrade a route when preflight cannot establish a safe context
  budget instead of relying on an optimistic advertised window.

Acceptance criteria:

- Context reports identify the calculation basis and all dropped/truncated
  sections.
- At least one long-context test proves preflight, compaction, and handoff
  behavior for a constrained route.
- User-visible status distinguishes advertised capacity from verified usable
  coding context.

Status: completed

### 10. Extend The Agentic Update Pipeline With Route-Promotion Gates

Goal: Ensure self-upgrade improves facts safely without automatically
upgrading agent authority.

Main actions:

- Extend proposal/diff/risk artifacts to include execution-route and evidence
  lifecycle changes, adapter-version changes, and de-promotion/expiry events.
- Require route-specific dry-run and, when explicitly authorized,
  provider-backed smoke before tool/coding-route promotion.
- Add rollback behavior that can revoke a route or downgrade it to
  preview/review mode without removing documented model metadata.

Acceptance criteria:

- A model discovery run can add Kimi K3-like factual metadata while leaving it
  non-agent-ready until the required gates pass.
- Promotion, downgrade, expiry, and rollback have secret-free durable records.
- Existing proposal-first, explicit-authorization, and rollback guarantees
  remain intact.

Status: completed

### 11. Enforce Runtime Admission And Explain Degradation In The Product

Goal: Make selected route, authority, and degradation visible and enforceable
at task start, not only in diagnostics.

Main actions:

- Route all provider/model selections through the execution-route admission
  gate before exposing autonomous tools or default placement.
- Surface clear distinctions among Codex-native, provider-native,
  preview/review-only, reduced-authority, blocked, and fallback states.
- Preserve user intent on model selection while requiring confirmation when a
  route loses tool, modality, reasoning, or continuity semantics.

Acceptance criteria:

- UI/API runtime status cannot overclaim a route's authority.
- A user can understand why a requested model was downgraded or handed off.
- Focused desktop/sidecar tests cover admission and status projection.

Status: completed

### 12. Run The Controlled Four-Provider/Kimi K3 Reference Cohort

Goal: Validate the generic contracts with a bounded representative cohort,
not an uncontrolled all-model retest.

Main actions:

- Select one representative route each for Qwen, DeepSeek, Kimi K3, and GLM,
  plus Codex-native control behavior where needed for comparison.
- Run deterministic conformance, neutral-handoff, tool receipt, fallback, and
  context tests; run a live smoke only if specifically authorized in that
  execution turn.
- Preserve secret-free reports that classify each route as verified, partial,
  reduced-authority, blocked, or deferred.

Acceptance criteria:

- The cohort produces route-level evidence rather than provider-wide claims.
- Kimi K3 proves or refutes the generic promotion path without a Kimi-only
  bypass.
- Any unsupported lane is visibly downgraded with an exact next fix target.

Status: completed

### 13. Close The Adaptation Upgrade Slice And Hand Back To Product Hardening

Goal: Produce a durable closure decision and feed the parent hardening plan.

Main actions:

- Run focused regression, compatibility, secret-scan, diff, and recovery
  checks for all files changed by this plan.
- Publish an operator-facing route/runbook update and a concise residual-risk
  report under the existing evidence roots.
- Update the parent hardening plan only with the evidence-backed outcome and
  the exact relevant next parent work unit.

Acceptance criteria:

- Verified, reduced-authority, blocked, and deferred route states are explicit.
- The parent plan receives a concrete evidence reference rather than a vague
  completion claim.
- A future agent can start the next maintenance or hardening task without
  reconstructing this conversation.

Status: completed

## Progress Log

### 2026-07-27 - Step 0

- Completed: Created this durable, narrow upgrade plan for Codex-core
  multi-provider adaptation. The plan records the user direction that Codex is
  AstraBridge's core and Hermes is a reference architecture only.
- Evidence inspected: `providers/profile.py`, `providers/transports/`,
  `providers/ir.py`, `providers/history_projector.py`,
  `providers/runtime_transition.py`, `providers/tooling/`,
  `coding_kernel/turn_loop.py`, `coding_kernel/context_budget.py`,
  `runtime_service.py`, `router_service.py`, the provider transport/handoff/
  tool compatibility tests, `docs/AGENTIC_UPDATE_PIPELINE_RUNBOOK.md`,
  `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`,
  `PLAN/AGENTIC_UPDATE_PIPELINE_EXECUTION_PLAN.md`, and
  `PLAN/ASTRABRIDGE_MULTI_PROVIDER_STABILITY_HARDENING_HANDOFF_PLAN.md`.
- Baseline finding: AstraBridge already has provider profiles, four
  provider-family transports, normalized responses, safe history projection,
  authority-gated native coding tools, edit/checkpoint policy, failure
  taxonomy, and a proposal-first update pipeline. The highest-leverage gaps
  are execution-route ownership, evidence lifecycle, tool side-effect receipts,
  transactional fallback, and endpoint-aware context semantics.
- Route change: No existing plan or validated implementation was replaced.
  This new bounded plan supplies the provider-adaptation execution path that
  the broader stability plan intentionally leaves at a higher product level.
- What must not be weakened: Codex's core role; cross-provider private-state
  isolation; explicit authorization for live calls; proposal-first upgrades;
  authority-gated tools; secret-free evidence; and one shared event/delivery
  vocabulary.
- Validation: Read the durable-handoff-plan skill and template; checked the
  existing parent/update plans to avoid a work reset or duplicate broad
  scheduler; confirmed the plan names one current work unit and gives every
  future step observable acceptance criteria.
- Blockers: None.
- Next step: Step 1, Freeze The Codex-Core Multi-Provider Execution Contract.

### 2026-07-27 - Step 1

- Completed: Landed
  `PLAN/CODEX_CORE_MULTI_PROVIDER_EXECUTION_CONTRACT.md`, a versioned
  contract that establishes Codex/App Server as the core runtime boundary,
  separates native-provider and preview/review routes, assigns the current
  owner surfaces, and defines evidence-qualified route admission.
- Files changed:
  `PLAN/CODEX_CORE_MULTI_PROVIDER_EXECUTION_CONTRACT.md` and
  `PLAN/ASTRABRIDGE_MULTI_PROVIDER_ADAPTATION_UPGRADE_HANDOFF_PLAN.md`.
- Validation: Checked all required contract headings, every referenced core
  owner file/test path, Codex-core and fail-closed requirements, no trailing
  whitespace, and no raw secret-like pattern. Repository evidence confirmed
  the contract baseline: provider profiles/transports, normalized responses,
  neutral cross-provider handoff, authority-gated native loop, and
  proposal-first update controls.
- Blockers: None.
- Next step: Step 2, Produce A Current Route And Semantic-Gap Baseline.

### 2026-07-27 - Step 2

- Completed: Preserved a four-provider representative route matrix and
  risk-ranked owner queue in
  PRIVATE/provider-compatibility/runs/step2-codex-core-route-baseline-20260727/route-semantic-baseline.json
  and
  PRIVATE/provider-compatibility/reports/step2-codex-core-route-semantic-gap-baseline-20260727.md.
- Files changed: the two Step 2 evidence artifacts and
  PLAN/ASTRABRIDGE_MULTI_PROVIDER_ADAPTATION_UPGRADE_HANDOFF_PLAN.md.
- Validation: Ran the focused transport/handoff/tool/failure suite (21 tests,
  all passed). Ran the new secret-free, no-network, no-provider-call dry-run
  matrix for Qwen, DeepSeek, Kimi, and GLM; it preserved 17 partial and 75
  blocked capability entries rather than overclaiming them. Parsed the Step 2
  matrix, checked all eight risk owners and cited evidence artifacts exist,
  and confirmed JSON/report syntax, whitespace, and raw secret-like scans.
- Baseline verdict: four dedicated adapters and the common safety primitives
  are repository-proven, while no representative route is eligible for default
  autonomous coding. Kimi K3 has a bounded managed health pass only and remains
  a generic reference case pending tool, recovery, and route evidence.
- Blockers: None.
- Next step: Step 3, Define The Versioned Execution-Route And Evidence
  Lifecycle Contract.

### 2026-07-27 - Step 3

- Completed: Landed the versioned, side-effect-free execution-route contract
  in `apps/astrabridge-sidecar/astrabridge_sidecar/providers/execution_route.py`
  and exported it through `providers/__init__.py`. It binds provider, model,
  endpoint fingerprint, adapter signature, configured/effective driver,
  authority ceiling, tool mode, context/reasoning policy, fallback targets,
  provenance, evidence references, verification time, and expiry without
  storing credentials.
- Safety result: Missing, generic, malformed, drifted, or expired evidence
  always de-promotes to `documented` / authority `C` / `preview_review`.
  A provider-wide backend, a generic capability snapshot, or metadata such as
  `last_verified_at` cannot promote an individual model. Only exact current
  model-and-endpoint evidence may admit a non-default route, and only explicit
  `default_route_eligible` evidence may make it a default route.
- Files changed: the new route module and focused test module,
  `providers/__init__.py`,
  `tests/test_provider_capability_snapshot.py`, and
  `PRIVATE/provider-compatibility/reports/step3-execution-route-contract-validation-20260727.md`.
- Validation: Passed 33 focused tests across route contract, transport,
  handoff, tool, failure-taxonomy, and capability-snapshot coverage; passed
  Python byte-compilation, scoped whitespace/diff checks, and a
  high-confidence secret-pattern scan. The existing snapshot test now uses a
  test-runtime current timestamp rather than a stale fixed date; its explicit
  expired-evidence test remains intact. No live provider calls, network access,
  credentials, or desktop key files were used.
- Deliberate boundary: This step does not yet make catalog/router/runtime
  selection consume the new route contract. Step 4 owns that migration and
  must preserve this fail-closed result for existing profiles and tasks.
- Blockers: None.
- Next step: Step 4, Refactor Provider, Model, Endpoint, And Route Ownership.

### 2026-07-27 - Step 4

- Completed: Routed catalog, router-config, and router profile resolution
  through the versioned execution-route contract. Provider-level
  `runtime_backend` is now retained as a configured candidate while the
  effective backend, authority, tool mode, warning, and default eligibility
  come from current model-and-endpoint evidence.
- Safety result: Canonical stored proof retains its original subject binding,
  so endpoint or adapter drift de-promotes the route rather than self-healing
  on reload. Missing/generic/unsafe proof remains review-only; a plain-text
  preview stays available, but supplied tool definitions are rejected until
  exact coding-route evidence exists. Default and recommended catalog placement
  now additionally require explicit `default_route_eligible` evidence.
- Files changed:
  `providers/execution_route.py`, `providers/__init__.py`,
  `router_config_service.py`, `router_service.py`,
  `model_catalog/catalog.py`,
  `provider_capability_verification_gate_baseline.json`,
  `tests/test_execution_route_ownership.py`,
  `PRIVATE/provider-compatibility/reports/step4-route-ownership-migration-validation-20260727.md`,
  and this plan.
- Validation: Passed the five ownership regressions, the two capability-gate
  regressions, the focused dry-run matrix assertion, and the combined focused
  route/catalog/router/transport/handoff/tool/source/reasoning/snapshot suite;
  byte-compilation passed for all changed route/config/router/catalog modules.
  The capability baseline now explicitly accepts the Kimi K3
  `reasoning=off` dry-run rejection because K3 is always-thinking. No live
  provider calls, network access, credentials, desktop key files, or live
  route promotion were used. See
  `PRIVATE/provider-compatibility/reports/step4-route-ownership-migration-validation-20260727.md`.
- Blockers: None.
- Next step: Step 5, Harden Protocol Adapters And Build A Semantic Conformance
  Corpus.

### 2026-07-27 - Step 5

- Completed: Added the versioned, deterministic four-provider semantic
  conformance corpus in
  `tests/fixtures/provider_semantic_conformance_v1.json` and its focused
  harness in `tests/test_provider_semantic_conformance_corpus.py`. Each Qwen,
  DeepSeek, Kimi, and GLM case now exercises instructions, messages, tools,
  tool-result turns, reasoning controls, a normalized response, stream events,
  cancellation metadata, and an error classification.
- Runtime result: `ProviderTransport` now publishes a secret-free semantic
  contract that distinguishes wire/response normalization from coding-agent
  admission. Router previews expose that contract alongside the execution
  route; no-evidence routes remain review-only even when text/tool wire shapes
  are valid. DeepSeek/GLM image attachment requests fail before an upstream
  call with an actionable downgrade; Kimi K3's always-thinking constraint stays
  explicit; malformed output becomes a blocked semantic observation and an
  `invalid_response` stream status without retaining raw payload data.
- Compatibility result: Saved profile-scoped evidence now canonicalizes through
  the same exact model/endpoint/adapter proof storage boundary. It can enable a
  verified profile route only for its bound model and cannot promote a different
  model; unsafe proof references are removed before persistence. The local
  HTTP adapter integration fixtures now carry this exact proof rather than
  relying on a provider-wide default.
- Files changed: `profile_service.py`, `router_service.py`,
  `providers/transports/base.py`, the transport registry and four active
  provider transport modules, the new corpus fixture/test,
  `tests/test_execution_route_ownership.py`, targeted adapter fixtures in
  `tests/test_sidecar_services.py`,
  `PRIVATE/provider-compatibility/reports/step5-protocol-semantic-conformance-validation-20260727.md`,
  and this plan.
- Validation: 63 focused corpus/route/catalog/handoff/tool/snapshot tests
  passed; 22 local adapter integration/image/tool-pair/stream/reasoning tests
  passed; two capability-gate tests and one dry-run unsupported-lane test
  passed; Python byte-compilation passed. The HTTP fixtures use only loopback
  fake upstreams. No external provider request, user credential, desktop key
  file, or live route promotion was used. No native-protocol adapter was added,
  because the existing Responses and Chat Completions owners cover the proven
  active routes without a speculative third protocol family. See
  `PRIVATE/provider-compatibility/reports/step5-protocol-semantic-conformance-validation-20260727.md`.
- Blockers: None.
- Next step: Step 6, Formalize Neutral Transcript And Reasoning-Artifact
  Provenance.

### 2026-07-27 - Step 6

- Completed: Added the versioned neutral transcript contract in
  `providers/history_projector.py`. The durable transcript contains only safe
  user intent, visible assistant output, tool call/result summaries, task
  state, checkpoint references, and bounded lineage. Arbitrary source-entry
  fields are reduced through a whitelist before persistence.
- Replay safety: Reasoning artifacts now require explicit issuer provider/model,
  endpoint fingerprint, adapter signature, source thread/turn/item lineage,
  same-issuer endpoint/model scope, ephemeral retention, a current issuance and
  expiry window, an exact target-route match, and a target profile that supports
  native replay. Missing, malformed, mismatched, and stale provenance produce
  explicit secret-free drop records; cross-provider native replay is forbidden.
- Runtime result: Provider-handoff bundles now use v2 and embed
  `astrabridge-neutral-transcript-v1`. The task event stores only safe bundle
  schema/digest/count metadata, while the bundle keeps no opaque provider
  reasoning, provider response identifiers, signed thinking, or credentials.
  Runtime projection now also records tool-result lineage and repairs missing
  tool results as a visible continuity event.
- Files changed: `providers/history_projector.py`, `providers/__init__.py`,
  `runtime_service.py`, `task_service.py`, new
  `tests/test_neutral_transcript_provenance.py`, updated handoff/history
  regressions, `PRIVATE/provider-compatibility/reports/step6-neutral-transcript-provenance-validation-20260727.md`,
  and this plan.
- Validation: Three new provenance/transcript tests, three handoff compatibility
  tests, and six existing history-projector tests passed. The combined semantic
  corpus/transport/route/catalog/handoff/tool/capability suite passed 66 tests.
  Byte-compilation, whitespace checks, and focused source/test secret scans
  passed. No external provider request, credential, desktop key file, or live
  model promotion was used.
- Blockers: None.
- Next step: Step 7, Introduce A Tool Action Envelope And Side-Effect Receipt
  Ledger.

### 2026-07-27 - Step 7

- Completed: Added the versioned tool-action envelope and workspace-local
  durable receipt ledger in `tool_action_ledger.py`. Every native side effect
  now requires strict normalized arguments, authority, task/turn/tool-call
  lineage, a stable idempotency key, workspace/checkpoint version, result
  summary, and a secret-free durable receipt.
- Safety result: Transport repair wrappers containing `raw` are rejected before
  dispatch. The native loop returns a repairable tool result rather than
  executing malformed arguments; the project-tool boundary repeats the check.
  Native model calls are rechecked for Tier A authority, while direct user/UI
  actions remain explicit distinct intents. Completed/terminal receipts
  deduplicate; timeouts and post-admission interruptions fail closed pending an
  explicit recovery resolution.
- Files changed: `tool_action_ledger.py`, `coding_kernel/turn_loop.py`,
  `project_tools_service.py`,
  `tests/test_tool_action_receipt_ledger.py`,
  `PRIVATE/provider-compatibility/reports/step7-tool-action-envelope-validation-20260727.md`,
  and this plan.
- Validation: The new receipt suite plus existing tool compatibility suite
  passed 23 tests; the combined semantic/transport/route/catalog/handoff/
  transcript/tool suite passed 55 tests; project edit, release-workflow, and
  native-kernel focused regressions passed 3, 2, and 12 tests respectively.
  Byte-compilation, scoped diff/whitespace checks, and a focused secret scan
  passed. No live provider call, network access, credential, desktop key file,
  or live model promotion was used.
- Blockers: None.
- Next step: Step 8, Make Fallback, Retry, And Handoff A Transactional Turn
  State Machine.

### 2026-07-27 - Step 8

- Completed: Added the versioned `astrabridge-turn-transition-v1` state
  machine in `providers/turn_transition.py` and connected it to ordinary
  `start_turn`, native turns, fresh/reused provider lanes, same-runtime forks,
  missing-thread recovery, and graph retry starts.
- Safety result: The transition checks secret-free source-lineage receipt
  references before runtime preparation or target-lane creation. `executing`,
  `interrupted`, and `recovery_required` receipts stop the transition pending
  explicit action recovery; no provider call, fork, target reuse, or tool
  replay is silently attempted. Every completed handoff keeps a compact record
  of semantic loss, route admission, retry/backoff advisory, and recovery
  evidence.
- Graph result: The direct live graph manifest now persists resolved
  `dispatch_control`, preventing the dispatch controller from interpreting an
  omitted limit set as zero available graph slots. Existing fanout/fanin graph
  dispatch and durable worker-handoff regression coverage passed.
- Files changed: `providers/turn_transition.py`, `providers/__init__.py`,
  `tool_action_ledger.py`, `project_tools_service.py`, `task_service.py`,
  `runtime_service.py`, the new
  `tests/test_transactional_turn_state_machine.py`,
  `PRIVATE/provider-compatibility/reports/step8-transactional-turn-state-machine-validation-20260727.md`,
  and this plan.
- Validation: Passed 24 focused transition/receipt/handoff/failure tests, 16
  start-turn/native regressions, and the live graph fanout/fanin regression;
  Python byte-compilation, scoped diff checks, and a focused high-confidence
  secret scan passed. No live provider call, network access, credential,
  vault, desktop key file, or route promotion was used.
- Boundary: Step 8 records compaction and reasoning-downgrade advice but does
  not calculate endpoint-specific budgets (Step 9) or broaden configured route
  evidence into runtime admission authority (Step 11).
- Blockers: None.
- Next step: Step 9, Make Context Budgeting And Compaction Endpoint-Aware.

### 2026-07-27 - Step 9

- Completed: Replaced the model-window-only context report with
  `astrabridge-context-budget-v2`. It records advertised capacity, endpoint
  protocol/fingerprint envelope, tool-schema and attachment costs, existing
  thread use, output reserve, safe reasoning-artifact policy, calculated
  capacity, and whether usable coding context is verified or conservative.
- Safety result: Unknown endpoint/window budgets select no injected context and
  visibly downgrade; insufficient usable budgets block before a provider call.
  User-authored text is never silently truncated. Later injected project/asset
  context may be deterministically compacted only with a secret-free report of
  every dropped/truncated section.
- Handoff result: Added
  `astrabridge-context-compaction-handoff-v1` to durable provider handoff
  bundles. It binds source/target route identity and context-report digests,
  budgets a neutral summary, and explicitly excludes opaque reasoning,
  provider-private state, raw tool payloads, response identifiers, and
  credentials from cross-route continuity.
- Files changed: `coding_kernel/context_budget.py`, new
  `coding_kernel/context_compaction.py`, coding-kernel exports and native
  turn input handling, `runtime_service.py`, `project_context_service.py`,
  `runtime_config_service.py`, `model_catalog/catalog.py`,
  `task_service.py`, `providers/runtime_transition.py`, the compact validation
  harness, focused context/handoff regressions, new
  `tests/test_endpoint_aware_context_budget.py`,
  `PRIVATE/provider-compatibility/reports/step9-endpoint-aware-context-budgeting-validation-20260727.md`,
  and this plan.
- Validation: Passed 4 new endpoint-aware budget tests, 7 context-gate tests,
  3 provider-handoff tests, 3 neutral-transcript provenance tests, 16
  start-turn/native regressions, and 2 target-model context/handoff
  regressions. Byte-compilation, diff checks, and a focused high-confidence
  secret scan passed. No live provider call, network call, credential, desktop
  key file, vault read, or route promotion was used.
- Blockers: None.
- Next step: Step 10, Extend The Agentic Update Pipeline With Route-Promotion
  Gates.

### 2026-07-27 - Step 10

- Completed: Added the versioned secret-free route-promotion section and
  lifecycle records to the agentic-update proposal/diff/artifact pipeline.
  Documentation produces a `documented` record only; a non-documentation
  promotion must bind the exact provider/model/native-model, endpoint
  fingerprint, and adapter signature, then advance one evidence state at a
  time.
- Metadata-first result: New documented Kimi K3-like facts can be staged with
  manual approval even when long-context or modality claims still need a
  provider smoke. The apply manifest records that this is metadata without
  execution-route authority, and no `execution_route_evidence` is persisted;
  the route remains review-only.
- Gate/result: Added route-specific dry-run and provider-smoke gate types.
  Provider, tool-contract, coding-route, and default-route promotions require
  explicit provider-call authorization plus actual provider-backed,
  exact-subject evidence. Fixture evidence and a missing route smoke runner
  fail closed. The new `execution_routes` supervised track is manual-only and
  cannot silently auto-promote authority.
- Recovery/result: Promotion, de-promotion, adapter drift, endpoint drift,
  expiry, and rollback write distinct secret-free lifecycle, apply-ledger, and
  rollback records. A route change re-binds the proof to current router state
  before storage; rollback restores prior evidence/documented state without
  removing model metadata.
- Files changed: new `agentic_updates/route_promotion.py`, update proposal,
  diff, validation, isolated apply/rollback, artifact, service, and API
  wiring; new `tests/test_agentic_update_route_promotion.py`; and
  `PRIVATE/provider-compatibility/reports/step10-route-promotion-gates-validation-20260727.md`.
- Validation: Six new route-promotion tests passed; 65 focused
  proposal/update/artifact/automation/execution-route tests passed; 32 parser,
  discovery, fixture-dogfood, kernel, and provider-smoke regressions passed;
  sidecar/transport/tool/catalog regressions and byte compilation passed.
  Scoped `git diff --check` and a literal-secret scan passed. No provider
  request, credential/key/vault/desktop-key read, or live route promotion was
  used.
- Blockers: None. Route-specific live smoke execution intentionally remains
  blocked unless a later explicitly authorized run supplies its secret-owning
  provider runner; Step 12 owns that controlled cohort.
- Next step: Step 11, Enforce Runtime Admission And Explain Degradation In The
  Product.

### 2026-07-27 - Step 11

- Completed: Added the versioned, secret-free
  `astrabridge-runtime-route-admission-v1` contract and made it authoritative
  at thread creation, asynchronous thread creation, fork, graph worker start,
  and turn start. The exact selected model is overlaid from router catalog
  facts before runtime preparation, so one model cannot inherit a sibling's
  stronger route evidence.
- Product result: Review-only/reduced routes require explicit confirmation and
  then run only as `no_tools`/`ask`; disabled, modality-incompatible, native
  feature-disabled, and unsupported thread-host paths block before provider
  setup. Cross-provider continuity and reasoning mappings are explicit. A
  non-default route cannot promote the project default. Fallback targets are
  informational and never automatic.
- API/UI result: Added a metadata-only admission preflight that does not inject
  credentials or start a runtime lane, structured admission errors, composer
  route status, and a keyboard-accessible confirmation/block dialog that
  preserves the user's selected model and draft.
- Compatibility result: Embedded legacy callers retain an existing native
  kernel host only for the exact same provider/model, without any proof or
  default-eligibility claim. This restored six focused native-kernel runtime
  regressions after the admission boundary was introduced.
- Evidence: `PRIVATE/provider-compatibility/reports/step11-runtime-admission-degradation-validation-20260727.md`.
- Validation: Python byte-compilation; 30 focused route/ownership/promotion/
  admission/API tests; 6 native-kernel regressions; one focused graph-worker
  MCP-policy regression; desktop TypeScript compilation; and 8 focused desktop
  tests passed. Scoped diff and credential-literal scans passed. No live
  provider call, credential/key/vault/desktop-key read, route promotion, or
  metadata upgrade was used.
- Residual regression boundary: The full 390-test sidecar suite has 7 known
  failures in existing Kimi metadata, project-context-pack, and provider
  thread-reuse cases. Broader graph-runtime validation also contains unrelated
  graph-contract/durable-delivery/failure-reconciliation cases. Neither was
  widened into this one-step runtime-admission slice.
- Blockers: None for Step 11 acceptance. Step 12 live smoke remains gated by
  explicit authorization and a secret-owning runner.
- Next step: Step 12, Run The Controlled Four-Provider/Kimi K3 Reference
  Cohort.

### 2026-07-27 - Step 12

- Completed: Added a deterministic, provider-free reference-cohort builder and
  runner that persist a normalized run contract before creating evidence. The
  cohort binds one exact catalog route each for `qwen/qwen3.7-plus`,
  `deepseek/deepseek-v4-pro`, `kimi/kimi-k3`, and `glm/glm-5.2`, with
  `openai/gpt-5.5` recorded only as a Codex/App Server comparison control.
- Route result: All four external routes passed semantic-conformance,
  neutral-handoff, local receipt-ledger, explicit-fallback, and endpoint-aware
  context checks. Each remains `documented` / `review_only` and is therefore
  explicitly classified `reduced_authority` with `no_tools` / `ask`, rather
  than being promoted from fixture evidence. The exact next gate for every
  route is `execution_route_adapter_dry_run`.
- Kimi K3 result: The generic promotion-path check passed with
  `kimi_only_bypass: false`; K3 still requires adapter dry-run, specifically
  authorized provider smoke, tool-contract evidence, coding-route
  verification, and default-route eligibility before any stronger admission.
- Evidence: `PRIVATE/provider-compatibility/reports/step12-controlled-four-provider-kimi-k3-reference-cohort-20260727.md` and
  `PRIVATE/agentic-update-pipeline/runs/step12-four-provider-reference-cohort-20260727-r5/`.
- Validation: The final deterministic runner passed; 52 focused cohort,
  semantic-corpus, neutral-transcript, receipt-ledger, transactional-turn,
  endpoint-aware-context, promotion, catalog, and source-registry tests
  passed; byte compilation, secret-literal scan, and whitespace scan passed.
  No network request, provider call, desktop secret-file read, vault read, or
  route promotion occurred.
- Blockers: None for deterministic cohort acceptance. Live smoke remains
  deferred until a future current-turn explicit authorization and a
  secret-owning runner are supplied; the deferred status is not an implied
  authorization.
- Next step: Step 13, Close The Adaptation Upgrade Slice And Hand Back To
  Product Hardening.

### 2026-07-27 - Step 13

- Completed: Closed the bounded multi-provider adaptation slice with current
  no-live-provider regression evidence, a route-status operator procedure,
  residual-risk report, and an evidence-backed parent-plan handoff.
- Closure result: The final exact-route cohort keeps
  `qwen/qwen3.7-plus`, `deepseek/deepseek-v4-pro`, `kimi/kimi-k3`, and
  `glm/glm-5.2` at `documented` / `review_only` /
  `reduced_authority` with `no_tools` / `ask`. The route table explicitly
  records no verified, partial, or blocked selected route; provider smoke is a
  separately deferred, explicitly authorized action. Kimi K3 passed the
  generic lifecycle check with no Kimi-only bypass.
- Validation: The final provider capability gate passed 82 tests with no
  network/provider call; 97 focused adaptation regressions passed across
  route, semantic, handoff, receipt/recovery, context, promotion, admission,
  and transport contracts; TypeScript checking and 21 focused desktop
  route-status tests passed; route/catalog owner modules byte-compiled;
  secret-free payload guards, literal-secret/whitespace scans, and scoped diff
  checks passed.
- Visibility repair: The first Step 13 gate preserved a valid failure because
  the operator Markdown report hid matrix entries after the first 80. Updated
  `provider_capability_dry_run_matrix.py` to project every bounded matrix
  entry, then preserved a passing rerun. This changed report visibility only;
  it did not alter a capability claim or promote any route.
- Evidence: `PRIVATE/provider-compatibility/reports/step13-adaptation-upgrade-closure-20260727.md`,
  `PRIVATE/agentic-update-pipeline/runs/step13-provider-capability-closure-20260727-r2/`,
  and
  `PRIVATE/agentic-update-pipeline/runs/step13-four-provider-reference-cohort-closure-20260727-r1/`.
- Operator and parent handoff: Updated
  `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` with the exact route-admission
  procedure and recorded the closure evidence in
  `PLAN/ASTRABRIDGE_MULTI_PROVIDER_STABILITY_HARDENING_HANDOFF_PLAN.md`.
  Parent Step 1 remains the next work unit; no parent work was skipped or
  marked complete.
- Residual boundary: Live provider smoke, route/default promotion, and any
  plaintext-secret/vault read remain unperformed and require future explicit
  authorization. Prior unrelated full-suite residuals remain part of the
  parent hardening lane if reproducible.
- Next step: This plan is complete. Continue only from parent hardening Step
  1, Freeze Product Boundary And Stability Closure Contract.
