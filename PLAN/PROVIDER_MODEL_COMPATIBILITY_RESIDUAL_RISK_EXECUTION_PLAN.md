# Provider Model Compatibility Residual Risk Execution Plan

## Total Objective

Close the remaining provider/model compatibility risks identified by the Step 15 final readiness review, excluding official OpenAI direct key-backed validation for now because no official OpenAI API key is currently available. The end state is that AstraBridge can make a stronger controlled-switching claim for the current managed providers by resolving or explicitly tiering the remaining partial lanes: Kimi tool/code-agent and handoff reliability, Qwen TTS, Yunwu image artifact persistence, GLM command execution, compact/long-context validation, and in-app browser screenshot reliability.

## Deliverables

- Provider-specific fixes or explicit tier-down decisions for Kimi, Qwen, Yunwu, and GLM residual risks.
- Provider-backed, sanitized smoke evidence under `PRIVATE/provider-compatibility/` for every fixed or tiered lane.
- Updated compatibility matrix/status data, UI warnings, and runbook notes reflecting the new evidence.
- A final residual-risk readiness report that states which risks were closed, which remain warning-gated, and why.

## Out Of Scope

- Official OpenAI direct provider validation is intentionally deferred. Do not block this plan on official OpenAI API access, and do not read desktop key files to obtain one.
- Do not reintroduce official OpenAI account login. OpenAI-compatible testing may continue through Yunwu where relevant.

## Constraints And Attention Notes

1. Preserve experiment artifacts, raw call records, sanitized responses, parsed outputs, validation reports, screenshots, logs, and caches by default.
2. Never persist API keys, bearer tokens, cookies, authorization headers, vault passwords, admin session tokens, provider raw secrets, or desktop `key.txt` contents.
3. Provider-backed smoke tests must be explicit, redacted, and recorded as sanitized evidence only. Use the managed `astra` vault only through app/sidecar surfaces that keep secrets redacted.
4. Keep web search as a standalone web lane unless the user explicitly changes that product boundary.
5. Do not promote a provider/model/capability lane to verified using only declared metadata or dry-run evidence; provider-backed evidence or an explicit reduced-authority/tier-down decision is required.
6. Favor existing AstraBridge profile, catalog, transport, capability, runtime, task, and UI patterns over broad new abstractions.
7. For app/UI changes, verify visually when feasible and preserve screenshots under `PRIVATE/**`. If in-app browser control is unavailable, use Playwright as a fallback and record that fact.

## Adjustment Policy

Agents may reasonably adjust specific substeps, implementation details, file paths, commands, or sequencing when evidence from the workspace requires it. Such adjustments must not change the total objective, lower the planned difficulty, remove provider-backed validation gates, remove secret-redaction requirements, or replace substantive compatibility work with cosmetic UI-only work. If a core objective becomes infeasible, record the blocker, evidence, attempted approaches, and a substitute path that preserves the original intent, such as tiering a provider down until upstream behavior can be verified.

## Execution Rules

1. Each user-facing execution round should complete exactly one numbered step from this plan unless the user explicitly asks otherwise.
2. Start from the earliest numbered step whose status is not `completed`, unless the user redirects to a specific step.
3. Each round must update this plan before stopping.
4. A step can be marked `completed` only when all of its acceptance criteria are met.
5. If blocked, mark the step `blocked`, record the concrete blocker and next entry point, and do not leave vague continuation notes.
6. Each round must end with a handoff summary: completed work, files changed, validation run, blockers, and the exact next step.

## Current Progress

- Current status: Completed
- Completed steps: 0. Create Durable Plan; 1. Residual Evidence Baseline And Reproduction Map; 2. Kimi Tool Schema Reproduction And Contract Test; 3. Kimi Shell Tool Schema Normalization; 4. Kimi Provider-Backed Code-Agent Validation; 5. Kimi Same-Task Handoff Revalidation; 6. Qwen TTS Request Contract Repair; 7. Qwen TTS Provider-Backed Smoke; 8. Yunwu Image Artifact Persistence Repair; 9. Yunwu Image Provider-Backed Smoke And UI Preview; 10. GLM Tool-Call And Command Event Instrumentation; 11. GLM Provider-Backed Code-Agent Revalidation; 12. Compact And Long-Context Validation Harness; 13. Provider-Backed Compact And Long-Context Validation; 14. In-App Browser Screenshot Reliability; 15. Residual Risk Final Gate
- Current step: None. Plan complete.
- Next step: None. Plan complete.
- Scope note: Official OpenAI direct provider validation remains explicitly deferred by user direction because no current official API key is available. Do not add it back into the active queue until the user provides a key or changes scope.
- Last updated: 2026-07-05

## Remaining Multi-Round Execution Slice

This plan is complete. The preserved residual-risk evidence and final readiness stance now live in the Step 15 report and the provider compatibility runbook. Official OpenAI direct provider validation remains deferred and is not part of this completed execution slice unless the user later opens a new follow-on plan.

### Remaining Goals

None. All goals in this residual-risk execution slice are complete.

### Remaining Round Order

None. No active rounds remain in this plan.

### Remaining Round Acceptance Summary

- Steps 7-15 are complete and remain part of the preserved evidence base; do not reopen them unless fresh regressions, provider/model upgrades, or a new official OpenAI direct validation scope require a follow-on plan.

## Execution Steps

### 0. Create Durable Plan

Goal: Create this residual-risk execution plan and make the next entry point clear.

Main actions:

- Define the reduced scope that excludes official OpenAI direct key-backed validation.
- Preserve the remaining risk list from the final readiness review.
- Sequence Kimi, Qwen TTS, Yunwu image persistence, GLM command execution, compact/long-context, in-app browser, and final gate work into independently executable steps.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, deliverables, out-of-scope boundary, constraints, adjustment policy, execution rules, numbered steps, acceptance criteria, and progress log.
- Current and next step are clearly identified.

Status: completed

### 1. Residual Evidence Baseline And Reproduction Map

Goal: Produce a fresh baseline map for the remaining risks before changing code.

Main actions:

- Read Step 10, Step 11, Step 12, Step 13, Step 14, and Step 15 evidence and extract the exact failing cases.
- Map each residual risk to source owners, tests, API endpoints, provider-backed smoke commands, expected artifacts, and UI surfaces.
- Record a secret-free baseline report under `PRIVATE/provider-compatibility/reports/`.

Acceptance criteria:

- Baseline report lists Kimi, Qwen TTS, Yunwu image artifact persistence, GLM command execution, compact/long-context, and in-app browser risks with source files and evidence paths.
- Report explicitly states official OpenAI direct evidence is deferred and not part of this plan.
- Focused secret scan over the new baseline report passes.

Status: completed

### 2. Kimi Tool Schema Reproduction And Contract Test

Goal: Turn the Kimi/Moonshot shell tool schema failure into a deterministic local contract test before fixing it.

Main actions:

- Inspect the current shell/code-agent tool schema generated for Kimi/Moonshot.
- Add or update tests that reproduce Moonshot's complaint: `required` references a field not defined in `properties`.
- Define the normalized Kimi-compatible shell tool schema shape without weakening other providers.

Acceptance criteria:

- A failing or newly passing regression test proves the current Kimi schema issue is covered.
- Test fixture is secret-free and does not require a provider call.
- The expected Kimi-compatible schema shape is documented in test assertions or a short code comment.

Status: completed

### 3. Kimi Shell Tool Schema Normalization

Goal: Normalize shell/tool schemas for Kimi/Moonshot without regressing other provider tool-call behavior.

Main actions:

- Implement provider-specific schema normalization in the existing transport/tooling boundary.
- Ensure shell tool `properties`, `required`, argument names, and nested objects are accepted by Moonshot-flavored validation.
- Preserve existing OpenAI-compatible, Qwen, DeepSeek, and GLM tool schema behavior unless tests prove a shared fix is safe.

Acceptance criteria:

- Kimi schema regression test passes.
- Existing tool-call compatibility, transport registry, and model authority tests pass.
- Runtime/catalog output still marks unverified or reduced-authority models conservatively where appropriate.

Status: completed

### 4. Kimi Provider-Backed Code-Agent Validation

Goal: Prove or tier down Kimi code-agent behavior with fresh provider-backed evidence after schema normalization.

Main actions:

- Run an authorized Kimi provider-backed text smoke and code-agent/shell-file smoke through the managed vault.
- Preserve sanitized request metadata, sanitized response metadata, terminal state, command-event count, and warnings.
- If Kimi still cannot execute tools reliably, explicitly record the reduced-authority tier and UI/runtime warnings.

Acceptance criteria:

- Evidence exists under `PRIVATE/provider-compatibility/runs/` and report path for Kimi text and code-agent.
- Kimi code-agent either passes with observable command execution events or is explicitly tiered down with concrete reasons.
- Secret scan over Kimi evidence passes.

Status: completed

### 5. Kimi Same-Task Handoff Revalidation

Goal: Revalidate Qwen -> Kimi handoff after the Kimi tool-schema fix or tier-down decision.

Main actions:

- Rerun a same-task Qwen -> Kimi handoff case with a safe prompt class that matches Kimi's intended tier.
- Confirm provider handoff event, source lane, target lane, projection mode, warning handling, and terminal statuses.
- If Kimi remains unsuitable as a target for tool-rich handoff, update fallback guidance and UI/runtime warning surfaces.

Acceptance criteria:

- Fresh Qwen -> Kimi handoff evidence exists with pass/partial/fail status and concrete reasons.
- Same-task continuity or safe fallback is visible in API/UI state.
- No provider-private reasoning, response IDs, signatures, or secrets are replayed across providers.

Status: completed

### 6. Qwen TTS Request Contract Repair

Goal: Fix or explicitly downgrade Qwen `speech.synthesize` readiness based on a correct request contract.

Main actions:

- Inspect Qwen/DashScope TTS or omni request requirements and current `speech.synthesize` request builder.
- Add a dry-run/fixture test for the expected TTS payload shape.
- Adjust capability adapter/request builder so TTS is not sent as an incompatible generic chat completions request.

Acceptance criteria:

- TTS request-shape test covers endpoint/model/message/output parameters that caused the sanitized DashScope 400.
- Existing Qwen text, vision, and ASR tests remain unaffected.
- If the correct API shape cannot be supported in this slice, route readiness is downgraded with a clear warning instead of hidden failure.

Status: completed

### 7. Qwen TTS Provider-Backed Smoke

Goal: Validate Qwen `speech.synthesize` after request repair or record a justified downgrade.

Main actions:

- Run authorized `speech.synthesize` provider smoke through `/api/runtime/capability-smoke`.
- Preserve audio artifacts, text sidecars, sanitized errors, and route metadata under `PRIVATE/**` or workspace-local `.astrabridge/`.
- Update capability route smoke status and matrix-linked evidence.

Acceptance criteria:

- Qwen TTS provider-backed smoke passes with a persisted audio artifact, or the route is explicitly marked partial/fail with a concrete provider-side reason.
- Artifact manifest contains local path, mime/type metadata, existence status, provider/model, and case id.
- Secret scan over Qwen TTS evidence passes.

Status: completed

### 8. Yunwu Image Artifact Persistence Repair

Goal: Ensure Yunwu `gpt-image-2` image generation produces a persisted local artifact and manifest entry when the provider returns image data or references.

Main actions:

- Inspect current Yunwu image adapter/parser and artifact persister.
- Add tests for provider responses that contain URL, base64, or artifact reference forms supported by the adapter.
- Normalize successful image responses into local `.astrabridge/` or `PRIVATE/**` files with preview metadata.

Acceptance criteria:

- Image artifact persistence tests cover the Step 12 failure shape and at least one successful local artifact path.
- No inline base64 image data is persisted in matrix/report summaries.
- Existing image generation response normalization remains secret-free.

Status: completed

### 9. Yunwu Image Provider-Backed Smoke And UI Preview

Goal: Revalidate Yunwu `gpt-image-2` image generation end to end after artifact persistence repair.

Main actions:

- Run authorized `image.generate` provider smoke through the capability smoke endpoint.
- Confirm local image artifact exists, manifest references it, and the desktop capability panel can preview it.
- Preserve screenshot evidence under `PRIVATE/**`.

Acceptance criteria:

- Provider smoke returns pass or a justified partial/fail with concrete reasons.
- At least one local image artifact exists and is referenced by manifest/summary.
- UI screenshot shows image artifact preview or a clear warning if provider output is unusable.
- Secret scan over image evidence passes.

Status: completed

### 10. GLM Tool-Call And Command Event Instrumentation

Goal: Determine whether GLM can produce command execution events or should be tiered down for code-agent autonomy.

Main actions:

- Inspect GLM transport/parser behavior for tool calls and command execution conversion.
- Add tests for GLM tool-call response shapes, including no-tool final-answer behavior.
- Ensure runtime warnings distinguish "turn completed" from "command executed".

Acceptance criteria:

- Tests cover GLM command-event-positive and command-event-missing paths.
- Runtime/model authority metadata can represent GLM code-agent partial status.
- Existing GLM text and handoff behavior is not regressed.

Status: completed

### 11. GLM Provider-Backed Code-Agent Revalidation

Goal: Revalidate GLM code-agent behavior with command-event evidence or explicitly tier it down.

Main actions:

- Run authorized GLM provider-backed text and code-agent smoke.
- Preserve sanitized terminal status, command-event count, parsed tool-call metadata, and warnings.
- Update matrix/UI/docs with pass, partial, or tier-down result.

Acceptance criteria:

- Evidence shows at least one command execution event for GLM code-agent, or GLM is explicitly reduced-authority with warnings.
- Fallback guidance tells users when to switch from GLM to Qwen/Yunwu/DeepSeek for code-agent work.
- Secret scan over GLM evidence passes.

Status: completed

### 12. Compact And Long-Context Validation Harness

Goal: Build a repeatable compact/long-context validation harness before running provider-backed long-context checks.

Main actions:

- Define test prompts or synthetic project context that approach compact thresholds without persisting secrets.
- Add dry-run tests for budget report, auto-compact trigger, compact summary quality metadata, provider context-limit classification, and fallback recommendation.
- Ensure the harness records declared context, effective context, compact threshold, and post-compact continuation state.

Acceptance criteria:

- Dry-run long-context/compact tests pass.
- Harness output can feed the compatibility matrix `validated_evidence` section.
- No raw provider secrets or oversized raw prompts are persisted in durable reports.

Status: completed

### 13. Provider-Backed Compact And Long-Context Validation

Goal: Validate compact/long-context behavior against selected current providers using the harness.

Main actions:

- Run provider-backed compact/long-context smoke for priority lanes, starting with Qwen, DeepSeek, Yunwu, and one GLM or Kimi lane if safe.
- Confirm post-compact continuation, context-limit rejection classification, fallback recommendation, and handoff behavior after compact.
- Record per-provider compact summary quality instead of leaving all lanes as `configured_unverified`.

Acceptance criteria:

- Provider-backed evidence exists for at least three current managed providers.
- Matrix or report records pass/partial/fail for compact quality and context-limit handling per provider.
- Secret scan over long-context evidence passes.

Status: completed

### 14. In-App Browser Screenshot Reliability

Goal: Repair or document the in-app browser tab API reliability issue so UI verification can consistently use the intended browser path.

Main actions:

- Reproduce `browser.tabs.list()` timeout against the in-app browser on the local app.
- Diagnose whether failure is plugin session state, browser backend selection, app launch isolation, or tab lifecycle.
- Fix the issue if it is in repo code; otherwise document Playwright fallback and update UI QA runbook.

Acceptance criteria:

- In-app browser tab listing and screenshot either work on the local app or a clear external/tooling blocker is recorded.
- At least one fresh UI screenshot is preserved under `PRIVATE/**` using the working path.
- The verification workflow documents when to use Playwright fallback.

Status: completed

### 15. Residual Risk Final Gate

Goal: Close this residual-risk plan with a final readiness report and updated compatibility status.

Main actions:

- Run final backend tests, desktop tests, type checks, py_compile, diff check, and secret scans.
- Summarize new provider-backed evidence for Kimi, Qwen TTS, Yunwu image, GLM, compact/long-context, and browser UI verification.
- Update runbook/matrix/UI status to reflect fixed lanes or deliberate tier-down decisions.
- Produce a final residual-risk readiness report under `PRIVATE/provider-compatibility/reports/`.

Acceptance criteria:

- Tests and selected provider-backed smoke evidence are internally consistent.
- Secret scan passes over changed files and relevant evidence paths.
- Final report states which residual risks were closed, which remain warning-gated, and whether the product claim can be strengthened.

Status: completed

## Progress Log

### 2026-07-05 - Step 15

- Completed: Closed the residual-risk plan with a final readiness review grounded in the current managed-provider evidence set. The Step 15 final report and machine-readable summary now state the strongest defensible claim precisely: AstraBridge can make a stronger evidence-backed controlled-switching claim for the current managed providers, but it still cannot claim seamless arbitrary switching across all models and providers. The runbook was aligned to the latest evidence so its current provider status, evidence index, and operator guidance match the actual Step 13 through Step 15 findings rather than the older partial matrix.
- Files changed: `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`, `PRIVATE/provider-compatibility/reports/step15-residual-risk-final-readiness-20260705.md`, `PRIVATE/provider-compatibility/raw/step15-residual-risk-final-readiness-20260705.json`, `PRIVATE/provider-compatibility/runs/step15-residual-risk-final-readiness-20260705/summary.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Reused the current-source provider evidence from Steps 4, 5, 7, 8, 9, 10, 11, 12, 13, and 14; verified the final report, raw summary, and run summary were present and internally consistent; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_provider_catalog_contract tests.test_model_catalog_contract tests.test_provider_model_compatibility_matrix tests.test_reasoning_policy_normalization tests.test_tool_call_compatibility tests.test_router_transport_registry tests.test_context_gate_compatibility tests.test_provider_handoff_compatibility tests.test_speech_synthesize_adapter tests.test_capability_smoke tests.test_capability_artifacts tests.test_capability_runtime` with 52 passing tests; ran `C:\Users\cyz19\AppData\Local\hermes\node\npm.cmd test -- src/features/runtime/reasoningOptions.test.ts src/features/runtime/modelAuthorityNotice.test.ts src/features/capabilities/CapabilityRoutesPanel.test.tsx src/features/runtime/InspectorPanels.test.tsx` with 46 passing tests; ran `C:\Users\cyz19\AppData\Local\hermes\node\npm.cmd run build` successfully; ran `git diff --check` over the touched Step 15 docs and artifacts with no content-format failures; and ran a focused secret scan over the final touched files with no concrete secret-value matches.
- Blockers: None. The remaining issues are explicitly carried forward as warning-gated provider limitations rather than unresolved execution blockers for this plan.
- Next step: None. Plan complete.

### 2026-07-05 - Step 14

- Completed: Closed the in-app browser screenshot reliability step by separating browser discovery from screenshot capture. The bundled in-app browser plugin path now has fresh evidence that `browser.tabs.list()` and `browser.tabs.selected()` work locally against the live AstraBridge tab, so the earlier reliability concern is no longer treated as a tab-discovery failure. The remaining instability is narrower: native in-app capture through `tab.screenshot(...)` timed out on the current local app state with `Timed out running CDP command "Page.captureScreenshot" for tab 1`. Instead of overclaiming that this path is fully fixed, this round recorded the timeout as the current screenshot-layer failure mode and preserved a working fallback path using `scripts/capture_astrabridge_page.mjs` on the same local URL. That fallback produced a fresh full-page screenshot plus capture JSON under `PRIVATE/provider-compatibility/screenshots/`, and the provider compatibility runbook now documents when to stay on the in-app browser path versus when to switch to the Playwright page-capture fallback.
- Files changed: `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`, `PRIVATE/provider-compatibility/reports/step14-in-app-browser-screenshot-reliability-20260705.md`, `PRIVATE/provider-compatibility/raw/step14-in-app-browser-screenshot-reliability-20260705.json`, `PRIVATE/provider-compatibility/runs/step14-in-app-browser-reliability-20260705/summary.json`, `PRIVATE/provider-compatibility/screenshots/step14-in-app-browser-reliability-20260705/playwright-fallback-current-tab.png`, `PRIVATE/provider-compatibility/screenshots/step14-in-app-browser-reliability-20260705/playwright-fallback-current-tab.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Read and followed the bundled in-app browser control skill, connected to the `iab` browser through the required bootstrap path, confirmed `browser.tabs.list()` and `browser.tabs.selected()` returned the live AstraBridge tab, attempted native `tab.screenshot(...)` and captured the current timeout error as durable evidence, then ran `node D:\AstraBridge\scripts\capture_astrabridge_page.mjs --url http://127.0.0.1:4181/?astrabridge_launch=dogfood&sidecar=http%3A%2F%2F127.0.0.1%3A8791 --out D:\AstraBridge\PRIVATE\provider-compatibility\screenshots\step14-in-app-browser-reliability-20260705\playwright-fallback-current-tab.png --report D:\AstraBridge\PRIVATE\provider-compatibility\screenshots\step14-in-app-browser-reliability-20260705\playwright-fallback-current-tab.json --wait-ms 1500 --expect-text AstraBridge`; visually checked the resulting screenshot; ran `git diff --check` over the Step 14 docs and artifacts with no content-format failures; and ran a focused secret scan over the touched Step 14 files, confirming no concrete secret-value matches beyond policy text that mentions bearer tokens generically.
- Blockers: None for closing Step 14. The remaining limitation is explicitly recorded as a screenshot capture timeout on the native in-app tab path, with a working Playwright page-capture fallback available for the final gate and future UI verification rounds.
- Next step: Step 15, Residual Risk Final Gate.

### 2026-07-05 - Step 13

- Completed: Captured fresh provider-backed compact/long-context evidence on the current-source sidecar `127.0.0.1:8792` using the managed `astra` vault session and a new dedicated runner that combines Step 12 dry-run context-limit classification with live `thread.compact` and `health_check` behavior. The final Step 13 report now covers four managed providers on the same active task path. The observed state is intentionally mixed rather than overclaimed: `glm` is `partial` because manual compact completed and the health-check handoff completed, but the earlier marker was still lost across the fresh thread; `qwen` is `partial` because compact started but the compaction turn ended in a failed/system-error shape before any visible completion event, and the follow-on health check still lost the marker; `deepseek` is `partial` because compact started and the health-check handoff completed, but no compact completion event appeared during the probe window and marker continuity still failed; `yunwu` is `fail` because compact returned a recoverable `thread_missing` / `restart_runtime_lane` outcome on the current lane and did not reach a usable health-check continuation. This closes Step 13 because the plan now has provider-backed evidence for at least three managed providers, explicit pass/partial/fail compact-quality plus context-limit-handling records per provider, and a focused secret-clean durable artifact set.
- Files changed: `PRIVATE/provider-compatibility/step13_provider_backed_compact_validation_runner.py`, `PRIVATE/provider-compatibility/reports/step13-provider-backed-compact-validation-20260705.md`, `PRIVATE/provider-compatibility/raw/step13-provider-backed-compact-validation-20260705.json`, `PRIVATE/provider-compatibility/runs/step13-provider-backed-compact-validation-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step13-provider-backed-compact-validation-20260705/cases/glm-glm-5.2-provider-backed-compact.json`, `PRIVATE/provider-compatibility/runs/step13-provider-backed-compact-validation-20260705/cases/qwen-qwen3.7-plus-provider-backed-compact.json`, `PRIVATE/provider-compatibility/runs/step13-provider-backed-compact-validation-20260705/cases/deepseek-deepseek-v4-pro-provider-backed-compact.json`, `PRIVATE/provider-compatibility/runs/step13-provider-backed-compact-validation-20260705/cases/yunwu-gpt-5.5-provider-backed-compact.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step13_provider_backed_compact_validation_runner.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step13_provider_backed_compact_validation_runner.py` repeatedly while hardening the live runtime-path assumptions until the runner used same-task `no_context` handoff instead of empty-task thread creation; verified the final summary/report record `glm=partial`, `qwen=partial`, `deepseek=partial`, and `yunwu=fail`; ran `git diff --check` over the Step 13 runner and durable artifacts with no content-format failures; and ran a focused secret scan over the Step 13 runner/report/raw/summary/case artifacts with no concrete secret-value matches.
- Blockers: None for closing Step 13. The residual compact lane is no longer metadata-only, but the evidence remains warning-gated: marker continuity after compaction is not yet verified on any managed lane, and Yunwu still needs lane-recovery handling before compact can be considered reliable there.
- Next step: Step 14, In-App Browser Screenshot Reliability.

### 2026-07-05 - Plan Scope Refresh

- Completed: Refreshed the durable multi-round plan after the latest scope clarification. The active queue now starts at Step 13 instead of the stale Step 9 reference, and the remaining-round summary now covers only Step 13 through Step 15. Official OpenAI direct provider validation remains explicitly deferred by user direction because there is no current official API key, so it is kept out of the execution queue rather than being left as an ambiguous pending item.
- Files changed: `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Re-read the current progress section, remaining-round slice, and progress log for consistency; confirmed the preserved completed history for Steps 0-12 remains intact; and confirmed the active entry point, remaining goals, and acceptance summary now match the actual unresolved work.
- Blockers: None. This was a plan-only update.
- Next step: Step 13, Provider-Backed Compact And Long-Context Validation.

### 2026-07-05 - Step 0

- Completed: Created the durable residual-risk execution plan, excluding official OpenAI direct validation per user direction.
- Files changed: `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Checked existing completed compatibility plan and Step 15 residual-risk report, then mapped all non-OpenAI residual risks into one-step-per-round execution steps with acceptance criteria.
- Blockers: None.
- Next step: Step 1, Residual Evidence Baseline And Reproduction Map.

### 2026-07-05 - Step 1

- Completed: Produced a fresh secret-free residual baseline and reproduction map for Kimi code-agent/schema and handoff reliability, Qwen TTS, Yunwu image artifact persistence, GLM command execution, compact/long-context validation, and in-app browser screenshot reliability. The report maps each risk to preserved evidence, source-owner modules, tests, API/smoke lanes, expected artifacts, and UI surfaces, and explicitly defers official OpenAI direct evidence from this plan.
- Files changed: `PRIVATE/provider-compatibility/reports/step1-residual-evidence-baseline-20260705.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Re-read the Step 10, Step 11, Step 12, and Step 15 preserved reports plus the Step 13 screenshot directory and relevant current source/test owners; ran `git diff --check -- PRIVATE/provider-compatibility/reports/step1-residual-evidence-baseline-20260705.md PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`; and ran a focused PCRE2 secret scan over the new baseline report with no matches.
- Blockers: None. The baseline is clear enough to start the Kimi tool-schema contract test directly next round.
- Next step: Step 2, Kimi Tool Schema Reproduction And Contract Test.

### 2026-07-05 - Step 2

- Completed: Added deterministic local Kimi/Moonshot schema contract coverage without making provider calls. The new regression coverage now includes one exact Moonshot-style failure fixture where `required=["command"]` but `properties` omits `command`, plus one native-kernel `run_command` schema assertion that documents the Kimi-compatible target shape shared Step 3 must preserve: `type=object`, `required=["command"]`, and `properties` containing `command`, `cwd`, and `timeout_seconds`.
- Files changed: `apps/astrabridge-sidecar/tests/test_tool_call_compatibility.py`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_tool_call_compatibility`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile tests\test_tool_call_compatibility.py`; and ran `git diff --check -- apps/astrabridge-sidecar/tests/test_tool_call_compatibility.py`.
- Blockers: None. The next round can implement provider-specific schema normalization against a now-fixed local contract target.
- Next step: Step 3, Kimi Shell Tool Schema Normalization.

### 2026-07-05 - Step 3

- Completed: Normalized the shared tool-schema sanitizer so it preserves named entries under JSON Schema `properties` instead of stripping them as unsupported keys, and made it accept both flat tool definitions and the nested OpenAI-style `function.parameters` shape already emitted by the native kernel. This closes the concrete Kimi/Moonshot failure mode that produced `required=['command']` while deleting `properties.command`, without weakening existing transport or authority behavior for the other providers.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/tool_schema_policy.py`, `apps/astrabridge-sidecar/tests/test_tool_call_compatibility.py`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_tool_call_compatibility tests.test_router_transport_registry tests.test_provider_catalog_contract tests.test_model_catalog_contract`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\providers\tooling\tool_schema_policy.py tests\test_tool_call_compatibility.py`; ran `git diff --check -- apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/tool_schema_policy.py apps/astrabridge-sidecar/tests/test_tool_call_compatibility.py`; and ran a focused PCRE2 secret scan over the changed files with no matches. `git diff --check` emitted only a line-ending warning for the modified Python file and no content-format failures.
- Blockers: None. The next round can now rerun Kimi with provider-backed evidence instead of guessing at the schema shape.
- Next step: Step 4, Kimi Provider-Backed Code-Agent Validation.

### 2026-07-05 - Step 4

- Completed: Ran fresh provider-backed Kimi validation after the schema normalization. Kimi text validation passed through the managed vault path, but the code-agent shell smoke still did not produce usable tool execution evidence. The new Step 4 evidence explicitly tiers Kimi down for code-agent autonomy while keeping the text lane available: the runtime turn was accepted over HTTP, but it came back with `turn.status=inProgress`, `items=[]`, and `commandExecution count=0` after the handoff into the active provider thread.
- Files changed: `PRIVATE/provider-compatibility/step4_kimi_code_agent_validation_runner.py`, `PRIVATE/provider-compatibility/reports/step4-kimi-code-agent-validation-20260705.md`, `PRIVATE/provider-compatibility/raw/step4-kimi-code-agent-validation-20260705.json`, `PRIVATE/provider-compatibility/runs/step4-kimi-code-agent-validation-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step4-kimi-code-agent-validation-20260705/cases/kimi-text.json`, `PRIVATE/provider-compatibility/runs/step4-kimi-code-agent-validation-20260705/cases/kimi-code-agent.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step4_kimi_code_agent_validation_runner.py` multiple times to regenerate sanitized evidence after improving the runner; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step4_kimi_code_agent_validation_runner.py`; ran `git diff --check -- D:\AstraBridge\PRIVATE\provider-compatibility\step4_kimi_code_agent_validation_runner.py D:\AstraBridge\PRIVATE\provider-compatibility\reports\step4-kimi-code-agent-validation-20260705.md D:\AstraBridge\PRIVATE\provider-compatibility\runs\step4-kimi-code-agent-validation-20260705\summary.json D:\AstraBridge\PRIVATE\provider-compatibility\runs\step4-kimi-code-agent-validation-20260705\cases\kimi-code-agent.json D:\AstraBridge\PRIVATE\provider-compatibility\raw\step4-kimi-code-agent-validation-20260705.json`; and ran a focused secret scan over the runner and all new Step 4 artifacts with no matches.
- Blockers: None for closing Step 4. Kimi remains a partial provider lane: text is provider-backed pass, but shell/code-agent autonomy is explicitly reduced-authority until later evidence shows real command execution.
- Next step: Step 5, Kimi Same-Task Handoff Revalidation.

### 2026-07-05 - Step 5

- Completed: Revalidated same-task `Qwen -> Kimi` handoff after the Step 4 tier-down decision using a fresh text-safe JSON continuity prompt. The result is `partial`, not `pass`: the handoff infrastructure itself works and remains visible in task state, but Kimi still does not produce a successful target reply even on this reduced-authority prompt class. The target Kimi thread moved onto the same task with a recorded `provider_handoff`, preserved the Qwen source lane, used `task_context_fresh_thread`, and explicitly set `drop_reasoning_replay=true`; however, the target Kimi thread still ended as `systemError` with no final continuity JSON payload.
- Files changed: `PRIVATE/provider-compatibility/step5_kimi_same_task_handoff_validation_runner.py`, `PRIVATE/provider-compatibility/reports/step5-kimi-same-task-handoff-revalidation-20260705.md`, `PRIVATE/provider-compatibility/raw/step5-kimi-same-task-handoff-revalidation-20260705.json`, `PRIVATE/provider-compatibility/runs/step5-kimi-same-task-handoff-revalidation-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step5-kimi-same-task-handoff-revalidation-20260705/cases/qwen-to-kimi-text-safe.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step5_kimi_same_task_handoff_validation_runner.py` repeatedly to tighten the evidence classification and remove a false-positive private-state detection; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step5_kimi_same_task_handoff_validation_runner.py`; ran `git diff --check -- D:\AstraBridge\PRIVATE\provider-compatibility\step5_kimi_same_task_handoff_validation_runner.py D:\AstraBridge\PRIVATE\provider-compatibility\reports\step5-kimi-same-task-handoff-revalidation-20260705.md D:\AstraBridge\PRIVATE\provider-compatibility\runs\step5-kimi-same-task-handoff-revalidation-20260705\summary.json D:\AstraBridge\PRIVATE\provider-compatibility\runs\step5-kimi-same-task-handoff-revalidation-20260705\cases\qwen-to-kimi-text-safe.json D:\AstraBridge\PRIVATE\provider-compatibility\raw\step5-kimi-same-task-handoff-revalidation-20260705.json`; and ran a focused secret scan over the runner and all new Step 5 artifacts with no matches.
- Blockers: None for closing Step 5. The controlled-switching boundary is now clearer: Kimi can remain visible as a same-task target only behind explicit warning-gated, text-safe fallback guidance, because even text-safe handoff does not yet produce a reliable target completion.
- Next step: Step 6, Qwen TTS Request Contract Repair.

### 2026-07-05 - Step 6

- Completed: Repaired the Qwen `speech.synthesize` request contract so it no longer uses the generic compatible-mode `chat/completions` shape that produced the Step 12 DashScope 400. The adapter now targets DashScope's multimodal-generation TTS API, sends the request as `model + input{text, voice, format, language_type?, instructions?}`, enables SSE through `X-DashScope-SSE: enable`, and parses audio from `output.audio.data` while remaining backward-compatible with any older `delta.audio.data` chunks. Capability metadata and route resolution were also updated so the TTS lane now resolves to `qwen.tts.api.v1` with `qwen3-tts-flash` / `qwen3-tts-instruct-flash` instead of the old omni chat route.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py`, `apps/astrabridge-sidecar/tests/test_speech_synthesize_adapter.py`, `apps/astrabridge-sidecar/tests/test_capability_specs.py`, `apps/astrabridge-sidecar/tests/test_capability_artifacts.py`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Re-read the preserved Step 12 provider-backed failure evidence and the current runtime/capability sources; confirmed the runtime now resolves `speech.synthesize` to adapter `qwen.tts.api.v1` with model `qwen3-tts-flash`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_speech_synthesize_adapter tests.test_capability_specs tests.test_capability_artifacts tests.test_capability_routes tests.test_capability_smoke`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\capabilities\speech_synthesize_adapter.py D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\capabilities\specs.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_speech_synthesize_adapter.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_capability_specs.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_capability_artifacts.py`; ran `git diff --check -- D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\capabilities\speech_synthesize_adapter.py D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\capabilities\specs.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_speech_synthesize_adapter.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_capability_specs.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_capability_artifacts.py`; and ran a focused secret scan over the changed files with no concrete secret-value matches. `git diff --check` emitted only line-ending warnings and no content-format failures.
- Blockers: None for closing Step 6. Provider-backed TTS still needs to be rerun in Step 7 to prove the new contract against the live Qwen route.
- Next step: Step 7, Qwen TTS Provider-Backed Smoke.

### 2026-07-05 - Step 7

- Completed: Revalidated Qwen `speech.synthesize` through the managed `astra` vault path and preserved fresh provider-backed evidence under `PRIVATE/provider-compatibility/`. Step 7 closes as `completed`, but the evidence classification is `partial`, not `clean pass`: the request contract and route are now corrected enough for `/api/runtime/capability-smoke` to hit `qwen.tts.api.v1` successfully, persist request/transcript/audio/summary artifacts, and return endpoint status `pass`; however, the persisted audio file is still not a valid RIFF/WAV container even though it is non-empty. During this round the TTS adapter was advanced in three concrete ways: it now normalizes DashScope TTS onto `.../api/v1` instead of the incompatible `compatible-mode/v1` path, it falls back to downloading `output.audio.url` when inline audio data is absent, and it treats `output.audio.data` as the latest complete snapshot rather than concatenating every snapshot into one corrupt file. The smoke fixture was also corrected to use `Cherry` and to forward `workspace_root` so provider-backed smoke preserves artifacts in a reproducible workspace.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py`, `apps/astrabridge-sidecar/tests/test_speech_synthesize_adapter.py`, `apps/astrabridge-sidecar/tests/test_capability_smoke.py`, `PRIVATE/provider-compatibility/step7_qwen_tts_provider_smoke_runner.py`, `PRIVATE/provider-compatibility/reports/step7-qwen-tts-provider-smoke-20260705.md`, `PRIVATE/provider-compatibility/raw/step7-qwen-tts-provider-smoke-20260705.json`, `PRIVATE/provider-compatibility/runs/step7-qwen-tts-provider-smoke-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step7-qwen-tts-provider-smoke-20260705/cases/qwen-tts-provider-smoke.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_speech_synthesize_adapter tests.test_capability_smoke tests.test_capability_specs tests.test_capability_artifacts`; ran temp-target `py_compile` over the modified adapter, smoke helper, tests, and Step 7 runner; repeatedly restarted the current-source sidecar on `127.0.0.1:8790`; re-authenticated the managed `astra` vault session through `/api/llm-manager/login` with `use_desktop_key_file=true`; reran `/api/runtime/capability-smoke` with `workspace_root` so artifacts landed under `PRIVATE/provider-compatibility/runs/step7-qwen-tts-provider-smoke-20260705/workspace/.astrabridge/capabilities/speech_synthesize/...`; verified the final route resolves to `qwen.tts.api.v1` / `qwen3-tts-flash`; inspected the persisted audio artifact and confirmed it is non-empty but fails RIFF/WAV validation; ran `git diff --check` on the touched Step 7 files (line-ending warnings only); and ran a focused secret scan over the new Step 7 evidence/report/raw/case files with no secret-value matches in the durable artifacts.
- Blockers: None for closing Step 7. Remaining residual warning: Qwen TTS now has provider-backed route/artifact evidence, but the current persisted audio bytes are still container-invalid for the requested `wav` format, so downstream readiness should continue to treat Qwen TTS as warning-gated until audio-container normalization is repaired.
- Next step: Step 8, Yunwu Image Artifact Persistence Repair.

### 2026-07-05 - Step 8

- Completed: Closed the Step 12 Yunwu image persistence gap by adding a runtime-level workspace-root fallback and a server-side default-workspace injection path so `image.generate` no longer depends on an explicit `workspace_root` in the smoke payload to persist artifacts. The focused regression coverage now proves `_workspace_root()` falls back to the current working directory when no `ASTRABRIDGE_WORKSPACE_ROOT*` environment variables are present, and the handler helper still prefers the current project workspace before seed-root fallback. Fresh provider-backed evidence was then captured on a dedicated current-source sidecar at `127.0.0.1:8791`: the same `/api/runtime/capability-smoke` shape used by Step 12, but without `workspace_root`, now auto-injects `D:\AstraBridge\PRIVATE\demo-runs\provider-switch-live-20260622-224524\workspace`, persists a local PNG under `.astrabridge/assets/generated/`, and records the generated `asset_manifest.json`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_capability_runtime.py`, `apps/astrabridge-sidecar/tests/test_sidecar_services.py`, `PRIVATE/provider-compatibility/reports/step8-yunwu-image-persistence-repair-20260705.md`, `PRIVATE/provider-compatibility/raw/step8-yunwu-image-persistence-repair-20260705.json`, `PRIVATE/provider-compatibility/runs/step8-yunwu-image-persistence-repair-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step8-yunwu-image-persistence-repair-20260705/cases/yunwu-image-persistence-smoke.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest apps.astrabridge-sidecar.tests.test_capability_runtime apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_handler_capability_payload_defaults_workspace_root_from_current_project apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_handler_capability_payload_defaults_workspace_root_from_seed_root apps.astrabridge-sidecar.tests.test_capability_smoke apps.astrabridge-sidecar.tests.test_capability_artifacts apps.astrabridge-sidecar.tests.test_image_generate_adapter`; ran temp-target `py_compile` over the modified runtime/server/tests; launched a dedicated current-source sidecar on `127.0.0.1:8791`; re-authenticated the managed `astra` vault session through `/api/llm-manager/login` with `use_desktop_key_file=true`; reran `/api/runtime/capability-smoke` for `image.generate` without `workspace_root`; verified `status=pass`, auto-injected workspace root, persisted PNG path, and generated manifest existence; ran `git diff --check` on the touched Step 8 files (line-ending warnings only); and ran a focused secret scan over the new Step 8 evidence/report/raw/case files with no secret-value matches in the durable artifacts.
- Blockers: None for closing Step 8. The residual image lane now moves to Step 9, which should confirm the same persisted artifact path is visible through the desktop/UI preview surfaces rather than only through smoke output.
- Next step: Step 9, Yunwu Image Provider-Backed Smoke And UI Preview.

### 2026-07-05 - Step 9

- Completed: Revalidated Yunwu `image.generate` end to end on the dedicated current-source sidecar `127.0.0.1:8791` and confirmed the persisted image is visible through the desktop capability UI. A fresh provider-backed smoke run passed again without an explicit `workspace_root`, auto-injected the demo-run workspace, and persisted a new PNG artifact plus manifest entry. The capability artifact snapshot now surfaces that newest asset as `preview.kind=image`, and the in-app browser `多模态能力路由` page renders the latest Step 9 artifact through `/api/project/files/media` with a loaded preview image (`naturalWidth=1024`, `naturalHeight=1024`). Screenshot evidence was preserved under `PRIVATE/provider-compatibility/screenshots/step9-yunwu-image-ui-preview-20260705.png`.
- Files changed: `PRIVATE/provider-compatibility/screenshots/step9-yunwu-image-ui-preview-20260705.png`, `PRIVATE/provider-compatibility/reports/step9-yunwu-image-provider-ui-preview-20260705.md`, `PRIVATE/provider-compatibility/raw/step9-yunwu-image-provider-ui-preview-20260705.json`, `PRIVATE/provider-compatibility/runs/step9-yunwu-image-provider-ui-preview-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step9-yunwu-image-provider-ui-preview-20260705/cases/yunwu-image-provider-ui-preview.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Read and followed the in-app browser control skill, connected to the in-app browser, opened the local app against sidecar `8791`, navigated to `工具 -> 多模态能力路由`, and captured UI state through live screenshots plus bounded read-only DOM inspection. Ran fresh `/api/runtime/capability-smoke` and `/api/runtime/capability-artifacts` requests against `127.0.0.1:8791`; verified `status=pass`, verified the latest `image.generate` artifact path exists on disk, verified the generated `asset_manifest.json` path exists, verified the artifact API returns the latest asset id and media preview path, ran `git diff --check` on the touched tracked files (line-ending warnings only), and ran a focused secret scan over the new Step 9 evidence/report/raw/case files with no secret-value matches.
- Blockers: None for closing Step 9. The Yunwu image lane is now backed by both provider smoke and UI preview evidence.
- Next step: Step 10, GLM Tool-Call And Command Event Instrumentation.

### 2026-07-05 - Step 10

- Completed: Hardened the GLM code-agent lane contract without overclaiming provider success. This round added explicit metadata for the known GLM partial state: provider profiles, model defaults, authority assessment, model catalog entries, and router capability records can now carry `command_execution_status=partial_no_command_execution` plus a note that the provider-backed turn reached `completed` without observable `commandExecution`. The authority layer now turns that metadata into a runtime/user warning so AstraBridge no longer conflates “turn completed” with “command executed”. On the parser side, GLM chat transport now has explicit regression coverage for both the no-tool/reasoning-only final-answer path and the positive tool-call response shape, which closes the Step 10 instrumentation gap before Step 11 revalidation.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/providers/profile.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/registry.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/model_authority.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`, `apps/astrabridge-sidecar/tests/test_tool_call_compatibility.py`, `apps/astrabridge-sidecar/tests/test_sidecar_services.py`, `apps/astrabridge-desktop/src/types.ts`, `PRIVATE/provider-compatibility/reports/step10-glm-tool-call-instrumentation-20260705.md`, `PRIVATE/provider-compatibility/raw/step10-glm-tool-call-instrumentation-20260705.json`, `PRIVATE/provider-compatibility/runs/step10-glm-tool-call-instrumentation-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step10-glm-tool-call-instrumentation-20260705/cases/glm-tool-call-instrumentation.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest apps.astrabridge-sidecar.tests.test_tool_call_compatibility apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_glm_chat_transport_normalizes_reasoning_notice_without_raw_payload_leak apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_glm_chat_transport_normalizes_tool_calls_without_raw_payload_leak apps.astrabridge-sidecar.tests.test_sidecar_services.AstraBridgeServiceTests.test_provider_profiles_seed_catalog_provider_and_model_defaults`; ran temp-target `py_compile` over the modified provider/tooling/catalog/tests files; probed `model_catalog_entry(glm/glm-5.2)` from current source and confirmed `command_execution_status=partial_no_command_execution`, the explanatory note, and distinguishing ui warnings; ran `git diff --check` on the touched tracked files (line-ending warnings only); and ran a focused secret scan over the new Step 10 evidence/report/raw/case files with no secret-value matches.
- Blockers: None for closing Step 10. GLM remains intentionally partial until Step 11 proves a real provider-backed `commandExecution` event or records an explicit reduced-authority result.
- Next step: Step 11, GLM Provider-Backed Code-Agent Revalidation.

### 2026-07-05 - Step 11

- Completed: Revalidated GLM against a fresh current-source sidecar on `127.0.0.1:8792` and closed the step as an explicit reduced-authority outcome, not a full pass. The live text check still passes on `glm-5.2`, but the provider-backed code-agent smoke again failed to produce any observable `commandExecution` item. This run is stronger than the older Step 10 evidence: the session log did show one provider `function_call`, the final assistant text still returned the requested JSON, and the effective catalog now surfaces `command_execution_status=partial_no_command_execution` plus the new warning note even when the persisted router model record was stale. That closes the ambiguity around GLM's current state: it can reach a completed-looking code-agent turn shape without executing the shell command, so AstraBridge should keep GLM warning-gated for code-agent autonomy and direct users to Qwen, DeepSeek, or Yunwu for real shell/patch execution.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`, `apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`, `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`, `PRIVATE/provider-compatibility/step11_glm_code_agent_revalidation_runner.py`, `PRIVATE/provider-compatibility/reports/step11-glm-code-agent-revalidation-20260705.md`, `PRIVATE/provider-compatibility/raw/step11-glm-code-agent-revalidation-20260705.json`, `PRIVATE/provider-compatibility/runs/step11-glm-code-agent-revalidation-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step11-glm-code-agent-revalidation-20260705/cases/glm-text.json`, `PRIVATE/provider-compatibility/runs/step11-glm-code-agent-revalidation-20260705/cases/glm-code-agent.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_provider_catalog_contract tests.test_tool_call_compatibility`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\router_config_service.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_provider_catalog_contract.py D:\AstraBridge\PRIVATE\provider-compatibility\step11_glm_code_agent_revalidation_runner.py`; launched a fresh current-source sidecar on `127.0.0.1:8792`; verified `/api/router/models/effective-catalog?model_id=glm/glm-5.2` now exposes `command_execution_status=partial_no_command_execution`, the explanatory note, and the new runtime warnings; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step11_glm_code_agent_revalidation_runner.py` twice to tighten the evidence summary; ran `git diff --check` on the touched Step 11 tracked files (line-ending warning only); and ran a focused secret scan over the new Step 11 runner and evidence artifacts with no secret-value matches.
- Blockers: None for closing Step 11. GLM remains intentionally reduced-authority for code-agent work until a future provider-backed smoke records a real `commandExecution` item.
- Next step: Step 12, Compact And Long-Context Validation Harness.

### 2026-07-05 - Step 12

- Completed: Built a reusable dry-run compact/long-context harness instead of another one-off report. The new harness generates synthetic secret-free long-context sections, computes budget reports through the existing `build_context_budget` path, records context-limit classification through the shared runtime-failure classifier, and captures the post-compaction continuation recommendation as a structured `health_check` state. A dedicated runner then produced matrix-ready dry-run evidence for the four managed priority lanes used in the next step: Qwen, DeepSeek, Yunwu, and GLM. The durable artifacts preserve only counts, dropped section ids, compact thresholds, continuation recommendations, and matrix-update payloads; no oversized raw synthetic prompt text is written to disk.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/compact_validation_harness.py`, `apps/astrabridge-sidecar/tests/test_context_gate_compatibility.py`, `PRIVATE/provider-compatibility/step12_compact_long_context_harness_runner.py`, `PRIVATE/provider-compatibility/reports/step12-compact-long-context-harness-20260705.md`, `PRIVATE/provider-compatibility/raw/step12-compact-long-context-harness-20260705.json`, `PRIVATE/provider-compatibility/runs/step12-compact-long-context-harness-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step12-compact-long-context-harness-20260705/cases/deepseek-deepseek-v4-pro-compact-harness.json`, `PRIVATE/provider-compatibility/runs/step12-compact-long-context-harness-20260705/cases/glm-glm-5.2-compact-harness.json`, `PRIVATE/provider-compatibility/runs/step12-compact-long-context-harness-20260705/cases/qwen-qwen3.7-plus-compact-harness.json`, `PRIVATE/provider-compatibility/runs/step12-compact-long-context-harness-20260705/cases/yunwu-gpt-5.5-compact-harness.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_RESIDUAL_RISK_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_context_gate_compatibility`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\compact_validation_harness.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_context_gate_compatibility.py D:\AstraBridge\PRIVATE\provider-compatibility\step12_compact_long_context_harness_runner.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step12_compact_long_context_harness_runner.py`; verified the runner report shows `compact_recommended=true`, `recommended_action=compact_thread`, and `post-compact recommended_action=health_check` for Qwen, DeepSeek, Yunwu, and GLM; verified the summary includes `matrix_updates` for all four lanes with `validation_scope=["thread.compact"]`; ran `git diff --check` on the touched Step 12 tracked files with no content-format failures; and ran a focused secret scan over the new Step 12 runner and durable artifacts, also checking that raw synthetic section text such as `src/module_000` does not appear in persisted output.
- Blockers: None for closing Step 12. The next step can now reuse this harness structure to run real provider-backed compact/long-context validation without redefining the dry-run case format.
- Next step: Step 13, Provider-Backed Compact And Long-Context Validation.
