# Provider And Model Compatibility Execution Plan

## Total Objective

Bring AstraBridge from "core provider/model adaptation exists with partial real validation" to a disciplined compatibility system where users can switch models and providers within the same task with predictable behavior, explicit capability boundaries, provider-specific pitfalls recorded, and fast adaptation paths for model upgrades or new providers.

This plan focuses on provider/model compatibility, context-window handling, tool/edit behavior such as `apply_patch`, reasoning/thinking normalization, same-task handoff, redacted provider validation, and UI observability. It does not reintroduce official OpenAI account login; OpenAI-compatible testing may use the existing Yunwu profile unless the user explicitly authorizes a different provider key path.

## Deliverables

- A provider/model compatibility matrix that is generated or checked against runtime profile/catalog data.
- Hardened runtime contracts for capabilities, context budgets, reasoning policies, tool schemas, `apply_patch`, and provider handoff.
- Real provider validation evidence for the current managed vault providers: Yunwu/OpenAI-compatible, DeepSeek, Qwen, Kimi, and GLM.
- UI surfaces that expose provider readiness, compatibility status, switching/handoff state, and validation warnings without leaking secrets.
- A future-provider onboarding and model-upgrade runbook with a small, repeatable smoke gate.

## Constraints And Attention Notes

1. Preserve experiment artifacts, raw call records, validation reports, screenshots, logs, and parsed outputs by default. Do not clean them unless the user explicitly names cleanup targets.
2. Never persist API keys, bearer tokens, cookies, authorization headers, vault passwords, admin session tokens, provider raw secrets, or desktop `key.txt` contents.
3. Provider-backed smoke tests must be explicit, redacted, and recorded as sanitized evidence only. Do not write grading or validation results back to external platforms.
4. Current product project state remains `.abproj` plus workspace-local `.astrabridge/`; do not reintroduce `.lcr*`, `.codexproj`, `.codex-shell`, or official OpenAI login as supported product paths.
5. Treat web search as a standalone web lane unless the user explicitly asks to merge it into model-backed provider capabilities.
6. Favor existing AstraBridge profile, catalog, transport, router, runtime, task, and UI patterns over new abstractions.
7. Use the `astra` managed vault only through app/sidecar surfaces that keep secrets redacted.
8. For app work, verify visual changes in the in-app browser when feasible and preserve screenshots under `PRIVATE/**`.

## Adjustment Policy

Agents may reasonably adjust specific substeps, implementation details, filenames, commands, or sequencing when evidence from the workspace requires it. Such adjustments must not change the total objective, lower the planned difficulty, remove provider-backed validation gates, remove secret-redaction requirements, or replace compatibility work with cosmetic UI-only work. If a core objective becomes infeasible, record the blocker, evidence, attempted approaches, and a substitute path that preserves the original intent.

## Execution Rules

1. Each user-facing execution round should complete exactly one numbered step from this plan unless the user explicitly asks otherwise.
2. Start from the earliest numbered step whose status is not `completed`, unless the user redirects to a specific step.
3. Each round must update this plan before stopping.
4. A step can be marked `completed` only when all of its acceptance criteria are met.
5. If blocked, mark the step `blocked`, record the concrete blocker and next entry point, and do not leave vague continuation notes.
6. Each round must end with a handoff summary: completed work, files changed, validation run, blockers, and the exact next step.

## Current Progress

- Current status: Completed
- Completed steps: 0. Create Durable Plan; 1. Baseline Compatibility Inventory; 2. Compatibility Matrix Contract; 3. Profile And Catalog Source-Of-Truth Cleanup; 4. Transport And Adapter Boundary Consolidation; 5. Reasoning And Thinking Policy Normalization; 6. Tool Calls And Apply Patch Compatibility; 7. Context Window And Compact Gate; 8. Same-Task Provider Handoff Hardening; 9. Unified Smoke Runner And Evidence Format; 10. Real Provider Text And Code-Agent Validation; 11. Cross-Provider Switch And Fallback Validation; 12. Multimodal And Capability Route Validation; 13. UI Observability And Screenshot Workflow; 14. Documentation, Pitfall Ledger, And Onboarding Runbook; 15. Final Gate And Release Readiness Review
- Current step: Complete
- Next step: None; follow the final report's recommended next execution slice for residual partial lanes.
- Last updated: 2026-07-05

## Execution Steps

### 0. Create Durable Plan

Goal: Create this durable 15-step execution plan and make the next entry point clear.

Main actions:

- Define the total objective, constraints, adjustment policy, execution rules, deliverables, and 15 implementation/validation steps.
- Record the current environment facts needed for handoff without storing secrets.
- Set the first executable step as the next entry point.

Acceptance criteria:

- Plan file exists on disk.
- Plan includes total objective, deliverables, constraints, adjustment policy, execution rules, current progress, 15 numbered steps, acceptance criteria for every step, and a progress log.
- Next step is clearly identified.

Status: completed

### 1. Baseline Compatibility Inventory

Goal: Produce a fresh, source-backed inventory of current provider/model compatibility behavior and gaps.

Main actions:

- Read the current provider profiles, registry, model catalog contract, transports, router adapter selection, context budget code, handoff/history projection code, and existing evidence records.
- Compare code behavior with the previous research conclusion: partial foundation, uneven validation, context/compact gaps, handoff gaps, Kimi instability, and Yunwu/OpenAI-compatible status.
- Record a concise inventory under `PRIVATE/provider-compatibility/` or a suitable report path with no secrets.

Acceptance criteria:

- Inventory report lists current providers, models, protocols, reasoning policy, edit/tool policy, context-window settings, smoke status, and known pitfalls.
- Report cites the source files and existing evidence records used.
- Report explicitly identifies stale, missing, or duplicated compatibility paths such as router inline adapters versus transport modules.

Status: completed

### 2. Compatibility Matrix Contract

Goal: Define the durable compatibility matrix schema that future code, UI, and validation can share.

Main actions:

- Design matrix fields for provider, model, protocol, context window, compact behavior, reasoning/thinking mode, tool-call support, `apply_patch` type, parallel tools, vision, image/audio capability links, web lane status, token usage, authority tier, smoke status, and known pitfalls.
- Decide which fields are source-of-truth from profile/catalog data and which fields are validation-derived.
- Add or update tests for matrix serialization and redaction behavior if code changes are needed.

Acceptance criteria:

- Matrix schema is documented in a repo file or code docstring.
- Schema separates declared capability, runtime-normalized contract, and validated evidence.
- Secret-bearing fields are excluded by design.

Status: completed

### 3. Profile And Catalog Source-Of-Truth Cleanup

Goal: Make provider profiles and model catalog metadata line up cleanly with the compatibility matrix.

Main actions:

- Audit `ProviderProfile`, registry defaults, generated catalog fields, and effective catalog responses.
- Fill missing or ambiguous metadata for Yunwu/OpenAI-compatible, DeepSeek, Qwen, Kimi, and GLM.
- Ensure OpenAI-compatible behavior can be represented through Yunwu without reviving official OpenAI account login.

Acceptance criteria:

- Provider/catalog data can populate the matrix without ad hoc inference for the current five managed providers.
- Tests or focused assertions cover key fields: context window, auto compact, reasoning policy, tool policy, apply-patch type, and web capability.
- Effective catalog remains redacted and only exposes key availability, not key material.

Status: completed

### 4. Transport And Adapter Boundary Consolidation

Goal: Reduce behavior drift between legacy inline router adapters and provider transport modules.

Main actions:

- Audit `_adapter_for` and transport classes for duplicate provider-specific logic.
- Move or centralize provider quirks where appropriate without broad refactors.
- Preserve existing external behavior while making transport ownership explicit.

Acceptance criteria:

- Provider-specific request/response mapping has a clear owner for each current provider.
- Duplicate logic is either removed, commented as legacy fallback, or covered by tests that prevent divergence.
- Router adapter selection still works for all current providers.

Status: completed

### 5. Reasoning And Thinking Policy Normalization

Goal: Make reasoning/thinking parameters predictable across OpenAI-compatible Responses, Qwen, DeepSeek, Kimi, and GLM.

Main actions:

- Verify mapping for `reasoning_effort`, `enable_thinking`, `reasoning_content`, GLM reasoning controls, and Kimi thinking behavior.
- Normalize unsupported effort names before they reach Codex runtime or upstream providers.
- Record provider-specific restrictions such as DeepSeek thinking temperature behavior and Qwen temperature omission.

Acceptance criteria:

- Unit tests cover effort normalization for each current provider.
- Real or dry-run preview evidence shows outbound payloads omit or transform incompatible fields.
- The matrix records whether reasoning state is replayable, visible-summary-only, or provider-private.

Status: completed

### 6. Tool Calls And Apply Patch Compatibility

Goal: Harden tool-call and edit behavior so models with different tool habits can still participate safely.

Main actions:

- Audit tool schema policy, tool call repair, model authority tiers, parallel tool behavior, and `apply_patch` type normalization.
- Add focused tests for `json` to Codex `freeform` apply-patch mapping, malformed tool args, duplicate tool call IDs, orphan tool results, and unverified parallel calls.
- Record provider-specific tool-call limitations in the compatibility matrix.

Acceptance criteria:

- Tool-call repair tests cover the known failure shapes.
- Apply-patch compatibility is represented consistently in catalog/runtime output.
- Models without verified structured tool calls are prevented from being treated as fully autonomous edit agents.

Status: completed

### 7. Context Window And Compact Gate

Goal: Move context-window support from rough budgeting toward an observable compatibility gate.

Main actions:

- Audit context budget estimation, project context pack generation, runtime config emission, tool-output token limits, and router context-limit behavior.
- Define provider/model-specific effective context limits and compact thresholds.
- Add tests or smoke fixtures for context budget reports, auto-compact status, tool-output truncation, and context-limit error handling.

Acceptance criteria:

- Matrix records declared context, effective context, compact threshold, and compact validation status.
- Router/runtime behavior clearly distinguishes "budgeted before send" from "provider rejected context".
- Known `configured_unverified` and `untested` statuses are either validated or explicitly preserved as warnings.

Status: completed

### 8. Same-Task Provider Handoff Hardening

Goal: Make model/provider switching within one user-visible task predictable and auditable.

Main actions:

- Audit task handoff detection, provider-thread creation/reuse, history projection, provider-private reasoning stripping, and UI conversation merge behavior.
- Add test coverage for same-task handoff across providers with text, tool calls, and private reasoning artifacts.
- Ensure handoff summaries include enough context without leaking provider-private state.

Acceptance criteria:

- Handoff tests cover at least one successful same-task switch and one projection warning path.
- Private provider keys, opaque reasoning, response IDs, and signatures are not replayed across incompatible providers.
- UI/API state makes the active provider lane and previous lane understandable.

Status: completed

### 9. Unified Smoke Runner And Evidence Format

Goal: Provide one repeatable smoke path for dry-run and provider-backed compatibility validation.

Main actions:

- Design or update a smoke runner that can execute dry-run previews and authorized provider-backed checks.
- Standardize sanitized request metadata, sanitized response metadata, usage signals, warnings, artifacts, and result status.
- Ensure evidence lands under `PRIVATE/**` and is scan-friendly.

Acceptance criteria:

- Smoke runner supports current managed providers without exposing raw secrets.
- Results can update or feed the compatibility matrix.
- Evidence format records pass, fail, partial, skipped, and blocked with concrete reasons.

Status: completed

### 10. Real Provider Text And Code-Agent Validation

Goal: Validate the core text/code-agent path for current priority providers.

Main actions:

- Run authorized provider-backed short text and code-agent smoke tasks through Yunwu/OpenAI-compatible, DeepSeek, Qwen, Kimi, and GLM.
- Capture sanitized raw call records, parsed outputs, warnings, usage signals, and UI/runtime state.
- Reproduce known weak spots such as Kimi stale system error or no-output behavior if still present.

Acceptance criteria:

- Each provider has a current pass/fail/partial/skipped record with evidence.
- Failures include provider, model, route, prompt class, observed behavior, and next fix target.
- No raw key, bearer token, cookie, authorization header, or vault password appears in evidence.

Status: completed

### 11. Cross-Provider Switch And Fallback Validation

Goal: Validate switching and fallback behavior beyond the simple successful handoff path.

Main actions:

- Run same-task provider switches across at least GLM to Qwen, DeepSeek to Yunwu, and one Kimi-involved path if safe.
- Add failure cases for missing key, auth failure, provider timeout, unsupported model, unsupported tool, and context-limit rejection.
- Confirm UI and API surfaces show actionable warnings and safe recovery choices.

Acceptance criteria:

- Evidence covers successful handoff, failed handoff, and fallback recommendation paths.
- Same-task conversation continuity is preserved where intended.
- Failures do not leak raw provider errors that contain secrets.

Status: completed

### 12. Multimodal And Capability Route Validation

Goal: Validate non-text capabilities without mixing them incorrectly into model-backed chat compatibility.

Main actions:

- Validate vision, image generation, speech transcription, speech synthesis, and standalone web search lanes according to their current architecture.
- Preserve known provider-specific pitfalls such as Qwen ASR audio-only content and Yunwu image artifact handling.
- Ensure capability route status can feed the compatibility matrix as linked capability evidence, not as generic chat capability.

Acceptance criteria:

- Current capability route evidence exists for each enabled route or records why it is skipped.
- Artifacts are preserved under `PRIVATE/**` with sanitized manifests.
- Web search remains a standalone web lane unless explicitly changed by the user.

Status: completed

### 13. UI Observability And Screenshot Workflow

Goal: Make compatibility state inspectable in the AstraBridge app and easy to verify visually.

Main actions:

- Identify the best UI surfaces for provider readiness, model compatibility matrix, smoke status, active lane, handoff history, and warnings.
- Implement focused UI updates consistent with the existing brand and settings/runtime layout.
- Use the in-app browser to capture before/after screenshots for the relevant surfaces.

Acceptance criteria:

- UI shows compatibility state without exposing raw secrets.
- Provider switching, current route, and validation warnings are visible enough for diagnosis.
- Screenshot evidence is preserved under `PRIVATE/**` and referenced in the progress log.

Status: completed

### 14. Documentation, Pitfall Ledger, And Onboarding Runbook

Goal: Convert validation results and provider quirks into durable documentation.

Main actions:

- Update or create docs that explain provider-specific behavior, known pitfalls, validation status, and how to add or upgrade a provider/model.
- Include a compatibility pitfall ledger for Qwen, DeepSeek, Kimi, GLM, and Yunwu/OpenAI-compatible behavior.
- Document the minimal smoke gate for future provider onboarding.

Acceptance criteria:

- Documentation links to the compatibility matrix and sanitized evidence.
- Each current provider has at least one recorded pitfall or an explicit "none observed in this pass" entry.
- New provider onboarding steps are concrete enough for a future agent to execute without reconstructing context from chat.

Status: completed

### 15. Final Gate And Release Readiness Review

Goal: Decide whether AstraBridge can claim provider/model switching is sufficiently adapted, and record remaining limits.

Main actions:

- Run the final local test suite and selected provider-backed smoke checks authorized for this plan.
- Run secret scans over changed files and preserved evidence paths.
- Produce a final readiness report with pass/fail status, residual risks, and next recommended execution slice if needed.

Acceptance criteria:

- Tests, smoke evidence, UI screenshots, matrix output, and docs are internally consistent.
- Secret scan passes for changed files and relevant evidence paths.
- Final report states whether compatibility is sufficient, partially sufficient, or not yet sufficient, with precise reasons.

Status: completed

## Progress Log

### 2026-07-04 - Step 0

- Completed: Created the durable 15-step provider/model compatibility execution plan.
- Files changed: `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Confirmed sidecar health on `127.0.0.1:8790`, confirmed `astra` managed vault is unlocked with five active provider keys via redacted session data, and opened the AstraBridge app in the in-app browser at `http://127.0.0.1:4181/?sidecar=http%3A%2F%2F127.0.0.1%3A8790`.
- Blockers: None for the plan. The in-app browser control initially timed out once, then recovered and opened the app.
- Next step: Step 1, Baseline Compatibility Inventory.

### 2026-07-04 - Step 1

- Completed: Produced a fresh baseline compatibility inventory from current source, current local runtime state, and existing redacted validation evidence.
- Files changed: `PRIVATE/provider-compatibility/reports/step1-baseline-compatibility-inventory-20260704.md`, `PRIVATE/provider-compatibility/raw/step1-baseline-compatibility-inventory-20260704.json`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Confirmed the JSON summary parses, confirmed the report references current code and evidence paths, and ran a focused secret-pattern scan over `PRIVATE/provider-compatibility/` with no matches.
- Blockers: None. The baseline already exposed concrete next-step work, including Kimi catalog/runtime drift, transport duplication, thin official OpenAI evidence, and universal `configured_unverified` compact status.
- Next step: Step 2, Compatibility Matrix Contract.

### 2026-07-04 - Step 2

- Completed: Defined the durable provider/model compatibility matrix contract in both human-readable and code-consumable form.
- Files changed: `PLAN/PROVIDER_MODEL_COMPATIBILITY_MATRIX_CONTRACT.md`, `apps/astrabridge-sidecar/astrabridge_sidecar/provider_model_compatibility_matrix.py`, `apps/astrabridge-sidecar/tests/test_provider_model_compatibility_matrix.py`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_provider_model_compatibility_matrix`, `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\provider_model_compatibility_matrix.py`, and `git diff --check` from `apps/astrabridge-sidecar` / repo root; all passed after tightening the secret-field filter so `secret_free` metadata is allowed while real secret-bearing fields are still rejected.
- Blockers: None. The contract now gives the next steps a fixed target shape for declared capability, runtime-normalized contract, and validated evidence.
- Next step: Step 3, Profile And Catalog Source-Of-Truth Cleanup.

### 2026-07-04 - Step 3

- Completed: Cleaned up provider/model source-of-truth resolution so generated catalog defaults stay authoritative for built-in model ranking while runtime evidence fields still override where appropriate, and added a provider-level contract helper for matrix population without ad hoc inference.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/llm_api_manager_service.py`, `apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_provider_catalog_contract tests.test_provider_model_compatibility_matrix`, `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\model_catalog\catalog.py astrabridge_sidecar\llm_api_manager_service.py astrabridge_sidecar\provider_model_compatibility_matrix.py`, and `git diff --check`. Also evaluated the live local AstraBridge state through `resolved_provider_source_of_truth_fields(...)`, which now reports `kimi` as `configured_default_model=kimi-k2.6` but `effective_default_model=kimi-k2.7-code` with `default_model_alignment=stale_config`, while the other four managed providers remain aligned.
- Blockers: None for this step. The cleanup intentionally surfaces stale configured defaults instead of silently rewriting user/provider state, so the next steps can decide where transport/runtime ownership should absorb or present those warnings.
- Next step: Step 4, Transport And Adapter Boundary Consolidation.

### 2026-07-04 - Step 4

- Completed: Consolidated active transport ownership into an explicit transport registry and made router adapter selection instantiate transports from that registry instead of maintaining provider-family branches in `RouterService`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py`, `apps/astrabridge-sidecar/tests/test_router_transport_registry.py`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_router_transport_registry tests.test_provider_catalog_contract tests.test_provider_model_compatibility_matrix`, `.\.venv\Scripts\python.exe -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_qwen_transport_normalizes_reasoning_state_without_raw_payload_leak tests.test_sidecar_services.AstraBridgeServiceTests.test_kimi_adapter_keeps_thinking_for_visual_micro_check_with_large_output_window tests.test_sidecar_services.AstraBridgeServiceTests.test_deepseek_adapter_uses_adapter_profile_not_exact_provider_id tests.test_sidecar_services.AstraBridgeServiceTests.test_yunwu_transport_normalizes_response_without_raw_payload_leak`, `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\router_service.py astrabridge_sidecar\providers\transports\__init__.py`, and `git diff --check`. The new registry tests prove explicit owners for Qwen, DeepSeek, Kimi, GLM, and the OpenAI-compatible wire-api fallbacks; the existing provider behavior tests still pass after routing through the registry.
- Blockers: None for this step. Legacy inline adapters still exist as commented historical fallback reference in `router_service.py`, but the active path is now owned by `providers/transports`, and tests guard the selection boundary so behavior drift cannot happen silently.
- Next step: Step 5, Reasoning And Thinking Policy Normalization.

### 2026-07-04 - Step 5

- Completed: Normalized reasoning/thinking policy handling across the current managed providers so Codex/runtime effort values are canonicalized before request build, provider-specific thinking controls resolve from one shared policy layer, and matrix/runtime contract output now records reasoning-state visibility and replayability explicitly.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/reasoning_policy.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/profile.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/profile_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/provider_model_compatibility_matrix.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/base.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/qwen_dashscope.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/deepseek.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/moonshot_kimi.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/zai_glm.py`, `apps/astrabridge-sidecar/tests/test_reasoning_policy_normalization.py`, `apps/astrabridge-sidecar/tests/test_model_catalog_contract.py`, `apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`, `apps/astrabridge-sidecar/tests/test_provider_model_compatibility_matrix.py`, `PRIVATE/provider-compatibility/raw/step5-reasoning-normalization-preview-20260704.json`, `PRIVATE/provider-compatibility/reports/step5-reasoning-normalization-preview-20260704.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_reasoning_policy_normalization tests.test_model_catalog_contract tests.test_provider_catalog_contract tests.test_provider_model_compatibility_matrix tests.test_router_transport_registry`, `.\.venv\Scripts\python.exe -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_qwen_adapter_maps_effort_to_enable_thinking tests.test_sidecar_services.AstraBridgeServiceTests.test_deepseek_adapter_converts_chat_completion_to_response tests.test_sidecar_services.AstraBridgeServiceTests.test_kimi_adapter_keeps_explicit_deep_visual_reasoning tests.test_sidecar_services.AstraBridgeServiceTests.test_glm_chat_transport_normalizes_reasoning_notice_without_raw_payload_leak tests.test_sidecar_services.AstraBridgeServiceTests.test_yunwu_transport_normalizes_response_without_raw_payload_leak`, `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\providers\transports\base.py astrabridge_sidecar\reasoning_policy.py astrabridge_sidecar\router_service.py astrabridge_sidecar\model_catalog\catalog.py`, and `git diff --check`. Rechecked the preserved Step 5 dry-run evidence and ran a focused secret-pattern scan over `PRIVATE/provider-compatibility/raw/step5-reasoning-normalization-preview-20260704.json` and `PRIVATE/provider-compatibility/reports/step5-reasoning-normalization-preview-20260704.md` with no matches.
- Blockers: None for this step. The dry-run evidence is sufficient for policy normalization, but provider-backed validation still belongs to later smoke and real-provider steps.
- Next step: Step 6, Tool Calls And Apply Patch Compatibility.

### 2026-07-04 - Step 6

- Completed: Hardened the structured tool-call path so malformed arguments, duplicate or missing tool call IDs, orphan tool results, and serial-only fallback are covered by direct tests; normalized `apply_patch` mapping now stays explicit in runtime status and written catalog output; and native-kernel tier `B` models now stay on a preview-only tool surface instead of receiving direct apply/execute tools.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/model_authority.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/providers/tooling/__init__.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/router_config_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/coding_kernel/turn_loop.py`, `apps/astrabridge-sidecar/tests/test_tool_call_compatibility.py`, `PRIVATE/provider-compatibility/raw/step6-tool-call-compatibility-preview-20260704.json`, `PRIVATE/provider-compatibility/reports/step6-tool-call-compatibility-preview-20260704.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_tool_call_compatibility tests.test_model_catalog_contract tests.test_provider_catalog_contract tests.test_router_transport_registry tests.test_reasoning_policy_normalization tests.test_sidecar_services.AstraBridgeServiceTests.test_model_authority_assessment_marks_propose_only_as_tier_b tests.test_sidecar_services.AstraBridgeServiceTests.test_native_kernel_tier_c_limits_tools_to_review_only tests.test_sidecar_services.AstraBridgeServiceTests.test_native_kernel_tier_c_rejects_checkpoint_and_edit_preview_execution tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_config_maps_json_apply_patch_to_codex_catalog_freeform tests.test_sidecar_services.AstraBridgeServiceTests.test_metadata_seed_import_and_effective_catalog_are_conservative`, `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\providers\tooling\model_authority.py astrabridge_sidecar\providers\tooling\__init__.py astrabridge_sidecar\router_config_service.py astrabridge_sidecar\model_catalog\catalog.py astrabridge_sidecar\runtime_config_service.py astrabridge_sidecar\coding_kernel\turn_loop.py tests\test_tool_call_compatibility.py`, and `git diff --check`. Rechecked the preserved Step 6 dry-run evidence and ran a focused secret-pattern scan over `PRIVATE/provider-compatibility/raw/step6-tool-call-compatibility-preview-20260704.json` and `PRIVATE/provider-compatibility/reports/step6-tool-call-compatibility-preview-20260704.md` with no matches.
- Blockers: None for this step. This round is dry-run and contract hardening only; provider-backed tool-call smoke and broader workflow validation remain for later validation steps.
- Next step: Step 7, Context Window And Compact Gate.

### 2026-07-04 - Step 7

- Completed: Turned the existing context budget and compaction hints into a clearer context gate by extending project-context budget reports with preflight budgeting and compaction-status fields, extending runtime/provider contracts with explicit declared/effective context and provider-rejection metadata, surfacing the same context limits in runtime status, and preserving current `configured_unverified` or `untested` compact states as explicit warnings in provider source-of-truth summaries.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/coding_kernel/context_budget.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/project_context_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/runtime_config_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/provider_model_compatibility_matrix.py`, `apps/astrabridge-sidecar/tests/test_context_gate_compatibility.py`, `apps/astrabridge-sidecar/tests/test_model_catalog_contract.py`, `apps/astrabridge-sidecar/tests/test_provider_catalog_contract.py`, `apps/astrabridge-sidecar/tests/test_provider_model_compatibility_matrix.py`, `PRIVATE/provider-compatibility/raw/step7-context-gate-preview-20260704.json`, `PRIVATE/provider-compatibility/reports/step7-context-gate-preview-20260704.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_context_gate_compatibility tests.test_tool_call_compatibility tests.test_model_catalog_contract tests.test_provider_catalog_contract tests.test_provider_model_compatibility_matrix tests.test_router_transport_registry tests.test_reasoning_policy_normalization`, `.\.venv\Scripts\python.exe -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_config_maps_json_apply_patch_to_codex_catalog_freeform tests.test_sidecar_services.AstraBridgeServiceTests.test_metadata_seed_import_and_effective_catalog_are_conservative tests.test_sidecar_services.AstraBridgeServiceTests.test_model_authority_assessment_marks_propose_only_as_tier_b tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_config_collaboration_and_compaction_metadata tests.test_sidecar_services.AstraBridgeServiceTests.test_project_context_snapshot_reports_ordered_sections_and_budget tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_project_context_budget_report_changes_with_target_model tests.test_sidecar_services.AstraBridgeServiceTests.test_task_provider_handoff_carries_context_budget_report_into_transition_plan tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_supervisor_normalizes_context_limit_and_auth_failures`, `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\coding_kernel\context_budget.py astrabridge_sidecar\project_context_service.py astrabridge_sidecar\model_catalog\catalog.py astrabridge_sidecar\runtime_config_service.py astrabridge_sidecar\provider_model_compatibility_matrix.py tests\test_context_gate_compatibility.py tests\test_model_catalog_contract.py tests\test_provider_catalog_contract.py tests\test_provider_model_compatibility_matrix.py`, and `git diff --check`. Rechecked the preserved Step 7 dry-run evidence and ran a focused secret-pattern scan over `PRIVATE/provider-compatibility/raw/step7-context-gate-preview-20260704.json` and `PRIVATE/provider-compatibility/reports/step7-context-gate-preview-20260704.md` with no matches.
- Blockers: None for this step. This round hardened dry-run and contract visibility only; provider-backed long-context rejection and compact-quality smoke still belong to later validation steps.
- Next step: Step 8, Same-Task Provider Handoff Hardening.

### 2026-07-04 - Step 8

- Completed: Hardened same-task provider switching by recording source-lane route metadata directly on handoff events, adding a reusable `lane_state` view that exposes active and previous provider lanes without persisting extra runtime state, surfacing that view through compact task and task-conversation API outputs, and making the desktop task UI show the previous lane alongside the active lane while keeping cross-provider projection warnings secret-free.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/task_conversation_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/project_service.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_provider_handoff_compatibility.py`, `apps/astrabridge-sidecar/tests/test_project_sidebar.py`, `apps/astrabridge-desktop/src/types.ts`, `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.tsx`, `apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.test.tsx`, `apps/astrabridge-desktop/src/features/runtime/taskSummary.ts`, `apps/astrabridge-desktop/src/features/runtime/taskSummary.test.ts`, `PRIVATE/provider-compatibility/raw/step8-handoff-preview-20260704.json`, `PRIVATE/provider-compatibility/reports/step8-handoff-preview-20260704.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\task_service.py astrabridge_sidecar\task_conversation_service.py astrabridge_sidecar\project_service.py astrabridge_sidecar\server.py tests\test_provider_handoff_compatibility.py tests\test_project_sidebar.py`, `.\.venv\Scripts\python.exe -m unittest tests.test_provider_handoff_compatibility tests.test_project_sidebar`, `.\.venv\Scripts\python.exe -m unittest tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_reuses_existing_provider_thread_for_same_task_handoff tests.test_sidecar_services.AstraBridgeServiceTests.test_runtime_provider_handoff_uses_history_projection_summary_for_transition_diagnostics tests.test_sidecar_services.AstraBridgeServiceTests.test_task_conversation_includes_provider_handoff_as_event_only_turn tests.test_sidecar_services.AstraBridgeServiceTests.test_task_provider_handoff_carries_context_budget_report_into_transition_plan`, `node .\node_modules\vitest\vitest.mjs run src/features/navigation/ProjectTaskTree.test.tsx src/features/runtime/taskSummary.test.ts`, `node .\node_modules\typescript\bin\tsc --noEmit`, and `git diff --check`. Rechecked the preserved Step 8 dry-run evidence and ran a focused secret-pattern scan over `PRIVATE/provider-compatibility/raw/step8-handoff-preview-20260704.json` and `PRIVATE/provider-compatibility/reports/step8-handoff-preview-20260704.md` with no matches.
- Blockers: None for this step. The in-app browser dev entry also had to be reopened through a trusted `astrabridge_launch` URL during the turn so the current desktop UI could remain inspectable, but that did not block the compatibility work.
- Next step: Step 9, Unified Smoke Runner And Evidence Format.

### 2026-07-04 - Step 9

- Completed: Added a unified provider/model compatibility smoke runner that batches dry-run and explicitly authorized provider-backed cases, normalizes case statuses to `pass`, `fail`, `partial`, `skipped`, or `blocked`, writes sanitized evidence under `PRIVATE/provider-compatibility/runs/`, and emits matrix-update records that can feed the compatibility matrix. Added a sidecar endpoint for the same runner at `/api/runtime/provider-compatibility-smoke`.
- Files changed: `apps/astrabridge-sidecar/astrabridge_sidecar/provider_compatibility_smoke.py`, `apps/astrabridge-sidecar/astrabridge_sidecar/server.py`, `apps/astrabridge-sidecar/tests/test_provider_compatibility_smoke.py`, `PRIVATE/provider-compatibility/runs/step9-unified-smoke-20260704/summary.json`, `PRIVATE/provider-compatibility/runs/step9-unified-smoke-20260704/report.md`, `PRIVATE/provider-compatibility/runs/step9-unified-smoke-20260704/cases/`, `PRIVATE/provider-compatibility/raw/step9-unified-smoke-preview-20260704.json`, `PRIVATE/provider-compatibility/reports/step9-unified-smoke-preview-20260704.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `.\.venv\Scripts\python.exe -m unittest tests.test_provider_compatibility_smoke tests.test_capability_smoke tests.test_provider_model_compatibility_matrix`, `.\.venv\Scripts\python.exe -m py_compile astrabridge_sidecar\provider_compatibility_smoke.py astrabridge_sidecar\server.py tests\test_provider_compatibility_smoke.py`, and `git diff --check`. Generated Step 9 fixture evidence covering `pass`, `partial`, `skipped`, and `blocked`, while unit tests also cover provider `fail`. Ran a focused secret-pattern scan over the Step 9 run, raw preview, and report paths with no matches.
- Blockers: None for this step. The generated Step 9 provider cases use a fake runtime by design; real provider-backed text/code-agent validation remains the Step 10 entry point.
- Next step: Step 10, Real Provider Text And Code-Agent Validation.

### 2026-07-04 - Step 10

- Completed: Ran authorized provider-backed short-text health smoke and runtime code-agent smoke through the managed `astra` vault for Yunwu/OpenAI-compatible, DeepSeek, Qwen, Kimi, and GLM. Text smoke passed for all five providers. Code-agent smoke passed for Yunwu, DeepSeek, and Qwen; GLM completed the turn but did not execute the requested shell command and is recorded as partial; Kimi failed before tool execution because Moonshot rejected the current shell tool JSON schema.
- Files changed: `PRIVATE/provider-compatibility/runs/step10-real-provider-text-code-agent-20260704/summary.json`, `PRIVATE/provider-compatibility/runs/step10-real-provider-text-code-agent-20260704/cases/`, `PRIVATE/provider-compatibility/raw/step10-real-provider-text-code-agent-20260704.json`, `PRIVATE/provider-compatibility/reports/step10-real-provider-text-code-agent-20260704.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Confirmed the sidecar was running from current source, confirmed the `astra` managed vault session was unlocked with five enabled provider keys through redacted sidecar endpoints, ran `/api/llm-manager/keys/test` for all five providers, ran `/api/runtime/turns/start` code-agent smoke turns with `context_mode=no_context`, reconciled runtime events for command execution and turn terminal status, ran `.\.venv\Scripts\python.exe -m unittest tests.test_provider_compatibility_smoke tests.test_provider_handoff_compatibility tests.test_tool_call_compatibility`, and ran `git diff --check`. Ran a focused secret-pattern scan over the Step 10 run, raw JSON, and Markdown report paths with no matches.
- Blockers: None for this step. Real validation found two compatibility follow-ups: Kimi/Moonshot needs shell-tool schema normalization because it rejected `tools.function.parameters` where `required` referenced `command` outside `properties`; GLM needs tool-use behavior verification because it completed the runtime turn and returned the expected JSON without a command execution event.
- Next step: Step 11, Cross-Provider Switch And Fallback Validation.

### 2026-07-05 - Step 11

- Completed: Ran provider-backed same-task switching evidence for GLM -> Qwen and DeepSeek -> Yunwu, preserving the provider handoff events, target lane continuity, and context projection warnings. Preserved Qwen -> Kimi as failed handoff evidence because the Kimi target lane failed after the handoff, matching the known Kimi compatibility risk. Added fallback recommendation evidence for missing key, auth failure, provider timeout, unsupported model, unsupported tool, and context-limit rejection.
- Files changed: `PRIVATE/provider-compatibility/runs/step11-cross-provider-switch-fallback-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step11-cross-provider-switch-fallback-20260705/cases/`, `PRIVATE/provider-compatibility/raw/step11-cross-provider-switch-fallback-20260705.json`, `PRIVATE/provider-compatibility/reports/step11-cross-provider-switch-fallback-20260705.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran real `/api/runtime/threads/create` and `/api/runtime/turns/start` calls through the managed `astra` vault for the switch cases; confirmed the DeepSeek -> Yunwu retry completed after the runtime switch pin expired; ran `.\.venv\Scripts\python.exe -m unittest tests.test_provider_handoff_compatibility tests.test_provider_compatibility_smoke tests.test_tool_call_compatibility`; ran `git diff --check`; and ran a focused secret-pattern scan over the Step 11 run, raw JSON, and Markdown report paths with no matches.
- Blockers: None for this step. Residual follow-ups remain for later steps: Kimi still needs schema/tool-surface normalization before it can be treated as a reliable handoff target, and the runtime switch pin behavior should be made more visible in UI recovery guidance.
- Next step: Step 12, Multimodal And Capability Route Validation.

### 2026-07-05 - Step 12

- Completed: Validated the capability route layer separately from model-backed chat routing. Route contract evidence now covers `image.generate`, `vision.analyze`, `speech.transcribe`, `speech.synthesize`, and `web.search`; provider-backed smoke ran for the four model-backed capabilities; and standalone web lane evidence persisted a research record through `/api/tools/web/research-brief` with `web.search` confirmed as `web_standalone` and `model_routing_enabled=false`.
- Files changed: `PRIVATE/provider-compatibility/step12_capability_validation_runner.py`, `PRIVATE/provider-compatibility/runs/step12-multimodal-capability-routes-20260705/summary.json`, `PRIVATE/provider-compatibility/runs/step12-multimodal-capability-routes-20260705/cases/`, `PRIVATE/provider-compatibility/raw/step12-multimodal-capability-routes-20260705.json`, `PRIVATE/provider-compatibility/reports/step12-multimodal-capability-routes-20260705.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe D:\AstraBridge\PRIVATE\provider-compatibility\step12_capability_validation_runner.py`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m unittest tests.test_capability_smoke tests.test_capability_routes tests.test_capability_specs tests.test_capability_mcp_server tests.test_web_lane`; ran `D:\AstraBridge\apps\astrabridge-sidecar\.venv\Scripts\python.exe -m py_compile D:\AstraBridge\PRIVATE\provider-compatibility\step12_capability_validation_runner.py`; ran `git diff --check`; and ran a focused secret-pattern scan over the Step 12 run, raw JSON, Markdown report, and runner with no matches after eliminating scan-pattern false positives.
- Blockers: None for this step. The Step 12 evidence is intentionally `partial`: Qwen vision and Qwen ASR provider smoke passed; Yunwu image generation invoked and normalized a response but failed artifact persistence because the returned artifact ref had no local path; Qwen TTS failed with a sanitized upstream 400 from the DashScope chat completions endpoint. These are recorded compatibility pitfalls for the documentation and final readiness steps.
- Next step: Step 13, UI Observability And Screenshot Workflow.

### 2026-07-05 - Step 13

- Completed: Made the existing multimodal capability routes panel diagnose provider/model compatibility at a glance. The panel now shows a compatibility snapshot for resolved routes, verified model-backed smoke evidence, warning count, and standalone web lane state; each route now has a compact diagnostic strip for missing routes, credential readiness, unverified or failed smoke, missing catalog metadata, and standalone web separation. No raw secrets are displayed; only provider/model IDs, env-var names already surfaced as redacted credential state, and route/smoke status are shown.
- Files changed: `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.tsx`, `apps/astrabridge-desktop/src/features/capabilities/CapabilityRoutesPanel.test.tsx`, `apps/astrabridge-desktop/src/features/i18n/catalog.ts`, `apps/astrabridge-desktop/src/styles.css`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Screenshot evidence: Preserved `PRIVATE/provider-compatibility/screenshots/step13-ui-observability-20260705/playwright-capabilities-page.png` as the accepted capability UI evidence. Additional navigation/context screenshots were preserved in the same directory: `playwright-current-page.png`, `playwright-settings-page.png`, and `playwright-models-page.png`.
- Validation: Ran `npm.cmd test -- --run src/features/capabilities/CapabilityRoutesPanel.test.tsx` from `apps/astrabridge-desktop` with 12 tests passing; ran `node .\node_modules\typescript\bin\tsc --noEmit`; ran `git diff --check` over the Step 13 UI files and plan; opened the local app through Playwright at `http://127.0.0.1:4181/?sidecar=http%3A%2F%2F127.0.0.1%3A8790&astrabridge_launch=dogfood`, navigated through Tools -> Multimodal capability routes, and confirmed the page contains `兼容性快照`, `多模态能力路由`, and `诊断警告`. Ran a strict focused secret-pattern scan over the changed UI files and Step 13 screenshot directory with no matches.
- Blockers: No product blocker. The in-app browser backend could be discovered, but `browser.tabs.list()` timed out twice during this round, so the preserved screenshot evidence was captured with the repository's installed Playwright browser rather than the in-app tab API.
- Next step: Step 14, Documentation, Pitfall Ledger, And Onboarding Runbook.

### 2026-07-05 - Step 14

- Completed: Added a durable provider/model compatibility runbook and pitfall ledger. The document links the matrix contract, current execution plan, Step 1 baseline, Step 10 real text/code-agent evidence, Step 11 handoff/fallback evidence, Step 12 capability evidence, Step 13 screenshot evidence, and Step 9 unified smoke format. It records provider-specific pitfalls for Yunwu/OpenAI-compatible, DeepSeek, Qwen, Kimi, and GLM, and defines the minimum onboarding/model-upgrade gate for source/catalog metadata, reasoning/tool contracts, context and handoff, unified provider smoke, text/code-agent, capability lanes, UI observability, and secret scanning.
- Files changed: `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Confirmed referenced matrix/evidence/screenshot paths exist; verified the runbook contains the five provider ledger sections, the current evidence index, the minimal smoke gate, and the status promotion checklist; ran `rg --pcre2` secret-pattern scan over `docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md` with no matches; ran `git diff --check -- docs/PROVIDER_MODEL_COMPATIBILITY_RUNBOOK.md PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`.
- Blockers: None. The runbook intentionally preserves current partial statuses instead of promoting them: Yunwu image artifact persistence, Qwen TTS, Kimi code-agent/schema and handoff target reliability, GLM command execution, and official OpenAI direct evidence remain final readiness considerations.
- Next step: Step 15, Final Gate And Release Readiness Review.

### 2026-07-05 - Step 15

- Completed: Produced the final readiness review and closed the 15-step provider/model compatibility execution plan. The final decision is `partially sufficient`: AstraBridge now has a disciplined compatibility system for controlled same-task provider/model switching with explicit metadata, validation evidence, UI warnings, fallback guidance, and onboarding gates, but it should not claim arbitrary seamless switching across all providers/models.
- Files changed: `PRIVATE/provider-compatibility/reports/step15-final-readiness-review-20260705.md`, `PLAN/PROVIDER_MODEL_COMPATIBILITY_EXECUTION_PLAN.md`
- Validation: Ran the backend compatibility unittest suite covering provider matrix, provider catalog, transport registry, reasoning normalization, tool-call compatibility, context gate, handoff, provider smoke, model catalog, and project sidebar (`35 tests`, `OK`); ran desktop vitest for capability routes, project tree, and task summary (`19 tests`, `3 files passed`); ran desktop `tsc --noEmit`; ran sidecar `py_compile` over the final changed compatibility modules; ran `git diff --check`; validated the matrix helper with a secret-free sample matrix; summarized Step 9-12 preserved evidence statuses; and ran PCRE2 secret scans over changed compatibility code/docs/UI paths plus `PRIVATE/provider-compatibility/reports`, `runs`, and Step 13 screenshots with no matches.
- Blockers: None for completing this execution plan. Residual risks remain for a later execution slice: direct official OpenAI evidence, Kimi code-agent/schema normalization, GLM command-event verification, Qwen TTS, Yunwu image artifact persistence, compact/long-context provider-backed validation, and in-app browser tab API screenshot reliability.
- Next step: No remaining step in this plan. Recommended follow-up is the final report's targeted residual-risk slice, starting with Kimi/Moonshot shell tool schema normalization or Qwen TTS/Yunwu image artifact persistence depending on product priority.
