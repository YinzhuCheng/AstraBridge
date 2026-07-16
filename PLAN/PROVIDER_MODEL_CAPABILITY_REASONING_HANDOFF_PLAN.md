# Provider Model Capability And Reasoning Handoff Plan

## Total Objective

Create a durable handoff plan that another agent can execute to close AstraBridge's most material gaps in provider/model capability coverage and reasoning-effort compatibility. The target end state is not exhaustive live verification for every model, but a disciplined system where priority providers, priority models, and priority multimodal lanes are documented, tested at the right layer, and represented honestly in runtime and user-facing status.

## Deliverables

- A priority-scoped provider/model/capability baseline that distinguishes declared capability, runtime-normalized behavior, and real validation evidence.
- An official-document source pack for priority providers and reasoning-effort references, including OpenRouter as a comparison reference rather than a source of truth.
- A gap report that names the highest-risk mismatches in multimodal capability routing, request-shape validation, and reasoning-effort abstraction.
- Focused code, test, and matrix updates for the highest-risk gaps that can be resolved inside AstraBridge.
- A bounded verification and handoff package that future agents can repeat without reconstructing chat context.

## Related Context Files

- `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`
- `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`
- `PRIVATE/agentic-update-pipeline/reports/step1-provider-model-capability-surface-inventory-20260706.md`

## Constraints And Attention Notes

1. This handoff plan complements the broader validation execution plan and must not overwrite or discard its completed history.
2. Do not read desktop plaintext key files or other raw secret sources unless the user explicitly authorizes that exact action in the current turn.
3. For provider-backed checks, use managed vault paths only when the user explicitly authorizes live testing for that turn.
4. Never persist API keys, bearer tokens, cookies, auth headers, admin session tokens, or provider raw secrets in git, reports, logs, or plan notes.
5. Preserve `PRIVATE/**` artifacts, sanitized raw records, validation outputs, screenshots, reports, and failure evidence by default unless the user explicitly names cleanup targets.
6. Official provider docs are the primary source for capability and reasoning claims. OpenRouter may be used as a design reference for reasoning abstraction, not as proof that a provider officially supports a behavior.
7. Do not promote a provider-wide flag into model-level support when capabilities vary by model. Unknown or unsupported is better than optimistic inheritance.
8. Official OpenAI direct live validation is out of scope for this plan unless the user later provides or authorizes an official OpenAI API-key path.
9. Reasoning effort does not need exhaustive live verification for every level. The required bar is documented justification plus focused validation of high-risk mappings.

## Adjustment Policy

Agents may adjust substeps, file paths, exact commands, provider ordering, or sequencing when repository facts require it. Those adjustments must not change the total objective, weaken the evidence bar, remove secret-handling safeguards, or replace substantive compatibility work with cosmetic-only updates. If a lane cannot be verified in the current product boundary, the acceptable substitute is an explicit downgrade with durable evidence and clear fallback guidance.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must start by reading this plan and the related context files that govern the current step.
3. Each turn must update this plan before stopping.
4. A step may be marked `completed` only when all of its acceptance criteria are satisfied.
5. If blocked, record the concrete blocker, evidence, attempted paths, and the exact next step entry point.
6. Each turn must end with a concise handoff that states completed work, files changed, validation run, blockers, and next step.

## Current Progress

- Current status: In progress
- Completed steps: Step 0, Create Durable Plan
- Current step: Step 1, Freeze Scope And Baseline Inputs
- Next step: Step 1, Freeze Scope And Baseline Inputs
- Last updated: 2026-07-06

## Execution Steps

### 0. Create Durable Plan

Goal: Create this handoff plan and make the next entry point clear.

Main actions:

- Define the total objective, constraints, execution rules, steps, and acceptance criteria.
- Record the files that future agents must treat as baseline context.
- Set current progress and initial log entry.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, constraints, adjustment policy, current progress, steps, acceptance criteria, and progress log.
- Next step is clearly identified.

Status: completed

### 1. Freeze Scope And Baseline Inputs

Goal: Make the exact scope of this handoff explicit so later agents do not drift into unrelated provider work.

Main actions:

- Read the current execution plan, matrix contract, and preserved baseline inventory.
- Fix the priority provider set for this slice: Yunwu/OpenAI-compatible, OpenAI official protocol docs, Qwen/DashScope, DeepSeek, Kimi/Moonshot, and GLM/Zhipu.
- Fix the priority lane set for this slice: text, image input, image output, audio input, audio output, tool calling, streaming, structured edit, context window, and reasoning.

Acceptance criteria:

- A written scope note exists under `PRIVATE/agentic-update-pipeline/reports/` or `PLAN/`.
- The scope note explicitly distinguishes in-scope priority lanes from deferred lanes such as official OpenAI live verification.
- A future agent can start the audit without reconstructing provider scope from chat history.

Status: not started

### 2. Build Official Documentation Source Pack

Goal: Gather the minimum primary-source document set required for capability and reasoning claims.

Main actions:

- Record official provider documentation URLs for model lists, modality support, reasoning or thinking controls, tool calling, streaming, and documented limits.
- Record retrieval date, source type, provider id, supported capability categories, and whether each source is stable or likely to drift.
- Keep non-official references clearly separated as secondary context.

Acceptance criteria:

- A source-pack artifact exists and is secret-free.
- Each source entry names the provider, URL, retrieval date, and capability categories it supports.
- Non-official references are clearly marked as secondary rather than mixed into primary evidence.

Status: not started

### 3. Produce Priority Capability Coverage Baseline

Goal: Make the current coverage state visible at the provider/model/capability level.

Main actions:

- Build a baseline matrix or report that separates `declared_capability`, `runtime_normalized_contract`, and `validated_evidence`.
- Record which capabilities are model-specific versus provider-wide defaults.
- Mark each priority lane as `verified`, `partial`, `blocked`, or `unknown` using the existing contract semantics.

Acceptance criteria:

- A baseline artifact exists for the priority providers and priority lanes.
- Model-level capability differences are visible rather than collapsed into provider-wide booleans.
- The baseline points to the exact code or evidence surfaces behind each status.

Status: not started

### 4. Audit Qwen Capability Claims And Multimodal Limits

Goal: Turn Qwen official docs and preserved failures into model-level compatibility conclusions.

Main actions:

- Review Qwen model documentation for text, vision, ASR, TTS, streaming, tool usage, and thinking controls.
- Record documented constraints such as image dimensions, media formats, content-shape limits, and thinking-related request restrictions.
- Compare the documented behavior with AstraBridge's current catalog, adapters, validators, and preserved Qwen evidence.

Acceptance criteria:

- Qwen priority models have lane-level status for text, vision, speech input, speech output, tool usage, and reasoning.
- Known pitfalls such as the tiny-image failure are classified correctly as request-shape constraints rather than blanket provider incompatibility.
- Any mismatch between docs and code is captured as a concrete gap for a later step.

Status: not started

### 5. Audit OpenAI Protocol Assumptions And Yunwu-Compatible Behavior

Goal: Separate official OpenAI protocol assumptions from Yunwu-compatible runtime evidence.

Main actions:

- Review official OpenAI documentation for Responses, reasoning effort, tool calls, image input or output, and streaming.
- Review Yunwu-compatible profiles, adapters, and preserved smoke evidence for the lanes AstraBridge actually exercises.
- Mark which claims are protocol assumptions, which are Yunwu-verified, and which remain unverified without official OpenAI live access.

Acceptance criteria:

- The resulting audit clearly separates OpenAI official protocol claims from Yunwu-compatible evidence.
- No official OpenAI lane is marked live-verified without authorized official-provider testing.
- Yunwu evidence links to preserved secret-free artifacts where available.

Status: not started

### 6. Audit DeepSeek, Kimi, And GLM Capability Claims

Goal: Reconcile current assumptions for the remaining managed providers with official docs and existing evidence.

Main actions:

- Review official docs for DeepSeek, Kimi, and GLM multimodal support, reasoning controls, streaming behavior, and tool-related limits.
- Compare those claims with current provider profiles, transports, route contracts, and preserved smoke results.
- Record provider-specific pitfalls such as no-output behavior, reasoning-content quirks, or modality-specific request-shape limitations.

Acceptance criteria:

- Each priority provider has a documented lane-level state for the priority capabilities.
- Each provider's known pitfalls are recorded with source citations or preserved evidence links.
- Unsupported or weakly supported lanes are not left in an optimistic default state.

Status: not started

### 7. Audit Reasoning-Effort Abstraction

Goal: Decide whether AstraBridge's reasoning-effort algorithm is defensible without exhaustively live-testing every effort level.

Main actions:

- Review official reasoning or thinking controls for the priority providers that expose them.
- Review OpenRouter's reasoning abstraction as a design comparison for effort normalization and unsupported-provider fallback.
- Compare those references with AstraBridge's profile fields, runtime normalization, catalog contract, and transport mappings.

Acceptance criteria:

- A reasoning audit exists with source citations and exact file references.
- The audit distinguishes documented mappings, inferred mappings, unsupported mappings, and noop mappings.
- The audit recommends either concrete code changes or an explicit decision that current behavior is acceptable with caveats.

Status: not started

### 8. Turn Audit Findings Into A Code And Validation Gap List

Goal: Convert research findings into actionable implementation targets.

Main actions:

- Map every high-risk mismatch to the smallest responsible code area, such as catalog metadata, provider profile, validator, transport, router, or UI status surface.
- Assign each gap a risk class, such as route misclassification, invalid request shape, unsupported reasoning mapping, stale capability declaration, or misleading UI.
- Identify which gaps require docs-only updates, which require tests, and which require code changes.

Acceptance criteria:

- A gap report exists with file-level ownership and risk classification.
- Every high-risk gap has a proposed follow-up action or explicit defer reason.
- The next implementation step is unambiguous.

Status: not started

### 9. Implement Highest-Risk Model-Level Capability Fixes

Goal: Remove the most dangerous optimistic assumptions in routing or declaration logic.

Main actions:

- Update model-level capability declarations or gating rules where provider-wide defaults currently overstate support.
- Add or tighten validators for the highest-risk multimodal request-shape constraints documented earlier.
- Keep changes scoped to the smallest surfaces that materially improve correctness.

Acceptance criteria:

- At least the highest-risk model/capability mismatches are blocked or downgraded before live provider calls.
- Tests cover representative positive and negative cases for the changed logic.
- Existing known-good routes continue to resolve.

Status: not started

### 10. Generate Dry-Run Coverage And Reasoning Reports

Goal: Expand coverage without spending provider tokens.

Main actions:

- Build or extend a dry-run report for the priority providers and models that records selected route, normalized contract, request-shape validation, and reasoning-effort mapping.
- Include representative unsupported and unknown cases instead of only success paths.
- Save the outputs in a secret-free form suitable for handoff and CI-style reruns.

Acceptance criteria:

- A dry-run artifact exists for the priority providers and priority lanes.
- The artifact makes unsupported, partial, blocked, and unknown lanes easy to identify.
- The dry-run path does not require live provider credentials.

Status: not started

### 11. Define The Minimal Managed-Key Smoke Set

Goal: Decide what must be live-tested and what can remain static or docs-backed.

Main actions:

- Define one representative text baseline per provider, plus one representative multimodal or reasoning lane where the provider claims support.
- Bound the live-smoke set by cost, token, time, and artifact-redaction rules.
- Exclude official OpenAI direct live validation unless the user later changes scope.

Acceptance criteria:

- A written smoke-selection policy exists.
- The policy justifies why exhaustive model-by-model live testing is not required.
- The authorization boundary for managed-vault usage is explicit.

Status: not started

### 12. Run Authorized Representative Managed-Key Smokes

Goal: Produce bounded live evidence for the highest-risk lanes when the user authorizes managed-vault testing.

Main actions:

- Confirm turn-level authorization before any live provider call.
- Run only the approved representative smokes and preserve sanitized evidence under `PRIVATE/**`.
- Record pass, partial, fail, blocked, or skipped with concrete reasons per case.

Acceptance criteria:

- New live evidence is secret-free and stored under `PRIVATE/**`.
- Each executed case is classified with a concrete reason and linked back to the capability baseline.
- A focused secret scan over the new artifacts passes.

Status: not started

### 13. Update Matrix, Status Surfaces, And Maintenance Runbook

Goal: Make the corrected compatibility story durable for both the product and future agents.

Main actions:

- Update the compatibility matrix or equivalent durable surface with the latest audit and evidence results.
- Tighten any user-facing or runtime-facing status surfaces that currently imply unsupported capabilities are safe.
- Write or update a maintenance runbook for adding models, rechecking docs, rerunning dry-runs, and authorizing live smokes.

Acceptance criteria:

- Durable status surfaces reflect the current evidence state rather than optimistic defaults.
- A future agent has a concrete runbook for updating capability and reasoning mappings.
- Verification commands or command sequences are documented.

Status: not started

### 14. Final Audit And Handoff

Goal: Confirm that the delegated work slice is complete and that the next maintenance entry point is obvious.

Main actions:

- Review deliverables and step acceptance criteria.
- Record residual risks, deferred work, and known provider-specific caveats.
- Write a concise final handoff summary with exact next maintenance entry points.

Acceptance criteria:

- The final handoff lists completed work, validation performed, residual risks, and deferred items.
- The plan's current-progress section matches the real completed state.
- No unresolved high-risk gap is silently omitted from the closing handoff.

Status: not started

## Progress Log

### 2026-07-06 - Step 0

- Completed: Created a durable handoff plan for provider/model capability coverage and reasoning-effort audit work.
- Files changed: `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_HANDOFF_PLAN.md`.
- Validation: Checked that the plan includes total objective, deliverables, related context files, constraints, adjustment policy, execution rules, current progress, numbered steps, acceptance criteria, and progress log.
- Blockers: None.
- Next step: Step 1, Freeze Scope And Baseline Inputs.
