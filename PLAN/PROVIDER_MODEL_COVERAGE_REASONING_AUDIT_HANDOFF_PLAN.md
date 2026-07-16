# Provider Model Coverage And Reasoning Audit Handoff Plan

## Total Objective

Create a durable handoff plan that another agent can execute to judge whether AstraBridge's provider/model capability coverage and reasoning-effort abstraction are complete enough for credible same-task cross-provider switching, then close the highest-risk gaps without requiring exhaustive live testing for every model and every capability lane.

## Deliverables

- A priority-scoped provider/model/capability audit baseline that separates declared capability, runtime-normalized behavior, and real validation evidence.
- A primary-source documentation pack for priority providers, with OpenRouter recorded only as a secondary reasoning-abstraction reference.
- A reasoning-effort compatibility audit that distinguishes documented mappings, inferred mappings, unsupported mappings, and noop mappings.
- A risk-ranked gap list covering multimodal capability truthfulness, request-shape validation, reasoning normalization, and misleading status surfaces.
- A bounded follow-up package covering code/test changes, dry-run coverage, optional managed-key smoke policy, and maintenance handoff notes.

## Related Context Files

- `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`
- `PLAN/PROVIDER_MODEL_TEST_COVERAGE_AND_REASONING_HANDOFF_PLAN.md`
- `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_HANDOFF_PLAN.md`
- `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`
- `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`
- `PRIVATE/agentic-update-pipeline/reports/step1-provider-model-capability-surface-inventory-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step11-provider-capability-dry-run-matrix-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step12-bounded-live-smoke-policy-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step13-managed-key-live-smoke-20260706.md`
- `PRIVATE/agentic-update-pipeline/reports/step14-failure-taxonomy-and-fallback-behavior-20260706.md`
- `PRIVATE/provider-compatibility/reports/step10-real-provider-text-code-agent-20260704.md`
- `PRIVATE/provider-compatibility/reports/step11-cross-provider-switch-fallback-20260705.md`
- `PRIVATE/provider-compatibility/reports/step12-multimodal-capability-routes-20260705.md`

## Constraints And Attention Notes

1. This plan is a focused handoff slice. It must not erase, rewrite, or silently replace the broader provider/model validation plans already on disk.
2. Do not read desktop plaintext key files, cookies, bearer tokens, auth headers, or provider raw secrets unless the user explicitly authorizes that exact action in the current turn.
3. Managed-vault credentials may be used only when the user explicitly authorizes live provider testing for the current turn.
4. Never persist API keys, bearer tokens, auth headers, admin session tokens, or provider raw secrets in git, reports, raw artifacts, logs, or plan notes.
5. Preserve `PRIVATE/**`, sanitized raw call records, smoke results, screenshots, caches, validation reports, and failure evidence by default unless the user explicitly names cleanup targets.
6. Official provider docs are the primary source for capability, modality, and reasoning claims. OpenRouter may be used only as a secondary design reference for reasoning normalization.
7. Do not treat provider-wide booleans as model-level proof when models under the same provider differ by modality, reasoning controls, or tool behavior.
8. Test completeness does not mean exhaustive live verification of every provider/model/capability combination. The required bar is layered coverage: docs-backed truth, static validation, targeted tests, dry-run coverage, and optional bounded live smoke where risk justifies it.
9. Official OpenAI direct live verification is out of scope unless the user later provides or authorizes an official OpenAI API-key path.
10. Reasoning-effort behavior may be accepted as docs-backed and transport-audited even when every effort level is not live-smoked, as long as unsupported or inferred behavior is marked honestly.
11. Do not write findings or grading results back to external platforms unless the user explicitly approves the exact writeback target.
12. Treat this plan as the preferred delegation entry point for the current provider/model coverage and reasoning audit slice. The sibling handoff plans listed above remain historical context unless the user explicitly redirects to them.

## Adjustment Policy

Agents may reasonably adjust substeps, exact file paths, commands, provider order, model selection, or sequencing when repository facts require it. Such adjustments must not weaken the evidence bar, downgrade model-level truthfulness requirements, remove secret-handling safeguards, or replace substantive compatibility work with cosmetic-only updates. If a capability lane cannot be verified inside the current product boundary, the acceptable substitute is an explicit downgrade with durable evidence, clear fallback guidance, and a next-step note that preserves the original intent.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must start by reading this plan and the related context files needed for the active step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all of its acceptance criteria are satisfied.
5. If blocked, record the concrete blocker, evidence, attempted paths, and exact next-step entry point.
6. Each turn must end with a concise handoff that states completed work, files changed, validation run, blockers, and next step.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan; Step 1, Freeze Scope And Priority Cohorts; Step 2, Build Official Documentation Source Pack; Step 3, Inventory Current Code, Tests, And Evidence Surfaces; Step 4, Define The Capability Coverage Matrix And Completeness Bar; Step 5, Build The Current Priority Coverage Baseline; Step 6, Audit Qwen Multimodal And Thinking Rules; Step 7, Audit OpenAI Protocol Assumptions And Yunwu-Compatible Reality; Step 8, Audit DeepSeek Capability And Reasoning Rules; Step 9, Audit Kimi Capability And Agent Constraints; Step 10, Audit GLM Capability And Reasoning Rules; Step 11, Audit Reasoning-Effort Abstraction Against Official Docs And OpenRouter; Step 12, Produce A Risk-Ranked Gap Report; Step 13, Implement The Highest-Risk Declaration, Validator, And Test Fixes.
- Current step: Step 14, Build Dry-Run Coverage, Optional Smoke Policy, And Final Handoff, aligned to `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` Step 15.
- Next step: Step 14, Build Dry-Run Coverage, Optional Smoke Policy, And Final Handoff, starting from the user-facing capability-status work in `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` Step 15.
- Last updated: 2026-07-06

## Execution Steps

### 0. Create Durable Plan

Goal: Create this handoff plan and make the next entry point clear.

Main actions:

- Define the total objective, deliverables, constraints, execution rules, steps, and acceptance criteria.
- Record the baseline context files that later agents must treat as authoritative inputs.
- Set current progress and initial log entry.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, deliverables, related context files, constraints, adjustment policy, current progress, numbered steps, acceptance criteria, and progress log.
- Next step is clearly identified.

Status: completed

### 1. Freeze Scope And Priority Cohorts

Goal: Lock the exact provider, model, and capability questions this audit slice must answer.

Main actions:

- Fix the priority provider set for this slice: Yunwu/OpenAI-compatible, OpenAI official docs as protocol reference, Qwen/DashScope, DeepSeek, Kimi/Moonshot, and GLM/Zhipu.
- Fix the priority model cohort from AstraBridge's current catalog and route surfaces rather than attempting the full long-tail model list.
- Fix the priority capability lanes: text input/output, image input, image output, audio input, audio output, tool calling, streaming, structured edit or apply_patch behavior, context-window handling, and reasoning or thinking controls.

Acceptance criteria:

- A written scope artifact exists under `PLAN/` or `PRIVATE/agentic-update-pipeline/reports/`.
- In-scope providers, priority models, and capability lanes are explicit.
- Deferred items such as official OpenAI direct live verification are called out explicitly.

Status: completed

### 2. Build Official Documentation Source Pack

Goal: Gather the minimum primary-source document set required for capability and reasoning claims.

Main actions:

- Record official provider-document URLs for model lists, modality support, reasoning or thinking controls, tool calling, streaming, and documented limits.
- Record retrieval date, provider id, source type, supported capability categories, and whether each source is stable or likely to drift.
- Keep OpenRouter and any other non-official references clearly separated as secondary context.

Acceptance criteria:

- A source-pack artifact exists and is secret-free.
- Each source entry names the provider, URL, retrieval date, and capability categories it supports.
- Non-official references are clearly marked as secondary rather than mixed into primary evidence.

Status: completed

### 3. Inventory Current Code, Tests, And Evidence Surfaces

Goal: Make the current verification baseline visible before judging completeness.

Main actions:

- Inventory provider profiles, transports, model-catalog declarations, capability specs, validators, tests, smoke reports, and matrix or runbook artifacts that affect the in-scope providers and capability lanes.
- Separate provider-level declarations, model-level declarations, adapter-level allowlists, validator logic, and preserved live evidence.
- Record where the current suite covers positive cases, negative cases, dry-run behavior, or only documentation assumptions.

Acceptance criteria:

- A written inventory exists with exact file references.
- The inventory distinguishes code declarations from real verification evidence.
- Coverage holes are visible at the provider/model/capability level rather than only as a generic test count.

Status: completed

### 4. Define The Capability Coverage Matrix And Completeness Bar

Goal: Create a durable structure for judging whether current coverage is complete enough.

Main actions:

- Adapt the existing matrix contract into a slice-specific view that records `declared_capability`, `runtime_normalized_contract`, `static_validation`, `unit_test_coverage`, `dry_run_coverage`, `live_evidence`, and `reasoning_mapping_status`.
- Define allowed status values such as `verified`, `partial`, `blocked`, `unknown`, `unsupported`, and `docs_only`.
- Define the completeness rule for this slice so that representative coverage can be considered sufficient without pretending the matrix is exhaustive.

Acceptance criteria:

- A matrix artifact or schema note exists for this slice.
- Status semantics are explicit and compatible with the broader matrix contract.
- The matrix makes it impossible to confuse provider-level defaults with model-level proof.

Status: completed

### 5. Build The Current Priority Coverage Baseline

Goal: Show the real current state before proposing changes.

Main actions:

- Fill the coverage matrix for the priority providers and priority models currently surfaced by AstraBridge.
- Mark each capability lane as covered by tests, dry-run validation, docs-only evidence, live evidence, or not covered.
- Highlight where models under the same provider expose different modality or reasoning behavior.

Acceptance criteria:

- A baseline coverage artifact exists on disk.
- The artifact shows model-level differences for multimodal lanes and reasoning behavior.
- A reader can tell which important lanes are tested, only documented, or currently unverified.

Status: completed

### 6. Audit Qwen Multimodal And Thinking Rules

Goal: Turn Qwen official docs and current code into a precise model-level compatibility judgment.

Main actions:

- Review official Qwen docs for text, vision, ASR, TTS, streaming, tool usage, and `enable_thinking` behavior.
- Record documented request constraints such as media formats, image dimension limits, audio-only content rules, and temperature or parameter quirks.
- Compare those claims with the current Qwen provider profile, model catalog, capability specs, adapters, tests, and preserved evidence.

Acceptance criteria:

- Qwen priority models have lane-level status for text, vision, audio input, audio output, tool usage, and reasoning.
- Known pitfalls are classified as request-shape or model-support constraints rather than vague provider incompatibility.
- Mismatches between docs and current code are captured as concrete follow-up items.

Status: completed

### 7. Audit OpenAI Protocol Assumptions And Yunwu-Compatible Reality

Goal: Separate official protocol truth from what AstraBridge has actually exercised through compatible providers.

Main actions:

- Review official OpenAI docs for Responses, tool calls, image input or output, structured edit behavior, streaming, and reasoning effort.
- Review Yunwu-compatible profiles, adapters, and preserved evidence for the same lanes.
- Mark which claims are official protocol assumptions, which are Yunwu-verified, and which remain unverified without official-provider live access.

Acceptance criteria:

- OpenAI official protocol claims are not mixed together with Yunwu runtime evidence.
- No official OpenAI lane is marked live-verified without authorized official-provider testing.
- Yunwu verified paths link to preserved secret-free artifacts where available.

Status: completed

### 8. Audit DeepSeek Capability And Reasoning Rules

Goal: Reconcile DeepSeek capability assumptions with official docs, current code, and preserved evidence.

Main actions:

- Review official DeepSeek docs for chat, tool calling, thinking mode, reasoning content, streaming, and documented limits.
- Compare those claims with provider profiles, transports, catalog metadata, tests, and preserved smoke results.
- Record DeepSeek-specific pitfalls such as reasoning-content behavior, parameter clamping, deprecated model aliases, or compact limitations.

Acceptance criteria:

- DeepSeek priority models have lane-level status for the in-scope capabilities.
- Known DeepSeek pitfalls are recorded with source citations or evidence links.
- Unsupported or weakly supported lanes are not left in an optimistic default state.

Status: completed

### 9. Audit Kimi Capability And Agent Constraints

Goal: Reconcile Kimi capability assumptions with official docs, current code, and preserved evidence.

Main actions:

- Review official Kimi docs for text, image or video understanding, tool usage, streaming, temperature restrictions, and thinking behavior.
- Compare those claims with provider profiles, transports, capability specs, tests, and preserved smoke results.
- Record Kimi-specific pitfalls such as tool-schema rejection, handoff-target unreliability, or modality-specific request constraints.

Acceptance criteria:

- Kimi priority models have lane-level status for the in-scope capabilities.
- Known Kimi pitfalls are recorded with source citations or evidence links.
- Unsupported or weakly supported lanes are not left in an optimistic default state.

Status: completed

### 10. Audit GLM Capability And Reasoning Rules

Goal: Reconcile GLM capability assumptions with official docs, current code, and preserved evidence.

Main actions:

- Review official GLM docs for multimodal input, function calling, streaming, reasoning controls, and documented limits.
- Compare those claims with provider profiles, transports, catalog metadata, tests, and preserved smoke results.
- Record GLM-specific pitfalls such as weak command-execution evidence, broader provider docs than current model-level proof, or compact limitations.

Acceptance criteria:

- GLM priority models have lane-level status for the in-scope capabilities.
- Known GLM pitfalls are recorded with source citations or evidence links.
- Unsupported or weakly supported lanes are not left in an optimistic default state.

Status: completed

### 11. Audit Reasoning-Effort Abstraction Against Official Docs And OpenRouter

Goal: Decide whether AstraBridge's reasoning-effort algorithm is justified, conservative, and maintainable.

Main actions:

- Review official reasoning or thinking controls for the in-scope providers, including effort levels, booleans, budgets, or reasoning-content modes where relevant.
- Review OpenRouter's reasoning abstraction as a secondary design reference for normalization, fallback, and unsupported-provider behavior.
- Compare those references with AstraBridge's reasoning policies, catalog contract, transport mappings, and default behavior.

Acceptance criteria:

- A reasoning audit exists with source citations and exact file references.
- The audit distinguishes documented mappings, inferred mappings, unsupported mappings, and noop mappings.
- The audit recommends concrete code changes or explicitly states why current behavior is acceptable with caveats.

Status: completed

### 12. Produce A Risk-Ranked Gap Report

Goal: Convert the audit into an actionable view of what is still missing.

Main actions:

- Classify gaps by risk, such as route misclassification, invalid request shape, stale capability declaration, unverified reasoning mapping, missing negative tests, or misleading UI status.
- Identify which gaps can be closed by docs-only clarification, which require new tests, which require capability-declaration changes, and which require validator or runtime work.
- Rank the gaps so later agents can address the most dangerous optimistic assumptions first.

Acceptance criteria:

- A gap report exists with risk classes and file-level ownership.
- The highest-risk missing tests and reasoning assumptions are clearly identified.
- The next implementation steps are unambiguous.

Status: completed

### 13. Implement The Highest-Risk Declaration, Validator, And Test Fixes

Goal: Remove the most dangerous false positives before broader verification.

Main actions:

- Tighten model-level capability declarations or routing gates where provider-wide defaults overstate support.
- Implement or refine the highest-risk request-shape validators identified earlier.
- Add focused positive and negative tests for the changed high-risk areas.

Acceptance criteria:

- At least the highest-risk optimistic capability mismatches are blocked, downgraded, or made explicit.
- Tests cover representative positive and negative cases for each changed high-risk area.
- Existing known-good routes still resolve.

Status: completed

### 14. Build Dry-Run Coverage, Optional Smoke Policy, And Final Handoff

Goal: Make the verification workflow repeatable without requiring chat reconstruction or uncontrolled live testing.

Main actions:

- Build or extend a dry-run report that enumerates priority provider/model/capability cases, selected route, normalized contract, validator outcome, and reasoning mapping.
- Define the minimal managed-key smoke set for cases that truly deserve live confirmation, with explicit authorization, cost, and redaction boundaries.
- Update the durable status surface or runbook with residual risks, deferred lanes, verification commands, and the next maintenance entry point; this includes user-facing capability-status surfacing so unsupported or unverified lanes are not presented as fully available.

Acceptance criteria:

- A dry-run coverage artifact exists and is secret-free.
- A written managed-key smoke policy exists and clearly excludes unauthorized live testing.
- A final handoff summary records completed work, residual risks, deferred items, and the exact next maintenance entry point, including the remaining status-surface work.

Status: in progress

## Progress Log

### 2026-07-06 - Step 0

- Completed: Created a durable handoff plan focused on provider/model capability coverage completeness and reasoning-effort audit work.
- Files changed: `PLAN/PROVIDER_MODEL_COVERAGE_REASONING_AUDIT_HANDOFF_PLAN.md`.
- Validation: Checked that the plan includes total objective, deliverables, related context files, constraints, adjustment policy, execution rules, current progress, numbered steps, acceptance criteria, and progress log.
- Blockers: None.
- Next step: Step 1, Freeze Scope And Priority Cohorts.

### 2026-07-06 - Plan Refresh

- Completed: Refreshed this plan to make it the preferred handoff entry point for the latest discussion about provider/model test completeness, model-level multimodal truthfulness, and official-doc-first reasoning-effort review.
- Files changed: `PLAN/PROVIDER_MODEL_COVERAGE_REASONING_AUDIT_HANDOFF_PLAN.md`.
- Validation: Re-checked scope, constraints, execution rules, and step structure against the durable handoff plan template; confirmed direct official OpenAI live verification remains explicitly out of scope.
- Blockers: None.
- Next step: Step 1, Freeze Scope And Priority Cohorts.

### 2026-07-06 - Execution Sync Refresh

- Completed: Synced this durable handoff plan with the active validation execution track so another agent can use one delegation entry point instead of reconstructing status from multiple sibling plans. Marked the scope, audit, matrix, baseline, reasoning, and gap-report phases as completed from the linked execution artifacts; left implementation follow-through in progress.
- Files changed: `PLAN/PROVIDER_MODEL_COVERAGE_REASONING_AUDIT_HANDOFF_PLAN.md`.
- Validation: Cross-checked completed status against `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` current progress and preserved reports under `PRIVATE/agentic-update-pipeline/reports/step1-provider-model-capability-surface-inventory-20260706.md`, `step3-official-provider-source-registry-20260706.md`, `step4-qwen-capability-audit-20260706.md`, `step5-openai-yunwu-capability-audit-20260706.md`, `step6-deepseek-kimi-glm-capability-audit-20260706.md`, `step7-reasoning-effort-audit-20260706.md`, and `step8-runtime-gap-report-20260706.md`.
- Blockers: None.
- Next step: Step 13, Implement The Highest-Risk Declaration, Validator, And Test Fixes, continuing from `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` Step 10.

### 2026-07-06 - Dry-Run Coverage Sync

- Completed: Synced this handoff plan to the current execution state after the model-level gating, request-shape validation, and dry-run matrix work landed. Marked Step 13 completed from the validated Step 9 and Step 10 implementation work, and moved the live delegation entry point to Step 14 with the new dry-run artifact baseline in place.
- Files changed: `PLAN/PROVIDER_MODEL_COVERAGE_REASONING_AUDIT_HANDOFF_PLAN.md`; `PRIVATE/agentic-update-pipeline/reports/step11-provider-capability-dry-run-matrix-20260706.md`.
- Validation: Cross-checked `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` through Step 11, verified the generated artifacts under `PRIVATE/agentic-update-pipeline/runs/step11-provider-capability-dry-run-matrix-20260706/` and `PRIVATE/provider-compatibility/runs/step11-provider-capability-dry-run-matrix-20260706-capability-smoke/`, and confirmed the remaining Step 14 work is the bounded smoke policy plus final handoff surface updates.
- Blockers: None.
- Next step: Step 14, Build Dry-Run Coverage, Optional Smoke Policy, And Final Handoff, continuing from `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` Step 12.

### 2026-07-06 - Delegation Entry Refresh

- Completed: Refreshed this durable handoff plan as the canonical delegation entry point for the latest discussion about provider/model test completeness, model-level multimodal truthfulness, and reasoning-effort defensibility. Synced the context list through the new dry-run, smoke-policy, managed-key, and failure-taxonomy artifacts, and moved the execution anchor forward so the next agent starts from the remaining user-facing status-surface work instead of recreating earlier audit steps.
- Files changed: `PLAN/PROVIDER_MODEL_COVERAGE_REASONING_AUDIT_HANDOFF_PLAN.md`.
- Validation: Cross-checked the plan against `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` current progress, confirmed the execution plan is now at Step 15, and verified the refreshed context list includes the latest Step 11 through Step 14 artifacts needed for delegation.
- Blockers: None.
- Next step: Step 14, Build Dry-Run Coverage, Optional Smoke Policy, And Final Handoff, starting from `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` Step 15.
