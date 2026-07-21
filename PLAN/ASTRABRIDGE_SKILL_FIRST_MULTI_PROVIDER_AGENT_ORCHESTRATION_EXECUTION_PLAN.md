# AstraBridge Skill-First Multi-Provider Agent Orchestration Execution Plan

## Plan Authority And Existing-Plan Relationship

This file is the durable execution control surface for the next AstraBridge
product-upgrade round focused on a skill-first route for:

- multi-provider, multi-model agent orchestration;
- MCP-unified multimodal, tool, and resource execution;
- code-authored and skill-authored orchestration over one canonical graph;
- bounded cross-provider and external-A2A interoperability;
- classic orchestration patterns packaged as reusable AstraBridge skills.

This is a plan-document expansion over existing validated work, not a work
reset. It preserves the current repository state and the completed or
authoritative baseline captured in:

- `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`
- `PLAN/ASTRABRIDGE_MULTI_PROVIDER_STABILITY_HARDENING_HANDOFF_PLAN.md`
- `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`
- `apps/astrabridge-sidecar/skills/agent-orchestration-operator/SKILL.md`

Those files remain evidence and baseline references. They are not the primary
next-step scheduler for this skill-first product-upgrade scope. Future work on
this exact track should continue from this file.

## Total Objective

Upgrade AstraBridge into a skill-first orchestration product for multi-provider
LLM agents where reusable orchestration patterns are defined, validated,
executed, and promoted through one canonical graph and one MCP-normalized
runtime surface before any new GUI authoring surface is attempted.

Concretely, this plan must produce a product path where:

1. classic orchestration patterns such as supervisor-worker, review-fix-verify,
   fanout-synthesis, provider-smoke, and multimodal adaptation can be shipped
   as AstraBridge skills or skill-backed presets rather than requiring a GUI;
2. every skill-backed orchestration compiles into the same canonical
   AstraBridge orchestration graph and runtime contract instead of inventing a
   second skill-only engine;
3. multimodal, tool, and resource execution still travel through MCP contracts,
   including first-party loopback paths;
4. cross-provider and cross-peer communication terminates in one
   AstraBridge-owned internal envelope and explicit A2A gateway boundary;
5. nested subagent behavior is disabled by default, total agent count and token
   budgets are bounded, and teammate communication remains explicit rather than
   emergent;
6. skills can express provider/model routing, typed input and output
   contracts, tool policy, approval policy, subagent policy, and artifact
   handoff without requiring direct GUI manipulation;
7. the above path is backed by lint, dry-run, runtime tests, evaluation
   bundles, promotion gates, and operator runbooks rather than product prose.

## Deliverables

- One durable skill-first execution source for this product-upgrade track.
- A frozen product-boundary contract for skill-backed orchestration, MCP-only
  execution, and no-new-GUI-in-this-track scope.
- A canonical skill-to-graph contract and packaging shape for orchestration
  skills and presets.
- A skill-backed orchestration preset library covering the first bounded set of
  classic orchestration patterns.
- One MCP tool surface for proposing, validating, dry-running, diffing, and
  launching skill-backed orchestration graphs.
- Runtime guardrails for total agents, graph depth, nested-subagent policy,
  per-provider concurrency, per-model concurrency, token budgets, retry
  budgets, and communication isolation.
- Cross-provider and external-A2A conformance evidence for skill-backed graph
  execution.
- Evaluation, dogfood, and promotion-gate evidence for the shipped
  skill-backed orchestration path.
- Operator and authoring runbooks that future agents can use without relying on
  chat history.

## Constraints And Attention Notes

1. Preserve `PLAN/ACTIVE_REPOSITORY_NORMALIZATION_EXECUTION.md`,
   `PLAN/AGENT_GRAPH_DYNAMIC_WORKFLOW_PRODUCTIZATION_PLAN.md`, and
   `PLAN/ASTRABRIDGE_PRODUCT_STABILITY_AND_INTEROPERABILITY_EXECUTION_PLAN.md`
   as historical or completed records.
2. Preserve `.abproj`, workspace-local `.astrabridge/`, `PRIVATE/**`, logs,
   validation reports, traces, screenshots, and non-secret raw experiment
   artifacts by default.
3. Never persist or stage API keys, bearer tokens, cookies, authorization
   headers, provider raw secrets, or unredacted peer credentials.
4. Do not create a second orchestration engine for skills. Skill-authored,
   code-authored, and imported orchestration must converge on one canonical
   graph plus one runtime.
5. Do not introduce provider-direct multimodal, tool, or resource execution
   paths that bypass MCP.
6. This plan explicitly defers net-new GUI authoring work. Existing GUI
   surfaces may be used only for compatibility inspection, evidence, or
   non-expanding operator flows when needed.
7. Default orchestration must stay shallow:
   - graph depth `2` is the normal maximum;
   - nested subagents are disabled by default;
   - deeper nesting requires explicit user approval and preserved evidence.
8. Do not allow unrestricted cross-agent messaging. Direct teammate messaging
   should remain off by default unless a bounded template explicitly requires
   it and the runtime contract supports it.
9. Do not claim a classic orchestration pattern is productized until it can be
   represented as a skill or preset, compiled, linted, dry-run validated, and
   executed through the canonical runtime.
10. Do not weaken provider truthfulness, downgrade semantics, approval gates,
    rollback expectations, or A2A gateway boundaries just to make skill
    authoring easier.
11. Before and after runtime-heavy development rounds, audit AstraBridge-owned
    listeners and stale launcher processes; reap only clearly owned stale
    processes.
12. Rewriting this plan from Step 0 is a plan-document reset, not a work
    reset. Carry forward validated repository evidence unless contradictory
    evidence appears.
13. Each execution turn under this plan should complete exactly one full
    numbered step, update Current Progress plus the Progress Log, and stop at
    the next clear entry point.

## Adjustment Policy

Agents may reasonably adjust substeps, filenames, commands, sequencing,
evidence layout, and implementation details when repository evidence requires
it. Adjustments must not:

- reintroduce a GUI-first route into this track;
- create a second graph or runtime truth for skills;
- weaken MCP, internal envelope, or A2A boundaries;
- turn bounded orchestration into unbounded recursive agent spawning;
- relax provider truthfulness or capability downgrade rules;
- replace runtime evidence with documentation-only claims;
- discard preserved evidence without contradictory proof.

If the current route becomes stale, record the blocker, evidence, attempted
paths, what must not be weakened, and the exact next step.

## Evidence Review And Plan Revision Policy

Before executing the next step, inspect the owner files, tests, and latest
preserved evidence for the relevant lane. Trigger a bounded plan review when:

1. repository code contradicts the assumed skill-first architecture;
2. the next step would create a parallel skill-only execution path instead of
   compiling into the canonical graph;
3. a claimed preset or skill pattern is backed only by documentation or
   examples rather than a canonical validation and runtime path;
4. the next step expands GUI scope while the actual blocker is still in skill
   contracts, runtime guardrails, provider compatibility, or MCP tooling;
5. repeated continuations are producing packaging or prose while the real
   blocker is budget enforcement, isolation, or runtime behavior;
6. provider, A2A, or MCP evidence shows that an intended preset pattern is not
   currently safe or truthful.

When triggered, revise minimally: record evidence, diagnosis, route change,
what must not be weakened, and the exact next step. Restore one executable work
unit rather than expanding documentation indefinitely.

## Execution Rules

1. Classify each future turn as planning mode or execution mode. Requests to
   continue, implement, advance, execute, fix, or resume default to execution
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

- Current status: Completed
- Completed steps: Step 0, Create Durable Skill-First Product Upgrade Plan;
  Step 1, Freeze Skill-First Product Boundary And Success Criteria;
  Step 2, Produce A Skill-First Baseline And Gap Report;
  Step 3, Define The Canonical Skill-To-Graph Contract;
  Step 4, Define The MCP Tool Surface For Skill-Backed Orchestration;
  Step 5, Package The First Skill Template Taxonomy;
  Step 6, Land The First Classic Orchestration Skill Templates;
  Step 7, Add Skill-To-Graph Lint, Diff, And Dry-Run Validation;
  Step 8, Enforce Runtime Guardrails And Anti-Explosion Limits;
  Step 9, Harden Typed Communication And Isolation Defaults;
  Step 10, Bind Provider Profiles And External A2A Cards;
  Step 11, Expose Skill-Backed Orchestration Through Canonical MCP Entry Points;
  Step 12, Build Evaluation And Promotion Gates For Skill-Backed Patterns;
  Step 13, Dogfood The Initial Skill Set In Real Product Workflows;
  Step 14, Publish Authoring And Operator Runbooks;
  Step 15, Run Final Skill-First Product Closure Gate
- Current step: Plan complete; next product track is skill productization and
  the existing product-stability shell-owner follow-up.
- Next step: Outside this numbered plan, productize the candidate manifests
  and resolve the shell-module budget gate before any live/provider-qualified
  promotion; keep GUI authoring deferred.
- Last updated: 2026-07-21

## Current Work Unit

- ID: step-15-final-skill-first-closure-gate
- Goal: Decide, using fresh repository evidence, whether the skill-first
  multi-provider orchestration path is stable enough to remain the current
  product upgrade track.
- Inputs: Steps 10-14 reports, the five skill manifests, canonical graph and
  MCP contracts, provider/A2A binding, runtime guardrails, evaluation gate,
  dogfood runner, authoring/operator runbooks, and release/promotion scripts.
- Expected output: One preserved final closure report that classifies every
  required surface as pass, blocked, or deferred and names the next product
  track without silently upgrading candidate/provider states.
- Acceptance check: fresh evaluation, promotion, dogfood, contract, focused
  regression, secret, and process-hygiene evidence is collected; the report
  verifies pattern set, MCP lifecycle, provider truthfulness, guardrails, A2A
  boundary, runbooks, and unsupported scope; plan status and next action are
  updated from the report.
- Status: completed
- Evidence: Final closure bundle under
  `PRIVATE/skill-first-orchestration/step15-closure/20260721/`, including the
  closure report and fresh evaluation, dogfood, readiness, promotion, contract,
  secret-scan, regression, and process-audit outputs.
- Next action: Continue in the product-stability shell-owner lane, then
  productize candidates and qualify provider/A2A routes through explicit
  approval and catalog evidence. Do not reopen GUI authoring in this track.

## Execution Steps

### 0. Create Durable Skill-First Product Upgrade Plan

Goal: Create the persistent execution contract for the skill-first
multi-provider orchestration upgrade track.

Main actions:

- Define the total objective, deliverables, constraints, adjustment policy,
  evidence-review policy, execution rules, and numbered steps.
- Preserve the relationship to existing Agent Graph and multi-provider
  hardening work.
- Leave an unambiguous next entry point.

Acceptance criteria:

- Plan file exists on disk.
- Plan preserves validated prior work instead of restarting it.
- Step 1 is explicitly identified as the next entry point.

Status: completed

### 1. Freeze Skill-First Product Boundary And Success Criteria

Goal: Lock the non-negotiable scope and success criteria for this skill-first
track.

Main actions:

- Write or update one contract artifact that freezes:
  - no new GUI authoring scope in this track;
  - one canonical graph and runtime for skills and code;
  - MCP-only multimodal/tool/resource execution;
  - one internal envelope plus explicit external-A2A boundary;
  - shallow orchestration, nested-subagent default deny, and budgeted runtime
    behavior.
- Define what counts as productized for a skill-backed orchestration pattern.
- Distinguish release-blocking violations from degradable warnings.

Acceptance criteria:

- One durable boundary contract exists on disk.
- The contract explicitly covers scope, graph ownership, MCP, envelopes, A2A,
  and runtime guardrails.
- Productized versus non-productized skill patterns are distinguishable.

Status: completed

### 2. Produce A Skill-First Baseline And Gap Report

Goal: Produce a source-backed baseline showing what already exists and what is
missing for skill-first orchestration productization.

Main actions:

- Inspect current orchestration graph, runtime scheduler, MCP surfaces,
  provider routing, A2A gateway, and skill packaging surfaces.
- Map current capabilities against the target skill-first shape.
- Save a gap report and identify the first contract blocker and first runtime
  blocker.

Acceptance criteria:

- A baseline report exists under a preserved evidence path.
- The report cites exact source files and distinguishes proven, partial,
  compatibility-only, and missing paths.
- The report names the next highest-leverage executable blocker.

Status: completed

### 3. Define The Canonical Skill-To-Graph Contract

Goal: Formalize how orchestration skills map into canonical graph structures
without creating a second engine.

Main actions:

- Define the minimum skill manifest and prompt structure needed to express:
  - node roles;
  - routing policy;
  - tool policy;
  - subagent policy;
  - typed input/output contracts;
  - handoff and artifact expectations.
- Define how a skill-backed preset resolves into a canonical graph file or
  graph payload.
- Define compatibility and migration rules.

Acceptance criteria:

- A contract artifact or code-backed schema exists on disk.
- The contract makes canonical graph ownership explicit.
- Review of the contract shows no parallel execution truth for skills.

Status: completed

### 4. Define The MCP Tool Surface For Skill-Backed Orchestration

Goal: Freeze one MCP-facing control surface for authoring and operating
skill-backed orchestration.

Main actions:

- Define the MCP operations for:
  - propose graph from skill or preset;
  - patch graph;
  - lint and validate;
  - dry-run;
  - diff;
  - launch;
  - inspect run state;
  - cancel or recover.
- Define required budget and guardrail fields on the launch path.
- Define fail-closed error behavior.

Acceptance criteria:

- One tool-surface contract exists on disk or in code.
- Launch and recovery operations require explicit bounded inputs.
- The surface does not permit hidden nested recursion or unbounded fan-out.

Status: completed

### 5. Package The First Skill Template Taxonomy

Goal: Choose and formalize the first bounded set of orchestration patterns to
 ship as skills or presets.

Main actions:

- Freeze the initial pattern set, expected use cases, and disallowed variants.
- Define per-pattern node topology, typed handoff expectations, approvals,
  artifact shapes, and budget defaults.
- Keep the set small enough to validate deeply before expansion.

Acceptance criteria:

- One durable taxonomy artifact exists on disk.
- The initial pattern set is finite, named, and bounded.
- Each pattern has explicit fit criteria and guardrails.

Status: completed

### 6. Land The First Classic Orchestration Skill Templates

Goal: Implement the first production candidate set of skill-backed
 orchestration templates.

Main actions:

- Implement the first template set, expected to include:
  - supervisor-worker-synthesizer;
  - review-fix-verify;
  - fanout-research-synthesis;
  - provider update smoke;
  - multimodal capability adapter.
- Ensure each template can emit or bind to a canonical graph payload.
- Preserve example outputs and template-specific validation artifacts.

Acceptance criteria:

- Each initial template exists as a skill or preset artifact.
- Each template resolves into a canonical graph representation.
- Template-level tests or validation fixtures pass.

Status: completed

### 7. Add Skill-To-Graph Lint, Diff, And Dry-Run Validation

Goal: Make skill-backed orchestration reviewable and safe before live runtime
 use.

Main actions:

- Extend or bind existing lint, diff, and dry-run checks to the skill-backed
  path.
- Preserve compiled-plan and validation evidence.
- Fail when a skill expands into an invalid or unsafe graph.

Acceptance criteria:

- A skill-backed orchestration can be linted, diffed, and dry-run validated.
- Invalid or unsafe expansions are rejected with actionable diagnostics.
- Validation evidence is preserved under a stable artifact layout.

Status: completed

### 8. Enforce Runtime Guardrails And Anti-Explosion Limits

Goal: Prevent token explosion, uncontrolled recursion, and communication
 ambiguity in skill-backed orchestration.

Main actions:

- Enforce limits for total agents, graph depth, nested-subagent default deny,
  max parallelism, per-provider concurrency, per-model concurrency, retry
  budget, and total token budget.
- Define how launch requests fail when limits are exceeded.
- Preserve guardrail decisions in run-policy snapshots.

Acceptance criteria:

- Runtime guardrail checks exist in code or contract-backed validation.
- Nested subagents are denied by default.
- Launches that exceed configured limits fail closed.

Status: completed

### 9. Harden Typed Communication And Isolation Defaults

Goal: Ensure skill-backed orchestration preserves explicit communication and
 context isolation.

Main actions:

- Enforce typed handoff contracts and artifact policies for skill-backed edges.
- Keep private-memory exclusion and teammate-isolation defaults intact.
- Ensure skills cannot silently request full-history context leakage.

Acceptance criteria:

- Tests or validation fixtures prove that only declared message parts and
  artifacts cross edges.
- Unsafe context sharing is rejected.
- Direct teammate messaging remains disabled by the current default runtime
  path; no skill can widen it implicitly.

Status: completed

### 10. Bind Provider Routing And External A2A Into The Skill Path

Goal: Make multi-provider routing and external peer interoperability first-class
 in skill-backed orchestration without leaking provider-specific shapes inward.

Main actions:

- Bind provider/model routing policy into skill-backed graph generation.
- Bind external A2A card references, trust levels, and gateway validation where
  patterns require them.
- Preserve downgrade semantics when routing or A2A trust is partial.

Acceptance criteria:

- Skill-backed graphs can declare bounded provider/model routing.
- External A2A usage, when present, resolves through the gateway boundary.
- Partial or downgraded capability states remain explicit and truthful.

Status: completed

### 11. Expose Skill-Backed Orchestration Through Canonical MCP Entry Points

Goal: Make skill-backed orchestration operable through one stable MCP surface.

Main actions:

- Implement or connect the MCP entry points frozen in Step 4.
- Ensure internal loopback paths still obey the same contract and guardrails.
- Preserve run, cancel, and recovery evidence for MCP-driven launches.

Acceptance criteria:

- At least one end-to-end skill-backed orchestration can be launched through
  the canonical MCP surface.
- Internal loopback launches use the same policy surface as external callers.
- MCP launch artifacts and runtime traces are preserved.

Status: completed

### 12. Build Evaluation And Promotion Gates For Skill-Backed Patterns

Goal: Prevent unvalidated orchestration skills from being treated as product
 features.

Main actions:

- Add evaluation packs for template validity, runtime stability, provider truth,
  guardrail enforcement, and A2A/MCP interoperability.
- Bind the most important checks into promotion or readiness gates.
- Preserve gate summaries and failure artifacts.

Acceptance criteria:

- A bounded evaluation suite exists for the initial pattern set.
- Promotion or readiness gates fail when a shipped skill pattern loses safety
  or truthfulness guarantees.
- Gate evidence is preserved under a stable path.

Status: completed

### 13. Dogfood The Initial Skill Set In Real Product Workflows

Goal: Prove that the initial skill-backed patterns help with real AstraBridge
 work rather than only synthetic fixtures.

Main actions:

- Choose bounded internal workflows that match the initial pattern set.
- Run them through the skill-backed path with preserved evidence.
- Record friction, missing contracts, and false assumptions.

Acceptance criteria:

- At least one bounded real workflow per major pattern family has preserved
  dogfood evidence.
- Dogfood findings distinguish product blockers from polish debt.
- Follow-up fixes are traceable to exact findings.

Status: completed

### 14. Publish Authoring And Operator Runbooks

Goal: Make the skill-first orchestration path usable by future agents and
 operators without chat reconstruction.

Main actions:

- Document how to choose a pattern, author or tailor a skill, validate it,
  launch it, inspect it, recover it, and interpret guardrail failures.
- Document what remains intentionally unsupported in the no-new-GUI track.
- Link the runbooks to the canonical contracts and tool surfaces.

Acceptance criteria:

- Durable runbooks exist on disk.
- The runbooks point to canonical contracts rather than parallel prose-only
  descriptions.
- Unsupported paths and escalation requirements are explicit.

Status: completed

### 15. Run Final Skill-First Product Closure Gate

Goal: Decide whether the skill-first orchestration path is stable enough to be
 treated as the current product upgrade track.

Main actions:

- Re-run the bounded evaluation, readiness, and dogfood checks.
- Verify the initial pattern set, MCP surface, provider truthfulness,
  guardrails, and A2A boundary remain consistent.
- Produce a closure verdict and explicit next-track recommendation.

Acceptance criteria:

- A final closure report exists on disk.
- The report distinguishes pass, blocked, and deferred items.
- The next product track after this plan is explicit: continue skill-first
  expansion, begin selective GUI surfacing, or hold on blockers.

Status: completed

## Progress Log

### 2026-07-21 - Step 0

- Completed: Created the durable skill-first product upgrade plan for
  multi-provider orchestration and MCP-unified interfaces.
- Files changed:
  `PLAN/ASTRABRIDGE_SKILL_FIRST_MULTI_PROVIDER_AGENT_ORCHESTRATION_EXECUTION_PLAN.md`
- Validation: Reviewed the durable-plan template, existing multi-provider
  hardening plan, completed Agent Graph productization plan, and current
  agent-orchestration skill surface before drafting this plan.
- Blockers: None.
- Next step: Step 1, Freeze Skill-First Product Boundary And Success
  Criteria.

### 2026-07-21 - Step 1

- Completed: Froze the skill-first product boundary in
  `PLAN/ASTRABRIDGE_SKILL_FIRST_ORCHESTRATION_BOUNDARY_CONTRACT.md`.
- Contract decisions: skills are authoring/reuse surfaces that compile into
  one canonical graph and runtime; MCP remains the only normal
  tool/resource/multimodal plane including loopback; internal envelopes and
  the external A2A gateway remain separate owners; GUI authoring is deferred;
  nested subagents and unrestricted teammate messaging are denied by default;
  finite agent/token/concurrency/retry limits and dry-run admission are
  mandatory.
- Product gate: Added explicit `candidate`, `validated`, `productized`,
  `provider-qualified`, and `external-a2a-qualified` levels, plus
  release-blocking versus degradable-warning rules.
- Files changed:
  `PLAN/ASTRABRIDGE_SKILL_FIRST_ORCHESTRATION_BOUNDARY_CONTRACT.md` and this
  plan's current-progress/status sections.
- Validation: Required-term and referenced-source checks passed for the
  boundary contract (283 lines, 13 required boundary terms, 8 source
  references); secret-like pattern scan passed; `git diff --check` passed for
  the plan update.
- Blockers: None. Numeric runtime cap defaults remain an implementation
  concern for Step 8, while the finite, explicit, fail-closed invariant is now
  frozen.
- Next step: Step 2, Produce A Skill-First Baseline And Gap Report.

### 2026-07-21 - Step 2

- Completed: Audited the canonical graph/compiler, graph examples and CLI,
  skill discovery/enablement and project presets, MCP broker and node policy,
  provider profiles/transports/client pool, internal protocol envelope,
  external A2A gateway/conformance, and durable graph scheduler.
- Evidence: Preserved the source-backed matrix and gap diagnosis in
  `PRIVATE/skill-first-orchestration/step2-baseline-gap/20260721/baseline-gap-report.md`.
- Validation: Six graph examples linted successfully; four dry-runs passed,
  one emitted an explicit route warning, and the provider-update pattern was
  blocked by its manual gate's zero timeout. The focused sidecar suites passed
  with 65 tests and 41 subtests. Report checks found 19 cited repository paths,
  all present, and no secret-like values.
- Findings: The first contract blocker is the missing machine-readable
  skill-to-graph manifest/resolver. The first runtime blocker is that graph
  lifecycle is HTTP/CLI-only while MCP has no skill-backed graph proposal,
  validation, launch, cancel, or recovery operation. A secondary Step 8 gap is
  that total-agent and per-skill budget fields are not yet part of graph
  admission even though nested agents, token presence, and dispatch capacity
  have existing protections.
- Files changed:
  `PRIVATE/skill-first-orchestration/step2-baseline-gap/20260721/baseline-gap-report.md`
  and this plan's current-progress/status sections.
- Blockers: None for the audit. The two concrete implementation blockers are
  carried into Steps 3, 4, 8, and 11; no parallel runtime route is authorized.
- Next step: Step 3, Define The Canonical Skill-To-Graph Contract.

### 2026-07-21 - Step 3

- Completed: Defined the normative skill-to-graph manifest, resolver result,
  policy precedence, composition limits, lifecycle statuses, failure semantics,
  and migration rules in
  `PLAN/ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md`.
- Machine-readable contract: Added the Draft 2020-12 schema at
  `PLAN/schemas/astrabridge-skill-to-graph-manifest-v1.schema.json`, including
  typed IO/artifact contracts, provider/model routing, MCP, approval,
  communication, subagent, budget, A2A, compatibility, and evidence policies.
- Evidence: Preserved validation output in
  `PRIVATE/skill-first-orchestration/step3-skill-to-graph-contract/20260721/contract-validation-report.md`.
- Validation: The schema parsed and passed Draft 2020-12 meta-schema checks;
  the reference manifest validated with zero errors and zero secret-like keys;
  the referenced `supervisor_worker_synthesizer` canonical graph linted with
  `status: pass` and matching graph schema/template identifiers.
- Blockers: None for the contract step. Resolver implementation, MCP graph
  lifecycle operations, and runtime cap enforcement remain intentionally
  assigned to Steps 4, 7, 8, and 11.
- Next step: Step 4, Define The MCP Tool Surface For Skill-Backed
  Orchestration.

### 2026-07-21 - Step 4

- Completed: Froze the single MCP control surface in
  `PLAN/ASTRABRIDGE_SKILL_BACKED_ORCHESTRATION_MCP_SURFACE_CONTRACT.md`.
  The surface defines nine tools: propose, patch, validate, dry-run, diff,
  launch, inspect, cancel, and recover. All operations remain behind the
  existing broker, canonical compiler, durable scheduler, run store, internal
  envelope, MCP policy, and A2A gateway owners.
- Machine-readable contract: Added
  `PLAN/schemas/astrabridge-skill-backed-orchestration-mcp-v1.schema.json`
  with typed request/response envelopes, resolution/provenance references,
  launch/recovery budgets, approval, dry-run receipts, idempotency, bounded
  inspection, and explicit recovery strategies.
- Evidence: Preserved validation output in
  `PRIVATE/skill-first-orchestration/step4-mcp-surface/20260721/mcp-surface-validation-report.md`.
- Validation: Draft 2020-12 schema and both reference blocks validated;
  9/9 operation fixtures passed; negative checks rejected missing budgets,
  empty recovery selection, nested subagents, and policy-widening patches;
  8 MCP core tests and 12 MCP broker tests passed. Tool catalog and six owner
  references were verified.
- Guardrail decisions: v1 launch/recovery requests require explicit finite
  budgets, approval, idempotency, and digest-bound dry-run receipts; depth is
  fixed at 2, nested subagents/direct teammate messaging are denied, and
  protocol ceilings are finite and lowerable by runtime/manifest policy.
- Blockers: None for the contract step. MCP implementation remains assigned
  to Step 11; runtime cap enforcement remains assigned to Step 8.
- Next step: Step 5, Package The First Skill Template Taxonomy.

### 2026-07-21 - Step 5

- Completed: Froze the finite v1 taxonomy in
  `PLAN/ASTRABRIDGE_SKILL_ORCHESTRATION_TEMPLATE_TAXONOMY.md`.
  The initial set contains exactly five patterns: supervisor-worker-
  synthesizer, review-fix-verify, fanout-research-synthesis, provider-update-
  smoke, and multimodal-capability-adapter. `document_extract_analyze_report`
  is deferred and `custom_blank_graph` remains a scaffold, not a skill.
- Per-pattern contract: Recorded canonical template IDs, topology and depth,
  fit criteria, typed port/artifact handoffs, MCP presets/effect classes,
  provider-routing evidence, approval requirements, taxonomy budget defaults,
  and disallowed variants for all five patterns.
- Evidence: Preserved validation output in
  `PRIVATE/skill-first-orchestration/step5-template-taxonomy/20260721/template-taxonomy-validation-report.md`.
- Validation: The machine-readable taxonomy summary parsed; all five graph
  examples linted and lowered successfully; all five compiled at depth 2 with
  expected maximum parallelism (1, 2, 2, 1, 1); every node retained typed
  input/output contracts and declared artifacts; dry-run-before-live policy
  and MCP/A2A/guardrail terms were present; secret-like key scan passed.
- Blockers: None for taxonomy definition. Skill manifest/preset implementation
  and resolver evidence remain assigned to Step 6.
- Next step: Step 6, Land The First Classic Orchestration Skill Templates.

### 2026-07-21 - Step 6

- Completed: Created five project-local skill packages under
  `apps/astrabridge-sidecar/skills/astrabridge-*`, each with a standard
  `SKILL.md`, `agents/openai.yaml`, and versioned
  `orchestration-manifest.json` using `resolution.mode: builtin_template`.
- Canonical bindings: Manifests map to
  `supervisor_worker_synthesizer`, `code_fix_test_review`,
  `fanout_fanin_research`, `provider_update_smoke_gate`, and
  `multimodal_capability_adapter`; no graph copy or skill-only scheduler was
  added.
- Evidence: Preserved validation output in
  `PRIVATE/skill-first-orchestration/step6-skill-templates/20260721/skill-template-validation-report.md`.
- Validation: `skill-creator` quick validation passed 5/5; manifest Draft
  2020-12 validation passed 5/5; canonical lint and compile passed 5/5 with
  depth 2 and expected parallelism; skill metadata and secret scans passed;
  focused registry/project-preset suites passed 12 tests and orchestration
  contract/compiler/file-format/SDK suites passed 25 tests. Four fixture
  dry-runs passed; the provider-update fixture remains explicitly blocked by
  its existing manual gate timeout `0`, which is preserved as a candidate
  blocker rather than a false pass.
- Policy boundary: `astrabridge_web` and `astrabridge_capabilities` refer to
  existing MCP presets. `astrabridge_workspace` is declared for workspace
  tools but remains a Step 11 implementation prerequisite before promotion.
- Blockers: None for candidate artifact creation. Workspace MCP exposure,
  skill-aware resolver/validation, runtime caps, and provider gate readiness
  remain assigned to Steps 7, 8, and 11.
- Next step: Step 7, Add Skill-To-Graph Lint, Diff, And Dry-Run Validation.

### 2026-07-21 - Step 7

- Completed: Added the skill-to-graph validation bridge in
  `apps/astrabridge-sidecar/astrabridge_sidecar/skill_orchestration_validation.py`.
  It resolves manifest paths or stable skill IDs through the canonical graph
  catalog, validates Draft 2020-12 manifest and parameter schemas, checks
  binding paths and fail-closed policy invariants, computes stable manifest and
  graph digests, and emits redacted provenance/evidence snapshots.
- Canonical reuse: Added `skill-lint`, `skill-compile`, `skill-dry-run`,
  `skill-validate`, and `skill-diff` CLI entry points. The bridge delegates
  graph checks to the existing file-format, compiler, lint, dry-run, and diff
  owners through an ephemeral canonical copy; no skill-only scheduler or live
  provider/MCP/agent path was introduced.
- Evidence: Preserved the validation report at
  `PRIVATE/skill-first-orchestration/step7-skill-graph-validation/20260721/skill-graph-validation-report.md`.
- Validation: The focused sidecar suites passed `56` tests. All five
  candidate skills resolved with stable digests; four lint/compile/dry-runs
  passed, while the provider-update dry-run retained its existing explicit
  manual-gate timeout blocker. Negative cases rejected missing/unknown
  parameters, unknown templates, unsafe nesting/bindings, policy widening,
  and secret-like content without echoing values. CLI JSON and markdown paths,
  Python compilation, and `git diff --check` passed.
- Boundary: Unknown `astrabridge_workspace` MCP references remain explicit
  warnings pending Step 11. This step does not claim runtime launch safety;
  agent-count/token/concurrency enforcement is the next runtime step.
- Blockers: None for the validation bridge. The provider smoke fixture remains
  intentionally blocked by its existing manual gate, and workspace MCP
  availability remains a Step 11 prerequisite.
- Next step: Step 8, Enforce Runtime Guardrails And Anti-Explosion Limits.

### 2026-07-21 - Step 8

- Completed: Added
  `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_guardrails.py` as the
  single fail-closed runtime admission evaluator. It enforces hard ceilings
  for graph/runtime depth, total agents, parallelism, total tokens, provider
  calls, retries, and provider/model concurrency; rejects nested subagents,
  direct teammate messaging, private-memory leakage, unrestricted history, and
  invalid typed communication policy; and emits a deterministic decision
  digest with redacted policy/provenance data.
- Canonical integration: Live queue admission and synchronous live execution
  call the evaluator after canonical compilation and before executor/provider
  dispatch. The queued and running `run_policy_snapshot` now preserves the
  guardrail decision. `GraphDispatchController` enforces route-specific
  provider/model limits, retry limits, and monotonic per-run provider-call
  usage; the existing scheduler/token allocator remains the execution owner.
- Compatibility: Legacy `limits.total_tokens` requests receive bounded,
  explicitly recorded compatibility-derived limits. Skill/resolution/strict
  requests require complete finite budget fields. No skill-only scheduler or
  provider-direct path was introduced.
- Evidence: Preserved validation at
  `PRIVATE/skill-first-orchestration/step8-runtime-guardrails/20260721/runtime-guardrails-validation-report.md`.
- Validation: New guardrail/dispatch/skill suites passed `19` tests; five
  focused scheduler admission/retry/concurrency/typed-handoff tests passed;
  three subgraph/local-executor tests passed; Python compilation passed; and a
  process audit found no stale AstraBridge-owned launchers. A broad scheduler
  batch showed intermittent timeout-at-the-test-window failures in two
  existing long-running scenarios, while the same scenarios passed in
  isolated runs; this is preserved as a stability follow-up signal rather than
  hidden as a pass.
- Blockers: None for the Step 8 guardrail acceptance. Broad-suite timing
  variance remains evidence for later stability/evaluation work; MCP surface
  exposure remains Step 11.
- Next step: Step 9, Harden Typed Communication And Isolation Defaults.

### 2026-07-21 - Step 9

- Completed: Added the single typed handoff/isolation admission owner in
  `apps/astrabridge-sidecar/astrabridge_sidecar/communication_isolation.py`.
  It reuses canonical graph validation and proves declared message-part modes,
  typed ports, source schema coverage, artifact declarations, bounded history,
  private-memory exclusion, and compiled-plan projection consistency. It fails
  closed on direct teammate messaging, nested-subagent widening, provider-
  private/raw-transcript content, and undeclared artifact leakage.
- Canonical integration: Skill resolution now exposes and enforces the same
  `astrabridge-communication-isolation-decision-v1` decision. Both live queue
  admission and synchronous execution validate it before executor/provider
  admission, and queued/running policy snapshots persist the redacted result.
  No second envelope or peer protocol was introduced.
- Evidence: Preserved the implementation and validation report at
  `PRIVATE/skill-first-orchestration/step9-typed-communication-isolation/20260721/typed-communication-isolation-report.md`.
- Validation: Five isolation tests passed; the combined communication,
  skill-resolution, graph-contract/compiler, guardrail, dispatch, and queue
  suites passed 24 tests; the broader Step 9 contract combination passed 27
  tests; three selected live local/subgraph/MCP runtime checks passed;
  Python compilation and `git diff --check` passed; before/after process audits
  found no stale AstraBridge-owned launchers. A broader fake-provider worker
  scenario still reports a pre-existing timing/status failure even when the
  new isolation validator is monkeypatched to unconditional pass, so it is
  retained as a later stability signal rather than misattributed here.
- Blockers: None for Step 9 acceptance. Provider/profile and external-A2A
  qualification remain the next implementation boundary; MCP lifecycle
  exposure remains Step 11.
- Next step: Step 10, Bind Provider Routing And External A2A Into The Skill
  Path.

### 2026-07-21 - Step 10

- Completed: Added the read-only provider/profile and external-A2A binding
  owner in `apps/astrabridge-sidecar/astrabridge_sidecar/skill_provider_a2a_binding.py`.
  It binds bounded provider/model routes to catalog records, verified capability
  snapshots, and declared profile snapshots; candidate routes remain explicit
  `downgraded` when evidence is partial, while promoted qualification levels
  fail closed.
- Canonical integration: `resolve_skill_to_graph` now exposes the same binding
  report and prefixes its blockers/warnings. External `a2a_card:*` routes use
  the existing `external_a2a_gateway` validator/snapshot and deterministic
  conformance kit; no direct peer protocol or live discovery path was added.
- Manifest correction: the five built-in skill manifests now include the
  canonical `qwen3-coder-plus` route used by their graph templates. The route
  remains downgraded when the local catalog has no verified snapshot, rather
  than being treated as ready by declaration alone.
- Evidence: Preserved
  `PRIVATE/skill-first-orchestration/step10-provider-a2a-binding/20260721/provider-a2a-binding-report.md`.
- Validation: Provider/A2A binding tests passed 5; skill-resolution tests
  passed 7; the communication-isolation, external-A2A gateway, and graph-check
  combination passed 28; Python compilation, `git diff --check`, and the
  focused secret-pattern scan passed. Provider-qualified and pinned external-
  A2A fixtures qualified without provider/MCP/network discovery calls; route,
  profile, freshness, and trust downgrade cases remained explicit.
- Blockers: None for Step 10 acceptance. MCP launch/lifecycle exposure is the
  next executable boundary; broader runtime timing signals remain preserved
  from earlier steps and were not reclassified here.
- Next step: Step 11, Expose Skill-Backed Orchestration Through Canonical MCP
  Entry Points.

### 2026-07-21 - Step 11

- Completed: Added `SkillOrchestrationMcpService` as the canonical skill-backed
  MCP control plane and late-bound it into `McpBrokerService` as the internal
  `astrabridge-orchestration` server. The surface exposes the nine Step 4 tools
  (`propose`, `patch`, `validate`, `dry_run`, `diff`, `launch`, `inspect`,
  `cancel`, and `recover`) without creating a second scheduler, provider SDK
  path, or tool execution owner.
- Canonical lifecycle: Skill resolution and compilation remain owned by the
  skill-to-graph bridge and canonical compiler; materialization, fixture runs,
  live admission, durable inspection, cancellation, and fixture recovery remain
  owned by the existing TaskService/RuntimeService/run-store path. Run policy
  snapshots now retain skill/resolution references, receipt, approval, and
  bounded budget metadata needed for correlation and recovery.
- Safety boundary: MCP requests are schema-validated and redacted; resolution
  references, operation journals, idempotency fingerprints, and digest-bound
  dry-run receipts are persisted under workspace-local `.astrabridge/` state.
  Candidate or unqualified skills remain blocked for live launch, while fixture
  launch/recovery provide deterministic evidence.
- Evidence: Preserved
  `PRIVATE/skill-first-orchestration/step11-mcp-entry-points/20260721/mcp-entry-points-report.md`.
- Validation: The Step 11 lifecycle suite passed `3/3`; MCP broker/core,
  skill-resolution, provider/A2A, and typed-isolation regressions passed
  `37/37`; Python compilation and `git diff --check` passed; the contract
  boundary audit passed `24/24`; and before/after process audits found no stale
  AstraBridge-owned listeners or launchers. The secret-like scanner only found
  expected static policy/auth field names in existing owners and the fail-closed
  key list; no credential value was persisted or echoed.
- Blockers: None for Step 11 acceptance. Live execution of candidate or
  provider/A2A-unqualified skills remains intentionally fail-closed and is a
  Step 12 promotion-gate input, not a hidden success.
- Next step: Step 12, Build Evaluation And Promotion Gates For Skill-Backed
  Patterns.

### 2026-07-21 - Step 12

- Completed: Added the bounded
  `skill_orchestration_evaluation_gate.py` evaluator and its CLI. The gate
  covers manifest integrity, canonical resolution/compile, typed
  communication isolation, strict runtime budgets, MCP loopback policy,
  provider/A2A truthfulness, and provider-free fixture execution for the five
  built-in patterns.
- Runtime contract fix: the first fixture evaluation exposed that the
  compatibility fixture emitted only `machine_result`, so typed `code_diff`
  and `image` handoffs could not be validated. `TaskService` now writes
  deterministic redacted fixture artifacts and protocol-valid `ArtifactRef`
  values for declared output ports; the repair was proven by the review/fix
  and multimodal fixture runs.
- Gate integration: the existing promotion gate now runs this lane in
  `evaluate` mode for PR/nightly and `promotion` mode for release. Candidate
  lifecycle states and the provider-update manual review state remain
  explicit release blockers.
- Evidence: Preserved
  `PRIVATE/skill-first-orchestration/step12-evaluation/20260721/evaluation-gate-report.md`,
  with structural, full fixture, and expected-failing promotion bundles under
  the same stable step directory.
- Validation: The focused regression lane passed `27/27`; structural
  evaluation passed all five patterns; full fixture evaluation passed all
  safety checks and completed the five patterns except the intentional
  provider-update `pending_review` outcome; promotion mode failed closed for
  candidate/pending states; an injected resolution blocker failed closed;
  contract-boundary audit passed `24/24`; focused new-file secret scan passed;
  Python compilation and `git diff --check` passed; before/after process audits
  found no stale AstraBridge-owned listeners or launchers.
- Blockers: None for Step 12 safety acceptance. Promotion readiness is
  intentionally false until the five manifests are productized and the
  provider-update review is explicitly resolved; provider/A2A downgrade
  warnings remain truthful and are not treated as qualification.
- Next step: Step 13, Dogfood The Initial Skill Set In Real Product Workflows.

### 2026-07-21 - Step 13

- Completed: Added the bounded `skill_orchestration_dogfood.py` runner and
  `scripts/run_skill_orchestration_dogfood.py` CLI. The case catalog covers
  supervisor/worker synthesis, review/fix/verify, contract-source fan-out,
  provider route qualification, and MCP-only multimodal fallback.
- Dogfood evidence: Ran all five product-shaped internal workflows through
  the canonical MCP loopback lifecycle (`propose`, `validate`, `dry_run`,
  fixture `launch`, and `inspect`) with repository references and stable input
  hashes. Four runs completed; provider update reached its explicit manual
  review gate. No operational product blockers were found.
- Classification: Candidate lifecycle and manual review remain policy gates;
  MCP preset availability, catalog snapshots, and provider-free placeholder
  artifacts are recorded as polish/evidence debt rather than hidden failures.
  Every case links exact follow-up owners.
- Evidence: Preserved
  `PRIVATE/skill-first-orchestration/step13-dogfood/20260721/dogfood-report.md`
  and the final bundle under
  `PRIVATE/skill-first-orchestration/step13-dogfood/20260721/initial-patterns-r2/`.
- Validation: The focused skill/MCP/evaluation/dogfood/promotion lane passed
  `29/29`; the contract-boundary audit passed `24/24`; provider and network
  discovery calls remained `0`; the focused secret scan passed across the
  runner, tests, and `227` preserved dogfood artifacts; Python compilation
  passed; and before/after process audits found no stale AstraBridge-owned
  listeners or launchers.
- Blockers: None for Step 13 operational acceptance. Live provider dogfood is
  intentionally deferred behind the existing approval, catalog, and promotion
  gates; this is recorded as a boundary, not a claim of live qualification.
- Next step: Step 14, Publish Authoring And Operator Runbooks.

### 2026-07-21 - Step 14

- Completed: Published the durable
  `docs/SKILL_FIRST_ORCHESTRATION_AUTHORING_RUNBOOK.md` and
  `docs/SKILL_FIRST_ORCHESTRATION_OPERATOR_RUNBOOK.md`. The author runbook
  covers pattern selection, package/manifest shape, tightening-only policy
  overrides, canonical lint/compile/dry-run commands, MCP admission, evidence
  levels, versioning, and contract-change escalation. The operator runbook
  covers preflight workspace/process hygiene, the full nine-tool MCP lifecycle,
  fixture-first launch, inspect/cancel/recover semantics, status interpretation,
  owner routing for guardrail failures, evidence roots, and handoff fields.
- Boundary preservation: Both runbooks make the canonical contracts and
  `astrabridge-orchestration` MCP server authoritative. They explicitly deny
  net-new GUI authoring, runtime skill nesting, unbounded teams/fan-out,
  provider-direct capability paths, direct peer messaging, second runtimes,
  unapproved external writes, and official-login product paths.
- Validation: The new runbook contract suite passed `23/23` tests (including
  local Markdown-link and required-section checks); the contract-boundary audit
  passed `24/24`; focused secret scanning across both runbooks and the new test
  passed with zero findings; `git diff --check` reported no whitespace errors
  (only the repository's existing LF/CRLF warnings); and before/after process
  audits found no stale AstraBridge-owned listeners or launchers.
- Blockers: None for Step 14 acceptance. Live provider qualification,
  provider catalog review, and any future GUI surfacing remain explicit later
  gates and are not implied by these documents.
- Next step: Step 15, Run Final Skill-First Product Closure Gate.

### 2026-07-21 - Step 15

- Completed: Ran the final bounded closure checks and preserved the closure
  report at
  `PRIVATE/skill-first-orchestration/step15-closure/20260721/final-closure-report.md`.
  The report classifies each requirement as pass, blocked, or deferred and
  names the next owner without treating fixture success as live qualification.
- Evidence: The fresh evaluation gate passed all five patterns with zero
  provider calls and zero network discovery calls; dogfood passed all five
  canonical MCP lifecycle cases (four completed and one explicit
  `pending_review`); release readiness passed with a short artifact root;
  contract-boundary audit passed `24/24`; current skill regression tests passed
  `23/23`; governance passed with `0` errors and `0` warnings; focused secret
  scanning covered `843` files with `0` findings; and before/after process
  audits found no stale AstraBridge-owned listeners or launchers.
- Promotion classification: Promotion remains correctly fail-closed. The
  candidate manifest lifecycle, provider-update manual review, and missing
  provider/catalog evidence are policy gates. The promotion quick lane also
  exposes a real cross-plan shell-owner budget blocker:
  `runtime_service.py` is `15869/15850` lines and `task_service.py` is
  `10928/10850` lines. This is assigned to the existing product-stability
  shell-module extraction lane; thresholds must not be raised to hide it.
- Diagnostics: A deep Windows artifact root reached a `261`-character target
  path and failed during stage-A copying, while the same readiness gate passed
  with a short root. The failure and outputs are preserved as path-ergonomics
  evidence rather than deleted.
- Blockers: No blocker remains for plan-level closure. Release/live provider
  qualification is still blocked or deferred until shell-owner budgets,
  candidate promotion, manual review, catalog snapshots, and provider/A2A
  evidence are resolved. GUI authoring remains explicitly out of scope.
- Next step: Plan complete; continue with product-stability shell-owner
  follow-up and selective skill productization outside this numbered plan.
