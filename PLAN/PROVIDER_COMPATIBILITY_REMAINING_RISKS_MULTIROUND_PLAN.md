# Provider Compatibility Remaining Risks Multi-Round Plan

## Total Objective

Close the currently relevant provider/model compatibility risks that still prevent AstraBridge from making a stronger "same-task controlled switching" claim across the managed provider set. This plan explicitly excludes official OpenAI direct API-key validation for now because no official OpenAI key is available. The target end state is not "all providers fully equal", but "every important lane is either provider-backed verified or explicitly downgraded with visible fallback guidance and durable evidence."

## Deliverables

- A refreshed remaining-risk baseline that points to the exact unresolved evidence and code owners.
- Provider-backed or explicitly downgraded outcomes for the unresolved GLM, Qwen TTS, Kimi, compact/long-context, and UI screenshot lanes.
- Updated runtime/catalog/UI status surfaces that distinguish verified, partial, and reduced-authority lanes.
- A final readiness report and compatibility matrix update that separate closed risks from warning-gated risks.

## Out Of Scope

- Official OpenAI direct provider validation through an official OpenAI API key.
- Reintroducing official OpenAI account login as a product path.
- Cleaning `PRIVATE/**`, smoke artifacts, raw traces, logs, or caches unless the user explicitly names cleanup targets.

## Constraints And Attention Notes

1. Preserve all experiment artifacts, smoke outputs, reports, screenshots, manifests, raw request metadata, raw response metadata, and validation records unless the user explicitly asks for cleanup.
2. Never persist API keys, vault passwords, admin session tokens, cookies, bearer tokens, authorization headers, or plaintext secret material in git, reports, logs, or plan notes.
3. If managed-provider validation is needed, use the app/sidecar-managed vault surfaces only. Do not read desktop plaintext key files directly.
4. Do not mark a lane "verified" from metadata-only reasoning, dry-run evidence, or UI appearance alone. Provider-backed evidence or an explicit downgrade decision is required.
5. Keep web search as a standalone web lane unless the user explicitly changes that product boundary.
6. Prefer existing AstraBridge profile, catalog, transport, authority, runtime, and desktop patterns over introducing parallel adapter systems.
7. Preserve prior execution plans and completed history. This plan is a new execution slice for the remaining unresolved risks, not a rewrite of old records.

## Adjustment Policy

Agents may adjust filenames, substeps, exact commands, implementation details, validation order, or report paths when the facts on disk require it. Those adjustments must not change the total objective, lower the quality bar, remove provider-backed validation gates, or replace substantive compatibility work with cosmetic-only changes. If a lane cannot currently be upgraded to verified status, the acceptable substitute is an explicit downgrade with durable evidence, UI/runtime warnings, and concrete fallback guidance.

## Execution Rules

1. Each user-facing round should complete exactly one numbered step unless the user explicitly redirects otherwise.
2. Start from the earliest numbered step whose status is not `completed`.
3. Update this plan file before ending the round.
4. A step may be marked `completed` only when all acceptance criteria for that step are satisfied.
5. If blocked, mark the step `blocked`, record the exact blocker and next entry point, and do not leave vague continuation notes.
6. Every completed round must record files changed, validation run, blockers, and the exact next step in the progress log.

## Current Progress

- Current status: Not started
- Completed steps: none
- Current step: 1. Remaining-Risk Baseline Refresh
- Next step: 1. Remaining-Risk Baseline Refresh
- Last updated: 2026-07-05

## Numbered Execution Steps

### 1. Remaining-Risk Baseline Refresh

Goal: Rebuild a clean baseline for only the still-open compatibility risks.

Main actions:

- Read the latest evidence and code paths for GLM code-agent behavior, Qwen TTS artifact validity, Kimi same-task target reliability, compact/long-context validation, and in-app browser screenshot reliability.
- Record exact current status, source owners, evidence paths, known blockers, and candidate fix paths.
- Write a fresh secret-free baseline report under `PRIVATE/provider-compatibility/reports/`.

Acceptance criteria:

- Baseline report lists every remaining risk with current status, evidence path, affected code paths, and intended execution step.
- Report explicitly states official OpenAI direct validation is deferred and out of scope.
- Focused secret scan over the new baseline report passes.

Status: not started

### 2. GLM Provider-Backed Code-Agent Revalidation

Goal: Decide whether GLM can actually execute code-agent work or must remain reduced-authority.

Main actions:

- Run authorized GLM provider-backed text and code-agent cases through the managed vault path.
- Capture sanitized terminal state, command-event count, parsed tool-call metadata, and warnings.
- Classify the result as `pass`, `partial`, or `reduced-authority`.

Acceptance criteria:

- Evidence shows either at least one observable `commandExecution` event or a durable reduced-authority decision with concrete reasons.
- Evidence files are preserved under `PRIVATE/provider-compatibility/`.
- Focused secret scan over the new GLM evidence passes.

Status: not started

### 3. GLM Fallback Surface Closure

Goal: Make the GLM reduced-authority boundary visible and actionable across product surfaces if Step 2 does not produce a full pass.

Main actions:

- Audit runtime, catalog, route, and desktop surfaces for how GLM code-agent partial status is shown.
- Add or tighten warnings, authority hints, or fallback text that steer users toward Qwen, Yunwu, or DeepSeek where appropriate.
- Add focused regression coverage for the chosen UI/runtime exposure path.

Acceptance criteria:

- GLM partial or reduced-authority state is visible through the intended runtime/catalog/UI surface.
- Tests cover the warning or fallback exposure path.
- No stronger claim than the provider-backed evidence supports is exposed.

Status: not started

### 4. Compact And Long-Context Harness Repair

Goal: Build a repeatable harness for validating compact and context-limit behavior before live provider checks.

Main actions:

- Define synthetic long-context cases that are safe to preserve.
- Add dry-run coverage for budget reporting, compact trigger conditions, summary quality metadata, context-limit classification, and fallback recommendations.
- Ensure the harness records declared context, effective context, compact threshold, and post-compact continuation state.

Acceptance criteria:

- Dry-run compact/long-context tests pass.
- Harness output is structured enough to feed matrix and report updates later.
- No oversized raw prompts or secrets are persisted in durable artifacts.

Status: not started

### 5. Provider-Backed Compact And Long-Context Validation

Goal: Replace metadata-only compact status with live evidence for the current managed provider set.

Main actions:

- Run provider-backed compact/long-context validation for at least three priority providers.
- Capture post-compact continuation quality, context-limit classification, fallback recommendation, and any handoff behavior after compact.
- Record pass/partial/fail per provider rather than leaving all lanes at `configured_unverified`.

Acceptance criteria:

- Provider-backed evidence exists for at least three managed providers.
- Matrix or report clearly records per-provider compact quality and context-limit handling.
- Focused secret scan over the new long-context evidence passes.

Status: not started

### 6. Qwen TTS Audio Container Normalization

Goal: Resolve the remaining gap where Qwen TTS produces an artifact that persists but is not a valid requested audio container.

Main actions:

- Inspect the current TTS adapter, artifact assembly path, and provider response forms.
- Add tests for the observed invalid-container shape and at least one valid persistence path.
- Implement the narrowest fix that preserves existing route and artifact behavior.

Acceptance criteria:

- Regression tests cover the prior invalid-container outcome.
- Persisted artifact validation now distinguishes valid versus corrupt output correctly.
- Existing Qwen text, vision, and ASR behavior remains unaffected.

Status: not started

### 7. Qwen TTS Provider-Backed Revalidation

Goal: Re-run live Qwen TTS after Step 6 and classify the lane as verified or warning-gated with current evidence.

Main actions:

- Run authorized provider-backed `speech.synthesize` smoke through the intended runtime path.
- Preserve audio artifact, transcript or text sidecar, manifest metadata, and sanitized response summary.
- Verify the produced audio is both non-empty and structurally valid for the requested format.

Acceptance criteria:

- Provider-backed evidence ends with either a valid persisted audio artifact or an explicit warning-gated downgrade with concrete reason.
- Manifest includes local path, provider/model, mime/type metadata, and case id.
- Focused secret scan over the new Qwen TTS evidence passes.

Status: not started

### 8. Kimi Same-Task Target Reliability Closure

Goal: Close the remaining ambiguity around Kimi as a same-task target provider.

Main actions:

- Re-read current Kimi handoff and code-agent evidence.
- Decide whether a further provider-backed retest is justified or whether the lane should remain explicitly text-safe only.
- Update fallback guidance, downgrade boundaries, and any relevant tests or status surfaces accordingly.

Acceptance criteria:

- Kimi target behavior is classified in a way that matches the live evidence.
- Same-task fallback guidance is concrete about when Kimi should and should not be selected.
- No provider-private state or secret-bearing data is replayed across lanes.

Status: not started

### 9. In-App Browser Screenshot Reliability

Goal: Restore a reliable screenshot path for UI verification, preferably through the in-app browser.

Main actions:

- Reproduce the current in-app browser listing/screenshot reliability issue.
- Determine whether the fix belongs in repo code, plugin/session handling, or test workflow documentation.
- If repo-fixable, implement the narrow fix; otherwise preserve a documented Playwright fallback path.

Acceptance criteria:

- At least one reliable screenshot workflow is on record.
- A fresh screenshot artifact is preserved under `PRIVATE/**`.
- The QA workflow clearly states when to use the in-app browser and when to fall back.

Status: not started

### 10. Compatibility Matrix And Status Surface Consolidation

Goal: Bring the current evidence back into the product-facing compatibility surfaces.

Main actions:

- Audit the compatibility matrix, provider status metadata, authority surfaces, and any desktop views that summarize capability readiness.
- Update those surfaces so they reflect the actual latest evidence for GLM, Qwen TTS, Kimi, compact validation, and screenshot workflow readiness.
- Add focused tests where these surfaces are generated from code rather than static docs.

Acceptance criteria:

- Product-facing compatibility/status surfaces no longer overclaim readiness for any unresolved lane.
- Evidence-backed passes, partials, and downgrades are represented consistently.
- Regression coverage exists for any code-generated status surface changes.

Status: not started

### 11. Router Fallback And Same-Task Switching Gate

Goal: Re-check that same-task switching behavior matches the newly consolidated authority and fallback data.

Main actions:

- Run focused routing or handoff validation for a small set of representative lanes, especially around downgraded providers.
- Confirm route selection, warning handling, and fallback recommendations stay coherent after the status-surface updates.
- Preserve sanitized switching evidence where it adds value.

Acceptance criteria:

- Representative same-task switching cases remain coherent with the latest downgrade and fallback rules.
- Fallback guidance is visible where route choice is constrained.
- No regression appears in existing verified handoff paths.

Status: not started

### 12. Final Remaining-Risk Readiness Gate

Goal: Close this plan with a final statement of what is truly verified versus warning-gated.

Main actions:

- Run final focused tests, compile checks, diff checks, and secret scans for the files touched in this plan.
- Summarize all new evidence, code changes, unresolved warnings, and fallback guidance.
- Write a final readiness report under `PRIVATE/provider-compatibility/reports/`.

Acceptance criteria:

- Final report clearly separates verified lanes, partial lanes, reduced-authority lanes, and deferred items.
- Deferred official OpenAI direct validation remains explicitly out of scope.
- Next maintenance entry points are unambiguous for future model upgrades or new-provider onboarding.

Status: not started

## Progress Log

- 2026-07-05: Created this plan as a fresh remaining-risk execution slice after deferring official OpenAI direct API-key validation. No implementation work has been performed under this new plan yet. Next step: `1. Remaining-Risk Baseline Refresh`.
