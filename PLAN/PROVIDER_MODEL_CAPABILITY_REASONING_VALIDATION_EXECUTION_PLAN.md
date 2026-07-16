# Provider Model Capability And Reasoning Validation Execution Plan

## Total Objective

Create a durable, evidence-backed validation system for AstraBridge provider/model capability compatibility, with special attention to multimodal input/output support and cross-provider reasoning-effort mapping. The final system should let agents safely update provider/model metadata, verify request-shape assumptions, run bounded live smokes only when authorized, and adapt to new models or providers without rewriting existing adapters.

## Deliverables

- A provider/model/capability matrix that distinguishes provider-level defaults from model-level capabilities.
- Official-document evidence records for priority providers and high-risk capability claims.
- A reasoning-effort mapping audit that compares AstraBridge behavior with official provider docs and OpenRouter-style abstraction.
- Static request-shape tests and dry-run matrix checks for multimodal and reasoning paths.
- A bounded live-smoke protocol for managed-vault providers, with redacted artifacts under `PRIVATE/**`.
- A runbook explaining how future agents should update, verify, and roll back provider/model capability changes.

## Constraints And Attention Notes

1. Do not read desktop key files, plaintext secret files, cookies, bearer tokens, or provider raw secrets unless the user explicitly authorizes that exact action in the current turn.
2. Use managed vault keys only when the user explicitly authorizes live provider testing for the current turn. Never print or persist raw keys, admin session tokens, authorization headers, or provider raw secret material.
3. Preserve experiment artifacts by default, including configs, logs, sanitized raw call records, parsed outputs, validation reports, smoke summaries, and failure reports. Do not clean artifacts unless the user explicitly names cleanup targets.
4. Prefer official provider documentation and primary sources. Record source URL, retrieval date, source type, and the exact capability claim being relied on.
5. Treat OpenAI as a normal API-key provider. Do not reintroduce official OpenAI account login as a product path.
6. Do not claim full support from a provider-level flag. Model-level capability records must gate multimodal routing whenever capability support varies by model.
7. Reasoning effort does not need exhaustive live testing for every level, but every provider-specific mapping must be justified by official docs or marked unverified/unsupported.
8. Live tests must be small, bounded, and intentionally selected. Use dry-run/static checks for broad coverage and live smoke only for representative high-risk paths.
9. Do not write results back to external platforms unless the user explicitly approves writeback.
10. Existing dirty worktree changes may belong to the user or earlier agents. Do not revert unrelated changes.

## Adjustment Policy

Agents may reasonably adjust specific substeps, implementation details, file paths, commands, provider ordering, or sequencing when evidence from the workspace requires it. Such adjustments must not change the total objective, lower the planned difficulty, remove quality gates, or replace substantive verification with cosmetic documentation. If a core objective becomes infeasible, record the blocker, evidence, attempted approaches, and a substitute path that preserves the original intent.

## Execution Rules

1. Each agent turn should complete exactly one numbered step unless the user explicitly asks otherwise.
2. Each turn must start by reading this plan and identifying the next step whose status is not `completed`.
3. Each turn must update this plan before stopping.
4. A step can be marked `completed` only when its acceptance criteria are met.
5. If blocked, record the concrete blocker, evidence, attempted paths, and exact next entry point.
6. Each turn must end with a concise handoff: completed work, files changed, validation run, blockers, and next step.

## Current Progress

- Current status: Complete.
- Completed steps: Step 0, Create Durable Plan; Step 1, Inventory Current Provider And Model Capability Surfaces; Step 2, Define Capability Taxonomy And Matrix Contract; Step 3, Create Official Documentation Source Registry For Priority Providers; Step 4, Audit Qwen/DashScope Model Capabilities And Multimodal Limits; Step 5, Audit OpenAI And Yunwu/OpenAI-Compatible Capability Assumptions; Step 6, Audit DeepSeek, Kimi, And GLM Capability Assumptions; Step 7, Audit Reasoning-Effort Abstraction Against Official Docs And OpenRouter; Step 8, Map Current Runtime Gaps To Code Owners And Risk Levels; Step 9, Implement Model-Level Capability Gating Improvements; Step 10, Implement Static Request-Shape Validators; Step 11, Build Dry-Run Matrix Generator; Step 12, Define Bounded Live-Smoke Selection Policy; Step 13, Run Authorized Managed-Key Live Smokes For Priority Paths; Step 14, Classify Failures And Define Fallback Behavior; Step 15, Update UI And User-Facing Status Surfaces; Step 16, Create Provider Capability And Reasoning Runbook; Step 17, Add Regression Gate Or CI-Friendly Verification Command; Step 18, Completion Audit And Final Handoff.
- Current step: None - objective complete.
- Next step: Future maintenance should start with `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` and `python scripts\run_provider_capability_verification_gate.py --run-id provider-capability-gate-YYYYMMDD`.
- Last updated: 2026-07-06.

## Execution Steps

### 0. Create Durable Plan

Goal: Create this durable plan and make the next entry point clear.

Main actions:

- Define the total objective.
- Record constraints, adjustment policy, execution rules, steps, and acceptance criteria.
- Set current progress and initial log entry.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, constraints, adjustment policy, current progress, steps, acceptance criteria, and progress log.
- Next step is clearly identified.

Status: completed

### 1. Inventory Current Provider And Model Capability Surfaces

Goal: Build a concise inventory of where AstraBridge currently stores and derives provider/model capability information.

Main actions:

- Inspect provider profiles, model catalog records, generated catalog data, capability specs, adapter contracts, router runtime contracts, and any existing matrix/report files.
- Identify every field that can affect multimodal input/output, tool calling, streaming, context window, output limit, reasoning, and provider-specific request behavior.
- Record which surfaces are provider-level, model-level, adapter-level, route-level, or smoke-evidence-level.

Acceptance criteria:

- A written inventory exists under `PRIVATE/agentic-update-pipeline/reports/` or `PLAN/` and cites exact source files.
- The inventory distinguishes provider-level flags from model-level capability claims.
- The next agent can tell which files must be updated for a new provider/model capability.

Status: completed

### 2. Define Capability Taxonomy And Matrix Contract

Goal: Define the minimum capability taxonomy needed for model-level routing and validation.

Main actions:

- Define stable capability dimensions: text input/output, image input/output, audio input/output, video input/output if applicable, tool calling, parallel tools, streaming, structured edits, web/search lane, context window, output limit, prompt cache, and reasoning behavior.
- Decide how to represent `declared`, `verified`, `failed`, `partial`, `unknown`, and `unsupported`.
- Specify how official-document evidence, static request-shape validation, dry-run results, and live-smoke results attach to each matrix entry.

Acceptance criteria:

- A matrix contract document exists or the existing matrix contract is updated.
- The contract includes status semantics, required evidence fields, and source precedence.
- The contract explicitly rejects inferring all model capabilities from a provider-level flag.

Status: completed

### 3. Create Official Documentation Source Registry For Priority Providers

Goal: Establish primary-source inputs for provider capability and reasoning claims.

Main actions:

- List priority providers for this phase: Yunwu/OpenAI-compatible, OpenAI official docs for protocol reference, Qwen/DashScope, DeepSeek, Kimi/Moonshot, GLM/Zhipu, and OpenRouter as reasoning-abstraction reference.
- For each provider, record official docs URLs for model lists, multimodal support, tool calls, reasoning/thinking, streaming constraints, and error/limit pages.
- Store retrieval metadata and note whether each source is stable, versioned, or likely to change.

Acceptance criteria:

- Source registry contains priority providers and relevant official URLs.
- Each source entry names the capability category it supports.
- Non-official sources are either excluded or clearly marked as secondary context.

Status: completed

### 4. Audit Qwen/DashScope Model Capabilities And Multimodal Limits

Goal: Convert Qwen official docs and observed failures into model-level compatibility rules.

Main actions:

- Verify official model support for Qwen text, vision, ASR, TTS, tool usage, streaming, and reasoning/thinking.
- Record image/audio input constraints such as minimum image size, supported formats, URL requirements, base64 limits, and streaming/non-streaming thinking constraints.
- Compare official claims with current Qwen profile, capability contracts, and adapters.

Acceptance criteria:

- Qwen matrix entries identify which models support vision, speech transcription, speech synthesis, text, tool usage, and reasoning/thinking.
- Known pitfalls include the image width/height greater-than-10px constraint and any thinking/streaming limitations.
- Any mismatch between docs and code is filed as a follow-up or fixed in a later implementation step.

Status: completed

### 5. Audit OpenAI And Yunwu/OpenAI-Compatible Capability Assumptions

Goal: Separate official OpenAI protocol assumptions from Yunwu-compatible runtime evidence.

Main actions:

- Review official OpenAI docs for Responses API, reasoning effort, tool calls, image input/output, streaming, structured outputs, and model capability declarations.
- Review Yunwu/OpenAI-compatible profile and previous live evidence for image generation, text, reasoning, and output artifact handling.
- Mark which OpenAI claims are official-protocol assumptions and which Yunwu paths are actually verified through managed keys.

Acceptance criteria:

- Matrix entries distinguish OpenAI official provider support from Yunwu/OpenAI-compatible support.
- Official OpenAI live tests remain optional unless the user supplies or authorizes an official key path.
- Yunwu verified evidence links to existing or new smoke records without exposing secrets.

Status: completed

### 6. Audit DeepSeek, Kimi, And GLM Capability Assumptions

Goal: Validate current assumptions for the other managed providers against official docs and existing smoke evidence.

Main actions:

- Review official docs for DeepSeek, Kimi/Moonshot, and GLM/Zhipu model capabilities, reasoning/thinking output behavior, tool usage, streaming, and multimodal support.
- Compare docs with current provider profiles, transports, capability contracts, and known failure records.
- Identify provider-specific pitfalls such as reasoning content format, token usage shape, stale/no-output behavior, or multimodal request format issues.

Acceptance criteria:

- Each provider has documented `declared`, `verified`, `failed`, or `unknown` capability states for priority models.
- Known pitfalls are recorded in the matrix or associated report.
- Any unsupported capability route is blocked or marked unverified rather than silently inferred.

Status: completed

### 7. Audit Reasoning-Effort Abstraction Against Official Docs And OpenRouter

Goal: Decide whether AstraBridge's reasoning-effort algorithm is reasonable without exhaustively live-testing every level.

Main actions:

- Review OpenRouter's reasoning abstraction as a design reference, including effort levels, token budgets, reasoning output inclusion, and provider-specific mapping.
- Review official docs for OpenAI reasoning effort, Qwen `enable_thinking`/thinking budget, Anthropic-style extended thinking budget if relevant to future support, and managed providers that expose reasoning content without an effort parameter.
- Compare those docs to AstraBridge reasoning policy, normalization, catalog contract, and transport mapping code.
- Define expected behavior for `off`, `low`, `medium`, `high`, `xhigh`, `auto`, unsupported/noop, and provider-specific budget-based modes.

Acceptance criteria:

- A reasoning-effort design audit exists with source citations and file references.
- The audit identifies which mappings are verified by docs, which are inferred, and which are unsupported.
- The audit recommends concrete changes or confirms current logic with caveats.

Status: completed

### 8. Map Current Runtime Gaps To Code Owners And Risk Levels

Goal: Turn documentation and inventory findings into actionable code gaps.

Main actions:

- Compare matrix/taxonomy requirements with current provider profiles, model catalog, capability registry, transports, request builders, history projector, and router fallback logic.
- Classify gaps by risk: route misclassification, invalid provider request, missing fallback, misleading UI, unverified reasoning mapping, context-window mismatch, or artifact/security issue.
- Assign each gap to the smallest likely code area.

Acceptance criteria:

- Gap report lists concrete files/functions and risk levels.
- Each gap has a proposed fix or explicit defer reason.
- The next implementation step is unambiguous.

Status: completed

### 9. Implement Model-Level Capability Gating Improvements

Goal: Ensure routing and adapters prefer model-level capability evidence over provider-level broad flags.

Main actions:

- Update capability registry, model catalog, provider profiles, or route resolution as needed so multimodal capabilities are gated by model-level declarations or adapter contracts.
- Avoid breaking provider-level defaults where all known models truly share a capability.
- Add tests for pure-text models that must not route to vision/audio adapters.

Acceptance criteria:

- Unsupported model/capability combinations are blocked before provider calls.
- Tests cover at least one positive and one negative case per high-risk provider family.
- Existing supported routes still resolve.

Status: completed

### 10. Implement Static Request-Shape Validators

Goal: Catch invalid multimodal and reasoning request shapes before live provider calls.

Main actions:

- Add or extend static validators for image, audio, tool, streaming, reasoning, context-window, and provider-specific parameter constraints.
- Include constraints like Qwen image dimensions, URL fetchability rules, ASR audio-only messages, temperature omission/clamping, and thinking/streaming rules where documented.
- Ensure validators return actionable redacted errors.

Acceptance criteria:

- Validators reject known-bad fixtures with clear local errors.
- Validators do not persist raw secrets or large media unless artifact policy allows sanitized storage.
- Unit tests cover representative bad and good request shapes.

Status: completed

### 11. Build Dry-Run Matrix Generator

Goal: Generate broad provider/model/capability coverage without spending provider tokens.

Main actions:

- Create or extend a dry-run command/service that enumerates configured providers and models, resolves capability candidates, builds sanitized request shapes, and records expected adapter/transport paths.
- Include reasoning-effort dry-run variants for representative levels without invoking providers.
- Emit a report that highlights unsupported, unknown, or conflicting combinations.

Acceptance criteria:

- Dry-run report covers all configured priority providers and their configured models.
- Report includes route, adapter, request-shape, reasoning mapping, and capability status per case.
- Report is secret-free and suitable for CI or agent handoff.

Status: completed

### 12. Define Bounded Live-Smoke Selection Policy

Goal: Decide which combinations deserve live provider calls and which remain static-only.

Main actions:

- Define a minimal live-smoke set per provider: text baseline, one multimodal representative per supported modality, one tool/reasoning representative when applicable, and one negative/fallback case where useful.
- Specify opt-in authorization language for managed vault usage.
- Define token/cost/time bounds and artifact redaction requirements.

Acceptance criteria:

- Live-smoke policy document lists selection rules and default cases.
- Policy explains why exhaustive provider/model/capability live testing is not required.
- User authorization boundary is explicit.

Status: completed

### 13. Run Authorized Managed-Key Live Smokes For Priority Paths

Goal: Produce bounded live evidence for selected high-risk paths when the user authorizes managed-key usage.

Main actions:

- Confirm the current user has authorized managed-key provider calls for this turn.
- Run only the approved live-smoke set, using managed vault injection and sanitized artifacts.
- Save summaries, raw redacted request/response diagnostics when allowed, and failure classifications under `PRIVATE/**`.

Acceptance criteria:

- Live-smoke results are saved with no raw keys, admin tokens, bearer headers, or secret-bearing URLs.
- Each live case is marked pass, partial, fail, blocked, or skipped with a concrete reason.
- Secret scan passes over new live-smoke artifacts.

Status: completed

### 14. Classify Failures And Define Fallback Behavior

Goal: Convert smoke and dry-run failures into actionable fallback or compatibility behavior.

Main actions:

- Classify each failure as unsupported model, invalid request-shape, provider outage, auth/key issue, timeout, semantic no-output, token/context issue, artifact issue, or unknown.
- Define runtime behavior for each class: local validation error, route fallback, retry with safer request shape, mark capability unverified, or user-facing remediation.
- Add tests for failure classification where behavior affects routing.

Acceptance criteria:

- Failure taxonomy is documented and mapped to runtime behavior.
- At least the known Qwen vision tiny-image failure is classified as local validation, not provider incompatibility.
- Tests cover failure behavior for high-risk classes.

Status: completed

### 15. Update UI And User-Facing Status Surfaces

Goal: Make capability status and uncertainty visible enough that users are not misled by provider/model switching.

Main actions:

- Inspect current UI surfaces for provider, model, capability routes, key health, smoke status, and task route switching.
- Add or update labels for verified, unverified, unsupported, partial, and failed capability states if needed.
- Ensure UI does not imply all models under a provider share every capability.

Acceptance criteria:

- UI or API surfaces expose model-level capability status where users choose or inspect models.
- Unsupported or unverified capabilities are not presented as fully available.
- Frontend tests or screenshots verify the relevant user-facing state if UI changes are made.

Status: completed

### 16. Create Provider Capability And Reasoning Runbook

Goal: Document how future agents should update models, capabilities, reasoning mappings, and validation artifacts.

Main actions:

- Write or update a runbook covering official-doc lookup, source registry updates, matrix changes, static validation, dry-run, live-smoke authorization, artifact preservation, secret scanning, and rollback.
- Include examples for adding a new Qwen multimodal model, changing an OpenAI reasoning effort mapping, and adding a new provider.
- Reference this plan as the execution contract.

Acceptance criteria:

- Runbook exists under `docs/` or a comparable project documentation path.
- Runbook includes step-by-step agent instructions and safety boundaries.
- Runbook links to evidence/artifact conventions and validation commands.

Status: completed

### 17. Add Regression Gate Or CI-Friendly Verification Command

Goal: Make the compatibility system easy for future agents to verify after updates.

Main actions:

- Define a single local command or documented command sequence that runs static request-shape tests, matrix contract checks, reasoning mapping checks, and dry-run matrix generation.
- Keep live provider calls out of default CI unless explicitly authorized.
- Ensure output includes a clear pass/fail summary and paths to reports.

Acceptance criteria:

- A documented verification command exists.
- The command or sequence avoids live provider calls by default.
- It fails on capability contract drift or unsupported route regressions.

Status: completed

### 18. Completion Audit And Final Handoff

Goal: Confirm the objective has been met and leave a concise future-maintenance handoff.

Main actions:

- Review deliverables against this plan's acceptance criteria.
- Confirm artifacts are preserved and secret scans have passed.
- Record remaining known risks, deferred providers/models, and the exact process for future model/provider updates.

Acceptance criteria:

- Current progress marks all completed steps accurately.
- Final report summarizes code changes, docs, validation, live evidence, residual risks, and next maintenance entry point.
- No required deliverable remains unaddressed or silently deferred.

Status: completed

## Progress Log

### 2026-07-06 - Step 0

- Completed: Created the durable plan for provider/model capability and reasoning-effort validation.
- Files changed: `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Checked that the plan includes total objective, deliverables, constraints, adjustment policy, execution rules, current progress, numbered steps, acceptance criteria, and progress log.
- Blockers: None.
- Next step: Step 1, Inventory Current Provider And Model Capability Surfaces.

### 2026-07-06 - Step 1

- Completed: Wrote the current provider/model capability surface inventory with file-level citations and explicit layer ownership.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step1-provider-model-capability-surface-inventory-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Verified the inventory report exists on disk, cites exact source files and line ranges, distinguishes provider/model/adapter/route/runtime/evidence layers, and names the files to update for new providers, models, capability changes, and reasoning mapping changes.
- Blockers: None.
- Next step: Step 2, Define Capability Taxonomy And Matrix Contract.

### 2026-07-06 - Step 2

- Completed: Updated the provider/model compatibility matrix contract to define a stable capability taxonomy, explicit status vocabulary, source precedence, dimension-level declaration rules, and structured evidence attachment rules.
- Files changed: `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Verified that the contract now includes capability taxonomy, status semantics for `declared`/`unsupported`/`unknown` and validation/promotion statuses, explicit declaration and validation source precedence, required `capability_dimensions` and `evidence_records` fields, and an explicit rule rejecting provider-level broad flags as proof of model-level capability.
- Blockers: None.
- Next step: Step 3, Create Official Documentation Source Registry For Priority Providers.

### 2026-07-06 - Step 3

- Completed: Upgraded the provider source registry to a capability-aware `v2` schema, added official-source coverage for the priority providers, tagged every source record with capability categories, retrieval date, stability, and primary-versus-secondary role, and added OpenRouter as a secondary reasoning-reference entry.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py`; `apps/astrabridge-sidecar/tests/test_provider_source_registry.py`; `PRIVATE/agentic-update-pipeline/reports/step3-official-provider-source-registry-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python D:\AstraBridge\apps\astrabridge-sidecar\tests\test_provider_source_registry.py` with 5 passing tests and `git diff --check -- D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\model_catalog\source_registry.py D:\AstraBridge\apps\astrabridge-sidecar\tests\test_provider_source_registry.py` with a clean result.
- Blockers: None.
- Next step: Step 4, Audit Qwen/DashScope Model Capabilities And Multimodal Limits.

### 2026-07-06 - Step 4

- Completed: Audited official Qwen/DashScope docs and current AstraBridge Qwen surfaces, produced a model-level capability matrix for text, vision, ASR, TTS, tool usage, and reasoning or thinking, and recorded concrete docs-to-code mismatches for later implementation steps.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step4-qwen-capability-audit-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m unittest tests.test_vision_analyze_adapter`, `python -m unittest tests.test_speech_transcribe_adapter`, `python -m unittest tests.test_speech_synthesize_adapter`, and `python -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_qwen_adapter_maps_effort_to_enable_thinking tests.test_sidecar_services.AstraBridgeServiceTests.test_qwen_transport_normalizes_reasoning_state_without_raw_payload_leak` from `D:\AstraBridge\apps\astrabridge-sidecar`, all passing. Ran `git diff --check -- D:\AstraBridge\PRIVATE\agentic-update-pipeline\reports\step4-qwen-capability-audit-20260706.md D:\AstraBridge\PLAN\PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` with a clean result.
- Blockers: None.
- Next step: Step 5, Audit OpenAI And Yunwu/OpenAI-Compatible Capability Assumptions.

### 2026-07-06 - Step 5

- Completed: Audited official OpenAI protocol docs versus local `openai` and Yunwu/OpenAI-compatible surfaces, separated protocol-backed capability claims from current Yunwu managed-key evidence, and recorded concrete mismatches around multimodal support, reasoning defaults, structured outputs, parallel tool calls, and image-generation validation.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step5-openai-yunwu-capability-audit-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m unittest tests.test_reasoning_policy_normalization`, `python -m unittest tests.test_provider_source_registry`, `python -m unittest tests.test_capability_registry`, and `python -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_responses_transport_stream_events_mark_function_calls_completed tests.test_sidecar_services.AstraBridgeServiceTests.test_responses_transport_stream_events_preserve_reasoning_items tests.test_sidecar_services.AstraBridgeServiceTests.test_responses_transport_normalizes_reasoning_state_without_raw_payload_leak tests.test_sidecar_services.AstraBridgeServiceTests.test_yunwu_transport_normalizes_response_without_raw_payload_leak` from `D:\AstraBridge\apps\astrabridge-sidecar`, all passing. Ran `git diff --check -- D:\AstraBridge\PRIVATE\agentic-update-pipeline\reports\step5-openai-yunwu-capability-audit-20260706.md D:\AstraBridge\PLAN\PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` with a clean result.
- Blockers: None.
- Next step: Step 6, Audit DeepSeek, Kimi, And GLM Capability Assumptions.

### 2026-07-06 - Step 6

- Completed: Audited official DeepSeek, Kimi/Moonshot, and GLM/Z.AI docs against current provider profiles, transports, capability contracts, tests, and preserved smoke evidence; produced model-level status calls for the priority models; and recorded concrete docs-to-code mismatches around DeepSeek output limits, Kimi non-thinking restrictions and tool-schema strictness, and GLM model-level multimodal ambiguity plus reasoning-default drift.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step6-deepseek-kimi-glm-capability-audit-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_chat_transport_normalizes_reasoning_notice_without_raw_payload_leak tests.test_sidecar_services.AstraBridgeServiceTests.test_chat_transport_repairs_duplicate_parallel_tool_calls_for_serial_model tests.test_sidecar_services.AstraBridgeServiceTests.test_kimi_chat_transport_normalizes_reasoning_and_tool_calls_without_raw_payload_leak tests.test_sidecar_services.AstraBridgeServiceTests.test_glm_chat_transport_normalizes_reasoning_notice_without_raw_payload_leak tests.test_sidecar_services.AstraBridgeServiceTests.test_glm_chat_transport_normalizes_tool_calls_without_raw_payload_leak` from `D:\AstraBridge\apps\astrabridge-sidecar`, all passing. Ran `git diff --check -- D:\AstraBridge\PRIVATE\agentic-update-pipeline\reports\step6-deepseek-kimi-glm-capability-audit-20260706.md D:\AstraBridge\PLAN\PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` with a clean result.
- Blockers: None.
- Next step: Step 7, Audit Reasoning-Effort Abstraction Against Official Docs And OpenRouter.

### 2026-07-06 - Step 7

- Completed: Audited official OpenAI, Qwen, DeepSeek, Kimi, and GLM reasoning/thinking controls plus OpenRouter's secondary abstraction guidance against AstraBridge's current reasoning normalization, provider defaults, catalog contract, and transport mappings. Recorded exact docs-backed, inferred, local-only, and unsupported mappings, with concrete findings around OpenAI/Qwen/DeepSeek/GLM default-level drift, Kimi's inferred scalar ladder, GLM `xhigh -> max` mismatch, and the lack of a first-class budget-based reasoning abstraction.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step7-reasoning-effort-audit-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m unittest tests.test_reasoning_policy_normalization tests.test_model_catalog_contract tests.test_provider_catalog_contract tests.test_sidecar_services.AstraBridgeServiceTests.test_provider_profiles_seed_reasoning_and_temperature_defaults tests.test_sidecar_services.AstraBridgeServiceTests.test_profile_service_defaults_reasoning_effort_from_provider_profile_when_missing tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_config_service_defaults_reasoning_effort_from_provider_profile_when_missing` from `D:\AstraBridge\apps\astrabridge-sidecar`, all passing. Ran `git diff --check -- D:\AstraBridge\PRIVATE\agentic-update-pipeline\reports\step7-reasoning-effort-audit-20260706.md D:\AstraBridge\PLAN\PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` with a clean result.
- Blockers: None.
- Next step: Step 8, Map Current Runtime Gaps To Code Owners And Risk Levels.

### 2026-07-06 - Step 8

- Completed: Mapped the runtime gaps from Steps 4 through 7 into concrete code-owner slices and risk classes, identifying the highest-risk follow-up work around provider-level capability heuristics, GLM reasoning wire mapping, Kimi non-thinking and fixed-parameter validation, default reasoning drift, generated catalog coverage gaps, structured-output blind spots, stale DeepSeek output-limit metadata, and UI verification semantics.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step8-runtime-gap-report-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m unittest tests.test_capability_registry tests.test_reasoning_policy_normalization tests.test_provider_catalog_contract` from `D:\AstraBridge\apps\astrabridge-sidecar`, and `git diff --check -- D:\AstraBridge\PRIVATE\agentic-update-pipeline\reports\step8-runtime-gap-report-20260706.md D:\AstraBridge\PLAN\PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Blockers: None.
- Next step: Step 9, Implement Model-Level Capability Gating Improvements.

### 2026-07-06 - Step 9

- Completed: Implemented model-level capability gating improvements across the catalog/runtime contract, capability routing, generated seed coverage, provider-profile router seeds, GLM/Kimi reasoning edge handling, and the desktop provider-draft modality surface so explicit model metadata now wins over provider-wide fallback heuristics for the high-risk multimodal lanes.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/diffing.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/zai_glm.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/moonshot_kimi.py`; `apps/astrabridge-desktop/src/features/runtime/reasoningOptions.ts`; `apps/astrabridge-sidecar/tests/test_capability_registry.py`; `apps/astrabridge-sidecar/tests/test_model_catalog_contract.py`; `apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`; `apps/astrabridge-sidecar/tests/test_reasoning_policy_normalization.py`; `apps/astrabridge-sidecar/tests/test_sidecar_services.py`; `apps/astrabridge-desktop/src/features/runtime/reasoningOptions.test.ts`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m unittest tests.test_capability_registry tests.test_model_catalog_contract tests.test_provider_catalog_contract tests.test_reasoning_policy_normalization tests.test_agentic_update_diffing tests.test_sidecar_services.AstraBridgeServiceTests.test_provider_profiles_seed_reasoning_and_temperature_defaults tests.test_sidecar_services.AstraBridgeServiceTests.test_provider_profiles_seed_catalog_provider_and_model_defaults tests.test_sidecar_services.AstraBridgeServiceTests.test_router_config_uses_provider_profile_defaults_for_new_provider_model tests.test_sidecar_services.AstraBridgeServiceTests.test_router_config_seeds_profile_fallback_models_without_static_catalog_duplicates tests.test_sidecar_services.AstraBridgeServiceTests.test_model_catalog_known_functions_fall_back_to_provider_profiles tests.test_sidecar_services.AstraBridgeServiceTests.test_metadata_seed_import_and_effective_catalog_are_conservative tests.test_sidecar_services.AstraBridgeServiceTests.test_profile_service_backfills_provider_policy_metadata_for_custom_profiles tests.test_sidecar_services.AstraBridgeServiceTests.test_profile_service_defaults_reasoning_effort_from_provider_profile_when_missing tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_config_service_defaults_reasoning_effort_from_provider_profile_when_missing` from `D:\AstraBridge\apps\astrabridge-sidecar`, all passing. Ran `npm.cmd test -- src/features/runtime/reasoningOptions.test.ts` from `D:\AstraBridge\apps\astrabridge-desktop`, passing. Ran `git diff --check --` on the touched files; it reported only line-ending warnings and no diff-check errors.
- Blockers: None.
- Next step: Step 10, Implement Static Request-Shape Validators.

### 2026-07-06 - Step 10

- Completed: Added local request-shape preflight validation for Kimi fixed-parameter and remote-image constraints across router preview/live request preparation, and tightened the vision capability adapters so Qwen rejects non-fetchable image URLs with redacted local errors while Kimi rejects remote image URLs in favor of inline/base64 or local-file inputs.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/vision_analyze_adapter.py`; `apps/astrabridge-sidecar/tests/test_vision_analyze_adapter.py`; `apps/astrabridge-sidecar/tests/test_reasoning_policy_normalization.py`; `apps/astrabridge-sidecar/tests/test_sidecar_services.py`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m compileall apps\astrabridge-sidecar\astrabridge_sidecar\router_service.py apps\astrabridge-sidecar\astrabridge_sidecar\capabilities\vision_analyze_adapter.py apps\astrabridge-sidecar\tests\test_vision_analyze_adapter.py apps\astrabridge-sidecar\tests\test_reasoning_policy_normalization.py apps\astrabridge-sidecar\tests\test_sidecar_services.py` from `D:\AstraBridge`; ran `python -m unittest tests.test_vision_analyze_adapter`, `python -m unittest tests.test_reasoning_policy_normalization`, and `python -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_kimi_adapter_maps_thinking_policy_and_streams_sse tests.test_sidecar_services.AstraBridgeServiceTests.test_kimi_adapter_maps_app_server_input_image_to_chat_image_part tests.test_sidecar_services.AstraBridgeServiceTests.test_kimi_adapter_rejects_remote_image_url_during_preview` from `D:\AstraBridge\apps\astrabridge-sidecar`, all passing.
- Blockers: None.
- Next step: Step 11, Build Dry-Run Matrix Generator.

### 2026-07-06 - Step 11

- Completed: Added a secret-free provider/model capability dry-run matrix generator, generated the first full priority-provider dry-run artifact set, and recorded the key preview blockers plus conflicting capability route pins for the next live-smoke-selection step.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_dry_run_matrix.py`; `apps/astrabridge-sidecar/tests/test_provider_capability_dry_run_matrix.py`; `PRIVATE/agentic-update-pipeline/reports/step11-provider-capability-dry-run-matrix-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m compileall apps\astrabridge-sidecar\astrabridge_sidecar\provider_capability_dry_run_matrix.py apps\astrabridge-sidecar\tests\test_provider_capability_dry_run_matrix.py` from `D:\AstraBridge`; ran `python -m unittest tests.test_provider_capability_dry_run_matrix` and `python -m unittest tests.test_provider_compatibility_smoke tests.test_capability_smoke tests.test_provider_model_compatibility_matrix` from `D:\AstraBridge\apps\astrabridge-sidecar`, all passing; executed `run_provider_capability_dry_run_matrix(run_id=\"step11-provider-capability-dry-run-matrix-20260706\")` to produce secret-free artifacts under `PRIVATE/agentic-update-pipeline/runs/step11-provider-capability-dry-run-matrix-20260706` and `PRIVATE/provider-compatibility/runs/step11-provider-capability-dry-run-matrix-20260706-capability-smoke`.
- Blockers: None.
- Next step: Step 12, Define Bounded Live-Smoke Selection Policy.

### 2026-07-06 - Step 12

- Completed: Defined the bounded Step 13 live-smoke policy, including candidate-selection rules, default per-provider case sets, static-only classes, run-size limits, request-shape bounds, artifact/redaction rules, and a reusable managed-vault authorization sentence.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step12-bounded-live-smoke-policy-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Cross-checked the policy against `PRIVATE/agentic-update-pipeline/reports/step11-provider-capability-dry-run-matrix-20260706.md`, `PRIVATE/provider-compatibility/reports/step10-real-provider-text-code-agent-20260704.md`, `PRIVATE/provider-compatibility/reports/step11-cross-provider-switch-fallback-20260705.md`, `PRIVATE/provider-compatibility/reports/step12-multimodal-capability-routes-20260705.md`, and the current adapter contracts in `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py` plus `apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py`.
- Blockers: None.
- Next step: Step 13, Run Authorized Managed-Key Live Smokes For Priority Paths.

### 2026-07-06 - Step 13

- Completed: Ran the bounded provider-backed live-smoke batch against the managed session on sidecar `8791`, preserved secret-free smoke artifacts under `PRIVATE/**`, and wrote a corrected human-reviewed classification report because one raw smoke case labeled as Qwen vision actually executed against Kimi.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step13-managed-key-live-smoke-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Called `POST /api/runtime/provider-compatibility-smoke` on `http://127.0.0.1:8791` using the current app session's temporary admin-session header and the bounded Step 12 case set (`qwen vision`, `qwen ASR`, `qwen TTS`, `kimi vision`); verified generated artifacts under `PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace/PRIVATE/provider-compatibility/runs/step13-bounded-live-smoke-20260706`; manually reviewed the persisted request/response artifacts for the two vision runs and the Qwen TTS case; ran a focused secret scan over the new smoke report paths and capability artifact directories with no raw keys, bearer tokens, admin-session tokens, cookies, or desktop key-file references found.
- Blockers: None.
- Next step: Step 14, Classify Failures And Define Fallback Behavior.

### 2026-07-06 - Step 14

- Completed: Added the Step 14 failure taxonomy to the runtime classifier, taught provider-compatibility smoke to persist structured `failure_notice` payloads and fail closed on provider/model mismatch, tightened runtime fallback-model selection to provider-profile-curated fallback sequences, and documented the taxonomy plus runtime behavior with concrete evidence examples.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/providers/failures.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/provider_compatibility_smoke.py`; `apps/astrabridge-sidecar/tests/test_provider_compatibility_smoke.py`; `apps/astrabridge-sidecar/tests/test_runtime_failure_taxonomy.py`; `PRIVATE/agentic-update-pipeline/reports/step14-failure-taxonomy-and-fallback-behavior-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python -m unittest apps\astrabridge-sidecar\tests\test_runtime_failure_taxonomy.py`, `python -m unittest apps\astrabridge-sidecar\tests\test_provider_compatibility_smoke.py` from `D:\AstraBridge`, and `python -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_supervisor_normalizes_context_limit_and_auth_failures tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_failure_classifier_uses_current_profile_defaults tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_failure_classifier_emits_restart_transition_for_runtime_corruption` from `D:\AstraBridge\apps\astrabridge-sidecar`, all passing.
- Blockers: None.
- Next step: Step 15, Update UI And User-Facing Status Surfaces.

### 2026-07-06 - Step 15

- Completed: Updated the desktop capability-routes surface so each resolved route and each selectable provider/model candidate now exposes an explicit model-level status (`verified`, `partial`, `failed`, `unverified`, or `unsupported`) instead of implying generic provider-wide availability. The candidate chooser now includes per-model status labels, the route header badges no longer claim `available` for unverified lanes, and the diagnostics explicitly distinguish partial smoke evidence from unverified or failed states.
- Files changed: `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.tsx`; `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.test.tsx`; `apps/astrabridge-desktop/src/features/i18n/catalog.ts`; `apps/astrabridge-desktop/src/styles.css`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `npm.cmd test -- --run src/features/capabilities/CapabilityRoutesPanel.test.tsx` from `D:\AstraBridge\apps\astrabridge-desktop` with 13 tests passing, and ran `node .\node_modules\typescript\bin\tsc --noEmit` from `D:\AstraBridge\apps\astrabridge-desktop` with a clean result.
- Blockers: None.
- Next step: Step 16, Create Provider Capability And Reasoning Runbook.

### 2026-07-06 - Step 16

- Completed: Rewrote the provider/model compatibility runbook so it now matches the current capability-and-reasoning validation track instead of the older compatibility slice. The new runbook makes `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` the primary execution contract, records current evidence roots and artifact conventions, defines the step-by-step maintenance workflow, lists the current validation commands, and adds explicit playbooks for adding a Qwen multimodal model, changing an OpenAI reasoning-effort mapping, and onboarding a new provider.
- Files changed: `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `rg -n "^# |^## |Primary execution contract|Safety Boundaries|Maintenance Workflow|Current Validation Commands|Example A|Example B|Example C|Promotion Rules|Handoff Expectations" D:\AstraBridge\docs\PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` to verify the required sections exist; verified the runbook's core referenced files and evidence roots exist with focused `Test-Path` checks; verified the referenced unittest modules exist on disk; and ran `git diff --check -- D:\AstraBridge\docs\PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md D:\AstraBridge\PLAN\PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` with a clean result.
- Blockers: None.
- Next step: Step 17, Add Regression Gate Or CI-Friendly Verification Command.

### 2026-07-06 - Step 17

- Completed: Added a single local provider capability verification gate that runs focused static request-shape, matrix-contract, reasoning-mapping, and dry-run-gate unittest groups, then runs the secret-free provider capability dry-run matrix and compares current non-pass results against a tracked baseline of accepted preview blockers and conflicting capability cases. Documented the single-command entrypoint in the runbook and persisted machine-readable gate reports plus command logs under `PRIVATE/agentic-update-pipeline/runs/`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate.py`; `apps/astrabridge-sidecar/astrabridge_sidecar/provider_capability_verification_gate_baseline.json`; `apps/astrabridge-sidecar/tests/test_provider_capability_verification_gate.py`; `scripts/run_provider_capability_verification_gate.py`; `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python scripts\run_provider_capability_verification_gate.py --run-id step17-provider-capability-gate-20260706` from `D:\AstraBridge`, which passed and wrote summary/report artifacts under `PRIVATE/agentic-update-pipeline/runs/step17-provider-capability-gate-20260706/` plus dry-run artifacts under `PRIVATE/agentic-update-pipeline/runs/step17-provider-capability-gate-20260706-dry-run/`; ran `python -m unittest tests.test_provider_capability_verification_gate` from `D:\AstraBridge\apps\astrabridge-sidecar`, passing; and ran `git diff --check -- D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\provider_capability_verification_gate.py D:\AstraBridge\apps\astrabridge-sidecar\astrabridge_sidecar\provider_capability_verification_gate_baseline.json D:\AstraBridge\apps\astrabridge-sidecar\tests\test_provider_capability_verification_gate.py D:\AstraBridge\scripts\run_provider_capability_verification_gate.py D:\AstraBridge\docs\PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` with a clean result.
- Blockers: None.
- Next step: Step 18, Completion Audit And Final Handoff.

### 2026-07-06 - Step 18

- Completed: Performed a current-state completion audit against the plan deliverables, rewrote the final evidence summary as a durable report, re-ran the provider capability verification gate and the capability-routes frontend validation, verified the final live/dry-run artifact paths still exist, and confirmed focused secret scans pass over the plan, runbook, reports, and gate artifacts. Marked the execution plan complete and recorded the future maintenance entrypoint.
- Files changed: `PRIVATE/agentic-update-pipeline/reports/step18-completion-audit-20260706.md`; `PLAN/PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md`.
- Validation: Ran `python scripts\run_provider_capability_verification_gate.py --run-id step18-provider-capability-gate-20260706` from `D:\AstraBridge`, passing and writing final gate artifacts under `PRIVATE/agentic-update-pipeline/runs/step18-provider-capability-gate-20260706/`; ran `npm.cmd test -- --run src/features/capabilities/CapabilityRoutesPanel.test.tsx` and `node .\node_modules\typescript\bin\tsc --noEmit` from `D:\AstraBridge\apps\astrabridge-desktop`, both passing; verified final evidence-path existence for the Step 1 through Step 14 reports plus Step 13 live smoke and Step 18 gate artifacts; ran a focused PCRE2 secret scan over the execution plan, matrix contract, runbook, Step 1 through Step 14 reports, Step 18 gate summaries, Step 13 live-smoke summary, and the Step 18 completion-audit report with no matches; and ran `git diff --check -- D:\AstraBridge\PRIVATE\agentic-update-pipeline\reports\step18-completion-audit-20260706.md D:\AstraBridge\PLAN\PROVIDER_MODEL_CAPABILITY_REASONING_VALIDATION_EXECUTION_PLAN.md` with a clean result.
- Blockers: None.
- Next step: Future maintenance should start with `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` and `python scripts\run_provider_capability_verification_gate.py --run-id provider-capability-gate-YYYYMMDD`.
