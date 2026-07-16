# Provider Model Test Coverage And Reasoning Handoff Plan

## Total Objective

Create a durable handoff plan for AstraBridge's provider/model capability verification work, with a narrower focus on multimodal test coverage completeness, model-level capability truthfulness, and reasoning-effort normalization against official documentation. The end state is a repeatable workflow where future agents can audit provider claims, identify test gaps, tighten capability declarations, and validate changes without relying on chat reconstruction or unsafe live experimentation.

## Deliverables

- A provider/model/capability coverage baseline that shows which high-priority lanes are currently covered by unit tests, dry-run validation, docs-backed assumptions, or live evidence.
- A primary-source audit pack for priority providers, with OpenRouter recorded only as a reasoning-abstraction design reference.
- A reasoning-effort compatibility audit that distinguishes documented mappings, inferred mappings, unsupported mappings, and noop mappings.
- A prioritized gap list covering missing tests, over-broad capability declarations, request-shape validation gaps, and misleading status surfaces.
- A bounded verification plan that defines what should remain static-only, what needs dry-run coverage, and what deserves optional managed-key live smoke.

## Related Context Files

- `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`
- `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_HANDOFF_PLAN.md`
- `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`
- `PRIVATE/agentic-update-pipeline/reports/step1-provider-model-capability-surface-inventory-20260706.md`

## Constraints And Attention Notes

1. This plan is a focused handoff slice. It must not erase, rewrite, or silently replace the broader provider/model capability validation plans already on disk.
2. Do not read desktop plaintext key files, cookies, bearer tokens, or provider raw secrets unless the user explicitly authorizes that exact action in the current turn.
3. Managed vault credentials may be used only when the user explicitly authorizes live provider testing for the current turn.
4. Never persist API keys, bearer tokens, auth headers, admin session tokens, or provider raw secrets in git, reports, test artifacts, or plan notes.
5. Preserve `PRIVATE/**`, sanitized raw call records, smoke results, validation reports, and screenshots by default unless the user explicitly names cleanup targets.
6. Official provider documentation is the primary source for modality, tool, streaming, and reasoning claims. OpenRouter is secondary context for abstraction design only.
7. Do not treat provider-wide booleans as proof of model-level capability when models under that provider differ by modality or reasoning behavior.
8. Test completeness does not require exhaustive live verification of every provider/model/capability combination. The required bar is layered coverage: docs-backed truth, static validation, targeted unit tests, dry-run coverage, and bounded live smoke only where risk justifies it.
9. Official OpenAI direct live verification remains out of scope unless the user later provides or authorizes an official OpenAI API-key path.
10. Reasoning-effort behavior may be accepted as docs-backed and transport-audited even when every effort level is not live-smoked, as long as unsupported or inferred behavior is marked honestly.

## Adjustment Policy

Agents may reasonably adjust substeps, exact file paths, commands, provider order, model selection, or sequencing when repository facts require it. Such adjustments must not weaken the evidence bar, remove secret-handling safeguards, downgrade model-level truthfulness requirements, or replace substantive compatibility work with cosmetic-only updates. If a lane cannot be verified inside the current product boundary, the acceptable substitute is an explicit downgrade with durable evidence and clear fallback behavior.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must start by reading this plan and the related context files needed for the active step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all of its acceptance criteria are satisfied.
5. If blocked, record the concrete blocker, evidence, attempted paths, and exact next step entry point.
6. Each turn must end with a concise handoff that states completed work, files changed, validation run, blockers, and next step.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Freeze Scope And Coverage Questions
- Next step: Step 1, Freeze Scope And Coverage Questions
- Last updated: 2026-07-06

## Execution Steps

### 0. Create Durable Plan

Goal: Create this handoff plan and make the next entry point clear.

Main actions:

- Define the total objective, related context files, constraints, execution rules, steps, and acceptance criteria.
- Make the focused scope explicit so later agents do not confuse this plan with the broader capability-validation plans.
- Set current progress and initial log entry.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, related context files, constraints, adjustment policy, current progress, steps, acceptance criteria, and progress log.
- Next step is clearly identified.

Status: completed

### 1. Freeze Scope And Coverage Questions

Goal: Lock the exact provider, model, and capability questions this plan is expected to answer.

Main actions:

- Fix the priority provider set for this slice: Yunwu/OpenAI-compatible, OpenAI official docs as protocol reference, Qwen/DashScope, DeepSeek, Kimi/Moonshot, and GLM/Zhipu.
- Fix the priority capability lanes: text input/output, image input, image output, audio input, audio output, tool calling, streaming, structured edit, context window handling, and reasoning or thinking controls.
- Write the exact coverage questions to answer, including whether current tests are sufficient, where model-level capability claims are too broad, and whether the current reasoning-effort algorithm is defensible.

Acceptance criteria:

- A written scope artifact exists under `PLAN/` or `PRIVATE/agentic-update-pipeline/reports/`.
- In-scope providers and capability lanes are explicit.
- A future agent can start the audit without reconstructing the user's intent from chat history.

Status: not started

### 2. Inventory Current Tests, Validators, And Evidence Surfaces

Goal: Make the current verification baseline visible before judging completeness.

Main actions:

- Inventory unit tests, adapter tests, transport tests, smoke reports, matrix reports, source registries, and request-shape validators that affect the in-scope providers and capability lanes.
- Separate provider-level declarations, model-catalog declarations, adapter-level allowlists, validator logic, and live evidence.
- Record where the current test suite covers positive cases, negative cases, dry-run behavior, or only documentation assumptions.

Acceptance criteria:

- A written inventory exists with exact file references.
- The inventory distinguishes code declarations from real verification evidence.
- Coverage holes are visible at the provider/model/capability level rather than only as a generic test count.

Status: not started

### 3. Define The Capability Coverage Matrix For This Slice

Goal: Create a durable structure for judging whether coverage is complete enough.

Main actions:

- Adapt the existing matrix contract into a slice-specific view that records `declared_capability`, `runtime_gating`, `static_validation`, `unit_test_coverage`, `dry_run_coverage`, `live_evidence`, and `reasoning_mapping_status`.
- Define allowed status values such as `verified`, `partial`, `blocked`, `unknown`, `unsupported`, and `docs_only`.
- Require each matrix entry to identify whether the claim is provider-level, model-level, or adapter-specific.

Acceptance criteria:

- A matrix artifact or schema note exists for this slice.
- Status semantics are explicit and compatible with the broader matrix contract.
- The matrix makes it impossible to confuse provider-level defaults with model-level proof.

Status: not started

### 4. Build A Current Coverage Baseline For Priority Providers

Goal: Show the real current state before proposing changes.

Main actions:

- Fill the coverage matrix for the priority providers and priority models currently surfaced by AstraBridge.
- Mark each capability lane as covered by tests, dry-run validation, docs-only evidence, live evidence, or not covered.
- Highlight where the same provider exposes different capability behavior by model family.

Acceptance criteria:

- A baseline coverage artifact exists on disk.
- The artifact shows model-level differences for multimodal lanes and reasoning behavior.
- A reader can tell which important lanes are tested, only documented, or currently unverified.

Status: not started

### 5. Audit Qwen/DashScope Multimodal And Thinking Rules

Goal: Turn Qwen official docs and current code into a precise compatibility judgment.

Main actions:

- Review official Qwen docs for text, vision, ASR, TTS, streaming, tool usage, and `enable_thinking` behavior.
- Record documented request constraints such as image width and height greater than 10px, supported media formats, URL or base64 requirements, and any streaming-related thinking guidance.
- Compare those claims with the current Qwen provider profile, model catalog, capability specs, adapters, tests, and preserved evidence.

Acceptance criteria:

- Qwen priority models have lane-level status for text, vision, audio input, audio output, tool usage, and reasoning.
- Known pitfalls are classified as request-shape or model-support constraints rather than vague provider incompatibility.
- Mismatches between docs and current code are captured as concrete follow-up items.

Status: not started

### 6. Audit OpenAI Protocol Assumptions And Yunwu-Compatible Reality

Goal: Separate official protocol truth from what AstraBridge has actually exercised through compatible providers.

Main actions:

- Review official OpenAI docs for Responses, tool calls, image input/output, structured outputs, streaming, and reasoning effort.
- Review Yunwu/OpenAI-compatible profiles, adapters, and preserved evidence for the same lanes.
- Mark which claims are official protocol assumptions, which are Yunwu-verified, and which remain unverified without official-provider live access.

Acceptance criteria:

- OpenAI official protocol claims are not mixed together with Yunwu runtime evidence.
- No official OpenAI lane is marked live-verified without authorized official-provider testing.
- Yunwu verified paths link to preserved secret-free artifacts where available.

Status: not started

### 7. Audit DeepSeek, Kimi, And GLM Multimodal And Reasoning Claims

Goal: Reconcile the remaining managed providers with current code and preserved evidence.

Main actions:

- Review official docs for DeepSeek, Kimi/Moonshot, and GLM/Zhipu across the in-scope capability lanes.
- Compare those claims with provider profiles, transports, validators, tests, and preserved smoke results.
- Record provider-specific pitfalls such as reasoning-content quirks, no-output behavior, multimodal request-shape constraints, or tool-call limitations.

Acceptance criteria:

- Each priority provider has lane-level status across the in-scope capabilities.
- Known provider-specific pitfalls are recorded with file references or source citations.
- Unsupported or weakly supported lanes are not left in an optimistic default state.

Status: not started

### 8. Audit Reasoning-Effort Normalization Against Official Docs And OpenRouter

Goal: Decide whether the current reasoning-effort algorithm is justified, conservative, and maintainable.

Main actions:

- Review official reasoning or thinking controls for the in-scope providers, including effort levels, booleans, budgets, or reasoning-content modes where relevant.
- Review OpenRouter's reasoning abstraction as a secondary design reference for normalization, fallback, and unsupported-provider behavior.
- Compare those references with AstraBridge's reasoning policies, catalog contract, transport mappings, and default behavior.

Acceptance criteria:

- A reasoning audit exists with source citations and exact file references.
- The audit distinguishes documented mappings, inferred mappings, unsupported mappings, and noop mappings.
- The audit recommends concrete code changes or explicitly states why the current behavior is acceptable with caveats.

Status: not started

### 9. Produce A Test Completeness And Risk Gap Report

Goal: Convert the audit into an actionable view of what is still missing.

Main actions:

- Classify gaps by risk, such as route misclassification, invalid request shape, stale capability declaration, unverified reasoning mapping, missing negative tests, or misleading UI status.
- Identify which gaps can be closed by docs-only clarification, which require new tests, which require capability declaration changes, and which require validator or runtime work.
- Rank the gaps so later agents can address the most dangerous optimistic assumptions first.

Acceptance criteria:

- A gap report exists with risk classes and file-level ownership.
- The highest-risk missing tests and reasoning assumptions are clearly identified.
- The next implementation steps are unambiguous.

Status: not started

### 10. Design The Static Validation And Unit-Test Expansion Set

Goal: Define the smallest high-value test additions that materially improve confidence.

Main actions:

- Propose new or updated unit tests for provider/model/capability combinations that are currently optimistic or under-specified.
- Propose validator coverage for documented multimodal constraints such as image dimensions, URL restrictions, audio-only message shape, and provider-specific parameter omissions or clamps.
- Ensure the design includes both positive and negative cases, not only happy-path routing.

Acceptance criteria:

- A test-expansion design artifact exists with exact target files or modules.
- Proposed tests are prioritized by risk and provider/model impact.
- The design makes clear which cases should stay static-only and which need later live smoke.

Status: not started

### 11. Implement The Highest-Risk Declaration And Validator Fixes

Goal: Remove the most dangerous false positives before broader verification.

Main actions:

- Tighten model-level capability declarations or routing gates where provider-wide defaults overstate support.
- Implement or refine the highest-risk request-shape validators identified earlier.
- Keep changes scoped to the smallest surfaces that materially improve correctness.

Acceptance criteria:

- At least the highest-risk optimistic capability mismatches are blocked, downgraded, or made explicit.
- Tests cover representative positive and negative cases for each changed high-risk area.
- Existing known-good routes still resolve.

Status: not started

### 12. Build Dry-Run Coverage Generation For Priority Cases

Goal: Expand verification breadth without spending provider tokens.

Main actions:

- Build or extend a dry-run report that enumerates priority provider/model/capability cases, selected route, normalized contract, validator outcome, and reasoning mapping.
- Include unsupported, blocked, unknown, and partial cases rather than only success paths.
- Save outputs in a secret-free form suitable for repeated agent use and CI-style checks.

Acceptance criteria:

- A dry-run coverage artifact exists for the priority providers and capability lanes.
- The artifact makes unsupported and unverified cases easy to identify.
- The dry-run path requires no live credentials.

Status: not started

### 13. Define The Bounded Managed-Key Smoke Policy

Goal: Decide what deserves live testing and what should remain docs-backed or dry-run only.

Main actions:

- Define one representative text baseline per provider and one representative multimodal or reasoning lane where provider claims justify live confirmation.
- Bound the live-smoke set by cost, time, token, artifact-redaction, and authorization rules.
- Exclude official OpenAI direct live testing unless the user later changes scope.

Acceptance criteria:

- A written live-smoke policy exists.
- The policy explains why exhaustive model-by-model live testing is unnecessary.
- The authorization boundary for managed-vault usage is explicit.

Status: not started

### 14. Run Authorized Representative Smokes And Classify Outcomes

Goal: Produce bounded live evidence only after the safer layers are in place.

Main actions:

- Confirm user authorization for the current turn before any live provider call.
- Run only the approved representative smokes and preserve sanitized evidence under `PRIVATE/**`.
- Classify each result as `pass`, `partial`, `fail`, `blocked`, or `skipped` with a concrete reason.

Acceptance criteria:

- New live artifacts are secret-free and stored under `PRIVATE/**`.
- Each executed case is linked back to the coverage matrix and failure taxonomy.
- A focused secret scan over new artifacts passes.

Status: not started

### 15. Publish The Maintenance Runbook And Final Handoff

Goal: Make the verification workflow repeatable for later model and provider updates.

Main actions:

- Update the durable matrix or status surface with the final audited state.
- Write or update a runbook covering official-doc lookup, reasoning audit refresh, test expansion, dry-run reruns, live-smoke authorization, artifact preservation, and rollback boundaries.
- Record residual risks, deferred lanes, and the next maintenance entry point.

Acceptance criteria:

- A future agent can repeat the verification workflow without reconstructing chat history.
- Residual risks and deferred provider/model lanes are explicitly recorded.
- The final handoff lists completed work, validation performed, and exact next maintenance entry points.

Status: not started

## Progress Log

### 2026-07-06 - Step 0

- Completed: Created a durable handoff plan focused on provider/model test coverage completeness and reasoning-effort audit work.
- Files changed: `PLAN/PROVIDER_MODEL_TEST_COVERAGE_AND_REASONING_HANDOFF_PLAN.md`.
- Validation: Checked that the plan includes total objective, deliverables, related context files, constraints, adjustment policy, execution rules, current progress, numbered steps, acceptance criteria, and progress log.
- Blockers: None.
- Next step: Step 1, Freeze Scope And Coverage Questions.
