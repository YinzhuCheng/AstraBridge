# Provider Model Compatibility Remaining Follow-up Plan

## Total Objective

Close the currently most material provider/model compatibility gaps for AstraBridge without depending on an official OpenAI direct API key. The target outcome is a tighter, evidence-backed compatibility story for the managed providers already available in the app: Kimi, Qwen, Yunwu, and GLM, plus the shared compact/long-context and UI verification lanes that affect cross-provider switching quality.

## Scope Decision

- Deferred for now: official OpenAI direct provider validation.
- Assumption for this plan: the user's "5 can暂时不做" refers to the previously discussed official OpenAI direct validation item, not to Step 5 in the older residual-risk plan.
- Still in scope: Kimi same-task handoff, because it affects the core "same task, switch provider smoothly" product claim.

## Constraints And Attention Notes

1. Preserve `PRIVATE/**` experiment artifacts, reports, screenshots, sanitized raw records, and validation outputs by default.
2. Never persist API keys, bearer tokens, cookies, admin session tokens, vault passwords, or provider raw secrets.
3. Provider-backed validation must use managed app/sidecar surfaces and produce secret-free evidence only.
4. Do not promote a lane to "verified" based only on static metadata, dry-run fixtures, or local mocks.
5. Keep changes aligned with the existing provider profile, catalog, transport, runtime, and UI warning architecture.
6. If a provider cannot meet the intended capability level, explicitly tier it down and surface that in runtime/UI status instead of leaving the failure implicit.

## Adjustment Policy

Agents may adjust filenames, substeps, commands, or exact sequencing when repository state requires it, but must not change the objective, weaken the evidence bar, or remove provider-backed gates. If a lane cannot be closed in the current product boundary, the fallback is an explicit reduced-authority decision with concrete evidence and warning surfaces.

## Current Progress

- Current status: planned
- Completed steps: none in this plan
- Current step: 1. Kimi Provider-Backed Code-Agent Validation
- Next step: 1. Kimi Provider-Backed Code-Agent Validation
- Last updated: 2026-07-05

## Execution Steps

### 1. Kimi Provider-Backed Code-Agent Validation

Goal: Verify whether the Kimi schema fix actually restores usable text and shell/code-agent behavior.

Main actions:

- Run fresh Kimi text smoke and code-agent smoke through the managed vault path.
- Preserve sanitized request/response metadata, terminal state, command-event counts, and warning fields.
- Record whether Kimi now executes at least one real command or still fails after schema normalization.

Acceptance criteria:

- Secret-free Kimi provider-backed evidence exists under `PRIVATE/provider-compatibility/`.
- Kimi code-agent status is explicitly pass, partial, or fail based on observable command execution evidence.
- A focused secret scan over the new Kimi artifacts passes.

Status: not started

### 2. Kimi Same-Task Handoff Revalidation

Goal: Re-check whether Kimi can safely act as a same-task target provider after the code-agent result is known.

Main actions:

- Run a Qwen -> Kimi or other approved source -> Kimi handoff case that matches Kimi's verified authority level.
- Inspect provider handoff metadata, projection behavior, terminal states, and warnings.
- If Kimi remains weak for tool-rich continuity, define the exact fallback guidance.

Acceptance criteria:

- Fresh same-task handoff evidence exists with explicit pass/partial/fail status.
- Runtime or UI state makes the fallback path visible when Kimi is not a safe target.
- No provider-private or secret-bearing state is replayed across providers.

Status: not started

### 3. Qwen TTS Request Contract Repair

Goal: Fix the request construction path behind the current Qwen TTS failure or explicitly downgrade the route.

Main actions:

- Inspect the Qwen/DashScope TTS request builder and target endpoint contract.
- Add or update secret-free tests for the intended payload shape.
- Repair the adapter path so TTS is not sent through the wrong generic request shape.

Acceptance criteria:

- Contract coverage exists for the failure-producing TTS payload shape.
- Existing Qwen text, vision, and ASR behavior remains intact.
- If unsupported in the current boundary, the route is explicitly downgraded with a clear warning.

Status: not started

### 4. Qwen TTS Provider-Backed Smoke

Goal: Validate Qwen TTS end to end after contract repair, or record a justified downgrade.

Main actions:

- Run provider-backed `speech.synthesize` smoke through the supported app/sidecar path.
- Preserve sanitized route metadata, errors, and any generated audio artifact.
- Update smoke evidence and readiness notes from the real outcome.

Acceptance criteria:

- Provider-backed Qwen TTS evidence exists with pass/partial/fail status.
- Successful runs include a persisted local artifact with path and metadata.
- A focused secret scan over the new Qwen TTS artifacts passes.

Status: not started

### 5. Yunwu Image Artifact Persistence Repair

Goal: Ensure Yunwu image generation results become durable local artifacts instead of transient success with missing files.

Main actions:

- Inspect the current Yunwu image response normalization and artifact persistence path.
- Add or update tests for supported provider response shapes such as URL, base64, or provider reference forms.
- Repair manifest and local file persistence behavior.

Acceptance criteria:

- Regression coverage exists for the earlier persistence failure shape.
- Successful normalization produces a local artifact path and preview-ready metadata.
- No base64 blobs or secrets leak into durable summaries.

Status: not started

### 6. Yunwu Image Provider-Backed Revalidation And UI Preview

Goal: Revalidate Yunwu image generation end to end and confirm the app can preview the resulting artifact.

Main actions:

- Run a provider-backed Yunwu image generation smoke.
- Verify the manifest points at a real local file.
- Capture UI evidence showing preview success or a precise warning state.

Acceptance criteria:

- Provider-backed Yunwu image evidence exists with pass/partial/fail status.
- At least one local artifact exists for a successful run.
- UI screenshot evidence is preserved under `PRIVATE/**`.

Status: not started

### 7. GLM Tool-Call And Command Event Contract Repair

Goal: Determine whether GLM can reliably produce command execution events or must be treated as reduced-authority for code-agent work.

Main actions:

- Inspect GLM tool-call parsing and runtime command-event conversion.
- Add or update regression tests for command-event-positive and no-command-event paths.
- Ensure runtime warnings distinguish "turn completed" from "tool actually executed".

Acceptance criteria:

- Secret-free test coverage exists for the key GLM tool-call paths.
- Runtime metadata can represent GLM partial or reduced-authority status cleanly.
- Existing GLM text or handoff paths are not regressed.

Status: not started

### 8. GLM Provider-Backed Code-Agent Revalidation

Goal: Re-run GLM code-agent validation and either confirm command execution or tier the lane down explicitly.

Main actions:

- Run provider-backed GLM text and code-agent smokes.
- Preserve sanitized command-event counts, parsed tool-call metadata, warnings, and terminal states.
- Update fallback guidance for when users should switch away from GLM.

Acceptance criteria:

- Fresh provider-backed GLM evidence exists.
- GLM is either validated with command execution evidence or explicitly reduced-authority with concrete reasons.
- A focused secret scan over the new GLM artifacts passes.

Status: not started

### 9. Compact And Long-Context Harness

Goal: Build a repeatable harness for context budget, auto-compact, and continuation validation before spending provider calls.

Main actions:

- Define synthetic long-context inputs that are secret-free and reproducible.
- Add or update tests for budget reporting, compact trigger, compact summary metadata, and fallback classification.
- Record declared context, effective context, and post-compact continuation state.

Acceptance criteria:

- Local harness coverage exists and passes.
- Harness outputs are structured enough to feed matrix/report evidence.
- Durable outputs stay secret-free and reasonably sized.

Status: not started

### 10. Provider-Backed Compact And Long-Context Validation

Goal: Replace "configured but unverified" compact/context claims with real evidence for current managed providers.

Main actions:

- Run the harness against priority providers such as Qwen, DeepSeek, Yunwu, and one additional lane judged safe.
- Record compact summary quality, limit classification, continuation behavior, and fallback guidance.
- Update matrix/report status per provider.

Acceptance criteria:

- Provider-backed compact/context evidence exists for at least three active providers.
- Each tested provider has pass/partial/fail reporting for compact quality and limit handling.
- A focused secret scan over the new evidence passes.

Status: not started

### 11. In-App Browser Screenshot Reliability

Goal: Make UI verification dependable again, either by fixing the in-app browser path or by clearly documenting the fallback.

Main actions:

- Reproduce the current in-app browser screenshot or tab-list failure path.
- Determine whether the issue is in repo code, plugin session state, or local tooling boundary.
- Fix it if it is owned by this repo; otherwise codify the Playwright fallback and preserve proof.

Acceptance criteria:

- A working screenshot path is demonstrated and recorded.
- At least one fresh screenshot artifact is preserved under `PRIVATE/**`.
- The verification workflow clearly states when to use the in-app browser versus Playwright.

Status: not started

### 12. Final Residual-Risk Gate

Goal: Consolidate the remaining-risk work into a final readiness statement that is tighter than the current baseline.

Main actions:

- Run the relevant backend tests, compile checks, diff checks, and focused secret scans.
- Summarize Kimi, Qwen TTS, Yunwu image, GLM, compact/context, and UI verification results.
- Update matrix, warnings, and runbook/report surfaces from the actual evidence.

Acceptance criteria:

- Final report states which lanes are verified, downgraded, or still warning-gated.
- Tests and preserved provider-backed evidence are internally consistent.
- The final secret scans over changed files and evidence paths pass.

Status: not started

## Progress Log

### 2026-07-05

- Completed: Created a fresh remaining-risk follow-up plan that explicitly defers official OpenAI direct validation and sequences the currently actionable provider/runtime gaps into one-step-per-round execution units.
- Files changed: `PLAN/PROVIDER_MODEL_COMPATIBILITY_REMAINING_FOLLOWUP_PLAN.md`
- Validation: Re-read the current residual-risk execution plan and aligned this follow-up plan to the already identified remaining gaps while removing the official OpenAI dependency.
- Blockers: None.
- Next step: Step 1, Kimi Provider-Backed Code-Agent Validation.
