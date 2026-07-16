# Provider Model Capability Exhaustive Smoke Execution Plan

## Total Objective

Exhaustively smoke the currently managed AstraBridge provider/model/capability surface, excluding official OpenAI direct live verification, so the project no longer relies only on representative live samples. The target end state is a durable, secret-free evidence set that covers every currently cataloged managed provider/model lane that AstraBridge claims is routable or capability-eligible, plus explicit reduced-authority or unsupported classifications wherever live execution cannot pass.

## Deliverables

- A catalog-driven exhaustive smoke scope manifest that lists every in-scope provider/model/capability lane and the reason each lane is `run`, `skip`, `unsupported`, or `reduced-authority`.
- Reusable exhaustive smoke synthesis and batch-execution helpers under the existing sidecar/provider-compatibility surfaces.
- Preserved managed-vault live smoke artifacts, summaries, and failure classifications under `PRIVATE/provider-compatibility/`.
- Updated compatibility matrix, runbook notes, and final report that separate provider-backed pass, partial, fail, unsupported, and reduced-authority outcomes.

## Out Of Scope

- Official OpenAI direct provider-backed verification with an official OpenAI API key.
- Reintroducing official OpenAI account login as a product path.
- Exhaustively testing every reasoning-effort level for every model. Reasoning policy remains docs-backed unless a specific lane is already naturally exercised by the exhaustive smoke payload.
- Cleaning `PRIVATE/**`, caches, logs, screenshots, or preserved raw artifacts unless the user explicitly names cleanup targets.

## Constraints And Attention Notes

1. Preserve all smoke artifacts, sanitized request/response metadata, manifests, matrix outputs, screenshots, and reports by default.
2. Never persist API keys, vault passwords, cookies, admin session tokens, authorization headers, desktop plaintext key contents, or provider raw secrets.
3. Use only app/sidecar-managed vault surfaces for live provider calls. Do not read plaintext key files for this plan.
4. Treat "exhaustive" as exhaustive over the current AstraBridge-managed provider/model/capability contract on disk, not over undocumented upstream features that AstraBridge does not yet route.
5. Every lane must end in one of: `pass`, `partial`, `fail`, `unsupported`, `reduced-authority`, or `skipped-with-reason`. Do not leave ambiguous unclassified rows.
6. Do not promote a lane to verified from metadata-only reasoning, dry-run evidence, or UI appearance alone. Provider-backed evidence or an explicit downgrade decision is required.
7. Reuse existing profile, catalog, capability runtime, provider-compatibility smoke, dry-run matrix, and authority surfaces instead of creating a parallel verification system.
8. Keep official OpenAI direct verification explicitly deferred unless the user later reopens that scope with a key.

## Adjustment Policy

Agents may reasonably adjust filenames, exact commands, per-batch ordering, model grouping, or report paths when the facts on disk require it. Those adjustments must not change the total objective, weaken the evidence bar, remove provider-backed validation gates, or replace exhaustive smoke work with representative sampling. If a lane proves impossible to run because the product contract is incomplete or the provider behavior is incompatible, record the blocker, preserve sanitized evidence, and convert the lane to an explicit `unsupported` or `reduced-authority` outcome instead of silently dropping it.

## Execution Rules

1. Each user-facing execution round should complete exactly one numbered step from this plan unless the user explicitly redirects otherwise.
2. Start from the earliest numbered step whose status is not `completed`.
3. Update this plan before ending the round.
4. Mark a step `completed` only when all acceptance criteria for that step are satisfied.
5. If blocked, mark the step `blocked`, record the exact blocker and next entry point, and do not leave vague continuation notes.
6. Each round must end with a concise handoff: completed work, files changed, validation run, blockers, and the exact next step.

## Current Progress

- Current status: Completed
- Completed steps: 0. Create Durable Plan; 1. Exhaustive Scope Inventory And Lane Manifest; 2. Exhaustive Smoke Contract And Case Schema; 3. Catalog-Driven Exhaustive Case Synthesis; 4. General Model Lane Synthesis For Text, Tools, And Edit Authority; 5. Exhaustive Runner Preflight, Batching, And Resume Support; 6. Execute Exhaustive Batch A: General Text, Tool, And Code-Agent Lanes; 7. Execute Exhaustive Batch B: Vision Analyze Lanes; 8. Execute Exhaustive Batch C: Speech Transcribe Lanes; 9. Execute Exhaustive Batch D: Speech Synthesize Lanes; 10. Execute Exhaustive Batch E: Image Generate Lanes; 11. Execute Exhaustive Batch F: Compact, Health-Check, And Same-Task Continuation Lanes; 12. Compatibility Matrix Consolidation And Final Readiness Report
- Current step: None. This execution plan is complete.
- Next step: Future maintenance should start from `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`, `PRIVATE/provider-compatibility/runs/step12-exhaustive-compatibility-matrix-20260706/summary.json`, and `python scripts\run_provider_capability_verification_gate.py --run-id provider-capability-gate-YYYYMMDD`.
- Scope note: Official OpenAI direct provider-backed verification remains out of scope by explicit user direction.
- Last updated: 2026-07-06

## Execution Steps

### 0. Create Durable Plan

Goal: Create this execution plan and make the next entry point unambiguous.

Main actions:

- Define the exhaustive-smoke objective, scope boundary, and output classes.
- Record constraints, adjustment policy, execution rules, and numbered steps.
- Set current progress and the next step.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes objective, deliverables, scope boundary, constraints, adjustment policy, execution rules, numbered steps, and progress log.
- The next agent entry point is clear.

Status: completed

### 1. Exhaustive Scope Inventory And Lane Manifest

Goal: Convert the current AstraBridge contract into a concrete exhaustive smoke manifest.

Main actions:

- Read the current provider catalog, capability registry, authority metadata, route specs, and existing smoke fixtures.
- Enumerate every in-scope managed provider/model/capability lane, including text/code-agent lanes and model-backed multimodal capability lanes.
- Write a secret-free scope manifest and baseline report under `PRIVATE/provider-compatibility/`.

Acceptance criteria:

- Every currently managed provider/model lane is classified as `run`, `skip`, `unsupported`, or `reduced-authority` with a reason.
- The manifest clearly separates capability lanes (`vision.analyze`, `speech.transcribe`, `speech.synthesize`, `image.generate`) from general model/tool lanes and compact/handoff lanes.
- Focused secret scan over the new manifest/report passes.

Status: completed

### 2. Exhaustive Smoke Contract And Case Schema

Goal: Define the case schema needed to drive exhaustive smoke batches without ad hoc per-provider payloads.

Main actions:

- Extend or document the reusable case format for provider/model/capability exhaustive smoke.
- Define normalized result fields, classification rules, and per-lane artifact expectations.
- Align the schema with existing provider-compatibility and capability-smoke report surfaces.

Acceptance criteria:

- Exhaustive case schema can represent all in-scope lane families.
- Classification rules cover pass, partial, fail, unsupported, reduced-authority, and skipped cases.
- Regression coverage proves the schema is secret-free and serializable.

Status: completed

### 3. Catalog-Driven Exhaustive Case Synthesis

Goal: Automatically synthesize exhaustive smoke cases from the live catalog and capability contract.

Main actions:

- Implement a synthesis path that derives cases from current provider/model records and capability specs.
- Carry through provider/model identifiers, capability ids, route hints, and skip reasons.
- Preserve a generated manifest artifact suitable for reruns and audits.

Acceptance criteria:

- Case synthesis emits deterministic exhaustive case manifests from current workspace state.
- Generated cases preserve explicit provider/model targeting instead of falling back to defaults.
- Tests cover at least one positive, unsupported, and reduced-authority synthesis path.

Status: completed

### 4. General Model Lane Synthesis For Text, Tools, And Edit Authority

Goal: Cover non-capability model lanes that matter for same-task switching.

Main actions:

- Define exhaustive cases for text-only health, tool-calling authority, command execution, and edit-policy lanes where the product claims support.
- Use current authority metadata to separate runnable lanes from explicit reduced-authority lanes.
- Ensure Kimi, GLM, DeepSeek, Qwen, and Yunwu general model lanes are represented where applicable.

Acceptance criteria:

- Exhaustive manifest includes general model lanes alongside multimodal capability lanes.
- Reduced-authority or unsupported model lanes are recorded explicitly rather than omitted.
- Tests or fixture validation prove those general-lane cases are synthesized correctly.

Status: completed

### 5. Exhaustive Runner Preflight, Batching, And Resume Support

Goal: Make exhaustive smoke runnable in bounded batches without losing coverage or artifacts.

Main actions:

- Add preflight checks for sidecar reachability, managed-vault auth state, provider availability, and artifact root setup.
- Add batch slicing and resume markers so the exhaustive run can continue across turns without recomputing prior finished cases.
- Persist per-batch manifests and summaries under `PRIVATE/provider-compatibility/runs/`.

Acceptance criteria:

- The exhaustive runner can execute a selected batch from the generated manifest and resume later batches safely.
- Failed or skipped cases still produce durable summaries and reasons.
- Regression coverage exists for batch slicing or resume state handling.

Status: completed

### 6. Execute Exhaustive Batch A: General Text, Tool, And Code-Agent Lanes

Goal: Run all in-scope general model lanes before modality-specific capability batches.

Main actions:

- Execute text-health, tool-call, command-execution, and edit-policy smoke lanes for all managed providers/models that are marked runnable.
- Preserve sanitized request/response summaries and classify each case.
- Update reduced-authority findings where live evidence confirms the downgrade.

Acceptance criteria:

- Every runnable general lane in the manifest has a live result or explicit blocked reason.
- Provider-backed evidence exists for each executed general-lane case.
- Batch report and focused secret scan pass.

Status: completed

### 7. Execute Exhaustive Batch B: Vision Analyze Lanes

Goal: Run every in-scope `vision.analyze` provider/model lane.

Main actions:

- Execute all runnable vision cases with stable image fixtures and explicit provider/model targeting.
- Preserve capability artifacts and classify empty-answer, unsupported-media, timeout, and route-mismatch failures distinctly.
- Record which models remain text-only despite provider-level vision availability.

Acceptance criteria:

- Every in-scope vision lane is classified with provider-backed evidence or an explicit unsupported reason.
- Vision batch summaries preserve artifact references and route resolution.
- Batch report and focused secret scan pass.

Status: completed

### 8. Execute Exhaustive Batch C: Speech Transcribe Lanes

Goal: Run every in-scope `speech.transcribe` provider/model lane.

Main actions:

- Execute all runnable transcription cases with stable audio fixtures and explicit provider/model targeting.
- Preserve transcript artifacts and classify provider-format or content-shape failures.
- Record any model-level speech limitations beneath provider-level audio claims.

Acceptance criteria:

- Every in-scope speech-transcribe lane has a classified result with evidence or an explicit unsupported reason.
- Artifact persistence and transcript presence are verified for pass/partial cases.
- Batch report and focused secret scan pass.

Status: completed

### 9. Execute Exhaustive Batch D: Speech Synthesize Lanes

Goal: Run every in-scope `speech.synthesize` provider/model lane.

Main actions:

- Execute all runnable TTS cases with stable text fixtures and explicit provider/model targeting.
- Validate transcript presence, audio artifact presence, and container sanity where the product claims a concrete format.
- Preserve partial classifications when route success still yields invalid or unusable audio artifacts.

Acceptance criteria:

- Every in-scope speech-synthesize lane has a classified result with evidence or an explicit unsupported reason.
- Artifact and container checks are recorded for each executed case.
- Batch report and focused secret scan pass.

Status: completed

### 10. Execute Exhaustive Batch E: Image Generate Lanes

Goal: Run every in-scope `image.generate` provider/model lane.

Main actions:

- Execute all runnable image-generation cases with stable prompts and explicit provider/model targeting.
- Verify persisted image artifacts, asset manifests, and route resolution.
- Record route gaps or persistence failures distinctly from provider content failures.

Acceptance criteria:

- Every in-scope image-generation lane has a classified result with evidence or an explicit unsupported reason.
- Persisted artifact checks succeed for pass cases and are explicitly recorded for non-pass cases.
- Batch report and focused secret scan pass.

Status: completed

### 11. Execute Exhaustive Batch F: Compact, Health-Check, And Same-Task Continuation Lanes

Goal: Exhaust the model lanes that affect same-task switching beyond single capability calls.

Main actions:

- Run `thread.compact`, health-check continuation, and same-task continuation probes for every provider/model lane marked in scope by the manifest.
- Preserve compact status, continuation markers, and restart/fallback classifications.
- Record which providers remain warning-gated for long-task continuity even if single-turn capability calls pass.

Acceptance criteria:

- Every in-scope continuation lane has provider-backed evidence or an explicit reduced-authority/unsupported classification.
- Compact and health-check artifacts are preserved under the batch run root.
- Batch report and focused secret scan pass.

Status: completed

### 12. Compatibility Matrix Consolidation And Final Readiness Report

Goal: Convert the exhaustive smoke evidence into the maintained compatibility surfaces.

Main actions:

- Update matrix/report/runbook/status surfaces from the actual exhaustive smoke results.
- Write a final secret-free readiness report that summarizes coverage totals and residual downgraded lanes.
- Run the existing verification gate, focused tests, diff checks, and secret scans over touched files and evidence.

Acceptance criteria:

- Compatibility surfaces reflect exhaustive evidence rather than representative-only live samples.
- Final report states exact totals for pass, partial, fail, unsupported, reduced-authority, and skipped lanes.
- Validation commands and focused secret scans pass.

Status: completed

## Progress Log

### 2026-07-06 - Step 0

- Completed: Created a new execution plan dedicated to exhaustive provider/model/capability smoke coverage because all earlier provider-compatibility plans on disk were already complete and their live-smoke scope was intentionally bounded or representative rather than exhaustive.
- Files changed: `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Read the completed earlier plans to confirm they do not own the new exhaustive-smoke scope; re-read the durable handoff skill template; inspected the current capability/runtime/smoke surfaces to ensure the new plan matches the existing product contract.
- Blockers: None.
- Next step: 1. Exhaustive Scope Inventory And Lane Manifest.

### 2026-07-06 - Step 1

- Completed: Converted the current AstraBridge contract into a durable exhaustive-scope manifest and baseline report. Added a reproducible private runner that inventories provider profiles, effective catalog models, capability-registry route targets, authority metadata, and compact/handoff lanes, then classifies each lane as `run`, `skip`, `unsupported`, or `reduced-authority`. The generated scope set covers 18 catalog models, 54 general model lanes, 77 capability lanes, and 54 compact/handoff lanes. It also preserves the key current downgrade boundaries: OpenAI direct remains skipped by scope, Kimi code-agent and handoff lanes remain reduced-authority, GLM code-agent remains reduced-authority, Qwen TTS remains in-scope with prior partial evidence, and Yunwu image generation is tracked through adapter-only capability models rather than the catalog default text model.
- Files changed: `PRIVATE/provider-compatibility/step1_exhaustive_scope_inventory_runner.py`, `PRIVATE/provider-compatibility/runs/step1-exhaustive-scope-inventory-20260706/manifest.json`, `PRIVATE/provider-compatibility/runs/step1-exhaustive-scope-inventory-20260706/summary.json`, `PRIVATE/provider-compatibility/reports/step1-exhaustive-scope-inventory-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step1_exhaustive_scope_inventory_runner.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step1_exhaustive_scope_inventory_runner.py`; inspected the generated `summary.json`, `manifest.json`, and markdown report; ran `git diff --check` over the touched Step 1 files with no content-format failures; and ran a focused secret-pattern scan over the plan, runner, report, and generated manifest/summary with no matches.
- Blockers: None.
- Next step: 2. Exhaustive Smoke Contract And Case Schema.

### 2026-07-06 - Step 2

- Completed: Added a reusable exhaustive-smoke contract module that defines normalized case and result schemas, scope decisions, execution policies, runner kinds, fixture kinds, artifact expectations, lower-level status mapping, and secret-free validation. The new contract now explicitly covers all active lane families from the plan: general model lanes, multimodal capability lanes, and compact/handoff lanes. It also preserves the current downgrade semantics by mapping reduced-authority confirmation cases to `reduced-authority` unless a future rerun actually proves `pass`. A secret-free sample artifact was generated so later synthesis work can consume a concrete contract example instead of rebuilding one from chat history.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/exhaustive_smoke_contract.py`, `apps/astrabridge-sidecar/tests/test_exhaustive_smoke_contract.py`, `PRIVATE/provider-compatibility/runs/step2-exhaustive-smoke-case-schema-20260706/sample-contracts.json`, `PRIVATE/provider-compatibility/reports/step2-exhaustive-smoke-case-schema-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\exhaustive_smoke_contract.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_exhaustive_smoke_contract.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_exhaustive_smoke_contract`; generated and inspected `PRIVATE/provider-compatibility/runs/step2-exhaustive-smoke-case-schema-20260706/sample-contracts.json`; ran `git diff --check` over the touched Step 2 files with no content-format failures; and ran a focused secret-pattern scan over the contract module, test, report, sample artifact, and this plan with no matches.
- Blockers: None.
- Next step: 3. Catalog-Driven Exhaustive Case Synthesis.

### 2026-07-06 - Step 3

- Completed: Added deterministic catalog-driven exhaustive case synthesis on top of the Step 1 scope manifest and the Step 2 contract. The new synthesis module converts every manifest lane into a secret-free executable or explicitly non-executable case while preserving explicit `provider_id`, `model`, `capability_id`, route expectations, evidence refs, and scope reasons. Unsupported, skipped, and reduced-authority lanes are no longer implicit exclusions; they are emitted as first-class cases with stable execution policies (`record_unsupported`, `skip_case`, or `confirm_reduced_authority`). A private runner now materializes the synthesized case manifest and summary from the current Step 1 scope inventory. The generated Step 3 manifest contains 185 total cases: 88 `run`, 11 `reduced-authority`, 28 `skip`, and 58 `unsupported`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/exhaustive_smoke_synthesis.py`, `apps/astrabridge-sidecar/tests/test_exhaustive_smoke_synthesis.py`, `PRIVATE/provider-compatibility/step3_exhaustive_case_synthesis_runner.py`, `PRIVATE/provider-compatibility/runs/step3-exhaustive-case-synthesis-20260706/manifest.json`, `PRIVATE/provider-compatibility/runs/step3-exhaustive-case-synthesis-20260706/summary.json`, `PRIVATE/provider-compatibility/reports/step3-exhaustive-case-synthesis-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\exhaustive_smoke_synthesis.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_exhaustive_smoke_synthesis.py D:\AstraBridge\PRIVATE\provider-compatibility\step3_exhaustive_case_synthesis_runner.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_exhaustive_smoke_synthesis tests.test_exhaustive_smoke_contract`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step3_exhaustive_case_synthesis_runner.py`; inspected the generated Step 3 `manifest.json`, `summary.json`, and markdown report; ran `git diff --check` over the touched Step 3 files with no content-format failures; and ran a focused secret-pattern scan over the synthesis module, test, runner, report, generated manifest/summary, and this plan with no matches.
- Blockers: None.
- Next step: 4. General Model Lane Synthesis For Text, Tools, And Edit Authority.

### 2026-07-06 - Step 4

- Completed: Refined exhaustive synthesis for `general_model` lanes so Batch A no longer inherits placeholder task definitions. Text-health lanes now synthesize an exact short-answer profile. Command-execution lanes now split into structured-shell execution, reduced-authority confirmation, and authority-probe shapes. Edit lanes now split into structured scratch-patch, reduced-authority confirmation, and authority-probe shapes. The synthesized runner hints now carry authority metadata from Step 1 (`authority_tier`, `command_execution_status`, `parallel_tool_call_status`, `supports_tool_calls`, `supports_mcp_tools`) plus explicit runtime-turn contracts for shell and edit probes. This step also fixed a synthesis bug where custom runner hints were overriding the default skip/unsupported policy hints and dropping `allow_provider=false`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/exhaustive_smoke_synthesis.py`, `apps/astrabridge-sidecar/tests/test_exhaustive_smoke_synthesis.py`, `PRIVATE/provider-compatibility/runs/step3-exhaustive-case-synthesis-20260706/manifest.json`, `PRIVATE/provider-compatibility/runs/step3-exhaustive-case-synthesis-20260706/summary.json`, `PRIVATE/provider-compatibility/reports/step4-exhaustive-general-model-lane-synthesis-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\exhaustive_smoke_synthesis.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_exhaustive_smoke_synthesis.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_exhaustive_smoke_synthesis tests.test_exhaustive_smoke_contract`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step3_exhaustive_case_synthesis_runner.py`; inspected representative rebuilt cases for DeepSeek, GLM, Qwen, Yunwu, and OpenAI scope-deferred lanes; and ran `git diff --check` over the touched Step 4 synthesis/test/manifest files with no content-format failures.
- Blockers: None.
- Next step: 5. Exhaustive Runner Preflight, Batching, And Resume Support.

### 2026-07-06 - Step 5

- Completed: Added a reusable exhaustive runner layer that materializes standard A-F batch manifests from the Step 3 case manifest, initializes a root `run-state.json` with resume markers, performs sidecar/managed-vault/provider-availability preflight using secret-free HTTP reads, and executes selected batches while persisting per-case results plus per-batch summaries. The runner supports partial execution and later resume without recomputing completed case outputs. A Step 5 private runner materialized the current batch plan, verified the live sidecar at `http://127.0.0.1:8791`, confirmed managed-vault availability for `deepseek`, `glm`, `kimi`, `qwen`, and `yunwu`, and proved resume by partially executing then resuming a skip-only general-model batch from the generated manifest.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/exhaustive_smoke_runner.py`, `apps/astrabridge-sidecar/tests/test_exhaustive_smoke_runner.py`, `PRIVATE/provider-compatibility/step5_exhaustive_runner_preflight_runner.py`, `PRIVATE/provider-compatibility/runs/step5-exhaustive-runner-preflight-batching-resume-20260706/batch-plan.json`, `PRIVATE/provider-compatibility/runs/step5-exhaustive-runner-preflight-batching-resume-20260706/preflight.json`, `PRIVATE/provider-compatibility/runs/step5-exhaustive-runner-preflight-batching-resume-20260706/run-state.json`, `PRIVATE/provider-compatibility/runs/step5-exhaustive-runner-preflight-batching-resume-20260706/summary.json`, `PRIVATE/provider-compatibility/runs/step5-exhaustive-runner-preflight-batching-resume-20260706/validation-summary.json`, `PRIVATE/provider-compatibility/runs/step5-exhaustive-runner-preflight-batching-resume-20260706/batches/**`, `PRIVATE/provider-compatibility/reports/step5-exhaustive-runner-preflight-batching-resume-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\exhaustive_smoke_runner.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_exhaustive_smoke_runner.py D:\AstraBridge\PRIVATE\provider-compatibility\step5_exhaustive_runner_preflight_runner.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_exhaustive_smoke_runner tests.test_exhaustive_smoke_synthesis tests.test_exhaustive_smoke_contract`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step5_exhaustive_runner_preflight_runner.py`; inspected `preflight.json`, `validation-summary.json`, `summary.json`, and the Step 5 markdown report; and confirmed the live preflight reported `pass` for sidecar reachability, managed-vault session, provider availability, and artifact-root setup.
- Blockers: None.
- Next step: 6. Execute Exhaustive Batch A: General Text, Tool, And Code-Agent Lanes.

### 2026-07-06 - Step 6

- Completed work: Added reusable Batch A live classification helpers for general-model text health, command execution, and edit/apply-patch lanes. The helper now parses runtime thread items plus session `.jsonl` records so shell tool calls and edit/apply strategy signals survive when `/api/runtime/thread` omits them. Added focused regression coverage for those helpers. Added a private Step 6 runner that materializes Batch A, runs live text-health checks through `/api/llm-manager/keys/test`, executes runtime command/edit probes through `/api/runtime/threads/create` and `/api/runtime/turns/start`, preserves scratch files plus session evidence, and writes per-case JSON plus batch/root summaries. Multiple preserved Step 6 runs now exist under `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706*` together with the first markdown report at `PRIVATE/provider-compatibility/reports/step6-exhaustive-batch-a-general-model-20260706.md`. Live evidence already proves: DeepSeek Batch 1 can complete; Qwen/GLM text-health lanes can return provider-backed `ok`; Kimi reduced-authority lanes can produce real shell-tool pass evidence on some code-agent variants; and unsupported/no-route Qwen VL text-health lanes fail with explicit router reasons.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/exhaustive_smoke_general_model.py`, `apps/astrabridge-sidecar/tests/test_exhaustive_smoke_general_model.py`, `PRIVATE/provider-compatibility/step6_exhaustive_batch_a_runner.py`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706*`, `PRIVATE/provider-compatibility/reports/step6-exhaustive-batch-a-general-model-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile` over the Step 6 helper/test/runner files; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_exhaustive_smoke_general_model tests.test_exhaustive_smoke_runner tests.test_exhaustive_smoke_synthesis tests.test_exhaustive_smoke_contract` with 22 passing tests; ran multiple preserved live Step 6 executions against both `http://127.0.0.1:8791` and `http://127.0.0.1:8792`; inspected representative case JSON, run summaries, runtime event streams, and session traces; manually called `/api/runtime/turns/interrupt` against a pinned thread/turn and confirmed the sidecar replied `no active turn to interrupt`; and ran `git diff --check` over the touched Step 6 source files with no formatting failures.
- Blockers: Step 6 cannot be marked complete yet because Batch A repeatedly hits a sidecar runtime-state bug after DeepSeek Batch 1 finishes. On both the long-lived `8791` sidecar and the cleaner `8792` sidecar, the next provider switch emits repeated `runtime_switch_deferred_active_turn` events that pin the last DeepSeek thread/turn, while `/api/runtime/turns/interrupt` simultaneously reports `no active turn to interrupt`. This stale pinned-active-turn guard prevents reliable cross-provider runtime thread creation for the remaining Batch A agent lanes and currently forces either long retry stalls or executor failures before the batch summary can close.
- Next step: Fix or work around the stale pinned-active-turn cleanup path in the sidecar runtime service, then rerun Step 6 Batch A on `http://127.0.0.1:8792` starting from `batch-a-general-model-02`, preserving the existing `step6-exhaustive-batch-a-general-model-20260706*` evidence set.

### 2026-07-06 - Step 6 Continuation

- Completed work: Implemented runtime pin-release logic inside `RuntimeService` so a turn pin no longer survives only by timeout. The service now clears the pin on terminal turn notifications, on successful interrupts, on explicit pin expiry, on client shutdown, and when `thread/read` observes the pinned turn in a terminal state. Added regression coverage that proves a terminal notification clears the pin and that a completed `thread/read` snapshot clears the pin without waiting for the five-minute `TURN_RUNTIME_PIN_SECONDS` timeout. This addresses the specific stale guard that was blocking cross-provider Batch A handoff after DeepSeek Batch 1.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py`, `apps/astrabridge-sidecar/tests/test_sidecar_services.py`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\runtime_service.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_sidecar_services.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_thread_list_defers_provider_switch_while_turn_runtime_is_pinned tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_notification_clears_pinned_turn_after_terminal_event tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_read_thread_clears_pinned_turn_after_terminal_turn_snapshot`; restarted a clean sidecar on `http://127.0.0.1:8792`; and verified through `/api/llm-manager/session` plus `/api/llm-manager/keys/test` that the restarted sidecar is now blocked by a locked LLM API Manager session rather than by the old stale pin path.
- Blockers: Live Step 6 rerun is currently blocked because the restarted clean sidecar is in anonymous/locked LLM API Manager mode. Provider vault users (`astra`, `user`) are visible, but `/api/llm-manager/keys/test` returns `Unlock LLM API Manager first.` until a managed-user session is unlocked again. Because this sidecar restart was required to pick up the runtime pin fix, Batch A cannot yet be rerun to completion on the fixed code path without re-unlocking the managed vault.
- Next step: Unlock the `8792` sidecar's LLM API Manager session through an approved managed-vault path, then rerun Step 6 Batch A on the fixed runtime-service build and inspect whether Batch 2+ now crosses providers without `runtime_switch_deferred_active_turn`.

### 2026-07-06 - Step 6 Completion

- Completed work: Closed Step 6 on the fixed code path. Added an app-server export compatibility shim in the model catalog so exported reasoning labels no longer leak internal `off` or native `max` values into `astrabridge-models.json`; exported general-lane catalogs now emit app-server-safe reasoning values while the internal runtime contract still preserves its own normalized policy semantics. Started a fresh current-source sidecar on `http://127.0.0.1:8793`, unlocked the managed `astra` vault through the sidecar-managed admin-token flow, verified DeepSeek and GLM keys live, and reran Batch A as `step6-exhaustive-batch-a-general-model-20260706-r8`. The rerun completed all 54 general lanes and advanced the resume marker to Batch B. This eliminated the earlier stale-pin and catalog-parse blockers and converted the prior DeepSeek/Yunwu pre-provider failures into provider-backed results. Final Batch A `r8` totals are `pass=21`, `partial=8`, `fail=8`, `reduced-authority=5`, `skipped=12`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`, `apps/astrabridge-sidecar/tests/test_model_catalog_contract.py`, `apps/astrabridge-sidecar/tests/test_tool_call_compatibility.py`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/**`, `PRIVATE/provider-compatibility/reports/step6-exhaustive-batch-a-general-model-20260706-r8.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `python -m py_compile` over the updated model-catalog and focused test files; ran `python -m unittest tests.test_model_catalog_contract tests.test_tool_call_compatibility`; reran the pinned-turn regressions in `tests.test_sidecar_services`; verified DeepSeek and GLM live key tests on the fresh `8793` sidecar after managed-vault unlock; ran `python D:\AstraBridge\PRIVATE\provider-compatibility\step6_exhaustive_batch_a_runner.py` with `ASTRABRIDGE_STEP6_RUN_ID=step6-exhaustive-batch-a-general-model-20260706-r8` and `ASTRABRIDGE_STEP6_SIDECAR_BASE=http://127.0.0.1:8793`; confirmed `summary.json`, `validation-summary.json`, and `step6-exhaustive-batch-a-general-model-20260706-r8.md` all report `completed_case_count=54`; reran the focused suite `tests.test_exhaustive_smoke_general_model tests.test_exhaustive_smoke_runner tests.test_exhaustive_smoke_synthesis tests.test_exhaustive_smoke_contract tests.test_model_catalog_contract tests.test_tool_call_compatibility` plus the three pinned-turn sidecar regressions with 42 passing tests; ran `git diff --check` over the touched source files; and ran a focused secret-pattern scan over the `r8` run/report artifacts and this plan with no matches.
- Blockers: None for Step 6 completion. Residual Batch A failures and partials are now classified evidence rather than execution blockers: Qwen VL general lanes still fail with explicit no-route outcomes, Kimi highspeed text health still fails, and several edit lanes still degrade to shell-based scratch edits or no explicit apply-patch surface.
- Next step: 7. Execute Exhaustive Batch B: Vision Analyze Lanes, starting from `batch-b-vision-analyze-01`.

### 2026-07-06 - Step 7

- Completed work: Added a private Step 7 runner that resumes from the completed `step6-exhaustive-batch-a-general-model-20260706-r8` baseline, reuses the existing exhaustive batch plan, executes every runnable `vision.analyze` lane through `/api/runtime/capability-smoke`, and classifies route mismatch, empty-answer, timeout, unsupported-media, artifact, and skip/unsupported outcomes into the normalized exhaustive result schema. The runner preserves per-case evidence paths under the baseline workspace root, writes a Step 7 validation summary plus markdown report, and records which catalog models remain text-only under providers that do expose some vision route targets. Live Batch B completion now covers all 18 vision lanes: `unsupported=10`, `fail=6`, `pass=1`, `skipped=1`. The most important new finding is not a missing provider feature but explicit route drift: six runnable lanes resolved to the wrong route target, including all four runnable Qwen vision lanes resolving to the Kimi `kimi-k2.7-code` vision adapter and two Kimi variants (`kimi-k2.6`, `kimi-k2.7-code-highspeed`) collapsing onto `kimi-k2.7-code`.
- Files changed: `PRIVATE/provider-compatibility/step7_exhaustive_batch_b_runner.py`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/batches/batch-b-vision-analyze-*/**`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/run-state.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/summary.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step7-preflight.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step7-validation-summary.json`, `PRIVATE/provider-compatibility/reports/step7-exhaustive-batch-b-vision-analyze-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `python -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step7_exhaustive_batch_b_runner.py`; ran `python D:\AstraBridge\PRIVATE\provider-compatibility\step7_exhaustive_batch_b_runner.py` with `ASTRABRIDGE_STEP7_SIDECAR_BASE=http://127.0.0.1:8793`; reran the same command once more to confirm resume-safe regeneration of the Step 7 summary/report without re-executing finished cases; inspected `step7-validation-summary.json`, the Step 7 markdown report, `summary.json`, `run-state.json`, and representative per-case JSON for a passing Kimi lane plus a failing Qwen route-mismatch lane; and confirmed the focused secret scan over Step 7 artifacts reported `ok=true` with zero findings.
- Blockers: None for Step 7 completion. Residual failures are classified evidence, not execution blockers. The newly exposed explicit-route drift in `vision.analyze` is a product issue to address in a later implementation step, but it does not prevent Batch B from being considered exhaustively executed and classified.
- Next step: 8. Execute Exhaustive Batch C: Speech Transcribe Lanes, starting from `batch-c-speech-transcribe-01`.

### 2026-07-06 - Step 8

- Completed work: Extended the model-backed capability smoke surface so `speech.transcribe` can accept explicit custom `audio_inputs` during provider-backed smoke instead of always forcing the synthetic tone fixture. Added a focused regression test that proves custom inline audio is forwarded to the runtime while the sanitized smoke request hides raw audio bytes. Added a private Step 8 runner that resumes from the existing `step6-exhaustive-batch-a-general-model-20260706-r8` baseline, loads a preserved human-speech ASR fixture from prior secret-free request artifacts, executes every Batch C lane, and classifies route mismatch, provider-format/content-shape, empty-transcript, timeout, and artifact-persistence outcomes into the normalized exhaustive schema. Batch C is now fully classified across all 18 `speech.transcribe` lanes with `pass=1`, `skipped=1`, and `unsupported=16`. The one runnable lane, `qwen/qwen3-asr-flash`, produced a correct provider-backed pass with `route provider=qwen`, `route model=qwen3-asr-flash`, `adapter=qwen.asr.chat.v1`, `usage total_tokens=33`, and a non-empty persisted transcript artifact.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py`, `apps/astrabridge-sidecar/tests/test_capability_smoke.py`, `PRIVATE/provider-compatibility/step8_exhaustive_batch_c_runner.py`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/batches/batch-c-speech-transcribe-*/**`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/run-state.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/summary.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step8-preflight.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step8-validation-summary.json`, `PRIVATE/provider-compatibility/reports/step8-exhaustive-batch-c-speech-transcribe-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `python -m py_compile D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\capabilities\smoke.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_capability_smoke.py D:\AstraBridge\PRIVATE\provider-compatibility\step8_exhaustive_batch_c_runner.py`; ran `python -m unittest tests.test_capability_smoke`; ran `python D:\AstraBridge\PRIVATE\provider-compatibility\step8_exhaustive_batch_c_runner.py` twice with `ASTRABRIDGE_STEP8_SIDECAR_BASE=http://127.0.0.1:8793` to confirm both live execution and resume-safe regeneration; inspected `step8-validation-summary.json`, the Step 8 markdown report, `summary.json`, and the provider-backed case record for `capability-qwen-qwen3-asr-flash-speech.transcribe-run`; confirmed the persisted transcript artifact under the baseline workspace root was non-empty; and ran `git diff --check` over the touched Step 8 source files with no formatting failures beyond line-ending warnings from the existing Windows worktree.
- Blockers: None for Step 8 completion. No new residual runtime blocker was exposed in Batch C. The only live ASR lane passed cleanly, and the remaining lanes are explicit unsupported/skip evidence rather than unclassified gaps.
- Next step: 9. Execute Exhaustive Batch D: Speech Synthesize Lanes, starting from `batch-d-speech-synthesize-01`.

### 2026-07-06 - Step 9

- Completed work: Added a private Step 9 runner that resumes from the existing `step6-exhaustive-batch-a-general-model-20260706-r8` baseline, reuses the current exhaustive batch plan, executes every `speech.synthesize` lane through `/api/runtime/capability-smoke`, and classifies route mismatch, missing-audio, invalid-container, provider-format, timeout, and skip/unsupported outcomes into the normalized exhaustive schema. Batch D is now fully classified across all 18 `speech.synthesize` lanes with `partial=1`, `fail=1`, `skipped=1`, and `unsupported=15`. The two runnable Qwen TTS lanes both produced provider-backed evidence and surfaced concrete product issues rather than coverage gaps: `qwen3-tts-flash` returned a persisted `.wav` artifact whose container is not valid RIFF/WAV, and `qwen3-tts-instruct-flash` resolved onto the plain `qwen3-tts-flash` route target instead of preserving the explicit instruct model selection.
- Files changed: `PRIVATE/provider-compatibility/step9_exhaustive_batch_d_runner.py`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/batches/batch-d-speech-synthesize-*/**`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/run-state.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/summary.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step9-preflight.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step9-validation-summary.json`, `PRIVATE/provider-compatibility/reports/step9-exhaustive-batch-d-speech-synthesize-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `python -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step9_exhaustive_batch_d_runner.py`; ran `python D:\AstraBridge\PRIVATE\provider-compatibility\step9_exhaustive_batch_d_runner.py` with `ASTRABRIDGE_STEP9_SIDECAR_BASE=http://127.0.0.1:8793`; inspected `step9-validation-summary.json`, the Step 9 markdown report, `run-state.json`, and both runnable Qwen per-case JSON records; confirmed the focused secret scan over Step 9 artifacts reported `ok=true` with zero findings; and verified the resume marker advanced to `batch-e-image-generate-01`.
- Blockers: None for Step 9 completion. The remaining TTS problems are classified product findings, not execution blockers: one invalid persisted WAV container and one explicit instruct-model route drift.
- Next step: 10. Execute Exhaustive Batch E: Image Generate Lanes, starting from `batch-e-image-generate-01`.

### 2026-07-06 - Step 10

- Completed work: Added a private Step 10 runner that resumes from the existing `step6-exhaustive-batch-a-general-model-20260706-r8` baseline, reuses the current exhaustive batch plan, executes every `image.generate` lane through `/api/runtime/capability-smoke`, and classifies route mismatch, missing-image, invalid-image, manifest-missing, manifest-entry, count-mismatch, timeout, and skip/unsupported outcomes into the normalized exhaustive schema. Batch E is now fully classified across all 23 `image.generate` lanes with `unsupported=17`, `skipped=1`, `fail=4`, and `partial=1`. All five runnable Yunwu adapter-only lanes produced provider-backed evidence. Four of them exposed explicit route/model drift: `flux-kontext-max`, `flux-kontext-pro`, `gpt-image-1`, and `gpt-image-2-all` all resolved onto `gpt-image-2` rather than preserving the pinned adapter-only model. The remaining runnable lane, `gpt-image-2`, did persist valid local image artifacts and a valid generated asset manifest, but the normalized result reported `actual_n=2` for `requested_n=1`, so it remains `partial` rather than `pass`.
- Files changed: `PRIVATE/provider-compatibility/step10_exhaustive_batch_e_runner.py`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/batches/batch-e-image-generate-*/**`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/run-state.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/summary.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step10-preflight.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step10-validation-summary.json`, `PRIVATE/provider-compatibility/reports/step10-exhaustive-batch-e-image-generate-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `python -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step10_exhaustive_batch_e_runner.py`; ran `python D:\AstraBridge\PRIVATE\provider-compatibility\step10_exhaustive_batch_e_runner.py` with `ASTRABRIDGE_STEP10_SIDECAR_BASE=http://127.0.0.1:8793`; inspected `step10-validation-summary.json`, the Step 10 markdown report, `run-state.json`, `batch-e-image-generate-02/summary.json`, and representative runnable case records for `capability-yunwu-gpt-image-2-image.generate-adapter-only-run` plus `capability-yunwu-gpt-image-1-image.generate-adapter-only-run`; confirmed the focused secret scan over Step 10 artifacts reported `ok=true` with zero findings; and verified the resume marker advanced to `batch-f-continuation-01`.
- Blockers: None for Step 10 completion. The remaining image-generation issues are classified product findings, not execution blockers: four adapter-only image routes drift to `gpt-image-2`, and the direct `gpt-image-2` route currently returns two persisted assets for a single-image request.
- Next step: 11. Execute Exhaustive Batch F: Compact, Health-Check, And Same-Task Continuation Lanes, starting from `batch-f-continuation-01`.

### 2026-07-06 - Step 11

- Completed work: Added a private Step 11 runner that resumes from the existing `step6-exhaustive-batch-a-general-model-20260706-r8` baseline, reuses the current exhaustive batch plan, executes every compact/handoff lane, and classifies `same_task.handoff_target`, `thread.compact`, and `thread.health_check` into the normalized exhaustive schema. Batch F is now fully classified across all 54 continuation lanes with `pass=13`, `partial=28`, `reduced-authority=1`, and `skipped=12`. Every in-scope runnable lane now has provider-backed evidence with preserved session-path artifacts and per-case runtime signals. The dominant residual findings are continuation-quality problems rather than missing coverage: `target_text_mismatch=6`, `compact_failed=7`, `compact_stale=12`, and `health_marker_lost=3`. DeepSeek continuation lanes were the strongest overall (`pass=7`, `partial=5`), Qwen same-task switching partly works but most compact/health-check lanes degrade to stale or failed compaction, Yunwu same-task handoff passed while its compact/health-check lanes remained partial, and only one Kimi same-task target stayed downgraded to explicit `reduced-authority`.
- Files changed: `PRIVATE/provider-compatibility/step11_exhaustive_batch_f_runner.py`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/batches/batch-f-continuation-*/**`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/run-state.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/summary.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step11-preflight.json`, `PRIVATE/provider-compatibility/runs/step6-exhaustive-batch-a-general-model-20260706-r8/step11-validation-summary.json`, `PRIVATE/provider-compatibility/reports/step11-exhaustive-batch-f-continuation-20260706.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `python -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step11_exhaustive_batch_f_runner.py`; ran `python D:\AstraBridge\PRIVATE\provider-compatibility\step11_exhaustive_batch_f_runner.py` with `ASTRABRIDGE_STEP11_SIDECAR_BASE=http://127.0.0.1:8793`; inspected `step11-validation-summary.json`, the Step 11 markdown report, `run-state.json`, `summary.json`, and representative per-case JSON across DeepSeek, GLM, Kimi, Qwen, and Yunwu continuation lanes; confirmed `completed_case_count=185` and `pending_case_count=0`; confirmed the focused secret scan over Step 11 artifacts reported `ok=true` with zero findings; and verified the resume marker is now fully cleared.
- Blockers: None for Step 11 completion. Residual continuation problems are now explicit evidence rather than execution blockers: most Qwen compact/health-check lanes degrade to `compact_stale` or `compact_failed`, several Qwen/DeepSeek handoff targets produce `target_text_mismatch`, and three health-check lanes lose the continuity marker after compaction.
- Next step: 12. Compatibility Matrix Consolidation And Final Readiness Report.

### 2026-07-06 - Step 12

- Completed work: Added a private Step 12 consolidation runner that consumes the preserved Step 1 scope manifest, Step 3 case manifest, the completed `step6-exhaustive-batch-a-general-model-20260706-r8` baseline, and the Step 6-11 validation summaries to generate a maintained compatibility matrix snapshot, summary, and final readiness report. The new maintained surfaces now live under `PRIVATE/provider-compatibility/runs/step12-exhaustive-compatibility-matrix-20260706/` and `PRIVATE/provider-compatibility/reports/step12-exhaustive-final-readiness-20260706.md`. They reflect the exact exhaustive totals `pass=36`, `partial=38`, `fail=19`, `reduced-authority=6`, `skipped=28`, and `unsupported=58`, plus model-level promotion totals `verified=1`, `partial=13`, `blocked=8`, and `unknown=1`. Updated the public runbook so the current evidence pack points at the new exhaustive provider-backed matrix/readiness surfaces rather than only the earlier representative audit track.
- Files changed: `PRIVATE/provider-compatibility/step12_exhaustive_matrix_readiness_runner.py`, `PRIVATE/provider-compatibility/runs/step12-exhaustive-compatibility-matrix-20260706/matrix.json`, `PRIVATE/provider-compatibility/runs/step12-exhaustive-compatibility-matrix-20260706/summary.json`, `PRIVATE/provider-compatibility/runs/step12-exhaustive-compatibility-matrix-20260706/report.md`, `PRIVATE/provider-compatibility/reports/step12-exhaustive-final-readiness-20260706.md`, `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`, `PLAN/PROVIDER_MODEL_CAPABILITY_EXHAUSTIVE_SMOKE_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step12_exhaustive_matrix_readiness_runner.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step12_exhaustive_matrix_readiness_runner.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_provider_model_compatibility_matrix tests.test_provider_capability_verification_gate`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe scripts\run_provider_capability_verification_gate.py --run-id step12-provider-capability-gate-20260706`, which passed and wrote gate artifacts under `PRIVATE/agentic-update-pipeline/runs/step12-provider-capability-gate-20260706/`; ran `git diff --check` over the touched Step 12 files with a clean result; and ran a focused secret-pattern scan over the Step 12 runner, runbook, plan, and new matrix/report artifacts with no matches.
- Blockers: None.
- Next step: Plan complete. Future maintenance should start from `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` and the Step 12 matrix summary.
